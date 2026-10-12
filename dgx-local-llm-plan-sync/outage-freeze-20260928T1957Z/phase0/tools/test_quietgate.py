"""Desired-behaviour tests for the quiet gate v7 and the bounded memlock (scratch lock files only; never the real
.memlock). Run under flock -x /home/research/phase0/.memlock on the host: python3 tools/test_quietgate.py -v
"""
import fcntl, os, random, subprocess, sys, tempfile, time, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attribution  # noqa: E402
import quietgate  # noqa: E402

QUIET = lambda: 10 * 1024 ** 3  # noqa: E731 - a perfectly steady host


class FakeTime:
    def __init__(self):
        self.t = 0.0

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(0.0, seconds)


class Scratch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='quietgate-test-')
        self.saved = (attribution.LOCK_PATH, attribution.LOCK_LOG)
        attribution.LOCK_PATH = os.path.join(self.dir, 'lock')
        attribution.LOCK_LOG = os.path.join(self.dir, 'lock.log')
        self.holders = []

    def tearDown(self):
        for p in self.holders:
            if p.poll() is None:
                p.kill()
                p.wait()
        attribution.LOCK_PATH, attribution.LOCK_LOG = self.saved

    def hold(self, seconds):
        """Another process holds the scratch lock for `seconds`."""
        code = (f"import fcntl,time; f=open({attribution.LOCK_PATH!r},'a'); fcntl.flock(f,fcntl.LOCK_EX); "
                f"print('held',flush=True); time.sleep({seconds})")
        p = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True)
        self.assertEqual(p.stdout.readline().strip(), 'held')
        self.holders.append(p)
        return p

    def free_now(self):
        """True if another process can take the scratch lock at once."""
        code = (f"import fcntl,sys; f=open({attribution.LOCK_PATH!r},'a')\n"
                f"try:\n fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); sys.exit(0)\nexcept BlockingIOError:\n sys.exit(1)")
        return subprocess.run([sys.executable, '-c', code]).returncode == 0

    @staticmethod
    def real_lock(yield_s=0.2):
        return lambda who, deadline: attribution.memlock(who, yield_s=yield_s, deadline=deadline)


class GateTests(Scratch):
    def test_pass_quiet_host_free_lock(self):
        started = time.monotonic()
        handle, rec = quietgate.gate('t', quiet_s=2, recheck_s=1, budget_s=10, external=QUIET, lock=self.real_lock())
        elapsed = time.monotonic() - started
        self.assertEqual(rec['gate'], 'passed')
        self.assertIsNotNone(handle)
        self.assertLessEqual(elapsed, 10)
        self.assertFalse(self.free_now(), 'the gate holds the lock after passing')
        attribution.memunlock(handle, 't')
        self.assertTrue(self.free_now())

    def test_contention_past_deadline_defers_by_deadline_and_leaves_no_waiter(self):
        holder = self.hold(8)
        started = time.monotonic()
        handle, rec = quietgate.gate('t', quiet_s=1, recheck_s=1, budget_s=3, external=QUIET, lock=self.real_lock())
        elapsed = time.monotonic() - started
        self.assertIsNone(handle)
        self.assertEqual(rec['gate'], 'deferred')
        self.assertLessEqual(elapsed, 3.3)
        self.assertFalse(rec['lock_taken'])
        holder.kill()
        holder.wait()
        self.assertTrue(self.free_now(), 'no waiter of ours takes the lock after the holder leaves')

    def test_default_yield_counts_against_the_budget(self):
        started = time.monotonic()
        handle, rec = quietgate.gate('t', quiet_s=1, recheck_s=1, budget_s=4, external=QUIET)  # 5 s default yield
        self.assertLessEqual(time.monotonic() - started, 4.3)
        self.assertIsNone(handle)
        self.assertEqual(rec['gate'], 'deferred')
        self.assertEqual(rec['lock_taken'], rec['lock_released'])
        self.assertTrue(self.free_now())

    def test_quiet_near_deadline_defers_and_never_passes_late(self):
        fake = FakeTime()
        calls = []
        handle, rec = quietgate.gate('t', quiet_s=3, recheck_s=2, budget_s=3.5, clock=fake.clock, sleep=fake.sleep,
                                     external=QUIET, lock=lambda who, d: calls.append(d) or ('h', 0), unlock=lambda h, w: None)
        self.assertIsNone(handle)
        self.assertEqual(rec['gate'], 'deferred')
        self.assertEqual(calls, [], 'no lock is taken when the recheck cannot finish in time')
        self.assertLessEqual(fake.t, 3.5)

    def test_codex_stub_ten_second_lock_defers_by_five_seconds(self):
        # Converted reproduction: gate(quiet_s=2, recheck_s=2, budget_s=5) with a lock that frees after 10 s.
        fake = FakeTime()

        def slow_lock(who, deadline):
            free_at = 10.0
            if deadline < free_at:
                fake.t = max(fake.t, deadline)
                return None, deadline
            fake.t = free_at
            return 'h', free_at

        unlocked = []
        handle, rec = quietgate.gate('t', quiet_s=2, recheck_s=2, budget_s=5, clock=fake.clock, sleep=fake.sleep,
                                     external=QUIET, lock=slow_lock, unlock=lambda h, w: unlocked.append(h))
        self.assertIsNone(handle)
        self.assertEqual(rec['gate'], 'deferred')
        self.assertLessEqual(fake.t, 5.0)
        self.assertFalse(rec['lock_taken'])

    def test_codex_stub_positive_control_zero_lock_delay_passes_at_two_seconds(self):
        fake = FakeTime()
        handle, rec = quietgate.gate('t', quiet_s=2, recheck_s=2, budget_s=5, clock=fake.clock, sleep=fake.sleep,
                                     external=QUIET, lock=lambda who, d: ('h', 0), unlock=lambda h, w: None)
        self.assertEqual(rec['gate'], 'passed')
        self.assertEqual(handle, 'h')
        self.assertLessEqual(fake.t, 5.0)

    def test_release_then_reacquire_within_budget_passes(self):
        self.hold(1.5)
        handle, rec = quietgate.gate('t', quiet_s=1, recheck_s=1, budget_s=10, external=QUIET, lock=self.real_lock())
        self.assertEqual(rec['gate'], 'passed')
        self.assertGreaterEqual(rec['attempts'][-1]['lock_wait_s'], 0.3)
        attribution.memunlock(handle, 't')
        log = open(attribution.LOCK_LOG).read()
        self.assertIn('waits: the lock is held by another process', log)
        self.assertIn('(another holder released it)', log)

    def test_lock_released_on_deferral_is_free_at_once(self):
        state = {'n': 0}

        def moving():  # steady until the lock is held, then the host keeps moving
            state['n'] += 1
            return (state['n'] % 2) * 1024 ** 3 if os.path.exists(attribution.LOCK_PATH) and not self.free_now() else 0

        handle, rec = quietgate.gate('t', quiet_s=1, recheck_s=1, budget_s=5, external=moving, lock=self.real_lock())
        self.assertIsNone(handle)
        self.assertEqual(rec['gate'], 'deferred')
        self.assertTrue(rec['lock_taken'])
        self.assertTrue(rec['lock_released'])
        self.assertTrue(self.free_now())

    def test_error_under_the_lock_releases_it(self):
        state = {'locked': False}

        def lock(who, deadline):
            handle, waited = attribution.memlock(who, yield_s=0, deadline=deadline)
            state['locked'] = True
            return handle, waited

        def failing():
            if state['locked']:
                raise OSError('meminfo read failed')
            return 0

        with self.assertRaises(OSError):
            quietgate.gate('t', quiet_s=1, recheck_s=1, budget_s=5, external=failing, lock=lock)
        self.assertTrue(self.free_now())

    def test_never_passes_after_deadline_randomised(self):
        rng = random.Random(7)
        for _ in range(300):
            fake = FakeTime()
            delay = rng.choice([0, 0.5, 2, 4, 9])
            budget = rng.choice([2, 3, 5, 8])

            def lock(who, deadline, delay=delay, fake=fake):
                if fake.t + delay > deadline:
                    fake.t = deadline
                    return None, delay
                fake.t += delay
                return 'h', delay

            released = []
            handle, rec = quietgate.gate('t', quiet_s=rng.choice([1, 2]), recheck_s=rng.choice([1, 2]), budget_s=budget,
                                         clock=fake.clock, sleep=fake.sleep, external=QUIET, lock=lock,
                                         unlock=lambda h, w: released.append(h))
            if rec['gate'] == 'passed':
                self.assertLessEqual(fake.t, budget)
                self.assertEqual(handle, 'h')
            else:
                self.assertIsNone(handle)
                self.assertEqual(rec['lock_taken'], rec['lock_released'])


class MemlockTests(Scratch):
    def test_no_deadline_keeps_blocking_behaviour(self):
        self.hold(1.0)
        handle, waited = attribution.memlock('m', yield_s=0)
        self.assertIsNotNone(handle)
        self.assertGreaterEqual(waited, 0.5)
        attribution.memunlock(handle, 'm')

    def test_deadline_returns_none_and_logs(self):
        self.hold(5)
        handle, waited = attribution.memlock('m', yield_s=0, deadline=time.monotonic() + 1)
        self.assertIsNone(handle)
        self.assertLessEqual(waited, 1.4)
        self.assertIn('gave up', open(attribution.LOCK_LOG).read())


if __name__ == '__main__':
    unittest.main()
