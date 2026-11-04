// DEF-IDN-10022 / DEF-IDN-10023 — the Security tab's settings made true (PO
// ruling 2026-10-08). The walk at 1440 on a LOCAL stack (never the live API):
//
//   1. a 90-day expiry and a password changed 91 days ago → sign-in lands on
//      the existing forced-change screen;
//   2. typing the same password again → refused, "Pick one you haven't used
//      recently.";
//   3. a new password → accepted, back to sign-in.
//
// Setup (the walk does not do it — it is two UPDATEs on a scratch database):
//   update security_policies set pw_expiry_days=90 where tenant_id=<brazosbend>;
//   update users set password_changed_at = now() - interval '91 days'
//     where email='dana@brazosbendutilities.com';
//
//   BASE=http://127.0.0.1:8772 OUT=<dir> node 10-scripts/def_idn_security_settings_walk.mjs
//
// WRITES: the user's new password. Prints PASS/FAIL per check, one line per
// screenshot, and FAILS if any API call leaves 127.0.0.1 (never the live API).
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8772";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "08-qa/security-settings-2026-10-08";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const OLD_PW = process.env.OLD_PW ?? "S3cure!passw0rd";
const NEW_PW = process.env.NEW_PW ?? "Harbor2026tide!";
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
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const hosts = new Set();
// Only API calls are checked: the stylesheet loads its webfont from Google Fonts.
page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.pathname.startsWith("/api/")) hosts.add(url.host);
});

async function shot(name) {
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log(`=== ${name}.png — ${page.url().replace(BASE, "")}`);
}

// 1 · Sign in with a 91-day-old password on a 90-day policy.
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", OLD_PW);
await page.click('form button[type="submit"]');
await page.waitForURL(new RegExp(`/${TENANT}/change-password`), { timeout: 30000 });
check("expired password lands on the forced change", page.url().includes("/change-password"));
await shot("1-forced-change-after-expiry");

// 2 · The same password again is refused.
await page.fill("#change-password-new", OLD_PW);
await page.fill("#change-password-confirm", OLD_PW);
await page.click('form button[type="submit"]');
const refusal = page.getByText("Pick one you haven't used recently.");
await refusal.first().waitFor({ timeout: 20000 });
check("reused password refused in words", await refusal.first().isVisible());
await shot("2-reused-password-refused");

// 3 · A new password is accepted and the person signs in again.
await page.fill("#change-password-new", NEW_PW);
await page.fill("#change-password-confirm", NEW_PW);
await page.click('form button[type="submit"]');
await page.getByText("Password changed. Sign in again.").waitFor({ timeout: 30000 });
check("new password accepted", true);
await shot("3-new-password-accepted");

const foreign = [...hosts].filter((host) => !host.startsWith("127.0.0.1"));
check("every API call stayed on 127.0.0.1", foreign.length === 0, foreign.join(", "));
await browser.close();
process.exit(failures ? 1 : 0);
