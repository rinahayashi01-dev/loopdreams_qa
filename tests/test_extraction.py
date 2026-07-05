import sys
import unittest
from unittest import mock

from loopdreams_qa import extraction


class TestOCRFallbackGracefulDegradation(unittest.TestCase):
    def test_missing_ocr_deps_returns_empty_strings_instead_of_crashing(self):
        # Real bug (tote bag, Jul 5 batch): this environment doesn't have
        # pdf2image installed. Previously, any page with near-empty
        # pdfplumber text (e.g. a pure-image screenshot page with zero
        # embedded text at all, unlike every prior sample which always
        # had at least a URL/timestamp footer keeping it above the OCR
        # threshold) crashed extraction entirely with ModuleNotFoundError,
        # even though the actual pattern content was on earlier, perfectly
        # readable text-layer pages. Simulates the missing-dependency case
        # deterministically regardless of what's actually installed in
        # whatever environment runs this test.
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "pdf2image":
                raise ModuleNotFoundError("No module named 'pdf2image'")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            results = extraction._ocr_pages("irrelevant/path.pdf", [3, 4, 5])

        self.assertEqual(results, ["", "", ""])

    def test_missing_ocr_deps_prints_a_warning_not_silence(self):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "pdf2image":
                raise ModuleNotFoundError("No module named 'pdf2image'")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            with mock.patch("sys.stderr") as mock_stderr:
                extraction._ocr_pages("irrelevant/path.pdf", [0])

        written = "".join(call.args[0] for call in mock_stderr.write.call_args_list if call.args)
        self.assertIn("OCR fallback unavailable", written)


if __name__ == "__main__":
    unittest.main()
