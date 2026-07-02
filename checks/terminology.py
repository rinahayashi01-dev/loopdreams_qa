"""
US/UK terminology consistency check.

Per ARCHITECTURE.md: only genuinely unambiguous abbreviations (US_ONLY /
UK_ONLY) are used as proof of convention or proof of mixing. Bare dc/tr/
dtr/dc2tog/tr2tog are deliberately never flagged on their own.
"""
from ..models import Issue
from .. import abbreviations as ab


def check(pattern) -> list:
    issues = []

    tokens_used = set(pattern.abbreviation_key.keys())
    for row in pattern.rows:
        for c in row.clauses:
            if c.stitch:
                tokens_used.add(c.stitch)

    if pattern.declared_system is None:
        issues.append(Issue(
            category="terminology",
            severity="warning",
            location="Materials",
            message=(
                "Could not determine whether this pattern uses US or UK terminology -- no explicit "
                "'Terminology:' field was found, and no unambiguous US-only or UK-only abbreviation "
                "(sc/hdc/sc2tog/hdc2tog vs htr/ttr/htr2tog/dtr2tog) appears anywhere to infer it from."
            ),
        ))
        return issues

    if pattern.declared_system == "US":
        conflicting = tokens_used & ab.UK_ONLY
        if conflicting:
            issues.append(Issue(
                category="terminology",
                severity="error",
                location="Pattern body",
                message=(
                    f"Pattern declares US terminology but uses UK-only abbreviation(s): "
                    f"{', '.join(sorted(conflicting))}."
                ),
            ))
    elif pattern.declared_system == "UK":
        conflicting = tokens_used & ab.US_ONLY
        if conflicting:
            issues.append(Issue(
                category="terminology",
                severity="error",
                location="Pattern body",
                message=(
                    f"Pattern declares UK terminology but uses US-only abbreviation(s): "
                    f"{', '.join(sorted(conflicting))}."
                ),
            ))

    return issues
