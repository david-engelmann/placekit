//! Field masks, a first-class part of the Places API (New) protocol.
//!
//! Every billable response field must be requested through the
//! `X-Goog-FieldMask` header. [`FieldMask`] validates paths once and renders
//! the header value, and ships curated defaults per endpoint so callers who
//! do not care still get sensible, non-surprising responses.

use crate::errors::Error;

/// Upper bound on the number of paths in one mask (R4-11). The
/// curated defaults hold at most 14; the bound exists so an unbounded
/// caller supplied list cannot build an unbounded header.
const MAX_MASK_PATHS: usize = 100;

/// Upper bound on the joined `X-Goog-FieldMask` header value, in
/// bytes (R4-11), comfortably above anything the curated defaults or
/// a realistic field list produce and below common header limits.
const MAX_MASK_HEADER_LEN: usize = 4096;

/// A validated set of field paths for one request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FieldMask(Vec<String>);

impl FieldMask {
    /// Build a mask from field paths such as `places.displayName`.
    ///
    /// The final rule set (R4-11), all enforced here, once: the list
    /// is non-empty and holds at most 100 paths; the joined header
    /// value is at most 4096 characters; no path is duplicated (a mask
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
                "field mask header value exceeds {MAX_MASK_HEADER_LEN} characters"
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
    /// because the response is a single place.
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
            "attributions",
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
