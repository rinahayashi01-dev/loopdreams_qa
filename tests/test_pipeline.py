"""
Regression tests for the QA pipeline's core logic.

Run with: python -m unittest discover -s tests -v
(from the project root, i.e. the directory containing loopdreams_qa/)
"""

import unittest

from loopdreams_qa.models import Pattern, RoundRow
from loopdreams_qa.stitch_parser import parse_round_body
from loopdreams_qa.checks.stitch_count import check_stitch_counts
from loopdreams_qa.checks.terminology import check_terminology
from loopdreams_qa.checks.completeness import check_completeness
from loopdreams_qa.pattern_parser import build_pattern


def make_round(label, number, body, system="US"):
    parsed = parse_round_body(body, system)
    return RoundRow(
        label=label, number=number, raw_text=body,
        leading_clauses=parsed["leading_clauses"],
        repeat_groups=parsed["repeat_groups"],
        trailing_clauses=parsed["trailing_clauses"],
        declared_count=parsed["declared_count"],
        unparsed_fragments=parsed["unparsed_fragments"],
    )


class StitchCountTests(unittest.TestCase):
    def test_clean_amigurumi_sphere(self):
        rounds = [
            make_round("Round", 1, "6 sc in magic ring (6)"),
            make_round("Round", 2, "*sc in next 1, inc* repeat from * around (9)"),
            make_round("Round", 3, "*sc in next 2, inc* repeat from * around (12)"),
            make_round("Round", 4, "sc in each st around (12)"),
        ]
        p = Pattern(source_path="t", full_text="", rounds=rounds, declared_system="US")
        issues = check_stitch_counts(p)
        self.assertEqual(issues, [], f"Expected no issues, got: {issues}")

    def test_catches_wrong_declared_count_after_solved_repeat(self):
        rounds = [
            make_round("Round", 1, "6 sc in magic ring (6)"),
            make_round("Round", 2, "*sc in next 1, inc* repeat from * around (9)"),
            make_round("Round", 3, "*sc in next 2, inc* repeat from * around (17)"),  # should be 12
        ]
        p = Pattern(source_path="t", full_text="", rounds=rounds, declared_system="US")
        issues = check_stitch_counts(p)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("Round 3", issues[0].location)

    def test_catches_fixed_math_error_no_unknowns(self):
        rounds = [
            make_round("Round", 1, "6 sc in magic ring (6)"),
            make_round("Round", 2, "sc, inc, sc, inc, sc, inc (10)"),  # math gives 9
        ]
        p = Pattern(source_path="t", full_text="", rounds=rounds, declared_system="US")
        issues = check_stitch_counts(p)
        self.assertEqual(len(issues), 1)
        self.assertIn("produce 9 stitches", issues[0].message)

    def test_decrease_round_clean(self):
        rounds = [
            make_round("Round", 5, "sc in each st around (12)"),
            make_round("Round", 6, "*sc in next 2, dec* repeat from * around (9)"),
        ]
        p = Pattern(source_path="t", full_text="", rounds=rounds, declared_system="US")
        issues = check_stitch_counts(p)
        self.assertEqual(issues, [])

    def test_explicit_repeat_count_x_form(self):
        rounds = [
            make_round("Round", 1, "12 sc in magic ring (12)"),
            make_round("Round", 2, "[sc, inc] x6 (18)"),  # 6 reps of (consumes2,produces3) -> consumes12,produces18
        ]
        p = Pattern(source_path="t", full_text="", rounds=rounds, declared_system="US")
        issues = check_stitch_counts(p)
        self.assertEqual(issues, [], f"Expected no issues, got: {issues}")

    def test_unbalanced_unsolvable_ambiguity_is_flagged_not_silently_passed(self):
        # 17 is not evenly reachable from 9 with a *sc,inc* repeat (delta +1/iter, needs to land on 12,13,...)
        rounds = [
            make_round("Round", 1, "*sc, inc* repeat from * around (9)"),
            make_round("Round", 2, "*sc, inc* repeat from * around (17)"),
        ]
        # round 1 has no previous count so it's accepted (declared count propagates); round 2 should be checked
        p = Pattern(source_path="t", full_text="", rounds=rounds, declared_system="US")
        issues = check_stitch_counts(p)
        self.assertTrue(any(i.severity == "error" for i in issues))


class TerminologyTests(unittest.TestCase):
    def test_flags_uk_term_in_us_declared_pattern(self):
        rounds = [make_round("Round", 4, "htr in each st around (12)")]
        p = Pattern(source_path="t", full_text="", rounds=rounds,
                     declared_system="US", declared_system_source="explicit")
        issues = check_terminology(p)
        self.assertTrue(any("htr" in i.message and i.severity == "error" for i in issues))

    def test_clean_us_pattern_no_terminology_issues(self):
        rounds = [make_round("Round", 1, "sc in each st around (6)")]
        p = Pattern(source_path="t", full_text="", rounds=rounds,
                     declared_system="US", declared_system_source="explicit")
        issues = check_terminology(p)
        self.assertEqual(issues, [])

    def test_no_declared_system_but_mixed_terms_flagged(self):
        rounds = [
            make_round("Round", 1, "sc in each st around (6)"),
            make_round("Round", 2, "htr in each st around (12)"),
        ]
        p = Pattern(source_path="t", full_text="", rounds=rounds,
                     declared_system=None, declared_system_source="none")
        issues = check_terminology(p)
        # one warning for "system not declared", one error for the mix
        self.assertTrue(any(i.severity == "error" and "mixes" in i.message for i in issues))

    def test_ambiguous_bare_dc_not_flagged_alone(self):
        rounds = [make_round("Round", 1, "dc in each st around (6)")]
        p = Pattern(source_path="t", full_text="", rounds=rounds,
                     declared_system="US", declared_system_source="explicit")
        issues = check_terminology(p)
        self.assertEqual(issues, [], "bare 'dc' is ambiguous and shouldn't be flagged on its own")


class CompletenessTests(unittest.TestCase):
    def test_missing_sections_flagged(self):
        text = "Instructions\nRound 1: 6 sc in magic ring (6)\n"
        p = build_pattern("t.docx", text)
        issues = check_completeness(p)
        locations = {i.message for i in issues}
        self.assertTrue(any("Gauge" in m for m in locations))
        self.assertTrue(any("finishing" in m.lower() for m in locations))

    def test_unbalanced_asterisk_flagged(self):
        rounds = [make_round("Round", 2, "*sc in next 2, dec around (8)")]
        p = Pattern(source_path="t", full_text="", rounds=rounds, sections={})
        issues = check_completeness(p)
        self.assertTrue(any("odd number of" in i.message for i in issues))

    def test_balanced_repeat_with_back_reference_not_flagged(self):
        rounds = [make_round("Round", 2, "*sc, inc* repeat from * around (9)")]
        p = Pattern(source_path="t", full_text="", rounds=rounds, sections={})
        issues = check_completeness(p)
        self.assertFalse(any("odd number of" in i.message for i in issues))


if __name__ == "__main__":
    unittest.main()
