"""Keyed comparison and content-bound evidence, using only Python's standard library."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import numbers
import platform
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .tables import table_records

VERSION = "0.1.0"
FORMAT_VERSION = 1


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _nonnegative(value: Any, name: str) -> float:
    value = _number(value, name)
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _safe(value: Any) -> Any:
    """Retain invalid numeric evidence as explicit strings, never nonstandard JSON NaN."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, numbers.Real):
        try:
            result = float(value)
        except (OverflowError, ValueError):
            return "<invalid numeric value>"
        return result if math.isfinite(result) else f"<nonfinite:{result}>"
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise ValueError("Metadata keys must be strings")
        return {k: _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    raise ValueError(f"Unsupported evidence type: {type(value).__name__}")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _source_digest() -> str:
    root = Path(__file__).parent
    return _digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                    for name in ("__init__.py", "core.py", "tables.py", "report.py")})


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Nonstandard JSON constant: {value}")
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


@dataclass(frozen=True)
class EvaluationSet:
    evaluation_id: str
    units: str
    coordinates: str
    horizon_ms: float
    purpose: str
    source_ref: str | None
    records: tuple[dict, ...]
    fingerprint: str

    @classmethod
    def from_records(cls, records, *, evaluation_id, units, coordinates,
                     horizon_ms=0, purpose="development", source_ref=None, columns=None):
        metadata = dict(evaluation_id=_text(evaluation_id, "evaluation_id"),
                        units=_text(units, "units"), coordinates=_text(coordinates, "coordinates"),
                        horizon_ms=_nonnegative(horizon_ms, "horizon_ms"),
                        purpose=_text(purpose, "purpose"),
                        source_ref=None if source_ref is None else _text(source_ref, "source_ref"))
        normalized, seen = [], set()
        for row in table_records(records, columns=columns):
            sid = _text(row.get("session_id"), "session_id")
            key = (sid, _text(row.get("sample_id"), "sample_id"))
            if key in seen:
                raise ValueError(f"Duplicate evaluation key: {key!r}")
            seen.add(key)
            eligible = row.get("eligible", True)
            if type(eligible) is not bool:
                raise ValueError("eligible must be a boolean")
            reason = row.get("exclusion_reason", "")
            if not eligible:
                _text(reason, "exclusion_reason for excluded sample")
            elif reason not in (None, ""):
                raise ValueError("Eligible samples must not declare an exclusion reason")
            normalized.append(dict(session_id=sid, sample_id=key[1],
                timestamp=_number(row.get("timestamp"), "timestamp"),
                target_vx=_number(row.get("target_vx"), "target_vx"),
                target_vy=_number(row.get("target_vy"), "target_vy"),
                eligible=eligible, exclusion_reason=reason or ""))
        if not normalized:
            raise ValueError("Evaluation set must contain at least one sample")
        normalized.sort(key=lambda r: (r["session_id"], r["sample_id"]))
        payload = dict(**metadata, records=normalized)
        return cls(**metadata, records=tuple(normalized), fingerprint=_digest(payload))

    def _payload(self):
        return dict(evaluation_id=self.evaluation_id, units=self.units,
                    coordinates=self.coordinates, horizon_ms=self.horizon_ms,
                    purpose=self.purpose, source_ref=self.source_ref, records=list(self.records))

    def save(self, path):
        if _digest(self._payload()) != self.fingerprint:
            raise ValueError("Evaluation content fingerprint mismatch")
        _write_json(Path(path), dict(format_version=FORMAT_VERSION, kind="evaluation",
                                   fingerprint=self.fingerprint, payload=self._payload()))

    @classmethod
    def load(cls, path):
        doc = _read_json(Path(path))
        if doc.get("format_version") != FORMAT_VERSION or doc.get("kind") != "evaluation":
            raise ValueError("Unsupported evaluation bundle format")
        payload = doc.get("payload")
        if _digest(payload) != doc.get("fingerprint"):
            raise ValueError("Evaluation content fingerprint mismatch")
        try:
            result = cls.from_records(**payload)
        except (TypeError, KeyError) as exc:
            raise ValueError("Malformed evaluation bundle") from exc
        if result.fingerprint != doc["fingerprint"]:
            raise ValueError("Evaluation bundle is not canonical")
        return result


@dataclass(frozen=True)
class PredictionSet:
    run_id: str
    evaluation_fingerprint: str
    units: str
    coordinates: str
    horizon_ms: float
    provenance: dict
    records: tuple[dict, ...]
    digest: str

    @classmethod
    def from_records(cls, records, *, run_id, evaluation, provenance=None, columns=None):
        if not isinstance(evaluation, EvaluationSet):
            raise ValueError("evaluation must be an EvaluationSet")
        metadata = dict(run_id=_text(run_id, "run_id"),
                        evaluation_fingerprint=evaluation.fingerprint,
                        units=evaluation.units, coordinates=evaluation.coordinates,
                        horizon_ms=evaluation.horizon_ms,
                        provenance=_safe(provenance or {}))
        if not isinstance(metadata["provenance"], dict):
            raise ValueError("provenance must be a mapping")
        normalized = []
        for row in table_records(records, columns=columns):
            normalized.append({key: _safe(row.get(key)) for key in
                ("session_id", "sample_id", "predicted_vx", "predicted_vy")})
        normalized.sort(key=_json)
        payload = dict(**metadata, records=normalized)
        return cls(**metadata, records=tuple(normalized), digest=_digest(payload))

    def _payload(self):
        return dict(run_id=self.run_id, evaluation_fingerprint=self.evaluation_fingerprint,
                    units=self.units, coordinates=self.coordinates, horizon_ms=self.horizon_ms,
                    provenance=self.provenance, records=list(self.records))

    def save(self, path):
        if _digest(self._payload()) != self.digest:
            raise ValueError("Prediction content digest mismatch")
        _write_json(Path(path), dict(format_version=FORMAT_VERSION, kind="predictions",
                                   digest=self.digest, payload=self._payload()))

    @classmethod
    def load(cls, path):
        doc = _read_json(Path(path))
        if doc.get("format_version") != FORMAT_VERSION or doc.get("kind") != "predictions":
            raise ValueError("Unsupported prediction bundle format")
        payload = doc.get("payload")
        if not isinstance(payload, dict) or _digest(payload) != doc.get("digest"):
            raise ValueError("Prediction content digest mismatch")
        required = {"run_id", "evaluation_fingerprint", "units", "coordinates", "horizon_ms", "provenance", "records"}
        if set(payload) != required or not isinstance(payload["records"], list):
            raise ValueError("Malformed prediction bundle")
        for name in ("run_id", "evaluation_fingerprint", "units", "coordinates"):
            _text(payload[name], name)
        _nonnegative(payload["horizon_ms"], "horizon_ms")
        if not isinstance(payload["provenance"], dict) or not all(isinstance(r, dict) for r in payload["records"]):
            raise ValueError("Malformed prediction records or provenance")
        return cls(**{**payload, "records": tuple(payload["records"])}, digest=doc["digest"])


def _index(predictions, evaluation, label):
    expected = {(r["session_id"], r["sample_id"]): r for r in evaluation.records}
    sessions = {r["session_id"] for r in evaluation.records}
    index, errors, global_issues = defaultdict(list), defaultdict(list), []
    excluded = 0
    for row in predictions.records:
        sid, sample = row.get("session_id"), row.get("sample_id")
        if not isinstance(sid, str) or not isinstance(sample, str):
            global_issues.append(f"{label}: prediction has a malformed session/sample identity")
            if isinstance(sid, str) and sid in sessions:
                errors[sid].append(f"{label}: malformed prediction identity")
            continue
        key = sid, sample
        if key not in expected:
            issue = f"{label}: unexpected prediction key {key!r}"
            global_issues.append(issue)
            if sid in sessions:
                errors[sid].append(issue)
            continue
        if not expected[key]["eligible"]:
            excluded += 1
            continue
        index[key].append(row)
    return index, errors, global_issues, excluded


def _rmse(errors):
    scale = max(errors)
    if scale == 0:
        return 0.0
    return scale * math.sqrt(math.fsum((value / scale) ** 2 for value in errors) / len(errors))


def compare(evaluation, baseline, candidate, *, tolerance=None, numerical_tolerance=1e-12,
            output_dir=None, description="") -> dict:
    """Compare fixed outputs; incomplete rows stay visible and no model is executed.

    ``tolerance`` is an absolute delta in the declared velocity units. None means
    descriptive deltas only. ``output_dir`` must not exist; artifacts are never overwritten.
    """
    if not isinstance(evaluation, EvaluationSet) or not all(isinstance(p, PredictionSet) for p in (baseline, candidate)):
        raise ValueError("Expected an EvaluationSet and two PredictionSet bundles")
    if tolerance is not None:
        tolerance = _nonnegative(tolerance, "tolerance")
    numerical_tolerance = _nonnegative(numerical_tolerance, "numerical_tolerance")
    if not isinstance(description, str):
        raise ValueError("description must be a string")
    identity_issues = []
    if _digest(evaluation._payload()) != evaluation.fingerprint:
        identity_issues.append("Evaluation content fingerprint mismatch")
    for name, pred in (("baseline", baseline), ("candidate", candidate)):
        if _digest(pred._payload()) != pred.digest:
            identity_issues.append(f"{name}: prediction content digest mismatch")
        if pred.evaluation_fingerprint != evaluation.fingerprint:
            identity_issues.append(f"{name}: evaluation-set identity mismatch")
        for field in ("units", "coordinates", "horizon_ms"):
            if getattr(pred, field) != getattr(evaluation, field):
                identity_issues.append(f"{name}: {field} mismatch")
    bi, be, bg, bx = _index(baseline, evaluation, "baseline")
    ci, ce, cg, cx = _index(candidate, evaluation, "candidate")
    global_issues = identity_issues + bg + cg
    groups = defaultdict(list)
    for row in evaluation.records:
        groups[row["session_id"]].append(row)
    results, observations = [], []
    for sid, rows in sorted(groups.items()):
        eligible = [r for r in rows if r["eligible"]]
        issues = list(identity_issues) + be[sid] + ce[sid]
        if not eligible:
            issues.append("No eligible scoring samples")
        paired = []
        for row in sorted(eligible, key=lambda r: (r["timestamp"], r["sample_id"])):
            key = sid, row["sample_id"]
            values = []
            for label, index in (("baseline", bi), ("candidate", ci)):
                matches = index.get(key, [])
                if len(matches) != 1:
                    issues.append(f"{label}: expected one prediction for {key!r}, found {len(matches)}")
                    continue
                try:
                    vx = _number(matches[0].get("predicted_vx"), "predicted_vx")
                    vy = _number(matches[0].get("predicted_vy"), "predicted_vy")
                    error = math.hypot(vx - row["target_vx"], vy - row["target_vy"])
                    if not math.isfinite(error):
                        raise ValueError("Error magnitude is not representable as a finite number")
                    values.append((vx, vy, error))
                except ValueError as exc:
                    issues.append(f"{label}: {key!r}: {exc}")
            if len(values) == 2:
                b, c = values
                paired.append(dict(session_id=sid, sample_id=row["sample_id"], timestamp=row["timestamp"],
                    target_vx=row["target_vx"], target_vy=row["target_vy"],
                    baseline_vx=b[0], baseline_vy=b[1], candidate_vx=c[0], candidate_vy=c[1],
                    baseline_error=b[2], candidate_error=c[2]))
        result = dict(session_id=sid, status="invalid" if issues else "valid", n_expected=len(eligible),
                      n_scored=0, baseline_rmse=None, candidate_rmse=None, delta=None,
                      regression=None, issues=list(dict.fromkeys(issues)))
        if not issues:
            br = _rmse([p["baseline_error"] for p in paired])
            cr = _rmse([p["candidate_error"] for p in paired])
            result.update(n_scored=len(paired), baseline_rmse=br, candidate_rmse=cr, delta=cr-br,
                          regression=None if tolerance is None else cr-br > tolerance)
            observations.extend(paired)
        results.append(result)
    results.sort(key=lambda r: (r["status"] != "invalid", -(r["delta"] or 0), r["session_id"]))
    complete = not global_issues and all(r["status"] == "valid" for r in results)
    pooled = None
    if complete:
        br = _rmse([p["baseline_error"] for p in observations])
        cr = _rmse([p["candidate_error"] for p in observations])
        pooled = dict(baseline_rmse=br, candidate_rmse=cr, delta=cr-br, n_samples=len(observations))
    report = dict(schema_version="1", comparator_version=VERSION, comparator_source_digest=_source_digest(), description=description,
        evaluation=dict(evaluation_id=evaluation.evaluation_id, fingerprint=evaluation.fingerprint,
                        units=evaluation.units, coordinates=evaluation.coordinates,
                        horizon_ms=evaluation.horizon_ms, purpose=evaluation.purpose, source_ref=evaluation.source_ref),
        baseline=dict(run_id=baseline.run_id, digest=baseline.digest, provenance=baseline.provenance),
        candidate=dict(run_id=candidate.run_id, digest=candidate.digest, provenance=candidate.provenance),
        tolerance=tolerance, numerical_tolerance=numerical_tolerance, complete=complete,
        issues=list(dict.fromkeys(global_issues)),
        excluded_counts=dict(evaluation=sum(not r["eligible"] for r in evaluation.records), baseline=bx, candidate=cx),
        sessions=results, pooled=pooled, samples=observations)
    if output_dir is not None:
        _save_comparison(Path(output_dir), evaluation, baseline, candidate, report)
    return report


def _save_comparison(destination, evaluation, baseline, candidate, result):
    from .report import render_report
    if destination.exists():
        raise FileExistsError(f"Output directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".bci-comparison-", dir=destination.parent))
    reserved = False
    moved = []
    try:
        evaluation.save(staging / "evaluation.json")
        baseline.save(staging / "baseline.json")
        candidate.save(staging / "candidate.json")
        _write_json(staging / "comparison.json", result)
        fields = ["session_id", "status", "n_expected", "n_scored", "baseline_rmse", "candidate_rmse", "delta", "regression", "issues"]
        with (staging / "session_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in result["sessions"]:
                writer.writerow({**row, "issues": json.dumps(row["issues"])})
        (staging / "report.html").write_text(render_report(result), encoding="utf-8")
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in staging.iterdir()}
        _write_json(staging / "manifest.json", dict(format_version=FORMAT_VERSION,
            comparator_version=VERSION, comparator_source_digest=result["comparator_source_digest"],
            metric="velocity_vector_rmse", tolerance=result["tolerance"],
            numerical_tolerance=result["numerical_tolerance"], description=result["description"],
            environment=dict(python=platform.python_version(), platform=platform.platform()), files=files))
        # Reserve rather than replace the destination, including an empty existing directory.
        destination.mkdir(exist_ok=False)
        reserved = True
        # A manifest appears only after every evidence file has been published.
        for path in sorted(staging.iterdir(), key=lambda p: (p.name == "manifest.json", p.name)):
            target = destination / path.name
            path.rename(target)
            moved.append(target)
    except BaseException:
        if reserved:
            for path in reversed(moved):
                path.unlink(missing_ok=True)
            try:
                destination.rmdir()
            except OSError:
                pass  # Never remove unrelated files another process may have written.
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def reproduce(bundle_dir, *, output_dir=None) -> dict:
    """Verify retained evidence and recompute scores without loading a decoder."""
    root = Path(bundle_dir)
    manifest = _read_json(root / "manifest.json")
    if manifest.get("format_version") != FORMAT_VERSION or manifest.get("comparator_version") != VERSION:
        raise ValueError("Unsupported bundle or comparator version; use the recorded version")
    if manifest.get("comparator_source_digest") != _source_digest():
        raise ValueError("Comparator source differs; use the recorded source revision")
    required = {"evaluation.json", "baseline.json", "candidate.json", "comparison.json", "session_metrics.csv", "report.html"}
    files = manifest.get("files", {})
    if not isinstance(files, dict) or set(files) != required:
        raise ValueError("Incomplete comparison manifest")
    for name, expected in files.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Artifact content digest mismatch: {name}")
    result = compare(EvaluationSet.load(root / "evaluation.json"),
        PredictionSet.load(root / "baseline.json"), PredictionSet.load(root / "candidate.json"),
        tolerance=manifest["tolerance"], numerical_tolerance=manifest["numerical_tolerance"],
        description=manifest.get("description", ""))
    saved = _read_json(root / "comparison.json")
    # Evidence identity and coverage must match exactly; only floating arithmetic has a tolerance.
    def same(a, b, path=()):
        computed = ((len(path) == 3 and path[0] == "sessions" and path[-1] in {"baseline_rmse", "candidate_rmse", "delta"})
                    or (len(path) == 2 and path[0] == "pooled" and path[-1] in {"baseline_rmse", "candidate_rmse", "delta"})
                    or (len(path) == 3 and path[0] == "samples" and path[-1] in {"baseline_error", "candidate_error"}))
        if computed and isinstance(a, float) and isinstance(b, (float, int)) and not isinstance(b, bool):
            return math.isclose(a, b, rel_tol=0, abs_tol=result["numerical_tolerance"])
        if type(a) is not type(b):
            return False
        if isinstance(a, dict):
            return set(a) == set(b) and all(same(a[k], b[k], path + (k,)) for k in a)
        if isinstance(a, list):
            return len(a) == len(b) and all(same(x, y, path + (i,)) for i, (x, y) in enumerate(zip(a, b)))
        return a == b
    if not same(result, saved):
        raise ValueError("Recomputed comparison differs from the recorded result")
    if output_dir is not None:
        _save_comparison(Path(output_dir), EvaluationSet.load(root / "evaluation.json"),
            PredictionSet.load(root / "baseline.json"), PredictionSet.load(root / "candidate.json"), result)
    return result
