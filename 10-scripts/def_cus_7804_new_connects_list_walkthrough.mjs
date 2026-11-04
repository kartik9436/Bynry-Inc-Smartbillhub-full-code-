// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-CUS-7804` — the five facts `GET /connections` served on
//          2026-09-28 that no screen read, now wired to S86's list.
// Rules:   hard-won law 6 (NO GATE IN THIS REPO READS RENDERED OUTPUT — nine
//          defects were found this way and by nothing else) · law 2 (built is
//          not wired) · B14 rule 42 (a screen is judged as it renders)
// Design:  05-prototype/new-connect-detail-2026-09-28/00-list.png
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS PROVES THAT `newConnectList.dom.test.tsx` CANNOT.** jsdom
// computes no layout and renders no CSS, so the accent on a 41-day-old build
// and the absence sentence sitting where a figure would be are things only a
// browser can show. This drives the REAL stack — Django on :8098, the BUILT
// SPA served by `server.mjs` on :8099, the same-origin `/api` join — and
// photographs the list with every new column turned on.
//
// ⚠ **IT ALSO READS BACK WHAT IT PHOTOGRAPHED**, because a screenshot nobody
// asserts over is a picture and not a check. Each of the five facts is read
// out of the rendered DOM and printed beside what the fixture put in.
//
// SEED FIRST:  cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//                python3 ../10-scripts/def_cus_7804_seed_build_rows.py
// RUN:         node 10-scripts/def_cus_7804_new_connects_list_walkthrough.mjs
const { mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8099";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def_cus_7804_list";
mkdirSync(OUT, { recursive: true });

const say = (...a) => console.log(...a);
const findings = [];

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
// ⚠ **TWO CONSOLE MESSAGES ARE THE CONTAINER'S AND NOT THE PRODUCT'S, AND
// THEY ARE NAMED RATHER THAN SWALLOWED.** The CSP `frame-ancestors` notice is
// the SPA's own `<meta>` policy, which a browser reports on every page of this
// app and which nothing on a screen can act on; `ERR_CERT_AUTHORITY_INVALID`
// is this container's outbound proxy CA, not a request the product made
// wrongly. Counting either as a finding makes the exit code mean nothing —
// law 7's *a check's output must distinguish pass from fail to a reader* —
// and the pair is printed at the end either way, so nothing is hidden.
const ENVIRONMENT_NOISE = [/frame-ancestors/, /ERR_CERT_AUTHORITY_INVALID/];
const noise = [];
page.on("console", (m) => {
  if (m.type() !== "error") return;
  const text = m.text().slice(0, 140);
  (ENVIRONMENT_NOISE.some((re) => re.test(text)) ? noise : findings).push(`console: ${text}`);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 45000 });
say(`signed in as ${EMAIL}`);

await page.goto(`${BASE}/${TENANT}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
await page.waitForSelector("[data-tile]", { timeout: 30000 });
await page.waitForTimeout(800);

// ── 1 · the strip, with the drawing's two new tiles on it ─────────────────
const tiles = await page.$$eval("[data-tile]", (nodes) =>
  nodes.map((n) => ({
    id: n.getAttribute("data-tile"),
    tag: n.tagName.toLowerCase(),
    filter: n.getAttribute("data-tile-filter"),
    text: (n.textContent ?? "").replace(/\s+/g, " ").trim(),
  })),
);
say("\nTILES");
for (const tile of tiles) say(`  ${tile.tag.padEnd(6)} ${String(tile.id).padEnd(20)} ${tile.text}`);
if (!tiles.some((t) => t.id === "waiting-anyone")) findings.push("no `Waiting on someone` tile");
if (!tiles.some((t) => t.id === "owed")) findings.push("no `Owed on builds` tile");
const owed = tiles.find((t) => t.id === "owed");
if (owed && owed.tag !== "div") findings.push("the owed tile is a control and should be a fact");
if (owed && /\$|0\.00/.test(owed.text)) findings.push(`the owed tile prints money: ${owed.text}`);
const waitingAnyone = tiles.find((t) => t.id === "waiting-anyone");
if (waitingAnyone && waitingAnyone.tag !== "div") {
  findings.push("`Waiting on someone` is clickable and `f.state` has no waiting value (OQ-371)");
}

await page.screenshot({ path: `${OUT}/01-list-default-1440.png`, fullPage: true });
say(`  captured 01-list-default-1440.png`);

// ── 2 · the two DRAWN columns: CUSTOMER and AGING ─────────────────────────
const headers = await page.$$eval("thead th", (n) =>
  n.map((h) => (h.textContent ?? "").replace(/[▲▼\s]+/g, " ").trim()),
);
say(`\nCOLUMNS: ${headers.join(" · ")}`);
for (const want of ["Customer", "Aging"]) {
  if (!headers.some((h) => h.includes(want))) findings.push(`no ${want} column on screen`);
}

const customers = await page.$$eval("tbody tr", (rows) =>
  rows.map((r) => ({
    build: (r.querySelector("td")?.textContent ?? "").trim().slice(0, 14),
    named: (r.querySelector("[data-customer-account]")?.textContent ?? "").trim(),
    absent: (r.querySelector("[data-customer-absent]")?.textContent ?? "").trim(),
    ageDays: r.querySelector("[data-age-days]")?.getAttribute("data-age-days"),
    accented: r.querySelector("[data-age-days]")?.getAttribute("data-age-accented"),
  })),
);
say("\nCUSTOMER and AGING, row by row");
for (const row of customers) {
  say(
    `  ${row.build.padEnd(14)} customer=${(row.named || row.absent || "«EMPTY CELL»").padEnd(30)}` +
      ` age=${row.ageDays ?? "-"}d accent=${row.accented ?? "-"}`,
  );
}
// The empty case is the one that matters: a build with no owner must SAY so.
if (!customers.some((r) => r.absent.length > 0)) {
  findings.push("no row states `no account yet` — the seeded owner-less build should");
}
if (customers.some((r) => !r.named && !r.absent)) {
  findings.push("a CUSTOMER cell is empty rather than stating an absence (DEF-127)");
}
if (!customers.some((r) => r.accented === "true")) {
  findings.push("no row draws an accented age — the 41-day build should");
}

// ── 3 · the five behind the column chooser ────────────────────────────────
await page.click('[aria-label="Show or hide columns"]');
await page.waitForTimeout(300);
const offered = await page.$$eval("details[open] label", (n) =>
  n.map((l) => (l.textContent ?? "").trim()),
);
say(`\nCHOOSER OFFERS: ${offered.join(" · ")}`);
for (const want of ["Charged", "Mode", "Scope", "Raised by", "Last event"]) {
  if (!offered.includes(want)) findings.push(`the chooser does not offer ${want}`);
}
// ⚠ **THE BOX IS FOUND BY ITS LABEL'S TEXT, IN THE PAGE, AND THE RESULT IS
// CHECKED.** The first draft used `page.$('label:text-is("Charged") input')`,
// which matched NOTHING and returned null — and the loop then did nothing at
// all, silently, so the walk reported five empty columns as if the cells were
// broken. A selector that finds nothing and a cell that renders nothing are
// indistinguishable unless the toggle says whether it fired (law 7).
for (const want of ["Charged", "Mode", "Scope", "Raised by", "Last event"]) {
  const turned = await page.evaluate((label) => {
    const panel = document.querySelector("details[open]");
    if (panel === null) return "no open chooser";
    for (const one of panel.querySelectorAll("label")) {
      if ((one.textContent ?? "").trim() !== label) continue;
      const box = one.querySelector('input[type="checkbox"]');
      if (box === null) return "label with no box";
      if (!box.checked) box.click();
      return "on";
    }
    return "no such label";
  }, want);
  if (turned !== "on") findings.push(`could not turn on ${want}: ${turned}`);
}
await page.waitForTimeout(400);
await page.click('[aria-label="Show or hide columns"]');
await page.waitForTimeout(400);

const extras = await page.$$eval("tbody tr", (rows) =>
  rows.map((r) => ({
    build: (r.querySelector("td")?.textContent ?? "").trim().slice(0, 14),
    charged:
      r.querySelector("[data-charged]")?.getAttribute("data-charged") ??
      `«${(r.querySelector("[data-charged-absent]")?.textContent ?? "EMPTY").trim()}»`,
    mode:
      r.querySelector("[data-mode]")?.textContent?.trim() ??
      `«${(r.querySelector("[data-mode-absent]")?.textContent ?? "EMPTY").trim()}»`,
    scope:
      r.querySelector("[data-scope]")?.textContent?.trim() ??
      `«${(r.querySelector("[data-scope-absent]")?.textContent ?? "EMPTY").trim()}»`,
    lastEvent: r.querySelector("[data-last-event]")?.textContent?.replace(/\s+/g, " ").trim(),
  })),
);
say("\nTHE CHOOSER'S COLUMNS, row by row");
for (const row of extras) {
  say(
    `  ${row.build.padEnd(14)} charged=${String(row.charged).padEnd(14)}` +
      ` mode=${String(row.mode).padEnd(20)} scope=${String(row.scope).padEnd(22)}` +
      ` last=${row.lastEvent ?? "-"}`,
  );
}
if (!extras.some((r) => String(r.charged).includes("Not priced"))) {
  findings.push("no row states `Not priced` — the unquoted build should");
}
const body = await page.$eval("tbody", (n) => n.textContent ?? "");
if (body.includes("$")) findings.push("a currency symbol reached the table and none is served");

await page.screenshot({ path: `${OUT}/02-list-all-columns-1440.png`, fullPage: true });
say(`  captured 02-list-all-columns-1440.png`);
await page.setViewportSize({ width: 1280, height: 1000 });
await page.waitForTimeout(500);
await page.screenshot({ path: `${OUT}/03-list-all-columns-1280.png`, fullPage: true });
say(`  captured 03-list-all-columns-1280.png`);

say("\n────────────────────────────────────────────");
if (noise.length > 0) {
  say(`${noise.length} environment message(s), counted as neither pass nor fail:`);
  for (const line of [...new Set(noise)]) say(`  · ${line}`);
}
if (findings.length === 0) {
  say("NOTHING TO REPORT: every wired fact rendered, and every empty case said so in words.");
} else {
  say(`${findings.length} FINDING(S):`);
  for (const line of findings) say(`  · ${line}`);
}
say(`screenshots in ${OUT}`);
await browser.close();
process.exit(findings.length === 0 ? 0 : 1);
