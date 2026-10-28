"""Synthetic evaluator output: a better pooled score hides one worse session.

This is a complete local workflow example, not a neural model experiment.
The saved baseline is reused on subsequent candidates without model execution.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from bci_regression import EvaluationSet, PredictionSet, compare, reproduce


def fixture():
    targets, baseline, candidate = [], [], []
    for session, count, error in [("session-01", 200, 0.3), ("session-02", 100, 0.7),
                                  ("session-03", 40, 0.4), ("session-04", 80, 1.0)]:
        for i in range(count):
            key = dict(session_id=session, sample_id=f"sample-{i:04d}")
            vx, vy = math.sin(i / 11), math.cos(i / 17)
            targets.append(dict(**key, timestamp=i * 0.02, target_vx=vx, target_vy=vy))
            baseline.append(dict(**key, predicted_vx=vx + 1, predicted_vy=vy))
            local_error = 2.8 if session == "session-03" and 18 <= i < 28 else error
            candidate.append(dict(**key, predicted_vx=vx + local_error, predicted_vy=vy))
    return targets, baseline, candidate


def run(output_dir: Path, candidate_id="candidate-001"):
    if not candidate_id or Path(candidate_id).name != candidate_id or candidate_id in {".", "..", "pinned"}:
        raise ValueError("candidate_id must be a simple unique directory name")
    targets, baseline_rows, candidate_rows = fixture()
    pinned = output_dir / "pinned"
    if output_dir.exists():
        if not (pinned / "evaluation.json").is_file() or not (pinned / "baseline.json").is_file():
            raise FileExistsError("Existing directory is not an initialized example; choose a fresh output directory")
        evaluation = EvaluationSet.load(pinned / "evaluation.json")
        baseline = PredictionSet.load(pinned / "baseline.json")
    else:
        pinned.mkdir(parents=True)
        evaluation = EvaluationSet.from_records(targets, evaluation_id="synthetic-velocity-v1",
            units="cm/s", coordinates="synthetic-x-y", source_ref="examples/basic_comparison.py:fixture",
            purpose="development / synthetic tooling acceptance")
        baseline = PredictionSet.from_records(baseline_rows, run_id="baseline-001", evaluation=evaluation,
            provenance={"producer": "examples/basic_comparison.py", "kind": "synthetic; no model execution"})
        evaluation.save(pinned / "evaluation.json")
        baseline.save(pinned / "baseline.json")

    # In an engineer's job, these rows come from their existing evaluation.
    candidate = PredictionSet.from_records(candidate_rows, run_id=candidate_id, evaluation=evaluation,
        provenance={"producer": "examples/basic_comparison.py", "kind": "synthetic; no model execution"})
    result = compare(evaluation, baseline, candidate, tolerance=0.1, output_dir=output_dir / candidate_id,
        description="Synthetic acceptance example. Predictions are constructed directly; no neural recordings or model performance claims.")
    assert result["complete"] and result["pooled"]["delta"] < 0
    assert [r["session_id"] for r in result["sessions"] if r["regression"]] == ["session-03"]
    reproduced = reproduce(output_dir / candidate_id)
    assert reproduced == result
    print(f"Comparison reproduced. Pooled error decreased; session-03 became worse.")
    print(f"Report: {(output_dir / candidate_id / 'report.html').resolve()}")
    print(f"Pinned baseline: {baseline.run_id} ({baseline.digest[:12]})")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--candidate-id", default="candidate-001")
    args = parser.parse_args()
    run(args.output_dir, args.candidate_id)
