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
reads the row grammars it actually knows and says "cannot verify" for anything
else, rather than guessing. Every count it derives is asserted against what the
row must come to, so a grammar that drifts fails loudly as "cannot verify"
instead of quietly comparing the wrong thing.

Two things a compound row does that a plain one does not, both handled here:

  A repeat bracket. "*ch 1, sc in next ch-1 sp, skip next st; rep from * 19 more
  times" is 20 worked repeats of its body, not one. Left unexpanded, a row came
  up short and was written off as unreadable -- which is why moss, linen and
  half of bobble could not be read at all.

  A colour resolution that is not the stitch count. A moss or linen row DECLARES
  2n+1 stitches but places only n+1 real single crochets, the ch-1 spaces
  between them being holes rather than stitches; the generator resamples the
  design down to that literal count before writing the colours out
  (buildMossLinenStitchColourRowsInternal's `literalCount`). So the expected row
  has to be resampled the same way before it is compared, or a correct pattern
  reads as wrong at 47 positions against 24.
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
    # "Sc in first st" opens every moss/linen row; "sc in next ch-1 sp" is the
    # one real stitch inside their offset repeat. Neither appears in the plain
    # grammar, and both are single stitches.
    r"|(?P<one>[A-Za-z][\w ]*?\s+(?:in|around) (?:the )?"
    r"(?:next (?:chain|st)|next ch-1 sp|first st|top of (?:the )?ch)\b)",
    re.I,
)
_RE_COLOUR_NAME = re.compile(r"(Colour\s+\w+|White)", re.I)

# "*ch 1, sc in next ch-1 sp, skip next st; rep from * 19 more times" -- the body
# is worked 20 times in all, once as written plus 19 repeats. Bodies never
# contain a nested "*", so a non-greedy run to the ";" is unambiguous.
#
# Deliberately does NOT match the plain builders' "rep from * to last 2 sts, 22
# more times" form: that one's body is bounded by a stitch count rather than a
# plain repeat, and guessing at it would be exactly the kind of silent wrong
# answer this check exists to avoid. Rows written that way are left to fail the
# length assertion and be reported as unreadable.
_RE_REPEAT = re.compile(r"\*(?P<body>[^*]*?);\s*rep from \*\s*(?P<n>\d+)\s+more times?\b", re.I)

# A moss/linen offset row: "ch 1, skip 1 st, sc in next st" (row 3) or
# "ch 1, sc in next ch-1 sp, skip next st" (row 4 onward).
_RE_OFFSET_ROW = re.compile(r"in next ch-1 sp|ch 1,\s*skip 1 st", re.I)


# ── Sedge ────────────────────────────────────────────────────────────────────
# A sedge row is "(sc, hdc, dc) in next st" clusters separated by "skip 2 sts",
# opened by a two-stitch hdc/dc pair and closed by a single sc. Its colours are
# written per CLUSTER, not per stitch: the generator resamples the design to
# one column per cluster plus one for the opener and one for the closer, so a
# 96-stitch row carries 33 colour positions, not 96.
#
# It gets its own tokenizer rather than new alternatives in _TOKENS, and that
# is deliberate. The phrases it needs -- "sc in last st" above all -- occur in
# other fabrics' rows too, where they are currently matched by nothing; adding
# them globally would change the token count of grammars that already read
# correctly. A row is only parsed this way when it actually says "(sedge
# made)", which is the generator's own marker and appears nowhere else.
_RE_SEDGE_ROW = re.compile(r"\(sedge made\)", re.I)

# ── Shell ────────────────────────────────────────────────────────────────────
# Shell alternates two row shapes and colours BOTH at cluster resolution: one
# column per shell or sc position, so a 43-stitch row carries 15 colour
# positions (1 + 2 x shells). Same story as sedge -- unreadable rows cleared
# `carried` and the silent rows after them read as worked with no colour named.
#
# A coloured shell row writes every cluster out longhand (joinClusterSegments
# pushes one phrase per colour column), so unlike the monochrome form there is
# no repeat bracket to expand -- each phrase below is exactly one position.
_RE_SHELL_ROW = re.compile(r"\(half shell made\)|\(shell made\)", re.I)

_SHELL_TOKENS = re.compile(
    r"(?P<with>With\s+(?:Colour\s+\w+|White))"
    r"|(?P<change>changing to\s+(?:Colour\s+\w+|White)\s+in the last st)"
    r"|(?P<half_open>2 dc in first sc \(turning ch-3 counts as first dc; half shell made\))"
    r"|(?P<half_close>3 dc in last sc \(half shell made\))"
    r"|(?P<shell>5 dc in next st \(shell made\))"
    r"|(?P<centre>sc in centre dc of (?:next|last) shell)"
    r"|(?P<dc_in_sc>5 dc in next sc)"
    r"|(?P<sc_first>sc in first st)"
    r"|(?P<sc_next>sc in next st)",
    re.I,
)


def _shell_row_colours(body, target, carried):
    """Colours a shell or half-shell row places, one per cluster position.

    Same contract as _row_colours. Returns None rather than a guess whenever
    the phrases do not add up to the row's own expected position count.
    """
    colours, cur = [], carried
    for m in _SHELL_TOKENS.finditer(body):
        kind = m.lastgroup
        if kind in ("with", "change"):
            cur = _RE_COLOUR_NAME.search(m.group()).group(1).title()
            continue
        colours.append(cur)
    if len(colours) != target:
        return None, f"shell row places {len(colours)} colour positions, expected {target}"
    return colours, cur

# The three things a sedge row places, each worth exactly one colour position.
# "in the last chain" as well as "in the last st": row 1 is worked into the
# foundation chain and says so throughout.
_SEDGE_TOKENS = re.compile(
    r"(?P<with>With\s+(?:Colour\s+\w+|White))"
    r"|(?P<change>changing to\s+(?:Colour\s+\w+|White)\s+in the last (?:st|chain))"
    r"|(?P<opener>hdc in first st,\s*dc in next st"
    r"|hdc in the next chain,\s*dc in the same chain)"
    r"|(?P<cluster>\(sc,\s*hdc,\s*dc\)\s*in next (?:st|chain)\s*\(sedge made\))"
    r"|(?P<closer>sc in last (?:st|chain))",
    re.I,
)


def _sedge_row_colours(body, target, carried):
    """Colours a sedge row places, one per opener/cluster/closer position.

    Same contract as _row_colours: (colours, ending) or (None, reason). Returns
    None rather than a guess whenever the pieces do not add up to the row's own
    expected position count -- a wrong parse here would turn a warning into a
    false accusation, which is the failure this whole module exists to avoid.
    """
    expanded, reason = _expand_repeats(body)
    if expanded is None:
        return None, reason

    colours, cur = [], carried
    for m in _SEDGE_TOKENS.finditer(expanded):
        kind = m.lastgroup
        if kind in ("with", "change"):
            # Same rule as the plain grammar: a change is written after the run
            # it closes, so everything from here on is the new colour.
            cur = _RE_COLOUR_NAME.search(m.group()).group(1).title()
            continue
        colours.append(cur)

    if len(colours) != target:
        return None, f"sedge row places {len(colours)} colour positions, expected {target}"
    return colours, cur


def _expand_repeats(body):
    """Write repeat brackets out in full, so the tokenizer sees every stitch the
    row actually works. Returns None if a bracket cannot be expanded safely."""
    def sub(m):
        inner = m.group("body")
        if "rep from" in inner.lower():
            raise _Unexpandable("nested repeat bracket")
        # A colour marker inside a bracket would be repeated along with the
        # stitches, which is not what the text means and not a form the
        # generator produces. Refuse rather than invent an interpretation.
        if _RE_WITH.search(inner) or _RE_CHANGE.search(inner):
            raise _Unexpandable("colour change inside a repeat bracket")
        return ", ".join([inner.strip()] * (int(m.group("n")) + 1))

    try:
        expanded = _RE_REPEAT.sub(sub, body)
    except _Unexpandable as exc:
        return None, str(exc)
    return expanded, None


class _Unexpandable(Exception):
    pass


def _colour_positions(body, width):
    """How many colour positions a row places, which is not always its declared
    stitch count.

    A moss or linen offset row declares 2n+1 but places n+1 real single
    crochets; the ch-1 spaces between them are holes, and the generator writes
    colours per real stitch. A turning chain of 2+ is itself the row's first
    stitch and is made in the previous row, so the row's own text accounts for
    one fewer."""
    if _RE_SHELL_ROW.search(body):
        # Stitch count is 6n + 1 for n shells; the colour columns are the
        # opening position plus one per shell and one per sc between them.
        return 1 + 2 * round((width - 1) / 6)
    if _RE_SEDGE_ROW.search(body):
        # Row stitch count is 3(n+1) for n clusters -- 2 opener sts + 3n + 1
        # closer st -- so the colour positions (opener + n + closer) are
        # width/3 + 1.
        return width // 3 + 1
    if _RE_OFFSET_ROW.search(body):
        return (width + 1) // 2
    if _RE_CHAIN_COUNTS.search(body):
        return width - 1
    return width
# The foundation row says so outright; a later row shows it by skipping the
# stitch under the chain and closing into the chain's top.
_RE_CHAIN_COUNTS = re.compile(r"count(?:s)? as this row's first stitch|in top of (?:the )?ch\b", re.I)


def _row_colours(text, width, carried):
    """Per-stitch colours a row's text actually produces, in the order worked.

    Returns (colours, ending_colour), or (None, reason) when the row is not a
    grammar this can read. `carried` is the colour already on the hook, which a
    row naming no colour simply continues in -- that is not a gap in the text,
    it is how a solid row is written.

    The list is at the row's OWN colour resolution, which for a moss or linen
    offset row is fewer positions than its stitch count. Callers compare it
    against the design resampled to len(colours), exactly as the generator
    resampled the design to write it.
    """
    body = re.sub(r"\.\s*(?:Ch \d+, turn|Turn|Fasten off[^.]*)\.?\s*$", "", text.strip(), flags=re.I)

    # Resolution first: it decides how long a SOLID row is too, so it has to be
    # settled before the shortcut below and not just before the tokenizer.
    target = _colour_positions(body, width)
    chain_counts = bool(_RE_CHAIN_COUNTS.search(body)) and not _RE_OFFSET_ROW.search(body)

    # A row that names no colour and changes to none is worked entirely in the
    # colour already on the hook — whatever its construction. That is as true of
    # a waffle, bobble or shell row as of a plain one, so it needs no run
    # parsing at all, and it is how most of a real photo design's rows read.
    #
    # Deliberately ahead of the run tokenizer: those regexes only know a handful
    # of grammars and would reject a perfectly unambiguous solid compound row
    # for containing stitches they cannot count.
    if not _RE_WITH.search(body) and not _RE_CHANGE.search(body):
        return [carried] * (target + (1 if chain_counts else 0)), carried

    if _RE_SHELL_ROW.search(body):
        return _shell_row_colours(body, target, carried)

    if _RE_SEDGE_ROW.search(body):
        return _sedge_row_colours(body, target, carried)

    expanded, reason = _expand_repeats(body)
    if expanded is None:
        return None, reason
    body = expanded

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

    def panel(g, rotate=True):
        # One design per face, the first-worked face rotated so both read the
        # same way up, then composed into a single panel image.
        #
        # The odd-row case is linen and is not a rounding wobble to be waved
        # away: linen works one row MORE than the panel (its row 3 converts the
        # plain setup row into the pattern), so a linen tote's body is always an
        # odd number of rows. Falling back to the unfolded layout there compared
        # a correct pattern against a design stretched over the whole panel and
        # reported a real tote as wrong. The generator composes the two faces at
        # their natural height and resamples the pair to the body's row count
        # (buildToteBagColourRows), so this does the same.
        half = _resize_nn(g, width, rows // 2)
        image = half + (_rot180(half) if rotate else half)
        if len(image) != rows:
            image = _resize_nn(image, width, rows)
        return to_working_order(image)

    build = panel if folded else flat
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
        cands.append(("the same design on both faces, but the first face not rotated (one face upside down)",
                      panel(design, rotate=False)))
    return cands


# Sections that are pieces of fabric a design can live on. Everything else a
# pattern is divided into — assembly narrative, a neckline round, button bands —
# is not a panel and must not be checked as one.
#
# Sleeves are excluded deliberately rather than incidentally. They taper through
# seven stitch counts, so the generator never puts a design on them and instead
# names the colour they ARE worked in ("Sleeves (make 2), in Colour 2:"). That
# phrasing happens not to match this module's colour regex today, which would
# make sleeves drop out on their own — but resting on that would mean a harmless
# wording change silently turning them into a panel that fails.
_NON_PANEL_SECTIONS = {"sleeves", "assembly", "neckline", "finishing", "handles", "pocket"}

# Handle strips are named PER PIECE since loopdreams #551 — "Handle 1",
# "Handle 2", and "Handle 1 (shoulder strap)" for the longer variant — where
# they used to be one unsectioned row matched by the bare "handles" above.
# A strip is always plain sc whatever the bag is worked in and never carries a
# design, so it is not a panel. Missing this turned every colourwork tote into
# a FAIL: its handles were the only sections, so the bag's entire body (which
# has no section of its own) was dropped and the two plain straps became the
# only "panels" — "not one of its panels works the design", against a pattern
# whose rows name a colour 121 times.
_NON_PANEL_SECTION_RE = re.compile(r"^handles?\s*\d*(?:\s*\(.*\))?$", re.I)


def _is_non_panel(section: str) -> bool:
    return section.lower() in _NON_PANEL_SECTIONS or bool(_NON_PANEL_SECTION_RE.match(section))


def _panels(source):
    """A pattern's fabric panels, in order, as (section name, rows).

    A garment is several separate pieces — a sweater's Back and Front are two
    40x48 rectangles, each carrying the whole design. Read as one strip they
    look like a single 96-row panel and a perfectly correct pattern reports as
    wrong, which is why garment colourwork had no live coverage until this.

    Returns a single unnamed panel when the pattern is not sectioned, which is
    every flat template.

    Rows with NO section are a piece too, and are collected into one unnamed
    panel rather than discarded. They used to be dropped the moment any other
    row carried a section, on the assumption that a sectioned pattern names
    every one of its pieces — true of garments, and false as soon as a tote
    named only its handles: the whole bag body disappeared from the check.
    """
    named = [r for r in source if (r.get("section") or "").strip()]
    if not named:
        return [(None, source)]
    order, groups = [], {}
    for row in source:
        sec = (row.get("section") or "").strip()
        if sec and _is_non_panel(sec):
            continue
        key = sec or None
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    if not order:
        return [(None, source)]
    return [(sec, groups[sec]) for sec in order]


# A cardigan's front is two half-width panels meeting at the button band, so one
# design spans them. Garment panels are named as WORN and a viewer sees the
# wearer's right on their own left, so "Right Front" holds the design's LEFT
# half — the same reasoning, and the same halves, as the generator's own
# columnSlice. Backwards here would report a correct cardigan as mirrored.
def _carries_design(rows):
    """Whether a panel's text actually places a design, rather than naming the
    single colour it is worked in.

    A design needs either a colour CHANGE or more than one colour named. One
    colour, stated once and never changed, is a solid panel — which is what a
    "front only" placement leaves the Back as, and what the generator is
    obliged to name so the maker knows which ball to pick up (loopdreams#487).
    """
    named, changed = set(), False
    for row in rows:
        text = row.get("instructions") or ""
        for m in _RE_WITH.finditer(text):
            named.add(m.group(1).title())
        for m in _RE_CHANGE.finditer(text):
            named.add(m.group(1).title())
            changed = True
    return changed or len(named) > 1


def _panel_design(design, section):
    if section not in ("Right Front", "Left Front"):
        return design
    half = max(1, len(design[0]) // 2)
    return [row[:half] for row in design] if section == "Right Front" else [row[half:] for row in design]


def check(pattern) -> list:
    design = getattr(pattern, "design_grid", None)
    if not design or not design[0] or len({c for row in design for c in row}) < 2:
        return []   # not a colourwork pattern; nothing to compare against

    source = getattr(pattern, "design_rows", None) or []
    if not source:
        return []   # no verbatim instructions to read; nothing this can check

    panels = _panels(source)
    if len(panels) > 1:
        # A panel worked in ONE colour throughout was deliberately left plain —
        # the maker chose which pieces carry the picture (loopdreams#493). That
        # is a placement decision, not a dropped design, and faulting it would
        # fail every "front only" garment. What WOULD be wrong is nothing
        # carrying the design at all, which is reported below.
        #
        # The test is "one colour and never changes", NOT "names no colour":
        # a plain panel still has to tell the maker which yarn to use, and
        # states it once on its foundation the way any solid piece does. Reading
        # that lone mention as "this panel carries the design" would compare a
        # deliberately solid panel against a multi-colour design and fail it.
        issues, carried = [], []
        for section, rows in panels:
            if not _carries_design(rows):
                continue
            carried.append(section)
            for issue in _check_panel(pattern, _panel_design(design, section), rows):
                # "Back — Row 12" reads; "Back — Pattern" does not. A
                # panel-wide finding is located by the panel itself.
                if section:
                    issue.location = section if issue.location == "Pattern" else f"{section} — {issue.location}"
                issues.append(issue)
        if not carried:
            return [Issue(
                category="colourwork_orientation", severity="error", location="Pattern",
                message=("The pattern was generated from a colourwork design, but not one of its panels works "
                         "the design — every piece is a single colour throughout. A panel left plain is a "
                         "placement choice, but ALL of them plain means the design was dropped somewhere "
                         "between the request and the rows. The pattern is a valid single-colour one, which is "
                         "why nothing else here objects to it."),
            )]
        return issues
    return _check_panel(pattern, design, panels[0][1])


def _check_panel(pattern, design, source) -> list:
    folded = any(_RE_FOLDED.search(r.get("instructions") or "") for r in source)

    actual, width, carried, unread, blind = [], None, None, [], []
    # Parallel to `actual`: True where the generator resampled the design
    # straight to the row's own colour resolution (sedge, shell) rather than
    # through its stitch count. See _expected_row.
    directs = []
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
            # The colour is read BEFORE the row is judged to be a foundation
            # chain, because a foundation names the colour its first worked row
            # is made in ("Foundation: With Colour 2, Ch 48.") and that is
            # frequently the only place the opening rows' colour is stated at
            # all — they have no change to announce, so they announce nothing.
            # Skipping the row before reading it left every pattern's first
            # rows unverifiable: between 1 and 27 of them each, which is the
            # design's bottom edge.
            m = _RE_WITH.search(text)
            if m:
                carried = m.group(1).title()
            # A chain-only foundation makes no stitches, so it is not part of
            # the fabric and must NOT hold a slot — `actual` is compared against
            # the design resampled to len(actual) rows, and an extra leading
            # slot shifts every row against it.
            if _RE_CHAIN_ONLY.match(text.strip()):
                continue
            if carried is None:
                # Nothing has established a colour yet, so this row is being
                # worked without the pattern ever having said in what — see the
                # `blind` report below. Its colours are unknown, so it holds its
                # slot as a hole rather than being dropped.
                #
                # Dropping it is not harmless: a row missing from the FRONT
                # shortens the grid and shifts every later row against the
                # design. A waffle pattern showed this immediately — its
                # foundation and setup rows named no colour, so both used to
                # vanish and the whole fabric read as misaligned against a
                # perfectly correct pattern.
                actual.append(None)
                directs.append(False)
                blind.append(row.get("row_number"))
                continue
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
            directs.append(False)
            unread.append((row.get("row_number"), ending))
            carried = None
            continue
        actual.append(colours)
        directs.append(bool(_RE_SEDGE_ROW.search(text) or _RE_SHELL_ROW.search(text)))
        carried = ending

    # "Dropped" means the instructions name no colour ANYWHERE, and is tested
    # by whether one was ever established -- NOT by how many rows could be read.
    # Those are different questions, and conflating them made this accuse a
    # pattern of dropping its design when it had merely stated its colours late:
    # a pattern whose opening rows are worked blind (loopdreams #487) has few
    # readable rows precisely BECAUSE of that defect, and reporting it as a
    # missing design would be a false accusation of the generator on top of a
    # true one.
    if carried is None and not any(r is not None for r in actual):
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
    if sum(1 for r in actual if r is not None) < 2:
        # Too little to compare a layout against, but something was read or
        # something was named: say what could not be checked, do not diagnose.
        return _blind_rows(blind) + _coverage(actual, unread)
    return _blind_rows(blind) + _compare(pattern, design, actual, width, folded, unread, directs)


def _blind_rows(blind):
    """Rows worked before the pattern ever says what colour to use.

    loopdreams #487: all six compound colourwork builders left the foundation
    chain colourless, and a row names a colour only when it has a CHANGE to
    announce. So a design whose bottom band is one colour -- most photographs,
    and every design with a margin -- produced a pattern that never told the
    maker which yarn to start with. A 60" waffle blanket went 28 rows, about a
    foot of fabric, before naming a colour.

    Nothing else in this package can see it. The pattern is internally
    consistent the whole way down: valid rows, correct stitch counts, no
    contradiction anywhere. Stitch-count and terminology checks pass it because
    nothing in the text is wrong -- the problem is what is absent. It takes the
    design grid to know the omission matters, which is why it lives here.

    An error, not a warning: the maker has to pick a colour to work these rows
    in, the pattern does not say which, and getting it wrong means frogging
    everything up to the first row that does.
    """
    if not blind:
        return []
    rows = ", ".join(f"row {n}" for n in blind[:6])
    if len(blind) > 6:
        rows += f", and {len(blind) - 6} more"
    return [Issue(
        category="colourwork_orientation", severity="error", location=f"Row {blind[0]}",
        message=(f"{len(blind)} row(s) are worked before the pattern names any colour ({rows}). The design "
                 f"has more than one colour, so the maker has to choose one for these rows with nothing to "
                 f"go on — and if they choose wrong there is no remedy but to frog back to the first row "
                 f"that does name one. The foundation chain should state the colour its first worked row is "
                 f"made in."),
    )]


def _labelled(design, palette):
    """The design in the pattern's own vocabulary. colourLabel() in the
    generator numbers palette entries from 1 and calls anything outside the
    palette "White", so the comparison has to speak the same language."""
    idx = {hexv: f"Colour {i + 1}" for i, hexv in enumerate(palette or [])}
    return [[idx.get(c, "White") for c in row] for row in design]


def _at_resolution(expected_row, n):
    """The expected row as the generator would have written it for a row that
    places `n` colour positions. Nearest-neighbour down to the literal count,
    the same call buildMossLinenStitchColourRowsInternal makes -- comparing a
    24-position moss row against the 47-wide design would fail a correct
    pattern at almost every position."""
    if len(expected_row) == n:
        return expected_row
    return _resize_nn([expected_row], n, 1)[0]


def _first_difference(expected, actual):
    for r, (e, a) in enumerate(zip(expected, actual)):
        if a is None:
            continue          # unreadable row — no claim either way
        for c, (ec, ac) in enumerate(zip(_at_resolution(e, len(a)), a)):
            if ec != ac:
                return r, c, ec, ac, len(a)
    return None


def _agrees(expected, actual):
    """Whether a candidate layout is consistent with every row that COULD be
    read. Unreadable rows abstain rather than vote — they can neither confirm
    a layout nor rule one out."""
    if len(expected) != len(actual):
        return False
    return all(a is None or _at_resolution(e, len(a)) == a for e, a in zip(expected, actual))


def _expected_row(base, per_res, name, i, a, direct):
    """The colours row `i` should have, at that row's own resolution.

    `direct` says which sampling the generator used for this row, and the two
    are not interchangeable. Most fabrics resample the design to the row's
    STITCH count and then to its colour resolution — moss's real output proves
    it, and re-deriving those rows in one step fails against it. Sedge and
    shell resample ONCE, straight to their cluster columns, never passing
    through the stitch count at all; re-deriving THOSE in two steps reported
    correct patterns as working the wrong colour. So the row says which.
    """
    if direct:
        return per_res[len(a)][name][i]
    return _at_resolution(base[name][i], len(a))


def _agrees_per_row(base, per_res, name, actual, directs):
    for i, (a, d) in enumerate(zip(actual, directs)):
        if a is None:
            continue          # unreadable row — abstains, as in _agrees
        grid = per_res[len(a)][name] if d else base[name]
        if len(grid) != len(actual) or _expected_row(base, per_res, name, i, a, d) != a:
            return False
    return True


def _first_difference_per_row(base, per_res, name, actual, directs):
    for i, (a, d) in enumerate(zip(actual, directs)):
        if a is None:
            continue
        grid = per_res[len(a)][name] if d else base[name]
        if len(grid) != len(actual):
            return None
        for c, (ec, ac) in enumerate(zip(_expected_row(base, per_res, name, i, a, d), a)):
            if ec != ac:
                return i, c, ec, ac, len(a)
    return None


def _compare(pattern, design, actual, width, folded, unread=(), directs=None) -> list:
    """Compare the fabric the instructions make against the design.

    Every row is checked at ITS OWN colour resolution, and the expectation for
    that row is built by resampling the design straight to it — one step, the
    same one the generator took. Rows in one panel do not all share a
    resolution: a coloured shell panel colours its setup row per stitch (43)
    and every row after it per cluster (15), and a sedge row's 96 stitches
    carry 33 colour positions.

    Building one expectation at the row's STITCH count and down-sampling each
    row to its colour resolution — 8 -> 43 -> 15 — is a different sampling
    from the generator's 8 -> 15 and disagrees at run boundaries. It reported
    correct sedge and shell patterns as working the wrong colour. Hence per
    resolution, which is also why `_at_resolution` is no longer needed here.
    """
    palette = getattr(pattern, "design_palette", None) or []
    labelled = _labelled(design, palette)
    rows = len(actual)

    directs = list(directs) if directs is not None else [False] * len(actual)
    base = dict(_candidate_expectations(labelled, width, rows, folded))
    names = [name for name, _ in _candidate_expectations(labelled, width, rows, folded)]
    # Only the single-resample rows need their own expectation grid.
    resolutions = {len(a) for a, d in zip(actual, directs) if a is not None and d}
    per_res = {res: dict(_candidate_expectations(labelled, res, rows, folded)) for res in resolutions}

    correct_name = names[0]
    if _agrees_per_row(base, per_res, correct_name, actual, directs):
        return _coverage(actual, unread)

    # Not the design. Before reporting a bare mismatch, see whether the fabric
    # matches one of the KNOWN wrong layouts -- naming the specific mistake is
    # the difference between "something is off" and a diagnosis.
    for name in names[1:]:
        if _agrees_per_row(base, per_res, name, actual, directs):
            return [Issue(
                category="colourwork_orientation", severity="error", location="Pattern",
                message=(f"The instructions do not make the chosen design: they make {name}. The design grid is "
                         f"stored top-row-first, but the first row crocheted is the BOTTOM of the piece, and "
                         f"flat rows are turned so consecutive rows run in opposite directions — both have to be "
                         f"applied before the colours are written out."),
            )]

    diff = _first_difference_per_row(base, per_res, correct_name, actual, directs)
    if diff is None:
        return [Issue(
            category="colourwork_orientation", severity="error", location="Pattern",
            message=(f"The instructions do not make the chosen design: the fabric is {len(actual)} rows of "
                     f"{width}, the design resolves to {rows} rows."),
        )]
    r, c, ec, ac, n = diff
    # "stitch" is only accurate when the row places one colour per counted
    # stitch. A moss or linen row places one per real single crochet, so the
    # position is named as what it is rather than mislabelled.
    where = f"stitch {c + 1}" if n == width else f"colour position {c + 1} of {n}"
    return [Issue(
        category="colourwork_orientation", severity="error", location=f"Row {r + 1}",
        message=(f"The instructions do not make the chosen design. The first difference is {where} of "
                 f"crocheted row {r + 1}: the design calls for {ec} there, the instructions work {ac}."),
    )]


def _coverage(actual, unread):
    """Reported when nothing CONTRADICTS the design but some rows could not be
    read. Deliberately still an issue rather than silence: "matches" and
    "matches as far as it could be read" are different claims, and the second
    must not be mistaken for the first.

    The two cases are worded separately on purpose. Saying "the design checks
    out on the 0 of 45 rows this can read" is technically true and actively
    misleading -- it reports having verified nothing as though it were
    agreement. When nothing could be read, this says so plainly and does not
    mention the design checking out at all.
    """
    if not unread:
        return []
    read = sum(1 for r in actual if r is not None)
    reasons = sorted({reason for _, reason in unread})
    rows = ", ".join(f"row {n}" for n, _ in unread[:6])
    if len(unread) > 6:
        rows += f", and {len(unread) - 6} more"
    detail = (f"A compound colourwork row states its texture as well as its colour, which is outside this "
              f"check's grammar. Reasons: {'; '.join(reasons)}.")

    if read == 0:
        return [Issue(
            category="colourwork_orientation", severity="warning", location="Pattern",
            message=(f"Could not check this design against the instructions at all: none of the "
                     f"{len(unread)} colourwork rows could be read ({rows}). Nothing here contradicts the "
                     f"design — nothing here confirms it either. {detail}"),
        )]

    # Only the rows actually compared are claimed. The unread count is stated
    # alongside rather than subtracted from a total: rows that establish no
    # colour are neither read nor unreadable, so the two do not sum to the
    # pattern's row count and implying they do would be its own small lie.
    return [Issue(
        category="colourwork_orientation", severity="warning", location="Pattern",
        message=(f"The design checks out on the {read} row(s) this could read, but {len(unread)} colourwork "
                 f"row(s) could not be read and are unverified ({rows}). {detail}"),
    )]
