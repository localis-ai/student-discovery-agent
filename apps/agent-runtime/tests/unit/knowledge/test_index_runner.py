import threading

from agent_runtime.knowledge.indexer import IndexReport, drain
from agent_runtime.knowledge.index_runner import KnowledgeIndexRunner


class Service:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = 0

    def run_once(self, batch_size):
        self.calls += 1
        return self.reports.pop(0) if self.reports else IndexReport()


def test_drain_pages_until_a_short_batch():
    service = Service([IndexReport(indexed=2), IndexReport(indexed=2), IndexReport(indexed=1)])
    assert drain(service, 2).indexed == 5
    assert service.calls == 3


def test_run_exits_when_the_queue_is_empty():
    passes = []
    runner = KnowledgeIndexRunner(lambda: passes.append(1) or IndexReport())
    assert runner.request() == "started"
    runner.join(2)
    assert passes == [1]
    assert not runner.running


def test_second_request_during_a_run_reruns_exactly_once():
    started, release = threading.Event(), threading.Event()
    passes = []

    def run_pass():
        passes.append(1)
        if len(passes) == 1:
            started.set()
            assert release.wait(2)
        return IndexReport(indexed=1) if len(passes) == 1 else IndexReport()

    runner = KnowledgeIndexRunner(run_pass)
    assert runner.request() == "started"
    assert started.wait(2)
    assert runner.request() == "already_running"
    assert runner.request() == "already_running"
    release.set()
    runner.join(2)
    # pass 1 (indexed work) -> pass 2 (empty) satisfies the rerun flag: no third pass
    assert len(passes) == 2
    assert runner.request() == "started"
    runner.join(2)


def test_rerun_flag_forces_one_more_pass_even_when_first_pass_is_empty():
    started, release = threading.Event(), threading.Event()
    passes = []

    def run_pass():
        passes.append(1)
        if len(passes) == 1:
            started.set()
            assert release.wait(2)
        return IndexReport()

    runner = KnowledgeIndexRunner(run_pass)
    runner.request()
    assert started.wait(2)
    assert runner.request() == "already_running"
    release.set()
    runner.join(2)
    assert len(passes) == 2


def test_never_two_threads_at_once():
    active, peak, lock = 0, 0, threading.Lock()
    gate = threading.Event()

    def run_pass():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        gate.wait(0.05)
        with lock:
            active -= 1
        return IndexReport()

    runner = KnowledgeIndexRunner(run_pass)
    results = [runner.request() for _ in range(5)]
    runner.join(2)
    assert results.count("started") >= 1 and peak == 1


def test_an_exception_ends_the_run_and_a_later_run_works(caplog):
    outcomes = [RuntimeError("secret postgresql://u:p@h/db"), IndexReport()]
    passes = []

    def run_pass():
        passes.append(1)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    runner = KnowledgeIndexRunner(run_pass)
    assert runner.request() == "started"
    runner.join(2)
    assert not runner.running
    assert "secret" not in caplog.text and "postgresql" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert runner.request() == "started"
    runner.join(2)
    assert len(passes) == 2
