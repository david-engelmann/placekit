# Field masks

The Places API (New) only returns the fields named in the `X-Goog-FieldMask` header, and billing follows the fields requested. placekit treats the mask as a typed feature instead of a string you assemble by hand.

```python
from placekit import FieldMask

result = client.text_search(
    "cafes in Sydney",
    fields=FieldMask("places.displayName", "places.rating"),
)
```

Any iterable of path strings works too, and `FieldMask.of` builds a mask from any such iterable, passing a mask it is handed through unchanged. A mask carries its joined header form on `FieldMask.header_value`, the value sent in the `X-Goog-FieldMask` header. Omit `fields` on a search or details call and that endpoint uses a curated default, available as `FieldMask.text_search()`, `FieldMask.nearby_search()`, and `FieldMask.place_details()`. The `normalize_fields` helper in `placekit.fields` turns a fields argument into the plain list of paths it carries, or None when no fields argument was given. Autocomplete takes an optional `fields` mask with no curated default behind it, and `place_photo` takes no `fields` argument at all.

One billing note on the defaults. They include fields from the Enterprise billing tier, among them rating, user rating counts and price level, so a search call with a default mask is billed at the Enterprise tier. Place Details is the exception. Its default mask requests every modelled field, including current opening hours from the higher Enterprise plus Atmosphere tier, so a default `place_details` call is billed at that tier. Pass a narrower `fields` set when you want a lower tier.

Two facts about details masks belong beside that invitation. The path root differs by endpoint. Search and nearby masks name their paths under the `places` prefix, as the example above does, while place details mask paths are bare field names with no prefix, so the details form of the example above is `FieldMask("id", "displayName", "rating")`. A details mask must also still name `id` or `name`, the two identity paths. Drop both and the call raises `DecodeError` even on a well-formed response, because a details result carrying no identity is the wrong shape entirely rather than a place with unrequested attributes. The curated details default names both, so the floor only bites a hand-built narrower mask.

### Reading attributes the mask did not request

A place from a search call only carries the fields the search mask asked for. Reading an attribute outside the mask gives None, an empty list, or an empty default, never an error and never a fabricated value, and the object cannot say whether the field was unrequested or simply had no value. The `raw` attribute on every model is the response body itself rather than a reserialization of the typed fields, so a name sits in `raw` exactly when the response carried that field, and membership in `raw` is an exact record of what arrived. The one exception is `PhotoMedia`, the downloaded photo form, which carries no `raw` because its content bytes are the body. Two habits follow. Check membership in `raw` with the wire name when the distinction matters. Call `place_details` with the place when the full modelled set is needed, since its default mask requests every modelled field.

