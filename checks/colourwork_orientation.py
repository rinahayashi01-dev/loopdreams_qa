"""Does the crocheted fabric actually show the design the user chose?

Every other check in this package reads pattern TEXT alone. This one is the
exception: it needs the design grid the pattern was generated FROM, so it can
compare intent against instructions. That comparison is the one nothing could
make before -- and its absence is exactly how two orientation bugs shipped:

  loopdreams #474 -- the grid was fed to every flat builder in STORED order.
    grid[0] is the top of the image but the first row crocheted is the BOTTOM
    of the piece, so the picture came out upside down; and flat rows are turned,
    so consecutive rows travel in opposite directions and every other row came
    out mirrored. An "F" was upside down AND combed apart.

  loopdreams #477 -- the Tote Bag returned before the colourwork dispatch, so a
    photo tote generated as a plain one-colour bag. Silent: valid rows, correct
    stitch counts, no colour anywhere.

Both were caught by hand-simulating the fabric. This does that simulation
automatically, on every batch run.

Deliberately narrow, in the same spirit as stitch_count's own posture: it
verifies the PLAIN colourwork row grammar (one grid cell per stitch) and says
"cannot verify" for anything else, rather than guessing. A compound colourwork
row (moss/waffle/bobble/sedge/shell) states its texture as well as its colour
and is left alone.
"""
import re

from ..models import Issue

# "With Colour 2," / "With White," -- a row's opening colour, or a run's.
_RE_WITH = re.compile(r"With\s+(Colour\s+\w+|White)\b", re.I)
# "changing to Colour 1 in the last st"
_RE_CHANGE = re.compile(r"changing to\s+(Colour\s+\w+|White)\s+in the last st", re.I)
# "23 dc in next 23 sts" / "4 dc in the next chain and in next 3 chs across"
_RE_RUN_N = re.compile(r"(\d+)\s+[\w ]+?\s+in (?:the )?next(?:\s+(\d+))?\s+(?:sts?|chs?|chains?)", re.I)
# "dc in the next chain" / "dc in top of ch" / "sc in next st" -- a single stitch
_RE_RUN_1 = re.compile(r"\b[\w ]+?\s+in (?:the )?(?:next (?:chain|st)\b|top of (?:the )?ch\b)", re.I)
# Whole-row shorthand for a solid row: "dc in each st across"
_RE_EACH = re.compile(r"\bin each (?:st|ch) across\b", re.I)

_RE_CHAIN_ONLY = re.compile(r"^(?:Foundation:\s*)?(?:With\s+(?:Colour\s+\w+|White),\s*)?Ch \d+[,.]", re.I)
# Rows that are not part of the fabric the design lives on. "Fasten off" is
# deliberately NOT here: the last body row fastens off and is still a design
# row -- dropping it shortens the panel and silently misaligns every
# expected row against the resampled design.
_SKIP_ROW = re.compile(r"Assembly|Handles?:|Pocket:|Liner|Zipper|Block the pieces|Seam|Repeat Row", re.I)


def _resize_nn(grid, cols, rows):
    """Nearest-neighbour resample -- must match resizeGridNN in the generator's
    colourwork.ts, or expected and actual disagree for reasons that have nothing
    to do with orientation."""
    src_rows = len(grid)
    if src_rows == 0 or cols <= 0 or rows <= 0:
        return []
    src_cols = len(grid[0])
    out = []
    for r in range(rows):
        sr = min(src_rows - 1, (r * src_rows) // rows)
        out.append([grid[sr][min(src_cols - 1, (c * src_cols) // cols)] for c in range(cols)])
    return out


def to_working_order(resized):
    """The design as it is actually crocheted: bottom-up, because the first row
    worked is the bottom of the piece, and every other row reversed, because
    turned rows travel in opposite directions relative to the fabric."""
    h = len(resized)
    out = []
    for i in range(h):
        row = resized[h - 1 - i]
        out.append(list(row) if i % 2 == 0 else list(reversed(row)))
    return out


# Stitch-producing phrases and colour markers, scanned in positional order so a
# "changing to X in the last st" lands after the stitches it follows. Ordered
# longest-first: "4 dc in the next chain and in next 3 chs across" states its
# TOTAL up front, so it must match before the bare "in next 3 chs" inside it.
_TOKENS = re.compile(
    r"(?P<with>With\s+(?:Colour\s+\w+|White))"
    r"|(?P<change>changing to\s+(?:Colour\s+\w+|White)\s+in the last st)"
    r"|(?P<run_chain_span>(?P<n_span>\d+)\s+[A-Za-z][\w ]*?\s+in the next chain and in next \d+\s+(?:chs?|chains?)(?: across)?)"
    # "around" as well as "in": a post stitch is worked AROUND the stitch below
    # ("2 fpdc around next 2 sts"), which is how every waffle colour run reads.
    r"|(?P<run_n>(?P<n_run>\d+)\s+[A-Za-z][\w ]*?\s+(?:in|around) (?:the )?next\s+\d+\s+(?:sts?|chs?|chains?))"
    r"|(?P<each>\bin each (?:st|ch) across\b)"
    r"|(?P<one>[A-Za-z][\w ]*?\s+(?:in|around) (?:the )?(?:next (?:chain|st)|top of (?:the )?ch)\b)",
    re.I,
)
_RE_COLOUR_NAME = re.compile(r"(Colour\s+\w+|White)", re.I)
# The foundation row says so outright; a later row shows it by skipping the
# stitch under the chain and closing into the chain's top.
_RE_CHAIN_COUNTS = re.compile(r"count(?:s)? as this row's first stitch|in top of (?:the )?ch\b", re.I)


def _row_colours(text, width, carried):
    """Per-stitch colours a row's text actually produces, in the order worked.

    Returns (colours, ending_colour), or (None, reason) when the row is not the
    plain colourwork grammar. `carried` is the colour already on the hook, which
    a row naming no colour simply continues in -- that is not a gap in the text,
    it is how a solid row is written.
    """
    body = re.sub(r"\.\s*(?:Ch \d+, turn|Turn|Fasten off[^.]*)\.?\s*$", "", text.strip(), flags=re.I)

    # A row that names no colour and changes to none is worked entirely in the
    # colour already on the hook — whatever its construction. That is as true of
    # a waffle, bobble or shell row as of a plain one, so it needs no run
    # parsing at all, and it is how most of a real photo design's rows read.
    #
    # Deliberately ahead of the run tokenizer: those regexes only know the plain
    # grammar and would reject a perfectly unambiguous solid compound row for
    # containing stitches they cannot count.
    if not _RE_WITH.search(body) and not _RE_CHANGE.search(body):
        return [carried] * width, carried

    # A turning chain of 2+ IS the row's first stitch, made at the END of the
    # previous row -- so it wears the colour carried in, and the row's own text
    # accounts for one stitch fewer (loopdreams #473/#475).
    chain_counts = bool(_RE_CHAIN_COUNTS.search(body))
    target = width - 1 if chain_counts else width

    # Two passes. An "in each st across" span means "whatever is left of the
    # row", and what is left depends on the stitches that come AFTER it too --
    # "dc in each st across, dc in top of ch" leaves one for the closing stitch.
    # So the tokens are collected first and the span resolved once the explicit
    # stitches on both sides of it are known.
    tokens = []
    for m in _TOKENS.finditer(body):
        kind = m.lastgroup
        if kind == "with":
            tokens.append(("with", _RE_COLOUR_NAME.search(m.group()).group(1).title()))
        elif kind == "change":
            tokens.append(("change", _RE_COLOUR_NAME.search(m.group()).group(1).title()))
        elif kind == "each":
            tokens.append(("span", None))
        elif kind in ("run_chain_span", "run_n"):
            tokens.append(("n", int(m.group("n_span") or m.group("n_run"))))
        else:
            tokens.append(("n", 1))

    explicit = sum(n for kind, n in tokens if kind == "n")
    spans = [i for i, (kind, _) in enumerate(tokens) if kind == "span"]
    if len(spans) > 1:
        return None, "more than one open-ended 'in each st across' span in the row"
    if spans:
        tokens[spans[0]] = ("n", max(0, target - explicit))

    colours, cur = [], carried
    for kind, val in tokens:
        if kind in ("with", "change"):
            # "changing to Colour 2 in the last st" is written AFTER the run it
            # closes, so by the time it is read those stitches are already
            # placed and everything from here on is the new colour. (The last
            # stitch of the outgoing run is where the change is physically
            # worked, but that stitch still reads as the outgoing colour.)
            cur = val
            continue
        colours.extend([cur] * val)

    if len(colours) != target:
        return None, f"row works {len(colours)} stitches, expected {target}"
    if chain_counts:
        colours.insert(0, carried)
    return colours, cur


def _rot180(g):
    return [list(reversed(r)) for r in reversed(g)]


# A tote is one panel folded in half, the fold becoming the bag's bottom, so it
# carries the design TWICE -- the half worked first rotated 180°, so both faces
# read the same way up (loopdreams #477). Detected from the assembly row rather
# than from a template name, which this tool never sees.
_RE_FOLDED = re.compile(r"Fold it in half", re.I)


def _candidate_expectations(design, width, rows, folded):
    """The working-order fabric each plausible layout would produce. The first
    is correct; the rest exist only to name the failure when it is one of the
    known orientation mistakes rather than arbitrary noise."""
    def flat(g):
        return to_working_order(_resize_nn(g, width, rows))

    def panel(g):
        half = _resize_nn(g, width, rows // 2)
        return to_working_order(half + _rot180(half))

    build = panel if folded and rows % 2 == 0 else flat
    cands = [("the design", build(design))]
    if not folded:
        resized = _resize_nn(design, width, rows)
        # Stored order: the exact #474 bug -- no bottom-up, no per-row reversal.
        cands.append(("the design fed in stored order (upside down, and every other row mirrored)",
                      [list(r) for r in resized]))
        cands.append(("the design upside down", to_working_order(list(reversed(resized)))))
        cands.append(("the design mirrored left-to-right",
                      to_working_order([list(reversed(r)) for r in resized])))
    else:
        cands.append(("the design stretched across both faces rather than repeated per face", flat(design)))
        half = _resize_nn(design, width, rows // 2)
        cands.append(("the same design on both faces, but the first face not rotated (one face upside down)",
                      to_working_order(half + half)))
    return cands


def check(pattern) -> list:
    design = getattr(pattern, "design_grid", None)
    if not design or not design[0] or len({c for row in design for c in row}) < 2:
        return []   # not a colourwork pattern; nothing to compare against

    source = getattr(pattern, "design_rows", None) or []
    if not source:
        return []   # no verbatim instructions to read; nothing this can check

    folded = any(_RE_FOLDED.search(r.get("instructions") or "") for r in source)

    actual, width, carried, unread = [], None, None, []
    for row in source:
        text = row.get("instructions") or ""
        count = row.get("stitch_count")
        if _SKIP_ROW.search(text) and not _RE_WITH.search(text):
            continue
        if not count:
            continue
        if width is None:
            width = count
        if count != width:
            continue          # a finishing row of a different width
        if carried is None:
            m = _RE_WITH.search(text)
            if not m:
                # Nothing has established a colour yet — either the pattern has
                # not started one, or an unreadable row broke the chain. Either
                # way this row's colours are unknown, so it holds its slot as a
                # hole rather than being dropped.
                #
                # Dropping it is not harmless: `actual` is compared against the
                # design resampled to len(actual) rows, so a row missing from
                # the FRONT shortens the grid and shifts every later row against
                # the design. A waffle pattern shows this immediately — its
                # foundation and setup rows name no colour, so both used to
                # vanish and the whole fabric read as misaligned against a
                # perfectly correct pattern.
                actual.append(None)
                continue
            carried = m.group(1).title()
            if _RE_CHAIN_ONLY.match(text.strip()):
                continue      # "With Colour 1, Ch 20, turn." -- foundation, no stitches
        colours, ending = _row_colours(text, width, carried)
        if colours is None:
            # Unreadable rows are HOLES, not a reason to abandon the pattern.
            # A compound colourwork row states its texture as well as its
            # colour and can be beyond this grammar, but the rows around it
            # are still worth checking — and an orientation fault shows up in
            # any of them, so partial cover still catches it.
            #
            # The row keeps its slot so every later row stays aligned with the
            # design; only the colours are unknown. Since the ending colour is
            # unknown too, `carried` is cleared: a wrong carried colour would
            # be worse than a second hole.
            actual.append(None)
            unread.append((row.get("row_number"), ending))
            carried = None
            continue
        actual.append(colours)
        carried = ending

    if sum(1 for r in actual if r is not None) < 2:
        # An ERROR, not a "cannot verify". The design has more than one colour
        # and the instructions have none: that is not ambiguity in the text, it
        # is a design that was requested and silently dropped -- exactly what
        # loopdreams #477 did for every tote, with valid rows and correct
        # stitch counts the whole way through.
        return [Issue(
            category="colourwork_orientation", severity="error", location="Pattern",
            message=("The pattern was generated from a colourwork design, but its instructions never name a "
                     "colour — the design was dropped somewhere between the request and the rows. The pattern "
                     "is a valid single-colour one, which is why nothing else here objects to it."),
        )]
    return _compare(pattern, design, actual, width, folded, unread)


def _labelled(design, palette):
    """The design in the pattern's own vocabulary. colourLabel() in the
    generator numbers palette entries from 1 and calls anything outside the
    palette "White", so the comparison has to speak the same language."""
    idx = {hexv: f"Colour {i + 1}" for i, hexv in enumerate(palette or [])}
    return [[idx.get(c, "White") for c in row] for row in design]


def _first_difference(expected, actual):
    for r, (e, a) in enumerate(zip(expected, actual)):
        if a is None:
            continue          # unreadable row — no claim either way
        for c, (ec, ac) in enumerate(zip(e, a)):
            if ec != ac:
                return r, c, ec, ac
    return None


def _agrees(expected, actual):
    """Whether a candidate layout is consistent with every row that COULD be
    read. Unreadable rows abstain rather than vote — they can neither confirm
    a layout nor rule one out."""
    if len(expected) != len(actual):
        return False
    return all(a is None or e == a for e, a in zip(expected, actual))


def _compare(pattern, design, actual, width, folded, unread=()) -> list:
    palette = getattr(pattern, "design_palette", None) or []
    labelled = _labelled(design, palette)
    rows = len(actual)

    candidates = _candidate_expectations(labelled, width, rows, folded)
    correct_name, correct = candidates[0]
    if _agrees(correct, actual):
        return _coverage(actual, unread)

    # Not the design. Before reporting a bare mismatch, see whether the fabric
    # matches one of the KNOWN wrong layouts -- naming the specific mistake is
    # the difference between "something is off" and a diagnosis.
    for name, cand in candidates[1:]:
        if _agrees(cand, actual):
            return [Issue(
                category="colourwork_orientation", severity="error", location="Pattern",
                message=(f"The instructions do not make the chosen design: they make {name}. The design grid is "
                         f"stored top-row-first, but the first row crocheted is the BOTTOM of the piece, and "
                         f"flat rows are turned so consecutive rows run in opposite directions — both have to be "
                         f"applied before the colours are written out."),
            )]

    diff = _first_difference(correct, actual)
    if diff is None:
        return [Issue(
            category="colourwork_orientation", severity="error", location="Pattern",
            message=(f"The instructions do not make the chosen design: the fabric is {len(actual)} rows of "
                     f"{width}, the design resolves to {len(correct)} rows."),
        )]
    r, c, ec, ac = diff
    return [Issue(
        category="colourwork_orientation", severity="error", location=f"Row {r + 1}",
        message=(f"The instructions do not make the chosen design. The first difference is stitch {c + 1} of "
                 f"crocheted row {r + 1}: the design calls for {ec} there, the instructions work {ac}."),
    )]


def _coverage(actual, unread):
    """Reported when the design checks out on every row that could be read, but
    some could not. Deliberately still an issue rather than silence: "matches"
    and "matches as far as it could be read" are different claims, and the
    second one should not be mistaken for the first."""
    if not unread:
        return []
    read = sum(1 for r in actual if r is not None)
    total = len(actual)
    reasons = sorted({reason for _, reason in unread})
    rows = ", ".join(f"row {n}" for n, _ in unread[:6])
    if len(unread) > 6:
        rows += f", and {len(unread) - 6} more"
    return [Issue(
        category="colourwork_orientation", severity="warning", location="Pattern",
        message=(f"The design checks out on the {read} of {total} rows this can read, but {len(unread)} could "
                 f"not be read and are unverified ({rows}). A compound colourwork row states its texture as "
                 f"well as its colour, which is outside this check's grammar. Reasons: {'; '.join(reasons)}."),
    )]
