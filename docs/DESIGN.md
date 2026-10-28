# Design

Status: the core comparison, report, and scoring-reproduction slice is implemented and validated with synthetic predictions and a completed public-recording demonstration. Hosted datarepo integration and synthetic report-interaction checks passed at the revision recorded in [Validation](VALIDATION.md). The public run, independent audit, and scoring reproduction are recorded in [Public demonstration results](public-demo/RESULTS.md). The reusable `PinnedComparison` integration layer described below passed local and hosted checks recorded in [Pinned-hook validation](PINNED-VALIDATION.md). Intended-engineer usability and Neuralink integration remain unperformed.

## Product boundary

The existing evaluator owns model loading, preprocessing, inference, accelerator use, state resets, and prediction generation. The workbench consumes its frozen outputs, validates that they can be scored together, and identifies session-level RMSE increases.

The [public-recording example](../examples/public_recording/run.py) demonstrates this boundary with a separate, frozen ridge-model producer. It exports both models' predictions before reading evaluation target values, then passes those saved outputs to the same comparison API. Its model fitting and independent protocol audit are example-specific; they do not add a model runner to the product or establish training provenance for arbitrary imported outputs.

The core entry point is `compare(evaluation, baseline, candidate, *, tolerance=None, numerical_tolerance=1e-12, output_dir=None, description="")`. It accepts an `EvaluationSet` and two `PredictionSet` objects and returns a result dictionary. The complete session table is `result["sessions"]`. Supplying a new `output_dir` also writes the report and scoring evidence; omitting it performs an in-memory comparison. The reusable reference layer delegates to this unchanged scoring function.

No model adapter or access to model binaries is required. Baseline and candidate may run in different model environments. The same comparison function can be called from an existing job runner without a separate orchestration system. A standalone CLI, native application, and hosted UI are outside the first implementation.

## Minimal input contract

| Input | Required contents |
| --- | --- |
| Evaluation table | Session ID, stable sample ID, target timestamp, target vx/vy, and the predeclared eligibility mask with exclusion reasons. |
| Baseline predictions | Session ID, sample ID, predicted vx/vy; one finite prediction per required scoring key. Its bundle binds the output digest to the producer-declared evaluation-set identity, units, coordinates, and horizon. |
| Candidate predictions | The same output schema and its own bound evaluation/target-semantics declaration. |
| Comparison specification | Explicit baseline/candidate run identities and output digests; evaluation-table content identity; target units, coordinates, prediction horizon, and reporting/numerical tolerances. |

`EvaluationSet.from_records` and `PredictionSet.from_records` accept mapping records, collected Polars DataFrames, or Arrow tables. Their optional `columns` mapping uses canonical field name → source column name. Lazy queries must be collected explicitly by the caller. `bci_regression.tables.load_parquet` reads one explicit local Parquet file when PyArrow is available. The core requires no third-party dependencies.

The evaluation fingerprint binds sample keys, targets, target semantics, eligibility, declared purpose, and optional `source_ref`, not just a name such as "test." Eligibility defaults to true; explicit exclusions require reasons. Model/checkpoint identity, generation-code revision, preprocessing configuration, training provenance, and state policy can be supplied in each prediction set's `provenance` mapping. The report labels this provenance as producer-supplied and unverified; the tool does not discover it automatically.

Creating a `PredictionSet` binds its records to the supplied `EvaluationSet`. Do this when exporting predictions from their actual evaluation. Load a saved baseline with `PredictionSet.load` for later comparisons; reconstructing old predictions against a new evaluation object would make a new declaration that the tool cannot independently justify.

Input representation and preprocessing may legitimately change between models. Those differences must be recorded, but the comparison requires the same evaluation examples and target semantics, not identical internal feature arrays.

## Reusable pinned comparison

The original recurring integration required each evaluator to manage reference files, output-column mapping, and fixed comparison settings. `PinnedComparison` in `bci_regression.pinned` moves that repeated setup into a small persistent reference. It introduces no model interface or alternative scoring behavior. The selected contract is:

```python
PinnedComparison.create(
    path, *, evaluation, baseline, prediction_columns=None,
    tolerance=None, numerical_tolerance=1e-12, description="",
)
PinnedComparison.load(path)
reference.compare(
    rows, *, evaluation, run_id, output_dir, provenance,
)
```

One-time creation takes the actual exported `EvaluationSet` and baseline `PredictionSet`. It requires complete baseline coverage and compatible evaluation semantics, then atomically stores their identities and contents with the candidate-column mapping, reporting tolerance, numerical tolerance, and description. Creation refuses an existing destination. The saved reference is immutable and hash-verified; changing the baseline or configuration requires an explicitly new reference.

At the end of each ordinary evaluation job, the caller supplies candidate output rows, their run identity and provenance, a new output directory, and the **actual current `EvaluationSet` from that job**. The reference applies its saved prediction-column mapping, binds candidate outputs to that supplied evaluation, and calls the core comparator using the pinned evaluation and baseline. It returns the existing result dictionary and writes the existing report and scoring bundle. The caller does not select the baseline or re-enter mappings and tolerances for each candidate.

The current evaluation is mandatory; it never defaults to the pinned evaluation. Changed targets, eligibility, units, coordinates, horizon, or other fingerprint-bound content must remain detectable as an incompatible comparison. Copying reference metadata onto arbitrary candidate outputs would only conceal a changed evaluation, so the integration must export its actual current declarations. Missing or duplicate candidate predictions retain the core's explicit invalid-session behavior and never reduce the denominator silently.

Local checks passed for reference creation/loading, configuration integrity, repeated candidate calls, equivalence with direct `compare`, and preservation of mismatch/invalid-input handling; hosted checks also passed. See [Pinned-hook validation](PINNED-VALIDATION.md) for source identities, counts, and optional skips. Output directories inside the pin are rejected before consuming candidate rows, including symlink aliases, so reporting cannot invalidate the reference. This layer reduces repository-specific integration code; it cannot establish whether Neuralink's evaluator provides the required outputs or whether an intended engineer finds the workflow useful.

## Baseline and data access

Select and save the baseline once for a fixed evaluation set, then load that exact bundle for later candidates. The reusable reference holds this explicit choice; direct users may continue loading the underlying bundles themselves. The report shows the run identity and content digest. The caller owns any human-readable alias resolution; the workbench does not select a baseline or substitute a latest or best-looking run. A baseline change must be explicit.

Missing or malformed saved bundles raise an error during loading. A successfully loaded baseline bound to incompatible evaluation semantics makes the comparison invalid. Neither path silently runs a model, selects another baseline, or shrinks the evaluation cohort.

The optional [datarepo example](../examples/datarepo_example.py) uses upstream `ParquetTable` to query synthetic prediction/target files and feeds the collected tables to the same core. Its pinned [environment](../requirements-datarepo.txt) passed a real hosted Parquet-load, comparison, and reproduction run; see [Validation](VALIDATION.md) for the tested revision and platform. Existing users can pass collected tables directly. Raw recordings and existing catalogs stay where they are.

## Alignment and scoring

The declared evaluation table drives the comparison. Alignment uses stable session/sample keys, never file row position, nearest timestamp, or the intersection of available predictions. Predictions for explicitly ineligible keys are counted as excluded. Unexpected keys make the comparison incomplete; they also invalidate an affected declared session when it can be identified. Missing or duplicate required predictions invalidate the affected session.

Verify each bundle's declared evaluation-set identity, target units, coordinates, and prediction horizon against the frozen specification. Check output dimensions, finite values, and content identities. These checks compare producer declarations; numerical values alone cannot establish their physical meaning. Compute the metric in [Evaluation](EVALUATION.md) on identical eligible keys for both runs. Preserve every selected session, including invalid rows. An invalid required session makes the overall comparison incomplete.

The comparator can verify this pairing and arithmetic. Prediction files cannot establish whether inference was causal, reset rules were followed, or training avoided evaluation data. Those are producer-owned protocol claims and must be attributed as such. Unknown training provenance does not prevent descriptive scoring, but it prevents describing the result as verified held-out evaluation.

## One output, with supporting detail

The returned dictionary includes the session table, comparison identities, completeness, issues, pooled context when complete, and paired samples from valid sessions. A self-contained local report shows baseline/candidate IDs, evaluation-set identity, completeness, and the sessions with increased error. It lists every session beside a selected-session evidence pane, with the signed RMSE change prominent and supporting sample references available in a disclosure. The small, fixed selection script progressively enhances native session links; no external assets or network requests are needed. That detail substantiates a regression; it does not diagnose its cause.

With `output_dir`, the call writes `report.html`, `session_metrics.csv`, `evaluation.json`, `baseline.json`, `candidate.json`, `comparison.json`, and `manifest.json`. The bundle retains the actual predictions, targets, eligibility, declared provenance, artifact hashes, comparator version/source digest, Python version, and platform. The output directory must not already exist. Data redistribution remains governed by source licenses.

`reproduce(bundle_dir, *, output_dir=None)` checks artifact hashes and the comparator source identity, then recomputes the saved comparison. Evidence and coverage must match exactly; declared numerical tolerance applies only to computed errors and scores. An optional new output directory saves another copy of the reproduced comparison. Re-running inference belongs to the original evaluator; supplied provenance is never executed.

Reproduction requires the same `__init__.py`, `core.py`, `tables.py`, and `report.py` source content, not merely the same package version. Retain the tested Git revision with the run evidence and check out that revision when reproducing later. The manifest records a source digest and environment information; it does not automatically record the Git commit.
