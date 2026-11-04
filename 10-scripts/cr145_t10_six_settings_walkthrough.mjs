// ── Trace ──────────────────────────────────────────────
// Change:  **CR-145-BRC08** task `T10` — six session and lockout rules became
//          per-utility settings on Settings → Security (PO 2026-09-28,
//          *"Im okay with these limit"*). This walk is the CLOSURE BAR:
//          PO ruling 2026-08-18, *"CR is not closed until we have confirm user
//          is able to perform tasks using screen/browser/UI"*.
// Rules:   BR-IDN-025 / BR-IDN-026 as amended 2026-09-28 · B14 rule 31 (no
//          database id is ever the visible value of a field) · B14 rule 33
//          (label ≤ 3 words · fact ≤ 6 words · instruction ≤ 6 words per
//          sentence · RATIONALE is ZERO words on screen) · CLAUDE.md hard-won
//          law 6 (no gate in this repo reads rendered output) · law 2's mirror
//          (a saved field that governs nothing is a live screen behind a dead
//          control — and it is this change request's whole failure mode).
// ───────────────────────────────────────────────────────
//
//   BASE=http://127.0.0.1:8572 \
//   DBURL=postgres://smartbillhub:smartbillhub@localhost:5432/sbh_cr145t10 \
//     node 10-scripts/cr145_t10_six_settings_walkthrough.mjs
//
// ⚠ **A SCREENSHOT OF A DROPDOWN IS NOT A PROOF, AND THAT IS THE WHOLE DESIGN
// OF THIS SCRIPT.** Every one of the six settings is walked twice — once at
// one value and once at another — and the assertion is that *the product
// BEHAVES differently*, not that the field kept what was typed. A check that
// only reads the field back would pass just as happily over a column nothing
// reads, which is exactly the defect `CR-145` was raised to prevent.
//
// ⚠ **TWO OF THE SIX CANNOT BE PROVED BY WAITING, AND THE SUBSTITUTION IS
// NAMED RATHER THAN HIDDEN.** A twelve-hour session and a thirty-day
// remembered browser are not walkable. Where a wait is impossible the script
// MOVES THE ROW'S CLOCK BACKWARDS IN THE DATABASE — `created_at`,
// `expires_at`, `last_seen_at`, `locked_until` — which is arithmetically what
// the passage of that much time does, and changes no code and no setting. Each
// such step prints `SUBSTITUTED:` and says what it stood in for. The two
// shortest windows — a 15-minute inactivity timeout and a 5-minute lock — are
// walked on the REAL wall clock, with no substitution at all.
//
// ⚠ **BUILD THE BUNDLE WITH A MODE (`DEF-INF-7702` / `DEF-INF-7802`).**
// `npx vite build --mode compose`. A bare `vite build` resolves as
// `production`, bakes the public API host into the bundle, and sign-in then
// answers *"That email or password is incorrect."* over a request that never
// left the page.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8572";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const WRONG = "definitely-not-the-password-9";
const DBURL =
  process.env.DBURL ?? "postgres://smartbillhub:smartbillhub@localhost:5432/sbh_cr145t10";
const OUT = process.env.OUT ?? "/tmp/cr145-t10";
/** The real waits. Lowered only to re-run the script quickly while writing it. */
const IDLE_WAIT_S = Number(process.env.IDLE_WAIT_S ?? 16 * 60 + 20);
const LOCK_WAIT_S = Number(process.env.LOCK_WAIT_S ?? 5 * 60 + 30);
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
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
  throw new Error("no chromium found");
}

let failures = 0;
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
};
const say = (line) => console.log(line);

/** Read-only or clock-only SQL. Never touches a setting and never a policy. */
const sql = (statement) =>
  execFileSync("psql", [DBURL, "-tAc", statement], { encoding: "utf8" }).trim();

const browser = await chromium.launch({ executablePath: resolveChromium() });

async function signedInContext(keepSignedIn = false) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();
  page.setDefaultTimeout(90000);
  // ⚠ ONE RETRY, BECAUSE THE FIRST RUN DIED HERE AND IT WAS NOT THE PRODUCT.
  // Eight contexts, a gate suite and a PostgreSQL test run were sharing this
  // machine; the bundle simply had not painted in 90 seconds. A walk that
  // crashes on a slow paint reports nothing at all about the six settings it
  // exists to measure, which is a worse outcome than a slow one.
  try {
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#signin-email");
  } catch {
    say("    (sign-in page was slow to paint — reloading once)");
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "load" });
    await page.waitForSelector("#signin-email", { timeout: 120000 });
  }
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  if (keepSignedIn) {
    await page.click('label[for="signin-keep"]');
  }
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 120000 }),
    page.click('button[type="submit"]'),
  ]);
  return { context, page };
}

async function openSecurity(page) {
  await page.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#session_timeout_minutes", { timeout: 90000 });
}

/** Set the named controls and press Save, the way a person does. */
async function saveSecurity(page, values) {
  await openSecurity(page);
  for (const [id, value] of Object.entries(values)) {
    if (typeof value === "boolean") {
      const now = await page.isChecked(`#${id}`);
      if (now !== value) await page.click(`label[for="${id}"]`);
    } else if ((await page.getAttribute(`#${id}`, "class"))?.includes("input-num")) {
      await page.fill(`#${id}`, String(value));
    } else {
      const tag = await page.evaluate((sel) => document.querySelector(sel)?.tagName, `#${id}`);
      if (tag === "SELECT") await page.selectOption(`#${id}`, String(value));
      else await page.fill(`#${id}`, String(value));
    }
  }
  await page.click('button:has-text("Save security settings")');
  await page.waitForSelector('[data-toast="region"] >> text=/saved/i', { timeout: 60000 });
}

const seconds = (n) => new Promise((r) => setTimeout(r, n * 1000));

/**
 * Has the product signed this browser out?
 *
 * ⚠ **THE FIRST RUN OF THIS WALK ASKED THE WRONG QUESTION AND CALLED THREE
 * CORRECT SIGN-OUTS A FAILURE.** It read `page.url()` and expected `/signin`.
 * The product does not redirect: it keeps the address the clerk asked for —
 * which is what lets them land back on it afterwards (`DEF-SHL-6378`) — and
 * renders a **Session expired · Sign in again to continue.** card over it. So
 * the URL is unchanged on a sign-out and identical on a success, and the check
 * could not tell them apart in either direction. That is CLAUDE.md hard-won
 * law 7's *looking at the wrong thing*, found the way that law prescribes: by
 * reading a failure and going to look at the screenshot instead of believing
 * the assertion. **Read the rendered screen, which is the only thing that
 * knows.**
 */
async function signedOut(page) {
  const body = await page.evaluate(() => document.body.innerText);
  return /Session expired/i.test(body) || page.url().includes("/signin");
}

/** The mirror, and it is NOT `!signedOut` — an error card is neither. */
async function stillInside(page) {
  if (await signedOut(page)) return false;
  return (await page.$("#session_timeout_minutes")) !== null;
}

const tenantId = sql(`select id from tenants where subdomain = '${TENANT}'`);
const userId = sql(`select id from users where email = '${EMAIL}'`);
const newestSession = () =>
  sql(`select id from sessions where user_id = '${userId}' order by created_at desc limit 1`);

say(`tenant ${tenantId}   user ${userId}`);

// ══════════════════════════════════════════════════════════════════════════
// 0 · THE SCREEN ITSELF — every list comes from the server (F1 + F2)
// ══════════════════════════════════════════════════════════════════════════
say("\n── 0 · Settings → Security, as a person opens it ──");
const admin = await signedInContext();
await openSecurity(admin.page);
await admin.page.screenshot({ path: `${OUT}/00-security-tab.png`, fullPage: true });

const optionValues = (selector) =>
  admin.page.$$eval(`${selector} option`, (nodes) => nodes.map((n) => n.value));
const timeouts = await optionValues("#session_timeout_minutes");
check(
  "inactivity offers 15/30/45/60 and neither withdrawn value",
  JSON.stringify(timeouts) === JSON.stringify(["15", "30", "45", "60"]),
  timeouts.join(","),
);
const minLengths = await optionValues("#pw_min_length");
const expiries = await optionValues("#pw_expiry_days");
check(
  "the two password lists render from the server's limits (F2)",
  JSON.stringify(minLengths) === JSON.stringify(["8", "10", "12"]) &&
    JSON.stringify(expiries) === JSON.stringify(["", "90", "180"]),
  `${minLengths.join(",")} · ${expiries.join(",")}`,
);

// B14 rule 31 — no database id is ever the visible value of a field.
const visibleText = await admin.page.evaluate(() => document.body.innerText);
const uuidOnScreen = visibleText.match(
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
);
check("B14 rule 31 — no database id is visible", uuidOnScreen === null, uuidOnScreen?.[0] ?? "none");

// B14 rule 33 — what each kind of string is allowed to be.
const labels = await admin.page.$$eval(".settings-tab .field label", (nodes) =>
  nodes.map((n) => (n.textContent ?? "").trim()),
);
const tooLongLabels = labels.filter((l) => l.replace(/\(optional\)/, "").trim().split(/\s+/).length > 3);
check("B14 rule 33 — every field label is 3 words or fewer", tooLongLabels.length === 0, tooLongLabels.join(" | "));
const helps = await admin.page.$$eval(".settings-tab .field-help", (nodes) =>
  nodes.map((n) => (n.textContent ?? "").trim()),
);
const tooLongHelp = helps.filter((h) =>
  h
    .split(/(?<=\.)\s+/)
    .some((sentence) => sentence.trim().replace(/\.$/, "").split(/\s+/).length > 6),
);
check(
  "B14 rule 33 — every range help is 6 words or fewer per sentence",
  tooLongHelp.length === 0,
  tooLongHelp.join(" | "),
);
say(`    labels: ${labels.join(" · ")}`);
say(`    helps:  ${helps.join(" · ")}`);

// ⚠ **THE REST OF THE SCREEN'S PROSE IS REPORTED, NOT FAILED — AND SAYING SO
// IS THE POINT (hard-won law 7, a check reporting zero over a scope it
// silently excludes).** The two checks above cover the strings `CR-145` wrote.
// The panel hints and the standing notes are OLDER copy on the same screen and
// several of them run past rule 33's six-word cap for a FACT. Failing this
// walk on them would make a `CR-145` closure hostage to somebody else's
// sentence; saying nothing would let a screen the PO is about to look at go
// unmeasured. So they are counted and printed, and the over-long ones are
// filed as their own defect row.
const prose = [
  ...(await admin.page.$$eval(".settings-tab .panel-hint", (n) => n.map((x) => (x.textContent ?? "").trim()))),
  ...(await admin.page.$$eval(".settings-tab [data-note]", (n) => n.map((x) => (x.textContent ?? "").trim()))),
];
const overCap = prose.filter((line) =>
  line
    .split(/(?<=\.)\s+/)
    .some((sentence) => sentence.trim().replace(/\.$/, "").split(/\s+/).filter(Boolean).length > 6),
);
say(`    rule 33, other copy on this screen: ${overCap.length} of ${prose.length} sentences run past six words`);
for (const line of overCap) say(`      OVER CAP: ${line}`);

// ══════════════════════════════════════════════════════════════════════════
// 1 · WRONG PASSWORDS BEFORE LOCKOUT — three attempts, two settings
// ══════════════════════════════════════════════════════════════════════════
say("\n── 1 · Wrong passwords before lockout ──");

async function tryWrong(times) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(90000);
  for (let i = 0; i < times; i += 1) {
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#signin-email");
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", WRONG);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(2500);
  }
  return { context, page };
}

/** Sign in with the RIGHT password and say whether the product let us in. */
async function tryCorrect() {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(90000);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#signin-email");
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(4000);
  const inside = !page.url().endsWith("/signin");
  return { context, page, inside };
}

await saveSecurity(admin.page, { lockout_max_failed: 5, lockout_minutes: 15 });
say("    the utility allows 5 wrong passwords");
let wrong = await tryWrong(3);
await wrong.context.close();
let attempt = await tryCorrect();
check("at 5 allowed, three wrong passwords do NOT lock the account", attempt.inside, attempt.page.url());
await attempt.context.close();

await saveSecurity(admin.page, { lockout_max_failed: 3, lockout_minutes: 5 });
say("    the utility now allows 3 wrong passwords, and locks for 5 minutes");
wrong = await tryWrong(3);
await wrong.page.screenshot({ path: `${OUT}/01-third-wrong-password.png`, fullPage: true });
await wrong.context.close();
const lockedUntil = sql(`select locked_until from users where id = '${userId}'`);
attempt = await tryCorrect();
check(
  "at 3 allowed, the SAME three wrong passwords lock the account",
  !attempt.inside,
  `locked_until=${lockedUntil}`,
);
await attempt.page.screenshot({ path: `${OUT}/02-locked-out.png`, fullPage: true });
await attempt.context.close();
const lockStarted = Date.now();

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE INACTIVITY TIMEOUT — the clock starts here, and it is a REAL clock
// ══════════════════════════════════════════════════════════════════════════
say("\n── 2 · Sign-out after inactivity: 15 minutes, on the wall clock ──");
await saveSecurity(admin.page, { session_timeout_minutes: "15" });
const idleSession = newestSession();
const idleStarted = Date.now();
// ⚠ CLOSE THE PAGE. A page left open polls, and a polled session is never
// idle — the walk would then measure React Query's refetch interval and call
// it a timeout. The COOKIE lives on the context, so a new page later is the
// same signed-in browser.
await admin.page.close();
say(`    session ${idleSession} is now idle; the tab is closed so nothing polls`);

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE LOCK RELEASES ITSELF AFTER FIVE REAL MINUTES
// ══════════════════════════════════════════════════════════════════════════
const elapsedLock = () => Math.round((Date.now() - lockStarted) / 1000);
say("\n── 3 · Lockout length: five minutes, on the wall clock ──");
await seconds(Math.max(0, 70 - elapsedLock()));
attempt = await tryCorrect();
check(
  `one minute into a five-minute lock the account is still locked (${elapsedLock()}s)`,
  !attempt.inside,
);
await attempt.context.close();
await seconds(Math.max(0, LOCK_WAIT_S - elapsedLock()));
attempt = await tryCorrect();
check(
  `after the five minutes the same password is accepted (${elapsedLock()}s waited, nothing else changed)`,
  attempt.inside,
  attempt.page.url(),
);
await attempt.page.screenshot({ path: `${OUT}/03-lock-expired.png`, fullPage: true });
const unlocked = attempt;

// The other half: a SIXTY-minute lock is not over after the same wait.
say("\n    and the contrast, with the clock moved instead of waited");
await saveSecurity(unlocked.page, { lockout_max_failed: 3, lockout_minutes: 60 });
wrong = await tryWrong(3);
await wrong.context.close();
sql(`update users set locked_until = locked_until - interval '6 minutes' where id = '${userId}'`);
say("    SUBSTITUTED: the lock's clock moved back 6 minutes — the same wait as above, not a setting");
attempt = await tryCorrect();
check("at 60 minutes the same six-minute wait leaves the account locked", !attempt.inside);
await attempt.context.close();
sql(`update users set locked_until = null, failed_attempts = 0 where id = '${userId}'`);
await saveSecurity(unlocked.page, { lockout_max_failed: 5, lockout_minutes: 15 });
say("    lockout put back to 5 tries / 15 minutes");

// ══════════════════════════════════════════════════════════════════════════
// 4 · "KEEP ME SIGNED IN" — offered or not, and for how long
// ══════════════════════════════════════════════════════════════════════════
say("\n── 4 · Whether the tick box is offered ──");
await saveSecurity(unlocked.page, { keep_signed_in_offered: true });
let anon = await browser.newContext();
let anonPage = await anon.newPage();
await anonPage.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await anonPage.waitForSelector("#signin-email");
await anonPage.waitForTimeout(3000);
check("offered ON — the sign-in screen shows the box", (await anonPage.$("#signin-keep")) !== null);
await anonPage.screenshot({ path: `${OUT}/04-keep-offered.png`, fullPage: true });
await anon.close();

await saveSecurity(unlocked.page, { keep_signed_in_offered: false });
anon = await browser.newContext();
anonPage = await anon.newPage();
await anonPage.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await anonPage.waitForSelector("#signin-email");
await anonPage.waitForTimeout(3000);
check("offered OFF — the box is gone from the sign-in screen", (await anonPage.$("#signin-keep")) === null);
await anonPage.screenshot({ path: `${OUT}/05-keep-not-offered.png`, fullPage: true });
await anon.close();
await saveSecurity(unlocked.page, { keep_signed_in_offered: true, keep_signed_in_days: 1 });

say("\n── 5 · How long the box remembers a browser ──");
async function persistentCookieDays() {
  const { context, page } = await signedInContext(true);
  const cookie = (await context.cookies()).find((c) => c.name === "sbh_session");
  const days = cookie && cookie.expires > 0 ? (cookie.expires * 1000 - Date.now()) / 86400000 : 0;
  return { context, page, days, raw: cookie?.expires ?? -1 };
}
let remembered = await persistentCookieDays();
check(
  "at 1 day, the browser is told to keep the sign-in for about a day",
  Math.abs(remembered.days - 1) < 0.05,
  `${remembered.days.toFixed(3)} days`,
);
const oneDaySession = newestSession();
await remembered.context.close();

await saveSecurity(unlocked.page, { keep_signed_in_days: 30 });
remembered = await persistentCookieDays();
check(
  "at 30 days, the same tick box is told to keep it for thirty",
  Math.abs(remembered.days - 30) < 0.05,
  `${remembered.days.toFixed(3)} days`,
);
const thirtyDaySession = newestSession();

// And the renewal window behind the cookie: an old remembered browser is let
// back in only while it is inside the utility's window.
say("    SUBSTITUTED: both remembered sessions aged two days — the wait itself is not walkable");
for (const id of [oneDaySession, thirtyDaySession]) {
  sql(
    `update sessions set created_at = created_at - interval '2 days', ` +
      `last_seen_at = last_seen_at - interval '2 days' where id = '${id}'`,
  );
}
await saveSecurity(unlocked.page, { keep_signed_in_days: 30 });
await remembered.page.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "domcontentloaded" });
await remembered.page.waitForTimeout(4000);
check(
  "at 30 days a two-day-old remembered browser is still let straight back in",
  await stillInside(remembered.page),
  remembered.page.url(),
);
await saveSecurity(unlocked.page, { keep_signed_in_days: 1 });
const stale = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await stale.addCookies([
  { name: "sbh_session", value: oneDaySession, url: BASE, httpOnly: true, sameSite: "Lax" },
]);
const stalePage = await stale.newPage();
await stalePage.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "domcontentloaded" });
await stalePage.waitForTimeout(4000);
check(
  "at 1 day the same two-day-old remembered browser is sent back to sign in",
  await signedOut(stalePage),
  stalePage.url(),
);
await stalePage.screenshot({ path: `${OUT}/06-remembered-expired.png`, fullPage: true });
await stale.close();
await saveSecurity(unlocked.page, { keep_signed_in_days: 30 });
await remembered.context.close();

// ══════════════════════════════════════════════════════════════════════════
// 6 · THE HARD LIMIT AFTER SIGN-IN
// ══════════════════════════════════════════════════════════════════════════
say("\n── 6 · The hard limit after sign-in ──");
await saveSecurity(unlocked.page, { absolute_session_hours: 4 });
let fresh = await signedInContext();
const fourHourSession = newestSession();
const fourHourSpan = sql(
  `select round(extract(epoch from (expires_at - created_at)) / 3600)::int ` +
    `from sessions where id = '${fourHourSession}'`,
);
check("signing in under a 4-hour limit stamps the session to end in 4 hours", fourHourSpan === "4", `${fourHourSpan}h`);
say("    SUBSTITUTED: the session's clock moved back 5 hours — a 12-hour wait is not walkable");
sql(
  `update sessions set created_at = created_at - interval '5 hours', ` +
    `expires_at = expires_at - interval '5 hours', last_seen_at = now() where id = '${fourHourSession}'`,
);
await fresh.page.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "domcontentloaded" });
await fresh.page.waitForTimeout(4000);
check(
  "five hours into a four-hour limit the clerk is signed out, though they were active a moment ago",
  await signedOut(fresh.page),
  fresh.page.url(),
);
await fresh.page.screenshot({ path: `${OUT}/07-hard-limit-4h.png`, fullPage: true });
await fresh.context.close();

await saveSecurity(unlocked.page, { absolute_session_hours: 12 });
fresh = await signedInContext();
const twelveHourSession = newestSession();
const twelveSpan = sql(
  `select round(extract(epoch from (expires_at - created_at)) / 3600)::int ` +
    `from sessions where id = '${twelveHourSession}'`,
);
check("signing in under a 12-hour limit stamps the session to end in 12 hours", twelveSpan === "12", `${twelveSpan}h`);
sql(
  `update sessions set created_at = created_at - interval '5 hours', ` +
    `expires_at = expires_at - interval '5 hours', last_seen_at = now() where id = '${twelveHourSession}'`,
);
await fresh.page.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "domcontentloaded" });
await fresh.page.waitForTimeout(4000);
check(
  "the SAME five hours under a twelve-hour limit changes nothing — still signed in",
  await stillInside(fresh.page),
  fresh.page.url(),
);
await fresh.context.close();

// Close the working context before the idle reload: a page left open polls,
// and eight live contexts on one machine is what made the first run's sign-in
// page time out.
await unlocked.context.close();

// ══════════════════════════════════════════════════════════════════════════
// 7 · BACK TO THE IDLE CLOCK THAT HAS BEEN RUNNING SINCE STEP 2
// ══════════════════════════════════════════════════════════════════════════
const elapsedIdle = () => Math.round((Date.now() - idleStarted) / 1000);
say(`\n── 7 · The inactivity timeout, ${elapsedIdle()}s in ──`);
await seconds(Math.max(0, IDLE_WAIT_S - elapsedIdle()));
const idlePage = await admin.context.newPage();
idlePage.setDefaultTimeout(90000);
await idlePage.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "domcontentloaded" });
await idlePage.waitForTimeout(5000);
check(
  `after ${Math.round(elapsedIdle() / 60)} untouched minutes on a 15-minute timeout the clerk is signed out`,
  await signedOut(idlePage),
  idlePage.url(),
);
await idlePage.screenshot({ path: `${OUT}/08-idle-signed-out.png`, fullPage: true });
await admin.context.close();

// The contrast, because "it signed me out" alone does not prove WHICH number.
const back = await signedInContext();
await saveSecurity(back.page, { session_timeout_minutes: "60" });
const sixtySession = newestSession();
say("    SUBSTITUTED: that session left untouched for 20 minutes by moving its clock, not by waiting again");
sql(`update sessions set last_seen_at = last_seen_at - interval '20 minutes' where id = '${sixtySession}'`);
await back.page.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "domcontentloaded" });
await back.page.waitForTimeout(4000);
check(
  "twenty untouched minutes on a 60-minute timeout signs nobody out",
  await stillInside(back.page),
  back.page.url(),
);

// Put the utility back where the walk found it.
await saveSecurity(back.page, {
  session_timeout_minutes: "60",
  absolute_session_hours: 12,
  keep_signed_in_offered: true,
  keep_signed_in_days: 30,
  lockout_max_failed: 5,
  lockout_minutes: 15,
});
await back.page.screenshot({ path: `${OUT}/09-back-to-defaults.png`, fullPage: true });
say("\n    the utility is back at 60 minutes / 12 hours / offered / 30 days / 5 tries / 15 minutes");
await back.context.close();

await browser.close();
say(`\nscreenshots: ${OUT}`);
say(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
