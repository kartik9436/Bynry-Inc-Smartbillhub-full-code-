// ── Trace ──────────────────────────────────────────────
// Change:  CR-131-BRC07 steps 3-7 — a route names PREMISES and derives the
//          units, meters and accounts inside them.
// Ruling:  PO 2026-09-22, verbatim: "thi sis correct - The routes design —
//          storing 726 unit rows instead of 6 premises, and the route going
//          stale the moment anything changes".
// Rules:   CR-131-BRC07 §5 acceptance items 1-4 · NFR-3 · NFR-5 ·
//          CLAUDE.md hard-won law 6 (no gate looks at rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT A UNIT TEST CANNOT, AND WHY IT IS RUN AT 726 UNITS.
//
//   ⚠ **A FIX PROVED ON SIX UNITS PROVES NOTHING HERE** (`CR-131-BRC07` §5).
//   The whole defect is arithmetic on the UNIT COUNT — 52 URL characters and
//   5.1 database queries each — so a six-unit fixture cannot tell the fixed
//   product from the broken one. This drives a REAL BROWSER against a property
//   carrying 726 units and 725 meters, which is the size the Product Owner hit
//   it at, and it watches the REQUEST the browser actually makes.
//
//   1 · Step 3 draws a table of meters instead of "No meters yet". The empty
//       state over a failed request is the false ABSENCE this CR exists to
//       remove, so the table having ROWS is the assertion.
//   2 · The URL the browser sends is read off the wire. It was 32,781
//       characters; a server accepts 4,000-8,000.
//   3 · Step 4 SAVES and the route appears with its meter count.
//   4 · A unit added afterwards is on the route WITH NOBODY RE-OPENING THE
//       WIZARD — §5 item 3, which is the ruling itself and cannot be true of
//       any design that stores a photograph.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ADDRESS = process.env.ADDRESS ?? "1 Tower Block Way";
const OUT = process.env.OUT ?? "/tmp/cr131";
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

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });
let failures = 0;
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
};

// ⚠ Every meter-picker request the browser makes, read OFF THE WIRE. The URL
// length is the defect; asserting it from the source would prove the source.
const pickerUrls = [];
page.on("request", (req) => {
  if (req.url().includes("/routes/meter-picker")) pickerUrls.push(req.url());
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
console.log("signed in as", EMAIL);

const api = (path, init) =>
  page.evaluate(
    async ([p, i]) => {
      const res = await fetch(p, { credentials: "include", ...(i ?? {}) });
      return { status: res.status, body: await res.text() };
    },
    [path, init],
  );

// ── the property, and how big it really is ─────────────────────────────────
const found = JSON.parse(
  (await api(`/api/${TENANT}/premises?q=${encodeURIComponent(ADDRESS)}&per=5`)).body,
);
const premises = (found.results ?? []).find((row) => row.address_line === ADDRESS);
check("the 726-unit property is there", premises !== undefined, ADDRESS);
const unitsPage = JSON.parse(
  (await api(`/api/${TENANT}/units?premises=${premises.id}&per=1`)).body,
);
console.log(`property ${ADDRESS}: ${unitsPage.count} units`);
check("it is big enough to break the old code", unitsPage.count >= 726, `${unitsPage.count} units`);

// ── 1 · STEP 3 · THE METER TABLE, IN THE WIZARD ────────────────────────────
const code = `WLK${Math.random().toString(36).slice(2, 7).toUpperCase()}`;
await page.goto(`${BASE}/${TENANT}/settings/reference-data/routes-cycles`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await page.click('button:has-text("+ Add route")');
await page.waitForSelector('[data-rcw="title"]', { timeout: 20000 });
// ⚠ The wizard's fields carry no ids, so they are addressed by their LABEL —
// which is also what a person uses, and is the selector that survives a
// re-layout. `nth` on a bare input would silently move with the next column.
const codeBox = page.locator("label", { hasText: "Route code" }).locator("input").first();
await codeBox.fill(code);
await page.locator("label", { hasText: /^Name/ }).locator("input").first().fill("Tower block walk");
// step 2 — pick the building
await page.click('button:has-text("Continue")');
await page.waitForSelector('[data-rcw="table"] tbody tr, table tbody tr', { timeout: 30000 });
await page.waitForTimeout(1500);
const searchBoxes = await page.$$('input[type="search"]');
await searchBoxes[searchBoxes.length - 1].fill(ADDRESS);
await page.waitForTimeout(2500);
await page.click('table tbody tr input[type="checkbox"]');
await page.waitForTimeout(800);
await page.click('button:has-text("Continue")');
// step 3 — the meters
await page.waitForSelector('[data-rcw="stats"]', { timeout: 30000 });
await page.waitForTimeout(4000);
const meterRows = await page.$$eval('[data-rcw="table"] tbody tr', (ns) => ns.length);
const emptyShown = await page.$$eval('[data-rcw="table"] tbody tr', (ns) =>
  ns.some((n) => /No meters yet/i.test(n.textContent ?? "")),
);
const failShown = (await page.$$('[data-rcw="meters-failed"]')).length > 0;
const stats = await page.$$eval('[data-rcw="stats"]', (ns) => ns[0].textContent.replace(/\s+/g, " ").trim());
console.log("step 3 stats:", stats);
check("step 3 draws METER ROWS, not the empty state", meterRows > 1 && !emptyShown, `${meterRows} rows`);
check("step 3 is not showing the failure state either", !failShown);

// ── 2 · STEP 5 · THE URL, READ OFF THE WIRE ────────────────────────────────
const longest = pickerUrls.reduce((a, b) => (a.length >= b.length ? a : b), "");
console.log("meter-picker URL:", longest);
check("the URL is a few dozen characters, not tens of thousands", longest.length < 400, `${longest.length} chars`);
check("no unit_id parameter is sent at all", !longest.includes("unit_id="));

// ── 3 · STEP 4 · THE SAVE ──────────────────────────────────────────────────
// ⚠ **A WAIT WITH A DEADLINE AND A STATE IT IS WAITING FOR**, never a bare
// sleep: the meter query fetches 725 rows and the footer's Continue is
// disabled while it is in flight, so a fixed pause is a race that passes on a
// fast machine and fails on a loaded one.
await page.waitForSelector('button:has-text("Continue"):not([disabled])', { timeout: 60000 });
await page.click('button:has-text("Continue")');
await page.waitForTimeout(2500);
// ⚠ **THE COMMIT BUTTON IS NAMED, NOT MATCHED LOOSELY.** `has-text("Save")`
// also matches the "Save as" radio group's own label, which is DISABLED — so
// a loose selector waits thirty seconds on the wrong control and reports a
// timeout that reads like a broken screen.
const saveButton = page.locator('button:has-text("Create route")');
check("the review step offers its commit button", (await saveButton.count()) === 1);
// The review is read as a FACT, not skipped past: it is where BR-MET-074's
// move is stated to the clerk before the press.
const review = (await page.$eval("main", (n) => n.textContent.replace(/\s+/g, " ").trim()));
check("the review states the premises and unit counts", /Premises · units ?1 · 7\d\d/.test(review), review.match(/Premises · units ?[\d · ]+/)?.[0] ?? "not found");
check("the review states BR-MET-074's move before the press", /premises move from/i.test(review));
await saveButton.click();
await page.waitForTimeout(6000);
const savedRow = JSON.parse((await api(`/api/${TENANT}/routes?q=${code}&per=5`)).body);
const saved = (savedRow.results ?? []).find((row) => row.code === code);
check("step 4 saved the route", saved !== undefined, code);
check("the saved route reports its meters", saved !== undefined && saved.meters > 700, `${saved?.meters} meters`);
check("the saved route reports one premises", saved !== undefined && saved.premises === 1, `${saved?.premises} premises`);

// ── 4 · §5 ITEM 3 · A UNIT ADDED AFTERWARDS, NO WIZARD ─────────────────────
const before = JSON.parse((await api(`/api/${TENANT}/routes/${saved.id}`)).body);
const label = `W${Math.random().toString(36).slice(2, 8)}`;
const made = await api(`/api/${TENANT}/units`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ premises_id: premises.id, label, services: ["water"] }),
});
check("a unit was added on its own", made.status === 201 || made.status === 200, `HTTP ${made.status}`);
const after = JSON.parse((await api(`/api/${TENANT}/routes/${saved.id}`)).body);
check(
  "§5 item 3 — the new unit is ON THE ROUTE with nobody re-opening the wizard",
  after.membership.length === before.membership.length + 1,
  `${before.membership.length} -> ${after.membership.length} members`,
);

await page.screenshot({ path: `${OUT}/step3-meters.png`, fullPage: false });
console.log(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
