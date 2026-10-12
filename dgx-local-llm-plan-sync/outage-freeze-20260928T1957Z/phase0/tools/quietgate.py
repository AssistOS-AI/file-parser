"""Quiet-host scheduling gate for the one bounded rerun round (decision of 2026-09-28, relayed by the plan review).

A scheduling heuristic only: it does not validate the attribution residual and does not make a run clean;
the functional and validity requirements of a run are unchanged.

- Without the lock, wait until observed non-runner memory ((AnonPages + Shmem) from /proc/meminfo; no runner
  is running between runs) holds within 0.25 GiB for 60 s, sampled every second.
- Then take the exclusive memory lock and re-check for 20 s under it. If the host moved, release the lock
  and wait again.
- If no quiet interval appears within 30 min, give up: the caller defers the configuration and reports it.
  The lock is never held while waiting for a quiet interval.
"""
import time

import attribution

G = 1024 ** 3
TOLERANCE = 0.25 * G


def _external():
    m = attribution.meminfo_snapshot()
    return m['AnonPages'] + m['Shmem']


def _wait_steady(seconds, deadline, interval=1.0):
    """True once the last `seconds` of samples lie within TOLERANCE; False at the deadline."""
    window = []
    while time.time() < deadline:
        now = time.time()
        window.append((now, _external()))
        window = [(t, v) for (t, v) in window if t >= now - seconds]
        values = [v for _, v in window]
        if window[-1][0] - window[0][0] >= seconds - interval and max(values) - min(values) <= TOLERANCE:
            return True
        time.sleep(interval)
    return False


def gate(who, quiet_s=60, recheck_s=20, budget_s=1800):
    """Returns (lock, record) once quiet, holding the lock; or (None, record) when deferred."""
    started = time.time()
    deadline = started + budget_s
    attempts = []
    while time.time() < deadline:
        if not _wait_steady(quiet_s, deadline):
            break
        quiet_at = time.time()
        lock, waited = attribution.memlock(who)
        if _wait_steady(recheck_s, time.time() + recheck_s + 5):
            attempts.append({'quiet_at': round(quiet_at, 3), 'lock_wait_s': waited, 'recheck': 'steady'})
            return lock, {'gate': 'passed', 'waited_s': round(time.time() - started, 1), 'attempts': attempts,
                          'quiet_s': quiet_s, 'recheck_s': recheck_s, 'tolerance_GiB': TOLERANCE / G}
        attempts.append({'quiet_at': round(quiet_at, 3), 'lock_wait_s': waited, 'recheck': 'moved; lock released'})
        attribution.memunlock(lock, who)
    return None, {'gate': 'deferred', 'waited_s': round(time.time() - started, 1), 'attempts': attempts,
                  'quiet_s': quiet_s, 'recheck_s': recheck_s, 'budget_s': budget_s, 'tolerance_GiB': TOLERANCE / G}
