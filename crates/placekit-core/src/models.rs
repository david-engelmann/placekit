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
    #[serde(default, skip_serializing_if = "is_empty_string")]
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

/// A rectangular area, bounded by its low (southwest) and high (northeast)
/// corners. Used by location bias and restriction values.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Viewport {
    pub low: LatLng,
    pub high: LatLng,
}

/// A `locationBias` value for Text Search: a rectangle or a circle, never
/// both (the API rejects a bias carrying both shapes).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TextSearchLocationBias {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rectangle: Option<Viewport>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub circle: Option<Circle>,
}

/// A `locationRestriction` value for Text Search, which accepts a
/// rectangle only (unlike the other endpoints).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TextSearchLocationRestriction {
    pub rectangle: Viewport,
}

/// A `locationBias` or `locationRestriction` value for Autocomplete: a
/// rectangle or a circle, never both.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AutocompleteLocation {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rectangle: Option<Viewport>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub circle: Option<Circle>,
}

/// Electric vehicle charging filter for Text Search.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EvOptions {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub minimum_charging_rate_kw: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub connector_types: Option<Vec<String>>,
}

/// A polyline in encoded or GeoJSON form, used by search along route.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Polyline {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub encoded_polyline: Option<String>,
}

/// Parameters for Text Search along a route.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SearchAlongRouteParameters {
    pub polyline: Polyline,
}

/// Route features to avoid when computing routing summaries.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RouteModifiers {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub avoid_tolls: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub avoid_highways: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub avoid_ferries: Option<bool>,
}

/// Routing inputs shared by Text Search and Nearby Search. When an origin
/// is supplied the API can return routing summaries with the results.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RoutingParameters {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub origin: Option<LatLng>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub travel_mode: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub route_modifiers: Option<RouteModifiers>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub routing_preference: Option<String>,
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
    pub location_bias: Option<TextSearchLocationBias>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location_restriction: Option<TextSearchLocationRestriction>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page_size: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min_rating: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ev_options: Option<EvOptions>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub search_along_route_parameters: Option<SearchAlongRouteParameters>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub routing_parameters: Option<RoutingParameters>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_pure_service_area_businesses: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_future_opening_businesses: Option<bool>,
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
    pub excluded_primary_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_result_count: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub region_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rank_preference: Option<NearbySearchRankPreference>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub routing_parameters: Option<RoutingParameters>,
    // Nearby Search documents includeFutureOpeningBusinesses only; it has
    // no includePureServiceAreaBusinesses field (spec note N1).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_future_opening_businesses: Option<bool>,
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
    pub location_bias: Option<AutocompleteLocation>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location_restriction: Option<AutocompleteLocation>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub origin: Option<LatLng>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub input_offset: Option<i32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub included_primary_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_pure_service_area_businesses: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_future_opening_businesses: Option<bool>,
}

// ---------------------------------------------------------------------------
// Responses
// ---------------------------------------------------------------------------

// Reserialization guards for the response models below: a field the wire
// did not carry must stay absent when the value is reserialized for the
// Python layer, instead of appearing with a null, empty or zero value
// (red team finding N1). Python `raw` mirrors the reserialized value, so
// without these guards raw overstates which fields the API returned.
// (serde calls the string guard with `&String` by contract, hence the
// allow for the clippy pointer argument lint.)
#[allow(clippy::ptr_arg)]
fn is_empty_string(value: &String) -> bool {
    value.is_empty()
}

fn is_zero_u32(value: &u32) -> bool {
    *value == 0
}

fn is_zero_i32(value: &i32) -> bool {
    *value == 0
}

/// A photo attached to a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Photo {
    /// Resource name, for example `places/{id}/photos/{ref}`. Pass this to
    /// the photo media endpoint.
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub name: String,
    #[serde(default, skip_serializing_if = "is_zero_u32")]
    pub width_px: u32,
    #[serde(default, skip_serializing_if = "is_zero_u32")]
    pub height_px: u32,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub author_attributions: Vec<AuthorAttribution>,
    /// Link where users can flag a problem with this photo.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub flag_content_uri: Option<String>,
    /// Link to view this photo on Google Maps.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub google_maps_uri: Option<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Attribution for a photo or a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AuthorAttribution {
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub display_name: String,
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub uri: String,
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub photo_uri: String,
}

/// Provider attribution attached to a place (Place Details responses).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Attribution {
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub provider: String,
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub provider_uri: String,
}

/// A calendar date, as used by opening hour points. A zero field means
/// that component is unset in the API value.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Date {
    #[serde(default, skip_serializing_if = "is_zero_i32")]
    pub year: i32,
    #[serde(default, skip_serializing_if = "is_zero_i32")]
    pub month: i32,
    #[serde(default, skip_serializing_if = "is_zero_i32")]
    pub day: i32,
}

/// One end of an opening period. `day` is 0 for Sunday through 6 for
/// Saturday, but the first period in a list does not start on any fixed
/// day, and period order is independent of weekday description order.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpeningPoint {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub date: Option<Date>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub truncated: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub day: Option<i32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub hour: Option<i32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub minute: Option<i32>,
}

/// A single open/close span within opening hours.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Period {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open: Option<OpeningPoint>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub close: Option<OpeningPoint>,
}

/// Regular opening hours of a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpeningHours {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open_now: Option<bool>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub periods: Vec<Period>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub weekday_descriptions: Vec<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// One component of a structured address.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AddressComponent {
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub long_text: String,
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub short_text: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub types: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
}

/// Plus code location reference for a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlusCode {
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub global_code: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub compound_code: Option<String>,
}

/// A postal address in structured form.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PostalAddress {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub region_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub postal_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub administrative_area: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub locality: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub address_lines: Vec<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// A single place. The same shape serves search results and Place Details.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Place {
    /// Resource name, `places/{id}`.
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub name: String,
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub display_name: Option<LocalizedText>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub formatted_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub short_formatted_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location: Option<LatLng>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub types: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub primary_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rating: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_rating_count: Option<u64>,
    /// One of `PRICE_LEVEL_FREE`, `PRICE_LEVEL_INEXPENSIVE`,
    /// `PRICE_LEVEL_MODERATE`, `PRICE_LEVEL_EXPENSIVE`,
    /// `PRICE_LEVEL_VERY_EXPENSIVE`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub price_level: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub business_status: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub national_phone_number: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub international_phone_number: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub website_uri: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub google_maps_uri: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub regular_opening_hours: Option<OpeningHours>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub current_opening_hours: Option<OpeningHours>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub address_components: Vec<AddressComponent>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub plus_code: Option<PlusCode>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub viewport: Option<Viewport>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub postal_address: Option<PostalAddress>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub adr_format_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub primary_type_display_name: Option<LocalizedText>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub photos: Vec<Photo>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
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
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub places: Vec<Place>,
    /// Present only when more Text Search pages exist.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub next_page_token: Option<String>,
    /// Any other top level fields the API returned, such as `searchUri`,
    /// `routingSummaries` and `contextualContents` when they are requested
    /// through the field mask, preserved verbatim so nothing is dropped
    /// when this response is reserialized for the Python layer.
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// A substring match range inside an autocomplete text.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StringMatch {
    #[serde(default, skip_serializing_if = "is_zero_u32")]
    pub start_offset: u32,
    #[serde(default, skip_serializing_if = "is_zero_u32")]
    pub end_offset: u32,
}

/// Text with match ranges, as returned by Autocomplete.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FormattedText {
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub text: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub matches: Vec<StringMatch>,
}

/// The main/secondary split of a prediction's display text.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StructuredFormat {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub main_text: Option<FormattedText>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub secondary_text: Option<FormattedText>,
}

/// A predicted place from Autocomplete.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlacePrediction {
    /// Resource name of the suggested place, for example
    /// `places/ChIJrTLr-GyuEmsRBfy61i59si0`.
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub place: String,
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub place_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text: Option<FormattedText>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub structured_format: Option<StructuredFormat>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub types: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub distance_meters: Option<u32>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// One autocomplete suggestion.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Suggestion {
    #[serde(default, skip_serializing_if = "Option::is_none")]
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
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub suggestions: Vec<Suggestion>,
    /// Any other top level fields the API returned, preserved verbatim
    /// like on [`SearchResponse`] so nothing is dropped when this
    /// response is reserialized for the Python layer.
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Downloaded photo media.
#[derive(Debug, Clone, PartialEq)]
pub struct PhotoResponse {
    pub bytes: Vec<u8>,
    pub content_type: Option<String>,
}

/// The JSON form of the photo media response, returned when the redirect
/// is skipped: a short lived URI the caller can render or fetch.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PhotoMediaJson {
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub name: String,
    #[serde(default, skip_serializing_if = "is_empty_string")]
    pub photo_uri: String,
}

/// Result of a photo media request: downloaded bytes by default, or the
/// JSON photo URI form when the caller asked to skip the redirect.
#[derive(Debug, Clone, PartialEq)]
pub enum PhotoMedia {
    Bytes(PhotoResponse),
    Uri(PhotoMediaJson),
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
        assert_eq!(
            resp.next_page_token.as_deref(),
            Some(
                "Aen7H9k2QpXv4mZ8wRtYuIoP3sDfGhJkL6zXcVbNmQ9wErTyUiOpA2sDfGhJkL5zXcVbNmQ8wErTyUiOpA1sDfGhJkL4zXcVbNmQ7wErTy9"
            )
        );
        // Top level fields this client does not type yet survive in extra
        // and survive reserialization (the C1 regression test).
        assert!(resp.extra.contains_key("searchUri"));
        assert!(resp.extra.contains_key("routingSummaries"));
        assert!(resp.extra.contains_key("contextualContents"));
        let value = serde_json::to_value(&resp).unwrap();
        assert!(value.get("searchUri").is_some());
        assert!(value.get("routingSummaries").is_some());
        assert!(value.get("contextualContents").is_some());
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
        // Periods are typed, with day not aligned to the weekday
        // descriptions order (spec note N6).
        assert_eq!(hours.periods.len(), 2);
        let open = hours.periods[0].open.as_ref().unwrap();
        assert_eq!(open.day, Some(3));
        assert_eq!(open.hour, Some(7));
        assert_eq!(open.minute, Some(0));
        let close = hours.periods[0].close.as_ref().unwrap();
        assert_eq!(close.hour, Some(15));
        // Structured address fields are typed.
        assert_eq!(place.address_components.len(), 3);
        assert_eq!(place.address_components[1].long_text, "George Street");
        assert_eq!(place.plus_code.as_ref().unwrap().global_code, "4RRH46J5+QJ");
        // Postal address and the adr microformat address are typed too
        // (finding C4); the fixture carries both so a wire name mistake
        // in either layer fails here.
        let postal = place.postal_address.as_ref().unwrap();
        assert_eq!(postal.region_code.as_deref(), Some("AU"));
        assert_eq!(postal.postal_code.as_deref(), Some("2000"));
        assert_eq!(
            postal.administrative_area.as_deref(),
            Some("New South Wales")
        );
        assert_eq!(postal.locality.as_deref(), Some("Sydney"));
        assert_eq!(postal.address_lines, vec!["Shop 1/123 George St"]);
        assert_eq!(
            place.adr_format_address.as_deref(),
            Some("<span class=\"street-address\">Shop 1/123 George St</span>, <span class=\"locality\">Sydney</span> <span class=\"region\">NSW</span> <span class=\"postal-code\">2000</span>, <span class=\"country-name\">Australia</span>")
        );
        let viewport = place.viewport.unwrap();
        assert!((viewport.low.latitude - (-33.868)).abs() < 1e-9);
        assert_eq!(
            place.primary_type_display_name.as_ref().unwrap().text,
            "Cafe"
        );
        assert!(place.current_opening_hours.is_some());
        // Photo URI fields are typed.
        let photo = &place.photos[0];
        assert_eq!(
            photo.flag_content_uri.as_deref(),
            Some("https://maps.example.com/flag/photo")
        );
        assert_eq!(
            photo.google_maps_uri.as_deref(),
            Some("https://maps.google.com/?cid=1234567890")
        );
        assert_eq!(place.attributions.len(), 1);
        assert_eq!(place.attributions[0].provider, "Example Maps Data");
    }

    #[test]
    fn reserialization_adds_no_keys_the_wire_did_not_carry() {
        // A response masked down to places.id must reserialize with no
        // keys beyond what the wire carried: absent typed fields stay
        // absent instead of appearing with null or empty values (red
        // team finding N1).
        let resp: SearchResponse = serde_json::from_str(r#"{"places":[{"id":"ChIJx"}]}"#).unwrap();
        let value = serde_json::to_value(&resp).unwrap();
        assert_eq!(value, serde_json::json!({"places": [{"id": "ChIJx"}]}));
        // The same holds for a bare Place Details payload.
        let place: Place = serde_json::from_str(r#"{"id":"ChIJx"}"#).unwrap();
        let value = serde_json::to_value(&place).unwrap();
        assert_eq!(value, serde_json::json!({"id": "ChIJx"}));
        // And for an autocomplete prediction with no distance, where the
        // wire omits distanceMeters unless an origin was sent.
        let resp: AutocompleteResponse =
            serde_json::from_str(r#"{"suggestions":[{"placePrediction":{"placeId":"ChIJx"}}]}"#)
                .unwrap();
        let value = serde_json::to_value(&resp).unwrap();
        assert_eq!(
            value,
            serde_json::json!({"suggestions": [{"placePrediction": {"placeId": "ChIJx"}}]})
        );
    }

    #[test]
    fn autocomplete_top_level_unknown_fields_survive() {
        // A future top level field on Autocomplete must reach the
        // Python layer through extra, like it already does on search.
        let resp: AutocompleteResponse =
            serde_json::from_str(r#"{"suggestions":[],"futureSummary":{"legs":[]}}"#).unwrap();
        let value = serde_json::to_value(&resp).unwrap();
        assert_eq!(value["futureSummary"], serde_json::json!({"legs": []}));
    }

    #[test]
    fn decodes_autocomplete_response() {
        let resp: AutocompleteResponse = serde_json::from_str(AUTOCOMPLETE_JSON).unwrap();
        assert_eq!(resp.suggestions.len(), 2);
        let pred = resp.suggestions[0].place_prediction.as_ref().unwrap();
        assert_eq!(pred.place_id, "ChIJrTLr-GyuEmsRBfy61i59si0");
        assert_eq!(pred.place, "places/ChIJrTLr-GyuEmsRBfy61i59si0");
        assert_eq!(
            pred.text.as_ref().unwrap().text,
            "Bianco Latte, George Street, Sydney NSW, Australia"
        );
        let structured = pred.structured_format.as_ref().unwrap();
        assert_eq!(structured.main_text.as_ref().unwrap().text, "Bianco Latte");
        // The fixture carries no distanceMeters: the API returns it only
        // for requests that carried an origin, so asserting a value here
        // asserted behaviour the client could never produce (finding A4).
        // The end to end Python test supplies an origin and asserts it.
        assert_eq!(pred.distance_meters, None);
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
    fn text_search_request_serializes_round_1_fields() {
        let req = TextSearchRequest {
            text_query: "ev charging".to_owned(),
            page_size: Some(10),
            min_rating: Some(4.0),
            ev_options: Some(EvOptions {
                minimum_charging_rate_kw: Some(50.0),
                connector_types: Some(vec!["EV_CONNECTOR_TYPE_J1772".to_owned()]),
            }),
            routing_parameters: Some(RoutingParameters {
                origin: Some(LatLng {
                    latitude: -33.86,
                    longitude: 151.20,
                }),
                travel_mode: Some("DRIVE".to_owned()),
                route_modifiers: None,
                routing_preference: None,
            }),
            include_pure_service_area_businesses: Some(true),
            location_bias: Some(TextSearchLocationBias {
                rectangle: None,
                circle: Some(Circle {
                    center: LatLng {
                        latitude: -33.86,
                        longitude: 151.20,
                    },
                    radius: 1000.0,
                }),
            }),
            ..Default::default()
        };
        let value = serde_json::to_value(&req).unwrap();
        assert_eq!(value["pageSize"], 10);
        assert_eq!(value["minRating"], 4.0);
        assert_eq!(value["evOptions"]["minimumChargingRateKw"], 50.0);
        assert_eq!(value["routingParameters"]["origin"]["latitude"], -33.86);
        assert_eq!(value["includePureServiceAreaBusinesses"], true);
        assert_eq!(value["locationBias"]["circle"]["radius"], 1000.0);
        assert!(value.get("searchAlongRouteParameters").is_none());
    }

    #[test]
    fn autocomplete_request_serializes_origin_offset_and_types() {
        let req = AutocompleteRequest {
            input: "Bianco".to_owned(),
            origin: Some(LatLng {
                latitude: -33.86,
                longitude: 151.20,
            }),
            input_offset: Some(6),
            included_primary_types: Some(vec!["cafe".to_owned()]),
            ..Default::default()
        };
        let value = serde_json::to_value(&req).unwrap();
        assert_eq!(value["origin"]["latitude"], -33.86);
        assert_eq!(value["inputOffset"], 6);
        assert_eq!(value["includedPrimaryTypes"], serde_json::json!(["cafe"]));
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
            excluded_primary_types: Some(vec!["bar".to_owned()]),
            max_result_count: Some(5),
            language_code: None,
            region_code: None,
            rank_preference: Some(NearbySearchRankPreference::Distance),
            routing_parameters: None,
            include_future_opening_businesses: None,
        };
        let value = serde_json::to_value(&req).unwrap();
        assert_eq!(
            value["locationRestriction"]["circle"]["center"]["latitude"],
            -33.86
        );
        assert_eq!(value["locationRestriction"]["circle"]["radius"], 800.0);
        assert_eq!(value["rankPreference"], "DISTANCE");
        assert_eq!(value["excludedPrimaryTypes"], serde_json::json!(["bar"]));
        assert!(value.get("excludedTypes").is_none());
    }
}
