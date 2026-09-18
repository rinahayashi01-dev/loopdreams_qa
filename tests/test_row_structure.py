"""Phase 1 of the row-to-row model: the group structure each row produces.

See SCOPE_ROW_TO_ROW.md. Nothing reads produced_groups yet, so none of this
can move a verdict -- these tests pin the model itself, so that phase 2 (the
clauses that resolve AGAINST it) starts from proven plumbing.

The row texts here are verbatim generator output wherever one was already
available in this suite, re-used rather than re-typed: a hand-written
imitation would only prove the model agrees with my idea of the generator.
"""
import unittest

from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count
from loopdreams_qa.checks.stitch_count import _zone_groups
from loopdreams_qa.stitch_parser import tokenize_round

# Imported as modules, not as names: importing the TestCase classes directly
# would pull them into this module's namespace and run them a second time.
from . import test_colourwork_orientation as _cw
from . import test_moss_chain_convention as _moss

SHELL_ROWS = _cw.SHELL_ROWS
MATERIALS  = _moss.MATERIALS
# The row texts only -- binding the TestCase class itself would re-collect it.
MOSS_PLAIN    = _moss.MossChainConventionTest.PLAIN
MOSS_UNROLLED = _moss.MossChainConventionTest.UNROLLED
MOSS_TRAILING = _moss.MossChainConventionTest.TRAILING


def _checked(rows):
    """Parse a generated-pattern payload, run the stitch-count check (which is
    what fills in produced_groups), and return {row label: RoundRow}."""
    payload = {
        "title": "Structure test", "rows": rows, "is_in_round": False,
        "gauge_sts_per_in": 4, "gauge_rows_per_in": 4,
        "params": {"hook_size": "5.0 mm", "yarn_weight": "Worsted"},
    }
    pattern = parse(build_raw_text(payload))
    issues = stitch_count.check(pattern)
    return pattern, issues


class ShellStructureTest(unittest.TestCase):
    """The case the whole model exists for.

    A shell row is not 13 stitches in a flat line -- it is 5 dc worked into
    one stitch, twice, with singles between. Only the second reading lets a
    later row's "sc in centre dc of next shell" say what it passes over.
    """

    def setUp(self):
        self.pattern, self.issues = _checked(SHELL_ROWS)
        self.rows = {r.label: r for r in self.pattern.rows}

    def test_a_shell_row_produces_groups_not_singles(self):
        # "sc in first st; skip 2, 5 dc in next st; skip 2, sc in next st;
        # skip 2, 5 dc in next st; skip 2, sc in next st" -- two shells of 5
        # with singles around them, 13 sts in 5 groups.
        self.assertEqual(self.rows["Row 2"].produced_groups, [1, 5, 1, 5, 1])

    def test_a_half_shell_row_produces_its_own_shape(self):
        # The alternating row: half shells at each edge (3 dc, counting the
        # turning chain) and a whole one in the middle.
        self.assertEqual(self.rows["Row 3"].produced_groups, [3, 1, 5, 1, 3])

    def test_every_shell_row_resolves_including_the_repeat_group_one(self):
        # Row 7 states its shells as "*...; rep from * to last shell, 0 more
        # times" rather than writing them out -- the repeat zone contributes
        # its unit's groups, repeated.
        for label in ("Row 1", "Row 2", "Row 3", "Row 4", "Row 5", "Row 6", "Row 7"):
            row = self.rows[label]
            self.assertIsNotNone(row.produced_groups, f"{label}: {row.produced_groups_reason}")
            self.assertEqual(sum(row.produced_groups), row.declared_count, label)

    def test_a_row_whose_consumes_is_unknown_still_reports_what_it_produces(self):
        # The point of splitting the two. Rows 3/5/7 are exactly the rows
        # this tool cannot do the arithmetic for -- "sc in centre dc of next
        # shell" has no consumes -- and they are also the rows whose produced
        # structure phase 2 will need. Both are true at once.
        self.assertTrue(any("centre dc" in i.message for i in self.issues))
        self.assertIsNotNone(self.rows["Row 3"].produced_groups)

    def test_recording_structure_added_no_findings(self):
        # Phase 1 is additive. The only thing this pattern has ever reported
        # is the centre-dc abstention, and it still is.
        self.assertEqual(len(self.issues), 1, [i.message for i in self.issues])
        self.assertEqual(self.issues[0].severity, "warning")


class PlainAndIncreaseStructureTest(unittest.TestCase):
    def test_a_plain_row_is_all_singles(self):
        pattern, _ = _checked([
            {"row_number": 1, "stitch_count": 20, "instructions": "Foundation: Ch 21, turn."},
            {"row_number": 2, "stitch_count": 20, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). Sc in the next chain and each ch across. Ch 1, turn."},
            {"row_number": 3, "stitch_count": 20, "instructions": "Sc in each st across. Ch 1, turn."},
        ])
        for row in pattern.rows:
            self.assertEqual(row.produced_groups, [1] * 20, row.label)

    def test_a_row_worked_into_the_foundation_chain_derives_from_the_CHAIN(self):
        # Not from the declared count -- that would make the sum check in
        # _row_group_structure circular and unable to catch anything. Ch 21,
        # skip 1, so 20 singles, which is then checked against the declared 20.
        pattern, _ = _checked([
            {"row_number": 1, "stitch_count": 20, "instructions": "Foundation: Ch 21, turn."},
            {"row_number": 2, "stitch_count": 20, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). Sc in the next chain and each ch across. Ch 1, turn."},
        ])
        self.assertEqual(pattern.rows[0].produced_groups, [1] * 20)

    def test_an_increase_makes_a_group_two_wide(self):
        # "2 sc in first st" puts two stitches in one place, which is a group
        # of 2 -- the same distinction shell relies on, at its smallest.
        pattern, _ = _checked([
            {"row_number": 1, "stitch_count": 3, "instructions": "Foundation: Ch 4, turn."},
            {"row_number": 2, "stitch_count": 5, "instructions": "2 sc in first st, sc in next st, 2 sc in last st. Ch 1, turn."},
            {"row_number": 3, "stitch_count": 7, "instructions": "2 sc in first st, sc in each of next 3 sts, 2 sc in last st. Ch 1, turn."},
        ])
        self.assertEqual(pattern.rows[0].produced_groups, [2, 1, 2])
        self.assertEqual(pattern.rows[1].produced_groups, [2, 1, 1, 1, 2])


class SameSpotTest(unittest.TestCase):
    """A clause working into the spot the clause before it named widens that
    group rather than opening a new one -- the granny-square "in the same sp"
    shape. The parser gives these the same clause_type as an ordinary
    cluster, so the model reads the word "same"."""

    def test_the_same_spot_widens_the_previous_group(self):
        self.assertEqual(_zone_groups(tokenize_round("5 dc in next sp, 1 dc in the same sp, dc in next 3 sts.")),
                         ([6, 1, 1, 1], None))

    def test_it_widens_whichever_group_actually_precedes_it(self):
        self.assertEqual(_zone_groups(tokenize_round("3 dc in next st, sc in next st, 3 dc in same st.")),
                         ([3, 4], None))

    def test_it_abstains_when_there_is_no_preceding_group(self):
        groups, reason = _zone_groups(tokenize_round("3 dc in the same sp."))
        self.assertIsNone(groups)
        self.assertIn("first clause in the row", reason)


class MossConventionStructureTest(unittest.TestCase):
    """Moss counts its ch-1 spaces toward the row total, and the next row
    works into those spaces -- so under that convention they are real groups.
    The row's own turning chain never is. Verbatim generator output, reused
    from test_moss_chain_convention."""

    def _rows(self, *body):
        raw = (
            "Structure test\n" + MATERIALS
            + "ABBREVIATIONS\nch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 22, turn.\n"
            "Row 1: Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Sc in the next chain and in each ch across. Ch 1, turn. (21 sts)\n"
            + "\n".join(f"Row {i + 2}: {t} (21 sts)" for i, t in enumerate(body)) + "\n"
            "Finishing\nBorder: Fasten off. (21 sts)\n"
        )
        pattern = parse(raw)
        stitch_count.check(pattern)
        return [r for r in pattern.rows if r.label.startswith("Row")]

    def test_every_moss_shape_resolves_to_21_single_groups(self):
        # Each ch-1 space is one stitch the next row works into, so every
        # group is 1 wide -- and there are 21 of them, not 22: the trailing
        # "Ch 1, turn." is dropped by position, the same way the arithmetic
        # drops it.
        for row in self._rows(MOSS_PLAIN, MOSS_UNROLLED, MOSS_TRAILING):
            self.assertEqual(row.produced_groups, [1] * 21, f"{row.label}: {row.produced_groups_reason}")


class AbstentionTest(unittest.TestCase):
    """What the model refuses to answer, and why. Each of these is a row the
    arithmetic above already abstains on for the same underlying reason."""

    def test_a_compound_stitch_with_no_stated_construction_abstains(self):
        pattern, _ = _checked([
            {"row_number": 1, "stitch_count": 20, "instructions": "Foundation: Ch 21, turn."},
            {"row_number": 2, "stitch_count": 20, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). Sc in the next chain and each ch across. Ch 1, turn."},
            {"row_number": 3, "stitch_count": 20, "instructions": "Sc in next 2 sts, *bobble in next st, sc in next 3 sts; rep from * across, 3 more times, sc in next 2 sts. Ch 1, turn."},
        ])
        row = pattern.rows[-1]
        self.assertIsNone(row.produced_groups)
        self.assertIn("bobble", row.produced_groups_reason)

    def test_a_structure_that_disagrees_with_the_declared_count_is_discarded(self):
        # The gate that makes this safe to build phase 2 on. Ch 22 starting in
        # the 3rd chain produces 20, not the 21 declared -- a row the
        # arithmetic reports as an error -- so no structure is carried forward
        # for it either.
        pattern, issues = _checked([
            {"row_number": 1, "stitch_count": 21, "instructions": "Foundation: Ch 22, turn."},
            {"row_number": 2, "stitch_count": 21, "instructions": "Dc in 3rd ch from hook (skipped 2-ch does not count as st) and in each ch across. Ch 2, turn."},
        ])
        row = pattern.rows[0]
        self.assertIsNone(row.produced_groups)
        self.assertIn("declares 21", row.produced_groups_reason)
        # And the two agree -- the model abstains exactly where the
        # arithmetic objects, rather than quietly disagreeing with it.
        self.assertTrue(any(i.severity == "error" for i in issues))

    def test_a_per_stitch_clause_never_resolves_on_its_own(self):
        # "sc in each st across" produces a RATIO, not a total -- how many
        # groups it makes depends on the in-count, which only the row walk
        # knows. Reaching the clause-level helper with one would be a bug,
        # so it abstains rather than reporting the single group its
        # produces=1 would otherwise suggest.
        groups, reason = _zone_groups(tokenize_round("sc in each st across"))
        self.assertIsNone(groups)
        self.assertIn("doesn't state", reason)


if __name__ == "__main__":
    unittest.main()
