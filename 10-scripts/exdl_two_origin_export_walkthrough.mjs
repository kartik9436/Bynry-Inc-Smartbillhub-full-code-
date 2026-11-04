// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-TEN-9189 (fixed 2.459.1) — Download saved `file.htm` when the app and the API
//          are on different hosts (CR-144: static app host + API host).
//          DEF-TEN-9190 — an export that cannot be stored must SAY so.
// ───────────────────────────────────────────────────────
//
// THE REPRODUCTION, IN A BROWSER, ON TWO ORIGINS — the way the developer's
// host is laid out (app-dev.bynry.com + api-smart360-dev.bynry.com).
//
// The stack this expects, each its own process:
//   * APP — the built bundle (`vite build --mode wolocal` with
//           VITE_API_BASE_URL=<API>) behind a STATIC host that answers every
//           unknown path with index.html, as a CDN does;
//   * API — gunicorn on production settings, JOBS_EAGER=false, with
//           CORS_ALLOWED_ORIGINS=<APP>;
//   * a celery worker, and an S3 bucket (an emulator such as moto is fine).
//
//   APP=http://app.exdl.localhost:56484 OUT=/tmp/x MODE=download node 10-scripts/exdl_two_origin_export_walkthrough.mjs
//
// MODE=download  export Premises, press Download, report what the browser SAVED.
//                Before 2.459.1 this saved `file.html` (the app's index.html);
//                from 2.459.1 it saves the CSV under its own name.
// MODE=failed    export Premises against a worker that cannot store (2.459.2),
//                and expect the failure on screen and NO Download link
import { mkdirSync, readFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const APP = process.env.APP ?? "http://app.exdl.localhost:56484";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/exdl-walk";
const MODE = process.env.MODE ?? "download";
const SHOT = process.env.SHOT ?? "exdl";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set CHROME");
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
page.on("response", (r) => {
  if (r.url().includes("/exports/") || r.url().includes("X-Amz")) console.log(`  ${r.status()} ${r.url().slice(0, 140)}`);
});

await page.goto(`${APP}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.getByLabel(/email/i).fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30_000 });
await page.waitForLoadState("networkidle");

await page.goto(`${APP}/${TENANT}/premises`, { waitUntil: "networkidle" });
await page.locator('[data-download="button"]').first().click();

if (MODE === "failed") {
  const alert = page.locator('[data-resource="premises"] [role="alert"]');
  await alert.waitFor({ timeout: 360_000 });
  const text = (await alert.textContent()) ?? "";
  await alert.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/${SHOT}.png` });
  check("the failure is on screen", /didn.t finish/i.test(text), text);
  check("no Download link is offered", (await page.getByRole("link", { name: /download the csv/i }).count()) === 0);
} else {
  const link = page.getByRole("link", { name: /download the csv/i });
  await link.waitFor({ timeout: 120_000 });
  const href = (await link.getAttribute("href")) ?? "";
  console.log(`  the Download link's href: ${href}`);
  check("the href is on the API's origin, not the app's", !href.startsWith("/") && !href.startsWith(APP), href);
  {
    const [download] = await Promise.all([page.waitForEvent("download", { timeout: 30_000 }), link.click()]);
    const name = download.suggestedFilename();
    const target = join(OUT, name);
    await download.saveAs(target);
    const size = statSync(target).size;
    const head = readFileSync(target, "utf8").slice(0, 160).replace(/\s+/g, " ");
    console.log(`  saved ${name} (${size} bytes): ${head}`);
    await page.screenshot({ path: `${OUT}/${SHOT}.png` });
    check("the browser saved the CSV, named", name.endsWith(".csv") && name.includes("premises"), name);
    check("its first line is the CSV header, not a web page", !/<!doctype|<html/i.test(head), head);
    check("the page did not navigate away", page.url().includes("/premises"), page.url());
  }
}

await browser.close();
console.log(failures === 0 ? "ALL PASS" : `${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
