from dataclasses import dataclass
from typing import Iterable, Tuple, Union

__all__ = [
    "MAX_MATERIALIZED_ITEMS",
    "NEARBY_SEARCH_FIELDS",
    "PLACE_DETAILS_FIELDS",
    "TEXT_SEARCH_FIELDS",
    "FieldMask",
    "FieldsLike",
    "normalize_fields",
]

MAX_MATERIALIZED_ITEMS: int

TEXT_SEARCH_FIELDS: Tuple[str, ...]
NEARBY_SEARCH_FIELDS: Tuple[str, ...]
PLACE_DETAILS_FIELDS: Tuple[str, ...]

@dataclass(frozen=True, slots=True)
class FieldMask:
    paths: Tuple[str, ...]
    def __init__(self, *paths: str) -> None: ...
    @property
    def header_value(self) -> str: ...
    @classmethod
    def of(cls, paths: Iterable[str] | "FieldMask") -> "FieldMask": ...
    @classmethod
    def text_search(cls) -> "FieldMask": ...
    @classmethod
    def nearby_search(cls) -> "FieldMask": ...
    @classmethod
    def place_details(cls) -> "FieldMask": ...

FieldsLike = Union[FieldMask, Iterable[str], None]

def normalize_fields(fields: FieldsLike) -> list[str] | None: ...
