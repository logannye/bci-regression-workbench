"""Small table boundary for records, Polars, Arrow, and one local Parquet file.

No optional dataframe library is imported when this module is imported. Column
mapping is explicit: canonical field name -> name in the supplied table. It
renames fields once, preserves other fields and row order, and never joins,
filters, fills missing values, or changes the scoring population.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from os import PathLike
from pathlib import Path
from typing import Any


def _column_mapping(columns: Mapping[str, str] | None) -> dict[str, str]:
    if columns is None:
        return {}
    if not isinstance(columns, Mapping):
        raise TypeError("columns must map canonical field names to source names")
    result = dict(columns)
    if any(
        not isinstance(name, str) or not name
        for pair in result.items()
        for name in pair
    ):
        raise ValueError("column names must be nonempty strings")
    if len(set(result.values())) != len(result):
        raise ValueError("a source column cannot map to multiple canonical fields")
    return result


def _validate_names(names: Iterable[str], mapping: Mapping[str, str]) -> None:
    names = list(names)
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("table column names must be nonempty strings")
    if len(set(names)) != len(names):
        raise ValueError("duplicate source column names are ambiguous")
    for canonical, source in mapping.items():
        if source not in names:
            raise ValueError(f"mapped source column is missing: {source!r}")
        if canonical != source and canonical in names:
            raise ValueError(
                f"column mapping collides with existing field: {canonical!r}"
            )


def table_records(
    table: Any, columns: Mapping[str, str] | None = None
) -> list[dict[str, Any]]:
    """Return copied row mappings without dropping or reordering any rows.

    Accept an iterable of mappings, a Polars DataFrame (``to_dicts``), or an
    Arrow Table/RecordBatch (``to_pylist``). Collect a lazy query explicitly in
    the caller; this function does not execute queries. A partial column map
    renames the specified fields and retains all other fields unchanged.

    Missing mapped source names and collisions raise ``ValueError``. Mapping
    names on an empty, schema-less iterable cannot be checked and is rejected.
    The evaluation/prediction constructors validate required canonical fields
    and values after this conversion.
    """
    mapping = _column_mapping(columns)
    if isinstance(table, (Mapping, str, bytes, bytearray)):
        raise TypeError("table must contain mapping records, not a single value")

    declared_names = None
    if callable(getattr(table, "to_dicts", None)):
        declared_names = getattr(table, "columns", None)
        rows = table.to_dicts()
    elif callable(getattr(table, "to_pylist", None)):
        declared_names = getattr(table, "column_names", None)
        # Arrow permits duplicate field names; check before conversion can
        # collapse them into one dictionary key.
        if declared_names is not None:
            _validate_names(declared_names, mapping)
        rows = table.to_pylist()
    else:
        rows = table

    if declared_names is not None:
        _validate_names(declared_names, mapping)
    try:
        iterator = iter(rows)
    except TypeError as exc:
        raise TypeError(
            "expected mapping records, a Polars DataFrame, or an Arrow table"
        ) from exc

    source_to_canonical = {source: canonical for canonical, source in mapping.items()}
    result = []
    for index, row in enumerate(iterator):
        if not isinstance(row, Mapping):
            raise TypeError(f"row {index} is not a mapping")
        _validate_names(row.keys(), mapping)
        result.append(
            {source_to_canonical.get(name, name): value for name, value in row.items()}
        )
    if not result and mapping and declared_names is None:
        raise ValueError("cannot validate mapped columns on empty schema-less records")
    return result


def load_parquet(
    path: str | PathLike[str], columns: Mapping[str, str] | None = None
) -> list[dict[str, Any]]:
    """Read one explicit local Parquet file, then apply the same column mapping.

    PyArrow is optional and imported only here. Directories, globs, remote
    catalogs, implicit dataset discovery, and row filtering are outside this
    small input boundary.
    """
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Parquet input must be one existing local file: {source}")
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Parquet input requires the optional pyarrow package") from exc
    # ParquetFile reads precisely this file, without directory partition
    # discovery or implicit additional columns from its parent path.
    return table_records(pq.ParquetFile(source).read(), columns=columns)
