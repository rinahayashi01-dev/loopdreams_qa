"""
Completeness checker.

Flags structural gaps that don't require stitch math: missing materials/
gauge/abbreviation-key/finishing sections, abbreviations used but never
defined in a present stitch key, unbalanced '*' repeat markers, rows in
taller stitches with no leading turning chain, and patterns with no
fasten-off/finishing step at all.

These are heuristics, not certainties -- several are flagged as "warning"
rather than "error" because legitimate patterns occasionally omit things
this checker expects (e.g. a standing stitch instead of a turning chain).
"""

from __future__ import annotations
import re

from ..models import Pattern, Issue

_HOOK_RE = re.compile(r"(?i)\b(\d+(\.\d+)?\s*mm|hook\s+size|[a-z]/\d+\s+hook|\d+(\.\d+)?\s*mm\s+hook)\b")
_YARN_RE = re.compile(r"(?i)\byarn\b")
_FASTEN_OFF_RE = re.compile(r"(?i)\b(fasten off|f\.?o\.?\b|weave in)\b")

_TALL_STITCHES = {"hdc", "dc", "tr", "dtr", "htr", "ttr"}


def _missing_sections(pattern: Pattern) -> list[Issue]:
    issues = []
    checks = [
        ("materials", "Materials/yarn/hook information"),
        ("gauge", "Gauge information"),
        ("abbreviations", "An abbreviation key / stitch key"),
        ("finishing", "A finishing/assembly section"),
    ]
    for key, label in checks:
        if key not in pattern.sections:
            issues.append(Issue(
                check="completeness", severity="warning", location="Whole pattern",
                message=f"{label} wasn't found in the document -- confirm it's genuinely absent, not just unlabeled.",
            ))
    return issues


def _materials_detail(pattern: Pattern) -> list[Issue]:
    issues = []
    materials = pattern.sections.get("materials")
    if not materials:
        return issues
    text = materials.raw_text
    if not _HOOK_RE.search(text):
        issues.append(Issue(
            check="completeness", severity="warning", location="Materials",
            message="The materials section doesn't appear to specify a hook size.",
        ))
    if not _YARN_RE.search(text):
        issues.append(Issue(
            check="completeness", severity="warning", location="Materials",
            message="The materials section doesn't appear to mention yarn weight/type.",
        ))
    return issues


def _undefined_abbreviations(pattern: Pattern) -> list[Issue]:
    issues = []
    if "abbreviations" not in pattern.sections:
        return issues  # already flagged by _missing_sections; avoid duplicate noise
    if not pattern.declared_abbreviations:
        return issues

    used = set()
    for r in pattern.rounds:
        for clause_list in (r.leading_clauses, r.trailing_clauses):
            for c in clause_list:
                if c.abbr:
                    used.add(c.abbr.lower())
        for rg in r.repeat_groups:
            for c in rg.clauses:
                if c.abbr:
                    used.add(c.abbr.lower())

    defined = set(pattern.declared_abbreviations.keys())
    undefined = sorted(t for t in used if t not in defined and t not in {"skip"})
    if undefined:
        issues.append(Issue(
            check="completeness", severity="warning", location="Abbreviation key",
            message=(
                f"These abbreviations are used in the instructions but not listed in "
                f"the stitch key: {', '.join(undefined)}."
            ),
        ))
    return issues


def _unbalanced_repeat_markers(pattern: Pattern) -> list[Issue]:
    issues = []
    for r in pattern.rounds:
        # 'repeat from *' contains an asterisk that refers back to the opening
        # marker, not a new one -- discount it before checking balance.
        checked_text = re.sub(r"(?i)(repeat|rep)(\s+from)?\s*\*", "", r.raw_text)
        if checked_text.count("*") % 2 != 0:
            issues.append(Issue(
                check="completeness", severity="error", location=r.label_str(),
                message=(
                    f"{r.label_str()} has an odd number of '*' marks -- a repeat "
                    f"section looks like it was opened but never closed (or vice versa)."
                ),
            ))
    return issues


def _missing_turning_chains(pattern: Pattern) -> list[Issue]:
    issues = []
    rows = [r for r in pattern.rounds if r.label == "Row"]
    if not rows:
        return issues
    for r in rows:
        if r.number == 1:
            continue
        first_clause = next(iter(r.leading_clauses), None)
        if first_clause is None:
            continue
        dominant_abbr = None
        for c in r.leading_clauses:
            if c.abbr in _TALL_STITCHES:
                dominant_abbr = c.abbr
                break
        if dominant_abbr is None:
            continue
        starts_with_chain = bool(re.match(r"(?i)^\s*ch\s*\d+", r.raw_text))
        if not starts_with_chain:
            issues.append(Issue(
                check="completeness", severity="warning", location=r.label_str(),
                message=(
                    f"{r.label_str()} works in {dominant_abbr} but doesn't appear to "
                    f"start with a turning chain -- confirm one isn't missing."
                ),
            ))
    return issues


def _missing_finishing_step(pattern: Pattern) -> list[Issue]:
    if "finishing" in pattern.sections:
        return []
    if _FASTEN_OFF_RE.search(pattern.full_text):
        return []
    return [Issue(
        check="completeness", severity="warning", location="Whole pattern",
        message="No fasten-off or finishing instructions were found anywhere in the pattern.",
    )]


def check_completeness(pattern: Pattern) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(_missing_sections(pattern))
    issues.extend(_materials_detail(pattern))
    issues.extend(_undefined_abbreviations(pattern))
    issues.extend(_unbalanced_repeat_markers(pattern))
    issues.extend(_missing_turning_chains(pattern))
    issues.extend(_missing_finishing_step(pattern))
    return issues
