// ── Trace ────────────────────────────────────────────────────────────────────
// Ask:      PO, 2026-09-20, verbatim: *"Something has to read cut dates daily
//           and surface what's due… A case due last week stops looking
//           identical to one due next month. The clerk stops being the
//           scheduler."* Screen: **the register — a due today view; plus a
//           scheduled job.**
// Walks:    `/{t}/accounts?tab=disconnects` (the register, Accounts blueprint
//           p140) at 1440 and 1280
// Rules:    B14 rule 33 (a LABEL ≤ 3 words; a FACT ≤ 6; RATIONALE zero) · rule
//           31 (no database id on screen) · rule 21 (Tailwind utilities) ·
//           BR-SHL-010 (the served vocabulary is the only vocabulary) ·
//           NFR-3 (the page and the total are the SERVER's) ·
//           CLAUDE.md hard-won laws 2 and 6
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS A PERSON WITH A BROWSER, WHICH IS THE ONLY CHECK IN THIS REPO
// THAT READS RENDERED OUTPUT** (hard-won law 6). Every assertion below is one a
// unit test cannot make: it drives the SHIPPED bundle through a real router, a
// real query client, a real API and a real PostgreSQL with RLS on.
//
// ⛔ **IT IS READ-ONLY AND IT CANNOT CUT ANYTHING.** No button on this walk
// commits anything: it opens the register, presses filter chips and reads. The
// overdue fixture it needs is made by the wizard — see the header of
// `po20260921_disconnect_web_walk.mjs`, `DWALK_SCHEDULE=1 DWALK_CUT_ON=<a past
// date>` — because a case created by hand is not a case the product made.
//
// ⚠ **`ROOT` IS DERIVED FROM THIS FILE'S OWN PATH AND IS PRINTED**
// (`DEF-CUS-6028`): a walk that hard-codes a checkout drives YOUR bundle and
// reads somebody else's Django, and nothing says so.
//
//   node 10-scripts/po20260921_cut_date_watch_walkthrough.mjs
//   CDW_BASE=http://127.0.0.1:9197 CDW_CASE=DSC-26-0001 node …
//
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.CDW_BASE || "http://127.0.0.1:9197";
const T = process.env.CDW_TENANT || "brazosbend";
const EMAIL = process.env.CDW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.CDW_PASSWORD || "S3cure!passw0rd";
/** The case that must be SCHEDULED with a date in the PAST. */
const OVERDUE_CASE = process.env.CDW_CASE || "DSC-26-0001";
/** The case that must be CUT — its date must read as an ordinary date. */
const CUT_CASE = process.env.CDW_CUT_CASE || "DSC-26-0002";
const CHROME = process.env.CDW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.CDW_SHOTS || "/tmp/claude-0/dbld3-shots";

console.log(`tree:   ${ROOT}`);
console.log(`app:    ${BASE}/${T}`);
console.log(`overdue case: ${OVERDUE_CASE}   cut case: ${CUT_CASE}\n`);

let pass = 0;
const failures = [];
const pageErrors = [];
const httpErrors = [];
function ok(what) { pass += 1; console.log(`  ✓ ${what}`); }
function bad(what, saw) { failures.push(`${what} — saw: ${saw}`); console.log(`  ✗ ${what}\n      saw: ${saw}`); }
function is(cond, what, saw) { cond ? ok(what) : bad(what, String(saw)); }

async function signIn(ctx, width) {
  const p = await ctx.newPage({ viewport: { width, height: 1800 } });
  p.setDefaultTimeout(25000);
  p.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
  p.on("response", async (r) => {
    if (r.url().includes("/api/") && r.status() >= 400) {
      httpErrors.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
    }
  });
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}
const bodyText = (p) => p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));

/** One row of the register, by case number, as the DOM has it. */
const rowOf = (p, caseNo) =>
  p.evaluate((wanted) => {
    const tr = [...document.querySelectorAll("tbody tr")].find((row) =>
      row.textContent.includes(wanted),
    );
    if (tr === undefined) return null;
    const marker = tr.querySelector("[data-cut-due-marker]");
    const cell = tr.querySelector("[data-cut-due]");
    return {
      text: tr.innerText.replace(/\s+/g, " ").trim(),
      status: cell === null ? null : cell.getAttribute("data-cut-due"),
      thisWeek: cell === null ? null : cell.getAttribute("data-cut-this-week"),
      marker: marker === null ? null : marker.innerText.replace(/\s+/g, " ").trim(),
      days: tr.querySelector("[data-cut-due-days]")?.getAttribute("data-cut-due-days") ?? null,
    };
  }, caseNo);

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  const page = await signIn(ctx, 1440);

  // ══════════════════════════════════════════════════════════════════════════
  // 1 · THE REGISTER — a date in the past stops looking like a date ahead
  // ══════════════════════════════════════════════════════════════════════════
  console.log("═══ 1 · THE REGISTER · /accounts?tab=disconnects ═══");
  await page.goto(`${BASE}/${T}/accounts?tab=disconnects`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOTS}/cdw1-register.png`, fullPage: true });

  const overdue = await rowOf(page, OVERDUE_CASE);
  is(overdue !== null, `the register draws ${OVERDUE_CASE}`, "row absent");
  is(overdue?.status === "overdue", "…and its cut date reads OVERDUE", overdue?.status);
  is(/overdue/i.test(overdue?.marker ?? ""), "…in words a clerk can read, not a colour alone", overdue?.marker);
  is(/\d+\s*days late/i.test(overdue?.marker ?? ""), "…with how late it is", overdue?.marker);
  // ⚠ **THE FACT THE OLD SCREEN COULD NOT STATE.** `cut_date_is_this_week` is
  // forward-looking, so it is FALSE on a date that has passed — which is why
  // the accent alone could never have shown this row.
  is(overdue?.thisWeek === "false",
     "…and it is NOT `this week`, which is why the accent could not show it",
     overdue?.thisWeek);

  const cut = await rowOf(page, CUT_CASE);
  is(cut !== null, `the register draws ${CUT_CASE}`, "row absent");
  // ⛔ `DEF-CUS-6055`'s general shape: a date that records WHEN something
  // happened must not match a window meaning WHEN IT WILL.
  is(cut?.status === "done", "a case already CUT is not late — its date is history", cut?.status);
  is(cut?.marker === null, "…and it carries no marker at all", cut?.marker);

  // ══════════════════════════════════════════════════════════════════════════
  // 2 · THE DUE NOW VIEW — the door, and the rows behind it
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 2 · THE `Due now` VIEW ═══");
  const dueViews = await page.$$eval("[data-disconnect-due-views] [data-due-view]", (els) =>
    els.map((e) => ({ code: e.getAttribute("data-due-view"), label: e.innerText.trim() })),
  );
  is(dueViews.length === 1, "the register offers a due-now quick view, and ONE", JSON.stringify(dueViews));
  is(dueViews.some((v) => v.code === "due_now"), "…named by the SERVER's code", JSON.stringify(dueViews));
  // ⚠ **THE DRAWN TOOLBAR IS ONE LINE (p140) AND IT MUST STAY ONE LINE.**
  // ⛔ **THIS IS MEASURED AS A SPREAD AND NOT AS A COUNT OF DISTINCT TOPS, AND
  // THE DIFFERENCE IS A FILED DEFECT RATHER THAN A LOOSER CHECK.** The chips
  // are on one line and are NOT on one baseline: `DisconnectStateChips` wraps
  // its row in a column with a six-word note under it, so its chips sit ~11px
  // higher than `All` and `+ Filter ▾`. That misalignment arrived with
  // `CR-125-BRC07` and is visible in a screenshot taken before this lane
  // touched the screen — `DEF-CUS-6085`, filed, not fixed here. A count of
  // distinct tops reports it as a WRAP, which it is not.
  const toolbar = await page.evaluate(() => {
    const chips = [...document.querySelectorAll("button")].filter((el) =>
      /^(Due to cut|At notice|Reconnections|Due now|All|\+ Filter)/.test(el.textContent.trim()),
    );
    const tops = chips.map((el) => el.getBoundingClientRect().top);
    const heights = chips.map((el) => el.getBoundingClientRect().height);
    return { spread: Math.round(Math.max(...tops) - Math.min(...tops)), chip: Math.round(Math.min(...heights)), n: chips.length };
  });
  is(toolbar.n >= 5 && toolbar.spread < toolbar.chip,
     "every toolbar control is on ONE line, as p140 draws it",
     `${toolbar.n} controls, spread ${toolbar.spread}px over a ${toolbar.chip}px chip`);
  // ⛔ `Overdue` IS SERVED AND IS NOT A CHIP -- it lives in the panel, from the
  // same vocabulary, so nothing a clerk could do is lost (BR-SHL-010).
  is(!dueViews.some((v) => v.code === "overdue"),
     "`Overdue` is not a chip — it is in the filter panel",
     JSON.stringify(dueViews));
  await page.click("text=+ Filter");
  await page.waitForTimeout(600);
  const panel = await bodyText(page);
  is(/Overdue/.test(panel), "…and the panel offers it", panel.slice(0, 200));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  // B14 rule 33 — a chip is a LABEL and a label is three words or fewer.
  for (const view of dueViews) {
    is(view.label.split(/\s+/).length <= 3, `\`${view.label}\` is three words or fewer (B14 rule 33)`, view.label);
  }

  await page.click('[data-disconnect-due-views] [data-due-view="due_now"]');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOTS}/cdw2-due-now.png`, fullPage: true });

  const afterUrlRows = await page.$$eval("tbody tr", (rs) => rs.length);
  const stillThere = await rowOf(page, OVERDUE_CASE);
  is(stillThere !== null, "pressing it keeps the overdue case", `${afterUrlRows} rows`);
  const cutGone = await rowOf(page, CUT_CASE);
  is(cutGone === null, "…and drops the one whose supply is already off", cutGone?.text);

  // ⚠ **THE SERVER NARROWED IT, NOT THE BROWSER (`NFR-3`).** The pager's own
  // total is the server's `COUNT(*)`; a filter applied in the browser would
  // leave it at the unfiltered number.
  const pager = await page.evaluate(() => document.body.innerText.match(/1[–-]\d+ of \d+/)?.[0] ?? "");
  is(/of 1$/.test(pager), "the SERVER counted the narrowed list, not the browser", pager);

  // ══════════════════════════════════════════════════════════════════════════
  // 3 · WHAT IS NOT ON THE SCREEN
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 3 · WHAT IS NOT ON THE SCREEN ═══");
  const text = await bodyText(page);
  is(!/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(text),
     "no database id is a visible value (B14 rule 31)",
     (text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}[^ ]*/i) ?? ["none"])[0]);
  // ⛔ A code is not a word. `DEF-CUS-6053` is three filter options that
  // reached a clerk reading `closed_out`, `in_progress_draft` and `parked`.
  is(!/\bdue_now\b|\bcut_due\b|\bno_date\b/.test(text),
     "no server code reaches the clerk",
     (text.match(/\b(due_now|cut_due|no_date)\b/) ?? ["none"])[0]);
  // ⛔ RATIONALE IS ZERO WORDS ON SCREEN (B14 rule 33). Nothing explains WHY
  // the register now watches dates; that belongs in the code and the register.
  is(!/because|in order to|the reason/i.test(text),
     "no rationale is printed on the screen (B14 rule 33)",
     (text.match(/[^.]*\b(because|in order to|the reason)\b[^.]*/i) ?? ["none"])[0]);

  // ══════════════════════════════════════════════════════════════════════════
  // 4 · 1280, THE LAPTOP MINIMUM
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 4 · 1280, the laptop minimum ═══");
  const narrow = await signIn(ctx, 1280);
  await narrow.goto(`${BASE}/${T}/accounts?tab=disconnects`, { waitUntil: "networkidle" });
  await narrow.waitForTimeout(2000);
  await narrow.screenshot({ path: `${SHOTS}/cdw3-1280.png`, fullPage: true });
  const sideways = await narrow.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
  );
  is(!sideways, "the register does not scroll sideways at 1280", `scrollWidth ${await narrow.evaluate(() => document.documentElement.scrollWidth)}`);
  const narrowRow = await rowOf(narrow, OVERDUE_CASE);
  is(narrowRow?.status === "overdue", "…and the overdue marker survives the narrower table", narrowRow?.status);
  await narrow.close();
} finally {
  if (browser !== undefined) await browser.close();
}

console.log(`\n${pass} passed · ${failures.length} failed`);
for (const line of failures) console.log(`FAIL ${line}`);
for (const line of pageErrors) console.log(line);
for (const line of httpErrors) console.log(`HTTP ${line}`);
console.log(`screenshots: ${SHOTS}`);
process.exit(failures.length + pageErrors.length + httpErrors.length === 0 ? 0 : 1);
