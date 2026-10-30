"""Supported language codes for the Places API (New).

Snapshot of the supported languages table in the Google Maps
Platform FAQ at https://developers.google.com/maps/faq as fetched
on 2026-10-30. The Places reference pages name that FAQ table as the
current list of supported languages for the language parameter.

The source table warns that the list may not be exhaustive and is
subject to change. The language parameter accepts any BCP 47
string whether or not a constant exists for it. The set in this
module describes what this version knows and must not be used to
reject codes, because unlisted codes remain valid input to the
client.
"""

from __future__ import annotations

AFRIKAANS = "af"
ALBANIAN = "sq"
AMHARIC = "am"
ARABIC = "ar"
ARMENIAN = "hy"
AZERBAIJANI = "az"
BASQUE = "eu"
BELARUSIAN = "be"
BENGALI = "bn"
BOSNIAN = "bs"
BULGARIAN = "bg"
BURMESE = "my"
CATALAN = "ca"
CHINESE = "zh"
CHINESE_SIMPLIFIED = "zh-CN"
CHINESE_HONG_KONG = "zh-HK"
CHINESE_TRADITIONAL = "zh-TW"
CROATIAN = "hr"
CZECH = "cs"
DANISH = "da"
DUTCH = "nl"
ENGLISH = "en"
ENGLISH_AUSTRALIAN = "en-AU"
ENGLISH_GREAT_BRITAIN = "en-GB"
ESTONIAN = "et"
FARSI = "fa"
FINNISH = "fi"
FILIPINO = "fil"
FRENCH = "fr"
FRENCH_CANADA = "fr-CA"
GALICIAN = "gl"
GEORGIAN = "ka"
GERMAN = "de"
GREEK = "el"
GUJARATI = "gu"
# The source table lists iw for Hebrew and the table is the
# authority, even where modern usage prefers a different code.
HEBREW = "iw"
HINDI = "hi"
HUNGARIAN = "hu"
ICELANDIC = "is"
INDONESIAN = "id"
ITALIAN = "it"
JAPANESE = "ja"
KANNADA = "kn"
KAZAKH = "kk"
KHMER = "km"
KOREAN = "ko"
KYRGYZ = "ky"
LAO = "lo"
LATVIAN = "lv"
LITHUANIAN = "lt"
MACEDONIAN = "mk"
MALAY = "ms"
MALAYALAM = "ml"
MARATHI = "mr"
MONGOLIAN = "mn"
NEPALI = "ne"
NORWEGIAN = "no"
POLISH = "pl"
PORTUGUESE = "pt"
PORTUGUESE_BRAZIL = "pt-BR"
PORTUGUESE_PORTUGAL = "pt-PT"
PUNJABI = "pa"
ROMANIAN = "ro"
RUSSIAN = "ru"
SERBIAN = "sr"
# The mixed case is part of the wire value.
SERBIAN_LATIN = "sr-Latn"
SINHALESE = "si"
SLOVAK = "sk"
SLOVENIAN = "sl"
SPANISH = "es"
SPANISH_LATIN_AMERICA = "es-419"
SWAHILI = "sw"
SWEDISH = "sv"
TAMIL = "ta"
TELUGU = "te"
THAI = "th"
TURKISH = "tr"
UKRAINIAN = "uk"
URDU = "ur"
UZBEK = "uz"
VIETNAMESE = "vi"
ZULU = "zu"

ALL_CODES: frozenset[str] = frozenset({
    "af",
    "sq",
    "am",
    "ar",
    "hy",
    "az",
    "eu",
    "be",
    "bn",
    "bs",
    "bg",
    "my",
    "ca",
    "zh",
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "en-AU",
    "en-GB",
    "et",
    "fa",
    "fi",
    "fil",
    "fr",
    "fr-CA",
    "gl",
    "ka",
    "de",
    "el",
    "gu",
    "iw",
    "hi",
    "hu",
    "is",
    "id",
    "it",
    "ja",
    "kn",
    "kk",
    "km",
    "ko",
    "ky",
    "lo",
    "lv",
    "lt",
    "mk",
    "ms",
    "ml",
    "mr",
    "mn",
    "ne",
    "no",
    "pl",
    "pt",
    "pt-BR",
    "pt-PT",
    "pa",
    "ro",
    "ru",
    "sr",
    "sr-Latn",
    "si",
    "sk",
    "sl",
    "es",
    "es-419",
    "sw",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "uz",
    "vi",
    "zu",
})

__all__ = [
    "AFRIKAANS",
    "ALBANIAN",
    "AMHARIC",
    "ARABIC",
    "ARMENIAN",
    "AZERBAIJANI",
    "BASQUE",
    "BELARUSIAN",
    "BENGALI",
    "BOSNIAN",
    "BULGARIAN",
    "BURMESE",
    "CATALAN",
    "CHINESE",
    "CHINESE_SIMPLIFIED",
    "CHINESE_HONG_KONG",
    "CHINESE_TRADITIONAL",
    "CROATIAN",
    "CZECH",
    "DANISH",
    "DUTCH",
    "ENGLISH",
    "ENGLISH_AUSTRALIAN",
    "ENGLISH_GREAT_BRITAIN",
    "ESTONIAN",
    "FARSI",
    "FINNISH",
    "FILIPINO",
    "FRENCH",
    "FRENCH_CANADA",
    "GALICIAN",
    "GEORGIAN",
    "GERMAN",
    "GREEK",
    "GUJARATI",
    "HEBREW",
    "HINDI",
    "HUNGARIAN",
    "ICELANDIC",
    "INDONESIAN",
    "ITALIAN",
    "JAPANESE",
    "KANNADA",
    "KAZAKH",
    "KHMER",
    "KOREAN",
    "KYRGYZ",
    "LAO",
    "LATVIAN",
    "LITHUANIAN",
    "MACEDONIAN",
    "MALAY",
    "MALAYALAM",
    "MARATHI",
    "MONGOLIAN",
    "NEPALI",
    "NORWEGIAN",
    "POLISH",
    "PORTUGUESE",
    "PORTUGUESE_BRAZIL",
    "PORTUGUESE_PORTUGAL",
    "PUNJABI",
    "ROMANIAN",
    "RUSSIAN",
    "SERBIAN",
    "SERBIAN_LATIN",
    "SINHALESE",
    "SLOVAK",
    "SLOVENIAN",
    "SPANISH",
    "SPANISH_LATIN_AMERICA",
    "SWAHILI",
    "SWEDISH",
    "TAMIL",
    "TELUGU",
    "THAI",
    "TURKISH",
    "UKRAINIAN",
    "URDU",
    "UZBEK",
    "VIETNAMESE",
    "ZULU",
    "ALL_CODES",
]
