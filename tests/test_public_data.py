"""Synthetic preparation tests; no public recording is accessed here."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

from examples.public_recording.data import (
    _channel_axis,
    _make_edges,
    _normalize_channel,
    _rates_for_vectors,
    read_neural,
    read_targets,
)


HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HAS_H5PY = importlib.util.find_spec("h5py") is not None


def _config(**overrides):
    return {
        "max_seconds_per_session": 300.0,
        "samples_per_bin": 16,
        "max_sample_gap_seconds": 0.008000001,
        "minimum_complete_bins": 10,
        "channels": [f"M1 {index:03d}" for index in range(1, 97)],
        **overrides,
    }


class ChannelIdentityTests(unittest.TestCase):
    def test_channel_normalization_does_not_confuse_regions(self):
        self.assertEqual(_normalize_channel("M1 1"), "M1 001")
        self.assertEqual(_normalize_channel(" S1 006\x00"), "S1 006")
        for name in ["M1 000", "M1 -1", "M2 001", "M1 one"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                _normalize_channel(name)

    def test_spike_axis_must_be_unique(self):
        self.assertEqual(_channel_axis((3, 96), 96), 1)
        self.assertEqual(_channel_axis((96, 5), 96), 0)
        for shape in [(96, 96), (3, 95), (96,), (96, 0)]:
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                _channel_axis(shape, 96)


@unittest.skipUnless(HAS_NUMPY, "optional NumPy is unavailable")
class NumericPreparationTests(unittest.TestCase):
    def test_complete_bins_actual_edges_and_incomplete_tail(self):
        import numpy as np

        times = 20 + np.arange(164) * 0.004
        edges = _make_edges(times, _config())
        self.assertEqual(edges.prefix_stop, 164)
        self.assertEqual(edges.source_start, 20)
        np.testing.assert_array_equal(edges.indices, np.arange(11) * 16)
        np.testing.assert_array_equal(edges.absolute, times[edges.indices])
        self.assertFalse(edges.indices.flags.writeable)

    def test_cap_retains_endpoint_and_ignores_incomplete_final_bin(self):
        import numpy as np

        times = np.arange(200) / 250
        edges = _make_edges(times, _config(max_seconds_per_session=0.65))
        self.assertEqual(edges.prefix_stop, 163)
        self.assertEqual(edges.indices[-1], 160)
        self.assertLessEqual(edges.absolute[-1], 0.65)

    def test_invalid_timestamp_in_incomplete_tail_is_not_hidden(self):
        import numpy as np

        for bad_value in [float("nan"), 0.63, 0.7]:
            times = np.arange(164) / 250
            times[-1] = bad_value
            with self.subTest(bad_value=bad_value), self.assertRaises(ValueError):
                _make_edges(times, _config())

    def test_minimum_bins_and_gap_are_enforced(self):
        import numpy as np

        with self.assertRaisesRegex(ValueError, "complete bins"):
            _make_edges(np.arange(160) / 250, _config())
        times = np.arange(161) / 250
        times[80:] += 0.009
        with self.assertRaisesRegex(ValueError, "gap"):
            _make_edges(times, _config())

    def test_half_open_bins_sum_residual_sorted_and_duplicate_events(self):
        import numpy as np

        rates = _rates_for_vectors(
            [[-1, 0, 0.5, 1, 2], [0, 1, 1], []], [0, 1, 2]
        )
        # t=2 is excluded. Repeated events at t=1 each count in the second bin.
        np.testing.assert_array_equal(rates, [3, 3])
        np.testing.assert_allclose(_rates_for_vectors([[0, 0.5]], [0, 0.5, 2]), [2, 2 / 3])

    def test_spike_validity_covers_the_entire_vector(self):
        for vector in [[0.1, float("nan")], [0.1, 100, 90], [[1, 2], [3, 4]]]:
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                _rates_for_vectors([vector], [0, 1])


@unittest.skipUnless(HAS_NUMPY and HAS_H5PY, "optional NumPy/h5py are unavailable")
class MatlabInputTests(unittest.TestCase):
    def _write(self, path, *, transpose=False, include_targets=True, names=None):
        import h5py
        import numpy as np

        names = names or [f"M1 {index}" for index in range(96, 0, -1)] + ["S1 1"]
        times = 10 + np.arange(164) / 250
        with h5py.File(path, "w") as handle:
            handle.create_dataset("t", data=times.reshape(1, -1))
            refs = handle.create_group("#refs#")
            name_refs = []
            for index, name in enumerate(names):
                name_refs.append(refs.create_dataset(
                    f"name-{index}", data=np.array([ord(c) for c in name], dtype="uint16").reshape(-1, 1)
                ).ref)
            handle.create_dataset("chan_names", data=np.array(name_refs, dtype=h5py.ref_dtype).reshape(1, -1))
            empty = refs.create_dataset("empty", data=np.array([0, 0], dtype="uint64"))
            empty.attrs["MATLAB_empty"] = np.uint8(1)
            residual = refs.create_dataset("residual", data=np.array([[times[0], times[16]]]))
            sorted_unit = refs.create_dataset("sorted", data=np.array([[times[8]]]))
            cells = np.full((3, len(names)), empty.ref, dtype=h5py.ref_dtype)
            m1_one = next((i for i, name in enumerate(names) if _normalize_channel(name) == "M1 001"), None)
            if m1_one is not None:
                cells[0, m1_one] = residual.ref
                cells[1, m1_one] = sorted_unit.ref
            if any(name.startswith("S1") for name in names):
                # Invalid S1 spikes are deliberately irrelevant to M1 features.
                bad = refs.create_dataset("unused-s1", data=np.array([float("nan")]))
                cells[0, -1] = bad.ref
            handle.create_dataset("spikes", data=cells.T if transpose else cells)
            if include_targets:
                positions = np.column_stack((3 * times, -2 * times))
                handle.create_dataset("cursor_pos", data=positions if transpose else positions.T)
        return times

    def test_both_matlab_orientations_and_canonical_channel_order(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as directory:
            for transpose in [False, True]:
                path = Path(directory) / f"session-{transpose}.mat"
                times = self._write(path, transpose=transpose)
                neural = read_neural(path, _config())
                self.assertEqual(neural.rates.shape, (10, 96))
                self.assertEqual(neural.channel_names[0], "M1 001")
                np.testing.assert_allclose(neural.rates[:2, 0], [2 / 0.064, 1 / 0.064])
                np.testing.assert_array_equal(neural.rates[:, 1:], 0)
                np.testing.assert_allclose(neural.timestamps, times[neural.edge_indices[1:]] - times[0])
                self.assertEqual(neural.sample_ids, tuple(f"bin-{i:06d}" for i in range(10)))
                targets = read_targets(path, neural.edges)
                np.testing.assert_allclose(targets, np.tile([3, -2], (10, 1)), atol=1e-12)

    def test_neural_stage_requires_no_cursor_or_target_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "neural-only.mat"
            self._write(path, include_targets=False)
            neural = read_neural(path, _config())
            self.assertEqual(neural.rates.shape, (10, 96))

    def test_missing_and_duplicate_channel_names_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = [
                [f"M1 {i}" for i in range(1, 96)],
                [f"M1 {i}" for i in range(1, 96)] + ["M1 001"],
            ]
            for index, names in enumerate(cases):
                path = Path(directory) / f"bad-{index}.mat"
                self._write(path, names=names)
                with self.assertRaises(ValueError):
                    read_neural(path, _config())

    def test_all_selected_cursor_values_checked_not_only_bin_edges(self):
        import h5py

        with tempfile.TemporaryDirectory() as directory:
            for bad_index in [1, 163]:
                path = Path(directory) / f"bad-cursor-{bad_index}.mat"
                self._write(path)
                with h5py.File(path, "r+") as handle:
                    handle["cursor_pos"][0, bad_index] = float("nan")
                # The neural stage must remain independent of even an invalid
                # cursor dataset. Admission of labels belongs to the later stage.
                neural = read_neural(path, _config())
                with self.assertRaisesRegex(ValueError, "all selected cursor"):
                    read_targets(path, neural.edges)

    def test_timestamp_change_between_stages_is_rejected(self):
        import h5py

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.mat"
            self._write(path)
            neural = read_neural(path, _config())
            with h5py.File(path, "r+") as handle:
                handle["t"][0, 1] += 0.0001
            with self.assertRaisesRegex(ValueError, "timestamps changed"):
                read_targets(path, neural.edges)


if __name__ == "__main__":
    unittest.main()
