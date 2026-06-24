"""Tests for the batch runner (batch.py)."""

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loopdreams_qa.batch import (
    CSV_FIELDNAMES,
    _report_to_csv_row,
    find_pattern_files,
    run_batch,
    write_csv,
    write_json_dir,
)

_SAMPLE_REPORT = {
    "source": "/tmp/my_pattern.docx",
    "declared_system": "US",
    "declared_system_source": "explicit",
    "rounds_parsed": 4,
    "sections_found": ["gauge", "instructions", "materials"],
    "extraction_warnings": [],
    "issue_counts": {"error": 1, "warning": 2, "info": 0},
    "issues": [
        {
            "check": "stitch_count",
            "severity": "error",
            "location": "Round 3",
            "message": "Expected 12 stitches, got 11",
        },
        {
            "check": "completeness",
            "severity": "warning",
            "location": "Pattern",
            "message": "Missing finishing section",
        },
    ],
}


class CsvRowTests(unittest.TestCase):
    def test_all_fieldnames_present(self):
        row = _report_to_csv_row(_SAMPLE_REPORT)
        for field in CSV_FIELDNAMES:
            self.assertIn(field, row)

    def test_basename_only_not_full_path(self):
        row = _report_to_csv_row(_SAMPLE_REPORT)
        self.assertEqual(row["file"], "my_pattern.docx")

    def test_counts(self):
        row = _report_to_csv_row(_SAMPLE_REPORT)
        self.assertEqual(row["errors"], 1)
        self.assertEqual(row["warnings"], 2)
        self.assertEqual(row["infos"], 0)

    def test_issues_concatenated_with_separator(self):
        row = _report_to_csv_row(_SAMPLE_REPORT)
        self.assertIn("Round 3", row["issues"])
        self.assertIn("Missing finishing section", row["issues"])
        self.assertIn("|", row["issues"])

    def test_none_system_becomes_unknown(self):
        row = _report_to_csv_row({**_SAMPLE_REPORT, "declared_system": None})
        self.assertEqual(row["declared_system"], "unknown")

    def test_no_issues_gives_empty_string(self):
        report = {**_SAMPLE_REPORT, "issues": [], "issue_counts": {"error": 0, "warning": 0, "info": 0}}
        row = _report_to_csv_row(report)
        self.assertEqual(row["issues"], "")


class FindPatternFilesTests(unittest.TestCase):
    def test_finds_docx_and_pdf_ignores_other(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.docx").touch()
            (Path(d) / "b.pdf").touch()
            (Path(d) / "c.txt").touch()
            names = [f.name for f in find_pattern_files(d)]
            self.assertIn("a.docx", names)
            self.assertIn("b.pdf", names)
            self.assertNotIn("c.txt", names)

    def test_returns_sorted_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "z.docx").touch()
            (Path(d) / "a.pdf").touch()
            self.assertEqual([f.name for f in find_pattern_files(d)], ["a.pdf", "z.docx"])

    def test_empty_folder_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(find_pattern_files(d), [])

    def test_case_insensitive_extension(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x.PDF").touch()
            (Path(d) / "y.DOCX").touch()
            names = [f.name for f in find_pattern_files(d)]
            self.assertIn("x.PDF", names)
            self.assertIn("y.DOCX", names)


class RunBatchTests(unittest.TestCase):
    def test_bad_file_produces_extraction_error_not_exception(self):
        results = run_batch([Path("/nonexistent/missing.docx")])
        self.assertEqual(len(results), 1)
        report = results[0]
        self.assertEqual(report["issue_counts"]["error"], 1)
        self.assertEqual(report["issues"][0]["check"], "extraction")
        self.assertIn("Failed to process", report["issues"][0]["message"])

    def test_delegates_to_cli_run(self):
        with patch("loopdreams_qa.batch.qa_run", return_value=_SAMPLE_REPORT) as mock:
            results = run_batch([Path("/tmp/test.docx")])
        mock.assert_called_once_with("/tmp/test.docx")
        self.assertEqual(results, [_SAMPLE_REPORT])

    def test_one_bad_file_does_not_stop_others(self):
        good_report = {**_SAMPLE_REPORT, "source": "/tmp/good.docx"}
        call_count = 0

        def fake_run(path):
            nonlocal call_count
            call_count += 1
            if "bad" in path:
                raise ValueError("corrupt file")
            return good_report

        with patch("loopdreams_qa.batch.qa_run", side_effect=fake_run):
            results = run_batch([Path("/tmp/bad.docx"), Path("/tmp/good.docx")])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["issues"][0]["check"], "extraction")
        self.assertEqual(results[1]["declared_system"], "US")


class WriteCsvTests(unittest.TestCase):
    def test_header_and_one_data_row(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".csv", delete=False) as f:
            tmp = f.name
        try:
            write_csv([_SAMPLE_REPORT], tmp)
            with open(tmp, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["file"], "my_pattern.docx")
            self.assertEqual(rows[0]["errors"], "1")
        finally:
            os.unlink(tmp)

    def test_multiple_rows(self):
        r2 = {**_SAMPLE_REPORT, "source": "/tmp/other.pdf", "issue_counts": {"error": 0, "warning": 0, "info": 1}}
        with tempfile.NamedTemporaryFile(mode="r", suffix=".csv", delete=False) as f:
            tmp = f.name
        try:
            write_csv([_SAMPLE_REPORT, r2], tmp)
            with open(tmp, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["file"], "other.pdf")
        finally:
            os.unlink(tmp)


class WriteJsonDirTests(unittest.TestCase):
    def test_writes_named_file(self):
        with tempfile.TemporaryDirectory() as d:
            write_json_dir([_SAMPLE_REPORT], d)
            out = Path(d) / "my_pattern_qa.json"
            self.assertTrue(out.exists())
            data = json.loads(out.read_text())
            self.assertEqual(data["declared_system"], "US")

    def test_creates_output_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as d:
            new_dir = os.path.join(d, "sub", "nested")
            write_json_dir([_SAMPLE_REPORT], new_dir)
            self.assertTrue(Path(new_dir).is_dir())

    def test_multiple_files_get_separate_json(self):
        r2 = {**_SAMPLE_REPORT, "source": "/tmp/other.pdf"}
        with tempfile.TemporaryDirectory() as d:
            write_json_dir([_SAMPLE_REPORT, r2], d)
            self.assertTrue((Path(d) / "my_pattern_qa.json").exists())
            self.assertTrue((Path(d) / "other_qa.json").exists())


if __name__ == "__main__":
    unittest.main()
