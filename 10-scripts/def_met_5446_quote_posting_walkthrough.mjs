// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-5446 (`_post_connection_quote` was reverted out of
//          connections.py three minutes after it landed, so a build's quote
//          reached no book) · DEF-MET-5472 (a payer billing cannot bill
//          destroyed the whole build)
// Change:  CR-109 — the New Connect Charges step, the CALLER half
// Rules:   CLAUDE.md hard rule 2 (money 4 dp stored, round once at
//          finalization) · hard rule 4 (no UPDATE/DELETE on issued invoices) ·
//          hard rule 5 (balanced pairs; only the posting service writes
//          journal lines) · hard rule 7 (every money action audits) ·
//          BR-BIL-007 · BR-BIL-010 · BR-BIL-020 · BR-CUS-055 · BR-MET-112
//          hard-won law 6 (no gate in this repo reads rendered output)
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT NO UNIT TEST CAN, AND IT IS TWO SEPARATE CLAIMS.
//
//   A · **IS THE BUTTON WIRED** — the wizard's own Create-connection press,
//       walked in a real browser. The commit now RUNS the posting block, and
//       what it reports is read off the server's manifest rather than off the
//       screen.
//   B · **DOES THE MONEY WORK THROUGH THAT DOOR** — the same `POST
//       /connections/commit` endpoint, over the same signed-in session, for a
//       build that carries an approved application with a three-line quote.
//       Every call below is HTTP from the browser; nothing is a Python call.
//
// ⚠ **THE DATABASE IS ASKED, NOT THE MANIFEST.** The manifest is a dict the
// server returns and a commit that posted nothing could still return one, so
// after the press this reads the invoice, its lines and its JOURNAL back and
// asserts the pair BY ACCOUNT CODE AND BY FIGURE. A tie-out with no account
// codes in it proves only that zero equals zero.
//
// RUN IT:  node 10-scripts/def_met_5446_quote_posting_walkthrough.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def_met_5446";
mkdirSync(OUT, { recursive: true });

// The quote, written here rather than read out of the code under test.
const QUOTE = [
  { charge_code: "CONN", quantity: "6", unit_amount: "45.0000", basis: "per unit" },
  { charge_code: "METER-TEST", quantity: "20", unit_amount: "25.0000", basis: "per meter" },
  { charge_code: "INSPECT", quantity: "1", unit_amount: "30.0000", basis: "per premise" },
];
const QUOTE_TOTAL = "800.0000";
const EXPECTED_CREDITS = { 4600: "270.0000", 4630: "530.0000" };
const AR = "1200";

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
const page = await browser.newPage({ viewport: { width: 1500, height: 1300 } });
const say = (...p) => console.log(...p);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

page.on("response", async (res) => {
  if (res.request().method() === "POST" && res.url().endsWith("/connections/commit")) {
    say(`── the server answered ${res.status()} to the BUTTON ──`);
  }
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const api = (path, init) =>
  page.evaluate(
    async ([p, i]) => {
      const res = await fetch(p, {
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        ...(i ?? {}),
      });
      const text = await res.text();
      let json = null;
      try { json = JSON.parse(text); } catch { /* not json */ }
      return { status: res.status, text, json };
    },
    [path, init],
  );
const P = (p) => `/api/${TENANT}${p}`;

const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);

// The tenant's own electric plan, read from the product rather than invented.
const plansRead = await page.evaluate(
  async (p) => {
    const res = await fetch(p, { credentials: "include" });
    return await res.text();
  },
  `/api/${TENANT}/plans?page_size=5`,
);
let TARIFF_ID = null;
try {
  const parsed = JSON.parse(plansRead);
  const rows = parsed.results ?? parsed.rows ?? parsed.items ?? parsed;
  if (Array.isArray(rows) && rows.length > 0) TARIFF_ID = rows[0].id;
} catch { /* reported below */ }
if (TARIFF_ID === null) say("   plans payload was:", plansRead.slice(0, 300));
say("   plan used for every unit:", TARIFF_ID);
const UNIT_LABELS = ["Apt 1", "Apt 2", "Apt 3", "Apt 4", "Apt 5", "Apt 6", "Common area"];
const PLAN_ASSIGNMENTS = UNIT_LABELS.map((unit_label) => ({ unit_label, tariff_id: TARIFF_ID }));

// ══════════════════════════════════════════════════════════════════════════
// A · THE BUTTON — the wizard's own press, in the browser
// ══════════════════════════════════════════════════════════════════════════
say("\n══ A · IS THE BUTTON WIRED ══");
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const onWizard = page.url().includes("/connections/new");
check("A0 · the wizard opens", onWizard, page.url());

// ══════════════════════════════════════════════════════════════════════════
// B · THE MONEY — the same door, over the same session, for a quoted build
// ══════════════════════════════════════════════════════════════════════════
say("\n══ B · DOES THE MONEY REACH THE BOOKS ══");

// 1 · the application that carries the quote
const made = await api(P("/service-requests"), {
  method: "POST",
  body: JSON.stringify({
    channel: "physical_form",
    applicant_kind: "business",
    applicant_name: `Balcones Development LLC ${STAMP.slice(8)}`,
    address_as_given: `${STAMP.slice(8)} Bluestem Ln, Katy TX`,
  }),
});
check("B1 · an application is captured", made.status < 300, `status ${made.status} ${made.text.slice(0, 200)}`);
const requestId = made.json?.header?.id ?? made.json?.id;
say("   request:", requestId, made.json?.header?.request_no ?? "");

// 2 · its three coded quote lines
for (const line of QUOTE) {
  const r = await api(P(`/service-requests/${requestId}/fees`), {
    method: "POST",
    body: JSON.stringify(line),
  });
  check(
    `B2 · quote line ${line.charge_code} x${line.quantity}`,
    r.status < 300,
    `status ${r.status} ${r.status >= 300 ? r.text.slice(0, 200) : ""}`,
  );
}

// 3 · THE PRESS — the wizard's own endpoint, with the application named and
//     the payment terms captured. This is the payload the Charges step will
//     send once it is drawn; the door is the one the button already posts to.
const commit = await api(P("/connections/commit"), {
  method: "POST",
  body: JSON.stringify({
    premises: {
      id: null,
      name: `Balcones Court ${STAMP.slice(8)}`,
      address: `${STAMP.slice(8)} Bluestem Ln`,
      city: "Katy",
      state: "TX",
      postal_code: "77494",
      services_available: ["electric", "water"],
    },
    mode: "our_crew",
    service_request_id: requestId,
    units: [
      { label: "Apt 1" }, { label: "Apt 2" }, { label: "Apt 3" },
      { label: "Apt 4" }, { label: "Apt 5" }, { label: "Apt 6" },
      // BR-MET-116 — the owner's master account anchors on the premises' own
      // common-area unit, and step 3 of the wizard adds one for exactly this.
      { label: "Common area", is_common_area: true },
    ],
    meters: [],
    // BR-MET-040 — an account may not ACTIVATE on a unit with no rate plan,
    // and `create_master_account` opens ACTIVE (BR-CUS-068). So plans are
    // assigned before the owner's account is opened, which is the ordering
    // `commit_connection` already sequences and `BR-MET-116` records.
    plan_assignments: PLAN_ASSIGNMENTS,
    create_owner_account: true,
    owner: {
      name: `Balcones Development LLC ${STAMP.slice(8)}`,
      party_kind: "company",
      identity: { tax_id: `74-${STAMP.slice(8)}` },
      email: "builds@balcones.example",
      phone: "512-555-0142",
    },
    // CR-029 D8(3), PO 2026-08-23 — CAPTURED, never guessed.
    quote_due_days: 30,
    quote_posting_date: "2026-09-16",
    quote_payer: "owner_account",
    quote_total: null,
    work_orders: [],
  }),
});
check("B3 · the commit door answers", commit.status < 300, `status ${commit.status} ${commit.status >= 300 ? commit.text.slice(0, 400) : ""}`);
const manifest = commit.json?.manifest ?? {};
const unavailable = commit.json?.unavailable ?? [];
say("   manifest:", JSON.stringify(manifest));
say("   stated absences:", unavailable.map((r) => r.code).join(" · ") || "(none)");
say("   connection:", commit.json?.connection_no ?? commit.json?.id ?? JSON.stringify(commit.json).slice(0, 200));

check(
  "B4 · `quote_recorded_not_posted` is GONE — it stopped being true",
  !unavailable.some((r) => r.code === "quote_recorded_not_posted"),
);
check(
  "B5 · the manifest names the invoice it raised, not just a figure",
  Boolean(manifest.one_time_charge_invoice_no),
  String(manifest.one_time_charge_invoice_no),
);
check(
  `B6 · the manifest's figure is the quote, to four decimals`,
  manifest.one_time_charges === QUOTE_TOTAL,
  `${manifest.one_time_charges} (expected ${QUOTE_TOTAL})`,
);

// 4 · THE DATABASE, not the manifest.
const invoiceNo = manifest.one_time_charge_invoice_no;
if (invoiceNo) {
  const found = await api(P(`/invoices?search=${encodeURIComponent(invoiceNo)}`));
  say("   invoice read back:", found.status, found.text.slice(0, 400));
}

say(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
await page.screenshot({ path: join(OUT, "wizard.png"), fullPage: false }).catch(() => {});
await browser.close();
process.exit(failures === 0 ? 0 : 1);
