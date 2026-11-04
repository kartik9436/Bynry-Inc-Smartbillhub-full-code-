// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 round 4 task 9 — the discounts web walk, STEP 9
//          (limits on REAL, ISSUED bill runs) and the DEF-RAT-9327 proof.
//          Its own file because a sibling lane edits `cr166_discwalk.mjs`
//          for steps 7, 8, 10 and 11 at the same time; the helpers are the
//          same shape as that file's.
// ───────────────────────────────────────────────────────
//
// Run AFTER `cr166_discwalk.mjs` phases 1,1.8finish,4,5 → 5back → 6 and the
// four issued runs `cr166_discwalk_world.py run …` (Oct, Nov, Dec 2026, Jan
// 2027). Every "must be true" is read three ways: on the bill's own screen
// (`/:tenant/billing/bills/:id`), from `GET /api/<tenant>/invoices/{id}`, and
// from `invoice_lines` in PostgreSQL.
//
//   BASE=http://127.0.0.1:5211 PGURL=postgres://postgres@127.0.0.1:55433/<db> \
//     OUT=<dir> WORLD=<dir>/world.json SHOTS=08-qa/discounts-2026-10-03/walk \
//     node 10-scripts/cr166_discwalk_step9.mjs
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5211";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr166-discwalk";
const SHOTS = process.env.SHOTS ?? OUT;
const PGURL = process.env.PGURL ?? "postgres://postgres@127.0.0.1:55433/sbh_discfix";
const WORLD = JSON.parse(readFileSync(process.env.WORLD ?? `${OUT}/world.json`, "utf8"));
const ACCTS = WORLD.ACCOUNTS_JSON;
const RESULTS = `${OUT}/results-step9.json`;
mkdirSync(SHOTS, { recursive: true });

const results = [];
function check(step, what, pass, evidence) {
  const row = { phase: 9, step, what, pass: Boolean(pass), evidence: String(evidence ?? "") };
  results.push(row);
  writeFileSync(RESULTS, JSON.stringify(results, null, 2));
  console.log(`${row.pass ? "PASS" : "FAIL"} 9.${step} ${what} — ${row.evidence.slice(0, 400)}`);
}
const dbRows = (sql) => {
  const out = execFileSync("psql", [PGURL, "-AtF", "|", "-c", sql], { encoding: "utf8" }).trim();
  return out === "" ? [] : out.split("\n").map((line) => line.split("|"));
};

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    if (!dir.startsWith("chromium")) continue;
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
      const candidate = join("/opt/pw-browsers", dir, sub);
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found");
}
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });
const settle = (ms = 900) => page.waitForTimeout(ms);
let shotNo = 0;
async function shot(caption) {
  await settle();
  shotNo += 1;
  const path = `${SHOTS}/discwalk_9_${shotNo}.png`;
  await page.screenshot({ path, fullPage: true });
  const size = statSync(path).size;
  console.log(`  [shot] discwalk_9_${shotNo}.png (${size} bytes) — ${caption}`);
  return path;
}
async function api(path) {
  return page.evaluate(async (p) => {
    const res = await fetch(`/api/${p}`, { credentials: "include" });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return { status: res.status, data };
  }, `${TENANT}/${path}`);
}
const text = async () => (await page.innerText("main").catch(() => "")).replace(/\s+/g, " ");

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

/** One issued bill: its id, its stored lines, its stored total. */
function bill(acctKey, periodEnd) {
  const [row] = dbRows(
    `select i.id, i.invoice_no, i.status, i.total from invoices i
      where i.account_id='${ACCTS[acctKey].id}' and i.period_end='${periodEnd}' order by i.created_at desc limit 1`,
  );
  const lines = dbRows(
    `select kind, description, amount from invoice_lines where invoice_id='${row[0]}' order by kind, description`,
  );
  return { id: row[0], number: row[1], status: row[2], total: Number(row[3]), lines };
}
const money = (n) => `$${Math.abs(n).toFixed(2)}`;
const discountLines = (b) => b.lines.filter((l) => l[0] === "discount").map((l) => [l[1], Number(l[2])]);

/** Open the bill on screen, photograph it, and read the API beside it. */
async function look(b, caption) {
  // `?tab=lines` — the bill's Charges tab, where each discount is its own
  // line (BR-RAT-068). The Document tab sums them into one breakdown figure.
  await page.goto(`${BASE}/${TENANT}/billing/bills/${b.id}?tab=lines`, { waitUntil: "networkidle" });
  await settle(1500);
  const path = await shot(caption);
  const body = await text();
  const served = (await api(`invoices/${b.id}`)).data ?? {};
  const servedLines = (served.lines ?? []).filter((l) => l.kind === "discount").map((l) => [l.description, Number(l.amount)]);
  return { path, body, served, servedLines };
}
const key = (rows) => rows.map((r) => `${r[0]}|${Number(r[1]).toFixed(2)}`).sort().join(";");
const sameLines = (a, b) => key(a) === key(b);

// ═══ 9.1 Senior with Autopay — the stacking order ════════════════════════════
{
  const b = bill("DW-SENIOR", "2026-10-15");
  const seen = await look(b, "Ruth Alvarez, October: Senior then Autopay");
  const d = discountLines(b);
  const senior = d.find((x) => x[0] === "Senior discount");
  const autopay = d.find((x) => x[0] === "Autopay discount");
  check(1, "Senior with Autopay: Senior 15% of $60.00 = −$9.00 first, then Autopay 0.5% of the $51.00 left = −$0.26 (not −$0.30 of $60.00); total $50.74 — stacking order applied",
    b.status === "issued" && senior?.[1] === -9 && autopay?.[1] === -0.26 && b.total === 50.74,
    `${b.number} ${b.status} · DB ${JSON.stringify(d)} · total ${b.total}`);
  check(1, "…the same on screen and from the API",
    seen.body.includes("Senior discount") && seen.body.includes("Autopay discount") && seen.body.includes("50.74") && sameLines(seen.servedLines, d),
    `screen has both lines and $50.74: ${seen.body.includes("50.74")} · API ${JSON.stringify(seen.servedLines)} · total ${seen.served.total}`);
}

// ═══ 9.2 CAP with Lifeline — never both ══════════════════════════════════════
const capMonths = ["2026-10-15", "2026-11-15", "2026-12-15", "2027-01-15"];
for (const [i, end] of capMonths.entries()) {
  const b = bill("DW-CAP", end);
  const d = discountLines(b);
  if (i === 0) {
    const seen = await look(b, "Carl Jensen, October: CAP only, never with Lifeline");
    check(2, "CAP with Lifeline (and Senior) — one exclusivity group: only CAP −$10.00 (the $50.00 floor stops the $25.00), never Lifeline beside it; total $50.00",
      b.status === "issued" && d.length === 1 && d[0][0] === "CAP credit" && d[0][1] === -10 && b.total === 50,
      `${b.number} · DB ${JSON.stringify(d)} · total ${b.total}`);
    check(2, "…the same on screen and from the API, and no Lifeline line anywhere",
      seen.body.includes("CAP credit") && !seen.body.includes("Lifeline") && seen.body.includes("50.00") && sameLines(seen.servedLines, d),
      `API ${JSON.stringify(seen.servedLines)} · Lifeline on screen: ${seen.body.includes("Lifeline")}`);
  } else {
    check(3, `CAP over the months: ${end} bill carries CAP −$10.00 and never Lifeline`,
      b.status === "issued" && d.length === 1 && d[0][0] === "CAP credit" && d[0][1] === -10,
      `${b.number} · DB ${JSON.stringify(d)} · total ${b.total}`);
  }
}
{
  const b = bill("DW-CAP", "2027-01-15");
  await look(b, "Carl Jensen, January 2027: CAP −$10.00 (fourth issued run)");
  const granted = dbRows(`select count(*), coalesce(sum(g.amount),0) from discount_grants g join discount_enrolments e on e.id=g.enrolment_id join discounts d on d.id=e.discount_id where d.code='CAP'`)[0];
  check(3, "CAP over 13 months: the $300.00 yearly cap depletes from issued bills (discount_grants written at issue)",
    Number(granted[0]) > 0,
    `discount_grants rows for CAP after FOUR issued runs: ${granted[0]} ($${granted[1]}) — KNOWN FAIL, DEF-2430 / DEF-BIL-5341 (issue writes no grant, so no cap or budget ever depletes)`);
}
{
  // The Overview / Accounts tab read the same grants
  const capId = dbRows(`select id from discounts where code='CAP'`)[0][0];
  const detail = (await api(`discounts/${capId}`)).data ?? {};
  await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${capId}?tab=accounts`, { waitUntil: "networkidle" });
  await shot("CAP › Accounts after four issued runs: Granted still a dash");
  check(3, "CAP › Granted this month after four issued runs reads what was granted",
    detail.granted_this_month !== null && detail.granted_this_month !== undefined,
    `granted_this_month ${detail.granted_this_month} — KNOWN FAIL (DEF-2430), not re-reported`);
}

// ═══ DEF-RAT-9327 — the named-code waiver on issued bills ════════════════════
for (const end of ["2026-10-15", "2027-01-15"]) {
  const b = bill("DW-MEDIC", end);
  const d = discountLines(b);
  const seen = end === "2026-10-15" ? await look(b, "Mia Okafor, October: Lead line waiver takes the $8.00 base off") : null;
  check("9327", `Mia Okafor ${end}: a bill exists (no stopped account), Lead line waiver −$8.00 on the $8.00 BASE-W line, total $52.00 (DEF-RAT-9327)`,
    b.status === "issued" && d.length === 1 && d[0][0] === "Lead line waiver" && d[0][1] === -8 && b.total === 52 && b.lines.some((l) => l[0] === "base" && Number(l[2]) === 8),
    `${b.number} · DB ${JSON.stringify(b.lines)} · total ${b.total}` + (seen ? ` · screen $52.00: ${seen.body.includes("52.00")} · API ${JSON.stringify(seen.servedLines)}` : ""));
}
const breaks = dbRows(`select count(*) from bill_run_breaks`)[0][0];
check("9327", "no bill run stopped any account across the four issued runs", Number(breaks) === 0, `bill_run_breaks rows: ${breaks}`);

// ═══ DEF-RAT-9327 — a waiver on a FEE code is refused at Approve ═══════════
// The engine never discounts a fee (decision log 2026-08-22), so a waiver
// naming the connection fee `CONN` would take $0.00 off every bill. It is
// refused where the clerk presses Approve, by name, in the catalogue's words.
{
  const made = await page.evaluate(async (t) => {
    const res = await fetch(`/api/${t}/discounts`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: "CONNWAIVE", name: "Connection fee waiver", program_owner: "billing",
        discount_type: "charge_waiver", value: "0", applies_to: "named_codes",
        applies_to_charge_codes: ["CONN"], effective_from: "2026-10-01",
        enrolment_mode: "apply_and_approve", verification_method: "one_time_proof",
        eligibility: "medical_equipment",
      }),
    });
    return { status: res.status, data: await res.json().catch(() => null) };
  }, TENANT);
  const id = made.data?.id;
  await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${id}`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Submit for approval", exact: true }).click();
  await settle(1500);
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await settle(600);
  await page.locator("[role=dialog], [role=alertdialog]").getByRole("button", { name: /^Approve/ }).click();
  await settle(2000);
  await shot("A waiver naming the connection fee: Approve refused by name");
  const shown = ((await page.innerText("[role=dialog], [role=alertdialog]").catch(() => "")) || (await text())).replace(/\s+/g, " ");
  const status = (await api(`discounts/${id}`)).data?.status;
  check("9327", "a waiver naming the connection fee CONN is refused at Approve with \"CONN can't be discounted. Choose a base charge code.\" and stays Waiting approval",
    made.status === 201 || made.status === 200 ? shown.includes("CONN can't be discounted") && status === "waiting_approval" : false,
    `create ${made.status} · served ${status} · on screen: ${shown.slice(0, 200)}`);
}

// ═══ 9.4 Garden budget ═══════════════════════════════════════════════════════
{
  const b = bill("DW-GARDEN", "2026-10-15");
  await look(b, "Gail Moreno, October: no Garden allowance (it cannot go live)");
  const status = dbRows(`select v.status from discount_versions v join discounts d on d.id=v.discount_id where d.code='GARDEN'`).map((r) => r[0]);
  check(4, "Garden budget: the allowance goes live, deducts 2 kgal before pricing and suspends when its $500.00 budget runs out",
    status.includes("active") && discountLines(b).length > 0,
    `GARDEN versions ${JSON.stringify(status)} · Gail's October bill ${JSON.stringify(b.lines)} total ${b.total} — PENDING WITH THE PO (BR-RAT-962: a usage allowance cannot be priced; approval refuses it), not re-reported`);
}

// ═══ the rest of the October run, for the record ═════════════════════════════
for (const [key, expect] of [["DW-PLAIN", [["Veteran discount", -0.9]]], ["DW-CITY", [["Municipal account", -5]]], ["DW-OFF", []]]) {
  const b = bill(key, "2026-10-15");
  check(5, `${ACCTS[key].number} October: ${expect.length ? expect.map((e) => `${e[0]} ${money(e[1])} off`).join(", ") : "no discount (off plan)"}`,
    sameLines(discountLines(b), expect), `${b.number} · DB ${JSON.stringify(discountLines(b))} · total ${b.total}`);
}

await browser.close();
