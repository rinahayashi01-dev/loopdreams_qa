import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import completeness

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""


def _guide_mismatch_issues(raw_text):
    pattern = parse(raw_text)
    issues = completeness.check(pattern)
    return [i for i in issues if i.location == "Stitch Guide"]


class TestStitchGuideBodyMismatch(unittest.TestCase):
    def test_named_stitch_only_in_body_annotations_not_flagged(self):
        # Real case (round 2/3 of the throw-blanket batch): the guide's named
        # stitch ("Shell Stitch") is genuinely worked in the body, but only
        # ever spelled out inside descriptive parenthetical annotations
        # ("(shell made)", "centre dc of next shell") rather than as a
        # recognized stitch token or an abbreviation-key entry. This must NOT
        # be flagged as a mismatch.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "STITCH GUIDE\n"
            "Shell Stitch: Fan-shaped clusters of 5 dc all worked into a\n"
            "single stitch, separated by sc anchors between each fan.\n"
            "Stitch multiple: Multiple of 6 + 1\n"
            "Foundation: Sc in 2nd ch from hook. *Skip 2 ch, work 5 dc all\n"
            "in the next ch (that's one complete shell), skip 2 ch, sc in the\n"
            "next ch; rep from * to end. Ch 3, turn.\n"
            "ABBREVIATIONS\n"
            "ch = chain · sc = single crochet · dc = double crochet · rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (19 sts)\n"
            "Row 2: Ch 1, sc in first st, *skip 2 sts, 5 dc in next st (shell made),\n"
            "skip 2 sts, sc in next st; rep from * across. Ch 3, turn. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        self.assertEqual(_guide_mismatch_issues(raw), [])

    def test_genuinely_unused_named_stitch_still_flagged(self):
        # Round-1-style real bug: the guide describes a named stitch whose
        # construction never appears anywhere in the body -- not as a token,
        # not as an abbreviation, not even as a literal word. This MUST still
        # be flagged; the fix for the case above must not mask this.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "STITCH GUIDE\n"
            "Sedge Stitch: A beginner-friendly textured stitch made from\n"
            "small three-stitch clusters (sc + hdc + dc) all worked into the\n"
            "same spot.\n"
            "Stitch multiple: Multiple of 3\n"
            "Foundation: (hdc, dc) in 2nd ch from hook. *Skip 2 ch, work\n"
            "(sc, hdc, dc) all in the next ch; rep from * to last ch, sc in last\n"
            "ch. Ch 1, turn.\n"
            "Working row: (hdc, dc) in the first sc. *Skip the hdc and dc of\n"
            "the previous cluster, work (sc, hdc, dc) in the next sc; rep\n"
            "from * to last st, sc in last st. Ch 1, turn.\n"
            "ABBREVIATIONS\n"
            "ch = chain · sc = single crochet · rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (19 sts)\n"
            "Row 2: Sc in first st, *ch 1, skip 1 st, sc in next st; rep from *\n"
            "across. Ch 1, turn. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        issues = _guide_mismatch_issues(raw)
        self.assertEqual(len(issues), 1)
        self.assertIn("Sedge Stitch", issues[0].message)

    def test_turning_chain_guide_with_matching_body_not_flagged(self):
        # A basic single-stitch technique guide ("Double Crochet (dc): ...
        # Turning chain: Ch 2, turn.") attached to a body that genuinely
        # works dc throughout. Must NOT be flagged -- the guide's own words
        # ("double crochet") are mirrored in the abbreviation key's
        # definition ("dc = double crochet"), and the heading's "(dc)"
        # parenthetical independently matches the abbreviation key too.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "STITCH GUIDE\n"
            "Double Crochet (dc): One of the most widely used stitches in\n"
            "crochet. Produces an open, flexible fabric.\n"
            "1. Yarn over FIRST, insert your hook under both loops of the next\n"
            "stitch, yarn over and pull through -- 3 loops on hook.\n"
            "2. Yarn over and pull through 2 loops, then the remaining 2.\n"
            "Turning chain: Ch 2, turn. The ch 2 does NOT count as a stitch.\n"
            "ABBREVIATIONS\n"
            "ch = chain · dc = double crochet · rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation chain:Ch 20, turn.\n"
            "Row 1: DC in 4th ch from hook and in each ch across. Ch 2, turn. (17 sts)\n"
            "Row 2: DC in each st across, ch 2, turn. (17 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        self.assertEqual(_guide_mismatch_issues(raw), [])

    def test_turning_chain_guide_mismatch_flagged(self):
        # Round-1-style real bug (throw blanket batch, Jul 2, round 1):
        # the guide teaches a basic dc technique via "Turning chain:", but
        # the body never actually works dc anywhere -- it's a plain sc +
        # ch-1 mesh instead. Before this fix, "turning chain:" wasn't in
        # complex_markers, so is_complex was False and this was skipped
        # entirely (a real, undetected defect). Must now be flagged.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "STITCH GUIDE\n"
            "Double Crochet (dc): One of the most widely used stitches in\n"
            "crochet. Produces an open, flexible fabric.\n"
            "1. Yarn over FIRST, insert your hook under both loops of the next\n"
            "stitch, yarn over and pull through -- 3 loops on hook.\n"
            "Turning chain: Ch 2, turn. The ch 2 does NOT count as a stitch.\n"
            "ABBREVIATIONS\n"
            "ch = chain · sc = single crochet · rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (19 sts)\n"
            "Row 2: Sc in first st, *ch 1, skip 1 st, sc in next st; rep from *\n"
            "across. Ch 1, turn. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        issues = _guide_mismatch_issues(raw)
        self.assertEqual(len(issues), 1)
        self.assertIn("Double Crochet", issues[0].message)

    def test_all_caps_colonless_heading_with_matching_body_not_flagged(self):
        # Real bug (scarf, Jul 15 batch, same "badge label" template family
        # as the Jul 12 sweater): the guide's own heading ("MOSS STITCH")
        # and its "Foundation"/"Working row" construction labels have NO
        # colon at all -- unlike every earlier sample's "Moss Stitch: ..."/
        # "Foundation: ...". Both the colon-requiring heading_re AND
        # construction_re used to find nothing at all here, producing a
        # false "(unnamed stitch)" mismatch even though the body's Row 1/
        # Row 2 text is a near-verbatim match for the guide's own
        # colonless "Foundation"/"Row 2" construction lines.
        raw = (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "STITCH GUIDE\n"
            "MOSS STITCH\n"
            "An alternating sc and chain-1 pattern that creates a tight, woven\n"
            "texture. Also called the linen stitch.\n"
            "Stitch multiple: Multiple of 2 + 1\n"
            "Foundation Sc in the 2nd ch from hook and in each ch across. Ch 1, turn.\n"
            "Row 2 Sc in the first stitch. *Ch 1, skip 1 st, sc in the next st; "
            "rep from * to end. Ch 1, turn.\n"
            "ABBREVIATIONS\n"
            "ch = chain · sc = single crochet · rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (19 sts)\n"
            "Row 2: Sc in first st, *ch 1, skip 1 st, sc in next st; rep from *\n"
            "across. Ch 1, turn. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        self.assertEqual(_guide_mismatch_issues(raw), [])

    def test_all_caps_colonless_heading_genuine_mismatch_still_flagged(self):
        # Same colonless template shape as above, but this time the guide's
        # named stitch genuinely doesn't match the body -- must still be
        # caught, confirming the fix above doesn't just wave everything
        # through.
        raw = (
            "Test Scarf\n"
            + MATERIALS_BLOCK
            + "STITCH GUIDE\n"
            "SEDGE STITCH\n"
            "A beginner-friendly textured stitch made from small three-stitch\n"
            "clusters (sc + hdc + dc) all worked into the same spot.\n"
            "Stitch multiple: Multiple of 3\n"
            "Foundation (hdc, dc) in 2nd ch from hook. Skip 2 ch, work (sc, hdc, "
            "dc) all in the next ch; rep to last ch, sc in last ch. Ch 1, turn.\n"
            "ABBREVIATIONS\n"
            "ch = chain · sc = single crochet · rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (19 sts)\n"
            "Row 2: Sc in first st, *ch 1, skip 1 st, sc in next st; rep from *\n"
            "across. Ch 1, turn. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        issues = _guide_mismatch_issues(raw)
        self.assertEqual(len(issues), 1)
        self.assertIn("Sedge", issues[0].message)


if __name__ == "__main__":
    unittest.main()
