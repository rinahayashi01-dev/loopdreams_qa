"""
Verified reference constructions for specific NAMED stitches, sourced from
authoritative published patterns/tutorials -- not derivable from pure
stitch-count math. A pattern can be perfectly self-consistent
arithmetically while still deviating from the well-known, canonical
construction of the stitch it claims to be (LoopDreams can compensate a
"wrong" chain-skip with a matching stitch-count elsewhere in the row,
producing internally clean math that still isn't the real named stitch).

Deliberately kept small and only added to when a real sample surfaces a
real, human-verified case -- like the linen/moss cross-variant check
(cross_variant.py), this trades broad coverage for avoiding false
positives against legitimate variants of the same general stitch family.
Do NOT add a stitch here speculatively; only after confirming against an
actual authoritative source, the way the entry below was confirmed
against Bella Coco's own published pattern text (not just a video
paraphrase -- see ARCHITECTURE.md for how the first attempt at this, based
on a recalled video description, had its own math error).

First entry: Waffle Stitch. Found via a real QA case (tote bag, Jul 4
batch): LoopDreams' generated Row 1 used "4th ch from hook" (skip 3), but
the canonical construction -- verified against
https://blog.bellacococrochet.com/waffle-stitch/ (UK terms; translated
UK tr -> US dc, UK FPtr -> US FPdc) -- skips only 2 chains ("3rd ch from
hook"), and requires a foundation chain that's a multiple of 3, plus 2.

Second entry: Sedge Stitch. Added the same day LoopDreams' own Sedge
construction got caught (twice) as wrong by a real tester's hands-on
attempt against Daisy Farm Crafts' "Crochet Sedge Stitch"
(https://www.youtube.com/watch?v=aQmLHCVQ5F8) -- this entry exists so a
future regression of the same kind gets caught automatically instead of
needing another real crocheter to find it by hand. Sedge's Row 1 phrases
its skip as "Skip the first N chain(s) from the hook" (clause type
skip_first_chains_from_hook, explicit_count IS the skip count) rather
than waffle's ordinal "Nth ch from hook" (clause type
foundation_into_chain, explicit_count is the ordinal position, one more
than the skip count) -- check() below handles both shapes.
"""
import re

from ..models import Issue

KNOWN_CONSTRUCTIONS = {
    "waffle stitch": {
        "source": "Bella Coco, https://blog.bellacococrochet.com/waffle-stitch/ "
                   "(UK terms, translated: tr->dc, FPtr->FPdc)",
        "row1_skip": 2,     # "3rd ch from hook"
        "multiple_of": 3,   # foundation chain must be (multiple_of * n) + plus
        "plus": 2,
    },
    "sedge stitch": {
        "source": "Daisy Farm Crafts, https://www.youtube.com/watch?v=aQmLHCVQ5F8",
        "row1_skip": 1,     # "Skip the first 1 chain from the hook"
        "multiple_of": 3,   # foundation chain count == stitch count exactly (see LoopDreams' own builders.ts comment)
        "plus": 0,
    },
}


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _stitch_guide_name(pattern):
    sg = next((s for s in pattern.sections if s.name == "stitch_guide"), None)
    if not sg:
        return None
    m = re.search(r"^([A-Z][A-Za-z ]{1,40}?)\s+Stitch\b", sg.raw_text, re.M)
    return f"{m.group(1).strip().lower()} stitch" if m else None


def check(pattern) -> list:
    name = _stitch_guide_name(pattern)
    if name not in KNOWN_CONSTRUCTIONS:
        return []
    ref = KNOWN_CONSTRUCTIONS[name]
    issues = []

    row1 = next((r for r in pattern.rows if r.row_start == 1), None)
    row1_clauses = row1.clauses if row1 else []

    # Two different phrasings for "how many chains does Row 1 skip before its
    # first real stitch", each from a different clause type -- see this
    # module's own docstring (Sedge Stitch entry) for why both exist.
    foundation_clause = next(
        (c for c in row1_clauses if c.clause_type == "foundation_into_chain"), None,
    )
    skip_clause = next(
        (c for c in row1_clauses if c.clause_type == "skip_first_chains_from_hook"), None,
    )

    actual_skip = None
    skip_phrase = None
    if foundation_clause is not None and foundation_clause.explicit_count is not None:
        # Ordinal style ("3rd ch from hook") -- explicit_count is the ordinal
        # position, one more than the actual skip count.
        actual_skip = foundation_clause.explicit_count - 1
        skip_phrase = f"'{_ordinal(foundation_clause.explicit_count)} ch from hook'"
    elif skip_clause is not None and skip_clause.explicit_count is not None:
        # Explicit-count style ("Skip the first N chain(s) from the hook") --
        # explicit_count already IS the skip count, no ordinal offset.
        actual_skip = skip_clause.explicit_count
        skip_phrase = f"'skip the first {actual_skip} chain(s) from the hook'"

    if actual_skip is not None and actual_skip != ref["row1_skip"]:
        issues.append(Issue(
            category="completeness", severity="warning", location="Row 1",
            message=(
                f"Row 1 skips {actual_skip} chain(s) before the first stitch ({skip_phrase}), "
                f"but the verified construction for '{name.title()}' ({ref['source']}) skips "
                f"{ref['row1_skip']} chain(s). The row's own stitch-count math may still be "
                f"internally consistent with a compensating foundation-chain length elsewhere, "
                f"but this deviates from the named stitch's canonical construction -- worth "
                f"confirming against source before shipping."
            ),
        ))

    if pattern.foundation_chain is not None:
        remainder = (pattern.foundation_chain - ref["plus"]) % ref["multiple_of"]
        if remainder != 0:
            lower = pattern.foundation_chain - remainder
            higher = lower + ref["multiple_of"]
            issues.append(Issue(
                category="completeness", severity="warning", location="Foundation",
                message=(
                    f"Foundation chain of {pattern.foundation_chain} doesn't satisfy '{name.title()}''s "
                    f"required stitch multiple (a multiple of {ref['multiple_of']}, plus {ref['plus']}, "
                    f"per {ref['source']}) -- nearest valid chain counts are {lower} or {higher}."
                ),
            ))

    return issues
