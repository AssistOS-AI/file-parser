#!/usr/bin/env python3
"""Sample /proc/meminfo and memory PSI until SIGTERM/SIGINT; write CSV and a JSON summary.
usage: memsample.py OUT_PREFIX [interval_ms]"""
import json, signal, sys, time
out = sys.argv[1]; interval = (int(sys.argv[2]) if len(sys.argv) > 2 else 100) / 1000
KEYS = ('MemTotal', 'MemFree', 'MemAvailable', 'Cached', 'Buffers', 'Shmem')
def meminfo():
    d = {}
    with open('/proc/meminfo') as f:
        for line in f:
            k, v = line.split(':', 1)
            if k in KEYS: d[k] = int(v.split()[0]) * 1024
    return d
def psi_full():
    try:
        with open('/proc/pressure/memory') as f:
            for line in f:
                if line.startswith('full'):
                    return float(line.split()[1].split('=')[1])
    except OSError:
        return None
stop = False
def handler(*_):
    global stop; stop = True
signal.signal(signal.SIGTERM, handler); signal.signal(signal.SIGINT, handler)
t0 = time.time(); first = meminfo(); rows = []
with open(out + '.csv', 'w') as csv:
    csv.write('epoch,t,' + ','.join(KEYS[1:]) + ',psi_full_avg10\n')
    while not stop:
        m = meminfo(); p = psi_full(); now = time.time(); t = now - t0
        rows.append((t, m, p))
        csv.write(f"{now:.3f},{t:.3f}," + ','.join(str(m[k]) for k in KEYS[1:]) + f",{p}\n")
        time.sleep(interval)
G = 1024 ** 3
last = rows[-1][1] if rows else first
summary = {
    't0_epoch': round(t0, 3),
    'samples': len(rows), 'seconds': round(rows[-1][0], 2) if rows else 0,
    'start_GiB': {k: round(first[k] / G, 2) for k in KEYS},
    'end_GiB': {k: round(last[k] / G, 2) for k in KEYS},
    'min_MemAvailable_GiB': round(min(r[1]['MemAvailable'] for r in rows) / G, 2),
    'min_MemFree_GiB': round(min(r[1]['MemFree'] for r in rows) / G, 2),
    'max_Cached_GiB': round(max(r[1]['Cached'] for r in rows) / G, 2),
    'min_Cached_GiB': round(min(r[1]['Cached'] for r in rows) / G, 2),
    'max_drop_MemAvailable_GiB': round((first['MemAvailable'] - min(r[1]['MemAvailable'] for r in rows)) / G, 2),
    'max_psi_full_avg10': max((r[2] or 0) for r in rows),
}
json.dump(summary, open(out + '.json', 'w'), indent=1); print(json.dumps(summary))
