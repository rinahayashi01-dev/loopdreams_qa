"""A mitten worked cuff-up opens on a chain ring, and skips (not holds) its thumb sts.

loopdreams' mitten used to start "Magic ring. 30 sc in ring" for the CUFF (a
magic ring is pulled shut, so it can't make an open cuff) and set the thumb
aside "on a holder or scrap yarn" (knitting's way of keeping live loops; a
crochet stitch has none). It now opens on "Ch 30, join with sl st to form
ring, taking care not to twist the chain.", works "Ch 1, sc in same ch as join and in each ch
around." into it, and says "Skip the next 10 sts and leave them unworked",
picking them up later as "the 10 skipped gusset sts".

Fixture: real generator output (buildMittenRows, Mittens - beginner batch
case, both mittens), from loopdreams fix/mitten-cuff-thumb.
"""
import json
import os
import re
import unittest

from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.stitch_parser import tokenize_round

_FIXTURE = os.path.join(os.path.dirname(__file__), "data", "mitten_chain_ring_cuff.json")


def _report(payload):
    return run_for_pattern(parse(build_raw_text(payload)), quiet=True)


def _bump_count(row):
    row["stitch_count"] += 1
    row["instructions"] = re.sub(r"\((\d+) sc\)", lambda m: f"({int(m.group(1)) + 1} sc)", row["instructions"])


class TestMittenChainRingCuff(unittest.TestCase):
    def setUp(self):
        with open(_FIXTURE) as f:
            self.payload = json.load(f)

    def _mutated(self, pred, change):
        payload = json.loads(json.dumps(self.payload))
        row = next(r for r in payload["rows"] if r["section"] == "Mitten 1" and pred(r))
        change(row)
        return payload

    def test_passes(self):
        report = _report(self.payload)
        self.assertEqual(report["summary"]["status"], "PASS", report["issues"])

    def test_twist_warning_is_a_no_op(self):
        clauses = tokenize_round("taking care not to twist the chain")
        self.assertEqual([(c.clause_type, c.consumes, c.produces) for c in clauses], [("note", 0, 0)])

    def test_skipped_and_held_wordings_set_aside_the_same_count(self):
        for text in ("Skip the next 10 sts and leave them unworked (thumb gusset)",
                     "Place the next 10 sts on a holder or scrap yarn (thumb gusset)"):
            with self.subTest(text):
                held = [c for c in tokenize_round(text) if c.clause_type == "held_aside"]
                self.assertEqual([(c.consumes, c.produces) for c in held], [(10, 0)])

    def test_first_round_is_still_checked(self):
        payload = self._mutated(lambda r: r["instructions"].startswith("Ch 1, sc in same ch as join"), _bump_count)
        self.assertEqual(_report(payload)["summary"]["status"], "FAIL")

    def test_wrong_skip_count_is_caught(self):
        payload = self._mutated(
            lambda r: "leave them unworked" in r["instructions"],
            lambda r: r.__setitem__("instructions", re.sub(
                r"Skip the next (\d+)", lambda m: f"Skip the next {int(m.group(1)) - 1}", r["instructions"])))
        self.assertEqual(_report(payload)["summary"]["status"], "FAIL")

    def test_wrong_thumb_pickup_is_caught(self):
        payload = self._mutated(
            lambda r: "skipped gusset sts" in r["instructions"],
            lambda r: r.__setitem__("instructions", re.sub(
                r"of the (\d+) skipped", lambda m: f"of the {int(m.group(1)) + 1} skipped", r["instructions"])))
        self.assertEqual(_report(payload)["summary"]["status"], "FAIL")

    def test_thumb_decrease_round_is_checked(self):
        payload = self._mutated(lambda r: r["instructions"].startswith("*Sc2tog; rep from * around")
                                and r["stitch_count"] < 12, _bump_count)
        self.assertEqual(_report(payload)["summary"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
