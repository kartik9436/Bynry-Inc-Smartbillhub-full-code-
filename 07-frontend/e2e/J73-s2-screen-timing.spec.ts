// ── Trace ──────────────────────────────────────────────
// Journey:  J73 S2 — 08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md
// Criteria: 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md §4 S2
// Harness:  10-scripts/j73_scale_proof.py (the server half: s2-server)
// ───────────────────────────────────────────────────────
//
// S2 timed IN THE BROWSER, on a 40,000-account run that has been Checked and
// Calculated (J73_RUN_ID). Each screen is timed with the browser's own clock
// (`performance.now()`): from the click (or the navigation's start, for a
// screen that opens on load) to the first frame in which the screen's DATA is
// on the page — a row of the tag's accounts, the Sign off figures, a row of
// Not in this run. Beside each it records the API request's own timing
// (`request.timing()`), so a slow screen says whether the time was the
// server's or the browser's.
//
// It ASSERTS nothing about the bar: it writes the figures to
// J73_S2_OUT (JSON) and the coordinator reads them against S2's 2 s. A timing
// assertion on a shared machine is a coin toss; a recorded figure with its load
// beside it is evidence.
//
//   E2E_BASE_URL=http://127.0.0.1:<web> J73_RUN_ID=<uuid> J73_TAG=<code> \
//     npx playwright test e2e/J73-s2-screen-timing.spec.ts --workers=1
import { readFileSync, writeFileSync } from "node:fs";
const loadavg = (): number[] =>
  readFileSync("/proc/loadavg", "utf8").split(" ").slice(0, 3).map(Number);

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const RUN = process.env.J73_RUN_ID ?? "";
const TAG = process.env.J73_TAG ?? "unit_has_no_plan";
const OUT = process.env.J73_S2_OUT ?? "/tmp/j73-s2-timing.json";

type Timed = {
  screen: string;
  ms: number | null;
  api: { url: string; status: number; ms: number }[];
  load: number[];
};

/** Watch for `selector` in the page and record performance.now() at the first frame it exists. */
async function armSeen(page: Page, key: string, selector: string, digit = false): Promise<void> {
  await page.evaluate(
    ({ key: k, selector: s, digit: d }) => {
      const w = window as unknown as Record<string, number | undefined>;
      w[k] = undefined;
      const tick = () => {
        const found = document.querySelector(s);
        if (found !== null && (!d || /\d/.test(found.textContent ?? ""))) {
          w[k] = performance.now();
          return;
        }
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    },
    { key, selector, digit },
  );
}

/** performance.now() at first paint of `key`'s selector, or null if it never painted within `timeout`. */
async function seenAt(page: Page, key: string, timeout = 900_000): Promise<number | null> {
  try {
    await page.waitForFunction(
      (k) => (window as unknown as Record<string, number | undefined>)[k] !== undefined,
      key,
      {
        timeout,
      },
    );
  } catch {
    return null;
  }
  return page.evaluate((k) => (window as unknown as Record<string, number>)[k], key);
}

const rounded = (ms: number | null): number | null => (ms === null ? null : Math.round(ms));

function apiTimer(page: Page, match: RegExp) {
  const seen: { url: string; status: number; ms: number }[] = [];
  page.on("requestfinished", (request) => {
    if (!match.test(request.url())) return;
    const t = request.timing();
    void request.response().then((response) => {
      seen.push({
        url: request.url().replace(/^https?:\/\/[^/]+/, ""),
        status: response?.status() ?? 0,
        ms: Math.round(t.responseEnd),
      });
    });
  });
  return seen;
}

test.describe(`J73 S2 — screen timing at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(2_400_000);
  test.use({ viewport: { width: WIDTH, height: 1000 } });

  test("S2 · a tag's account list, Sign off and Not in this run, timed to first paint of the data", async ({
    page,
  }) => {
    test.skip(RUN === "", "set J73_RUN_ID to a Checked and Calculated 40,000-account run");
    await signIn(page);
    const results: Timed[] = [];
    const runUrl = `/${tenant()}/billing/run?run=${RUN}`;
    // J73_AT_CHECK=1: the run is still at Check (not Calculated) — time the tag list only, with no
    // Sign off read in flight on the server (DEF-BIL-8696 holds a worker for 60 s and skews the rest).
    const atCheck = process.env.J73_AT_CHECK === "1";
    let rows = 0;
    let pager = 0;
    // J73_SENT=1 (DEF-BIL-8696's re-time, 2026-10-01): the run is already SENT, so it opens on
    // Send — Sign off is timed from the click on its rail step to the figures, the way a clerk
    // goes back to it. The 40,000 world is kept sent for reproduction (19-check-cost-measured §10).
    const sent = process.env.J73_SENT === "1";
    // J73_COLD=1 (DEF-TEN-8731 / DEF-MET-8732, 2026-10-01): S2 as a clerk meets it — a COLD
    // open of the sent run's page, timed from the NAVIGATION'S START to the screen's data. A sent
    // run opens on Send with every rail step locked (Sign off cannot be re-entered once sent), so
    // the data timed is what that screen shows: the sent card's total and Not in this run's first
    // row. Every /api/ request the page makes on the way is recorded with its start beside it (the
    // waterfall) — Sign off's own `sign-off-summary` read among them — because the side reads the
    // page makes on open hold web workers the screen's reads queue behind, and a screen's own
    // request timing alone cannot show that.
    if (sent && process.env.J73_COLD === "1") {
      const waterfall: { url: string; status: number; at: number; ms: number }[] = [];
      let origin = 0;
      page.on("requestfinished", (request) => {
        if (!/\/api\//.test(request.url())) return;
        const t = request.timing();
        void request.response().then((response) => {
          waterfall.push({
            url: request.url().replace(/^https?:\/\/[^/]+/, ""),
            status: response?.status() ?? 0,
            at: Math.round(t.startTime - origin),
            ms: Math.round(t.responseEnd),
          });
        });
      });
      await page.goto(runUrl, { waitUntil: "commit" });
      origin = await page.evaluate(() => performance.timeOrigin);
      await armSeen(page, "__coldSent", "[data-sent-card] dd", true);
      await armSeen(page, "__coldNotIn", "[data-not-in-run] [data-not-in-run-row]");
      const wait = Number(process.env.J73_SIGNOFF_WAIT_MS ?? "900000");
      const sentSeen = await seenAt(page, "__coldSent", wait);
      const notInSeen = await seenAt(page, "__coldNotIn", wait);
      await page.waitForLoadState("networkidle", { timeout: 300_000 }).catch(() => undefined);
      await page.screenshot({ path: `${OUT}.cold-${WIDTH}.png`, fullPage: false });
      writeFileSync(
        OUT,
        JSON.stringify(
          {
            width: WIDTH,
            run: RUN,
            cold_open_to_sent_total_ms: rounded(sentSeen),
            cold_open_to_not_in_run_first_row_ms: rounded(notInSeen),
            figures: await page.locator("[data-sent-card] dd").allTextContents(),
            load: loadavg(),
            waterfall: [...waterfall].sort((a, b) => a.at - b.at),
          },
          null,
          2,
        ),
      );
      return;
    }
    if (!atCheck) {
      // 1 · SIGN OFF — the run opens on its step; navigation start → the figures.
      const signOffApi = apiTimer(page, /sign-off-summary/);
      let clickedAt = 0;
      if (sent) {
        await page.goto(runUrl);
        await page.waitForLoadState("networkidle", { timeout: 300_000 }).catch(() => undefined);
        await armSeen(page, "__signoff", "[data-step=sign-off] [data-run-fact=bills] dd", true);
        clickedAt = await page.evaluate(() => performance.now());
        await page.locator("[data-wizard=rail] [data-wizard-step='3']").click();
      } else {
        await page.goto(runUrl, { waitUntil: "commit" });
        await armSeen(page, "__signoff", "[data-step=sign-off] [data-run-fact=bills] dd", true);
      }
      // J73_SIGNOFF_WAIT_MS: how long to wait for the figures (a gunicorn worker is given 60 s).
      const signOffSeen = await seenAt(
        page,
        "__signoff",
        Number(process.env.J73_SIGNOFF_WAIT_MS ?? "900000"),
      );
      const signOffMs = signOffSeen === null ? null : signOffSeen - clickedAt;
      await expect(page.locator("[data-step=sign-off]")).toBeVisible();
      await page.screenshot({ path: `${OUT}.signoff-${WIDTH}.png`, fullPage: false });
      results.push({
        screen: "Sign off (open the run)",
        ms: rounded(signOffMs),
        api: [...signOffApi],
        load: loadavg(),
      });

      // 2 · NOT IN THIS RUN — the list on Sign off; navigation start → its first row.
      const notInApi = apiTimer(page, /not-in-run/);
      let notInFrom = 0;
      if (sent) {
        await page.goto(runUrl);
        await page.waitForLoadState("networkidle", { timeout: 300_000 }).catch(() => undefined);
        await armSeen(page, "__notin", "[data-not-in-run] [data-not-in-run-row]");
        notInFrom = await page.evaluate(() => performance.now());
        await page.locator("[data-wizard=rail] [data-wizard-step='3']").click();
      } else {
        await page.goto(runUrl, { waitUntil: "commit" });
        await armSeen(page, "__notin", "[data-not-in-run] [data-not-in-run-row]");
      }
      const notInSeen = await seenAt(page, "__notin");
      const notInMs = notInSeen === null ? null : notInSeen - notInFrom;
      results.push({
        screen: "Not in this run (on Sign off)",
        ms: rounded(notInMs),
        api: [...notInApi],
        load: loadavg(),
      });
      pager = await page.locator("[data-not-in-run] nav, [data-not-in-run] [data-pager]").count();
      rows = await page.locator("[data-not-in-run] [data-not-in-run-row]").count();
    }

    // 3 · A TAG'S ACCOUNT LIST — on the Check; click → the tag's first row.
    if (atCheck) await page.goto(runUrl);
    else await page.locator("[data-wizard=rail] [data-wizard-step='2']").click();
    const tag = page.locator(`[data-tag="${TAG}"]`).first();
    await expect(tag).toBeVisible({ timeout: 120_000 });
    // Let the screen's own first reads (the categories, the tag it opens by itself) finish first.
    await page.waitForLoadState("networkidle", { timeout: 300_000 }).catch(() => undefined);
    const tagApi = apiTimer(page, /check\/findings\?/);
    const rowSel = TAG === "ready" ? "[data-ready-row]" : "[data-row-account]";
    await armSeen(page, "__tag", `[data-tag-pane="${TAG}"] ${rowSel}`);
    const t0 = await page.evaluate(() => performance.now());
    await tag.click();
    const tagSeen = await seenAt(page, "__tag");
    const tagMs = tagSeen === null ? null : tagSeen - t0;
    results.push({
      screen: `Tag account list (${TAG}, click)`,
      ms: rounded(tagMs),
      api: [...tagApi],
      load: loadavg(),
    });
    await page.screenshot({ path: `${OUT}.tag-${WIDTH}.png`, fullPage: false });

    writeFileSync(
      OUT,
      JSON.stringify({ width: WIDTH, run: RUN, results, notInRun: { rows, pager } }, null, 2),
    );
  });
});
