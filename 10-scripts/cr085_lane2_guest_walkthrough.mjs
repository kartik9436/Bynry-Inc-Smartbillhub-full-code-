// ── Trace ──────────────────────────────────────────────
// Change:  CR-085 step 2 lane 2 — the GUEST ENTRANCE & ERRANDS, ten routes:
//          the landing page · /sign-in · /enrol · /forgot-password · /track ·
//          /report · /visit · /visit/:slug · /help · /help/:slug
// Defects: DEF-CWP-4851 (nine routes ignore the portal's on/off switch) ·
//          DEF-CWP-4852 (no emergency band) · DEF-CWP-4853 (a staff error
//          panel with *Download error report* on a public page) ·
//          DEF-CWP-4854 (*Nothing here matches what you typed* said to
//          somebody who typed nothing) · DEF-CWP-4855 (*Postcode*) ·
//          DEF-CWP-4856 (rule 39 field anatomy) · DEF-CWP-4858 (a live
//          Continue over three empty required fields)
// Rules:   R-10 (the way out beside the bad news) · R-22 (three states, three
//          SENTENCES) · hard-won law 3 (defaults fail closed) · law 6 (no gate
//          in this repo reads rendered output) · B14 rule 39
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THE OFF-SWITCH IS PROVED BY REWRITING THE RESPONSE AND NOT BY
// SWITCHING A TENANT OFF.** `is_live` lives in one row of `portal_settings` on
// a stack six lanes share, and turning it off would take the portal down for
// all of them. The gate being tested is the CLIENT's, so the honest way to
// exercise it is to hand the client the payload a switched-off utility sends:
// `page.route` intercepts `public/front` and flips `is_live` to false. What
// that CANNOT prove is the server half — see §OFF's own note.
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8412";
// Two tenants on purpose: `pine-hill` has help answers, service centres, an
// emergency number and office hours; `brazosbend` has NONE of them, so it is
// the only place the EMPTY states can be seen at all.
const FULL = process.env.FULL_TENANT ?? "pine-hill";
const BARE = process.env.BARE_TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/cr085-lane2";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const say = (...parts) => console.log(...parts);
const failures = [];
function check(ok, label, detail) {
  say(`${ok ? "  PASS" : "  FAIL"}  ${label}${detail === undefined ? "" : ` — ${detail}`}`);
  if (!ok) failures.push(`${label}${detail === undefined ? "" : ` — ${detail}`}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });

/** Everything one address renders, read out of the DOM in one evaluate. */
async function readScreen(page) {
  return page.evaluate(() => {
    const text = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : null);
    const heads = [...document.querySelectorAll("h1")].map((h) => text(h));
    const screens = [...document.querySelectorAll("[data-screen]")].map((el) =>
      el.getAttribute("data-screen"),
    );
    const state = document.querySelector("[data-portal-state]");
    return {
      screens,
      heads,
      holding: document.querySelectorAll('[data-holding="true"]').length,
      frame: document.querySelectorAll("[data-portal-frame]").length,
      bands: document.querySelectorAll("[data-emergency-band]").length,
      phone: text(document.querySelector("[data-emergency-phone]")),
      stateKind: state ? state.getAttribute("data-portal-state") : null,
      stateSentence: text(document.querySelector("[data-state-sentence]")),
      waysOut: [...document.querySelectorAll("[data-way-out]")].map((el) =>
        el.getAttribute("data-way-out"),
      ),
      // The staff failure panel's own controls. Any of these on a public page
      // is `DEF-CWP-4853`.
      staffPanel: [...document.querySelectorAll("button")]
        .map((b) => text(b))
        .filter((s) => s && /download error report/i.test(s)).length,
      rawKeys: (document.body.innerText.match(/portal\.[a-zA-Z0-9._]+/g) ?? []).slice(0, 5),
      overflow: document.documentElement.scrollWidth > window.innerWidth,
      body: document.body.innerText.replace(/\s+/g, " ").trim().slice(0, 400),
    };
  });
}

/** label→input, input→helper and field→field, in pixels, off the live boxes. */
async function readFieldAnatomy(page) {
  return page.evaluate(() => {
    const out = [];
    const fields = [...document.querySelectorAll("[data-field]")];
    for (let i = 0; i < fields.length; i += 1) {
      const field = fields[i];
      const id = field.getAttribute("data-field");
      const label = field.querySelector("label");
      const control = field.querySelector("input, textarea, select");
      const helper = [...field.querySelectorAll("p")].find((p) => !p.hasAttribute("data-field-error"));
      const box = (el) => (el ? el.getBoundingClientRect() : null);
      const l = box(label);
      const c = box(control);
      const h = box(helper);
      const next = box(fields[i + 1]);
      const bottom = box(field);
      out.push({
        id,
        labelToInput: l && c ? Math.round(c.top - l.bottom) : null,
        inputToHelper: c && h ? Math.round(h.top - c.bottom) : null,
        fieldToField: next && bottom ? Math.round(next.top - bottom.bottom) : null,
      });
    }
    return out;
  });
}

/** Hand the client the payload a switched-off utility actually sends. */
async function withPortalOff(page, run) {
  await page.route("**/portal/public/front", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, is_live: false, cards: [], links: {} } });
  });
  try {
    await run();
  } finally {
    await page.unroute("**/portal/public/front");
  }
}

/**
 * Open an address and wait for the SCREEN, not for the network.
 *
 * ⚠ **`waitUntil: "networkidle"` IS NOT "THE PAGE IS DRAWN", AND THIS WALK
 * REPORTED TWO FALSE REDS BEFORE IT SAID SO.** On an SPA the last request can
 * finish a frame before React paints, and the read then sees a `<body>` with
 * no `[data-screen]` in it at all — which this file dutifully reported as
 * *exactly one h1 — saw 0* on `/track` at 390 while the identical route at
 * 1280 passed. A check whose red means *the harness was early* is worse than
 * no check, because the next reader cannot tell it from a real one
 * (hard-won law 7). So: wait for the mark every portal screen carries — its
 * own `data-screen`, or the holding page's `data-holding` — and only then read.
 */
async function openRoute(page, url) {
  await page.goto(url, { waitUntil: "networkidle" });
  try {
    await page.waitForSelector("[data-screen], [data-holding], [data-portal-state]", {
      timeout: 40000,
    });
  } catch {
    // ⚠ **SAY SO RATHER THAN READ AN EMPTY BODY.** The first version of this
    // swallowed the timeout and let the read happen anyway, which turned a
    // harness problem into two product-shaped reds: `/track` at 390 reported
    // *exactly one h1 — saw 0* with no `[data-screen]` in the document, while
    // the SAME address opened on its own rendered `CWP-012`, its heading and
    // its emergency band at both widths. A check that reports *the page is
    // wrong* when it means *I gave up waiting* is the worst kind — it is
    // indistinguishable from the real thing, and on a shared box running six
    // lanes it is also the common one.
    say(`  ⚠ HARNESS: nothing rendered within 40s at ${url} — this is the walk giving up, not a screen`);
  }
}

const ROUTES = [
  ["landing", ""],
  ["sign-in", "/sign-in"],
  ["enrol", "/enrol"],
  ["forgot-password", "/forgot-password"],
  ["track", "/track"],
  ["report", "/report"],
  ["visit", "/visit"],
  ["visit-one", "/visit/main-office"],
  ["help", "/help"],
  ["help-one", "/help/how-do-i-check-for-a-leak"],
];

const report = {};

for (const width of [390, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  say(`\n════════ ${width}px ════════`);

  // ── 1 · every route on a tenant with content ────────────────────────────
  say(`\n── ${FULL} (content published, emergency number published) @${width}`);
  for (const [name, path] of ROUTES) {
    await openRoute(page, `${BASE}/${FULL}/portal${path}`);
    const seen = await readScreen(page);
    report[`${FULL}|${name}|${width}`] = seen;
    await page.screenshot({ path: join(OUT, `${FULL}-${name}-${width}.png`), fullPage: true });
    say(
      `  ${name.padEnd(16)} screen=${(seen.screens[0] ?? "—").padEnd(8)} h1=${JSON.stringify(seen.heads[0] ?? null)} bands=${seen.bands} state=${seen.stateKind ?? "—"}`,
    );
    check(seen.heads.length === 1, `${name} @${width} · exactly one h1`, `saw ${seen.heads.length}`);
    check(seen.bands === 1, `${name} @${width} · exactly one emergency band`, `saw ${seen.bands}`);
    check(seen.staffPanel === 0, `${name} @${width} · no staff error panel`, `saw ${seen.staffPanel}`);
    check(seen.rawKeys.length === 0, `${name} @${width} · no raw catalogue key on screen`, seen.rawKeys.join(", "));
    check(!seen.overflow, `${name} @${width} · no sideways scroll`);
  }

  // ── 2 · the EMPTY tenant: /visit, /help and the two detail screens ──────
  say(`\n── ${BARE} (nothing published, NO emergency number) @${width}`);
  for (const [name, path] of ROUTES) {
    await openRoute(page, `${BASE}/${BARE}/portal${path}`);
    const seen = await readScreen(page);
    report[`${BARE}|${name}|${width}`] = seen;
    await page.screenshot({ path: join(OUT, `${BARE}-${name}-${width}.png`), fullPage: true });
    say(
      `  ${name.padEnd(16)} screen=${(seen.screens[0] ?? "—").padEnd(8)} h1=${JSON.stringify(seen.heads[0] ?? null)} state=${seen.stateKind ?? "—"} ways=${JSON.stringify(seen.waysOut)}`,
    );
    say(`      sentence: ${JSON.stringify(seen.stateSentence)}`);
    check(seen.heads.length === 1, `${BARE}/${name} @${width} · exactly one h1`, `saw ${seen.heads.length}`);
    check(seen.staffPanel === 0, `${BARE}/${name} @${width} · no *Download error report*`, `saw ${seen.staffPanel}`);
    check(seen.frame === 1, `${BARE}/${name} @${width} · rendered inside the guest frame`, `saw ${seen.frame}`);
    check(!seen.overflow, `${BARE}/${name} @${width} · no sideways scroll`);
  }

  // R-22: the empty /help and the no-match /help must not say the same thing.
  await openRoute(page, `${BASE}/${FULL}/portal/help`);
  await page.fill("#cwp011-search", "zzzzqqq");
  await page.waitForTimeout(200);
  const noMatch = await readScreen(page);
  report[`nomatch|${width}`] = noMatch;
  const empty = report[`${BARE}|help|${width}`];
  say(`\n  R-22 · empty  : ${JSON.stringify(empty.stateSentence)}`);
  say(`  R-22 · no-match: ${JSON.stringify(noMatch.stateSentence)}`);
  check(
    empty.stateSentence !== null && noMatch.stateSentence !== null &&
      empty.stateSentence !== noMatch.stateSentence,
    `R-22 @${width} · empty and no-match are different sentences`,
    `${JSON.stringify(empty.stateSentence)} vs ${JSON.stringify(noMatch.stateSentence)}`,
  );

  // ── 3 · the OFF switch, on all ten ─────────────────────────────────────
  say(`\n── the portal switched OFF @${width} (is_live:false on the wire)`);
  // ⚠ **THE SECOND HALF OF `DEF-CWP-4851`, AND THIS IS THE ONLY PLACE IT CAN
  // BE PROVED.** A page can hide its own screen and still ask the server for
  // the utility's help articles — two different statements, and the vitest
  // suite can make neither: `renderToStaticMarkup` runs no effects, so
  // react-query never starts a fetch there whatever `enabled` says. Here a
  // real browser does, so every request it makes is countable.
  const CONTENT_READS = /\/portal\/public\/(help|service-centres)/;
  const contentReads = [];
  const listen = (request) => {
    if (CONTENT_READS.test(request.url())) contentReads.push(request.url());
  };
  page.on("request", listen);
  await withPortalOff(page, async () => {
    for (const [name, path] of ROUTES) {
      await openRoute(page, `${BASE}/${FULL}/portal${path}`);
      const seen = await readScreen(page);
      report[`off|${name}|${width}`] = seen;
      await page.screenshot({ path: join(OUT, `off-${name}-${width}.png`), fullPage: true });
      say(`  ${name.padEnd(16)} holding=${seen.holding} screens=${JSON.stringify(seen.screens)} h1=${JSON.stringify(seen.heads[0] ?? null)}`);
      check(seen.holding === 1, `OFF ${name} @${width} · the holding page, and nothing behind it`, `body: ${seen.body.slice(0, 120)}`);
      check(
        seen.screens.filter((s) => s !== "CWP-001").length === 0,
        `OFF ${name} @${width} · no other screen rendered`,
        JSON.stringify(seen.screens),
      );
    }
  });
  page.off("request", listen);
  report[`off-content-reads|${width}`] = contentReads;
  say(`  content reads issued while the portal was off: ${contentReads.length}`);
  check(
    contentReads.length === 0,
    `OFF @${width} · a switched-off portal reads no content from the server`,
    contentReads.join(" · "),
  );

  // ── 4 · rule 39's field anatomy on the five guest forms ────────────────
  say(`\n── B14 rule 39 field anatomy @${width} (ratified 5 / 6 / 20)`);
  for (const [name, path] of [
    ["sign-in", "/sign-in"],
    ["enrol", "/enrol"],
    ["forgot-password", "/forgot-password"],
    ["track", "/track"],
    ["report", "/report"],
  ]) {
    await openRoute(page, `${BASE}/${FULL}/portal${path}`);
    const rows = await readFieldAnatomy(page);
    report[`anatomy|${name}|${width}`] = rows;
    for (const row of rows) {
      say(`  ${name.padEnd(16)} ${String(row.id).padEnd(22)} label→input=${row.labelToInput} input→helper=${row.inputToHelper} field→field=${row.fieldToField}`);
    }
    for (const row of rows) {
      if (row.labelToInput !== null) {
        check(row.labelToInput === 5, `rule 39 @${width} ${name}/${row.id} label→input = 5`, String(row.labelToInput));
      }
      if (row.inputToHelper !== null) {
        check(row.inputToHelper === 6, `rule 39 @${width} ${name}/${row.id} input→helper = 6`, String(row.inputToHelper));
      }
      // Two fields side by side at 1280 read negative, which is `TwoUp`
      // working rather than a fault — only the stacked reading is the anchor.
      if (row.fieldToField !== null && row.fieldToField >= 0) {
        check(row.fieldToField === 20, `rule 39 @${width} ${name}/${row.id} field→field = 20`, String(row.fieldToField));
      }
    }
  }

  // ── 5 · /enrol's commit, with nothing typed ───────────────────────────
  await openRoute(page, `${BASE}/${FULL}/portal/enrol`);
  const commit = await page.evaluate(() => {
    const button = [...document.querySelectorAll("button")].find((b) =>
      /continue|continuar/i.test(b.textContent || ""),
    );
    return button
      ? { found: true, disabled: button.disabled, reason: button.getAttribute("title") }
      : { found: false };
  });
  say(`\n  /enrol commit with three empty required fields: ${JSON.stringify(commit)}`);
  check(commit.found === true, `@${width} · /enrol has a Continue`, JSON.stringify(commit));
  check(commit.disabled === true, `@${width} · /enrol Continue is refused while empty`, JSON.stringify(commit));
  check(
    typeof commit.reason === "string" && commit.reason.length > 0,
    `@${width} · /enrol says WHY it is refused`,
    JSON.stringify(commit.reason),
  );

  // ── 6 · the word a North American reads ───────────────────────────────
  say(`\n── DEF-CWP-4855 · the postcode word @${width}`);
  for (const [name, path] of [["enrol", "/enrol"], ["track", "/track"]]) {
    await openRoute(page, `${BASE}/${FULL}/portal${path}`);
    const words = await page.evaluate(() =>
      document.body.innerText.replace(/\s+/g, " "),
    );
    const hasPostcode = /postcode/i.test(words);
    const hasZip = /zip/i.test(words);
    say(`  ${name.padEnd(16)} "Postcode" present=${hasPostcode}  "ZIP" present=${hasZip}`);
    check(!hasPostcode, `@${width} · ${name} does not say "Postcode"`);
    check(hasZip, `@${width} · ${name} says "ZIP code"`);
  }

  await page.close();
}

writeFileSync(join(OUT, "report.json"), JSON.stringify(report, null, 2));
await browser.close();

say(`\n════════ ${failures.length === 0 ? "ALL CHECKS PASS" : `${failures.length} CHECK(S) FAILED`} ════════`);
for (const one of failures) say(`  · ${one}`);
say(`screenshots + report.json under ${OUT}`);
process.exit(failures.length === 0 ? 0 : 1);
