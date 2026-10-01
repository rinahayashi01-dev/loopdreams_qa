import unittest

from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count, completeness
from loopdreams_qa.stitch_parser import tokenize_round

MATERIALS_BLOCK = """MATERIALS
Gauge: 16 sc x 8 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
"""


def _pattern(pattern_steps: str):
    raw = (
        "Test Scarf\n"
        + MATERIALS_BLOCK
        + "ABBREVIATIONS\n"
        "ch = chain, sl st = slip stitch, sc = single crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        + pattern_steps
        + "Finishing\n"
        "Border: Fasten off. (40 sts)\n"
    )
    return parse(raw)


class TestSlStAsRealStitch(unittest.TestCase):
    # Real sample (scarf-mossribbed, Jul 15 batch): "sl st" used as the
    # PRIMARY working stitch of an entire ribbing section (worked in the
    # back loop only, row after row), not just its previous role as a
    # no-op round-closing join marker. Was only in abbreviations.NEUTRAL
    # (for US/UK detection) with no fixed ratio -- every row using it as a
    # real stitch came back "no fixed consumes/produces ratio".
    def test_sl_st_has_a_one_to_one_ratio(self):
        clauses = tokenize_round("sl st in back loop only of each st across")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].stitch, "sl st")
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 1)
        self.assertIsNone(clauses[0].unverifiable_reason)

    def test_sl_st_join_still_a_noop_not_confused_with_real_stitch(self):
        # Must not regress: "sl st to join" is a round-closing no-op, not
        # a real worked stitch, even though "sl st" now has a real ratio.
        clauses = tokenize_round("sl st to top of ch 3 to join")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "join")


class TestChainNoSpace(unittest.TestCase):
    def test_ch_with_no_space_before_number(self):
        clauses = tokenize_round("Ch1")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "chain")
        self.assertEqual(clauses[0].explicit_count, 1)


class TestSlStEdgeAttachNoOp(unittest.TestCase):
    # Real phrasing (scarf-mossribbed, Jul 15 batch): a ribbing strip
    # worked perpendicular to the main panel is fused to it via extra
    # slip stitches into the panel's OWN edge -- a side action that
    # doesn't add to or subtract from the ribbing row's own declared
    # width.
    def test_edge_attach_into_foundation_chain_is_noop(self):
        clauses = tokenize_round("sl st in next 2 sts of the foundation chain")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 0)
        self.assertEqual(clauses[0].produces, 0)

    def test_edge_attach_into_final_row_is_noop(self):
        clauses = tokenize_round("sl st in next 1 st of the final row")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 0)
        self.assertEqual(clauses[0].produces, 0)

    # Current phrasing (loopdreams PR #333, Jul 28 batch): as of that PR, a
    # preliminary sc row is worked across the raw foundation-chain/final-row
    # edge first, and the ribbing panel attaches into THAT row instead --
    # "of the sc row" replaced "of the foundation chain"/"of the final row"
    # everywhere. Must still parse as the same no-op side action.
    def test_edge_attach_into_sc_row_is_noop(self):
        clauses = tokenize_round("sl st in next 2 sts of the sc row")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 0)
        self.assertEqual(clauses[0].produces, 0)


class TestBodyLengthCheckpointNoOp(unittest.TestCase):
    # "Body measures approximately X in." -- appended to a scarf body's own
    # last row before Ribbing/Fringe/Tassels (loopdreams PR #335, Jul 28
    # batch). Purely informational, no stitch-count effect -- must not be
    # reported as an unrecognized clause (real regression found while
    # testing today's other scarf-ribbing fixes: every scarf with this
    # checkpoint was flagging a spurious "Cannot verify stitch-count math"
    # warning on its body's own last row).
    def test_checkpoint_is_a_noop(self):
        clauses = tokenize_round("Body measures approximately 67 in.")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")
        self.assertEqual(clauses[0].consumes, 0)
        self.assertEqual(clauses[0].produces, 0)

    def test_checkpoint_with_decimal_length_is_a_noop(self):
        clauses = tokenize_round("Body measures approximately 19.5 in.")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")

    def test_checkpoint_trailing_on_a_real_row_does_not_break_its_math(self):
        clauses = tokenize_round("Dc in each st across. Fasten off, weave in ends. Body measures approximately 67 in.")
        self.assertEqual([c.clause_type for c in clauses], ["each_st_across", "fasten_off", "closure", "note"])
        self.assertIsNone(clauses[-1].unverifiable_reason)


class TestRibbingOpeningRowMergedScPass(unittest.TestCase):
    """Current construction (loopdreams, Jul 28 batch, same-day follow-up to
    PR #333): the preliminary sc pass across the raw edge is folded directly
    into the ribbing panel's own opening row (join, sc across, chain
    straight up -- no fasten off, no rejoin) rather than being a separate
    row. _RE_ROW_AS_EDGE_FOUNDATION must still recognize this merged shape
    as a row-declared-foundation (establishing component_foundations for
    the panel that follows), not just the older two-row phrasing."""

    def _raw(self, opening_row: str):
        return (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sl st = slip stitch, sc = single crochet, dc = double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "FORMING THE BODY\n"
            "Foundation Ch 10, turn.\n"
            "Row1 Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (9 sts)\n"
            "RIBBING\n"
            f"Row 2 {opening_row}\n"
            "Row 3 Sl st in 2nd ch from hook and in each ch across. Fasten off. (5 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )

    def test_merged_opening_row_still_establishes_the_ribbing_foundation(self):
        raw = self._raw(
            "With RS facing, join yarn to the first stitch of the foundation chain. Sc in each st evenly "
            "across, ending at the opposite corner. Ch 6, turn. (9 sts)"
        )
        pattern = parse(raw)
        self.assertEqual(pattern.component_foundations["RIBBING"], (6, False))

    def test_older_two_row_phrasing_still_works_too(self):
        # Backward compat: a pattern generated before today's fix (or the
        # older "sc row" wording from PR #333 alone) has no sc-pass clause
        # folded into this row at all -- must still match.
        raw = self._raw("With RS facing, join yarn to the first stitch of the sc row. Ch 6, turn. (5 sts)")
        pattern = parse(raw)
        self.assertEqual(pattern.component_foundations["RIBBING"], (6, False))


class TestLabelledPanelOpeningThroughPayload(unittest.TestCase):
    """The generator labels each panel's opening row "Ribbing (Panel N): ..."
    and from_pattern_json writes every row as "Row N: ...". Neither the label
    nor the colon matched _RE_ROW_AS_EDGE_FOUNDATION, so the panel's chain-up
    was never read as the strip's foundation. Its first row was checked
    against the scarf body's foundation chain instead, and every ribbed scarf
    FAILed ("on a 32-chain foundation should produce 29 sts, but the pattern
    declares 10 sts"). Built through build_raw_text, the path batch-test uses."""

    def _payload(self, chain_up: int, first_row_count: int):
        body = [{"row_number": 1, "stitch_count": 8, "instructions": "Ch 10, turn.", "section": None}]
        body += [{"row_number": i, "stitch_count": 8, "section": None, "instructions":
                  "Skip first st (the chain already \u2018fills\u2019 that slot), dc in each st across, "
                  "at the end of the row, dc in top of the ch-3. Ch 3, turn."} for i in range(2, 5)]
        body[1]["instructions"] = ("Skip the first 3 chains from the hook (they count as this row's first stitch, "
                                   "so the foundation chain is one shorter than this row's stitch count). "
                                   "Dc in the next chain and in each ch across. Ch 3, turn.")
        body[-1]["instructions"] = body[-1]["instructions"].replace("Ch 3, turn.", "Fasten off, weave in ends.")
        panel = [
            {"row_number": 5, "stitch_count": 8, "section": None, "instructions":
             "Ribbing (Panel 1): With RS facing, join yarn to the first stitch of the foundation chain. "
             f"Sc in each st evenly across, ending at the opposite corner. Ch {chain_up}, turn."},
            {"row_number": 6, "stitch_count": first_row_count, "section": None, "instructions":
             "Skip the first 3 chains from the hook (they don't count as a stitch). Dc in the next chain "
             "and in each ch across. Sl st in next 2 sts of the sc row. Ch 3, turn."},
        ]
        return {"title": "Test Scarf", "gauge_sts_per_in": 4, "gauge_rows_per_in": 2,
                "yarn_weight_name": "Medium", "hook_label": "5.0 mm",
                "abbreviations": [{"abbr": "dc", "definition": "Double Crochet"},
                                  {"abbr": "sc", "definition": "Single Crochet"}],
                "rows": body + panel}

    def _errors(self, payload):
        pattern = parse(build_raw_text(payload))
        return [i for i in stitch_count.check(pattern) if i.severity == "error"]

    def test_panel_row_is_checked_against_its_own_chain_up(self):
        self.assertEqual(self._errors(self._payload(chain_up=9, first_row_count=6)), [])

    def test_wrong_panel_count_still_caught(self):
        errors = self._errors(self._payload(chain_up=9, first_row_count=7))
        self.assertEqual(len(errors), 1)
        self.assertIn("9-chain foundation", errors[0].message)


class TestPostHdcRibbing(unittest.TestCase):
    """loopdreams writes 1x1 and 2x2 scarf ribbing in post hdc
    ("*Fphdc around next st, bphdc around next st; rep from * across.").
    fphdc/bphdc were not in the stitch vocabulary, so every ribbing row was
    "unrecognized clause": 60 rows per ribbed scarf with nothing checking
    them, and a wrong count on any of them hid inside the REVIEW."""

    def _payload(self, unit: int, counts: list, posts: int = None):
        posts = posts if posts is not None else unit
        body = [{"row_number": 1, "stitch_count": 8, "instructions": "Ch 9, turn.", "section": None}]
        body += [{"row_number": i, "stitch_count": 8, "section": None,
                  "instructions": "Sc in each st across, ch 1, turn."} for i in range(2, 4)]
        body[1]["instructions"] = "Skip the first chain from the hook (it doesn't count as a stitch). Sc in the next chain and in each ch across. Ch 1, turn."
        body[-1]["instructions"] = "Sc in each st across. Fasten off, weave in ends."
        sts = "st" if unit == 1 else f"{unit} sts"
        bp = "st" if posts == 1 else f"{posts} sts"
        rib = [
            {"row_number": 4, "stitch_count": 8, "section": None, "instructions":
             "Ribbing (Panel 1): With RS facing, join yarn to the first stitch of the foundation chain. "
             "Sc in each st evenly across, ending at the opposite corner. Ch 10, turn."},
            {"row_number": 5, "stitch_count": 8, "section": None, "instructions":
             "Skip the first 2 chains from the hook (they don't count as a stitch). Hdc in the next chain "
             "and in each ch across. Sl st in next 2 sts of the sc row. Ch 2, turn."},
        ]
        for i, c in enumerate(counts):
            rib.append({"row_number": 6 + i, "stitch_count": c, "section": None, "instructions":
                        f"*Fphdc around next {sts}, bphdc around next {bp}; rep from * across. Ch 2, turn."})
        return {"title": "Test Scarf", "gauge_sts_per_in": 4, "gauge_rows_per_in": 4,
                "yarn_weight_name": "Medium", "hook_label": "5.0 mm",
                "abbreviations": [{"abbr": a, "definition": d} for a, d in
                                  [("sc", "single crochet"), ("hdc", "half double crochet"),
                                   ("fphdc", "front post half double crochet"),
                                   ("bphdc", "back post half double crochet"), ("ch", "chain")]],
                "rows": body + rib}

    def _issues(self, payload, severity):
        pattern = parse(build_raw_text(payload))
        return [i for i in stitch_count.check(pattern) if i.severity == severity]

    def test_post_hdc_is_a_one_to_one_stitch(self):
        clauses = tokenize_round("fphdc around next 2 sts")
        self.assertEqual(len(clauses), 1)
        self.assertEqual((clauses[0].stitch, clauses[0].consumes, clauses[0].produces), ("fphdc", 2, 2))
        self.assertIsNone(clauses[0].unverifiable_reason)

    def test_1x1_and_2x2_ribbing_rows_verify(self):
        for unit in (1, 2):
            p = self._payload(unit, [8, 8, 8])
            self.assertEqual(self._issues(p, "error"), [], unit)
            self.assertEqual(self._issues(p, "warning"), [], unit)

    def test_wrong_count_is_caught(self):
        for unit in (1, 2):
            self.assertTrue(self._issues(self._payload(unit, [8, 9, 8]), "error"), unit)

    def test_wrong_repeat_is_caught(self):
        # 2 + 3 sts per repeat does not divide an 8-st row.
        self.assertTrue(self._issues(self._payload(2, [8, 8], posts=3), "error"))

    def test_post_hdc_is_us_only(self):
        from loopdreams_qa.checks import terminology
        raw = build_raw_text(self._payload(1, [8])).replace("Terminology: US", "Terminology: UK")
        errors = [i for i in terminology.check(parse(raw)) if i.severity == "error"]
        self.assertTrue(any("fphdc" in i.message for i in errors), errors)


class TestRibbingSectionLabelContinuation(unittest.TestCase):
    """Mirrors the real scarf-mossribbed construction: a moss-stitch main
    panel ("FORMING THE BODY") followed by a "RIBBING" section that (a)
    continues the SAME overall row numbering (no restart at Row 1, unlike
    the sweater's genuinely separate Back/Front/Sleeves pieces) but (b)
    still needs its own fresh foundation-chain baseline, since it's a
    narrower strip attached to the main panel's edge, not a continuation
    of the panel's own stitch count."""

    def _raw(self):
        # Current phrasing (loopdreams, Jul 28 batch, same-day follow-up to
        # PR #333): the preliminary sc pass across the raw foundation-chain/
        # final-row edge is folded directly into the panel's own opening row
        # (real crocheter feedback: the earlier two-row version -- a
        # separate sc row that fastened off, immediately followed by a
        # rejoin -- was an unnecessary fasten off/rejoin, since the sc pass
        # and the panel's own chain-up traverse the same edge in the same
        # direction). The "Ribbing (Panel N):" label stays on this same
        # merged row (stripped from the PDF text, same as it always was on
        # whichever row carried it -- see PatternPrintView.tsx's
        # isRibbingStep-driven stripping). Also reflects the same-day
        # tester-reported fix: each alternating row used to restate its own
        # leading "Ch N," -- e.g. "Ch 1, sl st in back loop..." --
        # duplicating the PREVIOUS row's own trailing "Ch N, turn." Fixed to
        # open directly with the stitch clause instead, same convention this
        # sample's Row 5 always used correctly for the setup row already.
        return (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sl st = slip stitch, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "FORMING THE BODY\n"
            "Foundation Ch 10, turn.\n"
            "Row1 Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (9 sts)\n"
            "Row 2 Sc in each st across. Fasten off, weave in ends. Body measures approximately 5 in. (9 sts)\n"
            "RIBBING\n"
            "Row 3 With RS facing, join yarn to the first stitch of the foundation chain. Sc in each st "
            "evenly across, ending at the opposite corner. Ch 6, turn. (9 sts)\n"
            "Row 4 Sl st in 2nd ch from hook and in each ch across. Sl st in next 2 sts of the sc row. "
            "Ch 1, turn. (5 sts)\n"
            "Row 5 Sl st in back loop only of each st across. Ch 1, turn. (5 sts)\n"
            "Row 6 Sl st in back loop only of each st across. Sl st in next 1 st of the sc row. "
            "Fasten off. (5 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )

    def test_no_false_row_gap_between_sections(self):
        # Row 3 continues straight on from Row 2 (no restart at 1) --
        # must not be flagged as "jumps from the foundation chain
        # directly to Row 3".
        pattern = parse(self._raw())
        issues = completeness.check(pattern)
        gap_issues = [i for i in issues if "No instructions are given" in i.message]
        self.assertEqual(gap_issues, [])

    def test_ribbing_gets_its_own_foundation_not_the_panels(self):
        pattern = parse(self._raw())
        self.assertEqual(pattern.component_foundations["RIBBING"], (6, False))

    def test_ribbing_stitch_math_verifies_against_its_own_foundation(self):
        # Row 4 must derive its in-count from RIBBING's own 6-chain
        # foundation (-> 5 sts), NOT from Row 2's 9 sts.
        pattern = parse(self._raw())
        issues = stitch_count.check(pattern)
        error_issues = [i for i in issues if i.severity == "error"]
        self.assertEqual(error_issues, [])

    def test_wrong_declared_count_in_ribbing_still_caught(self):
        raw = self._raw().replace(
            "Row 4 Sl st in 2nd ch from hook and in each ch across. Sl st in next 2 sts of the sc row. "
            "Ch 1, turn. (5 sts)",
            "Row 4 Sl st in 2nd ch from hook and in each ch across. Sl st in next 2 sts of the sc row. "
            "Ch 1, turn. (99 sts)",
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        row4_errors = [i for i in issues if i.location == "Row 4" and i.severity == "error"]
        self.assertEqual(len(row4_errors), 1)

    def test_second_reset_within_same_component_not_stale(self):
        # The core bug found this session: a SECOND "join yarn...Ch N,
        # turn" reset further into the SAME component (a second ribbing
        # strip) must not inherit a stale prev_count from the real row
        # immediately before it.
        raw = (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sl st = slip stitch, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "FORMING THE BODY\n"
            "Foundation Ch 10, turn.\n"
            "Row1 Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (9 sts)\n"
            "RIBBING\n"
            "Row 2 With RS facing, join yarn to the first stitch of the foundation chain. Ch 6, turn. (5 sts)\n"
            "Row 3 Sl st in 2nd ch from hook and in each ch across. Fasten off. (5 sts)\n"
            "Row 4 With RS facing, join yarn to the last stitch of the final row. Ch 4, turn. (3 sts)\n"
            "Row 5 Sl st in 2nd ch from hook and in each ch across. Fasten off. (3 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        row5_issues = [i for i in issues if i.location == "Row 5"]
        self.assertEqual(row5_issues, [])


class TestRibbingRedundantLeadingChain(unittest.TestCase):
    """Regression coverage for a real tester-reported defect (loopdreams
    builders.ts's ribbingAlternatingRow, Jul 28 batch): every alternating
    ribbing row used to restate its own leading "Ch N," before its own
    stitch clause, duplicating the previous row's own trailing "Ch N,
    turn." -- invisible to the stitch-count algebra (a bare, uncounted
    chain always produces=0), so this dedicated check exists specifically
    to catch a regression back to that old wording."""

    def _raw(self, alternating_row: str):
        return (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sl st = slip stitch, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "FORMING THE BODY\n"
            "Foundation Ch 10, turn.\n"
            "Row1 Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (9 sts)\n"
            "RIBBING\n"
            "Row 2 With RS facing, join yarn to the first stitch of the sc row. Ch 6, turn. (5 sts)\n"
            "Row 3 Sl st in 2nd ch from hook and in each ch across. Ch 1, turn. (5 sts)\n"
            f"Row 4 {alternating_row}\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )

    def test_old_buggy_wording_is_flagged(self):
        raw = self._raw("Ch 1, sl st in back loop only of each st across. Ch 1, turn. (5 sts)")
        pattern = parse(raw)
        issues = completeness.check(pattern)
        matches = [i for i in issues if i.location == "Row 4" and "redundant restatement" in i.message]
        self.assertEqual(len(matches), 1)

    def test_old_buggy_wording_is_flagged_for_post_stitch_types_too(self):
        raw = self._raw("Ch 3, *fpdc around next st, bpdc around next st; rep from * across. Ch 3, turn. (5 sts)")
        pattern = parse(raw)
        issues = completeness.check(pattern)
        matches = [i for i in issues if i.location == "Row 4" and "redundant restatement" in i.message]
        self.assertEqual(len(matches), 1)

    def test_fixed_wording_is_not_flagged(self):
        raw = self._raw("Sl st in back loop only of each st across. Ch 1, turn. (5 sts)")
        pattern = parse(raw)
        issues = completeness.check(pattern)
        matches = [i for i in issues if i.location == "Row 4" and "redundant restatement" in i.message]
        self.assertEqual(matches, [])

    def test_leading_chain_outside_a_ribbing_component_is_not_flagged(self):
        # Same shape (bare leading chain followed by a full-row stitch
        # clause), but NOT inside a "RIBBING" component -- must not misfire
        # on unrelated legitimate uses elsewhere in the app.
        raw = (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sl st = slip stitch, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation Ch 10, turn.\n"
            "Row1 Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (9 sts)\n"
            "Row 2 Ch 1, sl st in back loop only of each st across. Ch 1, turn. (9 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        issues = completeness.check(pattern)
        matches = [i for i in issues if "redundant restatement" in i.message]
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
