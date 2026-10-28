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

- [x] Select one multi-session dataset with compatible neural features and two-dimensional velocity labels; verify access and reuse terms.
- [x] Establish the example's grouping, training/evaluation boundaries, source identities, and target semantics before candidate evaluation.
- [x] Use two fixed decoder artifacts in a separate example producer; keep its inference logic out of the product interface.
- [x] Freeze the comparison specification, produce predictions, and preserve all session results.
- [x] Reproduce the scores from the output bundle and record the tested revision/platform.
- [ ] Present the workflow and record the remaining questions about a real engineer's output format and baseline conventions.

The public experiment is complete: source-only ridge fits on the September 15 recording produced a complete comparison for September 16, September 21, and September 27, with 4,684 eligible samples per session. All three candidate RMSE values were lower; the descriptive report uses `tolerance=None` and does not force a regression. The independent audit and score reproduction passed hosted and locally. [Public demonstration results](public-demo/RESULTS.md) records the exact run and evidence.

The remaining step is to present that evidence to an intended engineer and record the output-format and baseline-convention questions. No such usability or integration validation is claimed.

## 4. Make the reference setup reusable

The synthetic workflow already demonstrates baseline reuse, but each integrator previously had to copy its setup/loading logic and preserve the comparison settings. Address that concrete friction with one `PinnedComparison` layer in `bci_regression.pinned`, keeping the core comparator and frozen public-recording producer unchanged.

- [x] Fix the one-time `create`/`load` and recurring `compare` contract in [Design](DESIGN.md), with the actual current evaluation required on every candidate call.
- [x] Implement atomic reference creation, complete baseline validation, immutable saved mapping/settings, and verified loading without overwriting an existing reference.
- [x] Integrate the reference into the ordinary example invocation so subsequent candidates need no baseline selection or repeated mapping/tolerance entry.
- [x] Verify two candidate runs reuse identical reference contents and match direct core comparison, including invalid session rows.
- [x] Verify changed evaluation content or semantics cannot be silently rebound, and tampered/incomplete references fail explicitly.
- [ ] Record tests, recurring example execution, and scoring reproduction at the exact hosted revision and platform.

Local validation passed: 110 tests passed with nine optional-dependency skips, two recurring synthetic candidates reused unchanged reference bytes, and the saved public outputs produced identical scores through the hook. Hosted validation is pending. Its acceptance concerns less repeated integration code and preserved comparison semantics, not measured setup time or adoption by a Neuralink engineer. The engineer presentation and workflow questions in milestone 3 remain open.

## Current state

The first two milestones are complete for the previously tested synthetic workflow, including hosted core checks, real datarepo/Parquet integration, report interaction, and scoring reproduction; see [Validation](VALIDATION.md). The public-recording experiment and reproduction are also complete, with all selected sessions preserved in [Public demonstration results](public-demo/RESULTS.md). Models were trained and executed only by the separate example producer. The focused reusable-reference change passed local tests and saved-output replay; its hosted validation is pending. Earlier successful runs do not validate it. Intended-engineer presentation/usability validation and Neuralink integration remain unperformed.
