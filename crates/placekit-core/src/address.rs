//! Address composition over plain component data.
//!
//! This module carries the logic the Python `placekit.address`
//! helpers answer with, ported from that module in Round 53. It
//! works on plain data only, one component as its long text, its
//! short text and its type names, so the Python layer validates
//! and materialises caller values first and converts the checked
//! components into [`ComponentData`] before calling in. Nothing
//! here reads a Python object and nothing here raises a caller
//! argument error, because every error the address surface
//! raises is a property of the caller supplied Python values
//! and is raised by the Python validation funnels before the
//! conversion happens.
//!
//! The readings mirror the Python module's stated rules. Which
//! carrier holds the city changes by country, and in two
//! recorded countries the carriers disagree on the same place,
//! so a resolved city always travels with the carrier it came
//! from and a confidence grade in the open. Japan and the
//! Emirates carry a stated precedence, the United Kingdom
//! carries a stated two value answer, and every other country
//! follows one generic fallback chain whose results are capped
//! at the heuristic grade. The country code that routes a place
//! is matched without regard to letter case, while the code a
//! result carries stays the value as sent.

/// One address component as plain data.
///
/// A text the component does not carry reads as `None`, and a
/// text it carries empty stays an empty string, because the
/// scans distinguish a carried empty text from an absent one
/// only by truthiness and the Python layer keeps the two apart
/// the same way. A type slot the wire carried as null stays
/// `None` at its index, and membership reads past it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ComponentData {
    pub long_text: Option<String>,
    pub short_text: Option<String>,
    pub types: Vec<Option<String>>,
}

const TYPE_LOCALITY: &str = "locality";
const TYPE_POSTAL_TOWN: &str = "postal_town";
const TYPE_SUBLOCALITY_LEVEL_1: &str = "sublocality_level_1";
const TYPE_SUBLOCALITY_LEVEL_2: &str = "sublocality_level_2";
const TYPE_POSTAL_CODE: &str = "postal_code";
const TYPE_COUNTRY: &str = "country";
const TYPE_STREET_NUMBER: &str = "street_number";
const TYPE_ROUTE: &str = "route";
const TYPE_PREMISE: &str = "premise";
const TYPE_SUBPREMISE: &str = "subpremise";

/// Carrier names, matching the Python module constants of the
/// same names. The component carriers are the wire type strings
/// themselves, and the postal carriers name the postal field the
/// value came from.
pub const CARRIER_LOCALITY: &str = TYPE_LOCALITY;
pub const CARRIER_POSTAL_TOWN: &str = TYPE_POSTAL_TOWN;
pub const CARRIER_SUBLOCALITY_LEVEL_1: &str = TYPE_SUBLOCALITY_LEVEL_1;
pub const CARRIER_SUBLOCALITY_LEVEL_2: &str = TYPE_SUBLOCALITY_LEVEL_2;
pub const CARRIER_POSTAL_CODE_COMPONENT: &str = TYPE_POSTAL_CODE;
pub const CARRIER_POSTAL_ADDRESS_LOCALITY: &str = "postal_address_locality";
pub const CARRIER_POSTAL_ADDRESS_POSTAL_CODE: &str = "postal_address_postal_code";
pub const CARRIER_BOTH_POSTAL: &str = "both_postal_carriers";

pub const CONFIDENCE_PRIMARY: &str = "primary";
pub const CONFIDENCE_FALLBACK: &str = "fallback";
pub const CONFIDENCE_CONTESTED: &str = "contested";
pub const CONFIDENCE_HEURISTIC: &str = "heuristic";
pub const CONFIDENCE_NONE: &str = "none";

pub const POSTAL_PRESENT: &str = "present";
pub const POSTAL_ABSENT: &str = "absent";

fn has_type(component: &ComponentData, type_name: &str) -> bool {
    component
        .types
        .iter()
        .any(|item| item.as_deref() == Some(type_name))
}

fn nonempty(text: &Option<String>) -> Option<&str> {
    match text {
        Some(value) if !value.is_empty() => Some(value.as_str()),
        _ => None,
    }
}

/// The indices of every component whose types contain the name,
/// in list order.
pub fn matching_indices(components: &[ComponentData], type_name: &str) -> Vec<usize> {
    components
        .iter()
        .enumerate()
        .filter(|(_, component)| has_type(component, type_name))
        .map(|(index, _)| index)
        .collect()
}

/// The indices of every component whose types list is empty, in
/// list order.
pub fn untyped_indices(components: &[ComponentData]) -> Vec<usize> {
    components
        .iter()
        .enumerate()
        .filter(|(_, component)| component.types.is_empty())
        .map(|(index, _)| index)
        .collect()
}

/// The first nonempty long text among the matches for a type
/// name. A match whose long text is empty is skipped and the
/// scan keeps going, so this form never returns an empty string.
pub fn first_long_text(components: &[ComponentData], type_name: &str) -> Option<String> {
    components
        .iter()
        .filter(|component| has_type(component, type_name))
        .find_map(|component| nonempty(&component.long_text).map(str::to_owned))
}

/// The first nonempty short text among the matches for a type
/// name, on the same skip rule as [`first_long_text`].
pub fn first_short_text(components: &[ComponentData], type_name: &str) -> Option<String> {
    components
        .iter()
        .filter(|component| has_type(component, type_name))
        .find_map(|component| nonempty(&component.short_text).map(str::to_owned))
}

/// The nonempty long texts of every match, in list order.
pub fn long_texts(components: &[ComponentData], type_name: &str) -> Vec<String> {
    components
        .iter()
        .filter(|component| has_type(component, type_name))
        .filter_map(|component| nonempty(&component.long_text).map(str::to_owned))
        .collect()
}

/// The nonempty short texts of every match, in list order.
pub fn short_texts(components: &[ComponentData], type_name: &str) -> Vec<String> {
    components
        .iter()
        .filter(|component| has_type(component, type_name))
        .filter_map(|component| nonempty(&component.short_text).map(str::to_owned))
        .collect()
}

/// The short text of the country component, the first country
/// component with a nonempty short text. The value comes back
/// as sent and is never uppercased or mapped to another code.
pub fn country_code_from_components(components: &[ComponentData]) -> Option<String> {
    first_short_text(components, TYPE_COUNTRY)
}

/// Routing into a stated answer or the generic chain matches
/// the country code without regard to letter case. The
/// normalisation serves the match only.
fn routing_country(country_code: Option<&str>) -> Option<String> {
    country_code.map(str::to_uppercase)
}

/// One city reading with its carrier and confidence grade, as
/// plain data for the Python layer to wrap in its result type.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CityResolution {
    pub value: Option<String>,
    pub carrier: Option<&'static str>,
    pub confidence: &'static str,
    pub country_code: Option<String>,
    pub competing_value: Option<String>,
    pub competing_carrier: Option<&'static str>,
}

/// One district reading, on the same plain data terms.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DistrictResolution {
    pub value: Option<String>,
    pub carrier: Option<&'static str>,
    pub confidence: &'static str,
    pub country_code: Option<String>,
}

/// One postal code reading, on the same plain data terms. The
/// status keeps presence and absence distinct outcomes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PostalCodeResult {
    pub value: Option<String>,
    pub carrier: Option<&'static str>,
    pub status: &'static str,
    pub country_code: Option<String>,
    pub competing_value: Option<String>,
    pub competing_carrier: Option<&'static str>,
}

/// Whether the postal locality has been read yet.
///
/// The Python layer reads postal fields lazily, exactly where a
/// reading touches them, so a city chain that never reaches the
/// postal locality never reads it. The chain therefore runs
/// first with [`PostalLocality::Unread`], and only the chains
/// that fall to the postal carrier answer
/// [`CityResolutions::NeedsPostalLocality`], after which the
/// caller reads the field and runs the chain again with the
/// value in hand.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PostalLocality {
    Unread,
    Read(Option<String>),
}

/// The outcome of one city chain run.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CityResolutions {
    Done(Vec<CityResolution>),
    NeedsPostalLocality,
}

fn no_city(country_code: Option<&str>) -> CityResolution {
    CityResolution {
        value: None,
        carrier: None,
        confidence: CONFIDENCE_NONE,
        country_code: country_code.map(str::to_owned),
        competing_value: None,
        competing_carrier: None,
    }
}

fn one_city(
    value: String,
    carrier: &'static str,
    confidence: &'static str,
    country_code: Option<&str>,
) -> CityResolution {
    CityResolution {
        value: Some(value),
        carrier: Some(carrier),
        confidence,
        country_code: country_code.map(str::to_owned),
        competing_value: None,
        competing_carrier: None,
    }
}

fn british_resolutions(
    country_code: Option<&str>,
    components: &[ComponentData],
) -> Vec<CityResolution> {
    let locality = first_long_text(components, TYPE_LOCALITY);
    let town = first_long_text(components, TYPE_POSTAL_TOWN);
    match (locality, town) {
        (Some(locality), Some(town)) => {
            if locality != town {
                let mut first = one_city(
                    locality.clone(),
                    CARRIER_LOCALITY,
                    CONFIDENCE_CONTESTED,
                    country_code,
                );
                first.competing_value = Some(town.clone());
                first.competing_carrier = Some(CARRIER_POSTAL_TOWN);
                let mut second = one_city(
                    town,
                    CARRIER_POSTAL_TOWN,
                    CONFIDENCE_CONTESTED,
                    country_code,
                );
                second.competing_value = Some(locality);
                second.competing_carrier = Some(CARRIER_LOCALITY);
                vec![first, second]
            } else {
                vec![one_city(
                    locality,
                    CARRIER_LOCALITY,
                    CONFIDENCE_PRIMARY,
                    country_code,
                )]
            }
        }
        (Some(locality), None) => vec![one_city(
            locality,
            CARRIER_LOCALITY,
            CONFIDENCE_PRIMARY,
            country_code,
        )],
        (None, Some(town)) => vec![one_city(
            town,
            CARRIER_POSTAL_TOWN,
            CONFIDENCE_FALLBACK,
            country_code,
        )],
        (None, None) => vec![no_city(country_code)],
    }
}

/// Every city reading the applicable rules produce for one
/// component set and country code. The postal locality enters
/// only on the chains that read it, under the lazy read
/// protocol [`PostalLocality`] documents.
pub fn city_resolutions(
    components: &[ComponentData],
    country_code: Option<&str>,
    postal_locality: &PostalLocality,
) -> CityResolutions {
    let route = routing_country(country_code);
    match route.as_deref() {
        Some("GB") => {
            return CityResolutions::Done(british_resolutions(country_code, components));
        }
        Some("JP") | Some("AE") => {
            if let Some(locality) = first_long_text(components, TYPE_LOCALITY) {
                return CityResolutions::Done(vec![one_city(
                    locality,
                    CARRIER_LOCALITY,
                    CONFIDENCE_PRIMARY,
                    country_code,
                )]);
            }
            if route.as_deref() == Some("AE") {
                return match postal_locality {
                    PostalLocality::Unread => CityResolutions::NeedsPostalLocality,
                    PostalLocality::Read(Some(value)) => CityResolutions::Done(vec![one_city(
                        value.clone(),
                        CARRIER_POSTAL_ADDRESS_LOCALITY,
                        CONFIDENCE_FALLBACK,
                        country_code,
                    )]),
                    PostalLocality::Read(None) => {
                        CityResolutions::Done(vec![no_city(country_code)])
                    }
                };
            }
            return CityResolutions::Done(vec![no_city(country_code)]);
        }
        _ => {}
    }
    let generic_chain = [
        (TYPE_LOCALITY, CARRIER_LOCALITY),
        (TYPE_POSTAL_TOWN, CARRIER_POSTAL_TOWN),
        (TYPE_SUBLOCALITY_LEVEL_1, CARRIER_SUBLOCALITY_LEVEL_1),
        (TYPE_SUBLOCALITY_LEVEL_2, CARRIER_SUBLOCALITY_LEVEL_2),
    ];
    for (type_name, carrier) in generic_chain {
        if let Some(value) = first_long_text(components, type_name) {
            return CityResolutions::Done(vec![one_city(
                value,
                carrier,
                CONFIDENCE_HEURISTIC,
                country_code,
            )]);
        }
    }
    match postal_locality {
        PostalLocality::Unread => CityResolutions::NeedsPostalLocality,
        PostalLocality::Read(Some(value)) => CityResolutions::Done(vec![one_city(
            value.clone(),
            CARRIER_POSTAL_ADDRESS_LOCALITY,
            CONFIDENCE_HEURISTIC,
            country_code,
        )]),
        PostalLocality::Read(None) => CityResolutions::Done(vec![no_city(country_code)]),
    }
}

/// The district reading for one component set and country code.
/// Japan reads its district from sublocality level 2 and the
/// Emirates read theirs from sublocality level 1, and every
/// other country returns a none grade result because no other
/// district carrier is stated.
pub fn district_resolution(
    components: &[ComponentData],
    country_code: Option<&str>,
) -> DistrictResolution {
    let (type_name, carrier) = match routing_country(country_code).as_deref() {
        Some("JP") => (TYPE_SUBLOCALITY_LEVEL_2, CARRIER_SUBLOCALITY_LEVEL_2),
        Some("AE") => (TYPE_SUBLOCALITY_LEVEL_1, CARRIER_SUBLOCALITY_LEVEL_1),
        _ => {
            return DistrictResolution {
                value: None,
                carrier: None,
                confidence: CONFIDENCE_NONE,
                country_code: country_code.map(str::to_owned),
            }
        }
    };
    match first_long_text(components, type_name) {
        Some(value) => DistrictResolution {
            value: Some(value),
            carrier: Some(carrier),
            confidence: CONFIDENCE_PRIMARY,
            country_code: country_code.map(str::to_owned),
        },
        None => DistrictResolution {
            value: None,
            carrier: None,
            confidence: CONFIDENCE_NONE,
            country_code: country_code.map(str::to_owned),
        },
    }
}

/// The postal code reading from the two carrier values. When
/// both carriers hold the same code the carrier reports both of
/// them. When they hold different codes the headline carries
/// the component value and the postal value stays visible in
/// the competing fields. When neither carrier holds a code the
/// status reports absence.
pub fn postal_code_result(
    country_code: Option<String>,
    component_value: Option<String>,
    postal_value: Option<String>,
) -> PostalCodeResult {
    let base = PostalCodeResult {
        value: None,
        carrier: None,
        status: POSTAL_ABSENT,
        country_code,
        competing_value: None,
        competing_carrier: None,
    };
    match (component_value, postal_value) {
        (Some(component), Some(postal)) => {
            if component == postal {
                PostalCodeResult {
                    value: Some(component),
                    carrier: Some(CARRIER_BOTH_POSTAL),
                    status: POSTAL_PRESENT,
                    ..base
                }
            } else {
                PostalCodeResult {
                    value: Some(component),
                    carrier: Some(CARRIER_POSTAL_CODE_COMPONENT),
                    status: POSTAL_PRESENT,
                    competing_value: Some(postal),
                    competing_carrier: Some(CARRIER_POSTAL_ADDRESS_POSTAL_CODE),
                    ..base
                }
            }
        }
        (Some(component), None) => PostalCodeResult {
            value: Some(component),
            carrier: Some(CARRIER_POSTAL_CODE_COMPONENT),
            status: POSTAL_PRESENT,
            ..base
        },
        (None, Some(postal)) => PostalCodeResult {
            value: Some(postal),
            carrier: Some(CARRIER_POSTAL_ADDRESS_POSTAL_CODE),
            status: POSTAL_PRESENT,
            ..base
        },
        (None, None) => base,
    }
}

/// The component level presence flags for one component set.
/// Each flag follows the rule its Python helper states, and
/// `is_premise_level`, `spans_multiple_routes` and
/// `has_no_street_level` are the composite readings over the
/// same set.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ComponentFlags {
    pub has_street_number: bool,
    pub has_route: bool,
    pub has_premise: bool,
    pub has_subpremise: bool,
    pub is_premise_level: bool,
    pub spans_multiple_routes: bool,
    pub has_no_street_level: bool,
}

pub fn component_flags(components: &[ComponentData]) -> ComponentFlags {
    let has_street_number = components.iter().any(|c| has_type(c, TYPE_STREET_NUMBER));
    let has_route = components.iter().any(|c| has_type(c, TYPE_ROUTE));
    let has_premise = components.iter().any(|c| has_type(c, TYPE_PREMISE));
    let has_subpremise = components.iter().any(|c| has_type(c, TYPE_SUBPREMISE));
    let routes_with_text = components
        .iter()
        .filter(|c| has_type(c, TYPE_ROUTE))
        .filter(|c| nonempty(&c.long_text).is_some())
        .count();
    ComponentFlags {
        has_street_number,
        has_route,
        has_premise,
        has_subpremise,
        is_premise_level: has_premise && !has_street_number && !has_route,
        spans_multiple_routes: routes_with_text >= 2,
        has_no_street_level: !(has_street_number || has_route || has_premise || has_subpremise),
    }
}

/// Whether one character is whitespace under the Python
/// `str.strip` rule the compound code split follows. The set is
/// the Unicode White_Space characters plus the information
/// separators the Python rule also strips.
fn is_python_space(c: char) -> bool {
    matches!(
        c,
        '\u{9}'..='\u{d}'
            | '\u{1c}'..='\u{1f}'
            | ' '
            | '\u{85}'
            | '\u{a0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200a}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202f}'
            | '\u{205f}'
            | '\u{3000}'
    )
}

/// Split a compound plus code into its code and locality text,
/// split at its first space. The split returns `None` when the
/// input holds no space, or nothing before it, or nothing but
/// whitespace after it, so a locality text is never an empty
/// string. The input here is already validated as a string by
/// the Python layer, which owns the None and wrong type cases.
pub fn split_compound_code(compound_code: &str) -> Option<(String, String)> {
    let (code_part, rest) = compound_code.split_once(' ')?;
    if code_part.is_empty() {
        return None;
    }
    let locality = rest.trim_matches(is_python_space);
    if locality.is_empty() {
        return None;
    }
    Some((code_part.to_owned(), locality.to_owned()))
}

#[cfg(test)]
mod tests {
    use super::*;

    include!("address_test_data.rs");

    fn comp(long: Option<&str>, short: Option<&str>, types: &[Option<&str>]) -> ComponentData {
        ComponentData {
            long_text: long.map(str::to_owned),
            short_text: short.map(str::to_owned),
            types: types.iter().map(|item| item.map(str::to_owned)).collect(),
        }
    }

    fn typed(long: &str, short: &str, types: &[&str]) -> ComponentData {
        comp(
            Some(long),
            Some(short),
            &types.iter().map(|t| Some(*t)).collect::<Vec<_>>(),
        )
    }

    fn city_one(
        components: &[ComponentData],
        country: Option<&str>,
        postal: &PostalLocality,
    ) -> CityResolution {
        match city_resolutions(components, country, postal) {
            CityResolutions::Done(mut done) => {
                assert_eq!(done.len(), 1);
                done.pop().unwrap()
            }
            CityResolutions::NeedsPostalLocality => panic!("unexpected postal read"),
        }
    }

    // --- Scans, mirroring the scan pins of tests/test_address.py

    #[test]
    fn bare_sublocality_name_matches_every_levelled_component() {
        // Mirrors test_bare_sublocality_chain_trap.
        let place = a5_sublocality_chains();
        let indices = matching_indices(&place.components, "sublocality");
        let texts: Vec<_> = indices
            .iter()
            .map(|i| place.components[*i].long_text.as_deref())
            .collect();
        assert_eq!(texts, vec![Some("６"), Some("２丁目"), Some("浅草")]);
        let first = indices[0];
        assert_eq!(place.components[first].long_text.as_deref(), Some("６"));
    }

    #[test]
    fn fragment_is_found_but_never_a_city_output() {
        // Mirrors test_jp_district_and_barred_fragments.
        let place = a5_sublocality_chains();
        let fragment = matching_indices(&place.components, "sublocality_level_4");
        assert_eq!(fragment.len(), 1);
        assert_eq!(
            place.components[fragment[0]].long_text.as_deref(),
            Some("６")
        );
        let city = city_one(&place.components, Some("JP"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("台東区"));
    }

    #[test]
    fn first_long_text_skips_empty_matches() {
        // Mirrors the A11 survival pin in test_synthesized_a11_survival.
        let place = a11_empty_text();
        assert_eq!(first_long_text(&place.components, "route"), None);
        let found = matching_indices(&place.components, "route");
        assert_eq!(found.len(), 1);
        assert_eq!(place.components[found[0]].long_text.as_deref(), Some(""));
        assert!(component_flags(&place.components).has_route);
    }

    #[test]
    fn texts_collect_nonempty_in_order_and_skip_null_types() {
        let components = vec![
            typed("One", "1", &["route"]),
            comp(Some(""), Some(""), &[Some("route")]),
            comp(None, None, &[None, Some("route")]),
            typed("Two", "2", &["route"]),
            typed("Other", "o", &["locality"]),
        ];
        assert_eq!(long_texts(&components, "route"), vec!["One", "Two"]);
        assert_eq!(short_texts(&components, "route"), vec!["1", "2"]);
        assert_eq!(
            first_long_text(&components, "route").as_deref(),
            Some("One")
        );
        assert_eq!(first_short_text(&components, "route").as_deref(), Some("1"));
        assert_eq!(matching_indices(&components, "route"), vec![0, 1, 2, 3]);
    }

    #[test]
    fn untyped_components_surface_in_order() {
        // Mirrors test_jp_premise_duplication_shape and
        // test_ae_typeless_most_specific_text.
        let jp = a13_premise_and_subpremise();
        assert_eq!(untyped_indices(&jp.components), vec![0]);
        assert_eq!(
            jp.components[0].long_text.as_deref(),
            Some("1 Asakusa, Taito-ku")
        );
        let ae = a7_rtl_index1();
        let untyped = untyped_indices(&ae.components);
        let texts: Vec<_> = untyped
            .iter()
            .map(|i| ae.components[*i].long_text.as_deref())
            .collect();
        assert_eq!(texts, vec![Some("Level 3, Armani Hotel Dubai")]);
        for type_name in ["premise", "route", "locality", "country"] {
            assert!(!matching_indices(&ae.components, type_name).contains(&untyped[0]));
        }
    }

    #[test]
    fn country_code_comes_back_as_sent() {
        let place = a8_tokyo_english();
        assert_eq!(
            country_code_from_components(&place.components).as_deref(),
            Some("JP")
        );
        let everest = p1_no_address();
        assert_eq!(country_code_from_components(&everest.components), None);
        let empty_short = vec![
            typed("Nowhere", "", &["country"]),
            typed("Somewhere", "SW", &["country"]),
        ];
        assert_eq!(
            country_code_from_components(&empty_short).as_deref(),
            Some("SW")
        );
    }

    // --- Japan, stated precedence

    #[test]
    fn jp_city_primary_english() {
        // Mirrors test_jp_city_primary_english.
        let place = a8_tokyo_english();
        let city = city_one(&place.components, Some("JP"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("Taito City"));
        assert_eq!(city.carrier, Some(CARRIER_LOCALITY));
        assert_eq!(city.confidence, CONFIDENCE_PRIMARY);
        assert_eq!(city.country_code.as_deref(), Some("JP"));
    }

    #[test]
    fn jp_city_primary_japanese() {
        // Mirrors test_jp_city_primary_japanese.
        let place = a8_tokyo_japanese();
        let city = city_one(&place.components, Some("JP"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("台東区"));
        assert_eq!(city.confidence, CONFIDENCE_PRIMARY);
    }

    #[test]
    fn jp_district_from_sublocality_level_2() {
        // Mirrors test_jp_district_and_barred_fragments.
        let place = a5_sublocality_chains();
        let district = district_resolution(&place.components, Some("JP"));
        assert_eq!(district.value.as_deref(), Some("浅草"));
        assert_eq!(district.carrier, Some(CARRIER_SUBLOCALITY_LEVEL_2));
        assert_eq!(district.confidence, CONFIDENCE_PRIMARY);
        assert_eq!(district.country_code.as_deref(), Some("JP"));
    }

    #[test]
    fn jp_postal_both_carriers() {
        // Mirrors test_jp_postal_silence.
        let place = a6_block_addressing();
        let component_value = first_long_text(&place.components, TYPE_POSTAL_CODE);
        let result = postal_code_result(
            Some("JP".to_owned()),
            component_value,
            place.postal_postal_code().map(str::to_owned),
        );
        assert_eq!(result.value.as_deref(), Some("111-0032"));
        assert_eq!(result.carrier, Some(CARRIER_BOTH_POSTAL));
        assert_eq!(result.status, POSTAL_PRESENT);
        assert_eq!(result.country_code.as_deref(), Some("JP"));
    }

    #[test]
    fn jp_no_locality_reads_none_without_touching_postal() {
        let components = vec![
            typed("Asakusa", "Asakusa", &["sublocality_level_2"]),
            typed("Japan", "JP", &["country"]),
        ];
        let city = city_one(&components, Some("JP"), &PostalLocality::Unread);
        assert_eq!(city.confidence, CONFIDENCE_NONE);
        assert_eq!(city.value, None);
    }

    #[test]
    fn jp_premise_level_shape() {
        // Mirrors test_jp_premise_duplication_shape.
        let place = a13_premise_and_subpremise();
        assert_eq!(matching_indices(&place.components, "subpremise").len(), 1);
        let flags = component_flags(&place.components);
        assert!(flags.has_premise);
        assert!(flags.is_premise_level);
    }

    // --- Emirates, stated precedence

    #[test]
    fn ae_city_primary() {
        // Mirrors test_ae_city_primary.
        let place = a7_rtl_index0();
        let city = city_one(&place.components, Some("AE"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("دبي"));
        assert_eq!(city.carrier, Some(CARRIER_LOCALITY));
        assert_eq!(city.confidence, CONFIDENCE_PRIMARY);
        assert_eq!(city.country_code.as_deref(), Some("AE"));
    }

    #[test]
    fn ae_district_and_postal_substitution() {
        // Mirrors test_ae_district_and_postal_substitution.
        let place = a9_no_postal_codes();
        let district = district_resolution(&place.components, Some("AE"));
        assert_eq!(district.value.as_deref(), Some("المركز التجاري الثانية"));
        assert_eq!(district.carrier, Some(CARRIER_SUBLOCALITY_LEVEL_1));
        assert_eq!(district.confidence, CONFIDENCE_PRIMARY);
        let neighborhood = first_long_text(&place.components, "neighborhood");
        assert_eq!(place.postal_sublocality(), neighborhood.as_deref());
        assert_ne!(district.value, neighborhood);
    }

    #[test]
    fn ae_postal_absence_of_a_code() {
        // Mirrors test_ae_postal_absence_of_a_code.
        let place = a9_no_postal_codes();
        let result = postal_code_result(
            Some("AE".to_owned()),
            first_long_text(&place.components, TYPE_POSTAL_CODE),
            place.postal_postal_code().map(str::to_owned),
        );
        assert_eq!(result.value, None);
        assert_eq!(result.carrier, None);
        assert_eq!(result.status, POSTAL_ABSENT);
        assert_eq!(result.country_code.as_deref(), Some("AE"));
    }

    #[test]
    fn ae_no_locality_falls_back_to_postal_locality() {
        let components = vec![
            typed("Downtown", "Downtown", &["sublocality_level_1"]),
            typed("UAE", "AE", &["country"]),
        ];
        assert_eq!(
            city_resolutions(&components, Some("AE"), &PostalLocality::Unread),
            CityResolutions::NeedsPostalLocality
        );
        let city = city_one(
            &components,
            Some("AE"),
            &PostalLocality::Read(Some("Dubai Postal".to_owned())),
        );
        assert_eq!(city.value.as_deref(), Some("Dubai Postal"));
        assert_eq!(city.carrier, Some(CARRIER_POSTAL_ADDRESS_LOCALITY));
        assert_eq!(city.confidence, CONFIDENCE_FALLBACK);
        let none = city_one(&components, Some("AE"), &PostalLocality::Read(None));
        assert_eq!(none.confidence, CONFIDENCE_NONE);
    }

    #[test]
    fn ae_lying_labels() {
        // Mirrors test_lying_labels.
        let place = a7_rtl_index0();
        assert_eq!(
            first_long_text(&place.components, "route").as_deref(),
            Some("122nd Floor")
        );
        assert!(component_flags(&place.components).has_route);
        let district = district_resolution(&place.components, Some("AE"));
        assert_eq!(district.value.as_deref(), Some("برج خليفة"));
    }

    // --- United Kingdom, stated two value answer

    #[test]
    fn gb_two_value_answer() {
        // Mirrors test_gb_two_value_answer.
        let place = a4_disagree();
        let CityResolutions::Done(done) =
            city_resolutions(&place.components, Some("GB"), &PostalLocality::Unread)
        else {
            panic!("the British chain never reads postal")
        };
        assert_eq!(done.len(), 2);
        assert_eq!(done[0].value.as_deref(), Some("Bourton-on-the-Water"));
        assert_eq!(done[0].carrier, Some(CARRIER_LOCALITY));
        assert_eq!(done[0].confidence, CONFIDENCE_CONTESTED);
        assert_eq!(done[0].competing_value.as_deref(), Some("Cheltenham"));
        assert_eq!(done[0].competing_carrier, Some(CARRIER_POSTAL_TOWN));
        assert_eq!(done[1].value.as_deref(), Some("Cheltenham"));
        assert_eq!(done[1].carrier, Some(CARRIER_POSTAL_TOWN));
        assert_eq!(
            done[1].competing_value.as_deref(),
            Some("Bourton-on-the-Water")
        );
        assert_eq!(done[1].competing_carrier, Some(CARRIER_LOCALITY));
    }

    #[test]
    fn gb_equal_values_collapse_to_one_primary() {
        let components = vec![
            typed("Cheltenham", "Cheltenham", &["locality"]),
            typed("Cheltenham", "Cheltenham", &["postal_town"]),
            typed("United Kingdom", "GB", &["country"]),
        ];
        let city = city_one(&components, Some("GB"), &PostalLocality::Unread);
        assert_eq!(city.confidence, CONFIDENCE_PRIMARY);
        assert_eq!(city.carrier, Some(CARRIER_LOCALITY));
    }

    #[test]
    fn gb_single_carrier_cells() {
        let locality_only = vec![
            typed("Bourton-on-the-Water", "Bourton", &["locality"]),
            typed("United Kingdom", "GB", &["country"]),
        ];
        let city = city_one(&locality_only, Some("GB"), &PostalLocality::Unread);
        assert_eq!(city.confidence, CONFIDENCE_PRIMARY);
        let town_only = vec![
            typed("Cheltenham", "Cheltenham", &["postal_town"]),
            typed("United Kingdom", "GB", &["country"]),
        ];
        let city = city_one(&town_only, Some("GB"), &PostalLocality::Unread);
        assert_eq!(city.confidence, CONFIDENCE_FALLBACK);
        assert_eq!(city.carrier, Some(CARRIER_POSTAL_TOWN));
        let neither = vec![typed("United Kingdom", "GB", &["country"])];
        let city = city_one(&neither, Some("GB"), &PostalLocality::Unread);
        assert_eq!(city.confidence, CONFIDENCE_NONE);
    }

    // --- Country signal letter case

    #[test]
    fn lowercase_signals_route_and_carry_as_sent() {
        // Mirrors test_gb_lowercase_signal_keeps_the_contested_answer
        // and test_jp_lowercase_signal_takes_the_stated_table.
        let gb = a4_disagree();
        let CityResolutions::Done(done) =
            city_resolutions(&gb.components, Some("gb"), &PostalLocality::Unread)
        else {
            panic!("the British chain never reads postal")
        };
        assert_eq!(done.len(), 2);
        assert_eq!(done[0].country_code.as_deref(), Some("gb"));
        assert_eq!(done[0].confidence, CONFIDENCE_CONTESTED);
        let jp = a8_tokyo_english();
        let city = city_one(&jp.components, Some("jp"), &PostalLocality::Unread);
        assert_eq!(city.confidence, CONFIDENCE_PRIMARY);
        assert_eq!(city.country_code.as_deref(), Some("jp"));
        let district = district_resolution(&jp.components, Some("jp"));
        assert_eq!(district.confidence, CONFIDENCE_PRIMARY);
        let mixed = city_one(&jp.components, Some("Jp"), &PostalLocality::Unread);
        assert_eq!(mixed.confidence, CONFIDENCE_PRIMARY);
    }

    // --- Generic chain countries

    #[test]
    fn us_rescue_under_the_generic_chain() {
        // Mirrors test_us_rescue_under_the_generic_chain.
        let place = a2_no_locality();
        let city = city_one(&place.components, Some("US"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("Brooklyn"));
        assert_eq!(city.carrier, Some(CARRIER_SUBLOCALITY_LEVEL_1));
        assert_eq!(city.confidence, CONFIDENCE_HEURISTIC);
        assert_eq!(first_long_text(&place.components, "locality"), None);
    }

    #[test]
    fn us_plain_locality_under_the_generic_chain() {
        // Mirrors test_us_plain_locality_under_the_generic_chain.
        let place = p15_mall();
        let city = city_one(&place.components, Some("US"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("Santa Clara"));
        assert_eq!(city.carrier, Some(CARRIER_LOCALITY));
        assert_eq!(city.confidence, CONFIDENCE_HEURISTIC);
        assert_ne!(city.value.as_deref(), Some("Central San Jose"));
    }

    #[test]
    fn us_bridge_absence() {
        // Mirrors test_us_bridge_absence.
        let place = a1_no_street_number();
        let city = city_one(&place.components, Some("US"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("New York"));
        let flags = component_flags(&place.components);
        assert!(!flags.has_street_number);
        assert!(!flags.has_no_street_level);
    }

    #[test]
    fn vn_inversion_guard() {
        // Mirrors test_vn_inversion_guard.
        let place = p15_saigon();
        let city = city_one(&place.components, Some("VN"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("Thành phố Hồ Chí Minh"));
        assert_eq!(city.confidence, CONFIDENCE_HEURISTIC);
        assert_ne!(city.value.as_deref(), Some("Tan Son Hoa"));
        assert_eq!(place.postal_locality(), Some("Tan Son Hoa"));
    }

    #[test]
    fn il_thin_generic() {
        // Mirrors test_il_thin_generic.
        let place = a10_jerusalem_no_region();
        let city = city_one(&place.components, Some("IL"), &PostalLocality::Unread);
        assert_eq!(city.value.as_deref(), Some("Jerusalem"));
        assert_eq!(city.confidence, CONFIDENCE_HEURISTIC);
        assert_eq!(city.country_code.as_deref(), Some("IL"));
    }

    #[test]
    fn generic_chain_falls_to_postal_locality_last() {
        let components = vec![typed("France", "FR", &["country"])];
        assert_eq!(
            city_resolutions(&components, Some("FR"), &PostalLocality::Unread),
            CityResolutions::NeedsPostalLocality
        );
        let city = city_one(
            &components,
            Some("FR"),
            &PostalLocality::Read(Some("Paris".to_owned())),
        );
        assert_eq!(city.value.as_deref(), Some("Paris"));
        assert_eq!(city.carrier, Some(CARRIER_POSTAL_ADDRESS_LOCALITY));
        assert_eq!(city.confidence, CONFIDENCE_HEURISTIC);
    }

    #[test]
    fn district_is_none_outside_the_stated_countries() {
        let components = vec![
            typed("District Nine", "D9", &["sublocality_level_2"]),
            typed("Town", "Town", &["locality"]),
            typed("United States", "US", &["country"]),
        ];
        let district = district_resolution(&components, Some("US"));
        assert_eq!(district.value, None);
        assert_eq!(district.confidence, CONFIDENCE_NONE);
        assert_eq!(district.country_code.as_deref(), Some("US"));
        let no_country = district_resolution(&components, None);
        assert_eq!(no_country.country_code, None);
    }

    // --- Postal code composition

    #[test]
    fn postal_disagreement_headlines_the_component_value() {
        // The disagreement cell the Python suite names as unpinned
        // for lack of a recorded fixture, pinned here on authored
        // values.
        let result = postal_code_result(
            Some("JP".to_owned()),
            Some("111-0032".to_owned()),
            Some("999-9999".to_owned()),
        );
        assert_eq!(result.value.as_deref(), Some("111-0032"));
        assert_eq!(result.carrier, Some(CARRIER_POSTAL_CODE_COMPONENT));
        assert_eq!(result.status, POSTAL_PRESENT);
        assert_eq!(result.competing_value.as_deref(), Some("999-9999"));
        assert_eq!(
            result.competing_carrier,
            Some(CARRIER_POSTAL_ADDRESS_POSTAL_CODE)
        );
    }

    #[test]
    fn postal_single_carrier_cells() {
        let component_only =
            postal_code_result(Some("JP".to_owned()), Some("111-0032".to_owned()), None);
        assert_eq!(component_only.carrier, Some(CARRIER_POSTAL_CODE_COMPONENT));
        let postal_only =
            postal_code_result(Some("JP".to_owned()), None, Some("111-0032".to_owned()));
        assert_eq!(
            postal_only.carrier,
            Some(CARRIER_POSTAL_ADDRESS_POSTAL_CODE)
        );
        let neither = postal_code_result(Some("JP".to_owned()), None, None);
        assert_eq!(neither.status, POSTAL_ABSENT);
        assert_eq!(neither.value, None);
        assert_eq!(neither.carrier, None);
    }

    // --- Absence shapes

    #[test]
    fn everest_absence() {
        // Mirrors test_everest_absence.
        let place = p1_no_address();
        let city = city_one(&place.components, None, &PostalLocality::Read(None));
        assert_eq!(city.value, None);
        assert_eq!(city.carrier, None);
        assert_eq!(city.confidence, CONFIDENCE_NONE);
        assert_eq!(city.country_code, None);
    }

    #[test]
    fn no_carrier_set_at_all() {
        // Mirrors test_no_carrier_set_at_all.
        let place = a12_long_village();
        assert!(place.components.is_empty());
        let city = city_one(&place.components, None, &PostalLocality::Read(None));
        assert_eq!(city.confidence, CONFIDENCE_NONE);
        let flags = component_flags(&place.components);
        assert!(flags.has_no_street_level);
        assert!(!flags.has_route);
    }

    #[test]
    fn a11_empty_list_survival() {
        // Mirrors test_synthesized_a11_survival.
        let place = a11_empty_list();
        let flags = component_flags(&place.components);
        assert!(flags.has_no_street_level);
        let district = district_resolution(&place.components, None);
        assert_eq!(district.confidence, CONFIDENCE_NONE);
    }

    // --- Street flags

    #[test]
    fn spans_multiple_routes_counts_only_routes_with_text() {
        let two = vec![
            typed("Main Street", "Main St", &["route"]),
            typed("Second Avenue", "2nd Ave", &["route"]),
        ];
        assert!(component_flags(&two).spans_multiple_routes);
        let one_empty = vec![
            typed("Main Street", "Main St", &["route"]),
            typed("", "", &["route"]),
        ];
        assert!(!component_flags(&one_empty).spans_multiple_routes);
        assert!(component_flags(&one_empty).has_route);
    }

    #[test]
    fn premise_level_needs_premise_without_street_or_route() {
        let premise_only = vec![typed("Big Building", "Big", &["premise"])];
        assert!(component_flags(&premise_only).is_premise_level);
        let premise_and_route = vec![
            typed("Big Building", "Big", &["premise"]),
            typed("Main Street", "Main St", &["route"]),
        ];
        assert!(!component_flags(&premise_and_route).is_premise_level);
        let street_only = vec![typed("12", "12", &["street_number"])];
        let flags = component_flags(&street_only);
        assert!(flags.has_street_number);
        assert!(!flags.has_no_street_level);
    }

    // --- Plus code splitting, mirroring test_split_compound_code_edges
    // and the recorded split pins

    #[test]
    fn split_compound_code_recorded_forms() {
        assert_eq!(
            split_compound_code("P27Q+Q9 Brooklyn, NY, USA"),
            Some(("P27Q+Q9".to_owned(), "Brooklyn, NY, USA".to_owned()))
        );
        assert_eq!(
            split_compound_code("83G4+2P Santa Clara, CA, USA"),
            Some(("83G4+2P".to_owned(), "Santa Clara, CA, USA".to_owned()))
        );
        assert_eq!(
            split_compound_code("QMX9+V7 Tan Son Hoa, Ho Chi Minh, Vietnam"),
            Some((
                "QMX9+V7".to_owned(),
                "Tan Son Hoa, Ho Chi Minh, Vietnam".to_owned()
            ))
        );
    }

    #[test]
    fn split_compound_code_refusals() {
        assert_eq!(split_compound_code(""), None);
        assert_eq!(split_compound_code("87G8P27Q+Q9"), None);
        assert_eq!(split_compound_code("P27Q+Q9 "), None);
        assert_eq!(split_compound_code(" P27Q+Q9"), None);
        assert_eq!(split_compound_code(" "), None);
        assert_eq!(split_compound_code("C "), None);
        assert_eq!(split_compound_code(" C"), None);
    }

    #[test]
    fn split_compound_code_keeps_inner_spaces_and_strips_python_whitespace() {
        assert_eq!(
            split_compound_code("AB CD EF"),
            Some(("AB".to_owned(), "CD EF".to_owned()))
        );
        assert_eq!(
            split_compound_code("CODE  Double  Space"),
            Some(("CODE".to_owned(), "Double  Space".to_owned()))
        );
        // A tab is not the split point, so it stays inside the
        // code token when a space follows later, and the strip
        // rule is the Python set, which includes the information
        // separators and the next line character beside the
        // White_Space set.
        assert_eq!(
            split_compound_code("CODE\tTabbed Locality"),
            Some(("CODE\tTabbed".to_owned(), "Locality".to_owned()))
        );
        assert_eq!(
            split_compound_code("CODE Locality\u{1c}Town"),
            Some(("CODE".to_owned(), "Locality\u{1c}Town".to_owned()))
        );
        assert_eq!(
            split_compound_code("CODE \u{a0}Town"),
            Some(("CODE".to_owned(), "Town".to_owned()))
        );
        assert_eq!(
            split_compound_code("CODE Locality\u{85}"),
            Some(("CODE".to_owned(), "Locality".to_owned()))
        );
    }
}
