// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-007 · US-TEN-008 (EP-TEN-06 §Stories)  Screens: S8 (Settings → Services & UoM)
// Rules:    BR-TEN-025 (service TYPES are the closed platform catalog — toggle only, no add/rename/delete) ·
//           BR-TEN-026 (Enable creates/reactivates; Disable is GUARDED — blocked with the reference counts
//           named while rate schedules or active accounts exist) · BR-TEN-027 (UoM is forward-only; existing
//           reads and invoice lines keep their stored unit, a warning NAMES affected schedules) ·
//           BR-TEN-029 (deactivated UoM entries are excluded from NEW pickers) · DEF-184 (the UoM pickers
//           are scoped to the utility service — `selectors.uom_scope_filter`: scoped to THIS service, plus
//           everything scoped to none) · BR-TEN-024 (confirm + atomic
//           save) · BR-TEN-016 (audit `settings.service.enabled/disabled` · `settings.service_uom.updated` ·
//           `settings.service_metering.updated`) · BR-SHL-032 (the confirm names the action) ·
//           BR-SHL-025 (a non-admin sees disabled-with-reason) · BR-RAT-081 (a service DECLARES how it is
//           BILLED, and it is one of THREE — PO 2026-09-02, "we will have 3 states - meter unmetered and
//           % oaf service" / "Shall we consider Metered, % of service and Capacity based"; DEF-2409,
//           superseding the two-state form of PO 2026-08-20 "yes we have to say service is meter or
//           unmetered"; DEF-2310) ·
//           BR-RAT-038 (register unit vs BILLED unit, or a stated conversion factor; DEF-2311) ·
//           BR-TEN-810 (the declaration is forward-only — nothing already issued moves) ·
//           B14 rule 11 (a form writing service state names what it will do before the commit)
// ───────────────────────────────────────────────────────
// S8 → Services & UoM: one row per platform service, in the server's catalog
// order. Tenants toggle availability and set units; nobody adds a service type
// here, because BR-TEN-025 makes that a provider migration.
//
// The disable guard is the point of this screen. This file NEVER decides
// whether a service can be turned off — it asks, and when the server answers
// 409 BIZ-STATE `settings.services.disable_blocked` it renders that envelope,
// counts and all (US-TEN-007 TC-3). Predicting the block from the row's own
// count columns would be a second, drifting copy of the rule; worse, those
// counts are null while a neighbour lane is unwired, and a null is NOT a zero.
//
// ⚠ THE MEASUREMENT DECLARATION (DEF-2310 · DEF-2311, 2026-08-28). This screen
// is where a utility says a service is NOT METERED — BR-RAT-081, ruled
// 2026-08-20, and until this commit nothing anywhere in the product wrote the
// column. A refuse utility could not tell us it does not meter trash, so
// BR-RAT-090's per-cart billing (3 carts x $15.00 = $45.00) was reachable only
// by editing a database row by hand. The same modal states the BILLED unit and
// its conversion factor, which had a reader in metering, assets and rating and
// no writer at all.
//
// ⚠⚠ AND THE CHOICE THAT DECLARATION OFFERED WAS TOO SMALL BY ONE (DEF-2409,
// PO 2026-09-02): *"this says, metered or unmeters, but we agreed, we will have
// 3 states - meter unmetered and % oaf service"*, then *"Shall we consider
// Metered, % of service and Capacity based"*. So the control is THREE options
// and the column prints one of three words.
//
// **SEWER IS THE PROOF THAT TWO WERE NOT ENOUGH, AND IT IS A MONEY PATH.** The
// old control was a boolean whose `false` side meant *priced from a COUNT*.
// Sewer is not metered, and it is not counted either — it is 40% of the water
// usage charge (BR-RAT-015). A utility that ticked "Unmetered" to stop the bill
// run demanding a read was telling the engine to price sewer by counting carts.
// Neither value was true for it, which is why this is a widening rather than a
// relabel: the third state is the one sewer always needed.
//
// The wire values are `metered` · `share` · `capacity` and **none of them is
// ever shown** — B14 rule 32 keeps internal codes off clerk-facing copy, so
// `billingBasisText` is the one place the three map to the three words a person
// reads.
//
// It is ONE modal and one save, not a second control beside the units, because
// the three facts are one answer to one question — how is this service
// measured, and in what unit is it billed — and two write paths for one fact is
// how two screens come to disagree about what a tenant declared.
//
// The declaration is rendered in the TABLE for every service, on or off. A
// setting a tenant cannot SEE is what let `metered` sit unwritten for eight
// days; the modal is where it is changed, the column is where it is read.
//
// UoM edits carry the same discipline: the modal offers only ACTIVE UoM entries
// (BR-TEN-029) that are VALID FOR THIS UTILITY SERVICE (DEF-184 — a water
// service is not offered `therm`; see `activeUomOptions`) and, after a save that
// changed the primary unit, renders the server's
// `warnings.rate_schedules_in_old_unit` verbatim (BR-TEN-027). Nothing is
// converted anywhere in this file — historical units are never rewritten.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { getLookupEntries, getTenantServices, updateTenantService } from "@/api/endpoints";
import type {
  BillingBasis,
  LookupEntry,
  TenantServiceChanges,
  TenantServiceRow,
  TenantServiceSaved,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FormModal, SegmentedField, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PencilIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { Kicker, Note } from "@/components/TextBits";

import {
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * BR-TEN-026: counts arrive through the owning-module seams and are `null`
 * while that lane is unwired. A null renders "—" — writing 0 would claim the
 * service has no schedules, which is a different (and possibly false) statement.
 */
export function countText(value: number | null, dash: string): string {
  return value === null ? dash : String(value);
}

/**
 * The S8 service-settings form: primary is required, the alternate must differ
 * (US-TEN-008 TC-5), and BR-RAT-038's billed-unit pair holds together.
 *
 * ⚠ THE FOUR NEW FIELDS ARE OPTIONAL IN THE SHAPE AND THAT IS NOT LAXITY. This
 * validates what a FORM holds, and the units half of it predates the
 * measurement half by nineteen days; making `billed_uom` required here would
 * refuse a payload the server accepts. What must hold, holds — see the pair
 * rule below.
 *
 * **BR-RAT-038 ON THE CLIENT IS THE SECOND COPY OF ONE RULE, deliberately** —
 * `apps/tenancy/services._apply_service_uom` is the law (a script or a replayed
 * request never opens this modal) and this exists only so a clerk is not taught
 * it on submit. Change one, change both. Both are qualified the same way: the
 * pair is required only for a METERED service, because a `share` or `capacity`
 * one has no register and therefore no two units to reconcile (BR-MET-710 — the
 * quantity crosses the billing seam unitless).
 *
 * ⚠ **AN UNSTATED BASIS IS TREATED AS METERED *HERE AND NOWHERE ELSE*, AND THE
 * ASYMMETRY IS THE POINT.** Nothing DISPLAYS a guessed basis — the column says
 * "Not recorded" (DEF-2409: a confident wrong word is the defect). But refusing
 * a mismatched unit pair is recoverable in one edit, while accepting one writes
 * a conversion nobody stated, so this one check keeps the strict side while the
 * server has not yet shipped the field. It is exactly what the boolean did
 * before (`metered ?? true`), so no save that worked yesterday is refused now.
 */
export function serviceSettingsSchema(t: Translator) {
  return z
    .object({
      primary_uom: z.string(),
      alt_uom: z.string(),
      billed_uom: z.string().optional(),
      conversion_factor: z.string().optional(),
      billing_basis: z.string().optional(),
    })
    .superRefine((values, ctx) => {
      // BR-TEN-1181 (DEF-3232): a share service has no unit of its own, so it
      // owes none — and the modal hides all four unit fields for it, which is
      // why every check below is skipped rather than only the first. Validating
      // a field a clerk cannot see is a refusal with nothing to do about it.
      if ((values.billing_basis ?? "") === "share") {
        return;
      }
      if (values.primary_uom.trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["primary_uom"],
          message: t("settings.services.primaryRequired"),
        });
      }
      if (
        values.alt_uom !== "" &&
        values.alt_uom.toLowerCase() === values.primary_uom.toLowerCase()
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["alt_uom"],
          message: t("settings.services.altEqualsPrimary"),
        });
      }
      const factor = (values.conversion_factor ?? "").trim();
      if (factor !== "" && !POSITIVE_DECIMAL.test(factor)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["conversion_factor"],
          message: t("settings.services.factorFormat"),
        });
        return;
      }
      const billed = (values.billed_uom ?? "").trim();
      const stated = values.billing_basis ?? "";
      const metered = stated === "" || stated === "metered";
      if (
        metered &&
        billed !== "" &&
        billed.toLowerCase() !== values.primary_uom.trim().toLowerCase() &&
        factor === ""
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["conversion_factor"],
          message: t("settings.services.factorRequired", {
            billed_uom: billed,
            primary_uom: values.primary_uom,
          }),
        });
      }
    });
}

/**
 * A conversion factor is a positive decimal typed as TEXT — never a JS number.
 * CLAUDE.md rule 2 keeps binary floating point off every path a stored figure
 * travels, and `0.1 + 0.2` is the reason. A leading `+`/`-`, an exponent and a
 * bare `.` are all refused: none of them is a factor a utility means to type.
 */
const POSITIVE_DECIMAL = /^(?!0+(\.0+)?$)\d+(\.\d{1,6})?$/;

/**
 * One unit offered by the SET-03 UoM pickers.
 *
 * `outOfScope` is the REASON, not the effect: it is true only for a unit that
 * this service is already storing but may not newly pick. The modal turns it
 * into the effect — a disabled `<option>` whose label says why.
 */
export interface UomOption {
  value: string;
  label: string;
  outOfScope: boolean;
}

/**
 * The units this service's pickers may offer (BR-TEN-029 · DEF-184).
 *
 * TWO filters, applied in this order, and the order matters:
 *
 *  1. **BR-TEN-029** — a deactivated entry never appears in a NEW-record
 *     picker. Nothing below re-admits one.
 *  2. **DEF-184 / CR-004 task A3** — the utility-service scope. The server's
 *     rule is `apps/tenancy/selectors.uom_scope_filter`, quoted verbatim:
 *     *"a unit is valid for a service when it is scoped to that service or
 *     scoped to none (NULL = 'All services')."* This function is that same
 *     sentence on the screen, so the picker cannot offer what the write would
 *     refuse. It is a SECOND copy of one rule, and deliberately so: the server
 *     copy in `_apply_service_uom.resolve_uom` is the law (a script or a
 *     replayed request never opens this modal), and this one exists only so a
 *     clerk is not taught it on submit. Change one, change both.
 *     Matching is case-insensitive because the server matches `iexact`.
 *
 * `alreadySaved` is the escape hatch and it is narrow. A unit this service is
 * ALREADY assigned stays in its own picker even when out of scope — a stored
 * value vanishing from the control that shows it reads as data loss, and the
 * user would have no way to see what the service is set to. It comes back
 * flagged `outOfScope`, never silently mixed in with the legal units, which is
 * FieldOption's documented doctrine: *"Present and unselectable beats absent
 * (the user would never learn it exists) and beats selectable (they would only
 * learn on submit)."* Selectable is the wrong answer here for a concrete
 * reason — `resolve_uom` re-resolves BOTH units through the scope filter on
 * every save, so re-picking one would earn a server refusal.
 *
 * Pure: no hooks, no `t`, no DOM. The out-of-scope wording is applied by the
 * caller so this stays testable without a browser or an i18n bundle.
 *
 * ⚠ **A SECOND, NARROWER RULE NOW SITS ON TOP OF THIS ONE AND IT IS NOT IN
 * HERE — `CR-130-BRC07` §8.3, 2026-09-22.** `rating/ratingShared.scheduleUomOptions`
 * CALLS this function and then narrows its answer again, to the unit THIS
 * TENANT declared for THIS SERVICE (`tenant_services.billed_uom`, else
 * `primary_uom`), leaving the rest present and unselectable. **It was layered
 * rather than folded in, deliberately, and *"Change one, change both"* above
 * is exactly why:** that sentence is a promise about `selectors.uom_scope_filter`,
 * and a screen-only narrowing folded in here would make this function stop
 * mirroring the server — the picker would refuse units the write path accepts,
 * and the next person reading either side would have no way to tell which
 * clause belonged to whom. **This function is still the scope rule and nothing
 * else.** The narrowing is the rate wizard's alone; S8's own modal, below, is
 * where a utility STATES the declaration, so narrowing that picker by it would
 * be circular.
 */
export function activeUomOptions(
  entries: readonly LookupEntry[],
  serviceCode: string,
  alreadySaved: readonly (string | null | undefined)[] = [],
): UomOption[] {
  const service = serviceCode.trim().toLowerCase();
  const saved = new Set(
    alreadySaved
      .filter((code): code is string => typeof code === "string" && code.trim() !== "")
      .map((code) => code.toLowerCase()),
  );
  const options: UomOption[] = [];
  for (const entry of entries) {
    if (!entry.active) {
      continue; // BR-TEN-029 first — and it is never overridden below.
    }
    // ABSENT `service` is not the same statement as `null`: a list that
    // publishes no scope column is unscoped, which reads the same way here as
    // "All services". Both mean every service may use it.
    const scope = entry.service ?? null;
    const inScope = scope === null || scope.code.trim().toLowerCase() === service;
    if (!inScope && !saved.has(entry.code.toLowerCase())) {
      continue;
    }
    options.push({
      value: entry.code,
      label: `${entry.code} — ${entry.name}`,
      outOfScope: !inScope,
    });
  }
  return options;
}

/**
 * BR-TEN-027: the forward-only warning. `null`/absent means the rating lane
 * cannot answer yet (not "zero schedules"), so no warning is claimed.
 */
export function uomWarningCount(saved: TenantServiceSaved): number | null {
  const value = saved.warnings.rate_schedules_in_old_unit;
  return typeof value === "number" ? value : null;
}

/**
 * BR-TEN-810: the measurement declaration is FORWARD-ONLY, and this is the
 * count the server sends back when it CHANGED — how many accounts take the
 * service, and therefore how many next bills obtain their quantity a different
 * way. Nothing already issued moves (CLAUDE.md hard rule 4).
 *
 * `null`/absent for the same reason as the sibling above and it is the same
 * distinction: the customers lane may be unwired, and a null is *we cannot say*
 * — never *no accounts*. An unchanged declaration sends no key at all.
 */
export function meteringWarningCount(saved: TenantServiceSaved): number | null {
  const value = saved.warnings.accounts_on_next_bill;
  return typeof value === "number" ? value : null;
}

/**
 * What the table prints in the Billing basis column — BR-RAT-081 as re-ruled on
 * 2026-09-02, on every row whether the service is on or off.
 *
 * ⚠ **THIS FUNCTION USED TO HAVE NO FOURTH BRANCH AND SAID SO IN CAPITALS.**
 * The boolean it read was always answered, so *"a service nobody has declared
 * anything about is METERED"* was a safe default. DEF-2409 is what that default
 * cost: provisioning never wrote the column, so all ten services on every
 * tenant read METERED — Solar, Battery, Storm water and Sewer included — and
 * the screen rendered it faithfully, which is why it looked like a display bug
 * and was not.
 *
 * So an absent basis now draws **"Not recorded"**, and that is the whole reason
 * the branch exists: it is the difference between the product not knowing and
 * the product asserting something false about how a customer is billed. It is
 * NOT the "—" the unwired counts use, because a dash beside a number reads as
 * *no count yet* and this is a sentence about a declaration.
 */
export function billingBasisText(basis: BillingBasis | undefined, t: Translator): string {
  if (basis === "metered") {
    return t("settings.services.metered");
  }
  if (basis === "share") {
    return t("settings.services.share");
  }
  if (basis === "capacity") {
    return t("settings.services.capacity");
  }
  return t("settings.services.basisNotRecorded");
}

/**
 * What the table prints in the Billed unit column.
 *
 * `null` is NOT missing data — `service_billed_uoms()` states its meaning in
 * terms: *"the register's own unit is what is billed"*. So it renders that
 * sentence, never the "—" the unwired COUNTS use, because the two would be
 * telling a clerk two different things with one glyph.
 */
export function billedUomText(row: TenantServiceRow, t: Translator): string {
  return row.billed_uom ?? t("settings.services.billedUomSame");
}

/**
 * The one sentence a save leaves on the screen, or `null` for none.
 *
 * TWO WARNINGS, ONE SLOT, AND THE ORDER IS THE RULE. BR-TEN-027's
 * affected-schedule count is about work a person may have to REDO; BR-TEN-810's
 * account count is about money the NEXT bill obtains a different way. When one
 * save carries both — a clerk who changes the primary unit and the declaration
 * together — the money sentence is the one shown, because it is the one whose
 * consequence a person cannot undo by editing a schedule.
 *
 * A count of ZERO shows nothing, deliberately: *"0 accounts take Trash"* is a
 * true sentence that warns about nothing, and a warning banner that appears for
 * a non-event teaches people to ignore the banner.
 */
export function savedWarningText(saved: TenantServiceSaved, t: Translator): string | null {
  const accounts = meteringWarningCount(saved);
  if (accounts !== null && accounts > 0) {
    return t("settings.services.meteringWarning", {
      count: accounts,
      service: saved.name,
    });
  }
  const schedules = uomWarningCount(saved);
  if (schedules !== null && schedules > 0) {
    return t("settings.services.uomWarning", { count: schedules });
  }
  return null;
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface ServicesTabProps {
  readOnly: boolean;
  client?: ApiClient;
}

type PendingToggle = { service: TenantServiceRow; enable: boolean } | null;

export function ServicesTab(props: ServicesTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();

  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
  });

  const [toggle, setToggle] = useState<PendingToggle>(null);
  const [uomFor, setUomFor] = useState<TenantServiceRow | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const mutate = useMutation({
    mutationFn: (input: { service: string; changes: TenantServiceChanges }) =>
      updateTenantService(input.service, input.changes, client),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tenantServices });
      void queryClient.invalidateQueries({ queryKey: queryKeys.checklist });
    },
  });

  function runToggle(): void {
    if (toggle === null) {
      return;
    }
    const { service, enable } = toggle;
    setRefusal(null);
    mutate.mutate(
      { service: service.service, changes: { enabled: enable } },
      {
        onSuccess: () => {
          setToggle(null);
          fireToast(
            t(enable ? "settings.services.enabled" : "settings.services.disabled", {
              service: service.name,
            }),
          );
        },
        onError: (error: unknown) => {
          // BR-TEN-026: the counts in this line are the SERVER's, out of the
          // 409 envelope params — never recomputed from the row on screen.
          setToggle(null);
          setRefusal(refusalOf(error, t));
        },
      },
    );
  }

  if (servicesQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  if (servicesQuery.data === undefined) {
    if (isPermissionDenied(servicesQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.services.failedTitle")}
        reason={apiErrorText(servicesQuery.error, t)}
        onRetry={() => void servicesQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void servicesQuery.refetch()}
      />
    );
  }

  const rows = servicesQuery.data;
  const dash = t("settings.unwiredCount");

  return (
    <div className="settings-tab">
      <Kicker>{t("settings.services.kicker")}</Kicker>
      {/* BR-TEN-025 stated where the user would otherwise look for "+ Add". */}
      <p className="settings-lede">{t("settings.services.lede")}</p>

      <RefusalNotice refusal={refusal} />
      {warning !== null && (
        <p className="settings-warning" role="status">
          {warning}
        </p>
      )}

      {/* B9 row for S8 · Services & UoM declares NO table capabilities (6 fixed
          rows, no chooser, no pager) — a plain semantic table renders exactly
          what the matrix allows. */}
      <table className="settings-table">
        <thead>
          <tr>
            <th>{t("settings.services.col.service")}</th>
            <th>{t("settings.services.col.status")}</th>
            {/* BR-RAT-081 on the ROW, for every service on or off: the
                declaration a utility could not make until DEF-2310, in the one
                place a clerk looks to check what the product believes. Three
                words since DEF-2409, and the heading names the QUESTION rather
                than one of its answers — a column called "Metering" cannot head
                a cell that says "Capacity". */}
            <th>{t("settings.services.col.billingBasis")}</th>
            <th>{t("settings.services.col.primaryUom")}</th>
            <th>{t("settings.services.col.altUom")}</th>
            <th>{t("settings.services.col.billedUom")}</th>
            <th className="cell-num">{t("settings.services.col.rateSchedules")}</th>
            <th className="cell-num">{t("settings.services.col.accounts")}</th>
            <th>{t("settings.services.col.action")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.service} className={row.enabled ? undefined : "settings-row-off"}>
              <td>{row.name}</td>
              <td>
                <StatusPill tone={row.enabled ? "success" : "neutral"}>
                  {t(row.enabled ? "settings.services.on" : "settings.services.off")}
                </StatusPill>
              </td>
              <td>{billingBasisText(row.billing_basis, t)}</td>
              <td>{row.primary_uom ?? dash}</td>
              <td>{row.alt_uom ?? dash}</td>
              <td>{billedUomText(row, t)}</td>
              <td className="cell-num">{countText(row.rate_schedules, dash)}</td>
              <td className="cell-num">{countText(row.active_accounts, dash)}</td>
              <td>
                {/* r10 UI-RULES rule 15: "Row actions: Icons with tooltips,
                    never text links." These were two text buttons. The label
                    each one used to render is now its `title` AND its
                    `aria-label`, so nothing is lost to a screen reader or to a
                    hover — the words moved, they did not disappear. That
                    matters most for the DISABLED case, where the tooltip is
                    the only thing that says why (BR-SHL-025: a control this
                    deployment cannot honour renders with its reason). */}
                <RowActions>
                  {/* ⚠ THE TOGGLE'S "ICON" IS A RING, NOT AN SVG, and that is
                      r10's own drawing: an on/off control that FILLS when the
                      service is on. It goes through `RowAction` like every
                      other row action so the box, the disabled behaviour and
                      the accessible name come from one place — the glyph is
                      just a different shape. */}
                  <RowAction
                    label={t(row.enabled ? "settings.services.disable" : "settings.services.enable")}
                    icon={
                      <span
                        className={row.enabled ? "settings-toggle is-on" : "settings-toggle"}
                        aria-hidden="true"
                      />
                    }
                    reason={props.readOnly ? t("settings.readOnlyReason") : null}
                    onClick={() => setToggle({ service: row, enable: !row.enabled })}
                  />
                  <RowAction
                    label={t("settings.services.editService")}
                    icon={<PencilIcon />}
                    // BR-TEN-026: the units and the BR-RAT-081 declaration both
                    // live on the tenant_services row, which only exists once
                    // the service is on — the server refuses otherwise, so the
                    // control says why up front.
                    reason={
                      props.readOnly
                        ? t("settings.readOnlyReason")
                        : !row.enabled
                          ? t("settings.services.enableFirst")
                          : null
                    }
                    onClick={() => setUomFor(row)}
                  />
                </RowActions>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {toggle !== null && (
        // BR-SHL-032: the confirm button names the action, never "OK".
        <ConfirmDialog
          // B14 rule 6 (DEF-718): disabling a service is a deactivation; ENABLING one is not destructive at
          // all, so the same dialog wears each tier by what it is about to do.
          confirmVariant={toggle.enable ? "primary" : "danger"}
          title={t(
            toggle.enable ? "settings.services.enableTitle" : "settings.services.disableTitle",
            { service: toggle.service.name },
          )}
          consequence={t(
            toggle.enable ? "settings.services.enableBody" : "settings.services.disableBody",
            { service: toggle.service.name },
          )}
          confirmLabel={t(
            toggle.enable ? "settings.services.enableAction" : "settings.services.disableAction",
            { service: toggle.service.name },
          )}
          working={mutate.isPending}
          onConfirm={runToggle}
          onCancel={() => setToggle(null)}
        />
      )}

      {uomFor !== null && (
        <EditServiceModal
          service={uomFor}
          client={client}
          onClose={() => setUomFor(null)}
          onSaved={(saved) => {
            setUomFor(null);
            void queryClient.invalidateQueries({ queryKey: queryKeys.tenantServices });
            setWarning(savedWarningText(saved, t));
            fireToast(t("settings.services.settingsSaved", { service: saved.name }));
          }}
        />
      )}
    </div>
  );
}

// ── The S8 service-settings modal (US-TEN-008 + DEF-2310 / DEF-2311) ───────

function EditServiceModal(props: {
  service: TenantServiceRow;
  client: ApiClient;
  onClose: () => void;
  onSaved: (saved: TenantServiceSaved) => void;
}) {
  const { t } = useTranslation();
  // "" is NOT a fourth basis — it is "this utility has not said", which is what
  // the control shows when the server sends no declaration. It is never sent.
  const [basis, setBasis] = useState<BillingBasis | "">(props.service.billing_basis ?? "");
  const [primary, setPrimary] = useState(props.service.primary_uom ?? "");
  const [alt, setAlt] = useState(props.service.alt_uom ?? "");
  const [billed, setBilled] = useState(props.service.billed_uom ?? "");
  const [factor, setFactor] = useState(props.service.conversion_factor ?? "");

  // The UoM vocabulary is the tenant's Reference-data list (EP-TEN-07); this
  // modal only SELECTS from it — it never creates a unit.
  const uomQuery = useQuery({
    queryKey: queryKeys.lookupEntries("uoms", "", 1, 1000),
    queryFn: () => getLookupEntries("uoms", { per: 1000 }, props.client),
    staleTime: REFERENCE_STALE_MS,
  });
  // DEF-184: the whole list is fetched (it is one small tenant-owned list) and
  // scoped HERE, from the `service` each row already carries — there is no
  // per-service endpoint and none is needed. The three units this service has
  // stored are passed in so none can vanish from its own control.
  const options = activeUomOptions(uomQuery.data?.results ?? [], props.service.service, [
    props.service.primary_uom,
    props.service.alt_uom,
    props.service.billed_uom,
  ]).map((option) => ({
    value: option.value,
    // The option's own label carries the reason (FieldOption's contract), so
    // the "why" travels with the value into whichever picker shows it.
    label: option.outOfScope
      ? t("settings.services.uomOutOfScope", { label: option.label, service: props.service.name })
      : option.label,
    disabled: option.outOfScope,
  }));

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      // EVERY FIELD IS SENT, INCLUDING THE UNCHANGED ONES AND INCLUDING THE
      // EMPTY ONES AS `null`. Omitting a field leaves it alone on the server,
      // so a modal that sent only what it thought had changed could switch a
      // billed unit ON and never off again — the same trap DEF-515's fix
      // records one screen over ("a blank factor posts null WITH THE KEY
      // PRESENT"). This form holds the whole answer, so it sends the whole
      // answer.
      const changes: TenantServiceChanges = {
        // ⚠ THE ONE FIELD THAT IS OMITTED WHEN EMPTY, AND THE PARAGRAPH ABOVE
        // IS WHY THE OTHERS ARE NOT. A blank unit is a real answer ("bill in
        // the register's own unit") and must be sent as `null` or it can never
        // be cleared. A blank BASIS is not an answer at all — every value of
        // this field is a positive statement a utility makes about itself, so
        // there is nothing to clear, and sending one the clerk did not pick
        // would be resolving DEF-2409 by guessing.
        ...(basis === "" ? {} : { billing_basis: basis }),
        // BR-TEN-1181 (DEF-3232): a share service is priced as a percentage of
        // another service's charge — no register, no count, no unit of its own —
        // so all four unit fields go as `null`. Sending the values still sitting
        // in state would post units the server refuses, from fields this form
        // does not show, and a tenant provisioned before the ruling would keep
        // the stale unit migration `tenancy 0031` deliberately left alone.
        ...(basis === "share"
          ? { primary_uom: null, alt_uom: null, billed_uom: null, conversion_factor: null }
          : {
              primary_uom: primary,
              alt_uom: alt === "" ? null : alt,
              billed_uom: billed === "" ? null : billed,
              conversion_factor: factor.trim() === "" ? null : factor.trim(),
            }),
      };
      const saved = await updateTenantService(props.service.service, changes, props.client);
      props.onSaved(saved);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("settings.services.settingsTitle", { service: props.service.name })}
      kicker={t("settings.services.kicker")}
      schema={serviceSettingsSchema(t)}
      values={{
        primary_uom: primary,
        alt_uom: alt,
        billed_uom: billed,
        conversion_factor: factor,
        billing_basis: basis,
      }}
      submitLabel={t("settings.services.settingsSave")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* BR-RAT-081, first, because it decides how the rest of this form reads:
          only a metered service has a register, so only a metered service owes
          the billed-unit pair below.

          THREE options since DEF-2409, and a radio group rather than a
          checkbox was already the right shape for the reason that now matters
          most — these are statements a utility makes about itself, and there
          was never a two-valued question here to tick. The `value` is a wire
          code and the LABEL is the only thing a clerk reads (B14 rule 32).

          `""` selects none of the three, which is what an undeclared service
          honestly looks like. Nothing is preselected on its behalf. */}
      <SegmentedField
        id="billing_basis"
        label={t("settings.services.billingBasisLabel")}
        value={basis}
        onChange={(value) => setBasis(value as BillingBasis)}
        options={[
          { value: "metered", label: t("settings.services.meteredOption") },
          { value: "share", label: t("settings.services.shareOption") },
          { value: "capacity", label: t("settings.services.capacityOption") },
        ]}
      />
      {/* BR-TEN-1181 (DEF-3232) — THE FOUR UNIT FIELDS ARE NOT SHOWN FOR A
          SHARE SERVICE, because it has no unit to state. Sewer is 40% of the
          water usage charge: it reads no register, counts nothing, and there is
          no quantity for a unit to measure.

          HIDDEN RATHER THAN DISABLED, and rather than shown with a sentence
          explaining itself. B14 rule 33 puts RATIONALE at zero words on screen
          and rule 32 gives the screen a description budget; the basis control
          directly above already reads "% of another service — a share of its
          charge", so a clerk who moves the radio watches the units go and needs
          no paragraph about it. The server refuses a unit on a share service by
          name for the callers that are not this form. */}
      {basis !== "share" && (
        <>
          <SelectField
            id="primary_uom"
            label={t("settings.services.primaryUom")}
            value={primary}
            onChange={setPrimary}
            options={options}
            placeholder={t("settings.services.pickUom")}
            required
          />
          <SelectField
            id="alt_uom"
            label={t("settings.services.altUom")}
            value={alt}
            onChange={setAlt}
            options={options}
            placeholder={t("settings.services.noneOptional")}
          />
          {/* r6.4 / BR-RAT-038. The placeholder is the MEANING of leaving it
              empty, not the word "None": an unset billed unit bills in the
              register's own unit, which is a decision and not an absence. */}
          <SelectField
            id="billed_uom"
            label={t("settings.services.billedUom")}
            value={billed}
            onChange={setBilled}
            options={options}
            placeholder={t("settings.services.billedUomSame")}
          />
          <TextField
            id="conversion_factor"
            label={t("settings.services.conversionFactor")}
            value={factor}
            onChange={setFactor}
            numeric
            help={t("settings.services.factorHint")}
          />
          {/* B14 rule 11 — what this will do, said before the commit button and
              not after it. BR-TEN-027, for the units above. */}
          <Note>{t("settings.services.uomForwardOnly")}</Note>
        </>
      )}
      <Note>{t("settings.services.meteringConsequence")}</Note>
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-007@53479d6 (story+rules snapshot hash — EP-TEN-06; co-story US-TEN-008@53479d6)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope)
// exceptions: [DEF-184 lane 2026-08-17] `activeUomOptions` now takes the SERVICE being edited and applies `selectors.uom_scope_filter` on the screen — a water service is no longer offered `therm`. A unit the service ALREADY stores is kept, disabled, with the reason in its own label (FieldOption's rule), because the server's `resolve_uom` re-resolves BOTH units through the same filter on every save and would refuse a re-pick · NOT FIXED HERE, REPORTED: (a) a service whose STORED primary is out of scope cannot be saved at all until that primary is changed, and the server's refusal for it is `settings.services.uom_unknown` ("We don't recognize the unit therm, or it has been deactivated") — accurate about the outcome, wrong about the reason; a scope-specific message_key is a backend change and apps/tenancy is another lane's territory · (b) BR-TEN-029 still wins over the keep-what-is-stored rule, so a stored unit that has ALSO been deactivated does vanish from the picker — the backend anticipated this case (`uoms_for_service(include_inactive=…)`) but no rule says the modal may show one, and choosing one is the prime directive's line · (c) the modal's rendered output is not asserted (it opens on state this suite never sets); the scope rule is covered as a pure function and the wiring by tsc · E1 the B9 row for this screen declares NO table capabilities (6 fixed rows, no chooser, no pager) while FE-02 DataTable renders its ⋮ chooser and pager unconditionally — a plain semantic table is used so the screen shows only what the matrix allows; the FE-02 gap is reported, not patched from here · E4 the prototype's per-row `<select>` of actions is rendered as explicit buttons: a select whose options are actions cannot express BR-SHL-025 disabled-with-reason per action — reported
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
