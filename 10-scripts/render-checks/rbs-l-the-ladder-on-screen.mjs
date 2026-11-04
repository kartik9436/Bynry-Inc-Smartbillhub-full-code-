/**
 * RENDERED-OUTPUT CHECK — CR-075 wave L tasks `L2` and `L6`, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. The Product Owner's
 * own definition of done, 2026-09-06: *"everything should be executed based on
 * actual code, and rules that we place, also ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **WHAT THIS CHECK CAN AND CANNOT PROVE, SAID BEFORE ANYTHING ELSE — because
 * a walkthrough that quietly substitutes a different subject is worse than no
 * walkthrough.** Wave L builds the ACTING half and puts **no new screen** in the
 * product: `L7`'s Review/Approve/Applying/Done screens are another lane's, and
 * `POST /runbooks/{key}/runs` is `L3`'s, in an `api.py` this lane may not edit.
 * So there is no button anywhere that starts the collections ladder, and this
 * script does not pretend to press one.
 *
 * **What wave L DID put on a screen is the template's own entry in the library,
 * and that is a real assertion of three things this wave built:**
 *
 *   1  **RUNBOOK 8 IS REGISTERED AND REACHES THE BROWSER.** `L6` adds one line
 *      to `DEFINITION_MODULES`; if that line is missing, the module is imported,
 *      every unit test still passes, and the template simply never appears —
 *      which is hard-won law 2 (built is not wired) in this module's own shape.
 *      Only a browser can tell you it arrived.
 *   2  **"WHAT IT CAN TOUCH" IS DERIVED FROM `ports[]` AND FROM NOTHING ELSE**
 *      (`US-RBS-002`). The Check reads *writes nothing*; the ladder names its
 *      TWO ports. A hand-written label that disagreed with the constructor is
 *      exactly what this pair of rows catches, and it is the first time in this
 *      product that a template row has had to say two different things.
 *   3  **THERE IS NO CONTROL ON THIS SCREEN THAT CAN SEND ANYTHING.** Phase 2's
 *      launch sentence is *"a clerk sees exactly what would be sent to 812
 *      accounts and cannot yet send it"*. Asserted as an ABSENCE over the whole
 *      page: no button whose text is Send, Run, Approve or Apply.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3.12 06-backend/manage.py runserver 127.0.0.1:8123 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4321 API_PROXY_TARGET=http://127.0.0.1:8123 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4321 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-l-the-ladder-on-screen.mjs
 *
 * ⚠ **SIGN-IN IS AN XHR AND `networkidle` RETURNS BEFORE THE SESSION EXISTS.**
 * The email field is `#signin-email` and is `type="text"`, NOT `type="email"`,
 * so the obvious `input[type=email]` selector finds nothing. After submitting we
 * WAIT FOR THE DASHBOARD URL; without that wait every later call answers 401 and
 * the failure reads like a broken screen rather than like a race.
 */

import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// ⚠ **`playwright-core` IS RESOLVED FROM THE FRONTEND'S OWN `node_modules`, NOT
// FROM THIS DIRECTORY.** A bare `import "playwright"` here fails with
// `ERR_MODULE_NOT_FOUND`, because `10-scripts/` has no package of its own —
// which is exactly how the first run of this file ended.
// `rbs-c-can-we-bill.mjs` resolves it this way and this is that shape.
const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4321";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const notes = [];

function check(label, ok, detail = "") {
  if (ok) {
    notes.push(`  ok   ${label}${detail ? ` — ${detail}` : ""}`);
  } else {
    problems.push(`  FAIL ${label}${detail ? ` — ${detail}` : ""}`);
  }
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage();
page.on("console", (message) => {
  if (message.type() === "error") notes.push(`  (console error) ${message.text()}`);
});

try {
  // ── sign in ──────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ THE WAIT THAT MATTERS. Sign-in is an XHR; `networkidle` returns before
  // the session cookie exists and every later request 401s.
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  // ── the template library, which is where runbook 8 first appears ─────────
  await page.goto(`${BASE}/${TENANT}/runbooks/templates`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");

  // 1 · IT ARRIVED. The name a clerk reads is the SCREEN name — "Collections
  //     ladder" — and not the card's title, *Dunning and notices* (`RB-108`).
  check(
    "runbook 8 reached the browser as 'Collections ladder'",
    /Collections ladder/i.test(body),
    `library page text length ${body.length}`
  );

  // 2 · IT IS AN ACTION IN THE COLLECTIONS CATEGORY. Both are drawn from the
  //     definition, so a wrong `kind` or a wrong `category` shows here.
  check("the Collections category is drawn", /Collections/i.test(body));

  // 3 · WHAT IT CAN TOUCH — the two ports, from `ports[]` and nothing else.
  const api = await page.evaluate(async (tenant) => {
    const response = await fetch(`/api/${tenant}/runbooks/templates?per=200`, {
      credentials: "same-origin",
    });
    return response.ok ? response.json() : { error: response.status };
  }, TENANT);
  const rows = api?.results ?? [];
  const ladder = rows.find((row) => row.template_key === "collections_ladder");
  const check1 = rows.find((row) => row.template_key === "configuration_check");
  check("the library served the ladder", Boolean(ladder), `${rows.length} template(s) served`);
  if (ladder) {
    check("its kind is action", ladder.kind === "action", `kind=${ladder.kind}`);
    check("its category is collections", ladder.category === "collections");
    check(
      "it names exactly its two ports",
      JSON.stringify([...(ladder.ports ?? [])].sort()) ===
        JSON.stringify(["apply_fee", "queue_notice"]),
      JSON.stringify(ladder.ports)
    );
    check("and it does NOT read 'writes nothing'", ladder.writes_nothing === false);
  }
  if (check1) {
    // The other half of the same rule, so the assertion cannot pass by the
    // field being wrong for everybody in the same direction.
    check("the Check still reads 'writes nothing'", check1.writes_nothing === true);
    check("and the Check names no port at all", (check1.ports ?? []).length === 0);
  }

  // 4 · NOTHING ON THIS PAGE CAN SEND. Phase 2's launch sentence, as an
  //     absence over every control the page actually draws.
  const controls = await page
    .locator("button, a[role='button'], input[type='submit']")
    .allInnerTexts();
  const dangerous = controls
    .map((text) => text.trim())
    .filter((text) => /^(send|approve|apply|run( ▶)?)$/i.test(text));
  check(
    "no control on the library can send, approve, apply or run",
    dangerous.length === 0,
    dangerous.length ? `found: ${dangerous.join(" · ")}` : `${controls.length} control(s) read`
  );

  // 5 · AND THE WRITE ROUTE THAT WOULD START IT IS NOT THERE. Asserted over
  //     HTTP rather than by reading the code, because the question is what the
  //     RUNNING server does. 404 or 405 both mean *there is no way in*; a 200
  //     or a 202 would mean the dry half had quietly acquired a live half.
  const start = await page.evaluate(async (tenant) => {
    const response = await fetch(`/api/${tenant}/runbooks/collections_ladder/runs`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    return response.status;
  }, TENANT);
  check(
    "there is no route that starts the ladder",
    start === 404 || start === 405 || start === 403,
    `POST .../runs answered ${start}`
  );
} catch (error) {
  problems.push(`  FAIL the walkthrough threw — ${error.message}`);
} finally {
  await browser.close();
}

console.log("RBS-L · the collections ladder on screen");
for (const line of notes) console.log(line);
for (const line of problems) console.log(line);
console.log(
  problems.length === 0
    ? `PASS — ${notes.filter((n) => n.startsWith("  ok")).length} assertion(s), 0 problems`
    : `FAIL — ${problems.length} problem(s)`
);
process.exit(problems.length === 0 ? 0 : 1);
