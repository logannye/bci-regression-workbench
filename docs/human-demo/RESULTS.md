# Human recording demonstration results

**Complete offline comparison.** The fixed four-bin history candidate has lower inferred-target vector RMSE on all twelve evaluation days. All **324,732 / 324,732** expected samples were scored. There is no session-level error increase in this experiment; local added-error windows can still occur within improved days.

Pooled RMSE decreased from **0.4297063542** to **0.4118571201** dataset coordinate units (delta **−0.0178492341**). This is agreement with inferred cursor-to-target displacement, not measured intended velocity or demonstrated live control benefit. There is no categorical regression threshold or significance claim.

| Day | Scored bins | Baseline RMSE | Candidate RMSE | Candidate − baseline |
| --- | ---: | ---: | ---: | ---: |
| 675 | 25,561 | 0.26896312 | 0.24293630 | -0.02602682 |
| 689 | 28,479 | 0.26739191 | 0.25176385 | -0.01562806 |
| 692 | 28,132 | 0.25634110 | 0.23889746 | -0.01744363 |
| 702 | 27,129 | 0.29620723 | 0.27724288 | -0.01896435 |
| 709 | 28,794 | 0.31456644 | 0.30096514 | -0.01360129 |
| 715 | 28,946 | 0.33517896 | 0.31984584 | -0.01533312 |
| 727 | 29,379 | 0.47116522 | 0.44940692 | -0.02175831 |
| 751 | 14,260 | 0.26798195 | 0.24894107 | -0.01904088 |
| 758 | 28,902 | 0.65922649 | 0.63546187 | -0.02376462 |
| 770 | 29,140 | 0.58867957 | 0.56398285 | -0.02469672 |
| 783 | 29,279 | 0.53660272 | 0.53141153 | -0.00519119 |
| 800 | 26,731 | 0.51574918 | 0.49250378 | -0.02324540 |

## Fixed source and denominators

The plan was committed and pushed in `6e983e142a47d828c8f1ec2fb4c800e3406ffee7` before fitting. Execution used `ca4695da8e139643bc2baba2208a0609bd05b0e4`, Python 3.12.14, NumPy 2.2.6, SciPy 1.15.3 and OpenBLAS 0.3.29 on macOS arm64, with one BLAS thread.

All 29 released T11 task blocks were retained. The earliest three days supplied 85,423 eligible training bins. The twelve later days contain 348,967 total bins: 324,732 scored and 24,235 retained as excluded. Exclusions are exactly 10,255 outside-trial bins, 9,969 bins in source-excluded trials, and 4,011 shared history-warmup bins. No result-driven exclusions were added.

The actual files contain 1,839 trials and 35 exclusion flags, rather than the paper summary of 1,840 and 34. Stored target vectors match cursor-to-target displacement within float32 rounding. Zero targets remain eligible when the task mask permits.

## Validation

Both models were fitted once on training rows only. All evaluation predictions were saved before evaluation-label loading in that execution. Baseline initialization and candidate comparison used the standard pinned hook. Saved score reproduction passed.

The independent auditor verified all 87 source MATLAB file hashes, the complete masks and target values, source-only feature and target statistics, saved ridge optimality without refitting, every saved prediction, and all session and pooled scores. Reconstructed predictions matched exactly on the tested platform. Independent pooled arithmetic differs only by floating-point summation rounding.

Local preflight: 173 tests discovered, 164 passed, 9 optional-dependency skips. All human producer, audit and target-semantics tests ran. Default velocity identities, formula, localization and rendered fixture remain compatible. Hosted checks and browser acceptance are recorded separately in the validation receipt.

The macOS Accelerate wheel produced a numerical exception on a finite synthetic matrix test before any recording fit. Switching to the same pinned NumPy version’s OpenBLAS wheel resolved it. No model guard, data selection or scientific setting was changed.

## Interpretation

This is one participant’s recorded cursor task, collected under an existing online decoder. The two ridge models are new offline examples, not the original LSTM and not a reproduction of the MINDFUL algorithm. The inferred displacement target is a proxy for movement intention. Lower error does not establish that a participant would control a cursor better with the candidate.

Features were released with noncausal processing. History uses current and earlier released bins, but this is not an end-to-end causal or latency experiment. Training-only scaling is fixed across later days; no adaptation or hyperparameter search was performed. Structural label inspection and prior knowledge of the published study are acknowledged in the frozen plan.

[Frozen plan](PLAN.md) · [Exact result receipt](result-v1.json) · [Independent audit](audit-v1.json) · [Reproduction](REPRODUCE.md) · [Public dataset](https://doi.org/10.5061/dryad.n2z34tn5s)
