# placekit examples

Complete tasks that run offline against responses recorded from the live API, so the output shown is a real response body and no Google API key is needed.

Each example starts the small local stub in `offline_stub.py`, which serves the recorded responses in `fixtures/` and honours the field mask header the way the real API does, then points a client at it through the `base_url` argument. The same stub serves the test suite, where it lives as `tests/conftest.py`.

- `text_search.py` searches and reads the first result in full.
- `place_details.py` reads one place in full, with its address readers and opening hours.
- `error_handling.py` handles a quota error and a not found error by type.

Run any of them from a checkout or an installed environment:

```bash
python examples/text_search.py
```
