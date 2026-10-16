"""A textured (sedge, moss/linen) V-neck cardigan's Left Front steps at the
START of the row, on the same rows as the Right Front.

The Right Front stops a whole repeat short at the end of a step row
("..., leaving the last 3 sts unworked"). The Left Front's neck edge starts
those rows, so it slip-stitches across one repeat first:
"Decrease row: Sl st in each of the first 3 sts, ch 1 (does not count as a
st), hdc in next st, ...". The slip sts are consumed and produce nothing, and
the ch 1 is not one of moss's counted chains. The row after a step names its
last st in a trailing note. Before this, the Left Front stepped one row later
than the Right, and the two V's started a visible row apart (loopdreams,
2026-10-16).

Fixtures: real generator output from loopdreams feat/sedge-v-left-front-same-rows,
buildCardiganRows 46 in chest x 24 in body. Sedge at 3.3 x 2.7, moss at 4 x 4,
and a coloured sedge Front (heart design, placement "front", neckline kept)
through applyGarmentPanelColourwork.
"""
import json
import os
import re
import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.stitch_parser import tokenize_round

_DATA = os.path.join(os.path.dirname(__file__), "data")


def _load(name):
    with open(os.path.join(_DATA, f"cardigan_v_left_slip_step_{name}.json")) as f:
        return json.load(f)


def _status(payload):
    # As from_pattern_json.main builds it: the design travels beside the text.
    pattern = parse(build_raw_text(payload))
    pattern.design_grid = payload.get("design_grid")
    pattern.design_palette = payload.get("palette")
    pattern.neckline_edge = payload.get("neckline_edge")
    pattern.design_panels = payload.get("design_panels")
    pattern.design_rows = payload.get("rows") or []
    return run_for_pattern(pattern, quiet=True)["summary"]["status"]


def _mutate_first_step(payload, change):
    payload = json.loads(json.dumps(payload))
    row = next(r for r in payload["rows"]
               if r["section"] == "Left Front" and re.match(r"Decrease row: (?:With [^,]+, )?[Ss]l st", r["instructions"]))
    change(row)
    return payload


class TestLeftFrontSlipStep(unittest.TestCase):
    def test_the_slip_sts_are_consumed_and_make_nothing(self):
        c = tokenize_round("Sl st in each of the first 3 sts, ch 1 (does not count as a st), hdc in next st")
        self.assertEqual((c[0].clause_type, c[0].consumes, c[0].produces), ("skip", 3, 0))

    def test_a_note_after_the_repeat_count_is_not_a_stop_condition(self):
        c = tokenize_round("Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * 16 more times "
                           "(the row ends with an sc in the last ch-1 sp; the sc you made after the slip sts "
                           "and the slip sts stay unworked).")
        close = [x for x in c if x.clause_type == "repeat_close"]
        self.assertEqual(close[0].explicit_count, 16)
        self.assertIsNone(close[0].unverifiable_reason)

    def test_real_cardigans_pass(self):
        for name in ("sedge", "moss", "sedge_colour"):
            self.assertEqual(_status(_load(name)), "PASS", name)

    def test_a_wrong_slip_count_fails(self):
        for name, n in (("sedge", 3), ("moss", 2)):
            bad = _mutate_first_step(_load(name), lambda r: r.update(
                instructions=r["instructions"].replace(f"first {n} sts", f"first {n - 1} sts", 1)))
            self.assertEqual(_status(bad), "FAIL", name)

    def test_a_dropped_step_clause_fails(self):
        bad = _mutate_first_step(_load("sedge"), lambda r: r.update(instructions=r["instructions"].replace(
            "Sl st in each of the first 3 sts, ch 1 (does not count as a st), hdc in next st", "Hdc in first st", 1)))
        self.assertEqual(_status(bad), "FAIL")

    def test_moss_counts_the_marked_chain_only_if_unmarked(self):
        bad = _mutate_first_step(_load("moss"), lambda r: r.update(
            instructions=r["instructions"].replace(" (does not count as a st)", "", 1)))
        self.assertEqual(_status(bad), "FAIL")

    def test_a_wrong_colour_on_the_step_fails(self):
        bad = _mutate_first_step(_load("sedge_colour"), lambda r: r.update(
            instructions=r["instructions"].replace("With Colour 1, sl st", "With Colour 2, sl st", 1)))
        self.assertEqual(_status(bad), "FAIL")

    def test_the_step_row_reads_as_its_own_first_st(self):
        text = ("Decrease row: With Colour 1, sl st in each of the first 3 sts, ch 1 (does not count as a st), "
                "hdc in next st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); rep from * "
                "9 more times, sc in last st. Ch 1, turn. (33 sts)")
        colours, _ = co._row_colours(text, 33, "Colour 1")
        self.assertEqual(colours, ["Colour 1"] * 12)


if __name__ == "__main__":
    unittest.main()
