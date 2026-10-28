"""Synthetic-only end-to-end tests for a prospectively fixed human producer."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import numpy as np
    from scipy.io import savemat
    from examples.human_recording import run as producer
except ImportError:
    producer = None


@unittest.skipIf(producer is None, 'optional human-demo NumPy/SciPy environment is unavailable')
class HumanWorkflowTests(unittest.TestCase):
    def fixture(self, directory):
        directory = Path(directory)
        inputs = directory / 'inputs'
        blocks = []
        for day, role, block in ((658, 'train', 'Block_05'), (665, 'train', 'Block_06'),
                                  (675, 'evaluation', 'Block_06'), (675, 'evaluation', 'Block_07'),
                                  (689, 'evaluation', 'Block_13')):
            folder = inputs / f'day_{day}' / block
            folder.mkdir(parents=True)
            n = 16
            x = np.arange(n)[:, None] * np.linspace(.01, .04, 192)[None, :] + day / 1000
            labels = np.column_stack([np.linspace(0, .5, n), np.linspace(0, -.2, n)])
            savemat(folder / 'data.mat', dict(nctx=x, labels=labels, cursorVel=np.full((n, 2), 9876.)))
            savemat(folder / 'task.mat', dict(name='circleOfCircles', nPointsPerBlock=n,
                startStops=np.array([[2, 8], [10, 16]]), excludeTrials=np.array([0, 0])))
            savemat(folder / 'info.mat', dict(targetPos=labels, cursorPos=np.zeros((n, 2))))
            blocks.append(dict(day=day, block=block, role=role, n_bins=n, expected_eligible_bins=8,
                files={name: producer.digest(folder / name) for name in ('data.mat','task.mat','info.mat')}))
        plan = dict(protocol_id='synthetic-human-producer-test', blocks=blocks,
            dataset=dict(doi='synthetic-test-only'),
            data=dict(bin_seconds=.02, n_channels=192, common_history_bins=4,
                      units='dataset coordinate units', target_kind='inferred_cursor_to_target_vector'),
            models=dict(ridge_lambda=1., baseline=dict(id='baseline', history_bins=1),
                        candidate=dict(id='candidate', history_bins=4)),
            comparison=dict(reporting_tolerance=None, numerical_tolerance=1e-9))
        protocol = directory / 'protocol.json'; producer.write_json(protocol, plan)
        return inputs, protocol, plan

    def test_prediction_boundary_pinned_replay_and_full_denominators(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs, protocol, plan = self.fixture(temporary)
            output = Path(temporary) / 'output'
            actual_read = producer.read_targets
            actual_fit = producer.fit_source_ridge
            labels_opened, fits = [], []
            def guarded_read(path, spec):
                labels_opened.append((spec['day'], spec['block']))
                if spec['role'] == 'evaluation':
                    ready = json.loads((output / 'predictions-ready.json').read_text())
                    self.assertEqual(len(ready['predictions']), 6)
                    self.assertTrue(all((output / name).is_file() for name in ready['predictions']))
                    self.assertEqual(len(fits), 2)
                return actual_read(path, spec)
            def fit(x, y, alpha):
                fits.append((x.shape, y.shape, alpha))
                self.assertTrue(all(day < 675 for day, block in labels_opened))
                return actual_fit(x, y, alpha)
            with patch.object(producer, 'PROTOCOL_SHA256', producer.digest(protocol)), \
                 patch.object(producer, '_check_environment'), \
                 patch.object(producer, 'read_targets', side_effect=guarded_read), \
                 patch.object(producer, 'fit_source_ridge', side_effect=fit):
                result = producer.run(inputs, output, protocol)
                with self.assertRaises(FileExistsError):
                    producer.run(inputs, output, protocol)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(result['training_rows'], 16)
            self.assertEqual(result['pooled']['n_samples'], 24)
            self.assertEqual(result['excluded_counts']['evaluation'], 24)
            self.assertEqual(result['scoring_reproduction'], 'passed')
            self.assertEqual([shape[0] for shape in fits], [(16, 192), (16, 768)])
            evaluation = json.loads((output / 'comparison/evaluation.json').read_text())['payload']
            self.assertEqual(len(evaluation['records']), 48)
            self.assertEqual(evaluation['target_kind'], 'inferred_cursor_to_target_vector')
            rows = {r['sample_id']:r for r in evaluation['records'] if r['session_id'] == 'T11-day-0675'}
            self.assertEqual(rows['block-06:bin-000016']['timestamp'], .32)
            self.assertEqual(rows['block-07:bin-000001']['timestamp'], .34)
            manifest = json.loads((output / 'comparison/manifest.json').read_text())
            self.assertEqual(manifest['metric'], 'inferred_target_vector_rmse')
            self.assertTrue((output / 'reference/baseline.json').is_file())
            self.assertTrue((output / 'receipt.json').is_file())

    def test_corrupt_input_stops_before_fitting_and_preserves_failure_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs, protocol, plan = self.fixture(temporary)
            (inputs / 'day_689/Block_13/data.mat').write_bytes(b'not the frozen data')
            output = Path(temporary) / 'failed'
            with patch.object(producer, 'PROTOCOL_SHA256', producer.digest(protocol)), \
                 patch.object(producer, '_check_environment'), \
                 patch.object(producer, 'fit_source_ridge') as fit:
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    producer.run(inputs, output, protocol)
                fit.assert_not_called()
            receipt = json.loads((output / 'failure.json').read_text())
            self.assertEqual(receipt['phase'], 'admission')
            self.assertIn('T11-day-0689', receipt['selected_sessions'])
            self.assertFalse((output / 'comparison').exists())

    def test_unfrozen_protocol_refused_before_any_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs, protocol, _ = self.fixture(temporary)
            output = Path(temporary) / 'no-output'
            with self.assertRaisesRegex(ValueError, 'protocol bytes'):
                producer.run(inputs, output, protocol)
            self.assertFalse(output.exists())
