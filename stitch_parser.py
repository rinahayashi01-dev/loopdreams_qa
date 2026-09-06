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
from dataclasses import replace

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
# "chain"/"chains" added alongside the existing abbreviated "ch"/"chs" --
# real bug found (Sedge Stitch, loopdreams commit "Fix Sedge Stitch
# construction", Aug 2026): LoopDreams' generator universally spells this
# word out in prose ("Hdc in the next chain", "sc in last chain" --
# generate-pattern's builders.ts skipChainsClause() convention, used
# across every compound-stitch builder, not just Sedge), never abbreviates
# it to "ch" outside of the "Ch N" foundation-count clause itself (see
# _RE_CHAIN) or the dedicated "Nth ch from hook" ordinal shapes. "chain"
# listed before "ch" so the longer word is preferred when both could
# start a match, matching this file's existing longest-first convention
# (see _BASE_STITCH_WORDS's own comment) -- though re's alternation
# backtracking would find the correct overall match either order, since
# every use of _NOUN is anchored with a trailing $.
# "space"/"sp" added alongside the stitch nouns -- a round worked into the
# SPACES a previous round left (a ch-1 space, a ch-2 corner space, the gap
# between two dc) rather than into its stitches is the whole grammar of
# motif-in-the-round construction, and none of it parsed: every clause in
# LoopDreams' Granny Square and Basic Motif builders is written "in the same
# sp", "in next corner sp", "in the sp between any 2 dc" (real samples,
# generate-pattern builders.ts buildGrannySquareRows/buildBasicMotifRows,
# Sep 2026 batch -- the first two templates ever put through this tool).
# Without it EVERY round of both templates came back "unrecognized clause" on
# every clause, which in turn tripped completeness.py's "numbered as a pattern
# row but none of its text matches any recognizable stitch instruction"
# warning on real, ordinary stitch rows.
#
# The optional modifier in _TARGET is what makes "next corner sp" and "next
# ch-2 corner sp" reachable -- a space is routinely qualified by which corner
# or which chain made it, unlike a plain stitch, which never is.
_NOUN = r"(?:chain|space|sp|st|sc|hdc|dc|tr|ch)s?"
_MODIFIER = r"(?:ch-?\d+\s+)?(?:corner\s+)?(?:ch-?\d+\s+)?"
_TARGET = rf"{_POS}\s+{_MODIFIER}{_NOUN}"

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
# A bare "N more time(s)" fragment trailing a comma after "rep from * <tail>,"
# (e.g. "rep from * to last shell, 1 more time, sc in..." -- LoopDreams'
# timesWord() helper, Aug 23) splits into its own clause at the comma,
# separate from the "rep from *" clause it modifies. Recognized here as its
# own no-op (classified as "repeat_close", same as _RE_REP_FROM itself --
# see checks/stitch_count.py's _zone_sum, which already skips that type)
# rather than falling through to "unknown": it carries no consumes/produces
# of its own, and the repeat count is solved algebraically from the row's
# declared stitch count either way (see this file's own module docstring),
# so the stated number is informational only, never load-bearing for the math.
_RE_MORE_TIMES = re.compile(r"^(\d+)\s+more\s+times?$", re.I)
_RE_SKIP = re.compile(r"^sk(?:ip)?\s+(\d+)", re.I)
_RE_SKIP_POSITIONAL = re.compile(rf"^skip\s+{_POS}\s+{_NOUN}$", re.I)
# A row's OWN opening clause reading exactly "skip first st" (not "skip
# next st" or "skip last st" -- those aren't this convention, see
# tokenize_round's use of this below).
_RE_SKIP_FIRST_ST = re.compile(r"^skip\s+first\s+sts?\b", re.I)
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
# "sl st in next 2 sts of the sc row" (current phrasing, loopdreams PR #333,
# Jul 28 batch) / "...of the foundation chain"/"...of the final row" (older
# phrasing, scarf-mossribbed, Jul 15 batch, kept for backward compat with
# any pattern generated before #333 shipped): a separate ribbing strip is
# worked perpendicular to the main panel and fused to it row-by-row via
# extra slip stitches into the panel's OWN edge -- as of #333, a preliminary
# sc row worked across the raw foundation-chain/final-row edge first (see
# loopdreams builders.ts's buildScarfEdgeScRow), not the raw edge itself.
# A no-op for the ribbing row's own declared width -- that width is already
# fully accounted for by the row's other clause(s) (e.g. "sl st in back
# loop only of each st across"); this is a side action consuming from a
# DIFFERENT reference frame (the main panel's edge), not adding to or
# subtracting from this row's own stitch count.
_RE_SL_ST_EDGE_ATTACH = re.compile(
    r"^sl\s*st\s+in\s+next\s+\d+\s+sts?\s+of\s+the\s+(?:sc\s+row|foundation\s+chain|final\s+row)$", re.I
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
# "Body measures approximately 67 in." -- a length checkpoint appended to a
# scarf body's own last row before Ribbing/Fringe/Tassels (loopdreams PR
# #335, Jul 28 batch) -- purely informational, no stitch-count effect.
_RE_BODY_LENGTH_CHECKPOINT = re.compile(
    r"^body\s+measures\s+approximately\s+[\d.]+\s*in\.?$", re.I
)
# "Magic ring" -- opens a continuous-spiral or joined-round construction
# (real samples: Amigurumi Ball/Cone/Limb, Coaster, Mittens -- loopdreams
# generate-pattern/builders.ts, Jul 29 batch). On its own it's a pure setup
# no-op (0 stitches exist yet) -- the real stitch count comes from the
# following "N <stitch> in ring" clause (see patterns.ring_literal below).
# Matched as its own top-level clause because "Magic ring." is always
# immediately followed by a "." in the real generator text, which
# _split_top_level treats as a separator.
_RE_MAGIC_RING = re.compile(r"^magic\s+ring$", re.I)
# "do not join or turn" -- states the continuous-spiral convention (no join,
# no turning chain) for the rest of the construction. Purely informational,
# same class of no-op as _RE_PLACE_MARKER just before it in the same
# sentence (real samples: Amigurumi Ball/Cone/Limb, Mittens, Amigurumi Egg).
_RE_DO_NOT_JOIN_OR_TURN = re.compile(r"^do\s+not\s+join\s+or\s+turn$", re.I)
# "Stuff the piece firmly as you go" (prefixed onto the first decrease-phase
# round) / "Finish stuffing firmly" (prefixed onto the closing round) --
# real, current generator text (loopdreams generate-pattern/builders.ts,
# Amigurumi Ball/Limb's shaped-round and continuous-round builders). A
# loopdreams batch-test run against production (Aug 1 2026) flagged both as
# "unrecognized clause", which broke recognition of the REST of the same
# row too (a single unknown clause fails the whole row's stitch-count
# check) -- purely a maker-facing reminder, no stitch-count effect of its
# own, same class of no-op as the "do not join or turn"/magic-ring
# construction notes above.
_RE_STUFF_NOTE = re.compile(
    r"^(?:stuff\s+the\s+piece\s+firmly\s+as\s+you\s+go|finish\s+stuffing\s+firmly)$", re.I
)
# "working on the opposite side of the foundation chain" -- a construction
# note in the Amigurumi Egg/Basic Oval foundation round, marking the pivot
# from working down one side of the starting chain to working back up the
# other side. No stitch-count effect of its own -- the stitches on each side
# are fully accounted for by the ordinal/each-of clauses around it.
_RE_OPPOSITE_SIDE_CHAIN = re.compile(
    r"^working\s+on\s+the\s+opposite\s+side\s+of\s+the\s+foundation\s+chain$", re.I
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
# Optional trailing purpose phrase -- real sample (Amigurumi Cone,
# loopdreams generate-pattern's buildContinuousShapedRoundRows, Aug 1 2026
# batch-test run against production): "Fasten off, leaving a long tail for
# seaming." A cone is left open (no drawstring-cinch closure, per the
# builder's own comment: meant to be stuffed and attached to a body, not
# closed up like a stuffed ball), so its own long tail serves a different,
# stated purpose than the bare "leaving a long tail" form above -- same
# no-op semantics either way.
_RE_LEAVING_LONG_TAIL = re.compile(r"^leaving\s+a\s+long\s+tail(?:\s+for\s+[a-z]+)?$", re.I)
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
    rf"^\(([a-z][a-z ,]*)\)\s+(?:all\s+)?in\s+{_TARGET}$", re.I
)
# "[3 dc, ch 2, 3 dc] in next corner sp", "[1 dc, ch 2, 2 dc] in the same sp"
# -- the four-corner increase every square motif is built from: a group of
# stitches AND chains, all worked into one shared space. _RE_PAREN_CLUSTER
# above cannot cover it: it takes only "(...)" (the generator writes corners
# with square brackets, matching published granny-square convention) and its
# capture is letters-only, so a group carrying its own counts and a "ch 2" in
# the middle -- which every corner group does -- never matched. _RE_BRACKET_
# GROUP doesn't cover it either: that shape is "[...] N times", a REPEAT, and
# requires a multiplier that a corner group never has.
#
# The contents are re-tokenized recursively (same as _RE_BRACKET_GROUP), so
# each member is scored by the normal rules: chains produce 0, plain stitches
# produce their own ratio, and a compound member with no fixed ratio leaves
# the whole group correctly unverifiable rather than guessed.
_RE_GROUP_INTO_SPOT = re.compile(
    rf"^[\[(](.+?)[\])]\s+(?:all\s+)?in\s+(?:(?:the\s+)?same\s+{_MODIFIER}{_NOUN}|{_TARGET})$", re.I
)
_RE_GROUP_INTO_SAME_SPOT = re.compile(
    rf"^[\[(].+?[\])]\s+(?:all\s+)?in\s+(?:the\s+)?same\s+{_MODIFIER}{_NOUN}$", re.I
)
# "Sl st to corner sp.", "Sl st in next ch-2 corner sp." -- a positioning move
# that walks the hook to where the next round starts. It creates no fabric of
# its own (the slip stitch is worked over an existing stitch/space, and the
# round's own count never includes it), so it is a pure no-op here, the same
# as the round-closing "sl st ... to join" already handled by sl_st_join.
# Real sample: loopdreams builders.ts buildGrannySquareRows opens EVERY round
# this way, and buildBasicMotifRows Rounds 5-6 do too.
_RE_SL_ST_TRAVEL = re.compile(
    rf"^sl\s*st\s+(?:to|in)\s+(?:{_TARGET}|(?:the\s+)?same\s+{_MODIFIER}{_NOUN}|corner\s+sp(?:ace)?)$", re.I
)
# "Fasten off Colour 1." -- breaking ONE colour part-way through a pattern
# that carries on in another, as distinct from the pattern-closing bare
# "Fasten off." already handled by _RE_FASTEN_OFF. Same no-op for stitch-count
# purposes, but deliberately NOT typed "fasten_off": completeness.py's
# _check_finishing_present treats a fasten_off clause on the last body row as
# proof the piece tells the maker how to finish, and a mid-pattern colour
# break is not that. Real sample: loopdreams builders.ts buildBasicMotifRows,
# Rounds 2-4 (each round is worked in its own colour and breaks it).
_RE_FASTEN_OFF_COLOUR = re.compile(
    r"^(?:fasten\s+off|break)\s+(?:colour|color)\s+\S+\.?$", re.I
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
        "turning_chain_credit",
        "centre_dc", "around_post", "top_of_chain", "simple_positional",
        "stitch_in_ch1_space", "foundation_ordinal_single",
        "multi_into_each", "held_gusset_resume", "evenly_across_bridge", "bare_stitch",
        "each_st_to_marker", "each_st_to_last", "same_st",
        "ring_literal", "foundation_ordinal_and_next_chs", "each_of_next_chs",
        "skip_first_chains_from_hook", "skip_first_chains_counting",
        "foundation_stitch_in_next_chain",
        "foundation_next_chain_and_next_chs",
        "sl_st_join", "trailing_count_restatement", "count_in_same_spot",
    )

    def __init__(self, stitch_alt: str):
        # Optional "first" before the stitch word -- real phrasing found on
        # a real sample (Coaster HDC/DC round 1, loopdreams builders.ts
        # buildCoasterRows, Jul 29 batch): "Ch 3 (counts as first dc)",
        # alongside the previously-seen "(counts as dc)" form used
        # elsewhere (e.g. motif rounds) with no "first" at all.
        self.counts_as_chain = re.compile(
            rf"^ch\s+(\d+)\s*\(counts\s+as\s+(?:first\s+)?({stitch_alt})\)$", re.I
        )
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
        # Two-clause foundation-start shape, split across a sentence boundary
        # instead of a single ordinal clause: "Skip the first N chain(s)
        # from the hook (it/they doesn't/don't count as a stitch). <stitch>
        # in the next chain and in each ch across." Real, current, widely-
        # used generator output (loopdreams generate-pattern/builders.ts's
        # skipChainsClause() helper, used across most flat-row builders) --
        # found systemically, not a one-off: a loopdreams batch-test run
        # against production (Aug 1 2026) flagged this shape as an
        # "unrecognized clause" on Row 1 of nearly every flat-panel pattern
        # (Scarf, Sweater, Tote Bag, Throw Blanket, Dishcloth, Cardigan,
        # square Coaster), at every skill level. Semantically identical to
        # foundation_into_chain's single-clause "<stitch> in Nth ch from
        # hook and in each ch across" -- skipping the first N chains and
        # starting the stitch in the next one is the same starting position
        # as the (N+1)th chain from the hook -- just written as two
        # sentences instead of one. The skip clause itself is purely
        # informational (0 chains consumed as stitches, 0 stitches
        # produced -- it's a skip, not a stitch); tokenize_round's own
        # post-processing pairs it with the following stitch clause and
        # folds both into a single foundation_into_chain-equivalent result,
        # so the rest of the pipeline (checks/stitch_count.py's dedicated
        # foundation check, checks/completeness.py's foundation-ambiguity
        # check) sees exactly the same shape it already knows how to verify.
        self.skip_first_chains_from_hook = re.compile(
            rf"^skip\s+the\s+first\s+(\d+)\s+chains?\s+from\s+the\s+hook\s*"
            rf"\((?:it|they)\s+(?:doesn't|don't)\s+count\s+as\s+a\s+stitch"
            rf"(?:,[^)]*)?\)$", re.I
        )
        # The same shape under the opposite convention, which loopdreams
        # adopted for every turning chain of 2 or more (hdc/hhdc/dc/tr) --
        # "Skip the first 2 chains from the hook (they count as this row's
        # first stitch)". Deliberately a SEPARATE pattern rather than an
        # optional branch of the one above: the two differ by exactly one
        # stitch in the row's total, and a single regex swallowing both
        # parentheticals would silently pick one answer for the other's rows.
        # The foundation is one chain shorter to match, so the arithmetic only
        # balances if this is told apart from its opposite.
        # The parenthetical may carry a trailing explanation of the arithmetic
        # ("..., so the foundation chain is one shorter than this row's stitch
        # count"). A maker reported the bare form as confusing and was right to:
        # under this convention the chain no longer adds up on its face --
        # 77 chains, skip 2, work 75, yet the row has 76 -- and nothing said
        # where the extra stitch came from. What must stay exact is the
        # counts/doesn't-count phrase itself, since the two differ by one
        # stitch; anything after it is prose for the human.
        self.skip_first_chains_counting = re.compile(
            rf"^skip\s+the\s+first\s+(\d+)\s+chains?\s+from\s+the\s+hook\s*"
            rf"\((?:it\s+counts|they\s+count)\s+as\s+this\s+row's\s+first\s+stitch"
            rf"(?:,[^)]*)?\)$", re.I
        )
        # The second half of the pair above: no ordinal at all (the ordinal
        # position is implied entirely by however many chains the preceding
        # skip_first_chains_from_hook clause skipped), so this can only be
        # resolved together with that clause -- see the post-processing step
        # in tokenize_round. Matched on its own here as a distinct,
        # deliberately incomplete shape (not folded into foundation_into_
        # chain's own regex) so an unpaired occurrence -- e.g. this sentence
        # appearing without its skip clause immediately before it -- still
        # falls through to the normal "unknown" handling instead of being
        # silently misread as starting in some arbitrary chain.
        self.foundation_stitch_in_next_chain = re.compile(
            rf"^({stitch_alt})\s+in\s+the\s+next\s+chain\s+and\s+(?:in\s+)?each\s+ch\s+across$", re.I
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
        # The target noun was a hardcoded literal "st". A round worked back
        # over a previous round of known stitches names that stitch instead --
        # "2 dc in each remaining sc around" (real sample, Basic Motif Round 2,
        # loopdreams builders.ts buildBasicMotifRows) -- which is ordinary
        # crochet prose and no less precise than "st". Widened to the same
        # stitch alternation every other clause here already matches against;
        # the literal "st" stays in the alternation via _NOUN's own members, so
        # every previously-matching phrasing still matches unchanged.
        self.each_st_across = re.compile(
            rf"^\*?(\d*)\s*({stitch_alt})\s+in\s*(?:(?:the\s+)?(?:back|front)\s+loop\s+only\s+of\s+)?"
            rf"each\s+(?:remaining\s+)?(?:{stitch_alt}|sts?)\s+across\b\s*(.*)$", re.I
        )
        self.each_st_around = re.compile(
            rf"^\*?(\d*)\s*({stitch_alt})\s+in\s*(?:(?:the\s+)?(?:back|front)\s+loop\s+only\s+of\s+)?"
            rf"each\s+(?:remaining\s+)?(?:{stitch_alt}|sts?)\s+around\b\s*(.*)$", re.I
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
        # The optional trailing parenthetical is load-bearing, not cosmetic.
        # Without it a descriptive annotation -- "(wc st: insert the hook
        # through the middle of the 'v' ...)", the same shape "(shell made)"
        # takes elsewhere -- makes this pattern miss, and the clause then falls
        # through to each_st_to_marker's broad ".+$" catch-all below and is
        # reported unverifiable. That is exactly the swallowing this pattern
        # was added to prevent (see the comment above each_st_to_marker), just
        # reached via an annotation rather than via ordering. _classify's own
        # strip-and-retry fallback cannot save it either, since that only runs
        # after every pattern has failed and each_st_to_marker matches first.
        # Real case: loopdreams' inline stitch how-tos, 2026-08-31.
        # Deliberately "(...)" rather than each_st_across's looser "(.*)$" --
        # only a parenthetical is tolerated, so genuinely unparsed trailing
        # text still falls through instead of being silently accepted.
        self.each_st_to_last = re.compile(
            rf"^({stitch_alt})\s+in\s+each\s+st\s+to\s+last\s+st\s*(?:\([^)]*\))?$", re.I
        )
        self.side_edge = re.compile(
            rf"^working\s+(\d+)\s+({stitch_alt})\s+per\s+row-?end\s+along\s+(?:each\s+)?side\s+edge$", re.I
        )
        # "<N> <stitch> in (first|next|last) st" -- N copies all worked into ONE shared spot.
        self.cluster_same_spot = re.compile(
            rf"^(\d+)\s+({stitch_alt})\s+(?:all\s+)?in\s+{_TARGET}$", re.I
        )
        # "N <stitch> in (first|next|last) <noun> (turning ch-M counts as
        # first <stitch>[; free text])" -- the SAME turning-chain-counts-as-
        # first-stitch credit as counts_as_chain above, but folded as a
        # TRAILING parenthetical onto the opening stitch clause itself
        # instead of stated as its own separate leading clause. Real
        # phrasing (Shell Stitch half-shell row, loopdreams builders.ts
        # buildHalfShellRowText, post-PR-436, Aug 2026 batch): "2 dc in
        # first sc (turning ch-3 counts as first dc; half shell made)" --
        # the generator can't use a separate leading "Ch 3 (counts as first
        # dc)," clause here (breaks TURNING_CHAIN_ERROR's row-opener
        # recognition in validate-pattern/rules.ts, which needs the row to
        # open directly on a stitch count/abbreviation), so it states the
        # same credit inline instead. Same shape as cluster_same_spot right
        # above (one previous-row anchor, consumes=1) plus a flat +1 bonus
        # produced stitch for the credited chain -- the credited stitch
        # word itself isn't captured/used in the math, same as
        # counts_as_chain's own produces=1 regardless of which stitch is
        # named.
        self.turning_chain_credit = re.compile(
            rf"^(\d+)\s+({stitch_alt})\s+in\s+{_POS}\s+{_NOUN}\s*"
            rf"\(turning\s+ch[\s-]?\d+\s+counts\s+as\s+(?:the\s+)?first\s+(?:{stitch_alt})\s*(?:;[^)]*)?\)$",
            re.I,
        )
        # "sc in the centre dc of the next shell" -- single stitch into a named landmark position.
        self.centre_dc = re.compile(
            rf"^({stitch_alt})\s+in\s+(?:the\s+)?(?:centre|center)\s+dc\s+of\s+(?:the\s+)?(?:next|last)\s+shell$", re.I
        )
        # "fpdc around (post(s) of) next/last (N) st(s)" -- post stitches.
        self.around_post = re.compile(
            rf"^({stitch_alt})\s+around\s+(?:the\s+)?(?:posts?\s+of\s+)?{_POS}\s*(\d+)?\s*{_NOUN}$", re.I
        )
        # "dc in top of ch" / "dc in top of ch-2", and the shaped-row form
        # "2 dc in top of ch" -- an increase worked into the turning chain,
        # which is how a row whose chain counts as a stitch makes its far-edge
        # increase (real sample: triangle shawl, every row).
        self.top_of_chain = re.compile(
            rf"^(?:(\d+)\s+)?({stitch_alt})\s+in\s+top\s+of\s+(?:the\s+)?ch(?:-\d+)?$", re.I)
        # Generic single-instance positional clause: "<stitch> in (first|next|last) st"
        self.simple_positional = re.compile(rf"^({stitch_alt})\s+in\s+{_TARGET}$", re.I)
        # "<stitch> in (the) same st/chain" -- text that means "this stitch
        # shares whatever spot the immediately preceding clause named,"
        # widened from a hardcoded literal "st" to the full _NOUN set (real
        # sample, Sedge Stitch: "Hdc in the next chain, dc in the same
        # chain" -- see tokenize_round's post-processing for why this
        # match is classified provisionally, not with a final consumes/
        # produces value, despite looking identical in shape to simple_
        # positional above).
        self.same_st = re.compile(rf"^({stitch_alt})\s+in\s+(?:the\s+)?same\s+{_MODIFIER}{_NOUN}$", re.I)
        # "<N> <stitch> in (the) same sp" -- N copies into the spot the
        # preceding clause already named. Kept SEPARATE from same_st above
        # rather than folded in as an optional count, because the explicit
        # count removes the very ambiguity same_st's provisional
        # "same_as_previous" machinery exists to resolve: with a count
        # written out there is nothing to read as a turning-chain increase,
        # so this is unconditionally "N stitches, no new previous-round slot
        # consumed". Real phrasing: the opening corner of every round of
        # loopdreams' Granny Square ("Ch 3 (counts as first dc), 2 dc in the
        # same sp, ch 2, 3 dc in the same sp (corner made)") and Basic Motif
        # Border Round 1 ("3 hdc in the same sp").
        self.count_in_same_spot = re.compile(
            rf"^(\d+)\s+({stitch_alt})\s+(?:all\s+)?in\s+(?:the\s+)?same\s+{_MODIFIER}{_NOUN}$", re.I
        )
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
        # "<N> <stitch> in ring" -- the opening round of a magic-ring
        # construction (real samples: Amigurumi Ball/Cone/Limb "6 sc in
        # ring", Coaster "9 hdc in ring" / "11 dc in ring" / "8 sc in ring",
        # Mittens "38 sc in ring"). Unlike a real previous row, the ring
        # itself has no independently-stated stitch count of its own -- the
        # N stated HERE *is* the count, so consumes and produces are both
        # directly N (times the stitch's own ratio for produces), the same
        # "N == N" collapsing already used by literal_next's redundant-
        # restatement case above.
        self.ring_literal = re.compile(rf"^(\d+)\s+({stitch_alt})\s+in\s+ring$", re.I)
        # "<stitch> in 2nd ch from hook and each of next N chs" -- the first
        # side of a two-sided foundation-chain start (real sample:
        # Amigurumi Egg / Basic Oval round 1, loopdreams builders.ts
        # buildOvalRoundRows: "Sc in 2nd ch from hook and each of next 2
        # chs"). Distinct from foundation_into_chain's whole-row "...and
        # each ch across" shape: this one names an explicit count of
        # further chains rather than running to the end of the row, because
        # a second, symmetric clause covers the chain's other side later in
        # the same row (see each_of_next_chs below). Total stitches made:
        # 1 (the ordinal "2nd ch" itself) + N (the "next N chs").
        self.foundation_ordinal_and_next_chs = re.compile(
            rf"^({stitch_alt})\s+in\s+(\d+)(?:st|nd|rd|th)\s+ch\s+from\s+hook\s+and\s+each\s+of\s+next\s+(\d+)\s*chs?$",
            re.I,
        )
        # "<stitch> in the next chain and each of next N chs" -- the SAME
        # two-sided foundation-chain start as foundation_ordinal_and_next_chs
        # above, but paired with a preceding skip_first_chains_from_hook
        # clause instead of an ordinal (see that pattern's own comment) --
        # current, real generator text (Amigurumi Egg/Basic Oval round 1,
        # loopdreams generate-pattern's buildOvalRoundRows, confirmed against
        # a loopdreams batch-test run against production, Aug 1 2026: "Skip
        # the first 1 chain from the hook (it doesn't count as a stitch). Sc
        # in the next chain and each of next 2 chs, ..."). Unlike foundation_
        # into_chain's paired "and in each ch across" shape (see stitch_
        # parser.py's tokenize_round post-processing), this one doesn't need
        # pairing at all: the skipped-chain count only matters for computing
        # a WHOLE-ROW ordinal position, but here the "N chains" span is
        # stated directly and worked into the foundation chain regardless of
        # how many were skipped before it (consumes=0 either way) -- so it
        # classifies standalone, exactly like foundation_ordinal_and_next_chs
        # itself. Total stitches made: 1 (the "next chain" itself) + N.
        self.foundation_next_chain_and_next_chs = re.compile(
            rf"^({stitch_alt})\s+in\s+the\s+next\s+chain\s+and\s+each\s+of\s+next\s+(\d+)\s*chs?$", re.I
        )
        # "<stitch> in each of next N chs" -- the second (opposite) side of
        # the same two-sided foundation-chain start, worked back along the
        # chain's other loop after the "working on the opposite side of the
        # foundation chain" pivot note (_RE_OPPOSITE_SIDE_CHAIN). Same
        # "chs" noun as foundation_ordinal_and_next_chs above; distinct from
        # each_of_position, which is anchored to "sts" only.
        self.each_of_next_chs = re.compile(
            rf"^({stitch_alt})\s+in\s+each\s+of\s+(?:the\s+)?(first|last|next)\s+(\d+)\s*chs?$", re.I
        )
        # "sl st to top of ch 3 to join" -- ends a JOINED round (flat circle/motif
        # construction, real sample: coaster Jul 8 batch -- distinct from the
        # continuous-spiral mittens construction, which never joins at all). A
        # no-op for stitch-count purposes: it closes the round, doesn't add or
        # remove stitches. The sc-variant coaster (same batch) has no counted
        # turning chain to join back to -- its rounds open on a bare stitch
        # instead, so the round closes with "sl st to first sc to join" instead;
        # same no-op, different anchor phrase.
        #
        # The "first <stitch>" anchor used to be a bare module-level [a-z]+
        # instead of the real stitch_alt alternation -- real bug found
        # (loopdreams' "Batch-test regression matrix" CI job, run 33269385156,
        # Aug 2026, the first run after loopdreams_qa's deep cross-check was
        # actually wired into that job -- see loopdreams PR #437/#438): Coaster
        # wc st rounds close with "sl st to first wc st to join", and a
        # single-word [a-z]+ can't span the space in a two-word abbreviation --
        # it matched only as far as "wc", leaving "st to join" unconsumed and
        # the whole clause falling through to "unknown". Built from stitch_alt
        # (the same alternation every other per-pattern clause in this class
        # already matches against) instead, so it works for any known stitch
        # word regardless of how many words it's spelled with -- not just this
        # one two-word case, but also hhdc/bl sc/fl sc/bo and any future
        # custom-compound token, none of which this anchor could have matched
        # either.
        self.sl_st_join = re.compile(
            rf"^sl\s*st\s+to\s+(?:top\s+of\s+ch\s+\d+|first\s+(?:{stitch_alt}))\s+to\s+join$", re.I
        )
        # A round's declared stitch count restated as its own bare parenthetical
        # clause -- "(8 wc st)", "(24 dc)" -- split off by tokenize_round's
        # top-level comma/period split as a standalone clause, distinct from
        # _RE_PAREN_CLUSTER's "(sc, hdc, dc) in next st" shape (a list of
        # DIFFERENT stitches sharing one spot, always followed by "in ...").
        # No-op for stitch-count purposes: it's pure restatement, never new
        # information -- the row's authoritative declared_count is already
        # parsed separately (pattern_parser.py's row_re, or from_pattern_
        # json.py's _with_trailing_count for the JSON-adapter path this
        # actually surfaced on). For single-word abbreviations this
        # restatement is normally stripped as noise before it ever reaches
        # tokenize_round (see pattern_parser.py row_re's own comment on
        # duplicated "(N <abbr>) (N sts)" annotations) -- but that stripping
        # regex only knows a hardcoded sc/hdc/dc/tr/dtr/htr/ttr list, so a
        # multi-word abbreviation like "wc st" (same real bug as sl_st_join
        # above, same CI run) sails through unstripped and needs its own
        # no-op here instead.
        # Widened from a single "(N <stitch>)" tally to a comma-separated LIST
        # of them, with an optional trailing noun phrase per item: a round that
        # leaves chain spaces behind restates all of what it made, not just its
        # stitch total -- "(24 dc, 4 ch-2 corner sps, 4 ch-1 sps)", "(16
        # Clusters, 16 ch-1 sps)" (real samples: loopdreams builders.ts
        # buildGrannySquareRows and buildBasicMotifRows, every round). Still the
        # same pure no-op restatement as the single-tally form -- the row's
        # authoritative declared count is parsed separately -- but as one
        # unmatched clause per round it was the single most common piece of
        # "unrecognized clause" noise across both templates.
        tally = rf"~?\s*\d+\s*(?:ch-?\d+\s+)?(?:corner\s+)?(?:{stitch_alt}|sps?|spaces?|sts?|clusters?)"
        self.trailing_count_restatement = re.compile(
            rf"^\(\s*{tally}(?:\s*,\s*{tally})*\s*\)$", re.I
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
    """Split on separator chars, but never inside ( ) or [ ], and never on a
    "." that's a decimal point (digit immediately before AND after it, real
    sample: loopdreams' "Body measures approximately 19.5 in." length
    checkpoint, Jul 28 batch) rather than a real sentence-ending period --
    real patterns write multi-stitch clusters like "(sc, hdc, dc) in next
    st", which a naive comma split would tear apart, and a naive period
    split would tear "19.5" into "19" + "5"."""
    parts = []
    depth = 0
    buf = []
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
            buf.append(ch)
        elif ch in ")]":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif depth == 0 and ch == "." and i > 0 and i + 1 < len(text) and text[i - 1].isdigit() and text[i + 1].isdigit():
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


_RE_INTO_TOP_OF_CH = re.compile(r"\bin\s+top\s+of\s+(?:the\s+)?ch\b", re.I)


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

    # A row's very first clause being a bare "skip first st" (consumes=1,
    # produces=0, no counted_chain clause ahead of it -- it IS clause 0) is
    # the modern, more concise phrasing for a turning-chain-replaces-the-
    # first-stitch row. The older phrasing stated this explicitly as a
    # leading "Ch N (counts as dc), skip first st, ..." pair -- counted_chain
    # (produces=1) balancing this skip (consumes=1, produces=0) to a wash --
    # but the shorter form relies on the PREVIOUS row's own trailing
    # "Ch N, turn." having already made that chain, so nothing in THIS row's
    # text states it (real sample: Waffle Tote Bag, post-loopdreams#318
    # wording fix, Jul 26 batch -- that PR intentionally dropped the
    # restatement after real tester feedback showed it read as two separate
    # chains, see loopdreams builders.ts's Assembly-area comment). Scoped
    # tightly to the exact "skip first st" phrasing and clause position 0 so
    # it can't reinterpret a real mid-row decrease (e.g. bobble's "*dc in
    # next st, skip next st, ...*", or moss/linen's "skip next st" chain-1-
    # space offset, both of which are never clause 0 and never say "first").
    if (clauses and clauses[0].clause_type == "skip" and clauses[0].consumes == 1
            and clauses[0].produces == 0 and _RE_SKIP_FIRST_ST.match(clauses[0].raw.strip())):
        clauses[0] = replace(clauses[0], produces=1)

    # The same credit, for the same physical chain, on a row that does NOT
    # open with a bare "skip first st". A SHAPED row under the same convention
    # works its first stitch rather than skipping it -- that worked stitch is
    # the near-edge increase, with the turning chain still standing in for the
    # row's first stitch (real sample: triangle shawl, every row -- "Dc in
    # first st, dc in each of next N sts, 2 dc in top of ch"). Nothing in that
    # text mentions the chain, exactly as with the skip phrasing above, so
    # without this the row reads one stitch short on every row of the piece.
    #
    # Detected by the FAR edge instead: a row that works into the top of the
    # previous row's turning chain is necessarily a row whose own chain counts.
    # Credited as a synthetic counted_chain, which is precisely what the older,
    # explicit "Ch N (counts as dc)" phrasing produced -- see the comment above.
    #
    # Guarded against double-crediting: one chain, one credit, whichever of its
    # two tells is present. A waffle row has BOTH (it opens with "skip first
    # st" AND closes into the chain) and must still be credited once, which is
    # why this is an elif.
    # ...and never on top of an explicit one. The older phrasing states the
    # chain outright ("Ch 2 (counts as dc), skip first st, ... dc in top of
    # ch"), which already parses to a counted_chain carrying this exact credit;
    # crediting again would make that row read one stitch too wide.
    elif (clauses
            and not any(c.clause_type == "counted_chain" for c in clauses)
            and any(c.clause_type == "positional_single"
                    and _RE_INTO_TOP_OF_CH.search(c.raw) for c in clauses)):
        clauses.insert(0, StitchClause(
            raw="(turning chain counts as this row's first stitch)",
            clause_type="counted_chain", consumes=0, produces=1))

    # A row opening with "Magic ring" immediately followed by a counted
    # chain ("Ch N (counts as first X)") is the joined-round magic-ring
    # shape (real sample: Coaster HDC/DC round 1, loopdreams builders.ts
    # buildCoasterRows: "Magic ring. Ch 3 (counts as first dc), 11 dc in
    # ring, sl st to top of ch 3 to join."). Everywhere ELSE this same
    # counted_chain clause shape appears, it sits atop a REAL previous
    # round of stitches and correctly consumes=0 (the chain adds a new
    # stitch-equivalent without using up one of the previous round's own
    # stitches -- those are consumed by the row's other clauses instead).
    # Here there is no previous round: the ring itself is exactly as big as
    # this row's own stated stitch count (pattern_parser.py's magic-ring
    # foundation detection sets pattern.foundation_chain to N+1 for this
    # exact shape, folding the counted chain's own implicit stitch into the
    # total) -- so the counted chain has to claim one of the ring's N+1
    # slots itself, or this row's own consumed total could never reach the
    # ring size it's checked against. Scoped tightly to clause position
    # 0/1 (an exact "Magic ring" clause immediately followed by a
    # counted_chain) so it can't reinterpret a real mid-pattern counted
    # chain anywhere else.
    if (len(clauses) > 1 and clauses[0].raw.strip().lower() == "magic ring"
            and clauses[1].clause_type == "counted_chain"):
        clauses[1] = replace(clauses[1], consumes=1)

    # "X in (the) same st/chain" immediately following a clause that itself
    # claimed a real, single previous-row/foundation-chain slot (produced
    # by simple_positional, top_of_chain, stitch_in_ch1_space, or
    # around_post -- all tagged clause_type="positional_single") is case
    # (b) from patterns.same_st's own comment: two DIFFERENT stitches
    # sharing the one spot the preceding clause already paid for, not a
    # turning-chain increase. Reclassify to that non-doubled reading here;
    # everything else (no preceding clause, or preceded by a chain/
    # counted_chain/anything not itself a single real stitch pickup) keeps
    # the original, historically-verified turning-chain-increase doubling,
    # just relabelled to the normal "positional_single" type so downstream
    # consumers (checks/stitch_count.py) never need to know the provisional
    # "same_as_previous" type existed.
    for i, clause in enumerate(clauses):
        if clause.clause_type != "same_as_previous":
            continue
        if i > 0 and clauses[i - 1].clause_type == "positional_single":
            canon, is_compound, c, prod = _stitch_lookup(clause.stitch, custom_compound)
            clauses[i] = replace(
                clause, clause_type="positional_single", consumes=0, produces=prod,
                unverifiable_reason=None if prod is not None else
                f"'{canon}' has no fixed consumes/produces ratio",
            )
        else:
            clauses[i] = replace(clause, clause_type="positional_single")

    # A "Skip the first N chain(s) from the hook (...)" clause that ISN'T
    # immediately followed by the matching "<stitch> in the next chain and
    # in each ch across" shape doesn't get folded into a single
    # foundation_into_chain clause by the pairing step below -- real
    # construction found on a real sample (Sedge Stitch, loopdreams commit
    # "Fix Sedge Stitch construction", Aug 2026): "Skip the first 1 chain
    # from the hook (...). Hdc in the next chain, dc in the same chain.
    # ..." opens with a real 2-stitch cluster, not the whole-row "...and
    # each ch across" shape, so no merge happens and this clause stays
    # standalone. It's left at consumes=0 in patterns.skip_first_chains_
    # from_hook's own match arm ONLY because the paired case's dedicated
    # _check_foundation_into_chain check (checks/stitch_count.py) never
    # reads this clause's consumes at all -- it reads the MERGED clause's
    # own explicit_count instead. When nothing merges it, the generic
    # zone-sum-based checks (_check_repeat_group, _check_flat_sequence) DO
    # tally every clause's consumes across the whole row, and silently
    # leaving this at 0 would under-count the foundation chain by exactly
    # the skipped amount -- reproducing the same false stitch-count-
    # mismatch this whole fix is for. Bump it to the real skipped count
    # here, but ONLY when unpaired, so the paired case's own tested value
    # (0 -- see test_stitch_parser.py's TestSkipFirstChainsFoundationClause)
    # is untouched. Checked against the ORIGINAL, pre-pairing clause_type
    # of the following clause -- this loop must run before the pairing
    # loop below mutates it.
    for i, clause in enumerate(clauses):
        if clause.clause_type != "skip_first_chains_from_hook":
            continue
        paired = (i + 1 < len(clauses) and clauses[i + 1].clause_type == "foundation_stitch_in_next_chain")
        if not paired:
            clauses[i] = replace(clause, consumes=clause.explicit_count)

    # Pair up the split foundation-start shape (see patterns.skip_first_
    # chains_from_hook's own comment): "Skip the first N chain(s) from the
    # hook (...)." immediately followed by "<stitch> in the next chain and
    # in each ch across." is semantically identical to the single-clause
    # "<stitch> in (N+1)th ch from hook and in each ch across" that
    # foundation_into_chain already matches -- skipping N chains and
    # starting in the next one IS starting in the (N+1)th chain from the
    # hook. Fold the pair into that same clause_type here so every
    # downstream consumer (checks/stitch_count.py's _check_foundation_into_
    # chain, checks/completeness.py's foundation-ambiguity check) verifies
    # it exactly as it already verifies the ordinal phrasing, with no
    # separate code path to keep in sync.
    for i in range(len(clauses) - 1):
        if (clauses[i].clause_type == "skip_first_chains_from_hook"
                and clauses[i + 1].clause_type == "foundation_stitch_in_next_chain"):
            skipped = clauses[i].explicit_count
            clauses[i + 1] = replace(
                clauses[i + 1], clause_type="foundation_into_chain",
                explicit_count=skipped + 1, consumes=None, produces=None, unverifiable_reason=None,
                chain_counts_as_stitch=clauses[i].chain_counts_as_stitch,
            )

    return clauses


def _score_group_members(inner: str, patterns: _Patterns, custom_compound: frozenset):
    """Score the members of a group worked into ONE shared spot -- the
    "[3 dc, ch 2, 3 dc]" of a corner increase.

    Members are scored individually rather than through tokenize_round,
    because inside a group they are written as bare "<N> <stitch>" fragments
    with no positional phrase of their own (the group's single shared target
    supplies it), and no whole-clause shape in this module matches that:
    bare_stitch takes no leading count, and every counted shape requires an
    "in ..." phrase. Returns (member clauses, total produced) with total None
    if any member's own ratio is unknown -- an unknown member has to make the
    whole group unverifiable rather than silently undercount it.
    """
    members, total = [], 0
    for raw in inner.split(","):
        frag = raw.strip()
        if not frag:
            continue
        if _RE_CHAIN.match(frag):
            # The ch-2 that opens the corner space: real, but not fabric this
            # round counts -- 0 produced, same as a standalone chain clause.
            members.append(StitchClause(raw=frag, clause_type="chain", consumes=0, produces=0))
            continue
        m = re.match(rf"^(\d*)\s*({'|'.join(re.escape(w) for w in sorted(_BASE_STITCH_WORDS | custom_compound, key=len, reverse=True))})$", frag, re.I)
        if m:
            n = int(m.group(1)) if m.group(1) else 1
            canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
            members.append(StitchClause(raw=frag, stitch=canon, clause_type="literal_count",
                                        explicit_count=n, consumes=0,
                                        produces=None if prod is None else n * prod,
                                        is_compound=is_compound))
            if prod is None:
                total = None
            elif total is not None:
                total += n * prod
            continue
        members.append(_classify(frag, patterns, custom_compound))
        if members[-1].produces is None:
            total = None
        elif total is not None:
            total += members[-1].produces
    return members, total


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

    if _RE_FASTEN_OFF_COLOUR.match(p) or _RE_SL_ST_TRAVEL.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    if _RE_JOIN.match(p) or _RE_SETUP.match(p):
        return StitchClause(raw=raw_part, clause_type="join", consumes=0, produces=0)

    if _RE_NOTE.match(p) or _RE_ROW_TYPE_LABEL.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    if (_RE_PLACE_MARKER.match(p) or _RE_INLINE_COLOUR_CHANGE.match(p) or _RE_WORKING_LAST_INTO_CH.match(p)
            or _RE_BODY_LENGTH_CHECKPOINT.match(p) or _RE_DO_NOT_JOIN_OR_TURN.match(p)
            or _RE_OPPOSITE_SIDE_CHAIN.match(p) or _RE_STUFF_NOTE.match(p)):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    if _RE_MAGIC_RING.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

    if patterns.sl_st_join.match(p):
        return StitchClause(raw=raw_part, clause_type="join", consumes=0, produces=0)

    if patterns.trailing_count_restatement.match(p):
        return StitchClause(raw=raw_part, clause_type="note", consumes=0, produces=0)

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

    m = _RE_MORE_TIMES.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="repeat_close", explicit_count=int(m.group(1)),
                             unverifiable_reason=f"repeat-close modifier: '{m.group(0)}'")

    m = patterns.foundation_into_chain.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="foundation_into_chain",
                             explicit_count=int(m.group(2)), is_compound=is_compound)

    # See patterns.skip_first_chains_from_hook's own comment: the informational
    # first half of the split "Skip the first N chain(s) from the hook (...).
    # <stitch> in the next chain and in each ch across." shape. consumes=0/
    # produces=0 -- it's a skip, not a stitch -- paired with the following
    # clause by tokenize_round's post-processing step.
    m = patterns.skip_first_chains_from_hook.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="skip_first_chains_from_hook",
                             explicit_count=int(m.group(1)), consumes=0, produces=0)

    # Same clause, opposite convention -- the skipped chains ARE the row's
    # first stitch, so this one produces 1 where the above produces 0. Folded
    # into foundation_into_chain by the same post-processing step, carrying
    # chain_counts_as_stitch so the count check can add it back.
    m = patterns.skip_first_chains_counting.match(p)
    if m:
        return StitchClause(raw=raw_part, clause_type="skip_first_chains_from_hook",
                             explicit_count=int(m.group(1)), consumes=0, produces=1,
                             chain_counts_as_stitch=True)

    # See patterns.foundation_stitch_in_next_chain's own comment: the second
    # half of the same split shape, left unresolved (consumes/produces=None)
    # unless tokenize_round's post-processing finds an immediately preceding
    # skip_first_chains_from_hook clause to pair it with.
    m = patterns.foundation_stitch_in_next_chain.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        return StitchClause(raw=raw_part, stitch=canon, clause_type="foundation_stitch_in_next_chain",
                             is_compound=is_compound,
                             unverifiable_reason="'in the next chain' with no preceding 'skip the first N "
                                                  "chains from the hook' clause to establish the starting position")

    # "<stitch> in 2nd ch from hook and each of next N chs" -- one side of a
    # two-sided oval/egg foundation-chain start (see patterns.foundation_
    # ordinal_and_next_chs's own comment). Checked before foundation_
    # ordinal_single below, whose own "...from hook$" shape would otherwise
    # never match this anyway (extra trailing text after "hook").
    m = patterns.foundation_ordinal_and_next_chs.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        n = 1 + int(m.group(3))  # the ordinal "Nth ch" stitch itself, plus the N further chs
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n, consumes=0, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    # "<stitch> in the next chain and each of next N chs" -- the same shape
    # as foundation_ordinal_and_next_chs above, paired with a preceding
    # skip_first_chains_from_hook clause instead of an ordinal (see patterns.
    # foundation_next_chain_and_next_chs's own comment for why no pairing
    # step is needed here, unlike foundation_into_chain's paired form).
    m = patterns.foundation_next_chain_and_next_chs.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        n = 1 + int(m.group(2))  # the "next chain" itself, plus the N further chs
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n, consumes=0, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

    # "<stitch> in each of next N chs" -- the opposite side of the same
    # two-sided foundation-chain start (see patterns.each_of_next_chs's own
    # comment). consumes=0: worked into the foundation chain, not a
    # previous round of real stitches.
    m = patterns.each_of_next_chs.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        n = int(m.group(3))
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n, consumes=0, produces=produces, is_compound=is_compound,
                             unverifiable_reason=None if prod is not None else
                             f"'{canon}' has no fixed consumes/produces ratio")

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

    # "<N> <stitch> in ring" -- the opening round of a magic-ring
    # construction (see patterns.ring_literal's own comment). The stated N
    # directly is both the consumed "ring size" and (via the stitch's own
    # ratio) the produced stitch count -- there's no separate previous-row
    # count to cross-check it against.
    m = patterns.ring_literal.match(p)
    if m:
        n = int(m.group(1))
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        produces = (prod * n) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="literal_count",
                             explicit_count=n, consumes=n, produces=produces, is_compound=is_compound,
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

    # "N <stitch> in (first|next|last) <noun> (turning ch-M counts as first
    # <stitch>; ...)" -- same shape as cluster_same_spot immediately above,
    # plus a flat +1 bonus stitch credited from the previous row's own
    # trailing turning chain (see patterns.turning_chain_credit's own
    # comment for why this can't just be a separate leading counted_chain
    # clause here). Reuses clause_type="cluster_same_spot" -- structurally,
    # and for every downstream consumer's purposes, it IS that shape, just
    # with one bonus produced stitch.
    m = patterns.turning_chain_credit.match(p)
    if m:
        n = int(m.group(1))
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        produces = (prod * n) + 1 if prod is not None else None
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

    # Checked AFTER _RE_PAREN_CLUSTER above: that shape is the narrower one
    # (a letters-only list of plain abbreviations, "(sc, hdc, dc) in next
    # chain") and names its members in the clause's own `stitch` field, which
    # callers rely on. This is the general fallback for groups it can't take:
    # square brackets, and members carrying their own counts or a chain.
    m = _RE_GROUP_INTO_SPOT.match(p)
    if m:
        sub, total = _score_group_members(m.group(1), patterns, custom_compound)
        # "in the same sp" shares the spot the preceding clause already paid
        # for; "in next/first/last ..." claims one of its own.
        consumes = 0 if _RE_GROUP_INTO_SAME_SPOT.match(p) else 1
        # stitch is left None deliberately: the group is not an abbreviation,
        # and completeness.py's abbreviation check reads this field. Its
        # members reach that check through sub_clauses instead.
        return StitchClause(
            raw=raw_part, clause_type="cluster_same_spot", sub_clauses=sub,
            explicit_count=len(sub), consumes=consumes, produces=total,
            is_compound=total is None,
            unverifiable_reason=None if total is not None else
            "a stitch in this group worked into one spot has no fixed consumes/produces ratio",
        )

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
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        # "in top of (the) ch" names exactly ONE target chain-top, regardless
        # of which stitch is worked there -- and regardless of how many
        # stitches are worked INTO it, which is what the optional leading
        # multiple changes. "2 dc in top of ch" still consumes one chain-top;
        # it just produces two stitches there (a far-edge increase).
        n = int(m.group(1)) if m.group(1) else 1
        consumes = c if c is not None else 1
        return StitchClause(raw=raw_part, stitch=canon, clause_type="positional_single",
                             explicit_count=n if n > 1 else None,
                             consumes=consumes, produces=(prod * n) if prod is not None else None,
                             is_compound=is_compound,
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

    m = patterns.count_in_same_spot.match(p)
    if m:
        n = int(m.group(1))
        canon, is_compound, c, prod = _stitch_lookup(m.group(2), custom_compound)
        # produces is exact (N copies of a known stitch); consumes is left
        # UNKNOWN on purpose. The clause itself claims no new previous-round
        # slot -- it shares the one the preceding clause named -- but that
        # preceding clause is routinely a "Sl st to corner sp." positioning
        # move or a bare turning chain, neither of which claims a slot
        # either, so scoring this 0 leaves the round under-consuming and the
        # repeat resolver then divides the previous round's total by the
        # wrong unit. Measured, not assumed: scoring it 0 turned both of
        # LoopDreams' Granny Square corner rounds into confident stitch-count
        # MISMATCH errors against counts that are in fact correct (Round 2
        # "producing 78 sts total, but the pattern declares 24"). A round
        # worked into corner spaces needs a consumption model this checker
        # does not have, so per ARCHITECTURE.md it stays unverifiable rather
        # than guessed -- the gain here is that the row now says which clause
        # and why, instead of reporting the text as unrecognized.
        return StitchClause(raw=raw_part, stitch=canon, clause_type="cluster_same_spot",
                             explicit_count=n, consumes=None,
                             produces=None if prod is None else n * prod,
                             is_compound=is_compound,
                             unverifiable_reason=(
                                 f"'{m.group(0)}' works into the spot the preceding clause named; how many "
                                 f"previous-round stitches or spaces that spot accounts for isn't stated, so "
                                 f"the round's consumption can't be resolved from the text alone"
                             ))

    m = patterns.same_st.match(p)
    if m:
        canon, is_compound, c, prod = _stitch_lookup(m.group(1), custom_compound)
        # "X in same st/chain" is genuinely ambiguous out of context -- it
        # has TWO different real meanings depending on what immediately
        # precedes it, and the text alone can't tell them apart:
        #
        # (a) Hand-verified against the real sample (coaster, Jul 8 batch,
        # rounds 1-3): the preceding turning chain there is a BARE, un-
        # counted "Ch 3" (produces=0 on its own) -- the "counts as first
        # dc" convention stated once in the Foundation line carries
        # forward implicitly, rather than being restated on every round.
        # So "dc in same st" alone has to represent the FULL 2-stitch
        # increase at that position: consumes=1 (the one real previous-
        # round stitch the chain+this dc together replace), produces=2
        # (the implicit chain-stitch plus this explicit one). Confirmed by
        # testing all three increase rounds' declared counts (12->24,
        # 24->36, 36->48) against this exact model -- all resolve exactly.
        #
        # (b) Real sample (Sedge Stitch, loopdreams commit "Fix Sedge
        # Stitch construction", Aug 2026): "Hdc in the next chain, dc in
        # the same chain" -- a genuinely different idiom where TWO
        # DIFFERENT stitches share one real target (no turning-chain
        # increase involved at all): the immediately preceding clause
        # ("Hdc in the next chain") already claimed and paid for that one
        # slot, so this clause adds no further consumption and produces
        # only its own plain stitch -- consumes=0, produces=prod (not
        # doubled).
        #
        # Provisionally tagged "same_as_previous" (not "positional_single"
        # directly) with case (a)'s values, the historically-verified
        # default -- tokenize_round's post-processing below looks at what
        # actually precedes this clause and reclassifies to case (b) only
        # when that's a real single-stitch positional clause, leaving case
        # (a) (preceded by a bare/counted turning chain, or nothing at all)
        # untouched.
        produces = (prod * 2) if prod is not None else None
        return StitchClause(raw=raw_part, stitch=canon, clause_type="same_as_previous",
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
