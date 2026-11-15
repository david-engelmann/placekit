# Constants

Three modules carry the vocabularies callers pass most often, as plain strings that drop into the existing parameters. `placekit.types` holds the place type vocabulary from the official Place Types page, `placekit.lang` holds the supported language codes, and `placekit.ranking` holds the ranking preferences split by method, because Text Search and Nearby Search accept different sets.

```python
from placekit import lang, ranking, types

result = client.nearby_search(
    (-33.8668, 151.2071),
    800.0,
    included_types=[types.TYPE_CAFE],
    language=lang.ENGLISH,
    rank_preference=ranking.DISTANCE,
)
```

The modules are snapshots of the official tables and a convenience only. The client accepts any string in the type and language slots, including values this version has never heard of, so a type or language the API adds tomorrow works without waiting for a placekit release. The one refusal in those slots is a string carrying control characters or unpaired surrogates, which fails locally with a `ConfigError` naming the argument. The ranking slots are the exception, because the ranking preferences form a closed set in the API, and an unknown ranking value fails locally with a `ConfigError` naming the values the endpoint accepts.

