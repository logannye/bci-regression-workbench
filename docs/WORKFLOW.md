# Workflow

Status: the Python integration point, local report, and saved-baseline synthetic example are implemented. The workflow below is a proposed fit for Neuralink; its internal evaluator, experiment tracker, and review interfaces remain unknown.

## Fit the existing model-change loop

Neuralink's public ML role describes model-update evaluation work and names PyTorch, JAX, and Python. The following is a representative workflow to validate with its engineers, not a description of a verified internal process.

| Existing activity | Workbench interaction |
| --- | --- |
| Start from an established reference and make a model or preprocessing change. | None. The chosen baseline remains pinned in the evaluation configuration. |
| Train or otherwise produce a candidate artifact using the existing tooling. | None. The workbench does not train or load models. |
| Run the existing offline evaluation on the intended session set. | The evaluation's final step passes its outputs to the comparison function. |
| Review the normal experiment results. | Open the adjacent session-regression report. Baseline and evaluation-set identities are visible. |
| Investigate a worsened session. | Select its row to see paired error detail and the sample references needed to inspect it in existing tools. |
| Discuss, revise, or test the candidate further. | Reuse the report and scoring bundle. The workbench provides evidence, not a deployment verdict. |

The point of insertion is immediately after predictions are available and before the engineer decides which sessions to investigate. It should be part of the evaluation they already run.

Repeated comparisons belong to a declared development regression set. They do not turn that repeatedly inspected set into fresh final-assessment evidence.

## One-time integration

An engineer maps the current evaluator's session/sample keys and two-dimensional predictions to the small table contract. Both constructors accept `columns={"canonical_name": "source_name"}` for explicit renaming. The evaluation table supplies the reference labels and fixed eligible set. The integration code can pass run/configuration metadata already emitted by the evaluator through `provenance`; the workbench does not discover that metadata automatically.

The engineer creates and saves an `EvaluationSet` and baseline `PredictionSet` while exporting the baseline's actual evaluation. Later invocations use their `load` methods, preserving the original evaluation binding. The error tolerance is fixed in the caller's versioned configuration. If the evaluator does not retain keyed predictions, it must first add an output export. This is real setup work; the public evidence does not tell us whether Neuralink already has that output.

Finally, call `compare(evaluation, baseline, candidate, tolerance=..., output_dir=...)` at evaluation completion. Use a new comparison directory beside the job's existing artifacts. The return value is a result dictionary, including `result["sessions"]` and `result["complete"]`. A framework-specific callback, new experiment tracker, and new UI destination are unnecessary.

## Recurring experience

After that integration, the engineer runs the same candidate evaluation command as before. Saved baseline predictions are reused. The comparison appears beside the ordinary results without a second model run or manual file collection.

The first report view answers:

1. Which exact baseline, candidate, and evaluation set am I looking at?
2. Is the comparison complete, and which sessions became worse beyond the chosen tolerance?
3. Which session should I inspect first, and what exact observations support that finding?

Sort valid sessions by descending candidate-minus-baseline RMSE in velocity units, with invalid sessions prominently listed. Keep the full table available. A pooled score is secondary context. When no session exceeds tolerance, say so without labeling the candidate safe or ready to ship.

A session-row link jumps to its detail within the same report. `reproduce(bundle_dir)` verifies the saved artifacts and recomputes the comparison without loading models. Users return to their existing evaluator when they need to regenerate predictions or investigate model internals.

## Implemented example

From the repository root:

```sh
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --candidate-id candidate-002
```

Start with a fresh example directory. The first invocation saves the evaluation and baseline under `runs/demo/pinned/`. The second loads those files and saves a separate comparison for the same synthetic predictions under a new candidate ID. Each invocation prints its report path and verifies scoring reproduction. Existing candidate comparison directories are not overwritten.

This demonstrates the product's reuse path. It does not execute neural models or establish integration with any team's evaluator.

## Friction budget

These remain usability acceptance goals. The synthetic script provides the integration shape; actual engineer adoption has not been measured:

- After setup, zero additional manual commands to produce a comparison.
- One action to open the report and one to inspect a session.
- No repeated baseline selection, column mapping, or metadata entry for an unchanged evaluation set.
- No model rerun when compatible predictions are already available.
- No new server, login, data migration, or dependency on Neuralink's Electron fork.
- No silent baseline replacement, evaluation-set changes, or deletion of invalid sessions in pursuit of convenience.

Check report interaction in the synthetic example and retain the same flow for the future public-recording demonstration. Verify actual integration effort with an engineer before claiming it fits Neuralink's workflow. The key unknowns are retained prediction granularity, stable sample identities, and how the team names a reference run and evaluation set.
