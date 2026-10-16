"""A row's stated repeat count is checked, not only its total.

The single-group path solves how many times "rep from *" must run from the
previous row's count and checks the row's total. It never compared that with
the count the row STATES ("rep from * 24 more times"), which is the number a
maker actually follows. So "24 more times" bumped to 25 on a sedge cardigan
row still PASSed whenever the declared total was right (loopdreams,
2026-10-16).

Fixtures: the real sedge and moss cardigans from test_left_front_slip_step.py.
"""
import json
import os
import re
import unittest

from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse

_DATA = os.path.join(os.path.dirname(__file__), "data")


def _load(name):
    with open(os.path.join(_DATA, f"cardigan_v_left_slip_step_{name}.json")) as f:
        return json.load(f)


def _report(payload):
    return run_for_pattern(parse(build_raw_text(payload)), quiet=True)


def _bump(payload, section, k, nth=20):
    payload = json.loads(json.dumps(payload))
    rows = [r for r in payload["rows"] if r["section"] == section and re.search(r"\d+ more times", r["instructions"])]
    row = rows[nth]
    row["instructions"] = re.sub(r"(\d+) more times", lambda m: f"{int(m.group(1)) + k} more times",
                                 row["instructions"], count=1)
    return payload


def _messages(report):
    out = []

    def walk(x):
        if isinstance(x, dict):
            if x.get("severity") == "error":
                out.append(x.get("message", ""))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(report)
    return out


class TestStatedRepeatCount(unittest.TestCase):
    def test_real_counts_pass(self):
        for name in ("sedge", "moss"):
            self.assertEqual(_report(_load(name))["summary"]["status"], "PASS", name)

    def test_one_too_many_or_too_few_fails(self):
        for name in ("sedge", "moss"):
            for section in ("Back", "Right Front"):
                for k in (1, -1):
                    report = _report(_bump(_load(name), section, k, nth=5))
                    self.assertEqual(report["summary"]["status"], "FAIL", f"{name} {section} {k:+d}")
                    self.assertTrue(any(m.startswith("Repeat-count mismatch") for m in _messages(report)),
                                    f"{name} {section} {k:+d}: {_messages(report)[:2]}")

    def test_the_message_names_both_counts(self):
        report = _report(_bump(_load("sedge"), "Back", 1))
        msg = next(m for m in _messages(report) if m.startswith("Repeat-count mismatch"))
        self.assertRegex(msg, r"work the repeat (\d+) time\(s\) in all \('(\d+) more'\), but .* fits exactly (\d+) time\(s\)")


if __name__ == "__main__":
    unittest.main()
