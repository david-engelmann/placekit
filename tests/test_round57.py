"""Pins for the Round 57 README filter teachings, extended in
Round 67 and Round 77.

The claims census found the endpoints paragraph promising the
filters their endpoints offer while leaving real keywords
unnamed, and the cold read gauntlet found the price_levels value
shape stated nowhere in the document. These pins hold both
repairs. The keyword sets are derived from the client signatures
with inspect, never pasted into this file, so a keyword added to
a call and left untaught fails here. The price level pin reads
the values the README itself spells, checks them against the
five value vocabulary held in this file as an oracle, and
drives them through a call against the offline stub, proving
the client takes them.

The spelling guard covers the caller-spelled surface the README
teaches for the client calls and the field mask helper, and
nothing wider. For the calls, it covers the keyword-only
parameters of all five client calls, the four read calls and
place_photo alike, on the settlement Round 67 revises, where
Round 57 had held the place_photo keywords outside the promise.
For the helper, it covers the public members of FieldMask
other than its stored paths field, which the README does not
teach because it teaches construction and the header form
instead, each covered member spelled in the README in its
FieldMask.<member> form. Model members and the rest of the
public surface stand outside this guard, and no claim here
certifies them.

Round 77: the guard reads the text a reader sees, through
_reader_text below, because a spelling inside a span the
rendered page never shows teaches nobody anything. The raw
text let an HTML comment, a hidden element, a script or style
element, a tag attribute, a link destination and a link
definition each stand as a teaching.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from placekit import AsyncClient, Client, FieldMask

REPO_ROOT = Path(__file__).resolve().parents[1]

READ_CALLS = ("text_search", "nearby_search", "place_details", "autocomplete")
ALL_CALLS = READ_CALLS + ("place_photo",)

#: The public members of FieldMask the README must spell in
#: FieldMask.<member> form, derived from the class itself so a
#: member added and left untaught fails here. The dataclass
#: field ``paths`` stands outside the taught set, because the
#: README teaches construction and the header form rather than
#: the stored tuple.
FIELDMASK_MEMBERS = tuple(
    name
    for name, member in vars(FieldMask).items()
    if not name.startswith("_") and name != "paths"
)

#: The full price level vocabulary the API defines, held in
#: this file as the oracle for the price level pin. The shipped
#: Python surface states no price level constants family, in
#: the fields module or the types module or anywhere else, so
#: the set cannot be derived by import, and the README under
#: test cannot be its own oracle. The vocabulary is closed at
#: these five values under the Round 7 settlement, and the
#: constants census pattern of holding the expected truth in
#: the test is the house shape for a closed set. The sixth
#: enum name, PRICE_LEVEL_UNSPECIFIED, is the unset sentinel
#: for a place with no level rather than a value a filter can
#: select, so it stands outside the taught set.
PRICE_LEVEL_VALUES = (
    "PRICE_LEVEL_FREE",
    "PRICE_LEVEL_INEXPENSIVE",
    "PRICE_LEVEL_MODERATE",
    "PRICE_LEVEL_EXPENSIVE",
    "PRICE_LEVEL_VERY_EXPENSIVE",
)

_SPAN = re.compile(r"```.*?```|<!--.*?-->|<!--.*", re.DOTALL)
_DROPPED_ELEMENT = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE
)
_TAG = re.compile(r"<(/?)([A-Za-z][\w-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>")
_HIDES = re.compile(
    r"(?<![-\w])(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE
)
_LINK_OPEN = re.compile(r"(!?)\[")
_VOID = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)


def _is_hidden(attrs):
    # An element hides when it carries the hidden attribute as
    # its own token, or a style attribute, quoted or bare,
    # whose value carries one of the two hiding declarations.
    # Attribute and property names are case-insensitive, and a
    # data or aria attribute that merely contains the word
    # hides nothing. The token check reads the attribute text
    # with quoted values removed, so a class or title carrying
    # the word as its value is not mistaken for the attribute,
    # and the token must stand as an attribute name, preceded
    # by whitespace, so an unquoted value that happens to
    # equal the word is not mistaken for it either. The style
    # search anchors on the whitespace before the attribute
    # name, so style-shaped text inside another attribute's
    # quoted value cannot pose as it. The hiding check reads
    # the style value with CSS comments removed, because a
    # browser reads through them.
    bare = re.sub(r"\"[^\"]*\"|'[^']*'", "", attrs)
    if re.search(r"(?:^|\s)hidden(?![-\w])", bare, re.IGNORECASE):
        return True
    style = re.search(
        r"\sstyle\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
        attrs,
        re.IGNORECASE,
    )
    if not style:
        return False
    value = re.sub(r"/\*.*?\*/", "", style.group(1), flags=re.DOTALL)
    return bool(_HIDES.search(value))


def _strip_hidden(text):
    # Hidden elements go with their content. The scan walks
    # tag by tag because the close that pairs with a hidden
    # opening is found by counting openings and closings of
    # the same tag name, so a closed child of the same name
    # inside the element cannot end the span early. A hidden
    # opening with no pairing close runs to the end of the
    # text, which is where the element's content runs in a
    # browser too.
    out = []
    pos = 0
    while True:
        match = _TAG.search(text, pos)
        if match is None:
            out.append(text[pos:])
            return "".join(out)
        closing, name, attrs = match.groups()
        if closing or not _is_hidden(attrs):
            out.append(text[pos:match.end()])
            pos = match.end()
            continue
        out.append(text[pos:match.start()])
        if attrs.rstrip().endswith("/") or name.lower() in _VOID:
            # A self-closing tag and a void element carry no
            # content, so only the tag itself goes. A void
            # element has no closing tag by construction, and
            # scanning for one would eat the text behind it.
            pos = match.end()
            continue
        depth = 1
        scan = match.end()
        while depth:
            inner = _TAG.search(text, scan)
            if inner is None:
                scan = len(text)
                break
            scan = inner.end()
            if inner.group(2).lower() != name.lower():
                continue
            if inner.group(1):
                depth -= 1
            elif not inner.group(3).rstrip().endswith("/"):
                depth += 1
        pos = scan


def _balanced_close(text, opening, opener, closer):
    # The index just past the character that balances the one
    # at opening, counting nesting of the pair, or None when
    # the text ends first. A backslash escapes the character
    # behind it, which then counts as ordinary text, the way
    # the markup itself reads it.
    depth = 0
    scan = opening
    while scan < len(text):
        char = text[scan]
        if char == "\\":
            scan += 2
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return scan + 1
        scan += 1
    return None


def _destination_ok(inner):
    # The text between the parentheses of a link destination.
    # The destination itself carries no whitespace outside an
    # angle pair, and what follows it is at most a quoted
    # title. Anything else wearing the shape is prose in
    # brackets and parentheses, which renders as written.
    inner = inner.strip()
    if not inner:
        return True
    if inner.startswith("<"):
        angle = inner.find(">")
        if angle < 0:
            return False
        inner = inner[angle + 1:].strip()
        if not inner:
            return True
    parts = inner.split(None, 1)
    if len(parts) == 1:
        return True
    title = parts[1].strip()
    if len(title) < 2:
        return False
    if title[0] == title[-1] and title[0] in "\"'":
        return True
    return title.startswith("(") and title.endswith(")")


def _strip_links(text):
    # Link and image destinations go, balanced rather than to
    # a fixed depth. The scan walks bracket by bracket. The
    # visible text runs to the bracket that balances the
    # opening one, so text carrying its own brackets, an image
    # nested in a link among them, parses whole, and the
    # destination runs to the parenthesis that balances its
    # opening one, nested parentheses and escaped parentheses
    # alike read the way the markup reads them. An image drops
    # entirely, because its alt text is attribute text. A link
    # keeps its visible text, itself stripped by this same
    # scan, because the kept text can carry a nested image
    # whose alt text is no more rendered than a top level one.
    # A bracket with no balanced destination behind it is not
    # a link and stands as written.
    out = []
    pos = 0
    while True:
        match = _LINK_OPEN.search(text, pos)
        if match is None:
            out.append(text[pos:])
            return "".join(out)
        bracket = match.end() - 1
        text_end = _balanced_close(text, bracket, "[", "]")
        if text_end is None or text_end >= len(text) or text[text_end] != "(":
            out.append(text[pos:match.end()])
            pos = match.end()
            continue
        dest_end = _balanced_close(text, text_end, "(", ")")
        if dest_end is None or not _destination_ok(text[text_end + 1:dest_end - 1]):
            out.append(text[pos:match.end()])
            pos = match.end()
            continue
        out.append(text[pos:match.start()])
        if not match.group(1):
            out.append(_strip_links(text[bracket + 1:text_end - 1]))
        pos = dest_end


def _reader_text(readme):
    # The text a reader of the rendered README sees. Spans the
    # rendered page never shows are removed before the checks
    # read, so a spelling inside one cannot count as taught.
    # One pass first walks the fence and comment spans in the
    # order they stand, because the two nest inside each other
    # both ways. A comment marker inside a fenced example is
    # example text, and a fence marker inside a comment is
    # comment text, so whichever span opens first owns the
    # text it covers. Comments are blanked to spaces in that
    # pass, an unterminated opener blanking to the end of the
    # file, because the renderer swallows the remainder behind
    # it, and blanking keeps the text on either side of a
    # comment from joining across its seam.
    # The fences are stashed behind sentinels for the rest of
    # the extraction and restored at the end, because an
    # example renders as visible text, so comment-like or
    # tag-like text inside a fence is a real teaching and
    # nothing inside a fence is stripped. A sentinel comes
    # back only when its label is the stash's own and stands
    # exactly once in the text, so a sequence the document
    # carried, or one a removal joined across its seam, stays
    # literal. Script and style elements and hidden elements
    # then go with their content. Link definition lines never
    # render at all, an image drops whole because its alt
    # text is attribute text, and a link keeps only its
    # visible text, never its destination. Any remaining tag
    # drops while its inner text stays.
    fenced = []
    existing = [
        int(match.group(1)) for match in re.finditer(r"\x00(\d+)\x00", readme)
    ]
    base = max(existing) + 1 if existing else 0

    def stash(match):
        fenced.append(match.group(0))
        return f"\x00{base + len(fenced) - 1}\x00"

    parts = []
    pos = 0
    for match in _SPAN.finditer(readme):
        parts.append(readme[pos:match.start()])
        span = match.group(0)
        if span.startswith("```"):
            parts.append(stash(match))
        else:
            # A comment is blanked rather than removed, so
            # the text on either side of it can never join
            # across the seam into something it was not.
            parts.append(" " * len(span))
        pos = match.end()
    parts.append(readme[pos:])
    text = "".join(parts)
    text = _DROPPED_ELEMENT.sub("", text)
    text = _strip_hidden(text)
    text = re.sub(
        r"^\s{0,3}\[[^\]]*\]:\s*\S+.*(?:\n[ \t]+([\"']).*?\1[ \t]*\r?)?$",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = _strip_links(text)
    text = re.sub(r"<[^>]+>", "", text)

    issued = {base + index for index in range(len(fenced))}
    counts = {}
    for match in re.finditer(r"\x00(\d+)\x00", text):
        label = int(match.group(1))
        counts[label] = counts.get(label, 0) + 1

    def restore(match):
        # A NUL sequence the document already carried is not a
        # sentinel. The stash numbered its sentinels above
        # every index the input already held, a sequence
        # outside the stash range is left as the literal text
        # it is, and a sequence whose label stands more than
        # once in the text was joined across some removal's
        # seam into a copy, so it is left literal too. A
        # sentinel is restored only when its label is the
        # stash's own and stands exactly once, never an error
        # and never a copied fence.
        label = int(match.group(1))
        if label in issued and counts[label] == 1:
            return fenced[label - base]
        return match.group(0)

    return re.sub(r"\x00(\d+)\x00", restore, text)


@pytest.fixture()
def client(api_key, base_url) -> Client:
    return Client(api_key, base_url=base_url)


def _keyword_names(cls, method_name):
    parameters = inspect.signature(getattr(cls, method_name)).parameters
    return {
        name
        for name, parameter in parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    }


def _spelled(readme, name):
    # A keyword counts as taught when the README names it in
    # backticks or uses it as an argument in an example. A bare
    # prose word does not count, because words such as region
    # also live in passages that teach nothing about the keyword.
    if f"`{name}`" in readme:
        return True
    return re.search(rf"(?<![\w.]){re.escape(name)}=", readme) is not None


def test_sync_and_async_keyword_sets_match():
    # The README teaches one keyword surface per call, which is
    # honest only while the two clients carry the same surface.
    for method_name in ALL_CALLS:
        assert _keyword_names(Client, method_name) == _keyword_names(
            AsyncClient, method_name
        ), method_name


@pytest.mark.parametrize("method_name", ALL_CALLS)
def test_readme_spells_every_keyword_of_the_client_calls(method_name):
    readme = _reader_text((REPO_ROOT / "README.md").read_text())
    unspelled = sorted(
        name
        for name in _keyword_names(Client, method_name)
        if not _spelled(readme, name)
    )
    assert not unspelled, (
        f"{method_name} keywords the README never names: {unspelled}"
    )


def test_readme_spells_every_public_fieldmask_member():
    # The README writes the curated defaults in called form,
    # `FieldMask.text_search()` with the parentheses inside the
    # backticks, so the check accepts the bare and the called
    # spelling alike.
    readme = _reader_text((REPO_ROOT / "README.md").read_text())
    unspelled = sorted(
        name
        for name in FIELDMASK_MEMBERS
        if f"`FieldMask.{name}`" not in readme
        and f"`FieldMask.{name}()`" not in readme
    )
    assert not unspelled, (
        f"FieldMask members the README never names: {unspelled}"
    )


def test_readme_price_level_values_reach_the_wire(client, stub_server):
    # The values are read out of the README itself, and the
    # recorded request body proves the client accepts each taught
    # value and sends it under the wire name. The taught set is
    # first checked against the oracle, because the client passes
    # price values through unvalidated by design, so a corrupted
    # teaching would otherwise reach the wire under a green suite.
    readme = _reader_text((REPO_ROOT / "README.md").read_text())
    taught = sorted(set(re.findall(r"PRICE_LEVEL_[A-Z_]+", readme)))
    assert taught, "the README spells no price level values"
    assert taught == sorted(PRICE_LEVEL_VALUES), (
        f"the README teaches {taught} and the price level "
        f"vocabulary is {sorted(PRICE_LEVEL_VALUES)}"
    )
    client.text_search("cafes in Sydney", price_levels=taught)
    body = json.loads(stub_server.last_request["body"])
    assert body["priceLevels"] == taught
