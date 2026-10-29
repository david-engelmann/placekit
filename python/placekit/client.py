"""Sync and async clients for the Google Places API (New).

Both clients share one Rust core and one method set. ``Client`` blocks and
is safe to use from ordinary scripts; ``AsyncClient`` awaits and is the one
to use inside an event loop. Methods return the typed models in
``placekit.models`` and raise the exceptions in ``placekit.exceptions``.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from . import _placekit
from ._placekit import PlacesError as _CorePlacesError
from .exceptions import raise_translated
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


class _Base:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key must not be empty")
        self._inner = _placekit.Client(api_key, base_url, timeout)

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
                "maxResultCount": max_results,
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
                "maxResultCount": max_results,
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
    seconds.
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
            raise_translated(exc)
        return TextSearchResult.from_api(data)

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
            raise_translated(exc)
        return NearbySearchResult.from_api(data)

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
            raise_translated(exc)
        return Place.from_api(data)

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
            raise_translated(exc)
        return AutocompleteResult.from_api(data)

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
        try:
            tagged = self._inner.place_photo(
                photo_name, max_width_px, max_height_px, skip_http_redirect
            )
        except _CorePlacesError as exc:
            raise_translated(exc)
        return _photo_result(tagged)


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
            raise_translated(exc)
        return TextSearchResult.from_api(data)

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
            raise_translated(exc)
        return NearbySearchResult.from_api(data)

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
            raise_translated(exc)
        return Place.from_api(data)

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
            raise_translated(exc)
        return AutocompleteResult.from_api(data)

    async def place_photo(
        self,
        photo_name: str,
        *,
        max_width_px: Optional[int] = None,
        max_height_px: Optional[int] = None,
        skip_http_redirect: bool = False,
    ) -> PhotoMedia | PhotoUriResult:
        """Async version of ``Client.place_photo``."""
        try:
            tagged = await self._inner.place_photo_async(
                photo_name, max_width_px, max_height_px, skip_http_redirect
            )
        except _CorePlacesError as exc:
            raise_translated(exc)
        return _photo_result(tagged)
