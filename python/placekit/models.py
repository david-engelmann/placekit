"""Typed response models for placekit.

Responses arrive as dataclasses with attribute access, never raw dicts.
Fields this client version does not model yet are preserved verbatim
on ``raw``. Every model object that decodes from a JSON object
preserves that object on its ``raw``, so nothing the API returns is
silently lost at any level of the tree. ``raw`` is a deep copy
sharing no mutable state with any other copy. ``PhotoMedia`` is the
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
the narrower question of what the response carried, because a
wire name is a key in ``raw`` exactly when the response carried
that field. No attribute raises for being unreturned, and the
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
payload it came from, so the caller's dict, a result's raw and a
child model's raw share no mutable state.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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
    except (TypeError, ValueError) as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not a number: {value!r}"
        ) from exc


def _as_int(value: Any, model: str, key: str) -> int:
    if isinstance(value, bool):
        raise DecodeError(f"{model} payload key {key!r} is not an integer: {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not an integer: {value!r}"
        ) from exc


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
    shredded into one-character items."""
    if isinstance(value, (str, bytes)):
        raise DecodeError(
            f"{model} payload key {key!r} is a single string, not a list"
        )
    try:
        return list(value)
    except TypeError as exc:
        raise DecodeError(
            f"{model} payload key {key!r} is not a list: {value!r}"
        ) from exc


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
    def from_api(cls, data: dict[str, Any]) -> "LocalizedText":
        data = copy.deepcopy(data)
        return cls(
            text=data.get("text", ""), language_code=data.get("languageCode"), raw=data
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
    def from_api(cls, data: dict[str, Any]) -> "LatLng":
        data = copy.deepcopy(data)
        return cls(
            latitude=_as_float(_require(data, "latitude", "LatLng"), "LatLng", "latitude"),
            longitude=_as_float(
                _require(data, "longitude", "LatLng"), "LatLng", "longitude"
            ),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "AuthorAttribution":
        data = copy.deepcopy(data)
        return cls(
            display_name=data.get("displayName", ""),
            uri=data.get("uri", ""),
            photo_uri=data.get("photoUri", ""),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class Attribution:
    """Provider attribution attached to a place."""

    provider: str = ""
    provider_uri: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Attribution":
        data = copy.deepcopy(data)
        return cls(
            provider=data.get("provider", ""),
            provider_uri=data.get("providerUri", ""),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Photo":
        data = copy.deepcopy(data)
        return cls(
            name=data.get("name", ""),
            width_px=_as_int(data.get("widthPx", 0), "Photo", "widthPx"),
            height_px=_as_int(data.get("heightPx", 0), "Photo", "heightPx"),
            author_attributions=[
                AuthorAttribution.from_api(a) for a in data.get("authorAttributions", [])
            ],
            flag_content_uri=data.get("flagContentUri"),
            google_maps_uri=data.get("googleMapsUri"),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class Date:
    """A calendar date. A zero component means it was unset."""

    year: int = 0
    month: int = 0
    day: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Date":
        data = copy.deepcopy(data)
        return cls(
            year=_as_int(data.get("year", 0), "Date", "year"),
            month=_as_int(data.get("month", 0), "Date", "month"),
            day=_as_int(data.get("day", 0), "Date", "day"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "OpeningPoint":
        data = copy.deepcopy(data)
        date = data.get("date")
        return cls(
            date=Date.from_api(date) if date else None,
            truncated=_optional_bool(data.get("truncated"), "OpeningPoint", "truncated"),
            day=_optional_int(data.get("day"), "OpeningPoint", "day"),
            hour=_optional_int(data.get("hour"), "OpeningPoint", "hour"),
            minute=_optional_int(data.get("minute"), "OpeningPoint", "minute"),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class Period:
    """A single open/close span within opening hours."""

    open: Optional[OpeningPoint] = None
    close: Optional[OpeningPoint] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Period":
        data = copy.deepcopy(data)
        open_point = data.get("open")
        close_point = data.get("close")
        return cls(
            open=OpeningPoint.from_api(open_point) if open_point else None,
            close=OpeningPoint.from_api(close_point) if close_point else None,
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class SpecialDay:
    """A day on which the hours differ from the regular schedule,
    carried inside current opening hours."""

    date: Optional[Date] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "SpecialDay":
        data = copy.deepcopy(data)
        date = data.get("date")
        return cls(date=Date.from_api(date) if date else None, raw=data)


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
    def from_api(cls, data: dict[str, Any]) -> "OpeningHours":
        data = copy.deepcopy(data)
        return cls(
            open_now=_optional_bool(data.get("openNow"), "OpeningHours", "openNow"),
            periods=[Period.from_api(p) for p in data.get("periods", [])],
            weekday_descriptions=_str_list(
                data.get("weekdayDescriptions", []),
                "OpeningHours",
                "weekdayDescriptions",
            ),
            next_close_time=data.get("nextCloseTime"),
            next_open_time=data.get("nextOpenTime"),
            special_days=[
                SpecialDay.from_api(d) for d in data.get("specialDays", [])
            ],
            secondary_hours_type=data.get("secondaryHoursType"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "AddressComponent":
        data = copy.deepcopy(data)
        return cls(
            long_text=data.get("longText", ""),
            short_text=data.get("shortText", ""),
            types=_str_list(data.get("types", []), "AddressComponent", "types"),
            language_code=data.get("languageCode"),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class PlusCode:
    """Plus code location reference for a place."""

    global_code: str = ""
    compound_code: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PlusCode":
        data = copy.deepcopy(data)
        return cls(
            global_code=data.get("globalCode", ""),
            compound_code=data.get("compoundCode"),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class Viewport:
    """A rectangular area bounded by its low and high corners."""

    low: LatLng
    high: LatLng
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Viewport":
        data = copy.deepcopy(data)
        return cls(
            low=LatLng.from_api(_require(data, "low", "Viewport")),
            high=LatLng.from_api(_require(data, "high", "Viewport")),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "PostalAddress":
        data = copy.deepcopy(data)
        return cls(
            region_code=data.get("regionCode"),
            language_code=data.get("languageCode"),
            postal_code=data.get("postalCode"),
            administrative_area=data.get("administrativeArea"),
            locality=data.get("locality"),
            address_lines=_str_list(
                data.get("addressLines", []), "PostalAddress", "addressLines"
            ),
            sublocality=data.get("sublocality"),
            organization=data.get("organization"),
            recipients=_str_list(
                data.get("recipients", []), "PostalAddress", "recipients"
            ),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Review":
        data = copy.deepcopy(data)
        text = data.get("text")
        original = data.get("originalText")
        rating = data.get("rating")
        attribution = data.get("authorAttribution")
        visit = data.get("visitDate")
        return cls(
            name=data.get("name", ""),
            relative_publish_time_description=data.get(
                "relativePublishTimeDescription", ""
            ),
            text=LocalizedText.from_api(text) if text else None,
            original_text=LocalizedText.from_api(original) if original else None,
            rating=(
                _as_float(rating, "Review", "rating")
                if rating is not None
                else None
            ),
            author_attribution=(
                AuthorAttribution.from_api(attribution) if attribution else None
            ),
            publish_time=data.get("publishTime"),
            flag_content_uri=data.get("flagContentUri"),
            google_maps_uri=data.get("googleMapsUri"),
            visit_date=Date.from_api(visit) if visit else None,
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "PaymentOptions":
        data = copy.deepcopy(data)
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
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "ParkingOptions":
        data = copy.deepcopy(data)
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
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "AccessibilityOptions":
        data = copy.deepcopy(data)
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
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "TimeZone":
        data = copy.deepcopy(data)
        return cls(id=data.get("id", ""), raw=data)


@dataclass(frozen=True, slots=True)
class GenerativeSummary:
    """An AI generated overview of a place.

    Only the overview text is typed. The flag and disclosure leaves
    beside it stay in ``Place.raw``.
    """

    overview: Optional[LocalizedText] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "GenerativeSummary":
        data = copy.deepcopy(data)
        overview = data.get("overview")
        return cls(
            overview=LocalizedText.from_api(overview) if overview else None,
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "ReviewSummary":
        data = copy.deepcopy(data)
        text = data.get("text")
        return cls(text=LocalizedText.from_api(text) if text else None, raw=data)


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
    def from_api(cls, data: dict[str, Any]) -> "ConsumerAlert":
        data = copy.deepcopy(data)
        return cls(
            overview=data.get("overview", ""),
            language_code=data.get("languageCode"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "GoogleMapsLinks":
        data = copy.deepcopy(data)
        return cls(
            directions_uri=data.get("directionsUri"),
            place_uri=data.get("placeUri"),
            write_a_review_uri=data.get("writeAReviewUri"),
            reviews_uri=data.get("reviewsUri"),
            photos_uri=data.get("photosUri"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Money":
        data = copy.deepcopy(data)
        return cls(
            currency_code=data.get("currencyCode", ""),
            units=_as_int(data.get("units", 0), "Money", "units"),
            nanos=_as_int(data.get("nanos", 0), "Money", "nanos"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "PriceRange":
        data = copy.deepcopy(data)
        start = data.get("startPrice")
        end = data.get("endPrice")
        return cls(
            start_price=Money.from_api(start) if start else None,
            end_price=Money.from_api(end) if end else None,
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "ConnectorAggregation":
        data = copy.deepcopy(data)
        rate = data.get("maxChargeRateKw")
        return cls(
            type=data.get("type", ""),
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
            availability_last_update_time=data.get("availabilityLastUpdateTime"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "EvChargeOptions":
        data = copy.deepcopy(data)
        return cls(
            connector_count=_optional_int(
                data.get("connectorCount"), "EvChargeOptions", "connectorCount"
            ),
            connector_aggregation=[
                ConnectorAggregation.from_api(a)
                for a in data.get("connectorAggregation", [])
            ],
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Landmark":
        data = copy.deepcopy(data)
        display = data.get("displayName")
        straight = data.get("straightLineDistanceMeters")
        travel = data.get("travelDistanceMeters")
        return cls(
            name=data.get("name", ""),
            place_id=data.get("placeId", ""),
            display_name=LocalizedText.from_api(display) if display else None,
            types=_str_list(data.get("types", []), "Landmark", "types"),
            spatial_relationship=data.get("spatialRelationship"),
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
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Area":
        data = copy.deepcopy(data)
        display = data.get("displayName")
        return cls(
            name=data.get("name", ""),
            place_id=data.get("placeId", ""),
            display_name=LocalizedText.from_api(display) if display else None,
            containment=data.get("containment"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "AddressDescriptor":
        data = copy.deepcopy(data)
        return cls(
            landmarks=[
                Landmark.from_api(landmark)
                for landmark in data.get("landmarks", [])
            ],
            areas=[Area.from_api(area) for area in data.get("areas", [])],
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Place":
        data = copy.deepcopy(data)
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
        place_id = data.get("id") or str(data.get("name", "")).removeprefix("places/")
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
            name=data.get("name", ""),
            display_name=LocalizedText.from_api(display) if display else None,
            formatted_address=data.get("formattedAddress"),
            short_formatted_address=data.get("shortFormattedAddress"),
            location=LatLng.from_api(location) if location else None,
            types=_str_list(data.get("types", []), "Place", "types"),
            primary_type=data.get("primaryType"),
            rating=(
                _as_float(rating, "Place", "rating") if rating is not None else None
            ),
            user_rating_count=(
                _as_int(user_rating_count, "Place", "userRatingCount")
                if user_rating_count is not None
                else None
            ),
            price_level=data.get("priceLevel"),
            business_status=data.get("businessStatus"),
            national_phone_number=data.get("nationalPhoneNumber"),
            international_phone_number=data.get("internationalPhoneNumber"),
            website_uri=data.get("websiteUri"),
            google_maps_uri=data.get("googleMapsUri"),
            opening_hours=OpeningHours.from_api(hours) if hours else None,
            current_opening_hours=(
                OpeningHours.from_api(current_hours) if current_hours else None
            ),
            current_secondary_opening_hours=[
                OpeningHours.from_api(h)
                for h in data.get("currentSecondaryOpeningHours", [])
            ],
            regular_secondary_opening_hours=[
                OpeningHours.from_api(h)
                for h in data.get("regularSecondaryOpeningHours", [])
            ],
            address_components=[
                AddressComponent.from_api(c)
                for c in data.get("addressComponents", [])
            ],
            plus_code=PlusCode.from_api(plus_code) if plus_code else None,
            viewport=Viewport.from_api(viewport) if viewport else None,
            postal_address=PostalAddress.from_api(postal) if postal else None,
            adr_format_address=data.get("adrFormatAddress"),
            primary_type_display_name=(
                LocalizedText.from_api(type_display) if type_display else None
            ),
            google_maps_type_label=(
                LocalizedText.from_api(type_label) if type_label else None
            ),
            editorial_summary=(
                LocalizedText.from_api(summary) if summary else None
            ),
            icon_mask_base_uri=data.get("iconMaskBaseUri"),
            icon_background_color=data.get("iconBackgroundColor"),
            opening_date=Date.from_api(opening) if opening else None,
            utc_offset_minutes=_optional_int(
                data.get("utcOffsetMinutes"), "Place", "utcOffsetMinutes"
            ),
            pure_service_area_business=_optional_bool(
                data.get("pureServiceAreaBusiness"),
                "Place",
                "pureServiceAreaBusiness",
            ),
            moved_place=data.get("movedPlace"),
            moved_place_id=data.get("movedPlaceId"),
            photos=[Photo.from_api(p) for p in data.get("photos", [])],
            attributions=[Attribution.from_api(a) for a in data.get("attributions", [])],
            reviews=[Review.from_api(r) for r in data.get("reviews", [])],
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
                PaymentOptions.from_api(payment) if payment else None
            ),
            parking_options=(
                ParkingOptions.from_api(parking) if parking else None
            ),
            accessibility_options=(
                AccessibilityOptions.from_api(accessibility)
                if accessibility
                else None
            ),
            time_zone=TimeZone.from_api(time_zone) if time_zone else None,
            generative_summary=(
                GenerativeSummary.from_api(generative) if generative else None
            ),
            review_summary=(
                ReviewSummary.from_api(review_summary) if review_summary else None
            ),
            consumer_alert=ConsumerAlert.from_api(alert) if alert else None,
            google_maps_links=(
                GoogleMapsLinks.from_api(links) if links else None
            ),
            price_range=PriceRange.from_api(price_range) if price_range else None,
            ev_charge_options=EvChargeOptions.from_api(ev) if ev else None,
            address_descriptor=(
                AddressDescriptor.from_api(descriptor) if descriptor else None
            ),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Leg":
        data = copy.deepcopy(data)
        return cls(
            duration=data.get("duration", ""),
            distance_meters=_optional_int(
                data.get("distanceMeters"), "Leg", "distanceMeters"
            ),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "RoutingSummary":
        data = copy.deepcopy(data)
        return cls(
            legs=[Leg.from_api(leg) for leg in data.get("legs", [])],
            directions_uri=data.get("directionsUri"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "TextSearchResult":
        data = copy.deepcopy(data)
        return cls(
            places=[Place.from_api(p) for p in data.get("places", [])],
            next_page_token=data.get("nextPageToken"),
            search_uri=data.get("searchUri"),
            routing_summaries=[
                RoutingSummary.from_api(s)
                for s in data.get("routingSummaries", [])
            ],
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "NearbySearchResult":
        data = copy.deepcopy(data)
        return cls(
            places=[Place.from_api(p) for p in data.get("places", [])],
            routing_summaries=[
                RoutingSummary.from_api(s)
                for s in data.get("routingSummaries", [])
            ],
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class StringMatch:
    """A substring match range inside an autocomplete text."""

    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "StringMatch":
        data = copy.deepcopy(data)
        return cls(
            start_offset=_optional_int(data.get("startOffset"), "StringMatch", "startOffset"),
            end_offset=_optional_int(data.get("endOffset"), "StringMatch", "endOffset"),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "FormattedText":
        data = copy.deepcopy(data)
        return cls(
            text=data.get("text", ""),
            matches=[StringMatch.from_api(m) for m in data.get("matches", [])],
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "PlacePrediction":
        data = copy.deepcopy(data)
        text = data.get("text")
        structured = data.get("structuredFormat") or {}
        main = structured.get("mainText")
        secondary = structured.get("secondaryText")
        return cls(
            place_id=data.get("placeId", ""),
            place=data.get("place", ""),
            text=FormattedText.from_api(text) if text else None,
            main_text=FormattedText.from_api(main) if main else None,
            secondary_text=FormattedText.from_api(secondary) if secondary else None,
            types=_str_list(data.get("types", []), "PlacePrediction", "types"),
            distance_meters=_optional_int(
                data.get("distanceMeters"), "PlacePrediction", "distanceMeters"
            ),
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "QueryPrediction":
        data = copy.deepcopy(data)
        text = data.get("text")
        structured = data.get("structuredFormat") or {}
        main = structured.get("mainText")
        secondary = structured.get("secondaryText")
        return cls(
            text=FormattedText.from_api(text) if text else None,
            main_text=FormattedText.from_api(main) if main else None,
            secondary_text=FormattedText.from_api(secondary) if secondary else None,
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "Suggestion":
        data = copy.deepcopy(data)
        prediction = data.get("placePrediction")
        query = data.get("queryPrediction")
        return cls(
            place_prediction=PlacePrediction.from_api(prediction) if prediction else None,
            query_prediction=QueryPrediction.from_api(query) if query else None,
            raw=data,
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
    def from_api(cls, data: dict[str, Any]) -> "AutocompleteResult":
        data = copy.deepcopy(data)
        return cls(
            suggestions=[Suggestion.from_api(s) for s in data.get("suggestions", [])],
            raw=data,
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

    photo_uri: str
    name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PhotoUriResult":
        data = copy.deepcopy(data)
        return cls(
            photo_uri=data.get("photoUri", ""),
            name=data.get("name", ""),
            raw=data,
        )
