"""Run the frozen human MINDFUL T11 example, outside the comparison library.

One fit per model. Save every evaluation prediction before opening evaluation
labels in this execution. Structural/target inspection preceded plan freezing.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

import numpy as np
import scipy

from bci_regression import EvaluationSet, PredictionSet, reproduce
from bci_regression.pinned import PinnedComparison
from examples.public_recording.model import fit_source_ridge
from examples.human_recording.data import (
    block_id, digest, read_neural, read_targets, sample_id, session_id,
    trial_features, verify_block,
)

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / 'docs/human-demo/protocol-v1.json'
PROTOCOL_SHA256 = '9f51616b54b1af3dc884f4ccd51baa79ccb0f2789800aff676dafd93d68267b6'


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def _environment():
    return dict(python=platform.python_version(), platform=platform.platform(), numpy=np.__version__,
                scipy=scipy.__version__,
                numpy_blas=np.__config__.CONFIG.get('Build Dependencies', {}).get('blas', {}).get('name', 'unknown'),
                numpy_blas_version=np.__config__.CONFIG.get('Build Dependencies', {}).get('blas', {}).get('version', 'unknown'),
                source_revision=subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                producer_sources={str(p.relative_to(REPO)): digest(p) for p in [
                    Path(__file__), Path(__file__).with_name('data.py'),
                    REPO / 'examples/public_recording/model.py']},
                threads={key: os.environ.get(key) for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')})


def _check_environment(environment):
    if tuple(environment['python'].split('.')[:2]) != ('3', '12') or environment['numpy'] != '2.2.6' or environment['scipy'] != '1.15.3':
        raise ValueError('Use Python 3.12, NumPy 2.2.6 and SciPy 1.15.3 binary wheels')
    if any(value != '1' for value in environment['threads'].values()):
        raise ValueError('Set OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS to 1 before launch')


def _validate_plan(plan):
    blocks = plan['blocks']
    keys = [(b['day'], b['block']) for b in blocks]
    if not blocks or keys != sorted(set(keys)):
        raise ValueError('Frozen blocks must be unique and in chronological order')
    roles = [b['role'] for b in blocks]
    if not all(r in ('train', 'evaluation') for r in roles) or 'train' not in roles or 'evaluation' not in roles:
        raise ValueError('Both chronological training and evaluation partitions are required')
    if max(b['day'] for b in blocks if b['role'] == 'train') >= min(b['day'] for b in blocks if b['role'] == 'evaluation'):
        raise ValueError('Evaluation days must follow every training day')
    if plan['data']['target_kind'] != 'inferred_cursor_to_target_vector' or plan['data']['bin_seconds'] != .02:
        raise ValueError('Unexpected target semantics or bin width')
    if plan['models']['baseline']['history_bins'] != 1 or plan['models']['candidate']['history_bins'] != 4:
        raise ValueError('Expected current-bin versus four-bin history')
    if plan['models']['ridge_lambda'] != 1.0 or plan['comparison']['reporting_tolerance'] is not None:
        raise ValueError('Unexpected ridge setting or categorical reporting threshold')


def run(input_dir: Path, output_dir: Path, protocol_path: Path = PROTOCOL):
    input_dir, output_dir, protocol_path = Path(input_dir), Path(output_dir), Path(protocol_path)
    if digest(protocol_path) != PROTOCOL_SHA256:
        raise ValueError('Frozen protocol bytes differ; do not silently change the experiment')
    plan = json.loads(protocol_path.read_text())
    _validate_plan(plan)
    output_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(protocol_path, output_dir / 'protocol.json')
    phase = 'admission'
    selected = [session_id(b) for b in plan['blocks']]
    try:
        environment = _environment()
        write_json(output_dir / 'environment.json', environment)
        _check_environment(environment)
        specs = plan['blocks']
        paths = { (b['day'], b['block']): input_dir / f"day_{b['day']}" / b['block'] for b in specs }
        for b in specs:
            verify_block(paths[b['day'], b['block']], b)
        write_json(output_dir / 'inputs.json', specs)
        neural = {}
        admissions = []
        for b in specs:
            key = b['day'], b['block']
            n = read_neural(paths[key], b, plan['data'])
            neural[key] = n
            admissions.append(dict(day=b['day'], block=b['block'], role=b['role'],
                n_bins=b['n_bins'], n_eligible=len(n.indices), trials=n.trials,
                excluded_trials=n.excluded_trials, exclusions=dict(Counter(r for r in n.reasons if r))))
        write_json(output_dir / 'admission.json', admissions)
        if 'expected_counts' in plan:
            for role in ('train', 'evaluation'):
                actual = Counter()
                for a in admissions:
                    if a['role'] == role:
                        actual.update(a['exclusions'])
                        actual['eligible'] += a['n_eligible']
                if dict(actual) != plan['expected_counts'][role]:
                    raise ValueError('Partition counts differ from the frozen inspection')
        train = [b for b in specs if b['role'] == 'train']
        evaluation_specs = [b for b in specs if b['role'] == 'evaluation']
        phase = 'source_fit'
        Y = np.concatenate([read_targets(paths[b['day'], b['block']], b)[neural[b['day'], b['block']].indices] for b in train])
        models = {}
        model_receipts = {}
        (output_dir / 'models').mkdir()
        for role in ('baseline', 'candidate'):
            cfg = plan['models'][role]
            X = np.concatenate([trial_features(neural[b['day'], b['block']], cfg['history_bins']) for b in train])
            model = fit_source_ridge(X, Y, alpha=plan['models']['ridge_lambda'])
            del X
            models[role] = model
            path = output_dir / 'models' / f'{role}.json'
            write_json(path, dict(model_id=cfg['id'], history_bins=cfg['history_bins'],
                protocol_sha256=PROTOCOL_SHA256, model=model.to_dict()))
            model_receipts[role] = dict(sha256=digest(path), n_training_rows=len(Y), model_id=cfg['id'])
        del Y
        print('Both fixed training models saved; evaluation labels are not opened by inference.', flush=True)
        phase = 'neural_only_prediction'
        receipts = {}
        for role in models:
            (output_dir / 'predictions' / role).mkdir(parents=True)
        for b in evaluation_specs:
            key = b['day'], b['block']
            n = neural[key]
            for role, model in models.items():
                values = model.predict(trial_features(n, plan['models'][role]['history_bins']))
                relative = f'predictions/{role}/{session_id(b)}-{block_id(b)}.npz'
                path = output_dir / relative
                np.savez_compressed(path, sample_indices=n.indices, predicted_vector=values)
                receipts[relative] = digest(path)
        write_json(output_dir / 'predictions-ready.json', dict(
            phase='all_evaluation_predictions_saved_before_evaluation_labels_opened_in_this_run',
            protocol_sha256=PROTOCOL_SHA256, models=model_receipts, predictions=receipts,
            prior_inspection='Structural and target-semantic inspection occurred before protocol freeze; no fitted decoder outcomes were inspected.'))
        print('All evaluation predictions saved; now loading the fixed inferred targets for scoring.', flush=True)
        phase = 'score_saved_predictions'
        rows, predictions = [], {role: [] for role in models}
        offsets = defaultdict(int)
        manual_squared_errors = {role: defaultdict(list) for role in models}
        for b in evaluation_specs:
            key = b['day'], b['block']
            n = neural[key]
            target = read_targets(paths[key], b)
            sid = session_id(b)
            for i in range(b['n_bins']):
                reason = n.reasons[i]
                rows.append(dict(session_id=sid, sample_id=sample_id(b, i),
                    timestamp=(offsets[sid] + i + 1) * plan['data']['bin_seconds'],
                    target_vx=float(target[i, 0]), target_vy=float(target[i, 1]),
                    eligible=not bool(reason), exclusion_reason=reason))
            offsets[sid] += b['n_bins']
            for role in models:
                relative = f'predictions/{role}/{sid}-{block_id(b)}.npz'
                path = output_dir / relative
                if digest(path) != receipts[relative]:
                    raise ValueError('Saved prediction bytes changed before scoring')
                with np.load(path, allow_pickle=False) as saved:
                    indices, values = saved['sample_indices'], saved['predicted_vector']
                    if not np.array_equal(indices, n.indices) or values.shape != (len(n.indices), 2):
                        raise ValueError('Saved predictions do not cover the fixed scoring mask')
                    manual_squared_errors[role][sid].append(np.sum((values - target[indices]) ** 2, axis=1))
                    for i, value in zip(indices, values):
                        predictions[role].append(dict(session_id=sid, sample_id=sample_id(b, int(i)),
                            predicted_vx=float(value[0]), predicted_vy=float(value[1])))
        evaluation = EvaluationSet.from_records(rows, evaluation_id=plan['protocol_id'],
            units=plan['data']['units'], target_kind=plan['data']['target_kind'],
            coordinates='MINDFUL stored cursor-to-target x,y displacement; source coordinate scale retained',
            horizon_ms=0, purpose='frozen offline engineering demonstration against inferred targets',
            source_ref=f"{plan['dataset']['doi']}; protocol sha256:{PROTOCOL_SHA256}")
        provenance = dict(protocol_sha256=PROTOCOL_SHA256, source_revision=environment['source_revision'],
            producer_sources=environment['producer_sources'], input_files=specs,
            target_semantics='Stored inferred cursor-to-target displacement; not measured intended velocity.',
            timestamps='Concatenated recording seconds within each day; original pauses between blocks unknown and omitted; sample IDs retain block and 1-based original bin.',
            inference_boundary='All evaluation predictions saved before evaluation label loading in this execution; no test normalization, adaptation, or tuning.')
        baseline = PredictionSet.from_records(predictions['baseline'], run_id=plan['models']['baseline']['id'],
            evaluation=evaluation, provenance={**provenance, 'model_sha256': model_receipts['baseline']['sha256']})
        description = ('Public human MINDFUL T11 cursor recordings. Fixed current-bin ridge versus four-bin neural history. '
            'Offline error against inferred cursor-to-target vectors in dataset coordinate units, not measured intended velocity or live control. '
            'Training days 658, 665, 672; all 12 later days retained. Descriptive comparison; no categorical regression threshold. '
            'Times concatenate recorded blocks within each day, omitting unknown pauses. Original block/bin references remain in sample IDs.')
        PinnedComparison.create(output_dir / 'reference', evaluation=evaluation, baseline=baseline,
            tolerance=plan['comparison']['reporting_tolerance'], numerical_tolerance=plan['comparison']['numerical_tolerance'],
            description=description)
        pin = PinnedComparison.load(output_dir / 'reference')
        result = pin.compare(predictions['candidate'], evaluation=evaluation, run_id=plan['models']['candidate']['id'],
            output_dir=output_dir / 'comparison', provenance={**provenance, 'model_sha256': model_receipts['candidate']['sha256']})
        expected_sessions = sorted(set(session_id(b) for b in evaluation_specs))
        if not result['complete'] or sorted(r['session_id'] for r in result['sessions']) != expected_sessions:
            raise ValueError('Frozen comparison is incomplete; preserve every selected session')
        phase = 'arithmetic_audit_and_reproduction'
        tolerance = plan['comparison']['numerical_tolerance']
        for row in result['sessions']:
            for role in models:
                terms = np.concatenate(manual_squared_errors[role][row['session_id']])
                independent = float(np.sqrt(np.mean(terms)))
                if len(terms) != row['n_expected'] or abs(independent - row[f'{role}_rmse']) > tolerance:
                    raise ValueError('Direct NumPy arithmetic disagrees with saved comparison')
        if reproduce(output_dir / 'comparison') != result:
            raise ValueError('Saved score reproduction differed')
        per_day = []
        for sid in expected_sessions:
            day_blocks = [a for a in admissions if f"T11-day-{a['day']:04d}" == sid]
            counts = Counter()
            for a in day_blocks:
                counts.update(a['exclusions'])
            per_day.append(dict(session_id=sid, blocks=len(day_blocks), total_bins=sum(a['n_bins'] for a in day_blocks),
                eligible_bins=sum(a['n_eligible'] for a in day_blocks), exclusions=dict(counts)))
        summary = dict(status='complete', protocol_sha256=PROTOCOL_SHA256, source_revision=environment['source_revision'],
            producer_sources=environment['producer_sources'], comparator_source_digest=result['comparator_source_digest'],
            evaluation_fingerprint=evaluation.fingerprint, pin_fingerprint=pin.fingerprint,
            training_rows=sum(a['n_eligible'] for a in admissions if a['role'] == 'train'),
            models=model_receipts, sessions=result['sessions'], per_day=per_day,
            excluded_counts=result['excluded_counts'], pooled=result['pooled'],
            scoring_reproduction='passed', independent_arithmetic='passed', limitations=plan.get('limitations', []))
        write_json(output_dir / 'summary.json', summary)
        files = {str(p.relative_to(output_dir)): digest(p) for p in output_dir.rglob('*') if p.is_file()}
        write_json(output_dir / 'receipt.json', dict(status='complete', protocol_sha256=PROTOCOL_SHA256,
            source_revision=environment['source_revision'], files=files))
        print(json.dumps({'status':'complete','sessions':result['sessions'],'pooled':result['pooled']}, indent=2), flush=True)
        return summary
    except BaseException as exc:
        write_json(output_dir / 'failure.json', dict(status='failed', phase=phase, protocol_sha256=PROTOCOL_SHA256,
            selected_sessions=sorted(set(selected)), error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=PROTOCOL)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir, args.protocol)
