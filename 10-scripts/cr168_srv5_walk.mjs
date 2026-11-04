// CR-168-BRC10 round 6, lane SRV-5 — the walk at 1440 on PostgreSQL:
//   raise a job for a customer who elected email and text, assign it → the
//   customer's BOOKED message queued; the technician sets off and closes it →
//   ON THE WAY; Dana accepts → DONE; a second job put on hold and a third
//   declined → the office's bell says so; print the order and R. Patel's day.
//
//   BASE=http://127.0.0.1:5209 OUT=08-qa/work-2026-10-04/after \
//   SETUP="<shell line running cr168_srv5_walk_setup.py with SRV5_ACT=…>" \
//   DISPATCH="<shell line running manage.py dispatch_outbound>" \
//   node 10-scripts/cr168_srv5_walk.mjs
//
// Preconditions: migrate + seed_demo + load_sample_data --tenant brazosbend on
// PostgreSQL 16, then `SRV5_ACT=prep` (prints the SRV5 JSON this reads from
// $PREP). WRITES IT MAKES: three jobs, their acts, one hold, one acceptance.
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5209";
const TENANT = "brazosbend";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
const PREP = JSON.parse(process.env.PREP);
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

const checks = [];
function check(name, ok, detail = "") {
  checks.push([name, ok]);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}
const run = (act, order = "") =>
  execSync(process.env.SETUP, {
    stdio: "pipe", env: { ...process.env, SRV5_ACT: act, SRV5_ORDER: order },
  }).toString();
const dispatch = () => execSync(process.env.DISPATCH, { stdio: "pipe" });

const browser = await chromium.launch({ executablePath: resolveChromium() });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
const sleep = (ms) => page.waitForTimeout(ms);
async function shot(name) {
  await sleep(1200);
  await page.screenshot({ path: join(OUT, `srv5-${name}.png`), fullPage: true });
  console.log("shot", name);
}
async function api(method, path, body) {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
      const r = await fetch(`/api/brazosbend${path}`, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: body ? JSON.stringify(body) : undefined,
      });
      return { status: r.status, data: await r.json().catch(() => null) };
    },
    { method, path, body },
  );
}
async function messages() {
  const r = await api("GET", "/outbound?per=100&source_type=appointment");
  return (r.data?.results ?? r.data?.rows ?? []);
}

// ── Dana signs in ─────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.OFFICE_PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 1 · raise a job on the customer's unit, and give it to R. Patel today ──
const today = new Date();
const at = (h) => {
  const d = new Date(today);
  d.setHours(h, 0, 0, 0);
  return d.toISOString();
};
async function raise(type) {
  const r = await api("POST", "/work-orders", {
    type, service: PREP.service, premises_id: PREP.premises_id, unit_id: PREP.unit_id,
  });
  if (r.status >= 300) throw new Error(`raise ${r.status} ${JSON.stringify(r.data)}`);
  return r.data;
}
const isBooked = (m) => ["service_appointment", "sms_visit_booked"].includes(m.template_code);
const bookedBefore = (await messages()).filter(isBooked).length;
const job = await raise("Meter exchange");
const assigned = await api("POST", `/work-orders/${job.id}/assignments`, {
  act: "assign", technician_id: PREP.patel, window_start: at(13), window_end: at(17),
});
check("assigning tells the customer the visit is booked", assigned.data?.customer_notice === "visit_message_queued",
  JSON.stringify(assigned.data?.customer_notice));
await page.goto(`${BASE}/${TENANT}/work/orders/${job.order_no}`, { waitUntil: "networkidle" });
await shot("01-order-raised-assigned-print-in-head");
check("the order's head carries Print", (await page.locator('[data-action="print"]').count()) === 1);

let rows = await messages();
const booked = rows.filter(isBooked).slice(0, rows.filter(isBooked).length - bookedBefore);
check("booked queued by email and text", booked.length === 2, booked.map((m) => m.channel).join(","));
await page.goto(`${BASE}/${TENANT}/settings/notifications/messages`, { waitUntil: "networkidle" });
await shot("02-customer-booked-message-queued");

// ── 2 · the technician sets off and closes it; Dana accepts ───────────────
console.log(run("field", job.order_no).trim().split("\n").pop());
rows = await messages();
check("on the way queued (text)", rows.some((m) => m.template_code === "sms_technician_on_the_way"));
await page.goto(`${BASE}/${TENANT}/work/orders/${job.order_no}`, { waitUntil: "networkidle" });
await shot("03-order-closed-in-field-accept");
await page.locator('[data-action="accept"]').click();
await sleep(600);
await page.getByRole("alertdialog").getByRole("button").last().click();
await sleep(2500);
await shot("04-order-accepted");
rows = await messages();
check("done queued (email) at acceptance", rows.some((m) => m.template_code === "service_work_completed"));
await page.goto(`${BASE}/${TENANT}/settings/notifications/messages`, { waitUntil: "networkidle" });
await shot("05-customer-messages-booked-on-the-way-done");

// ── 3 · the office: a job on hold, a job declined ─────────────────────────
const second = await raise("Leak investigation");
await api("POST", `/work-orders/${second.id}/assignments`, {
  act: "assign", technician_id: PREP.patel, window_start: at(9), window_end: at(11),
});
await page.goto(`${BASE}/${TENANT}/work/orders/${second.order_no}`, { waitUntil: "networkidle" });
await page.locator('[data-action="hold"]').click();
await sleep(800);
const reason = page.locator("#reason_code");
const options = await reason.locator("option").allTextContents();
await reason.selectOption({ index: Math.min(1, options.length - 1) });
await shot("06-hold-dialog");
await page.getByRole("dialog").getByRole("button", { name: /hold/i }).last().click();
await sleep(2000);
const third = await raise("Meter test");
await api("POST", `/work-orders/${third.id}/assignments`, {
  act: "assign", technician_id: PREP.chen, window_start: at(10), window_end: at(12),
});
console.log(run("decline", third.order_no).trim().split("\n").pop());
dispatch();
await page.goto(`${BASE}/${TENANT}/work/orders/${second.order_no}`, { waitUntil: "networkidle" });
await page.locator("details.shell-bell summary").click().catch(() => undefined);
await sleep(1000);
await shot("07-office-bell-on-hold-and-declined");
const bell = await page.locator("details.shell-bell").innerText().catch(() => "");
check("the bell says on hold", bell.includes(`${second.order_no}: on hold`), bell.slice(0, 200));
check("the bell says declined", bell.includes(`${third.order_no}: declined by the technician`));

// ── 4 · print the order, and R. Patel's day ────────────────────────────────
async function capturePdf(click, name) {
  const [popup] = await Promise.all([ctx.waitForEvent("page"), click()]);
  const url = popup.url();
  await popup.close();
  const bytes = await page.evaluate(async (u) => {
    const r = await fetch(u, { credentials: "include" });
    return { status: r.status, type: r.headers.get("content-type"), body: Array.from(new Uint8Array(await r.arrayBuffer())) };
  }, url);
  writeFileSync(join(OUT, `srv5-${name}.pdf`), Buffer.from(bytes.body));
  execSync(`pdftoppm -png -r 80 ${join(OUT, `srv5-${name}.pdf`)} ${join(OUT, `srv5-${name}-page`)}`);
  return { url, ...bytes };
}
await page.goto(`${BASE}/${TENANT}/work/orders/${job.order_no}`, { waitUntil: "networkidle" });
const order = await capturePdf(() => page.locator('[data-action="print"]').click(), "08-work-order");
check("Print opens the job's PDF", order.status === 200 && order.type === "application/pdf",
  `${order.url.replace(BASE, "")} ${order.status} ${order.type}`);

await page.goto(`${BASE}/${TENANT}/work/crews/r-patel`, { waitUntil: "networkidle" });
await shot("09-technician-print-day-in-head");
await page.locator('[data-action="print-day"]').click();
await sleep(800);
await shot("10-print-day-dialog");
const pack = await capturePdf(
  () => page.getByRole("dialog").getByRole("button", { name: /^Print$/ }).click(),
  "11-day-pack",
);
check("Print day opens R. Patel's day pack", pack.status === 200 && pack.type === "application/pdf",
  pack.url.replace(BASE, ""));

await browser.close();
const failed = checks.filter(([, ok]) => !ok).length;
console.log(`${checks.length - failed}/${checks.length} checks passed`);
process.exit(failed ? 1 : 0);
