"""A tote's top finish: built-in handles and a top band, worked in joined
rounds on the assembled bag's rim (loopdreams buildToteTopFinishRows,
2026-10-11).

Before this the rounds were unrecognised labels, so each came back "cannot
verify" and, after sewn handle strips, was filed under the last strip as a
false row gap. Now each round is checked against what it works into: the
first round the whole rim (both halves of the folded panel), a Strap Round
the Handle Round's sts and chains, a Handle Edging its own opening and strap.

Fixtures: real builder output -- an hdc tote with built-in handles, an accent
colour and a crab round; a dc tote with a 3-round hdc band and sewn handles;
a striped sc tote with an accent band.
"""
import json
import os
import re
import unittest

from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse

_FIXTURES = json.load(open(os.path.join(os.path.dirname(__file__), "data", "tote_top_finish.json")))


def _report(payload):
    return run_for_pattern(parse(build_raw_text(payload)), quiet=True)


def _mutated(name, label, change):
    p = json.loads(json.dumps(_FIXTURES[name]))
    hit = False
    for r in p["rows"]:
        if r["instructions"].startswith(label):
            new = change(r["instructions"])
            hit = hit or new != r["instructions"]
            r["instructions"] = new
    assert hit, f"mutation did not apply to {label}"
    return p


class TestToteTopFinish(unittest.TestCase):
    def test_every_fixture_passes(self):
        for name, payload in _FIXTURES.items():
            report = _report(payload)
            self.assertEqual(report["summary"]["status"], "PASS", (name, report["issues"]))

    def test_pick_up_is_checked_against_the_whole_rim(self):
        p = _mutated("hdc-continuous-accent-crab", "Border Round 1",
                     lambda t: re.sub(r"rep from \* (\d+) more times", lambda m: f"rep from * {int(m.group(1)) - 1} more times", t, 1))
        self.assertEqual(_report(p)["summary"]["status"], "FAIL")

    def test_handle_round_and_strap_round_counts(self):
        p = _mutated("hdc-continuous-accent-crab", "Handle Round", lambda t: t.replace("skip next 25 sts", "skip next 26 sts", 1))
        self.assertEqual(_report(p)["summary"]["status"], "FAIL")
        # The Strap Round works into the chains too, so a chain short fails.
        p = _mutated("hdc-continuous-accent-crab", "Strap Round 1", lambda t: t.replace("next 54 ch", "next 53 ch", 1))
        self.assertEqual(_report(p)["summary"]["status"], "FAIL")

    def test_handle_edging_checks_its_own_opening(self):
        p = _mutated("hdc-continuous-accent-crab", "Handle 1 Edging", lambda t: t.replace("each of the 56 ch", "each of the 55 ch"))
        self.assertEqual(_report(p)["summary"]["status"], "FAIL")

    def test_band_after_sewn_strips_is_not_a_strip_row(self):
        # Used to be filed under the last handle strip as "no instructions for
        # Rows 2-65".
        issues = json.dumps(_report(_FIXTURES["dc-band-hdc"])["issues"])
        self.assertNotIn("No instructions are given", issues)
        p = _mutated("dc-band-hdc", "Top Band Round 2", lambda t: re.sub(r"next (\d+) sts", lambda m: f"next {int(m.group(1)) - 1} sts", t, 1))
        self.assertEqual(_report(p)["summary"]["status"], "FAIL")

    def test_accent_band_is_not_read_as_the_design(self):
        issues = json.dumps(_report(_FIXTURES["sc-striped-band-accent"])["issues"])
        self.assertNotIn("before the pattern names any colour", issues)
        self.assertNotIn("could not be read", issues)


if __name__ == "__main__":
    unittest.main()


class TestToteTopFinishLinen(unittest.TestCase):
    # A linen body's last row is sc and ch-1 sps; the pick-up names both and
    # counts 1 per position (loopdreams, crochet-pattern-reviewer 2026-10-11).
    def test_linen_pick_up_counts_sc_and_spaces(self):
        report = _report(_FIXTURES["linen-band-blsc-crab-leather"])
        self.assertEqual(report["summary"]["status"], "PASS", report["issues"])
        p = _mutated("linen-band-blsc-crab-leather", "Top Band Round 1",
                     lambda t: re.sub(r"next (\d+) sc and ch-1 sps", lambda m: f"next {int(m.group(1)) - 1} sc and ch-1 sps", t, 1))
        self.assertEqual(_report(p)["summary"]["status"], "FAIL")
