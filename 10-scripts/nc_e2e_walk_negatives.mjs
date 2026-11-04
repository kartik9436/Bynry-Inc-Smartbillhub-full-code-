#!/usr/bin/env node
// ── nc_e2e_walk_negatives.mjs ───────────────────────────────────────────────
//
// THE NEW CONNECTION END-TO-END WEB WALK, stage 14 — the two refusals the plan
// names, in a real Chromium against a real PostgreSQL 16:
//
//   14a  a role that may LOOK but not ACT (Executive): the request opens, and
//        every write the screen offers is refused by the server (403), whether
//        the button is pressed or the API is called directly.
//   14b  ANOTHER UTILITY's clerk (Dana, brazosbend): the request's address
//        under her own utility, under the walk utility's, and its record read,
//        all answer "not found" — never a different answer that would let an
//        id be probed (HR-1). Writes from her are refused the same way.
//
//   NCW_CID=<a walk build id, not yet approved> NCW_OUT=<dir> \
//     node 10-scripts/nc_e2e_walk_negatives.mjs
//
// The two users must be able to sign in (the walk's own setup gives the sample
// Executive a password; Dana is the second tenant's owner).
import { existsSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.NCW_BASE ?? "http://127.0.0.1:8992").replace(/\/$/, "");
const API = (process.env.NCW_API ?? "http://127.0.0.1:8991").replace(/\/$/, "");
const TENANT = process.env.NCW_TENANT ?? "lakeside";
const OTHER = process.env.NCW_OTHER_TENANT ?? "brazosbend";
const PASSWORD = process.env.NCW_PASSWORD ?? "S3cure!passw0rd";
const EXEC = process.env.NCW_EXEC_EMAIL ?? "avery.cole@sample.test";
const DANA = process.env.NCW_OTHER_EMAIL ?? "dana@brazosbendutilities.com";
const OUT = process.env.NCW_OUT ?? "/tmp/nce2e";
const CID = process.env.NCW_CID;
if (!CID) throw new Error("NCW_CID is required");

const results = [];
const record = (verdict, stage, label, evidence = "") => {
  results.push({ verdict, stage, label, evidence: String(evidence).slice(0, 1200) });
  console.log(`${verdict.padEnd(5)} [${stage}] ${label}${evidence === "" ? "" : ` — ${String(evidence).slice(0, 300)}`}`);
};
const check = (stage, label, ok, evidence = "") => record(ok ? "PASS" : "FAIL", stage, label, evidence);
const note = (stage, label, evidence = "") => record("NOTE", stage, label, evidence);

function resolveChromium() {
  const pinned = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  if (existsSync(pinned)) return pinned;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    const c = join("/opt/pw-browsers", dir, "chrome-linux", "chrome");
    if (existsSync(c)) return c;
  }
  throw new Error("no chromium");
}
const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });

async function session(tenant, email) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }).catch(() => undefined);
  const r = await page.request.post(`${API}/api/${tenant}/auth/session`, { data: { email, password: PASSWORD } });
  return { context, page, signedIn: r.status() < 300, status: r.status() };
}
async function shoot(page, name) {
  const file = join(OUT, `nce2e_NEG_${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  const size = statSync(file).size;
  console.log(`      shot ${file} ${size} bytes`);
  if (size < 15000) record("FAIL", "14", "screenshot looks blank", `${name} ${size} bytes`);
}
const text = async (page) => (await page.locator("body").innerText().catch(() => "")).replace(/\s+/g, " ");
async function call(page, method, url, data) {
  const r = await page.request.fetch(url, { method, data, failOnStatusCode: false });
  let body = "";
  try {
    body = (await r.text()).slice(0, 300);
  } catch {
    body = "";
  }
  return { status: r.status(), body };
}

// ════ 14a · the Executive ═══════════════════════════════════════════════════
{
  const { context, page, signedIn, status } = await session(TENANT, EXEC);
  check("14a", "the Executive can sign in", signedIn, status);
  await page.goto(`${BASE}/${TENANT}/connections/${CID}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const body = await text(page);
  check("14a", "the request opens for reading", /CON-\d\d-\d{4}/.test(body), body.match(/CON-\d\d-\d{4}.{0,80}/)?.[0]);
  const approve = page.locator("button", { hasText: /^Approve$/ }).first();
  const shown = (await approve.count()) > 0;
  const disabled = shown ? await approve.isDisabled() : null;
  note("14a", "Approve as the Executive", shown ? `shown, disabled=${disabled}, title=${await approve.getAttribute("title")}` : "not shown");
  if (shown && !disabled) {
    const wait = page.waitForResponse((r) => r.url().includes("/activate"), { timeout: 15000 }).catch(() => null);
    await approve.click();
    await page.waitForTimeout(1200);
    const go = page.locator(".modal-foot button").last();
    if ((await go.count()) > 0 && !(await go.isDisabled())) await go.click();
    const resp = await wait;
    await page.waitForTimeout(1500);
    const said = (await page.locator('.modal, [role="dialog"], [role="alert"]').first().innerText().catch(() => "")).replace(/\s+/g, " ");
    check("14a", "pressing Approve is refused by the server", resp === null || resp.status() === 403, `${resp === null ? "no request" : resp.status()} · screen: ${said.slice(0, 300)}`);
  }
  await shoot(page, "14a_executive_request");
  const writes = [
    ["POST", `/connections/${CID}/activate`, { service_ids: [], acknowledge_open_orders: true }],
    ["POST", `/connections/${CID}/hold`, { reason: "walk probe" }],
    ["POST", `/connections/${CID}/fees`, { charge_code: "INSPECT", quantity: "1", basis: "per premise", posting_date: "2026-10-03", due_days: 30 }],
    ["POST", `/connections/${CID}/units`, { label: "X", unit_type: "residential", services: ["water"] }],
    ["POST", `/connections/${CID}/messages/build_created/send`, { channel: "email", recipient: "owner" }],
    ["POST", "/connections/commit", {}],
  ];
  for (const [method, path, data] of writes) {
    const r = await call(page, method, `${API}/api/${TENANT}${path}`, data);
    check("14a", `Executive ${method} ${path.replace(CID, "{id}")} is refused`, r.status === 403, `${r.status} ${r.body}`);
  }
  const read = await call(page, "GET", `${API}/api/${TENANT}/connections/${CID}/record`);
  note("14a", "Executive reads the record", read.status);
  await context.close();
}

// ════ 14b · another utility's clerk ═════════════════════════════════════════
{
  const { context, page, signedIn, status } = await session(OTHER, DANA);
  check("14b", "the other utility's clerk can sign in to her own utility", signedIn, status);
  await page.goto(`${BASE}/${OTHER}/connections/${CID}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const own = await text(page);
  check("14b", "the walk's request does not open under her utility", !/Harbor Point|Delgado|Whitlock|Reyes|St\. Brendan|City of Lakeside/.test(own), own.slice(0, 300));
  await shoot(page, "14b_other_tenant_own_address");
  await page.goto(`${BASE}/${TENANT}/connections/${CID}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const theirs = await text(page);
  check("14b", "the walk utility's address does not show her the request", !/Harbor Point|Delgado|Whitlock|Reyes|St\. Brendan|City of Lakeside/.test(theirs), theirs.slice(0, 300));
  // DEF-SHL-9241 — she lands on THAT utility's sign-in, not a dead Retry.
  const landed = new URL(page.url()).pathname;
  check("14b", "the walk utility's address sends her to its sign-in", landed === `/${TENANT}/signin`, `${landed} · ${theirs.slice(0, 120)}`);
  await shoot(page, "14b_other_tenant_walk_address");
  const probes = [
    ["GET", `${API}/api/${OTHER}/connections/${CID}`],
    ["GET", `${API}/api/${OTHER}/connections/${CID}/record`],
    ["GET", `${API}/api/${TENANT}/connections/${CID}`],
    ["POST", `${API}/api/${OTHER}/connections/${CID}/hold`, { reason: "probe" }],
    ["POST", `${API}/api/${OTHER}/connections/${CID}/fees`, { charge_code: "INSPECT", quantity: "1", basis: "per premise", posting_date: "2026-10-03", due_days: 30 }],
  ];
  for (const [method, url, data] of probes) {
    const r = await call(page, method, url, data);
    const refused = r.status === 404 || r.status === 403 || r.status === 401;
    check("14b", `${method} ${url.replace(API, "").replace(CID, "{id}")} answers not found / refused`, refused, `${r.status} ${r.body}`);
  }
  const list = await call(page, "GET", `${API}/api/${OTHER}/connections?search=CON-26`);
  check("14b", "her own list holds none of the walk's builds", !list.body.includes(CID), list.body.slice(0, 200));
  await context.close();
}

await browser.close();
writeFileSync(join(OUT, "nce2e_NEG_RESULTS.json"), JSON.stringify({ cid: CID, results }, null, 2));
console.log(`── stage 14: ${results.length} checks, ${results.filter((r) => r.verdict === "FAIL").length} FAIL`);
