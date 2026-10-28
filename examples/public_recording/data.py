"""Frozen-demo input preparation with separate neural and target read stages.

Only ``read_targets`` accesses cursor positions. ``read_neural`` reads timestamps,
channel names and referenced spike vectors, and can run against a file that has
no cursor dataset. The caller controls the prediction-before-target boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping


@dataclass(frozen=True)
class BinEdges:
    indices: Any
    absolute: Any
    prefix_stop: int
    source_start: float
    prefix_times: Any


@dataclass(frozen=True)
class NeuralData:
    rates: Any
    edges: BinEdges
    timestamps: Any
    channel_names: tuple[str, ...]
    sample_ids: tuple[str, ...]

    @property
    def edge_indices(self):
        return self.edges.indices

    @property
    def absolute_edges(self):
        return self.edges.absolute

    @property
    def source_start(self):
        return self.edges.source_start

    @property
    def prefix_stop(self):
        return self.edges.prefix_stop


def _numpy():
    import numpy as np

    return np


def _readonly(values, dtype=None):
    np = _numpy()
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _vector(values, name: str):
    np = _numpy()
    array = np.asarray(values)
    if array.dtype.kind not in "fiu":
        raise ValueError(f"{name} must be a real numeric vector")
    if array.ndim > 2 or (array.ndim == 2 and all(size > 1 for size in array.shape)):
        raise ValueError(f"{name} must be a vector, not a matrix")
    return np.asarray(array, dtype=np.float64).reshape(-1)


def _make_edges(timestamps, config: Mapping[str, Any]) -> BinEdges:
    """Admit the entire selected prefix, including its incomplete trailing bin."""
    np = _numpy()
    times = _vector(timestamps, "t")
    if not len(times) or not np.isfinite(times[0]):
        raise ValueError("t must have a finite first timestamp")
    source_start = float(times[0])
    seconds = float(config["max_seconds_per_session"])
    max_gap = float(config["max_sample_gap_seconds"])
    width = config["samples_per_bin"]
    minimum = config["minimum_complete_bins"]
    if (
        not np.isfinite(seconds) or seconds <= 0
        or not np.isfinite(max_gap) or max_gap <= 0
        or type(width) is not int or width < 1
        or type(minimum) is not int or minimum < 1
    ):
        raise ValueError("invalid frozen binning configuration")
    cutoff = source_start + seconds
    if not np.isfinite(cutoff):
        raise ValueError("selected time cutoff is not finite")
    # Do not inspect position values to decide admission or selection. Stop at
    # the first timestamp beyond the cap; otherwise the selected prefix ends
    # at the file's final timestamp. No sortedness assumption precedes checks.
    beyond = np.flatnonzero(times > cutoff)
    prefix_stop = int(beyond[0]) if len(beyond) else len(times)
    prefix = times[:prefix_stop]
    if not np.all(np.isfinite(prefix)):
        raise ValueError("selected prefix timestamps must be finite")
    differences = np.diff(prefix)
    if np.any(differences <= 0):
        raise ValueError("selected prefix timestamps must be strictly increasing")
    if np.any(differences > max_gap):
        raise ValueError("selected prefix timestamp gap exceeds the frozen limit")
    count = (len(prefix) - 1) // width
    if count < minimum:
        raise ValueError(f"need at least {minimum} complete bins; found {count}")
    indices = np.arange(count + 1, dtype=np.int64) * width
    return BinEdges(
        indices=_readonly(indices),
        absolute=_readonly(prefix[indices]),
        prefix_stop=prefix_stop,
        source_start=source_start,
        prefix_times=_readonly(prefix),
    )


def _normalize_channel(name: str) -> str:
    name = name.strip(" \t\r\n\x00")
    match = re.fullmatch(r"(M1|S1)\s*([0-9]+)", name)
    if match is None or int(match.group(2)) < 1:
        raise ValueError(f"unsupported channel identifier: {name!r}")
    return f"{match.group(1)} {int(match.group(2)):03d}"


def _channel_axis(shape, channel_count: int) -> int:
    if len(shape) != 2 or min(shape) < 1:
        raise ValueError("spikes must be a nonempty two-dimensional MATLAB cell array")
    axes = [axis for axis, length in enumerate(shape) if length == channel_count]
    if len(axes) != 1:
        raise ValueError("spike cell orientation must have one unique channel-count axis")
    return axes[0]


def _rates_for_vectors(vectors, absolute_edges):
    """Count every event, including repeated timestamps, in [left, right)."""
    np = _numpy()
    edges = _vector(absolute_edges, "absolute edges")
    durations = np.diff(edges)
    if len(edges) < 2 or not np.all(np.isfinite(edges)) or np.any(durations <= 0):
        raise ValueError("bin edges must be finite and strictly increasing")
    counts = np.zeros(len(durations), dtype=np.int64)
    for values in vectors:
        vector = _vector(values, "spike timestamps")
        if not np.all(np.isfinite(vector)) or np.any(np.diff(vector) < 0):
            raise ValueError("spike timestamps must be finite and nondecreasing")
        counts += np.diff(np.searchsorted(vector, edges, side="left"))
    return counts.astype(np.float64) / durations


def _decode_channel(dataset) -> str:
    np = _numpy()
    values = np.asarray(dataset[()])
    if values.dtype.kind in "ui":
        chars = _vector(values, "channel name")
        try:
            text = "".join(chr(int(value)) for value in chars)
        except (ValueError, OverflowError) as exc:
            raise ValueError("channel name contains invalid character codes") from exc
    elif values.dtype.kind in "SU":
        parts = values.reshape(-1).tolist()
        text = "".join(part.decode("utf-8") if isinstance(part, bytes) else part for part in parts)
    else:
        raise ValueError("channel names must reference MATLAB character arrays")
    return _normalize_channel(text)


def _read_channel_names(handle, h5py) -> tuple[str, ...]:
    np = _numpy()
    dataset = handle["chan_names"]
    if h5py.check_dtype(ref=dataset.dtype) is None:
        raise ValueError("chan_names must be a MATLAB reference cell array")
    references = np.asarray(dataset[()])
    if references.ndim > 2 or (references.ndim == 2 and all(n > 1 for n in references.shape)):
        raise ValueError("chan_names must have one vector axis")
    names = []
    for reference in references.reshape(-1):
        if not reference:
            raise ValueError("missing channel name reference")
        names.append(_decode_channel(handle[reference]))
    if len(set(names)) != len(names):
        raise ValueError("duplicate canonical channel names")
    return tuple(names)


def _read_spike_vector(handle, reference):
    np = _numpy()
    if not reference:
        # A null cell is an explicit empty unit, not a missing named channel.
        return np.empty(0, dtype=np.float64)
    dataset = handle[reference]
    marker = np.asarray(dataset.attrs.get("MATLAB_empty", 0)).reshape(-1)
    if len(marker) != 1 or marker[0] not in (0, 1):
        raise ValueError("invalid MATLAB_empty marker")
    if marker[0] == 1:
        # MATLAB stores empty-array dimensions in the dataset itself. They are
        # not spike timestamps and must never be counted as events at t=0.
        return np.empty(0, dtype=np.float64)
    return _vector(dataset[()], "spike timestamps")


def read_neural(path: str | Path, config: Mapping[str, Any]) -> NeuralData:
    """Load neural rates only, using the frozen protocol's ``data`` dictionary.

    Neither cursor_pos nor target_pos is opened. All 96 M1 channel names must
    be present exactly once. S1 channels are identified but their spikes are
    not used. Unit cells, including the residual first unit, are summed.
    """
    import h5py

    np = _numpy()
    required = tuple(config["channels"])
    canonical = tuple(f"M1 {index:03d}" for index in range(1, 97))
    if required != canonical:
        raise ValueError("frozen feature order must be exactly M1 001 through M1 096")
    with h5py.File(path, "r") as handle:
        edges = _make_edges(handle["t"][()], config)
        names = _read_channel_names(handle, h5py)
        m1_names = {name for name in names if name.startswith("M1 ")}
        if m1_names != set(required):
            missing = sorted(set(required) - m1_names)
            extra = sorted(m1_names - set(required))
            raise ValueError(f"M1 channel identity mismatch; missing={missing}, extra={extra}")
        cells = handle["spikes"]
        if h5py.check_dtype(ref=cells.dtype) is None:
            raise ValueError("spikes must contain MATLAB dataset references")
        axis = _channel_axis(cells.shape, len(names))
        name_to_index = {name: index for index, name in enumerate(names)}
        rates = np.empty((len(edges.indices) - 1, len(required)), dtype=np.float64)
        for output_column, name in enumerate(required):
            source_column = name_to_index[name]
            references = cells[source_column, :] if axis == 0 else cells[:, source_column]
            vectors = (_read_spike_vector(handle, ref) for ref in references)
            rates[:, output_column] = _rates_for_vectors(vectors, edges.absolute)
    count = len(rates)
    return NeuralData(
        rates=_readonly(rates),
        edges=edges,
        timestamps=_readonly(edges.absolute[1:] - edges.absolute[0]),
        channel_names=required,
        sample_ids=tuple(f"bin-{index:06d}" for index in range(count)),
    )


def read_targets(path: str | Path, edges: BinEdges):
    """Read measured positions after predictions are saved; return bin velocities.

    The caller must pass the BinEdges retained by read_neural. Validate every
    cursor sample in the selected prefix, including the incomplete tail, then
    use only the fixed edge positions. No target_pos access occurs.
    """
    import h5py

    np = _numpy()
    if not isinstance(edges, BinEdges):
        raise TypeError("edges must be the BinEdges returned by read_neural")
    with h5py.File(path, "r") as handle:
        times = _vector(handle["t"][()], "t")
        if len(times) < edges.prefix_stop or not np.array_equal(
            times[:edges.prefix_stop], edges.prefix_times
        ):
            raise ValueError("timestamps changed between neural and target stages")
        positions = handle["cursor_pos"]
        if positions.ndim != 2:
            raise ValueError("cursor_pos must be an Nx2 or 2xN array")
        if positions.shape == (len(times), 2) and len(times) != 2:
            prefix = positions[:edges.prefix_stop, :]
        elif positions.shape == (2, len(times)) and len(times) != 2:
            prefix = positions[:, :edges.prefix_stop].T
        else:
            raise ValueError("cursor_pos orientation does not match t and two coordinates")
        if prefix.dtype.kind not in "fiu":
            raise ValueError("selected cursor positions must be real numeric values")
        prefix = np.asarray(prefix, dtype=np.float64)
        if not np.all(np.isfinite(prefix)):
            raise ValueError("all selected cursor positions must be finite")
        if not np.array_equal(times[edges.indices], edges.absolute):
            raise ValueError("target bin-edge timestamps do not match neural bin edges")
        velocities = np.diff(prefix[edges.indices], axis=0) / np.diff(edges.absolute)[:, None]
        if not np.all(np.isfinite(velocities)):
            raise ValueError("derived target velocities must be finite")
        return _readonly(velocities)
