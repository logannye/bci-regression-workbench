# BCI Regression Workbench

**See which recording sessions got worse after a decoder change, even when the overall score improves.**

### [Explore the human BCI demo →](https://logannye.github.io/bci-regression-workbench/)

**No installation or account required.** Open a completed comparison using public neural recordings, select a session, and inspect the baseline and candidate side by side.

A better average can hide a worse recording day. BCI Regression Workbench gives an ML engineer a repeatable session-by-session check at the end of an existing evaluation job. It compares both decoders on the same declared samples and preserves the inputs needed to recompute every score.

| At a glance | |
| --- | --- |
| **Use it when** | Reviewing a proposed decoder change after running your normal offline evaluation. |
| **Give it** | Fixed two-dimensional reference labels, sample eligibility, and baseline/candidate predictions keyed by session and sample. |
| **Get back** | An interactive HTML report, a CSV of session scores, and a saved bundle for reproducing the comparison. |
| **Daily workflow** | Pin the baseline and column mapping once. Each candidate evaluation writes its own report. |

**Existing evaluator → saved predictions → session comparison → inspect changed sessions.** Your model code, inference environment, and data access stay in your existing evaluation workflow. The metric is two-dimensional vector RMSE: lower means closer agreement with the declared reference labels. Velocity remains the default target type; the human demo explicitly declares inferred cursor-to-target vectors.

An independent open-source project by Logan Nye, designed for Neuralink's BCI ML engineering team. It has no official Neuralink affiliation or internal integration. The [sources and assumptions](docs/SOURCES.md) explain the public evidence behind this intended use.

**Status: working prototype.** Comparison, pinned-baseline reuse, the two-pane report, score reproduction, and the optional datarepo integration have passed their documented checks. See [implementation validation](docs/VALIDATION.md), [pinned-hook validation](docs/PINNED-VALIDATION.md), and [report validation](docs/REPORT-UI.md). Practical use by Neuralink engineers remains untested.

## Explore the demo in a minute

1. **Read the Change column.** It shows candidate minus baseline RMSE. Positive means higher error; negative means lower error. Coverage shows whether all expected samples were scored.
2. **Select a recording session.** The evidence pane immediately shows where the candidate added the most error in a fixed 24-scored-sample window, with exact sample IDs, timestamps, and a full-resolution paired trace. The session's original scores remain visible. If no window has net added error, the report says so.
3. **Expand the evidence you need.** Open **Supporting samples** for that window's values, **Full-session trace** for context, or **Identity & scoring details** for run identities and provenance. A local loss can occur in an overall-improved session; it does not change the session's regression flag. See the [fixed localization rule and checks](docs/LOCALIZATION.md).

The [human demo](https://logannye.github.io/bci-regression-workbench/) uses MINDFUL T11: public implanted-BCI recordings from one person performing a cursor task. Its [frozen evaluation plan](docs/human-demo/PLAN.md) compares a ridge decoder using the current neural bin with one adding three previous bins. Both train on the earliest three recording days and evaluate on **all twelve later days, with 324,732 eligible samples**. The model comparison follows the same pin-baseline, export-candidate, inspect-session workflow.

**Human targets are inferred cursor-to-target displacement vectors, not measured intended velocities.** Lower error means closer agreement with that proxy. The two example models are not the participant's original online LSTM decoder. Although the source recordings were collected during actual BCI use, our comparison is offline and cannot establish better live control. The released neural features include noncausal preprocessing, so this is not a timing or end-to-end causality demonstration.

The earlier [Indy macaque demo](https://logannye.github.io/bci-regression-workbench/indy/) remains available with its original evidence. Two fixed ridge decoders trained on one recording day and evaluated on three later days; **all three sessions had lower candidate error, with all 14,052 expected evaluation bins scored**. Its experiment was frozen before evaluation, and the saved comparison and independent prediction audit reproduced on Linux and macOS without refitting. [Results and limits](docs/public-demo/RESULTS.md), [frozen plan](docs/public-demo/PLAN.md), and [reproduction instructions](docs/public-demo/REPRODUCE.md) preserve that completed experiment.

The separate [synthetic example](#try-the-synthetic-demonstration) deliberately includes a worsened session. Real-data demos retain every selected session and do not require a favorable result or a regression. These independent public datasets do not establish performance on Neuralink participants. The hosted pages are reports to explore, not services for uploading recordings or running models.

## Try the synthetic demonstration

From the repository root, with Python 3.10 or later:

```sh
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --initialize
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --candidate-id candidate-002
```

The core uses only Python's standard library. No dependency installation or native compilation is needed. Start with a new example directory. Each candidate comparison needs a new candidate ID; existing comparison outputs are never overwritten.

The initialization command saves the evaluation, baseline, column mapping, and reporting tolerance once. Both ordinary candidate commands load that same pin and generate their reports as part of evaluation. They construct only candidate predictions and write separate run directories. Repeating initialization refuses to replace the reference. The fixture improves pooled RMSE while worsening a shorter session. Open the report path printed by the script, then select the worsened session to inspect its paired errors and sample references. On desktop, the session list stays beside a scrollable evidence pane; on narrow screens, selecting a session brings its stacked evidence into view.

This tradeoff checks the comparator's behavior. It is not a result about neural decoding performance.

## Add the comparison to an evaluation job

Map your evaluator's output columns and pin its baseline once. Each subsequent evaluation supplies the candidate outputs and current evaluation identity, then writes a report beside the job's other artifacts. The core uses Python's standard library and runs locally without an account or server.

Inputs are records keyed by `session_id` and `sample_id`. The evaluation table holds fixed targets and eligibility; each prediction bundle binds its outputs to that evaluation identity. Columns can be mapped once from the existing evaluator's names.

For inferred cursor-to-target vectors, set `target_kind="inferred_cursor_to_target_vector"` when constructing the evaluation and declare the source coordinate units. The default remains `target_kind="velocity"`. The kind is bound to the saved evaluation and predictions; a changed kind requires a new reference. The report labels inferred vectors explicitly while the scoring formula and session workflow stay the same. See [target semantics](docs/EVALUATION.md#declared-target-semantics) for the narrow supported distinction.

The reusable hook keeps the reference and reporting settings in a verified local directory. The integration outline is:

```python
from bci_regression.pinned import PinnedComparison

# Once, when exporting the baseline's actual evaluation:
PinnedComparison.create(
    "references/reaching-v1",
    evaluation=baseline_evaluation,       # EvaluationSet from actual labels and mask
    baseline=baseline_export,             # PredictionSet already bound to that evaluation
    prediction_columns={"session_id": "recording", "sample_id": "bin",
                        "predicted_vx": "vx", "predicted_vy": "vy"},
    tolerance=0.1,                        # Absolute RMSE increase in evaluation units
)

# At evaluator startup:
check = PinnedComparison.load("references/reaching-v1")

# At completion of each normal candidate evaluation:
result = check.compare(
    candidate_outputs, evaluation=current_evaluation,
    run_id=run_id, output_dir=job_dir / "session-regressions",
    provenance=run_metadata,
)
print(job_dir / "session-regressions" / "report.html")
```

These names represent the existing evaluator's outputs and metadata; [the executable example](examples/basic_comparison.py) supplies them end to end, including a noncanonical column schema. `current_evaluation` must be an `EvaluationSet` constructed from the current job's actual labels, sample keys, timestamps, eligibility, and declared semantics. The hook requires it and rejects a changed evaluation before creating a comparison. Loading labels from the pin and declaring that they describe the current job would defeat this check.

The daily call needs no baseline selection, column mapping, or tolerance entry. The pin refuses replacement and incomplete baseline coverage; changing the reference or settings requires a new pin directory. Missing, duplicate, or nonfinite candidate predictions remain visible as invalid sessions. A changed column schema produces an explicit error. Comparison artifacts retain the pin fingerprint and hook source digest in reserved `bci_regression_pin` candidate provenance.

The original `EvaluationSet`, `PredictionSet`, and `compare` APIs remain available for callers that already manage this configuration. Both paths produce the same report format. The hook only organizes saved inputs and settings; it cannot verify that exported outputs came from the declared model or that the producer supplied truthful metadata.

The returned dictionary contains all session rows under `result["sessions"]`, completeness, issues, pooled context when complete, and paired samples. A reporting tolerance is an absolute increase in RMSE in the declared target units; `tolerance=None` reports descriptive differences without categorical regression flags.

## Read and reproduce the result

Each comparison directory contains:

| Artifact | Purpose |
| --- | --- |
| `report.html` | Two-pane local report with identities, completeness, every session, selected error traces, and collapsible sample previews. No server or external assets. |
| `session_metrics.csv` | The full session comparison table. |
| `evaluation.json`, `baseline.json`, `candidate.json` | Retained targets, eligibility, predictions, and declared identities. |
| `comparison.json`, `manifest.json` | Results, comparison settings, environment information, and content hashes. |

Recompute a saved comparison without loading a decoder:

```python
from bci_regression import reproduce

recomputed = reproduce("runs/demo/candidate-001/session-regressions")
print(recomputed["complete"])
```

`reproduce` requires the same comparator source content, verifies saved artifacts, and compares recomputed results with the recorded result within the numerical tolerance. Retain the tested source revision with your run artifacts. The renderer is included in this identity: a UI update needs a new output bundle, while older bundles and pins continue to use their recorded source. See [report compatibility and validation](docs/REPORT-UI.md). It raises an error for changed evidence or a mismatched result. This reproduces scoring; regenerating predictions remains the original evaluator's responsibility.

The report lists invalid sessions prominently and sorts valid sessions by descending candidate-minus-baseline RMSE. Missing or duplicate required predictions never shrink the scoring set silently. Any invalid required session makes the comparison incomplete. The metric is `sqrt(mean((predicted_vx − target_vx)² + (predicted_vy − target_vy)²))`; positive candidate-minus-baseline differences mean higher error.

## Optional datarepo example

[examples/datarepo_example.py](examples/datarepo_example.py) exercises Neuralink's upstream [datarepo](https://github.com/neuralinkcorp/datarepo) Parquet interface with synthetic prediction tables. Its optional environment is pinned in [requirements-datarepo.txt](requirements-datarepo.txt). Hosted validation exercises real Arrow/Parquet tables separately from the standard-library core; see the tested source and environment in [Validation](docs/VALIDATION.md) and [report validation](docs/REPORT-UI.md).

The core accepts record mappings directly and does not require a catalog migration. The table boundary also supports collected Polars and Arrow tables when those libraries are available. Datarepo is a narrow source integration, not a replacement evaluation framework.

## Scope and evidence

The single benefit is exposing reproducible session-level regressions in existing outputs. The tool does not train or run models, diagnose a biological cause, measure latency, or approve deployment. Producer-supplied metadata cannot independently establish causal inference or training/evaluation independence. Offline prediction error does not establish interactive BCI performance.

## What will determine whether the project is practically useful

Tests and the constructed demonstration are implementation checks. The completed Indy demonstration and the separately frozen human experiment retain distinct evidence and target definitions. The pinned hook addresses observed integration boilerplate; whether an intended engineer has stable keyed exports, needs this view, or already has an equivalent remains unvalidated. No Neuralink data or model code is included.

The public examples cover macaque physical reaching and human implanted-BCI cursor recordings. Both support bounded offline comparisons. Deployment decisions remain outside this first iteration; any future expansion should depend on practical feedback from the ML engineering team.

Run the standard-library checks with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See [Design](docs/DESIGN.md), [Workflow](docs/WORKFLOW.md), [Evaluation](docs/EVALUATION.md), [Implementation plan](docs/PLAN.md), and [Sources and assumptions](docs/SOURCES.md) for the contract and evidence boundaries. Contributors should read [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE). Dependency and dataset licenses apply separately.
