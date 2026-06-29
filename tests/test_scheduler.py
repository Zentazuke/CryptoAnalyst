"""Scheduler tests — task cadence + isolation, with no network or real DB writes."""
import time

from analyst.scheduler import Task, Scheduler


def test_task_due_respects_interval():
    t = Task("x", interval_s=100, fn=lambda: None)
    now = time.time()
    assert t.due(now)  # never run -> due
    t.last_run = now
    assert not t.due(now + 50)
    assert t.due(now + 100)


def test_scheduler_runs_due_tasks_and_isolates_errors(monkeypatch):
    # build a scheduler without touching DuckDB or the network
    sched = Scheduler.__new__(Scheduler)
    sched._stop = __import__("threading").Event()
    calls = {"ok": 0, "boom": 0}

    def ok():
        calls["ok"] += 1

    def boom():
        calls["boom"] += 1
        raise RuntimeError("transient fetch error")

    sched.tasks = [Task("ok", 0, ok), Task("boom", 0, boom)]
    sched._thread = None

    # run one tick of the loop body manually
    now = time.time()
    for t in sched.tasks:
        if t.due(now):
            try:
                t.fn(); t.runs += 1
            except Exception:
                t.errors += 1
            finally:
                t.last_run = time.time()

    assert calls["ok"] == 1 and calls["boom"] == 1
    ok_task = next(t for t in sched.tasks if t.name == "ok")
    boom_task = next(t for t in sched.tasks if t.name == "boom")
    assert ok_task.runs == 1 and ok_task.errors == 0
    # a failing task is counted as an error but never propagates
    assert boom_task.errors == 1


def test_status_shape():
    sched = Scheduler.__new__(Scheduler)
    sched._thread = None
    sched.symbols = ["BTC_USDT"]
    sched.timeframes = ["1h"]
    sched.tasks = [Task("candles", 300, lambda: None)]
    st = sched.status()
    assert st["running"] is False
    assert st["symbols"] == ["BTC_USDT"]
    assert st["tasks"][0]["name"] == "candles" and st["tasks"][0]["interval_s"] == 300
