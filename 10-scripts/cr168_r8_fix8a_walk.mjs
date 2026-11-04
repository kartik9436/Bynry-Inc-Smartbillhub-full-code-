// CR-168-BRC10 round 8, lane FIX-8A — DEF-WRK-9688 walked at 1440 on PostgreSQL 16
// after `cr168_r8_fix8a_walk_prep.py prepare` (which prints ORDER, its id and TECH).
//
//   BASE=http://127.0.0.1:5223 OUT=<dir> ORDER=WO-0016 ORDER_ID=<uuid> TECH=<uuid> \
//   TECH_PASSWORD='…' node 10-scripts/cr168_r8_fix8a_walk.mjs
//
// WRITES IT MAKES: one Save on ORDER's edit page — R. Patel, 6 Oct, Morning —
// sent exactly as the page sends it (`patchOf`: naive clock times). Then reads:
// the edit page reopened, the order page, and R. Patel's Week in the field app.
// Prints PASS/FAIL per check.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5223";
const TENANT = "brazosbend";
const OUT = process.env.OUT ?? "/tmp/fix8a";
const ORDER = process.env.ORDER;
const ORDER_ID = process.env.ORDER_ID;
const TECH = process.env.TECH;
const TECH_PASSWORD = process.env.TECH_PASSWORD;
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
function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
// ⚠ THE BROWSER IS PUT IN UTC ON PURPOSE — the zone every earlier walk read the
// window back in, and the one in which the bug looked correct.
const office = await browser.newContext({ viewport: { width: 1440, height: 1000 }, timezoneId: "UTC" });
const page = await office.newPage();
const settle = (p, ms = 1200) => p.waitForTimeout(ms);
async function shot(p, name) {
  await settle(p, 600);
  await p.screenshot({ path: `${OUT}/${name}.png` });
  console.log(`=== ${name}.png — ${p.url().replace(BASE, "")}`);
}
async function api(p, path, method = "GET", body) {
  return p.evaluate(async ([t, path_, m, b]) => {
    const r = await fetch(`/api/${t}/${path_}`, { method: m, credentials: "include",
      headers: b ? { "Content-Type": "application/json" } : {}, body: b ? JSON.stringify(b) : undefined });
    let json = null; try { json = await r.json(); } catch { /* not JSON */ }
    return { status: r.status, body: json };
  }, [TENANT, path, method, body]);
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// 1 · Dana books 08:00–12:00 on 6 Oct for R. Patel — the page's own patch.
const saved = await api(page, `work-orders/${ORDER_ID}`, "PATCH", {
  technician_id: TECH,
  due_at: "2026-10-06T00:00:00",
  window_start: "2026-10-06T08:00:00",
  window_end: "2026-10-06T12:00:00",
});
check("the Save is accepted", saved.status === 200, `HTTP ${saved.status}`);

const form = await api(page, `work-orders/${ORDER_ID}/edit`);
check(
  "the server reads the booking back as 08:00–12:00 on 6 Oct, Central",
  form.body?.appointment?.start === "08:00" && form.body?.appointment?.end === "12:00",
  JSON.stringify(form.body?.appointment),
);
check(
  "stored as 13:00Z–17:00Z",
  String(form.body?.window_start).startsWith("2026-10-06T13:00:00") &&
    String(form.body?.window_end).startsWith("2026-10-06T17:00:00"),
  `${form.body?.window_start} → ${form.body?.window_end}`,
);

// 2 · The edit page reopens on Morning, in a UTC browser.
await page.goto(`${BASE}/${TENANT}/work/orders/${ORDER_ID}/edit`, { waitUntil: "networkidle" });
await settle(page, 2000);
const editText = await page.locator("main").innerText();
check("the edit page names the morning window", /08:00/.test(editText) && /12:00/.test(editText));
await shot(page, "fix8a-01-edit-reopens-morning-utc-browser");

// 3 · The order page.
await page.goto(`${BASE}/${TENANT}/work/orders/${ORDER}`, { waitUntil: "networkidle" });
await settle(page, 2000);
const orderText = await page.locator("main").innerText();
check("the order page reads 08:00–12:00", /08:00–12:00/.test(orderText), (orderText.match(/\d{2}:\d{2}–\d{2}:\d{2}/g) ?? []).join(", "));
check("…and not 03:00–07:00", !/03:00–07:00/.test(orderText));
await shot(page, "fix8a-02-order-page-0800-1200");

// 4 · R. Patel's Week on the field app.
const field = await browser.newContext({ viewport: { width: 1440, height: 1000 }, timezoneId: "UTC" });
const phone = await field.newPage();
await phone.goto(`${BASE}/${TENANT}/work/mobile/signin`, { waitUntil: "networkidle" });
await phone.fill("#signin-email", "r.patel@sample.test");
await phone.fill("#signin-password", TECH_PASSWORD);
await phone.click('button[type="submit"]');
await phone.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
const week = await api(phone, "work/mobile/today?days=7");
const card = (week.body?.jobs ?? []).find((job) => job.order_no === ORDER);
check(
  "the technician's day carries 08:00–12:00",
  card?.appointment?.start === "08:00" && card?.appointment?.end === "12:00",
  JSON.stringify(card?.appointment),
);
const unscheduled = (week.body?.jobs ?? []).filter((job) => job.unscheduled).map((job) => job.order_no);
console.log(`unscheduled on R. Patel's week: ${unscheduled.join(", ") || "none"}`);
await phone.goto(`${BASE}/${TENANT}/work/mobile/week`, { waitUntil: "networkidle" }).catch(() => undefined);
await settle(phone, 2500);
const phoneText = await phone.locator("body").innerText();
check("the phone card reads 08:00–12:00", phoneText.includes("08:00–12:00"));
await shot(phone, "fix8a-03-technician-week-0800-1200");

await browser.close();
