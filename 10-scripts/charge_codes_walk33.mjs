// ── Trace ──────────────────────────────────────────────
// Request:  PO 2026-10-01, verbatim: "we have 33 charge codes. can you do web walk
//           for all 33 cases - end to end as a clark and see theya re setting
//           correctly - also do updates web walk on all 33 cases … data is saved
//           correctly in update cases - obne record should be send to billing and
//           change history should be available; flat rate and multiple rate cases
//           are correctly saved in dB", and "do abse charge codes for all 11
//           utility services - customer type and asset sized based - real examples".
// Rules:    decision log 2026-10-01 rows whose last column reads "charge-code
//           redesign" (dated prices, logical kill, flat = one All-sizes row, the
//           free-codes picker, Effective from/to, three kinds, penalty by class,
//           entered when used) · CR-156-BRC10 · gate G141 (one row per lookup).
// ───────────────────────────────────────────────────────
// A clerk's walk, in Chromium at 1440, over EVERY charge code a provisioned tenant
// with all eleven services switched on holds, in three phases:
//
//   update  every SEEDED code is repriced through Edit from a future Effective
//           from (CHANGE_FROM); the old row must be closed the day before and
//           killed — never deleted or overwritten — the new row open, the audit
//           tab and `audit_log` must carry it, `charge_prices.price_on_date` must
//           answer exactly ONE row before and after, and the rate schedule /
//           plan / one-time bill preview must bill the right price per date.
//   add     every seeded code gets a TWIN minted in Settings (`A-<code>`) and
//           configured through Add with the same kind, service, class and
//           prices; the database must hold exactly the rows typed (flat = ONE
//           All-sizes row; sized = one row per size). Base twins are retired
//           afterwards through the screen so they do not make every bill of
//           their service ambiguous (two base codes for one class).
//   new     a NEW base code for each of the eleven services (water, electric and
//           trash also split Residential / Commercial), real sizes and figures,
//           added, checked, repriced and checked again; the seeded base codes of
//           the service are retired first so the new ones are what billing reads.
//
// The database half is `10-scripts/ccwalk_charge_code_db_check.py` (the real
// `price_on_date`, never a copy). Results: <SHOTS>/results.json; the page the PO
// reads, RESULTS.md, is written from it by `10-scripts/ccwalk_results_md.py <SHOTS>`.
//
//   BASE=http://127.0.0.1:<spa> SHOTS=<dir> DATABASE_URL=postgres://…/<walk db> \
//   PY=/tmp/venv_a5c/bin/python PHASES=update,add,new [ONLY=CODE1,CODE2] \
//   E2E_CHROMIUM_EXECUTABLE=<chrome> node 10-scripts/charge_codes_walk33.mjs
//
// Needs a PRIVATE database: `seed_demo`, all eleven services switched on
// (PUT /settings/services/<s> {"enabled": true}), then
// `manage.py load_sample_data --tenant brazosbend`. It writes prices and codes.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
const require = createRequire(`${REPO}/07-frontend/package.json`);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8978";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS ?? `${REPO}/08-qa/screens/charge-codes-walk33-2026-10-01`;
const PY = process.env.PY ?? "python3";
const PHASES = (process.env.PHASES ?? "update,add,new").split(",");
const ONLY = process.env.ONLY ? process.env.ONLY.split(",") : null;
mkdirSync(SHOTS, { recursive: true });

// The tenant's today is 2026-10-01 on the walk database.
const ADD_FROM = "2026-10-01";
const CHANGE_FROM = "2026-11-01";
const CLOSED_TO = "2026-10-31";
const BEFORE = "2026-10-15";
const AFTER = "2026-11-15";
const REASON = "Board approved price review, walk 33";

const RESULTS_FILE = `${SHOTS}/results.json`;
const results = existsSync(RESULTS_FILE) ? JSON.parse(readFileSync(RESULTS_FILE, "utf8")) : {};
const save = () => writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 1));

// ── helpers ─────────────────────────────────────────────────────────────────
const money = (v) => (v === null || v === undefined ? null : Number(v).toFixed(2));
const up = (v, by = 1) => (Number(v) + by).toFixed(2);
const slug = (code) => code.replace(/[^A-Za-z0-9-]/g, "_");

// ONE Django process for the whole walk (`--serve`): a request per line, a JSON
// answer per line, every answer read fresh from the database.
const helper = spawn(PY, [`${REPO}/10-scripts/ccwalk_charge_code_db_check.py`, "--tenant", TENANT, "--serve"], {
  env: { ...process.env, DJANGO_SETTINGS_MODULE: "config.settings.local", JOBS_EAGER: "false" },
  stdio: ["pipe", "pipe", "inherit"],
});
const waiting = [];
createInterface({ input: helper.stdout }).on("line", (line) => {
  if (!line.startsWith("{")) return;
  const next = waiting.shift();
  if (next) next(JSON.parse(line));
});
function ask(text) {
  return new Promise((done) => {
    waiting.push(done);
    helper.stdin.write(`${text}\n`);
  });
}
function dbCheck(codes, dates = [BEFORE, AFTER]) {
  return ask(`${codes.join(",")}|${dates.join(",")}`);
}

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);
await page.goto(`${BASE}/${TENANT}/signin`);
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
  page.click('button[type="submit"]'),
]);
const api = (p) => `${BASE}/api/${TENANT}${p}`;
async function get(p) {
  const r = await ctx.request.get(api(p));
  if (!r.ok()) throw new Error(`GET ${p} → ${r.status()} ${(await r.text()).slice(0, 300)}`);
  return r.json();
}
async function post(p, data) {
  const r = await ctx.request.post(api(p), { data });
  let body = null;
  try { body = await r.json(); } catch { body = null; }
  return { status: r.status(), body };
}
async function chargeByCode(code) {
  const list = await get(`/charges?q=${encodeURIComponent(code)}&per=50&f.status=all`);
  const row = list.results.find((one) => one.code === code);
  if (!row) return null;
  return get(`/charges/${row.id}`);
}
async function shot(name) {
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${SHOTS}/${name}.jpg`, fullPage: true, type: "jpeg", quality: 70 });
}
async function cont() {
  await page.getByRole("button", { name: /^Continue/ }).click();
  await page.waitForTimeout(500);
}
async function setDate(id, value) {
  await page.locator(`#${id}`).fill(value);
}
async function pickCode(code) {
  await page.locator("#cc-code").click();
  await page.getByRole("option", { name: new RegExp(`^${code.replace(/[-]/g, "\\-")} ·`) }).click();
}
/** What the pricing step draws: its inputs, by data-cell. */
async function pricingCells() {
  return page.locator('[data-step="pricing"] [data-cell]').evaluateAll((els) =>
    els.map((e) => ({ cell: e.getAttribute("data-cell"), value: e.value ?? "", tag: e.tagName })),
  );
}
function shapeOfCells(cells) {
  const names = cells.map((c) => c.cell);
  if (names.length === 0) return "entered";
  if (names.some((n) => n.startsWith("percent-"))) return names.some((n) => n.startsWith("class-")) ? "penalty-class" : "penalty";
  if (names.some((n) => n.startsWith("size-"))) return "sized";
  if (names.some((n) => n.startsWith("class-"))) return "class";
  return "flat";
}
function result(key, base) {
  results[key] = { ...(results[key] ?? {}), ...base };
  return results[key];
}
function note(row, text) {
  row.notes = [...(row.notes ?? []), text];
  console.log(`    · ${text}`);
}

// ── one-time bill previews ──────────────────────────────────────────────────
const previewAccounts = {};
const estimatesFor = {};
async function preview(accountId, body) {
  const cacheKey = `${accountId}|${(body.scope_services ?? []).join(",")}`;
  if (estimatesFor[cacheKey] && body.kind === "interim") {
    // The account's meters are known: ask for their estimates in one call.
    const res = await post("/billing/one-time/preview", { account_id: accountId, due_days: 21, ...body, readings: estimatesFor[cacheKey] });
    if (res.status === 200) return res;
  }
  let res = await post("/billing/one-time/preview", { account_id: accountId, due_days: 21, ...body });
  const rows = res.body?.readings?.rows ?? [];
  if (res.status === 200 && rows.some((row) => row.status === "waiting")) {
    // Step 2's "bill on the meter's own estimate" (DEF-BIL-8562): it reaches each
    // part of a bill cut at a price change, which one typed reading cannot.
    const serviceOf = {};
    for (const s of res.body?.services ?? []) for (const a of s.assets ?? []) serviceOf[a.asset_id] = s.service;
    const readings = rows
      .filter((row) => row.status === "waiting")
      .map((row) => ({ asset_id: row.asset_id, service: serviceOf[row.asset_id] ?? "", role: "estimate" }));
    estimatesFor[cacheKey] = readings;
    res = await post("/billing/one-time/preview", { account_id: accountId, due_days: 21, ...body, readings });
  }
  return res;
}
function lines(res) {
  return (res.body?.bill?.groups ?? []).flatMap((g) =>
    g.lines.map((l) => ({ ...l, period_start: g.period_start, period_end: g.period_end })),
  );
}
let accountMap = null;
async function accountFor(service, cls) {
  const key = `${service}|${cls ?? "*"}`;
  if (key in previewAccounts) return previewAccounts[key];
  if (accountMap === null) {
    accountMap = await ask("accounts");
  }
  const all = (await get("/accounts?per=100")).results;
  const ids = accountMap[`${service}|${cls ?? "residential"}`] ?? [];
  const list = ids.map((id) => all.find((a) => a.id === id)).filter((a) => a && a.status === "active");
  for (const account of list.slice(0, 6)) {
    const res = await preview(account.id, { kind: "interim", period_start: "2026-10-01", period_end: "2026-10-31", bill_date: "2026-11-01", scope_services: service === "sewer" ? ["water", "sewer"] : [service] });
    if (res.status !== 200) continue;
    // Billed on this account (a $0.00 base prints no line, so the service's own
    // status decides, not the presence of a base line).
    if ((res.body?.services ?? []).some((s) => s.service === service && ["billed", "follows_basis"].includes(s.status))) {
      previewAccounts[key] = account;
      return account;
    }
  }
  previewAccounts[key] = null;
  return null;
}

// ── checks ──────────────────────────────────────────────────────────────────
const keyOf = (r) => `${r.size_class}|${r.customer_class ?? ""}`;
function liveRows(check) {
  return check.rows.filter((r) => !r.killed);
}
/** After an UPDATE: nothing deleted, the changed key closed + killed, a new open row. */
function checkUpdateRows(before, after, changedKeys, newValues, row) {
  const problems = [];
  const afterIds = new Set(after.rows.map((r) => r.id));
  for (const r of before.rows) if (!afterIds.has(r.id)) problems.push(`row ${r.size_class}/${r.customer_class ?? "every"} DELETED`);
  for (const key of changedKeys) {
    const old = before.rows.find((r) => keyOf(r) === key && !r.killed);
    const oldNow = old && after.rows.find((r) => r.id === old.id);
    if (old && !oldNow) continue;
    if (old) {
      if (!oldNow.killed) problems.push(`${key}: old row not killed`);
      if (oldNow.effective_to !== CLOSED_TO) problems.push(`${key}: old row ends ${oldNow.effective_to}, not ${CLOSED_TO}`);
      if (money(oldNow.amount) !== money(old.amount) || money(oldNow.percent) !== money(old.percent)) problems.push(`${key}: old row OVERWRITTEN`);
    }
    const fresh = after.rows.filter((r) => keyOf(r) === key && !r.killed && r.effective_from === CHANGE_FROM);
    if (fresh.length !== 1) problems.push(`${key}: ${fresh.length} new open rows from ${CHANGE_FROM}`);
    else {
      const want = newValues[key];
      const got = fresh[0].percent !== null ? `${money(Number(fresh[0].percent) * 100)}%/${money(fresh[0].min_amount)}` : money(fresh[0].amount);
      if (want !== undefined && got !== want) problems.push(`${key}: new row ${got}, typed ${want}`);
      if (fresh[0].effective_to !== null) problems.push(`${key}: new row has an end ${fresh[0].effective_to}`);
    }
  }
  for (const r of before.rows.filter((x) => !x.killed && !changedKeys.includes(keyOf(x)))) {
    const same = after.rows.find((x) => x.id === r.id);
    if (!same || same.killed || money(same.amount) !== money(r.amount)) problems.push(`${keyOf(r)}: an UNCHANGED row moved`);
  }
  if (problems.length) note(row, `DB after update: ${problems.join("; ")}`);
  return problems.length === 0;
}
/** price_on_date answers ONE row per key on each date, with the right figure. */
function checkOneRow(check, expectBefore, expectAfter, row) {
  const problems = [];
  for (const [day, expect] of [[BEFORE, expectBefore], [AFTER, expectAfter]]) {
    for (const entry of check.lookups[day] ?? []) {
      const key = `${entry.size_class}|${entry.customer_class ?? ""}`;
      if (!(key in expect)) continue;
      if (entry.rows_in_force !== 1) problems.push(`${day} ${key}: ${entry.rows_in_force} rows in force`);
      const got = entry.terms ? `${money(Number(entry.terms.percent) * 100)}%/${money(entry.terms.minimum)}` : money(entry.amount);
      if (got !== expect[key]) problems.push(`${day} ${key}: lookup ${got} (${entry.refusal ?? "priced"}), expected ${expect[key]}`);
    }
  }
  if (problems.length) note(row, `price_on_date: ${problems.join("; ")}`);
  return problems.length === 0;
}
const valueOf = (r) => (r.percent !== null ? `${money(Number(r.percent) * 100)}%/${money(r.min_amount)}` : money(r.amount));
function valuesOn(check, day) {
  const out = {};
  for (const r of check.rows) {
    if (r.effective_from <= day && (r.effective_to === null || day <= r.effective_to)) out[keyOf(r)] = valueOf(r);
  }
  return out;
}

// ── walking a code ──────────────────────────────────────────────────────────
async function openEdit(id, code) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${id}/edit`);
  await page.locator("#cc-code").waitFor();
  await page.waitForFunction((want) => document.querySelector("#cc-code")?.value === want, code, { timeout: 30000 });
  await page.waitForTimeout(600);
}
/** Change the step-2 figures the way a clerk would: the FIRST priced row (or the one amount) +$1.00, a penalty +0.25 % and +$1.00. */
async function repriceOnStep2(shape) {
  const cells = await pricingCells();
  const changed = {};
  if (shape === "penalty" || shape === "penalty-class") {
    const pct = cells.find((c) => c.cell === "percent-0");
    const min = cells.find((c) => c.cell === "minimum-0");
    const newPct = (Number(pct.value || 0) + 0.25).toFixed(2);
    const newMin = up(min.value || 0);
    await page.locator('[data-cell="percent-0"]').fill(newPct);
    await page.locator('[data-cell="minimum-0"]').fill(newMin);
    const cls = shape === "penalty-class" ? cells.find((c) => c.cell === "class-0").value : "";
    changed[`All sizes|${cls}`] = `${newPct}%/${newMin}`;
    return changed;
  }
  const amountCells = cells.filter((c) => c.cell.startsWith("amount-") && c.value.trim() !== "");
  if (amountCells.length === 0) return changed;
  const first = amountCells[0];
  const index = first.cell.split("-")[1];
  const value = up(first.value);
  await page.locator(`[data-cell="amount-${index}"]`).fill(value);
  const size = shape === "sized" ? cells.find((c) => c.cell === `size-${index}`).value : "All sizes";
  const cls = shape === "class" ? cells.find((c) => c.cell === `class-${index}`).value : "";
  changed[`${size}|${cls}`] = value;
  return changed;
}

async function impactBase(code, check, row, changedKeys) {
  // The rate schedules whose Rates tab reads this code as its base.
  const schedules = (await get(`/rate-schedules?per=200&f.service=${check.service}`)).results ?? [];
  let shown = 0;
  let firstId = null;
  const problems = [];
  for (const s of schedules) {
    const rates = await get(`/rate-schedules/${s.id}/rates`).catch(() => null);
    const codes = (rates?.base_codes ?? []).map((one) => one.code);
    if (!rates || !(codes.includes(code) || rates.base_code?.code === code)) continue;
    shown += 1;
    firstId = firstId ?? s.id;
    const todays = valuesOn(check, ADD_FROM);
    const later = valuesOn(check, AFTER);
    for (const br of rates.base_rows.filter((one) => one.code === undefined || one.code === code)) {
      // DEF-RAT-8846 — a size whose price changes from CHANGE_FROM serves it as next.
      const k = `${br.size_class ?? "All sizes"}|`;
      if (changedKeys.includes(k)) {
        const wantNext = later[k];
        if (money(br.next_amount) !== wantNext || br.next_effective_from !== CHANGE_FROM) {
          problems.push(`${s.name} ${br.size_name ?? "All sizes"} next ${money(br.next_amount) ?? "—"} from ${br.next_effective_from ?? "—"}, expected ${wantNext} from ${CHANGE_FROM}`);
        }
      }
    }
    for (const br of rates.base_rows.filter((one) => one.code === undefined || one.code === code)) {
      const key = `${br.size_class ?? "All sizes"}|`;
      const want = todays[key] ?? todays[`${br.size_class ?? "All sizes"}|${(check.applies_to_customer_classes ?? [])[0] ?? ""}`];
      if (want === undefined) continue;
      const got = money(br.base_charge ?? br.amount ?? br.price);
      if (got !== null && got !== want) problems.push(`${s.name} ${br.size_name ?? "All sizes"} shows ${got}, today's price ${want}`);
      if (changedKeys.includes(key) && br.effective_to !== undefined && br.effective_to !== CLOSED_TO) {
        problems.push(`${s.name} ${br.size_name ?? "All sizes"} To ${br.effective_to ?? "—"}, expected ${CLOSED_TO}`);
      }
    }
  }
  if (firstId) {
    await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${firstId}?tab=rates`);
    await page.waitForTimeout(2500);
    await shot(`${slug(code)}-U4-schedule-rates`);
    // DEF-RAT-8846 — the Next change tile names a scheduled base price.
    const tile = await page.locator("[data-next-base-price]").innerText().catch(() => null);
    if (changedKeys.length) note(row, `Next change tile: ${tile ?? "None"}`);
  }
  const plans = await get(`/charges/${check.id}/plans`).catch(() => ({ count: 0 }));
  note(row, `rate schedules reading it as base: ${shown}; plans reached: ${plans.count ?? 0}`);
  if (problems.length) note(row, `schedule Rates tab: ${problems.join("; ")}`);
  return problems.length === 0;
}

/** A bill preview over October, over November, and across the change: one base line per part at that part's price. */
async function previewBase(code, check, row) {
  const cls = (check.applies_to_customer_classes ?? [])[0] ?? null;
  const account = await accountFor(check.service, cls ?? "residential");
  if (!account) {
    const ids = accountMap?.[`${check.service}|${cls ?? "residential"}`] ?? [];
    let why = "";
    if (ids.length) {
      const res = await preview(ids[0], { kind: "interim", period_start: "2026-10-01", period_end: "2026-10-31", bill_date: "2026-11-01", scope_services: [check.service] });
      why = res.status === 200 ? "" : ` — the first one is refused: ${(res.body?.params?.detail ?? res.body?.message_key ?? res.status).toString().slice(0, 160)}`;
    }
    note(row, `no ${cls ?? "any-class"} account on ${check.service} could be billed (${ids.length} on the service)${why}`);
    return null;
  }
  // One service on the bill (scope_services): this code's base, nothing else's setup.
  // Sewer is billed as a share of water, so water rides along on its bill.
  const one = { scope_services: check.service === "sewer" ? ["water", "sewer"] : [check.service] };
  const oct = await preview(account.id, { kind: "interim", period_start: "2026-10-01", period_end: "2026-10-31", bill_date: "2026-11-01", ...one });
  const nov = await preview(account.id, { kind: "interim", period_start: "2026-11-01", period_end: "2026-11-30", bill_date: "2026-12-01", ...one });
  const span = await preview(account.id, { kind: "interim", period_start: "2026-10-16", period_end: "2026-11-15", bill_date: "2026-11-16", ...one });
  const problems = [];
  const base = (res) => lines(res).filter((l) => l.service === check.service && l.charge === "base");
  for (const [label, res] of [["Oct", oct], ["Nov", nov], ["16 Oct–15 Nov", span]]) {
    if (res.status !== 200) problems.push(`${label} preview refused: ${res.body?.params?.detail ?? res.body?.message_key ?? res.status}`.slice(0, 300));
  }
  if (problems.length) {
    note(row, `bill preview (${account.account_no}): ${problems.join("; ")}`);
    return false;
  }
  const before = new Set(Object.values(valuesOn(check, BEFORE)));
  const after = new Set(Object.values(valuesOn(check, AFTER)));
  // The base as billed: its own `base` lines, or — on a count-based capacity
  // service (trash, fire) over a whole month — folded into the per-size line,
  // where each size's `base_each × count` is in the line's breakdown.
  const baseOf = (res) => {
    const own = base(res);
    if (own.length) {
      return { rates: own.map((l) => money(l.rate)), total: own.reduce((t, l) => t + Number(l.amount), 0), lines: own, folded: false };
    }
    const sized = lines(res).filter((l) => l.service === check.service && l.charge === "per_asset" && Array.isArray(l.breakdown) && l.breakdown.length);
    const bd = sized[0]?.breakdown ?? [];
    return {
      rates: bd.map((b) => money(b.base_each)),
      total: bd.reduce((t, b) => t + Number(b.base_each) * Number(b.count), 0),
      lines: [],
      folded: bd.length > 0,
    };
  };
  const o = baseOf(oct);
  const n = baseOf(nov);
  const x = baseOf(span);
  for (const r of o.rates) if (!before.has(r)) problems.push(`Oct base ${r} is not an October price (${[...before].join(", ")})`);
  for (const r of n.rates) if (!after.has(r)) problems.push(`Nov base ${r} is not a November price (${[...after].join(", ")})`);
  // Across the change the bill is cut at CHANGE_FROM (decision log 2026-10-01 (5)):
  // 16/31 of October's base and 15/30 of November's, one figure per part.
  const wantTotal = Math.round(o.total * 16 / 31 * 100) / 100 + Math.round(n.total * 15 / 30 * 100) / 100;
  if (Math.abs(x.total - wantTotal) > 0.021) {
    problems.push(`16 Oct–15 Nov: base ${x.total.toFixed(2)}, expected ${wantTotal.toFixed(2)} (16/31 × ${o.total.toFixed(2)} + 15/30 × ${n.total.toFixed(2)})`);
  }
  if (!o.folded && !n.folded && x.lines.length !== o.lines.length + n.lines.length) {
    problems.push(`16 Oct–15 Nov: ${x.lines.length} base lines, expected ${o.lines.length + n.lines.length} (one per part)`);
  }
  const fmt = (b) =>
    b.folded
      ? `in the per-size line ${b.rates.join("/")} each = ${b.total.toFixed(2)}`
      : b.lines.map((l) => `${money(l.rate)}×${l.quantity}=${money(l.amount)}`).join(" + ") || "no base line";
  note(row, `bill preview ${account.account_no}: Oct ${fmt(o)} · Nov ${fmt(n)} · 16 Oct–15 Nov ${fmt(x)} (total ${x.total.toFixed(2)})`);
  const zero = (set) => [...set].every((v) => v === "0.00");
  if (o.rates.length === 0 && !zero(before)) problems.push("no base billed in October");
  if (n.rates.length === 0 && !zero(after)) problems.push(`no base billed in November at ${[...after].join(", ")}`);
  if (problems.length) note(row, `bill preview: ${problems.join("; ")}`);
  return problems.length === 0;
}

/** A fee bill before and after the change: ONE line, at the price in force on the bill date. */
async function previewFee(code, check, row, enteredAmount) {
  const account = (await get("/accounts?per=100")).results.find((a) => a.status === "active" && a.account_type === "residential");
  const extra = enteredAmount ? { entered_amount: enteredAmount } : {};
  const before = await preview(account.id, { kind: "fee", charge_code: code, bill_date: BEFORE, ...extra });
  const after = await preview(account.id, { kind: "fee", charge_code: code, bill_date: AFTER, ...extra });
  const want = [valuesOn(check, BEFORE)["All sizes|"], valuesOn(check, AFTER)["All sizes|"]];
  if (enteredAmount) { want[0] = money(enteredAmount); want[1] = money(enteredAmount); }
  const problems = [];
  const got = [];
  for (const [label, res, expect] of [["before", before, want[0]], ["after", after, want[1]]]) {
    if (res.status !== 200) {
      problems.push(`${label}: refused — ${(res.body?.params?.detail ?? res.body?.message_key ?? res.status).toString().slice(0, 200)}`);
      continue;
    }
    const mine = lines(res).filter((l) => l.code === code);
    got.push(mine.map((l) => money(l.amount)).join("+"));
    if (mine.length !== 1) problems.push(`${label}: ${mine.length} lines for ${code}`);
    else if (expect !== undefined && money(mine[0].amount) !== expect) problems.push(`${label}: billed ${money(mine[0].amount)}, price ${expect}`);
  }
  note(row, `fee preview ${BEFORE} → ${got[0] ?? "—"}, ${AFTER} → ${got[1] ?? "—"}`);
  if (problems.length) note(row, `fee preview: ${problems.join("; ")}`);
  return problems.length === 0;
}

// ── PHASE UPDATE ────────────────────────────────────────────────────────────
const seeded = (await get("/charges?per=200")).results
  .filter((c) => !c.code.startsWith("A-") && !c.code.startsWith("NB-") && !c.code.startsWith("PRB-"))
  .filter((c) => c.kind)
  .sort((a, b) => `${a.kind}${a.code}`.localeCompare(`${b.kind}${b.code}`));
console.log(`seeded charge codes: ${seeded.length}`);
const SPEC_FILE = `${SHOTS}/seeded-before.json`;
if (!existsSync(SPEC_FILE)) {
  // The shape every seeded code had BEFORE this walk touched it — the twin copies it.
  writeFileSync(SPEC_FILE, JSON.stringify(await dbCheck(seeded.map((c) => c.code)), null, 1));
}
const spec = JSON.parse(readFileSync(SPEC_FILE, "utf8"));
const want = (c) => !ONLY || ONLY.includes(c);

if (PHASES.includes("update")) {
  for (const c of seeded.filter((x) => want(x.code))) {
    const code = c.code;
    console.log(`== UPDATE ${code} (${c.kind})`);
    const row = result(`U:${code}`, { phase: "update", code, kind: c.kind, notes: [] });
    try {
      const before = (await dbCheck([code]))[code];
      await openEdit(before.id, code);
      await cont();
      const cells = await pricingCells();
      const shape = shapeOfCells(cells);
      row.shape = shape;
      let changed = {};
      if (shape === "entered") {
        // Nothing to price — the clerk changes how it bills (Staff may waive) instead.
        await page.getByRole("button", { name: /Back|Previous/ }).first().click().catch(() => {});
        await page.waitForTimeout(400);
        const waive = await page.locator("#cc-waive").inputValue().catch(() => null);
        if (waive !== null) await page.locator("#cc-waive").selectOption(waive === "yes" ? "no" : "yes");
        await cont();
      } else {
        changed = await repriceOnStep2(shape);
      }
      await shot(`${slug(code)}-U1-pricing`);
      await cont();
      await setDate("cc-effective-from", CHANGE_FROM);
      await page.locator("#cc-reason").fill(REASON);
      await page.getByRole("button", { name: "Save change" }).click();
      await page.getByText(`${code} saved.`).waitFor({ timeout: 30000 });
      await shot(`${slug(code)}-U2-saved`);
      row.update = true;

      const after = (await dbCheck([code]))[code];
      const changedKeys = Object.keys(changed);
      row.dbUpdate = shape === "entered" ? after.rows.length === before.rows.length : checkUpdateRows(before, after, changedKeys, changed, row);
      note(row, `rows ${before.rows.length} → ${after.rows.length}; changed ${changedKeys.map((k) => `${k.replace("|", " ")} → ${changed[k]}`).join(", ") || "no price"}`);

      // History: the API's versions, the Audit tab, audit_log and rate_change_log.
      const detail = await get(`/charges/${after.id}`);
      await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${after.id}?tab=audit`);
      await page.waitForTimeout(2000);
      const auditText = await page.locator("main").innerText();
      await shot(`${slug(code)}-U3-audit`);
      const scheduled = (detail.versions ?? []).some((v) => v.effective_from === CHANGE_FROM);
      const audited = after.audit_log_rows > before.audit_log_rows;
      if (shape === "entered") {
        row.history = audited;
      } else {
        const onScreen = /scheduled/i.test(auditText) && auditText.includes("11/01/2026");
        row.history = scheduled && audited && after.rate_change_log_rows > before.rate_change_log_rows && onScreen;
        if (!scheduled) note(row, "history: no version from 11/01/2026 served");
        if (!onScreen) note(row, "history: Audit tab does not show the 11/01/2026 change as scheduled");
        if (after.rate_change_log_rows <= before.rate_change_log_rows) note(row, "history: no rate_change_log row");
      }
      if (!audited) note(row, "history: no audit_log row");

      // One row to billing, before and after.
      if (shape === "entered") {
        row.oneRow = after.rows.length === 0;
        row.feePreview = await previewFee(code, after, row, "1250.00");
      } else {
        const expectBefore = valuesOn(before, BEFORE);
        const expectAfter = { ...valuesOn(before, AFTER), ...changed };
        row.oneRow = checkOneRow(after, expectBefore, expectAfter, row);
      }

      // Impacts.
      if (c.kind === "base") {
        const sched = await impactBase(code, after, row, changedKeys);
        const bill = await previewBase(code, after, row);
        row.impact = sched && bill !== false;
      } else {
        const plans = await get(`/charges/${after.id}/plans`).catch(() => ({ count: 0, results: [] }));
        const planProblems = [];
        for (const p of plans.results ?? []) {
          const plan = await get(`/plans/${p.id ?? p.plan_id}`).catch(() => null);
          const rule = plan?.charge_rules?.find((r) => r.code === code);
          const late = plan?.late_fee_charge?.code === code ? plan.late_fee_charge : null;
          const shown = rule?.amount_display ?? (late ? `${late.percent_display}/${late.min_amount_display}` : null);
          const today = valuesOn(after, ADD_FROM)["All sizes|"];
          if (rule && today !== undefined && money(rule.amount_display?.replace(/[$,]/g, "")) !== today) {
            planProblems.push(`${plan.name} shows ${rule.amount_display}, today's price ${today}`);
          }
          note(row, `plan ${plan?.name ?? "?"} shows ${shown ?? "—"}`);
        }
        if (shape === "flat") row.feePreview = await previewFee(code, after, row);
        row.impact = planProblems.length === 0 && row.feePreview !== false;
        if (planProblems.length) note(row, `plan: ${planProblems.join("; ")}`);
      }
    } catch (error) {
      note(row, `FAILED: ${String(error.message ?? error).split("\n")[0].slice(0, 300)}`);
      await shot(`${slug(code)}-U-failed`).catch(() => {});
    }
    save();
  }
}

// The eleven services' new base codes (phase NEW) — real sizes, real figures.
const NEW_BASES = [
  { code: "NB-W-RES", name: "Water base — residential", service: "water", cls: "residential", rows: [["W-58", "8.00"], ["W-34", "8.00"], ["W-1", "11.50"], ["W-2", "34.00"]] },
  { code: "NB-W-COM", name: "Water base — commercial", service: "water", cls: "commercial", rows: [["W-58", "15.00"], ["W-34", "15.00"], ["W-1", "22.00"], ["W-112", "28.00"], ["W-2", "60.00"], ["W-4", "150.00"]] },
  { code: "NB-E-RES", name: "Electric base — residential", service: "electric", cls: "residential", rows: [["E-1P-100", "12.00"], ["E-1P-200", "14.50"], ["E-1P-400", "22.00"]] },
  { code: "NB-E-COM", name: "Electric base — commercial", service: "electric", cls: "commercial", rows: [["E-1P-200", "48.00"], ["E-1P-400", "120.00"], ["E-3P-200", "96.00"], ["E-3P-400", "168.00"], ["E-CT", "456.00"]] },
  { code: "NB-G", name: "Gas base", service: "gas", cls: "", rows: [["G-250", "6.00"], ["G-425", "8.10"], ["G-630", "10.56"], ["G-1000", "15.00"]] },
  { code: "NB-S", name: "Sewer base", service: "sewer", cls: "", rows: [["All sizes", "9.00"]] },
  { code: "NB-T-RES", name: "Trash base — residential carts", service: "trash", cls: "residential", rows: [["CART-35", "9.00"], ["CART-64", "12.00"], ["CART-96", "15.00"]], keepUnpriced: ["DUMP-2"] },
  { code: "NB-T-COM", name: "Trash base — commercial dumpsters", service: "trash", cls: "commercial", rows: [["CART-96", "15.00"], ["DUMP-2", "40.00"], ["DUMP-4", "65.00"], ["DUMP-6", "90.00"], ["DUMP-8", "115.00"]] },
  { code: "NB-SW", name: "Storm water base", service: "storm_water", cls: "", rows: [["SW-SF", "2.00"], ["SW-DUP", "3.50"], ["SW-APT", "12.00"], ["SW-COM-S", "18.00"], ["SW-COM-L", "45.00"]] },
  { code: "NB-SOL", name: "Solar base", service: "solar", cls: "", rows: [["SOL-P3", "3.00"], ["SOL-P5", "5.00"], ["SOL-P8", "8.00"], ["SOL-P10", "10.00"]] },
  { code: "NB-BB", name: "Broadband base", service: "broadband", cls: "", rows: [["BB-100", "30.00"], ["BB-500", "50.00"], ["BB-1000", "70.00"]] },
  { code: "NB-TH", name: "Thermal base", service: "thermal_heat", cls: "", rows: [["TH-T5", "20.00"], ["TH-T10", "35.00"], ["TH-T25", "80.00"], ["TH-T50", "150.00"]] },
  { code: "NB-BAT", name: "Battery base", service: "battery", cls: "", rows: [["BAT-5", "5.00"], ["BAT-10", "8.00"], ["BAT-15", "11.00"], ["BAT-20", "14.00"]] },
  { code: "NB-FIRE", name: "Fire line base", service: "fire", cls: "", rows: [["FL-2", "12.00"], ["FL-4", "30.00"], ["FL-6", "60.00"], ["FL-8", "100.00"]] },
];

// ── PHASE RECHECK (the bill impact of codes already updated, nothing edited) ─
// For a code whose update ran but whose impact check needed a second look (a
// walk fix, or a product fix landed since): the schedule and bill-preview checks
// only, on the database as it stands. Never re-edits a price.
if (PHASES.includes("recheck")) {
  const targets = [
    // A retired seeded code is not rechecked: billing no longer reads it.
    ...seeded.filter((x) => want(x.code) && x.kind === "base" && x.status === "active").map((x) => [x.code, `U:${x.code}`]),
    ...NEW_BASES.filter((x) => want(x.code)).map((x) => [x.code, `N:${x.code}`]),
  ];
  for (const [code, key] of targets) {
    console.log(`== RECHECK ${code}`);
    const row = result(key, {});
    row.notes = (row.notes ?? []).filter((n) => !/^bill preview|^rate schedules|^schedule Rates|^no .* account/.test(n));
    try {
      const after = (await dbCheck([code]))[code];
      const nb = NEW_BASES.find((x) => x.code === code);
      if (nb?.keepUnpriced) {
        // Re-read the ADD as stored (rows dated ADD_FROM): a size kept on screen and
        // left blank is a row with NO amount — "not served" (DEF-431) — by design.
        const typed = [
          ...nb.rows.map(([size, amount]) => `${size}|${amount}`),
          ...nb.keepUnpriced.map((size) => `${size}|null`),
        ].sort();
        const stored = after.rows.filter((r) => r.effective_from === ADD_FROM).map((r) => `${r.size_class}|${money(r.amount)}`).sort();
        row.dbAdd = typed.join() === stored.join();
        row.notes = (row.notes ?? []).filter((n) => !n.startsWith("DB after add"));
        note(row, `add stored ${stored.join(", ")} — ${nb.keepUnpriced.join(", ")} kept without a price is a row with no amount (not served, DEF-431)`);
      }
      const changedKeys = Object.keys(valuesOn(after, AFTER)).filter((k) => valuesOn(after, AFTER)[k] !== valuesOn(after, BEFORE)[k]);
      const sched = await impactBase(code, after, row, changedKeys);
      const bill = await previewBase(code, after, row);
      row.impact = sched && bill !== false;
    } catch (error) {
      note(row, `FAILED: ${String(error.message ?? error).split("\n")[0].slice(0, 300)}`);
    }
    save();
  }
}

// ── PHASE ADD (a twin of every seeded code, through Add) ────────────────────
async function mint(code, name) {
  const res = await post("/lookups/charge_codes", { code, name });
  if (res.status >= 300 && res.status !== 409 && !/exist|duplicate/i.test(JSON.stringify(res.body))) {
    throw new Error(`mint ${code}: ${res.status} ${JSON.stringify(res.body).slice(0, 200)}`);
  }
}
/** Step 1 + step 2 + step 3 of Add, typing `rows` ({size, cls, amount | percent+minimum}). */
async function addThroughScreen(code, opts, row, mode = {}) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/new`);
  await page.locator("#cc-kind").waitFor();
  await page.waitForTimeout(800);
  await page.locator("#cc-kind").selectOption(opts.kind);
  if (opts.kind === "base") {
    await page.locator("#cc-service").selectOption(opts.service);
    await page.waitForTimeout(400);
    if (opts.cls) await page.locator("#cc-class").selectOption(opts.cls);
    // DEF-RAT-8844 — on a service with sizes the clerk chooses Size or All sizes.
    if ((await page.locator("#cc-priced-by").count()) > 0) {
      await page.locator("#cc-priced-by").selectOption(opts.pricedBy === "size" ? "size" : "one");
    }
  } else if (opts.kind === "plan") {
    if (opts.chargeType) await page.locator("#cc-type").selectOption(opts.chargeType).catch(() => {});
    if (opts.service) await page.locator("#cc-service").selectOption(opts.service).catch(() => {});
    // The screen's Priced by values: a penalty's one pair is "one", per class "class".
    const pricedByValue = { penalty: "one", "penalty-class": "class", "penalty-flat": "amount" }[opts.pricedBy] ?? opts.pricedBy;
    await page.locator("#cc-priced-by").selectOption(pricedByValue);
  } else {
    if (opts.service) await page.locator("#cc-service").selectOption(opts.service).catch(() => {});
    await page.locator("#cc-amount-mode").selectOption(opts.pricedBy === "entered" ? "entered" : "one");
  }
  await pickCode(code);
  await cont();
  const cells = await pricingCells();
  if (opts.pricedBy === "size" && opts.fillAll) {
    // A seeded ONE-amount base on a sized service: Add starts with one row per
    // size of the service, and every one is typed at that amount.
    opts.rows = [];
    for (const sc of cells.filter((c) => c.cell.startsWith("size-"))) {
      const index = sc.cell.split("-")[1];
      await page.locator(`[data-cell="amount-${index}"]`).fill(opts.fillAll);
      opts.rows.push({ size: sc.value, amount: opts.fillAll });
    }
  } else if (opts.pricedBy === "size") {
    // The screen starts with one row per size of the service; keep the sizes typed, clear the rest.
    const sizeCells = cells.filter((c) => c.cell.startsWith("size-"));
    const wanted = new Map(opts.rows.map((r) => [r.size, r]));
    // Remove from the bottom so indices stay valid.
    for (const sc of [...sizeCells].reverse()) {
      if (!wanted.has(sc.value) && !(opts.keepUnpriced ?? []).includes(sc.value)) {
        const index = Number(sc.cell.split("-")[1]);
        await page.getByRole("button", { name: `Remove row — ${index + 1}` }).click();
        await page.waitForTimeout(150);
      }
    }
    // Add rows for any wanted size the screen did not start with (a plan by size starts with one empty row).
    let now = await pricingCells();
    for (const r of opts.rows) {
      if (now.some((c) => c.cell.startsWith("size-") && c.value === r.size)) continue;
      const empty = now.find((c) => c.cell.startsWith("size-") && c.value === "");
      if (!empty) {
        await page.getByRole("button", { name: /Add row/ }).click();
        now = await pricingCells();
      }
      const slot = now.find((c) => c.cell.startsWith("size-") && c.value === "");
      await page.locator(`[data-cell="${slot.cell}"]`).selectOption(r.size);
      now = await pricingCells();
    }
    for (const r of opts.rows) {
      const sc = now.find((c) => c.cell.startsWith("size-") && c.value === r.size);
      const index = sc.cell.split("-")[1];
      await page.locator(`[data-cell="amount-${index}"]`).fill(r.amount);
    }
  } else if (opts.pricedBy === "class" || opts.pricedBy === "penalty-class") {
    let now = await pricingCells();
    const classCells = now.filter((c) => c.cell.startsWith("class-"));
    for (const sc of [...classCells].reverse()) {
      if (!opts.rows.some((r) => r.cls === sc.value)) {
        const index = Number(sc.cell.split("-")[1]);
        await page.getByRole("button", { name: `Remove row — ${index + 1}` }).click();
        await page.waitForTimeout(150);
      }
    }
    for (const r of opts.rows) {
      now = await pricingCells();
      let sc = now.find((c) => c.cell.startsWith("class-") && c.value === r.cls);
      if (!sc) {
        await page.getByRole("button", { name: /Add row/ }).click();
        now = await pricingCells();
        sc = now.filter((c) => c.cell.startsWith("class-")).pop();
        await page.locator(`[data-cell="${sc.cell}"]`).selectOption(r.cls);
      }
      const index = sc.cell.split("-")[1];
      if (r.percent !== undefined) {
        await page.locator(`[data-cell="percent-${index}"]`).fill(r.percent);
        await page.locator(`[data-cell="minimum-${index}"]`).fill(r.minimum);
      } else {
        await page.locator(`[data-cell="amount-${index}"]`).fill(r.amount);
      }
    }
  } else if (opts.pricedBy === "penalty") {
    await page.locator('[data-cell="percent-0"]').fill(opts.rows[0].percent);
    await page.locator('[data-cell="minimum-0"]').fill(opts.rows[0].minimum);
  } else if (opts.pricedBy === "one" || opts.pricedBy === "penalty-flat") {
    await page.locator('[data-cell="amount-0"]').fill(opts.rows[0].amount);
  }
  await shot(`${slug(code)}-A2-pricing`);
  await cont();
  await setDate("cc-effective-from", ADD_FROM);
  await page.getByRole("button", { name: "Create charge code" }).click();
  if (mode.expectRefusal) {
    // DEF-RAT-8845 — the refusal a clerk reads, by name.
    const said = page.getByText(/already covers this class/).first();
    await said.waitFor({ timeout: 30000 }).catch(() => null);
    await shot(`${slug(code)}-A2b-second-base-refused`);
    return said.innerText().catch(() => null);
  }
  await page.getByText(`${code} created.`).waitFor({ timeout: 30000 });
  await shot(`${slug(code)}-A3-review-saved`);
  return null;
}
/** List + View details show it. */
async function checkListAndView(code, id, expectValues, row) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes?q=${encodeURIComponent(code)}`);
  await page.waitForTimeout(2000);
  const listText = await page.locator("main").innerText();
  const listed = listText.includes(code);
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${id}?tab=prices`);
  await page.waitForTimeout(2000);
  const viewText = await page.locator("main").innerText();
  await shot(`${slug(code)}-A4-view-prices`);
  const missing = expectValues.filter((v) => !viewText.includes(v.replace(/%.*/, "")));
  if (!listed) note(row, "list: code not found by search");
  if (missing.length) note(row, `view Prices tab: does not show ${missing.join(", ")}`);
  return listed && missing.length === 0;
}
/** After an ADD: exactly the typed rows, open, dated ADD_FROM, none killed. */
function checkAddRows(check, typed, row) {
  const problems = [];
  const live = liveRows(check);
  if (check.rows.length !== typed.length) problems.push(`${check.rows.length} rows stored, ${typed.length} typed`);
  for (const t of typed) {
    const hits = live.filter((r) => keyOf(r) === t.key);
    if (hits.length !== 1) { problems.push(`${t.key}: ${hits.length} rows`); continue; }
    const r = hits[0];
    if (valueOf(r) !== t.value) problems.push(`${t.key}: stored ${valueOf(r)}, typed ${t.value}`);
    if (r.effective_from !== ADD_FROM) problems.push(`${t.key}: from ${r.effective_from}`);
    if (r.effective_to !== null) problems.push(`${t.key}: to ${r.effective_to}`);
  }
  if (check.rows.some((r) => r.killed)) problems.push("a row is killed");
  if (problems.length) note(row, `DB after add: ${problems.join("; ")}`);
  return problems.length === 0;
}
async function retire(id, code, row) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${id}`);
  await page.getByRole("button", { name: "Retire" }).first().click();
  await page.waitForTimeout(400);
  // The confirm is an alertdialog (ConfirmDialog): it interrupts, and says so.
  const dialog = page.locator('[role="alertdialog"], [role="dialog"]').last();
  await dialog.getByRole("button", { name: /^Retire$/ }).click();
  await page.waitForTimeout(1500);
  const after = await get(`/charges/${id}`);
  if (after.status !== "inactive" && after.status !== "retired") note(row, `retire: status reads ${after.status}`);
  return true;
}

function optsFromSpec(s) {
  const live = s.rows.filter((r) => !r.killed);
  const typed = live.map((r) => ({ key: keyOf(r), value: valueOf(r) }));
  const sized = live.some((r) => r.size_class !== "All sizes");
  const byClass = live.some((r) => r.customer_class);
  const terms = live.some((r) => r.percent !== null);
  let pricedBy = "one";
  if (s.amount_rule === "per_case" || (live.length === 0 && s.kind === "other")) pricedBy = "entered";
  else if (s.charge_type === "penalty" && (terms || s.amount_rule === "percent_with_minimum")) pricedBy = byClass ? "penalty-class" : "penalty";
  else if (sized) pricedBy = "size";
  else if (byClass) pricedBy = "class";
  return {
    kind: s.kind,
    service: s.kind === "base" ? s.service : s.service ?? undefined,
    cls: s.kind === "base" ? (s.applies_to_customer_classes[0] ?? "") : undefined,
    chargeType: s.charge_type,
    pricedBy,
    rows: live.map((r) => ({
      size: r.size_class,
      cls: r.customer_class,
      amount: money(r.amount),
      percent: r.percent === null ? undefined : money(Number(r.percent) * 100),
      minimum: money(r.min_amount),
    })),
    typed,
  };
}

if (PHASES.includes("add")) {
  for (const c of seeded.filter((x) => want(x.code))) {
    const s = spec[c.code];
    const twin = `A-${c.code}`;
    console.log(`== ADD ${twin} (twin of ${c.code}, ${s.kind})`);
    const opts = optsFromSpec(s);
    const row = result(`A:${twin}`, { phase: "add", code: twin, twinOf: c.code, kind: s.kind, shape: opts.pricedBy, notes: [] });
    let liveId = null;
    try {
      // A base on a SIZED service is priced by size on Add (PO 2026-10-01: "one or more
      // sizes"); a seeded flat base on such a service is copied as every size at its amount.
      const sizes = s.kind === "base" && opts.pricedBy === "one" && !["sewer"].includes(s.service);
      if (s.kind === "base") {
        // DEF-RAT-8845 — a second live base for the same service and class is refused
        // at save. Prove the refusal on screen, then retire the seeded code so the
        // twin can be added, and bring the seeded code back afterwards.
        await mint(twin, c.name);
        const said = await addThroughScreen(twin, opts, row, { expectRefusal: true });
        note(row, `beside the live ${c.code}, Add refuses: "${said}"`);
        row.refusedSecondBase = /already covers/.test(said ?? "");
        // The live id, read from THIS database (seeded-before.json may predate a rebuild).
        liveId = (await chargeByCode(c.code)).id;
        const off = await ctx.request.patch(api(`/charges/${liveId}`), { data: { active: false } });
        if (!off.ok()) throw new Error(`retire ${c.code}: ${off.status()}`);
      }
      if (s.charge_type === "penalty" && opts.pricedBy === "one") {
        // NSF $30.00 / TAMPER $250.00 — a penalty priced as ONE AMOUNT (DEF-RAT-8843).
        opts.pricedBy = "penalty-flat";
      }
      if (opts.pricedBy === "penalty" && opts.rows.length === 0) {
        // LATE states its percent on the code itself (no rows); copy what the edit screen shows.
        opts.rows = [{ percent: "1.50", minimum: "5.00" }];
        opts.typed = [{ key: "All sizes|", value: "1.50%/5.00" }];
      }
      await mint(twin, c.name);
      // DEF-RAT-8844 — a one-amount base on a sized service is now added as ONE All sizes row.
      const addOpts = opts;
      await addThroughScreen(twin, addOpts, row).catch(async (e) => {
        throw e;
      });
      row.add = true;
      const check = (await dbCheck([twin], [BEFORE]))[twin];
      const typedNow = sizes ? addOpts.rows.map((r) => ({ key: `${r.size}|`, value: r.amount })) : opts.typed;
      row.dbAdd = checkAddRows(check, typedNow, row);
      note(row, `stored ${check.rows.map((r) => `${r.size_class}${r.customer_class ? "/" + r.customer_class : ""} ${valueOf(r)}`).join(", ") || "no price row"}`);
      row.view = await checkListAndView(twin, check.id, [...new Set(typedNow.map((t) => t.value).filter(Boolean))], row);
      row.oneRow = checkOneRow(check, Object.fromEntries(typedNow.map((t) => [t.key, t.value])), {}, row);
      if (check.kind !== s.kind) note(row, `kind stored ${check.kind}, chosen ${s.kind}`);
      if (s.kind === "base") {
        // DEF-RAT-8847 — the base made through Add starts on the seeded code's account.
        const made = await get(`/charges/${check.id}`);
        const seededRow = await get(`/charges/${liveId}`);
        row.gl = made.gl_account_id !== null && made.gl_account_id === seededRow.gl_account_id;
        note(row, `GL ${made.gl_account_code ?? "not set"} — the seeded ${c.code} posts to ${seededRow.gl_account_code ?? "not set"}`);
        // Put the utility back as it was: the twin retired, the seeded code live again.
        await retire(check.id, twin, row);
        await ctx.request.patch(api(`/charges/${liveId}`), { data: { active: true } });
        note(row, `twin retired and ${c.code} brought back`);
      }
    } catch (error) {
      note(row, `FAILED: ${String(error.message ?? error).split("\n")[0].slice(0, 300)}`);
      await shot(`${slug(twin)}-A-failed`).catch(() => {});
      // Never leave the seeded base retired behind a failed step.
      if (liveId) await ctx.request.patch(api(`/charges/${liveId}`), { data: { active: true } }).catch(() => {});
    }
    save();
  }
}

// ── PHASE RETIRETWINS (base twins added on a run that stopped before retiring them)
if (PHASES.includes("retiretwins")) {
  const live = (await get("/charges?per=200")).results.filter((c) => c.code.startsWith("A-BASE") && c.status === "active");
  for (const twin of live) {
    const s = spec[twin.code.slice(2)];
    console.log(`== RETIRE ${twin.code}`);
    const row = result(`A:${twin.code}`, {});
    row.notes = (row.notes ?? []).filter((n) => !n.startsWith("FAILED"));
    try {
      const cls = (s.applies_to_customer_classes ?? [])[0] ?? "residential";
      const account = await accountFor(s.service, cls);
      if (account) {
        const res = await preview(account.id, { kind: "interim", period_start: "2026-10-01", period_end: "2026-10-31", bill_date: "2026-11-01" });
        const said = res.status === 200 ? "priced" : `refused: ${(res.body?.params?.detail ?? res.body?.message_key ?? res.status).toString().slice(0, 160)}`;
        note(row, `with ${twin.code} AND ${twin.code.slice(2)} both live, a ${cls} ${s.service} bill preview (${account.account_no}) is ${said}`);
      }
      await retire(twin.id, twin.code, row);
      note(row, "retired after the checks (a second base code for the same service and class makes the bill refuse)");
    } catch (error) {
      note(row, `FAILED: ${String(error.message ?? error).split("\n")[0].slice(0, 300)}`);
    }
    save();
  }
}

// ── PHASE NEW (a base code for every one of the eleven services) ───────────

if (PHASES.includes("new")) {
  for (const nb of NEW_BASES.filter((x) => want(x.code))) {
    console.log(`== NEW ${nb.code} (${nb.service}, ${nb.cls || "all classes"})`);
    const flat = nb.rows.length === 1 && nb.rows[0][0] === "All sizes";
    const row = result(`N:${nb.code}`, { phase: "new", code: nb.code, kind: "base", shape: flat ? "flat" : "sized", service: nb.service, cls: nb.cls || "all", notes: [] });
    try {
      // Retire the service's seeded base codes this one replaces, so billing reads the new one.
      const olds = (await get(`/charges?per=200`)).results.filter(
        (c) => c.kind === "base" && c.service === nb.service && !c.code.startsWith("NB-") && c.status === "active",
      );
      const retired = [];
      for (const old of olds) {
        const classes = old.applies_to_customer_classes ?? [];
        if (nb.cls === "" || classes.length === 0 || classes.includes(nb.cls)) {
          await retire(old.id, old.code, row);
          retired.push(old.code);
        }
      }
      if (retired.length) note(row, `retired the seeded ${retired.join(", ")} first`);
      await mint(nb.code, nb.name);
      await addThroughScreen(
        nb.code,
        { kind: "base", service: nb.service, cls: nb.cls, pricedBy: flat ? "one" : "size", rows: nb.rows.map(([size, amount]) => ({ size, amount })), keepUnpriced: nb.keepUnpriced },
        row,
      );
      row.add = true;
      // A size kept on screen and left blank is stored as a row with NO amount —
      // "this size is not served" (DEF-431), billed $0.00 with a warning.
      const typed = [
        ...nb.rows.map(([size, amount]) => ({ key: `${size}|`, value: amount })),
        ...(nb.keepUnpriced ?? []).map((size) => ({ key: `${size}|`, value: null })),
      ];
      const added = (await dbCheck([nb.code]))[nb.code];
      row.dbAdd = checkAddRows(added, typed, row);
      note(row, `stored ${added.rows.map((r) => `${r.size_class} ${valueOf(r)}`).join(", ")}`);
      row.view = await checkListAndView(nb.code, added.id, typed.map((t) => t.value).filter(Boolean), row);
      // DEF-RAT-8847 — a base made through Add starts on its service's base revenue account.
      const made = await get(`/charges/${added.id}`);
      row.gl = made.gl_account_id !== null;
      note(row, `GL ${made.gl_account_code ?? "not set"}${made.gl_account_name ? ` — ${made.gl_account_name}` : ""}`);

      // UPDATE the first size (or the one amount) from CHANGE_FROM.
      await openEdit(added.id, nb.code);
      await cont();
      const changed = await repriceOnStep2(flat ? "flat" : "sized");
      await shot(`${slug(nb.code)}-U1-pricing`);
      await cont();
      await setDate("cc-effective-from", CHANGE_FROM);
      await page.locator("#cc-reason").fill(REASON);
      await page.getByRole("button", { name: "Save change" }).click();
      await page.getByText(`${nb.code} saved.`).waitFor({ timeout: 30000 });
      await shot(`${slug(nb.code)}-U2-saved`);
      row.update = true;
      const after = (await dbCheck([nb.code]))[nb.code];
      row.dbUpdate = checkUpdateRows(added, after, Object.keys(changed), changed, row);
      note(row, `changed ${Object.entries(changed).map(([k, v]) => `${k.replace("|", "")} → ${v}`).join(", ")}`);
      const detail = await get(`/charges/${after.id}`);
      await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${after.id}?tab=audit`);
      await page.waitForTimeout(2000);
      const auditText = await page.locator("main").innerText();
      await shot(`${slug(nb.code)}-U3-audit`);
      row.history =
        (detail.versions ?? []).some((v) => v.effective_from === CHANGE_FROM) &&
        after.audit_log_rows > added.audit_log_rows &&
        /scheduled/i.test(auditText);
      if (!row.history) note(row, `history: versions ${JSON.stringify((detail.versions ?? []).map((v) => [v.effective_from, v.state]))}, audit_log ${added.audit_log_rows}→${after.audit_log_rows}`);
      row.oneRow = checkOneRow(after, Object.fromEntries(typed.map((t) => [t.key, t.value])), { ...Object.fromEntries(typed.map((t) => [t.key, t.value])), ...changed }, row);
      const sched = await impactBase(nb.code, after, row, Object.keys(changed));
      const bill = await previewBase(nb.code, after, row);
      row.impact = sched && bill !== false;
    } catch (error) {
      note(row, `FAILED: ${String(error.message ?? error).split("\n")[0].slice(0, 300)}`);
      await shot(`${slug(nb.code)}-N-failed`).catch(() => {});
    }
    save();
  }
}

await browser.close();
helper.stdin.end();

// ── RESULTS.md ──────────────────────────────────────────────────────────────
const tick = (v) => (v === true ? "✅" : v === false ? "❌" : "—");
const order = Object.values(results).sort((a, b) => `${a.phase}${a.kind}${a.code}`.localeCompare(`${b.phase}${b.kind}${b.code}`));
const md = [
  "# Charge codes — the clerk's walk over every code (2026-10-01)",
  "",
  "Walked by `10-scripts/charge_codes_walk33.mjs` in Chromium at 1440 on a private PostgreSQL 16 database",
  "(`seed_demo` + all eleven services switched on + `load_sample_data`). The database half is",
  "`10-scripts/ccwalk_charge_code_db_check.py` (the real `charge_prices.price_on_date`).",
  `Dates: today ${ADD_FROM}; adds dated ${ADD_FROM}; every update dated ${CHANGE_FROM}, so the old row must end ${CLOSED_TO};`,
  `the one-row lookup is asked for ${BEFORE} and ${AFTER}.`,
  "",
  "| Phase | Code | Kind | Shape | Add | DB after add | Update | DB after update | History | One row to billing | Schedule / plan / bill impact | Notes |",
  "|---|---|---|---|---|---|---|---|---|---|---|---|",
  ...order.map((r) =>
    `| ${r.phase} | \`${r.code}\`${r.twinOf ? ` (twin of \`${r.twinOf}\`)` : ""} | ${r.kind} | ${r.shape ?? "—"} | ${tick(r.add)} | ${tick(r.dbAdd)} | ${tick(r.update)} | ${tick(r.dbUpdate)} | ${tick(r.history)} | ${tick(r.oneRow)} | ${tick(r.impact)} | ${(r.notes ?? []).join(" · ").replace(/\|/g, "/")} |`,
  ),
  "",
];
writeFileSync(`${SHOTS}/RESULTS.md`, md.join("\n"));
console.log(`wrote ${SHOTS}/RESULTS.md (${order.length} rows)`);
