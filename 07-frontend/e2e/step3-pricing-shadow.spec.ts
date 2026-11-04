// ── Trace ──────────────────────────────────────────────
// Story:   US-BIL-002 (S31.2 "Check what we found" — the pre-commit stage)
//          Screens: S31.2
// Defects: DEF-438 (the R1–R7 chain had no production caller) · DEF-494 (the
//          two paths mean OPPOSITE things by "a plan in force") · DEF-1811
//          (the shadow could not be run on any account — the reason the screen
//          half was withheld) · DEF-1813 (CLOSED — the fact that unblocked it)
// Rules:   BR-BIL-039 (the preview and the real run are the SAME code) ·
//          BR-SHL-020 (a refusal reads as a sentence, not a code)
// ───────────────────────────────────────────────────────
//
// **THE ONE THING THIS FILE PROVES: A PERSON CAN SEE, IN A BROWSER, BEFORE ANY
// BILL IS COMMITTED, WHERE THE TWO WAYS OF PRICING DISAGREE.**
//
// ⚠ **AND IT PROVES IT THE ONLY WAY THAT MEANS ANYTHING.** `DEF-438`'s escape
// reason names the trap: *"every gate that touches this file is a unit test
// calling it DIRECTLY, which is exactly the shape that passes forever on dead
// code."* A mocked render asserts against a fixture this file wrote, so it
// passes while nothing server-side ran. This drives the real screens against a
// real Django and a real Postgres, and the numbers on it come off the seeded
// utility's own rows.
//
// ⚠ **WHAT IT ASSERTS IS THE PAIR OF NUMBERS, NOT A DISAGREEMENT.** The
// decision log warns that *"a count that is always zero means the chain is not
// running, and nothing else would say so"* — so a spec asserting *"1
// disagreement"* would go red the day somebody RULES that class and fixes it,
// which is the outcome we are waiting for. What must always be true is that the
// panel is there and that it shows how many customers were worked out both
// ways beside how many differed. That is asserted; the verdict is not.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

test.describe("R1–R7 step 3 — the pricing comparison on the pre-commit stage @app-server", () => {
  skipUnlessAppServer(test);

  test("the comparison panel is on S31.2 and reads both numbers together", async ({ page }) => {
    test.setTimeout(180_000);

    await signIn(page);
    await page.goto(`/${tenant()}/billing/run`);
    await page.locator("#brun-cycle").waitFor();

    // -- STEP 1 - a real run, created through the app's own endpoint ------
    //
    // ⚠ **THE RUN IS CREATED THROUGH `POST /billing/runs`, NOT BY FILLING IN
    // THE WIZARD, AND THAT IS A DELIBERATE NARROWING.** Driving step 1's form
    // is `DEF-116-123.spec.ts`'s claim and it already makes it; repeating it
    // here buys nothing and cost this spec two runs — a cycle named `08-A`
    // that this world does not have, then service chips whose codes it does not
    // have either — each time proving NOTHING about the panel this file exists
    // for. `page.request` carries the browser's own session cookie, so it is
    // the same user, the same tenant and the same server; only the button press
    // is skipped, and the SCREEN is still read out of a real browser.
    //
    // The cycle is FOUND, not named: a cycle with no billable account prepares
    // zero customers, which looks exactly like this panel being broken and is
    // not.
    const cycles = await page.request.get(`/api/${tenant()}/cycles?page=1&per=1000`);
    expect(cycles.ok()).toBeTruthy();
    // BR-SHL-011's list envelope is `{count, next, previous, results}` — asserted
    // rather than assumed, because reading `.data` off it gave `undefined` and a
    // TypeError three lines later that said nothing about what was wrong.
    const body = (await cycles.json()) as { results?: { id: string; code: string }[] };
    const cycleRows = body.results ?? [];
    expect(cycleRows.length).toBeGreaterThan(0);

    const iso = (d: Date) => d.toISOString().slice(0, 10);
    // A window no earlier run of this spec can have used - BR-BIL-005 refuses a
    // repeat of (tenant, cycle, period), correctly, and a fixed one would make
    // this spec assert the idempotency rule forever after.
    const monthIndex = Math.floor(Date.now() / 1000) % 12;
    const windowStart = new Date(Date.UTC(2026, monthIndex, 1));
    const windowEnd = new Date(Date.UTC(2026, monthIndex + 1, 0));

    let sentence = "";
    let usedCycle = "";
    for (const cycle of cycleRows) {
      const created = await page.request.post(`/api/${tenant()}/billing/runs`, {
        data: {
          cycle_id: cycle.id,
          period_start: iso(windowStart),
          period_end: iso(windowEnd),
          bill_date: "2026-08-08",
          scope_services: null,
        },
      });
      if (created.status() !== 201) continue; // a duplicate run, or a cycle this world refuses
      const runId = (await created.json()).id as string;

      await page.goto(`/${tenant()}/billing/run?step=2&run=${runId}`);
      const counts = page.locator('[data-brun="shadow-counts"]');
      await counts.waitFor({ timeout: 60_000 }).catch(() => undefined);
      if ((await counts.count()) === 0) continue;
      sentence = (await counts.textContent()) ?? "";
      usedCycle = cycle.code;
      const denominator = Number(/of (\d+) customers/.exec(sentence)?.[1] ?? "0");
      if (denominator > 0) break;
    }
    expect(usedCycle, "no cycle in this world produced a comparison panel").not.toBe("");

    // ⚠ THE ELEMENT, NOT THE PAGE (DEF-2400, and the decision log's own
    // caution): a count that also appears in the page's furniture would let
    // this pass over a panel that never rendered. `sentence` above was read off
    // `[data-brun="shadow-counts"]` and nothing else.

    // Both numbers, in one sentence. "0 came out differently" is also what a
    // comparison that never ran looks like, so the count of customers actually
    // worked out both ways has to be beside it.
    expect(sentence).toMatch(/worked out \d+ of \d+ customers both ways/);
    expect(sentence).toMatch(/\d+ came out differently/);
    expect(sentence).toMatch(/\d+ could not be worked out at all/);

    // eslint-disable-next-line no-console
    console.log(
      `\nPRICING COMPARISON, off the seeded utility (cycle ${usedCycle}):\n  ${sentence.trim()}`,
    );

    // Whatever the verdict, the reader can tell the three states apart: either
    // there is something to rule (a class row) or the panel says in words that
    // nothing came out differently — never a bare silence.
    const anyClass = await page.locator('[data-brun="shadow-class"]').count();
    const saysNone = await page.locator('[data-brun="shadow-none"]').count();
    const measuredNothing = await page.locator('[data-brun="shadow-nothing"]').count();
    expect(anyClass + saysNone + measuredNothing).toBeGreaterThan(0);

    if (anyClass > 0) {
      // ⚠ THE HIGHEST-VALUE ROW IN THE EXERCISE. Both answers are on the row
      // and neither is chosen. Read off the cells rather than the page, for
      // DEF-2400's reason.
      const first = page.locator('[data-brun="shadow-class"]').first();
      const live = await first.locator('[data-brun="shadow-live"]').textContent();
      const ruled = await first.locator('[data-brun="shadow-ruled"]').textContent();
      const touched = await first.locator('[data-brun="shadow-class-accounts"]').textContent();
      // eslint-disable-next-line no-console
      console.log(
        `  first class: ${(await first.textContent())?.slice(0, 200)}\n` +
          `  customers: ${touched}\n  billing today: ${live}\n  the new rules: ${ruled}`,
      );
      expect(Number(touched)).toBeGreaterThan(0);
    }

    await page.screenshot({ path: "e2e-results/step3-pricing-shadow.png" });
  });
});
