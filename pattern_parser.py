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
    # Real sample (sweater, Jul 12 batch): a multi-panel garment's
    # finishing content is headed "ASSEMBLY" (seaming instructions for the
    # separate panels) rather than "Finishing" -- same role, different
    # word. A later "NECKLINE" sub-heading isn't its own SECTION_HEADERS
    # entry and doesn't need to be: it just stays part of this same
    # "finishing" section's raw text, which is harmless since nothing
    # currently depends on isolating it further.
    "assembly": "finishing",
    "notes": "notes",
    "confidence summary": "ignored_meta",  # LoopDreams' own auto-QA output -- not pattern content
    # Real sample found (tote bag, Jul 5 batch): "TESTER EXPECTATIONS" is a
    # different heading than the "TESTER FEEDBACK" seen on the Jul 4 tote
    # bag, but the same kind of content -- a request for the human tester's
    # own notes back to the designer, not pattern content to check.
    "tester feedback": "ignored_meta",
    "tester expectations": "ignored_meta",
    # Real sample found (tote bag, Jul 5 batch): without its own recognized
    # heading, this section's construction instructions (and everything
    # after them, including the tester-notes section above) got silently
    # absorbed into "finishing"'s raw_text, which broke the Handles
    # component's own "(N sts)" extraction (that regex anchors to the end
    # of the whole blob to find the trailing count -- with unrelated
    # trailing content glued on, the real count was no longer at the end).
    # See _check_zipper_liner_section in completeness.py for what's
    # actually verified about this section's own content.
    "adding a zipper & liner": "zipper_liner",
    # Real sample (Tote Bag, Jul 10 "Pattern Test v1" cover-page template):
    # a new template replaces the "Materials" heading entirely with two
    # separate headings -- "Pattern Overview" (gauge/colours/finished-size,
    # still "Label: value" fields) and "You Will Need" (a plain bullet
    # list of yarn/hook/notions, no labels at all). "Pattern Overview" maps
    # straight to "materials"; "You Will Need" gets its own section name
    # ("supplies_list") since its unlabeled bullet-list shape needs a
    # different parsing strategy -- see parse()'s merge step below, which
    # folds any yarn/hook mentions found there into the "materials"
    # section's fields.
    "pattern overview": "materials",
    "you will need": "supplies_list",
}


def _match_section_header(line: str):
    """Return the mapped section name for a header line, or None.

    Real sample (Sweater, Jul 12 batch, OCR'd from a text-free/vector-only
    PDF): each section heading has a small decorative icon glyph in front
    of it in the original design, which OCR misreads as a short garbage
    token instead of dropping it cleanly ("@ pattern overview", "wt
    abbreviations", "¢ pattern steps"). An exact-match lookup misses
    all of these. Try the exact line first, then fall back to stripping a
    single short (<=4 char) leading token and checking whether the
    remainder is an exact known header -- narrow enough that it can't
    accidentally match arbitrary unrelated content, since everything after
    the stripped token must still be a full, exact header phrase.
    """
    key = line.strip().lower()
    if key in SECTION_HEADERS:
        return SECTION_HEADERS[key]
    m = re.match(r"^\S{1,4}\s+(.*)$", key)
    if m and m.group(1) in SECTION_HEADERS:
        return SECTION_HEADERS[m.group(1)]
    return None

_RE_PAGE_HEADER = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*[AP]M\b.*$")
_RE_PAGE_FOOTER = re.compile(r"^https?://\S+\s+\d+/\d+$")
# Real sample (Tote Bag, Jul 10 "Pattern Test v1" cover-page template): a
# different footer style entirely -- a copyright/branding line, with the
# page number on its OWN separate following line ("© 2026 LoopDreams
# Studio Pattern Test v1" / "Page 4"), not a single combined line like the
# URL-based footer. Left unstripped, this glued itself onto whatever
# content immediately preceded it (here, the Handles component's own
# "(N sts)"), breaking the trailing-count regex anchor the same way an
# unstripped URL footer would have.
_RE_PAGE_FOOTER_COPYRIGHT = re.compile(r"^©\s*\d{4}\b.*$", re.I)
_RE_PAGE_FOOTER_PAGE_NUM = re.compile(r"^Page\s+\d+$", re.I)

_RE_FIELD_LINE = re.compile(r"^[A-Za-z][A-Za-z /]{1,24}:\s*\S")
# Real sample (sweater, Jul 12 batch, OCR'd from a text-free/vector-only
# PDF): the space between "Row" and a single-digit number is inconsistently
# dropped by OCR ("Row1", "Row3", "Row9" alongside a normally-spaced "Row
# 2", "Row 10") -- \s* (was \s+) tolerates both.
_RE_ROW_MARKER = re.compile(r"^Rows?\s*\d+", re.I)
# Colon after "Foundation" optional too -- same badge-label convention as
# Row N above (real sample: sweater, Jul 12 batch -- "Foundation Ch 87."
# with no colon at all).
_RE_FOUNDATION_MARKER = re.compile(r"^Foundation(?:\s+chain)?\s*:?", re.I)
_RE_BORDER_MARKER = re.compile(r"^Border\s*:", re.I)
# A standalone ALL-CAPS heading inside Pattern Steps marking one of several
# independently-numbered pieces in the same pattern (real sample: sweater,
# Jul 12 batch -- "BACK PANEL", "FRONT PANEL", "SLEEVES (MAKE 2)", each
# restarting its own "Row 1"). Every prior pattern had exactly one piece, so
# this line shape never needed to be distinguished from ordinary content
# before. Requires the whole line to be uppercase letters/digits/spaces/
# parens/&/apostrophe so it can't accidentally match real row/instruction
# text, which is always title- or sentence-case in every sample seen.
_RE_COMPONENT_HEADER = re.compile(r"^[A-Z][A-Z0-9 ()&'-]{2,40}$")


def _split_component_chunks(raw_text: str):
    """Split an instructions section's raw text into (component_name, text)
    chunks at each ALL-CAPS component heading. component_name is None for
    any text before the first heading (the common single-piece case, where
    there may be no heading at all -- that whole section becomes one chunk
    with component_name=None, identical to the pre-multi-piece behavior)."""
    chunks = []
    current_name = None
    current_lines = []
    for ln in raw_text.split("\n"):
        if _RE_COMPONENT_HEADER.match(ln.strip()):
            if current_lines:
                chunks.append((current_name, "\n".join(current_lines)))
            current_name = ln.strip()
            current_lines = []
        else:
            current_lines.append(ln)
    if current_lines:
        chunks.append((current_name, "\n".join(current_lines)))
    return chunks


def _strip_noise_lines(raw_text: str) -> list:
    lines = raw_text.split("\n")
    keep = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if (
            _RE_PAGE_HEADER.match(s)
            or _RE_PAGE_FOOTER.match(s)
            or _RE_PAGE_FOOTER_COPYRIGHT.match(s)
            or _RE_PAGE_FOOTER_PAGE_NUM.match(s)
        ):
            continue
        keep.append(s)
    return keep


def _split_into_sections(lines: list) -> list:
    """Split cleaned lines into raw Section objects by header lines."""
    sections = []
    current_name = "preamble"
    current_lines = []
    for ln in lines:
        mapped = _match_section_header(ln)
        if mapped is not None:
            if current_lines:
                sections.append(Section(name=current_name, raw_text="\n".join(current_lines)))
            current_name = mapped
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


def _parse_supplies_list(section: Section) -> dict:
    """A "You Will Need" bullet list (Tote Bag, Jul 10 "Pattern Test v1"
    template): plain prose lines with no "Label: value" structure at all
    ("4.0 mm (G-6 US) crochet hook", "#3 Light (DK) yarn -- approx 400
    yds"), unlike the labeled Materials/Pattern Overview block. Scan for a
    yarn and a hook mention specifically, since those are the two required
    fields a plain bullet list is standing in for here.
    """
    fields = {}
    for ln in section.raw_text.split("\n"):
        s = ln.strip()
        low = s.lower()
        if not s:
            continue
        if "yarn" not in fields and "yarn" in low and low != "yarn needle":
            fields["yarn"] = s
        if "hook" not in fields and "hook" in low:
            fields["hook"] = s
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
    """Split into per-component chunks (real sample: sweater, Jul 12 batch --
    Back Panel/Front Panel/Sleeves are each independently row-numbered) and
    parse each with the same logic as before, tagging results with which
    component they belong to. component=None (the single-piece case) covers
    every pattern before that batch and behaves exactly as it did previously."""
    from . import abbreviations as ab
    custom_compound = ab.custom_compound_tokens(pattern.abbreviation_key)

    for component, chunk_text in _split_component_chunks(section.raw_text):
        _parse_instructions_chunk(chunk_text, pattern, custom_compound, component)


# "Row 1 Sleeves (make 2): Ch 35. (32 sts)" -- real sample (sweater, Jul 12
# batch): a component whose OWN foundation chain is declared as its "Row 1"
# rather than a separate "Foundation:" line, with no real stitch
# construction of its own (the actual first worked row is "Row 2"). Treated
# as a no-op declaration row (establishes this component's foundation count
# directly from its own declared "(N sts)", which is already the post-
# turning-chain count) rather than a real stitch row to verify.
_RE_ROW_AS_FOUNDATION = re.compile(
    r"Row\s*(\d+)\.?\s+[A-Za-z][\w\s]*?\(make\s+\d+\)\s*:\s*Ch\s+(\d+)\.?\s*\(\s*~?\s*(\d+)\s*sts?\s*\)\.?",
    re.I,
)


def _parse_instructions_chunk(raw_text: str, pattern: Pattern, custom_compound, component):
    boundaries = [_RE_FOUNDATION_MARKER, _RE_ROW_MARKER]
    joined = _join_wrapped(raw_text, boundaries)
    blob = re.sub(r"\s+", " ", joined.replace("\n", " ")).strip()

    def _set_foundation(chain, is_magic_ring):
        if component is None:
            pattern.foundation_chain = chain
            pattern.foundation_is_magic_ring = is_magic_ring
        else:
            pattern.component_foundations[component] = (chain, is_magic_ring)

    found_rows = []

    fm = _RE_ROW_AS_FOUNDATION.search(blob)
    if fm:
        row_start = int(fm.group(1))
        raw_chain = int(fm.group(2))
        declared = int(fm.group(3))
        _set_foundation(raw_chain, False)
        rr = RoundRow(label=f"Row {row_start}", row_start=row_start, row_end=row_start,
                      raw_text=fm.group(0), declared_count=declared, component=component)
        rr.clauses = tokenize_round("ch " + str(raw_chain))  # a bare chain -- no-op for stitch-count purposes
        found_rows.append(rr)
        blob = blob[: fm.start()] + blob[fm.end():]

    # Optional leading colour clause before the chain count -- real sample
    # found (dishcloth, Jul 8 batch): "Foundation chain:With Colour 1 --
    # Honey, Ch 48, turn." (previously only "Foundation chain:Ch 48, turn."
    # -- no colour prefix -- was recognized). Colon after "Foundation"
    # itself now optional too -- real sample (sweater, Jul 12 batch):
    # "Foundation Ch 87." is a badge-label heading with no colon at all,
    # same convention as the colonless "Row N" badges.
    m = re.search(
        r"Foundation(?:\s+chain)?\s*:?\s*(?:With\s+Colour\s+[A-Za-z0-9]+\s*[—-]\s*[A-Za-z]+\s*,\s*)?Ch\s+(\d+)",
        blob, re.I,
    )
    if m:
        _set_foundation(int(m.group(1)), False)
    elif not fm:
        # "With Colour 1 -- Honey, magic ring. 30 sc in ring." -- a
        # continuous-spiral/amigurumi-style foundation with no chain at
        # all. Real sample found (mittens, Jul 7 batch): pattern.foundation_
        # chain is used throughout the codebase as "the starting stitch
        # count for row 1", not literally "number of chains", so this is a
        # semantically consistent alternate way to establish the same
        # field.
        m = re.search(r"magic\s+ring\.?\s*(\d+)\s*sc\s+in\s+ring", blob, re.I)
        if m:
            _set_foundation(int(m.group(1)), True)
        else:
            # "Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st
            # to top of ch 3 to join." -- a JOINED-round (flat circle/motif)
            # magic-ring foundation, real sample found (coaster, Jul 8
            # batch): distinct from the mittens continuous-spiral form
            # above (no counted turning chain there). The counted chain
            # always represents exactly 1 stitch, regardless of how many
            # actual chains form it -- total = 1 + the "N <stitch> in ring"
            # count.
            m = re.search(
                r"magic\s+ring\.?\s*ch\s+\d+\s*\(counts\s+as\s+first\s+[a-z]+\)\s*,\s*(\d+)\s+[a-z]+\s+in\s+ring",
                blob, re.I,
            )
            if m:
                _set_foundation(int(m.group(1)) + 1, True)

    # Colour identifier broadened to alphanumeric (was letter-only) and the
    # separator to accept a comma as well as a colon -- real sample found
    # (dishcloth, Jul 8 batch): "With Colour 2 -- Moss, 45 DC in next 45
    # sts." (a numbered identifier, comma-separated, instead of the
    # previously-seen lettered/colon-separated "With Colour B -- Moss:").
    # The colon after the row number itself is now OPTIONAL -- real sample
    # (sweater, Jul 12 batch): "Row N" is a visual badge label in the
    # source design with no literal colon at all ("Row 2 DC in each st
    # across..."), unlike every earlier pattern's "Row 2: DC in...".
    # The instr_text lookahead used to only stop at the NEXT "Row N" when it
    # was followed by a colon/dash -- fine while every row had one, but with
    # the colon now optional (see above), that lookahead never fired at all
    # for a colonless "Row N" boundary, so one match's capture ran on
    # through every subsequent row until it hit the next "(N sts)" it could
    # find, silently swallowing whole rows into one giant clause blob. Now
    # stops at ANY "Row N" occurrence, regardless of trailing punctuation.
    # Uses (?!\d) rather than \b after the digits -- \b doesn't fire between
    # a digit and an underscore (both are \w), and a real sample (sweater,
    # Jul 12 batch) has OCR noise gluing a stray "_" onto a row number
    # ("Row 8_ Increase row:..."), which silently defeated the \b version
    # of this same boundary check.
    row_re = re.compile(
        r"Rows?\s*(\d+)(?:\s*[–-]\s*(\d+))?\s*:?\s*"
        r"(?:With\s+Colour\s+([A-Za-z0-9]+)\s*[—-]\s*([A-Za-z]+)\s*[:,]\s*)?"
        r"((?:(?!Rows?\s*\d+(?!\d)).)*)"
        r"\(\s*~?\s*(\d+)\s*sts?\s*\)\.?",
        re.I,
    )
    for m in row_re.finditer(blob):
        row_start = int(m.group(1))
        row_end = int(m.group(2)) if m.group(2) else row_start
        color = m.group(4)
        instr_text = m.group(5).strip().rstrip(".")
        # Real samples found (mittens Jul 7, shawl/dishcloth/coaster Jul 8):
        # rows sometimes restate the count twice, either with the same unit
        # ("...(5 sts) (5 sts)", shawl), a different one ("...(30 sc)
        # (30 sts)", mittens), or a different stitch abbreviation entirely
        # ("...(24 dc) (24 sts)", coaster). The greedy capture above
        # correctly anchors on the LAST "(N sts)" as the real declared
        # count (same reasoning as the Jun 28 duplicated-(N sts) fix), but
        # leaves any earlier duplicate annotation embedded in instr_text as
        # noise. Strip any number of trailing "(N <stitch abbr>)"/"(N sts)"
        # annotations here, rather than touching the greedy capture itself.
        while True:
            stripped = re.sub(
                r"\s*\(\s*~?\s*\d+\s*(?:sc|hdc|dc|tr|dtr|htr|ttr|sts?)\s*\)\s*\.?\s*$", "", instr_text
            ).strip()
            if stripped == instr_text:
                break
            instr_text = stripped
        declared = int(m.group(6))
        label = f"Row {row_start}" if row_start == row_end else f"Rows {row_start}-{row_end}"
        rr = RoundRow(label=label, row_start=row_start, row_end=row_end,
                      raw_text=instr_text, color=color, declared_count=declared, component=component)
        rr.clauses = tokenize_round(instr_text, custom_compound)
        found_rows.append(rr)

    # "Rows N-M: [With Colour X -- Name:] Repeat Row(s) P[-Q]." -- a bare
    # back-reference to earlier row text, with no stitch count restated.
    # These never match row_re above (no trailing "(N sts)"), so they need
    # their own pass or they'd silently vanish from the parsed pattern.
    # Colon after the row number optional -- see row_re above.
    repeat_ref_re = re.compile(
        r"Rows?\s*(\d+)(?:\s*[–-]\s*(\d+))?\s*:?\s*"
        r"(?:With\s+Colour\s+([A-Za-z0-9]+)\s*[—-]\s*([A-Za-z]+)\s*[:,]\s*)?"
        r"Repeat\s+Rows?\s*(\d+)(?:\s*[–-]\s*(\d+))?\.?",
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
                      referenced_rows=referenced, component=component)
        found_rows.append(rr)

    # "Repeat Rows P[-Q] x N more times." -- a standalone repeat instruction
    # with NO leading "Rows A-B:" label at all (unlike repeat_ref_re above,
    # which requires one). Real phrasing found on a real sample (tote bag,
    # Jul 4 batch): "Repeat Rows 2-3 x 38 more times." following explicit
    # Row 2/Row 3 entries, with Row 80 appearing next. Since there's no
    # explicit target row-range in the text itself, it has to be inferred:
    # anchored immediately after the LAST already-parsed occurrence of the
    # referenced range's own last row (e.g. Row 3), spanning N more full
    # repeats of the P-Q cycle. Without this pass, this phrase is invisible
    # to found_rows entirely, and the checker sees a hard gap between the
    # last explicit row and the next explicit row after it.
    repeat_n_more_re = re.compile(
        r"Repeat\s+Rows?\s*(\d+)(?:\s*[–-]\s*(\d+))?\s*(?:x|×)\s*(\d+)\s+more\s+times?\.?",
        re.I,
    )
    for m in repeat_n_more_re.finditer(blob):
        ref_start = int(m.group(1))
        ref_end = int(m.group(2)) if m.group(2) else ref_start
        n_more = int(m.group(3))
        cycle_len = ref_end - ref_start + 1
        anchor = max((r.row_end for r in found_rows if r.row_end == ref_end), default=None)
        if anchor is None:
            continue  # can't anchor to a known occurrence -- leave unrecognized rather than guess
        new_start = anchor + 1
        new_end = anchor + n_more * cycle_len
        referenced = list(range(ref_start, ref_end + 1))
        label = f"Row {new_start}" if new_start == new_end else f"Rows {new_start}-{new_end}"
        rr = RoundRow(label=label, row_start=new_start, row_end=new_end,
                      raw_text=f"[repeats Row(s) {ref_start}-{ref_end}, {n_more} more time(s)]",
                      referenced_rows=referenced, component=component)
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
        # Real sample (sweater, Jul 12 batch): an assembly-diagram caption
        # ("Sleeve (make 2): worked cuff-up, increasing evenly from 8 in to
        # 15 in wide over 17 in.") matches this same "<Label> (make N):"
        # shape, but it's describing a picture, not giving new
        # construction -- the sleeve's real row-by-row instructions already
        # exist as their own "SLEEVES (MAKE 2)" component elsewhere in
        # Pattern Steps. Skip if a same-piece component (matched loosely,
        # ignoring case and singular/plural) is already present, so this
        # caption doesn't get parsed as if it were a second, undefined
        # construction full of unrecognized prose.
        existing_components = {(r.component or "").lower() for r in pattern.rows if r.component}
        label_singular = label.lower().rstrip("s")
        if any(label_singular in c for c in existing_components):
            return
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


_RE_TITLE_METADATA_LINE = re.compile(
    r"^.+\s*[-·]\s*(Beginner|Intermediate|Advanced|Easy)\s*[-·]\s*[A-Za-z]+\s+\d{1,2},\s*\d{4}$", re.I
)


def parse(raw_text: str) -> Pattern:
    lines = _strip_noise_lines(raw_text)
    pattern = Pattern(raw_text=raw_text)

    # Title heuristic: first non-empty line before MATERIALS that isn't the
    # secondary metadata line ("Scarf · Intermediate · June 26, 2026").
    # Real sample (Sweater, Jul 12 batch, OCR'd from a text-free/vector-only
    # PDF): a decorative cover-page logo graphic OCRs into several lines of
    # garbage BEFORE the real title line, so "first non-empty line" grabs
    # the garbage instead. The metadata line's format ("<Title> - <Level> -
    # <Month> <Day>, <Year>") is a stable, distinctive convention seen
    # across every batch -- find it and use the line immediately before it
    # as the title, falling back to the old first-line heuristic if no
    # such metadata line is present (keeps prior samples working exactly
    # as before).
    metadata_idx = next((i for i, ln in enumerate(lines) if _RE_TITLE_METADATA_LINE.match(ln.strip())), None)
    if metadata_idx is not None and metadata_idx > 0:
        pattern.title = lines[metadata_idx - 1].strip()
    else:
        for ln in lines:
            if _match_section_header(ln) is not None:
                break
            if pattern.title is None:
                pattern.title = ln.strip()

    raw_sections = _split_into_sections(lines)
    pattern.sections = raw_sections

    for section in raw_sections:
        if section.name == "materials":
            section.fields = _parse_materials(section)
        elif section.name == "supplies_list":
            section.fields = _parse_supplies_list(section)
        elif section.name == "abbreviations":
            pattern.abbreviation_key = _parse_abbreviations(section)
        elif section.name == "instructions":
            _parse_instructions(section, pattern)
        elif section.name == "finishing":
            _parse_finishing(section, pattern)

    # A "You Will Need" supplies list stands in for the yarn/hook fields a
    # labeled Materials block would normally give -- fold whatever it found
    # into the materials section so the required-fields check sees them,
    # without ever overriding a field the labeled block already gave.
    supplies_section = next((s for s in raw_sections if s.name == "supplies_list"), None)
    materials_section = next((s for s in raw_sections if s.name == "materials"), None)
    if supplies_section and materials_section:
        for field, value in supplies_section.fields.items():
            materials_section.fields.setdefault(field, value)

    # Declared system: prefer an explicit "Terminology:" field over heuristic.
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
