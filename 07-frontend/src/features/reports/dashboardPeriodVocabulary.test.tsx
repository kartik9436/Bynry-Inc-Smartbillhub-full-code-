// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.15`.
//          *"Amend A1, and add the one assertion that stops the drift running
//          the other way: the control is drawn from `period_filter.options`,
//          never from a front-end constant."*
//          Outcome: *"a test fails if the front end hardcodes the vocabulary"*.
// Rules:   BR-REP-035 (CONFIRMED-AS-AMENDED — `CR-029` `D8①` 2026-08-23
//          withdrew the completed-cycle window, PO verbatim *"dont build
//          it"*, `OQ-268` CLOSED-WITHDRAWN) · BR-REP-006 (a vocabulary
//          enumerates the LIVE set, never a hardcoded list) · BR-SHL-011
//          (an unknown `f.period` falls back and answers 200)
// Defect:  DEF-REP-6808 — A1 described the withdrawn window for a month
// ───────────────────────────────────────────────────────
/**
 * THE DASHBOARD PERIOD MENU IS THE SERVER'S LIST AND NOBODY ELSE'S.
 *
 * ⚠ **THE DRIFT THIS STOPS RUNS BOTH WAYS, AND ONLY ONE DIRECTION HAS EVER
 * BEEN CHECKED.** A1 described four windows for a month after the PO withdrew
 * one — that is the DOCUMENT drifting from the code, and it cost `P0.15`.
 * The mirror is worse and nothing looked for it: a front end that spells the
 * four ids into a constant renders a menu the server does not serve, the
 * withdrawn option comes BACK on screen, and choosing it sends
 * `f.period=last_cycle` — which `BR-SHL-011` makes the server fall back on,
 * silently and correctly, to a DIFFERENT window from the one the clerk picked.
 * Nothing 500s, nothing is logged, and the figures are right for a period
 * nobody asked for.
 *
 * ⚠ **SO THE FIXTURE BELOW USES A VOCABULARY THE PRODUCT HAS NEVER HEARD OF.**
 * If it used the real three, a hardcoded constant would pass by coincidence —
 * which is exactly the false pass law 7's second habit asks about. `fortnight`
 * and `since_go_live` are not `dashboard_period.OPTION_ORDER` values and never
 * will be; only a control reading its own `options` prop can render them.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { DashboardPeriodOption } from "@/api/endpoints";
import { PeriodBar } from "@/features/reports/DashboardPage";

const t = ((key: string) => key) as never;

function option(id: string, start: string, end: string): DashboardPeriodOption {
  return { id, start, end, cycle_code: null, cycle_name: null, fy_label: null, period_no: null };
}

/** Two ids no constant in this codebase contains, and one that never returns. */
const INVENTED = [
  option("fortnight", "2026-08-06", "2026-08-19"),
  option("since_go_live", "2026-01-01", "2026-08-19"),
];

function renderBar(options: DashboardPeriodOption[], selected: string) {
  return renderToStaticMarkup(
    <PeriodBar
      filter={{ selected, default: options[0]?.id ?? null, options }}
      asOf="2026-08-19"
      ageMinutes={null}
      onSelect={() => undefined}
      t={t}
    />,
  );
}

function optionValues(html: string): string[] {
  return [...html.matchAll(/<option value="([^"]*)"/g)].map((match) => match[1]);
}

describe("CR-142 P0.15 — the period control enumerates the server's options", () => {
  it("renders exactly the ids the payload carries, and no others", () => {
    const values = optionValues(renderBar(INVENTED, "fortnight"));
    expect(
      values,
      "The period menu must be built from `period_filter.options`. A value " +
        "here that the payload did not carry is a front-end constant, and a " +
        "constant is how the withdrawn `last_cycle` window comes back on " +
        "screen after `CR-029` `D8①` removed it.",
    ).toEqual(["fortnight", "since_go_live"]);
  });

  it("never re-adds the window CR-029 D8① withdrew", () => {
    // The named case, because `last_cycle` is still a recognised TOKEN on the
    // server (a shared link must keep resolving) and that is exactly the kind
    // of half-alive value a front end copies into a list.
    const html = renderBar(INVENTED, "fortnight");
    expect(
      html.includes('value="last_cycle"'),
      "`last_cycle` is a token the server still RECOGNISES and never OFFERS. " +
        "It appearing here means the menu is not the server's list.",
    ).toBe(false);
  });

  it("a one-option payload renders one option", () => {
    // A tenant with no fiscal calendar gets exactly this: the two accounting
    // windows are not offered at all. A hardcoded three would draw them.
    const values = optionValues(renderBar([option("last_30_days", "2026-07-21", "2026-08-19")], "last_30_days"));
    expect(values).toEqual(["last_30_days"]);
  });

  it("an empty payload draws no control at all", () => {
    // Not `null` and not an empty `<select>`: an empty picker is a control
    // that looks operable and is not (hard-won law 2's mirror).
    expect(renderBar([], "")).toBe("");
  });
});
