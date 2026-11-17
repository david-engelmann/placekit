"""The model field inventory, compared across its three homes.

Audit A50-057. The response model inventory is written in
python/placekit/models.py (the dataclasses), again in
python/placekit/models.pyi (the stubs), and in subset in
crates/placekit-core/src/models.rs (the core structs). The
core types only the fields it reads itself, 27 on Place, and
the rest ride its flattened extra map to the Python decode,
so the core inventory is a deliberate subset, not a copy.
What no shipped test compared before this file is that the
three writings agree where they claim to. The stub must
mirror the dataclasses field for field, and every field the
core types under a shared model name must exist on the
Python model of that name, under two standing renames the
exception table below records. Drift in any of the three
degrades silently into the extra map, so the comparison is
the pin.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path

from placekit import models

ROOT = Path(__file__).resolve().parent.parent

# The core structs that share a name with a Python model, as
# an explicit list, so renaming a model on either side fails
# here instead of shrinking the compared set in silence.
SHARED_MODELS = {
    "AddressComponent",
    "Attribution",
    "AuthorAttribution",
    "Date",
    "FormattedText",
    "LatLng",
    "LocalizedText",
    "OpeningHours",
    "OpeningPoint",
    "Period",
    "Photo",
    "Place",
    "PlacePrediction",
    "PlusCode",
    "PostalAddress",
    "StringMatch",
    "Suggestion",
    "Viewport",
}

# The standing renames between the core field name and the
# Python attribute name, each with its reason. An entry is
# consumed only while the core field it names still stands,
# which the test asserts, so the table cannot go stale.
CORE_FIELD_EXCEPTIONS = {
    # The wire name is regularOpeningHours. The Python public
    # name is the shorter opening_hours, a deliberate public
    # surface choice.
    ("Place", "regular_opening_hours"): "opening_hours",
    # The core flattens the structured format onto the
    # prediction (main_text and secondary_text), where Python
    # carries the two texts as fields of their own. The value
    # None records a shape difference, not a rename.
    ("PlacePrediction", "structured_format"): None,
}


def _python_inventory() -> dict[str, set[str]]:
    inventory = {}
    for name in dir(models):
        obj = getattr(models, name)
        if (
            isinstance(obj, type)
            and dataclasses.is_dataclass(obj)
            and obj.__module__ == models.__name__
        ):
            inventory[name] = {field.name for field in dataclasses.fields(obj)}
    return inventory


def _stub_inventory() -> dict[str, set[str]]:
    tree = ast.parse((ROOT / "python" / "placekit" / "models.pyi").read_text())
    inventory = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields = set()
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(
                stmt.target, ast.Name
            ):
                if stmt.target.id.startswith("_"):
                    continue
                if "ClassVar" in ast.unparse(stmt.annotation):
                    continue
                fields.add(stmt.target.id)
        inventory[node.name] = fields
    return inventory


def _core_inventory() -> dict[str, set[str]]:
    source = (ROOT / "crates" / "placekit-core" / "src" / "models.rs").read_text()
    inventory = {}
    for match in re.finditer(r"pub struct (\w+) \{", source):
        name = match.group(1)
        depth, index = 1, match.end()
        while depth and index < len(source):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
            index += 1
        body = source[match.end() : index - 1]
        fields = set(re.findall(r"^\s+pub (\w+):", body, re.M))
        if fields:
            inventory[name] = fields
    return inventory


def test_stub_inventory_matches_the_dataclasses():
    python = _python_inventory()
    stub = _stub_inventory()
    assert set(stub) == set(python)
    for name in python:
        assert stub[name] == python[name], name


def test_core_inventory_is_a_subset_of_the_python_inventory():
    python = _python_inventory()
    core = _core_inventory()
    shared = set(python) & set(core)
    assert shared == SHARED_MODELS
    consumed = set()
    for name in sorted(shared):
        core_fields = core[name] - {"extra"}
        python_fields = python[name] - {"raw"}
        for field in sorted(core_fields - python_fields):
            key = (name, field)
            assert key in CORE_FIELD_EXCEPTIONS, (
                f"core {name}.{field} has no Python counterpart "
                "and no recorded exception"
            )
            consumed.add(key)
    assert consumed == set(CORE_FIELD_EXCEPTIONS)
