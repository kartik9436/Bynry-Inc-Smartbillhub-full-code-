// ── Trace ────────────────────────────────────────────────────────────────────
// Ask:      The PO's `MasterReconnect1` and `MasterReconnect2` of 2026-09-25.
// Walks:    `S148` on a MASTER account — the one-line warning, the who-it-
//           reaches column, the unsplittable unit-meter row, and
//           transferred-up residue as its own money line.
// Rules:    BR-CUS-1098 · BR-CUS-097 · BR-CUS-171 · B14 rules 31, 33, 44.
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠⚠ **WHAT THIS PROVES AND WHAT IT DOES NOT — READ BEFORE QUOTING IT.**
// It drives the SHIPPED bundle in a real Chromium at both staff widths, so it
// proves the master screens RENDER: their rows, their order, their columns and
// that neither width scrolls sideways. **It intercepts `GET
// /disconnects/{ref}/reconnect` and answers with a fixed master payload**, so
// it proves NOTHING about whether the server assembles that payload correctly.
//
// **IT IS A STUB BECAUSE THE FIXTURE CANNOT PRODUCE THE CASE**, and that is a
// fact about the data rather than a shortcut: all four master accounts on
// `brazosbend` carry a **$0.00** balance, `disconnects.open_case` refuses a
// ladder on an account that owes nothing (*"there is nothing to chase"*), and
// inventing a debt to light a screen up would be fabricating financial data on
// the screen whose whole job is to state what is owed.
//
// **So the server's master half is covered by `tests/test_reconnect_read.py`
// and NOT by a browser.** A lane that can seed a master cut should point this
// script at it — delete the `route` block and pass `RWALK_CASE`.
//
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.RWALK_BASE || "http://127.0.0.1:8984";
const T = process.env.RWALK_TENANT || "brazosbend";
const CASE = process.env.RWALK_CASE || "dsc-26-0005";
const SHOTS = process.env.RWALK_SHOTS || "/tmp/claude-0/reconnect-shots";
const CHROME = process.env.RWALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const STUB = process.env.RWALK_STUB !== "0";

const money = (d) => ({ stored: `${d}0000`, display: d, currency: "USD", unavailable: null });
const MASTER = {
  case_no: "DSC-26-0007",
  account: {
    account_no: "AC-2026-00117",
    customer_name: "Marten Row Holdings",
    address: "500 Main Street · Silver Creek, TX 78611",
    account_kind: "master",
    account_class: "Commercial",
    cut_on: "2026-10-02",
    balance: money("12225.00"),
  },
  master: { is_master: true, units: 25, unit_accounts: 25 },
  services: {
    rows: [
      { service: "water", scope: "common_supply", service_point: "500 Main Street",
        point_known: true, meter: null, meter_absence: null,
        how_options: ["work_order", "remote", "no_visit"], how_default: "work_order",
        instruction: null, work_order: { reference: "WO-26-0488", assignee: "Wilkes crew" },
        reaches: "all_occupants" },
      { service: "water", scope: "unit_meters", service_point: "500 Main Street",
        point_known: true, meter: null, meter_absence: null,
        how_options: ["all_units_together"], how_default: "all_units_together",
        instruction: null, work_order: null, reaches: "each_unit" },
    ],
    unavailable: null,
    addable: [],
  },
  owed: {
    lines: [
      { code: "own_debt_at_the_cut", from_code: "the_owners_account", amount: money("11940.00"), when: "2026-10-02", negative: false },
      { code: "transferred_up_from_units", from_code: "occupying_accounts", amount: money("2450.00"), when: "2026-10-02", negative: false },
      { code: "reconnection_fee", from_code: "the_tenants_charge_code", amount: money("150.00"), when: "at_the_cut", negative: false },
      { code: "deposit_applied", from_code: "held_before_the_cut", amount: money("2400.00"), when: "2026-10-02", negative: true },
      { code: "paid_since", from_code: "payments", amount: money("0.00"), when: null, negative: true },
    ],
    still_owed: money("12140.00"),
    total_is_the_ledger: { code: "fee_is_already_in_the_balance", detail: "read once." },
    plan_label: "Commercial",
  },
  deposit: { held_before_the_cut: money("2400.00"), disposition: "applied_against_arrear", new_deposit_required: true },
  consequences: [
    { code: "common_supply_back_on" }, { code: "all_units_together" },
    { code: "owner_charges_restart" }, { code: "the_mark_clears" },
    { code: "work_orders_go_to_the_crew" }, { code: "the_case_closes" },
  ],
  warning: { code: "still_owed_you_may_continue", amount: money("12140.00") },
  commit_refused_by: { code: "not_settled", br_ref: "`DSC-02.4`" },
  step: "mark_reconnecting",
  restore_on: "2026-09-26",
};

let pass = 0;
const failures = [];
const ok = (w) => { pass += 1; console.log(`  ✓ ${w}`); };
const is = (c, w, saw) => (c ? ok(w) : (failures.push(w), console.log(`  ✗ ${w}\n      saw: ${saw}`)));

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  for (const width of [1440, 1280]) {
    console.log(`\n═══ MASTER · ${width}px ═══`);
    const p = await ctx.newPage({ viewport: { width, height: 1700 } });
    p.setDefaultTimeout(25000);
    await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
    await p.fill("#signin-email", "dana@brazosbendutilities.com");
    await p.fill("#signin-password", "S3cure!passw0rd");
    await Promise.all([
      p.waitForURL((u) => !u.pathname.endsWith("/signin")),
      p.click('button[type="submit"]'),
    ]);
    if (STUB) {
      await p.route(`**/api/${T}/disconnects/**/reconnect`, (route) =>
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MASTER) }),
      );
    }
    for (const step of [1, 2]) {
      await p.goto(`${BASE}/${T}/disconnects/${CASE}/reconnect?step=${step}`, { waitUntil: "networkidle" });
      await p.waitForTimeout(800);
      await p.screenshot({ path: `${SHOTS}/master-step${step}-${width}.png`, fullPage: true });
      const text = await p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));
      if (step === 1) {
        // `BR-CUS-1098` — ONE LINE is the whole master warning.
        is((await p.$('[data-testid="reconnect-master"]')) !== null, "the one-line master warning is drawn", "absent");
        is(/25 units come back on together/.test(text), "  and it says all 25 come back together", text.slice(0, 200));
        is(/Master · Commercial/.test(text), "the account type says MASTER", "absent");
        is(/Who it reaches/i.test(text), "the who-it-reaches column is drawn (BR-CUS-1098)", "absent");
        is(/All 25 occupants/.test(text), "  and the common supply reaches all 25", "absent");
        is(/Units cannot be restored separately/.test(text), "units cannot be split (4.6)", "absent");
        is(/Water — common supply/.test(text) && /Water — unit meters/.test(text),
           "both drawn rows are named as ONE service in two places", text.slice(0, 300));
        is(/WO-26-0488/.test(text) && /Wilkes crew/.test(text),
           "a raised order shows its reference and who it is with (4.5)", "absent");
      } else {
        is((await p.$('[data-owed-line="transferred_up_from_units"]')) !== null,
           "transferred-up residue is its OWN money line (BR-CUS-1098)", "absent");
        is((await p.$('[data-owed-line="own_debt_at_the_cut"]')) !== null,
           "and the owner's own debt is a separate line", "absent");
        is(/12,140\.00 still owed\. You may continue\./.test(text),
           "the warning states the figure and four words (BR-CUS-1097)", text.slice(0, 300));
        is(/25 occupants get service back/.test(text), "who gets service back is named", "absent");
        is((await p.$('[data-testid="reconnect-deposit"]')) !== null,
           "the deposit panel is drawn where a deposit WAS applied", "absent");
        const commit = await p.$('[data-wizard="actions"] button[data-variant="primary"]');
        is(commit !== null && (await commit.isDisabled()),
           "the commit is refused, not merely explained (law 2's mirror)", "live");
      }
      const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      is(over <= 0, `  no horizontal page scroll at ${width}px, step ${step}`, `${over}px over`);
    }
    await p.close();
  }
  console.log(`\n${pass} passed · ${failures.length} failed`);
  for (const f of failures) console.log(`  FAIL ${f}`);
  console.log(`shots: ${SHOTS}`);
  console.log(STUB ? "⚠ PAYLOAD STUBBED — this proves RENDERING, not assembly." : "live payload");
} finally {
  await browser?.close();
}
