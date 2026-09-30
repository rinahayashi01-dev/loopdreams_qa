"""A waffle's first texture row closes "dc in last st", not "in top of the ch-2".

The setup row below it starts from skipped foundation chains that don't count,
so there is no ch-2 at that edge (loopdreams waffleFarEdge). Every later texture
row still closes in the ch-2. The fixture is a real generated coloured waffle
(buildWaffleStitchColourRows, 8in x 8in, two colours).
"""

import copy
import json
import os
import re
import unittest

from loopdreams_qa import from_pattern_json as fpj
from loopdreams_qa.checks import colourwork_orientation as co

with open(os.path.join(os.path.dirname(__file__), "data", "waffle_first_texture_row.json")) as f:
    PAYLOAD = json.load(f)


def issues(payload):
    pattern = fpj.parse(fpj.build_raw_text(payload))
    pattern.design_grid = payload["design_grid"]
    pattern.design_palette = payload["palette"]
    pattern.design_rows = payload["rows"]
    return [i for i in co.check(pattern) if i.severity in ("error", "warning")]


def first_texture_row(payload):
    return next(r for r in payload["rows"] if re.search(r"skip first st", r["instructions"], re.I))


class WaffleFirstTextureRow(unittest.TestCase):
    def test_fixture_is_the_shape_under_test(self):
        t = first_texture_row(PAYLOAD)["instructions"]
        self.assertIn("dc in last st", t)
        self.assertNotIn("top of the ch-2", t)

    def test_every_row_is_read_and_matches(self):
        self.assertEqual(issues(PAYLOAD), [])

    def test_a_wrong_colour_on_that_row_is_an_error(self):
        p = copy.deepcopy(PAYLOAD)
        row = first_texture_row(p)
        m = re.match(r"With Colour (\d)", row["instructions"])
        row["instructions"] = row["instructions"].replace(m.group(0), f"With Colour {3 - int(m.group(1))}", 1)
        found = issues(p)
        self.assertTrue(any(i.severity == "error" for i in found), found)


if __name__ == "__main__":
    unittest.main()
