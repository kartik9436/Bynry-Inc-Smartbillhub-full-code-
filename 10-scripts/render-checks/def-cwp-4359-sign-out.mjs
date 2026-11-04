/**
 * RENDERED-OUTPUT CHECK — `DEF-CWP-4359`, the portal's sign-out, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. The Product Owner's standing definition of done is *"ensure
 * you do web walkthorugh before you sign off the user story or build"*, and
 * this defect is precisely the kind only a browser can settle — **a control
 * that is not there.**
 *
 * ⚠ **AND `cr068-e-getting-in.mjs` SAYS IT ALREADY COVERS THIS AND DOES NOT.**
 * Its header lists step 6 as *"Sign out, then forgotten password twice"*; the
 * script contains no sign-out at all — it navigates to `/forgot-password` with
 * the session still live. It could not have signed out: there was no control.
 * That is hard-won law 1 inside a walkthrough header, and it is why this file
 * asserts the SERVER's answer as well as the screen's.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwp4359 --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_portal_demo
 *   … runserver on $API_PORT, `vite build` + `node server.mjs` on $WEB_PORT …
 *   SMOKE_BASE=http://127.0.0.1:4391 SMOKE_PORTAL_EMAIL=… SMOKE_PORTAL_PASSWORD=… \
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/def-cwp-4359-sign-out.mjs
 *
 * ── WHAT IT CLICKS ────────────────────────────────────────────────────────
 *   1  Sign in as a customer and land on `CWP-022`.
 *   2  The header carries a *Sign out* control — and it is a real `<button>`
 *      that PAINTS: computed colour and font size are read, because
 *      `primitives.tsx` says in capitals that this theme clears Tailwind's
 *      stock palette and a wrong class compiles to NOTHING while `tsc` and
 *      every `toContain` pass.
 *   3  Press it. `POST /portal/auth/sign-out` is observed ON THE WIRE with its
 *      status — a screen that navigated without calling is the defect wearing
 *      a label.
 *   4  The address is `/{tenant}/portal/sign-in` — `BR-CWP-104` — and the
 *      tenant is still in it (`DEF-037`: the staff app once dropped it).
 *   5  The session cookie is GONE from the browser context.
 *   6  **THE SESSION IS GONE ON THE SERVER**, asked directly:
 *      `GET /api/{tenant}/portal/session` answers 401.
 *   7  Walking back to `/home` does not show signed-in content, and Back does
 *      not re-enter it (`replace: true`).
 *
 * ── RUN 2026-09-07 · 2.216.1 · PASS, 17 of 17 ────────────────────────────
 * Pine Hill, Chromium 1194, 1440×1000. The header reads *Help · Sign out ·
 * MA* (Messages is absent because `CWP-053` is unbuilt — the self-releasing
 * hold in `PortalShell.tsx`, working). The control measured
 * `rgb(45, 43, 43)`, the SAME colour as *Help* beside it, which is the claim
 * `NavActionWord` exists to make and the one no `toContain` can check.
 * `POST auth/sign-out` → 200. Landed on `/pine-hill/portal/sign-in`, screen
 * `CWP-015`, *Welcome back*. Cookie gone. `GET portal/session` → **401**.
 * Back did not re-enter; typing `/home` showed no address.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  // ⚠ **THE PATH ON DISK WINS OVER `executablePath()`, WHICH IS THE OPPOSITE
  // OF WHAT THE OTHER RENDER CHECKS DO AND IS DELIBERATE.**
  // `chromium.executablePath()` returns the build the INSTALLED playwright-core
  // expects (`chromium-1234/chrome-linux64/chrome`); this machine has
  // `chromium-1194/chrome-linux/chrome`. The library's answer is a path that
  // does not exist, and it does not throw — so the `try` never falls through
  // and the launch fails with a file-not-found nobody can act on. Looking on
  // disk first is the check that cannot be wrong about what is there.
  try {
    const found = execFileSync("bash", [
      "-lc",
      "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
    ])
      .toString()
      .trim();
    if (found) return found;
  } catch {
    /* fall through to the library's own answer */
  }
  return chromium.executablePath();
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4391";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const EMAIL = process.env.SMOKE_PORTAL_EMAIL ?? "m.alvarez@example.com";
const PASSWORD = process.env.SMOKE_PORTAL_PASSWORD ?? "Elm-Street-1408!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/def-cwp-4359";
const PORTAL = `${BASE}/${TENANT}/portal`;

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const signOutCalls = [];
  page.on("response", (r) => {
    if (r.url().includes("/portal/auth/sign-out")) signOutCalls.push({ url: r.url(), status: r.status() });
  });
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`def-cwp-4359: ${BASE} tenant=${TENANT}`);

  // ── 1 · in ────────────────────────────────────────────────────────────
  console.log("\n── 1 · sign in ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-015"]', { timeout: 20000 });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/\/portal\/home/, { timeout: 20000 });
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  check(true, `signed in and landed on ${new URL(page.url()).pathname}`);
  const cookiesIn = await context.cookies();
  check(cookiesIn.some((c) => c.name === "sbh_portal"), "the session cookie is set");

  // ── 2 · the control is THERE, and it paints ───────────────────────────
  console.log("\n── 2 · the control a customer looks for ──");
  const control = page.locator('[data-action="sign_out"]');
  check((await control.count()) === 1, "the header carries exactly one sign-out control");
  const label = (await control.innerText()).trim();
  check(label.length > 0, `its label is "${label}"`);
  check((await control.evaluate((el) => el.tagName)) === "BUTTON", "it is a real <button>, not a styled span");
  const painted = await control.evaluate((el) => {
    const s = getComputedStyle(el);
    return { color: s.color, fontSize: s.fontSize, cursor: s.cursor, padding: s.paddingLeft };
  });
  // ⚠ COMPUTED STYLE, not a class string. This theme clears Tailwind's stock
  // palette, so a wrong class renders as nothing while every `toContain`
  // passes (`primitives.tsx`, in capitals).
  check(painted.color !== "" && painted.color !== "rgba(0, 0, 0, 0)", `it has a painted colour (${painted.color})`);
  check(painted.cursor === "pointer", "it looks pressable (cursor: pointer)");
  const helpColour = await page
    .locator('header a[href*="/help"]')
    .first()
    .evaluate((el) => getComputedStyle(el).color)
    .catch(() => null);
  check(helpColour === null || helpColour === painted.color, `it matches the nav words beside it (Help is ${helpColour})`);
  await page.screenshot({ path: join(OUT, "1-signed-in-header.png"), fullPage: false });

  // ── 3 · press it, and watch the wire ──────────────────────────────────
  console.log("\n── 3 · press it ──");
  await control.click();
  await page.waitForURL(/\/portal\/sign-in/, { timeout: 20000 });
  check(signOutCalls.length >= 1, `POST auth/sign-out was actually called (${signOutCalls.length}×)`);
  check(signOutCalls.every((c) => c.status === 200), `and the server answered ${signOutCalls.map((c) => c.status).join(", ")}`);

  // ── 4 · where they land (BR-CWP-104) ──────────────────────────────────
  console.log("\n── 4 · where they land ──");
  const landed = new URL(page.url()).pathname;
  check(landed === `/${TENANT}/portal/sign-in`, `landed on ${landed} — the tenant's own portal front door`);
  check(!landed.startsWith("//"), "…and it is not a protocol-relative address (DEF-CWP-3925's fixture trap)");
  await page.waitForSelector('[data-screen="CWP-015"]', { timeout: 20000 });
  check(true, "the front door screen is what rendered");
  await page.screenshot({ path: join(OUT, "2-landed.png"), fullPage: true });

  // ── 5 · the cookie is gone from the browser ───────────────────────────
  console.log("\n── 5 · nothing left in the browser ──");
  const cookiesOut = await context.cookies();
  check(!cookiesOut.some((c) => c.name === "sbh_portal" && c.value), "the session cookie is gone");

  // ── 6 · THE SESSION IS GONE ON THE SERVER ─────────────────────────────
  console.log("\n── 6 · and gone on the SERVER, asked directly ──");
  const session = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/portal/session`, { credentials: "include" });
    return r.status;
  }, TENANT);
  check(session === 401, `GET portal/session answers ${session} — the session is revoked, not merely forgotten`);

  // ── 7 · you cannot walk back in ───────────────────────────────────────
  console.log("\n── 7 · you cannot walk back in ──");
  await page.goBack({ waitUntil: "networkidle" }).catch(() => undefined);
  const afterBack = new URL(page.url()).pathname;
  check(!afterBack.endsWith("/portal/home"), `Back did not re-enter the dead session (at ${afterBack})`);
  await page.goto(`${PORTAL}/home`, { waitUntil: "networkidle" });
  const body = await page.locator("body").innerText();
  check(!/1408 Elm St/.test(body), "typing /home shows no previous customer's address");
  await page.screenshot({ path: join(OUT, "3-home-after-signout.png"), fullPage: true });

  await browser.close();
  console.log(`\n${failures.length === 0 ? "PASS" : `FAIL (${failures.length})`} — screenshots in ${OUT}`);
  for (const f of failures) console.log(`   ⛔ ${f}`);
  process.exit(failures.length === 0 ? 0 : 1);
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
