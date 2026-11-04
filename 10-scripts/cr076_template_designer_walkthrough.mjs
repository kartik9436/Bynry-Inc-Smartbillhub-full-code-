// ── Trace ──────────────────────────────────────────────
// Change:  CR-076 + its 2026-09-07 addendum — the Product Owner compared the
//          running template screen with the design they supplied and asked for
//          a different SHAPE: *"thi si very importna to achieve - Preview-first:
//          a big paper showing the real document"*, *"here 60 is for A big paper
//          showing real docume nt"*, and, on what surrounds it, *"user does not
//          udnerstand so many option - you should show what customer is going to
//          get - rest is only for information"*.
// Screens: SET-10 (Settings → Configure → Templates → one template)
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//          running app) · law 7 (a check must be shown RED before it is trusted
//          green, and its output must distinguish pass from fail to a READER) ·
//          B14 rule 32 (a description budget) · BR-SHL-010 · BR-SHL-025
// Defects: DEF-NOT-4414 — the print window carried the right DOM with NO CSS ·
//          DEF-NOT-4456 (the paper began below the fold) · DEF-NOT-4457 (the
//          60 was on the wrong pane) · DEF-NOT-4462 (this file waited twenty
//          seconds for a selector the rebuild removed, so nothing had walked
//          this screen since) · DEF-NOT-4464 (a line printed twice) ·
//          DEF-NOT-4465 (an email previewed as a text blob)
// ───────────────────────────────────────────────────────
/**
 * cr076_template_designer_walkthrough — open SET-10 and say what is wrong.
 *
 *     # a stack on ports of your own (a port answering 200 is not proof YOUR
 *     # server bound it — check the boot lines in the logs)
 *     cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *       python3.12 manage.py runserver 127.0.0.1:8321 --noreload
 *     cd 07-frontend && ./node_modules/.bin/vite build \
 *       && PORT=8322 API_PROXY_TARGET=http://127.0.0.1:8321 node server.mjs
 *     OUT=/tmp/cr076 node 10-scripts/cr076_template_designer_walkthrough.mjs
 *
 * ⚠ **REBUILD `dist/` BEFORE YOU WALK.** `server.mjs` serves whatever was on
 * disk when a request arrives and never says the bundle is stale; confirm the
 * hash the page loaded is the hash you just built.
 *
 * ⚠ **IT OPENS THE READING VIEW, WHICH IS WHAT A TEMPLATE OPENS ON — AND THAT
 * IS `DEF-NOT-4462`.** Until 2026-09-07 the first thing this script did was
 * wait for `[data-testid="designer-frame"]`, which the SET-10 rebuild moved
 * behind *Edit wording*. So it timed out after twenty seconds and exited 1 on
 * something that reads exactly like a broken stack — and because this file is
 * run by hand and is in no suite, nothing said so. It was the ONLY thing in
 * this repo that reads this screen's rendered output, and it had not read it
 * for a day. The anchor is now `preview-page` (the paper), which is a claim
 * about the product rather than about a wrapper: if a template stops opening on
 * its document, THAT is the finding.
 *
 * WHAT IT ASKS, AND WHY EVERY ONE OF THESE NEEDS A BROWSER
 * -------------------------------------------------------
 *  · **The paper is ABOVE THE FOLD.** No check in this repo can ask where an
 *    element STARTS, so nothing could see that the document began at 902px in a
 *    900px window while every element was present and every DOM assertion
 *    passed (`DEF-NOT-4456`).
 *  · **The DOCUMENT is the 60, and the panes are NAMED.** The old version of
 *    this measured "the rail is 55–65% of the frame" and the DOM suite pinned
 *    `[3fr_2fr]`: both were true of a screen with the WRONG pane enlarged
 *    (`DEF-NOT-4457`). A ratio check that does not say which side is which
 *    passes on its own mirror image — law 7's second question, applied.
 *  · **The tabs are DERIVED.** It reads `preview_surfaces` OFF THE WIRE — the
 *    payload the screen actually used, not a second request with different
 *    headers — and compares it with the tabs drawn. A hardcoded five passes
 *    every DOM test ever written and fails here on `sms_bill_ready`.
 *  · **Nothing in the merge rail overprints anything else.** Overlap is a
 *    geometry question and jsdom performs no layout, so this is the only
 *    instrument that can ask it. It is a TWO-DIMENSIONAL test on purpose: two
 *    boxes stacked vertically overlap horizontally, and a check comparing only
 *    `left`/`right` reports an overlap for a row that is perfectly fine.
 *  · **No visible text appears twice inside the preview.** Both elements are
 *    individually correct in the repeat this caught (`DEF-NOT-4464`) — the
 *    derived preheader was right, the body was right, and the screen printed
 *    the same sentence twice with a note about our database schema between the
 *    copies. Only the COUNT is the defect.
 *  · **The word *preview* appears at most once outside the document.** The
 *    cheap, mechanical form of B14 rule 32, after the PO said *"why so many
 *    time pre view, pre view word"*. It cannot judge meaning; it can count, and
 *    counting is what nobody was doing.
 *  · **The printout is inspected, styles included.** DEF-NOT-4414 is the whole
 *    argument for the last part: the DOM travelling is not the document
 *    arriving, so this reads `white-space` and `display` in the print window
 *    and writes the PDF a person would get from "Save as PDF".
 *
 * ⚠ **WHAT IT DELIBERATELY DOES NOT ASSERT.** The word *sample* appears twelve
 * to twenty-one times on these screens, and nineteen of those are in the sample
 * DATA — `Sample Customer` at `1 Sample Street, Sample City` on account
 * `SAMPLE-ACCOUNT`. That is a recorded ruling in `template_preview.py` (*"a
 * sample that reads like a real utility's real customer is a sample somebody
 * screenshots into a ticket"*) and is with the Product Owner. A check written
 * against it here would be this lane overruling a ruling with a threshold.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8322";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr076-shots";
//: The window this walk judges "above the fold" against. 1440×1000 is what the
//: Product Owner's own before-numbers were measured at; 900 is the shorter
//: laptop and is reported beside it, because a document that clears one fold
//: and not the other is a fact worth printing rather than hiding behind a
//: single pass/fail.
const VIEWPORT = { width: Number(process.env.WIDTH ?? 1440), height: Number(process.env.HEIGHT ?? 1000) };

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
  throw new Error("no chromium found");
}

const findings = [];
const notes = [];
function say(line) {
  notes.push(line);
  console.log(line);
}
function bad(line) {
  findings.push(line);
  console.error("  ✗ " + line);
}

/**
 * Open a template and wait for THE DOCUMENT, not for a wrapper.
 *
 * ⚠ **`DEF-NOT-4462` IS THE REASON THIS FUNCTION LOOKS LIKE THIS.** It used to
 * wait for `[data-testid="designer-frame"]`, which the SET-10 rebuild moved
 * behind *Edit wording* — so every run timed out after twenty seconds and
 * exited 1 on something indistinguishable from a dead stack, and nothing walked
 * this screen for a day. A walkthrough anchored on a WRAPPER breaks silently
 * when the wrapper moves; anchored on the PAPER, a template that stops opening
 * on its document is reported as the finding it is.
 *
 * A class with no printable surface (SMS, in-app) draws a bubble instead, so
 * the caller says which anchor it expects.
 */
async function openTemplate(page, code, anchor = '[data-testid="preview-page"]') {
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/templates?template=${code}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-testid="template-detail-page"]', { timeout: 20000 });
  await page.waitForSelector(anchor, { timeout: 20000 });
}

/**
 * WHERE THE DOCUMENT STARTS, and how much of it a person can see without
 * touching the scrollbar.
 *
 * ⚠ **THE SCROLLER IS `<main>`, NOT THE WINDOW.** The app shell gives `main`
 * its own overflow, so `document.documentElement.scrollHeight` is the viewport
 * height on every screen in this product and `window.scrollY` never moves. A
 * check that measured against the window would report "above the fold" for a
 * paper 300px below it, which is law 7's *incapable of failing* shape.
 */
async function paperGeometry(page) {
  return page.evaluate(() => {
    const scroller = document.querySelector("main") ?? document.documentElement;
    const fold = scroller.getBoundingClientRect().bottom;
    const paper = document.querySelector('[data-testid="preview-page"]');
    if (paper === null) return null;
    const box = paper.getBoundingClientRect();
    const frame = document.querySelector('[data-testid="reading-frame"], [data-testid="designer-frame"]');
    // The biggest thing drawn inside `main` that is not a pure container — the
    // Product Owner's *"the document IS the screen"*, asked as arithmetic.
    const areas = [...document.querySelectorAll("main *")]
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { id: el.getAttribute("data-testid"), area: Math.round(r.width * r.height) };
      })
      .filter((e) => e.id !== null)
      .sort((a, b) => b.area - a.area);
    return {
      top: Math.round(box.top - scroller.getBoundingClientRect().top + scroller.scrollTop),
      absoluteTop: Math.round(box.top),
      fold: Math.round(fold),
      visible: Math.round(Math.max(0, Math.min(box.bottom, fold) - box.top)),
      width: Math.round(box.width),
      frameWidth: frame === null ? null : Math.round(frame.getBoundingClientRect().width),
      largest: areas.slice(0, 3),
      // The two the design compares. `reading-rail` is measured whether or not
      // it is the biggest, because "the document is the largest element" is
      // only meaningful against the thing that was beating it.
      paneArea: (() => {
        const el = document.querySelector('[data-testid="preview-scroll"]');
        if (el === null) return null;
        const r = el.getBoundingClientRect();
        return Math.round(r.width * r.height);
      })(),
      railArea: (() => {
        const el = document.querySelector('[data-testid="reading-rail"]');
        if (el === null) return null;
        const r = el.getBoundingClientRect();
        return Math.round(r.width * r.height);
      })(),
    };
  });
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium(), headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  // The REAL payload the screen used, read off the wire rather than re-fetched
  // — a second request with different headers is not evidence about this one.
  const payloads = new Map();
  page.on("response", async (r) => {
    if (r.status() >= 500) bad(`${r.status()} ${r.request().method()} ${r.url()}`);
    const match = /\/template-catalog\/([a-z0-9_]+)(?:\?|$)/.exec(r.url());
    if (match !== null && r.request().method() === "GET" && r.status() === 200) {
      try {
        const body = await r.json();
        payloads.set(match[1], (body.data ?? body).preview_surfaces);
      } catch {
        /* not JSON — the SPA fallback, which is not this request */
      }
    }
  });

  // ── sign in ────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  say("signed in");

  // ── 1 · a two-surface notice ───────────────────────────────────────────
  await openTemplate(page, "disconnect_notice_10_day");
  say(
    `served preview_surfaces for disconnect_notice_10_day: ${JSON.stringify(
      payloads.get("disconnect_notice_10_day") ?? null,
    )}`,
  );

  const tabs = page.locator('[data-testid="wireframe-surface-tabs"] [role="tab"]');
  const tabCount = await tabs.count();
  const tabText = await tabs.allTextContents();
  say(`tabs drawn: ${tabCount} → ${JSON.stringify(tabText)}`);
  if (tabCount !== 2) bad(`expected 2 tabs on a "Print + email" notice, saw ${tabCount}`);
  for (const dead of ["sms", "in_app", "contract"]) {
    if ((await page.locator(`[data-testid="wireframe-surface-${dead}"]`).count()) > 0) {
      bad(`a ${dead} tab is offered on a class that has no ${dead} form`);
    }
  }
  // `preview-kind` on a single-surface class, `data-preview-kind` on the
  // selected tab when there is a picker — one fact, one element, never both.
  const openedAs = await page
    .locator('[data-testid="preview-kind"], [data-preview-kind]')
    .first()
    .textContent();
  say(`opens on: ${openedAs} · preview-page present = ${
    (await page.locator('[data-testid="preview-page"]').count()) > 0
  }`);
  await page.screenshot({ path: join(OUT, "01-printable-tab.png"), fullPage: false });

  // ── 1a · THE DOCUMENT PANE SCROLLS, AND ITS LAST LINE IS REACHABLE ──────
  // ⚠ **THE TOP-EDGE NUMBER IS NOT A CRITERION AND HAS NOT BEEN SINCE THE
  // PRODUCT OWNER ANSWERED THE HEIGHT PROBLEM THEMSELVES:** *"you give scroll
  // option in PDF view area"* (2026-09-07). Two targets were written against a
  // top edge before that — 240px, then 560px — and BOTH were cancelled, the
  // second within an hour of being set. A number that has been wrong twice in
  // one day is a number this check should RECORD and not assert: the top edge
  // is reported below, and what is asserted is the thing the ruling actually
  // asks for.
  const geometry = await paperGeometry(page);
  say(
    `paper: top ${geometry.top}px (recorded, NOT asserted — the ruling is the scrolling pane) · ` +
      `${geometry.width}px wide of a ${geometry.frameWidth}px frame ` +
      `(${((geometry.width / geometry.frameWidth) * 100).toFixed(1)}%)`,
  );
  const pane = await page.evaluate(async () => {
    const box = document.querySelector('[data-testid="preview-scroll"]');
    if (box === null) return null;
    const scroller = document.querySelector("main") ?? document.documentElement;
    const cs = getComputedStyle(box);
    const pageBefore = scroller.scrollTop;
    box.scrollTop = box.scrollHeight;               // …to the very end
    await new Promise((r) => requestAnimationFrame(() => r(undefined)));
    const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 2;
    const pageAfter = scroller.scrollTop;
    // WHAT IS ACTUALLY VISIBLE at the bottom of the pane once scrolled there —
    // the ruling's *"the last line is reachable"*, read rather than inferred.
    const boxRect = box.getBoundingClientRect();
    const lastVisible = [...box.querySelectorAll("p, span, li, strong")]
      .filter((el) => el.children.length === 0 && (el.textContent ?? "").trim() !== "")
      .map((el) => ({ r: el.getBoundingClientRect(), t: (el.textContent ?? "").trim() }))
      .filter((e) => e.r.top < boxRect.bottom && e.r.bottom > boxRect.top)
      .pop();
    box.scrollTop = 0;
    return {
      clientHeight: Math.round(box.clientHeight),
      scrollHeight: Math.round(box.scrollHeight),
      // A scrollbar that is DRAWN, not an overlay: the difference between the
      // border box and the content box across the inline axis.
      scrollbarWidth: Math.round(box.offsetWidth - box.clientWidth),
      overflowY: cs.overflowY,
      overscroll: cs.overscrollBehaviorY,
      atEnd,
      pageMoved: pageAfter !== pageBefore,
      lastLine: lastVisible === undefined ? null : lastVisible.t.slice(0, 70),
    };
  });
  if (pane === null) {
    bad("there is no document pane at all — [data-testid=\"preview-scroll\"] is absent");
  } else {
    say(
      `pane: ${pane.clientHeight}px tall over ${pane.scrollHeight}px of letter · ` +
        `overflow-y ${pane.overflowY} · overscroll ${pane.overscroll} · ` +
        `scrollbar ${pane.scrollbarWidth}px · reached the end = ${pane.atEnd} · ` +
        `page moved with it = ${pane.pageMoved}`,
    );
    say(`last line reachable in the pane: ${JSON.stringify(pane.lastLine)}`);
    // 1 · IT SCROLLS AND THE LAST LINE IS REACHABLE — the whole ruling.
    if (!pane.atEnd || pane.lastLine === null) {
      bad("the document pane cannot be scrolled to its end, so the letter's last line is unreachable");
    }
    // 2 · IT LOOKS SCROLLABLE. If the letter appears to end where the frame
    //     ends, a clerk believes it does — which is worse than the page
    //     scrolling this replaced. `overflow-y: auto` over content that happens
    //     to fit proves nothing, so the SCROLLBAR is measured, not the style.
    if (pane.scrollHeight > pane.clientHeight + 2 && pane.scrollbarWidth < 1) {
      bad(
        `the pane holds ${pane.scrollHeight}px of letter in ${pane.clientHeight}px and draws NO ` +
          `scrollbar, so the document looks like it ends where the frame ends`,
      );
    }
    // 3 · IT DOES NOT SCROLL THE PAGE AS WELL. Nested containers that hand off
    //     at the boundary are the classic broken version of this.
    if (pane.pageMoved) {
      bad("scrolling the document pane scrolled the PAGE too — the scroll chained past the pane");
    }
    if (pane.overscroll !== "contain") {
      bad(`the pane's overscroll-behavior is ${pane.overscroll}, not contain, so it will chain`);
    }
  }
  // 4 · THE DOCUMENT IS THE LARGEST THING ON THE SCREEN — the ruling stated as
  //     arithmetic: *"you should show what customer is going to get - rest is
  //     only for information"*. Measured across all 38 rows this tenant serves,
  //     the biggest element used to be `reading-rail` on 33 of them.
  say(`largest elements in main: ${JSON.stringify(geometry.largest)}`);
  const biggest = geometry.largest.find((e) => e.id !== null);
  if (biggest !== undefined && geometry.railArea !== null && geometry.paneArea !== null) {
    say(`document pane ${geometry.paneArea}px² vs rail ${geometry.railArea}px²`);
    if (geometry.railArea >= geometry.paneArea) {
      bad(
        `the RAIL (${geometry.railArea}px²) is at least as large as the document ` +
          `(${geometry.paneArea}px²) — the design's central claim, inverted`,
      );
    }
  }

  // ── 1b · NO VISIBLE TEXT APPEARS TWICE INSIDE THE PREVIEW (DEF-NOT-4464) ──
  // The repeat this caught was two individually-correct elements: the derived
  // preheader was right, the body was right, and the screen printed one
  // sentence twice with a note about our database schema between the copies.
  // Only the COUNT is the defect, so only the count is asserted.
  const repeats = await page.evaluate(() => {
    const pane = document.querySelector('[data-testid="preview-printable"]');
    if (pane === null) return { checked: 0, repeated: [] };
    const seen = new Map();
    for (const el of pane.querySelectorAll("p, span, strong, li, h1, h2, h3, h4")) {
      // LEAF text only — a parent repeats every child by construction.
      if (el.querySelector("p, span, strong, li, h1, h2, h3, h4") !== null) continue;
      const text = (el.textContent ?? "").replace(/\s+/g, " ").trim();
      // Short strings legitimately recur on a document (a currency, a dash, a
      // column heading), so the bar is a SENTENCE's worth.
      if (text.length < 25) continue;
      seen.set(text, (seen.get(text) ?? 0) + 1);
    }
    return {
      checked: seen.size,
      repeated: [...seen.entries()].filter(([, n]) => n > 1).map(([t, n]) => ({ n, t: t.slice(0, 70) })),
    };
  });
  say(`preview text blocks checked: ${repeats.checked} · repeated: ${repeats.repeated.length}`);
  for (const r of repeats.repeated) {
    bad(`the preview prints the same ${r.n} times: ${JSON.stringify(r.t)} (DEF-NOT-4464)`);
  }

  // ── 1c · THE WORD "PREVIEW", COUNTED (B14 rule 32) ──────────────────────
  // The cheap mechanical form of a rule no gate can enforce, after the PO said
  // *"why so many time pre view, pre view word"*. It cannot judge meaning; it
  // can count, and counting is what nobody was doing. The DOCUMENT is excluded
  // — a template whose wording says "preview" is the tenant's business.
  const previewWords = await page.evaluate(() => {
    const scope = document.querySelector('[data-testid="template-detail-page"]');
    const paper = document.querySelector('[data-testid="preview-page"]');
    const clone = scope.cloneNode(true);
    const paperInClone = clone.querySelector('[data-testid="preview-page"]');
    if (paperInClone !== null) paperInClone.remove();
    const text = (clone.textContent ?? "").toLowerCase();
    return {
      outside: (text.match(/preview/g) ?? []).length,
      insideDocument: ((paper?.textContent ?? "").toLowerCase().match(/preview/g) ?? []).length,
    };
  });
  say(
    `the word "preview" appears ${previewWords.outside}× outside the document ` +
      `(${previewWords.insideDocument}× inside it, which is the tenant's wording)`,
  );
  if (previewWords.outside > 1) {
    bad(
      `"preview" appears ${previewWords.outside}× in this screen's own chrome; the design ` +
        `carries one caption line for the whole job (B14 rule 32)`,
    );
  }

  // ── 1d · NOTHING IN THE MERGE RAIL OVERPRINTS ANYTHING (DEF-NOT-4455) ────
  // ⚠ TWO-DIMENSIONAL ON PURPOSE. Two boxes stacked vertically overlap
  // horizontally, so a check comparing only `left`/`right` reports an overlap
  // for a row that is perfectly fine — and the fix for this defect is exactly
  // to let the value drop onto its own line.
  const rail = await page.evaluate(() => {
    // ⚠ **IT MEASURES THE TEXT, NOT THE BOX, AND THAT DISTINCTION IS THE WHOLE
    // CHECK.** The first draft compared each row's child ELEMENTS and reported
    // zero over the pre-fix rail, truthfully and uselessly: `KV_KEY` carries
    // `min-w-0`, so the token's SPAN shrinks to the space available while the
    // `<code>` inside it — which has no break opportunity — overflows and
    // prints across its neighbour. The boxes do not intersect; the ink does. A
    // `Range` over each text node gives the extents a person actually sees, and
    // is the only thing that can tell an overflow from a fit.
    const inkRects = (root) => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const out = [];
      let node = walker.nextNode();
      while (node !== null) {
        if ((node.textContent ?? "").trim() !== "") {
          const range = document.createRange();
          range.selectNodeContents(node);
          for (const r of range.getClientRects()) {
            if (r.width > 0 && r.height > 0) out.push({ r, text: (node.textContent ?? "").trim() });
          }
        }
        node = walker.nextNode();
      }
      return out;
    };
    const rows = [...document.querySelectorAll('[data-testid^="merge-field-"]')];
    const clashes = [];
    for (const row of rows) {
      const kids = [...row.children].filter((c) => (c.textContent ?? "").trim() !== "");
      for (let i = 0; i < kids.length; i += 1) {
        for (let j = i + 1; j < kids.length; j += 1) {
          for (const a of inkRects(kids[i])) {
            for (const b of inkRects(kids[j])) {
              const dx = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
              const dy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
              if (dx > 0.5 && dy > 0.5) {
                clashes.push({
                  row: row.getAttribute("data-testid"),
                  overlap: `${Math.round(dx)}×${Math.round(dy)}px`,
                  text: `${a.text} / ${b.text}`.slice(0, 60),
                });
              }
            }
          }
        }
      }
    }
    return { rows: rows.length, clashes };
  });
  say(`merge rail: ${rail.rows} row(s) measured, ${rail.clashes.length} overlapping`);
  for (const clash of rail.clashes) {
    bad(`${clash.row} overprints itself by ${clash.overlap}: ${clash.text} (DEF-NOT-4455)`);
  }

  // ── 2 · EDIT WORDING: the split, MEASURED, WITH THE PANES NAMED ────────
  // ⚠ **THE NAMING IS THE WHOLE FIX (`DEF-NOT-4457`).** This block used to
  // measure `railShare` and accept 55–65%, and the DOM suite pinned
  // `[3fr_2fr]`. Both were true of a screen giving the WORDING 662px and the
  // DOCUMENT 442px — the Product Owner's *"60 is for A big paper showing real
  // docume nt"* pointing the wrong way. A ratio check that does not say which
  // side is which passes on its own mirror image, so this one says.
  await page.click('[data-testid="edit-wording"]');
  await page.waitForSelector('[data-testid="designer-frame"]', { timeout: 20000 });
  await page.waitForSelector('[data-testid="editor-body"]', { timeout: 20000 });
  const split = await page.evaluate(() => {
    const frame = document.querySelector('[data-testid="designer-frame"]');
    const rail = document.querySelector('[data-testid="designer-rail"]');
    const out = document.querySelector('[data-testid="designer-output"]');
    const cs = getComputedStyle(frame);
    return {
      className: frame.className,
      gridTemplateColumns: cs.gridTemplateColumns,
      railWidth: rail.getBoundingClientRect().width,
      outputWidth: out.getBoundingClientRect().width,
      frameWidth: frame.getBoundingClientRect().width,
      // WHICH ONE IS ON THE LEFT — a fact the ratio cannot carry, and the one
      // that decides whether the paper jumps across the screen when a person
      // presses Edit wording.
      firstChild: frame.firstElementChild?.getAttribute("data-testid") ?? null,
    };
  });
  const documentShare = (split.outputWidth / (split.railWidth + split.outputWidth)) * 100;
  say(
    `edit mode: grid-template-columns = ${split.gridTemplateColumns}; DOCUMENT ${Math.round(
      split.outputWidth,
    )}px, WORDING ${Math.round(split.railWidth)}px → the document is ` +
      `${documentShare.toFixed(1)}% and is the ${split.firstChild === "designer-output" ? "first" : "second"} column`,
  );
  if (documentShare < 55 || documentShare > 65) {
    bad(
      `the DOCUMENT measures ${documentShare.toFixed(1)}% of the frame, not the ~60% the ` +
        `Product Owner asked for — the wording pane has ${(100 - documentShare).toFixed(1)}% ` +
        `(DEF-NOT-4457)`,
    );
  }
  if (split.firstChild !== "designer-output") {
    bad(
      `the wording pane is the FIRST column, so the paper jumps from the left of the reading ` +
        `view to the right of the editor when Edit wording is pressed`,
    );
  }
  await page.screenshot({ path: join(OUT, "01b-edit-wording.png"), fullPage: false });
  // …and back to the reading view, which is where the rest of this walk reads.
  await page.click('[data-testid="close-editor"]');
  await page.waitForSelector('[data-testid="reading-frame"]', { timeout: 20000 });

  // ── 3 · switch to email: the SAME document, a different frame ──────────
  // ⚠ **THIS BLOCK USED TO ASSERT THE DEFECT (`DEF-NOT-4465`).** It required
  // `preview-page` to be GONE after switching to Email — which it was, because
  // an email rendered as one paragraph carrying the raw string while a printed
  // notice got real typography. The Product Owner's verdict on the result was
  // exact: *"it is not PDF preview it is text only preview"*. What a customer
  // receives must not look like a different KIND of thing depending on which
  // template a clerk opened, so the same renderer draws both and the INBOX is
  // the frame around it.
  await page.click('[data-testid="wireframe-surface-email"]');
  await page.waitForSelector('[data-testid="preview-inbox"]', { timeout: 10000 });
  const emailShape = await page.evaluate(() => {
    const inbox = document.querySelector('[data-testid="preview-inbox"]');
    const paper = document.querySelector('[data-testid="preview-page"]');
    const styles = new Set(
      [...(paper?.children ?? [])].map((el) => {
        const cs = getComputedStyle(el);
        return `${cs.fontWeight}/${cs.fontSize}/${cs.textTransform}`;
      }),
    );
    return {
      framed: inbox !== null && paper !== null && inbox.contains(paper),
      subject: inbox?.querySelector('[data-testid="preview-subject"]')?.textContent ?? null,
      // ⚠ MORE THAN ONE TEXT STYLE — the mechanical form of "this is a document
      // and not a text blob". A `<p>` of raw string has exactly one.
      styleCount: styles.size,
    };
  });
  say(
    `after pressing Email: the document is framed as an inbox message = ${emailShape.framed} · ` +
      `subject "${emailShape.subject}" · ${emailShape.styleCount} distinct text style(s) on the page`,
  );
  if (!emailShape.framed) {
    bad("switching to Email did not draw the document inside the inbox frame (DEF-NOT-4465)");
  }
  if (emailShape.styleCount < 2) {
    bad(
      `the email preview uses ${emailShape.styleCount} text style(s), so it is a text blob and ` +
        `not a document — a printed notice on the same screen gets real typography ` +
        `(DEF-NOT-4465)`,
    );
  }
  await page.screenshot({ path: join(OUT, "02-email-tab.png"), fullPage: false });

  // ── 4 · PRINT — what actually comes out ────────────────────────────────
  const [printWindow] = await Promise.all([
    context.waitForEvent("page", { timeout: 15000 }),
    page.click('[data-testid="print-preview"]'),
  ]);
  await printWindow.waitForLoadState("domcontentloaded").catch(() => undefined);
  await printWindow.waitForFunction(() => document.body.children.length > 0, { timeout: 10000 });
  const printed = await printWindow.evaluate(() => ({
    title: document.title,
    styleSheets: document.querySelectorAll('link[rel="stylesheet"], style').length,
    hasInbox: document.querySelector('[data-testid="preview-inbox"]') !== null,
    hasPage: document.querySelector('[data-testid="preview-page"]') !== null,
    hasLockedBlock: document.querySelector('[data-testid^="preview-locked"]') !== null,
    hasPreviewNotice: document.querySelector('[data-testid="preview-notice"]') !== null,
    hasPre: document.querySelector("pre") !== null,
    text: (document.body.innerText || "").slice(0, 400),
  }));
  say(`print window title: ${printed.title}`);
  say(
    `print window carries: stylesheets=${printed.styleSheets} inbox=${printed.hasInbox} ` +
      `paper-page=${printed.hasPage} locked-rights-block=${printed.hasLockedBlock} ` +
      `preview-notice=${printed.hasPreviewNotice} bare-<pre>=${printed.hasPre}`,
  );
  if (!printed.hasInbox) bad("the print window does not carry the EMAIL drawing that was on screen");
  if (!printed.hasLockedBlock) bad("the print window has no locked rights block");
  if (!printed.hasPreviewNotice) bad("the print window does not say it is a preview");
  say("printed text begins: " + JSON.stringify(printed.text.replace(/\s+/g, " ").slice(0, 220)));

  // ⚠ DEF-NOT-4414 — THE DOM TRAVELLING IS NOT THE DOCUMENT ARRIVING. The first
  // version of this printed the right nodes with NO CSS: the sheet's href was
  // root-relative and `about:blank` has no base to resolve it against. So this
  // reads COMPUTED STYLE, which is the only thing that can tell the difference.
  await printWindow.waitForFunction(() => document.styleSheets.length > 0, { timeout: 10000 })
    .catch(() => undefined);
  const styled = await printWindow.evaluate(() => {
    // ⚠ **A PROSE BLOCK INSIDE THE PAGE, NOT THE PAGE ITSELF.** This used to
    // select `[data-testid="preview-inbox"] p` — the single paragraph an email
    // used to be — and `preview-page` as a fallback. Since `DEF-NOT-4465` an
    // email IS a page and the page's CHILDREN each declare their own
    // white-space (`documentBlocks`), so asking the card is asking the wrong
    // element: it answers `normal`, correctly, about a container that sets
    // nothing. What has to survive the trip is the author's own line breaks,
    // and they live on the prose blocks.
    const page = document.querySelector('[data-testid="preview-page"]');
    const paper =
      [...(page?.children ?? [])].find(
        (el) => el.tagName === "P" && (el.textContent ?? "").trim().length > 40,
      ) ?? page;
    const strip = document.querySelector('[data-testid="preview-strip"]');
    return {
      sheets: document.styleSheets.length,
      sheetHrefs: [...document.querySelectorAll('link[rel="stylesheet"]')].map((l) => l.href),
      paperWhiteSpace: paper === null ? null : getComputedStyle(paper).whiteSpace,
      paperPadding: paper === null ? null : getComputedStyle(paper).padding,
      stripDisplay: strip === null ? null : getComputedStyle(strip).display,
    };
  });
  say(
    `print window styles: sheets=${styled.sheets} href=${JSON.stringify(styled.sheetHrefs)} ` +
      `document white-space=${styled.paperWhiteSpace} padding=${styled.paperPadding} ` +
      `strip display=${styled.stripDisplay}`,
  );
  if (styled.sheets === 0) bad("the print window loaded no stylesheet at all (DEF-NOT-4414)");
  if (styled.paperWhiteSpace !== "pre-wrap") {
    bad(`the printed document is unstyled — white-space is ${styled.paperWhiteSpace}, not pre-wrap`);
  }
  if (styled.stripDisplay !== null && styled.stripDisplay !== "flex") {
    bad(`the printed strip is unstyled — display is ${styled.stripDisplay}, not flex`);
  }
  await printWindow.screenshot({ path: join(OUT, "03-print-window.png"), fullPage: true });

  // The PDF a person would get by choosing "Save as PDF" in that dialog.
  const cdp = await printWindow.context().newCDPSession(printWindow);
  const pdf = await cdp.send("Page.printToPDF", { printBackground: true });
  writeFileSync(join(OUT, "04-printed.pdf"), Buffer.from(pdf.data, "base64"));
  say(`PDF written: ${join(OUT, "04-printed.pdf")}`);
  await printWindow.close();

  // ── 5 · a ONE-surface class draws no strip ─────────────────────────────
  await openTemplate(page, "sms_bill_ready", '[data-testid="preview-sms-bubble"]');
  say(`served preview_surfaces for sms_bill_ready: ${JSON.stringify(payloads.get("sms_bill_ready") ?? null)}`);
  const strip = await page.locator('[data-testid="wireframe-surface-tabs"]').count();
  const bubble = await page.locator('[data-testid="preview-sms-bubble"]').count();
  const printBtn = page.locator('[data-testid="print-preview"]');
  say(
    `sms_bill_ready: surface strip drawn = ${strip > 0} · sms bubble = ${bubble > 0} · ` +
      `Print present = ${(await printBtn.count()) > 0} · disabled = ${await printBtn.isDisabled()}`,
  );
  if (strip !== 0) bad("a one-surface class draws a tab strip with nothing to switch to");
  await page.screenshot({ path: join(OUT, "05-sms-no-strip.png"), fullPage: false });

  // ── 6 · a CONTRACT — the surface a channel does not name ───────────────
  // ⚠ A CONTRACT HAS NO VERSION AND THEREFORE NO RENDERED PAGE. BR-NOT-002
  // makes it effective-dated and that date is a human's choice, so the wording
  // the platform OFFERS arrives on the payload and never as a version — which
  // makes that block the document on these four classes. Anchoring on
  // `preview-page` here waits twenty seconds for something the product
  // correctly does not draw, which is the shape of `DEF-NOT-4462` all over
  // again.
  await openTemplate(page, "contract_payment_plan", '[data-testid="platform-default-offer"]');
  const offerPlacement = await page.evaluate(() => {
    const offer = document.querySelector('[data-testid="platform-default-offer"]');
    const main = document.querySelector('[data-testid="reading-main"]');
    const rail = document.querySelector('[data-testid="reading-rail"]');
    const pane = document.querySelector('[data-testid="preview-scroll"]');
    return {
      inMain: main !== null && offer !== null && main.contains(offer),
      inRail: rail !== null && offer !== null && rail.contains(offer),
      inPane: pane !== null && offer !== null && pane.contains(offer),
      width: offer === null ? null : Math.round(offer.getBoundingClientRect().width),
    };
  });
  say(
    `contract offer: in the main column = ${offerPlacement.inMain} · in the rail = ` +
      `${offerPlacement.inRail} · inside the scrolling pane = ${offerPlacement.inPane} · ` +
      `${offerPlacement.width}px wide`,
  );
  // ⚠ `DEF-NOT-4482`. The pane wrapped the RENDERED preview, which is the path
  // 34 of the 38 rows take. The four contracts take the other one — BR-NOT-002
  // makes a contract effective-dated, so none has a published version and none
  // has a rendered preview — so the LONGEST documents in the catalogue were the
  // four drawn OUTSIDE the box that exists to stop a document pushing the page
  // down. Every check of the pane passed, because every check was pointed at a
  // template that has one.
  if (!offerPlacement.inPane) {
    bad(
      "a contract's offered wording is drawn OUTSIDE the scrolling pane, so the one class " +
        "that most needs the pane is the one that does not get it (DEF-NOT-4482)",
    );
  }
  if (!offerPlacement.inMain) {
    bad(
      "a contract's offered wording is drawn outside the main column — on these four classes " +
        "that block IS the document, and a document in a 320px rail is hard-won law 2 wearing " +
        "a tidy layout",
    );
  }
  say(
    `served preview_surfaces for contract_payment_plan: ${JSON.stringify(
      payloads.get("contract_payment_plan") ?? null,
    )}`,
  );
  const contractTabs = await page
    .locator('[data-testid="wireframe-surface-tabs"] [role="tab"]')
    .allTextContents();
  say(`contract_payment_plan tabs: ${JSON.stringify(contractTabs)}`);
  await page.screenshot({ path: join(OUT, "06-contract.png"), fullPage: false });


  /* ══ 7 · EVERY ROW THE CATALOGUE SERVES, NOT SIX NAMED ONES ══════════════
     Sections 1–6 walk six templates chosen because each one exercises a
     feature. That is the right shape for a feature, and the WRONG shape for a
     claim about the screen: the PO's sentence — *"you should show what
     customer is going to get"* — is a claim about every template a clerk can
     open, and the three findings that mattered most today were all found by
     counting rows rather than by looking at one.

     ⚠ **THE LIST IS READ OFF THE WIRE, NEVER TYPED HERE.** A hardcoded list of
     28 or 41 goes stale the day a class is added, and the PO added TWELVE on
     2026-09-07 (41 → 53 classes). A walk that names its own rows would have
     gone on reporting a clean sweep over a catalogue it no longer covers, which
     is law 7's *reporting zero over a scope it silently excludes*. So this
     sweeps whatever `GET /template-catalog` returns and PRINTS THE COUNT beside
     the result — a number a reader can compare with the register.

     ⚠ **AND IT PRINTS WHAT IT SKIPPED.** A class whose screen draws neither a
     document nor a platform-default offer is counted and named rather than
     quietly passed over, because "0 findings over 38 rows" and "0 findings over
     the 12 rows I could read" are indistinguishable otherwise. */
  const catalogueRows = [];
  page.on("response", async (r) => {
    if (!/\/template-catalog(\?|$)/.test(r.url())) return;
    if (r.request().method() !== "GET" || r.status() !== 200) return;
    try {
      const body = await r.json();
      const payload = body.data ?? body;
      for (const row of payload.rows ?? payload.results ?? []) catalogueRows.push(row);
    } catch {
      /* the SPA fallback, not this request */
    }
  });
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/templates`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2500);
  const everyCode = [...new Map(catalogueRows.map((r) => [r.code, r])).entries()];
  say(`sweeping EVERY template the catalogue serves: ${everyCode.length} rows`);
  if (everyCode.length === 0) {
    bad("the catalogue served no rows — the sweep below checked nothing at all");
  }

  const skipped = [];
  const shapeSeen = new Map();
  for (const [code, row] of everyCode) {
    await page.goto(
      `${BASE}/${TENANT}/settings/reference-data/templates?template=${code}`,
      { waitUntil: "networkidle" },
    );
    try {
      await page.waitForSelector('[data-testid="preview-pane"]', { timeout: 20000 });
    } catch {
      bad(`${code}: the screen drew no preview pane at all`);
      continue;
    }
    await page.waitForTimeout(250);

    const seen = await page.evaluate(async () => {
      const q = (s) => document.querySelector(s);
      const scroller = q("main") ?? document.documentElement;
      const pane = q('[data-testid="preview-scroll"]');
      const doc =
        q('[data-testid="preview-page"]') ??
        q('[data-testid="preview-sms-bubble"]') ??
        q('[data-testid="preview-bell-panel"]') ??
        q('[data-testid="platform-default-offer"]');

      /* ── the ruling: the pane scrolls and the LAST LINE IS REACHABLE ──────
         PO 2026-09-07: *"you give scroll option in PDF view area"*. Asserted by
         DOING it — scroll the pane to its end and look at what is on screen —
         because `overflow-y: auto` is a style, not a promise: a pane that
         clips reads identically in the DOM. */
      let scroll = null;
      if (pane !== null) {
        const pageBefore = scroller.scrollTop;
        pane.scrollTop = pane.scrollHeight;
        await new Promise((r) => requestAnimationFrame(() => r(undefined)));
        const paneBox = pane.getBoundingClientRect();
        // The document's own last inked line, and whether it is now on screen.
        let lastLine = null;
        if (doc !== null) {
          const leaves = [...doc.querySelectorAll("*")].filter(
            (el) => el.children.length === 0 && (el.textContent ?? "").trim() !== "",
          );
          const el = leaves[leaves.length - 1];
          if (el !== undefined) {
            const b = el.getBoundingClientRect();
            lastLine = {
              text: (el.textContent ?? "").trim().slice(0, 60),
              onScreen: b.bottom <= paneBox.bottom + 2 && b.bottom >= paneBox.top,
            };
          }
        }
        scroll = {
          clientH: pane.clientHeight,
          scrollH: pane.scrollHeight,
          scrollable: pane.scrollHeight > pane.clientHeight + 1,
          // A drawn track. `scrollbar-gutter: stable` reserves it, so a pane
          // that LOOKS like a letter ending at the frame is visible here as a
          // zero gutter.
          gutter: pane.offsetWidth - pane.clientWidth,
          atEnd: pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 2,
          // How far the pane's own bottom falls past the window's — the fact
          // that makes a NON-scrolling pane provable rather than assumed.
          bottomBelowFold: Math.round(
            paneBox.bottom - (scroller.getBoundingClientRect().bottom),
          ),
          pageMoved: scroller.scrollTop !== pageBefore,
          lastLine,
        };
        pane.scrollTop = 0;
      }

      const area = (el) => {
        if (el === null) return null;
        const r = el.getBoundingClientRect();
        return Math.round(r.width * r.height);
      };

      // repeated visible text INSIDE the preview
      const printable = q('[data-testid="preview-printable"]') ?? q('[data-testid="preview-pane"]');
      const counts = new Map();
      if (printable !== null) {
        for (const el of printable.querySelectorAll("*")) {
          if (el.children.length > 0) continue;
          const t = (el.textContent ?? "").trim();
          if (t.length >= 25) counts.set(t, (counts.get(t) ?? 0) + 1);
        }
      }

      // the word "preview" OUTSIDE the document
      const outside = [];
      for (const el of document.querySelectorAll("main *")) {
        if (el.children.length > 0) continue;
        if (doc !== null && doc.contains(el)) continue;
        const t = (el.textContent ?? "").trim();
        if (t !== "" && /preview/i.test(t)) outside.push(t.slice(0, 40));
      }

      const bubble = q('[data-testid="preview-sms-bubble"]');
      return {
        drew: doc === null ? null : doc.getAttribute("data-testid"),
        scroll,
        paneArea: area(pane),
        railArea: area(q('[data-testid="reading-rail"], [data-testid="designer-rail"]')),
        repeated: [...counts.entries()].filter(([, n]) => n > 1).map(([t]) => t.slice(0, 50)),
        previewOutside: outside,
        bubbleWidth: bubble === null ? null : Math.round(bubble.getBoundingClientRect().width),
        smsCount: q('[data-testid="preview-sms-count"]') !== null,
        sendTest: document.querySelectorAll('[data-testid="test-send"]').length,
        sendTestNote: document.querySelectorAll('[data-testid="test-send-reason"]').length,
        signature: document.querySelectorAll('[data-testid="preview-signature"]').length,
        audience: document.querySelectorAll('[data-testid="preview-audience"]').length,
        letterhead: document.querySelectorAll('[data-testid="preview-letterhead"]').length,
      };
    });

    if (seen.drew === null) {
      skipped.push(code);
      continue;
    }
    shapeSeen.set(seen.drew, (shapeSeen.get(seen.drew) ?? 0) + 1);

    // ① the pane scrolls and the last line is reachable
    if (seen.scroll === null) {
      bad(`${code}: the document is not inside a scrolling pane`);
    } else {
      if (seen.scroll.scrollable) {
        if (!seen.scroll.atEnd) bad(`${code}: the document pane will not scroll to its end`);
        if (seen.scroll.lastLine !== null && !seen.scroll.lastLine.onScreen) {
          bad(
            `${code}: the letter's last line is unreachable — scrolled the pane to its end and ` +
              `"${seen.scroll.lastLine.text}" is still off screen`,
          );
        }
        // ② a track a person can see
        if (seen.scroll.gutter < 1) {
          bad(
            `${code}: the pane scrolls but draws no scrollbar track (${seen.scroll.clientH}px ` +
              `showing ${seen.scroll.scrollH}px) — it reads as a letter that ends here`,
          );
        }
      }
      /* ⚠ **AND THE `else` IS THE HALF THAT COULD HAVE BEEN MISSING.** Every
         assertion above is guarded on `scrollable`, so a pane that simply GREW
         TO FIT THE WHOLE LETTER — which is the bug the PO's ruling exists to
         fix — reports `scrollable: false` and sails through all of them. That
         is law 7's *incapable of failing* shape hiding inside a correct-looking
         guard. A pane that does not scroll has to earn it by ENDING ABOVE THE
         FOLD. */
      if (!seen.scroll.scrollable && seen.scroll.bottomBelowFold > 2) {
        bad(
          `${code}: the document pane does not scroll and runs ${seen.scroll.bottomBelowFold}px ` +
            `past the bottom of the window — it grew to fit the letter instead of scrolling it`,
        );
      }
      // ③ scrolling the document must not scroll the page underneath it
      if (seen.scroll.pageMoved) {
        bad(`${code}: scrolling the document pane scrolled the page with it`);
      }
    }

    // ④ the document is the bigger half
    if (seen.paneArea !== null && seen.railArea !== null && seen.paneArea <= seen.railArea) {
      bad(
        `${code}: the rail is larger than the document (${seen.railArea}px² vs ` +
          `${seen.paneArea}px²) — the design's central claim, inverted`,
      );
    }

    // ⑤ nothing said twice inside the preview
    for (const t of seen.repeated) bad(`${code}: "${t}" is printed twice inside the preview`);

    // ⑥ the word "preview" at most once outside the document
    if (seen.previewOutside.length > 1) {
      bad(
        `${code}: the word "preview" appears ${seen.previewOutside.length} times outside the ` +
          `document — ${JSON.stringify(seen.previewOutside)}`,
      );
    }

    // ⑦ the shape-specific ones
    if (seen.drew === "preview-sms-bubble") {
      if (seen.bubbleWidth > 200) {
        bad(
          `${code}: the text-message bubble is ${seen.bubbleWidth}px wide — wider than the phone ` +
            `it is going to, so the wrapping a clerk sees is not the wrapping the customer gets`,
        );
      }
      if (!seen.smsCount) {
        bad(`${code}: a text message with no character count beside it — nothing says what it costs`);
      }
    }
    if (seen.drew === "preview-bell-panel") {
      if (seen.sendTest !== 0 || seen.sendTestNote !== 0) {
        bad(
          `${code}: an in-app banner offers "Send test to me" (${seen.sendTest} control, ` +
            `${seen.sendTestNote} note) and there is nowhere to send it`,
        );
      }
      if (seen.audience === 0) {
        bad(`${code}: nothing on screen says this one is read by a clerk and not by a customer`);
      }
      if (seen.letterhead !== 0) {
        bad(`${code}: an in-app banner drew a letterhead — it is not a letter from the utility`);
      }
    }
  }

  say(
    `swept ${everyCode.length} rows · shapes drawn: ` +
      JSON.stringify(Object.fromEntries(shapeSeen)) +
      (skipped.length === 0
        ? " · none skipped"
        : ` · SKIPPED ${skipped.length} that drew no document: ${JSON.stringify(skipped)}`),
  );
  if (skipped.length > 0) {
    // A declared blind spot with no number beside it is indistinguishable from
    // an empty one (hard-won law 7). This one has a number and its rows named.
    bad(
      `${skipped.length} of ${everyCode.length} templates drew no document and no offered ` +
        `wording, so this sweep could say nothing about them`,
    );
  }

  await browser.close();

  console.log(`\n── walkthrough summary (viewport ${VIEWPORT.width}×${VIEWPORT.height}) ──`);
  for (const n of notes) console.log("  " + n);
  if (findings.length) {
    console.log(`\nFINDINGS (${findings.length}):`);
    for (const f of findings) console.log("  ✗ " + f);
    process.exit(1);
  }
  console.log("\nno findings");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
