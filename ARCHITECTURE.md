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
- Real LoopDreams sample output to validate section-detection regexes and
  phrasing assumptions against actual generated text (everything so far has
  been validated against hand-written synthetic patterns).
- Decide on output format for batch runs (one JSON per file? one combined
  CSV/spreadsheet for a tester to skim?).
