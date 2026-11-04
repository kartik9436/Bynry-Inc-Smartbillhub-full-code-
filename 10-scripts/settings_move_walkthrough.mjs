/**
 * Walk the Templates + Notifications move and "mail server in Connectors only"
 * in a real browser against a real PostgreSQL (lane SETTINGS-MOVE, 2026-10-22;
 * DEF-NOT-10533, DEF-NOT-10534).
 *
 *     BASE=http://127.0.0.1:5213 node 10-scripts/settings_move_walkthrough.mjs
 *
 * What it proves, in order:
 *   1. Configure's row reads Reference data · Routes & Cycles · Numbering ·
 *      Templates · Notifications · Customer portal, and the top row has no
 *      Notifications tab.
 *   2. The mail-server status on Configure → Notifications FOLLOWS a change
 *      made on Connectors: connect Custom SMTP with one host, read the badge,
 *      change the host through Connectors' own update route, reload, read the
 *      badge again. A badge that read the old Notifications columns would not
 *      move — that is the false pass this step exists to rule out.
 *   3. The Channel status card has no "Nothing is sent" sentence and each
 *      channel carries one live line.
 *   4. Every old /settings/notifications address lands on its new home.
 *   5. The bell's Messages needing attention link opens the Messages tab.
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a stale bundle. The served bundle hash
 * is printed, and step 1 fails on any bundle that still draws the top-row tab.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:5213";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/settings_move_walk";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
await fs.mkdir(OUT, { recursive: true });

let failures = 0;
function check(name, passed, detail = "") {
  console.log(`${passed ? "PASS" : "FAIL"}  ${name}${detail === "" ? "" : ` — ${detail}`}`);
  if (!passed) failures += 1;
}

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();

const shell = await (await fetch(`${BASE}/${TENANT}/dashboard`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(shell) ?? [])[1] ?? "UNKNOWN";
console.log(`STACK: ${BASE} · bundle ${bundle}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 30000 });

const api = (path, init = {}) => ctx.request.fetch(`${BASE}/api/${TENANT}${path}`, init);
const NOTIFICATIONS = `${BASE}/${TENANT}/settings/reference-data/notifications`;

// ── 1 · the rows ───────────────────────────────────────────────────────────
await page.goto(NOTIFICATIONS, { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="notifications-subtabs"]', { timeout: 30000 });
const strips = await page.$$eval('[role="tablist"]', (lists) =>
  lists.map((list) => [...list.querySelectorAll('[role="tab"]')].map((tab) => tab.textContent.trim())),
);
console.log(`ROWS: ${JSON.stringify(strips)}`);
check("the top row has no Notifications tab", !strips[0].includes("Notifications"), strips[0].join(" · "));
check(
  "Configure reads … Templates · Notifications · Customer portal",
  JSON.stringify(strips[1]) ===
    JSON.stringify(["Reference data", "Routes & Cycles", "Numbering", "Templates", "Notifications", "Customer portal"]),
  strips[1].join(" · "),
);
check(
  "Notifications keeps three tabs",
  JSON.stringify(strips[2]) === JSON.stringify(["Settings", "Messages needing attention", "Blocked addresses"]),
  strips[2].join(" · "),
);

// ── 2 · the badge follows Connectors ──────────────────────────────────────
const connect = await api("/integrations/email_smtp/connect", {
  method: "POST",
  data: {
    environment: "production",
    cadence: "manual",
    fields: {
      host: "smtp.office365.com",
      port: "587",
      username: "billing@brazosbendutilities.com",
      password: "Ew3!kQ9-lockbox",
      send_from: "billing@brazosbendutilities.com",
    },
  },
});
console.log(`CONNECT: HTTP ${connect.status()} (409 = already connected by an earlier run)`);
// Re-runnable over its own leftovers: put the host back to the starting value.
await api("/integrations/email_smtp", { method: "PATCH", data: { config: { host: "smtp.office365.com" } } });
await api("/notification-settings", { method: "PATCH", data: { email_dispatch_active: false } });
const heading = async () => {
  await page.goto(NOTIFICATIONS, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="mail-server-heading"]', { timeout: 30000 });
  return (await page.textContent('[data-testid="mail-server-heading"]')).trim();
};
const first = await heading();
check("the badge names the connector's host", first.includes("smtp.office365.com"), first);
check(
  "the sender address is shown",
  ((await page.textContent('[data-testid="mail-server-sender"]')) ?? "").includes("billing@brazosbendutilities.com"),
);
const openHref = await page.getAttribute('[data-testid="mail-server-open-connectors"]', "href");
check("Open Connectors → goes to Custom SMTP", openHref === `/${TENANT}/settings/integrations/email_smtp`, openHref);
await page.screenshot({ path: `${OUT}/notifications-1440-before.png`, fullPage: true });

const moved = await api("/integrations/email_smtp", {
  method: "PATCH",
  data: { config: { host: "smtp.gmail.com" } },
});
console.log(`CONNECTORS PATCH host → smtp.gmail.com: HTTP ${moved.status()}`);
const second = await heading();
check("after changing the host on Connectors, the badge follows", second.includes("smtp.gmail.com"), second);
await page.screenshot({ path: `${OUT}/notifications-1440-after.png`, fullPage: true });

// ── 3 · one true line per channel ─────────────────────────────────────────
const body = (await page.textContent("body")) ?? "";
check("no 'Nothing is sent in this release' sentence", !body.includes("Nothing is sent in this release"));
for (const channel of ["email", "sms", "pdf_print"]) {
  const line = ((await page.textContent(`[data-testid="channel-line-${channel}"]`)) ?? "").trim();
  check(`the ${channel} line is drawn`, line.length > 0, line);
}
const on = await api("/notification-settings", { method: "PATCH", data: { email_dispatch_active: true } });
console.log(`EMAIL SWITCH ON: HTTP ${on.status()}`);
await page.goto(NOTIFICATIONS, { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="channel-line-email"]');
const emailLine = ((await page.textContent('[data-testid="channel-line-email"]')) ?? "").trim();
check(
  "switched on, email reads Sending through Custom SMTP (host)",
  emailLine === "Sending through Custom SMTP (smtp.gmail.com)",
  emailLine,
);
await page.screenshot({ path: `${OUT}/notifications-1440-email-on.png`, fullPage: true });
const refused = await api("/notification-sender", { method: "PATCH", data: { smtp_host: "evil.example" } });
check("a write to smtp_host is refused by name", refused.status() === 422, `HTTP ${refused.status()}`);

await page.setViewportSize({ width: 1280, height: 900 });
await page.goto(NOTIFICATIONS, { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="mail-server-heading"]');
await page.screenshot({ path: `${OUT}/notifications-1280.png`, fullPage: true });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
check("no sideways scroll at 1280", overflow <= 0, `${overflow}px`);
await page.setViewportSize({ width: 1440, height: 950 });

// ── 4 · every old address ─────────────────────────────────────────────────
const OLD = [
  ["/settings/notifications", "/settings/reference-data/notifications"],
  ["/settings/notifications/messages", "/settings/reference-data/notifications/messages"],
  ["/settings/notifications/blocked", "/settings/reference-data/notifications/blocked"],
  ["/settings/notifications/bill_ready", "/settings/reference-data/notifications/bill_ready"],
  ["/settings/notifications/rights", "/settings/reference-data/templates?template=disconnect_notice_10_day"],
  ["/settings/notifications/sender", "/settings/integrations/email_smtp"],
];
for (const [from, to] of OLD) {
  await page.goto(`${BASE}/${TENANT}${from}`, { waitUntil: "networkidle" });
  const url = new URL(page.url());
  const landed = `${url.pathname}${url.search}`;
  check(`${from} lands on its new home`, landed === `/${TENANT}${to}`, landed);
}
await page.goto(`${BASE}/${TENANT}/settings/notifications/rights`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="templates-rights"]', { timeout: 30000 }).catch(() => null);
check("the rights wording shows under the 10-day notice", (await page.$('[data-testid="templates-rights"]')) !== null);
check("…and its platform warning travelled with it", (await page.$('[data-testid="rights-platform-notice"]')) !== null);
await page.screenshot({ path: `${OUT}/templates-rights-1440.png`, fullPage: true });

// ── 5 · the bell ──────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/dashboard`, { waitUntil: "networkidle" });
await page.click(".shell-bell > summary");
await page.click('[data-testid="bell-messages-link"]');
await page.waitForSelector('[data-testid="notifications-tab-messages"][aria-selected="true"]', { timeout: 30000 })
  .catch(() => null);
check(
  "the bell opens Messages needing attention in one click",
  new URL(page.url()).pathname === `/${TENANT}/settings/reference-data/notifications/messages`,
  new URL(page.url()).pathname,
);

await browser.close();
console.log(failures === 0 ? "WALK: all checks passed" : `WALK: ${failures} check(s) FAILED`);
process.exit(failures === 0 ? 0 : 1);
