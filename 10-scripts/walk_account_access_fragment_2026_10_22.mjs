/**
 * walk_account_access_fragment_2026_10_22 — the three account-access lanes,
 * merged (CR-188-BRC10 STAFF-INVITE, DEF-CWP-10380/10381 PORTAL-RESET,
 * CR-189-BRC10 PORTAL-EMAIL), walked in Chromium at 1440 on a PRIVATE copy of
 * the dev database, with every one-time link's secret in the URL FRAGMENT
 * (decision log 2026-10-22, MERGE-ACCESS).
 *
 *     WEB=http://127.0.0.1:5611 MAIL="bash <walkshell.sh> <mail.py>" \
 *       OUT=08-qa/account-access-2026-10-22 node 10-scripts/walk_account_access_fragment_2026_10_22.mjs
 *
 * `MAIL_CMD` + `MAIL_PY` read the newest queued email to an address from the
 * database and RENDER it with the dispatcher's own renderer (no SMTP provider
 * on the walk host), so the walk opens exactly the link the email carries.
 *
 * WRITES (private DB only): one staff user, its password; the portal login's
 * password; the portal login's email (moved to a new address, then a new
 * password on it).
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:5611";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "08-qa/account-access-2026-10-22";
const ADMIN = process.env.ADMIN || "dana@brazosbendutilities.com";
const ADMIN_PW = process.env.ADMIN_PW || "S3cure!passw0rd";
const MAIL_CMD = process.env.MAIL_CMD;
const MAIL_PY = process.env.MAIL_PY;
const FACTS = JSON.parse(process.env.FACTS || "{}");
const STAMP = Date.now().toString(36);
const STAFF_EMAIL = `walk.staff.${STAMP}@example.com`;
const STAFF_PW = "Harbor2026tide!";
const CUSTOMER_PW = "Willow-2026-brook";
const NEW_EMAIL = `ana.new.${STAMP}@example.com`;
const NEWER_PW = "Cedar-2026-ridge";
mkdirSync(OUT, { recursive: true });

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  ${detail}` : ""}`);
}
// Only an email queued during THIS run counts: a row left by an earlier run
// would hand the walk a link that is already spent.
const STARTED = new Date(Date.now() - 5000).toISOString();
function mail(to, template) {
  const raw = execFileSync("bash", [MAIL_CMD, MAIL_PY], {
    env: { ...process.env, MAIL_TO: to, MAIL_TEMPLATE: template, MAIL_SINCE: STARTED },
    encoding: "utf8",
  });
  const line = raw.split("\n").find((l) => l.startsWith("MAIL "));
  return JSON.parse(line.slice(5));
}
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
  return undefined;
}
async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/1440-${name}.png`, fullPage: true });
}
function urlNow(page) {
  const u = new URL(page.url());
  return `${u.pathname}${u.search}${u.hash}`;
}
async function waitLinkStripped(page, path) {
  try {
    await page.waitForFunction((p) => `${location.pathname}${location.search}${location.hash}` === p, path, {
      timeout: 15000,
    });
    return true;
  } catch {
    return false;
  }
}

const browser = await chromium.launch({
  executablePath: resolveChromium(),
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));
const requested = [];
page.on("request", (r) => requested.push(r.url()));

try {
  // ══ 1 · staff invite → email → fragment link → set password → sign in ══
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", ADMIN);
  await page.fill("#signin-password", ADMIN_PW);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.goto(`${WEB}/${T}/settings/users`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "+ Invite user" }).click();
  await page.fill("#full_name", "Walk Staffer");
  await page.fill("#email", STAFF_EMAIL);
  const roleSelect = page.locator("#role");
  const roleOptions = await roleSelect.locator("option").allTextContents();
  const roleValue = await roleSelect.locator("option").nth(roleOptions.length > 1 ? 1 : 0).getAttribute("value");
  await roleSelect.selectOption(roleValue);
  await shot(page, "01-staff-invite-form");
  await page.getByRole("button", { name: "Create user" }).click();
  await page.waitForTimeout(2500);
  await shot(page, "02-staff-invite-done");
  const invite = mail(STAFF_EMAIL, "staff_user_invite");
  check("staff invite: an outbound email row exists for the new user", invite.found, invite.id);
  check(
    "staff invite: priority is immediate and the body renders with the link",
    invite.found && invite.priority > 0 && invite.link_in_body,
    `priority=${invite.priority} subject="${invite.subject}"`,
  );
  const staffLink = new URL(invite.link);
  check(
    "staff invite: the secret is in the FRAGMENT, not the query",
    staffLink.search === "" && staffLink.hash.startsWith("#token="),
    `${staffLink.pathname}${staffLink.search}#…`,
  );
  check("staff invite: the kept copy has the link redacted", !invite.kept_has_link && invite.kept_has_marker);
  console.log(`  rendered subject: ${invite.subject}`);
  console.log(`  rendered body:\n${invite.body.split("\n").map((l) => `    | ${l.replace(/token=[^\s]+/, "token=<redacted-in-log>")}`).join("\n")}`);

  // A fresh browser (the invitee is not the admin).
  const invitee = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const ip = await invitee.newPage();
  const inviteeRequests = [];
  ip.on("request", (r) => inviteeRequests.push(r.url()));
  const linkPath = `${staffLink.pathname}${staffLink.hash}`;
  await ip.goto(`${WEB}${linkPath}`, { waitUntil: "networkidle" });
  check(
    "set-password: the token is taken off the address bar",
    await waitLinkStripped(ip, staffLink.pathname),
    urlNow(ip),
  );
  const tokenValue = new URLSearchParams(staffLink.hash.slice(1)).get("token");
  check(
    "set-password: no request URL carried the token",
    !inviteeRequests.some((u) => u.includes(tokenValue)),
    `${inviteeRequests.length} requests`,
  );
  await ip.getByLabel(/New password/).fill(STAFF_PW);
  await ip.getByLabel(/Confirm/).fill(STAFF_PW);
  await shot(ip, "03-set-password");
  await Promise.all([
    ip.waitForURL((u) => u.pathname.endsWith("/signin"), { timeout: 30000 }),
    ip.getByRole("button", { name: "Set password" }).click(),
  ]);
  check("set-password: lands on sign-in with the changed note", (await ip.getByText("Password changed. Sign in again.").count()) > 0);
  await ip.fill("#signin-email", STAFF_EMAIL);
  await ip.fill("#signin-password", STAFF_PW);
  await Promise.all([
    ip.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }).catch(() => null),
    ip.click('button[type="submit"]'),
  ]);
  await ip.waitForTimeout(1500);
  await shot(ip, "04-staff-signed-in");
  check("staff: signs in with the password they chose", !new URL(ip.url()).pathname.endsWith("/signin"), urlNow(ip));
  await invitee.close();

  // ══ 2 · portal forgot-password: empty → error ══
  const portal = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const pp = await portal.newPage();
  const portalRequests = [];
  pp.on("request", (r) => portalRequests.push(r.url()));
  pp.on("pageerror", (e) => console.log(`  PORTAL PAGE ERROR ${e.message}`));
  await pp.goto(`${WEB}/${T}/portal/forgot-password`, { waitUntil: "networkidle" });
  await shot(pp, "05a-portal-forgot-open");
  await pp.getByRole("button", { name: /Send the link/ }).click();
  await pp.waitForTimeout(800);
  await shot(pp, "05-portal-forgot-empty");
  const errText = (await pp.locator('[data-field-error]').allTextContents()).join(" | ");
  check("portal forgot: an empty box is refused inline", errText.length > 0 && (await pp.locator("[data-reset-answer]").count()) === 0, errText);

  // ══ 3 · registered email → email → fragment link → new password → sign in ══
  const LOGIN = FACTS.login.email;
  await pp.locator('input[type="email"], input[name="email"], #reset-email').first().fill(LOGIN);
  await pp.getByRole("button", { name: /Send the link/ }).click();
  await pp.locator("[data-reset-answer]").waitFor({ timeout: 15000 });
  await shot(pp, "06-portal-forgot-sent");
  const reset = mail(LOGIN, "portal_password_reset");
  check("portal reset: an outbound email row exists", reset.found, reset.id);
  check("portal reset: the body renders with the link", reset.found && reset.link_in_body, `subject="${reset.subject}"`);
  const resetLink = new URL(reset.link);
  check(
    "portal reset: ref and token are in the FRAGMENT, not the query",
    resetLink.search === "" && /^#ref=[^&]+&token=/.test(resetLink.hash),
    `${resetLink.pathname}${resetLink.search}#…`,
  );
  check("portal reset: the kept copy has the link redacted", !reset.kept_has_link && reset.kept_has_marker);
  const resetToken = new URLSearchParams(resetLink.hash.slice(1)).get("token");
  await pp.goto(`${WEB}${resetLink.pathname}${resetLink.hash}`, { waitUntil: "networkidle" });
  // Same tab, same path: a fragment-only navigation does NOT reload, which is
  // the case `useLinkSecret` re-reads for (found by this walk).
  const opened = await pp.locator('[data-screen="CWP-018"]').waitFor({ timeout: 10000 }).then(() => true, () => false);
  check("portal reset: the link opens the new-password form (same tab, no reload)", opened);
  check("portal reset: the link is taken off the address bar", await waitLinkStripped(pp, resetLink.pathname), urlNow(pp));
  check("portal reset: no request URL carried the token", !portalRequests.some((u) => u.includes(resetToken)));
  await pp.getByLabel(/^New password/).fill(CUSTOMER_PW);
  await pp.getByLabel(/^Type it again/).fill(CUSTOMER_PW);
  await shot(pp, "07-portal-new-password");
  await pp.getByRole("button", { name: /Save new password/ }).click();
  await pp.locator("[data-reset-done]").waitFor({ timeout: 15000 });
  await shot(pp, "08-portal-reset-done");
  check("portal reset: the done panel shows", true);
  await pp.goto(`${WEB}/${T}/portal/sign-in`, { waitUntil: "networkidle" });
  await pp.locator('input[type="email"]').first().fill(LOGIN);
  await pp.locator('input[type="password"]').first().fill(CUSTOMER_PW);
  await pp.getByRole("button", { name: /^Sign in/ }).first().click();
  await pp.waitForTimeout(3000);
  await shot(pp, "09-portal-signed-in");
  check("portal: signs in with the new password", !new URL(pp.url()).pathname.endsWith("/sign-in"), urlNow(pp));
  await portal.close();

  // ══ 4 · update-email: 3 facts → code on file → new email → confirm → reset link ══
  const ue = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const up = await ue.newPage();
  up.on("pageerror", (e) => console.log(`  UPDATE-EMAIL PAGE ERROR ${e.message}`));
  await up.goto(`${WEB}/${T}/portal/update-email`, { waitUntil: "networkidle" });
  await shot(up, "10-update-email-start");
  await up.fill("#update-account", FACTS.login.account_no);
  await up.fill("#update-postcode", FACTS.login.postcode);
  await up.fill("#update-lastname", FACTS.login.last_name);
  await up.getByRole("button", { name: "Continue →" }).click();
  await up.getByText("Contacts on file").first().waitFor({ timeout: 15000 });
  await shot(up, "11-update-email-options");
  // Choose the EMAIL on file (no SMS provider on the walk host).
  await up.getByRole("radio", { name: /@/ }).first().check();
  await up.getByRole("button", { name: "Send a code" }).click();
  await up.locator("#update-code").waitFor({ timeout: 15000 });
  const onFile = mail(FACTS.login.email, "portal_enrolment_code");
  check("update-email: a one-time code email went to the address on file", onFile.found && !!onFile.code, `subject="${onFile.subject}"`);
  check("update-email: the code renders in the body; the kept copy is redacted", onFile.found && onFile.body.includes(onFile.code) && onFile.kept_has_marker);
  await up.fill("#update-code", onFile.code);
  await up.getByRole("button", { name: "Verify ✓" }).click();
  await up.locator("#update-new-email").waitFor({ timeout: 15000 });
  await shot(up, "12-update-email-new-address");
  await up.fill("#update-new-email", NEW_EMAIL);
  await up.getByRole("button", { name: "Send a code" }).click();
  await up.locator("#update-confirm-code").waitFor({ timeout: 15000 });
  const toNew = mail(NEW_EMAIL, "portal_email_change_code");
  check("update-email: a confirmation code went to the NEW address", toNew.found && !!toNew.code, `subject="${toNew.subject}"`);
  await up.fill("#update-confirm-code", toNew.code);
  await up.getByRole("button", { name: "Confirm ✓" }).click();
  await up.getByText("Email updated").first().waitFor({ timeout: 15000 });
  await shot(up, "13-update-email-done");
  const notice = mail(FACTS.login.email, "portal_email_changed_notice");
  check("update-email: the OLD address is told", notice.found, `subject="${notice.subject}"`);
  const finalReset = mail(NEW_EMAIL, "portal_password_reset");
  check("update-email: a reset link went to the NEW address", finalReset.found && finalReset.link_in_body);
  const finalLink = new URL(finalReset.link);
  check("update-email: that link's secret is in the FRAGMENT", finalLink.search === "" && finalLink.hash.startsWith("#ref="));
  await up.goto(`${WEB}${finalLink.pathname}${finalLink.hash}`, { waitUntil: "networkidle" });
  await up.getByLabel(/^New password/).fill(NEWER_PW);
  await up.getByLabel(/^Type it again/).fill(NEWER_PW);
  await up.getByRole("button", { name: /Save new password/ }).click();
  await up.locator("[data-reset-done]").waitFor({ timeout: 15000 });
  await up.goto(`${WEB}/${T}/portal/sign-in`, { waitUntil: "networkidle" });
  await up.locator('input[type="email"]').first().fill(NEW_EMAIL);
  await up.locator('input[type="password"]').first().fill(NEWER_PW);
  await up.getByRole("button", { name: /^Sign in/ }).first().click();
  await up.waitForTimeout(3000);
  await shot(up, "14-update-email-signed-in");
  check("update-email: signs in at the NEW address with the new password", !new URL(up.url()).pathname.endsWith("/sign-in"), urlNow(up));
  await ue.close();

  // ══ 5 · update-email dead end: nothing on file → call the office ══
  const de = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const dp = await de.newPage();
  await dp.goto(`${WEB}/${T}/portal/update-email`, { waitUntil: "networkidle" });
  await dp.fill("#update-account", FACTS.dead_end.account_no);
  await dp.fill("#update-postcode", FACTS.dead_end.postcode);
  await dp.fill("#update-lastname", FACTS.dead_end.last_name);
  await dp.getByRole("button", { name: "Continue →" }).click();
  await dp.getByText("Call the office").first().waitFor({ timeout: 15000 }).catch(() => null);
  await dp.waitForTimeout(2000);
  await shot(dp, "15-update-email-call-the-office");
  const text = await dp.locator("main, body").first().innerText();
  const digits = (FACTS.support_phone || "").replace(/\D/g, "").slice(-7);
  check(
    "update-email dead end: says call the office, with the utility's number",
    /call/i.test(text) && digits.length > 0 && text.replace(/\D/g, "").includes(digits),
    FACTS.support_phone,
  );
  await de.close();
} catch (err) {
  check("walk completed without an exception", false, String(err).split("\n")[0]);
  await page.screenshot({ path: `${OUT}/1440-ZZ-error.png` }).catch(() => {});
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(failed ? `WALK FAIL (${failed} of ${results.length})` : `WALK PASS (${results.length} checks)`);
process.exit(failed ? 1 : 0);
