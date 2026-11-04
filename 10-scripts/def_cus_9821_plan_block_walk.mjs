// ── Trace ──────────────────────────────────────────────
// Change:  DEF-CUS-9821 — New Connect step 2's This-plan block, redrawn to
//          the PO-approved drawing (claude.ai/artifact/9poRZzcU1ooxCw9A78jXgy).
// World:   10-scripts/def_cus_9821_plan_block_world.py (plan MBSP: Solar names
//          BASE-SOL; Battery's schedule names no base code and two codes could
//          serve a Residential account).
// What it walks, signed in as a System Admin, at 1440 and at 390:
//   1. Step 1: Customer category = Residential (the class the block narrows to).
//   2. Step 2: services Solar + Battery, plan MBSP → the block appears under the
//      Plan picker; photographs the panel collapsed (01), then with Taxes
//      expanded (02).
//   3. Checks: the eight parts; the warning only for Battery; five parts closed;
//      every link target=_blank; the not-zero sentence nowhere; the footer names
//      Residential; picking another plan refreshes the block.
//
//   BASE=http://127.0.0.1:<spa> TENANT=<slug> EMAIL=<admin> PASSWORD=<pw> SHOTS=<dir> \
//   node 10-scripts/def_cus_9821_plan_block_walk.mjs
import { createRequire } from "node:module";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
const require = createRequire(`${REPO}/07-frontend/package.json`);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:5821";
const TENANT = process.env.TENANT ?? "mvimatrix";
const EMAIL = process.env.EMAIL ?? "marcus@cedarford.example";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? `${REPO}/08-qa/screens/def-cus-9821-2026-10-06`;
const CHROME = process.env.E2E_CHROMIUM_EXECUTABLE ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(SHOTS, { recursive: true });

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} · ${name}${detail ? ` — ${detail}` : ""}`);
}

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 }), page.keyboard.press("Enter")]);
}

async function toStep2(page) {
  // The draft is in memory: it survives moves INSIDE the app, never a reload.
  // So open step 2, step back to 1 on the rail, pick the category, and come
  // forward with the browser's own history (a popstate, not a page load).
  await page.goto(`${BASE}/${TENANT}/connections/new?step=2`, { waitUntil: "networkidle" });
  await page.locator('[data-wizard-step="1"]').click();
  const category = page.locator("select[id$='owner_category']");
  await category.waitFor({ timeout: 30000 });
  const options = await category.locator("option").allTextContents();
  const residential = options.find((text) => /^Residential/.test(text.trim()));
  await category.selectOption({ label: residential });
  // The rail only goes back (`reached` is the step on the address), and the
  // address is written with `replace`, so there is no history entry to go
  // forward to. A client-side move to `?step=2` — what the router does on any
  // in-app link — keeps the in-memory draft; a page load would not.
  await page.evaluate(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("step", "2");
    window.history.pushState({}, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await page.locator('[data-step-content="services-and-plan"]').waitFor({ timeout: 30000 });
}

/** The panel from a FULL-PAGE capture, so the frame's sticky header and the
 *  wizard's footer do not sit over a panel taller than the window. */
async function shoot(page, locator, path) {
  // The frame scrolls an inner pane, not the window, so a full-page capture is
  // the window. A window tall enough for the whole panel, then back.
  const before = page.viewportSize();
  await page.setViewportSize({ width: before.width, height: 4000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await locator.screenshot({ path });
  await page.setViewportSize(before);
}

async function addService(page, label) {
  const add = page.locator("#services_available-add");
  const values = await add.locator("option").evaluateAll((nodes) => nodes.map((n) => [n.value, n.textContent]));
  const hit = values.find(([value, text]) => value === label.toLowerCase() || (text ?? "").trim().toLowerCase() === label.toLowerCase());
  if (hit) await add.selectOption(hit[0]);
}

async function walk(width) {
  const browser = await chromium.launch({ executablePath: existsSync(CHROME) ? CHROME : undefined });
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  await signIn(page);
  await toStep2(page);
  await addService(page, "solar");
  await addService(page, "battery");
  const plan = page.locator("#nc_plan");
  const planLabels = await plan.locator("option").allTextContents();
  await plan.selectOption({ label: planLabels.find((text) => text.includes("Municipal Solar PV")) });
  const panel = page.locator('[data-step-content="services-and-plan"]');
  await panel.locator("[data-this-plan]").waitFor({ timeout: 30000 });
  // The class's NAME comes from the account-types list, a read of its own; give
  // it the time a person would before reading the footer.
  await panel
    .locator("[data-this-plan-footer]")
    .filter({ hasText: "Residential" })
    .waitFor({ timeout: 15000 })
    .catch(() => undefined);
  await page.waitForTimeout(500);
  await shoot(page, panel, `${SHOTS}/${width}-01-panel-collapsed.png`);

  const text = await panel.innerText();
  check(`${width} · summary strip`, (await panel.locator('[data-facts="this-plan-summary"]').count()) === 1, "MBSP · v1 · Published · In force · Account type · Minimum bill · Covers");
  check(`${width} · code MBSP and covers 2 of 2`, text.includes("MBSP") && /2 of 2 services/.test(text));
  check(`${width} · Battery warning, and only that one`, (await panel.locator('[data-warning="this-plan-noBaseCode"]').count()) === 1 && (await panel.locator("[data-warning]").count()) === 1, text.match(/Battery: [^\n]*/)?.[0] ?? "");
  check(`${width} · Base charges + Usage rates open`, (await panel.locator('[data-this-plan-part="base"]').count()) === 1 && (await panel.locator('[data-this-plan-part="usage"]').count()) === 1);
  check(`${width} · five parts closed`, (await panel.locator('button[aria-expanded="false"]').count()) >= 5);
  check(`${width} · Battery base Not chosen`, (await panel.locator('[data-base-not-chosen="battery"]').count()) === 1);
  check(`${width} · BASE-SOL linked`, (await panel.getByRole("link", { name: /BASE-SOL/ }).count()) === 1);
  check(`${width} · unit price to four places`, text.includes("$0.0425"));
  check(`${width} · no not-zero sentence`, !text.includes("It is not zero"));
  check(`${width} · footer names Residential`, text.includes("for Residential accounts at this address"));
  const targets = await panel.locator("a").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("target")));
  check(`${width} · every link opens a new tab`, targets.length > 0 && targets.every((value) => value === "_blank"), `${targets.length} links`);
  check(`${width} · no horizontal page scroll`, await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));

  await panel.getByRole("button", { name: /^Taxes/ }).click();
  await panel.locator('[data-this-plan-part="taxes"]').waitFor();
  await shoot(page, panel, `${SHOTS}/${width}-02-panel-taxes-open.png`);
  check(`${width} · Taxes opens`, (await panel.locator('[data-this-plan-part="taxes"]').innerText()).length > 0);

  // Picking another plan refreshes the block.
  const other = planLabels.find((text) => text && !text.includes("Municipal Solar PV") && !/Choose/.test(text));
  if (other) {
    await plan.selectOption({ label: other });
    await page.waitForTimeout(1500);
    const code = await panel.locator("[data-this-plan]").getAttribute("data-this-plan").catch(() => null);
    check(`${width} · another plan refreshes the block`, code !== null && code !== "MBSP", `now ${code}`);
  }
  await browser.close();
}

await walk(1440);
await walk(390);
writeFileSync(`${SHOTS}/walk.txt`, results.map((r) => `${r.ok ? "PASS" : "FAIL"} · ${r.name}${r.detail ? ` — ${r.detail}` : ""}`).join("\n") + "\n");
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed} PASS / ${failed} FAIL`);
process.exit(failed === 0 ? 0 : 1);
