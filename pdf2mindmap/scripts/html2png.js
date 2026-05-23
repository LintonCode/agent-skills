#!/usr/bin/env node
/**
 * Convert markmap HTML to high-quality PNG using Puppeteer.
 *
 * Usage:
 *   node html2png.js <input.html> [output.png] [--scale 2] [--width 1920]
 *
 * Examples:
 *   node html2png.js mindmap.html output.png
 *   node html2png.js mindmap.html output.png --scale 3 --width 2560
 */

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

// Parse arguments
const args = process.argv.slice(2);
let htmlPath = null;
let outputPath = null;
let scale = 2;
let width = 1920;
let fullPage = true;

for (let i = 0; i < args.length; i++) {
    if (args[i] === '--scale' && args[i + 1]) {
        scale = parseInt(args[i + 1], 10);
        i++;
    } else if (args[i] === '--width' && args[i + 1]) {
        width = parseInt(args[i + 1], 10);
        i++;
    } else if (args[i] === '--full-page') {
        fullPage = true;
    } else if (args[i] === '--no-full-page') {
        fullPage = false;
    } else if (!htmlPath) {
        htmlPath = args[i];
    } else if (!outputPath) {
        outputPath = args[i];
    }
}

if (!htmlPath) {
    console.log('Usage: node html2png.js <input.html> [output.png] [--scale 2] [--width 1920]');
    process.exit(1);
}

if (!outputPath) {
    outputPath = htmlPath.replace(/\.html?$/, '.png');
}

async function screenshot() {
    console.log('[1/3] Loading Puppeteer...');

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: 'new',
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        });
    } catch (err) {
        console.log('[ERROR] Failed to launch Puppeteer.');
        console.log('Try installing Chromium:');
        console.log('  npm install -g puppeteer');
        console.log('Or set PUPPETEER_EXECUTABLE_PATH to a Chromium binary.');
        throw err;
    }

    console.log('[2/3] Rendering HTML...');

    try {
        const page = await browser.newPage();
        await page.setViewport({ width, height: 1080, deviceScaleFactor: scale });

        const absPath = path.resolve(htmlPath);
        const fileUrl = `file://${absPath}`;
        console.log(`  Loading: ${fileUrl}`);

        await page.goto(fileUrl, { waitUntil: 'networkidle0', timeout: 60000 });

        // Wait for markmap to fully render
        // markmap uses D3 with transitions, give it time
        await page.waitForFunction(() => {
            const mindmap = document.querySelector('g.mindmap');
            return mindmap !== null;
        }, { timeout: 30000 }).catch(() => {});

        // Additional wait for smooth rendering
        await new Promise(r => setTimeout(r, 3000));

        // If full page, adjust viewport to content size
        if (fullPage) {
            const dimensions = await page.evaluate(() => {
                const root = document.querySelector('.markmap-root, svg');
                if (!root) return { width: window.innerWidth, height: window.innerHeight };
                return {
                    width: root.getBBox().width + 200,
                    height: root.getBBox().height + 200
                };
            });

            await page.setViewport({
                width: Math.max(width, dimensions.width),
                height: dimensions.height,
                deviceScaleFactor: scale
            });

            // Re-wait for layout
            await new Promise(r => setTimeout(r, 1000));
        }

        console.log('[3/3] Taking screenshot...');
        await page.screenshot({
            path: outputPath,
            type: 'png',
            fullPage: fullPage,
            clip: fullPage ? undefined : undefined
        });

        console.log(`Saved: ${outputPath}`);
        const size = fs.statSync(outputPath).size;
        console.log(`Size: ${(size / 1024 / 1024).toFixed(2)} MB`);

    } finally {
        await browser.close();
    }
}

screenshot().catch(err => {
    console.error(err.message);
    process.exit(1);
});
