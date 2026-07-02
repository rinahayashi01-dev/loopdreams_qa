"""
Cross-variant consistency check: patterns that appear together in a batch
run and whose OWN Stitch Guide text claims to be the same construction as
each other (via "Also called the X stitch" aliasing) should actually
construct their opening row the same way.

This is deliberately scoped to what a pattern's own generated text
asserts, rather than an external "this is the one true way to make stitch
X" rule. Starting the alternating chain-1 pattern immediately in Row 1
(no separate plain setup row first) is, on its own, also a legitimate and
common way real patterns write linen/moss stitch -- flagging that shape
in isolation would be a false-positive risk against genuinely correct
patterns. What's actually suspicious is two files that explicitly claim
to be identical constructions (per their own generated Stitch Guide
prose) disagreeing on how Row 1 is built.

Found via a real, human-confirmed case (Jul 2 throw-blanket batch, tenth
round -- see ARCHITECTURE.md): moss's Stitch Guide says "Also called the
linen stitch", linen's says "Also called the moss stitch" -- yet moss's
Row 1 is a full plain sc row across the foundation before the
alternating pattern starts at Row 2, while linen's Row 1 starts the
alternating chain-1 pattern immediately, with no separate setup row at
all. Confirmed via an external crochet-technique reference (not something
this tool could verify on its own) that the setup row is the correct
step and linen's version is the one missing it.
"""
import re

from .models import Issue

_HEADING_NAME_RE = re.compile(r"^([A-Z][A-Za-z ]{1,40}?)\s+Stitch\b", re.M)
_ALIAS_RE = re.compile(r"also\s+called\s+the\s+([a-z][a-z \-]*?)\s+stitch", re.I)


def _stitch_names(pattern):
    """Returns (primary_name, alias_names) from a pattern's Stitch Guide,
    lowercased. (None, set()) if there's no Stitch Guide section or no
    recognizable heading."""
    sg = next((s for s in pattern.sections if s.name == "stitch_guide"), None)
    if not sg:
        return None, set()
    m = _HEADING_NAME_RE.search(sg.raw_text)
    primary = m.group(1).strip().lower() if m else None
    aliases = {a.strip().lower() for a in _ALIAS_RE.findall(sg.raw_text)}
    return primary, aliases


def _row1_has_immediate_repeat(pattern):
    """True if Row 1 contains a '*...' repeat group (alternating pattern
    starts immediately, no separate setup row). False if Row 1 exists but
    has no repeat group. None if there's no Row 1 at all."""
    row1 = next((r for r in pattern.rows if r.row_start == 1), None)
    if row1 is None:
        return None
    return any(c.raw.strip().startswith("*") for c in row1.clauses)


def check(patterns: dict) -> list:
    """patterns: {display_name: Pattern} for every file in one batch run.
    Returns a list of Issue objects (category="completeness",
    severity="warning") for any pair that claims equivalence but
    disagrees on Row 1 construction."""
    info = {}
    for name, pattern in patterns.items():
        primary, aliases = _stitch_names(pattern)
        if primary is None:
            continue
        info[name] = (primary, aliases, _row1_has_immediate_repeat(pattern))

    issues = []
    names = sorted(info.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            primary_a, aliases_a, repeat_a = info[a]
            primary_b, aliases_b, repeat_b = info[b]

            claims_equivalent = primary_a != primary_b and (
                primary_b in aliases_a or primary_a in aliases_b or bool(aliases_a & aliases_b)
            )
            if not claims_equivalent:
                continue
            if repeat_a is None or repeat_b is None or repeat_a == repeat_b:
                continue

            setup_row_file, no_setup_file = (a, b) if repeat_a is False else (b, a)
            issues.append(Issue(
                category="completeness", severity="warning",
                location=f"{a} vs {b}",
                message=(
                    f"'{primary_a.title()}' and '{primary_b.title()}' each describe themselves, in their own "
                    f"Stitch Guide, as the same stitch as the other -- but their Row 1 constructions disagree: "
                    f"'{setup_row_file}' starts with a plain full-width setup row before the alternating "
                    f"chain-1 pattern begins, while '{no_setup_file}' begins alternating immediately in Row 1 "
                    f"with no separate setup row. Both styles are independently legitimate ways to start this "
                    f"stitch, but since these two files claim to be identical constructions, they should match "
                    f"each other -- recommend checking whether '{no_setup_file}' is missing its initial setup row."
                ),
            ))
    return issues
