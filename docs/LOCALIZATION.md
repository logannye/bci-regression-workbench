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
