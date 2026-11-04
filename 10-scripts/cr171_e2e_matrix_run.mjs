#!/usr/bin/env node
// CR-171-BRC10 P4.02 (lane MVI-E2E-SEED) — THE MOVE-IN MATRIX RUNNER.
//
// One script, per case (M1–M7, decision log "THE END-TO-END SCOPE IS ACCEPTED
// AND WIDENED"):
//   1. SUBMIT the move-in through the BROWSER — the four steps a clerk clicks,
//      at desktop 1440, signed in as the case's clerk;
//   2. READ THE DATABASE BACK — `cr171_e2e_matrix_readback.py`, which prints
//      one JSON check per fact the move-in must have written;
//   3. WALK THE EIGHT MODULES' SCREENS — Units, Assets, Accounts, Payments,
//      Billing (the first bill), Cycle/Route, Work, Messages — and read each
//      one for what the move-in should have put there;
//   4. print PASS or FAIL per check, a count per case, and exit 1 on any FAIL.
//
// The world it stands on is `10-scripts/cr171_e2e_matrix_world.py setup`, on a
// FRESH lane database (it reads the seeded unit numbers back with `world`).
//
// Usage (from the repository root; the backend env reaches the two Python
// helpers):
//   DATABASE_URL=postgres://postgres@127.0.0.1:55433/<lane db> \
//   MX_BASE=http://127.0.0.1:5743 MX_CASES=M1 MX_OUT=<folder for photographs> \
//   node 10-scripts/cr171_e2e_matrix_run.mjs
//
// ⚠ IT WRITES REAL ROWS: every case commits a move-in. Run each case once per
// fresh world (a second run finds the unit occupied and says so as a FAIL).
//
// ── HOW A CASE IS DESCRIBED ──────────────────────────────────────────────
// `CASES[key]` is the case's INPUT (what the clerk types) and its EXPECTED
// screen facts. Every expected figure follows a PO ruling or a seeded rule,
// never what the product happened to print (B14 rule 37 for the drawn
// figures; decision log for the rulings):
//   * fees are never taxed at move-in (OQ-BIL-12788 (a));
//   * a match is shown only when our rule says match (2026-10-05 (1));
//   * a billing clerk records discounts and exemptions (2026-10-05 (2));
//   * unit and meter status are DERIVED, never written;
//   * labour comes from the technician's arrived/finished times.
// M1 is built and proved here. M2–M7 carry their inputs; the R4 lanes prove them.
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
const require = createRequire(join(REPO, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.MX_BASE || "http://127.0.0.1:5743";
const OUT = process.env.MX_OUT || join(REPO, "08-qa/movein-2026-10-05/e2e");
const CHROME = process.env.MX_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const PY = process.env.MX_PYTHON || "/tmp/venv_a5c/bin/python";
const WANT = (process.env.MX_CASES || "M1").split(",").map((s) => s.trim()).filter(Boolean);
const DATE = process.env.MX_DATE || "10/10/2026"; // typed as a clerk types it (the utility's format)
const DATE_ISO = process.env.MX_DATE_ISO || "2026-10-10";

const KILL = setTimeout(() => {
  console.error("REFUSED: the matrix run exceeded 20 minutes — killing");
  process.exit(3);
}, 20 * 60 * 1000);

function py(script, args) {
  return execFileSync(PY, [join(REPO, "10-scripts", script), ...args], {
    cwd: join(REPO, "06-backend"),
    env: { DJANGO_SETTINGS_MODULE: "config.settings.local", JOBS_EAGER: "false", ...process.env },
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
}
const lastJson = (text) => JSON.parse(text.slice(text.indexOf("{")));

// ── the cases: the clerk's input and the screens' expected facts ───────────
const CASES = {
  M1: {
    clerk: "clerk",
    reads: { "E-M1": "4300", "W-M1": "315.0" }, // above each meter's 09/30 read, in its own unit
    fieldVisits: [{ template: "Opening read", forMeter: "W-M1", window: "morning" }],
    customer: {
      kind: "person", type: "residential", subtype: "single_family",
      full_name: "Avery Collins", email: "avery.collins@example.invalid", phone: "(512) 555-0188",
      dob: "02/14/1988", driving_licence: "TX40418877", search: "new",
    },
    billing: { mode: "pay_now", method: "check", amount: "175.00", reference: "2041" },
    expect: {
      feesTotal: "$175.00", // DEPOSIT $150.00 (Residential rule) + CONN $25.00 — no tax on either (OQ-BIL-12788 (a))
      firstBillSentence: null, // paid in full: nothing of the fees goes on the first bill
      services: ["Electric", "Water", "Sewer", "Trash"],
    },
  },
  // M2 (lane MVI-E2E-1, R4): a RETURNING customer found by the identifier on file (her SSN —
  // PO 2026-10-05 (1): found = an identifier on file) and LINKED; a co-owner; a water meter
  // with an irrigation sub-meter and a backflow device under it; Add to bill.
  M2: {
    clerk: "clerk",
    // W-M2 and its sub-meter SW-M2 are read devices; the backflow BF-M2 is not, so no box for it.
    reads: { "W-M2": "121.5", "SW-M2": "42.0" },
    customer: {
      kind: "person", type: "residential", subtype: "multi_family",
      full_name: "Rosa Delgado", email: "rosa.delgado@example.invalid", phone: "(512) 555-0161",
      dob: "04/12/1979", ssn: "512-44-7781", search: "found", link: true,
    },
    coOwners: [{
      full_name: "Luis Delgado", relationship: "spouse", dob: "09/03/1977",
      phone: "(512) 555-0143", email: "luis.delgado@example.invalid", responsible: true,
    }],
    billing: { mode: "add_to_bill" },
    expect: {
      feesTotal: "$175.00", // DEPOSIT $150.00 (Residential rule) + CONN $25.00, none taxed (OQ-BIL-12788 (a))
      // Add to bill records no money: every fee row, the deposit included, is on the first bill.
      firstBillSentence: "$175.00",
      services: ["Water", "Sewer"],
      // Rosa's two accounts on file (the world's seed) — shown on the match, still hers after the link.
      matchAccounts: ["AC-2026-00054", "AC-2026-00055"],
      matchOwes: "$84.20",
    },
    async walkExtra(page, key, f) {
      // The co-owner is on the move's Account tab (P1.10's read).
      await visit(page, key, "Accounts", `/moves/${f.move_no}?tab=account`, `${key}-w10-move-account.png`, [
        ["the move's Account tab names the co-owner Luis Delgado", "Luis Delgado"],
        ["the move's Account tab names the customer Rosa Delgado", "Rosa Delgado"],
      ]);
      // The backflow device stands under W-M2 on the same unit (BR-AST-003): its page names its meter.
      for (const device of f.devices || []) {
        await visit(page, key, "Assets", `/assets/${device.asset_id}`, `${key}-w2-asset-${device.asset_no}.png`, [
          [`${device.asset_no} names the meter it stands under (${device.parent_no})`, device.parent_no],
        ]);
      }
      // Still to collect is the DEPOSIT not taken: nothing was paid, so all $150.00 (P1.13: never taken partly).
      const billing = await bodyTextAt(page, `/moves/${f.move_no}?tab=billing`);
      check(key, "Payments", "Add to bill: the move's Billing tab reads Still to collect $150.00 (deposit not taken)",
        /Still to collect\s*\$150\.00/i.test(billing), (billing.match(/Still to collect\s*\$[\d,.]+/i) || [""])[0]);
    },
  },
  // M3 (lane MVI-E2E-1, R4): a senior on low income, new to the utility; the plan's CAP
  // assistance discount claimed by the CLERK (PO 2026-10-05 (2)) with its evidence uploaded;
  // a PART payment smaller than the deposit, in cash.
  M3: {
    clerk: "clerk",
    reads: { "E-M3": "8905", "G-M3": "1541" }, // above each meter's 09/30 read, in its own unit
    customer: {
      kind: "person", type: "residential", subtype: "senior_low_income",
      full_name: "Harold Whitfield", email: "harold.whitfield@example.invalid", phone: "(512) 555-0127",
      dob: "03/22/1951", driving_licence: "TX50122334", search: "new",
    },
    // The evidence: an assistance-evidence document on the customer step (P2.25 → BR-CUS-073).
    documents: [{ type: "assistance_evidence", file: "cap-award-letter.pdf" }],
    // ⚖️ DEF-RAT-9833 (PO D2 (b) and ruling 4, 2026-10-06): the clerk also ticks Paperless
    // ($1.00 off) with Harold's Paperless preference left Off — picking it switches it On.
    discounts: [{ code: "CAP", note: "LIHEAP award letter 2026" }, { code: "PAPERLESS", paired: "paperless" }],
    // $100.00 is less than the $150.00 deposit, so it is ALL prepay and the deposit stays on the
    // first bill (move_fees: "the deposit is never taken partly", BR-CUS-025 / BR-PAY-012).
    billing: { mode: "pay_now", method: "cash", amount: "100.00" },
    expect: {
      feesTotal: "$175.00", // DEPOSIT $150.00 + CONN $25.00; a discount never waives a fee
      firstBillSentence: "$75.00", // $175.00 − $100.00 paid today
      services: ["Electric", "Gas"],
    },
    async walkExtra(page, key, f) {
      const billing = await bodyTextAt(page, `/moves/${f.move_no}?tab=billing`);
      check(key, "Payments", "part payment: Still to collect reads $150.00 (the deposit is never taken partly)",
        /Still to collect\s*\$150\.00/i.test(billing), (billing.match(/Still to collect\s*\$[\d,.]+/i) || [""])[0]);
      check(key, "Payments", "part payment: the move's Billing tab shows $100.00 paid", has(billing, "$100.00"));
      // A move-in record has no Documents tab; the papers it carried are the ACCOUNT's (BR-CUS-073).
      await visit(page, key, "Accounts", `/accounts/${f.account_id}?tab=documents`, `${key}-w10-account-documents.png`, [
        ["the account's Documents tab lists the assistance evidence", f.evidence_name || "cap-award-letter.pdf"],
      ]);
      // The enrolment is read where Plans & Rates lists a discount's accounts (CR-166 round 3 task 6).
      await visit(page, key, "Billing", `/plans-rates/discounts/${f.discount_id}?tab=accounts`,
        `${key}-w11-discount-accounts.png`, [
          [`${f.discount_name}'s Accounts tab lists ${f.account_no}`, f.account_no],
          [`${f.account_no}'s ${f.discount_name} enrolment reads Pending (proof asked, not yet verified)`, "Pending"],
        ]);
    },
  },
  M4: { clerk: "clerk", todo: "company with owners, Tax ID 74-3051190 found and linked, card" },
  M5: { clerk: "clerk", todo: "RELIGIOUS exemption with certificate; Fire $84.00 on ONE line" },
  M6: { clerk: "clerk", todo: "two field visits" },
  M7: { clerk: "clerk", todo: "GOVERNMENT exemption, PO number on bills" },
};

// ── M4 and M5 (lane MVI-E2E-2, R4) — their own block, so the M2/M3 lane's hunks never
// touch these lines; built on E2E-1's hooks (matchAndLink, addCoOwner, addDocument,
// walkExtra). Expected figures follow the seed and the PO's rulings; the readback's
// EXPECT_M4_M5 holds the database half and its reasons.
Object.assign(CASES, {
  M4: {
    clerk: "clerk",
    reads: { "E-M4": "15100", "W-M4": "642.0" }, // above each meter's 09/30 read (15022 kWh, 640.5 kgal)
    customer: {
      kind: "company", type: "commercial", subtype: "small_commercial",
      full_name: "Northgate Provisions LLC", tax_id: "74-3051190",
      // Found = identifier on file (PO 2026-10-05 (1)): the Tax ID is on file → "found", and the clerk links it.
      search: "found", link: true,
    },
    // The company's owners — the co-owner cards in their *Owners and officers* form.
    coOwners: [
      { kind: "officer", full_name: "Hal Brennan", title: "Managing member", ownership_pct: "60", signs: true },
      { kind: "officer", full_name: "Priya Nandakumar", title: "Member", ownership_pct: "40", signs: false },
    ],
    billing: { mode: "pay_now", method: "card", amount: "325.00", reference: "4417" },
    expect: {
      feesTotal: "$325.00", // DEPOSIT $300.00 (Commercial rule on SCW-COM) + CONN $25.00, no tax on either
      services: ["Electric", "Water", "Sewer", "Trash", "Storm water"],
      matchAccounts: ["AC-2026-00056"], // Northgate's account on file (the world's seed)
    },
    // DEF-CUS-9776's four labels left with its fix (2.549.8): the account is named by its customer.
    knownDefects: {},
  },
  M5: {
    clerk: "clerk",
    reads: { "W-M5": "89.5" }, // above W-M5's 09/30 read of 88.0 kgal; the three fire lines are not meters
    customer: {
      kind: "company", type: "commercial", subtype: "institutional_non_profit",
      full_name: "Grace Fellowship of Cedar Ford", tax_id: "74-6021455", business_type: "non_profit",
      registered_in: "TX", search: "new",
      contact: { full_name: "Ruth Okafor", job_title: "Pastor", email: "office@gracefellowship.example.invalid",
        phone: "(512) 555-0193" },
    },
    // Billing clerks record exemptions themselves (PO 2026-10-05 (2)).
    exemption: { category: "Religious organisation", ref: "CF-REL-2026-0412", issued: "01/15/2026",
      expires: "12/31/2028", file: "religious-exemption-certificate.pdf" },
    billing: { mode: "pay_now", method: "check", amount: "325.00", reference: "1187" },
    expect: {
      feesTotal: "$325.00", // DEPOSIT $300.00 + CONN $25.00 — fees are never taxed at move-in, exempt or not
      services: ["Water", "Sewer", "Fire"],
    },
    // DEF-CUS-9776, 9774 and 9775's labels left with their fix (2.549.8).
    knownDefects: {},
    async walkExtra(page, key, f) {
      // The certificate the clerk recorded is on the account and on the move's Billing tab —
      // never "Tax exempt: No" / "Tax: Taxed" for an account holding one.
      const account = await bodyTextAt(page, `/accounts/${f.account_id}`);
      check(key, "Accounts", `the account shows exemption certificate ${f.exemption_ref}`, has(account, f.exemption_ref));
      // DEF-CUS-9774 — and says which tax it removes (ruling (A): the blanket flag stays false).
      check(key, "Accounts", "the account says Exempt from the City's tax",
        has(account, "Exempt from City of Cedar Ford utility tax"));
      const billing = await bodyTextAt(page, `/moves/${f.move_no}?tab=billing`);
      check(key, "Billing", `the move's Billing tab names exemption certificate ${f.exemption_ref}`,
        has(billing, f.exemption_ref), (billing.match(/Tax\s*\n?\s*\w+/) || [""])[0].replace(/\s+/g, " "));
      // DEF-CUS-9775 — never "Taxed" for the exempt church.
      check(key, "Billing", "the move's Billing tab says Exempt from the City's tax",
        has(billing, "Exempt from City of Cedar Ford utility tax"));
    },
  },
});

// ── M6, M7 and P4.24–P4.26 (lane MVI-E2E-3, R4) — their own block, so no other lane's hunks
// touch these lines; built on E2E-1's and E2E-2's hooks (fieldVisits, companyFields,
// companyContact, exemption, walkExtra, knownDefects). The readback's EXPECT_M6_M7 holds the
// database half and its reasons. P24/P25 are COPIES of M1/M2 (`worldCase`): the same input on a
// freshly restored world, then the act (`after`). P26 drives a REQUEST (`run`), not the wizard.
Object.assign(CASES, {
  M6: {
    clerk: "clerk",
    // Above each meter's 09/30 read (52310 kWh, 7710 ccf, 203.0 kgal); PV-M6 is not a read device.
    reads: { "E-M6": "52400", "G-M6": "7725", "W-M6": "205.5" },
    // Two field visits (the PO's matrix): the electric meter's opening read in the morning, the gas
    // turn-on in the afternoon.
    fieldVisits: [
      { template: "Opening read", forMeter: "E-M6", window: "morning" },
      { template: "Reconnect visit", forMeter: "G-M6", window: "afternoon" },
    ],
    customer: {
      kind: "company", type: "industrial", subtype: "light_industrial",
      full_name: "Foundry Works Fabrication Inc.", tax_id: "74-8830215", business_type: "corporation",
      registered_in: "TX", search: "new",
      contact: { full_name: "Dale Mercer", job_title: "Plant manager", email: "dale.mercer@foundryworks.example.invalid",
        phone: "(512) 555-0152" },
    },
    // CASH: the tender received on the spot — does a deposit the utility HOLDS stay off the first bill?
    billing: { mode: "pay_now", method: "cash", amount: "525.00" },
    expect: {
      feesTotal: "$525.00", // DEPOSIT $500.00 (Industrial rule on SCW-IND) + CONN $25.00, none taxed
      services: ["Electric", "Gas", "Water", "Solar"],
    },
    knownDefects: {
      // DEF-CUS-9776's labels left with its fix (2.549.8).
      "Move-in completed prints no raw server code": "DEF-CUS-9785",
    },
    async walkExtra(page, key, f) {
      // The inverter stands behind E-M6 (BR-AST-003) and the move-in moved no equipment.
      for (const device of f.devices || []) {
        await visit(page, key, "Assets", `/assets/${device.asset_id}`, `${key}-w2-asset-${device.asset_no}.png`, [
          [`${device.asset_no} names the meter it stands behind (${device.parent_no})`, device.parent_no],
        ]);
      }
      // The move's Work tab lists BOTH orders the move-in raised.
      await visit(page, key, "Work", `/moves/${f.move_no}?tab=work`, `${key}-w10-move-work.png`,
        f.work_orders.map((o) => [`the move's Work tab lists ${o.order_no} (${o.template})`, o.order_no]));
    },
  },
  M7: {
    clerk: "clerk",
    reads: { "W-M7": "1462.0" }, // above W-M7's 09/30 read of 1450.0 kgal; the three carts are not meters
    customer: {
      // Government · Schools, the PO's M7: offered once the utility clears Government's legacy flag
      // on Settings (the world's `offer_government`; DEF-CUS-9786 / DEF-CUS-9808, lane DEF-9786-9788).
      kind: "company", type: "government", subtype: "schools",
      full_name: "Cedar Ford Independent School District", tax_id: "74-6000118", business_type: "government",
      registered_in: "TX", search: "new",
      contact: { full_name: "Marisol Vega", job_title: "Facilities director", email: "facilities@cfisd.example.invalid",
        phone: "(512) 555-0174" },
    },
    offers: [["government", "Government (the PO's M7: Government · Schools)"]],
    poNumber: "PO-2026-118", // *PO on bills* (image 40), on the ACCOUNT (accounts.po_number)
    // Billing clerks record exemptions themselves (PO 2026-10-05 (2)).
    exemption: { category: "Government entity", ref: "CF-GOV-2026-0077", issued: "07/01/2026",
      expires: "06/30/2027", file: "government-exemption-letter.pdf" },
    billing: { mode: "add_to_bill" }, // a school district is invoiced; it does not pay at a counter
    expect: {
      feesTotal: "$25.00", // no deposit rule for Government (the seed) + CONN $25.00
      firstBillSentence: "$25.00",
      services: ["Water", "Sewer", "Trash"],
    },
    knownDefects: {
    },
    async walkExtra(page, key, f) {
      const account = await bodyTextAt(page, `/accounts/${f.account_id}`);
      check(key, "Accounts", `the account shows exemption certificate ${f.exemption_ref}`, has(account, f.exemption_ref));
      check(key, "Accounts", `the account shows its PO ${f.po_number} (printed on every bill)`, has(account, f.po_number));
      await visit(page, key, "Accounts", `/moves/${f.move_no}?tab=account`, `${key}-w10-move-account.png`, [
        [`the move's Account tab shows the PO ${f.po_number}`, f.po_number],
      ]);
      const billing = await bodyTextAt(page, `/moves/${f.move_no}?tab=billing`);
      check(key, "Billing", `the move's Billing tab names exemption certificate ${f.exemption_ref}`,
        has(billing, f.exemption_ref), (billing.match(/Tax\s*\n?\s*\w+/) || [""])[0].replace(/\s+/g, " "));
    },
  },
});
// P4.24 and P4.25 are copies of M1 and M2: the same input, then the act on the details view.
Object.assign(CASES, {
  // Cancel is offered on Scheduled / Waiting on a read and NOT on Completed (the PO's actions table,
  // decision log "DETAILS-VIEW ACTIONS BY STATUS RULED AS PROPOSED"), so M1's copy leaves W-M1 unread.
  P24: { ...CASES.M1, worldCase: "M1",
    title: "P4.24 · a copy of M1, then Cancel move-in… (J6's four reversals; the unit Vacant again)", reads: { "E-M1": "4300" }, leaveUnread: ["W-M1"],
    // DEF-CUS-9789 FIXED (2.549.16): M1's $175.00 by check 2041 is still PROCESSING, so Cancel
    // CALLS OFF both payments ($150.00 deposit + $25.00) and refunds nothing — nothing arrived.
    // Cleared money is still ONE refund (the PO's signed $175.00, `test_cr171_oq_cus_12790_*`).
    async after(page, key, f) { await cancelAfterComplete(page, key, f); } },
  // Change move-in date is offered on Scheduled / Waiting on a read only (the same table), so M2's
  // copy leaves the irrigation sub-meter SW-M2 unread.
  // (step 1 lets a read go blank only when a visit is booked to take it — StepUnit.missingOpeningReads).
  P25: { ...CASES.M2, worldCase: "M2",
    title: "P4.25 · a copy of M2, then Change move-in date 10/10/2026 → 10/15/2026",
    // DEF-CUS-9790 FIXED (2.549.16): the move-in reads the account's new start everywhere.
    reads: { "W-M2": "121.5" }, leaveUnread: ["SW-M2"],
    // The visit's *For* list offers the connection's METER (W-M2), not its sub-meter.
    fieldVisits: [{ template: "Opening read", forMeter: "W-M2", window: "morning" }],
    newDate: "10/15/2026", newDateIso: "2026-10-15",
    async after(page, key, f) { await changeMoveInDate(page, key, f, this); } },
  // The proration half of P4.25 is ALSO read on a copy of M1 (W-M1 left for its booked visit, as
  // P24): M2's first bill could not be priced until DEF-MET-9773 was fixed (2.549.9), so both stay.
  P25B: { ...CASES.M1, worldCase: "M1",
    title: "P4.25 (proration) · a copy of M1, then Change move-in date 10/10/2026 → 10/15/2026",
    // DEF-CUS-9790 FIXED (2.549.16): the move-in reads the account's new start everywhere.
    reads: { "E-M1": "4300" }, leaveUnread: ["W-M1"],
    newDate: "10/15/2026", newDateIso: "2026-10-15",
    async after(page, key, f) { await changeMoveInDate(page, key, f, this); } },
  P26: { clerk: "clerk", worldCase: "M1",
    title: "P4.26 · SR R1 To approve → Ask for more → Approve → Start → Complete; SR R2 Declined", async run(page, key) { await requestPath(page, key); } },
});

// ── lane MVI-E2E-3's helpers ──────────────────────────────────────────────
// A details-view action: a drawn button, or an item under More ▾.
async function pressAction(page, id) {
  const button = page.locator(`[data-testid="move-action-${id}"]`);
  if ((await button.count()) > 0) return button.first().click();
  await page.locator("[data-move-more] summary").click();
  await page.locator(`[data-testid="move-more-${id}"]`).click();
}
async function moveStatus(page) {
  return page.locator("[data-move-status]").first().getAttribute("data-move-status", { timeout: 15000 }).catch(() => null);
}
async function awaitStatus(page, want) {
  return page.waitForSelector(`[data-move-status="${want}"]`, { timeout: 20000 }).then(() => true, () => false);
}
async function submitModal(page) {
  await page.locator('[role="dialog"] button[type="submit"]').last().click();
}

// P4.24 — Cancel move-in… on the committed copy of M1: the modal lists J6's four lines, then the press.
async function cancelAfterComplete(page, key, f) {
  await page.goto(`${BASE}/${TENANT}/moves/${f.move_no}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await pressAction(page, "cancel");
  const listed = await page.waitForSelector("[data-cancel-lines]", { timeout: 20000 }).then(() => true, () => false);
  const lines = listed ? await page.locator("[data-cancel-lines]").innerText() : await page.locator('[role="dialog"]').innerText().catch(() => "");
  check(key, "Accounts", "Cancel move-in… lists what it reverses before the press (J6)", listed, lines.slice(0, 200));
  check(key, "Accounts", `the modal names the account ${f.account_no} closing`, has(lines, f.account_no));
  check(key, "Payments", "the modal calls off the uncleared $150.00 and $25.00 and names no refund (DEF-CUS-9789)",
    has(lines, "$150.00") && has(lines, "$25.00") && /called off/i.test(lines) && !/refund/i.test(lines),
    lines.replace(/\s+/g, " "));
  for (const order of f.work_orders) check(key, "Work", `the modal names ${order.order_no} canceled`, has(lines, order.order_no));
  check(key, "Units", "the modal says the unit is vacant again", /vacant/i.test(lines));
  await shot(page, `${key}-a1-cancel-modal.png`);
  await submitModal(page);
  const cancelled = await awaitStatus(page, "cancelled");
  check(key, "Accounts", "the move-in reads Canceled after the press", cancelled, `status ${await moveStatus(page)}`);
  await shot(page, `${key}-a2-cancelled.png`);
  const back = lastJson(py("cr171_e2e_matrix_readback.py", ["--case", key, "--move", f.move_no, "--after", "cancel"]));
  for (const row of back.checks) check(key, row.module, row.name, row.pass, row.pass ? "" : row.detail);
  await visit(page, key, "Units", `/premises/units/${f.unit_id}`, `${key}-a3-unit.png`, [["the unit reads Vacant again", "Vacant"]]);
  await visit(page, key, "Accounts", `/accounts/${f.account_id}`, `${key}-a4-account.png`, [["the account reads Closed", "Closed"]]);
  for (const order of f.work_orders) {
    await visit(page, key, "Work", `/work/orders/${order.order_no}`, `${key}-a5-${order.order_no}.png`,
      [[`${order.order_no} reads Canceled`, "Cancel"]]);
  }
  await visit(page, key, "Payments", `/accounts/${f.account_id}?tab=payments`, `${key}-a6-payments.png`,
    [["the account's Payments tab shows the called-off $150.00", "150.00"]]);
  // The unit is offered again on a new move-in's step 1 (a cancelled account never occupies).
  await page.goto(`${BASE}/${TENANT}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => (document.querySelector("#mvi_unit")?.options.length ?? 0) > 1, null, { timeout: 30000 })
    .catch(() => undefined);
  const offered = await page.$$eval("#mvi_unit option", (os) => os.map((o) => o.textContent || "")).catch(() => []);
  check(key, "Units", `${f.unit_no} is offered as vacant again on a new move-in`, offered.some((o) => o.includes(f.unit_no)));
}

// P4.25 — Change move-in date on the committed copy of M2.
async function changeMoveInDate(page, key, f, spec) {
  await page.goto(`${BASE}/${TENANT}/moves/${f.move_no}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await pressAction(page, "changeDate");
  await page.waitForSelector('[role="dialog"] #date');
  // A native date input takes ISO; a typed one takes the utility's MM/DD/YYYY.
  await page.fill('[role="dialog"] #date', spec.newDateIso).catch(() => page.fill('[role="dialog"] #date', spec.newDate));
  await page.press('[role="dialog"] #date', "Tab");
  await shot(page, `${key}-a1-change-date-modal.png`);
  await submitModal(page);
  await page.waitForSelector('[role="dialog"]', { state: "detached", timeout: 20000 }).catch(() => undefined);
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(800);
  const text = await bodyText(page);
  check(key, "Accounts", `the details view reads the new move-in date ${spec.newDate}`, has(text, spec.newDate),
    (text.match(/\d{2}\/\d{2}\/2026/g) || []).join(" "));
  await shot(page, `${key}-a2-changed.png`);
  // Read again from a fresh load, so a stale screen and a stale SERVER are told apart.
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(800);
  const fresh = await bodyText(page);
  const chip = (await page.locator("[data-move-status]").first().locator("xpath=ancestor::span[1]/..").innerText()
    .catch(() => "")).replace(/\s+/g, " ");
  check(key, "Accounts", `after a reload the details view reads the new move-in date ${spec.newDate}`, has(fresh, spec.newDate),
    `chip "${chip.slice(0, 80)}" · dates on screen: ${(fresh.match(/\d{2}\/\d{2}\/2026/g) || []).join(" ")}`);
  await shot(page, `${key}-a2b-reloaded.png`);
  // The Move-ins list is a tab of Accounts (`moveShared.MOVE_INS_TAB_PATH`); `/move-ins` alone is
  // no screen ("This screen is not built yet") — lane DEF-CUS-9789, 2026-10-06.
  const list = await bodyTextAt(page, "/accounts?tab=move-ins");
  const row = (list.split("\n").find((l) => l.includes(f.move_no)) || "") + "";
  check(key, "Accounts", `the Move-ins list dates ${f.move_no} ${spec.newDate}`, has(list, spec.newDate),
    (list.match(new RegExp(`${f.move_no}[^\n]*`)) || [row])[0].slice(0, 160));
  await shot(page, `${key}-a2c-list.png`);
  // The base charges the first bill carried BEFORE the change (the readback's preview, from the
  // move-in date as completed) — the "was" of the proration check. After the change the account
  // itself opens on the new day, so a preview "from the old day" no longer exists to compare with.
  const baseWas = (f.first_bill?.lines || []).filter(([kind]) => kind === "base")
    .reduce((sum, [, , amount]) => sum + Math.round(Number(amount) * 100), 0) / 100;
  const back = lastJson(py("cr171_e2e_matrix_readback.py",
    ["--case", key, "--move", f.move_no, "--after", "date", ...(f.first_bill?.priced ? ["--was", baseWas.toFixed(2)] : [])]));
  for (const row of back.checks) check(key, row.module, row.name, row.pass, row.pass ? "" : row.detail);
  await visit(page, key, "Accounts", `/accounts/${f.account_id}`, `${key}-a3-account.png`,
    [[`the account reads opened ${spec.newDate}`, spec.newDate]]);
}

// P4.26 — a request through To approve → Ask for more → Approve → Start → Complete; one Declined.
async function requestPath(page, key) {
  const R1 = WORLD.requests.R1;
  const R2 = WORLD.requests.R2;
  if (!R1 || !R2) throw new Error("the world has no requests — run `cr171_e2e_matrix_world.py requests` first");
  await page.goto(`${BASE}/${TENANT}/moves/${R1.request_no}`, { waitUntil: "domcontentloaded" });
  check(key, "Accounts", `${R1.request_no} reads To approve`, await awaitStatus(page, "to_approve"), `status ${await moveStatus(page)}`);
  await shot(page, `${key}-r1-1-to-approve.png`);
  await pressAction(page, "askForMore");
  await page.waitForSelector('[role="dialog"] #text');
  await page.fill('[role="dialog"] #text', "Please send a copy of your lease.");
  await shot(page, `${key}-r1-2-ask-modal.png`);
  await submitModal(page);
  check(key, "Accounts", `Ask for more → ${R1.request_no} reads Waiting on customer`, await awaitStatus(page, "waiting_on_customer"),
    `status ${await moveStatus(page)}`);
  await shot(page, `${key}-r1-3-waiting.png`);
  await pressAction(page, "approve");
  await page.waitForSelector('[role="dialog"]');
  await shot(page, `${key}-r1-4-approve-modal.png`);
  await submitModal(page);
  check(key, "Accounts", `Approve → the move-in reads Not started`, await awaitStatus(page, "not_started"), `status ${await moveStatus(page)}`);
  await shot(page, `${key}-r1-5-not-started.png`);
  await pressAction(page, "start");
  const started = await page.waitForURL(/move-ins\/new\?request=/, { timeout: 20000 }).then(() => true, () => false);
  check(key, "Accounts", "Start opens the four-step form FROM the request", started, page.url());
  const spec = {
    reads: { [R1.meter]: "97.5" }, fromRequest: R1, date: "10/12/2026",
    customer: { kind: "person", type: "residential", subtype: "single_family", full_name: R1.applicant,
      email: "maya.okonkwo@example.invalid", phone: "(512) 555-0131", dob: "06/02/1990",
      driving_licence: "TX61200457", search: "new" },
    billing: { mode: "add_to_bill" },
    expect: { feesTotal: "$175.00", firstBillSentence: "$175.00", services: ["Water", "Sewer"] },
  };
  const { moveNo } = await submit(page, key, spec, { unit_no: R1.unit_no });
  // R2 — Decline.
  await page.goto(`${BASE}/${TENANT}/moves/${R2.request_no}`, { waitUntil: "domcontentloaded" });
  check(key, "Accounts", `${R2.request_no} reads To approve`, await awaitStatus(page, "to_approve"), `status ${await moveStatus(page)}`);
  await pressAction(page, "decline");
  await page.waitForSelector('[role="dialog"] #text');
  await page.fill('[role="dialog"] #text', "No service can start at this address yet.");
  await shot(page, `${key}-r2-1-decline-modal.png`);
  await submitModal(page);
  check(key, "Accounts", `Decline → ${R2.request_no} reads Declined`, await awaitStatus(page, "declined"), `status ${await moveStatus(page)}`);
  await shot(page, `${key}-r2-2-declined.png`);
  const back = lastJson(py("cr171_e2e_matrix_readback.py", ["--case", key, "--after", "requests"]));
  for (const row of back.checks) check(key, row.module, row.name, row.pass, row.pass ? "" : row.detail);
  if (moveNo) {
    await visit(page, key, "Accounts", `/moves/${moveNo}`, `${key}-r1-6-move.png`, [
      [`the completed move-in ${moveNo} names ${R1.applicant}`, R1.applicant],
      [`the completed move-in carries its request ${R1.request_no}`, R1.request_no],
    ]);
  }
  await visit(page, key, "Accounts", `/moves/${R2.request_no}?tab=messages`, `${key}-r2-3-messages.png`, [
    ["the declined request's Messages tab lists the letter to the applicant", R2.applicant],
  ]);
}

// ── reporting ─────────────────────────────────────────────────────────────
const results = [];
function check(caseKey, module, name, pass, detail = "") {
  results.push({ caseKey, module, name, pass });
  // A screen FAIL a case expects today is labelled with its filed defect (lane MVI-E2E-2).
  const known = CASES[caseKey]?.knownDefects?.[name];
  if (known && !pass) detail = `[${known}] ${detail}`;
  console.log(`  ${pass ? "PASS" : "FAIL"}  ${caseKey} · ${module.padEnd(9)} · ${name}${detail ? " — " + detail : ""}`);
}

// ── browser helpers ───────────────────────────────────────────────────────
async function signIn(context, email, password) {
  const page = await context.newPage();
  page.setDefaultTimeout(25000);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  return page;
}
async function shot(page, name) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(300);
  const tall = await page.evaluate(() =>
    Math.max(...[...document.querySelectorAll("*")].map((el) => el.scrollHeight), document.body.scrollHeight),
  );
  await page.setViewportSize({ width: 1440, height: Math.min(Math.max(tall + 120, 900), 6000) });
  await page.waitForTimeout(200);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
}
const bodyText = (page) => page.locator("body").innerText();
// A screen's text without a photograph (the photograph is `visit`'s).
async function bodyTextAt(page, path) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(800);
  return bodyText(page);
}
const has = (text, needle) => text.toLowerCase().includes(String(needle).toLowerCase());
const onStep = (page, n) =>
  page.waitForSelector(`[data-wizard-step="${n}"][data-state="active"]`, { timeout: 20000 });
const cont = (page) => page.getByRole("button", { name: "Continue" }).click();
// Continue, and if the next step does not open, say what the screen refused with.
async function advance(page, key, n) {
  await cont(page);
  const opened = await onStep(page, n).then(() => true, () => false);
  if (!opened) {
    const alerts = await page.locator('[role="alert"], [aria-invalid="true"]').allInnerTexts().catch(() => []);
    const invalid = await page.$$eval('[aria-invalid="true"]', (els) => els.map((e) => e.id || e.getAttribute("name")));
    await shot(page, `${key}-FAILED-step${n - 1}.png`);
    throw new Error(`step ${n} did not open — alerts ${JSON.stringify(alerts.slice(0, 5))} · invalid ${JSON.stringify(invalid)}`);
  }
}

// ── step helpers for M2/M3 (lane MVI-E2E-1) ───────────────────────────────
// Found by the identifier on file → the block names the customer, her accounts and
// what she owes; Link makes her the move-in's customer (no new customer is written).
async function matchAndLink(page, key, spec) {
  const block = page.locator(`[data-match-block="${spec.customer.search}"]`).first();
  const text = await block.innerText();
  check(key, "Accounts", `the match names ${spec.customer.full_name}`, has(text, spec.customer.full_name), text.slice(0, 160));
  for (const account of spec.expect.matchAccounts || []) {
    check(key, "Accounts", `the match lists her account ${account}`, has(text, account));
  }
  if (spec.expect.matchOwes) {
    check(key, "Accounts", `the match reads what she owes, ${spec.expect.matchOwes}`, has(text, spec.expect.matchOwes),
      (text.match(/\$[\d,]+\.\d{2}/g) || []).join(" "));
  }
  if (spec.customer.link) {
    await block.locator('[data-match-action="link"]').click();
    const linked = await page.waitForSelector('[data-customer-match="linked"]', { timeout: 10000 }).then(() => true, () => false);
    check(key, "Accounts", `Link makes ${spec.customer.full_name} the move-in's customer (Linked)`, linked);
  }
}
async function addCoOwner(page, key, n, co) {
  // `kind: "officer"` is a company's owner card (M4, lane MVI-E2E-2): title, share, signs.
  const kind = co.kind || "co_owner";
  if (n === 0) await page.locator(`#${kind}_enabled`).check({ force: true });
  else await page.click("[data-co-owner-add]");
  const id = (field) => `#${kind}_${n}_${field}`;
  await page.waitForSelector(id("full_name"));
  await page.fill(id("full_name"), co.full_name);
  if (co.title) await page.fill(id("title"), co.title);
  if (co.ownership_pct) await page.fill(id("ownership_pct"), co.ownership_pct);
  if (co.signs) await page.locator(id("signs_for_company")).check({ force: true });
  if (co.relationship) await page.selectOption(id("relationship"), co.relationship);
  if (co.dob) {
    await page.fill(id("date_of_birth"), co.dob);
    await page.keyboard.press("Tab");
  }
  if (co.phone) await page.fill(id("phone"), co.phone);
  if (co.email) await page.fill(id("email"), co.email);
  if (co.responsible) await page.locator(id("responsible_for_bills")).check({ force: true });
  check(key, "Accounts", `co-owner card ${n + 1} holds ${co.full_name}`,
    (await page.inputValue(id("full_name"))) === co.full_name);
}
async function addDocument(page, key, doc) {
  const table = page.locator('[data-array="move-in-documents"]');
  const before = await table.locator("tbody tr").count();
  await page.click('[data-array-action="add-document"]');
  const row = table.locator("tbody tr").nth(before);
  await row.locator('select[data-cell="doc-type"]').selectOption(doc.type);
  const path = join((await import("node:os")).tmpdir(), doc.file);
  // A one-page PDF written by the runner — the evidence's bytes are an illustration.
  const { writeFileSync } = await import("node:fs");
  writeFileSync(path, "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj " +
    "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n");
  await row.locator('input[type="file"]').setInputFiles(path);
  const staged = await row.locator('[data-doc-file="staged"]').waitFor({ timeout: 15000 }).then(() => true, () => false);
  check(key, "Accounts", `the ${doc.type} document is uploaded on the customer step`, staged,
    staged ? "" : await row.innerText());
}
async function claimDiscount(page, key, claim) {
  if (!(await page.locator("#move_in_discounts_on").isChecked())) await page.locator("#move_in_discounts_on").check({ force: true });
  const table = page.locator('[data-array="move-in-discounts"]');
  await table.waitFor();
  // A second claim takes a new row (+ Add discount) once the last row holds a pick.
  if ((await table.locator('select[data-cell="discount"]').last().inputValue()) !== "") {
    await table.getByRole("button", { name: "+ Add discount" }).click();
  }
  const select = table.locator('select[data-cell="discount"]').last();
  const options = await select.locator("option").allInnerTexts();
  const pick = await select.locator("option").evaluateAll(
    (os, code) => (os.find((o) => (o.textContent || "").toUpperCase().includes(code)) || {}).value || "",
    claim.code,
  );
  // The option's words are the discount's NAME (B14 rule 31); the code is matched only when the
  // name carries it, so fall back to the plan's own discount named for assistance.
  const value = pick || (await select.locator("option").evaluateAll(
    (os) => (os.find((o) => /assist|low.income|cap/i.test(o.textContent || "")) || {}).value || ""));
  check(key, "Payments", `the Discounts list offers the plan's ${claim.code}`, value !== "", options.join(" | "));
  // DEF-CUS-9779: the system grants Municipal account itself, so the claim list never offers it.
  // ⚖️ AMENDED 2026-10-06 (DEF-RAT-9833, PO D2 (b): "Offer Autopay and Paperless at move-in as
  // drawn"): Autopay and Paperless ARE offered again, and picking one switches its preference On.
  const automatic = options.filter((o) => /municipal/i.test(o));
  check(key, "Payments", "the Discounts list offers no Municipal account", automatic.length === 0,
    automatic.join(" | "));
  const paired = options.filter((o) => /paperless|autopay/i.test(o));
  check(key, "Payments", "the Discounts list offers Autopay and Paperless (DEF-RAT-9833)", paired.length === 2,
    options.join(" | "));
  if (claim.paired) {
    const before = await page.locator(`#${claim.paired}`).inputValue().catch(() => "");
    if (value) await select.selectOption(value);
    const after = await page.locator(`#${claim.paired}`).inputValue().catch(() => "");
    check(key, "Payments", `picking ${claim.code} switches the ${claim.paired} preference On (DEF-RAT-9833)`,
      after === "on", `${before} → ${after}`);
    await page.locator('[data-billing-section="preferences"]').screenshot(
      { path: join(OUT, `${key}-3-preferences-after-${claim.paired}.png`) }).catch(() => {});
  } else if (value) await select.selectOption(value);
  await table.screenshot({ path: join(OUT, `${key}-3-discounts.png`) }).catch(() => {});
  console.log(`  [${key}] discount options: ${options.join(" | ")}`);
  if (claim.note) await table.locator('input[data-cell="note"]').last().fill(claim.note);
}

// ── step helpers for M4/M5 (lane MVI-E2E-2) ───────────────────────────────
// The kit's checkbox is an sr-only input: tick it through its label, once.
async function tick(page, id) {
  if (!(await page.locator(`#${id}`).isChecked())) await page.locator(`label[for="${id}"]`).first().click();
}
// A company's own fields, before Search customer ID (the Tax ID is what the search asks).
async function companyFields(page, c) {
  if (c.business_type) await page.selectOption("#business_type", c.business_type);
  if (c.tax_id) await page.fill("#tax_id", c.tax_id);
  if (c.registered_in) await page.selectOption("#registered_in", c.registered_in);
}
// A NEW company's contact person (a linked one brings its own).
async function companyContact(page, c) {
  if (!c.contact) return;
  await page.fill("#contact_full_name", c.contact.full_name);
  if (c.contact.job_title) await page.fill("#contact_job_title", c.contact.job_title);
  await page.fill("#contact_email", c.contact.email);
  await page.fill("#contact_phone", c.contact.phone);
}
// Step 3, a tax exemption with its certificate — recorded by the billing clerk (PO 2026-10-05 (2)).
async function exemption(page, key, ex) {
  const box = page.locator("#move_in_tax_on");
  check(key, "Billing", "step 3 offers Tax exempt to the billing clerk", (await box.count()) > 0);
  if ((await box.count()) === 0) return;
  await tick(page, "move_in_tax_on");
  await page.waitForFunction(() => (document.querySelector("#move_in_tax_category")?.options.length ?? 0) > 1,
    null, { timeout: 15000 }).catch(() => undefined);
  const value = await page.$eval("#move_in_tax_category",
    (s, label) => [...s.options].find((o) => (o.textContent || "").includes(label))?.value ?? "", ex.category);
  check(key, "Billing", `the exemption list offers "${ex.category}"`, value !== "");
  if (value) await page.selectOption("#move_in_tax_category", value);
  await page.fill("#move_in_tax_ref", ex.ref);
  for (const [id, day] of [["#move_in_tax_issued", ex.issued], ["#move_in_tax_expires", ex.expires]]) {
    // A native date input takes ISO; a typed one takes the utility's MM/DD/YYYY.
    const [mm, dd, yyyy] = day.split("/");
    await page.fill(id, `${yyyy}-${mm}-${dd}`).catch(() => page.fill(id, day));
    await page.press(id, "Tab");
  }
  const pdf = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");
  await page.setInputFiles("#move_in_tax_certificate", { name: ex.file, mimeType: "application/pdf", buffer: pdf });
  const chosen = await page.waitForSelector('[data-tax-certificate="chosen"]', { timeout: 10000 }).then(() => true, () => false);
  check(key, "Billing", "the certificate PDF is chosen on step 3", chosen);
}

// ── 1 · submit through the browser ─────────────────────────────────────────
async function submit(page, key, spec, seeded) {
  if (!spec.fromRequest) {
  await page.goto(`${BASE}/${TENANT}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => (document.querySelector("#mvi_unit")?.options.length ?? 0) > 1, null, {
    timeout: 30000,
  });
  const value = await page.$eval(
    "#mvi_unit",
    (select, unit) => [...select.options].find((o) => o.textContent.includes(unit))?.value ?? "",
    seeded.unit_no,
  );
  check(key, "Units", `${seeded.unit_no} is offered as vacant before the move-in`, value !== "");
  if (!value) throw new Error(`unit ${seeded.unit_no} is not in the vacant list`);
  await page.selectOption("#mvi_unit", value);
  } else {
    // Started FROM an approved request (P4.26, lane MVI-E2E-3): the form arrives on the request's unit.
    const ready = await page.waitForSelector('[data-unit-card="ready"]', { timeout: 30000 }).then(() => true, () => false);
    const card = ready ? await page.locator('[data-unit-card="ready"]').innerText() : "";
    check(key, "Units", `the form opens on the request's unit ${seeded.unit_no}`, has(card, seeded.unit_no),
      card.replace(/\s+/g, " ").slice(0, 120));
  }
  await page.waitForSelector('[data-unit-card="ready"]');
  await page.waitForSelector('[data-array="move-in-meters"] tbody tr');
  await page.waitForLoadState("networkidle");
  const dateBox = page.locator("#opened_at");
  await dateBox.fill(spec.date || DATE);
  await dateBox.press("Tab");
  await page.waitForLoadState("networkidle");

  // Step 1 · every service the case starts is listed, each meter takes its opening read.
  const step1 = await page.locator('[data-array="move-in-meters"]').innerText();
  for (const service of spec.expect.services) {
    check(key, "Units", `step 1 lists ${service}`, has(step1, service));
  }
  for (const [meter, read] of Object.entries(spec.reads)) {
    const box = page.locator(`#moveIn-open-read-${meter}`);
    const present = (await box.count()) > 0;
    check(key, "Assets", `step 1 asks an opening read for ${meter}`, present);
    if (present) await box.fill(read);
  }
  for (const box of await page.locator("[data-opening-read] input").all()) {
    // A meter the case leaves unread on purpose (P24, lane MVI-E2E-3) is not an unasked box.
    const boxId = (await box.getAttribute("id")) || "";
    const left = (spec.leaveUnread || []).some((m) => boxId.endsWith(m));
    if ((await box.inputValue()) === "" && !left) {
      check(key, "Assets", "no meter asks an opening read the case did not name", false,
        (await box.getAttribute("id")) || "?");
    }
  }
  // Field visits: Work order template, For (the meter), Window, Assign to.
  for (const [n, visit] of (spec.fieldVisits || []).entries()) {
    await page.click('[data-array-action="add-work-order"]');
    await page.locator(`#move_in-fv-${n}-workOrder`).click();
    // THIS row's list only: the first row's (closed) list keeps its options in the page, so an
    // unscoped match picks a hidden one for the second visit (lane MVI-E2E-3, M6's two orders).
    const option = page.locator(`[role="option"][id^="move_in-fv-${n}-workOrder"]`, { hasText: visit.template }).first();
    check(key, "Work", `the Work order list offers "${visit.template}"`, (await option.count()) > 0);
    await option.click();
    const forOptions = await page.$$eval(`#move_in-fv-${n}-for option`, (os) =>
      os.map((o) => ({ value: o.value, text: o.textContent || "" })),
    );
    const target = forOptions.find((o) => o.text.includes(visit.forMeter)) || forOptions[1];
    if (target) await page.selectOption(`#move_in-fv-${n}-for`, target.value);
    await page.selectOption(`#move_in-fv-${n}-window`, visit.window);
    const holders = await page.$$eval(`#move_in-fv-${n}-assignee option`, (os) => os.map((o) => o.value));
    if (holders.length > 1) await page.selectOption(`#move_in-fv-${n}-assignee`, holders[1]);
    await page.waitForLoadState("networkidle");
  }
  await shot(page, `${key}-1-unit.png`);
  await advance(page, key, 2);
  await page.waitForSelector("[data-move-in-customer]");

  // Step 2 · the customer.
  const c = spec.customer;
  await page.locator("label", { hasText: c.kind === "company" ? /^Company$/ : /^Person$/ }).first().click();
  // A category the PO's matrix names, asked of the picker before the case enters the one it can
  // (M7: Government is legacy until the utility offers it again — DEF-CUS-9808, lane DEF-9786-9788).
  for (const [code, label] of spec.offers || []) {
    // The categories arrive from the server: wait for them, or an empty list reads as "not offered".
    await page.waitForFunction(() => (document.querySelector("#account_type")?.options.length ?? 0) > 2, null,
      { timeout: 20000 }).catch(() => undefined);
    const codes = await page.$$eval("#account_type option", (os) => os.map((o) => o.value));
    check(key, "Accounts", `step 2 offers ${label}`, codes.includes(code), `offered: ${codes.filter(Boolean).join(", ")}`);
  }
  await page.selectOption("#account_type", c.type);
  // The sub-type list loads AFTER the type is picked; asking for it at once raced it and
  // skipped the pick silently (DEF-MET-9802: 2 runs of 4 read the sub-type as None).
  if (c.subtype) await page.locator("#account_subtype").waitFor({ timeout: 8000 }).catch(() => undefined);
  if (c.subtype && (await page.locator("#account_subtype").count()) > 0) {
    await page.selectOption("#account_subtype", c.subtype);
  }
  await page.fill("#full_name", c.full_name);
  if (c.email) await page.fill("#email", c.email);
  if (c.phone) await page.fill("#phone", c.phone);
  if (c.dob) {
    await page.fill("#dob", c.dob);
    await page.keyboard.press("Tab");
  }
  if (c.driving_licence) await page.fill("#driving_licence", c.driving_licence);
  if (c.ssn) await page.fill("#ssn", c.ssn);
  if (c.kind === "company") await companyFields(page, c); // M4/M5
  if (c.search) {
    await page.click("[data-search-customer-id]");
    const verdict = c.search === "new" ? '[data-customer-match="new"]' : `[data-match-block="${c.search}"]`;
    const seen = await page.waitForSelector(verdict, { timeout: 15000 }).then(() => true, () => false);
    check(key, "Accounts", `Search customer ID answers "${c.search}"`, seen);
    // A match is shown only when our rule says match (PO 2026-10-05 (1)).
    if (c.search === "new") {
      check(key, "Accounts", "no match block is drawn for a new person",
        (await page.locator("[data-match-block]").count()) === 0);
    }
    if (c.search !== "new" && seen) await matchAndLink(page, key, spec);
  }
  if (c.kind === "company") await companyContact(page, c); // M5
  if (spec.poNumber) await page.fill("#po_number", spec.poNumber); // M7 (lane MVI-E2E-3)
  for (const [n, co] of (spec.coOwners || []).entries()) await addCoOwner(page, key, n, co);
  for (const doc of spec.documents || []) await addDocument(page, key, doc);
  await shot(page, `${key}-2-customer.png`);
  await advance(page, key, 3);
  await page.waitForSelector("[data-fees-total]");

  // Step 3 · Billing: the fees table and the payment.
  const total = (await page.locator("[data-fees-total]").innerText()).trim();
  check(key, "Payments", `Fees total reads ${spec.expect.feesTotal}`, has(total, spec.expect.feesTotal), total);
  const billing = await page.locator("[data-move-in-billing]").innerText();
  check(key, "Payments", "no fee row is taxed at move-in (no Taxable column, no tax row)",
    !/taxable/i.test(billing) && !/\btax\b.*\$\d/i.test((await page.locator('[data-editable-table], [data-fees-table], table').filter({ hasText: "DEPOSIT" }).first().innerText().catch(() => "")) || ""));
  for (const claim of spec.discounts || []) await claimDiscount(page, key, claim);
  if (spec.exemption) await exemption(page, key, spec.exemption); // M5
  const b = spec.billing;
  if (b.mode === "pay_now") {
    await page.getByRole("radio", { name: "Pay now" }).click();
    await page.selectOption("#move_in_payment_method", b.method);
    await page.fill("#move_in_payment_amount", b.amount);
    if (b.reference) await page.fill("#move_in_payment_reference", b.reference);
    if ((await page.locator("#move_in_payment_received").count()) > 0) {
      await page.fill("#move_in_payment_received", DATE_ISO).catch(() => page.fill("#move_in_payment_received", DATE));
    }
  } else {
    await page.getByRole("radio", { name: "Add to bill" }).click();
  }
  await page.waitForLoadState("networkidle");
  if (spec.expect.firstBillSentence) {
    const line = await page.locator("[data-move-in-billing]").innerText();
    check(key, "Payments", `step 3 says ${spec.expect.firstBillSentence} goes on the first bill`,
      new RegExp(`\\${spec.expect.firstBillSentence.replace(".", "\\.")}[^\\n]*first bill`, "i").test(line),
      (line.match(/[^\n]*first bill[^\n]*/i) || ["(no first-bill sentence)"])[0]);
  }
  await shot(page, `${key}-3-billing.png`);
  await advance(page, key, 4);
  await shot(page, `${key}-4-review.png`);
  if (spec.poNumber) { // M7 (lane MVI-E2E-3): Review reads what Complete will commit
    check(key, "Billing", `Review shows the PO ${spec.poNumber}`, has(await bodyText(page), spec.poNumber));
  }
  // Complete's own answer is kept so a warning's server DETAIL can be printed beside the screen's
  // words (lane MVI-E2E-3: M6's two visits came back `work_orders_not_raised` with no reason drawn).
  const completeAnswer = page.waitForResponse(
    (r) => r.request().method() === "POST" && /\/move-in$/.test(new URL(r.url()).pathname), { timeout: 45000 },
  ).then((r) => r.json()).catch(() => null);
  await page.getByRole("button", { name: /Complete move-in/ }).click();
  await page.waitForSelector('[data-screen="move-in-completed"]', { timeout: 45000 });
  const answered = await completeAnswer;
  for (const w of answered?.warnings || []) {
    if (w && typeof w === "object") console.log(`  NOTE  ${key} · Complete warned ${w.code}: ${String(w.detail || "").slice(0, 400)}`);
  }
  const done = await page.locator('[data-screen="move-in-completed"]').innerText();
  await shot(page, `${key}-5-completed.png`);
  const moveNo = (done.match(/MVI-\d{2}-\d{4,}/) || [])[0] || null;
  // No internal code reaches a clerk (B14 rule 32): a snake_case word on screen is a missing catalogue key.
  const codes = done.match(/\b[a-z]+(?:_[a-z]+){2,}\b/g) || [];
  check(key, "Accounts", "Move-in completed prints no raw server code", codes.length === 0, codes.join(", "));
  // The welcome message is queued at Complete (its rows are read back below), so the count is never 0.
  const queued = (done.match(/Messages\s*(\d+)\s*queued/) || [])[1];
  check(key, "Messages", "Move-in completed counts the queued welcome (not 0 queued)",
    queued !== undefined && Number(queued) > 0, `reads "${queued} queued"`);
  check(key, "Accounts", "Move-in completed names an MVI- number", moveNo !== null, moveNo || done.slice(0, 120));
  return { moveNo, completed: done };
}

// ── 3 · walk the eight modules' screens ────────────────────────────────────
async function visit(page, key, module, path, file, expectations) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  // A slow page is not a blank one (lane MVI-E2E-3: WO-0053 read before its h1 arrived, then
  // photographed drawn): wait for the heading, then read.
  await page.waitForSelector("h1", { timeout: 10000 }).catch(() => undefined);
  await page.waitForTimeout(800);
  const text = await bodyText(page);
  const blank = (await page.locator("h1").count()) === 0 || /application error|something went wrong/i.test(text);
  check(key, module, `${path} opens (h1 drawn, no error page)`, !blank);
  for (const [name, needle] of expectations) {
    check(key, module, name, has(text, needle), has(text, needle) ? "" : `"${needle}" not on ${path}`);
  }
  await shot(page, file);
  return text;
}

async function walk(page, key, facts, spec) {
  const f = facts;
  // Units — Occupied is DERIVED from the open account (never written) and the unit names it.
  await visit(page, key, "Units", `/premises/units/${f.unit_id}`, `${key}-w1-unit.png`, [
    ["the unit reads Occupied", "Occupied"],
    [`the unit names account ${f.account_no}`, f.account_no],
    // The account HOLDER, never its contact person — for a company they differ (lane MVI-E2E-2).
    [`the unit names the account holder (${f.account_no} · ${f.customer_name})`, `${f.account_no} · ${f.customer_name}`],
  ]);
  // Assets — each meter read at move-in, showing its opening read.
  for (const reading of f.opening_reads) {
    await visit(page, key, "Assets", `/assets/${reading.asset_id}`, `${key}-w2-asset-${reading.asset_no}.png`, [
      [`${reading.asset_no} is on account ${f.account_no}`, f.account_no],
      [`${reading.asset_no} reads Installed (derived, the move-in wrote no status)`, "Installed"],
      [`${reading.asset_no} names the account holder (${f.account_no} · ${f.customer_name})`,
        `${f.account_no} · ${f.customer_name}`],
    ]);
    await visit(page, key, "Assets", `/assets/${reading.asset_id}?tab=reads`,
      `${key}-w2-asset-${reading.asset_no}-reads.png`, [
        // The Reads tab prints the register bare (4300), the move record grouped (4,300): either is the read.
        [`${reading.asset_no}'s Reads tab shows the opening read ${reading.value_raw}`, reading.value_raw],
        [`${reading.asset_no}'s Reads tab shows it in ${reading.unit}`, reading.unit],
      ]);
  }
  // Accounts — the customer, the category, every service started.
  await visit(page, key, "Accounts", `/accounts/${f.account_id}`, `${key}-w3-account.png`, [
    [`the account shows ${f.customer_name}`, f.customer_name],
    [`the account shows ${f.account_type_name}`, f.account_type_name],
    ...f.services_display.map((s) => [`the account lists ${s}`, s]),
  ]);
  // The page's TITLE is the account holder: the name can also appear lower down (the
  // "All accounts for this customer" box), so the body alone cannot prove it (law 7).
  const accountTitle = (await page.locator("h1").first().innerText().catch(() => "")).trim();
  check(key, "Accounts", `the account's title is the account holder ${f.customer_name}`,
    has(accountTitle, f.customer_name), `title reads "${accountTitle}"`);
  // Payments — every payment the move-in took, on the account's Payments tab.
  await visit(page, key, "Payments", `/accounts/${f.account_id}?tab=payments`, `${key}-w4-payments.png`,
    f.payments.map((p) => [`payment ${p.payment_no} ($${p.amount_display}) is listed`, p.payment_no]));
  // Billing — the move's Billing tab: the fees the first bill carries.
  const billingTab = await visit(page, key, "Billing", `/moves/${f.move_no}?tab=billing`, `${key}-w5-billing.png`, [
    ...f.fee_codes.map((code) => [`the move's Billing tab lists ${code}`, code]),
    [`the fees total $${f.fees_total}`, f.fees_total],
    ...(f.confirmation
      ? [[`each payment is dated the day the clerk typed (${DATE})`,
        `${f.payment_method === "card" ? "Card" : "Check"} ${f.confirmation} · ${DATE}`]]
      : []),
  ]);
  if (f.paid_in_full) {
    check(key, "Payments", "a deposit paid in full reads as taken, nothing still to collect",
      !/Still to collect\s*\$[1-9]/i.test(billingTab), (billingTab.match(/Still to collect\s*\$[\d,.]+/i) || [""])[0]);
  }
  // Cycle/Route — the unit on its route's walk, and the cycle named on the account.
  if (f.route_id) {
    await visit(page, key, "Route", `/reads/routes/${f.route_id}`, `${key}-w6-route.png`, [
      [`route ${f.route_code} is the unit's (${f.route_name})`, f.route_name],
    ]);
  } else {
    check(key, "Route", "the unit is on a route", false, "no route membership read back");
  }
  // Work — each order raised by the move-in, with its template.
  for (const order of f.work_orders) {
    await visit(page, key, "Work", `/work/orders/${order.order_no}`, `${key}-w7-${order.order_no}.png`, [
      // The order page names the template's TYPE (the template "Opening read" is a "Re-read").
      [`${order.order_no} shows its template's type ${order.type}`, order.type],
      [`${order.order_no} names the account ${f.account_no}`, f.account_no],
      [`${order.order_no} names the meter ${order.asset_no}`, order.asset_no],
      [`${order.order_no} is on the technician's day (${order.day_display})`, order.day_display],
    ]);
  }
  // Messages — the move-in's own Messages tab.
  await visit(page, key, "Messages", `/moves/${f.move_no}?tab=messages`, `${key}-w8-messages.png`, [
    ["the move's Messages tab lists the welcome", "welcome"],
  ]);
  // The move-in record itself (Accounts > Move-ins).
  const record = await visit(page, key, "Accounts", `/moves/${f.move_no}`, `${key}-w9-move.png`, [
    [`the move-in record reads ${f.move_no}`, f.move_no],
    [`the move-in record names ${f.account_no}`, f.account_no],
  ]);
  if (spec?.leaveUnread?.length) {
    // A meter left unread (P24): the record waits on it — Scheduled / Waiting on a read (§6.1).
    check(key, "Assets", `the move-in record reads 'Waiting on a read' (${spec.leaveUnread.join(", ")} left unread)`,
      /Waiting on a read/i.test(record));
  } else {
  // Every meter was read at move-in, so the record waits on nothing.
  check(key, "Assets", "the move-in record no longer reads 'Waiting on a read' (every meter read)",
    !/Waiting on a read/i.test(record));
  }
  if (spec && spec.walkExtra) await spec.walkExtra(page, key, f);
}

// ── main ──────────────────────────────────────────────────────────────────
mkdirSync(OUT, { recursive: true });
const world = lastJson(py("cr171_e2e_matrix_world.py", ["world"]));
const TENANT = world.tenant;
const WORLD = world; // P4.26's requests (lane MVI-E2E-3)
const browser = await chromium.launch({ executablePath: CHROME });
let crashed = 0;
for (const key of WANT) {
  const spec = CASES[key];
  const seeded = world.cases[spec?.worldCase ?? key]; // P24/P25 copy M1/M2 (lane MVI-E2E-3)
  console.log(`\n── ${key} · ${spec?.title ?? seeded?.title ?? "?"}`);
  if (!spec || !seeded) {
    check(key, "Runner", "case is known to the runner and the world", false);
    continue;
  }
  if (spec.todo) {
    check(key, "Runner", `case driver written (${spec.todo})`, false, "R4 lanes: fill this case's input and expectations");
    continue;
  }
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const page = await signIn(context, spec.clerk === "owner" ? world.owner : world.clerk, world.password);
    if (spec.run) { // P4.26 (lane MVI-E2E-3): a request path, not one wizard submit
      await spec.run(page, key);
      await context.close();
      continue;
    }
    const { moveNo } = await submit(page, key, spec, seeded);
    if (!moveNo) throw new Error("no move number on Move-in completed");
    // 2 · the database, read back
    const back = lastJson(py("cr171_e2e_matrix_readback.py", ["--case", key, "--move", moveNo]));
    for (const row of back.checks) check(key, row.module, row.name, row.pass, row.pass ? "" : row.detail);
    // The first bill's lines as the preview priced them — the money figures a report quotes (lane MVI-E2E-3).
    for (const [kind, description, amount] of back.facts.first_bill?.lines || []) {
      console.log(`  NOTE  ${key} · first bill · ${kind} · ${description} · ${amount}`);
    }
    // 3 · the eight modules' screens
    await walk(page, key, back.facts, spec);
    if (spec.after) await spec.after(page, key, back.facts); // P24 cancel, P25 change date (lane MVI-E2E-3)
  } catch (error) {
    crashed += 1;
    check(key, "Runner", "the case ran to its end", false, String(error).split("\n")[0]);
    // Where it stopped, photographed (lane MVI-E2E-3) — a crash with no picture is a guess.
    const last = context.pages().at(-1);
    if (last) await last.screenshot({ path: join(OUT, `${key}-CRASHED.png`), fullPage: true }).catch(() => undefined);
    console.log(String(error.stack || error).split("\n").slice(0, 6).join("\n"));
  }
  await context.close();
}
await browser.close();
clearTimeout(KILL);

const fails = results.filter((r) => !r.pass);
console.log("\n── summary");
for (const key of WANT) {
  const mine = results.filter((r) => r.caseKey === key);
  console.log(`  ${key}: ${mine.filter((r) => r.pass).length} PASS · ${mine.filter((r) => !r.pass).length} FAIL`);
}
console.log(fails.length === 0 && crashed === 0 ? "ALL PASS" : `${fails.length} FAIL`);
process.exit(fails.length === 0 && crashed === 0 ? 0 : 1);
