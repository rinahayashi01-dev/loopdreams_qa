"""Rows that state their one colour with a bracketed note (loopdreams #837).

#837 added two row shapes, both on rows that are one colour all the way
across:

- The first solid row after a design's last change opens
  "With Colour 2 (cut Colour 1 — it is not used again on this piece), ...".
- A far-yarn change moved onto the previous row's last st:
  "... changing to Colour 2 in the last st (before you start that st, cut
  Colour 2 where it hangs, ...). Ch 1, turn."

On a waffle or bobble row the repeat is outside the run grammar, so both were
holes. On the waffle throw every row after the hole then read as naming no
colour, which is an error (batch-test went PASS -> FAIL on main 2026-11-10).
"""
import unittest

from loopdreams_qa.checks import colourwork_orientation as co

C1, C2 = "Colour 1", "Colour 2"

WAFFLE_CUT_ROW = (
    "With Colour 2 (cut Colour 1 — it is not used again on this piece), skip first st "
    "(the chain already ‘fills’ that slot), *dc in next st, fpdc around next 2 sts; rep from * "
    "3 more times, dc in next st, at the end of the row, dc in top of the ch-2. "
    "Ch 2 (counts as first dc), turn."
)
BOBBLE_FAR_CHANGE_ROW = (
    "Sc in each of first 2 sts, *bobble in next st ([yo, insert hook, yo, pull up loop, yo, "
    "pull through 2 loops] 5 times in same st, yo, pull through all 6 loops), sc in next st; "
    "rep from * to last 2 sts, 2 more times, sc in each of last 2 sts, changing to Colour 2 in "
    "the last st (before you start that st, cut Colour 2 where it hangs, leaving a 6 in tail; "
    "make the last yarn-over with the ball end, leaving a 6 in tail). Ch 1, turn."
)


class TestColourNoteRows(unittest.TestCase):
    def test_a_cut_note_after_the_opening_colour_is_read(self):
        # 15 sts: the counted ch-2 (made before "With", so in the colour on
        # the hook), then 14 in Colour 2.
        colours, ending = co._row_colours(WAFFLE_CUT_ROW, 15, C1)
        self.assertEqual(colours, [C1] + [C2] * 14)
        self.assertEqual(ending, C2)

    def test_a_far_yarn_note_after_the_closing_change_is_read(self):
        colours, ending = co._row_colours(BOBBLE_FAR_CHANGE_ROW, 10, C1)
        self.assertEqual(colours, [C1] * 10)
        self.assertEqual(ending, C2)

    def test_the_units_form_of_the_note_is_read(self):
        row = BOBBLE_FAR_CHANGE_ROW.replace("6 in tail", "6 in / 15 cm tail")
        self.assertEqual(co._row_colours(row, 10, C1), ([C1] * 10, C2))

    def test_a_second_colour_inside_the_row_is_not_flattened(self):
        # A mid-row change is not a one-colour row, so the shortcut must not
        # paint it solid; it is left to the run grammar (here, unreadable).
        row = WAFFLE_CUT_ROW.replace("dc in next st, at the end", "dc in next st, changing to Colour 1 in the last st; dc in next st, at the end")
        colours, _ = co._row_colours(row, 15, C1)
        self.assertNotEqual(colours, [C1] + [C2] * 14)

    def test_the_striped_panel_reader_accepts_the_notes(self):
        self.assertTrue(co._RE_LEAD_WITH.match("With Colour 2 (cut Colour 1 — it is not used again on this piece), sc in each st across."))
        self.assertTrue(co._RE_END_CHANGE.search("Sc in each st across, changing to Colour 2 in the last st (before you start that st, cut Colour 2 where it hangs). Ch 1, turn."))


if __name__ == "__main__":
    unittest.main()
