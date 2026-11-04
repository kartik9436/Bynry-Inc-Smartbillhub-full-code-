/**
 * walk_bill_link_2026_10_22 — DEF-BIL-10531, in Chromium at 1440 and 390 on a
 * PRIVATE copy of the dev database.
 *
 * PHASE=issue — signed in as the clerk, a one-time fee bill is drafted and sent
 *   by email through the screen's own endpoints; prints `INVOICE <uuid>`.
 *   The caller then reads the queued email back from the database (its body is
 *   rendered by the dispatcher's own renderer) and passes the link as LINK.
 * PHASE=open — a FRESH browser with no session opens LINK: the page must show
 *   the bill, take the secret off the address bar, never send it in any
 *   request URL, and Download must save the PDF to OUT/bill.pdf. Then an
 *   unknown link must show the dead end with the utility's phone.
 *
 *   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *      PUBLIC_APP_ORIGIN=http://127.0.0.1:8742 DATABASE_URL=postgres://…/<private copy> \
 *      python manage.py runserver 127.0.0.1:8741 --noreload)
 *   (cd 07-frontend && npx vite build && PORT=8742 API_PROXY_TARGET=http://127.0.0.1:8741 node server.mjs)
 *   PHASE=issue ACCOUNT=<uuid> CODE=CONN node 10-scripts/walk_bill_link_2026_10_22.mjs
 *   PHASE=open LINK='<the emailed link>' node 10-scripts/walk_bill_link_2026_10_22.mjs
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8742";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/claude-0/shots-bill-link";
mkdirSync(OUT, { recursive: true });

let failures = 0;
function check(name, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  ${detail}` : ""}`);
}
function resolveChromium() {
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
try {
  if ((process.env.PHASE ?? "issue") === "issue") {
    const page = await (await browser.newContext({ viewport: { width: 1440, height: 1100 } })).newPage();
    page.setDefaultTimeout(30000);
    const api = (method, path, body) =>
      page.evaluate(
        async ({ method, url, body }) => {
          const r = await fetch(url, {
            method,
            credentials: "include",
            headers: { Accept: "application/json", "Content-Type": "application/json" },
            body: body === undefined ? undefined : JSON.stringify(body),
          });
          return { status: r.status, data: await r.json().catch(() => null) };
        },
        { method, url: `/api/${T}${path}`, body },
      );
    await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
    const today = new Date().toISOString().slice(0, 10);
    const made = await api("POST", "/billing/one-time", {
      account_id: process.env.ACCOUNT,
      kind: "fee",
      charge_code: process.env.CODE ?? "CONN",
      bill_date: today,
      due_days: 21,
    });
    check("one-time bill drafted", made.status === 201, `status ${made.status} ${JSON.stringify(made.data).slice(0, 300)}`);
    const five = Object.fromEntries(
      ["compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final"].map((k) => [k, true]),
    );
    const sent = await api("POST", `/billing/one-time/${made.data.run_id}/send`, {
      confirmations: five,
      delivery: "email",
      sent_at: new Date().toISOString(),
    });
    check("bill issued and sent by email", sent.status === 201, `status ${sent.status} ${JSON.stringify(sent.data).slice(0, 300)}`);
    console.log(`INVOICE ${made.data.invoice_id}`);
  } else {
    const LINK = process.env.LINK;
    const secret = new URL(LINK).hash.replace(/^#token=/, "");
    for (const [label, width] of [["1440", 1440], ["390", 390]]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, acceptDownloads: true });
      const page = await context.newPage();
      page.setDefaultTimeout(30000);
      const urls = [];
      page.on("request", (request) => urls.push(request.url()));
      await page.goto(LINK, { waitUntil: "domcontentloaded" });
      await page.locator("[data-screen=bill-link]").waitFor();
      check(`${label}: the bill opens with no sign-in`, true);
      check(`${label}: the secret is off the address bar`, !page.url().includes(secret), page.url());
      await page.screenshot({ path: `${OUT}/${label}-01-bill.png`, fullPage: true });
      const downloading = page.waitForEvent("download");
      await page.getByRole("button", { name: "Download bill" }).click();
      const download = await downloading;
      const saved = `${OUT}/${label}-bill.pdf`;
      await download.saveAs(saved);
      check(`${label}: Download saves the PDF`, download.suggestedFilename().endsWith(".pdf"), download.suggestedFilename());
      check(`${label}: no request URL carries the secret`, urls.every((u) => !u.includes(secret)), `${urls.length} requests`);
      console.log(`SAVED ${saved}`);
      await context.close();
    }
    const dead = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
    await dead.goto(`${BASE}/${T}/portal/bill#token=not-a-real-token`, { waitUntil: "domcontentloaded" });
    await dead.locator("[data-screen=agreement-expired]").waitFor();
    const text = await dead.locator("[data-screen=agreement-expired]").innerText();
    check("an unknown link shows the dead end with the phone", /expired/i.test(text) && /\d{3}/.test(text), text.replace(/\n/g, " | "));
    await dead.screenshot({ path: `${OUT}/1440-02-dead-end.png`, fullPage: true });
  }
} catch (error) {
  failures += 1;
  console.log(`FAIL  walk aborted: ${error}`);
} finally {
  await browser.close();
}
console.log(failures === 0 ? "WALK PASS" : `WALK FAIL (${failures})`);
process.exit(failures === 0 ? 0 : 1);
