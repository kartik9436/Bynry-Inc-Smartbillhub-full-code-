// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 · US-TEN-010 · US-TEN-011 (EP-TEN-07 §Stories)
//           Screens: S8 (Reference data), S63 (Holiday calendar), S64/S66/S69/S70 (rule cards)
//           AMENDED 2026-08-16 (CR-004 task C): S71 Finance controls is no longer reached from this grid —
//           it renders as a section of Settings → Accounting, and this file now pins its ABSENCE plus the
//           fallback its old deep link takes.
// Rules:    BR-SHL-035 (ONE shell for EVERY card — list AND rule page) · BR-TEN-029 (live counts) ·
//           BR-TEN-030 (code freezes at Used-by > 0) · BR-TEN-034 (audit-lock delete, deactivate always) ·
//           BR-TEN-033 (templates card is navigation only) · BR-TEN-039/BR-TEN-041 (the rule cards)
//           AMENDED 2026-08-17 (CR-004 task A3): BR-TEN-078 — the Utility-service column is asserted in BOTH
//           directions, present on `uoms` and absent everywhere else, because a column that leaks onto an
//           unscoped list renders blanks and a blank column reads as "no value".
// ───────────────────────────────────────────────────────
// The load-bearing test in this file is the BR-SHL-035 one: the SAME management
// component, given two different card configs, renders the same shell with
// different columns — and a rule page renders that identical shell with a form
// body. If a future card ever needed its own screen, that test breaks.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type {
  Holiday,
  LookupCard,
  LookupEntry,
  Paginated,
  ReadValidationOverview,
  ReferenceFixtureGap,
  RuleDocument,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  REFERENCE_CARDS,
  listCards,
  placeholderCards,
  referenceCard,
  referenceCardViews,
  ruleCards,
} from "./referenceDataConfig";
import { rulePageForCard } from "./settingsRulePages";
import { RefusalNotice, refusalOf } from "./settingsShared";
import {
  ReferenceDataTab,
  badgeFor,
  codeIsFrozen,
  deleteIsLocked,
  deleteLockReason,
  detailText,
  openCardFrom,
  parentOptionsFor,
  serviceScopeText,
} from "./SettingsReferenceData";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// What `GET /lookups` serves today: the lists whose owning lane has landed.
const SERVER_CARDS: LookupCard[] = [
  { list: "uoms", owner: "tenancy", count: 6, state: "seeded" },
  { list: "meter_types", owner: "metering", count: 5, state: "seeded" },
  { list: "asset_types", owner: "assets", count: 10, state: "seeded" },
  { list: "asset_statuses", owner: "assets", count: 5, state: "seeded" },
];

function uom(code: string, name: string, usedBy: number, active = true): LookupEntry {
  return { id: `id-${code}`, code, name, active, is_system: false, used_by: usedBy };
}

/**
 * CR-004 task A3 — a UoM row WITH its scope, exactly as `UomLookupHandler`
 * serializes it. `null` is passed explicitly and means "All services": it is
 * the stored value, not an omission, and the helper takes it out loud so no
 * fixture in this file can leave the question open by accident.
 */
function scopedUom(code: string, name: string, service: string | null): LookupEntry {
  return {
    ...uom(code, name, 0),
    service: service === null ? null : { id: `svc-${service}`, code: service },
  };
}

function assetType(code: string, name: string, category: string): LookupEntry {
  return { id: `id-${code}`, code, name, active: true, is_system: true, used_by: 0, category };
}

function page<T>(results: T[]): Paginated<T> {
  return { count: results.length, next: null, previous: null, results };
}

// The rule pages this file reaches into. Decimals are the SERVER's own
// canonical strings — never numbers, here or anywhere downstream.
// S64's shape is CR-038 A1's whole-picture overview (per service), served by
// metering; the flat document above it is gone with the flat form.
// BR-MET-136 (PO 2026-08-26): every service entry carries the per-rule ON/OFF
// map, EXPANDED by the server, and every rule ships ON. Spelled here because
// this file's fixtures are the whole S64 payload — a service entry without the
// map is not a shape the server can produce.
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
const ALL_RULES_ON: Record<string, boolean> = Object.fromEntries(
  JUDGMENT_RULES.map((rule) => [rule, true]),
);

const READ_VALIDATION_OVERVIEW: ReadValidationOverview = {
  general: { present: true, est_method: "trailing_3_daily_avg", est_max_consecutive: 2 },
  services: [
    {
      service: "electric",
      source: "service",
      rule_enabled: ALL_RULES_ON,
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
    },
    { service: "gas", source: "none", unit_hint: "ccf", rule_enabled: ALL_RULES_ON },
  ],
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

const BILLING_DEFAULTS_RULES: RuleDocument = {
  late_pct: "1.5",
  late_min_amount: "5",
  late_grace_days: 5,
  late_grace_mode: "calendar",
  minimum_bill_amount: null,
  overcharge_guardrail_pct: "200",
  allocation_order: "oldest_invoice_first",
  deposit_interest_rate_annual: "0",
};

interface Seed {
  cards?: LookupCard[];
  entries?: { list: string; rows: LookupEntry[] };
  holidays?: Holiday[];
  rules?: { code: string; rules: RuleDocument };
  readValidation?: ReadValidationOverview;
  /** DEF-902 / BR-TEN-161 — how far behind the platform fixture this list is. */
  fixtureGap?: ReferenceFixtureGap;
}

function renderReference(path: string, seed: Seed, readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.lookupCards, seed.cards ?? SERVER_CARDS);
  if (seed.entries !== undefined) {
    queryClient.setQueryData(
      queryKeys.lookupEntries(seed.entries.list, "", 1, 50),
      page(seed.entries.rows),
    );
  }
  if (seed.holidays !== undefined) {
    queryClient.setQueryData(queryKeys.holidays, seed.holidays);
  }
  if (seed.rules !== undefined) {
    const rulePage = rulePageForCard(seed.rules.code);
    if (rulePage !== null) {
      queryClient.setQueryData(queryKeys.rulePage(rulePage.slug), seed.rules.rules);
    }
  }
  if (seed.readValidation !== undefined) {
    // S64's own query (CR-038 A1) — the rulePage key kept the slug.
    queryClient.setQueryData(queryKeys.rulePage("read-validation"), seed.readValidation);
  }
  if (seed.fixtureGap !== undefined) {
    queryClient.setQueryData(
      queryKeys.lookupFixtureGap(seed.fixtureGap.list),
      seed.fixtureGap,
    );
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <ReferenceDataTab readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-009 — Reference-data card grid and navigation", () => {
  it("US-TEN-009 TC-1: every card the server serves renders with its LIVE count and its sample line", () => {
    const html = renderReference("/settings/reference-data", {});
    expect(html).toContain("Units of measure");
    expect(html).toContain("kWh, kW, kgal, ccf, therm, month");
    expect(html).toContain("6 ›");
    expect(html).toContain("Meter types");
    expect(html).toContain("5 ›");
    expect(html).toContain("Asset types");
    expect(html).toContain("10 ›");
    // The grid intro states the lock rule before anyone clicks a card.
    expect(html).toContain("lock-protected");
  });

  it("US-TEN-009 TC-2: clicking a card opens its management view in the SAME frame, with the return link", () => {
    const html = renderReference("/settings/reference-data?list=uoms", {
      entries: { list: "uoms", rows: [uom("kWh", "Kilowatt hour", 0)] },
    });
    expect(html).toContain("settings-frame");
    expect(html).toContain("← Reference data");
    expect(html).toContain("Units of measure");
    // The same frame carries the audit line every card shows.
    expect(html).toContain("recorded in the audit log");
  });

  it("DEF-596 (CR-028 debt sweep): the SET-04 audit sentence renders EXACTLY ONCE on a list detail", () => {
    // RED before the sweep: SettingsFrame closes every card with
    // `settings.auditLine` AND ReferenceCardBody appended its own
    // `settings.reference.auditNote` — the identical sentence, so the PO's
    // screenshot showed it twice, one above the other. One frame, one line.
    const html = renderReference("/settings/reference-data?list=uoms", {
      entries: { list: "uoms", rows: [uom("kWh", "Kilowatt hour", 0)] },
    });
    expect(html.split("recorded in the audit log").length - 1).toBe(1);
  });

  it("BR-TEN-029: a card the server serves no count for says so — 0 would be a claim", () => {
    const views = referenceCardViews(SERVER_CARDS);
    const served = views.find((view) => view.card.code === "uoms");
    expect(served?.count).toBe(6);
    // DEF-235: `account_statuses` used to be this test's example — it went
    // LIVE, so the example became `work_skills`. ⚠ AMENDED 2026-09-04 (CR-070
    // wave C): that one went live too, and NO card carries `arrivesWithKey` any
    // more. The card that still has no count is `work_parts` — `kind: "link"`,
    // navigation only, so tenancy stores nothing for it and the badge says
    // where the number lives rather than inventing a zero.
    const work = views.find((view) => view.card.code === "work_parts");
    expect(work?.count).toBeNull();
    expect(work?.state).toBe("absent");
    // A list card the server does not serve AND that makes no honest promise is
    // not drawn at all: drawing it would imply data that does not exist.
    expect(views.map((view) => view.card.code)).not.toContain("charge_codes");
    // ⚠ AMENDED 2026-09-04 (CR-070 wave C): this used to render with NO cards
    // served, because four Work cards carried `arrivesWithKey` and were drawn
    // anyway. None does now, so an unserved list card is not drawn at all — and
    // *"Not set up yet"* is what a card the server DOES serve, with no rows,
    // says. That is the honest state this case is about either way: a badge
    // reading `0 ›` would claim the list is empty, which is a different
    // statement from "nobody has set it up".
    const html = renderReference("/settings/reference-data", {
      cards: [{ list: "work_skills", owner: "work", count: null, state: "seeded" }],
    });
    expect(html).toContain("Not set up yet");
    // No card anywhere renders a fabricated zero.
    expect(html).not.toContain(">0 ›<");
  });

  // ── DEF-336 · the badge has THREE states, and it used to have two ────────
  it("DEF-336: a card the server counts shows its number WHATEVER its kind is", () => {
    // The bug in one line: `custom_fields` is `kind: "custom"`, the server has
    // always served a count for it, and the tile threw the number away before
    // looking at it because the kind was not "list".
    const html = renderReference("/settings/reference-data", {
      cards: [
        { list: "uoms", owner: "tenancy", count: 26, state: "seeded" },
        { list: "custom_fields", owner: "tenancy", count: 3, state: "seeded" },
      ],
    });
    expect(html).toContain(">26 ›<");
    expect(html).toContain(">3 ›<");
  });

  it("DEF-336: a card with no list to count SAYS SO — it is never a bare chevron", () => {
    // What the PO photographed: the whole BILLING section — a rules card, a
    // rules card and a link card — drew "›" and nothing else, next to WORK's
    // honest "Not set up yet". A blank reads as missing configuration.
    const html = renderReference("/settings/reference-data", { cards: [] });
    expect(html).toContain(t("settings.reference.settingsCard"));
    expect(html).toContain(t("settings.reference.settingsCardWhy"));
    expect(html).toContain(t("settings.reference.opensElsewhere"));
    // The three states are DISTINCT: a settings card must not borrow the
    // empty-list sentence, which would claim nobody has configured it.
    const billingDefaults = badgeFor(
      { card: referenceCard("billing_defaults")!, count: null, state: "absent" },
      t,
    );
    expect(billingDefaults.text).toBe(t("settings.reference.settingsCard"));
    expect(billingDefaults.text).not.toBe(t("settings.reference.noEntries"));
    expect(billingDefaults.title).toBe(t("settings.reference.settingsCardWhy"));
    const templates = badgeFor(
      { card: referenceCard("templates")!, count: null, state: "absent" },
      t,
    );
    expect(templates.text).toBe(t("settings.reference.opensElsewhere"));
  });

  it("DEF-336: `uncounted` is the server's word for SET UP AND NOT COUNTABLE HERE", () => {
    // DEF-026 minted this state; nothing rendered it. It is NOT "not set up
    // yet" — `reference_seed_runs` proves the rows exist — and it is not a
    // fourth state invented by the screen.
    const badge = badgeFor(
      { card: referenceCard("uoms")!, count: null, state: "uncounted" },
      t,
    );
    expect(badge.text).toBe(t("settings.reference.uncounted"));
    expect(badge.text).not.toBe(t("settings.reference.noEntries"));
    expect(badge.title).toBe(t("settings.reference.uncountedWhy"));
  });

  it("DEF-336: a list card with no server card still says 'Not set up yet'", () => {
    const badge = badgeFor(
      { card: referenceCard("work_skills")!, count: null, state: "absent" },
      t,
    );
    expect(badge.text).toBe(t("settings.reference.noEntries"));
  });

  it("US-TEN-009 TC-3 / BR-TEN-033: the templates card is navigation only — it opens no management view", () => {
    const templates = referenceCard("templates");
    expect(templates?.kind).toBe("link");
    expect(templates?.target).toBe("/settings/templates");
    const html = renderReference("/settings/reference-data?list=templates", {});
    expect(html).toContain("Settings → Templates");
    expect(html).not.toContain("+ Add entry");
  });

  it("BR-SHL-011: an unknown ?list falls back to the grid instead of erroring", () => {
    expect(openCardFrom(new URLSearchParams(""))).toBeNull();
    expect(openCardFrom(new URLSearchParams("list=uoms"))?.code).toBe("uoms");
    expect(openCardFrom(new URLSearchParams("list=nonsense"))).toBeNull();
  });

  it.todo(
    "US-TEN-009 TC-4: adding a UoM lifts the card count to 7 — a live server recount, exercised end to end in the journey suite",
  );
  it.todo("US-TEN-009 TC-6 (isolation): per-tenant counts — server/RLS scope (G5)");
});

describe("US-TEN-010 — the ONE config-driven list-management view", () => {
  it("BR-SHL-035: the SAME component serves two different card configs — only the columns differ", () => {
    // Config A: units of measure — code · name · used-by · status · actions.
    const uoms = renderReference("/settings/reference-data?list=uoms", {
      entries: {
        list: "uoms",
        rows: [uom("kWh", "Kilowatt hour", 0), uom("kgal", "Thousand gallons", 4)],
      },
    });
    // Config B: asset types — the SAME shell plus the owner's `category` column.
    const assets = renderReference("/settings/reference-data?list=asset_types", {
      entries: {
        list: "asset_types",
        rows: [assetType("MTR-E", "Electric meter", "meter")],
      },
    });

    for (const html of [uoms, assets]) {
      // Identical shell: same frame, same return link, same toolbar, same audit
      // line, same table framework, same row actions.
      expect(html).toContain("settings-frame");
      expect(html).toContain("← Reference data");
      expect(html).toContain("+ Add entry");
      expect(html).toContain("recorded in the audit log");
      expect(html).toContain("data-table");
      expect(html).toContain('aria-label="Deactivate"');
    }
    // Only the configured detail column differs.
    expect(assets).toContain("Category");
    expect(assets).toContain("meter");
    expect(uoms).not.toContain("Category");
    // Different titles, one screen.
    expect(uoms).toContain("Units of measure");
    expect(assets).toContain("Asset types");
  });

  it("the ONE view is configured for every lookup card in the grid", () => {
    const codes = listCards().map((card) => card.code);
    expect(codes).toEqual([
      "uoms",
      "charge_codes",
      "tax_jurisdictions",
      // CR-166-BRC10 (PO 2026-10-03): the three discount dropdowns.
      "discount_program_owners",
      "discount_exclusivity_groups",
      "discount_eligibility",
      "reason_codes",
      "payment_methods",
      // DEF-203 (PO 2026-08-28, *"capture bank account in configure"*): the
      // tenant's OWN bank accounts. A model with a unique key, an RLS policy
      // and two readers had NO writer anywhere, so S38 step 1's picker was
      // empty on every real tenant and could never stop being empty.
      "bank_accounts",
      "meter_types",
      "read_methods",
      "asset_types",
      "asset_statuses",
      "account_statuses",
      "account_types",
      // CR-010 "Part-10 confirmations" 10.0 (PO 2026-08-17: "add them"): the
      // sub-type tree's tenant-editable second level, right under its
      // read-only platform parents — the two cards together are S65.
      "account_subtypes",
      // CR-004: the six r10 SET-04 lists tenancy now hosts. Real cards with
      // tables, handlers and seeded vocabularies — the ONE view drives them.
      "areas",
      "service_size_classes",
      // DEF-236 / CR-010 item 2: seeded since 2026-08-10, a card since
      // 2026-08-17 — the only list that ever had rows and no door.
      "premises_types",
      // CR-010 A-4 (PO 2026-08-17: "this is correct"): the UNIT_TYPES tuple
      // becomes editable rows; with premises_types this pair is r10 SET-04's
      // "Premise & unit types" surface.
      "unit_types",
      "occupancy_statuses",
      "device_types",
      "certification_types",
      "import_mappings",
      // ── r10 SET-04's WORK cards. ⚠ AMENDED 2026-09-04 (CR-070 wave C):
      // FIVE, AND WIRED. The four carried `arrivesWithKey` from 2026-08-16
      // because no module owned a work order, a skill or a parts stock; the PO
      // ruled Work its own module on 2026-09-03, `apps/work` owns all five
      // tables, and the sentence would now be false. `work_order_types` is the
      // fifth (`BR-WRK-017`). `work_parts` is deliberately NOT here: the
      // register is a SCREEN with six columns, so its card is `kind: "link"`
      // and navigates to it (BR-TEN-033's own precedent).
      "work_order_types",
      "work_priorities",
      "work_skills",
      "work_safety_kits",
      "work_parts_categories",
    ]);
    // …plus the rule pages, the ONE navigation-only card (BR-TEN-033
    // templates) and the ONE "custom" card (EP-TEN-09 custom fields, whose
    // resource is not a lookup list — BR-TEN-047 puts it in this grid, not in
    // this view).
    // …plus the placeholder set, pinned separately so it cannot grow or shrink
    // without somebody meaning it. ⚠ **AS OF 2026-09-04 IT IS EMPTY, AND THAT
    // IS THE WHOLE POINT OF CR-070 WAVE C.** It held the four r10 WORK cards —
    // declared with no endpoint, rendering *"Field work is not part of this
    // release yet"* — from 2026-08-16 until `apps/work` became the eleventh
    // code module and gave all four a table and a handler. An empty pin still
    // pins: the next card that ships a promise instead of a screen shows up
    // here, and has to be meant.
    // DEF-235 (2026-08-17): the two ACCOUNT cards LEFT this list. The previous
    // revision of this very comment said their accuracy was "reported, not
    // silently changed here" — and the report went nowhere for a week while
    // both lists sat seeded behind live handlers and the cards told the
    // operator nothing was stored. A pin test asserts what IS, and what is
    // includes staleness: the check that would have caught this is the one in
    // the backend (test_reference_data_completeness) asserting no card claims
    // "arrives with" over a list code whose handler is registered.
    expect(placeholderCards().map((card) => card.code)).toEqual([]);
    // +2 was the templates link and the custom-fields card; `work_parts` is a
    // third non-list card (BR-TEN-033 navigation), so the arithmetic was +3.
    // ⚠ **+4 SINCE 2026-09-27**: `delivery` is the fourth non-list card, a
    // `kind: "link"` to `4·1 Scheduled` under `BR-REP-044`. It is NOT a rule
    // card, so it does not reach `ruleCards()` — it lands in this remainder.
    // ⚠ **+5 SINCE 2026-10-24**: `read_formats` (`CR-192-BRC10`, MQ-033 task
    // 11) is the fifth — a `kind: "link"` under READS to Settings → Reads →
    // Read formats, `work_parts`' precedent.
    // ⚠ **+6 SINCE 2026-10-26**: `cant_read_reasons` (`DEF-MET-10609`, PO
    // *"yes do it"*) is the sixth — a `kind: "link"` under READS beside Read
    // formats, to the one can't-read reason list.
    expect(REFERENCE_CARDS).toHaveLength(codes.length + ruleCards().length + 6);
  });

  it("US-TEN-010 TC-3 / BR-TEN-030: a code freezes once it is used; the name never does", () => {
    expect(codeIsFrozen(uom("LEAK", "Leak adjustment", 12))).toBe(true);
    expect(codeIsFrozen(uom("RECON", "Reconnect fee", 0))).toBe(false);
    const html = renderReference("/settings/reference-data?list=uoms", {
      entries: { list: "uoms", rows: [uom("kgal", "Thousand gallons", 12)] },
    });
    expect(html).toContain('aria-label="Edit"'); // editing stays available — the NAME is editable
  });

  it("US-TEN-010 TC-4 (neg): a case-insensitive duplicate is the server's refusal, naming the existing entry", () => {
    const duplicate = new ApiError(422, {
      code: "VAL-002",
      message_key: "settings.lookups.duplicate_code",
      params: { existing: "kgal" },
      field_errors: [
        { field: "code", code: "VAL-002", message_key: "settings.lookups.duplicate_code", params: { existing: "kgal" } },
      ],
    });
    expect(refusalOf(duplicate, t).message).toBe(
      "kgal already exists in this list. Codes are unique, whatever the capitalization.",
    );
  });

  it("US-TEN-010 TC-6: an owner-supplied detail value renders without this screen asserting its type", () => {
    expect(detailText(assetType("MTR-E", "Electric meter", "meter"), "category")).toBe("meter");
    expect(detailText(uom("kWh", "Kilowatt hour", 0), "category")).toBe("");
    expect(detailText(uom("kWh", "Kilowatt hour", 0), undefined)).toBe("");
  });

  it("US-TEN-010 TC-1: the four newly-registered catalogs render through that SAME view — configuration, not code", () => {
    // charge_codes + tax_jurisdictions (rating) and reason_codes +
    // payment_methods (tenancy-hosted) were dark because no owner had
    // registered a handler. They have one now, and NOT ONE of them needed a
    // screen: each is the same LookupListView reading its config row.
    const cases: Record<string, { rows: LookupEntry[]; detail?: string }> = {
      charge_codes: {
        rows: [
          { id: "c1", code: "LATE", name: "Late payment fee", active: true, is_system: false, used_by: 3, charge_type: "penalty" },
        ],
        detail: "penalty",
      },
      tax_jurisdictions: {
        rows: [
          { id: "j1", code: "Fort Bend County", name: "Fort Bend County", active: true, is_system: false, used_by: 2, level: "county" },
        ],
        detail: "county",
      },
      reason_codes: {
        rows: [{ id: "r1", code: "MISREAD", name: "Meter misread", active: true, is_system: true, used_by: 0 }],
      },
      payment_methods: {
        rows: [{ id: "p1", code: "ACH", name: "Bank transfer", active: true, is_system: true, used_by: 41 }],
      },
    };
    for (const [code, { rows, detail }] of Object.entries(cases)) {
      const html = renderReference(`/settings/reference-data?list=${code}`, {
        entries: { list: code, rows },
      });
      // The identical shell every other card gets.
      expect(html).toContain("settings-frame");
      expect(html).toContain("← Reference data");
      expect(html).toContain("+ Add entry");
      expect(html).toContain("data-table");
      expect(html).toContain("recorded in the audit log");
      expect(html).toContain(rows[0].name);
      if (detail !== undefined) {
        // The owner's own detail slot — rendered, never asserted into a type.
        expect(html).toContain(detail);
      }
    }
    // read_methods is in the registry now too, so its card is servable.
    const readMethods = renderReference("/settings/reference-data?list=read_methods", {
      entries: {
        list: "read_methods",
        rows: [{ id: "m1", code: "AMI", name: "Automated meter reading", active: true, is_system: true, used_by: 12 }],
      },
    });
    expect(readMethods).toContain("Automated meter reading");
    expect(readMethods).toContain("data-table");
  });

  it("BR-TEN-031: the charge/tax cards say where the money lives, and never post it", () => {
    // These two cards mint CODES. Their amounts, rates and GL accounts are
    // refused by the owner as unknown fields, so the view states where they
    // belong rather than offering an input that will be rejected.
    const charges = renderReference("/settings/reference-data?list=charge_codes", {
      entries: {
        list: "charge_codes",
        rows: [{ id: "c1", code: "LATE", name: "Late payment fee", active: true, is_system: false, used_by: 0, charge_type: "penalty" }],
      },
    });
    expect(charges).toContain("Amounts, percentages and GL accounts are set on Plans &amp; Rates → Charges");
    const taxes = renderReference("/settings/reference-data?list=tax_jurisdictions", {
      entries: {
        list: "tax_jurisdictions",
        rows: [{ id: "j1", code: "Fort Bend County", name: "Fort Bend County", active: true, is_system: false, used_by: 0, level: "county" }],
      },
    });
    expect(taxes).toContain("Rates, authorities and filing details are set on Plans &amp; Rates → Taxes");
  });

  it.todo(
    "US-TEN-010 TC-2/TC-5: type-to-search a charge code and watch a duplicate refused — both are browser-interaction scope (the debouncer + the modal round trip)",
  );
  it.todo("US-TEN-010 TC-7 (isolation): per-tenant lists — server/RLS scope (G5)");
});

describe("CR-010 — the account sub-types card (the tree's second level)", () => {
  const subtype = (
    code: string,
    name: string,
    parent: { code: string; name: string } | null,
  ): LookupEntry => ({
    id: `st-${code}`,
    code,
    name,
    active: true,
    is_system: true,
    used_by: 0,
    parent_code: parent?.code ?? null,
    parent_name: parent?.name ?? null,
  });

  it("declares the ONE cross-list tree, and its parents are the account types", () => {
    // A flag on one card, not a payload sniff — the same reason `hierarchical`
    // and `serviceScoped` are flags. Exactly one card may carry it until a
    // ruling adds another.
    const declared = REFERENCE_CARDS.filter((card) => card.parentList !== undefined);
    expect(declared.map((card) => card.code)).toEqual(["account_subtypes"]);
    expect(referenceCard("account_subtypes")?.parentList?.code).toBe("account_types");
    // `areas` keeps its self-parenting flag — the two mechanisms coexist.
    // DEF-TEN-4478 turned that flag into the block carrying the list's own two
    // nouns, so what is asserted is that it is DECLARED, not that it is `true`.
    expect(referenceCard("areas")?.hierarchical).toBeDefined();
    expect(referenceCard("account_subtypes")?.hierarchical).toBeUndefined();
  });

  it("gives every self-parented card its OWN two nouns, never areas' by default", () => {
    // `BR-WRK-058` (PO 2026-09-07) — `work_order_types` is the SECOND
    // self-parented list, and this is the check that makes the second one
    // safe. Every default on the `hierarchical` path is area-law
    // ("Parent area", "Add a sub-area", "· 3 sub-areas"), so a card that
    // declared the mechanism and borrowed the words would render area
    // vocabulary over work order types — correct-looking, wrong, and invisible
    // to `tsc`, to every DOM test and to every gate, because the strings are
    // config rather than code. Nothing else in this suite can see it.
    const selfParented = REFERENCE_CARDS.filter((card) => card.hierarchical !== undefined);
    expect(selfParented.map((card) => card.code).sort()).toEqual([
      "areas",
      "work_order_types",
    ]);
    for (const card of selfParented) {
      const levels = card.hierarchical!;
      const keys = Object.values(levels);
      // Every key is a real string, and no two cards share one.
      expect(keys.every((k) => typeof k === "string" && k.length > 0)).toBe(true);
      expect(new Set(keys).size).toBe(keys.length);
    }
    // …and the two cards share NO key at all: one borrowed key is one screen
    // saying "area" where it means "type".
    const [first, second] = selfParented.map((card) => Object.values(card.hierarchical!));
    expect(first.filter((k) => second.includes(k))).toEqual([]);

    // The work order type card's nouns, named so a rename cannot happen quietly.
    const work = referenceCard("work_order_types")?.hierarchical;
    expect(work?.topKey).toBe("settings.reference.level.workType");
    expect(work?.subKey).toBe("settings.reference.level.workSubType");
    expect(work?.parentLabelKey).toBe("settings.reference.col.parentWorkType");
    expect(work?.countKey).toBe("settings.reference.subTypeCount");
  });

  it("renders type → sub-type: the Account type column names each row's parent", () => {
    const html = renderReference("/settings/reference-data?list=account_subtypes", {
      cards: [{ list: "account_subtypes", owner: "customers", count: 12, state: "seeded" }],
      entries: {
        list: "account_subtypes",
        rows: [
          subtype("healthcare", "Healthcare", { code: "commercial", name: "Commercial" }),
          subtype("schools", "Schools", { code: "government", name: "Government" }),
        ],
      },
    });
    // The parent column carries the CARD's own label, not areas' "Parent area".
    expect(html).toContain("Account type");
    expect(html).not.toContain("Parent area");
    expect(html).toContain("Commercial");
    expect(html).toContain("Government");
  });

  it("a pre-ruling row with no parent renders an em dash, never a guessed type", () => {
    const html = renderReference("/settings/reference-data?list=account_subtypes", {
      cards: [{ list: "account_subtypes", owner: "customers", count: 1, state: "seeded" }],
      entries: { list: "account_subtypes", rows: [subtype("legacy", "Legacy sub-type", null)] },
    });
    expect(html).toContain("—");
  });

  it("offers every ACTIVE account type as a parent — cross-list rows have no self/sub-row to exclude", () => {
    const types: LookupEntry[] = [
      { id: "t1", code: "residential", name: "Residential", active: true, is_system: true, used_by: 0 },
      { id: "t2", code: "commercial", name: "Commercial", active: true, is_system: true, used_by: 0 },
      { id: "t3", code: "industrial", name: "Industrial", active: false, is_system: true, used_by: 0 },
    ];
    // Same helper the modal uses: inactive rows drop, the rest are offerable.
    expect(parentOptionsFor(types, "st-healthcare").map((row) => row.code)).toEqual([
      "residential",
      "commercial",
    ]);
  });
});

describe("US-TEN-011 — deactivate, delete and the 🔒 audit-lock", () => {
  it("US-TEN-011 TC-1/TC-2: an unused entry offers a real Delete, and Deactivate is always offered", () => {
    const html = renderReference("/settings/reference-data?list=uoms", {
      entries: { list: "uoms", rows: [uom("TAMPER", "Tamper fee", 0)] },
    });
    expect(deleteIsLocked(uom("TAMPER", "Tamper fee", 0))).toBe(false);
    expect(html).toContain('aria-label="Delete"');
    expect(html).toContain('aria-label="Deactivate"');
    expect(html).not.toContain("🔒");
  });

  it("US-TEN-011 TC-3/TC-4: a USED entry shows 🔒 Delete disabled with its reason, and deactivation stays open", () => {
    const late = uom("LATE", "Late payment fee", 1240);
    expect(deleteIsLocked(late)).toBe(true);
    const html = renderReference("/settings/reference-data?list=uoms", {
      entries: { list: "uoms", rows: [late] },
    });
    expect(html).toContain("🔒 Delete");
    expect(html).toContain("Locked — 1240 records reference this entry. Deactivate it instead.");
    // ⚠ WAS `toContain("settings-locked")` UNTIL 2026-08-20 — a CLASS NAME, and
    // the class is gone: the kit already writes `disabled:cursor-not-allowed`
    // and `disabled:opacity-45`, so `.settings-locked` was a third statement of
    // a thing stated twice. The assertion now reads the BEHAVIOUR the test case
    // is about — the control is present, carries the lock reason, and cannot be
    // pressed — which is what TC-3 says and what a class name only ever implied.
    const deleteBtn = /<button[^>]*aria-label="🔒 Delete"[^>]*>/.exec(html)?.[0] ?? "";
    expect(deleteBtn, "the 🔒 Delete control must render").not.toBe("");
    expect(deleteBtn, "BR-TEN-034 — locked delete is DISABLED, not hidden").toContain("disabled");
    // BR-TEN-034: deactivation is never blocked by the lock.
    expect(html).toContain('aria-label="Deactivate"');
  });

  it("US-TEN-011 TC-4/TC-5: the API refusal is the law — a race loses on the SERVER's fresh count", () => {
    const locked = new ApiError(409, {
      code: "BIZ-LOCKED",
      message_key: "settings.lookups.locked_referenced",
      params: { used_by: 1 },
      br_ref: "BR-TEN-034",
    });
    const refusal = refusalOf(locked, t);
    expect(refusal.message).toBe(
      "1 records reference this entry, so it can't be deleted. Deactivate it instead.",
    );
    expect(refusal.brRef).toBe("BR-TEN-034");
    const html = renderToStaticMarkup(<RefusalNotice refusal={refusal} />);
    expect(html).toContain("Deactivate it instead");
  });

  it("BR-TEN-029: tax jurisdictions cannot be deactivated — the reason shows, the control is dead-on-arrival-proof", () => {
    // The owning table has no active column at all, so the server answers 409
    // rather than recording nothing. A live button here would always fail, so
    // it renders DISABLED WITH THE REASON (BR-SHL-025) and the view says why.
    const html = renderReference("/settings/reference-data?list=tax_jurisdictions", {
      entries: {
        list: "tax_jurisdictions",
        rows: [{ id: "j1", code: "Fort Bend County", name: "Fort Bend County", active: true, is_system: false, used_by: 0, level: "county" }],
      },
    });
    expect(html).toContain("Rows in this list can&#x27;t be deactivated yet");
    // The control is present (never silently missing) but disabled with reason.
    expect(html).toContain('aria-label="Deactivate"');
    expect(html).toMatch(/Rows in this list can&#x27;t be deactivated yet[^"]*"[^>]*disabled|disabled[^>]*title="Rows in this list/);
    // Every other list keeps a live Deactivate — this is per-list config.
    const uoms = renderReference("/settings/reference-data?list=uoms", {
      entries: { list: "uoms", rows: [uom("kWh", "Kilowatt hour", 0)] },
    });
    expect(uoms).not.toContain("Rows in this list can&#x27;t be deactivated yet");
  });

  it("the server's own 409 renders verbatim when a deactivate is attempted anyway", () => {
    // Defence in depth: the disabled control is convenience; THIS is the law.
    const refused = new ApiError(409, {
      code: "BIZ-STATE",
      message_key: "rating.lookups.deactivate_unsupported",
      params: { list: "tax_jurisdictions", name: "Fort Bend County" },
      br_ref: "BR-TEN-029",
    });
    const refusal = refusalOf(refused, t);
    expect(refusal.message).toBe(
      "Fort Bend County can't be deactivated: this list has nowhere to record it yet.",
    );
    expect(refusal.brRef).toBe("BR-TEN-029");
  });

  it.todo("US-TEN-011 TC-6 (isolation): lock state is per tenant — server/RLS scope (G5)");
});

describe("BR-SHL-035 — the rule cards use the SAME frame, with a form body", () => {
  it("S63 holiday calendar renders inside the identical shell, with the shared date cell", () => {
    const html = renderReference("/settings/reference-data?list=holidays", {
      holidays: [
        { id: "h1", date: "2026-07-04", label: "Independence Day" },
        { id: "h2", date: "2026-11-26", label: "Thanksgiving" },
      ],
    });
    // The same shell as a LIST card — that is the whole point of BR-SHL-035.
    expect(html).toContain("settings-frame");
    expect(html).toContain("← Reference data");
    expect(html).toContain("recorded in the audit log");
    // …with a rule body instead of the lookup table.
    expect(html).toContain("Holiday calendar");
    expect(html).toContain("Independence Day");
    expect(html).toContain("+ Add holiday");
    // BR-SHL-034: the date renders through DateCell, not a hand-rolled string.
    expect(html).toContain('dateTime="2026-07-04"');
    expect(html).toContain("07/04/2026");
  });

  it("S64 opens as the PER-SERVICE page in that identical frame (CR-038 A1)", () => {
    // Same shell as every card (BR-SHL-035) — back-link, header, audit line —
    // with the per-service body: one panel per enabled service, the locked
    // integrity list, and the fail-safe state written out for a service with
    // no figures. The panel mechanics live in SettingsReadValidation.test.tsx;
    // THIS case pins the card → frame → body wiring.
    const html = renderReference("/settings/reference-data?list=read_validation", {
      readValidation: READ_VALIDATION_OVERVIEW,
    });
    expect(html).toContain("settings-frame");
    expect(html).toContain("← Reference data");
    expect(html).toContain("recorded in the audit log");
    expect(html).toContain("High-use threshold");
    expect(html).toContain("Always runs"); // the locked integrity vocabulary
    expect(html).toContain("Save Electric thresholds");
    // ⚠ `"skipped and reported"` WAS ASSERTED HERE AND IS NOT ANY MORE
    // (DEF-900, 2026-08-27). It is gas's honest fail-safe sentence, and the PO
    // ruled each service into an expand/collapse panel, so only the FIRST
    // service — electric, asserted above — lands open. This suite renders
    // statically and cannot click, so the sentence is one click away rather
    // than absent. It is still asserted, on a one-service render, in
    // `SettingsReadValidation.test.tsx`; what this test is FOR is the shared
    // frame, and the frame is what the four assertions above check.
    // Gas is still PRESENT — its panel header renders whether or not it is
    // open — so this proves the page did not silently drop a service:
    expect(html).toContain("Gas");
  });

  it("S66/S69/S70 open as FORMS in that identical frame (their endpoints landed)", () => {
    // These rule pages used to state a gap. Their endpoints exist now, so each
    // one renders the SAME shell — back-link, header, audit line — with a form
    // where a list card has its table. No new screen was added for any of them:
    // one component reads settingsRulePages.ts and serves them all — including
    // S71 Finance controls, which is still one of those RULE_PAGES rows
    // but is now reached from Settings → Accounting rather than from here.
    const expected: Record<string, { rules: RuleDocument; marker: string }> = {
      billing_defaults: { rules: BILLING_DEFAULTS_RULES, marker: "Late fee rate" },
      budget_billing: {
        rules: { eligibility_months: 12, level_rounding: "whole_dollar" },
        marker: "History needed to qualify",
      },
      collections_notices: {
        // The marker was "Notice ladder" until 2026-08-17. That field moved to
        // Settings → Notifications with the rest of the chasing schedule
        // (BR-NOT-017, PO ruling), so this card is asserted on a row that is
        // still ITS OWN — the payment-plan reminder, which the ruling does not
        // name and which this page keeps.
        rules: { plan_reminder_days_before: 3, suppress_paper_on_bad_address: true },
        marker: "Payment-plan reminder before installment",
      },
      // finance_controls is deliberately ABSENT: CR-004 task C moved it to the
      // Accounting tab (PO 2026-08-16 *"this is moved to accounting tab"*), so
      // it no longer opens from this grid at all. Its rendering is asserted in
      // SettingsAccountingTab.test.tsx, and its ABSENCE here is asserted below.
    };
    for (const [code, { rules, marker }] of Object.entries(expected)) {
      const html = renderReference(`/settings/reference-data?list=${code}`, { rules: { code, rules } });
      expect(html).toContain("settings-frame");
      expect(html).toContain("← Reference data");
      expect(html).toContain("recorded in the audit log");
      expect(html).toContain(marker);
      // The form body: real inputs and a real save, in the shared save bar.
      expect(html).toContain("<input");
      expect(html).toContain("Save these rules");
      // BR-TEN-043 stated on every rule page, not just some.
      expect(html).toContain("New values apply from now on");
      // …and still nothing that could edit history or leave this frame.
      expect(html).not.toContain("settings-arrives");
    }
  });

  it("DEF-235: account statuses and types open as LIVE table views — the 'arrives with' claim is dead", () => {
    // This case asserted the OPPOSITE until 2026-08-17 — "they state that they
    // arrive with Accounts — they are not faked" — and it passed for a week
    // over two lists that were seeded (5 statuses, 4 types), structural, and
    // served by handlers registered since 2026-08-10. The test pinned the
    // defect as correct, which is DEF-235's escape reason in one line. Both
    // cards now drive the same management view as every other live list.
    for (const code of ["account_statuses", "account_types"]) {
      const html = renderReference(`/settings/reference-data?list=${code}`, {});
      expect(html).not.toContain("arrive with the Accounts feature");
      expect(html).toContain("settings-frame");
      expect(html).toContain("← Reference data");
      // The same frame carries the audit line every live card shows.
      expect(html).toContain("recorded in the audit log");
    }
  });

  it("every rule card is a Reference-data CARD, not a screen of its own", () => {
    expect(ruleCards().map((card) => card.code)).toEqual([
      // `DEF-CUS-10445` (PO 2026-10-22, *"Default 15 days"*) — the ACCOUNTS
      // section's Service requests card, declared after Account sub-types.
      "service_requests",
      // CR-068 wave D (US-CWP-074): the first record in this product that
      // models a physical place, as a card in the SAME frame (BR-SHL-035).
      "service_centres",
      "holidays",
      "read_validation",
      "billing_defaults",
      "budget_billing",
      "collections_notices",
      // ⚠ **DEF-REP-7050 — THESE TWO WERE MISSING AND THIS PIN WAS RED FROM
      // `97ac0ddd0` (2026-09-27) UNTIL IT WAS READ.** `P4.6` added two
      // `kind: "rules"` cards to the grid and did not move the pin that counts
      // them, so `ruleCards()` returned 8 against an expected 6. The pin did
      // exactly its job — it is a pin so that a rule card cannot arrive
      // unnoticed — and nobody read its output. Hard-won law 7: a guard is a
      // claim only while somebody reads it.
      "file_retention",
      "default_format",
      // CR-004 task C: "finance_controls" is NOT here any more. PO 2026-08-16,
      // asked whether Finance controls was dropped or moved: "this is moved to
      // accounting tab". r10 SET-04 draws one card under FINANCE (Import
      // mappings) and no Finance controls card.
    ]);
    for (const card of ruleCards()) {
      expect(card.kind).toBe("rules");
      expect(card.labelKey.startsWith("settings.reference.card.")).toBe(true);
    }
  });

  it("CR-004 task C: Finance controls has LEFT this grid — and its old deep link still lands somewhere honest", () => {
    // 1 · The card is gone from the registry, so nothing draws it and nothing
    //     resolves it. The FINANCE heading survives on its remaining card.
    expect(REFERENCE_CARDS.map((card) => card.code)).not.toContain("finance_controls");
    expect(referenceCard("finance_controls")).toBeNull();
    expect(REFERENCE_CARDS.filter((card) => card.group === "finance").map((card) => card.code)).toEqual([
      "import_mappings",
    ]);

    // 2 · The MOVE is a move, not a deletion: the rule page itself, its slug and
    //     its seven parameters are untouched in settingsRulePages.ts, which is
    //     still the single source of the field law wherever it is rendered.
    const page = rulePageForCard("finance_controls");
    expect(page?.slug).toBe("finance-controls");
    expect(page?.screen).toBe("S71");
    // 7 → 9 on 2026-08-17: CR-008 rulings 7 and 2 added the bank-match AMOUNT
    // tolerance (default $0.00, which is today's exact-to-the-penny behaviour)
    // and the MANUAL write-off approval threshold, which is a separate field
    // from the automatic small-balance one already on this page.
    expect(page?.params).toHaveLength(9);

    // 3 · The deep link. `?list=finance_controls` was a live URL until today, so
    //     a bookmark or a checklist link may still carry it. BR-SHL-011's
    //     spirit: an unknown ?list falls back to the GRID — it does not 500 and
    //     it does not draw an empty frame. Same path `?list=nonsense` takes.
    expect(openCardFrom(new URLSearchParams("list=finance_controls"))).toBeNull();
    const html = renderReference("/settings/reference-data?list=finance_controls", {});
    expect(html).toContain("lookup-grid"); // the grid, rendered whole
    expect(html).toContain("Units of measure");
    expect(html).not.toContain("settings-frame"); // …and NOT an empty card frame
    expect(html).not.toContain("Days-sales-outstanding target");
    // The grid it lands on no longer offers the card it was pointed at.
    expect(html).not.toContain("Bank match tolerance, write-off threshold, back-bill cap");
  });

  // ── CR-004 task A3 · the OPT-IN Utility-service column ───────────────────
  // r10 SET-04 draws Code · Name · Utility service · Used by · Status · Actions
  // on its list sub-screens. The column is real and it is PER LIST: BR-TEN-078
  // (PO 2026-08-17, "I have clariffied - already - dont attached them to
  // service") scopes exactly ONE list, `uoms`. Nine are CONFIRMED unscoped and
  // eight are unruled and unscoped by default. So these cases assert the column
  // in BOTH directions — it appears where the ruling put it and NOWHERE else —
  // because a column that leaks onto an unscoped list renders a row of blanks,
  // and a blank column reads as "no value" rather than "not a question we ask".
  it("CR-004 A3: the Utility-service column renders for uoms — a scoped row by name, an unscoped row as All services", () => {
    const html = renderReference("/settings/reference-data?list=uoms", {
      entries: {
        list: "uoms",
        rows: [
          // The stored scope: this unit belongs to Water and to nothing else.
          scopedUom("kgal", "Thousand gallons", "water"),
          // `null` — the VALUE "All services". A month is billable on any
          // service, and this is the state the sentence exists for.
          scopedUom("month", "Month (flat)", null),
        ],
      },
    });
    // r10's own header text, third column, before Used by.
    expect(html).toContain("<th>Utility service</th>");
    expect(html).toContain("<td>Water</td>");
    expect(html).toContain("<td>All services</td>");
    // …in r10's order: Name, then Utility service, then Used by. Compared
    // INSIDE `<thead>` on purpose — the column-chooser panel lists every label
    // earlier in the document, so a whole-document indexOf would compare the
    // chooser against the header and pass or fail for the wrong reason.
    const head = html.slice(html.indexOf("<thead>"), html.indexOf("</thead>"));
    expect(head.indexOf("<th>Utility service</th>")).toBeGreaterThan(head.indexOf(">Name<"));
    expect(head.indexOf("<th>Utility service</th>")).toBeLessThan(head.indexOf(">Used by<"));
    // It is a REAL column, not a hard-coded cell: the shared chooser offers it
    // alongside the others, so it hides and reorders like every other column.
    expect(html).toContain('aria-label="Move Utility service up"');
  });

  it("CR-004 A3: a list that does NOT declare the scope draws no such column — absent is not blank", () => {
    // asset_types carries a detail column (`category`) and no `serviceScoped`
    // flag, so the shell is identical and this ONE column is missing. Its rows
    // publish no `service` key at all, which is a different fact from `null`.
    const html = renderReference("/settings/reference-data?list=asset_types", {
      entries: { list: "asset_types", rows: [assetType("MTR-E", "Electric meter", "meter")] },
    });
    expect(html).toContain("data-table"); // same view, same shell
    expect(html).toContain("<th>Category</th>"); // its own detail column is there
    expect(html).not.toContain("<th>Utility service</th>");
    expect(html).not.toContain("All services");
  });

  it("BR-TEN-078: TWO cards declare the scope since 2026-09-02 — uoms, and size classes", () => {
    // ⚠ **THIS PINNED `["uoms"]` ALONE UNTIL 2026-09-02 AND IT WAS DOING ITS
    // JOB.** Its own comment asked that a second card here be "somebody's
    // deliberate act, reviewed against the PO's own list" — and that is exactly
    // what happened, so the list moves and the guard stays.
    //
    // PO ruling 2026-09-02 (CR-065), verbatim, sent with a screenshot of the
    // Fire rate schedule pricing *Electric CT-metered*: *"This is where we are
    // setting rates for fire  you should show only capacity for fire . in
    // Setting a capacity needs to tags to utility services ."* It supersedes
    // BR-TEN-078 for `service_size_classes` and for nothing else — the nine
    // CONFIRMED-unscoped lists and the unruled ones are untouched, and a THIRD
    // card appearing here still needs a ruling of its own.
    expect(
      REFERENCE_CARDS.filter((card) => card.serviceScoped === true)
        .map((c) => c.code)
        .sort(),
    ).toEqual(["service_size_classes", "uoms"]);
  });

  // ── DEF-203 · bank accounts are a CARD, not a screen ─────────────────────
  it("DEF-203: the bank-accounts card is a config row owned by payments, with the mask as its detail", () => {
    // BR-SHL-035 — the whole frontend half of "a utility can create its own
    // bank accounts" is this row. If a future change turns it into its own
    // screen, this is the assertion that says so out loud.
    const card = referenceCard("bank_accounts");
    expect(card).not.toBeNull();
    expect(card?.kind).toBe("list");
    expect(card?.group).toBe("payments");
    // BR-TEN-031: payments owns the table, so payments validates and writes.
    expect(card?.owner).toBe("payments");
    // The detail slot is the display MASK — never an account-number field.
    expect(card?.detailField).toEqual({
      field: "mask",
      labelKey: "settings.reference.col.mask",
    });
    // Nothing seeds it, so it must NOT claim "arrives with a future feature":
    // the list is live and empty, which is a different sentence (DEF-235).
    expect(card?.arrivesWithKey).toBeUndefined();
  });

  it("DEF-203: the ONE view draws the mask column and the account it belongs to", () => {
    const html = renderReference("/settings/reference-data?list=bank_accounts", {
      cards: [{ list: "bank_accounts", owner: "payments", count: 1, state: "seeded" }],
      entries: {
        list: "bank_accounts",
        rows: [
          {
            id: "id-chase",
            code: "Chase Operating",
            name: "Chase Operating",
            active: true,
            is_system: false,
            used_by: 0,
            mask: "4021",
          },
        ],
      },
    });
    expect(html).toContain("data-table"); // the same shell as every other card
    expect(html).toContain("<th>Last digits</th>");
    expect(html).toContain("Chase Operating");
    expect(html).toContain("4021");
    // …and no account-number column anywhere near it.
    expect(html).not.toContain("Account number");
  });

  it("CR-004 A3: the cell tells `null` (All services) apart from ABSENT (nothing to say)", () => {
    // `LookupEntry.service` is optional AND nullable, and those are two
    // different statements. A row on a scoped list that publishes no scope at
    // all gets an EMPTY cell: writing "All services" there would assert a
    // permission nobody granted.
    expect(serviceScopeText(scopedUom("kgal", "Thousand gallons", "water"), t)).toBe("Water");
    expect(serviceScopeText(scopedUom("month", "Month (flat)", null), t)).toBe("All services");
    expect(serviceScopeText(uom("kWh", "Kilowatt hour", 0), t)).toBe("");
    // All TEN platform services resolve to a NAME, never to a raw key — the
    // reason the label comes from `rating.service.*` (ten codes) rather than
    // `metering.service.*` (six, and `storm_water` would print raw). ⚠ That
    // six-key namespace no longer has a call site anywhere: DEF-763 re-pointed
    // the four screens that read it, and `features/rating/serviceNamespace.test.ts`
    // asserts none comes back.
    for (const code of [
      "electric",
      "water",
      "gas",
      "sewer",
      "trash",
      "storm_water",
      "solar",
      "broadband",
      "thermal_heat",
      "battery",
    ]) {
      const label = serviceScopeText(scopedUom("x", "x", code), t);
      expect(label).not.toBe(`rating.service.${code}`);
      expect(label).not.toBe(code);
    }
    // …and a service this build has never heard of degrades to its own code,
    // not to a key printed at a utility clerk.
    expect(serviceScopeText(scopedUom("x", "x", "hydrogen"), t)).toBe("hydrogen");
  });

  // DEF-188 — the two halves, both provable without a browser.
  it("DEF-188: a platform-seeded row cannot be deleted, and the lock says which reason", () => {
    // A seeded row nothing references: `used_by` is 0, so the OLD predicate
    // said "not locked" and the screen offered an enabled Delete that the
    // server then refused with a key no catalogue carried.
    const seeded: LookupEntry = { ...uom("OCC-T", "Occupied · tenant-billed", 0), is_system: true };
    expect(deleteIsLocked(seeded)).toBe(true);
    expect(deleteLockReason(seeded)).toBe("system");

    // A referenced row keeps the MORE SPECIFIC reason: telling a user how many
    // records point at it is what tells them to deactivate instead.
    const referenced: LookupEntry = { ...uom("VAC", "Vacant · base charges only", 3), is_system: true };
    expect(deleteLockReason(referenced)).toBe("referenced");

    // And a tenant's own unused row is still freely deletable — the fix must
    // not lock rows the audit-lock was never about (BR-TEN-034).
    const tenantOwn: LookupEntry = uom("MINE", "A code this tenant added", 0);
    expect(deleteIsLocked(tenantOwn)).toBe(false);
    expect(deleteLockReason(tenantOwn)).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07; co-stories US-TEN-010/011@178c282; co-packet EP-MET-04@34f14b6)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-09 by story-coder (frontend integration lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope)
// amended:   2026-08-16 by story-coder (CR-004 task C) — the two assertions that pinned `finance_controls` as a card in this grid are UPDATED to the new contract rather than deleted (`ruleCards()` is five, and the rule-page render loop drops its entry), and a new one asserts what the CR actually promises: the card is gone, the FINANCE heading keeps its remaining card, `rulePageForCard("finance_controls")` still answers with S71's seven parameters, and the now-dead `?list=finance_controls` deep link falls back to the GRID instead of erroring or drawing an empty frame. That last assertion did not exist before — the deep link was the part of this move most likely to break a bookmark and had nothing defending it.
// exceptions: E4 the previously-todo US-TEN-010 TC-1 now runs (the four catalogs render); TC-2 (type-to-search) and TC-5 (duplicate refusal round trip) stay todo as genuine browser-interaction scope — the debouncer and the modal submit both need a live DOM
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// DEF-902 — a list older than the platform fixture SAYS SO (BR-TEN-161)
// PO verbatim, on the live app at v2.61.1: *"in this setting - unable to see
// sub areas"*. Seven area rows in the fixture, four on the tenant, and the
// three the PO had ratified that same morning (OQ-432) among the missing.
// ══════════════════════════════════════════════════════════════════════════
const AREA_ROWS: LookupEntry[] = [
  { id: "a1", code: "NORTH", name: "North district", active: true, is_system: true, used_by: 0 },
  { id: "a2", code: "DTWN", name: "Downtown", active: true, is_system: true, used_by: 0 },
  { id: "a3", code: "EAST", name: "East district", active: true, is_system: true, used_by: 0 },
  {
    id: "a4",
    code: "IND",
    name: "Industrial corridor",
    active: true,
    is_system: true,
    used_by: 0,
  },
];

/** DEF-902's measured case, exactly as the server reports it. */
const AREAS_BEHIND: ReferenceFixtureGap = {
  list: "areas",
  fixture_version: "V2.48.0.2",
  seeded_version: "V2.19.0.0",
  missing: [
    { code: "NORTH-NE", name: "NE" },
    { code: "NORTH-NW", name: "NW" },
    { code: "EAST-SE", name: "SE" },
  ],
  held: 4,
  fixture_entries: 7,
  // BR-TEN-160: `areas` is SAMPLE content, so no sweep will ever deliver it.
  sweep_delivers: false,
};

describe("DEF-902 — the product says when a list is behind the platform fixture", () => {
  it("names the missing entries — by name and code, never a bare count", () => {
    const html = renderReference("/settings/reference-data?list=areas", {
      entries: { list: "areas", rows: AREA_ROWS },
      fixtureGap: AREAS_BEHIND,
    });
    expect(html).toContain('data-fixture-gap="3"');
    // The three the PO ratified under OQ-432 and then could not see.
    expect(html).toContain("NE (NORTH-NE)");
    expect(html).toContain("NW (NORTH-NW)");
    expect(html).toContain("SE (EAST-SE)");
    expect(html).toContain("V2.48.0.2");
  });

  it("says what to do about it, and the sentence follows BR-TEN-160", () => {
    const html = renderReference("/settings/reference-data?list=areas", {
      entries: { list: "areas", rows: AREA_ROWS },
      fixtureGap: AREAS_BEHIND,
    });
    // `sweep_delivers: false` ⇒ nothing adds them on its own. The copy is
    // chosen from the SERVED flag, so it cannot drift from the policy.
    expect(html).toContain(t("settings.reference.behind.repair"));
    expect(html).not.toContain(t("settings.reference.behind.sweep"));
  });

  it("a STRUCTURAL list that is behind gets the other sentence", () => {
    const html = renderReference("/settings/reference-data?list=read_methods", {
      entries: { list: "read_methods", rows: AREA_ROWS },
      fixtureGap: { ...AREAS_BEHIND, list: "read_methods", sweep_delivers: true },
    });
    expect(html).toContain(t("settings.reference.behind.sweep"));
    expect(html).not.toContain(t("settings.reference.behind.repair"));
  });

  it("a CURRENT list says nothing at all — a notice is a statement of fact", () => {
    const html = renderReference("/settings/reference-data?list=areas", {
      entries: { list: "areas", rows: AREA_ROWS },
      fixtureGap: { ...AREAS_BEHIND, missing: [], held: 7 },
    });
    expect(html).not.toContain("data-fixture-gap");
  });

  it("an UNANSWERED probe says nothing either — never 'nothing is missing'", () => {
    // The read has not landed. Claiming the list is current would be a
    // statement we cannot make, and it is the statement DEF-902 is about.
    const html = renderReference("/settings/reference-data?list=areas", {
      entries: { list: "areas", rows: AREA_ROWS },
    });
    expect(html).not.toContain("data-fixture-gap");
  });

  it("DEF-CUS-9808: an account type can be stopped or offered again on new accounts", () => {
    // OQ-CUS-12407 (a), PO 2026-09-18: any tenant admin, any row, seeded rows
    // included. Government arrives legacy (BR-CUS-094): it says Not offered and
    // its control reads Offer again; Residential's reads Stop offering.
    const html = renderReference("/settings/reference-data?list=account_types", {
      entries: {
        list: "account_types",
        rows: [
          { ...uom("residential", "Residential", 3), is_system: true, legacy: false },
          { ...uom("government", "Government", 0), is_system: true, legacy: true },
        ],
      },
    });
    expect(html).toContain("Not offered");
    expect(html).toContain('aria-label="Offer again"');
    expect(html).toContain('aria-label="Stop offering"');
    // A list with no such column draws no such control.
    const uoms = renderReference("/settings/reference-data?list=uoms", {
      entries: { list: "uoms", rows: [uom("kWh", "Kilowatt hour", 0)] },
    });
    expect(uoms).not.toContain("Stop offering");
    expect(uoms).not.toContain("Not offered");
  });
});
