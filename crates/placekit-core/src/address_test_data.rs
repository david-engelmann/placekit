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
            ComponentData { long_text: Some("15".to_string()), short_text: Some("15".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("6".to_string()), short_text: Some("6".to_string()), types: vec![Some("sublocality_level_4".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("2-chōme".to_string()), short_text: Some("2-chōme".to_string()), types: vec![Some("sublocality_level_3".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Asakusa".to_string()), short_text: Some("Asakusa".to_string()), types: vec![Some("sublocality_level_2".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Taito City".to_string()), short_text: Some("Taito City".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Tokyo".to_string()), short_text: Some("Tokyo".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Japan".to_string()), short_text: Some("JP".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("111-0032".to_string()), short_text: Some("111-0032".to_string()), types: vec![Some("postal_code".to_string())] },
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
            ComponentData { long_text: Some("１５".to_string()), short_text: Some("１５".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("６".to_string()), short_text: Some("６".to_string()), types: vec![Some("sublocality_level_4".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("２丁目".to_string()), short_text: Some("２丁目".to_string()), types: vec![Some("sublocality_level_3".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("浅草".to_string()), short_text: Some("浅草".to_string()), types: vec![Some("sublocality_level_2".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("台東区".to_string()), short_text: Some("台東区".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("東京都".to_string()), short_text: Some("東京都".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("日本".to_string()), short_text: Some("JP".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("111-0032".to_string()), short_text: Some("111-0032".to_string()), types: vec![Some("postal_code".to_string())] },
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
            ComponentData { long_text: Some("１５".to_string()), short_text: Some("１５".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("６".to_string()), short_text: Some("６".to_string()), types: vec![Some("sublocality_level_4".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("２丁目".to_string()), short_text: Some("２丁目".to_string()), types: vec![Some("sublocality_level_3".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("浅草".to_string()), short_text: Some("浅草".to_string()), types: vec![Some("sublocality_level_2".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("台東区".to_string()), short_text: Some("台東区".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("東京都".to_string()), short_text: Some("東京都".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("日本".to_string()), short_text: Some("JP".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("111-0032".to_string()), short_text: Some("111-0032".to_string()), types: vec![Some("postal_code".to_string())] },
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
            ComponentData { long_text: Some("１５".to_string()), short_text: Some("１５".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("６".to_string()), short_text: Some("６".to_string()), types: vec![Some("sublocality_level_4".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("２丁目".to_string()), short_text: Some("２丁目".to_string()), types: vec![Some("sublocality_level_3".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("浅草".to_string()), short_text: Some("浅草".to_string()), types: vec![Some("sublocality_level_2".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("台東区".to_string()), short_text: Some("台東区".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("東京都".to_string()), short_text: Some("東京都".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("日本".to_string()), short_text: Some("JP".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("111-0032".to_string()), short_text: Some("111-0032".to_string()), types: vec![Some("postal_code".to_string())] },
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
            ComponentData { long_text: Some("1 Asakusa, Taito-ku".to_string()), short_text: Some("".to_string()), types: vec![] },
            ComponentData { long_text: Some("1".to_string()), short_text: Some("1".to_string()), types: vec![Some("subpremise".to_string())] },
            ComponentData { long_text: Some("３７".to_string()), short_text: Some("３７".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("３７".to_string()), short_text: Some("３７".to_string()), types: vec![Some("sublocality_level_4".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("４丁目".to_string()), short_text: Some("４丁目".to_string()), types: vec![Some("sublocality_level_3".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("浅草".to_string()), short_text: Some("浅草".to_string()), types: vec![Some("sublocality_level_2".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("台東区".to_string()), short_text: Some("台東区".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("東京都".to_string()), short_text: Some("東京都".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("日本".to_string()), short_text: Some("JP".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("111-0032".to_string()), short_text: Some("111-0032".to_string()), types: vec![Some("postal_code".to_string())] },
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
            ComponentData { long_text: Some("Burj khalifa".to_string()), short_text: Some("Burj khalifa".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("57XF+J8R".to_string()), short_text: Some("57XF+J8R".to_string()), types: vec![Some("plus_code".to_string())] },
            ComponentData { long_text: Some("122nd Floor".to_string()), short_text: Some("122nd Floor".to_string()), types: vec![Some("route".to_string())] },
            ComponentData { long_text: Some("وسط مدينة دبي".to_string()), short_text: Some("وسط مدينة دبي".to_string()), types: vec![Some("neighborhood".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("برج خليفة".to_string()), short_text: Some("برج خليفة".to_string()), types: vec![Some("sublocality_level_1".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("دبي".to_string()), short_text: Some("دبي".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("دبي".to_string()), short_text: Some("دبي".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("الإمارات العربية المتحدة".to_string()), short_text: Some("AE".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
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
            ComponentData { long_text: Some("Level 3, Armani Hotel Dubai".to_string()), short_text: Some("".to_string()), types: vec![] },
            ComponentData { long_text: Some("برج خليفة".to_string()), short_text: Some("برج خليفة".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("بوليفارد الشيخ محمد بن راشد".to_string()), short_text: Some("بوليفارد الشيخ محمد بن راشد".to_string()), types: vec![Some("route".to_string())] },
            ComponentData { long_text: Some("وسط مدينة دبي".to_string()), short_text: Some("وسط مدينة دبي".to_string()), types: vec![Some("neighborhood".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("برج خليفة".to_string()), short_text: Some("برج خليفة".to_string()), types: vec![Some("sublocality_level_1".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("دبي".to_string()), short_text: Some("دبي".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("دبي".to_string()), short_text: Some("دبي".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("الإمارات العربية المتحدة".to_string()), short_text: Some("AE".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
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
            ComponentData { long_text: Some("Al Murooj Complex".to_string()), short_text: Some("Al Murooj Complex".to_string()), types: vec![Some("premise".to_string())] },
            ComponentData { long_text: Some("Dubai Mall".to_string()), short_text: Some("Dubai Mall".to_string()), types: vec![Some("point_of_interest".to_string()), Some("establishment".to_string()), Some("landmark".to_string())] },
            ComponentData { long_text: Some("وسط مدينة دبي".to_string()), short_text: Some("وسط مدينة دبي".to_string()), types: vec![Some("neighborhood".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("المركز التجاري الثانية".to_string()), short_text: Some("المركز التجاري الثانية".to_string()), types: vec![Some("sublocality_level_1".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("دبي".to_string()), short_text: Some("دبي".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("دبي".to_string()), short_text: Some("دبي".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("الإمارات العربية المتحدة".to_string()), short_text: Some("AE".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
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
            ComponentData { long_text: Some("1".to_string()), short_text: Some("1".to_string()), types: vec![Some("street_number".to_string())] },
            ComponentData { long_text: Some("Sherborne Street".to_string()), short_text: Some("Sherborne St".to_string()), types: vec![Some("route".to_string())] },
            ComponentData { long_text: Some("Bourton-on-the-Water".to_string()), short_text: Some("Bourton-on-the-Water".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Cheltenham".to_string()), short_text: Some("Cheltenham".to_string()), types: vec![Some("postal_town".to_string())] },
            ComponentData { long_text: Some("Gloucestershire".to_string()), short_text: Some("Gloucestershire".to_string()), types: vec![Some("administrative_area_level_2".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("England".to_string()), short_text: Some("England".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("United Kingdom".to_string()), short_text: Some("GB".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("GL54 2BY".to_string()), short_text: Some("GL54 2BY".to_string()), types: vec![Some("postal_code".to_string())] },
        ],
        postal: None,
    }
}

pub(crate) fn a2_no_locality() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("292".to_string()), short_text: Some("292".to_string()), types: vec![Some("street_number".to_string())] },
            ComponentData { long_text: Some("Bedford Avenue".to_string()), short_text: Some("Bedford Ave".to_string()), types: vec![Some("route".to_string())] },
            ComponentData { long_text: Some("Williamsburg".to_string()), short_text: Some("Williamsburg".to_string()), types: vec![Some("neighborhood".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Brooklyn".to_string()), short_text: Some("Brooklyn".to_string()), types: vec![Some("sublocality_level_1".to_string()), Some("sublocality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Kings County".to_string()), short_text: Some("Kings County".to_string()), types: vec![Some("administrative_area_level_2".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("New York".to_string()), short_text: Some("NY".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("United States".to_string()), short_text: Some("US".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("11249".to_string()), short_text: Some("11249".to_string()), types: vec![Some("postal_code".to_string())] },
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
            ComponentData { long_text: Some("2801".to_string()), short_text: Some("2801".to_string()), types: vec![Some("street_number".to_string())] },
            ComponentData { long_text: Some("Stevens Creek Boulevard".to_string()), short_text: Some("Stevens Creek Blvd".to_string()), types: vec![Some("route".to_string())] },
            ComponentData { long_text: Some("Central San Jose".to_string()), short_text: Some("Central San Jose".to_string()), types: vec![Some("neighborhood".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Santa Clara".to_string()), short_text: Some("Santa Clara".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Santa Clara County".to_string()), short_text: Some("Santa Clara County".to_string()), types: vec![Some("administrative_area_level_2".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("California".to_string()), short_text: Some("CA".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("United States".to_string()), short_text: Some("US".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("95050".to_string()), short_text: Some("95050".to_string()), types: vec![Some("postal_code".to_string())] },
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
            ComponentData { long_text: Some("Williamsburg Bridge".to_string()), short_text: Some("Williamsburg Bridge".to_string()), types: vec![Some("route".to_string())] },
            ComponentData { long_text: Some("New York".to_string()), short_text: Some("New York".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("New York".to_string()), short_text: Some("NY".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("United States".to_string()), short_text: Some("US".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
        ],
        postal: None,
    }
}

pub(crate) fn p15_saigon() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Đường Nguyễn Văn Trỗi".to_string()), short_text: Some("Đ. Nguyễn Văn Trỗi".to_string()), types: vec![Some("route".to_string())] },
            ComponentData { long_text: Some("Thành phố Hồ Chí Minh".to_string()), short_text: Some("Thành phố Hồ Chí Minh".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Hồ Chí Minh".to_string()), short_text: Some("Hồ Chí Minh".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Vietnam".to_string()), short_text: Some("VN".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
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
            ComponentData { long_text: Some("Jerusalem".to_string()), short_text: Some("Jerusalem".to_string()), types: vec![Some("locality".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Jerusalem District".to_string()), short_text: Some("Jerusalem District".to_string()), types: vec![Some("administrative_area_level_1".to_string()), Some("political".to_string())] },
            ComponentData { long_text: Some("Israel".to_string()), short_text: Some("IL".to_string()), types: vec![Some("country".to_string()), Some("political".to_string())] },
        ],
        postal: None,
    }
}

pub(crate) fn p1_no_address() -> FixturePlace {
    FixturePlace {
        components: vec![
            ComponentData { long_text: Some("Mount Everest".to_string()), short_text: Some("Monte Everest".to_string()), types: vec![Some("mountain_peak".to_string()), Some("natural_feature".to_string()), Some("establishment".to_string())] },
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
            ComponentData { long_text: Some("".to_string()), short_text: Some("".to_string()), types: vec![Some("route".to_string())] },
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
