"""Render a portable comparison with an optional, fixed session-selection script."""

from __future__ import annotations

from collections import defaultdict, deque
from fractions import Fraction
from html import escape
import json
import math


_PREVIEW_ROWS = 24
_TRACE_BUCKETS = 80
_LOCALIZATION_SAMPLES = 24


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
    """Round for display only; never round a nonzero change down to zero."""
    number = _finite(value)
    if number is None:
        return "—"
    if number == 0:
        return "0.00"
    sign = "+" if signed else ""
    if abs(number) < 0.01 or abs(number) >= 1_000_000:
        return format(number, f"{sign}.3g")
    return format(number, f"{sign},.2f")


def _count(value: object) -> str:
    number = _finite(value)
    if number is None:
        return "—"
    return f"{int(number):,}" if number.is_integer() else _number(number)


def _metric(value: object, *, signed: bool = False) -> str:
    # The title retains the supplied precision; all attribute content is escaped.
    return f'<span title="{_text(value)}">{_number(value, signed=signed)}</span>'


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


def _localization_window(samples: list[dict]) -> tuple[int, int] | None:
    """Locate positive net added squared error; never change supplied scores.

    Rank every window of min(24, n) consecutive scored samples in supplied
    evaluation order. Fractions preserve the exact finite floating-point error
    values without overflow, underflow, or cancellation during ranking. Strict
    improvement retains the earliest window on ties. The stop is exclusive.
    """
    if not samples:
        return None
    width = min(_LOCALIZATION_SAMPLES, len(samples))
    losses = deque()
    total = Fraction(0)
    best_total = Fraction(0)
    best = None
    for index, sample in enumerate(samples):
        baseline = _finite(sample.get("baseline_error"))
        candidate = _finite(sample.get("candidate_error"))
        if baseline is None or candidate is None or baseline < 0 or candidate < 0:
            return None
        baseline = Fraction.from_float(baseline)
        candidate = Fraction.from_float(candidate)
        loss = candidate * candidate - baseline * baseline
        losses.append(loss)
        total += loss
        if len(losses) > width:
            total -= losses.popleft()
        if len(losses) == width and total > best_total:
            best_total = total
            best = (index + 1 - width, index + 1)
    return best


def _error_trace(samples: list[dict], units: object, maximum: float, anchor: str,
                 *, start: int = 0, title: str = "Paired error trace",
                 inferred_target: bool = False) -> str:
    if not samples:
        return '<p class="muted">No paired samples are available for this session.</p>'
    indices = _trace_indices(samples)
    if not any(_finite(sample.get(key)) is not None for sample in samples
               for key in ("baseline_error", "candidate_error")):
        return '<p class="muted">No finite paired errors are available to plot.</p>'
    width, height = 480, 188
    grid, ticks = [], []
    for step in range(5):
        fraction = step / 4
        y = height * fraction
        grid.append(f'<line x1="0" x2="{width}" y1="{y:g}" y2="{y:g}" class="gridline"/>')
        ticks.append(f'<span>{_number(maximum * (1 - fraction))}</span>')
    lines = []
    for key, kind in (("baseline_error", "baseline"), ("candidate_error", "candidate")):
        points = []
        for i in indices:
            error = _finite(samples[i].get(key))
            if error is None:
                continue
            x = width * i / max(1, len(samples) - 1) if len(samples) > 1 else width / 2
            y = height * (1 - error / maximum)
            points.append(f"{x:.3f},{y:.3f}")
        if len(points) == 1:
            x, y = points[0].split(",")
            lines.append(f'<circle cx="{x}" cy="{y}" r="3" class="trace-point {kind}"/>')
        elif points:
            lines.append(f'<polyline points="{" ".join(points)}" class="trace-line {kind}"/>')
    if len(indices) < len(samples):
        preview = (
            f"Trace preview uses {len(indices):,} of {len(samples):,} samples, "
            "preserving each display bucket's minima and maxima for both series. "
            "Lines connect selected samples; this is not a full-resolution trace."
        )
    else:
        preview = ("The single paired sample is shown." if len(samples) == 1 else
                   f"All {len(samples):,} paired samples are shown.")
    xlabels = (f'<span>{start + 1:,}</span>' if len(samples) == 1 else
               f'<span>{start + 1:,}</span><span>{start + len(samples):,}</span>')
    return (
        f'<figure aria-labelledby="{anchor}-trace-title">'
        '<div class="trace-heading">'
        f'<h3 id="{anchor}-trace-title">{_text(title)}</h3>'
        f'<span class="muted">{_text(units)}</span></div>'
        '<div class="legend" aria-label="Trace legend">'
        '<span><i class="swatch baseline" aria-hidden="true"></i>Baseline · dashed</span>'
        '<span><i class="swatch candidate" aria-hidden="true"></i>Candidate · solid</span></div>'
        '<div class="chart"><div class="chart-y" aria-hidden="true">'
        f'{"".join(ticks)}</div><svg viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="none" role="img" '
        f'aria-labelledby="{anchor}-svg-title {anchor}-svg-description">'
        f'<title id="{anchor}-svg-title">Paired Euclidean {"inferred-target vector" if inferred_target else "velocity"} error in evaluation sample order</title>'
        f'<desc id="{anchor}-svg-description">Sample order {start + 1:,} to {start + len(samples):,}. '
        f'Shared vertical range zero to {_number(maximum)} {_text(units)}. '
        'Baseline is gray and dashed; candidate is blue and solid.</desc>'
        f'{"".join(grid)}{"".join(lines)}</svg>'
        f'<div class="chart-x{" single" if len(samples) == 1 else ""}" aria-hidden="true">{xlabels}</div>'
        '<div class="axis-title">Evaluation sample order</div></div>'
        f'<figcaption>Shared y-axis across valid sessions: 0–{_number(maximum)} {_text(units)}. '
        f'{preview} Per-sample Euclidean error is shown; session RMSE uses every eligible sample.</figcaption>'
        '</figure>'
    )


def _sample_preview(samples: list[dict], units: object, *, start: int = 0,
                    total: int | None = None, localized: bool = False,
                    inferred_target: bool = False) -> str:
    if not samples:
        return ""
    rows = []
    for sample in samples[:_PREVIEW_ROWS]:
        timestamp = sample.get("timestamp", "")
        timestamp_number = _finite(timestamp)
        timestamp_display = _text(timestamp) if timestamp_number is None else format(timestamp_number, ".6g")
        rows.append(
            '<tr><th scope="row">' + _text(sample.get("sample_id", "")) + "</th>"
            f'<td title="{_text(timestamp)}">{timestamp_display}</td>'
            f'<td>{_metric(sample.get("target_vx"))}, {_metric(sample.get("target_vy"))}</td>'
            f'<td>{_metric(sample.get("baseline_vx"))}, {_metric(sample.get("baseline_vy"))}</td>'
            f'<td>{_metric(sample.get("candidate_vx"))}, {_metric(sample.get("candidate_vy"))}</td>'
            f'<td>{_metric(sample.get("baseline_error"))}</td>'
            f'<td>{_metric(sample.get("candidate_error"))}</td></tr>'
        )
    count = min(len(samples), _PREVIEW_ROWS)
    total = len(samples) if total is None else total
    selection = (
        f'Window samples {start + 1:,}–{start + count:,} of {total:,} scored samples. '
        if localized else
        f'Showing {count:,} of {total:,} paired sample{"s" if total != 1 else ""} in evaluation order. '
    )
    components = "x, y" if inferred_target else "vx, vy"
    values_label = "Vectors" if inferred_target else "Velocities"
    return (
        '<details class="supporting-samples"><summary>Supporting samples '
        f'<span class="muted">· {count:,} / {total:,} {"window" if localized else "preview"}</span></summary>'
        '<div class="details-content">'
        f'<p class="caption">{selection}{values_label} and errors use {_text(units)}. '
        'Display values are rounded; timestamps retain the producer\'s convention. '
        'All samples and their identities remain in the saved scoring bundle.</p>'
        '<div class="table-scroll" tabindex="0" role="region" aria-label="Supporting sample table">'
        '<table class="sample-table"><thead><tr>'
        '<th scope="col">Sample ID</th><th scope="col">Timestamp</th>'
        f'<th scope="col">{"Inferred target" if inferred_target else "Target"} ({components})</th>'
        f'<th scope="col">Baseline ({components})</th>'
        f'<th scope="col">Candidate ({components})</th><th scope="col">Baseline error</th>'
        '<th scope="col">Candidate error</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div></details>'
    )


def _session_evidence(samples: list[dict], units: object, maximum: float,
                      anchor: str, delta: object, *, inferred_target: bool = False) -> str:
    """Put a reproducible investigation window beside the unchanged session result."""
    width = min(_LOCALIZATION_SAMPLES, len(samples))
    window = _localization_window(samples)
    rule = (
        f'Fixed rule: examine every window of {_LOCALIZATION_SAMPLES} consecutive scored samples '
        f'(the whole session if shorter). This session uses {width:,} samples per window. '
        'Rank by summed candidate squared error minus baseline squared error, '
        'with the earliest window winning exact ties. '
        'Consecutive scored samples may span recording gaps; this is not a fixed-duration window. '
        "Timestamps retain the producer's convention."
    )
    method = (
        '<details class="localization-method"><summary>How this window is selected</summary>'
        f'<div class="details-content"><p class="caption">{rule}</p>'
        '<p class="caption">Exploratory localization only: it does not change scoring, '
        'establish statistical significance, or identify a cause.</p></div></details>'
    )
    if window is None:
        usable = bool(samples) and all(
            _finite(sample.get(key)) is not None and _finite(sample.get(key)) >= 0
            for sample in samples for key in ("baseline_error", "candidate_error")
        )
        message = (f'No {width:,}-sample window has net added squared error under this rule.'
                   if usable else 'Finite paired errors are unavailable for localization.')
        return (
            '<section class="localization-empty" aria-label="Error localization">'
            f'<h3>{"No added-error window" if usable else "Localization unavailable"}</h3>'
            f'<p class="caption">{message} Session scores and flags are unchanged.</p>'
            f'{method}</section>'
            + _error_trace(samples, units, maximum, anchor, inferred_target=inferred_target)
            + _sample_preview(samples, units, inferred_target=inferred_target)
        )
    start, stop = window
    selected = samples[start:stop]
    references = []
    for label, sample in (("Start", selected[0]), ("End", selected[-1])):
        references.append(
            f'<div><dt>{label} sample</dt><dd class="mono">{_text(sample.get("sample_id", ""))}</dd>'
            f'<dt>Timestamp</dt><dd class="mono">{_text(sample.get("timestamp", ""))}</dd></div>'
        )
    context = (
        'This session improves overall; this window only identifies a local loss.'
        if (_finite(delta) or 0) < 0 else
        'This window is an investigation starting point, not a new regression flag.'
    )
    return (
        f'<section class="localization" data-localization-start="{start}" '
        f'data-localization-stop="{stop}" aria-labelledby="{anchor}-window-heading">'
        f'<h3 id="{anchor}-window-heading">Highest added-error window</h3>'
        f'<p class="window-range">Scored samples <strong>{start + 1:,}–{stop:,}</strong> '
        f'of {len(samples):,} · {len(selected):,} samples</p>'
        f'<p class="caption">{context}</p>'
        f'<dl class="window-references">{"".join(references)}</dl>'
        + _error_trace(selected, units, maximum, anchor + "-window", start=start,
                       title="Paired errors in selected window", inferred_target=inferred_target)
        + _sample_preview(selected, units, start=start, total=len(samples), localized=True,
                          inferred_target=inferred_target)
        + method + '</section><details class="full-session-trace"><summary>Full-session trace</summary>'
        '<div class="details-content">'
        + _error_trace(samples, units, maximum, anchor, inferred_target=inferred_target)
        + '</div></details>'
    )


_CSS = """
:root{color-scheme:light;--ink:#17212c;--muted:#586575;--line:#dce2e8;
--accent:#255b91;--baseline:#596878;--bad:#9b392d;--paper:#fff;--bg:#f7f8fa;
--selected:#edf4fb}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:var(--accent);text-underline-offset:3px;overflow-wrap:anywhere}
a:focus-visible,summary:focus-visible,[tabindex]:focus-visible{outline:3px solid var(--accent);
outline-offset:4px;border-radius:2px}.skip-link{position:absolute;top:8px;left:12px;
transform:translateY(-160%);padding:10px 16px;background:var(--paper);z-index:5}
.skip-link:focus{transform:none}.sr-only{position:absolute;width:1px;height:1px;padding:0;
margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.topbar{background:var(--paper);border-bottom:1px solid var(--line)}.topbar-inner{max-width:1380px;
margin:auto;padding:17px 28px;display:flex;gap:12px 22px;align-items:center;justify-content:space-between;
flex-wrap:wrap}.product{font-weight:600;letter-spacing:-.3px}.topbar a{font-size:12px}
main{max-width:1380px;margin:0 auto;padding:24px 28px 40px}h1{font-size:28px;font-weight:550;
letter-spacing:-.7px;line-height:1.2;margin:0 0 12px}h2{font-size:17px;font-weight:600;
letter-spacing:-.25px;margin:0;overflow-wrap:anywhere}h3{font-size:13px;font-weight:600;margin:0}
p{margin:8px 0 14px}.eyebrow{font-size:11px;letter-spacing:1.15px;text-transform:uppercase;
color:var(--muted);margin:0 0 6px}.muted,.caption,figcaption{color:var(--muted)}
.run-context{display:flex;flex-wrap:wrap;gap:8px 26px;font-size:12px;color:var(--muted)}
.run-context>div{min-width:0;max-width:100%;overflow-wrap:anywhere}.run-context strong{font-weight:500;
color:var(--ink);display:block;margin-top:2px;font-size:13px}.description{font-size:12px;
color:var(--muted);max-width:1080px;white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0 0}
.status{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:16px 0;
margin:20px 0 24px}.status-heading{display:flex;justify-content:space-between;gap:12px 24px;
flex-wrap:wrap}.outcome{font-size:19px;font-weight:550;letter-spacing:-.3px}.coverage{text-align:right;
font-size:12px;overflow-wrap:anywhere}.coverage strong{font-weight:600}.status p{font-size:12px;
color:var(--muted);margin:5px 0 0}.status.incomplete{border-left:3px solid var(--bad);padding-left:14px}
.status.incomplete .outcome{color:var(--bad)}.issues{margin:10px 0 0;padding-left:20px;
color:var(--bad);overflow-wrap:anywhere;font-size:12px}.review-columns{display:grid;grid-template-columns:1fr;
gap:24px;align-items:start}.enhanced .review-columns{grid-template-columns:minmax(0,1.12fr) minmax(0,1fr)}
.session-list,.evidence-pane{min-width:0}.enhanced .evidence-pane{position:sticky;top:16px;
max-height:calc(100vh - 32px);max-height:calc(100dvh - 32px);overflow-y:auto;
scrollbar-gutter:stable;padding:5px;margin:-5px}
.section-heading{display:flex;align-items:baseline;
justify-content:space-between;gap:12px;flex-wrap:wrap;margin:0 0 12px}.section-heading>span{font-size:12px;
overflow-wrap:anywhere}.table-frame,.session-detail{background:var(--paper);border:1px solid var(--line);
border-radius:8px}.table-frame{overflow:auto}.session-table{border-collapse:collapse;width:100%;min-width:360px;
table-layout:fixed;font-variant-numeric:tabular-nums}.session-table th,.session-table td{padding:13px 10px;
border-bottom:1px solid var(--line);text-align:right;vertical-align:top;overflow-wrap:anywhere}
.session-table th:first-child{text-align:left}.session-table thead th{font-size:11px;color:var(--muted);
background:#f2f5f8;font-weight:500;white-space:nowrap;overflow-wrap:normal}.session-table tbody th{font-weight:400}.session-table tbody tr:last-child>*{
border-bottom:0}.session-table tbody tr:hover{background:#f7f9fc}.session-table tr.invalid{background:#fff6f3}
.session-table tr.is-selected,.session-table tr.is-selected:hover{background:var(--selected)}
.session-table tr.is-selected>th{box-shadow:inset 3px 0 0 var(--accent)}.session-link{display:block;
font-size:13px;min-height:28px;padding:2px 0 5px;color:var(--ink);text-decoration:none;font-weight:500;
line-height:1.45}.session-link:hover{text-decoration:underline}.session-link[aria-current="true"]{
color:var(--accent)}.row-meta{display:flex;align-items:baseline;flex-wrap:wrap;gap:2px 8px;
color:var(--muted);font-size:11px;margin:2px 0 0}.row-meta>span{min-width:0;overflow-wrap:anywhere}
.badge{display:inline-block;font-size:11px;line-height:1.4;color:var(--muted)}.badge.bad{color:var(--bad);
font-weight:600}.row-issues{font-size:11px;color:var(--bad);margin:5px 0 0;overflow-wrap:anywhere}
.delta{font-weight:600;font-size:14px}.delta-up{color:var(--bad)}.score{font-size:12px}
.caption{font-size:12px;margin:10px 0;overflow-wrap:anywhere}.pooled{margin-top:16px}
.session-detail{padding:20px;margin:0 0 20px;scroll-margin-top:18px;min-width:0}
.session-detail:last-child{margin-bottom:0}.session-detail:target{outline:2px solid var(--accent);
outline-offset:3px}.enhanced .session-detail:target{outline:none}.detail-heading{display:flex;
justify-content:space-between;align-items:baseline;gap:12px}.detail-heading h2{flex:1;min-width:0}
.detail-change{font-size:32px;font-weight:500;letter-spacing:-1px;font-variant-numeric:tabular-nums;
margin:14px 0 0;overflow-wrap:anywhere;line-height:1.25}.detail-change .unit{font-size:13px;
letter-spacing:0;color:var(--muted);font-weight:400}.change-label{font-size:12px;color:var(--muted);
margin:4px 0 14px}.detail-values{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;
margin:16px 0 0;padding:12px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.detail-values dt{font-size:11px;color:var(--muted)}.detail-values dd{font-size:13px;margin:3px 0 0;
font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.localization,.localization-empty{margin-top:18px}.window-range{font-size:12px;color:var(--muted);margin:5px 0}
.window-range strong{color:var(--ink);font-weight:600}.window-references{display:grid;
grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 16px;margin:12px 0;padding:10px 12px;
background:var(--bg);border-radius:5px}.window-references dt{font-size:11px;color:var(--muted)}
.window-references dd{margin:2px 0 6px;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.window-references dd:last-child{margin-bottom:0}.localization-method{margin-top:10px;padding-top:8px}
.localization-method summary{color:var(--muted)}.full-session-trace .details-content>figure{margin-top:8px}
.trace-heading{display:flex;justify-content:space-between;
gap:12px;align-items:baseline;flex-wrap:wrap}.trace-heading>span{font-size:12px;overflow-wrap:anywhere}
figure{margin:20px 0 0}.legend{display:flex;gap:12px 18px;flex-wrap:wrap;font-size:12px;
color:var(--muted);margin:9px 0 14px}.legend>span{display:flex;gap:7px;align-items:center}
.swatch{display:inline-block;width:21px;border-top:2px solid var(--accent)}.swatch.baseline{
border-color:var(--baseline);border-top-style:dashed}.chart{display:grid;grid-template-columns:minmax(35px,auto) minmax(0,1fr);
gap:6px 9px}.chart-y{height:188px;display:flex;flex-direction:column;justify-content:space-between;
font-size:12px;line-height:1;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
.chart-y>span:first-child{transform:translateY(-50%)}.chart-y>span:last-child{transform:translateY(50%)}
.chart svg{display:block;width:100%;height:188px;overflow:visible}.gridline{stroke:#e2e7ec;stroke-width:1;
vector-effect:non-scaling-stroke}.trace-line{fill:none;stroke-width:1.6;vector-effect:non-scaling-stroke}
.trace-line.baseline{stroke:var(--baseline);stroke-dasharray:5 3}.trace-line.candidate{stroke:var(--accent)}
.trace-point.baseline{fill:var(--baseline)}.trace-point.candidate{fill:var(--accent)}.chart-x{
grid-column:2;display:flex;justify-content:space-between;font-size:12px;color:var(--muted);
font-variant-numeric:tabular-nums}.chart-x.single{justify-content:center}.axis-title{grid-column:2;
font-size:12px;text-align:center;color:var(--muted)}figcaption{font-size:12px;margin:12px 0 0;
overflow-wrap:anywhere}details{border-top:1px solid var(--line);margin-top:18px;padding-top:12px}
summary{cursor:pointer;min-height:30px;font-size:12px;padding:3px 0;overflow-wrap:anywhere}
summary::marker{color:var(--accent)}.details-content{padding-top:6px;min-width:0}.table-scroll{
overflow:auto;max-width:100%;border:1px solid var(--line);border-radius:4px}.sample-table{border-collapse:collapse;
width:100%;font-size:12px;font-variant-numeric:tabular-nums}.sample-table th,.sample-table td{
padding:8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:top}
.sample-table th:first-child{text-align:left;white-space:normal;min-width:100px;overflow-wrap:anywhere}
.sample-table thead th{font-weight:500;background:var(--bg);color:var(--muted)}.sample-table tbody th{
font-weight:400}.back-link{font-size:12px;margin:16px 0 0}.evidence{margin-top:24px;padding-top:14px}
.evidence>summary{font-weight:500;font-size:13px}.evidence h2{font-size:15px;margin:12px 0}
.evidence h3{margin:14px 0 8px}.metadata{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
gap:24px}.metadata dl{margin:0}.metadata dt{font-size:11px;color:var(--muted);margin-top:12px}
.metadata dd{font-size:12px;margin:3px 0;overflow-wrap:anywhere}.mono,code,pre{font-family:ui-monospace,
SFMono-Regular,Consolas,monospace;font-size:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;
background:#edf1f5;border-radius:4px;padding:12px}.metric{overflow-wrap:anywhere}.provenance{
margin-top:18px}.provenance-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}
.provenance-grid>div{min-width:0}footer{font-size:11px;color:var(--muted);margin:24px 0 0;
overflow-wrap:anywhere}noscript p{font-size:12px;color:var(--muted)}
@media(max-width:900px){.enhanced .review-columns{grid-template-columns:1fr}
.enhanced .evidence-pane{position:static;max-height:none;overflow:visible;padding:0;margin:0;
scrollbar-gutter:auto}.session-detail{scroll-margin-top:12px}
main{padding:20px}.topbar-inner{padding:15px 20px}.metadata{grid-template-columns:1fr;gap:0}}
@media(max-width:480px){main{padding:18px 12px 28px}.topbar-inner{padding:14px 12px}h1{font-size:25px}
.session-detail{padding:16px 12px}.session-table th,.session-table td{padding:11px 6px}.session-link{
font-size:12px}.delta{font-size:13px}.score{font-size:12px}.coverage{text-align:left}.status-heading{
display:block}.coverage{margin-top:10px}.detail-values{gap:7px}.provenance-grid{grid-template-columns:1fr}
.run-context{gap:8px 18px}.detail-change{font-size:30px}.chart{column-gap:7px}}
@media print{body{background:#fff;font-size:11px}.enhanced .evidence-pane{position:static;
max-height:none;overflow:visible;padding:0;margin:0;scrollbar-gutter:auto}
.topbar,.skip-link,.back-link,#selection-announcement{
display:none!important}main{max-width:none;margin:0;padding:0}.review-columns,.enhanced .review-columns{
display:block}.session-detail,.session-detail[hidden]{display:block!important;border-radius:0;
margin-top:18px;break-inside:avoid}.session-detail:target{outline:none}.session-table{font-size:11px}
.session-table tr.is-selected{background:transparent}.session-table tr.is-selected>th{box-shadow:none}
.session-table th,.session-table td{padding:7px}.evidence{break-before:page}details> .details-content{
display:block!important}details::details-content{display:block!important;content-visibility:visible!important;
height:auto!important}details>summary{list-style:none;font-weight:600}.table-scroll{overflow:visible;
border:0}.sample-table{table-layout:fixed;font-size:9px}.sample-table th,.sample-table td{
white-space:normal;overflow-wrap:anywhere;padding:4px}.sample-table th:first-child{min-width:0}
.metadata{grid-template-columns:1fr}.provenance-grid{grid-template-columns:1fr}a{color:inherit;
text-decoration:none}pre{background:#fff;border:1px solid var(--line)}.description{max-width:none}}
"""

# This script is constant. Producer text exists only in escaped HTML, never in JS.
_SCRIPT = """(() => {
  'use strict';
  const root = document.getElementById('bci-report');
  if (!root) return;
  const links = Array.from(root.querySelectorAll('a[data-session-link]'));
  const panels = new Map(Array.from(root.querySelectorAll('section.session-detail'))
    .map(panel => [panel.id, panel]));
  const announcement = document.getElementById('selection-announcement');
  let selected = null;
  function select(id, moveFocus) {
    if (!panels.has(id)) return;
    panels.forEach((panel, key) => { panel.hidden = key !== id; });
    links.forEach(link => {
      const active = link.getAttribute('href') === '#' + id;
      if (active) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
      const row = link.closest('tr');
      if (row) row.classList.toggle('is-selected', active);
    });
    const panel = panels.get(id);
    const heading = document.getElementById(panel.getAttribute('aria-labelledby'));
    if (selected !== id && announcement && heading) {
      announcement.textContent = 'Selected session: ' + heading.textContent;
    }
    selected = id;
    if (moveFocus && heading) {
      heading.focus({preventScroll: true});
      if (window.innerWidth <= 900) panel.scrollIntoView({block: 'start'});
      else heading.scrollIntoView({block: 'nearest'});
    }
  }
  function fromLocation(moveFocus) {
    const id = window.location.hash.slice(1);
    if (panels.has(id)) select(id, moveFocus);
    else if (!selected || !id) select(panels.keys().next().value, moveFocus);
    if (id === 'comparison-evidence') {
      const evidence = document.getElementById('comparison-evidence');
      if (evidence) evidence.open = true;
    }
  }
  if (panels.size) {
    links.forEach(link => link.addEventListener('click', event => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
          event.shiftKey || event.altKey) return;
      const id = link.getAttribute('href').slice(1);
      if (!panels.has(id)) return;
      event.preventDefault();
      if (window.location.hash !== '#' + id) {
        try { window.history.pushState(null, '', '#' + id); }
        catch (_) { window.location.hash = id; }
      }
      select(id, true);
    }));
    root.classList.add('enhanced');
    fromLocation(false);
    window.addEventListener('hashchange', () => fromLocation(true));
    window.addEventListener('popstate', () => fromLocation(true));
  }
  let printState = null;
  window.addEventListener('beforeprint', () => {
    if (printState) return;
    printState = Array.from(root.querySelectorAll('details')).map(detail => [detail, detail.open]);
    printState.forEach(([detail]) => { detail.open = true; });
  });
  window.addEventListener('afterprint', () => {
    if (!printState) return;
    printState.forEach(([detail, wasOpen]) => { detail.open = wasOpen; });
    printState = null;
  });
})();"""


def _outcome(sessions: list[dict], complete: bool) -> str:
    if not complete:
        return "Incomplete comparison"
    valid = [row for row in sessions if row.get("status") == "valid"]
    if not valid:
        return "No valid session scores"
    deltas = [_finite(row.get("delta")) for row in valid]
    higher = sum(value is not None and value > 0 for value in deltas)
    lower = sum(value is not None and value < 0 for value in deltas)
    if len(valid) == 1:
        if higher:
            return "Higher RMSE in the session"
        if lower:
            return "Lower RMSE in the session"
        if deltas[0] == 0:
            return "Unchanged RMSE in the session"
    if higher:
        return f"Higher RMSE in {higher:,} of {len(valid):,} sessions"
    if lower == len(valid):
        return f"Lower RMSE in all {len(valid):,} sessions"
    if lower == 0 and all(value == 0 for value in deltas):
        return f"Unchanged RMSE in all {len(valid):,} sessions"
    return "No session has higher RMSE"


def render_report(result: dict) -> str:
    """Render supplied scores without modifying them or executing any model.

    Every session and its evidence is HTML-rendered and accessible without JS.
    A fixed optional script selects one evidence pane; no producer content is
    embedded into executable source. All display rounding is presentation only.
    """
    evaluation = result.get("evaluation", {})
    target_kind = evaluation.get("target_kind", "velocity")
    if target_kind not in ("velocity", "inferred_cursor_to_target_vector"):
        raise ValueError("Unsupported report target_kind")
    inferred_target = target_kind == "inferred_cursor_to_target_vector"
    target_notice = (
        '<p class="description target-semantics"><strong>Inferred cursor-to-target vectors.</strong> '
        'Targets are an inferred movement proxy, not measured intended velocities. '
        'Lower error means closer agreement with this proxy; this offline comparison '
        'does not establish better live BCI control.</p>'
        if inferred_target else ""
    )
    target_caption = (
        '<p class="caption target-semantics">Error against inferred cursor-to-target vectors, '
        'in the declared source coordinate units.</p>' if inferred_target else ""
    )
    x_field, y_field = ("x", "y") if inferred_target else ("vx", "vy")
    baseline = result.get("baseline", {})
    candidate = result.get("candidate", {})
    units = evaluation.get("units", "unspecified units")
    tolerance = result.get("tolerance")
    sessions = sorted(result.get("sessions", []), key=lambda row: (
        row.get("status") == "valid", -(_finite(row.get("delta")) or 0),
        str(row.get("session_id", "")),
    ))
    samples_by_session = defaultdict(list)
    valid_ids = {row.get("session_id") for row in sessions if row.get("status") == "valid"}
    maximum = 0.0
    for sample in result.get("samples", []):
        samples_by_session[sample.get("session_id")].append(sample)
        if sample.get("session_id") in valid_ids:
            for key in ("baseline_error", "candidate_error"):
                value = _finite(sample.get(key))
                if value is not None:
                    maximum = max(maximum, value)
    maximum = maximum or 1.0
    invalid = sum(row.get("status") != "valid" for row in sessions)
    regressions = sum(row.get("status") == "valid" and row.get("regression") is True for row in sessions)
    complete = result.get("complete") is True
    scored = sum(_finite(row.get("n_scored")) or 0 for row in sessions)
    expected = sum(_finite(row.get("n_expected")) or 0 for row in sessions)
    completeness = "Complete comparison" if complete else "Incomplete comparison"
    tolerance_text = (
        f'Regression reporting tolerance: {_number(tolerance)} {_text(units)}. '
        'Regression means candidate-minus-baseline RMSE exceeds this tolerance; '
        'within tolerance is not a deployment decision.'
        if tolerance is not None else
        'No regression reporting tolerance was specified. Deltas are descriptive; '
        'no categorical regression claim is made.'
    )
    flag_summary = (
        f'{regressions:,} above tolerance' if tolerance is not None else 'Descriptive deltas only'
    )
    description = result.get("description", "")
    description_html = f'<p class="description">{_text(description)}</p>' if description else ""
    rows, details = [], []
    for index, session in enumerate(sessions, start=1):
        session_id = session.get("session_id", "")
        anchor = f"session-{index}"
        valid = session.get("status") == "valid"
        flagged = valid and session.get("regression") is True and tolerance is not None
        row_class = "invalid" if not valid else ("regression" if flagged else "")
        badge = "Invalid" if not valid else (
            "Regression" if flagged else ("Descriptive" if tolerance is None else "Within tolerance")
        )
        badge_class = "badge bad" if not valid or flagged else "badge"
        issues = session.get("issues", [])
        delta = session.get("delta") if valid else None
        baseline_rmse = session.get("baseline_rmse") if valid else None
        candidate_rmse = session.get("candidate_rmse") if valid else None
        delta_class = "delta delta-up" if (_finite(delta) or 0) > 0 else "delta"
        issue_html = f'<p class="row-issues">{_text("; ".join(str(issue) for issue in issues))}</p>' if issues else ""
        rows.append(
            f'<tr class="{row_class}" data-session-row="{anchor}"><th scope="row">'
            f'<a class="session-link" data-session-link href="#{anchor}" aria-controls="{anchor}">'
            f'{_text(session_id)}</a><span class="row-meta"><span>'
            f'{_count(session.get("n_scored"))} / {_count(session.get("n_expected"))} samples</span>'
            f'<span class="{badge_class}">{badge}</span></span>{issue_html}</th>'
            f'<td class="{delta_class}">{_metric(delta, signed=True)}</td>'
            f'<td class="score">{_metric(baseline_rmse)}</td>'
            f'<td class="score">{_metric(candidate_rmse)}</td></tr>'
        )
        session_samples = samples_by_session.get(session_id, []) if valid else []
        evidence = (
            _session_evidence(session_samples, units, maximum, anchor, delta,
                              inferred_target=inferred_target)
            if valid else
            '<p>This session was not scored as a valid pair. Its missing or incompatible '
            'evidence remains part of the comparison.</p>'
        )
        details.append(
            f'<section class="session-detail" id="{anchor}" aria-labelledby="{anchor}-heading">'
            '<p class="eyebrow">Session evidence</p><div class="detail-heading">'
            f'<h2 id="{anchor}-heading" tabindex="-1">{_text(session_id)}</h2>'
            f'<span class="{badge_class}">{badge}</span></div>'
            f'<div class="detail-change{ " delta-up" if (_finite(delta) or 0) > 0 else ""}">'
            f'{_metric(delta, signed=True)} <span class="unit">{_text(units)}</span></div>'
            '<p class="change-label">Candidate − baseline RMSE · positive means higher error</p>'
            f'{target_caption}'
            '<dl class="detail-values"><div><dt>Baseline RMSE</dt>'
            f'<dd>{_metric(baseline_rmse)}</dd></div><div><dt>Candidate RMSE</dt>'
            f'<dd>{_metric(candidate_rmse)}</dd></div><div><dt>Scored / expected</dt>'
            f'<dd>{_count(session.get("n_scored"))} / {_count(session.get("n_expected"))}</dd></div></dl>'
            f'{_issues(issues)}{evidence}'
            '<p class="back-link"><a href="#comparison">Back to session comparison</a></p></section>'
        )
    pooled = result.get("pooled")
    if complete and pooled is not None:
        pooled_html = (
            '<p class="caption pooled">Sample-weighted pooled RMSE, secondary context: '
            f'{_number(pooled.get("baseline_rmse"))} → {_number(pooled.get("candidate_rmse"))} '
            f'{_text(units)}; change {_number(pooled.get("delta"), signed=True)} '
            f'across {_count(pooled.get("n_samples"))} samples.</p>'
        )
    else:
        pooled_html = '<p class="caption pooled">No complete pooled comparison is reported.</p>'
    excluded = result.get("excluded_counts", {})
    excluded_html = (
        '<p class="caption">Rows excluded by the declared evaluation selection: '
        f'evaluation {_count(excluded.get("evaluation", 0))}; '
        f'baseline {_count(excluded.get("baseline", 0))}; '
        f'candidate {_count(excluded.get("candidate", 0))}.</p>'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Decoder comparison · BCI Regression Workbench</title>'
        f'<style>{_CSS}</style></head><body>'
        '<a class="skip-link" href="#comparison">Skip to session comparison</a>'
        '<div class="topbar"><div class="topbar-inner"><span class="product">BCI Regression Workbench</span>'
        '<a href="#comparison-evidence">Identity &amp; scoring details</a></div></div>'
        '<main id="bci-report"><header><h1>Decoder comparison</h1>'
        '<div class="run-context"><div>Baseline'
        f'<strong>{_text(baseline.get("run_id", ""))}</strong></div><div>Candidate'
        f'<strong>{_text(candidate.get("run_id", ""))}</strong></div><div>Evaluation'
        f'<strong>{_text(evaluation.get("evaluation_id", ""))}</strong></div></div>'
        f'{description_html}{target_notice}</header><section class="status{" incomplete" if not complete else ""}" '
        'aria-label="Comparison status"><div class="status-heading">'
        f'<div><div class="outcome">{_outcome(sessions, complete)}</div><p>{flag_summary}</p></div>'
        f'<div class="coverage"><strong>{completeness}</strong><br>'
        f'{len(sessions) - invalid:,} / {len(sessions):,} valid sessions · {invalid:,} invalid<br>'
        f'{_count(scored)} / {_count(expected)} samples</div></div>'
        f'<p>{tolerance_text}</p>{_issues(result.get("issues", []))}</section>'
        '<div id="selection-announcement" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>'
        '<noscript><p>All session evidence is shown below. Session links jump directly to it.</p></noscript>'
        '<div class="review-columns"><section class="session-list" aria-labelledby="sessions-heading">'
        '<div class="section-heading"><h2 id="sessions-heading">All sessions</h2>'
        f'<span class="muted">RMSE · {_text(units)}</span></div><div class="table-frame" '
        'tabindex="0" role="region" aria-label="Session comparison table">'
        '<table class="session-table" id="comparison" tabindex="-1" aria-describedby="session-order">'
        '<colgroup><col style="width:37%"><col style="width:21%"><col style="width:21%"><col style="width:21%"></colgroup>'
        '<thead><tr><th scope="col">Session / coverage</th><th scope="col">Change ↓</th>'
        '<th scope="col">Baseline</th><th scope="col">Candidate</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        '<p class="caption" id="session-order">Invalid sessions appear first, followed by the largest '
        'candidate-minus-baseline RMSE. Positive changes indicate higher error. Select a session to inspect its evidence.</p>'
        f'{pooled_html}{excluded_html}</section><div class="evidence-pane" tabindex="0" '
        f'role="region" aria-label="Session evidence inspector">{"".join(details)}</div></div>'
        '<details class="evidence" id="comparison-evidence"><summary>Evaluation identity &amp; scoring details</summary>'
        '<div class="details-content"><section aria-labelledby="metric-heading">'
        '<h2 id="metric-heading">Metric and reproduction</h2>'
        f'<p class="metric"><code>Vector RMSE = sqrt(mean((predicted_{x_field} − target_{x_field})² '
        f'+ (predicted_{y_field} − target_{y_field})²))</code></p>'
        f'<p class="caption">RMSE and its change use {_text(units)}. Numerical reproduction tolerance: '
        f'{_number(result.get("numerical_tolerance"))} {_text(units)}. Display rounding does not change '
        'scores, sorting, or regression flags; the JSON bundle and CSV retain the recorded scores.</p>'
        '<p class="caption">The saved scoring bundle retains predictions, reference labels, eligibility, '
        'identities, and comparison settings. Recompute with <code>reproduce(bundle_dir)</code> using the '
        'recorded comparator source. This report does not certify that reproduction has been run.</p></section>'
        '<section aria-labelledby="identity-heading"><h2 id="identity-heading">Comparison identity</h2>'
        '<div class="metadata"><dl><dt>Baseline run</dt>'
        f'<dd>{_text(baseline.get("run_id", ""))}</dd><dt>Full output digest</dt>'
        f'<dd class="mono">{_text(baseline.get("digest", ""))}</dd></dl>'
        '<dl><dt>Candidate run</dt>'
        f'<dd>{_text(candidate.get("run_id", ""))}</dd><dt>Full output digest</dt>'
        f'<dd class="mono">{_text(candidate.get("digest", ""))}</dd></dl>'
        '<dl><dt>Evaluation set</dt>'
        f'<dd>{_text(evaluation.get("evaluation_id", ""))}</dd><dt>Full fingerprint</dt>'
        f'<dd class="mono">{_text(evaluation.get("fingerprint", ""))}</dd><dt>Declared purpose</dt>'
        f'<dd>{_text(evaluation.get("purpose", "unspecified"))}</dd></dl></div>'
        f'<p class="caption">Target units: {_text(units)} · Coordinates: '
        f'{_text(evaluation.get("coordinates", ""))} · Prediction horizon: '
        f'{_text(evaluation.get("horizon_ms", ""))} ms.</p>'
        '<details class="provenance"><summary>Producer-supplied provenance (not independently verified)</summary>'
        '<div class="details-content provenance-grid"><div><h3>Baseline</h3>'
        f'<pre>{_json_text(baseline.get("provenance", {}))}</pre></div><div><h3>Candidate</h3>'
        f'<pre>{_json_text(candidate.get("provenance", {}))}</pre></div></div></details></section></div></details>'
        '<footer>Scores describe supplied outputs and labels. Re-scoring does not verify model execution '
        'or training independence, and does not establish deployment readiness. Independent project; '
        'no Neuralink integration is implied.</footer></main>'
        f'<script id="report-interaction">{_SCRIPT}</script></body></html>'
    )
