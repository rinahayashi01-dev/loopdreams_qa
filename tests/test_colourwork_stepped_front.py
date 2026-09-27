"""A textured-stitch (sedge) V-neck Front carrying a colourwork design: the V
is stepped a whole repeat at a time ("..., sc in next st, leaving the last 3 sts
unworked"), and each narrowed row is the design at full width, cut at the
centre-front, then resampled to the row's cluster columns in DESIGN order
before odd rows are reversed (loopdreams, 2026-09-27)."""
import copy
import re
import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.models import Pattern

A, B = "#C9A227", "#4F7942"
F = ["BBBBBBBB", "BAAAAAAA", "BAAAAAAA", "BBBBAAAA", "BAAAAAAA", "BAAAAAAA", "BAAAAAAA", "AAAAAAAA"]
DESIGN = [[A if c == "A" else B for c in row] for row in F]

# Real generator output, verbatim: loopdreams buildCardiganRows (sedge, chest
# 20, body 10 in, 4 x 2.66 gauge, V-neck, design on the Fronts) through
# applyGarmentPanelColourwork. Each Front steps 21 -> 12 sts in 3 steps.
FRONT_ROWS = [
    {"row_number": 29, "stitch_count": 21, "instructions": "Foundation: With Colour 1, Ch 21, turn.", "section": "Right Front"},
    {"row_number": 30, "stitch_count": 21, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). Hdc in the next chain, dc in the same chain. *skip 2 chains, (sc, hdc, dc) in next chain (sedge made); rep from * to the last chain, 5 more times, sc in last chain. The right side (RS) is the side on which this row ends at the right-hand edge when the foundation is at the bottom; clip a marker to it. This Front carries the left half of the design as pictured and the design reads the right way round on the RS. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 31, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 32, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 33, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, changing to Colour 2 in the last st; skip 2 sts, (sc, hdc, dc) in next st (sedge made); sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 34, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; skip 2 sts, (sc, hdc, dc) in next st (sedge made), changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 35, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, changing to Colour 2 in the last st; skip 2 sts, (sc, hdc, dc) in next st (sedge made); sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 36, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; skip 2 sts, (sc, hdc, dc) in next st (sedge made), changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 37, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, changing to Colour 2 in the last st; skip 2 sts, (sc, hdc, dc) in next st (sedge made); sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 38, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; skip 2 sts, (sc, hdc, dc) in next st (sedge made), changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 39, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, changing to Colour 2 in the last st; skip 2 sts, (sc, hdc, dc) in next st (sedge made); sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 40, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; skip 2 sts, (sc, hdc, dc) in next st (sedge made), changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 41, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, changing to Colour 2 in the last st; skip 2 sts, (sc, hdc, dc) in next st (sedge made); sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 42, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; skip 2 sts, (sc, hdc, dc) in next st (sedge made), changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 43, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 5 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 44, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 45, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 46, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; skip 2 sts, (sc, hdc, dc) in next st (sedge made), changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 47, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, changing to Colour 2 in the last st; skip 2 sts, (sc, hdc, dc) in next st (sedge made); sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 48, "stitch_count": 21, "instructions": "With Colour 2, hdc in first st, dc in next st; skip 2 sts, (sc, hdc, dc) in next st (sedge made), changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times; sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 49, "stitch_count": 21, "instructions": "With Colour 1, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, changing to Colour 2 in the last st; skip 2 sts, (sc, hdc, dc) in next st (sedge made); sc in last st. Ch 1, turn.", "section": "Right Front"},
    {"row_number": 50, "stitch_count": 18, "instructions": "Decrease row: With Colour 2, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 1 more time, changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 2 more times; sc in next st, leaving the last 3 sts unworked. Ch 1, turn. (18 sts)", "section": "Right Front"},
    {"row_number": 51, "stitch_count": 18, "instructions": "With Colour 1, hdc in first st (the sc you just made — the unworked sts below stay as they are), dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 2 more times, changing to Colour 2 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 1 more time; sc in last st. Ch 1, turn. (18 sts)", "section": "Right Front"},
    {"row_number": 52, "stitch_count": 15, "instructions": "Decrease row: With Colour 2, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 1 more time, changing to Colour 1 in the last st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 1 more time; sc in next st, leaving the last 3 sts unworked. Ch 1, turn. (15 sts)", "section": "Right Front"},
    {"row_number": 53, "stitch_count": 15, "instructions": "With Colour 2, hdc in first st (the sc you just made — the unworked sts below stay as they are), dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 3 more times; sc in last st. Ch 1, turn. (15 sts)", "section": "Right Front"},
    {"row_number": 54, "stitch_count": 12, "instructions": "Decrease row: Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 2 more times, sc in next st, leaving the last 3 sts unworked. Ch 1, turn. (12 sts)", "section": "Right Front"},
    {"row_number": 55, "stitch_count": 12, "instructions": "Hdc in first st (the sc you just made — the unworked sts below stay as they are), dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 2 more times, sc in last st. Ch 1, turn. (12 sts)", "section": "Right Front"},
    {"row_number": 56, "stitch_count": 12, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 2 more times, sc in last st. Fasten off. (12 sts)", "section": "Right Front"},
    {"row_number": 57, "stitch_count": 21, "instructions": "Foundation: With Colour 1, Ch 21, turn.", "section": "Left Front"},
    {"row_number": 58, "stitch_count": 21, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). Hdc in the next chain, dc in the same chain. *skip 2 chains, (sc, hdc, dc) in next chain (sedge made); rep from * to the last chain, 5 more times, sc in last chain. The right side (RS) is the side on which this row ends at the right-hand edge when the foundation is at the bottom; clip a marker to it. This Front carries the right half of the design as pictured and the design reads the right way round on the RS. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 59, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 60, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 61, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 62, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 63, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 64, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 65, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 66, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 67, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 68, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 69, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 70, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 71, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 72, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 73, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 74, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 75, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 76, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 77, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn.", "section": "Left Front"},
    {"row_number": 78, "stitch_count": 21, "instructions": "Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 5 more times, sc in last st. Ch 1, turn. (21 sts)", "section": "Left Front"},
    {"row_number": 79, "stitch_count": 18, "instructions": "Decrease row: Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 4 more times, sc in next st, leaving the last 3 sts unworked. Ch 1, turn. (18 sts)", "section": "Left Front"},
    {"row_number": 80, "stitch_count": 18, "instructions": "Hdc in first st (the sc you just made — the unworked sts below stay as they are), dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 4 more times, sc in last st. Ch 1, turn. (18 sts)", "section": "Left Front"},
    {"row_number": 81, "stitch_count": 15, "instructions": "Decrease row: With Colour 2, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 3 more times; sc in next st, leaving the last 3 sts unworked. Ch 1, turn. (15 sts)", "section": "Left Front"},
    {"row_number": 82, "stitch_count": 15, "instructions": "Hdc in first st (the sc you just made — the unworked sts below stay as they are), dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 3 more times, sc in last st. Ch 1, turn. (15 sts)", "section": "Left Front"},
    {"row_number": 83, "stitch_count": 12, "instructions": "Decrease row: Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 2 more times, sc in next st, leaving the last 3 sts unworked. Ch 1, turn. (12 sts)", "section": "Left Front"},
    {"row_number": 84, "stitch_count": 12, "instructions": "Hdc in first st (the sc you just made — the unworked sts below stay as they are), dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * to the last st, 2 more times, sc in last st. Fasten off. (12 sts)", "section": "Left Front"}
]


def _pattern(rows):
    p = Pattern()
    p.design_grid = DESIGN
    p.design_palette = [A, B]
    p.design_rows = rows
    return p


class TestSteppedSedgeFront(unittest.TestCase):
    def test_real_stepped_sedge_front_passes(self):
        self.assertEqual(co.check(_pattern(FRONT_ROWS)), [])

    def test_a_wrong_colour_inside_the_v_is_caught(self):
        self.assertEqual(co.check(_pattern(FRONT_ROWS)), [])
        full = {s: max(r["stitch_count"] for r in FRONT_ROWS if r["section"] == s) for s in ("Right Front", "Left Front")}
        v_rows = [i for i, r in enumerate(FRONT_ROWS)
                  if r["stitch_count"] < full[r["section"]] and "changing to" in r["instructions"]]
        self.assertTrue(v_rows)
        for i in v_rows:
            rows = copy.deepcopy(FRONT_ROWS)
            t = rows[i]["instructions"]
            m = re.search(r"changing to Colour (\d)", t)
            rows[i]["instructions"] = t[:m.start()] + f"changing to Colour {'2' if m.group(1) == '1' else '1'}" + t[m.end():]
            self.assertTrue(any(x.severity == "error" for x in co.check(_pattern(rows))), f"row {i}")

    def test_a_step_row_reads_with_its_closer_and_leave_clause(self):
        text = ("Decrease row: With Colour 2, hdc in first st, dc in next st; *skip 2 sts, (sc, hdc, dc) in next st "
                "(sedge made); rep from * 3 more times; sc in next st, leaving the last 3 sts unworked. Ch 1, turn. (15 sts)")
        colours, _ = co._row_colours(text, 15, "Colour 2")
        self.assertEqual(colours, ["Colour 2"] * 6)   # opener + 4 clusters + closer = 15 // 3 + 1

    def test_the_anchor_after_a_step_is_not_a_stitch(self):
        text = ("With Colour 1, hdc in first st (the sc you just made — the unworked sts below stay as they are), "
                "dc in next st; *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * 3 more times; "
                "sc in last st. Ch 1, turn. (15 sts)")
        colours, _ = co._row_colours(text, 15, "Colour 1")
        self.assertEqual(colours, ["Colour 1"] * 6)


if __name__ == "__main__":
    unittest.main()
