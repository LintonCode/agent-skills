---
name: pdf2mindmap
version: 1.0.0
author: linton
description: Convert PDF documents into interactive mind maps using PyMuPDF for parsing and markmap-cli for visualization. Always uses LLM to read and summarize chapter content.
---

# PDF to Mindmap

## Overview

Convert PDF documents into interactive mind maps using:
- **PyMuPDF** (pymupdf) — high-performance PDF text extraction with font-size-aware heading detection
- **RapidOCR** (rapidocr-onnxruntime) — OCR for scanned PDFs (automatic detection)
- **markmap-cli** — convert Markdown to interactive mind map HTML
- **LLM summarization** — always used to read and summarize chapter content for rich mind maps
- **pyppeteer** — render markmap HTML to high-quality PNG with Chinese font support

The pipeline handles large PDFs with multiple chapters by generating:
1. Individual chapter mind maps (with LLM-enhanced content)
2. An overall document mind map showing all chapter relationships

## Installation

### From GitHub (recommended)
```bash
# Clone the agent-skills repository
git clone https://github.com/LintonCode/agent-skills.git

# Copy the skill to your agent's skills directory
cp -r agent-skills/pdf2mindmap ~/.hermes/skills/pdf2mindmap

# Install dependencies
pip install pymupdf pyppeteer
npm install -g markmap-cli
```

### Dependencies
- **Python:** `pymupdf`, `pyppeteer`
- **Node.js:** `markmap-cli`
- **OCR (for scanned PDFs):** `rapidocr-onnxruntime`

### OCR Support (Scanned PDFs)

If the PDF is scanned (image-based), the pipeline automatically detects it and uses RapidOCR to extract text:

```bash
# Install OCR dependency
pip install rapidocr-onnxruntime

# Run the pipeline (OCR is automatic)
python3 pdf2mindmap.py scanned_document.pdf
```

The script will:
1. Detect if the PDF is scanned by sampling pages
2. Convert pages to images (300 DPI)
3. Use RapidOCR to extract text from each page
4. Save OCR text to `text/` directory
5. Continue with chapter detection and LLM summarization

**Note:** OCR is slower than text extraction but works for scanned documents.

### Verify Installation
```bash
python3 -c "import fitz; print(fitz.__version__)"
node /usr/local/lib/node_modules/markmap-cli/bin/cli.js --version 2>/dev/null || markmap --version
```

### Chromium Library Fix (if needed)
If you get `libnspr4.so: cannot open shared object file` error, set:
```bash
export LD_LIBRARY_PATH=/home/linton/anaconda3/lib:$LD_LIBRARY_PATH
```

The html2png.py script already sets this internally.

## Usage

### Command Line
```bash
python3 pdf2mindmap.py <input.pdf> [output_dir]
```

Examples:
```bash
# Default output: ./mindmap_<pdf_name>/
python3 pdf2mindmap.py document.pdf

# Custom output directory
python3 pdf2mindmap.py report.pdf ./mindmaps/report
```

### As a Library (Python)
```python
from pdf2mindmap import pdf_to_mindmap

result = pdf_to_mindmap("document.pdf", "./output_dir")

# Access results
print(result["output_dir"])           # Output directory path
print(result["chapters"])             # List of chapter dicts
print(result["chapter_text_files"])   # List of .txt paths for summarization
print(result["html_paths"])           # Dict: markdown_filename -> html_path
```

## Output Structure

**Standardized output directory structure with separate folders for markdown, output files, and raw text.**

```
{output_dir}/
├── markdown/                          # LLM-generated Markdown files
│   ├── chapter_1_Introduction.md
│   ├── chapter_2_Methodology.md
│   ├── ...
│   └── document_overall.md
├── output/                            # Generated HTML and PNG files
│   ├── chapter_1_Introduction.html
│   ├── chapter_1_Introduction.png
│   ├── chapter_2_Methodology.html
│   ├── chapter_2_Methodology.png
│   ├── ...
│   ├── document_overall.html
│   └── document_overall.png
└── text/                              # Raw extracted text (for reference)
    ├── _text_Introduction.txt
    ├── _text_Methodology.txt
    └── ...
```

## Workflow

### Step 1: Parse PDF with PyMuPDF
```python
import fitz

doc = fitz.open(pdf_path)

# Extract table of contents (bookmarks)
toc = doc.get_toc()  # [(level, title, page_num), ...]

# Extract text blocks with font-size info
for page_num in range(doc.page_count):
    page = doc[page_num]
    text_dict = page.get_text("dict", sort=True)
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:  # skip images
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                font_size = span.get("size", 12)
```

Key PyMuPDF APIs:
- `doc.get_toc()` — PDF bookmarks/TOC (if embedded)
- `page.get_text("dict")` — structured text with font sizes (best for heading detection)
- `page.get_text("blocks")` — simpler block extraction
- `page.get_text("text")` — plain text only
- `page.get_text("words")` — word-level extraction with positions

### Step 2: Detect if PDF is Scanned (OCR Check)

The script automatically checks if the PDF is scanned by sampling pages:

```python
def is_scanned_pdf(pdf_path: str, sample_pages: int = 5) -> bool:
    """Check if PDF is scanned (image-based) by sampling pages."""
    doc = fitz.open(pdf_path)
    pages_to_check = min(sample_pages, doc.page_count)
    
    textless_pages = 0
    for i in range(pages_to_check):
        page = doc[i]
        text = page.get_text("text").strip()
        if len(text) < 50:  # Very little text = likely scanned
            textless_pages += 1
    
    doc.close()
    return textless_pages >= pages_to_check * 0.8
```

If the PDF is scanned:
1. Convert pages to images (300 DPI)
2. Use RapidOCR to extract text from each page
3. Save OCR text to `text/` directory
4. Continue with chapter detection using OCR text

### Step 3: Detect Chapter Structure

Two strategies, used in order of priority:

**Strategy A: PDF Bookmarks (TOC)**
If the PDF has embedded bookmarks (`doc.get_toc()` returns non-empty), use them directly:
- Level 1 = top-level chapters
- Level 2 = subsections
- Level 3 = sub-subsections

**Strategy B: Font-Size Heuristics**
If no bookmarks exist, detect headings from font sizes:
1. Collect all font sizes from text blocks
2. Sort descending (largest font = highest level)
3. Assign levels: largest font = `#`, next = `##`, etc.
4. Group content between headings into chapters

Font-size threshold for heading detection:
```python
median_size = sorted(font_sizes)[len(font_sizes) // 2]
heading_threshold = median_size * 1.5  # 50% larger than median
```

### Step 4: Extract Chapter Text

The script extracts raw text for each chapter and saves it to `text/` directory. These files are the input for LLM summarization.

For scanned PDFs, the text is extracted using RapidOCR. For text-based PDFs, the text is extracted directly using PyMuPDF.

### Step 5: LLM Summarization (AGENT TASK)

**This is where you (the agent) come in.** For each chapter's `.txt` file, read the full text and generate a structured Markdown summary using the LLM.

**Prompt template for summarization:**
```
你是一位专业的读书笔记助手。请阅读以下章节内容，生成结构化的思维导图素材。

要求：
1. 用 Markdown 层级格式输出，# 表示一级标题（章节名），## 表示二级标题（小节名），### 表示三级标题（子小节名）
2. 每个要点前用 ★ 标注重要性：★★★ = 核心概念，★★ = 重要，★ = 补充
3. 用 ◯ 标注需要记忆的关键点
4. 提取核心定义、分类、特征、关系、对比、案例
5. 保持原文的逻辑结构，不要遗漏重要内容
6. 用简洁的语言，适合做成思维导图
7. 只输出 Markdown 内容，不要输出其他说明文字

章节标题：{chapter_title}
章节内容：
{chapter_text}
```

**Example output (what you should produce):**
```markdown
# 第四章 知识产权的主体

## 一、 主体概述 ★◯
### 主体范围 ◯
- 权利角度：权利所有人（著作权人、专利权人、商标权人）
- 法律关系角度：权利人 + 义务人
- 主体类型：自然人、法人、非法人组织、国家

## 二、 原始主体 ★★★◯
- **原始取得含义**：第一次产生权利、不依赖他人既有权利
- **两大取得方式 ◯**
  - ① 创作者的创造性行为（事实行为，权利源泉）
  - ② 国家机关的授权行为（行政行为，权利根据）
```

**Workflow for summarization:**
1. Read each `.txt` file in `text/` directory (named `_text_<safe_title>.txt`)
2. For each file, use `delegate_task` or direct LLM call to summarize the content
3. Save each summary as `chapter_<safe_title>.md` in `markdown/` directory
4. Generate `document_overall.md` by combining all chapter summaries
5. Run markmap to generate HTML in `output/` directory
6. Run `html2png.py --batch` to convert all HTML to PNG

### Step 6: Generate Mind Maps with markmap

```bash
# Generate mind map from Markdown
markmap markdown/chapter_1.md -o output/chapter_1.html --offline --no-open
```

Options:
- `--offline` — inline all assets for standalone HTML
- `--no-open` — don't open in browser after generation
- `-o <file>` — specify output filename

### Step 7: Convert HTML to PNG

```bash
# Batch convert all HTML files
python3 html2png.py output/ --batch
```

## HTML to PNG Export — Critical Notes

### 1. markmap SVG is dynamic (CRITICAL)
markmap renders SVG dynamically with D3.js at runtime. The HTML contains an empty `<svg id="mindmap">` tag — **static SVG extraction (cairosvg, lxml, etc.) does NOT work**. A real browser (pyppeteer) is REQUIRED.

### 2. Chinese Font Rendering (CJK text shows as garbled)
Linux headless Chrome/Chromium does NOT have CJK fonts by default. The html2png.py script automatically injects Google Noto Sans SC font before taking the screenshot.

**Font injection sequence (must follow this order):**
1. Inject Google Fonts link: `https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap`
2. Wait for `document.fonts.ready` to resolve
3. Sleep 5 seconds for font download
4. Force apply font to all elements via CSS: `* { font-family: 'Noto Sans SC', ... !important; }`
5. Sleep 3 seconds for font application
6. Sleep 10 seconds for D3 animations to complete

### 3. Viewport Size — MUST be 8K (7680x4320) with deviceScaleFactor=1
**CRITICAL:** markmap fills the entire viewport. A small viewport = truncated mindmap.

- **WRONG:** `viewport: {width: 2560, height: 1440, deviceScaleFactor: 3}` — This causes truncation because markmap layouts at 2560x1440 then scales up, cutting off content at edges.
- **CORRECT:** `viewport: {width: 7680, height: 4320, deviceScaleFactor: 1}` — markmap layouts at 8K resolution, no scaling needed, content is complete.

The script uses 7680x4320 (8K) with deviceScaleFactor=1 by default.

### 4. Wait Time
D3.js animations need time to complete. The script waits 10 seconds after font injection before taking the screenshot.

### 5. Chromium Setup
- pyppeteer uses Playwright's pre-installed Chromium
- If `libnspr4.so` error occurs, set: `export LD_LIBRARY_PATH=/home/linton/anaconda3/lib:$LD_LIBRARY_PATH`
- The html2png.py script already sets this internally
- Chromium binary location: `/home/linton/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome`

### 6. Batch Conversion
```bash
# Convert all HTML files in output/ directory
python3 scripts/html2png.py output/ --batch
```
Each HTML file produces a PNG with the same name.

## Handling Large PDFs

### Chapter-Based Generation
For large PDFs (100+ pages), the pipeline:
1. Detects chapter boundaries from TOC or font sizes
2. Generates individual mind maps per chapter
3. Generates an overall mind map showing chapter relationships

### Memory Considerations
- PyMuPDF processes pages one at a time — low memory usage
- markmap inlines assets in HTML (~300-500KB per mind map)
- For very large documents, consider generating only chapter-level maps

## Limitations & Tips

### TOC Detection
- PDFs without embedded bookmarks fall back to font-size detection
- Font-size detection works best when headings use distinctly larger fonts
- For uniform-font PDFs, consider using an LLM to identify structure

### Content Quality
- The LLM summarization produces rich, structured mind maps with priority markers (★) and memory indicators (◯)
- Chinese PDFs: PyMuPDF handles CJK text natively; markmap supports CJK in headings and content
- For best results, ensure the PDF has embedded bookmarks (TOC) for accurate chapter detection

### Chinese PDFs
- PyMuPDF handles CJK text natively
- markmap supports CJK in headings and content
- Ensure font embedding in PDFs for accurate text extraction

### Customization
- Adjust `threshold_ratio` in `detect_headings_from_fontsize()` for different PDF styles
- Modify `heading_threshold = median_size * 1.3` in `_extract_formatted_content()` for finer control
- Edit the LLM summarization prompt template for different document types (academic, legal, technical)

## Pitfalls

### Large PDFs (100+ chapters) — timeout & incomplete output
- The script's `subprocess.run` for markmap uses a **60-second timeout per chapter**.
- The main pipeline prints a summary but does **not** verify which HTML files were actually created.
- For PDFs with 100+ chapters, the total run time can exceed 120s (the terminal timeout), causing the process to be killed mid-run.
- **Workaround**: After a timeout, check for missing HTML files:
  ```bash
  cd /path/to/output_dir/output
  ls *.md | while read md; do
    html="${md%.md}.html"
    if [ ! -f "$html" ]; then
      echo "Missing: $html — regenerating..."
      markmap "$md" -o "$html" --no-open --offline
    fi
  done
  ```
- The **overall document mindmap** (`document_overall.md` → `document_overall.html`) is generated last and is the largest (often 300-500KB+). It needs the most time. If the run is cut short, regenerate it last with a longer timeout (300s).

### Filenames with spaces
- If a chapter title contains spaces, the markdown filename will contain spaces. When running markmap manually, always quote the filename: `markmap "chapter_1_ My Title.md" -o "chapter_1_ My Title.html" --offline --no-open`
- The Python script handles this correctly via `subprocess.run` with a list of arguments, so no issue when running the script directly.

### LLM Context Window Limits
- For very long chapters (>10,000 chars), consider splitting the text into sections before summarizing
- The script saves raw text to `.txt` files, so you can read them in chunks if needed

## File Locations

- **Script**: `~/.hermes/skills/pdf2mindmap/scripts/pdf2mindmap.py`
- **HTML to PNG**: `~/.hermes/skills/pdf2mindmap/scripts/html2png.py` (pyppeteer, with font injection)
- **Skill file**: `~/.hermes/skills/pdf2mindmap/SKILL.md`
- **PNG troubleshooting**: `references/html-to-png.md` (detailed HTML→PNG conversion guide)
- **Summarization workflow**: `references/summarization-workflow.md` (LLM summarization prompt and examples)
- **GitHub repository**: https://github.com/LintonCode/agent-skills
