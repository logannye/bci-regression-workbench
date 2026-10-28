# Design

Status: proposed, not implemented.

## Core behavior

Given a baseline, a candidate, and a fixed set of sessions, return an inspectable answer to where the candidate's prediction error increased. All design decisions must support this behavior or the validity of its evidence.

## Inputs

### Session manifest

The manifest selects explicit session IDs and source identities before candidate evaluation. It records:

- Dataset identity, reuse terms, subject/session grouping, and evaluation membership.
- Immutable file hashes or retained source versions, plus the source catalog revision.
- Ordered sample IDs, timestamps, input feature names/order, and trial/reset boundaries.
- Two-dimensional target velocity, units, coordinate convention, and fixed prediction horizon.
- Predeclared valid-sample masks and reasons for any exclusions.
- The development/evaluation split and the provenance of preprocessing parameters.

Selection by an unrecorded query against mutable "latest" data is insufficient for reproduction. Historical training overlap cannot be inferred from model weights: supplied training provenance must establish the comparison's declared held-out status, or the report must say that status is unverified.

### Fixed decoder pair

Both artifacts include configuration and fitted preprocessing parameters. The adapter exposes only initialization/reset and chronological prediction. There is no fitting, label access, or update method in version one.

The evaluator owns labels. Each prediction uses only input available up to its declared prediction time. Fitted normalizers and other learned transforms must come from the declared training procedure. No full-evaluation-session normalization or future-looking smoothing is permitted.

Use one simple decoder family for the first implementation. Both versions receive identical feature arrays and sample identities. Each starts from its specified initial state at the same session/trial boundaries; candidate state must never leak into baseline state or across runs.

## datarepo's role

Use the upstream [datarepo](https://github.com/neuralinkcorp/datarepo) interfaces to resolve explicit sessions and expose typed comparison rows. Keep recordings in their existing files. Pin the tested dependency revision/version when the implementation begins.

For the first local Parquet integration, record file content hashes and reject changed sources. If the chosen dataset requires Delta-backed access, reuse its existing transaction-version support and require retained historical files. Implement only the source path actually needed by the selected dataset.

The scoring path should operate on validated arrays after loading. No custom data lake, universal ingestion layer, replacement catalog, hosted service, or credentials manager is required. A `datarepo` catalog alone does not guarantee immutable inputs.

## Comparison procedure

1. Resolve and validate the full manifest and model artifacts.
2. For each session, feed the same causally available feature sequence to each fixed decoder.
3. Match predictions to the predeclared sample IDs and verify dimensions and finite values.
4. Score both outputs on the same valid-sample mask using the one metric in [Evaluation](EVALUATION.md).
5. Emit every session's result, including explicit invalid results. Sort valid comparisons by the candidate-minus-baseline error difference.

No wall-clock pacing or latency measurement is needed. "Replay" means ordered, causal evaluation of recorded inputs.

## Outputs

The first output is a plain table with session ID, evaluated sample count, baseline RMSE, candidate RMSE, absolute difference, validity, and any reason for invalidity. A small report explains the metric and highlights regressions under the predeclared reporting tolerance. All sessions remain visible.

The reproduction bundle records the manifest, source/model digests, configurations, code revision, dependency environment, valid masks, paired predictions, labels or resolvable label references, and result table. Raw data redistribution is subject to its license; reproducibility may require the reader to retrieve permitted source files separately.

The report identifies an affected session and a measurable difference. It does not claim to explain the biological cause or approve a model update. The minimal interface and exact file formats will be implemented only after the evaluation specification and dataset are fixed.
