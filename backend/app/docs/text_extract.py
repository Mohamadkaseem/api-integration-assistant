"""Turn PDFs and web pages into plain text for the AI to read."""

import io
import re
from html.parser import HTMLParser

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_PAGES = 500


class ExtractError(ValueError):
    pass


def pdf_to_text(data: bytes) -> tuple[str, list[str]]:
    """Return (text, warnings)."""
    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractError("This PDF is password-protected. Remove the password and upload it again.")
        pages = reader.pages
        if len(pages) > MAX_PDF_PAGES:
            warnings.append(f"Only the first {MAX_PDF_PAGES} of {len(pages)} pages were read.")
        texts = []
        for number, page in enumerate(list(pages)[:MAX_PDF_PAGES], start=1):
            texts.append(f"\n[Page {number}]\n{page.extract_text() or ''}")
    except PdfReadError as exc:
        raise ExtractError(f"Could not read this PDF ({exc}).") from exc
    text = "".join(texts)
    if len(re.sub(r"\[Page \d+\]|\s", "", text)) < 100:
        raise ExtractError(
            "This PDF contains almost no text - it is probably scanned images. "
            "Use a text-based PDF, or copy the text and paste it instead."
        )
    return text, warnings


class _HTMLText(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "section", "article", "table", "dt", "dd"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, text) of a web page, without scripts, menus and styling."""
    parser = _HTMLText()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return parser.title.strip(), text
