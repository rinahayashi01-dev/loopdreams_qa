import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import completeness

MATERIALS_BLOCK = """MATERIALS
Gauge: 20 sc x 10 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
"""


def _pattern(pattern_steps: str, abbreviations: str = "ch = chain, sc = single crochet"):
    raw = (
        "Test Piece\n"
        + MATERIALS_BLOCK
        + "ABBREVIATIONS\n"
        + abbreviations + "\n"
        + "PATTERN STEPS\n"
        + pattern_steps
    )
    return parse(raw)


def _no_finishing_issues(pattern):
    return [i for i in completeness.check(pattern) if "No Finishing" in i.message]


class TestOvalFoundationNeverTurnsException(unittest.TestCase):
    # Real sample: Amigurumi Egg (Jul 17 batch), buildOvalRoundRows.
    # foundation_is_magic_ring is False here (the oval starts from a real
    # chain, not "magic ring"), but the construction is still worked as a
    # continuous spiral with no seams to join -- the original exception
    # only recognized magic-ring foundations, so this pattern always
    # false-failed "No Finishing/assembly section found" despite already
    # closing cleanly.
    def test_oval_chain_foundation_with_closure_row_is_not_flagged(self):
        pattern = _pattern(
            "Row 1: Ch 5. Sc in 2nd ch from hook and each of next 2 chs, 3 sc in last ch, working on "
            "the opposite side of the foundation chain: sc in each of next 2 chs, 3 sc in last ch. "
            "Do not join or turn, work in continuous rounds. (12 sc) (12 sts)\n"
            "Row 2: Sc in each st around. (12 sc) (12 sts)\n"
            "Row 3: Sc in each st around. (12 sc) (12 sts)\n"
            "Row 4: Finish stuffing firmly. Fasten off, leaving a long tail. Thread the tail through "
            "the front loop of each remaining stitch, pull tight to close the opening, and weave in "
            "the end. (12 sts)\n"
        )
        self.assertFalse(pattern.foundation_is_magic_ring)
        self.assertEqual(_no_finishing_issues(pattern), [])

    def test_oval_chain_foundation_without_a_closure_clause_is_still_flagged(self):
        # Guard against the exception swallowing every no-Finishing-section
        # case outright -- it should still require an actual closure/
        # fasten-off clause on the last row, same as the magic-ring path.
        pattern = _pattern(
            "Row 1: Ch 5. Sc in 2nd ch from hook and each of next 2 chs, 3 sc in last ch, working on "
            "the opposite side of the foundation chain: sc in each of next 2 chs, 3 sc in last ch. "
            "Do not join or turn, work in continuous rounds. (12 sc) (12 sts)\n"
            "Row 2: Sc in each st around. (12 sc) (12 sts)\n"
        )
        self.assertNotEqual(_no_finishing_issues(pattern), [])


class TestFlatPanelStillRequiresFinishing(unittest.TestCase):
    # Regression guard for the fix above: a flat panel (Dishcloth-shaped --
    # every row but the last turns) with no Finishing section must still be
    # flagged, even though its own last row now also ends in a real
    # "Fasten off, weave in ends." closure clause (see generate-pattern's
    # buildGenericFlatRows fix, Jul 17). Broadening the exception to "last
    # row has a closure clause" alone would have wrongly exempted this too --
    # the "never turns anywhere in the body" check is what keeps this
    # correctly flagged.
    def test_flat_panel_with_plain_fasten_off_last_row_is_still_flagged(self):
        pattern = _pattern(
            "Foundation: Ch 48, turn. (47 sts)\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (47 sts)\n"
            "Row 2: Sc in each st across, ch 1, turn. (47 sts)\n"
            "Row 3: Sc in each st across. Fasten off, weave in ends. (47 sts)\n"
        )
        self.assertNotEqual(_no_finishing_issues(pattern), [])


if __name__ == "__main__":
    unittest.main()
