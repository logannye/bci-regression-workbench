# Evaluation

Status: scoring and validity rules are implemented, with synthetic fixtures and a local workflow example. Public-recording evaluation remains planned. Implementation checks are not neural-decoder performance results.

## One task and one primary metric

For each session, compare two existing sets of velocity predictions with the recording's compatible target labels at a fixed, declared horizon. Coordinate conventions and units must match; a task target or intended destination is not automatically a velocity label. The workbench does not generate these predictions.

For N valid samples, define velocity vector RMSE as:

```text
RMSE = sqrt(sum((predicted_vx - target_vx)^2
              + (predicted_vy - target_vy)^2) / N)
delta = candidate_RMSE - baseline_RMSE
```

This is the root mean squared Euclidean velocity error, with no additional division by the number of coordinates. It retains the velocity units. Positive delta means the candidate is worse on that session.

Always show raw deltas. Choose the absolute reporting tolerance, in the same units, before opening evaluation results. A regression flag means the delta exceeds that tolerance; it is not a statistical-significance claim, a clinical threshold, or a deployment decision. If no meaningful tolerance is specified, report descriptive deltas without a categorical claim.

A pooled RMSE may provide context using the same formula over all valid samples. It must be labeled sample-weighted and must never replace the per-session table. A partial run must not present a pooled result as a complete comparison.

## Fair comparison

Freeze sessions, valid masks, target semantics, baseline/candidate identities, and tolerance before comparing candidate results. The prediction producer must record its model and preprocessing versions. Use the same scoring keys for both outputs. A prediction failure does not authorize dropping its sample from either model's denominator.

For the future public-recording demonstration, the prediction producer must keep evaluation labels out of model inference and model selection, use causal inputs, and declare reset boundaries. The current synthetic example constructs outputs directly and does not run a decoder. An imported output bundle cannot independently prove execution or training properties. Record supplied provenance and treat it as unverified. Do not describe an imported comparison as verified held-out evaluation solely because its metadata says "test."

Align against the expected evaluation keys, never row position or a surviving inner-join subset. Within-session time samples are correlated; the report must not treat them as independent subjects or claim population-wide efficacy.

A reusable regression set supports day-to-day development. If its results influence candidate selection, it is development evidence, even if its labels were not used for fitting. Record that evaluation purpose and do not describe repeated comparisons as an untouched final assessment. A separate sealed assessment remains the team's existing evaluation responsibility; this tool does not create or manage it.

Numerical repeatability tolerance and regression-reporting tolerance are different concepts. Declare both before validation. The first allows documented numerical variation across repeated computations; the second governs which measured performance changes are highlighted.

## Invalid evidence

The evaluation table must first define an unambiguous scoring population. Empty tables, duplicate evaluation keys, malformed labels/timestamps, and invalid eligibility declarations raise an error in `EvaluationSet.from_records`. Missing or tampered saved bundles also fail during loading. No comparison report is claimed for an input that cannot establish that contract.

Given a valid evaluation table, missing or duplicate required predictions, malformed prediction values, empty session scoring masks, and incompatible prediction-bundle identities or semantics produce explicit invalid session rows. Unexpected prediction keys make the overall comparison incomplete. In-memory content mutations are detected before scoring. The report retains issues and every declared session; it never converts missing evidence into zero error or silently scores a surviving subset.

If any required session is invalid, mark the overall comparison incomplete. Valid session rows may still be inspected, but the run cannot be described as a complete comparison.

## Acceptance cases

These cases test implementation correctness. The core/report cases have corresponding synthetic tests; actual validation runs and their platforms must be recorded separately. They are not a second scientific benchmark or a general fault-injection feature.

| Case | Required observation |
| --- | --- |
| Identical prediction outputs | Every valid session has a zero delta within the declared numerical tolerance. |
| Hand-calculated fixture | The implementation matches independently calculated vector RMSE and sample counts. |
| Hidden session regression | A constructed candidate improves pooled RMSE but worsens one designated session; the report exposes that session. |
| Invalid comparison | A missing prediction or mismatched scoring identity remains visible and makes the comparison incomplete. Unloadable or tampered bundles fail explicitly. |
| Row order and target identity | Permuting file rows preserves results when keys match; incompatible targets or horizons are rejected. |
| Scoring reproduction | A fresh environment recovers the same session rows and scores from preserved predictions and labels without model loading. |
| One public-data demonstration — planned | A fixed baseline/candidate comparison produces a complete, inspectable report with documented source and model provenance. Improvement is not required. |
| Recurring workflow — synthetic example implemented | A sample producer saves the pinned baseline once, loads it for a subsequent candidate ID, and creates the report as part of its normal invocation. The one-open, one-session-selection interaction remains a usability check, not an established Neuralink workflow. |

The standard-library tests and [basic example](../examples/basic_comparison.py) exercise constructed outputs. The optional real datarepo/Parquet example awaits hosted validation. Freeze the future public-data demonstration before running its separate prediction producer. Report failures, unchanged results, and limitations as observed; do not select a flattering subset of sessions after looking at scores.

## Interpretation

The result concerns the error of supplied predictions against supplied reference labels. Reproducing that arithmetic does not establish reproducible model execution or valid training provenance. It cannot recreate the feedback between a user and a different decoder, establish interactive cursor control, or predict performance on Neuralink's private data. For the intended engineer, it is evidence to investigate a change and plan subsequent evaluation.
