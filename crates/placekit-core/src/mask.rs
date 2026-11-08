//! Field masks, a first-class part of the Places API (New) protocol.
//!
//! Every billable response field must be requested through the
//! `X-Goog-FieldMask` header. [`FieldMask`] validates paths once and renders
//! the header value, and ships curated defaults per endpoint so callers who
//! do not care still get sensible, non-surprising responses.

use crate::errors::Error;

/// Upper bound on the number of paths in one mask (R4-11). The
/// largest curated default, the Place Details default below, holds
/// 72 paths. The bound exists so an unbounded caller supplied list
/// cannot build an unbounded header.
const MAX_MASK_PATHS: usize = 100;

/// Upper bound on the joined `X-Goog-FieldMask` header value, in
/// bytes (R4-11), comfortably above anything the curated defaults or
/// a realistic field list produce and below common header limits.
const MAX_MASK_HEADER_LEN: usize = 4096;

/// Whether one path matches the construction grammar the Python
/// `FieldMask` enforces when a mask is built, read over the byte
/// form the Python layer sends across (Round 54).
///
/// The grammar is the one the Python check has always applied. A
/// path is dot separated segments, and every segment is a camelCase
/// identifier of at least two characters, an ASCII letter followed
/// by ASCII letters and digits. The Python check reaches the same
/// verdict through its own reads, because its opening tests name
/// exactly the characters this grammar excludes. An empty path has
/// one empty segment, a path that begins or ends with whitespace
/// or carries a comma puts a character outside the segment alphabet
/// into some segment, and a wildcard is outside the alphabet too,
/// so the segment test alone decides every case. This grammar is
/// deliberately stricter than the call time grammar [`FieldMask::new`]
/// enforces on paths already built, where one character segments
/// and underscores pass. Construction is where semantic errors such
/// as snake_case names are refused locally, and the two rule sets
/// are not interchangeable.
pub fn valid_path(path: &[u8]) -> bool {
    if path.is_empty() {
        return false;
    }
    path.split(|byte| *byte == b'.').all(|segment| {
        segment.len() >= 2
            && segment[0].is_ascii_alphabetic()
            && segment.iter().all(|byte| byte.is_ascii_alphanumeric())
    })
}

/// The indices of the first occurrence of each distinct path, in
/// first seen order (Round 54).
///
/// This is the duplicate dropping the Python `FieldMask`
/// construction performs, decided over the byte forms as sent. The
/// Python layer stores its own caller objects at these indices, so
/// the mask keeps the first seen object for each distinct path the
/// way the Python dict pass it replaces always did.
pub fn unique_indices(paths: &[Vec<u8>]) -> Vec<usize> {
    let mut seen = std::collections::HashSet::new();
    let mut indices = Vec::new();
    for (index, path) in paths.iter().enumerate() {
        if seen.insert(path.as_slice()) {
            indices.push(index);
        }
    }
    indices
}

/// The order that sorts keyed members the way the set door of the
/// Python `FieldMask.of` sorts them (Round 54).
///
/// Each key is the pair the Python sort key computes, a rank and a
/// byte form. String members carry rank 0 with their own bytes, so
/// they sort among themselves in string order (byte order over the
/// surrogatepass form is code point order), and every other member
/// carries rank 1 with the bytes of its safe repr, so it sorts
/// after the strings by that text and is refused by the constructor
/// afterwards. The sort is stable, so members whose keys compare
/// equal keep their materialised order, as they do under the
/// Python sort.
pub fn sorted_order(keys: &[(u8, Vec<u8>)]) -> Vec<usize> {
    let mut order: Vec<usize> = (0..keys.len()).collect();
    order.sort_by(|a, b| keys[*a].cmp(&keys[*b]));
    order
}

/// A validated set of field paths for one request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FieldMask(Vec<String>);

impl FieldMask {
    /// Build a mask from field paths such as `places.displayName`.
    ///
    /// The final rule set (R4-11), all enforced here, once: the list
    /// is non-empty and holds at most 100 paths; the joined header
    /// value is at most 4096 bytes; no path is duplicated (a mask
    /// is a set); every path is ASCII, contains no whitespace, comma or
    /// control character, and does not begin or end with whitespace;
    /// no dot separated segment of a path is empty; and no segment is
    /// the wildcard `*`, which this grammar does not use: the curated
    /// defaults name every field explicitly, and accepting a wildcard
    /// would let one path silently widen a request to every billable
    /// field. Anything else would corrupt or widen the
    /// `X-Goog-FieldMask` header the paths are joined into.
    pub fn new(paths: Vec<String>) -> Result<Self, Error> {
        if paths.is_empty() {
            return Err(Error::config("field mask must contain at least one path"));
        }
        if paths.len() > MAX_MASK_PATHS {
            return Err(Error::config(format!(
                "field mask holds at most {MAX_MASK_PATHS} paths, got {}",
                paths.len()
            )));
        }
        let mut seen = std::collections::HashSet::new();
        for path in &paths {
            let trimmed = path.trim();
            if trimmed.is_empty()
                || trimmed != path
                || path.contains(',')
                || !path.is_ascii()
                || path.chars().any(|c| c.is_whitespace())
                || path.chars().any(|c| c.is_control())
                || path
                    .split('.')
                    .any(|segment| segment.is_empty() || segment == "*")
                || !seen.insert(path.clone())
            {
                return Err(Error::config(format!("invalid field mask path: {path:?}")));
            }
        }
        let mask = Self(paths);
        if mask.header_value().len() > MAX_MASK_HEADER_LEN {
            return Err(Error::config(format!(
                "field mask header value exceeds {MAX_MASK_HEADER_LEN} bytes"
            )));
        }
        Ok(mask)
    }

    /// The value for the `X-Goog-FieldMask` header.
    pub fn header_value(&self) -> String {
        self.0.join(",")
    }

    /// The individual paths.
    pub fn paths(&self) -> &[String] {
        &self.0
    }

    fn from_static(paths: &[&str]) -> Self {
        Self(paths.iter().map(|s| (*s).to_owned()).collect())
    }

    /// Default mask for Text Search. Covers identity, address, rating and
    /// photos, plus the pagination token.
    pub fn text_search_default() -> Self {
        Self::from_static(&[
            "places.id",
            "places.name",
            "places.displayName",
            "places.formattedAddress",
            "places.location",
            "places.rating",
            "places.userRatingCount",
            "places.types",
            "places.primaryType",
            "places.priceLevel",
            "places.businessStatus",
            "places.photos",
            "nextPageToken",
        ])
    }

    /// Default mask for Nearby Search (which has no pagination token).
    pub fn nearby_search_default() -> Self {
        Self::from_static(&[
            "places.id",
            "places.name",
            "places.displayName",
            "places.formattedAddress",
            "places.location",
            "places.rating",
            "places.userRatingCount",
            "places.types",
            "places.primaryType",
            "places.priceLevel",
            "places.businessStatus",
            "places.photos",
        ])
    }

    /// Default mask for Place Details. Field paths here are unprefixed
    /// because the response is a single place. This is every modelled
    /// field, mirroring `PLACE_DETAILS_FIELDS` in the Python package,
    /// because the method promises full details.
    pub fn place_details_default() -> Self {
        Self::from_static(&[
            "id",
            "name",
            "displayName",
            "formattedAddress",
            "shortFormattedAddress",
            "location",
            "rating",
            "userRatingCount",
            "types",
            "primaryType",
            "priceLevel",
            "businessStatus",
            "photos",
            "nationalPhoneNumber",
            "internationalPhoneNumber",
            "websiteUri",
            "googleMapsUri",
            "regularOpeningHours",
            "currentOpeningHours",
            "currentSecondaryOpeningHours",
            "regularSecondaryOpeningHours",
            "addressComponents",
            "adrFormatAddress",
            "plusCode",
            "postalAddress",
            "primaryTypeDisplayName",
            "viewport",
            "attributions",
            "googleMapsTypeLabel",
            "editorialSummary",
            "iconMaskBaseUri",
            "iconBackgroundColor",
            "openingDate",
            "utcOffsetMinutes",
            "pureServiceAreaBusiness",
            "movedPlace",
            "movedPlaceId",
            "reviews",
            "takeout",
            "delivery",
            "dineIn",
            "curbsidePickup",
            "reservable",
            "servesBreakfast",
            "servesLunch",
            "servesDinner",
            "servesBeer",
            "servesWine",
            "servesBrunch",
            "servesVegetarianFood",
            "outdoorSeating",
            "liveMusic",
            "menuForChildren",
            "servesCocktails",
            "servesDessert",
            "servesCoffee",
            "goodForChildren",
            "allowsDogs",
            "restroom",
            "goodForGroups",
            "goodForWatchingSports",
            "paymentOptions",
            "parkingOptions",
            "accessibilityOptions",
            "timeZone",
            "generativeSummary",
            "reviewSummary",
            "consumerAlert",
            "googleMapsLinks",
            "priceRange",
            "evChargeOptions",
            "addressDescriptor",
        ])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn joins_paths_with_commas() {
        let mask = FieldMask::new(vec![
            "places.id".to_owned(),
            "places.displayName".to_owned(),
        ])
        .unwrap();
        assert_eq!(mask.header_value(), "places.id,places.displayName");
        assert_eq!(mask.paths().len(), 2);
    }

    #[test]
    fn rejects_empty_mask() {
        assert_eq!(FieldMask::new(vec![]).unwrap_err().kind(), "config");
    }

    #[test]
    fn rejects_bad_paths() {
        for bad in ["", " places.id", "places.id ", "places.id,places.name"] {
            let err = FieldMask::new(vec![bad.to_owned()]).unwrap_err();
            assert_eq!(err.kind(), "config", "path {bad:?} should be rejected");
        }
    }

    #[test]
    fn rejects_control_characters() {
        // An interior control character is rejected only by the F13
        // control character clause: it is not whitespace, so the trimmed
        // comparison cannot catch it. (A trailing newline would also be
        // caught by the older trimmed check, so it cannot isolate F13.)
        let err = FieldMask::new(vec!["places.\u{1}id".to_owned()]).unwrap_err();
        assert_eq!(err.kind(), "config");
    }

    #[test]
    fn rejects_interior_whitespace_duplicates_and_bad_segments() {
        // R4-11, one rejected shape per rule: interior whitespace,
        // a duplicated path, an empty segment, a wildcard segment,
        // and a non-ASCII character (which HeaderValue would otherwise
        // pass as obs-text bytes).
        for bad in [
            "places.display Name",
            "places..id",
            ".places.id",
            "places.id.",
            "*",
            "places.*",
            "places.idé",
        ] {
            let err = FieldMask::new(vec![bad.to_owned()]).unwrap_err();
            assert_eq!(err.kind(), "config", "path {bad:?} should be rejected");
        }
        let err = FieldMask::new(vec!["places.id".to_owned(), "places.id".to_owned()]).unwrap_err();
        assert_eq!(err.kind(), "config");
    }

    #[test]
    fn rejects_oversized_masks() {
        // R4-11: the path count and the joined header length are
        // bounded; both constructions fail as config errors.
        let many: Vec<String> = (0..101).map(|i| format!("places.f{i}")).collect();
        assert_eq!(FieldMask::new(many).unwrap_err().kind(), "config");
        let long = vec![format!("places.{}", "x".repeat(5000))];
        assert_eq!(FieldMask::new(long).unwrap_err().kind(), "config");
    }

    #[test]
    fn construction_grammar_accepts_wire_paths() {
        // The valid side of the Python construction check, whose
        // refusals are mirrored in the next test (tests/test_client.py
        // test_field_mask_grammar_rejects_semantic_errors and
        // tests/test_round31.py test_mask_plain_members_behave_as_before).
        for good in [
            "places.displayName",
            "places.id",
            "places.addressComponents",
            "id",
            "name",
            "nextPageToken",
            "ab",
            "aB.cD9",
        ] {
            assert!(valid_path(good.as_bytes()), "path {good:?} should be valid");
        }
    }

    #[test]
    fn construction_grammar_rejects_the_python_refusals() {
        // Mirrors the refusal list of the Python grammar test in
        // tests/test_client.py (snake_case, empty segments, stray
        // punctuation, spaces, wildcards and one letter segments),
        // plus the shapes the core call time grammar test above
        // already names and the non ASCII and surrogate forms the
        // byte crossing can carry.
        for bad in [
            "",
            "a",
            "places.i",
            "a.b",
            "ab.c",
            "places.display_name",
            "places..rating",
            "places.",
            ".places",
            "not a field!!!",
            "a b",
            "not a path",
            "*",
            "places.*",
            " places.id",
            "places.id ",
            "places.id,places.name",
            "places.display Name",
        ] {
            assert!(
                !valid_path(bad.as_bytes()),
                "path {bad:?} should be invalid"
            );
        }
        assert!(!valid_path("places.idé".as_bytes()));
        // A lone surrogate crosses in surrogatepass form as the
        // three bytes ED A0 80, which sit outside the segment
        // alphabet like every other non ASCII byte.
        assert!(!valid_path(b"places.id\xed\xa0\x80"));
    }

    #[test]
    fn construction_grammar_first_byte_rule_and_tail_digits() {
        // The first byte of a segment must be an ASCII letter, a
        // rule the all bytes alphanumeric test behind it cannot
        // state on its own. A digit led segment is long enough
        // and alphanumeric throughout and still refused, in the
        // first segment and in later segments alike, and a
        // segment opening on a multibyte character is refused at
        // the same test. Digits are free in every later position,
        // down to the two byte floor.
        for bad in ["1a", "9abc", "ab.1c", "ab.cd.2e"] {
            assert!(
                !valid_path(bad.as_bytes()),
                "path {bad:?} should be invalid"
            );
        }
        assert!(!valid_path(b"\xc3\xa9b.cd"));
        for good in ["a1", "Z9", "ab.c2"] {
            assert!(valid_path(good.as_bytes()), "path {good:?} should be valid");
        }
    }

    #[test]
    fn construction_grammar_refuses_separator_made_empty_segments() {
        // The split hands the length floor one empty segment for
        // every separator standing at an edge or doubled, and
        // the floor refuses each before the first byte index the
        // census names runs, which is why these shapes answer
        // false rather than panicking. A path of separators
        // alone carries no other content, and doubled separators
        // at the start, the end and the middle each leave their
        // empty segment behind.
        for bad in [".", "..", "...", "..ab", "ab..", "ab...cd", "ab.cd.."] {
            assert!(
                !valid_path(bad.as_bytes()),
                "path {bad:?} should be invalid"
            );
        }
    }

    #[test]
    fn construction_grammar_refuses_bytes_outside_the_segment_alphabet() {
        // The segment alphabet is ASCII letters and digits, and
        // every other byte is refused in a segment. The refusal
        // lists above name the space, the comma, the underscore,
        // the asterisk and the bang and the non ASCII shapes.
        // This test names the rest of the boundary, so an edit
        // that admits one more byte to the alphabet fails here
        // instead of passing both suites in silence. The hyphen
        // and the tab open the list, in a tail, at the head of a
        // segment and across segments.
        for bad in [
            "places.display-name",
            "places.-name",
            "ab.cd-ef",
            "places.display\tname",
            "ab.c\td",
            "places.display+name",
            "places.display/name",
        ] {
            assert!(
                !valid_path(bad.as_bytes()),
                "path {bad:?} should be invalid"
            );
        }
        // The remaining printable punctuation, one tail probe
        // each in a segment that is well formed in every other
        // respect, so the probed byte alone decides the verdict.
        for byte in [
            b'"', b'#', b'$', b'%', b'&', b'\'', b'(', b')', b':', b';', b'<', b'=', b'>', b'?',
            b'@', b'[', b'\\', b']', b'^', b'`', b'{', b'|', b'}', b'~',
        ] {
            let path = [b'a', b'b', byte, b'c', b'd'];
            assert!(
                !valid_path(&path),
                "byte {byte:#04x} should be refused in a segment tail"
            );
        }
        // The control range, the tab inside it, the delete byte
        // and the whole non ASCII range answer the same way.
        for byte in (0x00u8..=0x1f).chain([0x7f]).chain(0x80..=0xff) {
            let path = [b'a', b'b', byte, b'c', b'd'];
            assert!(
                !valid_path(&path),
                "byte {byte:#04x} should be refused in a segment tail"
            );
        }
    }

    #[test]
    fn construction_grammar_accepts_paths_past_the_constructor_caps() {
        // The construction grammar carries no length cap and no
        // segment count cap of its own. The caps live in
        // FieldMask::new, on the joined header value and on the
        // path count of one mask, and the module doc warns the
        // two rule sets are not interchangeable. A single
        // segment far past the header cap and a path holding
        // more segments than the constructor allows in one mask
        // are both well formed here.
        let long_segment = vec![b'a'; 5000];
        assert!(valid_path(&long_segment));
        let many_segments = (0..150).map(|_| "ab").collect::<Vec<_>>().join(".");
        assert!(valid_path(many_segments.as_bytes()));
    }

    #[test]
    fn unique_indices_keeps_first_seen_order() {
        // Mirrors the dedupe half of the Python test
        // test_field_mask_deduplicates_and_set_input_is_deterministic
        // in tests/test_client.py.
        let paths: Vec<Vec<u8>> = ["places.id", "places.id", "places.rating"]
            .iter()
            .map(|s| s.as_bytes().to_vec())
            .collect();
        assert_eq!(unique_indices(&paths), vec![0, 2]);
        let distinct: Vec<Vec<u8>> = ["places.id", "places.rating"]
            .iter()
            .map(|s| s.as_bytes().to_vec())
            .collect();
        assert_eq!(unique_indices(&distinct), vec![0, 1]);
        let repeated: Vec<Vec<u8>> = ["ab", "ab", "ab"]
            .iter()
            .map(|s| s.as_bytes().to_vec())
            .collect();
        assert_eq!(unique_indices(&repeated), vec![0]);
        assert!(unique_indices(&[]).is_empty());
    }

    #[test]
    fn sorted_order_places_strings_first_in_string_order() {
        // Mirrors the set determinism half of the Python test
        // test_field_mask_deduplicates_and_set_input_is_deterministic
        // and the mixed type set ordering behind
        // test_fieldmask_of_mixed_type_set_is_config_error in
        // tests/test_round24.py, where the non string member sorts
        // after every string and is refused by the constructor.
        let keys: Vec<(u8, Vec<u8>)> = [
            (0u8, b"places.rating".to_vec()),
            (0u8, b"places.id".to_vec()),
            (0u8, b"places.name".to_vec()),
        ]
        .to_vec();
        assert_eq!(sorted_order(&keys), vec![1, 2, 0]);
        let mixed: Vec<(u8, Vec<u8>)> =
            [(1u8, b"7".to_vec()), (0u8, b"places.id".to_vec())].to_vec();
        assert_eq!(sorted_order(&mixed), vec![1, 0]);
        // Equal keys keep their materialised order.
        let equal: Vec<(u8, Vec<u8>)> = [(0u8, b"ab".to_vec()), (0u8, b"ab".to_vec())].to_vec();
        assert_eq!(sorted_order(&equal), vec![0, 1]);
        assert!(sorted_order(&[]).is_empty());
    }

    #[test]
    fn defaults_are_valid_and_distinct() {
        let text = FieldMask::text_search_default();
        let nearby = FieldMask::nearby_search_default();
        let details = FieldMask::place_details_default();
        assert!(text.header_value().contains("nextPageToken"));
        assert!(!nearby.header_value().contains("nextPageToken"));
        assert!(details.header_value().starts_with("id,"));
        // Re-validating a default through the checked constructor succeeds.
        assert!(FieldMask::new(details.paths().to_vec()).is_ok());
    }
}
