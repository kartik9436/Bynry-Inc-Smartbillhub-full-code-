/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-110-BRC04 — S142 rebuilt to the PO's ruling of 2026-09-17: the
 *          header carries the connector's own facts, the ACTIONS move to the
 *          page head, a KPI line is added, and the Test column's sentence is
 *          said once.
 * Defects: DEF-INT-5579 (the actions in a page-bottom footer) · DEF-INT-5580
 *          (no regenerate control) · DEF-INT-5581 (the set-up form's Save is
 *          refused on the second visit) · DEF-INT-5582 (a retired manifest
 *          field freezes every later PATCH).
 * Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
 *          output) · law 7 (a check must tell pass from fail to a READER, and
 *          ask what would make it pass — or FAIL — wrongly) · B14 rule 2 (one
 *          page header, right-aligned actions) · rule 6 (the danger tier on
 *          the destructive COMMIT) · rule 33 (a fact ≤ 6 words) · rules 32/33
 *          (one sentence per section).
 * ───────────────────────────────────────────────────────
 *
 * RUN IT:
 *     (cd 07-frontend && ./node_modules/.bin/vite build)
 *     DIST=$PWD/07-frontend/dist BACKEND=http://127.0.0.1:<api> PORT=8712 \
 *       node <scratchpad>/walkserver.mjs
 *     node 10-scripts/cr110_s142_head_and_kpis_walkthrough.mjs
 *
 * ⚠ **CHECK THE SERVED BUNDLE IS YOURS.** The first run of a walkthrough on
 * this CR measured a SIBLING LANE'S app, because the port it assumed was free
 * was not. `curl -s <base>/ | grep -o 'assets/index-[^"]*\.js'` must name the
 * file your own build just wrote.
 *
 * ⚠ **TWO OF THESE CHECKS FAILED WRONGLY ON THE FIRST RUN, AND BOTH TAUGHT
 * SOMETHING (law 7's habit 2, read in the other direction).**
 *   * The *not set up* case was pointed at `pay_worldpay`, which declares
 *     `Disposition(kind="coming_soon")` — so *no actions* was the CORRECT
 *     answer and that fixture could never have shown the Connect arm. It is
 *     `erp_infor` now, which is live and unconnected.
 *   * The *Save is not refused* check read the whole BODY for the word
 *     "cannot", and the connector view it lands on says *Cannot be tested
 *     until first use.* — a false alarm over a save that had worked perfectly.
 *     It asks `[data-save-refusal]` now, which is the element that means it.
 */
import { createRequire } from "node:module";
const require = createRequire("file:///home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
const BASE = "http://127.0.0.1:8712", T = "brazosbend";
const OUT = "/tmp/claude-0/-home-user-SMARTBillHub/d8cc0edb-6533-58a7-9b8e-548fbd3d8b79/scratchpad/gj-shots";
require("node:fs").mkdirSync(OUT, { recursive: true });

const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1440, height: 1300 } });
const errs = [];
p.on("pageerror", (e) => errs.push(String(e).slice(0, 160)));
p.on("response", (r) => { if (r.status() >= 400 && r.url().includes("/api/")) errs.push(`${r.status()} ${r.url().split("/api/")[1]}`); });

await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
await p.fill("#signin-email", "dana@brazosbendutilities.com");
await p.fill("#signin-password", "S3cure!passw0rd");
await p.click('button[type="submit"]');
await p.waitForTimeout(2500);

let fails = 0;
const say = (l, ok, d = "") => { console.log(`${ok ? "  OK" : "  XX"} ${l}${d ? " — " + d : ""}`); if (!ok) fails++; };
const open = async (k) => {
  await p.goto(`${BASE}/${T}/settings/integrations/${k}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1400);
  const crashed = (await p.locator("body").innerText()).includes("Unexpected Application Error");
  say(`${k}: the screen RENDERS (no error boundary)`, !crashed);
  return !crashed;
};
const headActions = async () =>
  (await p.locator(".page-header-actions button, .page-header-actions a").allInnerTexts()).map((s) => s.trim()).filter(Boolean);

for (const [k, what, expected] of [
  ["erp_aclarian", "reads from us — we issue their key", ["Edit", "Keys", "Disconnect", "Regenerate key"]],
  ["email_smtp", "we dial it", ["Edit", "Disconnect", "Replace password"]],
  ["email_microsoft", "signs in with Microsoft", ["Edit", "Disconnect", "Re-authorise now"]],
  ["erp_infor", "not set up (and LIVE — pay_worldpay is coming_soon and could never show Connect)", ["Connect"]],
  ["sms_twilio", "coming soon", []],
]) {
  console.log(`\n== ${k} · ${what} ==`);
  if (!(await open(k))) continue;
  const acts = await headActions();
  say(`${k}: the action row is ${JSON.stringify(expected)}`, JSON.stringify(acts) === JSON.stringify(expected), JSON.stringify(acts));
  // Nothing is left at the bottom of the page.
  const foot = await p.locator("[data-connection-footer]").allInnerTexts();
  say(`${k}: the footer holds the note and no button`, foot.length === 0 || (foot[0].includes("Runs are kept") && (await p.locator("[data-connection-footer] button, [data-connection-footer] a").count()) === 0), foot[0]?.slice(0, 44) ?? "(absent)");
  // The head's own facts.
  const head = (await p.locator(".page-header-id").innerText()).replace(/\n+/g, " | ");
  say(`${k}: the head carries category · direction`, !/^Connector/.test(head), head.slice(0, 120));
  // The KPI line.
  const tiles = await p.locator(".kpi-grid .kpi").count();
  say(`${k}: four KPI tiles`, tiles === 4, `${tiles}`);
  const chip = await p.locator(".page-header").innerText();
  say(`${k}: the API-count chip has LEFT the identity line`, !/\d+\s+APIs?\b/.test(chip));
  await p.screenshot({ path: `${OUT}/after-1440-${k}.png`, fullPage: true });
  await p.setViewportSize({ width: 1280, height: 1300 });
  await p.waitForTimeout(500);
  const wrapped = await p.evaluate(() => {
    const row = document.querySelector(".page-header-actions");
    if (!row) return false;
    const kids = [...row.children];
    return kids.length > 1 && new Set(kids.map((k) => k.getBoundingClientRect().top)).size > 1;
  });
  say(`${k}: the action row does NOT wrap at 1280`, !wrapped);
  await p.screenshot({ path: `${OUT}/after-1280-${k}.png`, fullPage: true });
  await p.setViewportSize({ width: 1440, height: 1300 });
}

console.log("\n== THE RED *WHY* LINE — the one structurally at risk of never rendering ==");
for (const [k, sentence] of [
  ["meters_neptune360", "No connection to the meter cloud."],
  ["bank_lockbox_file", "No folder client is installed."],
]) {
  if (!(await open(k))) continue;
  const why = p.locator("[data-state-reason]");
  const n = await why.count();
  say(`${k}: the reason is ON THE SCREEN`, n === 1, n ? await why.innerText() : "(absent)");
  if (n === 1) {
    const colour = await why.evaluate((el) => getComputedStyle(el).color);
    say(`${k}: it is RED, read off the built stylesheet`, /rgb\(\s*(1[5-9]\d|2[0-5]\d)\s*,\s*\d{1,2}\s*,/.test(colour), colour);
    say(`${k}: it says the provider's own words`, (await why.innerText()).trim() === sentence);
    const strip = await p.locator(".kpi-grid").boundingBox();
    const box = await why.boundingBox();
    say(`${k}: it sits UNDER the KPI line`, strip !== null && box !== null && box.y > strip.y);
  }
  await p.screenshot({ path: `${OUT}/after-why-${k}.png`, fullPage: true });
}

console.log("\n== *Cannot be tested* is said ONCE ==");
await open("erp_aclarian");
{
  const cells = await p.locator("[data-test-action]").allInnerTexts();
  const notes = await p.locator("[data-test-note]").allInnerTexts();
  say("aclarian: no row repeats the sentence", cells.every((c) => !c.includes("Cannot be tested")), `${cells.length} cells`);
  say("aclarian: it is said once under the table", notes.length === 1 && notes[0].includes("Cannot be tested"), notes[0] ?? "(absent)");
}

console.log("\n== REGENERATE KEY — the primary, its RED confirm, and the key shown ONCE ==");
await open("erp_aclarian");
{
  const btn = p.locator("[data-regenerate-key]");
  say("the control exists and is the PRIMARY", (await btn.count()) === 1 && (await btn.getAttribute("data-variant")) === "primary", await btn.getAttribute("data-variant"));
  await btn.click();
  await p.waitForTimeout(600);
  const dialog = p.locator('[role="alertdialog"]');
  say("it opens a confirm, not a key", (await dialog.count()) === 1);
  const text = await dialog.innerText();
  say("the consequence is there", text.includes("Their next call is refused"), text.replace(/\n+/g, " | ").slice(0, 110));
  const confirm = dialog.locator('button[data-variant="danger"]');
  say("the CONFIRM carries the danger tier (B14 rule 6)", (await confirm.count()) === 1);
  await p.screenshot({ path: `${OUT}/after-regenerate-confirm.png`, fullPage: true });
  await confirm.click();
  await p.waitForTimeout(2500);
  const panel = p.locator("[data-issued-key-panel]");
  say("the new key is shown ONCE", (await panel.count()) === 1);
  const value = (await p.locator("[data-issued-key-value]").innerText()).trim();
  say("it is a whole key and not a hint", value.length > 20 && !value.includes("••••"), `${value.length} chars`);
  await p.screenshot({ path: `${OUT}/after-regenerate-key.png`, fullPage: true });
  // It must not come back on a reload — it is stored nowhere.
  await p.reload({ waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  say("and it is GONE after a reload (stored nowhere)", (await p.locator("[data-issued-key-panel]").count()) === 0);
  say("the KPI *Keys in use* still reads 1", (await p.locator("[data-kpi='keys']").innerText()).trim() === "1", await p.locator("[data-kpi='keys']").innerText());
}

console.log("\n== EDIT — the PO's blocker: change the allowed addresses and have it STICK ==");
{
  await open("erp_aclarian");
  await p.locator("[data-edit]").click();
  await p.waitForTimeout(1800);
  say("Edit lands on the set-up form, not *not built yet*", p.url().includes("/settings/connectors/erp_aclarian/configure") && !(await p.locator("body").innerText()).includes("not built yet"), p.url().split(T)[1]);
  const field = p.locator('[data-field="allowed_addresses"] input, [data-field="allowed_addresses"] textarea').first();
  say("the allowed-addresses field is OPTIONAL now (no red asterisk)", (await p.locator('[data-field="allowed_addresses"] .text-danger-700').count()) === 0);
  const help = p.locator("[data-allowlist-help]");
  say("and it says what a blank means", (await help.count()) === 1, (await help.count()) ? await help.innerText() : "(absent)");
  await p.screenshot({ path: `${OUT}/after-setup-form.png`, fullPage: true });
  await field.fill("203.0.113.0/24, 198.51.100.7");
  await p.locator("button", { hasText: /Save and test/ }).first().click();
  await p.waitForTimeout(2600);
  const strip = p.locator("[data-save-refusal]");
  const refusedText = (await strip.count()) ? await strip.innerText() : "";
  say("Save is NOT refused on an already-connected connector", (await strip.count()) === 0, refusedText || "(no refusal strip)");
  say("and it left the form for the connector view", !p.url().includes("/configure"), p.url().split(T)[1]);
  await p.goto(`${BASE}/${T}/settings/connectors/erp_aclarian/configure`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1800);
  const back = await p.locator('[data-field="allowed_addresses"] input, [data-field="allowed_addresses"] textarea').first().inputValue();
  say("and reopening the form shows what was saved", back.includes("203.0.113.0/24"), JSON.stringify(back));
  await p.screenshot({ path: `${OUT}/after-setup-saved.png`, fullPage: true });
}

console.log("\n== REGRESSION · the neighbours ==");
for (const [path, marker, name] of [
  ["/settings/integrations", "Custom SMTP", "the connector grid"],
  ["/settings/integrations/erp_aclarian/access", "Keys we issue", "S144 machine keys"],
  ["/settings/integrations/bank_lockbox_file/mappings", "", "S143 mappings"],
]) {
  await p.goto(`${BASE}/${T}${path}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1400);
  const body = await p.locator("body").innerText();
  say(name, !/went wrong|Something broke|not built yet|Unexpected Application Error/i.test(body) && (marker === "" || body.includes(marker)));
}

console.log("\nerrors:", errs.length ? [...new Set(errs)] : "none");
console.log(fails ? `\n${fails} CHECK(S) FAILED` : "\nall checks passed");
await b.close();
