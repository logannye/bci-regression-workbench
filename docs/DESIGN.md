# Design

Status: the first comparison, report, and scoring-reproduction slice is implemented and validated with synthetic predictions. Hosted datarepo integration and report-interaction checks also passed at the revision recorded in [Validation](VALIDATION.md). Public-recording evaluation and a Neuralink integration remain unperformed.

## Product boundary

The existing evaluator owns model loading, preprocessing, inference, accelerator use, state resets, and prediction generation. The workbench consumes its frozen outputs, validates that they can be scored together, and identifies session-level RMSE increases.

The entry point is `compare(evaluation, baseline, candidate, *, tolerance=None, numerical_tolerance=1e-12, output_dir=None, description="")`. It accepts an `EvaluationSet` and two `PredictionSet` objects and returns a result dictionary. The complete session table is `result["sessions"]`. Supplying a new `output_dir` also writes the report and scoring evidence; omitting it performs an in-memory comparison.

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

## Baseline and data access

Select and save the baseline once for a fixed evaluation set, then load that exact bundle for later candidates. The report shows the run identity and content digest. The caller owns any human-readable alias resolution; the workbench does not select a baseline or substitute a latest or best-looking run. A baseline change must be explicit.

Missing or malformed saved bundles raise an error during loading. A successfully loaded baseline bound to incompatible evaluation semantics makes the comparison invalid. Neither path silently runs a model, selects another baseline, or shrinks the evaluation cohort.

The optional [datarepo example](../examples/datarepo_example.py) uses upstream `ParquetTable` to query synthetic prediction/target files and feeds the collected tables to the same core. Its pinned [environment](../requirements-datarepo.txt) passed a real hosted Parquet-load, comparison, and reproduction run; see [Validation](VALIDATION.md) for the tested revision and platform. Existing users can pass collected tables directly. Raw recordings and existing catalogs stay where they are.

## Alignment and scoring

The declared evaluation table drives the comparison. Alignment uses stable session/sample keys, never file row position, nearest timestamp, or the intersection of available predictions. Predictions for explicitly ineligible keys are counted as excluded. Unexpected keys make the comparison incomplete; they also invalidate an affected declared session when it can be identified. Missing or duplicate required predictions invalidate the affected session.

Verify each bundle's declared evaluation-set identity, target units, coordinates, and prediction horizon against the frozen specification. Check output dimensions, finite values, and content identities. These checks compare producer declarations; numerical values alone cannot establish their physical meaning. Compute the metric in [Evaluation](EVALUATION.md) on identical eligible keys for both runs. Preserve every selected session, including invalid rows. An invalid required session makes the overall comparison incomplete.

The comparator can verify this pairing and arithmetic. Prediction files cannot establish whether inference was causal, reset rules were followed, or training avoided evaluation data. Those are producer-owned protocol claims and must be attributed as such. Unknown training provenance does not prevent descriptive scoring, but it prevents describing the result as verified held-out evaluation.

## One output, with supporting detail

The returned dictionary includes the session table, comparison identities, completeness, issues, pooled context when complete, and paired samples from valid sessions. A self-contained local report shows baseline/candidate IDs, evaluation-set identity, completeness, and the sessions with increased error. It lists every session and links directly to its paired error trace and supporting sample references. That detail substantiates a regression; it does not diagnose its cause.

With `output_dir`, the call writes `report.html`, `session_metrics.csv`, `evaluation.json`, `baseline.json`, `candidate.json`, `comparison.json`, and `manifest.json`. The bundle retains the actual predictions, targets, eligibility, declared provenance, artifact hashes, comparator version/source digest, Python version, and platform. The output directory must not already exist. Data redistribution remains governed by source licenses.

`reproduce(bundle_dir, *, output_dir=None)` checks artifact hashes and the comparator source identity, then recomputes the saved comparison. Evidence and coverage must match exactly; declared numerical tolerance applies only to computed errors and scores. An optional new output directory saves another copy of the reproduced comparison. Re-running inference belongs to the original evaluator; supplied provenance is never executed.

Reproduction requires the same `__init__.py`, `core.py`, `tables.py`, and `report.py` source content, not merely the same package version. Retain the tested Git revision with the run evidence and check out that revision when reproducing later. The manifest records a source digest and environment information; it does not automatically record the Git commit.
