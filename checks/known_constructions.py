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
    foundation_clause = next(
        (c for c in row1.clauses if c.clause_type == "foundation_into_chain"),
        None,
    ) if row1 else None
    if foundation_clause is not None and foundation_clause.explicit_count is not None:
        actual_skip = foundation_clause.explicit_count - 1
        if actual_skip != ref["row1_skip"]:
            issues.append(Issue(
                category="completeness", severity="warning", location="Row 1",
                message=(
                    f"Row 1 skips {actual_skip} chain(s) before the first stitch "
                    f"('{_ordinal(foundation_clause.explicit_count)} ch from hook'), but the verified "
                    f"construction for '{name.title()}' ({ref['source']}) skips {ref['row1_skip']} "
                    f"chain(s) ('{_ordinal(ref['row1_skip'] + 1)} ch from hook'). The row's own stitch-count "
                    f"math may still be internally consistent with a compensating foundation-chain length "
                    f"elsewhere, but this deviates from the named stitch's canonical construction -- worth "
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
