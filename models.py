from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StitchClause:
    raw: str
    stitch: Optional[str] = None          # normalized token, e.g. "sc", "sh st", None if unrecognized
    clause_type: str = "unknown"          # literal_count | each_st_across | each_st_around | inc | dec |
                                           # skip | chain | counted_chain | turn | join | note |
                                           # corner | side_edge_rule | cluster_same_spot |
                                           # positional_single | foundation_into_chain |
                                           # bracket_group | repeat_close | unknown
    explicit_count: Optional[int] = None  # explicit number stated, e.g. "sc in next 3" -> 3
    consumes: Optional[int] = None
    produces: Optional[int] = None
    is_compound: bool = False
    unverifiable_reason: Optional[str] = None
    sub_clauses: list = field(default_factory=list)   # for clause_type == "bracket_group"


@dataclass
class RoundRow:
    label: str                  # "Row 1", "Rows 1-198", "Round 4", "Border"
    row_start: int
    row_end: int
    raw_text: str
    color: Optional[str] = None
    clauses: list = field(default_factory=list)
    declared_count: Optional[int] = None
    declared_count_is_approx: bool = False
    referenced_rows: list = field(default_factory=list)   # e.g. [2, 3] for "Repeat Rows 2-3"
    # Which independently-numbered piece this row belongs to (e.g. "BACK
    # PANEL", "SLEEVES (MAKE 2)"), None for single-piece patterns (every
    # pattern before the Jul 12 sweater batch). Real sample: a sweater made
    # of 4 separate row-by-row pieces (Back, Front, 2x Sleeves), each
    # restarting its own numbering at Row 1 -- row_start alone is no longer
    # globally unique within a pattern, so checks that walk pattern.rows in
    # row-number order must group by component first.
    component: Optional[str] = None


@dataclass
class Section:
    name: str
    raw_text: str
    fields: dict = field(default_factory=dict)


@dataclass
class Pattern:
    title: Optional[str] = None
    raw_text: str = ""
    sections: list = field(default_factory=list)
    abbreviation_key: dict = field(default_factory=dict)   # lower(abbr) -> definition text
    declared_system: Optional[str] = None                  # "US" | "UK" | None
    declared_system_source: Optional[str] = None            # "explicit_field" | "heuristic" | None
    foundation_chain: Optional[int] = None
    foundation_is_magic_ring: bool = False  # True when foundation_chain came from "magic ring. N sc in ring"
                                             # rather than "Ch N" -- no turning-chain-skip ambiguity applies
    rows: list = field(default_factory=list)                # list[RoundRow]
    # Per-component foundation info for multi-piece patterns (real sample:
    # sweater, Jul 12 batch -- Back Panel, Front Panel, and Sleeves each
    # have their OWN "Foundation Ch N" line). Keyed by RoundRow.component
    # (None for the single-piece case, mirroring foundation_chain/
    # foundation_is_magic_ring above exactly). Value is (chain_count,
    # is_magic_ring).
    component_foundations: dict = field(default_factory=dict)


@dataclass
class Issue:
    category: str     # "stitch_count" | "terminology" | "completeness"
    severity: str      # "error" | "warning" | "info"
    location: str
    message: str

    def to_dict(self):
        return {
            "category": self.category,
            "severity": self.severity,
            "location": self.location,
            "message": self.message,
        }
