# Clips

**Pull the highlights out of your PDFs and turn them into clean, chapter-grouped Markdown notes.**

Clips reads a PDF you've highlighted in Adobe Acrobat Reader (or any viewer that writes standard PDF markup annotations) and produces a tidy Markdown file — every highlighted passage, plus any comment attached to it, grouped under the chapter or section it appears in.

It ships as a [Claude](https://claude.com) plugin, but underneath it's just a single Python script, so you can run it anywhere.

---

## Why this exists

I read most of my books digitally, and highlighting key passages to revisit later is the feature I lean on the hardest.

Kindle makes this painless — highlights are stored in a format you can access and export. Adobe PDFs are a different story. You can annotate all you like, but there's no straightforward way for most people to get those highlights back *out*. When I went looking for a solution, nearly everything was a paid product, some charging north of $75 for what is really a pretty simple workflow.

That made it a perfect candidate for a weekend build.

## How it works (the interesting part)

The first question was: how does Acrobat actually store a highlight?

It turns out Acrobat **doesn't store the highlighted words at all**. A highlight is an annotation described by **QuadPoints** — the coordinates of the rectangles covering the marked region, not the text itself. So recovering what you actually highlighted means mapping those coordinates back onto the document's text layer and reading whatever sits underneath them.

Once that clicked, the rest fell into place. Clips:

- Recovers the **real highlighted text** by reading the text under each annotation's quad points.
- Captures any **sticky-note comment** attached to a highlight.
- Groups every highlight under the **chapter / section heading** it falls within, using the PDF's outline (bookmarks). When several headings share a page, it finds each heading's true position by searching the page for its title text rather than trusting unreliable TOC coordinates. No outline? It falls back to grouping by page, and anything before the first chapter lands under **Front matter**.
- Pulls **title, author, publisher, and year** from the PDF's metadata and XMP for the header.

## What you get

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

Missing metadata fields render as `Unknown` and can be set by hand (see options). Comments are appended to each bullet by default; you can drop them for pure highlighted-text bullets.

---

## Requirements

- Python 3.9+
- [PyMuPDF](https://pymupdf.readthedocs.io/), pinned to `1.24.10` (the script installs it on first run if it's missing)
- Optional: [Claude Code](https://code.claude.com) if you want to use it as a plugin

## Two ways to run it

### 1. As a Claude plugin

Install the plugin, then just ask in plain language:

> "Extract my highlights from `~/Downloads/thesis.pdf`."

The `extract-highlights` skill fires automatically. You can also invoke it directly:

```
/clips:extract-highlights
```

To install as a drop-in skill, copy the plugin folder into your personal skills directory:

```bash
cp -r clips ~/.claude/skills/
```

Because it contains `.claude-plugin/plugin.json`, Claude Code loads it on the next session. Verify with `claude plugin list`. You can also load it for a single session with `claude --plugin-dir /path/to/clips`, or publish it through a [marketplace](https://code.claude.com/docs/en/plugin-marketplaces).

> **Heads-up on the Claude app's image limit.** If you run this inside the Claude app, PDF pages count toward the chat's 100-image limit, so large documents — or several runs in one chat — can hit that wall. The fix is the next option.

### 2. As a plain Python script (no page limit)

Under the hood it's just a script, so you can run it locally against any PDF and skip the image limit entirely — no page ceiling, no re-uploading:

```bash
pip install "pymupdf==1.24.10"

python3 highlight_extractor.py input.pdf
python3 highlight_extractor.py input.pdf -o notes.md
```

The script lives at `skills/extract-highlights/scripts/highlight_extractor.py`. Without `-o`, it writes `<pdf name>_highlights.md` next to the source PDF.

## Options

| Flag | What it does |
| --- | --- |
| `-o, --output` | Output `.md` path (defaults to `<pdf>_highlights.md`) |
| `--title` / `--author` / `--publisher` / `--year` | Override header fields when the PDF's metadata is missing or wrong |
| `--notes inline\|skip` | `inline` (default) appends each comment to its bullet; `skip` gives pure text |
| `--types highlight underline strikeout squiggly note` | Choose which annotation kinds to include (default: all) |
| `--include-empty` | Also list chapters that contain no highlights |

Example — fill in the header yourself, text-only bullets:

```bash
python3 highlight_extractor.py book.pdf \
    --author "Jane Doe" --publisher "O'Reilly" --year 2021 --notes skip
```

## Limits

- **Chapter grouping needs bookmarks.** Without a PDF outline, highlights are grouped by page instead.
- **Scanned PDFs need OCR first.** If there's no text layer under the highlight, there's nothing to read — run OCR before extracting.
- **Password-protected PDFs must be decrypted first.**

## Security note

Clips parses whatever PDF you hand it via PyMuPDF, which wraps the native MuPDF library. Parsing a maliciously crafted PDF is the real attack surface for *any* PDF tool, so the dependency is pinned deliberately — keep it updated, and for files from untrusted sources, run Clips in a sandbox or container. All text pulled out of the PDF (title, author, highlights, notes) is Markdown-escaped before it's written, so a crafted PDF can't inject links, images, or raw HTML into your notes.

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