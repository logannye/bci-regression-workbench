# Contributor instructions

## Product constraint

Optimize for exactly one benefit: find sessions where a fixed candidate decoder performs worse than a fixed baseline on identical declared recording samples, and reproduce those score comparisons.

The product consumes keyed outputs from the user's existing evaluator. Do not require model loading, a custom decoder runner, or a new training environment. Reproduction means recomputing scores from preserved predictions and labels; regenerating predictions remains the producer's responsibility. A public example may generate predictions separately.

Do not expand the design with dashboards, timing benchmarks, synthetic stress platforms, broad adapters, automated diagnosis, adaptation, calibration experiments, new model research, or deployment gates. Reproducibility and input validity are requirements of the one benefit. A second independent benefit requires an explicit user change to scope.

The first comparison/report/scoring-reproduction slice and synthetic example are implemented. Public-recording evaluation and Neuralink integration remain unperformed. Keep documentation honest about implemented behavior, planned work, and measured results. Verify executable examples before documenting them. The optional datarepo environment requires its own real hosted validation; core tests do not establish that integration works.

## Evaluation discipline

- Follow docs/EVALUATION.md. Freeze the dataset, partitions, metric, preprocessing, artifacts, and thresholds before opening evaluation results.
- In a future public-recording example, keep evaluation labels outside decoder code and require causal inputs and declared reset rules. Current synthetic fixtures construct predictions directly. For imported outputs, record producer-supplied protocol provenance; do not claim the comparator independently verifies model execution or training independence.
- Bind prediction outputs to their evaluation identity when exported. Reuse saved baseline bundles through loading; never relabel old predictions against a changed evaluation set to make a comparison pass.
- Preserve every selected session in results, including invalid rows. Do not hide failed comparisons or change denominators to improve scores.
- Use synthetic fixtures to verify the evaluator, not to claim biological robustness or decoder improvement.
- Record tested revision, dependency environment, platform, and reproduction evidence.
- Keep raw recordings, model binaries, credentials, and large run artifacts out of Git. Publish only data permitted for redistribution.

## Repository relationship

This is Logan Nye's independent project intended for presentation to Neuralink's BCI ML team. Do not imply sponsorship, collaboration, private-data access, or internal integration. Prefer a thin use of upstream datarepo over a fork or replacement platform.

## Native build storage

User preference established September 29, 2026, applies to any Rust introduced later:

- Keep edits, formatting, documentation checks, and other non-build static work local. Run native compilation, executable native tests, extension rebuilds, and packaging on hosted CI or an already-authorized remote environment by default.
- Local Rust compilation is opt-in, including cargo check/clippy/test/build and implicit uv/maturin builds. Require explicit authorization for the work, then reuse it for necessary commands. Avoid lightweight commands that silently rebuild native packages.
- Batch coherent changes before native validation. Preserve required tests and release gates, record revision/platform, and never claim unperformed validation. If remote validation is unavailable, continue static work and report what remains unvalidated.
- Reuse compatible installed native libraries for Python-only changes. Changed Rust requires a rebuilt library in the validation environment before integration testing.
- If local compilation is authorized, use focused checks, one reusable build directory, and one native validation process. Prefer debug = 0 and incremental = false unless debugger needs justify otherwise; explain the tradeoffs.
- Before substantial local builds, inspect disk space and artifact size. Keep disposable outputs bounded. Clean only identified inactive regenerable task outputs at validation boundaries; preserve user data and useful failure evidence. Use managed pruning, not unrelated cache deletion. Temporary directories still consume local disk.
