# Known-unverifiable rows

Every REVIEW the batch suite currently reports, why the row cannot be checked,
and what it would take to change that. If a REVIEW you are looking at is on
this list, it has already been investigated — please don't re-derive it.

As of 2026-09-20: **79 cases — 76 pass, 3 review, 0 fail.** All 3 REVIEWs come
from the single cause below.

A REVIEW means "this tool could not do the arithmetic", never "the pattern is
wrong". Every one of these has been read by hand and the pattern is correct.
The rule this whole tool follows is that a clause it cannot resolve returns no
answer and says why, because a wrong parse turns a warning into a false
accusation — see ARCHITECTURE.md.

---

## 1. Granny Square Blanket rounds 3–4 — an undeclared `cluster`

**Affects:** `Granny Square Blanket — beginner / intermediate / advanced`
(3 cases)

Reported as `'cluster' has no fixed consumes/produces ratio`. Rounds 5 and 6
of the same patterns verify; only the two Cluster rounds abstain.

**`cluster`** is a named group whose stitch count the pattern never settles.
The abbreviation key defines it as *"2 dc worked together in the same space"*,
which normally yields ONE stitch — but the round declares
`(16 Clusters, 16 ch-1 sps)` while its own stitch count is **32**, i.e. two
per Cluster. The pattern says both things, so the tool cannot pick one without
guessing, and the round states its repeat as "rep from * around" with no
number, so there is no second equation to solve it from either.

Unlike `bobble`, which the tool solves algebraically across many rows that each
declare their own counts, these rounds do not give it enough independent
equations.

**What would change it:** a pattern that agrees with itself. Either the
declared count counts Clusters as one stitch each, or the abbreviation says a
Cluster is two separate dc. This one is arguably a finding about the pattern
rather than a gap in the tool — worth raising with the generator before
teaching the checker to prefer one reading.

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
| `[3 dc, ch 2] 3 times in ring` — a bracket of mixed stitches | #68 |
| `in the same sp` on a motif round | #68 |
| `then * to ** once` — a square's fourth side | #68 |
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
