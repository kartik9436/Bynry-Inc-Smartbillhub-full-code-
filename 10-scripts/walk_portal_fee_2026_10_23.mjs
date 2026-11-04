/**
 * walk_portal_fee_2026_10_23 — CR-191-BRC10, in Chromium at 1280 and 390 on a
 * PRIVATE copy of the dev database, against the SANDBOX card provider.
 *
 * A complete draft is saved through the portal's own draft endpoint, then the
 * browser opens its link, which lands on step 4 (Check and send). With
 * FEE=10 the step must show HOW YOU ARE PAYING, "Pay $10.00 and submit ✓"
 * held until the card is typed, the not-refunded consequence; paying must
 * reach the Sent panel saying "We received your $10.00 application fee." and
 * print `REFERENCE SR-…`. With FEE=0 there must be no card boxes, the button
 * must read "Send my application ✓", and "Nothing is charged today." stays.
 *
 *   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *      DATABASE_URL=postgres://…/<private copy> python manage.py runserver 127.0.0.1:8791 --noreload)
 *   (cd 07-frontend && npx vite build && PORT=8792 API_PROXY_TARGET=http://127.0.0.1:8791 node server.mjs)
 *   FEE=10 node 10-scripts/walk_portal_fee_2026_10_23.mjs
 *   FEE=0  node 10-scripts/walk_portal_fee_2026_10_23.mjs
 */
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8792";
const T = process.env.TENANT ?? "brazosbend";
const FEE = process.env.FEE ?? "10";
const OUT = process.env.OUT ?? "/tmp/claude-0/shots-portal-fee";
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

const start = new Date(Date.now() + 21 * 86400000).toISOString().slice(0, 10);
async function seedDraft(token) {
  const r = await fetch(`${BASE}/api/${T}/portal/public/applications/${token}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      address_as_given: "4107 Walk Fee Ln",
      address_city_as_given: "Richmond",
      address_postal_code_as_given: "77469",
      service_codes: ["water"],
      applicant_kind: "person",
      first_name: "Daniel",
      last_name: "Okafor",
      email: "d.okafor@example.test",
      phone: "(512) 555-7730",
      account_type_code: "residential",
      requested_start: start,
      mailing_same_as_service: true,
      // Brazos Bend asks one required question of its own on the portal.
      custom_data: { premises: { roof_material: "Metal" } },
    }),
  });
  return r.status;
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
try {
  for (const width of [1280, 390]) {
    const token = randomUUID();
    check(`${width} · draft saved`, (await seedDraft(token)) === 200);
    const page = await (
      await browser.newContext({ viewport: { width, height: 1400 } })
    ).newPage();
    page.setDefaultTimeout(30000);
    await page.goto(`${BASE}/${T}/portal/start-service/${token}`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-screen="CWP-009"][data-step="review"]').catch(async (e) => { await page.screenshot({ path: `${OUT}/stuck-${width}.png`, fullPage: true }); console.log((await page.locator("body").innerText()).slice(0, 1500)); throw e; });
    const send = page.locator('[data-action="send"]');
    const body = () => page.locator('[data-screen="CWP-009"]').innerText();
    const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
    check(`${width} · no sideways scroll`, scrollW <= width, `scrollWidth=${scrollW}`);
    if (FEE !== "0") {
      check(`${width} · HOW YOU ARE PAYING shown`, (await page.locator("[data-fee-card]").count()) === 1);
      check(`${width} · button reads Pay $10.00 and submit ✓`, (await send.innerText()).trim() === "Pay $10.00 and submit ✓", await send.innerText());
      check(`${width} · held until the card is typed`, await send.isDisabled());
      const text = await body();
      check(`${width} · consequence states the charge`, text.includes("Your card is charged $10.00 now."));
      check(`${width} · consequence says not refunded`, text.includes("The fee is not refunded."));
      check(`${width} · no "Nothing is charged" on a fee`, !text.includes("Nothing is charged today."));
      await page.screenshot({ path: `${OUT}/fee-${width}-before.png`, fullPage: true });
      // Keyboard only: the three boxes are reached and typed by label.
      await page.getByLabel("Card number").fill("4242 4242 4242 4242");
      await page.getByLabel("Expires").fill("11/27");
      await page.getByLabel("Security code").fill("123");
      check(`${width} · released once the card is typed`, !(await send.isDisabled()));
      await send.focus();
      await page.keyboard.press("Enter");
      await page.waitForSelector('[data-sent="true"]');
      const sent = await page.locator('[data-sent="true"]').innerText();
      check(`${width} · Sent says the fee received`, sent.includes("We received your $10.00 application fee."));
      check(`${width} · Sent does not say nothing is charged`, !sent.includes("Nothing is charged"));
      const reference = await page.locator("[data-reference]").innerText();
      check(`${width} · a reference`, /^SR-/.test(reference), reference);
      console.log(`REFERENCE ${reference}`);
      await page.screenshot({ path: `${OUT}/fee-${width}-sent.png`, fullPage: true });
    } else {
      check(`${width} · no card boxes on a $0 fee`, (await page.locator("[data-fee-card]").count()) === 0);
      check(`${width} · button reads Send my application ✓`, (await send.innerText()).trim() === "Send my application ✓", await send.innerText());
      check(`${width} · Nothing is charged today. stays`, (await body()).includes("Nothing is charged today."));
      await page.screenshot({ path: `${OUT}/zero-${width}-before.png`, fullPage: true });
      await send.click();
      await page.waitForSelector('[data-sent="true"]');
      const sent = await page.locator('[data-sent="true"]').innerText();
      check(`${width} · Sent keeps Nothing is charged today.`, sent.includes("Nothing is charged today."));
      const reference = await page.locator("[data-reference]").innerText();
      console.log(`REFERENCE ${reference}`);
      await page.screenshot({ path: `${OUT}/zero-${width}-sent.png`, fullPage: true });
    }
  }
} finally {
  await browser.close();
}
console.log(failures === 0 ? "WALK PASS" : `WALK FAIL (${failures})`);
process.exit(failures === 0 ? 0 : 1);
