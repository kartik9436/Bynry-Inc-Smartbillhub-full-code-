// ── Trace ──────────────────────────────────────────────
// Change:  `CR-136-BRC07` phase 2 — `P2.7` (`Start counter →` in every payments
//          page head), `P2.8` ③ (the Batch filter chip on 2·1) and `P2.9`
//          (2·3a's counter banner, with the way out).
// Rules:   CLAUDE.md hard-won law 6 — *"Diff the running app against
//          `05-prototype/`. No gate looks at rendered output. Nine defects were
//          found this way and by nothing else."*
// Screens: 1·1 Summary · 2·1 Payments · 2·3a Record a payment · 3·1 Counters ·
//          7·3a the collections ladder
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS WALK IS FOR, AND IT IS NOT "DOES THE BUTTON EXIST".** `P2.7`'s
// whole subject is a DOOR, and the failure it exists to prevent is a door that
// is present, tested, typed and green while pointing nowhere — the customer
// portal shipped **two working doors out of eight** that way on 2026-09-05, and
// every one of its 391 cases passed. So every assertion below reads an `href`
// off the rendered page and then FOLLOWS it, and the screen that opens is
// checked for being the right screen rather than for being a screen.
//
// ⚠ **`GET /counters` IS `P2.3` AND IS NOT SERVED AT THIS COMMIT.** That is the
// state this walk runs in and it is the right one to walk: the control must
// render `Start counter →` — never an error, never a blank slot — when the read
// 404s, because that is what every clerk will see until `P2.3` lands.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   10-scripts/proof-db.sh build --force        # once, if the template is stale
//   10-scripts/proof-db.sh clone p2head
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p2head \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8395 --noreload)
//   (cd 07-frontend && ./node_modules/.bin/vite build && PORT=8396 \
//      API_PROXY_TARGET=http://127.0.0.1:8395 node server.mjs)
//   BASE=http://127.0.0.1:8396 node 10-scripts/p2head_counter_door_walkthrough.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8396";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots-p2head";

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

/** A clipped figure reads perfectly to `textContent` and is cut in half on
 *  screen — the defect phase 0's walk found. Overflow is MEASURED. */
const clipped = (selector) =>
  page.$$eval(selector, (nodes) =>
    nodes
      .filter((n) => n.scrollWidth > n.clientWidth + 1)
      .map((n) => `${(n.textContent ?? "").trim().slice(0, 40)}`),
  );

const doorHref = () =>
  page.$eval('[data-counter-door]', (n) => n.getAttribute("href")).catch(() => null);

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ══════════════════════════════════════════════════════════════════════════
  // `P2.7` — THE DOOR, ON EVERY PAYMENTS SCREEN
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P2.7 — Start counter → in every payments page head");

  // Six tabs. `counter` is excluded on purpose: 3·1 draws the control as its
  // OWN primary (p052) and the `P2.6` lane built it there, so a second copy in
  // the secondary slot would be two identical buttons on one head.
  const TABS = [
    ["summary", "/payments"],
    ["record", "/payments/record"],
    ["imports", "/payments/imports"],
    ["settlements", "/payments/settlements"],
    ["outstandings", "/payments/outstandings"],
  ];
  for (const [tab, path] of TABS) {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1800);
    const href = await doorHref();
    if (href === null) {
      bad(`no Start counter control on the ${tab} tab`, "P2.7's whole subject");
    } else if (href !== `/${TENANT}/payments/counter?start=1`) {
      bad(`the ${tab} tab's door points at ${href}`, "expected /payments/counter?start=1");
    } else {
      ok(`${tab} carries the door`, href);
    }
  }
  await page.screenshot({ path: `${SHOTS}/01-payments-head.png` });

  // The counter tab has its OWN primary and must not grow a second.
  await page.goto(`${BASE}/${TENANT}/payments/counter`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  const onCounter = await page.$$eval("[data-counter-door]", (n) => n.length);
  if (onCounter === 0) ok("the counter tab draws no SECOND door", "3·1 has its own primary");
  else bad(`the counter tab draws ${onCounter} extra door(s)`, "two identical buttons on one head");
  await page.screenshot({ path: `${SHOTS}/02-counter-tab.png` });

  // The ladder — a payments screen by the strip it carries (7·3a).
  await page.goto(`${BASE}/${TENANT}/payments/collections`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  const ladderHref = await doorHref();
  if (ladderHref === `/${TENANT}/payments/counter?start=1`) ok("the ladder carries the door");
  else bad("the collections ladder has no door", String(ladderHref));

  // ── FOLLOW IT. A door is only a door if it opens something. ───────────────
  console.log("\n  P2.7 — and the door actually opens 3·3a");
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  await page.click("[data-counter-door]");
  await page.waitForTimeout(2200);
  const afterUrl = page.url();
  if (!afterUrl.includes("/payments/counter")) {
    bad("the door did not land on the Counter tab", afterUrl);
  } else if (!afterUrl.includes("start=1")) {
    bad("the door landed on 3·1 without opening 3·3a", afterUrl);
  } else {
    ok("the door lands on 3·1 with ?start=1", afterUrl);
  }
  const dialog = await page.$('[role="dialog"]');
  if (dialog) ok("3·3a Start your counter opened over it");
  else note("no dialog opened — `P2.6` reads ?start=1, so check that lane if this stays");
  await page.screenshot({ path: `${SHOTS}/03-start-modal.png` });

  // ══════════════════════════════════════════════════════════════════════════
  // `P2.9` — 2·3a's BANNER, AND THE WAY OUT
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P2.9 — the banner on Record a payment");
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  await page.click('button:has-text("Record payment")').catch(() => {});
  await page.waitForTimeout(2200);
  const banner = await page.$("[data-counter-banner]");
  if (!banner) {
    bad("no counter banner on 2·3a", "`a clerk must never wonder` — note ①");
  } else {
    const state = await banner.getAttribute("data-counter-banner");
    ok(`the banner is drawn, state ${state}`);
    const text = (await banner.textContent()) ?? "";
    if (state === "none") {
      if (text.includes("You have no counter open.")) ok("the drawn FACT is on screen");
      else bad("the refusal sentence is not the drawn one", text.slice(0, 60));
      if (text.includes("Start one before you take money."))
        ok("the drawn INSTRUCTION is on screen");
      else bad("the next-step sentence is missing", text.slice(0, 60));
    }
  }
  // ⚠ **THE ASSERTION THIS TASK EXISTS FOR.** A refusal with no door is the
  // defect, not the feature.
  const bannerDoor = await page
    .$eval('[data-counter-banner="none"] ~ *, .modal-card [data-counter-door]', (n) =>
      n.getAttribute("href"),
    )
    .catch(() => null);
  const inModal = await page.$$eval(".modal-card [data-counter-door]", (n) =>
    n.map((x) => x.getAttribute("href")),
  );
  if (inModal.length > 0 && inModal[0] === `/${TENANT}/payments/counter?start=1`) {
    ok("the refusal offers the way out", inModal[0]);
  } else {
    bad("the banner refuses with no door", JSON.stringify(inModal) + " " + String(bannerDoor));
  }
  await page.screenshot({ path: `${SHOTS}/04-record-banner.png` });

  const cut = await clipped("[data-counter-banner], [data-counter-door]");
  if (cut.length === 0) ok("nothing in the banner or the door is clipped");
  else bad(`${cut.length} clipped element(s)`, cut.join(" | "));

  // ══════════════════════════════════════════════════════════════════════════
  // `P2.8` — SOURCE AND BATCH, AND THE TWO FILTER CHIPS
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  P2.8 — the two columns and the two filters on 2·1");
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2200);
  const headers = await page.$$eval("th", (n) =>
    n.map((x) => (x.textContent ?? "").trim().toUpperCase()),
  );
  for (const column of ["SOURCE", "BATCH"]) {
    if (headers.includes(column)) ok(`the ${column} column is drawn`);
    else bad(`no ${column} column on 2·1`, headers.join(" · ").slice(0, 120));
  }
  // The offer panel, where both filters have to be offerable.
  await page.click('summary:has-text("Filter")').catch(() => {});
  await page.waitForTimeout(900);
  const panel = (await page.textContent(".table-toolbar")) ?? "";
  if (panel.includes("Source")) ok("the Source filter is offered");
  else bad("the Source filter is not offered", panel.slice(0, 120));
  if (panel.includes("Batch")) ok("the Batch filter is offered");
  else note("the Batch filter is not offered — its options are the batches ON THE PAGE, so a tenant with no batched payments offers none");
  await page.screenshot({ path: `${SHOTS}/05-filters.png`, fullPage: false });

  // ── 1280, the laptop minimum every staff screen must work at ──────────────
  console.log("\n  the staff minimum width");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${BASE}/${TENANT}/payments/record`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  const wrapped = await page.$$eval(".page-header-actions", (nodes) =>
    nodes.map((n) => n.getBoundingClientRect().height),
  );
  if (wrapped.length && wrapped[0] > 64)
    bad("the action row wrapped at 1280", `height ${wrapped[0]}px`);
  else ok("the action row holds one line at 1280", `height ${wrapped[0] ?? "n/a"}px`);
  await page.screenshot({ path: `${SHOTS}/06-1280.png` });
} catch (error) {
  bad("the walk threw", String(error).slice(0, 200));
} finally {
  await browser.close();
  console.log(`\n  ${passes} passed · ${failures.length} failed`);
  for (const line of failures) console.log(`    ● ${line}`);
  process.exit(failures.length === 0 ? 0 : 1);
}
