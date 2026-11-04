// ── Trace ──────────────────────────────────────────────
// Change:   CR-158-BRC10 — the clerk opens a customer's uploaded file. Its own
//           record (§4) left one thing NOT PROVED: "a PDF actually DRAWN by a
//           desktop browser's viewer under the policy (headless Chromium has no
//           PDF viewer) — a person opening one on screen is still owed".
//           This walk is that proof.
// Utility:  Six Rivers Utility (`sixrivers`), 10-scripts/cr158_seed_portal_upload.py.
// Run:      HEADED, because the PDF viewer only exists in a headed Chromium:
//           E2E_BASE_URL=http://127.0.0.1:<spa> E2E_TENANT=sixrivers \
//           E2E_EMAIL=priya@sixriversutility.com \
//           E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//           E2E_HEADED=1 xvfb-run -a npx playwright test e2e/CR-158-pdf-display-headed.spec.ts --headed
// ───────────────────────────────────────────────────────
//
// It is a sibling of CR-158-portal-application-documents.spec.ts and walks the
// same customer half; what it adds is the half that one could not do:
//   * a REAL three-page PDF with text on every page, opened from the Documents
//     tab, and the viewer's own page count and on-screen text read back;
//   * a PNG and a JPEG made by the browser itself, opened and measured as
//     decoded images (naturalWidth > 0), not merely as bytes;
//   * `as=download` asked for in the browser and seen to SAVE rather than draw.
// Without a viewer (headless) the spec SKIPS by name rather than passing.
import { mkdirSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

const SHOTS = "../08-qa/screens/pdf-display-2026-10-02";
const ADDRESS = "88 Riverbend Way";
const PDF_NAME = "sample-id.pdf";
const PNG_NAME = "sample-id-photo.png";
const JPG_NAME = "sample-id-scan.jpg";

/** A real PDF: three pages, Helvetica text on each, a correct xref table.
 *  Every character is ASCII (the em dash is the PDF escape `\227`), so a
 *  string's length IS its byte length and the xref offsets are exact. */
function threePagePdf(): Buffer {
  const pages = [1, 2, 3];
  const objects: string[] = [];
  objects[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objects[2] = `<< /Type /Pages /Kids [${pages.map((p) => `${2 + p * 2} 0 R`).join(" ")}] /Count ${pages.length} >>`;
  objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>";
  for (const p of pages) {
    // \227 is the em dash in WinAnsiEncoding.
    const text = `BT /F1 36 Tf 60 700 Td (SAMPLE ID \\227 page ${p}) Tj ET BT /F1 18 Tf 60 650 Td (Six Rivers Utility test upload) Tj ET`;
    objects[2 + p * 2] =
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${3 + p * 2} 0 R >>`;
    objects[3 + p * 2] = `<< /Length ${text.length} >>\nstream\n${text}\nendstream`;
  }
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (let i = 1; i < objects.length; i++) {
    offsets[i] = out.length;
    out += `${i} 0 obj\n${objects[i]}\nendobj\n`;
  }
  const xref = out.length;
  out += `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
  for (let i = 1; i < objects.length; i++) out += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

/** A picture the browser draws for us, so the PNG and JPEG are real images. */
async function picture(ctx: BrowserContext, label: string, type: "png" | "jpeg"): Promise<Buffer> {
  const p = await ctx.newPage();
  await p.setViewportSize({ width: 480, height: 300 });
  await p.setContent(
    `<body style="margin:0;background:#e8f0fe;font:bold 40px sans-serif;display:flex;align-items:center;justify-content:center;height:300px">${label}</body>`,
  );
  const bytes = await p.screenshot({ type, ...(type === "jpeg" ? { quality: 85 } : {}) });
  await p.close();
  return bytes;
}

function startDate(): string {
  const day = new Date(Date.now() + 21 * 24 * 3600 * 1000);
  while (day.getDay() === 0 || day.getDay() === 6) day.setDate(day.getDate() + 1);
  return day.toISOString().slice(0, 10);
}

async function shot(page: Page, name: string, fullPage = true): Promise<void> {
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage });
}

skipUnlessAppServer(test);

test("CR-158 — the clerk's PDF opens in the browser's viewer; PNG and JPEG draw as images", async ({
  browser,
  browserName,
}) => {
  test.skip(browserName !== "chromium", "the viewer checked here is Chromium's");
  test.skip(!process.env.E2E_HEADED, "set E2E_HEADED=1 and run --headed: headless Chromium has no PDF viewer");
  test.setTimeout(240_000);
  const T = tenant();
  const PDF = threePagePdf();

  // ═════ 1 · the customer applies and attaches three files ═════════════════
  const guest = await browser.newContext();
  const PNG = await picture(guest, "SAMPLE ID — PNG", "png");
  const JPG = await picture(guest, "SAMPLE ID — JPG", "jpeg");
  const page = await guest.newPage();
  await page.goto(`/${T}/portal/start-service`);
  await page.fill("#availability-address", ADDRESS);
  await page.click('[data-action="check"]');
  await page.waitForSelector("[data-minitable]", { timeout: 30_000 });
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 30_000 });
  await page.fill("#requested_start", startDate());
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(800);
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-step="about"]', { timeout: 30_000 });
  await page.fill("#first_name", "Amara");
  await page.fill("#last_name", "Okafor");
  await page.fill("#email", `amara.${Date.now()}@example.test`);
  await page.fill("#phone", "(281) 555-0144");
  await page.fill("#date_of_birth", "1990-05-14");
  await page.locator("#date_of_birth").blur();
  const input = page.locator('[data-application-documents] input[type="file"]');
  for (const [name, mimeType, buffer] of [
    [PDF_NAME, "application/pdf", PDF],
    [PNG_NAME, "image/png", PNG],
    [JPG_NAME, "image/jpeg", JPG],
  ] as const) {
    await input.setInputFiles({ name, mimeType, buffer });
    await expect(page.locator(`[data-attached-file="${name}"]`)).toBeVisible({ timeout: 30_000 });
  }
  await shot(page, "1-customer-three-files");
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-screen="CWP-009"]', { timeout: 30_000 });
  const submitted = page.waitForResponse(
    (r) => r.url().includes("/submit") && r.request().method() === "POST",
  );
  await page.click('[data-action="send"]');
  const answer = (await (await submitted).json()) as { reference: string; request_id: string };
  expect(answer.reference).toMatch(/^SR-/);
  await guest.close();

  // ═════ 2 · the clerk, on the request's Documents tab ═════════════════════
  const staff = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const clerk = await staff.newPage();
  await signIn(clerk);
  await clerk.goto(`/${T}/requests/${answer.request_id}?tab=documents`);
  const button = (name: string) => clerk.locator("[data-doc-open]", { hasText: name });
  await expect(button(PDF_NAME)).toBeVisible({ timeout: 30_000 });
  await shot(clerk, "2-clerk-documents-tab");

  // ── the PDF, in the viewer ────────────────────────────────────────────────
  const [viewer] = await Promise.all([staff.waitForEvent("page"), button(PDF_NAME).click()]);
  await viewer.waitForURL(/\/content\?as=view$/, { timeout: 30_000 });
  const pdfUrl = viewer.url();
  // Chromium hands a PDF navigation to its viewer: the tab's document becomes an
  // <embed type="application/pdf">, and the viewer itself lives in an extension
  // frame. Neither exists when the PDF is refused or downloaded instead.
  await expect(viewer.locator('embed[type="application/pdf"]')).toHaveCount(1, { timeout: 30_000 });
  // The viewer is Chromium's own extension page (chrome-extension://…), which
  // Playwright does not list among the tab's frames. Reach it as a CDP target
  // and read the toolbar's page count out of its shadow DOM.
  const cdp = await browser.newBrowserCDPSession();
  let pageCount = "";
  let viewerTarget = "";
  const expression = `(() => {
    const found = [];
    const walk = (root) => root.querySelectorAll("*").forEach((el) => {
      if (el.shadowRoot) walk(el.shadowRoot);
      if (/^page-?length$/i.test(el.id)) found.push(el.textContent);
    });
    walk(document);
    return found.join("|");
  })()`;
  for (let i = 0; i < 40 && !pageCount; i++) {
    await viewer.waitForTimeout(500);
    const { targetInfos } = (await cdp.send("Target.getTargets")) as {
      targetInfos: { targetId: string; url: string; type: string }[];
    };
    for (const t of targetInfos.filter((x) => x.url.startsWith("chrome-extension://"))) {
      viewerTarget = `${t.type} ${t.url}`;
      // Playwright's browser session cannot route a flattened child session, so
      // talk to the viewer through the non-flattened message relay.
      const { sessionId } = (await cdp.send("Target.attachToTarget", {
        targetId: t.targetId,
        flatten: false,
      })) as { sessionId: string };
      const reply = new Promise<string>((resolve) => {
        const onMessage = (event: { sessionId: string; message: string }) => {
          const msg = JSON.parse(event.message) as {
            id?: number;
            result?: { result?: { value?: string } };
            error?: { message: string };
          };
          if (event.sessionId !== sessionId || msg.id !== 1) return;
          cdp.off("Target.receivedMessageFromTarget" as never, onMessage as never);
          resolve(String(msg.result?.result?.value ?? msg.error?.message ?? ""));
        };
        cdp.on("Target.receivedMessageFromTarget" as never, onMessage as never);
        setTimeout(() => resolve("(no reply)"), 5000);
      });
      await cdp.send("Target.sendMessageToTarget", {
        sessionId,
        message: JSON.stringify({
          id: 1,
          method: "Runtime.evaluate",
          params: { expression, returnByValue: true },
        }),
      });
      const value = await reply;
      viewerTarget += ` → ${value}`;
      // The toolbar reads 0 until the document has loaded — a 0 is "not yet",
      // never an answer (a first draft stopped on it and reported a false red).
      const m = /([1-9]\d*)/.exec(value);
      if (m) pageCount = m[1];
      await cdp.send("Target.detachFromTarget", { sessionId }).catch(() => undefined);
    }
  }
  await viewer.waitForTimeout(1500);
  await shot(viewer, "3-pdf-in-chromium-viewer", false);
  console.log(`PDF viewer: url=${pdfUrl} pageCount=${pageCount || "(not readable)"}`);
  console.log(`PDF viewer target: ${viewerTarget}`);
  expect(pageCount, "the viewer's own page count").toBe("3");
  await viewer.close();

  // ── the headers that let it draw ──────────────────────────────────────────
  const view = await staff.request.get(pdfUrl);
  expect(view.status()).toBe(200);
  const h = view.headers();
  console.log(`view headers: ${JSON.stringify(h)}`);
  expect(h["content-type"]).toBe("application/pdf");
  expect(h["content-disposition"]).toMatch(/^inline;/);
  expect(h["x-content-type-options"]).toBe("nosniff");
  expect(h["content-security-policy"]).toContain("default-src 'none'");
  expect(h["content-security-policy"]).not.toMatch(/script-src/);
  expect(Array.from(await view.body())).toEqual(Array.from(PDF));

  // ── `as=download` saves rather than draws ─────────────────────────────────
  const downloadUrl = pdfUrl.replace(/as=view$/, "as=download");
  const dl = await staff.request.get(downloadUrl);
  expect(dl.headers()["content-disposition"]).toMatch(/^attachment;/);
  expect(dl.headers()["content-type"]).toBe("application/pdf");
  const tab = await staff.newPage();
  const [download] = await Promise.all([
    tab.waitForEvent("download", { timeout: 30_000 }),
    tab.goto(downloadUrl).catch(() => undefined), // a download aborts the navigation
  ]);
  expect(download.suggestedFilename()).toBe(PDF_NAME);
  await tab.close();

  // ── the PNG and the JPEG, drawn as images ─────────────────────────────────
  for (const [name, type, bytes, shotName] of [
    [PNG_NAME, "image/png", PNG, "4-png-opened"],
    [JPG_NAME, "image/jpeg", JPG, "5-jpg-opened"],
  ] as const) {
    const [opened] = await Promise.all([staff.waitForEvent("page"), button(name).click()]);
    await opened.waitForURL(/\/content\?as=view$/, { timeout: 30_000 });
    // Chromium wraps a top-level image in its own <img>; a decoded image has
    // a natural size, a refused or broken one has 0.
    const img = opened.locator("img");
    await expect(img).toHaveCount(1, { timeout: 30_000 });
    const size = await img.evaluate((el: HTMLImageElement) => [el.naturalWidth, el.naturalHeight]);
    expect(size).toEqual([480, 300]);
    await shot(opened, shotName, false);
    const r = await staff.request.get(opened.url());
    expect(r.headers()["content-type"]).toBe(type);
    expect(r.headers()["content-disposition"]).toMatch(/^inline;/);
    expect(Array.from(await r.body())).toEqual(Array.from(bytes));
    await opened.close();
  }
  await staff.close();
});
