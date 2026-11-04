// ── Trace ──────────────────────────────────────────────
// Change:   CR-158-BRC10 — a customer attaches documents to a portal
//           new-service application; the clerk opens them on the request.
//           PO 2026-10-01: "you need to allow customer to upload documents and
//           save those document to server for that Utility - and then clark
//           should able to view those document in new request".
// Utility:  PO 2026-10-01: "When you take utilty take it for 6 utility services
//           water, trash, sewer, fire, solar and battery - self service
//           portal" — Six Rivers Utility (`sixrivers`), seeded by
//           10-scripts/cr158_seed_portal_upload.py.
// Run:      E2E_BASE_URL=http://127.0.0.1:<vite> E2E_TENANT=sixrivers \
//           E2E_EMAIL=priya@sixriversutility.com npx playwright test \
//           e2e/CR-158-portal-application-documents.spec.ts
// ───────────────────────────────────────────────────────
//
// ONE WALK, THREE ACTORS' WORTH OF PROOF:
//   1. a stranger applies at 88 Riverbend Way (all six services, water and solar
//      among them), attaches TWO files on step 3, sees both restated on step 4,
//      and sends;
//   2. the clerk opens the request and opens BOTH files — the bytes that come
//      back are the bytes the stranger chose, with the safety headers;
//   3. nothing about the files is visible as a database id (B14 rule 31).
import { mkdirSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

const SHOTS = "../08-qa/screens/cr158-portal-upload-2026-10-01";
const ADDRESS = "88 Riverbend Way";

const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n",
);
// A one-pixel PNG — a real image, so a browser can draw it.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

function startDate(): string {
  const day = new Date(Date.now() + 21 * 24 * 3600 * 1000);
  while (day.getDay() === 0 || day.getDay() === 6) day.setDate(day.getDate() + 1);
  return day.toISOString().slice(0, 10);
}

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

skipUnlessAppServer(test);

test("CR-158 — a customer attaches two files, sends, and the clerk opens both", async ({
  browser,
}) => {
  const T = tenant();

  // ═════ 1 · the customer, on the portal, signed in as nobody ══════════════
  const guest = await browser.newContext();
  const page = await guest.newPage();
  await page.goto(`/${T}/portal/start-service`);
  await page.fill("#availability-address", ADDRESS);
  await page.click('[data-action="check"]');
  await page.waitForSelector("[data-minitable]", { timeout: 30_000 });
  // The six services are the utility's own; water and solar are available here.
  await expect(page.locator('[data-row="water"]')).toBeVisible();
  await expect(page.locator('[data-row="solar"]')).toBeVisible();
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 30_000 });
  await page.fill("#requested_start", startDate());
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(800);
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-step="about"]', { timeout: 30_000 });

  // The DF-4 hold has expired: the drop zone is real, its limits stated first.
  await expect(page.locator('[data-photo-picker="held"]')).toHaveCount(0);
  await expect(page.getByText("PDF, JPG or PNG. Up to 10 MB each. 5 files at most.")).toBeVisible();

  await page.fill("#first_name", "Amara");
  await page.fill("#last_name", "Okafor");
  await page.fill("#email", "amara.okafor@example.test");
  await page.fill("#phone", "(281) 555-0144");
  await page.fill("#date_of_birth", "1990-05-14");
  await page.locator("#date_of_birth").blur();

  const input = page.locator('[data-application-documents] input[type="file"]');
  await input.setInputFiles({ name: "tenancy-agreement.pdf", mimeType: "application/pdf", buffer: PDF });
  await expect(page.locator('[data-attached-file="tenancy-agreement.pdf"]')).toBeVisible({
    timeout: 30_000,
  });
  await input.setInputFiles({ name: "photo-id.png", mimeType: "image/png", buffer: PNG });
  await expect(page.locator('[data-attached-file="photo-id.png"]')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('[data-attached-file="tenancy-agreement.pdf"]')).toContainText("PDF");
  await expect(page.locator('[data-attached-file="photo-id.png"]')).toContainText("PNG");
  await shot(page, "1-about-you-two-files");

  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-screen="CWP-009"]', { timeout: 30_000 });
  await expect(page.locator('[data-attached-file="tenancy-agreement.pdf"]')).toBeVisible();
  await expect(page.locator('[data-attached-file="photo-id.png"]')).toBeVisible();
  await shot(page, "2-check-and-send");

  const submitted = page.waitForResponse(
    (response) => response.url().includes("/submit") && response.request().method() === "POST",
  );
  await page.click('[data-action="send"]');
  const answer = (await (await submitted).json()) as { reference: string; request_id: string };
  expect(answer.reference).toMatch(/^SR-/);
  await page.waitForSelector("[data-reference]", { timeout: 30_000 });
  await shot(page, "3-sent");
  await guest.close();

  // ═════ 2 · the clerk, signed in, on the request ══════════════════════════
  const staff = await browser.newContext();
  const clerk = await staff.newPage();
  await signIn(clerk);
  await clerk.goto(`/${T}/requests/${answer.request_id}?tab=documents`);
  const pdfButton = clerk.locator('[data-doc-open]', { hasText: "tenancy-agreement.pdf" });
  const pngButton = clerk.locator('[data-doc-open]', { hasText: "photo-id.png" });
  await expect(pdfButton).toBeVisible({ timeout: 30_000 });
  await expect(pngButton).toBeVisible();
  // Name · TYPE · size · date — and no database id on the screen.
  const tabText = await clerk.locator("main").innerText();
  expect(tabText).toContain("PDF");
  expect(tabText).toContain("PNG");
  expect(tabText).not.toContain(answer.request_id);
  await shot(clerk, "4-clerk-documents-tab");

  for (const [button, bytes, type] of [
    [pdfButton, PDF, "application/pdf"],
    [pngButton, PNG, "image/png"],
  ] as const) {
    // `noopener` tabs are announced on the CONTEXT, not as the opener's popup.
    const [opened] = await Promise.all([staff.waitForEvent("page"), button.click()]);
    await opened.waitForURL(/\/content\?as=view$/, { timeout: 30_000 }).catch(() => undefined);
    const url = opened.url();
    expect(url).toMatch(/\/service-requests\/[^/]+\/documents\/[^/]+\/content\?as=view$/);
    await opened.close().catch(() => undefined);
    // Fetch the same address with the clerk's own session — this is what the
    // tab displayed, and it proves the bytes and the headers.
    const response = await staff.request.get(url);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toBe(type);
    expect(response.headers()["content-disposition"]).toMatch(/^inline;/);
    expect(response.headers()["x-content-type-options"]).toBe("nosniff");
    expect(response.headers()["content-security-policy"]).toContain("default-src 'none'");
    expect(Array.from(await response.body())).toEqual(Array.from(bytes));
  }
  await staff.close();
});
