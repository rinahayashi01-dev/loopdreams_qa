import unittest

from loopdreams_qa.pattern_parser import parse, _strip_noise_lines
from loopdreams_qa.checks import completeness


def _pattern_test_v1_raw(handles_trailer: str = ""):
    # Mirrors the real sample (Tote Bag, Jul 10 "Pattern Test v1" cover
    # page): a "Pattern Overview" + "You Will Need" header pair replacing
    # "Materials", plus a copyright-style page footer split across two
    # lines instead of the earlier URL-based single-line footer.
    return (
        "Tote Bag — Jul 10\n"
        "PATTERN TEST V1\n"
        "Pattern Overview\n"
        "Gauge:18 sc x 20 rows = 4 in [10 cm] · Terminology:US\n"
        "You Will Need\n"
        "#3 Light (DK) yarn — approx 400 yds\n"
        "4.0 mm (G-6 US) crochet hook\n"
        "Yarn needle\n"
        "Scissors\n"
        "© 2026 LoopDreams Studio Pattern Test v1\n"
        "Page 1\n"
        "Abbreviations\n"
        "ch = chain, sc = single crochet, rep = repeat\n"
        "Pattern Steps\n"
        "Foundation chain:Ch 21, turn.\n"
        "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (20 sts)\n"
        "Finishing\n"
        "Border: Fasten off. (20 sts)\n"
        f"Handles (make 2): Ch 41. Sc in 2nd ch from hook and each ch across. Fasten off.{handles_trailer} "
        "(40 sts)\n"
        "© 2026 LoopDreams Studio Pattern Test v1\n"
        "Page 2\n"
    )


class TestCopyrightFooterStripping(unittest.TestCase):
    def test_copyright_and_page_number_lines_stripped(self):
        raw = "Row 1: Sc across. (5 sts)\n© 2026 LoopDreams Studio Pattern Test v1\nPage 3\n"
        lines = _strip_noise_lines(raw)
        self.assertEqual(lines, ["Row 1: Sc across. (5 sts)"])

    def test_handles_trailing_count_not_corrupted_by_footer(self):
        pattern = parse(_pattern_test_v1_raw())
        handles_row = next(r for r in pattern.rows if r.row_start == -2)
        self.assertEqual(handles_row.declared_count, 40)
        issues = completeness.check(pattern)
        handles_issues = [i for i in issues if i.location == handles_row.label]
        self.assertEqual(handles_issues, [])


class TestPatternOverviewYouWillNeedTemplate(unittest.TestCase):
    def test_pattern_overview_recognized_as_materials(self):
        pattern = parse(_pattern_test_v1_raw())
        materials_sections = [s for s in pattern.sections if s.name == "materials"]
        self.assertEqual(len(materials_sections), 1)

    def test_gauge_terminology_yarn_hook_all_recognized(self):
        pattern = parse(_pattern_test_v1_raw())
        materials = next(s for s in pattern.sections if s.name == "materials")
        self.assertIn("gauge", materials.fields)
        self.assertIn("yarn", materials.fields)
        self.assertIn("hook", materials.fields)
        self.assertEqual(pattern.declared_system, "US")
        self.assertEqual(pattern.declared_system_source, "explicit_field")

    def test_yarn_needle_bullet_not_mistaken_for_yarn_field(self):
        pattern = parse(_pattern_test_v1_raw())
        materials = next(s for s in pattern.sections if s.name == "materials")
        self.assertNotEqual(materials.fields["yarn"].strip().lower(), "yarn needle")

    def test_no_materials_section_false_positive(self):
        pattern = parse(_pattern_test_v1_raw())
        issues = completeness.check(pattern)
        materials_issues = [i for i in issues if i.location == "Materials"]
        self.assertEqual(materials_issues, [])

    def test_still_flags_a_genuinely_missing_field(self):
        # Same template shape, but yarn is never mentioned anywhere -- must
        # still be caught as a real missing-field error, not waved through
        # just because the template is now recognized.
        raw = (
            "Tote Bag — Jul 10\n"
            "Pattern Overview\n"
            "Gauge:18 sc x 20 rows = 4 in [10 cm] · Terminology:US\n"
            "You Will Need\n"
            "4.0 mm (G-6 US) crochet hook\n"
            "Scissors\n"
            "Abbreviations\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "Pattern Steps\n"
            "Foundation chain:Ch 21, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (20 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (20 sts)\n"
        )
        pattern = parse(raw)
        issues = completeness.check(pattern)
        yarn_issues = [i for i in issues if "yarn" in i.message.lower()]
        self.assertEqual(len(yarn_issues), 1)
        self.assertEqual(yarn_issues[0].severity, "error")


if __name__ == "__main__":
    unittest.main()
