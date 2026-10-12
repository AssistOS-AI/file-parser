#!/usr/bin/env python3
"""Classify follow-up runs as memory evidence: rule version 3 (plans/phase0-followup-data-quality_codex.md,
rev 2 sections 3-5 and section 5a). Applied prospectively; the rule-1 and rule-2 outputs are kept as
memory-validity.rule1.json and memory-validity.rule2.json.

Rule 3 changes (the whole-window attribution identity failed, 0.76 GiB against 0.3, so attribution is not
validated): no run is CONTAMINATED and no peak is reduced or excluded; measured external movement can still
deny CLEAN. A peak is marked a LOWER BOUND when external memory was released during the run: memory ends
above the pre-run baseline (end offset below -0.5 GiB) or a later phase peak falls more than 0.5 GiB below
the at-ready drop. Lower bounds stay in the worst case and are never used to argue a smaller need.
Run records are every <stem>-r<rep>[-a<attempt>].json; *.INTERRUPTED.json markers are listed, not classified.

Reads the raw run records (<run>.json, <run>-mem.csv, <run>-attr.jsonl), engineering-activity.json and the
preserved Phase 0 runs; writes results/followup/memory-validity.json. Raw records and annotations.json
(request validity) are never changed.

Per run:
  quiet windows  pre: the harness's flat baseline (a wait over 60 s is noted "host busy before run", not a
                 rejection); post: MemAvailable flat for 10 s, reached within 60 s of exit. The net change
                 (post - pre) must be within 0.5 GiB, or be matched by measured external memory.
  release        back within 0.5 GiB by exit + 10 s, no excursion above 0.75 GiB in [exit, exit + 10 s].
  lock           harness v4+ held the memory lock; before v4, no recorded engineering activity overlaps.
  external       harness v5+: external memory ((AnonPages + Shmem) - runner) within 0.5 GiB during the run.
                 Before v5 it is not measured and not required.
Classes:
  CLEAN          every check passes. Counts as a sample.
  CONTAMINATED   a check fails and there is positive evidence: measured external growth over 0.5 GiB, or a
                 recorded activity whose estimated size covers the failure. Only what the evidence explains
                 leaves the worst case (phase peaks less the measured external growth at that moment).
  INCONCLUSIVE   any other failure. Not a sample, but its peaks stay in the worst case.
The residual (unattributed memory) is diagnostic only until the validation checks pass; it decides nothing.
Per configuration: enough evidence = two CLEAN runs whose at-ready drop and every phase peak agree within
0.75 GiB. Worst case = the maximum over CLEAN and INCONCLUSIVE peaks, CONTAMINATED peaks less what is
explained, and the preserved Phase 0 observations of the same configuration.

usage: memory_validity.py [--dir results/followup]
"""
import argparse, datetime, glob, hashlib, json, os, re, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import attribution  # noqa: E402

G = 1024 ** 3
RULE_VERSION = 3
ATTRIBUTION_VALIDATED = False
AGREE_GIB = 0.75
RUN_NAME = re.compile(r'-r\d+(-a\d+)?$')
DEFAULT_CACHE_RAM = 8192
# Phase 0 observations (results/serve) kept in the worst case of the matching configuration (old harness,
# no validity checks: INCONCLUSIVE). Configuration: (model, ctx, np, cache_ram, extra).
PHASE0 = [
    ('120b-c128k-np4-dio', ('gpt-oss-120b-MXFP4.gguf', 131072, 4, 8192, '')),
    ('20b-c128k-np4-cram-default', ('gpt-oss-20b-MXFP4.gguf', 131072, 4, 8192, '')),
    ('20b-c128k-np4-cram-8192-v2', ('gpt-oss-20b-MXFP4.gguf', 131072, 4, 8192, '')),
    ('qwen-c128k-np4-mtpoff', ('Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf', 131072, 4, 8192, '')),
    ('qwen-c128k-np4-mtpon', ('Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf', 131072, 4, 8192, '--spec-type draft-mtp --spec-draft-n-max 3')),
    ('qwen-c256k-np1-mtpoff', ('Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf', 262144, 1, 8192, '')),
    ('qwen-c256k-np1-mtpon', ('Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf', 262144, 1, 8192, '--spec-type draft-mtp --spec-draft-n-max 3')),
]


def load_mem(prefix):
    rows = []
    with open(prefix + '-mem.csv') as f:
        next(f)
        for line in f:
            parts = line.strip().split(',')
            rows.append((float(parts[0]), int(parts[3])))
    return rows


def load_attr(prefix):
    path = prefix + '-attr.jsonl'
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def activities(directory):
    path = os.path.join(directory, 'engineering-activity.json')
    if not os.path.exists(path):
        return []
    data = json.load(open(path))
    out = []
    for entry in data['intervals']:
        start = datetime.datetime.fromisoformat(f"{data['date']}T{entry['start']}+02:00").timestamp()
        end = datetime.datetime.fromisoformat(f"{data['date']}T{entry['end']}+02:00").timestamp()
        out.append((start, end, entry['what'], entry.get('est_GiB', 0.0)))
    return out


def config_of(res):
    return (res.get('model'), res.get('ctx'), res.get('np'), res.get('cache_ram') if res.get('cache_ram') is not None else DEFAULT_CACHE_RAM,
            (res.get('extra') or '').strip())


def classify(name, raw, res, prefix, acts):
    mem = load_mem(prefix)
    attr = load_attr(prefix)
    base = res['baseline']['MemAvailable']
    v = attribution.analyse(res, mem, attr, base)
    hv = res.get('harness_version') or 1
    checks, notes, failures = {}, [], []
    waited = res['baseline'].get('waited_s') or 0
    if waited > 60:
        notes.append(f'host busy before run: the baseline took {waited:.0f} s to settle')
    checks['quiet_pre'] = not res['baseline'].get('drift')
    if not checks['quiet_pre']:
        failures.append('no flat pre-run baseline within 300 s')
    quiet = v.get('quiet_after')
    ext = v.get('external')
    net = quiet['net_post_minus_pre_GiB'] if quiet else None
    checks['quiet_post'] = quiet is not None and abs(net) <= 0.5
    if quiet is None:
        failures.append('no 10 s flat post-run window within 60 s of exit')
    elif abs(net) > 0.5:
        failures.append(f'post-run level differs from pre-run by {net:+.2f} GiB')
    rel = v.get('release_10s', {})
    checks['release'] = bool(rel.get('ok'))
    if not checks['release']:
        failures.append(f'release: {rel.get("offset_at_10s_GiB")} GiB missing at exit+10 s, max {rel.get("max_offset_GiB")} GiB')
    window = ((mem[0][0] if mem else 0) - waited - 10, (res.get('exit_epoch') or 0) + 10)
    overlapping = [(what, est) for (s, e, what, est) in acts if s <= window[1] and e >= window[0]]
    if hv >= 4:
        checks['lock'] = 'memlock_wait_s' in res
    else:
        checks['lock'] = not overlapping
        if overlapping:
            failures.append('overlapped engineering activity: ' + '; '.join(w for w, _ in overlapping))
    if ext is not None:
        checks['external'] = ext['within_0.5GiB']
        if not checks['external']:
            failures.append(f'external memory moved up to {ext["max_abs_growth_GiB"]} GiB during the run')
    else:
        checks['external'] = None
        notes.append('external memory not measured (harness < v5)')
    peaks = {p['name']: p.get('peak_drop_GiB') for p in res['phases'] if p['name'] not in ('load', 'settle')}
    explained = None
    lower_bound = []
    end_offset = (rel.get('offsets_GiB') or {}).get('+60s')
    if mem and res.get('exit_epoch'):
        tail = [v for (t, v) in mem if t >= res['exit_epoch']]
        if tail:
            end_offset = round((base - tail[-1]) / G, 2)
    if end_offset is not None and end_offset < -0.5:
        lower_bound.append(f'memory ended {-end_offset:.2f} GiB above the pre-run baseline')
    at_ready = res.get('at_ready_drop_GiB')
    for phase_name, peak in peaks.items():
        if peak is not None and at_ready is not None and peak < at_ready - 0.5:
            lower_bound.append(f'{phase_name} peak {peak} GiB is {at_ready - peak:.2f} GiB below at-ready')
    if not failures:
        cls = 'CLEAN'
    elif not ATTRIBUTION_VALIDATED:
        cls = 'INCONCLUSIVE'
    else:
        evidence = []
        if ext is not None and ext['max_abs_growth_GiB'] > 0.5:
            evidence.append(f'measured external growth up to {ext["max_abs_growth_GiB"]} GiB')
            explained = {p['name']: p['peak_drop_less_external_GiB'] for p in ext['phases'] if p['name'] in peaks}
        magnitude = max([abs(net or 0), rel.get('offset_at_10s_GiB') or 0, rel.get('max_offset_GiB') or 0])
        for what, est in overlapping:
            if est and est >= magnitude:
                evidence.append(f'recorded activity large enough ({est} GiB): {what}')
                explained = explained or {k: round(p - est, 2) for k, p in peaks.items() if p is not None}
        cls = 'CONTAMINATED' if evidence else 'INCONCLUSIVE'
        if evidence:
            notes.extend(evidence)
    if waited > 60 and cls == 'CLEAN':
        pass  # a busy host before the run is recorded, not a rejection
    return {
        'run': name, 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'rule_version': RULE_VERSION, 'harness_version': hv,
        'class': cls, 'failures': failures, 'notes': notes, 'checks': checks,
        'baseline_GiB': round(base / G, 2), 'baseline_waited_s': waited, 'quiet_after': quiet, 'release_10s': rel,
        'at_ready_drop_GiB': res.get('at_ready_drop_GiB'), 'phase_peaks_GiB': peaks,
        'peaks_less_explained_GiB': explained,
        'peaks_are_lower_bounds': bool(lower_bound), 'lower_bound_reasons': lower_bound, 'end_offset_GiB': end_offset,
        'diagnostic': {k: v.get(k) for k in ('coverage_at_ready', 'load_lag', 'residual_status')} if ext is not None else None,
        'config': config_of(res),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=os.path.join(TOOLS, '..', 'results', 'followup'))
    a = ap.parse_args()
    directory = os.path.abspath(a.dir)
    acts = activities(directory)
    runs = []
    interrupted = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(directory, '*.INTERRUPTED.json')))]
    deferred = [os.path.basename(p)[:-len('.DEFERRED.json')] for p in sorted(glob.glob(os.path.join(directory, '*.DEFERRED.json')))]
    for path in sorted(glob.glob(os.path.join(directory, '*.json'))):
        name = os.path.basename(path)[:-5]
        if not RUN_NAME.search(name) or name.startswith('stop-'):
            continue
        raw = open(path, 'rb').read()
        runs.append(classify(name, raw, json.loads(raw), path[:-5], acts))
    preserved = []
    for name, config in PHASE0:
        path = os.path.join(directory, '..', 'serve', name + '.json')
        if not os.path.exists(path):
            continue
        raw = open(path, 'rb').read()
        mem = json.loads(raw)['mem']
        preserved.append({'run': f'phase0/{name}', 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'class': 'INCONCLUSIVE',
                          'reason': 'Phase 0 harness: no validity checks or attribution; its peak stays in the worst case',
                          'peak_drop_GiB': round(mem['start_GiB']['MemAvailable'] - mem['min_MemAvailable_GiB'], 2),
                          'config': config})
    configs = {}
    for entry in runs:
        configs.setdefault(entry['config'], {'runs': [], 'preserved': []})['runs'].append(entry)
    for entry in preserved:
        if entry['config'] in configs:
            configs[entry['config']]['preserved'].append(entry)
    out_configs = []
    for config, group in configs.items():
        clean = [e for e in group['runs'] if e['class'] == 'CLEAN']
        pair = None
        for i in range(len(clean)):
            for j in range(i + 1, len(clean)):
                x, y = clean[i], clean[j]
                values = [(x['at_ready_drop_GiB'], y['at_ready_drop_GiB'])] + [(x['phase_peaks_GiB'].get(k), y['phase_peaks_GiB'].get(k)) for k in x['phase_peaks_GiB']]
                if all(p is not None and q is not None and abs(p - q) <= AGREE_GIB for p, q in values):
                    pair = pair or (x['run'], y['run'])
        worst = []
        lower = {e['run'] for e in group['runs'] if e['peaks_are_lower_bounds']}
        for e in group['runs']:
            if e['class'] in ('CLEAN', 'INCONCLUSIVE'):
                worst += [(v, e['run'], k) for k, v in e['phase_peaks_GiB'].items() if v is not None]
            else:
                worst += [(v, e['run'] + ' (less explained)', k) for k, v in (e['peaks_less_explained_GiB'] or {}).items() if v is not None]
        worst += [(e['peak_drop_GiB'], e['run'], 'peak') for e in group['preserved']]
        top = max(worst) if worst else None
        out_configs.append({
            'config': dict(zip(('model', 'ctx', 'np', 'cache_ram', 'extra'), config)),
            'runs': [(e['run'], e['class']) for e in group['runs']] + [(e['run'], e['class']) for e in group['preserved']],
            'status': 'enough' if pair else f'needs clean runs ({len(clean)} clean, no agreeing pair)' if clean else 'needs 2 clean runs',
            'agreeing_clean_pair': pair,
            'worst_case': {'drop_GiB': top[0], 'from': top[1], 'phase': top[2], 'is_lower_bound': top[1] in lower} if top else None,
            'lower_bound_runs': sorted(lower),
        })
    report = {'rule_version': RULE_VERSION, 'generated': datetime.datetime.now().isoformat(timespec='seconds'),
              'rules': 'plans/phase0-followup-data-quality_codex.md rev 2, sections 3-5; see this tool\'s docstring',
              'attribution_check': json.load(open(os.path.join(directory, 'attribution-check.json'))) if os.path.exists(os.path.join(directory, 'attribution-check.json')) else None,
              'attribution_validated': ATTRIBUTION_VALIDATED,
              'deferred_by_quiet_gate': deferred,
              'interrupted_attempts': [{'run': i['run'], 'status': i['status'], 'retry': i.get('retry')} for i in interrupted],
              'runs': runs, 'preserved_phase0': preserved, 'configs': out_configs}
    target = os.path.join(directory, 'memory-validity.json')
    with open(target + '.tmp', 'w') as f:
        json.dump(report, f, indent=1)
    os.replace(target + '.tmp', target)
    for e in runs:
        print(f"{e['run']:<38} v{e['harness_version']} {e['class']:<13}{' LOWER-BOUND' if e['peaks_are_lower_bounds'] else ''} {'; '.join(e['failures'])}")
    for c in out_configs:
        print(c['config']['model'][:14], c['config']['ctx'], c['config']['np'], c['config']['cache_ram'], c['config']['extra'][:12] or '-', '|', c['status'], '| worst', c['worst_case'])


if __name__ == '__main__':
    main()
