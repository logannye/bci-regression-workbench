# Implementation plan

The project has one core benefit: identify and reproduce session-level prediction regressions. Integrate at the output of an existing evaluator. Do not require users to adopt a new model runner.

## 1. Build the smallest correct comparison

- [ ] Fix the keyed prediction/target contract and one metric in [Design](DESIGN.md) and [Evaluation](EVALUATION.md).
- [ ] Implement the Python comparison function over typed tables, with explicit baseline and evaluation-set identities.
- [ ] Verify hand-calculated scores, the hidden-session tradeoff, keyed alignment, and invalid-evidence cases on synthetic outputs.
- [ ] Save sufficient evidence to recompute the full comparison without a model environment.

Done when a constructed pooled improvement cannot hide a session regression and incomplete evidence cannot disappear from the report.

## 2. Fit the recurring evaluation workflow

- [ ] Add the thin Parquet/datarepo loading example and one-time output-column mapping.
- [ ] Produce the full session table and a self-contained local report with direct session detail.
- [ ] Demonstrate pinned-baseline reuse at the end of a sample evaluation job, with no manual comparison step.
- [ ] Check the action counts and baseline/error behavior in [Workflow](WORKFLOW.md).

Done when the ordinary evaluation produces the report automatically, a reader can open it and select a session, and the saved comparison reproduces in a clean environment. This validates the example workflow, not an untested Neuralink integration.

## 3. Demonstrate on public recordings

- [ ] Select one multi-session dataset with compatible neural features and two-dimensional velocity labels; verify access and reuse terms.
- [ ] Establish the example's grouping, training/evaluation boundaries, source identities, and target semantics before candidate evaluation.
- [ ] Use two fixed decoder artifacts in a separate example producer; keep its inference logic out of the product interface.
- [ ] Freeze the comparison specification, produce predictions, and preserve all session results.
- [ ] Reproduce the scores from the output bundle and record the tested revision/platform.
- [ ] Present the workflow and record the remaining questions about a real engineer's output format and baseline conventions.

Done when another engineer can inspect and recompute a public-data comparison and understand the small output mapping needed to try their own permitted results.

## Current state

All implementation milestones are open. This repository is a planning artifact. No dataset has been downloaded, decoder trained, model evaluated, or Neuralink integration tested.
