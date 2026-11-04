// DEF-CUS-10093 (PO 2026-10-13, option B) — walk a move-out through the screens
// and confirm Complete drafts the final bill, then send that draft from Billing.
//
//   ACCOUNT=AC-2026-00001 READS='{"E-...":"+50"}' DATE=2026-10-12 SHOT=01-residential \
//     BASE=http://127.0.0.1:8082 node 10-scripts/def_cus_10093_move_out_final_draft_walkthrough.mjs
//
// READS maps a meter number to a value or "+N" (last reading plus N), or "estimate".
// SHORTFALL picks step 4's path (collect | payment_plan | transfer) and records it.
// DEPOSIT picks a step-3 deposit option by its data-deposit-option value.
// SEND=1 opens the draft from the completion screen and approves it.
// Prints one JSON line per scenario; screenshots go to OUT.
import { mkdirSync } from "node:fs";

const pw = await import(
  process.env.PW ?? "/home/user/SMARTBillHub/07-frontend/node_modules/playwright/index.mjs"
);
const chromium = pw.chromium ?? pw.default.chromium;
const BASE = process.env.BASE ?? "http://127.0.0.1:8082";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "05-prototype/move-out-final-bill-2026-10-13";
const ACCOUNT_NO = process.env.ACCOUNT;
const DATE = process.env.DATE ?? "2026-10-12";
const READS = JSON.parse(process.env.READS ?? "{}");
const SHOT = process.env.SHOT ?? ACCOUNT_NO;
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
// CLOCK (ISO instant) moves the BROWSER clock, for a walk whose server runs on a
// shifted day (combined walk 2026-10-14) — so the date pickers agree with it.
if (process.env.CLOCK) await page.clock.setSystemTime(new Date(process.env.CLOCK));
const out = { account: ACCOUNT_NO, date: DATE };
if (process.env.DEBUG_PREVIEW) {
  page.on("response", async (response) => {
    if (!response.url().includes("final-bill-preview")) return;
    const body = await response.json().catch(() => null);
    console.error(
      JSON.stringify({
        sent: response.request().postData(),
        priced: body?.priced,
        total: body?.total,
        unavailable: body?.priced_unavailable,
      }),
    );
  });
}
const shot = (name) => page.screenshot({ path: `${OUT}/${SHOT}-${name}.png`, fullPage: true });
const advance = () =>
  page.evaluate(() => {
    const button = [...document.querySelectorAll('[data-wizard="actions"] button')].find(
      (b) => /continue/i.test(b.textContent ?? "") && !b.disabled,
    );
    if (button === undefined) return false;
    button.click();
    return true;
  });
const uuidOnScreen = () =>
  page.evaluate(() =>
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(document.body.innerText),
  );

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  if (process.env.BILL_HREF) {
    out.done = { href: process.env.BILL_HREF };
  } else {
  const accountId = await page.evaluate(
    async ([tenant, no]) => {
      const r = await fetch(`/api/${tenant}/accounts?q=${encodeURIComponent(no)}&per=20`, {
        headers: { Accept: "application/json" },
      });
      const body = await r.json();
      const rows = body.results ?? body.data?.results ?? body.items ?? [];
      return rows.find((row) => row.account_no === no)?.id ?? "";
    },
    [TENANT, ACCOUNT_NO],
  );
  if (!accountId) throw new Error(`no account ${ACCOUNT_NO}`);

  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=1`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  await advance();
  await page.waitForTimeout(1500);
  await page.fill("#moved_out_on", DATE);
  await page.waitForTimeout(400);
  const reason = await page.$("#close_reason");
  if (reason !== null) await reason.selectOption({ index: 1 }).catch(() => undefined);
  await page.waitForTimeout(1500);
  const boxes = page.locator('input[id^="moveOut-read-"]:not([id^="moveOut-read-date-"])');
  const typed = [];
  for (let i = 0; i < (await boxes.count()); i += 1) {
    const box = boxes.nth(i);
    const row = await box.evaluate((el) => el.closest("tr")?.innerText ?? "");
    const meter = Object.keys(READS).find((m) => row.includes(m));
    const wanted = meter === undefined ? (process.env.DEFAULT_READ ?? "+0") : READS[meter];
    if (wanted === "estimate") {
      const tick = box.locator("xpath=ancestor::tr//input[@type='checkbox']");
      if ((await tick.count()) > 0) await tick.first().check({ force: true });
      typed.push({ row: row.split("\n")[0], estimate: true });
      continue;
    }
    const last = (await box.inputValue()).replace(/,/g, "");
    if (last === "" && meter === undefined && String(wanted).startsWith("+")) {
      typed.push({ row: row.split("\n")[0].slice(0, 40), last, value: null });
      continue; // no reading on file: a "+N" default has nothing to add to
    }
    const value = String(wanted).startsWith("+")
      ? String(Number(last || "0") + Number(String(wanted).slice(1)))
      : String(wanted);
    await box.fill(value);
    typed.push({ row: row.split("\n")[0].slice(0, 40), last, value });
  }
  out.typed = typed;
  await shot("step2");
  await advance();
  // Wait for step 3's figure: the draft-bill table, or its stated absence.
  await page
    .waitForFunction(
      () =>
        document.querySelector('[data-move-matrix="draft-bill"]') !== null ||
        /not generated|cannot be priced/i.test(document.body.innerText),
      null,
      { timeout: Number(process.env.STEP3_WAIT ?? 30000) },
    )
    .catch(() => undefined);
  await page.waitForTimeout(1500);
  await shot("step3");
  const step3 = await page.evaluate(() => {
    const table = document.querySelector('[data-move-matrix="draft-bill"]');
    const text = document.body.innerText;
    const rows = table ? [...table.querySelectorAll("tr")].map((tr) => tr.innerText) : [];
    const totalRow = rows.reverse().find((r) => /^\s*Total\b/i.test(r)) ?? "";
    const total = (totalRow.match(/-?\$[\d,]+\.\d\d/) ?? [null])[0];
    const money = (label) =>
      (text.match(new RegExp(`${label}\\s*(-?\\s?\\$[\\d,]+\\.\\d\\d)`)) ?? [null, null])[1];
    return {
      priced: table !== null,
      total,
      finalBillNet: money("Final bill, net"),
      priorBalance: money("Prior balance"),
      depositApplied: money("Deposit applied"),
      verdict: (text.match(/\n(Short by|Refund due|Settled|Owed back|Refund)[^\n]*\s*(-?\$[\d,]+\.\d\d)/) ?? [null])[0],
      quantities: table
        ? [...table.querySelectorAll("td")].map((td) => td.innerText).filter((s) => / (kWh|kgal|kW|gal|ccf|therm)/.test(s))
        : [],
      notGenerated: text.includes("not generated"),
    };
  });
  out.step3 = step3;
  // SHORTFALL=collect|payment_plan|transfer records step 4's decision first.
  if (process.env.SHORTFALL) {
    const pick = page.locator(`[data-shortfall-pick="${process.env.SHORTFALL}"]`);
    out.shortfallOffered = await page.evaluate(() =>
      [...document.querySelectorAll("[data-shortfall-pick]")].map(
        (el) => `${el.getAttribute("data-shortfall-pick")}${el.disabled ? " (blocked)" : ""}`,
      ),
    );
    if ((await pick.count()) > 0 && !(await pick.first().isDisabled())) {
      await pick.first().check({ force: true });
      await page.waitForTimeout(400);
      await page.click("[data-shortfall-confirm]");
      await page.waitForTimeout(2500);
      out.shortfallRecorded = process.env.SHORTFALL;
      await shot("step3-decided");
    } else {
      out.shortfallRecorded = null;
      out.shortfallBlocked = await page
        .locator(`[data-shortfall-needs="${process.env.SHORTFALL}"]`)
        .first()
        .innerText()
        .catch(() => null);
    }
  }
  if (process.env.STOP_AT === "3") throw new Error("stopped at step 3 (STOP_AT=3)");
  if (process.env.DEPOSIT) {
    const pick = page.locator(`[data-deposit-option="${process.env.DEPOSIT}"]`);
    if ((await pick.count()) > 0) await pick.first().click();
    await page.waitForTimeout(800);
  }
  await advance();
  await page.waitForTimeout(2500);
  await shot("step4");
  // Complete — advancing through any step left before it.
  let committed = false;
  for (let i = 0; i < 4 && !committed; i += 1) {
    committed = await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find((b) =>
        /Complete move-out/.test(b.textContent ?? ""),
      );
      if (!button || button.disabled) return false;
      button.click();
      return true;
    });
    if (!committed) {
      await advance();
      await page.waitForTimeout(2000);
    }
  }
  out.pressedComplete = committed;
  await page.waitForTimeout(1200);
  // A confirm dialog, if the frame asks one.
  await page.evaluate(() => {
    const dialog = document.querySelector('[role="dialog"]');
    if (!dialog) return;
    const go = [...dialog.querySelectorAll("button")].find((b) => /complete|close|confirm/i.test(b.textContent ?? ""));
    go?.click();
  });
  await page.waitForTimeout(6000);
  await shot("done");
  out.done = await page.evaluate(() => {
    const fact = document.querySelector("[data-move-out-final-bill]");
    const link = fact?.querySelector("a");
    return {
      finalBill: fact ? fact.textContent : null,
      href: link ? link.getAttribute("href") : null,
      refusal: document.querySelector('[role="alert"]')?.textContent ?? null,
      title: (document.body.innerText.match(/Move-out (complete|done)[^\n]*/i) ?? [null])[0],
    };
  });
  out.uuidOnDone = await uuidOnScreen();
  }

  if (process.env.SEND === "1" && out.done.href) {
    await page.goto(`${BASE}${out.done.href}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await shot("bill-draft");
    out.uuidOnBill = await uuidOnScreen();
    await page.click('[data-bil="approve-draft"]');
    await page.waitForTimeout(800);
    const ticks = page.locator('[role="dialog"] input[type="checkbox"]');
    for (let i = 0; i < (await ticks.count()); i += 1) await ticks.nth(i).check({ force: true });
    await shot("approve-dialog");
    await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]');
      const go = [...dialog.querySelectorAll("button")].reverse().find((b) => /approve|send/i.test(b.textContent ?? "") && !b.disabled);
      go?.click();
    });
    await page.waitForTimeout(6000);
    await shot("bill-issued");
    out.afterSend = await page.evaluate(() => ({
      status: (document.body.innerText.match(/\b(Draft|Issued|Open|Paid)\b/) ?? [null])[0],
      toast: document.querySelector('[role="status"]')?.textContent ?? null,
    }));
  }
} catch (error) {
  out.error = String(error);
  await shot("error").catch(() => undefined);
}
console.log(JSON.stringify(out));
await browser.close();
