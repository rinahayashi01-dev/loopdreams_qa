"""
Crochet abbreviation reference data.

Two things live here:
1. Per-stitch "math" — how many stitches a stitch operation consumes from
   the previous round/row, and how many it produces — used by the stitch
   count checker.
2. The US/UK term ladder — used by the terminology checker.

IMPORTANT ASYMMETRY, read before changing this file:
Several abbreviations exist in BOTH systems but mean different stitches
(e.g. "dc" is single crochet's UK name AND US double crochet's own name).
Those are *ambiguous* on their own and are deliberately left out of the
"unambiguous" marker sets below. Only abbreviations that exist in exactly
one system are safe to use as proof that a pattern is using that system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StitchInfo:
    abbr: str
    name: str
    consumes: int  # stitches consumed from the previous round/row, per occurrence
    produces: int  # stitches produced, per occurrence
    counts_toward_total: bool = True  # turning chains / slip stitches usually don't


# Stitch math is the same regardless of what a stitch is *called* — a US "sc"
# and a UK "dc" both consume 1 and produce 1, they're the same physical stitch.
# So we key this by a canonical stitch "shape", and let the term tables below
# map abbreviations (US or UK) onto a shape.
STITCH_MATH = {
    "single_tall":   StitchInfo("", "single crochet height", 1, 1),
    "half_double":   StitchInfo("", "half double crochet height", 1, 1),
    "double_tall":   StitchInfo("", "double crochet height", 1, 1),
    "treble":        StitchInfo("", "treble crochet height", 1, 1),
    "double_treble": StitchInfo("", "double treble height", 1, 1),
    "post_stitch":   StitchInfo("", "post stitch", 1, 1),
    "inc":           StitchInfo("inc", "increase", 1, 2),
    "dec":           StitchInfo("dec", "decrease", 2, 1),
    "skip":          StitchInfo("skip", "skipped stitch", 1, 0),
    "ch":            StitchInfo("ch", "chain", 0, 1, counts_toward_total=False),
    "sl_st":         StitchInfo("sl st", "slip stitch", 1, 1, counts_toward_total=False),
    "no_op":         StitchInfo("", "marker / no stitch math", 0, 0, counts_toward_total=False),
}

# US terms -> canonical shape
US_TERMS = {
    "sc": "single_tall",
    "hdc": "half_double",
    "dc": "double_tall",
    "tr": "treble",
    "dtr": "double_treble",
    "fpdc": "post_stitch",
    "bpdc": "post_stitch",
    "sc2tog": "dec",
    "hdc2tog": "dec",
    "dc2tog": "dec",
    "tr2tog": "dec",
    "inc": "inc",
    "dec": "dec",
    "ch": "ch",
    "sl st": "sl_st",
    "mr": "no_op",
    "fo": "no_op",
}

# UK terms -> canonical shape
UK_TERMS = {
    "dc": "single_tall",     # UK dc = US sc
    "htr": "half_double",    # UK htr = US hdc
    "tr": "double_tall",     # UK tr = US dc
    "dtr": "treble",         # UK dtr = US tr
    "ttr": "double_treble",  # UK ttr = US dtr
    "fpdc": "post_stitch",
    "bpdc": "post_stitch",
    "dc2tog": "dec",
    "htr2tog": "dec",
    "tr2tog": "dec",
    "dtr2tog": "dec",
    "inc": "inc",
    "dec": "dec",
    "ch": "ch",
    "sl st": "sl_st",
    "mr": "no_op",
    "fo": "no_op",
}

# Terms that exist in exactly one system — safe to use as proof of which
# convention a pattern is actually using. See module docstring for why "dc",
# "tr", "dtr", "dc2tog", "tr2tog" are deliberately excluded.
UNAMBIGUOUS_US_ONLY = {"sc", "hdc", "sc2tog", "hdc2tog"}
UNAMBIGUOUS_UK_ONLY = {"htr", "ttr", "htr2tog", "dtr2tog"}

# All known abbreviations across both systems, for tokenizing round/row text.
ALL_KNOWN_TERMS = sorted(set(US_TERMS) | set(UK_TERMS), key=len, reverse=True)

# Terms whose stitch math doesn't depend on system (used identically, same meaning).
SHARED_TERMS = {"ch", "sl st", "inc", "dec", "mr", "fo", "fpdc", "bpdc"}


def shape_for_term(term: str, system: str) -> str | None:
    """Look up the canonical stitch shape for an abbreviation under a given
    system ("US" or "UK"). Falls back to checking the other system's table
    if not found, since shared terms (ch, sl st, inc, dec...) are identical
    either way."""
    term = term.lower()
    table = US_TERMS if system == "US" else UK_TERMS
    if term in table:
        return table[term]
    other = UK_TERMS if system == "US" else US_TERMS
    return other.get(term)


def stitch_info_for_term(term: str, system: str) -> StitchInfo | None:
    shape = shape_for_term(term, system)
    if shape is None:
        return None
    return STITCH_MATH[shape]
