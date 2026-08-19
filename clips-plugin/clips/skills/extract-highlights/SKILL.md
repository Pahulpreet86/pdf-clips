---
name: extract-highlights
description: Use when the user has a PDF highlighted or commented in Adobe Acrobat Reader (or any viewer that writes standard PDF markup annotations) and wants those highlights and their comments pulled into a Markdown file, grouped under the chapter or section each highlight appears in. Triggers on requests like "extract my highlights", "get the highlighted text out of this PDF", "turn my Acrobat annotations into notes", "export PDF highlights to markdown", or when an annotated PDF is provided and the user asks for the highlights. Do NOT use for creating PDFs, merging/splitting, or extracting plain text from a PDF that has no annotations.
---

# Extract PDF Highlights

Extract highlight annotations (and the sticky-note comments attached to them) from
an annotated PDF and write a Markdown file organized by chapter / section.

## What this does

- Recovers the **actual highlighted words**. Acrobat stores only the *coordinates*
  of a highlight, so the script reads the text sitting under those coordinates.
- Captures any **comment / sticky note** attached to a highlight.
- Groups each highlight under the **chapter or section heading** it falls within,
  using the PDF outline (bookmarks).
- Handles multiple headings on one page, highlights before the first chapter
  ("Front matter"), and PDFs with no outline (falls back to grouping by page).

## Output format

The script writes a Markdown file in exactly this shape:

```markdown
# {Book Title}
**Author:** {Author Name}
**Publisher:** {Publishing House}
**Published:** {Year}

---

## {Chapter / Section Heading}
- {highlighted text}
- {highlighted text}

## {Chapter / Section Heading}
- {highlighted text}
```

Title/author/publisher/year come from the PDF's metadata and XMP. When a field is
missing it reads `Unknown` — override any of them with the flags below. Every
heading is rendered at `##`. If a highlight has a sticky-note comment, it is
appended to the bullet as ` — _Note: ..._` (use `--notes skip` for pure text).

## How to run it

1. Ensure the one dependency is present (idempotent — safe to run every time):

   ```bash
   python3 -c "import pymupdf" 2>/dev/null || pip install "pymupdf==1.24.10" --quiet
   ```

   The version is pinned on purpose: this tool feeds an untrusted PDF into
   PyMuPDF (a binding over the native MuPDF parser), so you want a known, vetted
   version rather than silently pulling whatever is newest. Bump it deliberately.

2. Run the bundled extractor. Use `${CLAUDE_PLUGIN_ROOT}` so the path resolves
   wherever the plugin is installed:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/extract-highlights/scripts/highlight_extractor.py" \
       "<path/to/highlighted.pdf>" \
       -o "<path/to/output.md>"
   ```

   If the user did not specify an output path, drop the `-o` flag and the script
   writes `<pdf name>_highlights.md` next to the source PDF.

3. Show the user the resulting Markdown (or open the `.md` file for them).

## Options

- `--title`, `--author`, `--publisher`, `--year` — override the header fields when
  the PDF's metadata is missing or wrong. Supply these whenever the user tells you
  the book's details, or when the auto-detected header shows `Unknown`.
- `--notes inline|skip` — `inline` (default) appends each comment to its bullet;
  `skip` outputs pure highlighted-text bullets.
- `--types highlight underline strikeout squiggly note` — choose which annotation
  kinds to include. Default is all of them.
- `--include-empty` — also list chapters that contain no highlights.

Example — fill in the header the user gave you, text-only bullets:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/extract-highlights/scripts/highlight_extractor.py" \
    book.pdf --author "Jane Doe" --publisher "O'Reilly" --year 2021 --notes skip
```

## Notes & limits

- Works with any viewer that writes standard PDF markup annotations (Acrobat,
  Preview, Foxit, and others), not only Acrobat.
- Chapter detection relies on the PDF's bookmarks/outline; with none, it groups
  highlights by page.
- Scanned PDFs with no text layer have no text under the highlight to read — run
  OCR first.
- Password-protected PDFs must be decrypted first.
