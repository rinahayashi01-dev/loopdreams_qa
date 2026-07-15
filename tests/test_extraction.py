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


class TestOCRProgressVisibility(unittest.TestCase):
    # Real motivation (scarf/sweater, Jul 12-15 batches): a new LoopDreams
    # export template renders every page as vector graphics with no text
    # layer at all, so every page needs OCR (~15-20s/page) -- a multi-page
    # file running silently for minutes is easy to mistake for a hang.
    # These progress lines go to stderr specifically so they never pollute
    # stdout (e.g. batch --json's single combined JSON document).
    def test_ocr_pages_prints_per_page_progress(self):
        with mock.patch("pdf2image.convert_from_path", return_value=[mock.Mock()]), \
             mock.patch("pytesseract.image_to_string", return_value="text"):
            with mock.patch("sys.stderr") as mock_stderr:
                extraction._ocr_pages("irrelevant/path.pdf", [2, 5, 9])

        written = "".join(call.args[0] for call in mock_stderr.write.call_args_list if call.args)
        self.assertIn("page 3 (1/3)", written)
        self.assertIn("page 6 (2/3)", written)
        self.assertIn("page 10 (3/3)", written)

    def test_extract_pdf_notes_how_many_pages_need_ocr(self):
        fake_page = mock.Mock()
        fake_page.extract_text.return_value = ""
        fake_pdf = mock.MagicMock()
        fake_pdf.__enter__.return_value.pages = [fake_page, fake_page]

        with mock.patch("pdfplumber.open", return_value=fake_pdf), \
             mock.patch.object(extraction, "_ocr_pages", return_value=["a", "b"]):
            with mock.patch("sys.stderr") as mock_stderr:
                extraction._extract_pdf("some-pattern.pdf")

        written = "".join(call.args[0] for call in mock_stderr.write.call_args_list if call.args)
        self.assertIn("some-pattern.pdf", written)
        self.assertIn("2 page(s)", written)


if __name__ == "__main__":
    unittest.main()
