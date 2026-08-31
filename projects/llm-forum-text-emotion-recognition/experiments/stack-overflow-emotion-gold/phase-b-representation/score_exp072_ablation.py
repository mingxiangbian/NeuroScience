#!/usr/bin/env python3
"""Score the complete sealed EXP-072 prediction family; never load a model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import stat
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
LABELS = ('love', 'joy', 'surprise', 'anger', 'sadness', 'fear')
CONDITIONS = tuple((seed, condition) for seed in (42, 43, 44)
                   for condition in (('A0', 'A1', 'A2', 'A3', 'A4', 'A5') if seed == 42
                                     else ('A0', 'A1', 'A2', 'A3')))


def load_runner(config_path):
    config = json.loads(config_path.read_bytes())
    record = config['implementation']['runner']
    path = ROOT.parents[2] / record['path']
    info = path.lstat()
    if (path != ROOT / 'run_exp072_ablation.py' or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1 or info.st_size != record['bytes']
            or f'{stat.S_IMODE(info.st_mode):04o}' != record['mode']
            or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']):
        raise ValueError('Runner identity drift')
    spec = importlib.util.spec_from_file_location('exp072_scoring_io', path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def sigmoid(logits):
    value = np.asarray(logits, dtype=np.float64)
    if not np.isfinite(value).all():
        raise ValueError('Nonfinite logits')
    output = np.empty_like(value)
    positive = value >= 0
    output[positive] = 1 / (1 + np.exp(-value[positive]))
    exp_value = np.exp(value[~positive])
    output[~positive] = exp_value / (1 + exp_value)
    return output


def classification(gold, prediction):
    gold, prediction = np.asarray(gold), np.asarray(prediction)
    if (gold.shape != prediction.shape or gold.ndim != 2 or gold.shape[1] != 6
            or gold.shape[0] == 0 or not np.isin(gold, [0, 1]).all()
            or not np.isin(prediction, [0, 1]).all()):
        raise ValueError('Invalid binary scoring arrays')
    tp = np.sum((gold == 1) & (prediction == 1), axis=0)
    fp = np.sum((gold == 0) & (prediction == 1), axis=0)
    fn = np.sum((gold == 1) & (prediction == 0), axis=0)
    support = np.sum(gold, axis=0)
    divide = lambda a, b: np.divide(a, b, out=np.zeros(6, dtype=np.float64), where=b != 0)
    precision, recall = divide(tp, tp + fp), divide(tp, tp + fn)
    f1 = divide(2 * tp, 2 * tp + fp + fn)
    micro_denominator = 2 * int(tp.sum()) + int(fp.sum()) + int(fn.sum())
    return {
        'rows': len(gold), 'six_label_macro_f1': float(f1.mean()),
        'five_label_macro_f1': float(f1[[0, 1, 3, 4, 5]].mean()),
        'micro_f1': 2 * int(tp.sum()) / micro_denominator if micro_denominator else 0.0,
        'weighted_f1': float(np.dot(f1, support) / support.sum()) if support.sum() else 0.0,
        'hamming_loss': float(np.mean(gold != prediction)),
        'subset_accuracy': float(np.mean(np.all(gold == prediction, axis=1))),
        'per_label': {label: {'precision': float(precision[i]), 'recall': float(recall[i]),
                              'f1': float(f1[i]), 'support': int(support[i])}
                      for i, label in enumerate(LABELS)},
    }


def score_arrays(gold, logits, thresholds):
    results, predictions = {}, {}
    for seed, condition in CONDITIONS:
        key, baseline = f's{seed}:{condition}', f's{seed}:A0'
        threshold = thresholds[seed]
        if threshold.shape != (3360,) or not np.isfinite(threshold).all() or np.any((threshold < 0) | (threshold > 1)):
            raise ValueError('Frozen threshold contract drift')
        prediction = (sigmoid(logits[key]) >= threshold[:, None]).astype(np.uint8)
        predictions[key] = prediction
        metrics = classification(gold, prediction)
        full = metrics if condition == 'A0' else results[baseline]['metrics']
        full_prediction = prediction if condition == 'A0' else predictions[baseline]
        delta = {name: float(metrics[name] - full[name]) for name in (
            'six_label_macro_f1', 'five_label_macro_f1', 'micro_f1', 'weighted_f1',
            'hamming_loss', 'subset_accuracy')}
        delta['per_label_f1'] = {label: metrics['per_label'][label]['f1'] - full['per_label'][label]['f1'] for label in LABELS}
        results[key] = {
            'seed': seed, 'condition': condition, 'metrics': metrics, 'delta_from_full': delta,
            'prediction_vector_flip_rate': float(np.mean(np.any(prediction != full_prediction, axis=1))),
            'mean_absolute_logit_change': float(np.mean(np.abs(logits[key].astype(np.float64) - logits[baseline].astype(np.float64)))),
        }
    return {'condition_order': list(results), 'conditions': results}, predictions


def require_seal(runner, config_path, config):
    public, private = runner.roots(config)
    for root, mode, names in (
            (public, 0o755, {'run-claim.json', 'run.json', 'stdout.log', 'prediction-seal.json', 'workers'}),
            (private, 0o700, {'input-manifest.json', 'prediction-manifest.json', 'workers'})):
        if (root.is_symlink() or not root.is_dir() or stat.S_IMODE(root.stat().st_mode) != mode
                or {path.name for path in root.iterdir()} != names):
            raise ValueError('Failed or nonexact completed inference prefix')
        for path in root.iterdir():
            if path.is_symlink():
                raise ValueError('Unsafe scoring prefix')
    for name in ('score.json', 'score-failure.json', 'verification.json'):
        if os.path.lexists(public / name):
            raise FileExistsError('Score attempt already exists')
    if os.path.lexists(private / 'scored-predictions.npz'):
        raise FileExistsError('Scored predictions already exist')
    config_record = runner.artifact(config_path)
    seal_path = public / 'prediction-seal.json'
    seal = runner.strict_json(seal_path)
    if (seal.get('status') != 'Sealed' or seal.get('experiment_id') != 'EXP-072'
            or seal.get('config') != config_record or seal.get('worker_count') != 70
            or seal.get('a0_worker_count') != 15 or seal.get('total_forward_rows') != 47040
            or seal.get('all_a0_passed') is not True or seal.get('all_predictions_sealed') is not True
            or seal.get('labels_accessed') is not False or seal.get('metrics_computed') is not False):
        raise ValueError('All predictions must be sealed before labels')
    manifest_path = runner.require_record(seal['prediction_manifest'])
    if manifest_path != private / 'prediction-manifest.json':
        raise ValueError('Prediction manifest path drift')
    manifest = runner.strict_json(manifest_path)
    expected = runner.expected_workers()
    order = [item['worker_id'] for item in expected]
    if (manifest.get('status') != 'Sealed' or manifest.get('config') != config_record
            or manifest.get('worker_order') != order or set(manifest['workers']) != set(order)
            or runner.digest(manifest['workers']) != seal['worker_inventory_sha256']):
        raise ValueError('Sealed worker inventory drift')
    run = runner.strict_json(public / 'run.json')
    if run.get('status') != 'CompletedAwaitingScore':
        raise ValueError('Inference is not complete')
    for spec in expected:
        records = manifest['workers'][spec['worker_id']]
        if runner.validate_worker(config, config_path, spec) != records:
            raise ValueError('Worker record differs from validated inference artifact')
        for record in records.values():
            runner.require_record(record)
        worker = runner.strict_json(runner.require_record(records['manifest']))
        if (worker.get('status') != 'Completed' or worker.get('config') != config_record
                or any(worker.get(key) != spec[key] for key in ('worker_id', 'seed', 'fold', 'condition'))
                or worker.get('rows') != 672 or worker.get('output') != records['logits']
                or worker.get('source_before') != worker.get('source_after')
                or worker.get('tensor_before') != worker.get('tensor_after')):
            raise ValueError('Worker seal integrity failure')
        if spec['condition'] == 'A0':
            replay = worker['replay']
            if (replay['required'] is not True or replay['checked_rows'] != 672
                    or replay['atol'] != 1e-5 or replay['rtol'] != 0.0
                    or not 0 <= replay['max_abs_error'] <= 1e-5):
                raise ValueError('Full replay gate failed')
    return seal_path, manifest


def load_scoring_sources(runner, metadata, config, manifest):
    original = metadata['original_config']
    selector = runner._import_record(config['source']['helpers']['selective_json'], 'exp072_score_selective')
    public_rows = []
    with runner.require_record(original['data']['fold_manifest_public']).open('rb') as handle:
        for line in handle:
            row, _ = selector.select_json_scalars(line, [('sample_id',), ('fold_id',)])
            public_rows.append({'sample_id': row[('sample_id',)], 'fold_id': row[('fold_id',)]})
    if len(public_rows) != 3360 or len({row['sample_id'] for row in public_rows}) != 3360:
        raise ValueError('Public fold coverage drift')
    fold_ids = np.asarray([row['fold_id'] for row in public_rows], dtype=np.int8)
    row_contract = runner.read_npz_members(runner.require_record(config['source']['exp070_row_contract']), ['ordinal', 'fold_id'])
    if (not np.array_equal(row_contract['ordinal'], np.arange(3360))
            or not np.array_equal(row_contract['fold_id'], fold_ids)):
        raise ValueError('Ordinal-fold identity drift')
    logits = {f's{seed}:{condition}': np.empty((3360, 6), dtype=np.float32) for seed, condition in CONDITIONS}
    for spec in runner.expected_workers():
        record = manifest['workers'][spec['worker_id']]['logits']
        arrays = runner.read_npz_members(runner.require_record(record), ['ordinal', 'fold_id', 'logits'])
        ordinals = np.flatnonzero(fold_ids == spec['fold']).astype(np.int32)
        if (arrays['ordinal'].dtype != np.int32 or arrays['fold_id'].dtype != np.int8
                or arrays['logits'].dtype != np.float32 or arrays['logits'].shape != (672, 6)
                or not np.array_equal(arrays['ordinal'], ordinals)
                or not np.array_equal(arrays['fold_id'], fold_ids[ordinals])
                or not np.isfinite(arrays['logits']).all()):
            raise ValueError('Worker prediction alignment drift')
        logits[f"s{spec['seed']}:{spec['condition']}"][ordinals] = arrays['logits']
    thresholds = {}
    for item in config['source']['thresholds']:
        if item['allowed_members'] != ['fold_ids', 'm3_raw_thresholds']:
            raise ValueError('Threshold member access drift')
        arrays = runner.read_npz_members(runner.require_record(item['artifact']), item['allowed_members'])
        if arrays['fold_ids'].dtype != np.int8 or arrays['m3_raw_thresholds'].dtype != np.float64 or not np.array_equal(arrays['fold_ids'], fold_ids):
            raise ValueError('Threshold row alignment drift')
        thresholds[item['seed']] = arrays['m3_raw_thresholds']
    # This frozen fold manifest has labels and identities but no text.
    gold = []
    with runner.require_record(original['data']['fold_manifest_private']).open('rb') as handle:
        for ordinal, line in enumerate(handle):
            row, spans = selector.select_json_scalars(
                line, [('sample_id',), ('fold_id',)], capture_paths=[('labels',)])
            labels = json.loads(spans[('labels',)])
            if (ordinal >= 3360 or row[('sample_id',)] != public_rows[ordinal]['sample_id']
                    or row[('fold_id',)] != int(fold_ids[ordinal]) or not isinstance(labels, list)
                    or len(labels) != 6
                    or any(type(value) not in (bool, int) or value not in (0, 1) for value in labels)):
                raise ValueError('Frozen label source alignment drift')
            gold.append(labels)
    if len(gold) != 3360 or set(thresholds) != {42, 43, 44}:
        raise ValueError('Scoring source coverage drift')
    return np.asarray(gold, dtype=np.uint8), fold_ids, logits, thresholds


def write_once(path, payload, mode=0o644):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'wb') as handle:
        os.fchmod(handle.fileno(), mode)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def score(config_path):
    runner = load_runner(config_path)
    config = runner.load_config(config_path)
    with runner.file_lock(runner.HEAVY_LOCK), runner.file_lock(
            runner.PREFIX + '/private/locks/exp-072-score.lock'):
        return _score_locked(config_path, runner, config)


def _score_locked(config_path, runner, config):
    started = time.monotonic()
    public, private = runner.roots(config)
    metadata = runner.metadata_gate(config_path, config)
    seal_path, manifest = require_seal(runner, config_path, config)
    input_manifest = runner.strict_json(runner.require_record(manifest['input_manifest']))
    if (input_manifest['source_snapshot'] != metadata['source_snapshot']
            or input_manifest['source_snapshot_sha256'] != metadata['source_snapshot_sha256']
            or manifest['source_snapshot_sha256'] != metadata['source_snapshot_sha256']):
        raise ValueError('Scoring source does not match sealed inference source')
    seal_record = runner.artifact(seal_path)
    try:
        gold, fold_ids, logits, thresholds = load_scoring_sources(runner, metadata, config, manifest)
        results, predictions = score_arrays(gold, logits, thresholds)
        after = runner.metadata_gate(config_path, config)
        runner.require_record(metadata['original_config']['data']['fold_manifest_private'])
        if after['source_snapshot_sha256'] != metadata['source_snapshot_sha256'] or runner.artifact(seal_path) != seal_record:
            raise ValueError('Scoring source mutation')
        arrays = {'ordinal': np.arange(3360, dtype=np.int32), 'fold_id': fold_ids, 'gold': gold}
        arrays.update({f'{key.replace(":", "_")}_prediction': value for key, value in predictions.items()})
        prediction_path = private / 'scored-predictions.npz'
        bundle = io.BytesIO()
        np.savez(bundle, **arrays)
        runner.create_bytes_once(prediction_path, bundle.getvalue(), private=True)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = peak if sys.platform == 'darwin' else peak * 1024
        elapsed = time.monotonic() - started
        if elapsed > 3600 or peak_bytes > 17179869184:
            raise RuntimeError('Scoring resource budget exceeded')
        report = {'schema_version': 'exp-072-score-v1', 'experiment_id': 'EXP-072', 'tier': 'Major',
                  'status': 'ScoredAwaitingVerification', 'config': runner.artifact(config_path),
                  'prediction_seal': seal_record, 'source_snapshot_sha256': metadata['source_snapshot_sha256'],
                  'results': results, 'results_sha256': runner.digest(results),
                  'scored_predictions': runner.artifact(prediction_path),
                  'created_at_utc': datetime.now(timezone.utc).isoformat(),
                  'resources': {'wall_seconds': elapsed, 'peak_rss_bytes': peak_bytes, 'api_cost_usd': 0},
                  'access': {'labels_after_prediction_seal': True, 'train_labels_read': True,
                             'threshold_members_read': ['fold_ids', 'm3_raw_thresholds'],
                             'model_loaded': False, 'forward_executed': False, 'text_read': False,
                             'validation_accessed': False, 'test_accessed': False}}
        runner.create_bytes_once(public / 'score.json', runner.canonical_json_bytes(report), private=False)
        return report
    except BaseException as error:
        path = public / 'score-failure.json'
        if not os.path.lexists(path):
            write_once(path, runner.canonical_json_bytes({'experiment_id': 'EXP-072', 'status': 'Failed',
                       'stage': 'score', 'error_type': type(error).__name__, 'automatic_retry': False}))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    try:
        report = score(args.config.resolve())
        print(json.dumps({'experiment_id': 'EXP-072', 'status': report['status']}))
    except BaseException as error:
        print(json.dumps({'experiment_id': 'EXP-072', 'status': 'Failed', 'error_type': type(error).__name__}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
