// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-WRK-9583 (critical, CR-168-BRC10 round 2, lane IDN-FIX) — a
//          field technician can never sign in. This walk is the browser
//          proof of the fix, at 1440, against the running product.
// ───────────────────────────────────────────────────────
//
// Expects the API on a scratch PostgreSQL 16 database (`migrate` + `seed_demo`
// + `load_sample_data --tenant brazosbend`) and the SPA built by `vite build`
// served by `07-frontend/server.mjs` (API_PROXY_TARGET at the API).
//
//   BASE=http://127.0.0.1:5431 OUT=08-qa/work-2026-10-04/idn-fix \
//     node 10-scripts/def_wrk_9583_field_signin_walk.mjs
//
// Writes to the database only what an administrator's own press writes: ONE
// temporary password for the demo's field technician (as the beta tester did),
// then that technician's own password change.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5431";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/idn-fix";
const NEW_PASSWORD = "N3w!Technician#2026";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
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

const T = (p) => `${BASE}/${TENANT}${p}`;
const say = (...parts) => console.log(...parts);
const browser = await chromium.launch({ executablePath: resolveChromium() });

async function fresh() {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  const posts = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/auth/session")) posts.push(r.postData() ?? "");
  });
  const answers = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.request().method() !== "GET") answers.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
  });
  return { ctx, page, posts, answers };
}

async function shot(page, name, caption) {
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`\n=== ${name}.png — ${caption} — ${page.url().replace(BASE, "")}`);
  say((await page.locator("body").innerText()).replace(/\n{2,}/g, "\n").slice(0, 500));
}

async function signIn(page, email, password) {
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
}

// ── 0 · the administrator issues the technician a temporary password ──────
const admin = await fresh();
await admin.page.goto(T("/signin"), { waitUntil: "networkidle" });
await signIn(admin.page, EMAIL, PASSWORD);
const api = (method, path, body) =>
  admin.page.evaluate(
    async ([m, p, b]) => {
      const res = await fetch(`/api/${p}`, {
        method: m, credentials: "include", headers: { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      let data = null;
      try { data = await res.json(); } catch { data = null; }
      return { status: res.status, data };
    },
    [method, `${TENANT}/${path}`, body],
  );
const users = await api("GET", "users?per=100");
const rows = users.data?.results ?? users.data ?? [];
const tech = rows.find((u) => u.role_code === "field_technician" || /technician/i.test(u.role ?? ""));
const clerk = rows.find((u) => u.role_code === "billing_clerk" || /clerk/i.test(u.role ?? ""));
say("TECH:", tech?.email, "· CLERK:", clerk?.email);
const tp = await api("POST", `users/${tech.id ?? tech.user_id}/temp-password`, {});
say("TEMP PASSWORD:", tp.status, tp.data?.temp_password ? "(issued)" : JSON.stringify(tp.data).slice(0, 200));
const temp = tp.data.temp_password;

// ── 1 · the technician on the OFFICE sign-in: named, with the field app's door ─
{
  const { ctx, page, posts } = await fresh();
  await page.goto(T("/signin"), { waitUntil: "networkidle" });
  await signIn(page, tech.email, temp);
  say("POSTED:", posts.map((p) => JSON.parse(p).surface));
  await shot(page, "idn1-technician-on-office-signin", "a technician on the office sign-in — the wrong door is named");
  // ── 2 · a wrong password on the same form: still the one generic line ──
  await signIn(page, tech.email, "not-the-password");
  await shot(page, "idn2-wrong-password-generic", "a wrong password — the one generic line");
  // ── 3 · the link it offers is the field app's own door ─────────────────
  await signIn(page, tech.email, temp);
  await page.getByRole("link", { name: "Field app" }).click();
  await page.waitForTimeout(1500);
  await shot(page, "idn3-field-app-signin", "the Field app link opens the field app's sign-in");
  await ctx.close();
}

// ── 4 · the phone with no session is sent to its own door; sign in → change → Today ─
{
  const { ctx, page, posts, answers } = await fresh();
  await page.goto(T("/work/mobile"), { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  say("NO SESSION ON /work/mobile LANDS AT:", page.url().replace(BASE, ""));
  await signIn(page, tech.email, temp);
  say("POSTED:", posts.map((p) => JSON.parse(p).surface));
  await shot(page, "idn4-technician-forced-change", "the invited technician signed in on the field app — the password change comes first");
  const pw = page.locator('input[type="password"]');
  const n = await pw.count();
  for (let i = 0; i < n; i += 1) await pw.nth(i).fill(NEW_PASSWORD);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(3000);
  say("ANSWERS:", JSON.stringify(answers));
  await shot(page, "idn5-technician-on-today", "after the change the technician lands on the field app's Today");
  await ctx.close();
}

// ── 6 · a clerk on the default scope may use the field app's door ─────────
say("\nCLERK (default scope `both`) on the field app's door — answered by the API proof, not walked.");

await admin.ctx.close();
await browser.close();
