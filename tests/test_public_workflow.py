"""Synthetic checks for the producer's prediction-before-label boundary."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    import h5py
    import numpy as np
    from examples.public_recording import run as producer
except ImportError:
    producer = None


@unittest.skipIf(producer is None, "optional public-demo NumPy/h5py environment is unavailable")
class PublicWorkflowTests(unittest.TestCase):
    def test_all_predictions_are_saved_before_any_evaluation_positions_are_opened(self):
        plan = json.loads(producer.PROTOCOL.read_text())
        selected = plan["files"]
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            rates = np.tile(np.arange(10, dtype=float)[:, None], (1, 96))
            neural = SimpleNamespace(rates=rates, edge_indices=np.arange(11)*16,
                absolute_edges=np.arange(11)*.064, timestamps=np.arange(1, 11)*.064,
                sample_ids=tuple(f"bin-{i:06d}" for i in range(10)), edges=object())

            def fake_neural(path, config):
                calls.append(("neural", path.name))
                return neural

            def fake_targets(path, edges):
                calls.append(("targets", path.name))
                if path.name != selected[0]["name"]:
                    ready = json.loads((output / "predictions-ready.json").read_text())
                    self.assertEqual(len(ready["predictions"]), 6)
                    for spec in selected[1:]:
                        for role in ("baseline", "candidate"):
                            file = output / "predictions" / role / f"{spec['session_id']}.npz"
                            self.assertEqual(producer.digest(file), ready["predictions"][f"{role}/{spec['session_id']}"])
                    for role in ("baseline", "candidate"):
                        self.assertTrue((output / "models" / f"{role}.json").is_file())
                return np.column_stack((np.arange(10)*2.0, np.arange(10)*-1.0))

            with patch.object(producer, "fetch_input", side_effect=lambda directory, spec: {**spec, "sha256": "synthetic"}), \
                 patch.object(producer, "read_neural", side_effect=fake_neural), \
                 patch.object(producer, "read_targets", side_effect=fake_targets), \
                 patch.object(producer, "audit_run", return_value={"status": "passed", "scope": "mock for synthetic order test"}), \
                 patch.object(producer.platform, "python_version_tuple", return_value=("3", "11", "0")), \
                 patch.object(producer.np, "__version__", "2.2.6"), \
                 patch.object(producer.h5py, "__version__", "3.14.0"), \
                 patch.dict(producer.os.environ, {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}):
                result = producer.run(Path(directory) / "inputs", output)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["training_rows"], 7)
            self.assertEqual(len(result["sessions"]), 3)
            first_eval_label = calls.index(("targets", selected[1]["name"]))
            self.assertTrue(all(calls.index(("neural", spec["name"])) < first_eval_label for spec in selected[1:]))

    def test_changed_frozen_protocol_is_refused_before_output_or_input_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changed = root / "changed.json"
            changed.write_text('{}\n')
            with patch.object(producer, "PROTOCOL", changed), patch.object(producer, "fetch_input") as fetch:
                with self.assertRaisesRegex(ValueError, "Frozen protocol"):
                    producer.run(root / "inputs", root / "output")
                fetch.assert_not_called()
                self.assertFalse((root / "output").exists())
