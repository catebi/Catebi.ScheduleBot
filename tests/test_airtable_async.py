"""Level 1: run_airtable offloads to a worker thread and carries context along."""

import threading

from app.airtable_logger import _context, airtable_context
from app.data.airtable_async import run_airtable


async def test_returns_result():
    def work(x, y):
        return x + y

    assert await run_airtable(work, 2, 3) == 5
    assert await run_airtable(work, 2, y=3) == 5


async def test_runs_off_the_event_loop():
    def worker_thread_name():
        return threading.current_thread().name

    name = await run_airtable(worker_thread_name)
    assert name != threading.current_thread().name  # executed in a different thread


async def test_reraises_exceptions():
    def boom():
        raise ValueError("nope")

    try:
        await run_airtable(boom)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert str(e) == "nope"


async def test_airtable_context_propagates_into_worker():
    @airtable_context("mycontext")
    async def do():
        # _context is read inside the worker thread; the value must propagate.
        return await run_airtable(_context.get)

    assert await do() == "mycontext"
