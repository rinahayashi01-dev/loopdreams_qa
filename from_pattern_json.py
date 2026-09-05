"""
Adapter for scripts/batch-test.ts in the sibling `loopdreams` repo.

That script generates patterns via generate-pattern's dry_run mode --
structured JSON (rows with row_number/stitch_count/instructions), not a
PDF/docx file -- so there's nothing for extraction.py to extract text from.
Rather than duplicating this tool's own text-format knowledge (section
headers, the required "(N sts)" trailing count per row, required Materials
fields, etc.) on the TypeScript side, the batch script sends a small JSON
payload here and this module owns turning it into the raw text
pattern_parser.parse() expects, then runs the normal check pipeline.

Input (stdin): a JSON object --
{
  "title": str,
  "gauge_sts_per_in": float | null, "gauge_rows_per_in": float | null,
  "yarn_weight_name": str | null, "hook_label": str | null,
  "abbreviations": [{"abbr": str, "definition": str}, ...],
  "rows": [
    {"row_number": int, "stitch_count": int, "instructions": str, "section": str | null},
    ...
  ]
}

Output (stdout): the same JSON report shape cli.run_for_pattern's --json
mode prints (see report.py:build_report) -- {title, declared_system,
foundation_chain, row_count, summary: {errors, warnings, status}, issues}.

Row -> text mapping:
- A flat construction's row 1 is always a pure chain foundation ("Ch 35,
  turn.", "Foundation: Ch 59.") -- its own `stitch_count` field is the count
  the FIRST WORKED row will produce, not a count this chain-only row itself
  produces (chains aren't "sts"). Confirmed against PatternPrintView.tsx,
  which hardcodes `stitchCount: 0` (no badge at all) for exactly this row --
  the real exported PDF never shows a count next to it. Detected via
  _FOUNDATION_CHAIN_RE and rendered as a bare "Foundation: ..." line with no
  appended count, matching pattern_parser.py's own dedicated foundation-chain
  regex (independent of row_re) -- and every row after it in the same
  section gets renumbered starting from 1, since this tool doesn't count
  the foundation chain itself as "Row 1" (loopdreams_qa/tests/
  test_pattern_parser.py's fixtures always show "Foundation:..." followed
  by "Row 1:", never "Row 2:"). Round/in-the-round constructions (coaster,
  amigurumi) have no such row -- their row 1 already has real worked
  stitches (e.g. "Magic ring... (12 dc)"), so nothing is detected and every
  row_number is used as-is.
- row_re in pattern_parser.py requires a trailing "(~?N sts?)" annotation to
  recognize a (non-foundation) row at all. Round constructions' real output
  (e.g. "...sl st to top of ch 3 to join. (12 dc)") ends in the stitch
  abbreviation instead -- append a normalized "(N sts)" whenever one isn't
  already there. This mirrors how real LoopDreams PDF samples this tool was
  built against actually look (see pattern_parser.py's row_re comment:
  coaster/mitten samples restate the count twice, "(24 dc) (24 sts)") --
  the tool already strips the earlier, redundant annotation as noise.
- A row whose instructions start with "Border:"/"Assembly:"/"Pocket:"/
  "Adding a Zipper:"/"Adding a Liner:"/"Adding a Zipper and Liner:", or
  start with "Handles (", is treated as Finishing content instead of a
  numbered pattern row, matching _RE_BORDER_MARKER's/_parse_finishing's own
  "<Label> (make N):" convention. Deliberately NOT generalized to "any last
  row" the way the sibling loopdreams repo's generatePatternApi.ts
  (`isFinishing`) now is (tried it, then reverted): _parse_finishing only
  knows how to extract a checkable RoundRow from a "Border:"/"Pocket:"- or
  "<Label> (make N):"-shaped blob, so moving an ordinary plain-text closing
  row (no such marker) under a synthesized "Finishing" heading silently
  drops it from stitch-count verification entirely (nothing else in
  pattern_parser recognizes it there) -- trading a real completeness gap
  for a worse, silent one. These are safe additions to the allowlist for
  the same reason "Border:" was: Tote Bag's buildToteBagRows already emits
  real assembly/handle/pocket/liner content in exactly these shapes, so
  routing them under Finishing doesn't drop anything from verification --
  they were just never being recognized as Finishing content at all,
  despite already existing. (Only "Handles" needs the open-paren form
  rather than a trailing colon -- its label is always followed by a
  parenthetical variant clause, e.g. "(make 2)"/"(leather, purchased)"/
  "(make 2, shoulder-strap length)", before the colon.)
  Real sample (Tote Bag with pocket + liner, no zipper/straps): the
  trailing run is Assembly, Handles, Pocket, then "Adding a Liner" -- FOUR
  consecutive finishing-shaped rows, not just one. Checking only the
  single last row (as this adapter did until now) left Assembly/Handles/
  Pocket stuck as ordinary numbered rows even when a Liner/Zipper row
  followed them, since a real body row that happens to be finishing-shaped
  is never anything other than the true trailing run in practice (nothing
  in generate-pattern EVER puts non-finishing body content after Assembly)
  -- so this now walks backward from the pattern's actual last row,
  collecting every consecutive row that matches the finishing-row pattern,
  not just checking the single final one.
  Assembly/Zipper/Liner rows have no "(N sts)"/"(make N)" shape at all (no
  stitch content -- pure fabric/sewing prose) and _parse_finishing has no
  regex that matches them, so they're safely absorbed into the Finishing
  section's raw text with zero rows extracted -- exactly the same "nothing
  to verify" outcome as if they'd been hand-written directly under a real
  "Finishing" heading. Pocket, like Border, DOES have real stitch content
  and a trailing "(N sts)", so _parse_finishing's Border regex is
  generalized to accept "Pocket" as an alternate label.
  completeness.py's _check_finishing_present is, on inspection, working as
  intended here rather than buggy: its own comment explains flat-panel
  constructions (blanket, tote, dishcloth) are deliberately held to a
  stricter standard than continuous-spiral amigurumi ones (which get an
  explicit "no seams to join" exception) -- so "No Finishing" on Dishcloth/
  Throw Blanket/Shawl/Amigurumi Egg (whose oval foundation isn't magic-ring,
  so it doesn't qualify for that exception either) most likely reflects a
  genuine content gap in those templates' generators (no separate
  weave-in-ends/assembly guidance) -- see generate-pattern's
  buildGenericFlatRows/buildScarfRows and the moss/linen/waffle/sedge/
  bobble/shell builders, all fixed to fasten off with "weave in ends" on
  2026-07-17. Tote Bag was the one exception: its generator already had
  real Assembly/Handles/Pocket/Liner content: this adapter just wasn't
  recognizing all of it.
- A last row whose text tells the crocheter to redo the whole pattern for a
  second item ("To complete the pair, repeat Rows 1-29 once more to make a
  second, matching mitten.") isn't stitch content at all -- goes to a
  trailing "Notes" section (untouched by any row/stitch-count check) rather
  than a numbered row, with no count appended. Real sample: Mittens'
  buildMittenRows appends exactly this as the pattern's actual last row,
  after the real fasten-off/closure row -- left as a normal row with a
  fabricated count, pattern_parser's repeat_ref_re misreads the embedded
  "Rows 1-29" as a within-piece row-range reference and this adapter's own
  count normalization stamps a bogus declared count onto it, producing a
  genuine false stitch-count-mismatch error.
- Consecutive rows sharing the same non-null `section` (multi-piece
  garments, e.g. the drop-shoulder sweater's Back/Front/Sleeves/Assembly)
  get an all-caps component header line before them, matching
  _RE_COMPONENT_HEADER's convention for multi-panel patterns. generate-
  pattern's own row_number is GLOBAL across the whole pattern, not
  section-relative (Back 1-49, Front 50-98, Sleeves 99-135, ...) -- but the
  real app restarts numbering per piece for display (see the "Multi-piece
  garments... restart row numbering within it" comment on PatternStep's
  `section` field in generatePatternApi.ts), and pattern_parser.py expects
  that same per-piece renumbering. So each section independently checks its
  own first row for a foundation shape (plain chain-only, or the sweater
  sleeves' "<Label> (make N): Ch X." shape) and renumbers everything after
  it in that section starting from 1 (or 2, when the foundation itself
  consumes row 1) -- never trusting the incoming global row_number once a
  section boundary is crossed.
"""
import json
import re
import sys

from .cli import run_for_pattern
from .pattern_parser import parse

_TRAILING_COUNT_RE = re.compile(r"\(\s*~?\s*\d+\s*sts?\s*\)\.?\s*$", re.I)
_FINISHING_ROW_RE = re.compile(
    r"^\s*(?:Border|Assembly|Pocket|Adding\s+a\s+(?:Zipper\s+and\s+Liner|Zipper|Liner))\s*:|^\s*Handles\s*\(",
    re.I,
)
# Colour name after the identifier is itself optional -- real sample
# (LoopDreams generator, colourwork rows): "With Colour 1, Ch 33, turn."
# states the identifier alone with no "-- Name" suffix at all (the name is
# a frontend-only display enrichment, never part of the stored pattern text
# this tool actually receives -- same real cause as pattern_parser.py's own
# colour-clause regexes, which had this same mandatory-name bug fixed
# separately; this site was missed in that pass since it lives in this
# adapter file, not pattern_parser.py itself). Without this, a bare-colour
# Row 1 fails _is_chain_only_foundation, falls through to being rendered as
# an ordinary numbered row with its "next row's" stitch_count wrongly
# stamped onto ITS OWN declared count, and pattern.foundation_chain is never
# set at all -- producing a genuine false stitch-count-mismatch on Row 2
# (the checker misreads the foundation chain count from that wrongly
# labeled "(N sts)" instead of the real Ch N in the text).
_FOUNDATION_CHAIN_RE = re.compile(
    r"^(?:Foundation(?:\s+chain)?:?\s*)?"
    # Also accepts a bare "With White," designator (no "Colour" word at
    # all) -- margin/blank picture-grid cells not part of the chosen
    # palette are labelled literally "White" by the generator's own
    # colourLabel(), not a numbered "Colour N" (see pattern_parser.py's
    # matching fix for the BLANK_COLOUR source).
    r"(?:With\s+(?:Colour\s+\S+|White)(?:\s*[—-]\s*\w+)?,?\s*)?"
    r"Ch\s+\d+\.?,?\s*(?:turn\.?)?$",
    re.I,
)
# A repeated-piece foundation (e.g. the drop-shoulder sweater's "Sleeves
# (make 2): Ch 39.") -- pattern_parser.py's own _RE_ROW_AS_FOUNDATION
# expects this rendered as a numbered row (crucially with NO colon after
# the row number -- "Row 1 Sleeves (make 2): ...", unlike every other row
# shape this adapter emits) carrying its own trailing "(N sts)", unlike the
# plain "Foundation: Ch N." shape which never has a count at all. Confirmed
# against pattern_parser.py's own comment: "Row 1 Sleeves (make 2): Ch 35.
# (32 sts)" -- real sample, sweater Jul 12 batch.
# The colour clause is accepted in exactly the position _FOUNDATION_CHAIN_RE
# accepts it — immediately after the label — because a repeated piece needs to
# say which yarn it is worked in for the same reason a main panel does
# (loopdreams#487), and a sweater's sleeves became the first place that mattered
# once garments could carry a design (loopdreams#493). Without it the whole
# "(make N):" component fails to parse, the piece stops being finishing content,
# and the misread cascades into a false row-range gap and a false stitch-count
# mismatch on the row after it.
_MAKE_N_FOUNDATION_RE = re.compile(
    r"^[A-Za-z][\w\s]*?\(make\s+\d+\)\s*:\s*"
    r"(?:With\s+(?:Colour\s+\S+|White)(?:\s*[—-]\s*\w+)?,?\s*)?"
    r"Ch\s+\d+\.?\s*$",
    re.I,
)
# A trailing narrative remark telling the crocheter to redo the whole
# pattern for a second item ("To complete the pair, repeat Rows 1-29 once
# more to make a second, matching mitten."). This isn't new row content at
# all -- it doesn't describe any stitches -- but pattern_parser.py's
# repeat_ref_re still recognizes the embedded "Rows 1-29" as a row-range
# reference (that shorthand is normally used for a WITHIN-piece repeat, not
# a whole-pattern one), and this adapter's own "(N sts)" normalization then
# stamps this row's real stitch_count onto that misidentified reference --
# producing a genuine false stitch-count-mismatch error against a
# correctly generated pattern. Real sample: Mittens (generate-pattern's
# buildMittenRows appends this as its actual last row, after the real
# fasten-off/closure row).
_REPEAT_WHOLE_PATTERN_RE = re.compile(
    r"repeat\s+Rows?\s+\d+\s*[-–]\s*\d+.*(?:second|another|matching|pair)",
    re.I,
)


def _is_chain_only_foundation(instructions: str) -> bool:
    return bool(_FOUNDATION_CHAIN_RE.match(instructions.strip()))


def _is_make_n_foundation(instructions: str) -> bool:
    return bool(_MAKE_N_FOUNDATION_RE.match(instructions.strip()))


def _is_repeat_whole_pattern_note(instructions: str) -> bool:
    return bool(_REPEAT_WHOLE_PATTERN_RE.search(instructions.strip()))


def _foundation_line(row: dict) -> str:
    instructions = row["instructions"].strip()
    if re.match(r"^Foundation\b", instructions, re.I):
        return instructions
    return f"Foundation: {instructions}"


def _with_trailing_count(row: dict) -> str:
    instructions = row["instructions"].strip()
    if not _TRAILING_COUNT_RE.search(instructions):
        instructions = f"{instructions.rstrip('.')}. ({row['stitch_count']} sts)"
    return instructions


def _row_line(row_number: int, row: dict) -> str:
    return f"Row {row_number}: {_with_trailing_count(row)}"


def _section_groups(body_rows: list) -> list:
    """Splits rows into consecutive same-section runs, preserving order.
    Each group is (section_name_or_none, [rows]). A single-piece pattern
    (every `section` is None) is one group covering the whole pattern."""
    groups = []
    for row in body_rows:
        section = row.get("section")
        if groups and groups[-1][0] == section:
            groups[-1][1].append(row)
        else:
            groups.append((section, [row]))
    return groups


def build_raw_text(payload: dict) -> str:
    lines = [payload.get("title") or "Pattern"]

    lines.append("MATERIALS")
    gauge_sts = payload.get("gauge_sts_per_in")
    gauge_rows = payload.get("gauge_rows_per_in")
    if gauge_sts and gauge_rows:
        lines.append(f"Gauge: {gauge_sts * 4:g} sts x {gauge_rows * 4:g} rows = 4 in")
    lines.append("Terminology: US")
    if payload.get("yarn_weight_name"):
        lines.append(f"Yarn: {payload['yarn_weight_name']}")
    if payload.get("hook_label"):
        lines.append(f"Hook: {payload['hook_label']}")

    abbrevs = payload.get("abbreviations") or []
    if abbrevs:
        lines.append("ABBREVIATIONS")
        lines.append(", ".join(f"{a['abbr']} = {a['definition']}" for a in abbrevs))

    lines.append("PATTERN STEPS")
    body_rows = payload.get("rows") or []
    finishing_lines = []
    note_lines = []
    groups = _section_groups(body_rows)
    for group_idx, (section, rows) in enumerate(groups):
        if section:
            lines.append(section.upper())

        remaining = rows
        if remaining and _is_chain_only_foundation(remaining[0]["instructions"]):
            lines.append(_foundation_line(remaining[0]))
            remaining = remaining[1:]
            renumber_from = 1
        elif remaining and _is_make_n_foundation(remaining[0]["instructions"]):
            lines.append(f"Row 1 {_with_trailing_count(remaining[0])}")
            remaining = remaining[1:]
            renumber_from = 2
        else:
            renumber_from = None  # keep each row's own row_number as-is

        last_group = group_idx == len(groups) - 1

        # Real sample (Tote Bag with pocket + liner): the trailing run is
        # Assembly, Handles, Pocket, then "Adding a Liner" -- four
        # consecutive finishing-shaped rows, not just the single last one.
        # Walk backward from the true last row collecting every consecutive
        # match, rather than only ever checking the final row. The
        # "repeat whole pattern" note (Mittens) is a separate, mutually
        # exclusive case -- it isn't finishing-shaped itself, so it's
        # excluded from the scan below before walking backward from it.
        note_row_idx = None
        finishing_start_idx = len(remaining)
        if last_group and remaining:
            scan_end = len(remaining)
            if _is_repeat_whole_pattern_note(remaining[-1]["instructions"]):
                note_row_idx = len(remaining) - 1
                scan_end = note_row_idx
            idx = scan_end
            while idx > 0 and _FINISHING_ROW_RE.match(remaining[idx - 1]["instructions"]):
                idx -= 1
            finishing_start_idx = idx

        for i, row in enumerate(remaining):
            row_number = renumber_from + i if renumber_from is not None else row["row_number"]
            if i == note_row_idx:
                # Not stitch content -- leave the count off entirely so it
                # can't be misread as a declared row count.
                note_lines.append(row["instructions"].strip())
            elif last_group and i >= finishing_start_idx:
                finishing_lines.append(_row_line(row_number, row))
            else:
                lines.append(_row_line(row_number, row))

    if finishing_lines:
        lines.append("Finishing")
        lines.extend(finishing_lines)

    if note_lines:
        lines.append("Notes")
        lines.extend(note_lines)

    return "\n".join(lines) + "\n"


def main():
    payload = json.load(sys.stdin)
    raw_text = build_raw_text(payload)
    pattern = parse(raw_text)
    # Colourwork only: the design the pattern was generated from, so
    # colourwork_orientation can compare instructions against intent. Absent
    # for a plain pattern, and that check then does nothing.
    pattern.design_grid = payload.get("design_grid")
    pattern.design_palette = payload.get("palette")
    # The instructions VERBATIM. The parser deliberately strips a row's leading
    # "With Colour N," (it is not a stitch clause), which is exactly the token
    # colourwork_orientation needs, so that check reads the original text rather
    # than depending on parser internals that were never meant to preserve it.
    pattern.design_rows = payload.get("rows") or []
    report = run_for_pattern(pattern, quiet=True)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
