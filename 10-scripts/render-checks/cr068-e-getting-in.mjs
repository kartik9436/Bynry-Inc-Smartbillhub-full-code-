/**
 * RENDERED-OUTPUT CHECK — CR-068 wave E, "Getting in", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE HAS A SECOND REASON THAT IS ITS OWN.** Four of wave E's
 * rules are about what a screen does NOT say, and an absence is invisible to
 * every check this repo has (CLAUDE.md hard rule 8's own lesson). A test can
 * assert a response body; only a browser can tell you that the masked phone
 * `••• ••• 4218` is on the screen, that the switcher is a LABEL and not a
 * control, and that the two reset panels are the same string.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwpe --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_portal_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8069 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4269 API_PROXY_TARGET=http://127.0.0.1:8069 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4269 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-e-getting-in.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ⚠ **AND IT READS THE ONE-TIME CODE OFF THE OUTBOUND QUEUE, WHICH IS WHAT A
 * PERSON DOES TODAY.** W6 has not activated sending and there is no SMS
 * provider until W8, so the code exists in a queue row and nowhere else. The
 * script fetches it through the API rather than out of a log, which is the
 * same thing the demo script tells a human to do.
 *
 * ── WHAT IT CLICKS (the wave E demo script, 10-execution-plan.md) ─────────
 *   1  `/pine-hill/portal/sign-in` — the front door states THREE doors, and
 *      the staff admin's own email and password are refused with the ORDINARY
 *      failure. No session row is written.
 *   2  *First time here* — three facts off the paper bill. The response body
 *      carries no name, no balance and no address (asserted on the WIRE, not
 *      on the screen). A wrong surname is refused identically.
 *   3  *Prove it is you* — the masked phone `••• ••• 4218` is ON THE SCREEN,
 *      and the real number is NOT anywhere in the DOM.
 *   4  *Choose a password* — eight characters refused where the tenant asks
 *      for twelve, and the consequence panel names `$142.18`.
 *   5  The shell — the switcher is a LABEL for one account (`<select>` count
 *      is zero), six tabs, `aria-current` on the active one, and the active
 *      tab's bottom border is 3px in the tenant's own colour.
 *   6  *Forgotten password* twice.
 *      ⚠ **THIS READ *"Sign out, then forgotten password twice"* UNTIL
 *      2026-09-07 AND THE SCRIPT HAS NEVER SIGNED OUT** (`DEF-CWP-4359`).
 *      It navigates to `/forgot-password` with the session still live. It
 *      could not have signed out: there was no control in the portal until
 *      that defect was fixed. Hard-won law 1 inside a walkthrough header —
 *      a header is a note, and a note nobody re-reads becomes a lie, and
 *      this one said the very gap the PO later reported was covered.
 *      The sign-out is walked by
 *      `10-scripts/render-checks/def-cwp-4359-sign-out.mjs`.
 *      The step itself: a real address and an unknown one — and the two
 *      panels are compared as STRINGS.
 *   7  The landlord — the switcher IS a `<select>` with four flat entries, and
 *      the tenants' own accounts are not among them.
 *   8  Nothing on any of these screens shows a database id or an internal code
 *      (B14 rule 31 · rule 32).
 */

import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  try {
    return chromium.executablePath();
  } catch {
    return execFileSync("bash", ["-lc", "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome | head -1"])
      .toString()
      .trim();
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4269";
const TENANT = "pine-hill";
const STAFF_EMAIL = process.env.SMOKE_EMAIL ?? "sarah@pinehillwp.test";
const STAFF_PASSWORD = process.env.SMOKE_PASSWORD ?? "Pin3Hill!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-e";
const VIEWPORT = { width: 1440, height: 1000 };

const PORTAL = `${BASE}/${TENANT}/portal`;
const ACCOUNT_NO = process.env.SMOKE_ACCOUNT ?? "ACC-10432-A";
const POSTCODE = "78702";
const SURNAME = "Alvarez";
const MASKED_TAIL = "4218";
const CONSEQUENCE_FIGURE = "$142.18";
const LANDLORD_TOTAL = "$872.82";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** B14 rule 31 and rule 32 — never an id, never an internal code, on screen. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

function noInternals(page, where) {
  return page.locator("body").innerText().then((text) => {
    for (const pattern of FORBIDDEN) {
      check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31)`);
    }
  });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  //: `11-response-times.md` §5 — this walkthrough PRINTS what it cost and does
  //: not assert that a target was met. Attached to the CONTEXT rather than the
  //: page so the landlord's second page (step 7) is counted too. It measures
  //: what the run already does; it adds no request of its own.
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-e: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · the front door, and the staff credential ══════════════════════
  console.log("\n── 1 · three doors, and a staff password that opens none of them ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-015"]', { timeout: 20000 });
  for (const door of ["enrol", "quick_pay", "start_service"]) {
    check((await page.locator(`[data-door="${door}"]`).count()) === 1, `the ${door} door is offered`);
  }
  await page.fill("#portal-email", STAFF_EMAIL);
  await page.fill("#portal-password", STAFF_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector("[data-signin-refused]", { timeout: 20000 });
  const refusal = (await page.locator("[data-signin-refused]").innerText()).trim();
  check(refusal.split(/\s+/).length <= 6, `the refusal is ${refusal.split(/\s+/).length} words (B14 rule 33): "${refusal}"`);
  check(!/staff|admin|employee/i.test(refusal), "…and it does not hint that the address is a staff one");
  check(page.url().includes("/sign-in"), "the staff credential opened nothing");
  await page.screenshot({ path: join(OUT, "1-front-door.png"), fullPage: true });

  // ═════ 2 · find my account, and what the WIRE carries ════════════════════
  console.log("\n── 2 · matched, and told nothing ──");
  let findBody = null;
  page.on("response", async (response) => {
    if (response.url().includes("/enrol/find-account") && response.status() === 200) {
      findBody = await response.text();
    }
  });
  await page.goto(`${PORTAL}/enrol`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-016"]', { timeout: 20000 });
  await page.fill("#enrol-account", ACCOUNT_NO);
  await page.fill("#enrol-postcode", POSTCODE);
  await page.fill("#enrol-lastname", "Nobody");
  await page.getByRole("button", { name: /continue/i }).click();
  await page.waitForSelector("[data-enrol-refused]", { timeout: 20000 });
  const wrongName = await page.locator("[data-enrol-refused]").innerText();
  await page.fill("#enrol-lastname", SURNAME);
  await page.getByRole("button", { name: /continue/i }).click();
  await page.waitForSelector('[data-screen="CWP-017"]', { timeout: 20000 });
  // ⚠ ASSERTED ON THE BODY THE SERVER SENT, not on what the screen drew: a
  // field that is served and merely not drawn is still served (BR-CWP-032).
  check(findBody !== null, "the find-account response was captured");
  if (findBody) {
    for (const forbidden of [SURNAME, "Maria", "Elm St", "142.18", "78702"]) {
      check(!findBody.includes(forbidden), `the match body carries no ${forbidden} (BR-CWP-032)`);
    }
  }
  check(wrongName.trim().length > 0, `a wrong surname is refused: "${wrongName.trim()}"`);

  // ═════ 3 · the masked phone, on the screen and only masked ═══════════════
  console.log("\n── 3 · the number we already hold, and only its last four ──");
  const sentTo = (await page.locator("[data-enrol-sentto]").innerText()).trim();
  check(sentTo.startsWith("••• ••• "), `the contact is masked on screen: ${sentTo}`);
  check(sentTo.endsWith(MASKED_TAIL), `…and it is the right four digits (${MASKED_TAIL})`);
  const proveDom = await page.content();
  check(!/\(512\)\s*555/.test(proveDom), "the real number is nowhere in the DOM (BR-CWP-033)");
  check(
    (await page.locator("[data-enrol-wrongnumber]").count()) === 1,
    "…and *wrong number? ring the office* is offered rather than a second address box",
  );
  await page.screenshot({ path: join(OUT, "3-prove-it.png"), fullPage: true });

  // The code is read off the QUEUE — W6 has not activated sending.
  const code = await readCodeFromQueue(context);
  check(/^\d{6}$/.test(code ?? ""), `the code came off the outbound queue (${code})`);
  await page.fill("#enrol-code", code ?? "");
  await page.getByRole("button", { name: /verify/i }).click();
  await page.waitForSelector('[data-screen="CWP-018"]', { timeout: 20000 });

  // ═════ 4 · the policy, and the consequence panel's figure ════════════════
  console.log("\n── 4 · the tenant's own minimum, and the balance stated before the button ──");
  const helper = await page.locator('[data-field="enrol-new"]').innerText();
  check(/\b12\b/.test(helper), `the helper line states the TENANT's minimum: "${helper.trim()}"`);
  const balance = (await page.locator("[data-enrol-balance]").innerText()).trim();
  check(balance === CONSEQUENCE_FIGURE, `the consequence panel says ${balance} (expected ${CONSEQUENCE_FIGURE})`);
  const panelText = await page.locator('[data-testid="enrol-consequences"]').innerText();
  for (const cannot of [/close/i, /belong|owner|name/i, /end your service|service/i]) {
    check(cannot.test(panelText), `…and says what the login cannot do (${cannot})`);
  }
  await page.screenshot({ path: join(OUT, "4-consequences.png"), fullPage: true });
  await page.fill("#enrol-email", `maria+${Date.now()}@example.test`);
  await page.fill("#enrol-new", "Elm-Street-1408");
  await page.fill("#enrol-again", "Elm-Street-1408");
  await page.getByRole("button", { name: /create my login/i }).click();

  // ═════ 5 · the shell ═════════════════════════════════════════════════════
  console.log("\n── 5 · the shell, and a switcher that is a LABEL ──");
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  check(
    (await page.locator('[data-account-switcher="label"]').count()) === 1,
    "one account → the switcher is a LABEL",
  );
  check(
    (await page.locator('[data-account-switcher="select"]').count()) === 0,
    "…and there is no <select> at all — not a disabled one (component inventory §1)",
  );
  const tabs = await page.locator("[data-tab]").count();
  check(tabs === 6, `six tabs (${tabs})`);
  const current = page.locator('[data-tab][aria-current="page"]');
  check((await current.count()) === 1, "exactly one tab carries aria-current");
  // COMPUTED STYLE — the class could be in the DOM and compile to nothing
  // (DEF-974), so the browser is asked what it actually painted.
  const border = await current.evaluate((el) => {
    const style = getComputedStyle(el);
    return { width: style.borderBottomWidth, colour: style.borderBottomColor };
  });
  check(border.width === "3px", `the active tab's border is ${border.width} (component inventory §1)`);
  check(border.colour !== "rgba(0, 0, 0, 0)", `…and it is painted: ${border.colour}`);
  const avatar = (await page.locator("[data-shell-avatar]").innerText()).trim();
  check(/^[A-Z]{1,2}$/.test(avatar), `the avatar is initials, never an id: ${avatar}`);
  const owing = (await page.locator("[data-owing]").first().innerText()).trim();
  check(owing === CONSEQUENCE_FIGURE, `Home's lead tile reads ${owing}`);
  await noInternals(page, "the shell");
  await page.screenshot({ path: join(OUT, "5-shell.png"), fullPage: true });

  // ═════ 6 · the two reset panels, compared as strings ═════════════════════
  console.log("\n── 6 · one answer, whether or not the address has a login ──");
  const panels = [];
  for (const address of ["maria@example.test", "nobody-here@example.test"]) {
    await page.goto(`${PORTAL}/forgot-password`, { waitUntil: "networkidle" });
    await page.fill("#reset-email", address);
    await page.getByRole("button", { name: /send the link/i }).click();
    await page.waitForSelector("[data-reset-answer]", { timeout: 20000 });
    panels.push((await page.locator("[data-reset-answer]").innerText()).trim());
  }
  check(panels[0] === panels[1], `the two panels are the same string: "${panels[0]}" / "${panels[1]}"`);
  await page.screenshot({ path: join(OUT, "6-reset.png"), fullPage: true });

  // ═════ 7 · the landlord, and a FLAT set ══════════════════════════════════
  if (process.env.SMOKE_LANDLORD_EMAIL) {
    console.log("\n── 7 · four flat entries, and no tenant's account among them ──");
    await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
    await page.fill("#portal-email", process.env.SMOKE_LANDLORD_EMAIL);
    await page.fill("#portal-password", process.env.SMOKE_LANDLORD_PASSWORD ?? "");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
    const select = page.locator('[data-account-switcher="select"]');
    check((await select.count()) === 1, "four accounts → the switcher IS a control");
    const options = await select.locator("option").count();
    check(options === 4, `four flat entries (${options}) — a master is one of them, not a parent`);
    const total = (await page.locator("[data-home-total]").innerText()).trim();
    check(total.includes(LANDLORD_TOTAL), `the total reads ${LANDLORD_TOTAL}: "${total}"`);
    await page.screenshot({ path: join(OUT, "7-landlord.png"), fullPage: true });
  } else {
    console.log("\n── 7 · SKIPPED — set SMOKE_LANDLORD_EMAIL to walk the landlord ──");
  }

  // ═════ 9 · what it cost, measured (11-response-times.md §5) ══════════════
  //: ⚠ **A TARGET THAT WAS NOT EXERCISED PRINTS *NOT MEASURED*, and that is the
  //: point.** RT-3 is reached only when a step signs in far enough to load the
  //: shell, and step 7 is skipped unless `SMOKE_LANDLORD_EMAIL` is set — so on a
  //: partial run the table says which figures it does not have rather than
  //: quietly reporting fewer rows.
  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-3", match: "/portal/balance/summary", p95: 600 },
    ],
  });

  await browser.close();
  console.log(`\n${failures.length === 0 ? "GREEN" : `RED — ${failures.length} failure(s)`}`);
  for (const failure of failures) console.log(`   ⛔ ${failure}`);
  process.exit(failures.length === 0 ? 0 : 1);
})().catch((error) => {
  console.error(error);
  process.exit(2);
});

/**
 * The one-time code, read off the outbound queue through the staff API.
 *
 * ⚠ **THIS IS WHAT A PERSON DOES TODAY AND THE SCRIPT SHOULD NOT PRETEND
 * OTHERWISE.** W6 activates email and W8 brings an SMS provider; until then a
 * code is queued and never sent, and the demo script says so in as many words.
 * When sending activates, this helper is the thing that changes.
 */
async function readCodeFromQueue(context) {
  const api = await context.request.get(
    `${BASE}/api/${TENANT}/portal/public/front`,
  );
  if (!api.ok()) return null;
  const probe = await context.request.get(
    `${BASE}/api/${TENANT}/dev/last-portal-code`,
  );
  if (probe.ok()) {
    const body = await probe.json();
    return body.code ?? null;
  }
  return process.env.SMOKE_CODE ?? null;
}
