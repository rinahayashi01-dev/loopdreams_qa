import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count, completeness
from loopdreams_qa.stitch_parser import tokenize_round

MATERIALS_BLOCK = """MATERIALS
Gauge: 16 dc x 8 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
"""


def _pattern(pattern_steps: str, finishing: str = "Finishing\nAssembly: seam pieces together.\n"):
    raw = (
        "Test Sweater\n"
        + MATERIALS_BLOCK
        + "ABBREVIATIONS\n"
        "ch = chain, dc = double crochet, sc = single crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        + pattern_steps
        + finishing
    )
    return parse(raw)


# Mirrors the real sweater's shape closely enough for the multi-panel
# behaviors under test, without needing the full 46/35-row bodies.
BACK_PANEL = (
    "BACK PANEL\n"
    "Foundation Ch 7.\n"
    "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (4 sts)\n"
    "Row 2 DC in each st across. Ch 3, turn. (4 sts)\n"
)
FRONT_PANEL = (
    "FRONT PANEL\n"
    "Foundation Ch 7.\n"
    "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (4 sts)\n"
    "Row 2 DC in each st across. Ch 3, turn. (4 sts)\n"
)
SLEEVES = (
    "SLEEVES (MAKE 2)\n"
    "Row 1 Sleeves (make 2): Ch 6. (3 sts)\n"
    "Row 2 DC in 4th ch from hook and in each ch across. Ch 3, turn. (3 sts)\n"
    "Row 3 2 DC in first st, DC in each st to last st, 2 DC in last st. Ch 3, turn. (5 sts)\n"
)


class TestMultiPanelRowNumbering(unittest.TestCase):
    def test_each_panel_restarts_at_row_one_without_collision(self):
        pattern = parse(
            "Test Sweater\n" + MATERIALS_BLOCK + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\nPATTERN STEPS\n"
            + BACK_PANEL + FRONT_PANEL + SLEEVES
            + "Finishing\nAssembly: seam pieces together.\n"
        )
        components = [(r.component, r.row_start) for r in pattern.rows]
        self.assertIn(("BACK PANEL", 1), components)
        self.assertIn(("FRONT PANEL", 1), components)
        self.assertIn(("SLEEVES (MAKE 2)", 1), components)
        back_rows = [r for r in pattern.rows if r.component == "BACK PANEL"]
        front_rows = [r for r in pattern.rows if r.component == "FRONT PANEL"]
        self.assertEqual(len(back_rows), 2)
        self.assertEqual(len(front_rows), 2)

    def test_each_component_has_its_own_foundation(self):
        pattern = parse(
            "Test Sweater\n" + MATERIALS_BLOCK + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\nPATTERN STEPS\n"
            + BACK_PANEL + SLEEVES
            + "Finishing\nAssembly: seam pieces together.\n"
        )
        self.assertEqual(pattern.component_foundations["BACK PANEL"], (7, False))
        # Sleeves' foundation comes from its own "Row 1" declaration (Ch 6),
        # captured as the RAW chain count, not the post-skip stitch count.
        self.assertEqual(pattern.component_foundations["SLEEVES (MAKE 2)"], (6, False))

    def test_no_cross_component_stitch_count_bleed(self):
        # Back Panel's Row 2 (4 sts) must not be checked against Sleeves'
        # foundation (6 ch) or vice versa -- each component's math is
        # verified independently.
        pattern = parse(
            "Test Sweater\n" + MATERIALS_BLOCK + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\nPATTERN STEPS\n"
            + BACK_PANEL + SLEEVES
            + "Finishing\nAssembly: seam pieces together.\n"
        )
        issues = stitch_count.check(pattern)
        error_issues = [i for i in issues if i.severity == "error"]
        self.assertEqual(error_issues, [])

    def test_row_gap_detected_within_one_component_not_across(self):
        # Real defect (sweater, Jul 12 batch): Sleeves' Row 15 missing
        # entirely (jumps Row 14 -> Row 16). Must be caught as a real gap,
        # scoped to that component, while Back/Front (which restart at
        # Row 1 right after) must NOT be flagged as a false gap.
        pattern = parse(
            "Test Sweater\n" + MATERIALS_BLOCK + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\nPATTERN STEPS\n"
            "BACK PANEL\n"
            "Foundation Ch 7.\n"
            "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (4 sts)\n"
            "SLEEVES (MAKE 2)\n"
            "Row 1 Sleeves (make 2): Ch 6. (3 sts)\n"
            "Row 2 DC in 4th ch from hook and in each ch across. Ch 3, turn. (3 sts)\n"
            "Row 4 DC in each st across. Ch 3, turn. (3 sts)\n"
            "Finishing\nAssembly: seam pieces together.\n"
        )
        issues = completeness.check(pattern)
        gap_issues = [i for i in issues if "No instructions are given" in i.message]
        self.assertEqual(len(gap_issues), 1)
        self.assertIn("Row 3", gap_issues[0].message)
        self.assertIn("SLEEVES (MAKE 2)", gap_issues[0].location)
        # Back Panel (only Row 1 present) must not be flagged just because
        # Sleeves also has its own Row 1/2/4.
        back_gap_issues = [i for i in gap_issues if "BACK PANEL" in i.location]
        self.assertEqual(back_gap_issues, [])


class TestColonlessRowBadgeFormat(unittest.TestCase):
    # Real sample (sweater, Jul 12 batch): "Row N" is a visual badge label
    # in the source design with no literal colon at all.
    def test_colonless_row_parses_correctly(self):
        pattern = _pattern(
            "Foundation Ch 7.\n"
            "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (4 sts)\n"
            "Row 2 DC in each st across. Ch 3, turn. (4 sts)\n"
        )
        row2 = next(r for r in pattern.rows if r.row_start == 2)
        self.assertEqual(row2.declared_count, 4)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_missing_space_before_row_number_tolerated(self):
        # OCR artifact: "Row3" with no space, alongside normally-spaced
        # "Row 2" elsewhere in the same file.
        pattern = _pattern(
            "Foundation Ch 7.\n"
            "Row1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (4 sts)\n"
            "Row 2 DC in each st across. Ch 3, turn. (4 sts)\n"
            "Row3 DC in each st across. Ch 3, turn. (4 sts)\n"
        )
        row_starts = sorted(r.row_start for r in pattern.rows)
        self.assertEqual(row_starts, [1, 2, 3])

    def test_stray_underscore_after_row_number_does_not_swallow_next_row(self):
        # OCR artifact: "Row 8_ Increase row: ..." -- \b fails to match
        # between a digit and an underscore (both \w), which previously let
        # the preceding row's capture swallow this one whole.
        pattern = _pattern(
            "Foundation Ch 7.\n"
            "Row 7 DC in each st across. Ch 3, turn. (4 sts)\n"
            "Row 8_ Increase row: 2 DC in first st, DC in each st to last st, 2 DC in last st. Ch 3, "
            "turn. (6 sts)\n"
        )
        row7 = next(r for r in pattern.rows if r.row_start == 7)
        row8 = next(r for r in pattern.rows if r.row_start == 8)
        self.assertNotIn("Row 8", row7.raw_text)
        self.assertEqual(row8.declared_count, 6)
        unknown = [c for c in row8.clauses if c.clause_type == "unknown"]
        self.assertEqual(unknown, [])


class TestColonlessFoundationBadge(unittest.TestCase):
    def test_foundation_with_no_colon_recognized(self):
        pattern = _pattern(
            "Foundation Ch 7.\n"
            "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (4 sts)\n"
        )
        self.assertEqual(pattern.foundation_chain, 7)


class TestEachStToLastClause(unittest.TestCase):
    # Real phrasing (sweater, Jul 12 batch, sleeve increase rows): "2 DC in
    # first st, DC in each st to last st, 2 DC in last st" -- an increase
    # row shape, NOT a marker-based partial round completion (which is what
    # the pre-existing broad "each st to <anything>" pattern would
    # otherwise misclassify this as).
    def test_tokenizes_as_each_st_across_not_marker(self):
        clauses = tokenize_round("dc in each st to last st")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "each_st_across")
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 1)

    def test_full_increase_row_verifies_correctly(self):
        # in_count=8: 1 (first st, ->2) + 6 (middle, ->6) + 1 (last st, ->2)
        # = 8 consumed, 2+6+2=10 produced.
        pattern = _pattern(
            "Foundation Ch 11.\n"
            "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (8 sts)\n"
            "Row 2 2 DC in first st, DC in each st to last st, 2 DC in last st. Ch 3, turn. (10 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(row2_issues, [])

    def test_wrong_declared_count_still_caught(self):
        pattern = _pattern(
            "Foundation Ch 11.\n"
            "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (8 sts)\n"
            "Row 2 2 DC in first st, DC in each st to last st, 2 DC in last st. Ch 3, turn. (99 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2" and i.severity == "error"]
        self.assertEqual(len(row2_issues), 1)

    def test_real_marker_based_completion_still_unverifiable(self):
        # Must NOT regress the pre-existing each_st_to_marker behavior for
        # an actual marker reference (not "last st").
        clauses = tokenize_round("sc in each st to marker")
        self.assertEqual(clauses[0].clause_type, "each_st_to_marker")
        self.assertIsNone(clauses[0].consumes)


class TestIncreaseRowLabel(unittest.TestCase):
    def test_increase_row_label_is_noop(self):
        clauses = tokenize_round("Increase row")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")

    def test_increase_row_label_with_ocr_noise_prefix_is_noop(self):
        clauses = tokenize_round("_ Increase row")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")


class TestAssemblyAsFinishingAlias(unittest.TestCase):
    def test_assembly_heading_satisfies_finishing_requirement(self):
        pattern = _pattern(
            "Foundation Ch 7.\n"
            "Row 1 DC in 4th ch from hook and in each ch across. Fasten off. (4 sts)\n",
            finishing="Assembly\nSeam all pieces together and weave in ends.\n",
        )
        issues = completeness.check(pattern)
        no_finishing_issues = [i for i in issues if "No Finishing" in i.message]
        self.assertEqual(no_finishing_issues, [])


class TestDiagramCaptionNotTreatedAsNewComponent(unittest.TestCase):
    def test_caption_matching_existing_component_name_ignored(self):
        pattern = parse(
            "Test Sweater\n" + MATERIALS_BLOCK + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\nPATTERN STEPS\n"
            + SLEEVES
            + "Finishing\n"
            "Assembly: Sleeve (make 2): worked cuff-up, increasing evenly from 8 in to 15 in wide "
            "over 17 in. Seam shoulders and sides.\n"
        )
        make_n_rows = [r for r in pattern.rows if r.row_start == -2]
        self.assertEqual(make_n_rows, [])

    def test_genuine_new_component_still_recognized(self):
        pattern = _pattern(
            "Foundation Ch 7.\n"
            "Row 1 DC in 4th ch from hook and in each ch across. Ch 3, turn. (4 sts)\n",
            finishing="Finishing\nHandles (make 2): Ch 11. SC in 2nd ch from hook and each ch across. "
            "Fasten off. (10 sts)\n",
        )
        make_n_rows = [r for r in pattern.rows if r.row_start == -2]
        self.assertEqual(len(make_n_rows), 1)
        self.assertEqual(make_n_rows[0].declared_count, 10)


if __name__ == "__main__":
    unittest.main()
