"""A fixed reference for repeated comparisons of an evaluator's saved outputs.

Import ``PinnedComparison`` from this module. A pin fixes the evaluation,
baseline, column mapping, and reporting configuration; it never runs a model
or updates the baseline. Comparison bundles use the existing ``reproduce``
function to recompute scores from retained predictions and targets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from . import core
from .core import EvaluationSet, PredictionSet
from .tables import _column_mapping


_FORMAT = 1
_KIND = "bci-regression-pin"
_RESERVED = "bci_regression_pin"
_PREDICTION_FIELDS = {"session_id", "sample_id", "predicted_vx", "predicted_vy"}
_FILES = {"evaluation.json", "baseline.json"}
_CONFIG_FIELDS = {"prediction_columns", "tolerance", "numerical_tolerance", "description"}
_MANIFEST_FIELDS = {
    "format_version", "kind", "comparator_version", "comparator_source_digest",
    "wrapper_source_digest", "evaluation", "baseline", "configuration", "files",
    "fingerprint",
}


def _wrapper_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"Malformed pin {label}: unexpected or missing fields")


def _sha256(value, label):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"Malformed pin {label}: expected a SHA256 digest")


def _read_json(path):
    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise ValueError(f"Duplicate JSON field: {name}")
            result[name] = value
        return result

    def constant(value):
        raise ValueError(f"Nonstandard JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=constant)


def _configuration(prediction_columns, tolerance, numerical_tolerance, description):
    mapping = _column_mapping(prediction_columns)
    if set(mapping) - _PREDICTION_FIELDS:
        raise ValueError("prediction_columns may map only session_id, sample_id, predicted_vx, predicted_vy")
    for canonical, source in mapping.items():
        if not source.strip():
            raise ValueError("prediction_columns source names must be nonempty strings")
        if source in _PREDICTION_FIELDS and canonical != source:
            raise ValueError(f"prediction_columns collides with canonical field: {source!r}")
    if not isinstance(description, str):
        raise ValueError("description must be a string")
    return dict(prediction_columns=mapping,
                tolerance=None if tolerance is None else core._nonnegative(tolerance, "tolerance"),
                numerical_tolerance=core._nonnegative(numerical_tolerance, "numerical_tolerance"),
                description=description)


def _fingerprint(manifest):
    return core._digest({key: value for key, value in manifest.items() if key != "fingerprint"})


def _complete_reference(evaluation, baseline, config):
    result = core.compare(evaluation, baseline, baseline, tolerance=config["tolerance"],
                          numerical_tolerance=config["numerical_tolerance"],
                          description=config["description"])
    if not result["complete"]:
        issues = result["issues"] + [issue for row in result["sessions"] for issue in row["issues"]]
        raise ValueError("Cannot pin an incomplete or invalid baseline: " + "; ".join(dict.fromkeys(issues)))


def _read_pin(path):
    """Validate every saved field and reference before exposing configuration."""
    try:
        if path.is_symlink() or not path.is_dir():
            raise ValueError("Pin must be an existing regular directory")
        if {p.name for p in path.iterdir()} != _FILES | {"manifest.json"}:
            raise ValueError("Pin must contain exactly evaluation.json, baseline.json, and manifest.json")
        for name in _FILES | {"manifest.json"}:
            file = path / name
            if file.is_symlink() or not file.is_file():
                raise ValueError(f"Pin artifact must be a regular file: {name}")
        manifest = _read_json(path / "manifest.json")
        _keys(manifest, _MANIFEST_FIELDS, "manifest")
        if type(manifest["format_version"]) is not int or manifest["format_version"] != _FORMAT or manifest["kind"] != _KIND:
            raise ValueError("Unsupported pin format")
        if manifest["comparator_version"] != core.VERSION:
            raise ValueError("Comparator version differs; use the recorded version or create a new pin")
        for name in ("fingerprint", "wrapper_source_digest", "comparator_source_digest"):
            _sha256(manifest[name], name)
        if _fingerprint(manifest) != manifest["fingerprint"]:
            raise ValueError("Pin fingerprint mismatch; restore the original pin or create a new pin")
        if manifest["wrapper_source_digest"] != _wrapper_digest():
            raise ValueError("Pin wrapper source differs; use the recorded source or create a new pin")
        if manifest["comparator_source_digest"] != core._source_digest():
            raise ValueError("Pin comparator source differs; use the recorded source or create a new pin")
        _keys(manifest["evaluation"], {"evaluation_id", "fingerprint"}, "evaluation identity")
        _keys(manifest["baseline"], {"run_id", "digest"}, "baseline identity")
        _sha256(manifest["evaluation"]["fingerprint"], "evaluation fingerprint")
        _sha256(manifest["baseline"]["digest"], "baseline digest")
        core._text(manifest["evaluation"]["evaluation_id"], "evaluation_id")
        core._text(manifest["baseline"]["run_id"], "baseline run_id")
        config = manifest["configuration"]
        _keys(config, _CONFIG_FIELDS, "configuration")
        normalized = _configuration(**config)
        if core._json(normalized) != core._json(config):
            raise ValueError("Pin configuration is not canonical")
        _keys(manifest["files"], _FILES, "files")
        for name in _FILES:
            _sha256(manifest["files"][name], f"file digest for {name}")
            if hashlib.sha256((path / name).read_bytes()).hexdigest() != manifest["files"][name]:
                raise ValueError(f"Pin artifact content digest mismatch: {name}")
            doc = _read_json(path / name)
            identity = "fingerprint" if name == "evaluation.json" else "digest"
            _keys(doc, {"format_version", "kind", identity, "payload"}, name)
            if type(doc["format_version"]) is not int or doc["format_version"] != core.FORMAT_VERSION:
                raise ValueError(f"Unsupported pin artifact format: {name}")
            payload_fields = ({"evaluation_id", "units", "coordinates", "horizon_ms", "purpose", "source_ref", "records"}
                              if name == "evaluation.json" else
                              {"run_id", "evaluation_fingerprint", "units", "coordinates", "horizon_ms", "provenance", "records"})
            if isinstance(doc["payload"], dict) and "target_kind" in doc["payload"]:
                payload_fields.add("target_kind")
            _keys(doc["payload"], payload_fields, f"{name} payload")
            records = doc["payload"]["records"]
            if not isinstance(records, list):
                raise ValueError(f"Malformed pin records: {name}")
            row_fields = ({"session_id", "sample_id", "timestamp", "target_vx", "target_vy", "eligible", "exclusion_reason"}
                          if name == "evaluation.json" else _PREDICTION_FIELDS)
            for row in records:
                _keys(row, row_fields, f"{name} record")
        evaluation = EvaluationSet.load(path / "evaluation.json")
        baseline = PredictionSet.load(path / "baseline.json")
        if manifest["evaluation"] != dict(evaluation_id=evaluation.evaluation_id, fingerprint=evaluation.fingerprint):
            raise ValueError("Pin evaluation identity does not match its artifact")
        if manifest["baseline"] != dict(run_id=baseline.run_id, digest=baseline.digest):
            raise ValueError("Pin baseline identity does not match its artifact")
        _complete_reference(evaluation, baseline, config)
        return manifest, evaluation, baseline
    except (OSError, TypeError, KeyError) as exc:
        raise ValueError(f"Cannot read a valid pin at {path}: {exc}") from exc


@dataclass(frozen=True)
class PinnedComparison:
    """Load a fixed reference and compare new keyed prediction rows against it.

    Use ``create`` once, then ``load`` in subsequent evaluator runs. Every call
    to ``compare`` must supply the current evaluation and a fresh output path.
    Hashes identify the supplied evidence; they do not authenticate its producer
    or independently verify how model predictions were generated.
    """

    path: Path
    fingerprint: str

    @classmethod
    def create(cls, path, *, evaluation: EvaluationSet, baseline: PredictionSet,
               prediction_columns=None, tolerance=None, numerical_tolerance=1e-12,
               description=""):
        destination = Path(path).absolute()
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Pin destination already exists: {destination}")
        config = _configuration(prediction_columns, tolerance, numerical_tolerance, description)
        _complete_reference(evaluation, baseline, config)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".bci-pin-", dir=destination.parent))
        published = []
        reserved = False
        try:
            evaluation.save(staging / "evaluation.json")
            baseline.save(staging / "baseline.json")
            manifest = dict(format_version=_FORMAT, kind=_KIND, comparator_version=core.VERSION,
                comparator_source_digest=core._source_digest(), wrapper_source_digest=_wrapper_digest(),
                evaluation=dict(evaluation_id=evaluation.evaluation_id, fingerprint=evaluation.fingerprint),
                baseline=dict(run_id=baseline.run_id, digest=baseline.digest), configuration=config,
                files={name: hashlib.sha256((staging / name).read_bytes()).hexdigest() for name in _FILES})
            manifest["fingerprint"] = _fingerprint(manifest)
            core._write_json(staging / "manifest.json", manifest)
            _read_pin(staging)
            destination.mkdir(exist_ok=False)
            reserved = True
            # Exclusive hard links publish complete files and never replace an
            # existing filename. The manifest is the final completion marker.
            for name in sorted(_FILES) + ["manifest.json"]:
                target = destination / name
                os.link(staging / name, target)
                published.append((staging / name, target))
        except BaseException:
            if reserved:
                for source, target in reversed(published):
                    if target.exists() and os.path.samefile(source, target):
                        target.unlink()
                try:
                    destination.rmdir()
                except OSError:
                    pass  # Preserve unrelated files written by another process.
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return cls(destination, manifest["fingerprint"])

    @classmethod
    def load(cls, path):
        destination = Path(path).absolute()
        manifest, _, _ = _read_pin(destination)
        return cls(destination, manifest["fingerprint"])

    def compare(self, rows, *, evaluation: EvaluationSet, run_id, output_dir, provenance=None):
        """Compare outputs only after verifying the caller's current evaluation.

        Missing, duplicate, extra, or nonfinite prediction values remain visible
        in the ordinary incomplete comparison report. Column mapping errors
        raise before a report is written.
        """
        manifest, _, baseline = _read_pin(self.path)
        if manifest["fingerprint"] != self.fingerprint:
            raise ValueError("Loaded pin identity changed; restore the original pin or create a new pin")
        if not isinstance(evaluation, EvaluationSet):
            raise ValueError("Current evaluation must be an EvaluationSet; a new pin is required for changed evaluation data")
        try:
            current_fingerprint = core._digest(evaluation._payload())
        except (TypeError, ValueError) as exc:
            raise ValueError("Current evaluation payload is invalid; rebuild the evaluation; a new pin is required if it changed") from exc
        if current_fingerprint != evaluation.fingerprint:
            raise ValueError("Current evaluation payload fingerprint mismatch; rebuild the evaluation; a new pin is required if it changed")
        if evaluation.fingerprint != manifest["evaluation"]["fingerprint"]:
            raise ValueError("Current evaluation differs from the pinned evaluation; a new pin is required for changed targets, eligibility, samples, or semantics")
        if output_dir is None:
            raise ValueError("output_dir must be a new comparison directory")
        output_path = Path(output_dir).resolve()
        pin_path = self.path.resolve()
        if output_path == pin_path or pin_path in output_path.parents:
            raise ValueError("output_dir must be outside the pin directory to preserve its fixed artifacts")
        if provenance is not None and not isinstance(provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        metadata = dict(provenance) if provenance is not None else {}
        if _RESERVED in metadata:
            raise ValueError(f"provenance key {_RESERVED!r} is reserved for the pin")
        metadata[_RESERVED] = dict(fingerprint=self.fingerprint,
                                  wrapper_source_digest=manifest["wrapper_source_digest"])
        config = manifest["configuration"]
        candidate = PredictionSet.from_records(rows, run_id=run_id, evaluation=evaluation,
            provenance=metadata, columns=config["prediction_columns"])
        return core.compare(evaluation, baseline, candidate, tolerance=config["tolerance"],
            numerical_tolerance=config["numerical_tolerance"], description=config["description"],
            output_dir=output_dir)
