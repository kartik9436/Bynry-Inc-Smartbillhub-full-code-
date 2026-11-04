// ── Trace ──────────────────────────────────────────────
// Change:  CR-199-BRC10 R2 (screens lane) — screenshot the redesigned
//          Templates list and workspace beside each drawing image in
//          05-prototype/templates-redesign-2026-10-29/images/.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app against the drawing)
// ───────────────────────────────────────────────────────
/**
 * Drives `07-frontend/templates-harness.html` (the real screen over a fixture
 * API — see its own docstring for what is ahead of the server) and saves one
 * PNG per drawing, named after it.
 *
 *     cd 07-frontend && npx vite --port 5191 --strictPort &
 *     OUT=/tmp/cr199 CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       node 10-scripts/cr199_templates_capture.mjs
 */
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://localhost:5191/templates-harness.html";
const OUT = process.env.OUT ?? "/tmp/cr199";
mkdirSync(OUT, { recursive: true });

const OPEN = "?template=email_bill_ready&variant=v-default";
const shots = [
  { name: "01-list", q: "" },
  { name: "02-workspace-email-view", q: OPEN },
  { name: "03-workspace-email-edit-placeholders", q: `${OPEN}&mode=edit`, click: ["insert-placeholder"] },
  { name: "05-workspace-text", q: "?template=sms_bill_ready&variant=v-default&mode=edit" },
  { name: "06-new-variant", q: `${OPEN}&dialog=new` },
  { name: "07-history", q: `${OPEN}&view=history`, click: ["preview-version-1"] },
  { name: "08-make-live-again", q: `${OPEN}&view=history`, click: ["make-live-1"] },
  { name: "10-duplicate-as-variant", q: `${OPEN}&dialog=duplicate` },
  { name: "11-publish-confirm", q: `${OPEN}&mode=edit&dialog=publish` },
  { name: "12-send-test", q: `${OPEN}&dialog=send-test` },
  { name: "13-legal-notice", q: "?template=disconnect_notice_10_day&variant=v-default" },
  { name: "15-legal-history", q: "?template=disconnect_notice_10_day&variant=v-default&view=history" },
  { name: "16-spanish", q: "?template=email_bill_ready&variant=v-es" },
  { name: "17-warnings", q: `${OPEN}&mode=edit`, extra: "&errors=1", type: "Hello {first_name}, pay at {pay_link} {bogus}" },
  { name: "18-start-from-english", q: OPEN, pickLanguage: "es", variantCustomers: "commercial" },
  { name: "19-list-dark", q: "", extra: "&dark=1" },
  { name: "20-workspace-dark", q: OPEN, extra: "&dark=1" },
  { name: "21-list-phone", q: "", width: 390 },
  { name: "22-workspace-phone", q: OPEN, width: 390 },
];

const browser = await chromium.launch({ executablePath: process.env.CHROME });
for (const shot of shots) {
  const page = await browser.newPage({
    viewport: { width: shot.width ?? 1440, height: 1000 },
    colorScheme: (shot.extra ?? "").includes("dark") ? "dark" : "light",
  });
  const url = `${BASE}?entry=${encodeURIComponent(shot.q)}${shot.extra ?? ""}`;
  await page.goto(url);
  await page.waitForTimeout(1600);
  for (const testId of shot.click ?? []) {
    await page.getByTestId(testId).first().click();
    await page.waitForTimeout(400);
  }
  if (shot.variantCustomers) {
    await page.locator("[data-testid=picker-customers] select").selectOption(shot.variantCustomers);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  }
  if (shot.pickLanguage) {
    await page.locator("[data-testid=picker-language] select").selectOption(shot.pickLanguage);
    await page.waitForTimeout(300);
  }
  if (shot.type) {
    await page.getByTestId("editor-body").fill(shot.type);
    await page.waitForTimeout(900);
  }
  await page.screenshot({ path: `${OUT}/${shot.name}.png`, fullPage: true });
  console.log(`saved ${OUT}/${shot.name}.png`);
  await page.close();
}
await browser.close();
