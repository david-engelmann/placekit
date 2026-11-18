"""Package-wide guarded readings and the bounded materialiser.

This module is the one home for the two disciplines that
sit below every other module in the import graph: naming
a caller supplied value in a refusal without letting the
value break the refusal itself, and materialising a
caller iterable under the universal ceiling. models,
exceptions and fields each carried their own copy of the
render helpers, with one copy's fallback wording diverged
from the other two, and the materialiser lived in fields,
which exceptions could only reach through a call time
import because the module level import cannot close the
circle (audit A50-081 and A50-082).

The module imports nothing from the package except, at
its foot, the ConfigError the materialiser raises. That
import stands last on purpose: exceptions imports this
module in its turn, after its own classes, and placing
the import after every definition here lets either
module load first.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

#: The universal ceiling on caller iterables the client materialises
#: (field masks here, list and mapping parameters in the client).
#: Slots whose API documentation states a smaller maximum enforce
#: that maximum instead; this ceiling is the bound for every other
#: slot, so an endless or absurd iterable is refused with a
#: ConfigError after this many items instead of being consumed
#: until memory runs out (R20-F01 and F02).
MAX_MATERIALIZED_ITEMS = 1000


def _safe_type_name(value: Any) -> Optional[str]:
    """The type name of a caller supplied value, safe to read in
    a refusal.

    Refusals name the values they refuse by type as well as by
    repr, and a class can answer its name through a metaclass
    that raises on the read or answers with something that is
    not a plain string, so a refusal interpolating the raw
    name would break on the name itself and escape bare.
    Where the name reads as a plain string it is returned
    unchanged, so no honest refusal message moves. Where it
    cannot be read as one, None stands in and the caller
    names the value by the fixed unrepresentable form
    instead. This is the one guarded name reading in the
    package, and every site that names a type reads through
    it.
    """
    try:
        name = type(value).__name__
    except Exception:
        return None
    if type(name) is str:
        return name
    return None


def _safe_repr(value: Any) -> str:
    """The repr of a caller supplied value, safe to name in a
    refusal.

    Refusals interpolate the values they refuse, and a value
    whose own repr raises would break the refusal itself and
    escape bare. Where repr works its answer is returned
    unchanged, so no honest refusal message moves. Where it
    raises, the value is named by its type instead, through
    the guarded name reading above, and where the name
    cannot be read as a plain string the fixed
    unrepresentable form stands in its place.
    """
    try:
        return repr(value)
    except Exception:
        pass
    name = _safe_type_name(value)
    if name is not None:
        return f"<unrepresentable {name}>"
    return "<unrepresentable value>"


def _materialize_bounded(
    name: str,
    iterable: Iterable[Any],
    limit: int,
    *,
    documented_maximum: bool = False,
) -> list:
    """Materialise one caller iterable under a bound, in one place.

    This is the single bounded read loop behind the field mask
    builder and the client's list and mapping parameters, with
    one error wording for every slot. Items are counted as they
    are consumed, never by any container they land in, so a
    stream that never ends is refused after the limit even when
    it cycles over values it already yielded. Anything the
    iterable raises while being read surfaces as a ConfigError
    with the original exception chained, and the caught
    exception is named through the safe repr, so an exception
    whose own repr raises cannot break the refusal itself.
    ``documented_maximum``
    marks a limit the API documentation states for the slot,
    which words the refusal as the slot's own maximum; every
    other limit is the universal ceiling and words it as one.
    """
    try:
        iterator = iter(iterable)
    except Exception as exc:
        raise ConfigError(
            f"{name} could not be read as an iterable: "
            f"{_safe_repr(exc)}"
        ) from exc
    items: list = []
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except Exception as exc:
            raise ConfigError(
                f"{name} raised while being read: "
                f"{_safe_repr(exc)}"
            ) from exc
        items.append(item)
        if len(items) > limit:
            if documented_maximum:
                raise ConfigError(
                    f"{name} takes at most {limit} items, got more"
                )
            raise ConfigError(
                f"{name} materialised past the ceiling of "
                f"{limit} items; refusing to consume an "
                "unbounded iterable"
            )
    return items


from .exceptions import ConfigError  # noqa: E402
