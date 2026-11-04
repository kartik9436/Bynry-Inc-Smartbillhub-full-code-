// CR-168-BRC10 round 6, lane FIX-7 — the walk at 1440 on PostgreSQL 16:
//   1 · DEF-NOT-9668 — Silver Creek Sample Millworks chose texts; a job on their
//       unit is assigned → the BOOKED text is addressed to the phone on their
//       account (+1 (402) 555-1049), not "Address not looked up".
//   2 · DEF-NOT-9667 — Messages needing attention fits its card at 1440.
//   3 · DEF-WRK-9672 — a crew's row offers Print day…; it opens that crew's
//       day pack.
//   4 · DEF-WRK-9671 — a job the certification rule raised on a meter in the
//       warehouse reads the meter's stored-at note, or a dash.
//
//   BASE=http://127.0.0.1:5215 OUT=08-qa/work-2026-10-04/after \
//   SETUP="<shell line running cr168_srv5_walk_setup.py with SRV5_ACT=…>" \
//   PSQL="psql -h 127.0.0.1 -p 55433 -U postgres -d <db> -At -c" \
//   NOTED=WO-0041 BARE=WO-0042 RULE=<rule uuid> \
//   node 10-scripts/cr168_fix7_walk.mjs
//
// Preconditions: migrate + seed_demo + load_sample_data --tenant brazosbend,
// then the Asset age rule swept once (it raises NOTED and BARE on AST-04412/13,
// meters in the warehouse). WRITES IT MAKES: Millworks elects email and text
// (SRV-5's prep), one job raised and assigned, AST-04412's location note.
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5215";
const TENANT = "brazosbend";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
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

const prepLine = execSync(process.env.SETUP, { stdio: "pipe", env: { ...process.env, SRV5_ACT: "prep" } })
  .toString()
  .split("\n")
  .find((line) => line.startsWith("SRV5 "));
const PREP = JSON.parse(prepLine.slice(5));
execSync(`${process.env.PSQL} "update assets set location_note='Warehouse bay 3' where asset_no='AST-04412'"`);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
const sleep = (ms) => page.waitForTimeout(ms);
async function shot(name) {
  await sleep(1200);
  await page.screenshot({ path: join(OUT, `fix7-${name}.png`), fullPage: true });
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

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.OFFICE_PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 1 · DEF-NOT-9668 — the booked text goes to the customer's phone ────────
const today = new Date();
const at = (h) => {
  const d = new Date(today);
  d.setHours(h, 0, 0, 0);
  return d.toISOString();
};
const raised = await api("POST", "/work-orders", {
  type: "Meter exchange", service: PREP.service, premises_id: PREP.premises_id, unit_id: PREP.unit_id,
});
if (raised.status >= 300) throw new Error(`raise ${raised.status} ${JSON.stringify(raised.data)}`);
const assigned = await api("POST", `/work-orders/${raised.data.id}/assignments`, {
  act: "assign", technician_id: PREP.patel, window_start: at(13), window_end: at(17),
});
check("assigning queues the booked message", assigned.data?.customer_notice === "visit_message_queued",
  JSON.stringify(assigned.data?.customer_notice));
const listed = await api("GET", "/outbound?per=200&source_type=appointment");
const texts = (listed.data?.results ?? listed.data?.rows ?? []).filter(
  (m) => m.channel === "sms" && m.template_code === "sms_visit_booked",
);
const latest = texts[texts.length - 1] ?? texts[0];
check("the booked text is addressed to the customer's phone",
  texts.some((m) => m.recipient_address === "+1 (402) 555-1049"),
  JSON.stringify(texts.map((m) => [m.recipient_address, m.unavailable_reason])));
writeFileSync(join(OUT, "fix7-01-booked-text-row.json"), JSON.stringify(latest ?? null, null, 2));

// ── 2 · DEF-NOT-9667 — the table fits its card at 1440 ─────────────────────
await page.goto(`${BASE}/${TENANT}/settings/notifications/messages`, { waitUntil: "networkidle" });
await shot("02-messages-needing-attention-fits-1440");
const fit = await page.evaluate(() => {
  const table = document.querySelector("table.data-table");
  const box = table.parentElement;
  return { table: Math.round(table.getBoundingClientRect().width), box: box.clientWidth, scroll: box.scrollWidth };
});
check("the queue table is no wider than its card", fit.scroll <= fit.box, JSON.stringify(fit));

// ── 3 · DEF-WRK-9672 — Print day… on a crew ───────────────────────────────
await page.goto(`${BASE}/${TENANT}/work/crews?view=crews`, { waitUntil: "networkidle" });
await shot("03-crews-print-day-on-each-row");
const crewRow = page.locator("tr", { hasText: "Field crew A" }).first();
await crewRow.getByRole("button", { name: "Print day…" }).click();
await sleep(800);
await shot("04-crew-print-day-dialog");
const [popup] = await Promise.all([
  ctx.waitForEvent("page"),
  page.getByRole("dialog").getByRole("button", { name: /^Print$/ }).click(),
]);
const packUrl = popup.url();
await popup.close();
const pack = await page.evaluate(async (u) => {
  const r = await fetch(u, { credentials: "include" });
  return { status: r.status, type: r.headers.get("content-type"), body: Array.from(new Uint8Array(await r.arrayBuffer())) };
}, packUrl);
writeFileSync(join(OUT, "fix7-05-crew-day-pack.pdf"), Buffer.from(pack.body));
execSync(`pdftoppm -png -r 80 -f 1 -l 1 ${join(OUT, "fix7-05-crew-day-pack.pdf")} ${join(OUT, "fix7-05-crew-day-pack-page")}`);
check("Print day opens the crew's day pack", pack.status === 200 && pack.type === "application/pdf" && packUrl.includes("crew=field-crew-a"),
  packUrl.replace(BASE, ""));

// ── 4 · DEF-WRK-9671 — a warehouse meter's job says where it is ───────────
await page.goto(`${BASE}/${TENANT}/work/orders/${process.env.NOTED}`, { waitUntil: "networkidle" });
await shot("06-warehouse-job-stored-at");
check("the order page names where the meter is stored",
  (await page.getByText("Warehouse bay 3").count()) > 0);
await page.goto(`${BASE}/${TENANT}/work/rules/${process.env.RULE}?tab=jobs`, { waitUntil: "networkidle" });
await shot("07-rule-jobs-stored-at-or-dash");
const cells = await page.locator("tbody tr").allInnerTexts();
check("the rule's Jobs tab reads the note for one job and a dash for the other",
  cells.some((r) => r.includes(process.env.NOTED) && r.includes("Warehouse bay 3"))
    && cells.some((r) => r.includes(process.env.BARE) && r.includes("—")),
  JSON.stringify(cells.slice(0, 3)));

await browser.close();
const failed = checks.filter(([, ok]) => !ok).length;
console.log(`${checks.length - failed}/${checks.length} checks passed`);
process.exit(failed ? 1 : 0);
