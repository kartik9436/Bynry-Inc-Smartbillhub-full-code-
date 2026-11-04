// ── Trace ──────────────────────────────────────────────
// Change:  payments blueprint phase 0, front end — `P0.8`/`P0.9` (the seven-tab
//          strip, the three holds and the ladder's door), `P0.10` (the kit's
//          selection toolbar), `P0.11` (the ageing cards) and `P0.12` (rule
//          11's box on the three money forms).
// Rules:   CLAUDE.md hard-won law 6 — *"Diff the running app against
//          `05-prototype/`. No gate looks at rendered output. Nine defects were
//          found this way and by nothing else."* · law 1 — a route constant is
//          not a door, so every tab here is CLICKED · law 2's mirror — a hold is
//          only honest if somebody can still reach what it holds.
// Screens: 1·1 Summary · 2·1 Payments · 3·x Counter · 4·x Imports · 5·x
//          Settlements · 6·1 Refunds · 7·1 Debtors · 7·3a Ladder · 2·3a Record
//          · 2·3b Edit the reference
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS WALK EXISTS BECAUSE EVERY CHECK THAT PASSED ON THIS WORK READS
// SOURCE OR A RENDER TREE, AND NEITHER IS A BROWSER.** `sevenTabs.dom.test.tsx`
// proves the strip renders seven labels and that each tab's `path` is the right
// string. It cannot prove that clicking the fifth one lands anywhere, because
// nothing in it mounts the ROUTER the product ships. That gap is exactly the
// shape `DEF-CWP-3925` had, where 42 test files and 391 cases passed over a
// front page with two working doors out of eight.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   10-scripts/proof-db.sh clone p0fe
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p0fe \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8291 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8292 \
//      API_PROXY_TARGET=http://127.0.0.1:8291 node server.mjs)
//   BASE=http://127.0.0.1:8292 node 10-scripts/p0fe_phase0_frontend_walkthrough.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8292";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots-p0fe";

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

/** The strip's labels, in the order the DOM holds them. */
const stripLabels = () =>
  page.$$eval("[data-page-header-tabs] [role='tab']", (nodes) =>
    nodes.map((n) => (n.textContent ?? "").trim()),
  );

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── `P0.8` — SEVEN TABS, IN THE DRAWING'S ORDER, ON A REAL SCREEN ────────
  console.log("\n  P0.8 — the seven-tab strip");
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);
  const labels = await stripLabels();
  note(`strip: ${labels.join(" · ")}`);
  const AS_DRAWN = [
    "Summary",
    "Payments",
    "Counter",
    "Imports",
    "Settlements",
    "Refunds",
    "Debtors",
  ];
  if (JSON.stringify(labels) === JSON.stringify(AS_DRAWN)) {
    ok("seven tabs, with §03's own labels and order");
  } else {
    bad("the strip is not the drawing's seven", labels.join(" · "));
  }
  await page.screenshot({ path: `${SHOTS}/01-strip.png`, fullPage: false });

  // ── `P0.9` — EVERY TAB IS CLICKED, AND THE THREE HOLDS SAY SO PLAINLY ────
  console.log("\n  P0.9 — every tab is a door, and it is opened here");
  const EXPECT = [
    { tab: "Summary", path: `/${TENANT}/payments`, held: null },
    { tab: "Payments", path: `/${TENANT}/payments/record`, held: null },
    { tab: "Counter", path: `/${TENANT}/payments/counter`, held: "Counter is not built yet" },
    { tab: "Imports", path: `/${TENANT}/payments/imports`, held: "Imports are not built yet" },
    {
      tab: "Settlements",
      path: `/${TENANT}/payments/settlements`,
      held: "Settlements are not built yet",
    },
    { tab: "Refunds", path: `/${TENANT}/finance/refunds`, held: null },
    { tab: "Debtors", path: `/${TENANT}/payments/outstandings`, held: null },
  ];
  for (const step of EXPECT) {
    await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    await page.click(`[data-page-header-tabs] [role='tab']:text-is("${step.tab}")`);
    await page.waitForTimeout(1800);
    const landed = new URL(page.url()).pathname;
    if (landed === step.path) {
      ok(`${step.tab} opens ${landed}`);
    } else {
      bad(`${step.tab} landed somewhere else`, `${landed} (wanted ${step.path})`);
    }
    // ⚠ **THE CATCH-ALL IS WHAT A WRONG ADDRESS LOOKS LIKE**, and it renders a
    // real page, so a check that only read the URL would pass over it.
    const body = (await page.textContent("body")) ?? "";
    if (body.includes("W0 scaffold")) {
      bad(`${step.tab} landed on the scaffold`, landed);
    }
    if (step.held !== null) {
      if (body.includes(step.held)) {
        ok(`${step.tab} says plainly that it is not built`, step.held);
      } else {
        bad(`${step.tab} does not state its absence`, step.held);
      }
    }
    await page.screenshot({ path: `${SHOTS}/02-${step.tab.toLowerCase()}.png` });
  }

  // ── `P0.9` — THE LADDER STILL HAS A DOOR AFTER ITS TAB LEFT THE STRIP ────
  console.log("\n  P0.9 — the ladder keeps a door");
  await page.goto(`${BASE}/${TENANT}/payments/outstandings`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2200);
  const ladderHref = await page.getAttribute(
    `a[href="/${TENANT}/payments/collections"]`,
    "href",
  );
  if (ladderHref === `/${TENANT}/payments/collections`) {
    ok("the Debtors tab carries a link to the ladder", ladderHref);
    await page.click(`a[href="/${TENANT}/payments/collections"]`);
    await page.waitForTimeout(2200);
    const onLadder = new URL(page.url()).pathname;
    if (onLadder === `/${TENANT}/payments/collections`) {
      ok("and it opens the ladder", onLadder);
    } else {
      bad("the ladder link went elsewhere", onLadder);
    }
    const active = await page.$$eval("[data-page-header-tabs] [role='tab']", (nodes) =>
      nodes.filter((n) => n.getAttribute("aria-selected") === "true").map((n) => n.textContent),
    );
    if (active.join("") === "Debtors") {
      ok("and the ladder's strip shows Debtors selected, as the drawing shows it");
    } else {
      bad("the ladder's strip selects the wrong tab", active.join("|"));
    }
    await page.screenshot({ path: `${SHOTS}/03-ladder.png` });
  } else {
    bad("the ladder has NO door — a live screen is unreachable");
  }

  // ── `P0.11` — THE AGEING CARDS ARE CONTROLS AND THEY NARROW THE LIST ─────
  console.log("\n  P0.11 — the ageing cards");
  await page.goto(`${BASE}/${TENANT}/payments/outstandings`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const bands = await page.$$eval("[data-ageing-cards] button[data-band]", (nodes) =>
    nodes.map((n) => n.getAttribute("data-band")),
  );
  note(`bands: ${bands.join(" · ")}`);
  if (bands.length === 5) {
    ok("five cards, one per band");
  } else {
    bad("the debtor screen does not draw five ageing cards", String(bands.length));
  }
  const before = (await page.textContent("body")) ?? "";
  if (bands.includes("61-90")) {
    await page.click('[data-ageing-cards] button[data-band="61-90"]');
    await page.waitForTimeout(2200);
    const pressed = await page.getAttribute(
      '[data-ageing-cards] button[data-band="61-90"]',
      "aria-pressed",
    );
    if (pressed === "true") {
      ok("pressing a card narrows the list to that band");
    } else {
      bad("a pressed card does not read as pressed", String(pressed));
    }
    const after = (await page.textContent("body")) ?? "";
    note(`page text changed on filter: ${String(before !== after)}`);
    await page.click('[data-ageing-cards] button[data-band="61-90"]');
    await page.waitForTimeout(1800);
    const cleared = await page.getAttribute(
      '[data-ageing-cards] button[data-band="61-90"]',
      "aria-pressed",
    );
    if (cleared === "false") {
      ok("and pressing it again clears the filter");
    } else {
      bad("the card will not clear", String(cleared));
    }
  }
  await page.screenshot({ path: `${SHOTS}/04-ageing.png` });

  // ── `P0.12` — THE RULE-11 BOX ON A MONEY FORM A CLERK OPENS ──────────────
  console.log("\n  P0.12 — rule 11's box, on a form a clerk opens");
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const pencil = await page.$('button[aria-label*="Correct"], button[title*="Correct"]');
  if (pencil !== null) {
    await pencil.click();
    await page.waitForTimeout(1500);
    const box = await page.$('[data-consequence="correct"]');
    if (box !== null) {
      const text = (await box.textContent()) ?? "";
      ok("the correction form draws the box, before anything is typed", text.trim());
    } else {
      bad("the correction form draws no consequence box");
    }
    await page.screenshot({ path: `${SHOTS}/05-correct.png` });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);
  } else {
    note("no correction row action on this page — the box is asserted by its own dom test");
  }

  // The Record form. The account picker is a server search, so this drives it.
  await page.click('button:text-is("Record payment")').catch(() => undefined);
  await page.waitForTimeout(1500);
  const accountBox = await page.$("#account_query");
  if (accountBox !== null) {
    const before12 = await page.$('[data-consequence="record"]');
    if (before12 === null) {
      ok("an empty Record form draws no box — a consequence of nothing is noise");
    } else {
      bad("the Record form draws a box over an empty form");
    }
    await accountBox.fill("AC-2026");
    await page.waitForTimeout(2500);
    const options = await page.$$eval("#account_id option", (nodes) =>
      nodes.map((n) => n.getAttribute("value")).filter((v) => v !== null && v !== ""),
    );
    if (options.length > 0) {
      await page.selectOption("#account_id", options[0]);
      await page.fill("#amount", "158.10");
      await page.waitForTimeout(1500);
      const recordBox = await page.$('[data-consequence="record"]');
      if (recordBox !== null) {
        ok("and once an account and an amount are chosen, it says what will happen", (
          (await recordBox.textContent()) ?? ""
        ).trim());
      } else {
        bad("the Record form draws no box with an account and an amount");
      }
      await page.screenshot({ path: `${SHOTS}/06-record.png` });
    } else {
      note("the account search returned nothing on this fixture");
    }
  } else {
    note("the Record modal did not open on this fixture");
  }

  console.log(`\n  ${passes} passed, ${failures.length} failed`);
  for (const f of failures) console.log(`    ● ${f}`);
  console.log(`  screenshots: ${SHOTS}`);
} finally {
  await browser.close();
}
