// ── Trace ──────────────────────────────────────────────
// Change:  CR-087 lane C — the discount wizard's two dropdowns (C1), the
//          wizard's step 4 dates (C3), the discount detail's three tabs and its
//          take-up counts (C2), and the uniform action row on the discount and
//          rate-schedule detail screens (E1).
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do web
//          walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output) · hard-won law 2's
//          mirror (a live screen behind a dead control) · PRB-14 (a client that
//          cannot express a state is not a server that refuses it).
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH ONE IS HERE RATHER THAN IN A UNIT TEST.
//
//   1 · Step 1's Type control and step 3's Enrolment control, read as REAL
//       <select> elements with their real option lists. A unit test asserts a
//       string is in the markup; only the browser can say the control is a
//       dropdown a person can open and that it holds exactly three options.
//   2 · **The impossible pair, POSTED PAST THE FORM.** The whole point of C1 is
//       that the screen can no longer express it — so the screen cannot test
//       the server. This posts `automatic` + `proof_required` straight at
//       `POST /discounts` from the signed-in browser session and reads the 422
//       and the field names back. That is PRB-14's own done-when and no
//       front-end test can make the claim.
//   3 · Step 4's two date fields, read as `type="date"` — a picker, not a text
//       box a clerk has to guess the format for.
//   4 · The discount detail's tab strip, its four KPI tiles with their
//       captions, and the three headed blocks of the merged Overview.
//   5 · The action row on BOTH detail screens, reading the `disabled`
//       ATTRIBUTE and never the word — the shared Button's utility string
//       carries `disabled:opacity-45`, so a text search for "disabled" passes
//       on an ENABLED button.
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8502";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr087c";
mkdirSync(OUT, { recursive: true });

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
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const say = (...parts) => console.log(...parts);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const options = (sel) =>
  page.$$eval(`${sel} option`, (os) => os.map((o) => `${o.value} :: ${o.textContent.trim()}`));

// ══ 1 · the wizard, step 1 — Type is a DROPDOWN ═══════════════════════════
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#discount-type", { timeout: 30000 });
say("\n── STEP 1 · TYPE");
say("   tag:", await page.$eval("#discount-type", (el) => el.tagName));
for (const o of await options("#discount-type")) say("   option:", o);
// ⚠ ASSERTED AS AN ABSENCE TOO. A dropdown ADDED beside the five radio cards
// would leave the old control on screen and pass every positive check above.
say("   radios named discount-type still on screen:",
  await page.$$eval('input[name="discount-type"]', (n) => n.length));

// ══ 2 · step 3 — Enrolment is ONE dropdown of three ═══════════════════════
await page.fill("#discount-code", "WALKTHRU");
await page.fill("#discount-name", "Walkthrough discount");
const next = async () => {
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(400);
};
await next();                                    // → step 2 Value
await page.fill("#discount-value", "10").catch(() => {});
await next();                                    // → step 3 Eligibility
await page.waitForSelector("#discount-enrolment", { timeout: 20000 });
say("\n── STEP 3 · ENROLMENT");
say("   tag:", await page.$eval("#discount-enrolment", (el) => el.tagName));
for (const o of await options("#discount-enrolment")) say("   option:", o);
say("   separate 'proof is required' tick-box on screen:",
  await page.$$eval("#discount-proof-required", (n) => n.length));
say("   proof-kind tick-boxes visible under Apply-and-approve:",
  await page.$$eval('[id^="discount-proof-"]', (n) => n.length));
// Pick the third option and watch the proof list appear.
await page.selectOption("#discount-enrolment", "apply_and_approve_with_proof");
await page.waitForTimeout(300);
say("   …after choosing WITH PROOF:",
  await page.$$eval('[id^="discount-proof-"]', (n) => n.length), "proof controls");
await page.screenshot({ path: `${OUT}/step3-enrolment.png` });

// ══ 3 · step 4 — the dates are PICKERS ════════════════════════════════════
await page.check("#discount-proof-government_id").catch(() => {});
await next();                                    // → step 4 Effective
await page.waitForSelector("#discount-effective-from", { timeout: 20000 });
say("\n── STEP 4 · DATES AND BUDGET");
for (const id of ["discount-effective-from", "discount-effective-to"]) {
  say(`   #${id} type=`, await page.$eval(`#${id}`, (el) => el.getAttribute("type")));
}
const notes = await page.$$eval("[data-note]", (ns) => ns.map((n) => n.textContent.trim()));
const conflict = notes.find((n) => n.includes("$500"));
say("   second-approval note:", JSON.stringify(conflict));
say("   …sentences:", conflict ? conflict.split(/(?<=\.)\s+/).filter(Boolean).length : "(absent)");
await page.screenshot({ path: `${OUT}/step4-dates.png` });

// ══ 4 · THE IMPOSSIBLE PAIR, POSTED PAST THE FORM ════════════════════════
say("\n── PRB-14 · the pair the form can no longer express, posted anyway");
const refusal = await page.evaluate(async () => {
  const res = await fetch(`/api/${window.location.pathname.split("/")[1]}/discounts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      code: "WALKPAIR",
      name: "Impossible pair",
      discount_type: "percentage",
      value: "10",
      applies_to: "whole_bill",
      enrolment_mode: "automatic",
      proof_required: true,
      accepted_proof_kinds: ["government_id"],
    }),
  });
  return { status: res.status, body: await res.json().catch(() => null) };
});
say("   status:", refusal.status);
say("   fields named:", JSON.stringify((refusal.body?.field_errors ?? []).map((e) => e.field)));
say("   message_key:", JSON.stringify((refusal.body?.field_errors ?? []).map((e) => e.message_key)));

// ══ 5 · the discount DETAIL — three tabs, four tiles, three blocks ════════
const list = await page.evaluate(async () => {
  const res = await fetch(`/api/${window.location.pathname.split("/")[1]}/discounts?limit=5`, { credentials: "include" });
  return res.json();
});
const first = (list.results ?? list.items ?? list)[0];
say("\n── DISCOUNT DETAIL ·", first.code);
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${first.id}`, { waitUntil: "networkidle" });
await page.waitForSelector(".kpi", { timeout: 30000 });
say("   TABS:", JSON.stringify(await page.$$eval("[role='tab'], .page-header-tabs button",
  (bs) => bs.map((b) => b.textContent.trim()))));
say("   TILES:", JSON.stringify(await page.$$eval(".kpi",
  (ks) => ks.map((k) => k.textContent.trim().replace(/\s+/g, " ")))));
say("   OVERVIEW BLOCK HEADINGS:", JSON.stringify(await page.$$eval("[data-kicker]",
  (ks) => ks.map((k) => k.textContent.trim()))));
const actions = async () =>
  page.$$eval(".page-header button", (bs) =>
    bs.filter((b) => !b.getAttribute("role"))
      .map((b) => `${b.textContent.trim()}${b.hasAttribute("disabled") ? " [DISABLED]" : ""}` +
        `${b.getAttribute("data-variant") ? " <" + b.getAttribute("data-variant") + ">" : ""}`));
say("   ACTION ROW:", JSON.stringify(await actions()));
say("   HELD REASON:", JSON.stringify(await page.$$eval(".page-header button[title]",
  (bs) => [...new Set(bs.map((b) => b.getAttribute("title")))])));
await page.screenshot({ path: `${OUT}/discount-detail.png`, fullPage: true });

// the Audit tab still draws the DATED banner over the version table
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${first.id}?tab=audit`,
  { waitUntil: "networkidle" });
await page.waitForTimeout(600);
say("   AUDIT TAB draws the dated banner:",
  (await page.$$("[data-dated-banner]")).length > 0);

// ══ 6 · the RATE SCHEDULE detail — same action row ════════════════════════
const rates = await page.evaluate(async () => {
  const res = await fetch(`/api/${window.location.pathname.split("/")[1]}/rate-schedules?limit=5`, { credentials: "include" });
  return res.json();
});
const rate = (rates.results ?? rates.items ?? rates)[0];
say("\n── RATE SCHEDULE DETAIL ·", rate.name ?? rate.code);
// ⚠ **THE ADDRESS IS `…/rates/{id}`, NOT `…/rate-schedules/{id}`** — and the
// first draft of this walk used the second, got a page reading *"This screen is
// not built yet"*, and reported an EMPTY action row as though the buttons were
// missing. That is CLAUDE.md law 7's *looking at the wrong thing*, caught here
// only because an empty list was suspicious enough to probe. So the walk now
// asserts it is on the real screen before reading anything off it.
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${rate.id}`, { waitUntil: "networkidle" });
await page.waitForSelector(".page-header", { timeout: 30000 });
await page.waitForTimeout(1200);
const rateTitle = (await page.$eval("h1", (h) => h.textContent.trim()));
say("   H1:", JSON.stringify(rateTitle));
if (/not built yet/i.test(rateTitle)) {
  throw new Error("this walk is on the wrong address — the schedule detail did not render");
}
say("   ACTION ROW:", JSON.stringify(await actions()));
await page.screenshot({ path: `${OUT}/rate-detail.png`, fullPage: true });

say("\nshots in", OUT);
await browser.close();
