// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-4954 — pressing Download saved `file.json` containing a 404
//          on every deployment with JOBS_EAGER=false (worker wrote the file to
//          its own disk; web looked in its own).
// Change:  Export files move to S3 — PO ruling 2026-10-02 (decision log,
//          "EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS
//          APPROVED"). Analysis: 09-infra/04-exports-to-s3.md.
// ───────────────────────────────────────────────────────
//
// THE RE-TAKE OF THE REPRODUCTION, IN A BROWSER, THE WAY A CLERK REACHES IT.
//
// The stack this expects (each its own process, as in production):
//   * web    — gunicorn, JOBS_EAGER=false, its OWN TMPDIR
//   * worker — celery -Q celery,billing, JOBS_EAGER=false, its OWN TMPDIR
//   * both   — DOCUMENT_STORAGE_BUCKET + DOCUMENT_STORAGE_ENDPOINT_URL pointing at
//              one S3 bucket (an S3 emulator such as `moto_server` is fine)
//   * the SPA — `PORT=8456 API_PROXY_TARGET=http://<web> node 07-frontend/server.mjs`
// No directory is shared between web and worker. Before the move this exact
// setup saved `file.json` with a 404 in it; now the file must arrive, named.
//
//   BASE=http://127.0.0.1:8456 OUT=/tmp/s3a node 10-scripts/s3a_def_met_4954_s3_export_walkthrough.mjs
import { mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8456";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/s3a-walk";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

let failures = 0;
function check(name, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${detail ? `\n          ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.on("pageerror", (e) => console.log("  page error:", e.message));
page.on("response", (r) => { if (process.env.TRACE_API || (r.url().includes("/api/") && r.status() >= 400)) console.log(`  api ${r.status()} ${r.url()}`); });
page.on("requestfailed", (r) => console.log(`  request failed ${r.url()} ${r.failure()?.errorText}`));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.getByLabel(/email/i).fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30_000 }).catch(async () => {
  await page.screenshot({ path: `${OUT}/0-signin-stuck.png` });
  throw new Error("sign-in did not leave the sign-in page");
});
await page.waitForLoadState("networkidle");

// Start where the clerk starts: the Premises list, its own Export control.
await page.goto(`${BASE}/${TENANT}/premises`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${OUT}/1-premises-list.png` });
await page.locator('[data-download="button"]').first().click();
const link = page.getByRole("link", { name: /download the csv/i });
await link.waitFor({ timeout: 60_000 });
await page.screenshot({ path: `${OUT}/2-export-ready.png` });
const href = await link.getAttribute("href");
check("the ready notice links the platform download route", /^\/api\/exports\/[0-9a-f-]+\/file$/.test(href ?? ""), href);

const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
const name = download.suggestedFilename();
const saved = `${OUT}/${name}`;
await download.saveAs(saved);
const body = readFileSync(saved, "utf-8");
check("the browser saved a CSV named by IS-11, not file.json", /^brazosbend_premises_.*\.csv$/.test(name), name);
check("the file is the export, not a 404 body", body.startsWith("premise_no,") && !body.includes("errors.not-found"), body.slice(0, 80));
console.log(`  saved ${saved} (${body.length} bytes) — url ${download.url().split("?")[0]}`);

await browser.close();
console.log(failures ? `${failures} FAILED` : "all checks passed");
process.exit(failures ? 1 : 0);
