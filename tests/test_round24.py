"""Round 24 acceptance pins.

The address module's entry discipline (M1, M2, RT1, RT3): every
public helper validates what it reads, so caller shaped corruption
raises ConfigError instead of escaping as a bare builtin or flowing
into a result under a type it does not have, and a one shot iterable
answers with its real contents. The FieldMask standalone discipline
(RT4) and the of(FieldMask) repair. retry_after honesty (RT5): the
runtime value is the float the stubs declare. The duplicate cause
removal and the decode element position (Min3 actionable subset).
The star import surfaces and the async docstring parity (Min4, Min2).
"""

from __future__ import annotations

import ast
import asyncio
import time
from email.utils import formatdate
from pathlib import Path

import pytest

from placekit import AsyncClient, Client, address
from placekit.exceptions import (
    ConfigError,
    DecodeError,
    PlacesError,
    RateLimitError,
)
from placekit.fields import MAX_MATERIALIZED_ITEMS, FieldMask, normalize_fields
from placekit.models import (
    AddressComponent,
    Place,
    PlusCode,
    PostalAddress,
    TextSearchResult,
)

LOCALITY = AddressComponent(
    long_text="Springfield", short_text="SP", types=["locality"]
)
COUNTRY = AddressComponent(
    long_text="United States", short_text="US", types=["country"]
)
ROUTE = AddressComponent(long_text="Main St", short_text="Main", types=["route"])
COMPS = [LOCALITY, COUNTRY, ROUTE]

QUOTA_BODY = (
    '{"error": {"code": 429, "message": "Quota exceeded", '
    '"status": "RESOURCE_EXHAUSTED"}}'
)


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _place(**over) -> Place:
    base = dict(
        id="places/x1",
        address_components=list(COMPS),
        postal_address=PostalAddress(
            region_code="US", postal_code="12345", locality="Springfield"
        ),
    )
    base.update(over)
    return Place(**base)


# ---------------------------------------------------------------------
# Address entry discipline: bare escape classes land as ConfigError.


@pytest.mark.parametrize(
    "bad",
    [None, 123, 1.5, "locality", {"a": 1}, [None], [42], [{"long_text": "x"}]],
)
def test_components_argument_corruption_is_config_error(bad):
    with pytest.raises(ConfigError):
        address.find_components(bad, "route")


@pytest.mark.parametrize(
    "bad_place", [None, "places/x1", 123, ["not", "a", "place"]]
)
def test_place_argument_corruption_is_config_error(bad_place):
    with pytest.raises(ConfigError):
        address.country_code(bad_place)


def test_place_components_wrong_element_type_is_config_error():
    with pytest.raises(ConfigError):
        address.country_code(_place(address_components=[123]))


def test_place_components_not_iterable_is_config_error():
    with pytest.raises(ConfigError):
        address.country_code(_place(address_components=123))


def test_formatted_address_wrong_type_is_config_error():
    with pytest.raises(ConfigError):
        address.country_code(_place(formatted_address=123))


# ---------------------------------------------------------------------
# Address entry discipline: wrong typed fields refuse at the read.


def test_component_long_text_int_is_config_error():
    bad = AddressComponent(long_text=123, short_text="x", types=["route"])
    with pytest.raises(ConfigError):
        address.component_long_text([bad], "route")


def test_component_short_text_list_is_config_error():
    bad = AddressComponent(long_text="x", short_text=["y"], types=["route"])
    with pytest.raises(ConfigError):
        address.component_short_text([bad], "route")


def test_component_types_not_a_list_is_config_error():
    bad = AddressComponent(long_text="x", short_text="x", types=123)
    with pytest.raises(ConfigError):
        address.find_components([bad], "route")


def test_component_types_item_int_is_config_error():
    # An int inside the types list used to match nothing silently, so
    # the helper answered empty for a component that was there.
    bad = AddressComponent(long_text="x", short_text="x", types=[123])
    with pytest.raises(ConfigError):
        address.find_components([bad], "route")


def test_component_types_null_item_still_answers():
    # The Round 16 null settlement stands: a null element inside the
    # types list lands as None at its wire index and reads past.
    comp = AddressComponent(long_text="x", short_text="x", types=[None, "route"])
    assert address.find_components([comp], "route") == (comp,)


def test_postal_code_int_is_config_error_not_an_int_result():
    # RT1: an int postal code used to come back as the int.
    bad = PostalAddress(postal_code=12345)
    with pytest.raises(ConfigError):
        address.postal_code_from_postal_address(bad)


def test_postal_locality_dict_is_config_error():
    bad = PostalAddress(locality={"x": 1})
    with pytest.raises(ConfigError):
        address.postal_locality(bad)


def test_postal_readers_refuse_a_non_postal_address():
    with pytest.raises(ConfigError):
        address.postal_locality("Springfield")
    with pytest.raises(ConfigError):
        address.postal_region_code([1])


def test_postal_code_reading_a_place_refuses_an_int_postal_code():
    place = _place(
        address_components=[LOCALITY, COUNTRY],
        postal_address=PostalAddress(postal_code=12345),
    )
    with pytest.raises(ConfigError):
        address.postal_code(place)


def test_region_code_int_is_config_error_through_resolve_city():
    # RT3: the routing helper used to crash on .upper() here.
    place = _place(
        address_components=[LOCALITY],
        postal_address=PostalAddress(region_code=7),
    )
    with pytest.raises(ConfigError):
        address.resolve_city(place)


def test_resolve_city_refuses_an_int_locality_text():
    # RT1: the resolved city value used to be the int itself.
    bad = AddressComponent(long_text=123, short_text="x", types=["locality"])
    place = _place(address_components=[bad], postal_address=None)
    with pytest.raises(ConfigError):
        address.resolve_city(place)


def test_split_helpers_validate_their_arguments():
    with pytest.raises(ConfigError):
        address.split_compound_code(b"8FVC9G8F+6X Springfield")
    with pytest.raises(ConfigError):
        address.split_compound_code(7)
    with pytest.raises(ConfigError):
        address.split_plus_code("8FVC9G8F+6X")
    with pytest.raises(ConfigError):
        address.split_plus_code(PlusCode(global_code="g", compound_code=2))


def test_components_ceiling_is_config_error():
    many = (LOCALITY for _ in range(1001))
    with pytest.raises(ConfigError):
        address.find_components(many, "route")


# ---------------------------------------------------------------------
# Single pass iterables answer with their contents (M2, RT2). A one
# shot iterable stored on a Place is refused instead (repair, F3).


def test_generator_components_answer_directly():
    assert address.has_route(c for c in COMPS) is True
    found = address.find_components((c for c in COMPS), "route")
    assert [c.long_text for c in found] == ["Main St"]


def test_place_holding_a_generator_is_config_error():
    # Repair of red team F3. A one shot iterable stored on a
    # Place used to answer with its contents on the first
    # helper call and read empty on every later one, silently
    # flipping the answers for an unchanged place. The
    # components a Place carries must be a list or tuple, and
    # the refusal is the same on the first call and on a later
    # one, so no answer ever depends on call order.
    place = _place(address_components=(c for c in COMPS), postal_address=None)
    with pytest.raises(ConfigError):
        address.country_code(place)
    with pytest.raises(ConfigError):
        address.country_code(place)


def test_place_holding_a_generator_is_config_error_for_flags():
    place = _place(address_components=(c for c in COMPS), postal_address=None)
    with pytest.raises(ConfigError):
        address.address_flags(place)


class _ComponentBag:
    """A durable looking iterable that is neither list nor tuple."""

    def __iter__(self):
        return iter(COMPS)


def test_place_holding_another_iterable_is_config_error():
    place = _place(address_components=_ComponentBag(), postal_address=None)
    with pytest.raises(ConfigError):
        address.country_code(place)


def test_place_holding_a_tuple_of_components_answers():
    # A tuple is a durable sequence and stays accepted on a
    # Place, read after read.
    place = _place(address_components=tuple(COMPS), postal_address=None)
    assert address.country_code(place) == "US"
    assert address.address_flags(place).has_route is True


def test_corrupt_place_components_escape_nowhere():
    # RT2 companion: a Place whose components slot holds scalars used
    # to escape as a bare TypeError through the guard.
    place = _place(address_components=1.5, postal_address=None)
    with pytest.raises(ConfigError):
        address.address_flags(place)


# ---------------------------------------------------------------------
# FieldMask standalone discipline (RT4) and of(FieldMask) (Min6).


class _BadRepr:
    def __repr__(self):
        raise RuntimeError("repr boom")


def test_fieldmask_direct_hostile_member_is_config_error():
    with pytest.raises(ConfigError):
        FieldMask("places.id", _BadRepr())


def test_fieldmask_of_hostile_member_is_config_error():
    with pytest.raises(ConfigError):
        FieldMask.of([_BadRepr()])


def test_fieldmask_of_mixed_set_with_hostile_member_is_config_error():
    with pytest.raises(ConfigError):
        FieldMask.of({_BadRepr(), "places.id"})


def test_fieldmask_of_mixed_type_set_is_config_error():
    with pytest.raises(ConfigError):
        FieldMask.of({"places.id", 7})


def test_fieldmask_of_accepts_a_fieldmask():
    mask = FieldMask("places.id", "places.rating")
    assert FieldMask.of(mask) == mask
    assert normalize_fields(FieldMask.of(mask)) == [
        "places.id",
        "places.rating",
    ]


# ---------------------------------------------------------------------
# retry_after honesty (RT5, Min1 B4).


def test_retry_after_integer_header_arrives_as_float(client, raw_response):
    raw_response(429, QUOTA_BODY, headers={"Retry-After": "7"})
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.retry_after == 7.0
    assert type(excinfo.value.retry_after) is float


def test_retry_after_canned_quota_route_is_float(client):
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("TRIGGER_QUOTA")
    assert excinfo.value.retry_after == 7.0
    assert type(excinfo.value.retry_after) is float


def test_retry_after_fractional_header_keeps_its_fraction(
    client, raw_response
):
    raw_response(429, QUOTA_BODY, headers={"Retry-After": "7.5"})
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.retry_after == 7.5


def test_retry_after_negative_header_is_none(client, raw_response):
    raw_response(429, QUOTA_BODY, headers={"Retry-After": "-3"})
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.retry_after is None


def test_retry_after_http_date_in_the_future_is_seconds(
    client, raw_response
):
    future = formatdate(time.time() + 120, usegmt=True)
    raw_response(429, QUOTA_BODY, headers={"Retry-After": future})
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    value = excinfo.value.retry_after
    assert value is not None and 0 < value <= 120


def test_retry_after_http_date_in_the_past_is_zero(client, raw_response):
    past = formatdate(time.time() - 3600, usegmt=True)
    raw_response(429, QUOTA_BODY, headers={"Retry-After": past})
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.retry_after == 0.0


def test_retry_after_unparseable_header_is_none(client, raw_response):
    raw_response(429, QUOTA_BODY, headers={"Retry-After": "whenever"})
    with pytest.raises(RateLimitError) as excinfo:
        client.text_search("pizza")
    assert excinfo.value.retry_after is None


def test_retry_after_fractional_header_async(api_key, base_url, raw_response):
    async def run():
        client = AsyncClient(api_key, base_url=base_url)
        raw_response(429, QUOTA_BODY, headers={"Retry-After": "7.5"})
        with pytest.raises(RateLimitError) as excinfo:
            await client.text_search("pizza")
        assert excinfo.value.retry_after == 7.5
        assert type(excinfo.value.retry_after) is float

    asyncio.run(run())


def test_places_error_construction_coerces_retry_after_to_float():
    err = PlacesError("slow down", retry_after=7)
    assert err.retry_after == 7.0
    assert type(err.retry_after) is float
    # Round 25 supersedes the bool passthrough this test used to
    # codify: a bool is not a count of seconds, and a non numeric
    # value is not one either, so both read as None and the stored
    # value is a float or None, never the caller's object.
    assert PlacesError("x", retry_after=True).retry_after is None
    assert PlacesError("x", retry_after="7").retry_after is None


# ---------------------------------------------------------------------
# Error patterns (Min3 actionable subset): no duplicate same type
# cause, and the original chain survives the context annotation.


def test_body_builder_error_has_no_duplicate_cause(client):
    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", page_size=99)
    assert excinfo.value.context == "text_search"
    assert excinfo.value.__cause__ is None


def test_photo_validation_error_has_no_duplicate_cause(client):
    with pytest.raises(ConfigError) as excinfo:
        client.place_photo("places/x/photos/y", max_width_px=9999)
    assert excinfo.value.__cause__ is None
    assert "place_photo" in (excinfo.value.context or "")


def test_hostile_iterable_chain_survives_context_annotation(client):
    def hostile():
        yield "PRICE_LEVEL_FREE"
        raise RuntimeError("iter boom")

    with pytest.raises(ConfigError) as excinfo:
        client.text_search("pizza", price_levels=hostile())
    chain = []
    seen = excinfo.value
    while seen is not None:
        chain.append(type(seen))
        seen = seen.__cause__ or seen.__context__
        if len(chain) > 8:
            break
    assert RuntimeError in chain


# ---------------------------------------------------------------------
# Decode element position (Min3 actionable subset).


def test_decode_names_the_failing_photo_element():
    payload = {
        "id": "places/x",
        "photos": [
            {"name": "places/x/photos/a", "widthPx": 10, "heightPx": 10},
            {"name": "places/x/photos/b", "widthPx": "wide"},
        ],
    }
    with pytest.raises(DecodeError) as excinfo:
        Place.from_api(payload)
    message = excinfo.value.message
    assert "'photos'" in message
    assert "element 1" in message


def test_decode_names_the_failing_place_element():
    payload = {"places": [{"id": "places/a"}, {"id": "places/b", "rating": "high"}]}
    with pytest.raises(DecodeError) as excinfo:
        TextSearchResult.from_api(payload)
    message = excinfo.value.message
    assert "'places'" in message
    assert "element 1" in message


def test_root_decode_failure_has_no_placeholder_path(client, raw_response):
    raw_response(200, "12345")
    with pytest.raises(DecodeError) as excinfo:
        client.text_search("pizza")
    assert "?: " not in excinfo.value.message


# ---------------------------------------------------------------------
# Star import surfaces (Min4) and async docstring parity (Min2).


def _stub_surface(module_file: str) -> set[str]:
    stub = Path(module_file).with_suffix(".pyi")
    tree = ast.parse(stub.read_text())
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            names.add(node.target.id)
    return {name for name in names if not name.startswith("_")}


@pytest.mark.parametrize(
    "module_name", ["models", "fields", "exceptions", "client"]
)
def test_star_surface_matches_the_stub(module_name):
    import importlib

    module = importlib.import_module(f"placekit.{module_name}")
    assert set(module.__all__) == _stub_surface(module.__file__)
    namespace: dict = {}
    exec(f"from placekit.{module_name} import *", namespace)
    bound = {name for name in namespace if not name.startswith("_")}
    assert bound == set(module.__all__)


def test_async_docstrings_carry_the_sync_content():
    import inspect

    for name in ("text_search", "nearby_search", "autocomplete"):
        sync_doc = inspect.getdoc(getattr(Client, name))
        async_doc = inspect.getdoc(getattr(AsyncClient, name))
        assert async_doc.startswith(f"Async version of ``Client.{name}``.")
        assert async_doc.split("\n\n", 1)[1] == sync_doc.split("\n\n", 1)[1]


# ---------------------------------------------------------------------
# Repair pins: the address entry guard (red team F1 and F2), the
# shared safe repr (standards Minor), and the FieldMask
# constructor ceiling (red team I1).


def test_uninitialised_component_is_config_error():
    # F1: an instance built without its constructor has no
    # attributes to read, and the read used to escape as a
    # bare AttributeError out of the components funnel.
    bare = object.__new__(AddressComponent)
    with pytest.raises(ConfigError):
        address.find_components([bare], "route")


def test_uninitialised_place_is_config_error():
    bare = object.__new__(Place)
    with pytest.raises(ConfigError):
        address.resolve_city(bare)
    with pytest.raises(ConfigError):
        address.address_flags(bare)


def test_uninitialised_postal_address_is_config_error():
    bare = object.__new__(PostalAddress)
    with pytest.raises(ConfigError):
        address.postal_locality(bare)


def test_uninitialised_plus_code_is_config_error():
    bare = object.__new__(PlusCode)
    with pytest.raises(ConfigError):
        address.split_plus_code(bare)


class _UpperBoom(str):
    def upper(self):
        raise RuntimeError("upper boom")


def test_hostile_upper_country_code_is_config_error_with_chain():
    # F2: the routing read uppercases the country code after
    # validation, and a string subclass whose upper raises
    # used to escape as the bare RuntimeError.
    evil = AddressComponent(
        long_text="Nowhere", short_text=_UpperBoom("US"), types=["country"]
    )
    place = _place(address_components=[evil, LOCALITY], postal_address=None)
    with pytest.raises(ConfigError) as excinfo:
        address.resolve_city(place)
    assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_hostile_upper_postal_region_code_is_config_error():
    place = _place(
        address_components=[LOCALITY],
        postal_address=PostalAddress(region_code=_UpperBoom("US")),
    )
    with pytest.raises(ConfigError):
        address.resolve_city(place)


class _EqBoom(str):
    def __eq__(self, other):
        raise RuntimeError("eq boom")

    __hash__ = str.__hash__


def test_types_item_with_hostile_eq_is_config_error():
    comp = AddressComponent(
        long_text="Main St", short_text="Main", types=[_EqBoom("route")]
    )
    with pytest.raises(ConfigError):
        address.find_components([comp], "route")


class _IterBoom(list):
    def __iter__(self):
        raise RuntimeError("iter boom")


class _ContainsBoom(list):
    def __contains__(self, item):
        raise RuntimeError("contains boom")


def test_types_with_hostile_iter_is_config_error():
    comp = AddressComponent(long_text="x", short_text="y", types=["route"])
    object.__setattr__(comp, "types", _IterBoom(["route"]))
    with pytest.raises(ConfigError):
        address.find_components([comp], "route")


def test_types_with_hostile_contains_is_config_error():
    comp = AddressComponent(long_text="x", short_text="y", types=["route"])
    object.__setattr__(comp, "types", _ContainsBoom(["route"]))
    with pytest.raises(ConfigError):
        address.find_components([comp], "route")


class _GetterBoomComponent(AddressComponent):
    @property
    def long_text(self):  # type: ignore[override]
        raise RuntimeError("getter boom")


def test_component_property_getter_that_raises_is_config_error():
    evil = object.__new__(_GetterBoomComponent)
    object.__setattr__(evil, "short_text", "Main")
    object.__setattr__(evil, "types", ["route"])
    object.__setattr__(evil, "language_code", None)
    object.__setattr__(evil, "raw", {})
    with pytest.raises(ConfigError):
        address.find_components([evil], "route")


class _GetterBoomPlace(Place):
    @property
    def formatted_address(self):  # type: ignore[override]
        raise RuntimeError("place getter boom")


def test_place_property_getter_that_raises_is_config_error():
    evil = object.__new__(_GetterBoomPlace)
    object.__setattr__(evil, "address_components", list(COMPS))
    object.__setattr__(evil, "postal_address", None)
    with pytest.raises(ConfigError):
        address.resolve_city(evil)


class _GetterBoomPostal(PostalAddress):
    @property
    def locality(self):  # type: ignore[override]
        raise RuntimeError("postal getter boom")


def test_postal_property_getter_that_raises_is_config_error():
    evil = object.__new__(_GetterBoomPostal)
    object.__setattr__(evil, "region_code", "US")
    with pytest.raises(ConfigError):
        address.postal_locality(evil)


class _InterruptBoom(list):
    def __iter__(self):
        raise KeyboardInterrupt


def test_base_exception_from_a_caller_value_passes_through():
    # The guard wraps Exception only. A BaseException raised
    # by a caller supplied value stays the caller's own, the
    # standing posture everywhere in the library.
    comp = AddressComponent(long_text="x", short_text="y", types=["route"])
    object.__setattr__(comp, "types", _InterruptBoom(["route"]))
    with pytest.raises(KeyboardInterrupt):
        address.find_components([comp], "route")


def test_deliberate_config_error_keeps_its_own_message():
    # A ConfigError raised deliberately inside a helper
    # passes through the guard unchanged, message and all,
    # and gains no chained cause from the guard.
    with pytest.raises(ConfigError) as excinfo:
        address.find_components(None, "route")
    assert "components must be a sequence" in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_address_shares_the_fields_safe_repr():
    from placekit.fields import _safe_repr

    assert address._safe_repr is _safe_repr


def test_fieldmask_constructor_enforces_the_ceiling():
    # I1: the constructor now refuses past the same ceiling
    # FieldMask.of enforces, so both doors into the type
    # refuse the same absurd sizes.
    mask = FieldMask(*(["places.id"] * MAX_MATERIALIZED_ITEMS))
    assert mask.paths == ("places.id",)
    with pytest.raises(ConfigError):
        FieldMask(*(["places.id"] * (MAX_MATERIALIZED_ITEMS + 1)))
