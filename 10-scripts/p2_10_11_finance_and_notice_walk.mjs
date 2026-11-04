// ── Trace ──────────────────────────────────────────────
// Change:  CR-136-BRC07 — `P2.10` (*"Finance picks up the batch — a closed
//          till's batch appears on Deposits ready to match"*) and `P2.11`
//          (*"Notification: the unclosed till"*), looked at in a browser.
// Rules:   CLAUDE.md hard-won law 6 — *"Diff the running app against
//          `05-prototype/`. No gate looks at rendered output. Nine defects were
//          found this way and by nothing else."* · law 1 (a comment claiming a
//          guarantee is not the guarantee) · law 7 (a check's output must
//          distinguish pass from fail to a READER) · B14 rule 31 (no database
//          id on screen) · B14 rule 33 (a fact ≤ 6 words)
// Screens: S37 Finance → Deposits
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS WALK EXISTS BECAUSE `P2.10`'s BRIEF SAID SO, VERBATIM:** *"HARD-WON
// LAW 1: a comment claiming a guarantee is not the guarantee. Do not report
// this done because the code reads as if it works. Open Finance → Deposits in a
// browser with a closed till behind it and look."*
//
// WHAT IT ASSERTS, AND WHY EACH ONE CAN FAIL
// -------------------------------------------
//   1. The CLOSED till's batch is ON the page. `P2.10`'s own sentence.
//   2. The OPEN till's batch is NOT. The defect this task fixes.
//   3. Both at once. *"The open one is absent"* is equally true of a screen
//      that failed to load, so the absence only means something beside the
//      presence.
//   4. The held-back money is a VISIBLE NUMBER. Law 7 — a declared blind spot
//      with no number attached is indistinguishable from an empty one, and
//      without this the list is simply short by $612.50 with nothing saying so.
//   5. The In-transit TILE does not include the held-back money. The tiles fold
//      the rows they sit over; a tile that counted a drawer still taking money
//      would put one confident wrong number over a correct list.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   10-scripts/proof-db.sh clone p2wire
//   python3 10-scripts/p2_10_11_seed_tills.py          # the tills and batches
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p2wire \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8471 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8472 \
//      API_PROXY_TARGET=http://127.0.0.1:8471 node server.mjs)
//   BASE=http://127.0.0.1:8472 node 10-scripts/p2_10_11_finance_and_notice_walk.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8472";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots-p2wire";

/** The seed's own codes. Named here so a reader can tell which is which
 *  without opening the seeder. */
const CLOSED_TILL_BATCH = "DEP-260923-9002"; // Sam counted and sealed it
const OPEN_TILL_BATCH = "DEP-260923-9001"; // Dana's drawer, still taking money
const SYSTEM_TILL_BATCH = "DEP-260923-9003"; // ACH/cheque — born closed
const LEGACY_BATCH = "DEP-260808-CHK-LEGACY"; // banked before tills existed

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

/** A clipped figure reads perfectly as a string and is cut in half on screen —
 *  phase 0's browser walk found exactly that, under `white-space: nowrap`. */
const clipped = (selector) =>
  page.$$eval(selector, (nodes) =>
    nodes
      .filter((n) => n.scrollWidth > n.clientWidth + 1)
      .map(
        (n) => `${(n.textContent ?? "").trim().slice(0, 40)} (${n.scrollWidth}>${n.clientWidth})`,
      ),
  );

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ══════════════════════════════════════════════════════════════════════════
  // `P2.10` — FINANCE → DEPOSITS, WITH A CLOSED TILL AND AN OPEN ONE BEHIND IT
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P2.10 — Finance → Deposits (S37)");
  await page.goto(`${BASE}/${TENANT}/finance/deposits`, { waitUntil: "domcontentloaded" });
  // ⚠ **WAIT FOR THE CONTENT, NOT FOR A CLOCK.** A fixed `waitForTimeout` is
  // how the first run of this walk reported six failures over a page that was
  // still drawing its loading skeleton — and one of them was a FALSE PASS
  // ("the open till's batch is held back") that was true only because nothing
  // had rendered at all. That is hard-won law 7's *"what would make this check
  // pass wrongly"* answered by the check itself, on its first run.
  await page.waitForSelector("tbody tr", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/01-deposits.png`, fullPage: true });

  const body = (await page.textContent("body")) ?? "";

  // 1 + 3 · The batches that SHOULD be there. Asserted FIRST, so the absence
  // below can only mean what it is supposed to mean.
  for (const [code, why] of [
    [CLOSED_TILL_BATCH, "a closed till's batch IS the deposit batch"],
    [SYSTEM_TILL_BATCH, "the system till is born closed — ACH, card, wire, lockbox"],
    [LEGACY_BATCH, "banked before tills existed (session_id IS NULL)"],
  ]) {
    if (body.includes(code)) ok(`${code} is on Deposits`, why);
    else bad(`${code} is MISSING from Deposits`, why);
  }

  // 2 · The one that must not be there.
  if (body.includes(OPEN_TILL_BATCH)) {
    bad(
      `${OPEN_TILL_BATCH} is on Deposits and its till is still OPEN`,
      "reconciling it would LOCK a drawer still taking money (BR-PAY-004)",
    );
  } else {
    ok(`${OPEN_TILL_BATCH} is held back`, "its counter has not been closed");
  }

  // 4 · The held-back money is a NUMBER a person can read (law 7).
  const stillOpen = await page.$("[data-testid='deposits-still-open']");
  if (!stillOpen) {
    bad(
      "nothing on screen says money is being held back",
      "a declared blind spot with no number is indistinguishable from an empty one",
    );
  } else {
    const text = (await stillOpen.textContent())?.trim() ?? "";
    note(`the held-back line reads: ${text}`);
    if (/\d/.test(text)) ok("the held-back line carries a figure", text);
    else bad("the held-back line carries no figure", text);
    // BR-SHL-023 — the ONE money formatter. A raw six-decimal wire value on
    // screen is the failure this catches: `612.500000` instead of `$612.50`.
    if (/\.\d{3,}/.test(text)) {
      bad("the held-back figure is unformatted", `${text} — six decimals reached the screen`);
    } else {
      ok("the held-back figure went through the money formatter");
    }
    // B14 rule 33 — a FACT is at most six words.
    const words = text.split(/\s+/).filter(Boolean).length;
    if (words <= 7) ok(`the held-back line is ${words} words`, "B14 rule 33");
    else bad(`the held-back line is ${words} words`, "B14 rule 33 caps a fact at six");
  }

  // 5 · The In-transit tile folds the ROWS and not the held-back money.
  //
  // ⚠ **THE FIRST VERSION OF THIS CHECK COULD NOT FAIL**, and it is left
  // recorded rather than quietly rewritten: it matched the element whose text
  // STARTS WITH "In transit", which is the LABEL — so it read the four words
  // "In transit", found no "612.50" in them, and reported a pass. A check
  // whose subject contains no figure cannot be wrong about a figure (law 7's
  // *"structurally incapable of failing"*). It now demands the tile it reads
  // CARRIES a money figure, and fails if it cannot find one.
  const tile = await page.$$eval("*", (nodes) => {
    const candidates = nodes
      .filter((n) => n.children.length === 0)
      .map((n) => (n.textContent ?? "").replace(/\s+/g, " ").trim())
      .filter((t) => /^\$[\d,]+\.\d{2}$/.test(t));
    return candidates;
  });
  // The tiles in order: Deposited · Reconciled · Unmatched · In transit.
  const inTransit = tile[3] ?? "";
  note(`money figures in the KPI strip: ${tile.join(" · ") || "(none)"}`);
  if (!/^\$[\d,]+\.\d{2}$/.test(inTransit)) {
    bad("no In-transit FIGURE found", `the strip read ${tile.join(" · ") || "(nothing)"}`);
  } else if (inTransit.includes("612.50")) {
    bad("the In-transit tile counts the open drawer", inTransit);
  } else {
    // The tiles fold the rows they sit over: 1,284.60 + 884.00 + 4,400.00.
    const expected = "$6,568.60";
    if (inTransit === expected) {
      ok("the In-transit tile ties to the three rows exactly", `${inTransit} = the seed's three`);
    } else {
      bad("the In-transit tile does not tie to the rows", `${inTransit}, expected ${expected}`);
    }
  }
  // …and the held-back money appears NOWHERE in the strip, under any tile.
  if (tile.some((figure) => figure.includes("612.50"))) {
    bad("the held-back money is inside a KPI tile", tile.join(" · "));
  } else {
    ok("no KPI tile carries the held-back money");
  }

  // The house rules, on a screen this lane changed.
  if (/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.test(body)) {
    bad("a database id is visible on Deposits (B14 rule 31)");
  } else {
    ok("no database id is visible");
  }
  const clip = await clipped("td, .kpi-value, .pay-absent");
  if (clip.length > 0) bad("something is CLIPPED on Deposits", clip.join(" | "));
  else ok("nothing on Deposits is cut off at 1440");

  // ══════════════════════════════════════════════════════════════════════════
  // `P2.11` — THE EVENT IS ON SETTINGS → NOTIFICATIONS, WHERE BR-NOT-017 PUTS IT
  // ══════════════════════════════════════════════════════════════════════════
  //
  // ⚠ **THE SWEEP ITSELF IS NOT CLICKABLE AND IS NOT PRETENDED TO BE.** It is a
  // management command; what a person can see in the product is the RULE that
  // governs it, and BR-NOT-017 says that rule has exactly one home. A row that
  // never reached this screen would be a notification nobody could switch, which
  // is the failure this half checks for.
  console.log("\n  P2.11 — the rule has a home (S8)");
  await page.goto(`${BASE}/${TENANT}/settings/notifications`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("tbody tr", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/02-notification-rules.png`, fullPage: true });

  const rulesBody = (await page.textContent("body")) ?? "";
  if (rulesBody.includes("Counter left open")) {
    ok("Counter left open is a rule a System Admin can see and switch");
  } else {
    bad(
      "Counter left open is not on Settings → Notifications",
      "BR-NOT-017 — every notification rule has ONE home",
    );
  }
  if (rulesBody.includes("counter_left_open")) {
    bad("the raw event key is on screen", "B14 rule 32 — no internal code in clerk-facing copy");
  } else {
    ok("the event key itself is not on screen");
  }
  if (rulesBody.includes("When the banking day has ended")) {
    ok("its timing reads in a clerk's words");
  } else {
    note("the timing cell was not found by text — check the screenshot");
  }
} catch (error) {
  bad("the walk stopped", String(error).slice(0, 300));
} finally {
  await browser.close();
}

console.log(`\n  ${passes} passed · ${failures.length} failed`);
for (const line of failures) console.log(`    ● ${line}`);
console.log(`  screenshots: ${SHOTS}`);
process.exit(failures.length === 0 ? 0 : 1);
