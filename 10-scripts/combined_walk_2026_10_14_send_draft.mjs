#!/usr/bin/env node
// Combined walk step 7 — the clerk sends a move-out's drafted final bill from
// Billing (Approve on the bill page), then reads the move-out record and the
// account. CW_BILL_ID=<invoice uuid> CW_ACCOUNT_ID=<account uuid> CW_SHOT=S7-send
import { open, BASE, T } from "./combined_walk_2026_10_14_lib.mjs";

const BILL = process.env.CW_BILL_ID;
const ACCOUNT = process.env.CW_ACCOUNT_ID;
const SHOT = process.env.CW_SHOT || "S7-send";
const w = await open({ clock: process.env.CW_CLOCK });
const { page, check, shot } = w;
try {
  await w.staff();
  await page.goto(`${BASE}/${T}/billing/bills/${BILL}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-bil="approve-draft"]', { timeout: 30000 });
  await shot(`${SHOT}-1-bill-draft.png`);
  await page.click('[data-bil="approve-draft"]');
  await page.waitForTimeout(800);
  const ticks = page.locator('[role="dialog"] input[type="checkbox"]');
  for (let i = 0; i < (await ticks.count()); i += 1) await ticks.nth(i).check({ force: true });
  await shot(`${SHOT}-2-approve-dialog.png`);
  await page.evaluate(() => {
    const dialog = document.querySelector('[role="dialog"]');
    const go = [...dialog.querySelectorAll("button")].reverse().find((b) => /approve|send/i.test(b.textContent ?? "") && !b.disabled);
    go?.click();
  });
  await page.waitForTimeout(6000);
  await shot(`${SHOT}-3-bill-issued.png`);
  const text = await page.locator("main").innerText();
  check("the bill reads Issued", /\bIssued\b/.test(text));
  if (ACCOUNT) {
    await page.goto(`${BASE}/${T}/accounts/${ACCOUNT}`, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle").catch(() => undefined);
    await page.waitForTimeout(1500);
    const acct = await page.locator("main").innerText();
    const owner = (acct.match(/To the owner[^\n]*\n?[^\n]*/) || [""])[0];
    check("the account says the money went to the owner", /Posted/.test(owner), owner.replace(/\n/g, " "));
    await shot(`${SHOT}-4-account.png`);
  }
} catch (e) {
  check("send ran to the end", false, String(e).split("\n")[0]);
}
process.exit(await w.done());
