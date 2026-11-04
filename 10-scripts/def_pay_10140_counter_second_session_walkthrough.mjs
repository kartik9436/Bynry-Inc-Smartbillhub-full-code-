// DEF-PAY-10140 — a second counter on one day, walked through the screens.
//
//   WEB=http://127.0.0.1:8091 OUT=05-prototype/counter-second-session-2026-10-14 \
//     node 10-scripts/def_pay_10140_counter_second_session_walkthrough.mjs
//
// Run against a PRIVATE copy of the demo database that carries the PO's state:
// Dana's CTR-261013-DW (06:24–06:44, counted) and a second till opened 13:04 the
// same day, written before payments/0050 and repaired by it to CTR-261013-DW-2.
//
//   A · the repaired till opens by its code, and Force close works on it
//   B · an unknown code shows the server's reason, not "did not answer"
//   C · today: open → close → open again as the same person; the second is -2
//   D · record a cash payment into the second, then force close it
// Prints one line per step; screenshots go to OUT.
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

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

const WEB = process.env.WEB || "http://127.0.0.1:8091";
const TENANT = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/counter-second-session-2026-10-14";
const REPAIRED = process.env.REPAIRED || "CTR-261013-DW-2";
const ACCOUNT_NO = process.env.ACCOUNT || "AC-2026-00001";
const STEPS = (process.env.STEPS || "A,B,C,D").split(",");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROME || "/opt/pw-browsers/chromium", args: ["--disable-dev-shm-usage", "--no-sandbox", "--no-zygote", "--disable-gpu", "--disable-features=site-per-process"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
// CLOCK (ISO instant) moves the BROWSER clock, for a walk whose server runs on a
// shifted day (combined walk 2026-10-14): a till opens only on the utility's today.
if (process.env.CLOCK) await page.clock.setSystemTime(new Date(process.env.CLOCK));
const say = (step, what) => console.log(`[${step}] ${what}`);
page.on("pageerror", (e) => say("console", `PAGE ERROR: ${e.message}`));
page.on("console", (m) => process.env.DEBUG && say("console", `${m.type()}: ${m.text().slice(0, 200)}`));
page.on("requestfailed", (r) => process.env.DEBUG && say("net", `FAILED ${r.method()} ${r.url()} ${r.failure()?.errorText}`));
page.on("response", async (r) => {
  if (process.env.DEBUG) say("net", `${r.request().method()} ${r.url()} ${r.status()}`);
  if (r.url().includes("/counters") && r.status() >= 400) {
    say("api", `${r.request().method()} ${new URL(r.url()).pathname} → ${r.status()}`);
  }
});
const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
const body = () => page.evaluate(() => document.body.innerText);
const uuidOnScreen = async () =>
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(await body());

async function openCounter(code) {
  await page.goto(`${WEB}/${TENANT}/payments/counter/${code}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
}

async function forceClose(code, why) {
  // From the Counters list: the row's own Force close action. The row is
  // matched on its WHOLE code cell — `CTR-261013-DW` is a prefix of `-2`.
  await page.goto(`${WEB}/${TENANT}/payments/counter`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const exact = new RegExp(`^\\s*${code.replace(/[-]/g, "\\-")}\\s*$`);
  const row = page.locator("tr").filter({ has: page.locator("td", { hasText: exact }) }).first();
  await row.locator('button:has-text("Force close"), a:has-text("Force close")').first().click();
  await page.waitForTimeout(1200);
  await page.fill("textarea#note, #note", why);
  await shot(`force-close-${code}`);
  await page.locator('.modal-card button:has-text("Force close"), [role="dialog"] button:has-text("Force close")').last().click();
  await page.waitForTimeout(2000);
}

try {
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
  await page.waitForTimeout(5000); // a loaded machine hydrates slowly
  await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
  // Wait for the session, not for the dashboard: the dashboard's map is not what
  // this walk is about and is the heaviest page in the product.
  await Promise.all([
    page.waitForResponse((r) => r.request().method() === "POST" && r.status() < 400, {
      timeout: 90000,
    }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(1500);

  if (STEPS.includes("A")) {
    await page.goto(`${WEB}/${TENANT}/payments/counter`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await shot("01-counters-list-after-repair");
    const text = await body();
    say("A", `list shows CTR-261013-DW: ${/CTR-261013-DW(?!-)/.test(text)} · ${REPAIRED}: ${text.includes(REPAIRED)}`);
    await openCounter(REPAIRED);
    await shot("02-repaired-counter-opens");
    const opened = await body();
    say("A", `${REPAIRED} opens: ${!opened.includes("could not load")} · uuid on screen: ${await uuidOnScreen()}`);
    await forceClose(REPAIRED, "Shift ended without a count");
    await shot("03-after-force-close-repaired");
    await openCounter(REPAIRED);
    say("A", `after force close the page reads closed: ${/forced|closed/i.test(await body())}`);
  }

  if (STEPS.includes("B")) {
    await openCounter("CTR-261013-ZZ");
    await shot("04-unknown-code-shows-the-reason");
    const text = await body();
    say("B", `reason shown: ${text.includes("This counter does not exist.")} · old line: ${text.includes("did not answer")}`);
  }

  if (STEPS.includes("C")) {
    for (const round of [1, 2]) {
      await page.goto(`${WEB}/${TENANT}/payments/counter?start=1`, { waitUntil: "networkidle" });
      await page.waitForTimeout(1500);
      await page.selectOption("#service_centre", { index: 1 }).catch(() => undefined);
      await page.fill("#opening_float", "200.00");
      await shot(`0${4 + round}-start-counter-round-${round}`);
      await page.locator('.modal-card button:has-text("Start"), [role="dialog"] button:has-text("Start")').last().click();
      await page.waitForTimeout(2500);
      const where = new URL(page.url()).pathname;
      say("C", `round ${round} opened → ${where}`);
      if (round === 1) {
        await page.locator('button:has-text("Close batch")').first().click();
        await page.waitForTimeout(800);
        const boxes = page.locator('.modal-card input[inputmode="decimal"], [role="dialog"] input[inputmode="decimal"]');
        if ((await boxes.count()) > 0) await boxes.first().fill("200.00");
        await shot("06-close-round-1");
        await page.locator('.modal-card button:has-text("Close batch"), [role="dialog"] button:has-text("Close batch")').last().click();
        await page.waitForTimeout(2500);
      } else {
        await shot("07-second-counter-same-day");
        say("C", `second counter code in address: ${where.split("/").pop()}`);
      }
    }
  }

  if (STEPS.includes("D")) {
    const code = process.env.SECOND || "CTR-261014-DW-2";
    // The door the clerk uses: My counter → Record payment.
    await openCounter(code);
    await page.locator('a:has-text("Record payment"), button:has-text("Record payment")').first().click();
    await page.waitForTimeout(2500);
    await page.fill("#account_id", ACCOUNT_NO);
    await page.waitForTimeout(2500);
    await page.locator('[role="option"]', { hasText: ACCOUNT_NO }).first().click();
    await page.waitForTimeout(1500);
    await page.fill("#amount", "25.00");
    const methods = await page.$$eval("#method option", (opts) => opts.map((o) => [o.value, o.textContent]));
    const cash = methods.find(([value, label]) => /cash/i.test(`${value} ${label}`));
    if (cash) await page.selectOption("#method", cash[0]);
    await page.waitForTimeout(1500);
    const form = await body();
    say("D", `record form names the till ${code}: ${form.includes(code)}`);
    await shot("08-record-cash-into-second-counter");
    await page.locator('button[type="submit"]').last().click();
    await page.waitForTimeout(3500);
    await shot("09-payment-recorded");
    await openCounter(code);
    await shot("10-second-counter-holds-the-payment");
    say("D", `counter page after the payment: ${(await body()).match(/\d+ payments?/)?.[0]}`);
    await forceClose(code, "Supervisor sealing the second till");
    await shot("11-second-counter-force-closed");
    const after = await body();
    const row = after.split("\n").find((line) => line.startsWith(code)) ?? "";
    say("D", `list row after force close: ${row.replace(/\t/g, " | ")}`);
  }
} catch (error) {
  say("walk", `threw: ${error.message}`);
  await shot("zz-where-it-stopped").catch(() => undefined);
} finally {
  await browser.close();
}
