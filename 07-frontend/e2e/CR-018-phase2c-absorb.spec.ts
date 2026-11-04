// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 2c — OQ-279 (absorb the three 22px titles into the
//           ruled heading scale) and OQ-273 (the four service colours).
// Rules:    decision log 2026-08-20 "OQ-279 ruled: absorb the three 22px
//           titles" (commit 5dbf2d7) and "OQ-273 ruled: the four hexes applied
//           to OUR services" (commit 4e78da4). The bar: the ONLY pixels that
//           may move are `.modal-title`, `[data-rcw="head-title"]` and `.brun-h`.
//           DEF-316 — a `fullPage` shot of this app is a viewport shot unless
//           the inner scroller is released first.
// Impacts:  nothing in src/ — this is an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// WHY THIS EXISTS AND WHY `CR-018-phase2-type-scale.spec.ts` IS NOT ENOUGH
//
// That census walks screens reachable by NAVIGATION and, in its own recorded
// words, "opens no modal, wizard step or panel". All three titles OQ-279 moves
// are behind a click: `.modal-title` needs a modal opened, the wizard head
// needs the route wizard entered, `.brun-h` needs /billing/run. A phase whose
// only intended movements are invisible to its instrument proves nothing.
//
// So this one CLICKS to each of the three, records the computed size of the
// title AND of every other element on the surface, and photographs it. Two
// runs into two directories; the diff is the complete list of pixels that
// moved, and every line in it must be one of the three the ruling names.
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npx vite build && \
//       E2E_BASE_URL=http://127.0.0.1:8180 \
//       E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//       CR018P2C_OUT=/tmp/cr018p2c/before \
//       npx playwright test e2e/CR-018-phase2c-absorb.spec.ts
//
// ⚠ REBUILD THE FRONTEND FIRST — boot_stack serves `dist/`, so a stale bundle
// photographs yesterday's CSS, which is the one thing this file exists to see.
// ⚠ THE TWO RUNS MUST USE DIFFERENT `CR018P2C_OUT` DIRECTORIES, or the second
// overwrites the "before" it is being compared against.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { baseUrl, expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const OUT = process.env.CR018P2C_OUT ?? "/tmp/cr018p2c/shot";

const PROPS = ["font-size", "font-weight", "font-family", "line-height", "letter-spacing"] as const;

/** Same census shape as Phase 2's, keyed by tree path and not by class list. */
const censusScript = (props: string[]) => {
  function pathOf(el: Element): string {
    const parts: string[] = [];
    for (let node: Element | null = el; node !== null; node = node.parentElement) {
      if (node.tagName === "HTML") break;
      const parent = node.parentElement;
      const index = parent === null ? 0 : Array.prototype.indexOf.call(parent.children, node);
      parts.unshift(`${node.tagName.toLowerCase()}[${index}]`);
    }
    return parts.join(">");
  }
  // ⚠ `main.view` is NOT the root here: a modal is rendered by the shell and a
  // census rooted at the content pane would not contain the one element the
  // surface was opened to measure.
  const root = document.body;
  const out: Record<string, Record<string, string>> = {};
  for (const el of [root, ...Array.from(root.querySelectorAll("*"))]) {
    const cs = getComputedStyle(el);
    const row: Record<string, string> = {};
    for (const p of props) row[p] = cs.getPropertyValue(p);
    out[pathOf(el)] = row;
  }
  return out;
};

async function shoot(page: Page, name: string): Promise<void> {
  await expandInnerScroller(page); // DEF-316
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
}

/** The computed size of one selector, or "ABSENT" — recorded per surface so a
 *  selector that stopped matching reads as a loud string rather than as an
 *  unchanged census. */
async function sizeOf(page: Page, selector: string): Promise<string> {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    return el === null ? "ABSENT" : getComputedStyle(el).fontSize;
  }, selector);
}

test.describe("CR-018 Phase 2c — the three absorbed titles and the ten service dots", () => {
  test("every moved surface is censused and photographed @app-server", async ({ page }) => {
    test.setTimeout(900_000);
    await page.setViewportSize({ width: 1440, height: 900 });

    const census: Record<string, Record<string, Record<string, string>>> = {};
    const key: Record<string, string> = {};

    await signIn(page);

    // ── 1 · THE MODAL · `.modal-title` ──────────────────────────────────
    // Reference data → Areas & sub-areas → "+ Add entry" is the shortest path
    // to a real FormModal with real fields behind it (CR-004's own walk).
    await page.goto(`${baseUrl()}/${tenant()}/settings/reference-data`);
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.locator(".lookup-card").first().waitFor({ timeout: 30_000 });
    await page.waitForTimeout(1_200);
    // The lookup CARD is also one of the two genuine 22px metrics the ruling
    // KEEPS, so it is measured on the surface it lives on, before the click.
    key["lookup-card .v"] = await sizeOf(page, ".lookup-card .v");
    key["lookup-group h3"] = await sizeOf(page, "section.lookup-group h3");
    census["settings/reference-data"] = await page.evaluate(censusScript, PROPS as unknown as string[]);
    await shoot(page, "1a-reference-data");

    await page.locator(".lookup-card").filter({ hasText: "Areas & sub-areas" }).first().click();
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.getByRole("button", { name: "+ Add entry" }).first().click();
    await page.locator(".modal-card").waitFor({ timeout: 30_000 });
    await page.waitForTimeout(800);
    key["modal-title"] = await sizeOf(page, ".modal-title");
    key["modal-kicker"] = await sizeOf(page, ".modal-kicker");
    census["modal"] = await page.evaluate(censusScript, PROPS as unknown as string[]);
    await page.screenshot({ path: join(OUT, "2-modal.png"), fullPage: true });

    // ── 2 · THE WIZARD · `[data-rcw="head-title"]` ─────────────────────
    await page.goto(`${baseUrl()}/${tenant()}/settings/reference-data/routes-cycles`);
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.getByRole("button", { name: "+ Add route" }).first().waitFor({ timeout: 30_000 });
    await page.getByRole("button", { name: "+ Add route" }).first().click();
    await page.locator('[data-rcw="head-title"]').waitFor({ timeout: 30_000 });
    await page.waitForTimeout(1_000);
    key["rcw-head-title"] = await sizeOf(page, '[data-rcw="head-title"]');
    key["rcw-title"] = await sizeOf(page, '[data-rcw="title"]');
    census["routes-wizard"] = await page.evaluate(censusScript, PROPS as unknown as string[]);
    await shoot(page, "3-routes-wizard");

    // ── 3 · THE BILL RUN · the step heading ─────────────────────────────
    // Was `.brun-h`; `features/billing/billRun.css` is deleted (CR-018 long
    // tail, 2026-08-22) and the heading is utilities, so the walk reaches it
    // by `data-brun="h"`. The `key` entry keeps its old NAME on purpose: it is
    // the measurement's label in census.json, comparable across runs.
    await page.goto(`${baseUrl()}/${tenant()}/billing/run`);
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.locator('[data-brun="h"]').first().waitFor({ timeout: 30_000 });
    await page.waitForTimeout(1_200);
    key["brun-h"] = await sizeOf(page, '[data-brun="h"]');
    census["billing-run"] = await page.evaluate(censusScript, PROPS as unknown as string[]);
    await shoot(page, "4-billing-run");

    // ── 4 · THE SERVICE DOTS · `.rating-tag.svc-*` ──────────────────────
    await page.goto(`${baseUrl()}/${tenant()}/plans-rates`);
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.waitForTimeout(2_400);
    key["rating-tag dots"] = String(await page.locator(".rating-tag").count());
    census["plans-rates"] = await page.evaluate(censusScript, PROPS as unknown as string[]);
    await shoot(page, "5-plans-rates");

    // ── 5 · READS · the other genuine 22px metric, `.rd-figure-value` ────
    await page.goto(`${baseUrl()}/${tenant()}/reads`);
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.waitForTimeout(2_000);
    key["rd-figure-value"] = await sizeOf(page, ".rd-figure-value");
    census["reads"] = await page.evaluate(censusScript, PROPS as unknown as string[]);
    await shoot(page, "6-reads");

    // A census over an empty walk passes vacuously — DEF-057's shape.
    const elements = Object.values(census).reduce((n, s) => n + Object.keys(s).length, 0);
    expect(Object.keys(census).length).toBe(6);
    // 1,200 is a FLOOR under a MEASURED 1,435 (2026-08-20, this walk at
    // 1440x900), not a guess. The first draft guessed 1,500 and went RED on a
    // healthy run — which is how the guard was proved to fire (law 7) and why
    // the number written here is the one the browser reported.
    expect(elements, "the census measured almost nothing").toBeGreaterThan(1_200);
    // …and the three titles must have been REACHED, not merely walked past.
    for (const k of ["modal-title", "rcw-head-title", "brun-h"]) {
      expect(key[k], `${k} was never on screen — the click path is broken`).not.toBe("ABSENT");
    }

    mkdirSync(OUT, { recursive: true });
    writeFileSync(join(OUT, "census.json"), `${JSON.stringify(census, null, 1)}\n`);
    writeFileSync(join(OUT, "key.json"), `${JSON.stringify(key, null, 1)}\n`);

    // eslint-disable-next-line no-console
    console.log(`CR-018 Phase 2c: ${elements} elements over 6 surfaces → ${OUT}\n${JSON.stringify(key, null, 1)}`);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 12-governance/02-decision-log.md 2026-08-20 OQ-279 (commit 5dbf2d7) + OQ-273/OQ-274 (commit 4e78da4) + 12-governance/11-change-requests.md CR-018
// generated: 2026-08-20 by the CR-018 Phase 2c lane
// checklist: A✔ B=n/a(instrument, no screen) C=deferred(no backend half) D=deferred(no API call) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST (hard-won law 7). The emptiness guard fired for real on the first BEFORE run — the draft floor of 1,500 was above the measured 1,435 and the run failed naming it; the floor is now 1,200 under a recorded measurement. The three ABSENT guards were proved by pointing the modal click at a button name that does not exist, which left key["modal-title"]==="ABSENT" and failed naming it.
// exceptions: (1) it WRITES artefacts and asserts almost nothing — the comparison happens between two output directories, because "identical to the previous run" is not a fact one run can hold · (2) five type properties only; a layout regression is invisible to it, CR-016's register is the instrument for that
// status: VERIFIED-UNRATIFIED
