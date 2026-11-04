#!/usr/bin/env node
/**
 * Render every Runbooks wireframe to a PNG, and save its build sheet beside it.
 *
 * WHY THIS EXISTS. The Runbooks specification and Twenty-One Runbooks draw 75
 * frames between them, as HTML inside the documents, each with a build sheet
 * under it listing its regions in order with the copy verbatim. Every other
 * module in 04-docs/05-modules carries its wireframes as IMAGES, because a
 * picture is what a builder compares a screenshot of the built screen against
 * (hard-won law 6 — no gate in this repo reads rendered output, so that
 * comparison is done by a person looking at two things). The picture alone is
 * not checkable: "is the copy right, is the order right, is the size right" is
 * answered by the sheet. So both are saved, paired by name.
 *
 * WHAT IT DOES NOT DO. It does not invent, rename or fix a frame. If a frame is
 * wrong in the document it is wrong here identically — which is the point: the
 * sheet and the frame are derived from one source and cannot disagree.
 *
 *   node 10-scripts/runbooks_wireframes.mjs <source.html> <outdir>
 *
 * ⚠ SCREEN CODES ARE TRANSLATED ON THE WAY OUT, and the map lives HERE rather
 * than in a rename step afterwards. The source documents number these screens
 * S147-S154; the PO ruled on 2026-09-06 that runbook screens carry their own
 * series, RBS-001..RBS-008, and that `S147` stays the next free `S`. A rename
 * done by hand would be undone by the next run of this script, which is law 1's
 * shape — so the translation is part of the derivation, and the documents stay
 * untouched as the source.
 */
import { createRequire } from 'node:module';
import { mkdirSync, existsSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

// `playwright` IS RESOLVED FROM `07-frontend`, EXPLICITLY. Node resolves a bare
// import from the SCRIPT's own directory upward — never from the working
// directory — so a plain `import ... from "playwright"` in a file under
// 10-scripts/ fails with ERR_MODULE_NOT_FOUND however you invoke it, and the
// repo root has no node_modules. This is `cwp_portal_walkthrough.mjs`'s pattern,
// which carries the same comment for the same reason; reused, not re-derived.
const require = createRequire(new URL('../07-frontend/package.json', import.meta.url));
const { chromium } = require('playwright');

const SCREEN_MAP = {
  S147: 'RBS-001', S148: 'RBS-002', S149: 'RBS-003', S150: 'RBS-004',
  S151: 'RBS-005', S152: 'RBS-006', S153: 'RBS-007', S154: 'RBS-008',
};

/** S150-R8 -> RBS-004-R8 · S151.3 -> RBS-005.3 · S154 -> RBS-008 */
function ourCode(docCode) {
  return docCode.replace(/\bS1(4[7-9]|5[0-4])\b/g, (m) => SCREEN_MAP[m] ?? m);
}

const [src, outDir] = process.argv.slice(2);
if (!src || !outDir) { console.error('usage: runbooks_wireframes.mjs <source.html> <outdir>'); process.exit(2); }
if (!existsSync(src)) { console.error(`no such file: ${src}`); process.exit(2); }
mkdirSync(outDir, { recursive: true });

// The pinned Playwright revision is often absent in this environment while a
// working chromium sits at /opt/pw-browsers/chromium. `12-smoke-walkthrough.mjs`
// solved this first and prints the mismatch rather than hiding it; same shape
// here, and the fallback is NAMED in the output so a reader knows which binary
// drew the picture.
function resolveChromium() {
  const pinned = chromium.executablePath();
  if (pinned && existsSync(pinned)) return pinned;
  const fallback = '/opt/pw-browsers/chromium';
  if (existsSync(fallback)) { console.log(`chromium: pinned revision missing; using ${fallback}`); return fallback; }
  throw new Error('no chromium found: neither the pinned revision nor /opt/pw-browsers/chromium');
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
await page.goto('file://' + resolve(src), { waitUntil: 'networkidle' });

// The document's nav bar is `position:sticky`, so it sits ON TOP of whatever
// frame is being shot and clips its title bar — which is where the screen code
// lives, the one thing every frame is named for. Removing it costs nothing: it
// is document chrome, not part of any wireframe.
await page.addStyleTag({ content: '.topbar{display:none!important}' });

// ⚠ TRANSLATE THE CODE ON THE FRAME ITSELF, not only in the filename. A picture
// whose title bar reads `S147.1` while everything around it says `RBS-001.1` is
// two names for one screen, and a reader has to hold the mapping in their head.
// The source documents are untouched — this rewrites the rendered DOM only, in
// the same place and by the same map as the filename, so the two cannot drift.
await page.evaluate((map) => {
  const ours = (t) => t.replace(/\bS1(4[7-9]|5[0-4])\b/g, (m) => map[m] ?? m);
  for (const el of document.querySelectorAll('.wf-code, .bs .bsh')) {
    for (const n of [...el.childNodes].filter((n) => n.nodeType === 3)) {
      const next = ours(n.nodeValue);
      if (next !== n.nodeValue) n.nodeValue = next;
    }
  }
}, SCREEN_MAP);

const safe = (s) => s.replace(/[^A-Za-z0-9.\-]/g, '_');
const seen = new Map();
const uniq = (code) => {
  const n = (seen.get(code) ?? 0) + 1;
  seen.set(code, n);
  return n === 1 ? code : `${code}--${n}`;
};

// ── the pictures ──────────────────────────────────────────────────────────
let shots = 0, unnamed = 0;
for (const [i, frame] of (await page.locator('div.wf').all()).entries()) {
  const el = frame.locator('.wf-bar .wf-code').first();
  let code = (await el.count()) ? (await el.innerText()).trim() : '';
  if (!code) { unnamed += 1; code = `UNNAMED-${String(i + 1).padStart(2, '0')}`; }
  await frame.screenshot({ path: `${outDir}/${safe(uniq(ourCode(code)))}.png` });
  shots += 1;
}

// ── the build sheets, as markdown beside their picture ─────────────────────
const sheets = await page.locator('div.bs').evaluateAll((nodes) => nodes.map((n) => {
  const head = n.querySelector('.bsh')?.innerText.trim() ?? '';
  const rows = [...n.querySelectorAll('tbody tr')].map((tr) =>
    [...tr.querySelectorAll('td')].map((td) => td.innerText.replace(/\s*\n\s*/g, ' · ').trim()));
  const cols = [...n.querySelectorAll('thead th')].map((th) => th.innerText.trim());
  const foot = n.querySelector('.bsf')?.innerText.trim() ?? '';
  return { code: n.dataset.code ?? '', head, cols, rows, foot };
}));

const sheetSeen = new Map();
let written = 0, codeless = 0;
for (const s of sheets) {
  if (!s.code) { codeless += 1; continue; }
  const our = ourCode(s.code);
  const n = (sheetSeen.get(our) ?? 0) + 1; sheetSeen.set(our, n);
  const name = safe(n === 1 ? our : `${our}--${n}`);
  const esc = (c) => c.replace(/\|/g, '\\|');
  const body = [
    `# ${our} — build sheet`,
    '',
    `> Derived from the source document's own markup by \`10-scripts/runbooks_wireframes.mjs\`.`,
    `> The document numbers this screen \`${s.code}\`; this repo numbers it \`${our}\` (PO ruling 2026-09-06).`,
    `> **A sheet and its frame cannot disagree — one is derived from the other. If one is wrong, both are, and the frame is the thing to fix.**`,
    '',
    `**${s.head}**`, '',
    `| ${s.cols.map(esc).join(' | ')} |`,
    `|${s.cols.map(() => '---').join('|')}|`,
    ...s.rows.map((r) => `| ${r.map(esc).join(' | ')} |`),
    '', s.foot ? `_${s.foot}_` : '', '',
    `Picture: \`${name}.png\``, '',
  ].join('\n');
  writeFileSync(`${outDir}/${name}.md`, body);
  written += 1;
}

await browser.close();
// A count that distinguishes pass from fail to a READER, not only to an exit
// code (law 7, habit 3). An unnamed frame or a codeless sheet means the source
// document is missing a code, which is a defect in the document, not here.
console.log(`${shots} pictures · ${written} build sheets → ${outDir}`);
console.log(`${seen.size} distinct screen codes · ${unnamed} frames with no code · ${codeless} sheets with no code`);
if (unnamed || codeless) process.exitCode = 1;
