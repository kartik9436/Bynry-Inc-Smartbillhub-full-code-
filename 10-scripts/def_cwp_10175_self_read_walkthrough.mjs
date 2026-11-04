// DEF-CWP-10175 · US-CWP-042 — a customer sends their own meter reading, in a
// real browser, end to end: staff switch self-read ON in Settings → the
// customer signs in to the portal → Readings → Send a reading (CWP-035) →
// a normal reading is "Received" → staff read log shows Source "Customer" →
// a very high reading is "Received – we will check it" and staff see the flag
// → staff switch self-read OFF → the portal's action is gone and the address
// refuses.
//
// Serve a LOCAL bundle against a LOCAL API on a PRIVATE copy of the database
// (README in 05-prototype/walk-portal-self-read-2026-10-17/), then:
//
//   BASE=http://127.0.0.1:8105 node 10-scripts/def_cwp_10175_self_read_walkthrough.mjs
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8105";
const T = process.env.TENANT ?? "brazosbend";
const STAFF = process.env.STAFF ?? "dana@brazosbendutilities.com";
const STAFF_PASSWORD = process.env.STAFF_PASSWORD ?? "S3cure!passw0rd";
const PORTAL_LOGIN = process.env.PORTAL_LOGIN ?? "alvarez0@example.invalid";
const PORTAL_PASSWORD = process.env.PORTAL_PASSWORD ?? "Sample-Portal-2026!";
const OUT =
  process.env.OUT ??
  new URL("../05-prototype/walk-portal-self-read-2026-10-17/", import.meta.url).pathname;
const NORMAL = { meter: "W-5000", value: "1027" };
const HIGH = { meter: "E-5000", value: "23400" };
mkdirSync(OUT, { recursive: true });

let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const staffCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const staff = await staffCtx.newPage();
staff.setDefaultTimeout(30000);
const portalCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const portal = await portalCtx.newPage();
portal.setDefaultTimeout(30000);
const shot = async (page, name) => {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`      shot ${name}`);
};

async function setSwitch(selector, wanted) {
  const sw = staff.locator(selector).locator("[role='switch']").first();
  await sw.waitFor();
  const now = (await sw.getAttribute("aria-checked")) === "true";
  if (now !== wanted) {
    await sw.click();
    await staff.waitForFunction(
      ([sel, want]) =>
        document.querySelector(`${sel} [role='switch']`)?.getAttribute("aria-checked") === String(want),
      [selector, wanted],
    );
  }
}

async function readLogRow(meter) {
  await staff.goto(`${BASE}/${T}/reads?q=${encodeURIComponent(meter)}`);
  await staff.waitForLoadState("networkidle").catch(() => undefined);
  await staff.waitForTimeout(800);
  return (await staff.locator("main").innerText()).replace(/\s+/g, " ");
}

try {
  // ── 1 · staff switch the portal live and self-read ON ───────────────────
  await staff.goto(`${BASE}/${T}/signin`);
  await staff.fill("#signin-email", STAFF);
  await staff.fill("#signin-password", STAFF_PASSWORD);
  await Promise.all([
    staff.waitForURL((u) => !u.pathname.endsWith("/signin")),
    staff.getByRole("button", { name: /sign in/i }).click(),
  ]);
  await staff.goto(`${BASE}/${T}/settings/reference-data/customer-portal`);
  await staff.locator("[data-switch='self_read_enabled']").waitFor();
  await setSwitch("[data-portal-live] ~ div", true).catch(async () => {
    // The live switch sits in the panel beside `data-portal-live`.
    const live = staff.locator("[data-portal-live]").locator("xpath=..").locator("[role='switch']");
    if ((await live.getAttribute("aria-checked")) !== "true") await live.click();
  });
  await setSwitch("[data-switch='self_read_enabled']", true);
  check(
    "Settings — self-read is ON",
    (await staff.locator("[data-switch='self_read_enabled'] [role='switch']").getAttribute("aria-checked")) ===
      "true",
  );
  await shot(staff, "01-staff-settings-self-read-on.png");

  // ── 2 · the customer signs in, opens Readings, sees Send a reading ──────
  await portal.goto(`${BASE}/${T}/portal/sign-in`);
  await portal.fill("#portal-email", PORTAL_LOGIN);
  await portal.fill("#portal-password", PORTAL_PASSWORD);
  await portal.locator("main button", { hasText: /^Sign in$/ }).click();
  await portal.waitForURL(/\/portal\/home/);
  await portal.goto(`${BASE}/${T}/portal/readings`);
  const action = portal.locator("a[data-send-reading]");
  await action.waitFor();
  check(
    "Readings — Send a reading opens /usage/submit",
    (await action.getAttribute("href")) === `/${T}/portal/usage/submit`,
  );
  await shot(portal, "02-portal-readings-send-a-reading.png");

  // ── 3 · a normal reading → Received ─────────────────────────────────────
  await action.click();
  await portal.waitForURL(/\/portal\/usage\/submit/);
  await portal.locator("[data-screen='CWP-035'] form").waitFor();
  await portal.selectOption("#sr-meter", NORMAL.meter);
  await shot(portal, "03-portal-send-form.png");
  await portal.fill("#sr-value", NORMAL.value);
  // Keyboard only, from the dial box: Tab past Cancel to Send, then Enter.
  await portal.locator("#sr-value").press("Enter");
  const status = portal.locator("[role='status'][data-received]");
  await status.waitFor();
  const cleanText = (await status.innerText()).replace(/\s+/g, " ");
  check(
    "Normal reading — Received (no flag)",
    (await status.getAttribute("data-received")) === "clean" && /received/i.test(cleanText),
    cleanText,
  );
  await shot(portal, "04-portal-received.png");

  // ── 4 · staff read log shows Source "Customer" ──────────────────────────
  const logNormal = await readLogRow(NORMAL.meter);
  check("Read log — W-5000 shows Source Customer", /Customer/.test(logNormal));
  await shot(staff, "05-staff-read-log-source-customer.png");

  // ── 5 · a very high reading → accepted and flagged ──────────────────────
  await portal.goto(`${BASE}/${T}/portal/usage/submit`);
  await portal.locator("#sr-meter").waitFor();
  await portal.selectOption("#sr-meter", HIGH.meter);
  await portal.fill("#sr-value", HIGH.value);
  await portal.getByRole("button", { name: "Send it" }).click();
  await status.waitFor();
  const flaggedText = (await status.innerText()).replace(/\s+/g, " ");
  check(
    "Very high reading — Received and flagged",
    (await status.getAttribute("data-received")) === "flagged" && /we will check it/i.test(flaggedText),
    flaggedText,
  );
  await shot(portal, "06-portal-received-flagged.png");
  const logHigh = await readLogRow(HIGH.meter);
  check(
    "Read log — E-5000 shows Source Customer and a High flag",
    /Customer/.test(logHigh) && /High/i.test(logHigh),
  );
  await shot(staff, "07-staff-read-log-flagged.png");

  // ── 6 · switch OFF → the portal hides the action and the form ───────────
  await staff.goto(`${BASE}/${T}/settings/reference-data/customer-portal`);
  await staff.locator("[data-switch='self_read_enabled']").waitFor();
  await setSwitch("[data-switch='self_read_enabled']", false);
  await shot(staff, "08-staff-settings-self-read-off.png");
  await portal.goto(`${BASE}/${T}/portal/readings`);
  await portal.locator("[data-screen='CWP-034']").waitFor();
  await portal.waitForLoadState("networkidle").catch(() => undefined);
  check("Self-read off — Readings has no Send a reading", (await action.count()) === 0);
  await shot(portal, "09-portal-readings-no-action.png");
  await portal.goto(`${BASE}/${T}/portal/usage/submit`);
  await portal.locator("[data-portal-state='failed']").waitFor();
  const offText = (await portal.locator("main").innerText()).replace(/\s+/g, " ");
  check(
    "Self-read off — the address draws no form, only the refusal",
    (await portal.locator("[data-screen='CWP-035'] form").count()) === 0 &&
      /not taken online/.test(offText),
    offText.slice(0, 160),
  );
  await shot(portal, "10-portal-send-refused-when-off.png");

  // ── 7 · phone width — no sideways scroll on the form (question 6) ───────
  await setSwitch("[data-switch='self_read_enabled']", true);
  const phone = await portalCtx.newPage();
  await phone.setViewportSize({ width: 390, height: 900 });
  await phone.goto(`${BASE}/${T}/portal/usage/submit`);
  await phone.locator("#sr-value").waitFor();
  const scroll = await phone.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  const heights = await phone.evaluate(() =>
    ["#sr-meter", "#sr-date", "#sr-value"].map((s) => document.querySelector(s)?.getBoundingClientRect().height ?? 0),
  );
  check("390px — no sideways scroll", !scroll);
  check("390px — every box at least 44px tall", heights.every((h) => h >= 44), JSON.stringify(heights));
  await phone.screenshot({ path: join(OUT, "11-portal-send-form-390.png"), fullPage: true });
} finally {
  await browser.close();
}
console.log(failed ? `${failed} FAILED` : "ALL PASS");
process.exit(failed ? 1 : 0);
