"""Synthetic-only checks for the isolated public-recording prediction producer."""

from dataclasses import FrozenInstanceError
import inspect
import json
import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from examples.public_recording.model import (
        RidgeModel, causal_features, fit_source_ridge, predict,
    )


@unittest.skipIf(np is None, "Public-recording producer tests require optional NumPy")
class PublicModelTests(unittest.TestCase):
    def test_current_to_older_order_and_common_rows(self):
        rates = np.arange(8 * 96, dtype=np.float64).reshape(8, 96)
        indices = np.array([3, 5, 7])
        baseline = causal_features(rates, indices, 1)
        candidate = causal_features(rates, indices, 4)
        np.testing.assert_array_equal(baseline, rates[indices])
        np.testing.assert_array_equal(candidate[:, :96], baseline)
        for row, index in enumerate(indices):
            np.testing.assert_array_equal(
                candidate[row], np.concatenate([rates[index - lag] for lag in range(4)])
            )
        self.assertEqual(candidate.dtype, np.float64)

    def test_future_rates_cannot_change_previous_features(self):
        rates = np.arange(9 * 96, dtype=np.float64).reshape(9, 96)
        before = causal_features(rates, np.array([3, 4]), 4)
        rates[5:] = 1_000_000
        np.testing.assert_array_equal(before, causal_features(rates, np.array([3, 4]), 4))

    def test_session_reset_and_order_have_no_hidden_state(self):
        first = np.arange(6 * 96, dtype=np.float64).reshape(6, 96)
        second = np.full((6, 96), 100.0)
        expected_first = causal_features(first, np.array([3, 4, 5]), 4)
        second_features = causal_features(second, np.array([3, 4, 5]), 4)
        np.testing.assert_array_equal(second_features, np.full((3, 384), 100.0))
        np.testing.assert_array_equal(expected_first, causal_features(first, np.array([3, 4, 5]), 4))
        with self.assertRaises(ValueError):
            causal_features(second, np.array([2]), 4)

    def test_feature_contract_rejects_invalid_indices_and_channels(self):
        rates = np.ones((8, 96))
        invalid_indices = ([3, 3], [4, 3], [-1], [8], [3.0], [], [True])
        for indices in invalid_indices:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                causal_features(rates, np.array(indices), 4)
        for history in (0, 2, 5, True, 1.0):
            with self.subTest(history=history), self.assertRaises(ValueError):
                causal_features(rates, np.array([3]), history)
        for wrong_rates in (np.ones((8, 95)), np.ones((8, 97)), -rates, rates * np.nan):
            with self.assertRaises(ValueError):
                causal_features(wrong_rates, np.array([3]), 4)

    def test_closed_form_solution_and_unpenalized_intercept(self):
        # X has mean 0/std 1. Both targets have slope 2; ridge alpha=1
        # shrinks those slopes to 1 while preserving target means 0 and 6.
        X = np.array([[-1.0], [1.0]])
        Y = np.array([[-2.0, 4.0], [2.0, 8.0]])
        model = fit_source_ridge(X, Y)
        np.testing.assert_allclose(model.weights, [[1.0, 1.0]], rtol=0, atol=1e-14)
        np.testing.assert_array_equal(model.target_mean, [0.0, 6.0])
        np.testing.assert_allclose(predict(model, X), [[-1.0, 5.0], [1.0, 7.0]], rtol=0, atol=1e-14)

    def test_mean_loss_penalty_is_invariant_to_duplicate_source_rows(self):
        X = np.array([[1.0], [3.0]])
        Y = np.array([[0.0, 2.0], [4.0, 6.0]])
        original = fit_source_ridge(X, Y)
        repeated = fit_source_ridge(np.repeat(X, 4, axis=0), np.repeat(Y, 4, axis=0))
        np.testing.assert_allclose(original.weights, repeated.weights, rtol=0, atol=1e-14)
        np.testing.assert_allclose(original.predict(X), repeated.predict(X), rtol=0, atol=1e-14)

    def test_population_scaling_and_zero_variance(self):
        X = np.array([[1.0, 7.0], [3.0, 7.0]])
        model = fit_source_ridge(X, np.array([[0.0, 2.0], [4.0, 6.0]]))
        np.testing.assert_array_equal(model.feature_mean, [2.0, 7.0])
        np.testing.assert_array_equal(model.feature_scale, [1.0, 1.0])
        np.testing.assert_array_equal(model.weights[1], [0.0, 0.0])
        constant = fit_source_ridge(np.full((2, 1), 7.0), np.array([[9.0, 4.0], [11.0, 8.0]]), alpha=100)
        np.testing.assert_array_equal(constant.weights, [[0.0, 0.0]])
        np.testing.assert_array_equal(constant.predict([[7.0], [9.0]]), [[10.0, 6.0], [10.0, 6.0]])

    def test_prediction_never_refits_source_normalization(self):
        model = fit_source_ridge([[1.0], [3.0]], [[0.0, 2.0], [4.0, 6.0]])
        snapshot = model.to_dict()
        batch = np.array([[101.0], [-33.0], [2.0]])
        together = model.predict(batch)
        separate = np.vstack([model.predict(row[None, :]) for row in batch])
        np.testing.assert_array_equal(together, separate)
        self.assertEqual(snapshot, model.to_dict())
        np.testing.assert_array_equal(model.feature_mean, [2.0])
        np.testing.assert_array_equal(model.feature_scale, [1.0])

    def test_prediction_signature_has_no_labels(self):
        self.assertEqual(tuple(inspect.signature(predict).parameters), ("model", "X"))
        self.assertEqual(tuple(inspect.signature(RidgeModel.predict).parameters), ("self", "X"))
        model = fit_source_ridge([[-1.0], [1.0]], [[0.0, 1.0], [2.0, 3.0]])
        with self.assertRaises(TypeError):
            predict(model, [[0.0]], Y=[[0.0, 0.0]])

    def test_json_roundtrip_retains_exact_source_parameters(self):
        X = np.array([[-1.0, 1.0], [0.0, 4.0], [1.0, 2.0]])
        model = fit_source_ridge(X, np.array([[1.0, 2.0], [3.0, 5.0], [4.0, 9.0]]))
        document = json.loads(json.dumps(model.to_dict(), allow_nan=False))
        restored = RidgeModel.from_dict(document)
        self.assertEqual(model.to_dict(), restored.to_dict())
        np.testing.assert_array_equal(model.predict(X), restored.predict(X))
        document["feature_mean"][0] = 999
        self.assertNotEqual(document["feature_mean"], restored.feature_mean.tolist())
        with self.assertRaises(ValueError):
            restored.weights[0, 0] = 1
        with self.assertRaises(FrozenInstanceError):
            restored.alpha = 9

    def test_invalid_fit_or_artifact_is_rejected(self):
        X, Y = np.array([[-1.0], [1.0]]), np.array([[0.0, 1.0], [2.0, 3.0]])
        for alpha in (0, -1, True, float("inf"), float("nan")):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                fit_source_ridge(X, Y, alpha=alpha)
        for bad_X, bad_Y in ((X[:0], Y[:0]), (X, Y[:, :1]), (X * np.nan, Y), (X, np.full(Y.shape, np.inf))):
            with self.assertRaises(ValueError):
                fit_source_ridge(bad_X, bad_Y)
        model = fit_source_ridge(X, Y)
        with self.assertRaises(ValueError):
            model.predict([[0.0, 0.0]])
        with self.assertRaises(ValueError):
            model.predict([[float("nan")]])
        document = model.to_dict()
        document["feature_scale"] = [0.0]
        with self.assertRaises(ValueError):
            RidgeModel.from_dict(document)


if __name__ == "__main__":
    unittest.main()
