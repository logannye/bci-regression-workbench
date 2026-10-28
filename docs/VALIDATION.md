# Initial implementation validation

Recorded October 28, 2026. This validates comparison software and a synthetic workflow, not a neural decoder or an internal Neuralink integration.

## Tested source

- Implementation head: `0f82fde32e5c510efc59800eaf5eb8c0a8aeaa02`.
- GitHub's tested pull-request merge: `a5cdd48bab2617f35fe0cc6ca6234aa609567be6`.
- Comparator source digest: `95d50f159a4ac854fb0d7f7bb3e7282e7fa7ca7ec1a20b526dd2d20e9ea79a83`.
- Successful hosted run: [40735266228](https://github.com/logannye/bci-regression-workbench/actions/runs/40735266228).

The source digest covers the four package source files and is also recorded in each comparison bundle. Reproduction requires that exact source content. These results apply to the recorded source; future code changes need their own validation.

## Checks performed

| Environment | Checks | Outcome |
| --- | --- | --- |
| Local Python 3.14.6, Darwin 25.2.0, arm64 | Standard-library suite; synthetic example twice with the same saved baseline; score reproduction | 65 passed; 2 optional Arrow tests skipped; both examples reproduced |
| Ubuntu 24.04.5, Python 3.10.22, 3.12.15, 3.14.9 | Suite in each environment; recurring synthetic example and scoring reproduction; pure Python wheel build, install, and import outside the source directory | 65 passed and 2 optional tests skipped per environment; all example and packaging steps passed |
| Ubuntu 24.04.5, Python 3.11.17 | Full suite with real Arrow/Parquet; upstream datarepo query/collect, comparison, and scoring reproduction | 67 passed, none skipped; integration passed |
| Linux bundle reproduced on local macOS/Python 3.14.6 | Verify downloaded CI artifact hashes and recompute its scores using the standard-library core | Passed |

The optional environment used `data-repository==0.1.0`, `polars==1.12.0`, `deltalake==0.25.5`, and `pyarrow==18.1.0`. All dependencies were installed from wheels. The [resolved environment](validation/2026-10-28-datarepo-environment.txt) records the remaining packages. No local native compilation or optional dependency installation was performed.

The hosted `synthetic-datarepo-evidence` artifact contains local synthetic Parquet inputs, the comparison bundle, environment listing, and actual checked-out revision. Its hosted retention is 14 days; the fixture can be regenerated from the tested source and environment. No neural recordings, model weights, credentials, or private inputs are included.

## What the fixture establishes

The datarepo fixture has eight samples in `long-session` and two in `short-session`. Baseline vector RMSE is 1.0 in both. Candidate RMSE is 0.25 and 2.0 respectively. Pooled candidate RMSE is `sqrt(0.85)`, approximately 0.921954, below the baseline's 1.0; the short session is correctly reported as a regression. These are constructed arithmetic values, not scientific results.

Tests additionally cover hand-calculated vector RMSE, key-based alignment, duplicate and missing predictions, fixed scoring populations, incompatible declarations, nonfinite inputs, invalid-session visibility, evidence tampering, output publication failure, and score recomputation. Report tests cover escaping, bounded previews, ordering, and native session links.

The synthetic report was visually inspected at a 1265 × 712 browser viewport. Run identities, completeness, and the worsened session were visible on opening. One click on that session reached its paired error trace and sample references. This is a check of the example interaction, not measured adoption by Neuralink engineers.

## Preserved failure and remaining work

[Run 40734920825](https://github.com/logannye/bci-regression-workbench/actions/runs/40734920825) failed before running jobs because a colon in an unquoted YAML command made the workflow invalid. Commit `c725245` corrected the command. A concurrent main-branch README edit was merged before the successful run. The failed run is not treated as test execution.

No public neuroscience dataset, trained decoder, live BCI, or Neuralink internal evaluator has been evaluated. The current implementation materializes inputs and paired samples in memory; large-recording memory and runtime behavior have not been benchmarked. The next product validation is one prespecified public-recording comparison, followed by feedback on the real integration effort from an intended engineer.
