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
from loopdreams_qa.checks.stitch_count import _zone_groups, _resolve_group_references
from loopdreams_qa.models import RoundRow
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

    def test_what_a_row_produces_is_known_even_when_what_it_consumes_is_not(self):
        # The point of splitting the two, and what makes phase 2 possible.
        # Rows 3/5/7 are exactly the rows whose arithmetic could not be done
        # -- "sc in centre dc of next shell" states no consumes -- and their
        # PRODUCED structure was knowable all along. Phase 2 feeds one to the
        # other.
        for label in ("Row 3", "Row 5", "Row 7"):
            self.assertIsNotNone(self.rows[label].produced_groups, label)

    def test_the_whole_shell_piece_now_verifies(self):
        # Before phase 2 this pattern's only finding was the centre-dc
        # abstention. With the previous row's widths available there is
        # nothing left it cannot do.
        self.assertEqual(self.issues, [], [i.message for i in self.issues])


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


class GroupReferenceResolutionTest(unittest.TestCase):
    """Phase 2: a clause naming a position inside one of the previous row's
    groups gets its consumes from that row's structure.

    Driven directly, with the previous row's widths supplied, because that
    is the only way to prove the width is READ rather than assumed -- the
    same half-shell row over a 3-wide shell has to come out as 3.
    """

    # Verbatim generator wording, both forms buildHalfShellRowText writes:
    # every shell spelled out, and the middle ones as a repeat group.
    WRITTEN_OUT = ("2 dc in first sc (turning ch-3 counts as first dc; half shell made), "
                   "sc in centre dc of next shell; 5 dc in next sc; "
                   "sc in centre dc of last shell; 3 dc in last sc (half shell made). Ch 1, turn.")
    AS_REPEAT   = ("2 dc in first sc (turning ch-3 counts as first dc; half shell made), "
                   "*sc in centre dc of next shell, 5 dc in next sc; "
                   "rep from * to last shell, 1 more time, sc in centre dc of last shell, "
                   "3 dc in last sc (half shell made).")

    def _resolve(self, text, prev_groups):
        row = RoundRow(label="Row X", row_start=1, row_end=1, raw_text=text,
                       clauses=tokenize_round(text))
        reason = _resolve_group_references(row, prev_groups)
        return reason, [c.consumes for c in row.clauses if c.group_reference]

    def test_the_shell_width_is_read_from_the_previous_row_not_assumed(self):
        # The reason this could never be a regex: the instruction reads
        # identically whatever the shell's width, so a hardcoded 5 would be
        # silently wrong on any other shell -- see KNOWN_UNVERIFIABLE.md.
        for width in (3, 5, 7):
            reason, consumes = self._resolve(self.WRITTEN_OUT, [1, width, 1, width, 1])
            self.assertIsNone(reason)
            self.assertEqual(consumes, [width, width], f"{width}-wide shell")

    def test_it_resolves_the_same_row_written_as_a_repeat_group(self):
        # The repeat count is solved from the GROUP count (7 groups into
        # 1 + 2x2 + 2), independently of the arithmetic solving the same
        # number of repeats from the stitch count.
        reason, consumes = self._resolve(self.AS_REPEAT, [1, 5, 1, 5, 1, 5, 1])
        self.assertIsNone(reason)
        self.assertEqual(consumes, [5, 5])

    def test_it_abstains_when_the_previous_rows_structure_is_unknown(self):
        reason, consumes = self._resolve(self.WRITTEN_OUT, None)
        self.assertIn("isn't known", reason)
        self.assertEqual(consumes, [None, None])

    def test_it_abstains_when_the_clauses_and_the_groups_do_not_line_up(self):
        # One group too many for the clauses to account for.
        reason, _ = self._resolve(self.WRITTEN_OUT, [1, 5, 1, 5, 1, 1])
        self.assertIn("accounts for 5 groups", reason)

    def test_it_abstains_when_a_plain_clause_sits_over_a_wide_group(self):
        # The check that keeps one-clause-one-group honest. Here the row's
        # opening "2 dc in first sc" consumes 1, but the alignment would put
        # it over a 5-wide shell -- so something is wrong and nothing is
        # written, rather than the row being told a number.
        reason, consumes = self._resolve(self.WRITTEN_OUT, [5, 1, 1, 5, 1])
        self.assertIn("lines up with a group of 5", reason)
        self.assertEqual(consumes, [None, None])

    def test_it_abstains_on_a_clause_that_consumes_more_than_one_group(self):
        # "skip 2 sts" accounts for two of the previous row's stitches, which
        # may be one group or two -- the model cannot tell, so it stops.
        reason, _ = self._resolve("sc in centre dc of next shell, skip 2 sts, sc in next st.", [5, 2, 1])
        self.assertIn("rather than", reason)

    def test_it_abstains_when_one_clause_would_need_two_different_answers(self):
        # The same clause object covers every repetition of the unit. If the
        # shells under it are not all the same width there is no single
        # consumes to give it.
        reason, _ = self._resolve(self.AS_REPEAT, [1, 5, 1, 3, 1, 5, 1])
        self.assertIn("different widths", reason)

    def test_it_abstains_when_the_groups_do_not_divide_into_the_repeat(self):
        reason, _ = self._resolve(self.AS_REPEAT, [1, 5, 1, 5, 1, 5, 1, 1])
        self.assertIn("don't divide evenly", reason)

    def test_nothing_is_written_when_any_part_of_the_row_fails(self):
        # All-or-nothing: a half-resolved row would be worse than an
        # unresolved one, because the arithmetic would then run on a row it
        # only partly understands. The first reference here could be paired
        # with a group; the row still comes back untouched.
        reason, consumes = self._resolve(self.WRITTEN_OUT, [1, 5, 1, 5, 1, 1])
        self.assertIsNotNone(reason)
        self.assertEqual(consumes, [None, None])


class ShellNowCheckedTest(unittest.TestCase):
    """The coverage this buys: shell rows were verified by nothing at all,
    so a real regression in them would have passed silently."""

    def test_a_wrong_declared_count_on_a_shell_row_is_now_caught(self):
        import copy
        rows = copy.deepcopy(SHELL_ROWS)
        rows[3]["stitch_count"] = 15          # the half-shell row; really 13
        _, issues = _checked(rows)
        self.assertTrue(any(i.severity == "error" for i in issues),
                        [f"{i.severity} {i.location} {i.message}" for i in issues])

    def test_the_correct_piece_still_passes(self):
        # The other half of the same claim -- catching a wrong count is only
        # worth anything if the right one is not also flagged.
        _, issues = _checked(SHELL_ROWS)
        self.assertEqual(issues, [], [i.message for i in issues])


if __name__ == "__main__":
    unittest.main()
