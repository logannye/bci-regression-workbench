# Frozen public-recording demonstration

This plan is committed before downloading or opening any selected recording. Only public metadata, file names, file sizes, checksums, and the dataset's format description have been inspected. The published `refh_results.csv` performance results have not been consulted. [protocol-v1.json](protocol-v1.json) is the machine-readable authority for this experiment; preserve its bytes after freezing.

## Dataset and selection

Use O'Doherty, Cardoso, Makin, and Sabes, *Nonhuman Primate Reaching with Multichannel Sensorimotor Cortex Electrophysiology*, [Zenodo version 2, DOI 10.5281/zenodo.3854034](https://zenodo.org/records/3854034), licensed CC BY 4.0. These are macaque physical-reaching recordings with measured cursor position; the cursor follows the animal's hand. The demo derives velocity from that measured position, not from the desired target location. It is an offline movement-decoding example.

To bound transfer and computation without consulting outcomes, use the first four distinct September 2016 recording dates for Indy, taking the earliest file on each date:

| Role | Recording |
| --- | --- |
| Train both models | `indy_20160915_01` |
| Evaluation | `indy_20160916_01` |
| Evaluation | `indy_20160921_01` |
| Evaluation | `indy_20160927_04` |

The four published files total 460,047,972 bytes. Their exact URLs, sizes, and published MD5 checksums are pinned in the protocol; execution additionally records SHA-256. Use the first 300 seconds, or the complete shorter recording, of each file. No alternative sessions may replace a disappointing or invalid one.

## Fixed comparison

The baseline is ridge regression on the current completed neural bin. The candidate is ridge regression on that bin and the preceding three bins. Both use the same source-day rows, source-only standardization, float64, an unpenalized intercept, and ridge coefficient 1.0 for the mean-squared-error objective. There are exactly two fits and no parameter search, adaptation, calibration, or held-out model selection.

Bins span 16 position-sampling intervals, nominally 64 ms. Counts include spikes in the half-open interval from bin start up to bin end; divide by the actual duration. Sum sorted and residual unsorted events for each of the 96 named M1 channels, aligned by channel identity. Do not transfer sorted-unit indices across days. All channels must be present; no intersection or missing-channel fill is allowed.

At each bin's end, predict its average x/y cursor velocity in mm/s. Compute reference velocity as the measured position difference over that bin divided by its duration. No future neural sample, target position, or evaluation position enters inference. Both models and all evaluation predictions must be saved before evaluation position arrays are opened. Each file starts fresh; there is no state crossing session boundaries.

The first three complete bins of every file are declared warmup for both models and remain visible as excluded rows. Every later complete bin is scored, including stationary periods. The protocol defines structural admission checks. A failed file aborts the comparison and produces a receipt listing the entire fixed selection; it never becomes a silently smaller cohort.

## Reporting and completion

Report every evaluation session using the workbench's existing vector RMSE and signed candidate-minus-baseline delta. The reporting tolerance is `null`: no defensible material-degradation threshold has been established for these units, so report descriptive changes without categorical claims. Numerical reproduction tolerance is 1e-9 mm/s. Pooled error is sample-weighted context only.

The demo succeeds when the fixed three-session comparison is complete, all artifacts have recorded identities, independent arithmetic agrees, and the saved scoring bundle reproduces. Improvement, a hidden regression, statistical significance, and deployability are not success requirements. Preserve the observed result even if the candidate improves everywhere or worsens everywhere.

Execution uses hosted Linux with pinned wheel-only dependencies and a 20-minute limit. Raw recordings stay out of Git and uploaded artifacts. Keep full derived evidence outside Git; publish the aggregate table, recipe, hashes, environment, and limitations. Record any execution failure or implementation repair without changing the frozen scientific choices.
