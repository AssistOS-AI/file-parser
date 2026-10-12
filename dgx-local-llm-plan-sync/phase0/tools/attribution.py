"""Harness v4 additions (plans/phase0-followup-data-quality_codex.md, section 5): passive only.

- memlock(): an exclusive flock on /home/research/phase0/.memlock, held for a whole run (baseline to
  the end of the post-exit window). Engineering's tests, builds, hashing and pushes take the same lock.
- AttributionSampler: every 500 ms, the runner's process group (VmRSS, RssAnon, RssShmem from
  /proc/<pid>/status), per-process GPU memory from nvidia-smi (runner vs others), and every other
  user's RssAnon total. Rows go to <out>-attr.jsonl with epoch timestamps.
- analyse(): unattributed = (baseline - MemAvailable) - runner GPU - runner (RssAnon + RssShmem), per
  phase, relative to its at-ready value; the other users' anonymous memory relative to the start;
  baseline flags; release judged at exit + 10 s.

v5 (validity rules rev 2, section 4): each sample also reads /proc/meminfo in the same iteration
(MemAvailable, AnonPages, Shmem, Unevictable), and times nvidia-smi (start, end; the GPU value is placed
at the midpoint). External memory for everyone, including this user's other processes, is
(AnonPages + Shmem) - runner (RssAnon + RssShmem), relative to the pre-run baseline snapshot.
analyse() adds the post-run quiet window, the load-step lag and the coverage check against the logged
buffers. The residual stays diagnostic until the validation checks pass.

Nothing here changes the requests or their pass/fail logic.
"""
import fcntl, json, os, pwd, subprocess, threading, time

G = 1024 ** 3
LOCK_PATH = '/home/research/phase0/.memlock'
IDLE_REFERENCE_GIB = 109.4


LOCK_LOG = '/home/research/phase0/logs/memlock.log'
# Scheduling only (2026-09-28): flock is not FIFO, so a harness pauses before asking for the lock; a waiter
# blocked in flock (tests, a reviewer's fixtures) then gets it between matrix runs. Every grant is logged.
YIELD_S = 5.0


def _lock_log(text):
    try:
        with open(LOCK_LOG, 'a') as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {text}\n")
    except OSError:
        pass


def memlock(who='harness', yield_s=YIELD_S):
    """Take the exclusive memory-measurement lock (LOCK_EX); returns (file, seconds waited). Held until the process
    exits or memunlock(). Logs whether another process held it when asked."""
    time.sleep(yield_s)
    started = time.time()
    f = open(LOCK_PATH, 'a')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        busy = False
    except BlockingIOError:
        busy = True
        _lock_log(f'{who} pid {os.getpid()} waits: the lock is held by another process')
        fcntl.flock(f, fcntl.LOCK_EX)
    waited = round(time.time() - started, 1)
    _lock_log(f'{who} pid {os.getpid()} granted after {waited} s' + (' (another holder released it)' if busy else ''))
    return f, waited


def memunlock(f, who='harness'):
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()
    _lock_log(f'{who} pid {os.getpid()} released')


MEMINFO_KEYS = ('MemAvailable', 'AnonPages', 'Shmem', 'Unevictable', 'Mlocked', 'Cached')


def meminfo_snapshot():
    out = {}
    with open('/proc/meminfo') as f:
        for line in f:
            key, _, value = line.partition(':')
            if key in MEMINFO_KEYS:
                out[key] = int(value.split()[0]) * 1024
    out['epoch'] = round(time.time(), 3)
    return out


def _status(pid):
    out = {}
    with open(f'/proc/{pid}/status') as f:
        for line in f:
            key, _, value = line.partition(':')
            if key in ('Uid', 'VmRSS', 'RssAnon', 'RssShmem'):
                out[key] = value.split()
    return out


_users = {}


def _user(uid):
    if uid not in _users:
        try:
            _users[uid] = pwd.getpwuid(uid).pw_name
        except KeyError:
            _users[uid] = str(uid)
    return _users[uid]


def scan(pgid):
    """One sample of the runner's group and of everyone else, in bytes."""
    runner = {'VmRSS': 0, 'RssAnon': 0, 'RssShmem': 0}
    runner_pids = []
    others = {}
    me = os.getpid()
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            group = os.getpgid(pid)
            st = _status(pid)
        except (OSError, ProcessLookupError):
            continue
        if 'RssAnon' not in st:
            continue  # kernel threads
        if group == pgid:
            runner_pids.append(pid)
            for key in runner:
                runner[key] += int(st.get(key, ['0'])[0]) * 1024
        elif pid != me:
            user = _user(int(st['Uid'][0]))
            others[user] = others.get(user, 0) + int(st['RssAnon'][0]) * 1024
    return runner, runner_pids, others


def gpu_by_pid():
    out = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True, timeout=5).stdout
    used = {}
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            used[int(parts[0])] = int(parts[1]) * 1024 * 1024
    return used


class AttributionSampler:
    def __init__(self, out_prefix, pgid, interval=0.5):
        self.path = out_prefix + '-attr.jsonl'
        self.pgid = pgid
        self.interval = interval
        self.rows = []
        self.errors = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        with open(self.path, 'w') as f:
            while not self.stop_event.is_set():
                try:
                    t = time.time()
                    mem = meminfo_snapshot()
                    runner, pids, others = scan(self.pgid)
                    t_scan = time.time()
                    gpu = gpu_by_pid()
                    t_gpu = time.time()
                    runner_gpu = sum(v for pid, v in gpu.items() if pid in pids)
                    row = {'epoch': round(t, 3), 'scan_end': round(t_scan, 3),
                           'gpu_epoch': round((t_scan + t_gpu) / 2, 3), 'gpu_query_s': round(t_gpu - t_scan, 3),
                           'meminfo': mem,
                           'runner_vmrss': runner['VmRSS'], 'runner_anon': runner['RssAnon'],
                           'runner_shmem': runner['RssShmem'], 'runner_gpu': runner_gpu,
                           'other_gpu': sum(gpu.values()) - runner_gpu, 'runner_pids': len(pids), 'others_anon': others}
                    self.rows.append(row)
                    f.write(json.dumps(row) + '\n')
                    f.flush()
                except Exception as e:  # noqa: BLE001 - passive sampler; recorded, never fatal
                    if len(self.errors) < 20:
                        self.errors.append(repr(e)[:200])
                self.stop_event.wait(self.interval)

    def stop(self):
        self.stop_event.set()
        self.thread.join(10)


def _nearest(rows, t):
    """MemAvailable of the mem.csv sample nearest to t (rows sorted by epoch)."""
    lo, hi = 0, len(rows) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if rows[mid][0] < t:
            lo = mid + 1
        else:
            hi = mid
    best = min((i for i in (lo - 1, lo) if 0 <= i < len(rows)), key=lambda i: abs(rows[i][0] - t))
    return rows[best][1]


def quiet_after(mem_rows, exit_t, base, window=10.0, tolerance=0.25 * G, within=60.0):
    """The first window of `window` s whose MemAvailable spread is within `tolerance`, starting within
    `within` s of exit: its start (s after exit), mean and net change (post - pre, GiB; negative = missing)."""
    after = [(t, v) for (t, v) in mem_rows if t >= exit_t]
    j = 0
    for i in range(len(after)):
        if after[i][0] - exit_t > within:
            break
        while j < len(after) and after[j][0] - after[i][0] <= window:
            j += 1
        if j >= len(after) or after[j - 1][0] - after[i][0] < window - 0.2:
            break
        values = [v for (_, v) in after[i:j]]
        if max(values) - min(values) <= tolerance:
            mean = sum(values) / len(values)
            return {'start_after_exit_s': round(after[i][0] - exit_t, 1), 'mean_GiB': round(mean / G, 2),
                    'net_post_minus_pre_GiB': round((mean - base) / G, 2)}
    return None


def load_lag(mem_rows, attr_rows, base, start, end):
    """Seconds by which MemAvailable's drop trails the runner's GPU + host memory during the load, from the
    shift that best aligns them (positive: MemAvailable later)."""
    pts = [(r.get('gpu_epoch', r['epoch']), r['runner_gpu'] + r['runner_anon'] + r['runner_shmem'])
           for r in attr_rows if start <= r.get('gpu_epoch', r['epoch']) <= end]
    if len(pts) < 3 or not mem_rows:
        return None
    best = None
    for step in range(-30, 31):
        lag = step / 10
        err = sum(abs((base - _nearest(mem_rows, t + lag)) - v) for (t, v) in pts) / len(pts)
        if best is None or err < best[1]:
            best = (lag, err)
    return {'lag_s': best[0], 'mean_abs_error_GiB': round(best[1] / G, 2), 'points': len(pts)}


def analyse(result, mem_rows, attr_rows, base, idle_reference_gib=IDLE_REFERENCE_GIB):
    """v4/v5 memory fields for the result (all GiB). mem_rows: [(epoch, MemAvailable)]."""
    out = {}
    b = result.get('baseline', {})
    out['baseline'] = {
        'waited_s': b.get('waited_s'),
        'wait_over_60s': (b.get('waited_s') or 0) > 60,
        'idle_reference_GiB': idle_reference_gib,
        'off_reference_GiB': round(base / G - idle_reference_gib, 2),
        'off_reference': abs(base / G - idle_reference_gib) > 0.5,
    }
    exit_t = result.get('exit_epoch')
    if exit_t and mem_rows:
        window = [(t - exit_t, (base - v) / G) for (t, v) in mem_rows if exit_t <= t <= exit_t + 10.05]
        at10 = [o for (dt, o) in window if dt >= 9.5]
        offsets = {f'+{s}s': round((base - _nearest(mem_rows, exit_t + s)) / G, 2) for s in (0, 2, 5, 10, 60)}
        out['release_10s'] = {
            'offsets_GiB': offsets,
            'max_offset_GiB': round(max((o for _, o in window), default=float('nan')), 2),
            'offset_at_10s_GiB': round(sum(at10) / len(at10), 2) if at10 else None,
        }
        out['release_10s']['ok'] = (out['release_10s']['offset_at_10s_GiB'] is not None
                                    and out['release_10s']['offset_at_10s_GiB'] <= 0.5
                                    and out['release_10s']['max_offset_GiB'] <= 0.75)
    if exit_t and mem_rows:
        out['quiet_after'] = quiet_after(mem_rows, exit_t, base)
    pre = result.get('baseline_meminfo')
    v5 = [r for r in attr_rows if 'meminfo' in r]
    if v5 and pre:
        ext0 = pre['AnonPages'] + pre['Shmem']
        ext_series = [(r['epoch'], (r['meminfo']['AnonPages'] + r['meminfo']['Shmem'] - r['runner_anon'] - r['runner_shmem']) - ext0,
                       base - r['meminfo']['MemAvailable'], r['runner_gpu'], r['runner_anon'] + r['runner_shmem']) for r in v5]
        phases = []
        for ph in result['phases']:
            inside = [s for s in ext_series if ph['start'] <= s[0] <= ph['end']]
            if inside:
                phases.append({'name': ph['name'],
                               'external_growth_max_GiB': round(max(s[1] for s in inside) / G, 2),
                               'external_growth_min_GiB': round(min(s[1] for s in inside) / G, 2),
                               # The phase peak with the measured external growth at that moment taken out.
                               'peak_drop_less_external_GiB': round(max(s[2] - max(0, s[1]) for s in inside) / G, 2),
                               'residual_max_GiB': round(max(s[2] - s[3] - s[4] - s[1] for s in inside) / G, 2),
                               'residual_min_GiB': round(min(s[2] - s[3] - s[4] - s[1] for s in inside) / G, 2)})
        run_window = [s for s in ext_series if s[0] <= (exit_t or float('inf'))]
        out['external'] = {
            'formula': 'external = (AnonPages + Shmem) - runner (RssAnon + RssShmem), minus the same at the pre-run baseline',
            'max_abs_growth_GiB': round(max(abs(s[1]) for s in run_window) / G, 2) if run_window else None,
            'within_0.5GiB': bool(run_window) and max(abs(s[1]) for s in run_window) <= 0.5 * G,
            'phases': phases,
        }
        ready = next((p for p in result['phases'] if p['name'] == 'settle'), None)
        load = next((p for p in result['phases'] if p['name'] == 'load'), None)
        if ready:
            near = [r for r in v5 if ready['start'] <= r['epoch'] <= ready['end']] or [min(v5, key=lambda r: abs(r['epoch'] - ready['end']))]
            r = near[-1]
            cuda0 = sum(v for k, v in result.get('buffers_MiB', {}).items() if k.startswith('CUDA0 ')) * 1024 * 1024
            host = sum(v for k, v in result.get('buffers_MiB', {}).items() if k.startswith('CUDA_Host ')) * 1024 * 1024
            out['coverage_at_ready'] = {
                'runner_gpu_GiB': round(r['runner_gpu'] / G, 2), 'logged_CUDA0_buffers_GiB': round(cuda0 / G, 2),
                'gpu_minus_buffers_GiB': round((r['runner_gpu'] - cuda0) / G, 2),
                'runner_rssanon_GiB': round(r['runner_anon'] / G, 2), 'runner_rssshmem_GiB': round(r['runner_shmem'] / G, 2),
                'logged_CUDA_Host_buffers_GiB': round(host / G, 2),
                'residual_GiB': round((base - r['meminfo']['MemAvailable'] - r['runner_gpu'] - r['runner_anon'] - r['runner_shmem']
                                       - ((r['meminfo']['AnonPages'] + r['meminfo']['Shmem'] - r['runner_anon'] - r['runner_shmem']) - (pre['AnonPages'] + pre['Shmem']))) / G, 2),
            }
        if load:
            out['load_lag'] = load_lag(mem_rows, v5, base, load['start'], load['end'])
        out['residual_status'] = 'diagnostic only until the validation checks (rev 2, 4a-4e) pass'
    if attr_rows and mem_rows:
        series = []
        for r in attr_rows:
            drop = base - _nearest(mem_rows, r['epoch'])
            runner_host = r['runner_anon'] + r['runner_shmem']
            series.append((r['epoch'], drop, r['runner_gpu'], runner_host, drop - r['runner_gpu'] - runner_host,
                           sum(r['others_anon'].values()), r['others_anon']))
        first_others = series[0][6]
        ready = next((p for p in result['phases'] if p['name'] == 'settle'), None)
        ref = None
        if ready:
            near = [s for s in series if ready['start'] <= s[0] <= ready['end']] or \
                   [min(series, key=lambda s: abs(s[0] - ready['end']))]
            ref = sum(s[4] for s in near) / len(near)
        phases = []
        for ph in result['phases']:
            inside = [s for s in series if ph['start'] <= s[0] <= ph['end']]
            if not inside:
                continue
            un = [s[4] for s in inside]
            users = {}
            for s in inside:
                for user, v in s[6].items():
                    users[user] = max(users.get(user, 0), v - first_others.get(user, 0))
            top = sorted(users.items(), key=lambda kv: -kv[1])[:3]
            phases.append({
                'name': ph['name'],
                'runner_gpu_max_GiB': round(max(s[2] for s in inside) / G, 2),
                'runner_host_max_GiB': round(max(s[3] for s in inside) / G, 2),
                'unattributed_min_GiB': round(min(un) / G, 2),
                'unattributed_max_GiB': round(max(un) / G, 2),
                'unattributed_vs_ready_max_GiB': round(max(abs(u - ref) for u in un) / G, 2) if ref is not None else None,
                'others_anon_growth_top_GiB': [(u, round(v / G, 2)) for u, v in top],
            })
        out['attribution'] = {
            'formula': 'unattributed = (baseline - MemAvailable) - runner GPU (nvidia-smi, runner pids) - runner RssAnon - runner RssShmem',
            'samples': len(series),
            'unattributed_at_ready_GiB': round(ref / G, 2) if ref is not None else None,
            'phases': phases,
        }
        vs = [p['unattributed_vs_ready_max_GiB'] for p in phases if p['unattributed_vs_ready_max_GiB'] is not None]
        out['attribution']['within_0.5GiB_of_ready'] = bool(vs) and max(vs) <= 0.5
    return out
