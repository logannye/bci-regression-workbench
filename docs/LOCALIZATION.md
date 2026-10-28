# Session error localization

Selecting a valid session automatically shows the 24-scored-sample window with the largest positive sum of candidate-minus-baseline squared error. Short sessions use all their scored samples. The window uses the existing paired error values; it does not run models or change scores, thresholds, flags, eligibility, or denominators.

## Fixed display rule

Examine every sliding window of `min(24, scored_sample_count)` consecutive scored samples in evaluation order. Rank each window by:

```text
sum(candidate_error² − baseline_error²)
```

This compares the loss underlying vector RMSE before its final square root. Use the earliest window when sums tie, and show a selected window only if its net added squared error is strictly positive. Arithmetic uses exact rational representations of the supplied finite floating-point errors, avoiding overflow and cancellation in window ranking. This display calculation does not replace the scorer.

The window is a fixed sample count, not a fixed duration. Consecutive scored samples may span excluded samples or time gaps. Start/end sample IDs and timestamps retain the producer's convention; the report does not infer elapsed seconds or missing recording intervals.

The selected window's paired trace contains every selected sample, and Supporting samples uses that same window. The full-session trace remains available. If no window has positive net added error, the report says so and retains the ordinary session trace/sample preview. Invalid sessions remain invalid and have no localized evidence.

An overall-improved session can still contain a local increase. The selected window is an exploratory place to start investigation, not a categorical session regression, significance test, causal diagnosis, or deployment decision. Full-session scores and flags remain visible and authoritative for their original definitions.

## Acceptance case fixed before implementation validation

The `late-session-regression` synthetic fixture has 1,800 control samples and 600 affected-session samples. Baseline error is 1 throughout. Candidate error is 0.25 except for indices 540 through 563 inclusive of the affected session, where it is 6. The reporting tolerance is 0.1.

Acceptance requires complete scoring of all 2,400 samples, lower pooled RMSE, a regression flag only for the affected session, and automatic localization to `sample-0540` through `sample-0563`. These samples are outside the old first-24 preview. The saved comparison must reproduce. This is a constructed software test, not a neural-decoding result.

The broader checks cover independent brute-force window selection, ties, short/zero/no-positive cases, improving sessions with local loss, finite numerical extremes, invalid evidence, escaping, and unchanged input results. Browser validation checks session selection, exact source references, supporting samples, full-session context, and narrow-screen/keyboard behavior.

## Saved evidence and publication

The renderer participates in the comparator source identity. Old bundles and pins keep their recorded source. To update the public demo, load its saved original inputs into a new comparison directory, preserve all settings, and verify equality of every result field except the comparator source digest. Never overwrite or rebind the original inputs, refit the models, or change the completed experiment.

Publish only the reviewed report snapshot, unchanged aggregate CSV, and publication identities. The original public result remains lower error on all three sessions; localization does not manufacture a session regression.

## Local validation

Implementation revision `772d008ee7e1c78bdae67c48723b696548c3f354`, renderer SHA-256 `261cc328c354e8b065b4c728eabeeae72670245024d08c9cb6097dc5ab5a5c24`, passed 135 local tests with nine optional-dependency skips (144 discovered), including all 18 localization tests. Python 3.14.6 on macOS arm64 was used; see the [aggregate receipt](validation/localization-v1.json) for the exact platform and source identities. The fixed report script passed Node syntax validation and is unchanged.

Nine generated comparison bundles reproduced. The fixed late-session case selected indices `[540, 564)` and sample IDs `sample-0540` through `sample-0563`; pooled RMSE decreased from 1 to 0.649519 while the affected session increased from 1 to 1.224745. Every one of its 2,400 samples was retained. All 14,052 public samples and every original result field except source digest remained identical; the old public bundle also reproduced with archived pre-change source. No models were refitted or executed.

Browser checks passed for nine states at three viewport sizes (27 combinations), with no document-wide horizontal overflow or console errors. Clicking or keyboard-selecting the affected session revealed the correct late interval; its supporting table contained exactly those 24 sample IDs. Full-session expansion, browser history, and fragment reload passed. Mobile selection placed the evidence panel about 12px below the viewport top. The two initial old report-test failures were obsolete expectations about preview wording and the number of charts; their evidence-preservation assertions remain enforced.

Hosted checks and deployment status are attached to the publication pull request/commit. These targeted checks do not establish screen-reader conformance, actual print/PDF behavior, production-scale performance, or intended-engineer usability.
