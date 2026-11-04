#!/usr/bin/env node
/**
 * DEF-IDN-9777 — photograph the field technician's wrong-door notice at 1440,
 * on BOTH screens that show it, against a running Vite dev server.
 *
 * The API is answered in the browser (Playwright route interception), because
 * the two screens are decided by ONE answer each and no other data:
 *   · sign-in (ONB-03): `POST /auth/session` → 403 `identity.signIn.fieldAppOnly`
 *   · the staff shell (DSH-01): `GET /me` → a technician, `GET /shell/display` → 403
 * The server half of both refusals is proved by
 * `06-backend/tests/test_def_idn_9748_technician_surface.py` and
 * `test_def_wrk_9583_field_sign_in.py`; this walk proves what is DRAWN.
 *
 * It FAILS (exit 1) when either screen does not show both PO sentences and one
 * "Open the field app" control pointing at the field app's sign-in, or when the
 * page scrolls sideways at 1440.
 *
 * Usage:
 *   (cd 07-frontend && npx vite --port 5199 --strictPort) &
 *   node 10-scripts/def_idn_9777_field_app_notice_walkthrough.mjs <outdir> [baseUrl]
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const OUT = process.argv[2] ?? "08-qa/def-idn-9777-2026-10-06";
const BASE = process.argv[3] ?? "http://localhost:5199";
const TENANT = "entranosa-water-association";
const FIRST = "Field Technicians do not have access to the staff portal.";
const SECOND = "Please sign in on the Field Technician mobile app instead.";
const OPEN = "Open the field app";
mkdirSync(OUT, { recursive: true });

const TECHNICIAN = {
  id: "u7",
  full_name: "Tomas Field",
  email: "tomas@entranosa.example",
  phone: null,
  role: "field_technician",
  role_name: "Field technician",
  must_change_password: false,
};
const refusal = (key) => ({
  code: "AUTH-002",
  message_key: key,
  params: {},
  field_errors: [],
  br_ref: null,
  trace_id: "walk",
});

let failures = 0;
function check(ok, what) {
  console.log(`${ok ? "PASS" : "FAIL"}  ${what}`);
  if (!ok) failures += 1;
}

async function answer(page, rules) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    // Only the API: Vite serves source modules under `/src/api/…`, which the
    // glob also matches, and answering those with JSON blanks the page.
    if (!url.pathname.startsWith("/api/")) return route.continue();
    for (const [test, status, body] of rules) {
      if (test(url.pathname, method)) {
        return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
      }
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
}

async function verify(page, where) {
  const text = await page.evaluate(() => document.body.innerText);
  check(text.includes(FIRST), `${where}: first sentence shown`);
  check(text.includes(SECOND), `${where}: second sentence shown`);
  const open = page.getByRole("link", { name: OPEN });
  check((await open.count()) === 1, `${where}: exactly one "${OPEN}" control`);
  check(
    (await open.getAttribute("href")) === `/${TENANT}/work/mobile/signin`,
    `${where}: it opens the field app's sign-in`,
  );
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  check(!sideways, `${where}: no sideways scroll at 1440`);
}

/** The pinned revision may be absent in a container; fall back to any installed chromium. */
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = path.join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
try {
  // ── 1 · the sign-in page's error box ─────────────────────────────────────
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await answer(page, [
      [(p, m) => p.endsWith("/auth/session") && m === "POST", 403, refusal("identity.signIn.fieldAppOnly")],
      [(p) => p.endsWith("/me"), 401, refusal("errors.auth.not_authenticated")],
    ]);
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "load", timeout: 120000 });
    await page.locator("#signin-email").waitFor({ timeout: 120000 });
    await page.fill("#signin-email", "tomas@entranosa.example");
    await page.fill("#signin-password", "a-correct-password");
    await page.click('button[type="submit"]');
    await page.getByText(FIRST).waitFor({ timeout: 60000 });
    await verify(page, "sign-in");
    await page.screenshot({ path: path.join(OUT, "def-idn-9777-signin-1440.png"), fullPage: true });
    await context.close();
  }

  // ── 2 · the staff shell's 403 page ───────────────────────────────────────
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await answer(page, [
      [(p) => p.endsWith("/shell/display"), 403, refusal("errors.auth.permission_denied")],
      [(p) => p.endsWith("/me"), 200, TECHNICIAN],
    ]);
    await page.goto(`${BASE}/${TENANT}/dashboard`, { waitUntil: "load", timeout: 120000 });
    await page.getByText(FIRST).waitFor({ timeout: 60000 });
    await verify(page, "shell 403");
    const heading = await page.getByRole("heading", { name: FIRST }).count();
    check(heading === 1, "shell 403: the first sentence heads a centred card");
    await page.screenshot({ path: path.join(OUT, "def-idn-9777-shell-403-1440.png"), fullPage: true });
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
