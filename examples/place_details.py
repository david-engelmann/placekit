"""Read one place in full, including its address and opening hours.

Every example runs offline against responses recorded from the live
API, so the output shown is a real response body and no Google API
key is needed. Run it from anywhere with placekit installed:

    python examples/place_details.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from offline_stub import serve

from placekit import Client, address


def main():
    server, base_url = serve()
    try:
        client = Client("recorded-offline", base_url=base_url)
        result = client.text_search("cafes in Sydney")
        place = client.place_details(result.places[0])
        city = address.resolve_city(place)
        print("city", city.value, city.carrier, city.confidence)
        print("country", address.country_code(place))
        if place.current_opening_hours is not None:
            print("open now", place.current_opening_hours.open_now)
            for line in place.current_opening_hours.weekday_descriptions:
                print(line)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
