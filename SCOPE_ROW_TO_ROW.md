# Scope: a row-to-row model

What it would take for this tool to verify the rows it currently abstains on,
what that buys, and where the risk is. Written 2026-09-17; phase 1 is built
(2026-09-18), and so is phase 2. Phase 3 is not. The rows in question are catalogued
in KNOWN_UNVERIFIABLE.md.

## The gap in one sentence

Clauses are read one at a time, so a clause that points INTO the previous
row — "sc in centre dc of next shell", "1 dc in the same sp" — cannot say how
many of that row's stitches it passes over, because the width of the thing it
points at lives in a row this one cannot see.

## What already exists

More than you would expect. `checks/stitch_count.py`'s `check()` already walks
rows in order and carries state between them:

- `prev_count` / `prev_label` — the previous row's declared count
- `prev_component` — reset at each component boundary, seeded from that
  component's own foundation (`component_foundations`)

So the loop, the ordering and the per-piece reset are all there. What is NOT
carried is the previous row's **structure**: where its groups fall and how
wide each one is. Clauses return scalar `consumes` / `produces`; nothing
records that a shell row produced `[1, 5, 1, 5, …, 1]` rather than 19 stitches
in a flat line.

## Phase 1 — rows emit their structure — **DONE (2026-09-18)**

Each row additionally returns the ordered list of groups it produces, with
widths. A shell row becomes `[1, 5, 1, 5, …, 1]`; a plain dc row becomes
`[1] * n`.

Most of the information is already at hand: `cluster_same_spot` knows it made
one group of N, `count_in_same_spot` likewise, and every positional single is
a group of 1. The work is threading a second return value through `_zone_sum`
and the row walk, and deciding what a repeat group contributes (its unit's
groups, repeated).

Landed as `RoundRow.produced_groups`, filled in by
`checks/stitch_count.py`'s row walk. See ARCHITECTURE.md's entry for what it
turned out to involve.

**Risk: very low.** Purely additive — nothing reads it in this phase, so it
cannot change a verdict. Landing it on its own means the risky phase arrives
with the plumbing already proven.

## Phase 2 — clauses that reference a group resolve against it — **DONE (2026-09-18)**

The clauses that currently return `consumes=None` for this reason, with the
patterns that produce them:

| clause | pattern | what it needs |
|---|---|---|
| `sc in centre dc of next shell` | `centre_dc` | the next group's width, to consume all of it |
| `sc in centre dc of last shell` | `centre_dc` | the last group's width |
| `1 dc in the same sp` | `count_in_same_spot` | what the preceding clause's target was worth |
| `3 dc in next sp` | `each_of_position` | the next group/space's width |

Each resolves against the previous row's group list from phase 1, advancing a
cursor as the row is read.

Landed as `_resolve_group_references`. Two corrections to the table above,
found in the building:

- `each_of_position` was already fully resolved in the parser
  (`consumes=n`) and needed nothing.
- `count_in_same_spot` is deliberately left for phase 3. The rounds that use
  it abstain for the mixed bracket and the undeclared `cluster` as well, so
  resolving it alone cannot move a verdict — it would be code no measurement
  could check.

**Measured:** 71 PASS / 8 REVIEW → 73 PASS / 6 REVIEW across 79 cases, 0 FAIL
either side, with byte-identical findings on the other 77. 74 shell rows went
from verified by nothing to verified and passing. See ARCHITECTURE.md.

**Risk: this is where it lives.** A wrong resolution turns a warning into a
false accusation, which is the one failure mode this tool exists to avoid — so
the rule stays: if the group cursor cannot be resolved unambiguously, return
no answer and say why, exactly as today.

**Verification:** the method that has worked all week. Sweep every builder
before and after, expect exactly the intended cases to move, and treat any new
FAIL as guilty until the pattern is checked by hand. Recent precedent: three
separate false FAILs were caught that way and none by the unit tests.

## Phase 3 — the granny bracket (independent)

Does **not** need phases 1–2, and should not be bundled with them. Two
unrelated parser features:

- expanding a bracket of mixed stitch types — `[3 dc, ch 2] 3 times in ring`
  currently resolves to no single stitch and therefore no ratio
- accepting a declared count stated as several tallies —
  `(12 dc, 4 ch-2 corner sps)` rather than one number

The second changes a shared assumption (one row, one declared count), so it
reaches well beyond granny squares.

## What it buys, honestly

Not bug-fixing: all 8 current REVIEWs have been read by hand and every pattern
is correct. The value is **coverage of rows that are verified by nothing
today**.

That argument is much stronger for shell than for granny:

- **Shell** is a shipped stitch, whitelisted on four templates, in single and
  multi-colour form — and its stitch-count arithmetic is never checked. A real
  regression there would pass silently. Phases 1–2 close that.
- **Granny** rounds are hardcoded in the generator rather than computed, so
  there is far less that can drift, and correspondingly less to gain.

## Recommendation

Do phases 1 and 2. Defer phase 3 until something makes granny rounds worth
verifying — a change to how they are generated would be the trigger.
