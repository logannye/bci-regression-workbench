# Contributor instructions

## Product constraint

Optimize for exactly one benefit: find sessions where a fixed candidate decoder performs worse than a fixed baseline on identical declared recording samples, and reproduce those score comparisons.

The product consumes keyed outputs from the user's existing evaluator. Do not require model loading, a custom decoder runner, or a new training environment. Reproduction means recomputing scores from preserved predictions and labels; regenerating predictions remains the producer's responsibility. A public example may generate predictions separately.

Do not expand the design with dashboards, timing benchmarks, synthetic stress platforms, broad adapters, automated diagnosis, adaptation, calibration experiments, new model research, or deployment gates. Reproducibility and input validity are requirements of the one benefit. A second independent benefit requires an explicit user change to scope.

The first comparison/report/scoring-reproduction slice, synthetic workflow, and optional datarepo integration have passed the checks recorded in [Validation](docs/VALIDATION.md). The frozen public-recording demonstration, independent audit, and scoring reproduction also passed; see [Public demonstration results](docs/public-demo/RESULTS.md). Its candidate had lower RMSE on all three selected sessions; do not manufacture a regression or generalize that result to other recordings. Intended-engineer usability and Neuralink integration remain unperformed. Keep documentation honest about implemented behavior, planned work, and measured results. Verify executable examples before documenting them. Continue validating the optional datarepo environment separately; core tests alone do not establish that integration works.

The separate [human MINDFUL T11 comparison](docs/human-demo/RESULTS.md) completed on all twelve evaluation days and 324,732 eligible samples, with saved score reproduction and an independent prediction audit. Its inferred cursor-to-target displacement labels are a proxy, not measured intended velocity. Preserve this explicit target kind and the recorded source identity. The released neural features include noncausal preprocessing; current/past released bins do not establish end-to-end causal decoding. Lower offline error is not evidence of improved live control. Preserve the frozen human plan and the earlier Indy artifacts separately.

## Evaluation discipline

- Follow docs/EVALUATION.md. Freeze the dataset, partitions, metric, preprocessing, artifacts, and thresholds before opening evaluation results.
- Preserve each completed demonstration's frozen protocol and all selected session results. Separate producers keep evaluation labels outside decoder inference and follow declared reset rules. The Indy producer uses causal inputs; the human example's released preprocessing is noncausal as noted above. Any later experiment requires a new prospective protocol. Synthetic fixtures construct predictions directly. For imported outputs, record producer-supplied protocol provenance; do not claim the comparator independently verifies model execution or training independence.
- Bind prediction outputs to their evaluation identity when exported. Reuse saved baseline bundles through loading; never relabel old predictions against a changed evaluation set to make a comparison pass.
- Preserve every selected session in results, including invalid rows. Do not hide failed comparisons or change denominators to improve scores.
- Use synthetic fixtures to verify the evaluator, not to claim biological robustness or decoder improvement.
- Record tested revision, dependency environment, platform, and reproduction evidence.
- Keep raw recordings, model binaries, credentials, and large run artifacts out of Git. Publish only data permitted for redistribution.

## Repository relationship

This is Logan Nye's independent project intended for presentation to Neuralink's BCI ML team. Do not imply sponsorship, collaboration, private-data access, or internal integration. Prefer a thin use of upstream datarepo over a fork or replacement platform.
