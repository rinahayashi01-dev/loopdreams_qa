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
- A row whose instructions start with "Border:" and is the pattern's last
  row is treated as Finishing content instead of a numbered pattern row,
  matching _RE_BORDER_MARKER's own convention.
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
_BORDER_ROW_RE = re.compile(r"^\s*Border\s*:", re.I)
_FOUNDATION_CHAIN_RE = re.compile(
    r"^(?:Foundation(?:\s+chain)?:?\s*)?"
    r"(?:With\s+Colour\s+\S+\s*[—-]\s*\w+,?\s*)?"
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
_MAKE_N_FOUNDATION_RE = re.compile(r"^[A-Za-z][\w\s]*?\(make\s+\d+\)\s*:\s*Ch\s+\d+\.?\s*$", re.I)


def _is_chain_only_foundation(instructions: str) -> bool:
    return bool(_FOUNDATION_CHAIN_RE.match(instructions.strip()))


def _is_make_n_foundation(instructions: str) -> bool:
    return bool(_MAKE_N_FOUNDATION_RE.match(instructions.strip()))


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
        for i, row in enumerate(remaining):
            row_number = renumber_from + i if renumber_from is not None else row["row_number"]
            is_last_row_overall = last_group and i == len(remaining) - 1
            if is_last_row_overall and _BORDER_ROW_RE.match(row["instructions"]):
                finishing_lines.append(_row_line(row_number, row))
            else:
                lines.append(_row_line(row_number, row))

    if finishing_lines:
        lines.append("Finishing")
        lines.extend(finishing_lines)

    return "\n".join(lines) + "\n"


def main():
    payload = json.load(sys.stdin)
    raw_text = build_raw_text(payload)
    pattern = parse(raw_text)
    report = run_for_pattern(pattern, quiet=True)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
