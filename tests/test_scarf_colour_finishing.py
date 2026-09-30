import copy
import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.models import Pattern


A, B = "#C9A227", "#4F7942"
# Two-row stripes, bottom row last: worked A, B, B, A from the foundation up.
STRIPES = [[A] * 8, [B] * 8, [B] * 8, [A] * 8]


def _pattern(rows, grid=STRIPES):
    p = Pattern()
    p.design_grid = grid
    p.design_palette = [A, B]
    p.design_rows = rows
    return p


def _errors(rows):
    return [i for i in co.check(_pattern(rows)) if i.severity == "error"]


# Real generator output (buildScarfColourRows over buildGenericFlatColourRows,
# dc, 2 in wide, 7 in long with 1x1 ribbing and an sc border), copied verbatim.
# Ribbing is carved out of the length, so the body is 2 in: 4 rows. Every row
# after it is finishing: two ribbing panels, whose rows after the first carry
# no label, and the border round.
RIBBED_ROWS = [
    {"row_number": 1, "stitch_count": 8, "instructions": "With Colour 1, Ch 10, turn."},
    {"row_number": 2, "stitch_count": 8, "instructions": "Skip the first 3 chains from the hook (they count as this row's first stitch, so the foundation chain is one shorter than this row's stitch count). With Colour 1, 7 dc in next 7 chs, changing to Colour 2 in the last st. Ch 3, turn."},
    {"row_number": 3, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 4, "stitch_count": 8, "instructions": "With Colour 2, skip first st (the chain already ‘fills’ that slot), 6 dc in next 6 sts, at the end of the row, dc in top of the ch-3, changing to Colour 1 in the last st. Ch 3, turn."},
    {"row_number": 5, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Fasten off, weave in ends. Body measures approximately 2 in."},
    {"row_number": 6, "stitch_count": 8, "instructions": "Ribbing (Panel 1): With RS facing, join Colour 1 to the first stitch of the foundation chain. Sc in each st evenly across, ending at the opposite corner. Ch 12, turn."},
    {"row_number": 7, "stitch_count": 10, "instructions": "Skip the first 2 chains from the hook (they don't count as a stitch). Hdc in the next chain and in each ch across. Sl st in next 2 sts of the sc row. Ch 2, turn."},
    {"row_number": 8, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Ch 2, turn."},
    {"row_number": 9, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Sl st in next 2 sts of the sc row. Ch 2, turn."},
    {"row_number": 10, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Ch 2, turn."},
    {"row_number": 11, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Sl st in next 2 sts of the sc row. Ch 2, turn."},
    {"row_number": 12, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Ch 2, turn."},
    {"row_number": 13, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Sl st in next 2 sts of the sc row. Fasten off."},
    {"row_number": 14, "stitch_count": 8, "instructions": "Ribbing (Panel 2): With RS facing, join Colour 1 to the last stitch of the final row. Sc in each st evenly across, ending at the opposite corner. Ch 12, turn."},
    {"row_number": 15, "stitch_count": 10, "instructions": "Skip the first 2 chains from the hook (they don't count as a stitch). Hdc in the next chain and in each ch across. Sl st in next 2 sts of the sc row. Ch 2, turn."},
    {"row_number": 16, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Ch 2, turn."},
    {"row_number": 17, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Sl st in next 2 sts of the sc row. Ch 2, turn."},
    {"row_number": 18, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Ch 2, turn."},
    {"row_number": 19, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Sl st in next 2 sts of the sc row. Ch 2, turn."},
    {"row_number": 20, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Ch 2, turn."},
    {"row_number": 21, "stitch_count": 10, "instructions": "*Fphdc around next st, bphdc around next st; rep from * across. Sl st in next 2 sts of the sc row. Fasten off."},
    {"row_number": 22, "stitch_count": 64, "instructions": "Border: With RS facing, join Colour 1 at either end of the row you just finished — that row is the stitch edge, not row-ends. Ch 1, 2 sc in same corner st (first corner begun), sc in each st across flat edge, 3 sc in corner, working 1 sc per row-end along side edge, 3 sc in corner, sc in each st across flat edge, 3 sc in corner, working 1 sc per row-end along side edge, sc in same corner st as the beginning (first corner completed). Join with sl st to first sc. Fasten off. (64 sts)"},
]

# Same design at 7 in with fringe: the body is the whole length, resampled to
# 14 rows, then the fringe's two edge sc rows and the knotting row.
FRINGED_ROWS = [
    {"row_number": 1, "stitch_count": 8, "instructions": "With Colour 1, Ch 10, turn."},
    {"row_number": 2, "stitch_count": 8, "instructions": "Skip the first 3 chains from the hook (they count as this row's first stitch, so the foundation chain is one shorter than this row's stitch count). Dc in the next chain and in each ch across. Ch 3, turn."},
    {"row_number": 3, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 4, "stitch_count": 8, "instructions": "With Colour 1, skip first st (the chain already ‘fills’ that slot), 6 dc in next 6 sts, at the end of the row, dc in top of the ch-3, changing to Colour 2 in the last st. Ch 3, turn."},
    {"row_number": 5, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 6, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 7, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 8, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 9, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 10, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 11, "stitch_count": 8, "instructions": "With Colour 2, skip first st (the chain already ‘fills’ that slot), 6 dc in next 6 sts, at the end of the row, dc in top of the ch-3, changing to Colour 1 in the last st. Ch 3, turn."},
    {"row_number": 12, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 13, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 14, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Ch 3, turn."},
    {"row_number": 15, "stitch_count": 8, "instructions": "Skip first st (the chain already ‘fills’ that slot), dc in each st across, at the end of the row, dc in top of the ch-3. Fasten off, weave in ends. Body measures approximately 7 in."},
    {"row_number": 16, "stitch_count": 8, "instructions": "Fringe: With RS facing, join Colour 1 to the first stitch of the foundation chain. Sc in each st evenly across, ending at the opposite corner. Fasten off."},
    {"row_number": 17, "stitch_count": 8, "instructions": "Fringe: With RS facing, join Colour 1 to the last stitch of the final row. Sc in each st evenly across, ending at the opposite corner. Fasten off."},
    {"row_number": 18, "stitch_count": 8, "instructions": "Fringe: Cut strands of Colour 1 twice your desired fringe length plus 1 in for knotting. Holding 3-4 strands together, fold in half and pull the folded loop through a stitch of the sc row with your hook; pull the loose ends through the loop and tighten. Repeat every 2-3 sts across both sc rows. Trim ends even."},
]


class TestScarfFinishingIsNotDesign(unittest.TestCase):
    # A row-striped design is compared at any width, so before this every
    # finishing row was read as one more stripe and the design came out wrong
    # by row 3 of a ribbed scarf.
    def test_ribbed_scarf_with_border_matches_its_stripes(self):
        self.assertEqual(_errors(RIBBED_ROWS), [])

    def test_fringed_scarf_matches_its_stripes(self):
        self.assertEqual(_errors(FRINGED_ROWS), [])

    def test_a_wrong_body_row_is_still_caught(self):
        # Control: stopping at the finishing must not stop the body being read.
        # Row 4 is the second Colour 2 stripe row; working it in Colour 1
        # leaves one B row where the design has two.
        rows = copy.deepcopy(RIBBED_ROWS)
        rows[3]["instructions"] = rows[3]["instructions"].replace("With Colour 2, ", "With Colour 1, ")
        self.assertTrue(_errors(rows))

    def test_a_dropped_body_row_is_still_caught(self):
        # Control: the body ending early, before the finishing, still fails.
        rows = copy.deepcopy(RIBBED_ROWS)
        del rows[2]
        self.assertTrue(_errors(rows))


if __name__ == "__main__":
    unittest.main()
