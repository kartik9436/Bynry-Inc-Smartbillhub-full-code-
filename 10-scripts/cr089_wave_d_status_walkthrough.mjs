// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave D — D1 (`PUJ-21`) and D2 (`PUJ-48`): a property and a
//          unit can be taken out of service, and put back.
// Rules:   BR-MET-1164 (PO 2026-09-08 — *"if you ahve units - active, assets or
//          active accounts, you cannot shut down building pr premises"*) ·
//          PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output) · hard-won law 2's
//          mirror (a live screen behind a dead control).
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH ONE IS HERE RATHER THAN IN A UNIT TEST.
//
//   1 · The property page's header, read as REAL BUTTONS. A unit test asserts a
//       string is in the markup; only the browser can say the third button is
//       there beside Edit and Add unit and that a person can press it.
//   2 · The dialog over a building with LIVE UNITS: the counts as they render,
//       every one of them read as an `<a href>` a person can follow, the hold
//       sentence, and the commit button's `disabled` ATTRIBUTE — never the word
//       "disabled", because the shared Button's utility string carries
//       `disabled:opacity-45` and a text search for it passes on an ENABLED
//       button.
//   3 · **THE REFUSAL POSTED PAST THE SCREEN.** The dialog will not let the
//       press through, so the screen cannot test the server. This posts the
//       transition straight at `POST /premises/{id}/status` from the signed-in
//       session and reads the 409 and its sentence back.
//   4 · A REAL DEACTIVATION, END TO END: the units are taken out, the property
//       goes, the pill reads Inactive, and the button turns into the
//       reactivation — which is CR-089 §8's one thing the rollback must keep.
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8511";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089d";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
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

/** EVERY pill in the identity block, not the first one.
 *
 * ⚠ A UNIT PAGE DRAWS THE OCCUPANCY PILL BEFORE THE STATUS PILL, so a read of
 * the first match answered "Vacant" for a unit that had just been taken out of
 * service — a walkthrough looking at the wrong thing and reporting it as a
 * finding (hard-won law 7's fourth shape). */
const pills = (p) => p.$$eval("[data-status], .pill", (ns) => ns.map((n) => n.textContent.trim()));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

/** Find a property that HAS live units — the case the refusal is written for. */
const api = (path, init) =>
  page.evaluate(
    async ([p, i]) => {
      const res = await fetch(p, { credentials: "include", ...(i ?? {}) });
      return { status: res.status, body: await res.text() };
    },
    [path, init],
  );

// ⚠ TWO PROPERTIES, AND THE SECOND IS NOT A CONVENIENCE. The refusal can only
// be watched on a building that still has something live on it, and the
// deactivation can only be COMPLETED on one that does not — so a walk that
// used one property would prove half the task and stop. The second is chosen by
// asking the server which properties are free, never by assuming.
const list = JSON.parse((await api(`/api/${TENANT}/premises?per=200`)).body);
let target = null;
let clear = null;
for (const row of list.results ?? []) {
  if (target !== null && clear !== null) break;
  const detail = JSON.parse((await api(`/api/${TENANT}/premises/${row.id}`)).body);
  if (detail.status !== "active") continue;
  const view = JSON.parse((await api(`/api/${TENANT}/premises/${row.id}/status-change`)).body);
  const counts = Object.fromEntries(view.dependencies.map((d) => [d.kind, d.count]));
  if (target === null && counts.open_accounts > 0 && counts.active_units >= 2) {
    target = { ...detail, counts };
  }
  if (
    clear === null &&
    counts.open_accounts === 0 &&
    counts.unpaid_balances === 0 &&
    counts.attached_assets === 0 &&
    counts.active_units >= 1
  ) {
    clear = { ...detail, counts };
  }
}
if (target === null) throw new Error("no active property with live units AND an open account");
if (clear === null) throw new Error("no active property whose blockers are already clear");
say(`\nheld property:  ${target.premise_no} · ${target.address_line} · ${JSON.stringify(target.counts)}`);
say(`clear property: ${clear.premise_no} · ${clear.address_line} · ${JSON.stringify(clear.counts)}`);

// ══ 1 · THE HEADER HAS A THIRD BUTTON ═════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/premises/${target.id}`, { waitUntil: "networkidle" });
await page.waitForSelector("h1", { timeout: 30000 });
const headerButtons = await page.$$eval("button", (bs) =>
  bs.map((b) => b.textContent.trim()).filter(Boolean),
);
say("\n── 1 · PROPERTY HEADER");
say("   buttons:", JSON.stringify(headerButtons));
say("   pills:", JSON.stringify(await pills(page)));
await page.screenshot({ path: `${OUT}/1-property-header.png` });

// ══ 2 · THE DIALOG OVER A LIVE BUILDING ═══════════════════════════════════
await page.click('button:has-text("Change status")');
// ⚠ WAIT FOR THE ANSWER, NOT FOR THE FRAME. `[data-status-dialog]` is the modal
// body and renders at once with the loading skeleton over it; a read taken then
// sees no counts and no hold, and would report a dialog that draws neither.
await page.waitForSelector('[data-consequence="status-change"]', { timeout: 20000 });
say("\n── 2 · THE DIALOG, OVER A BUILDING WITH LIVE UNITS");
say("   title:", await page.$eval(".modal-title", (el) => el.textContent.trim()));
const counts = await page.$$eval("[data-dependency]", (rows) =>
  rows.map((row) => {
    const link = row.querySelector("a");
    return {
      kind: row.getAttribute("data-dependency"),
      text: row.textContent.trim(),
      href: link ? link.getAttribute("href") : null,
    };
  }),
);
for (const row of counts) say("   count:", row.kind, "→", JSON.stringify(row.text), "href:", row.href);
say("   hold:", JSON.stringify(await page.$$eval("[data-status-hold]", (n) => n.map((e) => e.textContent.trim()))));
say(
  "   consequence:",
  JSON.stringify(
    await page.$eval('[data-consequence="status-change"]', (el) => el.textContent.trim()),
  ),
);
const commit = await page.$('.modal-foot button[data-variant="danger"]');
say("   commit label:", (await commit.textContent()).trim());
// ⚠ THE ATTRIBUTE, NOT THE WORD.
say("   commit disabled ATTRIBUTE:", await commit.evaluate((el) => el.hasAttribute("disabled")));
say("   commit data-variant:", await commit.evaluate((el) => el.getAttribute("data-variant")));
await page.screenshot({ path: `${OUT}/2-dialog-held.png` });

// ══ 3 · THE REFUSAL, POSTED PAST THE SCREEN ═══════════════════════════════
say("\n── 3 · THE SERVER'S OWN REFUSAL (the screen will not let this through)");
const refused = await api(`/api/${TENANT}/premises/${target.id}/status`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ status: "inactive", effective_date: "2026-09-08", reason: "walkthrough" }),
});
say("   status:", refused.status);
say("   body:", refused.body.slice(0, 300));

// ══ 4 · A PROPERTY WHOSE BLOCKERS ARE CLEAR, TAKEN OUT FOR REAL ═══════════
say("\n── 4 · THE CLEAR PROPERTY: TAKING ITS UNIT OUT, THEN THE PROPERTY");
await page.goto(`${BASE}/${TENANT}/premises/units/${clear.unit_rows[0].id}`, {
  waitUntil: "networkidle",
});
await page.waitForSelector("h1", { timeout: 30000 });
await page.click('button:has-text("Change status")');
await page.waitForSelector('[data-consequence="status-change"]', { timeout: 20000 });
say("   unit dialog title:", await page.$eval(".modal-title", (el) => el.textContent.trim()));
say(
  "   unit counts:",
  JSON.stringify(
    await page.$$eval("[data-dependency]", (rows) =>
      rows.map((r) => `${r.getAttribute("data-dependency")}=${r.textContent.trim()}`),
    ),
  ),
);
await page.fill("#status-effective-date", "2026-09-08");
await page.fill("#status-reason", "Walkthrough — flat knocked through");
await page.click('.modal-foot button[data-variant="danger"]');
await page.waitForTimeout(1500);
await page.reload({ waitUntil: "networkidle" });
say("   unit pills after:", JSON.stringify(await pills(page)));

await page.goto(`${BASE}/${TENANT}/premises/${clear.id}`, { waitUntil: "networkidle" });
await page.waitForSelector("h1", { timeout: 30000 });
await page.click('button:has-text("Change status")');
await page.waitForSelector('[data-consequence="status-change"]', { timeout: 20000 });
const nowHeld = await page.$$eval("[data-status-hold]", (n) => n.length);
say("   hold sentence still on screen:", nowHeld);
const commit2 = await page.$('.modal-foot button[data-variant="danger"]');
say("   commit disabled with the blockers clear:", await commit2.evaluate((el) => el.hasAttribute("disabled")));

// Both answers are required — press with an empty form first.
await commit2.click();
await page.waitForTimeout(300);
say(
  "   pressed empty →",
  JSON.stringify(await page.$$eval("[data-field-error], .field-error", (n) => n.map((e) => e.textContent.trim()))),
);
await page.screenshot({ path: `${OUT}/3-dialog-free.png` });

await page.fill("#status-effective-date", "2026-09-08");
await page.fill("#status-reason", "Walkthrough — building demolished");
await page.click('.modal-foot button[data-variant="danger"]');
await page.waitForTimeout(1500);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector("h1", { timeout: 30000 });
say("\n── 5 · AFTERWARDS (the clear property)");
say("   pills:", JSON.stringify(await pills(page)));
const buttonsAfter = await page.$$eval("button", (bs) =>
  bs.map((b) => b.textContent.trim()).filter(Boolean),
);
say("   header buttons:", JSON.stringify(buttonsAfter));
await page.click('button:has-text("Change status")');
await page.waitForSelector('[data-consequence="status-change"]', { timeout: 20000 });
say("   dialog title now:", await page.$eval(".modal-title", (el) => el.textContent.trim()));
const back = await page.$('.modal-foot button[data-variant="primary"]');
say("   reactivation button:", back ? (await back.textContent()).trim() : "(absent)");
say("   counts drawn on the reactivation:", (await page.$$("[data-dependency]")).length);
await page.screenshot({ path: `${OUT}/4-reactivate.png` });

// ══ 6 · THE UNIT'S OWN DIALOG ═════════════════════════════════════════════
say("\n── 6 · THE UNIT PAGE");
const someUnit = target.unit_rows[0];  // the HELD property's unit — an open account on it
await page.goto(`${BASE}/${TENANT}/premises/units/${someUnit.id}`, { waitUntil: "networkidle" });
await page.waitForSelector("h1", { timeout: 30000 });
const unitButtons = await page.$$eval("button", (bs) =>
  bs.map((b) => b.textContent.trim()).filter(Boolean),
);
say("   header buttons:", JSON.stringify(unitButtons));
await page.click('button:has-text("Change status")');
await page.waitForSelector('[data-consequence="status-change"]', { timeout: 20000 });
say("   dialog title:", await page.$eval(".modal-title", (el) => el.textContent.trim()));
const unitCounts = await page.$$eval("[data-dependency]", (rows) =>
  rows.map((row) => `${row.getAttribute("data-dependency")}=${row.textContent.trim()}`),
);
say("   counts:", JSON.stringify(unitCounts));
const unitHold = await page.$$eval("[data-status-hold]", (n) => n.map((e) => e.textContent.trim()));
say("   hold:", JSON.stringify(unitHold));
await page.screenshot({ path: `${OUT}/5-unit-dialog.png` });

// ══ 7 · A ROLE THAT MAY NOT PRESS IT SEES NO BUTTON AT ALL ═══════════════
// CR-089: *"A read-only role sees no button at all — absent, not greyed."*
// ⚠ AND THE CASE THAT MATTERS IS NOT THE READ-ONLY ONE. A Billing Clerk holds
// **Full** on Premises/Accounts and may create and edit — and the status
// endpoint is `@require_role(SYSTEM_ADMIN)`. Gating the button on the A4 CELL
// would have offered it to them over a call that can only 403, which is why
// this walk signs in a second time rather than reasoning about it.
const CLERK = process.env.CLERK_EMAIL ?? "sam.reyes@sample.test";
const clerkPage = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
await clerkPage.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await clerkPage.fill("#signin-email", CLERK);
await clerkPage.fill("#signin-password", PASSWORD);
await clerkPage.click('button[type="submit"]');
await clerkPage.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("\n── 7 · SIGNED IN AS A BILLING CLERK:", CLERK);
for (const [what, url] of [
  ["property", `${BASE}/${TENANT}/premises/${target.id}`],
  ["unit", `${BASE}/${TENANT}/premises/units/${target.unit_rows[0].id}`],
]) {
  await clerkPage.goto(url, { waitUntil: "networkidle" });
  // ⚠ NOT `waitForSelector("h1")`. A role that may not read the surface at all
  // lands on the A18 §6 denied panel, which has no H1 — so waiting for one
  // turns "the clerk cannot even open this" into a TIMEOUT rather than into the
  // reading it is. Wait for the frame, then read what is on it.
  await clerkPage.waitForSelector("main, [role='main'], .met-page", { timeout: 30000 });
  await clerkPage.waitForTimeout(800);
  const labels = await clerkPage.$$eval("button", (bs) =>
    bs.map((b) => b.textContent.trim()).filter(Boolean),
  );
  say(`   ${what} buttons:`, JSON.stringify(labels));
  say(`   ${what} "Change status" present:`, labels.includes("Change status"));
}
await clerkPage.screenshot({ path: `${OUT}/6-clerk-no-button.png` });

await browser.close();
say("\nscreenshots in", OUT);
