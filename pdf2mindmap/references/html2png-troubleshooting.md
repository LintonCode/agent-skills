# HTML to PNG Export — Troubleshooting & Technical Details

## markmap SVG Rendering Architecture

markmap generates HTML with an empty `<svg id="mindmap">` tag. The actual SVG content is rendered at runtime by D3.js (v6+) using the markmap-view library. This means:

- **Static SVG extraction does NOT work** — cairosvg, lxml, BeautifulSoup will extract an empty or tiny SVG
- **A real browser is REQUIRED** — pyppeteer, puppeteer, playwright, or any headless Chrome/Chromium
- **D3 animations need time** — wait 10+ seconds after page load for all transitions to complete

## Chinese Font Injection (乱码 Fix)

**Problem:** Linux headless Chrome has no CJK fonts. Chinese characters render as garbled boxes (乱码).

**Solution:** Inject Google Noto Sans SC via JavaScript before screenshotting:

```javascript
// Inject font stylesheet
const link = document.createElement('link');
link.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap';
link.rel = 'stylesheet';
document.head.appendChild(link);

// Wait for font to load
await document.fonts.ready;

// Force font application
const style = document.createElement('style');
style.textContent = `
    * { font-family: 'Noto Sans SC', ui-sans-serif, system-ui, sans-serif !important; }
`;
document.head.appendChild(style);
```

**Wait times:**
- 5 seconds after font injection (for download and parsing)
- 3 seconds after style injection (for re-rendering)
- 10 seconds after page load (for D3 animations)

## Viewport Size

markmap fills the entire viewport. A small viewport = truncated mindmap.

| Viewport | Output (2x scale) | Use Case |
|----------|-------------------|----------|
| 1920x1080 | 3840x2160 | Minimum (may truncate large mindmaps) |
| 3840x2160 | 7680x4320 | Recommended (4K input, 8K output) |
| 7680x4320 | 15360x8640 | Maximum quality (8K input, 16K output) |

**Default:** `--width 3840` (4K viewport, 8K output)

## Chromium Setup

### pyppeteer (recommended)
```bash
pip install pyppeteer
# Downloads Chromium on first use (~183MB)
```

### Playwright Chromium (pre-installed in conda)
```bash
export LD_LIBRARY_PATH=/home/linton/anaconda3/lib:$LD_LIBRARY_PATH
CHROME_PATH=/home/linton/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome
```

### node-html-to-image (official recommendation)
```bash
npm install -g node-html-to-image
# Requires Puppeteer + Chromium — npm network is often slow
```

## Common Errors

### "libnspr4.so: cannot open shared object file"
**Fix:** Set `LD_LIBRARY_PATH` to conda's library path:
```bash
export LD_LIBRARY_PATH=/home/linton/anaconda3/lib:$LD_LIBRARY_PATH
```

### "Chromium download failed"
**Fix:** Use Playwright's pre-installed Chromium or set up a mirror:
```bash
export PUPPETEER_DOWNLOAD_HOST=https://npmmirror.com/mirrors/chromium-browser-snapshots
```

### "Image is blank or tiny"
**Cause:** Static SVG extraction (cairosvg) or insufficient wait time.
**Fix:** Use pyppeteer with 10+ second wait after page load.

### "Chinese text is garbled (乱码)"
**Cause:** No CJK fonts in headless Chrome.
**Fix:** Inject Google Noto Sans SC via JavaScript (see above).

### "Content is truncated"
**Cause:** Viewport too small.
**Fix:** Use `--width 3840` (4K) or `--width 7680` (8K).

## Batch Conversion

```bash
# Convert all HTML files in a directory
python3 html2png.py /path/to/mindmaps/ --batch --scale 2 --width 3840

# Output to different directory
python3 html2png.py /path/to/mindmaps/ --batch --output-dir /path/to/pngs/
```

## Performance

- Each HTML file takes ~20-30 seconds to render (including font download and D3 animations)
- For 100+ chapters, expect 30-60 minutes total
- Consider running in background with `--batch` mode
