"""Round 77 pins for the spelling guard's reader text.

The Round 57 guard read the raw README, so a name spelled only
inside a span the rendered page never shows counted as taught.
Each pin below builds a document whose only spelling of the
target sits inside one such span and asserts the guard now
reports the name untaught, driving the guard module's own
machinery loaded by path. The positive controls assert the
shapes a reader does see still count. Every false pass pin
fails against the unguarded raw read, and the controls are
pinned against the repair's earlier forms, which the mutation
passes demonstrate.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

GUARD_PATH = Path(__file__).resolve().parent / "test_round57.py"
spec = importlib.util.spec_from_file_location("round57_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

KEYWORD = "max_height_px"


def taught(text, name=KEYWORD):
    return guard._spelled(guard._reader_text(text), name)


def test_comment_only_spelling_is_untaught():
    assert not taught("The size pair is set in pixels.\n<!-- `max_height_px` -->")


def test_multiline_comment_spelling_is_untaught():
    text = "The size pair is set in pixels.\n<!--\n`max_height_px`\n-->"
    assert not taught(text)


def test_unterminated_comment_spelling_is_untaught():
    assert not taught("Pixels.\n<!-- max_height_px=4800")


def test_tag_attribute_argument_form_is_untaught():
    assert not taught('<span title="max_height_px=4800">Pixels.</span>')


def test_tag_attribute_backticked_form_is_untaught():
    assert not taught('<span title="`max_height_px`">Pixels.</span>')


def test_hidden_element_spelling_is_untaught():
    assert not taught("<span hidden>`max_height_px`</span> Pixels.")


def test_display_none_element_spelling_is_untaught():
    text = '<span style="display: none">`max_height_px`</span> Pixels.'
    assert not taught(text)


def test_link_destination_spelling_is_untaught():
    text = "[the photo call](https://example.com/media?max_height_px=4800)"
    assert not taught(text)


def test_reference_definition_spelling_is_untaught():
    text = "The photo call takes a size.\n\n[sz]: https://example.com/?max_height_px=4800"
    assert not taught(text)


def test_member_spelling_in_comment_is_untaught():
    rendered = guard._reader_text("Masks are built by hand.\n<!-- `FieldMask.of` -->")
    assert "`FieldMask.of`" not in rendered


def test_price_values_in_comment_are_untaught():
    comment = "<!-- " + " ".join(guard.PRICE_LEVEL_VALUES) + " -->"
    rendered = guard._reader_text("Prices filter by level.\n" + comment)
    assert re.findall(r"PRICE_LEVEL_[A-Z_]+", rendered) == []


def test_hidden_same_tag_child_is_untaught():
    text = "<div hidden><div>inner</div> `max_height_px` </div> Pixels."
    assert not taught(text)


def test_hidden_same_tag_child_span_is_untaught():
    text = "<span hidden><span>inner</span> `max_height_px` </span> Pixels."
    assert not taught(text)


def test_hidden_unclosed_element_is_untaught():
    assert not taught("Pixels. <span hidden>`max_height_px`")


def test_uppercase_hidden_attribute_is_untaught():
    assert not taught("<span HIDDEN>`max_height_px`</span> Pixels.")


def test_uppercase_display_none_is_untaught():
    text = '<span style="DISPLAY: NONE">`max_height_px`</span> Pixels.'
    assert not taught(text)


def test_unquoted_style_display_none_is_untaught():
    text = "<span style=display:none>`max_height_px`</span> Pixels."
    assert not taught(text)


def test_visibility_hidden_element_is_untaught():
    text = '<span style="visibility: hidden">`max_height_px`</span> Pixels.'
    assert not taught(text)


def test_parenthesised_link_destination_is_untaught():
    text = "[photo](https://example.com/wiki/Photo_(media)?max_height_px=4800)"
    assert not taught(text)


def test_image_alt_text_is_untaught():
    assert not taught("![`max_height_px`](photo.png) Pixels.")


def test_reference_definition_title_line_is_untaught():
    text = 'A size.\n\n[sz]: https://example.com/x\n  "max_height_px=4800"'
    assert not taught(text)


def test_script_element_spelling_is_untaught():
    text = "<script>var x = 'max_height_px=4800';</script> Pixels."
    assert not taught(text)


def test_style_element_spelling_is_untaught():
    text = "<style>.a { content: 'max_height_px=4800'; }</style> Pixels."
    assert not taught(text)


def test_visible_element_spelling_still_counts():
    assert taught("<span>`max_height_px`</span>")


def test_fenced_example_spelling_still_counts():
    assert taught("```python\nphoto = client.place_photo(p, max_height_px=4800)\n```")


def test_struck_through_spelling_still_counts():
    assert taught("~~`max_height_px`~~")


def test_plain_teaching_still_counts():
    assert taught("The size is set with `max_height_px` as the other member.")


def test_comment_mentioning_a_fence_keeps_the_tail():
    text = (
        "<!-- note ``` -->\nSome prose.\n```python\nx = 1\n```\n"
        "The size is set with `max_height_px` here."
    )
    assert taught(text)


def test_comment_inside_a_fence_still_counts():
    text = "```html\n<!-- `max_height_px` -->\n```"
    assert taught(text)


def test_data_named_attribute_spelling_still_counts():
    assert taught('<span data-hidden="true">`max_height_px`</span>')


def test_class_named_hidden_spelling_still_counts():
    assert taught('<span class="hidden">`max_height_px`</span>')


def test_gt_in_attribute_hidden_is_untaught():
    assert not taught('<div data-x="a>b" hidden>`max_height_px`</div>')


def test_gt_in_attribute_style_is_untaught():
    text = '<div data-x="a>b" style="display:none">`max_height_px`</div>'
    assert not taught(text)


def test_two_level_parenthesised_destination_is_untaught():
    text = "[x](https://example.com/a(b(c)d)?max_height_px=4800)"
    assert not taught(text)


def test_crlf_definition_title_is_untaught():
    text = '[sz]: https://example.com/x\r\n  "max_height_px=4800"\r\n'
    assert not taught(text)


def test_css_comment_style_is_untaught():
    text = '<div style="display /*c*/ : none">`max_height_px`</div>'
    assert not taught(text)


def test_void_input_hidden_keeps_the_tail():
    assert taught("<input hidden> The size is set with `max_height_px` here.")


def test_void_img_hidden_keeps_the_tail():
    text = '<img hidden src="x.png"> The size is set with `max_height_px` here.'
    assert taught(text)


def test_longer_property_name_still_counts():
    assert taught('<div style="x-display: none">`max_height_px`</div>')


def test_unquoted_value_named_hidden_still_counts():
    assert taught("<div data-note=hidden>`max_height_px`</div>")


def test_nul_literal_survives_and_counts():
    assert taught("plain \x003\x00 text with `max_height_px` set")


def test_three_level_parenthesised_destination_is_untaught():
    text = "[x](https://example.com/a(b(c(d)e)f)?max_height_px=4800)"
    assert not taught(text)


def test_three_level_parenthesised_image_is_untaught():
    text = "![x](https://example.com/a(b(c(d)e)f)?max_height_px=4800)"
    assert not taught(text)


def test_seam_formed_sentinel_does_not_duplicate_a_fence():
    text = "A\x00<!--x-->0\x00 B\n```\ncode\n```\n`max_height_px`"
    assert guard._reader_text(text).count("```") == 2


def test_nested_image_alt_in_link_text_is_untaught():
    text = "[see ![alt `max_height_px`](img.png) here](https://example.com/)"
    assert not taught(text)


def test_badge_form_alt_is_untaught():
    text = "[![`max_height_px`](img.png)](https://example.com/)"
    assert not taught(text)


def test_nested_brackets_text_destination_is_untaught():
    text = "[a [b] c](https://example.com/?max_height_px=4800)"
    assert not taught(text)


def test_escaped_close_parenthesis_destination_is_untaught():
    text = "[x](https://example.com/a\\)b?max_height_px=4800)"
    assert not taught(text)


def test_escaped_open_parenthesis_destination_is_untaught():
    text = "[x](https://example.com/a\\(b?max_height_px=4800)"
    assert not taught(text)


def test_prose_bracket_with_spaced_parenthesis_still_counts():
    assert taught("the index [0](max_height_px=4800 in parens) stands")


def test_empty_destination_link_text_still_counts():
    assert taught("[`max_height_px`]()")


def test_spaced_empty_destination_does_not_raise():
    assert not taught("![`max_height_px`]( )")
