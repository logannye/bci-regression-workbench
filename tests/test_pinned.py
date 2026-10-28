"""Fixed-reference workflow checks using constructed predictions, not models."""

from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bci_regression import EvaluationSet, PredictionSet, reproduce
from bci_regression.pinned import PinnedComparison


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


class PinnedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.evaluation_rows = [
            dict(session_id="alpha", sample_id="0", timestamp=0, target_vx=1, target_vy=-1),
            dict(session_id="alpha", sample_id="1", timestamp=1, target_vx=2, target_vy=0),
            dict(session_id="beta", sample_id="0", timestamp=0, target_vx=0, target_vy=3),
        ]
        self.rows = [dict(session_id=row["session_id"], sample_id=row["sample_id"],
                          predicted_vx=row["target_vx"], predicted_vy=row["target_vy"])
                     for row in self.evaluation_rows]
        self.evaluation = self.make_evaluation()
        self.baseline = PredictionSet.from_records(self.rows, run_id="fixed-reference",
            evaluation=self.evaluation, provenance={"producer": "existing-evaluator", "revision": "old"})

    def make_evaluation(self, rows=None, **overrides):
        options = dict(evaluation_id="fixed-sessions", units="cm/s", coordinates="x-right,y-up",
                       source_ref="explicit-evaluation-export")
        options.update(overrides)
        return EvaluationSet.from_records(self.evaluation_rows if rows is None else rows, **options)

    def pin(self, **options):
        return PinnedComparison.create(self.root / "pin", evaluation=self.evaluation,
                                       baseline=self.baseline, **options)

    def compare(self, pin, rows=None, **options):
        args = dict(evaluation=self.evaluation, run_id="new-candidate", output_dir=self.root / "candidate")
        args.update(options)
        return pin.compare(self.rows if rows is None else rows, **args)

    def snapshot(self, path):
        return {file.name: file.read_bytes() for file in path.iterdir()}

    def change_manifest(self, pin, change, refresh_fingerprint=False):
        path = pin.path / "manifest.json"
        manifest = json.loads(path.read_text())
        change(manifest)
        if refresh_fingerprint:
            manifest["fingerprint"] = digest({k: v for k, v in manifest.items() if k != "fingerprint"})
        path.write_text(json.dumps(manifest, allow_nan=False))

    def assert_rejected_before_rows(self, pin, evaluation, pattern="new pin is required"):
        def never_read():
            self.fail("Candidate rows must not be consumed before evaluation validation")
            yield {}

        output = self.root / "must-not-exist"
        with self.assertRaisesRegex(ValueError, pattern):
            self.compare(pin, never_read(), evaluation=evaluation, output_dir=output)
        self.assertFalse(output.exists())

    def test_recurring_runs_keep_pin_bytes_and_fixed_configuration(self):
        pin = self.pin(tolerance=0.2, numerical_tolerance=1e-10, description="Fixed reference comparison")
        before = self.snapshot(pin.path)
        provenance = {"revision": "new", "protocol": {"split": "held-out"}}
        first = self.compare(pin, provenance=provenance)
        changed = [dict(row) for row in self.rows]
        changed[2]["predicted_vx"] = 4
        second = self.compare(PinnedComparison.load(pin.path), changed, run_id="next-candidate",
                              output_dir=self.root / "next")
        self.assertEqual(self.snapshot(pin.path), before)
        self.assertEqual(provenance, {"revision": "new", "protocol": {"split": "held-out"}})
        for report in (first, second):
            self.assertTrue(report["complete"])
            self.assertEqual(report["baseline"]["digest"], self.baseline.digest)
            self.assertEqual(report["tolerance"], 0.2)
            self.assertEqual(report["numerical_tolerance"], 1e-10)
            self.assertEqual(report["description"], "Fixed reference comparison")
            identity = report["candidate"]["provenance"]["bci_regression_pin"]
            self.assertEqual(identity["fingerprint"], pin.fingerprint)
            self.assertEqual(identity["wrapper_source_digest"],
                             json.loads(before["manifest.json"])["wrapper_source_digest"])
        self.assertEqual(first["candidate"]["provenance"]["protocol"], {"split": "held-out"})
        self.assertTrue(next(row for row in second["sessions"] if row["session_id"] == "beta")["regression"])
        self.assertEqual(first, reproduce(self.root / "candidate"))
        self.assertEqual(second, reproduce(self.root / "next"))

    def test_identity_is_independent_of_pin_location(self):
        first = self.pin(tolerance=0)
        second = PinnedComparison.create(self.root / "elsewhere", evaluation=self.evaluation,
                                         baseline=self.baseline, tolerance=0)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(self.snapshot(first.path), self.snapshot(second.path))
        with self.assertRaises(FrozenInstanceError):
            first.fingerprint = "changed"

    def test_current_targets_masks_samples_and_semantics_require_new_pin(self):
        pin = self.pin()
        changes = [
            ("target_vx", 1.001), ("timestamp", 0.01), ("sample_id", "different"),
            ("session_id", "different"), ("eligible", False),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                rows = [dict(row) for row in self.evaluation_rows]
                rows[0][field] = value
                if field == "eligible":
                    rows[0]["exclusion_reason"] = "current evaluator exclusion"
                self.assert_rejected_before_rows(pin, self.make_evaluation(rows))
        for key, value in dict(evaluation_id="new-id", units="m/s", coordinates="x-up,y-right",
                               horizon_ms=1, purpose="assessment", source_ref="different-source").items():
            with self.subTest(semantic=key):
                self.assert_rejected_before_rows(pin, self.make_evaluation(**{key: value}))

    def test_mutated_evaluation_payload_cannot_reuse_cached_fingerprint(self):
        pin = self.pin()
        self.evaluation.records[0]["target_vx"] += 1
        self.assert_rejected_before_rows(pin, self.evaluation, "payload fingerprint mismatch")
        self.evaluation.records[0]["target_vx"] = float("nan")
        self.assert_rejected_before_rows(pin, self.evaluation, "payload is invalid")

    def test_current_evaluation_is_required_and_cannot_be_loaded_from_pin_implicitly(self):
        pin = self.pin()
        with self.assertRaises(TypeError):
            pin.compare(self.rows, run_id="candidate", output_dir=self.root / "candidate")
        self.assert_rejected_before_rows(pin, None)

    def test_stale_and_incomplete_baselines_cannot_be_pinned(self):
        changed_rows = [dict(row) for row in self.evaluation_rows]
        changed_rows[0]["target_vx"] += 1
        changed_evaluation = self.make_evaluation(changed_rows)
        with self.assertRaisesRegex(ValueError, "evaluation-set identity mismatch"):
            PinnedComparison.create(self.root / "pin", evaluation=changed_evaluation, baseline=self.baseline)
        self.assertFalse((self.root / "pin").exists())
        for records in (self.rows[:1], self.rows + [self.rows[0]],
                        [{**self.rows[0], "predicted_vx": float("nan")}] + self.rows[1:]):
            with self.subTest(records=records):
                baseline = PredictionSet.from_records(records, run_id="bad", evaluation=self.evaluation)
                with self.assertRaisesRegex(ValueError, "incomplete or invalid baseline"):
                    PinnedComparison.create(self.root / "pin", evaluation=self.evaluation, baseline=baseline)
                self.assertFalse((self.root / "pin").exists())

    def test_mutated_baseline_payload_cannot_be_pinned(self):
        self.baseline.records[0]["predicted_vx"] += 1
        with self.assertRaisesRegex(ValueError, "prediction content digest mismatch"):
            self.pin()
        self.assertFalse((self.root / "pin").exists())

    def test_arbitrary_column_mapping_is_fixed_and_applied_once(self):
        columns = {"session_id": "recording name", "sample_id": "row key",
                   "predicted_vx": "decoded x", "predicted_vy": "decoded y"}
        pin = self.pin(prediction_columns=columns)
        columns["session_id"] = "caller mutation"
        mapped_rows = [{"recording name": row["session_id"], "row key": row["sample_id"],
                        "decoded x": row["predicted_vx"], "decoded y": row["predicted_vy"],
                        "irrelevant": 123} for row in self.rows]
        report = self.compare(pin, mapped_rows)
        self.assertTrue(report["complete"])
        self.assertEqual(report["pooled"]["delta"], 0)
        with self.assertRaises(TypeError):
            pin.compare(mapped_rows, evaluation=self.evaluation, run_id="candidate",
                        output_dir=self.root / "other", tolerance=10)

    def test_invalid_mapping_is_rejected_at_creation_before_candidate_exists(self):
        for mapping in ({"target_vx": "x"}, {"sample_id": ""}, {"sample_id": " "},
                        {"session_id": "id", "sample_id": "id"},
                        {"session_id": "sample_id"}, ["sample_id"]):
            with self.subTest(mapping=mapping), self.assertRaises((ValueError, TypeError)):
                self.pin(prediction_columns=mapping)
            self.assertFalse((self.root / "pin").exists())

    def test_mapping_missing_source_or_collision_is_a_structural_error(self):
        pin = self.pin(prediction_columns={"session_id": "recording"})
        for row in (self.rows[0], {**self.rows[0], "recording": "alpha"}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.compare(pin, [row])
            self.assertFalse((self.root / "candidate").exists())

    def test_malformed_candidate_outputs_remain_in_incomplete_reproducible_bundle(self):
        pin = self.pin()
        cases = [[], self.rows[:1], self.rows + [self.rows[0]],
                 [{**self.rows[0], "predicted_vx": float("nan")}] + self.rows[1:],
                 [{**self.rows[0], "sample_id": None}] + self.rows[1:],
                 self.rows + [{**self.rows[0], "session_id": "unknown"}]]
        for index, rows in enumerate(cases):
            with self.subTest(case=index):
                destination = self.root / f"malformed-{index}"
                report = self.compare(pin, rows, output_dir=destination)
                self.assertFalse(report["complete"])
                self.assertIsNone(report["pooled"])
                self.assertEqual({row["session_id"] for row in report["sessions"]}, {"alpha", "beta"})
                self.assertEqual(len(PredictionSet.load(destination / "candidate.json").records), len(rows))
                self.assertEqual(report, reproduce(destination))

    def test_reserved_provenance_cannot_be_supplied_by_caller(self):
        pin = self.pin()
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.compare(pin, provenance={"bci_regression_pin": {"fingerprint": "fake"}})
        self.assertFalse((self.root / "candidate").exists())
        for value in ([], "", 0):
            with self.subTest(provenance=value), self.assertRaisesRegex(ValueError, "mapping"):
                self.compare(pin, provenance=value)

    def test_corrupt_artifact_and_changed_source_are_rejected(self):
        pin = self.pin()
        original = (pin.path / "baseline.json").read_bytes()
        (pin.path / "baseline.json").write_bytes(original + b" ")
        self.assert_rejected_before_rows(pin, self.evaluation, "artifact content digest mismatch")
        (pin.path / "baseline.json").write_bytes(original)
        for name in ("wrapper_source_digest", "comparator_source_digest"):
            before = (pin.path / "manifest.json").read_bytes()
            self.change_manifest(pin, lambda manifest: manifest.update({name: "0" * 64}), True)
            with self.subTest(source=name), self.assertRaisesRegex(ValueError, "source differs"):
                PinnedComparison.load(pin.path)
            (pin.path / "manifest.json").write_bytes(before)

    def test_configuration_tampering_cannot_slip_into_loaded_pin(self):
        pin = self.pin(tolerance=0.1)
        self.change_manifest(pin, lambda manifest: manifest["configuration"].update(tolerance=10.0))
        self.assert_rejected_before_rows(pin, self.evaluation, "fingerprint mismatch")
        self.change_manifest(pin, lambda manifest: None, True)
        self.assert_rejected_before_rows(pin, self.evaluation, "Loaded pin identity changed")

    def test_strict_manifest_and_configuration_reject_self_consistent_malformed_pins(self):
        pin = self.pin()
        original = (pin.path / "manifest.json").read_bytes()
        mutations = [
            lambda m: m.update(unrecognized="field"),
            lambda m: m.update(format_version=True),
            lambda m: m["configuration"].update(tolerance=-1.0),
            lambda m: m["configuration"].update(numerical_tolerance=True),
            lambda m: m["configuration"].update(prediction_columns={"target_vx": "x"}),
            lambda m: m["configuration"].update(extra="field"),
            lambda m: m["files"].update(extra="0" * 64),
            lambda m: m["evaluation"].update(fingerprint="0" * 64),
        ]
        for index, mutation in enumerate(mutations):
            (pin.path / "manifest.json").write_bytes(original)
            self.change_manifest(pin, mutation, True)
            with self.subTest(case=index), self.assertRaises(ValueError):
                PinnedComparison.load(pin.path)
        (pin.path / "manifest.json").write_bytes(original[:-2] + b', "format_version": 1}\n')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON field"):
            PinnedComparison.load(pin.path)

    def test_reference_artifact_schema_is_strict_even_with_refreshed_hashes(self):
        pin = self.pin()
        path = pin.path / "baseline.json"
        doc = json.loads(path.read_text())
        doc["extra"] = "field"
        path.write_text(json.dumps(doc))
        self.change_manifest(pin, lambda m: m["files"].update(
            {"baseline.json": hashlib.sha256(path.read_bytes()).hexdigest()}), True)
        with self.assertRaisesRegex(ValueError, "unexpected or missing fields"):
            PinnedComparison.load(pin.path)

    def test_missing_or_extra_files_are_rejected(self):
        pin = self.pin()
        extra = pin.path / "unrelated.txt"
        extra.write_text("do not ingest")
        with self.assertRaisesRegex(ValueError, "exactly"):
            PinnedComparison.load(pin.path)
        extra.unlink()
        (pin.path / "baseline.json").unlink()
        with self.assertRaisesRegex(ValueError, "exactly"):
            PinnedComparison.load(pin.path)

    def test_existing_pin_and_comparison_destinations_are_not_overwritten(self):
        pin = self.pin()
        before = self.snapshot(pin.path)
        with self.assertRaises(FileExistsError):
            self.pin(tolerance=100)
        self.assertEqual(self.snapshot(pin.path), before)
        destination = self.root / "candidate"
        destination.mkdir()
        (destination / "keep").write_text("existing output")
        with self.assertRaises(FileExistsError):
            self.compare(pin)
        self.assertEqual(self.snapshot(destination), {"keep": b"existing output"})
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(FileExistsError):
            PinnedComparison.create(empty, evaluation=self.evaluation, baseline=self.baseline)

    def test_output_inside_pin_is_rejected_before_rows_even_through_symlink(self):
        pin = self.pin()
        before = self.snapshot(pin.path)
        alias = self.root / "pin-alias"
        alias.symlink_to(pin.path, target_is_directory=True)

        def never_read():
            self.fail("Candidate rows must not be consumed for an output inside the pin")
            yield {}

        for destination in (pin.path, pin.path / "runs" / "candidate",
                            alias, alias / "runs" / "candidate"):
            with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, "outside the pin"):
                self.compare(pin, never_read(), output_dir=destination)
            self.assertEqual(self.snapshot(pin.path), before)
            self.assertEqual(pin, PinnedComparison.load(pin.path))

    def test_manifest_is_published_last_and_failed_publication_rolls_back_own_files(self):
        original_link = os.link
        calls = []

        def observe(source, target):
            calls.append(Path(target).name)
            if Path(target).name == "manifest.json":
                self.assertEqual({p.name for p in Path(target).parent.iterdir()},
                                 {"baseline.json", "evaluation.json"})
            return original_link(source, target)

        with patch("bci_regression.pinned.os.link", side_effect=observe):
            pin = self.pin()
        self.assertEqual(calls, ["baseline.json", "evaluation.json", "manifest.json"])
        self.assertEqual(pin, PinnedComparison.load(pin.path))
        for keep_unrelated in (False, True):
            destination = self.root / f"failed-{keep_unrelated}"

            def fail(source, target):
                if Path(target).name == "evaluation.json":
                    if keep_unrelated:
                        (destination / "unrelated").write_text("preserve")
                    raise OSError("simulated publication failure")
                return original_link(source, target)

            with patch("bci_regression.pinned.os.link", side_effect=fail):
                with self.assertRaisesRegex(OSError, "simulated"):
                    PinnedComparison.create(destination, evaluation=self.evaluation, baseline=self.baseline)
            if keep_unrelated:
                self.assertEqual(self.snapshot(destination), {"unrelated": b"preserve"})
            else:
                self.assertFalse(destination.exists())
            self.assertEqual(list(self.root.glob(".bci-pin-*")), [])


if __name__ == "__main__":
    unittest.main()
