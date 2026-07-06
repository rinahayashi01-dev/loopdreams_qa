# LoopDreams pattern QA tool — architecture & decisions log

Keep this file updated as we make decisions. Drop it in the project's
knowledge files so any new chat in this project has it, even without
conversation memory.

## What this tool does
Automatically QA-checks AI-generated crochet patterns (PDF or Word) before
they go to testers/customers. Three check categories:
1. **Stitch-count math** — do round/row counts add up given the stated inc/dec?
2. **Terminology consistency** — does the pattern stick to its declared US/UK convention?
3. **Completeness** — missing turning chains, ambiguous repeats, undefined
   abbreviations, missing gauge/yarn/hook info, missing finishing steps.

## Decisions made so far
- **Language/stack**: Python. `python-docx` for Word, `pdfplumber` for native
  PDF text, `pdf2image` + `pytesseract` (+ system `tesseract`) for OCR fallback
  on scanned/image-based PDF pages. All confirmed available in the build
  environment already — no new installs needed.
- **Stitch-count parsing**: stitch-by-stitch, not just keyword/delta sanity
  checks. Each clause in a round ("sc in next 3", "2 sc in next st", "inc",
  "dec", "skip 2") is tokenized into an exact consumes/produces count.
- **Unstated repeat counts are solved algebraically, not guessed.** When a
  round uses "*...* repeat from * around" or "sc in each st around" with no
  explicit number, the checker solves for the repeat multiplier using the
  previous round's count and/or this round's declared count, then
  cross-checks both. If the multiplier doesn't come out to a clean
  non-negative integer, or the two equations disagree, that's reported as a
  real stitch-count error — not silently passed or guessed at. If 2+
  unstated repeats appear in one round, it's flagged as unverifiable rather
  than guessed.
- **Terminology check only treats genuinely unambiguous abbreviations as
  proof of US vs UK convention**: `sc`, `hdc`, `sc2tog`, `hdc2tog` (US-only)
  and `htr`, `ttr`, `htr2tog`, `dtr2tog` (UK-only). Bare `dc`, `tr`, `dtr`,
  `dc2tog`, `tr2tog` exist in both systems with different meanings and are
  deliberately NOT used as standalone proof of mixing — see
  `abbreviations.py` docstring. This avoids false positives at the cost of
  not catching every possible mixing case; revisit if that gap matters in
  practice.
- **Run mode**: CLI now (`python -m loopdreams_qa.cli path/to/pattern.docx`),
  one file at a time. A batch wrapper looping over a folder is the planned
  next step, built on top of the same `cli.run()` function so nothing in the
  core pipeline needs to change for it.

## Current scope / known limitations (V1)
- Only one repeat group (`*...*` or `[...]`) is parsed per round/row. A
  second one in the same round is flagged as unsupported rather than guessed.
- No nested repeat groups.
- Chain stitches never count toward the stitch total, even in patterns that
  count chain spaces (e.g. some granny-square styles). Could cause false
  positives there — revisit if it comes up.
- "Missing turning chain" detection is a light heuristic (row-based pattern +
  tall stitch + no leading `ch N`) — flagged as a warning, not an error,
  since standing stitches and other techniques are legitimate exceptions.
- Section detection (materials/gauge/abbreviations/instructions/finishing)
  relies on the document having a line that's basically just that heading.
  LoopDreams output should be consistent enough for this, but worth
  revisiting once we see real generated output.
- Abbreviation-key parsing handles `abbr - definition` / `abbr: definition` /
  `abbr = definition` style lines, comma-separated or one per line.
- **Custom compound-stitch tokens (added batch six) assume the Abbreviations
  section appears before Pattern Steps/Finishing in the document** — true
  in every real sample seen so far, and `parse()` processes sections in
  document order, so `pattern.abbreviation_key` is already populated by the
  time instructions/finishing are tokenized. If a future sample ever
  declares abbreviations after the rows that use them, those custom tokens
  would silently fall back to unrecognized rather than being picked up —
  revisit if that ordering shows up in practice.

## Project layout
```
loopdreams_qa/
  abbreviations.py      US/UK term tables + per-stitch consumes/produces math
  models.py              Pattern / Section / RoundRow / StitchClause / Issue dataclasses
  stitch_parser.py        Tokenizes one round/row's text into clauses
  pattern_parser.py        Raw text -> sections, abbreviation key, declared system, rounds
  extraction.py             PDF/docx -> raw text, with OCR fallback for scanned PDF pages
  report.py                  Pattern + issues -> JSON-able report / human-readable text
  cli.py                      Entry point: extract -> parse -> check -> report
  checks/
    stitch_count.py            The round-by-round algebra solver
    terminology.py              US/UK consistency check
    completeness.py             Missing sections / undefined abbrs / unclear repeats / etc.
  tests/
    test_pipeline.py             Regression tests (run: python -m unittest discover -s tests)
```

## Next steps (not yet built)
- Batch wrapper over a folder of patterns, reusing `cli.run()`.
- Decide on output format for batch runs (one JSON per file? one combined
  CSV/spreadsheet for a tester to skim?).

## Real LoopDreams sample validated against (Jun 26, 2026)
First real generated output seen: `loopdreams-scarf-jun-26.pdf` (a 2-color
shell-stitch scarf with a sc border). Ran the full pipeline against it
end-to-end successfully. Findings:

- **Code itself does not persist between chats** — only this file does (it's
  in the project's knowledge files). Each new chat that needs to actually
  run the tool has to rebuild `loopdreams_qa/` from this spec first. Worth
  exporting the working tree as a zip from any session where it's in good
  shape, so a future chat can restore it instead of rewriting from scratch.
- **New extraction-format wrinkles confirmed working**: abbreviation key
  using `·` (middot) as the entry separator instead of commas; en-dash row
  ranges (`Rows 1–198:`); em-dash before a color name (`With Colour A —
  Honey:`); PDF page header/footer noise (timestamp+filename, URL+page
  number) from a web-exported PDF, now stripped before parsing.
- **Gap found — compound/decorative stitches**: the existing abbreviation
  model only had fixed consumes/produces ratios for simple stitches
  (sc/hdc/dc/tr/inc/dec/etc.). Real output used `sh st = shell stitch` —
  defined as a *name* in the abbreviation key, but the construction (how
  many stitches per shell, stitches skipped) was never given anywhere, so
  no consumes/produces ratio could exist for it at all. Added a distinct
  "compound stitch" concept (`COMPOUND_STITCH_WORDS` in `abbreviations.py`):
  these stitches can only be checked if the pattern itself states the
  construction (detected heuristically by checking whether the
  abbreviation's definition text contains a digit). If not, every row using
  that stitch is flagged unverifiable (stitch-count, warning) AND a
  completeness error is raised naming the missing construction — this is a
  more specific, more useful flag than a generic "undefined abbreviation"
  would have been, since the abbreviation key technically does have an
  entry for it.
- **Gap found — composite border/repeat structures**: real border
  instructions combined a `*...* rep from * around` group with a *separate*
  additive rule stated outside the asterisks ("working 1 sc per row-end
  along each side edge"), and never stated the number of corners the repeat
  travels around. This is one step beyond the single-clean-repeat-group
  algebra solver in V1's design — solving it would require assuming a
  corner count (4) that isn't actually in the text, which the project's
  stated philosophy explicitly rules out (no guessing). Resolved by treating
  "repeat group + separate additive rule, with an unstated multiplier" as
  its own unverifiable case, distinct from the plain unsolvable-multiplier
  case already covered. Still V1 scope — not solved, correctly flagged.
- **Gap found — approximate final counts**: the sample stated its border
  count as `(~876 sts)` even though the count is fully determined by
  fixed row counts and a fixed per-row stitch count (and in this case the
  natural hand-computation matches 876 exactly — the `~` adds false
  uncertainty rather than reflecting real uncertainty). Added a
  completeness check flagging `~`/`approx` notation on any final declared
  count as worth a clarity nit, since it can mask a real miscount.
- **Turning-chain heuristic note**: this sample puts `ch 3, turn` at the
  *end* of each row rather than the start. Confirmed this should NOT be
  flagged as a missing turning chain — it's a legitimate, if less common,
  phrasing convention. The "missing turning chain" heuristic needs to check
  for a chain anywhere in the row text near a turn, not just a leading
  `ch N`, or it would false-positive on patterns written this way.
- **Not yet encoded as an automated check, flagged manually this round**:
  this sample's row count (198 rows + 198 rows = 396 rows total before the
  border) is an unusually large, suspiciously exact 50/50 split for a
  scarf. Plausible (≈72 in at this gauge) but exactly the shape of an AI
  generation duplication artifact. Didn't bake a "suspiciously round
  row-count split" heuristic into the checker since it doesn't cleanly fit
  any of the three documented check categories and risks being a pure
  guess — flagged conversationally instead. Revisit if this pattern (heh)
  recurs across more real samples.

## Second real-sample batch (Jun 27, 2026) — 7 patterns: sc, hdc, dc, moss,
## sedge, shell, waffle
Much richer real output than the first sample. Required substantial parser
work; all of it now built and passing against this batch.

- **New section type**: LoopDreams output now includes a `STITCH GUIDE`
  section (between Materials and Abbreviations) with prose + a worked
  example for the pattern's named stitch, sometimes including a `Stitch
  multiple: ...` line. Added `"stitch guide"` to `SECTION_HEADERS`. Not
  deeply parsed yet (no construction-extraction from its prose) because
  this batch's body rows all spell out literal stitch components directly
  (e.g. `(sc, hdc, dc) in next st`) rather than hiding behind an
  unexplained compound abbreviation like Jun 26's `sh st` — so the existing
  per-component math already covers it. Revisit if a future sample names a
  compound stitch in the body *without* spelling out components, the way
  Jun 26's shell stitch did.
- **`Foundation:` vs `Foundation chain:`** — both spellings now seen in the
  wild; marker regex broadened to accept either.
- **"Repeat Row(s) P[-Q]." shorthand**: rows are now frequently written as
  `Rows 3–88: Repeat Row 2.` with no restated stitch count at all. These
  never match the normal counted-row regex (no trailing `(N sts)`), so they
  need their own regex pass or they silently vanish from the parsed
  pattern. Added one. These rows aren't independently re-verified (the
  referenced row already was, the first time its text appeared) — they're
  used only for row-numbering continuity and total-row-count bookkeeping
  (e.g. for border math that depends on total row count).
- **Regex bug found and fixed**: the original counted-row regex's lazy
  `(.*?)` had no guard against crossing into the *next* `Rows? N:` marker,
  so when scanning hit a bare "Repeat Row" line (no count of its own), it
  would skip straight past it and silently attach a *later* row's declared
  count to the wrong row label. Fixed with a negative-lookahead guard so
  the lazy match can never cross a row marker. (This was a real bug, not a
  pattern defect — worth remembering if row parsing ever looks subtly
  wrong again.)
- **New border notation — and it's fully solvable**: this batch's border is
  `[3 sc in corner, sc in each st across flat edge] twice (top and bottom
  edges), [3 sc in corner, working 1 sc per row-end along side edge] twice
  (left and right edges)`. Unlike Jun 26's `*...* rep from * around` (
  unstated multiplier, flagged unverifiable), this states its multiplier
  explicitly (`twice`) and cleanly separates the two edge types. Added
  bracket-group parsing (`[...]  <multiplier>`) with a small word-to-number
  table (`once`/`twice`/`N times`). Border math now verifies exactly
  against the declared count on all 7 samples — first real win for a fully
  *confirmed* (not just "not disproven") stitch count.
- **New clause shapes added to the tokenizer**: parenthesized multi-stitch
  clusters sharing one target spot (`(sc, hdc, dc) in next st`); a leading-
  count version of the same (`5 dc in next st`, `2 dc in first sc`);
  generic single-instance positional clauses (`sc in first st`, `dc in top
  of ch`); post-stitch clauses (`fpdc around next st` / `around next 2
  sts`); a counted turning chain (`Ch 2 (counts as dc)` — produces 1,
  unlike a plain chain); `skip first st` (no explicit number). Also had to
  paren-protect the comma split in the tokenizer itself, since a naive
  split was tearing `(sc, hdc, dc) in next st` apart at the internal
  commas.
- **Gap found — chain-counting convention varies by stitch**: moss/linen
  stitch (`sc, *ch 1, skip 1 st, sc in next st; rep*`) declares a stitch
  count that **includes** its ch-1 spaces as counted stitches, unlike every
  other chain in this corpus (turning chains, which never count). This is
  exactly the ambiguity flagged as a known limitation after the first
  sample ("chain stitches never count... could cause false positives
  there"). Resolved by trying both conventions when a repeat unit's
  produced-count doesn't match the declared count: chains outside a repeat
  unit (PRE/POST zones, i.e. turning chains) still never count; a chain
  *inside* a repeat unit gets a second look counted as a real stitch
  before the mismatch is reported as an error. Avoids hardcoding either
  convention globally.
- **Gap found — positional "landmark" references don't fit the simple
  consumes model**: shell stitch's `sc in the centre dc of the next shell`
  names one specific stitch (the 3rd of 5 dc) inside a multi-stitch group,
  implicitly passing over the rest of that group without ever saying
  "skip" — completely unambiguous to a human crocheter, but the true
  number of previous-row stitches it passes over depends on the named
  group's width (5, in this case), which isn't reliably inferable from
  text alone. Modeling this as "consumes 1" produced a confident but wrong
  stitch-count *error* on a totally valid, idiomatic pattern — a real
  false positive, caught by hand-checking the math before trusting the
  tool's first answer. Fixed by leaving `consumes` unset (unverifiable) for
  this clause shape rather than guessing 1. Flags as a warning instead of
  a (wrong) error. This is the kind of mistake that matters most to avoid,
  since a QA tool that cries wolf on valid patterns gets ignored on real
  ones.
- **Gap found — row-numbering gaps**: both the shell and waffle samples
  jump straight from `Rows 90–178: ... Repeat Rows 2–3.` to `Row 180:`,
  never writing Row 179 at all. Added a generic row-coverage gap check
  (sorts all body rows by row number, flags any break in the sequence).
  Caught real, identical bugs in two independently-generated samples — same
  underlying generation defect, not a one-off.
- **Gap found — missing fasten-off before the border**: the sc/hdc/dc
  tutorial samples never include a "fasten off" instruction anywhere in
  the body, even though the border re-joins with a fresh strand. Added a
  check: if no row anywhere in the body has a fasten-off clause, flag it.
- **Gap found — duplicated/contradictory turning chain**: sc/hdc/dc's
  colour-join row (e.g. `DC in each st across, ch 3, turn.. At end of this
  row, join Colour B — Moss. Ch 1, turn.`) keeps the row's own template
  ending (`ch 3, turn`) *and* appends a second, different chain+turn for
  the colour join — two separate turning instructions in one row, leaving
  it unclear which is real. (The other 5 samples in this batch don't have
  this bug — their colour-join row replaces the row's normal ending rather
  than keeping both, so this is specific to how sc/hdc/dc's join-row was
  generated, not a universal LoopDreams behavior.) Added a check counting
  `turn` clauses per row; >1 is flagged.
- **Gap found — ambiguous foundation row**: sc/hdc/dc's Row 1 says `SC/HDC/
  DC in each st across` directly off the foundation chain, never stating
  which numbered chain to start in (the other 5 samples explicitly say
  "in 2nd ch from hook" or similar). The stated counts are numerically
  consistent with the standard skip-N-for-turning-chain convention, but
  since the row never actually says so, scaling the foundation chain count
  1:1 to verify it would risk a confident wrong answer (or right answer
  for the wrong reason). Now treated as a dedicated unverifiable case
  (distinct from a normal row-to-row each-st-across check, which still
  verifies normally) plus a completeness clarity flag.
- **Confirmed clean**: terminology checking stayed correct across all 7 (no
  false positives) even with the new `fpdc` stitch and the unusual `sh
  st`-free, components-spelled-out style of sedge/shell.

## Third real-sample batch (Jun 28, 2026) — 3 patterns: tote bag (dc, hdc, sc)
First sample with a second component (handles) and no border. All FAIL on
the same two issues; everything else (panel rows, handle chain math) checks
out cleanly once a couple of new format wrinkles were handled.

- **New noise pattern — duplicated stitch-count annotation**: this batch
  states its count twice in a row, e.g. `(70 sts) (70 sts)`, and for the
  colour-join row the two occurrences aren't even adjacent —
  `... (70 sts). At end of this row, join Colour B — Moss. ch 1, turn.
  (70 sts)`. The counted-row regex's guarded-lazy match was stopping at
  the *first* occurrence, which truncated the colour-join row's text
  before its own `ch 1, turn` was even captured (silently hiding a real
  duplicate-turn case from the row-content the checker could see). Fixed
  by making that capture group greedy instead of lazy (still bounded by
  the existing "don't cross another `Row N:` marker" guard), so it now
  grabs the *last* `(N sts)` before the next row marker rather than the
  first.
- **New construction type — a second component embedded in the row
  sequence**: this pattern has no `Finishing` section at all. Instead,
  assembly instructions and a "Handles (make 2)" sub-pattern are given
  literal `Row 81:` / `Row 82:` labels, continuing the main panel's row
  numbering, each with a bogus/unrelated declared stitch count tacked on.
  `_check_finishing_present` already correctly flags the missing Finishing
  section (as an error), but that alone doesn't capture *why* — added a
  new check, `_check_non_stitch_rows`, that flags any numbered row whose
  text contains zero recognizable stitch clauses (only chains/turns/
  unrecognized text): a strong signal the "row" isn't actually a stitch
  row. Caught both Row 81 (assembly) and would have caught Row 82 too, if
  Row 82 hadn't also contained genuinely parseable stitch content (next
  point).
- **Real bug found and fixed — a second component's own foundation chain
  was checked against the wrong row's count**: Row 82 ("Handles (make 2):
  Ch 53. DC in 4th ch from hook and each ch across...") starts a *brand
  new* foundation chain mid-row, unrelated to the main panel's running
  stitch count (70). The checker was naively using the previous row's
  declared count (70) as the "foundation chain" input for this row's
  `foundation_into_chain` math, which would have produced a confidently
  *wrong* error (70 − 3 = 67 ≠ declared 50, when the real chain stated
  right there in the row, 53, gives exactly 53 − 3 = 50). Fixed by
  detecting an inline `chain` clause earlier in the *same* row and using
  *that* count instead of the cross-row running total when one is present.
  All three samples' handle math (53→50 dc, 52→50 hdc, 51→50 sc) now
  verifies correctly and silently.
- **Parser robustness fix**: added `:` to the paren-protected clause
  splitter. Labels like `Handles (make 2):` and `Assembly:` were gluing
  onto the instruction text that followed them (e.g. `"Handles (make 2):
  Ch 53"` as one unsplittable blob), which would have hidden the handle's
  otherwise-correct chain math entirely.
- **Minor wording tolerance**: the handle instruction says "and **each** ch
  across" (missing "in") instead of "and **in** each ch across" used
  everywhere else. Treated as harmless phrasing variance, not a real
  ambiguity (unlike the Row-1-without-an-ordinal case) — made "in"
  optional in that one spot rather than flagging it.
- **Retroactive win**: re-running the now-more-rigorous checks against the
  Jun 26 and Jun 27 samples picked up two more real, previously-missed
  issues on the Jun 26 sample alone (no `fasten off` before its border;
  Row 1's `sh st in each st across` is *also* ambiguous about which
  chain to start in, on top of the already-flagged undefined
  construction) — confirms the new completeness checks generalize rather
  than being overfit to one sample.
- **All 3 patterns: FAIL**, on the same two issues — missing Finishing
  section / non-stitch rows 81-82, and a duplicated-turn-chain on each
  pattern's colour-join row (Row 39, same root cause as the Jun 27 sc/hdc/
  dc tutorial samples: template splicing keeps the row's own ending chain
  *and* appends a second one for the colour join).
- Foundation-row ambiguity (Row 1, no stated chain ordinal) does **not**
  recur here — all three give the ordinal explicitly ("2nd"/"3rd"/"4th ch
  from hook"), unlike the Jun 27 sc/hdc/dc tutorial samples. Worth noting
  since it shows the gap isn't universal to "tutorial-style" LoopDreams
  output, just inconsistent.

## Fourth real-sample batch (Jun 29, 2026) — 3 patterns: tote bag (dc, hdc, sc)
LoopDreams output has visibly evolved since Jun 28 — two of that batch's
issues are gone, but a new one took their place. No checker code changes
were needed this round; the existing pipeline handled the new wrinkle
correctly on the first run.

- **Two Jun 28 bugs appear fixed on LoopDreams' side**: no more duplicated
  `(70 sts) (70 sts)` count annotation, and the colour-join row (Row 39)
  now correctly *replaces* its own ending chain+turn with the join's
  chain+turn instead of keeping both — no duplicate-turn issue this round.
- **Assembly correctly moved into a real `Finishing` section** this time
  (`Finishing` / `Assembly: Fold panel in half...`), instead of being
  numbered as a fake pattern row the way Jun 28's Row 81 was. Since this
  Finishing text has no trailing `(N sts)`, `_parse_finishing` correctly
  leaves it as section prose rather than a phantom RoundRow — no change
  needed there.
- **New bug — Row 81 is now a true numbering gap**: with Assembly no
  longer occupying a row slot, the pattern jumps straight from `Row 80` to
  `Row 82` (the handles component), never reusing 81. The existing
  row-coverage gap check (built for Jun 27's shell/waffle Row 179 gap)
  caught this immediately with no changes — same underlying generator
  habit (component/assembly content nudges row numbers around without the
  rest of the numbering being corrected) as Jun 28, just manifesting as a
  hole instead of a mislabeled row.
- **All 3 patterns: FAIL, on exactly this one issue** — single error, zero
  warnings, across all three. Cleanest result yet on a non-PASS sample:
  one real, genuine defect, no noise.
- Handle chain math (53→50 dc, 52→50 hdc, 51→50 sc) and the rest of the
  panel verify silently again, confirming the Jun 28 fixes (inline
  foundation-chain detection, `:` clause-splitting) generalize to this
  near-identical-but-not-identical sample rather than being a one-off fit.

## Fifth real-sample batch (Jun 29, 2026, second upload) — 3 patterns:
## tote bag (dc, hdc, sc), 3-color beginner variant
Same filenames as the fourth batch, but a genuinely different pattern (3
colours instead of 2, "Forming the Body"/"Creating Handles" prose
sub-headers instead of fake row numbers). No row-gap issue this time —
handles are no longer numbered as a row at all.

- **New gap — a component with no expected stitch count**: the handles are
  now written as plain prose under `Finishing` ("Handles (make 2): Ch 43.
  DC in 4th ch from hook and each ch across..."), with **no trailing
  `(N sts)`** at all. Previously (Jun 28/29 first upload) this same
  construction was numbered as a fake row and always ended in `(50 sts)`.
  Since there's nothing to compare against, this wasn't even being
  *parsed* before — `_parse_finishing` only recognized `Border:`. Added a
  parallel pass recognizing `"<Name> (make N): ..."` as a secondary
  component, capturing its construction whether or not a count is stated,
  and a new completeness check (`_check_missing_component_count`) that
  flags it specifically when one isn't: gives real, verifiable stitch
  instructions but never states a target to verify against.
- **Verified anyway**: even with no stated target, the construction itself
  computes cleanly using the same inline-foundation-chain logic from Jun
  28 (43→40 dc, 42→40 hdc, 41→40 sc) — there's just no declared count in
  the text to confirm it against. The check reports the gap; it doesn't
  invent the missing number.
- **Regex bug found and fixed**: the section's own sub-header text
  ("Creating Handles") sits immediately before the real label ("Handles
  (make 2):"), and a loose label-capture regex grabbed both as one label
  ("Creating Handles Handles (make 2)"). Fixed by requiring the captured
  label to be exactly one capitalized word, which correctly skips past
  the sub-header to the real label.
- Generalized the row-gap / fasten-off / duplicate-turn / non-stitch-row
  checks to exclude any non-body construct by `row_start <= 0` (Border was
  -1; this new component type is -2) rather than only excluding Border by
  name, so they don't misfire against components that aren't body rows.
- **All 3 patterns: REVIEW** (0 errors, 1 warning each) — the only finding
  is the missing handle stitch count. Panel rows, colour joins, and
  fasten-off are all clean.

## Sixth real-sample batch (Jun 29, 2026, third upload) — 4 patterns:
## tote bag (bobble, dc, hdc, sc)
Same panel/handle structure as the fourth and fifth batches (individually
numbered rows for bobble; "Repeat Row N" shorthand for dc/hdc/sc; handles
as Finishing prose with a stated count). New stitch this time: a custom
`bo` abbreviation for bobble stitch. Two real tool gaps found and fixed;
two real pattern defects found (not tool bugs) on the dc and hdc variants.

- **Real pattern defect — dc and hdc foundation-chain math is wrong**: all
  four patterns share the same `Foundation: Ch 71.` line, which is only
  correct for the sc variant (`SC in 2nd ch from hook` → 71 − 1 = 70,
  matches the declared `(70 sts)`). The dc variant works `DC in 4th ch
  from hook` (71 − 3 = 68 ≠ 70) and the hdc variant works `HDC in 3rd ch
  from hook` (71 − 2 = 69 ≠ 70) — both declare 70 anyway. Looks like the
  foundation chain count was copy-pasted from the sc template without
  adjusting for the extra chains taller stitches skip. **Genuine LoopDreams
  generation defect, correctly caught** — first real, clean single-root-
  cause stitch-count error this checker has produced (previous batches'
  findings were all completeness/structural, not raw foundation math).
  sc variant: clean, **PASS** with zero findings.
- **Tool gap found — a pattern's own custom abbreviation for a compound
  stitch was invisible to the tokenizer**: the bobble variant defines `bo
  = bobble (5 incomplete dc in same st, yo pull through all loops)` in its
  abbreviation key and uses `BO` throughout the body, alternating with
  `sc`. Every clause-shape regex matches against a **hardcoded** global
  word list (`STITCH_MATH` + `COMPOUND_STITCH_WORDS` + the literal words
  "shell"/"bobble"/"puff"/etc.) — a pattern's own shorthand for one of
  those concepts was never in that list, so `BO in next st` matched
  nothing and fell through to generic `unknown`/"unrecognized clause"
  noise. Worse, because the clause's `.stitch` field was never populated,
  the completeness check's abbreviation-usage scan never saw `bo` as a
  stitch at all — it couldn't even confirm the construction was (correctly)
  stated, so neither the right "compound stitch, no fixed ratio" warning
  NOR a sanity check on the construction ever ran. **Fixed**: added
  `abbreviations.custom_compound_tokens(abbr_key)`, which scans a pattern's
  own abbreviation-key definitions for one of the known compound-stitch
  words (e.g. "bobble" inside `bo`'s definition) and returns the matching
  custom token(s). `stitch_parser.py` now builds its stitch-word regex
  alternation **per pattern** (base hardcoded words + that pattern's custom
  tokens), cached per distinct token set so this doesn't cost anything
  across the ~80 rows of one pattern. `completeness.py`'s compound-stitch
  detection now also checks the same custom-token set, so the
  digit-in-definition heuristic correctly applies to `bo`'s own definition
  text rather than never firing. Net effect on this sample: `bo`'s
  definition contains a digit (`5`), so the construction is correctly
  treated as stated (no false "undefined construction" error) — but since
  it's still free-text prose, not a fixed ratio, every row using `bo` is
  still correctly flagged unverifiable. This is the intended, honest
  result for a real compound stitch with a real (if prose-only)
  construction, not a regression.
- **Tool gap found — new clause shape, `<stitch> in each of (the)
  first/last N sts`**: the bobble pattern's brick-offset rows (alternating
  between starting the bobble repeat at st 1 vs st 2) write their
  non-repeated edge stitches this way (`SC in each of first 2 sts ... SC
  in each of last 2 sts`), distinct from the existing `in next N` and
  plain `in first/last st` shapes. Neither matched before. **Added** a new
  regex (`each_of_position`) with the same literal-count math as the
  existing `in next N` clause shape.
- **Tool gap found and fixed — same fix exposed a noise problem**: with
  both gaps above fixed, the bobble pattern's `bo` rows (40 of 80) would
  each independently produce an identical "cannot verify: 'bo' has no
  fixed consumes/produces ratio" warning — technically correct, but a wall
  of 40 repeated sentences that buries any other real finding, exactly the
  "QA tool that cries wolf... gets ignored" failure mode the project has
  flagged as the one to avoid since the second batch. **Added** a generic
  de-duplication pass in `stitch_count.check()`: 3+ stitch-count warnings
  that share the *exact same* underlying reason text are collapsed into
  one issue naming every affected row, rather than one issue per row. This
  doesn't drop or weaken any detection — every affected row is still named
  in the combined message — it only changes how many times the identical
  sentence is printed. Threshold of 3 chosen so genuinely-occasional
  unverifiable rows (1-2) still get reported individually with full
  row-specific context.
- **All fixes spot-checked against pre-existing compound-stitch paths**
  (hardcoded `sh st`, paren-clusters `(sc, hdc, dc)`, centre-dc landmark
  references) to confirm no regression — all unchanged. Bundled regression
  test (`test_pipeline.py`, Jun 26 scarf sample) still passes/skips
  identically (sample file isn't bundled in the zip, same as every prior
  batch).
- **Final batch result**: dc — **FAIL** (1 error, the foundation-chain
  defect above); hdc — **FAIL** (1 error, same root cause); sc — **PASS**
  (clean); bobble — **REVIEW** (1 warning, the inherent bo-construction
  unverifiability, correctly de-duplicated to a single issue instead of
  40). Handle math (Ch 51 → 50 sc) verifies silently on all four, same as
  every batch since the inline-foundation-chain fix in batch three.

### Addendum (same batch) — solving compound-stitch ratios algebraically
Asked directly: "how do we make the bobble REVIEW verifiable instead of
just unverifiable?" Answer turned out to extend a technique already in the
codebase, not invent a new one.

- **The insight**: a compound stitch's CONSUMES value is usually
  grammar-determined regardless of which stitch is named — `"<stitch> in
  next st"` (singular) means exactly one previous-row stitch is targeted,
  full stop, whether that stitch is `sc` or an undefined `bo`. Only
  PRODUCES (what that one stitch leaves behind — 1 for a plain decorative
  substitute, more for a fanned-out construction like shell) genuinely
  depends on the stitch and can't be assumed. `stitch_parser.py`'s
  `simple_positional`, `around_post`, and `top_of_chain` clause shapes
  previously set BOTH to `None` for any compound stitch, conflating "we
  don't know consumes" with "we don't know produces" — fixed to set
  consumes from the clause's own grammar even when the stitch is compound,
  leaving produces as the one real unknown. (`centre_dc` is deliberately
  untouched — that clause genuinely can't fix even consumes from grammar
  alone, per its original design.)
- **The consequence**: once consumes is always known, the repeat count in
  a row like `*BO in next st, SC in next st; rep from *...` is solvable
  independent of `bo`'s produces value (exactly the existing
  unstated-repeat-multiplier algebra) — which leaves the row's own
  declared count as one equation in exactly one remaining unknown:
  `bo`'s produces. Solvable the same way an unstated repeat count already
  is, not guessed.
- **Added `_solve_compound_ratios`** (`checks/stitch_count.py`): scans every
  row for this single-degree-of-freedom case (repeat-group rows, flat
  sequences, and `each_st_across/around` rows all handled), solves where
  possible, then cross-checks every row's answer against every other row
  using the same token:
  - **All agree** → resolved. Reported as an `info`-severity issue (doesn't
    count toward errors/warnings, so it doesn't change PASS/REVIEW/FAIL on
    its own) explicitly stating it's a *solved*, not stated, value, naming
    every contributing row. The resolved value is then substituted in
    everywhere that token appears — including rows that didn't contribute
    an equation — so they get genuinely *verified*, not just assumed
    clean.
  - **Disagree** → a real `error`, naming exactly which rows imply which
    conflicting values. This is strictly more useful than "unverifiable"
    — it's now an actual, pinpointed pattern defect (the kind of thing a
    real generation bug would produce: e.g. an inconsistent stitch count
    somewhere in the body).
  - **No row can supply a clean equation** → token stays unresolved,
    falls back to exactly the same honest "unverifiable" warning as
    before this feature existed. Never forces a non-integer or negative
    "solution."
  - Synthetic-case tested: contradictory rows correctly raise the error
    (with both conflicting values and source rows named) while still
    leaving each contributing row's own per-row warning intact for
    traceability; a single solvable row with no other occurrences resolves
    correctly on its own (cross-row agreement is a bonus, not a
    requirement, when there's only one equation to begin with).
- **Real result on the bobble sample**: all 40 rows independently solve to
  the same value — `bo` produces exactly 1 stitch (i.e. it's a true
  decorative *substitute* for a plain stitch, not a fan/increase, which
  matches what "drawn together in one stitch" / "one bobble made" in the
  pattern's own construction text describes, though that text was never
  parsed — only the row math was). **Status upgraded from REVIEW to
  PASS**, with one `info` note disclosing exactly how and from which rows
  the ratio was derived.
- Spot-checked for regressions: dc/hdc/sc (no compound stitches) produce
  byte-identical results to before this change. Hardcoded `sh st`,
  paren-clusters, and the centre-dc landmark case all spot-checked
  unchanged. Bundled regression test still passes/skips identically.
- **Noted, not fixed**: while reading `stitch_parser.py`'s `corner` clause
  handling for this work, found `produces=(prod or 1) * count` — if a
  *compound* stitch ever appeared in a corner clause (`"3 bo in corner"`),
  `prod` would be `None` and `(None or 1)` would silently assume 1 rather
  than leaving it unverifiable, which is exactly the kind of guess this
  project avoids everywhere else. No real sample has ever put a compound
  stitch in a corner (every corner seen so far is plain `sc`), so this
  isn't exercised and isn't fixed yet — flagging it here per the project's
  own "revisit if it comes up" convention rather than fixing speculatively
  against a case with no real test data.




## Seventh real-sample batch (Jul 1, 2026, fourth upload) — 6 patterns:
## tote bag (sc, hdc, dc, linen, bobble, waffle)
Largest batch so far. New stitches: waffle (fpdc + dc 2-row repeat) and
linen (stitch guide only -- body is DC, a generation defect). Two tool
gaps found and fixed.

- **Real pattern defect -- linen: wrong stitch guide attached to a DC
  body**: The linen variant's Stitch Guide describes the Linen Stitch (an
  alternating SC + chain-1 pattern with its own Foundation and Working row
  instructions) but the pattern body is entirely plain DC, identical to the
  DC variant. The abbreviation key has no linen/ls/moss entry and no
  instruction row mentions anything linen-stitch-related. The stitch-count
  math passes because DC rows verify as DC -- the defect is completely
  invisible to math-only checks. Same generation-defect class as the Jun
  29 dc/hdc foundation-chain error: correct body for what it is, wrong
  metadata attached.
- **Tool gap -- fasten-off message hard-coded to reference a border that
  may not exist**: `_check_fasten_off` always emitted "before the border
  begins... 'join yarn at any corner' (implying a fresh strand)..." even
  for patterns with no border row at all. The waffle variant triggered
  this: its last body row (Row 80) genuinely has no "Fasten off." but the
  pattern has no border. **Fixed**: check whether a border row
  (`row_start == -1`) actually exists; if so, use the original
  border-specific message; if not, use a generic "last row has no
  explicit fasten-off before Finishing" message.
- **Tool gap -- no stitch-guide-vs-body mismatch check**: The Stitch
  Guide section was previously parsed (to split it from Materials and
  Instructions) but never analysed for consistency with the body. A
  pattern with a completely wrong stitch guide silently PASSed because
  math-only checks don't care what the guide says. **Added**
  `_check_stitch_guide_body_mismatch` to `completeness.py`:
  - Scope: only "complex" stitch guides that describe a full stitch
    pattern row-by-row, detected by any of: "foundation:", "working row",
    or "stitch multiple" in the guide text (case-insensitive). Basic
    technique guides ("here is how a dc works") don't contain these and
    are skipped. This prevents false positives on the SC/HDC/DC guides.
  - Detection strategy A: extract any parenthetical abbreviations from
    anywhere in the guide (e.g. "(FPdc)", "(bo)"). If any appear in the
    body stitch tokens or abbreviation key, the guide is being used →
    pass. Catches the waffle correctly: "(FPdc)" → "fpdc" in body.
  - Detection strategy B: extract heading keywords from "Name Stitch:" /
    "Name (abbr):" lines at the start of guide lines. If any keyword
    appears in the body-token + abbreviation-definition corpus, pass.
    Catches the bobble correctly: "Bobble Stitch" → "bobble" in "bo"'s
    definition.
  - If NEITHER strategy finds a match → error. Catches the linen
    correctly: "Linen Stitch" → "linen" in neither body tokens nor
    abbreviation key values.
  - Regression confirmed: SC/HDC/DC (not complex) → not checked.
    Bobble (complex via "working row pattern:" in guide) → passes via
    keyword match. Waffle (complex via "stitch multiple:") → passes via
    parenthetical abbreviation match. Jun 29 sc, dc, bobble results
    byte-identical to before.
- **Waffle stitch-count math clean**: fpdc clauses (both singular
  "around next st" and plural "around next 2 sts") parse correctly via
  the around-post regex with the grammar-based consumes fix from batch
  six. Counted ch-2 turning chains ("Ch 2 (counts as dc)") and "dc in
  top of ch" also parse correctly. All 80 rows verify with 22 repeats
  per row; three-colour joins and handles clean.
- **Bobble 3-colour**: same algebraic solving as Jun 29; colour B joins
  at Row 28 (parsed as "With Colour B -- Moss:"), colour C at Row 55.
  All 40 bo rows solve consistently to 1 produces, PASS with INFO.
- **SC/HDC/DC all PASS**: foundation chain math correct for all three
  (57-1=56, 58-2=56, 59-3=56). Jul 1 correctly fixed the Jun 29 dc/hdc
  foundation-chain defect.
- **Final batch result**: sc — **PASS**; hdc — **PASS**; dc — **PASS**;
  linen — **FAIL** (wrong stitch guide); bobble — **PASS** (with INFO);
  waffle — **REVIEW** (1 warning, missing fasten-off on final row).

## Eighth real sample (Jul 1, 2026, third upload) — linen tote bag, corrected
A revised linen variant (Beginner difficulty, worsted/H-8, different gauge
from the batch above -- clearly a distinct generation, not a re-upload of
the same file). Unlike every prior linen sample, the body genuinely IS
Linen Stitch this time: Row 1/Row 2 read "SC in 2nd ch from hook, *ch 1,
skip 1 ch, SC in next ch; rep from * to end" / "SC in first st, *ch 1,
skip ch-1 sp, SC in next SC; rep from * to end" -- copied almost verbatim
from the guide's own Foundation:/Working row: lines. The real defect from
the earlier batches (wrong guide on a DC body) appears fixed. Running the
existing pipeline against it produced a **false FAIL**, from two tool gaps:

- **Tool gap -- stitch-guide-vs-body mismatch check only recognized named-
  token reuse, not construction-text reuse**: `_check_stitch_guide_body_mismatch`
  only passed a guide as "in use" if a literal word from the guide's
  heading (e.g. "linen") or a parenthetical abbreviation appeared in the
  body/abbreviation key. A pattern that spells the construction out
  directly in the body (real `sc`/`ch` clauses matching the guide's own
  text) instead of using a named shorthand token was invisible to both
  existing strategies -- the body never writes "linen" and never defines
  an abbreviation for it, so the check flagged a real, matching guide as
  mismatched. **Fixed**: added a third detection strategy in
  `checks/completeness.py` -- extract the guide's own
  "Foundation:"/"Working row:" lines, tokenize their meaningful words, and
  check whether >=70% of those words appear verbatim somewhere in the
  pattern's actual body row text. High overlap (near-verbatim reuse) passes;
  incidental shared crochet vocabulary alone ("sc", "in", "next") doesn't
  meet the threshold. Regression-checked with a synthetic wrong-body-DC
  case (same guide, DC body, no textual overlap) -- still correctly FAILs;
  all six Jul 1 second-upload samples (sc/hdc/dc/waffle/bobble unaffected,
  now-correct linen) re-verified unchanged/fixed.
- **Tool gap -- stitch_parser.py had no clause shape for a standalone
  ordinal foundation-chain start mixed with a separate repeat group, or
  for skipping a previously-made chain-1 space**: linen/moss-stitch-style
  rows write "SC in 2nd ch from hook" as one clause and a separate
  "*ch 1, skip 1 ch/skip the ch-1 space, SC in next ch/sc; rep from *"
  group -- a shape stitch_parser.py didn't recognize, so both clauses fell
  through to generic "unrecognized clause" text. **Partially fixed**:
  added explicit recognition for both shapes.
  - `skip (the) ch-1 sp(ace)` -- skips a chain-1 *space* created by an
    earlier `ch 1`, not a real previous-row stitch, so it consumes 0 (per
    the existing "chain stitches never count toward stitch total"
    convention). This IS safely computable and now resolves cleanly:
    e.g. Row 2's repeat (`sc in first st` pre + `ch1/skip-space/sc-in-
    next-sc` unit) now solves to exactly 55 repeats, matching the
    declared 56 sts, with **no warning** (previously an unrecognized-
    clause warning).
  - `<stitch> in Nth ch from hook` (no trailing "and each ch across") is
    recognized as its own clause shape now, but its consumes/produces are
    deliberately left `None`/unverifiable rather than computed. Reason:
    the existing whole-row `foundation_into_chain` offset formula
    (`chain_count - (ordinal-1)`) is a *whole-row* property; worked out
    by hand for this specific mixed-row shape (ordinal clause + separate
    repeat group), the repeat's own chain consumption doesn't divide
    evenly regardless of how the one-time ordinal offset is distributed
    (55 remaining chains / 2 chains-per-repeat is non-integer) -- meaning
    a real, valid linen-stitch row of this exact shape can legitimately
    have "leftover" asymmetric chain handling at the row's tail that a
    single-clean-repeat-group model can't resolve. Assigning a concrete
    number here risked turning an honest "can't verify" into a *wrong*
    "error" on a correct pattern. Left unverifiable per the project's
    "never silently guess" rule -- Row 1 of this sample now reports one
    clear, specific warning naming exactly this reason, instead of a
    generic "unrecognized clause" message.
- **Result after both fixes**: linen — **REVIEW** (0 errors, 1 warning:
  Row 1's foundation-ordinal-clause is honestly unverifiable). Previously
  FAIL (1 error, false positive) is now correctly not-a-hard-failure; the
  one remaining warning is a real, accurate statement of what the tool
  can't check, not a defect finding.
- **Next step, not yet built**: a proper row-level model for mixed
  foundation rows (ordinal single-stitch clause + separate repeat group)
  that correctly distributes the one-time ordinal offset and handles
  asymmetric/leftover chain endings, so Row 1 of constructions like this
  can eventually resolve to a real PASS/ERROR instead of staying
  unverifiable. Revisit if more linen/moss-stitch samples show up.

## Ninth real-sample batch (Jul 2, 2026) — 10 patterns: throw blanket
## (sedge, waffle, linen, moss, bobble, shell, tr, dc, hdc, sc)
Largest single-day batch: one stitch-variant per file, same blanket
otherwise (2-colour, 151-row body, standard 4-edge border). Run three
times the same day as fixes landed between rounds. Confirms the project's
"a QA tool that cries wolf gets ignored" risk cuts both ways — this round
surfaced a real false positive in the tool itself, not just in the
patterns.

### Round 1 — root cause: all 10 files share one identical body
Every file's Pattern Steps section was byte-identical (plain sc + ch-1
mesh, 151 rows) regardless of the file's namesake stitch — only the
Stitch Guide section was swapped per variant. The shared body happens to
BE moss/linen stitch construction, so:
- **linen, moss**: guide genuinely matches the (identical) body → PASS.
- **sedge, waffle, bobble, shell**: caught correctly by
  `_check_stitch_guide_body_mismatch` (all four guides are "complex" —
  contain "Foundation:"/"Working row:"/"Stitch multiple:" — and none of
  their named stitches appear anywhere in the shared generic body).
- **tr, dc, hdc, sc**: same underlying defect (body never uses tr/dc/hdc,
  and sc's body is a mesh, not a plain sc fabric) but NOT caught — these
  four guides teach the basic stitch technique using a "Turning chain:"
  heading instead of "Foundation:"/"Working row:"/"Stitch multiple:", so
  `is_complex` never recognizes them and the check skips them entirely.
  **Confirmed tool gap, not yet fixed this round** (content was
  genuinely broken here too, so fixing the detection wasn't the
  immediate priority — the generation-pipeline defect was the bigger
  problem). Revisit `complex_markers` if a future batch needs this path
  covered.
- Stitch-count math and terminology checks stayed clean across all 10 —
  expected, since the one shared body is internally self-consistent;
  this class of defect (right math, wrong stitch) is structurally
  invisible to those two check categories, exactly as documented for the
  Jul 1 linen defect.
- Also noted: each file's own embedded "Confidence Summary" (LoopDreams'
  internal QA) claimed 99% confidence with every sub-check green on all
  10 files, including the four with a completely wrong stitch guide —
  not a reliable independent signal.

### Round 2 — generation defect fixed; new real bugs; a real tool false positive
Every file now has its own distinct, stitch-correct body (verified by
hand for sedge/waffle in addition to the automated PASS). Two genuinely
new, real pattern defects surfaced, plus the tool's first confirmed false
positive on a real sample:

- **Real defect — bobble**: `bobble` is used throughout the body and
  described in the Stitch Guide, but was never added to the
  Abbreviations key (only ch/sl st/sc/dc/rep/rs listed). Correctly
  flagged as a completeness error by the existing undefined-abbreviation
  check — no tool change needed, this one just worked.
- **Real defect — tr, dc, hdc, sc**: body ends at "Rows 75–150: Repeat
  Row 2" with no final capping row and no explicit "Fasten off" before
  the Border begins, unlike the other 6 variants in the batch (which all
  have an explicit final numbered row ending in "Fasten off."). Correctly
  flagged as a warning by the existing `_check_fasten_off` check.
- **linen**: unchanged from the Jul 1 eighth-batch finding — same Row 1
  text, same honest "unverifiable" warning. Manually re-attempted the
  hand-computation and still couldn't resolve it cleanly either way;
  recommended a physical swatch check rather than trusting either
  reading. Not a confirmed defect, not newly investigated further this
  round.
- **Tool false positive — shell**: `_check_stitch_guide_body_mismatch`
  flagged shell as a guide/body mismatch again, but manual verification
  showed the body genuinely works the shell construction ("5 dc in next
  st (shell made)", "sc in centre dc of next shell", matching the
  guide's "Stitch multiple: Multiple of 6 + 1" exactly). Root cause:
  strategy (a) only checks a guide heading's keyword (e.g. "shell")
  against `body_tokens` (recognized stitch abbreviations like sc/dc) and
  `abbr_corpus` (the abbreviation key) — never against literal words
  actually written in the row text. "Shell" only ever appears inside
  descriptive parenthetical annotations `(shell made)`, never as a
  parsed stitch token or an abbreviation-key entry, so strategy (a)
  can't see it. Strategy (c) (construction-text overlap) also missed it:
  it only fires for guides using "Foundation:"/"Working row:" headers
  with ≥70% word overlap, but shell's guide uses "Shell row:"/"SC row:"
  headers, and its "Foundation:" line phrasing ("work 5 dc all in the
  next ch") differs enough from the body's ("5 dc in next st") to fall
  under the threshold. **Not fixed this round** — flagged to the user,
  confirmed real via manual read, deferred to the next round.

### Round 3 — all three real defects confirmed fixed; tool false positive fixed
Re-ran after fixes: bobble (abbreviation key now includes
`bobble = bobble (5 incomplete dc in same st, yo pull through all
loops)`) and tr/dc/hdc/sc (each now has an explicit final row ending
"Fasten off.") all now PASS clean. shell's guide/body mismatch persisted
unchanged (byte-identical body text to Round 2) — as expected, since it
was never a content bug.

- **Tool fix — strategy (a) now also checks literal body words, not just
  tokens/abbreviations**: `checks/completeness.py`'s
  `_check_stitch_guide_body_mismatch` now computes `body_words` (every
  literal word in `row.raw_text`, lowercased) once, before strategy (a),
  and checks `name_keywords & (combined | body_words)` instead of just
  `combined`. This directly catches "shell" via its parenthetical
  annotations. Verified safe against reintroducing the Round-1-style
  genuine mismatch: that content never contained the words
  "sedge"/"waffle"/"bobble"/"shell" anywhere in the body at all (pure
  generic mesh, zero reference to any named stitch), so the broadened
  match target doesn't mask it.
- **Regression tests added** (`tests/test_stitch_guide_mismatch.py`,
  synthetic pattern text, no external sample file needed):
  `test_named_stitch_only_in_body_annotations_not_flagged` (the shell
  case — must NOT flag) and
  `test_genuinely_unused_named_stitch_still_flagged` (a Round-1-style
  sedge-guide-on-plain-sc-mesh case — must still flag). Both pass; full
  existing suite unaffected; all 10 live batch files re-verified against
  the fix with no other regressions.
- **Known gap still open, not addressed this round**: the Round 1
  tr/dc/hdc/sc detection gap (guides using a "Turning chain:" heading
  bypass `is_complex` entirely) is unrelated to this fix and remains
  unaddressed — those guides happened to be content-correct by Round 2,
  so there was no live defect to catch, but the detection blind spot
  itself is unchanged. Revisit `complex_markers` in `is_complex` if a
  future batch has a genuinely wrong tr/dc/hdc/sc-style (simple
  "Turning chain:"-only) guide.
- **Final batch result (Round 3)**: sedge, waffle, moss, bobble, tr, dc,
  hdc, sc — all PASS. linen — REVIEW (1 warning, same known
  unverifiable Row 1 shape, recommend physical swatch). shell — REVIEW
  (1 warning, the pre-existing and legitimate "centre dc of next shell"
  landmark-reference math limitation from the Jun 27 batch) — no error,
  false positive resolved.

### Tech-debt pass (Jul 2, 2026) — closing the Round 1 tr/dc/hdc/sc detection gap
Asked directly which open tech-debt items to tackle next; started with the
gap flagged (not fixed) two entries above. Turned into a two-bug fix, not
one — the straightforward version of this change would have silently
defeated its own purpose.

- **Fix attempt 1 — add `"turning chain:"` to `complex_markers`**: makes
  basic single-stitch technique guides (dc/hdc/tr/sc's "Turning chain:
  Ch 2, turn..." style) subject to the same guide/body cross-check as
  named compound-stitch guides, closing the Round 1 blind spot. Reasoned
  safe against false positives because genuinely-correct simple guides
  are independently confirmed two ways before this even matters: strategy
  (b)'s parenthetical-abbreviation match (heading's own "(dc)" against the
  abbreviation key, which always has a "dc" entry for a real dc pattern)
  and strategy (a)'s word overlap (heading "Double Crochet" vs. abbr
  key's own "dc = double crochet" definition text).
- **Bug found in that reasoning — the generic word "crochet" self-matches
  everything**: `abbr_corpus` includes every meaningful word from every
  abbreviation's own definition text, and "crochet" appears in literally
  every stitch's definition ("single crochet", "double crochet", "half
  double crochet", ...). So strategy (a)'s word-overlap check would have
  spuriously matched ANY "___ Crochet" heading regardless of which
  specific stitch was actually named -- caught by testing a genuinely
  broken synthetic case (a "Double Crochet (dc):" guide attached to a
  body that only ever uses sc) before trusting the fix. **Fixed**: added
  "crochet" to `skip_words` -- same category and same justification as
  "stitch" already being there (a domain-generic word that appears in
  every heading and therefore can't discriminate between them).
- **Second bug found in the same test — `heading_re` itself also matches
  "Turning chain:"**: the regex used to extract "named stitch" headings
  for strategy (a) doesn't distinguish a real stitch-name heading
  ("Double Crochet (dc):") from a construction-detail label that happens
  to share the same "Capitalized Words:" shape ("Turning chain:",
  "Foundation:", "Working row:", "Stitch multiple:"). This was harmless
  for the pre-existing three markers (their keywords -- "foundation",
  "working", "row", "stitch", "multiple" -- don't coincidentally collide
  with anything in a typical abbreviation corpus), but "Turning chain:"
  extracts the keyword "chain", which trivially matches because nearly
  every real pattern defines `ch = chain`. Left unfixed, this would have
  made ANY guide containing a "Turning chain:" line auto-pass via that
  line alone, regardless of whether the guide's actual named stitch
  matched the body -- silently defeating the entire point of enabling
  this marker. **Fixed**: headings whose text exactly matches one of
  `complex_markers` (colon stripped) are now excluded from the
  strategy-(a) heading list entirely, so only genuine named-stitch
  headings are ever checked for keyword overlap.
- **Regression tests added** (`tests/test_stitch_guide_mismatch.py`):
  `test_turning_chain_guide_with_matching_body_not_flagged` (a real,
  correct dc pattern via "Turning chain:" -- must pass) and
  `test_turning_chain_guide_mismatch_flagged` (the actual Round 1 bug
  shape -- a "Turning chain:"-style dc guide on a body that never uses
  dc -- must now flag). Both required the second bug fix above to pass;
  neither passed after fix attempt 1 alone, which is exactly why the
  synthetic mismatch test existed before declaring this done. Full
  4-test suite passes; all 10 live Jul 2 batch files re-verified
  unchanged (byte-identical PASS/REVIEW results to Round 3).
- **Remaining open items, not addressed this pass** (see the "tech debt"
  discussion this entry came from): the linen Row-1 mixed-foundation-row
  model is still not built (recurring unverifiable warning, three rounds
  running); the corner-clause `(prod or 1)` silent-guess for a compound
  stitch is still unfixed (never triggered by real data); no batch-runner
  exists yet (every round including this one was still a manual per-file
  loop).

### Tech-debt pass (Jul 2, 2026) — batch runner
Closed the other item raised in the same tech-debt discussion: a batch
wrapper over a folder of patterns, the "next step" flagged since the very
first version of this doc and manually worked around every round since
(a shell for-loop calling the single-file CLI once per file).

- **Added `loopdreams_qa/batch.py`** (`python -m loopdreams_qa.batch
  <folder> [--json]`), built on top of `cli.run()` per the original plan
  rather than duplicating the extract/parse/check pipeline.
  `cli.run()` gained one new optional parameter, `quiet: bool = False`
  (default preserves every existing call site's behaviour exactly,
  including `test_pipeline.py`'s use of the underlying checks directly,
  which doesn't call `run()` at all).
  - Human-readable mode (default): prints each file's full report
    exactly as the single-file CLI always has -- byte-for-byte the same
    experience as every for-loop run this project has done by hand so
    far -- then appends one combined `BATCH SUMMARY` table (filename,
    status, error/warning counts, plus a final PASS/REVIEW/FAIL tally).
    This table is exactly the shape manually retyped for the user after
    every batch round to date.
  - `--json` mode: suppresses per-file printing (`quiet=True` on each
    `cli.run()` call) and instead emits one combined JSON document
    (`{"files": {filename: report, ...}, "batch_summary": {...}}`) --
    deliberately not N separate JSON blobs on stdout, since that isn't
    something a downstream script could parse cleanly.
  - Discovers `.pdf`/`.docx` files case-insensitively (`B.PDF`, `c.DOCX`,
    etc. all found), ignores everything else (`.DS_Store`, stray `.txt`
    notes). Directory-not-found and no-patterns-found are both handled
    as a clear stderr message + exit code 2, distinct from exit code 1
    (reserved for "checked the batch, at least one file FAILed" --
    mirrors the single-file CLI's error-vs-usage exit code convention).
- **Tested**: unit tests (`tests/test_batch.py`) for the two pure-logic
  pieces that don't need a real PDF fixture (`discover_patterns`'
  extension/case handling, `_batch_summary`'s count aggregation).
  End-to-end verified by copying the actual 10-file Jul 2 throw-blanket
  batch into a scratch folder and running both modes against it: text
  mode reproduced the exact 8-PASS/2-REVIEW/0-FAIL summary from the Round
  3 + tech-debt-pass results; `--json` mode produced one clean combined
  document with no per-file prints leaking into it and the correct
  per-file statuses inside; both error paths (missing directory, empty
  directory) confirmed to exit 2 with a clear message rather than a
  traceback.

### Tech-debt pass (Jul 2, 2026) — corner-clause silent guess for a compound stitch
Closed the third item from the same tech-debt discussion (`stitch_parser.py`'s
corner-clause `produces=(prod or 1) * count`), which was the one place in the
codebase that guessed instead of reporting "can't verify" for a compound
stitch. Never triggered by real data -- every corner seen across all 9+ real
sample batches so far is plain `sc` -- but inconsistent with how every other
compound-stitch clause shape (`each_st_across`/`each_st_around`, etc.)
already handles this.

- **Fix**: `_stitch_lookup` always returns `prod=None` for any compound
  stitch (confirmed by reading it directly), so the fix is exactly the
  same `is_compound` branch already used everywhere else: `produces =
  None if is_compound else (prod or 1) * count`, plus the matching
  `unverifiable_reason` message. A compound stitch's produced count for
  N corner repeats genuinely isn't knowable without a stated ratio, so
  this correctly falls through to the standard "cannot verify" path
  instead of confidently asserting 1-per-repeat.
- **Not attempted, and deliberately so**: resolving a compound corner
  stitch's ratio via the existing `ratio_overrides` mechanism (the
  algebraic solver from the Jun 29 bobble batch). `_zone_sum` adds
  `ratio_overrides[stitch]` once per clause with no multiplier, so even
  if a ratio were resolved elsewhere, a corner's explicit count > 1
  would still need dedicated multiplication logic that doesn't exist
  yet. Building that now, with zero real samples ever exercising a
  compound stitch in a corner, would be exactly the kind of speculative
  work against no test data the project avoids -- left as a known,
  documented gap for if/when a real sample needs it.
- **Regression tests added** (`tests/test_stitch_parser.py`, the first
  direct unit tests of `stitch_parser.tokenize_round` in this project --
  everything before this was tested indirectly via full-pattern parsing):
  a plain-sc corner (`"3 sc in corner"`) still resolves `produces=3`
  exactly as before; a synthetic compound-stitch corner (`"3 bo in
  corner"`, since no real sample has ever done this) now correctly
  leaves `produces=None` with a specific `unverifiable_reason` instead of
  silently returning `3`. Full suite passes (10 tests, 1 skip); all 10
  live Jul 2 throw-blanket files re-verified byte-identical to before
  this change.
- **Remaining open tech-debt item at the time, addressed next**: single
  repeat group per row / no nested repeat groups -- see below. Turned out
  not to be as purely theoretical as first thought.

### Tech-debt pass (Jul 2, 2026) — second repeat group per row wasn't actually caught
The last item from the same tech-debt discussion was framed as "a
structural V1 limitation, never violated by any real sample so far, worth
keeping in mind as a ceiling" -- i.e. assumed to be a documented, inert
gap. Checking it properly (rather than leaving it as a note) found it
wasn't inert: the "flagged as unsupported rather than guessed" behavior
`ARCHITECTURE.md`'s own V1-limitations list has claimed since the very
first version of this doc was **not actually implemented** -- a row with
two separate repeat groups could silently produce a confidently wrong
PASS instead.

- **Reproduced the actual (mis)behavior** with a synthetic row (`"*Sc in
  next st; rep from *. *Dc in next st; rep from *."`, no other real
  sample has ever needed this shape): `_check_row` only ever locates the
  FIRST `*` opener and the FIRST `repeat_close` after it
  (`checks/stitch_count.py`'s `opener_idx`/`closer_idx`), then hands
  everything from the first closer onward to `_check_repeat_group` as a
  flat "post" zone via `_zone_sum`. Critically, `_zone_sum` explicitly
  **skips any `repeat_close` clause as a no-op** rather than checking its
  `consumes` value (which is always `None` on that clause type) --
  meaning a second, unrecognized repeat group's own opener/body/closer
  gets summed as if it were flat, one-time literal content instead of
  being flagged as an unhandled shape. With the right declared row count
  (constructed so "19 reps of the first group + 1 literal occurrence of
  the second" arithmetically totals the declared count), this returned a
  clean, confident PASS with zero warnings -- numerically self-consistent
  but meaningless, since the second group was never actually verified as
  a repeat construct at all.
- **Fixed**: `_check_row` now checks for a second `*` opener anywhere
  after the first repeat group's closer *before* dispatching to
  `_check_repeat_group`, and returns a specific "more than one repeat
  group... currently unsupported" warning instead of attempting the
  flawed flat-sequence math. This makes the actual behavior match what
  `ARCHITECTURE.md` has claimed all along, rather than changing the
  claim to match the (wrong) behavior.
- **Regression tests added** (`tests/test_multiple_repeat_groups.py`):
  confirms the ordinary single-repeat-group shape still verifies cleanly
  (no regression), and that the two-repeat-group shape above is now
  caught with a clear warning instead of silently passing. Full suite
  passes (12 tests, 1 skip); all 10 live Jul 2 throw-blanket files
  re-verified byte-identical to before this change (none of them use
  more than one repeat group per row).
- **Not attempted, and correctly so**: actually parsing/verifying
  multiple or nested repeat groups. Zero real samples have ever needed
  this; the fix here is scoped to detecting the unsupported shape
  honestly, not building support for it speculatively.

## Tenth real-sample batch (Jul 2, 2026, regenerated) — same 10 throw-blanket
## variants (sedge, waffle, linen, moss, bobble, shell, tr, dc, hdc, sc)
Same filenames as the Jul 2 batch, but regenerated content -- first real
use of the batch runner (`python -m loopdreams_qa.batch`) built two
tech-debt passes ago. It immediately paid for itself: **moss regressed
from PASS to REVIEW**, caught instantly by the summary table rather than
requiring a manual per-file eyeball comparison against the prior round.

- **Investigated the moss regression -- new phrasing, not a new defect**:
  moss and linen's repeat unit changed from the earlier "*ch 1, skip 1
  st, sc in next st*" / "*ch 1, skip ch-1 sp, SC in next SC*" ordering to
  "*ch 1, sc in next ch-1 sp, skip next st*" -- the chain-1 space itself
  is now the stitch's target noun, and the skip comes after rather than
  before. Neither half of this new ordering matched any existing clause
  shape, so both fell through to "unrecognized clause" and correctly
  turned the row unverifiable -- a real tool gap, not a false alarm, but
  also not a pattern defect: hand-verified using the existing moss/linen
  "chains count inside the repeat unit" convention (from the Jun 27
  batch) that 241 sts in resolves cleanly to 241 sts out with this
  phrasing, exactly as the older phrasing did.
- **Fixed two clause-shape gaps in `stitch_parser.py`**:
  - New `stitch_in_ch1_space` pattern: `"<stitch> in (first|next|last)
    ch-1 sp(ace)"` -- same semantics as the existing `simple_positional`
    clause (one previous-row slot in, the stitch's own produces out),
    just a different noun (a chain-1 space instead of an actual
    previous-row stitch).
  - `_RE_SKIP_POSITIONAL` previously only matched `"skip (the) first
    <noun>"`; broadened to use the shared `_POS` group so `"skip next
    st"` and `"skip last st"` are recognized too, not just `"first"`.
- **Regression tests added** (`tests/test_stitch_parser.py`): both new
  clause shapes tokenize correctly in isolation, `"skip next/last st"`
  now resolves (previously only `"first"` did), and a full synthetic
  moss-style row using the new phrasing verifies end-to-end with zero
  stitch-count issues. Full suite passes (15 tests, 1 skip); moss
  confirmed back to PASS, linen back down to just its one pre-existing
  Row 1 warning (same known unverifiable mixed-foundation-row shape as
  every prior round, not new), shell's pre-existing centre-dc warning
  unchanged -- all other files re-verified byte-identical.
- **Batch result**: sedge, waffle, moss, bobble, tr, dc, hdc, sc -- all
  PASS. linen, shell -- REVIEW (both pre-existing, known, non-blocking
  warnings). 8 PASS / 2 REVIEW / 0 FAIL, matching the healthiest prior
  round once the phrasing gap was closed.

### linen's recurring Row 1 warning resolved via external reference -- new check added (Jul 2, 2026)
Asked directly: a real crochet-technique tutorial video (moss stitch)
shows foundation chain -> a full plain sc row across -> THEN the
alternating chain-1 pattern begins. moss.pdf does exactly this. linen.pdf
does not -- it starts the alternating pattern immediately in Row 1, with
no separate plain setup row. Is linen actually missing a step, and if so,
why didn't the QA tool catch it as an error?

- **Why the tool only ever flagged this as an ambiguity, not an error**:
  this exact Row 1 shape (starting the alternating chain-1 pattern
  immediately, no plain setup row) is, on its own, ALSO a legitimate and
  common way real patterns write linen stitch -- plenty of published
  patterns do it this way. The tool has correctly refused to call it
  wrong in isolation every round so far (the recurring "cannot verify
  Row 1" warning), because doing so would require an external
  ground-truth reference for "the one true way to make stitch X", which
  the tool has no access to and shouldn't fabricate.
- **What actually makes THIS case resolvable, though**: LoopDreams' own
  generated Stitch Guide text for both files explicitly claims
  equivalence -- linen's guide says "Also called the moss stitch",
  moss's says "Also called the linen stitch". Given the pattern set
  itself asserts these are the same construction, they SHOULD match each
  other, and demonstrably don't (moss has the setup row, linen doesn't).
  The external video reference confirms which one is correct (moss's
  setup-row version), but the tool doesn't need the video to detect the
  *inconsistency* -- only LoopDreams' own claim of equivalence, which is
  already present in every generated file.
- **Added `cross_variant.py`** (new top-level module, not inside
  `checks/`, since every existing check operates on ONE pattern and this
  inherently compares sibling files against each other): extracts each
  pattern's Stitch Guide heading name and any "Also called the X stitch"
  aliases; for any two files in a batch whose names/aliases claim mutual
  equivalence, compares whether Row 1 starts the alternating pattern
  immediately (`*` opener present) or has a separate plain setup row
  first. Disagreement -> a completeness-category warning naming both
  files and which one has the setup row. Deliberately scoped to the
  pattern's OWN claims, not an external hardcoded "correct" convention --
  this is what keeps it from false-positiving on genuinely-correct
  patterns that legitimately skip the setup row (e.g. it correctly leaves
  sedge/shell alone despite sedge's guide loosely referencing "the shell
  cluster stitch", since that's a different name than shell's own
  "shell", not an exact match).
- **Wired into `batch.py`**: `run_batch()` now also re-parses each file
  (separately from `cli.run()`'s own internal parse, so `cli.run()`'s
  single-file contract stays untouched -- these files are small, the
  extra parse is cheap) purely to build the `{name: Pattern}` map
  `cross_variant.check()` needs. Results append a new `CROSS-VARIANT
  CONSISTENCY` section to the text summary and a `cross_variant_issues`
  key to the combined JSON document.
- **Tests**: `tests/test_cross_variant.py` covers the real mismatched
  case, a matching (not-flagged) case, an unrelated-stitches case
  (confirms no false positive on sedge/shell despite loose naming
  overlap), and a no-Stitch-Guide-section case. `tests/test_batch.py`
  adds a true end-to-end `run_batch()` integration test with
  `extract_text` mocked per-filename (no real PDF fixtures needed,
  matching this project's existing synthetic-text testing convention) --
  confirms the cross-variant section actually surfaces correctly through
  the full batch pipeline, not just in the standalone check function.
  Full suite passes (21 tests, 1 skip).
- **Not attempted**: actually determining which side of a mismatch is
  "correct" -- the check only reports that two claimed-equivalent files
  disagree, exactly as the real case required a human (with an external
  video reference) to resolve which one was actually right. Building
  that judgment into the tool would mean encoding a crochet-technique
  knowledge base, which is a fundamentally different and much larger
  scope than anything else this project does.

## Eleventh real-sample batch (Jul 4, 2026) — tote bag (waffle stitch)
One file. Two real, unrelated findings -- a genuine parser gap (new row-
shorthand phrasing) and a genuine content defect (wrong chain-skip
convention for the named stitch), the latter requiring three rounds of
back-and-forth with an external source before landing on the right
answer. Worth reading in full if a similar "the video says X" claim comes
up again -- the first two attempts to resolve it were each wrong in a
different, instructive way.

### Parser gap: "Repeat Rows P-Q x N more times." with no row-range label
Running the QA tool immediately produced a false `"No instructions are
given for Rows 4-79"` error. The pattern used `"Repeat Rows 2-3 x 38 more
times."` as a standalone sentence -- unlike the previously-supported
`"Rows 4-79: Repeat Row 2."` shorthand, this has NO leading row-range
label at all, only a repeat count. **Fixed** in `pattern_parser.py`: a
new regex anchors immediately after the LAST already-parsed occurrence of
the referenced range's own last row (e.g. Row 3), spanning `N * (Q-P+1)`
more rows; if no such anchor exists (e.g. a typo referencing a row that
was never parsed), it's left unrecognized rather than guessed. Hand-
verified the row math first (1 + 1 + 1 + 38×2 + 1 = 80 rows, ending
correctly on the row type the guide describes). Tests in
`tests/test_pattern_parser.py`. With this fixed, the pattern's own
stitch-count math is fully clean using its existing "4th ch from hook"
Row 1 wording -- which turned out to matter a lot for the next part.

### Content defect: wrong chain-skip convention for Waffle Stitch's Row 1 -- three rounds to resolve
The user flagged, from a YouTube video, that Row 1 should skip only 1
chain ("2nd ch from hook"), not 3 ("4th ch from hook" as generated).

**Round 1 (wrong on my end)**: pointed out that "4th ch from hook" is the
generic US double-crochet convention (skip 3, matching a ch-3 turning-
chain-equivalent), and that switching to "2nd ch from hook" would break
the row's own stated count (72 chain - 1 = 71 sts, not the declared 69).
Both true, but beside the point -- I was defending the *generic* dc
convention without checking whether THIS specific named, sourced
technique actually follows it.

**Round 2 (closer, still wrong)**: identified the video as Bella Coco's
"How to crochet the Waffle Stitch" -- confirmed via `oembed` (full video
pages don't render through WebFetch, but oembed reliably returns title/
author) -- and via web search that her patterns are written in **UK
terminology**, where "double crochet" is a different, shorter stitch
than the US term (UK dc = US sc). Correctly concluded the video's "dc"
and this pattern's US "dc" aren't the same stitch. But a search-result
snippet paraphrase claimed her tutorial specifies "third chain, not
second" -- and when the user then handwrote out Row 2/Row 3 from memory
based on the video, Row 3's stitch math (checked the same way as Round
1's foundation-row check) didn't divide evenly. Flagged this discrepancy
directly instead of accepting the recalled description at face value --
the right move, since the exact wording mattered and secondhand
paraphrase/memory wasn't precise enough to resolve it.

**Round 3 (resolved)**: the user provided a screenshot of Bella Coco's
actual published written pattern (blog.bellacococrochet.com/waffle-
stitch/), in UK terms. Translating precisely (UK tr -> US dc, UK FPtr ->
US FPdc) and checking the arithmetic:
- Row 1: `dc in 3rd ch from hook (skipped 2-ch does not count as st)` --
  skip 2, not skip 3 as LoopDreams generated, and not skip 1 as the
  user's first video-recall suggested either.
- Row 2/Row 3 translated exactly (not the user's earlier from-memory
  version) both resolve cleanly: 69 sts - 3 (edges) = 66, / 3 = exactly
  22 repeats each.
- Critically: the canonical construction requires the foundation chain
  to be `3n + 2` for the resulting stitch count to be a clean multiple of
  3 (needed for Row 2/3's own repeat math). LoopDreams' foundation of
  Ch 72 does NOT satisfy this (72 isn't `3n+2` for any integer n) -- with
  the *canonical* skip of 2, Ch 72 gives 70 sts, which does NOT divide
  cleanly for Row 2/3 (66.67). LoopDreams' actual "skip 3" choice is what
  makes Ch 72 produce a workable 69 stitches (a clean multiple of 3) --
  an internally self-consistent variant, but not a faithful reproduction
  of the named, sourced technique. **Confirmed real defect**: both Row 1's
  wording and the foundation chain count need to change together (e.g.
  Ch 71 -> 69 sts with the corrected "3rd ch from hook", leaving Rows
  2-80 unchanged since 69 sts still resolves the same way).
- **The lesson**: neither "internally self-consistent" nor "matches
  generic stitch-family convention" is sufficient to confirm a named,
  sourced stitch is constructed correctly -- only checking against the
  actual verified source settled it, and it took three passes (generic-
  convention defense, video-title + secondhand-paraphrase, actual
  published-pattern screenshot) to get there. Each intermediate step was
  reasoned about carefully rather than accepted at face value, and each
  wrong conclusion was caught by the same discipline that's been used
  throughout this project: check the arithmetic before trusting an
  answer, whichever direction it points.

**Tool addition**: `checks/known_constructions.py` -- a small, explicit
reference table of verified stitch constructions (currently one entry:
Waffle Stitch, sourced to Bella Coco's published pattern), checked
against any pattern whose own Stitch Guide heading names a stitch in the
table. Flags (a) a Row 1 chain-skip that doesn't match the verified skip,
and (b) a foundation chain that doesn't satisfy the verified stitch
multiple. Both as warnings, not errors, since a pattern can still be
internally self-consistent while deviating from the named technique --
this is a "worth confirming" flag, not a hard failure, the same posture
as the cross-variant check. Deliberately kept small: entries are only
added after a real, human-verified case, never speculatively, to avoid
false-positiving on legitimate variants of a stitch family that share a
name loosely. Tests in `tests/test_known_constructions.py` cover the real
mismatched case (both warnings fire), the corrected/canonical case (no
warnings), an unrelated stitch name (not checked), and no-Stitch-Guide-
section (not checked). Wired into `cli.run()` directly (not just
`batch.py`, since this check operates on one pattern at a time, unlike
`cross_variant.py`). Full suite passes (27 tests, 1 skip).
- **Not attempted**: broader coverage of other named stitches. This
  table is intentionally minimal and grows only from real, sourced cases
  -- the same discipline as `cross_variant.py`'s "don't add features
  beyond a verified real case" approach.

## Twelfth real-sample batch (Jul 5, 2026) — tote bag with lining + zipper
First LoopDreams sample to add a lining/zipper component on top of the
crocheted body (previous tote bags stopped at handles). Also the first
sample whose PDF genuinely needed OCR and didn't have it available --
surfaced a real extraction crash, a real parser gap, and a real content
defect, all in the same file.

- **Extraction crash, fixed**: this PDF's trailing screenshot/confidence-
  summary pages have ZERO embedded text at all -- unlike every prior
  sample, which always had at least a URL/timestamp footer keeping those
  pages above `MIN_CHARS_BEFORE_OCR_FALLBACK`. That pushed them into the
  OCR fallback path, and this environment doesn't have `pdf2image`
  installed, so `extract_text()` crashed with `ModuleNotFoundError`
  instead of returning the (perfectly readable) real pattern content on
  the earlier text-layer pages. **Fixed**: `_ocr_pages` now catches
  `ImportError` (broadened from a narrower `ModuleNotFoundError` catch,
  to also cover a partially-broken install) and returns empty strings
  for the affected pages with a printed warning, instead of crashing the
  whole extraction. OCR is a fallback for genuinely scanned pages, not
  something that should hard-crash QA of an otherwise-fine PDF just
  because it's unavailable in a given environment. Tests in
  `tests/test_extraction.py` simulate the missing-dependency case
  deterministically (via mocking `__import__`) rather than depending on
  whatever happens to be installed wherever the suite runs.
- **Parser gap, fixed**: neither `"Adding a Zipper & Liner"` nor
  `"TESTER EXPECTATIONS"` (a new heading wording, distinct from the Jul 4
  batch's `"TESTER FEEDBACK"`) were recognized `SECTION_HEADERS`. Both
  got silently absorbed into `"finishing"`'s `raw_text`, which broke the
  Handles component's own `"(N sts)"` extraction -- that regex anchors to
  the end of the whole blob to find the trailing count, and with
  unrelated trailing content (zipper/liner instructions, then the entire
  tester questionnaire) glued on, the real count was no longer at the
  true end. Produced a false "Handles gives real stitch construction
  instructions but never states an expected stitch count" warning on a
  pattern that actually states one. **Fixed**: added both headings to
  `SECTION_HEADERS` -- `"tester feedback"`/`"tester expectations"` as
  `ignored_meta` (same treatment as `"confidence summary"`: a request for
  the human tester's own notes, not pattern content), `"adding a zipper &
  liner"` as its own new `"zipper_liner"` section type (real pattern
  content that needs its own completeness check -- see below, not just a
  boundary fix). Tests in `tests/test_pattern_parser.py`.
- **Content defect, confirmed and now caught automatically**: the
  `"zipper_liner"` section's own heading explicitly promises both a
  zipper AND a liner, but the body only ever gave liner installation
  instructions -- the word "zipper" appears exactly twice in the whole
  document (the Materials list heading, and this section's own title)
  and never again in any actual instructional sentence. A tester
  literally has no way to complete the zipper step from this pattern as
  written. **Added** `_check_zipper_liner_section` to
  `checks/completeness.py`: flags (as an error, same severity as a
  missing Materials/Finishing section) when a `"zipper_liner"` section
  exists but its body is missing "zipper" and/or "liner"/"lining"
  content. Tests in `tests/test_zipper_liner_check.py` cover missing-
  zipper (the real case), missing-liner (for symmetry), both-present
  (not flagged), and no-such-section (not checked).
- **Liner technique spot-checked against a user-provided reference**
  (Mason Jar Yarn Designs, "Adding A Fabric Lining to your Crochet Bag")
  and found consistent, not defective: both use the same core sequence
  (fold fabric right-sides-together, sew the side seams, turn right-side
  out, nest inside the finished bag, hand-stitch the folded top hem to
  the bag's top edge). LoopDreams' specific fixed hem/seam-allowance
  numbers (0.5in side seam, 0.75in top hem) are a reasonable
  simplification of the reference's "size it to your actual bag" approach,
  not a contradiction. Fabric cut dimensions (15in x 33.5in) independently
  verified against the pattern's own stated 14in x 16in finished size:
  14+1=15 and 2(16)+1.5=33.5, both exact. No defect found here --
  included to record that the comparison was actually done, not skipped,
  given the user had proactively gathered reference material for this
  exact scenario.
- **Final result**: was previously uncheckable at all (crashed before
  reaching the checks). After all three fixes: **FAIL** (1 error -- the
  real missing-zipper-instructions defect; 0 warnings; stitch-count math,
  terminology, and the linen-stitch body -- using the ch-1-space
  phrasing fixed two batches ago -- all verify cleanly).

## Thirteenth real-sample batch (Jul 6, 2026) — same 10 throw-blanket
## variants, regenerated
Best batch result yet: 9 PASS / 1 REVIEW / 0 FAIL. Notably, this batch
confirms **two previously-reported real content defects were actually
fixed on LoopDreams' side**, not just internal tool changes -- the first
direct evidence this feedback loop (QA finding -> reported -> LoopDreams
regenerates -> re-verify) is working end to end.

- **Waffle Stitch's chain-skip defect is fixed**: Row 1 now reads "Dc in
  3rd ch from hook (skipped 2-ch does not count as st) and in each ch
  across", on a Ch 242 foundation. This is *exactly* the corrected
  construction verified against Bella Coco's published pattern (tote bag,
  Jul 4 batch): skip 2 (not 3), and 242 satisfies the required "multiple
  of 3, plus 2" ((242-2)/3 = 80 clean). `checks/known_constructions.py`
  confirms both independently -- no warnings from that check on this
  file.
- **Linen's missing setup row is fixed**: Linen's own Stitch Guide
  "Foundation:" line now reads "SC in 2nd ch from hook and in each ch
  across" (the same plain, unambiguous whole-row shape Moss has always
  used) followed by a separate Row 2 for the alternating pattern --
  instead of the old ambiguous "SC in 2nd ch from hook, *ch 1, skip 1 ch,
  SC in next ch; rep from * to end" mixed shape that jumped straight into
  alternating with no setup row (the exact inconsistency `cross_variant.py`
  was built to catch, Jul 2 batch tenth round). The body's own Row 1
  matches the guide change. Result: Linen now resolves with zero
  warnings for the first time across every batch this project has QA'd --
  the recurring "Row 1 cannot verify" warning is gone because the
  underlying ambiguous construction itself is gone, not because the tool
  changed.
- **Tool gap found and fixed**: the corrected Waffle Row 1 introduced a
  new clause shape our own `foundation_into_chain` regex didn't allow --
  a parenthetical clarification ("(skipped 2-ch does not count as st)")
  inserted between the ordinal clause and "and in each ch across". This
  fell through to unrecognized, which cascaded into a false "Row 1 reads
  like non-stitch content" completeness warning on an otherwise-already-
  fixed, correct row. **Fixed**: the regex now optionally allows any
  parenthetical there. Tests in `tests/test_stitch_parser.py` cover both
  the new phrasing and confirm the plain shape (no parenthetical) still
  works unchanged.
- **Batch result**: sedge, waffle, linen, moss, bobble, tr, dc, hdc, sc --
  all PASS. shell -- REVIEW (1 warning, the same pre-existing "centre dc
  of next shell" landmark-reference math limitation from the Jun 27
  batch, unchanged and expected). Full suite passes (36 tests, 1 skip).

