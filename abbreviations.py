"""
US/UK crochet abbreviation tables and basic stitch math.

Decisions (see ARCHITECTURE.md):
- Only genuinely unambiguous abbreviations are used as proof of US vs UK
  convention: US_ONLY and UK_ONLY below. Bare dc/tr/dtr/dc2tog/tr2tog exist
  in both systems with DIFFERENT meanings (US dc == UK tr, etc.) and are
  deliberately NOT used as standalone proof of mixing -- using them that
  way would produce false positives any time a pattern just legitimately
  uses dc in a self-consistently-US (or self-consistently-UK) pattern.
- STITCH_MATH covers simple stitches with a fixed, universal consumes/
  produces ratio per instance (1 worked stitch consumes N previous-row
  stitches and produces M current-row stitches).
- COMPOUND_STITCHES are named/decorative stitches (shell, cluster, popcorn,
  puff, bobble, etc.) that have NO fixed universal consumes/produces ratio
  -- it depends entirely on how the individual pattern defines them (e.g.
  "shell = 5 dc in same st, skip 2 sts" vs "shell = 3 dc"). These can only
  be checked if the pattern itself defines the construction somewhere
  (abbreviation key, a "Special Stitches" note, or inline). If undefined,
  the stitch-count checker must flag rows using them as unverifiable
  rather than guess at a ratio.
"""

# Unambiguous US-only abbreviations (proof of US convention if present)
US_ONLY = {"sc", "hdc", "sc2tog", "hdc2tog"}

# Unambiguous UK-only abbreviations (proof of UK convention if present)
UK_ONLY = {"htr", "ttr", "htr2tog", "dtr2tog"}

# Exist in both systems with DIFFERENT meanings -- never used alone as proof
AMBIGUOUS_BOTH_SYSTEMS = {"dc", "tr", "dtr", "dc2tog", "tr2tog"}

# Neutral abbreviations -- same meaning/spelling in both systems, never
# diagnostic of US vs UK either way.
NEUTRAL = {"ch", "sl st", "rep", "rs", "ws", "fo", "mr", "fpdc", "bpdc", "inc", "dec", "st", "sts"}

# Simple stitches: (stitches consumed from previous row, stitches produced
# in current row) for ONE instance of the stitch worked into ONE previous
# stitch. inc/dec are themselves already net operations.
STITCH_MATH = {
    # Real sample (scarf-mossribbed, Jul 15 batch): "sl st" used as the
    # PRIMARY working stitch of an entire ribbing section (worked in the
    # back loop only, row after row -- a real, well-defined 1:1 stitch),
    # not just its previous role as a no-op round-closing join marker
    # ("sl st to join", handled separately by _RE_SL_ST_JOIN and never
    # reaching this table). "sl st" was only ever in abbreviations.NEUTRAL
    # (for US/UK terminology detection) with no fixed ratio, so every row
    # using it as a real stitch came back "no fixed consumes/produces
    # ratio" -- a real gap, not a join-clause conflict, since the join
    # patterns are matched first and never fall through to this lookup.
    "sl st": (1, 1),
    "sc": (1, 1),
    "hdc": (1, 1),
    "dc": (1, 1),
    "tr": (1, 1),
    "dtr": (1, 1),
    "htr": (1, 1),
    "ttr": (1, 1),
    "fpdc": (1, 1),
    "bpdc": (1, 1),
    "inc": (1, 2),
    "dec": (2, 1),
    "sc2tog": (2, 1),
    "hdc2tog": (2, 1),
    "dc2tog": (2, 1),
    "tr2tog": (2, 1),
    "htr2tog": (2, 1),
    "dtr2tog": (2, 1),
    # Loop-variant stitches (LoopDreams' Stitch_Library skill-tier expansion,
    # loopdreams repo) -- each is a SINGLE insertion-point variant of an
    # existing base stitch, not a compound/decorative stitch with a
    # pattern-defined ratio: bl sc/fl sc insert under one loop only (back or
    # front) instead of both, same as a plain sc; hhdc inserts under the
    # front loop and pulls through only the first loop before finishing like
    # a regular hdc; wc st (waistcoat stitch) inserts into the "v" post
    # below rather than the top two loops. All still consume exactly 1
    # previous-row stitch and produce exactly 1 current-row stitch per
    # instance -- these were simply never taught to this tool, so every
    # real pattern using one came back as a mass of "unrecognized clause"
    # findings instead of a real opinion (confirmed via loopdreams'
    # scripts/metric-sweep.ts + qa-triage.ts output against real production
    # patterns).
    "bl sc": (1, 1),
    "fl sc": (1, 1),
    "hhdc": (1, 1),
    "wc st": (1, 1),
    # "bo" -- LoopDreams' own Tote Bag bobble-stitch abbreviation (real
    # sample: Tote Bag advanced, Jul 29 batch: "*bo in next st, sc in next
    # st; rep from * to last st, sc in last st."). Unlike the pattern-
    # defined compound words below (shell/cluster/moss/etc., whose actual
    # construction varies pattern to pattern and must be verified against
    # that pattern's own definition), this is the generator's OWN hardcoded
    # template (loopdreams builders.ts buildToteBagRows' isBobble branch) --
    # always exactly "5 incomplete dc pulled through together in the same
    # st", i.e. one worked stitch replacing one previous-row stitch,
    # regardless of which pattern it appears in. Same category as bl sc/
    # fl sc/hhdc/wc st above: a fixed single-insertion-point variant, not a
    # genuinely pattern-configurable decorative stitch -- and the generator
    # never actually emits an abbreviation-key entry defining "bo" anywhere
    # in the pattern text, so the custom_compound_tokens() per-pattern path
    # (which needs such a definition to recognize a token at all) can never
    # catch this one; it has to be taught here instead, the same as sc/dc.
    "bo": (1, 1),
}

# Named/compound decorative stitches with no fixed universal ratio.
# Presence of one of these tokens (or a custom abbreviation key entry whose
# DEFINITION text contains one of these words) marks a stitch as needing an
# explicit construction definition before stitch-count math can be verified.
# "moss"/"sedge" added from a real sample (shawl, Jul 8 batch): unlike
# every earlier moss/sedge stitch sample (throw blanket), which always
# spelled out the sc/ch1 or sc+hdc+dc construction literally in the row
# text, this one uses "MOSS"/"SEDGE" directly as a stitch TOKEN in row
# instructions ("2 MOSS in first st, MOSS in next st, ..."), the same
# shorthand-token style already used for shell/bobble/etc. Without this,
# every clause using the token fails to match ANY clause shape at all
# (the word isn't in the stitch-word alternation), producing "unrecognized
# clause" noise on every single row instead of the correct "compound
# stitch, no fixed ratio" completeness flag.
COMPOUND_STITCH_WORDS = {
    "shell", "sh st", "cluster", "cl", "popcorn", "pc", "bobble", "puff",
    "v-st", "v st", "picot", "star st", "moss", "sedge",
}

KNOWN_SIMPLE_TOKENS = set(STITCH_MATH.keys())
ALL_KNOWN_TOKENS = KNOWN_SIMPLE_TOKENS | US_ONLY | UK_ONLY | AMBIGUOUS_BOTH_SYSTEMS | NEUTRAL

import re as _re

_COMPOUND_WORD_RE = _re.compile(
    r"\b(" + "|".join(_re.escape(w) for w in COMPOUND_STITCH_WORDS) + r")\b", _re.I
)


def custom_compound_tokens(abbr_key: dict) -> frozenset:
    """A pattern can define its OWN short abbreviation for a named/decorative
    stitch (e.g. 'bo = bobble (5 incomplete dc in same st, ...)') instead of
    writing the compound-stitch word itself in the instructions. Neither the
    stitch tokenizer nor the completeness checks previously had any way to
    recognize that custom token as a stitch at all unless we look at what
    its OWN definition text names. Real gap found on a real sample (bobble
    tote bag, Jun 29 batch): 'bo' was used throughout the body but never
    matched any known stitch word, so every row using it silently became
    "unrecognized clause" noise instead of a proper "compound stitch, no
    fixed ratio" flag -- and the completeness check never saw it as a
    stitch at all, so it couldn't even confirm the construction was
    (correctly) stated.

    Returns the set of abbreviation-key tokens (already lowercased) whose
    definition text names one of COMPOUND_STITCH_WORDS, so callers can treat
    that token exactly like a hardcoded compound-stitch word: no fixed
    consumes/produces ratio, construction-required per the digit heuristic.
    Tokens that are already a recognized simple/system/neutral abbreviation
    are skipped -- a pattern redefining e.g. 'sc' is not this case.
    """
    found = set()
    for abbr, definition in abbr_key.items():
        if abbr in ALL_KNOWN_TOKENS:
            continue
        if _COMPOUND_WORD_RE.search(definition):
            found.add(abbr)
    return frozenset(found)
