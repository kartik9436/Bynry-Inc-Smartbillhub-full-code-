// ── Trace ──────────────────────────────────────────────
// Story:   `CR-115-BRC05` — the two email connectors learn to send, and domain
//          verification. Screens: S8 Settings → Integrations (the connector
//          table) · S141 the Connect modal · S142 the connector view.
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — the
//          browser is the only evidence) · law 2 (built is not wired, and its
//          mirror: a live card over a broken door) · `CR-115-BRC05` §7.6
//          (**"Prove a save works in a BROWSER, not with a passing test"** —
//          `DEF-INT-5579`–`5582` are four defects that a green suite missed)
// ───────────────────────────────────────────────────────
/**
 * Walk the two email connectors the way a clerk does.
 *
 *     BASE=http://127.0.0.1:5200 node 10-scripts/cr115_email_connector_walkthrough.mjs
 *
 * ⚠ **WHY THIS WALK EXISTS AND A PASSING SUITE DOES NOT REPLACE IT.** Binding
 * an adapter makes a card LIVE. Forty-one backend cases prove the adapter is
 * right; not one of them proves a clerk can press the card, because no gate in
 * this repo reads rendered output. `DEF-INT-5579`–`5582` are four defects where
 * the SAVE PATH refused a field name it did not recognise, all four found in a
 * browser and none by a test.
 *
 * ⚠ **IT ASSERTS WHAT THE STACK SERVES BEFORE IT BELIEVES ANYTHING**, the
 * clause `con01_connector_table_walkthrough.mjs` paid for on 2026-09-16: a
 * front end started on a port another lane held never bound, the browser was
 * served by the OLDER stack, and its answers were reported as product faults.
 * The bundle hash and the connector count are printed first.
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY:**
 *  * **A card that reads *Connect* proves nothing if the button is greyed.**
 *    The row's action buttons are read with their disabled state and printed.
 *  * **A modal that opens proves nothing if Save is refused.** The walk fills
 *    the four real fields, presses Save, and then re-reads the API to see
 *    whether a connection row actually exists — the screen's own optimism is
 *    not the evidence.
 *  * **A `200` from the DNS route proves nothing if the records are empty.**
 *    The record list is printed with each row's `source`, so the DMARC line we
 *    compose is visibly distinguishable from the three only SendGrid can give.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:5200";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/cr115-walk";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
await fs.mkdir(OUT, { recursive: true });

const say = (...a) => console.log(...a);
let failures = 0;
const check = (ok, label, detail = "") => {
  say(`${ok ? "  PASS" : "  FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures += 1;
};

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => say(`  ⚠ PAGE ERROR: ${e.message}`));

// ── 0 · WHICH STACK IS THIS ───────────────────────────────────────────────
const html = await (await fetch(`${BASE}/${TENANT}/settings/integrations`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(html) ?? [])[1] ?? "UNKNOWN";
say(`STACK: ${BASE} · bundle ${bundle}`);

// ── 1 · SIGN IN AS A REAL USER ────────────────────────────────────────────
say("\nSTEP 1 · sign in as the utility's owner");
// ⚠ **RETRIED, FOR THE REASON THE TABLE LOAD BELOW IS.** This box runs many
// lanes at once; sign-in timed out twice against a stack that was serving the
// right bundle and answering `200`. A walk that reports *sign-in is broken*
// from one slow navigation is worse than no walk, so it tries three times and
// says how many it took.
let signedIn = false;
for (let attempt = 1; attempt <= 3 && !signedIn; attempt += 1) {
  try {
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#signin-email", { timeout: 20000 });
    await page.fill("#signin-email", "dana@brazosbendutilities.com");
    await page.fill("#signin-password", "S3cure!passw0rd");
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/dashboard/, { timeout: 30000 });
    signedIn = true;
    if (attempt > 1) say(`  (signed in on attempt ${attempt} — this box is busy)`);
  } catch {
    say(`  (sign-in did not complete within the deadline on attempt ${attempt} — retrying)`);
  }
}
check(signedIn, "signed in and landed on the dashboard", page.url());
if (!signedIn) { say("\nWALK ABANDONED: could not sign in."); await browser.close(); process.exit(1); }

const api = (path, init) =>
  page.evaluate(
    async ([p, i]) => {
      const r = await fetch(p, { credentials: "include", ...(i ?? {}) });
      let body = null;
      try { body = await r.json(); } catch { body = null; }
      return { status: r.status, body };
    },
    [path, init],
  );

const grid = await api(`/api/${TENANT}/integrations`);
say(`STACK: the API serves ${grid.body?.providers?.length ?? "?"} connectors`);

// ── 1b · WHAT STATE IS THIS TENANT IN, AND SAY IT OUT LOUD ────────────────
//
// ⚠ **A WALK THAT ONLY WORKS ONCE IS A WALK NOBODY RUNS TWICE**, and this one
// found that out the hard way: its first run connected SendGrid, and its second
// reported a FAILURE against a screen doing exactly what `CR-115-BRC05` R2's
// ratified matrix says. So the walk ADAPTS instead of assuming, and prints
// which door it took.
//
// ⚠ **AND `DELETE` IS NOT A RESET — THAT IS `US-INT-025` WORKING AS DESIGNED.**
// Disconnect destroys every credential version and KEEPS the connection row,
// set `off`, with its run history. So a disconnected connector is still a
// connected-shaped row, `Connect` stays greyed, and the way back in is `Edit`.
// Walking that discovered `DEF-INT-5658` — see step 2.
const state0 = ((grid.body?.providers ?? []).find((p) => p.key === "sendgrid") ?? {}).state;
say(`TENANT: sendgrid starts this walk in state "${state0 ?? "no card"}"`);

// ── 2 · THE TWO EMAIL CARDS ARE NO LONGER HELD ────────────────────────────
say("\nSTEP 2 · Settings → Integrations: are SendGrid and Postmark pressable?");
// ⚠ **RETRY THE LOAD, AND SAY SO — A TIMEOUT UNDER LOAD IS NOT A DEFECT.**
// This walk once reported the connector table as failing to render; it was
// forty other pytest processes on the box, and a probe run seconds later drew
// the table perfectly with no page error. A walk that files that as a product
// fault is worse than no walk (`con01`'s 2026-09-16 lesson, one cause along).
let drew = false;
for (let attempt = 1; attempt <= 3 && !drew; attempt += 1) {
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "domcontentloaded" });
  try {
    await page.waitForSelector("table tbody tr", { timeout: 25000 });
    drew = true;
  } catch {
    say(`  (the table did not draw within 25s on attempt ${attempt} — retrying)`);
  }
}
check(drew, "the connector table draws");
await page.screenshot({ path: `${OUT}/01-connector-table.png`, fullPage: true });

const rows = await page.evaluate(() => {
  const out = {};
  for (const tr of document.querySelectorAll("table tbody tr")) {
    const key = tr.querySelector("[data-provider]")?.getAttribute("data-provider");
    if (!key) continue;
    const cell = tr.querySelector("[data-row-actions]");
    out[key] = {
      name: (tr.querySelector("[data-connector-link]")?.textContent ?? "").trim(),
      state: (tr.querySelector('[data-cell="state"]')?.textContent ?? "").trim(),
      actions: [...(cell?.querySelectorAll("button, a") ?? [])].map((a) => ({
        label: (a.getAttribute("aria-label") ?? a.textContent ?? "").trim(),
        disabled: a.tagName === "BUTTON" ? a.disabled : false,
        title: a.getAttribute("title") ?? "",
      })),
    };
  }
  return out;
});

for (const key of ["sendgrid", "postmark"]) {
  const row = rows[key];
  if (!row) { check(false, `${key} has a row in the table`); continue; }
  const connect = row.actions.find((a) => /connect/i.test(a.label));
  say(`  ${key}: "${row.name}" · state "${row.state}" · actions ${JSON.stringify(row.actions)}`);
  check(!!connect, `${key} offers a Connect action`);
  // ⚠ **THE CARD IS NO LONGER HELD** is the thing this change is judged on, and
  // *held* is `Not built yet` — NOT *greyed*. A card greyed `Already connected`
  // is the opposite of held. So the check is on the REASON, not on the pixel.
  check(
    connect ? connect.title !== "Not built yet" : false,
    `${key} is no longer held as "Not built yet"`,
    connect?.title ?? "",
  );
  // ⚠ **`DEF-INT-5658`, FOUND BY THIS WALK AND FILED RATHER THAN FIXED** (the
  // connector table is `07-frontend`, another lane's). A connector a clerk has
  // DISCONNECTED reads `● Turned off` in the State column while its Connect
  // action is greyed `Already connected` — two statements about one row that
  // cannot both be true, on the one screen a clerk uses to get back in.
  if (/turned off/i.test(row.state) && /already connected/i.test(connect?.title ?? "")) {
    check(false, `DEF-INT-5658 · ${key} says "${row.state}" and "${connect.title}" at once`);
  }
}

// ── 3 · CONNECT SENDGRID, FOR REAL, THROUGH THE MODAL ─────────────────────
say("\nSTEP 3 · press Connect on SendGrid and save the four fields");
const before = await api(`/api/${TENANT}/integrations/sendgrid/sending-domain`);
say(`  before connecting, the DNS route answers ${before.status}: ${JSON.stringify(before.body)}`);

// ⚠ **TWO THINGS THE FIRST DRAFT OF THIS STEP GOT WRONG, BOTH LAW 7's
// *looking at the wrong thing*, and both found only by printing the DOM:**
//  1. `data-provider` sits on a SPAN INSIDE the row, not on the `<tr>`, so
//     `[data-provider="sendgrid"] [data-row-actions]` matches nothing at all —
//     against a table that renders perfectly.
//  2. **Connect is an `<a href=…/configure>`, not a button opening a modal.**
//     A walk written for a dialog waits thirty seconds and then reports a
//     product fault about a screen that works. The clerk's real path is a
//     PAGE, and that is what is walked.
// ⚠ **WHICHEVER DOOR THE CLERK ACTUALLY HAS.** On a day-one tenant that is
// `Connect`; on a tenant that has connected once it is `Edit`, because
// `US-INT-025`'s disconnect keeps the row. Both land on the same set-up page
// and both end at the same `Save and test`, so the walk takes the one that is
// enabled and PRINTS WHICH — a walk that silently took a different path than it
// claimed would be law 7's *looking at the wrong thing*.
const sendgridActions = rows.sendgrid?.actions ?? [];
const canConnect = !(sendgridActions.find((a) => /connect/i.test(a.label))?.disabled ?? true);
const door = canConnect ? "Connect" : "Edit";
say(`  the enabled door on this tenant is ${door}`);
await page
  .locator(`tr:has([data-provider="sendgrid"]) [data-row-actions] a[aria-label="${door}"]`)
  .click();
await page.waitForURL(/\/settings\/connectors\/sendgrid\//, { timeout: 20000 });
check(true, `${door} opens the connector set-up page`, page.url());
await page.waitForTimeout(2500);
await page.screenshot({ path: `${OUT}/02-configure-page.png`, fullPage: true });

const fieldNames = await page.evaluate(() =>
  [...document.querySelectorAll("input, select, textarea")].map((i) => ({
    name: i.getAttribute("name") ?? i.id,
    type: i.getAttribute("type"),
  })),
);
say(`  the set-up page asks for: ${JSON.stringify(fieldNames)}`);

const FIELDS = {
  base_url: "https://api.sendgrid.com",
  api_key: "SG.walkthrough-not-a-real-key",
  sending_domain: "brazosbendutilities.com",
  send_from: "billing@brazosbendutilities.com",
};
for (const [name, value] of Object.entries(FIELDS)) {
  const sel = `[name="${name}"], #${name}, #field-${name}`;
  if (await page.$(sel)) {
    await page.fill(sel, value);
    say(`  filled ${name}`);
  } else {
    say(`  ⚠ no box named ${name} on the page`);
  }
}
await page.screenshot({ path: `${OUT}/03-configure-filled.png`, fullPage: true });

// ⚠ THE SAVE BUTTON'S OWN WORDS, READ RATHER THAN ASSUMED.
const saveLabel = await page.evaluate(() =>
  [...document.querySelectorAll("button")]
    .map((b) => (b.textContent ?? "").trim())
    .filter((t) => /connect|save/i.test(t)),
);
say(`  buttons that look like Save: ${JSON.stringify(saveLabel)}`);
// ⚠ **THE BUTTON SAYS *Save and test*, NOT *Connect*.** Read, not assumed —
// and the word matters: pressing it stores the credential AND queues one real
// send, so this walk is also the first time anything in this product has tried
// to hand a message to SendGrid. It will fail to dial (the egress proxy refuses
// the vendor), and the interesting question is whether the CONNECTION is still
// written, which is what the API check below asks.
const save = page.locator('button:has-text("Save and test")').last();
await save.click();
await page.waitForTimeout(5000);
await page.screenshot({ path: `${OUT}/04-after-save.png`, fullPage: true });
say(`  after Save the browser is at ${page.url()}`);

// ⚠ THE SCREEN'S OWN OPTIMISM IS NOT THE EVIDENCE — ask the API.
const afterGrid = await api(`/api/${TENANT}/integrations`);
const card = (afterGrid.body?.providers ?? []).find((p) => p.key === "sendgrid");
say(`  the API now says sendgrid is: ${JSON.stringify(card)}`);
check(
  !!card && card.state !== "not_connected" && card.state !== "coming_soon",
  "the SAVE actually wrote a connection (CR-115 §7.6 — prove it in a browser)",
  card?.state ?? "no card",
);

// ── 4 · THE DNS RECORDS — THE LONG POLE ───────────────────────────────────
say("\nSTEP 4 · the sending-domain route a utility's IT team works from");
const dns = await api(`/api/${TENANT}/integrations/sendgrid/sending-domain`);
say(`  GET → ${dns.status}`);
say(`  ${JSON.stringify(dns.body, null, 1)}`);
check(dns.status === 200, "GET answers 200 on a freshly connected connector");
check(dns.body?.connected === true, "it says the connector is connected");
check(dns.body?.last_attempt === null, "a GET reports no press (it never dials)");
const records = dns.body?.records ?? [];
check(records.length >= 1, "it already carries at least one record before any check", `${records.length}`);
const ours = records.filter((r) => r.source === "ours");
check(ours.length === 1 && ours[0].purpose === "dmarc", "the one record we compose is the DMARC line, marked `ours`");
check(
  ours[0]?.host === `_dmarc.${FIELDS.sending_domain}`,
  "the DMARC host is the utility's own domain",
  ours[0]?.host ?? "",
);

const pressed = await api(`/api/${TENANT}/integrations/sendgrid/sending-domain`, { method: "POST" });
say(`\n  POST (Check now) → ${pressed.status}`);
say(`  ${JSON.stringify(pressed.body, null, 1)}`);
check(pressed.status === 200, "POST answers 200 even when SendGrid cannot be reached");
check(
  pressed.body?.last_attempt && pressed.body.last_attempt.ok === false,
  "the press is REPORTED as failed rather than looking identical to no change",
  JSON.stringify(pressed.body?.last_attempt),
);
check(
  (pressed.body?.records ?? []).length === records.length,
  "a refused check did NOT destroy the records we already hold",
);

// ── 5 · POSTMARK SAYS WHY IT CANNOT BE ASKED ──────────────────────────────
say("\nSTEP 5 · Postmark's sending domain — a stated absence, not an empty box");
const pm = await api(`/api/${TENANT}/integrations/postmark/sending-domain`);
say(`  GET → ${pm.status}: ${JSON.stringify(pm.body)}`);
check(pm.status === 200, "Postmark's route answers rather than erroring");
check(pm.body?.connected === false, "it says Postmark is not connected here");
check(typeof pm.body?.reason === "string", "and it says WHY in a word a panel can translate", pm.body?.reason ?? "");

// ── 6 · THE CONNECTOR VIEW SCREEN STILL OPENS ─────────────────────────────
say("\nSTEP 6 · the connector view screen for a now-live email connector");
await page.goto(`${BASE}/${TENANT}/settings/integrations/sendgrid`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await page.screenshot({ path: `${OUT}/05-connector-view.png`, fullPage: true });
const view = await page.evaluate(() => ({
  heading: (document.querySelector("h1, h2")?.textContent ?? "").trim(),
  body: (document.body.innerText ?? "").slice(0, 400),
}));
say(`  heading: ${JSON.stringify(view.heading)}`);
check(view.heading.length > 0, "the connector view renders a heading");
check(
  !/not built yet|coming soon/i.test(view.body),
  "the view no longer calls this connector unbuilt",
);

say(`\nSCREENSHOTS in ${OUT}`);
say(failures === 0 ? "\nWALK: every check passed" : `\nWALK: ${failures} check(s) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
