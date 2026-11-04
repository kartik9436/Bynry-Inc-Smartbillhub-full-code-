// DEF-BIL-10128 / DEF-BIL-10129 — walk move-out steps 2 and 3 on AC-2026-00041
// (Apt 101: M-MASTER-01 + W-5040 + sub-meter SM-7040, sewer at 90% of water).
//
//   BASE=http://127.0.0.1:8090 SHOT=before node 05-prototype/move-out-percent-service-2026-10-14/walk.mjs
//
// READS maps a meter number to a value or "estimate". Prints one JSON line.
import { mkdirSync } from "node:fs";

const pw = await import(
  process.env.PW ?? "/home/user/SMARTBillHub/07-frontend/node_modules/playwright/index.mjs"
);
const chromium = pw.chromium ?? pw.default.chromium;
const BASE = process.env.BASE ?? "http://127.0.0.1:8090";
const TENANT = "brazosbend";
const OUT = process.env.OUT ?? "05-prototype/move-out-percent-service-2026-10-14";
const ACCOUNT_NO = process.env.ACCOUNT ?? "AC-2026-00041";
const DATE = process.env.DATE ?? "2026-10-14";
const READS = JSON.parse(
  process.env.READS ?? '{"W-5040":"2545","SM-7040":"10","M-MASTER-01":"estimate","E-5040":"+0"}',
);
const SHOT = process.env.SHOT ?? "walk";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
const out = { account: ACCOUNT_NO, date: DATE, shot: SHOT, consoleErrors: [] };
page.on("console", (m) => { if (m.type() === "error") out.consoleErrors.push(m.text().slice(0, 300)); });
page.on("pageerror", (e) => out.consoleErrors.push(String(e).slice(0, 300)));
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

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  const accountId = await page.evaluate(
    async ([tenant, no]) => {
      const r = await fetch(`/api/${tenant}/accounts?q=${encodeURIComponent(no)}&per=20`);
      const body = await r.json();
      const rows = body.results ?? body.data?.results ?? body.items ?? [];
      return rows.find((row) => row.account_no === no)?.id ?? "";
    },
    [TENANT, ACCOUNT_NO],
  );
  if (!accountId) throw new Error(`no account ${ACCOUNT_NO}`);
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=1`, { waitUntil: "networkidle" });
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
    if (meter === undefined) continue;
    const wanted = READS[meter];
    if (wanted === "estimate") {
      const tick = box.locator("xpath=ancestor::tr//input[@type='checkbox']");
      if ((await tick.count()) > 0) await tick.first().check({ force: true });
      typed.push({ meter, estimate: true });
      continue;
    }
    const last = (await box.inputValue()).replace(/,/g, "");
    const value = String(wanted).startsWith("+")
      ? String(Number(last || "0") + Number(String(wanted).slice(1)))
      : String(wanted);
    await box.fill(value);
    typed.push({ meter, last, value });
  }
  out.typed = typed;
  // the estimate note asks the server (a draft-bill preparation, a few seconds)
  await page.waitForSelector("[data-move-out-estimate]", { timeout: 60000 }).catch(() => undefined);
  await page.waitForTimeout(1000);
  out.step2Rows = await page.evaluate(() =>
    [...document.querySelectorAll('[data-editable-table="move-out-metered"] tbody tr')].map((tr) =>
      tr.innerText.replace(/\s+/g, " ").trim(),
    ),
  );
  await shot("step2");
  await advance();
  await page
    .waitForFunction(
      () =>
        document.querySelector('[data-move-matrix="draft-bill"]') !== null ||
        /not generated|cannot be priced/i.test(document.body.innerText),
      null,
      { timeout: 60000 },
    )
    .catch(() => undefined);
  await page.waitForTimeout(1500);
  await shot("step3");
  out.step3 = await page.evaluate(() => {
    const table = document.querySelector('[data-move-matrix="draft-bill"]');
    const text = document.body.innerText;
    return {
      priced: table !== null,
      lines: table ? [...table.querySelectorAll("tr")].map((tr) => tr.innerText.replace(/\s+/g, " ").trim()) : [],
      notGenerated: (text.match(/The draft bill is not generated[^\n]*(\n[^\n]*){0,4}/) ?? [null])[0],
    };
  });
} catch (error) {
  out.error = String(error);
  out.url = page.url();
  out.text = (await page.evaluate(() => document.body.innerText).catch(() => "")).slice(0, 600);
} finally {
  console.log(JSON.stringify(out));
  await browser.close();
}
