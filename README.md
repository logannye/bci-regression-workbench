# BCI Regression Workbench

**Find the recording sessions where a new decoder performs worse, and reproduce each finding.**

An independent open-source project by Logan Nye, designed for presentation to Neuralink's BCI ML engineering team. This is not an official Neuralink project or an implemented integration with its internal systems.

**Status: project specification only.** The repository contains the proposed scope, design, and evaluation plan. No decoder runner, data adapter, report generator, or scientific results have been implemented yet.

## One benefit

A decoder update can improve an overall score while making particular recording sessions worse. An engineer needs to see those regressions before deciding what to investigate or test next.

The workbench will compare two fixed decoders on exactly the same held-out recordings. Its output will identify which sessions became worse, show the size of each change, and preserve the inputs needed to reproduce it.

Reproducibility supports that single benefit. It is not a separate experiment-management platform.

## Built for a specific engineering decision

The intended user is a Neuralink BCI ML engineer reviewing a proposed decoder change. Neuralink's public [ML role](https://job-boards.greenhouse.io/neuralink/jobs/5663271003) explicitly includes building evaluation infrastructure for model updates. That supports the relevance of the problem; it does not establish a gap in their existing internal tools.

The question this project will answer is:

> On the same recorded sessions, where did candidate B become worse than baseline A?

It will not decide whether a model is ready to deploy. Recorded replay cannot recreate how a person changes their behavior in response to a different decoder.

## First version

| Decision | Scope |
| --- | --- |
| Task | Predict two-dimensional movement velocity from recorded neural features. |
| Dataset | One public dataset with multiple sessions and suitable velocity labels; selection and reuse terms remain to be verified. |
| Models | Two fixed decoder artifacts using one shared adapter contract; no fitting or adaptation during evaluation. |
| Primary metric | Per-session velocity vector RMSE, in declared physical units. |
| Comparison | Paired predictions on identical, predeclared sample identities. |
| Output | A session comparison table, a short report, and a minimal reproduction bundle. |
| Neuralink repository used | A thin `datarepo` integration for locating the declared session tables and cataloging the comparison table. |

If the public recordings contain physical reaching rather than attempted cursor movement, the demonstration will be described as an offline movement-decoding example. It will not be presented as a Neuralink participant evaluation.

## Intended workflow

1. Supply a frozen session manifest and baseline/candidate decoder artifacts.
2. Validate that both decoders can be evaluated on the same inputs and labels.
3. Run the fixed decoders in recording order, resetting inference state at the declared boundaries.
4. Inspect every session's error and the candidate-minus-baseline difference.
5. Reproduce a selected finding from its recorded input, model, and environment identities.

These steps describe planned behavior. There is no executable CLI yet.

## What would make the project useful

The first demonstration must expose a deliberately constructed tradeoff: the candidate's pooled error improves while its error on a known session worsens. It must show that result without dropping difficult samples, changing the scoring set, or hiding invalid sessions.

A clean environment must then reproduce the comparison within a declared numerical tolerance. The constructed tradeoff tests the workbench; it is not evidence of a better neural decoder.

## Explicitly outside the project scope

No dashboards, latency benchmarking, fault-injection platform, automatic root-cause diagnosis, drift monitoring, new decoder research, online adaptation, calibration study, live implant integration, or release-approval system. Neuralink's historical Electron fork is not a dependency.

## Project documents

- [Design](docs/DESIGN.md): the minimum inputs, comparison procedure, and outputs.
- [Evaluation](docs/EVALUATION.md): metric, validity rules, and acceptance cases.
- [Implementation plan](docs/PLAN.md): the short path from specification to a useful demonstration.
- [Sources and assumptions](docs/SOURCES.md): public evidence and unresolved integration questions.
- [Contributor instructions](AGENTS.md): the scope guardrail and development constraints.

## License

[MIT](LICENSE). Dependency and dataset licenses apply separately. No Neuralink code or data is vendored in this initial repository.
