// ── Trace ──────────────────────────────────────────────
// Change:  CR-145-BRC08 tasks F1–F4 — six session and lockout rules become
//          per-utility settings (PO 2026-09-28, "Im okay with these limit").
// Rules:   BR-IDN-025 / BR-IDN-026 as amended · B14 rule 33 (on-screen text is
//          capped by what it is FOR) · B14 rule 44 (our UI standard decides how
//          a screen is BUILT) · CLAUDE.md hard-won law 6 — NO GATE IN THIS REPO
//          READS RENDERED OUTPUT, so this script is the only check that does
// ───────────────────────────────────────────────────────
/**
 * Walk the Security tab and the sign-in door IN A REAL BROWSER, at the two
 * widths the staff app is verified at.
 *
 *     BASE=http://127.0.0.1:8591 SHOTS=scratchpad/po-shots \
 *       node 10-scripts/cr145_security_settings_walkthrough.mjs
 *
 * ⚠ **WHAT THIS PROVES AND WHAT IT DOES NOT — READ BEFORE QUOTING IT.**
 * The API is served by `page.route` here, NOT by Django: this container has no
 * Docker daemon and no booted stack, so a full-stack walk was not available.
 * **Everything on the SCREEN is real** — the real bundle, the real stylesheet,
 * the real component kit, real layout at real widths — and that is exactly the
 * half no gate can see. **Nothing about the SERVER is proved here**: not the
 * migration, not the validation, not the audit row. Those belong to `B1`–`B13`
 * and to `T11`, whose end-to-end case (set 15 minutes, be signed out at 15) is
 * the thing that actually closes this change request.
 *
 * ⚠ **THE FIXTURE BELOW IS THE SERVER'S OWN SHAPE, COPIED FROM
 * `services.SETTING_LIMITS` AT `22ef3fc7e`** — six entries, and deliberately no
 * `pw_min_length` or `pw_expiry_days` among them (`DEF-IDN-7501`). A fixture
 * invented to suit the screen would prove the screen agrees with itself.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8591";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS ?? "scratchpad/po-shots";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const fail = (m) => { problems.push(m); console.log("  x " + m); };
const ok = (m) => console.log("  ok " + m);

const POLICY = {
  pw_min_length: 8,
  pw_require_mixed: true,
  pw_require_symbol: false,
  pw_expiry_days: null,
  session_timeout_minutes: 60,
  ip_allowlist: [],
  absolute_session_hours: 12,
  keep_signed_in_offered: true,
  keep_signed_in_days: 30,
  lockout_max_failed: 5,
  lockout_minutes: 15,
  limits: {
    session_timeout_minutes: { choices: [15, 30, 45, 60], default: 60 },
    absolute_session_hours: { min: 4, max: 12, default: 12 },
    keep_signed_in_offered: { boolean: true, default: true },
    keep_signed_in_days: { min: 1, max: 30, default: 30 },
    lockout_max_failed: { min: 3, max: 10, default: 5 },
    lockout_minutes: { min: 5, max: 60, default: 15 },
  },
};

const ME = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbendutilities.com",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

/** State the walk changes between steps. */
const state = { offersKeepSignedIn: true, refuseField: null };

const json = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function serveApi(page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (path.endsWith("/auth/sign-in-options")) {
      return json(route, { keep_signed_in_offered: state.offersKeepSignedIn });
    }
    if (path.endsWith("/settings/security-policy")) {
      if (method === "PUT" && state.refuseField) {
        const lim = POLICY.limits[state.refuseField];
        return json(
          route,
          {
            error: {
              code: "VAL-RANGE",
              message_key: "errors.validation.failed",
              field_errors: [
                {
                  field: state.refuseField,
                  code: "VAL-RANGE",
                  message_key: "errors.identity.value_out_of_range",
                  params: { min: lim.min, max: lim.max },
                },
              ],
            },
          },
          400,
        );
      }
      return json(route, POLICY);
    }
    if (path.endsWith("/me/permissions")) {
      return json(route, { permissions: { settings: "edit" } });
    }
    if (path.endsWith("/me")) return json(route, ME);
    // Anything else this screen reaches for answers empty rather than hanging.
    return json(route, {});
  });
}

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});

/** One pass of the Security tab at a given width. */
async function walkTab(width) {
  console.log(`\n── Security tab at ${width} ──`);
  const ctx = await browser.newContext({ viewport: { width, height: 1100 } });
  const page = await ctx.newPage();
  await serveApi(page);
  await page.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "networkidle" });
  await page.waitForSelector("#lockout_minutes", { timeout: 30000 });

  // ── The five new controls are on the screen, at their defaults ──────────
  for (const [id, value] of [
    ["absolute_session_hours", "12"],
    ["keep_signed_in_days", "30"],
    ["lockout_max_failed", "5"],
    ["lockout_minutes", "15"],
  ]) {
    const v = await page.inputValue(`#${id}`);
    v === value ? ok(`${id} = ${v}`) : fail(`${id} is ${v}, expected ${value}`);
  }
  const offered = await page.isChecked("#keep_signed_in_offered");
  offered ? ok("keep_signed_in_offered is ticked") : fail("keep_signed_in_offered is not ticked");

  // ── The timeout select offers the server's four and NOT the withdrawn two ─
  const options = await page.$$eval("#session_timeout_minutes option", (els) =>
    els.map((e) => e.textContent.trim()),
  );
  const expected = ["15 minutes", "30 minutes", "45 minutes", "1 hour"];
  JSON.stringify(options) === JSON.stringify(expected)
    ? ok(`timeout choices = ${options.join(" · ")}`)
    : fail(`timeout choices are ${JSON.stringify(options)}, expected ${JSON.stringify(expected)}`);
  for (const gone of ["4 hours", "8 hours"]) {
    options.includes(gone) ? fail(`${gone} is still offered`) : ok(`${gone} is withdrawn`);
  }

  // ── The ranges are stated beside their controls, from the server's numbers ─
  const body = await page.textContent("body");
  for (const sentence of [
    "Between 4 and 12 hours.",
    "Between 1 and 30 days.",
    "Between 3 and 10 tries.",
    "Between 5 and 60 minutes.",
  ]) {
    body.includes(sentence) ? ok(`states "${sentence}"`) : fail(`missing "${sentence}"`);
  }

  // ── The card sentence: the two that survive, and the three that did not ──
  for (const kept of ["The last 5 passwords are blocked.", "A temporary password lasts 7 days."]) {
    body.includes(kept) ? ok(`still states "${kept}"`) : fail(`lost "${kept}"`);
  }
  for (const gone of [
    "5 failed sign-ins lock the account for 15 minutes",
    "every session ends after 12 hours",
    "Fixed for every utility",
  ]) {
    body.includes(gone) ? fail(`still prints "${gone}"`) : ok(`no longer prints "${gone}"`);
  }

  // ── Nothing scrolls sideways at either width (staff app, 1280 and 1440) ──
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  overflow <= 0 ? ok("no horizontal scroll") : fail(`page scrolls sideways by ${overflow}px`);

  await page.screenshot({ path: `${SHOTS}/cr145-security-tab-${width}.png`, fullPage: true });
  ok(`shot → ${SHOTS}/cr145-security-tab-${width}.png`);

  // ── F4: the refusal lands on the control the server named ───────────────
  if (width === 1440) {
    state.refuseField = "lockout_minutes";
    await page.fill("#lockout_minutes", "90");
    await page.click('button:has-text("Save security settings")');
    await page.waitForSelector("#lockout_minutes-error", { timeout: 15000 });
    const msg = (await page.textContent("#lockout_minutes-error")).trim();
    msg === "Choose between 5 and 60."
      ? ok(`lockout_minutes announces "${msg}"`)
      : fail(`lockout_minutes announces "${msg}"`);
    const describedBy = await page.getAttribute("#lockout_minutes", "aria-describedby");
    describedBy.includes("lockout_minutes-error")
      ? ok("the input points at its own error")
      : fail(`aria-describedby is "${describedBy}"`);
    // …and its siblings say nothing.
    for (const sib of ["lockout_max_failed", "absolute_session_hours", "keep_signed_in_days"]) {
      (await page.getAttribute(`#${sib}`, "aria-invalid"))
        ? fail(`${sib} was marked invalid too`)
        : ok(`${sib} is untouched`);
    }
    await page.screenshot({ path: `${SHOTS}/cr145-range-refusal-1440.png`, fullPage: true });
    ok(`shot → ${SHOTS}/cr145-range-refusal-1440.png`);
    state.refuseField = null;
  }
  await ctx.close();
}

/** The sign-in door, with the tick box offered and withheld. */
async function walkSignIn(width, offers) {
  console.log(`\n── Sign-in at ${width}, keep-signed-in ${offers ? "OFFERED" : "OFF"} ──`);
  state.offersKeepSignedIn = offers;
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  const page = await ctx.newPage();
  await serveApi(page);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.waitForSelector("#signin-password", { timeout: 30000 });

  const box = await page.$("#signin-keep");
  if (offers) {
    box ? ok("the tick box is offered") : fail("the tick box is missing where it is offered");
  } else {
    box ? fail("the tick box is drawn although this utility switched it off") : ok("the tick box is gone");
    const text = await page.textContent("body");
    /keep me signed in/i.test(text)
      ? fail("the screen still mentions it — B14 rule 33 says the absence explains nothing")
      : ok("nothing is said about the absence (B14 rule 33)");
  }
  // Either way the door still works.
  (await page.$("#signin-email")) ? ok("email field present") : fail("email field missing");
  (await page.$("#signin-password")) ? ok("password field present") : fail("password field missing");

  await page.screenshot({
    path: `${SHOTS}/cr145-signin-${offers ? "offered" : "off"}-${width}.png`,
    fullPage: true,
  });
  ok(`shot → ${SHOTS}/cr145-signin-${offers ? "offered" : "off"}-${width}.png`);
  await ctx.close();
}

await walkTab(1440);
await walkTab(1280);
await walkSignIn(1440, true);
await walkSignIn(1440, false);
await walkSignIn(1280, false);

await browser.close();
console.log(`\n${problems.length} problem(s)`);
problems.forEach((p) => console.log("  x " + p));
process.exit(problems.length === 0 ? 0 : 1);
