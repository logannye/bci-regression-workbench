"""Explicit MINDFUL T11 admission and trial-bounded neural history.

This example reads the released features. It does not claim that their source
signal filtering is causal. Target labels are loaded by a separate function.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from pathlib import Path
import hashlib

import numpy as np
from scipy.io import loadmat


@dataclass(frozen=True)
class NeuralBlock:
    rates: np.ndarray
    indices: np.ndarray
    trial_starts: np.ndarray
    reasons: tuple[str, ...]
    trials: int
    excluded_trials: int


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_block(path: Path, spec: dict) -> None:
    if set(spec['files']) != {'data.mat', 'task.mat', 'info.mat'}:
        raise ValueError('Expected frozen data, task, and info identities')
    for name, expected in spec['files'].items():
        file = path / name
        if file.is_symlink() or not file.is_file() or digest(file) != expected:
            raise ValueError(f"Frozen input checksum mismatch: day_{spec['day']}/{spec['block']}/{name}")


def _real(value, shape, name):
    raw = np.asarray(value)
    if raw.shape != shape or raw.dtype.kind not in 'iuf' or not np.isfinite(raw).all():
        raise ValueError(f'{name} must be finite real values with shape {shape}')
    return raw.astype(np.float64, copy=False)


def admit_neural(rates, task: dict, *, n_bins: int, n_channels=192, history_bins=4) -> NeuralBlock:
    if type(n_bins) is not int or n_bins < 1 or n_channels != 192 or history_bins != 4:
        raise ValueError('Expected a nonempty 192-channel block and four-bin common history')
    rates = _real(rates, (n_bins, n_channels), 'nctx')
    if (rates < 0).any():
        raise ValueError('nctx must be nonnegative')
    if task.get('name') != 'circleOfCircles' or task.get('nPointsPerBlock') != n_bins:
        raise ValueError('Task or bin count differs from the frozen T11 cursor task')
    bounds = np.atleast_2d(task.get('startStops'))
    if bounds.ndim != 2 or bounds.shape[1] != 2 or bounds.shape[0] < 1:
        raise ValueError('Trial bounds must be a nonempty Nx2 array')
    if bounds.dtype.kind not in 'iuf' or not np.isfinite(bounds).all() or not np.equal(bounds, np.floor(bounds)).all():
        raise ValueError('Trial bounds must be finite integers')
    if (bounds < 1).any() or (bounds > n_bins).any() or (bounds[:, 0] > bounds[:, 1]).any():
        raise ValueError('Trial bounds exceed the block or are reversed')
    bounds = bounds.astype(np.int64)
    if (bounds[1:, 0] <= bounds[:-1, 1]).any():
        raise ValueError('Trial bounds must be ordered and nonoverlapping')
    excluded = np.atleast_1d(task.get('excludeTrials'))
    if excluded.shape != (len(bounds),) or excluded.dtype.kind not in 'biuf' or not np.isin(excluded, [0, 1]).all():
        raise ValueError('excludeTrials must contain one boolean per trial')
    reasons = np.full(n_bins, 'outside-trial', dtype=object)
    starts = np.full(n_bins, -1, dtype=np.int64)
    for (first, last), exclude in zip(bounds, excluded):
        # MATLAB first:last is 1-based and inclusive at BOTH ends.
        start, stop = int(first) - 1, int(last)
        starts[start:stop] = start
        if exclude:
            reasons[start:stop] = 'source-excluded-trial'
        else:
            reasons[start:stop] = ''
            reasons[start:min(start + history_bins - 1, stop)] = 'history-warmup'
    indices = np.flatnonzero(reasons == '')
    if not len(indices):
        raise ValueError('Block contains no eligible samples under the frozen common mask')
    return NeuralBlock(rates, indices, starts, tuple(reasons), len(bounds), int(np.count_nonzero(excluded)))


def read_neural(path: Path, spec: dict, data: dict) -> NeuralBlock:
    """Read neural features and task mask only, never labels or online outputs."""
    neural = loadmat(path / 'data.mat', variable_names=['nctx'], simplify_cells=True)
    task = loadmat(path / 'task.mat', variable_names=['name', 'nPointsPerBlock', 'startStops', 'excludeTrials'], simplify_cells=True)
    result = admit_neural(neural['nctx'], task, n_bins=spec['n_bins'],
                         n_channels=data['n_channels'], history_bins=data['common_history_bins'])
    if 'expected_eligible_bins' in spec and len(result.indices) != spec['expected_eligible_bins']:
        raise ValueError('Eligible count differs from the frozen inspection')
    if 'expected_exclusions' in spec and dict(Counter(r for r in result.reasons if r)) != spec['expected_exclusions']:
        raise ValueError('Exclusion counts differ from the frozen inspection')
    return result


def read_targets(path: Path, spec: dict) -> np.ndarray:
    """Read stored inferred x/y displacement without rescaling or normalization."""
    labels = loadmat(path / 'data.mat', variable_names=['labels'], simplify_cells=True)['labels']
    return _real(labels, (spec['n_bins'], 2), 'inferred targets')


def trial_features(neural: NeuralBlock, history_bins: int) -> np.ndarray:
    if type(history_bins) is not int or history_bins not in (1, 4):
        raise ValueError('The frozen models use one or four bins')
    indices = neural.indices
    if (indices - (history_bins - 1) < neural.trial_starts[indices]).any():
        raise ValueError('History would cross a trial boundary')
    return neural.rates[indices[:, None] - np.arange(history_bins)[None, :]].reshape(len(indices), history_bins * 192)


def session_id(spec: dict) -> str:
    return f"T11-day-{spec['day']:04d}"


def block_id(spec: dict) -> str:
    return f"block-{int(spec['block'].split('_')[1]):02d}"


def sample_id(spec: dict, index: int) -> str:
    return f'{block_id(spec)}:bin-{index + 1:06d}'
