"""A whole flat piece's horizontal stripes come out an even number of rows,
counted from the first worked row, so each colour returns to the edge it was
left at (loopdreams resizeGridNN evenStripes / evenStripeRows, 2026-11-21).
Garment panels and folded totes keep the plain resample."""
import unittest

from loopdreams_qa.checks import colourwork_orientation as co

A, B, C = "#C9A227", "#4F7942", "#8E3B46"


def _runs(grid):
    runs = []
    for row in reversed(grid):          # bottom-up: the order it is worked
        if runs and runs[-1][0] == row[0]:
            runs[-1][1] += 1
        else:
            runs.append([row[0], 1])
    return runs


class TestEvenStripeResample(unittest.TestCase):
    def test_every_stripe_but_the_top_one_is_even(self):
        for g in (3, 4, 7, 12, 30, 120):
            grid = [[(A, B, C)[i % 3]] * 5 for i in range(g)]
            for rows in range(2, 160):
                out = co._resize_nn(grid, 5, rows, even_stripes=True)
                self.assertEqual(len(out), rows)
                runs = _runs(out)
                for colour, n in runs[:-1]:
                    self.assertEqual(n % 2, 0, f"g={g} rows={rows}: {runs}")
                    self.assertGreaterEqual(n, 2)
                # Never loses a colour the plain resample kept, while there
                # is room for each to have its 2 rows.
                kept = {r[0] for r in co._resize_plain_nn(grid, 5, rows)}
                if rows >= 2 * len(kept):
                    self.assertTrue(kept <= {r[0] for r in out}, f"g={g} rows={rows}")

    def test_already_even_is_untouched(self):
        grid = [[A] * 3, [A] * 3, [B] * 3, [B] * 3]
        self.assertEqual(co._resize_nn(grid, 3, 4, even_stripes=True), grid)
        self.assertEqual(co._resize_nn(grid, 3, 8, even_stripes=True), co._resize_plain_nn(grid, 3, 8))

    def test_a_painted_band_stays_in_place(self):
        # A 3-row Colour 2 band rows 8-10 of 24 (top-first): it keeps an even
        # height and does not move by more than a row.
        band = [[B if 8 <= r < 11 else A] * 4 for r in range(24)]
        out = co._resize_nn(band, 4, 24, even_stripes=True)
        idx = [r for r, row in enumerate(out) if row[0] == B]
        self.assertIn(len(idx), (2, 4))
        self.assertTrue(7 <= idx[0] and idx[-1] <= 11, idx)

    def test_a_legacy_one_row_step_grid_keeps_its_colours(self):
        # Saved before 2026-11-21: one grid row per worked row, colours
        # alternating every row. Each step is doubled instead of half of them
        # being dropped.
        legacy = [[(A, B)[i % 2]] * 4 for i in range(20)]
        out = co._resize_nn(legacy, 4, 20, even_stripes=True)
        self.assertEqual([r[0] for r in reversed(out)][:6], [B, B, A, A, B, B])

    def test_left_alone_without_the_flag_or_for_a_picture(self):
        stripes = [[A] * 4, [B] * 4, [A] * 4]
        self.assertEqual(co._resize_nn(stripes, 4, 14), co._resize_plain_nn(stripes, 4, 14))
        picture = [[A, B, A, A], [B, B, A, B], [A, A, A, B]]
        self.assertEqual(co._resize_nn(picture, 4, 14, even_stripes=True), co._resize_plain_nn(picture, 4, 14))
        one_colour = [[A] * 4] * 3
        self.assertEqual(co._resize_nn(one_colour, 4, 14, even_stripes=True), co._resize_plain_nn(one_colour, 4, 14))


if __name__ == "__main__":
    unittest.main()
