"""Core data model shared across extraction, parsing, and checks."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StitchClause:
    """One parsed clause from a round/row, e.g. 'sc in next 3' or '2 sc in next st'."""
    raw: str
    abbr: Optional[str] = None        # canonical abbreviation as written, e.g. "sc", "inc"
    kind: str = "stitch"              # "stitch" | "skip" | "each_around" | "unparsed"
    multiplier: int = 1                # how many stitches this clause works (sequentially)
    cluster_size: Optional[int] = None  # set when N stitches go into ONE target st, e.g. "3 sc in next st"
    consumes: int = 0
    produces: int = 0


@dataclass
class RepeatGroup:
    """A '*...* repeat from * N times' (or 'around') block."""
    raw: str
    clauses: list[StitchClause] = field(default_factory=list)
    repeat_count: Optional[int] = None   # explicit count from the text, if stated
    repeat_count_is_explicit: bool = False


@dataclass
class RoundRow:
    label: str                 # "Round" or "Row"
    number: int
    raw_text: str
    leading_clauses: list[StitchClause] = field(default_factory=list)   # before any repeat group
    repeat_groups: list[RepeatGroup] = field(default_factory=list)
    trailing_clauses: list[StitchClause] = field(default_factory=list)  # after repeat group(s)
    declared_count: Optional[int] = None   # the (12) / [18 sts] annotation, if present
    unparsed_fragments: list[str] = field(default_factory=list)
    char_offset: int = 0

    def label_str(self) -> str:
        return f"{self.label} {self.number}"


@dataclass
class Section:
    name: str            # "materials" | "gauge" | "abbreviations" | "instructions" | "finishing"
    raw_text: str
    char_offset: int = 0


@dataclass
class Pattern:
    source_path: str
    full_text: str
    sections: dict[str, Section] = field(default_factory=dict)
    rounds: list[RoundRow] = field(default_factory=list)
    declared_abbreviations: dict[str, str] = field(default_factory=dict)  # abbr -> definition text
    declared_system: Optional[str] = None     # "US" | "UK" | None
    declared_system_source: str = "none"      # "explicit" | "inferred" | "none"
    extraction_warnings: list[str] = field(default_factory=list)


@dataclass
class Issue:
    """A single flagged problem, ready to drop into a report."""
    check: str          # "stitch_count" | "terminology" | "completeness"
    severity: str       # "error" | "warning" | "info"
    location: str        # human-readable location, e.g. "Round 7"
    message: str
