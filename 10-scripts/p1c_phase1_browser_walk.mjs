// ── Trace ──────────────────────────────────────────────
// Change:  payments blueprint phase 1 — `P1.5` (the Imports tab and its ONE
//          door), `P1.8` (the eligible count, the per-row confirm, the
//          consequence box), and a REGRESSION walk of the four phase-1 screens
//          nobody had clicked: `P1.6` Move and Reapply, `P1.7`'s bulk bar,
//          `P1.18`'s refused write mode and `P1.19`'s Scan card.
// Rules:   CLAUDE.md hard-won law 6 — *"Diff the running app against
//          `05-prototype/`. No gate looks at rendered output. Nine defects were
//          found this way and by nothing else."*
// Screens: 4·1 Batches · 4·3a Import · 2·1 Payments · 2·1b Bulk · 2·3f Move ·
//          2·3g Reapply
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS WALK EXISTS BECAUSE LANE P1-B SAID SO ITSELF**, on 2026-09-22:
// *"no gate in this repo reads rendered output, and I did not click these
// screens in a browser. Everything above is tests, types and gates."* Five
// phase-1 rows had shipped by then and not one of them had been looked at.
//
// The morning's browser walk on phase 0 found two things every other check
// passed over — money clipped in half inside the ageing cards, and a screen-id
// badge reading `PAY-summary` while the clerk was on Settlements. Neither was
// visible to `tsc`, to 386 cases or to the Route B compiler check.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   10-scripts/proof-db.sh clone p1c
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p1c \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8391 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8392 \
//      API_PROXY_TARGET=http://127.0.0.1:8391 node server.mjs)
//   BASE=http://127.0.0.1:8392 node 10-scripts/p1c_phase1_browser_walk.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8392";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots-p1c";

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

mkdirSync(SHOTS, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);

let passes = 0;
const failures = [];
const ok = (what, detail = "") => {
  passes += 1;
  console.log(`    ✓ ${what}${detail ? `  — ${detail}` : ""}`);
};
const note = (what) => console.log(`    · ${what}`);
const bad = (what, detail = "") => {
  failures.push(`${what}${detail ? ` — ${detail}` : ""}`);
  console.log(`    ● ${what}${detail ? `  — ${detail}` : ""}`);
};

/**
 * ⚠ **A CLIPPED FIGURE IS THE DEFECT PHASE 0'S WALK FOUND, AND IT IS INVISIBLE
 * TO `textContent`.** `$7,938.35 POSTING DATE` read perfectly as a string while
 * the money was cut in half on screen under `white-space: nowrap`. So overflow
 * is measured, not read: an element whose `scrollWidth` exceeds its
 * `clientWidth` is showing a person less than it is telling a test.
 */
const clipped = (selector) =>
  page.$$eval(selector, (nodes) =>
    nodes
      .filter((n) => n.scrollWidth > n.clientWidth + 1)
      .map((n) => `${(n.textContent ?? "").trim().slice(0, 40)} (${n.scrollWidth}>${n.clientWidth})`),
  );

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ══════════════════════════════════════════════════════════════════════════
  // `P1.5` — 4·1 BATCHES: THE TAB, THE LIST AND THE ONE DOOR
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P1.5 — the Imports tab (4·1)");
  await page.goto(`${BASE}/${TENANT}/payments/imports`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/01-imports-tab.png`, fullPage: false });

  const body1 = (await page.textContent("body")) ?? "";
  if (body1.includes("Imports are not built yet")) {
    bad("the hold is still on screen", "the panel P1.5 replaces is still drawn");
  } else {
    ok("the holding panel is gone");
  }
  if (body1.includes("W0 scaffold")) bad("the tab landed on the catch-all scaffold");

  // The head, as 4·1 draws it: `PAYMENTS › IMPORTS` over **Imports**.
  const h1 = (await page.textContent("h1")) ?? "";
  if (h1.trim() === "Imports") ok("the head reads Imports", h1.trim());
  else bad("the head is not the drawing's", h1.trim());

  // ⚠ **THE DOOR IS CLICKED, NOT READ.** A route constant is not a door
  // (law 1), and `DEF-CWP-3925` is what a door nobody pressed costs.
  const doors = await page.$$eval("a[href]", (nodes) =>
    nodes.map((n) => n.getAttribute("href")).filter((h) => h && h.includes("/imports/new")),
  );
  if (doors.length === 1) ok("exactly ONE door onto the runner", doors[0]);
  else bad(`the drawing says 1 door; this screen has ${doors.length}`, doors.join(" · "));

  // The empty state or the list — either is honest, and a clerk sees one of them.
  const rows1 = await page.$$eval("tbody tr", (n) => n.length);
  note(`run rows on screen: ${rows1}`);
  if (rows1 === 0 && !body1.includes("No payment imports yet")) {
    bad("no rows and no empty state", "a list that says nothing is a broken load");
  } else {
    ok(rows1 === 0 ? "the empty state states what is missing" : `${rows1} run(s) listed`);
  }

  // B14 rule 31 — nothing uuid-shaped is a VISIBLE value anywhere on this list.
  const uuidOnScreen = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.test(body1);
  if (uuidOnScreen) bad("a database id is visible on the Imports tab (B14 rule 31)");
  else ok("no database id is visible");

  const clip1 = await clipped("td, .kpi-value, [data-selection-eligibility]");
  if (clip1.length > 0) bad("something is CLIPPED on the Imports tab", clip1.join(" | "));
  else ok("nothing on the Imports tab is cut off at 1440");

  // ══════════════════════════════════════════════════════════════════════════
  // `P1.5` + `P1.17`/`P1.18`/`P1.19` — 4·3a, THROUGH THE DOOR
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P1.5 → 4·3a — the runner, reached by pressing the door");
  await page.click(`a[href="/${TENANT}/payments/imports/new"]`);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/02-runner-extract.png`, fullPage: false });
  const landed = new URL(page.url()).pathname;
  if (landed === `/${TENANT}/payments/imports/new`) ok("the door opens the runner", landed);
  else bad("the door led somewhere else", landed);

  const body2 = (await page.textContent("body")) ?? "";
  if (body2.includes("W0 scaffold") || body2.includes("not built yet")) {
    bad("the runner is not what opened", body2.slice(0, 120));
  } else {
    ok("stage 1 Extract is on screen");
  }

  // `P1.19` — the FIFTH source card, drawn and refused with its reason.
  const cards = await page.$$eval("[data-workflow-source]", (nodes) =>
    nodes.map((n) => n.getAttribute("data-workflow-source")),
  );
  note(`source cards: ${cards.join(" · ")}`);
  if (cards.includes("scan")) ok("Scan paper is drawn as a source card (P1.19)");
  else bad("the Scan paper card is not on the screen", cards.join(" · "));

  // `P1.18` — BOTH write modes drawn, one refused WITH its reason as TEXT
  // (never a `title` tooltip: unreachable by keyboard, invisible on touch).
  const modes = await page.$$eval("[data-write-mode]", (nodes) =>
    nodes.map((n) => `${n.getAttribute("data-write-mode")}:${n.getAttribute("data-refused")}`),
  );
  note(`write modes: ${modes.join(" · ")}`);
  if (modes.includes("upsert:true") && modes.includes("insert:false")) {
    ok("Insert & update is drawn, present and REFUSED (P1.18)");
  } else {
    bad("the write-mode control is not as P1.18 draws it", modes.join(" · "));
  }
  const refusalText = (await page.textContent('[data-workflow="write-mode-refused"]')) ?? "";
  if (refusalText.trim().length > 0) ok("the refusal states its reason in TEXT", refusalText.trim());
  else bad("the refused write mode gives no reason a clerk can read");

  const clip2 = await clipped("[data-workflow-source], [data-write-mode]");
  if (clip2.length > 0) bad("something is CLIPPED on stage 1", clip2.join(" | "));
  else ok("nothing on stage 1 is cut off at 1440");

  // ══════════════════════════════════════════════════════════════════════════
  // `P1.7` + `P1.8` — 2·1b, THE BULK BAR
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P1.7/P1.8 — the selection toolbar (2·1b)");
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);
  const tickCount = await page.$$eval('tbody input[type="checkbox"]', (n) => n.length);
  note(`rows with a tick: ${tickCount}`);
  if (tickCount === 0) {
    bad("no payment rows to tick", "the bar cannot be walked on an empty list");
  } else {
    // ⚠ **RE-QUERIED EVERY TIME, NEVER HELD.** Ticking a row re-renders the
    // table, so a handle taken before the first click is detached by the
    // second — `elementHandle.click: Element is not attached to the DOM`. The
    // first draft of this walk held three handles and stopped here.
    for (let index = 0; index < Math.min(3, tickCount); index += 1) {
      await page.click(`tbody tr:nth-child(${index + 1}) input[type="checkbox"]`);
      await page.waitForTimeout(600);
    }
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${SHOTS}/03-bulk-bar.png`, fullPage: false });

    const bar = await page.$("[data-selection-toolbar]");
    if (bar === null) bad("the kit's selection toolbar is not the bar on screen");
    else ok("the bar is the kit's SelectionToolbar (P0.10's piece, P1.8's caller)");

    const barText = bar === null ? "" : ((await bar.textContent()) ?? "");
    note(`bar: ${barText.replace(/\s+/g, " ").trim()}`);

    // `P1.7` — the two dead controls are OFF the bar, not greyed.
    if (/Reapply|Send receipts/i.test(barText)) {
      bad("a control P1.7 removed is back on the bar", barText.slice(0, 120));
    } else {
      ok("Reapply and Send receipts are off the bar entirely (P1.7)");
    }

    // The drawing's bar: Reverse (danger) · Refund · Clear. Nothing else.
    const barButtons = bar === null
      ? []
      : await bar.$$eval("button", (nodes) => nodes.map((n) => (n.textContent ?? "").trim()));
    note(`bar controls: ${barButtons.join(" · ")}`);
    if (barButtons.length === 3) ok("three controls, which is what 2·1b draws");
    else bad(`the bar has ${barButtons.length} controls`, barButtons.join(" · "));

    // `P1.8` — the count in the button.
    if (barButtons.some((label) => /^Reverse \d+$/.test(label))) {
      ok("the Reverse button carries a COUNT", barButtons.find((l) => l.startsWith("Reverse")));
    } else {
      bad("the Reverse button does not carry its eligible count", barButtons.join(" · "));
    }

    const clip3 = await clipped("[data-selection-toolbar] *");
    if (clip3.length > 0) bad("something is CLIPPED on the bulk bar", clip3.join(" | "));
    else ok("nothing on the bulk bar is cut off at 1440");

    // `P1.8` — the per-row confirm.
    const reverseButton = await page.$('[data-selection-toolbar] button:has-text("Reverse")');
    if (reverseButton === null || (await reverseButton.isDisabled())) {
      note("Reverse is disabled on this selection — the confirm cannot be opened here");
    } else {
      await reverseButton.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: `${SHOTS}/04-reverse-confirm.png`, fullPage: false });
      const preview = await page.$("[data-selection-preview]");
      if (preview === null) bad("the confirm draws no per-row table (P1.8 ⑤)");
      else {
        const previewRows = await page.$$eval("[data-preview-row]", (n) => n.length);
        ok(`the confirm lists ${previewRows} row(s), one per ticked payment`);
      }
      const consequence = await page.$('[data-consequence="bulk-reverse"]');
      if (consequence === null) {
        note("no consequence box — correct only when nothing is eligible");
      } else {
        ok("the consequence box is drawn", ((await consequence.textContent()) ?? "").trim());
      }
      const clip4 = await clipped("[data-selection-preview] td, [data-consequence] *");
      if (clip4.length > 0) bad("something is CLIPPED in the confirm", clip4.join(" | "));
      else ok("nothing in the confirm is cut off");
      await page.keyboard.press("Escape");
      await page.waitForTimeout(800);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // `P1.6` — 2·3f MOVE AND 2·3g REAPPLY, ON THE ROW OVERFLOW
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P1.6 — Move and Reapply on the row overflow (2·3f, 2·3g)");
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);
  // ⚠ **THE FIRST RUN OF THIS WALK LOOKED FOR `aria-haspopup` AND A `…` GLYPH,
  // FOUND NEITHER, AND WAS RIGHT TO FAIL** — there was no overflow at all, and
  // all four row actions were drawn side by side with two of them past the
  // right edge of a 1440 window (`DEF-PAY-6214`, fixed in this same commit).
  // The kit's overflow is a `<details data-row-more>` with a `<summary>`.
  const rowActionLabels = await page.$$eval("tbody tr:nth-child(1) td:last-child button", (nodes) =>
    nodes.map((n) => n.getAttribute("aria-label")).filter((label) => label !== null),
  );
  note(`row actions drawn: ${rowActionLabels.join(" · ")}`);
  if (rowActionLabels.length <= 2) {
    ok("at most two controls on the row itself (B14 rule 15)");
  } else {
    bad(`${rowActionLabels.length} controls on the row`, rowActionLabels.join(" · "));
  }

  const overflow = await page.$("tbody tr:nth-child(1) [data-row-more] summary");
  if (overflow === null) {
    bad("no row overflow control on the payments list", "2·3f/2·3g's only door");
  } else {
    await overflow.click();
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${SHOTS}/05-row-overflow.png`, fullPage: false });
    const menu = await page.$$eval("tbody tr:nth-child(1) [data-row-more] button", (nodes) =>
      nodes.map((n) => ({
        label: (n.textContent ?? "").trim(),
        right: Math.round(n.getBoundingClientRect().right),
      })),
    );
    note(`overflow: ${menu.map((m) => `${m.label}@${m.right}`).join(" · ")}`);
    for (const word of ["Move", "Reapply"]) {
      const entry = menu.find((m) => m.label.includes(word));
      if (entry === undefined) bad(`${word} is not on the row overflow`, "the drawing says 2 doors");
      else if (entry.right > 1440) bad(`${word} opens past the right edge`, `${entry.right}px`);
      else ok(`${word} is offered on the row overflow`, `ends at ${entry.right}px`);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // THE NEIGHBOURS — a regression walk, because a kit change reaches them
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  regression — the three lists that already drew these pieces");
  for (const [what, path] of [
    ["Debtors (7·1, the kit toolbar's other caller)", `/${TENANT}/payments/outstandings`],
    ["Accounts → Imports (S81, the extracted list's other caller)", `/${TENANT}/accounts?tab=imports`],
    ["Premises → Imports (PRM-04, deliberately NOT migrated)", `/${TENANT}/premises?tab=imports`],
  ]) {
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    const text = (await page.textContent("body")) ?? "";
    if (text.includes("W0 scaffold") || text.includes("Something went wrong")) {
      bad(`${what} is broken`, path);
    } else {
      ok(`${what} still renders`);
    }
    await page.screenshot({
      path: `${SHOTS}/06-${path.replace(/[^a-z]/gi, "-").slice(-28)}.png`,
      fullPage: false,
    });
  }
} catch (error) {
  bad("the walk stopped", String(error).slice(0, 300));
} finally {
  await browser.close();
}

console.log(`\n  ${passes} passed · ${failures.length} failed`);
for (const failure of failures) console.log(`  ● ${failure}`);
console.log(`  shots: ${SHOTS}`);
process.exit(failures.length === 0 ? 0 : 1);
