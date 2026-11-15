# Endpoints

| Method | Endpoint | Returns |
| --- | --- | --- |
| `text_search` | `POST /v1/places:searchText` | `TextSearchResult` with a `next_page_token` for paging |
| `nearby_search` | `POST /v1/places:searchNearby` | `NearbySearchResult` |
| `place_details` | `GET /v1/places/{id}` | `Place` |
| `autocomplete` | `POST /v1/places:autocomplete` | `AutocompleteResult` split into place and query predictions |
| `place_photo` | `GET /v1/{photo}/media` | `PhotoMedia` with the image bytes, or `PhotoUriResult` carrying `photo_uri` when `skip_http_redirect=True` |

The search and autocomplete calls take the filters their endpoints offer as keyword arguments. Text Search accepts `page_size`, `min_rating`, `open_now`, `price_levels`, `strict_type_filtering`, `included_type`, the `location_bias` and `location_restriction` shapes, `ev_options`, `search_along_route`, `routing_parameters`, `include_pure_service_area_businesses` and `include_future_opening_businesses`. Nearby Search accepts `included_types`, `excluded_types`, `included_primary_types` and `excluded_primary_types` beside `max_results` and `routing_parameters`, and it accepts `include_future_opening_businesses` as well. Autocomplete accepts `origin`, `input_offset`, `included_primary_types`, `included_region_codes` and `include_query_predictions` beside its input, together with the `location_bias` and `location_restriction` shapes and the `include_pure_service_area_businesses` and `include_future_opening_businesses` switches. Each of those calls and Place Details also accepts `region`, a CLDR region code such as `AU` naming the region a request is centered on. `price_levels` takes a list of the API price level values, `PRICE_LEVEL_FREE`, `PRICE_LEVEL_INEXPENSIVE`, `PRICE_LEVEL_MODERATE`, `PRICE_LEVEL_EXPENSIVE` and `PRICE_LEVEL_VERY_EXPENSIVE`, the same strings a place carries on its `price_level` attribute.

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

