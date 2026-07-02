import json


def build_report(pattern, issues: list) -> dict:
    by_category = {"stitch_count": [], "terminology": [], "completeness": []}
    for issue in issues:
        by_category.setdefault(issue.category, []).append(issue.to_dict())

    n_errors = sum(1 for i in issues if i.severity == "error")
    n_warnings = sum(1 for i in issues if i.severity == "warning")

    return {
        "title": pattern.title,
        "declared_system": pattern.declared_system,
        "declared_system_source": pattern.declared_system_source,
        "foundation_chain": pattern.foundation_chain,
        "row_count": len(pattern.rows),
        "summary": {
            "errors": n_errors,
            "warnings": n_warnings,
            "status": "FAIL" if n_errors else ("REVIEW" if n_warnings else "PASS"),
        },
        "issues": by_category,
    }


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2)


def to_text(report: dict) -> str:
    lines = []
    title = report.get("title") or "(untitled pattern)"
    lines.append(f"QA Report: {title}")
    lines.append(f"Declared terminology: {report['declared_system']} (source: {report['declared_system_source']})")
    lines.append(f"Status: {report['summary']['status']}  "
                 f"({report['summary']['errors']} error(s), {report['summary']['warnings']} warning(s))")
    lines.append("")
    for category in ("stitch_count", "terminology", "completeness"):
        cat_issues = report["issues"].get(category, [])
        label = {"stitch_count": "STITCH-COUNT MATH", "terminology": "TERMINOLOGY",
                 "completeness": "COMPLETENESS"}[category]
        lines.append(f"== {label} ==")
        if not cat_issues:
            lines.append("  No issues found.")
        else:
            for issue in cat_issues:
                tag = issue["severity"].upper()
                lines.append(f"  [{tag}] {issue['location']}: {issue['message']}")
        lines.append("")
    return "\n".join(lines)
