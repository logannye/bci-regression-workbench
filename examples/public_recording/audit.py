"""Independently verify a frozen public-demo run without fitting any model.

This module intentionally does not import the producer, recording loader, or
comparator. It checks retained arrays; raw-recording extraction is a separate
source-code and checksum responsibility.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import re

import numpy as np


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _array(value, shape, name):
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: not a numeric array") from exc
    _require(result.shape == shape, f"{name}: expected shape {shape}, got {result.shape}")
    _require(np.isfinite(result).all(), f"{name}: contains nonfinite values")
    return result


def _close(actual, expected, tolerance, name):
    _require(actual.shape == expected.shape, f"{name}: shape mismatch")
    error = float(np.max(np.abs(actual - expected))) if actual.size else 0.0
    _require(math.isfinite(error) and error <= tolerance,
             f"{name}: absolute difference {error} exceeds {tolerance}")
    return error


def _indices(values, expected, name):
    values = np.asarray(values)
    _require(values.dtype.kind in "iu" and values.shape == expected.shape,
             f"{name}: expected an integer vector with shape {expected.shape}")
    _require(np.array_equal(values, expected), f"{name}: unexpected sample identities")
    return values


def _design(rates, indices, history):
    # Each block is current, then successively older completed neural bins.
    return np.concatenate([rates[indices - lag] for lag in range(history)], axis=1)


def _rmse(predictions, targets):
    # Independent arithmetic: sum squared 2D residuals, divide by rows, then root.
    terms = [(float(p[0]) - float(y[0])) ** 2 + (float(p[1]) - float(y[1])) ** 2
             for p, y in zip(predictions, targets)]
    _require(bool(terms), "Cannot score an empty sample set")
    return math.sqrt(math.fsum(terms) / len(terms))


def audit_run(root) -> dict:
    """Verify retained feature/model/prediction evidence and recompute its scores.

    Returns an audit receipt or raises ValueError on a failed invariant. No model
    fitting, tuning, data downloading, or artifact writing occurs here.
    """
    root = Path(root)
    evidence = {}

    def read_bytes(relative):
        data = (root / relative).read_bytes()
        evidence[relative] = {"path": relative, "size_bytes": len(data),
                              "sha256": hashlib.sha256(data).hexdigest()}
        return data

    def read_json(relative):
        def invalid_constant(value):
            raise ValueError(f"{relative}: nonstandard JSON constant {value}")
        return json.loads(read_bytes(relative), parse_constant=invalid_constant)

    def read_npz(relative):
        with np.load(io.BytesIO(read_bytes(relative)), allow_pickle=False) as source:
            return {key: source[key].copy() for key in source.files}

    def bundle(relative, kind, digest_key):
        doc = read_json(relative)
        _require(doc.get("format_version") == 1 and doc.get("kind") == kind,
                 f"{relative}: unsupported bundle format")
        payload = doc.get("payload")
        _require(isinstance(payload, dict), f"{relative}: missing payload")
        _require(_canonical_digest(payload) == doc.get(digest_key),
                 f"{relative}: content identity mismatch")
        return doc

    protocol = read_json("protocol.json")
    protocol_digest = evidence["protocol.json"]["sha256"]
    tolerance = float(protocol["comparison"]["numerical_tolerance"])
    _require(math.isfinite(tolerance) and tolerance >= 0, "Invalid numerical tolerance")
    _require(protocol["comparison"]["reporting_tolerance"] is None,
             "This protocol requires descriptive comparisons without regression flags")
    config = protocol["data"]
    channels = config["channels"]
    _require(len(channels) == 96 and len(set(channels)) == 96, "Expected 96 unique channels")
    warmup = config["common_warmup_bins"]
    source_files = [row for row in protocol["files"] if row["role"] == "train"]
    evaluation_files = [row for row in protocol["files"] if row["role"] == "evaluation"]
    _require(len(source_files) == 1 and len(evaluation_files) == 3,
             "Expected one source and all three frozen evaluation sessions")
    source_id = source_files[0]["session_id"]

    inputs = read_json("inputs.json")
    _require(isinstance(inputs, list) and len(inputs) == len(protocol["files"]),
             "Input receipt does not contain every selected file")
    by_name = {entry["name"]: entry for entry in inputs}
    _require(len(by_name) == len(inputs), "Input receipt contains duplicate files")
    _require(set(by_name) == {entry["name"] for entry in protocol["files"]},
             "Input receipt differs from the frozen selection")
    for frozen in protocol["files"]:
        observed = by_name[frozen["name"]]
        for key in ("session_id", "role", "md5", "size_bytes"):
            _require(observed.get(key) == frozen[key], f"Input receipt mismatch: {frozen['name']} {key}")
        _require(re.fullmatch(r"[0-9a-f]{64}", observed.get("sha256", "")) is not None,
                 f"Missing SHA-256 identity for {frozen['name']}")

    source = read_npz("source-training.npz")
    source_rates = np.asarray(source["rates"])
    _require(source_rates.ndim == 2, "Source rates must be a matrix")
    source_rates = _array(source_rates, (source_rates.shape[0], 96), "source rates")
    _require((source_rates >= 0).all(), "Source rates must be nonnegative")
    n_source = len(source_rates)
    _require(n_source >= config["minimum_complete_bins"], "Insufficient source bins")
    source_targets = _array(source["targets"], (n_source, 2), "source targets")
    source_indices = _indices(source["sample_indices"], np.arange(warmup, n_source), "source sample indices")
    selected_targets = source_targets[source_indices]

    models, model_checks = {}, {}
    for label in ("baseline", "candidate"):
        snapshot = read_json(f"models/{label}.json")
        declared = protocol["models"][label]
        _require(snapshot["model_id"] == declared["id"], f"{label}: model ID mismatch")
        _require(snapshot["history_bins"] == declared["history_bins"], f"{label}: history mismatch")
        _require(snapshot["source_session_id"] == source_id, f"{label}: wrong source session")
        _require(snapshot["protocol_sha256"] == protocol_digest, f"{label}: protocol identity mismatch")
        history = snapshot["history_bins"]
        _require(type(history) is int and 1 <= history <= warmup + 1, f"{label}: invalid history")
        model = snapshot["model"]
        width = 96 * history
        mean = _array(model["feature_mean"], (width,), f"{label} feature mean")
        scale = _array(model["feature_scale"], (width,), f"{label} feature scale")
        weights = _array(model["weights"], (width, 2), f"{label} weights")
        target_mean = _array(model["target_mean"], (2,), f"{label} target mean")
        alpha = float(model["alpha"])
        _require(alpha == protocol["models"]["ridge_lambda"], f"{label}: ridge penalty mismatch")
        _require(model["n_source_rows"] == len(source_indices), f"{label}: training denominator mismatch")
        raw = _design(source_rates, source_indices, history)
        expected_mean = raw.mean(axis=0)
        expected_scale = raw.std(axis=0, ddof=0)
        expected_scale[expected_scale == 0] = 1.0
        mean_error = _close(mean, expected_mean, tolerance, f"{label} source-only mean")
        scale_error = _close(scale, expected_scale, tolerance, f"{label} source-only scale")
        _require((scale > 0).all(), f"{label}: feature scale must be positive")
        target_error = _close(target_mean, selected_targets.mean(axis=0), tolerance,
                              f"{label} source-only target mean")
        standardized = (raw - mean) / scale
        centered_targets = selected_targets - target_mean
        rhs = standardized.T @ centered_targets / len(source_indices)
        residual = standardized.T @ (standardized @ weights - centered_targets) / len(source_indices) + alpha * weights
        residual_size = float(np.max(np.abs(residual))) / max(1.0, float(np.max(np.abs(rhs))))
        _require(math.isfinite(residual_size) and residual_size <= 1e-9,
                 f"{label}: normalized ridge optimality residual {residual_size} exceeds 1e-9")
        models[label] = (history, mean, scale, weights, target_mean)
        model_checks[label] = {"n_training_rows": len(source_indices),
            "feature_mean_max_abs_error": mean_error, "feature_scale_max_abs_error": scale_error,
            "target_mean_max_abs_error": target_error, "normalized_optimality_residual": residual_size}

    evaluation_doc = bundle("comparison/evaluation.json", "evaluation", "fingerprint")
    evaluation = evaluation_doc["payload"]
    for key in ("units", "coordinates", "horizon_ms"):
        _require(evaluation[key] == config[key], f"Evaluation {key} differs from protocol")
    target_rows = {}
    for row in evaluation["records"]:
        key = (row["session_id"], row["sample_id"])
        _require(key not in target_rows, f"Duplicate evaluation key: {key}")
        target_rows[key] = row
    supplied = {}
    for label in ("baseline", "candidate"):
        doc = bundle(f"comparison/{label}.json", "predictions", "digest")
        payload = doc["payload"]
        _require(payload["run_id"] == protocol["models"][label]["id"], f"{label}: bound run ID mismatch")
        _require(payload["evaluation_fingerprint"] == evaluation_doc["fingerprint"],
                 f"{label}: bound evaluation identity mismatch")
        for key in ("units", "coordinates", "horizon_ms"):
            _require(payload[key] == evaluation[key], f"{label}: bound {key} mismatch")
        rows = {}
        for row in payload["records"]:
            key = (row["session_id"], row["sample_id"])
            _require(key not in rows, f"{label}: duplicate bound prediction key")
            rows[key] = row
        supplied[label] = rows

    expected_all_keys, expected_scored_keys = set(), set()
    session_checks, pooled_predictions, pooled_targets = [], {"baseline": [], "candidate": []}, []
    for entry in evaluation_files:
        sid = entry["session_id"]
        features = read_npz(f"features/{sid}.npz")
        rates = np.asarray(features["rates"])
        _require(rates.ndim == 2, f"{sid}: rates must be a matrix")
        n_bins = len(rates)
        rates = _array(rates, (n_bins, 96), f"{sid} rates")
        _require((rates >= 0).all() and n_bins >= config["minimum_complete_bins"],
                 f"{sid}: invalid rate values or bin count")
        indices = _indices(features["sample_indices"], np.arange(warmup, n_bins), f"{sid} sample indices")
        _indices(features["edge_indices"], np.arange(n_bins + 1) * config["samples_per_bin"], f"{sid} edge indices")
        edges = _array(features["absolute_edges"], (n_bins + 1,), f"{sid} bin edges")
        _require((np.diff(edges) > 0).all(), f"{sid}: bin edges must increase")
        _require(edges[-1] - edges[0] <= config["max_seconds_per_session"], f"{sid}: exceeds selected duration")
        timestamps = _array(features["timestamps"], (n_bins,), f"{sid} timestamps")
        _close(timestamps, edges[1:] - edges[0], tolerance, f"{sid} relative timestamps")
        target_values = []
        for index in range(n_bins):
            key = (sid, f"bin-{index:06d}")
            expected_all_keys.add(key)
            _require(key in target_rows, f"Missing evaluation key: {key}")
            row = target_rows[key]
            _require(row["timestamp"] == float(timestamps[index]), f"{sid}: target timestamp mismatch")
            expected_eligible = index >= warmup
            _require(type(row["eligible"]) is bool and row["eligible"] == expected_eligible,
                     f"{sid}: eligibility differs from frozen warmup")
            _require(row["exclusion_reason"] == ("" if expected_eligible else "causal-history warmup"),
                     f"{sid}: exclusion reason mismatch")
            target = _array([row["target_vx"], row["target_vy"]], (2,), f"{key} target")
            if expected_eligible:
                expected_scored_keys.add(key)
                target_values.append(target)
        targets = np.asarray(target_values)
        pooled_targets.extend(targets.tolist())
        scores, errors = {}, {}
        for label in ("baseline", "candidate"):
            retained = read_npz(f"predictions/{label}/{sid}.npz")
            _indices(retained["sample_indices"], indices, f"{label}/{sid} prediction indices")
            predictions = _array(retained["predicted_velocity"], (len(indices), 2), f"{label}/{sid} predictions")
            history, mean, scale, weights, target_mean = models[label]
            reconstructed = ((_design(rates, indices, history) - mean) / scale) @ weights + target_mean
            errors[label] = _close(predictions, reconstructed, tolerance, f"{label}/{sid} reconstructed predictions")
            for index, prediction in zip(indices, predictions):
                key = (sid, f"bin-{index:06d}")
                _require(key in supplied[label], f"{label}: missing bound prediction {key}")
                row = supplied[label][key]
                bound = _array([row["predicted_vx"], row["predicted_vy"]], (2,), f"{label}/{key} bound prediction")
                _require(np.array_equal(bound, prediction), f"{label}/{key}: bound output changed after retention")
            scores[label] = _rmse(predictions, targets)
            pooled_predictions[label].extend(predictions.tolist())
        session_checks.append({"session_id": sid, "n_expected": len(indices),
            "baseline_rmse": scores["baseline"], "candidate_rmse": scores["candidate"],
            "delta": scores["candidate"] - scores["baseline"], "prediction_max_abs_error": errors})
    _require(set(target_rows) == expected_all_keys, "Unexpected or missing evaluation rows")
    for label in supplied:
        _require(set(supplied[label]) == expected_scored_keys, f"{label}: bound output coverage differs")

    comparison = read_json("comparison/comparison.json")
    _require(comparison["complete"] is True and comparison["issues"] == [], "Comparison is incomplete")
    _require(comparison["tolerance"] is None and comparison["numerical_tolerance"] == tolerance,
             "Comparison tolerances differ from protocol")
    saved_sessions = {row["session_id"]: row for row in comparison["sessions"]}
    _require(len(saved_sessions) == 3 and len(comparison["sessions"]) == 3,
             "Comparison does not retain all three sessions")
    for check in session_checks:
        sid = check["session_id"]
        _require(sid in saved_sessions, f"Missing comparison session: {sid}")
        saved = saved_sessions[sid]
        _require(saved["status"] == "valid" and saved["issues"] == [] and saved["regression"] is None,
                 f"{sid}: unexpected session validity or categorical claim")
        _require(saved["n_expected"] == saved["n_scored"] == check["n_expected"], f"{sid}: changed scoring denominator")
        for field in ("baseline_rmse", "candidate_rmse", "delta"):
            _close(np.asarray([saved[field]], dtype=float), np.asarray([check[field]]), tolerance, f"{sid} {field}")
    pooled = {f"{label}_rmse": _rmse(pooled_predictions[label], pooled_targets) for label in supplied}
    pooled["delta"] = pooled["candidate_rmse"] - pooled["baseline_rmse"]
    pooled["n_samples"] = len(pooled_targets)
    _require(isinstance(comparison["pooled"], dict), "Missing pooled comparison")
    _require(comparison["pooled"]["n_samples"] == pooled["n_samples"], "Pooled denominator mismatch")
    for field in ("baseline_rmse", "candidate_rmse", "delta"):
        _close(np.asarray([comparison["pooled"][field]], dtype=float), np.asarray([pooled[field]]), tolerance, f"pooled {field}")

    return {"status": "passed", "protocol_sha256": protocol_digest,
        "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "normal_equation_residual_tolerance": 1e-9, "absolute_numerical_tolerance": tolerance,
        "model_checks": model_checks, "sessions": session_checks, "pooled": pooled,
        "evidence_files": [evidence[key] for key in sorted(evidence)],
        "scope": "Retained-array prediction reconstruction and independent scoring; no refit or raw-recording extraction verification."}
