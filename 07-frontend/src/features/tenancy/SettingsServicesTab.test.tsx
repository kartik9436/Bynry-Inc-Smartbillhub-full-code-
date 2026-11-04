// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-007 · US-TEN-008 (EP-TEN-06 §Stories)  Screens: S8 (Settings → Services & UoM)
// Rules:    BR-TEN-025 (closed catalog — toggle only) · BR-TEN-026 (guarded disable, counts named) ·
//           BR-TEN-027 (UoM forward-only, affected schedules NAMED) · BR-TEN-029 (deactivated UoM
//           entries excluded from NEW pickers) · BR-SHL-032 (confirms name the action) ·
//           BR-RAT-081 (a service DECLARES HOW IT IS BILLED, one of THREE — DEF-2409, PO 2026-09-02,
//           superseding the metered/unmetered boolean of DEF-2310) · BR-RAT-038 (the
//           register→billed UoM pair, or a stated conversion factor — DEF-2311) · BR-TEN-810 (the
//           declaration is forward-only and NAMES the accounts whose next bill moves)
// ───────────────────────────────────────────────────────
// §4 test data: Brazos Bend — Electric On (kWh / kW, 3 schedules, 612 accounts),
// Water On (kgal / ccf, 2 schedules, 568 accounts), Gas Off.
//
// Sewer and Trash were ADDED on 2026-09-02 and they are not decoration: sewer
// is the one service the metered/unmetered boolean could describe with NEITHER
// of its values, and trash is the count the `false` side used to mean. Gas now
// carries NO declaration. ⚠ The SERVER always answers the key (BR-TEN-1180,
// `selectors.service_row`), so this row is a GUARD and not a picture of today:
// it pins that a payload which ever loses the key makes the screen go quiet
// rather than confident. Four rows, four states — the fourth "not recorded".
//
// ⚠ THE WIRING HALF IS NOT HERE. This suite renders; whether the clerk's choice
// reaches the API layer is `SettingsServicesBasis.dom.test.tsx`, which drives
// the modal and reads the request body (hard-won law 2).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { LookupEntry, TenantServiceRow, TenantServiceSaved } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { collectFormErrors } from "@/components/FormModal";
import { ToastProvider } from "@/components/Toast";

import { RefusalNotice, refusalOf } from "./settingsShared";
import {
  ServicesTab,
  activeUomOptions,
  billedUomText,
  billingBasisText,
  countText,
  meteringWarningCount,
  savedWarningText,
  serviceSettingsSchema,
  uomWarningCount,
} from "./SettingsServicesTab";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const SERVICES: TenantServiceRow[] = [
  {
    service: "electric",
    name: "Electric",
    enabled: true,
    // BR-RAT-081: the column's own safe default — an electric utility reads a
    // meter, and a service nobody has declared anything about is METERED.
    billing_basis: "metered",
    primary_uom: "kWh",
    alt_uom: "kW",
    // r6.4: null means "the register's own unit is what is billed", which is
    // what every tenant in the product answered before DEF-2311 gave the
    // column a writer.
    billed_uom: null,
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 3,
    active_accounts: 612,
  },
  {
    service: "water",
    name: "Water",
    enabled: true,
    billing_basis: "metered",
    primary_uom: "kgal",
    alt_uom: "ccf",
    // A tenant that reads kgal and bills ccf, with BR-RAT-038's factor stated —
    // the pair the server refuses to store half of.
    billed_uom: "ccf",
    conversion_factor: "0.748052",
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 2,
    active_accounts: 568,
  },
  {
    service: "sewer",
    name: "Sewer",
    // ⚠ THE ROW THAT PROVES TWO STATES WERE NEVER ENOUGH (DEF-2409). Sewer is
    // not metered, and it is not counted either — it is 40% of the water usage
    // charge (BR-RAT-015). Under the boolean, NEITHER value was true for it,
    // and a utility ticking "Unmetered" to stop the run demanding a read was
    // telling the engine to price sewer by counting carts.
    billing_basis: "share",
    enabled: true,
    primary_uom: null,
    alt_uom: null,
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 1,
    active_accounts: 1014,
  },
  {
    service: "trash",
    name: "Trash",
    // BR-RAT-090's per-cart billing — 3 carts × $15.00 = $45.00. Priced from a
    // count, which is what the boolean's `false` side used to mean and is now
    // one named state of three.
    billing_basis: "capacity",
    enabled: true,
    primary_uom: "month",
    alt_uom: null,
    billed_uom: "cart",
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 1,
    active_accounts: 986,
  },
  {
    service: "gas",
    name: "Gas",
    enabled: false,
    // ⚠ NO DECLARATION AT ALL. The server always answers the key today
    // (BR-TEN-1180), so this row is a GUARD, not a picture: it pins that a
    // payload which ever loses the key makes the table say "Not recorded"
    // rather than draw the old safe default, which is DEF-2409's own shape —
    // provisioning never wrote the column and every service read METERED.
    // Drawing it here would be the product asserting something false about
    // how a customer is billed.
    //
    // The row is also OFF, on purpose: the declaration renders for every
    // service on or off, because a setting a tenant cannot SEE is what let
    // this column sit unwritten for eight days (DEF-2310).
    primary_uom: null,
    alt_uom: null,
    billed_uom: "cart",
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 0,
    active_accounts: 0,
  },
];

/**
 * DEF-184: `service` is the UoM list's CR-004 scope column, serialized by
 * `UomLookupHandler.serialize` as `{id, code}` or `null`. `null` is the VALUE
 * "All services", not a missing field — so the helper takes it explicitly and
 * every fixture row states its scope out loud.
 */
function entry(code: string, active: boolean, service: string | null = null): LookupEntry {
  return {
    id: code,
    code,
    name: code,
    active,
    is_system: true,
    used_by: 0,
    service: service === null ? null : { id: service, code: service },
  };
}

function renderTab(rows: TenantServiceRow[], readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.tenantServices, rows);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <ServicesTab readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-007 — enable / disable services per tenant", () => {
  it("US-TEN-007 TC-1/TC-2: each catalog service renders one row with its state and its units", () => {
    const html = renderTab(SERVICES);
    expect(html).toContain("Electric");
    expect(html).toContain("kWh");
    expect(html).toContain("Gas");
    // On/Off state comes from the row, and an Off row offers Enable.
    expect(html).toContain(">On<");
    expect(html).toContain(">Off<");
    // r10 UI-RULES rule 15 turned these two into ICONS. Asserting the
    // ACCESSIBLE NAME rather than the visible text is the point: the words
    // must survive the conversion, or the row actions become unlabelled
    // glyphs for anyone not using a mouse. Text-content assertions would go
    // green on an icon with no name at all.
    expect(html).toContain('aria-label="Enable"');
    expect(html).toContain('aria-label="Disable"');
    // BR-TEN-025: no add/rename/delete affordance exists anywhere on the tab.
    expect(html).not.toContain("+ Add service");
    expect(html).toContain("New service types are added by your platform provider");
  });

  it("US-TEN-007 TC-3 (neg): the disable guard renders the SERVER's counts, never the row's", () => {
    // The screen must not pre-judge from the visible 3 / 612 — the refusal is
    // the server's 409, with the server's freshly counted params.
    const blocked = new ApiError(409, {
      code: "BIZ-STATE",
      message_key: "settings.services.disable_blocked",
      params: { service: "Electric", rate_schedules: 3, active_accounts: 612 },
      br_ref: "BR-TEN-026",
    });
    const refusal = refusalOf(blocked, t);
    expect(refusal.message).toBe(
      // Shortened to the 12-word rule, PO 2026-08-19 (decision log `6baa846`).
      "Electric has 3 rate schedules and 612 active accounts. End or reassign them first.",
    );
    expect(refusal.brRef).toBe("BR-TEN-026");
    const html = renderToStaticMarkup(<RefusalNotice refusal={refusal} />);
    expect(html).toContain("3 rate schedules and 612 active accounts");
    expect(html).toContain('role="alert"');

    // The Disable control is NOT pre-disabled from the counts: the guard is the
    // server's, and a stale count on screen must never block a legal action.
    const page = renderTab(SERVICES);
    expect(page).toContain('aria-label="Disable"');
  });

  it("US-TEN-007 TC-4 (neg): a read-only role gets disabled controls carrying the reason", () => {
    const html = renderTab(SERVICES, true);
    expect(html).toContain("Your role can view this, but not change it.");
    expect(html).toContain("disabled");
  });

  it("BR-TEN-026: a count the owning lane cannot answer renders '—', never a fabricated 0", () => {
    expect(countText(null, "—")).toBe("—");
    expect(countText(0, "—")).toBe("0");
    expect(countText(612, "—")).toBe("612");
    const unwired = renderTab([
      { ...SERVICES[0], rate_schedules: null, active_accounts: null },
    ]);
    expect(unwired).toContain("—");
  });

  it("BR-SHL-032: the enable/disable confirm names the action instead of saying OK", () => {
    expect(t("settings.services.disableAction", { service: "Gas" })).toBe("Turn off Gas");
    expect(t("settings.services.enableAction", { service: "Gas" })).toBe("Turn on Gas");
    expect(t("settings.services.disableAction", { service: "Gas" })).not.toBe("OK");
  });
});

describe("US-TEN-008 — edit UoM per service", () => {
  it("US-TEN-008 TC-1: after a primary-unit change the SERVER's affected-schedule count is what warns", () => {
    const saved: TenantServiceSaved = {
      ...SERVICES[1],
      primary_uom: "ccf",
      warnings: { rate_schedules_in_old_unit: 2 },
    };
    expect(uomWarningCount(saved)).toBe(2);
    expect(t("settings.services.uomWarning", { count: 2 })).toBe(
      "2 rate schedules are still priced in the previous unit. Nothing was converted.",
    );
    // A lane that cannot answer yet returns null — that is NOT "zero affected".
    expect(uomWarningCount({ ...saved, warnings: { rate_schedules_in_old_unit: null } })).toBeNull();
    expect(uomWarningCount({ ...saved, warnings: {} })).toBeNull();
  });

  it("US-TEN-008 TC-4 (neg): a deactivated UoM never appears in the picker for a NEW assignment", () => {
    // All three unscoped ("All services"), so BR-TEN-029 is the only filter
    // this case exercises — the DEF-184 scope cases are the block below.
    const options = activeUomOptions(
      [entry("kgal", true), entry("ccf", true), entry("therm", false)],
      "water",
    );
    expect(options.map((option) => option.value)).toEqual(["kgal", "ccf"]);
    expect(options.map((option) => option.value)).not.toContain("therm");
  });

  // ── DEF-184 · the picker is scoped to the utility service ────────────────
  // The rule is `apps/tenancy/selectors.uom_scope_filter`, quoted VERBATIM:
  //   "a unit is valid for a service when it is scoped to that service or
  //    scoped to none (NULL = 'All services')."
  // These four cases are the SCREEN half of that one expression. The server
  // half (`_apply_service_uom` → `resolve_uom`) already refuses out-of-scope
  // units at the write; a screen that draws the right options is a screen, not
  // a rule, so both halves exist and neither is trusted alone.
  it("DEF-184 (RED first): a WATER service is NOT offered `therm` or `kWh`", () => {
    const options = activeUomOptions(
      [
        entry("kgal", true, "water"),
        entry("ccf", true, null),
        entry("therm", true, "gas"),
        entry("kWh", true, "electric"),
        entry("kW", true, "electric"),
      ],
      "water",
    );
    // The defect the PO reported, stated as an assertion: before the fix this
    // list came back with every active unit, `therm` included.
    expect(options.map((option) => option.value)).toEqual(["kgal", "ccf"]);
    expect(options.map((option) => option.value)).not.toContain("therm");
    expect(options.map((option) => option.value)).not.toContain("kWh");
  });

  it("DEF-184: a unit scoped to NO service is offered to EVERY service", () => {
    const units = [entry("ccf", true, null), entry("month", true, null), entry("kWh", true, "electric")];
    for (const service of ["water", "gas", "electric", "thermal", "battery"]) {
      const offered = activeUomOptions(units, service).map((option) => option.value);
      expect(offered).toContain("ccf");
      expect(offered).toContain("month");
    }
    // …and the scoped one only where it belongs.
    expect(activeUomOptions(units, "electric").map((option) => option.value)).toContain("kWh");
    expect(activeUomOptions(units, "water").map((option) => option.value)).not.toContain("kWh");
  });

  it("DEF-184: the service code matches case-insensitively, as the server does", () => {
    // `uom_scope_filter` uses `service__code__iexact`; a screen that matched
    // case-sensitively would hide a tenant's own units on a casing difference.
    const offered = activeUomOptions([entry("kgal", true, "Water")], "water");
    expect(offered.map((option) => option.value)).toEqual(["kgal"]);
  });

  it("DEF-184: a unit the service ALREADY stores still renders — present but unselectable", () => {
    // A stored value vanishing from its own picker reads as data loss, so it
    // stays. It is `outOfScope`, which the modal renders as a DISABLED option
    // carrying the reason — matching the server, which refuses that unit at
    // the write (`resolve_uom`), so selectable would only teach on submit.
    const options = activeUomOptions(
      [entry("kgal", true, "water"), entry("therm", true, "gas")],
      "water",
      ["therm", null],
    );
    expect(options.map((option) => option.value)).toEqual(["kgal", "therm"]);
    expect(options.find((option) => option.value === "therm")?.outOfScope).toBe(true);
    expect(options.find((option) => option.value === "kgal")?.outOfScope).toBe(false);
  });

  it("DEF-184: keeping a stored unit does NOT re-admit a deactivated one (BR-TEN-029 still wins)", () => {
    const options = activeUomOptions(
      [entry("kgal", true, "water"), entry("therm", false, "gas")],
      "water",
      ["therm"],
    );
    expect(options.map((option) => option.value)).toEqual(["kgal"]);
  });

  it("DEF-184: the out-of-scope reason is spelled out on the option itself", () => {
    expect(t("settings.services.uomOutOfScope", { label: "therm — Therm", service: "Water" })).toBe(
      "therm — Therm (not available for Water — choose another unit)",
    );
  });

  it("US-TEN-008 TC-5 (neg): primary is required and the alternate must differ", () => {
    const schema = serviceSettingsSchema(t);
    expect(collectFormErrors(schema, { primary_uom: "kgal", alt_uom: "ccf" }).count).toBe(0);
    expect(collectFormErrors(schema, { primary_uom: "kgal", alt_uom: "" }).count).toBe(0);

    const missing = collectFormErrors(schema, { primary_uom: "", alt_uom: "ccf" });
    expect(missing.errors.primary_uom).toBe("Pick a primary unit.");

    const same = collectFormErrors(schema, { primary_uom: "kgal", alt_uom: "KGAL" });
    expect(same.errors.alt_uom).toBe("The alternate unit must differ from the primary one.");
  });

  it("BR-TEN-027: the modal states forward-only BEFORE the save, and nothing in this file converts a unit", () => {
    expect(t("settings.services.uomForwardOnly")).toContain(
      "keep the unit they were stored with",
    );
  });

  it.todo(
    "US-TEN-008 TC-2: July reads and invoice lines still show kgal after the change — server-stored units (BR-TEN-027), not a screen behaviour",
  );
  it.todo(
    "US-TEN-008 TC-3: demand-based rate creation offers kW — Plans & Rates screens, a later packet",
  );
  it.todo("US-TEN-007 TC-5 / US-TEN-008 TC-6 (isolation): per-tenant service state — G5 scope");
});

describe("DEF-2310 / DEF-2311 / DEF-2409 — a utility declares how each service is billed", () => {
  it("DEF-2409: all THREE states reach the table, and the column heads the question", () => {
    const html = renderTab(SERVICES);

    // The heading names the QUESTION. "Metering" could not head a cell that
    // says "Capacity", which is how a two-state word survives a three-state
    // rule and quietly makes the column read wrong.
    expect(html).toContain("Billing basis");
    expect(html).not.toContain("Metering");

    // Three words, three services, and the middle one is the whole point of
    // the ruling: sewer could not be said at all before today.
    expect(html).toContain("Metered");
    expect(html).toContain("% of another service");
    expect(html).toContain("Capacity");
    expect(html).not.toContain("Unmetered");

    // Gas is OFF and its basis is on screen all the same. A declaration only
    // reachable through a modal that the row's own state disables is a
    // setting a tenant cannot check.
    expect(html).toContain("Gas");
    // The billed unit too — DEF-2311's column.
    expect(html).toContain("Billed unit");
    expect(html).toContain("ccf");
  });

  it("DEF-2409: a service the server has not declared reads 'Not recorded', never 'Metered'", () => {
    // THE DEFECT ITSELF. `metered` defaulted to true and provisioning never
    // wrote it, so all ten services on every tenant read METERED — Solar,
    // Battery, Storm water and Sewer included — and the screen rendered it
    // faithfully. An absent answer is now said to be absent.
    expect(billingBasisText(undefined, t)).toBe("Not recorded");
    expect(billingBasisText(undefined, t)).not.toBe("Metered");
    // …and it is NOT the "—" the unwired counts use: that glyph means "no
    // count yet" and this is a sentence about a declaration.
    expect(billingBasisText(undefined, t)).not.toBe("—");

    expect(billingBasisText("metered", t)).toBe("Metered");
    expect(billingBasisText("share", t)).toBe("% of another service");
    expect(billingBasisText("capacity", t)).toBe("Capacity");

    // B14 rule 32: the wire value never reaches a clerk.
    expect(billingBasisText("share", t)).not.toBe("share");
    expect(billingBasisText("capacity", t)).not.toBe("capacity");
  });

  it("DEF-2409: the row with no declaration renders the words, not a blank cell", () => {
    const html = renderTab(SERVICES);
    expect(html).toContain("Not recorded");
  });

  it("DEF-2409: the modal offers three options and never a boolean", () => {
    // The three labels a clerk chooses between. Asserting the catalogue rather
    // than the rendered modal because the modal opens on state this suite does
    // not set (the file's own E-note (c)); the WIRE half is proved by the
    // write test below, which is the half law 2 is about.
    expect(t("settings.services.meteredOption")).toBe("Metered — a meter is read");
    expect(t("settings.services.shareOption")).toBe(
      "% of another service — a share of its charge",
    );
    expect(t("settings.services.capacityOption")).toBe("Capacity — priced by size or count");
    expect(t("settings.services.billingBasisLabel")).toBe("How this service is billed");
    // The refusal the server sends when the value is not one of the three.
    expect(t("settings.services.billing_basis_invalid")).toBe(
      "Choose how this service is billed.",
    );
  });

  it("DEF-2311: a null billed unit says what it MEANS, not '—'", () => {
    // `service_billed_uoms()` states the reading in terms: null is "the
    // register's own unit is what is billed". The "—" the unwired COUNTS use
    // would be telling a clerk two different things with one glyph.
    expect(billedUomText(SERVICES[0], t)).toBe("Same as the primary unit");
    expect(billedUomText(SERVICES[1], t)).toBe("ccf");
  });

  it("BR-RAT-038: a metered service billed in another unit must state a factor", () => {
    const schema = serviceSettingsSchema(t);
    const clean = collectFormErrors(schema, {
      primary_uom: "kgal",
      alt_uom: "",
      billed_uom: "ccf",
      conversion_factor: "0.748052",
      billing_basis: "metered",
    });
    expect(clean.count).toBe(0);

    const missing = collectFormErrors(schema, {
      primary_uom: "kgal",
      alt_uom: "",
      billed_uom: "ccf",
      conversion_factor: "",
      billing_basis: "metered",
    });
    expect(missing.errors.conversion_factor).toBe(
      "ccf differs from kgal. Add a conversion factor.",
    );

    // The same unit twice needs nothing — there is nothing to convert.
    expect(
      collectFormErrors(schema, {
        primary_uom: "kgal",
        alt_uom: "",
        billed_uom: "kgal",
        conversion_factor: "",
        billing_basis: "metered",
      }).count,
    ).toBe(0);
  });

  it("BR-MET-710: a CAPACITY service is asked for no factor — month to cart converts by nothing", () => {
    // The trap DEF-1813 hit from the other side and recorded: gating the cart
    // count on a declared billed unit would have refused the one declaration
    // BR-RAT-081 exists for.
    const schema = serviceSettingsSchema(t);
    expect(
      collectFormErrors(schema, {
        primary_uom: "month",
        alt_uom: "",
        billed_uom: "cart",
        conversion_factor: "",
        billing_basis: "capacity",
      }).count,
    ).toBe(0);
    // …and a SHARE service owes none either: it reads no register, so there
    // are never two units to reconcile (DEF-2409 — this is the state sewer
    // always needed and the boolean could not express).
    expect(
      collectFormErrors(schema, {
        primary_uom: "month",
        alt_uom: "",
        billed_uom: "cart",
        conversion_factor: "",
        billing_basis: "share",
      }).count,
    ).toBe(0);
    // …and the guard is not simply absent — flip the declaration back.
    expect(
      collectFormErrors(schema, {
        primary_uom: "month",
        alt_uom: "",
        billed_uom: "cart",
        conversion_factor: "",
        billing_basis: "metered",
      }).errors.conversion_factor,
    ).toBe("cart differs from month. Add a conversion factor.");
  });

  it("CLAUDE.md rule 2: a conversion factor is a positive decimal typed as TEXT", () => {
    const schema = serviceSettingsSchema(t);
    const bad = (factor: string) =>
      collectFormErrors(schema, {
        primary_uom: "kgal",
        alt_uom: "",
        billed_uom: "ccf",
        conversion_factor: factor,
        billing_basis: "metered",
      }).errors.conversion_factor;

    expect(bad("nope")).toBe("Enter the conversion factor as a number, like 0.748052.");
    expect(bad("0")).toBe("Enter the conversion factor as a number, like 0.748052.");
    expect(bad("-1")).toBe("Enter the conversion factor as a number, like 0.748052.");
    expect(bad("1e-3")).toBe("Enter the conversion factor as a number, like 0.748052.");
    expect(bad("0.748052")).toBeUndefined();
  });

  it("BR-TEN-810: the save names how many accounts' NEXT bill moves, and the money sentence wins", () => {
    const base: TenantServiceSaved = { ...SERVICES[1], warnings: {} };

    expect(meteringWarningCount({ ...base, warnings: { accounts_on_next_bill: 4 } })).toBe(4);
    // A lane that cannot answer returns null — that is NOT "no accounts".
    expect(meteringWarningCount({ ...base, warnings: { accounts_on_next_bill: null } })).toBeNull();
    expect(meteringWarningCount(base)).toBeNull();

    expect(
      savedWarningText({ ...base, warnings: { accounts_on_next_bill: 4 } }, t),
    ).toBe("4 accounts take Water. Their next bill uses the new setting.");

    // Both at once: the MONEY sentence is the one shown, because it is the one
    // a person cannot undo by editing a schedule.
    expect(
      savedWarningText(
        { ...base, warnings: { accounts_on_next_bill: 4, rate_schedules_in_old_unit: 2 } },
        t,
      ),
    ).toContain("next bill");

    // Zero shows nothing: a banner that appears for a non-event teaches people
    // to ignore the banner.
    expect(savedWarningText({ ...base, warnings: { accounts_on_next_bill: 0 } }, t)).toBeNull();
    expect(savedWarningText(base, t)).toBeNull();
  });

  it("B14 rule 11: the modal states the consequence BEFORE the commit, and it is forward-only", () => {
    expect(t("settings.services.meteringConsequence")).toBe(
      "Bills already issued keep what they charged. The next bill uses this setting.",
    );
  });

  it.todo(
    "DEF-2310 end to end in a browser: declare trash unmetered on S8, then bill three carts at $45.00 — proved server-side in 06-backend/tests/test_def_2310_service_declaration.py::tc8",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-007@53479d6 (story+rules snapshot hash — EP-TEN-06; co-story US-TEN-008@53479d6)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
