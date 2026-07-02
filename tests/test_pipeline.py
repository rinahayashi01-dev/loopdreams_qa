import os
import unittest

from loopdreams_qa.extraction import extract_text
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count, terminology, completeness
from loopdreams_qa.report import build_report

SAMPLE = "/mnt/user-data/uploads/loopdreams-scarf-jun-26.pdf"


class TestScarfPattern(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SAMPLE):
            raise unittest.SkipTest("sample file not present")
        raw_text = extract_text(SAMPLE)
        cls.pattern = parse(raw_text)
        cls.issues = (
            stitch_count.check(cls.pattern)
            + terminology.check(cls.pattern)
            + completeness.check(cls.pattern)
        )
        cls.report = build_report(cls.pattern, cls.issues)

    def test_materials_parsed(self):
        self.assertEqual(self.pattern.declared_system, "US")
        self.assertEqual(self.pattern.foundation_chain, 39)

    def test_rows_parsed(self):
        labels = [r.label for r in self.pattern.rows]
        self.assertEqual(labels, ["Rows 1-198", "Rows 199-396", "Border"])
        self.assertEqual(self.pattern.rows[0].declared_count, 36)
        self.assertEqual(self.pattern.rows[2].declared_count, 876)
        self.assertTrue(self.pattern.rows[2].declared_count_is_approx)

    def test_terminology_clean(self):
        term_issues = [i for i in self.issues if i.category == "terminology"]
        self.assertEqual(term_issues, [])

    def test_shell_stitch_construction_flagged(self):
        msgs = [i.message for i in self.issues if i.category == "completeness" and i.severity == "error"]
        self.assertTrue(any("sh st" in m and "construction" in m for m in msgs))

    def test_overall_status_fail(self):
        self.assertEqual(self.report["summary"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
