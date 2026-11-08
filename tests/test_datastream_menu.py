"""Terminal preparation menu uses the same reproducible CLI for each run."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
import laspy
import numpy as np

from cavegen.datastream.menu import main
from cavegen.datastream.voxel_io import load_volume_npz


class DatastreamMenuTests(unittest.TestCase):
    def test_foreground_menu_generates_outputs_and_reproduction_record(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, folder = root / 'cloud with spaces.xyz', root / 'out'
            source.write_text('0 0 0\n1 1 1\n')
            answers = ['1', f'"{source}"', '8', str(folder), '', '', '', '', '1', '0']
            with patch('builtins.input', side_effect=answers), redirect_stdout(StringIO()) as log:
                main()
            self.assertTrue((folder / 'surface.npz').is_file())
            self.assertEqual(load_volume_npz(folder / 'interior.npz').open_voxels, 0)
            receipt = json.loads((folder / 'surface.run.json').read_text())
            self.assertEqual(receipt['surface_metadata']['volume_shape_zyx'], [8, 8, 8])
            self.assertEqual(receipt['processing']['progress_every'], 1000000)
            self.assertIn('Comando equivalente', log.getvalue())

    def test_menu_accepts_las_and_preserves_its_transform_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, folder = root / 'cloud.las', root / 'out'
            header = laspy.LasHeader(point_format=0, version='1.2')
            header.scales = np.array([.01, .01, .01])
            header.offsets = np.array([1000., 2000., 3000.])
            cloud = laspy.LasData(header)
            cloud.x, cloud.y, cloud.z = [1000., 1001.], [2000., 2001.], [3000., 3001.]
            cloud.write(source)
            answers = ['1', str(source), '8', str(folder), '', '', '', '', '1', '0']
            with patch('builtins.input', side_effect=answers), redirect_stdout(StringIO()):
                main()
            volume = load_volume_npz(folder / 'interior.npz')
            self.assertEqual(volume.metadata['source_format'], 'las')
            self.assertEqual(volume.metadata['las_header']['offsets_xyz'], [1000, 2000, 3000])

    def test_background_launch_is_detached_and_records_log_and_pid(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, folder = root / 'cloud.xyz', root / 'out'
            source.write_text('0 0 0\n')
            answers = ['1', str(source), '8 10 12', str(folder), '', '2', '0', 'n', '2', '0']
            with patch('builtins.input', side_effect=answers), redirect_stdout(StringIO()), \
                    patch('cavegen.datastream.menu.subprocess.Popen') as launch:
                launch.return_value.pid = 12345
                main()
            command = launch.call_args.args[0]
            self.assertIn(str(source), command)
            self.assertNotIn('--interior-output', command)
            self.assertEqual(command[command.index('--shape') + 1:command.index('--shape') + 4],
                             ['8', '10', '12'])
            self.assertTrue(launch.call_args.kwargs['start_new_session'])
            self.assertTrue((folder / 'surface.log').is_file())
            self.assertEqual((folder / 'surface.pid').read_text().strip(), '12345')

    def test_menu_does_not_overwrite_an_existing_preparation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'cloud.xyz'
            source.write_text('0 0 0\n')
            (root / 'surface.npz').write_bytes(b'existing')
            answers = ['1', str(source), '64', str(root), '', '', '', '', '0']
            with patch('builtins.input', side_effect=answers), redirect_stdout(StringIO()) as log:
                main()
            self.assertIn('saídas anteriores', log.getvalue())
            self.assertEqual((root / 'surface.npz').read_bytes(), b'existing')

    def test_invalid_input_is_reprompted_and_cancellation_writes_nothing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, folder = root / 'cloud.xyz', root / 'out'
            source.write_text('0 0 0\n')
            answers = ['bad', '1', '/missing/cloud.xyz', str(source), '0', '16',
                       str(folder), '', 'bad', '2', '-1', '2', 'maybe', 'n', '0', '0']
            with patch('builtins.input', side_effect=answers), redirect_stdout(StringIO()) as log:
                main()
            self.assertFalse(folder.exists())
            self.assertIn('dimensões positivas', log.getvalue())

    def test_eof_exits_cleanly(self):
        with patch('builtins.input', side_effect=EOFError), redirect_stdout(StringIO()) as log:
            main()
        self.assertIn('Menu encerrado', log.getvalue())
