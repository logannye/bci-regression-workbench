"""An existing evaluator with one pinned comparison hook at completion.

Initialize the reference once. Later commands generate only candidate outputs
and reuse the reference unchanged. All predictions here are synthetic.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from bci_regression import EvaluationSet, PredictionSet, reproduce
from bci_regression.pinned import PinnedComparison


# This is the existing evaluator's export schema, mapped once at setup.
PREDICTION_COLUMNS = {
    "session_id": "recording", "sample_id": "bin",
    "predicted_vx": "vx", "predicted_vy": "vy",
}
DESCRIPTION = "Synthetic evaluator integration. No neural recordings or model performance claims."


def current_evaluation():
    """Build identity from the job's actual labels/mask, never from the pin."""
    targets = []
    for session, count in [("session-01", 200), ("session-02", 100),
                           ("session-03", 40), ("session-04", 80)]:
        for i in range(count):
            targets.append(dict(session_id=session, sample_id=f"sample-{i:04d}",
                timestamp=i * 0.02, target_vx=math.sin(i / 11), target_vy=math.cos(i / 17)))
    return EvaluationSet.from_records(targets, evaluation_id="synthetic-velocity-v1",
        units="cm/s", coordinates="synthetic-x-y", source_ref="examples/basic_comparison.py",
        purpose="development / synthetic tooling acceptance")


def synthetic_outputs(evaluation, *, baseline=False):
    errors = {"session-01": 0.3, "session-02": 0.7, "session-03": 0.4, "session-04": 1.0}
    rows = []
    for row in evaluation.records:
        sid, sample = row["session_id"], row["sample_id"]
        i = int(sample.split("-")[1])
        error = 1.0 if baseline else (2.8 if sid == "session-03" and 18 <= i < 28 else errors[sid])
        rows.append(dict(recording=sid, bin=sample,
                         vx=row["target_vx"] + error, vy=row["target_vy"]))
    return rows


def initialize(output_dir: Path):
    evaluation = current_evaluation()
    baseline = PredictionSet.from_records(synthetic_outputs(evaluation, baseline=True),
        run_id="baseline-001", evaluation=evaluation, columns=PREDICTION_COLUMNS,
        provenance={"producer": "examples/basic_comparison.py", "kind": "synthetic"})
    PinnedComparison.create(output_dir / "pinned", evaluation=evaluation, baseline=baseline,
        prediction_columns=PREDICTION_COLUMNS, tolerance=0.1, description=DESCRIPTION)
    print(f"Reference initialized: {(output_dir / 'pinned').resolve()}")


def run(output_dir: Path, candidate_id="candidate-001"):
    if not candidate_id or Path(candidate_id).name != candidate_id or candidate_id in {".", "..", "pinned"}:
        raise ValueError("candidate_id must be a simple unique directory name")
    check = PinnedComparison.load(output_dir / "pinned")

    # The ordinary evaluator owns this work and its actual evaluation identity.
    evaluation = current_evaluation()
    candidate_rows = synthetic_outputs(evaluation)
    report_dir = output_dir / candidate_id / "session-regressions"

    # The sole addition at evaluation completion: no baseline, mapping or threshold selection.
    result = check.compare(candidate_rows, evaluation=evaluation, run_id=candidate_id,
        output_dir=report_dir,
        provenance={"producer": "examples/basic_comparison.py", "kind": "synthetic"})
    print(f"Report: {(report_dir / 'report.html').resolve()}")

    # Acceptance checks for this constructed demonstration, not a deployment gate.
    assert result["complete"] and result["pooled"]["delta"] < 0
    assert [r["session_id"] for r in result["sessions"] if r["regression"]] == ["session-03"]
    assert reproduce(report_dir) == result
    print("Comparison reproduced. Pooled error decreased; session-03 became worse.")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--initialize", action="store_true", help="One-time reference setup; refuses replacement")
    parser.add_argument("--candidate-id", default="candidate-001")
    args = parser.parse_args()
    if args.initialize:
        initialize(args.output_dir)
    else:
        run(args.output_dir, args.candidate_id)
