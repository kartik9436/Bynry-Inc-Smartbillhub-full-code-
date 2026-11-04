/**
 * RENDERED-OUTPUT CHECK — CR-075 wave D, tasks `D3` and `D4`. `RBS-002` and
 * `RBS-003`, in a real browser, against a real server and a real PostgreSQL.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"everything should be executed
 * based on actual code, and rules that we place, also ensure you do web
 * walkthorugh before you sign off the user story or build"*.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   Use a database NOBODY ELSE is seeding — on 2026-08-30 a sibling check lost
 *   three runs to the shared one, with every id changing mid-run, which looks
 *   exactly like a broken screen.
 *
 *     createdb sbh_rbsd34 TEMPLATE smartbillhub     (the seeded demo tenant)
 *     DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…sbh_rbsd34 \
 *       python3.12 10-scripts/render-checks/rbs_d_seed_library.py
 *     DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…sbh_rbsd34 \
 *       python3.12 06-backend/manage.py runserver 127.0.0.1:8077 --noreload &
 *     (cd 07-frontend && ./node_modules/.bin/vite build && \
 *        PORT=4277 API_PROXY_TARGET=http://127.0.0.1:8077 node server.mjs &)
 *     SMOKE_BASE=http://127.0.0.1:4277 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *       node 10-scripts/render-checks/rbs-d-the-library.mjs
 *
 *   ⚠ `python3` on this box is 3.11 and has no Django; `python3.12` does
 *   (`DEF-GOV-4299` — the boot script's refusal was true of the NAME and false
 *   of the machine, and it cost three lanes their walkthrough in one day).
 *
 * ── WHAT IT ASSERTS, AND WHY EACH ONE NEEDS A BROWSER ────────────────────
 *   1  **THE CHIPS ARE COUNTED FROM WHAT THE SERVER SENT** (`TC-RBS-20`,
 *      `BR-RBS-025`). The count on screen is compared with `category_chips` in
 *      the captured RESPONSE, so *"the screen drew a number"* and *"the server
 *      sent that number"* are asked separately — `DEF-RBS-4284` is what happens
 *      when only one of them is.
 *   2  **A FINANCE USER'S LIBRARY DOES NOT HOLD PLATFORM** (`RB-050`,
 *      `BR-RBS-024`). Signed in as the executive, then as the admin, against
 *      the SAME database. Two sessions, two answers, one screen.
 *   3  **EVERY CHIP AND CARD IS ACTUALLY PAINTED** — read from COMPUTED STYLE,
 *      never from a class name. B14 rule 21's migration clause means an
 *      unlisted file's utility renders as NOTHING while the class sits in the
 *      DOM, and `tsc`, eslint and every `toContain` pass over it (`DEF-974`).
 *   4  **EVERY DOOR RESOLVES TO A SCREEN THAT EXISTS** — asserted by following
 *      it, not by finding a string. `//host/…` reads as a perfectly good href
 *      to a string assertion (`DEF-CWP-3925`), and `RBS-004` had no door at all
 *      until `RBS-003` landed.
 *   5  **THE EMPTY STATE NAMES THE ACTION THAT FILLS IT** (B14 rule 17) and
 *      that action goes somewhere.
 *   6  **NO DATABASE ID AND NO RULE ID REACHES A CLERK** (B14 rules 31, 32).
 *   7  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
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
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4277";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const ADMIN = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const ADMIN_PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
/** The executive — this product's FINANCE role (`ROLE_VISIBILITY_BY_CATEGORY`). */
const FINANCE = process.env.SMOKE_FINANCE_EMAIL ?? "avery.cole@sample.test";
const FINANCE_PASSWORD = process.env.SMOKE_FINANCE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-d-the-library";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  [/\bBR-[A-Z]{3}-\d{3,5}\b/, "a business-rule id"],
  [/\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b/, "a register id"],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "a database id"],
];

/**
 * Sign in and WAIT FOR THE DASHBOARD.
 *
 * ⚠ Three separate faults live in these five lines and each cost a lane a
 * debugging cycle. The address is `/{tenant}/signin`, not `/sign-in`. The work
 * email field is `type="text"` with `id="signin-email"`, so
 * `input[type="email"]` matches nothing and times out with a message about a
 * locator rather than about the page. And sign-in is an XHR, so
 * `waitForLoadState("networkidle")` returns BEFORE the session exists and every
 * later call answers 401 — which reads as a screen full of broken regions.
 * Landing on the dashboard is the fact that the session is real.
 */
async function signIn(page, email, password) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });
}

/** Every chip on a row, as `{code, label, count}` read off the rendered DOM. */
async function chipsOn(page, row) {
  return page.$$eval(`[data-chips="${row}"] [data-${row === "kind" ? "kind" : "category"}]`, (nodes) =>
    nodes.map((node) => ({
      code: node.getAttribute("data-kind") ?? node.getAttribute("data-category"),
      text: (node.textContent ?? "").trim(),
      // COMPUTED, not declared. A chip whose class never compiled is invisible
      // and its text is still in the DOM.
      border: getComputedStyle(node).borderTopWidth,
      background: getComputedStyle(node).backgroundColor,
    })),
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });

  // ── the ADMIN's library ──────────────────────────────────────────────
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answer, captured rather than inferred.
  const wire = [];
  page.on("response", async (response) => {
    if (!/\/api\/.*runbooks/.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });

  console.log("── sign in as the System Admin ───────────────────────────");
  await signIn(page, ADMIN, ADMIN_PASSWORD);

  console.log("── RBS-002.1 · the library ───────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/templates`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-002"]', { timeout: 15000 });
  await page.screenshot({ path: join(OUT, "rbs-002-1-library.png"), fullPage: true });

  const served = wire
    .filter((w) => /\/runbooks\/templates\b/.test(w.url))
    .map((w) => {
      try {
        return JSON.parse(w.body);
      } catch {
        return null;
      }
    })
    .filter(Boolean)
    .pop();
  check(served !== undefined && served !== null, "GET /runbooks/templates answered with a body");

  const categoryChips = await chipsOn(page, "category");
  const kindChips = await chipsOn(page, "kind");

  // 1 · TC-RBS-20 — the chips are the SERVER's, and the number on screen is the
  // number in the payload. Compared against the wire rather than against a
  // hard-coded 8, because the shipped registry holds one runbook today and the
  // rule is *"built from the templates present"*, not *"eight"*.
  if (served) {
    check(
      categoryChips.length === served.category_chips.length,
      `the category row drew one chip per served category — ${categoryChips.length} on screen, ` +
        `${served.category_chips.length} on the wire (${served.category_chips
          .map((c) => `${c.category}=${c.count}`)
          .join(" · ")})`,
    );
    for (const chip of served.category_chips) {
      const drawn = categoryChips.find((c) => c.code === chip.category);
      check(
        drawn !== undefined && drawn.text.endsWith(String(chip.count)),
        `chip ${chip.category} carries the server's count ${chip.count} ` +
          `(screen: ${drawn?.text ?? "ABSENT"})`,
      );
    }
    check(
      kindChips.map((c) => c.code).join(",") === "all,check,action",
      `the kind row is All · Checks · Actions and nothing else (saw ${kindChips
        .map((c) => c.code)
        .join(",")})`,
    );
    const allChip = kindChips.find((c) => c.code === "all");
    const servedAll = served.kind_chips.find((c) => c.kind === "all");
    check(
      allChip !== undefined && allChip.text.endsWith(String(servedAll.count)),
      `All carries the server's ${servedAll.count} (screen: ${allChip?.text ?? "ABSENT"})`,
    );
  }

  // 3 · every chip is PAINTED. A class that never compiled leaves the text in
  // the DOM and draws nothing at all.
  for (const chip of [...kindChips, ...categoryChips]) {
    check(
      chip.border !== "0px" || chip.background !== "rgba(0, 0, 0, 0)",
      `chip "${chip.text}" is actually painted (border ${chip.border}, background ${chip.background})`,
    );
  }

  // 6 · nothing a clerk must not read.
  const libraryText = (await page.textContent("body")) ?? "";
  for (const [pattern, what] of FORBIDDEN_IN_CLERK_COPY) {
    const hit = libraryText.match(pattern);
    check(hit === null, `the library shows no ${what}${hit ? ` — found "${hit[0]}"` : ""}`);
  }

  // 7 · no sideways scroll at 1440.
  check(
    (await page.evaluate(SIDEWAYS)) === 0,
    "the library does not scroll sideways at 1440",
  );

  // 4 · the card's title is a real door to the template detail.
  const firstTitle = await page.$("[data-card-title]");
  const titleHref = firstTitle === null ? null : await firstTitle.getAttribute("href");
  check(
    titleHref !== null && titleHref.startsWith(`/${TENANT}/runbooks/templates/`),
    `a card title opens the template detail (href ${titleHref})`,
  );

  console.log("── RBS-002.2 · one template ──────────────────────────────");
  if (titleHref !== null) {
    await page.goto(`${BASE}${titleHref}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-state="detail"]', { timeout: 15000 });
    await page.screenshot({ path: join(OUT, "rbs-002-2-detail.png"), fullPage: true });
    const detail = (await page.textContent("body")) ?? "";
    check(
      /What it can touch/i.test(detail),
      "the detail draws *What it can touch* — the first thing after the name",
    );
    // For a Check it always reads *Nothing*, and that is the whole reason a
    // Check can be trusted (`BR-RBS-002`: the capability is ABSENT, not
    // withheld).
    const touchRows = await page.$$eval("[data-plaintable] tbody tr", (rows) =>
      rows.map((row) => (row.textContent ?? "").replace(/\s+/g, " ").trim()),
    );
    console.log(`     rows drawn: ${JSON.stringify(touchRows)}`);
    check(
      touchRows.length === 2,
      `a Check draws TWO rows — Writes and Sends — and not the sheet's four ` +
        `(Reads and Runs for are on no payload; DEF-RBS-4309). Saw ${touchRows.length}.`,
    );
    check(
      touchRows.every((row) => /Nothing/.test(row)),
      "both rows read Nothing",
    );
    check(
      (await page.$('[data-region="what-it-does"]')) === null,
      "no *What it does* list is drawn, because the step LABELS are on no payload",
    );
    check(
      (await page.evaluate(SIDEWAYS)) === 0,
      "the template detail does not scroll sideways at 1440",
    );
  }

  console.log("── RBS-003 · My runbooks ─────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/mine`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-003"]', { timeout: 15000 });
  await page.screenshot({ path: join(OUT, "rbs-003-my-runbooks.png"), fullPage: true });

  const rows = await page.$$("tbody tr");
  console.log(`     ${rows.length} runbook row(s) drawn`);
  if (rows.length === 0) {
    // 5 · `RBS-003.3` — an empty list names the missing thing and the action
    // that fills it (B14 rule 17).
    const empty = (await page.textContent("body")) ?? "";
    check(/No runbooks yet/.test(empty), "the empty state names what is missing");
    check(/Add one from templates/.test(empty), "…and how to fill it");
    const cta = await page.$('button:has-text("Browse templates")');
    check(cta !== null, "…and offers the button that does it");
    if (cta !== null) {
      await cta.click();
      await page.waitForURL(/\/runbooks\/templates$/, { timeout: 15000 });
      check(true, "Browse templates → actually navigates to the library");
      await page.goBack({ waitUntil: "networkidle" });
    }
  } else {
    const headers = await page.$$eval("thead th", (cells) =>
      cells.map((cell) => (cell.textContent ?? "").trim()),
    );
    check(
      headers.join(" · ") ===
        "Runbook · Kind · Category · Schedule · Last run · Result · Open items · Actions",
      `the eight columns are in the sheet's order (saw: ${headers.join(" · ")})`,
    );
    // 4 · the door `RBS-004` had none of. Followed, not merely found.
    const nameLink = await page.$("[data-runbook]");
    const href = nameLink === null ? null : await nameLink.getAttribute("href");
    check(href !== null && href.startsWith(`/${TENANT}/runbooks/`), `a runbook name links to ${href}`);
    if (href !== null) {
      await page.goto(`${BASE}${href}`, { waitUntil: "networkidle" });
      const landed = (await page.textContent("body")) ?? "";
      check(
        !/not built yet|coming soon|opens with the next release/i.test(landed),
        `${href} opens a screen that exists`,
      );
      await page.goto(`${BASE}/${TENANT}/runbooks/mine`, { waitUntil: "networkidle" });
    }
  }

  const mineText = (await page.textContent("body")) ?? "";
  for (const [pattern, what] of FORBIDDEN_IN_CLERK_COPY) {
    const hit = mineText.match(pattern);
    check(hit === null, `My runbooks shows no ${what}${hit ? ` — found "${hit[0]}"` : ""}`);
  }
  check(
    (await page.evaluate(SIDEWAYS)) === 0,
    "My runbooks does not scroll sideways at 1440",
  );

  // ── 2 · THE SAME LIBRARY, AS A FINANCE USER ──────────────────────────
  //
  // `BR-RBS-024` clause 2 / `RB-050`, and `07-endpoints.md`'s own worked
  // example: *a Finance user's Templates page shows Finance, Payments and
  // Collections runbooks and not Platform.* A SECOND browser context, because
  // signing out and in again in one context is where a stale session makes a
  // permission check look like a screen fault.
  console.log("── the same library, signed in as Finance ────────────────");
  const financeContext = await browser.newContext({ viewport: VIEWPORT });
  const financePage = await financeContext.newPage();
  const financeWire = [];
  financePage.on("response", async (response) => {
    if (!/\/api\/.*runbooks\/templates/.test(response.url())) return;
    try {
      financeWire.push(await response.text());
    } catch {
      /* nothing to read */
    }
  });
  await signIn(financePage, FINANCE, FINANCE_PASSWORD);
  await financePage.goto(`${BASE}/${TENANT}/runbooks/templates`, { waitUntil: "networkidle" });
  await financePage.waitForSelector('[data-screen="RBS-002"]', { timeout: 15000 });
  await financePage.screenshot({ path: join(OUT, "rbs-002-1-finance.png"), fullPage: true });

  const financeChips = await chipsOn(financePage, "category");
  console.log(
    `     admin sees: ${categoryChips.map((c) => c.code).join(", ") || "(none)"}\n` +
      `     finance sees: ${financeChips.map((c) => c.code).join(", ") || "(none)"}`,
  );
  check(
    !financeChips.some((chip) => chip.code === "platform"),
    "a Finance user's library draws NO Platform chip",
  );
  const financeText = (await financePage.textContent("body")) ?? "";
  check(
    !/data-card-title="configuration_check"/.test(await financePage.content()),
    "…and no Platform template card either",
  );
  check(
    /No templates|no results|Nothing/i.test(financeText) || financeChips.length > 0,
    "…and the screen says what it is showing rather than drawing a blank",
  );

  // ── 5 · `RBS-003.3` — the empty state, and the ONLY way to reach it here ──
  //
  // ⚠ **THE SEEDED TENANT CANNOT BE EMPTIED AND THAT IS THE PRODUCT BEING
  // RIGHT.** Deleting the demo runbook is refused by the database itself —
  // *"BR-RBS-038: runbook version 1 cannot be deleted — a run pinned it"* — so
  // the empty list has to be reached honestly rather than by clearing a table.
  // A **Finance user's** My runbooks IS empty: the one runbook this tenant has
  // is category `platform`, and `ROLE_VISIBILITY_BY_CATEGORY` shows that to
  // `system_admin` alone. So this reaches `RBS-003.3` **and** proves the
  // catalogue's role filter in the same click — the list, not just the library.
  console.log("── RBS-003.3 · the empty state, as Finance ───────────────");
  await financePage.goto(`${BASE}/${TENANT}/runbooks/mine`, { waitUntil: "networkidle" });
  await financePage.waitForSelector('[data-screen="RBS-003"]', { timeout: 15000 });
  await financePage.screenshot({ path: join(OUT, "rbs-003-3-empty.png"), fullPage: true });
  const financeRows = await financePage.$$("tbody tr");
  check(
    financeRows.length === 0,
    `a Finance user's My runbooks is empty — the tenant's one runbook is Platform ` +
      `(saw ${financeRows.length} row(s))`,
  );
  const emptyText = (await financePage.textContent("body")) ?? "";
  check(/No runbooks yet/.test(emptyText), "the empty state names what is missing (B14 rule 17)");
  check(/Add one from templates/.test(emptyText), "…and how to fill it");
  const browse = await financePage.$('button:has-text("Browse templates")');
  check(browse !== null, "…and offers the button that does it");
  if (browse !== null) {
    // Followed, not merely found. A button with no handler renders, passes
    // every test and does nothing (hard-won law 2).
    await browse.click();
    await financePage.waitForURL(/\/runbooks\/templates$/, { timeout: 15000 });
    check(true, "Browse templates → actually navigates to the library");
  }
  check(
    (await financePage.evaluate(SIDEWAYS)) === 0,
    "the empty state does not scroll sideways at 1440",
  );

  writeFileSync(join(OUT, "wire.json"), JSON.stringify({ admin: wire, finance: financeWire }, null, 2));
  await browser.close();

  console.log("");
  if (failures.length > 0) {
    console.error(`⛔ ${failures.length} check(s) failed:`);
    for (const line of failures) console.error(`   · ${line}`);
    process.exit(1);
  }
  console.log(`✓ every check passed — screenshots and the wire capture in ${OUT}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
