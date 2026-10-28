# Report interface

The report supports one review task: compare the candidate with its fixed baseline, identify sessions requiring attention, and inspect their paired evidence.

## Layout and interaction

The header shows the baseline, candidate, and evaluation identities. A factual outcome statement sits beside completeness and exact sample coverage. Performance and input validity remain separate: a complete comparison is not deployment approval, and an unset reporting tolerance produces descriptive deltas only.

On desktop, the session table sits beside a bounded, sticky evidence pane. Its native scrolling and keyboard focus let users inspect longer evidence without losing the selected row in a longer session list. Invalid sessions stay first; valid sessions retain descending candidate-minus-baseline RMSE order. The signed change and its units are visually primary. Every session, both scores, and scored/expected counts remain available. Selecting a native session link updates the evidence pane, and the URL hash supports direct links and browser history.

On narrow screens the panes stack. Supporting sample tables and full provenance use native disclosures. The paired-error preview distinguishes baseline and candidate through line style and labels, uses an explicit shared vertical scale, and retains sample-order axes; timestamps are not silently interpreted as elapsed time. Preview sampling never changes the scoring population.

The page contains its own styles and a fixed, small enhancement script. Producer text is escaped into HTML and never interpolated into that script. No external assets, network calls, framework, new metrics, or model execution are required. Without JavaScript, all session sections remain available through ordinary anchors. Print handling exposes all sessions and supporting details.

## Evidence compatibility

`report.py` participates in the existing comparator source digest. A renderer change therefore gives newly produced bundles a new source identity even when scoring arithmetic is unchanged. Existing reports, manifests, and pins must not be overwritten or relabeled.

Use the recorded source revision to reproduce an older bundle. To review the same already-exported outputs with a newer report, load the original `EvaluationSet` and both `PredictionSet` bundles, preserve the original tolerance/description, and call `compare` into a new directory. This recomputes scores without training or inference. Verify the result payload against the original, excluding only `comparator_source_digest`, and verify that the original files remain unchanged. Pins also bind source identity, so an older pin continues to require its recorded source; creating a new reference is explicit.

The original Indy evidence remains at its original revision. The UI validation fixture generator can create a separate public replay while enforcing these checks:

```sh
PYTHONPATH=src python3 tests/report_ui_fixtures.py \
  --output-dir runs/report-ui-new \
  --public-bundle /path/to/original/comparison
```

The public-bundle argument is optional. The seven synthetic states cover a hidden session regression, invalid required predictions, global-only incompleteness, descriptive mixed signs, long/hostile text, a zero-error singleton, and within/exact/above-tolerance boundaries. Every generated bundle is score-reproduced.

## Validation

Local validation passed against renderer SHA256 `7e60809d927a997acc548540611ea8bac3763f19f8dfa229383c9920de62d97d`; hosted validation is pending.

- Python 3.14.6 on macOS Darwin 25.2.0 arm64: 126 tests discovered, 117 passed, nine optional-dependency skips. All 14 report-specific tests passed. Node 24.3.0 syntax-checked the fixed script.
- Eight real-comparator fixture states passed browser checks at 1265 × 712, 390 × 844, and 320 × 740 in the ChatGPT in-app browser: 24 state/viewport combinations, no document-wide horizontal overflow or browser console errors. Narrow score tables scroll locally when required; chart labels retain 12px text.
- Mouse and keyboard selection, visible focus, collapsed sample expansion, URL-fragment reload, browser back, and escape by Tab from the evidence pane were checked. A 40-session fixture preserved both the selected row and evidence heading in the desktop viewport. Mobile selection placed the panel 12px below the top. Removing only the fixed script exposed all four synthetic sessions and preserved native anchor navigation.
- Initial browser checks found excessive row spacing, mobile selection stopping at the viewport bottom, word-broken table headers, and loss of selected-row context with a tall evidence pane. These were repaired and the final interface rechecked. Initial test failures also exposed old display-format/copy assumptions; exact input/flag preservation and script-isolation assertions remain enforced.
- Five representative text/surface color pairs were checked, with minimum calculated contrast 5.359:1. This is a targeted check, not a full accessibility conformance audit.
- The original public bundle score-reproduced using archived source `be134e06cc01359715347ed2f43956733c7127d9`. A new bundle loaded its saved inputs without rebinding them, preserved every result field except `comparator_source_digest`, reproduced under the new source, and left the original files unchanged. All 14,052 public samples and their scores are identical. No new model fit, inference, or recording download occurred.
- `core.py`, `tables.py`, `__init__.py`, `pinned.py`, and the frozen public producer were not changed. The pinned example still initializes once and produces/reproduces two ordinary candidate reports.

Full comparison bundles, browser receipts, and desktop/mobile screenshots are retained in this task's local output. Print styles and the before/after-print handlers were reviewed, but an actual print/PDF dialog was not exercised. Production-scale performance, other browser engines, screen-reader usability, and intended-engineer usability remain untested. This is interface validation, not intended-engineer usability or Neuralink internal integration evidence.
