# Clips — Claude Code plugin

**Clips** pulls the highlights out of your PDFs and turns them into clean notes.

A Claude Code plugin that turns a PDF you highlighted in **Adobe Acrobat Reader**
into a clean Markdown file, with every highlighted passage (and its comment)
grouped under the **chapter / section** it appears in.

Once installed, just ask Claude something like *"extract the highlights from
book.pdf"* and the `extract-highlights` skill fires automatically.

## What's inside

```
clips/
├── .claude-plugin/
│   └── plugin.json                       # plugin manifest
├── skills/
│   └── extract-highlights/
│       ├── SKILL.md                      # tells Claude when + how to run it
│       └── scripts/
│           └── highlight_extractor.py    # the actual extractor (PyMuPDF)
├── README.md
└── CHANGELOG.md
```

## Requirements

- [Claude Code](https://code.claude.com)
- Python 3.9+
- `pymupdf`, pinned (the skill installs it automatically the first time it runs:
  `pip install "pymupdf==1.24.10"`)

> **Security note.** Clips parses whatever PDF you hand it using PyMuPDF, which
> wraps the native MuPDF library. Parsing a maliciously crafted PDF is the real
> attack surface for *any* PDF tool, so keep PyMuPDF updated and, for PDFs from
> untrusted sources, run Clips in a sandbox / container. Text pulled out of the
> PDF (title, author, highlights, notes) is Markdown-escaped before it's written,
> so a crafted PDF can't inject links, images, or raw HTML into your notes.

## Install

### Option A — drop-in (persistent, no marketplace)

Copy the `clips/` folder into your personal skills directory:

```bash
cp -r clips ~/.claude/skills/
```

Because it contains `.claude-plugin/plugin.json`, Claude Code loads it on the next
session as `clips@skills-dir`. Verify with:

```bash
claude plugin list
```

### Option B — load for one session

```bash
claude --plugin-dir /path/to/clips
```

### Option C — publish via a marketplace

Add the folder to a marketplace repo and `claude plugin install clips@your-marketplace`.
See the [plugin marketplaces docs](https://code.claude.com/docs/en/plugin-marketplaces).

## Use

Just talk to Claude:

- "Extract my highlights from `~/Downloads/thesis.pdf`."
- "Turn the Acrobat comments in this PDF into markdown notes."
- "Export the highlights, only the ones with sticky notes."

Or invoke the skill directly:

```
/clips:extract-highlights
```

(The plugin is named `clips`; its one skill is `extract-highlights`, so the fully
qualified command is `clips:extract-highlights`.)

## Output shape

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

The header (title / author / publisher / year) is read from the PDF's metadata and
XMP; missing fields show `Unknown` and can be set with `--title`, `--author`,
`--publisher`, `--year`. Comments are appended to each bullet by default; pass
`--notes skip` for pure highlighted-text bullets.

## Customize

Edit `.claude-plugin/plugin.json` to set your name/email and bump the `version`
when you change things. The extractor's behavior (which annotation types, empty
chapters, etc.) is controlled by flags documented in `SKILL.md`.

## Limits

- Chapter grouping uses the PDF's bookmarks; without them it groups by page.
- Scanned PDFs need OCR first (no text under the highlight otherwise).
- Password-protected PDFs must be decrypted first.
