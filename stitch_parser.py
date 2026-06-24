"""
Parses a single round/row's instruction text into stitch clauses.

Design: a round's text is split into (optional leading clauses) + (optional
repeat group, demarcated by *...* or [...]) + (optional trailing clauses),
plus a declared stitch count pulled off the end. Each clause is tokenized
into a StitchClause carrying how many stitches it consumes from the previous
round and how many it produces -- that's the raw material the stitch-count
checker does algebra on.

Known V1 scope limits (documented rather than silently guessed around):
- Only one repeat group per round/row is parsed; a second '*...*' block is
  recorded in unparsed_fragments with a warning rather than guessed at.
- Nested repeat groups aren't supported.
- Chain spaces that a pattern chooses to count toward its stitch total
  (e.g. granny-square 'ch-1 sp' counted as a stitch) are NOT counted here --
  chains are always treated as not counting toward the total, matching the
  more common convention. This can cause false positives on patterns that
  count chain spaces; flag and revisit if that comes up often.
"""

from __future__ import annotations
import re
from typing import Optional

from .abbreviations import STITCH_MATH, shape_for_term
from .models import StitchClause, RepeatGroup, RoundRow


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _clause_math(shape: str, multiplier: int = 1, cluster_size: Optional[int] = None,
                  force_zero_consumes: bool = False) -> tuple[int, int]:
    info = STITCH_MATH[shape]
    if not info.counts_toward_total:
        return 0, 0
    if cluster_size is not None:
        consumes = 0 if force_zero_consumes else info.consumes
        return consumes, info.produces * cluster_size
    consumes = 0 if force_zero_consumes else info.consumes * multiplier
    return consumes, info.produces * multiplier


_MAGIC_RING = re.compile(
    r"^(\d+)\s+([a-z0-9]+)\s+in(?:to)?\s+(?:the\s+)?(?:magic\s+ring|mr)$"
)
_CLUSTER_NEXT_SAME = re.compile(
    r"^(\d+)\s+([a-z0-9]+)\s+in\s+(?:the\s+)?(?:next|same)\s+st(?:itch)?$"
)
_SEQ_NEXT_N = re.compile(
    r"^([a-z0-9]+)\s+in\s+(?:the\s+)?next\s+(\d+)\s*(?:sts?|stitches)?$"
)
_SINGLE_NEXT_SAME = re.compile(
    r"^([a-z0-9]+)\s+in\s+(?:the\s+)?(?:next|same)\s+st(?:itch)?$"
)
_EACH_AROUND = re.compile(
    r"^([a-z0-9]+)\s+(?:in\s+each\s+st(?:itch)?(?:\s+around)?|around)$"
)
_SKIP_N = re.compile(r"^skip\s+(?:the\s+)?next\s+(\d+)\s*(?:sts?|stitches)?$")
_SKIP_ONE = re.compile(r"^skip\s+(?:the\s+)?next\s+st(?:itch)?$")
_CHAIN = re.compile(r"^ch\s*(\d+)$")
_LEADING_COUNT = re.compile(r"^(\d+)\s+([a-z0-9]+)$")
_BARE = re.compile(r"^([a-z0-9]+)$")


def parse_clause(raw: str, system: Optional[str]) -> Optional[StitchClause]:
    text = _norm(raw)
    if not text:
        return None

    if text.startswith("sl st") or text.startswith("slst"):
        return StitchClause(raw=raw, abbr="sl st", kind="stitch", multiplier=1,
                             consumes=0, produces=0)

    if m := _SKIP_N.match(text):
        n = int(m.group(1))
        return StitchClause(raw=raw, abbr="skip", kind="skip", multiplier=n,
                             consumes=n, produces=0)
    if _SKIP_ONE.match(text):
        return StitchClause(raw=raw, abbr="skip", kind="skip", multiplier=1,
                             consumes=1, produces=0)

    if m := _CHAIN.match(text):
        return StitchClause(raw=raw, abbr="ch", kind="stitch",
                             multiplier=int(m.group(1)), consumes=0, produces=0)

    if m := _MAGIC_RING.match(text):
        cluster_size, abbr = int(m.group(1)), m.group(2)
        shape = shape_for_term(abbr, system)
        if shape is None:
            return StitchClause(raw=raw, kind="unparsed")
        _, produces = _clause_math(shape, cluster_size=cluster_size)
        return StitchClause(raw=raw, abbr=abbr, kind="stitch",
                             cluster_size=cluster_size, consumes=0, produces=produces)

    if m := _CLUSTER_NEXT_SAME.match(text):
        cluster_size, abbr = int(m.group(1)), m.group(2)
        shape = shape_for_term(abbr, system)
        if shape is None:
            return StitchClause(raw=raw, kind="unparsed")
        c, p = _clause_math(shape, cluster_size=cluster_size)
        return StitchClause(raw=raw, abbr=abbr, kind="stitch",
                             cluster_size=cluster_size, consumes=c, produces=p)

    if m := _SEQ_NEXT_N.match(text):
        abbr, mult = m.group(1), int(m.group(2))
        shape = shape_for_term(abbr, system)
        if shape is None:
            return StitchClause(raw=raw, kind="unparsed")
        c, p = _clause_math(shape, multiplier=mult)
        return StitchClause(raw=raw, abbr=abbr, kind="stitch", multiplier=mult,
                             consumes=c, produces=p)

    if m := _SINGLE_NEXT_SAME.match(text):
        abbr = m.group(1)
        shape = shape_for_term(abbr, system)
        if shape is None:
            return StitchClause(raw=raw, kind="unparsed")
        c, p = _clause_math(shape, multiplier=1)
        return StitchClause(raw=raw, abbr=abbr, kind="stitch", multiplier=1,
                             consumes=c, produces=p)

    if m := _EACH_AROUND.match(text):
        abbr = m.group(1)
        shape = shape_for_term(abbr, system)
        if shape is None:
            return StitchClause(raw=raw, kind="unparsed")
        info = STITCH_MATH[shape]
        per_c = info.consumes if info.counts_toward_total else 0
        per_p = info.produces if info.counts_toward_total else 0
        return StitchClause(raw=raw, abbr=abbr, kind="each_around",
                             consumes=per_c, produces=per_p)

    if m := _LEADING_COUNT.match(text):
        mult, abbr = int(m.group(1)), m.group(2)
        shape = shape_for_term(abbr, system)
        if shape is None:
            return StitchClause(raw=raw, kind="unparsed")
        c, p = _clause_math(shape, multiplier=mult)
        return StitchClause(raw=raw, abbr=abbr, kind="stitch", multiplier=mult,
                             consumes=c, produces=p)

    if m := _BARE.match(text):
        abbr = m.group(1)
        shape = shape_for_term(abbr, system)
        if shape is None:
            return StitchClause(raw=raw, kind="unparsed")
        c, p = _clause_math(shape, multiplier=1)
        return StitchClause(raw=raw, abbr=abbr, kind="stitch", multiplier=1,
                             consumes=c, produces=p)

    return StitchClause(raw=raw, kind="unparsed")


def split_clauses(text: str) -> list[str]:
    return [c.strip() for c in re.split(r"[;,]", text) if c.strip()]


_TRAILING_COUNT = re.compile(r"[\(\[]\s*(\d+)\s*[a-zA-Z .]*[\)\]]\s*\.?\s*$")


def extract_declared_count(text: str) -> tuple[str, Optional[int]]:
    m = _TRAILING_COUNT.search(text.strip())
    if m:
        return text[: m.start()].rstrip(" ,."), int(m.group(1))
    return text, None


_REPEAT_COUNT_TIMES = re.compile(r"(\d+)\s*(?:more\s+)?times?\b", re.IGNORECASE)
_REPEAT_COUNT_X = re.compile(r"\bx\s*(\d+)\b", re.IGNORECASE)
_REPEAT_WORDING = re.compile(r"(?i)^[, ]*(repeat|rep)(\s+from\s*\*)?\s*", )


def _extract_repeat_group(text: str) -> tuple[str, Optional[RepeatGroup], str, list[str]]:
    """Returns (before, repeat_group_with_raw_content_only, after, warnings)."""
    warnings: list[str] = []
    m = re.search(r"\*(.+?)\*", text)
    if not m:
        m = re.search(r"\[(.+?)\]", text)
    if not m:
        return text, None, "", warnings

    content = m.group(1)
    before = text[: m.start()]
    after = text[m.end():]

    # second repeat marker present? not supported in v1 -- flag it.
    # ('repeat from *' itself contains an asterisk referring back to the
    # opening marker, not a second group, so strip that wording first)
    _check = re.sub(r"(?i)from\s*\*", "", after)
    if re.search(r"[\*\[]", _check):
        warnings.append(
            "Found a second repeat marker in this round/row; only the first "
            "repeat group is checked in this version."
        )

    count_match = _REPEAT_COUNT_TIMES.search(after) or _REPEAT_COUNT_X.search(after)
    repeat_count = None
    explicit = False
    if count_match:
        repeat_count = int(count_match.group(1))
        explicit = True
        after = after[: count_match.start()] + after[count_match.end():]

    after = _REPEAT_WORDING.sub("", after)
    after = re.sub(r"(?i)\baround\b", "", after)
    after = re.sub(r"(?i)\bto\s+end\b", "", after)
    after = re.sub(r"(?i)\bacross\b", "", after)

    rg = RepeatGroup(raw=content, repeat_count=repeat_count, repeat_count_is_explicit=explicit)
    return before, rg, after, warnings


def parse_round_body(body_text: str, system: Optional[str]) -> dict:
    """Parses one round/row's body text (label already stripped) into clauses."""
    text = body_text.strip()
    text, declared_count = extract_declared_count(text)
    before, rg, after, group_warnings = _extract_repeat_group(text)

    leading: list[StitchClause] = []
    repeat_groups: list[RepeatGroup] = []
    trailing: list[StitchClause] = []
    unparsed: list[str] = list(group_warnings)

    def collect(segment_text: str, target: list[StitchClause]):
        for c in split_clauses(segment_text):
            clause = parse_clause(c, system)
            if clause is None:
                continue
            if clause.kind == "unparsed":
                unparsed.append(clause.raw)
            target.append(clause)

    collect(before, leading)
    if rg is not None:
        for c in split_clauses(rg.raw):
            clause = parse_clause(c, system)
            if clause is None:
                continue
            if clause.kind == "unparsed":
                unparsed.append(clause.raw)
            rg.clauses.append(clause)
        repeat_groups.append(rg)
    collect(after, trailing)

    return {
        "leading_clauses": leading,
        "repeat_groups": repeat_groups,
        "trailing_clauses": trailing,
        "declared_count": declared_count,
        "unparsed_fragments": unparsed,
    }
