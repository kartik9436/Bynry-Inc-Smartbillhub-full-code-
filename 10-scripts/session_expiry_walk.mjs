// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-6378 — the PO, on production v2.344.0 as System Admin:
//          *"whenever user session expire system show this message - You don't
//          have access to this. Your role can't open Payments. … we need to say
//          your session is expired and login again. this happens many places"*.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app; no gate reads
//          rendered output) · `22-product-maintenance-process.md` steps 0 and 4
//          (reproduce it, then prove the fix against the same reproduction)
// ───────────────────────────────────────────────────────
//
// THE REPRODUCTION, WRITTEN ONCE AND RUN TWICE — against the unchanged build
// (EXPECT=denial) and against the fix (EXPECT=expired). Same steps both times:
//   1. sign in, land on the Dashboard;
//   2. END THE SESSION underneath the open tab — MODE=cookie deletes the
//      session cookie, MODE=row expires the server's session row (what twelve
//      hours does on its own);
//   3. click Payments in the sidebar;
//   4. read what the screen says.
// With EXPECT=expired it then presses Sign in, signs in again and checks the
// browser is back on Payments rather than the Dashboard.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   10-scripts/proof-db.sh clone session --stale-ok   (then migrate it)
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=<the clone> JOBS_EAGER=false \
//      python manage.py runserver 127.0.0.1:8493 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8494 \
//      API_PROXY_TARGET=http://127.0.0.1:8493 node server.mjs)
//   EXPECT=denial|expired MODE=cookie|row DATABASE_URL=<the clone> \
//      BASE=http://127.0.0.1:8494 node 10-scripts/session_expiry_walk.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { execFileSync } = await import("node:child_process");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8494";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const EXPECT = process.env.EXPECT ?? "expired";
const MODE = process.env.MODE ?? "cookie";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots/session";
const TAG = `${EXPECT}-${MODE}`;
if (!["denial", "expired"].includes(EXPECT)) throw new Error("EXPECT is denial or expired");
if (!["cookie", "row"].includes(MODE)) throw new Error("MODE is cookie or row");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const failures = [];
function check(label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(label);
}

/** MODE=row — expire THIS session's row the way twelve hours would. */
function expireSessionRow(sessionId) {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("MODE=row needs DATABASE_URL (the clone, never a shared database)");
  // Hard rule 1: the tenant is set before the tenant table is touched.
  const sql = [
    `select set_config('app.tenant_id', (select id::text from tenants where subdomain = '${TENANT}'), false);`,
    `update sessions set expires_at = now() - interval '1 minute' where id = '${sessionId}';`,
  ].join(" ");
  const out = execFileSync("psql", [url.replace(/\?.*$/, ""), "-Atc", sql], { encoding: "utf8" });
  return out.trim().split("\n").pop();
}

mkdirSync(SHOTS, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(30000);

async function signIn() {
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

try {
  console.log(`\n  ${TAG}`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await signIn();
  await page.getByRole("heading", { level: 1 }).first().waitFor();
  await page.screenshot({ path: join(SHOTS, `${TAG}-01-signed-in.png`) });

  const cookie = (await context.cookies()).find((c) => c.name === "sbh_session");
  check("a session cookie was set by signing in", cookie !== undefined);
  if (MODE === "cookie") {
    await context.clearCookies();
  } else {
    const updated = expireSessionRow(cookie.value);
    check("the session row was expired", updated === "UPDATE 1", updated);
  }

  await page.locator("nav").getByRole("link", { name: "Payments", exact: true }).first().click();
  await page.waitForURL((u) => u.pathname === `/${TENANT}/payments`);
  const expired = page.getByText("Session expired", { exact: true });
  const denied = page.getByText("You don't have access to this.", { exact: true });
  await Promise.race([expired.waitFor(), denied.waitFor()]);
  await page.screenshot({ path: join(SHOTS, `${TAG}-02-after-clicking-payments.png`) });
  const sawExpired = (await expired.count()) > 0;
  const sawDenied = (await denied.count()) > 0;
  console.log(`  screen says: expired=${sawExpired} denied=${sawDenied}`);

  if (EXPECT === "denial") {
    check("REPRODUCED: the unchanged build shows the role denial", sawDenied && !sawExpired);
  } else {
    check("the screen says Session expired", sawExpired);
    check("the role denial is NOT shown", !sawDenied);
    const signInLink = page.getByRole("link", { name: /^Sign in/ });
    const href = await signInLink.getAttribute("href");
    check("Sign in goes to this tenant's sign-in with the way back", href === `/${TENANT}/signin?next=%2Fpayments`, href ?? "");
    await signInLink.click();
    await page.waitForURL((u) => u.pathname === `/${TENANT}/signin`);
    await page.screenshot({ path: join(SHOTS, `${TAG}-03-sign-in-page.png`) });
    await signIn();
    await page.waitForURL((u) => u.pathname === `/${TENANT}/payments`);
    await page.getByRole("heading", { level: 1, name: "Payments" }).waitFor();
    check("signing in again lands back on Payments", new URL(page.url()).pathname === `/${TENANT}/payments`, page.url());
    await page.screenshot({ path: join(SHOTS, `${TAG}-04-back-on-payments.png`) });
  }
} catch (error) {
  failures.push(String(error));
  console.log(`  FAIL  ${error}`);
  await page.screenshot({ path: join(SHOTS, `${TAG}-99-error.png`) }).catch(() => {});
} finally {
  await browser.close();
}
console.log(failures.length === 0 ? `\n  ${TAG}: ALL PASS` : `\n  ${TAG}: ${failures.length} FAILED`);
process.exit(failures.length === 0 ? 0 : 1);
