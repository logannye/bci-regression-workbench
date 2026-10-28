# Contributor instructions

## Product constraint

Optimize for exactly one benefit: find sessions where a fixed candidate decoder performs worse than a fixed baseline on identical recorded inputs, and reproduce those findings.

Do not expand the design with dashboards, timing benchmarks, synthetic stress platforms, broad adapters, automated diagnosis, adaptation, calibration experiments, new model research, or deployment gates. Reproducibility and input validity are requirements of the one benefit. A second independent benefit requires an explicit user change to scope.

This repository currently contains a specification only. Keep documentation honest about implemented behavior, planned work, and measured results. Do not add installation instructions or executable command examples until they work.

## Evaluation discipline

- Follow docs/EVALUATION.md. Freeze the dataset, partitions, metric, preprocessing, artifacts, and thresholds before opening evaluation results.
- Keep evaluation labels outside decoder code; require causal inputs and fixed state-reset rules.
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
