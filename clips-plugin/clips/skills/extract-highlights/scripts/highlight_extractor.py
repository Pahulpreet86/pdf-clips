#!/usr/bin/env python3
"""
clips
=====

Ingest a PDF that was highlighted / commented in Adobe Acrobat Reader (or any
viewer that writes standard PDF markup annotations) and produce a clean Markdown
file. Every highlighted passage — together with any sticky-note comment attached
to it — is grouped under the chapter / section heading it appears within, in
natural reading order.

Why a coordinate-based approach?
--------------------------------
Acrobat does NOT store the highlighted words inside the annotation. It stores the
*coordinates* of the highlight (QuadPoints). This tool reads those coordinates and
pulls out the text that physically sits underneath them, which is the only reliable
way to recover what the reader actually marked.

Chapter mapping is done primarily by page number. When several headings live on the
same page, each heading's true vertical position is located by searching the page
for its title text — TOC destination coordinates are unreliable across PDFs, so we
avoid depending on them.

Usage
-----
    python highlight_extractor.py input.pdf
    python highlight_extractor.py input.pdf -o notes.md
    python highlight_extractor.py input.pdf --include-empty --types highlight underline

Requires: pymupdf  (pip install pymupdf)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

try:
    import pymupdf  # PyMuPDF >= 1.24
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "This tool needs PyMuPDF. Install it with:\n\n    pip install pymupdf\n\n"
    )
    raise SystemExit(1)


# Annotation subtypes we treat as "markup on text" (they carry QuadPoints).
MARKUP_TYPES = {
    pymupdf.PDF_ANNOT_HIGHLIGHT: "highlight",
    pymupdf.PDF_ANNOT_UNDERLINE: "underline",
    pymupdf.PDF_ANNOT_STRIKE_OUT: "strikeout",
    pymupdf.PDF_ANNOT_SQUIGGLY: "squiggly",
}
# Sticky notes: a free-floating comment with no highlighted text of its own.
NOTE_TYPE = pymupdf.PDF_ANNOT_TEXT


@dataclass
class Highlight:
    page: int          # 0-based page index
    y_top: float       # top y-coordinate (top-left origin) for ordering
    kind: str          # "highlight" | "underline" | "note" | ...
    text: str          # the highlighted passage (empty for pure sticky notes)
    note: str          # the attached comment / sticky-note body
    color: Optional[str] = None


@dataclass
class Section:
    page: int
    y_top: float
    level: int         # 1 = top-level chapter, 2 = section, ...
    title: str
    highlights: list = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def _rgb_to_hex(color) -> Optional[str]:
    if not color:
        return None
    stroke = color.get("stroke") or color.get("fill")
    if not stroke:
        return None
    try:
        return "#" + "".join(f"{int(round(c * 255)):02x}" for c in stroke[:3])
    except Exception:
        return None


def _text_under_annot(page, annot) -> str:
    """Recover the text sitting beneath a markup annotation via its quad points."""
    verts = annot.vertices
    pieces: list[str] = []
    if verts and len(verts) >= 4:
        # Vertices arrive as groups of 4 points, one quad per highlighted line.
        for i in range(0, len(verts), 4):
            quad = verts[i : i + 4]
            if len(quad) < 4:
                continue
            xs = [p[0] for p in quad]
            ys = [p[1] for p in quad]
            rect = pymupdf.Rect(min(xs), min(ys), max(xs), max(ys))
            chunk = page.get_textbox(rect).strip()
            if chunk:
                pieces.append(chunk)
    else:
        pieces.append(page.get_textbox(annot.rect).strip())
    # Collapse internal whitespace / hyphenated line breaks lightly.
    joined = " ".join(pieces)
    return " ".join(joined.split())


def extract_highlights(doc, wanted_kinds: set[str]) -> list[Highlight]:
    out: list[Highlight] = []
    for pno in range(doc.page_count):
        page = doc.load_page(pno)
        for annot in page.annots() or []:
            atype = annot.type[0]
            if atype in MARKUP_TYPES and MARKUP_TYPES[atype] in wanted_kinds:
                kind = MARKUP_TYPES[atype]
                text = _text_under_annot(page, annot)
                note = (annot.info.get("content") or "").strip()
                if not text and not note:
                    continue
                out.append(
                    Highlight(
                        page=pno,
                        y_top=annot.rect.y0,
                        kind=kind,
                        text=text,
                        note=note,
                        color=_rgb_to_hex(annot.colors),
                    )
                )
            elif atype == NOTE_TYPE and "note" in wanted_kinds:
                note = (annot.info.get("content") or "").strip()
                if note:
                    out.append(
                        Highlight(
                            page=pno,
                            y_top=annot.rect.y0,
                            kind="note",
                            text="",
                            note=note,
                        )
                    )
    out.sort(key=lambda h: (h.page, h.y_top))
    return out


def build_sections(doc) -> list[Section]:
    """Turn the PDF outline into ordered sections with resolved on-page positions."""
    toc = doc.get_toc(simple=True)  # [level, title, page(1-based)]
    sections: list[Section] = []
    for level, title, page1 in toc:
        pno = max(0, page1 - 1)
        y_top = 0.0
        try:
            page = doc.load_page(pno)
            hits = page.search_for(title, quads=False)
            if not hits:
                # Retry with a trimmed leading number, e.g. "2.1 Sampling"
                trimmed = title.split(" ", 1)[-1] if " " in title else title
                hits = page.search_for(trimmed, quads=False)
            if hits:
                y_top = min(h.y0 for h in hits)
        except Exception:
            pass
        sections.append(Section(page=pno, y_top=y_top, level=level, title=title.strip()))
    sections.sort(key=lambda s: (s.page, s.y_top, s.level))
    return sections


def assign_to_sections(highlights: list[Highlight], sections: list[Section]):
    """Attach each highlight to the deepest section boundary that precedes it."""
    front_matter = Section(page=-1, y_top=0.0, level=1, title="Front matter")
    if not sections:
        # No outline in the PDF: fall back to one pseudo-section per page.
        by_page: dict[int, Section] = {}
        ordered: list[Section] = []
        for h in highlights:
            sec = by_page.get(h.page)
            if sec is None:
                sec = Section(page=h.page, y_top=0.0, level=1,
                              title=f"Page {h.page + 1}")
                by_page[h.page] = sec
                ordered.append(sec)
            sec.highlights.append(h)
        return ordered

    used_front = False
    for h in highlights:
        chosen = None
        for sec in sections:
            if (sec.page, sec.y_top) <= (h.page, h.y_top):
                chosen = sec
            else:
                break
        if chosen is None:
            front_matter.highlights.append(h)
            used_front = True
        else:
            chosen.highlights.append(h)

    result = ([front_matter] if used_front else []) + sections
    return result


# --------------------------------------------------------------------------- #
# Book / document metadata
# --------------------------------------------------------------------------- #
import re as _re


def _xmp_field(xmp: str, *tags: str) -> Optional[str]:
    """Pull the first value of any of the given XMP tags (e.g. dc:publisher)."""
    if not xmp:
        return None
    for tag in tags:
        m = _re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xmp, _re.S | _re.I)
        if not m:
            # Some XMP fields are self-contained attributes / simple values.
            m = _re.search(rf'{tag}[^>]*>([^<]+)<', xmp, _re.S | _re.I)
        if m:
            inner = m.group(1)
            li = _re.search(r"<rdf:li[^>]*>(.*?)</rdf:li>", inner, _re.S | _re.I)
            value = (li.group(1) if li else inner).strip()
            value = _re.sub(r"<[^>]+>", "", value).strip()
            if value:
                return value
    return None


def _year_from(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    # Handles "D:20200115...", "2020-01-15", "2020", etc.
    m = _re.search(r"(\d{4})", value)
    return m.group(1) if m else None


def collect_book_metadata(doc, source_name: str, overrides: dict) -> dict:
    """Best-effort title / author / publisher / year, with CLI overrides winning."""
    md = doc.metadata or {}
    try:
        xmp = doc.get_xml_metadata() or ""
    except Exception:
        xmp = ""

    title = (overrides.get("title")
             or (md.get("title") or "").strip()
             or _xmp_field(xmp, "dc:title")
             or os.path.splitext(os.path.basename(source_name))[0])

    author = (overrides.get("author")
              or (md.get("author") or "").strip()
              or _xmp_field(xmp, "dc:creator")
              or "Unknown")

    publisher = (overrides.get("publisher")
                 or _xmp_field(xmp, "dc:publisher")
                 or "Unknown")

    year = (overrides.get("year")
            or _year_from(_xmp_field(xmp, "dc:date"))
            or _year_from(_xmp_field(xmp, "xmp:CreateDate"))
            or _year_from(md.get("creationDate"))
            or "Unknown")

    return {"title": title, "author": author, "publisher": publisher, "year": year}


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #
_KIND_TAG = {
    "underline": " _(underlined)_",
    "strikeout": " _(struck through)_",
    "squiggly": " _(squiggly)_",
}

# All text written below — book metadata AND the recovered highlight/note text —
# originates from an untrusted PDF. Before writing it into the .md we neutralize the
# characters that let a crafted PDF inject *active* Markdown/HTML: links and images
# ([]()  !), raw HTML (< > &), emphasis/code (* _ ` ~), tables (|), and heading /
# brace constructs (# { }). We deliberately do NOT escape ordinary prose punctuation
# like . - + so normal highlights stay readable — those are only structural at the
# start of a line, and every line we emit is prefixed by us, not by the PDF.
_MD_ACTIVE = set("`*_~[]()<>&|#{}!")


def _escape_md(value: str) -> str:
    """Escape Markdown/HTML-active characters in untrusted PDF-derived text."""
    if not value:
        return ""
    value = value.replace("\\", "\\\\")  # backslash first, so we don't double-escape
    out = []
    for ch in value:
        if ch == "&":
            out.append("&amp;")
        elif ch in _MD_ACTIVE:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def render_markdown(doc, sections: list[Section], source_name: str,
                    include_empty: bool, book: dict, notes: str = "inline") -> str:
    """Render the requested format:

        # {Book Title}
        **Author:** {Author}
        **Publisher:** {Publisher}
        **Published:** {Year}
        ---
        ## {Chapter / Section Heading}
        - {highlighted text}
        - {highlighted text}
    """
    lines: list[str] = []
    lines.append(f"# {_escape_md(book['title'])}")
    lines.append(f"**Author:** {_escape_md(book['author'])}")
    lines.append(f"**Publisher:** {_escape_md(book['publisher'])}")
    lines.append(f"**Published:** {_escape_md(book['year'])}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for sec in sections:
        if not sec.highlights and not include_empty:
            continue
        lines.append(f"## {_escape_md(sec.title)}")
        if not sec.highlights:
            lines.append("")
            lines.append("_(no highlights)_")
            lines.append("")
            continue
        for h in sec.highlights:
            text = h.text.strip() if h.text else ""
            if not text and h.kind == "note":
                text = h.note.strip()
                note = ""
            else:
                note = h.note.strip()
            # Collapse any newlines inside a single highlight into one line, then
            # escape — the text came straight out of an untrusted PDF.
            text = _escape_md(" ".join(text.split()))
            note = _escape_md(" ".join(note.split()))
            bullet = f"- {text}" if text else "- _(sticky note)_"
            if note and notes == "inline":
                bullet += f" — _Note: {note}_"
            tag = _KIND_TAG.get(h.kind, "")
            bullet += tag
            lines.append(bullet)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Extract Acrobat highlights + comments into a chapter-organized "
                    "Markdown file.")
    ap.add_argument("pdf", help="Path to the highlighted PDF")
    ap.add_argument("-o", "--output", help="Output .md path "
                    "(default: <pdf name>_highlights.md next to the PDF)")
    ap.add_argument("--types", nargs="+",
                    default=["highlight", "underline", "strikeout", "squiggly", "note"],
                    choices=["highlight", "underline", "strikeout", "squiggly", "note"],
                    help="Which annotation kinds to include (default: all).")
    ap.add_argument("--include-empty", action="store_true",
                    help="Also list chapters that contain no highlights.")
    ap.add_argument("--notes", choices=["inline", "skip"], default="inline",
                    help="How to handle a highlight's sticky-note comment: append "
                         "it to the bullet ('inline', default) or drop it ('skip').")
    # Header overrides — handy because PDF metadata is often missing/wrong.
    ap.add_argument("--title", help="Override the book title in the header.")
    ap.add_argument("--author", help="Override the author in the header.")
    ap.add_argument("--publisher", help="Override the publisher in the header.")
    ap.add_argument("--year", help="Override the published year in the header.")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.pdf):
        ap.error(f"File not found: {args.pdf}")

    try:
        doc = pymupdf.open(args.pdf)
    except Exception as e:
        ap.error(f"Could not open PDF: {e}")

    if doc.needs_pass:
        ap.error("This PDF is password-protected. Decrypt it first.")

    highlights = extract_highlights(doc, set(args.types))
    if not highlights:
        print("No matching highlights or comments were found in this PDF.")
        # Still write an (almost) empty file so the run is reproducible.
    sections = build_sections(doc)
    grouped = assign_to_sections(highlights, sections)
    overrides = {k: v for k, v in (
        ("title", args.title), ("author", args.author),
        ("publisher", args.publisher), ("year", args.year)) if v}
    book = collect_book_metadata(doc, args.pdf, overrides)
    md = render_markdown(doc, grouped, args.pdf, args.include_empty,
                         book, notes=args.notes)

    out_path = args.output or (
        os.path.splitext(args.pdf)[0] + "_highlights.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Extracted {len(highlights)} highlight(s) → {out_path}")
    return out_path


if __name__ == "__main__":
    main()
