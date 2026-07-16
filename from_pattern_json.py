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
- Every row becomes "Row {row_number}: {instructions}".
- row_re in pattern_parser.py requires a trailing "(~?N sts?)" annotation to
  recognize a row at all. Round constructions' real output (e.g. "...sl st
  to top of ch 3 to join. (12 dc)") ends in the stitch abbreviation instead
  -- append a normalized "(N sts)" whenever one isn't already there. This
  mirrors how real LoopDreams PDF samples this tool was built against
  actually look (see pattern_parser.py's row_re comment: coaster/mitten
  samples restate the count twice, "(24 dc) (24 sts)") -- the tool already
  strips the earlier, redundant annotation as noise.
- A row whose instructions start with "Border:" and is the pattern's last
  row is treated as Finishing content instead of a numbered pattern row,
  matching _RE_BORDER_MARKER's own convention.
- Consecutive rows sharing the same non-null `section` (multi-piece
  garments, e.g. the drop-shoulder sweater's Back/Front/Sleeves/Assembly)
  get an all-caps component header line before them, matching
  _RE_COMPONENT_HEADER's convention for multi-panel patterns.
"""
import json
import re
import sys

from .cli import run_for_pattern
from .pattern_parser import parse

_TRAILING_COUNT_RE = re.compile(r"\(\s*~?\s*\d+\s*sts?\s*\)\.?\s*$", re.I)
_BORDER_ROW_RE = re.compile(r"^\s*Border\s*:", re.I)


def _row_line(row: dict) -> str:
    instructions = row["instructions"].strip()
    if not _TRAILING_COUNT_RE.search(instructions):
        instructions = f"{instructions.rstrip('.')}. ({row['stitch_count']} sts)"
    return f"Row {row['row_number']}: {instructions}"


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
    current_section = None
    finishing_lines = []
    last_idx = len(body_rows) - 1
    for i, row in enumerate(body_rows):
        section = row.get("section")
        if section and section != current_section:
            lines.append(section.upper())
            current_section = section
        if i == last_idx and _BORDER_ROW_RE.match(row["instructions"]):
            finishing_lines.append(_row_line(row))
        else:
            lines.append(_row_line(row))

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
