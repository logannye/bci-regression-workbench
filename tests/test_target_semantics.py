"""Explicit proxy-target identity, compatibility, and report acceptance checks."""

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from bci_regression import EvaluationSet, PredictionSet, compare, reproduce
from bci_regression.pinned import PinnedComparison
from bci_regression.report import render_report


INFERRED = "inferred_cursor_to_target_vector"


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _inputs(**options):
    evaluation = EvaluationSet.from_records([
        dict(session_id="one", sample_id="0", timestamp=0, target_vx=10, target_vy=-5),
        dict(session_id="one", sample_id="1", timestamp=1, target_vx=2, target_vy=3),
    ], evaluation_id="semantic-fixture", units="source coordinate units", coordinates="x,y", **options)
    baseline = PredictionSet.from_records([
        dict(session_id="one", sample_id="0", predicted_vx=10, predicted_vy=-5),
        dict(session_id="one", sample_id="1", predicted_vx=2, predicted_vy=3),
    ], run_id="baseline", evaluation=evaluation)
    candidate = PredictionSet.from_records([
        dict(session_id="one", sample_id="0", predicted_vx=13, predicted_vy=-1),
        dict(session_id="one", sample_id="1", predicted_vx=2, predicted_vy=3),
    ], run_id="candidate", evaluation=evaluation)
    return evaluation, baseline, candidate


class TargetSemanticsTests(unittest.TestCase):
    def test_default_velocity_preserves_existing_evidence_and_report(self):
        # Frozen before this extension, against source b5869bb. These identify a
        # deliberately small compatibility fixture, not scientific evidence.
        evaluation, baseline, candidate = _inputs()
        self.assertEqual(evaluation.fingerprint, "237999280804a7fe2796b9f4e8f1a27c937d129a59f1f1ec1f559e1b34565f74")
        self.assertEqual(baseline.digest, "5952a986d0bf898650d76e6d050fa83ffde43005971cbd9de5f9ceaf767a6796")
        self.assertEqual(candidate.digest, "ba41102f277b635f532949a369236f1a6b20f056010c7a1c21633cfe3af9591c")
        result = compare(evaluation, baseline, candidate, tolerance=.2)
        result.pop("comparator_source_digest")
        self.assertEqual(_hash(result), "4506efb0c4520dafeb5397fd9e312f4531ac5e72ecf80abad1de3295dfd7f977")
        self.assertEqual(hashlib.sha256(render_report(result).encode()).hexdigest(),
                         "2cf857889acb4d500605f201980064ddf66b8aa388a06803de3d2bfe9c8a6136")
        for implicit, explicit in zip(_inputs(), _inputs(target_kind="velocity")):
            self.assertEqual(implicit, explicit)

    def test_target_kind_changes_identity_without_changing_scoring_math(self):
        velocity = _inputs()
        inferred = _inputs(target_kind=INFERRED)
        self.assertNotEqual(velocity[0].fingerprint, inferred[0].fingerprint)
        self.assertNotEqual(velocity[1].digest, inferred[1].digest)
        self.assertEqual(inferred[0].records, velocity[0].records)
        ordinary = compare(*velocity, tolerance=.2)
        proxy = compare(*inferred, tolerance=.2)
        for field in ("sessions", "pooled", "samples", "excluded_counts", "complete"):
            self.assertEqual(proxy[field], ordinary[field])
        self.assertEqual(proxy["evaluation"]["target_kind"], INFERRED)
        self.assertEqual(proxy["metric"], "inferred_target_vector_rmse")
        self.assertEqual(proxy["pooled"]["baseline_rmse"], 0)
        self.assertAlmostEqual(proxy["pooled"]["candidate_rmse"], math.sqrt(25 / 2))

    def test_inferred_bundle_round_trip_and_manifest_reproduction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = _inputs(target_kind=INFERRED)
            result = compare(*inputs, tolerance=None, output_dir=root / "run")
            restored = (EvaluationSet.load(root / "run/evaluation.json"),
                        PredictionSet.load(root / "run/baseline.json"),
                        PredictionSet.load(root / "run/candidate.json"))
            self.assertEqual(restored, inputs)
            for name in ("evaluation", "baseline", "candidate"):
                payload = json.loads((root / f"run/{name}.json").read_text())["payload"]
                self.assertEqual(payload["target_kind"], INFERRED)
                self.assertEqual(payload["units"], "source coordinate units")
            manifest = json.loads((root / "run/manifest.json").read_text())
            self.assertEqual(manifest["metric"], "inferred_target_vector_rmse")
            self.assertEqual(reproduce(root / "run", output_dir=root / "repeated"), result)
            self.assertEqual(reproduce(root / "repeated"), result)

    def test_legacy_inputs_load_without_a_target_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind, item, field in (("evaluation", _inputs()[0], "fingerprint"),
                                      ("predictions", _inputs()[1], "digest")):
                payload = item._payload()
                self.assertNotIn("target_kind", payload)
                path = root / f"{kind}.json"
                path.write_text(json.dumps(dict(format_version=1, kind=kind,
                                                payload=payload, **{field: _hash(payload)})))
                loaded = type(item).load(path)
                self.assertEqual(loaded, item)
                self.assertEqual(loaded.target_kind, "velocity")

    def test_semantic_mismatch_invalidates_all_sessions_and_keeps_denominator(self):
        velocity = _inputs()
        inferred = _inputs(target_kind=INFERRED)
        result = compare(inferred[0], inferred[1], velocity[2])
        self.assertFalse(result["complete"])
        self.assertIsNone(result["pooled"])
        self.assertEqual(result["sessions"][0]["n_expected"], 2)
        self.assertEqual(result["sessions"][0]["n_scored"], 0)
        self.assertIn("candidate: target_kind mismatch", result["issues"])
        self.assertIn("candidate: evaluation-set identity mismatch", result["issues"])

    def test_kind_is_bound_to_prediction_content_even_if_evaluation_id_is_forged(self):
        velocity = _inputs()
        inferred = _inputs(target_kind=INFERRED)
        forged = replace(velocity[2], evaluation_fingerprint=inferred[0].fingerprint,
                         target_kind=INFERRED)
        result = compare(inferred[0], inferred[1], forged)
        self.assertFalse(result["complete"])
        self.assertIn("candidate: prediction content digest mismatch", result["issues"])

    def test_unknown_or_noncanonical_serialized_kind_is_rejected(self):
        for bad in (None, "cursor_velocity", "", 0, [], "<script>bad</script>"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _inputs(target_kind=bad)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            for item, field, kind in ((_inputs()[0], "fingerprint", "evaluation"),
                                      (_inputs()[1], "digest", "predictions")):
                for bad in ("unknown", "velocity"):
                    payload = {**item._payload(), "target_kind": bad}
                    path.write_text(json.dumps(dict(format_version=1, kind=kind,
                        payload=payload, **{field: _hash(payload)})))
                    with self.subTest(kind=kind, bad=bad), self.assertRaises(ValueError):
                        type(item).load(path)

    def test_reproduction_rejects_a_misleading_metric_in_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            compare(*_inputs(target_kind=INFERRED), output_dir=root)
            path = root / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["metric"] = "velocity_vector_rmse"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "metric does not match"):
                reproduce(root)

    def test_pin_reuses_inferred_semantics_and_rejects_changed_target_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluation, baseline, candidate = _inputs(target_kind=INFERRED)
            PinnedComparison.create(root / "pin", evaluation=evaluation, baseline=baseline)
            pin = PinnedComparison.load(root / "pin")
            result = pin.compare(candidate.records, evaluation=evaluation,
                                 run_id="candidate", output_dir=root / "run")
            self.assertTrue(result["complete"])
            self.assertEqual(result["evaluation"]["target_kind"], INFERRED)
            self.assertEqual(reproduce(root / "run"), result)
            def forbidden_rows():
                self.fail("Changed target semantics must be refused before consuming predictions")
                yield
            with self.assertRaisesRegex(ValueError, "differs from the pinned evaluation"):
                pin.compare(forbidden_rows(), evaluation=_inputs()[0],
                            run_id="candidate-2", output_dir=root / "must-not-exist")
            self.assertFalse((root / "must-not-exist").exists())

    def test_human_report_labels_proxy_targets_in_header_and_session(self):
        result = compare(*_inputs(target_kind=INFERRED))
        html = render_report(result)
        header = html.split("<header>")[1].split("</header>")[0]
        self.assertIn("Inferred cursor-to-target vectors", header)
        self.assertIn("not measured intended velocities", header)
        self.assertIn("does not establish better live BCI control", header)
        self.assertIn("Error against inferred cursor-to-target vectors", html)
        self.assertIn("Inferred target (x, y)", html)
        self.assertIn("Vectors and errors use source coordinate units", html)
        self.assertIn("Paired Euclidean inferred-target vector error", html)
        self.assertIn("predicted_x − target_x", html)
        self.assertNotIn("Target (vx, vy)", html)
        self.assertNotIn("Velocities and errors", html)
        self.assertNotIn("Euclidean velocity error", html)
        self.assertNotIn("target_vx", html)

    def test_unknown_report_kind_cannot_silently_be_called_velocity(self):
        result = compare(*_inputs(target_kind=INFERRED))
        result["evaluation"]["target_kind"] = "unknown"
        with self.assertRaisesRegex(ValueError, "Unsupported report target_kind"):
            render_report(result)


if __name__ == "__main__":
    unittest.main()
