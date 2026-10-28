# Pinned evaluator-hook validation

Recorded October 28, 2026. This change removes repeated reference/configuration glue from an existing evaluator. It does not add a model runner, new metric, or deployment decision.

## Tested source and environment

- Implementation head: `2866339fdedd661057537437725ef79a64ed7dd2`.
- Hosted pull-request merge: `aefa4fb109c2cdecb8965b1d54f482622b839322`; its tree matches that implementation head.
- [Hosted run 40744448413](https://github.com/logannye/bci-regression-workbench/actions/runs/40744448413): all four jobs passed.
- `pinned.py` SHA256: `d1dccdc567e67d4d7372a50eadb350b1869e45bb740acbb53c72b9693611c987`.
- Unchanged core comparator digest: `95d50f159a4ac854fb0d7f7bb3e7282e7fa7ca7ec1a20b526dd2d20e9ea79a83`.

The new class is imported from `bci_regression.pinned`. The original four comparator modules and the frozen public producer/protocol are unchanged. Score reproduction still requires those four comparator sources; loading a pin additionally requires its recorded hook source. Changing hook code requires the recorded version or an explicitly new pin. Pin fingerprints establish content identity, not authenticity of producer claims.

| Environment | Outcome |
| --- | --- |
| Local macOS Darwin 25.2.0 arm64, Python 3.14.6, installed NumPy 2.4.1 | 119 discovered: 110 passed, 9 skipped for unavailable optional dependencies. All 20 new hook tests passed. |
| Ubuntu 24.04, Python 3.10.22 / 3.12.15 / 3.14.9, no optional dependencies | 119 discovered per job: 87 passed, 32 optional tests skipped. All hook tests, explicit initialization plus two ordinary candidate commands, score reproduction, and pure Python wheel installation/import passed. |
| Ubuntu 24.04, Python 3.11.17, pinned datarepo/Arrow environment | 119 discovered: 89 passed, 30 public-producer tests skipped because NumPy/HDF5 dependencies were absent. All hook and Arrow tests, real upstream Parquet query/collect, and comparison reproduction passed. |
| Hosted datarepo artifact downloaded to macOS | Its comparison score-reproduced successfully using the unchanged core. |

The [resolved optional environment](validation/2026-10-28-pinned-datarepo-environment.txt) records dependencies. Optional skips are not passes. This iteration did not rerun the frozen public model experiment; its separate producer validation remains recorded in [public results](public-demo/RESULTS.md). No local package installation or native compilation was used.

## Acceptance checks

The runnable [example](../examples/basic_comparison.py) now separates one-time reference initialization from the normal candidate command. The initializer stores evaluation, complete baseline predictions, a noncanonical output-column mapping, tolerance, numerical tolerance, and description. The normal path constructs its actual current evaluation and candidate outputs, then calls the hook once. It performs no baseline prediction construction and selects no new reference/settings.

Two candidate runs reused byte-identical pin files, wrote separate reports, and reproduced their scores. The constructed pooled improvement still exposed `session-03` as worse. Tests verify direct-core equivalence and preserve complete expected counts for invalid outputs.

Additional tests and independent adversarial review checked:

- Changed targets, sample keys, timestamps, masks, units, coordinates, horizon, or stale in-memory fingerprints are rejected before consuming candidate rows.
- Incomplete/incompatible baselines cannot be pinned. Changed configuration, files, source identities, or a replaced pin cannot silently alter an already loaded check.
- Missing, duplicate, unknown, and nonfinite candidate outputs retain incomplete reports and expected session denominators; structural column errors raise explicitly.
- Existing pin/report directories are never overwritten. Publication failures remove only this operation's files and preserve unrelated content.
- Reports cannot be written inside the pin, including through symlink aliases. Independent review caught this edge before commit; it was fixed and regression-tested.
- Reserved pin provenance cannot be supplied by a caller. Unrelated producer metadata is retained.

## Replay of the existing public outputs

A local replay used the already exported Indy evaluation/baseline/candidate bundles. It verified all 26 original receipt hashes and reproduced the original comparison before creating a new pin. Both subsequent hook comparisons reproduced, with unchanged pin bytes and exactly equal session scores, paired samples, exclusions, and pooled metrics.

All 14,052 expected samples remain scored. The per-session candidate-minus-baseline deltas remain −14.1523, −16.6435, and −5.8046 mm/s; descriptive regression flags remain null. No recordings were downloaded, no models were fitted or executed, and no new scientific comparison was selected. This tests a new integration route over the same evidence.

The [aggregate verification record](validation/pinned-hook-v1.json) binds source identities and results. Full local replay bundles are retained with this task; predictions and model snapshots are not added to Git.

## Limits and next validation

This establishes a reusable integration pattern and preserved scoring behavior. It does not measure onboarding time, throughput, memory at production scale, or usefulness inside Neuralink. The current implementation materializes evaluation and prediction records and revalidates reference contents on each comparison.

Before expanding features, validate one real integration with an intended engineer: whether the evaluator retains predictions at stable session/sample keys, how it declares actual labels/eligibility, how a reference run is chosen, and whether this session view is missing from current tooling. The engineer should run one normal evaluation and reach an actionable session through the existing artifact destination. That validation has not occurred.
