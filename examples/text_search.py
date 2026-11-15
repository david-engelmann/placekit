"""Search for places and read the first result in full.

Every example runs offline against responses recorded from the live
API, so the output shown is a real response body and no Google API
key is needed. Run it from anywhere with placekit installed:

    python examples/text_search.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from offline_stub import serve

from placekit import Client


def main():
    server, base_url = serve()
    try:
        client = Client("recorded-offline", base_url=base_url)
        result = client.text_search("cafes in Sydney")
        for place in result.places:
            print(place.display_text, place.rating, place.formatted_address)
        details = client.place_details(result.places[0])
        print(details.national_phone_number, details.website_uri)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
