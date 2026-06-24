"""Turns raw extracted pattern text into a structured Pattern object."""

from __future__ import annotations
import re

from .models import Pattern, Section, RoundRow
from .stitch_parser import parse_round_body
from .abbreviations import UNAMBIGUOUS_US_ONLY, UNAMBIGUOUS_UK_ONLY

_SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)^(materials|yarn(?:\s*(?:and|&)\s*hook)?|supplies|you will need)\s*:?\s*$"), "materials"),
    (re.compile(r"(?i)^gauge\s*:?\s*$"), "gauge"),
    (re.compile(r"(?i)^(abbreviations?|stitch key|abbreviation key|special stitches|terms?(?:\s+used)?)\s*:?\s*$"), "abbreviations"),
    (re.compile(r"(?i)^(instructions?|pattern instructions?|directions?|pattern)\s*:?\s*$"), "instructions"),
    # LoopDreams app heading — may have trailing abbreviation legend, e.g. "PATTERN STEPS ch sl st sc"
    (re.compile(r"(?i)^pattern\s+steps?\b"), "instructions"),
    (re.compile(r"(?i)^(finishing(?:\s*(?:and|&)\s*assembly)?|assembly|join(?:ing)?(?:\s+pieces)?)\s*:?\s*$"), "finishing"),
]

# Matches "Round 3:", "Row 2.", "Rnd 4 -"  OR  LoopDreams short form "R3" / "R2–R73"
# Named groups keep extraction logic readable regardless of which branch matched.
_ROUND_LABEL = re.compile(
    r"(?im)"
    r"(?:"
    r"\b(?P<word_label>round|rnd|row)\.?\s*(?P<word_num>\d+)\s*[:.\-]"
    r"|"
    r"^R(?P<r_num>\d+)(?:[–\-]R?\d+)?\s+"  # R1 / R2–R73 / R74-R145 at start of line
    r")"
)

_ABBR_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9]{1,7})\s*[-=:\u2013]\s*(.+)$")


def _split_sections(full_text: str) -> dict[str, Section]:
    lines = full_text.splitlines()
    sections: dict[str, Section] = {}
    current_name = "preamble"
    current_lines: list[str] = []
    current_offset = 0
    offset = 0

    def flush():
        text = "\n".join(current_lines).strip()
        if text:
            if current_name in sections:
                sections[current_name].raw_text += "\n" + text
            else:
                sections[current_name] = Section(name=current_name, raw_text=text, char_offset=current_offset)

    for line in lines:
        stripped = line.strip()
        matched_name = None
        for pattern, name in _SECTION_PATTERNS:
            if pattern.match(stripped):
                matched_name = name
                break
        if matched_name:
            flush()
            current_name = matched_name
            current_lines = []
            current_offset = offset
        else:
            current_lines.append(line)
        offset += len(line) + 1
    flush()
    return sections


def _detect_declared_system(full_text: str, instructions_text: str) -> tuple[str | None, str]:
    explicit_us = re.search(r"(?i)\b(US|American)\s+(?:crochet\s+)?terms?\b", full_text)
    explicit_uk = re.search(r"(?i)\b(UK|British)\s+(?:crochet\s+)?terms?\b", full_text)
    if explicit_us and explicit_uk:
        return None, "conflicting"
    if explicit_us:
        return "US", "explicit"
    if explicit_uk:
        return "UK", "explicit"

    best_pos = None
    best_system = None
    for term in UNAMBIGUOUS_US_ONLY:
        m = re.search(rf"(?i)\b{re.escape(term)}\b", instructions_text)
        if m and (best_pos is None or m.start() < best_pos):
            best_pos, best_system = m.start(), "US"
    for term in UNAMBIGUOUS_UK_ONLY:
        m = re.search(rf"(?i)\b{re.escape(term)}\b", instructions_text)
        if m and (best_pos is None or m.start() < best_pos):
            best_pos, best_system = m.start(), "UK"

    if best_system:
        return best_system, "inferred"
    return None, "none"


def _parse_abbreviation_key(section_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in section_text.splitlines():
        for chunk in raw_line.split(","):
            chunk = chunk.strip()
            m = _ABBR_LINE.match(chunk)
            if m:
                abbr, definition = m.group(1).strip().lower(), m.group(2).strip()
                if len(definition) > 1:
                    result[abbr] = definition
    return result


def _parse_rounds(instructions_text: str, declared_system: str | None) -> tuple[list[RoundRow], list[str]]:
    rounds: list[RoundRow] = []
    warnings: list[str] = []
    matches = list(_ROUND_LABEL.finditer(instructions_text))
    if not matches:
        return rounds, warnings

    for i, m in enumerate(matches):
        if m.group("word_label"):
            label = m.group("word_label").capitalize()
            if label.lower() == "rnd":
                label = "Round"
            number = int(m.group("word_num"))
        else:
            label = "Row"
            number = int(m.group("r_num"))
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(instructions_text)
        body = instructions_text[body_start:body_end].strip()

        parsed = parse_round_body(body, declared_system)
        rounds.append(RoundRow(
            label=label,
            number=number,
            raw_text=body,
            leading_clauses=parsed["leading_clauses"],
            repeat_groups=parsed["repeat_groups"],
            trailing_clauses=parsed["trailing_clauses"],
            declared_count=parsed["declared_count"],
            unparsed_fragments=parsed["unparsed_fragments"],
            char_offset=m.start(),
        ))
    return rounds, warnings


def build_pattern(source_path: str, full_text: str) -> Pattern:
    sections = _split_sections(full_text)
    instructions_text = sections.get("instructions", Section("instructions", full_text)).raw_text
    declared_system, source = _detect_declared_system(full_text, instructions_text)
    rounds, warnings = _parse_rounds(instructions_text, declared_system)

    declared_abbrevs: dict[str, str] = {}
    if "abbreviations" in sections:
        declared_abbrevs = _parse_abbreviation_key(sections["abbreviations"].raw_text)

    return Pattern(
        source_path=source_path,
        full_text=full_text,
        sections=sections,
        rounds=rounds,
        declared_abbreviations=declared_abbrevs,
        declared_system=declared_system,
        declared_system_source=source,
        extraction_warnings=warnings,
    )
