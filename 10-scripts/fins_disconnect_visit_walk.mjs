// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9696 (CR-168-BRC10, lane FIN-S) — the disconnect case page
//           lists the cut visit the wizard raised, by its WO- number, linked.
// Usage:    BASE=http://127.0.0.1:5229 CASE=dsc-26-0001 ORDER=WO-0041 \
//             node 10-scripts/fins_disconnect_visit_walk.mjs
// ───────────────────────────────────────────────────────
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5229";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const CASE = process.env.CASE ?? "dsc-26-0001";
const ORDER = process.env.ORDER ?? "WO-0041";
const SHOTS = process.env.SHOTS ?? "08-qa/work-2026-10-04/final";

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

const failures = [];
function check(label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(label);
}

mkdirSync(SHOTS, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
page.setDefaultTimeout(45000);
try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"));

  await page.goto(`${BASE}/${TENANT}/disconnects/${CASE}`, { waitUntil: "domcontentloaded" });
  const link = page.locator(`[data-case-visit-order="${ORDER}"]`);
  await link.waitFor();
  const row = await page.locator("[data-case-visits]").innerText();
  check("the case lists its cut visit with counts", /1 raised · 0 done · 0 accepted/.test(row), row);
  check("the job is named by its number", (await link.innerText()) === ORDER);
  await page.locator('[data-testid="disconnect-record-case"]').scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "fins-01-disconnect-case-lists-its-visit.png") });

  await link.click();
  await page.waitForURL((u) => u.pathname.endsWith(`/work/orders/${ORDER}`));
  await page.getByText(ORDER).first().waitFor();
  check("the link opens the job", page.url().endsWith(`/work/orders/${ORDER}`), page.url());
  await page.screenshot({ path: join(SHOTS, "fins-02-the-link-opens-the-job.png") });
} finally {
  await browser.close();
}
console.log(failures.length ? `\n  ${failures.length} FAIL` : "\n  all PASS");
process.exit(failures.length ? 1 : 0);
