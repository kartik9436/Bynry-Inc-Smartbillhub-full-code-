// ── Trace ──────────────────────────────────────────────
// Change:  CR-036 (h) — *"No screen can set a premises' services. The
//          Add-Premises wizard and the edit modal both omit the field — only
//          the CSV importer ever fills it. So every address you create by hand
//          has none. - we will ahve to fix that keep them in CR36 only"*
//          (PO, 2026-08-26). DEF-756, promoted to a scoped item.
// Screens: S16 (the guided add, single-premise step) · PRM-01/PRM-02 edit modal
// Rules:   BR-MET-003 (a premises may only offer services this utility SELLS —
//          `services_available` ⊆ the tenant's enabled set) ·
//          B14 rule 9 (a multi-select is removable CHIPS + an add control,
//          never a wall of checkboxes) · B14 rule 21 (new UI is Tailwind
//          utilities and adds NO class to a stylesheet)
// Tests:    src/features/metering/PremisesServices.dom.test.tsx ·
//           src/features/metering/PremisesServicesNotRecorded.dom.test.tsx ·
//           src/features/metering/def4742EnglishOnlyKeys.test.ts
// ───────────────────────────────────────────────────────
// ONE control, two screens — the same reason `AreaFields` exists: a second copy
// is a second place to add a service rule to, and one of them would be
// forgotten (DEF-021's shape, and DEF-756 is the same shape one level up).
//
// ⚠ **WHY THE OPTIONS ARE A QUERY AND NEVER A LIST IN THIS FILE.** Ten services
// exist platform-wide and a tenant sells some subset of them; BR-MET-003 says a
// premises may offer only what this utility sells. `GET /settings/services` is
// the ONE place that answers which — the same source the CSV importer validates
// against (`apps/metering/import_rules._eval_services_enabled` reads
// `World.enabled_services`, built from `seams.enabled_service_codes()`), and the
// same source `apps/metering/services._clean_services` refuses against on the
// write. A hardcoded array here would be a fourth answer to a question that
// already has one, and it would be wrong for every tenant that turns a service
// on tomorrow.
//
// ⚠ **AND `null` IS NOT `[]`.** A premises whose `services_available` column has
// never been written holds SQL NULL, which means *never asked* — not *offers
// nothing*. The CALLERS decide whether to SEND the field at all, and both of
// them send it only when the clerk's answer differs from what they were shown.
// Backfilling NULL to `[]` on an unrelated address edit would destroy the only
// signal that the address was never asked (CR-036 (h), scope row 5).
//
// ⚠ **AND THIS CONTROL CAN NOW SEE THE DIFFERENCE, WHICH IT COULD NOT WHEN IT
// WAS WRITTEN (DEF-762).** The paragraph above used to end *"the premises
// selector serves both as `[]`, so this control cannot tell them apart and must
// not pretend to"* — true when it was written and false since the selector
// stopped collapsing the two. `value` is therefore `readonly string[] | null`:
// `null` draws *Not recorded* rather than *No services*, and the moment the
// clerk touches the control the value becomes an array, which is an ANSWER and
// is sent. That is how an unasked address finally becomes answerable as
// "offers nothing" — before, an untouched `null` and a deliberate `[]` were the
// same value and the caller could not send one without inventing the other.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getTenantServices } from "@/api/endpoints";
import type { TenantServiceRow } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { useFieldError } from "@/components/FormModal";
import { FieldError } from "@/components/StateFrame";

/** The field id the SERVER names in a `field_errors` entry — so a refusal from
 *  `_clean_services` ("... isn't one of the services this utility bills") lands
 *  under this control and not at the top of the form as an orphan. */
export const SERVICES_FIELD_ID = "services_available";

/** The enabled subset, in the platform's own seed order — which is the order
 *  `GET /settings/services` returns and therefore the order every screen in the
 *  product already lists services in. Never re-sorted here. */
export function enabledServiceRows(
  rows: readonly TenantServiceRow[] | undefined,
): readonly TenantServiceRow[] {
  return (rows ?? []).filter((row) => row.enabled);
}

/** Two answers are the SAME when they hold the same codes, whatever order the
 *  clerk added them in. Callers use this to decide whether to send the field at
 *  all — see the `null`-is-not-`[]` note above.
 *
 *  ⚠ `null` is one of the values it compares, and it is NOT equal to `[]`
 *  (DEF-762). *Never asked* and *offers nothing* are two answers, so a form that
 *  opened on `null` and closed on `[]` has CHANGED and must send `[]`; a form
 *  that opened and closed on `null` has not, and must send nothing at all. */
export function sameServices(
  a: readonly string[] | null,
  b: readonly string[] | null,
): boolean {
  if (a === null || b === null) {
    return a === b;
  }
  return a.length === b.length && [...a].sort().join(" ") === [...b].sort().join(" ");
}

export function ServicesAvailableField(props: {
  /** `null` = nobody has been asked about this address yet (DEF-762). Any array,
   *  empty included, is somebody's answer. */
  value: readonly string[] | null;
  onChange: (next: string[]) => void;
  client?: ApiClient;
  /** Full-page forms pass the refusal directly; inside a FormModal the frame's
   *  context supplies it, exactly as every other field in the kit works. */
  error?: string;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const contextError = useFieldError(SERVICES_FIELD_ID);
  const error = props.error ?? contextError;
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const enabled = enabledServiceRows(servicesQuery.data);
  const nameOf = (code: string): string =>
    enabled.find((row) => row.service === code)?.name ??
    t(`rating.service.${code}`, { defaultValue: code });
  // The chips are drawn from the ANSWER; `null` has no chips and says so below.
  const chosen = props.value ?? [];
  const remaining = enabled.filter((row) => !chosen.includes(row.service));
  // `B4`'s type-to-filter box. Its own state, because what a clerk has typed so
  // far is not an answer yet — the answer is `props.value`, and a half-typed
  // word must not reach it.
  const [typed, setTyped] = useState("");

  return (
    <div className="field">
      <label id={`${SERVICES_FIELD_ID}-label`} htmlFor={`${SERVICES_FIELD_ID}-add`}>
        {t("metering.premises.col.services")}
      </label>
      <p className="field-help" id={`${SERVICES_FIELD_ID}-help`}>
        {t("metering.premises.field.servicesHelp")}
      </p>
      <div
        className="flex flex-wrap items-center gap-1.5"
        role="group"
        aria-labelledby={`${SERVICES_FIELD_ID}-label`}
        aria-describedby={`${SERVICES_FIELD_ID}-help`}
      >
        {/* DEF-762 — the form says WHY it is empty. "No services" beneath an
            untouched control read as an answer this address had given; it had
            given none. */}
        {props.value === null && (
          <span className="text-sm text-neutral-600">
            {t("metering.premises.field.servicesNotRecorded")}
          </span>
        )}
        {props.value !== null && props.value.length === 0 && (
          <span className="text-sm text-neutral-600">{t("metering.services.none")}</span>
        )}
        {/* B14 rule 9 — removable chips, never a wall of checkboxes. */}
        {chosen.map((code) => (
          <button
            key={code}
            type="button"
            className="cursor-pointer border border-divider bg-transparent bg-none px-2 py-[3px] text-sm text-inherit hover:border-accent hover:text-accent"
            aria-label={t("metering.premises.field.servicesRemove", { service: nameOf(code) })}
            onClick={() => props.onChange(chosen.filter((kept) => kept !== code))}
          >
            {nameOf(code)} x
          </button>
        ))}
        {/* ── CR-089 wave B `B4` — TYPE-TO-FILTER ─────────────────────────
            PO 2026-09-08, verbatim: *"Services available = Utility services =
            drop down - multi select."* The chips and the multi-select were here
            already; what was not was the ability to TYPE. Eleven services is
            past the point where a clerk scans a menu — `fire` was appended at
            position 11 by `CR-063` and is the last option in the list, which is
            exactly the one a warehouse clerk needs most.
            ⚠ A `datalist`, not a second picker component. `SearchSelectField`
            is the house control for a long list (`BR-SHL-033`) and it is a
            SINGLE-value control with its own label and layout; wrapping one to
            act as an *add* button inside a chip row would give this field two
            labels and two error slots. The native list keeps one control, one
            label, and adds the filtering the ruling asks for. */}
        <input
          id={`${SERVICES_FIELD_ID}-type`}
          list={`${SERVICES_FIELD_ID}-options`}
          aria-label={t("metering.premises.field.servicesAdd")}
          className="min-h-[26px] w-auto border border-field-border bg-bg px-1.5 py-0.5 text-sm text-text"
          placeholder={t("metering.premises.field.servicesAdd")}
          value={typed}
          disabled={remaining.length === 0}
          aria-invalid={error !== undefined ? true : undefined}
          onChange={(event) => {
            const text = event.target.value;
            // A `datalist` fires `change` with the option's VALUE when one is
            // picked and with free text while typing, so the add happens only
            // on an exact match against what is still available — a half-typed
            // word must never add a service.
            const match = remaining.find(
              (row) => row.service === text || nameOf(row.service) === text,
            );
            if (match !== undefined) {
              setTyped("");
              props.onChange([...chosen, match.service]);
              return;
            }
            setTyped(text);
          }}
        />
        <datalist id={`${SERVICES_FIELD_ID}-options`}>
          {remaining.map((row) => (
            <option key={row.service} value={nameOf(row.service)} />
          ))}
        </datalist>
        {/* Kept beside the typing box rather than replaced by it: a clerk who
            does not know what the utility sells needs to SEE the list, and a
            `datalist` only opens on focus. Two ways into one answer, one state. */}
        {/* ⚠ **THIS KEEPS THE `id` THE `<label htmlFor>` NAMES, AND THAT IS NOT
            COSMETIC.** The field's accessible name is *Services available* and
            three shipped cases resolve it with `getByRole("combobox", { name:
            "Services available" })`. Moving that id onto the typing box above
            silently re-pointed the label at an `<input list=…>` — which is ALSO
            a combobox — so `selectOptions(..., "water")` failed with *"Value
            water not found in options"* and the control a screen reader
            announces changed with it. The typing box carries its own
            `aria-label` instead. */}
        <select
          id={`${SERVICES_FIELD_ID}-add`}
          className="min-h-[26px] w-auto border border-field-border bg-bg px-1.5 py-0.5 text-sm text-text"
          value=""
          disabled={remaining.length === 0}
          aria-invalid={error !== undefined ? true : undefined}
          onChange={(event) => {
            const code = event.target.value;
            if (code !== "" && !chosen.includes(code)) {
              // The tenant's OWN order, so this address, the list column and the
              // export all read the services in one sequence.
              props.onChange(
                enabled
                  .map((row) => row.service)
                  .filter((service) => service === code || chosen.includes(service)),
              );
            }
          }}
        >
          <option value="">
            {remaining.length === 0
              ? t("metering.premises.field.servicesAllAdded")
              : t("metering.premises.field.servicesAdd")}
          </option>
          {remaining.map((row) => (
            <option key={row.service} value={row.service}>
              {row.name}
            </option>
          ))}
        </select>
      </div>
      {/* The list could not be read. Said out loud rather than rendered as an
          empty menu, which is indistinguishable from "you sell nothing". */}
      {servicesQuery.data === undefined && !servicesQuery.isPending && (
        <p className="field-help">
          {t("metering.premises.field.servicesUnavailable")}
        </p>
      )}
      {error !== undefined && <FieldError id={`${SERVICES_FIELD_ID}-error`} message={error} />}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-003@4ebc614 (EP-MET-01-premises-units.md, git hash-object,
//         short) + BR-MET-003 in 04-docs/05-modules/04-metering/02-business-rules.md
//         @a5f68c8 + CR-036 (h), 12-governance/11-change-requests.md (verbatim)
//         + DEF-756, 12-governance/10-defect-log.csv
// screens: S16 (A1, the guided add) · PRM-01 / PRM-02 (r10, the premises edit modal)
// generated: 2026-08-26 by lane PREMSVC (CR-036 (h) / DEF-756)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc --noEmit exit 0 · vitest src/features/metering/ 284 passed .
//        vitest routeBUtilities 10 passed · g31_declared_classes.py PASS (0, at
//        the baseline) · g13_unwired.py PASS · eslint --max-warnings 0 exit 0
// exceptions:
//   E4 **r10 DRAWS A WALL OF CHECKBOXES AND THIS DRAWS CHIPS.** The S16 add form
//      in `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` heads the control
//      `Services available at this premise` and renders a six-column grid of
//      `label.service-chip > input[type=checkbox]`. **B14 rule 9 wins** — *"a
//      multi-select renders as removable chips + an add control, never a wall of
//      checkboxes"* — as CLAUDE.md requires (r10's UI-RULES is the SOURCE, B14 is
//      the authority). The house precedent is `RoutesCyclesWizards.tsx`'s area
//      chips, and the shape scales: r10's grid was drawn for six services and
//      the platform sells TEN.
//   E3 **r10's SIX ARE HARDCODED AND TWO ARE PRE-TICKED REGARDLESS OF TENANT** —
//      Electric, Water, Gas, Sewer, Trash, Broadband, with Electric and Water
//      `checked`. That list is not portable and CR-036 (h) forbids it outright
//      (*"the tenant's own ENABLED services — never a hardcoded list"*), so the
//      options come from `GET /settings/services` filtered to `enabled`. Storm
//      water, Solar, Thermal/Heat and Battery are absent from r10's drawing and
//      are offered here the moment a tenant switches one on.
//   ✔ r10's PRE-TICKED posture IS honoured and is not this file's invention: the
//      S16 wizard opens with every enabled service on the address and the clerk
//      removes the exceptions (`resolvedServices` in `AddPremisesWizard.tsx`).
//      The EDIT modal does not — it opens on what the server stored, because a
//      premises already on file has an answer (or a NULL) that a default would
//      overwrite.
//   E4 the control renders as a standard `.field` with the kit's label, help and
//      `FieldError`, where r10 uses a bare `span.kicker` heading. The kit is what
//      carries the server's `field_errors["services_available"]` refusal to the
//      control that caused it; a kicker has no error slot, and BR-MET-003's
//      refusal has to land somewhere a clerk can see it.
//   E3 the service NAME is the server's own (`TenantServiceRow.name`), falling
//      back to `rating.service.<code>` and then the raw code. `metering.service.*`
//      is NOT used: that namespace holds only SIX of the ten platform codes, so
//      `storm_water`, `solar`, `thermal_heat` and `battery` would print raw.
//      ⚠ **REPORTED here as DEF-763 and FIXED 2026-08-26 by lane DEFSWEEP** —
//      the four other screens (and two more this row had not counted, both in
//      `BillRunWizard.tsx`) now read `rating.service.*` too, and the six-key
//      namespace has no call site left.
//   ✔ **CLOSED 2026-09-10 (`DEF-4742`).** This row read *"the five new copy keys
//      carry `defaultValue` and are handed over in `scratchpad/newkeys-PREMSVC.json`
//      … G27 counts this component until an orchestrator merges them."* The
//      hand-off file was never merged and the scratchpad is not durable, so four
//      of those keys — `servicesHelp`, `servicesRemove`, `servicesAllAdded`,
//      `servicesUnavailable` — sat in **none of the eleven catalogues for two
//      weeks**, rendering their English `defaultValue` to every tenant in every
//      language, permanently and silently: nothing is *missing* at runtime when a
//      call site carries its own fallback, so no warning fires, and the parity
//      gate compares the ten catalogues against `en.json` and had nothing to
//      compare. All four are now in all eleven, and **every `defaultValue` in
//      this file is deleted** so a future absence prints the key instead of
//      quietly printing English. The one that remains is
//      `rating.service.${code}` — a DYNAMIC key whose fallback to the raw code is
//      the deliberate last resort for a service this catalogue has never heard of.
//      `ServicesAvailableFieldKeys.test.tsx` is the check that goes red if one
//      comes back.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
