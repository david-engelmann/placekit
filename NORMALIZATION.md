# Normalizing addresses with placekit

This guide teaches the address handling that the recorded corpus and the
`placekit.address` module embody. It is written for a working programmer
who reads Places responses and has met an address that refused to behave.
The oddities catalogue explains why the data looks the way it does, the
per country readings say how far a city reading can be trusted, and the
recipes show the handling code. Nothing here surveys address practice in
countries the corpus never recorded.

## 1. A response is a sample and not a fact

[Research] Google states that the response format is not guaranteed to
remain the same between requests. The Google Place reference, as quoted
in the Round 11 research behind this guide, warns that the address
component array may hold more components than the formatted address
shows. The address component array does not necessarily include all the
political entities that contain an address. A component can change
position and can change type and may be missing in a later response, and
the number of components varies by address and can change over time for
the same address.

[Cannot promise] Because a component can vanish, every rule in this guide
degrades to an honest absence rather than to a guess, and no rule keys
identity on component text. The formatted address and the component array
are parallel products of the same response, so this guide never treats
one as a parse of the other.

[Cannot promise] The corpus behind this guide was recorded in October
2026 and this guide makes no claim about current API behaviour. The
corpus holds same day repeat pairs only, and every recorded pair returned
identical component type sets, so the corpus neither proves nor refutes
change over time. Read every recorded claim below as an account of that
dated corpus.

[Cannot promise] Judging whether components are confirmed or replaced or
inferred is the job of the Address Validation API, a separate paid
product whose verdicts this library does not absorb. Places components
cannot carry a deliverability verdict.

## 2. How claims are marked and how far the evidence reaches

Every claim bearing paragraph and every claim bearing table row in this
guide opens with one claim tag, and the tag is the first token of the
paragraph or the first cell content of the row. The eight tags and their
meanings are the marking key.

- [Recorded] means the claim is pinned by a recorded fixture excerpt or
  verified against fixture bytes, and it licenses a shape claim and never
  a prevalence claim on its own.
- [Cassette reported] means the claim rests on cassette reading with no
  isolating fixture excerpt, and it licenses prose teaching only.
- [Synthesized] means the shape is authored under a synthesized fixture
  and no recording of it exists.
- [Stated rule] means the claim is a rule of the shipped module as stated
  in its design record, whether or not a fixture pins it.
- [Heuristic] means the claim comes from the generic fallback chain or
  from caller judgement labelled as judgement.
- [Recipe] means the passage is documented guidance for caller code
  rather than library behaviour.
- [Research] means the claim is an external statement from the Round 11
  research with its source named in the same paragraph.
- [Cannot promise] means the passage states a boundary.

Code blocks inherit the tag of the paragraph that introduces them.
Headings carry no tags, because the tag belongs to claims and not to
furniture. This section and the front matter above it are apparatus
rather than claims, so they carry no tags, and no paragraph in any later
section may claim that standing.

The evidence layers carry different weight and the guide keeps them
apart. Cassette bodies carry prevalence, and the address evidence is
counted on the exchanges that carry address data, giving 12 exchanges
that requested addressComponents and 10 that requested postalAddress
holding 88 address bearing observations over 68 distinct places and 674
components. Recorded fixture excerpts prove shape and pin behaviour and
never prove how common a shape is. A prevalence claim in this guide rests
on cassette counts and never on a one place or two place fixture excerpt.
Synthesized fixtures prove only that the typed layer decodes an authored
shape. Round 11 research statements are research evidence and never
corpus evidence. The address case accounting comes from the fixture
manifest, giving 12 recorded cases of 18, with 1 synthesized candidate
and 2 hunted and missed and 3 still open.

Five shipped fixture pairs are byte identical under two names and each
pair counts as one evidence item and never as two. The pairs are
recorded_A3_postal_town_carries_city.json filed also as
recorded_A4_locality_postal_town_disagree.json, and
recorded_A5_sublocality_chains.json filed also as
recorded_A6_japanese_block_addressing.json, and
recorded_P1_no_address_natural_feature.json filed also as
recorded_V5_plus_code_global_only.json, and
recorded_P12_contained_place.json filed also as
recorded_P15_richest_mall_store.json, and
recorded_P15_details_depth_saigon.json filed also as
recorded_H10_seasonal_offset_sample.json. Later mentions cite a pair by
its two case ids with the words one item between them. The Saigon hotel
also appears under recorded_H11_description_order_vs_period_anchor.json
carrying the German request reading, and that file is a genuine second
reading rather than a duplicate.

Absence comes in three postures and the guide keeps them apart. A mask
backed absence means the request asked for the carrier and the body
omitted it. An unobserved absence means the mask never asked, so the
record says nothing either way. The no carrier set shape means a place
carries neither the components nor a postalAddress at all. The typed
layer collapses a missing wire key and an empty wire value into the same
reading, so the distinction lives in the request masks and in raw.

## 3. The two carrier sets at a glance

[Stated rule] A place carries two parallel carrier sets. The address
components are a list of typed text pieces in list order, and the
postalAddress is a structured summary with its own locality and
sublocality and administrative area and postal code and region code
fields. The two sets overlap without agreeing by construction, and
neither is a copy of the other. The formatted address and the short
formatted address are parallel text products beside them, and no helper
in placekit.address parses either text.

[Stated rule] The module placekit.address is the shipped reader of the
two sets. It looks components up by type, reads the country and the
postal code across both sets, resolves a city and a district with the
carrier and the confidence grade in the open, and splits compound plus
codes. Signatures and field lists live in the module and its stub, and
this guide teaches the behaviour rather than restating the surface.

[Cannot promise] The surface is deliberately narrower than the address
problem. placekit.address ships no formatter and no display composer and
no envelope renderer. The rest of the held surface inventory is stated
in full with the decision rules in section 6, and the recipes point at
caller code or at libaddressinput metadata wherever a reader would
otherwise hunt for those behaviours.


## 4. The oddities catalogue

[Stated rule] The catalogue is organised by failure mode rather than by
country or by component type, because country organisation scatters one
failure across five entries and component organisation hides the carrier
rivalry that is the deepest lesson. Each cluster ends with the consumer
habit that survives it.

### Cluster A. Rival carriers and the missing city

[Recorded] No single field carries the city across countries. The corpus
offers locality and postal_town and the levelled sublocality family and
neighborhood and administrative area levels as component carriers, and
the postalAddress offers a parallel set of its own, and which carrier
holds the city changes by country.

[Recorded] One place in recorded_A2_no_locality_sublocality_city.json
carries no locality component at all, and its city lives in sublocality
level 1 and in the postalAddress locality, both reading Brooklyn. The
United States reading rests on 3 details places across 2 states with 3
different geometries and no American search set with components exists
and every American claim in the guide must carry this thin warning in
the same paragraph.

[Recorded] The mirror image occurs on the one Vietnamese place in
recorded_P15_details_depth_saigon.json, whose component locality holds
the city while its postalAddress locality holds a ward name, Tan Son Hoa,
found in no component. A postal wins rule generalised from New York
demotes a city to a ward. The Vietnam reading rests on 1 distinct place
seen twice in two details calls under English and German requests and it
must be presented as single place status wherever it appears.

[Recorded] The postal sublocality never aligns with component
sublocality level 1. In the Dubai cassette set it appears on 6 of 20
places and copies the neighborhood value on 6 of 6, and the pinned place
in recorded_A9_country_without_postal_codes.json shows the split on one
body. In the Japanese sets the postal locality and sublocality are absent
on 40 of 40 observations while the component locality is present on 40 of
40, so the Japanese postal set names no city at all.

[Recorded] In the British set the civil place and the mailing town
coexist and disagree on 20 of 20 places in the Bourton-on-the-Water
cassette set, locality reading Bourton-on-the-Water and postal_town
reading Cheltenham, and the formatted address stacks both in that order.
No postalAddress exists in the British record to arbitrate.

[Stated rule] The habit that survives this cluster is that a city reading
names its carrier or it is not a reading this guide endorses.

### Cluster B. Labels, text and identity that cannot be taken at face value

[Recorded] Twelve recorded components across the Japanese and Dubai
cassette sets carry no types key at all and sit in the most specific slot
of their lists holding floor and unit and mall level descriptions. A type
keyed lookup walks past them, and guessing a type for them would
fabricate data the wire never sent.

```python
from placekit import address

# The fused first component of the A13 place carries no types key, and
# neither does the Level 3 component of the second Dubai place in A7.
untyped = address.untyped_components(place.address_components)
untyped[0].long_text
```

[Recorded] A component type names a role and the text inside that role
need not match it. The first place in recorded_A7_rtl_script_address.json
carries a route component whose long text reads 122nd Floor, verified
against the fixture bytes, while its presence flags answer truthfully.

```python
from placekit import address, types

route_text = address.component_long_text(place.address_components, types.TYPE_ROUTE)
has_route = address.has_route(place.address_components)
flags = address.address_flags(place)
```

[Cassette reported] Two further label lies rest on cassette reading with
no isolating fixture excerpt, so they get prose only and no example. A
street_number component holds a floor label in the Emirates set and a
unit label in the Bourton set, and a neighborhood component holds a mall
name on one Dubai place.

[Recorded] The neighborhood carrier is barred as a city source for a
pinned reason as well. The mall store place in
recorded_P15_richest_mall_store.json, one item with
recorded_P12_contained_place.json, carries a neighborhood reading Central
San Jose beside a locality reading Santa Clara. The United States reading
rests on 3 details places across 2 states with 3 different geometries and
no American search set with components exists and every American claim in
the guide must carry this thin warning in the same paragraph.

[Recorded] Component language tags range wider than the request languages
and are not reliable script labels. The Everest component in
recorded_P1_no_address_natural_feature.json reads Monte Everest in its
Spanish short text while its language code reads en. No helper filters
or groups by language tag.

[Cassette reported] The cassette sets hold more of the same
unreliability with no isolating fixture excerpt. Transliteration tags
appear inside mismatched requests, and an undetermined tag sits on
English text.

[Recorded] One place can carry two components of the winning type, and
two components on one place can hold the same text. Twelve of the 40
Japanese cassette observations carry two premise components, and the
place in recorded_A13_premise_and_subpremise.json holds one digit string
as both its premise text and its sublocality level 4 text, on distinct
components. Text equality is not identity.

[Cassette reported] The same string can also occupy more than one role
at once. On one Bourton place the string Lansdowne reads as route and as
sublocality level 1 in overlapping roles, while the street number on
that place reads 3. In the Dubai set the
neighborhood sits ahead of the sublocality on most places and behind the
locality on two places that lead with a typeless component, and one place
drops neighborhood entirely. Neither shape is isolated in an excerpt.

[Stated rule] The habit that survives this cluster is that presence flags
trust types by design while display and city logic may not trust text.

### Cluster C. Order, count and language that move

[Research] The instability warning from the opening section, drawn from
the Google Place reference as quoted in the Round 11 research, is
recapped here because this cluster is where its recorded shadows fall.
The corpus holds no recorded instance of a change between requests.

[Recorded] Component counts across the 88 address bearing cassette
observations run from 1 to 11 and count alone separates almost nothing.
The segment before the political tail takes many orders as street level
components come and go, while the political tail from the city carrier
onward keeps a fixed relative order.

```python
from placekit import address, types

components = place.address_components
chain = address.find_components(components, types.TYPE_SUBLOCALITY)
district = address.component_long_text(components, types.TYPE_SUBLOCALITY_LEVEL_2)
fragment = address.component_long_text(components, types.TYPE_SUBLOCALITY_LEVEL_4)
```

[Recorded] The bare sublocality lookup returns three components in list
order with the level 4 block fragment first, on the place in
recorded_A5_sublocality_chains.json, filed also as
recorded_A6_japanese_block_addressing.json and counted as one item. The
district text comes from level 2 and the level 4 text is a fragment and
never a city, because every levelled component carries the bare type as a
companion.

[Recorded] The same Tokyo place under Japanese and English requests
carries an identical ordered type sequence and a different everything
else, in recorded_A8_tokyo_japanese.json and recorded_A8_tokyo_english
.json. Text and script and formatted order and address line segmentation
all move, and at cassette level all 18 shared places match in type
sequence and count while each file holds 2 place ids the other lacks.

[Recorded] Two details calls for one Jerusalem place under two region
settings returned identical address content, in
recorded_A10_jerusalem_no_region_code.json and
recorded_A10_jerusalem_region_ps.json, teaching an absence of observed
variance and nothing stronger. The Israel reading rests on 1 distinct
place seen twice under two region settings and it must be presented as
single place status wherever it appears.

[Recorded] The longest formatted addresses in the corpus are Arabic
rather than Welsh. Three Dubai formatted addresses in the cassette run
from 126 to 130 characters, and the second place in
recorded_A7_rtl_script_address.json measures 130 characters. The 46
character Welsh addresses are nowhere near the record.

[Stated rule] The habit that survives this cluster is that absolute
position and head order and text length carry no meaning a consumer may
build on.

### Cluster D. Absence in its several kinds

[Recorded] A missing postal code can be a property of the country rather
than a gap in one address. The Dubai set requested both postal carriers
on every place and returned a code in neither carrier on 20 of 20 places,
while the postalAddress object itself was present on every place, and
recorded_A9_country_without_postal_codes.json carries that absence on one
body. An unrequested absence would prove nothing.

[Recorded] One place in recorded_P1_no_address_natural_feature.json,
filed also as recorded_V5_plus_code_global_only.json and counted as one
item, carries a single component naming the place itself, with no country
component and no city carrier and no postalAddress and only a global plus
code. Its postal absences are observed rather than mask backed, because
the search mask never requested those fields.

[Recorded] The Welsh places in recorded_A12_long_village_name.json carry
a formatted address and no components and no postalAddress, because their
set mask requested neither carrier. The fixture proves the typed absence
shape and a 46 character formatted address and nothing about Welsh
component geometry.

[Synthesized] A component can in principle arrive with empty text, and a
place can arrive with an empty component list beside a formatted address.
No recorded instance of an empty text component or an empty component
list exists anywhere in the corpus. Both shapes are authored under
synthesized_A11_component_present_but_empty.json and pin survival only.

```python
from placekit import address, types

# Authored shapes, not recordings. The helpers return their stated
# absence outcomes on both places and raise nothing.
route = address.find_component(place.address_components, types.TYPE_ROUTE)
route_text = address.component_long_text(place.address_components, types.TYPE_ROUTE)
city = address.resolve_city(place)
```

[Stated rule] The habit that survives this cluster is that absence is an
honest answer, and no helper promotes a place name or a formatted string
into a structured slot to fill a gap.

## 5. Reading by country

[Stated rule] A stated answer exists only where the corpus carries one.
Japan and the United Arab Emirates hold stated precedences and the United
Kingdom holds a stated two value answer, each resting on at least 20
distinct recorded places or on a details grade record pinning a carrier
disagreement directly. Every other reading runs under the generic
fallback chain and is capped at the heuristic grade.

### Japan

[Stated rule] The locality component carries the city at primary grade
and sublocality level 2 carries the district, and levels 3 and 4 carry
block fragments and never the city, and the postalAddress is excluded
from city and district evidence because it names neither on any
observation. The Japan precedence rests on one Asakusa query in Tokyo and
its places sit inside one special ward set with 40 observations over 22
distinct places in two request language sets over that same query and the
district row claims recorded special ward geometry and no wider Japanese
geometry.

[Recorded] The postal code agrees across both carriers on 40 of 40
observations in the seven digit hyphenated form. Premise level addressing
is the normal shape, and no route and no street number and no neighborhood
and no administrative area level 2 appears in any Japanese observation.

[Stated rule] The Japan precedence rests on one Asakusa query in Tokyo and
its places sit inside one special ward set with 40 observations over 22
distinct places in two request language sets over that same query and the
district row claims recorded special ward geometry and no wider Japanese
geometry.

### United Arab Emirates

[Stated rule] The locality component carries the city at primary grade
and the postalAddress locality is its only stated fallback, matching the
component value on every observation. Sublocality level 1 carries the
district, and neighborhood never carries the city or the district, and
the postal sublocality never stands in for level 1 because it copies the
neighborhood value instead. The Emirates precedence rests on one Downtown
Dubai search set in Arabic with 20 distinct places and it claims that
sampled locality and no wider Emirates geometry.

[Recorded] The postal administrative area drops out on 7 of 20 places in
the Dubai cassette set while the level 1 component stays present on 20 of
20, as the second place in recorded_A7_rtl_script_address.json shows.
Presence in one carrier set licenses no inference about the other.

[Stated rule] The Emirates precedence rests on one Downtown Dubai search
set in Arabic with 20 distinct places and it claims that sampled locality
and no wider Emirates geometry.

### United Kingdom

[Stated rule] The locality component carries the civil place and the
postal_town component carries the mailing town, and on the recorded set
both are always present and always different, so the honest reading
returns both values with the rivalry visible and no precedence between
them. The British answer rests on one village set at Bourton-on-the-Water
with 20 distinct places in one search set and it claims that sampled
village geometry and no wider British geometry.

[Stated rule] No postalAddress evidence exists for this country because
the only British set never requested one, so that carrier set is
unobserved rather than absent and no British cross reading row is stated.
A postal locality on a British place never enters British city resolution
and stays readable only as a cross reading value.

[Stated rule] The British answer rests on one village set at
Bourton-on-the-Water with 20 distinct places in one search set and it
claims that sampled village geometry and no wider British geometry.

### United States

[Heuristic] Three recorded places show three different city geometries
and together they forbid any single carrier rule. One holds its city only
in sublocality level 1 and in the postal locality, and one holds a plain
locality agreeing with its postal set while its neighborhood names a
different city, and one holds a locality with a single route and no
postalAddress and no postal code. The generic chain reaches each recorded
answer at heuristic grade and that reach is not a stated precedence. The
United States reading rests on 3 details places across 2 states with 3
different geometries and no American search set with components exists
and every American claim in the guide must carry this thin warning in the
same paragraph.

```python
from placekit import address

city = address.resolve_city(place)
flags = address.address_flags(place)
```

[Recorded] On the mall store place in recorded_P15_richest_mall_store
.json, one item with recorded_P12_contained_place.json, the city reads
Santa Clara from locality at heuristic grade while the neighborhood reads
Central San Jose. On the bridge place in recorded_A1_no_street_number
.json the city reads New York at heuristic grade with postal status
absent, and its route with no street number leaves the no street level
flag false even though the street number flag is also false. The United
States reading rests on 3 details places across 2 states with 3 different
geometries and no American search set with components exists and every
American claim in the guide must carry this thin warning in the same
paragraph.

[Heuristic] The United States reading rests on 3 details places across 2
states with 3 different geometries and no American search set with
components exists and every American claim in the guide must carry this
thin warning in the same paragraph.

### Vietnam

[Heuristic] On the one recorded place the component locality yields the
city at heuristic grade while the postal locality holds a ward name, and
the postal administrative spelling changes across request languages while
the component text stays stable. No wider Vietnamese pattern may be
stated, because every apparent pattern could be a property of this one
hotel. The Vietnam reading rests on 1 distinct place seen twice in two
details calls under English and German requests and it must be presented
as single place status wherever it appears.

```python
from placekit import address

city = address.resolve_city(place)
ward = address.postal_locality(place.postal_address)
```

[Recorded] On the Saigon place in recorded_P15_details_depth_saigon.json,
one item with recorded_H10_seasonal_offset_sample.json, the city resolves
from the component locality and never equals Tan Son Hoa, while the
postal locality returns Tan Son Hoa as a cross reading value. The German
reading in recorded_H11_description_order_vs_period_anchor.json is a
genuine second reading, cited as one where the spelling point matters.
The Vietnam reading rests on 1 distinct place seen twice in two details
calls under English and German requests and it must be presented as
single place status wherever it appears.

[Heuristic] The Vietnam reading rests on 1 distinct place seen twice in
two details calls under English and German requests and it must be
presented as single place status wherever it appears.

### Israel

[Heuristic] On the one recorded place the component locality yields the
city at heuristic grade and the place type is itself locality, so the
place is the city. The postal set is absent on both calls although the
details mask requested it, so that absence is mask backed. The region
pair teaches the identity finding in the catalogue and nothing about
adjudication. The Israel reading rests on 1 distinct place seen twice
under two region settings and it must be presented as single place status
wherever it appears.

### The Everest place

[Recorded] A place can carry structured address fields and still have no
country and no city to resolve, and the honest output is absence from
every extractor. The no country reading rests on 1 place from 1 search
set over Mount Everest, in recorded_P1_no_address_natural_feature.json,
one item with recorded_V5_plus_code_global_only.json.

### Countries the fixtures touch without address evidence

[Recorded] The remaining recorded fixtures carry formatted text only,
because their masks never requested address components. The Berlin sets
carry German places with no component geometry, and the Kathmandu and
Kiritimati sets carry offset evidence and no components, and Nepal and
Kiribati and Fiji appear only as formatted text. The Australian address
in the legacy hand built fixture place_details.json is authored decode
coverage and never live evidence. For every country named here the corpus
holds no recorded components for it, and no reading is taught for any of
them.

## 6. The decision rules a consumer must understand

### The grades

[Stated rule] Every city and district reading carries one of five
confidence grades in the open, and the grades mean the following.

| Grade | Meaning |
| --- | --- |
| [Stated rule] primary | The value came from the primary row of a stated table for a country with a stated precedence. |
| [Stated rule] fallback | The value came from a later row of a stated table or from a stated cross reading rescue. |
| [Stated rule] heuristic | The value came from the generic fallback chain, and no result from that chain may rise above this grade. |
| [Stated rule] none | No carrier yielded a value, and the value and carrier are both None. |
| [Stated rule] contested | Contested reports a live rivalry rather than a confidence level and a consumer must not sort a contested result as weaker than a fallback result. |

[Stated rule] A primary grade means the value came from the stated table
for the sampled region of its country and it does not mean a surveyed
national rule. Contested stands outside the strength ordering of primary
and then fallback and then heuristic and then none, and where the
contested condition holds on a British place it replaces the grade that
table would otherwise assign to the headline.

[Cannot promise] A result from this module is a reading of one response
and its confidence grade is part of that reading.

### Carriers and routing

[Stated rule] A city result names exactly one carrier or None when the
value is None. The competing fields carry a value only on a contested
result, where the headline carries the rival value and its carrier, and
every other result leaves both fields as None. The country code field on
a result carries the country reading for the same place, and it is None
on the Everest shape. The place ID remains the only join key across
scripts.

| Carrier rule | Statement |
| --- | --- |
| [Stated rule] Never a city carrier | The postal sublocality and the postal administrative area and the bare sublocality type never appear as the carrier of a shipped city result. |
| [Stated rule] Country sets | PRECEDENCE_COUNTRIES holding JP and AE only and CONTESTED_COUNTRIES holding GB alone, and every other country follows the generic chain. |
| [Stated rule] Routing case | The country code that routes a place is matched without regard to letter case, while returned codes stay the value as sent. |

[Stated rule] The British cells run as follows, and the United Kingdom
never follows the generic chain.

| British cell | Result |
| --- | --- |
| [Stated rule] Both carriers, different values | Contested, two resolutions, the civil place as the headline. |
| [Stated rule] Both carriers, equal values | One value at primary with no rivalry. |
| [Stated rule] Locality alone | Primary. |
| [Stated rule] Postal town alone | Fallback, because the chain fell past the primary row to the stated rival row. |
| [Stated rule] Neither carrier | The none grade result. |
| [Stated rule] Empty components beside a postal locality | The none grade result, because no British cross reading row exists. |

### Scanning forms and the generic chain

[Stated rule] The text forms return the first matching component whose
requested text is nonempty and keep scanning past empty text, so a text
form never returns an empty string. The component forms return the first
match in list order even when it carries empty text, so a caller can see
that it exists. City and district resolution read every component step
through the scanning long text form, so an empty text locality never
shadows a later locality with real text.

[Heuristic] The generic chain runs locality and then postal_town and then
sublocality level 1 and then sublocality level 2 and then the
postalAddress locality, stopping at the first carrier with a nonempty
value. The heuristic grade does not drop between steps and the carrier
field carries the within chain position. The bare sublocality type and
neighborhood and administrative area levels and sublocality levels 3 and
4 and 5 and the postal sublocality and the postal administrative area are
never chain steps. The Vietnam reading rests on 1 distinct place seen
twice in two details calls under English and German requests and it must
be presented as single place status wherever it appears.

[Stated rule] District resolution names a district carrier for two
countries only, sublocality level 2 for Japan under the recorded special
ward geometry and sublocality level 1 for the Emirates, and every other
country returns a none grade district result. The Emirates postal
sublocality is never a district source under any circumstance.

```python
from placekit import address

district = address.resolve_district(place)
```

### Country, administrative area and postal extraction

[Stated rule] The country read takes the short text of the first country
component with a nonempty short text and falls back to the postal region
code through postal_region_code when no such component exists.
postal_region_code is the surviving name of that read, and the deleted
name country_code_from_postal_address ships nowhere. The administrative
area read returns the long text of the first level 1 component and never
falls back to the postal administrative area.

```python
from placekit import address

code = address.country_code(place)
area = address.administrative_area(place)
postal_area = address.postal_administrative_area(place.postal_address)
```

[Stated rule] The postal code read runs in a fixed order. Both carriers
holding equal values gives that value with the both postal carriers
marker and present status. One carrier holding a value gives that value
with its carrier named. Neither gives None with absent status. Both
holding different values gives the component value as the headline with
the postal value in the competing fields, because the component list is
the fuller record and the postalAddress is a derived summary of it. No
helper fabricates a code from formatted text.

```python
from placekit import address

locality = address.postal_locality(place.postal_address)
sublocality = address.postal_sublocality(place.postal_address)
result = address.postal_code(place)
print(result.status)
```

[Recorded] That block runs on the Japanese place in
recorded_A6_japanese_block_addressing.json, one item with
recorded_A5_sublocality_chains.json, where the status prints present with
both carriers agreeing, and on the Dubai place in
recorded_A9_country_without_postal_codes.json, where the status prints
absent and the postal sublocality repeats the downtown value while
sublocality level 1 names a different district.

### Presence flags and plus codes

[Stated rule] Presence flags trust type labels by design and no flag
inspects text for plausibility. The street number flag is true when a
street number component exists whatever its text holds, and the premise
and subpremise and route flags follow the same rule. The premise level
flag is true when a premise exists and no street number and no route
exists. The multiple routes flag counts only routes with nonempty long
text. The no street level flag is true only when none of street number
and route and premise and subpremise exists.

[Stated rule] Splitting a compound plus code takes the token before the
first space as the code part and the trimmed trailing text as the
locality text. A global code alone returns None, meaning no compound form
was present rather than no plus code at all. An input holding a code
token and a space and nothing after it also returns None, so a locality
text is never an empty string. The locality text of a compound plus code
is reference text as sent and no helper feeds it into city resolution.

### Degenerate input

[Stated rule] Type keyed lookup skips typeless components, and
untyped_components returns them in list order, and no helper guesses a
type for them. Duplicate components of the winning type resolve by list
order, the first match winning every single value helper and the plural
form returning every duplicate. Language tags change no rule.

[Stated rule] A place with no components gives every list helper its
empty or None outcome, and an empty component list behaves exactly like a
missing component key at the typed layer, and helpers never parse the
formatted address beside it. A missing postalAddress gives None from
every postal field reader, with identical behaviour whether the absence
is mask backed or unobserved. A place with neither carrier set returns
absence from country and city and postal extraction, and only the plus
code split may still yield a value.

[Stated rule] Helpers over wire shaped input do not raise. Caller
argument errors sit outside wire shaped input and raise ConfigError from
placekit.exceptions. A bare string or bytes value where a component
sequence belongs raises ConfigError, and a nonstring type name raises
ConfigError, and an empty type name raises ConfigError, because returning
None there would dress a caller bug as a recorded absence.

```python
from placekit import address, types

# Each call below raises ConfigError from placekit.exceptions.
address.find_component("route,locality", types.TYPE_ROUTE)
address.find_component([], 5)
address.find_component([], "")
```

### Held surfaces and rules no fixture can pin yet

[Cannot promise] The module ships no prefix or suffix assembly and no
sorting code reader and no formatted text parser and no display
composition and no envelope rendering and no district helper beyond the
two stated district carriers and no region helper beyond administrative
area at level 1 and no function that takes raw dicts. No helper reads raw
anywhere. Those absences are stated here and in the module docstring so
no consumer reads any of them as an oversight.

[Stated rule] Several stated rules cannot be pinned from recorded
evidence yet and are taught without an invented proof example. A
duplicate premise pin needs an excerpt isolating one Japanese place with
two premise components. A British postal cross reading pin cannot be
written because no British postalAddress was ever requested. Prefix and
suffix and sorting code pins cannot be written because no such component
or key exists in the corpus. A United States primary grade pin stays
unwritten while the United States table stays held. Change between
requests and colloquial area and intersection pins cannot be written
because those cases hold no recorded components. A postal disagreement
pin cannot be written because no fixture carries two postal carriers
holding different values. A country code fallback pin cannot be written
because no excerpt isolates a place whose components hold no country
component while its postalAddress holds a region code.

## 7. Worked recipes

### Recipe 1. Read a city with its grade and act on the grade

[Recipe] Call resolve_city and branch on the confidence grade before
using the value. A primary value may be presented as the stated reading
for its sampled region, a heuristic value must be labelled as a generic
chain reading, and a none value must render as no recorded city rather
than an empty string. The Brooklyn place below is an American claim, so
its warning rides here. The United States reading rests on 3 details
places across 2 states with 3 different geometries and no American search
set with components exists and every American claim in the guide must
carry this thin warning in the same paragraph.

```python
from placekit import address

# The Tokyo place from the English fixture, the Brooklyn place from
# the A2 fixture, and the Everest place, in fixture order.
for place in (tokyo_place, brooklyn_place, everest_place):
    city = address.resolve_city(place)
    if city.value is None:
        print("no recorded city", city.confidence)
    else:
        print(city.value, city.carrier, city.confidence)
```

```text
Taito City locality primary
Brooklyn sublocality_level_1 heuristic
no recorded city none
```

[Cannot promise] No resolved city in this guide is a fact of the same
kind as a place ID.

### Recipe 2. Handle the British two values

[Stated rule] For a British place call city_resolutions and present both
returned values with their carriers whenever the tuple holds two
elements, and never collapse the pair into one silent value. The British
headline in resolve_city is an interim rule and not a finding of this
guide. A single value caller using resolve_city receives the civil place
as that interim headline with the mailing town visible in the competing
fields.

```python
from placekit import address

resolutions = address.city_resolutions(place)
for resolution in resolutions:
    print(resolution.value, resolution.carrier, resolution.confidence)
headline = address.resolve_city(place)
```

```text
Bourton-on-the-Water locality contested
Cheltenham postal_town contested
```

[Recipe] The proof suite pins one place under two case names for this
recipe, from recorded_A4_locality_postal_town_disagree.json, filed also
as recorded_A3_postal_town_carries_city.json and counted as one item. The
20 of 20 disagreement prevalence stays a cassette claim outside the test.

### Recipe 3. Assemble a line by hand without inventing fields

[Recipe] placekit.address ships no formatter and no display composer and
no envelope renderer, so this recipe is caller owned guidance and not
library behaviour. A consumer assembling a line by hand reads the typed
components in list order and takes each value as sent, without inventing
a field the place does not carry and without parsing the formatted
address to fill a gap. Display selection between the formatted address
and the short formatted address stays caller judgement, and envelope
formatting is a pointer at libaddressinput metadata rather than a
reimplementation here.

```python
from placekit import address

# Caller owned guidance, not library behaviour. The join reads every
# component in list order, so it keeps the untyped texts that a type
# keyed read walks past, and the lost list names those texts.
components = place.address_components
line = ", ".join(
    component.long_text for component in components if component.long_text
)
lost = [
    component.long_text
    for component in address.untyped_components(components)
    if component.long_text
]
```

[Recipe] On the second Dubai place in recorded_A7_rtl_script_address
.json the joined line reads Level 3, Armani Hotel Dubai, برج خليفة, بوليفارد الشيخ محمد بن راشد, وسط مدينة دبي, برج خليفة, دبي, دبي, الإمارات العربية المتحدة
as an inspection string only. Where no components exist, as on the Welsh
places in recorded_A12_long_village_name.json, only the formatted address
remains and the caller falls back to it as unparsed text.

[Cannot promise] The assembled line carries no envelope correctness
claim and no deliverability claim for any country, and no field order
correctness claim beyond the recorded sets.

### Recipe 4. Compare two readings of one place

[Recipe] Hold two readings of one place id side by side and compare the
typed outputs helper by helper rather than comparing raw text. For the
language pair expect the texts and the formatted order to differ while
the type sequence holds. For the region pair expect identity on this
recorded pair without generalising it, and the pair is an Israeli claim,
so its marking rides here. The Israel reading rests on 1 distinct place
seen twice under two region settings and it must be presented as single
place status wherever it appears.

```python
from placekit import address

# The Tokyo pair, stored in Japanese and kept for display in English.
same_place = stored.id == display.id
same_skeleton = [tuple(c.types) for c in stored.address_components] == [
    tuple(c.types) for c in display.address_components
]
stored_city = address.resolve_city(stored)
display_city = address.resolve_city(display)
```

```python
from placekit import address

# The Jerusalem pair, compared over the localised helper set.
place_level = (address.country_code, address.resolve_city,
               address.resolve_district, address.postal_code,
               address.address_flags)
postal_level = (address.postal_locality, address.postal_sublocality,
                address.postal_administrative_area,
                address.postal_region_code)
same = all(helper(first) == helper(second) for helper in place_level)
same = same and all(
    helper(first.postal_address) == helper(second.postal_address)
    for helper in postal_level
)
same = same and address.split_plus_code(first.plus_code) == address.split_plus_code(second.plus_code)
```

[Recipe] The right to left companion shape in
recorded_A7_rtl_script_address.json, where Latin fragments interleave
with Arabic texts inside one response, is taught in prose here and gets
no second code block. Readings stay separate values joined only by the
place ID, under recipe 6.

### Recipe 5. Handle a place with no street level and a place with no components

[Recipe] Branch on address_flags before rendering or routing. A place
with no street level components reads through its premise or political
carriers, and the premise level flag names the Japanese block shape. A
place with no components at all returns absence from every extractor, and
the consumer falls back to the formatted address as unparsed text or to
the place ID and nothing else.

```python
from placekit import address

flags = address.address_flags(premise_place)
city = address.resolve_city(empty_place)
code = address.country_code(empty_place)
result = address.postal_code(empty_place)
```

[Recipe] The flags run on the Japanese place from
recorded_A6_japanese_block_addressing.json, one item with
recorded_A5_sublocality_chains.json, and the absence outcomes run on the
Welsh place from recorded_A12_long_village_name.json. The bridge place in
recorded_A1_no_street_number.json teaches the neighbouring caution,
because its route with no street number leaves its no street level flag
false even though its street number flag is also false.

### Recipe 6. Deduplicate on the place ID and nothing else

[Recipe] Join readings of a place on the place ID and on nothing else.
Component text changes across languages for one place, and result set
membership itself shifts across request languages, and text equality does
not imply component identity on one place, so a fingerprint built from
component text will split one place into several keys and can merge
distinct places that share a string.

```python
from placekit import address

same_place = japanese_place.id == english_place.id
japanese_texts = tuple(c.long_text for c in japanese_place.address_components)
english_texts = tuple(c.long_text for c in english_place.address_components)
texts_agree = japanese_texts == english_texts
```

[Heuristic] A consumer who builds a normalised address fingerprint
anyway must label it as a heuristic grouping aid at best, with its
collision and drift behaviour stated wherever it is taught. The
fingerprint is a second class key and never becomes identity.

[Cannot promise] The place ID remains the only join key across scripts.
No reading in this guide equates names across scripts, and no local rule
may present a text match as the same place.

### Recipe 7. Keep a second language reading for display

[Recipe] Store the reading taken under the local script request as the
stored form and request a second language reading for display where a
display audience needs it, and never merge names across scripts into one
field. The Tokyo pair in recipe 4 shows the working shape, with the
Japanese response carrying local script texts and full width digits and
the English response carrying translated and transliterated texts for the
same components under the same place ID, and that recipe holds the code
so this one adds no second block.

[Heuristic] Which reading serves a given display audience is caller
judgement rather than rule. The language tag on a component is data about
that component and not a merge key, and the stored and display readings
stay separate values joined only by the place ID under recipe 6.

### Recipe 8. Read a postal code with its status and split a compound plus code

[Recipe] Read postal_code and branch on its status before branching on
its value, so a country property absence renders differently from an
unrequested absence wherever raw can tell them apart. Split a compound
plus code for display of its code part while keeping its locality text
labelled as reference text. The Saigon split below is a Vietnamese claim,
so its marking rides here. The Vietnam reading rests on 1 distinct place
seen twice in two details calls under English and German requests and it
must be presented as single place status wherever it appears.

```python
from placekit import address

result = address.postal_code(place)
for source in (brooklyn_place, mall_place, saigon_place):
    parts = address.split_plus_code(source.plus_code)
    code_part = parts.code_part
    locality_text = parts.locality_text
global_parts = address.split_plus_code(everest_place)
```

[Cannot promise] The locality text of a compound plus code is reference
text as sent and no helper feeds it into city resolution. A global code
alone returns None from the split, meaning no compound form was present,
and the consumer reads the global code from the model itself in that case.

## 8. What cannot be promised

[Cannot promise] This section consolidates the honest boundaries as a
checklist a reader can scan before shipping handling code. It is an index
into boundaries already stated beside their claims in the earlier
sections, and no boundary sentence has been moved out of its home section
to land here. Each entry names the section where the boundary travels.

- [Cannot promise] Deliverability belongs to the Address Validation API and postal authority data, and no assembled line gains a deliverability claim, from section 1.
- [Cannot promise] Stability is not promised. A result from this module is a reading of one response and its confidence grade is part of that reading, and that sentence is homed in the grades group of section 6.
- [Cannot promise] The resolved city itself is bounded. No resolved city in this guide is a fact of the same kind as a place ID, and that sentence is homed in recipe 1 of section 7.
- [Cannot promise] Completeness is not promised, because the component array omits political entities and containment questions need reverse geocoding, which this library does not offer, from sections 1 and 6.
- [Cannot promise] Freshness is not promised, because freshness is a data propagation question the corpus can at most detect drift for and cannot prevent, from section 1.
- [Cannot promise] Cross script identity beyond the place ID is not promised, and no local rule equates names across scripts safely, from section 6 and recipe 6.
- [Cannot promise] Disputed territory adjudication is not promised, because names and borders follow the requesting region and its law, and the Jerusalem pair returning identical content is the whole recorded statement, from section 5.
- [Cannot promise] Stated precedences beyond the sampled localities are not promised, and no table extends to another country or another region by analogy, from section 5.
- [Cannot promise] Envelope rendering and display composition as library behaviour are not promised, because both are held surfaces and the guide teaches the libaddressinput pointer inside recipe 3 instead.
- [Cannot promise] Unrecorded countries carry no corpus claim here. Spain and Switzerland and India are named in this entry only, and the Round 11 research file is the source a reader follows for anything further about them, and France and Germany and Canada and China and Brazil sit under the same bar.
- [Cannot promise] Prefix and suffix assembly is not promised, because zero prefix or suffix components occur in the corpus and the module ships no assembly helper.
- [Cannot promise] A typed sorting code read is not promised, because no sorting code key occurs in any recorded postal address and the shipped PostalAddress model carries no sorting code field.
- [Cannot promise] Colloquial areas and intersections carry no recorded component in any body, and route multiplicity is not taught as an intersection pattern anywhere in this guide.
- [Cannot promise] Change between requests holds no recorded example, because every same day repeat pair returned identical component type sets, and the warning itself is taught as a Google statement in section 1.

## 9. A short consumer checklist

[Recipe] Every line below restates a rule from an earlier section and
names that section, so the checklist is a memory aid and never a second
source of truth.

- [Stated rule] Branch on the grade before using a city value, from section 6.
- [Stated rule] Present both British values where city_resolutions returns two, from section 7.
- [Stated rule] Branch on postal status before using a postal value, from section 6.
- [Stated rule] Keep language readings apart under one place ID, from section 7.
- [Recipe] Fall back to formatted text as unparsed text when no components exist, from section 7.
- [Cannot promise] Check the cannot promise list before promising a consumer anything downstream, from section 8.
