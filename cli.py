"""
CLI entry point.

Usage:
    python -m loopdreams_qa.cli path/to/pattern.docx
    python -m loopdreams_qa.cli path/to/pattern.pdf --json

Designed to run on one file at a time for now; a batch wrapper that loops
this over a folder is the planned next step, sharing this same `run()`
function so nothing here needs to change.
"""

from __future__ import annotations
import argparse
import json
import sys

from . import extraction, pattern_parser, report as report_mod
from .checks.stitch_count import check_stitch_counts
from .checks.terminology import check_terminology
from .checks.completeness import check_completeness


def run(path: str) -> dict:
    full_text, extraction_warnings = extraction.extract_text(path)
    pattern = pattern_parser.build_pattern(path, full_text)
    pattern.extraction_warnings = extraction_warnings + pattern.extraction_warnings

    issues = []
    issues.extend(check_stitch_counts(pattern))
    issues.extend(check_terminology(pattern))
    issues.extend(check_completeness(pattern))

    return report_mod.build_report(pattern, issues)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QA-check a LoopDreams crochet pattern (PDF or Word).")
    parser.add_argument("path", help="Path to the pattern file (.pdf or .docx)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of a human-readable report")
    args = parser.parse_args(argv)

    try:
        rep = run(args.path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(report_mod.render_text_report(rep))

    return 1 if rep["issue_counts"]["error"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
