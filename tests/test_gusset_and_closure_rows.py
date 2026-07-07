import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count

MATERIALS_BLOCK = """MATERIALS
Gauge: 16 sc x 8 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
"""


def _pattern(pattern_steps: str):
    raw = (
        "Test Mitten\n"
        + MATERIALS_BLOCK
        + "ABBREVIATIONS\n"
        "ch = chain, sc = single crochet, sc2tog = sc2tog, rep = repeat\n"
        "PATTERN STEPS\n"
        + pattern_steps
    )
    return parse(raw)


class TestMagicRingFoundation(unittest.TestCase):
    def test_magic_ring_establishes_foundation_count(self):
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 6 sc in ring. Place a stitch marker in the "
            "first st — work in a continuous spiral from here on, do not join or turn. (6 sc)\n"
            "Row 1: Sc in the back loop only of each st around. (6 sc) (6 sts)\n"
        )
        self.assertEqual(pattern.foundation_chain, 6)
        self.assertTrue(pattern.foundation_is_magic_ring)
        issues = stitch_count.check(pattern)
        self.assertEqual(issues, [])

    def test_magic_ring_does_not_trigger_chain_ordinal_ambiguity(self):
        # Real bug: a magic-ring foundation has no turning-chain-skip
        # concept at all, but the existing "which numbered chain to start
        # in" ambiguity check didn't know that and flagged it anyway.
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 6 sc in ring. (6 sc)\n"
            "Row 1: Sc in each st around. (6 sc) (6 sts)\n"
        )
        issues = stitch_count.check(pattern)
        ambiguity_issues = [i for i in issues if "numbered chain" in i.message]
        self.assertEqual(ambiguity_issues, [])


class TestIncreaseClausesBeforeEachStAround(unittest.TestCase):
    def test_leading_increases_correctly_accounted_for(self):
        # Real bug (mittens, Jul 7 batch, thumb gusset shaping rows): a row
        # with literal increase clauses BEFORE a trailing "sc in each st
        # around to end" used to be checked as if the whole row were just
        # that trailing clause -- confidently wrong, not just unverifiable.
        # in_count=30; "2 sc in each of next 2 sts" (consumes 2, produces
        # 4) + "sc in each of next 2 sts" (consumes 2, produces 2) + "sc in
        # each st around to end" (consumes the remaining 26, produces 26)
        # = 32 total, matching the declared count.
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 30 sc in ring. (30 sc)\n"
            "Row 1: Sc in each st around. (30 sc) (30 sts)\n"
            "Row 2: Place a marker in next 4 sts (gusset sts). 2 sc in each of next 2 sts, sc in each of next "
            "2 sts, sc in each st around to end. (32 sc) (32 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(row2_issues, [])

    def test_wrong_declared_count_with_leading_increases_still_caught(self):
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 30 sc in ring. (30 sc)\n"
            "Row 1: Sc in each st around. (30 sc) (30 sts)\n"
            "Row 2: Place a marker in next 4 sts (gusset sts). 2 sc in each of next 2 sts, sc in each of next "
            "2 sts, sc in each st around to end. (99 sc) (99 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(len(row2_issues), 1)
        self.assertEqual(row2_issues[0].severity, "error")
        self.assertIn("mismatch", row2_issues[0].message)


class TestGussetTransitionRow(unittest.TestCase):
    def _row(self, declared):
        return (
            "Row 2: Sc in each st to the marked gusset sts. Place the next 2 sts on a holder or scrap yarn "
            f"(thumb gusset). Ch 1 to bridge the gap, then sc in each remaining st around, working the last "
            f"1 sts of the round into the 1 ch just made. ({declared} sc) ({declared} sts)\n"
        )

    def test_correct_gusset_math_verifies_cleanly(self):
        # in_count=7 (from Row 1), held=2, bridge=1 -> expected = 7-2+1 = 6.
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 7 sc in ring. (7 sc)\n"
            "Row 1: Sc in each st around. (7 sc) (7 sts)\n" + self._row(6)
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(row2_issues, [])

    def test_wrong_gusset_math_still_caught_as_a_real_error(self):
        # Same setup, but declares 8 sts instead of the correct 6 -- must
        # still be flagged as a real mismatch, not silently waved through
        # just because the row shape is now recognized.
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 7 sc in ring. (7 sc)\n"
            "Row 1: Sc in each st around. (7 sc) (7 sts)\n" + self._row(8)
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(len(row2_issues), 1)
        self.assertEqual(row2_issues[0].severity, "error")
        self.assertIn("mismatch", row2_issues[0].message)


class TestHeldGussetResume(unittest.TestCase):
    def test_resume_row_does_not_inherit_unrelated_prior_count(self):
        # Row 2 (the fingertip closure) declares an unrelated small count
        # (3 sts); Row 3 resumes the held gusset sts from an entirely
        # separate part of the piece -- it must NOT be checked against
        # Row 2's 3 sts (which would be a nonsensical comparison and a
        # false mismatch), only against its own explicit numbers.
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 7 sc in ring. (7 sc)\n"
            "Row 1: *sc2tog, sc in each of next 1 sts; rep from * around. (3 sc) (3 sts)\n"
            "Row 2: Fasten off, leaving a long tail. Thread the tail through the front loop of each remaining "
            "stitch, pull tight to close the fingertip opening, and weave in the end. (3 sts)\n"
            "Row 3: Join yarn in a held gusset st. Sc in each of the 2 held gusset sts, then sc 1 sts evenly "
            "across the bridge chain. Place a stitch marker — work in a continuous spiral from here. (3 sc) "
            "(3 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row3_issues = [i for i in issues if i.location == "Row 3"]
        self.assertEqual(row3_issues, [])

    def test_resume_row_wrong_count_still_caught(self):
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 7 sc in ring. (7 sc)\n"
            "Row 1: *sc2tog, sc in each of next 1 sts; rep from * around. (3 sc) (3 sts)\n"
            "Row 2: Fasten off, leaving a long tail. Thread the tail through the front loop of each remaining "
            "stitch, pull tight to close the fingertip opening, and weave in the end. (3 sts)\n"
            "Row 3: Join yarn in a held gusset st. Sc in each of the 2 held gusset sts, then sc 1 sts evenly "
            "across the bridge chain. Place a stitch marker — work in a continuous spiral from here. (5 sc) "
            "(5 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row3_issues = [i for i in issues if i.location == "Row 3"]
        self.assertEqual(len(row3_issues), 1)
        self.assertEqual(row3_issues[0].severity, "error")


class TestTerminalClosureRow(unittest.TestCase):
    def test_closure_row_matching_count_verifies_cleanly(self):
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 4 sc in ring. (4 sc)\n"
            "Row 1: Sc in each st around. (4 sc) (4 sts)\n"
            "Row 2: Fasten off, leaving a long tail. Thread the tail through the front loop of each remaining "
            "stitch, pull tight to close the opening, and weave in the end. (4 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(row2_issues, [])

    def test_closure_row_mismatched_count_still_caught(self):
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, magic ring. 4 sc in ring. (4 sc)\n"
            "Row 1: Sc in each st around. (4 sc) (4 sts)\n"
            "Row 2: Fasten off, leaving a long tail. Thread the tail through the front loop of each remaining "
            "stitch, pull tight to close the opening, and weave in the end. (6 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(len(row2_issues), 1)
        self.assertEqual(row2_issues[0].severity, "error")


if __name__ == "__main__":
    unittest.main()
