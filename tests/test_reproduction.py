"""Evidence preservation and independent score-recomputation acceptance checks."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bci_regression import EvaluationSet, PredictionSet, compare, reproduce


class ReproductionAcceptanceTests(unittest.TestCase):
    def inputs(self, missing_candidate=False):
        evaluation = EvaluationSet.from_records([
            {"session_id": "one", "sample_id": "0", "timestamp": 0.0,
             "target_vx": 0.0, "target_vy": 0.0},
            {"session_id": "one", "sample_id": "1", "timestamp": 1.0,
             "target_vx": 1.0, "target_vy": -1.0},
        ], evaluation_id="reproduction-fixture", units="cm/s", coordinates="x-right,y-up")
        rows = [
            {"session_id": "one", "sample_id": "0", "predicted_vx": 0.0, "predicted_vy": 0.0},
            {"session_id": "one", "sample_id": "1", "predicted_vx": 1.0, "predicted_vy": -1.0},
        ]
        baseline = PredictionSet.from_records(rows, run_id="baseline", evaluation=evaluation)
        candidate = PredictionSet.from_records(
            rows[:1] if missing_candidate else rows,
            run_id="candidate", evaluation=evaluation,
        )
        return evaluation, baseline, candidate

    def write_bundle(self, root, **options):
        bundle = root / "comparison"
        result = compare(*self.inputs(), output_dir=bundle, **options)
        return bundle, result

    def change_report_and_refresh_file_digest(self, bundle, change):
        """Keep file hashes self-consistent to exercise recomputation, not just hashing."""
        report_path = bundle / "comparison.json"
        report = json.loads(report_path.read_text())
        change(report)
        report_path.write_text(json.dumps(report, allow_nan=False))
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["comparison.json"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, allow_nan=False))

    def test_complete_bundle_recomputes_exact_session_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, original = self.write_bundle(Path(directory), tolerance=0.0)
            repeated = reproduce(bundle)
            self.assertTrue(repeated["complete"])
            self.assertEqual(original, repeated)
            self.assertTrue((bundle / "manifest.json").is_file())
            self.assertTrue((bundle / "report.html").is_file())
            self.assertTrue((bundle / "session_metrics.csv").is_file())

    def test_incomplete_comparison_can_be_preserved_and_recomputed_as_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "incomplete"
            original = compare(*self.inputs(missing_candidate=True), output_dir=bundle)
            repeated = reproduce(bundle)
            self.assertFalse(repeated["complete"])
            self.assertIsNone(repeated["pooled"])
            self.assertEqual(repeated["sessions"][0]["status"], "invalid")
            self.assertEqual(original, repeated)

    def test_reproduction_can_save_a_new_independently_readable_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, original = self.write_bundle(root)
            destination = root / "reproduced"
            repeated = reproduce(bundle, output_dir=destination)
            self.assertEqual(original, repeated)
            self.assertEqual(repeated, reproduce(destination))

    def test_changed_retained_artifact_is_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, _ = self.write_bundle(root)
            (bundle / "report.html").write_text("changed report")
            destination = root / "must-not-exist"
            with self.assertRaises(ValueError):
                reproduce(bundle, output_dir=destination)
            self.assertFalse(destination.exists())

    def test_missing_required_artifact_is_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, _ = self.write_bundle(root)
            (bundle / "candidate.json").unlink()
            destination = root / "must-not-exist"
            with self.assertRaises((ValueError, FileNotFoundError)):
                reproduce(bundle, output_dir=destination)
            self.assertFalse(destination.exists())

    def test_manifest_cannot_omit_a_required_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, _ = self.write_bundle(Path(directory))
            path = bundle / "manifest.json"
            manifest = json.loads(path.read_text())
            del manifest["files"]["candidate.json"]
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                reproduce(bundle)

    def test_self_consistent_file_hashes_do_not_replace_score_recomputation(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, _ = self.write_bundle(Path(directory))
            self.change_report_and_refresh_file_digest(
                bundle, lambda report: report["sessions"][0].update(candidate_rmse=1.0)
            )
            with self.assertRaises(ValueError):
                reproduce(bundle)

    def test_numerical_tolerance_does_not_allow_changed_retained_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, _ = self.write_bundle(Path(directory), numerical_tolerance=1.0)
            self.change_report_and_refresh_file_digest(
                bundle, lambda report: report["samples"][0].update(target_vx=0.25)
            )
            with self.assertRaises(ValueError):
                reproduce(bundle)

    def test_numerical_tolerance_does_not_allow_changed_retained_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, _ = self.write_bundle(Path(directory), numerical_tolerance=1.0)
            self.change_report_and_refresh_file_digest(
                bundle, lambda report: report["samples"][0].update(candidate_vy=0.25)
            )
            with self.assertRaises(ValueError):
                reproduce(bundle)

    def test_numerical_tolerance_does_not_allow_changed_reporting_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, _ = self.write_bundle(Path(directory), tolerance=0.1, numerical_tolerance=1.0)
            self.change_report_and_refresh_file_digest(
                bundle, lambda report: report.update(tolerance=0.2)
            )
            with self.assertRaises(ValueError):
                reproduce(bundle)

    def test_failed_render_leaves_no_partial_destination_or_staging_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "failed"
            with patch("bci_regression.report.render_report", side_effect=RuntimeError("render failure")):
                with self.assertRaises(RuntimeError):
                    compare(*self.inputs(), output_dir=destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(root.glob(".bci-comparison-*")), [])

    def test_failed_file_publication_leaves_no_partial_destination(self):
        for fail_on in (1, 2):
            with self.subTest(fail_on=fail_on), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                destination = root / "failed"
                original_rename = Path.rename
                calls = 0

                def fail_publication(path, target):
                    nonlocal calls
                    if path.parent.name.startswith(".bci-comparison-"):
                        calls += 1
                        if calls == fail_on:
                            raise OSError("simulated publication failure")
                    return original_rename(path, target)

                with patch.object(Path, "rename", fail_publication):
                    with self.assertRaises(OSError):
                        compare(*self.inputs(), output_dir=destination)
                self.assertFalse(destination.exists())
                self.assertEqual(list(root.glob(".bci-comparison-*")), [])


if __name__ == "__main__":
    unittest.main()
