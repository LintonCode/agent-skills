#!/usr/bin/env python3
"""
Convert markmap HTML to high-quality PNG using pyppeteer (headless Chrome).

CRITICAL: markmap renders SVG dynamically with D3.js. Static SVG extraction (cairosvg, etc.) does NOT work.
CRITICAL: Chinese text requires font injection — the script injects Google Noto Sans SC automatically.
CRITICAL: Viewport must be 8K (7680x4320) to avoid truncation.

Usage:
  python3 html2png.py <input.html> [output.png] [--scale 2] [--width 7680]
  
Examples:
  python3 html2png.py mindmap.html output.png
  python3 html2png.py mindmap.html output.png --scale 2 --width 7680
  python3 html2png.py ./output/ --batch   # batch convert all HTML in directory
"""

import sys
import os
import asyncio
from pathlib import Path

# Set library path for Playwright Chromium (conda environment)
os.environ['LD_LIBRARY_PATH'] = '/home/linton/anaconda3/lib:' + os.environ.get('LD_LIBRARY_PATH', '')


async def screenshot_html(html_path: str, output_path: str, scale: int, width: int):
    """Use pyppeteer to render the HTML and take a high-quality screenshot."""
    from pyppeteer import launch

    # Use Playwright's pre-installed Chromium if available
    CHROME_PATH = '/home/linton/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome'
    if not os.path.exists(CHROME_PATH):
        print(f"[ERROR] Chromium not found at {CHROME_PATH}")
        print("Install pyppeteer: pip install pyppeteer")
        sys.exit(1)

    print(f"  Loading: {html_path}")
    browser = await launch(
        executablePath=CHROME_PATH,
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
    )
    try:
        page = await browser.newPage()
        # Set 8K viewport to avoid truncation
        await page.setViewport({
            'width': width,
            'height': int(width * 0.6),  # reasonable height
            'deviceScaleFactor': 1  # Don't use scale factor, use full width
        })

        abs_path = os.path.abspath(html_path)
        file_url = f"file://{abs_path}"
        await page.goto(file_url, waitUntil='networkidle0', timeout=60000)

        # CRITICAL: Inject Google Noto Sans SC font for Chinese text
        print("  Injecting Noto Sans SC font...")
        await page.evaluate("""() => {
            const link = document.createElement('link');
            link.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap';
            link.rel = 'stylesheet';
            document.head.appendChild(link);
            return document.fonts.ready;
        }""")
        await asyncio.sleep(5)

        # Force font application to all elements
        await page.evaluate("""() => {
            const style = document.createElement('style');
            style.textContent = `
                * { font-family: 'Noto Sans SC', ui-sans-serif, system-ui, sans-serif !important; }
            `;
            document.head.appendChild(style);
        }""")
        await asyncio.sleep(3)

        # Wait for D3 animations to complete
        print("  Waiting for markmap to render...")
        await asyncio.sleep(10)

        # Take screenshot
        print("  Taking screenshot...")
        await page.screenshot({
            'path': output_path,
            'type': 'png',
            'fullPage': True,
        })

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Saved: {output_path} ({size_mb:.2f} MB)")

    finally:
        await browser.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convert markmap HTML to high-quality PNG")
    parser.add_argument("input", help="HTML file or directory path")
    parser.add_argument("output", nargs="?", help="Output PNG path (ignored if --batch)")
    parser.add_argument("--scale", type=int, default=1, help="Device scale factor. Default: 1")
    parser.add_argument("--width", type=int, default=7680, help="Viewport width in pixels. Default: 7680 (8K)")
    parser.add_argument("--batch", action="store_true", help="Convert all HTML files in input directory")
    parser.add_argument("--output-dir", default=None, help="Output directory for batch mode")

    args = parser.parse_args()

    input_path = Path(args.input)

    if args.batch or input_path.is_dir():
        # Batch mode: convert all HTML files in directory
        html_files = list(input_path.glob("*.html"))
        if not html_files:
            print(f"[ERROR] No HTML files found in {input_path}")
            sys.exit(1)

        out_dir = Path(args.output_dir) if args.output_dir else input_path
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"Batch mode: found {len(html_files)} HTML files")
        for html_file in sorted(html_files):
            png_path = out_dir / (html_file.stem + ".png")
            asyncio.run(screenshot_html(str(html_file), str(png_path), args.scale, args.width))

        print(f"\nDone! All PNGs saved to: {out_dir}")

    else:
        # Single file mode
        if not args.output:
            args.output = str(input_path.with_suffix('.png'))
        asyncio.run(screenshot_html(str(input_path), args.output, args.scale, args.width))


if __name__ == "__main__":
    main()
