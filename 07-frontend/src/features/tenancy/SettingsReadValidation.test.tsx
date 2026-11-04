// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 · AMENDMENT 1 — S64 per-service VEE settings (PO 2026-08-26).
//           Screens: S64
// Rules:    BR-MET-020 (the fail-safe "skipped and reported" state is RENDERED,
//           never a zero) · BR-SHL-025 (view-only = disabled WITH the reason) ·
//           CLAUDE.md rule 2 (decimals stay strings; trimming is string
//           surgery, no float is ever made from a figure) · rule 3 (the floor
//           shows its unit) · B14 r21 (no new stylesheet class — asserted by
//           G31 at integration; this file asserts the BODY)
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReadValidationOverview, ReadValidationServiceEntry } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { queryKeys } from "@/api/queryClient";

import {
  EST_METHOD_CODES,
  ReadValidationRulesView,
  SERVICE_FIGURE_FIELDS,
  draftFromEntry,
  readValidationKey,
  sameFigure,
  serviceChanges,
  serviceDraftProblems,
  switchChanges,
  switchesMoved,
  trimDecimalString,
} from "./SettingsReadValidation";
import type { ServiceDraft } from "./SettingsReadValidation";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * The switchable vocabulary as the ENGINE serves it (validation.JUDGMENT_RULES,
 * catalog order). Spelled once here so a rule added to the engine and not to
 * this fixture is a visible diff rather than a silently thinner screen.
 */
const JUDGMENT_RULES = [
  "zero",
  "high",
  "low",
  "days_threshold",
  "out_of_window",
  "vacant_unit",
  "tou_sum_sanity",
  "mismatch",
  "factor_flag",
  "generation_channel",
  "plan_registers",
  "cycle_membership",
  "service_coherence",
];

/** BR-MET-136 clause 2: the server EXPANDS the map, and every rule ships on. */
const ALL_ON: Record<string, boolean> = Object.fromEntries(
  JUDGMENT_RULES.map((rule) => [rule, true]),
);

const ELECTRIC: ReadValidationServiceEntry = {
  service: "electric",
  source: "service",
  rule_enabled: ALL_ON,
  high_pct: "200.000000",
  high_abs_value: "50.000000",
  high_abs_unit: "kWh",
  low_pct: "25.000000",
  zero_scope: "active_non_vacant",
  days_flag_min: 25,
  days_flag_max: 35,
  days_hard_min: 20,
  days_hard_max: 45,
  mismatch_pct: "3.000000",
  tou_sum_tolerance_pct: "1.000000",
};

const WATER_FALLBACK: ReadValidationServiceEntry = {
  ...ELECTRIC,
  service: "water",
  source: "tenant_fallback",
  high_abs_value: "1.000000",
  high_abs_unit: "kgal",
};

const GAS_NONE: ReadValidationServiceEntry = {
  service: "gas",
  source: "none",
  unit_hint: "ccf",
  rule_enabled: ALL_ON,
};

const OVERVIEW: ReadValidationOverview = {
  general: { present: true, est_method: "trailing_3_daily_avg", est_max_consecutive: 2 },
  services: [ELECTRIC, WATER_FALLBACK, GAS_NONE],
  integrity_rules: [
    "unknown_meter",
    "retired_meter",
    "unit_missing",
    "negative_usage",
    "rollover",
    "duplicate",
    "export_not_net",
  ],
  judgment_rules: JUDGMENT_RULES,
  legacy_fallback_services: ["electric", "water"],
};

/**
 * DEF-901: a SEWER entry, because the defect was reported about sewer and
 * because the rule under test is explicitly NOT "sewer never has meters".
 */
const SEWER: ReadValidationServiceEntry = {
  ...ELECTRIC,
  service: "sewer",
  high_abs_value: "1.000000",
  high_abs_unit: "kgal",
};

/**
 * `metered` is DEF-901's estate probe (`GET /assets/metered-services`).
 * `undefined` seeds nothing, which is the loading-or-failed state — and the
 * state every pre-DEF-901 case in this file renders in, unchanged, because
 * BR-TEN-162 clause 3 fails toward SHOWING.
 */
function renderPage(
  overview: ReadValidationOverview = OVERVIEW,
  readOnly = false,
  metered?: string[],
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(readValidationKey(), overview);
  if (metered !== undefined) {
    queryClient.setQueryData(queryKeys.meteredServices, metered);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <ReadValidationRulesView readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ── the string law (CLAUDE.md rule 2) ──────────────────────────────────────
describe("decimals stay strings — trimming is string surgery", () => {
  it("trims stored 6dp noise without touching the number", () => {
    expect(trimDecimalString("200.000000")).toBe("200");
    expect(trimDecimalString("3.500000")).toBe("3.5");
    expect(trimDecimalString("0.125000")).toBe("0.125");
    expect(trimDecimalString("-1.100000")).toBe("-1.1");
    // not a plain decimal → untouched, never coerced
    expect(trimDecimalString("kWh")).toBe("kWh");
    expect(trimDecimalString("25")).toBe("25");
  });

  it("sameFigure equates a stored figure with its typed form", () => {
    expect(sameFigure("250", "250.000000")).toBe(true);
    expect(sameFigure("250.5", "250.500000")).toBe(true);
    expect(sameFigure("250", "251.000000")).toBe(false);
  });
});

// ── draft mechanics ────────────────────────────────────────────────────────
describe("draftFromEntry and serviceChanges", () => {
  it("a configured service opens trimmed; a partial edit sends ONLY what changed", () => {
    const original = draftFromEntry(ELECTRIC);
    expect(original.high_pct).toBe("200");
    expect(original.days_flag_min).toBe("25");
    const edited: ServiceDraft = { ...original, high_pct: "250" };
    expect(serviceChanges(edited, original)).toEqual({ high_pct: "250" });
  });

  it("day bounds travel as integers, figures as the typed strings", () => {
    const original = draftFromEntry(ELECTRIC);
    const edited: ServiceDraft = { ...original, days_hard_max: "60", mismatch_pct: "4.5" };
    expect(serviceChanges(edited, original)).toEqual({ days_hard_max: 60, mismatch_pct: "4.5" });
  });

  it("an unconfigured service opens EMPTY with the unit prefilled — and a create sends every field", () => {
    const draft = draftFromEntry(GAS_NONE);
    expect(draft.high_abs_unit).toBe("ccf"); // the tenant's own billed unit
    expect(draft.high_pct).toBe("");
    const filled: ServiceDraft = {
      high_pct: "200",
      high_abs_value: "5",
      high_abs_unit: "ccf",
      low_pct: "25",
      zero_scope: "active_non_vacant",
      days_flag_min: "25",
      days_flag_max: "35",
      days_hard_min: "20",
      days_hard_max: "45",
      mismatch_pct: "3",
      tou_sum_tolerance_pct: "1",
    };
    const sent = serviceChanges(filled, null);
    expect(Object.keys(sent).sort()).toEqual([...SERVICE_FIGURE_FIELDS].sort());
    expect(sent.days_flag_min).toBe(25);
  });
});

// ── the nonsense-refusal law (client mirror; the server is the authority) ──
describe("serviceDraftProblems refuses structural nonsense", () => {
  const good = draftFromEntry(ELECTRIC);

  it("a clean draft has no problems", () => {
    expect(serviceDraftProblems(good, t)).toEqual({});
  });

  it("percentages must be above zero", () => {
    expect(serviceDraftProblems({ ...good, high_pct: "0" }, t).high_pct).toContain(
      "more than zero",
    );
    expect(serviceDraftProblems({ ...good, high_pct: "-10" }, t).high_pct).toContain(
      "more than zero",
    );
    expect(
      serviceDraftProblems({ ...good, tou_sum_tolerance_pct: "0" }, t).tou_sum_tolerance_pct,
    ).toContain("more than zero");
  });

  it("floors cannot be negative; low sits in (0, 100]", () => {
    expect(serviceDraftProblems({ ...good, high_abs_value: "-1" }, t).high_abs_value).toContain(
      "negative",
    );
    expect(serviceDraftProblems({ ...good, low_pct: "150" }, t).low_pct).toContain("up to 100");
  });

  it("the hard window must CONTAIN the flag window", () => {
    const narrowHard = serviceDraftProblems({ ...good, days_hard_min: "30" }, t);
    expect(narrowHard.days_flag_min).toContain("has to sit inside the hard window");
    const wideFlag = serviceDraftProblems({ ...good, days_flag_max: "50" }, t);
    expect(wideFlag.days_flag_min).toContain("has to sit inside the hard window");
  });

  it("each window must be a real window, and bounds start at 1", () => {
    expect(serviceDraftProblems({ ...good, days_flag_min: "40" }, t).days_flag_max).toContain(
      "the first number must be the smaller one",
    );
    expect(serviceDraftProblems({ ...good, days_hard_min: "0" }, t).days_hard_min).toContain(
      "start at 1",
    );
  });

  it("a non-number is named, never coerced", () => {
    expect(serviceDraftProblems({ ...good, high_pct: "lots" }, t).high_pct).toContain("number");
  });
});

// ── the rendered page ──────────────────────────────────────────────────────
describe("S64 renders every enabled service honestly", () => {
  it("one panel per enabled service, in the server's order, with units shown", () => {
    const html = renderPage();
    expect(html).toContain("Electric");
    expect(html).toContain("Water");
    expect(html).toContain("Gas");
    expect(html.indexOf("Electric")).toBeLessThan(html.indexOf("Water"));
    expect(html.indexOf("Water")).toBeLessThan(html.indexOf("Gas"));
    // Editable thresholds with their units (rule 3): the electric floor's
    // help names kWh, and the value arrives trimmed of stored-scale noise.
    expect(html).toContain("kWh");
    expect(html).toContain('value="200"');
    expect(html).toContain("High-use threshold");
  });

  it("the integrity rules are listed and visibly locked, with the sentence why", () => {
    const html = renderPage();
    expect(html).toContain("Integrity checks");
    expect(html).toContain("cannot be switched off");
    for (const rule of OVERVIEW.integrity_rules) {
      expect(html).toContain(`data-integrity-rule="${rule}"`);
    }
    expect(html).toContain("Unknown meter");
    expect(html).toContain("Negative usage");
    expect(html).toContain("Always runs");
  });

  it("BR-MET-020: a service with no figures says 'skipped and reported' — never a zero", () => {
    // ⚠ RENDERED WITH GAS ALONE SINCE 2026-08-27 (DEF-900), and the reason is
    // worth the line: the PO ruled each service into an expand/collapse panel
    // (*"for each utilitu service you can make expand and collapse"*), so only
    // the FIRST panel lands open and this suite renders statically — it cannot
    // click. Asserting a collapsed panel's body would assert nothing.
    // The test proves exactly what it always proved, on a one-service tenant:
    // a service with no figures says so in WORDS and shows no invented number.
    const html = renderPage({ ...OVERVIEW, services: [GAS_NONE] });
    expect(html).toContain('data-source="none"');
    expect(html).toContain("skipped and reported");
    expect(html).toContain("Set thresholds for Gas");
    // No invented figure appears in the gas panel: the fail-safe is words,
    // not a form pre-filled with another service's numbers.
    expect(html).not.toContain('value="undefined"');
  });

  it("an electric/water fallback panel says WHOSE figures govern", () => {
    // Rendered with the fallback service alone, for the reason on the test
    // above: one panel opens, and this suite renders without interacting.
    const html = renderPage({ ...OVERVIEW, services: [WATER_FALLBACK] });
    expect(html).toContain('data-source="tenant_fallback"');
    // The wording lost its second sentence in DEF-MET-4479; what it PROVES —
    // that the panel names whose figures govern — is unchanged.
    expect(html).toContain("the tenant-wide ones here judge its readings");
  });

  it("the estimation panel is tenant-wide and its method is now a CHOICE", () => {
    // ⚠ THIS CASE ASSERTED `readonly` UNTIL 2026-09-07. The method was a fixed
    // box because BR-MET-026 named exactly one; the PO ruled seven (CR-079),
    // so the assertion that used to be the point is now the defect. What
    // survives unchanged is that the panel is TENANT-WIDE and that the stored
    // figures reach it.
    const html = renderPage();
    expect(html).toContain("Estimation — all services");
    expect(html).toContain("Daily average of the last 3 periods");
    expect(html).toContain('<select id="rv-est_method"');
    expect(html).toContain('value="2"'); // est_max_consecutive
  });

  it("BR-SHL-025: a view-only role gets Save disabled WITH its reason", () => {
    const html = renderPage(OVERVIEW, true);
    expect(html).toContain("Save Electric thresholds");
    expect(html).toContain("disabled");
    expect(html).toContain("Your role can view this, but not change it.");
    // …and the create door for the unconfigured service is not offered.
    expect(html).not.toContain("Set thresholds for Gas");
  });
});

// ── BR-MET-136 · the per-rule switch (the S64 follow-up) ───────────────────
describe("BR-MET-136 — a judgment rule can be switched off, an integrity rule cannot", () => {
  it("every judgment rule is drawn as a checkbox, checked, from the SERVED list", () => {
    // WOULD CATCH: the screen hard-coding the rule list, or drawing a rule
    // unchecked that the server said was on. Clause 2 is "default ALL ENABLED",
    // and this is that default made visible on a page a person actually reads.
    const html = renderPage();
    expect(html).toContain('data-checks-for="electric"');
    for (const rule of JUDGMENT_RULES) {
      expect(html).toContain(`data-rule="${rule}"`);
      expect(html).toContain(`id="rv-electric-rule-${rule}"`);
    }
    expect(html).toContain('data-rule-enabled="true"');
    expect(html).not.toContain('data-rule-enabled="false"');
    expect(html).toContain("Which checks run");
  });

  it("RED PROOF: an integrity rule renders LOCKED, with no input and a stated reason", () => {
    // WOULD CATCH: the integrity rules rendered as disabled CHECKBOXES —
    // greyed-out controls with no explanation, which read as "broken" or "not
    // your permission level" rather than "this cannot be turned off"
    // (BR-SHL-025). PROVED RED by rendering them through CheckboxField with
    // `checked` and no locked row: the assertion below on the absence of
    // `id="rv-electric-rule-duplicate"` failed, because a switchable-looking
    // control existed for a rule the server refuses to switch.
    const html = renderPage();
    expect(html).toContain("Checks that cannot be turned off");
    for (const rule of OVERVIEW.integrity_rules) {
      expect(html).toContain(`data-locked-rule="${rule}"`);
      // …and NO input for it: nothing to click, so nothing to wonder about
      expect(html).not.toContain(`id="rv-electric-rule-${rule}"`);
    }
    expect(html).toContain("Locked");
    expect(html).toContain("Always runs");
    expect(html).toContain("These protect the data itself.");
    // the five rules S64 used to render as raw identifiers now read as English
    expect(html).toContain("Export without a net meter");
    expect(html).toContain("Registers the plan expects");
  });

  it("a switched-off rule shows as off and says what a clerk will see on the reading", () => {
    // WOULD CATCH: a screen that renders a disabled check identically to an
    // enabled one — and the admin never learning that BR-MET-136's trailing
    // clause puts the words on every reading.
    const withOff: ReadValidationOverview = {
      ...OVERVIEW,
      services: [{ ...ELECTRIC, rule_enabled: { ...ALL_ON, vacant_unit: false } }],
    };
    const html = renderPage(withOff);
    expect(html).toContain('data-rule-enabled="false"');
    expect(html).toContain('data-checks-off-count="1"');
    expect(html).toContain("Each reading will say it was turned off.");
  });

  it("BR-SHL-025: a view-only role reads the setting, it is not offered as an input", () => {
    // WOULD CATCH: a checkbox a viewer can click that silently does nothing.
    const html = renderPage(OVERVIEW, true);
    expect(html).not.toContain('id="rv-electric-rule-zero"');
    expect(html).toContain("Zero usage — on");
  });
});

describe("BR-MET-136 — what a save SENDS", () => {
  it("only the rules that moved travel, so naming one never re-enables the rest", () => {
    // WOULD CATCH: the whole map being sent, which the server merges — so a
    // save about the zero check would silently restate twelve other decisions.
    const moved = switchChanges({ ...ALL_ON, zero: false }, ALL_ON);
    expect(moved).toEqual({ zero: false });
    expect(switchesMoved({ ...ALL_ON, zero: false }, ALL_ON)).toBe(true);
  });

  it("an unchanged map sends nothing at all", () => {
    // WOULD CATCH: an empty `{}` shipped on every save — a change to nothing
    // that the server then has to have an opinion about.
    expect(switchChanges(ALL_ON, ALL_ON)).toEqual({});
    expect(switchesMoved(ALL_ON, ALL_ON)).toBe(false);
  });

  it("switching a rule back ON is a change too", () => {
    // WOULD CATCH: a diff that only notices switching OFF, so re-enabling a
    // check quietly never reaches the server.
    expect(switchChanges(ALL_ON, { ...ALL_ON, zero: false })).toEqual({ zero: true });
  });

  it("a CREATE sends only the checks turned OFF, never thirteen explicit trues", () => {
    // WOULD CATCH: the create path shipping the whole map. It would store
    // thirteen `true`s — choices nobody made, which in the row are
    // indistinguishable from choices somebody did, and which the audit trail
    // would then have to pretend to explain. A brand-new service with nothing
    // switched off sends NO switch key at all and inherits the ratified
    // default from the column.
    expect(switchChanges(ALL_ON, ALL_ON)).toEqual({});
    expect(switchChanges({ ...ALL_ON, vacant_unit: false }, ALL_ON)).toEqual({
      vacant_unit: false,
    });
  });

  it("an integrity rule is not a key the screen can even produce", () => {
    // WOULD CATCH: the screen offering a control whose payload the server
    // refuses — the refusal is the last line of defence, not the first.
    for (const rule of OVERVIEW.integrity_rules) {
      expect(Object.keys(ALL_ON)).not.toContain(rule);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-038 Amendment 1 (2026-08-26)
// generated: 2026-08-26 by the CR-038 A1 S64 lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// DEF-901 — thresholds are offered only where a reading can be taken
// PO verbatim, on the live app at v2.61.1: *"are these settings applicable to
// sewer"*. BR-TEN-162: the test is the tenant's own ESTATE, never the service
// code.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-901 — a service with no meters gets a sentence, not a form", () => {
  // ⚠ **THE SHAPE MOVED ON 2026-09-07 AND THE RULE DID NOT (DEF-MET-4479).**
  // DEF-901 gave each unmetered service its own collapsed panel carrying two
  // sentences. Nine of those is noise, so they are now ONE line above the
  // estimation panel naming every one of them. Everything DEF-901 actually
  // proved still has a case below: no form is offered, no Save button is
  // offered, and the service is NAMED rather than dropped.
  it("withholds the threshold form and says why, for an unmetered service", () => {
    // The estate: sewer is not metered, electric is. Both are ENABLED — which
    // is the entire test the broken page applied.
    const overview: ReadValidationOverview = {
      ...OVERVIEW,
      services: [SEWER, ELECTRIC],
    };
    const html = renderPage(overview, false, ["electric"]);

    expect(html).toContain('data-metered="false"');
    expect(html).toContain(t("metering.readValidation.notMetered.line"));
    // …and NOT the fourteen inputs, nor the Save button behind them.
    expect(html).not.toContain('id="rv-sewer-high_pct"');
    expect(html).not.toContain(
      t("metering.readValidation.save", { service: t("rating.service.sewer") }),
    );
  });

  it("the metered service in the same page keeps its form in full", () => {
    const overview: ReadValidationOverview = { ...OVERVIEW, services: [ELECTRIC, SEWER] };
    const html = renderPage(overview, false, ["electric"]);
    expect(html).toContain('id="rv-electric-high_pct"');
    // sewer is on the shared line, and electric is NOT on it
    expect(html).toContain('data-service-listed="sewer" data-metered="false"');
    expect(html).not.toContain('data-service-listed="electric" data-metered="false"');
  });

  it("the service is still DRAWN — a missing section reads as a broken page", () => {
    const overview: ReadValidationOverview = { ...OVERVIEW, services: [SEWER, ELECTRIC] };
    const html = renderPage(overview, false, ["electric"]);
    // BR-TEN-162 clause 2: honest absence, not absence. The NAME is on the
    // page and so is the reason — one line instead of a panel.
    expect(html).toContain(t("rating.service.sewer"));
    expect(html).toContain('data-service-listed="sewer"');
    expect(html).toContain(t("metering.readValidation.notMetered.line"));
  });

  it("THE RULE IS NOT 'sewer never has meters' — a metered sewer gets the form", () => {
    // A utility that genuinely meters sewer. A hard-coded set of unmetered
    // service codes passes every other case here and fails this one, which is
    // exactly what it is for.
    const overview: ReadValidationOverview = { ...OVERVIEW, services: [SEWER] };
    const html = renderPage(overview, false, ["sewer"]);
    expect(html).toContain('id="rv-sewer-high_pct"');
    expect(html).not.toContain('data-metered="false"');
  });

  it("FAILS TOWARD SHOWING when the estate is unknown (BR-TEN-162 clause 3)", () => {
    // The probe has not answered — still loading, or it failed. Hiding
    // configuration a tenant needs is the expensive direction, so every form
    // is drawn. This is also why the 26 cases above this block did not move.
    const overview: ReadValidationOverview = { ...OVERVIEW, services: [SEWER, ELECTRIC] };
    const html = renderPage(overview, false, undefined);
    expect(html).not.toContain('data-metered="false"');
    expect(html).toContain('id="rv-sewer-high_pct"');
  });

  it("an unmetered service does NOT fall through to the 'no figures yet' invitation", () => {
    // Both are honest-absence states and only one of them is true. *"No
    // figures yet — enter some"* invites work on a form that can never run,
    // which is the defect wearing the fix's clothes.
    const unmeteredAndUnconfigured: ReadValidationServiceEntry = {
      service: "trash",
      source: "none",
      unit_hint: null,
      rule_enabled: ALL_ON,
    };
    const overview: ReadValidationOverview = {
      ...OVERVIEW,
      services: [unmeteredAndUnconfigured],
    };
    const html = renderPage(overview, false, ["water"]);
    expect(html).toContain('data-metered="false"');
    expect(html).not.toContain('data-source="none"');
    expect(html).not.toContain(
      t("metering.readValidation.setUp", { service: t("rating.service.trash") }),
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-MET-4480 — THE PAGE MUST NEVER END IN SILENCE
//
// PO, build 2.217.0, two screenshots of one URL minutes apart: one carried
// Electric, Water, Sewer, Trash and Storm water; the other stopped dead after
// the integrity chips. REPRODUCED in a browser on 2026-09-07 by switching the
// tenant's services off — `services: []` renders the intro, the integrity
// panel and then NOTHING, and a page with nothing after its first panel reads
// as a finished page. The map over an empty array is the silence.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-MET-4480 — an absent section says it is absent", () => {
  it("no services switched on: the page SAYS so instead of ending after the chips", () => {
    // WOULD CATCH: the exact reported page. Before this, `services: []`
    // rendered the integrity panel and then jumped straight to the estimation
    // panel with not one word about the missing sections.
    const html = renderPage({ ...OVERVIEW, services: [] });
    expect(html).toContain('data-no-services="true"');
    expect(html).toContain("No services are switched on");
  });

  it("every service the tenant sells is NAMED on the page, metered or not", () => {
    // WOULD CATCH: a section quietly dropped. The page is the whole picture or
    // it is misleading — there is no third state.
    const overview: ReadValidationOverview = {
      ...OVERVIEW,
      services: [ELECTRIC, WATER_FALLBACK, SEWER, GAS_NONE],
    };
    const html = renderPage(overview, false, ["electric", "water"]);
    for (const entry of overview.services) {
      expect(html).toContain(`data-service-listed="${entry.service}"`);
    }
  });

  it("EVERY service unmetered still leaves a page that speaks", () => {
    // The worst case for the silence: nothing to draw a form for at all.
    const overview: ReadValidationOverview = { ...OVERVIEW, services: [SEWER, GAS_NONE] };
    const html = renderPage(overview, false, []);
    expect(html).toContain('data-unmetered-line="true"');
    expect(html).toContain('data-service-listed="sewer"');
    expect(html).toContain('data-service-listed="gas"');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-MET-4479 — TWO INPUTS IN A ROW SHARE A TOP EDGE, AND THE PAGE STOPS
// EXPLAINING ITSELF (B14 rule 32)
//
// MEASURED IN A BROWSER on 2026-09-07 before the fix: `rv-electric-days_hard_min`
// sat at y=1450 and `rv-electric-days_hard_max` at y=1398 — 52px apart in one
// row, because the left field carried a help line and the right did not.
// `grid-rows-subgrid` cannot fix that: subgrid assigns children to tracks IN
// SOURCE ORDER, so a field with no help puts its INPUT on the help row.
// The cure is structural — no field in this grid carries help at all.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-MET-4479 — the thresholds grid has no help lines to disagree about", () => {
  it("not one field in the grid carries a help line", () => {
    // WOULD CATCH: a help sentence added back under any label, which is what
    // pushes one column's input below the other's.
    const html = renderPage({ ...OVERVIEW, services: [ELECTRIC] });
    const grid = html.slice(html.indexOf('id="rv-electric-high_pct"'));
    const body = grid.slice(0, grid.indexOf("data-checks-for"));
    expect(body).not.toContain("field-help");
    expect(body).not.toContain("-help");
  });

  it("the floor's unit rides its LABEL, so the field needs no sentence (hard rule 3)", () => {
    // WOULD CATCH: the unit dropped along with the help line. A floor without
    // its unit means nothing.
    const html = renderPage({ ...OVERVIEW, services: [ELECTRIC] });
    expect(html).toContain("High-use floor (kWh)");
  });

  it("a configured service whose unit is BLANK asks for it in the label, not in a sentence", () => {
    // ⚠ THIS CASE WAS FIRST WRITTEN AGAINST `GAS_NONE` AND WAS GREEN BEFORE
    // THE FIX — hard-won law 7's "looking at the wrong thing". A `source:
    // "none"` service draws the *invitation*, not the form, so the help line
    // under discussion was never rendered and the absence proved nothing. The
    // fixture is now a service whose FORM is on screen with an empty unit,
    // which is the only state that ever showed `unitMissingHelp`.
    const blankUnit: ReadValidationServiceEntry = { ...ELECTRIC, high_abs_unit: "" };
    const html = renderPage({ ...OVERVIEW, services: [blankUnit] });
    expect(html).toContain('id="rv-electric-high_abs_value"');
    expect(html).not.toContain("a floor without its unit means nothing");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-079 — THE ESTIMATION METHOD IS A CHOICE (PO 2026-09-07, verbatim:
// *"this should be drop down options - give 4 to 5 options here"*, then
// *"we are good with these + add last 6 month avg + Use avg from plan"*)
// ══════════════════════════════════════════════════════════════════════════
describe("CR-079 — seven estimation methods, and the default does not move", () => {
  it("the dropdown offers all seven, with today's method selected", () => {
    const html = renderPage();
    expect(html).toContain('id="rv-est_method"');
    for (const code of EST_METHOD_CODES) {
      expect(html).toContain(`value="${code}"`);
    }
    expect(html).toContain("Daily average of the last 3 periods");
    expect(html).toContain("Daily average of the last 6 periods");
    expect(html).toContain("Daily average of the last 12 periods");
    expect(html).toContain("The same period last year");
    expect(html).toContain("Repeat the last actual reading");
  });

  it("the two methods with nothing to read are OFFERED and NOT SELECTABLE", () => {
    // BR-SHL-025: a control that cannot act is disabled WITH its reason.
    // Neither has an input anywhere in this product — `route_peer_average`
    // has no definition of a peer group and `plan_average` has no plan-held
    // average to read (OQ-MET-1761 / OQ-MET-1762).
    const html = renderPage();
    expect(html).toContain('value="route_peer_average" disabled');
    expect(html).toContain('value="plan_average" disabled');
  });

  it("B14 rule 32: the sentence about the Product Owner is GONE", () => {
    // WOULD CATCH: internal process leaking into clerk-facing copy. It also
    // became false the moment the dropdown landed.
    const html = renderPage();
    expect(html).not.toContain("Product Owner");
    expect(html).not.toContain("ratified");
  });

  it("the panel describes the method that is CHOSEN, in one line", () => {
    const html = renderPage();
    expect(html).toContain("Averages the last three actual readings");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// A TENANT WITH NO ESTIMATION SETTINGS AT ALL SAYS SO — it does NOT show a
// method it is not running.
//
// ⚠ **THIS IS DEF-MET-4480's OWN CLASS, ONE FIELD DOWN, AND THE CR-079
// DROPDOWN NEARLY INTRODUCED IT.** The old read-only box printed an em dash
// when `est_method` was null; a `<select>` has no em dash, so the first draft
// fell back to the default and drew *"Daily average of the last 3 periods"* on
// a tenant that has no settings row — a figure the product is not using,
// presented as one it is. The engine refuses EVERY estimate for such a tenant
// (`validation_config_missing`), so the screen was about to disagree with it
// silently. `general.present` is served precisely so it does not have to.
// ══════════════════════════════════════════════════════════════════════════
describe("no estimation settings yet", () => {
  const NOTHING: ReadValidationOverview = {
    ...OVERVIEW,
    general: { present: false, est_method: null, est_max_consecutive: null },
  };

  it("shows no method rather than the default, and says why", () => {
    const html = renderPage(NOTHING);
    expect(html).toContain("Nothing is estimated yet");
    // the select is EMPTY — no option is marked selected
    expect(html).not.toContain('value="trailing_3_daily_avg" selected');
  });

  it("a tenant that HAS settings still shows them", () => {
    const html = renderPage();
    expect(html).not.toContain("Nothing is estimated yet");
    expect(html).toContain("Averages the last three actual readings");
  });
});
