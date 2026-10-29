"""Sync and async clients for the Google Places API (New).

Both clients share one Rust core and one method set. ``Client`` blocks and
is safe to use from ordinary scripts; ``AsyncClient`` awaits and is the one
to use inside an event loop. Methods return the typed models in
``placekit.models`` and raise the exceptions in ``placekit.exceptions``.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional

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


def _point(value: LatLng | tuple[float, float]) -> dict[str, float]:
    if isinstance(value, LatLng):
        return value.to_api()
    latitude, longitude = value
    return {"latitude": float(latitude), "longitude": float(longitude)}


def _circle_body(
    location: LatLng | tuple[float, float], radius_m: float
) -> dict[str, Any]:
    return {"circle": {"center": _point(location), "radius": float(radius_m)}}


def _location_body(value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Normalize a location bias or restriction dict into wire shape.

    Callers may describe a circle as ``{"circle": {"center":
    (latitude, longitude), "radius": meters}}`` with the center as a
    ``LatLng`` or a plain tuple, or pass a rectangle with ``low`` and
    ``high`` corners in either form. Values already in wire shape pass
    through. The Rust core validates the result (one shape only, bias
    circle radius within range, bias and restriction mutually exclusive).
    """
    if value is None:
        return None
    result = dict(value)
    circle = result.get("circle")
    if isinstance(circle, dict) and "center" in circle:
        circle = dict(circle)
        center = circle["center"]
        if isinstance(center, LatLng) or isinstance(center, tuple):
            circle["center"] = _point(center)
        result["circle"] = circle
    rectangle = result.get("rectangle")
    if isinstance(rectangle, dict):
        rectangle = dict(rectangle)
        for corner in ("low", "high"):
            point = rectangle.get(corner)
            if isinstance(point, LatLng) or isinstance(point, tuple):
                rectangle[corner] = _point(point)
        result["rectangle"] = rectangle
    return result


def _routing_body(value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Normalize routing parameters, converting an origin given as a
    ``LatLng`` or a tuple into wire shape."""
    if value is None:
        return None
    result = dict(value)
    origin = result.get("origin")
    if isinstance(origin, LatLng) or isinstance(origin, tuple):
        result["origin"] = _point(origin)
    return result


def _photo_result(tagged: tuple) -> PhotoMedia | PhotoUriResult:
    """Turn the core's tagged photo tuple into a public model."""
    tag, first, second = tagged
    if tag == "uri":
        return PhotoUriResult(photo_uri=first, name=second or "")
    return PhotoMedia(content=first, content_type=second)


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
        if not api_key or not api_key.strip():
            raise ConfigError("api_key must not be empty")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= _MAX_TIMEOUT_SECONDS
        ):
            raise ConfigError(
                "timeout must be a positive, finite number of seconds, "
                f"at most {_MAX_TIMEOUT_SECONDS}"
            )
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
    def _convert(convert, data):
        """Run a model conversion over a decoded response.

        The model layer is a second decoder; its builtin failures
        (KeyError, TypeError and friends) are translated into
        DecodeError so callers only ever see the typed hierarchy.
        """
        try:
            return convert(data)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise DecodeError(
                f"response failed model conversion: {exc!r}"
            ) from exc

    # Body builders shared by the sync and async method sets.

    @staticmethod
    def _text_search_body(
        query: str,
        *,
        max_results: Optional[int],
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
                "maxResultCount": _Base._validate_int_range(
                "max_results", max_results, 1, 20
            ),
                "pageToken": page_token,
                "languageCode": language,
                "regionCode": region,
                "rankPreference": rank_preference,
                "openNow": open_now,
                "priceLevels": list(price_levels) if price_levels is not None else None,
                "strictTypeFiltering": strict_type_filtering,
                "includedType": included_type,
                "locationBias": _location_body(location_bias),
                "locationRestriction": _location_body(location_restriction),
                "pageSize": page_size,
                "minRating": min_rating,
                "evOptions": ev_options,
                "searchAlongRouteParameters": search_along_route,
                "routingParameters": _routing_body(routing_parameters),
                "includePureServiceAreaBusinesses": (
                    include_pure_service_area_businesses
                ),
                "includeFutureOpeningBusinesses": include_future_opening_businesses,
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
                "includedTypes": list(included_types) if included_types is not None else None,
                "excludedTypes": list(excluded_types) if excluded_types is not None else None,
                "includedPrimaryTypes": (
                    list(included_primary_types)
                    if included_primary_types is not None
                    else None
                ),
                "excludedPrimaryTypes": (
                    list(excluded_primary_types)
                    if excluded_primary_types is not None
                    else None
                ),
                "maxResultCount": _Base._validate_int_range(
                "max_results", max_results, 1, 20
            ),
                "languageCode": language,
                "regionCode": region,
                "rankPreference": rank_preference,
                "routingParameters": _routing_body(routing_parameters),
                "includeFutureOpeningBusinesses": include_future_opening_businesses,
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
                "includedRegionCodes": (
                    list(included_region_codes)
                    if included_region_codes is not None
                    else None
                ),
                "includeQueryPredictions": include_query_predictions,
                "locationBias": _location_body(location_bias),
                "locationRestriction": _location_body(location_restriction),
                "origin": _point(origin) if origin is not None else None,
                "inputOffset": input_offset,
                "includedPrimaryTypes": (
                    list(included_primary_types)
                    if included_primary_types is not None
                    else None
                ),
                "includePureServiceAreaBusinesses": (
                    include_pure_service_area_businesses
                ),
                "includeFutureOpeningBusinesses": include_future_opening_businesses,
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
        max_results: Optional[int] = None,
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
        ``page_size`` is the current spelling of the page size limit and
        supersedes ``max_results`` when both are given. ``min_rating``
        filters out places rated below it (0 to 5). ``ev_options`` and
        ``search_along_route`` take the API's camelCase dict shapes.
        ``routing_parameters`` takes a dict whose ``origin`` may be a
        ``LatLng`` or a ``(latitude, longitude)`` tuple.
        """
        body = self._text_search_body(
            query,
            max_results=max_results,
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
        try:
            data = self._inner.text_search(body, normalize_fields(fields))
        except _CorePlacesError as exc:
            raise_translated(exc, "text_search")
        return self._convert(TextSearchResult.from_api, data)

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
        try:
            data = self._inner.nearby_search(body, normalize_fields(fields))
        except _CorePlacesError as exc:
            raise_translated(exc, "nearby_search")
        return self._convert(NearbySearchResult.from_api, data)

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
        try:
            data = self._inner.place_details(
                place_id,
                normalize_fields(fields),
                language,
                region,
                session_token,
            )
        except _CorePlacesError as exc:
            raise_translated(exc, f"place_details place_id={place_id}")
        return self._convert(Place.from_api, data)

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
        try:
            data = self._inner.autocomplete(body, normalize_fields(fields))
        except _CorePlacesError as exc:
            raise_translated(exc, "autocomplete")
        return self._convert(AutocompleteResult.from_api, data)

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
        carrying the photo's short lived URI instead.
        """
        self._validate_int_range("max_width_px", max_width_px, 1, 4800)
        self._validate_int_range("max_height_px", max_height_px, 1, 4800)
        try:
            tagged = self._inner.place_photo(
                photo_name, max_width_px, max_height_px, skip_http_redirect
            )
        except _CorePlacesError as exc:
            raise_translated(exc, f"place_photo name={photo_name}")
        return self._convert(_photo_result, tagged)


class AsyncClient(_Base):
    """Async client for the Places API (New), with Client's method set.

    >>> client = AsyncClient("YOUR_API_KEY")
    >>> result = await client.text_search("pizza in New York")
    """

    async def text_search(
        self,
        query: str,
        *,
        fields: FieldsLike = None,
        max_results: Optional[int] = None,
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
        body = self._text_search_body(
            query,
            max_results=max_results,
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
        try:
            data = await self._inner.text_search_async(body, normalize_fields(fields))
        except _CorePlacesError as exc:
            raise_translated(exc, "text_search")
        return self._convert(TextSearchResult.from_api, data)

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
        try:
            data = await self._inner.nearby_search_async(body, normalize_fields(fields))
        except _CorePlacesError as exc:
            raise_translated(exc, "nearby_search")
        return self._convert(NearbySearchResult.from_api, data)

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
        try:
            data = await self._inner.place_details_async(
                place_id,
                normalize_fields(fields),
                language,
                region,
                session_token,
            )
        except _CorePlacesError as exc:
            raise_translated(exc, f"place_details place_id={place_id}")
        return self._convert(Place.from_api, data)

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
        try:
            data = await self._inner.autocomplete_async(
                body, normalize_fields(fields)
            )
        except _CorePlacesError as exc:
            raise_translated(exc, "autocomplete")
        return self._convert(AutocompleteResult.from_api, data)

    async def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = None,
        max_height_px: Optional[int] = None,
        skip_http_redirect: bool = False,
    ) -> PhotoMedia | PhotoUriResult:
        """Async version of ``Client.place_photo``."""
        self._validate_int_range("max_width_px", max_width_px, 1, 4800)
        self._validate_int_range("max_height_px", max_height_px, 1, 4800)
        try:
            tagged = await self._inner.place_photo_async(
                photo_name, max_width_px, max_height_px, skip_http_redirect
            )
        except _CorePlacesError as exc:
            raise_translated(exc, f"place_photo name={photo_name}")
        return self._convert(_photo_result, tagged)
