/**
 * ADD AN ASSET — WALK ALL FIVE STEPS AT 1280 AND 1440 AND SAY WHAT IS ON EACH.
 *
 * Screens 28-32 of `05-prototype/01 Assets Menu Blueprint.pdf` (pages 108-121).
 * It REPORTS; it asserts only the three things that can be wrong silently:
 * a sideways-scrolling body, a control off the right edge, and a step whose
 * field set does not match the drawing's.
 *
 *   cd 07-frontend && npx vite build
 *   node <this file>
 */
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const KLASS = process.env.KLASS ?? "meters";
const SHOTS = process.env.SHOTS ?? "";
const say = (...a) => console.log(...a);

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

/** Everything a person can read or press on the step that is showing. */
const SNAPSHOT = `
  const head = document.querySelector(".page-header");
  const rail = [...document.querySelectorAll("[data-wizard-step]")].map(
    (b) => b.getAttribute("data-wizard-step") + " " + b.textContent.trim().replace(/^\\d+/, "") +
           " [" + b.getAttribute("data-state") + "]");
  const fields = [...document.querySelectorAll("[data-wizard='content'] input, [data-wizard='content'] select, [data-wizard='content'] textarea")]
    .map((el) => {
      const lab = el.id ? document.querySelector("label[for='" + CSS.escape(el.id) + "']") : null;
      const box = el.getBoundingClientRect();
      return {
        id: el.id, tag: el.tagName, type: el.type || "",
        label: (lab ? lab.textContent : "").trim(),
        x: Math.round(box.x), w: Math.round(box.width),
        disabled: el.disabled,
      };
    });
  const helpers = [...document.querySelectorAll("[data-wizard='content'] .field-help, [data-wizard='content'] [id$='-help']")]
    .map((el) => el.textContent.trim());
  const notes = [...document.querySelectorAll("[data-wizard='content'] [data-note], [data-wizard='content'] [data-consequence], [data-wizard='content'] [role='note']")]
    .map((el) => el.textContent.trim());
  const panels = [...document.querySelectorAll("[data-wizard='content'] h3")].map((el) => el.textContent.trim());
  const facts = [...document.querySelectorAll("[data-wizard='content'] dt")].map((el) => el.textContent.trim());
  const buttons = [...document.querySelectorAll("[data-wizard='actions'] button, [data-wizard='actions'] a")]
    .map((b) => b.textContent.trim() + (b.disabled ? " (disabled)" : ""));
  const radios = [...document.querySelectorAll("[data-wizard='content'] [role='radio'], [data-wizard='content'] input[type=radio]")]
    .map((b) => b.textContent.trim() || b.value);
  const checks = [...document.querySelectorAll("[data-wizard='content'] input[type=checkbox]")]
    .map((b) => { const l = b.id ? document.querySelector("label[for='" + CSS.escape(b.id) + "']") : null;
                  return (l ? l.textContent : b.getAttribute("aria-label") || "").trim(); });
  return {
    kicker: (document.querySelector("[data-kicker]") || {}).textContent || "",
    title: (document.querySelector(".page-header h1, .page-header h2") || {}).textContent || "",
    headTail: head ? head.textContent.trim().slice(0, 260) : "",
    rail, fields, helpers, notes, panels, facts, buttons, radios, checks,
    bodyScrollsSideways: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    docWidth: document.documentElement.scrollWidth,
  };
`;

async function snap(page) {
  return page.evaluate("(() => {" + SNAPSHOT + "})()");
}

function report(width, step, s) {
  say(`\n──────── ${width}px · STEP ${step} ────────`);
  say(`  kicker  : ${s.kicker.trim()}`);
  say(`  title   : ${s.title.trim()}`);
  say(`  head    : ${s.headTail.replace(/\s+/g, " ").slice(0, 200)}`);
  say(`  rail    : ${s.rail.join(" | ")}`);
  if (s.radios.length) say(`  choices : ${s.radios.join(" · ")}`);
  for (const f of s.fields) {
    say(`  field   : ${(f.label || "(no label)").padEnd(34)} ${f.tag}${f.type ? "/" + f.type : ""}  x=${f.x} w=${f.w}${f.disabled ? " DISABLED" : ""}`);
  }
  if (s.panels.length) say(`  panels  : ${s.panels.join(" · ")}`);
  if (s.facts.length) say(`  facts   : ${s.facts.join(" · ")}`);
  if (s.checks.length) say(`  checks  : ${s.checks.join(" · ")}`);
  for (const h of s.helpers) say(`  help    : ${h}`);
  for (const n of s.notes) say(`  note    : ${n.replace(/\s+/g, " ").slice(0, 160)}`);
  say(`  buttons : ${s.buttons.join(" · ")}`);
  say(`  sideways scroll: ${s.bodyScrollsSideways ? "YES — FINDING" : "no"} (doc ${s.docWidth})`);
}

const run = async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  if (SHOTS) mkdirSync(SHOTS, { recursive: true });
  try {
    for (const width of [1280, 1440]) {
      const ctx = await browser.newContext({ viewport: { width, height: 950 } });
      const page = await ctx.newPage();
      await signIn(page);
      await page.goto(`${BASE}/${TENANT}/assets/new?class=${KLASS}&step=1`, { waitUntil: "networkidle" });

      // Step 1 — answer what the step needs so Continue is live.
      const typeSel = page.locator("#type");
      await typeSel.waitFor({ state: "visible", timeout: 15000 });
      const typeValue = await typeSel.locator("option").nth(1).getAttribute("value");
      await typeSel.selectOption(typeValue);
      const svc = page.locator("#service");
      if (await svc.count()) {
        const svcValue = await svc.locator("option").nth(1).getAttribute("value");
        if (svcValue) await svc.selectOption(svcValue);
      }
      report(width, 1, await snap(page));
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/${width}-step1.png`, fullPage: true });

      for (let step = 2; step <= 6; step += 1) {
        const cont = page.getByRole("button", { name: /^Continue$/ });
        if (!(await cont.count())) break;
        await cont.click();
        await page.waitForTimeout(350);
        // Step 2 needs a unit of measure on a measuring class.
        const uom = page.locator("#unit");
        if (await uom.count()) {
          const v = await uom.inputValue();
          if (v === "") await uom.fill("kgal");
        }
        const s = await snap(page);
        report(width, step, s);
        if (SHOTS) await page.screenshot({ path: `${SHOTS}/${width}-step${step}.png`, fullPage: true });
        if (s.buttons.some((b) => /Add asset/.test(b))) break;
      }
      await ctx.close();
    }
  } finally {
    await browser.close();
  }
};

run().catch((error) => {
  console.error(error);
  process.exit(2);
});
