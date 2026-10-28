"""Independent, no-refit audit of the frozen MINDFUL T11 example.

Read original MATLAB inputs and saved artifacts. Do not import the producer,
its loader/model, or the comparator. Reconstruct trial masks, source-only
normalization, prediction arithmetic, and vector RMSE independently.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
from scipy.io import loadmat

FROZEN_SHA256 = "9f51616b54b1af3dc884f4ccd51baa79ccb0f2789800aff676dafd93d68267b6"
TARGET_KIND = "inferred_cursor_to_target_vector"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _array(value, shape, name):
    value = np.asarray(value)
    _require(value.shape == shape and value.dtype.kind in "iuf" and np.isfinite(value).all(),
             f"{name}: invalid shape or nonfinite numeric values")
    return value.astype(np.float64, copy=False)


def _close(actual, expected, tolerance, name):
    actual, expected = np.asarray(actual), np.asarray(expected)
    _require(actual.shape == expected.shape, f"{name}: shape mismatch")
    error = float(np.max(np.abs(actual - expected))) if actual.size else 0.0
    _require(math.isfinite(error) and error <= tolerance,
             f"{name}: absolute difference {error} exceeds {tolerance}")
    return error


def _read_block(input_dir, spec, *, verify=True):
    """Use inclusive source trial intervals, independently of producer masks."""
    directory = input_dir / f"day_{spec['day']}" / spec["block"]
    _require(directory.resolve().is_relative_to(input_dir.resolve()), "Input path escapes T11 directory")
    if verify:
        _require(set(spec["files"]) == {"data.mat", "task.mat", "info.mat"}, "Unexpected source file set")
        for name, expected in spec["files"].items():
            path = directory / name
            _require(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                     f"Source hash mismatch: {directory.name}/{name}")
    n = spec["n_bins"]
    data = loadmat(directory / "data.mat", variable_names=["nctx", "labels"], simplify_cells=True)
    task = loadmat(directory / "task.mat", simplify_cells=True)
    neural = _array(data["nctx"], (n, 192), "source nctx")
    targets = _array(data["labels"], (n, 2), "source inferred targets")
    _require((neural >= 0).all(), "Negative source neural features")
    _require(task["name"] == "circleOfCircles" and task["nPointsPerBlock"] == n,
             "Source task identity or bin count differs")
    intervals = np.atleast_2d(task["startStops"])
    _require(intervals.ndim == 2 and intervals.shape[1] == 2 and len(intervals) > 0,
             "Malformed trial intervals")
    _require(intervals.dtype.kind in "iuf" and np.isfinite(intervals).all()
             and np.equal(intervals, np.floor(intervals)).all(), "Noninteger trial intervals")
    intervals = intervals.astype(np.int64)
    flags = np.atleast_1d(task["excludeTrials"])
    _require(flags.shape == (len(intervals),) and flags.dtype.kind in "biuf"
             and np.isin(flags, [0, 1]).all(), "Malformed trial exclusions")
    reasons = ["outside-trial"] * n
    indices, preceding_stop = [], 0
    for (first, last), flag in zip(intervals, flags):
        _require(1 <= first <= last <= n and first > preceding_stop, "Overlapping or invalid trial intervals")
        preceding_stop = last
        for one_based in range(int(first), int(last) + 1):
            if flag:
                reason = "source-excluded-trial"
            elif one_based - first < 3:
                reason = "history-warmup"
            else:
                reason = ""
                indices.append(one_based - 1)
            reasons[one_based - 1] = reason
    indices = np.asarray(indices, dtype=np.int64)
    counts = dict(Counter(reason for reason in reasons if reason))
    _require(len(indices) == spec["expected_eligible_bins"], "Frozen eligible denominator differs")
    _require(counts == spec["expected_exclusions"], "Frozen exclusion denominators differ")
    return neural, targets, indices, reasons


def _design(neural, indices, history):
    # Build lag columns separately rather than use the producer's reshape path.
    return np.concatenate([neural[indices - lag, :] for lag in range(history)], axis=1)


def audit_run(root, input_dir, *, expected_protocol_sha256=FROZEN_SHA256):
    """Return an aggregate audit receipt; never fit, download, or write artifacts.

    The optional digest override exists for isolated synthetic test fixtures.
    Production calls use the default identity of the prospectively frozen plan.
    """
    root, input_dir = Path(root), Path(input_dir)
    evidence = {}

    def read(relative):
        path = root / relative
        _require(path.resolve().is_relative_to(root.resolve()), "Evidence path escapes run directory")
        value = path.read_bytes()
        evidence[relative] = dict(path=relative, size_bytes=len(value), sha256=hashlib.sha256(value).hexdigest())
        return value

    def document(relative):
        def reject(value):
            raise ValueError(f"Nonstandard JSON constant: {value}")
        return json.loads(read(relative), parse_constant=reject)

    def bundle(relative, kind, identity):
        doc = document(relative)
        _require(doc.get("format_version") == 1 and doc.get("kind") == kind, "Unexpected comparison bundle format")
        _require(_digest(doc["payload"]) == doc[identity], f"{relative}: bundle content identity differs")
        return doc

    protocol = document("protocol.json")
    protocol_hash = evidence["protocol.json"]["sha256"]
    _require(protocol_hash == expected_protocol_sha256, "Frozen protocol identity differs")
    config, specs = protocol["data"], protocol["blocks"]
    tolerance = protocol["comparison"]["numerical_tolerance"]
    _require(tolerance == 1e-9 and protocol["comparison"]["reporting_tolerance"] is None,
             "Unexpected comparison settings")
    _require(config["target_kind"] == TARGET_KIND and config["n_channels"] == 192
             and config["common_history_bins"] == 4 and config["bin_seconds"] == 0.02,
             "Unexpected frozen feature or target semantics")
    _require(document("inputs.json") == specs, "Input receipt differs from frozen blocks")
    keys = [(b["day"], b["block"]) for b in specs]
    _require(keys == sorted(set(keys)), "Duplicate or unordered selected blocks")
    train = [b for b in specs if b["role"] == "train"]
    evaluation_specs = [b for b in specs if b["role"] == "evaluation"]
    _require(train and evaluation_specs and len(train) + len(evaluation_specs) == len(specs)
             and max(b["day"] for b in train) < min(b["day"] for b in evaluation_specs),
             "Training/evaluation partitions are not chronological")
    source_blocks = []
    role_counts = defaultdict(Counter)
    for spec in specs:
        block = _read_block(input_dir, spec)
        role_counts[spec["role"]].update(spec["expected_exclusions"])
        role_counts[spec["role"]]["eligible"] += len(block[2])
        if spec["role"] == "train":
            source_blocks.append(block)
    for role, counts in role_counts.items():
        _require(dict(counts) == protocol["expected_counts"][role], "Frozen partition denominators differ")

    ready = document("predictions-ready.json")
    _require(ready["protocol_sha256"] == protocol_hash, "Prediction-ready protocol differs")
    _require(ready["phase"] == "all_evaluation_predictions_saved_before_evaluation_labels_opened_in_this_run",
             "Prediction-ready phase differs")
    n_train = sum(len(block[2]) for block in source_blocks)
    targets = np.concatenate([block[1][block[2]] for block in source_blocks])
    target_mean = targets.mean(axis=0)
    models, model_checks = {}, {}
    for role, history in (("baseline", 1), ("candidate", 4)):
        relative = f"models/{role}.json"
        snapshot = document(relative)
        cfg = protocol["models"][role]
        _require(snapshot["model_id"] == cfg["id"] and snapshot["history_bins"] == history == cfg["history_bins"]
                 and snapshot["protocol_sha256"] == protocol_hash, f"{role}: model identity differs")
        _require(ready["models"][role]["sha256"] == evidence[relative]["sha256"], f"{role}: saved model hash differs")
        _require(ready["models"][role]["n_training_rows"] == n_train
                 and ready["models"][role]["model_id"] == cfg["id"], f"{role}: model receipt differs")
        m, width = snapshot["model"], history * 192
        _require(m["schema_version"] == 1 and m["kind"] == "source_standardized_ridge", "Unexpected model format")
        mean = _array(m["feature_mean"], (width,), f"{role} mean")
        scale = _array(m["feature_scale"], (width,), f"{role} scale")
        weights = _array(m["weights"], (width, 2), f"{role} weights")
        intercept = _array(m["target_mean"], (2,), f"{role} intercept")
        _require((scale > 0).all() and m["alpha"] == protocol["models"]["ridge_lambda"] == 1.0
                 and m["n_source_rows"] == n_train, f"{role}: model setting or training denominator differs")
        # Blockwise passes bound memory; no optimizer/solve or model.predict.
        expected_mean = sum((_design(x, ii, history).sum(axis=0) for x, _, ii, _ in source_blocks),
                            np.zeros(width)) / n_train
        variance = sum((((_design(x, ii, history) - expected_mean) ** 2).sum(axis=0)
                        for x, _, ii, _ in source_blocks), np.zeros(width)) / n_train
        expected_scale = np.sqrt(variance)
        expected_scale[expected_scale == 0] = 1.0
        mean_error = _close(mean, expected_mean, tolerance, f"{role}: training-only mean")
        scale_error = _close(scale, expected_scale, tolerance, f"{role}: training-only scale")
        target_error = _close(intercept, target_mean, tolerance, f"{role}: training-only target mean")
        gradient, rhs = np.zeros_like(weights), np.zeros_like(weights)
        for x, y, ii, _ in source_blocks:
            z = (_design(x, ii, history) - mean) / scale
            centered = y[ii] - intercept
            gradient += z.T @ (z @ weights - centered) / n_train
            rhs += z.T @ centered / n_train
        gradient += m["alpha"] * weights
        residual = float(np.max(np.abs(gradient))) / max(1.0, float(np.max(np.abs(rhs))))
        _require(math.isfinite(residual) and residual <= tolerance, f"{role}: ridge optimality residual exceeds tolerance")
        models[role] = history, mean, scale, weights, intercept
        model_checks[role] = dict(n_training_rows=n_train, feature_mean_max_abs_error=mean_error,
            feature_scale_max_abs_error=scale_error, target_mean_max_abs_error=target_error,
            normalized_optimality_residual=residual)
    del source_blocks, targets

    eval_doc = bundle("comparison/evaluation.json", "evaluation", "fingerprint")
    evaluation = eval_doc["payload"]
    _require(evaluation["evaluation_id"] == protocol["protocol_id"] and evaluation["target_kind"] == TARGET_KIND
             and evaluation["units"] == config["units"] and evaluation["horizon_ms"] == 0,
             "Evaluation target semantics differ")
    _require(evaluation["coordinates"] == "MINDFUL stored cursor-to-target x,y displacement; source coordinate scale retained",
             "Evaluation coordinate convention differs")
    target_rows = {(r["session_id"], r["sample_id"]): r for r in evaluation["records"]}
    _require(len(target_rows) == len(evaluation["records"]), "Duplicate evaluation identities")
    supplied, bundle_digests = {}, {}
    for role in models:
        doc = bundle(f"comparison/{role}.json", "predictions", "digest")
        payload = doc["payload"]
        _require(payload["run_id"] == protocol["models"][role]["id"]
                 and payload["evaluation_fingerprint"] == eval_doc["fingerprint"], f"{role}: prediction identity differs")
        for key in ("units", "coordinates", "horizon_ms", "target_kind"):
            _require(payload[key] == evaluation[key], f"{role}: prediction target semantics differ")
        rows = {(r["session_id"], r["sample_id"]): r for r in payload["records"]}
        _require(len(rows) == len(payload["records"]), f"{role}: duplicate prediction identities")
        supplied[role], bundle_digests[role] = rows, doc["digest"]

    all_keys, scored_keys, prediction_files = set(), set(), set()
    offsets, terms, denominators = defaultdict(int), defaultdict(lambda: defaultdict(list)), Counter()
    maximum_prediction_error = {role: 0.0 for role in models}
    for spec in evaluation_specs:
        neural, targets, indices, reasons = _read_block(input_dir, spec, verify=False)
        sid = f"T11-day-{spec['day']:04d}"
        block = f"block-{int(spec['block'].split('_')[1]):02d}"
        for index, target in enumerate(targets):
            key = sid, f"{block}:bin-{index + 1:06d}"
            all_keys.add(key)
            _require(key in target_rows, f"Missing evaluation sample {key}")
            row = target_rows[key]
            _require(type(row["eligible"]) is bool and row["eligible"] == (reasons[index] == "")
                     and row["exclusion_reason"] == reasons[index], f"{key}: trial eligibility or reason differs")
            _require(row["timestamp"] == (offsets[sid] + index + 1) * 0.02, f"{key}: recording timestamp differs")
            _close([row["target_vx"], row["target_vy"]], target, 0.0, f"{key}: stored inferred target differs")
            if row["eligible"]:
                scored_keys.add(key)
        offsets[sid] += spec["n_bins"]
        denominators[sid] += len(indices)
        for role, (history, mean, scale, weights, intercept) in models.items():
            relative = f"predictions/{role}/{sid}-{block}.npz"
            prediction_files.add(relative)
            raw = read(relative)
            _require(evidence[relative]["sha256"] == ready["predictions"].get(relative), "Saved prediction hash differs")
            with np.load(io.BytesIO(raw), allow_pickle=False) as arrays:
                ii = arrays["sample_indices"]
                _require(ii.dtype.kind in "iu" and np.array_equal(ii, indices), "Saved prediction indices differ from trial mask")
                predicted = _array(arrays["predicted_vector"], (len(indices), 2), "Saved predicted vector")
            reconstructed = (_design(neural, indices, history) - mean) / scale @ weights + intercept
            error = _close(predicted, reconstructed, tolerance, f"{role}: reconstructed predictions")
            maximum_prediction_error[role] = max(maximum_prediction_error[role], error)
            for index, value, target in zip(indices, predicted, targets[indices]):
                key = sid, f"{block}:bin-{index + 1:06d}"
                _require(key in supplied[role], f"{role}: missing bound prediction")
                row = supplied[role][key]
                _close([row["predicted_vx"], row["predicted_vy"]], value, 0.0, f"{role}: bound prediction differs")
                terms[sid][role].append((float(value[0]) - float(target[0])) ** 2
                                        + (float(value[1]) - float(target[1])) ** 2)
    _require(set(target_rows) == all_keys, "Unexpected evaluation samples")
    _require(set(ready["predictions"]) == prediction_files, "Prediction-ready file inventory differs")
    for role in models:
        _require(set(supplied[role]) == scored_keys, f"{role}: unexpected bound prediction samples")

    result = document("comparison/comparison.json")
    _require(result["complete"] is True and result["issues"] == [] and result["tolerance"] is None
             and result["numerical_tolerance"] == tolerance and result["metric"] == "inferred_target_vector_rmse",
             "Comparison settings or completion differ")
    _require(result["evaluation"]["fingerprint"] == eval_doc["fingerprint"]
             and result["evaluation"]["target_kind"] == TARGET_KIND, "Comparison evaluation identity differs")
    for role in models:
        _require(result[role]["digest"] == bundle_digests[role], "Comparison prediction identity differs")
    sessions = {r["session_id"]: r for r in result["sessions"]}
    _require(len(sessions) == len(result["sessions"]) and set(sessions) == set(denominators), "Comparison session inventory differs")
    checks = []
    for sid in sorted(sessions):
        row, n = sessions[sid], denominators[sid]
        _require(row["status"] == "valid" and row["issues"] == [] and row["regression"] is None
                 and row["n_expected"] == row["n_scored"] == n, "Comparison session eligibility differs")
        computed = {f"{role}_rmse": math.sqrt(math.fsum(terms[sid][role]) / n) for role in models}
        computed["delta"] = computed["candidate_rmse"] - computed["baseline_rmse"]
        for key, value in computed.items():
            _close(row[key], value, tolerance, f"{sid}: {key}")
        checks.append(dict(session_id=sid, n_expected=n, **computed))
    total = sum(denominators.values())
    pooled = {f"{role}_rmse": math.sqrt(math.fsum(v for sid in terms for v in terms[sid][role]) / total)
              for role in models}
    pooled["delta"] = pooled["candidate_rmse"] - pooled["baseline_rmse"]
    pooled["n_samples"] = total
    for key, value in pooled.items():
        _close(result["pooled"][key], value, tolerance, f"pooled: {key}")
    _require(result["excluded_counts"] == dict(evaluation=len(all_keys) - total, baseline=0, candidate=0),
             "Comparison excluded counts differ")
    paired_keys = set()
    for row in result["samples"]:
        key = row["session_id"], row["sample_id"]
        _require(key in scored_keys and key not in paired_keys, "Comparison paired sample inventory differs")
        paired_keys.add(key)
        target = target_rows[key]
        for field in ("timestamp", "target_vx", "target_vy"):
            _require(row[field] == target[field], "Comparison paired target differs")
        for role in models:
            p = supplied[role][key]
            _require(row[f"{role}_vx"] == p["predicted_vx"] and row[f"{role}_vy"] == p["predicted_vy"],
                     "Comparison paired prediction differs")
            error = math.hypot(p["predicted_vx"] - target["target_vx"], p["predicted_vy"] - target["target_vy"])
            _close(row[f"{role}_error"], error, tolerance, "Comparison paired error differs")
    _require(paired_keys == scored_keys, "Missing paired comparison samples")
    return dict(status="passed", protocol_sha256=protocol_hash,
        audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_files_verified=sum(len(b["files"]) for b in specs), training_rows=n_train,
        model_checks=model_checks, maximum_prediction_error=maximum_prediction_error,
        sessions=checks, pooled=pooled, evidence_files=list(evidence.values()),
        scope="Original file hashes, trial masks, retained targets, source-only preprocessing, saved ridge optimality, predictions and scores. No refit.",
        limitation="This audit verifies saved mathematical evidence, not when a human inspected labels or whether the historical participant would benefit from a different live decoder.")
