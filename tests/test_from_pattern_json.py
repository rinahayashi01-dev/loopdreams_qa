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
