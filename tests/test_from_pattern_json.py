import unittest

from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count, completeness

BASE_PAYLOAD = {
    "title": "Test Scarf",
    "gauge_sts_per_in": 4,
    "gauge_rows_per_in": 2,
    "yarn_weight_name": "Medium",
    "hook_label": "5.0 mm",
    "abbreviations": [{"abbr": "dc", "definition": "Double Crochet"}],
}


class TestRowLineNormalization(unittest.TestCase):
    def test_appends_normalized_sts_count_when_row_ends_in_stitch_abbreviation(self):
        # Real round-construction output (coaster/mitten) ends "(N dc)", not
        # "(N sts)" -- pattern_parser.py's row_re requires the latter to
        # recognize a row at all.
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 12, "instructions": "Magic ring, 12 dc in ring. (12 dc)", "section": None},
        ]}
        raw = build_raw_text(payload)
        self.assertIn("Row 1: Magic ring, 12 dc in ring. (12 dc). (12 sts)", raw)

    def test_leaves_existing_sts_count_alone(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 36, "instructions": "Ch 37, turn. (36 sts)", "section": None},
        ]}
        raw = build_raw_text(payload)
        self.assertIn("Row 1: Ch 37, turn. (36 sts)", raw)
        self.assertNotIn("(36 sts). (36 sts)", raw)


class TestRequiredMaterialsFields(unittest.TestCase):
    def test_gauge_terminology_yarn_hook_all_present(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 10, "instructions": "Ch 11, turn. (10 sts)", "section": None},
        ]}
        raw = build_raw_text(payload)
        self.assertIn("Gauge: 16 sts x 8 rows = 4 in", raw)
        self.assertIn("Terminology: US", raw)
        self.assertIn("Yarn: Medium", raw)
        self.assertIn("Hook: 5.0 mm", raw)

        pattern = parse(raw)
        issues = completeness.check(pattern)
        missing_field_issues = [i for i in issues if "Missing required materials field" in i.message]
        self.assertEqual(missing_field_issues, [], f"unexpected: {missing_field_issues}")


class TestBorderRowBecomesFinishing(unittest.TestCase):
    def test_last_row_starting_with_border_is_finishing_not_a_numbered_row(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 36, "instructions": "Ch 37, turn. (36 sts)", "section": None},
            {"row_number": 2, "stitch_count": 144, "instructions": "Border: Fasten off. Sc around. (144 sts)", "section": None},
        ]}
        raw = build_raw_text(payload)
        lines = raw.split("\n")
        self.assertIn("Finishing", lines)
        finishing_idx = lines.index("Finishing")
        # It's moved under Finishing (not left as a numbered Row among
        # PATTERN STEPS) -- _parse_finishing's own Border regex uses
        # re.search, not an anchored match, so the leftover "Row 2:" prefix
        # ahead of "Border:" doesn't stop it from being recognized.
        self.assertTrue(any("Border:" in ln for ln in lines[finishing_idx:]))
        pattern_steps_idx = lines.index("PATTERN STEPS")
        self.assertNotIn("Border:", "\n".join(lines[pattern_steps_idx:finishing_idx]))

        pattern = parse(raw)
        border_rows = [r for r in pattern.rows if r.label == "Border"]
        self.assertEqual(len(border_rows), 1)
        self.assertEqual(border_rows[0].declared_count, 144)


class TestComponentSections(unittest.TestCase):
    def test_distinct_sections_get_all_caps_header_lines(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 10, "instructions": "Ch 11, turn. (10 sts)", "section": "Back"},
            {"row_number": 2, "stitch_count": 10, "instructions": "Sc across. (10 sts)", "section": "Back"},
            {"row_number": 1, "stitch_count": 10, "instructions": "Ch 11, turn. (10 sts)", "section": "Front"},
        ]}
        raw = build_raw_text(payload)
        lines = raw.split("\n")
        self.assertIn("BACK", lines)
        self.assertIn("FRONT", lines)
        # Only one header per component, not one per row.
        self.assertEqual(lines.count("BACK"), 1)


class TestChainOnlyFoundationDetection(unittest.TestCase):
    # Real generate-pattern output for a flat construction's row 1 is always
    # a bare chain ("Ch 35, turn.") with no pre-existing trailing count --
    # its own stitch_count field describes what the FIRST WORKED row will
    # produce, not something the chain itself produces. The fixtures in the
    # other test classes above all happen to include a trailing "(N sts)"
    # already, which is unrealistic (real data never does this) and masks
    # this whole code path -- these tests use realistic data instead.

    def test_bare_chain_row_becomes_a_foundation_line_with_no_count(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 32, "instructions": "Ch 35, turn.", "section": None},
            {"row_number": 2, "stitch_count": 32, "instructions": "Dc in 4th ch from hook and in each ch across. Ch 3, turn.", "section": None},
        ]}
        raw = build_raw_text(payload)
        lines = raw.split("\n")
        self.assertIn("Foundation: Ch 35, turn.", lines)
        # Renumbered starting from 1 -- this tool doesn't count the
        # foundation chain itself as "Row 1".
        self.assertIn("Row 1: Dc in 4th ch from hook and in each ch across. Ch 3, turn. (32 sts)", lines)

        pattern = parse(raw)
        self.assertEqual(pattern.foundation_chain, 35)
        issues = stitch_count.check(pattern)
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(errors, [], f"unexpected: {errors}")

    def test_foundation_prefix_variant_is_used_as_is(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 56, "instructions": "Foundation: Ch 59.", "section": None},
            {"row_number": 2, "stitch_count": 56, "instructions": "Dc in 4th ch from hook and in each ch across. Ch 3, turn.", "section": None},
        ]}
        raw = build_raw_text(payload)
        lines = raw.split("\n")
        self.assertIn("Foundation: Ch 59.", lines)
        self.assertIn("Row 1: Dc in 4th ch from hook and in each ch across. Ch 3, turn. (56 sts)", lines)

    def test_round_construction_first_round_is_not_treated_as_foundation(self):
        # A magic-ring round genuinely has real worked stitches -- it keeps
        # its own row_number and gets a normalized count like any other row.
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 12, "instructions": "Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to join. (12 dc)", "section": None},
            {"row_number": 2, "stitch_count": 24, "instructions": "Ch 3, dc in same st, 2 dc in each remaining st around, sl st to top of ch 3 to join. (24 dc)", "section": None},
        ]}
        raw = build_raw_text(payload)
        lines = raw.split("\n")
        self.assertFalse(any(ln.startswith("Foundation:") for ln in lines))
        self.assertIn(
            "Row 1: Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to join. (12 dc). (12 sts)",
            lines,
        )

    def test_each_section_gets_its_own_foundation_and_renumbering(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 92, "instructions": "Foundation: Ch 95.", "section": "Back"},
            {"row_number": 2, "stitch_count": 92, "instructions": "Dc in 4th ch from hook and in each ch across. Ch 3, turn.", "section": "Back"},
            {"row_number": 1, "stitch_count": 92, "instructions": "Foundation: Ch 95.", "section": "Front"},
            {"row_number": 2, "stitch_count": 92, "instructions": "Dc in 4th ch from hook and in each ch across. Ch 3, turn.", "section": "Front"},
        ]}
        raw = build_raw_text(payload)
        lines = raw.split("\n")
        self.assertEqual(lines.count("Foundation: Ch 95."), 2)
        self.assertEqual(lines.count("Row 1: Dc in 4th ch from hook and in each ch across. Ch 3, turn. (92 sts)"), 2)

        pattern = parse(raw)
        issues = completeness.check(pattern)
        gap_issues = [i for i in issues if "jumps from" in i.message]
        self.assertEqual(gap_issues, [], f"unexpected row-gap issues: {gap_issues}")


class TestMakeNFoundationDetection(unittest.TestCase):
    # Real sample (sweater, dry-run batch): the drop-shoulder sweater's
    # Sleeves section is a single component covering both sleeves, whose
    # own first row reads "Sleeves (make 2): Ch 39." rather than a plain
    # "Foundation: Ch N." -- and row_number is GLOBAL across the whole
    # pattern (Back 1-49, Front 50-98, Sleeves 99-135, ...), not relative
    # to each section, unlike every other fixture in this file. Before this
    # fix, "Sleeves (make 2): Ch 39." fell through to a plain numbered row
    # (keeping the global row_number, e.g. 99) with a fabricated "(36 sts)"
    # appended, which the row-after-foundation stitch-count check then read
    # as a real declared count on a genuine chain -- producing a false
    # "should produce 36 sts but declares 39" style FAIL against a
    # correctly-generated pattern.

    def test_make_n_row_renumbers_to_row_1_no_colon_with_trailing_count(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 99, "stitch_count": 36, "instructions": "Sleeves (make 2): Ch 39.", "section": "Sleeves"},
            {"row_number": 100, "stitch_count": 36, "instructions": "Dc in 4th ch from hook and in each ch across. Ch 3, turn.", "section": "Sleeves"},
        ]}
        raw = build_raw_text(payload)
        lines = raw.split("\n")
        # No colon after the row number -- pattern_parser.py's
        # _RE_ROW_AS_FOUNDATION requires exactly this shape.
        self.assertIn("Row 1 Sleeves (make 2): Ch 39. (36 sts)", lines)
        self.assertIn("Row 2: Dc in 4th ch from hook and in each ch across. Ch 3, turn. (36 sts)", lines)

    def test_component_foundation_is_recorded_and_no_stitch_count_errors(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 99, "stitch_count": 36, "instructions": "Sleeves (make 2): Ch 39.", "section": "Sleeves"},
            {"row_number": 100, "stitch_count": 36, "instructions": "Dc in 4th ch from hook and in each ch across. Ch 3, turn.", "section": "Sleeves"},
            {"row_number": 101, "stitch_count": 36, "instructions": "Dc in each st across. Ch 3, turn.", "section": "Sleeves"},
        ]}
        raw = build_raw_text(payload)
        pattern = parse(raw)
        # component names are the exact all-caps header text (see
        # _split_component_chunks), so "SLEEVES" not "Sleeves".
        self.assertEqual(pattern.component_foundations.get("SLEEVES"), (39, False))
        issues = stitch_count.check(pattern)
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(errors, [], f"unexpected: {errors}")


class TestEndToEnd(unittest.TestCase):
    def test_full_pipeline_runs_without_crashing_and_finds_the_right_row_count(self):
        payload = {**BASE_PAYLOAD, "rows": [
            {"row_number": 1, "stitch_count": 36, "instructions": "Foundation chain: Ch 37, turn. (36 sts)", "section": None},
            {"row_number": 2, "stitch_count": 36, "instructions": "Sc in each st across. Ch 1, turn. (36 sts)", "section": None},
            {"row_number": 3, "stitch_count": 36, "instructions": "Sc in each st across. Ch 1, turn. (36 sts)", "section": None},
        ]}
        raw = build_raw_text(payload)
        pattern = parse(raw)
        self.assertEqual(len(pattern.rows), 3)
        self.assertEqual(pattern.declared_system, "US")
        issues = stitch_count.check(pattern)
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(errors, [], f"unexpected stitch-count errors: {errors}")


if __name__ == "__main__":
    unittest.main()
