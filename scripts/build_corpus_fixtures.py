"""Build the recorded corpus fixtures from the live smoke cassettes.

The script is the only author of recorded fixture bytes. It reads the
exchange files in the two live smoke session folders, selects the places
each spec names, applies the named trims and the redaction rule from the
Round 13 design record as amended by the parent ruling, and writes each
fixture in the canonical form the legacy fixtures use, meaning sorted
keys, compact separators, escaped non ASCII text, one line, and no
trailing newline.

Trims are limited to the two the record allows. The top level
nextPageToken value is removed, and every photos array is cut back to
its first entry. The original length of every trimmed array is recorded
in the facts the script prints, and no other path is trimmed.

Redaction follows the parent ruling. Inside every author attribution
object, in review author attributions and in photo author attributions
alike, the display name, the profile URI, and the photo URI are replaced
with shape preserving synthetic values on the example domain. Review
text and original review text are replaced with synthetic text of the
same character length carrying the same language code, and the original
length is recorded in the facts. Every replaced path is recorded.

The redactor works by key, so a post redaction scan walks every
finished fixture without trusting key names and refuses the build on
anything the redactor could not see. An attribution shaped object
under any key or container must hold only synthetic values in its
identity fields, no contributor shaped URI may survive anywhere, and
review text inside any review shaped container must sit in the
synthetic form or the build fails. The scan runs on every build, in
verify mode as well, because both modes share the build path.

Usage, from the repo root.

    python3 scripts/build_corpus_fixtures.py --cassettes DIR [--facts FILE]
    python3 scripts/build_corpus_fixtures.py --cassettes DIR --verify [--manifest FILE]

The cassettes directory holds the two session folders named 2026-10-30
and 2026-10-31-session2. Verify mode rebuilds every fixture in memory
and compares the bytes and the recomputed facts against the shipped
files and, when a manifest is given, against the manifest entries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SESSION_FOLDERS = {"S1": "2026-10-30", "S2": "2026-10-31-session2"}

# Each spec names one output file, the cassette it is drawn from, and the
# place ids the excerpt keeps. Details specs keep the whole body, so their
# selector holds the single place id of the body itself. Search selectors
# list ids in the order the body carries them.
SPECS = [
    {"file": "recorded_A2_no_locality_sublocality_city.json", "session": "S1", "exchange": "02_exchange.json", "ids": ["ChIJzRBPAz5ZwokRd0AUXGm-2f8"]},
    {"file": "recorded_P4_temporarily_closed.json", "session": "S1", "exchange": "03_exchange.json", "ids": ["ChIJzw3eiINbwokRKCVwMLN501M"]},
    {"file": "recorded_V1_rating_absent_against_whole.json", "session": "S1", "exchange": "03_exchange.json", "ids": ["ChIJL-0tDU9bwokRNIqrbAnPVuc", "ChIJTSFxKQBbwokRnlW6hfLADH8"]},
    {"file": "recorded_P8_search_depth_no_rating.json", "session": "S1", "exchange": "03_exchange.json", "ids": ["ChIJTSFxKQBbwokRnlW6hfLADH8"]},
    {"file": "recorded_P15_details_depth_saigon.json", "session": "S2", "exchange": "01_exchange.json", "ids": ["ChIJV4k8_9UodTERU5KXbkYpSYs"]},
    {"file": "recorded_H10_seasonal_offset_sample.json", "session": "S2", "exchange": "01_exchange.json", "ids": ["ChIJV4k8_9UodTERU5KXbkYpSYs"]},
    {"file": "recorded_P12_contained_place.json", "session": "S2", "exchange": "02_exchange.json", "ids": ["ChIJ8WvuSB7Lj4ARFyHppkxDRQ4"]},
    {"file": "recorded_P15_richest_mall_store.json", "session": "S2", "exchange": "02_exchange.json", "ids": ["ChIJ8WvuSB7Lj4ARFyHppkxDRQ4"]},
    {"file": "recorded_P7_no_photos_key.json", "session": "S2", "exchange": "03_exchange.json", "ids": ["ChIJqXbFE1vGwoARUN09pf8FYqM"]},
    {"file": "recorded_P10_ev_charging_full_detail.json", "session": "S2", "exchange": "03_exchange.json", "ids": ["ChIJqy0cdk3GwoARVLngjTmC44A"]},
    {"file": "recorded_P11_fuel_options.json", "session": "S2", "exchange": "04_exchange.json", "ids": ["ChIJA6GX3IEzsYkRz8NMql4bGB8"]},
    {"file": "recorded_H1_open_24_hours.json", "session": "S2", "exchange": "05_exchange.json", "ids": ["ChIJdzXgRn8E9YgRZCIoanr8GPw"]},
    {"file": "recorded_H2_split_hours.json", "session": "S2", "exchange": "06_exchange.json", "ids": ["ChIJ-RAVYVVQqEcRIfxE6EjRZ38"]},
    {"file": "recorded_H3_overnight_hours.json", "session": "S2", "exchange": "06_exchange.json", "ids": ["ChIJZ5QEJ19PqEcR0ciT7zE11sE"]},
    {"file": "recorded_H6_truncated_period_points.json", "session": "S2", "exchange": "06_exchange.json", "ids": ["ChIJZ5QEJ19PqEcR0ciT7zE11sE"]},
    {"file": "recorded_V11_next_open_time_populated.json", "session": "S2", "exchange": "06_exchange.json", "ids": ["ChIJywdI5etRqEcRUVD-ycuGL6M"]},
    {"file": "recorded_V3_top_price_levels.json", "session": "S2", "exchange": "06_exchange.json", "ids": ["ChIJA-K5lEpQqEcRHGv7ScsVIXs"]},
    {"file": "recorded_H8_fractional_utc_offset.json", "session": "S2", "exchange": "07_exchange.json", "ids": ["ChIJKc7950UZ6zkRIDoTfViKQyw"]},
    {"file": "recorded_H9_extreme_utc_offset.json", "session": "S2", "exchange": "08_exchange.json", "ids": ["ChIJoeTv8C6iAnoR6m3PZFxVVxM"]},
    {"file": "recorded_A5_sublocality_chains.json", "session": "S2", "exchange": "10_exchange.json", "ids": ["ChIJzVXOw5SPGGAR7yVtRAihT7o"]},
    {"file": "recorded_A6_japanese_block_addressing.json", "session": "S2", "exchange": "10_exchange.json", "ids": ["ChIJzVXOw5SPGGAR7yVtRAihT7o"]},
    {"file": "recorded_A13_premise_and_subpremise.json", "session": "S2", "exchange": "10_exchange.json", "ids": ["ChIJUXs3NtOPGGARhehCaUQo5J8"]},
    {"file": "recorded_A8_tokyo_japanese.json", "session": "S2", "exchange": "10_exchange.json", "ids": ["ChIJzVXOw5SPGGAR7yVtRAihT7o"]},
    {"file": "recorded_A8_tokyo_english.json", "session": "S2", "exchange": "11_exchange.json", "ids": ["ChIJzVXOw5SPGGAR7yVtRAihT7o"]},
    {"file": "recorded_A7_rtl_script_address.json", "session": "S2", "exchange": "12_exchange.json", "ids": ["ChIJ4TyFlYFCXz4RNMf0stgxhLc", "ChIJUUpqvgVDXz4RgVl27UZC1ko"]},
    {"file": "recorded_A9_country_without_postal_codes.json", "session": "S2", "exchange": "12_exchange.json", "ids": ["ChIJ98qoMwBDXz4RXUcEE0Tvwug"]},
    {"file": "recorded_A3_postal_town_carries_city.json", "session": "S2", "exchange": "13_exchange.json", "ids": ["ChIJGZS3NZwlcUgRZF3cPB1OFGk"]},
    {"file": "recorded_A4_locality_postal_town_disagree.json", "session": "S2", "exchange": "13_exchange.json", "ids": ["ChIJGZS3NZwlcUgRZF3cPB1OFGk"]},
    {"file": "recorded_A12_long_village_name.json", "session": "S2", "exchange": "14_exchange.json", "ids": ["ChIJaXoVnASpZUgRwmxnGAkXgx4", "ChIJ6UJwtHmpZUgR0gUI1R5g0D4"]},
    {"file": "recorded_P8_details_depth_no_rating.json", "session": "S2", "exchange": "16_exchange.json", "ids": ["ChIJS_zBNNbXAhURy-FuRT5ib9k"]},
    {"file": "recorded_A10_jerusalem_no_region_code.json", "session": "S2", "exchange": "16_exchange.json", "ids": ["ChIJS_zBNNbXAhURy-FuRT5ib9k"]},
    {"file": "recorded_A10_jerusalem_region_ps.json", "session": "S2", "exchange": "17_exchange.json", "ids": ["ChIJS_zBNNbXAhURy-FuRT5ib9k"]},
    {"file": "recorded_V10_long_form_place_id.json", "session": "S2", "exchange": "21_exchange.json", "ids": ["EiZXaWxsaWFtc2J1cmcgQnJpZGdlLCBOZXcgWW9yaywgTlksIFVTQSIuKiwKFAoSCccn3dnXW8KJEdugE_vLf17YEhQKEgk7CD_TpU_CiRFi_nfhBo8LyA"]},
    {"file": "recorded_A1_no_street_number.json", "session": "S2", "exchange": "21_exchange.json", "ids": ["EiZXaWxsaWFtc2J1cmcgQnJpZGdlLCBOZXcgWW9yaywgTlksIFVTQSIuKiwKFAoSCccn3dnXW8KJEdugE_vLf17YEhQKEgk7CD_TpU_CiRFi_nfhBo8LyA"]},
    {"file": "recorded_P1_no_address_natural_feature.json", "session": "S2", "exchange": "22_exchange.json", "ids": ["ChIJvZ69FaJU6DkRsrqrBvjcdgU"]},
    {"file": "recorded_V5_plus_code_global_only.json", "session": "S2", "exchange": "22_exchange.json", "ids": ["ChIJvZ69FaJU6DkRsrqrBvjcdgU"]},
    {"file": "recorded_P2_transit_station.json", "session": "S2", "exchange": "23_exchange.json", "ids": ["ChIJhRwB-yFawokRi0AhGH87UTc"]},
    {"file": "recorded_H7_secondary_hours.json", "session": "S2", "exchange": "24_exchange.json", "ids": ["ChIJjWm3wdJzToYR8efPhAe5lzY"]},
    {"file": "recorded_H11_description_order_vs_period_anchor.json", "session": "S2", "exchange": "25_exchange.json", "ids": ["ChIJV4k8_9UodTERU5KXbkYpSYs"]},
    {"file": "recorded_OBS1_requested_field_vanishes.json", "session": "S2", "exchange": "26_exchange.json", "ids": ["ChIJx7K17Ji3t4kRr3VvqMTw7cc"]},
    {"file": "recorded_OBS2_pure_service_area_depth_split.json", "session": "S2", "exchange": "20_exchange.json", "ids": ["ChIJkaUn1JPTD4gR7ZWpE9cCuow"]},
]

REVIEW_PHRASES = {
    "en": "Example review text. ",
    "de": "Beispieltext einer Bewertung. ",
}

ATTRIBUTION_FIELDS = ("displayName", "uri", "photoUri")


def canonical_bytes(obj) -> bytes:
    return json.dumps(
        obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_text(length: int, language_code) -> str:
    phrase = REVIEW_PHRASES.get(language_code or "en", REVIEW_PHRASES["en"])
    if length <= 0:
        return ""
    repeats = length // len(phrase) + 1
    return (phrase * repeats)[:length]


class Redactor:
    """Applies the redaction rule and records every replaced path."""

    def __init__(self):
        self.counter = 0
        self.paths: list[str] = []
        self.review_text_lengths: dict[str, int] = {}

    def _attribution(self, obj: dict, path: str):
        unknown = set(obj) - set(ATTRIBUTION_FIELDS)
        if unknown:
            raise SystemExit(
                f"attribution object at {path} carries unknown fields {sorted(unknown)}"
            )
        self.counter += 1
        n = self.counter
        if "displayName" in obj:
            obj["displayName"] = f"Example Author {n}"
            self.paths.append(f"{path}.displayName")
        if "uri" in obj:
            obj["uri"] = f"https://example.com/contributors/{n}"
            self.paths.append(f"{path}.uri")
        if "photoUri" in obj:
            obj["photoUri"] = f"https://example.com/contributors/{n}/photo"
            self.paths.append(f"{path}.photoUri")

    def _review(self, review: dict, path: str):
        for member in ("text", "originalText"):
            sub = review.get(member)
            if isinstance(sub, dict) and isinstance(sub.get("text"), str):
                original = sub["text"]
                self.review_text_lengths[f"{path}.{member}.text"] = len(original)
                self.paths.append(f"{path}.{member}.text")
                sub["text"] = synthetic_text(len(original), sub.get("languageCode"))
        self._walk(review, path)

    def _walk(self, node, path: str):
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{path}.{key}" if path else key
                if key == "authorAttribution" and isinstance(value, dict):
                    self._attribution(value, child)
                elif key == "authorAttributions" and isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            self._attribution(item, f"{child}[{i}]")
                elif key == "reviews" and isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            self._review(item, f"{child}[{i}]")
                else:
                    self._walk(value, child)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                self._walk(item, f"{path}[{i}]")

    def apply(self, body: dict):
        self._walk(body, "")
        return self


# The post redaction scan. The redactor works by key, so its coverage
# depends on the cassette carrying attribution objects and reviews in
# the canonical shapes. The scan works by shape and by value instead.
# It walks the finished body without trusting any key name, and the
# build refuses on anything it finds, so a renamed, pluralised, or
# singular key and a noncanonical container buy a hostile or future
# cassette nothing.

CONTRIBUTOR_URI_MARKERS = ("googleusercontent.com", "ggpht.com", "/maps/contrib/")
REVIEW_CONTAINER_KEYS = ("reviews", "review")
REVIEW_MARKER_KEYS = (
    "authorAttribution",
    "authorAttributions",
    "rating",
    "publishTime",
    "relativePublishTimeDescription",
)
SYNTHETIC_NAME_FORM = re.compile(r"^Example Author [0-9]+$")
SYNTHETIC_URI_PREFIX = "https://example.com/contributors/"


def _contributor_shaped(value: str) -> bool:
    return any(marker in value for marker in CONTRIBUTOR_URI_MARKERS)


def _synthetic_attribution_value(field: str, value) -> bool:
    if field == "displayName":
        return isinstance(value, str) and bool(SYNTHETIC_NAME_FORM.match(value))
    return isinstance(value, str) and value.startswith(SYNTHETIC_URI_PREFIX)


def scan_for_survivors(body) -> list[str]:
    """List anything personal the redactor may have missed.

    Three nets, none of them keyed on the canonical placements. Any
    string carrying a contributor shaped URI is a survivor, whatever
    holds it. Any object carrying a profile URI field, a photo URI
    field, or two or more of the identity fields is attribution
    shaped, and every identity field it carries must hold the
    synthetic form. Any review text inside a review shaped container
    must sit in the synthetic form, and string form review text is a
    survivor on sight, because the redaction always writes the dict
    form. A review shaped container is a value under a review key or
    an object carrying one of the review marker keys.
    """
    survivors: list[str] = []

    def walk(node, path: str, in_review: bool):
        if isinstance(node, str):
            if _contributor_shaped(node):
                survivors.append(f"contributor shaped URI survives at {path}")
            return
        if isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]", in_review)
            return
        if not isinstance(node, dict):
            return
        identity = [field for field in ATTRIBUTION_FIELDS if field in node]
        if "uri" in node or "photoUri" in node or len(identity) >= 2:
            for field in identity:
                if not _synthetic_attribution_value(field, node[field]):
                    survivors.append(
                        f"attribution field {field} survives unredacted at {path}"
                    )
        review_shaped = in_review or any(key in node for key in REVIEW_MARKER_KEYS)
        if review_shaped:
            for member in ("text", "originalText"):
                if member not in node:
                    continue
                value = node[member]
                member_path = f"{path}.{member}" if path else member
                if isinstance(value, str):
                    survivors.append(
                        f"review text survives in string form at {member_path}"
                    )
                elif isinstance(value, dict) and isinstance(value.get("text"), str):
                    inner = value["text"]
                    if inner != synthetic_text(len(inner), value.get("languageCode")):
                        survivors.append(
                            f"review text survives unredacted at {member_path}.text"
                        )
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            # Nothing below a text member needs the review context.
            # The member itself was judged above, at its parent.
            child_in_review = (
                in_review or key in REVIEW_CONTAINER_KEYS
            ) and key not in ("text", "originalText")
            walk(value, child, child_in_review)

    walk(body, "", False)
    return survivors


def trim_photos(node, path: str, trims: list):
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            if key == "photos" and isinstance(value, list) and len(value) > 1:
                trims.append(
                    {"path": child, "kind": "array_cut_to_first", "original_length": len(value)}
                )
                node[key] = value[:1]
            else:
                trim_photos(value, child, trims)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            trim_photos(item, f"{path}[{i}]", trims)


def check_preserved(source, fixture, path: str, trims: list, redacted: set):
    """Assert nothing outside the named trims and redactions changed.

    Walks the selected source object and the finished fixture side by
    side. Scalars must match in type and value, which is the check that
    a whole number can never be silently rewritten with a trailing
    fraction by the excerpt step.
    """
    trim_paths = {t["path"] for t in trims}
    if path in redacted:
        assert type(source) is type(fixture), f"type changed at {path}"
        return
    if isinstance(source, dict):
        assert isinstance(fixture, dict), f"shape changed at {path}"
        for key, value in source.items():
            child = f"{path}.{key}" if path else key
            if child in trim_paths and child == "nextPageToken":
                assert key not in fixture, f"trimmed token still present at {child}"
                continue
            assert key in fixture, f"key lost at {child}"
            check_preserved(value, fixture[key], child, trims, redacted)
    elif isinstance(source, list):
        assert isinstance(fixture, list), f"shape changed at {path}"
        if path in trim_paths:
            assert len(fixture) == 1, f"trimmed array not cut to one at {path}"
            check_preserved(source[0], fixture[0], f"{path}[0]", trims, redacted)
            return
        assert len(source) == len(fixture), f"array length changed at {path}"
        for i, (s_item, f_item) in enumerate(zip(source, fixture)):
            check_preserved(s_item, f_item, f"{path}[{i}]", trims, redacted)
    else:
        assert type(source) is type(fixture), (
            f"scalar type changed at {path}, {type(source).__name__} to {type(fixture).__name__}"
        )
        assert source == fixture, f"scalar value changed at {path}"


def endpoint_name(request: dict) -> str:
    path = request.get("path", "")
    if "searchText" in path:
        return "searchText"
    if "searchNearby" in path:
        return "searchNearby"
    if "autocomplete" in path:
        return "autocomplete"
    return "placeDetails"


def build_one(cassette_root: Path, spec: dict):
    folder = cassette_root / SESSION_FOLDERS[spec["session"]]
    exchange = json.loads((folder / spec["exchange"]).read_text())
    request = exchange["request"]
    source_body = exchange["response"]["body"]
    source_hash = sha256_hex(canonical_bytes(source_body))

    import copy

    body = copy.deepcopy(source_body)
    if "places" in body:
        wanted = list(spec["ids"])
        selected = [p for p in body["places"] if p.get("id") in wanted]
        found = [p.get("id") for p in selected]
        if found != wanted:
            raise SystemExit(
                f"{spec['file']}, selector mismatch, wanted {wanted}, body order gives {found}"
            )
        body = {"places": selected}
        if "nextPageToken" in source_body:
            body["nextPageToken"] = source_body["nextPageToken"]
    else:
        if body.get("id") != spec["ids"][0]:
            raise SystemExit(
                f"{spec['file']}, details id mismatch, wanted {spec['ids'][0]}, body has {body.get('id')}"
            )

    trims: list = []
    if isinstance(body, dict) and "nextPageToken" in body:
        del body["nextPageToken"]
        trims.append({"path": "nextPageToken", "kind": "value_removed"})
    trim_photos(body, "", trims)

    preserved_source = copy.deepcopy(body)
    redactor = Redactor().apply(body)

    check_preserved(
        preserved_source, body, "", trims, set(redactor.paths)
    )

    survivors = scan_for_survivors(body)
    if survivors:
        raise SystemExit(
            f"{spec['file']}, post redaction scan refuses the build, "
            + ", ".join(survivors)
        )

    data = canonical_bytes(body)
    facts = {
        "file": spec["file"],
        "session": spec["session"],
        "exchange": spec["exchange"],
        "endpoint": endpoint_name(request),
        "request_mask": request.get("field_mask"),
        "selector_place_ids": list(spec["ids"]),
        "source_body_sha256": source_hash,
        "fixture_sha256": sha256_hex(data),
        "size_bytes": len(data),
        "trims": trims,
        "redaction_paths": redactor.paths,
        "review_text_lengths": redactor.review_text_lengths,
    }
    return data, facts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cassettes", required=True)
    parser.add_argument("--out", default="tests/fixtures/recorded")
    parser.add_argument("--facts", default=None)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args()

    cassette_root = Path(args.cassettes)
    out_dir = Path(args.out)
    all_facts = []
    failures = []

    for spec in SPECS:
        data, facts = build_one(cassette_root, spec)
        all_facts.append(facts)
        target = out_dir / spec["file"]
        if args.verify:
            if not target.exists():
                failures.append(f"{spec['file']}, missing on disk")
            elif target.read_bytes() != data:
                failures.append(f"{spec['file']}, bytes differ from rebuild")
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text())
        by_file = {}
        for case in manifest.get("cases", []):
            for fixture in case.get("fixtures", []):
                by_file[fixture["file"]] = fixture
        for obs in manifest.get("observations", []):
            if obs.get("fixture"):
                by_file[obs["fixture"]] = obs
        for facts in all_facts:
            entry = by_file.get(facts["file"])
            if entry is None:
                failures.append(f"{facts['file']}, no manifest entry")
                continue
            for field in (
                "source_body_sha256",
                "fixture_sha256",
                "size_bytes",
                "session",
                "exchange",
                "endpoint",
                "request_mask",
            ):
                if entry.get(field) != facts[field]:
                    failures.append(
                        f"{facts['file']}, manifest {field} is {entry.get(field)!r}, rebuild gives {facts[field]!r}"
                    )
            if entry.get("selector_place_ids") != facts["selector_place_ids"]:
                failures.append(f"{facts['file']}, manifest selector differs")
            if entry.get("trims") != facts["trims"]:
                failures.append(f"{facts['file']}, manifest trims differ")
            redactions = entry.get("redactions") or {}
            if redactions.get("paths") != facts["redaction_paths"]:
                failures.append(f"{facts['file']}, manifest redaction paths differ")
            if redactions.get("review_text_lengths") != facts["review_text_lengths"]:
                failures.append(f"{facts['file']}, manifest review text lengths differ")

    if args.facts:
        Path(args.facts).write_text(json.dumps(all_facts, indent=2) + "\n")

    total = sum(f["size_bytes"] for f in all_facts)
    print(f"fixtures built, {len(all_facts)}, total bytes, {total}")
    for facts in all_facts:
        print(
            f"{facts['file']}, {facts['size_bytes']} bytes, redactions {len(facts['redaction_paths'])}, trims {len(facts['trims'])}"
        )
    if failures:
        print("VERIFY FAILURES")
        for failure in failures:
            print(f"  {failure}")
        return 1
    if args.verify:
        print("verify ok, every shipped fixture rebuilds byte identically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
