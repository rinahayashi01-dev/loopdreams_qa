"""
Raw text -> Pattern (sections, abbreviation key, declared system, rows).

Handles real-world extraction noise:
- Repeated page header/footer lines (timestamp + filename, URL + page number)
  from PDF-exported web pages -- stripped before anything else.
- PDF line-wrapping mid-sentence (pdfplumber emits a newline at every visual
  line break, which is usually just a wrapped space in the original
  paragraph). Within a section body we join wrapped lines with a single
  space rather than treating every newline as meaningful, UNLESS the next
  line itself looks like a new "Label: value" field or a new "Row(s) N:"
  marker, which are kept as real boundaries.
"""
import re

from .models import Pattern, Section, RoundRow
from .stitch_parser import tokenize_round

SECTION_HEADERS = {
    "materials": "materials",
    "abbreviations": "abbreviations",
    "abbreviation key": "abbreviations",
    "stitch guide": "stitch_guide",
    "pattern steps": "instructions",
    "instructions": "instructions",
    "finishing": "finishing",
    "notes": "notes",
    "confidence summary": "ignored_meta",  # LoopDreams' own auto-QA output -- not pattern content
}

_RE_PAGE_HEADER = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*[AP]M\b.*$")
_RE_PAGE_FOOTER = re.compile(r"^https?://\S+\s+\d+/\d+$")

_RE_FIELD_LINE = re.compile(r"^[A-Za-z][A-Za-z /]{1,24}:\s*\S")
_RE_ROW_MARKER = re.compile(r"^Rows?\s+\d+", re.I)
_RE_FOUNDATION_MARKER = re.compile(r"^Foundation(?:\s+chain)?\s*:", re.I)
_RE_BORDER_MARKER = re.compile(r"^Border\s*:", re.I)


def _strip_noise_lines(raw_text: str) -> list:
    lines = raw_text.split("\n")
    keep = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if _RE_PAGE_HEADER.match(s) or _RE_PAGE_FOOTER.match(s):
            continue
        keep.append(s)
    return keep


def _split_into_sections(lines: list) -> list:
    """Split cleaned lines into raw Section objects by header lines."""
    sections = []
    current_name = "preamble"
    current_lines = []
    for ln in lines:
        key = ln.strip().lower()
        if key in SECTION_HEADERS:
            if current_lines:
                sections.append(Section(name=current_name, raw_text="\n".join(current_lines)))
            current_name = SECTION_HEADERS[key]
            current_lines = []
        else:
            current_lines.append(ln)
    if current_lines:
        sections.append(Section(name=current_name, raw_text="\n".join(current_lines)))
    return sections


def _join_wrapped(lines_text: str, boundary_res) -> str:
    """Join PDF line-wraps with a space, but keep real boundaries (lines
    matching one of boundary_res) on their own logical line, separated by
    a double space marker so callers can re-split on it if needed."""
    lines = lines_text.split("\n")
    out_lines = []
    buf = ""
    for ln in lines:
        is_boundary = any(r.match(ln) for r in boundary_res)
        if is_boundary and buf:
            out_lines.append(buf.strip())
            buf = ln
        elif is_boundary and not buf:
            buf = ln
        else:
            buf = (buf + " " + ln).strip() if buf else ln
    if buf:
        out_lines.append(buf.strip())
    return "\n".join(out_lines)


def _parse_materials(section: Section) -> dict:
    joined = _join_wrapped(section.raw_text, [_RE_FIELD_LINE])
    blob = " ".join(joined.split("\n"))
    blob = re.sub(r"\s+", " ", blob).strip()
    # Find all label positions, slice text between them.
    label_re = re.compile(r"(?:^|(?<=[\s·]))([A-Z][a-zA-Z]{2,20}):\s*")
    matches = list(label_re.finditer(blob))
    fields = {}
    for i, m in enumerate(matches):
        label = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        value = blob[start:end].strip().strip("·").strip()
        fields[label] = value
    return fields


def _parse_abbreviations(section: Section) -> dict:
    blob = " ".join(section.raw_text.split("\n"))
    blob = re.sub(r"\s+", " ", blob).strip()
    entries = re.split(r"\s*·\s*|\s*,\s*(?=[a-z]{1,8}\s*(?:=|:|-)\s)", blob)
    abbr_key = {}
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9 ]{0,12}?)\s*(?:=|:|-)\s*(.+)$", entry)
        if m:
            abbr = m.group(1).strip().lower()
            definition = m.group(2).strip()
            abbr_key[abbr] = definition
    return abbr_key


def _parse_instructions(section: Section, pattern: Pattern):
    from . import abbreviations as ab
    custom_compound = ab.custom_compound_tokens(pattern.abbreviation_key)

    boundaries = [_RE_FOUNDATION_MARKER, _RE_ROW_MARKER]
    joined = _join_wrapped(section.raw_text, boundaries)
    blob = re.sub(r"\s+", " ", joined.replace("\n", " ")).strip()

    m = re.search(r"Foundation(?:\s+chain)?\s*:\s*Ch\s+(\d+)", blob, re.I)
    if m:
        pattern.foundation_chain = int(m.group(1))

    found_rows = []

    row_re = re.compile(
        r"Rows?\s+(\d+)(?:\s*[–-]\s*(\d+))?\s*:\s*"
        r"(?:With\s+Colour\s+([A-Za-z])\s*[—-]\s*([A-Za-z]+)\s*:\s*)?"
        r"((?:(?!Rows?\s+\d+\s*[:–-]).)*)"
        r"\(\s*~?\s*(\d+)\s*sts?\s*\)\.?",
        re.I,
    )
    for m in row_re.finditer(blob):
        row_start = int(m.group(1))
        row_end = int(m.group(2)) if m.group(2) else row_start
        color = m.group(4)
        instr_text = m.group(5).strip().rstrip(".")
        declared = int(m.group(6))
        label = f"Row {row_start}" if row_start == row_end else f"Rows {row_start}-{row_end}"
        rr = RoundRow(label=label, row_start=row_start, row_end=row_end,
                      raw_text=instr_text, color=color, declared_count=declared)
        rr.clauses = tokenize_round(instr_text, custom_compound)
        found_rows.append(rr)

    # "Rows N-M: [With Colour X -- Name:] Repeat Row(s) P[-Q]." -- a bare
    # back-reference to earlier row text, with no stitch count restated.
    # These never match row_re above (no trailing "(N sts)"), so they need
    # their own pass or they'd silently vanish from the parsed pattern.
    repeat_ref_re = re.compile(
        r"Rows?\s+(\d+)(?:\s*[–-]\s*(\d+))?\s*:\s*"
        r"(?:With\s+Colour\s+([A-Za-z])\s*[—-]\s*([A-Za-z]+)\s*:\s*)?"
        r"Repeat\s+Rows?\s+(\d+)(?:\s*[–-]\s*(\d+))?\.?",
        re.I,
    )
    for m in repeat_ref_re.finditer(blob):
        row_start = int(m.group(1))
        row_end = int(m.group(2)) if m.group(2) else row_start
        color = m.group(4)
        ref_start = int(m.group(5))
        ref_end = int(m.group(6)) if m.group(6) else ref_start
        referenced = list(range(ref_start, ref_end + 1))
        label = f"Row {row_start}" if row_start == row_end else f"Rows {row_start}-{row_end}"
        rr = RoundRow(label=label, row_start=row_start, row_end=row_end,
                      raw_text=f"[repeats Row(s) {ref_start}-{ref_end}]", color=color,
                      referenced_rows=referenced)
        found_rows.append(rr)

    found_rows.sort(key=lambda r: r.row_start)

    # Resolve "Repeat Row(s) P-Q" rows' declared_count from whichever
    # referenced row was already parsed (referenced rows always come earlier
    # in the pattern, so by this point they're already in found_rows).
    by_start = {r.row_start: r for r in found_rows if not r.referenced_rows}
    for rr in found_rows:
        if rr.referenced_rows:
            ref_row = by_start.get(rr.referenced_rows[-1]) or by_start.get(rr.referenced_rows[0])
            if ref_row is not None:
                rr.declared_count = ref_row.declared_count

    pattern.rows.extend(found_rows)


def _parse_finishing(section: Section, pattern: Pattern):
    from . import abbreviations as ab
    custom_compound = ab.custom_compound_tokens(pattern.abbreviation_key)

    blob = re.sub(r"\s+", " ", section.raw_text.replace("\n", " ")).strip()
    m = re.search(r"Border\s*:\s*(.*?)\(\s*(~?)\s*(\d+)\s*sts?\s*\)\.?", blob, re.I)
    if m:
        instr_text = m.group(1).strip().rstrip(".")
        is_approx = m.group(2) == "~"
        declared = int(m.group(3))
        rr = RoundRow(label="Border", row_start=-1, row_end=-1, raw_text=instr_text,
                      declared_count=declared, declared_count_is_approx=is_approx)
        rr.clauses = tokenize_round(instr_text, custom_compound)
        pattern.rows.append(rr)

    # A secondary component (e.g. handles/straps) stated in Finishing as
    # "<Name> (make N): ..." rather than as a numbered pattern row. Capture
    # from the label to the end of the section (or to an explicit "(N sts)"
    # if one is given) so its construction still gets verified even though
    # it isn't a "Row N:".
    comp_m = re.search(r"\b([A-Z][a-z]+)\s*\(make\s+(\d+)\)\s*:\s*(.*?)\.?\s*$", blob)
    if comp_m:
        label = comp_m.group(1).strip()
        comp_text = comp_m.group(3).strip()
        declared, is_approx = None, False
        cm = re.search(r"\(\s*(~?)\s*(\d+)\s*sts?\s*\)\.?\s*$", comp_text)
        if cm:
            is_approx = cm.group(1) == "~"
            declared = int(cm.group(2))
            comp_text = comp_text[: cm.start()].strip().rstrip(".")
        rr = RoundRow(label=f"{label} (make {comp_m.group(2)})", row_start=-2, row_end=-2,
                      raw_text=comp_text, declared_count=declared, declared_count_is_approx=is_approx)
        rr.clauses = tokenize_round(comp_text, custom_compound)
        pattern.rows.append(rr)


def parse(raw_text: str) -> Pattern:
    lines = _strip_noise_lines(raw_text)
    pattern = Pattern(raw_text=raw_text)

    # Title heuristic: first non-empty line before MATERIALS that isn't the
    # secondary metadata line ("Scarf · Intermediate · June 26, 2026").
    for ln in lines:
        if ln.strip().lower() in SECTION_HEADERS:
            break
        if pattern.title is None:
            pattern.title = ln.strip()

    raw_sections = _split_into_sections(lines)
    pattern.sections = raw_sections

    for section in raw_sections:
        if section.name == "materials":
            section.fields = _parse_materials(section)
        elif section.name == "abbreviations":
            pattern.abbreviation_key = _parse_abbreviations(section)
        elif section.name == "instructions":
            _parse_instructions(section, pattern)
        elif section.name == "finishing":
            _parse_finishing(section, pattern)

    # Declared system: prefer an explicit "Terminology:" field over heuristic.
    materials_section = next((s for s in raw_sections if s.name == "materials"), None)
    if materials_section and "terminology" in materials_section.fields:
        val = materials_section.fields["terminology"].strip().upper()
        if val in ("US", "UK"):
            pattern.declared_system = val
            pattern.declared_system_source = "explicit_field"

    if pattern.declared_system is None:
        # Heuristic fallback per ARCHITECTURE.md: only unambiguous tokens count.
        from . import abbreviations as ab
        tokens_seen = set(pattern.abbreviation_key.keys())
        for row in pattern.rows:
            for c in row.clauses:
                if c.stitch:
                    tokens_seen.add(c.stitch)
        if tokens_seen & ab.US_ONLY and not (tokens_seen & ab.UK_ONLY):
            pattern.declared_system = "US"
            pattern.declared_system_source = "heuristic"
        elif tokens_seen & ab.UK_ONLY and not (tokens_seen & ab.US_ONLY):
            pattern.declared_system = "UK"
            pattern.declared_system_source = "heuristic"

    return pattern
