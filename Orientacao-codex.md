# Lista de tarefas — dados reais, voxelização e IA

## Parsers e inspeção de datasets

- [x] Corrigir a configuração do Elaphes para o formato `.ply` em
  `configs/datasets.yaml`.
- [x] Implementar o parser incremental `.f32` em `src/cavegen/datastream/f32.py`:
  validação do layout, `numpy.memmap` somente leitura e lotes XYZ `float32`.
- [x] Implementar o parser incremental `.ply` em `src/cavegen/datastream/ply.py`:
  validação de cabeçalho, PLY ASCII por streaming e PLY binário por
  `numpy.memmap`.
- [x] Criar testes sintéticos para PLY ASCII, binário little-endian e cabeçalho
  inválido em `tests/test_ply.py`.
- [ ] Inspecionar formalmente `data/raw/nasa/indian_tunnel.f32`: confirmar
  endianness, layout de sete atributos e valores plausíveis de XYZ.
- [x] Inspecionar o cabeçalho real de
  `/run/media/midnavi/Pablo/TCC/DATA/RAW/elaphes_cave.ply`: PLY ASCII 1.0,
  `94_465_067` vértices, `vertex` como primeiro elemento, XYZ `float64` e 16
  atributos escalares adicionais. Um lote real de 2.048 pontos foi lido com
  sucesso como XYZ `float32` finito.
- [x] Adicionar `reservoir_sample_xyz` em `cavegen.datastream.sampling` para
  amostragem reprodutível por `max_points`, sem carregar o dataset inteiro.

## Pré-processamento e voxelização

- [x] Implementar e testar `calculate_xyz_bounds` em
  `src/cavegen/datastream/bounds.py`: mínimos e máximos incrementais,
  `float32`, lotes vazios, validações e testes em `tests/test_bounds.py`.
- [x] Executar `calculate_xyz_bounds` sobre todos os `94_465_067` vértices do
  Elaphes e registrar os limites definitivos para a normalização em
  `data/params/elaphes_xyz_bounds.json`.
- [x] Definir e implementar a normalização espacial em
  `src/cavegen/core/normalization.py`, preservando proporções com uma escala
  compartilhada, padding simétrico e tratamento de eixos degenerados.
- [x] Criar `src/cavegen/core/voxelization.py` para gerar
  `surface_voxels: np.ndarray[bool]` a partir de pontos normalizados.
- [x] Integrar leitura PLY, limites persistidos, normalização e voxelização em
  `src/cavegen/datastream/reference_preprocessing.py`, com teste de integração
  em `tests/test_reference_preprocessing.py`.
- [x] Voxelizar o Elaphes em `32³`: o arquivo
  `elaphes_surface_32.npz` contém 245 voxels de superfície em 32.768 (0,75%).
- [ ] Avaliar o Elaphes em `64³` e `128³` somente após inspecionar o resultado
  salvo em `32³`.
- [x] Salvar referências de superfície em `.npz` com metadados de origem,
  resolução e normalização, em formato separado de `Volume3D`.
- [ ] Documentar em `docs/` a diferença metodológica entre `surface_voxels` e
  `void_voxels`, incluindo as limitações de usar IoU diretamente entre ambos.
- [ ] Definir e justificar qualquer conversão de superfície para volume vazio
  antes de comparar dados reais com os geradores.

## Dataset para GAN e Colab

- [ ] Gerar um dataset sintético inicial com Random Walk e Cellular Automata.
- [ ] Produzir inicialmente cerca de 1.000 volumes `32³` e manter dados e
  checkpoints fora do Git.
- [ ] Definir o formato para PyTorch: `(B, 1, D, H, W)`.
- [ ] Criar notebook mínimo em `notebooks/colab/` com instalação, carregamento
  de `.npz`, visualização de slices, `Dataset`, `DataLoader` e inspeção de um
  batch.
- [ ] Implementar um baseline neural simples (autoencoder ou DCGAN) antes de
  iniciar WGAN ou PCGRL.

## Ordem recomendada

1. Validar os dois datasets reais com seus parsers.
2. Calcular limites e normalização incrementalmente.
3. Voxelizar a superfície em baixa resolução e documentar a semântica.
4. Gerar o dataset sintético e preparar o notebook Colab.
5. Treinar GAN; deixar PCGRL para depois do baseline clássico e neural.
