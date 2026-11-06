// Fixture places for the address tests, generated from the
// recorded and synthesized corpus by the Round 53 parity
// tooling. Each value is the decoded model value the Python
// helpers read, so the core tests pin the same readings the
// Python suite pins in tests/test_address.py.

// Two fields of the postal record are never read by the core
// tests. They stay because the record mirrors the decoded
// Python postal address in full, and dropping them would
// make the generated data lossy.
#[allow(dead_code)]
pub(crate) struct FixturePostal {
    pub(crate) region_code: Option<&'static str>,
    pub(crate) postal_code: Option<&'static str>,
    pub(crate) locality: Option<&'static str>,
    pub(crate) sublocality: Option<&'static str>,
    pub(crate) administrative_area: Option<&'static str>,
}

pub(crate) struct FixturePlace {
    pub(crate) components: Vec<ComponentData>,
    pub(crate) postal: Option<FixturePostal>,
}

impl FixturePlace {
    /// The postal code field under the Python field reader
    /// rule, where a missing or empty field reads as None.
    pub(crate) fn postal_postal_code(&self) -> Option<&str> {
        self.postal
            .as_ref()
            .and_then(|postal| postal.postal_code)
            .filter(|value| !value.is_empty())
    }

    pub(crate) fn postal_locality(&self) -> Option<&str> {
        self.postal
            .as_ref()
            .and_then(|postal| postal.locality)
            .filter(|value| !value.is_empty())
    }

    pub(crate) fn postal_sublocality(&self) -> Option<&str> {
        self.postal
            .as_ref()
            .and_then(|postal| postal.sublocality)
            .filter(|value| !value.is_empty())
    }
}

pub(crate) fn a8_tokyo_english() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("15".as_bytes().to_vec()), short_text: Some("15".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("6".as_bytes().to_vec()), short_text: Some("6".as_bytes().to_vec()), types: vec![Some("sublocality_level_4".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("2-chōme".as_bytes().to_vec()), short_text: Some("2-chōme".as_bytes().to_vec()), types: vec![Some("sublocality_level_3".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Asakusa".as_bytes().to_vec()), short_text: Some("Asakusa".as_bytes().to_vec()), types: vec![Some("sublocality_level_2".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Taito City".as_bytes().to_vec()), short_text: Some("Taito City".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Tokyo".as_bytes().to_vec()), short_text: Some("Tokyo".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Japan".as_bytes().to_vec()), short_text: Some("JP".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("111-0032".as_bytes().to_vec()), short_text: Some("111-0032".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("JP"),
            postal_code: Some("111-0032"),
            locality: None,
            sublocality: None,
            administrative_area: Some("Tokyo"),
        }),
    }
}

pub(crate) fn a8_tokyo_japanese() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("１５".as_bytes().to_vec()), short_text: Some("１５".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("６".as_bytes().to_vec()), short_text: Some("６".as_bytes().to_vec()), types: vec![Some("sublocality_level_4".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("２丁目".as_bytes().to_vec()), short_text: Some("２丁目".as_bytes().to_vec()), types: vec![Some("sublocality_level_3".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("浅草".as_bytes().to_vec()), short_text: Some("浅草".as_bytes().to_vec()), types: vec![Some("sublocality_level_2".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("台東区".as_bytes().to_vec()), short_text: Some("台東区".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("東京都".as_bytes().to_vec()), short_text: Some("東京都".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("日本".as_bytes().to_vec()), short_text: Some("JP".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("111-0032".as_bytes().to_vec()), short_text: Some("111-0032".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("JP"),
            postal_code: Some("111-0032"),
            locality: None,
            sublocality: None,
            administrative_area: Some("東京都"),
        }),
    }
}

pub(crate) fn a5_sublocality_chains() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("１５".as_bytes().to_vec()), short_text: Some("１５".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("６".as_bytes().to_vec()), short_text: Some("６".as_bytes().to_vec()), types: vec![Some("sublocality_level_4".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("２丁目".as_bytes().to_vec()), short_text: Some("２丁目".as_bytes().to_vec()), types: vec![Some("sublocality_level_3".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("浅草".as_bytes().to_vec()), short_text: Some("浅草".as_bytes().to_vec()), types: vec![Some("sublocality_level_2".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("台東区".as_bytes().to_vec()), short_text: Some("台東区".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("東京都".as_bytes().to_vec()), short_text: Some("東京都".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("日本".as_bytes().to_vec()), short_text: Some("JP".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("111-0032".as_bytes().to_vec()), short_text: Some("111-0032".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("JP"),
            postal_code: Some("111-0032"),
            locality: None,
            sublocality: None,
            administrative_area: Some("東京都"),
        }),
    }
}

pub(crate) fn a6_block_addressing() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("１５".as_bytes().to_vec()), short_text: Some("１５".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("６".as_bytes().to_vec()), short_text: Some("６".as_bytes().to_vec()), types: vec![Some("sublocality_level_4".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("２丁目".as_bytes().to_vec()), short_text: Some("２丁目".as_bytes().to_vec()), types: vec![Some("sublocality_level_3".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("浅草".as_bytes().to_vec()), short_text: Some("浅草".as_bytes().to_vec()), types: vec![Some("sublocality_level_2".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("台東区".as_bytes().to_vec()), short_text: Some("台東区".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("東京都".as_bytes().to_vec()), short_text: Some("東京都".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("日本".as_bytes().to_vec()), short_text: Some("JP".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("111-0032".as_bytes().to_vec()), short_text: Some("111-0032".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("JP"),
            postal_code: Some("111-0032"),
            locality: None,
            sublocality: None,
            administrative_area: Some("東京都"),
        }),
    }
}

pub(crate) fn a13_premise_and_subpremise() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("1 Asakusa, Taito-ku".as_bytes().to_vec()), short_text: Some("".as_bytes().to_vec()), types: vec![] },
            ComponentData { long_text: Some("1".as_bytes().to_vec()), short_text: Some("1".as_bytes().to_vec()), types: vec![Some("subpremise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("３７".as_bytes().to_vec()), short_text: Some("３７".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("３７".as_bytes().to_vec()), short_text: Some("３７".as_bytes().to_vec()), types: vec![Some("sublocality_level_4".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("４丁目".as_bytes().to_vec()), short_text: Some("４丁目".as_bytes().to_vec()), types: vec![Some("sublocality_level_3".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("浅草".as_bytes().to_vec()), short_text: Some("浅草".as_bytes().to_vec()), types: vec![Some("sublocality_level_2".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("台東区".as_bytes().to_vec()), short_text: Some("台東区".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("東京都".as_bytes().to_vec()), short_text: Some("東京都".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("日本".as_bytes().to_vec()), short_text: Some("JP".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("111-0032".as_bytes().to_vec()), short_text: Some("111-0032".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("JP"),
            postal_code: Some("111-0032"),
            locality: None,
            sublocality: None,
            administrative_area: Some("東京都"),
        }),
    }
}

pub(crate) fn a7_rtl_index0() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Burj khalifa".as_bytes().to_vec()), short_text: Some("Burj khalifa".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("57XF+J8R".as_bytes().to_vec()), short_text: Some("57XF+J8R".as_bytes().to_vec()), types: vec![Some("plus_code".as_bytes().to_vec())] },
            ComponentData { long_text: Some("122nd Floor".as_bytes().to_vec()), short_text: Some("122nd Floor".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
            ComponentData { long_text: Some("وسط مدينة دبي".as_bytes().to_vec()), short_text: Some("وسط مدينة دبي".as_bytes().to_vec()), types: vec![Some("neighborhood".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("برج خليفة".as_bytes().to_vec()), short_text: Some("برج خليفة".as_bytes().to_vec()), types: vec![Some("sublocality_level_1".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("دبي".as_bytes().to_vec()), short_text: Some("دبي".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("دبي".as_bytes().to_vec()), short_text: Some("دبي".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("الإمارات العربية المتحدة".as_bytes().to_vec()), short_text: Some("AE".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("AE"),
            postal_code: None,
            locality: Some("دبي"),
            sublocality: Some("وسط مدينة دبي"),
            administrative_area: Some("دبي"),
        }),
    }
}

pub(crate) fn a7_rtl_index1() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Level 3, Armani Hotel Dubai".as_bytes().to_vec()), short_text: Some("".as_bytes().to_vec()), types: vec![] },
            ComponentData { long_text: Some("برج خليفة".as_bytes().to_vec()), short_text: Some("برج خليفة".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("بوليفارد الشيخ محمد بن راشد".as_bytes().to_vec()), short_text: Some("بوليفارد الشيخ محمد بن راشد".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
            ComponentData { long_text: Some("وسط مدينة دبي".as_bytes().to_vec()), short_text: Some("وسط مدينة دبي".as_bytes().to_vec()), types: vec![Some("neighborhood".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("برج خليفة".as_bytes().to_vec()), short_text: Some("برج خليفة".as_bytes().to_vec()), types: vec![Some("sublocality_level_1".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("دبي".as_bytes().to_vec()), short_text: Some("دبي".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("دبي".as_bytes().to_vec()), short_text: Some("دبي".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("الإمارات العربية المتحدة".as_bytes().to_vec()), short_text: Some("AE".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("AE"),
            postal_code: None,
            locality: Some("دبي"),
            sublocality: None,
            administrative_area: None,
        }),
    }
}

pub(crate) fn a9_no_postal_codes() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Al Murooj Complex".as_bytes().to_vec()), short_text: Some("Al Murooj Complex".as_bytes().to_vec()), types: vec![Some("premise".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Dubai Mall".as_bytes().to_vec()), short_text: Some("Dubai Mall".as_bytes().to_vec()), types: vec![Some("point_of_interest".as_bytes().to_vec()), Some("establishment".as_bytes().to_vec()), Some("landmark".as_bytes().to_vec())] },
            ComponentData { long_text: Some("وسط مدينة دبي".as_bytes().to_vec()), short_text: Some("وسط مدينة دبي".as_bytes().to_vec()), types: vec![Some("neighborhood".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("المركز التجاري الثانية".as_bytes().to_vec()), short_text: Some("المركز التجاري الثانية".as_bytes().to_vec()), types: vec![Some("sublocality_level_1".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("دبي".as_bytes().to_vec()), short_text: Some("دبي".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("دبي".as_bytes().to_vec()), short_text: Some("دبي".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("الإمارات العربية المتحدة".as_bytes().to_vec()), short_text: Some("AE".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("AE"),
            postal_code: None,
            locality: Some("دبي"),
            sublocality: Some("وسط مدينة دبي"),
            administrative_area: Some("دبي"),
        }),
    }
}

pub(crate) fn a4_disagree() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("1".as_bytes().to_vec()), short_text: Some("1".as_bytes().to_vec()), types: vec![Some("street_number".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Sherborne Street".as_bytes().to_vec()), short_text: Some("Sherborne St".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Bourton-on-the-Water".as_bytes().to_vec()), short_text: Some("Bourton-on-the-Water".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Cheltenham".as_bytes().to_vec()), short_text: Some("Cheltenham".as_bytes().to_vec()), types: vec![Some("postal_town".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Gloucestershire".as_bytes().to_vec()), short_text: Some("Gloucestershire".as_bytes().to_vec()), types: vec![Some("administrative_area_level_2".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("England".as_bytes().to_vec()), short_text: Some("England".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("United Kingdom".as_bytes().to_vec()), short_text: Some("GB".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("GL54 2BY".as_bytes().to_vec()), short_text: Some("GL54 2BY".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: None,
    }
}

pub(crate) fn a2_no_locality() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("292".as_bytes().to_vec()), short_text: Some("292".as_bytes().to_vec()), types: vec![Some("street_number".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Bedford Avenue".as_bytes().to_vec()), short_text: Some("Bedford Ave".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Williamsburg".as_bytes().to_vec()), short_text: Some("Williamsburg".as_bytes().to_vec()), types: vec![Some("neighborhood".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Brooklyn".as_bytes().to_vec()), short_text: Some("Brooklyn".as_bytes().to_vec()), types: vec![Some("sublocality_level_1".as_bytes().to_vec()), Some("sublocality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Kings County".as_bytes().to_vec()), short_text: Some("Kings County".as_bytes().to_vec()), types: vec![Some("administrative_area_level_2".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("New York".as_bytes().to_vec()), short_text: Some("NY".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("United States".as_bytes().to_vec()), short_text: Some("US".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("11249".as_bytes().to_vec()), short_text: Some("11249".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("US"),
            postal_code: Some("11249"),
            locality: Some("Brooklyn"),
            sublocality: None,
            administrative_area: Some("New York"),
        }),
    }
}

pub(crate) fn p15_mall() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("2801".as_bytes().to_vec()), short_text: Some("2801".as_bytes().to_vec()), types: vec![Some("street_number".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Stevens Creek Boulevard".as_bytes().to_vec()), short_text: Some("Stevens Creek Blvd".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Central San Jose".as_bytes().to_vec()), short_text: Some("Central San Jose".as_bytes().to_vec()), types: vec![Some("neighborhood".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Santa Clara".as_bytes().to_vec()), short_text: Some("Santa Clara".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Santa Clara County".as_bytes().to_vec()), short_text: Some("Santa Clara County".as_bytes().to_vec()), types: vec![Some("administrative_area_level_2".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("California".as_bytes().to_vec()), short_text: Some("CA".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("United States".as_bytes().to_vec()), short_text: Some("US".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("95050".as_bytes().to_vec()), short_text: Some("95050".as_bytes().to_vec()), types: vec![Some("postal_code".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("US"),
            postal_code: Some("95050"),
            locality: Some("Santa Clara"),
            sublocality: None,
            administrative_area: Some("California"),
        }),
    }
}

pub(crate) fn a1_no_street_number() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Williamsburg Bridge".as_bytes().to_vec()), short_text: Some("Williamsburg Bridge".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
            ComponentData { long_text: Some("New York".as_bytes().to_vec()), short_text: Some("New York".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("New York".as_bytes().to_vec()), short_text: Some("NY".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("United States".as_bytes().to_vec()), short_text: Some("US".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
        ],
        postal: None,
    }
}

pub(crate) fn p15_saigon() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Đường Nguyễn Văn Trỗi".as_bytes().to_vec()), short_text: Some("Đ. Nguyễn Văn Trỗi".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Thành phố Hồ Chí Minh".as_bytes().to_vec()), short_text: Some("Thành phố Hồ Chí Minh".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Hồ Chí Minh".as_bytes().to_vec()), short_text: Some("Hồ Chí Minh".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Vietnam".as_bytes().to_vec()), short_text: Some("VN".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
        ],
        postal: Some(FixturePostal {
            region_code: Some("VN"),
            postal_code: None,
            locality: Some("Tan Son Hoa"),
            sublocality: None,
            administrative_area: Some("Ho Chi Minh"),
        }),
    }
}

pub(crate) fn a10_jerusalem_no_region() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Jerusalem".as_bytes().to_vec()), short_text: Some("Jerusalem".as_bytes().to_vec()), types: vec![Some("locality".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Jerusalem District".as_bytes().to_vec()), short_text: Some("Jerusalem District".as_bytes().to_vec()), types: vec![Some("administrative_area_level_1".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
            ComponentData { long_text: Some("Israel".as_bytes().to_vec()), short_text: Some("IL".as_bytes().to_vec()), types: vec![Some("country".as_bytes().to_vec()), Some("political".as_bytes().to_vec())] },
        ],
        postal: None,
    }
}

pub(crate) fn p1_no_address() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Mount Everest".as_bytes().to_vec()), short_text: Some("Monte Everest".as_bytes().to_vec()), types: vec![Some("mountain_peak".as_bytes().to_vec()), Some("natural_feature".as_bytes().to_vec()), Some("establishment".as_bytes().to_vec())] },
        ],
        postal: None,
    }
}

pub(crate) fn a12_long_village() -> FixturePlace {
    FixturePlace {
        components: vec![
        ],
        postal: None,
    }
}

pub(crate) fn a11_empty_text() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("".as_bytes().to_vec()), short_text: Some("".as_bytes().to_vec()), types: vec![Some("route".as_bytes().to_vec())] },
        ],
        postal: None,
    }
}

pub(crate) fn a11_empty_list() -> FixturePlace {
    FixturePlace {
        components: vec![
        ],
        postal: None,
    }
}
