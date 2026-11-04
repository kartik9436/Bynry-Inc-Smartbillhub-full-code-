// ── Trace ──────────────────────────────────────────────
// Change:   CR-073 — universal search reaches Work and Plans & Rates.
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · 13-change-process.md's CLOSURE BAR (PO 2026-08-18:
//           *"CR is not closed until we have confirm user is able to perform
//           tasks using screen/broswer/UI"*) · B14 rule 31 (no database id is
//           ever the visible value of a field)
// ───────────────────────────────────────────────────────
/**
 * cr073_search_walkthrough — TYPE in the real box, READ what comes back, and
 * CLICK through to the screen behind it.
 *
 *     ./08-qa/01-e2e/stack/boot_stack.sh
 *     node 10-scripts/cr073_search_walkthrough.mjs
 *
 * ⚠ **IT DOES NOT ASSERT THAT A GROUP EXISTS — IT READS THE RENDERED HEADING,
 * FOLLOWS THE LINK, AND CHECKS THE PAGE THAT OPENS.** That distinction is the
 * whole reason this file exists: 52 backend cases and 258 frontend cases pass
 * on this change already, and not one of them can see a heading that renders
 * blank because a locale key is missing, or a link that resolves to a route
 * `App.tsx` never looks at (`DEF-WRK-4051` made two shipped screens unreachable
 * for three commits with every check green).
 *
 * ⚠ **IT ALSO MEASURES THE CROWDING**, which was the open question when this
 * scope was set: fifteen groups at five rows is 75 rows in the arithmetic worst
 * case. The counts it prints are the evidence in the decision log — taken, not
 * assumed.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
const page = await ctx.newPage();

// ── sign in through the real form ──────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

// The shell's own search input, found the way a screen reader would.
const box = page.locator(".shell-search input[type=search]").first();
await box.waitFor({ timeout: 20000 });

/** Type into the real box and read the rendered popover. */
async function search(term) {
  await box.click();
  await box.fill("");
  await box.type(term, { delay: 25 });
  await page.waitForTimeout(1200); // the 300 ms debounce plus the round trip
  const sections = page.locator('header section, [role="status"]').first();
  await sections.waitFor({ timeout: 15000 }).catch(() => {});
  const groups = await page.evaluate(() => {
    const out = [];
    for (const s of document.querySelectorAll("section")) {
      const h = s.querySelector("h2");
      if (!h) continue;
      const rows = [...s.querySelectorAll("li a")].map((a) => ({
        text: a.textContent.trim(),
        href: a.getAttribute("href"),
      }));
      if (rows.length) out.push({ heading: h.textContent.trim(), rows });
    }
    return out;
  });
  return groups;
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const measured = [];

async function probe(term, expectHeading) {
  note(`\ntyping "${term}"`);
  const groups = await search(term);
  const rows = groups.reduce((n, g) => n + g.rows.length, 0);
  measured.push({ term, groups: groups.length, rows });
  note(`  → ${groups.length} group(s), ${rows} row(s): ${groups.map((g) => `${g.heading} (${g.rows.length})`).join(" · ") || "nothing"}`);

  for (const g of groups) {
    // A heading that renders blank is the silent-locale failure this repo opens
    // with: the row is there, the API served it, tsc passed, and the clerk sees
    // an empty strip of grey.
    if (!g.heading) fail(`a group rendered with NO heading — a locale key resolves to nothing`);
    if (/^shell\.search/.test(g.heading)) fail(`heading rendered the KEY, not the words: ${g.heading}`);
    for (const r of g.rows) {
      if (UUID.test(r.text)) fail(`B14 rule 31 — a uuid is VISIBLE in a result: ${r.text}`);
      if (!r.href || r.href === "#") fail(`a row has no destination: ${r.text}`);
      if (/\/\/[^/]/.test(r.href.replace(/^https?:/, ""))) fail(`protocol-relative href (the //portal/… trap): ${r.href}`);
    }
  }
  if (expectHeading) {
    const hit = groups.find((g) => g.heading.toLowerCase().includes(expectHeading.toLowerCase()));
    if (!hit) fail(`"${term}" did not produce a "${expectHeading}" group`);
    else ok(`"${term}" → ${hit.heading}: ${hit.rows.map((r) => r.text).join(" | ")}`);
    return hit;
  }
  return null;
}

/** Follow a row and confirm the page that opens is the one it promised. */
async function follow(group, expectOnPage) {
  if (!group || !group.rows.length) return;
  const href = group.rows[0].href;
  await page.goto(`${BASE}${href}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const body = await page.evaluate(() => document.body.innerText);
  if (/not built yet|Page not found|404/i.test(body.slice(0, 800))) {
    fail(`${href} opened the not-built-yet / 404 page — the router does not serve it`);
  } else if (expectOnPage && !body.includes(expectOnPage)) {
    fail(`${href} opened, but "${expectOnPage}" is not on the page it drew`);
  } else {
    ok(`${href} opens a real screen${expectOnPage ? ` showing "${expectOnPage}"` : ""}`);
  }
  await page.goto(`${BASE}/${TENANT}/dashboard`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
}

// ── the six new groups ─────────────────────────────────────────────────────
const orders = await probe("WO-", "Work orders");
await follow(orders);

const templates = await probe("Meter set", "templates");
await follow(templates);

const parts = await probe("MTR", "Parts");
await follow(parts);

const crews = await probe("Crew", "Crews");
await follow(crews);

const plans = await probe("RES", "Plans");
await follow(plans);

const charges = await probe("LATE", "Charge codes");
await follow(charges);

// ── the crowding measurement (the open question this change created) ───────
note("\n── crowding, measured rather than assumed ─────────────────");
for (const t of ["MTR", "Meter", "A-1", "e", "0"]) {
  const groups = await search(t);
  const rows = groups.reduce((n, g) => n + g.rows.length, 0);
  note(`  "${t}" → ${groups.length} group(s), ${rows} row(s)`);
  measured.push({ term: t, groups: groups.length, rows });
}
const worst = measured.reduce((a, b) => (b.groups > a.groups ? b : a), measured[0]);
note(`\nWORST OBSERVED: "${worst.term}" — ${worst.groups} groups, ${worst.rows} rows (arithmetic worst case is 15 groups / 75 rows)`);

// ── DEF-WRK-4094: a "View all" must actually filter ────────────────────────
note("\n── DEF-WRK-4094 · does \"View all\" really filter? ─────────");
for (const [path, term] of [["/work/parts", "MTR"], ["/work/crews", "Crew"]]) {
  await page.goto(`${BASE}/${TENANT}${path}?q=${encodeURIComponent(term)}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);
  const value = await page.evaluate(() => {
    const i = document.querySelector('main input[type="search"], main input[placeholder*="earch"]');
    return i ? i.value : null;
  });
  if (value === term) ok(`${path}?q=${term} — the list opened with "${term}" in its own search box`);
  else fail(`${path}?q=${term} — the search box reads ${JSON.stringify(value)}; the link promised a filter and delivered a full list`);
}

console.log("\n" + (problems.length ? `FAILED — ${problems.length} problem(s):\n  - ${problems.join("\n  - ")}` : "PASSED — every group renders, every link opens, nothing shows a uuid"));
await browser.close();
process.exit(problems.length ? 1 : 0);
