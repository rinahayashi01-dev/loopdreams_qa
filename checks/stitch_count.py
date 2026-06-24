"""
Stitch-count checker.

For each round/row, we know:
  - fixed clauses: exact consumes/produces, no unknowns
  - "unknown" segments: an each_around clause, or a repeat group with no
    explicit repeat count -- each has a known PER-ITERATION consumes/produces,
    but an unknown multiplier (how many times it repeats)

If there's exactly one unknown segment, we solve for its multiplier using
algebra against the previous round's stitch count and/or this round's
declared count, then cross-check both equations agree. If they don't agree,
or the solved multiplier isn't a non-negative integer, that's a real
stitch-count bug -- not a parsing failure.

If there are 0 unknown segments, we just compare the fixed totals directly.
If there are 2+ unknown segments, we can't solve uniquely, so we report that
this round couldn't be fully verified rather than guessing.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ..models import Pattern, RoundRow, Issue


@dataclass
class _UnknownSegment:
    label: str           # description for messages, e.g. "the *sc, inc* repeat group"
    per_consumes: int
    per_produces: int
    explicit_count: Optional[int] = None  # set if the text DID give a number


def _collect_segments(round_row: RoundRow):
    fixed_consumes = 0
    fixed_produces = 0
    unknowns: list[_UnknownSegment] = []

    def handle_clause_list(clauses):
        nonlocal fixed_consumes, fixed_produces
        for c in clauses:
            if c.kind == "unparsed":
                continue
            if c.kind == "each_around":
                unknowns.append(_UnknownSegment(
                    label=f"'{c.raw}'", per_consumes=c.consumes, per_produces=c.produces,
                ))
            else:
                fixed_consumes += c.consumes
                fixed_produces += c.produces

    handle_clause_list(round_row.leading_clauses)
    handle_clause_list(round_row.trailing_clauses)

    for rg in round_row.repeat_groups:
        per_c = sum(c.consumes for c in rg.clauses if c.kind != "unparsed")
        per_p = sum(c.produces for c in rg.clauses if c.kind != "unparsed")
        if rg.repeat_count_is_explicit and rg.repeat_count is not None:
            fixed_consumes += per_c * rg.repeat_count
            fixed_produces += per_p * rg.repeat_count
        else:
            unknowns.append(_UnknownSegment(
                label=f"the '*{rg.raw}*' repeat group", per_consumes=per_c, per_produces=per_p,
            ))

    return fixed_consumes, fixed_produces, unknowns


def _check_round(round_row: RoundRow, prev_count: Optional[int]) -> tuple[list[Issue], Optional[int]]:
    """Returns (issues, resolved_produced_count_for_this_round)."""
    issues: list[Issue] = []
    loc = round_row.label_str()
    fixed_consumes, fixed_produces, unknowns = _collect_segments(round_row)
    declared = round_row.declared_count

    if round_row.unparsed_fragments:
        issues.append(Issue(
            check="stitch_count", severity="info", location=loc,
            message=(
                f"Couldn't fully parse this {round_row.label.lower()} for stitch-count "
                f"verification: {', '.join(round_row.unparsed_fragments)}. Counts below "
                f"may be incomplete."
            ),
        ))

    if len(unknowns) == 0:
        if prev_count is not None and fixed_consumes != prev_count:
            issues.append(Issue(
                check="stitch_count", severity="error", location=loc,
                message=(
                    f"{loc} works {fixed_consumes} stitches from the previous round/row, "
                    f"but the previous one ended with {prev_count} stitches."
                ),
            ))
        if declared is not None and fixed_produces != declared:
            issues.append(Issue(
                check="stitch_count", severity="error", location=loc,
                message=(
                    f"{loc} is marked with a stitch count of ({declared}), but the "
                    f"instructions as written produce {fixed_produces} stitches."
                ),
            ))
        resolved = declared if declared is not None else fixed_produces
        return issues, resolved

    if len(unknowns) > 1:
        issues.append(Issue(
            check="stitch_count", severity="warning", location=loc,
            message=(
                f"{loc} has more than one ambiguous repeat section "
                f"({', '.join(u.label for u in unknowns)}), so the stitch count "
                f"couldn't be automatically verified -- check it by hand."
            ),
        ))
        resolved = declared if declared is not None else None
        return issues, resolved

    # exactly one unknown segment: solve for its multiplier
    u = unknowns[0]
    x_from_consumes = None
    x_from_produces = None
    if prev_count is not None and u.per_consumes > 0:
        x_from_consumes = (prev_count - fixed_consumes) / u.per_consumes
    if declared is not None and u.per_produces > 0:
        x_from_produces = (declared - fixed_produces) / u.per_produces

    def _bad_solve(x, source_count, fixed, per, basis):
        if x is None:
            return None
        if x < 0 or abs(x - round(x)) > 1e-6:
            return (
                f"{loc}: to reach {basis}={source_count}, {u.label} would need to repeat "
                f"{x:.2f} times (after accounting for {fixed} fixed stitches at {per} "
                f"per repeat) -- that's not a whole number, so the stitch counts don't add up."
            )
        return None

    x = None
    if x_from_consumes is not None:
        x = x_from_consumes
        bad = _bad_solve(x, prev_count, fixed_consumes, u.per_consumes, "the previous round's count")
        if bad:
            issues.append(Issue(check="stitch_count", severity="error", location=loc, message=bad))
            resolved = declared if declared is not None else None
            return issues, resolved
    elif x_from_produces is not None:
        x = x_from_produces
        bad = _bad_solve(x, declared, fixed_produces, u.per_produces, "the declared count")
        if bad:
            issues.append(Issue(check="stitch_count", severity="error", location=loc, message=bad))
            resolved = declared
            return issues, resolved

    if x is None:
        # neither prev_count nor declared was available to solve against
        issues.append(Issue(
            check="stitch_count", severity="info", location=loc,
            message=(
                f"{loc} contains {u.label} with no stated repeat count, and there's no "
                f"previous count or declared count to solve it against -- couldn't verify."
            ),
        ))
        return issues, declared

    x_int = round(x)
    computed_produces = fixed_produces + u.per_produces * x_int
    computed_consumes = fixed_consumes + u.per_consumes * x_int

    if declared is not None and computed_produces != declared:
        issues.append(Issue(
            check="stitch_count", severity="error", location=loc,
            message=(
                f"{loc}: solving {u.label} against the previous round's count of "
                f"{prev_count} implies it repeats {x_int} times, which produces "
                f"{computed_produces} stitches -- but {loc} is marked ({declared})."
            ),
        ))
    if prev_count is not None and computed_consumes != prev_count:
        issues.append(Issue(
            check="stitch_count", severity="error", location=loc,
            message=(
                f"{loc}: solving {u.label} against the declared count of {declared} "
                f"implies it repeats {x_int} times, which would consume {computed_consumes} "
                f"stitches from the previous round -- but the previous round/row ended "
                f"with {prev_count} stitches."
            ),
        ))

    resolved = declared if declared is not None else computed_produces
    return issues, resolved


def check_stitch_counts(pattern: Pattern) -> list[Issue]:
    issues: list[Issue] = []
    prev_count: Optional[int] = None
    for round_row in pattern.rounds:
        round_issues, resolved = _check_round(round_row, prev_count)
        issues.extend(round_issues)
        prev_count = resolved
    return issues
