// ── `DEF-PAY-6342` — MARK A LETTER RETURNED, SEE THE ACCOUNT SAY SO, CLEAR IT ──
//
// The PO asked what happens when a clerk presses *Mark returned*. The answer
// was: a record, an audit row — and nothing a person could see. The account
// page went on reading **Bad address: No**, there was no banner, and nothing
// could clear the flag. The backend suite now proves every link of that chain
// through its routes; only a browser can prove a clerk READS it (hard-won law 6).
//
// ⚠ IT WRITES. Run it against a CLONE (`10-scripts/proof-db.sh clone badaddr`),
// never a shared database: it marks one letter returned and clears it again.
//
//   BA_BASE      default http://127.0.0.1:8762   (node server.mjs → runserver)
//   BA_TENANT    default brazosbend
//   BA_EMAIL     default dana@brazosbendutilities.com
//   BA_PASSWORD  default S3cure!passw0rd
//   BA_ACCOUNT   the account id whose letter is marked (it has a mailing row)
//   BA_INVOICE   that letter's bill id
//   BA_SEEDED    an account flagged with NO return behind it (a migration's flag)
//   BA_CHROME    default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//   BA_SHOTS     where screenshots go
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { join } from "node:path";

const BASE = process.env.BA_BASE || "http://127.0.0.1:8762";
const T = process.env.BA_TENANT || "brazosbend";
const EMAIL = process.env.BA_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.BA_PASSWORD || "S3cure!passw0rd";
const ACCOUNT = process.env.BA_ACCOUNT;
const INVOICE = process.env.BA_INVOICE;
const SEEDED = process.env.BA_SEEDED;
const CHROME = process.env.BA_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.BA_SHOTS || ".";
if (!ACCOUNT || !INVOICE) {
  console.error("REFUSED: BA_ACCOUNT and BA_INVOICE are required.");
  process.exit(2);
}

const R = [];
const ok = (n, c, d = "") => {
  R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
  console.log(R[R.length - 1]);
};
const BANNER = "Post came back from this address.";

/** The Overview's `Bad address` value, read off the rendered page. */
async function badAddressValue(p) {
  // The Overview renders asynchronously; wait for the row before reading it.
  await p.getByText("Bad address", { exact: true }).first().waitFor({ timeout: 15000 });
  const text = await p.locator("body").innerText();
  const m = /Bad address\s*\n\s*(Yes|No)/.exec(text);
  return m ? m[1] : null;
}

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

// ── 1 · BEFORE: no banner, `Bad address: No` ────────────────────────────────
await p.goto(`${BASE}/${T}/accounts/${ACCOUNT}`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
ok("before: no returned-post banner", (await p.locator("[data-returned-post-banner]").count()) === 0);
ok("before: the Overview reads Bad address: No", (await badAddressValue(p)) === "No");

// ── 2 · MARK THE LETTER RETURNED, FROM THE BILL'S OWN DELIVERY ROW ──────────
await p.goto(`${BASE}/${T}/billing/bills/${INVOICE}`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
// The delivery rows live on the bill's `Sent` tab.
await p.getByRole("tab", { name: /^Sent/ }).click();
await p.waitForTimeout(1000);
await p.getByRole("button", { name: "Mark returned" }).first().click();
const dialog = p.getByRole("dialog");
await dialog.locator("#returned_on").fill("2026-09-08");
await p.screenshot({ path: join(SHOTS, "def-pay-6342-1-mark.png"), fullPage: true });
await dialog.getByRole("button", { name: "Mark returned" }).click();
await p.waitForTimeout(2000);
ok("the bill's delivery row now carries a came-back date", !(await p.getByRole("dialog").count()));

// ── 3 · AFTER: the banner, and `Bad address: Yes` ──────────────────────────
await p.goto(`${BASE}/${T}/accounts/${ACCOUNT}`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
const banner = p.locator("[data-returned-post-banner]");
ok("after: the banner is on the account", (await banner.count()) === 1);
ok("after: it states the fact", ((await banner.innerText()) || "").includes(BANNER));
ok("after: the Overview reads Bad address: Yes", (await badAddressValue(p)) === "Yes");
await p.screenshot({ path: join(SHOTS, "def-pay-6342-2-banner.png"), fullPage: true });

// ── 4 · THE CLEAR STEP ROUTES ON WHERE THE LETTER WENT ─────────────────────
await banner.getByRole("button", { name: "Resolve" }).click();
const clear = p.getByRole("dialog");
await clear.locator("[data-returned-post-letters]").waitFor({ timeout: 10000 });
const letters = await clear.locator("[data-returned-post-letters]").innerText();
ok("the letter is listed as sent to the MAILING address", letters.includes("Mailing address"), letters.trim());
ok("the mailing correction is offered", (await clear.getByText("Correct mailing address").count()) === 1);
ok("no premises link for a mailing letter", (await clear.locator("[data-returned-post-premises]").count()) === 0);
await p.screenshot({ path: join(SHOTS, "def-pay-6342-3-clear-step.png"), fullPage: true });
await clear.getByText("Address is correct").click();
await clear.getByRole("button", { name: "Clear flag" }).click();
await p.waitForTimeout(2500);

// ── 5 · CLEARED: banner gone, `Bad address: No` ────────────────────────────
ok("cleared: the banner is gone", (await p.locator("[data-returned-post-banner]").count()) === 0);
ok("cleared: the Overview reads Bad address: No", (await badAddressValue(p)) === "No");
await p.screenshot({ path: join(SHOTS, "def-pay-6342-4-cleared.png"), fullPage: true });

// ── 6 · A FLAG WITH NO RETURN BEHIND IT (a migration's) IS STILL SHOWN ─────
if (SEEDED) {
  await p.goto(`${BASE}/${T}/accounts/${SEEDED}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const seeded = p.locator("[data-returned-post-banner]");
  ok("a migrated flag shows the banner too", (await seeded.count()) === 1);
  await seeded.getByRole("button", { name: "Resolve" }).click();
  await p.getByRole("dialog").locator("[data-returned-post-none]").waitFor({ timeout: 10000 });
  ok("and says no letter is on file", true);
  await p.screenshot({ path: join(SHOTS, "def-pay-6342-5-no-letter.png"), fullPage: true });
}

await b.close();
console.log("\n" + R.join("\n"));
process.exit(R.some((r) => r.startsWith("FAIL")) ? 1 : 0);
