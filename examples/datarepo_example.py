"""Synthetic output comparison through upstream datarepo's real Parquet API.

This example generates prediction tables directly; it does not train or run
decoders and contains no neural recordings. The smaller session worsens while
pooled RMSE improves. Run in the optional requirements-datarepo environment.
The upstream 0.1.0 wheel defines NlkDataFrame as polars.LazyFrame and exposes
ParquetTable(name, uri, partitioning=[]), whose query is explicitly collected.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import math
from pathlib import Path


def run(output_dir: Path) -> None:
    import boto3
    import pyarrow as pa
    import pyarrow.parquet as pq
    from datarepo.core import NlkDataFrame, ParquetTable

    from bci_regression import EvaluationSet, PredictionSet, compare
    from bci_regression.tables import table_records

    # Explicit placeholders prevent ambient AWS credential discovery. These
    # are not credentials and are never sent anywhere: every URI is a local
    # file and this example makes no cloud requests.
    local_session = boto3.Session(
        aws_access_key_id="unused-local-file-example",
        aws_secret_access_key="unused-local-file-example",
        region_name="us-east-1",
    )

    targets, baseline_rows, candidate_rows = [], [], []
    for session_id, count, candidate_error in [
        ("long-session", 8, 0.25),
        ("short-session", 2, 2.0),
    ]:
        for index in range(count):
            identity = {"session_id": session_id, "sample_id": str(index)}
            vx, vy = index / 10, -index / 10
            targets.append(
                {
                    **identity,
                    "timestamp": index * 0.02,
                    "target_vx": vx,
                    "target_vy": vy,
                    "eligible": True,
                }
            )
            baseline_rows.append(
                {**identity, "predicted_vx": vx + 1.0, "predicted_vy": vy}
            )
            candidate_rows.append(
                {
                    **identity,
                    "predicted_vx": vx + candidate_error,
                    "predicted_vy": vy,
                }
            )

    # Refuse to overwrite an earlier example or any user-owned directory.
    output_dir.mkdir(parents=True, exist_ok=False)
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir()
    loaded = {}
    for name, records in [
        ("targets", targets),
        ("baseline", baseline_rows),
        ("candidate", candidate_rows),
    ]:
        path = inputs_dir / f"{name}.parquet"
        pq.write_table(pa.Table.from_pylist(records), path)
        table = ParquetTable(name=name, uri=str(path.resolve()), partitioning=[])
        query = table(boto3_session=local_session)
        if not isinstance(query, NlkDataFrame):
            raise TypeError("datarepo returned an unexpected query type")
        loaded[name] = table_records(query.collect())

    target_digest = hashlib.sha256((inputs_dir / "targets.parquet").read_bytes()).hexdigest()
    evaluation = EvaluationSet.from_records(
        loaded["targets"],
        evaluation_id="synthetic-datarepo-v1",
        units="cm/s",
        coordinates="synthetic-x-y",
        horizon_ms=0,
        purpose="development",
        source_ref=f"local targets.parquet sha256:{target_digest}",
    )
    provenance = {
        "producer": "examples/datarepo_example.py",
        "kind": "synthetic prediction fixture; no model execution",
        "datarepo_version": version("data-repository"),
        "polars_version": version("polars"),
        "pyarrow_version": version("pyarrow"),
    }
    baseline = PredictionSet.from_records(
        loaded["baseline"],
        run_id="synthetic-baseline-v1",
        evaluation=evaluation,
        provenance=provenance,
    )
    candidate = PredictionSet.from_records(
        loaded["candidate"],
        run_id="synthetic-candidate-v1",
        evaluation=evaluation,
        provenance=provenance,
    )
    result = compare(
        evaluation,
        baseline,
        candidate,
        tolerance=0.1,
        numerical_tolerance=1e-12,
        output_dir=output_dir / "comparison",
        description="Synthetic datarepo integration example. Constructed predictions; no neural recordings or model execution.",
    )
    if not result["complete"]:
        raise AssertionError("Synthetic fixture must produce a complete comparison")
    sessions = {row["session_id"]: row for row in result["sessions"]}
    for name, expected_count, expected_candidate in [
        ("long-session", 8, 0.25),
        ("short-session", 2, 2.0),
    ]:
        row = sessions[name]
        if (
            row["n_scored"] != expected_count
            or not math.isclose(row["baseline_rmse"], 1.0, abs_tol=1e-12)
            or not math.isclose(row["candidate_rmse"], expected_candidate, abs_tol=1e-12)
        ):
            raise AssertionError(f"Unexpected synthetic session scores: {row}")
    if not sessions["short-session"]["regression"] or result["pooled"]["delta"] >= 0:
        raise AssertionError("The report must expose a regression despite pooled improvement")
    print(f"Synthetic datarepo comparison saved to {output_dir / 'comparison'}")
    print("Expected session RMSE: baseline 1.0 each; candidate long 0.25, short 2.0.")
    print("Pooled candidate RMSE is sqrt(0.85), below baseline 1.0.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == "__main__":
    main()
