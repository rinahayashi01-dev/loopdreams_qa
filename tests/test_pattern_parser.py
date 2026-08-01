import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import completeness, stitch_count

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""


class TestRepeatNMoreTimesShorthand(unittest.TestCase):
    def test_repeat_rows_x_n_more_times_closes_the_row_gap(self):
        # Real phrasing found on a real sample (tote bag, Jul 4 batch):
        # "Repeat Rows 2-3 x 38 more times." with NO leading "Rows 4-79:"
        # label at all, unlike the previously-supported "Rows N-M: Repeat
        # Row(s) P-Q." shorthand. Before this fix, this phrase was
        # invisible to the parser entirely, so the row-gap completeness
        # check saw a hard gap between Row 3 and Row 80 and raised a false
        # "no instructions for Rows 4-79" error on an otherwise-correct
        # pattern.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, fpdc = front post double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 72.\n"
            "Row 1: DC in 4th ch from hook and in each ch across. Ch 2, turn. (69 sts)\n"
            "Row 2: Ch 2 (counts as dc), skip first st, *fpdc around next st, dc in next 2 sts; "
            "rep from * to last 2 sts, fpdc around next st, dc in top of ch. Ch 2, turn. (69 sts)\n"
            "Row 3: Ch 2 (counts as dc), skip first st, *dc in next st, fpdc around next 2 sts; "
            "rep from * to last 2 sts, dc in next st, dc in top of ch. Ch 2, turn. (69 sts)\n"
            "Repeat Rows 2–3 × 38 more times.\n"
            "Row 80: Ch 2 (counts as dc), skip first st, *fpdc around next st, dc in next 2 sts; "
            "rep from * to last 2 sts, fpdc around next st, dc in top of ch. Fasten off. (69 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)

        labels = [r.label for r in pattern.rows]
        self.assertIn("Rows 4-79", labels)

        gap_row = next(r for r in pattern.rows if r.label == "Rows 4-79")
        self.assertEqual(gap_row.row_start, 4)
        self.assertEqual(gap_row.row_end, 79)
        self.assertEqual(gap_row.referenced_rows, [2, 3])
        self.assertEqual(gap_row.declared_count, 69)

        issues = completeness.check(pattern)
        row_gap_issues = [i for i in issues if "Rows 4" in i.message or "jumps from" in i.message]
        self.assertEqual(row_gap_issues, [])

    def test_without_the_fix_shape_missing_anchor_is_left_unrecognized(self):
        # If the referenced range's last row was never actually parsed
        # (e.g. a typo referencing a row number that doesn't exist), don't
        # guess an anchor -- leave it unrecognized rather than silently
        # inventing a row range.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 22, turn.\n"
            "Row 1: DC in 4th ch from hook and in each ch across. Ch 2, turn. (19 sts)\n"
            "Repeat Rows 2-3 x 5 more times.\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        labels = [r.label for r in pattern.rows]
        self.assertNotIn("Rows 4-13", labels)


class TestZipperLinerSectionBoundary(unittest.TestCase):
    def test_zipper_liner_and_tester_headings_dont_bleed_into_finishing(self):
        # Real bug (tote bag, Jul 5 batch): neither "Adding a Zipper &
        # Liner" nor "TESTER EXPECTATIONS" were recognized section
        # headings, so their content (and everything after) got silently
        # absorbed into "finishing"'s raw_text. That broke the Handles
        # component's own "(N sts)" extraction, which anchors to the end
        # of the whole blob to find the trailing count -- with unrelated
        # trailing content glued on, the real count was no longer at the
        # true end, producing a false "missing stitch count" warning on a
        # pattern that actually states one.
        raw = (
            "Test Tote Bag\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 22, turn.\n"
            "Row 1: SC in 2nd ch from hook and in each ch across. Ch 1, turn. (21 sts)\n"
            "Finishing\n"
            "Assembly: Fold panel in half. Seam both side edges.\n"
            "Creating Handles\n"
            "Handles (make 2): Ch 21. SC in 2nd ch from hook and each ch across. Ch 1, turn. "
            "Fasten off. (20 sts)\n"
            "Adding a Zipper & Liner\n"
            "Adding a Liner: Cut fabric to size. Sew the liner and whip stitch it in place.\n"
            "TESTER EXPECTATIONS\n"
            "Thank you for testing! Did the stitch counts work out?\n"
        )
        pattern = parse(raw)

        section_names = [s.name for s in pattern.sections]
        self.assertIn("zipper_liner", section_names)
        self.assertIn("ignored_meta", section_names)

        finishing = next(s for s in pattern.sections if s.name == "finishing")
        self.assertNotIn("Zipper", finishing.raw_text)
        self.assertNotIn("TESTER", finishing.raw_text.upper())

        issues = completeness.check(pattern)
        component_count_issues = [i for i in issues if "Handles" in i.location and "never states" in i.message]
        self.assertEqual(component_count_issues, [])


class TestDuplicateScStsAnnotation(unittest.TestCase):
    def test_leading_sc_count_stripped_leaving_only_sts_as_declared(self):
        # Real phrasing found on a real sample (mittens, Jul 7 batch):
        # rows state BOTH a stitch-abbreviation count and a generic count,
        # e.g. "...(30 sc) (30 sts)". Before this fix, the earlier "(30
        # sc)" stayed embedded in the row's instruction text and got
        # tokenized as an "unrecognized clause" -- noise on every single
        # row of the pattern.
        raw = (
            "Test Mitten\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 22, turn.\n"
            "Row 1: Sc in each st across. (21 sc) (21 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        row1 = pattern.rows[0]
        self.assertEqual(row1.declared_count, 21)
        self.assertNotIn("sc)", row1.raw_text)
        types = [c.clause_type for c in row1.clauses]
        self.assertNotIn("unknown", types)


class TestTitleMetadataLineLabel(unittest.TestCase):
    # Real sample (scarf, Jul 15 batch): the metadata line reads "Scarf -
    # Beginner - Generated: July 15, 2026" -- an extra "Generated:" label
    # before the date that every earlier sample's metadata line ("Tote Bag
    # - Intermediate - July 10, 2026") never had. Without tolerating this,
    # the title heuristic never finds the metadata line at all and falls
    # back to the first non-empty line, which (on an OCR'd/vector-only PDF
    # with a decorative logo graphic) is scattered logo garbage instead of
    # the real title.
    def test_generated_label_before_date_still_locates_title(self):
        raw = (
            "ypDre\no ca\n\nScarf — Jul 15\n\nScarf - Beginner - Generated: July 15, 2026\n\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        self.assertEqual(pattern.title, "Scarf — Jul 15")

    def test_plain_metadata_line_without_label_still_works(self):
        # Confirms the fix doesn't regress the original, no-label format.
        raw = (
            "Tote Bag — Jul 10\n\nTote Bag - Intermediate - July 10, 2026\n\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        self.assertEqual(pattern.title, "Tote Bag — Jul 10")


class TestPlainUnlabeledFinishingContent(unittest.TestCase):
    def test_bare_fasten_off_with_no_label_is_recognized_not_dropped(self):
        # Real generator/PDF shape (Dishcloth/Throw Blanket/square Coaster
        # beginner variant, generate-pattern's buildGenericFlatRows -- a
        # flat single-panel construction with no separate Border/Pocket/
        # Handles component): the Finishing section's own content is a
        # plain, unlabeled closing instruction ("Fasten off, weave in
        # ends."), confirmed against the real PDF renderer
        # (PatternPrintView.tsx), which prints this under a bare "Finishing"
        # heading with no label text at all. Before this fix, _parse_
        # finishing only recognized Border:/Pocket:/"<Label> (make N):"
        # shapes, so this content was silently dropped -- a real, complete
        # pattern then produced a false "no fasten off" REVIEW (previously
        # misdiagnosed as a genuine content gap in these templates; the
        # content was always there, this checker just couldn't see it).
        raw = (
            "Test Dishcloth\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet\n"
            "PATTERN STEPS\n"
            "Foundation: Ch 39, turn.\n"
            "Row 1: Skip the first 3 chains from the hook (they don't count as a stitch). "
            "Dc in the next chain and in each ch across. Ch 3, turn. (36 sts)\n"
            "Row 2: Dc in each st across. (36 sts)\n"
            "Finishing\n"
            "Fasten off, weave in ends.\n"
        )
        pattern = parse(raw)
        finishing_rows = [r for r in pattern.rows if r.label == "Finishing"]
        self.assertEqual(len(finishing_rows), 1)
        self.assertEqual(finishing_rows[0].row_start, -1)
        clause_types = [c.clause_type for c in finishing_rows[0].clauses]
        self.assertIn("fasten_off", clause_types)

        issues = stitch_count.check(pattern) + completeness.check(pattern)
        fasten_off_issues = [i for i in issues if "fasten off" in i.message.lower()]
        self.assertEqual(fasten_off_issues, [], f"unexpected: {fasten_off_issues}")

    def test_unrelated_prose_with_no_closing_content_still_left_unrecognized(self):
        # Scoping check: the fallback only claims a chunk that actually
        # tokenizes into real closing content (fasten_off/closure) -- it
        # must not sweep up arbitrary unrelated Finishing-section prose as
        # a bogus row.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet\n"
            "PATTERN STEPS\n"
            "Foundation: Ch 22, turn.\n"
            "Row 1: Dc in 3rd ch from hook and in each ch across. Ch 2, turn. (19 sts)\n"
            "Finishing\n"
            "Some unrelated caption text with no real instruction at all.\n"
        )
        pattern = parse(raw)
        self.assertNotIn("Finishing", [r.label for r in pattern.rows])


if __name__ == "__main__":
    unittest.main()
