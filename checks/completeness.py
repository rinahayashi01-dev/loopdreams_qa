"""
Completeness checks: missing required materials fields, abbreviations used
in instructions but never defined in the abbreviation key, compound/
decorative stitches that ARE named in the key but whose actual construction
is never specified, gaps in row numbering, a missing final 'fasten off'
before the border, contradictory duplicate turning-chain instructions
within a single row, and a foundation row that's ambiguous about which
chain to start in.
"""
import re

from ..models import Issue
from .. import abbreviations as ab

REQUIRED_MATERIALS_FIELDS = ["gauge", "hook", "yarn"]

# Utility/structural clause types that are never themselves "abbreviations
# needing a definition" -- turn, join, fasten off, chains, etc.
_NON_STITCH_CLAUSE_TYPES = {
    "turn", "join", "note", "fasten_off", "chain", "repeat_close", "unknown", "skip",
}


def check(pattern) -> list:
    issues = []
    issues.extend(_check_required_fields(pattern))
    issues.extend(_check_abbreviations(pattern))
    issues.extend(_check_finishing_present(pattern))
    issues.extend(_check_row_gaps(pattern))
    issues.extend(_check_fasten_off(pattern))
    issues.extend(_check_duplicate_turn(pattern))
    issues.extend(_check_foundation_row_ambiguity(pattern))
    issues.extend(_check_non_stitch_rows(pattern))
    issues.extend(_check_missing_component_count(pattern))
    issues.extend(_check_stitch_guide_body_mismatch(pattern))
    issues.extend(_check_zipper_liner_section(pattern))
    return issues


def _check_required_fields(pattern) -> list:
    issues = []
    materials = next((s for s in pattern.sections if s.name == "materials"), None)
    if materials is None:
        issues.append(Issue(
            category="completeness", severity="error", location="Materials",
            message="No Materials section found -- gauge, yarn, and hook information are all missing.",
        ))
        return issues
    for field in REQUIRED_MATERIALS_FIELDS:
        if field not in materials.fields or not materials.fields[field].strip():
            issues.append(Issue(
                category="completeness", severity="error", location="Materials",
                message=f"Missing required materials field: '{field}'.",
            ))
    return issues


def _check_finishing_present(pattern) -> list:
    issues = []
    has_finishing = any(s.name == "finishing" for s in pattern.sections)
    if not has_finishing:
        issues.append(Issue(
            category="completeness", severity="error", location="Pattern",
            message="No Finishing/assembly section found.",
        ))
    return issues


def _collect_stitch_tokens(clauses, tokens):
    for c in clauses:
        if c.clause_type == "bracket_group":
            _collect_stitch_tokens(c.sub_clauses, tokens)
            continue
        if not c.stitch or c.clause_type in _NON_STITCH_CLAUSE_TYPES:
            continue
        if c.stitch.startswith("("):
            # paren-cluster like "(sc, hdc, dc)" -- check each component, not
            # the combined string, since the abbreviation key defines them
            # individually.
            for tok in c.stitch.strip("()").split(","):
                tokens.add(tok.strip())
        else:
            tokens.add(c.stitch)


def _check_abbreviations(pattern) -> list:
    issues = []
    stitch_tokens = set()
    for row in pattern.rows:
        _collect_stitch_tokens(row.clauses, stitch_tokens)

    abbr_key = pattern.abbreviation_key
    custom_compound = ab.custom_compound_tokens(abbr_key)
    seen_undefined_construction = set()

    for token in sorted(stitch_tokens):
        in_key = token in abbr_key
        is_compound = token in ab.COMPOUND_STITCH_WORDS or token == "sh st" or token in custom_compound

        if not in_key and token not in ab.ALL_KNOWN_TOKENS:
            issues.append(Issue(
                category="completeness", severity="error", location="Abbreviations",
                message=f"Abbreviation '{token}' is used in the pattern instructions but never defined "
                        f"in the abbreviation key.",
            ))
            continue

        if is_compound and token not in seen_undefined_construction:
            definition = abbr_key.get(token, "")
            has_numeric_construction = bool(re.search(r"\d", definition))
            if not has_numeric_construction:
                seen_undefined_construction.add(token)
                where = f"defined in the abbreviation key only as '{token} = {definition}'" if in_key else \
                        "not defined anywhere in the pattern"
                issues.append(Issue(
                    category="completeness", severity="error", location="Abbreviations",
                    message=(
                        f"'{token}' is a compound/decorative stitch ({where}) but its actual "
                        f"construction -- how many stitches it's made of and any stitches skipped "
                        f"between repeats -- is never specified. Without that, the stitch-count math "
                        f"for every row using '{token}' is unverifiable, and a tester cannot actually "
                        f"work the stitch from this pattern as written."
                    ),
                ))

    return issues


def _check_row_gaps(pattern) -> list:
    issues = []
    body_rows = sorted((r for r in pattern.rows if r.row_start > 0), key=lambda r: r.row_start)
    prev_end = 0  # row 0 == right after the foundation chain
    prev_label = "the foundation chain"
    for r in body_rows:
        if r.row_start > prev_end + 1:
            lo, hi = prev_end + 1, r.row_start - 1
            missing_desc = f"Row {lo}" if lo == hi else f"Rows {lo}-{hi}"
            issues.append(Issue(
                category="completeness", severity="error", location="Pattern Steps",
                message=(
                    f"No instructions are given for {missing_desc} -- the pattern jumps from "
                    f"{prev_label} directly to {r.label}."
                ),
            ))
        prev_end = max(prev_end, r.row_end)
        prev_label = f"Row {prev_end}"
    return issues


def _check_fasten_off(pattern) -> list:
    body_rows = [r for r in pattern.rows if r.row_start > 0]
    if not body_rows:
        return []
    has_fasten_off = any(c.clause_type == "fasten_off" for r in body_rows for c in r.clauses)
    if not has_fasten_off:
        has_border = any(r.row_start == -1 for r in pattern.rows)
        if has_border:
            msg = (
                "The pattern body never includes a 'fasten off' instruction before the border begins. "
                "Since the border instruction says to 'join yarn at any corner' (implying a fresh strand), "
                "the working yarn from the last body row should normally be fastened off first."
            )
        else:
            msg = (
                "The pattern body never includes a 'fasten off' instruction -- the last instruction row "
                "ends without one before the Finishing section begins. Recommend adding 'Fasten off.' "
                "to the final row so it's explicit when the crocheter should cut the yarn."
            )
        return [Issue(
            category="completeness", severity="warning", location="Pattern Steps",
            message=msg,
        )]
    return []


def _check_duplicate_turn(pattern) -> list:
    issues = []
    for r in pattern.rows:
        if r.row_start <= 0 or r.referenced_rows:
            continue
        n_turns = sum(1 for c in r.clauses if c.clause_type == "turn")
        if n_turns > 1:
            chain_texts = [c.raw for c in r.clauses if c.clause_type in ("chain", "counted_chain")]
            issues.append(Issue(
                category="completeness", severity="warning", location=r.label,
                message=(
                    f"{r.label} contains {n_turns} separate 'turn' instructions, each preceded by its own "
                    f"chain ({'; '.join(chain_texts)}) -- it's unclear which chain is the actual turning "
                    f"chain for this row. This looks like leftover template text from splicing in the "
                    f"colour-join instruction."
                ),
            ))
    return issues


def _check_foundation_row_ambiguity(pattern) -> list:
    first = next((r for r in pattern.rows if r.row_start == 1), None)
    if first is None:
        return []
    has_foundation_clause = any(c.clause_type == "foundation_into_chain" for c in first.clauses)
    each_st = next((c for c in first.clauses if c.clause_type in ("each_st_across", "each_st_around")), None)
    if each_st is not None and not has_foundation_clause:
        return [Issue(
            category="completeness", severity="warning", location=first.label,
            message=(
                f"{first.label} works '{each_st.stitch} in each st across' directly off the foundation chain "
                f"without stating which numbered chain to start in (e.g. '2nd ch from hook' for sc, '4th ch "
                f"from hook' for dc). Skipping some chains as a turning-chain equivalent is standard "
                f"convention, but the exact number depends on stitch height and isn't actually stated here."
            ),
        )]
    return []


_REAL_STITCH_CLAUSE_TYPES = {
    "literal_count", "each_st_across", "each_st_around", "corner", "side_edge_rule",
    "cluster_same_spot", "positional_single", "foundation_into_chain", "counted_chain",
    "skip", "bracket_group",
}


def _check_non_stitch_rows(pattern) -> list:
    """A row whose text contains zero recognizable stitch-instruction
    clauses (only chains/turns/unknowns) is a sign the 'row' isn't actually
    a stitch row at all -- e.g. assembly instructions or a separate
    component (handles, straps) that got numbered as if it were the next
    row of the main piece."""
    issues = []
    for r in pattern.rows:
        if r.row_start <= 0 or r.referenced_rows or not r.clauses:
            continue
        has_real_stitch_content = any(c.clause_type in _REAL_STITCH_CLAUSE_TYPES for c in r.clauses)
        has_unknown = any(c.clause_type == "unknown" for c in r.clauses)
        if not has_real_stitch_content and has_unknown:
            issues.append(Issue(
                category="completeness", severity="warning", location=r.label,
                message=(
                    f"{r.label} is numbered as a pattern row with a declared stitch count "
                    f"({r.declared_count} sts), but none of its text matches any recognizable stitch "
                    f"instruction -- it reads like non-stitch content (assembly steps, or a separate "
                    f"component) that's been numbered as if it were the next row of the main piece. "
                    f"Recommend giving this its own labeled section instead of a row number."
                ),
            ))
    return issues


def _check_missing_component_count(pattern) -> list:
    """A secondary component (handles, straps, etc.) that gives real stitch
    construction instructions but never states an expected stitch count
    leaves nothing for a tester to verify their own work against."""
    issues = []
    for r in pattern.rows:
        if r.row_start != -2 or r.declared_count is not None:
            continue
        has_real_stitch = any(c.clause_type in _REAL_STITCH_CLAUSE_TYPES for c in r.clauses)
        if has_real_stitch:
            issues.append(Issue(
                category="completeness", severity="warning", location=r.label,
                message=(
                    f"{r.label} gives real stitch construction instructions but never states an expected "
                    f"stitch count to check against (no '(N sts)'). Recommend adding one so a tester can "
                    f"confirm their piece is on track."
                ),
            ))
    return issues


def _check_stitch_guide_body_mismatch(pattern) -> list:
    """If the Stitch Guide section describes a named specialty stitch pattern
    (detected by the presence of 'Foundation:', 'Working row:', 'Stitch
    multiple:', or 'Turning chain:' inside the guide -- markers that a full
    row-by-row stitch technique is being described, not just decorative
    prose with no checkable claim) but none of the named stitch(es) in that
    guide actually appear in the body rows or abbreviation key, flag it as
    an error.

    This catches the case where the wrong stitch guide was attached to a
    generated pattern body: e.g. a Linen Stitch guide on a pure-DC body.
    The body's math may verify clean -- the guide mismatch is invisible to
    stitch-count checks -- so this is a dedicated completeness check.

    Detection strategy:
    - 'Complex' stitch guides are identified by any of: "foundation:",
      "working row", "stitch multiple" in the section text (case-insensitive).
      Simple technique guides ("Here's how to work a dc") do not contain these.
    - Named stitches in the guide are identified two ways:
      (a) Heading lines: "Name Stitch:" or "Name Stitch (abbr):" patterns
          at the start of lines, from which we extract name keywords and
          any parenthetical abbreviation.
      (b) Parenthetical abbreviations anywhere in the guide text: "(FPdc)",
          "(bo)", etc. -- these are the canonical abbreviation forms, and if
          any of them appears in the pattern's own body stitch tokens or
          abbreviation key, the guide is clearly being used.
    - If at least one named stitch from the guide is found in the body or
      abbreviation key, the check passes. Only if NONE match is an error
      raised, to avoid false positives from guides that describe multiple
      stitches (some of which may be contextual/teaching content rather than
      new stitch tokens to define).
    """
    import re

    sg = next((s for s in pattern.sections if s.name == "stitch_guide"), None)
    if not sg:
        return []

    raw = sg.raw_text

    # Only check guides that make a specific, checkable claim about which
    # stitch is being worked -- not pure decorative/history prose with
    # nothing to verify. "Turning chain:" is included alongside the
    # row-by-row markers because basic single-stitch technique guides
    # ("Double Crochet (dc): ... Turning chain: Ch 2, turn...") name a
    # specific stitch just as concretely as a named compound stitch does --
    # a guide teaching "how to work a dc" attached to a body that never
    # actually works a dc is exactly the same class of bug as a named
    # compound-stitch guide attached to the wrong body. This is safe against
    # false positives on genuinely-correct simple guides: their heading's
    # own words (e.g. "double crochet") are already mirrored in the
    # abbreviation key's own definition text ("dc = double crochet"), which
    # strategy (a) matches against, and the heading's "(dc)"-style
    # parenthetical is independently caught by strategy (b) -- both fire
    # before any of this ever reaches the stricter strategy (c).
    complex_markers = ["foundation:", "working row", "stitch multiple", "turning chain:"]
    is_complex = any(m in raw.lower() for m in complex_markers)
    if not is_complex:
        return []

    # Build the set of things that exist in the actual pattern body.
    # body_tokens: stitch tokens from every parsed clause.
    # abbr_corpus: every token in the abbreviation key PLUS every meaningful
    #   word in every abbreviation definition (so "bo = bobble ..." contributes
    #   "bobble" to the corpus, letting us match the guide's "Bobble Stitch:").
    body_tokens = set()
    for row in pattern.rows:
        for c in row.clauses:
            if c.stitch:
                body_tokens.add(c.stitch.lower())

    # "crochet" is as generically non-discriminating as "stitch" -- it
    # appears in every stitch's own abbreviation definition ("single
    # crochet", "double crochet", "half double crochet", ...), so without
    # excluding it, ANY "___ Crochet" heading would spuriously self-match
    # against the abbreviation corpus regardless of which specific stitch
    # is actually named (found while enabling "turning chain:" guides for
    # this check -- see ARCHITECTURE.md).
    skip_words = {
        "stitch", "crochet", "the", "a", "an", "and", "or", "in", "of", "to",
        "at", "from", "what", "is", "how", "per", "you", "your",
    }
    abbr_corpus = set(pattern.abbreviation_key.keys())
    for defn in pattern.abbreviation_key.values():
        for word in re.split(r"[\s\-\(\)/,]+", defn.lower()):
            if len(word) > 2 and word not in skip_words:
                abbr_corpus.add(word)

    combined = body_tokens | abbr_corpus

    # Literal words appearing anywhere in the pattern body's row text (not
    # just recognized stitch tokens/abbreviations). Needed because a guide's
    # named stitch is sometimes only ever spelled out in descriptive
    # annotations -- e.g. "5 dc in next st (shell made)", "sc in centre dc
    # of next shell" -- which the parser never tokenizes as a formal stitch
    # or abbreviation, but which a human reader would clearly recognize as
    # "yes, this row is working a shell."
    body_corpus = " ".join(row.raw_text.lower() for row in pattern.rows)
    body_words = set(re.findall(r"[a-z]+", body_corpus))

    # Strategy (b): check parenthetical abbreviations anywhere in the guide.
    paren_abbrs = re.findall(r"\(([A-Za-z][A-Za-z0-9]{0,10})\)", raw)
    for abbr in paren_abbrs:
        if abbr.lower() in body_tokens or abbr.lower() in pattern.abbreviation_key:
            return []  # guide abbreviation used in body -- guide is relevant

    # Strategy (a): extract heading lines and check their name keywords
    # against both formal tokens/abbreviations AND literal body words (see
    # body_words comment above -- a heading keyword like "shell" showing up
    # verbatim in the row text, even only inside a parenthetical annotation,
    # is enough to confirm the guide is in use).
    #
    # Structural/construction-label lines (the same labels complex_markers
    # checks for -- "Foundation:", "Working row:", "Stitch multiple:",
    # "Turning chain:") are NOT named-stitch headings and must be excluded
    # here, not just treated as ordinary headings that happen not to match.
    # "Turning chain:" in particular is a landmine if left in: its keyword
    # "chain" trivially self-matches the abbreviation corpus, since nearly
    # every real pattern defines "ch = chain" -- meaning ANY guide with a
    # "Turning chain:" line would spuriously "pass" via this heading alone,
    # regardless of whether the guide's actual named stitch is used anywhere
    # in the body. Found while enabling "turning chain:" as a complexity
    # marker (see ARCHITECTURE.md) -- without this exclusion, that change
    # would have silently defeated its own purpose.
    structural_labels = {m.rstrip(":") for m in complex_markers}
    heading_re = re.compile(
        r"^([A-Z][A-Za-z ]{1,40}?)(?:\s*\([^)]+\))?\s*:",
        re.M,
    )
    headings = [
        m.group(1).strip().lower() for m in heading_re.finditer(raw)
        if m.group(1).strip().lower() not in structural_labels
    ]

    for name in headings:
        name_keywords = {
            w for w in name.split()
            if w not in skip_words and len(w) > 2
        }
        if name_keywords & (combined | body_words):
            return []  # at least one keyword from this heading found in body/abbr

    # Strategy (c): construction-text overlap. Some patterns spell the named
    # stitch's construction out directly in the body (literal 'sc'/'ch'
    # clauses matching the guide's own Foundation:/Working row: text)
    # instead of using a named shorthand token or restating the stitch's
    # name anywhere -- strategies (a)/(b) can't see this, since neither a
    # matching word nor a matching abbreviation ever appears. Real case
    # found on a real sample (linen tote bag, Jul 1 second upload): the
    # guide's "Foundation: SC in 2nd ch from hook. *Ch 1, skip 1 ch, SC in
    # next ch..." is reproduced almost verbatim as the pattern's actual
    # Row 1/Row 2 text -- a genuine match that strategies (a)/(b) miss
    # because the body never writes the word "linen" and never defines a
    # shorthand abbreviation for it. Detected by extracting the first line
    # after each "Foundation:"/"Working row:" label in the guide and
    # checking whether most of its own meaningful words appear verbatim
    # somewhere in the pattern's body row text. A high overlap threshold
    # (70%) keeps this from matching on incidental shared crochet
    # vocabulary ("sc", "in", "next") alone.
    construction_re = re.compile(r"(?:foundation|working row)\s*:\s*(.+)", re.I)
    for line in raw.splitlines():
        m = construction_re.search(line)
        if not m:
            continue
        words = {
            w for w in re.findall(r"[a-z]+", m.group(1).lower())
            if len(w) > 2 and w not in skip_words
        }
        if not words:
            continue
        overlap = words & body_words
        if len(overlap) / len(words) >= 0.7:
            return []  # guide's own construction text is echoed in the body -- guide is in use

    # Nothing matched -- the stitch guide appears to describe a stitch that
    # the pattern body never actually uses. Report the primary heading name.
    if headings:
        display = headings[0].title()
    else:
        display = "(unnamed stitch)"

    return [Issue(
        category="completeness", severity="error",
        location="Stitch Guide",
        message=(
            f"The Stitch Guide describes a named stitch pattern ('{display}') with its own row-by-row "
            f"working instructions, but neither the body rows nor the abbreviation key uses or references "
            f"that stitch. The pattern body appears to be written for a completely different stitch than the "
            f"guide describes -- this looks like the wrong stitch guide was generated or attached for this "
            f"pattern variant."
        ),
    )]


def _check_zipper_liner_section(pattern) -> list:
    """A section whose own heading is "Adding a Zipper & Liner" (parsed as
    section name "zipper_liner", see pattern_parser.SECTION_HEADERS)
    explicitly promises BOTH a zipper and a liner. Real sample found (tote
    bag, Jul 5 batch): the section's body only ever gave liner instructions
    -- "zipper" appeared nowhere in it at all, meaning the section's own
    title is a promise the content never keeps. This is a hard completeness
    gap (a tester literally has no instructions for a step the pattern's
    own Materials list -- "Zipper & Liner: ..." -- and section heading both
    say is part of this bag), not a stitch-count or math issue."""
    zl = next((s for s in pattern.sections if s.name == "zipper_liner"), None)
    if not zl:
        return []

    body_lower = zl.raw_text.lower()
    has_zipper = "zipper" in body_lower
    has_liner = "liner" in body_lower or "lining" in body_lower
    missing = [name for name, present in (("zipper", has_zipper), ("liner", has_liner)) if not present]
    if not missing:
        return []

    present = [name for name in ("zipper", "liner") if name not in missing]
    coverage = "neither is actually covered" if not present else f"only {present[0]} content is present"
    return [Issue(
        category="completeness", severity="error",
        location="Adding a Zipper & Liner",
        message=(
            f"This section's own heading promises both a zipper and a liner, but the body never actually "
            f"gives {' or '.join(missing)} installation instructions -- {coverage}. A tester has no way to "
            f"complete the missing step(s) from this pattern as written."
        ),
    )]
