/**
 * walk_corrected_bill_channels_2026_10_22 — DEF-BIL-10535 / DEF-BIL-4454, in
 * Chromium at 1440 on a PRIVATE copy of the dev database.
 *
 * An account like Daniel Thomas's (paperless off, an email on file, its last
 * bill queued by post only): Ben Bennett, AC-2026-00002, BL-2610-000109.
 * The case is opened through the screen's own routes (preview → send), then
 * the APPROVAL STEP is driven in the browser: it must offer Send by: Email ·
 * Paper · Both, start on Paper, and the approver picks Both. The rows are then
 * read back from the database by the caller (`CHECK_SQL`).
 *
 *   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *      DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<private copy> \
 *      python manage.py migrate && python manage.py runserver 127.0.0.1:8571 --noreload)
 *   (cd 07-frontend && npx vite build && PORT=8572 API_PROXY_TARGET=http://127.0.0.1:8571 node server.mjs)
 *   BASE=http://127.0.0.1:8572 INVOICE=<uuid> ACCOUNT=<uuid> node 10-scripts/walk_corrected_bill_channels_2026_10_22.mjs
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8572";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const INVOICE = process.env.INVOICE;
const ACCOUNT = process.env.ACCOUNT;
const OUT = process.env.OUT ?? "/tmp/claude-0/shots-corrected-bill";
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

try {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  let caseId = process.env.CASE;
  if (!caseId) {
  const scope = { kind: "account", account_id: ACCOUNT, invoice_ids: [INVOICE] };
  const q = new URLSearchParams({ scope_kind: "account", account_id: ACCOUNT, invoice_ids: INVOICE });
  const options = await api("GET", `/corrections/options?${q}`);
  const meter = options.data?.meters?.[0];
  check("the bill's meter is offered", options.status === 200 && meter !== undefined, JSON.stringify(meter ?? options.data).slice(0, 160));
  const current = Number(meter.billed_reading);
  const value = String(current - 2);
  const items = [{ reason: "wrong_read", item: meter.asset_id, value, bill_ids: null }];
  const asOf = new Date().toISOString().slice(0, 10);
  const preview = await api("POST", "/corrections/preview", { scope, items, as_of: asOf });
  check("preview priced", preview.status === 200, `status ${preview.status} ${JSON.stringify(preview.data).slice(0, 200)}`);
  const sent = await api("POST", "/corrections", { scope, items, as_of: asOf, preview_hash: preview.data.preview_hash });
  check("case sent for approval", sent.status === 201 || sent.status === 200, `status ${sent.status}`);
  caseId = sent.data.id;
  }
  const opened = await api("GET", `/corrections/${caseId}`);
  check("the case serves the delivery offer", opened.data.delivery?.preselected === "paper" && opened.data.delivery?.email_on_file === true, JSON.stringify(opened.data.delivery));

  await page.goto(`${BASE}/${T}/billing/fix?case=${caseId}`, { waitUntil: "domcontentloaded" });
  const group = page.getByRole("radiogroup", { name: "Send by" });
  await group.waitFor();
  await page.screenshot({ path: `${OUT}/1440-01-approval-step.png`, fullPage: true });
  const paper = group.getByRole("radio", { name: "Paper" });
  check("starts on Paper (the original went by post)", (await paper.getAttribute("aria-checked")) === "true");
  const both = group.getByRole("radio", { name: "Both" });
  check("Both is offered (an email is on file)", !(await both.isDisabled()));
  await both.click();
  check("Both is chosen", (await both.getAttribute("aria-checked")) === "true");
  await page.screenshot({ path: `${OUT}/1440-02-both-chosen.png`, fullPage: true });
  await page.getByRole("button", { name: "Approve and issue", exact: true }).click();
  await page.locator("[data-fix-send=done]").waitFor({ timeout: 60000 });
  await page.screenshot({ path: `${OUT}/1440-03-done.png`, fullPage: true });
  check("the correction is done", true);
  console.log(`CASE ${caseId}`);
} catch (error) {
  failures += 1;
  console.log(`FAIL  walk aborted: ${error}`);
  await page.screenshot({ path: `${OUT}/1440-error.png`, fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
console.log(failures === 0 ? "WALK PASS" : `WALK FAIL (${failures})`);
process.exit(failures === 0 ? 0 : 1);
