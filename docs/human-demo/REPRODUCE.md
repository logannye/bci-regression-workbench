# Reproduce the MINDFUL T11 demonstration

The frozen plan is commit `6e983e142a47d828c8f1ec2fb4c800e3406ffee7`; [protocol-v1.json](protocol-v1.json) SHA-256 is `9f51616b54b1af3dc884f4ccd51baa79ccb0f2789800aff676dafd93d68267b6`. Preserve it unchanged. Execution and publication revisions are recorded in the result receipt.

## Obtain the original public files

Open the [Dryad dataset](https://doi.org/10.5061/dryad.n2z34tn5s) in a browser and download **MINDFUL_Data.zip**. The browser route worked without a sign-in; direct automated stream requests returned 403 and API downloads required authentication. This is a documented manual acquisition step, not a promise that unattended CI can download it.

Require exactly 411,951,588 bytes and SHA-256 `6d12b5dbcf9cac654ff1d0679e9753bf042b56cd5b8852eb31236b3cdecf7332`. Extract the `MINDFUL_Data/T11/` MATLAB files outside Git. The producer verifies every selected file against the committed protocol. Other participants and additional tasks are not used. Keep the source README and cite Pun et al. (2024), Dryad DOI `10.5061/dryad.n2z34tn5s`, CC0-1.0.

## Regenerate predictions under the frozen plan

This is a deliberate rerun, not required to explore the static demo. Use Python 3.12 and the binary-only requirements. No compilation is necessary. From the repository root, after installing `requirements-human-demo.txt` into your chosen environment:

```sh
export PYTHONPATH=src:.
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
python examples/human_recording/run.py \
  --input-dir /path/to/MINDFUL_Data/T11 \
  --output-dir runs/mindful-t11-rerun
```

Choose a new output directory; the producer refuses to overwrite evidence. It checks hashes and masks, fits one baseline and one candidate, saves every evaluation prediction before loading evaluation labels in that execution, then creates a pinned baseline and compares the candidate. Structural inspection read labels before the plan was frozen; that limitation remains documented.

On the tested macOS arm64 runtime, NumPy 2.2.6's macOS 14 Accelerate wheel raised spurious floating-point exceptions on finite synthetic matrix multiplication. The same version's macOS 11 OpenBLAS wheel passed preflight. To select that binary wheel explicitly for CPython 3.12:

```sh
python -m pip download --only-binary=:all: --no-deps \
  --platform macosx_11_0_arm64 --python-version 312 --implementation cp --abi cp312 \
  --dest wheels numpy==2.2.6
python -m pip install --no-deps --force-reinstall \
  wheels/numpy-2.2.6-cp312-cp312-macosx_11_0_arm64.whl
```

The model's finite-arithmetic guards were not relaxed. Record your actual platform and BLAS backend. A new execution does not inherit the original run's acceptance automatically.

## Audit without refitting

The independent auditor reconstructs trial masks, training-only normalization, ridge optimality, predictions and scores from original files and saved evidence. It does not call the producer, model implementation or comparator:

```python
from examples.human_recording.audit import audit_run
receipt = audit_run("runs/mindful-t11-rerun", "/path/to/MINDFUL_Data/T11")
assert receipt["status"] == "passed"
```

To reproduce only the saved score comparison, no scientific dependencies or model execution are needed:

```python
from bci_regression import reproduce
result = reproduce("runs/mindful-t11-rerun/comparison")
assert result["complete"]
```

Score reproduction requires the comparator source recorded in that bundle, including the renderer. Old Indy bundles retain their old source identity. The site contains only bounded report previews and aggregate scores, not the full inputs needed for either audit; those remain in the local run artifacts.
