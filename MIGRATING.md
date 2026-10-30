# Migrating from python-google-places (googleplaces) to placekit

## Before you port a single line

python-google-places wraps the legacy Places API. That API is feature
frozen and closed to new projects, and Google directs new work to
Places API (New). placekit wraps Places API (New) end to end, so every
call in this guide targets the new API and its response shapes.

This is a port, not a rename. The import changes, the client changes,
and several call shapes change with them.
There is no compatibility facade, and this guide does not assume one.
Code written against the legacy library is rewritten call by call,
and this guide walks that rewrite through the four canonical legacy
examples.

**Four things in the old library have no equivalent anywhere in the
new API, and code that uses them is deleted, not ported.**

- Nearby search keyword and name filters
- Adding and deleting places
- Checkins
- Radar search

String locations are a fifth, softer removal, and they get their own
line. A string location needs coordinates from a geocode step that
placekit does not perform.

Before the examples, one setup pass. Enable Places API (New) on the
Google Cloud project. Install placekit and uninstall
python-google-places, because the two packages answer to different
APIs and keeping both invites importing the wrong one. Python 3.10 or
newer is required. The examples use the placeholder YOUR_API_KEY.

## The five shape changes

Five changes explain almost every edit a port makes. They are stated
here once and then met again inside the examples.

1. Field masks decide what a response carries, and billing follows
   the mask. Each endpoint has a default mask, and the details
   default requests every modelled field. An attribute missing from
   a result is usually a field the mask never asked for.
2. Locations are coordinates. There are no string locations anywhere
   in placekit and no hidden geocode call behind any method. The
   caller supplies latitude and longitude, always.
3. Upgrades are explicit calls that return new objects. A search
   result is a summary, a details call returns a fuller object, and
   nothing mutates in place. Nothing is gated either, and the
   attribute contract below replaces the old gating.
4. The vocabulary was rebuilt. The constants modules exist again,
   with names carried where the concept survived and every value
   checked against the new API tables. A few legacy names and values
   did not survive, and the constants section lists them.
5. Errors are typed. One legacy error class becomes a hierarchy of
   typed exceptions, with the HTTP status and the Google status
   carried as data on the exception instead of buried in message
   text.

## Example 1. The flagship search

The legacy flagship is quoted in full below, exactly as published.
It is Python 2 as published, it is quoted history, and it is not
executed anywhere in this repository.

```python
from googleplaces import GooglePlaces, types, lang

google_places = GooglePlaces(YOUR_API_KEY)

query_result = google_places.nearby_search(
        location='London, England', keyword='Fish and Chips',
        radius=20000, types=[types.TYPE_FOOD])

if query_result.has_attributions:
    print query_result.html_attributions

for place in query_result.places:
    print place.name
    print place.geo_location
    print place.place_id
    place.get_details()
    print place.details
    print place.local_phone_number
    print place.international_phone_number
    print place.website
    print place.url
    for photo in place.photos:
        photo.get(maxheight=500, maxwidth=500)
        photo.mimetype
        photo.url
        photo.filename
        photo.data

if query_result.has_next_page_token:
    query_result_next_page = google_places.nearby_search(
            pagetoken=query_result.next_page_token)
```

The ported flagship follows. It is two searches, because the legacy
call mixed two intents the new API keeps apart, and then the same
result loop with the upgrade made explicit.

```python
from placekit import Client, types

client = Client("YOUR_API_KEY")

# "Fish and Chips" is a text filter. Nearby Search (New) has no text
# filter, so a keyword search is a Text Search now. The string
# location is gone too. The caller supplies coordinates, and the
# search is biased to a circle on London at the old radius.
result = client.text_search(
    "Fish and Chips",
    location_bias={
        "circle": {"center": (51.5074, -0.1278), "radius": 20000.0}
    },
    included_type=types.TYPE_RESTAURANT,
)

# A pure type and radius browse, with no text filter, stays a
# Nearby Search.
browse = client.nearby_search(
    (51.5074, -0.1278),
    20000.0,
    included_types=[types.TYPE_RESTAURANT],
)

for place in result.places:
    # Places from a search are summaries under the field mask. The
    # display name is display_text. The attribute named name is the
    # resource name, not the business name.
    print(place.display_text)
    print(place.location.latitude, place.location.longitude)
    print(place.id)

    # The upgrade is an explicit call, and it returns a new Place.
    # Rebind the variable. The summary object never changes.
    place = client.place_details(place)
    print(place.raw)
    print(place.national_phone_number)
    print(place.international_phone_number)
    print(place.website_uri)
    print(place.google_maps_uri)

    # Attributions ride on each place as typed objects.
    for attribution in place.attributions:
        print(attribution.provider)

    # Photos are fetched through the client, keyed by the photo
    # object itself. The bytes come back on a PhotoMedia.
    for photo in place.photos:
        media = client.place_photo(
            photo, max_width_px=500, max_height_px=500
        )
        print(media.content_type)
        print(len(media.content))
        media.save("photo.jpg")
```

What changed, in the order the code meets it.

- The import and the client name. placekit replaces googleplaces,
  and Client replaces GooglePlaces.
- Print is a function now. The legacy examples are Python 2, and
  every print in the ported code carries parentheses.
- The string location became caller supplied coordinates, and this
  is the single biggest change in the port. London, England becomes
  the pair 51.5074 and -0.1278, and producing that pair from an
  address is a geocode step the caller owns.
- The keyword forced the move to Text Search. Nearby Search in the
  new API accepts no text filter at all, so a keyword search is a
  text_search call, and only the pure browse stays a nearby_search.
- The type filter changed value. Only Table A values may filter a
  search, and the legacy value food is a Table B value, so
  types.TYPE_FOOD is unusable in a request even though the constant
  exists. The port filters on restaurant, a Table A value, and the
  query text carries the broader food intent.
- place.name became display_text. The attribute named name is the
  resource name, a string like places/ChIJrTLr-GyuEmsRBfy61i59si0,
  and display_text is the business name the legacy name printed.
- geo_location became location, and its members are float latitude
  and float longitude instead of a dict of Decimal values.
- place_id became id. The identifier lives on the place itself
  under the shorter name.
- get_details became the rebinding upgrade. place_details returns a
  new Place, the summary object never changes, and the port holds
  the upgrade by rebinding the variable.
- The phone and URL attributes renamed. local_phone_number is
  national_phone_number, international_phone_number keeps its name,
  website is website_uri, and url is google_maps_uri.
- Attributions moved onto each place. There is no result level
  attribution list, and each Place carries typed Attribution
  objects with a provider on them.
- The photo flow became a client call returning a PhotoMedia. The
  bytes are content and the type is content_type. There is no
  server provided filename at all, and save takes the name the
  caller chooses. Dimensions rename to max_width_px and
  max_height_px, and the cap is 4800, up from the legacy 1600.
  Passing the photo object with neither size downloads at the
  photo native width, capped at 4800, so a thumbnail caller passes
  sizes explicitly, as this example does.

## Example 2. Following the next page

The legacy next page flow is the tail of the flagship, quoted here
on its own. It is quoted history and is not executed.

```python
if query_result.has_next_page_token:
    query_result_next_page = google_places.nearby_search(
            pagetoken=query_result.next_page_token)
```

The ported flow follows a Text Search page, because paging exists
only there.

```python
if result.next_page_token:
    next_page = client.text_search(
        "Fish and Chips", page_token=result.next_page_token
    )
```

Three changes hide in those two lines. The boolean property becomes
a truthiness test, and the token itself reads None when no page
remains, where the legacy token default was an empty list. The
parameter renames to page_token, and the original query arguments
may be repeated or omitted, because the token carries the query.
And paging exists only on Text Search. A Nearby Search result has
no next_page_token attribute at all, because the new API returns
one page of at most 20 results by design.

## Example 3. Autocomplete with a country restriction

The legacy autocomplete example is quoted from the legacy reference.
It is quoted history and is not executed.

```python
result = google_places.autocomplete(
    input="Hattie B's", types='establishment',
    components=[('country', 'US')])
for prediction in result.predictions:
    print prediction.description, prediction.place_id
    prediction.get_details()
```

The ported example follows. It adds one duty the legacy library
never had, and the token code is part of the example, not ceremony.

```python
import uuid

from placekit import Client, types

client = Client("YOUR_API_KEY")

# One token per autocomplete session. Generate it, pass it on every
# autocomplete call in the session, and pass the same token on the
# place_details call that closes the session.
session_token = str(uuid.uuid4())

result = client.autocomplete(
    "Hattie B's",
    included_primary_types=[types.TYPE_ESTABLISHMENT],
    included_region_codes=["US"],
    session_token=session_token,
)
for prediction in result.place_predictions:
    print(prediction.text.text)
    print(prediction.place_id)
    details = client.place_details(prediction, session_token=session_token)
    print(details.display_text)
```

What changed, in order. The input keyword became the positional
input_text, so the query text is simply the first argument. The
single types string became included_primary_types, a list of up to
five primary types, and the two search collections survived as
constants, with COLLECTION_CITIES and COLLECTION_REGIONS in
placekit.types standing in for the legacy cities and regions
strings. The components tuples became included_region_codes, a
plain list of region codes.

The predictions list became place_predictions, and query
predictions live in their own list, query_predictions, which fills
only when include_query_predictions is passed. description became
text.text, with text a FormattedText on the prediction.
matched_substrings became text.matches, whose entries carry
start_offset and end_offset, and either offset may be None when
the API returned only one end of a match. terms has no equivalent
at all, and the structured main_text and secondary_text on the
prediction are the replacement shape. One warning deserves its own
sentence. prediction.place is a resource name, not an identifier,
and place_details never reads it, because the resolver takes the
identifier from place_id.

The get_details call became place_details on the prediction object
itself, returning a new Place as in the flagship. Session tokens
are new. One token covers a run of autocomplete calls and the
place_details call that closes it, and Google bills that session
as a unit instead of charging for every call on its own, so a
fresh token per session is the habit this example teaches.

## Example 4. Adding and deleting a place

The last canonical example is short by design. Its legacy block is
quoted in full, and it is quoted history that is not executed.

```python
try:
    added_place = google_places.add_place(
        name='Mom and Pop local store',
        lat_lng={'lat': 51.501984, 'lng': -0.141792},
        accuracy=100, types=types.TYPE_HOME_GOODS_STORE,
        language=lang.ENGLISH_GREAT_BRITAIN)
    print added_place.place_id
    google_places.delete_place(added_place.place_id)
except GooglePlacesError as error_detail:
    print error_detail
```

There is no equivalent in placekit or in Places API (New). The new
API is read only, and no call on the client adds or deletes a
place. Business owners manage listings through Google Business
Profile. The code path is deleted rather than ported, and the same
is true of the other removals this table collects.

| Legacy call or parameter | What replaces it |
| --- | --- |
| checkin, on the client and on Place | Nothing. The endpoint is gone. |
| radar_search | Nothing. The new API has no equivalent. |
| The query alias | Nothing. The searches are text_search and nearby_search. |
| The sensor parameter | Nothing. Google dropped it years ago. |
| The deprecated id and reference identifiers | Nothing. The one identifier is Place.id. |
| geocode_location | Nothing in placekit. The caller supplies coordinates. |

The error half of the legacy block does port, and it ports to a
short block of its own.

```python
from placekit import PlacesError

try:
    client.text_search("Fish and Chips")
except PlacesError as error:
    print(error.status_code, error.google_status)
```

GooglePlacesError becomes the PlacesError hierarchy, each subclass
names a failure class, and the full mapping sits in the errors
section below.

## Reading attributes

This is the contract that replaces gating, and it is the section
to read twice. The legacy library gated its detail attributes.
Reading website, a phone number, or photos on a place raised
GooglePlacesAttributeError until get_details ran on that place,
and the summary attributes silently refilled from the details
payload afterwards. A missing attribute was a loud failure with a
name.

placekit never gates. An attribute the response did not carry
reads None, an empty list, or its empty default, and nothing
raises and nothing is fabricated. The trade is real. The object
cannot say whether the field was unrequested or simply had no
value, and code that relied on the loud failure must learn the
two working habits instead.

The first habit is the raw membership check. When the distinction
matters, test the wire name against the object raw, as in
"websiteUri" in place.raw. A name present in raw was carried by
the response, and a name absent from it was not. The check has
one limit. A modelled field the response carried as an explicit
null, or as an explicitly empty list, loses its key when the core
reserializes the response, so membership is exact for unmodelled
fields and at the model layer rather than through the client for
those two shapes.

The second habit is the upgrade. Call place_details when the full
modelled set is needed, because its default mask requests every
modelled field, and an attribute still reading None on a details
result is a field the API had no value for, within the membership
limit above.

The billing warning belongs here, at the point where the habit
forms. A default place_details call is billed at the Place Details
tier that includes the Atmosphere fields, and doing it inside a
loop over every search result
is the most expensive shape this API offers. Upgrade the places the
caller actually needs, and pass a narrower fields mask when the
full set is not needed.

One sentence on the freeze. Results are frozen value objects,
assignment to an attribute raises, and the rebinding pattern from
Example 1 is the intended way to hold an upgrade.

## Name and shape mapping

One row per legacy name, with the placekit form and the shape
difference where there is one.

| Legacy name | placekit form | Note |
| --- | --- | --- |
| name | display_text | The attribute named name is the resource name. |
| place_id | id | The identifier lives on the place itself. |
| geo_location | location | A LatLng with float latitude and longitude. Decimal arithmetic needs a conversion at the caller boundary. |
| vicinity | short_formatted_address | The short form of the address. |
| formatted_address | formatted_address | The same name, carried on search results as well. |
| local_phone_number | national_phone_number | The number in national format. |
| international_phone_number | international_phone_number | The same name. |
| website | website_uri | The place website as a URI string. |
| url | google_maps_uri | The Google Maps link for the place. |
| details | Typed attributes, then raw | The dict is gone. Read typed attributes first and raw for what is not modelled. |
| rating | rating | Reads None when the API sent none, where the legacy library read an empty string. |
| icon | icon_mask_base_uri and icon_background_color | Typed attributes in the details default mask. The legacy icon was one ready to render URL, and the new pair needs assembly. |
| html_attributions on a result | attributions on each Place | Typed Attribution objects. There is no result level list. |
| photos | photos, fetched with client.place_photo | The fetch returns a PhotoMedia or a PhotoUriResult and stores nothing on the photo. |
| matched_substrings | text.matches | Entries carry start_offset and end_offset, and either may be None. |
| terms | No equivalent | Predictions carry structured main_text and secondary_text instead. |
| description | text.text | The text member of the FormattedText on the prediction. |

## Constants

placekit.types, placekit.lang and placekit.ranking carry the
vocabulary as plain strings, and the client accepts any string in
these slots. The modules are a convenience and a typo guard, not a
gate, and a value the modules have never heard of still passes to
the API untouched.

The ranking rule comes first because it breaks loudly. Legacy
PROMINENCE has no equivalent constant. Nearby Search ranks by
ranking.POPULARITY or ranking.DISTANCE, and Text Search ranks by
ranking.RELEVANCE or ranking.DISTANCE. Legacy lowercase wire
strings raise from the core when pasted, so a copied rank value
fails fast instead of falling back silently.

The filter rule breaks quietly, which is worse. Only Table A
values may filter a search. placekit.types files Table B values
under their own heading, and a Table B constant in included_types
or included_type is refused by the live API even though it passes
every local check. The flagship example meets this rule at the
type filter, and it applies to every Table B value a legacy types
list carried.

The dead list is short and complete. Legacy types address and
grocery_or_supermarket have no placekit constant. Legacy languages
with the codes nn, or, rm and tl have no placekit constant, and
Norwegian is lang.NORWEGIAN with the code no, while lang.FILIPINO
carries the code fil. The legacy misspellings GALICAIN, GUJURATI,
UKRANIAN and AC_TYPE_ADDDRESS are not carried, and the corrected
spellings are GALICIAN, GUJARATI and UKRAINIAN in placekit.lang,
with the autocomplete collections named COLLECTION_CITIES and
COLLECTION_REGIONS in placekit.types.

## Errors

GooglePlacesError arrived as one class with the status in the
message text. placekit raises typed subclasses of PlacesError,
each carrying status_code and google_status as data, and the
mapping from legacy uses is short.

| Legacy GooglePlacesError use | placekit exception |
| --- | --- |
| Quota exhausted or rate limited | RateLimitError, also exported as QuotaError |
| Authentication failure | AuthenticationError |
| Invalid request | InvalidRequestError |
| Place not found | NotFoundError |
| Network failure | NetworkError |
| Local misuse and bad arguments | ConfigError, which subclasses ValueError, so a legacy except ValueError clause still catches placekit argument errors |

GooglePlacesAttributeError has no equivalent, because the gating
it served is gone, and the Reading attributes section above is its
replacement.

## Session tokens

The legacy library predates session tokens, so this duty is new
rather than renamed. An autocomplete session is one token shared
by the autocomplete calls and the closing place_details call, and
Google bills the session as a unit. Tokens are caller generated,
and a UUID is the usual shape. place_details and autocomplete both
accept session_token, and Example 3 is the worked form.

## What a search result carries

Two result levels exist and they carry different fields. A search
result carries the search default fields and reads everything else
under the attribute contract, as None, an empty list, or an empty
default. A details result carries every modelled field the API had
values for. The fields migrants most often reach for on the wrong
level are website_uri, the phone numbers, opening hours, reviews
and the full address components, and each of them belongs to the
details level. Reviews are typed Place.reviews in the details
default and absent from search results under the default masks.

## Port checklist

- [ ] Swap the import and the client.
- [ ] Replace string locations with coordinates from a geocode step of your own.
- [ ] Move keyword searches to Text Search.
- [ ] Change filter values to Table A values.
- [ ] Rebind upgrades instead of mutating.
- [ ] Replace attribute guards with the reading contract.
- [ ] Thread a session token through autocomplete.
- [ ] Delete the removed endpoints.
- [ ] Rename the error clauses.
- [ ] Pass language explicitly where output depends on it.
