# PDF to Mindmap

Convert PDF documents into beautiful, interactive mind maps with LLM-powered summarization.

## Features

- **Automatic chapter detection** — Uses PDF bookmarks (TOC) or font-size heuristics
- **LLM summarization** — Generates structured markdown with priority markers (★) and memory indicators (◯)
- **Interactive mind maps** — Powered by markmap-cli, viewable in any browser
- **High-quality PNG export** — 8K resolution with Chinese font support
- **Batch processing** — Handle large PDFs with 100+ chapters

## Installation

```bash
# Python dependencies
pip install pymupdf pyppeteer

# Node.js dependencies
npm install -g markmap-cli
```

## Quick Start

```bash
# Convert PDF to mindmap
python3 scripts/pdf2mindmap.py your_document.pdf

# Output structure:
# mindmap_your_document/
# ├── markdown/          # LLM-generated markdown files
# ├── output/            # HTML and PNG mind maps
# └── text/              # Raw extracted text
```

## Workflow

1. **Parse PDF** — Extract text and chapter structure using PyMuPDF
2. **LLM Summarization** — Agent reads each chapter and creates structured markdown
3. **Generate HTML** — Convert markdown to interactive mind maps with markmap
4. **Export PNG** — Convert HTML to high-quality PNG images (8K resolution)

## Output Structure

```
mindmap_<pdf_name>/
├── markdown/          # LLM-generated Markdown files
│   ├── chapter_1_Introduction.md
│   ├── chapter_2_Methodology.md
│   └── document_overall.md
├── output/            # Generated HTML and PNG files
│   ├── chapter_1_Introduction.html
│   ├── chapter_1_Introduction.png
│   └── document_overall.html
└── text/              # Raw extracted text (for reference)
```

## HTML to PNG Export

The included `html2png.py` script handles:
- Chinese font rendering (injects Google Noto Sans SC)
- 8K viewport (7680x4320) to avoid truncation
- D3.js animation completion (10s wait)
- Batch conversion of all HTML files

```bash
# Batch convert all HTML to PNG
python3 scripts/html2png.py output/ --batch
```

## Requirements

- Python 3.8+
- Node.js 16+
- PyMuPDF (pymupdf)
- pyppeteer
- markmap-cli

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
