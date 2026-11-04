// CR-170-BRC10, lane PWD — the forgot-password walk at 1440 on PostgreSQL 16,
// from the System Admin's reset to a fresh sign-in with the new password
// (journey `08-qa/01-e2e/journeys/forgot-password-admin-reset.md`).
//
//   BASE=http://127.0.0.1:5237 OUT=08-qa/password-2026-10-05 \
//   ADMIN=dana@brazosbendutilities.com ADMIN_PW='S3cure!passw0rd' USER_EMAIL=<a user> \
//   node 10-scripts/cr170_forgot_password_walk.mjs
//
// WRITES: one temporary password for USER_EMAIL (the admin's reset), then that
// user's new password. Prints one PASS/FAIL line per check and one line per
// screenshot.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5237";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "08-qa/password-2026-10-05";
const ADMIN = process.env.ADMIN ?? "dana@brazosbendutilities.com";
const ADMIN_PW = process.env.ADMIN_PW ?? "S3cure!passw0rd";
const USER_EMAIL = process.env.USER_EMAIL;
const NEW_PW = process.env.NEW_PW ?? "Harbor2026tide!";
if (!USER_EMAIL) throw new Error("USER_EMAIL is required");
mkdirSync(OUT, { recursive: true });

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
  throw new Error("no chromium found");
}
let failures = 0;
function check(name, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const viewport = { width: 1440, height: 1000 };

async function shot(page, name) {
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log(`=== ${name}.png — ${page.url().replace(BASE, "")}`);
}
async function signIn(page, email, password) {
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('form button[type="submit"]');
}

// ── 1 · The System Admin resets the user on Settings › Users & roles ──────
const adminCtx = await browser.newContext({ viewport });
const admin = await adminCtx.newPage();
await admin.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await signIn(admin, ADMIN, ADMIN_PW);
try {
  await admin.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 });
} catch (error) {
  await admin.screenshot({ path: `${process.env.DEBUG_DIR ?? OUT}/zz-admin-sign-in-failed.png` });
  throw error;
}
await admin.goto(`${BASE}/${TENANT}/settings`, { waitUntil: "networkidle" });
await admin.getByRole("tab", { name: "Users & roles" }).click();
await admin.waitForLoadState("networkidle");
const row = admin.locator("tr", { hasText: USER_EMAIL });
try {
  await row.getByRole("button", { name: "Reset temp password" }).click({ timeout: 20000 });
} catch (error) {
  await admin.screenshot({ path: `${process.env.DEBUG_DIR ?? OUT}/zz-users-tab.png`, fullPage: true });
  throw error;
}
await admin.getByRole("alertdialog").getByRole("button", { name: "Reset temp password" }).click();
const code = admin.locator(".settings-temp-password-value");
await code.waitFor({ timeout: 20000 });
const temp = (await code.textContent())?.trim() ?? "";
check("the admin's reset shows a temporary password once", temp.length >= 8, `${temp.length} chars`);
await shot(admin, "01-admin-resets-user");
await adminCtx.close();

// ── 2 · The user taps Forgot password? and sees the page ──────────────────
const ctx = await browser.newContext({ viewport });
const page = await ctx.newPage();
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.getByRole("link", { name: "Forgot password?" }).click();
await page.waitForURL(new RegExp(`/${TENANT}/forgot-password$`));
const card = page.locator('[data-page="forgot-password"]');
const cardText = (await card.textContent()) ?? "";
check("the forgot page has the ruled heading", cardText.includes("Forgot your password?"));
check(
  "the forgot page has the ruled instruction",
  cardText.includes("Ask your System Admin. They give you a temporary password. Sign in with it."),
);
check("the forgot page shows no contact", !/@|\d{3}[\s.-]?\d{3,4}|contact|administrator/i.test(cardText));
await shot(page, "02-user-forgot-password-page");

// ── 3 · Back to sign in, then the temporary password ──────────────────────
await page.getByRole("link", { name: "Back to sign in" }).click();
await page.waitForURL(new RegExp(`/${TENANT}/signin$`));
await signIn(page, USER_EMAIL, temp);
await page.waitForURL(new RegExp(`/${TENANT}/change-password`), { timeout: 30000 });
check("the temporary password opens the set-a-password screen", true, page.url().replace(BASE, ""));
await shot(page, "03-user-signed-in-with-temp-password");

// ── 4 · The user sets a new password ──────────────────────────────────────
await page.fill("#change-password-new", NEW_PW);
await page.fill("#change-password-confirm", NEW_PW);
await shot(page, "04-user-sets-new-password");
await page.click('form button[type="submit"]');

// ── 5 · Lands on sign-in with the note ────────────────────────────────────
await page.getByText("Password changed. Sign in again.").waitFor({ timeout: 30000 });
check("lands on sign-in", /\/signin$/.test(new URL(page.url()).pathname), page.url().replace(BASE, ""));
check("the one-time flag is consumed", !page.url().includes("changed="));
const me = await page.evaluate(async (t) => (await fetch(`/api/${t}/me`, { credentials: "include" })).status, TENANT);
check("the session was ended (GET /me)", me === 401, String(me));
await shot(page, "05-user-lands-on-sign-in-with-note");

// The temporary password is dead.
await signIn(page, USER_EMAIL, temp);
await page.getByRole("alert").waitFor({ timeout: 20000 });
check("the temporary password no longer works", /\/signin/.test(page.url()));

// ── 6 · The new password reaches the dashboard ────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
check("the note does not come back on a plain visit", (await page.getByText("Password changed. Sign in again.").count()) === 0);
await signIn(page, USER_EMAIL, NEW_PW);
await page.waitForURL(/\/dashboard/, { timeout: 30000 });
await page.waitForLoadState("networkidle");
await page.waitForTimeout(3000);
check("the new password reaches the dashboard", true, page.url().replace(BASE, ""));
await shot(page, "06-user-signs-in-with-new-password-dashboard");

await browser.close();
console.log(failures === 0 ? "ALL PASS" : `${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
