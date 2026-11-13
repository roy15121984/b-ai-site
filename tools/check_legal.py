"""The legal pages, checked after the Jekyll build (2026-11-13).

    python3 tools/check_legal.py _site [OWNERS_FOLDER]

1. Each page's Markdown has the sum tools/legal.sha256 gives it. With OWNERS_FOLDER, each
   page is the Owner's file it names byte for byte, less the one line the Owner had
   removed (2026-11-13): the draft notice and the blank line after it.
2. The built page shows its text as written: every line of the Markdown, its markup taken
   off, appears in the page's visible text unchanged (no curly quotes, no typographic
   dashes), and its headings are built as headings (nothing left unparsed).
3. The Hebrew pages are right to left (<html lang="he" dir="rtl">), the English left to right.
4. Every legal page and the home page link to all ten pages.
"""

from __future__ import annotations

import hashlib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ("privacy", "terms", "data-deletion", "dpa", "subprocessors")
PAGES = [f"{prefix}{doc}/" for doc in DOCS for prefix in ("", "he/")]
# The Owner's decision (2026-11-13): the draft notice removed from each page, nothing else
NOTICES = (
    "> Draft for review by the Owner. Not legal advice.".encode(),
    "> טיוטה לבדיקת הבעלים. אין לראות בה ייעוץ משפטי.".encode(),
)


def published_from(original: bytes) -> bytes:
    """The Owner's file less its draft notice line and the blank line after it."""
    lines = original.split(b"\n")
    at = [i for i, line in enumerate(lines) if line in NOTICES]
    if len(at) != 1 or lines[at[0] + 1] != b"":
        raise ValueError("not one draft notice followed by a blank line")
    return b"\n".join(lines[: at[0]] + lines[at[0] + 2 :])


class _Text(HTMLParser):
    """The visible text of a page (entities resolved; style, script and title left out)."""

    HIDDEN = ("style", "script", "title")
    # inline elements join the text around them; every other tag separates it
    INLINE = ("a", "abbr", "b", "code", "em", "i", "span", "strong", "sub", "sup")

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.hidden += tag in self.HIDDEN
        if tag not in self.INLINE:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        self.hidden -= tag in self.HIDDEN
        if tag not in self.INLINE:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def visible(markup: str) -> str:
    parser = _Text()
    parser.feed(markup)
    return " ".join("".join(parser.parts).split())


def plain(line: str) -> list[str]:
    """A Markdown line's text as a reader sees it: headings', quotes', lists' and tables'
    markers and the emphasis marks taken off; a table row gives one text per cell."""
    text = line.strip()
    if not text or text.startswith("<") or re.fullmatch(r"\|?[\s:|-]+\|?", text):
        return []  # an HTML line (the Hebrew files' <div>) or a table's separator
    text = re.sub(r"^#{1,6}\s+", "", text)
    text = re.sub(r"^(>\s*)+", "", text)
    text = re.sub(r"^([-*+]|\d+[.)])\s+", "", text)
    cells = text.strip("|").split("|") if text.startswith("|") else [text]
    found = []
    for cell in cells:
        cell = " ".join(re.sub(r"\*\*|\*|`", "", cell).split())
        if cell:
            found.append(cell)
    return found


def main(site: Path, owners: Path | None) -> list[str]:
    problems: list[str] = []
    sums = [
        line.split()
        for line in (ROOT / "tools" / "legal.sha256").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert sorted(row[1] for row in sums) == sorted(f"{p}index.md" for p in PAGES), sums
    for digest, path, original, original_digest in sums:
        page = (ROOT / path).read_bytes()
        if hashlib.sha256(page).hexdigest() != digest:
            problems.append(f"{path}: not the published sum")
        if owners is None:
            continue
        theirs = (owners / original).read_bytes()
        if hashlib.sha256(theirs).hexdigest() != original_digest:
            problems.append(f"{original}: the Owner's file differs from its recorded sum")
        if page != published_from(theirs):
            problems.append(f"{path}: not the Owner's {original} less the draft notice")
    links = [f'href="/{page}"' for page in PAGES]
    home = (site / "index.html").read_text(encoding="utf-8")
    problems += [f"index.html: no link {link}" for link in links if link not in home]
    for page in PAGES:
        built = (site / page / "index.html").read_text(encoding="utf-8")
        hebrew = page.startswith("he/")
        frame = '<html lang="he" dir="rtl">' if hebrew else '<html lang="en" dir="ltr">'
        if frame not in built:
            problems.append(f"{page}: not {frame}")
        problems += [f"{page}: no link {link}" for link in links if link not in built]
        shown = visible(built)
        source = (ROOT / page / "index.md").read_text(encoding="utf-8")
        for level in (1, 2, 3):  # the Markdown parsed, inside the Hebrew <div> too
            written = sum(line.startswith("#" * level + " ") for line in source.splitlines())
            if built.count(f"<h{level}") != written:
                problems.append(f"{page}: {written} level-{level} headings, {built.count(f'<h{level}')} built")
        if "**" in shown:
            problems.append(f"{page}: Markdown left unparsed (**)")
        for number, line in enumerate(source.splitlines(), start=1):
            for text in plain(line):
                if text not in shown:
                    problems.append(f"{page} line {number}: not shown as written: {text[:80]}")
    return problems


if __name__ == "__main__":
    found = main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
    for problem in found:
        print(problem)
    print(f"{len(PAGES)} legal pages checked: {len(found)} problem(s)")
    sys.exit(1 if found else 0)
