# Addresses

`placekit.address` reads the structured address a place already carries and answers the questions its two carrier sets raise. It looks components up by type and has a reader for the components that carry no type at all, reads the country with `country_code` and the postal code with `postal_code` across both carrier sets, reads the administrative area from the components alone with its postal counterpart read by the separate `postal_administrative_area` reader, and splits plus codes from a plus code object or a compound code string. Its `postal_code` reader returns a `PostalCodeResult` that carries the value with its carrier, a present or absent status, and any competing value the other carrier set holds, and the postal address readers read the second carrier set on its own terms. `country_code` returns a plainer shape than that, the region code itself as a plain string or None when neither carrier set yields one, with no result object to unpack and no value member to read off it. Presence helpers and an `address_flags` summary answer the shape questions about a place. City resolution is the careful part, because which carrier holds the city changes by country and the carriers sometimes disagree on the same place, so `resolve_city` returns the value with the carrier it came from and a confidence grade in the open.

```python
from placekit import Client, address

client = Client("YOUR_API_KEY")
result = client.text_search("cafes in Sydney")
place = client.place_details(result.places[0])

city = address.resolve_city(place)
city.value, city.carrier, city.confidence
code = address.country_code(place)
```

The details call in that example is load bearing. These readers read the address a place carries, and a bare search result carrying neither address components nor a postal address gives them nothing to read, so the same calls over such a result answer quietly instead, a city resolution carrying no value and a country code of None, and no error marks the difference.

`city_resolutions` returns every reading a place supports, and where the carriers disagree the reading carries its rival on the result itself, as `competing_value` and `competing_carrier`. A British place whose locality and postal town differ therefore hands back both values with the rivalry visible, instead of one value with the other hidden.

Stated answers ship for Japan and the United Arab Emirates and the United Kingdom, each built from recorded places inside one sampled locality, and every other country follows a generic fallback chain capped at the heuristic grade. The module never parses formatted text and never composes a display address, and a resolved city is a reading of one response rather than a fact of the same kind as a place ID.

The normalization guide teaches the address handling the recorded corpus and this module embody, with an oddities catalogue of the shapes the corpus actually returned, per country readings that state how far each one reaches, worked recipes that run against the recorded fixtures, and a list of the things no helper here can promise.

[Normalizing addresses with placekit](NORMALIZATION.md)

