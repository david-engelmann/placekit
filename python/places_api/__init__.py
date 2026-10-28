"""places_api: a modern client for the Google Places API (New).

The HTTP and protocol layer is a Rust core (reqwest with rustls, typed
requests, typed errors). This package wraps it in a Python surface with a
sync ``Client``, an ``AsyncClient`` with the same methods, and dataclass
response models.

>>> from places_api import Client
>>> client = Client("YOUR_API_KEY")
>>> cafe = client.text_search("cafe in Sydney").places[0]
>>> cafe.display_text, cafe.rating
('Bianco Latte', 4.6)
"""

from .client import AsyncClient, Client
from .exceptions import (
    ApiError,
    AuthenticationError,
    ConfigError,
    DecodeError,
    InvalidRequestError,
    NetworkError,
    NotFoundError,
    PlacesError,
    QuotaError,
    RateLimitError,
)
from .fields import FieldMask
from .models import (
    Attribution,
    AuthorAttribution,
    AutocompleteResult,
    FormattedText,
    LatLng,
    LocalizedText,
    NearbySearchResult,
    OpeningHours,
    Photo,
    PhotoMedia,
    Place,
    PlacePrediction,
    StringMatch,
    Suggestion,
    TextSearchResult,
)

try:
    from importlib.metadata import version as _metadata_version

    __version__ = _metadata_version("places-api")
except Exception:  # pragma: no cover, only hit in uninstalled source trees
    __version__ = "0.1.0"

__all__ = [
    "AsyncClient",
    "Client",
    "FieldMask",
    "ApiError",
    "AuthenticationError",
    "ConfigError",
    "DecodeError",
    "InvalidRequestError",
    "NetworkError",
    "NotFoundError",
    "PlacesError",
    "QuotaError",
    "RateLimitError",
    "Attribution",
    "AuthorAttribution",
    "AutocompleteResult",
    "FormattedText",
    "LatLng",
    "LocalizedText",
    "NearbySearchResult",
    "OpeningHours",
    "Photo",
    "PhotoMedia",
    "Place",
    "PlacePrediction",
    "StringMatch",
    "Suggestion",
    "TextSearchResult",
    "__version__",
]
