"""Round 30 standing regression tests for the exit crash.

A process that used the AsyncClient could crash while the
interpreter exited, after every result had already been delivered
correctly. The fault lived in the completion machinery the async
bindings used to hand results back from runtime worker threads,
and it fired only during finalization. These tests run the worst
shapes as subprocesses and assert on the child exit code, because
nothing about the fault was visible while a process was working.
In suite counts stay small on purpose. The landing probes ran each
shape fifty to a hundred times against the fixed build, and the
round dossier carries those counts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import placekit

FIXTURE_BODY = (Path(__file__).parent / "fixtures" / "place_details.json").read_bytes()

STORM_CHILD = """
import asyncio
import sys

from placekit import AsyncClient


async def main():
    client = AsyncClient("test-key", base_url=sys.argv[1])
    tasks = [
        asyncio.ensure_future(client.place_details(f"slow-{i}")) for i in range(8)
    ]
    await asyncio.sleep(0.3)
    for task in tasks:
        task.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    cancelled = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
    assert cancelled == 8, f"cancelled {cancelled} of 8"
    print("storm-ok")


asyncio.run(main())
"""

ONE_CALL_CHILD = """
import asyncio
import sys

from placekit import AsyncClient


async def main():
    client = AsyncClient("test-key", base_url=sys.argv[1])
    place = await client.place_details("stub-place")
    assert place.id
    print("one-ok")


asyncio.run(main())
"""

DROP_CHILD = """
import asyncio
import sys

from placekit import AsyncClient


async def main():
    client = AsyncClient("test-key", base_url=sys.argv[1])
    tasks = [
        asyncio.ensure_future(client.place_details(f"slow-{i}")) for i in range(8)
    ]
    await asyncio.sleep(0.3)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    return client


client = asyncio.run(main())
del client
print("drop-ok")
"""

MANUAL_LOOP_CHILD = """
import asyncio
import sys

from placekit import AsyncClient


async def main(client):
    tasks = [
        asyncio.ensure_future(client.place_details(f"slow-{i}")) for i in range(8)
    ]
    await asyncio.sleep(0.3)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


client = AsyncClient("test-key", base_url=sys.argv[1])
loop = asyncio.new_event_loop()
loop.run_until_complete(main(client))
print("manual-ok")
"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        place_id = self.path.split("/")[3].split(":")[0].split("?")[0]
        if place_id.startswith("slow"):
            time.sleep(1.0)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(FIXTURE_BODY)))
        self.end_headers()
        self.wfile.write(FIXTURE_BODY)


@pytest.fixture(scope="module")
def stub_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()
    server.server_close()


def run_child(tmp_path: Path, name: str, source: str, url: str, runs: int) -> None:
    script = tmp_path / name
    script.write_text(source)
    env = dict(os.environ)
    package_parent = str(Path(placekit.__file__).resolve().parent.parent)
    env["PYTHONPATH"] = package_parent + os.pathsep + env.get("PYTHONPATH", "")
    for _ in range(runs):
        proc = subprocess.run(
            [sys.executable, str(script), url],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        assert "-ok" in proc.stdout


def test_cancelled_storm_exits_clean(tmp_path, stub_url):
    run_child(tmp_path, "storm_child.py", STORM_CHILD, stub_url, 5)


def test_one_call_then_exit_clean(tmp_path, stub_url):
    run_child(tmp_path, "one_child.py", ONE_CALL_CHILD, stub_url, 3)


def test_drop_without_collect_exits_clean(tmp_path, stub_url):
    run_child(tmp_path, "drop_child.py", DROP_CHILD, stub_url, 3)


def test_manual_unclosed_loop_exits_clean(tmp_path, stub_url):
    run_child(tmp_path, "manual_child.py", MANUAL_LOOP_CHILD, stub_url, 3)
