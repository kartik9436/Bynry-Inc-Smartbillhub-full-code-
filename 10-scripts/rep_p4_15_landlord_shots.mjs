// ── Trace ──────────────────────────────────────────────
// Change:  `CR-142-BRC07` `P4.15` — *"a landlord sees their own account
//          only"*. Screen `CWP-078` at `/{tenant}/portal/property`.
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app — no gate looks at
//          rendered output"*) · law 2's mirror (a live screen behind a dead
//          control) · law 7 (a check's output must distinguish pass from fail
//          TO A READER) · B14 rule 33 (rationale is ZERO WORDS on screen) ·
//          rule 31 (no database id is a visible value) · the customer-portal
//          widths, 390 and 1280.
// ───────────────────────────────────────────────────────
//
// PHOTOGRAPH WHAT IS THERE. No CSS is injected, no element is hidden, no value
// is substituted. Where a state cannot be reached the script SAYS SO in
// `00-README.txt` rather than skipping it — an absence with no reason beside it
// is indistinguishable from a pass (hard-won law 7's fifth shape).
//
//   node 10-scripts/rep_p4_15_landlord_shots.mjs
//
// Env: SMOKE_BASE · SMOKE_TENANT · SHOT_OUT · PW_CHROME
//      LANDLORD_A / LANDLORD_B / PORTAL_PASSWORD
//
// ⚠ **THE ONE THING THESE PICTURES MUST SHOW IS AN ABSENCE**, and an absence
// cannot be read off a PNG. So the script also PRINTS, beside each shot, the
// account numbers it found on the page and the ones it did NOT — and it fails
// loudly if a number belonging to the other landlord is anywhere in the page
// text. A photograph of a correct screen and a photograph of a leaking one look
// identical to a reader who does not know which numbers to expect.

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8123";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const OUT = process.env.SHOT_OUT ?? "/tmp/p415-shots";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const PASSWORD = process.env.PORTAL_PASSWORD ?? "Proof!passw0rd";
const A = process.env.LANDLORD_A ?? "landlord.a@proof.test";
const B = process.env.LANDLORD_B ?? "landlord.b@proof.test";

const notes = [];
let failures = 0;
function note(line) { console.log(line); notes.push(line); }
function check(label, ok, detail) {
  if (!ok) failures += 1;
  note(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1100 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

async function signIn(page, email) {
  // Through the API the screen itself posts to, so the session cookie is the
  // real one. The sign-in FORM is `CWP-016`'s and is not what this walk is
  // about; walking it would make a failure there look like a failure here.
  const answer = await page.evaluate(
    async ([base, tenant, e, p]) => {
      const r = await fetch(`${base}/api/${tenant}/portal/auth/sign-in`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: e, password: p }),
      });
      return { status: r.status, body: await r.text() };
    },
    [BASE, TENANT, email, PASSWORD],
  );
  return answer;
}

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const context = await browser.newContext();
  // ⚠ **THE DEFAULT 30 s IS A CLOCK, AND THIS BOX IS SHARED.** Measured on
  // 2026-09-27 at a load average of 71 (twenty sibling test processes), a
  // first navigation to the built SPA exceeded it and the script reported a
  // TimeoutError over a stack that was answering 200 to `curl` the whole time.
  // A generous ceiling costs nothing when things are fast and is the
  // difference between a real failure and a busy afternoon.
  context.setDefaultTimeout(120_000);
  context.setDefaultNavigationTimeout(120_000);

  for (const [label, email, mine, theirs] of [
    ["landlord-a", A, (process.env.A_HOLDS ?? "").split(","), (process.env.A_NOT ?? "").split(",")],
    ["landlord-b", B, (process.env.B_HOLDS ?? "").split(","), (process.env.B_NOT ?? "").split(",")],
  ]) {
    const page = await context.newPage();
    await page.goto(`${BASE}/${TENANT}/portal/`, { waitUntil: "domcontentloaded" });
    const signedIn = await signIn(page, email);
    check(`${label} · signed in`, signedIn.status === 200, `HTTP ${signedIn.status}`);
    if (signedIn.status !== 200) { note(`  body: ${signedIn.body.slice(0, 200)}`); continue; }

    await page.goto(`${BASE}/${TENANT}/portal/property`, { waitUntil: "networkidle" });
    // ⚠ **WAIT FOR THE CONTENT, NEVER FOR A CLOCK.** The first draft of this
    // script slept 1200 ms and photographed a BLANK body under load, then
    // reported FAIL over a screen that works — hard-won law 7's *looking at the
    // wrong thing*, in the check rather than in the product. `networkidle` is
    // not enough either: it settles before React has painted the answer.
    let painted = true;
    try {
      await page.waitForSelector('[data-statement-total=""]', { timeout: 60_000 });
    } catch {
      painted = false;
    }
    check(`${label} · the statement painted`, painted, painted ? "" : "body never rendered a total");

    for (const width of [1280, 390]) await shot(page, label, width);

    const text = (await page.evaluate(() => document.body.innerText)) ?? "";
    const held = mine.filter(Boolean);
    const not = theirs.filter(Boolean);

    // ⚠ **THE STRINGS ARE THE UNIT LABELS AND THE MONEY, NOT THE ACCOUNT
    // NUMBERS.** The first draft looked for `AC-2026-00045` and failed on a
    // correct page: this screen draws the UNIT — *Apt 105*, *Unit 200* — and
    // the account number is not a visible value on it. The assertion was wrong
    // about the product, which is the same class of fault as the sleep above
    // and was found the same way: by comparing the check against the picture
    // it was taken with.
    check(
      `${label} · everything it HOLDS is on the page`,
      held.length > 0 && held.every((n) => text.includes(n)),
      `expected ${JSON.stringify(held)}`,
    );
    const leaked = not.filter((n) => text.includes(n));
    check(
      `${label} · no account it does NOT hold is anywhere on the page`,
      leaked.length === 0,
      leaked.length ? `LEAKED ${JSON.stringify(leaked)}` : `checked ${JSON.stringify(not)}`,
    );
    // B14 rule 33 — the screen never EXPLAINS the scoping.
    const preachy = ["tenant's", "privacy", "not shown", "only your", "hidden"]
      .filter((w) => text.toLowerCase().includes(w));
    check(
      `${label} · the screen says nothing about WHY a neighbour is absent`,
      preachy.length === 0,
      preachy.length ? `found ${JSON.stringify(preachy)}` : "rule 33: rationale is zero words",
    );
    // Sign out so the next landlord starts clean.
    await page.evaluate(
      async ([base, tenant]) => {
        await fetch(`${base}/api/${tenant}/portal/auth/sign-out`, {
          method: "POST", credentials: "include",
        });
      },
      [BASE, TENANT],
    );
    await context.clearCookies();
    await page.close();
  }

  await browser.close();
  note("");
  note(failures ? `${failures} FAILURE(S)` : "all checks passed");
  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
  process.exit(failures ? 1 : 0);
};

run().catch((err) => {
  console.error(err);
  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + `\nCRASHED: ${err}\n`);
  process.exit(2);
});
