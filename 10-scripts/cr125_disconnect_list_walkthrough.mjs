// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — the disconnect LIST, built to page 142 of the
//           Accounts Menu Blueprint. PO ruling 2026-09-20: *"drwaing and
//           screens hosuld match"*.
// Rules:    hard-won law 6 (**diff the running app against the drawing — no
//           gate in this repo reads rendered output, and nine defects were
//           found this way and by nothing else**) · B14 rule 42 (the drawing is
//           an IMAGE) · rule 33 (the caps) · rule 15 (a row action is an icon)
// ───────────────────────────────────────────────────────
//
// **WHY A BROWSER AND NOT THE SUITE.**
//
// `DisconnectsListDrawing.dom.test.tsx` renders this tab in jsdom against a
// fixture a lane typed. It cannot tell you that the SERVER sends what the
// fixture claims, that the strip lays out in the drawn order at a real width,
// or that the toolbar's controls fit on ONE row — which is the measurement B14
// rule 12 actually turns on and the one `G43` says out loud it cannot make
// (*"a jsdom render cannot see a wrapped row"*).
//
// ⚠ **CHECK THE PORT IS YOURS BEFORE YOU BELIEVE A WORD OF THE OUTPUT.** A
// sibling lane serving the same port once made a walkthrough read THEIR tree
// and THEIR database, and report a finding about a screen that was working.
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8479";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr125list";
mkdirSync(OUT, { recursive: true });

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

const ABSENCE = { code: "delivery_adapter_absent", br_ref: "BR-NOT-005", detail: "no adapter" };
const NO_SCHEDULER = { code: "no_scheduler", br_ref: "BR-CUS-039", detail: "nothing advances the ladder", advances_on_a_schedule: false };
/** p142's own rows. ⚠ Every FIGURE here is an ILLUSTRATION (B14 rule 37) — what
 *  this fixture pins is the SHAPE of a row, never `$2,410.00` as a requirement. */
function r(caseNo, acct, customer, address, owed, tierCode, tierLabel, cutDate, noticeOn, stored, held) {
  return {
    account_id: `acc-${acct}`, case_no: caseNo, case_no_unavailable: null,
    account_no: acct, customer, address, unit_id: `u-${acct}`,
    owed: { stored: `${owed}00`, display: owed, currency: "USD", source: "ledger", unavailable: null },
    tier: { chips: tierCode ? [{ code: tierCode, label: tierLabel, tone: "ink" }] : [],
            ambiguous: false, unavailable: tierCode ? [] : [{ code: "no_tier_reached", br_ref: "BR-CUS-039", detail: "none" }] },
    cut_date: cutDate, cut_date_is_this_week: false,
    last_notice: { issued_on: noticeOn, tier: tierCode, delivery_state: null, unavailable: ABSENCE },
    state: { stored, held_by: held, one_cell_is_unresolved: false, unavailable: null },
    ladder: { runs: true, halt_code: null, detail: "runs", sequence: "service", scheduler: NO_SCHEDULER },
    protections: [], case: null, subject: null, chase_subject_unresolved: null,
  };
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
// 1440 is the staff app's DESIGN TARGET (the skill's own table): the laptop
// most clerks have, and the width B14's toolbar measurement uses.
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
const check = (ok, what) => {
  say(`${ok ? "  ok  " : "  FAIL"} ${what}`);
  if (!ok) failures += 1;
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL, "on", TENANT, "\n");

// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE DATA PATH MAY BE DOWN ON THE BRANCH, AND THIS SAYS SO RATHER THAN
//   QUIETLY PAPERING OVER IT
// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-6039`: `customers` has TWO migration leaves — `0061` was written
// against `0059` with its own comment *"Re-point to 0060_* when that lane
// lands"*, `0060` landed, and the re-point did not. `manage.py migrate` refuses
// the whole graph, so `disconnect_cases.stopped_note` does not exist and
// `GET /disconnects` answers **500** on any host provisioned from this branch.
//
// **That is a finding, not a reason to skip the walk.** So: try the live read
// first; if it fails, serve p142's own three rows through a route intercept and
// **print a loud line saying the data path was NOT walked**. Reporting a
// fixture walk as a live one is exactly the dishonesty hard-won law 7 is about.
let liveData = true;
const FIXTURE = {
  rows: [
    r("DSC-26-0003", "A-11812", "Bramble Bakery", "142 Bakers Row · Suite 1", "2410.00",
      "tier_2_10_day", "TIER 2 · 10-DAY", "2026-05-14", "2026-04-24", "notice_sent", []),
    r("DSC-26-0002", "A-11602", "Ncube, T.", "1408 Elm · Unit E", "512.80",
      "tier_2_10_day", "TIER 2 · 10-DAY", "2026-05-21", "2026-05-01", "notice_sent", []),
    r("DSC-26-0001", "A-11333", "Halvorsen, P.", "88 Quarry Lane", "318.20",
      null, null, null, "2026-04-02", null, ["medical_certificate"]),
  ],
  kpis: {
    at_notice: 1, due_to_cut_this_week: 1, on_hold_protected: 1,
    cut_awaiting_payment: 0,
    cut_awaiting_payment_unavailable: { code: "cut_accrual_caption_superseded", br_ref: "BR-CUS-103", detail: "superseded" },
    reconnections_due: 0, as_of: "2026-09-20",
  },
  page: 1, per: 50, total: 3, pages: 1,
  columns: ["reference","account","customer","address","owed","tier","cut_date","last_notice","state"],
  segment: "all",
  segments: [{ code: "all", label: "All", supported: true, unavailable: null }],
  filters: ["state"],
  states: [{ code: "notice_sent" }, { code: "scheduled" }, { code: "on_hold" }, { code: "cut" }, { code: "reconnecting" }],
  chips: [],
  open_case_count: 3,
  search: { hint: "Case #, customer, account #, address, or meter #…",
            legs: ["case_no","customer","account_no","address","meter_no"] },
  delivery: ABSENCE, scheduler: NO_SCHEDULER, as_of: "2026-09-20",
};

const probe = await page.evaluate(
  async (t) => (await fetch(`/api/${t}/disconnects?per=1`)).status,
  TENANT,
);
if (probe !== 200) {
  liveData = false;
  say(`\n  ⚠ GET /disconnects answered ${probe} — DEF-CUS-6039. Serving p142's rows`);
  say("  ⚠ through a route intercept. THE DATA PATH IS NOT WALKED BY THIS RUN.\n");
  await page.route(`**/api/${TENANT}/disconnects*`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FIXTURE) }),
  );
}

await page.goto(`${BASE}/${TENANT}/accounts?tab=disconnects`, { waitUntil: "networkidle" });
await page.waitForSelector("table", { timeout: 20000 });
await page.screenshot({ path: `${OUT}/01-list-1440.png`, fullPage: true });

// ── 1 · THE SUB-LINE ──────────────────────────────────────────────────────
const sub = await page.evaluate(() => {
  const el = document.querySelector(".page-head .sub, [data-rollup], .sub");
  return el ? el.textContent.trim() : document.body.innerText.split("\n").find((l) => l.includes("tabs ·")) ?? "";
});
say("sub-line:", JSON.stringify(sub));
check(/tabs ·/.test(sub), "the head carries the `N tabs · Tab` sub-line");
check(/open case/.test(sub), "…and the drawn THIRD fragment, the open-case count");

// ── 2 · THE FIVE TILES, IN THE DRAWN ORDER ────────────────────────────────
const tiles = await page.evaluate(() =>
  Array.from(document.querySelectorAll(".kpi-grid .kpi")).map((k) => ({
    label: k.querySelector("span.k")?.textContent.trim() ?? "",
    value: k.querySelector("span.v")?.textContent.trim() ?? "",
    detail: k.querySelector(".kpi-detail, .d")?.textContent.trim() ?? "",
    top: Math.round(k.getBoundingClientRect().top),
  })),
);
say("tiles:", JSON.stringify(tiles.map((t) => `${t.label} = ${t.value}`)));
check(
  JSON.stringify(tiles.map((t) => t.label)) ===
    JSON.stringify(["At notice", "Due to cut", "Cut, awaiting reconnect", "On hold", "Reconnections"]),
  "p142's five tiles, in p142's order",
);
check(tiles.every((t) => t.label.split(/\s+/).length <= 3), "B14 rule 33 — every tile label ≤ 3 words");
check(new Set(tiles.map((t) => t.top)).size === 1, "the strip is ONE row at 1440");

// ── 3 · THE TOOLBAR — and whether it FITS, which is the jsdom blind spot ──
const toolbar = await page.evaluate(() => {
  const chips = Array.from(document.querySelectorAll("[data-quick-view]")).map((c) => ({
    label: c.textContent.trim(),
    code: c.getAttribute("data-quick-view"),
    top: Math.round(c.getBoundingClientRect().top),
  }));
  const note = document.querySelector("[data-quick-view-note]")?.textContent.trim() ?? "";
  const row = document.querySelector(".dt-toolbar, [data-table-toolbar], .tt-bar");
  const controls = row
    ? Array.from(row.children).map((c) => Math.round(c.getBoundingClientRect().top))
    : [];
  return { chips, note, controls, rowWidth: row ? Math.round(row.getBoundingClientRect().width) : null };
});
say("chips:", JSON.stringify(toolbar.chips.map((c) => c.label)), "note:", JSON.stringify(toolbar.note));
check(
  JSON.stringify(toolbar.chips.map((c) => c.code)) ===
    JSON.stringify(["scheduled", "notice_sent", "reconnecting"]),
  "the three quick views, in p142's order",
);
check(toolbar.note.replace(/\.$/, "").split(/\s+/).length <= 6, "B14 rule 33 — the note is ≤ 6 words");
check(new Set(toolbar.chips.map((c) => c.top)).size === 1, "the chips are ONE row");
if (toolbar.controls.length > 0) {
  check(new Set(toolbar.controls).size <= 2, `the toolbar does not wrap past 2 rows at 1440 (${new Set(toolbar.controls).size})`);
}

// ── 4 · THE NINE DRAWN COLUMNS ────────────────────────────────────────────
const heads = await page.evaluate(() =>
  Array.from(document.querySelectorAll("table thead th"))
    .map((th) => th.textContent.replace(/[⇅↑↓]/g, "").trim())
    .filter((s) => s !== ""),
);
say("columns:", JSON.stringify(heads));
check(heads[0] === "Case #", "the first column head is `Case #`");
check(!heads.includes("Reference"), "…and `Reference` is gone");
check(!heads.some((h) => /waiting/i.test(h)), "no `Waiting on` column — the FIGURE wins over the caption");

// ── 5 · `↗ Open` — THE HOLD THAT EXPIRED, NOW A LIVE DOOR ────────────────
// This block asserted the ABSENCE of the action until 2026-09-20, because the
// blueprint's own caption said *"no disconnect case page exists"*. It does now
// (`DisconnectRecordPage`, mounted at `/:tenant/disconnects/:ref`), so the hold
// is released and what is checked is that the door OPENS — by address, and by
// the screen that answers at the other end.
// ⚠ **ACROSS THE ROWS, NOT THE FIRST ONE — THE FIRST DRAFT READ ROW 1 AND
// CALLED A CORRECT SCREEN BROKEN.** On live data the newest rows are protected
// accounts with no case raised, so row 1 legitimately carries a DISABLED button
// and no link. Reading one row and generalising is hard-won law 7's *looking at
// the wrong thing*; both halves of the rule are checked here instead.
const cells = await page.evaluate(() =>
  Array.from(document.querySelectorAll("table tbody tr")).map((r) => {
    const tds = r.querySelectorAll("td");
    const last = tds[tds.length - 1];
    const a = last?.querySelector("a[aria-label]");
    const btn = last?.querySelector("button[aria-label]");
    const el = a ?? btn;
    return {
      ref: (tds[0]?.textContent ?? "").trim().slice(0, 24),
      href: a ? a.getAttribute("href") : null,
      disabled: btn ? btn.disabled : null,
      reason: btn ? btn.getAttribute("title") : null,
      name: el ? el.getAttribute("aria-label") : null,
      text: el ? el.textContent.trim() : null,
      glyph: el ? el.querySelector("svg") !== null : false,
    };
  }),
);
const opener = cells.find((c) => c.href !== null) ?? null;
const refused = cells.find((c) => c.href === null) ?? null;
say("rows with a door:", cells.filter((c) => c.href !== null).length, "of", cells.length);
say("row action:", JSON.stringify(opener));
check(cells.length > 0 && cells.every((c) => c.name !== null), "EVERY row carries the control");
check(opener !== null, "a row with a case reference carries a LINK to it");
check(
  (opener?.href ?? "").endsWith(`/disconnects/${(opener?.ref ?? "").trim()}`),
  "…at that row's OWN address, tenant-scoped",
);
// BR-SHL-025 — a row that cannot open says why, and keeps its control.
if (refused !== null) {
  check(refused.disabled === true, "a row with no reference is DISABLED, not missing");
  check((refused.reason ?? "") !== "", "…and carries its reason");
}
// B14 rule 15 — an unlabelled glyph with an accessible name, never the drawn
// labelled button (rule 38 gives CONSTRUCTION to the UI rules).
check(opener?.glyph === true, "…drawn as a glyph");
check(!/Open/.test(opener?.text ?? "x"), "…with no visible label");
check((opener?.name ?? "") !== "", "…and an accessible name a screen reader can say");

// **AND THE DOOR IS WALKED, NOT JUST READ.** A href that looks right and opens
// a "not built yet" page is hard-won law 2's mirror, and the only thing that
// tells them apart is following it.
await page.click("table tbody tr a[aria-label]");  // the first row that HAS a door
await page.waitForTimeout(2500);
const landed = await page.evaluate(() => ({
  path: location.pathname,
  screen: document.querySelector("[data-screen]")?.getAttribute("data-screen") ?? null,
  notBuilt: /not built yet/i.test(document.body.innerText),
}));
say("landed on:", JSON.stringify(landed));
check(
  landed.path.endsWith(`/disconnects/${(opener?.ref ?? "").trim()}`),
  "the link NAVIGATES to that case",
);
// BY SCREEN ID, not only by address: an address that matches a route says the
// link is not a 404; only this says WHICH screen answered.
check((landed.screen ?? "").includes("disconnectRecord"), "…and the record screen answers");
check(!landed.notBuilt, "…and what opens is a screen, not a `not built yet`");
await page.screenshot({ path: `${OUT}/04-case-opened.png`, fullPage: true });
await page.goBack({ waitUntil: "networkidle" });
await page.waitForSelector("table", { timeout: 20000 });

// ── 6 · THE SEARCH PROMPT NAMES WHAT THE QUERY MATCHES ────────────────────
// ⚠ **SCOPED TO THE TABLE FRAME, AND THE FIRST DRAFT WAS NOT.** A bare
// `input[type="search"]` returns the APP SHELL's global box — `aria-label
// "Global search"`, placeholder "Search" — because it comes first in document
// order. The run reported `FAIL the prompt names the case number` over a box
// that is not this screen's, which is hard-won law 7's *looking at the wrong
// thing* found by running the check rather than by reading it.
const prompt = await page.evaluate(() => {
  const frame = document.querySelector(".data-table-frame");
  const box = frame?.querySelector('input[type="search"], .table-toolbar input');
  return { ph: box?.placeholder ?? "", found: box !== null && box !== undefined };
});
say("search prompt:", JSON.stringify(prompt));
check(prompt.found, "the tab's OWN search box is rendered, not just the shell's");
check(/Case #/.test(prompt.ph), "the prompt names the case number");

// ── 7 · A QUICK VIEW IS PRESSED, AND THE SERVER ANSWERS ───────────────────
const before = await page.evaluate(() => document.querySelectorAll("table tbody tr").length);
const requests = [];
page.on("request", (r) => {
  if (r.url().includes("/disconnects")) requests.push(r.url());
});
await page.click('[data-quick-view="notice_sent"]');
await page.waitForTimeout(1500);
say("requests after the press:", JSON.stringify(requests.slice(-1)));
check(
  requests.some((u) => u.includes("f.state=notice_sent")),
  "pressing `At notice` sends `f.state` TO THE SERVER",
);
const pressed = await page.evaluate(
  () => document.querySelector('[data-quick-view="notice_sent"]')?.getAttribute("aria-pressed"),
);
check(pressed === "true", "…and the chip reads as pressed");
await page.screenshot({ path: `${OUT}/02-at-notice.png`, fullPage: true });
say("rows before/after:", before, "→", await page.evaluate(() => document.querySelectorAll("table tbody tr").length));

// ── 8 · THE DRAWING'S TWO NOTES ARE RATIONALE AND MUST NOT BE ON SCREEN ───
const body = await page.evaluate(() => document.body.innerText);
check(!/is not a delay/.test(body), "the `On hold is not a delay` note is NOT rendered (rule 33)");
check(!/answer different questions/.test(body), "the `Tier and Last notice` note is NOT rendered (rule 33)");

// ── 9b · `LAST NOTICE` IS ONE LINE, AS p142 DRAWS IT ──────────────────────
const noticeAt1440 = await page.evaluate(() => {
  const c = document.querySelector("[data-last-notice]");
  const inner = c?.firstElementChild;
  return {
    h: c ? Math.round(c.getBoundingClientRect().height) : 0,
    ws: inner ? getComputedStyle(inner).whiteSpace : null,
    text: (c?.textContent ?? "").replace(/\s+/g, " ").trim(),
  };
});
say("last notice:", JSON.stringify(noticeAt1440));
check(noticeAt1440.ws === "nowrap", "the notice's two facts cannot break apart");
check(noticeAt1440.h <= 26, `LAST NOTICE is ONE line at 1440 (${noticeAt1440.h}px)`);

// ── 9 · NO RAW KEY, NO DATABASE ID ────────────────────────────────────────
check(!/customers\.disconnects\./.test(body), "no raw catalogue key reaches the screen");
check(
  !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.test(body),
  "B14 rule 31 — no database id is visible",
);

// ── 10 · THE LAPTOP MINIMUM — everything must work at 1280 ────────────────
// The skill's own table: the staff app is verified at 1280 AND 1440, and
// nothing below 1280 is supported. This is the width where a toolbar that is
// over budget wraps and strands the export and the ▦ (DEF-1085).
await page.setViewportSize({ width: 1280, height: 1100 });
await page.waitForTimeout(600);
const narrow = await page.evaluate(() => {
  const chips = Array.from(document.querySelectorAll("[data-quick-view]")).map((c) =>
    Math.round(c.getBoundingClientRect().top),
  );
  const notice = document.querySelector("[data-last-notice]");
  return {
    chipRows: new Set(chips).size,
    noticeLines: notice ? Math.round(notice.getBoundingClientRect().height) : 0,
    sideScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  };
});
say("at 1280:", JSON.stringify(narrow));
check(narrow.chipRows === 1, "the quick views are still ONE row at 1280");
check(!narrow.sideScroll, "the page does not scroll sideways at 1280");
// ⚠ **THIS CASE EXISTS BECAUSE ITS ABSENCE LET A FAILED EDIT PASS.** The run
// printed `noticeLines: 63` and asserted nothing about it, so a `nowrap` fix
// that never reached the file — a python heredoc that hit an `AssertionError`
// inside a backgrounded `&&` chain, after which the build succeeded over
// unchanged source — was walked GREEN. A number printed and not checked is not
// a check (hard-won law 7: a check's output must distinguish pass from fail).
check(narrow.noticeLines <= 26, `LAST NOTICE is ONE line at 1280 (${narrow.noticeLines}px)`);
await page.screenshot({ path: `${OUT}/03-list-1280.png`, fullPage: true });

say(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
if (!liveData) {
  say("⚠ THE DATA PATH WAS NOT WALKED — the rows came from a route intercept,");
  say("⚠ because GET /disconnects answers 500 on this branch (DEF-CUS-6039).");
  say("⚠ Layout, order, copy, the toolbar row and the press ARE real; the read is not.");
}
say("screenshots in", OUT);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
