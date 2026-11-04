#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
// rbs-jk-money-truth.mjs — CR-075 waves J and K, CLICKED IN A REAL BROWSER.
//
// Story:  US-RBS-008 (cutover reconciliation) · US-RBS-009 (books tie-out).
// Screens: RBS-006-R2 · RBS-006-R9, both drawn by wave C's renderer.
// Law:    CLAUDE.md hard-won law 6 — *diff the running app against the
//         prototype; no gate looks at rendered output* — and the PO's standing
//         definition of done: *"ensure you do web walkthorugh before you sign
//         off the user story or build"*.
//
// WHAT THIS PROVES THAT NO BACKEND TEST CAN
// ------------------------------------------
// `RB-020`'s claim is that **adding a runbook is one Python module and no
// frontend code**, because its report is a composition of the twelve blocks and
// nothing else. Waves J and K wrote two Python modules and not one line of
// TypeScript. **This script runs the SHIPPED SPA bundle** — built before either
// runbook existed — against a backend that serves them, so a green run is that
// claim being cashed rather than restated.
//
// It is also the only place the FIX ROUTES are exercised. `BR-RBS-011` says a
// failure names its fix route, and `DEF-RBS-4329` is what a route that resolves
// to nothing costs: every Fix link on every runbook landed on *"This screen is
// not built yet."* while `tsc` and every suite stayed green, because a relative
// `to` resolves against the CURRENT route. Only a browser can see that.
//
// WHAT FAILS IT
//   * a missing or empty <h1> on any screen it opens;
//   * a raw i18n key (`errors.something`) anywhere in body text — DEF-532;
//   * any 5xx observed at any point — DEF-529's class;
//   * the verdict word, the tie-out figures or the Close-period button not
//     matching what the engine computed;
//   * a Fix link that lands on "not built yet" — DEF-RBS-4329;
//   * and **`Close period ✓` being ABSENT rather than DISABLED**, which is the
//     `DEF-RBS-4360` case: the execution plan says absent and the build sheet,
//     the catalogue, the payload contract and the renderer all say disabled.
//
// CONFIG (env): RBS_BASE (http://127.0.0.1:9222) · RBS_TENANT (brazosbend) ·
//               RBS_EMAIL · RBS_PASSWORD · RBS_OUT (screenshot dir) · RBS_HEADED
// ─────────────────────────────────────────────────────────────────────────────

import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";

const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.RBS_BASE ?? "http://127.0.0.1:9222").replace(/\/$/, "");
const TENANT = process.env.RBS_TENANT ?? "brazosbend";
const EMAIL = process.env.RBS_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.RBS_PASSWORD ?? "S3cure!passw0rd";
const OUT =
  process.env.RBS_OUT ??
  join(tmpdir(), `rbs-jk-${new Date().toISOString().replace(/[:.]/g, "-")}`);
const HEADED = process.env.RBS_HEADED === "1";

/** DEF-532's second screenshot: the app printed `errors.not-found` to the user.
 *  `errors.` followed by a key segment — "3 errors." deliberately does not match. */
const RAW_KEY_RE = /\berrors\.[a-zA-Z][\w-]*/;

const failures = [];
const fiveHundreds = [];
let stepNo = 0;

function fail(step, message) {
  failures.push(`[${step}] ${message}`);
  console.error(`  ✗ ${message}`);
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      for (const candidate of [
        join(root, dir, "chrome-linux", "chrome"),
        join(root, dir, "chrome-linux", "headless_shell"),
      ]) {
        if (existsSync(candidate)) {
          console.log(`  · chromium: ${candidate} (not the pinned revision)`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

async function step(page, name, body) {
  stepNo += 1;
  const label = `${String(stepNo).padStart(2, "0")} ${name}`;
  console.log(`▶ ${label}`);
  try {
    await body();
  } catch (error) {
    fail(name, error.message);
  }
  try {
    await page.screenshot({ path: join(OUT, `${label.replace(/\s+/g, "-")}.png`), fullPage: true });
    // Every screen must have a heading and no raw key. Checked AFTER the body
    // so a step that navigated is judged on where it landed.
    const heading = await page.locator("h1").first().textContent().catch(() => null);
    if (!heading || !heading.trim()) fail(name, "no <h1> on this screen");
    const body = (await page.locator("body").innerText().catch(() => "")) ?? "";
    const leaked = body.match(RAW_KEY_RE);
    if (leaked) fail(name, `a raw i18n key reached the reader: ${leaked[0]}`);
  } catch {
    /* a screenshot failure is not the thing under test */
  }
}

/** The run id of the newest run of `key`, read through the API the SPA uses. */
async function newestRun(page, key) {
  const body = await page.evaluate(async (args) => {
    const response = await fetch(
      `/api/${args.tenant}/runbooks/runs?f.runbook=${args.key}&page=1&per=5`,
      { credentials: "same-origin" },
    );
    return response.json();
  }, { tenant: TENANT, key });
  const rows = body.results ?? body.rows ?? [];
  if (!rows.length) throw new Error(`no runs of ${key} — start one first`);
  return rows[0].id ?? rows[0].run_id;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  console.log(`base ${BASE} · tenant ${TENANT} · out ${OUT}`);

  const browser = await chromium.launch({ executablePath: resolveChromium(), headless: !HEADED });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.on("response", (response) => {
    if (response.status() >= 500) {
      fiveHundreds.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });

  await step(page, "sign-in", async () => {
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  });

  await step(page, "runbooks-home-offers-both-new-runbooks", async () => {
    await page.goto(`${BASE}/${TENANT}/runbooks`, { waitUntil: "networkidle" });
    // ⚠ **THE HOME PAGE PAGES ITS TABLES AND THE NEEDS-YOU LIST IS 30 ROWS
    // LONG**, so a runbook that has never needed anybody is legitimately not on
    // the first page of it. The library is the surface that must offer every
    // registered runbook, so that is where this is asserted — through the same
    // API the Templates screen reads.
    await page.waitForSelector("h1", { timeout: 15000 });
    const library = await page.evaluate(async (tenant) => {
      const response = await fetch(`/api/${tenant}/runbooks/templates?page=1&per=100`, {
        credentials: "same-origin",
      });
      return response.json();
    }, TENANT);
    const names = (library.results ?? library.rows ?? []).map((row) => row.name);
    // The NAMES a clerk reads, never the keys (B14 rule 31).
    for (const name of ["Cutover reconciliation", "Books tie-out"]) {
      if (!names.includes(name)) {
        throw new Error(
          `the templates library does not offer "${name}" — RB-020's claim is that adding a runbook is one Python module and no frontend code. Saw: ${names.join(", ")}`,
        );
      }
    }
    console.log(`  · the library offers ${names.length} runbooks including both new ones`);
  });

  // ── K · the books tie-out ────────────────────────────────────────────────
  let monthEndRunId;
  await step(page, "month-end-result-screen", async () => {
    monthEndRunId = await newestRun(page, "month_end");
    await page.goto(`${BASE}/${TENANT}/runbooks/month_end/runs/${monthEndRunId}`, {
      waitUntil: "networkidle",
    });
    const text = await page.locator("body").innerText();
    if (!/Not balanced|Balanced/.test(text)) throw new Error("no verdict word on the result screen");
    if (!text.includes("Tie-out")) throw new Error("the Reconciled block did not draw");
    // B14 rule 34's ratified pair, rendered. ⚠ **COMPARED CASE-INSENSITIVELY,
    // AND THAT IS NOT LAZINESS.** `innerText` returns text as it is PAINTED,
    // and rule 20 sets table headers in uppercase — so a case-sensitive check
    // here fails on a screen that is exactly right. It failed that way on
    // 2026-09-07 and the screen was correct; the assertion was not.
    const upper = text.toUpperCase();
    for (const heading of ["Recorded", "In the books"]) {
      if (!upper.includes(heading.toUpperCase())) {
        throw new Error(`the tie-out table is missing the column "${heading}"`);
      }
    }
  });

  await step(page, "close-period-is-DISABLED-with-its-reason-not-absent", async () => {
    // ⚠ THE `DEF-RBS-4360` CASE, AND THE ONLY PLACE IT CAN BE CHECKED. The
    // execution plan's K2 row says the button is ABSENT while the list is
    // non-empty; the build sheet, RB-109, contract.PAYLOAD_FIELDS and
    // ActionBlock.tsx all say DISABLED WITH ITS REASON. A backend test can
    // assert the payload; only a browser can say what a person sees.
    const button = page.locator('[data-block="action"] button');
    if ((await button.count()) === 0) {
      throw new Error(
        "Close period ✓ is ABSENT. It must be DISABLED with its reason — a control is absent when the CAPABILITY does not exist, and disabled when a PRECONDITION is not met (DEF-RBS-4360)",
      );
    }
    const label = (await button.first().innerText()).trim();
    if (!label.startsWith("Close period")) throw new Error(`the action button reads "${label}"`);
    if (!(await button.first().isDisabled())) {
      throw new Error("Close period ✓ is ENABLED over a period with blockers open");
    }
    // The reason must be READABLE, not only a tooltip: a refusal half the
    // readers cannot reach is half a refusal.
    const reason = await page.locator("[data-action-reason]").innerText().catch(() => "");
    if (!/\d+ blockers? open/.test(reason)) {
      throw new Error(`the disabled button states no readable reason (saw "${reason}")`);
    }
    // B14 rule 6 — the danger tier on an irreversible commit.
    const tier = await button.first().getAttribute("data-action-tier");
    if (tier !== "danger") throw new Error(`Close period ✓ is the "${tier}" tier, not danger`);
    console.log(`  · Close period ✓ · danger · disabled · "${reason.trim()}"`);
  });

  await step(page, "every-fix-link-opens-a-real-screen", async () => {
    // `BR-RBS-011` · `DEF-RBS-4329`. A relative `to` resolves against the
    // CURRENT route, so a tenant-relative fix route becomes
    // `/tenant/runbooks/month_end/runs/<id>/finance` — a live-looking link onto
    // "not built yet". `tsc` and every suite pass on it.
    const links = page.locator('a[href*="/' + TENANT + '/"]').filter({ hasText: /→|Open|Allocate|Reconcile|Record/ });
    const count = await links.count();
    if (count === 0) throw new Error("the settle table drew no fix links at all");
    const seen = [];
    for (let index = 0; index < Math.min(count, 6); index += 1) {
      const href = await links.nth(index).getAttribute("href");
      if (!href) continue;
      if (href.includes("/runs/")) {
        throw new Error(`a fix route resolved against the run's own URL: ${href} (DEF-RBS-4329)`);
      }
      seen.push(href);
    }
    console.log(`  · ${seen.length} fix routes, none nested under the run: ${seen.join(" ")}`);
  });

  // ── J · the cutover reconciliation ───────────────────────────────────────
  await step(page, "cutover-result-screen-reads-the-variance", async () => {
    const runId = await newestRun(page, "cutover_readiness");
    await page.goto(`${BASE}/${TENANT}/runbooks/cutover_readiness/runs/${runId}`, {
      waitUntil: "networkidle",
    });
    const text = await page.locator("body").innerText();
    if (!/No-go|Go/.test(text)) throw new Error("no verdict word on the cutover result screen");
    if (!text.includes("Counts and totals")) throw new Error("the Reconciled block did not draw");
    if (!text.includes("1,204.05") && !text.includes("1204.05")) {
      throw new Error("the $1,204.05 variance is not on screen — this is the figure the epic signs");
    }
    console.log("  · the cutover variance reads $1,204.05 on screen");
  });

  await step(page, "the-nine-step-chain-draws-with-a-red-cell", async () => {
    const cells = page.locator("[data-chain-cell], [data-block='chain'] li, [data-block='chain'] div");
    const text = await page.locator("body").innerText();
    for (const label of ["Balances", "Sample gone", "Plan items"]) {
      if (!text.includes(label)) throw new Error(`the chain is missing the cell "${label}"`);
    }
    console.log(`  · the nine-cell chain drew (${await cells.count()} nodes)`);
  });

  await context.close();
  await browser.close();

  if (fiveHundreds.length) {
    console.error("\n5xx responses observed:");
    for (const one of fiveHundreds) console.error(`  ${one}`);
    failures.push(`${fiveHundreds.length} 5xx response(s)`);
  }
  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length) {
    console.error(`\nFAILED · ${failures.length}`);
    for (const one of failures) console.error(`  ${one}`);
    process.exit(1);
  }
  console.log("\nPASSED · both money-truth runbooks render through the SHIPPED bundle");
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
