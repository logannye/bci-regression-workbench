# Evaluation

Status: scoring and validity rules have passed synthetic checks locally and in hosted CI. The real datarepo/Parquet integration and scoring reproduction passed at the revisions/platforms in [Validation](VALIDATION.md). The prospectively frozen Indy demonstration is complete, with an independent audit and scoring reproduction; see [Indy results](public-demo/RESULTS.md). The [human demonstration](human-demo/PLAN.md) has a separate frozen protocol. Implementation tests and the bounded recording results are distinct evidence.

## One task and one primary metric

For each session, compare two existing sets of two-dimensional predictions with compatible reference labels at a fixed, declared horizon. Coordinate conventions, units, and target kind must match; a task target or intended destination is not automatically a velocity label. Velocity remains the default. The workbench does not generate these predictions.

For N valid samples, define vector RMSE as:

```text
RMSE = sqrt(sum((predicted_vx - target_vx)^2
              + (predicted_vy - target_vy)^2) / N)
delta = candidate_RMSE - baseline_RMSE
```

This is the root mean squared Euclidean error, with no additional division by the number of coordinates. It retains the declared target units. The canonical column names above are preserved for compatibility; their meaning is determined by the explicitly bound target kind. Positive delta means the candidate is worse against those labels on that session.

Always show raw deltas. Choose the absolute reporting tolerance, in the same units, before opening evaluation results. A regression flag means the delta exceeds that tolerance; it is not a statistical-significance claim, a clinical threshold, or a deployment decision. If no meaningful tolerance is specified, report descriptive deltas without a categorical claim.

A pooled RMSE may provide context using the same formula over all valid samples. It must be labeled sample-weighted and must never replace the per-session table. A partial run must not present a pooled result as a complete comparison.

## Declared target semantics

`EvaluationSet.from_records` supports exactly two target kinds:

| `target_kind` | Interpretation | Manifest metric |
| --- | --- | --- |
| `"velocity"` (default) | Two-dimensional velocity predictions and compatible velocity labels, in declared velocity units. | `velocity_vector_rmse` |
| `"inferred_cursor_to_target_vector"` | Two-dimensional cursor-to-target displacement used as an inferred movement proxy, in declared source coordinate units. | `inferred_target_vector_rmse` |

The second kind does not turn displacement into velocity or establish measured intention. MINDFUL's stored `labels` agree with `targetPos - cursorPos` to float32 rounding. Its recorded `cursorVel` is an output of the original online decoder, not our reference target. Lower proxy error does not establish better live control.

The inferred kind is included in evaluation fingerprints and prediction digests, checked during comparison and pinned-reference reuse, and shown prominently in the report. Changing it requires a new evaluation and pin. Unknown kinds are rejected. Default velocity serialization, fingerprints, output schema, and display remain compatible; older complete bundles still require their recorded comparator source. The same RMSE arithmetic, masks, flags, and localization rule apply to both supported kinds. This is a narrow semantic extension, not a configurable metrics system.

## Fair comparison

Freeze sessions, valid masks, target semantics, baseline/candidate identities, and tolerance before comparing candidate results. The prediction producer must record its model and preprocessing versions. Use the same scoring keys for both outputs. A prediction failure does not authorize dropping its sample from either model's denominator.

The completed Indy public-recording demonstration uses a separate prediction producer that keeps evaluation labels out of model inference and model selection, uses causal inputs, and declares reset boundaries. Its source-only fitting and saved predictions were audited separately from the comparator. The separately frozen human experiment uses released features described as noncausal; current/past-bin history does not establish end-to-end causal preprocessing. The synthetic example constructs outputs directly and does not run a decoder. An arbitrary imported output bundle cannot independently prove execution or training properties. Record supplied provenance and treat it as unverified. Do not describe an imported comparison as verified held-out evaluation solely because its metadata says "test."

Align against the expected evaluation keys, never row position or a surviving inner-join subset. Within-session time samples are correlated; the report must not treat them as independent subjects or claim population-wide efficacy.

A reusable regression set supports day-to-day development. If its results influence candidate selection, it is development evidence, even if its labels were not used for fitting. Record that evaluation purpose and do not describe repeated comparisons as an untouched final assessment. A separate sealed assessment remains the team's existing evaluation responsibility; this tool does not create or manage it.

Numerical repeatability tolerance and regression-reporting tolerance are different concepts. Declare both before validation. The first allows documented numerical variation across repeated computations; the second governs which measured performance changes are highlighted.

## Invalid evidence

The evaluation table must first define an unambiguous scoring population. Empty tables, duplicate evaluation keys, malformed labels/timestamps, and invalid eligibility declarations raise an error in `EvaluationSet.from_records`. Missing or tampered saved bundles also fail during loading. No comparison report is claimed for an input that cannot establish that contract.

Given a valid evaluation table, missing or duplicate required predictions, malformed prediction values, empty session scoring masks, and incompatible prediction-bundle identities or semantics produce explicit invalid session rows. Unexpected prediction keys make the overall comparison incomplete. In-memory content mutations are detected before scoring. The report retains issues and every declared session; it never converts missing evidence into zero error or silently scores a surviving subset.

If any required session is invalid, mark the overall comparison incomplete. Valid session rows may still be inspected, but the run cannot be described as a complete comparison.

## Acceptance cases

These cases test implementation correctness. The core/report cases have corresponding synthetic tests; completed runs and their platforms are recorded in [Validation](VALIDATION.md). They are not a second scientific benchmark or a general fault-injection feature.

| Case | Required observation |
| --- | --- |
| Identical prediction outputs | Every valid session has a zero delta within the declared numerical tolerance. |
| Hand-calculated fixture | The implementation matches independently calculated vector RMSE and sample counts. |
| Hidden session regression | A constructed candidate improves pooled RMSE but worsens one designated session; the report exposes that session. |
| Invalid comparison | A missing prediction or mismatched scoring identity remains visible and makes the comparison incomplete. Unloadable or tampered bundles fail explicitly. |
| Row order and target identity | Permuting file rows preserves results when keys match; incompatible targets or horizons are rejected. |
| Scoring reproduction | A fresh environment recovers the same session rows and scores from preserved predictions and labels without model loading. |
| One public-data demonstration — completed | The frozen public run produced a complete report for all three selected sessions, with documented source/model provenance, an independent audit, and hosted/local scoring reproduction. Candidate RMSE was lower on all three; no regression was forced. See [results](public-demo/RESULTS.md). |
| Recurring workflow — synthetic example checked | A sample producer saves the pinned baseline once, loads it for a subsequent candidate ID, and creates the report as part of its normal invocation. Browser inspection confirmed the session table is visible on opening and one session-row selection reaches its trace. This is an example interaction check, not intended-engineer usability evidence or an established Neuralink workflow. |

The standard-library tests and [basic example](../examples/basic_comparison.py) exercise constructed outputs. Hosted runs also exercised the optional real datarepo/Parquet example, and a downloaded CI artifact was score-reproduced locally; see [Validation](VALIDATION.md). The separate public-data producer followed its frozen [protocol](public-demo/protocol-v1.json). Report failures, unchanged results, and limitations as observed; do not select a flattering subset of sessions after looking at scores.

## Completed Indy public-recording demonstration

Two ridge models were fitted once each using the first 300 seconds of the September 15, 2016 Indy recording. The baseline uses the current 64 ms neural bin; the candidate uses that bin and three preceding bins. Both were scored on the same 4,684 eligible samples per session from September 16, September 21, and September 27, with no evaluation-label fitting or post-result model selection. Targets are measured two-dimensional cursor velocity, not intended motion or future cursor control.

The candidate had lower vector RMSE in all three selected sessions. Reporting tolerance was `None`, so the report preserves descriptive deltas without categorical regression flags. The synthetic fixture remains the demonstration of a pooled improvement hiding a session regression. Neither outcome is a prerequisite for the comparator to work.

Hosted run `40738828979` tested merge revision `ff10e82d` for head `3bb6995`: 99 tests ran, with 97 passing and two optional Arrow skips. The independent audit and saved-score reproduction passed in the hosted run and locally. Exact identities, environment, scores, and evidence are in [Public demonstration results](public-demo/RESULTS.md). This is a bounded offline demonstration; intended-engineer usability and Neuralink integration remain untested.

## Frozen human recording demonstration

The [MINDFUL T11 plan](human-demo/PLAN.md) was committed after structural inspection and before model fitting. It includes all 29 released blocks from 15 center-out-and-back recording days. The earliest three days supply training; all twelve later days supply evaluation. The fixed masks retain 85,423 training samples and 324,732 evaluation samples. Both models receive the same scoring keys and exclusions.

The baseline uses the current 20 ms neural bin; the candidate adds three preceding bins, with history reset at each trial and block. Both are simple fixed ridge models fitted by a separate example producer, not the participant's original online LSTM. Targets remain the released inferred displacement vectors without velocity conversion or normalization. Reporting tolerance is `None`, and success means a complete, reproducible comparison with independent audit, regardless of the sign of any score change. The [protocol](human-demo/protocol-v1.json) defines the precise admission, fitting, exclusion, and failure rules.

## Interpretation

The result concerns the error of supplied predictions against supplied reference labels. Reproducing that arithmetic does not establish reproducible model execution or valid training provenance. It cannot recreate the feedback between a user and a different decoder, establish interactive cursor control, or predict performance on Neuralink's private data. For the intended engineer, it is evidence to investigate a change and plan subsequent evaluation.
