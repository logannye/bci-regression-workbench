# Frozen human recording demonstration

This experiment asks whether adding recent neural history changes offline prediction error on later recording days. It demonstrates the existing baseline/candidate review workflow using one person's public implanted-BCI recordings. It does not reproduce MINDFUL, compare against the participant's online decoder, or estimate a new decoder's live control performance.

The authoritative [protocol](protocol-v1.json) was committed after [structural inspection](inspection-v1.json), before any model fitting or decoder comparison. Inspection read labels to verify their meaning and checked shapes, file hashes, trial bounds and exclusions. Published study conclusions were already known. This is a prospectively specified engineering demonstration, not a blinded scientific validation.

## Data and access

Pun et al. (2024), *Measuring instability in chronic human intracortical neural recordings towards stable, long-term brain-computer interfaces*. [Dryad DOI](https://doi.org/10.5061/dryad.n2z34tn5s), version 6 / API version ID 324345, CC0-1.0. The ordinary browser download succeeded after direct automated downloads returned HTTP 403 and the API download required authentication. The original 411,951,588-byte archive matches the official SHA-256 `6d12b5dbcf9cac654ff1d0679e9753bf042b56cd5b8852eb31236b3cdecf7332`.

All 29 blocks from T11's 15 center-out-and-back recording days are included. T5 and T11(additional) are outside scope. The actual release has 1,839 trials and 35 exclusion flags, different from the manuscript's 1,840 and 34. We preserve the released files, including their exclusions.

## Fixed comparison

| Decision | Frozen choice |
| --- | --- |
| Training | All six blocks from the earliest three days: 658, 665, 672. |
| Evaluation | All 23 blocks from all twelve later days: 675, 689, 692, 702, 709, 715, 727, 751, 758, 770, 783, 800. |
| Neural input | All 192 released nctx columns at native 20 ms bins. |
| Target | Stored two-dimensional cursor-to-target displacement, unchanged and in dataset coordinate units. |
| Baseline | Ridge regression from the current released neural bin. |
| Candidate | The same ridge procedure with the current and three previous bins. |
| Fit | One deterministic fit per model; source-only mean/std, mean-loss ridge penalty 1, unpenalized intercept. |
| Metric | Per-day vector RMSE; candidate minus baseline. No categorical reporting threshold. |
| Success | Complete, reproducible comparison and independent audit. Neither improvement nor regression is required. |

Trial bounds are MATLAB one-based inclusive. Exclude bins outside task trials, source-excluded trials, and the first three bins of every remaining trial for both models. History resets at each trial and block. Preserve excluded rows and their reasons; keep valid zero targets. This gives 85,423 training bins and 324,732 evaluation bins. Both models use exactly those denominators.

Source-fitted normalization is per design column, with population standard deviation (`ddof=0`) and exactly zero standard deviation replaced by one. The loss is the mean squared two-component residual plus `1 * sum(weights**2)`. There is no test-day scaling, adaptation, hyperparameter search or outcome-based selection.

Both fitted models and all evaluation predictions must be saved before the execution pipeline loads evaluation labels. The earlier structural inspection is explicitly acknowledged. The shared comparator then binds exports to their evaluation identity, pins the baseline once, and compares the candidate through the existing hook.

## Interpretation and boundaries

These labels agree with `targetPos - cursorPos` to float32 rounding. They are inferred displacement proxies, not measured intention or velocity. RMSE measures agreement with that proxy. Recorded cursor velocity is an output of the original online decoder and is not our ground truth.

The released threshold-crossing features are described as noncausal. Current/past-bin history does not establish end-to-end causal preprocessing. This experiment makes no timing claim.

Reports group blocks by recording day. Sample IDs retain the block and original one-based bin. Timestamps concatenate recorded bins within a day and omit unknown pauses; they are not wallclock times. Existing localization may span excluded samples or block boundaries and remains an exploratory starting point.

Keep all selected days even when results are unfavorable. Abort on admission failure; preserve failures. Repairs may fix implementation under the same protocol, but changing scientific choices requires a new experiment. Publish only the bounded report, aggregate scores, source identities and validation receipts. Full recordings, labels, predictions and fitted models remain outside Git.
