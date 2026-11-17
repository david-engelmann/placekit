"""Handle placekit errors by type.

Every example runs offline against responses recorded from the live
API, so the output shown is a real response body and no Google API
key is needed. The stub serves its recorded quota error for a query
carrying the TRIGGER_QUOTA marker and its recorded not found error
for the place id "missing-place". Run it from anywhere with
placekit installed:

    python examples/error_handling.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from offline_stub import serve

from placekit import Client, NotFoundError, RateLimitError


def main():
    server, base_url = serve()
    try:
        client = Client("recorded-offline", base_url=base_url)
        try:
            client.text_search("TRIGGER_QUOTA cafes")
        except RateLimitError as exc:
            print("quota", exc.status_code, exc.google_status, exc.retry_after)
            print("quota message", exc.server_message)
            for entry in exc.quota_violation_entries:
                print("quota violation", entry["quota_metric"], entry["quota_value"])
        try:
            client.place_details("missing-place")
        except NotFoundError as exc:
            print("not found", exc.status_code, exc.google_status)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
