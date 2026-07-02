import os
import tempfile
import unittest

from loopdreams_qa import batch


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


if __name__ == "__main__":
    unittest.main()
