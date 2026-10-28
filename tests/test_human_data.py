"""Synthetic boundary checks for the human recording importer."""
import unittest
from unittest.mock import patch
from pathlib import Path

try:
    import numpy as np
    from examples.human_recording import data
except ImportError:
    data = None


@unittest.skipIf(data is None, 'optional human-demo NumPy/SciPy environment is unavailable')
class HumanDataTests(unittest.TestCase):
    def block(self):
        rates = np.repeat(np.arange(20, dtype=float)[:, None], 192, axis=1)
        task = dict(name='circleOfCircles', nPointsPerBlock=20,
                    startStops=np.array([[2, 7], [9, 14], [16, 20]]),
                    excludeTrials=np.array([0, 1, 0]))
        return rates, task

    def test_matlab_inclusive_bounds_and_common_trial_warmup(self):
        rates, task = self.block()
        got = data.admit_neural(rates, task, n_bins=20)
        self.assertEqual(got.indices.tolist(), [4, 5, 6, 18, 19])
        self.assertEqual(got.reasons[0], 'outside-trial')
        self.assertEqual(got.reasons[1:4], ('history-warmup',) * 3)
        self.assertEqual(got.reasons[8:14], ('source-excluded-trial',) * 6)
        self.assertEqual(got.excluded_trials, 1)
        self.assertEqual(got.trials, 3)
        self.assertEqual(len(got.reasons), 20)

    def test_history_contains_current_then_prior_and_never_crosses_trials(self):
        rates, task = self.block()
        got = data.admit_neural(rates, task, n_bins=20)
        x = data.trial_features(got, 4).reshape(5, 4, 192)
        self.assertEqual(x[0, :, 0].tolist(), [4, 3, 2, 1])
        self.assertEqual(x[-1, :, 0].tolist(), [19, 18, 17, 16])
        self.assertEqual(data.trial_features(got, 1)[:, 0].tolist(), [4, 5, 6, 18, 19])
        rates[7:18] = 999
        changed = data.trial_features(data.admit_neural(rates, task, n_bins=20), 4)
        np.testing.assert_array_equal(changed[0], x[0].ravel())

    def test_rejects_invalid_trials_instead_of_clipping_or_dropping(self):
        rates, task = self.block()
        for bounds in ([[0, 5]], [[2, 21]], [[5, 2]], [[2, 5], [5, 7]], [[2.5, 6]]):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                data.admit_neural(rates, {**task, 'startStops': np.array(bounds), 'excludeTrials': np.zeros(len(bounds))}, n_bins=20)
        with self.assertRaises(ValueError):
            data.admit_neural(rates, {**task, 'excludeTrials': [0, 2, 0]}, n_bins=20)

    def test_rejects_bad_features_and_unexpected_task(self):
        rates, task = self.block()
        for replacement in (np.nan, np.inf, -1.):
            bad = rates.copy(); bad[8, 0] = replacement
            with self.subTest(value=replacement), self.assertRaises(ValueError):
                data.admit_neural(bad, task, n_bins=20)
        with self.assertRaises(ValueError):
            data.admit_neural(rates[:, :-1], task, n_bins=20)
        with self.assertRaises(ValueError):
            data.admit_neural(rates, {**task, 'name': 'personal use'}, n_bins=20)

    def test_short_trials_do_not_borrow_history(self):
        rates, task = self.block()
        task.update(startStops=np.array([[2, 3], [6, 10]]), excludeTrials=[0, 0])
        got = data.admit_neural(rates, task, n_bins=20)
        self.assertEqual(got.indices.tolist(), [8, 9])
        task.update(startStops=np.array([[2, 3]]), excludeTrials=[0])
        with self.assertRaisesRegex(ValueError, 'no eligible'):
            data.admit_neural(rates, task, n_bins=20)

    def test_loader_separates_features_and_targets_and_preserves_zero_targets(self):
        rates, task = self.block()
        spec = dict(n_bins=20, expected_eligible_bins=5)
        config = dict(n_channels=192, common_history_bins=4)
        calls = []
        targets = np.zeros((20, 2)); targets[4] = [0.3, -0.4]
        def fake(path, *, variable_names, simplify_cells):
            calls.append(variable_names)
            if variable_names == ['nctx']: return dict(nctx=rates)
            if variable_names == ['labels']: return dict(labels=targets)
            return task
        with patch.object(data, 'loadmat', side_effect=fake):
            got = data.read_neural(Path('block'), spec, config)
            self.assertFalse(any('labels' in v for v in calls))
            labels = data.read_targets(Path('block'), spec)
        np.testing.assert_array_equal(labels, targets)
        self.assertEqual(calls[-1], ['labels'])
        self.assertEqual(data.sample_id(dict(block='Block_06'), 263), 'block-06:bin-000264')
        self.assertEqual(data.session_id(dict(day=675)), 'T11-day-0675')
