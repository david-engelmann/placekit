"""Round 81 pins: every materialisable container counts toward the
dict body budget.

The materialisation ceiling walk in ``_validate_dict_body`` counted
mapping entries and list or tuple elements, but every other
container was an uncounted leaf, and the converter materialises any
sequence whole at the list-typed fields inside the free-form dict
bodies. A set, a deque or any other sequence of any size at one of
those fields therefore carried its members past the ceiling of
1000 and reached the wire. These pins hold the repaired posture:
every container the converter can materialise draws on the same
node budget, at the same boundary, at any depth, while a container
inside the budget still converts and reaches the wire as before.
"""

import asyncio
import json
import threading
from collections import UserList, deque
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from placekit import AsyncClient, Client, ConfigError
from placekit.client import _validate_dict_body


class _Stub:
    def __init__(self):
        self.bodies = []
        bodies = self.bodies

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                bodies.append(self.rfile.read(length))
                out = json.dumps({"places": []}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def wire(self):
        return json.loads(self.bodies[-1])


@pytest.fixture()
def stub():
    return _Stub()


@pytest.fixture()
def client(stub):
    return Client("test-key", base_url=stub.base_url)


def test_set_at_a_list_field_refuses_past_the_ceiling(client, stub):
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "p",
            ev_options={
                "connectorTypes": {f"T{i}" for i in range(2001)}
            },
        )
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []


def test_frozenset_at_a_list_field_refuses_past_the_ceiling(client, stub):
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "p",
            ev_options={
                "connectorTypes": frozenset(f"T{i}" for i in range(2001))
            },
        )
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []


def test_set_and_list_share_one_boundary(client, stub):
    client.text_search(
        "p", ev_options={"connectorTypes": [f"T{i}" for i in range(999)]}
    )
    assert len(stub.wire()["evOptions"]["connectorTypes"]) == 999
    client.text_search(
        "p", ev_options={"connectorTypes": {f"T{i}" for i in range(999)}}
    )
    assert len(stub.wire()["evOptions"]["connectorTypes"]) == 999
    for value in (
        [f"T{i}" for i in range(1000)],
        {f"T{i}" for i in range(1000)},
    ):
        before = len(stub.bodies)
        with pytest.raises(ConfigError) as caught:
            client.text_search("p", ev_options={"connectorTypes": value})
        assert "more than 1000 values" in str(caught.value)
        assert len(stub.bodies) == before


def test_a_small_set_still_reaches_the_wire(client, stub):
    client.text_search(
        "p",
        ev_options={
            "connectorTypes": {"EV_CONNECTOR_TYPE_1", "EV_CONNECTOR_TYPE_2"}
        },
    )
    wire = stub.wire()["evOptions"]["connectorTypes"]
    assert sorted(wire) == ["EV_CONNECTOR_TYPE_1", "EV_CONNECTOR_TYPE_2"]


def test_a_set_at_a_nested_list_field_is_counted(client, stub):
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "p",
            ev_options={
                "outer": {
                    "connectorTypes": {f"T{i}" for i in range(2001)}
                }
            },
        )
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []


def test_set_members_draw_on_the_shared_budget():
    with pytest.raises(ConfigError) as caught:
        _validate_dict_body(
            "ev_options", {"anything": {f"T{i}" for i in range(1001)}}
        )
    assert "more than 1000 values" in str(caught.value)
    _validate_dict_body(
        "ev_options", {"anything": {f"T{i}" for i in range(999)}}
    )


def test_a_frozenset_inside_a_frozenset_is_counted(client, stub):
    nested = frozenset([frozenset(f"T{i}" for i in range(1500))])
    with pytest.raises(ConfigError) as caught:
        client.text_search("p", ev_options={"connectorTypes": nested})
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []


def test_async_set_at_a_list_field_refuses_past_the_ceiling(stub):
    client = AsyncClient("test-key", base_url=stub.base_url)

    async def run():
        with pytest.raises(ConfigError) as caught:
            await client.text_search(
                "p",
                ev_options={
                    "connectorTypes": {f"T{i}" for i in range(2001)}
                },
            )
        return caught

    caught = asyncio.run(run())
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []


class _StrSequence(Sequence):
    """A minimal sequence of strings that is neither list nor tuple."""

    def __init__(self, items):
        self._items = list(items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]


def test_a_deque_at_a_list_field_refuses_past_the_ceiling(client, stub):
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "p",
            ev_options={
                "connectorTypes": deque(f"T{i}" for i in range(2001))
            },
        )
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []


def test_a_small_deque_still_reaches_the_wire(client, stub):
    client.text_search(
        "p",
        ev_options={
            "connectorTypes": deque(
                ["EV_CONNECTOR_TYPE_1", "EV_CONNECTOR_TYPE_2"]
            )
        },
    )
    wire = stub.wire()["evOptions"]["connectorTypes"]
    assert wire == ["EV_CONNECTOR_TYPE_1", "EV_CONNECTOR_TYPE_2"]


def test_a_user_list_at_a_list_field_refuses_past_the_ceiling(
    client, stub
):
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "p",
            ev_options={
                "connectorTypes": UserList(
                    f"T{i}" for i in range(2001)
                )
            },
        )
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []


def test_a_custom_sequence_at_a_list_field_is_counted(client, stub):
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "p",
            ev_options={
                "connectorTypes": _StrSequence(
                    f"T{i}" for i in range(2001)
                )
            },
        )
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []
    client.text_search(
        "p",
        ev_options={
            "connectorTypes": _StrSequence(
                ["EV_CONNECTOR_TYPE_1", "EV_CONNECTOR_TYPE_2"]
            )
        },
    )
    wire = stub.wire()["evOptions"]["connectorTypes"]
    assert wire == ["EV_CONNECTOR_TYPE_1", "EV_CONNECTOR_TYPE_2"]


def test_a_range_at_a_list_field_refuses_at_the_ceiling(client, stub):
    with pytest.raises(ConfigError) as caught:
        client.text_search(
            "p", ev_options={"connectorTypes": range(2001)}
        )
    assert "more than 1000 values" in str(caught.value)
    assert stub.bodies == []
