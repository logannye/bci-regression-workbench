# Workflow

Status: the Python integration point, local report, and saved-baseline synthetic example are implemented and checked as recorded in [Validation](VALIDATION.md). A separate public-recording producer has also exported fixed predictions into the same comparison/report path, with independent audit and scoring reproduction recorded in [Public demonstration results](public-demo/RESULTS.md). The reusable pinned hook passed its own local and hosted [validation](PINNED-VALIDATION.md). The redesigned report passed the browser and hosted checks in [Report interface](REPORT-UI.md). The workflow below remains a proposed fit for Neuralink; its internal evaluator, experiment tracker, and review interfaces are unknown.

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

The engineer exports an `EvaluationSet` and baseline `PredictionSet` while running the baseline's actual evaluation. `PinnedComparison.create(reference_dir, evaluation=..., baseline=..., prediction_columns=..., tolerance=...)` persists them together with fixed reporting settings. It rejects incomplete baseline coverage and refuses any existing reference directory. New settings or a new evaluation set require an explicit new pin.

At evaluator startup, `PinnedComparison.load(reference_dir)` verifies the pin's content hashes and configuration. At evaluation completion, call:

```python
result = check.compare(candidate_outputs, evaluation=current_evaluation,
    run_id=run_id, output_dir=job_dir / "session-regressions", provenance=run_metadata)
```

`current_evaluation` is built from the job's actual labels, keys, timestamps, eligibility, and declared semantics, independently of the pin. It is mandatory. A mismatch fails before output creation, with an instruction to create a new pin; a stale reference is never rebound to changed labels. This detects incompatible declarations and data, not a producer that falsely declares its inputs. The stored column mapping applies only to candidate outputs; it does not discover an evaluator's labels or sample identity.

The returned dictionary retains `result["sessions"]` and `result["complete"]`. Reports appear beside the job's existing artifacts, with pin identity recorded in candidate provenance. The original low-level API remains available. No framework-specific callback, experiment tracker, or UI destination is required.

## Recurring experience

After that integration, the engineer runs the same candidate evaluation command as before. Saved baseline predictions are reused. The comparison appears beside the ordinary results without a second model run or manual file collection.

The first report view answers:

1. Which exact baseline, candidate, and evaluation set am I looking at?
2. Is the comparison complete, and which sessions became worse beyond the chosen tolerance?
3. Which session should I inspect first, and what exact observations support that finding?

Sort valid sessions by descending candidate-minus-baseline RMSE in velocity units, with invalid sessions prominently listed. Keep the full table available. A pooled score is secondary context. When no session exceeds tolerance, say so without labeling the candidate safe or ready to ship.

A session-row link selects its evidence in the adjacent pane, or in the stacked pane on narrow screens. The selected session has a direct URL fragment; native anchors keep every session accessible without JavaScript. Supporting samples and full provenance remain available in disclosures. See [Report interface](REPORT-UI.md) for the interaction and evidence-compatibility contract. `reproduce(bundle_dir)` verifies the saved artifacts and recomputes the comparison without loading models. Users return to their existing evaluator when they need to regenerate predictions or investigate model internals.

## Implemented example

From the repository root:

```sh
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --initialize
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo
PYTHONPATH=src python3 examples/basic_comparison.py --output-dir runs/demo --candidate-id candidate-002
```

Start with a fresh example directory. Initialization stores the evaluation, baseline, prediction column mapping, and tolerances under `runs/demo/pinned/`. The two ordinary candidate commands load the same reference and save reports at `runs/demo/<candidate-id>/session-regressions/report.html`. Each prints its report path and verifies score reproduction. Existing references and comparison directories are not overwritten.

The fixture uses the producer's `recording`, `bin`, `vx`, and `vy` fields. They are mapped once at initialization. The normal candidate path constructs its actual evaluation identity and predictions, then adds one comparison call. It contains no reference creation, baseline prediction construction, or repeated settings entry. This verifies a concrete integration pattern, not integration with Neuralink's evaluator.

The completed [public-recording demonstration](public-demo/RESULTS.md) supplies real neural-recording predictions through the same interface. Its separate producer fits two fixed ridge models on one source recording and exports predictions for three evaluation sessions before scoring. All three candidate session RMSE values were lower, and `tolerance=None` preserves descriptive deltas. The saved bundle supports scoring reproduction without rerunning either model; see the [reproduction instructions](public-demo/REPRODUCE.md). This demonstrates the output contract on public recordings, not adoption by an intended engineer.

## Friction budget

These goals are checked in the synthetic workflow, with browser interaction evidence in [Validation](VALIDATION.md). They are not measurements of setup effort, usability, or adoption by an intended engineer:

- After setup, zero additional manual commands to produce a comparison.
- One action to open the report and one to inspect a session.
- No repeated baseline selection, column mapping, or metadata entry for an unchanged evaluation set.
- No model rerun when compatible predictions are already available.
- No new server, login, data migration, or dependency on Neuralink's Electron fork.
- No silent baseline replacement, evaluation-set changes, or deletion of invalid sessions in pursuit of convenience.

Browser inspection of the synthetic report confirmed that the session table is visible on opening and a single session-row selection reaches the paired error trace. The public-recording demonstration uses the same report structure. Verify actual integration effort with an engineer before claiming it fits Neuralink's workflow. The key unknowns are retained prediction granularity, stable sample identities, and how the team names a reference run and evaluation set.
