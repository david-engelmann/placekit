"""Round 30 repair pins for the per loop pump registry.

The pump registry keys its pumps by event loop in a weak key
dictionary, which promises that an entry dies with its loop. The
landed pump held its own loop in a strong slot, so the value kept
its key alive and no entry could ever be released. Every loop
that served an async call was therefore retained for the life of
the process, which the audit red team measured at three hundred
entries after three hundred asyncio.run rounds. These pins hold
the repaired lifetime. A dead loop loses its entry, and the pump
machinery built on top stays quiet once its loop is gone.
"""

from __future__ import annotations

import asyncio
import gc
import weakref
from typing import Any

from placekit.client import _PUMPS, _pump_for


class _FakeHandle:
    """A native call handle stand in with the pump facing surface."""

    def __init__(self, done: bool, value: Any = None) -> None:
        self._done = done
        self._value = value
        self.aborted = False
        self.taken = 0

    def is_done(self) -> bool:
        return self._done

    def take_result(self) -> Any:
        self.taken += 1
        return self._value

    def abort(self) -> None:
        self.aborted = True


async def _pump_round() -> Any:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[Any] = loop.create_future()
    handle = _FakeHandle(done=True, value=("typed", "body", 200))
    _pump_for(loop).add(handle, future)
    return await future


def test_registry_releases_a_dead_loop() -> None:
    baseline = len(_PUMPS)
    loop = asyncio.new_event_loop()
    pump = _pump_for(loop)
    future: asyncio.Future[Any] = loop.create_future()
    pump.add(_FakeHandle(done=True, value=1), future)
    assert loop.run_until_complete(_await(future)) == 1
    assert pump.pending == {}
    loop.close()
    ref = weakref.ref(loop)
    del loop, future, pump
    gc.collect()
    assert ref() is None
    assert len(_PUMPS) == baseline


def test_repeated_asyncio_run_rounds_leave_no_entries() -> None:
    baseline = len(_PUMPS)
    for _ in range(25):
        assert asyncio.run(_pump_round()) == ("typed", "body", 200)
    gc.collect()
    assert len(_PUMPS) == baseline


def test_cancellation_removes_the_entry_and_aborts() -> None:
    loop = asyncio.new_event_loop()
    try:
        pump = _pump_for(loop)
        handle = _FakeHandle(done=False)
        future: asyncio.Future[Any] = loop.create_future()
        pump.add(handle, future)
        assert len(pump.pending) == 1
        future.cancel()
        loop.run_until_complete(asyncio.sleep(0))
        assert pump.pending == {}
        assert handle.aborted
        assert pump.timer is None
    finally:
        loop.close()


def test_timer_chain_stops_once_nothing_is_pending() -> None:
    loop = asyncio.new_event_loop()
    try:
        pump = _pump_for(loop)
        future: asyncio.Future[Any] = loop.create_future()
        pump.add(_FakeHandle(done=True, value=1), future)
        assert loop.run_until_complete(_await(future)) == 1
        assert pump.pending == {}
        loop.run_until_complete(asyncio.sleep(0.05))
        assert pump.timer is None
        assert pump.step == 0
    finally:
        loop.close()


def test_pump_stays_quiet_once_its_loop_is_gone() -> None:
    loop = asyncio.new_event_loop()
    pump = _pump_for(loop)
    future: asyncio.Future[Any] = loop.create_future()
    pump.add(_FakeHandle(done=True, value=1), future)
    assert loop.run_until_complete(_await(future)) == 1
    loop.close()
    ref = weakref.ref(loop)
    del loop, future
    gc.collect()
    assert ref() is None
    pump._kick()
    pump._poll()
    assert pump.timer is None


async def _await(future: asyncio.Future[Any]) -> Any:
    return await future
