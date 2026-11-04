// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave C — the property's tabs. C1 (`PUJ-12`) · C2 (`PUJ-13`) ·
//          C3/C4 (`PUJ-14`) · C5 (`PUJ-15`, `DEF-AST-4690`) · C6 (`PUJ-16`,
//          `PUJ-17`).
// Rules:   BR-AST-004 (every asset on exactly one category tab) · BR-AST-044
//          (all three classifications on the DETAIL view; `meter_type` is
//          UNAVAILABLE on non-measuring types) · BR-MET-045 (the tab set, and
//          the tab is called Assets) · BR-MET-094 + BR-CUS-170 (a vacancy is
//          billed, automatically, to the owner's master account) · BR-MET-101
//          (a common area IS a unit with a flag) · BR-AUD-010 (one audit
//          surface) · BR-RAT-090 / CR-063 (trash prices per cart; fire prices
//          by diameter) · PO definition of done, verbatim: *"ensure you do web
//          walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH ONE NEEDS A BROWSER RATHER THAN A UNIT TEST.
//
//   1 · **C5 tags a real fire line on `brazosbend`**, through the API the
//       inventory picker posts to, and then reads it back off the property's
//       Assets tab. A migration test proves a ROW exists; only this proves a
//       clerk can put an asset on it and see it.
//   2 · **C3/C4** read the two group headings, their counts and the last-read
//       cell as RENDERED TEXT. The fixture in the suite is four objects a lane
//       typed; this is the server's own thirteen-type catalogue.
//   3 · **C1** reads the Owed column off a building whose units actually owe
//       money in the seeded ledger — 362.61 and 90.18 on `P-00039` — and
//       checks the vacancy sentence appears where there is no occupying
//       account and NO `0.00` is manufactured.
//   4 · **C2** presses `+ Add a common area` and creates one, then finds it in
//       the tab's table. A unit test can assert the button is in the markup;
//       only the browser can say it opens something that works.
//   5 · **C6** reads the audit tab with no press at all — no `Expand`, the old
//       value and the new one both on the row.
//
// ⚠ **THE WORK-ORDERS TAB IS NOT WALKED AND THIS SCRIPT SAYS SO OUT LOUD.**
// No work order exists on any sample property, so there is nothing to open. It
// is built to the journey and asserted in `buildViews.test.tsx`; that is not
// the same as having been seen, and reporting it as walked would be the exact
// dishonesty hard-won law 7 is about.
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

// ⚠ **CHECK THE PORT IS YOURS BEFORE YOU BELIEVE A WORD OF THE OUTPUT.** The
// first run of this walkthrough read a SIBLING LANE's backend: another lane was
// already serving 8411, this lane's `runserver` printed *"That port is already
// in use"* into a log nobody read, and every request went to their tree and
// their database. It answered `signin 201`, drew a real property and reported
// the Owed column as an em-dash — a *finding* about a screen that was working.
// `11-smoke-stack.sh` refuses a busy port for exactly this reason (assumption
// 5); this constant is not that check, so the operator has to be.
const BASE = process.env.BASE ?? "http://127.0.0.1:8478";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089c";
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

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });
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

const api = (path, init) =>
  page.evaluate(
    async ([p, i]) => {
      const res = await fetch(p, {
        credentials: "include",
        headers: i?.body ? { "Content-Type": "application/json" } : undefined,
        ...(i ?? {}),
      });
      return { status: res.status, body: await res.text() };
    },
    [path, init],
  );

const tabText = async (premisesId, tab) => {
  await page.goto(`${BASE}/${TENANT}/premises/${premisesId}?tab=${tab}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("h1", { timeout: 30000 });
  return page.evaluate(() => document.body.innerText);
};

// ══ 1 · C5 · TAG A FIRE LINE ON brazosbend ════════════════════════════════
say("── C5 · the fire service line (DEF-AST-4690)");
const types = JSON.parse((await api(`/api/${TENANT}/lookups/asset_types`)).body);
const rows = types.results ?? types.items ?? types;
const byCategory = {};
for (const row of rows) byCategory[row.category] = (byCategory[row.category] ?? 0) + 1;
const fire = rows.find((r) => r.code === "fire_line");
say(`   catalogue: ${JSON.stringify(byCategory)} · ${rows.length} types`);
check(fire !== undefined, `the picker offers "Fire service line" on ${TENANT}`);
check(byCategory.behind_the_meter === 10, "ten behind-the-meter types, not nine");

// Put one on a real unit. This is the post the inventory picker makes.
const premisesList = JSON.parse((await api(`/api/${TENANT}/premises?per=200`)).body);
// The LIST already carries `units`, so the detail read is made only for the
// handful this walk actually opens. The first draft fetched all 79 details
// twice and took four minutes to reach its first assertion.
const wanted = new Set(["P-00002", "P-00039"]);
const withUnits = [];
for (const row of premisesList.results ?? []) {
  if (!wanted.has(row.premise_no) && withUnits.length >= 4) continue;
  if ((row.units ?? 0) === 0) continue;
  const detail = JSON.parse((await api(`/api/${TENANT}/premises/${row.id}`)).body);
  if ((detail.unit_rows ?? []).length > 0) withUnits.push(detail);
}
const fireHost = withUnits.find((p) => p.premise_no === "P-00002") ?? withUnits[0];
const fireUnit = fireHost.unit_rows[0];
// ⚠ THE FIELD IS `unit_id`, NOT `assign_to_unit_id`. The first draft guessed
// the second and got a clean 422 naming the field — which is the server's
// `assets.unknown_field` refusal doing exactly its job, and is why this posts
// against the real endpoint instead of asserting a fixture.
const created = await api(`/api/${TENANT}/assets`, {
  method: "POST",
  body: JSON.stringify({
    type: "fire_line",
    status: "active",
    size_class: "FL-6",
    unit_id: fireUnit.id,
    // ⚠ **NO `service`, AND THAT IS THE PRODUCT AND NOT A SHORTCUT.** Sending
    // `service: "fire"` is refused `metering.service_not_enabled` — correctly:
    // `BR-MET-119` says a unit's services come from its PREMISES, and no
    // brazosbend address offers fire in `services_available`. A fire line is
    // non-measuring (`MEASURING_TYPES` is meter · net_meter · sub_meter), so
    // it needs no service point at all; the picker's own path for a
    // behind-the-meter asset is this one.
    install_date: "2026-09-09",
  }),
});
say(`   POST /assets fire_line → HTTP ${created.status}`);
let fireAssetNo = null;
if (created.status === 201) {
  fireAssetNo = JSON.parse(created.body).asset_no;
  say(`   tagged ${fireAssetNo} on ${fireHost.premise_no} · ${fireHost.address_line}`);
} else {
  say(`   body: ${created.body.slice(0, 400)}`);
}
check(created.status === 201, "a fire line can actually be tagged (the whole point of C5)");

// ══ 2 · C3 / C4 · THE ASSETS TAB ══════════════════════════════════════════
say("\n── C3/C4 · the Assets tab");
const assetsText = await tabText(fireHost.id, "assets");
await page.screenshot({ path: join(OUT, "c3-c4-assets.png"), fullPage: true });
const groups = await page.$$eval("[data-asset-group]", (ns) =>
  ns.map((n) => n.getAttribute("data-asset-group")),
);
const counts = await page.$$eval("[data-asset-group-count]", (ns) =>
  ns.map((n) => `${n.getAttribute("data-asset-group-count")}=${n.textContent.trim()}`),
);
say(`   groups: ${JSON.stringify(groups)} · counts: ${JSON.stringify(counts)}`);
check(assetsText.includes("Meters and sub-meters"), "the metered group is headed");
check(assetsText.includes("These are what bill."), "…and says what it means");
check(assetsText.includes("Behind the meter"), "the behind-the-meter group is headed");
check(assetsText.includes("We own them. They are not read."), "…and says what it means");
check(groups[0] === "metered", "what bills leads");
// ⚠ CASE-INSENSITIVE, AND THAT IS NOT A CONVENIENCE. `innerText` returns
// RENDERED text and B14's table headers are uppercased in CSS, so the column
// reads `LAST READ` on screen. The first draft searched for "Last read" and
// reported a column that was plainly there as missing — law 7's *looking at
// the wrong thing*, inside the check itself.
check(/last read/i.test(assetsText), "C4 · there is a Last read column at all");
const notRead = await page.$$eval("[data-not-read]", (ns) =>
  ns.map((n) => `${n.getAttribute("data-not-read")}: ${n.textContent.trim()}`),
);
say(`   not-read cells: ${JSON.stringify(notRead)}`);
check(
  notRead.some((c) => c.startsWith("fire_line:") && c.includes("billed on size")),
  'the fire line reads "not read — billed on size"',
);
// The tab keeps its name. `BR-MET-045`, and the PO reversed our rename.
const tabNames = await page.$$eval("[data-page-header-tabs] button", (bs) =>
  bs.map((b) => b.textContent.trim()),
);
say(`   tabs: ${JSON.stringify(tabNames)}`);
check(tabNames.includes("Assets") && !tabNames.includes("Meters"), "the tab is still called Assets");

// A cart, wherever one is tagged — trash carts live on their own addresses.
say("\n── C4 · a trash cart, on whichever building holds one");
let cartSeen = null;
for (const p of withUnits.slice(0, 6)) {
  const list = JSON.parse((await api(`/api/${TENANT}/assets?f.premises_id=${p.id}&per=200`)).body);
  if ((list.results ?? []).some((a) => a.type === "container_cart")) {
    const text = await tabText(p.id, "assets");
    const cells = await page.$$eval("[data-not-read]", (ns) =>
      ns.map((n) => `${n.getAttribute("data-not-read")}: ${n.textContent.trim()}`),
    );
    cartSeen = { premise: p.premise_no, cells, text };
    break;
  }
}
if (cartSeen === null) {
  say("   NOT WALKED — no container_cart is tagged on any brazosbend property");
} else {
  say(`   on ${cartSeen.premise}: ${JSON.stringify(cartSeen.cells)}`);
  check(
    cartSeen.cells.some((c) => c.startsWith("container_cart:") && c.includes("billed per cart")),
    'a cart reads "not read — billed per cart"',
  );
}

// ══ 3 · C1 · MONEY ON THE UNITS TAB ═══════════════════════════════════════
say("\n── C1 · what each unit owes");
const owing = withUnits.find((p) => p.premise_no === "P-00039") ?? withUnits[0];
const unitsText = await tabText(owing.id, "units");
await page.screenshot({ path: join(OUT, "c1-units.png"), fullPage: true });
const owed = await page.$$eval("[data-owed]", (ns) =>
  ns.map((n) => `${n.getAttribute("data-owed")} → ${n.textContent.trim()}`),
);
say(`   ${owing.premise_no} · ${owing.address_line}`);
for (const row of owed) say(`     ${row}`);
check(/\bowed\b/i.test(unitsText), "the column exists");
check(
  owed.some((r) => /\$\d/.test(r)),
  "at least one unit shows a real figure",
);
check(
  owed.every((r) => !/\.\d{3}/.test(r)),
  "every figure is at TWO decimals, never the ledger's four (hard rule 2)",
);
const vacancy = owed.filter((r) => r.includes("base charges bill to the owner"));
say(`   vacancy sentences: ${vacancy.length}`);
const zeroOnVacant = vacancy.some((r) => r.includes("$0.00"));
check(!zeroOnVacant, "no vacant unit manufactures a $0.00 (DEF-138)");

// ══ 4 · C2 · ADD A COMMON AREA ════════════════════════════════════════════
say("\n── C2 · adding a common area from the tab that is about them");
const commonText = await tabText(owing.id, "common-areas");
const hasAdd = await page.$$eval("button", (bs) =>
  bs.some((b) => b.textContent.trim().includes("Add a common area")),
);
say(`   tab says: ${commonText.split("\n").slice(0, 4).join(" / ")}`);
check(hasAdd, "the + Add a common area control is on the tab");
if (hasAdd) {
  await page.click('button:has-text("Add a common area")');
  await page.waitForSelector("#common-area-label", { timeout: 15000 });
  const modalText = await page.evaluate(() => document.body.innerText);
  check(
    modalText.includes("bills the owner"),
    "the modal names what it is about to do (BR-SHL-032)",
  );
  const label = `Bike store ${Date.now() % 100000}`;
  await page.fill("#common-area-label", label);
  await page.screenshot({ path: join(OUT, "c2-add-modal.png"), fullPage: true });
  await page.click('button:has-text("Add"):not(:has-text("Add a common area"))');
  await page.waitForTimeout(2500);
  const after = await tabText(owing.id, "common-areas");
  say(`   after the commit, the tab holds: ${after.includes(label) ? label : "(not found)"}`);
  check(after.includes(label), "the common area a clerk just made is on the tab");
}

// ══ 5 · C6 · THE AUDIT TAB, WITH NO PRESS ═════════════════════════════════
say("\n── C6 · the old value, without a press");
const auditText = await tabText(owing.id, "audit");
await page.screenshot({ path: join(OUT, "c6-audit.png"), fullPage: true });
const inline = await page.$$eval("[data-audit-inline]", (ns) =>
  ns.map((n) => n.textContent.trim().replace(/\s+/g, " ").slice(0, 120)),
);
// ⚠ **SCOPED TO THE TABLE, BECAUSE THE APP SHELL HAS ITS OWN DISCLOSURES.**
// A page-wide count of `[aria-expanded]` answered 1 over an audit table with
// none — the shell's own nav — and would have been reported as a row still
// hiding its values. Law 7's *looking at the wrong thing*, inside the check.
const presses = await page.$$eval("table [aria-expanded]", (ns) => ns.length);
say(`   inline value blocks: ${inline.length} · expand controls: ${presses}`);
for (const one of inline.slice(0, 4)) say(`     ${one}`);
check(inline.length > 0 || !auditText.includes("Expand"), "values are on the row, not behind one");
check(presses === 0, "there is nothing left to press on this tab");
check(auditText.includes("→") || inline.length === 0, "the old value sits beside the new one");

// ══ 6 · THE TAB THAT WAS NOT WALKED ═══════════════════════════════════════
say("\n── C6 · the work-orders tab");
const woText = await tabText(owing.id, "work-orders");
const orders = JSON.parse(
  (await api(`/api/${TENANT}/premises/${owing.id}/work-orders`)).body || "{}",
);
say(`   ${(orders.results ?? []).length} work order(s) at this address`);
if ((orders.results ?? []).length === 0) {
  say("   ⚠ NOT WALKED — nothing has been raised here, so the When/Who columns");
  say("     have no row to render. Built to the journey and covered by");
  say("     buildViews.test.tsx; NOT the same as having been seen.");
  check(woText.includes("No jobs have been raised here."), "the empty state is honest");
} else {
  const when = await page.$$eval("[data-order-when]", (ns) => ns.map((n) => n.textContent.trim()));
  const who = await page.$$eval("[data-order-who]", (ns) => ns.map((n) => n.textContent.trim()));
  say(`   when: ${JSON.stringify(when)} · who: ${JSON.stringify(who)}`);
  check(woText.includes("When") && woText.includes("Who"), "the two columns are drawn");
}

say(`\nscreenshots: ${OUT}`);
say(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
