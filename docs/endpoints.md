# Endpoints

| Method | Endpoint | Returns |
| --- | --- | --- |
| `text_search` | `POST /v1/places:searchText` | `TextSearchResult` with a `next_page_token` for paging |
| `nearby_search` | `POST /v1/places:searchNearby` | `NearbySearchResult` |
| `place_details` | `GET /v1/places/{id}` | `Place` |
| `autocomplete` | `POST /v1/places:autocomplete` | `AutocompleteResult` split into place and query predictions |
| `place_photo` | `GET /v1/{photo}/media` | `PhotoMedia` with the image bytes, or `PhotoUriResult` carrying `photo_uri` when `skip_http_redirect=True` |

The search and autocomplete calls take the filters their endpoints offer as keyword arguments. Text Search accepts `page_size`, `min_rating`, `open_now`, `price_levels`, `strict_type_filtering`, `included_type`, the `location_bias` and `location_restriction` shapes, `ev_options`, `search_along_route`, `routing_parameters`, `include_pure_service_area_businesses` and `include_future_opening_businesses`. Nearby Search accepts `included_types`, `excluded_types`, `included_primary_types` and `excluded_primary_types` beside `max_results` and `routing_parameters`, and it accepts `include_future_opening_businesses` as well. Autocomplete accepts `origin`, `input_offset`, `included_primary_types`, `included_region_codes` and `include_query_predictions` beside its input, together with the `location_bias` and `location_restriction` shapes and the `include_pure_service_area_businesses` and `include_future_opening_businesses` switches. Each of those calls and Place Details also accepts `region`, a CLDR region code such as `AU` naming the region a request is centered on. `price_levels` takes a list of the API price level values, `PRICE_LEVEL_FREE`, `PRICE_LEVEL_INEXPENSIVE`, `PRICE_LEVEL_MODERATE`, `PRICE_LEVEL_EXPENSIVE` and `PRICE_LEVEL_VERY_EXPENSIVE`, the same strings a place carries on its `price_level` attribute.

Four of the five calls, both searches, Place Details and Autocomplete, also accept `language`, a language code from `placekit.lang` naming the language results come back in. Both searches accept `rank_preference`, which orders the results by relevance or by distance on Text Search and by distance or popularity on Nearby Search. Nearby Search takes its center and radius as positional arguments before the keyword arguments. The first is the location, a `LatLng`, a (latitude, longitude) tuple or list, or a latitude and longitude mapping, and the second is the radius in meters. Omitting `fields` on a search or details call sends that endpoint's curated default mask. Autocomplete has no curated default, so omitting `fields` there sends no field mask header at all and the API default field set governs what is billed and returned.

A downloaded photo arrives as `PhotoMedia`, whose `content` attribute carries the image bytes and whose `content_type` attribute carries the response content type. `place_photo` requires at least one of `max_width_px` and `max_height_px` when the photo is passed by name, and a call by name with neither raises `ConfigError` before any request. A photo passed as a `Photo` object defaults one size from its own dimensions when neither is given.

The result and place models expose their decoders as public `from_api` class methods, the same decoders the client calls use, so a response dict a caller already holds can be decoded without a client call. The decoders read strictly, so a value of the wrong kind in a slot raises `DecodeError` instead of being converted, and a dict decoded directly gets the same verdicts a client call would give it. The downloaded photo form is the exception, since its content bytes are the body and there is no dict to decode.

A text search result also carries a `search_uri`, and both search results carry `routing_summaries`, the typed routing summaries for the call, when the response includes them.

Text Search results page through `next_page_token`. Pass it back as `page_token` on the same Text Search call to fetch the next page.

```python
page = client.text_search("cafes in Sydney")
while page.next_page_token:
    page = client.text_search("cafes in Sydney", page_token=page.next_page_token)
```

Stop when the returned token is absent or repeats the one just used, so a server that hands back the same token cannot hold the loop open.

A details result carries the opening hours the API returned for the place. The hours object sits at `current_opening_hours`, which is the attribute spelling of the wire field `currentOpeningHours`, one field under two spellings, the wire spelling in a field mask and the attribute spelling on the result. The regular hours object sits at `regular_opening_hours`, the wire name alias for `opening_hours`, beside the current hours object the example below reads. Its open state sits at `current_opening_hours.open_now`, and the same object carries `weekday_descriptions`, the week's hours as one text line per day. Both levels of the path can be None on a given place, the hours object when the response carried no hours and `open_now` itself when hours arrived without a state, so the example checks the hours object before reading it, and `open_now` can still be None and prints as None.

```python
result = client.text_search("cafes in Sydney")
details = client.place_details(result.places[0])
if details.current_opening_hours is not None:
    print(details.current_opening_hours.open_now)
    for line in details.current_opening_hours.weekday_descriptions:
        print(line)
```

Autocomplete and Place Details both accept `session_token`. One token ties a run of autocomplete calls to the details call that closes the session, and that grouping is the shape the API bills as one session, so an autocomplete flow in production should mint a fresh token for each session and pass it to both calls. Tokens are caller generated rather than minted by placekit, and a UUID is the usual shape.

An autocomplete result carries its predictions on two members, `place_predictions` and `query_predictions`, both read off its `suggestions`, the full list of suggestion objects the response carried. A prediction's `text` is an optional `FormattedText` rather than a plain string, so the read guards it first. The display string sits at `prediction.text.text`, and the ranges where the input matched inside that string sit at `prediction.text.matches`.

```python
result = client.autocomplete("Bianco")
for prediction in result.place_predictions:
    if prediction.text is not None:
        print(prediction.text.text)
```

