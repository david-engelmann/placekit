# placekit documentation

The README carries the install path and the quickstart. This folder carries the reference and the two long guides, one file per subject.

- [Endpoints](endpoints.md) names the five calls, what each returns, the keyword arguments each one takes, and the worked passages on paging, opening hours, session tokens, and autocomplete predictions.
- [Field masks](field-masks.md) covers mask construction, the curated defaults and their billing tiers, the identity floor on details masks, and how to read attributes the mask did not request.
- [Constants](constants.md) covers the type, language, and ranking vocabularies in `placekit.types`, `placekit.lang`, and `placekit.ranking`, and the one refusal those slots make.
- [Addresses](addresses.md) covers the `placekit.address` readers, city resolution across the two carrier sets, and how far the stated per country answers reach.
- [Errors](errors.md) covers the exception hierarchy, how classification reads the Google envelope before the HTTP code, and the attributes every API exception carries.
- [Migrating from python-google-places](MIGRATING.md) walks the four canonical legacy examples across to placekit call by call, with the name mapping, the attribute reading contract, and the removals named plainly.
- [Normalizing addresses with placekit](NORMALIZATION.md) teaches the address handling the recorded corpus and the address module embody, with an oddities catalogue, per country readings, and worked recipes that run against the recorded fixtures.

The [examples](../examples/) folder holds complete tasks that run offline against recorded responses, with no Google API key needed.
