"""The tote's pocket, made as its own piece and sewn on before Assembly
(loopdreams, 2026-11-23). Row text copied verbatim from buildPocketRows /
buildPocketAttachRows."""
import unittest

from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse

ATTACH = ("Attaching the Pocket: Lay the finished panel flat with the side that will be the outside of the bag "
          "(RS) facing up. On the half that starts at the foundation chain (this half becomes the front), place "
          "the pocket with its last row at the top, centered side to side, its top edge 2 in / 5 cm below the "
          "foundation chain edge. Pin, then whip stitch the pocket's sides and bottom to the panel, leaving the "
          "top edge open as the pocket opening.")
POCKET = ("Skip the first chain from the hook (it doesn't count as a stitch). Sc in the next chain and each ch "
          "across. Ch 1, turn. Work 19 more rows of sc (20 rows total). Fasten off. ({n} sts)")


def payload(pocket_sts=28):
    return {
        "title": "Tote Bag", "gauge_sts_per_in": 4, "gauge_rows_per_in": 4,
        "yarn_weight_name": "Worsted", "hook_label": "5.0 mm (H-8)",
        "abbreviations": [{"abbr": "sc", "definition": "single crochet"},
                          {"abbr": "ch", "definition": "chain"}],
        "rows": [
            {"row_number": 1, "stitch_count": 56, "section": None,
             "instructions": "Ch 57. Skip the first chain from the hook (it doesn't count as a stitch). "
                             "Sc in the next chain and each ch across. Ch 1, turn. (56 sts)"},
            {"row_number": 2, "stitch_count": 56, "section": None, "instructions": "Sc in each st across. Ch 1, turn. (56 sts)"},
            {"row_number": 3, "stitch_count": 28, "section": "Pocket", "instructions": "Foundation: Ch 29."},
            {"row_number": 4, "stitch_count": 28, "section": "Pocket", "instructions": POCKET.format(n=pocket_sts)},
            {"row_number": 5, "stitch_count": 56, "section": None, "instructions": ATTACH},
            {"row_number": 6, "stitch_count": 56, "section": None,
             "instructions": "Assembly: Lay the finished panel flat, WS facing up. Fold it in half and seam each side."},
        ],
    }


def report(p):
    return run_for_pattern(parse(build_raw_text(p)), quiet=True)


class TestAttachingThePocket(unittest.TestCase):
    def test_sewing_row_is_finishing_and_not_counted(self):
        raw = build_raw_text(payload())
        self.assertLess(raw.index("Finishing"), raw.index("Attaching the Pocket:"), raw)
        self.assertLess(raw.index("POCKET"), raw.index("Finishing"), raw)
        r = report(payload())
        self.assertEqual(r["summary"]["status"], "PASS", r["issues"])

    def test_the_pocket_piece_is_still_checked(self):
        r = report(payload(pocket_sts=29))
        self.assertEqual(r["summary"]["status"], "FAIL", r["issues"])

    def test_the_older_counted_pocket_row_is_still_read(self):
        # Saved patterns carry the old single "Pocket: Ch N. ..." row at the end.
        p = payload()
        p["rows"] = p["rows"][:2] + [p["rows"][5], {
            "row_number": 4, "stitch_count": 28, "section": None,
            "instructions": "Pocket: Ch 29. Skip the first chain from the hook (it doesn't count as a stitch). "
                            "Sc in the next chain and each ch across. Ch 1, turn. Work 19 more rows of sc "
                            "(20 rows total). Fasten off. Sew the pocket to the front panel. (28 sts)"}]
        self.assertTrue(any(rr.label == "Pocket" for rr in parse(build_raw_text(p)).rows))


if __name__ == "__main__":
    unittest.main()
