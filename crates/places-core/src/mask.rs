//! Field masks, a first-class part of the Places API (New) protocol.
//!
//! Every billable response field must be requested through the
//! `X-Goog-FieldMask` header. [`FieldMask`] validates paths once and renders
//! the header value, and ships curated defaults per endpoint so callers who
//! do not care still get sensible, non-surprising responses.

use crate::errors::Error;

/// A validated set of field paths for one request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FieldMask(Vec<String>);

impl FieldMask {
    /// Build a mask from field paths such as `places.displayName`.
    ///
    /// Fails on an empty list, an empty path, or a path containing a comma
    /// or whitespace (all of which would corrupt the header).
    pub fn new(paths: Vec<String>) -> Result<Self, Error> {
        if paths.is_empty() {
            return Err(Error::config("field mask must contain at least one path"));
        }
        for path in &paths {
            let trimmed = path.trim();
            if trimmed.is_empty() || trimmed != path || path.contains(',') {
                return Err(Error::config(format!("invalid field mask path: {path:?}")));
            }
        }
        Ok(Self(paths))
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
