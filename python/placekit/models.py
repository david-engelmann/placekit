"""Typed response models for placekit.

Responses arrive as dataclasses with attribute access, never raw dicts.
Fields this client version does not model yet are preserved verbatim
on ``raw``. Every model object that decodes from a JSON object
preserves that object on its ``raw``, so nothing the API returns is
silently lost at any level of the tree. ``raw`` shares no mutable
state with any other copy. ``PhotoMedia`` is the
one class with no ``raw``, because its payload is bytes rather than
a JSON object.

Responses populate attributes only from fields the response
carried, and the response carries only what the field mask
requested and the API had values for. An optional attribute that
reads None was not returned, and not returned covers both fields
the mask never requested and fields the API had no value for,
which cannot be told apart from the object. List attributes read
an empty list in the same state, and a few string and number
attributes read their empty default. The ``raw`` payload answers
the narrower question of what the response carried. A wire name
is a key in ``raw`` exactly when the response carried that field,
at the model layer and through the client alike. Through the
client the core returns the response body beside the typed
value and ``raw`` is built from the body itself, so an explicit
null, an explicitly empty list, an empty string and a zero value
all keep their keys, and no value the wire did not send is ever
fabricated into it. No attribute raises for being
unreturned, and the
way to populate the full modelled set is a ``place_details``
call, whose default mask requests all of it.

The models are frozen value objects. Attribute assignment on a
parsed result raises instead of silently rewriting it, so a result
can be shared without one holder rebinding another holder's fields.
The freeze is shallow by design. List fields and each ``raw`` dict
remain mutable in place, so a holder can still append to
``place.types`` or edit ``place.raw``; only rebinding is refused.
They stay unhashable where they carry list fields; ``LatLng``, the
one pure pair, is hashable. Every ``raw`` is a deep copy of the
payload it came from, or at the top of a client call the parsed
body itself, which the client built for that call and holds no
other reference to. Either way the caller's dict, a result's raw
and a child's raw share no mutable state.
"""

from __future__ import annotations

import contextvars
import copy
import math
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterator, Optional

from .exceptions import ConfigError, DecodeError


def _require(data: dict[str, Any], key: str, model: str) -> Any:
    """Fetch a required payload key or raise a DecodeError naming it.

    One strictness policy for every decoder (RC-18): a missing
    required key is a DecodeError with the key and model named, never
    a bare KeyError and never a fabricated empty object.
    """
    if key not in data:
        raise DecodeError(f"{model} payload is missing required key {key!r}")
    return data[key]


def _as_float(value: Any, model: str, key: str) -> float:
    if isinstance(value, bool):
        raise DecodeError(f"{model} payload key {key!r} is not a number: {value!r}")
    try:
        return float(value)
    except Exception as exc:
        # The catch is the whole Exception family, matching the
        # integer decoder beside it. A huge integer in a float
        # position raises OverflowError on conversion, which used
        # to escape the direct layer bare (R20-F13), and a payload
        # object whose own float conversion raises must surface
        # the same way, as a DecodeError, never the bare builtin
        # it raised.
        raise DecodeError(
            f"{model} payload key {key!r} is not a number: {value!r}"
        ) from exc


def _as_int(value: Any, model: str, key: str) -> int:
    if isinstance(value, bool):
        raise DecodeError(f"{model} payload key {key!r} is not an integer: {value!r}")
    try:
        fractional = (
            (isinstance(value, float) and not value.is_integer())
            or (
                isinstance(value, Decimal)
                and value != value.to_integral_value()
            )
            or (isinstance(value, Fraction) and value.denominator != 1)
        )
    except Exception as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not an integer: {value!r}"
        ) from exc
    if fractional:
        # A fractional value in an integer position is refused, not
        # truncated (R20-F03). Silently dropping the fraction made
        # the typed view contradict raw with no signal; the Rust
        # core rejects the same shape at every position it models,
        # and an exactly integral value still decodes normally.
        # The check covers every standard numeric type that can
        # carry a fraction, float and Decimal and Fraction alike,
        # because a recorded payload replayed through a parser
        # that yields Decimal values reaches the same defect with
        # a different type.
        raise DecodeError(
            f"{model} payload key {key!r} is not an integer: {value!r}"
        )
    try:
        result = int(value)
    except Exception as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not an integer: {value!r}"
        ) from exc
    try:
        str(result)
    except ValueError as exc:
        # An integer past the interpreter string conversion limit
        # would store successfully and then raise a bare ValueError
        # the first time the result is printed or logged (R20-F14
        # residue). The client path refuses the same value at the
        # bindings, so the direct layer refuses it here instead.
        raise DecodeError(
            f"{model} payload key {key!r} is an integer too large "
            f"to print: {exc}"
        ) from exc
    return result


def _as_str(value: Any, model: str, key: str) -> Optional[str]:
    """Decode one declared string slot.

    A value that is not a string and not null is refused with a
    DecodeError instead of being stored verbatim in a slot whose
    type declaration forbids it (R20-F04). Null passes through
    exactly as it always has. The Round 16 typed position null
    settlements govern null at these positions and are not
    reopened; this check governs the wrong type family only, so a
    number, a boolean, a list or an object in a string slot is the
    defect refused here, never a null.
    """
    if value is None or isinstance(value, str):
        return value
    raise DecodeError(
        f"{model} payload key {key!r} is not a string: {value!r}"
    )


def _optional_int(value: Any, model: str, key: str) -> Optional[int]:
    return None if value is None else _as_int(value, model, key)


def _optional_bool(value: Any, model: str, key: str) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise DecodeError(
        f"{model} payload key {key!r} is not a boolean: {value!r}"
    )


def _str_list(value: Any, model: str, key: str) -> list[str]:
    """Decode a list of strings; a bare string is a DecodeError, never
    shredded into one-character items.

    The value must be a JSON array shape. A mapping in the slot is
    refused rather than read as its keys, which fabricated list
    contents the payload never sent as a list (R20-F12), and an
    element that is not a string is refused instead of being stored
    unchecked. A null element still lands as None at its wire
    index, under the Round 16 typed position null settlement for
    modelled string lists, which this check does not reopen.
    """
    if isinstance(value, (str, bytes)):
        raise DecodeError(
            f"{model} payload key {key!r} is a single string, not a list"
        )
    if not isinstance(value, (list, tuple)):
        raise DecodeError(
            f"{model} payload key {key!r} is not a list: {value!r}"
        )
    try:
        items = list(value)
    except Exception as exc:
        # A list subclass whose own iteration raises must surface
        # as a DecodeError, not the bare builtin it raised; the
        # helper trusts the container protocol, so the read is
        # guarded the way the payload preparation is.
        raise DecodeError(
            f"{model} payload key {key!r} could not be read "
            f"as a list: {exc!r}"
        ) from exc
    for item in items:
        if item is not None and not isinstance(item, str):
            raise DecodeError(
                f"{model} payload key {key!r} holds an item that "
                f"is not a string: {item!r}"
            )
    return items


def _model_list(value: Any, model: str, key: str) -> list:
    """Validate one payload slot that must carry a JSON array of
    sub payloads, so a scalar, a mapping or a null in the slot is a
    DecodeError naming the slot instead of a bare builtin from the
    iteration that follows (R20-F05)."""
    if isinstance(value, (list, tuple)):
        try:
            return list(value)
        except Exception as exc:
            raise DecodeError(
                f"{model} payload key {key!r} could not be read "
                f"as a list: {exc!r}"
            ) from exc
    raise DecodeError(
        f"{model} payload key {key!r} is not a list: {value!r}"
    )


#: The deepest container nesting a ``from_api`` payload may carry.
#: Past it the payload is refused with a DecodeError before any
#: decoding runs, so deep nesting can no longer kill decoding with
#: a bare RecursionError inside the payload copy (R20-F06). The
#: wire path stops earlier, at the Rust parser limit; this guard
#: is the direct layer's own stated bound, in the same spirit as
#: the client body guard of the same depth.
_MAX_PAYLOAD_DEPTH = 128


def _validate_payload(data: Any, model: str) -> None:
    """Validate one ``from_api`` payload without copying it.

    The payload must be a JSON object and its container nesting
    must stay within the stated depth guard, so deep nesting can
    no longer kill decoding with a bare RecursionError inside the
    payload copy (R20-F06). The walk trusts the payload's own
    container protocols, so a mapping whose values method raises
    surfaces as a DecodeError rather than the bare builtin it
    raised. BaseException subclasses are process control flow and
    pass through untouched, here as everywhere in the library.
    """
    if not isinstance(data, dict):
        raise DecodeError(
            f"{model} payload must be an object, got "
            f"{type(data).__name__}: {data!r}"
        )
    try:
        stack = [(data, 1)]
        while stack:
            node, depth = stack.pop()
            if isinstance(node, dict):
                if depth > _MAX_PAYLOAD_DEPTH:
                    raise DecodeError(
                        f"{model} payload is nested deeper than "
                        f"{_MAX_PAYLOAD_DEPTH} levels"
                    )
                stack.extend((child, depth + 1) for child in node.values())
            elif isinstance(node, (list, tuple)):
                if depth > _MAX_PAYLOAD_DEPTH:
                    raise DecodeError(
                        f"{model} payload is nested deeper than "
                        f"{_MAX_PAYLOAD_DEPTH} levels"
                    )
                stack.extend((child, depth + 1) for child in node)
    except DecodeError:
        raise
    except Exception as exc:
        raise DecodeError(
            f"{model} payload could not be read: {exc!r}"
        ) from exc


def _prepare_payload(data: Any, model: str) -> dict[str, Any]:
    """Validate and copy one ``from_api`` payload.

    Every decoder in this module promises one strictness policy
    (RC-18): a malformed payload raises a DecodeError naming the
    problem, never a bare builtin. That promise starts here. The
    payload is validated under ``_validate_payload`` and only then
    is it deep copied for decoding (R20-F05 and F06).
    """
    _validate_payload(data, model)
    try:
        return copy.deepcopy(data)
    except DecodeError:
        raise
    except Exception as exc:
        # An object whose copy machinery raises surfaces the same
        # way as one whose containers cannot be read, as a
        # DecodeError rather than the bare builtin it raised.
        raise DecodeError(
            f"{model} payload could not be read: {exc!r}"
        ) from exc


class _DecodeOwnership:
    """The ownership state of one client conversion.

    The state pairs the parsed body tree the client built for one
    conversion with the process that opened the window. The
    pairing with the process id mirrors the bindings runtime slot
    across fork (Round 19). A child process forked mid conversion
    inherits the memory but not the conversion, so it must not
    inherit the window either.
    """

    __slots__ = ("pid", "raw_root")

    def __init__(self, raw_root: dict[str, Any]) -> None:
        self.pid = os.getpid()
        self.raw_root = raw_root


_decode_ownership: contextvars.ContextVar[Optional[_DecodeOwnership]] = (
    contextvars.ContextVar("placekit_decode_ownership", default=None)
)


@contextmanager
def _owned_decode(raw_root: dict[str, Any]) -> Iterator[None]:
    """Mark the conversion the client runs over one parsed body.

    Inside the window the model layer knows both decode sources
    are owned by the call itself. The client built the typed dict
    fresh in the bindings for this call and parsed the body text
    for this conversion alone, and it drops both when the call
    returns. That ownership is what makes the copies the direct
    layer needs against caller supplied input redundant here,
    under the decoder discipline this module holds. Decoders read
    their payload, they never mutate it, and they never retain a
    part of it outside ``raw``. Only the client opens the window,
    and only around the conversion of one response.
    """
    token = _decode_ownership.set(_DecodeOwnership(raw_root))
    try:
        yield
    finally:
        _decode_ownership.reset(token)


def _ownership() -> Optional[_DecodeOwnership]:
    ownership = _decode_ownership.get()
    if ownership is not None and ownership.pid == os.getpid():
        return ownership
    return None


def _prepare(
    data: Any, raw: Optional[dict[str, Any]], model: str
) -> tuple[dict[str, Any], Any]:
    """Settle the two sources of one ``from_api`` decode.

    Every decoder opens with this call. It validates the payload
    under the same rules as ``_prepare_payload`` and returns the
    payload to read attributes from beside the payload to keep as
    the node's ``raw``, with the copies between them paid only
    where a copy is load bearing (Round 21).

    Off the client path the payload is deep copied once, because
    a direct caller keeps their dict and the result must share no
    mutable state with it. When the caller hands the same object
    as both sources, which is what every child decode on that
    path receives, the one copy serves both and no second copy is
    made. A raw source handed over separately is deep copied,
    because a node's raw must share no mutable state with its
    parent's raw or with the caller's.

    Inside a client conversion both sources are already owned by
    the call, so the payload is read in place and only raw is
    copied, once per node below the first. The first node's raw
    is the parsed body itself, adopted rather than copied,
    because the client built that tree for this conversion and
    nothing outside the result ever holds it.
    """
    ownership = _ownership()
    if ownership is not None:
        _validate_payload(data, model)
        if raw is ownership.raw_root:
            return data, raw
        if raw is None or raw is data:
            # A node whose raw source is its own payload, because
            # the raw tree held no subtree for it, still keeps a
            # raw of its own, copied from the payload it reads.
            return data, copy.deepcopy(data)
        return data, copy.deepcopy(raw)
    prepared = _prepare_payload(data, model)
    if raw is None or raw is data:
        return prepared, prepared
    return prepared, copy.deepcopy(raw)


def _raw_subtree(raw: Any, key: str, fallback: Any) -> Any:
    """The raw source for a child model under one wire key.

    When the raw source carries the key, its subtree is the child's
    raw source, an explicit null included. When a raw source is
    supplied and it does not carry the key, the child raw is empty.
    The attribute source subtree is never substituted on a supplied
    raw source, because the typed tree carries defaulted children
    the wire never sent (the viewport corners above all), and the
    substitution would fabricate a raw for a child the body never
    mentioned. Each decoder names the wire key it reads, which is
    the same key the raw source is read under, so the two trees
    stay aligned by construction. With no raw source supplied the
    decoder default makes the raw source the attribute source
    itself, so any key a child is decoded from is present by
    construction and the direct model layer behaviour is unchanged.
    A raw source that is not an object at all keeps the attribute
    source, which is the explicit null and malformed subtree case
    the decoders have always read that way.
    """
    if isinstance(raw, dict):
        return raw.get(key, {})
    return fallback


def _raw_element(raw: Any, key: str, index: int, fallback: Any) -> Any:
    """The raw source for one element of a list child, by wire
    index, with the attribute element as the fallback when the raw
    source has no element at that index."""
    if isinstance(raw, dict):
        items = raw.get(key)
        if isinstance(items, list) and index < len(items):
            return items[index]
    return fallback


def _reject_bare_string(model: str, field_name: str, value: Any) -> None:
    """Direct construction guard (RT5-L3): a list-typed field handed
    a bare string or bytes value would otherwise store it unchecked,
    and iterating the field later would yield one-character items,
    the shred the decoders already refuse on the response side."""
    if isinstance(value, (str, bytes)):
        raise ConfigError(
            f"{model} field {field_name!r} must be a list, not a "
            f"single string: {value!r}"
        )


@dataclass(frozen=True, slots=True)
class LocalizedText:
    """A text value paired with its language."""

    text: str
    language_code: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "LocalizedText":
        data, raw = _prepare(data, raw, "LocalizedText")
        return cls(
            text=_as_str(data.get("text", ""), "LocalizedText", "text"),
            language_code=_as_str(
                data.get("languageCode"), "LocalizedText", "languageCode"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class LatLng:
    """A latitude/longitude pair.

    Construction validates the values are real, finite numbers
    (bools and strings are not coordinates). Range is a request-side
    rule enforced by the client at call time, so a LatLng decoded
    from a response is preserved exactly as the API sent it.
    """

    latitude: float
    longitude: float
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("latitude", self.latitude),
            ("longitude", self.longitude),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ConfigError(
                    f"LatLng {name} must be a finite real number, got {value!r}"
                )

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "LatLng":
        data, raw = _prepare(data, raw, "LatLng")
        return cls(
            latitude=_as_float(_require(data, "latitude", "LatLng"), "LatLng", "latitude"),
            longitude=_as_float(
                _require(data, "longitude", "LatLng"), "LatLng", "longitude"
            ),
            raw=raw,
        )

    def to_api(self) -> dict[str, float]:
        return {"latitude": float(self.latitude), "longitude": float(self.longitude)}


@dataclass(frozen=True, slots=True)
class AuthorAttribution:
    """Credit for a photo author."""

    display_name: str = ""
    uri: str = ""
    photo_uri: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "AuthorAttribution":
        data, raw = _prepare(data, raw, "AuthorAttribution")
        return cls(
            display_name=_as_str(
                data.get("displayName", ""), "AuthorAttribution", "displayName"
            ),
            uri=_as_str(data.get("uri", ""), "AuthorAttribution", "uri"),
            photo_uri=_as_str(
                data.get("photoUri", ""), "AuthorAttribution", "photoUri"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Attribution:
    """Provider attribution attached to a place."""

    provider: str = ""
    provider_uri: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Attribution":
        data, raw = _prepare(data, raw, "Attribution")
        return cls(
            provider=_as_str(data.get("provider", ""), "Attribution", "provider"),
            provider_uri=_as_str(
                data.get("providerUri", ""), "Attribution", "providerUri"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Photo:
    """A photo attached to a place.

    Pass the ``Photo`` itself to ``Client.place_photo`` or
    ``AsyncClient.place_photo`` to download the image, or pass its
    ``name`` as a string. Passing the Photo with no size arguments
    downloads at the photo native width up to the API cap of 4800.
    """

    name: str
    width_px: int = 0
    height_px: int = 0
    author_attributions: list[AuthorAttribution] = field(default_factory=list)
    #: Link where users can flag a problem with this photo.
    flag_content_uri: Optional[str] = None
    #: Link to view this photo on Google Maps.
    google_maps_uri: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("Photo", "author_attributions", self.author_attributions)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Photo":
        data, raw = _prepare(data, raw, "Photo")
        return cls(
            name=_as_str(data.get("name", ""), "Photo", "name"),
            width_px=_as_int(data.get("widthPx", 0), "Photo", "widthPx"),
            height_px=_as_int(data.get("heightPx", 0), "Photo", "heightPx"),
            author_attributions=[
                AuthorAttribution.from_api(
                    a, _raw_element(raw, "authorAttributions", i, a)
                )
                for i, a in enumerate(
                    _model_list(
                        data.get("authorAttributions", []),
                        "Photo",
                        "authorAttributions",
                    )
                )
            ],
            flag_content_uri=_as_str(
                data.get("flagContentUri"), "Photo", "flagContentUri"
            ),
            google_maps_uri=_as_str(
                data.get("googleMapsUri"), "Photo", "googleMapsUri"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Date:
    """A calendar date. A zero component means it was unset."""

    year: int = 0
    month: int = 0
    day: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Date":
        data, raw = _prepare(data, raw, "Date")
        return cls(
            year=_as_int(data.get("year", 0), "Date", "year"),
            month=_as_int(data.get("month", 0), "Date", "month"),
            day=_as_int(data.get("day", 0), "Date", "day"),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class OpeningPoint:
    """One end of an opening period.

    ``day`` is 0 for Sunday through 6 for Saturday. The first period in a
    list does not start on any fixed day, and period order is independent
    of the weekday description order.
    """

    date: Optional[Date] = None
    truncated: Optional[bool] = None
    day: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "OpeningPoint":
        data, raw = _prepare(data, raw, "OpeningPoint")
        date = data.get("date")
        return cls(
            date=Date.from_api(date, _raw_subtree(raw, "date", date))
            if date
            else None,
            truncated=_optional_bool(data.get("truncated"), "OpeningPoint", "truncated"),
            day=_optional_int(data.get("day"), "OpeningPoint", "day"),
            hour=_optional_int(data.get("hour"), "OpeningPoint", "hour"),
            minute=_optional_int(data.get("minute"), "OpeningPoint", "minute"),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Period:
    """A single open/close span within opening hours."""

    open: Optional[OpeningPoint] = None
    close: Optional[OpeningPoint] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Period":
        data, raw = _prepare(data, raw, "Period")
        open_point = data.get("open")
        close_point = data.get("close")
        return cls(
            open=OpeningPoint.from_api(
                open_point, _raw_subtree(raw, "open", open_point)
            )
            if open_point
            else None,
            close=OpeningPoint.from_api(
                close_point, _raw_subtree(raw, "close", close_point)
            )
            if close_point
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class SpecialDay:
    """A day on which the hours differ from the regular schedule,
    carried inside current opening hours."""

    date: Optional[Date] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "SpecialDay":
        data, raw = _prepare(data, raw, "SpecialDay")
        date = data.get("date")
        return cls(
            date=Date.from_api(date, _raw_subtree(raw, "date", date))
            if date
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class OpeningHours:
    """Regular opening hours of a place."""

    open_now: Optional[bool] = None
    periods: list[Period] = field(default_factory=list)
    weekday_descriptions: list[str] = field(default_factory=list)
    #: When the place next closes, as an unparsed timestamp string.
    #: Present on an open place. Absent (None) when the API sends none.
    next_close_time: Optional[str] = None
    #: When the place next opens, as an unparsed timestamp string.
    next_open_time: Optional[str] = None
    special_days: list[SpecialDay] = field(default_factory=list)
    #: Which kind of secondary hours this entry describes (for example
    #: drive through or delivery hours). Set on the secondary opening
    #: hours lists of a place, absent on regular and current hours.
    secondary_hours_type: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("OpeningHours", "periods", self.periods)
        _reject_bare_string(
            "OpeningHours", "weekday_descriptions", self.weekday_descriptions
        )
        _reject_bare_string("OpeningHours", "special_days", self.special_days)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "OpeningHours":
        data, raw = _prepare(data, raw, "OpeningHours")
        return cls(
            open_now=_optional_bool(data.get("openNow"), "OpeningHours", "openNow"),
            periods=[
                Period.from_api(p, _raw_element(raw, "periods", i, p))
                for i, p in enumerate(
                    _model_list(
                        data.get("periods", []),
                        "OpeningHours",
                        "periods",
                    )
                )
            ],
            weekday_descriptions=_str_list(
                data.get("weekdayDescriptions", []),
                "OpeningHours",
                "weekdayDescriptions",
            ),
            next_close_time=_as_str(
                data.get("nextCloseTime"), "OpeningHours", "nextCloseTime"
            ),
            next_open_time=_as_str(
                data.get("nextOpenTime"), "OpeningHours", "nextOpenTime"
            ),
            special_days=[
                SpecialDay.from_api(d, _raw_element(raw, "specialDays", i, d))
                for i, d in enumerate(
                    _model_list(
                        data.get("specialDays", []),
                        "OpeningHours",
                        "specialDays",
                    )
                )
            ],
            secondary_hours_type=_as_str(
                data.get("secondaryHoursType"),
                "OpeningHours",
                "secondaryHoursType",
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class AddressComponent:
    """One component of a structured address."""

    long_text: str = ""
    short_text: str = ""
    types: list[str] = field(default_factory=list)
    language_code: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("AddressComponent", "types", self.types)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "AddressComponent":
        data, raw = _prepare(data, raw, "AddressComponent")
        return cls(
            long_text=_as_str(
                data.get("longText", ""), "AddressComponent", "longText"
            ),
            short_text=_as_str(
                data.get("shortText", ""), "AddressComponent", "shortText"
            ),
            types=_str_list(data.get("types", []), "AddressComponent", "types"),
            language_code=_as_str(
                data.get("languageCode"), "AddressComponent", "languageCode"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class PlusCode:
    """Plus code location reference for a place."""

    global_code: str = ""
    compound_code: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "PlusCode":
        data, raw = _prepare(data, raw, "PlusCode")
        return cls(
            global_code=_as_str(data.get("globalCode", ""), "PlusCode", "globalCode"),
            compound_code=_as_str(
                data.get("compoundCode"), "PlusCode", "compoundCode"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Viewport:
    """A rectangular area bounded by its low and high corners."""

    low: LatLng
    high: LatLng
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Viewport":
        data, raw = _prepare(data, raw, "Viewport")
        low = _require(data, "low", "Viewport")
        high = _require(data, "high", "Viewport")
        return cls(
            low=LatLng.from_api(low, _raw_subtree(raw, "low", low)),
            high=LatLng.from_api(high, _raw_subtree(raw, "high", high)),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class PostalAddress:
    """A postal address in structured form."""

    region_code: Optional[str] = None
    language_code: Optional[str] = None
    postal_code: Optional[str] = None
    administrative_area: Optional[str] = None
    locality: Optional[str] = None
    address_lines: list[str] = field(default_factory=list)
    sublocality: Optional[str] = None
    organization: Optional[str] = None
    recipients: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("PostalAddress", "address_lines", self.address_lines)
        _reject_bare_string("PostalAddress", "recipients", self.recipients)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "PostalAddress":
        data, raw = _prepare(data, raw, "PostalAddress")
        return cls(
            region_code=_as_str(
                data.get("regionCode"), "PostalAddress", "regionCode"
            ),
            language_code=_as_str(
                data.get("languageCode"), "PostalAddress", "languageCode"
            ),
            postal_code=_as_str(
                data.get("postalCode"), "PostalAddress", "postalCode"
            ),
            administrative_area=_as_str(
                data.get("administrativeArea"),
                "PostalAddress",
                "administrativeArea",
            ),
            locality=_as_str(data.get("locality"), "PostalAddress", "locality"),
            address_lines=_str_list(
                data.get("addressLines", []), "PostalAddress", "addressLines"
            ),
            sublocality=_as_str(
                data.get("sublocality"), "PostalAddress", "sublocality"
            ),
            organization=_as_str(
                data.get("organization"), "PostalAddress", "organization"
            ),
            recipients=_str_list(
                data.get("recipients", []), "PostalAddress", "recipients"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Review:
    """One user review of a place, as carried on Place Details results."""

    name: str = ""
    relative_publish_time_description: str = ""
    text: Optional[LocalizedText] = None
    original_text: Optional[LocalizedText] = None
    rating: Optional[float] = None
    author_attribution: Optional[AuthorAttribution] = None
    #: When the review was published, as an unparsed timestamp string.
    publish_time: Optional[str] = None
    flag_content_uri: Optional[str] = None
    google_maps_uri: Optional[str] = None
    visit_date: Optional[Date] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Review":
        data, raw = _prepare(data, raw, "Review")
        text = data.get("text")
        original = data.get("originalText")
        rating = data.get("rating")
        attribution = data.get("authorAttribution")
        visit = data.get("visitDate")
        return cls(
            name=_as_str(data.get("name", ""), "Review", "name"),
            relative_publish_time_description=_as_str(
                data.get("relativePublishTimeDescription", ""),
                "Review",
                "relativePublishTimeDescription",
            ),
            text=LocalizedText.from_api(text, _raw_subtree(raw, "text", text))
            if text
            else None,
            original_text=LocalizedText.from_api(
                original, _raw_subtree(raw, "originalText", original)
            )
            if original
            else None,
            rating=(
                _as_float(rating, "Review", "rating")
                if rating is not None
                else None
            ),
            author_attribution=(
                AuthorAttribution.from_api(
                    attribution, _raw_subtree(raw, "authorAttribution", attribution)
                )
                if attribution
                else None
            ),
            publish_time=_as_str(
                data.get("publishTime"), "Review", "publishTime"
            ),
            flag_content_uri=_as_str(
                data.get("flagContentUri"), "Review", "flagContentUri"
            ),
            google_maps_uri=_as_str(
                data.get("googleMapsUri"), "Review", "googleMapsUri"
            ),
            visit_date=Date.from_api(visit, _raw_subtree(raw, "visitDate", visit))
            if visit
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class PaymentOptions:
    """Payment methods a place accepts."""

    accepts_credit_cards: Optional[bool] = None
    accepts_debit_cards: Optional[bool] = None
    accepts_cash_only: Optional[bool] = None
    accepts_nfc: Optional[bool] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "PaymentOptions":
        data, raw = _prepare(data, raw, "PaymentOptions")
        return cls(
            accepts_credit_cards=_optional_bool(
                data.get("acceptsCreditCards"), "PaymentOptions", "acceptsCreditCards"
            ),
            accepts_debit_cards=_optional_bool(
                data.get("acceptsDebitCards"), "PaymentOptions", "acceptsDebitCards"
            ),
            accepts_cash_only=_optional_bool(
                data.get("acceptsCashOnly"), "PaymentOptions", "acceptsCashOnly"
            ),
            accepts_nfc=_optional_bool(
                data.get("acceptsNfc"), "PaymentOptions", "acceptsNfc"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class ParkingOptions:
    """Parking options a place offers."""

    free_parking_lot: Optional[bool] = None
    paid_parking_lot: Optional[bool] = None
    free_street_parking: Optional[bool] = None
    paid_street_parking: Optional[bool] = None
    valet_parking: Optional[bool] = None
    free_garage_parking: Optional[bool] = None
    paid_garage_parking: Optional[bool] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "ParkingOptions":
        data, raw = _prepare(data, raw, "ParkingOptions")
        return cls(
            free_parking_lot=_optional_bool(
                data.get("freeParkingLot"), "ParkingOptions", "freeParkingLot"
            ),
            paid_parking_lot=_optional_bool(
                data.get("paidParkingLot"), "ParkingOptions", "paidParkingLot"
            ),
            free_street_parking=_optional_bool(
                data.get("freeStreetParking"), "ParkingOptions", "freeStreetParking"
            ),
            paid_street_parking=_optional_bool(
                data.get("paidStreetParking"), "ParkingOptions", "paidStreetParking"
            ),
            valet_parking=_optional_bool(
                data.get("valetParking"), "ParkingOptions", "valetParking"
            ),
            free_garage_parking=_optional_bool(
                data.get("freeGarageParking"), "ParkingOptions", "freeGarageParking"
            ),
            paid_garage_parking=_optional_bool(
                data.get("paidGarageParking"), "ParkingOptions", "paidGarageParking"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class AccessibilityOptions:
    """Accessibility options a place offers."""

    wheelchair_accessible_parking: Optional[bool] = None
    wheelchair_accessible_entrance: Optional[bool] = None
    wheelchair_accessible_restroom: Optional[bool] = None
    wheelchair_accessible_seating: Optional[bool] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "AccessibilityOptions":
        data, raw = _prepare(data, raw, "AccessibilityOptions")
        return cls(
            wheelchair_accessible_parking=_optional_bool(
                data.get("wheelchairAccessibleParking"),
                "AccessibilityOptions",
                "wheelchairAccessibleParking",
            ),
            wheelchair_accessible_entrance=_optional_bool(
                data.get("wheelchairAccessibleEntrance"),
                "AccessibilityOptions",
                "wheelchairAccessibleEntrance",
            ),
            wheelchair_accessible_restroom=_optional_bool(
                data.get("wheelchairAccessibleRestroom"),
                "AccessibilityOptions",
                "wheelchairAccessibleRestroom",
            ),
            wheelchair_accessible_seating=_optional_bool(
                data.get("wheelchairAccessibleSeating"),
                "AccessibilityOptions",
                "wheelchairAccessibleSeating",
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class TimeZone:
    """The time zone of a place.

    Only the id is typed. The IANA database version the API reports
    beside it is version metadata and stays in ``Place.raw``.
    """

    id: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "TimeZone":
        data, raw = _prepare(data, raw, "TimeZone")
        return cls(
            id=_as_str(data.get("id", ""), "TimeZone", "id"), raw=raw
        )


@dataclass(frozen=True, slots=True)
class GenerativeSummary:
    """An AI generated overview of a place.

    Only the overview text is typed. The flag and disclosure leaves
    beside it stay in ``Place.raw``.
    """

    overview: Optional[LocalizedText] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "GenerativeSummary":
        data, raw = _prepare(data, raw, "GenerativeSummary")
        overview = data.get("overview")
        return cls(
            overview=LocalizedText.from_api(
                overview, _raw_subtree(raw, "overview", overview)
            )
            if overview
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    """An AI generated summary of a place's reviews.

    Only the summary text is typed. The flag, disclosure and reviews
    link leaves beside it stay in ``Place.raw``.
    """

    text: Optional[LocalizedText] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "ReviewSummary":
        data, raw = _prepare(data, raw, "ReviewSummary")
        text = data.get("text")
        return cls(
            text=LocalizedText.from_api(text, _raw_subtree(raw, "text", text))
            if text
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class ConsumerAlert:
    """A consumer alert about a place, with its headline and language.

    The detail blocks under the headline stay in ``Place.raw``. The
    overview is a plain string here, not a LocalizedText, because the
    wire carries the language as the sibling field below.
    """

    overview: str = ""
    language_code: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "ConsumerAlert":
        data, raw = _prepare(data, raw, "ConsumerAlert")
        return cls(
            overview=_as_str(data.get("overview", ""), "ConsumerAlert", "overview"),
            language_code=_as_str(
                data.get("languageCode"), "ConsumerAlert", "languageCode"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class GoogleMapsLinks:
    """The Google Maps links for a place, beyond the single maps URI
    carried on the place itself."""

    directions_uri: Optional[str] = None
    place_uri: Optional[str] = None
    write_a_review_uri: Optional[str] = None
    reviews_uri: Optional[str] = None
    photos_uri: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "GoogleMapsLinks":
        data, raw = _prepare(data, raw, "GoogleMapsLinks")
        return cls(
            directions_uri=_as_str(
                data.get("directionsUri"), "GoogleMapsLinks", "directionsUri"
            ),
            place_uri=_as_str(
                data.get("placeUri"), "GoogleMapsLinks", "placeUri"
            ),
            write_a_review_uri=_as_str(
                data.get("writeAReviewUri"),
                "GoogleMapsLinks",
                "writeAReviewUri",
            ),
            reviews_uri=_as_str(
                data.get("reviewsUri"), "GoogleMapsLinks", "reviewsUri"
            ),
            photos_uri=_as_str(
                data.get("photosUri"), "GoogleMapsLinks", "photosUri"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Money:
    """An amount of money in a single currency.

    Units are an int64 the wire carries as a JSON string, decoded to
    an int here, and nanos is the sub unit component as a plain
    number.
    """

    currency_code: str = ""
    units: int = 0
    nanos: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Money":
        data, raw = _prepare(data, raw, "Money")
        return cls(
            currency_code=_as_str(
                data.get("currencyCode", ""), "Money", "currencyCode"
            ),
            units=_as_int(data.get("units", 0), "Money", "units"),
            nanos=_as_int(data.get("nanos", 0), "Money", "nanos"),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class PriceRange:
    """The price range of a place.

    An absent end price is an open ended range and reads None, never
    a zero Money.
    """

    start_price: Optional[Money] = None
    end_price: Optional[Money] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "PriceRange":
        data, raw = _prepare(data, raw, "PriceRange")
        start = data.get("startPrice")
        end = data.get("endPrice")
        return cls(
            start_price=Money.from_api(start, _raw_subtree(raw, "startPrice", start))
            if start
            else None,
            end_price=Money.from_api(end, _raw_subtree(raw, "endPrice", end))
            if end
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class ConnectorAggregation:
    """One connector type inside an EV charging summary.

    ``type`` is the API's own field name and is kept as is. The
    availability timestamp stays an unparsed string, like every other
    timestamp in the model layer.
    """

    type: str = ""
    max_charge_rate_kw: Optional[float] = None
    count: Optional[int] = None
    available_count: Optional[int] = None
    out_of_service_count: Optional[int] = None
    availability_last_update_time: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "ConnectorAggregation":
        data, raw = _prepare(data, raw, "ConnectorAggregation")
        rate = data.get("maxChargeRateKw")
        return cls(
            type=_as_str(data.get("type", ""), "ConnectorAggregation", "type"),
            max_charge_rate_kw=(
                _as_float(rate, "ConnectorAggregation", "maxChargeRateKw")
                if rate is not None
                else None
            ),
            count=_optional_int(
                data.get("count"), "ConnectorAggregation", "count"
            ),
            available_count=_optional_int(
                data.get("availableCount"),
                "ConnectorAggregation",
                "availableCount",
            ),
            out_of_service_count=_optional_int(
                data.get("outOfServiceCount"),
                "ConnectorAggregation",
                "outOfServiceCount",
            ),
            availability_last_update_time=_as_str(
                data.get("availabilityLastUpdateTime"),
                "ConnectorAggregation",
                "availabilityLastUpdateTime",
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class EvChargeOptions:
    """The electric vehicle charging summary of a place."""

    connector_count: Optional[int] = None
    connector_aggregation: list[ConnectorAggregation] = field(
        default_factory=list
    )
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string(
            "EvChargeOptions",
            "connector_aggregation",
            self.connector_aggregation,
        )

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "EvChargeOptions":
        data, raw = _prepare(data, raw, "EvChargeOptions")
        return cls(
            connector_count=_optional_int(
                data.get("connectorCount"), "EvChargeOptions", "connectorCount"
            ),
            connector_aggregation=[
                ConnectorAggregation.from_api(
                    a, _raw_element(raw, "connectorAggregation", i, a)
                )
                for i, a in enumerate(
                    _model_list(
                        data.get("connectorAggregation", []),
                        "EvChargeOptions",
                        "connectorAggregation",
                    )
                )
            ],
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Landmark:
    """A nearby landmark inside an address descriptor."""

    name: str = ""
    place_id: str = ""
    display_name: Optional[LocalizedText] = None
    types: list[str] = field(default_factory=list)
    spatial_relationship: Optional[str] = None
    straight_line_distance_meters: Optional[float] = None
    travel_distance_meters: Optional[float] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("Landmark", "types", self.types)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Landmark":
        data, raw = _prepare(data, raw, "Landmark")
        display = data.get("displayName")
        straight = data.get("straightLineDistanceMeters")
        travel = data.get("travelDistanceMeters")
        return cls(
            name=_as_str(data.get("name", ""), "Landmark", "name"),
            place_id=_as_str(data.get("placeId", ""), "Landmark", "placeId"),
            display_name=LocalizedText.from_api(
                display, _raw_subtree(raw, "displayName", display)
            )
            if display
            else None,
            types=_str_list(data.get("types", []), "Landmark", "types"),
            spatial_relationship=_as_str(
                data.get("spatialRelationship"),
                "Landmark",
                "spatialRelationship",
            ),
            straight_line_distance_meters=(
                _as_float(straight, "Landmark", "straightLineDistanceMeters")
                if straight is not None
                else None
            ),
            travel_distance_meters=(
                _as_float(travel, "Landmark", "travelDistanceMeters")
                if travel is not None
                else None
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Area:
    """An area containing an address, inside an address descriptor."""

    name: str = ""
    place_id: str = ""
    display_name: Optional[LocalizedText] = None
    containment: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Area":
        data, raw = _prepare(data, raw, "Area")
        display = data.get("displayName")
        return cls(
            name=_as_str(data.get("name", ""), "Area", "name"),
            place_id=_as_str(data.get("placeId", ""), "Area", "placeId"),
            display_name=LocalizedText.from_api(
                display, _raw_subtree(raw, "displayName", display)
            )
            if display
            else None,
            containment=_as_str(data.get("containment"), "Area", "containment"),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class AddressDescriptor:
    """Landmarks and areas describing where an address sits."""

    landmarks: list[Landmark] = field(default_factory=list)
    areas: list[Area] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("AddressDescriptor", "landmarks", self.landmarks)
        _reject_bare_string("AddressDescriptor", "areas", self.areas)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "AddressDescriptor":
        data, raw = _prepare(data, raw, "AddressDescriptor")
        return cls(
            landmarks=[
                Landmark.from_api(
                    landmark, _raw_element(raw, "landmarks", i, landmark)
                )
                for i, landmark in enumerate(
                    _model_list(
                        data.get("landmarks", []),
                        "AddressDescriptor",
                        "landmarks",
                    )
                )
            ],
            areas=[
                Area.from_api(area, _raw_element(raw, "areas", i, area))
                for i, area in enumerate(
                    _model_list(
                        data.get("areas", []),
                        "AddressDescriptor",
                        "areas",
                    )
                )
            ],
            raw=raw,
        )


# Wire fidelity note (T19): public field names mirror the API's own
# names even where they shadow builtins (Place.id above all, and the
# various types fields). Renaming them would break the one-to-one
# mapping between model attributes and wire fields that callers rely
# on when reading raw payloads, so the shadowing is kept deliberately
# and no rename is planned.
@dataclass(frozen=True, slots=True)
class Place:
    """A single place, from search results or Place Details."""

    id: str
    name: str = ""
    display_name: Optional[LocalizedText] = None
    formatted_address: Optional[str] = None
    short_formatted_address: Optional[str] = None
    location: Optional[LatLng] = None
    types: list[str] = field(default_factory=list)
    primary_type: Optional[str] = None
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    price_level: Optional[str] = None
    business_status: Optional[str] = None
    national_phone_number: Optional[str] = None
    international_phone_number: Optional[str] = None
    website_uri: Optional[str] = None
    google_maps_uri: Optional[str] = None
    opening_hours: Optional[OpeningHours] = None
    current_opening_hours: Optional[OpeningHours] = None
    current_secondary_opening_hours: list[OpeningHours] = field(
        default_factory=list
    )
    regular_secondary_opening_hours: list[OpeningHours] = field(
        default_factory=list
    )
    address_components: list[AddressComponent] = field(default_factory=list)
    plus_code: Optional[PlusCode] = None
    viewport: Optional[Viewport] = None
    postal_address: Optional[PostalAddress] = None
    adr_format_address: Optional[str] = None
    primary_type_display_name: Optional[LocalizedText] = None
    google_maps_type_label: Optional[LocalizedText] = None
    editorial_summary: Optional[LocalizedText] = None
    icon_mask_base_uri: Optional[str] = None
    icon_background_color: Optional[str] = None
    opening_date: Optional[Date] = None
    utc_offset_minutes: Optional[int] = None
    pure_service_area_business: Optional[bool] = None
    moved_place: Optional[str] = None
    moved_place_id: Optional[str] = None
    photos: list[Photo] = field(default_factory=list)
    attributions: list[Attribution] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    takeout: Optional[bool] = None
    delivery: Optional[bool] = None
    dine_in: Optional[bool] = None
    curbside_pickup: Optional[bool] = None
    reservable: Optional[bool] = None
    serves_breakfast: Optional[bool] = None
    serves_lunch: Optional[bool] = None
    serves_dinner: Optional[bool] = None
    serves_beer: Optional[bool] = None
    serves_wine: Optional[bool] = None
    serves_brunch: Optional[bool] = None
    serves_vegetarian_food: Optional[bool] = None
    outdoor_seating: Optional[bool] = None
    live_music: Optional[bool] = None
    menu_for_children: Optional[bool] = None
    serves_cocktails: Optional[bool] = None
    serves_dessert: Optional[bool] = None
    serves_coffee: Optional[bool] = None
    good_for_children: Optional[bool] = None
    allows_dogs: Optional[bool] = None
    restroom: Optional[bool] = None
    good_for_groups: Optional[bool] = None
    good_for_watching_sports: Optional[bool] = None
    payment_options: Optional[PaymentOptions] = None
    parking_options: Optional[ParkingOptions] = None
    accessibility_options: Optional[AccessibilityOptions] = None
    time_zone: Optional[TimeZone] = None
    generative_summary: Optional[GenerativeSummary] = None
    review_summary: Optional[ReviewSummary] = None
    consumer_alert: Optional[ConsumerAlert] = None
    google_maps_links: Optional[GoogleMapsLinks] = None
    price_range: Optional[PriceRange] = None
    ev_charge_options: Optional[EvChargeOptions] = None
    address_descriptor: Optional[AddressDescriptor] = None
    #: The full response payload for this place, including any fields this
    #: client version does not model yet. A deep copy of the payload, so
    #: it shares no mutable state with the caller's dict. Excluded from
    #: repr and equality, which are about the modelled fields.
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("Place", "types", self.types)
        _reject_bare_string("Place", "address_components", self.address_components)
        _reject_bare_string("Place", "photos", self.photos)
        _reject_bare_string("Place", "attributions", self.attributions)
        _reject_bare_string(
            "Place",
            "current_secondary_opening_hours",
            self.current_secondary_opening_hours,
        )
        _reject_bare_string(
            "Place",
            "regular_secondary_opening_hours",
            self.regular_secondary_opening_hours,
        )
        _reject_bare_string("Place", "reviews", self.reviews)

    @property
    def display_text(self) -> Optional[str]:
        """The display name as a plain string, when present."""
        return self.display_name.text if self.display_name else None

    @property
    def regular_opening_hours(self) -> Optional[OpeningHours]:
        """Alias for ``opening_hours`` under its wire name,
        ``regularOpeningHours``."""
        return self.opening_hours

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Place":
        data, raw = _prepare(data, raw, "Place")
        display = data.get("displayName")
        location = data.get("location")
        hours = data.get("regularOpeningHours")
        current_hours = data.get("currentOpeningHours")
        plus_code = data.get("plusCode")
        viewport = data.get("viewport")
        postal = data.get("postalAddress")
        type_display = data.get("primaryTypeDisplayName")
        type_label = data.get("googleMapsTypeLabel")
        summary = data.get("editorialSummary")
        opening = data.get("openingDate")
        payment = data.get("paymentOptions")
        parking = data.get("parkingOptions")
        accessibility = data.get("accessibilityOptions")
        time_zone = data.get("timeZone")
        generative = data.get("generativeSummary")
        review_summary = data.get("reviewSummary")
        alert = data.get("consumerAlert")
        links = data.get("googleMapsLinks")
        price_range = data.get("priceRange")
        ev = data.get("evChargeOptions")
        descriptor = data.get("addressDescriptor")
        name_value = _as_str(data.get("name", ""), "Place", "name")
        place_id = _as_str(data.get("id"), "Place", "id") or (
            name_value.removeprefix("places/")
            if isinstance(name_value, str)
            else ""
        )
        if not data:
            # An empty payload is a truncated or wrong response, not a
            # place; a payload that merely lacks an id (a field mask
            # that did not request one) still decodes, with id "".
            raise DecodeError(
                "Place payload is empty; refusing to fabricate an "
                "empty place from it"
            )
        rating = data.get("rating")
        user_rating_count = data.get("userRatingCount")
        return cls(
            id=place_id,
            name=name_value,
            display_name=LocalizedText.from_api(
                display, _raw_subtree(raw, "displayName", display)
            )
            if display
            else None,
            formatted_address=_as_str(
                data.get("formattedAddress"), "Place", "formattedAddress"
            ),
            short_formatted_address=_as_str(
                data.get("shortFormattedAddress"),
                "Place",
                "shortFormattedAddress",
            ),
            location=LatLng.from_api(
                location, _raw_subtree(raw, "location", location)
            )
            if location
            else None,
            types=_str_list(data.get("types", []), "Place", "types"),
            primary_type=_as_str(
                data.get("primaryType"), "Place", "primaryType"
            ),
            rating=(
                _as_float(rating, "Place", "rating") if rating is not None else None
            ),
            user_rating_count=(
                _as_int(user_rating_count, "Place", "userRatingCount")
                if user_rating_count is not None
                else None
            ),
            price_level=_as_str(data.get("priceLevel"), "Place", "priceLevel"),
            business_status=_as_str(
                data.get("businessStatus"), "Place", "businessStatus"
            ),
            national_phone_number=_as_str(
                data.get("nationalPhoneNumber"), "Place", "nationalPhoneNumber"
            ),
            international_phone_number=_as_str(
                data.get("internationalPhoneNumber"),
                "Place",
                "internationalPhoneNumber",
            ),
            website_uri=_as_str(data.get("websiteUri"), "Place", "websiteUri"),
            google_maps_uri=_as_str(
                data.get("googleMapsUri"), "Place", "googleMapsUri"
            ),
            opening_hours=OpeningHours.from_api(
                hours, _raw_subtree(raw, "regularOpeningHours", hours)
            )
            if hours
            else None,
            current_opening_hours=(
                OpeningHours.from_api(
                    current_hours,
                    _raw_subtree(raw, "currentOpeningHours", current_hours),
                )
                if current_hours
                else None
            ),
            current_secondary_opening_hours=[
                OpeningHours.from_api(
                    h, _raw_element(raw, "currentSecondaryOpeningHours", i, h)
                )
                for i, h in enumerate(
                    _model_list(
                        data.get("currentSecondaryOpeningHours", []),
                        "Place",
                        "currentSecondaryOpeningHours",
                    )
                )
            ],
            regular_secondary_opening_hours=[
                OpeningHours.from_api(
                    h, _raw_element(raw, "regularSecondaryOpeningHours", i, h)
                )
                for i, h in enumerate(
                    _model_list(
                        data.get("regularSecondaryOpeningHours", []),
                        "Place",
                        "regularSecondaryOpeningHours",
                    )
                )
            ],
            address_components=[
                AddressComponent.from_api(
                    c, _raw_element(raw, "addressComponents", i, c)
                )
                for i, c in enumerate(
                    _model_list(
                        data.get("addressComponents", []),
                        "Place",
                        "addressComponents",
                    )
                )
            ],
            plus_code=PlusCode.from_api(
                plus_code, _raw_subtree(raw, "plusCode", plus_code)
            )
            if plus_code
            else None,
            viewport=Viewport.from_api(
                viewport, _raw_subtree(raw, "viewport", viewport)
            )
            if viewport
            else None,
            postal_address=PostalAddress.from_api(
                postal, _raw_subtree(raw, "postalAddress", postal)
            )
            if postal
            else None,
            adr_format_address=_as_str(
                data.get("adrFormatAddress"), "Place", "adrFormatAddress"
            ),
            primary_type_display_name=(
                LocalizedText.from_api(
                    type_display,
                    _raw_subtree(raw, "primaryTypeDisplayName", type_display),
                )
                if type_display
                else None
            ),
            google_maps_type_label=(
                LocalizedText.from_api(
                    type_label,
                    _raw_subtree(raw, "googleMapsTypeLabel", type_label),
                )
                if type_label
                else None
            ),
            editorial_summary=(
                LocalizedText.from_api(
                    summary, _raw_subtree(raw, "editorialSummary", summary)
                )
                if summary
                else None
            ),
            icon_mask_base_uri=_as_str(
                data.get("iconMaskBaseUri"), "Place", "iconMaskBaseUri"
            ),
            icon_background_color=_as_str(
                data.get("iconBackgroundColor"), "Place", "iconBackgroundColor"
            ),
            opening_date=Date.from_api(
                opening, _raw_subtree(raw, "openingDate", opening)
            )
            if opening
            else None,
            utc_offset_minutes=_optional_int(
                data.get("utcOffsetMinutes"), "Place", "utcOffsetMinutes"
            ),
            pure_service_area_business=_optional_bool(
                data.get("pureServiceAreaBusiness"),
                "Place",
                "pureServiceAreaBusiness",
            ),
            moved_place=_as_str(data.get("movedPlace"), "Place", "movedPlace"),
            moved_place_id=_as_str(
                data.get("movedPlaceId"), "Place", "movedPlaceId"
            ),
            photos=[
                Photo.from_api(p, _raw_element(raw, "photos", i, p))
                for i, p in enumerate(
                    _model_list(
                        data.get("photos", []),
                        "Place",
                        "photos",
                    )
                )
            ],
            attributions=[
                Attribution.from_api(a, _raw_element(raw, "attributions", i, a))
                for i, a in enumerate(
                    _model_list(
                        data.get("attributions", []),
                        "Place",
                        "attributions",
                    )
                )
            ],
            reviews=[
                Review.from_api(r, _raw_element(raw, "reviews", i, r))
                for i, r in enumerate(
                    _model_list(
                        data.get("reviews", []),
                        "Place",
                        "reviews",
                    )
                )
            ],
            takeout=_optional_bool(data.get("takeout"), "Place", "takeout"),
            delivery=_optional_bool(data.get("delivery"), "Place", "delivery"),
            dine_in=_optional_bool(data.get("dineIn"), "Place", "dineIn"),
            curbside_pickup=_optional_bool(
                data.get("curbsidePickup"), "Place", "curbsidePickup"
            ),
            reservable=_optional_bool(
                data.get("reservable"), "Place", "reservable"
            ),
            serves_breakfast=_optional_bool(
                data.get("servesBreakfast"), "Place", "servesBreakfast"
            ),
            serves_lunch=_optional_bool(
                data.get("servesLunch"), "Place", "servesLunch"
            ),
            serves_dinner=_optional_bool(
                data.get("servesDinner"), "Place", "servesDinner"
            ),
            serves_beer=_optional_bool(
                data.get("servesBeer"), "Place", "servesBeer"
            ),
            serves_wine=_optional_bool(
                data.get("servesWine"), "Place", "servesWine"
            ),
            serves_brunch=_optional_bool(
                data.get("servesBrunch"), "Place", "servesBrunch"
            ),
            serves_vegetarian_food=_optional_bool(
                data.get("servesVegetarianFood"), "Place", "servesVegetarianFood"
            ),
            outdoor_seating=_optional_bool(
                data.get("outdoorSeating"), "Place", "outdoorSeating"
            ),
            live_music=_optional_bool(
                data.get("liveMusic"), "Place", "liveMusic"
            ),
            menu_for_children=_optional_bool(
                data.get("menuForChildren"), "Place", "menuForChildren"
            ),
            serves_cocktails=_optional_bool(
                data.get("servesCocktails"), "Place", "servesCocktails"
            ),
            serves_dessert=_optional_bool(
                data.get("servesDessert"), "Place", "servesDessert"
            ),
            serves_coffee=_optional_bool(
                data.get("servesCoffee"), "Place", "servesCoffee"
            ),
            good_for_children=_optional_bool(
                data.get("goodForChildren"), "Place", "goodForChildren"
            ),
            allows_dogs=_optional_bool(
                data.get("allowsDogs"), "Place", "allowsDogs"
            ),
            restroom=_optional_bool(data.get("restroom"), "Place", "restroom"),
            good_for_groups=_optional_bool(
                data.get("goodForGroups"), "Place", "goodForGroups"
            ),
            good_for_watching_sports=_optional_bool(
                data.get("goodForWatchingSports"), "Place", "goodForWatchingSports"
            ),
            payment_options=(
                PaymentOptions.from_api(
                    payment, _raw_subtree(raw, "paymentOptions", payment)
                )
                if payment
                else None
            ),
            parking_options=(
                ParkingOptions.from_api(
                    parking, _raw_subtree(raw, "parkingOptions", parking)
                )
                if parking
                else None
            ),
            accessibility_options=(
                AccessibilityOptions.from_api(
                    accessibility,
                    _raw_subtree(raw, "accessibilityOptions", accessibility),
                )
                if accessibility
                else None
            ),
            time_zone=TimeZone.from_api(
                time_zone, _raw_subtree(raw, "timeZone", time_zone)
            )
            if time_zone
            else None,
            generative_summary=(
                GenerativeSummary.from_api(
                    generative,
                    _raw_subtree(raw, "generativeSummary", generative),
                )
                if generative
                else None
            ),
            review_summary=(
                ReviewSummary.from_api(
                    review_summary,
                    _raw_subtree(raw, "reviewSummary", review_summary),
                )
                if review_summary
                else None
            ),
            consumer_alert=ConsumerAlert.from_api(
                alert, _raw_subtree(raw, "consumerAlert", alert)
            )
            if alert
            else None,
            google_maps_links=(
                GoogleMapsLinks.from_api(
                    links, _raw_subtree(raw, "googleMapsLinks", links)
                )
                if links
                else None
            ),
            price_range=PriceRange.from_api(
                price_range, _raw_subtree(raw, "priceRange", price_range)
            )
            if price_range
            else None,
            ev_charge_options=EvChargeOptions.from_api(
                ev, _raw_subtree(raw, "evChargeOptions", ev)
            )
            if ev
            else None,
            address_descriptor=(
                AddressDescriptor.from_api(
                    descriptor,
                    _raw_subtree(raw, "addressDescriptor", descriptor),
                )
                if descriptor
                else None
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Leg:
    """One leg of a routing summary.

    The duration stays the wire string and is never parsed into an
    interval, because the string carries routing semantics of its own.
    """

    duration: str = ""
    distance_meters: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Leg":
        data, raw = _prepare(data, raw, "Leg")
        return cls(
            duration=_as_str(data.get("duration", ""), "Leg", "duration"),
            distance_meters=_optional_int(
                data.get("distanceMeters"), "Leg", "distanceMeters"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class RoutingSummary:
    """A routing summary for a search result."""

    legs: list[Leg] = field(default_factory=list)
    directions_uri: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("RoutingSummary", "legs", self.legs)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "RoutingSummary":
        data, raw = _prepare(data, raw, "RoutingSummary")
        return cls(
            legs=[
                Leg.from_api(leg, _raw_element(raw, "legs", i, leg))
                for i, leg in enumerate(
                    _model_list(
                        data.get("legs", []),
                        "RoutingSummary",
                        "legs",
                    )
                )
            ],
            directions_uri=_as_str(
                data.get("directionsUri"), "RoutingSummary", "directionsUri"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class TextSearchResult:
    """One page of Text Search results."""

    places: list[Place]
    #: Pass back as ``page_token`` to fetch the next page, when present.
    next_page_token: Optional[str] = None
    #: Link to run the same query on Google Maps. Present only when the
    #: ``searchUri`` field was requested through the field mask.
    search_uri: Optional[str] = None
    #: Routing summaries, one per place, when requested through the field
    #: mask and routing parameters were supplied. Typed since round 6.
    #: The untyped dict form stays reachable through ``raw``.
    routing_summaries: list[RoutingSummary] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("TextSearchResult", "places", self.places)
        _reject_bare_string(
            "TextSearchResult", "routing_summaries", self.routing_summaries
        )

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "TextSearchResult":
        data, raw = _prepare(data, raw, "TextSearchResult")
        return cls(
            places=[
                Place.from_api(p, _raw_element(raw, "places", i, p))
                for i, p in enumerate(
                    _model_list(
                        data.get("places", []),
                        "TextSearchResult",
                        "places",
                    )
                )
            ],
            next_page_token=_as_str(
                data.get("nextPageToken"), "TextSearchResult", "nextPageToken"
            ),
            search_uri=_as_str(
                data.get("searchUri"), "TextSearchResult", "searchUri"
            ),
            routing_summaries=[
                RoutingSummary.from_api(
                    s, _raw_element(raw, "routingSummaries", i, s)
                )
                for i, s in enumerate(
                    _model_list(
                        data.get("routingSummaries", []),
                        "TextSearchResult",
                        "routingSummaries",
                    )
                )
            ],
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class NearbySearchResult:
    """Nearby Search results (the API returns at most one page).

    There is deliberately no ``next_page_token`` here. The Places API
    does not paginate Nearby Search; the Rust response type is shared
    with Text Search, which is the only reason the field exists at the
    wire layer at all.
    """

    places: list[Place]
    #: Routing summaries, one per place, when requested through the field
    #: mask and routing parameters were supplied.
    routing_summaries: list[RoutingSummary] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("NearbySearchResult", "places", self.places)
        _reject_bare_string(
            "NearbySearchResult", "routing_summaries", self.routing_summaries
        )

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "NearbySearchResult":
        data, raw = _prepare(data, raw, "NearbySearchResult")
        return cls(
            places=[
                Place.from_api(p, _raw_element(raw, "places", i, p))
                for i, p in enumerate(
                    _model_list(
                        data.get("places", []),
                        "NearbySearchResult",
                        "places",
                    )
                )
            ],
            routing_summaries=[
                RoutingSummary.from_api(
                    s, _raw_element(raw, "routingSummaries", i, s)
                )
                for i, s in enumerate(
                    _model_list(
                        data.get("routingSummaries", []),
                        "NearbySearchResult",
                        "routingSummaries",
                    )
                )
            ],
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class StringMatch:
    """A substring match range inside an autocomplete text."""

    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "StringMatch":
        data, raw = _prepare(data, raw, "StringMatch")
        return cls(
            start_offset=_optional_int(data.get("startOffset"), "StringMatch", "startOffset"),
            end_offset=_optional_int(data.get("endOffset"), "StringMatch", "endOffset"),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class FormattedText:
    """Text with match ranges, as returned by Autocomplete."""

    text: str = ""
    matches: list[StringMatch] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("FormattedText", "matches", self.matches)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "FormattedText":
        data, raw = _prepare(data, raw, "FormattedText")
        return cls(
            text=_as_str(data.get("text", ""), "FormattedText", "text"),
            matches=[
                StringMatch.from_api(m, _raw_element(raw, "matches", i, m))
                for i, m in enumerate(
                    _model_list(
                        data.get("matches", []),
                        "FormattedText",
                        "matches",
                    )
                )
            ],
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class PlacePrediction:
    """A predicted place from Autocomplete."""

    place_id: str
    #: Resource name of the suggested place, for example
    #: ``places/ChIJrTLr-GyuEmsRBfy61i59si0``.
    place: str = ""
    text: Optional[FormattedText] = None
    main_text: Optional[FormattedText] = None
    secondary_text: Optional[FormattedText] = None
    types: list[str] = field(default_factory=list)
    distance_meters: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("PlacePrediction", "types", self.types)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "PlacePrediction":
        data, raw = _prepare(data, raw, "PlacePrediction")
        text = data.get("text")
        structured = data.get("structuredFormat") or {}
        if not isinstance(structured, dict):
            raise DecodeError(
                "PlacePrediction payload key 'structuredFormat' is "
                f"not an object: {structured!r}"
            )
        raw_structured = _raw_subtree(raw, "structuredFormat", structured)
        main = structured.get("mainText")
        secondary = structured.get("secondaryText")
        return cls(
            place_id=_as_str(data.get("placeId", ""), "PlacePrediction", "placeId"),
            place=_as_str(data.get("place", ""), "PlacePrediction", "place"),
            text=FormattedText.from_api(text, _raw_subtree(raw, "text", text))
            if text
            else None,
            main_text=FormattedText.from_api(
                main, _raw_subtree(raw_structured, "mainText", main)
            )
            if main
            else None,
            secondary_text=FormattedText.from_api(
                secondary,
                _raw_subtree(raw_structured, "secondaryText", secondary),
            )
            if secondary
            else None,
            types=_str_list(data.get("types", []), "PlacePrediction", "types"),
            distance_meters=_optional_int(
                data.get("distanceMeters"), "PlacePrediction", "distanceMeters"
            ),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class QueryPrediction:
    """A predicted search query from Autocomplete, returned when
    ``include_query_predictions`` is set."""

    text: Optional[FormattedText] = None
    main_text: Optional[FormattedText] = None
    secondary_text: Optional[FormattedText] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "QueryPrediction":
        data, raw = _prepare(data, raw, "QueryPrediction")
        text = data.get("text")
        structured = data.get("structuredFormat") or {}
        if not isinstance(structured, dict):
            raise DecodeError(
                "QueryPrediction payload key 'structuredFormat' is "
                f"not an object: {structured!r}"
            )
        raw_structured = _raw_subtree(raw, "structuredFormat", structured)
        main = structured.get("mainText")
        secondary = structured.get("secondaryText")
        return cls(
            text=FormattedText.from_api(text, _raw_subtree(raw, "text", text))
            if text
            else None,
            main_text=FormattedText.from_api(
                main, _raw_subtree(raw_structured, "mainText", main)
            )
            if main
            else None,
            secondary_text=FormattedText.from_api(
                secondary,
                _raw_subtree(raw_structured, "secondaryText", secondary),
            )
            if secondary
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class Suggestion:
    """One autocomplete suggestion.

    ``place_prediction`` is set for place suggestions and
    ``query_prediction`` for query suggestions; the full payload is
    preserved on ``raw`` either way.
    """

    place_prediction: Optional[PlacePrediction] = None
    query_prediction: Optional[QueryPrediction] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "Suggestion":
        data, raw = _prepare(data, raw, "Suggestion")
        prediction = data.get("placePrediction")
        query = data.get("queryPrediction")
        return cls(
            place_prediction=PlacePrediction.from_api(
                prediction, _raw_subtree(raw, "placePrediction", prediction)
            )
            if prediction
            else None,
            query_prediction=QueryPrediction.from_api(
                query, _raw_subtree(raw, "queryPrediction", query)
            )
            if query
            else None,
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class AutocompleteResult:
    """Autocomplete suggestions for one input."""

    suggestions: list[Suggestion]
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _reject_bare_string("AutocompleteResult", "suggestions", self.suggestions)

    @property
    def place_predictions(self) -> list[PlacePrediction]:
        """Just the place predictions, skipping any other suggestion kinds."""
        return [s.place_prediction for s in self.suggestions if s.place_prediction]

    @property
    def query_predictions(self) -> list[QueryPrediction]:
        """Just the query predictions, skipping any other suggestion kinds."""
        return [s.query_prediction for s in self.suggestions if s.query_prediction]

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "AutocompleteResult":
        data, raw = _prepare(data, raw, "AutocompleteResult")
        return cls(
            suggestions=[
                Suggestion.from_api(s, _raw_element(raw, "suggestions", i, s))
                for i, s in enumerate(
                    _model_list(
                        data.get("suggestions", []),
                        "AutocompleteResult",
                        "suggestions",
                    )
                )
            ],
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class PhotoMedia:
    """Downloaded photo bytes from the photo media endpoint."""

    #: The image bytes; excluded from repr so printing a result does
    #: not dump the payload.
    content: bytes = field(repr=False)
    content_type: Optional[str] = None

    def save(self, path: str | Path) -> Path:
        """Write the photo to ``path`` and return the path.

        An existing file at ``path`` is overwritten. The parent
        directory must already exist.
        """
        target = Path(path)
        target.write_bytes(self.content)
        return target


@dataclass(frozen=True, slots=True)
class PhotoUriResult:
    """The photo media endpoint's JSON form, returned on request instead
    of following its redirect.

    Returned by ``place_photo`` when ``skip_http_redirect`` is set.
    ``photo_uri`` is short lived. Render or fetch it promptly. The
    full JSON form the endpoint returned is preserved on ``raw``,
    including any fields this client version does not model yet.
    """

    #: The signed photo URI; excluded from repr so printing a result
    #: does not write the short lived bearer capability into a log
    #: (R18-A7). The bytes model takes the same care with its content.
    photo_uri: str = field(repr=False)
    name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(
        cls, data: dict[str, Any], raw: Optional[dict[str, Any]] = None
    ) -> "PhotoUriResult":
        data, raw = _prepare(data, raw, "PhotoUriResult")
        return cls(
            photo_uri=_as_str(data.get("photoUri", ""), "PhotoUriResult", "photoUri"),
            name=_as_str(data.get("name", ""), "PhotoUriResult", "name"),
            raw=raw,
        )
