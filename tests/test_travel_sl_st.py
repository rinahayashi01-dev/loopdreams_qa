"""A travel sl st makes no fabric, whatever it lands in or carries as a note.

loopdreams' 1-colour Granny Square Blanket motif (#619) slips across to each
round's start instead of joining new yarn, and Round 5's slip stitches carry the
note the maker needs ("in this round, every Cluster and every ch-1 sp counts as
1 st"). "sl st in next Cluster", "sl st in the sp between ..." and a travel with
a "counts as" note were all unrecognised, which cost Round 5 its count check.
The fixture is the live generator's 1-colour 48x60 dry-run output.
"""

import copy
import json
import os
import unittest

from loopdreams_qa import from_pattern_json as fpj
from loopdreams_qa.checks import stitch_count
from loopdreams_qa.stitch_parser import tokenize_round

with open(os.path.join(os.path.dirname(__file__), "data", "granny_blanket_one_colour.json")) as f:
    PAYLOAD = json.load(f)


def row_issues(payload, row):
    pattern = fpj.parse(fpj.build_raw_text(payload))
    return [i for i in stitch_count.check(pattern) if i.location == f"Row {row}"]


def no_op(text):
    return [(c.clause_type, c.consumes, c.produces) for c in tokenize_round(text)] == [("note", 0, 0)]


class TravelSlSt(unittest.TestCase):
    def test_new_targets_are_no_ops(self):
        self.assertTrue(no_op("Sl st in next Cluster"))
        self.assertTrue(no_op("Sl st in the sp between the ch 3 and the next dc"))

    def test_a_note_about_the_rounds_stitches_is_a_no_op(self):
        self.assertTrue(no_op(
            "Sl st in next ch-1 sp (the sp between the 2 Clusters of an increase; "
            "in this round, every Cluster and every ch-1 sp counts as 1 st)"))

    def test_a_sl_st_claiming_to_count_is_not_guessed(self):
        # The sl st itself counting as a stitch would change the round's math.
        self.assertFalse(no_op("Sl st in next sp (counts as first sc)"))
        self.assertFalse(no_op("Sl st in next Cluster (counts as 1 st)"))

    def test_a_note_carrying_stitch_work_is_not_guessed(self):
        self.assertFalse(no_op("Sl st in next sp (2 dc, counts as a shell)"))

    def test_existing_travel_forms_unchanged(self):
        self.assertTrue(no_op("Sl st in next ch-2 corner sp"))
        self.assertTrue(no_op("Sl st to corner sp"))


class OneColourGrannyMotif(unittest.TestCase):
    def test_fixture_is_the_shape_under_test(self):
        r5 = next(r for r in PAYLOAD["rows"] if r["row_number"] == 5)["instructions"]
        self.assertTrue(r5.startswith("Sl st in next ch-1 sp, sl st in next Cluster, sl st in next ch-1 sp ("))
        self.assertIn("counts as 1 st)", r5)

    def test_round_5_is_verified(self):
        self.assertEqual(row_issues(PAYLOAD, 5), [])

    def test_a_wrong_count_on_round_5_is_an_error(self):
        p = copy.deepcopy(PAYLOAD)
        row = next(r for r in p["rows"] if r["row_number"] == 5)
        row["instructions"] = row["instructions"].replace(
            "1 sc in each of next 3 sts", "1 sc in each of next 4 sts", 1)
        errs = [i for i in row_issues(p, 5) if i.severity == "error"]
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("Stitch-count mismatch", errs[0].message)

    def test_round_3_is_unverifiable_for_the_cluster_only(self):
        # Clusters are still honestly unverifiable (KNOWN_UNVERIFIABLE item 1);
        # the slip across into Round 2's first space no longer adds a reason.
        msgs = [i.message for i in row_issues(PAYLOAD, 3)]
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn("'cluster' has no fixed consumes/produces ratio", msgs[0])
        self.assertNotIn("unrecognized clause", msgs[0])


if __name__ == "__main__":
    unittest.main()
