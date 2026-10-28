# Implementation plan

The project has one core benefit: identify and reproduce session-level prediction regressions. Additions that do not directly support it are outside scope.

## 1. Freeze the smallest useful comparison

- [ ] Select one public multi-session dataset with compatible neural features and two-dimensional velocity labels; verify access and reuse terms.
- [ ] Establish grouping, training/evaluation boundaries, source hashes, and target semantics.
- [ ] Choose one simple decoder family and freeze baseline/candidate provenance without using the evaluation split for selection.
- [ ] Fix the metric, numerical tolerance, and regression-reporting rule in a dated evaluation manifest.

Done when the comparison is fully specified and evaluation data access is governed by that specification. If dataset feasibility fails, revise the specification before evaluating another dataset.

## 2. Implement the comparison

- [ ] Add the single data loading path through `datarepo` and validate session identities.
- [ ] Implement the fixed-decoder runner and paired RMSE calculation.
- [ ] Produce the complete session table, concise report, and reproduction bundle.
- [ ] Verify the synthetic acceptance cases in [Evaluation](EVALUATION.md).

Done when a constructed pooled improvement cannot conceal a session regression, and invalid evidence cannot disappear from the report.

## 3. Reproduce and present

- [ ] Run the frozen public-data comparison and preserve all results.
- [ ] Reproduce the report in a clean environment with the tested revision and platform recorded.
- [ ] Prepare a short demonstration: select two decoders, see the affected session, inspect its paired errors, and reproduce the result.
- [ ] Document the small input mapping an engineer would need to try their own permitted recordings.

Done when another engineer can reproduce the finding from the repository instructions. Present the observed results, not a promise of internal adoption.

## Current state

All implementation milestones are open. This initial repository is a planning artifact. No dataset has been downloaded, decoder trained, model evaluated, or Neuralink integration tested.
