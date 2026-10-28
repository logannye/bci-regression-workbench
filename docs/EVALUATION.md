# Evaluation

Status: planned criteria. Nothing in this document is a completed experimental result.

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

In the public demonstration, the prediction producer keeps evaluation labels out of model inference and model selection, uses causal inputs, and declares reset boundaries. An imported output bundle cannot independently prove these properties. Record supplied training/execution provenance and mark absent evidence unverified. Do not describe an imported comparison as verified held-out evaluation solely because its metadata says "test."

Align against the expected evaluation keys, never row position or a surviving inner-join subset. Within-session time samples are correlated; the report must not treat them as independent subjects or claim population-wide efficacy.

A reusable regression set supports day-to-day development. If its results influence candidate selection, it is development evidence, even if its labels were not used for fitting. Record that evaluation purpose and do not describe repeated comparisons as an untouched final assessment. A separate sealed assessment remains the team's existing evaluation responsibility; this tool does not create or manage it.

Numerical repeatability tolerance and regression-reporting tolerance are different concepts. Declare both before validation. The first allows documented numerical variation across repeated computations; the second governs which measured performance changes are highlighted.

## Invalid evidence

Missing or duplicate required predictions, mismatched IDs, nonfinite values, incompatible target units/coordinates/horizon, missing labels, empty scoring masks, and changed prediction/label content identities produce an explicit invalid result. Preserve the reason and artifact identities. Never convert missing evidence into zero error, silently repair it, or hide the affected session.

If any required session is invalid, mark the overall comparison incomplete. Valid session rows may still be inspected, but the run cannot be described as a complete comparison.

## Acceptance cases

These cases test the implementation's correctness. They are not a second scientific benchmark or a general fault-injection feature.

| Case | Required observation |
| --- | --- |
| Identical prediction outputs | Every valid session has a zero delta within the declared numerical tolerance. |
| Hand-calculated fixture | The implementation matches independently calculated vector RMSE and sample counts. |
| Hidden session regression | A constructed candidate improves pooled RMSE but worsens one designated session; the report exposes that session. |
| Invalid comparison | A missing prediction, changed digest, or mismatched sample identity remains visible and makes the comparison incomplete. |
| Row order and target identity | Permuting file rows preserves results when keys match; incompatible targets or horizons are rejected. |
| Scoring reproduction | A fresh environment recovers the same session rows and scores from preserved predictions and labels without model loading. |
| One public-data demonstration | A fixed baseline/candidate comparison produces a complete, inspectable report with documented source and model provenance. Improvement is not required. |
| Recurring workflow | After one-time setup, an ordinary candidate evaluation creates the report automatically; one action opens it and one selects a session. |

Develop the comparator against synthetic prediction fixtures first. Then freeze the public-data demonstration before running its separate prediction producer. Report failures, unchanged results, and limitations as observed; do not select a flattering subset of sessions after looking at scores.

## Interpretation

The result concerns the error of supplied predictions against supplied reference labels. Reproducing that arithmetic does not establish reproducible model execution or valid training provenance. It cannot recreate the feedback between a user and a different decoder, establish interactive cursor control, or predict performance on Neuralink's private data. For the intended engineer, it is evidence to investigate a change and plan subsequent evaluation.
