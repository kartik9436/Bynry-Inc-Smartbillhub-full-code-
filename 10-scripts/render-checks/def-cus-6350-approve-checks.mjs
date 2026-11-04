#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-6350 (Approve checks the property and the unit) ·
//           DEF-CUS-6352 (a move-in's window talked about a build) ·
//           DEF-CUS-6420 (the fee gates approval again)
// Rulings:  PO 2026-09-23 — the Approve window's two layouts, approved with
//           *"please please ensure you follow ui styleguide and correct
//           tailwind components"*; OQ-CUS-12615 / 12616 / 12617
// Why:      hard-won law 6 — no gate reads rendered output. The PO judges the
//           look from these screenshots.
// ───────────────────────────────────────────────────────
/**
 * Open the Approve window on four requests in a real browser and photograph
 * it at 1440×900 (the staff design target) and 1280×900 (the laptop minimum).
 *
 *     BASE=http://127.0.0.1:8742 OUT=/tmp/approve \
 *     REQS='{"fee":"SR-…","occupied":"SR-…","newAddr":"SR-…","near":"SR-…","inPremises":"SR-…"}' \
 *       node 10-scripts/render-checks/def-cus-6350-approve-checks.mjs
 *
 * The requests must be planted first (a free unit with an unpaid fee, an
 * occupied unit, a new address, a near match, an address in Premises). It
 * refuses — exits 1 — when a window does not fit 900px high, when Approve is
 * live over a ✗ row, or when the word "register" reaches the clerk.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8742";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def-cus-6350";
const REQS = JSON.parse(process.env.REQS ?? "{}");

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
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const failures = [];
const say = (s) => console.log(s);
const bad = (s) => {
  failures.push(s);
  say(`  ✗ ${s}`);
};

async function openRequest(page, number) {
  await page.goto(`${BASE}/${TENANT}/requests?q=${encodeURIComponent(number)}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const link = page.getByRole("link", { name: number }).first();
  if ((await link.count()) === 0) {
    const row = page.getByText(number, { exact: true }).first();
    await row.click();
  } else {
    await link.click();
  }
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1200);
}

async function openApprove(page) {
  const main = page.locator("main");
  const buttons = main.getByRole("button", { name: /^Approve$/ });
  await buttons.first().click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor({ timeout: 10000 });
  await page.waitForTimeout(900);
  return dialog;
}

async function pickKind(dialog, label) {
  const radio = dialog.getByRole("radio", { name: label });
  if ((await radio.count()) > 0) await radio.first().click();
  await dialog.page().waitForTimeout(900);
}

async function measure(page, dialog, name) {
  const facts = await dialog.evaluate((d) => {
    const r = d.getBoundingClientRect();
    const rows = [...d.querySelectorAll("[data-check]")].map((li) => ({
      state: li.getAttribute("data-check-state"),
      text: li.innerText.replace(/\s+/g, " ").trim(),
    }));
    // The footer's commit, found by its words: while a check blocks, the kit
    // renders it disabled and it may not be `type="submit"` at all.
    const submit = [...d.querySelectorAll("button")].filter((b) => /^Approve/.test(b.innerText.trim())).pop();
    return {
      top: Math.round(r.top),
      bottom: Math.round(r.bottom),
      scrollH: d.scrollHeight,
      clientH: d.clientHeight,
      inner: [...d.querySelectorAll("*")].some((e) => e.scrollHeight > e.clientHeight + 2 && getComputedStyle(e).overflowY !== "visible"),
      rows,
      submit: submit ? { text: submit.innerText.trim(), disabled: submit.disabled || submit.getAttribute("aria-disabled") === "true" } : null,
      text: d.innerText,
    };
  });
  say(`${name}: dialog ${facts.top}–${facts.bottom}px; submit ${JSON.stringify(facts.submit)}`);
  for (const row of facts.rows) say(`    [${row.state}] ${row.text}`);
  const vh = page.viewportSize().height;
  if (facts.bottom > vh || facts.top < 0) bad(`${name}: the window does not fit ${vh}px high (${facts.top}–${facts.bottom})`);
  if (facts.inner) say(`    note: an element inside the window scrolls`);
  if (/register/i.test(facts.text)) bad(`${name}: the word "register" reaches the clerk`);
  if (facts.submit && !facts.submit.disabled && facts.rows.some((r) => r.state === "bad")) bad(`${name}: Approve is live over a ✗ row`);
  if (!facts.submit) bad(`${name}: no Approve button in the window`);
  return facts;
}

(async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  for (const [w, h] of [[1440, 900], [1280, 900]]) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });
    say(`signed in at ${w}×${h}`);
    const shoot = (n) => page.screenshot({ path: join(OUT, `${w}-${n}.png`) });

    if (REQS.occupied) {
      await openRequest(page, REQS.occupied);
      const d = await openApprove(page);
      await pickKind(d, "Move-in");
      await measure(page, d, `${REQS.occupied} move-in, occupied unit`);
      await shoot("1-move-in-occupied");
      await page.keyboard.press("Escape");
    }
    if (REQS.fee) {
      await openRequest(page, REQS.fee);
      const d = await openApprove(page);
      await pickKind(d, "Move-in");
      await measure(page, d, `${REQS.fee} move-in, fee unpaid`);
      await shoot("2-move-in-fee-unpaid");
      await page.keyboard.press("Escape");
    }
    if (REQS.newAddr) {
      await openRequest(page, REQS.newAddr);
      const d = await openApprove(page);
      await pickKind(d, "New connection");
      await measure(page, d, `${REQS.newAddr} new connection, new address`);
      await shoot("3-new-connection-new-address");
      await page.keyboard.press("Escape");
    }
    if (REQS.near) {
      await openRequest(page, REQS.near);
      const d = await openApprove(page);
      await pickKind(d, "New connection");
      await measure(page, d, `${REQS.near} new connection, near match`);
      await shoot("4-new-connection-near-match");
      const newAddr = d.getByRole("button", { name: "It's a new address" });
      if ((await newAddr.count()) > 0) {
        await newAddr.click();
        await page.waitForTimeout(700);
        await measure(page, d, `${REQS.near} after "It's a new address"`);
        await shoot("5-new-connection-declared-new");
      } else bad(`${REQS.near}: no "It's a new address" button`);
      await page.keyboard.press("Escape");
    }
    if (REQS.inPremises) {
      await openRequest(page, REQS.inPremises);
      const d = await openApprove(page);
      await pickKind(d, "New connection");
      await measure(page, d, `${REQS.inPremises} new connection, in Premises`);
      await shoot("6-new-connection-in-premises");
      await page.keyboard.press("Escape");
    }
    await page.close();
  }
  await browser.close();
  say(failures.length ? `FAIL: ${failures.length}` : "PASS");
  process.exit(failures.length ? 1 : 0);
})();
