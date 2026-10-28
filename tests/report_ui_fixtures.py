"""Generate real comparison bundles for report UI validation; no models run.

From the repository root:
    PYTHONPATH=src python3 tests/report_ui_fixtures.py --output-dir /tmp/report-ui-new
    PYTHONPATH=src python3 tests/report_ui_fixtures.py --output-dir /tmp/report-ui-public \
        --public-bundle /path/to/original/saved-comparison

The output directory must not exist. Each state contains the normal seven-file
comparison bundle, verified with reproduce(). index.json and stdout summarize
the actual scores. Public replay loads the saved inputs without rebinding them,
checks the complete result except comparator_source_digest, and verifies that
the original bundle bytes remain unchanged. Serve only newly generated reports
over HTTP for browser validation; this script does not open a browser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from bci_regression import EvaluationSet, PredictionSet, compare, reproduce
from bci_regression.report import _localization_window


_LAYOUT = [("session-01", 200), ("session-02", 100), ("session-03", 40), ("session-04", 80)]
_ARTIFACTS = {"evaluation.json", "baseline.json", "candidate.json", "comparison.json",
              "session_metrics.csv", "report.html"}
_DESCRIPTION = "Synthetic UI validation fixture. No neural recordings or decoder performance claim."


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _candidate_error(session, index):
    if session == "session-03" and 18 <= index < 28:
        return 2.8
    return {"session-01": 0.3, "session-02": 0.7, "session-03": 0.4, "session-04": 1.0}[session]


def _inputs(name, layout=_LAYOUT, *, baseline_error=lambda _s, _i: 1.0,
            candidate_error=_candidate_error, suffix=""):
    targets, baseline, candidate = [], [], []
    for session, count in layout:
        for index in range(count):
            sid, sample = session + suffix, f"sample-{index:04d}" + suffix
            vx, vy = math.sin(index / 11), math.cos(index / 17)
            targets.append(dict(session_id=sid, sample_id=sample, timestamp=index * 0.02,
                                target_vx=vx, target_vy=vy))
            for rows, error in ((baseline, baseline_error), (candidate, candidate_error)):
                rows.append(dict(session_id=sid, sample_id=sample,
                                 predicted_vx=vx + error(session, index), predicted_vy=vy))
    evaluation = EvaluationSet.from_records(targets, evaluation_id=f"ui-{name}" + suffix,
        units="cm/s", coordinates="synthetic-x-y", purpose="synthetic UI validation",
        source_ref="tests/report_ui_fixtures.py" + suffix)
    metadata = {"producer": "report_ui_fixtures", "kind": "constructed outputs", "note" + suffix: suffix}
    return (evaluation,
            PredictionSet.from_records(baseline, run_id="baseline-fixed" + suffix,
                                       evaluation=evaluation, provenance=metadata),
            PredictionSet.from_records(candidate, run_id="candidate-current" + suffix,
                                       evaluation=evaluation, provenance=metadata))


def _summary(name, result):
    sessions = result["sessions"]
    return dict(name=name, report=f"{name}/report.html", scoring_reproduced=True,
        comparator_source_digest=result["comparator_source_digest"],
        evaluation_fingerprint=result["evaluation"]["fingerprint"],
        baseline_digest=result["baseline"]["digest"], candidate_digest=result["candidate"]["digest"],
        complete=result["complete"], tolerance=result["tolerance"], session_count=len(sessions),
        valid_session_count=sum(row["status"] == "valid" for row in sessions),
        invalid_session_count=sum(row["status"] != "valid" for row in sessions),
        flagged_session_count=sum(row["regression"] is True for row in sessions),
        expected_samples=sum(row["n_expected"] for row in sessions),
        scored_samples=sum(row["n_scored"] for row in sessions),
        global_issues=result["issues"], pooled=result["pooled"],
        excluded_counts=result["excluded_counts"], sessions=sessions)


def _write(root, name, inputs, *, tolerance=0.1, numerical_tolerance=1e-12,
           description=_DESCRIPTION):
    destination = root / name
    result = compare(*inputs, tolerance=tolerance, numerical_tolerance=numerical_tolerance,
                     description=description, output_dir=destination)
    _require(reproduce(destination) == result, f"Scoring reproduction differs: {name}")
    _require({p.name for p in destination.iterdir()} == _ARTIFACTS | {"manifest.json"},
             f"Unexpected bundle files: {name}")
    return result, _summary(name, result)


def _changed_candidate(inputs, records):
    evaluation, baseline, candidate = inputs
    return evaluation, baseline, PredictionSet.from_records(records, run_id=candidate.run_id,
        evaluation=evaluation, provenance=candidate.provenance)


def _public_replay(root, source):
    manifest = json.loads((source / "manifest.json").read_text())
    _require(set(manifest["files"]) == _ARTIFACTS, "Unexpected original public manifest files")
    before = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
              for name in _ARTIFACTS | {"manifest.json"}}
    _require(all(before[name] == expected for name, expected in manifest["files"].items()),
             "Original public bundle does not match its saved file hashes")
    original = json.loads((source / "comparison.json").read_text())
    inputs = (EvaluationSet.load(source / "evaluation.json"),
              PredictionSet.load(source / "baseline.json"),
              PredictionSet.load(source / "candidate.json"))
    result, summary = _write(root, "public-saved-output-replay", inputs,
        tolerance=manifest["tolerance"], numerical_tolerance=manifest["numerical_tolerance"],
        description=manifest["description"])

    def without_source(value):
        return json.dumps({k: v for k, v in value.items() if k != "comparator_source_digest"},
                          sort_keys=True, separators=(",", ":"), allow_nan=False)

    _require(without_source(original) == without_source(result),
             "Public result changed in a field other than comparator_source_digest")
    after = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in before}
    _require(before == after, "Original public bundle bytes changed")
    summary.update(original_payload_equal_except_source_digest=True, original_bundle_unchanged=True,
                   original_comparator_source_digest=original["comparator_source_digest"],
                   original_manifest_sha256=before["manifest.json"])
    return summary


def generate(output_dir, public_bundle=None):
    """Write fresh fixture bundles and return their machine-readable index."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=False)
    states = []

    inputs = _inputs("pooled-improves-session-regresses")
    result, summary = _write(root, "pooled-improves-session-regresses", inputs)
    _require(result["complete"] and result["pooled"]["delta"] < 0, "Expected pooled improvement")
    _require([row["session_id"] for row in result["sessions"] if row["regression"]] == ["session-03"],
             "Expected exactly session-03 to regress")
    _require(summary["session_count"] == 4 and summary["scored_samples"] == 420,
             "Expected four sessions and 420 scored samples")
    states.append(summary)

    # Fixed acceptance case: a 24-sample late failure, hidden by pooled improvement.
    # This is constructed tooling evidence, not an experiment on recordings.
    result, summary = _write(root, "late-session-regression", _inputs(
        "late-session-regression", [("control-session", 1800), ("late-session", 600)],
        candidate_error=lambda session, index: (
            6.0 if session == "late-session" and 540 <= index < 564 else 0.25)))
    late_samples = [row for row in result["samples"] if row["session_id"] == "late-session"]
    _require(result["complete"] and result["pooled"]["delta"] < 0,
             "Late fixture must have complete coverage and pooled improvement")
    _require([row["session_id"] for row in result["sessions"] if row["regression"]] == ["late-session"],
             "Late fixture must flag only the affected session")
    _require(_localization_window(late_samples) == (540, 564),
             "Localization must recover the fixed late window exactly")
    summary["localization_acceptance"] = dict(
        session_id="late-session", start_index=540, stop_index_exclusive=564,
        start_sample_id="sample-0540", end_sample_id="sample-0563",
        first_24_samples_outside_failure=True, all_2400_samples_scored=True)
    states.append(summary)

    invalid_inputs = _inputs("invalid-missing-nonfinite-and-global")
    invalid_rows = [dict(row) for row in invalid_inputs[2].records
                    if (row["session_id"], row["sample_id"]) != ("session-01", "sample-0000")]
    for row in invalid_rows:
        if (row["session_id"], row["sample_id"]) == ("session-02", "sample-0000"):
            row["predicted_vx"] = float("nan")
    unknown = dict(session_id="unknown-session", sample_id="unexpected", predicted_vx=0, predicted_vy=0)
    invalid_rows.append(unknown)
    result, summary = _write(root, "invalid-missing-nonfinite-and-global",
                             _changed_candidate(invalid_inputs, invalid_rows))
    _require(not result["complete"] and result["pooled"] is None and result["issues"], "Expected incomplete comparison")
    _require(summary["session_count"] == 4 and summary["invalid_session_count"] == 2,
             "Expected two invalid sessions without dropping any session")
    states.append(summary)

    global_inputs = _inputs("global-only-incomplete")
    result, summary = _write(root, "global-only-incomplete", _changed_candidate(
        global_inputs, list(global_inputs[2].records) + [unknown]))
    _require(not result["complete"] and result["pooled"] is None and result["issues"], "Expected global incompleteness")
    _require(summary["valid_session_count"] == 4 and summary["invalid_session_count"] == 0,
             "Global-only case must retain four valid session rows")
    states.append(summary)

    result, summary = _write(root, "descriptive-mixed-signs", _inputs("descriptive-mixed-signs"), tolerance=None)
    _require(result["complete"] and all(row["regression"] is None for row in result["sessions"]),
             "Descriptive state cannot contain categorical regression flags")
    _require(any(row["delta"] > 0 for row in result["sessions"]) and
             any(row["delta"] < 0 for row in result["sessions"]), "Expected mixed descriptive signs")
    states.append(summary)

    hostile = "-" + "long_unbroken_identifier_" * 9 + '\"><img src=x onerror="alert(1)"><script>unsafe</script>&測定'
    result, summary = _write(root, "long-hostile-identifiers",
        _inputs("long-hostile-identifiers", [("session", 360)], candidate_error=lambda _s, _i: 0.5, suffix=hostile),
        description=_DESCRIPTION + "\nProducer text: " + hostile)
    _require(result["complete"] and summary["scored_samples"] == 360, "Expected complete long-ID fixture")
    summary["preview_checks"] = "360 samples exercise bounded trace and 24-row sample preview; producer strings must remain text"
    states.append(summary)

    result, summary = _write(root, "singleton-zero-error", _inputs("singleton-zero-error", [("only-session", 1)],
        baseline_error=lambda _s, _i: 0, candidate_error=lambda _s, _i: 0))
    _require(result["complete"] and result["pooled"]["baseline_rmse"] == 0 and
             result["pooled"]["candidate_rmse"] == 0, "Expected single sample with zero error")
    states.append(summary)

    deltas = {"within-tolerance": 0.125, "exactly-tolerance": 0.25, "above-tolerance": 0.5}
    result, summary = _write(root, "numeric-tolerance-boundaries",
        _inputs("numeric-tolerance-boundaries", [(name, 1) for name in deltas],
                candidate_error=lambda session, _i: 1 + deltas[session]), tolerance=0.25)
    for row in result["sessions"]:
        _require(row["delta"] == deltas[row["session_id"]], "Unexpected numeric fixture delta")
        _require(row["regression"] is (row["session_id"] == "above-tolerance"),
                 "Regression must mean strictly greater than tolerance")
    states.append(summary)

    if public_bundle is not None:
        states.append(_public_replay(root, Path(public_bundle)))
    digests = {state["comparator_source_digest"] for state in states}
    _require(len(digests) == 1, "Comparator source changed while generating fixtures; preserve this run and start a fresh directory")
    index = dict(kind="report-ui-validation-fixtures", format_version=1,
                 comparator_source_digest=next(iter(digests)), states=states)
    (root / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="Fresh destination; existing directories are refused")
    parser.add_argument("--public-bundle", type=Path, help="Existing saved public comparison; read only, no model execution")
    arguments = parser.parse_args()
    print(json.dumps(generate(arguments.output_dir, arguments.public_bundle), indent=2, sort_keys=True, allow_nan=False))
