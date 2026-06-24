"""
Batch QA runner: process every .docx / .pdf in a folder.

Usage
-----
    python -m loopdreams_qa.batch path/to/folder/
    python -m loopdreams_qa.batch path/to/folder/ --csv qa_results.csv
    python -m loopdreams_qa.batch path/to/folder/ --json-dir out/json/
    python -m loopdreams_qa.batch path/to/folder/ --csv results.csv --json-dir out/json/

Exit code: 0 if all patterns passed, 1 if any had errors or failed to process.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from .cli import run as qa_run

SUPPORTED_EXTENSIONS = {".docx", ".pdf"}

CSV_FIELDNAMES = [
    "file", "errors", "warnings", "infos",
    "declared_system", "rounds_parsed", "sections_found",
    "issues", "extraction_warnings",
]


def find_pattern_files(folder: str) -> list[Path]:
    """Return all .docx and .pdf files in *folder* (non-recursive), sorted by name."""
    return sorted(
        p for p in Path(folder).iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def run_batch(paths: list[Path]) -> list[dict]:
    """
    Run QA on each file.  Per-file errors are caught so one corrupt file
    doesn't abort the whole batch — they produce a synthetic report with
    check="extraction" and severity="error".
    """
    results = []
    for path in paths:
        try:
            report = qa_run(str(path))
        except Exception as exc:
            report = {
                "source": str(path),
                "declared_system": None,
                "declared_system_source": "none",
                "rounds_parsed": 0,
                "sections_found": [],
                "extraction_warnings": [],
                "issue_counts": {"error": 1, "warning": 0, "info": 0},
                "issues": [
                    {
                        "check": "extraction",
                        "severity": "error",
                        "location": path.name,
                        "message": f"Failed to process file: {exc}",
                    }
                ],
            }
        results.append(report)
    return results


def _report_to_csv_row(report: dict) -> dict:
    issues_text = " | ".join(
        f"[{i['severity'].upper()}] {i['location']}: {i['message']}"
        for i in report["issues"]
    )
    return {
        "file": os.path.basename(report["source"]),
        "errors": report["issue_counts"]["error"],
        "warnings": report["issue_counts"]["warning"],
        "infos": report["issue_counts"]["info"],
        "declared_system": report["declared_system"] or "unknown",
        "rounds_parsed": report["rounds_parsed"],
        "sections_found": ", ".join(report["sections_found"]),
        "issues": issues_text,
        "extraction_warnings": " | ".join(report.get("extraction_warnings", [])),
    }


def write_csv(results: list[dict], out_path: str) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(_report_to_csv_row(r) for r in results)


def write_json_dir(results: list[dict], json_dir: str) -> None:
    out = Path(json_dir)
    out.mkdir(parents=True, exist_ok=True)
    for report in results:
        stem = Path(report["source"]).stem
        (out / f"{stem}_qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch QA-check all .docx/.pdf pattern files in a folder."
    )
    parser.add_argument("folder", help="Folder containing pattern files")
    parser.add_argument("--csv", metavar="FILE", help="Write a summary CSV to FILE")
    parser.add_argument("--json-dir", metavar="DIR", help="Write one JSON report per file into DIR")
    args = parser.parse_args(argv)

    paths = find_pattern_files(args.folder)
    if not paths:
        print(f"No .docx or .pdf files found in: {args.folder}", file=sys.stderr)
        return 1

    results = run_batch(paths)

    any_error = False
    for report in results:
        counts = report["issue_counts"]
        if counts["error"]:
            any_error = True
        status = "FAIL" if counts["error"] else "PASS"
        print(f"{status}  {os.path.basename(report['source'])}  ({counts['error']} error(s), {counts['warning']} warning(s))")

    if args.csv:
        write_csv(results, args.csv)
        print(f"\nCSV written to: {args.csv}")

    if args.json_dir:
        write_json_dir(results, args.json_dir)
        print(f"JSON reports written to: {args.json_dir}/")

    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
