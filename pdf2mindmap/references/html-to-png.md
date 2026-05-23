# HTML to PNG Conversion — Troubleshooting Guide

## Core Problem
markmap renders SVG dynamically with D3.js at runtime. The HTML contains an empty `<svg id="mindmap">` tag — static SVG extraction (cairosvg, lxml, etc.) does NOT work. A real browser (pyppeteer) is REQUIRED.

## Common Issues and Fixes

### 1. Chinese Text Shows as Garbled (乱码)
**Cause:** Linux headless Chrome/Chromium has no CJK fonts. markmap uses `ui-sans-serif, system-ui, sans-serif` which falls back to DejaVu Sans (no CJK support).

**Fix:** Inject Google Noto Sans SC font via JavaScript before screenshotting.

```python
# Font injection sequence (MUST follow this order)
await page.evaluate("""() => {
    const link = document.createElement('link');
    link.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
    return document.fonts.ready;
}""")
await asyncio.sleep(5)  # Wait for font download

# Force apply font to all elements
await page.evaluate("""() => {
    const style = document.createElement('style');
    style.textContent = `
        * { font-family: 'Noto Sans SC', ui-sans-serif, system-ui, sans-serif !important; }
    `;
    document.head.appendChild(style);
}""")
await asyncio.sleep(3)  # Wait for font application
```

### 2. Content Truncated at Edges
**Cause:** markmap fills the entire viewport. If the viewport is too small, the mindmap content gets clipped.

**WRONG approach:**
```python
# This causes truncation!
await page.setViewport({
    'width': 2560,
    'height': 1440,
    'deviceScaleFactor': 3  # Scales up AFTER layout, causing clipping
})
```

**CORRECT approach:**
```python
# This works — markmap layouts at 8K resolution
await page.setViewport({
    'width': 7680,
    'height': 4320,
    'deviceScaleFactor': 1  # No scaling, full resolution layout
})
```

**Why this matters:** markmap's D3.js layout algorithm calculates positions based on viewport size. If you use a small viewport with high scale factor, the layout is calculated for the small size, then scaled up — causing content to be cut off at the edges.

### 3. D3 Animations Not Complete
**Cause:** D3.js uses CSS transitions and JavaScript animations that need time to complete.

**Fix:** Wait at least 10 seconds after page load and font injection before taking the screenshot.

```python
# Wait for D3 animations to complete
print("Waiting for markmap to render...")
await asyncio.sleep(10)

# Take screenshot
await page.screenshot({
    'path': output_path,
    'type': 'png',
    'fullPage': True,
})
```

### 4. libnspr4.so Error
**Cause:** Playwright's bundled Chromium requires nspr/nss libraries that may not be installed.

**Fix:** Use conda's pre-installed libraries:
```bash
export LD_LIBRARY_PATH=/home/linton/anaconda3/lib:$LD_LIBRARY_PATH
```

The html2png.py script already sets this internally.

### 5. Chromium Not Found
**Cause:** pyppeteer/puppeteer try to download Chromium (~183MB) on first use. If the download fails, the script can't run.

**Fix:** Use Playwright's pre-installed Chromium:
```python
CHROME_PATH = '/home/linton/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome'

browser = await launch(
    executablePath=CHROME_PATH,
    headless=True,
    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
)
```

## Recommended Parameters

| Parameter | Value | Reason |
|-----------|-------|--------|
| Viewport width | 7680 | 8K resolution, prevents truncation |
| Viewport height | 4320 | 16:9 aspect ratio |
| deviceScaleFactor | 1 | No scaling, full resolution layout |
| Font wait | 5s | Font download time |
| Animation wait | 10s | D3.js animation completion |
| Total wait | ~18s | Ensures complete rendering |

## Batch Conversion

```bash
# Convert all HTML files in output/ directory
python3 scripts/html2png.py output/ --batch
```

Each HTML file produces a PNG with the same name. The script handles:
- Font injection
- Viewport setup
- Animation waiting
- Error handling

## Verification

After conversion, verify the PNG:
```python
from PIL import Image
img = Image.open('output.png')
print(f'Dimensions: {img.size[0]} x {img.size[1]}')
print(f'File size: {os.path.getsize("output.png") / (1024*1024):.2f} MB')
```

Expected output for 8K viewport:
- Dimensions: 7680 x 4320
- File size: 1-3 MB (depending on content)
