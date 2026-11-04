// ── Trace ──────────────────────────────────────────────
// Question: OQ-INT-12398 — CLOSED 2026-09-17. PO, verbatim: "a) A short line
//           under the field when you clear it — "This allows any address."
//           - yes okay". The options put were (a) a line, (b) a dialog,
//           (c) leave it.
// Screens:  S147 · INT-07, /:tenant/settings/connectors/:providerKey/configure
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output) · law 7
//           habit 2 (what would make this pass wrongly?) · B14 rule 33.
// ───────────────────────────────────────────────────────
/**
 * Clearing a non-empty allowed-addresses list says so — ONCE.
 *
 *     BASE=http://127.0.0.1:5300 KEY=erp_msgp \
 *       node 10-scripts/oq_int_12398_allowlist_cleared_walkthrough.mjs
 *
 * ⚠ **PICK A CONNECTOR THAT HAS NEVER HELD A LIST, OR STEP A PROVES NOTHING.**
 * The first run of this walk used `payments_kiosk`, which already had
 * `198.51.100.0/24` stored — so step A reported the line appearing and read as
 * a FAILURE of the always-blank rule when it was really testing the cleared
 * rule twice. `erp_infor` and `erp_msgp` hold no connection on the demo tenant.
 * That is hard-won law 7's *looking at the wrong thing*, met in the middle of
 * writing the check for it.
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY.** A build keyed off *the box is
 * empty* alone renders the line permanently — steps C and D would both look
 * right and only step A would catch it, which is why A runs FIRST and on a
 * never-connected connector. A build keyed off a ref in `onChange` passes C
 * and fails nothing else; D and A together pin it.
 *
 * Step E asserts the ABSENCE of a dialog, because the PO declined one
 * explicitly and a later lane adding one would be reversing a ruling.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");
const BASE = process.env.BASE ?? "http://127.0.0.1:5300";
const TENANT = process.env.TENANT ?? "brazosbend";
const KEY = process.env.KEY ?? "payments_kiosk";
const OUT = process.env.OUT ?? "/tmp/oq-int-12398";
await fs.mkdir(OUT, { recursive: true });

const html = await (await fetch(`${BASE}/${TENANT}/settings/integrations`)).text();
console.log(`STACK: ${BASE} · bundle ${(/assets\/(index-[^"]+\.js)/.exec(html) ?? [])[1]}`);

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 20000 });

const url = `${BASE}/${TENANT}/settings/connectors/${KEY}/configure`;
const lineText = () => page.evaluate(() => {
  const n = document.querySelector("[data-allowlist-cleared]");
  return n ? n.textContent.trim() : null;
});

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForSelector("#field-allowed_addresses", { timeout: 15000 });

// ── A · the list is ALREADY blank (nothing stored) ────────────────────────
console.log(`A. on arrival, box = ${JSON.stringify(await page.inputValue("#field-allowed_addresses"))}`);
console.log(`   line: ${JSON.stringify(await lineText())}`);
await page.fill("#field-allowed_addresses", "10.0.0.1");
await page.fill("#field-allowed_addresses", "");
console.log(`A. typed then cleared an ALWAYS-BLANK list -> line: ${JSON.stringify(await lineText())}`);
await page.screenshot({ path: `${OUT}/a-always-blank.png` });

// ── B · save a real list, so the connection HAS one ───────────────────────
await page.fill("#field-allowed_addresses", "198.51.100.0/24");
await page.locator("button", { hasText: /^Save and test$/ }).first().click();
await page.waitForTimeout(3500);
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForSelector("#field-allowed_addresses", { timeout: 15000 });
console.log(`B. reopened with a stored list, box = ${JSON.stringify(await page.inputValue("#field-allowed_addresses"))}`);
console.log(`   line on arrival (must be null): ${JSON.stringify(await lineText())}`);
await page.screenshot({ path: `${OUT}/b-stored-list.png` });

// ── C · clear it — the line appears ───────────────────────────────────────
await page.fill("#field-allowed_addresses", "");
console.log(`C. CLEARED a stored list -> line: ${JSON.stringify(await lineText())}`);
await page.screenshot({ path: `${OUT}/c-cleared.png` });

// ── D · put a value back — the line goes ──────────────────────────────────
await page.fill("#field-allowed_addresses", "203.0.113.7");
console.log(`D. typed a value back -> line: ${JSON.stringify(await lineText())}`);

// ── E · no dialog anywhere (the PO declined one) ──────────────────────────
await page.fill("#field-allowed_addresses", "");
const dialogs = await page.locator('[role="dialog"]').count();
console.log(`E. clearing again -> dialogs on screen: ${dialogs} (the PO chose the line over a dialog)`);
await browser.close();
console.log("screenshots in", OUT);
