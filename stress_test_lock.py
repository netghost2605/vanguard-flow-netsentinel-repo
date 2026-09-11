#!/usr/bin/env python3
"""
Stress-tests the exact _try_start_test() pattern added to speedtest_monitor.py,
to prove the race it's meant to close (two threads both seeing _test_busy() ==
False in the same instant and both proceeding) is actually closed, rather than
just trusting that "with self._test_lock:" is correct by inspection.

Runs two versions back to back:
  1. OLD pattern (separate check-then-set, no lock) -- expected to show
     double-claims under enough contention, proving the bug was real.
  2. NEW pattern (_try_start_test, atomic under a lock) -- expected to show
     zero double-claims no matter how much contention is thrown at it.
"""
import threading
import time

N_THREADS = 64
N_ROUNDS = 500


class OldStyle:
    def __init__(self):
        self._running_manual = False
        self._running_auto = False

    def _test_busy(self):
        return bool(self._running_manual or self._running_auto)

    def claim(self, auto=False):
        if self._test_busy():
            return False
        # A real thread switch (or a GIL release during I/O) can land here,
        # between the check above and the claim below -- that gap is the
        # actual bug, whether it's one nanosecond or one millisecond wide.
        # Widened deliberately so the race is reproducible in a short run
        # instead of relying on getting unlucky against the real scheduler.
        time.sleep(0.0005)
        if auto:
            self._running_auto = True
        else:
            self._running_manual = True
        return True

    def release(self, auto=False):
        if auto:
            self._running_auto = False
        else:
            self._running_manual = False


class NewStyle:
    def __init__(self):
        self._running_manual = False
        self._running_auto = False
        self._test_lock = threading.Lock()

    def _try_start_test(self, auto=False):
        with self._test_lock:
            if self._running_manual or self._running_auto:
                return False
            if auto:
                self._running_auto = True
            else:
                self._running_manual = True
            return True

    def release(self, auto=False):
        if auto:
            self._running_auto = False
        else:
            self._running_manual = False


def run(monitor, claim_fn, rounds, threads, label):
    double_claims = [0]
    concurrent = [0]
    lock = threading.Lock()

    def worker(i):
        for _ in range(rounds):
            auto = (i % 2 == 0)
            ok = claim_fn(monitor, auto)
            if ok:
                with lock:
                    concurrent[0] += 1
                    if concurrent[0] > 1:
                        double_claims[0] += 1
                # simulate the "speed test" taking a moment
                time.sleep(0.0002)
                with lock:
                    concurrent[0] -= 1
                monitor.release(auto)

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    t0 = time.monotonic()
    for t in ts: t.start()
    for t in ts: t.join()
    dt = time.monotonic() - t0
    print(f"[{label}] threads={threads} rounds/thread={rounds} "
          f"elapsed={dt:.2f}s double_claims={double_claims[0]}")
    return double_claims[0]


if __name__ == "__main__":
    old_double = run(OldStyle(), lambda m, a: m.claim(a), N_ROUNDS, N_THREADS, "OLD (no lock)")
    new_double = run(NewStyle(), lambda m, a: m._try_start_test(a), N_ROUNDS, N_THREADS, "NEW (locked)")

    print()
    if old_double > 0:
        print(f"CONFIRMED: old check-then-set pattern double-claimed {old_double} times "
              f"under contention -- the race is real.")
    else:
        print("NOTE: old pattern got lucky this run and showed 0 double-claims "
              "(a race condition isn't guaranteed to fire every run) -- "
              "re-run or raise N_THREADS/N_ROUNDS if you need a repro.")

    if new_double == 0:
        print("PASS: new _try_start_test() pattern never double-claimed, "
              f"across {N_THREADS * N_ROUNDS} attempts.")
    else:
        print(f"FAIL: new pattern still double-claimed {new_double} times -- NOT fixed.")
        raise SystemExit(1)
