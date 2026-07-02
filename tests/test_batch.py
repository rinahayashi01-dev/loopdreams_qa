import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from loopdreams_qa import batch

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""


def _pattern_text(stitch_guide_body, row1_text):
    return (
        "Test Blanket\n"
        + MATERIALS_BLOCK
        + "STITCH GUIDE\n"
        + stitch_guide_body + "\n"
        "ABBREVIATIONS\n"
        "ch = chain, sc = single crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        "Foundation:Ch 22, turn.\n"
        f"Row 1: {row1_text} (21 sts)\n"
        "Finishing\n"
        "Border: Fasten off. (40 sts)\n"
    )


class TestDiscoverPatterns(unittest.TestCase):
    def test_finds_pdf_and_docx_case_insensitively_ignores_others(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.pdf", "B.PDF", "c.docx", "d.DOCX", "notes.txt", ".DS_Store"):
                open(os.path.join(d, name), "w").close()
            found = [os.path.basename(p) for p in batch.discover_patterns(d)]
            self.assertEqual(found, ["B.PDF", "a.pdf", "c.docx", "d.DOCX"])

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(batch.discover_patterns(d), [])


class TestBatchSummary(unittest.TestCase):
    def _report(self, status, errors=0, warnings=0):
        return {"summary": {"status": status, "errors": errors, "warnings": warnings}}

    def test_counts_and_totals(self):
        results = {
            "a.pdf": self._report("PASS"),
            "b.pdf": self._report("REVIEW", warnings=1),
            "c.pdf": self._report("FAIL", errors=1),
            "d.pdf": self._report("FAIL", errors=2, warnings=1),
        }
        summary = batch._batch_summary(results)
        self.assertEqual(summary["files_checked"], 4)
        self.assertEqual(summary["pass"], 1)
        self.assertEqual(summary["review"], 1)
        self.assertEqual(summary["fail"], 2)
        self.assertEqual(summary["total_errors"], 3)
        self.assertEqual(summary["total_warnings"], 2)

    def test_all_pass_summary(self):
        results = {"a.pdf": self._report("PASS"), "b.pdf": self._report("PASS")}
        summary = batch._batch_summary(results)
        self.assertEqual(summary["fail"], 0)
        self.assertEqual(summary["total_errors"], 0)


class TestRunBatchCrossVariantIntegration(unittest.TestCase):
    """End-to-end run_batch() test with extract_text mocked per-filename --
    no real PDF fixtures needed. Placeholder files on disk only need to
    exist with a .pdf extension for discover_patterns() to find them;
    their actual (empty) content is never read since extract_text is
    patched in both cli.py and batch.py (each imports it into its own
    module namespace)."""

    def _fake_extract_text(self, texts_by_name, path):
        return texts_by_name[os.path.basename(path)]

    def test_mismatched_row1_surfaces_in_text_and_json_output(self):
        texts = {
            "moss.pdf": _pattern_text(
                "Moss Stitch: An alternating sc/ch1 pattern. Also called the linen stitch.",
                "Sc in 2nd ch from hook and in each ch across. Ch 1, turn.",
            ),
            "linen.pdf": _pattern_text(
                "Linen Stitch: An alternating sc/ch1 pattern. Also called the moss stitch.",
                "SC in 2nd ch from hook, *ch 1, skip 1 ch, SC in next ch; rep from * to end. Ch 1, turn.",
            ),
        }
        fake = lambda path: self._fake_extract_text(texts, path)

        with tempfile.TemporaryDirectory() as d:
            for name in texts:
                open(os.path.join(d, name), "w").close()

            with mock.patch("loopdreams_qa.cli.extract_text", side_effect=fake), \
                 mock.patch("loopdreams_qa.batch.extract_text", side_effect=fake):
                with contextlib.redirect_stdout(io.StringIO()):
                    combined = batch.run_batch(d, json_output=True)

        self.assertEqual(len(combined["cross_variant_issues"]), 1)
        issue = combined["cross_variant_issues"][0]
        self.assertEqual(issue["severity"], "warning")
        self.assertIn("missing its initial setup row", issue["message"])

    def test_no_mismatch_when_row1_shapes_agree(self):
        matching_row1 = "SC in 2nd ch from hook, *ch 1, skip 1 ch, SC in next ch; rep from * to end. Ch 1, turn."
        texts = {
            "moss.pdf": _pattern_text(
                "Moss Stitch: An alternating sc/ch1 pattern. Also called the linen stitch.", matching_row1,
            ),
            "linen.pdf": _pattern_text(
                "Linen Stitch: An alternating sc/ch1 pattern. Also called the moss stitch.", matching_row1,
            ),
        }
        fake = lambda path: self._fake_extract_text(texts, path)

        with tempfile.TemporaryDirectory() as d:
            for name in texts:
                open(os.path.join(d, name), "w").close()

            with mock.patch("loopdreams_qa.cli.extract_text", side_effect=fake), \
                 mock.patch("loopdreams_qa.batch.extract_text", side_effect=fake):
                with contextlib.redirect_stdout(io.StringIO()):
                    combined = batch.run_batch(d, json_output=True)

        self.assertEqual(combined["cross_variant_issues"], [])


if __name__ == "__main__":
    unittest.main()
