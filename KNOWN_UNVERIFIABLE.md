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
accusation — see ARCHITECTURE.md. "Correct" means following the house
conventions in [`loopdreams/docs/crochet-conventions.md`](https://github.com/rinahayashi01-dev/loopdreams/blob/main/docs/crochet-conventions.md).

---

## 1. Granny Square Blanket rounds 3–4 — the Cluster's yield

**Affects:** `Granny Square Blanket — beginner / intermediate / advanced`
(3 cases)

Reported as:

- Round 3: `'cluster' has no fixed consumes/produces ratio`
- Round 4: `a stitch in this group worked into one spot has no fixed
  consumes/produces ratio` (its `[Cluster, ch 1, Cluster] in next ch-1 sp`)

Rounds 5 and 6 of the same patterns verify; only the two Cluster rounds
abstain.

**The one remaining cause: the tool does not know that a Cluster makes one
stitch.** `cluster` is defined in the pattern's own abbreviation key, so it is
read as a custom compound stitch with no fixed ratio (`produces=None`), and a
clause with an unknown yield stops the round before any repeat arithmetic runs.
To a maker the answer is not in doubt. The key defines it as *"2 dc worked
together in the same space"*, a completed Cluster is ONE stitch (the loops are
closed with a single final loop), and the round says so itself:
`(16 Clusters, 16 ch-1 sps)`.

**There used to be a second cause, and it is gone.** Until loopdreams #577
(2026-09-26) both rounds said "rep from * around" with no number. They are
worked into the previous round's spaces, so there was no usable in-count to
solve the repeat from either. That was two unknowns and one equation, and
knowing the Cluster's yield would not have been enough on its own. #577 now
states the repeats ("rep from * 14 more times, ch 1" / "6 more times, then *
to ** once, ch 1") for the maker's sake, and that removed this cause.
Measured on 2026-09-26 by swapping `Cluster` for a stitch of known yield (`dc`)
in each version:

| row text | result | +1 on the declared count |
|---|---|---|
| before #577 ("rep from * around") | REVIEW, *repeat group does not state how many times it is worked* | not caught |
| after #577 (stated repeats) | PASS, 0 warnings | caught on both rounds |

So the Cluster's yield is now the only thing between these rounds and full
verification. This entry used to say "a stated repeat count would change it",
and that was half right: the count was necessary but not sufficient.

**An earlier version of this entry said the pattern "disagrees with itself",
because the round's `stitch_count` was 32 against its stated 16 Clusters.
That was wrong** and is worth recording so it is not re-derived: 32 was the dc
actually worked, which the yarn estimate needs, and it was simply sharing a
field with the count a maker checks. The generator now states both separately
(`stitch_count: 16`, `yarn_stitches: 32` — loopdreams #562), and these two
rounds still abstain. Correcting the count did not change this result, which
was verified before the change was made.

**What would change it:** a yield for `cluster` that the tool can actually
know. That is now a parser feature, not a pattern change. It must not be
hardcoded as "cluster = 1": the word means different things in different
patterns (a 3-dc or 5-dc cluster is still one stitch, but a pattern may also
use "cluster" loosely for a group of separate stitches). The honest source is
the pattern's own key. A definition saying the stitches are *worked together*
describes a joined cluster, which is one stitch whatever it is made of. That
follows the same rule as the shell fix below: read the fact from the pattern,
never assume it. Granny squares commonly call a group of 3 separate dc a
"cluster", so a key definition that does *not* say "together" must still
abstain.

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
