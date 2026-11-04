// ── Trace ──────────────────────────────────────────────
// Change:  P4 (Finance blueprint p017) — the walkthrough that OPENS every
//          Finance download control in a real browser against a booted stack,
//          presses the ones that should work, and photographs the result.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app against the design —
//          the one law with no tool behind it) · hard-won law 2, BOTH
//          directions (a live screen behind a dead control is invisible to
//          every gate) · B14 rule 33 (rationale is ZERO words on screen)
//          Screens: 3·1 Deposits · 4·1 By authority · 6·1 General ledger ·
//          6·2 Close & export · S59 · S60 · the customer statement
// ───────────────────────────────────────────────────────
//
// **WHY THIS EXISTS RATHER THAN A UNIT TEST.** `p45DownloadsWork.dom.test.tsx`
// asserts that ONE control is pressable and calls the right resource. It cannot
// tell you whether the OTHER four are, whether a refusal sentence is still
// painted somewhere on the page, or whether the screen looks like the drawing.
// No gate in this repo reads rendered output, so this script is the check — and
// the photographs it takes are the evidence.
//
// **WHAT IT ASSERTS, per screen:**
//   1 · the page has a real `<h1>` — a screen that renders nothing fails here;
//   2 · every download control on it is found, and its `disabled` state is
//       RECORDED rather than assumed;
//   3 · no retired refusal sentence appears anywhere in the body text;
//   4 · no raw catalogue key (`finance.…`, `reports.…`) leaks into the page.
//
// It is deliberately NOT a pass/fail gate over the disabled states: `P4.6`'s
// deposit slip and `P4.12`'s Export view are separate tasks, so a control that
// is still disabled is REPORTED with its reason rather than failed. The report
// is what a person reads.
//
// CONFIG (env): P4_BASE (http://127.0.0.1:8081) · P4_TENANT (brazosbend) ·
//   P4_EMAIL · P4_PASSWORD · P4_OUT (screenshot dir) · P4_WIDTHS (1440,1280)
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// `playwright-core` is pinned in 07-frontend for the e2e suite; borrowed the
// same way `12-smoke-walkthrough.mjs` borrows it, so this script declares no
// dependency of its own and cannot drift to a different browser build.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.P4_BASE ?? "http://127.0.0.1:8081";
const TENANT = process.env.P4_TENANT ?? "brazosbend";
const EMAIL = process.env.P4_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.P4_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.P4_OUT ?? "/tmp/p4-finance-screens";
const WIDTHS = (process.env.P4_WIDTHS ?? "1440,1280").split(",").map((n) => Number(n.trim()));

/** The three sentences `P4.5` DELETED. None may appear on any screen. */
const RETIRED = [
  "Downloads are not built yet",
  "needs the report export service",
  "no download",
];

const findings = [];
const observed = [];

/** Chromium, wherever this container put it — the smoke script's own resolver. */
function resolveChromium() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  if (!existsSync(root)) return undefined;
  for (const entry of readdirSync(root)) {
    if (!entry.startsWith("chromium")) continue;
    for (const candidate of [
      join(root, entry, "chrome-linux", "chrome"),
      join(root, entry, "chrome-linux", "headless_shell"),
    ]) {
      if (existsSync(candidate)) return candidate;
    }
  }
  return undefined;
}

/**
 * Photograph one screen and record every download control on it.
 *
 * ⚠ **THE DISABLED STATE IS READ FROM THE DOM, NEVER INFERRED FROM THE SOURCE.**
 * That is the whole point: `DEF-CWP-3925` was a live screen behind a dead
 * control, and every check in the repo passed over it because each asked about
 * the code rather than about the page.
 */
async function shoot(page, name, url, { width }) {
  await page.setViewportSize({ width, height: 1000 });
  await page.goto(url, { waitUntil: "networkidle" });
  try {
    await page.waitForSelector("h1", { timeout: 15000 });
  } catch {
    findings.push(`${name}: no <h1> — the screen rendered nothing`);
  }
  // Let the report behind the control finish loading; a control disabled
  // because its data has not arrived is not the same statement as one held.
  await page.waitForTimeout(1500);

  const heading = await page.locator("h1").first().innerText().catch(() => "(none)");
  const body = await page.locator("body").innerText().catch(() => "");

  for (const sentence of RETIRED) {
    if (body.includes(sentence)) {
      findings.push(`${name}: a RETIRED refusal sentence is still on screen — "${sentence}"`);
    }
  }
  const key = body.match(/\b(finance|reports|ledger|download)\.[a-zA-Z0-9_.]{3,}/);
  if (key) findings.push(`${name}: a raw catalogue key leaked into the page — ${key[0]}`);

  const buttons = page.locator('[data-download="button"], [data-download="menu"]');
  const count = await buttons.count();
  const states = [];
  for (let i = 0; i < count; i += 1) {
    const one = buttons.nth(i);
    const disabled = await one.isDisabled().catch(() => null);
    const title = await one.getAttribute("title").catch(() => null);
    states.push({ disabled, title });
  }
  observed.push({ screen: name, width, heading, downloads: count, states });

  // ⚠ **`fullPage: true` DOES NOT WORK ON THIS PRODUCT AND FAILS SILENTLY.**
  // The shell scrolls an inner `main.view`, not the document, so Playwright is
  // told the page is one viewport tall, believes it, and returns a CROP with no
  // error and no warning — which reads as deliberate framing rather than as
  // truncation. Every Finance shot taken before 2026-09-24 was cropped this
  // way. So the scroller is measured and the VIEWPORT is grown to it, and each
  // shot's height is printed so a reader can tell a short screen from a cut one.
  const needed = await page.evaluate(() => {
    const main = document.querySelector("main.view") || document.body;
    const chrome = window.innerHeight - main.clientHeight;
    return Math.min(9000, Math.ceil(main.scrollHeight + chrome + 24));
  });
  if (needed > 1000) {
    await page.setViewportSize({ width, height: needed });
    await page.waitForTimeout(900);
  }
  const suffix = width === WIDTHS[0] ? "" : `-${width}`;
  const file = join(OUT, `${name}${suffix}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(
    `  ${name}${suffix}  h1="${heading}"  downloads=${count} ` +
      (states.map((s) => (s.disabled ? "DISABLED" : "works")).join(",") || "(none)") +
      `  height=${needed}`,
  );
  return file;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  console.log(`P4 walkthrough: ${BASE} tenant=${TENANT} → ${OUT}`);

  const browser = await chromium.launch({ executablePath: resolveChromium(), headless: true });
  const context = await browser.newContext({ viewport: { width: WIDTHS[0], height: 1000 } });
  const page = await context.newPage();
  page.on("response", (r) => {
    if (r.status() >= 500) findings.push(`5xx: ${r.status()} ${r.request().method()} ${r.url()}`);
  });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  console.log("signed in");

  const screens = [
    ["p4-5-trial-balance", `${BASE}/${TENANT}/finance`],
    ["p4-11-taxes-by-authority", `${BASE}/${TENANT}/finance/taxes`],
    ["p4-12-close-and-export", `${BASE}/${TENANT}/finance/export`],
    ["p4-6-deposit-slip", `${BASE}/${TENANT}/finance/deposits`],
    ["p4-5-by-premises", `${BASE}/${TENANT}/reports/by-premises`],
    ["p4-5-account-ledger", `${BASE}/${TENANT}/reports/account-ledger`],
    ["p4-5-customer-statement", `${BASE}/${TENANT}/reports/customer-statement`],
  ];

  for (const width of WIDTHS) {
    console.log(`── ${width}px ──`);
    for (const [name, url] of screens) {
      await shoot(page, name, url, { width });
    }
  }

  // ── press the trial-balance download and photograph what a clerk sees ────
  await page.setViewportSize({ width: WIDTHS[0], height: 1000 });
  await page.goto(`${BASE}/${TENANT}/finance`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const control = page.locator('[data-download="button"]').first();
  if ((await control.count()) > 0 && !(await control.isDisabled())) {
    await control.click();
    await page.waitForTimeout(1200);
    const tall = await page.evaluate(() => {
      const main = document.querySelector("main.view") || document.body;
      return Math.min(9000, Math.ceil(main.scrollHeight + (window.innerHeight - main.clientHeight) + 24));
    });
    if (tall > 1000) {
      await page.setViewportSize({ width: WIDTHS[0], height: tall });
      await page.waitForTimeout(600);
    }
    await page.screenshot({
      path: join(OUT, "p4-5-trial-balance-pressed.png"),
      fullPage: true,
    });
    console.log("  pressed the trial-balance download");
  } else {
    findings.push("trial balance: the download control is still disabled");
  }

  writeFileSync(join(OUT, "observed.json"), JSON.stringify({ observed, findings }, null, 2));
  await browser.close();

  console.log("");
  if (findings.length === 0) {
    console.log("NO FINDINGS");
  } else {
    console.log(`${findings.length} FINDING(S):`);
    for (const f of findings) console.log(`  · ${f}`);
  }
  console.log(`screenshots: ${OUT}`);
  process.exit(findings.length === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
