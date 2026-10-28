# BCI Regression Workbench

**Find the recording sessions where a candidate decoder performs worse, even when its pooled score improves. Reproduce each reported difference.**

Call a small Python function at the end of an existing evaluation job. It compares saved two-dimensional velocity predictions on the same declared samples, writes a session-level RMSE report, and preserves the evidence needed to recompute it. Your evaluator continues to own model execution and data access.

**Status: started, in progress.** The first implementation includes keyed comparison, a self-contained HTML report, CSV results, and scoring reproduction from a JSON bundle. The demonstration uses constructed predictions. Hosted tests, packaging, and the optional datarepo example pass; see [Validation](docs/VALIDATION.md). No public neuroscience dataset or Neuralink internal integration has been evaluated.

An independent open-source project by Logan Nye, designed for Neuralink's BCI ML engineering team. (This is not an official Neuralink project or an implemented integration with its internal systems.)

The intended user is a Neuralink BCI ML engineer reviewing a proposed decoder change to determine whether or not it is worth keeping. It is informed by Neuralink's public [ML role](https://job-boards.greenhouse.io/neuralink/jobs/5663271003), which explicitly mentions building evaluation infrastructure for model updates.

> On the same recorded sessions, where did candidate B become WORSE than baseline A?

## Try the synthetic demonstration

From the repository root, with Python 3.10 or later:

```sh
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --candidate-id candidate-002
```

The core uses only Python's standard library. No dependency installation or native compilation is needed. Start with a new example directory. Each candidate comparison needs a new candidate ID; existing comparison outputs are never overwritten.

The first invocation creates a pinned evaluation set and baseline. The second reuses their saved bundles and writes the same constructed candidate predictions under a new run ID, demonstrating baseline reuse. The fixture improves pooled RMSE while worsening a shorter session. Open the report path printed by the script, then select the worsened session to inspect its paired errors and sample references.

This tradeoff checks the comparator's behavior. It is not a result about neural decoding performance.

## Add the comparison to an evaluation job

Engineers on the BCI team can keep their model code, inference environment, data access, and evaluation command. They do not need to load a model into this tool. A one-time output mapping and pinned baseline enable a recurring path: run evaluation as usual, then open the comparison report. No new account, server, or dashboard is needed; it is meant to fit conveniently within their existing workflows with as few extra clicks as possible.

Inputs are records keyed by `session_id` and `sample_id`. The evaluation table holds fixed targets and eligibility; each prediction bundle binds its outputs to that evaluation identity. Columns can be mapped once from the existing evaluator's names.

This complete Python example uses two synthetic samples. Run it with this repository's `src` on `PYTHONPATH`:

```python
from bci_regression import EvaluationSet, PredictionSet, compare

keys = [("session-a", "sample-0"), ("session-b", "sample-0")]
evaluation = EvaluationSet.from_records(
    [{"session_id": s, "sample_id": k, "timestamp": 0.0,
      "target_vx": 0.0, "target_vy": 0.0} for s, k in keys],
    evaluation_id="synthetic-example-v1", units="cm/s",
    coordinates="x-right,y-up", horizon_ms=0, purpose="synthetic",
)

def prediction_rows(values):
    return [{"session_id": s, "sample_id": k,
             "predicted_vx": vx, "predicted_vy": 0.0}
            for (s, k), vx in zip(keys, values)]

baseline = PredictionSet.from_records(
    prediction_rows([3.0, 1.0]), run_id="baseline-v1", evaluation=evaluation,
)
candidate = PredictionSet.from_records(
    prediction_rows([1.0, 2.0]), run_id="candidate-v1", evaluation=evaluation,
)
result = compare(
    evaluation, baseline, candidate, tolerance=0.1,
    output_dir="runs/api-example",
    description="Synthetic arithmetic example; no model execution.",
)
print(result["complete"], result["sessions"])
```

For subsequent candidates, load `EvaluationSet.load("runs/api-example/evaluation.json")` and `PredictionSet.load("runs/api-example/baseline.json")`, then create only the new candidate bundle from the normal evaluator's outputs. Do not recreate or relabel an old baseline against a changed evaluation set. The basic demonstration exercises this saved-baseline path.

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

recomputed = reproduce("runs/api-example")
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

Tests and the constructed demonstration are implementation checks. A frozen public-recording demonstration and validation with an intended engineer remain future work. No Neuralink data or model code is included.

If the future public recordings contain physical reaching rather than attempted cursor movement, that demonstration will be described as an offline movement-decoding example, not a Neuralink participant evaluation. Deployment decisions remain outside this first iteration; any future expansion should depend on practical feedback from the ML engineering team.

Run the standard-library checks with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See [Design](docs/DESIGN.md), [Workflow](docs/WORKFLOW.md), [Evaluation](docs/EVALUATION.md), [Implementation plan](docs/PLAN.md), and [Sources and assumptions](docs/SOURCES.md) for the contract and evidence boundaries. Contributors should read [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE). Dependency and dataset licenses apply separately.
