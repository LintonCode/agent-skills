# PNG Export Troubleshooting

## Common Issues and Fixes

### 1. Chinese Text Shows as Garbled (乱码)

**Root cause:** Linux headless Chrome/Chromium has no CJK fonts. markmap uses `ui-sans-serif, system-ui, sans-serif` which falls back to DejaVu Sans (no CJK support).

**Fix:** Inject Google Noto Sans SC font via JavaScript before screenshot:

```javascript
const link = document.createElement('link');
link.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap';
link.rel = 'stylesheet';
document.head.appendChild(link);
return document.fonts.ready;
```

Then force font application:
```javascript
const style = document.createElement('style');
style.textContent = `* { font-family: 'Noto Sans SC', ui-sans-serif, system-ui, sans-serif !important; }`;
document.head.appendChild(style);
```

**Wait 5 seconds** after font injection before screenshot.

### 2. Content Truncated at Edges

**Root cause:** markmap fills the entire viewport. Small viewport = truncated mindmap.

**Fix:** Use 8K viewport (7680x4320) minimum:

```python
await page.setViewport({
    'width': 7680,
    'height': 4320,
    'deviceScaleFactor': 1  # Don't use scale factor, use full width
})
```

**DO NOT** use `deviceScaleFactor > 1` with small viewport — this causes truncation. The mindmap layout is calculated based on viewport size, so you need the viewport to be the final output size.

### 3. D3.js Animations Not Complete

**Root cause:** markmap uses D3.js for animations. Screenshot too early = incomplete mindmap.

**Fix:** Wait 10+ seconds after page load and font injection:

```python
await page.goto(file_url, waitUntil='networkidle0', timeout=60000)
# ... font injection ...
await asyncio.sleep(10)  # Wait for D3 animations
await page.screenshot({'path': output, 'type': 'png', 'fullPage': True})
```

### 4. Chromium Missing Shared Libraries

**Error:** `libnspr4.so: cannot open shared object file`

**Fix:** Use conda's libraries:
```bash
export LD_LIBRARY_PATH=/home/linton/anaconda3/lib:$LD_LIBRARY_PATH
```

The `html2png.py` script already sets this internally.

### 5. Static SVG Extraction Does NOT Work

**Important:** markmap HTML contains an empty `<svg id="mindmap">` tag. The mindmap is rendered dynamically by D3.js at runtime.

**DO NOT use:**
- cairosvg
- lxml SVG parsing
- Any static SVG converter

**MUST use:** A real browser (pyppeteer, puppeteer, playwright) to render and screenshot.

## Recommended Viewport Sizes

| Quality | Viewport | Output (1x scale) |
|---------|----------|-------------------|
| Standard | 1920x1080 | 1920x1080 |
| HD | 2560x1440 | 2560x1440 |
| 4K | 3840x2160 | 3840x2160 |
| 8K (recommended) | 7680x4320 | 7680x4320 |

## Batch Conversion

```bash
python3 html2png.py output/ --batch --width 7680
```

This converts all `.html` files in the directory to `.png` with 8K resolution.
