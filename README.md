# BCI Regression Workbench

**Find the recording sessions where a candidate decoder performs worse, even when its pooled score improves. Reproduce each reported difference.**

Call a small Python function at the end of an existing evaluation job. It compares saved two-dimensional velocity predictions on the same declared samples, writes a session-level RMSE report, and preserves the evidence needed to recompute it. Your evaluator continues to own model execution and data access.

**Status: started, in progress.** The implementation includes keyed comparison, a self-contained HTML report, CSV results, scoring reproduction, and a reusable pinned check for an existing evaluator. The synthetic example, real datarepo integration, and a frozen public neural-recording comparison have passed their checks. See [implementation validation](docs/VALIDATION.md) and [public-demo results](docs/public-demo/RESULTS.md). Neuralink internal integration and intended-engineer usability remain untested.

An independent open-source project by Logan Nye, designed for Neuralink's BCI ML engineering team. (This is not an official Neuralink project or an implemented integration with its internal systems.)

The intended user is a Neuralink BCI ML engineer reviewing a proposed decoder change to determine whether or not it is worth keeping. It is informed by Neuralink's public [ML role](https://job-boards.greenhouse.io/neuralink/jobs/5663271003), which explicitly mentions building evaluation infrastructure for model updates.

> On the same recorded sessions, where did candidate B become WORSE than baseline A?

## Public recording demonstration

A prospectively frozen comparison trained both ridge decoders on one public Indy recording day and evaluated three later days. The candidate added recent neural history. Its error was lower on all three sessions, with all 14,052 expected evaluation bins scored; no session-level increase was observed. The full comparison and independent prediction audit reproduced on Linux and macOS without refitting.

[Read the per-session results and limits](docs/public-demo/RESULTS.md), [inspect the frozen plan](docs/public-demo/PLAN.md), or [reproduce the evidence](docs/public-demo/REPRODUCE.md). This is offline decoding of measured physical-reaching velocity from one macaque, not a Neuralink participant evaluation. The core library continues to consume existing predictions; the example producer is separate.

## Try the synthetic demonstration

From the repository root, with Python 3.10 or later:

```sh
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --initialize
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --candidate-id candidate-002
```

The core uses only Python's standard library. No dependency installation or native compilation is needed. Start with a new example directory. Each candidate comparison needs a new candidate ID; existing comparison outputs are never overwritten.

The initialization command saves the evaluation, baseline, column mapping, and reporting tolerance once. Both ordinary candidate commands load that same pin and generate their reports as part of evaluation. They construct only candidate predictions and write separate run directories. Repeating initialization refuses to replace the reference. The fixture improves pooled RMSE while worsening a shorter session. Open the report path printed by the script, then select the worsened session to inspect its paired errors and sample references.

This tradeoff checks the comparator's behavior. It is not a result about neural decoding performance.

## Add the comparison to an evaluation job

Engineers on the BCI team can keep their model code, inference environment, data access, and evaluation command. They do not need to load a model into this tool. A one-time output mapping and pinned baseline enable a recurring path: run evaluation as usual, then open the comparison report. No new account, server, or dashboard is needed; it is meant to fit conveniently within their existing workflows with as few extra clicks as possible.

Inputs are records keyed by `session_id` and `sample_id`. The evaluation table holds fixed targets and eligibility; each prediction bundle binds its outputs to that evaluation identity. Columns can be mapped once from the existing evaluator's names.

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

The returned dictionary contains all session rows under `result["sessions"]`, completeness, issues, pooled context when complete, and paired samples. A reporting tolerance is an absolute increase in RMSE in the declared velocity units; `tolerance=None` reports descriptive differences without categorical regression flags.

## Read and reproduce the result

Each comparison directory contains:

| Artifact | Purpose |
| --- | --- |
| `report.html` | Local report with identities, completeness, every session, and linked error traces and sample previews. No server or external assets. |
| `session_metrics.csv` | The full session comparison table. |
| `evaluation.json`, `baseline.json`, `candidate.json` | Retained targets, eligibility, predictions, and declared identities. |
| `comparison.json`, `manifest.json` | Results, comparison settings, environment information, and content hashes. |

Recompute a saved comparison without loading a decoder:

```python
from bci_regression import reproduce

recomputed = reproduce("runs/demo/candidate-001/session-regressions")
print(recomputed["complete"])
```

`reproduce` requires the same comparator source content, verifies saved artifacts, and compares recomputed results with the recorded result within the numerical tolerance. Retain the tested source revision with your run artifacts. It raises an error for changed evidence or a mismatched result. This reproduces scoring; regenerating predictions remains the original evaluator's responsibility.

The report lists invalid sessions prominently and sorts valid sessions by descending candidate-minus-baseline RMSE. Missing or duplicate required predictions never shrink the scoring set silently. Any invalid required session makes the comparison incomplete. The metric is `sqrt(mean((predicted_vx − target_vx)² + (predicted_vy − target_vy)²))`; positive candidate-minus-baseline differences mean higher error.

## Optional datarepo example

[examples/datarepo_example.py](examples/datarepo_example.py) exercises Neuralink's upstream [datarepo](https://github.com/neuralinkcorp/datarepo) Parquet interface with synthetic prediction tables. Its optional environment is pinned in [requirements-datarepo.txt](requirements-datarepo.txt). The real datarepo example and all 67 tests passed in its Python 3.11 hosted environment; see the exact source and platform in [Validation](docs/VALIDATION.md).

The core accepts record mappings directly and does not require a catalog migration. The table boundary also supports collected Polars and Arrow tables when those libraries are available. Datarepo is a narrow source integration, not a replacement evaluation framework.

## Scope and evidence

The single benefit is exposing reproducible session-level regressions in existing outputs. The tool does not train or run models, diagnose a biological cause, measure latency, or approve deployment. Producer-supplied metadata cannot independently establish causal inference or training/evaluation independence. Offline prediction error does not establish interactive BCI performance.

## What will determine whether the project is practically useful

Tests and the constructed demonstration are implementation checks. The public-recording demonstration is complete. The pinned hook addresses observed integration boilerplate; whether an intended engineer has stable keyed exports, needs this view, or already has an equivalent remains unvalidated. No Neuralink data or model code is included.

The selected public recordings contain physical reaching and are described as an offline movement-decoding example. Deployment decisions remain outside this first iteration; any future expansion should depend on practical feedback from the ML engineering team.

Run the standard-library checks with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See [Design](docs/DESIGN.md), [Workflow](docs/WORKFLOW.md), [Evaluation](docs/EVALUATION.md), [Implementation plan](docs/PLAN.md), and [Sources and assumptions](docs/SOURCES.md) for the contract and evidence boundaries. Contributors should read [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE). Dependency and dataset licenses apply separately.
