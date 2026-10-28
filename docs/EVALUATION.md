# Evaluation

Status: planned criteria. Nothing in this document is a completed experimental result.

## One task and one primary metric

For each session, predict the two components of velocity at a fixed, declared horizon. Compare them with the recording's compatible target labels. Coordinate conventions and units must match; a task target or intended destination is not automatically a velocity label.

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

Freeze sessions, valid masks, preprocessing, model identities, prediction horizon, and tolerance before evaluation. Use the same samples for both models. A prediction failure does not authorize dropping its sample from either model's denominator.

Evaluation labels stay outside the decoder interface. Any training or model selection occurs separately and must not use the held-out sessions. Record grouping and overlap checks appropriate to the chosen dataset. Within-session time samples are correlated; the report must not treat them as independent subjects or claim population-wide efficacy.

Numerical repeatability tolerance and regression-reporting tolerance are different concepts. Declare both before validation. The first allows documented numerical variation across repeated computations; the second governs which measured performance changes are highlighted.

## Invalid evidence

Missing or duplicate required predictions, mismatched IDs, nonfinite values, incompatible units/features, missing labels, empty scoring masks, and changed source/model hashes produce an explicit invalid result. Preserve the reason and artifact identities. Never convert missing evidence into zero error, silently repair it, or hide the affected session.

If any required session is invalid, mark the overall comparison incomplete. Valid session rows may still be inspected, but the run cannot be described as a complete comparison.

## Acceptance cases

These cases test the implementation's correctness. They are not a second scientific benchmark or a general fault-injection feature.

| Case | Required observation |
| --- | --- |
| Identical decoders | Every valid session has a zero delta within the declared numerical tolerance. |
| Hand-calculated fixture | The implementation matches independently calculated vector RMSE and sample counts. |
| Hidden session regression | A constructed candidate improves pooled RMSE but worsens one designated session; the report exposes that session. |
| Invalid comparison | A missing prediction, changed digest, or mismatched sample identity remains visible and makes the comparison incomplete. |
| Reproduction | A fresh environment recovers the same session rows and scores within the declared tolerance from the saved bundle. |
| One public-data demonstration | A fixed baseline/candidate comparison produces a complete, inspectable report with documented source and model provenance. Improvement is not required. |

Develop the evaluator against synthetic fixtures first. Then freeze the public-data evaluation before running it. Report failures, unchanged results, and limitations as observed; do not select a flattering subset of sessions after looking at scores.

## Interpretation

The result concerns predictive error on the supplied recordings. It cannot recreate the feedback between a user and a different decoder, establish interactive cursor control, or predict performance on Neuralink's private data. For the intended engineer, it is evidence to investigate a change and plan subsequent evaluation.
