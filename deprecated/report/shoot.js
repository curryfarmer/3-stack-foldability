#!/usr/bin/env node
// shoot.js — screenshot fold-pattern solutions from the actual browser tool via Playwright.
//
// Usage:
//   node shoot.js --results ../results/6x5_<hash>.json --ids 1,2,3
//   node shoot.js --results <file> --id 2 --out figures --element .svg-wrap --scale 2
//
// Drives the live app (default http://localhost:8001): loads the results JSON via the
// app's automation hook (App.loadResultsData), steps to each solution by id
// (App.stepToId), and screenshots the rendered SVG element to report/figures/.
//
// Requires the static server running (e.g. python3 -m http.server 8001 from the project
// dir) and Google Chrome installed (used via channel:'chrome', no browser download).

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

function parseArgs(argv) {
  const a = { url: 'http://localhost:8001', out: path.join(__dirname, 'figures'),
              element: '.svg-wrap', scale: 2, ids: [] };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--results') a.results = argv[++i];
    else if (k === '--id') a.ids.push(parseInt(argv[++i], 10));
    else if (k === '--ids') a.ids.push(...argv[++i].split(',').map(s => parseInt(s, 10)));
    else if (k === '--url') a.url = argv[++i];
    else if (k === '--out') a.out = argv[++i];
    else if (k === '--element') a.element = argv[++i];
    else if (k === '--scale') a.scale = parseFloat(argv[++i]);
    else if (k === '--label') a.label = argv[++i];   // optional filename suffix
  }
  return a;
}

(async () => {
  const args = parseArgs(process.argv.slice(2));
  if (!args.results) { console.error('error: --results <file> required'); process.exit(2); }
  const data = JSON.parse(fs.readFileSync(args.results, 'utf8'));
  const tag = data.meta ? `${data.meta.m}x${data.meta.n}` : 'grid';
  const ids = args.ids.length ? args.ids : data.solutions.map(s => s.id);
  fs.mkdirSync(args.out, { recursive: true });

  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ deviceScaleFactor: args.scale });
    await page.goto(args.url, { waitUntil: 'load' });
    await page.waitForFunction(() => window.App && typeof window.App.loadResultsData === 'function');
    const count = await page.evaluate(d => window.App.loadResultsData(d), data);
    console.log(`loaded ${count} solutions from ${path.basename(args.results)}`);

    for (const id of ids) {
      const ok = await page.evaluate(i => window.App.stepToId(i), id);
      if (!ok) { console.warn(`  id ${id}: not found, skipped`); continue; }
      await page.waitForTimeout(150);   // let the SVG re-render settle
      const el = await page.$(args.element);
      if (!el) { console.warn(`  id ${id}: element ${args.element} not found`); continue; }
      const suffix = args.label ? `_${args.label}` : '';
      const out = path.join(args.out, `${tag}_sol${id}${suffix}.png`);
      await el.screenshot({ path: out });
      console.log(`  shot sol ${id} -> ${path.relative(process.cwd(), out)}`);
    }
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
