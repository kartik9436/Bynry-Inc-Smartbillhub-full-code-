#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-076 addendum (2026-09-07) — the Product Owner compared the
//           running template designer with the design they supplied and
//           reported that the two are STRUCTURALLY different.
// Screens:  SET-10 (Settings → Configure → Templates → one template)
// Defects:  DEF-NOT-4443 (the designer drew the LIST's screen id) ·
//           DEF-NOT-4444 (a raw message key in the variant badge) ·
//           DEF-NOT-4445 (the Default variant badge was always true)
// Rules:    B14 rule 31 (no database id is ever a visible value) · rule 36 (the
//           shared kit) · BR-SHL-020 (an absent fact is NAMED, never faked) ·
//           BR-NOT-001 (the default variant) · CR-076 item 2 (the 60/40 split)
// Why:      hard-won law 6 — NO GATE LOOKS AT RENDERED OUTPUT. Four faults in
//           this one rebuild were invisible to `tsc` and to 267 passing DOM
//           cases and visible only here.
// ───────────────────────────────────────────────────────
/**
 * Open SET-10 in a real browser at 1440 and refuse when the design is not on
 * the screen.
 *
 *     # a stack on ports of your own (a port answering 200 is not proof YOUR
 *     # server bound it — check the boot lines in the logs)
 *     cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *       python3.12 manage.py runserver 127.0.0.1:8321 --noreload
 *     cd 07-frontend && ./node_modules/.bin/vite build \
 *       && PORT=8322 API_PROXY_TARGET=http://127.0.0.1:8321 node server.mjs
 *     OUT=/tmp/set10 node 10-scripts/render-checks/set10-design-conformance.mjs
 *
 * ⚠ **REBUILD `dist/` BEFORE YOU WALK.** `server.mjs` serves whatever was on
 * disk when a request arrives and never says the bundle is stale.
 *
 * ⚠ **THE TEMPLATES TAB IS `/settings/reference-data/templates`, NOT
 * `/settings/configure/templates`.** *Configure* is the tab's LABEL and
 * `reference-data` is its id — `SettingsPage.tsx` keeps the old segment
 * deliberately (CR-001) so every deep link still resolves. The wrong address
 * renders the Settings landing tab and every selector below then reports
 * "missing" over a screen that was never opened, which is a walkthrough lying
 * about the thing it exists to check.
 *
 * WHAT IT ASKS, AND WHY EACH ONE NEEDS A BROWSER
 * ----------------------------------------------
 *  · **The screen id.** `<body data-screen-id>` is rendered chrome: no DOM test
 *    reads it and no gate compares a badge with the screen it is drawn over.
 *    The catalogue must say SET-09 and the designer SET-10 (`DEF-NOT-4443`).
 *  · **One h1.** This header is drawn inside the Settings page, which has
 *    already written "Settings". Two page titles in one outline is a fact about
 *    the composed document and cannot be seen from either component alone.
 *  · **The paper is LIGHTER than the page.** `bg-surface` is the card colour
 *    and is DARKER than the ground it stands on, so the "white document card"
 *    read as a hole in the page. Every class was real and every assertion
 *    passed; only `getComputedStyle` says which is lighter.
 *  · **The letterhead and its accent rule.** The seeded disconnection notice
 *    opens with a name and a street address on two lines, and a rule that asked
 *    for one line found no letterhead at all — so the page opened with body
 *    text where the design has a heading and a rule.
 *  · **No token overprints its value in the rail.** A `<code>` with no break
 *    opportunity does not shrink with the slot that contains it. Overlap is a
 *    geometry question and jsdom performs no layout.
 *  · **The 60/40 split still holds in EDIT mode.** CR-076 item 2 is a ruled
 *    ratio and the mode change must not have moved it.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8322";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/set10-conformance";
/** A PRINTABLE class with a letterhead, label/value lines and two surfaces. */
const CODE = process.env.CODE ?? "disconnect_notice_10_day";
const TEMPLATES = `${BASE}/${TENANT}/settings/reference-data/templates`;

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const failures = [];
const lines = [];
const say = (s) => {
  lines.push(s);
  console.log(s);
};
const bad = (s) => {
  failures.push(s);
  say(`  ✗ ${s}`);
};

/** `rgb(a,b,c)` → its perceived lightness, for "is this lighter than that". */
function lightness(css) {
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(css ?? "");
  if (m === null) return null;
  return 0.2126 * +m[1] + 0.7152 * +m[2] + 0.0722 * +m[3];
}

(async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  say("signed in");

  // ── 1 · the two screen ids ───────────────────────────────────────────────
  await page.goto(TEMPLATES, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const listBadge = await page.evaluate(() => document.body.dataset.screenId ?? "(none)");
  say(`catalogue badge: ${listBadge}`);
  if (listBadge !== "SET-09") bad(`the templates CATALOGUE badges ${listBadge}, not SET-09`);

  await page.goto(`${TEMPLATES}?template=${CODE}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  const detailBadge = await page.evaluate(() => document.body.dataset.screenId ?? "(none)");
  say(`designer badge:  ${detailBadge}`);
  if (detailBadge !== "SET-10") {
    bad(
      `the template DESIGNER badges ${detailBadge}, not SET-10 — a fault ` +
        `photographed here would be filed against the catalogue (DEF-NOT-4443)`,
    );
  }
  await page.screenshot({ path: join(OUT, "01-reading.png"), fullPage: true });

  // ── 2 · everything the composed page can be asked in one pass ────────────
  const seen = await page.evaluate(() => {
    const q = (s) => document.querySelector(s);
    const box = (s) => {
      const e = q(s);
      if (!e) return null;
      const r = e.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height) };
    };
    // ⚠ **TWO-DIMENSIONAL, AND MEASURING THE INK (amended 2026-09-07,
    //    `DEF-NOT-4455`'s fix).** This read `k.right - v.left` — a purely
    //    HORIZONTAL comparison of two element BOXES — and it was wrong twice
    //    over. Two boxes stacked VERTICALLY overlap horizontally, so once the
    //    row was allowed to wrap (which is the fix) this reported an overlap on
    //    every healthy row. And a `<code>` inside a `min-w-0` span does not
    //    shrink with its slot: the span's box stays small while the TEXT
    //    overflows across its neighbour, so a box comparison reported ZERO over
    //    the very defect it was written for. A `Range` over each text node
    //    gives the extents a person actually sees.
    const inkRects = (root) => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const out = [];
      let node = walker.nextNode();
      while (node !== null) {
        if ((node.textContent ?? "").trim() !== "") {
          const range = document.createRange();
          range.selectNodeContents(node);
          for (const r of range.getClientRects()) if (r.width > 0 && r.height > 0) out.push(r);
        }
        node = walker.nextNode();
      }
      return out;
    };
    const rows = [...document.querySelectorAll('[data-testid^="merge-field-"]')].map((r) => {
      let worst = 0;
      const kids = [...r.children].filter((c) => (c.textContent ?? "").trim() !== "");
      for (let i = 0; i < kids.length; i += 1)
        for (let j = i + 1; j < kids.length; j += 1)
          for (const a of inkRects(kids[i]))
            for (const b of inkRects(kids[j])) {
              const dx = Math.min(a.right, b.right) - Math.max(a.left, b.left);
              const dy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
              if (dx > 0.5 && dy > 0.5) worst = Math.max(worst, Math.round(dx));
            }
      return { overlap: worst, text: r.textContent.trim().slice(0, 40) };
    });
    const paper = q('[data-testid="preview-page"]');
    return {
      h1s: [...document.querySelectorAll("h1")].map((h) => h.textContent.trim()),
      h2: q(".page-header-id h2")?.textContent?.trim() ?? null,
      kicker: q("[data-kicker]")?.textContent?.trim() ?? null,
      meta: q('[data-testid="head-meta"]')?.textContent?.trim() ?? null,
      actions: [...document.querySelectorAll(".page-header-actions button")].map((b) =>
        b.textContent.trim(),
      ),
      tabAccent: (() => {
        const t = q('[data-page-header-tabs] [aria-selected="true"]');
        if (!t) return null;
        const s = getComputedStyle(t);
        return { border: s.borderBottomColor, width: s.borderBottomWidth, colour: s.color };
      })(),
      strip: q('[data-testid="preview-strip"]')?.textContent?.trim() ?? null,
      main: box('[data-testid="reading-main"]'),
      rail: box('[data-testid="reading-rail"]'),
      paperBg: paper ? getComputedStyle(paper).backgroundColor : null,
      pageBg: getComputedStyle(document.body).backgroundColor,
      letterhead: q('[data-testid="preview-letterhead"]')?.textContent?.trim() ?? null,
      ruleColour: (() => {
        const e = q('[data-testid="preview-rule"]');
        return e ? getComputedStyle(e).backgroundColor : null;
      })(),
      accent: getComputedStyle(document.documentElement).getPropertyValue("--color-accent").trim(),
      pairs: [...document.querySelectorAll("[data-doc-pair]")].length,
      railPanels: [...document.querySelectorAll('[data-testid="reading-rail"] h3')].map((h) =>
        h.textContent.trim(),
      ),
      overlaps: rows.filter((r) => r.overlap > 0),
      rawKey: (document.body.textContent ?? "").includes("templates.detail."),
      sideScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      hasTextarea: !!q('[data-testid="editor-body"]'),
    };
  });
  say(JSON.stringify(seen, null, 2));

  // ⚠ ONE h1. Two page titles in one outline is a fact about the COMPOSED page.
  if (seen.h1s.length !== 1) bad(`${seen.h1s.length} h1(s) on the page: ${seen.h1s.join(" · ")}`);
  if (seen.h2 === null) bad("the template's name is not drawn as the header's title");
  if (seen.kicker === null || !seen.kicker.includes("·")) {
    bad(`the kicker should read TEMPLATE · <group>; it reads ${seen.kicker}`);
  }
  // BR-SHL-020 — the author is not served, so it is NAMED rather than faked.
  if (seen.meta === null || !/author/i.test(seen.meta)) {
    bad("the head's meta line does not name the author absence (BR-SHL-020)");
  }
  if (seen.actions.length < 3) bad(`the head offers ${seen.actions.length} actions, not three`);
  if (seen.hasTextarea) bad("the screen opens on the EDITOR — editing is a mode, and this is not it");

  // The design's tabs are an ACCENT UNDERLINE, not chips.
  if (seen.tabAccent === null) bad("no variant tab strip is drawn");
  else if (seen.tabAccent.width === "0px" || seen.tabAccent.border === "rgba(0, 0, 0, 0)") {
    bad(`the open variant tab has no underline (${JSON.stringify(seen.tabAccent)})`);
  }

  // ⚠ THE PAPER MUST BE LIGHTER THAN THE PAGE. `bg-surface` is the CARD colour
  // and is darker than the ground, so the document read as a hole in the page.
  const paperL = lightness(seen.paperBg);
  const pageL = lightness(seen.pageBg);
  say(`paper lightness ${paperL} vs page ${pageL}`);
  if (paperL === null || pageL === null) bad("no document card is drawn");
  else if (paperL <= pageL) {
    bad(`the paper (${seen.paperBg}) is not lighter than the page (${seen.pageBg})`);
  }

  if (seen.letterhead === null) {
    bad("the document has no letterhead — a name and an address is ONE letterhead");
  }
  if (seen.ruleColour === null) bad("no accent rule under the letterhead");
  if (seen.pairs < 1) {
    bad(`no label/value row in the document (${CODE} renders at least one)`);
  }
  if (seen.railPanels.length !== 3) {
    bad(`the rail holds ${seen.railPanels.length} panels, not the design's three`);
  }
  if (seen.overlaps.length > 0) {
    bad(`${seen.overlaps.length} merge row(s) overprint their value: ${JSON.stringify(seen.overlaps)}`);
  }
  // DEF-NOT-4444 — a message key that resolves to nothing renders as itself.
  if (seen.rawKey) bad("a raw message key is on the screen (DEF-NOT-4444's shape)");
  if (seen.sideScroll) bad("the page body scrolls sideways");
  if (seen.main && seen.rail && seen.main.w <= seen.rail.w) {
    bad(`the document column (${seen.main.w}px) is not wider than the rail (${seen.rail.w}px)`);
  }

  // ── 3 · DEF-NOT-4445: the badge names the OPEN variant ───────────────────
  const tabs = await page.evaluate(() =>
    [...document.querySelectorAll("[data-page-header-tabs] [data-tab]")].map((t) =>
      t.getAttribute("data-tab"),
    ),
  );
  if (tabs.length > 1) {
    await page.click(`[data-tab="${tabs[1]}"]`);
    await page.waitForTimeout(1500);
    const second = await page.evaluate(() => ({
      pill: !!document.querySelector('[data-testid="preview-default-pill"]'),
      action: !!document.querySelector('[data-testid="set-default"]'),
    }));
    say(`second variant → pill ${second.pill}, Set as default ${second.action}`);
    if (second.pill && second.action) bad("both the Default badge and Set as default are drawn");
    await page.screenshot({ path: join(OUT, "02-second-variant.png"), fullPage: true });
  } else {
    say(`only one variant on ${CODE}; the badge/action pair is covered by the DOM suite`);
  }

  // ── 4 · edit mode still splits 60/40 (CR-076 item 2) ─────────────────────
  await page.goto(`${TEMPLATES}?template=${CODE}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  await page.click('[data-testid="edit-wording"]');
  await page.waitForTimeout(1800);
  const edit = await page.evaluate(() => {
    const w = (s) => {
      const e = document.querySelector(s);
      return e ? Math.round(e.getBoundingClientRect().width) : null;
    };
    return {
      rail: w('[data-testid="designer-rail"]'),
      output: w('[data-testid="designer-output"]'),
      textarea: !!document.querySelector('[data-testid="editor-body"]'),
    };
  });
  // ⚠ **AMENDED 2026-09-07 (`DEF-NOT-4457`): THE 60 IS THE DOCUMENT'S.** This
  // measured `rail / (rail + output)` and accepted 0.55–0.65, which was true of
  // a screen giving the WORDING 662px and the DOCUMENT 442px — the Product
  // Owner's *"here 60 is for A big paper showing real docume nt"* pointing the
  // wrong way. A ratio that does not name its panes passes on its own mirror
  // image, so this one names them.
  const ratio = edit.rail && edit.output ? edit.output / (edit.rail + edit.output) : null;
  say(`edit mode: DOCUMENT ${edit.output}px · wording ${edit.rail}px · document share ${ratio?.toFixed(3)}`);
  if (!edit.textarea) bad("Edit wording did not open the wording form");
  if (ratio === null || ratio < 0.55 || ratio > 0.65) {
    bad(`the DOCUMENT is ${(ratio ?? 0).toFixed(3)} of the split, not the Product Owner's 0.60`);
  }
  await page.screenshot({ path: join(OUT, "03-edit-mode.png"), fullPage: true });

  await browser.close();
  writeFileSync(join(OUT, "walk.txt"), lines.join("\n"));

  console.log("\n════════════════════════════════════════════════════════════");
  if (failures.length === 0) {
    console.log(`PASS — SET-10 draws the design. Screenshots in ${OUT}.`);
    process.exit(0);
  }
  console.log(`FAIL — ${failures.length} finding(s):`);
  for (const f of failures) console.log(`  · ${f}`);
  console.log(
    "\nThese are RENDERED observations. `tsc`, eslint and the DOM suites cannot\n" +
      "see any of them, which is why they are here — see this file's header.",
  );
  process.exit(1);
})().catch((err) => {
  console.error("set10 conformance FAILED:", err.message);
  process.exit(1);
});
