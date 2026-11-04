// ── RATE SCHEDULE EDIT: SEASONAL PRICES COME BACK, EFFECTIVE FROM IS PROPOSED ──
// DEF-RAT-10148 · DEF-RAT-10149 · decision log 2026-10-14 (PO "go A").
//
// Walks, as a clerk, the Edit of a seasonal kW-DC schedule shaped like Ann
// Arbor's *Bryant Solar and Battery Service Pilot Rate* (Summer 1 Apr–30 Sep,
// Winter 1 Oct–31 Mar, two prices): opens Edit, reads step 2's prices, reads
// Review's prices and its proposed Effective from, saves the new version with
// nothing changed, then reads back from the API what the server stored — the
// new version's prices and start, and the previous version's end.
//
// NOT A GATE. Run against a PRIVATE database copy and private ports only:
//   WALK_BASE      default http://127.0.0.1:8094   (server.mjs → API on 8014)
//   WALK_TENANT    default brazosbend
//   WALK_EMAIL     default dana@brazosbendutilities.com
//   WALK_PASSWORD  default S3cure!passw0rd
//   WALK_SHOTS     default 05-prototype/rate-schedule-edit-2026-10-14
//   WALK_CHROME    default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.WALK_BASE || "http://127.0.0.1:8094";
const T = process.env.WALK_TENANT || "brazosbend";
const EMAIL = process.env.WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.WALK_PASSWORD || "S3cure!passw0rd";
const SHOTS = process.env.WALK_SHOTS || "05-prototype/rate-schedule-edit-2026-10-14";
const CHROME = process.env.WALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const results = [];
const verdict = (what, ok, saw) => {
  results.push({ what, ok });
  console.log(`${ok ? "PASS" : "FAIL"} · ${what}${ok ? "" : `\n     saw: ${saw}`}`);
};

const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

const api = async (method, path, body) =>
  page.evaluate(
    async ({ method, path, body }) => {
      const res = await fetch(`/api/${path}`, {
        method,
        credentials: "include",
        headers: body === undefined ? {} : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return { status: res.status, data: await res.json().catch(() => null) };
    },
    { method, path, body },
  );

// ── the schedule, created live (in force since 05/01/2026) ─────────────────
const charges = await api("GET", `${T}/charges?per=200&status=active`);
const base = (charges.data?.results ?? []).find((row) => row.is_base && row.service === "electric");
const name = `Bryant Solar and Battery Pilot (walk ${Date.now().toString().slice(-5)})`;
const created = await api("POST", `${T}/rate-schedules`, {
  name,
  service: "electric",
  model: "seasonal",
  uom: "kW-DC",
  base_charge_code: base?.id,
  structure: {
    seasons: [
      { label: "Summer", start_month: 4, start_day: 1, end_month: 9, end_day: 30, unit_price: "12.5" },
      { label: "Winter", start_month: 10, start_day: 1, end_month: 3, end_day: 31, unit_price: "9.75" },
    ],
  },
  effective_from: "2026-05-01",
  notify_customers: false,
  publish_public: false,
});
if (created.status >= 300) {
  console.log("could not create the schedule:", created.status, JSON.stringify(created.data).slice(0, 800));
  await browser.close();
  process.exit(1);
}
const id = created.data.id;
console.log(`created ${name} (${id}) — v1 from 2026-05-01, Summer 12.5, Winter 9.75`);

// ── the view, as the clerk sees it before Edit ─────────────────────────────
await page.goto(`${BASE}/${T}/plans-rates/rates/${id}`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${SHOTS}/1-view-rates.png`, fullPage: true });

// ── Edit → step 2 ──────────────────────────────────────────────────────────
await page.goto(`${BASE}/${T}/plans-rates/rates/${id}/edit`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-step="details"]');
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForSelector('[data-cell="season-price-0"]');
const summer = await page.inputValue('[data-cell="season-price-0"]');
const winter = await page.inputValue('[data-cell="season-price-1"]');
verdict("step 2 Price per kW-DC shows Summer 12.5000 and Winter 9.7500", summer === "12.5000" && winter === "9.7500", `${summer} / ${winter}`);
await page.screenshot({ path: `${SHOTS}/2-edit-step2-prices.png`, fullPage: true });

// ── Review ─────────────────────────────────────────────────────────────────
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForSelector('[data-step="review"]');
const usage = (await page.textContent('[data-usage-table="seasonal"]')) ?? "";
verdict("Review shows $12.50 and $9.75", usage.includes("$12.50") && usage.includes("$9.75"), usage);
const from = await page.inputValue("#rs-effective-from");
const to = await page.inputValue("#rs-effective-to");
const expectedFrom = (() => {
  const [y, m] = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago" }).format(new Date()).split("-").map(Number);
  return new Date(Date.UTC(y, m, 1)).toISOString().slice(0, 10);
})();
verdict(`Effective from proposed as ${expectedFrom}; Effective to blank`, from === expectedFrom && to === "", `${from} / ${to}`);
const changes = (await page.textContent("main")) ?? "";
verdict("What changes reads 0 changes", /0 changes/.test(changes), changes.slice(0, 200));
await page.screenshot({ path: `${SHOTS}/3-edit-review.png`, fullPage: true });

// ── save the new version with nothing changed ──────────────────────────────
await page.fill("#rs-what-changed", "Re-filed, same prices");
await page.getByRole("button", { name: "Create new version" }).click();
// "Nothing saved yet." also contains "saved", so wait for the outcome sentence itself.
await page.waitForFunction(() => /saved as new version/.test(document.querySelector("main")?.textContent ?? ""), null, { timeout: 30000 }).catch(() => undefined);
const outcome = (await page.textContent("main")) ?? "";
verdict("the save answers '… saved as new version.'", /saved as new version/.test(outcome), outcome.replace(/\s+/g, " ").slice(0, 300));
await page.screenshot({ path: `${SHOTS}/4-saved.png`, fullPage: true });

// ── read back what the server stored ───────────────────────────────────────
const after = await api("GET", `${T}/rate-schedules/${id}`);
const versions = after.data?.versions ?? [];
const next = versions.find((v) => v.effective_from === expectedFrom);
const prev = versions.find((v) => v.effective_from === "2026-05-01");
const priceOf = (v, label) => v?.structure?.tiers?.find((tier) => tier.season === label)?.unit_price;
verdict(
  "new version stores Summer 12.5 and Winter 9.75",
  Number(priceOf(next, "Summer")) === 12.5 && Number(priceOf(next, "Winter")) === 9.75,
  `${priceOf(next, "Summer")} / ${priceOf(next, "Winter")}`,
);
verdict(`new version starts ${expectedFrom} and is open-ended`, next?.effective_from === expectedFrom && next?.effective_to === null, JSON.stringify(next?.effective_from) + " → " + JSON.stringify(next?.effective_to));
const dayBefore = new Date(`${expectedFrom}T00:00:00Z`);
dayBefore.setUTCDate(dayBefore.getUTCDate() - 1);
const expectedEnd = dayBefore.toISOString().slice(0, 10);
verdict(`previous version now ends ${expectedEnd}`, prev?.effective_to === expectedEnd, JSON.stringify(prev?.effective_to));

await page.goto(`${BASE}/${T}/plans-rates/rates/${id}`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${SHOTS}/5-view-after.png`, fullPage: true });

verdict("no page errors", errors.length === 0, errors.join(" | "));
await browser.close();
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} PASS`);
process.exit(failed === 0 ? 0 : 1);
