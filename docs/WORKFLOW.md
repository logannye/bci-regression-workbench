# Workflow

Status: proposed user experience. Neuralink's internal evaluator, experiment tracker, and review interfaces are not known to us.

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

An engineer maps the current evaluator's session/sample keys and two-dimensional predictions to the small table contract. The evaluation table supplies the reference labels and fixed eligible set. The mapping also captures available run and configuration identities automatically.

The engineer selects a baseline output bundle and fixes the evaluation identity and error tolerance in versioned configuration. If the evaluator does not retain keyed predictions, it must first add an output export. This is real setup work; the public evidence does not tell us whether Neuralink already has that output.

Finally, add the comparison call at evaluation completion and save its artifacts in the job's existing output location. A framework-specific callback, new experiment tracker, and new UI destination are unnecessary.

## Recurring experience

The engineer runs the same candidate evaluation command as before. Baseline predictions are reused. The comparison appears beside the ordinary results without a second model run or manual file collection.

The first report view answers:

1. Which exact baseline, candidate, and evaluation set am I looking at?
2. Is the comparison complete, and which sessions became worse beyond the chosen tolerance?
3. Which session should I inspect first, and what exact observations support that finding?

Sort valid sessions by descending candidate-minus-baseline RMSE in velocity units, with invalid sessions prominently listed. Keep the full table available. A pooled score is secondary context. When no session exceeds tolerance, say so without labeling the candidate safe or ready to ship.

A session selection opens its detail within the same report. The evidence bundle allows recomputation of the comparison. Users return to their existing evaluator when they need to regenerate predictions or investigate model internals.

## Friction budget

These are acceptance goals, not performance claims:

- After setup, zero additional manual commands to produce a comparison.
- One action to open the report and one to inspect a session.
- No repeated baseline selection, column mapping, or metadata entry for an unchanged evaluation set.
- No model rerun when compatible predictions are already available.
- No new server, login, data migration, or dependency on Neuralink's Electron fork.
- No silent baseline replacement, evaluation-set changes, or deletion of invalid sessions in pursuit of convenience.

Measure this flow in the public demonstration. Verify the actual integration effort with an engineer before claiming it fits Neuralink's workflow. The key unknowns are retained prediction granularity, stable sample identities, and how the team names a reference run and evaluation set.
