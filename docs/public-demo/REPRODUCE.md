# Reproducing the public demonstration

The [frozen plan](PLAN.md) and [protocol](protocol-v1.json) define the experiment. The producer is an isolated example; the `bci_regression` library still only consumes predictions and labels. Do not change the frozen protocol to obtain a preferred outcome.

## Re-score an existing evidence bundle

Use the comparator source revision recorded in the run. Scoring reproduction needs only Python's standard library:

```python
from bci_regression import reproduce

result = reproduce("path/to/indy-demo/comparison")
print(result["sessions"])
```

The bundle retains targets, predictions, eligibility, identities, settings, and hashes. This operation does not fit a decoder or download recordings. It checks the saved files and recomputes the reported scores.

To independently reconstruct the saved predictions from retained neural features and model snapshots, use an environment with NumPy:

```python
from examples.public_recording.audit import audit_run

audit = audit_run("path/to/indy-demo")
print(audit["status"])
```

The independent auditor also checks source-only normalization, the ridge normal equations without refitting, complete sample coverage, and separate session/pooled arithmetic. It verifies the retained arrays; it does not independently extract them again from raw recordings.

## Regenerate the example from public recordings

Regeneration is a separate, explicit experiment execution. It downloads the four pinned files (460 MB total) and fits the two prespecified models. The original execution runs on hosted Ubuntu with binary dependencies; native source compilation is unnecessary. Preserve its exact source revision and environment for comparison.

In an existing Python 3.11 environment with the pinned wheels from `requirements-public-demo.txt`, run from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
PYTHONPATH=src:. python examples/public_recording/run.py \
  --input-dir data/indy-public-v1 \
  --output-dir runs/indy-public-v1
```

The output directory must be new. Existing downloaded inputs are reused only after size and checksum verification. Inputs remain outside the output directory. The driver refuses altered protocol bytes and a different pinned package environment. The hosted workflow in `.github/workflows/public-demo.yml` runs synthetic acceptance tests before opening recordings and retains derived evidence for 30 days.

| Evidence | Purpose |
| --- | --- |
| `protocol.json`, `inputs.json`, `environment.json` | Frozen choices, recording checksums, producer source identity, and runtime |
| `models/`, `source-training.npz` | The two source-day model snapshots and evidence for their fixed fits |
| `features/`, `predictions/`, `predictions-ready.json` | Keyed neural-only inputs/outputs saved before evaluation labels are opened |
| `comparison/` | The existing tool's HTML report and reproducible scoring bundle |
| `audit.json`, `summary.json`, `receipt.json` | Independent checks, aggregate results, and artifact hashes |
| `failure.json`, when present | Failed phase and full fixed selection; never interpret it as a successful comparison |

Raw recordings are not uploaded with the run artifacts or committed to Git. The derived artifacts include public measured movement and model outputs and carry source attribution. Keep that attribution when sharing. Their presence does not establish Neuralink workflow adoption or live BCI control performance.
