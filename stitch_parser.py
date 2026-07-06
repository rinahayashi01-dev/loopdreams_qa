"""
Tokenizes the instruction text of a single round/row (or border instruction)
into a list of StitchClause objects.

Approach: split on commas/semicolons/periods into clause candidates -- but
NOT inside parentheses, since real patterns write multi-stitch clusters as
"(sc, hdc, dc) in next st", which would otherwise get torn apart by a naive
comma split -- then pattern-match each candidate against known shapes.
Anything that doesn't match a known shape is kept as clause_type='unknown'
with an unverifiable_reason, rather than being silently dropped -- per
ARCHITECTURE.md philosophy of never silently guessing.

Stitch-word matching is PER-PATTERN, not just global: a pattern can define
its own shorthand abbreviation for a compound/decorative stitch (e.g.
"bo = bobble (5 incomplete dc in same st, ...)") instead of writing the
compound-stitch word itself in the instructions. The regex alternation of
recognized stitch words is therefore built fresh per call, extended with
whatever custom compound tokens the calling pattern's own abbreviation key
defines (see abbreviations.custom_compound_tokens), and cached so repeated
calls for the same pattern don't pay a rebuild cost per row.
"""
import functools
import re

from .models import StitchClause
from . import abbreviations as ab

# Base (hardcoded) stitch-ish words, independent of any one pattern's own
# abbreviation key. Longest-first ordering happens at compile time so e.g.
# "sh st" matches before "st" alone, "sc2tog" before "sc".
_BASE_STITCH_WORDS = frozenset(
    ab.ALL_KNOWN_TOKENS | {"shell stitch", "shell", "sh st", "cluster", "popcorn", "bobble", "puff"}
)

_POS = r"(?:the\s+)?(?:very\s+)?(first|next|last)"
_NOUN = r"(?:st|sc|hdc|dc|tr|ch)s?"

# Regexes that do NOT depend on the stitch-word alternation -- compiled once.
_RE_CHAIN = re.compile(r"^ch\s+(\d+)$", re.I)
_RE_TURN = re.compile(r"^turn$", re.I)
_RE_FASTEN_OFF = re.compile(r"^fasten off\.?$", re.I)
_RE_JOIN = re.compile(r"^join\b", re.I)
_RE_SETUP = re.compile(r"^with (rs|ws) facing\b", re.I)
_RE_REP_FROM = re.compile(r"^rep(?:eat)? from \*\s*(.*)$", re.I)
_RE_SKIP = re.compile(r"^sk(?:ip)?\s+(\d+)", re.I)
_RE_SKIP_POSITIONAL = re.compile(rf"^skip\s+{_POS}\s+{_NOUN}$", re.I)
# "skip (the) ch-1 sp(ace)" -- skips a chain-1 SPACE created by an earlier
# 'ch 1' in the pattern, not a real previous-row stitch (e.g. linen/moss
# stitch's "*ch 1, skip the ch-1 space, sc in next sc*"). Distinct from
# _RE_SKIP ("skip 1 ch" / "skip 2 sts"), which skips actual stitches/chains
# and does consume from the running count -- this skips a space that was
# never counted toward the stitch total in the first place (consistent with
# ARCHITECTURE.md's "chain stitches never count toward stitch total"), so
# it consumes 0.
_RE_SKIP_CHAIN_SPACE = re.compile(r"^skip\s+(?:the\s+)?ch-?1\s+sp(?:ace)?$", re.I)
_RE_NOTE = re.compile(r"^at (?:the )?end of this row$", re.I)
_RE_BRACKET_GROUP = re.compile(r"^\[(.*)\]\s*(once|twice|[a-z]+\s+times?|\d+\s*times?)\b", re.I)
# "(sc, hdc, dc) in next st" -- a named list of different stitches, all into ONE shared spot.
# Captures arbitrary lowercase words, so it works for custom tokens too without
# needing the dynamic alternation -- each captured word is individually looked
# up via _stitch_lookup at classify time.
_RE_PAREN_CLUSTER = re.compile(
    rf"^\(([a-z][a-z ,]*)\)\s+(?:all\s+)?in\s+{_POS}\s+{_NOUN}$", re.I
)

_MULTIPLIER_WORDS = {
    "once": 1, "twice": 2, "two times": 2, "three times": 3, "four times": 4,
    "five times": 5, "six times": 6, "seven times": 7, "eight times": 8,
}


class _Patterns:
    """Container for the subset of regexes whose alternation depends on the
    set of recognized stitch words for one particular pattern (built fresh
    per distinct custom-token set, then cached)."""

    __slots__ = (
        "counts_as_chain", "foundation_into_chain", "each_st_across", "each_st_around",
        "corner", "literal_next", "each_of_position", "side_edge", "cluster_same_spot",
        "centre_dc", "around_post", "top_of_chain", "simple_positional",
        "stitch_in_ch1_space", "foundation_ordinal_single",
    )

    def __init__(self, stitch_alt: str):
        self.counts_as_chain = re.compile(rf"^ch\s+(\d+)\s*\(counts\s+as\s+({stitch_alt})\)$", re.I)
        # Optional parenthetical clarification between the ordinal clause and
        # "and (in) each ch across" -- real phrasing found on a real sample
        # (waffle, Jul 6 batch): "Dc in 3rd ch from hook (skipped 2-ch does
        # not count as st) and in each ch across." This is LoopDreams
        # explicitly stating the skip-count convention inline, matching
        # exactly the verified canonical Waffle Stitch construction from
        # checks/known_constructions.py -- the row itself is correct; only
        # the clause shape was new.
        self.foundation_into_chain = re.compile(
            rf"^({stitch_alt})\s+in\s+(\d+)(?:st|nd|rd|th)\s+ch\s+from\s+hook\s*(?:\([^)]*\)\s*)?"
            rf"and\s+(?:in\s+)?each\s+ch\s+across$", re.I
        )
        self.each_st_across = re.compile(rf"^\*?({stitch_alt})\s+in\s+each\s+st\s+across\b\s*(.*)$", re.I)
        self.each_st_around = re.compile(rf"^\*?({stitch_alt})\s+in\s+each\s+st\s+around\b\s*(.*)$", re.I)
        self.corner = re.compile(rf"^\*?(\d*)\s*({stitch_alt})\s+in\s+corner$", re.I)
        self.literal_next = re.compile(rf"^(\d*)\s*({stitch_alt})\s+in\s+next\s+(\d+)\s*(?:sts?)?$", re.I)
        # "<stitch> in each of (the) first/last N sts" -- a generalization of
        # "in first/last st" to an explicit count N, instead of "in next N".
        # New clause shape found on a real sample (bobble tote bag, Jun 29
        # batch): the brick-offset bobble rows write their non-repeated edge
        # stitches this way ("SC in each of first 2 sts ... SC in each of
        # last 2 sts"), which no prior clause shape matched.
        self.each_of_position = re.compile(
            rf"^({stitch_alt})\s+in\s+each\s+of\s+(?:the\s+)?(first|last)\s+(\d+)\s*(?:sts?)?$", re.I
        )
        self.side_edge = re.compile(
            rf"^working\s+(\d+)\s+({stitch_alt})\s+per\s+row-?end\s+along\s+(?:each\s+)?side\s+edge$", re.I
        )
        # "<N> <stitch> in (first|next|last) st" -- N copies all worked into ONE shared spot.
        self.cluster_same_spot = re.compile(
            rf"^(\d+)\s+({stitch_alt})\s+(?:all\s+)?in\s+{_POS}\s+{_NOUN}$", re.I
        )
        # "sc in the centre dc of the next shell" -- single stitch into a named landmark position.
        self.centre_dc = re.compile(
            rf"^({stitch_alt})\s+in\s+(?:the\s+)?(?:centre|center)\s+dc\s+of\s+(?:the\s+)?(?:next|last)\s+shell$", re.I
        )
        # "fpdc around (post(s) of) next/last (N) st(s)" -- post stitches.
        self.around_post = re.compile(
            rf"^({stitch_alt})\s+around\s+(?:the\s+)?(?:posts?\s+of\s+)?{_POS}\s*(\d+)?\s*{_NOUN}$", re.I
        )
        # "dc in top of ch" / "dc in top of ch-2"
        self.top_of_chain = re.compile(rf"^({stitch_alt})\s+in\s+top\s+of\s+(?:the\s+)?ch(?:-\d+)?$", re.I)
        # Generic single-instance positional clause: "<stitch> in (first|next|last) st"
        self.simple_positional = re.compile(rf"^({stitch_alt})\s+in\s+{_POS}\s+{_NOUN}$", re.I)
        # "<stitch> in (first|next|last) ch-1 sp(ace)" -- linen/moss-stitch
        # style, working into a chain-1 SPACE left by the previous row
        # rather than into an actual previous-row stitch. New phrasing found
        # on a real sample (Jul 2, third throw-blanket batch): earlier
        # samples wrote this as "skip the ch-1 space, sc in next st/sc" (the
        # skip and the stitch-target are separate clauses); this phrasing
        # instead makes the ch-1 space itself the stitch's target noun.
        # Semantically the same "one previous-row slot in, one stitch out"
        # shape as simple_positional -- just a different noun -- so it gets
        # the same consumes=1 (that slot), produces=stitch's own ratio.
        self.stitch_in_ch1_space = re.compile(
            rf"^({stitch_alt})\s+in\s+{_POS}\s+ch-?1\s+sp(?:ace)?$", re.I
        )
        # "<stitch> in 2nd ch from hook" WITHOUT a following "and each ch
        # across" -- a standalone foundation-start clause that's part of a
        # mixed row (e.g. linen/moss stitch: one ordinal stitch, then a
        # separate repeat group), not the whole-row "foundation_into_chain"
        # shape. The offset convention that shape uses (chain_count -
        # (ordinal-1)) is a whole-row property and doesn't have a
        # well-defined per-clause consumes/produces split when it's mixed
        # with an separately-written repeat group -- see stitch_count.py's
        # docstring on why this is left unverifiable rather than guessed.
        self.foundation_ordinal_single = re.compile(
            rf"^({stitch_alt})\s+in\s+(\d+)(?:st|nd|rd|th)\s+ch\s+from\s+hook$", re.I
        )


@functools.lru_cache(maxsize=64)
def _compiled_patterns(extra_tokens: frozenset) -> _Patterns:
    words = sorted(_BASE_STITCH_WORDS | extra_tokens, key=len, reverse=True)
    stitch_alt = "|".join(re.escape(w) for w in words)
    return _Patterns(stitch_alt)


def _parse_multiplier(text: str):
    t = text.strip().lower()
    if t in _MULTIPLIER_WORDS:
        return _MULTIPLIER_WORDS[t]
    m = re.match(r"^(\d+)\s*times?$", t)
    if m:
        return int(m.group(1))
    return None


def _canonical_stitch(token: str) -> str:
    t = token.lower().strip()
    if t in ("shell", "shell stitch"):
        return "sh st"
    return t


def _stitch_lookup(token: str, custom_compound: frozenset = frozenset()):
    """Returns (canonical_token, is_compound, consumes, produces)."""
    canon = _canonical_stitch(token)
    if canon in ab.STITCH_MATH:
        c, p = ab.STITCH_MATH[canon]
        return canon, False, c, p
    if canon in custom_compound or canon in ab.COMPOUND_STITCH_WORDS or canon in ("sh st",):
        return canon, True, None, None
    return canon, False, None, None  # totally unrecognized


def _split_top_level(text: str, seps: str = ",;.:") -> list:
    """Split on separator chars, but never inside ( ) or [ ] -- real patterns
    write multi-stitch clusters like "(sc, hdc, dc) in next st", which a
    naive comma split would tear apart."""
    parts = []
    depth = 0
    buf = []
    for ch in text:
        if ch in "([":
            depth += 1
            buf.append(ch)
        elif ch in ")]":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif depth == 0 and ch in seps:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return parts


def _strip_trailing_annotation(s: str) -> str:
    """Strip a trailing descriptive parenthetical like '(shell made)' or
    '(half shell at the edge)' -- but never the kind of parenthetical that
    IS the instruction itself (e.g. a leading stitch-cluster list), and
    never one that carries real math like '(counts as dc)'."""
    s = s.strip()
    m = re.search(r"\s*\(([^)]*)\)\s*$", s)
    while m:
        inner = m.group(1).strip().lower()
        before = s[: m.start()].strip()
        if not before or "counts as" in inner:
            break
        s = before
        m = re.search(r"\s*\(([^)]*)\)\s*$", s)
    return s


def tokenize_round(raw_text: str, custom_compound: frozenset = frozenset()) -> list:
    """Split a round/row's instruction text into StitchClause objects.

    custom_compound: tokens (lowercased) from THIS pattern's own
    abbreviation key that should be treated as compound/decorative stitches
    with no fixed consumes/produces ratio -- see
    abbreviations.custom_compound_tokens. Defaults to empty for callers
    (like tests) that don't have a pattern-specific abbreviation key handy.
    """
    custom_compound = frozenset(custom_compound)
    patterns = _compiled_patterns(custom_compound)
    text = raw_text.strip()
    parts = _split_top_level(text)
    clauses = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = _RE_BRACKET_GROUP.match(part)
        if m:
            inner_text = m.group(1)
            mult = _parse_multiplier(m.group(2))
            sub = tokenize_round(inner_text, custom_compound)
            clauses.append(StitchClause(raw=part, clause_type="bracket_group", explicit_count=mult,
                                         sub_clauses=sub,
                                         unverifiable_reason=None if mult is not None else
                                         f"could not parse repeat multiplier '{m.group(2)}'"))
            continue
        clauses.append(_classify(part, patterns, custom_compound))
    return clauses


def _classify(part: str, patterns: _Patterns, custom_compound: frozenset) -> StitchClause:
    raw_part = part
    p = part.strip()

    m = patterns.counts_as_chain.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="counted_chain",
                             explicit_count=int(m.group(1)), consumes=0, produces=1)

    m = _RE_CHAIN.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="chain", explicit_count=int(m.group(1)), consumes=0, produces=0)

    if _RE_TURN.match(p):
        return StitchClause(raw=raw_part, clause_type="turn", consumes=0, produces=0)

    if _RE_FASTEN_OFF.match(p):
        return StitchClause(raw=raw_part, clause_type="fasten_off", consumes=0, produces=0)

    if _RE_JOIN.match(p) or _RE_SETUP.match(p):
        return StitchClause(raw=raw_part, clause_type="join", consumes=0, produces=0)

    if _RE_NOTE.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    m = _RE_REP_FROM.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="repeat_close", explicit_count=None,
                             unverifiable_reason=f"repeat-close modifier: '{m.group(1).strip()}'")

    m = patterns.foundation_into_chain.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="foundation_into_chain",
                             explicit_count=int(m.group(2)), is_compound=is_compound)

    m = patterns.each_st_across.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="each_st_across",
                             consumes=c, produces=prod, is_compound=is_compound,
                             unverifiable_reason=None if not is_compound else
                             f"'{canon}' has no fixed consumes/produces ratio; construction not defined")

    m = patterns.each_st_around.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="each_st_around",
                             consumes=c, produces=prod, is_compound=is_compound,
                             unverifiable_reason=None if not is_compound else
                             f"'{canon}' has no fixed consumes/produces ratio; construction not defined")

    m = patterns.corner.match(p)
    if m:
        count = int(m.group(1)) if m.group(1) else 1
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        # A compound stitch has no fixed ratio (prod is always None from
        # _stitch_lookup for these), so its total produced count for N
        # corner repeats isn't knowable either -- leave unverifiable
        # rather than guessing 1 per repeat, same as every other
        # compound-stitch clause shape (each_st_across/around, etc.).
        # Note this is also why resolving via a solved ratio_overrides
        # value wouldn't be safe to add here on its own: _zone_sum adds
        # ratio_overrides[stitch] once per clause with no multiplier, so
        # a corner's explicit count > 1 would still need dedicated
        # handling before this could resolve to a real number.
        produces = None if is_compound else (prod or 1) * count
        return StitchClause(raw=raw_part, stitch=canon, clause_type="corner", explicit_count=count,
                             consumes=0, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if not is_compound else
                             f"'{canon}' has no fixed consumes/produces ratio; construction not defined")

    m = patterns.side_edge.match(p)
    if m:
        per_row = int(m.group(1))
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="side_edge_rule",
                             explicit_count=per_row, is_compound=is_compound)

    m = patterns.literal_next.match(p)
    if m:
        n_stitches = int(m.group(1)) if m.group(1) else 1
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        consumed_target = int(m.group(3))
        produces = (prod * n_stitches * consumed_target) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n_stitches, consumes=consumed_target,
                             produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    # "<stitch> in each of (the) first/last N sts" -- non-repeated edge
    # stitches stated with an explicit count rather than "in next N".
    m = patterns.each_of_position.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        n = int(m.group(3))
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n, consumes=n, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    # "<N> <stitch> in (first|next|last) st" -- N copies into ONE shared spot.
    m = patterns.cluster_same_spot.match(p)
    if m:
        n = int(m.group(1))
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="cluster_same_spot",
                             explicit_count=n, consumes=1, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    # "(sc, hdc, dc) in next st" -- named list of stitches, all into ONE shared spot.
    m = _RE_PAREN_CLUSTER.match(p)
    if m:
        tokens = [t.strip().lower() for t in m.group(1).split(",") if t.strip()]
        total_produce = 0
        unknown = []
        for tok in tokens:
            canon, is_compound, c, prod = _stitch_lookup(tok, custom_compound)
            if prod is None:
                unknown.append(canon)
            else:
                total_produce += prod
        return StitchClause(raw=raw_part, stitch="(" + ", ".join(tokens) + ")", clause_type="cluster_same_spot",
                             explicit_count=len(tokens), consumes=1,
                             produces=total_produce if not unknown else None,
                             is_compound=bool(unknown),
                             unverifiable_reason=None if not unknown else
                             f"unrecognized stitch(es) in cluster: {', '.join(unknown)}")

    m = patterns.centre_dc.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        # The true number of previous-row stitches this passes over depends
        # on the width of the referenced compound stitch (e.g. a 5-dc shell)
        # and isn't reliably inferable from the text alone -- consumes is
        # left unknown rather than guessed at 1, per ARCHITECTURE.md.
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             consumes=None, produces=prod, is_compound=is_compound,
                             unverifiable_reason=(
                                 f"'{m.group(0)}' references a position inside a multi-stitch group; how many "
                                 f"previous-row stitches this passes over depends on that group's width, which "
                                 f"can't be reliably inferred from the text alone"
                             ))

    m = patterns.around_post.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        n = int(m.group(3)) if m.group(3) else 1
        # "around (post of) next/last N st(s)" names the consumed count (N,
        # default 1) in its own grammar -- this is true regardless of which
        # stitch is being worked there, compound or not. Only produces
        # genuinely depends on the stitch itself.
        consumes = (c * n) if c is not None else n
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             explicit_count=n, consumes=consumes, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    m = patterns.top_of_chain.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        # "in top of (the) ch" names exactly ONE target chain-top, regardless
        # of which stitch is worked there.
        consumes = c if c is not None else 1
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             consumes=consumes, produces=prod, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    m = patterns.simple_positional.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        # "<stitch> in (first|next|last) st" -- singular "st" names exactly
        # ONE target previous-row stitch in its own grammar, regardless of
        # which stitch is worked into it. Only produces (what that one
        # stitch leaves behind -- 1 for a plain substitute, more for a
        # fanned-out construction) genuinely depends on the stitch itself
        # and can't be assumed.
        consumes = c if c is not None else 1
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             consumes=consumes, produces=prod, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    m = patterns.stitch_in_ch1_space.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        # Same shape as simple_positional above -- one previous-row slot in
        # (here, a chain-1 space left by the previous row, rather than an
        # actual previous-row stitch), one stitch's own produces out.
        consumes = c if c is not None else 1
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             consumes=consumes, produces=prod, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    m = _RE_SKIP_CHAIN_SPACE.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="skip", consumes=0, produces=0)

    m = _RE_SKIP.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="skip", explicit_count=int(m.group(1)),
                             consumes=int(m.group(1)), produces=0)

    m = _RE_SKIP_POSITIONAL.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="skip", explicit_count=1, consumes=1, produces=0)

    m = patterns.foundation_ordinal_single.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             explicit_count=int(m.group(2)), consumes=None, produces=None,
                             is_compound=is_compound,
                             unverifiable_reason=(
                                 f"'{m.group(0)}' is a standalone ordinal foundation-chain start mixed with a "
                                 f"separately-written repeat group (linen/moss-stitch style) rather than the "
                                 f"whole-row '...and each ch across' shape -- the offset convention for that "
                                 f"shape doesn't have a well-defined split across a mixed row like this, so "
                                 f"it's left unverifiable rather than guessed"
                             ))

    # Leading '*' opens a repeat group around whatever clause follows -- if we
    # didn't already match it above (e.g. "*3 sc in corner" matched the
    # corner pattern because it allows an optional leading '*'), tag it
    # generically.
    if p.startswith("*"):
        inner = _classify(p[1:].strip(), patterns, custom_compound)
        inner.raw = raw_part
        return inner

    # Trailing descriptive annotation like "(shell made)" didn't get stripped
    # by any of the regexes above (which all anchor at $) -- try stripping it
    # and re-classifying once before giving up.
    stripped = _strip_trailing_annotation(p)
    if stripped != p:
        inner = _classify(stripped, patterns, custom_compound)
        inner.raw = raw_part
        return inner

    return StitchClause(raw=raw_part, clause_type="unknown",
                         unverifiable_reason="unrecognized clause text; not matched by any known pattern shape")
