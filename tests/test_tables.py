"""Verify the table boundary cannot silently alter or ambiguously map rows."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

from bci_regression.tables import load_parquet, table_records


class TableRecordsTests(unittest.TestCase):
    def test_records_preserve_order_values_and_input(self):
        rows = [
            {"session_id": "b", "sample_id": "2", "predicted_vx": None},
            {"session_id": "a", "sample_id": "1", "predicted_vx": 4.0},
        ]
        result = table_records(iter(rows))
        self.assertEqual(result, rows)
        self.assertIsNot(result[0], rows[0])
        result[0]["sample_id"] = "changed"
        self.assertEqual(rows[0]["sample_id"], "2")

    def test_partial_canonical_to_source_mapping_preserves_other_fields(self):
        rows = [{"recording": "s", "sample_id": "x", "vx": 2, "note": "keep"}]
        result = table_records(
            rows, {"session_id": "recording", "predicted_vx": "vx"}
        )
        self.assertEqual(
            result,
            [{"session_id": "s", "sample_id": "x", "predicted_vx": 2, "note": "keep"}],
        )
        self.assertIn("recording", rows[0])

    def test_identity_mapping_is_valid(self):
        self.assertEqual(
            table_records([{"sample_id": "a"}], {"sample_id": "sample_id"}),
            [{"sample_id": "a"}],
        )

    def test_missing_source_is_not_filled(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            table_records([{"sample_id": "a"}], {"session_id": "recording"})

    def test_existing_canonical_name_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError, "collides"):
            table_records(
                [{"session_id": "original", "recording": "other"}],
                {"session_id": "recording"},
            )

    def test_one_source_cannot_stand_in_for_two_fields(self):
        with self.assertRaisesRegex(ValueError, "multiple"):
            table_records([{"id": "x"}], {"session_id": "id", "sample_id": "id"})

    def test_invalid_mapping_names_and_types(self):
        for mapping in [{"": "id"}, {"sample_id": ""}, {"sample_id": 3}]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                table_records([{"id": "x"}], mapping)
        with self.assertRaises(TypeError):
            table_records([{"id": "x"}], ["id"])

    def test_non_mapping_rows_and_single_mapping_are_rejected(self):
        for value in [{"sample_id": "x"}, "text", [["x", 1]], 42]:
            with self.subTest(value=value), self.assertRaises(TypeError):
                table_records(value)

    def test_schema_less_empty_mapping_cannot_claim_validation(self):
        self.assertEqual(table_records([]), [])
        with self.assertRaisesRegex(ValueError, "empty"):
            table_records([], {"session_id": "recording"})

    def test_polars_style_conversion(self):
        class Frame:
            columns = ["recording", "sample_id"]

            def to_dicts(self):
                return [{"recording": "s", "sample_id": "1"}]

        self.assertEqual(
            table_records(Frame(), {"session_id": "recording"}),
            [{"session_id": "s", "sample_id": "1"}],
        )

    def test_arrow_style_duplicate_names_rejected_before_lossy_conversion(self):
        class Table:
            column_names = ["sample_id", "sample_id"]

            def to_pylist(self):
                self.fail_if_called = True
                raise AssertionError("duplicate names must be checked before conversion")

        with self.assertRaisesRegex(ValueError, "duplicate"):
            table_records(Table())

    def test_arrow_style_empty_schema_still_checks_mapping(self):
        class Table:
            column_names = ["recording"]

            def to_pylist(self):
                return []

        self.assertEqual(table_records(Table(), {"session_id": "recording"}), [])
        with self.assertRaisesRegex(ValueError, "missing"):
            table_records(Table(), {"session_id": "absent"})

    def test_parquet_input_must_be_an_explicit_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "one existing local file"):
                load_parquet(directory)


@unittest.skipUnless(importlib.util.find_spec("pyarrow"), "optional pyarrow is unavailable")
class ArrowAndParquetTests(unittest.TestCase):
    def test_real_arrow_and_parquet_round_trip_preserves_identity(self):
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = [
            {"recording": "s2", "sample_id": "2", "predicted_vx": 2.5},
            {"recording": "s1", "sample_id": "1", "predicted_vx": None},
        ]
        arrow = pa.Table.from_pylist(rows)
        expected = table_records(rows, {"session_id": "recording"})
        self.assertEqual(table_records(arrow, {"session_id": "recording"}), expected)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.parquet"
            pq.write_table(arrow, path)
            self.assertEqual(load_parquet(path, {"session_id": "recording"}), expected)
            with self.assertRaisesRegex(ValueError, "missing"):
                load_parquet(path, {"session_id": "absent"})

    def test_real_arrow_duplicate_field_names_are_rejected(self):
        import pyarrow as pa

        table = pa.Table.from_arrays([pa.array(["a"]), pa.array(["b"])], names=["id", "id"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            table_records(table)


if __name__ == "__main__":
    unittest.main()
