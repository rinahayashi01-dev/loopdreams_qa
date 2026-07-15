import unittest

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


class TestRibbingSectionLabelContinuation(unittest.TestCase):
    """Mirrors the real scarf-mossribbed construction: a moss-stitch main
    panel ("FORMING THE BODY") followed by a "RIBBING" section that (a)
    continues the SAME overall row numbering (no restart at Row 1, unlike
    the sweater's genuinely separate Back/Front/Sleeves pieces) but (b)
    still needs its own fresh foundation-chain baseline, since it's a
    narrower strip attached to the main panel's edge, not a continuation
    of the panel's own stitch count."""

    def _raw(self):
        return (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sl st = slip stitch, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "FORMING THE BODY\n"
            "Foundation Ch 10, turn.\n"
            "Row1 Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (9 sts)\n"
            "Row 2 Sc in each st across. Ch 1, turn. (9 sts)\n"
            "RIBBING\n"
            "Row 3 With RS facing, join yarn to the first stitch of the foundation chain. Ch 6, turn. (5 sts)\n"
            "Row 4 Sl st in 2nd ch from hook and in each ch across. Sl st in next 2 sts of the foundation "
            "chain. Ch 1, turn. (5 sts)\n"
            "Row 5 Ch 1, sl st in back loop only of each st across. Ch 1, turn. (5 sts)\n"
            "Row 6 Ch 1, sl st in back loop only of each st across. Sl st in next 1 st of the foundation "
            "chain. Fasten off. (5 sts)\n"
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
            "Row 4 Sl st in 2nd ch from hook and in each ch across. Sl st in next 2 sts of the foundation "
            "chain. Ch 1, turn. (5 sts)",
            "Row 4 Sl st in 2nd ch from hook and in each ch across. Sl st in next 2 sts of the foundation "
            "chain. Ch 1, turn. (99 sts)",
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


if __name__ == "__main__":
    unittest.main()
