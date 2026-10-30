"""Sync and async clients for the Google Places API (New).

Both clients share one Rust core and one method set. ``Client`` blocks and
is safe to use from ordinary scripts; ``AsyncClient`` awaits and is the one
to use inside an event loop. Methods return the typed models in
``placekit.models`` and raise the exceptions in ``placekit.exceptions``.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping
from typing import Any, Callable, Iterable, Optional

from . import _placekit
from ._placekit import PlacesError as _CorePlacesError
from .exceptions import ConfigError, DecodeError, raise_translated
from .fields import FieldsLike, normalize_fields
from .models import (
    AutocompleteResult,
    LatLng,
    NearbySearchResult,
    PhotoMedia,
    PhotoUriResult,
    Place,
    TextSearchResult,
)


def _drop_none(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


def _string_list(
    name: str, value: Optional[Iterable[str]]
) -> Optional[list[str]]:
    """Materialize an iterable-of-strings parameter exactly once.

    A bare string or bytes value is the classic slip for these slots:
    it is rejected with a ConfigError naming the parameter instead of
    being shredded into one-character items and sent. Every item must
    be a string. An empty result means the parameter is omitted,
    uniformly for every slot. That includes an already exhausted
    generator, which is indistinguishable from an empty one: the
    filter is omitted rather than sent as an empty list, and the
    behavior is the same in every slot (RT5-L2).
    """
    if value is None:
        return None
    if isinstance(value, (str, bytes)):
        raise ConfigError(
            f"{name} must be an iterable of strings, not a single "
            f"string: {value!r}"
        )
    try:
        items = list(value)
    except TypeError as exc:
        raise ConfigError(
            f"{name} must be an iterable of strings, got {value!r}"
        ) from exc
    for item in items:
        if not isinstance(item, str):
            raise ConfigError(
                f"{name} items must be strings, got {item!r}"
            )
    return items or None


def _validate_bool(name: str, value: Optional[bool]) -> Optional[bool]:
    """Accept only a real bool for a boolean body field.

    Anything else (the string "false", 0/1, a list) used to be coerced
    by truthiness in the conversion layer, silently inverting intent
    on the wire.
    """
    if value is None or isinstance(value, bool):
        return value
    raise ConfigError(f"{name} must be a bool, got {value!r}")


def _validate_coordinate(name: str, value: Any, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a real number, got {value!r}")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ConfigError(
            f"{name} must be finite and within {low:g} to {high:g}, "
            f"got {value!r}"
        )
    return result


def _validate_lat_lng(
    value: LatLng | tuple[float, float] | list[float] | dict[str, Any],
    name: str,
) -> dict[str, float]:
    """Validate one coordinate pair and return it in wire shape.

    Only ordered containers are accepted (LatLng, tuple, list, or a
    wire-shape dict); a set would unpack latitude and longitude in an
    arbitrary order. Values must be real numbers, bools are not
    numbers here, NaN and infinity are rejected instead of serializing
    as JSON null, and the ranges match the core's.
    """
    if isinstance(value, LatLng):
        latitude: Any = value.latitude
        longitude: Any = value.longitude
    elif isinstance(value, Mapping):
        if "latitude" not in value or "longitude" not in value:
            raise ConfigError(
                f"{name} must carry latitude and longitude, got {value!r}"
            )
        latitude = value["latitude"]
        longitude = value["longitude"]
    elif isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ConfigError(
                f"{name} must be a (latitude, longitude) pair, got {value!r}"
            )
        latitude, longitude = value
    else:
        raise ConfigError(
            f"{name} must be a LatLng, a (latitude, longitude) pair or "
            f"a latitude/longitude dict, got {value!r}"
        )
    return {
        "latitude": _validate_coordinate(f"{name} latitude", latitude, -90, 90),
        "longitude": _validate_coordinate(
            f"{name} longitude", longitude, -180, 180
        ),
    }


def _point(value: LatLng | tuple[float, float]) -> dict[str, float]:
    return _validate_lat_lng(value, "location")


def _circle_body(
    location: LatLng | tuple[float, float], radius_m: float
) -> dict[str, Any]:
    if (
        isinstance(radius_m, bool)
        or not isinstance(radius_m, (int, float))
        or not math.isfinite(float(radius_m))
    ):
        raise ConfigError(
            f"radius_m must be a finite number, got {radius_m!r}"
        )
    return {
        "circle": {
            "center": _validate_lat_lng(location, "location"),
            "radius": float(radius_m),
        }
    }


#: Wire names of the documented list-of-strings fields that can
#: appear inside the free-form dict body parameters. A bare string in
#: one of these slots is a list the caller forgot to write out; the
#: generic converter iterates a string as a sequence, so it would
#: reach the wire shredded into one-character strings (RT5-L1).
_DICT_LIST_FIELDS = frozenset(
    {
        "connectorTypes",
        "includedTypes",
        "excludedTypes",
        "includedPrimaryTypes",
        "excludedPrimaryTypes",
        "includedRegionCodes",
        "priceLevels",
    }
)

#: The deepest nesting accepted inside a free-form dict body
#: parameter. Past it the structure is cyclic or absurd, and the
#: caller gets a ConfigError instead of a RecursionError.
_MAX_DICT_DEPTH = 128


def _validate_dict_body(name: str, value: Any, depth: int = 0) -> None:
    """Recursively guard one free-form dict body parameter.

    Only the documented list-typed fields are checked, but they are
    checked at any nesting depth, so a bare string can never be
    iterated anywhere in body building. Everything else in these
    dicts is free-form by design and passes through untouched.
    """
    if depth > _MAX_DICT_DEPTH:
        raise ConfigError(
            f"{name} is nested deeper than {_MAX_DICT_DEPTH} levels; "
            "check for a self-referential structure"
        )
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _DICT_LIST_FIELDS and isinstance(item, (str, bytes)):
                raise ConfigError(
                    f"{name} field {key!r} must be a list of strings, "
                    f"not a single string: {item!r}"
                )
            _validate_dict_body(name, item, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_dict_body(name, item, depth + 1)


def _location_body(
    value: Optional[dict[str, Any]],
    name: str = "location bias or restriction",
) -> Optional[dict[str, Any]]:
    """Normalize a location bias or restriction dict into wire shape.

    Callers may describe a circle as ``{"circle": {"center":
    (latitude, longitude), "radius": meters}}`` with the center as a
    ``LatLng``, a tuple, a list or a wire-shape dict, or pass a
    rectangle with ``low`` and ``high`` corners in any of those forms.
    Values already in wire shape pass through. Coordinates are range
    checked here; the Rust core validates the rest (one shape only,
    bias circle radius within range, bias and restriction mutually
    exclusive). Non-mapping input is a ConfigError, never coerced
    through ``dict(...)``.
    """
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ConfigError(
            f"location bias or restriction must be a dict, got {value!r}"
        )
    result = dict(value)
    circle = result.get("circle")
    if isinstance(circle, dict) and "center" in circle:
        circle = dict(circle)
        center = circle["center"]
        if isinstance(center, (LatLng, tuple, list, Mapping)):
            circle["center"] = _validate_lat_lng(center, "circle center")
        result["circle"] = circle
    rectangle = result.get("rectangle")
    if isinstance(rectangle, dict):
        rectangle = dict(rectangle)
        for corner in ("low", "high"):
            point = rectangle.get(corner)
            if isinstance(point, (LatLng, tuple, list, Mapping)):
                rectangle[corner] = _validate_lat_lng(
                    point, f"rectangle {corner} corner"
                )
        result["rectangle"] = rectangle
    _validate_dict_body(name, result)
    return result


def _routing_body(value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Normalize routing parameters, converting an origin given as a
    ``LatLng``, a tuple, a list or a wire-shape dict into wire shape."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ConfigError(f"routing_parameters must be a dict, got {value!r}")
    result = dict(value)
    origin = result.get("origin")
    if isinstance(origin, (LatLng, tuple, list, Mapping)):
        result["origin"] = _validate_lat_lng(origin, "routing origin")
    _validate_dict_body("routing_parameters", result)
    return result


def _mapping_body(name: str, value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Validate a bare dict escape-hatch parameter's shape."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a dict, got {value!r}")
    result = dict(value)
    _validate_dict_body(name, result)
    return result


def _photo_result(tagged: tuple[str, Any, Any]) -> PhotoMedia | PhotoUriResult:
    """Turn the core's tagged photo tuple into a public model.

    The uri arm's third element is the whole JSON form the endpoint
    returned, as a dict. The model is built from it so the full form
    is preserved on the result's ``raw``. The tuple's first element
    repeats the URI already inside that dict and is not read.
    """
    tag, first, second = tagged
    if tag == "uri":
        return PhotoUriResult.from_api(second)
    if tag == "bytes":
        return PhotoMedia(content=first, content_type=second)
    raise DecodeError(f"photo result carried an unknown tag: {tag!r}")


#: The longest per-request timeout the Python clients accept, in
#: seconds. Beyond an hour a per-request timeout stops meaning
#: anything; the value is rejected as a configuration error instead
#: of being silently treated as no timeout at all.
_MAX_TIMEOUT_SECONDS = 3600


class _Base:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        if not isinstance(api_key, str):
            raise ConfigError(f"api_key must be a string, got {api_key!r}")
        if not api_key.strip():
            raise ConfigError("api_key must not be empty")
        if api_key != api_key.strip() or not api_key.isascii() or any(
            char.isspace() for char in api_key
        ):
            raise ConfigError(
                "api_key must not contain whitespace or non-ASCII characters"
            )
        if base_url is not None and not isinstance(base_url, str):
            raise ConfigError(f"base_url must be a string, got {base_url!r}")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= _MAX_TIMEOUT_SECONDS
        ):
            raise ConfigError(
                "timeout must be a positive, finite number of seconds, "
                f"at most {_MAX_TIMEOUT_SECONDS}, got {timeout!r}"
            )
        self._closed = False
        try:
            self._inner = _placekit.Client(api_key, base_url, timeout)
        except _CorePlacesError as exc:
            raise_translated(exc, "client construction")
        except ValueError as exc:
            # The bindings surface core configuration failures (for
            # example a key that cannot be sent as a header value) as
            # plain ValueError; inside this package they are
            # ConfigError, the one documented type for local misuse.
            raise ConfigError(str(exc)) from exc

    # -- lifecycle and duplication -------------------------------------

    def close(self) -> None:
        """Release the underlying native client.

        Idempotent. Any later call on this client raises ConfigError.
        Both clients are context managers (``with`` for Client,
        ``async with`` for AsyncClient) that close on exit.
        """
        self._inner = None
        self._closed = True

    def _ensure_open(self, context: str) -> None:
        if self._closed:
            raise ConfigError("client is closed", context=context)

    def __reduce__(self):
        # The native handle is a live resource; the default pickle
        # error used to name the hidden native class, a phantom
        # "builtins.Client" users never imported.
        raise TypeError(
            "placekit clients hold a live native resource and cannot "
            "be pickled or copied; create a new client instead"
        )

    def __copy__(self):
        return self.__reduce__()

    def __deepcopy__(self, memo):
        return self.__reduce__()

    @staticmethod
    def _with_context(exc: ConfigError, context: str) -> ConfigError:
        """Attach the calling method as context to a locally raised
        ConfigError that does not carry one yet (RC-03)."""
        if exc.context is None:
            return ConfigError(str(exc), context=context)
        return exc

    @staticmethod
    def _check_no_running_loop(context: str) -> None:
        """A sync call inside a running event loop would freeze the
        whole loop for the request duration; refuse and point at
        AsyncClient instead (RC-13)."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise ConfigError(
            "the sync Client cannot be called from a running event "
            "loop; use AsyncClient inside async code",
            context=context,
        )

    @staticmethod
    def _require_str(name: str, value: Any, context: str) -> str:
        if not isinstance(value, str):
            raise ConfigError(
                f"{name} must be a string, got {value!r}", context=context
            )
        return value

    @staticmethod
    def _validate_photo_args(
        photo_name: Any,
        max_width_px: Optional[int],
        max_height_px: Optional[int],
        skip_http_redirect: Any,
        context: str,
    ) -> None:
        """place_photo validation, enforced here before the native
        call: a string name, each dimension in range, at least one
        dimension present, and a real bool for the redirect flag."""
        _Base._require_str("photo_name", photo_name, context)
        try:
            _Base._validate_int_range("max_width_px", max_width_px, 1, 4800)
            _Base._validate_int_range("max_height_px", max_height_px, 1, 4800)
        except ConfigError as exc:
            raise _Base._with_context(exc, context) from exc
        if max_width_px is None and max_height_px is None:
            raise ConfigError(
                "place_photo requires at least one of max_width_px "
                "and max_height_px",
                context=context,
            )
        if not isinstance(skip_http_redirect, bool):
            raise ConfigError(
                f"skip_http_redirect must be a bool, got {skip_http_redirect!r}",
                context=context,
            )

    @staticmethod
    def _validate_int_range(
        name: str, value: Optional[int], low: int, high: int
    ) -> Optional[int]:
        """Validate an optional integer argument before it reaches the
        core, where a negative or oversized value would otherwise
        escape the typed hierarchy as a bare OverflowError or a
        ValueError carrying one."""
        if value is None:
            return None
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not low <= value <= high
        ):
            raise ConfigError(
                f"{name} must be an integer between {low} and {high}, got {value!r}"
            )
        return value

    @staticmethod
    def _validate_float_range(
        name: str, value: Optional[float], low: float, high: float
    ) -> Optional[float]:
        """Validate an optional real-number argument, bools rejected,
        NaN and infinity rejected instead of reaching the core."""
        if value is None:
            return None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not low <= float(value) <= high
        ):
            raise ConfigError(
                f"{name} must be a number between {low:g} and {high:g}, "
                f"got {value!r}"
            )
        return float(value)

    @staticmethod
    def _convert(convert: Callable[[Any], Any], data: Any, context: str):
        """Run a model conversion over a decoded response.

        The model layer is a second decoder; its builtin failures
        (KeyError, TypeError and friends) are translated into
        DecodeError so callers only ever see the typed hierarchy. The
        DecodeError carries the calling method as its context.
        """
        try:
            return convert(data)
        except DecodeError as exc:
            if exc.context is None:
                raise DecodeError(str(exc), context=context) from exc
            raise
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise DecodeError(
                f"response failed model conversion: {exc!r}", context=context
            ) from exc

    # Body builders shared by the sync and async method sets.

    @staticmethod
    def _text_search_body(
        query: str,
        *,
        page_token: Optional[str],
        language: Optional[str],
        region: Optional[str],
        rank_preference: Optional[str],
        open_now: Optional[bool],
        price_levels: Optional[Iterable[str]],
        strict_type_filtering: Optional[bool],
        included_type: Optional[str],
        location_bias: Optional[dict[str, Any]],
        location_restriction: Optional[dict[str, Any]],
        page_size: Optional[int] = None,
        min_rating: Optional[float] = None,
        ev_options: Optional[dict[str, Any]] = None,
        search_along_route: Optional[dict[str, Any]] = None,
        routing_parameters: Optional[dict[str, Any]] = None,
        include_pure_service_area_businesses: Optional[bool] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> dict[str, Any]:
        return _drop_none(
            {
                "textQuery": query,
                "pageToken": page_token,
                "languageCode": language,
                "regionCode": region,
                "rankPreference": rank_preference,
                "openNow": _validate_bool("open_now", open_now),
                "priceLevels": _string_list("price_levels", price_levels),
                "strictTypeFiltering": _validate_bool(
                    "strict_type_filtering", strict_type_filtering
                ),
                "includedType": included_type,
                "locationBias": _location_body(location_bias, "location_bias"),
                "locationRestriction": _location_body(
                    location_restriction, "location_restriction"
                ),
                "pageSize": _Base._validate_int_range(
                    "page_size", page_size, 1, 20
                ),
                "minRating": _Base._validate_float_range(
                    "min_rating", min_rating, 0, 5
                ),
                "evOptions": _mapping_body("ev_options", ev_options),
                "searchAlongRouteParameters": _mapping_body(
                    "search_along_route", search_along_route
                ),
                "routingParameters": _routing_body(routing_parameters),
                "includePureServiceAreaBusinesses": _validate_bool(
                    "include_pure_service_area_businesses",
                    include_pure_service_area_businesses,
                ),
                "includeFutureOpeningBusinesses": _validate_bool(
                    "include_future_opening_businesses",
                    include_future_opening_businesses,
                ),
            }
        )

    @staticmethod
    def _nearby_search_body(
        location: LatLng | tuple[float, float],
        radius_m: float,
        *,
        included_types: Optional[Iterable[str]],
        excluded_types: Optional[Iterable[str]],
        max_results: Optional[int],
        language: Optional[str],
        region: Optional[str],
        rank_preference: Optional[str],
        included_primary_types: Optional[Iterable[str]] = None,
        excluded_primary_types: Optional[Iterable[str]] = None,
        routing_parameters: Optional[dict[str, Any]] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> dict[str, Any]:
        return _drop_none(
            {
                "locationRestriction": _circle_body(location, radius_m),
                "includedTypes": _string_list("included_types", included_types),
                "excludedTypes": _string_list("excluded_types", excluded_types),
                "includedPrimaryTypes": _string_list(
                    "included_primary_types", included_primary_types
                ),
                "excludedPrimaryTypes": _string_list(
                    "excluded_primary_types", excluded_primary_types
                ),
                "maxResultCount": _Base._validate_int_range(
                    "max_results", max_results, 1, 20
                ),
                "languageCode": language,
                "regionCode": region,
                "rankPreference": rank_preference,
                "routingParameters": _routing_body(routing_parameters),
                "includeFutureOpeningBusinesses": _validate_bool(
                    "include_future_opening_businesses",
                    include_future_opening_businesses,
                ),
            }
        )

    @staticmethod
    def _autocomplete_body(
        input_text: str,
        *,
        language: Optional[str],
        region: Optional[str],
        session_token: Optional[str],
        included_region_codes: Optional[Iterable[str]],
        include_query_predictions: Optional[bool],
        location_bias: Optional[dict[str, Any]],
        location_restriction: Optional[dict[str, Any]],
        origin: Optional[LatLng | tuple[float, float]] = None,
        input_offset: Optional[int] = None,
        included_primary_types: Optional[Iterable[str]] = None,
        include_pure_service_area_businesses: Optional[bool] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> dict[str, Any]:
        return _drop_none(
            {
                "input": input_text,
                "languageCode": language,
                "regionCode": region,
                "sessionToken": session_token,
                "includedRegionCodes": _string_list(
                    "included_region_codes", included_region_codes
                ),
                "includeQueryPredictions": _validate_bool(
                    "include_query_predictions", include_query_predictions
                ),
                "locationBias": _location_body(location_bias, "location_bias"),
                "locationRestriction": _location_body(
                    location_restriction, "location_restriction"
                ),
                "origin": (
                    _validate_lat_lng(origin, "origin")
                    if origin is not None
                    else None
                ),
                "inputOffset": _Base._validate_int_range(
                    "input_offset", input_offset, 0, 2**31 - 1
                ),
                "includedPrimaryTypes": _string_list(
                    "included_primary_types", included_primary_types
                ),
                "includePureServiceAreaBusinesses": _validate_bool(
                    "include_pure_service_area_businesses",
                    include_pure_service_area_businesses,
                ),
                "includeFutureOpeningBusinesses": _validate_bool(
                    "include_future_opening_businesses",
                    include_future_opening_businesses,
                ),
            }
        )


class Client(_Base):
    """Blocking client for the Places API (New).

    >>> client = Client("YOUR_API_KEY")
    >>> result = client.text_search("pizza in New York")
    >>> result.places[0].display_text
    '...'

    ``base_url`` overrides the API root, which is how the test suite points
    the client at a local stub server. ``timeout`` is per request, in
    seconds, and may be at most 3600; anything else about it (zero,
    negative, non-finite, a boolean, a non-number) is a ``ConfigError``.
    """

    def text_search(
        self,
        query: str,
        *,
        fields: FieldsLike = None,
        page_token: Optional[str] = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        rank_preference: Optional[str] = None,
        open_now: Optional[bool] = None,
        price_levels: Optional[Iterable[str]] = None,
        strict_type_filtering: Optional[bool] = None,
        included_type: Optional[str] = None,
        location_bias: Optional[dict[str, Any]] = None,
        location_restriction: Optional[dict[str, Any]] = None,
        page_size: Optional[int] = None,
        min_rating: Optional[float] = None,
        ev_options: Optional[dict[str, Any]] = None,
        search_along_route: Optional[dict[str, Any]] = None,
        routing_parameters: Optional[dict[str, Any]] = None,
        include_pure_service_area_businesses: Optional[bool] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> TextSearchResult:
        """Search for places matching a free-form query.

        ``rank_preference`` is ``"RELEVANCE"`` or ``"DISTANCE"``.
        ``price_levels`` takes API values such as ``"PRICE_LEVEL_MODERATE"``.
        ``page_size`` caps how many results one page carries (1 to 20).
        ``min_rating``
        filters out places rated below it (0 to 5). ``ev_options`` and
        ``search_along_route`` take the API's camelCase dict shapes.
        ``routing_parameters`` takes a dict whose ``origin`` may be a
        ``LatLng`` or a ``(latitude, longitude)`` tuple.
        """
        self._ensure_open("text_search")
        self._check_no_running_loop("text_search")
        self._require_str("query", query, "text_search")
        try:
            body = self._text_search_body(
                query,
                page_token=page_token,
                language=language,
                region=region,
                rank_preference=rank_preference,
                open_now=open_now,
                price_levels=price_levels,
                strict_type_filtering=strict_type_filtering,
                included_type=included_type,
                location_bias=location_bias,
                location_restriction=location_restriction,
                page_size=page_size,
                min_rating=min_rating,
                ev_options=ev_options,
                search_along_route=search_along_route,
                routing_parameters=routing_parameters,
                include_pure_service_area_businesses=(
                    include_pure_service_area_businesses
                ),
                include_future_opening_businesses=include_future_opening_businesses,
            )
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, "text_search") from exc
        try:
            data = self._inner.text_search(body, fields_list)
        except _CorePlacesError as exc:
            raise_translated(exc, "text_search")
        return self._convert(TextSearchResult.from_api, data, "text_search")

    def nearby_search(
        self,
        location: LatLng | tuple[float, float],
        radius_m: float,
        *,
        fields: FieldsLike = None,
        included_types: Optional[Iterable[str]] = None,
        excluded_types: Optional[Iterable[str]] = None,
        max_results: Optional[int] = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        rank_preference: Optional[str] = None,
        included_primary_types: Optional[Iterable[str]] = None,
        excluded_primary_types: Optional[Iterable[str]] = None,
        routing_parameters: Optional[dict[str, Any]] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> NearbySearchResult:
        """Search for places around ``location`` within ``radius_m`` meters.

        ``rank_preference`` is ``"DISTANCE"`` or ``"POPULARITY"``.
        The primary type filters take up to 50 place types each, and a
        type listed in both is an error at the API.
        """
        self._ensure_open("nearby_search")
        self._check_no_running_loop("nearby_search")
        try:
            body = self._nearby_search_body(
                location,
                radius_m,
                included_types=included_types,
                excluded_types=excluded_types,
                max_results=max_results,
                language=language,
                region=region,
                rank_preference=rank_preference,
                included_primary_types=included_primary_types,
                excluded_primary_types=excluded_primary_types,
                routing_parameters=routing_parameters,
                include_future_opening_businesses=include_future_opening_businesses,
            )
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, "nearby_search") from exc
        try:
            data = self._inner.nearby_search(body, fields_list)
        except _CorePlacesError as exc:
            raise_translated(exc, "nearby_search")
        return self._convert(NearbySearchResult.from_api, data, "nearby_search")

    def place_details(
        self,
        place_id: str,
        *,
        fields: FieldsLike = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        session_token: Optional[str] = None,
    ) -> Place:
        """Fetch full details for one place id."""
        self._ensure_open("place_details")
        self._check_no_running_loop("place_details")
        self._require_str("place_id", place_id, "place_details")
        context = f"place_details place_id={place_id}"
        try:
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, context) from exc
        try:
            data = self._inner.place_details(
                place_id,
                fields_list,
                language,
                region,
                session_token,
            )
        except _CorePlacesError as exc:
            raise_translated(exc, context)
        return self._convert(Place.from_api, data, context)

    def autocomplete(
        self,
        input_text: str,
        *,
        fields: FieldsLike = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        session_token: Optional[str] = None,
        included_region_codes: Optional[Iterable[str]] = None,
        include_query_predictions: Optional[bool] = None,
        location_bias: Optional[dict[str, Any]] = None,
        location_restriction: Optional[dict[str, Any]] = None,
        origin: Optional[LatLng | tuple[float, float]] = None,
        input_offset: Optional[int] = None,
        included_primary_types: Optional[Iterable[str]] = None,
        include_pure_service_area_businesses: Optional[bool] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> AutocompleteResult:
        """Get place predictions for partial input text.

        Pass ``origin`` (a ``LatLng`` or a ``(latitude, longitude)``
        tuple) to get ``distance_meters`` on predictions; without an
        origin the API returns no distances. ``included_primary_types``
        takes up to 5 place types, or the single collection ``(cities)``
        or ``(regions)``. A ``fields`` mask is optional on this endpoint.
        """
        self._ensure_open("autocomplete")
        self._check_no_running_loop("autocomplete")
        self._require_str("input_text", input_text, "autocomplete")
        try:
            body = self._autocomplete_body(
                input_text,
                language=language,
                region=region,
                session_token=session_token,
                included_region_codes=included_region_codes,
                include_query_predictions=include_query_predictions,
                location_bias=location_bias,
                location_restriction=location_restriction,
                origin=origin,
                input_offset=input_offset,
                included_primary_types=included_primary_types,
                include_pure_service_area_businesses=(
                    include_pure_service_area_businesses
                ),
                include_future_opening_businesses=include_future_opening_businesses,
            )
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, "autocomplete") from exc
        try:
            data = self._inner.autocomplete(body, fields_list)
        except _CorePlacesError as exc:
            raise_translated(exc, "autocomplete")
        return self._convert(AutocompleteResult.from_api, data, "autocomplete")

    def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = None,
        max_height_px: Optional[int] = None,
        skip_http_redirect: bool = False,
    ) -> PhotoMedia | PhotoUriResult:
        """Download a photo by its resource name.

        ``photo_name`` comes from ``Place.photos[i].name``. At least one of
        ``max_width_px`` and ``max_height_px`` is required (each 1 to 4800).

        By default this follows the endpoint's redirect and returns a
        ``PhotoMedia`` with the image bytes. With
        ``skip_http_redirect=True`` it returns a ``PhotoUriResult``
        carrying the photo's short lived URI instead, with the full
        JSON form the endpoint returned preserved on its ``raw``.
        """
        context = f"place_photo name={photo_name}"
        self._ensure_open("place_photo")
        self._check_no_running_loop("place_photo")
        self._validate_photo_args(
            photo_name, max_width_px, max_height_px, skip_http_redirect, context
        )
        try:
            tagged = self._inner.place_photo(
                photo_name, max_width_px, max_height_px, skip_http_redirect
            )
        except _CorePlacesError as exc:
            raise_translated(exc, context)
        return self._convert(_photo_result, tagged, context)

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


class AsyncClient(_Base):
    """Async client for the Places API (New), with Client's method set.

    >>> client = AsyncClient("YOUR_API_KEY")
    >>> result = await client.text_search("pizza in New York")

    Argument validation fires when a call is awaited, not when the
    coroutine object is created, because an async method's body only
    runs on await (A21). A ``ConfigError`` for bad arguments
    therefore surfaces at the ``await``, unlike the sync client,
    where it surfaces at the call itself.
    """

    async def text_search(
        self,
        query: str,
        *,
        fields: FieldsLike = None,
        page_token: Optional[str] = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        rank_preference: Optional[str] = None,
        open_now: Optional[bool] = None,
        price_levels: Optional[Iterable[str]] = None,
        strict_type_filtering: Optional[bool] = None,
        included_type: Optional[str] = None,
        location_bias: Optional[dict[str, Any]] = None,
        location_restriction: Optional[dict[str, Any]] = None,
        page_size: Optional[int] = None,
        min_rating: Optional[float] = None,
        ev_options: Optional[dict[str, Any]] = None,
        search_along_route: Optional[dict[str, Any]] = None,
        routing_parameters: Optional[dict[str, Any]] = None,
        include_pure_service_area_businesses: Optional[bool] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> TextSearchResult:
        """Async version of ``Client.text_search``."""
        self._ensure_open("text_search")
        self._require_str("query", query, "text_search")
        try:
            body = self._text_search_body(
                query,
                page_token=page_token,
                language=language,
                region=region,
                rank_preference=rank_preference,
                open_now=open_now,
                price_levels=price_levels,
                strict_type_filtering=strict_type_filtering,
                included_type=included_type,
                location_bias=location_bias,
                location_restriction=location_restriction,
                page_size=page_size,
                min_rating=min_rating,
                ev_options=ev_options,
                search_along_route=search_along_route,
                routing_parameters=routing_parameters,
                include_pure_service_area_businesses=(
                    include_pure_service_area_businesses
                ),
                include_future_opening_businesses=include_future_opening_businesses,
            )
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, "text_search") from exc
        try:
            data = await self._inner.text_search_async(body, fields_list)
        except _CorePlacesError as exc:
            raise_translated(exc, "text_search")
        return self._convert(TextSearchResult.from_api, data, "text_search")

    async def nearby_search(
        self,
        location: LatLng | tuple[float, float],
        radius_m: float,
        *,
        fields: FieldsLike = None,
        included_types: Optional[Iterable[str]] = None,
        excluded_types: Optional[Iterable[str]] = None,
        max_results: Optional[int] = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        rank_preference: Optional[str] = None,
        included_primary_types: Optional[Iterable[str]] = None,
        excluded_primary_types: Optional[Iterable[str]] = None,
        routing_parameters: Optional[dict[str, Any]] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> NearbySearchResult:
        """Async version of ``Client.nearby_search``."""
        self._ensure_open("nearby_search")
        try:
            body = self._nearby_search_body(
                location,
                radius_m,
                included_types=included_types,
                excluded_types=excluded_types,
                max_results=max_results,
                language=language,
                region=region,
                rank_preference=rank_preference,
                included_primary_types=included_primary_types,
                excluded_primary_types=excluded_primary_types,
                routing_parameters=routing_parameters,
                include_future_opening_businesses=include_future_opening_businesses,
            )
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, "nearby_search") from exc
        try:
            data = await self._inner.nearby_search_async(body, fields_list)
        except _CorePlacesError as exc:
            raise_translated(exc, "nearby_search")
        return self._convert(NearbySearchResult.from_api, data, "nearby_search")

    async def place_details(
        self,
        place_id: str,
        *,
        fields: FieldsLike = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        session_token: Optional[str] = None,
    ) -> Place:
        """Async version of ``Client.place_details``."""
        self._ensure_open("place_details")
        self._require_str("place_id", place_id, "place_details")
        context = f"place_details place_id={place_id}"
        try:
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, context) from exc
        try:
            data = await self._inner.place_details_async(
                place_id,
                fields_list,
                language,
                region,
                session_token,
            )
        except _CorePlacesError as exc:
            raise_translated(exc, context)
        return self._convert(Place.from_api, data, context)

    async def autocomplete(
        self,
        input_text: str,
        *,
        fields: FieldsLike = None,
        language: Optional[str] = None,
        region: Optional[str] = None,
        session_token: Optional[str] = None,
        included_region_codes: Optional[Iterable[str]] = None,
        include_query_predictions: Optional[bool] = None,
        location_bias: Optional[dict[str, Any]] = None,
        location_restriction: Optional[dict[str, Any]] = None,
        origin: Optional[LatLng | tuple[float, float]] = None,
        input_offset: Optional[int] = None,
        included_primary_types: Optional[Iterable[str]] = None,
        include_pure_service_area_businesses: Optional[bool] = None,
        include_future_opening_businesses: Optional[bool] = None,
    ) -> AutocompleteResult:
        """Async version of ``Client.autocomplete``."""
        self._ensure_open("autocomplete")
        self._require_str("input_text", input_text, "autocomplete")
        try:
            body = self._autocomplete_body(
                input_text,
                language=language,
                region=region,
                session_token=session_token,
                included_region_codes=included_region_codes,
                include_query_predictions=include_query_predictions,
                location_bias=location_bias,
                location_restriction=location_restriction,
                origin=origin,
                input_offset=input_offset,
                included_primary_types=included_primary_types,
                include_pure_service_area_businesses=(
                    include_pure_service_area_businesses
                ),
                include_future_opening_businesses=include_future_opening_businesses,
            )
            fields_list = normalize_fields(fields)
        except ConfigError as exc:
            raise self._with_context(exc, "autocomplete") from exc
        try:
            data = await self._inner.autocomplete_async(
                body, fields_list
            )
        except _CorePlacesError as exc:
            raise_translated(exc, "autocomplete")
        return self._convert(AutocompleteResult.from_api, data, "autocomplete")

    async def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = None,
        max_height_px: Optional[int] = None,
        skip_http_redirect: bool = False,
    ) -> PhotoMedia | PhotoUriResult:
        """Async version of ``Client.place_photo``."""
        context = f"place_photo name={photo_name}"
        self._ensure_open("place_photo")
        self._validate_photo_args(
            photo_name, max_width_px, max_height_px, skip_http_redirect, context
        )
        try:
            tagged = await self._inner.place_photo_async(
                photo_name, max_width_px, max_height_px, skip_http_redirect
            )
        except _CorePlacesError as exc:
            raise_translated(exc, context)
        return self._convert(_photo_result, tagged, context)

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None:
        self.close()
