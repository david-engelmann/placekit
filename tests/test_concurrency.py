"""Round 19 (T9) concurrency regressions.

The close race tests drive the race through caller input alone, with
no timing window to hit. A fields iterable that closes the client
while the call is building its body, and a Photo width whose
comparison closes the client while its size is being defaulted, both
land the close after the entry check and before the native call on
the old code, where the call then dereferenced a handle that close
had already cleared and escaped as a bare AttributeError.

The fork test runs in a subprocess because a wedged child must never
be able to hang this suite. The child reports through a file, the
script kills it at a hard deadline, and the subprocess itself runs
under a timeout.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import textwrap

import pytest

from placekit import AsyncClient, Client
from placekit.exceptions import ConfigError
from placekit.models import Photo

PHOTO_NAME = "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample"


class ClosingFields:
    """A fields iterable that closes its client mid iteration."""

    def __init__(self, client):
        self._client = client

    def __iter__(self):
        yield "places.displayName"
        self._client.close()
        yield "places.rating"


class ClosingWidth(int):
    """An int width whose first >= comparison closes its client."""

    def __new__(cls, value, client):
        instance = super().__new__(cls, value)
        instance._client = client
        instance._fired = False
        return instance

    def __ge__(self, other):
        if not self._fired:
            self._fired = True
            self._client.close()
        return super().__ge__(other)


def closing_photo(client) -> Photo:
    return Photo(
        name=PHOTO_NAME,
        width_px=ClosingWidth(800, client),
        height_px=600,
    )


def test_close_racing_sync_text_search_completes(api_key, base_url):
    # The call captured its handle at entry, so a close landing
    # during body building cannot withdraw it. The call completes
    # and only later calls are refused.
    client = Client(api_key, base_url=base_url)
    result = client.text_search("cafes", fields=ClosingFields(client))
    assert len(result.places) == 2
    with pytest.raises(ConfigError):
        client.text_search("cafes")


def test_close_racing_async_text_search_completes(api_key, base_url):
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        result = await client.text_search(
            "cafes", fields=ClosingFields(client)
        )
        assert len(result.places) == 2
        with pytest.raises(ConfigError):
            await client.text_search("cafes")

    asyncio.run(run())


def test_close_racing_sync_place_photo_completes(api_key, base_url):
    # The photo path takes no fields, so its window is the Photo
    # size defaulting, reached through the width comparison.
    client = Client(api_key, base_url=base_url)
    media = client.place_photo(closing_photo(client))
    assert media.content_type == "image/png"
    with pytest.raises(ConfigError):
        client.place_photo(PHOTO_NAME, max_width_px=100)


def test_close_racing_async_place_photo_completes(api_key, base_url):
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        media = await client.place_photo(closing_photo(client))
        assert media.content_type == "image/png"
        with pytest.raises(ConfigError):
            await client.place_photo(PHOTO_NAME, max_width_px=100)

    asyncio.run(run())


_FORK_CHILD_SCRIPT = textwrap.dedent(
    """
    import asyncio
    import json
    import os
    import signal
    import sys
    import time

    from placekit import AsyncClient, Client

    base_url, result_path = sys.argv[1], sys.argv[2]

    inherited_sync = Client("test-api-key", base_url=base_url)
    inherited_async = AsyncClient("test-api-key", base_url=base_url)
    warm = inherited_sync.text_search("cafes")
    assert len(warm.places) == 2

    sys.stdout.flush()
    sys.stderr.flush()
    pid = os.fork()
    if pid == 0:
        outcomes = {}

        def record(name, call):
            try:
                result = call()
                outcomes[name] = f"success places={len(result.places)}"
            except BaseException as exc:
                outcomes[name] = f"{type(exc).__name__}: {exc}"

        record(
            "fresh_sync",
            lambda: Client("test-api-key", base_url=base_url).text_search(
                "cafes"
            ),
        )
        record(
            "inherited_sync",
            lambda: inherited_sync.text_search("cafes"),
        )

        async def async_calls():
            fresh = AsyncClient("test-api-key", base_url=base_url)
            outcomes["fresh_async"] = (
                f"success places={len((await fresh.text_search('cafes')).places)}"
            )
            outcomes["inherited_async"] = (
                f"success places={len((await inherited_async.text_search('cafes')).places)}"
            )

        try:
            asyncio.run(async_calls())
        except BaseException as exc:
            outcomes["async"] = f"{type(exc).__name__}: {exc}"
        fd = os.open(result_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        os.write(fd, json.dumps(outcomes).encode())
        os.close(fd)
        os._exit(0)

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        done, sts = os.waitpid(pid, os.WNOHANG)
        if done:
            status = sts
            break
        time.sleep(0.05)
    if status is None:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        print("child hung past the deadline and was killed")
        sys.exit(3)
    sys.exit(0)
    """
)


@pytest.mark.skipif(
    not hasattr(__import__("os"), "fork"),
    reason="fork is not available on this platform",
)
def test_fork_after_first_use_child_calls_work(base_url, tmp_path):
    # A process that calls placekit and then forks must leave the
    # child able to call. Before the fork aware runtime this child
    # hung forever on every call, fresh clients included, because
    # the process global runtime's worker threads do not survive a
    # fork. The child gets ten seconds, then it is killed and this
    # test fails on the missing result file.
    result_path = tmp_path / "fork_child.json"
    completed = subprocess.run(
        [sys.executable, "-c", _FORK_CHILD_SCRIPT, base_url, str(result_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    outcomes = json.loads(result_path.read_text())
    assert outcomes["fresh_sync"] == "success places=2"
    assert outcomes["inherited_sync"] == "success places=2"
    assert outcomes["fresh_async"] == "success places=2"
    assert outcomes["inherited_async"] == "success places=2"
