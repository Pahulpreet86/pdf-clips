# Clips

Extract highlights and comments from an annotated PDF into a clean Markdown file, grouped under the chapter or section each highlight appears in.

Works with PDFs highlighted in Adobe Acrobat Reader or any viewer that writes standard PDF markup annotations. Ships as a [Claude](https://claude.com) plugin, but underneath it's a single Python script that runs anywhere.

## Features

- Recovers the actual highlighted text by reading the text under each annotation's quad points.
- Captures any sticky-note comment attached to a highlight.
- Groups highlights under the chapter / section heading from the PDF outline (bookmarks). When several headings share a page, it locates each heading by searching the page for its title text. With no outline, it falls back to grouping by page; pre-chapter highlights go under **Front matter**.
- Reads title, author, publisher, and year from the PDF's metadata and XMP.
- Markdown-escapes all PDF-derived text on output, so a crafted PDF can't inject links, images, or raw HTML.

## Output format

```markdown
# Your Book Title
**Author:** Jane Doe
**Publisher:** O'Reilly
**Published:** 2021

---

## Chapter 1: Foundations
- the exact sentence you highlighted — _Note: the comment you attached_
- another highlighted passage

## Section 1.2: A Subsection
- one more highlighted passage
```

Missing metadata fields render as `Unknown` and can be overridden via flags. Comments are appended inline by default; use `--notes skip` for pure highlighted-text bullets.

## Requirements

- Python 3.9+
- [PyMuPDF](https://pymupdf.readthedocs.io/) `1.24.10` (installed on first run if missing)
- Optional: [Claude Code](https://code.claude.com) to use it as a plugin

## Usage

### As a plain Python script

```bash
pip install "pymupdf==1.24.10"

python3 highlight_extractor.py input.pdf
python3 highlight_extractor.py input.pdf -o notes.md
```

The script is at `skills/extract-highlights/scripts/highlight_extractor.py`. Without `-o`, it writes `<pdf name>_highlights.md` next to the source PDF.

### In the Claude app

1. Download **clips-plugin.zip** file.
2. In Claude, open **Settings → Plugins** and upload the ZIP file.
3. Start a chat, **attach the PDF** you want to extract highlights from, and run:

   ```
   /extract-highlights
   ```

   Or just ask in plain language — "extract my highlights from this PDF" — and the `extract-highlights` skill fires automatically.

Claude returns the Markdown file for you to download.

> **Note:** In the Claude app, PDF pages count toward the chat's 100-image limit, so large documents (or several runs in one chat) can hit that wall. Running the script locally avoids the limit entirely.

### As a Claude Code plugin

Copy the plugin folder into your skills directory:

```bash
cp -r clips ~/.claude/skills/
```

Because it contains `.claude-plugin/plugin.json`, Claude Code loads it on the next session (verify with `claude plugin list`). Load it for a single session with `claude --plugin-dir /path/to/clips`, or publish it through a [marketplace](https://code.claude.com/docs/en/plugin-marketplaces). Invoke it with `/clips:extract-highlights` or a plain-language request.

## Options

| Flag | Description |
| --- | --- |
| `-o, --output` | Output `.md` path (defaults to `<pdf>_highlights.md`) |
| `--title` / `--author` / `--publisher` / `--year` | Override header fields when metadata is missing or wrong |
| `--notes inline\|skip` | `inline` (default) appends comments to bullets; `skip` gives pure text |
| `--types highlight underline strikeout squiggly note` | Annotation kinds to include (default: all) |
| `--include-empty` | Also list chapters with no highlights |

Example:

```bash
python3 highlight_extractor.py book.pdf \
    --author "Jane Doe" --publisher "O'Reilly" --year 2021 --notes skip
```

## Limits

- **Chapter grouping needs bookmarks.** Without a PDF outline, highlights are grouped by page.
- **Scanned PDFs need OCR first.** With no text layer under the highlight, there's nothing to read.
- **Password-protected PDFs must be decrypted first.**

## Security

Clips parses untrusted PDFs via PyMuPDF (a binding over native MuPDF), which is the real attack surface for any PDF tool. The dependency is pinned deliberately — keep it updated, and sandbox PDFs from untrusted sources. All extracted text is Markdown-escaped before it's written.

## Project layout

```
clips/
├── .claude-plugin/
│   └── plugin.json                       # plugin manifest
├── skills/
│   └── extract-highlights/
│       ├── SKILL.md                      # tells Claude when + how to run it
│       └── scripts/
│           └── highlight_extractor.py    # the extractor (PyMuPDF)
├── README.md
└── CHANGELOG.md
```

## Contributing

Issues and pull requests welcome. If you hit a PDF that Clips doesn't group cleanly, open an issue with details.
