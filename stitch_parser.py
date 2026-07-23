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
#
# Unions ab.COMPOUND_STITCH_WORDS directly (rather than a separately
# hand-maintained duplicate list, which is what this used to be) --
# real bug found (shawl, Jul 8 batch): "moss"/"sedge" were added to
# abbreviations.COMPOUND_STITCH_WORDS but NOT to this separate hardcoded
# set, so every clause using them still failed to match ANY shape at all
# (unrecognized-clause noise on every row) even after that first fix,
# since THIS is the set that actually builds the tokenizer's regex
# alternation. Deriving from the one shared source avoids this class of
# bug recurring for the next compound word added.
_BASE_STITCH_WORDS = frozenset(ab.ALL_KNOWN_TOKENS | ab.COMPOUND_STITCH_WORDS | {"shell stitch"})

_POS = r"(?:the\s+)?(?:very\s+)?(first|next|last)"
_NOUN = r"(?:st|sc|hdc|dc|tr|ch)s?"

# Regexes that do NOT depend on the stitch-word alternation -- compiled once.
# \s* (was \s+) tolerates OCR dropping the space before the number (real
# sample: scarf-mossribbed, Jul 15 batch -- "Ch1" alongside a normally-
# spaced "Ch 1" elsewhere in the same file), same as the earlier "Row1"
# fix.
_RE_CHAIN = re.compile(r"^ch\s*(\d+)$", re.I)
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
# "Increase row: 2 DC in first st, ..." -- a leading row-type label, real
# phrasing (sweater, Jul 12 batch, sleeve shaping rows). Purely descriptive
# (the actual increase is fully accounted for by the row's own stitch
# clauses) -- a no-op for stitch-count purposes, same as the other labels
# below.
# Leading [^A-Za-z]* tolerates OCR noise gluing a stray punctuation
# character onto the row-number badge just before this label (real sample:
# sweater, Jul 12 batch: "Row 8_ Increase row: ..." -- the row_re parser
# leaves the underscore attached to the front of this clause's own text).
_RE_ROW_TYPE_LABEL = re.compile(r"^[^A-Za-z]*(?:increase|decrease)\s+row$", re.I)
# Real clause shapes found on a real sample (mittens, Jul 7 batch -- the
# first continuous-spiral/amigurumi-style construction this project has
# QA'd, with a thumb gusset). All of the following are no-ops for
# stitch-count purposes (informational markers, not stitches), EXCEPT
# held_aside/bridge_chain which carry real numbers other clauses need.
_RE_PLACE_MARKER = re.compile(r"^place\s+a\s+(?:stitch\s+)?marker\b", re.I)
# "Place the next 10 sts on a holder or scrap yarn (thumb gusset)" -- sets
# aside N sts from the active round (they're picked back up later, in a
# separate row/round -- see held_gusset_resume below). Removes N from
# THIS row's produced total but doesn't destroy them.
_RE_HELD_ASIDE = re.compile(r"^place\s+the\s+next\s+(\d+)\s+sts\s+on\s+a\s+holder\s+or\s+scrap\s+yarn\b", re.I)
# "Ch 2 to bridge the gap" -- a chain worked to bridge over the gap left by
# stitches just set aside (held_aside above), later folded into real
# stitches by a "working the last N sts ... into the N ch just made"
# round-completion clause in the SAME row -- see checks/stitch_count.py's
# dedicated gusset-transition row handler for how these combine.
_RE_BRIDGE_CHAIN = re.compile(r"^ch\s+(\d+)\s+to\s+bridge\s+the\s+gap$", re.I)
# "sl st to top of ch 3 to join" -- ends a JOINED round (flat circle/motif
# construction, real sample: coaster Jul 8 batch -- distinct from the
# continuous-spiral mittens construction, which never joins at all). A
# no-op for stitch-count purposes: it closes the round, doesn't add or
# remove stitches. The sc-variant coaster (same batch) has no counted
# turning chain to join back to -- its rounds open on a bare stitch
# instead, so the round closes with "sl st to first sc to join" instead;
# same no-op, different anchor phrase.
_RE_SL_ST_JOIN = re.compile(
    r"^sl\s*st\s+to\s+(?:top\s+of\s+ch\s+\d+|first\s+[a-z]+)\s+to\s+join$", re.I
)
# "sl st in next 2 sts of the foundation chain"/"...of the final row" --
# real phrasing (scarf-mossribbed, Jul 15 batch): a separate ribbing strip
# is worked perpendicular to the main panel and fused to it row-by-row via
# extra slip stitches into the panel's OWN edge (the foundation chain on
# one side, the final row on the other), not into the ribbing's own
# stitches. A no-op for the ribbing row's own declared width -- that width
# is already fully accounted for by the row's other clause(s) (e.g. "sl st
# in back loop only of each st across"); this is a side action consuming
# from a DIFFERENT reference frame (the main panel's edge), not adding to
# or subtracting from this row's own stitch count.
_RE_SL_ST_EDGE_ATTACH = re.compile(
    r"^sl\s*st\s+in\s+next\s+\d+\s+sts?\s+of\s+the\s+(?:foundation\s+chain|final\s+row)$", re.I
)
# "changing to Colour 2 -- Moss in the last st" -- an inline colour change
# stated as a trailing clause within a row (distinct from the existing
# leading "With Colour B -- Moss:" row-opening marker pattern_parser.py
# already handles). No stitch-count effect either way. The "-- Name" suffix
# is itself optional -- real sample (LoopDreams generator): "changing to
# Colour 2 in the last st" with no name at all (the name is a frontend-only
# display enrichment, never part of the stored pattern text this tool
# actually receives). Also accepts a bare "changing to White in the last
# st" -- no "colour" word at all -- for margin/blank picture-grid cells,
# which the generator's own colourLabel() names literally "White" rather
# than a numbered "Colour N" (see pattern_parser.py's Foundation-clause fix
# comment for the BLANK_COLOUR source).
_RE_INLINE_COLOUR_CHANGE = re.compile(
    r"^changing\s+to\s+(?:colour\s+[\w]+(?:\s*[—-]\s*[\w]+)?|white)\s+in\s+the\s+last\s+st$", re.I
)
# "working the last 2 sts of the round into the 2 ch just made" -- the
# comma-split half of the round-completion sentence that follows "sc in
# each remaining st around,". No-op on its own: the gusset-transition row
# handler in checks/stitch_count.py gets both numbers it needs directly
# from the held_aside/bridge_chain clauses earlier in the same row, not
# from re-parsing this phrase.
_RE_WORKING_LAST_INTO_CH = re.compile(
    r"^working\s+the\s+last\s+\d+\s+sts?\s+of\s+the\s+round\s+into\s+the\s+\d+\s+ch\s+just\s+made$", re.I
)
# Drawstring-cinch closure (real phrasing, mittens Jul 7 batch: "Fasten
# off, leaving a long tail. Thread the tail through the front loop of each
# remaining stitch, pull tight to close the fingertip opening, and weave
# in the end."). The comma/period split breaks this into several top-level
# parts -- "Fasten off" already matches _RE_FASTEN_OFF; these cover the
# rest. All no-ops for stitch-count purposes: the trailing declared count
# restates how many stitches existed going into the closure, not something
# this text itself produces.
_RE_LEAVING_LONG_TAIL = re.compile(r"^leaving\s+a\s+long\s+tail$", re.I)
_RE_THREAD_TAIL_FRONT_LOOP = re.compile(
    r"^thread\s+the\s+tail\s+through\s+the\s+front\s+loop\s+of\s+each\s+remaining\s+stitch$", re.I
)
_RE_PULL_TIGHT_CLOSE = re.compile(r"^pull\s+tight\s+to\s+close\s+the\s+.+$", re.I)
# Two real closing phrasings: the drawstring-cinch single-tail form above
# ("...pull tight to close the ..., and weave in the end.") and the far more
# common plain closure used across nearly every other construction ("Fasten
# off, weave in ends." -- plural, no "and"/"the" at all; see generate-pattern's
# builders.ts, e.g. line 212). Previously only the singular "the end" form
# matched, so the plain "weave in ends" close -- the majority case -- fell
# through as an unrecognized clause on every non-amigurumi pattern's last row.
_RE_WEAVE_IN_END = re.compile(r"^(?:and\s+)?weave\s+in\s+(?:the\s+end|ends)$", re.I)
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
        "multi_into_each", "held_gusset_resume", "evenly_across_bridge", "bare_stitch",
        "each_st_to_marker", "each_st_to_last", "same_st",
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
        # Both allow an optional "in the back/front loop only of" infix
        # (real phrasing, mittens Jul 7 batch: "Sc in the back loop only of
        # each st around") and an optional "remaining" qualifier ("each
        # remaining st around" -- the gusset-transition round-completion
        # clause after some stitches were already set aside/worked
        # separately earlier in the same row). Also an optional leading
        # count multiplier (real phrasing, coaster Jul 8 batch: "2 dc in
        # each remaining st around" -- an increase, 2 copies into EACH
        # remaining stitch, not just 1).
        # "in\s*each" (was "in\s+each") -- real OCR artifact (sweater, Jul
        # 12 batch, sc variant): a single row's "SC in each st across" comes
        # out as "SC ineach st across", the space between "in" and "each"
        # dropped, while every other row in the same file has it normally.
        # \s* tolerates both without risking a false match elsewhere, since
        # the literal word "each" still must follow directly either way.
        self.each_st_across = re.compile(
            rf"^\*?(\d*)\s*({stitch_alt})\s+in\s*(?:(?:the\s+)?(?:back|front)\s+loop\s+only\s+of\s+)?"
            rf"each\s+(?:remaining\s+)?st\s+across\b\s*(.*)$", re.I
        )
        self.each_st_around = re.compile(
            rf"^\*?(\d*)\s*({stitch_alt})\s+in\s*(?:(?:the\s+)?(?:back|front)\s+loop\s+only\s+of\s+)?"
            rf"each\s+(?:remaining\s+)?st\s+around\b\s*(.*)$", re.I
        )
        self.corner = re.compile(rf"^\*?(\d*)\s*({stitch_alt})\s+in\s+corner$", re.I)
        self.literal_next = re.compile(rf"^(\d*)\s*({stitch_alt})\s+in\s+next\s+(\d+)\s*(?:sts?)?$", re.I)
        # "<stitch> in each of (the) first/last N sts" -- a generalization of
        # "in first/last st" to an explicit count N, instead of "in next N".
        # New clause shape found on a real sample (bobble tote bag, Jun 29
        # batch): the brick-offset bobble rows write their non-repeated edge
        # stitches this way ("SC in each of first 2 sts ... SC in each of
        # last 2 sts"), which no prior clause shape matched.
        self.each_of_position = re.compile(
            rf"^({stitch_alt})\s+in\s+each\s+of\s+(?:the\s+)?(first|last|next)\s+(\d+)\s*(?:sts?)?$", re.I
        )
        # "<N> <stitch> in each of (first|next|last) M sts" -- an increase:
        # N copies worked into EACH of the next M previous-row stitches
        # (distinct from each_of_position above, which is a plain 1:1
        # pickup of M stitches; here every one of the M stitches gets N
        # copies). Real phrasing (mittens, Jul 7 batch, thumb gusset
        # shaping): "2 sc in each of next 2 sts".
        self.multi_into_each = re.compile(
            rf"^(\d+)\s+({stitch_alt})\s+in\s+each\s+of\s+(?:the\s+)?(?:first|next|last)\s+(\d+)\s*(?:sts?)?$", re.I
        )
        # "<stitch> in each of the N held gusset sts" -- resuming the
        # stitches set aside earlier by held_aside (see module-level
        # _RE_HELD_ASIDE), a plain 1:1 pickup. Real phrasing (mittens,
        # Jul 7 batch, thumb round 1).
        self.held_gusset_resume = re.compile(
            rf"^({stitch_alt})\s+in\s+each\s+of\s+the\s+(\d+)\s+held\s+gusset\s+sts$", re.I
        )
        # "then sc N sts evenly across the bridge chain" -- picking up N new
        # stitches from the bridge chain made earlier (module-level
        # _RE_BRIDGE_CHAIN), not consuming any previous-round stitches.
        self.evenly_across_bridge = re.compile(
            rf"^(?:then\s+)?({stitch_alt})\s+(\d+)\s+sts\s+evenly\s+across\s+the\s+bridge\s+chain$", re.I
        )
        # Bare stitch token with no positional phrase at all -- e.g.
        # "sc2tog" used alone inside a repeat group ("*sc2tog, sc in each
        # of next 12 sts; rep from * around"). Real phrasing (mittens,
        # Jul 7 batch, decrease rounds). Only matches stitches with a
        # grammar-independent fixed ratio already in abbreviations.STITCH_MATH
        # (sc2tog is consumes=2/produces=1 regardless of context) -- a
        # compound/unrecognized token here would have nothing to anchor a
        # ratio to, so it's left to the final "unknown" fallback instead.
        self.bare_stitch = re.compile(rf"^({stitch_alt})$", re.I)
        # "<stitch> in each st to <arbitrary marker text>" -- a PARTIAL round
        # completion that stops before a marked point, rather than finishing
        # the whole round (each_st_around) or the whole row (each_st_across).
        # How many previous-row stitches this consumes on its own isn't
        # knowable without knowing exactly where the marker falls -- left
        # unverifiable at the clause level, but see
        # checks/stitch_count.py's dedicated gusset-transition row handler:
        # the ROW's total math doesn't actually depend on that split point.
        self.each_st_to_marker = re.compile(
            rf"^({stitch_alt})\s+in\s+each\s+st\s+to\s+.+$", re.I
        )
        # "<stitch> in each st to last st" -- NOT a marker (the position is
        # exactly as well-defined as "in last st" is everywhere else in this
        # module), so it must be checked BEFORE each_st_to_marker's broad
        # ".+$" catch-all, which would otherwise swallow it as an
        # unverifiable partial-round-completion. Real phrasing (sweater,
        # Jul 12 batch, sleeve increase rows): "2 DC in first st, DC in
        # each st to last st, 2 DC in last st" -- reuses the "each_st_
        # across" clause TYPE (not a new one) so the existing pre/post
        # each_st dispatch in checks/stitch_count.py handles it for free:
        # the trailing "2 DC in last st" clause's own consumes/produces
        # already get folded into "post", correctly reserving that last
        # stitch out of what this clause consumes.
        self.each_st_to_last = re.compile(
            rf"^({stitch_alt})\s+in\s+each\s+st\s+to\s+last\s+st$", re.I
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
        # "<stitch> in (the) same st" -- an increase paired with a counted
        # turning chain (real sample, coaster Jul 8 batch: "Ch 3 (counts as
        # first dc), dc in same st" -- the ch-3 already counts as the
        # round's first dc; this adds a SECOND dc at that same position,
        # rather than consuming a new previous-row stitch).
        self.same_st = re.compile(rf"^({stitch_alt})\s+in\s+(?:the\s+)?same\s+st$", re.I)
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

    if _RE_NOTE.match(p) or _RE_ROW_TYPE_LABEL.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    if _RE_PLACE_MARKER.match(p) or _RE_INLINE_COLOUR_CHANGE.match(p) or _RE_WORKING_LAST_INTO_CH.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    if _RE_SL_ST_JOIN.match(p):
        return StitchClause(raw=raw_part, clause_type="join", consumes=0, produces=0)

    if _RE_SL_ST_EDGE_ATTACH.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    if (_RE_LEAVING_LONG_TAIL.match(p) or _RE_THREAD_TAIL_FRONT_LOOP.match(p)
            or _RE_PULL_TIGHT_CLOSE.match(p) or _RE_WEAVE_IN_END.match(p)):
        return StitchClause(raw=raw_part, clause_type="closure", consumes=0, produces=0)

    m = _RE_HELD_ASIDE.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="held_aside",
                             explicit_count=int(m.group(1)), consumes=int(m.group(1)), produces=0)

    m = _RE_BRIDGE_CHAIN.match(p)
    if m:
        # Distinct clause_type (not the generic "chain") so
        # checks/stitch_count.py's gusset-transition row handler can detect
        # this shape unambiguously rather than sniffing raw text.
        return StitchClause(raw=raw_part, clause_type="bridge_chain", explicit_count=int(m.group(1)),
                             consumes=0, produces=0)

    m = _RE_REP_FROM.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="repeat_close", explicit_count=None,
                             unverifiable_reason=f"repeat-close modifier: '{m.group(1).strip()}'")

    m = patterns.foundation_into_chain.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="foundation_into_chain",
                             explicit_count=int(m.group(2)), is_compound=is_compound)

    m = patterns.each_st_to_last.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="each_st_across",
                             consumes=c, produces=prod, is_compound=is_compound,
                             unverifiable_reason=None if not is_compound else
                             f"'{canon}' has no fixed consumes/produces ratio; construction not defined")

    m = patterns.each_st_to_marker.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="each_st_to_marker",
                             consumes=None, produces=None, is_compound=is_compound,
                             unverifiable_reason=(
                                 f"'{m.group(0)}' is a partial round completion stopping at a marked point -- "
                                 f"how many previous-row stitches this consumes on its own depends on where the "
                                 f"marker falls, which isn't stated as a number"
                             ))

    m = patterns.each_st_across.match(p)
    if m:
        multiplier = int(m.group(1)) if m.group(1) else 1
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        produces = (prod * multiplier) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="each_st_across",
                             explicit_count=multiplier, consumes=c, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if not is_compound else
                             f"'{canon}' has no fixed consumes/produces ratio; construction not defined")

    m = patterns.each_st_around.match(p)
    if m:
        multiplier = int(m.group(1)) if m.group(1) else 1
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        produces = (prod * multiplier) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="each_st_around",
                             explicit_count=multiplier, consumes=c, produces=produces, is_compound=is_compound,
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
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        consumed_target = int(m.group(3))
        if not m.group(1):
            # Bare "<stitch> in next N sts" -- no leading count at all.
            # Well-established: 1 stitch per position, N total.
            n_stitches = 1
            produces = (prod * consumed_target) if prod is not None else None
            unverifiable_reason = None if prod is not None else f"'{canon}' has no fixed consumes/produces ratio"
        else:
            n_stitches = int(m.group(1))
            if n_stitches == consumed_target:
                # Real phrasing found on a real sample (dishcloth, Jul 8
                # batch): "45 DC in next 45 sts" -- the leading count is a
                # redundant restatement of the same number, not a
                # multiplier ("N per EACH of the M stitches", which is what
                # this shape means when the two numbers differ). Confirmed
                # by the row's own declared count staying flat (45 -> 45,
                # no shaping expected): the only sensible reading is 1
                # stitch per position, same as the bare form above.
                produces = (prod * consumed_target) if prod is not None else None
                unverifiable_reason = (
                    None if prod is not None else f"'{canon}' has no fixed consumes/produces ratio"
                )
            else:
                # "<N> <stitch> in next <M> sts" with N != M: read as N
                # copies into EACH of M stitches. Unlike the N == M case
                # above, this specific combination has never actually been
                # exercised by any real sample or test -- rather than keep
                # guessing an unvalidated formula, leave it unverifiable
                # until a real case confirms which reading is intended.
                produces = None
                unverifiable_reason = (
                    f"'{m.group(0)}' states two different numbers ({n_stitches} and {consumed_target}) with no "
                    f"confirmed real-sample precedent for what that combination means here -- left unverifiable "
                    f"rather than guessed"
                )
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n_stitches, consumes=consumed_target,
                             produces=produces, is_compound=is_compound,
                             unverifiable_reason=unverifiable_reason)

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

    # "<N> <stitch> in each of (first|next|last) M sts" -- an increase: N
    # copies worked into EACH of M previous-row stitches (distinct from
    # each_of_position above, which is a plain 1:1 pickup of M stitches).
    m = patterns.multi_into_each.match(p)
    if m:
        n_per = int(m.group(1))
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        count = int(m.group(3))
        produces = (prod * n_per * count) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=count, consumes=count, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    # "<stitch> in each of the N held gusset sts" -- resuming stitches set
    # aside earlier (held_aside), a plain 1:1 pickup.
    m = patterns.held_gusset_resume.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        n = int(m.group(2))
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="held_gusset_resume",
                             explicit_count=n, consumes=n, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    # "then sc N sts evenly across the bridge chain" -- N new stitches
    # picked up from the bridge chain, not consuming any previous-round sts.
    m = patterns.evenly_across_bridge.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        n = int(m.group(2))
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n, consumes=0, produces=produces, is_compound=is_compound,
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

    m = patterns.same_st.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        # Hand-verified against the real sample (coaster, Jul 8 batch,
        # rounds 1-3): the preceding turning chain here is a BARE, un-
        # counted "Ch 3" (produces=0 on its own) -- the "counts as first
        # dc" convention stated once in the Foundation line carries
        # forward implicitly, rather than being restated on every round.
        # So "dc in same st" alone has to represent the FULL 2-stitch
        # increase at that position: consumes=1 (the one real previous-
        # round stitch the chain+this dc together replace), produces=2
        # (the implicit chain-stitch plus this explicit one). Confirmed by
        # testing all three increase rounds' declared counts (12->24,
        # 24->36, 36->48) against this exact model -- all resolve exactly.
        produces = (prod * 2) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             consumes=1, produces=produces, is_compound=is_compound,
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

    # Bare stitch token with no positional phrase at all (e.g. "sc2tog"
    # inside a repeat group). Only fires for stitches with a fixed,
    # context-independent ratio -- see patterns.bare_stitch's own comment.
    m = patterns.bare_stitch.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        if c is not None and prod is not None:
            return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                                 explicit_count=1, consumes=c, produces=prod, is_compound=is_compound)

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
