// ── Trace ──────────────────────────────────────────────
// Change:   CR-060 C15 · task T5 (widen the cost categories — but NOT to
//           capital assets) and its T7c flag.
//           Screens: S73 (the capture form's Category field)
// Rules:    BR-LED-029 as AMENDED 2026-09-01 (sixteen categories in five
//           operating-statement groups; five capital names refused BY NAME,
//           pointing at the asset) · BR-SHL-025 (a control that cannot be
//           offered is SHOWN with its reason, never hidden) · B14 rule 21 (a
//           file not on route-b-migrated.txt adds NO class) · B14 rule 32 (a
//           screen's description budget)
// ───────────────────────────────────────────────────────
// **THE REFUSAL IS THE POINT OF THIS FILE.** The tidier screen sits right
// beside it and would be a lie: a picker that simply OMITS the capital names
// teaches a clerk nothing — they would look for somewhere to record the truck,
// not find it, and file it under Infrastructure, which is the exact $40,000
// error the refusal exists to prevent. Present-and-unselectable is the shape
// `FieldOption.disabled` was built for and says so in its own comment.
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CostRegisterResponse } from "@/api/endpoints";

import { captureCategoryOptions, cautionFor } from "./CostOfServicePage";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

function register(overrides: Partial<CostRegisterResponse> = {}): CostRegisterResponse {
  return {
    rows: [],
    total_amount: null,
    currency: "USD",
    count: 0,
    sort: "-date",
    bulk_actions: [],
    categories: ["water", "operations_maintenance", "admin_payroll_benefits"],
    category_catalog: [
      {
        code: "water",
        label: "Water",
        group: "cost_of_service",
        group_label: "Cost of service",
        enters_recovery_denominator: true,
        caution: null,
        account_code: "5110",
      },
      {
        code: "operations_maintenance",
        label: "Operations & maintenance",
        group: "operations_maintenance",
        group_label: "Operations & maintenance",
        enters_recovery_denominator: false,
        caution: null,
        account_code: "5200",
      },
      {
        code: "admin_payroll_benefits",
        label: "Payroll & benefits",
        group: "administrative_general",
        group_label: "Administrative & general",
        enters_recovery_denominator: false,
        caution:
          "A record of what left the bank, and nothing more. This is not payroll accounting.",
        account_code: "5500",
      },
    ],
    refused_categories: [
      {
        code: "capital_assets",
        label: "Capital assets",
        reason: "a capitalised asset is not a cost of this period",
        record_on: "asset",
      },
      {
        code: "depreciation",
        label: "Depreciation",
        reason: "depreciation is COMPUTED from the asset's own cost, method and expected life",
        record_on: "asset",
      },
    ],
    forbidden_actions: [],
    pending_finance_re_sign_cost: [],
    cost_section_source: "",
    posting: { posted: false, reason: "capture_posts_nothing_in_r2" },
    ...overrides,
  };
}

describe("S73 · the widened category picker (CR-060 T5)", () => {
  it("offers every capturable category under its operating-statement group", () => {
    const options = captureCategoryOptions(register(), t);
    const capturable = options.filter((option) => option.disabled !== true);

    expect(capturable.map((option) => option.value)).toEqual([
      "water",
      "operations_maintenance",
      "admin_payroll_benefits",
    ]);
    // The bucket rides the LABEL, because a native <select> has no <optgroup>
    // here and a disabled separator row would put an unselectable entry into a
    // list of choices.
    expect(capturable[2].label).toBe("Administrative & general · Payroll & benefits");
    // A service reads as a name, not as a code — the picker showed the bare
    // code until 2026-09-01 and would have read as two kinds of thing in one
    // list beside the categories.
    expect(capturable[0].label).toBe("Cost of service · Water");
  });

  it("shows a capital category and refuses to let it be chosen", () => {
    const options = captureCategoryOptions(register(), t);
    const refused = options.filter((option) => option.disabled === true);

    expect(refused.map((option) => option.value)).toEqual(["capital_assets", "depreciation"]);
    // **PRESENT, and the label says where the money goes instead.** Hiding
    // them is the failure this test exists for: a clerk who cannot find
    // anywhere to record a $40,000 truck files it under Infrastructure.
    for (const option of refused) {
      expect(option.label).toContain("record it on the asset instead");
    }
    expect(refused[0].label).toBe("Capital assets — record it on the asset instead");
  });

  it("never lets a refused category be submitted from the picker", () => {
    const options = captureCategoryOptions(register(), t);
    const selectable = new Set(
      options.filter((option) => option.disabled !== true).map((option) => option.value),
    );
    expect(selectable.has("capital_assets")).toBe(false);
    expect(selectable.has("depreciation")).toBe(false);
  });

  it("falls back to the flat list when the catalog is absent", () => {
    // A server or a mock predating 2026-09-01 still renders a working picker —
    // `categories` is the contract and `category_catalog` is additive.
    const options = captureCategoryOptions(
      register({ category_catalog: undefined, refused_categories: undefined }),
      t,
    );
    expect(options.map((option) => option.value)).toEqual([
      "water",
      "operations_maintenance",
      "admin_payroll_benefits",
    ]);
    expect(options.every((option) => option.disabled !== true)).toBe(true);
  });

  it("shows the payroll caution only on payroll", () => {
    const data = register();
    // B14 rule 32's description budget: one sentence, and only where it means
    // something. CR-060 §6 is explicit that payroll needs it — a one-line
    // figure does not carry the withholdings a utility remits.
    expect(cautionFor(data, "admin_payroll_benefits")).toContain("not payroll accounting");
    expect(cautionFor(data, "water")).toBeNull();
    expect(cautionFor(data, "operations_maintenance")).toBeNull();
  });

  it("adds no Tailwind utility, because features/ledger is not migrated", () => {
    // B14 rule 21 / DEF-974: a utility written in an unmigrated file renders as
    // NOTHING while tsc, eslint and every toContain assertion pass on it. The
    // grouping rides the option label and the caution rides SelectField's own
    // `help`, so nothing here emits a class at all.
    const options = captureCategoryOptions(register(), t);
    for (const option of options) {
      expect(option).not.toHaveProperty("className");
    }
  });
});
