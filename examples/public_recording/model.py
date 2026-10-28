"""Frozen source-day ridge models for the isolated public-recording example.

This module performs no file access, split selection, binning, or model search.
The caller supplies each session's admitted 96-channel rates and the protocol's
common eligible row indices. Only ``fit_source_ridge`` accepts target labels.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import numbers

import numpy as np


def _array(value, name: str, dimensions: int) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or raw.ndim != dimensions:
        raise ValueError(f"{name} must be a {dimensions}D real numeric array")
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite float64 values")
    return result


def _positive_alpha(alpha) -> float:
    if isinstance(alpha, bool) or not isinstance(alpha, numbers.Real):
        raise ValueError("alpha must be a positive finite number")
    try:
        value = float(alpha)
    except (OverflowError, ValueError) as exc:
        raise ValueError("alpha must be a positive finite number") from exc
    if not np.isfinite(value) or value <= 0:
        raise ValueError("alpha must be a positive finite number")
    return value


def causal_features(rates, sample_indices, history_bins) -> np.ndarray:
    """Build current-to-older features within one session, without state.

    ``rates`` has shape (complete bins, 96). Each selected index identifies a
    just-completed bin. For four-bin history the corresponding row concatenates
    bins ``i, i-1, i-2, i-3``. The caller uses the same common indices for both
    models and calls this function separately for each recording file.
    """
    rates = _array(rates, "rates", 2)
    if rates.shape[0] == 0 or rates.shape[1] != 96:
        raise ValueError("rates must have shape (nonempty complete bins, 96)")
    if (rates < 0).any():
        raise ValueError("rates must be nonnegative")
    if isinstance(history_bins, bool) or not isinstance(history_bins, numbers.Integral):
        raise ValueError("history_bins must be 1 or 4")
    if history_bins not in (1, 4):
        raise ValueError("history_bins must be 1 or 4")
    indices = np.asarray(sample_indices)
    if indices.ndim != 1 or indices.dtype.kind not in "iu" or indices.size == 0:
        raise ValueError("sample_indices must be a nonempty 1D integer array")
    # Compare before conversion, so large unsigned indices cannot wrap negative.
    if (indices < history_bins - 1).any() or (indices >= rates.shape[0]).any():
        raise ValueError("sample_indices exceed this session or lack complete causal history")
    indices = indices.astype(np.int64, copy=False)
    if (np.diff(indices) <= 0).any():
        raise ValueError("sample_indices must be unique and in increasing order")
    history = indices[:, None] - np.arange(history_bins, dtype=np.int64)[None, :]
    return rates[history].reshape(len(indices), history_bins * 96)


@dataclass(frozen=True, eq=False)
class RidgeModel:
    """Source-fitted preprocessing and coefficients; arrays are copied/read-only."""

    feature_mean: np.ndarray
    feature_scale: np.ndarray
    weights: np.ndarray
    target_mean: np.ndarray
    alpha: float
    n_source_rows: int

    def __post_init__(self):
        mean = _array(self.feature_mean, "feature_mean", 1)
        scale = _array(self.feature_scale, "feature_scale", 1)
        weights = _array(self.weights, "weights", 2)
        target_mean = _array(self.target_mean, "target_mean", 1)
        features = len(mean)
        if features == 0 or scale.shape != (features,) or weights.shape != (features, 2):
            raise ValueError("Feature mean, scale, and two-output weights have incompatible shapes")
        if target_mean.shape != (2,) or (scale <= 0).any():
            raise ValueError("target_mean must have two components and feature_scale must be positive")
        if isinstance(self.n_source_rows, bool) or not isinstance(self.n_source_rows, numbers.Integral):
            raise ValueError("n_source_rows must be a positive integer")
        if self.n_source_rows < 1:
            raise ValueError("n_source_rows must be a positive integer")
        for name, value in (
            ("feature_mean", mean), ("feature_scale", scale),
            ("weights", weights), ("target_mean", target_mean),
        ):
            copied = np.array(value, dtype=np.float64, copy=True)
            copied.setflags(write=False)
            object.__setattr__(self, name, copied)
        object.__setattr__(self, "alpha", _positive_alpha(self.alpha))
        object.__setattr__(self, "n_source_rows", int(self.n_source_rows))

    def predict(self, X) -> np.ndarray:
        """Predict two velocities using the unchanged source-fitted parameters."""
        features = _array(X, "X", 2)
        if features.shape[1] != self.weights.shape[0]:
            raise ValueError("X feature count does not match the fixed model")
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                output = ((features - self.feature_mean) / self.feature_scale) @ self.weights + self.target_mean
        except FloatingPointError as exc:
            raise ValueError("Prediction exceeds finite float64 arithmetic") from exc
        if not np.isfinite(output).all():
            raise ValueError("Prediction exceeds finite float64 arithmetic")
        return output

    def to_dict(self) -> dict:
        """Return finite JSON-compatible parameters; caller supplies history metadata."""
        return {
            "schema_version": 1,
            "kind": "source_standardized_ridge",
            "feature_mean": self.feature_mean.tolist(),
            "feature_scale": self.feature_scale.tolist(),
            "weights": self.weights.tolist(),
            "target_mean": self.target_mean.tolist(),
            "alpha": self.alpha,
            "n_source_rows": self.n_source_rows,
        }

    @classmethod
    def from_dict(cls, payload) -> RidgeModel:
        """Restore an artifact without fitting or changing its normalization."""
        fields = {"schema_version", "kind", "feature_mean", "feature_scale", "weights",
                  "target_mean", "alpha", "n_source_rows"}
        if not isinstance(payload, Mapping) or set(payload) != fields:
            raise ValueError("Malformed ridge artifact fields")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ValueError("Unsupported ridge artifact schema")
        if payload["kind"] != "source_standardized_ridge":
            raise ValueError("Unsupported ridge artifact kind")
        return cls(**{name: payload[name] for name in fields - {"schema_version", "kind"}})


def fit_source_ridge(X, Y, alpha=1.0) -> RidgeModel:
    """Fit once on common eligible source rows.

    Minimize ``sum(||Y_i - intercept - Z_i W||^2) / N + alpha*sum(W^2)``.
    Z uses source-column means and population standard deviations (ddof=0),
    with exactly zero standard deviations replaced by one. Target centering
    leaves the intercept unpenalized. No randomization or parameter search.
    """
    features = _array(X, "X", 2)
    targets = _array(Y, "Y", 2)
    if features.shape[0] == 0 or features.shape[1] == 0:
        raise ValueError("Source features must have nonempty rows and columns")
    if targets.shape != (features.shape[0], 2):
        raise ValueError("Y must have shape (source rows, 2)")
    penalty = _positive_alpha(alpha)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            feature_mean = features.mean(axis=0)
            feature_scale = features.std(axis=0, ddof=0)
            feature_scale = np.where(feature_scale == 0, 1.0, feature_scale)
            target_mean = targets.mean(axis=0)
            standardized = (features - feature_mean) / feature_scale
            centered_targets = targets - target_mean
            gram = standardized.T @ standardized / features.shape[0]
            gram += penalty * np.eye(features.shape[1], dtype=np.float64)
            rhs = standardized.T @ centered_targets / features.shape[0]
            weights = np.linalg.solve(gram, rhs)
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise ValueError("Source ridge fit failed finite deterministic arithmetic") from exc
    return RidgeModel(feature_mean, feature_scale, weights, target_mean, penalty, features.shape[0])


def predict(model: RidgeModel, X) -> np.ndarray:
    """Prediction-only convenience function; deliberately has no label argument."""
    if not isinstance(model, RidgeModel):
        raise TypeError("model must be a fixed RidgeModel")
    return model.predict(X)
