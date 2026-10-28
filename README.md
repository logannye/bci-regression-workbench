# BCI Regression Workbench

**Find the recording sessions where a new decoder performs worse, and reproduce each finding.**

An independent open-source project by Logan Nye, designed for presentation to Neuralink's BCI ML engineering team. This is not an official Neuralink project or an implemented integration with its internal systems.

**Status: project specification only.** The repository contains the proposed scope, design, and evaluation plan. No comparison library, output importer, report generator, or scientific results have been implemented yet.

## One benefit

A decoder update can improve an overall score while making particular recording sessions worse. An engineer needs to see those regressions before deciding what to investigate or test next.

The workbench will compare saved predictions from baseline and candidate evaluations on the same declared recording samples. Its output will identify which sessions became worse, show the size of each change, and preserve the evidence needed to recompute those differences.

Reproducibility supports that single benefit. It is not a separate experiment-management platform.

## Form factor: a small step in the existing evaluation job

The primary interface will be a Python comparison function called after the engineer's normal evaluation finishes. It consumes keyed predictions and targets, returns the session comparison table, and writes a self-contained report beside the existing evaluation artifacts.

Engineers keep their model code, inference environment, data access, and evaluation command. They do not load a model into this tool. A one-time output mapping and pinned baseline enable the recurring path: run evaluation as usual, then open the comparison report. No new account, server, or dashboard is needed.

See [Workflow](docs/WORKFLOW.md) for the intended user experience and first-time setup.

## Built for a specific engineering decision

The intended user is a Neuralink BCI ML engineer reviewing a proposed decoder change. Neuralink's public [ML role](https://job-boards.greenhouse.io/neuralink/jobs/5663271003) explicitly includes building evaluation infrastructure for model updates. That supports the relevance of the problem; it does not establish a gap in their existing internal tools.

The question this project will answer is:

> On the same recorded sessions, where did candidate B become worse than baseline A?

It will not decide whether a model is ready to deploy. Recorded replay cannot recreate how a person changes their behavior in response to a different decoder.

## First version

| Decision | Scope |
| --- | --- |
| Task | Compare existing two-dimensional movement-velocity predictions with fixed reference labels. |
| Public demonstration | One multi-session dataset and two fixed decoders; dataset selection and reuse terms remain to be verified. The demonstration's prediction producer is separate from the product. |
| Inputs | Keyed baseline predictions, candidate predictions, and a frozen evaluation table. Model binaries are not required for scoring. |
| Primary metric | Per-session velocity vector RMSE, in declared physical units. |
| Comparison | Paired predictions on identical, predeclared sample identities. |
| Output | A session comparison table, a short local report, and evidence to reproduce the scoring. |
| Neuralink repository used | A thin `datarepo` example reads the required prediction/target tables and exposes comparison rows. The core also accepts typed tables directly; no catalog migration is required. |

If the public recordings contain physical reaching rather than attempted cursor movement, the demonstration will be described as an offline movement-decoding example. It will not be presented as a Neuralink participant evaluation.

## Intended workflow

1. Once, map existing evaluation outputs and explicitly pin a baseline and evaluation set.
2. Run the normal candidate evaluation; its final step invokes the comparison.
3. Open the report beside the normal evaluation results, with baseline and evaluation-set identities visible.
4. Select a worsened session to inspect its paired errors and exact supporting samples.
5. Recompute the comparison from the preserved predictions, targets, and comparison specification.

These steps describe planned behavior. There is no executable interface yet. The product reproduces score comparisons; regenerating model predictions remains the existing evaluator's responsibility.

## What would make the project useful

The first demonstration must expose a deliberately constructed tradeoff: the candidate's pooled error improves while its error on a known session worsens. It must show that result without dropping difficult samples, changing the scoring set, or hiding invalid sessions.

A clean environment must then reproduce the scores from preserved outputs within a declared numerical tolerance. The constructed tradeoff tests the workbench; it is not evidence of a better neural decoder. After initial integration, the target is zero additional manual comparison commands, one action to open the report, and one action to inspect a session. These are usability acceptance goals, not measured results.

## Explicitly outside the project scope

No model execution framework, dashboards, latency benchmarking, fault-injection platform, automatic root-cause diagnosis, drift monitoring, new decoder research, online adaptation, calibration study, live implant integration, or release-approval system. Neuralink's historical Electron fork is not a dependency.

## Project documents

- [Design](docs/DESIGN.md): the minimum inputs, comparison procedure, and outputs.
- [Workflow](docs/WORKFLOW.md): one-time integration and the recurring evaluation experience.
- [Evaluation](docs/EVALUATION.md): metric, validity rules, and acceptance cases.
- [Implementation plan](docs/PLAN.md): the short path from specification to a useful demonstration.
- [Sources and assumptions](docs/SOURCES.md): public evidence and unresolved integration questions.
- [Contributor instructions](AGENTS.md): the scope guardrail and development constraints.

## License

[MIT](LICENSE). Dependency and dataset licenses apply separately. No Neuralink code or data is vendored in this initial repository.
