# Known-unverifiable rows

Every REVIEW the batch suite currently reports, why the row cannot be checked,
and what it would take to change that. If a REVIEW you are looking at is on
this list, it has already been investigated — please don't re-derive it.

As of 2026-11-11 the list is **empty**. Before this change the batch matrix was
98 cases, 92 pass, 6 review, 0 fail. The 6 REVIEWs had two causes, and both are
now verified (see "Things that are NOT on this list" below): the scarf
fringe/tassel end-prep rows (3 cases) and the Granny Square Cluster (3 cases).
The first batch run after this ships is what confirms 98 pass.

A REVIEW means "this tool could not do the arithmetic", never "the pattern is
wrong". Every one of these has been read by hand and the pattern is correct.
The rule this whole tool follows is that a clause it cannot resolve returns no
answer and says why, because a wrong parse turns a warning into a false
accusation — see ARCHITECTURE.md. "Correct" means following the house
conventions in [`loopdreams/docs/crochet-conventions.md`](https://github.com/rinahayashi01-dev/loopdreams/blob/main/docs/crochet-conventions.md).

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
| Granny Square Blanket rounds 3–4, the Cluster's yield | 2026-11-11, read from the key |
| a scarf's `Fringe:`/`Tassels:` end-prep sc rows | 2026-11-11 |

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

### On the Cluster

It was item 1 from 2026-09-20 to 2026-11-11. `cluster` is a compound word with
no fixed ratio, so Rounds 3 and 4 abstained. The fix doesn't hard-code
"cluster = 1", because the word means different things in different
patterns. Granny patterns often call 3 separate dc a "cluster", and that is
three stitches. The yield is read from the pattern's own key: a named stitch
whose definition says it is *worked together in the same* st or space is one
stitch in one place (`abbreviations.one_stitch_tokens`). loopdreams keys it
"2 dc worked together in the same space". A key that doesn't say so, or says
"worked together over" several stitches (a decrease), still abstains.

Rounds 3 and 4 needed the stated repeat counts as well (loopdreams #577,
2026-09-26). Without them a known yield would still have left two unknowns
and one equation.

Also don't re-derive this: an earlier version of item 1 said the pattern
"disagrees with itself" (`stitch_count` 32 against "16 Clusters"). That was
wrong. 32 was the dc worked, for the yarn estimate. loopdreams #562 split it
into `stitch_count: 16` and `yarn_stitches: 32`.
