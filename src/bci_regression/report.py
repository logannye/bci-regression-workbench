"""Render a comparison as a portable, script-free HTML report."""

from __future__ import annotations

from collections import defaultdict
from html import escape
import json
import math


_PREVIEW_ROWS = 24
_TRACE_BUCKETS = 80


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _finite(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _number(value: object, *, signed: bool = False) -> str:
    number = _finite(value)
    if number is None:
        return "—"
    return format(number, "+.6g" if signed and number != 0 else ".6g")


def _json_text(value: object) -> str:
    return _text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _issues(issues: list) -> str:
    if not issues:
        return ""
    return '<ul class="issues">' + "".join(
        f"<li>{_text(issue)}</li>" for issue in issues
    ) + "</ul>"


def _trace_indices(samples: list[dict]) -> list[int]:
    """Bound SVG size while preserving each bucket's extrema for both series."""
    count = len(samples)
    if count <= _TRACE_BUCKETS * 4:
        return list(range(count))
    selected = {0, count - 1}
    for bucket in range(_TRACE_BUCKETS):
        start = bucket * count // _TRACE_BUCKETS
        end = (bucket + 1) * count // _TRACE_BUCKETS
        for name in ("baseline_error", "candidate_error"):
            indices = [
                i for i in range(start, end) if _finite(samples[i].get(name)) is not None
            ]
            if indices:
                selected.add(min(indices, key=lambda i: float(samples[i][name])))
                selected.add(max(indices, key=lambda i: float(samples[i][name])))
    return sorted(selected)


def _error_trace(samples: list[dict], units: object) -> str:
    if not samples:
        return '<p class="muted">No paired samples are available for this session.</p>'
    indices = _trace_indices(samples)
    values = [
        number
        for sample in samples
        for key in ("baseline_error", "candidate_error")
        if (number := _finite(sample.get(key))) is not None
    ]
    if not values:
        return '<p class="muted">No finite paired errors are available to plot.</p>'
    maximum = max(values) or 1.0
    left, right, top, bottom = 70, 940, 18, 190
    grid = []
    for step in range(5):
        value = maximum * step / 4
        y = bottom - (bottom - top) * step / 4
        grid.append(
            f'<line x1="{left}" x2="{right}" y1="{y:g}" y2="{y:g}" '
            'stroke="#e6e9ed"/>'
            f'<text x="{left - 10}" y="{y + 4:g}" text-anchor="end">'
            f'{_number(value)}</text>'
        )
    lines = []
    for key, color, dash in (
        ("baseline_error", "#426b87", ' stroke-dasharray="5 3"'),
        ("candidate_error", "#b45d2b", ""),
    ):
        points = []
        for i in indices:
            error = _finite(samples[i].get(key))
            if error is None:
                continue
            x = left + (right - left) * i / max(1, len(samples) - 1)
            y = bottom - (bottom - top) * error / maximum
            points.append(f"{x:.2f},{y:.2f}")
        if len(points) == 1:
            x, y = points[0].split(",")
            lines.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{color}"/>')
        elif points:
            lines.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{color}" stroke-width="1.8"{dash}/>'
            )
    preview = ""
    if len(indices) < len(samples):
        preview = (
            f" Trace preview uses {len(indices):,} of {len(samples):,} samples, "
            "preserving each display bucket's minima and maxima for both series."
        )
    return (
        '<figure><div class="trace-heading"><strong>Paired error trace</strong>'
        '<span class="legend"><span class="baseline-key">Baseline · dashed</span>'
        '<span class="candidate-key">Candidate · solid</span></span></div>'
        '<svg viewBox="0 0 960 238" role="img" '
        'aria-label="Baseline and candidate Euclidean velocity error by sample order">'
        '<title>Paired Euclidean velocity error in evaluation sample order</title>'
        f'{"".join(grid)}{"".join(lines)}'
        f'<text x="{left}" y="212">1</text>'
        f'<text x="{right}" y="212" text-anchor="end">{len(samples):,}</text>'
        '<text x="505" y="233" text-anchor="middle">Evaluation sample order</text>'
        '</svg><figcaption>Per-sample Euclidean velocity error ('
        f'{_text(units)}); session RMSE is calculated from every eligible sample.'
        f'{preview}</figcaption></figure>'
    )


def _sample_preview(samples: list[dict], units: object) -> str:
    if not samples:
        return ""
    rows = []
    for sample in samples[:_PREVIEW_ROWS]:
        rows.append(
            '<tr><th scope="row">' + _text(sample.get("sample_id", "")) + "</th>"
            f'<td>{_text(sample.get("timestamp", ""))}</td>'
            f'<td>{_number(sample.get("target_vx"))}, '
            f'{_number(sample.get("target_vy"))}</td>'
            f'<td>{_number(sample.get("baseline_vx"))}, '
            f'{_number(sample.get("baseline_vy"))}</td>'
            f'<td>{_number(sample.get("candidate_vx"))}, '
            f'{_number(sample.get("candidate_vy"))}</td>'
            f'<td>{_number(sample.get("baseline_error"))}</td>'
            f'<td>{_number(sample.get("candidate_error"))}</td></tr>'
        )
    count = min(len(samples), _PREVIEW_ROWS)
    return (
        '<h3>Supporting samples</h3>'
        f'<p class="muted">Showing {count:,} of {len(samples):,} paired samples '
        f'in evaluation order. Velocities and errors use {_text(units)}. '
        'All samples and their identities remain in the saved scoring bundle.</p>'
        '<div class="table-scroll"><table class="sample-table"><thead><tr>'
        '<th>Sample ID</th><th>Timestamp</th><th>Target (vx, vy)</th>'
        '<th>Baseline (vx, vy)</th><th>Candidate (vx, vy)</th>'
        '<th>Baseline error</th><th>Candidate error</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


_CSS = """
:root{color-scheme:light;--ink:#202c39;--muted:#5d6b79;--line:#dbe1e7;
--accent:#315d75;--bad:#9e382c;--paper:#fff;--bg:#f3f5f7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1160px;margin:24px auto;padding:0 28px 50px}h1{font-size:30px;
font-weight:650;letter-spacing:-.7px;margin:4px 0}h2{font-size:19px;margin:0 0 10px}
h3{font-size:15px;margin:22px 0 8px}p{margin:8px 0 16px}.eyebrow{font-size:12px;
letter-spacing:1.5px;text-transform:uppercase;color:var(--accent);font-weight:700}
.muted,figcaption{color:var(--muted)}.intro{max-width:810px;margin:4px 0 10px}
.run-context{display:flex;gap:8px 22px;flex-wrap:wrap;font-size:13px;color:var(--muted)}
.run-context span{overflow-wrap:anywhere}.run-context strong{color:var(--ink);font-weight:600}
.panel,.session-detail{background:var(--paper);border:1px solid var(--line);
border-radius:8px;padding:20px;margin:16px 0}
.status{border-left:4px solid var(--accent)}.status.incomplete{border-left-color:var(--bad);
background:#fff8f6}.status{padding:14px 18px}.status-heading{display:flex;align-items:baseline;
gap:8px 24px;flex-wrap:wrap}.status-heading>strong{font-size:16px}.status p{font-size:13px;
margin:6px 0 0}.note{padding:10px 12px;margin:10px 0;background:#eef3f7;
border-radius:5px;white-space:pre-wrap;overflow-wrap:anywhere}.metadata{display:grid;
grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}.metadata dt{font-size:12px;
text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-top:12px}
.metadata dd{margin:3px 0;overflow-wrap:anywhere}.mono,code,pre{font-family:ui-monospace,
SFMono-Regular,Consolas,monospace;font-size:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;
background:#f5f7f9;border-radius:4px;padding:12px}.table-scroll{overflow:auto}table{border-collapse:
collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:12px 10px;border-bottom:
1px solid #e8ecf0;text-align:right;vertical-align:top}thead th{font-size:12px;color:var(--muted);
font-weight:650;background:#f7f9fa;white-space:nowrap}th:first-child,td:first-child{text-align:left}
tbody th{font-weight:500}a{color:var(--accent);text-underline-offset:3px;overflow-wrap:anywhere}
tr.invalid{background:#fff5f2}tr.regression{background:#fffaf4}.badge{display:inline-block;
font-size:12px;padding:3px 8px;border-radius:4px;background:#edf2f5;white-space:nowrap}
.badge.bad{color:var(--bad);background:#f9e6e1}.delta-up{color:var(--bad);font-weight:650}
.issue-inline{max-width:330px;text-align:left;font-size:12px;color:var(--bad);overflow-wrap:anywhere}
.issues{padding-left:20px;overflow-wrap:anywhere}.summary-line{display:flex;gap:18px;flex-wrap:wrap;
margin:0;font-size:13px}.summary-line span{color:var(--muted)}.summary-line strong{color:var(--ink)}
.session-detail{scroll-margin-top:20px}.session-detail summary{cursor:pointer;font-weight:650;
font-size:17px;overflow-wrap:anywhere}.session-detail summary::marker{color:var(--accent)}
.detail-body{padding-top:14px}.trace-heading{display:flex;align-items:baseline;justify-content:
space-between;gap:12px;flex-wrap:wrap}.legend{display:flex;gap:18px;font-size:12px}
.baseline-key{color:#426b87}.candidate-key{color:#b45d2b}figure{margin:24px 0 18px}svg{display:block;
width:100%;height:auto;margin-top:12px}svg text{font:11px system-ui,sans-serif;fill:#647281}
figcaption{font-size:12px;margin-top:8px}.sample-table{font-size:12px}.sample-table th,
.sample-table td{padding:8px;white-space:nowrap}.sample-table th:first-child{white-space:normal;
min-width:100px;overflow-wrap:anywhere}.metric{font-family:ui-monospace,SFMono-Regular,Consolas,
monospace;font-size:13px;overflow-wrap:anywhere}.provenance{margin-top:18px}.provenance summary{
cursor:pointer;color:var(--muted);font-size:13px}footer{font-size:12px;color:var(--muted);margin-top:30px}
@media(max-width:760px){main{margin:22px auto;padding:0 14px 30px}.panel,.session-detail{padding:16px}
.metadata{grid-template-columns:1fr;gap:6px}h1{font-size:27px}}
@media print{body{background:#fff}main{max-width:none;margin:0;padding:0}.panel,.session-detail{
break-inside:avoid;border-radius:0}a{color:inherit}details.provenance{display:block}th,td{padding:6px}}
"""


def render_report(result: dict) -> str:
    """Return one self-contained report without executing or loading any model.

    The caller supplies a validated comparison result. All producer text is
    treated as text, including identifiers, provenance, issues, and timestamps.
    No external resources or JavaScript are included.
    """
    evaluation = result.get("evaluation", {})
    baseline = result.get("baseline", {})
    candidate = result.get("candidate", {})
    units = evaluation.get("units", "unspecified units")
    tolerance = result.get("tolerance")
    sessions = sorted(
        result.get("sessions", []),
        key=lambda row: (
            row.get("status") == "valid",
            -(_finite(row.get("delta")) or 0),
            str(row.get("session_id", "")),
        ),
    )
    samples_by_session = defaultdict(list)
    for sample in result.get("samples", []):
        samples_by_session[sample.get("session_id")].append(sample)
    invalid = sum(row.get("status") != "valid" for row in sessions)
    regressions = sum(
        row.get("status") == "valid" and row.get("regression") is True
        for row in sessions
    )
    complete = result.get("complete") is True
    completeness = "Complete comparison" if complete else "Incomplete comparison"
    status_class = "status" if complete else "status incomplete"
    tolerance_text = (
        f'Regression reporting tolerance: {_number(tolerance)} {_text(units)}. '
        'A flag means the candidate-minus-baseline RMSE exceeds this tolerance.'
        if tolerance is not None else
        'No regression reporting tolerance was specified. Deltas are descriptive; '
        'no categorical regression claim is made.'
    )
    description = result.get("description", "")
    description_html = f'<p class="note">{_text(description)}</p>' if description else ""
    rows, details = [], []
    for index, session in enumerate(sessions, start=1):
        session_id = session.get("session_id", "")
        anchor = f"session-{index}"
        valid = session.get("status") == "valid"
        flagged = valid and session.get("regression") is True
        row_class = "invalid" if not valid else ("regression" if flagged else "")
        badge = "Invalid" if not valid else (
            "Regression" if flagged else ("Descriptive" if tolerance is None else "Within tolerance")
        )
        badge_class = "badge bad" if not valid or flagged else "badge"
        issues = session.get("issues", [])
        delta = session.get("delta") if valid else None
        delta_class = "delta-up" if (_finite(delta) or 0) > 0 else ""
        rows.append(
            f'<tr class="{row_class}"><th scope="row"><a href="#{anchor}">'
            f'{_text(session_id)}</a></th><td><span class="{badge_class}">{badge}</span></td>'
            f'<td>{_number(session.get("n_scored"))} / '
            f'{_number(session.get("n_expected"))}</td>'
            f'<td>{_number(session.get("baseline_rmse") if valid else None)}</td>'
            f'<td>{_number(session.get("candidate_rmse") if valid else None)}</td>'
            f'<td class="{delta_class}">{_number(delta, signed=True)}</td>'
            f'<td class="issue-inline">{_text("; ".join(str(i) for i in issues))}</td></tr>'
        )
        session_samples = samples_by_session.get(session_id, []) if valid else []
        detail = (
            _error_trace(session_samples, units) + _sample_preview(session_samples, units)
            if valid else
            '<p>This session was not scored as a valid pair. Its missing or incompatible '
            'evidence remains part of the comparison.</p>'
        )
        details.append(
            f'<details class="session-detail" id="{anchor}" open>'
            f'<summary>{_text(session_id)} · {badge}</summary><div class="detail-body">'
            f'<p>Candidate − baseline RMSE: <strong>{_number(delta, signed=True)} '
            f'{_text(units)}</strong>. Scored / expected samples: '
            f'{_number(session.get("n_scored"))} / {_number(session.get("n_expected"))}.</p>'
            f'{_issues(issues)}{detail}<p><a href="#comparison">Back to session comparison</a></p>'
            '</div></details>'
        )
    pooled = result.get("pooled")
    if complete and pooled is not None:
        pooled_html = (
            '<p class="muted">Sample-weighted pooled RMSE, secondary context: '
            f'baseline {_number(pooled.get("baseline_rmse"))}; '
            f'candidate {_number(pooled.get("candidate_rmse"))}; '
            f'change {_number(pooled.get("delta"), signed=True)} {_text(units)} '
            f'across {_number(pooled.get("n_samples"))} samples.</p>'
        )
    else:
        pooled_html = '<p class="muted">No complete pooled comparison is reported.</p>'
    excluded = result.get("excluded_counts", {})
    excluded_html = (
        '<p class="muted">Rows excluded by the declared evaluation selection: '
        f'evaluation {_number(excluded.get("evaluation", 0))}; '
        f'baseline {_number(excluded.get("baseline", 0))}; '
        f'candidate {_number(excluded.get("candidate", 0))}.</p>'
    )
    flag_summary = (
        f'<span><strong>{regressions}</strong> above tolerance</span>'
        if tolerance is not None else '<span>Descriptive deltas only</span>'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Session regression report · BCI Regression Workbench</title>'
        f'<style>{_CSS}</style></head><body><main>'
        '<header><div class="eyebrow">BCI Regression Workbench</div>'
        '<h1>Session regression report</h1>'
        '<p class="intro muted">Compare per-session errors on the same declared samples '
        'and inspect the supporting evidence.</p>'
        '<div class="run-context">'
        f'<span><strong>Baseline:</strong> {_text(baseline.get("run_id", ""))}</span>'
        f'<span><strong>Candidate:</strong> {_text(candidate.get("run_id", ""))}</span>'
        f'<span><strong>Evaluation:</strong> {_text(evaluation.get("evaluation_id", ""))}</span>'
        '</div>'
        f'{description_html}</header><section class="panel {status_class}">'
        f'<div class="status-heading"><strong>{completeness}</strong><div class="summary-line">'
        f'<span><strong>{len(sessions)}</strong> sessions</span>'
        f'<span><strong>{invalid}</strong> invalid</span>{flag_summary}</div></div>'
        f'<p>{tolerance_text}</p>{_issues(result.get("issues", []))}</section>'
        '<section class="panel" id="comparison"><h2>All sessions</h2>'
        '<p class="muted">Invalid sessions appear first, followed by the largest '
        'candidate-minus-baseline RMSE. Positive changes indicate higher error.</p>'
        '<div class="table-scroll"><table><thead><tr><th>Session</th><th>Status</th>'
        '<th>Scored / expected</th><th>Baseline RMSE</th><th>Candidate RMSE</th>'
        '<th>Change</th><th>Issue</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>{pooled_html}{excluded_html}'
        f'</section>{"".join(details)}'
        '<section class="panel"><h2>Metric and reproduction</h2>'
        '<p class="metric">Vector RMSE = sqrt(mean((predicted_vx − target_vx)² '
        '+ (predicted_vy − target_vy)²))</p>'
        f'<p>RMSE and its change use {_text(units)}. Numerical reproduction tolerance: '
        f'{_number(result.get("numerical_tolerance"))} {_text(units)}.</p>'
        '<p class="muted">The saved scoring bundle retains the predictions, reference '
        'labels, eligibility, identities, and comparison specification needed to recompute '
        'these scores. This report previews the supporting samples; it is not a substitute '
        'for that bundle.</p></section>'
        '<section class="panel"><h2>Comparison identity</h2><div class="metadata">'
        '<dl><dt>Baseline run</dt>'
        f'<dd>{_text(baseline.get("run_id", ""))}</dd><dt>Output digest</dt>'
        f'<dd class="mono">{_text(baseline.get("digest", ""))}</dd></dl>'
        '<dl><dt>Candidate run</dt>'
        f'<dd>{_text(candidate.get("run_id", ""))}</dd><dt>Output digest</dt>'
        f'<dd class="mono">{_text(candidate.get("digest", ""))}</dd></dl>'
        '<dl><dt>Evaluation set</dt>'
        f'<dd>{_text(evaluation.get("evaluation_id", ""))}</dd><dt>Fingerprint</dt>'
        f'<dd class="mono">{_text(evaluation.get("fingerprint", ""))}</dd>'
        f'<dt>Declared purpose</dt><dd>{_text(evaluation.get("purpose", "unspecified"))}</dd></dl>'
        '</div><p class="muted">Target units: '
        f'{_text(units)} · Coordinates: {_text(evaluation.get("coordinates", ""))} '
        f'· Prediction horizon: {_text(evaluation.get("horizon_ms", ""))} ms.</p>'
        '<details class="provenance"><summary>Producer-supplied provenance '
        '(not independently verified)</summary><h3>Baseline</h3>'
        f'<pre>{_json_text(baseline.get("provenance", {}))}</pre><h3>Candidate</h3>'
        f'<pre>{_json_text(candidate.get("provenance", {}))}</pre></details></section>'
        '<footer>Scores describe supplied outputs and labels. '
        'Re-scoring does not verify model execution or training independence, and does '
        'not establish deployment readiness. Independent project; no Neuralink integration '
        'is implied.</footer></main></body></html>'
    )
