"""The legal pages, checked after the Jekyll build (2026-11-13).

    python3 tools/check_legal.py _site [OWNERS_FOLDER]

1. Each page's Markdown is byte for byte the Owner's file it names (tools/legal.sha256);
   with OWNERS_FOLDER, the Owner's files themselves are checked against the same sums.
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
    assert sorted(path for _, path, _ in sums) == sorted(f"{p}index.md" for p in PAGES), sums
    for digest, path, original in sums:
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            problems.append(f"{path}: not byte for byte the Owner's {original}")
        if owners is not None and hashlib.sha256((owners / original).read_bytes()).hexdigest() != digest:
            problems.append(f"{original}: the Owner's file differs from the published sum")
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
