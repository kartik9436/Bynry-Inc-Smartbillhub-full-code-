// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-014 (auto-estimate a missing read) · US-MET-015 (the
//           true-up/override half)   Screens: S25
// Rules:    BR-MET-026 (the trailing-3 daily average) · BR-MET-027 (the
//           consecutive cap forces a field visit) · BR-MET-028 (method +
//           consecutive number, NO register value) · BR-MET-062 (a demand peak
//           is NEVER estimated) · BR-SHL-020 (plain-language states) ·
//           CLAUDE.md rule 3 (consumption ALWAYS carries an explicit unit)
// ───────────────────────────────────────────────────────
// TWO THINGS ARE BEING GUARDED HERE AND BOTH ARE THE KIND THAT SHIP SILENTLY.
//
// 1. **A consumption is never rendered without its unit.** 618 kWh and 618 CCF
//    are different bills, and a screen that prints the number alone looks
//    perfectly fine in review. The test feeds a result whose unit the server
//    omitted and asserts the FIGURE DOES NOT APPEAR — not that a warning
//    appears beside it, because a number on screen with a warning beside it is
//    still a number somebody will copy onto a bill.
//
// 2. **A refusal is never rendered as a result.** `POST /reads/estimate`
//    answers 200 for both outcomes. "No history — a field visit is needed" is
//    an answer, and rendering it as an empty estimate (or worse, as 0.000000)
//    would put a fabricated consumption into a bill run.
//
// GT-9's own figure is used as the fixture — 618.000000 kWh — so this suite
// speaks the same numbers as the frozen golden test the engine is measured by.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { READ_CHANNELS } from "@/api/endpoints";
import type { EstimateReadResult } from "@/api/endpoints";

import { EstimateOutcome, EstimateReadModal, estimateSchema } from "./EstimateReadModal";

const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** GT-9's signed estimate: 1,854 kWh over 90 days → 20.6/day × 30 = 618. */
const GT9_ESTIMATE: EstimateReadResult = {
  estimated: true,
  consumption: "618.000000",
  unit: "kWh",
  channel: "total",
  estimation_method: "trailing_3_avg",
  consecutive_estimate_no: 1,
};

/** BR-MET-026's refusal: no actual history at all, so a field visit is forced. */
const NO_HISTORY: EstimateReadResult = {
  estimated: false,
  consumption: null,
  unit: null,
  reason: "no_history",
  detail: { forced_disposition: "field_visit" },
};

/** BR-MET-062: a demand peak is never estimated, and it forces nothing. */
const DEMAND_REFUSED: EstimateReadResult = {
  estimated: false,
  consumption: null,
  unit: null,
  reason: "demand_never_estimated",
  detail: { channel: "demand", rule_ref: "BR-MET-062" },
};

function render(result: EstimateReadResult): string {
  return renderToStaticMarkup(<EstimateOutcome result={result} t={t} />);
}

/** The DIALOG, first paint. No network: nothing is fetched until submit. */
function renderModal(): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads`]}>
        <EstimateReadModal onClose={() => undefined} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DEF-897 — the estimate screen is a DIALOG, like its three siblings", () => {
  it("renders inside a modal, with a Cancel and no page header or back link", () => {
    // PO 2026-08-27, on the live app at v2.61.1: "this can be modal - instead
    // of page". Three of the four S25 actions already opened a dialog and this
    // one navigated away to /reads/estimate.
    const html = renderModal();
    expect(html).toContain('role="dialog"');
    expect(html).toContain(t("metering.estimate.title"));
    expect(html).toContain(t("metering.estimate.kicker"));
    expect(html).toContain(t("forms.cancel"));
    expect(html).toContain(t("metering.estimate.submit"));
    // The three fields are all still there — the container moved, the form did
    // not, and a "fix" that dropped a field would pass the assertions above.
    expect(html).toContain(t("metering.estimate.meterNo"));
    expect(html).toContain(t("metering.estimate.channelLabel"));
    expect(html).toContain(t("metering.estimate.readAt"));
    // The page's own furniture is gone with the page.
    expect(html).not.toContain("metering.estimate.back");
  });

  it("keeps B14 rule 18's measure on the OUTCOME — max-w-measure, NOT max-w-prose", () => {
    // ⚠ `max-w-prose` is a real Tailwind utility and the WRONG cap; that exact
    // confusion is DEF-900. Rule 18's measure is the `--desc-measure` token.
    //
    // ⚠ **IT IS ASSERTED ON THE OUTCOME AND NO LONGER ON THE FORM'S LEDE**,
    // because `MR-14` removed the lede: B14 rule 33 caps RATIONALE at zero
    // words on screen and those 25 words were rationale. Left pointed at the
    // first paint this would have gone red for the right reason and been read
    // as the wrong one.
    const html = render(GT9_ESTIMATE);
    expect(html).toContain("max-w-measure");
    expect(html).not.toContain("max-w-prose");
  });

  it("the schema is unchanged — the container moved, the refusals did not", () => {
    expect(estimateSchema.safeParse({ meter_no: "", channel: "total", read_at: "2026-08-03" }).success).toBe(false);
    expect(estimateSchema.safeParse({ meter_no: "M-7001", channel: "total", read_at: "" }).success).toBe(false);
    expect(
      estimateSchema.safeParse({ meter_no: "M-7001", channel: "total", read_at: "2026-08-03" })
        .success,
    ).toBe(true);
  });
});

/**
 * ⚠ **THE REGISTER TRAP, GUARDED WHERE IT ACTUALLY BITES — ON THE RENDERED
 * OPTIONS (`DEF-MET-5203`, and Q7 is the ruling the PO put first).**
 *
 * The obvious guard here is `expect(ESTIMATE_CHANNELS).toEqual(READ_CHANNELS)`,
 * and it is worthless: the constant IS `READ_CHANNELS` now, so that assertion
 * is a tautology that can never fail — hard-won law 7's *structurally incapable
 * of failing* shape, written on purpose rather than by accident.
 *
 * **What CAN regress is the options map**, which is where the three dead values
 * lived: somebody re-introduces a literal list, or types a label key that
 * resolves in eleven languages over a value the server refuses by name. So this
 * reads the VALUES the dialog actually renders and compares the set against the
 * client's one mirror of `models.CHANNELS`.
 *
 * ⚠ **AND IT IS ASSERTED AS A SET EQUALITY IN BOTH DIRECTIONS.** A subset check
 * would pass on a dialog that offered only `total` — which is precisely the
 * state the defect left the product in: of five choices exactly one could
 * produce an estimate.
 */
function registerOptionValues(html: string): string[] {
  const select = /<select[^>]*id="channel"[\s\S]*?<\/select>/.exec(html);
  if (select === null) return [];
  return [...select[0].matchAll(/<option value="([^"]*)"/g)]
    .map((match) => match[1])
    .filter((value) => value !== "");
}

describe("DEF-MET-5203 — the dialog offers the registers the SERVER knows", () => {
  it("every rendered register is one the server accepts, and all seven are offered", () => {
    // The dialog posted `peak`, `mid_peak` and `off_peak`; the server knows
    // `tou_on`, `tou_mid`, `tou_off`. Proved on the running stack by posting
    // each with a meter number that cannot exist, so the refusal fired before
    // anything could be written: three came back "not a register on this
    // meter." A time-of-use meter short of its mid-peak window before a bill
    // run could not be estimated from this dialog at all.
    const offered = registerOptionValues(renderModal());
    expect([...offered].sort()).toEqual([...READ_CHANNELS].sort());
  });

  it("no register reaches the clerk as an internal code (B14 rule 31)", () => {
    // The words are BR-MET-170 (3)'s own — *Total register · On-peak ·
    // Mid-peak · Off-peak · Demand · Export · Generation* — the same seven the
    // reads list and the chase panel print. `tou_mid` is not a word this
    // product uses anywhere a person can see.
    const html = renderModal();
    for (const code of READ_CHANNELS) {
      expect(html).toContain(t(`metering.reads.channel.${code}`));
    }
    expect(html).not.toContain(">tou_mid<");
    expect(html).not.toContain(">tou_on<");
  });

  it("BR-MET-062: demand is still OFFERED, and the refusal is what explains it", () => {
    // Deliberate, and the opposite of hiding it. A clerk with a missing demand
    // peak needs to learn WHY it cannot be estimated, once — not to find the
    // option gone and try again tomorrow. The blueprint's floor note says the
    // same in five words: "A demand register is never estimated."
    expect(registerOptionValues(renderModal())).toContain("demand");
    expect(render(DEMAND_REFUSED)).toContain(t("metering.estimate.reason.demand_never_estimated"));
  });

  it("the register is read BACK in words, because an estimate cannot be re-registered", () => {
    // Q7: `supersede_read` takes only a value and a reason and migration 0007's
    // trigger freezes the channel, so a reading filed against the wrong
    // register is PERMANENT. The outcome panel is the last place a clerk can
    // catch it, and it printed `tou_mid` at them.
    const onMidPeak: EstimateReadResult = { ...GT9_ESTIMATE, channel: "tou_mid" };
    const html = render(onMidPeak);
    expect(html).toContain(t("metering.reads.channel.tou_mid"));
    expect(html).not.toContain(">tou_mid<");
  });

  it("the method is read back in words too (B14 rule 31)", () => {
    // It printed `trailing_3_daily_avg`. The product already holds the seven
    // method NAMES the Settings screen offers, so the clerk reads the same word
    // as the person who chose the method.
    const known: EstimateReadResult = { ...GT9_ESTIMATE, estimation_method: "trailing_3_daily_avg" };
    const html = render(known);
    expect(html).toContain(t("settings.rules.choice.est_method.trailing_3_daily_avg"));
    expect(html).not.toContain(">trailing_3_daily_avg<");
    // A method nobody named still falls back to itself rather than to silence —
    // a reason nobody translated is still a reason (BR-SHL-020).
    expect(render({ ...GT9_ESTIMATE, estimation_method: "nobody_named_this" })).toContain(
      "nobody_named_this",
    );
  });
});

describe("US-MET-014 — the estimate screen and CLAUDE.md rule 3", () => {
  it("renders the consumption WITH its unit, never the bare number", () => {
    // ⚠ **THE FIGURE IS `618`, NOT `618.000000` — `BR-MET-144`.** At most two
    // decimals, trailing zeros TRIMMED, storage unmoved: `8.000000` is `8` and
    // never `8.00`, because a quantity's precision is what the meter measured
    // rather than a property of a currency. This screen was the one reads
    // surface still printing the served decimal string raw.
    const html = render(GT9_ESTIMATE);
    expect(html).toContain(">618<");
    expect(html).toContain("kWh");
    // …and the six zeros are GONE rather than merely joined by a unit.
    expect(html).not.toContain("618.000000");
    // The two are adjacent in one figure, not in unrelated corners of the page.
    expect(html).toMatch(/>618<\/span>\s*<span[^>]*>kWh/);
  });

  it("RULE 3 · a consumption with no unit is NOT rendered at all", () => {
    // Should be impossible — the engine always sets a unit — so if it ever
    // happens the screen must refuse to print the figure rather than print it
    // unlabelled. A number with a warning beside it is still a number somebody
    // copies onto a bill.
    // ⚠ The assertion is on the FORMATTED figure (`BR-MET-144`), not on the
    // served string. Asserting `618.000000` here would be a guard that can no
    // longer fail — the screen stopped printing that form for every result,
    // refusal or not — which is the *structurally incapable of failing* shape
    // hard-won law 7 names.
    const unitless: EstimateReadResult = { ...GT9_ESTIMATE, unit: null };
    const html = render(unitless);
    expect(html).not.toContain(">618<");
    expect(html).toContain(t("metering.estimate.noUnit"));
  });

  it("BR-MET-028 · the method and the consecutive number are on screen", () => {
    const html = render(GT9_ESTIMATE);
    expect(html).toContain("trailing_3_avg");
    // And the screen says no dial reading was stored, so nobody looks for one.
    expect(html).toContain(t("metering.estimate.noRegister"));
  });

  it("a refusal is an ANSWER — never an empty estimate and never a zero", () => {
    const html = render(NO_HISTORY);
    expect(html).toContain(t("metering.estimate.refusedTitle"));
    expect(html).toContain(t("metering.estimate.reason.no_history"));
    // The three ways this could go wrong, each excluded by name.
    expect(html).not.toContain(t("metering.estimate.madeTitle"));
    expect(html).not.toContain("0.000000");
    expect(html).not.toContain(t("metering.estimate.consumption"));
  });

  it("BR-MET-026/027 · a forced field visit says so, in words", () => {
    expect(render(NO_HISTORY)).toContain(t("metering.estimate.fieldVisit"));
    // BR-MET-062 refuses WITHOUT forcing a visit — the sentence must not leak
    // onto a refusal that did not carry `forced_disposition`.
    expect(render(DEMAND_REFUSED)).not.toContain(t("metering.estimate.fieldVisit"));
  });

  it("BR-MET-062 · the demand refusal explains itself rather than hiding", () => {
    const html = render(DEMAND_REFUSED);
    expect(html).toContain(t("metering.estimate.reason.demand_never_estimated"));
  });

  it("an untranslated reason code still reaches the user (BR-SHL-020)", () => {
    const odd: EstimateReadResult = {
      ...NO_HISTORY,
      reason: "a_reason_nobody_wrote_a_string_for",
      detail: null,
    };
    // A reason nobody translated is still a reason. Silence is the defect.
    expect(render(odd)).toContain("a_reason_nobody_wrote_a_string_for");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-014@feddf11 (EP-MET-05, co-story US-MET-015; ships with features/metering/EstimateReadModal.tsx)
// generated: 2026-08-16 by story-coder (unreachable-screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — not a 🔒 path: quantities only; no money figure, rate or rounding is asserted here)
// gates: vitest 7 passed✔ · tsc✔ · eslint --max-warnings 0✔ · RED-PROVED TWICE: (1) removing the unit check renders `<span data-cell="estimate-value">618.000000</span> <span data-cell="estimate-unit"></span>` (the classes were `rd-est-value`/`rd-est-unit` until CR-054 W0 T3 moved this file to Tailwind) and the rule-3 TC fails with "expected … not to contain '618.000000'"; (2) treating the refusal as a result renders "Estimate recorded" over an empty consumption and four TCs go red
// exceptions: the fixture is GT-9's own signed figure (618.000000 kWh from 1,854 kWh over 90 days) so this suite speaks the same numbers as the frozen golden test the engine is measured by — deliberate, not a coincidence to be tidied away
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
