#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 — walks the REAL app with analytics ON (a fake dev key
//          and the walk's own host as the expected host), intercepts every
//          request to PostHog US, and reads what would have been sent.
// Proves:  the page policy lets PostHog in (a CSP refusal happens BEFORE the
//          interception, so a blocked host would capture nothing); sign-in,
//          screen_viewed, list_searched and sign-out arrive; every address is
//          cleaned; the recording carries the chrome and not the customer's
//          name or balance read off the very screen it recorded.
// ───────────────────────────────────────────────────────
//
//   BASE=http://localhost:5191 OUT=<dir> node 10-scripts/cr169_posthog_walkthrough.mjs
//
// Needs the bundle built with VITE_POSTHOG_KEY set and
// VITE_POSTHOG_EXPECTED_HOSTS=<host of BASE>, served by server.mjs, and the API
// running behind it with the seeded demo utility.

import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://localhost:5191";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = process.env.OUT ?? "/tmp/cr169-walk";
mkdirSync(OUT, { recursive: true });

/** Decode one PostHog request body into a list of events. */
function decode(url, body) {
  if (!body || body.length === 0) return [];
  let text;
  // gzip by magic number: `compression=gzip-js` in the query, or a native
  // CompressionStream body announced only by its header.
  if (url.includes("compression=gzip-js") || (body[0] === 0x1f && body[1] === 0x8b)) {
    text = gunzipSync(body).toString("utf8");
  } else {
    text = body.toString("utf8");
    if (text.startsWith("data=")) {
      text = Buffer.from(decodeURIComponent(text.slice(5)), "base64").toString("utf8");
    }
  }
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : parsed.batch ?? [parsed];
  } catch {
    return [{ undecoded: text.slice(0, 200) }];
  }
}

/**
 * ⚠ THE RECORDER COMPRESSES ITS OWN PAYLOAD (`compress_events`): a full
 * snapshot's `data`, and a mutation's `adds` / `texts` / `attributes`, arrive
 * as gzip held in a latin-1 string. A search for "Maria Lopez" over the raw
 * JSON therefore finds NOTHING whether or not she was recorded — a check that
 * cannot fail (law 7). Every such string is inflated before anything is
 * searched; the walk's first draft searched the compressed form and reported
 * a clean result over bytes it could not read.
 */
function inflate(value) {
  if (typeof value === "string" && value.charCodeAt(0) === 0x1f && value.charCodeAt(1) === 0x8b) {
    try {
      return inflate(JSON.parse(gunzipSync(Buffer.from(value, "latin1")).toString("utf8")));
    } catch {
      return "(could not inflate)";
    }
  }
  if (Array.isArray(value)) return value.map(inflate);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, inflate(v)]));
  }
  return value;
}

const events = [];
const hosts = new Set();
const requests = [];
const cspViolations = [];

const browser = await chromium.launch({ executablePath: CHROME });
// ⚠ posthog-js DROPS every event from a bot user agent, and headless Chromium
// announces itself as `HeadlessChrome` — so the walk presents an ordinary one,
// or it would capture nothing and prove nothing.
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  userAgent:
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
});
// …and drops it again when `navigator.webdriver` is true, which Playwright sets.
await page.addInitScript(() => {
  Object.defineProperty(navigator, "webdriver", { get: () => false });
});
page.on("console", (msg) => {
  if (/Content Security Policy|Refused to connect/i.test(msg.text())) cspViolations.push(msg.text());
});
await page.route(/https:\/\/us(-assets)?\.i\.posthog\.com\/.*/, async (route) => {
  const request = route.request();
  hosts.add(new URL(request.url()).host);
  const decoded = decode(request.url(), request.postDataBuffer());
  requests.push({ url: request.url().replace(/[?].*$/, ""), query: new URL(request.url()).search, events: decoded.length, undecoded: decoded.filter((e) => e.undecoded).length });
  events.push(...decoded);
  // The project's remote config, answered as a project with "Record user
  // sessions" switched ON would answer it (CR-169 §10 asks for that setting in
  // all three projects). With `{}` the recorder never starts.
  const body = /\/config(\.js)?(\?|$)/.test(request.url())
    ? JSON.stringify({ sessionRecording: { endpoint: "/s/" }, supportedCompression: ["gzip", "gzip-js"] })
    : "{}";
  await route.fulfill({ status: 200, contentType: "application/json", body });
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
await page.waitForLoadState("networkidle");

// ⚠ NAVIGATE INSIDE THE APP, NEVER `page.goto`, from here on. A full reload
// makes PostHog flush its queue with `sendBeacon` on unload, and a beacon is
// not something Playwright's route can intercept — so a walk that reloads
// between screens loses exactly the events it set out to read.
async function openFromNav(segment) {
  await page.click(`nav a[href$="/${segment}"]`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
}

await openFromNav("accounts");
// The customer name and the first money figure the list SHOWS — what the
// recording must not carry.
const shown = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("main tbody tr, .main tbody tr")].slice(0, 5);
  const cells = rows.flatMap((tr) => [...tr.querySelectorAll("td")].map((td) => td.textContent?.trim() ?? ""));
  const name = cells.find((text) => /^[A-Z][a-z]+[, ][ A-Z]/.test(text) && !/^Await|^Active/.test(text)) ?? null;
  const money = cells.find((text) => /\$\s?[1-9][0-9,]*\.[0-9]{2}/.test(text)) ?? null;
  // Every value the first rows SHOW that a person could be identified by:
  // account numbers, names, premises, balances.
  const secrets = cells
    .map((text) => text.replace(/(Master|Awaits billing|Active)$/g, "").trim())
    .filter((text) => /[A-Z]{1,3}-[0-9]{3,}|[0-9]+\.[0-9]{2}|^[A-Z][a-z]+,? [A-Z][a-z]+/.test(text) && text.length > 4);
  return { name, money, secrets: [...new Set(secrets)] };
});
await page.screenshot({ path: join(OUT, "01-accounts-list-as-shown.png") });

// The LIST's own search (DataTable, `type="search"` inside the page), not the
// shell's universal search box at the top.
const search = page.getByPlaceholder(/Account #/).first();
if (await search.count()) {
  await search.fill(shown.name ? shown.name.split(" ")[0] : "a");
  await page.waitForTimeout(2500);
  await page.waitForLoadState("networkidle");
}
await page.screenshot({ path: join(OUT, "02-accounts-searched.png") });

// Open the first account: its address carries the account's reference, which
// must leave the browser withheld.
const firstRow = page.locator("tbody tr a").first();
let detailPath = null;
if (await firstRow.count()) {
  await firstRow.click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2000);
  detailPath = new URL(page.url()).pathname;
  await page.screenshot({ path: join(OUT, "03-account-detail-as-shown.png") });
}
const detailShown = await page.evaluate(() => document.querySelector("h1")?.textContent?.trim() ?? null);

await openFromNav("payments");
await page.screenshot({ path: join(OUT, "04-payments.png") });

// Let PostHog flush its queue and the recorder its buffer, with the page OPEN.
await page.waitForTimeout(15000);

// Sign out last: `user_signed_out` then a reset.
await page.click("button.foot").catch(() => undefined);
await page.waitForTimeout(500);
const signOut = page.getByRole("menuitem", { name: /sign out/i });
if (await signOut.count()) {
  await signOut.first().click();
  await page.waitForTimeout(5000);
}
await browser.close();

const named = events.filter((e) => e && e.event).map((e) => e.event);
const custom = events.filter((e) => e && e.event && !e.event.startsWith("$"));
const snapshotEvents = inflate(events.filter((e) => e && e.event === "$snapshot"));
const snapshots = JSON.stringify(snapshotEvents);
const inflateFailures = (snapshots.match(/could not inflate/g) ?? []).length;
const all = JSON.stringify(events);

const report = {
  hosts: [...hosts],
  requests,
  cspViolations,
  eventCounts: named.reduce((acc, name) => ({ ...acc, [name]: (acc[name] ?? 0) + 1 }), {}),
  customEvents: custom.map((e) => ({
    event: e.event,
    properties: Object.fromEntries(
      Object.entries(e.properties ?? {}).filter(([k]) =>
        !k.startsWith("$") || ["$current_url", "$pathname", "$groups"].includes(k),
      ),
    ),
  })),
  shownOnScreen: { ...shown, detailTitle: detailShown, detailPath },
  detailPathLeftTheBrowser: detailPath ? all.includes(detailPath) : null,
  recordingContainsDetailTitle: detailShown ? snapshots.includes(detailShown) : null,
  recordingBytes: snapshots.length,
  recordingInflateFailures: inflateFailures,
  recordingStillCompressed: snapshots.includes("\\u001f\\u008b"),
  recordingContainsShownName: shown.name ? snapshots.includes(shown.name) : null,
  recordingContainsShownMoney: shown.money ? snapshots.includes(shown.money) : null,
  secretsChecked: shown.secrets.length,
  secretsFoundInRecording: shown.secrets.filter((secret) => snapshots.includes(secret)),
  secretsFoundInEvents: shown.secrets.filter((secret) => JSON.stringify(custom).includes(secret)),
  anyEventContainsShownName: shown.name ? all.includes(shown.name) : null,
  anyEventContainsOwnerName: all.includes("Dana Whitfield"),
  anyEventContainsOwnerEmail: all.includes(EMAIL),
  recordingContainsChrome: ["Accounts", "Payments", "Dashboard"].filter((word) => snapshots.includes(word)),
};
writeFileSync(join(OUT, "walk-report.json"), JSON.stringify(report, null, 2));
writeFileSync(join(OUT, "recording-inflated.json"), JSON.stringify(snapshotEvents, null, 1));
console.log(JSON.stringify(report, null, 2));
