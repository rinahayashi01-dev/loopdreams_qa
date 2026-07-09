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
