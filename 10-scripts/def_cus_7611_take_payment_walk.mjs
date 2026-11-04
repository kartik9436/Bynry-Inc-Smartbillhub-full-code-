// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-7611 — step 6 took no payment at all; DEF-CUS-7681 — the
//          browser's manifest was four keys behind the server's.
// Rules:   BR-MET-1187 (the connection, the invoice and the payment in ONE
//          act) · BR-PAY-021 (no clearing date ⇒ `processing`: settles no bill,
//          posts no ledger pair) · CLAUDE.md hard-won law 6 (no gate in this
//          repo reads rendered output — you find this by looking) · law 7
//          habit 3 (a check's output must distinguish pass from fail TO A
//          READER, not merely to an exit code)
// Basis:   10-scripts/po_new_connect_clerk_walk.mjs — the clerk walk that
//          already knows this wizard's selectors and its two traps (a radio in
//          this kit is visually hidden, so `check()` can never reach it; the
//          services control is a chip multi-select). This is that walk with a
//          CHARGE and a CHEQUE added on step 6, and with the money FOLLOWED
//          past the press: the build's own Charges figures and the invoice's
//          settled amount, read from the API rather than from the screen.
//
// ⚠ **IT FOLLOWS THE MONEY RATHER THAN THE RECEIPT.** The first working
// version of the server change printed a receipt number and left the invoice
// `$0.00` settled, because the payment had no clearing date and was therefore
// `processing`. A walk that stopped at *"a receipt number appeared"* would
// have called that a pass. So the last thing this prints is what the BILL
// says, and it says PASS or FAIL in words.
//
// RUN:  BASE=http://127.0.0.1:8080 OUT=/tmp/nc-pay \
//         node 10-scripts/def_cus_7611_take_payment_walk.mjs
// ───────────────────────────────────────────────────────
const { mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/nc-pay";
const UNITS = Number(process.env.UNITS ?? 2);
const TAKE = process.env.TAKE ?? "100.00";
// ⚠ NEVER `playwright install` — the installed build may not match the repo's
// playwright version, so the binary is named.
const CHROME =
  process.env.E2E_CHROMIUM_EXECUTABLE ??
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });

const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);
const ADDRESS = `${STAMP.slice(8)} Cheque Counter Way`;
const TODAY = new Date().toISOString().slice(0, 10);
const say = (...a) => console.log(...a);
const refusals = [];
const findings = [];
const noise = [];
// ⚠ **THE BROWSER ECHOES EVERY 4xx TO THE CONSOLE TOO**, so a refusal this
// walk DELIBERATELY causes — opening a till that is already open — arrives
// twice: once as a response this file classifies as expected, and once as a
// bare *"Failed to load resource: the server responded with a status of 422"*
// that carries no body and cannot be classified on its own. Counting the
// echoes lets the second one be matched to the first WITHOUT blanket-muting
// 422s, which would hide a real one.
let expectedEchoes = 0;
let stepNo = 0;

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
// The container's own noise — a CSP meta warning and a cert warning on an
// outbound resource — is NOT the product refusing anything. Printed, counted
// separately, and kept out of the verdict.
const CONTAINER_NOISE = /frame-ancestors|ERR_CERT_AUTHORITY_INVALID/;
page.on("console", (m) => {
  if (m.type() !== "error") return;
  const text = m.text().slice(0, 140);
  if (CONTAINER_NOISE.test(text)) {
    noise.push(text);
    return;
  }
  if (/Failed to load resource: the server responded with a status of 4/.test(text) && expectedEchoes > 0) {
    expectedEchoes -= 1;
    noise.push(`${text}  (the console's echo of a refusal this walk caused on purpose)`);
    return;
  }
  refusals.push(`console: ${text}`);
});
// ⚠ **THE REFUSAL'S OWN WORDS, NOT THE STATUS CODE.** A walk that reports
// "422" tells the next reader nothing they can act on; the server names the
// rule it refused on and that is what belongs in the log (BR-SHL-020 r2, and
// law 7 habit 3 — a check's output must distinguish pass from fail TO A
// READER).
page.on("response", async (r) => {
  if (r.status() >= 400 && r.url().includes("/api/")) {
    let body = "";
    try {
      body = (await r.text()).slice(0, 400);
    } catch {
      body = "(body unreadable)";
    }
    // ⚠ **NOISE IS PRINTED AND NOT COUNTED.** `payments.counter.refused`
    // on a second run means the till is already open, which is the state this
    // walk wants, and two CSP/cert console lines come from the container
    // rather than from the product. Both are shown — a blind spot with no
    // number beside it is indistinguishable from an empty one — but neither
    // decides the verdict.
    const benign = body.includes("payments.counter.refused");
    const line = `HTTP ${r.status()} ${r.url().replace(BASE, "")} :: ${body}`;
    if (benign) {
      expectedEchoes += 1;
      say(`  (expected) ${line.slice(0, 120)}`);
    } else {
      refusals.push(line);
    }
  }
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL}`);

const api = (path) =>
  page.evaluate(async (p) => {
    const r = await fetch(p, { headers: { accept: "application/json" } });
    return { status: r.status, body: await r.text() };
  }, path);

async function shot(name) {
  stepNo += 1;
  await page.screenshot({
    path: `${OUT}/${String(stepNo).padStart(2, "0")}-${name}.png`,
    fullPage: true,
  });
}

/** A radio in this kit is visually hidden and zero-sized, so neither `check()`
 *  nor `scrollIntoViewIfNeeded()` can ever reach it. Dispatching the click on
 *  the input is the same event React binds to. */
async function pick(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) {
    refusals.push(`no control named ${name}=${value}`);
    return;
  }
  await el.evaluate((n) => n.click());
}

async function forward(label) {
  const buttons = await page.$$('[data-wizard="actions"] button');
  const last = buttons[buttons.length - 1];
  const text = (await last.innerText()).trim();
  if (await last.isDisabled()) {
    refusals.push(`${label}: cannot advance — "${text}" is disabled`);
    return text;
  }
  await last.click();
  await page.waitForTimeout(1600);
  return text;
}

// ══════════════════════════════════════════════════════════════════════════
// OPEN THE TILL FIRST — `BR-PAY-060`, and the walk found this by being run
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **A CHEQUE TAKEN AT THE COUNTER NEEDS AN OPEN TILL, AND THE COMMIT SAYS SO
// BY NAME.** The first run of this walk pressed Create with no counter open and
// the server refused with `payments.counter.till_required` carrying
// `step: "charges"` — *"Money that passes through your hands — cash, cheques
// and money orders — belongs to a till, so the drawer can be counted at the end
// of the shift"*. That is the rule working, not a defect, and it is why
// `commit_connection` asks `assert_till_open_for_tender` (`DEF-PAY-6226`'s
// lesson). **A walk that skipped this would prove the screen and never the
// money**, which is the whole point of this file.
const apiPost = (path, body) =>
  page.evaluate(
    async ([p, b]) => {
      const r = await fetch(p, {
        method: "POST",
        headers: { "content-type": "application/json", accept: "application/json" },
        body: JSON.stringify(b),
      });
      return { status: r.status, body: (await r.text()).slice(0, 300) };
    },
    [path, body],
  );

// ⚠ **ASK WHETHER A TILL IS ALREADY OPEN BEFORE OPENING ONE.** A second run
// on the same day is refused with `payments.counter.refused` — one person may
// have one till at a time (`BR-PAY-1160`) — and that refusal is echoed to the
// browser console as a bare *"status of 422"* with no body, BEFORE the response
// handler can classify it. Filtering the echo afterwards is a race; **not
// causing it is not a race.** `f.mine=1` is resolved server-side and an unknown
// `f.` name is refused by name, so this asks exactly the right question
// (`DEF-PAY-6235`).
const myTills = JSON.parse(
  (await api(`/api/${TENANT}/counters?f.mine=1&f.state=open&per=1`)).body ?? "{}",
);
const tillAlreadyOpen = (myTills.count ?? (myTills.data ?? myTills.rows ?? []).length ?? 0) > 0;
if (tillAlreadyOpen) say("  a till of mine is already open — nothing to do");

const centres = JSON.parse(
  (await api(`/api/${TENANT}/settings/reference-data/service-centres`)).body ?? "{}",
);
// ⚠ **`centres`, AND THE VALUE IS THE `slug`.** The first draft read
// `data ?? results ?? rows` and took an `id`, found nothing, and printed *"no
// service centre to open a till at"* over a tenant that has three — a check
// reporting zero over a scope it was looking at wrongly (law 7). The real
// screen is the authority: `StartCounterModal` says *"`service_centre_id` IS
// THE SERVER'S KEY AND THE VALUE IS A SLUG"*.
let centre = tillAlreadyOpen ? "already-open" : ((centres.centres ?? [])[0] ?? null);
// ⚠ **`seed_demo` SEEDS NO SERVICE CENTRE**, measured: `select count(*) from
// service_centres` is 0 on a freshly seeded tenant. The counter needs one, so
// the walk makes one rather than reporting a product gap that is really a
// fixture gap — which is the wrong conclusion the third run of this file drew
// out loud before anyone looked at the table.
if (centre === null && !tillAlreadyOpen) {
  const made = await apiPost(`/api/${TENANT}/settings/reference-data/service-centres`, {
    name: "Counter Walk Office",
    address: "1 Counter Walk Plaza, Austin, TX 78704",
    // ⚠ **THE CENTRE'S VOCABULARY IS NOT PAYMENTS' — IT SPELLS IT `cheque`.**
    // `published_content.CENTRE_PAYMENT_METHODS` is `cash · cheque · card ·
    // money_order` while `BR-PAY-026`'s tender code is `check`. Sending the
    // payments spelling here is refused by name (`centre.method_unknown`), as
    // the fourth run of this walk found. Two vocabularies for one word, one
    // table apart — noted here because the next reader will hit it too.
    payment_methods_accepted: ["cash", "cheque", "card"],
  });
  say(`  no centre seeded — created one: HTTP ${made.status}`);
  const again = JSON.parse(
    (await api(`/api/${TENANT}/settings/reference-data/service-centres`)).body ?? "{}",
  );
  centre = (again.centres ?? [])[0] ?? null;
}
if (tillAlreadyOpen) {
  // nothing to open
} else if (centre === null) {
  refusals.push("no service centre to open a till at — the cheque cannot be taken");
} else {
  const opened = await apiPost(`/api/${TENANT}/counters`, {
    service_centre_id: centre.slug,
    opening_float: "0.00",
    opened_at: new Date().toISOString(),
  });
  // ⚠ **ALREADY OPEN IS A PASS, AND IT DOES NOT ANSWER 409.** A second run
  // of this walk on the same day is refused with **422**
  // `payments.counter.refused` — *"you already have a counter open, and one
  // person may have only one at a time"* (`BR-PAY-1160`). That is the state
  // this step wants, so reading it as a failure made the walk print
  // **WALK: FAIL** over a run whose money footed perfectly — a verdict line
  // that cannot distinguish pass from fail is worse than none (law 7,
  // habit 3). The CODE is what is branched on, never the status and never
  // the English.
  const alreadyOpen =
    opened.status === 409 ||
    (opened.status === 422 && opened.body.includes("payments.counter.refused"));
  say(
    `  till at ${centre.name} (${centre.slug}): HTTP ${opened.status}` +
      (alreadyOpen ? " — already open, which is the state we want" : ""),
  );
  if (![200, 201].includes(opened.status) && !alreadyOpen) {
    refusals.push(`could not open a till: HTTP ${opened.status} ${opened.body}`);
  }
}

await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

// ── 1 · Owner & scope ────────────────────────────────────────────────────
await page.selectOption("#nc_owner_kind", "builder_developer").catch(() => {});
await page.fill("#nc_owner_name", "Cheque Counter Developments LLC");
await page.selectOption("#nc_owner_subcategory", "permanent").catch(() => {});
await page.fill("#nc_owner_email", "build@chequecounter.example").catch(() => {});
await page.fill("#nc_owner_phone", "512-555-0177").catch(() => {});
await pick("nc_party_kind", "company");
await page.waitForTimeout(400);
for (const s of ["#nc_tax_id", "#nc_owner_tax_id"]) {
  if (await page.$(s)) await page.fill(s, `TX-${STAMP.slice(8)}`).catch(() => {});
}
await page.fill("#nc_prefix", "Apt").catch(() => {});
await pick("nc_scope", "new_premise");
await pick("nc_mode", "our_crew");
await forward("step 1 · Owner & scope");

// ── 2 · Premise ──────────────────────────────────────────────────────────
await page.fill("#nc_address", ADDRESS).catch(() => {});
for (const [s, v] of [
  ["#nc_city", "Austin"],
  ["#nc_postal_code", "78704"],
  ["#nc_zip", "78704"],
  ["#nc_premises_name", "Cheque Counter Court"],
]) {
  if (await page.$(s)) await page.fill(s, v).catch(() => {});
}
if (await page.$("#nc_state")) await page.fill("#nc_state", "TX").catch(() => {});
const ptypes = await page
  .$$eval("#nc_premise_type option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
if (ptypes.length) await page.selectOption("#nc_premise_type", ptypes[0]);
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
const offered = await page
  .$$eval("#services_available-add option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
for (const code of offered.slice(0, 2)) {
  await page.selectOption("#services_available-add", code).catch(() => {});
  await page.waitForTimeout(250);
}
const plans = await page
  .$$eval("#nc_plan option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
if (plans.length === 0) refusals.push("step2: no plan offered — the commit will refuse later");
else await page.selectOption("#nc_plan", plans[0]);
await forward("step 2 · Premise");

// ── 3 · Units ────────────────────────────────────────────────────────────
await page.fill("#nc_from", "1").catch(() => {});
await page.fill("#nc_to", String(UNITS)).catch(() => {});
await page.waitForTimeout(600);
await forward("step 3 · Units");

// ── 4 · Map services · 5 · Work orders ───────────────────────────────────
await page.waitForTimeout(1200);
await forward("step 4 · Map services");
await page.waitForTimeout(800);
await forward("step 5 · Work orders");

// ══════════════════════════════════════════════════════════════════════════
// 6 · CHARGES — a charge, then a CHEQUE with a clearing date
// ══════════════════════════════════════════════════════════════════════════
await page.waitForTimeout(1200);

// A charge the catalogue can actually price. `TAP`, `IMPACT` and `DAMAGE` are
// live codes with NO amount and the step refuses them by name (DEF-MET-6110),
// so the walk takes the first option the picker offers and says which.
const codes = await page
  .$$eval("#nc_quote_charge_code option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
if (codes.length === 0) {
  refusals.push("step6: the charge picker offered nothing");
} else {
  await page.selectOption("#nc_quote_charge_code", codes[0]);
  say(`  charge code taken: ${codes[0]} (of ${codes.length} offered)`);
  const add = await page.$("[data-add-charge]");
  if (add === null) refusals.push("step6: no Add a charge button");
  else {
    await add.click();
    await page.waitForTimeout(1500);
  }
}
await page.fill("#nc_quote_due_days", "30").catch(() => {});
await page.fill("#nc_quote_posting_date", TODAY).catch(() => {});
await page.waitForTimeout(800);

// ── THE CONTROLS THIS WALK EXISTS FOR ───────────────────────────────────
const before = await page.evaluate(() => ({
  refusalGone: document.querySelector('[data-take-payment="not-built"]') === null,
  takePayment: document.querySelector("#nc_take_payment")?.value ?? null,
  amountDrawn: document.querySelector("#nc_payment_amount") !== null,
}));
say(`  the old refusal is gone: ${before.refusalGone}`);
say(`  Take payment defaults to: ${JSON.stringify(before.takePayment)}`);
say(`  nothing else drawn until it is Yes: ${!before.amountDrawn}`);
if (!before.refusalGone) refusals.push("step6: the 'No payment is taken here' strip is STILL there");
if (before.takePayment !== "none") refusals.push("step6: Take payment does not default to none");
if (before.amountDrawn) refusals.push("step6: the amount box is drawn before a payment is chosen");
await shot("step6-charges-no-payment");

await page.selectOption("#nc_take_payment", "deposit");
await page.waitForTimeout(1200);

const methods = await page
  .$$eval("#nc_payment_method option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
say(`  tender list SERVED by GET /payments: ${methods.length} — ${methods.join(", ")}`);
if (methods.length === 0) refusals.push("step6: the method picker offered nothing — is it served?");
// The drawing's *Cheque* is the CODE `check`. Taken by code, never by label.
const cheque = methods.includes("check") ? "check" : methods[0];
await page.selectOption("#nc_payment_method", cheque);
await page.fill("#nc_payment_reference", `CHQ ${STAMP.slice(8)}`);
await page.fill("#nc_payment_amount", TAKE);
await page.waitForTimeout(600);

// ⚠ **THE CLEARING DATE IS EMPTY BEFORE IT IS TYPED, AND THAT IS THE RULE.**
const clearedBefore = await page.$eval("#nc_payment_cleared_date", (n) => n.value).catch(() => null);
say(`  clearing date before typing: ${JSON.stringify(clearedBefore)}`);
if (clearedBefore !== "") refusals.push(`step6: the clearing date is PREFILLED (${clearedBefore})`);
await page.fill("#nc_payment_cleared_date", TODAY);
await page.waitForTimeout(800);
await shot("step6-charges-cheque-taken");

const summary = await page.evaluate(() => ({
  rows: Array.from(document.querySelectorAll("[data-payment-summary-row]")).map((n) =>
    n.innerText.replace(/\s+/g, " ").trim(),
  ),
  outstandingStated: document.querySelector("[data-outstanding-absent]")?.innerText?.trim() ?? null,
}));
say(`  payment summary on screen: ${JSON.stringify(summary.rows)}`);
say(`  Outstanding, stated rather than computed: ${JSON.stringify(summary.outstandingStated)}`);

await forward("step 6 · Charges");

// ── 7 · Communication · 8 · Review, then PRESS ──────────────────────────
await page.waitForTimeout(900);
await forward("step 7 · Communication");
await page.waitForTimeout(1200);
await shot("step8-review");
const pressed = await forward("step 8 · REVIEW → Create");
await page.waitForTimeout(7000);
await shot("step9-after-the-press");

// ⚠ **WHERE DID A REFUSAL LAND, AND WHAT DID IT SAY?** `DEF-MET-6110`'s ruling
// is that a rule refusal reaches the clerk ON THE STEP THEY CHOSE IT, and the
// server carries `step: "charges"` for exactly that. A walk that only reports
// "no connection row" cannot tell a refusal that worked from a screen that
// swallowed it.
const landed = await page.evaluate(() => ({
  url: location.pathname + location.search,
  strip: Array.from(document.querySelectorAll('[data-step-refusal],[data-refusal],[role="alert"]'))
    .map((n) => n.textContent.trim())
    .filter(Boolean)
    .slice(0, 3),
  amountStillThere: document.querySelector("#nc_payment_amount")?.value ?? null,
  clearedStillThere: document.querySelector("#nc_payment_cleared_date")?.value ?? null,
}));
say("\n══ WHERE A REFUSAL LANDED ══");
say(`  ${landed.url}`);
say(`  on screen: ${JSON.stringify(landed.strip)}`);
say(`  the clerk's typing survived: amount=${JSON.stringify(landed.amountStillThere)} cleared=${JSON.stringify(landed.clearedStillThere)}`);

// ══════════════════════════════════════════════════════════════════════════
// FOLLOW THE MONEY — the DATABASE, not the screen and not the receipt
// ══════════════════════════════════════════════════════════════════════════
say("\n══ WHAT REACHED THE DATABASE ══");
const list = JSON.parse((await api(`/api/${TENANT}/connections?per=5`)).body ?? "{}");
const made = (list.data ?? list.results ?? [])[0] ?? null;
if (made === null) {
  refusals.push("the press produced no connection row");
  say("  NOTHING — no connection row came back");
} else {
  say(`  connection ${made.connection_no ?? made.id}`);
  // ⚠ **THE BUILD RECORD, WHICH IS WHAT THE CHARGES TAB RENDERS.**
  // `connection_record._money` derives `taken` from
  // `seams.settled_against_bills` — what actually SETTLED the invoice — so a
  // payment left `processing` for want of a clearing date reads 0 here even
  // though a receipt number exists. That is the whole reason this walk does
  // not stop at the receipt.
  const record = JSON.parse(
    (await api(`/api/${TENANT}/connections/${made.id}/record`)).body ?? "{}",
  );
  const r = record.data ?? record;
  const money = r.money ?? r.charges ?? {};
  say("\n══ THE BUILD'S CHARGES TAB — Quoted · Taken · Outstanding ══");
  for (const k of ["invoice_no", "billed_to", "quoted", "taken", "outstanding"]) {
    if (money[k] !== undefined) say(`  ${k.padEnd(14)} ${JSON.stringify(money[k])}`);
  }
  const num = (pair) => {
    const raw = pair && typeof pair === "object" ? (pair.stored ?? pair.display) : pair;
    return raw === null || raw === undefined || raw === "" ? null : Number(String(raw).replace(/[^0-9.-]/g, ""));
  };
  const quoted = num(money.quoted);
  const taken = num(money.taken);
  const outstanding = num(money.outstanding);
  if (taken === null || taken === 0) {
    findings.push(
      `TAKEN reads ${JSON.stringify(money.taken)} after a ${TAKE} cheque — the money did not settle the bill`,
    );
  }
  if (quoted !== null && taken !== null && outstanding !== null) {
    const foots = Math.abs(quoted - taken - outstanding) < 0.005;
    say(`  ${quoted} quoted − ${taken} taken = ${outstanding} outstanding · foots: ${foots}`);
    if (!foots) findings.push("the three figures on the Charges tab do not foot");
  }

  // ⚠ **THE `taken` FIGURE ABOVE IS THE BILL'S OWN ANSWER, WHICH IS WHY THERE
  // IS NO SECOND PROBE HERE.** `connection_record._money` derives it from
  // `seams.settled_against_bills([quote_invoice_id])` — what actually SETTLED
  // this invoice — so `taken` reading `100.00` IS the statement *"the payment
  // met the bill"*. A receipt number over a `$0.00` invoice, which is the
  // failure this walk exists for, shows up here as `taken: 0` beside an
  // `outstanding` equal to `quoted`.
  //
  // ⚠ **AN EARLIER DRAFT ALSO ASKED `GET /bills` AND CRASHED THE WHOLE WALK ON
  // `Unexpected token '<'`** — that route does not exist, the SPA answered with
  // its own `index.html`, and `JSON.parse` threw AFTER every real finding had
  // been printed. A proof that dies on its last line reports nothing at all, so
  // the redundant probe is gone rather than wrapped.
  if (money.invoice_no) {
    say(`\n  the bill this settled: ${money.invoice_no}, billed to ${money.billed_to}`);
  } else {
    findings.push("no invoice number on the build — the charge was not raised");
  }
}

// ── SAY PASS OR FAIL IN WORDS (law 7 habit 3) ───────────────────────────
say(`\n══ REFUSALS THE CLERK SAW: ${refusals.length} ══`);
refusals.forEach((r) => say("  · " + r));
say(`\n══ CONTAINER NOISE, NOT THE PRODUCT: ${noise.length} ══`);
noise.forEach((r) => say("  · " + r));
say(`\n══ FINDINGS: ${findings.length} ══`);
findings.forEach((r) => say("  · " + r));
say(`\nbutton pressed: "${pressed}"`);
say(`screens: ${OUT}`);
say(refusals.length + findings.length === 0 ? "\nWALK: PASS" : "\nWALK: FAIL");
await browser.close();
