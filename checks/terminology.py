"""
Terminology checker.

Confirms which convention (US/UK) the pattern claims to use -- explicitly
stated, or inferred from the first unambiguous term if not stated -- then
scans every round/row plus the abbreviation key for any term that only
exists in the OTHER system. See abbreviations.py's module docstring for why
only a subset of abbreviations (sc, hdc, htr, ttr, and their *2tog forms)
are treated as unambiguous proof of a system; bare 'dc'/'tr'/'dtr' are
legitimately used in both systems with different meanings and are not
flagged on their own in this version.
"""

from __future__ import annotations
import re

from ..models import Pattern, Issue
from ..abbreviations import UNAMBIGUOUS_US_ONLY, UNAMBIGUOUS_UK_ONLY


def _find_unambiguous_terms(text: str) -> list[tuple[str, str]]:
    """Returns [(term, system), ...] for every unambiguous term found in text."""
    found = []
    for term in UNAMBIGUOUS_US_ONLY:
        if re.search(rf"(?i)\b{re.escape(term)}\b", text):
            found.append((term, "US"))
    for term in UNAMBIGUOUS_UK_ONLY:
        if re.search(rf"(?i)\b{re.escape(term)}\b", text):
            found.append((term, "UK"))
    return found


def check_terminology(pattern: Pattern) -> list[Issue]:
    issues: list[Issue] = []

    if pattern.declared_system_source == "conflicting":
        issues.append(Issue(
            check="terminology", severity="warning", location="Pattern header",
            message=(
                "The pattern's text claims to use both US and UK terms -- "
                "conflicting statements were found. Clarify which convention it "
                "actually follows."
            ),
        ))
    elif pattern.declared_system_source == "none":
        issues.append(Issue(
            check="terminology", severity="warning", location="Pattern header",
            message=(
                "This pattern doesn't state whether it uses US or UK crochet terms, "
                "and no unambiguous term was found to infer one from. Add a "
                "'This pattern uses US/UK terms' note."
            ),
        ))

    locations: list[tuple[str, str, str]] = []  # (location, term, system)
    for r in pattern.rounds:
        for term, sys_ in _find_unambiguous_terms(r.raw_text):
            locations.append((r.label_str(), term, sys_))

    if not pattern.rounds:
        fallback_text = pattern.sections.get("instructions")
        text = fallback_text.raw_text if fallback_text else pattern.full_text
        for term, sys_ in _find_unambiguous_terms(text):
            locations.append(("Instructions", term, sys_))

    abbr_section = pattern.sections.get("abbreviations")
    if abbr_section:
        for term, sys_ in _find_unambiguous_terms(abbr_section.raw_text):
            locations.append(("Abbreviation key", term, sys_))

    system = pattern.declared_system
    if system is not None:
        for loc, term, sys_ in locations:
            if sys_ != system:
                issues.append(Issue(
                    check="terminology", severity="error", location=loc,
                    message=(
                        f"This pattern declares {system} terms, but '{term}' is a "
                        f"{sys_}-only abbreviation, found in {loc}."
                    ),
                ))
    else:
        us_terms = sorted({term for _, term, sys_ in locations if sys_ == "US"})
        uk_terms = sorted({term for _, term, sys_ in locations if sys_ == "UK"})
        if us_terms and uk_terms:
            us_locs = sorted({loc for loc, _, sys_ in locations if sys_ == "US"})
            uk_locs = sorted({loc for loc, _, sys_ in locations if sys_ == "UK"})
            issues.append(Issue(
                check="terminology", severity="error", location="Multiple locations",
                message=(
                    f"The pattern mixes US-only terms ({', '.join(us_terms)}, seen in "
                    f"{', '.join(us_locs)}) with UK-only terms ({', '.join(uk_terms)}, "
                    f"seen in {', '.join(uk_locs)}) without a consistent convention."
                ),
            ))

    return issues
