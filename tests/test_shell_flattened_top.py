"""Shell's Flattened top in colour (loopdreams #884, 2026-11-23).

The straight-edge last row of a shell piece keeps the half-shell row's cluster
resolution: one colour for the opening position, one per "hdc, sc, sc, sc, hdc"
group and one per dc, so 1 + 2 x shells positions. It names no "(shell made)",
so it used to be read stitch by stitch and a coloured one with blocks smaller
than a shell FAILed against the finer resample. Fixtures are real output of
buildShellStitchColourRows(w, h, 4, 2, grid, [A, B], true), copied verbatim.
"""
import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.models import Pattern

A, B = "#C9A227", "#4F7942"
F = ["BBBBBBBB", "BAAAAAAA", "BAAAAAAA", "BBBBAAAA", "BAAAAAAA", "BAAAAAAA", "BAAAAAAA", "AAAAAAAA"]
F_DESIGN = [[A if c == "A" else B for c in row] for row in F]
CHECKER = [[A if (r + c) % 2 == 0 else B for c in range(8)] for r in range(8)]


def _pattern(rows, grid):
    p = Pattern()
    p.design_grid = grid
    p.design_palette = [A, B]
    p.design_rows = rows
    return p


def _errors(rows, grid):
    return [i for i in co.check(_pattern(rows, grid)) if i.severity == "error"]


# 6.25 x 2.5 in, checker: the top's ch 3 counts ("With Colour 1, skip first st
# (the chain already 'fills' that slot as a dc); ...").
CHECKER_COUNTED = [
    {"row_number": 1, "stitch_count": 25, "instructions": "Foundation: With Colour 1, Ch 26, turn."},
    {"row_number": 2, "stitch_count": 25, "instructions": "Skip the first chain from the hook (it doesn't count as a stitch). With Colour 1, 4 sc in next 4 chs, changing to Colour 2 in the last st; 3 sc in next 3 chs, changing to Colour 1 in the last st; 3 sc in next 3 chs, changing to Colour 2 in the last st; 3 sc in next 3 chs, changing to Colour 1 in the last st; 3 sc in next 3 chs, changing to Colour 2 in the last st; 3 sc in next 3 chs, changing to Colour 1 in the last st; 3 sc in next 3 chs, changing to Colour 2 in the last st; 3 sc in next 3 chs, changing to Colour 1 in the last st. Ch 1, turn."},
    {"row_number": 3, "stitch_count": 25, "instructions": "With Colour 1, sc in first st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st, changing to Colour 1 in the last st (before you start that st, cut Colour 1 where it hangs, leaving a 6 in / 15 cm tail; make the last yarn-over with the ball end, leaving a 6 in / 15 cm tail). Ch 3, turn."},
    {"row_number": 4, "stitch_count": 25, "instructions": "With Colour 1, 2 dc in first sc (turning ch-3 counts as first dc; half shell made); sc in centre dc of next shell, changing to Colour 2 in the last st; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of next shell, changing to Colour 2 in the last st; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of next shell, changing to Colour 2 in the last st; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of last shell, changing to Colour 2 in the last st; 3 dc in last sc (half shell made), changing to Colour 1 in the last st (on the final yarn-over of the 3rd dc). Ch 1, turn."},
    {"row_number": 5, "stitch_count": 25, "instructions": "With Colour 1, sc in first st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st, changing to Colour 1 in the last st (before you start that st, cut Colour 1 where it hangs, leaving a 6 in / 15 cm tail; make the last yarn-over with the ball end, leaving a 6 in / 15 cm tail). Ch 3, turn."},
    {"row_number": 6, "stitch_count": 25, "instructions": "With Colour 1, 2 dc in first sc (turning ch-3 counts as first dc; half shell made); sc in centre dc of next shell, changing to Colour 2 in the last st; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of next shell, changing to Colour 2 in the last st; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of next shell, changing to Colour 2 in the last st; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of last shell, changing to Colour 2 in the last st; 3 dc in last sc (half shell made), changing to Colour 1 in the last st (on the final yarn-over of the 3rd dc). Ch 1, turn."},
    {"row_number": 7, "stitch_count": 25, "instructions": "With Colour 1, sc in first st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st, changing to Colour 2 in the last st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st, changing to Colour 1 in the last st (before you start that st, cut Colour 1 where it hangs, leaving a 6 in / 15 cm tail; make the last yarn-over with the ball end, leaving a 6 in / 15 cm tail). Ch 3, turn."},
    {"row_number": 8, "stitch_count": 25, "instructions": "With Colour 1, skip first st (the chain already ‘fills’ that slot as a dc); hdc in next st, sc in next st, sc in next st, sc in next st, hdc in next st, changing to Colour 2 in the last st; dc in next st, changing to Colour 1 in the last st; hdc in next st, sc in next st, sc in next st, sc in next st, hdc in next st, changing to Colour 2 in the last st; dc in next st, changing to Colour 1 in the last st; hdc in next st, sc in next st, sc in next st, sc in next st, hdc in next st, changing to Colour 2 in the last st; dc in next st, changing to Colour 1 in the last st; hdc in next st, sc in next st, sc in next st, sc in next st, hdc in next st, changing to Colour 2 in the last st; dc in next st. Fasten off, weave in ends."},
]

# 3.25 x 2.5 in, checker: the colour changes straight after the first dc, so the
# top works it and says the ch-3 doesn't count.
CHECKER_FALLBACK = [
    {"row_number": 1, "stitch_count": 13, "instructions": "Foundation: With Colour 1, Ch 14, turn."},
    {"row_number": 2, "stitch_count": 13, "instructions": "Skip the first chain from the hook (it doesn't count as a stitch). With Colour 1, 2 sc in next 2 chs, changing to Colour 2 in the last st; 2 sc in next 2 chs, changing to Colour 1 in the last st; 1 sc in next 1 ch, changing to Colour 2 in the last st; 2 sc in next 2 chs, changing to Colour 1 in the last st; 2 sc in next 2 chs, changing to Colour 2 in the last st; 1 sc in next 1 ch, changing to Colour 1 in the last st; 2 sc in next 2 chs, changing to Colour 2 in the last st; 1 sc in next 1 ch. Ch 1, turn."},
    {"row_number": 3, "stitch_count": 13, "instructions": "With Colour 2, sc in first st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st, changing to Colour 1 in the last st. Ch 3, turn."},
    {"row_number": 4, "stitch_count": 13, "instructions": "With Colour 1, 2 dc in first sc (turning ch-3 counts as first dc; half shell made), changing to Colour 2 in the last st; sc in centre dc of next shell; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of last shell; 3 dc in last sc (half shell made), changing to Colour 2 in the last st (before you start that st, cut Colour 2 where it hangs, leaving a 6 in / 15 cm tail; make the last yarn-over with the ball end, leaving a 6 in / 15 cm tail). Ch 1, turn."},
    {"row_number": 5, "stitch_count": 13, "instructions": "With Colour 2, sc in first st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st, changing to Colour 1 in the last st. Ch 3, turn."},
    {"row_number": 6, "stitch_count": 13, "instructions": "With Colour 1, 2 dc in first sc (turning ch-3 counts as first dc; half shell made), changing to Colour 2 in the last st; sc in centre dc of next shell; 5 dc in next sc, changing to Colour 1 in the last st; sc in centre dc of last shell; 3 dc in last sc (half shell made), changing to Colour 2 in the last st (before you start that st, cut Colour 2 where it hangs, leaving a 6 in / 15 cm tail; make the last yarn-over with the ball end, leaving a 6 in / 15 cm tail). Ch 1, turn."},
    {"row_number": 7, "stitch_count": 13, "instructions": "With Colour 2, sc in first st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 1 in the last st; skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st, changing to Colour 1 in the last st. Ch 3, turn."},
    {"row_number": 8, "stitch_count": 13, "instructions": "With Colour 1, dc in first st (the ch-3 does not count as a st on this row), changing to Colour 2 in the last st; hdc in next st, sc in next st, sc in next st, sc in next st, hdc in next st; dc in next st, changing to Colour 1 in the last st; hdc in next st, sc in next st, sc in next st, sc in next st, hdc in next st; dc in next st. Fasten off, weave in ends."},
]

# 3.25 x 2.5 in, the F design: a one-colour top after a cut-colour note, still
# written with its repeat bracket.
F_CUT_NOTE = [
    {"row_number": 1, "stitch_count": 13, "instructions": "Foundation: With Colour 2, Ch 14, turn."},
    {"row_number": 2, "stitch_count": 13, "instructions": "Skip the first chain from the hook (it doesn't count as a stitch). With Colour 2, 2 sc in next 2 chs, changing to Colour 1 in the last st; 11 sc in next 11 chs. Ch 1, turn."},
    {"row_number": 3, "stitch_count": 13, "instructions": "With Colour 1, sc in first st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st. Ch 3, turn."},
    {"row_number": 4, "stitch_count": 13, "instructions": "With Colour 2, 2 dc in first sc (turning ch-3 counts as first dc; half shell made), changing to Colour 1 in the last st; sc in centre dc of next shell; 5 dc in next sc; sc in centre dc of last shell; 3 dc in last sc (half shell made). Ch 1, turn."},
    {"row_number": 5, "stitch_count": 13, "instructions": "With Colour 1, sc in first st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st. Ch 3, turn."},
    {"row_number": 6, "stitch_count": 13, "instructions": "With Colour 2, 2 dc in first sc (turning ch-3 counts as first dc; half shell made), changing to Colour 1 in the last st; sc in centre dc of next shell; 5 dc in next sc; sc in centre dc of last shell; 3 dc in last sc (half shell made). Ch 1, turn."},
    {"row_number": 7, "stitch_count": 13, "instructions": "With Colour 1, sc in first st; skip 2 sts, 5 dc in next st (shell made); skip 2 sts, sc in next st; skip 2 sts, 5 dc in next st (shell made), changing to Colour 2 in the last st; skip 2 sts, sc in next st. Ch 3, turn."},
    {"row_number": 8, "stitch_count": 13, "instructions": "With Colour 2 (cut Colour 1 — it is not used again on this piece), skip first st (the chain already ‘fills’ that slot as a dc), *hdc in next st, sc in next st, sc in next st, sc in next st, hdc in next st, dc in next st; rep from * 1 more time. Fasten off, weave in ends."},
]


class ShellFlattenedTopColoursTest(unittest.TestCase):
    def test_faithful_tops_report_nothing(self):
        self.assertEqual(co.check(_pattern(CHECKER_COUNTED, CHECKER)), [])
        self.assertEqual(co.check(_pattern(CHECKER_FALLBACK, CHECKER)), [])
        self.assertEqual(co.check(_pattern(F_CUT_NOTE, F_DESIGN)), [])

    def test_the_top_is_read_at_cluster_resolution(self):
        top = CHECKER_COUNTED[-1]
        colours, _ = co._row_colours(top["instructions"], top["stitch_count"], "Colour 1")
        self.assertIsNotNone(colours, "a coloured Flattened top should be readable")
        self.assertEqual(len(colours), 1 + 2 * round((top["stitch_count"] - 1) / 6))

    def test_a_counted_chain_is_the_colour_the_row_below_ended_in(self):
        # Whatever "With" the top opens with, its ch 3 was made at the end of
        # the row below.
        top = CHECKER_COUNTED[-1]["instructions"]
        colours, _ = co._row_colours(top, CHECKER_COUNTED[-1]["stitch_count"], "Colour 2")
        self.assertEqual(colours[0], "Colour 2")

    def test_a_one_colour_top_with_a_repeat_bracket_is_read(self):
        top = F_CUT_NOTE[-1]
        colours, _ = co._row_colours(top["instructions"], top["stitch_count"], "Colour 2")
        self.assertEqual(colours, ["Colour 2"] * 5)

    def test_a_wrong_colour_on_the_top_is_caught(self):
        broken = [dict(r) for r in CHECKER_FALLBACK]
        broken[-1]["instructions"] = broken[-1]["instructions"].replace("Colour 1", "Colour X").replace(
            "Colour 2", "Colour 1").replace("Colour X", "Colour 2")
        self.assertTrue(_errors(broken, CHECKER), "a top worked in swapped colours should FAIL")

    def test_a_counted_chain_left_in_the_old_colour_is_caught(self):
        # Drop the row below's final change: the ch 3 is then the old colour.
        broken = [dict(r) for r in CHECKER_COUNTED]
        below = broken[-2]["instructions"]
        at = below.rfind(", changing to ")
        self.assertGreater(at, 0)
        broken[-2]["instructions"] = below[:at] + ". Ch 3, turn."
        self.assertTrue(_errors(broken, CHECKER), "a counted ch 3 in the old colour should FAIL")


if __name__ == "__main__":
    unittest.main()
