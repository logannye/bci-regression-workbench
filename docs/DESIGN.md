# Design

Status: proposed, not implemented.

## Product boundary

The existing evaluator owns model loading, preprocessing, inference, accelerator use, state resets, and prediction generation. The workbench consumes its frozen outputs, validates that they can be scored together, and identifies session-level RMSE increases.

The primary entry point is one Python comparison function called at evaluation completion. It accepts baseline outputs, candidate outputs, and a frozen evaluation specification; it returns the comparison table and saves the report and scoring evidence. This is an interface contract, not a currently callable API.

No model adapter or access to model binaries is required. Baseline and candidate may run in different model environments. The same comparison function can be called from an existing job runner without a separate orchestration system. A standalone CLI, native application, and hosted UI are outside the first implementation.

## Minimal input contract

| Input | Required contents |
| --- | --- |
| Evaluation table | Session ID, stable sample ID, target timestamp, target vx/vy, and the predeclared eligibility mask with exclusion reasons. |
| Baseline predictions | Session ID, sample ID, predicted vx/vy; one finite prediction per required scoring key. Its bundle binds the output digest to the producer-declared evaluation-set identity, units, coordinates, and horizon. |
| Candidate predictions | The same output schema and its own bound evaluation/target-semantics declaration. |
| Comparison specification | Explicit baseline/candidate run identities and output digests; evaluation-table content identity; target units, coordinates, prediction horizon, and reporting/numerical tolerances. |

Scope the first implementation to typed tables and Parquet files. A one-time mapping translates the existing evaluator's column names. Do not introduce a general plugin or ingestion system.

The evaluation-set identity binds sample keys, targets, target semantics, and eligibility, not just a name such as "test." Capture a reference to the shared source recordings. Model/checkpoint identity, generation-code revision, preprocessing configuration, training provenance, and state policy are supplied by the producer when available. Record absent provenance as unverified; do not make engineers re-enter metadata already emitted by their evaluator.

Input representation and preprocessing may legitimately change between models. Those differences must be recorded, but the comparison requires the same evaluation examples and target semantics, not identical internal feature arrays.

## Baseline and data access

Select and pin the baseline once for a fixed evaluation set. Resolve any human-readable alias to an immutable run identity before comparison and show that identity in the report. Never automatically substitute the latest or best-looking run. A baseline change must be explicit.

Reuse saved baseline predictions. A missing or incompatible baseline produces an actionable comparison error; the tool does not silently run a model, select another baseline, or shrink the evaluation cohort.

Use upstream [datarepo](https://github.com/neuralinkcorp/datarepo) as a thin table-loading example for exported prediction/target Parquet and the resulting comparison rows. Existing users can pass their queried typed tables directly. Record file content hashes and pin the tested dependency version when implemented. Raw recordings and existing catalogs stay where they are.

## Alignment and scoring

The declared evaluation table drives the comparison. Join by stable session/sample keys, never file row position, nearest timestamp, or the intersection of available predictions. Report extra rows and apply only the evaluation manifest's explicit selection rule. Missing or duplicate required predictions invalidate the affected session.

Verify each bundle's declared evaluation-set identity, target units, coordinates, and prediction horizon against the frozen specification. Check output dimensions, finite values, and content identities. These checks compare producer declarations; numerical values alone cannot establish their physical meaning. Compute the metric in [Evaluation](EVALUATION.md) on identical eligible keys for both runs. Preserve every selected session, including invalid rows. An invalid required session makes the overall comparison incomplete.

The comparator can verify this pairing and arithmetic. Prediction files cannot establish whether inference was causal, reset rules were followed, or training avoided evaluation data. Those are producer-owned protocol claims and must be attributed as such. Unknown training provenance does not prevent descriptive scoring, but it prevents describing the result as verified held-out evaluation.

## One output, with supporting detail

The Python return value is the full session table. A self-contained local report shows baseline/candidate IDs, evaluation-set identity, completeness, and the sessions with increased error. It lists every session and offers a direct session detail containing the paired error trace and supporting sample references. That detail substantiates a regression; it does not diagnose its cause.

The same call writes the result table, report, and comparison specification beside the existing evaluation artifacts. The scoring bundle retains predictions, targets, masks, code/environment identity, and source hashes or retained immutable references. It must contain enough evidence to recompute the table without model loading. Data redistribution remains governed by source licenses.

Recomputing saved scores is the version-one reproducibility promise. Re-running model inference belongs to the original evaluator. Preserve its supplied configuration/artifact references for an engineer to use there, without automatically executing embedded commands.
