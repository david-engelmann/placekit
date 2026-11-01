from dataclasses import dataclass
from typing import ClassVar, Optional, Sequence

from .models import AddressComponent, Place, PlusCode, PostalAddress

CARRIER_LOCALITY: str
CARRIER_POSTAL_TOWN: str
CARRIER_SUBLOCALITY_LEVEL_1: str
CARRIER_SUBLOCALITY_LEVEL_2: str
CARRIER_SUBLOCALITY_LEVEL_3: str
CARRIER_SUBLOCALITY_LEVEL_4: str
CARRIER_SUBLOCALITY_LEVEL_5: str
CARRIER_NEIGHBORHOOD: str
CARRIER_ADMINISTRATIVE_AREA_LEVEL_1: str
CARRIER_ADMINISTRATIVE_AREA_LEVEL_2: str
CARRIER_POSTAL_ADDRESS_LOCALITY: str
CARRIER_POSTAL_ADDRESS_SUBLOCALITY: str
CARRIER_POSTAL_ADDRESS_ADMINISTRATIVE_AREA: str
CARRIER_POSTAL_ADDRESS_POSTAL_CODE: str
CARRIER_POSTAL_ADDRESS_REGION_CODE: str
CARRIER_POSTAL_CODE_COMPONENT: str
CARRIER_BOTH_POSTAL: str
CARRIER_COUNTRY_COMPONENT: str

CONFIDENCE_PRIMARY: str
CONFIDENCE_FALLBACK: str
CONFIDENCE_CONTESTED: str
CONFIDENCE_HEURISTIC: str
CONFIDENCE_NONE: str
CONFIDENCE_GRADES: frozenset[str]

POSTAL_PRESENT: str
POSTAL_ABSENT: str

PRECEDENCE_COUNTRIES: frozenset[str]
CONTESTED_COUNTRIES: frozenset[str]


@dataclass(frozen=True, slots=True)
class CityResolution:
    __match_args__: ClassVar[tuple[str, ...]] = (
        "value",
        "carrier",
        "confidence",
        "country_code",
        "competing_value",
        "competing_carrier",
    )
    value: Optional[str]
    carrier: Optional[str]
    confidence: str
    country_code: Optional[str]
    competing_value: Optional[str]
    competing_carrier: Optional[str]
    def __init__(
        self,
        value: Optional[str],
        carrier: Optional[str],
        confidence: str,
        country_code: Optional[str] = ...,
        competing_value: Optional[str] = ...,
        competing_carrier: Optional[str] = ...,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class DistrictResolution:
    __match_args__: ClassVar[tuple[str, ...]] = (
        "value",
        "carrier",
        "confidence",
        "country_code",
    )
    value: Optional[str]
    carrier: Optional[str]
    confidence: str
    country_code: Optional[str]
    def __init__(
        self,
        value: Optional[str],
        carrier: Optional[str],
        confidence: str,
        country_code: Optional[str] = ...,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class PostalCodeResult:
    __match_args__: ClassVar[tuple[str, ...]] = (
        "value",
        "carrier",
        "status",
        "country_code",
        "competing_value",
        "competing_carrier",
    )
    value: Optional[str]
    carrier: Optional[str]
    status: str
    country_code: Optional[str]
    competing_value: Optional[str]
    competing_carrier: Optional[str]
    def __init__(
        self,
        value: Optional[str],
        carrier: Optional[str],
        status: str,
        country_code: Optional[str] = ...,
        competing_value: Optional[str] = ...,
        competing_carrier: Optional[str] = ...,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class PlusCodeParts:
    __match_args__: ClassVar[tuple[str, ...]] = ("code_part", "locality_text")
    code_part: str
    locality_text: Optional[str]
    def __init__(
        self, code_part: str, locality_text: Optional[str]
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AddressFlags:
    __match_args__: ClassVar[tuple[str, ...]] = (
        "has_street_number",
        "has_route",
        "has_premise",
        "has_subpremise",
        "is_premise_level",
        "spans_multiple_routes",
        "has_no_street_level",
        "has_postal_code",
        "has_postal_address",
        "has_country",
        "has_city_carrier",
    )
    has_street_number: bool
    has_route: bool
    has_premise: bool
    has_subpremise: bool
    is_premise_level: bool
    spans_multiple_routes: bool
    has_no_street_level: bool
    has_postal_code: bool
    has_postal_address: bool
    has_country: bool
    has_city_carrier: bool
    def __init__(
        self,
        has_street_number: bool,
        has_route: bool,
        has_premise: bool,
        has_subpremise: bool,
        is_premise_level: bool,
        spans_multiple_routes: bool,
        has_no_street_level: bool,
        has_postal_code: bool,
        has_postal_address: bool,
        has_country: bool,
        has_city_carrier: bool,
    ) -> None: ...


def find_component(
    components: Sequence[AddressComponent], type_name: str
) -> Optional[AddressComponent]: ...


def find_components(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[AddressComponent, ...]: ...


def component_long_text(
    components: Sequence[AddressComponent], type_name: str
) -> Optional[str]: ...


def component_short_text(
    components: Sequence[AddressComponent], type_name: str
) -> Optional[str]: ...


def component_long_texts(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[str, ...]: ...


def component_short_texts(
    components: Sequence[AddressComponent], type_name: str
) -> tuple[str, ...]: ...


def untyped_components(
    components: Sequence[AddressComponent],
) -> tuple[AddressComponent, ...]: ...


def country_code(place: Place) -> Optional[str]: ...


def country_code_from_components(
    components: Sequence[AddressComponent],
) -> Optional[str]: ...


def administrative_area(place: Place) -> Optional[str]: ...


def postal_code(place: Place) -> PostalCodeResult: ...


def postal_code_from_components(
    components: Sequence[AddressComponent],
) -> Optional[str]: ...


def postal_code_from_postal_address(
    postal_address: Optional[PostalAddress],
) -> Optional[str]: ...


def resolve_city(place: Place) -> CityResolution: ...


def city_resolutions(place: Place) -> tuple[CityResolution, ...]: ...


def resolve_district(place: Place) -> DistrictResolution: ...


def address_flags(place: Place) -> AddressFlags: ...


def has_street_number(components: Sequence[AddressComponent]) -> bool: ...


def has_route(components: Sequence[AddressComponent]) -> bool: ...


def has_premise(components: Sequence[AddressComponent]) -> bool: ...


def has_subpremise(components: Sequence[AddressComponent]) -> bool: ...


def is_premise_level(place: Place) -> bool: ...


def spans_multiple_routes(components: Sequence[AddressComponent]) -> bool: ...


def has_no_street_level(components: Sequence[AddressComponent]) -> bool: ...


def split_plus_code(plus_code: Optional[PlusCode]) -> Optional[PlusCodeParts]: ...


def split_compound_code(compound_code: Optional[str]) -> Optional[PlusCodeParts]: ...


def postal_locality(postal_address: Optional[PostalAddress]) -> Optional[str]: ...


def postal_sublocality(postal_address: Optional[PostalAddress]) -> Optional[str]: ...


def postal_administrative_area(
    postal_address: Optional[PostalAddress],
) -> Optional[str]: ...


def postal_region_code(postal_address: Optional[PostalAddress]) -> Optional[str]: ...


__all__ = [
    "CARRIER_ADMINISTRATIVE_AREA_LEVEL_1",
    "CARRIER_ADMINISTRATIVE_AREA_LEVEL_2",
    "CARRIER_BOTH_POSTAL",
    "CARRIER_COUNTRY_COMPONENT",
    "CARRIER_LOCALITY",
    "CARRIER_NEIGHBORHOOD",
    "CARRIER_POSTAL_ADDRESS_ADMINISTRATIVE_AREA",
    "CARRIER_POSTAL_ADDRESS_LOCALITY",
    "CARRIER_POSTAL_ADDRESS_POSTAL_CODE",
    "CARRIER_POSTAL_ADDRESS_REGION_CODE",
    "CARRIER_POSTAL_ADDRESS_SUBLOCALITY",
    "CARRIER_POSTAL_CODE_COMPONENT",
    "CARRIER_POSTAL_TOWN",
    "CARRIER_SUBLOCALITY_LEVEL_1",
    "CARRIER_SUBLOCALITY_LEVEL_2",
    "CARRIER_SUBLOCALITY_LEVEL_3",
    "CARRIER_SUBLOCALITY_LEVEL_4",
    "CARRIER_SUBLOCALITY_LEVEL_5",
    "CONFIDENCE_CONTESTED",
    "CONFIDENCE_FALLBACK",
    "CONFIDENCE_GRADES",
    "CONFIDENCE_HEURISTIC",
    "CONFIDENCE_NONE",
    "CONFIDENCE_PRIMARY",
    "CONTESTED_COUNTRIES",
    "POSTAL_ABSENT",
    "POSTAL_PRESENT",
    "PRECEDENCE_COUNTRIES",
    "AddressFlags",
    "CityResolution",
    "DistrictResolution",
    "PlusCodeParts",
    "PostalCodeResult",
    "address_flags",
    "administrative_area",
    "city_resolutions",
    "component_long_text",
    "component_long_texts",
    "component_short_text",
    "component_short_texts",
    "country_code",
    "country_code_from_components",
    "find_component",
    "find_components",
    "has_no_street_level",
    "has_premise",
    "has_route",
    "has_street_number",
    "has_subpremise",
    "is_premise_level",
    "postal_administrative_area",
    "postal_code",
    "postal_code_from_components",
    "postal_code_from_postal_address",
    "postal_locality",
    "postal_region_code",
    "postal_sublocality",
    "resolve_city",
    "resolve_district",
    "spans_multiple_routes",
    "split_compound_code",
    "split_plus_code",
    "untyped_components",
]
