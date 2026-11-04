// CR-168-BRC10 round 9, lane FIN-T — P3.42 walked at 1440 on PostgreSQL 16
// (`sbh_wfint`: migrate + seed_demo + load_sample_data --tenant brazosbend).
//
//   BASE=http://127.0.0.1:5227 OUT=08-qa/work-2026-10-04/final node 10-scripts/cr168_fint_preselection_walk.mjs
//
// WRITES IT MAKES: one Work rule on *A customer moves out* (Final read, High,
// D. Ortiz), one on *A new connection is built*, and — at the end — one
// move-out saved, so the raised job can be read back. Prints PASS/FAIL.
import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");
function resolveChromium() {
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) { if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) { const c = join(root, dir, sub); if (existsSync(c)) return c; } }
  }
  throw new Error("no chromium");
}
const BASE = process.env.BASE ?? "http://127.0.0.1:5227", TENANT = "brazosbend";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/final";
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
const api = (p, m = "GET", b) => page.evaluate(async ([t, p, m, b]) => {
  const r = await fetch(`/api/${t}/${p}`, { method: m, credentials: "include", headers: b ? { "Content-Type": "application/json" } : {}, body: b ? JSON.stringify(b) : undefined });
  let j = null; try { j = await r.json(); } catch {} return { status: r.status, body: j }; }, [TENANT, p, m, b]);

const settle = (ms = 1200) => page.waitForTimeout(ms);
function check(name, ok, detail = "") { console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`); }
async function shot(name) { await settle(600); await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false }); console.log(`=== ${name}.png — ${page.url().replace(BASE, "")}`); }

if (process.env.SKIP_MOVEOUT !== "1") {
const opts0 = await api("work/raise-options");
const high = opts0.body.priorities.find((p) => p.code === "HIGH");
const templates = await api("work/templates?per=50");
const finalRead = templates.body.results.find((t) => t.name === "Final read");
const crews = await api("work/crews?per=20");
const ortiz = crews.body.results.find((c) => c.name === "D. Ortiz");
const made = await api("work/rules", "POST", {
  name: "Final read on move-out",
  triggers: [{ kind: "move_out", params: {} }],
  template_id: finalRead.id,
  priority_id: high.id,
  assign_to: { kind: "technician", id: ortiz.id },
});
check("a supervisor's rule on A customer moves out is saved", made.status === 201 || made.status === 200, String(made.status));
const opts = await api("work/raise-options");
const row = (opts.body.preselected?.move_out ?? [])[0];
check("raise-options serves the rule's row for move_out", row?.rule?.name === "Final read on move-out" && row.priority_id === high.id, JSON.stringify(row));

const accts = await api("accounts?per=50&q=AC-2026-00044");
const account = accts.body.results.find((a) => a.account_no === "AC-2026-00044");
await page.goto(`${BASE}/${TENANT}/accounts/${account.id}/move-out`, { waitUntil: "networkidle" });
await settle(2500);
await page.getByRole("button", { name: /^Continue/ }).click();
await settle(2500);
const dialog = page.getByRole("dialog");
const text = await dialog.innerText();
check("step 2 of the move-out opens with the rule's row", text.includes("By rule: Final read on move-out"), text.slice(0, 200).replace(/\n/g, " | "));
const table = page.locator('[data-field-visit="move_out"]');
await table.scrollIntoViewIfNeeded().catch(() => undefined);
const values = await table.evaluate((el) => [...el.querySelectorAll("select")].map((s) => s.selectedOptions[0]?.textContent ?? ""));
check("the row carries Re-read, High and D. Ortiz", values.join("|").includes("Re-read") && values.includes("High") && values.includes("D. Ortiz"), JSON.stringify(values));
await shot("fint-02-move-out-step2-rule-row");

// ── save it, and read the job back ──────────────────────────────────────────
await dialog.locator('input[type="date"]').first().fill("2026-10-05");
await dialog.getByLabel(/^Reason/).selectOption({ label: "Lease ended" });
const readDates = dialog.getByPlaceholder("MM/DD/YYYY");
for (let i = 0; i < 2; i += 1) await readDates.nth(i).fill("10/05/2026");
for (const step of [3, 4]) {
  await page.getByRole("button", { name: /^Continue/ }).click();
  await settle(2500);
  const now = await dialog.innerText();
  console.log(`--- after Continue (wanted step ${step}):`, now.slice(0, 160).replace(/\n/g, " | "));
  const alerts = await dialog.locator('[role="alert"]').allInnerTexts();
  if (alerts.length) console.log("alerts:", JSON.stringify(alerts));
}
await shot("fint-03-move-out-review");
const commit = dialog.getByRole("button", { name: /Complete move-out/ }).last();
console.log("commit button:", await commit.innerText().catch(() => "none"));
await commit.click();
await settle(4000);
await shot("fint-04-move-out-done");
const done = await page.locator("body").innerText();
const orderNo = (done.match(/WO-\d{4}/) ?? [null])[0];
console.log("raised:", orderNo);
if (orderNo) {
  const list = await api(`work-orders?q=${orderNo}`);
  const job = (list.body.results ?? []).find((r) => r.order_no === orderNo);
  const detail = job ? await api(`work-orders/${job.id}`) : { body: null };
  const d = detail.body ?? {};
  console.log(JSON.stringify({ source: d.source, rule: d.rule ?? d.rule_id ?? d.raised_by, priority: d.priority?.code, tech: d.technician?.name, type: d.type }));
  check("the saved move-out raised the rule's job, High, with D. Ortiz", d.priority?.code === "HIGH" && (d.technician?.name ?? "") === "D. Ortiz", orderNo);
}
}

// ── the new connection: step 3 arrives on the rule's job ───────────────────
const nc = await api("work/rules", "POST", {
  name: "Survey every build",
  triggers: [{ kind: "new_connect", params: {} }],
  template_id: (await api("work/templates?per=50")).body.results.find((t) => t.name === "Service drop").id,
});
check("a rule on A new connection is built is saved", nc.status === 201, String(nc.status));
const offer = await api("connections/proposed-work-orders?services=electric");
const ticked = (offer.body.proposed ?? []).filter((r) => r.preselected_by);
check("step 3's proposals mark the rule's job", ticked.length === 1 && ticked[0].preselected_by.name === "Survey every build", JSON.stringify(ticked.map((r) => [r.name, r.preselected_by])));
const water = await api("connections/proposed-work-orders?services=water");
check("a water-only build is not offered the electric rule's job", !(water.body.proposed ?? []).some((r) => r.preselected_by), "");

// ── the job the move-out raised, on its own page ───────────────────────────
const jobs = await api("work-orders?per=200");
const raised = (jobs.body.results ?? []).filter((r) => r.source === "move_out").pop();
if (raised) {
  await page.goto(`${BASE}/${TENANT}/work/orders/${raised.id}`, { waitUntil: "networkidle" });
  await settle(2500);
  const body = await page.locator("main").innerText();
  check("the raised job reads its priority and holder", /High/.test(body) && /D\. Ortiz/.test(body), raised.order_no);
  await shot("fint-05-raised-job-names-the-rule");
  const rule = (await api("work/rules?q=Final%20read%20on%20move-out")).body.results?.[0];
  const ruleJobs = rule ? await api(`work/rules/${rule.id}/jobs`) : { body: {} };
  check("the rule's Jobs tab lists the job it put on the screen", (ruleJobs.body.results ?? []).some((j) => j.order_no === raised.order_no), raised.order_no);
}
await browser.close();
