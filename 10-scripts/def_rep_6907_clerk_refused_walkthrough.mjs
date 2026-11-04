/**
 * DEF-REP-6907 + DEF-REP-6913's constraint, walked as the person it is about.
 *
 * Sam Reyes is a Billing Clerk. `access_review` carries min_role=executive, so
 * the server refuses it — 403 AUTH-002 reports.viewer.role_refused. Before this
 * fix the viewer replaced that with a fixed helper claiming the clerk cannot
 * run reports AT ALL, which is false: step 1 counts the cards he DOES get.
 */
import { chromium } from "playwright";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
const BASE = process.env.BASE ?? "http://127.0.0.1:8087";
const T = "brazosbend";
const OUT = "/home/user/SMARTBillHub/scratchpad/po-shots/schedule-door";
function chrome() {
  const w = chromium.executablePath();
  if (w && existsSync(w)) return w;
  for (const r of ["/opt/pw-browsers"]) for (const d of readdirSync(r)) {
    const c = join(r, d, "chrome-linux", "chrome"); if (existsSync(c)) return c;
  }
  throw new Error("no chromium");
}
let fail = 0;
const ok = (c, m) => { console.log(`${c ? "  PASS" : "  FAIL"} · ${m}`); if (!c) fail++; };
const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });
try {
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await p.fill("#signin-email", "sam.reyes@sample.test");
  await p.fill("#signin-password", "S3cure!passw0rd");
  await p.click('button[type="submit"]');
  await p.waitForTimeout(3500);

  console.log("── 1 · THE CLERK RUNS REPORTS, WHICH IS WHY THE OLD SENTENCE WAS FALSE");
  await p.goto(`${BASE}/${T}/reports`, { waitUntil: "networkidle" });
  await p.waitForTimeout(3000);
  await p.screenshot({ path: `${OUT}/08-clerk-catalogue-1440.png`, fullPage: false });
  const cards = await p.evaluate(() => document.querySelectorAll('[data-report-card], .report-card, a[href*="/reports/"]').length);
  console.log(`  report links the clerk is served: ${cards}`);
  ok(cards > 5, "the clerk is served many reports — 'cannot run reports' was false on its face");

  console.log("\n── 2 · THE ONE HE MAY NOT RUN NAMES ITSELF, AND OFFERS NO DOOR");
  await p.goto(`${BASE}/${T}/reports/access-review`, { waitUntil: "networkidle" });
  await p.waitForTimeout(4000);
  await p.screenshot({ path: `${OUT}/09-clerk-refused-1440-server-sentence.png`, fullPage: false });
  const s = await p.evaluate(() => ({
    body: document.body.innerText,
    schedule: [...document.querySelectorAll(".page-header-actions button")].map((e) => e.textContent.trim()),
  }));
  console.log(`  on screen: ${JSON.stringify(s.body.replace(/\s+/g, " ").slice(0, 180))}`);
  console.log(`  header actions: ${JSON.stringify(s.schedule)}`);
  ok(/Your role cannot run this report\./.test(s.body), "the SERVER's six-word sentence is shown");
  ok(!/cannot run reports/.test(s.body), "the FALSE module-wide sentence is GONE");
  ok(!/Ask a System Admin/.test(s.body), "and its rationale clause with it (B14 rule 33)");
  ok(!s.schedule.includes("Schedule"), "no Schedule door is offered over a refusal");
} finally {
  console.log(`\n${fail === 0 ? "WALK GREEN" : `WALK RED — ${fail} failed`}`);
  await b.close();
  process.exit(fail === 0 ? 0 : 1);
}
