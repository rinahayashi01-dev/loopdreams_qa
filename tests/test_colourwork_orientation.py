import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.models import Pattern


A, B = "#C9A227", "#4F7942"
# Asymmetric on BOTH axes, so neither a vertical flip nor a per-row mirror can
# hide behind the other -- which is precisely how loopdreams #474 went unseen.
F = ["BBBBBBBB", "BAAAAAAA", "BAAAAAAA", "BBBBAAAA", "BAAAAAAA", "BAAAAAAA", "BAAAAAAA", "AAAAAAAA"]
DESIGN = [[A if c == "A" else B for c in row] for row in F]


def _pattern(rows, grid=DESIGN, palette=(A, B)):
    p = Pattern()
    p.design_grid = grid
    p.design_palette = list(palette)
    p.design_rows = rows
    return p


# Real output from the generator (buildGenericFlatColourRows, dc, the 4x4 design
# above resampled to 8 sts x 6 rows), copied verbatim rather than reconstructed.
# A hand-written imitation would only prove this check agrees with my idea of
# the generator; the point is that it agrees with the generator.
FAITHFUL_ROWS = [
    {"row_number": 1, "stitch_count": 8, "instructions": "With Colour 2, Ch 10, turn."},
    {"row_number": 2, "stitch_count": 8, "instructions": "Skip the first 3 chains from the hook (they count as this row's first stitch). With Colour 2, dc in the next chain, changing to Colour 1 in the last st; 6 dc in next 6 chs. Ch 3, turn."},
    {"row_number": 3, "stitch_count": 8, "instructions": "With Colour 1, skip first st, 3 dc in next 3 sts, changing to Colour 2 in the last st; 3 dc in next 3 sts, dc in top of ch. Ch 3, turn."},
    {"row_number": 4, "stitch_count": 8, "instructions": "With Colour 2, skip first st, 3 dc in next 3 sts, changing to Colour 1 in the last st; 3 dc in next 3 sts, dc in top of ch. Ch 3, turn."},
    {"row_number": 5, "stitch_count": 8, "instructions": "With Colour 1, skip first st, 5 dc in next 5 sts, changing to Colour 2 in the last st; 1 dc in next 1 st, dc in top of ch. Ch 3, turn."},
    {"row_number": 6, "stitch_count": 8, "instructions": "Skip first st, dc in each st across, dc in top of ch. Ch 3, turn."},
    {"row_number": 7, "stitch_count": 8, "instructions": "Skip first st, dc in each st across, dc in top of ch. Fasten off, weave in ends."},
]
SMALL_DESIGN = [[A if c == "A" else B for c in row] for row in ["BBBB", "BAAA", "BBAA", "BAAA"]]


# Real output from the generator for the moss stitch (dishcloth, the 4x4 design
# above at 11 sts x 10 rows), again copied verbatim. Moss is the awkward case:
# the row DECLARES 11 stitches but places only 6 real single crochets, the ch-1
# spaces between them being holes -- so the colours are written at 6 positions,
# not 11, and every clause after the first is a repeat bracket.
MOSS_ROWS = [
    {"row_number": 1, "stitch_count": 11, "instructions": "Foundation: Ch 12, turn."},
    {"row_number": 2, "stitch_count": 11, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). With Colour 2, 3 Sc in the next chain and in next 2 chs across, changing to Colour 1 in the last st; 8 Sc in next 8 chs. Ch 1, turn."},
    {"row_number": 3, "stitch_count": 11, "instructions": "With Colour 1, Sc in first st, *ch 1, skip 1 st, sc in next st; rep from * 3 more times, changing to Colour 2 in the last st; ch 1, skip 1 st, sc in next st. Ch 1, turn."},
    {"row_number": 4, "stitch_count": 11, "instructions": "With Colour 2, Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 2 more times, changing to Colour 1 in the last st; *ch 1, sc in next ch-1 sp, skip next st; rep from * 1 more time. Ch 1, turn."},
    {"row_number": 5, "stitch_count": 11, "instructions": "With Colour 1, Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 1 more time, changing to Colour 2 in the last st; *ch 1, sc in next ch-1 sp, skip next st; rep from * 2 more times. Ch 1, turn."},
    {"row_number": 6, "stitch_count": 11, "instructions": "With Colour 2, Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 2 more times, changing to Colour 1 in the last st; *ch 1, sc in next ch-1 sp, skip next st; rep from * 1 more time. Ch 1, turn."},
    {"row_number": 7, "stitch_count": 11, "instructions": "With Colour 1, Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 3 more times, changing to Colour 2 in the last st; ch 1, sc in next ch-1 sp, skip next st. Ch 1, turn."},
    {"row_number": 8, "stitch_count": 11, "instructions": "With Colour 2, Sc in first st, ch 1, sc in next ch-1 sp, skip next st, changing to Colour 1 in the last st; *ch 1, sc in next ch-1 sp, skip next st; rep from * 3 more times. Ch 1, turn."},
    {"row_number": 9, "stitch_count": 11, "instructions": "With Colour 2, Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 4 more times. Ch 1, turn."},
    {"row_number": 10, "stitch_count": 11, "instructions": "Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 4 more times. Ch 1, turn."},
    {"row_number": 11, "stitch_count": 11, "instructions": "Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 4 more times. Fasten off, weave in ends."},
]

_BOB = ("bobble in next st (yo, [insert hook, yo, pull up loop, yo, pull through 2 loops] 5 times "
        "in same st, yo pull through all 6 loops)")
# Same design, bobble stitch, 7 sts x 6 rows -- verbatim. The inline how-to in
# every bobble is the trap: it is full of stitch-shaped words ("insert hook",
# "pull through 2 loops") that must contribute nothing to the count.
BOBBLE_ROWS = [
    {"row_number": 1, "stitch_count": 7, "instructions": "Foundation: Ch 8, turn."},
    {"row_number": 2, "stitch_count": 7, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). With Colour 2, 2 Sc in the next chain and in next 1 ch across, changing to Colour 1 in the last st; 5 Sc in next 5 sts. Ch 3, turn."},
    {"row_number": 3, "stitch_count": 7, "instructions": f"With Colour 1, dc in next st, changing to Colour 1 in the last st; {_BOB}, changing to Colour 1 in the last st; dc in next st, changing to Colour 2 in the last st; {_BOB}, changing to Colour 2 in the last st; dc in next st, changing to Colour 2 in the last st; {_BOB}, changing to Colour 2 in the last st; dc in next st. Ch 1, turn."},
    {"row_number": 4, "stitch_count": 7, "instructions": "With Colour 2, 4 sc in next 4 sts, changing to Colour 1 in the last st; 3 sc in next 3 sts. Ch 3, turn."},
    {"row_number": 5, "stitch_count": 7, "instructions": f"With Colour 1, dc in next st, changing to Colour 1 in the last st; {_BOB}, changing to Colour 1 in the last st; dc in next st, changing to Colour 1 in the last st; {_BOB}, changing to Colour 1 in the last st; dc in next st, changing to Colour 2 in the last st; {_BOB}, changing to Colour 2 in the last st; dc in next st. Ch 1, turn."},
    {"row_number": 6, "stitch_count": 7, "instructions": "With Colour 2, 2 sc in next 2 sts, changing to Colour 1 in the last st; 5 sc in next 5 sts. Ch 3, turn."},
    {"row_number": 7, "stitch_count": 7, "instructions": f"With Colour 2, dc in next st, changing to Colour 2 in the last st; {_BOB}, changing to Colour 2 in the last st; dc in next st, changing to Colour 2 in the last st; {_BOB}, changing to Colour 2 in the last st; dc in next st, changing to Colour 2 in the last st; {_BOB}, changing to Colour 2 in the last st; dc in next st. Ch 1, turn."},
    {"row_number": 8, "stitch_count": 7, "instructions": "Sc in each st across. Fasten off, weave in ends."},
]


class TestOrientation(unittest.TestCase):
    def test_no_grid_is_not_this_check_s_business(self):
        p = Pattern()
        self.assertEqual(co.check(p), [])

    def test_single_colour_grid_is_ignored(self):
        p = _pattern([], grid=[[A, A], [A, A]])
        self.assertEqual(co.check(p), [])

    def test_a_dropped_design_is_an_error_not_a_shrug(self):
        # loopdreams #477: a design was requested and the plain builder ran
        # anyway. Valid rows, correct counts, no colour anywhere.
        rows = [{"row_number": n, "stitch_count": 8,
                 "instructions": "Skip first st, dc in each st across, dc in top of ch. Ch 3, turn."}
                for n in range(1, 6)]
        issues = co.check(_pattern(rows))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("never name a colour", issues[0].message)

    def test_working_order_is_bottom_up_and_alternately_mirrored(self):
        # The two halves of #474, asserted directly on the helper.
        grid = [["a", "b"], ["c", "d"], ["e", "f"]]
        self.assertEqual(co.to_working_order(grid), [["e", "f"], ["d", "c"], ["a", "b"]])

    def test_real_generator_output_passes(self):
        self.assertEqual(co.check(_pattern(FAITHFUL_ROWS, grid=SMALL_DESIGN)), [])

    def test_the_same_output_against_a_different_design_is_caught(self):
        # The instructions are unchanged and internally valid; only the design
        # they claim to make is different. Nothing but this check can tell.
        flipped = list(reversed(SMALL_DESIGN))
        issues = co.check(_pattern(FAITHFUL_ROWS, grid=flipped))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("do not make the chosen design", issues[0].message)

    def test_mirroring_every_other_row_is_caught(self):
        mirrored = [list(reversed(r)) for r in SMALL_DESIGN]
        issues = co.check(_pattern(FAITHFUL_ROWS, grid=mirrored))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")


class TestCoverageWording(unittest.TestCase):
    """A partial check must not read as a pass. Saying "the design checks out on
    the 0 of 45 rows this can read" is true and misleading at once — it reports
    having verified nothing as though it were agreement."""

    def _issue(self, read_rows, unread_count):
        actual = [["Colour 1"] for _ in range(read_rows)] + [None] * unread_count
        unread = [(i + 1, "a reason") for i in range(unread_count)]
        return co._coverage(actual, unread)[0]

    def test_nothing_read_does_not_claim_the_design_checks_out(self):
        msg = self._issue(0, 12).message
        self.assertIn("Could not check this design", msg)
        self.assertNotIn("checks out", msg)
        self.assertIn("nothing here confirms it either", msg)

    def test_some_read_claims_only_what_was_compared(self):
        msg = self._issue(48, 48).message
        self.assertIn("checks out on the 48 row(s) this could read", msg)
        self.assertIn("48 colourwork row(s) could not be read", msg)

    def test_nothing_unread_is_silent(self):
        self.assertEqual(co._coverage([["Colour 1"]] * 5, []), [])


class TestRepeatBrackets(unittest.TestCase):
    """A repeat bracket is the whole reason moss, linen and half of bobble read
    as unverifiable for as long as they did: unexpanded, every such row came up
    short and was written off."""

    def test_a_bracket_is_worked_its_body_plus_its_repeats(self):
        body, reason = co._expand_repeats("*sc in next st; rep from * 2 more times")
        self.assertIsNone(reason)
        self.assertEqual(body.count("sc in next st"), 3)   # once as written, twice more

    def test_singular_more_time_is_two_repeats(self):
        body, _ = co._expand_repeats("*sc in next st; rep from * 1 more time")
        self.assertEqual(body.count("sc in next st"), 2)

    def test_a_colour_change_inside_a_bracket_is_refused_not_guessed(self):
        # Repeating a colour change along with the stitches would invent a
        # meaning the text does not have. The generator never writes this;
        # if it ever starts, the row must read as unverifiable, not as agreeing.
        body, reason = co._expand_repeats(
            "*sc in next st, changing to Colour 2 in the last st; rep from * 2 more times")
        self.assertIsNone(body)
        self.assertIn("colour change inside a repeat bracket", reason)

    def test_the_plain_builders_bounded_form_is_left_alone(self):
        # "rep from * to last 2 sts, 22 more times" bounds its repeat by a
        # stitch count rather than a plain multiplier. Expanding it as though
        # the multiplier were the whole story would be a silent wrong answer.
        text = "*bobble in next st, sc in next st; rep from * to last 2 sts, 22 more times"
        body, reason = co._expand_repeats(text)
        self.assertIsNone(reason)
        self.assertEqual(body, text)          # untouched

    def test_a_bobble_row_opening_with_a_bracket_reads(self):
        # The shape a real tote's bobble rows take: a bracket, then bobbles with
        # their inline how-to. Unexpanded the bracket counted 1 where it works
        # 2, the row came up short, and the whole row was discarded.
        text = ("With Colour 2, *sc in next st; rep from * 1 more time, changing to Colour 1 in the "
                "last st; " + _BOB + ". Ch 1, turn.")
        colours, ending = co._row_colours(text, 3, "Colour 2")
        self.assertEqual(colours, ["Colour 2", "Colour 2", "Colour 1"])
        self.assertEqual(ending, "Colour 1")

    def test_a_bobbles_inline_how_to_contributes_no_stitches(self):
        # "insert hook", "pull up loop", "pull through 2 loops" are all
        # stitch-shaped. Counting any of them would break every bobble row.
        colours, _ = co._row_colours(f"With Colour 1, {_BOB}. Ch 1, turn.", 1, "Colour 2")
        self.assertEqual(colours, ["Colour 1"])


class TestColourResolution(unittest.TestCase):
    """A moss or linen row places fewer colours than it declares stitches."""

    def test_an_offset_row_places_one_colour_per_real_stitch(self):
        # 11 declared stitches, 6 real single crochets (the ch-1 spaces between
        # them are holes). Comparing 6 against 11 fails a correct pattern.
        text = ("With Colour 1, Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * "
                "3 more times, changing to Colour 2 in the last st; ch 1, sc in next ch-1 sp, "
                "skip next st. Ch 1, turn.")
        colours, ending = co._row_colours(text, 11, "Colour 1")
        self.assertEqual(len(colours), 6)
        self.assertEqual(colours, ["Colour 1"] * 5 + ["Colour 2"])
        self.assertEqual(ending, "Colour 2")

    def test_a_solid_offset_row_is_also_at_the_literal_count(self):
        # The shortcut for a row naming no colour has to know the resolution
        # too, or a solid moss row comes back 11 long and is compared against
        # the design at 11 while the generator wrote it at 6.
        colours, _ = co._row_colours(
            "Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 4 more times. Ch 1, turn.",
            11, "Colour 2")
        self.assertEqual(colours, ["Colour 2"] * 6)

    def test_a_plain_row_is_unchanged_at_its_full_width(self):
        colours, _ = co._row_colours(
            "Skip first st, dc in each st across, dc in top of ch. Ch 3, turn.", 8, "Colour 1")
        self.assertEqual(colours, ["Colour 1"] * 8)

    def test_the_expected_row_is_resampled_to_meet_it(self):
        # Nearest-neighbour, matching resizeGridNN in the generator -- this is
        # the call buildMossLinenStitchColourRowsInternal makes before writing
        # the colours out, so the check has to make it too.
        self.assertEqual(co._at_resolution(list("aaaabbbb"), 4), list("aabb"))
        self.assertEqual(co._at_resolution(list("aabb"), 4), list("aabb"))


class TestCompoundGeneratorOutput(unittest.TestCase):
    def test_real_moss_output_passes(self):
        self.assertEqual(co.check(_pattern(MOSS_ROWS, grid=SMALL_DESIGN)), [])

    def test_real_bobble_output_passes(self):
        self.assertEqual(co.check(_pattern(BOBBLE_ROWS, grid=SMALL_DESIGN)), [])

    def test_a_wrong_design_is_still_caught_through_the_moss_grammar(self):
        # Coverage that cannot fail anything is worth nothing. The same rows
        # against a different design must be rejected -- otherwise reading moss
        # would only have bought a green light.
        other = [[A if c == "A" else B for c in row] for row in ["AAAA", "ABBB", "AABB", "ABBB"]]
        issues = co.check(_pattern(MOSS_ROWS, grid=other))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")

    def test_the_position_of_a_moss_difference_is_named_honestly(self):
        # "stitch 4" would be wrong for an offset row: it is the 4th real single
        # crochet, not the 4th of the 11 stitches the row declares. Only the
        # offset rows are kept here, so the difference has to land on one.
        offset_only = [MOSS_ROWS[0]] + MOSS_ROWS[2:]
        other = [[A if c == "A" else B for c in row] for row in ["AAAA", "ABBB", "AABB", "ABBB"]]
        issues = co.check(_pattern(offset_only, grid=other))
        self.assertEqual(len(issues), 1)
        self.assertIn("colour position", issues[0].message)
        self.assertIn(" of 6 ", issues[0].message)   # 6 real sts, not the declared 11


class TestFoldedPanel(unittest.TestCase):
    def test_an_odd_body_is_still_two_faces(self):
        # Linen works one row MORE than the panel, so a linen tote's body is
        # always odd. Treating odd as "not folded" compared a correct tote
        # against the design stretched over the whole panel and called it wrong.
        design = [["a", "b"], ["c", "d"]]
        for rows in (6, 7):
            cands = co._candidate_expectations(design, 2, rows, folded=True)
            self.assertEqual(cands[0][0], "the design")
            self.assertEqual(len(cands[0][1]), rows)
            # A folded panel repeats the design per face; the stretched-across
            # layout is only ever offered as a named WRONG answer.
            self.assertIn("stretched across both faces", cands[1][0])


class TestFoundationColour(unittest.TestCase):
    """The foundation chain names the colour its first worked row is made in,
    and is very often the only place the opening rows' colour is stated -- they
    have no change to announce, so they announce nothing."""

    def _rows(self, foundation):
        # A solid opening band, then a row that changes: the shape of almost
        # every real photo design, and the one that hid loopdreams #487.
        return [
            {"row_number": 1, "stitch_count": 4, "instructions": foundation},
            {"row_number": 2, "stitch_count": 4, "instructions": "Sc in each st across. Ch 1, turn."},
            {"row_number": 3, "stitch_count": 4, "instructions": "Sc in each st across. Ch 1, turn."},
            {"row_number": 4, "stitch_count": 4, "instructions": "With Colour 2, 1 sc in next 1 st, changing to Colour 1 in the last st; 3 sc in next 3 sts. Ch 1, turn."},
        ]

    def test_the_foundations_colour_is_carried_into_the_rows_that_name_none(self):
        colours, _ = co._row_colours("Sc in each st across. Ch 1, turn.", 4, "Colour 1")
        self.assertEqual(colours, ["Colour 1"] * 4)

    def test_a_named_foundation_puts_the_opening_rows_in_reach(self):
        # The strong form: with the foundation read, the very FIRST crocheted
        # row can be judged. Before this it abstained -- the check could not
        # have flagged anything there no matter how wrong it was, and the
        # design's bottom edge is exactly where an orientation fault shows.
        # These rows deliberately do not match the design, so a check that is
        # really looking at row 1 must say so.
        issues = co.check(_pattern(self._rows("With Colour 1, Ch 5, turn."), grid=SMALL_DESIGN))
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].location, "Row 1")
        self.assertNotIn("worked before", errors[0].message)

    def test_the_foundation_still_holds_no_slot(self):
        # It makes no stitches. Reading its colour must not also give it a row,
        # or every later row shifts by one against the design.
        named = co.check(_pattern(self._rows("With Colour 1, Ch 5, turn."), grid=SMALL_DESIGN))
        bare = co.check(_pattern(self._rows("Foundation: Ch 5, turn."), grid=SMALL_DESIGN))
        # The bare one reports blind rows; neither reports a row-count mismatch.
        for issues in (named, bare):
            self.assertNotIn("rows, the design resolves to", " ".join(i.message for i in issues))

    def test_rows_worked_before_any_colour_is_named_are_an_error(self):
        # loopdreams #487 exactly: the foundation says nothing, and neither do
        # the opening rows, because they have no change to announce.
        issues = co.check(_pattern(self._rows("Foundation: Ch 5, turn."), grid=SMALL_DESIGN))
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("worked before the pattern names any colour", errors[0].message)
        self.assertIn("row 2, row 3", errors[0].message)
        self.assertEqual(errors[0].location, "Row 2")

    def test_a_pattern_that_names_a_colour_from_the_first_worked_row_is_clean(self):
        # No foundation colour, but nothing is worked blind either -- the first
        # worked row states its own. That is not the #487 defect.
        rows = self._rows("Foundation: Ch 5, turn.")
        rows[1]["instructions"] = "With Colour 1, sc in each st across. Ch 1, turn."
        issues = co.check(_pattern(rows, grid=SMALL_DESIGN))
        self.assertEqual([i.message for i in issues if "worked before" in i.message], [])

    def test_a_wholly_colourless_pattern_is_still_the_dropped_design_error(self):
        # Not reported as "worked blind" twice over: a pattern that names no
        # colour ANYWHERE is #477, and says so.
        rows = [{"row_number": n, "stitch_count": 4,
                 "instructions": "Sc in each st across. Ch 1, turn."} for n in range(1, 6)]
        issues = co.check(_pattern(rows, grid=SMALL_DESIGN))
        self.assertEqual(len(issues), 1)
        self.assertIn("never name a colour", issues[0].message)


# A sweater panel: a foundation chain plus straight rows, all in one section.
def _panel(section, foundation, body_rows, width=4):
    rows = [{"row_number": 1, "stitch_count": width, "instructions": foundation, "section": section}]
    for i, text in enumerate(body_rows):
        rows.append({"row_number": i + 2, "stitch_count": width, "instructions": text, "section": section})
    return rows


class TestMultiPanel(unittest.TestCase):
    """A garment is several separate pieces. Read as one strip, a sweater's Back
    and Front look like a single panel of twice the height and a perfectly
    correct pattern reports as wrong — which is why garment colourwork had no
    live regression coverage until this."""

    SOLID_1 = "With Colour 1, sc in each st across. Ch 1, turn."
    SOLID_2 = "With Colour 2, sc in each st across. Ch 1, turn."
    # Solid per row, so a panel's correct instructions are unambiguous. Row 0 is
    # the TOP of the image and the LAST row crocheted, so working order is
    # Colour 2 then Colour 1 — derived from to_working_order, not guessed.
    DESIGN = [["#111", "#111"], ["#222", "#222"]]
    PALETTE = ("#111", "#222")
    RIGHT = [SOLID_2, SOLID_1]     # what a correct panel says
    WRONG = [SOLID_1, SOLID_2]     # the same panel upside down

    def _garment(self, back, front):
        return (_panel("Back", "Foundation: With Colour 2, Ch 5.", back)
                + _panel("Front", "Foundation: With Colour 2, Ch 5.", front)
                + [{"row_number": 99, "stitch_count": 3, "section": "Sleeves",
                    "instructions": "Sleeves (make 2): With Colour 2, Ch 4."},
                   {"row_number": 100, "stitch_count": 0, "section": "Assembly",
                    "instructions": "Block the pieces: block all four pieces."}])

    def test_panels_are_read_separately_not_as_one_strip(self):
        # Both panels carry the SAME design. Concatenated they would be a
        # 2x-height strip that matches nothing, so a pass here is only possible
        # if each panel was compared against the design in its own right.
        rows = self._garment(self.RIGHT, self.RIGHT)
        p = _pattern(rows, grid=self.DESIGN, palette=self.PALETTE)
        self.assertEqual([i for i in co.check(p) if i.severity == "error"], [])

    def test_a_plain_panel_is_a_placement_choice_not_a_dropped_design(self):
        # "Front only" leaves the Back plain on purpose (loopdreams#493).
        # Faulting it would fail every garment that isn't front-and-back.
        rows = (_panel("Back", "Foundation: Ch 5.",
                       ["Sc in each st across. Ch 1, turn."] * 2)
                + _panel("Front", "Foundation: With Colour 2, Ch 5.", self.RIGHT))
        self.assertEqual([i for i in co.check(_pattern(rows, grid=self.DESIGN, palette=self.PALETTE))
                          if i.severity == "error"], [])

    def test_no_panel_carrying_it_at_all_is_still_the_dropped_design_error(self):
        rows = (_panel("Back", "Foundation: Ch 5.", ["Sc in each st across. Ch 1, turn."] * 2)
                + _panel("Front", "Foundation: Ch 5.", ["Sc in each st across. Ch 1, turn."] * 2))
        issues = co.check(_pattern(rows, grid=self.DESIGN, palette=self.PALETTE))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("not one of its panels works the design", issues[0].message)

    def test_a_wrong_panel_is_named_in_the_finding(self):
        # "Something is off" is worth much less than "the Front is off" when a
        # garment has four pieces.
        rows = self._garment(self.RIGHT, self.WRONG)
        issues = [i for i in co.check(_pattern(rows, grid=self.DESIGN, palette=self.PALETTE))
                  if i.severity == "error"]
        self.assertTrue(issues, "a front panel carrying the design upside down must be caught")
        self.assertTrue(all(i.location.startswith("Front") for i in issues),
                        f"the finding should name the Front panel, got: {[i.location for i in issues]}")

    def test_sleeves_are_not_treated_as_a_panel(self):
        # They taper, so they never carry a design — but they DO name the colour
        # they are worked in, so "does it mention a colour" is not enough to
        # exclude them. Being in _NON_PANEL_SECTIONS is what excludes them, and
        # this test is what stops that being quietly removed.
        rows = self._garment(self.RIGHT, self.RIGHT)
        self.assertEqual([i for i in co.check(_pattern(rows, grid=self.DESIGN, palette=self.PALETTE))
                          if "Sleeve" in i.location], [])

    def test_an_unsectioned_pattern_is_still_one_panel(self):
        # Every flat template and the tote. The panel split must not change them.
        self.assertEqual(co.check(_pattern(FAITHFUL_ROWS, grid=SMALL_DESIGN)), [])


class TestCardiganFrontSplit(unittest.TestCase):
    def test_right_front_takes_the_designs_left_half(self):
        # Panels are named as WORN and a viewer sees the wearer's right on their
        # own left. Backwards here reports a correct cardigan as mirrored — and
        # it has to match the generator's own columnSlice exactly.
        design = [["#111", "#111", "#222", "#222"]] * 4
        self.assertEqual(co._panel_design(design, "Right Front")[0], ["#111", "#111"])
        self.assertEqual(co._panel_design(design, "Left Front")[0], ["#222", "#222"])

    def test_other_panels_get_the_whole_design(self):
        design = [["#111", "#222"], ["#222", "#111"]]
        self.assertEqual(co._panel_design(design, "Back"), design)
        self.assertEqual(co._panel_design(design, None), design)


class TestPlainPanelNamesItsColour(unittest.TestCase):
    """A panel the placement leaves plain still has to say which yarn it is
    worked in — the maker has two balls in front of them. Stating it must not
    make the checker treat the panel as carrying the design."""

    DESIGN = [["#111", "#111"], ["#222", "#222"]]
    PALETTE = ("#111", "#222")

    def _rows(self, back_foundation, back_body):
        return (_panel("Back", back_foundation, back_body)
                + _panel("Front", "Foundation: With Colour 2, Ch 5.",
                         ["With Colour 2, sc in each st across. Ch 1, turn.",
                          "With Colour 1, sc in each st across. Ch 1, turn."]))

    def test_one_colour_named_once_is_a_plain_panel_not_a_design(self):
        # The shape the generator now emits for a "front only" garment: the
        # Back names its colour on the foundation and never changes.
        rows = self._rows("Foundation: With Colour 1, Ch 5.",
                          ["Sc in each st across. Ch 1, turn."] * 2)
        issues = [i for i in co.check(_pattern(rows, grid=self.DESIGN, palette=self.PALETTE))
                  if i.severity == "error"]
        self.assertEqual(issues, [], f"a solid Back must not be judged against the design: {issues}")

    def test_a_panel_that_changes_colour_is_still_checked(self):
        # Coverage that cannot fail anything is worth nothing: a Back that
        # actually works colour changes must still be compared, and caught when
        # it is wrong. Here it carries the design upside down.
        rows = self._rows("Foundation: With Colour 1, Ch 5.",
                          ["With Colour 1, sc in each st across. Ch 1, turn.",
                           "With Colour 2, sc in each st across. Ch 1, turn."])
        issues = [i for i in co.check(_pattern(rows, grid=self.DESIGN, palette=self.PALETTE))
                  if i.severity == "error"]
        self.assertTrue(issues, "a Back working real colour changes must still be verified")
        self.assertTrue(all(i.location.startswith("Back") for i in issues),
                        f"the finding should name the Back panel: {[i.location for i in issues]}")

    def test_carries_design_needs_a_change_or_a_second_colour(self):
        one = [{"instructions": "Foundation: With Colour 1, Ch 5."},
               {"instructions": "Sc in each st across. Ch 1, turn."}]
        two = [{"instructions": "With Colour 1, sc across."},
               {"instructions": "With Colour 2, sc across."}]
        change = [{"instructions": "With Colour 1, 2 sc in next 2 sts, changing to Colour 2 in the last st."}]
        self.assertFalse(co._carries_design(one))
        self.assertTrue(co._carries_design(two))
        self.assertTrue(co._carries_design(change))

    def test_a_wholly_plain_garment_is_still_a_dropped_design(self):
        # Every panel solid in the same colour is not a placement choice — it is
        # a design that never arrived, and must stay an error.
        rows = (_panel("Back", "Foundation: With Colour 1, Ch 5.",
                       ["Sc in each st across. Ch 1, turn."] * 2)
                + _panel("Front", "Foundation: With Colour 1, Ch 5.",
                         ["Sc in each st across. Ch 1, turn."] * 2))
        issues = co.check(_pattern(rows, grid=self.DESIGN, palette=self.PALETTE))
        self.assertEqual(len(issues), 1)
        self.assertIn("not one of its panels works the design", issues[0].message)


# ── Sedge ────────────────────────────────────────────────────────────────────
# Real output from buildSedgeStitchColourRows for the F design above at
# 5 x 3 in / 4 sts / 2 rows (21 sts = 6 clusters, 6 rows), copied verbatim for
# the same reason every other fixture here is: a hand-written imitation would
# only prove this check agrees with my idea of the generator.
#
# A sedge row declares 21 stitches but places 8 colour positions -- an opener
# column covering its hdc+dc pair, one per (sc, hdc, dc) cluster, and a closer.
# Before this was read, every one of these rows was a hole, and a panel of
# holes let a real defect through as "unverified" while a correct pattern was
# reported as worked with no colour named at all (loopdreams #543).
SEDGE_ROWS = [
    {"row_number": 1, "stitch_count": 21, "instructions": "Foundation: With Colour 2, Ch 21, turn."},
    {"row_number": 2, "stitch_count": 21, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). With Colour 2, hdc in the next chain, dc in the same chain, changing to Colour 1 in the last chain; *skip 2 chains, (sc, hdc, dc) in next chain (sedge made); rep from * 5 more times; sc in last chain. Ch 1, turn."},
    {"row_number": 3, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 5 more times, changing to Colour 2 in the last st; sc in last st. Ch 1, turn."},
    {"row_number": 4, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st, changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 5 more times; sc in last st. Ch 1, turn."},
    {"row_number": 5, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 5 more times, changing to Colour 2 in the last st; sc in last st. Ch 1, turn."},
    {"row_number": 6, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st, changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 5 more times; sc in last st. Ch 1, turn."},
    {"row_number": 7, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 5 more times; sc in last st. Fasten off, weave in ends."},
]


class SedgeColourRowsTest(unittest.TestCase):
    def test_a_faithful_sedge_pattern_reports_nothing(self):
        self.assertEqual(co.check(_pattern(SEDGE_ROWS)), [])

    def test_rows_are_read_at_cluster_resolution_not_stitch_count(self):
        # 21 declared stitches, 8 colour positions: opener + 6 clusters + closer.
        colours, _ = co._row_colours(SEDGE_ROWS[2]["instructions"], 21, "Colour 2")
        self.assertIsNotNone(colours, "a sedge row should be readable")
        self.assertEqual(len(colours), 8)

    def test_a_row_is_read_as_the_generator_wrote_it(self):
        # Row 3: opener in Colour 1, six clusters in Colour 1, the change
        # announced on the last of them, so the closer is Colour 2.
        colours, ending = co._row_colours(SEDGE_ROWS[2]["instructions"], 21, "Colour 2")
        self.assertEqual(colours, ["Colour 1"] * 7 + ["Colour 2"])
        self.assertEqual(ending, "Colour 2")

    def test_the_foundation_colour_is_still_what_the_first_row_continues(self):
        # The opening row names its own colour here, but the check must not
        # depend on that: the foundation is where a solid bottom band states it.
        colours, _ = co._row_colours("Foundation: With Colour 2, Ch 21, turn.", 21, None)
        self.assertIsNone(colours, "a chain-only row places no stitches")

    def test_an_upside_down_sedge_pattern_is_still_caught(self):
        # The point of reading these rows is to be able to FAIL them. Reversing
        # the row order makes the fabric the design upside down; if the reader
        # had merely stopped objecting, this would pass too.
        flipped = [SEDGE_ROWS[0]] + list(reversed(SEDGE_ROWS[1:]))
        for i, row in enumerate(flipped):
            row = dict(row)
            row["row_number"] = i + 1
            flipped[i] = row
        issues = co.check(_pattern(flipped))
        self.assertTrue(issues, "an upside-down sedge design should be reported")
        self.assertTrue(
            any(i.severity == "error" for i in issues),
            f"expected an error, got {[(i.severity, i.message[:60]) for i in issues]}",
        )

    def test_a_wrong_colour_in_one_cluster_is_caught(self):
        # A single cluster worked in the other colour — the smallest real
        # defect this can see, and the one a hole would have hidden.
        broken = [dict(r) for r in SEDGE_ROWS]
        broken[2]["instructions"] = broken[2]["instructions"].replace(
            "With Colour 1, hdc in first st", "With Colour 2, hdc in first st", 1)
        issues = co.check(_pattern(broken))
        self.assertTrue(
            any(i.severity == "error" for i in issues),
            f"a mis-coloured cluster should be an error, got {[(i.severity, i.message[:70]) for i in issues]}",
        )


# ── Shell ────────────────────────────────────────────────────────────────────
# Real output from buildShellStitchColourRows for the F design at
# 3.25 x 2.5 in / 4 sts / 2 rows (13 sts = 2 shells, 6 worked rows), copied
# verbatim like every other fixture here.
#
# Shell alternates two row shapes and colours BOTH at cluster resolution: a
# 13-stitch row carries 5 colour positions, not 13. Before this was read, 16
# of 18 rows of a coloured shell piece were holes — and holes clear `carried`,
# so the silent rows after them were reported as worked with no colour ever
# named, on a pattern that was correct (loopdreams#543's story, for shell).
SHELL_ROWS = [
    {"row_number": 1, "stitch_count": 13, "instructions": "Foundation: With Colour 2, Ch 14, turn."},
    {"row_number": 2, "stitch_count": 13, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). With Colour 2, 2 Sc in the next chain and in next 1 ch across, changing to Colour 1 in the last st; 11 Sc in next 11 sts. Ch 1, turn."},
    {"row_number": 3, "stitch_count": 13, "instructions": "With Colour 1, sc in first st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st. Ch 3, turn."},
    {"row_number": 4, "stitch_count": 13, "instructions": "With Colour 2, 2 dc in first sc (turning ch-3 counts as first dc; half shell made), changing to Colour 1 in the last st; sc in centre dc of next shell; 5 dc in next sc; sc in centre dc of last shell; 3 dc in last sc (half shell made). Ch 1, turn."},
    {"row_number": 5, "stitch_count": 13, "instructions": "With Colour 1, sc in first st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st. Ch 3, turn."},
    {"row_number": 6, "stitch_count": 13, "instructions": "With Colour 2, 2 dc in first sc (turning ch-3 counts as first dc; half shell made), changing to Colour 1 in the last st; sc in centre dc of next shell; 5 dc in next sc; sc in centre dc of last shell; 3 dc in last sc (half shell made). Ch 1, turn."},
    {"row_number": 7, "stitch_count": 13, "instructions": "With Colour 1, sc in first st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st. Ch 3, turn."},
    {"row_number": 8, "stitch_count": 13, "instructions": "2 dc in first sc (turning ch-3 counts as first dc; half shell made), *sc in centre dc of next shell, 5 dc in next sc; rep from * to last shell, 0 more times, sc in centre dc of last shell, 3 dc in last sc (half shell made). Fasten off, weave in ends."},
]


class ShellColourRowsTest(unittest.TestCase):
    def test_a_faithful_shell_pattern_reports_nothing(self):
        self.assertEqual(co.check(_pattern(SHELL_ROWS)), [])

    def test_a_shell_row_is_read_at_cluster_resolution(self):
        # 13 declared stitches, 5 colour positions: the opening sc, then one
        # per shell and one per sc between them.
        colours, _ = co._row_colours(SHELL_ROWS[2]["instructions"], 13, "Colour 2")
        self.assertIsNotNone(colours, "a shell row should be readable")
        self.assertEqual(len(colours), 5)

    def test_a_half_shell_row_is_read_at_the_same_resolution(self):
        colours, _ = co._row_colours(SHELL_ROWS[3]["instructions"], 13, "Colour 1")
        self.assertIsNotNone(colours, "a half-shell row should be readable")
        self.assertEqual(len(colours), 5)

    def test_the_change_marker_applies_from_where_it_is_written(self):
        # Row 3 opens in Colour 1 and announces the change on the second
        # shell, so only the closing sc is Colour 2.
        colours, ending = co._row_colours(SHELL_ROWS[2]["instructions"], 13, "Colour 2")
        self.assertEqual(colours, ["Colour 1"] * 4 + ["Colour 2"])
        self.assertEqual(ending, "Colour 2")

    def test_an_upside_down_shell_pattern_is_still_caught(self):
        # Reading these rows is only worth it if a wrong one can still fail.
        flipped = [SHELL_ROWS[0], SHELL_ROWS[1]] + list(reversed(SHELL_ROWS[2:]))
        flipped = [dict(r, row_number=i + 1) for i, r in enumerate(flipped)]
        issues = co.check(_pattern(flipped))
        self.assertTrue(
            any(i.severity == "error" for i in issues),
            f"an upside-down shell design should be reported, got {[(i.severity, i.message[:60]) for i in issues]}",
        )

    def test_a_wrong_colour_in_one_cluster_is_caught(self):
        broken = [dict(r) for r in SHELL_ROWS]
        broken[2]["instructions"] = broken[2]["instructions"].replace(
            "With Colour 1, sc in first st", "With Colour 2, sc in first st", 1)
        issues = co.check(_pattern(broken))
        self.assertTrue(
            any(i.severity == "error" for i in issues),
            f"a mis-coloured shell cluster should be an error, got {[(i.severity, i.message[:70]) for i in issues]}",
        )

    def test_moss_still_uses_the_two_step_sampling(self):
        # The regression guard for this change. Moss's generator resamples the
        # design to the stitch count and THEN to the row's real single
        # crochets; re-deriving those rows in one step fails against its own
        # real output. Sedge and shell are the single-step exceptions, decided
        # per row rather than globally.
        self.assertEqual(co.check(_pattern(MOSS_ROWS, grid=SMALL_DESIGN)), [])


class ToteHandleSectionsTest(unittest.TestCase):
    """A tote names its handle strips but not its body.

    Real incident (2026-09-18, loopdreams #551 + this repo's #65): the handles
    became two rows each carrying their own section ("Handle 1", "Handle 2"),
    where they had been one unsectioned row. _panels then treated the pattern
    as sectioned, DISCARDED every row without a section -- the entire bag body
    -- and was left with two plain sc straps. All four colourwork tote cases
    turned FAIL on "not one of its panels works the design", against patterns
    whose rows name a colour 121 times.

    Two things were wrong and both are fixed: _NON_PANEL_SECTIONS held the old
    bare "handles" and matched none of the new per-piece names, and rows with
    no section were dropped rather than collected into a panel of their own.
    """

    HANDLE_ROWS = [
        {"row_number": 8, "stitch_count": 6, "instructions": "Foundation: Ch 7.", "section": "Handle 1"},
        {"row_number": 9, "stitch_count": 6, "instructions": "Sc in the next chain and each ch across. Work 5 more rows of sc (6 rows total). Fasten off. (6 sts)", "section": "Handle 1"},
        {"row_number": 10, "stitch_count": 6, "instructions": "Foundation: Ch 7.", "section": "Handle 2"},
        {"row_number": 11, "stitch_count": 6, "instructions": "Sc in the next chain and each ch across. Work 5 more rows of sc (6 rows total). Fasten off. (6 sts)", "section": "Handle 2"},
    ]

    def test_the_body_is_still_checked_when_only_the_handles_are_sectioned(self):
        rows = [*FAITHFUL_ROWS, *self.HANDLE_ROWS]
        self.assertEqual(co.check(_pattern(rows, grid=SMALL_DESIGN)), [])

    def test_the_shoulder_strap_naming_is_covered_too(self):
        # The longer variant names its pieces "Handle 1 (shoulder strap)".
        rows = [*FAITHFUL_ROWS, *[{**r, "section": f"{r['section']} (shoulder strap)"} for r in self.HANDLE_ROWS]]
        self.assertEqual(co.check(_pattern(rows, grid=SMALL_DESIGN)), [])

    def test_a_genuinely_wrong_body_is_still_caught_through_the_handles(self):
        # The fix must not become a way for a sectioned pattern to stop being
        # checked at all. Same handles, design flipped: still reported.
        flipped = SMALL_DESIGN[::-1]
        issues = co.check(_pattern([*FAITHFUL_ROWS, *self.HANDLE_ROWS], grid=flipped))
        self.assertTrue(issues, "a flipped design should still be reported with handles present")

    def test_a_real_named_panel_is_unaffected(self):
        # Garments name every fabric row, and must still split per piece --
        # the unsectioned-rows change must not merge them into one strip.
        back  = [{**r, "section": "Back"} for r in FAITHFUL_ROWS]
        front = [{**r, "row_number": r["row_number"] + 7, "section": "Front"} for r in FAITHFUL_ROWS]
        self.assertEqual(co.check(_pattern([*back, *front], grid=SMALL_DESIGN)), [])
