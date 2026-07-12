"""
Round-by-round stitch-count math.

Per ARCHITECTURE.md:
- Unstated repeat counts are solved algebraically where possible; if it
  doesn't come out to a clean non-negative integer, or two equations
  disagree, that's a real error -- not silently passed or guessed.
- A row is marked unverifiable (warning, not error) when the math genuinely
  can't be checked -- e.g. a compound stitch with no defined construction,
  or an unrecognized clause -- rather than assuming a value.
- A repeat group is solved by partitioning a row's clauses into PRE (before
  the '*'), UNIT (the repeated block itself), and POST (after 'rep from *'),
  then solving the repeat count algebraically from the previous row's count
  and cross-checking against the declared count.
- Working straight into the foundation CHAIN (not a previous row of real
  stitches) is a special case: "<stitch> in each st across" applied
  directly to a foundation chain is ambiguous unless the row also states
  which numbered chain to start in (e.g. "in 2nd ch from hook") -- skipping
  some number of chains as a turning-chain equivalent is standard
  convention, but the *exact* number depends on stitch height and isn't
  knowable from "in each st across" alone. Rather than guess at a skip
  count, that case is flagged unverifiable.
- A compound stitch's PRODUCES value (how many current-row stitches it
  leaves behind) is, by definition, never read off a fixed table -- but its
  CONSUMES value usually IS grammar-determined regardless (see
  stitch_parser.py: "<stitch> in next st" names exactly one target no
  matter what stitch is worked there). That means a row using exactly one
  unresolved compound-stitch token, with everything else determined, has
  exactly one degree of freedom -- solvable from the row's own declared
  count, the same way an unstated repeat multiplier already is. See
  _solve_compound_ratios: every row that can independently supply such an
  equation is used and cross-checked against every other row using the
  same token; agreement resolves the ratio (reported as solved, not
  stated), disagreement is a real reportable inconsistency, and a token
  with no solvable row at all is left exactly as unverifiable as before.
"""
from collections import defaultdict

from ..models import Issue

_NO_OP_TYPES = {"chain", "turn", "join", "note", "fasten_off"}

# Sentinel distinct from a legitimate component value of None (the
# single-piece case), so the very first row always triggers the
# component-boundary reset in check() below.
_UNSET = object()

# Past this many rows sharing the EXACT same "cannot verify" reason, repeating
# the identical explanation once per row stops being useful and starts
# burying any other findings in noise. Real case found on a real sample
# (bobble tote bag, Jun 29 batch): a compound stitch alternating through 40
# of 80 rows produced 40 near-identical warnings before this was added.
_DEDUPE_THRESHOLD = 3
_DEDUPE_PREFIX = "Cannot verify stitch-count math for "


def check(pattern) -> list:
    ratio_overrides, solve_issues = _solve_compound_ratios(pattern)
    issues = list(solve_issues)

    prev_count = None
    prev_label = "Foundation chain"
    prev_component = _UNSET
    body_width = None
    total_rows = 0

    for row in pattern.rows:
        if row.label == "Border":
            issues.extend(_check_border(row, body_width, total_rows, ratio_overrides))
            continue

        # Real sample (sweater, Jul 12 batch): Back Panel/Front Panel/
        # Sleeves are each independently numbered ("component" on
        # RoundRow), so a row-to-row count carried across a component
        # boundary would compare unrelated pieces against each other.
        # Reset the running state at each boundary and seed it from that
        # component's OWN foundation (component_foundations, or the
        # pattern-level foundation_chain/is_magic_ring for the single-piece
        # case -- component is None there, identical to every prior batch).
        if row.component != prev_component:
            prev_count = None
            prev_label = "Foundation chain"
            prev_component = row.component
            cur_foundation_chain, cur_is_magic_ring = pattern.component_foundations.get(
                row.component, (pattern.foundation_chain, pattern.foundation_is_magic_ring)
            )

        total_rows = max(total_rows, row.row_end)

        if row.referenced_rows:
            # A bare "Repeat Row(s) P-Q" back-reference: the referenced
            # row(s) were already individually verified when they were
            # first stated, so there's nothing new to check here -- just
            # carry the count forward.
            prev_count = row.declared_count
            prev_label = row.label
            body_width = row.declared_count if row.declared_count is not None else body_width
            continue

        if row.clauses and all(c.clause_type in _NO_OP_TYPES for c in row.clauses):
            if len(row.clauses) == 1 and row.clauses[0].clause_type == "chain":
                # A component's own foundation declared AS a numbered row
                # (real sample: sweater, Jul 12 batch, "Row 1 Sleeves
                # (make 2): Ch 35. (32 sts)") -- its declared_count is
                # already the POST-turning-chain-skip stitch count (used
                # above to seed this component's foundation_chain), not a
                # real row-to-row count to carry forward. The very next
                # row typically re-derives directly from the raw chain via
                # its own "Nth ch from hook" clause -- if prev_count were
                # set here, that row would subtract the turning-chain skip
                # a second time. Skip entirely, leaving prev_count at
                # whatever it was (None, right after the component reset
                # above).
                continue
            # Any other row with no real stitch content at all can't be
            # "verified" against the in-count the normal way (it has
            # nothing to produce/consume), so just carry its own declared
            # count forward as the new baseline, the same as the
            # referenced_rows bypass above.
            prev_count = row.declared_count
            prev_label = row.label
            body_width = row.declared_count if row.declared_count is not None else body_width
            continue

        in_count = prev_count if prev_count is not None else cur_foundation_chain
        in_label = prev_label
        # A magic-ring foundation (continuous-spiral/amigurumi-style, real
        # sample: mittens Jul 7 batch) has no turning-chain-skip concept at
        # all -- stitches are worked directly into the ring, so there's no
        # "which numbered chain to start in" ambiguity the way there is for
        # a real chain foundation. Only flag the transition ambiguity when
        # the foundation actually came from a chain.
        is_foundation_transition = prev_count is None and not cur_is_magic_ring

        row_issues = _check_row(row, in_count, in_label, is_foundation_transition, ratio_overrides)
        issues.extend(row_issues)

        prev_count = row.declared_count
        prev_label = row.label
        if row.declared_count is not None:
            body_width = row.declared_count

    return _dedupe_repeated_warnings(issues)


# ----------------------------------------------------------------------
# Compound-stitch ratio solving
# ----------------------------------------------------------------------

def _sum_known(clauses):
    """Like _zone_sum, but for the ratio-solving pre-scan. Returns
    (known_produces, consumes_total, unknown) where `unknown` is a dict of
    stitch-token -> occurrence-count for clauses whose produces is
    genuinely undetermined (always a compound stitch, by construction --
    see stitch_parser.py's grammar-based consumes fix). The whole result
    collapses to (0, None, None) if ANY clause is a hard block (an
    unrecognized clause, or one whose CONSUMES can't even be determined,
    like the centre-dc landmark case) -- no equation can be trusted if part
    of it is already unknown for a different reason."""
    known_p = 0
    consumes_total = 0
    unknown = defaultdict(int)
    for c in clauses:
        if c.clause_type in _NO_OP_TYPES or c.clause_type == "repeat_close":
            continue
        if c.clause_type == "unknown" or c.consumes is None:
            return 0, None, None
        consumes_total += c.consumes
        if c.produces is None:
            if c.is_compound and c.stitch:
                # Weight by the clause's own multiplier (e.g. cluster_
                # same_spot's "2 moss in first st" represents 2 units of
                # the unknown ratio, not 1) rather than always +=1. Real
                # bug found (shawl, Jul 8 batch): every compound stitch
                # seen before this always appeared with an implicit
                # multiplier of 1 ("bobble in next st"), so the always-1
                # assumption happened to be correct and this was never
                # exercised -- "2 MOSS in first st" / "MOSS in each of
                # next N sts" (multipliers of 2 and N) exposed it,
                # producing a contradictory-equations false error instead
                # of solving cleanly.
                unknown[c.stitch] += c.explicit_count if c.explicit_count is not None else 1
            else:
                return 0, None, None
        else:
            known_p += c.produces
    return known_p, consumes_total, dict(unknown)


def _solve_row_for_ratio(row, in_count):
    """If this row's stitch-count math has exactly one degree of freedom --
    a single compound-stitch token with an unknown produces value, with
    everything else (consumes, repeat count if any, other stitches'
    produces) fully determined -- solve for that one unknown from the
    row's own declared count. Returns (token, value) if solvable, else
    None. Never forces a solution that isn't a clean non-negative integer;
    those cases are left for the normal verification pass to report on
    their own terms."""
    if row.declared_count is None:
        return None
    clauses = row.clauses

    if any(c.clause_type == "foundation_into_chain" for c in clauses):
        return None  # foundation rows have their own dedicated check; out of scope here

    opener_idx = next((i for i, c in enumerate(clauses) if c.raw.strip().startswith("*")), None)
    closer_idx = None
    if opener_idx is not None:
        closer_idx = next((i for i in range(opener_idx, len(clauses)) if clauses[i].clause_type == "repeat_close"), None)

    if opener_idx is not None and closer_idx is not None:
        pre, unit, post = clauses[:opener_idx], clauses[opener_idx:closer_idx], clauses[closer_idx + 1:]
        pre_p, pre_c, pre_u = _sum_known(pre)
        unit_p, unit_c, unit_u = _sum_known(unit)
        post_p, post_c, post_u = _sum_known(post)
        if pre_c is None or unit_c is None or post_c is None or not unit_c or in_count is None:
            return None

        remainder = in_count - pre_c - post_c
        if remainder < 0 or remainder % unit_c != 0:
            return None  # a real mismatch -- the normal pass reports it; not a ratio-solving job

        r = remainder // unit_c
        all_unknown = defaultdict(int)
        for k, v in pre_u.items():
            all_unknown[k] += v
        for k, v in unit_u.items():
            all_unknown[k] += v * r
        for k, v in post_u.items():
            all_unknown[k] += v
        if len(all_unknown) != 1:
            return None  # zero or multiple distinct unknown tokens -- not a single clean equation

        token, occurrences = next(iter(all_unknown.items()))
        if not occurrences:
            return None
        known_total = pre_p + r * unit_p + post_p
        numerator = row.declared_count - known_total
        if numerator < 0 or numerator % occurrences != 0:
            return None
        return token, numerator // occurrences

    each_st = next((c for c in clauses if c.clause_type in ("each_st_across", "each_st_around")), None)
    if each_st is not None:
        if each_st.produces is not None or not each_st.is_compound or not in_count:
            return None
        if row.declared_count % in_count != 0:
            return None
        return each_st.stitch, row.declared_count // in_count

    known_p, consumes_total, unknown = _sum_known(clauses)
    if consumes_total is None or unknown is None or len(unknown) != 1:
        return None
    token, occurrences = next(iter(unknown.items()))
    if not occurrences:
        return None
    numerator = row.declared_count - known_p
    if numerator < 0 or numerator % occurrences != 0:
        return None
    return token, numerator // occurrences


def _solve_compound_ratios(pattern):
    """Scan every body row in sequence (mirroring check()'s own prev_count
    tracking) collecting, per compound-stitch token, every row that can
    independently solve for that token's produces value. Cross-check the
    results: full agreement resolves the token (used to actually verify
    every row using it, including ones that didn't contribute an
    equation); disagreement is reported as a real error; a token with no
    solvable row at all is left unresolved, exactly as unverifiable as
    before this feature existed."""
    candidates = defaultdict(list)  # token -> [(row_label, value)]
    prev_count = None
    prev_component = _UNSET
    cur_foundation_chain = pattern.foundation_chain

    for row in pattern.rows:
        if row.label == "Border":
            continue

        # Mirror check()'s own per-component reset (see there for why: Back
        # Panel/Front Panel/Sleeves each restart their own numbering).
        if row.component != prev_component:
            prev_count = None
            prev_component = row.component
            cur_foundation_chain, _ = pattern.component_foundations.get(
                row.component, (pattern.foundation_chain, pattern.foundation_is_magic_ring)
            )

        if row.referenced_rows:
            prev_count = row.declared_count if row.declared_count is not None else prev_count
            continue

        if row.clauses and all(c.clause_type in _NO_OP_TYPES for c in row.clauses):
            if len(row.clauses) == 1 and row.clauses[0].clause_type == "chain":
                continue  # component's own foundation declaration -- see check() for why
            prev_count = row.declared_count if row.declared_count is not None else prev_count
            continue

        in_count = prev_count if prev_count is not None else cur_foundation_chain
        result = _solve_row_for_ratio(row, in_count)
        if result is not None:
            token, value = result
            candidates[token].append((row.label, value))

        if row.declared_count is not None:
            prev_count = row.declared_count

    overrides = {}
    issues = []
    for token, entries in candidates.items():
        labels = [lbl for lbl, _ in entries]
        values = sorted({v for _, v in entries})
        if len(values) == 1:
            value = values[0]
            overrides[token] = value
            loc = f"{labels[0]}\u2013{labels[-1]} ({len(labels)} rows)" if len(labels) > 1 else labels[0]
            issues.append(Issue(
                category="stitch_count", severity="info", location=loc,
                message=(
                    f"'{token}' has no fixed consumes/produces ratio stated anywhere (its construction is "
                    f"descriptive text, not a number) -- but solving algebraically from {len(labels)} row(s)' "
                    f"own declared stitch counts ({', '.join(labels)}) gives a consistent answer: {value} "
                    f"produced stitch(es) per '{token}'. This is a solved value, not a guess -- every "
                    f"contributing row independently agrees -- and it's used below to actually verify every "
                    f"row using '{token}', including ones that didn't contribute to solving it."
                ),
            ))
        else:
            by_value = defaultdict(list)
            for lbl, v in entries:
                by_value[v].append(lbl)
            detail = "; ".join(f"{v} implied by {', '.join(lbls)}" for v, lbls in sorted(by_value.items()))
            issues.append(Issue(
                category="stitch_count", severity="error",
                location=f"{labels[0]}\u2013{labels[-1]}",
                message=(
                    f"Solving for '{token}''s produces-count from different rows' own declared counts gives "
                    f"contradictory answers depending which row you start from: {detail}. These can't all be "
                    f"correct -- at least one of these rows' declared stitch count is wrong."
                ),
            ))
    return overrides, issues


# ----------------------------------------------------------------------
# Normal per-row verification (uses ratio_overrides resolved above)
# ----------------------------------------------------------------------

def _check_row(row, in_count, in_label, is_foundation_transition, ratio_overrides):
    clauses = row.clauses

    foundation_clause = next((c for c in clauses if c.clause_type == "foundation_into_chain"), None)
    if foundation_clause is not None:
        idx = clauses.index(foundation_clause)
        inline_chain = next((c for c in reversed(clauses[:idx]) if c.clause_type == "chain"), None)
        if inline_chain is not None:
            # This row starts its OWN fresh foundation chain mid-row (e.g. a
            # second component like handles/straps) rather than continuing
            # the running row-to-row count -- verify against that, not
            # against whatever the main piece's last row declared.
            return _check_foundation_into_chain(row, foundation_clause, inline_chain.explicit_count,
                                                 "its own foundation chain stated in this row")
        return _check_foundation_into_chain(row, foundation_clause, in_count, in_label)

    # Terminal drawstring-cinch closure (real shape, mittens Jul 7 batch:
    # "Fasten off, leaving a long tail. Thread the tail through the front
    # loop of each remaining stitch, pull tight to close..., and weave in
    # the end."). A row whose only real content is fasten_off/closure/note
    # clauses doesn't produce or consume stitches in the normal sense --
    # it gathers up whatever's left and closes the piece. The declared
    # count here just restates how many stitches existed going INTO the
    # closure, not something the row itself produces, so the normal
    # consumed/produced-vs-declared check doesn't apply; the only
    # meaningful invariant is that the restated count matches what was
    # actually carried in from the previous row.
    real_types = {"fasten_off", "closure", "note"}
    if clauses and all(c.clause_type in real_types for c in clauses):
        if in_count is not None and row.declared_count is not None and in_count != row.declared_count:
            return [Issue(
                category="stitch_count", severity="error", location=row.label,
                message=(
                    f"Stitch-count mismatch at {row.label}: {in_label} has {in_count} sts, but this closing "
                    f"row states {row.declared_count} sts going into the closure."
                ),
            )]
        return []

    # Gusset-transition round: sets some stitches aside on a holder, bridges
    # the gap with a chain, and completes the round by folding that chain's
    # stitches back in (real shape found on a real sample, mittens Jul 7
    # batch, thumb gusset). The total math is knowable even though exactly
    # where the held stitches fall within the round isn't stated as a
    # number: produced = (in_count - held) + bridge, regardless of the
    # split -- see _check_gusset_transition.
    held_clause = next((c for c in clauses if c.clause_type == "held_aside"), None)
    bridge_clause = next((c for c in clauses if c.clause_type == "bridge_chain"), None)
    if held_clause is not None and bridge_clause is not None:
        return _check_gusset_transition(row, held_clause, bridge_clause, in_count, in_label)

    # A row resuming stitches set aside by an earlier gusset-transition row
    # (e.g. starting the thumb from held gusset stitches) is its OWN fresh
    # sub-round, not a continuation of the immediately-preceding row's
    # count -- that preceding row is usually a different part of the piece
    # entirely (e.g. the fingertip closure). The held count and any newly
    # picked-up stitches are both stated explicitly in THIS row's own
    # clauses, so the inherited in_count isn't relevant -- and would be
    # actively wrong to check against. Falls through to the normal
    # dispatch below with in_count=None, which still verifies
    # produced == declared_count via _check_flat_sequence.
    if any(c.clause_type == "held_gusset_resume" for c in clauses):
        in_count = None

    opener_idx = next((i for i, c in enumerate(clauses) if c.raw.strip().startswith("*")), None)
    closer_idx = None
    if opener_idx is not None:
        closer_idx = next((i for i in range(opener_idx, len(clauses)) if clauses[i].clause_type == "repeat_close"), None)

    if opener_idx is not None and closer_idx is not None:
        # Only one repeat group per row is supported (see ARCHITECTURE.md's
        # V1 scope). A second '*' opener anywhere after the first group
        # closes must be caught HERE, before falling through to
        # _check_repeat_group: that function treats everything after the
        # first closer as flat, one-time "post" content via _zone_sum,
        # which SKIPS repeat_close clauses entirely as no-ops rather than
        # flagging them -- so a second, unrecognized repeat group's own
        # opener/body/closer would silently get summed as if it occurred
        # exactly once, which can happen to produce a numerically
        # consistent (but meaningless) confident PASS instead of the
        # "unsupported" warning this was always supposed to be.
        second_opener_idx = next(
            (i for i in range(closer_idx + 1, len(clauses)) if clauses[i].raw.strip().startswith("*")),
            None,
        )
        if second_opener_idx is not None:
            return [Issue(
                category="stitch_count", severity="warning", location=row.label,
                message=(
                    f"{row.label} appears to contain more than one repeat group (a second '*...' "
                    f"marker found after the first repeat group closes). Only one repeat group per "
                    f"row is currently supported, so this row's stitch-count math can't be verified."
                ),
            )]
        return _check_repeat_group(row, clauses, opener_idx, closer_idx, in_count, in_label, ratio_overrides)

    each_st = next((c for c in clauses if c.clause_type in ("each_st_across", "each_st_around")), None)
    if each_st is not None:
        idx = clauses.index(each_st)
        pre, post = clauses[:idx], clauses[idx + 1:]
        if pre or post:
            # Literal clauses surround the "each st across/around" clause --
            # e.g. short-row increases before finishing the rest of the
            # round plainly (mittens, Jul 7 batch, thumb gusset shaping:
            # "2 sc in each of next 2 sts, sc in each of next 2 sts, sc in
            # each st around to end"). Previously this branch ignored
            # everything except the each_st clause itself and treated the
            # WHOLE row as if it were bare "<stitch> in each st
            # across/around" from the very start -- a confidently WRONG
            # answer (the pre/post clauses' own stitches were neither
            # subtracted from in_count nor added to the total), not just an
            # unverifiable gap. Sum pre/post explicitly and feed the
            # adjusted numbers through.
            pre_p, pre_c, pre_r = _zone_sum(pre, ratio_overrides=ratio_overrides)
            post_p, post_c, post_r = _zone_sum(post, ratio_overrides=ratio_overrides)
            reasons = pre_r + post_r
            if reasons:
                return [Issue(
                    category="stitch_count", severity="warning", location=row.label,
                    message=f"Cannot verify stitch-count math for {row.label}: {'; '.join(reasons)}.",
                )]
            return _check_each_st(row, each_st, in_count, in_label, is_foundation_transition, ratio_overrides,
                                   pre_consumes=pre_c + post_c, pre_produces=pre_p + post_p)
        return _check_each_st(row, each_st, in_count, in_label, is_foundation_transition, ratio_overrides)

    # No repeat group, no each-st clause: a flat, non-repeating sequence of
    # fixed-count clauses (e.g. literal stitch-by-stitch instructions).
    return _check_flat_sequence(row, clauses, in_count, in_label, ratio_overrides, is_foundation_transition)


def _zone_sum(clauses, count_chains=False, ratio_overrides=None):
    ratio_overrides = ratio_overrides or {}
    produces, consumes = 0, 0
    reasons = []
    for c in clauses:
        if c.clause_type == "chain" and count_chains:
            produces += c.explicit_count or 0
            continue
        if c.clause_type in _NO_OP_TYPES or c.clause_type == "repeat_close":
            continue
        if c.clause_type == "unknown":
            reasons.append(f"unrecognized clause: '{c.raw}'")
            continue
        if c.consumes is None:
            reasons.append(c.unverifiable_reason or f"'{c.stitch}' has no fixed consumes/produces ratio")
            continue
        consumes += c.consumes
        if c.produces is None:
            if c.is_compound and c.stitch in ratio_overrides:
                # Weight by the clause's own multiplier -- same fix as
                # _sum_known above, for the same reason (shawl, Jul 8
                # batch): "2 moss in first st" is 2 units of the resolved
                # per-unit ratio, not 1.
                weight = c.explicit_count if c.explicit_count is not None else 1
                produces += ratio_overrides[c.stitch] * weight
            else:
                reasons.append(c.unverifiable_reason or f"'{c.stitch}' has no fixed consumes/produces ratio")
                continue
        else:
            produces += c.produces
    return produces, consumes, reasons


def _check_repeat_group(row, clauses, opener_idx, closer_idx, in_count, in_label, ratio_overrides):
    pre, unit, post = clauses[:opener_idx], clauses[opener_idx:closer_idx], clauses[closer_idx + 1:]
    pre_p, pre_c, pre_r = _zone_sum(pre, ratio_overrides=ratio_overrides)
    unit_p, unit_c, unit_r = _zone_sum(unit, ratio_overrides=ratio_overrides)
    post_p, post_c, post_r = _zone_sum(post, ratio_overrides=ratio_overrides)
    reasons = pre_r + unit_r + post_r

    if reasons:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=f"Cannot verify stitch-count math for {row.label}: {'; '.join(reasons)}.",
        )]

    if in_count is None:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=f"Cannot verify stitch-count math for {row.label}: no usable starting count from {in_label}.",
        )]

    if unit_c == 0:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=f"Cannot verify stitch-count math for {row.label}: the repeated unit consumes 0 stitches per "
                     f"repeat, so the repeat count can't be solved from the previous row's count.",
        )]

    remainder = in_count - pre_c - post_c
    if remainder < 0 or remainder % unit_c != 0:
        return [Issue(
            category="stitch_count", severity="error", location=row.label,
            message=(
                f"Stitch-count mismatch at {row.label}: starting from {in_label} ({in_count} sts), after the "
                f"non-repeated stitches ({pre_c + post_c} consumed) there are {remainder} stitches left for the "
                f"repeat, which doesn't divide evenly into the repeat unit ({unit_c} sts per repeat). The repeat "
                f"count for 'rep from *' can't be a whole number here."
            ),
        )]

    r = remainder // unit_c
    produced_total = pre_p + r * unit_p + post_p
    if row.declared_count is not None and produced_total != row.declared_count:
        # Some stitches (e.g. moss/linen stitch) conventionally count their
        # chain-1 spaces as stitches toward the row total; most patterns'
        # turning chains don't. Try the alternate convention for chains
        # INSIDE the repeated unit before concluding it's a real mismatch.
        unit_p_alt, _, unit_r_alt = _zone_sum(unit, count_chains=True, ratio_overrides=ratio_overrides)
        if not unit_r_alt:
            produced_alt = pre_p + r * unit_p_alt + post_p
            if produced_alt == row.declared_count:
                return []
        return [Issue(
            category="stitch_count", severity="error", location=row.label,
            message=(
                f"Stitch-count mismatch at {row.label}: starting from {in_label} ({in_count} sts), the repeat "
                f"resolves to {r} repetition(s), producing {produced_total} sts total, but the pattern declares "
                f"{row.declared_count} sts."
            ),
        )]
    return []


def _check_each_st(row, each_st, in_count, in_label, is_foundation_transition, ratio_overrides,
                    pre_consumes=0, pre_produces=0):
    produces = each_st.produces
    if produces is None and each_st.is_compound and each_st.stitch in ratio_overrides:
        produces = ratio_overrides[each_st.stitch]

    if produces is None:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=(
                f"Cannot verify stitch-count math for {row.label}: uses '{each_st.stitch}', which has no defined "
                f"consumes/produces ratio."
            ),
        )]

    if is_foundation_transition:
        # Ambiguous: "X in each st across" applied directly to a foundation
        # chain doesn't say which numbered chain to start in, so the number
        # of chains treated as a turning-chain equivalent is unknown.
        # Flagged here (and separately, for clarity, as a completeness
        # issue) rather than guessed at.
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=(
                f"Cannot verify stitch-count math for {row.label}: the instruction works '{each_st.stitch} in "
                f"each st across' directly off the foundation chain ({in_count} ch) without stating which "
                f"numbered chain to start in (e.g. '2nd ch from hook'), so the number of chains used as a "
                f"turning-chain equivalent is unknown. Declared count: {row.declared_count} sts."
            ),
        )]

    remaining = (in_count - pre_consumes) if in_count is not None else None
    expected = (remaining * produces + pre_produces) if remaining is not None else None
    if expected is not None and row.declared_count is not None and expected != row.declared_count:
        detail = (
            f" ({pre_consumes} consumed by other clauses earlier in this row, {remaining} remaining)"
            if pre_consumes else ""
        )
        message = (
            f"Stitch-count mismatch at {row.label}: {in_label} has {in_count} sts{detail}; working "
            f"'{each_st.stitch}' across the remainder should produce {expected} sts total, but the pattern "
            f"declares {row.declared_count} sts."
        )
        return [Issue(category="stitch_count", severity="error", location=row.label, message=message)]
    return []


def _check_flat_sequence(row, clauses, in_count, in_label, ratio_overrides, is_foundation_transition=False):
    p, c, reasons = _zone_sum(clauses, ratio_overrides=ratio_overrides)
    if reasons:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=f"Cannot verify stitch-count math for {row.label}: {'; '.join(reasons)}.",
        )]
    if in_count is not None and c != in_count:
        if is_foundation_transition and c < in_count:
            # Ambiguous, not wrong: this row's clauses consume fewer
            # stitches than the raw foundation chain, with no ordinal
            # "in Nth ch from hook" clause stating how many chains were
            # meant as a turning-chain equivalent. Real sample found
            # (shawl, Jul 8 batch): a triangle shawl's first row works
            # "2 SC in first st, SC in next st, 2 SC in last st" straight
            # off a Ch 4 foundation, consuming only 3 -- almost certainly
            # the standard "skip 1 as if it were a turning chain"
            # convention (matching the declared count exactly), but never
            # stated as such, so left unverifiable rather than assumed --
            # same posture as the analogous each_st-clause ambiguity above.
            return [Issue(
                category="stitch_count", severity="warning", location=row.label,
                message=(
                    f"Cannot verify stitch-count math for {row.label}: this row's stitches only account for "
                    f"{c} of the {in_count} foundation chain sts, with no ordinal clause (e.g. '2nd ch from "
                    f"hook') stating how many chains were meant as a turning-chain equivalent. Declared count: "
                    f"{row.declared_count} sts."
                ),
            )]
        return [Issue(
            category="stitch_count", severity="error", location=row.label,
            message=(
                f"Stitch-count mismatch at {row.label}: {in_label} has {in_count} sts, but the row's stitches "
                f"only account for {c} of them."
            ),
        )]
    if row.declared_count is not None and p != row.declared_count:
        return [Issue(
            category="stitch_count", severity="error", location=row.label,
            message=(
                f"Stitch-count mismatch at {row.label}: the row's stitches produce {p} sts, but the pattern "
                f"declares {row.declared_count} sts."
            ),
        )]
    return []


def _check_foundation_into_chain(row, clause, foundation_chain, in_label):
    if foundation_chain is None:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=f"Cannot verify stitch-count math for {row.label}: no foundation chain count was found "
                     f"to check against.",
        )]
    skip = clause.explicit_count - 1  # "2nd ch from hook" -> skip 1, "4th" -> skip 3
    expected = foundation_chain - skip
    if row.declared_count is not None and expected != row.declared_count:
        return [Issue(
            category="stitch_count", severity="error", location=row.label,
            message=(
                f"Stitch-count mismatch at {row.label}: starting in the {clause.explicit_count}"
                f"{'st' if clause.explicit_count == 1 else 'nd' if clause.explicit_count == 2 else 'rd' if clause.explicit_count == 3 else 'th'} "
                f"chain from the hook on a {foundation_chain}-chain foundation should produce {expected} sts, "
                f"but the pattern declares {row.declared_count} sts."
            ),
        )]
    return []


def _check_gusset_transition(row, held_clause, bridge_clause, in_count, in_label):
    """A round that sets N stitches aside on a holder (held_aside) and
    bridges the gap with M chain stitches (bridge_chain), later folded back
    in by a round-completion clause. Real shape found on a real sample
    (mittens, Jul 7 batch, thumb gusset transition): "Sc in each st to the
    marked gusset sts. Place the next 10 sts on a holder... Ch 2 to bridge
    the gap, then sc in each remaining st around, working the last 2 sts of
    the round into the 2 ch just made."

    The row's two "each st ..." clauses (one stopping at the marker, one
    finishing the round) each cover an UNKNOWN, unstated number of
    stitches individually -- but their sum is always exactly
    (in_count - N), regardless of exactly where the split falls, since
    together they account for every non-held stitch in the round. Total
    produced = (in_count - N) [the two each-st clauses, both plain 1:1] +
    M [the bridge stitches folded in by the completion clause]. This is
    knowable and checked directly, without needing to know the split."""
    if in_count is None:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=f"Cannot verify stitch-count math for {row.label}: no usable starting count from {in_label}.",
        )]
    held = held_clause.explicit_count
    bridge = bridge_clause.explicit_count
    if held is None or bridge is None:
        return [Issue(
            category="stitch_count", severity="warning", location=row.label,
            message=f"Cannot verify stitch-count math for {row.label}: held-aside or bridge-chain count not "
                     f"stated as a number.",
        )]
    expected = in_count - held + bridge
    if row.declared_count is not None and expected != row.declared_count:
        return [Issue(
            category="stitch_count", severity="error", location=row.label,
            message=(
                f"Stitch-count mismatch at {row.label}: starting from {in_label} ({in_count} sts), setting "
                f"aside {held} st(s) and bridging with {bridge} chain st(s) should produce {expected} sts, but "
                f"the pattern declares {row.declared_count} sts."
            ),
        )]
    return []


def _check_border(row, body_width, total_rows, ratio_overrides):
    issues = []
    bracket_groups = [c for c in row.clauses if c.clause_type == "bracket_group"]

    if bracket_groups:
        grand_total = 0
        problems = []
        for g in bracket_groups:
            if g.explicit_count is None:
                problems.append(f"could not resolve the repeat count for '{g.raw}'")
                continue
            val, unresolved = _bracket_group_value(g, body_width, total_rows, ratio_overrides)
            if unresolved:
                problems.append(f"could not fully resolve '{g.raw}' ({'; '.join(unresolved)})")
                continue
            grand_total += val * g.explicit_count

        if problems:
            issues.append(Issue(
                category="stitch_count", severity="warning", location="Border",
                message=f"Cannot fully verify border stitch count: {'; '.join(problems)}.",
            ))
        elif row.declared_count is not None and grand_total != row.declared_count:
            issues.append(Issue(
                category="stitch_count", severity="error", location="Border",
                message=(
                    f"Border stitch-count mismatch: working through the border's repeat groups gives "
                    f"{grand_total} sts, but the pattern declares {row.declared_count} sts."
                ),
            ))
    else:
        has_repeat_close = any(c.clause_type == "repeat_close" for c in row.clauses)
        has_side_edge_rule = any(c.clause_type == "side_edge_rule" for c in row.clauses)
        if has_repeat_close and has_side_edge_rule:
            issues.append(Issue(
                category="stitch_count", severity="warning", location="Border",
                message=(
                    "Border stitch count cannot be automatically verified: the instruction combines an "
                    "unstated-multiplier repeat group with a separate additive rule for side-edge stitches, "
                    "and never states how many corners the repeat runs around. Declared total "
                    f"({row.declared_count} sts) could not be independently confirmed."
                ),
            ))

    if row.declared_count_is_approx:
        issues.append(Issue(
            category="completeness", severity="warning", location="Border",
            message=(
                f"Final border stitch count is given as approximate ('~{row.declared_count} sts'). A border "
                f"stitch count built from fixed row counts and a fixed stitch count per row is a deterministic "
                f"value, not an approximation -- stating it as '~N' makes it impossible to tell whether a real "
                f"miscount is hiding behind the approximation. Recommend an exact count."
            ),
        ))

    return issues


def _bracket_group_value(group, body_width, total_rows, ratio_overrides):
    total = 0
    unresolved = []
    for c in group.sub_clauses:
        if c.clause_type in _NO_OP_TYPES or c.clause_type == "repeat_close":
            continue
        if c.clause_type == "corner":
            if c.produces is None:
                unresolved.append(c.raw)
            else:
                total += c.produces
        elif c.clause_type in ("each_st_across", "each_st_around"):
            produces = c.produces
            if produces is None and c.is_compound and c.stitch in ratio_overrides:
                produces = ratio_overrides[c.stitch]
            if produces is None or body_width is None:
                unresolved.append(c.raw)
            else:
                total += produces * body_width
        elif c.clause_type == "side_edge_rule":
            if total_rows is None or not total_rows:
                unresolved.append(c.raw)
            else:
                total += (c.explicit_count or 0) * total_rows
        elif c.clause_type == "unknown":
            unresolved.append(c.raw)
        elif c.produces is not None:
            total += c.produces
        elif c.is_compound and c.stitch in ratio_overrides:
            total += ratio_overrides[c.stitch]
        else:
            unresolved.append(c.raw)
    return total, unresolved


# ----------------------------------------------------------------------
# De-duplication of repeated identical warnings
# ----------------------------------------------------------------------

def _dedupe_repeated_warnings(issues: list) -> list:
    """Collapse stitch-count warnings that share the exact same underlying
    reason across _DEDUPE_THRESHOLD+ rows into a single combined issue
    naming all affected rows, instead of repeating the identical
    explanation once per row. This never changes WHAT was detected (every
    affected row is still named, in the combined issue's message) -- it
    only changes how many times the same sentence is printed."""
    groups = defaultdict(list)
    passthrough = []
    for issue in issues:
        if (issue.category == "stitch_count" and issue.severity == "warning"
                and issue.message.startswith(_DEDUPE_PREFIX)):
            rest = issue.message[len(_DEDUPE_PREFIX):]
            _label_part, _, reason = rest.partition(": ")
            groups[reason].append(issue)
        else:
            passthrough.append(issue)

    deduped = list(passthrough)
    for reason, entries in groups.items():
        if len(entries) < _DEDUPE_THRESHOLD:
            deduped.extend(entries)
            continue
        locations = [e.location for e in entries]
        deduped.append(Issue(
            category="stitch_count", severity="warning",
            location=f"{locations[0]}\u2013{locations[-1]} ({len(locations)} rows)",
            message=(
                f"Cannot verify stitch-count math for {len(locations)} rows ({', '.join(locations)}): {reason} "
                f"This exact reason recurs identically across all {len(locations)} of them, so it's reported "
                f"once here instead of once per row."
            ),
        ))
    return deduped
