"""Plain-text view of an NJT document, with paging and search.

A complete NJT page is 1-3 MB of HTML (most of it markup and page chrome); a model client
truncates a tool result long before that. This module turns the reconstructed page into the
legal text only, and serves it in pages with offsets the caller can continue from, so a long
act or a municipal building regulation can be read in full instead of silently cut off.

What counts as legal text: everything inside elements whose ``id`` is an NJT content slice
(``sc{document-id}-{n}``) - title, subtitle, structure headings, sections, points, tables and
annexes. Page chrome, scripts, footnote bodies (``div.footnote``) and footnote markers
(``sup.fnSup``) are left out; the amendment history they carry stays available in the HTML
returned by the ``*_text`` tools.
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

_CONTENT_ID = re.compile(r"^sc\d")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
         "param", "source", "track", "wbr"}
_BLOCK = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "ul", "ol",
          "section", "article", "header", "footer", "blockquote"}
_SKIP_TAGS = {"script", "style", "noscript", "template"}
_ATTACHMENT_HREF = re.compile(r"^/?document/.+", re.IGNORECASE)


_ANNEX_LABEL = re.compile(r"(\d+(?:\.\d+)*\.\s*mell[eé]klet)", re.IGNORECASE)


def _annex_label(preceding: str) -> str | None:
    """The last 'N.N. melleklet' heading before an attachment link, if any."""
    found = _ANNEX_LABEL.findall(preceding[-1500:])
    return " ".join(found[-1].split()) if found else None


def _skipped(tag: str, classes: set[str]) -> bool:
    return (
        tag in _SKIP_TAGS
        or (tag == "div" and "footnote" in classes)
        or (tag == "sup" and "fnSup" in classes)
    )


class _TextExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url.rstrip("/")
        self._stack: list[str] = []
        self._capture_at: int | None = None
        self._skip_at: int | None = None
        self._link_stack: list[str | None] = []
        self.parts: list[str] = []
        self.attachments: list[dict[str, str]] = []
        self._link_text: list[str] = []
        self._cell_at: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag in _VOID:
            if tag == "br" and self._capturing():
                self.parts.append(" " if self._cell_at is not None else "\n")
            return
        self._stack.append(tag)
        depth = len(self._stack)
        if self._skip_at is None and _skipped(tag, classes):
            self._skip_at = depth
            if tag == "sup" and self._capture_at is not None:
                # "rendelet<sup>1</sup>alapjan": keep the words apart once the marker goes.
                self.parts.append(" ")
        if tag == "a":
            href = attributes.get("href") or ""
            url = None
            if self._capturing() and _ATTACHMENT_HREF.match(href):
                url = f"{self._base_url}/{href.lstrip('/')}"
                self._link_text = []
            self._link_stack.append(url)
        if self._capture_at is None and _CONTENT_ID.match(attributes.get("id") or ""):
            self._capture_at = depth
        if tag in {"td", "th"} and self._cell_at is None:
            self._cell_at = depth
        if self._capturing():
            if tag in {"td", "th"}:
                self.parts.append(" | ")
            elif tag in _BLOCK and tag != "tr" and self._cell_at is not None:
                self.parts.append(" ")  # keep a table row on one line
            elif tag in _BLOCK:
                self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" and self._capturing():
            self.parts.append(" " if self._cell_at is not None else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID or tag not in self._stack:
            return
        # Pop to the matching open tag; tolerates unclosed inline elements.
        while self._stack:
            depth = len(self._stack)
            current = self._stack.pop()
            if current == "a" and self._link_stack:
                url = self._link_stack.pop()
                if url and self._capturing():
                    self.parts.append(f" [PDF: {url}]")
                    title = " ".join("".join(self._link_text).split())
                    label = _annex_label("".join(self.parts[-200:]))
                    if label and label not in title:
                        title = f"{label}: {title}"
                    if all(item["url"] != url for item in self.attachments):
                        self.attachments.append({"title": title, "url": url})
            if self._capturing() and current in _BLOCK:
                in_cell = self._cell_at is not None and depth > self._cell_at
                self.parts.append(" " if in_cell else "\n")
            if self._cell_at is not None and depth <= self._cell_at:
                self._cell_at = None
            if self._skip_at is not None and depth <= self._skip_at:
                self._skip_at = None
            if self._capture_at is not None and depth <= self._capture_at:
                self._capture_at = None
            if current == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._capturing():
            if "table" in self._stack:
                # Source line breaks inside a table must not split a row across lines.
                data = data.replace("\n", " ")
            self.parts.append(data)
            if self._link_stack and self._link_stack[-1]:
                self._link_text.append(data)

    def _capturing(self) -> bool:
        return self._capture_at is not None and self._skip_at is None


def html_to_text(html: str, base_url: str = "https://njt.jog.gov.hu") -> str:
    """Extract the legal text of an NJT document page as plain text.

    Annexes NJT publishes only as attached files (typically plan sheets of a municipal
    building regulation) appear in the text as ``[PDF: <absolute url>]`` after their notice.
    """
    return extract(html, base_url)[0]


def extract(html: str, base_url: str = "https://njt.jog.gov.hu") -> tuple[str, list[dict]]:
    """Return (plain text, attached annex files as ``{"title", "url"}``)."""
    parser = _TextExtractor(base_url)
    parser.feed(html)
    parser.close()
    raw = "".join(parser.parts).replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in raw.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), parser.attachments


def _fold(text: str) -> str:
    """Lower-case, accent-free copy with exactly the same length (offsets stay valid)."""
    out = []
    for ch in text.lower():
        base = unicodedata.normalize("NFKD", ch)
        stripped = "".join(c for c in base if not unicodedata.combining(c))
        out.append(stripped[:1] if len(stripped) >= 1 else ch)
    return "".join(out)


def search_text(text: str, query: str, limit: int = 30, context: int = 90) -> list[dict]:
    """Find a phrase (case- and accent-insensitive); return offsets with a short snippet."""
    needle = _fold(query.strip())
    if not needle:
        return []
    haystack = _fold(text)
    hits: list[dict] = []
    pos = haystack.find(needle)
    while pos != -1 and len(hits) < limit:
        left = max(0, pos - context)
        right = min(len(text), pos + len(needle) + context)
        snippet = " ".join(text[left:right].split())
        hits.append({"start": pos, "snippet": snippet})
        pos = haystack.find(needle, pos + len(needle))
    return hits


def page(text: str, start: int, max_chars: int) -> tuple[str, int, int | None]:
    """Return (chunk, end, next_start). Cuts at a line break near the limit when possible."""
    start = max(0, min(start, len(text)))
    end = min(len(text), start + max_chars)
    if end < len(text):
        cut = text.rfind("\n", start + int(max_chars * 0.8), end)
        if cut > start:
            end = cut + 1
    return text[start:end], end, (end if end < len(text) else None)
