// ── Trace ──────────────────────────────────────────────
// Lane:    LOGO (2026-10-05) — the utility logo moves from a database column
//          to the S3 document store and is drawn everywhere it is drawn.
// Rulings: decision log 2026-10-05, "THE UTILITY LOGO MOVES FROM A DATABASE
//          COLUMN TO THE S3 DOCUMENT STORE…" and "THE LOGO-TO-S3 PLAN IS
//          APPROVED AS WRITTEN…".
// ───────────────────────────────────────────────────────
//
// ONE WALK, RUN BEFORE AND AFTER THE FIX, THE WAY A SYSTEM ADMIN REACHES IT.
//
// It uploads one logo on Settings › Company › Brand and then looks at the five
// places the logo is drawn, recording for each what is actually on screen —
// the logo, the generated two-letter mark, a broken image, or nothing — and
// every logo request the browser made (status, content type, cache headers).
//
// The stack it expects (as the deployed hosts are: the SPA and the API on two
// ORIGINS, and the document store a real S3 API):
//   * API   — gunicorn on 127.0.0.1:8103, CORS/origin guard allowing the SPA
//   * S3    — an S3 emulator (moto) the API's DOCUMENT_STORAGE_ENDPOINT_URL names
//   * SPA   — `vite build --mode dev` with VITE_API_BASE_URL=http://127.0.0.1:8103,
//             served by `server.mjs` with API_PROXY_TARGET="" (no /api on the
//             SPA's own host, exactly like app-dev.bynry.com)
//
//   LOGO=/path/logo.png LABEL=before-png OUT=08-qa/logo-2026-10-05 \
//     node 10-scripts/logo_s3_walkthrough.mjs
//
// LOGO may be omitted to walk the surfaces without uploading (e.g. after a
// migration, to show an existing logo survived).
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5235";
const API = process.env.API ?? "http://127.0.0.1:8103";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/logo-2026-10-05";
const LABEL = process.env.LABEL ?? "walk";
const LOGO = process.env.LOGO ?? "";
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

const findings = [];
function note(surface, shows, detail = "") {
  findings.push({ surface, shows, detail });
  console.log(`  ${surface.padEnd(28)} ${shows}${detail ? `  — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const logoRequests = [];
page.on("response", async (r) => {
  const url = r.url();
  if (/logo/i.test(url)) {
    const h = r.headers();
    logoRequests.push({
      url,
      status: r.status(),
      type: h["content-type"] ?? "",
      etag: h["etag"] ?? "",
      cache: h["cache-control"] ?? "",
    });
  } else if (url.includes("/api/") && r.status() >= 400) {
    console.log(`  api ${r.status()} ${url}`);
  }
});
page.on("pageerror", (e) => console.log("  page error:", e.message));

/** What an element that stands where the logo stands is actually showing. */
async function markState(locator) {
  if ((await locator.count()) === 0) return { shows: "nothing", src: "" };
  const el = locator.first();
  return el.evaluate((node) => {
    if (node.tagName === "IMG") {
      const img = node;
      const ok = img.complete && img.naturalWidth > 0;
      return { shows: ok ? `the logo (${img.naturalWidth}x${img.naturalHeight})` : "a BROKEN image", src: img.getAttribute("src") ?? "" };
    }
    return { shows: `the two-letter mark "${(node.textContent ?? "").trim()}"`, src: "" };
  });
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.getByLabel(/email/i).fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30_000 });
await page.waitForLoadState("networkidle");

// ── 0 · Settings › Company › Brand — the upload ─────────────────────────────
await page.goto(`${BASE}/${TENANT}/settings/company/profile`, { waitUntil: "networkidle" });
if (LOGO !== "") {
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/settings/company/logo") && r.request().method() === "POST"),
    page.locator("#company-logo").setInputFiles(LOGO),
  ]);
  let body = "";
  try { body = JSON.stringify(await resp.json()); } catch { body = "(no json)"; }
  note("upload POST", `HTTP ${resp.status()}`, body.slice(0, 220));
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
}
const letterhead = page.locator(".settings-letterhead").first();
await letterhead.scrollIntoViewIfNeeded().catch(() => {});
const brand = await markState(page.locator(".settings-letterhead img, .settings-letterhead [role=img]"));
note("Settings › Company › Brand", brand.shows, brand.src);
await page.screenshot({ path: `${OUT}/${LABEL}-1-company-brand.png` });

// ── 1 · the app header (the sidebar's tenant mark) ─────────────────────────
const header = await markState(page.locator(".tenant img, .tenant [role=img]"));
note("App header", header.shows, header.src);
await page.locator(".tenant").first().screenshot({ path: `${OUT}/${LABEL}-2-app-header.png` }).catch(async () => {
  await page.screenshot({ path: `${OUT}/${LABEL}-2-app-header.png`, clip: { x: 0, y: 0, width: 400, height: 160 } });
});

// ── 2 · Settings › Billing › Bill layout (the chooser and its preview) ──────
await page.goto(`${BASE}/${TENANT}/settings/reference-data/templates`, { waitUntil: "networkidle" });
const billOpen = page.locator('[data-testid^="template-open-bill:"]').first();
let previewSrc = "";
if ((await billOpen.count()) > 0) {
  await billOpen.click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  previewSrc = (await page.locator('[data-bil="layout-preview"]').first().getAttribute("src").catch(() => "")) ?? "";
  const layoutMark = await markState(page.locator('[data-bil="layout-logo"] img, [data-bil="layout-logo"] [role=img]'));
  note("Bill layout (screen)", layoutMark.shows === "nothing" ? "no logo drawn on the chooser" : layoutMark.shows, previewSrc.split("#")[0]);
} else {
  note("Bill layout (screen)", "no bill row to open");
}
await page.screenshot({ path: `${OUT}/${LABEL}-3-bill-layout.png` });

// ── 3 · Settings › Customer portal › Branding ──────────────────────────────
await page.goto(`${BASE}/${TENANT}/settings/reference-data/customer-portal/branding`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const portalSettings = await markState(page.locator('[data-screen="CWP-070"] img, [data-portal-logo] img, [data-portal-logo] [role=img]'));
const portalSettingsText = (await page.locator('[data-screen="CWP-070"]').first().innerText().catch(() => "")).replace(/\s+/g, " ");
const logoLine = /logo[^.]{0,60}/i.exec(portalSettingsText)?.[0] ?? "";
note("Customer portal settings", portalSettings.shows === "nothing" ? `no image — text only: "${logoLine}"` : portalSettings.shows, portalSettings.src);
await page.screenshot({ path: `${OUT}/${LABEL}-4-portal-settings.png` });

// ── 4 · the customer portal itself (a guest's first page) ──────────────────
const guest = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const guestPage = await guest.newPage();
guestPage.on("response", (r) => {
  if (/logo/i.test(r.url())) {
    const h = r.headers();
    logoRequests.push({ url: r.url(), status: r.status(), type: h["content-type"] ?? "", etag: h["etag"] ?? "", cache: h["cache-control"] ?? "" });
  }
});
await guestPage.goto(`${BASE}/${TENANT}/portal`, { waitUntil: "networkidle" });
await guestPage.waitForTimeout(1000);
const portal = await markState(guestPage.locator("[data-portal-brand] img, [data-portal-brand] [role=img]"));
note("Customer portal", portal.shows === "nothing" ? "no logo and no mark drawn" : portal.shows, portal.src);
await guestPage.screenshot({ path: `${OUT}/${LABEL}-5-portal.png` });
await guest.close();

// ── 5 · a generated document — the bill layout's PDF ───────────────────────
if (previewSrc !== "") {
  const url = previewSrc.split("#")[0];
  const pdf = await page.request.get(url);
  const bytes = await pdf.body();
  const pdfPath = `${OUT}/${LABEL}-6-bill-preview.pdf`;
  writeFileSync(pdfPath, bytes);
  const text = bytes.toString("latin1");
  const images = (text.match(/\/Subtype\s*\/Image/g) ?? []).length;
  note("Generated bill (PDF)", images > 0 ? `${images} embedded image(s)` : "NO image in the PDF", `HTTP ${pdf.status()} ${bytes.length} bytes`);
  try {
    execFileSync("pdftoppm", ["-png", "-r", "60", "-f", "1", "-l", "1", "-singlefile", pdfPath, `${OUT}/${LABEL}-6-bill-preview`]);
  } catch (e) {
    console.log("  pdftoppm failed:", e.message);
  }
}

// ── 6 · an ISSUED bill — the document a customer actually receives ─────────
// ACCOUNT_ID set → issue one fee bill on that account through the real
// one-time door (create, then send with all five confirmations), and fetch
// the issued bill's own PDF. That bill is STAMPED with the logo on file now.
const ACCOUNT_ID = process.env.ACCOUNT_ID ?? "";
if (ACCOUNT_ID !== "") {
  const today = new Date().toISOString().slice(0, 10);
  const made = await page.request.post(`${API}/api/${TENANT}/billing/one-time`, {
    data: { account_id: ACCOUNT_ID, kind: "fee", charge_code: "RECON", bill_date: today, due_days: 21 },
  });
  const draft = await made.json().catch(() => ({}));
  if (made.status() !== 201) {
    note("Issued bill (PDF)", `could not draft a fee bill: HTTP ${made.status()}`, JSON.stringify(draft).slice(0, 200));
  } else {
    const five = { compliance: true, email_mandate: true, sms_mandate: true, autopay_mandate: true, final: true };
    const sent = await page.request.post(`${API}/api/${TENANT}/billing/one-time/${draft.run_id}/send`, {
      data: { confirmations: five, delivery: "email", sent_at: new Date().toISOString() },
    });
    const pdf = await page.request.get(`${API}/api/${TENANT}/invoices/${draft.invoice_id}/document.pdf`);
    const bytes = await pdf.body();
    const pdfPath = `${OUT}/${LABEL}-7-issued-bill.pdf`;
    writeFileSync(pdfPath, bytes);
    const images = (bytes.toString("latin1").match(/\/Subtype\s*\/Image/g) ?? []).length;
    note("Issued bill (PDF)", images > 0 ? `${images} embedded image(s)` : "NO image in the PDF", `send HTTP ${sent.status()} · pdf HTTP ${pdf.status()} ${bytes.length} bytes`);
    try {
      execFileSync("pdftoppm", ["-png", "-r", "60", "-f", "1", "-l", "1", "-singlefile", pdfPath, `${OUT}/${LABEL}-7-issued-bill`]);
    } catch (e) {
      console.log("  pdftoppm failed:", e.message);
    }
  }
}

console.log("\n  logo requests the browser made:");
for (const r of logoRequests) {
  console.log(`    ${r.status} ${r.type || "-"} etag=${r.etag || "-"} cache=${r.cache || "-"}\n      ${r.url}`);
}
writeFileSync(`${OUT}/${LABEL}-findings.json`, JSON.stringify({ base: BASE, api: API, findings, logoRequests }, null, 2));
await browser.close();
