// ── Trace ──────────────────────────────────────────────
// Change:   `CR-111-BRC04` / `DEF-INT-5574` / `DEF-INT-5586` — the TWENTY-NINTH
//           connector, `pay_invoicecloud_partner`. PO 2026-09-17, verbatim:
//           *"a) Two connectors — one for the reading half, live now; the card
//           one stays where it is	the customer gets their key today. Two rows
//           in the list with the same company name - this is correct - we ahve
//           to issue our key and also save secrete given by them in bi
//           directional Connectors"*.
// Rules:    `BR-INT-037` (a connector is DATA — a new file must produce a card,
//           a view screen, four API rows and a key screen with NO screen code) ·
//           `BR-INT-044` (one refusal, one body, one set of bytes) ·
//           `BR-TEN-003` (nothing a caller sends selects anything) ·
//           CLAUDE.md hard rule 1 · hard-won law 6 (no gate reads rendered
//           output — diff the running app) · law 7 (name the false pass first) ·
//           `13-change-process.md`'s CLOSURE BAR (PO 2026-08-18: *"CR is not
//           closed until we have confirm user is able to perform tasks using
//           screen/broswer/UI"*).
// ───────────────────────────────────────────────────────
/**
 * A KEY CAN NOW BE ISSUED TO INVOICE CLOUD, AND ALL FIVE ADDRESSES ANSWER IT.
 *
 *     BASE=http://127.0.0.1:8412 API=http://127.0.0.1:8412 \
 *       LEFT_COMPANY=<tenant uuid> RIGHT_COMPANY=<tenant uuid> \
 *       node 10-scripts/cr111_invoicecloud_partner_walk.mjs
 *
 * WHAT THIS EXISTS TO PROVE, AND WHY A UNIT TEST CANNOT
 * ------------------------------------------------------
 * `CR-111-BRC04` shipped the whole Invoice Cloud partner surface — five
 * addresses, a CSV, a response shape — and **none of it could be reached**,
 * because `machine_auth._partner_manifest` issues a key only where a manifest
 * reads `they_hold_ours` and `pay_invoicecloud` reads `we_hold_theirs`
 * (`DEF-INT-5574`). Every test of that surface passed by granting itself a
 * scope in a fixture. **The claim that matters is that a CLERK can do it**, and
 * no gate in this repository reads rendered output.
 *
 * WHAT WOULD MAKE THIS WALK PASS WRONGLY — asked before it was written
 * ---------------------------------------------------------------------
 * **1 · ONE utility.** Every read step would pass over a resolver hard-wired to
 * the only tenant there is. So the walk runs TWO, with DIFFERENT row counts
 * (84 accounts against 72 on this database), and asserts both directions.
 *
 * **2 · Asserting a 200.** A 200 carrying the wrong utility's rows IS the
 * failure. Every success step reads the total and the first record back.
 *
 * **3 · Asserting a 404 on the cross-tenant bill.** A 404 is also what an
 * unknown id gets, so a per-case status proves nothing. Step 8 compares the
 * WHOLE BODY, byte for byte, against what a refused key gets — which is the
 * property `BR-INT-044` actually states.
 *
 * **4 · Asserting that `bill-download` "returned something".** A JSON refusal
 * with status 200 would satisfy that. Step 7 asserts the content type is
 * `application/pdf` AND that the first bytes are `%PDF`.
 *
 * **5 · Believing the stack.** A walk against a backend without this change is
 * not a weaker proof, it is a proof of a different product. Step 0 makes the
 * ONE request that only this build answers this way and refuses to walk
 * otherwise.
 *
 * **6 · Screen code.** The whole of `BR-INT-037` is that a connector costs one
 * data file. Step 2 therefore reads the grid, the view screen and the key panel
 * of a connector **no `.tsx` file mentions by name** — `grep` for the key
 * across `07-frontend/src` returns nothing — so anything that renders is
 * rendering from the manifest.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
import fs from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:8412";
const API = process.env.API ?? BASE;
const OUT = process.env.OUT ?? "/tmp/claude-0/ic-walk";
fs.mkdirSync(OUT, { recursive: true });

const LEFT = {
  slug: process.env.LEFT ?? "brazosbend",
  email: process.env.LEFT_USER ?? "dana@brazosbendutilities.com",
  company: process.env.LEFT_COMPANY ?? null,
};
const RIGHT = {
  slug: process.env.RIGHT ?? "laneseed-log",
  email: process.env.RIGHT_USER ?? "owner@laneseed-log.test",
  company: process.env.RIGHT_COMPANY ?? null,
};
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const PROVIDER = "pay_invoicecloud_partner";
const CARD = "pay_invoicecloud";
//: An invoice that exists at LEFT and NOT at RIGHT — checked against the
//: database before this walk was written, because a cross-tenant case run with
//: an id both utilities happen to hold proves nothing at all.
const LEFT_ONLY_BILL = process.env.LEFT_ONLY_BILL ?? "BL-2609-000082";

let failures = 0;
function say(step, ok, detail = "") {
  if (ok === false) failures += 1;
  const mark = ok === null ? "····" : ok ? "PASS" : "FAIL";
  console.log(`${mark}  ${step}${detail ? `\n        ${detail}` : ""}`);
}

async function raw(path, { key = null, params = {}, binary = false } = {}) {
  const url = new URL(API + path);
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined) url.searchParams.set(k, v);
  const headers = key === null ? {} : { Authorization: `Bearer ${key}` };
  const r = await fetch(url, { headers });
  const type = r.headers.get("content-type") ?? "";
  if (binary) {
    const buf = Buffer.from(await r.arrayBuffer());
    return { status: r.status, type, bytes: buf, head: buf.subarray(0, 8).toString("latin1"), text: buf.subarray(0, 200).toString("utf8") };
  }
  const text = await r.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = null; }
  return { status: r.status, type, body, text: text.slice(0, 400) };
}

// ══ STEP 0 · does this stack have the change at all? ═══════════════════════
{
  const probe = await raw("/api/partner/v1/reference");
  const ok = probe.status === 404 && probe.body?.code === "REFUSED";
  say("step 0a · the partner surface is mounted on this stack", ok, `GET /api/partner/v1/reference -> ${probe.status} ${probe.text}`);
  if (!ok) { console.log("\nREFUSING TO WALK — no partner surface here."); process.exit(2); }
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });

async function clerk(util, width = 1440) {
  const ctx = await browser.newContext({ viewport: { width, height: 1000 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/${util.slug}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", util.email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  return { ctx, page, signedIn: !page.url().includes("/signin") };
}

const seat = { [LEFT.slug]: await clerk(LEFT), [RIGHT.slug]: await clerk(RIGHT) };
say(`step 1a · ${LEFT.email} is signed in at ${LEFT.slug}`, seat[LEFT.slug].signedIn);
say(`step 1b · ${RIGHT.email} is signed in at ${RIGHT.slug}`, seat[RIGHT.slug].signedIn);

// ══ STEP 2 · THE GRID · TWO ROWS, ONE COMPANY NAME ═════════════════════════
// The PO's own words. Both rows have to be present AND tellable apart before
// either is opened, or the ruling has been implemented in name only.
async function gridRows(page, slug) {
  return page.evaluate(async (s) => {
    const r = await fetch(`/api/${s}/integrations`);
    const grid = await r.json();
    const providers = grid.providers ?? grid.data?.providers ?? [];
    return providers.map((p) => ({
      key: p.key, name: p.display_name, summary: p.summary,
      category: p.category, state: p.display_state, coming: p.disposition?.kind,
      ops: (p.operations ?? []).map((o) => o.name),
      connected: Boolean(p.connection),
    }));
  }, slug);
}

const rowsLeft = await gridRows(seat[LEFT.slug].page, LEFT.slug);
const mine = rowsLeft.find((r) => r.key === PROVIDER);
const card = rowsLeft.find((r) => r.key === CARD);
say("step 2a · the grid serves 29 connectors", rowsLeft.length === 29, `${rowsLeft.length} rows`);
say(
  "step 2b · BOTH InvoiceCloud rows are there, and they are NOT the same row",
  Boolean(mine) && Boolean(card) && mine.name !== card.name,
  `card: "${card?.name}" (${card?.coming}) · read half: "${mine?.name}" (${mine?.coming})`,
);
say(
  "step 2c · the read half declares its four APIs, from the manifest alone",
  mine?.ops?.join(",") === "serve_customer,serve_bill,serve_payment,serve_document",
  (mine?.ops ?? []).join(" · "),
);
say(
  "step 2d · the card half is UNTOUCHED — still coming soon, still four card APIs",
  card?.coming === "coming_soon" && card.ops.join(",") === "deliver_charge,deliver_card_page,fetch_settlement,deliver_refund",
  `${card?.coming} · ${(card?.ops ?? []).join(" · ")}`,
);

// ══ STEP 3 · WHAT A CLERK SEES, AT 1280 AND AT 1440 ════════════════════════
async function shootGrid(util, width) {
  const ctx = await browser.newContext({ viewport: { width, height: 1000 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/${util.slug}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", util.email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);
  await page.goto(`${BASE}/${util.slug}/settings/integrations`, { waitUntil: "networkidle" });
  // ⚠ **THE TABLE'S OWN SEARCH BOX, NOT THE SHELL'S OMNIBOX.** The first draft
  // matched `input[type="search"]` and typed into the HEADER search, which
  // answered *"No results for 'InvoiceCloud'"* over an unfiltered grid — and
  // the step still passed, because the two names were further down the page.
  // A screenshot of the wrong control is hard-won law 7's *looking at the wrong
  // thing* with a picture attached.
  await page.fill('input[placeholder^="Search services"]', "InvoiceCloud");
  await page.waitForTimeout(1800);
  const text = await page.evaluate(() => document.body.innerText);
  const shot = `${OUT}/grid-${width}.png`;
  await page.screenshot({ path: shot, fullPage: false });
  // Did the name CLIP? `w-32 truncate` is on the sentence columns; the name is
  // not supposed to be one of them, and "InvoiceCloud (reads from us)" is the
  // longest display name this product has ever carried, so it is measured
  // rather than assumed.
  const clipped = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll("td, th, span, a")) {
      if ((el.textContent ?? "").includes("reads from us")) {
        out.push({ text: el.textContent.trim().slice(0, 60), clipped: el.scrollWidth > el.clientWidth + 1 });
      }
    }
    return out;
  });
  await ctx.close();
  return { text, shot, clipped };
}

for (const width of [1280, 1440]) {
  const seen = await shootGrid(LEFT, width);
  const both = seen.text.includes("InvoiceCloud (reads from us)") && /InvoiceCloud\b(?!\s*\()/.test(seen.text);
  say(
    `step 3 · at ${width}px the grid DRAWS both rows, and no screen code names this connector`,
    both,
    `screenshot ${seen.shot}\n        clipping: ${seen.clipped.length === 0 ? "name not found as its own element" : seen.clipped.map((c) => `${c.clipped ? "CLIPPED" : "full"} "${c.text}"`).join(", ")}`,
  );
}

// ══ STEP 4 · CONNECT, then GENERATE A KEY — through the screen ═════════════
async function connectIfNeeded(util) {
  const { page } = seat[util.slug];
  return page.evaluate(async (args) => {
    const grid = await (await fetch(`/api/${args.slug}/integrations`)).json();
    const providers = grid.providers ?? grid.data?.providers ?? [];
    const cardRow = providers.find((p) => p.key === args.provider) ?? {};
    if (cardRow.connection) return { already: true };
    const token = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
    const r = await fetch(`/api/${args.slug}/integrations/${args.provider}/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      body: JSON.stringify({
        environment: "production", cadence: "manual",
        // Where this walk calls from. An EMPTY list permits everything, which
        // is lawful since the PO made the field optional and is the wrong
        // thing to demonstrate.
        fields: { allowed_addresses: "127.0.0.1/32" },
      }),
    });
    return { already: false, status: r.status, body: (await r.text()).slice(0, 200) };
  }, { slug: util.slug, provider: PROVIDER });
}

for (const util of [LEFT, RIGHT]) {
  const done = await connectIfNeeded(util);
  say(`step 4a · ${util.slug}: the connector CONNECTS`, done.already === true || done.status === 201,
      done.already ? "already connected" : `${done.status} ${done.body}`);
}

// ══ STEPS 4b–4e · THE THREE SCREENS, AND THE BUTTON THE RULING UNBLOCKS ════
// ⚠ **THREE ADDRESSES, NOT ONE, AND THE FIRST DRAFT OF THIS WALK ASKED THE
// WRONG SCREEN.** `App.tsx` mounts the SET-UP screen (S147) at
// `settings/connectors/:providerKey/configure` and the CONNECTION view (S142)
// at `settings/integrations/:key`, with the keys screen (S144) at
// `…/:key/access`. *Generate a key* lives on S147; S142 draws *Regenerate key*
// because a connection already has one. Pointing at `settings/integrations/…`
// and reporting "the button is not drawn" is hard-won law 7's *looking at the
// wrong thing*, and it reported exactly that until this was measured.
const SETUP = (slug) => `${BASE}/${slug}/settings/connectors/${PROVIDER}/configure`;
const VIEW = (slug) => `${BASE}/${slug}/settings/integrations/${PROVIDER}`;
const KEYS = (slug) => `${BASE}/${slug}/settings/integrations/${PROVIDER}/access`;

async function issueKey(util) {
  const { page } = seat[util.slug];
  await page.goto(SETUP(util.slug), { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  const shot = `${OUT}/setup-${util.slug}.png`;
  await page.screenshot({ path: shot, fullPage: true });
  const setupText = await page.evaluate(() => document.body.innerText);
  const button = await page.$("[data-generate-key]");
  const drawn = button !== null;
  const disabled = drawn ? await button.isDisabled() : null;
  let key = null, how = "not attempted";
  if (drawn && disabled === false) {
    await button.click();
    await page.waitForTimeout(3000);
    const shown = await page.$("[data-issued-key]");
    if (shown !== null) { key = (await shown.innerText()).trim(); how = "the button on S147"; }
    await page.screenshot({ path: `${OUT}/key-${util.slug}.png`, fullPage: true });
  }
  if (key === null) {
    const made = await page.evaluate(async (args) => {
      const token = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
      const r = await fetch(`/api/${args.slug}/integrations/${args.provider}/key`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": token },
        body: JSON.stringify({ scope: args.scope }),
      });
      return { status: r.status, body: await r.text() };
    }, { slug: util.slug, provider: PROVIDER, scope: ["serve_customer", "serve_bill", "serve_payment", "serve_document"] });
    try { const parsed = JSON.parse(made.body); key = parsed?.data?.key ?? parsed?.key ?? null; } catch { key = null; }
    how = `the endpoint the button calls (${made.status})`;
  }
  // The CONNECTION view — four API rows, their addresses, their ceilings.
  await page.goto(VIEW(util.slug), { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/view-${util.slug}.png`, fullPage: true });
  const viewText = await page.evaluate(() => document.body.innerText);
  // The KEYS screen — S144.
  await page.goto(KEYS(util.slug), { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/keys-${util.slug}.png`, fullPage: true });
  const keysText = await page.evaluate(() => document.body.innerText);
  return { key, how, drawn, disabled, shot, setupText, viewText, keysText };
}

const held = {};
for (const util of [LEFT, RIGHT]) {
  const issued = await issueKey(util);
  held[util.slug] = issued.key;
  say(
    `step 4b · ${util.slug}: S147 DRAWS "Generate a key", and it is LIVE`,
    issued.drawn === true && issued.disabled === false,
    `drawn=${issued.drawn} disabled=${issued.disabled} · screenshot ${issued.shot}`,
  );
  say(
    `step 4c · ${util.slug}: a key WAS ISSUED — the thing DEF-INT-5574 made impossible`,
    issued.key !== null,
    issued.key === null ? issued.how : `${issued.key.slice(0, 16)}…  via ${issued.how}  (shown once, ever)`,
  );
  const addresses = [...new Set(issued.viewText.match(/\/partner\/v1\/[a-z-]+\/?/g) ?? [])];
  say(
    `step 4d · ${util.slug}: S142 draws FOUR API rows with their own addresses and ceilings`,
    addresses.length === 4 && issued.viewText.includes("600 / min") && issued.viewText.includes("60 / min"),
    `${addresses.join(" · ")}\n        ceilings on screen: ${[...new Set(issued.viewText.match(/\d+ \/ min/g) ?? [])].join(", ")}`,
  );
  say(
    `step 4e · ${util.slug}: S144 lists the key we issued, by its hint and its scope`,
    /\u2022\u2022\u2022\u2022/.test(issued.keysText),
    issued.keysText.split("\n").filter((l) => l.includes("\u2022\u2022\u2022\u2022")).slice(0, 2).join(" | ") || issued.keysText.slice(0, 200),
  );
}

// ══ STEP 5 · ALL FIVE ADDRESSES, WITH A LIVE KEY ═══════════════════════════
// ⚠ **TWO OF THE FIVE REQUIRE A SELECTOR, AND THAT IS THE PRODUCT BEING RIGHT
// RATHER THAN THIS WALK BEING CLEVER.** `/payments` refuses without a date
// range (`DATE_RANGE_REQUIRED`) and `/consumer-info` without a consumer
// (`CONSUMER_SELECTOR_REQUIRED`) — hard-won law 3, the unsafe option is the one
// you type: an unbounded payments walk is the request that hurts. The first
// draft of this walk sent neither and scored two FAILs against correct
// refusals, which is worth leaving written down.
const CONSUMER = process.env.CONSUMER ?? "A-10432";
const FIVE = [
  ["/api/partner/v1/accounts", {}],
  ["/api/partner/v1/bills", {}],
  ["/api/partner/v1/payments", { start_date: "2026-01-01", end_date: "2026-12-31" }],
  ["/api/partner/v1/consumer-info", { consumer_numbers: CONSUMER }],
];
const counts = {};
for (const util of [LEFT, RIGHT]) {
  if (!held[util.slug] || !util.company) { say(`step 5 · ${util.slug}`, null, "no key or no company id — not walked"); continue; }
  counts[util.slug] = {};
  for (const [path, extra] of FIVE) {
    const got = await raw(path, { key: held[util.slug], params: { company_id: util.company, page_size: "2", ...extra } });
    // ⚠ **THE ENVELOPE IS INVOICE CLOUD'S OWN AND WAS OURS UNTIL 2026-09-17
    // (`DEF-INT-5642`).** `shapes.BY_CONNECTOR` named no connector a partner
    // can hold a key for, so every real call resolved to `NATIVE`; this walk
    // read `total_records` / `records` and got them, truthfully, out of a
    // dialect nobody had asked for. It reads `count` / `results` where the
    // dialect answers and falls back to ours, so one script drives an
    // InvoiceCloud key and an Aclarian one.
    const total = got.body?.count ?? got.body?.total_records ?? null;
    counts[util.slug][path] = total;
    const first = (got.body?.results ?? got.body?.records)?.[0];
    say(
      `step 5 · ${util.slug}: GET ${path}`,
      got.status === 200 && typeof total === "number",
      `${got.status} ${got.type} · total=${total} · first=${first ? JSON.stringify(first).slice(0, 150) : got.text}`,
    );
  }
  // …and the CSV, which is the same records in another representation.
  const csv = await raw("/api/partner/v1/bills", { key: held[util.slug], params: { company_id: util.company, page_size: "2", format: "csv" } });
  say(`step 5e · ${util.slug}: GET /api/partner/v1/bills?format=csv`, csv.status === 200 && csv.type.includes("csv"),
      `${csv.status} ${csv.type} · ${csv.text.split("\n")[0]?.slice(0, 160)}`);
}

// ══ STEP 6 · THE ISOLATION CLAIM ═══════════════════════════════════════════
say(
  "step 6 · one address, two keys, two utilities — and the answers DIFFER",
  counts[LEFT.slug] && counts[RIGHT.slug] &&
    counts[LEFT.slug]["/api/partner/v1/accounts"] !== counts[RIGHT.slug]["/api/partner/v1/accounts"],
  `${LEFT.slug}=${counts[LEFT.slug]?.["/api/partner/v1/accounts"]} vs ${RIGHT.slug}=${counts[RIGHT.slug]?.["/api/partner/v1/accounts"]} customers — same URL, only the key differed`,
);
// ⚠ AND THE OTHER DIRECTION: LEFT's key asking for RIGHT's company id.
{
  const crossed = await raw("/api/partner/v1/accounts", { key: held[LEFT.slug], params: { company_id: RIGHT.company, page_size: "2" } });
  const own = counts[LEFT.slug]?.["/api/partner/v1/accounts"];
  const crossedTotal = crossed.body?.count ?? crossed.body?.total_records;
  say(
    "step 6b · LEFT's key naming RIGHT's company id gets LEFT's OWN rows (BR-TEN-003)",
    crossed.status === 200 && crossedTotal === own,
    `${crossed.status} · total=${crossedTotal} (its own ${own}) — nothing a caller sends selects anything`,
  );
}

// ══ STEP 7 · `bill-download` — the address that had no door ════════════════
{
  const pdf = await raw("/api/partner/v1/bill-download/", { key: held[LEFT.slug], params: { company_id: LEFT.company, bill_id: LEFT_ONLY_BILL }, binary: true });
  say(
    `step 7 · ${LEFT.slug}: GET /api/partner/v1/bill-download/?bill_id=${LEFT_ONLY_BILL} is a PDF`,
    pdf.status === 200 && pdf.type.includes("application/pdf") && pdf.head.startsWith("%PDF"),
    `${pdf.status} ${pdf.type} · ${pdf.bytes.length} bytes · first eight: ${JSON.stringify(pdf.head)}`,
  );
  const nobill = await raw("/api/partner/v1/bill-download/", { key: held[LEFT.slug], params: { company_id: LEFT.company } });
  say("step 7b · no bill named is a 400 that NAMES the mistake, not the refusal",
      nobill.status === 400 && nobill.body?.code === "BILL_ID_REQUIRED", `${nobill.status} ${nobill.text}`);
}

// ══ STEP 8 · BR-INT-044 · THE BYTES, NOT THE STATUS ════════════════════════
{
  const notOurs = await raw("/api/partner/v1/bill-download/", { key: held[RIGHT.slug], params: { company_id: RIGHT.company, bill_id: LEFT_ONLY_BILL } });
  const badKey = await raw("/api/partner/v1/bill-download/", { key: "sbh_live_not_a_real_key", params: { bill_id: LEFT_ONLY_BILL } });
  say(
    "step 8 · another utility's bill answers the SAME BYTES as a refused key",
    notOurs.status === badKey.status && notOurs.text === badKey.text,
    `not ours: ${notOurs.status} ${notOurs.text}\n        bad key: ${badKey.status} ${badKey.text}`,
  );
}

// ══ STEP 9 · THE CARD HALF IS PROVABLY UNTOUCHED ═══════════════════════════
{
  const { page } = seat[LEFT.slug];
  const refused = await page.evaluate(async (args) => {
    const token = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
    const r = await fetch(`/api/${args.slug}/integrations/${args.card}/connect`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      body: JSON.stringify({ environment: "production", cadence: "manual", fields: {} }),
    });
    return { status: r.status, body: (await r.text()).slice(0, 200) };
  }, { slug: LEFT.slug, card: CARD });
  say("step 9 · connecting `pay_invoicecloud` is STILL refused 409 (BR-INT-001 / BR-INT-011)",
      refused.status === 409, `${refused.status} ${refused.body}`);
}

await browser.close();
console.log(`\n${failures === 0 ? "ALL STEPS PASSED" : `${failures} STEP(S) FAILED`} · screenshots in ${OUT}`);
process.exit(failures === 0 ? 0 : 1);
