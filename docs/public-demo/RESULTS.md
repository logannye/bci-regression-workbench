# Public Indy recording demonstration

**Completed: the candidate had lower error on all three held-out recording days. No session-level error increase was observed.** The tool preserved every expected sample and reproduced the full comparison. This result validates a real-data example of its workflow; the deliberate regression-detection checks remain the separate synthetic tests.

## Fixed experiment

The [plan](PLAN.md) and [machine-readable protocol](protocol-v1.json) were frozen in commit `b88ecd5cb920305bc1194b8ff758b6bf19c3cecf` before selected recordings were downloaded or opened. Dataset: O'Doherty et al., [public Indy physical-reaching recordings, Zenodo version 2](https://zenodo.org/records/3854034), CC BY 4.0.

Both ridge decoders were fitted once on September 15, 2016. The baseline used the current completed 64 ms neural bin; the candidate used that bin and three preceding bins. All 96 named M1 channels were aggregated by electrode, including sorted and residual unsorted events. Source-only standardization, ridge penalty, common warmup, and all other choices stayed fixed. There was no sweep, calibration, adaptation, or outcome-driven rerun.

Each selected recording supplied its first 300 seconds. There were 4,687 complete bins per file; the first three were prespecified warmup. Both models therefore fitted on the same 4,684 source rows and scored the same 4,684 rows on each evaluation day. All six prediction files were saved before any evaluation cursor-position array was read. Labels were measured hand-controlled cursor velocity, not intended target direction.

## Per-session result

Vector RMSE and differences are in **mm/s**. Difference is candidate minus baseline; negative means lower candidate error. No substantive regression threshold was justified, so the frozen reporting tolerance was `null` and results are descriptive.

| Recording | Scored / expected | Baseline RMSE | Candidate RMSE | Difference |
| --- | ---: | ---: | ---: | ---: |
| `indy_20160916_01` | 4,684 / 4,684 | 91.027034 | 76.874726 | −14.152308 |
| `indy_20160921_01` | 4,684 / 4,684 | 112.252325 | 95.608846 | −16.643479 |
| `indy_20160927_04` | 4,684 / 4,684 | 103.403608 | 97.599023 | −5.804585 |

Sample-weighted pooled context across all **14,052** scored bins: baseline **102.597615**, candidate **90.510302**, difference **−12.087313 mm/s** (11.78% lower). There were no invalid sessions and no missing scored predictions. Nine declared warmup rows remain in the evaluation evidence, excluded equally for both models. Incomplete trailing intervals were outside the complete-bin selection.

## Execution and verification

- [Hosted run 40738828979](https://github.com/logannye/bci-regression-workbench/actions/runs/40738828979) passed on its first recording execution. Implementation head: `3bb699526644c13d1b0bd6c5142ecde4a2de2c02`; actual tested PR merge: `ff10e82dda29e5319aea5fe98c866a915aa98706`. Their trees are identical.
- Protocol SHA-256: `c7d24fbde2bd727247fb4415d134d10761b3ab204bb4f3af3015dbda02488af9`. The four downloaded files matched their published sizes/MD5 checksums; their additional SHA-256 identities are in the [aggregate receipt](result-v1.json).
- Runtime: hosted Ubuntu 24.04, Python 3.11.17, NumPy 2.2.6, h5py 3.14.0, with BLAS thread counts fixed to one. Dependencies came from wheels; no local native build was performed. See the [resolved environment](environment-v1.txt).
- Before recording access, 99 tests ran: 97 passed; two optional Arrow tests were skipped. Every public-producer test passed without a skip. The separate datarepo job exercised the Arrow integration.
- The independent auditor reconstructed predictions from saved neural-rate arrays and model snapshots, checked source-only normalizers and ridge optimality without refitting, checked full key coverage, and recomputed session/pooled scores independently. The scoring bundle also passed the tool's `reproduce` function.
- Downloaded evidence passed all 26 receipt-hash checks and both verification paths on local macOS/arm64, Python 3.14.6 and NumPy 2.4.1. Maximum reconstructed prediction discrepancy was `7.11e-14 mm/s`, below the frozen `1e-9` tolerance. The auditor verifies retained arrays; it does not independently re-extract neural features or labels from raw files.

The run's `indy-public-demo-evidence` artifact contains the HTML report, scoring bundle, derived arrays, model snapshots, hashes, and attribution, with hosted retention of 30 days. Raw recordings are excluded. Git contains only the recipe and aggregate evidence. [Reproduction instructions](REPRODUCE.md) distinguish re-scoring saved evidence from regenerating predictions.

Recording execution is now an explicitly dispatched workflow so later documentation pushes do not refit models automatically. This scheduling change does not alter the recorded experiment or its producer code.

## Limits and practical use

This is one macaque performing physical reaches, three evaluation days, and two fixed linear models. Adding history also changes parameter count and effective regularization; the result does not isolate the causal effect of history. Bins within a recording are correlated, and no significance, population-wide benefit, or clinical conclusion is claimed.

The result cannot establish performance on Neuralink's private data, attempted movement, or interactive BCI control. It demonstrates that an existing evaluator can export real predictions into the tool and retain a complete, inspectable session comparison. The next product validation is an intended engineer trying the small output mapping and pinned-baseline workflow with permitted outputs.
