// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-IDN-5653 — EVERY INVITED USER IS LOCKED OUT. Sign-in succeeds,
//          redirects to `/{tenant}/change-password`, and that screen did not
//          exist. The PO photographed the symptom on the live deployment:
//          "We couldn't load your regional settings." with a Retry button.
// Change:  PO ruling 2026-09-17 — the roles & permissions grid moves from a
//          button-revealed panel into a sub-tab of Users & roles.
// Rules:   BR-IDN-022 (forced change) · BR-IDN-011 (a forced change ACTIVATES
//          an invited membership) · BR-IDN-005 (it revokes PRIOR sessions) ·
//          BR-IDN-014 (the matrix is read-only)
//          CLAUDE.md hard-won law 6 — no gate in this repo reads rendered
//          output, so this walk is the only thing that can prove either.
// ───────────────────────────────────────────────────────
/**
 * WALK THE WHOLE LOCKOUT, AS THE LOCKED-OUT USER.
 *
 *     BASE=http://127.0.0.1:8180 node 10-scripts/def_idn_5653_forced_password_walkthrough.mjs
 *
 * It creates a user through the real Add-user screen, takes the temporary
 * password the panel shows ONCE (BR-IDN-021 — no email is sent), signs in as
 * that person, changes the password and checks they reach the product. Then it
 * signs them out and in again to prove the flag stayed cleared.
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY, AND WHAT IS DONE ABOUT IT** —
 * law 7 habit 2, because the first draft of this defect's unit test scored two
 * passes on the broken screen:
 *
 *  * **"A form rendered" is not the assertion.** The catch-all rendered a
 *    LOADING SKELETON inside the shell, which has no nav, no "not built" text
 *    and plenty of markup — so three obvious checks all pass on the defect.
 *    This walk therefore asserts the PO'S OWN SYMPTOM STRING is absent
 *    ("couldn't load your regional settings") and that the screen's own
 *    `data-page` handle is present, and it prints both verdicts.
 *  * **"It navigated to /dashboard" is not proof of getting in.** A redirect
 *    can land on a shell that then fails. So the walk reads the DASHBOARD'S
 *    OWN rendered text and the sidebar, and prints what it found.
 *  * **The screen could be lying about the membership.** It is not asked. The
 *    row is read back from PostgreSQL by the caller, and this script prints
 *    the user's id and email so that read can be exact.
 *  * **A walk against a stale bundle proves a different product.** The served
 *    JS bundle hash is printed first.
 *  * **A refusal path that is never exercised is a refusal path nobody has
 *    seen.** The walk deliberately submits a password that breaks the tenant's
 *    policy FIRST, and prints the rule the server sent back — which is the
 *    only way this screen can state the rules at all (`_FORCED_CHANGE_EXEMPT`
 *    refuses `GET /settings/security-policy` to exactly this user).
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:8180";
const TENANT = process.env.TENANT ?? "brazosbend";
const OWNER = process.env.OWNER_EMAIL ?? "dana@brazosbendutilities.com";
const OWNER_PW = process.env.OWNER_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def_idn_5653";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const STAMP = process.env.STAMP ?? String(Date.now()).slice(-6);
const NEW_EMAIL = `walk.invited.${STAMP}@brazosbend.example`;
const NEW_NAME = "Walk Invited";
const WEAK = "abc";
const STRONG = `W4lk!${STAMP}aZ`;

await fs.mkdir(OUT, { recursive: true });
const verdicts = [];
const say = (ok, line) => {
  verdicts.push({ ok, line });
  console.log(`${ok ? "PASS" : "FAIL"}  ${line}`);
};

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();
const shot = async (name) => {
  const file = `${OUT}/${name}.png`;
  await page.screenshot({ path: file, fullPage: false });
  console.log(`      shot → ${file}`);
};

const indexHtml = await (await fetch(`${BASE}/${TENANT}/signin`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(indexHtml) ?? [])[1] ?? "UNKNOWN";
console.log(`STACK: ${BASE} · tenant ${TENANT} · bundle ${bundle}\n`);

async function signIn(email, password) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
}

async function signOut() {
  await page.click(".foot");
  await page.click('button:has-text("Sign out")');
  await page.waitForURL(/\/signin$/, { timeout: 20000 });
}

// ── 1 · the owner invites somebody, and the temp password is shown ONCE ─────
console.log("── 1 · invite a user (real Add-user screen, real server) ──");
await signIn(OWNER, OWNER_PW);
await page.waitForURL(/\/dashboard/, { timeout: 30000 });
await page.goto(`${BASE}/${TENANT}/settings/users`, { waitUntil: "networkidle" });
await page.click('button:has-text("+ Invite user")');
await page.waitForSelector("#full_name", { timeout: 15000 });
await page.fill("#full_name", NEW_NAME);
await page.fill("#email", NEW_EMAIL);
await page.selectOption("#role", { index: 1 });
await page.click('button:has-text("Create user")');
await page.waitForSelector(".settings-temp-password-value", { timeout: 20000 });
const tempPassword = (await page.locator(".settings-temp-password-value").innerText()).trim();
say(tempPassword.length > 0, `the temp password was shown once: ${tempPassword.length} chars`);
await shot("01-temp-password-issued");
console.log(`      invited: ${NEW_EMAIL}`);
await signOut();

// ── 2 · THE DEFECT: sign in as the invited user ─────────────────────────────
console.log("\n── 2 · sign in as the invited user — this is where they were stranded ──");
await signIn(NEW_EMAIL, tempPassword);
await page.waitForURL(/\/change-password/, { timeout: 30000 });
await page.waitForTimeout(1200); // let any shell boot attempt fail, as it used to
const bodyText = await page.innerText("body");
say(
  !/couldn't load your regional settings|could not load your regional settings/i.test(bodyText),
  "the PO's symptom is GONE — no \"couldn't load your regional settings\"",
);
say(
  (await page.locator('[data-page="change-password"]').count()) === 1,
  "the forced-change screen itself renders at the address sign-in redirects to",
);
say((await page.locator(".app-shell").count()) === 0, "it renders OUTSIDE the app shell");
say((await page.locator("aside.sidebar").count()) === 0, "there is no sidebar to navigate away by");
say(
  (await page.locator('input[type="password"]').count()) === 2,
  "two password boxes — new and confirm, and no current-password field",
);
say(
  !/current password/i.test(bodyText),
  "it never asks for the current password (the server ignores it on a forced change)",
);
await shot("02-change-password-screen");

// ── 3 · the tenant's rules come from the server's refusal ──────────────────
console.log("\n── 3 · a password that breaks the policy — the rules arrive from the server ──");
await page.fill("#change-password-new", WEAK);
await page.fill("#change-password-confirm", WEAK);
await page.click('button[type="submit"]');
await page.waitForTimeout(1500);
const refusal = await page.innerText('[data-page="change-password"]');
const ruleShown = /at least \d+ characters|upper case|symbol/i.test(refusal);
say(ruleShown, `the server's own rule is on the field: ${JSON.stringify(
  (refusal.match(/Use at least \d+ characters\.|Use upper case[^.]*\.|Add at least one symbol[^.]*\./g) ?? []).join(" "),
)}`);
say(
  (await page.locator('[data-page="change-password"]').count()) === 1,
  "the user is still on the screen — a refusal does not strand them again",
);
await shot("03-policy-refusal-from-server");

// ── 4 · the real change, and reaching the product ──────────────────────────
console.log("\n── 4 · set a real password and reach the product ──");
await page.fill("#change-password-new", STRONG);
await page.fill("#change-password-confirm", STRONG);
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 30000 });
await page.waitForTimeout(1500);
const dash = await page.innerText("body");
say(/\/dashboard/.test(page.url()), `landed on the dashboard: ${page.url()}`);
say(
  (await page.locator("aside.sidebar").count()) === 1,
  "the app shell BOOTED for this user — sidebar present",
);
say(
  !/couldn't load|could not load|Retry/i.test(dash),
  "the shell did not fail — no load failure and no Retry button",
);
say(
  (await page.locator('a[href$="/dashboard"], .side-item').count()) > 3,
  "the navigation is live — this is the product, not a frame around an error",
);
await shot("04-reached-the-product");

// ── 5 · it stays fixed: sign out, sign in again ────────────────────────────
console.log("\n── 5 · sign out and back in — the flag stayed cleared ──");
await signOut();
await signIn(NEW_EMAIL, STRONG);
await page.waitForTimeout(2500);
say(
  /\/dashboard/.test(page.url()) && !/change-password/.test(page.url()),
  `the second sign-in goes STRAIGHT to the dashboard: ${page.url()}`,
);
await shot("05-second-signin-straight-in");

// ── 6 · the roles sub-tab (the second task, walked as a user) ──────────────
console.log("\n── 6 · Settings → Users & roles → Roles & permissions ──");
await signOut();
await signIn(OWNER, OWNER_PW);
await page.waitForURL(/\/dashboard/, { timeout: 30000 });
await page.goto(`${BASE}/${TENANT}/settings/users`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const usersTab = await page.innerText("body");
say(
  !/View roles & permissions/i.test(usersTab),
  "the old \"View roles & permissions\" BUTTON is gone — one way in, not two",
);
const strip = page.locator('[aria-label="Users and roles tabs"]');
say((await strip.count()) === 1, "Users & roles now carries a sub-tab strip, like Company's");
await shot("06-users-subtab-strip");

await page.click('[aria-label="Users and roles tabs"] button:has-text("Roles & permissions")');
await page.waitForTimeout(1200);
say(
  /\/settings\/users\/roles$/.test(page.url()),
  `the grid has an ADDRESS now: ${page.url()}`,
);
say(
  (await page.locator(".settings-matrix table").count()) === 1,
  "the read-only matrix renders on its own sub-tab",
);
say(
  (await page.locator(".settings-matrix input, .settings-matrix select, .settings-matrix button").count()) === 0,
  "BR-IDN-014 holds — the grid offers no control that could change it",
);
await shot("07-roles-subtab");

// the link somebody could now send
await page.goto(`${BASE}/${TENANT}/settings/users/roles`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
say(
  (await page.locator(".settings-matrix table").count()) === 1,
  "that address survives a cold load — it can be linked and bookmarked",
);
await shot("08-roles-deep-link");

// ── verdict ────────────────────────────────────────────────────────────────
const failed = verdicts.filter((v) => !v.ok);
console.log(`\n${"─".repeat(70)}`);
console.log(`${verdicts.length - failed.length}/${verdicts.length} checks passed`);
if (failed.length > 0) {
  for (const f of failed) console.log(`  FAILED: ${f.line}`);
}
console.log(`invited user email (read the membership back by this): ${NEW_EMAIL}`);
console.log(`screenshots: ${OUT}`);
await browser.close();
process.exit(failed.length === 0 ? 0 : 1);
