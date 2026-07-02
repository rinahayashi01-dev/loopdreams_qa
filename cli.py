import argparse
import sys

from .extraction import extract_text
from .pattern_parser import parse
from .checks import stitch_count, terminology, completeness
from .report import build_report, to_text, to_json


def run(path: str, json_output: bool = False, quiet: bool = False) -> dict:
    raw_text = extract_text(path)
    pattern = parse(raw_text)

    issues = []
    issues.extend(stitch_count.check(pattern))
    issues.extend(terminology.check(pattern))
    issues.extend(completeness.check(pattern))

    report = build_report(pattern, issues)
    if not quiet:
        if json_output:
            print(to_json(report))
        else:
            print(to_text(report))
    return report


def main():
    parser = argparse.ArgumentParser(prog="python -m loopdreams_qa.cli")
    parser.add_argument("path", help="Path to a .pdf or .docx pattern file")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable text")
    args = parser.parse_args()
    report = run(args.path, json_output=args.json)
    sys.exit(1 if report["summary"]["errors"] else 0)


if __name__ == "__main__":
    main()
