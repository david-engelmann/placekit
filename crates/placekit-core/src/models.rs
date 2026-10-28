//! Request and response types for the Places API (New).
//!
//! Requests serialize to the exact JSON bodies the API expects. Responses
//! deserialize leniently: every field is optional or defaulted, and unknown
//! fields are preserved in a flattened `extra` map on [`Place`], so new API
//! fields never break decoding or get silently dropped.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

// ---------------------------------------------------------------------------
// Shared building blocks
// ---------------------------------------------------------------------------

/// A latitude/longitude pair.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct LatLng {
    pub latitude: f64,
    pub longitude: f64,
}

/// A text value paired with its language.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalizedText {
    pub text: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
}

/// A circular area, used to bias or restrict searches.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Circle {
    pub center: LatLng,
    /// Radius in meters, at most 50000.
    pub radius: f64,
}

/// A `locationRestriction` value holding a single circle.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LocationRestriction {
    pub circle: Circle,
}

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

/// Rank preference for Text Search.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TextSearchRankPreference {
    Relevance,
    Distance,
}

/// Rank preference for Nearby Search.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum NearbySearchRankPreference {
    Distance,
    Popularity,
}

/// Body of a `places:searchText` request.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TextSearchRequest {
    pub text_query: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_result_count: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page_token: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub region_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rank_preference: Option<TextSearchRankPreference>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open_now: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub price_levels: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub strict_type_filtering: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub included_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location_bias: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location_restriction: Option<Value>,
}

/// Body of a `places:searchNearby` request.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NearbySearchRequest {
    pub location_restriction: LocationRestriction,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub included_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub excluded_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub included_primary_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_result_count: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub region_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rank_preference: Option<NearbySearchRankPreference>,
}

/// Body of a `places:autocomplete` request.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AutocompleteRequest {
    pub input: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub region_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub session_token: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub included_region_codes: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_query_predictions: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location_bias: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location_restriction: Option<Value>,
}

// ---------------------------------------------------------------------------
// Responses
// ---------------------------------------------------------------------------

/// A photo attached to a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Photo {
    /// Resource name, for example `places/{id}/photos/{ref}`. Pass this to
    /// the photo media endpoint.
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub width_px: u32,
    #[serde(default)]
    pub height_px: u32,
    #[serde(default)]
    pub author_attributions: Vec<AuthorAttribution>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Attribution for a photo or a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AuthorAttribution {
    #[serde(default)]
    pub display_name: String,
    #[serde(default)]
    pub uri: String,
    #[serde(default)]
    pub photo_uri: String,
}

/// Provider attribution attached to a place (Place Details responses).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Attribution {
    #[serde(default)]
    pub provider: String,
    #[serde(default)]
    pub provider_uri: String,
}

/// Regular opening hours of a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpeningHours {
    #[serde(default)]
    pub open_now: Option<bool>,
    #[serde(default)]
    pub weekday_descriptions: Vec<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// A single place. The same shape serves search results and Place Details.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Place {
    /// Resource name, `places/{id}`.
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub display_name: Option<LocalizedText>,
    #[serde(default)]
    pub formatted_address: Option<String>,
    #[serde(default)]
    pub short_formatted_address: Option<String>,
    #[serde(default)]
    pub location: Option<LatLng>,
    #[serde(default)]
    pub types: Vec<String>,
    #[serde(default)]
    pub primary_type: Option<String>,
    #[serde(default)]
    pub rating: Option<f64>,
    #[serde(default)]
    pub user_rating_count: Option<u64>,
    /// One of `PRICE_LEVEL_FREE`, `PRICE_LEVEL_INEXPENSIVE`,
    /// `PRICE_LEVEL_MODERATE`, `PRICE_LEVEL_EXPENSIVE`,
    /// `PRICE_LEVEL_VERY_EXPENSIVE`.
    #[serde(default)]
    pub price_level: Option<String>,
    #[serde(default)]
    pub business_status: Option<String>,
    #[serde(default)]
    pub national_phone_number: Option<String>,
    #[serde(default)]
    pub international_phone_number: Option<String>,
    #[serde(default)]
    pub website_uri: Option<String>,
    #[serde(default)]
    pub google_maps_uri: Option<String>,
    #[serde(default)]
    pub regular_opening_hours: Option<OpeningHours>,
    #[serde(default)]
    pub photos: Vec<Photo>,
    #[serde(default)]
    pub attributions: Vec<Attribution>,
    /// Any fields this version of the client does not model yet, preserved
    /// verbatim so nothing the API returns is lost.
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Response of Text Search and Nearby Search.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchResponse {
    #[serde(default)]
    pub places: Vec<Place>,
    /// Present only when more Text Search pages exist.
    #[serde(default)]
    pub next_page_token: Option<String>,
}

/// A substring match range inside an autocomplete text.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StringMatch {
    #[serde(default)]
    pub start_offset: u32,
    #[serde(default)]
    pub end_offset: u32,
}

/// Text with match ranges, as returned by Autocomplete.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FormattedText {
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub matches: Vec<StringMatch>,
}

/// The main/secondary split of a prediction's display text.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StructuredFormat {
    #[serde(default)]
    pub main_text: Option<FormattedText>,
    #[serde(default)]
    pub secondary_text: Option<FormattedText>,
}

/// A predicted place from Autocomplete.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlacePrediction {
    #[serde(default)]
    pub place_id: String,
    #[serde(default)]
    pub text: Option<FormattedText>,
    #[serde(default)]
    pub structured_format: Option<StructuredFormat>,
    #[serde(default)]
    pub types: Vec<String>,
    #[serde(default)]
    pub distance_meters: Option<u32>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// One autocomplete suggestion.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Suggestion {
    #[serde(default)]
    pub place_prediction: Option<PlacePrediction>,
    /// Raw prediction payload for suggestion kinds this client does not
    /// model (for example query predictions), when present.
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Response of Autocomplete.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AutocompleteResponse {
    #[serde(default)]
    pub suggestions: Vec<Suggestion>,
}

/// Downloaded photo media.
#[derive(Debug, Clone, PartialEq)]
pub struct PhotoResponse {
    pub bytes: Vec<u8>,
    pub content_type: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    const TEXT_SEARCH_JSON: &str = include_str!("../../../tests/fixtures/text_search.json");
    const NEARBY_SEARCH_JSON: &str = include_str!("../../../tests/fixtures/nearby_search.json");
    const PLACE_DETAILS_JSON: &str = include_str!("../../../tests/fixtures/place_details.json");
    const AUTOCOMPLETE_JSON: &str = include_str!("../../../tests/fixtures/autocomplete.json");

    #[test]
    fn decodes_text_search_response() {
        let resp: SearchResponse = serde_json::from_str(TEXT_SEARCH_JSON).unwrap();
        assert_eq!(resp.places.len(), 2);
        assert_eq!(resp.next_page_token.as_deref(), Some("token-abc-123"));
        let first = &resp.places[0];
        assert_eq!(first.id, "ChIJrTLr-GyuEmsRBfy61i59si0");
        assert_eq!(first.display_name.as_ref().unwrap().text, "Bianco Latte");
        assert_eq!(first.rating, Some(4.6));
        assert_eq!(first.user_rating_count, Some(1284));
        let loc = first.location.unwrap();
        assert!((loc.latitude - (-33.866_784)).abs() < 1e-9);
        assert_eq!(first.photos.len(), 1);
        assert_eq!(
            first.photos[0].name,
            "places/ChIJrTLr-GyuEmsRBfy61i59si0/photos/ATJ83zh8vExample"
        );
        assert_eq!(
            first.photos[0].author_attributions[0].display_name,
            "Jane Photographer"
        );
    }

    #[test]
    fn decodes_nearby_search_response() {
        let resp: SearchResponse = serde_json::from_str(NEARBY_SEARCH_JSON).unwrap();
        assert_eq!(resp.places.len(), 1);
        assert_eq!(resp.next_page_token, None);
        assert_eq!(resp.places[0].primary_type.as_deref(), Some("cafe"));
    }

    #[test]
    fn decodes_place_details_response() {
        let place: Place = serde_json::from_str(PLACE_DETAILS_JSON).unwrap();
        assert_eq!(place.id, "ChIJrTLr-GyuEmsRBfy61i59si0");
        assert_eq!(
            place.national_phone_number.as_deref(),
            Some("(02) 5550 1234")
        );
        assert_eq!(place.website_uri.as_deref(), Some("https://example.com/"));
        let hours = place.regular_opening_hours.unwrap();
        assert_eq!(hours.open_now, Some(true));
        assert_eq!(hours.weekday_descriptions.len(), 7);
        assert_eq!(place.attributions.len(), 1);
        assert_eq!(place.attributions[0].provider, "Example Maps Data");
    }

    #[test]
    fn decodes_autocomplete_response() {
        let resp: AutocompleteResponse = serde_json::from_str(AUTOCOMPLETE_JSON).unwrap();
        assert_eq!(resp.suggestions.len(), 2);
        let pred = resp.suggestions[0].place_prediction.as_ref().unwrap();
        assert_eq!(pred.place_id, "ChIJrTLr-GyuEmsRBfy61i59si0");
        assert_eq!(
            pred.text.as_ref().unwrap().text,
            "Bianco Latte, George Street, Sydney NSW, Australia"
        );
        let structured = pred.structured_format.as_ref().unwrap();
        assert_eq!(structured.main_text.as_ref().unwrap().text, "Bianco Latte");
        assert_eq!(pred.distance_meters, Some(1250));
    }

    #[test]
    fn unknown_fields_are_preserved_in_extra() {
        let mut place: Place = serde_json::from_str(PLACE_DETAILS_JSON).unwrap();
        // `editorialSummary` is not modeled by this client version.
        assert!(place.extra.contains_key("editorialSummary"));
        // And it survives a re-serialization round trip.
        let value = serde_json::to_value(&place).unwrap();
        assert!(value.get("editorialSummary").is_some());
        place.extra.clear();
    }

    #[test]
    fn text_search_request_serializes_camel_case_and_omits_none() {
        let req = TextSearchRequest {
            text_query: "pizza".to_owned(),
            language_code: Some("en".to_owned()),
            open_now: Some(true),
            ..Default::default()
        };
        let value = serde_json::to_value(&req).unwrap();
        assert_eq!(value["textQuery"], "pizza");
        assert_eq!(value["languageCode"], "en");
        assert_eq!(value["openNow"], true);
        assert!(value.get("pageToken").is_none());
        assert!(value.get("maxResultCount").is_none());
    }

    #[test]
    fn nearby_search_request_serializes_location_restriction() {
        let req = NearbySearchRequest {
            location_restriction: LocationRestriction {
                circle: Circle {
                    center: LatLng {
                        latitude: -33.86,
                        longitude: 151.20,
                    },
                    radius: 800.0,
                },
            },
            included_types: Some(vec!["cafe".to_owned()]),
            excluded_types: None,
            included_primary_types: None,
            max_result_count: Some(5),
            language_code: None,
            region_code: None,
            rank_preference: Some(NearbySearchRankPreference::Distance),
        };
        let value = serde_json::to_value(&req).unwrap();
        assert_eq!(
            value["locationRestriction"]["circle"]["center"]["latitude"],
            -33.86
        );
        assert_eq!(value["locationRestriction"]["circle"]["radius"], 800.0);
        assert_eq!(value["rankPreference"], "DISTANCE");
        assert!(value.get("excludedTypes").is_none());
    }
}
