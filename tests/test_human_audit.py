"""Synthetic refusal controls for the independent human-recording audit."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from scipy.io import savemat
    from examples.human_recording.audit import audit_run
    from bci_regression import EvaluationSet, PredictionSet, compare
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


@unittest.skipUnless(AVAILABLE, "NumPy/SciPy human-example dependencies are optional")
class HumanAuditTests(unittest.TestCase):
    def fixture(self, root):
        inputs = root / "input"
        specs, data = [], {}
        counts = {"train": {}, "evaluation": {}}
        for day, blocknum, role in [(1, 1, "train"), (2, 1, "train"), (3, 1, "evaluation"), (3, 2, "evaluation")]:
            n = 24
            directory = inputs / f"day_{day}" / f"Block_{blocknum:02d}"
            directory.mkdir(parents=True)
            neural = (np.arange(n)[:, None] ** 2 + np.arange(192)[None, :] * (day + 2)) % 13
            neural = neural.astype(float)
            neural[:, -1] = 3.0  # Exercise exactly constant source columns.
            targets = np.column_stack([np.arange(n) * .03 + day / 10, -np.arange(n) ** 2 / 100])
            targets[5] = 0.0  # Retain an eligible zero displacement.
            task = dict(name="circleOfCircles", nPointsPerBlock=n,
                        startStops=np.array([[2, 7], [10, 13], [15, 23]]),
                        excludeTrials=np.array([0, 1, 0], dtype=np.uint8))
            savemat(directory / "data.mat", dict(nctx=neural, labels=targets))
            savemat(directory / "task.mat", task)
            savemat(directory / "info.mat", dict(targetPos=targets, cursorPos=np.zeros_like(targets)))
            # Hand-declared oracle for 1-based inclusive trial ranges.
            eligible = np.array([4, 5, 6, 17, 18, 19, 20, 21, 22], dtype=np.int64)
            reasons = ["outside-trial"] * n
            for i in [1, 2, 3, 14, 15, 16]:
                reasons[i] = "history-warmup"
            for i in [9, 10, 11, 12]:
                reasons[i] = "source-excluded-trial"
            for i in eligible:
                reasons[i] = ""
            exclusions = {"outside-trial": 5, "history-warmup": 6, "source-excluded-trial": 4}
            spec = dict(day=day, block=f"Block_{blocknum:02d}", n_bins=n, role=role,
                        expected_eligible_bins=9, expected_exclusions=exclusions,
                        files={name: sha(directory / name) for name in ("data.mat", "task.mat", "info.mat")})
            specs.append(spec)
            data[day, blocknum] = neural, targets, eligible, reasons
            for key, value in dict(exclusions, eligible=9).items():
                counts[role][key] = counts[role].get(key, 0) + value
        protocol = dict(protocol_id="synthetic-human-audit", blocks=specs, expected_counts=counts,
            data=dict(n_channels=192, common_history_bins=4, bin_seconds=.02,
                      target_kind="inferred_cursor_to_target_vector", units="dataset coordinate units"),
            models=dict(baseline=dict(id="current", history_bins=1), candidate=dict(id="history", history_bins=4), ridge_lambda=1.0),
            comparison=dict(numerical_tolerance=1e-9, reporting_tolerance=None))
        write(root / "protocol.json", protocol)
        digest = sha(root / "protocol.json")
        write(root / "inputs.json", specs)
        models, ready_models = {}, {}
        source = [data[1, 1], data[2, 1]]
        y = np.vstack([a[1][a[2]] for a in source])
        for role, history in [("baseline", 1), ("candidate", 4)]:
            x = np.array([np.hstack([a[0][i-j] for j in range(history)]) for a in source for i in a[2]])
            mean, scale, intercept = x.mean(axis=0), x.std(axis=0), y.mean(axis=0)
            scale[scale == 0] = 1
            z = (x - mean) / scale
            # Tiny synthetic dual solve, separate from the producer's primal fit.
            weights = z.T @ np.linalg.solve(z @ z.T + len(y) * np.eye(len(y)), y - intercept)
            model = dict(schema_version=1, kind="source_standardized_ridge", feature_mean=mean.tolist(),
                         feature_scale=scale.tolist(), weights=weights.tolist(), target_mean=intercept.tolist(),
                         alpha=1.0, n_source_rows=len(y))
            write(root / f"models/{role}.json", dict(model_id=protocol["models"][role]["id"],
                  history_bins=history, protocol_sha256=digest, model=model))
            models[role] = history, mean, scale, weights, intercept
            ready_models[role] = dict(sha256=sha(root / f"models/{role}.json"), n_training_rows=len(y),
                                      model_id=protocol["models"][role]["id"])
        rows, predicted_rows, ready_predictions = [], {"baseline": [], "candidate": []}, {}
        for blocknum in (1, 2):
            neural, targets, indices, reasons = data[3, blocknum]
            sid, bid = "T11-day-0003", f"block-{blocknum:02d}"
            for i, target in enumerate(targets):
                rows.append(dict(session_id=sid, sample_id=f"{bid}:bin-{i+1:06d}",
                    timestamp=((blocknum - 1) * 24 + i + 1) * .02,
                    target_vx=float(target[0]), target_vy=float(target[1]),
                    eligible=not reasons[i], exclusion_reason=reasons[i]))
            for role, (history, mean, scale, weights, intercept) in models.items():
                x = np.array([np.hstack([neural[i-j] for j in range(history)]) for i in indices])
                values = (x - mean) / scale @ weights + intercept
                relative = f"predictions/{role}/{sid}-{bid}.npz"
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                np.savez(root / relative, sample_indices=indices, predicted_vector=values)
                ready_predictions[relative] = sha(root / relative)
                predicted_rows[role].extend(dict(session_id=sid, sample_id=f"{bid}:bin-{i+1:06d}",
                    predicted_vx=float(v[0]), predicted_vy=float(v[1])) for i, v in zip(indices, values))
        write(root / "predictions-ready.json", dict(protocol_sha256=digest, models=ready_models,
              predictions=ready_predictions,
              phase="all_evaluation_predictions_saved_before_evaluation_labels_opened_in_this_run"))
        evaluation = EvaluationSet.from_records(rows, evaluation_id=protocol["protocol_id"],
            units=protocol["data"]["units"], coordinates="MINDFUL stored cursor-to-target x,y displacement; source coordinate scale retained",
            target_kind=protocol["data"]["target_kind"])
        predictions = [PredictionSet.from_records(predicted_rows[role], run_id=protocol["models"][role]["id"],
                                                  evaluation=evaluation) for role in ("baseline", "candidate")]
        compare(evaluation, *predictions, numerical_tolerance=1e-9, output_dir=root / "comparison")
        return inputs, digest

    def run_audit(self, root, fixture):
        inputs, digest = fixture
        return audit_run(root, inputs, expected_protocol_sha256=digest)

    def rehash_ready(self, root, relative):
        path = root / "predictions-ready.json"
        ready = json.loads(path.read_text())
        if relative.startswith("models/"):
            role = Path(relative).stem
            ready["models"][role]["sha256"] = sha(root / relative)
        else:
            ready["predictions"][relative] = sha(root / relative)
        write(path, ready)

    def test_valid_independent_audit_retains_zero_targets_and_all_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_audit(root, self.fixture(root))
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["input_files_verified"], 12)
            self.assertEqual(result["training_rows"], 18)
            self.assertEqual(result["pooled"]["n_samples"], 18)
            self.assertEqual(result["sessions"][0]["n_expected"], 18)
            self.assertTrue(all(not Path(f["path"]).is_absolute() for f in result["evidence_files"]))

    def test_mutated_protocol_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            path = root / "protocol.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "Frozen protocol identity"):
                self.run_audit(root, fixture)

    def test_mutated_raw_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            path = fixture[0] / "day_3/Block_01/data.mat"
            path.write_bytes(path.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "Source hash mismatch"):
                self.run_audit(root, fixture)

    def test_test_fitted_scaler_is_rejected_even_with_updated_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            relative = "models/candidate.json"
            model = json.loads((root / relative).read_text())
            model["model"]["feature_mean"][0] += .25
            write(root / relative, model)
            self.rehash_ready(root, relative)
            with self.assertRaisesRegex(ValueError, "training-only mean"):
                self.run_audit(root, fixture)

    def test_modified_weights_fail_optimality_without_refitting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            relative = "models/candidate.json"
            model = json.loads((root / relative).read_text())
            model["model"]["weights"][0][0] += .25
            write(root / relative, model)
            self.rehash_ready(root, relative)
            with self.assertRaisesRegex(ValueError, "optimality residual"):
                self.run_audit(root, fixture)

    def test_wrong_trial_start_index_cannot_shrink_or_shift_population(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            relative = "predictions/candidate/T11-day-0003-block-01.npz"
            with np.load(root / relative) as saved:
                indices, values = saved["sample_indices"], saved["predicted_vector"]
            indices[0] -= 1
            np.savez(root / relative, sample_indices=indices, predicted_vector=values)
            self.rehash_ready(root, relative)
            with self.assertRaisesRegex(ValueError, "indices differ from trial mask"):
                self.run_audit(root, fixture)

    def test_wrong_history_predictions_rejected_even_with_updated_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            relative = "predictions/candidate/T11-day-0003-block-01.npz"
            with np.load(root / relative) as saved:
                indices, values = saved["sample_indices"], saved["predicted_vector"]
            values[3] = values[2]  # Last previous-trial output reused in the next trial.
            np.savez(root / relative, sample_indices=indices, predicted_vector=values)
            self.rehash_ready(root, relative)
            with self.assertRaisesRegex(ValueError, "reconstructed predictions"):
                self.run_audit(root, fixture)

    def test_rebound_target_cannot_replace_original_inferred_vector(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            path = root / "comparison/evaluation.json"
            doc = json.loads(path.read_text())
            doc["payload"]["records"][0]["target_vx"] += 1
            doc["fingerprint"] = canonical(doc["payload"])
            write(path, doc)
            for role in ("baseline", "candidate"):
                path = root / f"comparison/{role}.json"
                pred = json.loads(path.read_text())
                pred["payload"]["evaluation_fingerprint"] = doc["fingerprint"]
                pred["digest"] = canonical(pred["payload"])
                write(path, pred)
            with self.assertRaisesRegex(ValueError, "stored inferred target differs"):
                self.run_audit(root, fixture)

    def test_changed_session_score_rejected_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            path = root / "comparison/comparison.json"
            result = json.loads(path.read_text())
            result["sessions"][0]["candidate_rmse"] += .1
            write(path, result)
            with self.assertRaisesRegex(ValueError, "candidate_rmse"):
                self.run_audit(root, fixture)


if __name__ == "__main__":
    unittest.main()
