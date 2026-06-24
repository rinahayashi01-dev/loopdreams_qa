"""Report assembly: turns a Pattern + list of Issues into a serializable report."""

from __future__ import annotations
from .models import Pattern, Issue


def build_report(pattern: Pattern, issues: list[Issue]) -> dict:
    return {
        "source": pattern.source_path,
        "declared_system": pattern.declared_system,
        "declared_system_source": pattern.declared_system_source,
        "rounds_parsed": len(pattern.rounds),
        "sections_found": sorted(pattern.sections.keys()),
        "extraction_warnings": pattern.extraction_warnings,
        "issue_counts": {
            "error": sum(1 for i in issues if i.severity == "error"),
            "warning": sum(1 for i in issues if i.severity == "warning"),
            "info": sum(1 for i in issues if i.severity == "info"),
        },
        "issues": [
            {"check": i.check, "severity": i.severity, "location": i.location, "message": i.message}
            for i in issues
        ],
    }


_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def render_text_report(report: dict) -> str:
    lines = []
    lines.append(f"QA report: {report['source']}")
    lines.append(
        f"Declared system: {report['declared_system'] or 'not determined'} "
        f"({report['declared_system_source']})"
    )
    lines.append(f"Sections found: {', '.join(report['sections_found']) or 'none'}")
    lines.append(f"Rounds/rows parsed: {report['rounds_parsed']}")

    if report["extraction_warnings"]:
        lines.append("Extraction warnings:")
        for w in report["extraction_warnings"]:
            lines.append(f"  - {w}")

    counts = report["issue_counts"]
    lines.append("")
    lines.append(f"Issues: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info")
    lines.append("")

    issues = sorted(report["issues"], key=lambda i: _SEVERITY_ORDER.get(i["severity"], 9))
    if not issues:
        lines.append("No issues found.")
    else:
        for i in issues:
            lines.append(f"[{i['severity'].upper()}] ({i['check']}) {i['location']}: {i['message']}")

    return "\n".join(lines)
