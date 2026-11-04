// ── Trace ──────────────────────────────────────────────
// Change:   the uniform correction verbs. PO ruling 2026-09-17: *"please fix
//           all these"*.
// Defects:  DEF-RAT-5709 — a discount could not be edited at all, not even a
//           draft nobody had submitted.
// Rules:    BR-RAT-1016 · BR-RAT-104 · BR-RAT-077 / BR-RAT-109 (untouched) ·
//           CLAUDE.md hard-won law 6 (NO GATE READS RENDERED OUTPUT) · law 2 in
//           both directions · 13-change-process.md's CLOSURE BAR, PO 2026-08-18
// ───────────────────────────────────────────────────────
/**
 * Walk the discount's three verbs IN A REAL BROWSER.
 *
 *     BASE=http://127.0.0.1:8580 node 10-scripts/br_rat_1016_discount_verbs_walkthrough.mjs
 *
 * ⚠ **WHY THE 39 CASES DO NOT REPLACE IT.** They prove each verb refuses and
 * accepts what it should, and that the pure chooser picks the right one. None
 * of them can prove the DOOR is reachable by a person on the page it lives on,
 * which is exactly what hard-won law 2 is about, and none can prove the two
 * routes are mounted at the addresses the client builds.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8580";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const fail = (m) => { problems.push(m); console.log("  x " + m); };
const ok = (m) => console.log("  ok " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
console.log(`signed in as ${EMAIL}`);

const detailOf = async (id) =>
  (await (await ctx.request.get(`${BASE}/api/${TENANT}/discounts/${id}`)).json());

async function survey() {
  const list = await (await ctx.request.get(`${BASE}/api/${TENANT}/discounts?per=100`)).json();
  const rows = list.results ?? list;
  let live = null;
  let draft = null;
  for (const row of rows) {
    const d = await detailOf(row.id);
    if (d.version_status === "active" && live === null) live = d;
    if (d.version_status === "draft" && d.version_submitted !== true && draft === null) draft = d;
  }
  return { count: rows.length, live, draft };
}

/**
 * ⚠ **THE FIRST RUN OF THIS FILE PRINTED `WALK CLEAN` OVER A TENANT WITH ZERO
 * DISCOUNTS**, having walked nothing at all. That is hard-won law 7's
 * *reporting zero over a scope it silently excludes*: the script was not lying,
 * and a reader could not tell an empty tenant from a working product. So it
 * SEEDS what it needs, and every skipped verb below is a FAILURE rather than a
 * line of prose.
 */
async function seedDiscount(code, { activate }) {
  const created = await ctx.request.post(`${BASE}/api/${TENANT}/discounts`, {
    data: {
      code,
      name: `${code} walkthrough programme`,
      discount_type: "percentage",
      value: "15",
      applies_to: "whole_bill",
      effective_from: "2026-08-01",
      budget_cap: "500",
    },
  });
  if (!created.ok()) {
    fail(`could not seed ${code} (status ${created.status()}, ${(await created.text()).slice(0, 200)})`);
    return null;
  }
  const row = await created.json();
  const detail = await detailOf(row.id);
  if (!activate) {
    return detail;
  }
  for (const act of ["submit", "approve", "activate"]) {
    const res = await ctx.request.post(
      `${BASE}/api/${TENANT}/discounts/${row.id}/versions/${detail.version_id}/${act}`,
      { data: {} },
    );
    if (!res.ok()) {
      fail(`could not ${act} ${code} (status ${res.status()})`);
      return null;
    }
  }
  return await detailOf(row.id);
}

let { count, live, draft } = await survey();
console.log(`catalogue: ${count} discount(s)`);
const stamp = Date.now().toString().slice(-5);
if (live === null) {
  live = await seedDiscount(`WLKA${stamp}`, { activate: true });
  console.log(`seeded a LIVE discount: ${live ? live.code : "FAILED"}`);
}
if (draft === null) {
  draft = await seedDiscount(`WLKD${stamp}`, { activate: false });
  console.log(`seeded a DRAFT discount: ${draft ? draft.code : "FAILED"}`);
}
console.log(`live: ${live ? live.code : "none"} · never-submitted draft: ${draft ? draft.code : "none"}`);

// ── 1 · THE IDENTITY, which had no route at all ────────────────────────────
if (live ?? draft) {
  const subject = live ?? draft;
  console.log(`\n1 · the identity of ${subject.code} — verb 1, any state`);
  const renamed = await ctx.request.fetch(`${BASE}/api/${TENANT}/discounts/${subject.id}`, {
    method: "PATCH", data: { name: `${subject.name} (walk)` },
  });
  if (renamed.ok()) { ok("the programme name can be fixed"); }
  else { fail(`renaming refused (status ${renamed.status()})`); }
  await ctx.request.fetch(`${BASE}/api/${TENANT}/discounts/${subject.id}`, {
    method: "PATCH", data: { name: subject.name },
  });
  const worth = await ctx.request.fetch(`${BASE}/api/${TENANT}/discounts/${subject.id}`, {
    method: "PATCH", data: { value: "99" },
  });
  if (!worth.ok()) { ok("what it is WORTH is still refused on this route"); }
  else { fail("the identity route accepted a VALUE — the priced agreement is open"); }
}

// ── 2 · A NEVER-SUBMITTED DRAFT, edited in place ───────────────────────────
if (draft) {
  console.log(`\n2 · ${draft.code}'s draft version — verb 1, in place`);
  const before = draft.value;
  const edited = await ctx.request.fetch(
    `${BASE}/api/${TENANT}/discounts/${draft.id}/versions/${draft.version_id}`,
    { method: "PATCH", data: { value: "2" } },
  );
  if (edited.ok()) { ok(`the draft's value moved ${before} -> 2 with no reason and no new version`); }
  else { fail(`the draft refused an in-place edit (status ${edited.status()}, ${(await edited.text()).slice(0,200)})`); }
  const after = await detailOf(draft.id);
  if (after.version_no === draft.version_no) { ok("no second version was minted"); }
  else { fail(`the version number moved ${draft.version_no} -> ${after.version_no}`); }
  await ctx.request.fetch(
    `${BASE}/api/${TENANT}/discounts/${draft.id}/versions/${draft.version_id}`,
    { method: "PATCH", data: { value: before } },
  );
} else {
  fail("verb 1 on a version was NOT walked — a walk that exercises nothing must not read as a pass");
}

// ── 3 · A LIVE VERSION, corrected over the SAME window ─────────────────────
if (live) {
  console.log(`\n3 · ${live.code} is live — the correction door`);
  await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${live.id}`, { waitUntil: "networkidle" });
  const door = page.getByRole("button", { name: "Fix this version" });
  if (await door.count()) { ok("the page offers `Fix this version`"); }
  else { fail("a LIVE discount offers no correction door — the verb has no way in (law 2)"); }

  const refused = await ctx.request.fetch(
    `${BASE}/api/${TENANT}/discounts/${live.id}/versions/${live.version_id}/corrections`,
    { method: "POST", data: { value: "1.5" } },
  );
  if (!refused.ok()) { ok("a correction with no reason is refused"); }
  else { fail("a correction with no reason was accepted"); }

  const windowWas = live.effective_from;
  const done = await ctx.request.fetch(
    `${BASE}/api/${TENANT}/discounts/${live.id}/versions/${live.version_id}/corrections`,
    {
      method: "POST",
      data: {
        value: "1.5",
        effective_from: "2099-01-01",
        reason: "Walkthrough: proving the window is copied and not taken from the payload.",
      },
    },
  );
  const saved = await done.json();
  if (done.ok()) { ok(`the correction is accepted and is now version ${saved.version_no}`); }
  else { fail(`the correction was refused (status ${done.status()}, ${JSON.stringify(saved).slice(0,300)})`); }
  if (done.ok() && saved.effective_from === windowWas) {
    ok(`THE WINDOW DID NOT MOVE: still ${windowWas}, though the payload asked for 2099-01-01`);
  } else if (done.ok()) {
    fail(`the window MOVED to ${saved.effective_from} — a correction became a backdated change`);
  }
  if (done.ok() && saved.corrects === live.version_id) { ok("the two rows are linked"); }
  else if (done.ok()) { fail("the correction does not point at the row it corrects"); }
  if (done.ok() && saved.issued_bills_unchanged === true && saved.open_question === "OQ-310") {
    ok("the response says issued bills are unchanged and names OQ-310");
  } else if (done.ok()) { fail("the response does not name the unruled half"); }

  const again = await detailOf(live.id);
  if (again.version_status === "active" && again.version_corrects === live.version_id) {
    ok("the detail now reads the correction as the version in force");
  } else {
    fail(`the detail reads ${again.version_status} / corrects=${again.version_corrects}`);
  }
} else {
  fail("verb 2 was NOT walked — a walk that exercises nothing must not read as a pass");
}

console.log(`\n${problems.length === 0 ? "WALK CLEAN" : problems.length + " PROBLEM(S)"}`);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
