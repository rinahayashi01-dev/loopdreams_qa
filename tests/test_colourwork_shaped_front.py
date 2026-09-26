"""A V-neck cardigan Front carrying a colourwork design narrows at its
centre-front edge, so its V rows are the design with the V's cells cut away,
not finishing rows of a different width (loopdreams, 2026-09-26). This check
used to skip every narrower row and compare a shortened panel against the full
design -- a false FAIL on a correct pattern."""
import copy
import re
import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.models import Pattern

A, B = "#C9A227", "#4F7942"
F = ["BBBBBBBB", "BAAAAAAA", "BAAAAAAA", "BBBBAAAA", "BAAAAAAA", "BAAAAAAA", "BAAAAAAA", "AAAAAAAA"]
DESIGN = [[A if c == "A" else B for c in row] for row in F]

# Real generator output, copied verbatim: loopdreams buildCardiganRows (dc,
# chest 20, body 6 in, 4 x 2 gauge, V-neck, design on the Fronts) through
# applyGarmentPanelColourwork. Each Front narrows 20 -> 9 sts over its V.
FRONT_ROWS = [
    {"row_number": 14, "stitch_count": 20, "instructions": "Foundation: With Colour 1, Ch 22.", "section": "Right Front"},
    {"row_number": 15, "stitch_count": 20, "instructions": "Skip the first 3 chains from the hook (they count as this row's first stitch, so the foundation chain is one shorter than this row's stitch count). Dc in the next chain and in each ch across. The right side (RS) is the side on which the design reads the right way round; clip a marker to it once the design shows. Ch 3, turn.", "section": "Right Front"},
    {"row_number": 16, "stitch_count": 20, "instructions": "With Colour 1, skip first st (the chain already ‘fills’ that slot), 14 dc in next 14 sts, changing to Colour 2 in the last st; 4 dc in next 4 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Right Front"},
    {"row_number": 17, "stitch_count": 20, "instructions": "With Colour 2, skip first st (the chain already ‘fills’ that slot), 4 dc in next 4 sts, changing to Colour 1 in the last st; 14 dc in next 14 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Right Front"},
    {"row_number": 18, "stitch_count": 20, "instructions": "With Colour 1, skip first st (the chain already ‘fills’ that slot), 14 dc in next 14 sts, changing to Colour 2 in the last st; 4 dc in next 4 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Right Front"},
    {"row_number": 19, "stitch_count": 20, "instructions": "With Colour 2, skip first st (the chain already ‘fills’ that slot), 4 dc in next 4 sts, changing to Colour 1 in the last st; 14 dc in next 14 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Right Front"},
    {"row_number": 20, "stitch_count": 20, "instructions": "With Colour 1, skip first st (the chain already ‘fills’ that slot), 14 dc in next 14 sts, changing to Colour 2 in the last st; 4 dc in next 4 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Right Front"},
    {"row_number": 21, "stitch_count": 18, "instructions": "Decrease row: With Colour 2, skip first st (the chain already ‘fills’ that slot), 14 dc in next 14 sts; dc2tog (dc2tog: [yo, insert hook in next st, yo and pull up a loop, yo and pull through 2 loops] twice, yo and pull through all 3 loops — 2 sts become 1, a decrease); dc2tog; at the end of the row, dc in top of the ch-3, changing to Colour 1 in the last st. Ch 3, turn. (18 sts)", "section": "Right Front"},
    {"row_number": 22, "stitch_count": 16, "instructions": "Decrease row: With Colour 1, skip first st (the chain already ‘fills’ that slot), dc2tog; dc2tog; 8 dc in next 8 sts, changing to Colour 2 in the last st; 4 dc in next 4 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn. (16 sts)", "section": "Right Front"},
    {"row_number": 23, "stitch_count": 14, "instructions": "Decrease row: With Colour 2, skip first st (the chain already ‘fills’ that slot), 4 dc in next 4 sts, changing to Colour 1 in the last st; 6 dc in next 6 sts; dc2tog; dc2tog; at the end of the row, dc in top of the ch-3. Ch 3, turn. (14 sts)", "section": "Right Front"},
    {"row_number": 24, "stitch_count": 12, "instructions": "Decrease row: With Colour 1, skip first st (the chain already ‘fills’ that slot), dc2tog; dc2tog; 4 dc in next 4 sts, changing to Colour 2 in the last st; 4 dc in next 4 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn. (12 sts)", "section": "Right Front"},
    {"row_number": 25, "stitch_count": 10, "instructions": "Decrease row: With Colour 2, skip first st (the chain already ‘fills’ that slot), 6 dc in next 6 sts; dc2tog; dc2tog; at the end of the row, dc in top of the ch-3. Ch 3, turn. (10 sts)", "section": "Right Front"},
    {"row_number": 26, "stitch_count": 9, "instructions": "Decrease row: With Colour 2, skip first st (the chain already ‘fills’ that slot), dc2tog; 6 dc in next 6 sts, at the end of the row, dc in top of the ch-3. Fasten off. (9 sts)", "section": "Right Front"},
    {"row_number": 27, "stitch_count": 20, "instructions": "Foundation: With Colour 1, Ch 22.", "section": "Left Front"},
    {"row_number": 28, "stitch_count": 20, "instructions": "Skip the first 3 chains from the hook (they count as this row's first stitch, so the foundation chain is one shorter than this row's stitch count). Dc in the next chain and in each ch across. The right side (RS) is the side on which the design reads the right way round; clip a marker to it once the design shows. Ch 3, turn.", "section": "Left Front"},
    {"row_number": 29, "stitch_count": 20, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Left Front"},
    {"row_number": 30, "stitch_count": 20, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Left Front"},
    {"row_number": 31, "stitch_count": 20, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Left Front"},
    {"row_number": 32, "stitch_count": 20, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Left Front"},
    {"row_number": 33, "stitch_count": 20, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn.", "section": "Left Front"},
    {"row_number": 34, "stitch_count": 18, "instructions": "Decrease row: With Colour 1, skip first st (the chain already ‘fills’ that slot), dc2tog; dc2tog; 14 dc in next 14 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn. (18 sts)", "section": "Left Front"},
    {"row_number": 35, "stitch_count": 16, "instructions": "Decrease row: With Colour 1, skip first st (the chain already ‘fills’ that slot), 12 dc in next 12 sts; dc2tog; dc2tog; at the end of the row, dc in top of the ch-3. Ch 3, turn. (16 sts)", "section": "Left Front"},
    {"row_number": 36, "stitch_count": 14, "instructions": "Decrease row: With Colour 1, skip first st (the chain already ‘fills’ that slot), dc2tog; dc2tog; 10 dc in next 10 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn. (14 sts)", "section": "Left Front"},
    {"row_number": 37, "stitch_count": 12, "instructions": "Decrease row: With Colour 1, skip first st (the chain already ‘fills’ that slot), 8 dc in next 8 sts; dc2tog; dc2tog; at the end of the row, dc in top of the ch-3, changing to Colour 2 in the last st. Ch 3, turn. (12 sts)", "section": "Left Front"},
    {"row_number": 38, "stitch_count": 10, "instructions": "Decrease row: With Colour 2, skip first st (the chain already ‘fills’ that slot), dc2tog; dc2tog; 6 dc in next 6 sts, at the end of the row, dc in top of the ch-3. Ch 3, turn. (10 sts)", "section": "Left Front"},
    {"row_number": 39, "stitch_count": 9, "instructions": "Decrease row: With Colour 2, skip first st (the chain already ‘fills’ that slot), 6 dc in next 6 sts; dc2tog; at the end of the row, dc in top of the ch-3. Fasten off. (9 sts)", "section": "Left Front"}
]


def _pattern(rows):
    p = Pattern()
    p.design_grid = DESIGN
    p.design_palette = [A, B]
    p.design_rows = rows
    return p


class TestShapedFront(unittest.TestCase):
    def test_real_v_neck_front_output_passes(self):
        self.assertEqual(co.check(_pattern(FRONT_ROWS)), [])

    def test_a_wrong_colour_inside_the_v_is_caught(self):
        # Proves the V rows are compared, not skipped: flip the colour a
        # decrease row changes to.
        # Meaningful only against a clean baseline: a checker that already
        # rejects the correct pattern "catches" every mutation for free.
        self.assertEqual(co.check(_pattern(FRONT_ROWS)), [])
        caught = 0
        v_rows = [i for i, r in enumerate(FRONT_ROWS) if r["instructions"].startswith("Decrease row") and "changing to" in r["instructions"]]
        self.assertTrue(v_rows)
        for i in v_rows:
            rows = copy.deepcopy(FRONT_ROWS)
            t = rows[i]["instructions"]
            m = re.search(r"changing to Colour (\d)", t)
            rows[i]["instructions"] = t[:m.start()] + f"changing to Colour {'2' if m.group(1) == '1' else '1'}" + t[m.end():]
            if any(x.severity == "error" for x in co.check(_pattern(rows))):
                caught += 1
        self.assertEqual(caught, len(v_rows))

    def test_the_v_is_cut_from_the_centre_front_edge(self):
        # Right Front: the centre-front cells end even working rows and start
        # odd ones; the Left Front is the other way round.
        grid = [list("abcd"), list("abcd")]
        self.assertEqual(co._shape_expectation(grid, [1, 1], "Right Front"), [list("abc"), list("bcd")])
        self.assertEqual(co._shape_expectation(grid, [1, 1], "Left Front"), [list("bcd"), list("abc")])
        self.assertEqual(co._shape_expectation(grid, [0, 2], "Right Front"), [list("abcd"), list("cd")])

    def test_a_decrease_is_one_position_and_its_how_to_adds_none(self):
        text = ("Decrease row: With Colour 2, skip first st (the chain already fills that slot), "
                "2 dc in next 2 sts; dc2tog (dc2tog: [yo, insert hook in next st, yo and pull up a loop, "
                "yo and pull through 2 loops] twice, yo and pull through all 3 loops); at the end of the row, "
                "dc in top of the ch-3. Ch 3, turn. (5 sts)")
        colours, _ = co._row_colours(text, 5, "Colour 2")
        self.assertEqual(colours, ["Colour 2"] * 5)
        # And without the how-to, the bare decrease alone must supply that
        # position (before, the how-to's "insert hook in next st" was being
        # counted in its place).
        bare = re.sub(r" \(dc2tog: [^)]*\)", "", text)
        colours, _ = co._row_colours(bare, 5, "Colour 2")
        self.assertEqual(colours, ["Colour 2"] * 5)


if __name__ == "__main__":
    unittest.main()
