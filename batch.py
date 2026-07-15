"""
Batch wrapper over a folder of patterns, built on top of cli.run() so the
core extract -> parse -> check -> report pipeline doesn't change for it
(per ARCHITECTURE.md's "next steps" note from the very first version of
this tool).

Human-readable mode prints each file's full report exactly as the
single-file CLI does (every batch run so far has been done by hand this
way, in a shell for-loop), then appends one combined summary table.
--json mode suppresses the per-file prints and emits a single combined
JSON document instead, since N separate JSON blobs on stdout isn't
something a script can consume cleanly.

Also runs cross_variant.check() across every parsed pattern in the batch
-- a check that inherently can't live in checks/ (which all operate on
one pattern at a time) since it compares sibling files against each
other. See cross_variant.py's own docstring for why/how.
"""
import argparse
import json
import os
import sys

from . import cli
from . import cross_variant
from .extraction import extract_text
from .pattern_parser import parse

PATTERN_EXTENSIONS = (".pdf", ".docx")


def discover_patterns(dir_path: str) -> list:
    names = [n for n in os.listdir(dir_path) if n.lower().endswith(PATTERN_EXTENSIONS)]
    return [os.path.join(dir_path, n) for n in sorted(names)]


def _batch_summary(results: dict) -> dict:
    statuses = [r["summary"]["status"] for r in results.values()]
    return {
        "files_checked": len(results),
        "pass": statuses.count("PASS"),
        "review": statuses.count("REVIEW"),
        "fail": statuses.count("FAIL"),
        "total_errors": sum(r["summary"]["errors"] for r in results.values()),
        "total_warnings": sum(r["summary"]["warnings"] for r in results.values()),
    }


def _summary_text(results: dict, summary: dict, cross_variant_issues: list) -> str:
    lines = ["", "=" * 60, "BATCH SUMMARY", "=" * 60]
    name_width = max((len(n) for n in results), default=4)
    for name, report in results.items():
        s = report["summary"]
        lines.append(
            f"{name.ljust(name_width)}  {s['status']:<7} "
            f"({s['errors']} error(s), {s['warnings']} warning(s))"
        )
    lines.append("")
    lines.append(
        f"{summary['files_checked']} file(s) checked: {summary['pass']} PASS, "
        f"{summary['review']} REVIEW, {summary['fail']} FAIL"
    )
    if cross_variant_issues:
        lines.append("")
        lines.append("=" * 60)
        lines.append("CROSS-VARIANT CONSISTENCY")
        lines.append("=" * 60)
        for issue in cross_variant_issues:
            lines.append(f"[{issue.severity.upper()}] {issue.location}: {issue.message}")
    return "\n".join(lines)


def run_batch(dir_path: str, json_output: bool = False) -> dict:
    paths = discover_patterns(dir_path)

    results = {}
    patterns = {}
    for path in paths:
        name = os.path.basename(path)
        # Printed unconditionally (even in --json mode, where it goes to
        # stderr so it never lands in the JSON on stdout) -- real need
        # (scarf/sweater, Jul 12-15 batches): those patterns need OCR
        # (~15-20s/page), and a batch of several such files running
        # sequentially with zero output otherwise looks hung for minutes.
        print(f"Checking {name}...", file=sys.stderr if json_output else sys.stdout, flush=True)
        # Extract+parse ONCE and reuse for both the report and
        # cross_variant.check() below -- this used to extract twice per
        # file (once inside cli.run(), once again here), which silently
        # doubled the OCR cost for every OCR-needing file.
        pattern = parse(extract_text(path))
        patterns[name] = pattern
        # quiet during the per-file call when we're going to emit one
        # combined JSON document at the end instead of per-file printing.
        results[name] = cli.run_for_pattern(pattern, json_output=False, quiet=json_output)

    cross_variant_issues = cross_variant.check(patterns)

    summary = _batch_summary(results)
    combined = {
        "files": results,
        "cross_variant_issues": [i.to_dict() for i in cross_variant_issues],
        "batch_summary": summary,
    }

    if json_output:
        print(json.dumps(combined, indent=2))
    else:
        print(_summary_text(results, summary, cross_variant_issues))

    return combined


def main():
    parser = argparse.ArgumentParser(prog="python -m loopdreams_qa.batch")
    parser.add_argument("directory", help="Folder containing .pdf/.docx pattern files")
    parser.add_argument("--json", action="store_true",
                         help="Output one combined JSON document instead of human-readable text")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Not a directory: {args.directory}", file=sys.stderr)
        sys.exit(2)

    if not discover_patterns(args.directory):
        print(f"No .pdf/.docx pattern files found in: {args.directory}", file=sys.stderr)
        sys.exit(2)

    combined = run_batch(args.directory, json_output=args.json)
    sys.exit(1 if combined["batch_summary"]["fail"] else 0)


if __name__ == "__main__":
    main()
