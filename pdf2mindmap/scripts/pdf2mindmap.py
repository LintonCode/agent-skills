#!/usr/bin/env python3
"""
PDF to Mindmap Pipeline
=======================
Uses PyMuPDF to parse PDFs, then the agent's LLM to summarize chapters,
and markmap-cli to generate interactive mind maps.

Workflow:
  1. Parse PDF with PyMuPDF (extract text blocks + TOC)
  2. Detect chapter structure (from bookmarks/TOC or font-size heuristics)
  3. Extract raw text for each chapter and save to text/ directory
  4. AGENT: Read each chapter's text and summarize with LLM into structured Markdown
  5. Generate markmap HTML for each summarized chapter + overall mind map
  6. Convert HTML to PNG using pyppeteer (with Chinese font support)

Output structure:
  {output_dir}/
  ├── markdown/          # LLM-generated Markdown files
  ├── output/            # Generated HTML and PNG files
  └── text/              # Raw extracted text (for reference)

Usage:
  python3 pdf2mindmap.py <input.pdf> [output_dir]

The script extracts text and structure. The agent (you) summarizes each chapter
using the LLM, then generates the final Markdown and mind maps.

Dependencies:
  pip install pymupdf pyppeteer
  npm install -g markmap-cli
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import fitz  # pymupdf


# ---------------------------------------------------------------------------
# 1. PDF Parsing
# ---------------------------------------------------------------------------

def parse_pdf(pdf_path: str) -> Tuple[List[Dict], Dict[int, List[Dict]], int]:
    """
    Parse a PDF using PyMuPDF.

    Returns:
        toc: Table of contents list of [level, title, page_num]
        page_blocks: Dict mapping page_num -> list of text blocks
        page_count: Total number of pages
    """
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    page_count = doc.page_count
    page_blocks = {}

    for page_num in range(page_count):
        page = doc[page_num]
        text_dict = page.get_text("dict", sort=True)
        blocks = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # skip image blocks
                continue
            block_text = ""
            block_font_sizes = []
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "")
                    block_font_sizes.append(span.get("size", 12))
            block_text = block_text.strip()
            if block_text:
                avg_font_size = sum(block_font_sizes) / len(block_font_sizes) if block_font_sizes else 12
                blocks.append({
                    "text": block_text,
                    "avg_font_size": avg_font_size,
                    "bbox": block.get("bbox", [0, 0, 0, 0]),
                })
        page_blocks[page_num] = blocks

    doc.close()
    return toc, page_blocks, page_count


def detect_headings_from_fontsize(blocks: List[Dict], threshold_ratio: float = 1.5) -> List[Dict]:
    """Detect heading blocks based on font size relative to body text."""
    if not blocks:
        return []

    font_sizes = [b["avg_font_size"] for b in blocks if b["avg_font_size"] > 8]
    if not font_sizes:
        return []

    median_size = sorted(font_sizes)[len(font_sizes) // 2]
    heading_threshold = median_size * threshold_ratio

    headings = []
    for i, block in enumerate(blocks):
        if block["avg_font_size"] >= heading_threshold:
            headings.append({
                "index": i,
                "text": block["text"],
                "font_size": block["avg_font_size"],
                "is_heading": True,
            })
    return headings


# ---------------------------------------------------------------------------
# 2. Chapter / Section Structure Detection
# ---------------------------------------------------------------------------

def build_chapter_structure(
    toc: List[List],
    page_blocks: Dict[int, List[Dict]],
    page_count: int,
) -> List[Dict]:
    """
    Build a hierarchical chapter/section structure from PDF.
    """
    if toc and len(toc) > 0:
        return _build_from_toc(toc, page_count)
    else:
        return _build_from_fontsize(page_blocks, page_count)


def _build_from_toc(toc: List[List], page_count: int) -> List[Dict]:
    """Build chapter structure from the PDF's built-in TOC/bookmarks."""
    chapters = []
    for item in toc:
        level, title, page_num = item[0], item[1], item[2]
        chapters.append({
            "title": title.strip(),
            "level": level,
            "start_page": page_num - 1,  # 0-indexed
            "end_page": page_num,  # will be updated
            "subsections": [],
            "content": "",
        })

    for i in range(len(chapters) - 1):
        chapters[i]["end_page"] = chapters[i + 1]["start_page"]
    if chapters:
        chapters[-1]["end_page"] = page_count

    root = {"title": "Root", "level": 0, "subsections": chapters, "content": ""}
    return _flatten_hierarchy(root)


def _build_from_fontsize(page_blocks: Dict[int, List[Dict]], page_count: int) -> List[Dict]:
    """Build chapter structure by detecting headings from font sizes."""
    all_headings = []
    for page_num in sorted(page_blocks.keys()):
        headings = detect_headings_from_fontsize(page_blocks[page_num])
        for h in headings:
            h["page"] = page_num
            all_headings.append(h)

    if not all_headings:
        return [{
            "title": "Full Document",
            "level": 1,
            "start_page": 0,
            "end_page": page_count,
            "subsections": [],
            "content": "",
        }]

    all_headings.sort(key=lambda x: (x["page"], x["index"]))

    font_sizes = sorted(set(h["font_size"] for h in all_headings), reverse=True)
    size_to_level = {}
    for i, size in enumerate(font_sizes):
        size_to_level[size] = i + 1

    chapters = []
    current_chapter = None
    current_sub = None

    for h in all_headings:
        level = size_to_level.get(h["font_size"], 1)
        if level == 1:
            if current_chapter:
                current_chapter["end_page"] = h["page"]
            current_chapter = {
                "title": h["text"],
                "level": 1,
                "start_page": h["page"],
                "end_page": h["page"],
                "subsections": [],
                "content": "",
            }
            chapters.append(current_chapter)
            current_sub = None
        elif level == 2 and current_chapter:
            current_sub = {
                "title": h["text"],
                "level": 2,
                "start_page": h["page"],
                "end_page": h["page"],
                "subsections": [],
                "content": "",
            }
            current_chapter["subsections"].append(current_sub)
        elif level >= 3 and current_sub:
            current_sub["subsections"].append({
                "title": h["text"],
                "level": level,
                "start_page": h["page"],
                "end_page": h["page"],
                "subsections": [],
                "content": "",
            })

    if current_chapter:
        current_chapter["end_page"] = page_count

    return _flatten_hierarchy({"title": "Root", "level": 0, "subsections": chapters})


def _flatten_hierarchy(node: Dict) -> List[Dict]:
    """Flatten hierarchical structure into a list."""
    result = []
    for child in node.get("subsections", []):
        result.append(child)
        result.extend(_flatten_hierarchy(child))
    return result


# ---------------------------------------------------------------------------
# 3. Text Extraction — saves chapter text for LLM summarization
# ---------------------------------------------------------------------------

def extract_chapter_text(
    chapter: Dict,
    page_blocks: Dict[int, List[Dict]],
    skip_titles: set,
) -> str:
    """
    Extract raw text content for a chapter from page blocks.
    Returns clean text string.
    """
    lines = []
    for page_num in range(chapter["start_page"], min(chapter["end_page"], len(page_blocks))):
        blocks = page_blocks.get(page_num, [])
        for block in blocks:
            text = block.get("text", "").strip()
            if not text:
                continue
            if text in skip_titles:
                continue
            lines.append(text)
    return "\n".join(lines)


def save_chapter_texts(
    chapters: List[Dict],
    page_blocks: Dict[int, List[Dict]],
    text_dir: str,
) -> List[Dict]:
    """
    Extract raw text for each chapter and save to text/ directory.
    Returns list of chapter dicts with 'text_file' path added.
    """
    os.makedirs(text_dir, exist_ok=True)
    text_files = []

    for chapter in chapters:
        # Collect all titles in this chapter subtree (to skip from body text)
        all_titles = set()
        def collect_titles(ch):
            all_titles.add(ch["title"])
            for s in ch.get("subsections", []):
                collect_titles(s)
        collect_titles(chapter)

        text = extract_chapter_text(chapter, page_blocks, all_titles)
        safe_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff\s-]', '', chapter["title"]).strip().replace(' ', '-')[:50]
        text_filename = f"_text_{safe_title}.txt"
        text_path = os.path.join(text_dir, text_filename)

        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)

        chapter["text_file"] = text_path
        chapter["safe_title"] = safe_title
        text_files.append(text_path)

    return text_files


# ---------------------------------------------------------------------------
# 4. Markmap Generation
# ---------------------------------------------------------------------------

def generate_mindmap(markdown_path: str, output_html: str, offline: bool = True) -> str:
    """Generate an interactive mindmap HTML from a Markdown file using markmap-cli."""
    cmd = ["markmap", markdown_path, "-o", output_html, "--no-open"]
    if offline:
        cmd.append("--offline")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"  [WARN] markmap failed for {markdown_path}: {result.stderr}")

    return output_html


def generate_all_mindmaps(
    markdown_dir: str,
    output_dir: str,
) -> Dict[str, str]:
    """Generate mindmap HTML for all markdown files in markdown_dir."""
    html_paths = {}
    os.makedirs(output_dir, exist_ok=True)

    for md_filename in os.listdir(markdown_dir):
        if not md_filename.endswith(".md"):
            continue
        
        md_path = os.path.join(markdown_dir, md_filename)
        html_name = md_filename.replace(".md", ".html")
        html_path = os.path.join(output_dir, html_name)

        print(f"  Generating mindmap: {md_filename} -> {html_name}")
        generate_mindmap(md_path, html_path)
        html_paths[md_filename] = html_path

    return html_paths


# ---------------------------------------------------------------------------
# 5. Main Pipeline
# ---------------------------------------------------------------------------

def pdf_to_mindmap(
    pdf_path: str,
    output_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Full pipeline: PDF -> Parse -> Extract text -> (AGENT summarizes) -> Markdown -> Mindmap

    Returns dict with:
      - output_dir
      - markdown_dir (path to markdown/ directory)
      - text_dir (path to text/ directory)
      - chapters (list with text_file paths for LLM summarization)
      - chapter_text_files (list of .txt paths to summarize)
      - html_paths (filled after agent generates markdowns)
    """
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_name = Path(pdf_path).stem
    if output_dir is None:
        output_dir = f"./mindmap_{pdf_name}"
    output_dir = os.path.abspath(output_dir)

    # Create output directories
    markdown_dir = os.path.join(output_dir, "markdown")
    text_dir = os.path.join(output_dir, "text")
    output_html_dir = os.path.join(output_dir, "output")
    
    os.makedirs(markdown_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)
    os.makedirs(output_html_dir, exist_ok=True)

    print(f"=== PDF to Mindmap Pipeline ===")
    print(f"Input:  {pdf_path}")
    print(f"Output: {output_dir}")
    print(f"  markdown/: {markdown_dir}")
    print(f"  text/:     {text_dir}")
    print(f"  output/:   {output_html_dir}\n")

    # Step 1: Parse PDF
    print("[1/5] Parsing PDF with PyMuPDF...")
    toc, page_blocks, page_count = parse_pdf(pdf_path)
    print(f"  Pages: {page_count}")
    print(f"  TOC entries: {len(toc)}")

    # Step 2: Build chapter structure
    print("[2/5] Detecting chapter structure...")
    chapters = build_chapter_structure(toc, page_blocks, page_count)
    print(f"  Chapters detected: {len(chapters)}")
    for ch in chapters:
        print(f"    - {'#' * ch['level']} {ch['title']} (pages {ch['start_page']}-{ch['end_page']})")

    # Step 3: Extract text and save to files
    print("[3/5] Extracting chapter text...")
    text_files = save_chapter_texts(chapters, page_blocks, text_dir)
    print(f"  Saved {len(text_files)} chapter text files to: {text_dir}")

    # Step 4: AGENT SUMMARIZES (call delegate_task for each chapter)
    print("[4/5] === AGENT TASK: Summarize each chapter using LLM ===")
    print("  Read each .txt file in the text/ directory and generate")
    print("  a structured Markdown summary with ★ priority and ◯ memory markers.")
    print("  Save summaries to chapter_<safe_title>.md in markdown/ directory.")
    print("  Then generate document_overall.md from all summaries.")
    print("  After that, run markmap to generate HTML files in output/ directory.")

    # Step 5: Generate mindmaps (after agent creates markdowns)
    print("[5/5] Generating mindmaps with markmap...")
    # Find all chapter markdowns (agent-created) and overall
    markdown_files = {}
    for f in os.listdir(markdown_dir):
        if f.endswith(".md"):
            md_path = os.path.join(markdown_dir, f)
            with open(md_path, "r", encoding="utf-8") as fh:
                markdown_files[f] = fh.read()

    if markdown_files:
        html_paths = generate_all_mindmaps(markdown_dir, output_html_dir)
    else:
        print("  [SKIP] No chapter markdown files found. Agent should run summarize_chapters() first.")
        html_paths = {}

    print(f"\n=== Done! ===")
    print(f"Output directory: {output_dir}")
    print(f"  markdown/: {markdown_dir}")
    print(f"  text/:     {text_dir}")
    print(f"  output/:   {output_html_dir}")

    return {
        "output_dir": output_dir,
        "markdown_dir": markdown_dir,
        "text_dir": text_dir,
        "output_html_dir": output_html_dir,
        "chapters": chapters,
        "chapter_text_files": text_files,
        "html_paths": html_paths,
    }


def summarize_chapters(text_dir: str, chapters: List[Dict], markdown_dir: str) -> Dict[str, str]:
    """
    Agent function: read each chapter's text file and generate a summarized Markdown.
    This is called by the agent using delegate_task after pdf_to_mindmap() extracts text.

    Returns dict mapping safe_title -> summary markdown content.
    """
    summaries = {}
    for chapter in chapters:
        text_file = chapter.get("text_file", "")
        safe_title = chapter.get("safe_title", "")
        chapter_title = chapter.get("title", "")

        if not os.path.exists(text_file):
            print(f"  [SKIP] Text file not found: {text_file}")
            continue

        with open(text_file, "r", encoding="utf-8") as f:
            raw_text = f.read()

        if not raw_text.strip():
            print(f"  [SKIP] Empty text for: {chapter_title}")
            continue

        # The agent should call LLM here to summarize the raw_text
        # into structured Markdown with ★ priority and ◯ markers
        # This is a placeholder — the agent fills in the actual summary
        print(f"  [SUMMARIZE] {chapter_title} ({len(raw_text)} chars) -> save to markdown/chapter_{safe_title}.md")
        summaries[safe_title] = f"# {chapter_title}\n\n{raw_text}"

    return summaries


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 pdf2mindmap.py <input.pdf> [output_dir]")
        print("")
        print("Workflow:")
        print("  1. Script extracts PDF text and chapter structure")
        print("  2. Agent (you) reads each chapter's .txt and summarizes with LLM")
        print("  3. Agent saves summaries as .md files in markdown/ directory")
        print("  4. Script generates mindmap HTML in output/ directory")
        print("  5. Run html2png.py output/ --batch to convert to PNG")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = pdf_to_mindmap(pdf_path, output_dir)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
