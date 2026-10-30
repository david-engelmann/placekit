"""placekit: a modern client for the Google Places API (New).

The HTTP and protocol layer is a Rust core (reqwest with rustls, typed
requests, typed errors). This package wraps it in a Python surface with a
sync ``Client``, an ``AsyncClient`` with the same methods, and dataclass
response models.

>>> from placekit import Client
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
    AccessibilityOptions,
    AddressComponent,
    AddressDescriptor,
    Area,
    Attribution,
    AuthorAttribution,
    AutocompleteResult,
    ConsumerAlert,
    ConnectorAggregation,
    Date,
    EvChargeOptions,
    FormattedText,
    GenerativeSummary,
    GoogleMapsLinks,
    Landmark,
    LatLng,
    Leg,
    LocalizedText,
    Money,
    NearbySearchResult,
    OpeningHours,
    OpeningPoint,
    ParkingOptions,
    PaymentOptions,
    Period,
    Photo,
    PhotoMedia,
    PhotoUriResult,
    Place,
    PlacePrediction,
    PlusCode,
    PostalAddress,
    PriceRange,
    QueryPrediction,
    Review,
    ReviewSummary,
    RoutingSummary,
    SpecialDay,
    StringMatch,
    Suggestion,
    TextSearchResult,
    TimeZone,
    Viewport,
)
from . import lang, ranking, types

try:
    from importlib.metadata import PackageNotFoundError, version as _metadata_version

    __version__ = _metadata_version("placekit")
except PackageNotFoundError:  # pragma: no cover, only hit in uninstalled source trees
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
    "AccessibilityOptions",
    "AutocompleteResult",
    "AddressComponent",
    "AddressDescriptor",
    "Area",
    "ConsumerAlert",
    "ConnectorAggregation",
    "Date",
    "EvChargeOptions",
    "FormattedText",
    "GenerativeSummary",
    "GoogleMapsLinks",
    "Landmark",
    "LatLng",
    "Leg",
    "LocalizedText",
    "Money",
    "NearbySearchResult",
    "OpeningHours",
    "OpeningPoint",
    "ParkingOptions",
    "PaymentOptions",
    "Period",
    "Photo",
    "PhotoMedia",
    "PhotoUriResult",
    "Place",
    "PlacePrediction",
    "PlusCode",
    "PostalAddress",
    "PriceRange",
    "QueryPrediction",
    "Review",
    "ReviewSummary",
    "RoutingSummary",
    "SpecialDay",
    "StringMatch",
    "Suggestion",
    "TextSearchResult",
    "TimeZone",
    "Viewport",
    "lang",
    "ranking",
    "types",
    "__version__",
]
