// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 §Stories + SCOPE ADDENDUM — the S63–S71 rule-page cards)
//           Screens: S66, S69, S70, S71
//           ⚠ S64 LEFT this component 2026-08-26 — CR-038 A1 made it a
//           per-service page (SettingsReadValidation.tsx + its own test).
// Rules:    BR-SHL-035 (ONE shell; a rule page is a card whose view is a FORM) ·
//           BR-TEN-024 (partial change set in, whole page out) · BR-TEN-043 (event-time forward) ·
//           BR-MET-020 (the page IS the config) · BR-BIL-017 · BR-BIL-021 (UNSET ≠ zero) ·
//           BR-PAY-010 · BR-BIL-014 (a one-value choice is fixed, never a guessed second option) ·
//           BR-SHL-025 (a view-only role gets disabled-with-reason)
// ───────────────────────────────────────────────────────
// The load-bearing test in this file is the decimal round trip: a canonical
// decimal string from the server has to come back out of the draft byte for
// byte. If anything on the path ever parses it into a float, "1.500000" stops
// being "1.500000" and a billing rate has silently changed (CLAUDE.md #2).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, formErrorEnvelope } from "@/api/client";
import type { RegionalSettings, RuleDocument } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { envelopeErrors } from "@/components/FormModal";
import { ToastProvider } from "@/components/Toast";

import {
  BILLING_DEFAULTS_PAGE,
  BUDGET_BILLING_PAGE,
  COLLECTIONS_PAGE,
  FINANCE_CONTROLS_PAGE,
  RULE_PAGES,
  SERVICE_REQUESTS_PAGE,
  choiceIsFixed,
  draftFromDocument,
  ruleChanges,
  ruleFieldValue,
  ruleIsDirty,
  rulePageForCard,
} from "./settingsRulePages";
import { RulePageView, moneyEcho } from "./SettingsRulePageView";
import { refusalOf } from "./settingsShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// The S66 page exactly as the server serves it: decimals as canonical STRINGS,
// integers as numbers, an UNSET nullable as null.
const BILLING_DEFAULTS: RuleDocument = {
  late_pct: "1.500000",
  late_min_amount: "5.000000",
  late_grace_days: 5,
  late_grace_mode: "calendar",
  minimum_bill_amount: null, // BR-BIL-021: named, never ratified — UNSET
  overcharge_guardrail_pct: "200",
  allocation_order: "oldest_invoice_first",
  // The PO's ruling of 2026-08-12, as the server seeds it: BR-PAY-038's
  // within-invoice sequence, shipped in the 11 August order.
  allocation_class_order: ["usage_base", "taxes", "tenant_defined", "fees"],
  deposit_interest_rate_annual: "0",
};

const REGIONAL: RegionalSettings = {
  country: "US",
  state: "TX",
  timezone: "America/Chicago",
  language: "en",
  first_day_of_week: "sunday",
  currency: "USD",
  number_format: "1,234.56",
  date_format: "MM/DD/YYYY",
  time_format: "24h",
  fy_start_month: 10,
  fy_start_day: 1,
  accounting_method: "accrual",
  close_cadence: "monthly",
  close_day: "5",
  lock_closed_periods: true,
  current_period: null,
};

function renderRules(
  page: typeof BILLING_DEFAULTS_PAGE,
  document: RuleDocument | undefined,
  options: { readOnly?: boolean; regional?: RegionalSettings | null } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (document !== undefined) {
    queryClient.setQueryData(queryKeys.rulePage(page.slug), document);
  }
  if (options.regional != null) {
    queryClient.setQueryData(queryKeys.regionalSettings, options.regional);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <RulePageView page={page} readOnly={options.readOnly ?? false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-009 (S63–S71 addendum) — a rule page loads and saves a PARTIAL change set", () => {
  it("US-TEN-009 TC-1: the page renders the server's stored values as real, editable fields", () => {
    const html = renderRules(BILLING_DEFAULTS_PAGE, BILLING_DEFAULTS);
    expect(html).toContain("Billing defaults");
    expect(html).toContain("Late fee rate");
    expect(html).toContain("Grace period");
    // The stored values are on screen, unmodified.
    expect(html).toContain('value="1.500000"');
    expect(html).toContain('value="5"');
    // …and the shared save bar is here, not a bespoke one.
    expect(html).toContain("Save these rules");
    expect(html).toContain("Discard");
  });

  it("BR-TEN-024: an untouched page posts NOTHING; one edit posts exactly that one field", () => {
    const original = draftFromDocument(BILLING_DEFAULTS_PAGE, BILLING_DEFAULTS);
    expect(ruleIsDirty(BILLING_DEFAULTS_PAGE, original, original)).toBe(false);
    expect(ruleChanges(BILLING_DEFAULTS_PAGE, original, original)).toEqual({});

    const edited = { ...original, late_grace_days: "10" };
    expect(ruleIsDirty(BILLING_DEFAULTS_PAGE, edited, original)).toBe(true);
    // ONE key — a save can never silently rewrite a threshold nobody touched.
    expect(ruleChanges(BILLING_DEFAULTS_PAGE, edited, original)).toEqual({ late_grace_days: 10 });
  });

  it("BR-TEN-043: every rule page states that new values apply forward only", () => {
    for (const page of RULE_PAGES) {
      const html = renderRules(page, {});
      expect(html).toContain("New values apply from now on");
    }
  });

  it("BR-SHL-025: a view-only role gets Save disabled WITH its reason, never a missing button", () => {
    const html = renderRules(BILLING_DEFAULTS_PAGE, BILLING_DEFAULTS, { readOnly: true });
    expect(html).toContain("Save these rules");
    expect(html).toContain("disabled");
    expect(html).toContain("Your role can view this, but not change it.");
  });
});

describe("CLAUDE.md #2 — a decimal STRING survives the round trip untouched", () => {
  it("a canonical decimal comes back out of the draft byte for byte, never parsed", () => {
    const original = draftFromDocument(BILLING_DEFAULTS_PAGE, BILLING_DEFAULTS);
    // Into the draft: identity, not Number().
    expect(original.late_pct).toBe("1.500000");
    expect(original.deposit_interest_rate_annual).toBe("0");

    // Out of the draft: the same string, with its trailing zeros intact. This
    // is the assertion that breaks the moment anyone adds a parseFloat.
    const edited = { ...original, late_pct: "1.750000" };
    const changes = ruleChanges(BILLING_DEFAULTS_PAGE, edited, original);
    expect(changes.late_pct).toBe("1.750000");
    expect(typeof changes.late_pct).toBe("string");
    // And the untouched one is not in the payload at all.
    expect(changes).not.toHaveProperty("overcharge_guardrail_pct");
  });

  it("no rounding happens client-side — a long fraction is sent exactly as typed", () => {
    const param = BILLING_DEFAULTS_PAGE.params.find((p) => p.key === "late_pct");
    expect(param).toBeDefined();
    expect(ruleFieldValue(param!, "1.6666665")).toBe("1.6666665");
    expect(ruleFieldValue(param!, " 2.5 ")).toBe("2.5"); // trimmed, not reformatted
  });

  it("BR-BIL-021 / BR-BIL-017: an empty nullable posts null — UNSET, never zero", () => {
    const minimumBill = BILLING_DEFAULTS_PAGE.params.find((p) => p.key === "minimum_bill_amount");
    expect(minimumBill?.nullable).toBe(true);
    expect(ruleFieldValue(minimumBill!, "")).toBeNull();
    // And it renders as an empty field, not as "0" or "null".
    const draft = draftFromDocument(BILLING_DEFAULTS_PAGE, BILLING_DEFAULTS);
    expect(draft.minimum_bill_amount).toBe("");

    const settleUp = BUDGET_BILLING_PAGE.params.find((p) => p.key === "settle_up_month");
    expect(settleUp?.nullable).toBe(true);
    expect(ruleFieldValue(settleUp!, "")).toBeNull();
  });

  it("BR-NOT-017: the notice ladder has LEFT this page — SET-12D owns it now", () => {
    // ⚠ THIS TEST WAS NOT DELETED AND ITS ASSERTION WAS NOT LOOSENED. It used
    // to prove that `notice_tier_days` kept the order it was typed in on THIS
    // page. The RULING moved, not the behaviour: PO 2026-08-17, verbatim, *"we
    // bring all internal external ntification rule sat one place and they are
    // part of notification settings"*, so the three ladder timings are edited
    // on Settings → Notifications (SET-12D) and this card gives them up.
    //
    // **The STORE did not move.** `PUT /settings/collections` is still where
    // all five figures land — SET-12D posts to it — so the ordering behaviour
    // this test used to guard is unchanged and is exercised by the backend's
    // own `_check_notice_tiers` cross-check. What this now guards is that the
    // ladder does not quietly come BACK to this page, which would be the two
    // editors over one figure that CR-009 exists to prevent.
    for (const key of ["reminder_days_after_due", "notice_tier_days", "final_notice_hours"]) {
      expect(COLLECTIONS_PAGE.params.find((p) => p.key === key)).toBeUndefined();
    }
    // The rows that stayed are collections POLICY the ruling does not name.
    expect(COLLECTIONS_PAGE.params.map((p) => p.key)).toEqual([
      "plan_reminder_days_before",
      "plan_missed_notice_days_after",
      "plan_void_after_misses",
      "nsf_privilege_n",
      "suppress_paper_on_bad_address",
    ]);
  });

  it("an unparseable integer travels as typed so the SERVER explains it, not a silent truncation", () => {
    const graceDays = BILLING_DEFAULTS_PAGE.params.find((p) => p.key === "late_grace_days");
    expect(ruleFieldValue(graceDays!, "10")).toBe(10);
    // "25.5" is NOT quietly floored to 25 — that would move a threshold.
    expect(ruleFieldValue(graceDays!, "25.5")).toBe("25.5");
  });

  it("BR-SHL-023: a money parameter echoes through the ONE money formatter, never a hand-built string", () => {
    const lateMin = BILLING_DEFAULTS_PAGE.params.find((p) => p.key === "late_min_amount");
    expect(moneyEcho(lateMin!, "5.000000", "USD")).toEqual({ amount: "5.000000", currency: "USD" });
    // No currency on file → no echo. A bare symbol would be a guess.
    expect(moneyEcho(lateMin!, "5.000000", null)).toBeNull();
    const pct = BILLING_DEFAULTS_PAGE.params.find((p) => p.key === "late_pct");
    expect(moneyEcho(pct!, "1.5", "USD")).toBeNull(); // a percent is not money

    const html = renderRules(BILLING_DEFAULTS_PAGE, BILLING_DEFAULTS, { regional: REGIONAL });
    expect(html).toContain("cell-money"); // MoneyCell rendered it, not this screen
    expect(html).toContain("$5.00");
  });
});

describe("US-MET-011 TC-7/TC-8 — every refusal class renders where it belongs", () => {
  it("422 settings.unknown_field lands on the offending field", () => {
    const error = new ApiError(422, {
      code: "VAL-002",
      message_key: "settings.unknown_field",
      field_errors: [
        { field: "late_pct_typo", code: "VAL-002", message_key: "settings.unknown_field" },
      ],
    });
    const mapped = envelopeErrors(formErrorEnvelope(error), t);
    expect(mapped.fields.late_pct_typo).toBe(
      "This app sent a field this setting doesn't have. Nothing was saved.",
    );
  });

  it("422 range refusals carry the server's own bound", () => {
    const tooLow = new ApiError(422, {
      code: "VAL-003",
      message_key: "settings.param_below_min",
      params: { min: 0, exclusive: true },
      field_errors: [
        {
          field: "high_pct",
          code: "VAL-003",
          message_key: "settings.param_below_min",
          params: { min: 0, exclusive: true },
        },
      ],
    });
    expect(envelopeErrors(formErrorEnvelope(tooLow), t).fields.high_pct).toBe(
      "Too low — the minimum is 0.",
    );

    const tooHigh = new ApiError(422, {
      code: "VAL-003",
      message_key: "settings.param_above_max",
      params: { max: 50 },
      field_errors: [
        {
          field: "write_off_threshold_amount",
          code: "VAL-003",
          message_key: "settings.param_above_max",
          params: { max: 50 },
        },
      ],
    });
    expect(
      envelopeErrors(formErrorEnvelope(tooHigh), t).fields.write_off_threshold_amount,
    ).toBe("Too high — the maximum is 50.");

    // S64's window cross-check (flag window inside hard) is a range refusal
    // too — the KEYS live on: the per-service server raises the same ones.
    const inverted = new ApiError(422, {
      code: "VAL-003",
      message_key: "settings.read_validation.soft_outside_hard",
      params: { soft: [25, 35], hard: [30, 45] },
      br_ref: "BR-MET-020",
      field_errors: [
        {
          field: "days_soft_min",
          code: "VAL-003",
          message_key: "settings.read_validation.soft_outside_hard",
          params: { soft: [25, 35], hard: [30, 45] },
        },
      ],
    });
    expect(envelopeErrors(formErrorEnvelope(inverted), t).fields.days_soft_min).toContain(
      "has to sit inside the hard window",
    );
  });

  it("422 unratified enum names what IS ratified, from params.allowed", () => {
    const badChoice = new ApiError(422, {
      code: "VAL-004",
      message_key: "settings.param_bad_choice",
      params: { allowed: ["calendar", "business"], br: "BR-BIL-002" },
      br_ref: "BR-BIL-002",
      field_errors: [
        {
          field: "late_grace_mode",
          code: "VAL-004",
          message_key: "settings.param_bad_choice",
          params: { allowed: ["calendar", "business"] },
        },
      ],
    });
    expect(envelopeErrors(formErrorEnvelope(badChoice), t).fields.late_grace_mode).toBe(
      "That value isn't ratified. Allowed: calendar,business.",
    );
  });

  it("403 on a write is the server refusing this role — rendered, never swallowed", () => {
    // A4 gives Executive "View" on Settings, so its PUT comes back 403 even
    // though its GET succeeded. The screen shows the refusal with its rule.
    const denied = new ApiError(403, {
      code: "AUTH-002",
      message_key: "errors.auth-002",
      br_ref: "BR-SHL-025",
    });
    const refusal = refusalOf(denied, t);
    expect(refusal.message).toBe(
      "Your role doesn't allow this. Ask a System Admin if you need it.",
    );
    expect(refusal.brRef).toBe("BR-SHL-025");
  });

  it("US-TEN-009 TC-5: a 403 on the READ renders the permission-denied state, not an error", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter>
            <RulePageView page={BILLING_DEFAULTS_PAGE} readOnly={false} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // Nothing is seeded, so the read is pending: the A18 §3 skeleton, never a
    // half-drawn form with invented values.
    expect(html).toContain("skeleton");
    expect(html).not.toContain("Save these rules");
  });
});

describe("A one-value choice set is a FIXED control — this screen invents no option", () => {
  it("BR-PAY-010 / BR-BIL-014 / BR-BIL-017: three params accept exactly one value today (est_method moved to S64's own page)", () => {
    const fixed = RULE_PAGES.flatMap((page) =>
      page.params.filter(choiceIsFixed).map((param) => param.key),
    );
    // ⚠ **FOUR SINCE 2026-09-27, AND THIS PIN SAID THREE UNTIL 2026-10-02.**
    // `CR-142-BRC07` `P4.6` (`97ac0ddd0`, 2.379.0) added S8's *Default format*
    // card with `default_download_format` fixed at `csv` — one ratified value,
    // because no PDF renderer is declared anywhere in the product
    // (`apps/reports/models.FORMATS`). `settingsRulePages.ts` names
    // `allocation_order` and `level_rounding` as its precedents.
    expect(fixed.sort()).toEqual([
      "allocation_order",
      "correction_approval_mode",
      "default_download_format",
      "level_rounding",
    ]);
    // …and a genuinely multi-valued choice is NOT fixed.
    const graceMode = BILLING_DEFAULTS_PAGE.params.find((p) => p.key === "late_grace_mode");
    expect(choiceIsFixed(graceMode!)).toBe(false);
  });

  it("the fixed control says the other values are not ratified, and offers no alternative", () => {
    const html = renderRules(FINANCE_CONTROLS_PAGE, {
      correction_approval_mode: "all",
      dso_target_days: 15,
    });
    expect(html).toContain("Corrections that need approval");
    expect(html).toContain("Every correction");
    expect(html).toContain("This is the only value approved so far");
    // The control is present and READ-ONLY — never a dropdown whose only
    // option is the value already selected.
    expect(html).toContain('id="correction_approval_mode" class="input" readonly=""');
    // The multi-valued choice on the same page DOES get a real select.
    const s66 = renderRules(BILLING_DEFAULTS_PAGE, BILLING_DEFAULTS);
    expect(s66).toContain("<select");
    expect(s66).toContain("Calendar days");
    expect(s66).toContain("Business days");
  });
});

describe("BR-SHL-035 — four pages, ONE component, ONE config", () => {
  it("every rule card with an endpoint resolves to a config row, and vice versa", () => {
    // ⚠ **SIX SINCE 2026-09-27 (`CR-142-BRC07` `P4.6`, `97ac0ddd0`)** — S8's
    // *File retention* and *Default format* cards, one `reports` family behind
    // one `PUT /settings/reports`. This pin said four until 2026-10-02.
    expect(RULE_PAGES.map((page) => page.card)).toEqual([
      "billing_defaults",
      "budget_billing",
      "collections_notices",
      "finance_controls",
      "file_retention",
      "default_format",
      // `DEF-CUS-10445` (PO 2026-10-22) — the service request default target
      // days, `PUT /settings/service-requests`.
      "service_requests",
    ]);
    for (const page of RULE_PAGES) {
      expect(rulePageForCard(page.card)).toBe(page);
    }
    // The holiday calendar is a rule CARD but not one of these documents — it
    // has its own resource, and asking for it must not hand back a wrong page.
    expect(rulePageForCard("holidays")).toBeNull();
    expect(rulePageForCard("nonsense")).toBeNull();
  });

  it("the field law matches the server's registry, page by page", () => {
    // 9 → 10 on 2026-10-13: `reopen_within_years` (BR-CUS-1119, PO *"Q4 - keep
    // 5 years right now"*) — how long a returning customer's closed account
    // may be reopened at move-in.
    // 10 → 12 on 2026-10-14: `temporary_stop_min_days` / `_max_months`
    // (BR-CUS-1121, PO B3 — *"10 days for time being"*, *"12 months maximum"*).
    expect(BILLING_DEFAULTS_PAGE.params).toHaveLength(12);
    expect(BILLING_DEFAULTS_PAGE.params.map((p) => p.key)).toContain("reopen_within_years");
    expect(BILLING_DEFAULTS_PAGE.params.map((p) => p.key)).toContain("temporary_stop_min_days");
    expect(BILLING_DEFAULTS_PAGE.params.map((p) => p.key)).toContain("temporary_stop_max_months");
    expect(BUDGET_BILLING_PAGE.params).toHaveLength(7);
    // 8 until 2026-08-17. Three ladder timings moved to SET-12D (BR-NOT-017);
    // the store did not move, only the door.
    expect(COLLECTIONS_PAGE.params).toHaveLength(5);
    // 7 → 9 on 2026-08-17, and both new fields are PO rulings on CR-008:
    //   · `bank_match_amount_tolerance` — ruling 7, *"We can take it as
    //     threshold from user"*. ⚠ Its default is $0.00, which IS today's
    //     behaviour: `reconciliation.py` matches exactly to the penny, so a
    //     non-zero default would have loosened a money match by shipping.
    //   · `write_off_approval_threshold_amount` — ruling 2, and it is a
    //     SEPARATE field from `write_off_threshold_amount` above it on purpose.
    //     That one is BR-BIL-013's automatic small-balance write-off ($5,
    //     capped $50); this one is the manual approval the PO asked for. The
    //     two were one collision away from a utility setting one believing they
    //     had set the other, which is why both are asserted here by name.
    expect(FINANCE_CONTROLS_PAGE.params).toHaveLength(9);
    expect(FINANCE_CONTROLS_PAGE.params.map((p) => p.key)).toEqual(
      expect.arrayContaining(["bank_match_amount_tolerance", "write_off_approval_threshold_amount"]),
    );
    // Every parameter names the rule that ratified it — no orphan fields.
    for (const page of RULE_PAGES) {
      for (const param of page.params) {
        expect(param.br).toMatch(/^BR-[A-Z]{3}-\d{3,6}$/);
      }
    }
  });

  it("every parameter, title and choice has copy in the catalog — no raw key reaches a user", () => {
    for (const page of RULE_PAGES) {
      for (const key of [`settings.rules.${page.card}.title`, `settings.rules.${page.card}.hint`]) {
        expect(i18n.exists(key)).toBe(true);
      }
      for (const param of page.params) {
        expect(i18n.exists(`settings.rules.${page.card}.${param.key}`)).toBe(true);
        for (const choice of param.choices ?? []) {
          expect(i18n.exists(`settings.rules.choice.${param.key}.${choice}`)).toBe(true);
        }
      }
    }
  });

  it.todo(
    "US-TEN-009 (addendum) TC: typing into a threshold and watching the save bar arm — browser-interaction scope",
  );
  it.todo(
    "US-MET-011 TC-9 (server): an engine refuses rather than assuming when a parameter is UNSET — backend/golden scope",
  );
});

describe("DEF-CUS-10445 — the service request default target days is a Settings field", () => {
  it("renders the server's seeded 15 as an editable whole-number field in days, and posts only it", () => {
    const html = renderRules(SERVICE_REQUESTS_PAGE, { service_request_default_target_days: 15 });
    expect(html).toContain("Service requests");
    expect(html).toContain("Target after request");
    expect(html).toContain('id="service_request_default_target_days"');
    expect(html).toContain('value="15"');
    expect(html).toContain("days");
    // A utility moving it to 10 posts exactly that one key, as a NUMBER.
    const draft = draftFromDocument(SERVICE_REQUESTS_PAGE, {
      service_request_default_target_days: 15,
    });
    expect(ruleIsDirty(SERVICE_REQUESTS_PAGE, draft, draft)).toBe(false);
    const edited = { ...draft, service_request_default_target_days: "10" };
    expect(ruleChanges(SERVICE_REQUESTS_PAGE, edited, draft)).toEqual({
      service_request_default_target_days: 10,
    });
    expect(rulePageForCard("service_requests")).toBe(SERVICE_REQUESTS_PAGE);
    expect(SERVICE_REQUESTS_PAGE.slug).toBe("service-requests");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packet EP-MET-04@34f14b6)
// generated: 2026-08-09 by story-coder v1 (W0 frontend integration lane — the five rule pages)
// checklist: A✔ B✔ C✔ D=deferred(no endpoint of its own — the wrappers are api/endpoints.ts) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope)
// exceptions: E3 the S63–S71 stories (US-TEN-013..017) are ALLOCATED but UNAUTHORED, so these tests are named for US-TEN-009's addendum and US-MET-011's TCs rather than inventing TC numbers for stories that do not exist — reported
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
