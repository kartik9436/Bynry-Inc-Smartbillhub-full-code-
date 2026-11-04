#!/usr/bin/env node
/**
 * Screenshot every drawn state of the redrawn one-time bill, named exactly as
 * the drawing's own PNGs in `05-prototype/one-time-bill-2026-09-30/`, so the
 * two sets pair one-to-one for the skill's §4 side-by-side comparison.
 *
 * It drives the REAL page through `07-frontend/otb-harness.html`, which mounts
 * `OneTimeBillPage` with the real stylesheets and an API answered from
 * `oneTimeBillFixtures.ts` (the backend is being built to the same contract
 * in parallel). Start the dev server first:
 *
 *     (cd 07-frontend && npx vite --port 5199 --strictPort --host 127.0.0.1)
 *     node 10-scripts/one_time_bill_capture.mjs
 *
 * `compare-kinds` (state 37) is the mock-up's own review aid and is NOT built,
 * so it is not captured (inventory.md §0).
 */
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5199/otb-harness.html";
const OUT = process.env.OUT ?? new URL("../08-qa/screens/one-time-bill-2026-09-30/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

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
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });

const KINDS = [
  { kind: "interim", name: "Interim", first: 1 },
  { kind: "first", name: "First-bill", first: 9 },
  { kind: "final", name: "Final", first: 14 },
  { kind: "backbill", name: "Catch-up", first: 19 },
  { kind: "penalty", name: "Penalty", first: 24 },
  { kind: "fee", name: "Fee", first: 29 },
];

const pad = (n) => String(n).padStart(2, "0");
const byId = (id) => `[id="${id}"]`;
const settle = (page) => page.waitForTimeout(700);

async function shot(page, width, file, { keepFocus = false } = {}) {
  await settle(page);
  // A full-page capture of a scrolled page draws the sticky aside mid-page —
  // the artefact the drawing itself has (inventory §0). Capture from the top,
  // and with no field left focused unless the state IS the focus.
  await page.evaluate((keep) => {
    if (!keep && document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo(0, 0);
  }, keepFocus);
  await page.waitForTimeout(150);
  await page.screenshot({ path: join(OUT, `${width}-${file}.png`), fullPage: true });
  console.log(`·  ${width}-${file}.png`);
}

async function chooseAccount(page, { keepOpen = false } = {}) {
  await page.locator(byId("account_id")).fill("Alv");
  await page.locator('[id="account_id-listbox"] [role="option"]').first().waitFor();
  if (keepOpen) return;
  await page.locator('[id="account_id-listbox"] [role="option"]').first().click();
  await page.waitForFunction(() => document.getElementById("due_days")?.value === "21");
}

async function fillStep1(page, kind) {
  if (kind === "interim") {
    await page.locator(byId("period_start")).fill("2026-09-01");
    await page.locator(byId("period_end")).fill("2026-09-30");
  } else if (kind === "first") {
    await page.locator(byId("period_end")).fill("2026-09-30");
  } else if (kind === "final") {
    await page.locator(byId("period_start")).fill("2026-09-01");
    await page.locator(byId("period_end")).fill("2026-09-18");
  } else if (kind === "backbill" || kind === "penalty") {
    await page.getByRole("button", { name: "Add period" }).click();
    await page.getByRole("button", { name: "Add period" }).click();
    const spans = [
      ["2026-06-01", "2026-06-30"],
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
    ];
    for (const [i, [start, end]] of spans.entries()) {
      await page.locator(byId(`sub_periods[${i}].period_start`)).fill(start);
      await page.locator(byId(`sub_periods[${i}].period_end`)).fill(end);
    }
    await page.locator(byId("reason_code")).selectOption(kind === "penalty" ? "THEFT" : "MISSED");
    if (kind === "penalty") await page.locator(byId("charge_code")).selectOption("TAMPER");
  } else if (kind === "fee") {
    await page.locator(byId("charge_code")).selectOption("RECON");
  }
}

async function currentStep(page) {
  return page.locator('[data-wizard-step][aria-current="step"]').getAttribute("data-wizard-step");
}

/** Continue, and REFUSE to go on if the step did not move — otherwise the next
 *  file is named for a state the page is not in (the first draft of this
 *  script saved First-bill step 2 as "3-review" and "4-send"). `expectStay`
 *  is for the problems states, where staying on step 1 IS the state. */
async function next(page, { expectStay = false } = {}) {
  const before = await currentStep(page);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await settle(page);
  const after = await currentStep(page);
  if (!expectStay && after === before) throw new Error(`Continue did not advance from step ${before}`);
}

async function open(page, query) {
  await page.goto(`${BASE}?${query}`);
  await page.locator(byId("account_id")).waitFor();
}

for (const width of [1440, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });

  for (const { kind, name, first } of KINDS) {
    let n = first;
    await open(page, `kind=${kind}&reads=1`);
    if (kind === "interim") {
      await chooseAccount(page, { keepOpen: true });
      await shot(page, width, `02-Interim-1-account-dropdown-open`, { keepFocus: true });
      await open(page, `kind=${kind}&reads=1`);
    }
    await chooseAccount(page);
    await fillStep1(page, kind);
    await shot(page, width, `${pad(n)}-${name}-1-account`);
    n += kind === "interim" ? 2 : 1;
    await next(page);
    await shot(page, width, `${pad(n)}-${name}-2-services`);
    n += 1;
    if (kind === "first") {
      // The one meter with no move-in reading on file — typed, as drawn.
      await page.locator(byId("reading-w2|move_in|")).fill("128.9");
    }
    if (kind !== "fee") {
      for (const title of ["Services", "Rates", "Move-in charges"]) {
        const toggle = page.locator(`section[aria-label="${title}"] button[aria-controls]`);
        if ((await toggle.count()) > 0) await toggle.click();
      }
      await shot(page, width, `${pad(n)}-${name}-2-services-collapsed`);
      n += 1;
    }
    await next(page);
    await shot(page, width, `${pad(n)}-${name}-3-review`);
    n += 1;
    await next(page);
    await shot(page, width, `${pad(n)}-${name}-4-send`);
    n += 1;
    if (kind === "interim") {
      await page.getByText("I checked the amounts", { exact: true }).click();
      await shot(page, width, `07-Interim-4-send-ticked`);
      await page.getByRole("button", { name: /^Send .* bill$/ }).click();
      await page.getByText("Bill BL-2609-000318 sent").waitFor();
      await shot(page, width, `08-Interim-4-sent`);
    }
  }

  // Problems on step 1 — every problem at once, each on its field.
  await open(page, "kind=interim&reads=1");
  await chooseAccount(page);
  await page.locator(byId("period_start")).fill("2026-09-01");
  await page.locator(byId("period_end")).fill("2026-08-20");
  await page.locator(byId("due_days")).fill("");
  await next(page, { expectStay: true });
  await shot(page, width, "33-state-problems-Interim");

  await open(page, "kind=backbill&reads=1");
  await chooseAccount(page);
  await page.getByRole("button", { name: "Add period" }).click();
  await page.getByRole("button", { name: "Add period" }).click();
  for (const [i, [start, end]] of [["2026-06-01", "2026-06-30"], ["2026-07-01", "2026-06-15"], ["2026-08-01", "2026-08-31"]].entries()) {
    await page.locator(byId(`sub_periods[${i}].period_start`)).fill(start);
    await page.locator(byId(`sub_periods[${i}].period_end`)).fill(end);
  }
  await page.locator(byId("due_days")).fill("");
  await next(page, { expectStay: true });
  await shot(page, width, "34-state-problems-Catch-up");

  await open(page, "kind=fee&reads=1");
  await chooseAccount(page);
  await page.locator(byId("due_days")).fill("");
  await next(page, { expectStay: true });
  await shot(page, width, "35-state-problems-Fee");

  // Already billed — the banner stands on step 2, as drawn.
  await open(page, "kind=interim&reads=1&dup=1");
  await chooseAccount(page);
  await fillStep1(page, "interim");
  await next(page);
  await shot(page, width, "36-state-already-billed");

  await page.close();
}

await browser.close();
