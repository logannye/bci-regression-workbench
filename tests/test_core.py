"""Independent acceptance checks for paired session-level velocity scoring.

The small, constructed data below test evaluator behavior. They are not
evidence about biological performance or a trained decoder.
"""

from dataclasses import FrozenInstanceError, replace
import math
from pathlib import Path
import tempfile
import unittest

from bci_regression import EvaluationSet, PredictionSet, compare


def evaluation_row(session, sample, vx=0.0, vy=0.0, timestamp=0.0, **extra):
    return {
        "session_id": session,
        "sample_id": sample,
        "timestamp": timestamp,
        "target_vx": vx,
        "target_vy": vy,
        **extra,
    }


def prediction_row(session, sample, vx=0.0, vy=0.0):
    return {
        "session_id": session,
        "sample_id": sample,
        "predicted_vx": vx,
        "predicted_vy": vy,
    }


class CoreAcceptanceTests(unittest.TestCase):
    def evaluation(self, records=None, **overrides):
        if records is None:
            records = [
                evaluation_row("alpha", "a0", timestamp=0.0),
                evaluation_row("alpha", "a1", timestamp=1.0),
                evaluation_row("beta", "b0", timestamp=0.0),
            ]
        config = {
            "evaluation_id": "acceptance-evaluation",
            "units": "cm/s",
            "coordinates": "x-right,y-up",
            "horizon_ms": 0.0,
        }
        config.update(overrides)
        return EvaluationSet.from_records(records, **config)

    def predictions(self, evaluation, records=None, run_id="baseline"):
        if records is None:
            records = [
                prediction_row("alpha", "a0"),
                prediction_row("alpha", "a1"),
                prediction_row("beta", "b0"),
            ]
        return PredictionSet.from_records(
            records, run_id=run_id, evaluation=evaluation
        )

    def rows(self, report):
        rows = {row["session_id"]: row for row in report["sessions"]}
        self.assertEqual(len(rows), len(report["sessions"]))
        return rows

    def assert_session_invalid(self, report, session="alpha"):
        self.assertFalse(report["complete"])
        self.assertIsNone(report["pooled"])
        row = self.rows(report)[session]
        self.assertEqual(row["status"], "invalid")
        self.assertEqual(row["n_scored"], 0)
        self.assertIsNone(row["delta"])
        self.assertIsNone(row["regression"])
        self.assertTrue(row["issues"])
        return row

    def test_vector_rmse_matches_hand_calculation_without_coordinate_division(self):
        evaluation = self.evaluation([
            evaluation_row("one", "0"),
            evaluation_row("one", "1", timestamp=1.0),
        ])
        baseline = self.predictions(evaluation, [
            prediction_row("one", "0"), prediction_row("one", "1")
        ])
        candidate = self.predictions(evaluation, [
            prediction_row("one", "0", 3.0, 4.0),
            prediction_row("one", "1"),
        ], run_id="candidate")
        report = compare(evaluation, baseline, candidate)
        row = self.rows(report)["one"]
        self.assertTrue(report["complete"])
        self.assertEqual(row["n_expected"], 2)
        self.assertEqual(row["n_scored"], 2)
        self.assertEqual(row["baseline_rmse"], 0.0)
        self.assertAlmostEqual(row["candidate_rmse"], math.sqrt(25.0 / 2.0))
        self.assertAlmostEqual(row["delta"], math.sqrt(25.0 / 2.0))

    def test_nonzero_labels_are_used_in_error_calculation(self):
        evaluation = self.evaluation([evaluation_row("one", "0", 10.0, -5.0)])
        baseline = self.predictions(evaluation, [prediction_row("one", "0", 10, -5)])
        candidate = self.predictions(evaluation, [prediction_row("one", "0", 13, -1)])
        row = self.rows(compare(evaluation, baseline, candidate))["one"]
        self.assertEqual(row["baseline_rmse"], 0.0)
        self.assertEqual(row["candidate_rmse"], 5.0)

    def test_identical_predictions_have_zero_delta_for_every_session(self):
        evaluation = self.evaluation()
        predictions = self.predictions(evaluation, [
            prediction_row("alpha", "a0", 3, 4),
            prediction_row("alpha", "a1", -1, 2),
            prediction_row("beta", "b0", 7, -2),
        ])
        report = compare(evaluation, predictions, predictions, tolerance=0.0)
        self.assertTrue(report["complete"])
        self.assertEqual(set(self.rows(report)), {"alpha", "beta"})
        for row in report["sessions"]:
            self.assertEqual(row["status"], "valid")
            self.assertEqual(row["delta"], 0.0)
            self.assertFalse(row["regression"])

    def test_pooled_improvement_does_not_hide_a_session_regression(self):
        records = [evaluation_row("long", str(i), timestamp=float(i)) for i in range(4)]
        records.append(evaluation_row("short", "0"))
        evaluation = self.evaluation(records)
        baseline_rows = [prediction_row("long", str(i), 2, 0) for i in range(4)]
        baseline_rows.append(prediction_row("short", "0"))
        candidate_rows = [prediction_row("long", str(i)) for i in range(4)]
        candidate_rows.append(prediction_row("short", "0", 3, 0))
        report = compare(
            evaluation,
            self.predictions(evaluation, baseline_rows),
            self.predictions(evaluation, candidate_rows, run_id="candidate"),
            tolerance=0.0,
        )
        rows = self.rows(report)
        self.assertTrue(report["complete"])
        self.assertEqual(rows["long"]["delta"], -2.0)
        self.assertEqual(rows["short"]["delta"], 3.0)
        self.assertTrue(rows["short"]["regression"])
        self.assertFalse(rows["long"]["regression"])
        self.assertAlmostEqual(report["pooled"]["baseline_rmse"], math.sqrt(16 / 5))
        self.assertAlmostEqual(report["pooled"]["candidate_rmse"], math.sqrt(9 / 5))
        self.assertLess(report["pooled"]["candidate_rmse"], report["pooled"]["baseline_rmse"])

    def test_prediction_row_order_does_not_change_alignment_or_scores(self):
        evaluation = self.evaluation()
        records = [
            prediction_row("alpha", "a0", 3, 4),
            prediction_row("alpha", "a1", 1, 0),
            prediction_row("beta", "b0", 0, 2),
        ]
        baseline = self.predictions(evaluation)
        ordered = compare(evaluation, baseline, self.predictions(evaluation, records))
        reversed_rows = compare(
            evaluation, baseline, self.predictions(evaluation, list(reversed(records)))
        )
        self.assertTrue(reversed_rows["complete"])
        self.assertEqual(self.rows(ordered), self.rows(reversed_rows))
        self.assertEqual(ordered["pooled"], reversed_rows["pooled"])

    def test_sample_id_is_scoped_by_session(self):
        evaluation = self.evaluation([
            evaluation_row("alpha", "0", 1, 0),
            evaluation_row("beta", "0", 2, 0),
        ])
        predictions = self.predictions(evaluation, [
            prediction_row("beta", "0", 2, 0),
            prediction_row("alpha", "0", 1, 0),
        ])
        report = compare(evaluation, predictions, predictions)
        self.assertTrue(report["complete"])
        for row in report["sessions"]:
            self.assertEqual(row["baseline_rmse"], 0.0)

    def test_evaluation_row_order_does_not_change_scores(self):
        records = [
            evaluation_row("one", "0", 2, 0),
            evaluation_row("one", "1", 0, 3, timestamp=1.0),
        ]
        prediction_records = [
            prediction_row("one", "0", 1, 0),
            prediction_row("one", "1", 0, 1),
        ]
        reports = []
        for selected in (records, list(reversed(records))):
            evaluation = self.evaluation(selected)
            predictions = self.predictions(evaluation, prediction_records)
            reports.append(compare(evaluation, predictions, predictions))
        self.assertEqual(self.rows(reports[0]), self.rows(reports[1]))
        self.assertEqual(reports[0]["pooled"], reports[1]["pooled"])

    def test_missing_prediction_keeps_expected_denominator_and_session_visible(self):
        evaluation = self.evaluation()
        baseline = self.predictions(evaluation)
        candidate = self.predictions(evaluation, [
            prediction_row("alpha", "a0"), prediction_row("beta", "b0")
        ])
        report = compare(evaluation, baseline, candidate)
        row = self.assert_session_invalid(report)
        self.assertEqual(row["n_expected"], 2)
        self.assertIsNone(row["candidate_rmse"])
        self.assertEqual(self.rows(report)["beta"]["status"], "valid")

    def test_duplicate_prediction_invalidates_affected_session(self):
        evaluation = self.evaluation()
        records = [
            prediction_row("alpha", "a0"), prediction_row("alpha", "a1"),
            prediction_row("alpha", "a1"), prediction_row("beta", "b0"),
        ]
        report = compare(evaluation, self.predictions(evaluation), self.predictions(evaluation, records))
        self.assert_session_invalid(report)
        self.assertEqual(self.rows(report)["beta"]["status"], "valid")

    def test_nonfinite_required_prediction_never_becomes_a_scored_subset(self):
        evaluation = self.evaluation()
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                records = [
                    prediction_row("alpha", "a0"),
                    prediction_row("alpha", "a1", value, 0),
                    prediction_row("beta", "b0"),
                ]
                report = compare(evaluation, self.predictions(evaluation), self.predictions(evaluation, records))
                row = self.assert_session_invalid(report)
                self.assertEqual(row["n_expected"], 2)
                self.assertIsNone(row["candidate_rmse"])

    def test_missing_prediction_component_invalidates_affected_session(self):
        evaluation = self.evaluation()
        malformed = prediction_row("alpha", "a1")
        del malformed["predicted_vy"]
        records = [prediction_row("alpha", "a0"), malformed, prediction_row("beta", "b0")]
        report = compare(evaluation, self.predictions(evaluation), self.predictions(evaluation, records))
        self.assert_session_invalid(report)

    def test_nonnumeric_prediction_component_invalidates_affected_session(self):
        evaluation = self.evaluation()
        records = [
            prediction_row("alpha", "a0"),
            prediction_row("alpha", "a1", "bad", 0),
            prediction_row("beta", "b0"),
        ]
        report = compare(evaluation, self.predictions(evaluation), self.predictions(evaluation, records))
        self.assert_session_invalid(report)

    def test_bad_baseline_predictions_are_not_treated_more_leniently(self):
        evaluation = self.evaluation()
        bad_baseline = self.predictions(evaluation, [prediction_row("beta", "b0")])
        report = compare(evaluation, bad_baseline, self.predictions(evaluation))
        row = self.assert_session_invalid(report)
        self.assertIsNone(row["baseline_rmse"])

    def test_unknown_extra_prediction_keys_make_comparison_incomplete(self):
        evaluation = self.evaluation()
        for extra in (prediction_row("unknown", "0"), prediction_row("alpha", "unknown")):
            with self.subTest(extra=extra):
                records = [
                    prediction_row("alpha", "a0"), prediction_row("alpha", "a1"),
                    prediction_row("beta", "b0"), extra,
                ]
                report = compare(evaluation, self.predictions(evaluation), self.predictions(evaluation, records))
                self.assertFalse(report["complete"])
                self.assertIsNone(report["pooled"])
                self.assertTrue(report["issues"])
                self.assertEqual(set(self.rows(report)), {"alpha", "beta"})

    def test_explicitly_ineligible_sample_is_not_required_or_scored(self):
        evaluation = self.evaluation([
            evaluation_row("one", "keep"),
            evaluation_row("one", "excluded", eligible=False, exclusion_reason="predeclared quality exclusion"),
        ])
        baseline = self.predictions(evaluation, [prediction_row("one", "keep")])
        candidate = self.predictions(evaluation, [
            prediction_row("one", "keep", 3, 4),
            prediction_row("one", "excluded", 10000, 10000),
        ])
        report = compare(evaluation, baseline, candidate)
        row = self.rows(report)["one"]
        self.assertTrue(report["complete"])
        self.assertEqual(row["n_expected"], 1)
        self.assertEqual(row["n_scored"], 1)
        self.assertEqual(row["candidate_rmse"], 5.0)
        self.assertEqual(report["excluded_counts"], {
            "evaluation": 1, "baseline": 0, "candidate": 1
        })

    def test_session_with_empty_scoring_mask_remains_visible_and_invalid(self):
        evaluation = self.evaluation([
            evaluation_row("empty", "0", eligible=False, exclusion_reason="predeclared exclusion"),
            evaluation_row("valid", "0"),
        ])
        predictions = self.predictions(evaluation, [prediction_row("valid", "0")])
        report = compare(evaluation, predictions, predictions)
        row = self.assert_session_invalid(report, "empty")
        self.assertEqual(row["n_expected"], 0)
        self.assertEqual(self.rows(report)["valid"]["status"], "valid")

    def test_identity_and_semantic_mismatch_invalidates_all_sessions(self):
        evaluation = self.evaluation()
        baseline = self.predictions(evaluation)
        replacements = {
            "evaluation_fingerprint": "a-different-evaluation",
            "units": "m/s",
            "coordinates": "x-right,y-down",
            "horizon_ms": 25.0,
        }
        for field, value in replacements.items():
            with self.subTest(field=field):
                candidate = replace(baseline, **{field: value})
                report = compare(evaluation, baseline, candidate)
                for session in ("alpha", "beta"):
                    self.assert_session_invalid(report, session)

    def test_predictions_bound_to_different_label_set_are_rejected(self):
        evaluation = self.evaluation()
        changed = self.evaluation([
            evaluation_row("alpha", "a0", 1, 0),
            evaluation_row("alpha", "a1", timestamp=1.0),
            evaluation_row("beta", "b0"),
        ])
        self.assertNotEqual(evaluation.fingerprint, changed.fingerprint)
        report = compare(evaluation, self.predictions(evaluation), self.predictions(changed))
        for session in ("alpha", "beta"):
            self.assert_session_invalid(report, session)

    def test_reporting_tolerance_is_strictly_greater_than(self):
        evaluation = self.evaluation([evaluation_row("one", "0")])
        baseline = self.predictions(evaluation, [prediction_row("one", "0")])
        candidate = self.predictions(evaluation, [prediction_row("one", "0", 1, 0)])
        equal = self.rows(compare(evaluation, baseline, candidate, tolerance=1.0))["one"]
        above = self.rows(compare(evaluation, baseline, candidate, tolerance=0.999))["one"]
        self.assertEqual(equal["delta"], 1.0)
        self.assertFalse(equal["regression"])
        self.assertTrue(above["regression"])

    def test_none_tolerance_reports_delta_without_categorical_flag(self):
        evaluation = self.evaluation([evaluation_row("one", "0")])
        baseline = self.predictions(evaluation, [prediction_row("one", "0")])
        candidate = self.predictions(evaluation, [prediction_row("one", "0", 1, 0)])
        row = self.rows(compare(evaluation, baseline, candidate, tolerance=None))["one"]
        self.assertEqual(row["delta"], 1.0)
        self.assertIsNone(row["regression"])

    def test_invalid_reporting_tolerances_raise(self):
        evaluation = self.evaluation()
        predictions = self.predictions(evaluation)
        for value in (-1.0, float("nan"), float("inf")):
            with self.subTest(tolerance=value):
                with self.assertRaises(ValueError):
                    compare(evaluation, predictions, predictions, tolerance=value)

    def test_empty_evaluation_is_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluation([])

    def test_duplicate_evaluation_key_is_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluation([evaluation_row("one", "0"), evaluation_row("one", "0")])

    def test_nonfinite_evaluation_labels_and_timestamps_are_rejected(self):
        for field in ("target_vx", "target_vy", "timestamp"):
            for value in (float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value):
                    row = evaluation_row("one", "0")
                    row[field] = value
                    with self.assertRaises(ValueError):
                        self.evaluation([row])

    def test_nonstring_evaluation_identity_is_rejected(self):
        for field in ("session_id", "sample_id"):
            with self.subTest(field=field):
                row = evaluation_row("one", "0")
                row[field] = 1
                with self.assertRaises(ValueError):
                    self.evaluation([row])

    def test_exclusion_requires_a_reason(self):
        with self.assertRaises(ValueError):
            self.evaluation([evaluation_row("one", "0", eligible=False)])

    def test_eligibility_must_be_boolean(self):
        with self.assertRaises(ValueError):
            self.evaluation([evaluation_row("one", "0", eligible="false")])

    def test_empty_semantic_metadata_is_rejected(self):
        for field in ("evaluation_id", "units", "coordinates"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.evaluation(**{field: ""})

    def test_artifacts_are_frozen_dataclasses(self):
        evaluation = self.evaluation()
        predictions = self.predictions(evaluation)
        with self.assertRaises(FrozenInstanceError):
            evaluation.units = "m/s"
        with self.assertRaises(FrozenInstanceError):
            predictions.run_id = "changed"

    def test_saved_artifacts_reload_and_reproduce_scores(self):
        evaluation = self.evaluation()
        baseline = self.predictions(evaluation)
        candidate = self.predictions(evaluation, [
            prediction_row("alpha", "a0", 3, 4),
            prediction_row("alpha", "a1"), prediction_row("beta", "b0", 1, 0),
        ], run_id="candidate")
        original = compare(evaluation, baseline, candidate, tolerance=0.0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluation.save(root / "evaluation.json")
            baseline.save(root / "baseline.json")
            candidate.save(root / "candidate.json")
            loaded_evaluation = EvaluationSet.load(root / "evaluation.json")
            loaded_baseline = PredictionSet.load(root / "baseline.json")
            loaded_candidate = PredictionSet.load(root / "candidate.json")
            self.assertEqual(loaded_evaluation.fingerprint, evaluation.fingerprint)
            self.assertEqual(loaded_baseline.digest, baseline.digest)
            self.assertEqual(loaded_candidate.digest, candidate.digest)
            reproduced = compare(loaded_evaluation, loaded_baseline, loaded_candidate, tolerance=0.0)
        self.assertEqual(self.rows(reproduced), self.rows(original))
        self.assertEqual(reproduced["pooled"], original["pooled"])

    def test_tampered_saved_evaluation_is_rejected(self):
        evaluation = self.evaluation()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            evaluation.save(path)
            content = path.read_text()
            self.assertIn("acceptance-evaluation", content)
            path.write_text(content.replace("acceptance-evaluation", "tampered-evaluation"))
            with self.assertRaises(ValueError):
                EvaluationSet.load(path)

    def test_tampered_saved_predictions_are_rejected(self):
        evaluation = self.evaluation()
        predictions = self.predictions(evaluation, run_id="unique-baseline-id")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.json"
            predictions.save(path)
            content = path.read_text()
            self.assertIn("unique-baseline-id", content)
            path.write_text(content.replace("unique-baseline-id", "tampered-baseline-id"))
            with self.assertRaises(ValueError):
                PredictionSet.load(path)

    def test_existing_output_directory_is_not_overwritten(self):
        evaluation = self.evaluation()
        predictions = self.predictions(evaluation)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing-result"
            output.mkdir()
            marker = output / "preserved.txt"
            marker.write_text("existing evidence")
            with self.assertRaises((ValueError, FileExistsError)):
                compare(evaluation, predictions, predictions, output_dir=output)
            self.assertEqual(marker.read_text(), "existing evidence")


if __name__ == "__main__":
    unittest.main()
