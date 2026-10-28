"""Synthetic acceptance checks for the independent retained-array auditor."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from bci_regression import EvaluationSet, PredictionSet, compare
    from examples.public_recording.audit import audit_run


@unittest.skipIf(np is None, "optional NumPy dependency is not installed")
class PublicAuditTests(unittest.TestCase):
    def fixture(self, root):
        protocol_path = Path(__file__).resolve().parents[1] / "docs/public-demo/protocol-v1.json"
        protocol_bytes = protocol_path.read_bytes()
        protocol = json.loads(protocol_bytes)
        (root / "protocol.json").write_bytes(protocol_bytes)
        protocol_digest = hashlib.sha256(protocol_bytes).hexdigest()
        inputs = [{key: item[key] for key in ("name", "session_id", "role", "md5", "size_bytes")}
                  | {"sha256": "a" * 64} for item in protocol["files"]]
        (root / "inputs.json").write_text(json.dumps(inputs))
        n = 12
        indices = np.arange(3, n)
        source_rates = np.arange(n)[:, None] + np.arange(96)[None, :].astype(float)
        source_rates[:, -1] = 5.0
        source_targets = np.column_stack((2 * np.arange(n) + 3, -np.arange(n) + 1)).astype(float)
        np.savez(root / "source-training.npz", rates=source_rates, targets=source_targets,
                 sample_indices=indices)
        (root / "models").mkdir()
        (root / "features").mkdir()
        snapshots = {}
        for label, history in (("baseline", 1), ("candidate", 4)):
            raw = np.column_stack([source_rates[indices - lag] for lag in range(history)])
            mean = raw.mean(axis=0)
            deviation = raw.std(axis=0)
            constant = deviation == 0
            scale = np.where(constant, 1.0, deviation)
            # All nonconstant standardized columns equal one centered unit-variance
            # vector z. Thus (J + I) W = [2*std, -std] has this analytic solution.
            training_std = float(np.std(indices))
            weights = np.tile([2 * training_std, -training_std], (96 * history, 1))
            weights /= int((~constant).sum()) + 1
            weights[constant] = 0.0
            model = {"feature_mean": mean.tolist(), "feature_scale": scale.tolist(),
                     "weights": weights.tolist(), "target_mean": source_targets[indices].mean(axis=0).tolist(),
                     "alpha": 1.0, "n_source_rows": len(indices)}
            snapshot = {"model_id": protocol["models"][label]["id"], "history_bins": history,
                        "source_session_id": protocol["files"][0]["session_id"],
                        "protocol_sha256": protocol_digest, "model": model}
            (root / f"models/{label}.json").write_text(json.dumps(snapshot))
            snapshots[label] = snapshot
            (root / f"predictions/{label}").mkdir(parents=True)
        evaluation_rows = []
        prediction_rows = {"baseline": [], "candidate": []}
        for offset, item in enumerate(protocol["files"][1:]):
            sid = item["session_id"]
            rates = 1.1 * np.arange(n)[:, None] + np.arange(96)[None, :] + offset
            rates[:, -1] = 5.0
            absolute_edges = 100.0 + np.arange(n + 1) * 0.064
            timestamps = absolute_edges[1:] - absolute_edges[0]
            np.savez(root / f"features/{sid}.npz", rates=rates, sample_indices=indices,
                     edge_indices=np.arange(n + 1) * 16, absolute_edges=absolute_edges,
                     timestamps=timestamps)
            for index in range(n):
                evaluation_rows.append({"session_id": sid, "sample_id": f"bin-{index:06d}",
                    "timestamp": float(timestamps[index]), "target_vx": float(index * 1.5 + offset),
                    "target_vy": float(-index * 0.75), "eligible": index >= 3,
                    "exclusion_reason": "" if index >= 3 else "causal-history warmup"})
            for label, snapshot in snapshots.items():
                model = snapshot["model"]
                raw = np.column_stack([rates[indices - lag] for lag in range(snapshot["history_bins"])])
                prediction = ((raw - model["feature_mean"]) / model["feature_scale"]) @ np.asarray(model["weights"]) + model["target_mean"]
                np.savez(root / f"predictions/{label}/{sid}.npz", sample_indices=indices,
                         predicted_velocity=prediction)
                for index, value in zip(indices, prediction):
                    prediction_rows[label].append({"session_id": sid, "sample_id": f"bin-{index:06d}",
                        "predicted_vx": float(value[0]), "predicted_vy": float(value[1])})
        evaluation = EvaluationSet.from_records(evaluation_rows, evaluation_id="synthetic-audit-only",
            units=protocol["data"]["units"], coordinates=protocol["data"]["coordinates"])
        baseline, candidate = [PredictionSet.from_records(prediction_rows[label], evaluation=evaluation,
            run_id=protocol["models"][label]["id"]) for label in ("baseline", "candidate")]
        compare(evaluation, baseline, candidate, numerical_tolerance=1e-9, output_dir=root / "comparison")
        return protocol

    def test_valid_synthetic_run_passes_independent_reconstruction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            result = audit_run(root)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(len(result["sessions"]), 3)
            self.assertEqual(result["pooled"]["n_samples"], 27)
            self.assertTrue(all(row["n_expected"] == 9 for row in result["sessions"]))
            self.assertTrue(all(not Path(row["path"]).is_absolute() for row in result["evidence_files"]))

    def test_changed_source_scaler_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / "models/candidate.json"
            snapshot = json.loads(path.read_text())
            snapshot["model"]["feature_mean"][0] += 0.5
            path.write_text(json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "source-only mean"):
                audit_run(root)

    def test_changed_weights_fail_normal_equations_without_refitting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / "models/baseline.json"
            snapshot = json.loads(path.read_text())
            snapshot["model"]["weights"][0][0] += 0.25
            path.write_text(json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "optimality residual"):
                audit_run(root)

    def test_changed_retained_prediction_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.fixture(root)
            sid = protocol["files"][1]["session_id"]
            path = root / f"predictions/candidate/{sid}.npz"
            with np.load(path) as values:
                indices = values["sample_indices"]
                prediction = values["predicted_velocity"]
            prediction[0, 0] += 0.5
            np.savez(path, sample_indices=indices, predicted_velocity=prediction)
            with self.assertRaisesRegex(ValueError, "reconstructed predictions"):
                audit_run(root)

    def test_changed_score_is_rejected_by_independent_arithmetic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / "comparison/comparison.json"
            result = json.loads(path.read_text())
            result["sessions"][0]["candidate_rmse"] += 1.0
            path.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, "candidate_rmse"):
                audit_run(root)

    def test_missing_prediction_does_not_shrink_audited_population(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = self.fixture(root)
            sid = protocol["files"][1]["session_id"]
            path = root / f"predictions/baseline/{sid}.npz"
            with np.load(path) as values:
                indices = values["sample_indices"][1:]
                prediction = values["predicted_velocity"][1:]
            np.savez(path, sample_indices=indices, predicted_velocity=prediction)
            with self.assertRaisesRegex(ValueError, "integer vector"):
                audit_run(root)


if __name__ == "__main__":
    unittest.main()
