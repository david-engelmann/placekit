//! Request and response types for the Places API (New).
//!
//! Requests serialize to the exact JSON bodies the API expects. Responses
//! deserialize leniently: every field is optional or defaulted, and unknown
//! fields are preserved in a flattened `extra` map on the response types,
//! so new API fields never break decoding or get silently dropped.
//!
//! Decoded response values are passed through unclamped and unvalidated
//! (the posture decided in Round 4, finding R4-27). This client is a
//! transport: it must not hide what the API returned or break forward
//! compatibility by rejecting values a future API version considers
//! valid, so a rating outside 0 to 5 or a count that arrived string
//! encoded is surfaced as decoded rather than silently corrected. The
//! leniency stops at representability: a value the typed field cannot
//! hold at all (a negative or fractional count, for example) is still a
//! decode error. Request values, which the caller controls, are the
//! opposite: they are validated in the core before anything is sent.
//!
//! One consequence of the leniency posture is worth stating plainly.
//! Typed values default what the server omitted (a location carrying
//! only a latitude reads a longitude of 0.0), and the typed dict these
//! models reserialize into for the Python layer carries that default,
//! exactly as it always has. The `raw` view is a different
//! construction since Round 16. The core returns the response body
//! beside the typed value, and the Python layer builds `raw` from the
//! body itself, so raw claims exactly what the server said and
//! nothing it did not. The two views can therefore disagree on a
//! partial object, deliberately. Raw is the wire record; the typed
//! value is the lenient reading of it.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

// ---------------------------------------------------------------------------
// Shared building blocks
// ---------------------------------------------------------------------------

/// A latitude/longitude pair.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LatLng {
    #[serde(default)]
    pub latitude: WireFloat,
    #[serde(default)]
    pub longitude: WireFloat,
    /// Unknown fields inside a decoded coordinate object, preserved like
    /// on the other response types.
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

impl LatLng {
    /// A coordinate with no extra fields, as request code constructs it.
    pub fn new(latitude: f64, longitude: f64) -> Self {
        Self {
            latitude: latitude.into(),
            longitude: longitude.into(),
            extra: Map::new(),
        }
    }
}

/// A text value paired with its language.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalizedText {
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub text: WireString,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub language_code: Option<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Decode a request circle center, requiring both coordinates.
///
/// Response leniency defaults a missing latitude or longitude to 0.0,
/// which is the right posture for values the API sent. A request body
/// is caller supplied, though, and the same defaults silently aimed a
/// circle whose center was absent, or missing one coordinate, at
/// latitude 0.0 and longitude 0.0. Circle is request geometry only,
/// never a response type, so its center decodes strictly here. A
/// missing center or coordinate is a decode error, which the bindings
/// surface as a configuration error, while the response types keep
/// the lenient [`LatLng`] decoding.
fn de_complete_center<'de, D>(deserializer: D) -> Result<LatLng, D::Error>
where
    D: serde::Deserializer<'de>,
{
    #[derive(Deserialize)]
    struct CompleteCenter {
        latitude: f64,
        longitude: f64,
        #[serde(flatten)]
        extra: Map<String, Value>,
    }
    let center = CompleteCenter::deserialize(deserializer)?;
    Ok(LatLng {
        latitude: center.latitude.into(),
        longitude: center.longitude.into(),
        extra: center.extra,
    })
}

/// A circular area, used to bias or restrict searches.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Circle {
    #[serde(deserialize_with = "de_complete_center")]
    pub center: LatLng,
    /// Radius in meters, at most 50000.
    #[serde(default)]
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
    #[serde(default)]
    pub low: LatLng,
    #[serde(default)]
    pub high: LatLng,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
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
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
    pub connector_types: Option<Vec<String>>,
}

/// A polyline in encoded or GeoJSON form, used by search along route.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Polyline {
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
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
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub travel_mode: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub route_modifiers: Option<RouteModifiers>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
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
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub page_token: Option<String>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub region_code: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rank_preference: Option<TextSearchRankPreference>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open_now: Option<bool>,
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
    pub price_levels: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub strict_type_filtering: Option<bool>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
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
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
    pub included_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
    pub excluded_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
    pub included_primary_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
    pub excluded_primary_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_result_count: Option<u32>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
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
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub language_code: Option<String>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub region_code: Option<String>,
    #[serde(default, skip_serializing_if = "none_or_empty_string")]
    pub session_token: Option<String>,
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
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
    #[serde(default, skip_serializing_if = "none_or_empty_vec")]
    pub included_primary_types: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_pure_service_area_businesses: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_future_opening_businesses: Option<bool>,
}

// ---------------------------------------------------------------------------
// Responses
// ---------------------------------------------------------------------------

// Presence tracking for response positions (Round 16). The Python
// layer decodes its attributes from the typed dict these models
// reserialize into, and at some positions absence, an explicit null
// and a sent value are three different readings there. A plain
// String, Vec or f64 collapses those states, so the positions the
// Python contract treats differently carry one of these wrappers
// instead. Each wrapper keeps the wire state beside the typed value.
// Internal reads see the absence shape (an empty string, an empty
// list, a defaulted coordinate), while the reserialized dict keeps
// the state apart, omitting an absent field, emitting a null field
// as null and emitting a sent value as itself. The deserializers
// run only when the wire carried the key (a missing key falls back
// to the field default, the absent state), so a visit to the none
// arm always means an explicit null was sent. Request types never
// use these wrappers, so request bodies on the wire are untouched
// by them. Before this round the reserialization also fed Python
// raw, and a family of skip guards kept absent fields absent from
// it (red team finding N1). Raw is built from the response body
// itself now, so the guards that remain serve the typed dict alone.

/// A response string field with its wire presence state. The outer
/// option is the carried state (absent or carried) and the inner
/// option is the null state (null or a sent string).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct WireString(Option<Option<String>>);

impl WireString {
    /// The string the wire sent, or the empty default internal
    /// reads already use for an absent or null field.
    pub fn as_str(&self) -> &str {
        match &self.0 {
            Some(Some(value)) => value,
            _ => "",
        }
    }

    /// True when the field reads as the empty default internally,
    /// which covers absence, an explicit null and an empty string.
    pub fn is_empty(&self) -> bool {
        self.as_str().is_empty()
    }
}

impl PartialEq<&str> for WireString {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == *other
    }
}

impl serde::Serialize for WireString {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        match &self.0 {
            Some(Some(value)) => serializer.serialize_str(value),
            _ => serializer.serialize_none(),
        }
    }
}

impl<'de> serde::Deserialize<'de> for WireString {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        struct WireStringVisitor;

        impl<'de> serde::de::Visitor<'de> for WireStringVisitor {
            type Value = WireString;

            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("a string or null")
            }

            fn visit_none<E>(self) -> Result<WireString, E>
            where
                E: serde::de::Error,
            {
                Ok(WireString(Some(None)))
            }

            fn visit_unit<E>(self) -> Result<WireString, E>
            where
                E: serde::de::Error,
            {
                Ok(WireString(Some(None)))
            }

            fn visit_some<D>(self, deserializer: D) -> Result<WireString, D::Error>
            where
                D: serde::Deserializer<'de>,
            {
                Ok(WireString(Some(Some(String::deserialize(deserializer)?))))
            }

            fn visit_str<E>(self, value: &str) -> Result<WireString, E>
            where
                E: serde::de::Error,
            {
                Ok(WireString(Some(Some(value.to_owned()))))
            }

            fn visit_string<E>(self, value: String) -> Result<WireString, E>
            where
                E: serde::de::Error,
            {
                Ok(WireString(Some(Some(value))))
            }
        }

        deserializer.deserialize_option(WireStringVisitor)
    }
}

/// Skip guard for a [`WireString`] field. Only an absent field is
/// omitted from the reserialized dict; an explicit null stays as
/// null and an empty string stays as an empty string.
fn wire_string_absent(value: &WireString) -> bool {
    value.0.is_none()
}

/// A response coordinate with its wire presence state. Absence
/// decodes to the typed default the leniency posture promises, so
/// the wrapper only needs to carry one extra state of its own, the
/// explicit null, which the reserialized dict must emit as null
/// while every internal read keeps the default.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct WireFloat(Option<f64>);

impl WireFloat {
    /// The typed coordinate. An explicit null reads as the absence
    /// default, exactly as a missing coordinate does.
    pub fn value(&self) -> f64 {
        self.0.unwrap_or(0.0)
    }

    /// True when the wire carried an explicit null.
    pub fn is_null(&self) -> bool {
        self.0.is_none()
    }
}

impl Default for WireFloat {
    fn default() -> Self {
        WireFloat(Some(0.0))
    }
}

impl From<f64> for WireFloat {
    fn from(value: f64) -> Self {
        WireFloat(Some(value))
    }
}

impl PartialEq<f64> for WireFloat {
    fn eq(&self, other: &f64) -> bool {
        self.value() == *other
    }
}

impl serde::Serialize for WireFloat {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        match self.0 {
            Some(value) => serializer.serialize_f64(value),
            None => serializer.serialize_none(),
        }
    }
}

impl<'de> serde::Deserialize<'de> for WireFloat {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        struct WireFloatVisitor;

        impl<'de> serde::de::Visitor<'de> for WireFloatVisitor {
            type Value = WireFloat;

            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("a number or null")
            }

            fn visit_none<E>(self) -> Result<WireFloat, E>
            where
                E: serde::de::Error,
            {
                Ok(WireFloat(None))
            }

            fn visit_unit<E>(self) -> Result<WireFloat, E>
            where
                E: serde::de::Error,
            {
                Ok(WireFloat(None))
            }

            fn visit_some<D>(self, deserializer: D) -> Result<WireFloat, D::Error>
            where
                D: serde::Deserializer<'de>,
            {
                Ok(WireFloat(Some(f64::deserialize(deserializer)?)))
            }

            fn visit_f64<E>(self, value: f64) -> Result<WireFloat, E>
            where
                E: serde::de::Error,
            {
                Ok(WireFloat(Some(value)))
            }

            fn visit_i64<E>(self, value: i64) -> Result<WireFloat, E>
            where
                E: serde::de::Error,
            {
                Ok(WireFloat(Some(value as f64)))
            }

            fn visit_u64<E>(self, value: u64) -> Result<WireFloat, E>
            where
                E: serde::de::Error,
            {
                Ok(WireFloat(Some(value as f64)))
            }
        }

        deserializer.deserialize_option(WireFloatVisitor)
    }
}

/// A response list field with its wire presence state, on the same
/// two option shape as [`WireString`].
#[derive(Debug, Clone, PartialEq)]
pub struct WireList<T>(Option<Option<Vec<T>>>);

impl<T> WireList<T> {
    /// The elements the wire sent, or an empty slice for an absent
    /// or null field, which is the absence shape internal reads
    /// already use for both.
    pub fn as_slice(&self) -> &[T] {
        match &self.0 {
            Some(Some(items)) => items,
            _ => &[],
        }
    }
}

impl<T> Default for WireList<T> {
    fn default() -> Self {
        WireList(None)
    }
}

impl<T> From<Vec<T>> for WireList<T> {
    fn from(items: Vec<T>) -> Self {
        WireList(Some(Some(items)))
    }
}

impl<T> std::ops::Deref for WireList<T> {
    type Target = [T];

    fn deref(&self) -> &[T] {
        self.as_slice()
    }
}

impl<T> serde::Serialize for WireList<T>
where
    T: serde::Serialize,
{
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        match &self.0 {
            Some(Some(items)) => items.serialize(serializer),
            _ => serializer.serialize_none(),
        }
    }
}

impl<'de, T> serde::Deserialize<'de> for WireList<T>
where
    T: serde::Deserialize<'de>,
{
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        struct WireListVisitor<T>(std::marker::PhantomData<T>);

        impl<'de, T> serde::de::Visitor<'de> for WireListVisitor<T>
        where
            T: serde::Deserialize<'de>,
        {
            type Value = WireList<T>;

            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("a list or null")
            }

            fn visit_none<E>(self) -> Result<WireList<T>, E>
            where
                E: serde::de::Error,
            {
                Ok(WireList(Some(None)))
            }

            fn visit_unit<E>(self) -> Result<WireList<T>, E>
            where
                E: serde::de::Error,
            {
                Ok(WireList(Some(None)))
            }

            fn visit_some<D>(self, deserializer: D) -> Result<WireList<T>, D::Error>
            where
                D: serde::Deserializer<'de>,
            {
                Ok(WireList(Some(Some(Vec::<T>::deserialize(deserializer)?))))
            }
        }

        deserializer.deserialize_option(WireListVisitor(std::marker::PhantomData))
    }
}

/// Skip guard for a [`WireList`] field. Only an absent field is
/// omitted from the reserialized dict; an explicit null stays as
/// null and an empty list stays as an empty list.
fn wire_list_absent<T>(value: &WireList<T>) -> bool {
    value.0.is_none()
}

fn is_zero_u32(value: &u32) -> bool {
    *value == 0
}

fn is_zero_i32(value: &i32) -> bool {
    *value == 0
}

// Lenient scalar decoding for count and dimension fields (R4-08). The
// API is observed to encode integers as strings on some Google surfaces
// and a fractional float that is exactly integral carries the same
// value, so all three forms decode; anything the typed field cannot
// represent (negative, fractional, out of range, non-numeric) is a
// decode error rather than a silent truncation.
fn lenient_u64_value(value: &Value) -> Option<u64> {
    match value {
        Value::Number(n) => n.as_u64().or_else(|| {
            let f = n.as_f64()?;
            // The bound is strict. u64::MAX as f64 rounds up to
            // exactly 2^64, so a bound of f <= u64::MAX as f64 let a
            // count of exactly 2^64 through, and the cast saturated
            // it to u64::MAX, one less than the value sent. Anything
            // at or above 2^64 is unrepresentable and stays an error.
            if f.fract() == 0.0 && (0.0..18_446_744_073_709_551_616.0).contains(&f) {
                Some(f as u64)
            } else {
                None
            }
        }),
        Value::String(s) => s.parse::<u64>().ok(),
        _ => None,
    }
}

fn lenient_u32_value(value: &Value) -> Option<u32> {
    lenient_u64_value(value).and_then(|v| u32::try_from(v).ok())
}

fn de_lenient_u32<'de, D>(deserializer: D) -> Result<u32, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = Value::deserialize(deserializer)?;
    lenient_u32_value(&value)
        .ok_or_else(|| serde::de::Error::custom("expected a non-negative integer"))
}

fn de_lenient_opt_u64<'de, D>(deserializer: D) -> Result<Option<u64>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = Option::<Value>::deserialize(deserializer)?;
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(v) => lenient_u64_value(&v)
            .map(Some)
            .ok_or_else(|| serde::de::Error::custom("expected a non-negative integer count")),
    }
}

fn de_lenient_opt_u32<'de, D>(deserializer: D) -> Result<Option<u32>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = Option::<Value>::deserialize(deserializer)?;
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(v) => lenient_u32_value(&v)
            .map(Some)
            .ok_or_else(|| serde::de::Error::custom("expected a non-negative integer")),
    }
}

// Request serialization guards (R4-17): an optional string or list the
// caller set to an empty value means "not supplied", exactly like None,
// and is omitted from the body instead of sent as an empty value whose
// meaning differs from absence at the API.
fn none_or_empty_string(value: &Option<String>) -> bool {
    value.as_ref().is_none_or(|s| s.is_empty())
}

fn none_or_empty_vec(value: &Option<Vec<String>>) -> bool {
    value.as_ref().is_none_or(|v| v.is_empty())
}

/// A photo attached to a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Photo {
    /// Resource name, for example `places/{id}/photos/{ref}`. Pass this to
    /// the photo media endpoint.
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub name: WireString,
    #[serde(
        default,
        deserialize_with = "de_lenient_u32",
        skip_serializing_if = "is_zero_u32"
    )]
    pub width_px: u32,
    #[serde(
        default,
        deserialize_with = "de_lenient_u32",
        skip_serializing_if = "is_zero_u32"
    )]
    pub height_px: u32,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub author_attributions: WireList<AuthorAttribution>,
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
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub display_name: WireString,
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub uri: WireString,
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub photo_uri: WireString,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Provider attribution attached to a place (Place Details responses).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Attribution {
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub provider: WireString,
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub provider_uri: WireString,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
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
    #[serde(flatten)]
    pub extra: Map<String, Value>,
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
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// A single open/close span within opening hours.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Period {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open: Option<OpeningPoint>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub close: Option<OpeningPoint>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Regular opening hours of a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpeningHours {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open_now: Option<bool>,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub periods: WireList<Period>,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub weekday_descriptions: WireList<Option<String>>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// One component of a structured address.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AddressComponent {
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub long_text: WireString,
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub short_text: WireString,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub types: WireList<Option<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Plus code location reference for a place.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlusCode {
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub global_code: WireString,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub compound_code: Option<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
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
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub address_lines: WireList<Option<String>>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// A single place. The same shape serves search results and Place Details.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Place {
    /// Resource name, `places/{id}`.
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub name: WireString,
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub id: WireString,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub display_name: Option<LocalizedText>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub formatted_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub short_formatted_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location: Option<LatLng>,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub types: WireList<Option<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub primary_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rating: Option<f64>,
    #[serde(
        default,
        deserialize_with = "de_lenient_opt_u64",
        skip_serializing_if = "Option::is_none"
    )]
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
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub address_components: WireList<AddressComponent>,
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
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub photos: WireList<Photo>,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub attributions: WireList<Attribution>,
    /// Any fields this version of the client does not model yet, preserved
    /// verbatim so nothing the API returns is lost.
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Response of Text Search and Nearby Search.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchResponse {
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub places: WireList<Place>,
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

/// A substring match range inside an autocomplete text. The offsets are
/// presence based (R4-24): a start offset of 0 is a real value the API
/// sends, so the fields are optional rather than zero-skipped, and a
/// decoded 0 survives reserialization instead of vanishing from `raw`.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StringMatch {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub start_offset: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub end_offset: Option<u32>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// Text with match ranges, as returned by Autocomplete.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FormattedText {
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub text: WireString,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub matches: WireList<StringMatch>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// The main/secondary split of a prediction's display text.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StructuredFormat {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub main_text: Option<FormattedText>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub secondary_text: Option<FormattedText>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

/// A predicted place from Autocomplete.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlacePrediction {
    /// Resource name of the suggested place, for example
    /// `places/ChIJrTLr-GyuEmsRBfy61i59si0`.
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub place: WireString,
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub place_id: WireString,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text: Option<FormattedText>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub structured_format: Option<StructuredFormat>,
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub types: WireList<Option<String>>,
    #[serde(
        default,
        deserialize_with = "de_lenient_opt_u32",
        skip_serializing_if = "Option::is_none"
    )]
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
    #[serde(default, skip_serializing_if = "wire_list_absent")]
    pub suggestions: WireList<Suggestion>,
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
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub name: WireString,
    #[serde(default, skip_serializing_if = "wire_string_absent")]
    pub photo_uri: WireString,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
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
        let loc = first.location.as_ref().unwrap();
        assert!((loc.latitude.value() - (-33.866_784)).abs() < 1e-9);
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
        assert_eq!(
            postal.address_lines.as_slice(),
            [Some("Shop 1/123 George St".to_owned())]
        );
        assert_eq!(
            place.adr_format_address.as_deref(),
            Some("<span class=\"street-address\">Shop 1/123 George St</span>, <span class=\"locality\">Sydney</span> <span class=\"region\">NSW</span> <span class=\"postal-code\">2000</span>, <span class=\"country-name\">Australia</span>")
        );
        let viewport = place.viewport.unwrap();
        assert!((viewport.low.latitude.value() - (-33.868)).abs() < 1e-9);
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
        // `zzUnmodelled` stands for any field no layer of this client
        // models. It is injected into the fixture payload so the
        // example cannot quietly become a modelled field later (the
        // previous example, editorialSummary, was typed in Round 6).
        let mut payload: Value = serde_json::from_str(PLACE_DETAILS_JSON).unwrap();
        payload.as_object_mut().unwrap().insert(
            "zzUnmodelled".to_owned(),
            serde_json::json!({"text": "unmodelled"}),
        );
        let mut place: Place = serde_json::from_value(payload).unwrap();
        assert!(place.extra.contains_key("zzUnmodelled"));
        // And it survives a re-serialization round trip.
        let value = serde_json::to_value(&place).unwrap();
        assert!(value.get("zzUnmodelled").is_some());
        place.extra.clear();
    }

    #[test]
    fn partial_nested_objects_decode_with_defaults() {
        // R4-01: one partial nested object must not fail the whole
        // response. A location carrying only a latitude, a viewport
        // carrying only one corner of one point, and a circle carrying
        // only a center all decode with the missing pieces defaulted.
        let resp: SearchResponse =
            serde_json::from_str(r#"{"places":[{"id":"ChIJx","location":{"latitude":-33.86}}]}"#)
                .unwrap();
        let loc = resp.places[0].location.as_ref().unwrap();
        assert_eq!(loc.latitude, -33.86);
        assert_eq!(loc.longitude, 0.0);
        let place: Place =
            serde_json::from_str(r#"{"id":"ChIJx","viewport":{"low":{"latitude":1.0}}}"#).unwrap();
        let viewport = place.viewport.as_ref().unwrap();
        assert_eq!(viewport.low.latitude, 1.0);
        assert_eq!(viewport.high.longitude, 0.0);
        let circle: Circle =
            serde_json::from_str(r#"{"center":{"latitude":1.0,"longitude":2.0}}"#).unwrap();
        assert_eq!(circle.radius, 0.0);
        // Serialization of a full value is unchanged by the defaults.
        let value = serde_json::to_value(LatLng::new(-33.86, 151.2)).unwrap();
        assert_eq!(
            value,
            serde_json::json!({"latitude": -33.86, "longitude": 151.2})
        );
    }

    #[test]
    fn nested_unknown_fields_survive_reserialization() {
        // R4-12: unknown fields inside nested response types are kept
        // in their extra maps, not silently dropped on the way to the
        // Python layer's raw view.
        let place: Place = serde_json::from_str(
            r#"{"id":"ChIJx",
                "location":{"latitude":1.0,"longitude":2.0,"futureCoordField":7},
                "regularOpeningHours":{"periods":[{"open":{"day":1,"futurePointField":true},"futurePeriodField":"x"}]},
                "addressComponents":[{"longText":"George Street","futureComponentField":3}],
                "plusCode":{"globalCode":"4RRH46J5+QJ","futureCodeField":4},
                "photos":[{"name":"places/ChIJx/photos/p","authorAttributions":[{"displayName":"Jane","futureAttributionField":5}]}]}"#,
        )
        .unwrap();
        let value = serde_json::to_value(&place).unwrap();
        assert_eq!(value["location"]["futureCoordField"], 7);
        assert_eq!(
            value["regularOpeningHours"]["periods"][0]["futurePeriodField"],
            "x"
        );
        assert_eq!(
            value["regularOpeningHours"]["periods"][0]["open"]["futurePointField"],
            true
        );
        assert_eq!(value["addressComponents"][0]["futureComponentField"], 3);
        assert_eq!(value["plusCode"]["futureCodeField"], 4);
        assert_eq!(
            value["photos"][0]["authorAttributions"][0]["futureAttributionField"],
            5
        );
    }

    #[test]
    fn lenient_scalar_forms_decode_counts_and_dimensions() {
        // R4-08: string encoded and exactly integral float counts and
        // dimensions decode to the same typed values as plain integers.
        let place: Place =
            serde_json::from_str(r#"{"id":"ChIJx","userRatingCount":"1284"}"#).unwrap();
        assert_eq!(place.user_rating_count, Some(1284));
        let place: Place =
            serde_json::from_str(r#"{"id":"ChIJx","userRatingCount":1284.0}"#).unwrap();
        assert_eq!(place.user_rating_count, Some(1284));
        let place: Place = serde_json::from_str(
            r#"{"id":"ChIJx","photos":[{"name":"p","widthPx":"800","heightPx":600.0}]}"#,
        )
        .unwrap();
        assert_eq!(place.photos[0].width_px, 800);
        assert_eq!(place.photos[0].height_px, 600);
        // Values the typed fields cannot represent are decode errors,
        // never silent truncations.
        assert!(serde_json::from_str::<Place>(r#"{"id":"ChIJx","userRatingCount":-3}"#).is_err());
        assert!(serde_json::from_str::<Place>(r#"{"id":"ChIJx","userRatingCount":1.5}"#).is_err());
        assert!(
            serde_json::from_str::<Place>(r#"{"id":"ChIJx","userRatingCount":"many"}"#).is_err()
        );
    }

    #[test]
    fn lenient_count_boundary_at_two_to_the_sixty_fourth() {
        // The decoder's own rule is that a value the typed field
        // cannot represent is a decode error, never a silent
        // correction. 2^64 - 1 is the largest representable count and
        // decodes exactly; exactly 2^64 and above fail in integer,
        // float and string form alike, where they used to saturate
        // to u64::MAX through the float fallback.
        let place: Place =
            serde_json::from_str(r#"{"id":"ChIJx","userRatingCount":18446744073709551615}"#)
                .unwrap();
        assert_eq!(place.user_rating_count, Some(u64::MAX));
        for body in [
            r#"{"id":"ChIJx","userRatingCount":18446744073709551616}"#,
            r#"{"id":"ChIJx","userRatingCount":18446744073709551617}"#,
            r#"{"id":"ChIJx","userRatingCount":18446744073709551616.0}"#,
            r#"{"id":"ChIJx","userRatingCount":"18446744073709551616"}"#,
        ] {
            assert!(serde_json::from_str::<Place>(body).is_err(), "{body}");
        }
    }

    #[test]
    fn request_circles_require_a_complete_center() {
        // A circle decoded for a request must carry a center with
        // both coordinates present. The response leniency defaults
        // would otherwise aim an omitted center, or a center missing
        // one coordinate, at 0.0, 0.0 without a word, on every path
        // that accepts a circle.
        let nearby: Result<NearbySearchRequest, _> =
            serde_json::from_str(r#"{"locationRestriction":{"circle":{"radius":100.0}}}"#);
        assert!(nearby.is_err());
        let nearby: Result<NearbySearchRequest, _> = serde_json::from_str(
            r#"{"locationRestriction":{"circle":{"center":{"latitude":-33.86},"radius":100.0}}}"#,
        );
        assert!(nearby.is_err());
        let text: Result<TextSearchRequest, _> = serde_json::from_str(
            r#"{"textQuery":"cafes","locationBias":{"circle":{"center":{"longitude":151.2},"radius":100.0}}}"#,
        );
        assert!(text.is_err());
        let auto: Result<AutocompleteRequest, _> = serde_json::from_str(
            r#"{"input":"Bianco","locationRestriction":{"circle":{"radius":100.0}}}"#,
        );
        assert!(auto.is_err());
        // A complete center decodes on the same path, and the radius
        // keeps its default.
        let nearby: NearbySearchRequest = serde_json::from_str(
            r#"{"locationRestriction":{"circle":{"center":{"latitude":-33.86,"longitude":151.2}}}}"#,
        )
        .unwrap();
        let circle = &nearby.location_restriction.circle;
        assert_eq!(circle.center.latitude, -33.86);
        assert_eq!(circle.center.longitude, 151.2);
        assert_eq!(circle.radius, 0.0);
    }

    #[test]
    fn zero_start_offset_survives_reserialization() {
        // R4-24: a match starting at offset 0 was present on the wire
        // and stays present in the reserialized value.
        let resp: AutocompleteResponse = serde_json::from_str(
            r#"{"suggestions":[{"placePrediction":{"placeId":"ChIJx","text":{"text":"Bianco","matches":[{"startOffset":0,"endOffset":3}]}}}]}"#,
        )
        .unwrap();
        let value = serde_json::to_value(&resp).unwrap();
        assert_eq!(
            value["suggestions"][0]["placePrediction"]["text"]["matches"][0]["startOffset"],
            0
        );
        assert_eq!(
            value["suggestions"][0]["placePrediction"]["text"]["matches"][0]["endOffset"],
            3
        );
    }

    #[test]
    fn passthrough_integers_keep_full_precision() {
        // R4-19: an unknown field carrying an integer beyond u64 used
        // to reserialize in scientific notation with digits lost, so
        // the value Python received in raw was not the value the API
        // sent. Arbitrary precision numbers keep every digit.
        let resp: SearchResponse = serde_json::from_str(
            r#"{"places":[],"futureCounter":340282366920938463463374607431768211456}"#,
        )
        .unwrap();
        let text = serde_json::to_string(&resp).unwrap();
        assert!(
            text.contains("340282366920938463463374607431768211456"),
            "{text}"
        );
    }

    #[test]
    fn empty_request_collections_and_strings_are_omitted() {
        // R4-17: an empty optional string or list serializes exactly
        // like None, as an absent field.
        let req = TextSearchRequest {
            text_query: "pizza".to_owned(),
            page_token: Some(String::new()),
            language_code: Some(String::new()),
            price_levels: Some(Vec::new()),
            ..Default::default()
        };
        let value = serde_json::to_value(&req).unwrap();
        assert!(value.get("pageToken").is_none());
        assert!(value.get("languageCode").is_none());
        assert!(value.get("priceLevels").is_none());
        let req = NearbySearchRequest {
            location_restriction: LocationRestriction {
                circle: Circle {
                    center: LatLng::new(-33.86, 151.20),
                    radius: 800.0,
                },
            },
            included_types: Some(Vec::new()),
            excluded_types: None,
            included_primary_types: None,
            excluded_primary_types: Some(Vec::new()),
            max_result_count: None,
            language_code: Some(String::new()),
            region_code: None,
            rank_preference: None,
            routing_parameters: None,
            include_future_opening_businesses: None,
        };
        let value = serde_json::to_value(&req).unwrap();
        assert!(value.get("includedTypes").is_none());
        assert!(value.get("excludedPrimaryTypes").is_none());
        assert!(value.get("languageCode").is_none());
        assert!(value.get("locationRestriction").is_some());
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
                origin: Some(LatLng::new(-33.86, 151.20)),
                travel_mode: Some("DRIVE".to_owned()),
                route_modifiers: None,
                routing_preference: None,
            }),
            include_pure_service_area_businesses: Some(true),
            location_bias: Some(TextSearchLocationBias {
                rectangle: None,
                circle: Some(Circle {
                    center: LatLng::new(-33.86, 151.20),
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
            origin: Some(LatLng::new(-33.86, 151.20)),
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
                    center: LatLng::new(-33.86, 151.20),
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

    #[test]
    fn presence_aware_string_round_trips_its_three_states() {
        // Round 16, class 2. A plain string position on a response
        // type keeps missing, explicit null and sent value apart in
        // the reserialized typed dict, while internal reads see the
        // empty default for the first two.
        let component: AddressComponent =
            serde_json::from_str(r#"{"longText":"123 George Street"}"#).unwrap();
        assert_eq!(component.short_text.as_str(), "");
        let value = serde_json::to_value(&component).unwrap();
        assert!(value.get("shortText").is_none());

        let component: AddressComponent =
            serde_json::from_str(r#"{"longText":"123 George Street","shortText":null}"#).unwrap();
        assert_eq!(component.short_text.as_str(), "");
        let value = serde_json::to_value(&component).unwrap();
        assert!(value["shortText"].is_null());

        let component: AddressComponent =
            serde_json::from_str(r#"{"longText":"123 George Street","shortText":""}"#).unwrap();
        assert_eq!(component.short_text.as_str(), "");
        let value = serde_json::to_value(&component).unwrap();
        assert_eq!(value["shortText"], "");

        let component: AddressComponent =
            serde_json::from_str(r#"{"longText":"123 George Street","shortText":"123"}"#).unwrap();
        assert_eq!(component.short_text, "123");
        let value = serde_json::to_value(&component).unwrap();
        assert_eq!(value["shortText"], "123");
    }

    #[test]
    fn presence_aware_list_forwards_a_null_field_and_keeps_null_elements() {
        // Round 16, classes 1 and 4. A null list field decodes to
        // the empty absence shape internally and reserializes as the
        // explicit null the Python layer must meet, and a null
        // element inside a modelled string list survives in place.
        let place: Place = serde_json::from_str(r#"{"id":"ChIJx","types":null}"#).unwrap();
        assert!(place.types.is_empty());
        let value = serde_json::to_value(&place).unwrap();
        assert!(value["types"].is_null());

        let place: Place = serde_json::from_str(r#"{"id":"ChIJx","types":["cafe",null]}"#).unwrap();
        assert_eq!(place.types.as_slice(), [Some("cafe".to_owned()), None]);
        let value = serde_json::to_value(&place).unwrap();
        assert_eq!(value["types"], serde_json::json!(["cafe", null]));

        let resp: SearchResponse = serde_json::from_str(r#"{"places":null}"#).unwrap();
        assert!(resp.places.is_empty());
        let value = serde_json::to_value(&resp).unwrap();
        assert!(value["places"].is_null());
    }

    #[test]
    fn presence_aware_coordinate_forwards_an_explicit_null() {
        // Round 16, class 3. A null coordinate decodes with the
        // typed default internally and reserializes as the explicit
        // null, while a missing coordinate keeps reserializing as
        // the default, which is the leniency the typed layer owes.
        let place: Place = serde_json::from_str(
            r#"{"id":"ChIJx","location":{"latitude":null,"longitude":151.2}}"#,
        )
        .unwrap();
        let location = place.location.as_ref().unwrap();
        assert_eq!(location.latitude.value(), 0.0);
        assert_eq!(location.longitude.value(), 151.2);
        let value = serde_json::to_value(&place).unwrap();
        assert_eq!(
            value["location"],
            serde_json::json!({"latitude": null, "longitude": 151.2})
        );

        let place: Place =
            serde_json::from_str(r#"{"id":"ChIJx","location":{"latitude":-33.86}}"#).unwrap();
        let value = serde_json::to_value(&place).unwrap();
        assert_eq!(
            value["location"],
            serde_json::json!({"latitude": -33.86, "longitude": 0.0})
        );
    }

    #[test]
    fn photo_media_json_decodes_a_null_field_under_the_class_2_form() {
        // Round 16, class 2 on the photo URI form. A null field
        // decodes, reads as the empty default for the identity
        // guard, and reserializes as the explicit null.
        let media: PhotoMediaJson =
            serde_json::from_str(r#"{"name":null,"photoUri":"https://example.test/img"}"#).unwrap();
        assert!(media.name.is_empty());
        assert_eq!(media.photo_uri, "https://example.test/img");
        let value = serde_json::to_value(&media).unwrap();
        assert!(value["name"].is_null());
        assert_eq!(value["photoUri"], "https://example.test/img");
    }

    #[test]
    fn request_bodies_stay_byte_identical_with_empty_and_unset_values() {
        // Round 16 guard pin. The presence wrappers live on response
        // types only, so a request body carrying empty and unset
        // values serializes byte identical to the body the head
        // before this round produced. The expected strings are that
        // output, recorded literally.
        let req = TextSearchRequest {
            text_query: "pizza".to_owned(),
            page_token: Some(String::new()),
            language_code: Some(String::new()),
            region_code: Some(String::new()),
            price_levels: Some(Vec::new()),
            ..Default::default()
        };
        assert_eq!(
            serde_json::to_string(&req).unwrap(),
            r#"{"textQuery":"pizza"}"#
        );

        let req = NearbySearchRequest {
            location_restriction: LocationRestriction {
                circle: Circle {
                    center: LatLng::new(-33.86, 151.20),
                    radius: 800.0,
                },
            },
            included_types: Some(Vec::new()),
            excluded_types: Some(Vec::new()),
            included_primary_types: Some(Vec::new()),
            excluded_primary_types: Some(Vec::new()),
            max_result_count: None,
            language_code: Some(String::new()),
            region_code: Some(String::new()),
            rank_preference: None,
            routing_parameters: None,
            include_future_opening_businesses: None,
        };
        assert_eq!(
            serde_json::to_string(&req).unwrap(),
            r#"{"locationRestriction":{"circle":{"center":{"latitude":-33.86,"longitude":151.2},"radius":800.0}}}"#
        );

        let req = AutocompleteRequest {
            input: "Bianco".to_owned(),
            language_code: Some(String::new()),
            session_token: Some(String::new()),
            included_region_codes: Some(Vec::new()),
            included_primary_types: Some(Vec::new()),
            origin: Some(LatLng::new(-33.86, 151.20)),
            ..Default::default()
        };
        assert_eq!(
            serde_json::to_string(&req).unwrap(),
            r#"{"input":"Bianco","origin":{"latitude":-33.86,"longitude":151.2}}"#
        );
    }
}
