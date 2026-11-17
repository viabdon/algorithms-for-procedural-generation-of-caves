"""GAN contracts verified on synthetic fixtures; no cave reference training."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from cavegen.core.volume import Volume3D
from cavegen.datastream.voxel_io import load_volume_npz, save_volume_npz
from cavegen.generators.gan_3d import GAN3DGenerator
from cavegen.training.evaluate_gan import evaluate_checkpoint, evaluation_seeds
from cavegen.training.gan_data import ReferenceDataset, decode_volume, encode_volume
from cavegen.training.gan_evaluation import compare_distributions, pattern_histogram
from cavegen.training.gan_models import Discriminator3D, Generator3D, ModelConfig, latent_for_seed
from cavegen.training.gan_training import GANTrainer, TrainingConfig, preflight, save_checkpoint, train
from cavegen.training.reference_data import make_splits, read_reference
from test_gan_reference_data import write_caves


@pytest.fixture(autouse=True)
def small_cpu_thread_pool():
    old = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(old)


@pytest.mark.parametrize("representation", ["occupancy", "sdf"])
@pytest.mark.parametrize("resolution", [16, 32, 64])
def test_model_shapes_and_output_domains(representation, resolution):
    config = ModelConfig(resolution, latent_dim=4, base_channels=2,
                         representation=representation)
    generator, discriminator = Generator3D(config), Discriminator3D(config)
    with torch.no_grad():
        field = generator(torch.zeros(2, 4))
        assert field.shape == (2, 1, resolution, resolution, resolution)
        assert discriminator(field).shape == (2,)
        assert torch.isfinite(field).all()
        assert field.min() >= (0 if representation == "occupancy" else -1)
        assert field.max() <= 1


@pytest.mark.parametrize("representation", ["occupancy", "sdf"])
def test_adversarial_step_has_finite_gradients_updates_both_models_and_r1(representation):
    cfg = TrainingConfig(model=ModelConfig(16, 4, 2, representation), r1_interval=1,
                         require_cuda=False)
    trainer = GANTrainer(cfg)
    g_before = [p.detach().clone() for p in trainer.generator.parameters()]
    d_before = [p.detach().clone() for p in trainer.discriminator.parameters()]
    air = np.zeros((16,) * 3, dtype=bool)
    air[3:12, 3:12, 3:12] = True
    real = torch.from_numpy(encode_volume(air, cfg.model))[None, None]
    result = trainer.optimization_step(real)
    assert all(np.isfinite(value) for value in result.values())
    assert result["r1"] > 0
    assert any(not torch.equal(a, b) for a, b in zip(g_before, trainer.generator.parameters()))
    assert any(not torch.equal(a, b) for a, b in zip(d_before, trainer.discriminator.parameters()))
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in trainer.generator.parameters())


def test_checkpoint_resume_restores_models_optimizers_and_rng_exactly(tmp_path):
    cfg = TrainingConfig(model=ModelConfig(16, 4, 2), require_cuda=False)
    first = GANTrainer(cfg)
    real = torch.zeros(1, 1, 16, 16, 16)
    real[..., 4:10, 4:10, 4:10] = 1
    first.optimization_step(real)
    path = tmp_path / "checkpoint.pt"
    provenance = {"experiment_id": "test"}
    save_checkpoint(path, first.checkpoint(provenance))
    expected = first.optimization_step(real)
    expected_field = first.fields([42])[0]
    resumed = GANTrainer(cfg)
    resumed.restore(torch.load(path, weights_only=True), provenance)
    actual = resumed.optimization_step(real)
    assert expected == actual
    np.testing.assert_array_equal(expected_field, resumed.fields([42])[0])
    with pytest.raises(ValueError, match="identity"):
        resumed.restore(torch.load(path, weights_only=True), {"experiment_id": "wrong"})


@pytest.mark.parametrize("seed", [0, 1, 42, 2**32-1, 2**63-1])
def test_arbitrary_inference_seed_roundtrip_npz_and_no_global_rng_side_effect(tmp_path, seed):
    trainer = GANTrainer(TrainingConfig(model=ModelConfig(16, 4, 2)))
    path = tmp_path / "weights.pt"
    save_checkpoint(path, trainer.checkpoint({"experiment_id": "test"}))
    generator = GAN3DGenerator(path)
    state = torch.get_rng_state().clone()
    field = generator.generate_field(seed)
    np.testing.assert_array_equal(field, generator.generate_field(seed))
    assert torch.equal(state, torch.get_rng_state())
    volume = generator.generate((16, 16, 16), seed)
    assert volume.metadata["seed"] == seed
    assert volume.data.dtype == np.bool_
    save_volume_npz(volume, tmp_path / "volume.npz")
    np.testing.assert_array_equal(volume.data, load_volume_npz(tmp_path / "volume.npz").data)
    with pytest.raises(ValueError, match="shape"):
        generator.generate((32, 32, 32), seed)


@pytest.mark.parametrize("seed", [-1, 2**63, True, 1.5])
def test_invalid_inference_seeds_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        latent_for_seed(seed, 4)


@pytest.mark.parametrize("case", ["solid", "air", "thin", "cube"])
def test_tsdf_sign_reconstructs_all_voxels_including_boundary(case):
    air = np.zeros((16,) * 3, dtype=bool)
    if case == "air":
        air[:] = True
    elif case == "thin":
        air[0, 2:14, 8] = True
    elif case == "cube":
        air[4:12, 4:12, 4:12] = True
    cfg = ModelConfig(16, representation="sdf")
    field = encode_volume(air, cfg)
    assert field.dtype == np.float32
    assert np.abs(field).max() <= 1
    np.testing.assert_array_equal(air, decode_volume(field, cfg))


def test_threshold_is_explicit_and_nonfinite_fields_are_rejected():
    cfg = ModelConfig(16)
    field = np.full((16,) * 3, 0.1)
    assert not decode_volume(field, cfg).any()
    with pytest.raises(ValueError):
        decode_volume(field * np.nan, cfg)


def test_reference_loader_enforces_candidate_opt_in_and_geometry(tmp_path):
    audit = write_caves(tmp_path)
    splits = make_splits(audit)
    fold = splits["folds"][0]["id"]
    with pytest.raises(ValueError, match="proxy"):
        ReferenceDataset(tmp_path, splits, fold, "train", ModelConfig(16))
    dataset = ReferenceDataset(tmp_path, splits, fold, "train", ModelConfig(16),
                               allow_candidate_proxy=True)
    assert len(dataset) == 2
    assert dataset[0].shape == (1, 16, 16, 16)
    with pytest.raises(ValueError, match="native resolution"):
        ReferenceDataset(tmp_path, splits, fold, "train", ModelConfig(32),
                          allow_candidate_proxy=True)
    row = next(r for r in audit["records"] if r["candidate"] and r["group"] == "archamps")
    data, metadata, _ = read_reference(tmp_path / row["path"])
    data[:] = False
    data[4, 4, 4] = True
    save_volume_npz(Volume3D(data, metadata), tmp_path / row["path"])
    from cavegen.datastream.surface_io import save_surface_npz
    shell = np.zeros_like(data)
    shell[3:6, 3:6, 3:6] = True
    shell[4, 4, 4] = False
    save_surface_npz(shell, (tmp_path / row["path"]).with_name("surface.npz"),
                     {**metadata, "kind": "surface_voxels", "semantic": "true_means_observed_surface"})
    # Audit again to freeze the changed content; it remains unusable for training.
    from cavegen.training.reference_data import audit_references
    bad_splits = make_splits(audit_references(tmp_path))
    # Archamps is validation in this fold and must be checked too.
    cfg = TrainingConfig(model=ModelConfig(16), allow_candidate_proxy=True)
    with pytest.raises(ValueError, match="Insufficient"):
        preflight(tmp_path, bad_splits, "holdout_markovspodmol", cfg)


def test_metric_controls_detect_empty_and_copied_generation():
    cube = np.zeros((16,) * 3, dtype=bool)
    cube[4:12, 4:12, 4:12] = True
    copied = compare_distributions([cube, cube], [cube], [cube])
    assert copied["selection_score"] == pytest.approx(0)
    assert copied["exact_training_copy_fraction"] == 1
    assert copied["duplicate_fraction"] == 0.5
    solid = np.zeros_like(cube)
    empty = compare_distributions([solid], [cube], [cube])
    assert empty["degenerate_fraction"] == 1
    assert empty["selection_score"] > copied["selection_score"]
    assert pattern_histogram(solid)[0] == 15**3
    assert pattern_histogram(~solid)[255] == 15**3


def test_explicit_seed_lists_and_ranges():
    assert evaluation_seeds(500, 3) == [500, 501, 502]
    assert evaluation_seeds(explicit=[2**63-1, 0]) == [2**63-1, 0]
    for bad in ([], [1, 1], [-1], [2**63]):
        with pytest.raises(ValueError):
            evaluation_seeds(explicit=bad)


def test_full_runner_checkpoint_evaluation_and_no_overwrite_on_synthetic_caves(tmp_path):
    root = tmp_path / "references"
    splits = make_splits(write_caves(root))
    cfg = TrainingConfig(model=ModelConfig(16, 4, 2), steps=1, batch_size=1,
                         validation_interval=1, validation_count=2,
                         allow_candidate_proxy=True, require_cuda=False)
    output = tmp_path / "run"
    train(root, splits, "holdout_indian_tunnel", cfg, output, device="cpu")
    assert (output / "best.pt").is_file()
    result = evaluate_checkpoint(output / "best.pt", root, splits, [0, 2**63-1],
                                  tmp_path / "evaluation")
    assert result["generated_count"] == 2
    assert result["seeds"] == [0, 2**63-1]
    assert result["copy_control"]["exact_training_copy_fraction"] == 1
    assert len(list((tmp_path / "evaluation").glob("*.field.npz"))) == 2
    with pytest.raises(FileExistsError):
        train(root, splits, "holdout_indian_tunnel", cfg, output, device="cpu")


def test_failure_records_status_and_preserves_last_complete_checkpoint(tmp_path, monkeypatch):
    root = tmp_path / "references"
    splits = make_splits(write_caves(root))
    config = TrainingConfig(model=ModelConfig(16, 4, 2), steps=1,
                             allow_candidate_proxy=True, require_cuda=False)
    def fail_step(self, real):
        raise FloatingPointError("synthetic regression fixture")
    monkeypatch.setattr(GANTrainer, "optimization_step", fail_step)
    output = tmp_path / "run"
    with pytest.raises(FloatingPointError):
        train(root, splits, "holdout_indian_tunnel", config, output, device="cpu")
    status = json.loads((output / "status.json").read_text())
    assert status["status"] == "stopped"
    checkpoint = torch.load(output / "latest.pt", weights_only=True)
    assert checkpoint["step"] == 0
    with pytest.raises(ValueError, match="untrained"):
        evaluate_checkpoint(output / "latest.pt", root, splits, [0], tmp_path / "evaluation")


@pytest.mark.parametrize("model", [dict(resolution=8), dict(latent_dim=0),
                                 dict(representation="surface"), dict(sdf_tau=float("nan"))])
def test_invalid_model_configs_are_rejected(model):
    with pytest.raises(ValueError):
        ModelConfig(**model)


def test_invalid_training_scalars_are_rejected():
    for values in (dict(batch_size=0), dict(learning_rate=float("nan")), dict(threshold=0),
                   dict(max_minutes=-1), dict(beta2=1), dict(r1_gamma=-1)):
        with pytest.raises(ValueError):
            TrainingConfig(**values)
