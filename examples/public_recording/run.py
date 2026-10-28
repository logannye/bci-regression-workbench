"""Run the frozen Indy demonstration outside the comparison library.

No model selection: fit twice on the source day, save every evaluation
prediction, then open evaluation cursor positions and call the comparator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import urllib.request

import h5py
import numpy as np

from bci_regression import EvaluationSet, PredictionSet, compare, reproduce
from examples.public_recording.audit import audit_run
from examples.public_recording.data import read_neural, read_targets
from examples.public_recording.model import causal_features, fit_source_ridge, predict


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "docs/public-demo/protocol-v1.json"
PROTOCOL_SHA256 = "c7d24fbde2bd727247fb4415d134d10761b3ab204bb4f3af3015dbda02488af9"


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def verify_input(path, spec):
    if path.stat().st_size != spec["size_bytes"] or digest(path, "md5") != spec["md5"]:
        raise ValueError(f"Published size/checksum mismatch: {spec['name']}")
    return {**spec, "sha256": digest(path)}


def fetch_input(directory, spec):
    """Bounded, checksum-verified public download; never read the results CSV."""
    path = directory / spec["name"]
    if path.exists():
        return verify_input(path, spec)
    partial = path.with_suffix(path.suffix + ".part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "bci-regression-workbench/0.1 public-research-demo"})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
                size = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > spec["size_bytes"]:
                        raise ValueError("Download exceeded frozen file size")
                    out.write(chunk)
            receipt = verify_input(partial, spec)
            partial.rename(path)
            return receipt
        except (OSError, ValueError):
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def save_features(path, neural, indices):
    np.savez_compressed(path, rates=neural.rates, sample_indices=indices,
                        edge_indices=neural.edge_indices, absolute_edges=neural.absolute_edges,
                        timestamps=neural.timestamps)


def run(input_dir: Path, output_dir: Path):
    if digest(PROTOCOL) != PROTOCOL_SHA256:
        raise ValueError("Frozen protocol bytes differ; do not silently change the experiment")
    plan = json.loads(PROTOCOL.read_text())
    if sum(f["size_bytes"] for f in plan["files"]) > plan["data"]["max_total_download_bytes"]:
        raise ValueError("Frozen download budget exceeded")
    output_dir.mkdir(parents=True, exist_ok=False)
    input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROTOCOL, output_dir / "protocol.json")
    (output_dir / "ATTRIBUTION.txt").write_text(
        "Source: O'Doherty, Cardoso, Makin, and Sabes. Nonhuman Primate Reaching with "
        "Multichannel Sensorimotor Cortex Electrophysiology, version 2. "
        "https://doi.org/10.5281/zenodo.3854034 ; CC BY 4.0 "
        "https://creativecommons.org/licenses/by/4.0/ .\n"
        "Derived here: 64 ms neural rates, measured cursor velocity, ridge predictions, "
        "and comparison scores. Physical-reaching data from one macaque; no Neuralink data.\n")
    phase = "download"
    try:
        source_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        source_hashes = {p.name: digest(p) for p in Path(__file__).parent.glob("*.py")}
        environment = dict(python=platform.python_version(), platform=platform.platform(),
                           numpy=np.__version__, h5py=h5py.__version__, source_revision=source_revision,
                           producer_sources=source_hashes,
                           threads={k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")})
        write_json(output_dir / "environment.json", environment)
        if platform.python_version_tuple()[:2] != ("3", "11") or np.__version__ != "2.2.6" or h5py.__version__ != "3.14.0":
            raise ValueError("Use the frozen Python 3.11 / NumPy 2.2.6 / h5py 3.14.0 producer environment")
        if any(environment["threads"][key] != "1" for key in environment["threads"]):
            raise ValueError("Set OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS to 1 before launch")
        inputs = []
        for spec in plan["files"]:
            inputs.append(fetch_input(input_dir, spec))
            write_json(output_dir / "inputs.json", inputs)
            print(f"Verified public recording: {spec['name']}", flush=True)
        source = next(f for f in inputs if f["role"] == "train")
        evaluation_specs = [f for f in inputs if f["role"] == "evaluation"]
        phase = "source_fit"
        source_neural = read_neural(input_dir / source["name"], plan["data"])
        source_targets = read_targets(input_dir / source["name"], source_neural.edges)
        warmup = plan["data"]["common_warmup_bins"]
        source_indices = np.arange(warmup, len(source_neural.rates), dtype=np.int64)
        np.savez_compressed(output_dir / "source-training.npz", rates=source_neural.rates,
                            targets=source_targets, sample_indices=source_indices,
                            edge_indices=source_neural.edge_indices, absolute_edges=source_neural.absolute_edges)
        (output_dir / "models").mkdir()
        models = {}
        model_receipts = {}
        for role in ("baseline", "candidate"):
            config = plan["models"][role]
            features = causal_features(source_neural.rates, source_indices, history_bins=config["history_bins"])
            model = fit_source_ridge(features, source_targets[source_indices], alpha=plan["models"]["ridge_lambda"])
            models[role] = model
            model_path = output_dir / "models" / f"{role}.json"
            write_json(model_path, dict(model_id=config["id"], history_bins=config["history_bins"],
                source_session_id=source["session_id"], protocol_sha256=PROTOCOL_SHA256, model=model.to_dict()))
            model_receipts[role] = dict(sha256=digest(model_path), history_bins=config["history_bins"],
                                        model_id=config["id"], n_source_rows=len(source_indices))
        print("Saved both fixed source-day models. Evaluation cursor positions remain unopened.", flush=True)
        phase = "neural_only_prediction"
        (output_dir / "features").mkdir()
        for role in models:
            (output_dir / "predictions" / role).mkdir(parents=True)
        neural_sessions, prediction_receipts = {}, {}
        for spec in evaluation_specs:
            sid = spec["session_id"]
            neural = read_neural(input_dir / spec["name"], plan["data"])
            neural_sessions[sid] = neural
            indices = np.arange(warmup, len(neural.rates), dtype=np.int64)
            save_features(output_dir / "features" / f"{sid}.npz", neural, indices)
            for role, model in models.items():
                features = causal_features(neural.rates, indices, history_bins=plan["models"][role]["history_bins"])
                outputs = predict(model, features)
                path = output_dir / "predictions" / role / f"{sid}.npz"
                np.savez_compressed(path, sample_indices=indices, predicted_velocity=outputs)
                prediction_receipts[f"{role}/{sid}"] = digest(path)
        write_json(output_dir / "predictions-ready.json", dict(
            protocol_sha256=PROTOCOL_SHA256, phase="all_predictions_saved_before_evaluation_labels",
            models=model_receipts, predictions=prediction_receipts))
        # Nothing above this line opens evaluation cursor_pos or target_pos.
        # Freeze raw prediction files for ALL sessions before binding them to scorer labels.
        phase = "score_saved_predictions"
        evaluation_rows, prediction_rows = [], {role: [] for role in models}
        for spec in evaluation_specs:
            sid = spec["session_id"]
            neural = neural_sessions[sid]
            targets = read_targets(input_dir / spec["name"], neural.edges)
            for i, (timestamp, target) in enumerate(zip(neural.timestamps, targets)):
                evaluation_rows.append(dict(session_id=sid, sample_id=neural.sample_ids[i],
                    timestamp=float(timestamp), target_vx=float(target[0]), target_vy=float(target[1]),
                    eligible=i >= warmup, exclusion_reason="" if i >= warmup else "causal-history warmup"))
            for role in models:
                path = output_dir / "predictions" / role / f"{sid}.npz"
                if digest(path) != prediction_receipts[f"{role}/{sid}"]:
                    raise ValueError("Saved predictions changed before scoring")
                with np.load(path, allow_pickle=False) as saved:
                    for i, values in zip(saved["sample_indices"], saved["predicted_velocity"]):
                        prediction_rows[role].append(dict(session_id=sid, sample_id=neural.sample_ids[int(i)],
                            predicted_vx=float(values[0]), predicted_vy=float(values[1])))
        evaluation = EvaluationSet.from_records(evaluation_rows, evaluation_id=plan["protocol_id"],
            units=plan["data"]["units"], coordinates=plan["data"]["coordinates"],
            horizon_ms=plan["data"]["horizon_ms"], purpose=plan["comparison"]["purpose"],
            source_ref=f"{plan['dataset']['doi']}; protocol sha256:{PROTOCOL_SHA256}")
        bundles = {}
        for role in models:
            bundles[role] = PredictionSet.from_records(prediction_rows[role], run_id=plan["models"][role]["id"],
                evaluation=evaluation, provenance=dict(protocol_sha256=PROTOCOL_SHA256,
                    model_sha256=model_receipts[role]["sha256"], source_training_session=source["session_id"],
                    source_revision=source_revision, producer_sources=source_hashes,
                    recording_sha256={f["session_id"]: f["sha256"] for f in inputs},
                    raw_predictions_sha256={k: v for k, v in prediction_receipts.items() if k.startswith(role + "/")},
                    protocol="One source-day fit; all predictions saved before evaluation positions are read; no evaluation refit."))
        result = compare(evaluation, bundles["baseline"], bundles["candidate"],
            tolerance=plan["comparison"]["reporting_tolerance"],
            numerical_tolerance=plan["comparison"]["numerical_tolerance"], output_dir=output_dir / "comparison",
            description="Public Indy physical-reaching recordings. Current-bin ridge versus four-bin causal history, trained on September 15 and evaluated on three later days. Offline measured movement; descriptive differences, not Neuralink or closed-loop results.")
        if not result["complete"] or len(result["sessions"]) != len(evaluation_specs):
            raise ValueError("Frozen comparison is incomplete; retain every expected session")
        phase = "independent_audit_and_reproduction"
        audit = audit_run(output_dir)
        write_json(output_dir / "audit.json", audit)
        if audit.get("status") != "passed":
            raise ValueError("Independent verification did not pass")
        if reproduce(output_dir / "comparison") != result:
            raise ValueError("Scoring reproduction differed")
        summary = dict(status="complete", protocol_sha256=PROTOCOL_SHA256, source_revision=source_revision,
            producer_sources=source_hashes, comparator_source_digest=result["comparator_source_digest"],
            input_files=inputs, models=model_receipts, training_rows=len(source_indices),
            source_training_bundle_sha256=digest(output_dir / "source-training.npz"),
            sessions=result["sessions"], excluded_counts=result["excluded_counts"], pooled=result["pooled"],
            evaluation_fingerprint=evaluation.fingerprint, audit=audit, scoring_reproduction="passed",
            limitations=plan["limitations"])
        write_json(output_dir / "summary.json", summary)
        files = {str(p.relative_to(output_dir)): digest(p) for p in output_dir.rglob("*") if p.is_file()}
        write_json(output_dir / "receipt.json", dict(status="complete", protocol_sha256=PROTOCOL_SHA256,
                                                    source_revision=source_revision, files=files))
        print(json.dumps(dict(status="complete", sessions=result["sessions"], pooled=result["pooled"]), indent=2), flush=True)
        return summary
    except BaseException as exc:
        write_json(output_dir / "failure.json", dict(status="failed", phase=phase,
            selected_sessions=[f["session_id"] for f in plan["files"]], protocol_sha256=PROTOCOL_SHA256,
            error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir)
