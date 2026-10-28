# Implementation plan

The project has one core benefit: identify and reproduce session-level prediction regressions. Integrate at the output of an existing evaluator. Do not require users to adopt a new model runner.

## 1. Build the smallest correct comparison

- [x] Fix the keyed prediction/target contract and one metric in [Design](DESIGN.md) and [Evaluation](EVALUATION.md).
- [x] Implement the Python comparison function over typed tables, with explicit baseline and evaluation-set identities.
- [x] Verify hand-calculated scores, the hidden-session tradeoff, keyed alignment, and invalid-evidence cases with local standard-library tests.
- [x] Save sufficient evidence to recompute the full comparison without a model environment, including comparator source binding.

Completed and checked with synthetic outputs. A constructed pooled improvement remains accompanied by its session regression, and invalid evidence remains visible. Local and hosted evidence is recorded in [Validation](VALIDATION.md). These checks establish comparator behavior, not neural-model performance.

## 2. Fit the recurring evaluation workflow

- [x] Add explicit output-column mapping and the optional Parquet/datarepo example source.
- [x] Produce the full session table and a self-contained local report with direct session detail.
- [x] Add a synthetic producer example that loads the pinned evaluation/baseline for later candidate comparisons and verifies scoring reproduction.
- [x] Complete the optional real datarepo/Parquet run in its pinned hosted environment and record its revision/platform.
- [x] Record the synthetic report-interaction check and action counts in [Workflow](WORKFLOW.md) and [Validation](VALIDATION.md).
- [x] Record clean hosted reproduction of the core example at the tested source revision and local reproduction of a downloaded CI artifact.

Completed for the synthetic example at the revision recorded in [Validation](VALIDATION.md). The example automatically produces its report, browser inspection confirms direct access to the session trace, and saved scores reproduce using the recorded source. This validates the example workflow; intended-engineer usability and Neuralink integration have not been evaluated.

## 3. Demonstrate on public recordings

- [ ] Select one multi-session dataset with compatible neural features and two-dimensional velocity labels; verify access and reuse terms.
- [ ] Establish the example's grouping, training/evaluation boundaries, source identities, and target semantics before candidate evaluation.
- [ ] Use two fixed decoder artifacts in a separate example producer; keep its inference logic out of the product interface.
- [ ] Freeze the comparison specification, produce predictions, and preserve all session results.
- [ ] Reproduce the scores from the output bundle and record the tested revision/platform.
- [ ] Present the workflow and record the remaining questions about a real engineer's output format and baseline conventions.

Done when another engineer can inspect and recompute a public-data comparison and understand the small output mapping needed to try their own permitted results.

## Current state

The first two milestones are complete for the tested synthetic workflow, including hosted core checks, real datarepo/Parquet integration, report interaction, and scoring reproduction. Exact evidence and remaining limits are in [Validation](VALIDATION.md). No public neuroscience dataset has been evaluated, no decoder has been trained or executed by the product, and no intended-engineer usability study or Neuralink integration has been performed.
