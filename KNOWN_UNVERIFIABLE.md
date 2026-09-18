# Known-unverifiable rows

Every REVIEW the batch suite currently reports, why the row cannot be checked,
and what it would take to change that. If a REVIEW you are looking at is on
this list, it has already been investigated — please don't re-derive it.

As of 2026-09-18: **79 cases — 73 pass, 6 review, 0 fail.** All 6 REVIEWs come
from the two causes below, and both are granny.

A REVIEW means "this tool could not do the arithmetic", never "the pattern is
wrong". Every one of these has been read by hand and the pattern is correct.
The rule this whole tool follows is that a clause it cannot resolve returns no
answer and says why, because a wrong parse turns a warning into a false
accusation — see ARCHITECTURE.md.

---

## 1. Granny Square round 2 — a bracketed group of mixed stitches worked in a ring

**Affects:** `Granny Square — beginner / intermediate / advanced` (3 cases)

The row: `Ch 3 (counts as first dc), 2 dc in ring, ch 2, [3 dc, ch 2] 3 times
in ring, sl st to top of ch 3 to join. (12 dc, 4 ch-2 corner sps)`

Two things defeat it, and reported together as `'None' has no fixed
consumes/produces ratio` — the `None` being a clause with no single identified
stitch:

- `[3 dc, ch 2] 3 times` is a bracket holding **two different stitch types**.
  The grammar decomposes a bracket of one repeated stitch; a mixed one has no
  single ratio to name, so the clause resolves to no stitch at all.
- The round declares its total as **two separate tallies** —
  `(12 dc, 4 ch-2 corner sps)` — not one number. There is no single declared
  count to check a single produced figure against.

**What would change it:** expanding mixed brackets into their members, and
teaching the row model that a declared count can be several tallies of
different things. Both are real work, and the second changes a shared
assumption.

---

## 2. Granny Square Blanket round 3 — "the same sp", and an undeclared cluster

**Affects:** `Granny Square Blanket — beginner / intermediate / advanced`
(3 cases)

Reported as: `'1 dc in the same sp' works into the spot the preceding clause
named; how many previous-round stitches or spaces that spot accounts for isn't
stated` plus `'cluster' has no fixed consumes/produces ratio`.

- **`in the same sp`** is a back-reference. It consumes nothing new — it works
  into the spot the clause before it already named — but how much of the
  previous round *that* spot accounts for is a property of the previous round,
  which the clause does not state. Same shape of problem as the shell case that used to head this list — see
  the table below.
- **`cluster`** is a named group whose stitch count the pattern never declares.
  Unlike `bobble`, which the tool solves algebraically across many rows that
  each declare their own counts, the granny motif's rounds do not give it
  enough independent equations to solve.

**What would change it:** phase 3 of SCOPE_ROW_TO_ROW.md (expanding a mixed
bracket, and accepting a declared count stated as several tallies), plus
either a declared construction for `cluster` in the abbreviation key or enough
rows to solve it from. The row-to-row model that cleared the shell case is
built and would resolve `in the same sp` on its own, but on its own it changes
nothing here: these rounds abstain for the bracket and the `cluster` as well,
so all three have to go together.

---

## Things that are NOT on this list

These were once REVIEWs and are now genuinely verified — don't "fix" them
again:

| was | fixed by |
|---|---|
| sedge colourwork rows unreadable | #55 |
| more than one repeat group per row | #56 |
| mid-row `With Colour N`, `changing to … in the last chain` | #57 |
| a foundation row's counted runs (`8 Sc in next 8 chs`) | #58 |
| shell colourwork rows unreadable | #59 |
| `sc in centre dc of next shell` — a position inside a multi-stitch group | #63/#64 |

### On the shell case in particular

It headed this list until 2026-09-18, and the reason it is gone is worth
keeping, because the argument for *not* fixing it was a good one:

> **Why it is not just hardcoded.** The tool reads clause by clause; assuming
> "a shell is 5 dc" would be reading one row's arithmetic out of another row's
> text. It also stops being true the moment a pattern uses a 3-dc or 7-dc
> shell, and the instruction reads identically in all three cases — so the
> wrong answer would be silent.

That still holds, and the fix does not violate it. The width is not assumed;
it is read from the previous row's own recorded structure, which is why the
same row resolves to 3 over a 3-dc shell and 7 over a 7-dc one (there is a
test that drives exactly that). Every shell in the live corpus happens to be
5 wide, so the corpus alone could not tell a correct reading from a hardcoded
one — the test is what distinguishes them.

**Measured:** 74 shell rows across `Coaster (square) — shell, intermediate`
and `Throw Blanket — colourwork, shell` went from verified by nothing to
verified and passing. Nothing else in the 79-case sweep changed.
