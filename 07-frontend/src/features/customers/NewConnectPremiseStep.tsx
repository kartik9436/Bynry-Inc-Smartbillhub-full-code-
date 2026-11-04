// ── Trace ──────────────────────────────────────────────
// Change:   Lane E wave 1 — SPLIT OUT OF `NewConnectWizard.tsx`.
//           2026-09-16 (`CR-094-BRC01` wave 2 lane G) — premises NAME, the
//           town in three fields, services, the PLAN and a register SEARCH.
//           Lane TEXT — 2026-09-28 — four sentences deleted, one moved.
//           **Lane CUSTOMER-PREMISE — 2026-09-29 — REBUILT FROM THE DRAWING**
//           `05-prototype/new-connect-redesign-2026-09-28/step2-premise.png`,
//           read AS AN IMAGE (B14 rule 42) and built with our own kit
//           (rule 44). `CR-150-BRC09` `NCT-01` task 6.
// Rules:    CLAUDE.md hard rule 8 (an address is stored on `premises` and
//           nowhere else — this is the one step that asks for one, and the one
//           door that can create a SECOND row for one building) ·
//           `BR-MET-1162` (a UNIT may carry its own `lat`/`lng`; where it does
//           those are the truth for that unit, with the building's as the
//           fallback — **and every screen showing a point says which of the
//           two it is showing**) · hard rule 2 (no money is multiplied up in
//           this client) · BR-MET-003 · BR-MET-034 · BR-RAT-030 (only a
//           PUBLISHED plan is assignable) · BR-SHL-025 · B14 rule 9 · rule 21 ·
//           rule 31 · rule 32 · rule 33 · rule 37 · rule 42 · rule 43 · rule 44
// Tests:    newConnectSteps12Redesign.dom.test.tsx · NewConnectWizard.test.tsx ·
//           features/rating/planSections/ThisPlanBlock.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// STEP 2 · PREMISE — *"The premise"*
// ══════════════════════════════════════════════════════════════════════════
//
// ── WHAT THE DRAWING SETTLED THAT THE OLD SCREEN GOT WRONG ────────────────
//   * **`Unit, apt. or suite` IS ENABLED AND OPTIONAL.** It was `disabled`
//     with the help line *"Named on the next step"*, and the PO asked why it
//     was required and why it was greyed. The drawing answers both: *"Unit,
//     apt. or suite is enabled and optional. It is part of the postal address;
//     unit labels stay on step 3."* So it is the POSTAL line — `Suite 200` on
//     an envelope — and not a unit record. Hard rule 8 is untouched: it is
//     part of the premises' own address and is stored with it.
//   * **The record gains `Latitude`, `Longitude` and `Location verified`**,
//     all optional. PO: *"you should include lat and long and verified tag -
//     all these will be options"*.
//   * **`Scope` MOVES HERE FROM STEP 1** — the step-1 drawing's own *Removed
//     from this step* list says *"Scope and its three explanation lines, moved
//     to step 2"*, and the step-2 drawing draws it as `What is built`.
//   * **THE PLAN IS SHOWN IN FULL AND EACH SERVICE SHOWS ITS PRICE.** PO:
//     *"you ahve to show more details of plan and Utility services here"*. The
//     summary was three rows (name, covers, effective); the drawing asks for
//     code, status and version, effective dates, account type, budget billing,
//     minimum bill, the description, and then a row per chosen service saying
//     how the plan prices it.
//     ⚠ **SUPERSEDED 2026-10-06 (`DEF-CUS-9821`) — that facts grid and the
//     *What each service is priced at* table are REPLACED by `ThisPlanBlock`**
//     (`features/rating/planSections/`), redrawn to the PO-approved drawing:
//     PO, *"all component bind in plan like rate, charge,code, base reate,
//     taxes, discount needs to visible"*. Only the Services and plan panel's
//     plan information moved; nothing else on this step did.
//
// ── THE POINT SAYS WHOSE IT IS, AND THAT IS THE RULE RATHER THAN A NICETY ─
// `BR-MET-1162`'s last clause is a SCREEN obligation: a unit may carry its own
// `lat`/`lng` and where it does those are the truth for that unit, so *every
// screen showing a point says which of the two it is showing*. This step only
// ever shows the BUILDING's, and it says so in five words beside the boxes.
// Without that line a clerk reading a unit's own point on another screen has
// no way to tell the two apart — which is the whole reason the clause exists.
//
// ── WHAT IS DRAWN AND IS NOT BUILT, STAMPED RATHER THAN SILENT ────────────
// See `05-prototype/new-connect-redesign-2026-09-28/DIVERGENCES-steps-1-2.md`.
// Three: the `PRICED AS` column's pricing BASIS (*Metered · Water 1"*) has no
// field on any endpoint, so the attached rate schedule's NAME is what is
// shown; `ACCOUNT TYPE` resolves to a uuid nobody publishes a name for (B14
// rule 31 forbids printing it); and `State` is a text box because the state
// list has no door.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import {
  getLookupEntries,
  getPremisesDetail,
  getPremisesTypes,
  getRoutes,
  getShellDisplay,
  getUnitPlanOptions,
} from "@/api/endpoints";
import type { UnitPlanOption } from "@/api/endpoints";
import { getPlanWithSections } from "@/api/planFormEndpoints";
import { Button } from "@/components/Button";
import { CheckboxField, SelectField, TextField } from "@/components/FormModal";
import { CustomFieldsInput, CustomFieldsView } from "@/components/CustomFields";
import { Panel } from "@/components/Panel";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { US_STATE_ROWS } from "@/components/usStates";
import { US_ZIP } from "@/components/UsAddressFields";
import { queryKeys } from "@/api/queryClient";
// ⚠ **THE SERVICE LIST IS READ FROM THE TENANT AND IS NEVER TYPED HERE.**
// `BR-MET-003` says a premises may offer only what this utility sells, and
// `GET /settings/services` is the ONE place that answers which. A list typed
// into this file would be the third hand-typed service list in the front end,
// which is exactly how `fire` reached position 11 and never appeared on the
// sign-up screen.
import { ServicesAvailableField } from "@/features/metering/ServicesAvailableField";

import { CONNECT_SCOPES } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import type { Translator } from "./newConnectShared";
import { FieldGrid } from "./serviceRequestShared";
// ⚠ **THE SAME SEARCH DOOR THE REQUEST WIZARD USES, NOT A SECOND ONE.**
// `GET /premises/picker` hands the paginator an UNEVALUATED queryset, so the
// read costs the page rather than the register (`NFR-3`).
import { searchPremisesPicker } from "./serviceRequestEndpoints";
import type { PremisesPickerRow } from "./serviceRequestEndpoints";
import { StepIntro } from "./newConnectStepKit";
// ⊕ `DEF-CUS-9821` — the plan block is the RATING kit's, one component (B14
// rule 43), fed by the plan details page's own read.
import { ThisPlanBlock } from "@/features/rating/planSections/ThisPlanBlock";
import { RequestPrefillNote } from "./moveInRequestBlocks";

/**
 * **The seeded catalogue, as a FALLBACK only — `DEF-MET-5463`.**
 *
 * ⚠ **THIS LIST READ `single_family · multi_unit · commercial · industrial`
 * UNTIL 2026-09-16 AND THREE OF THOSE FOUR CODES DO NOT EXIST ON THE SERVER.**
 * `premises_type` is resolved against the tenant's own Reference-data list
 * (`BR-MET-034`), whose seeded six are below. **THE REAL FIX IS THE QUERY, NOT
 * THIS CONSTANT** — these six are what the screen offers while the catalogue
 * is still loading, kept EQUAL to `services.SEED_PREMISES_TYPES`.
 */
export const PREMISE_TYPES = [
  { code: "apartment_complex", en: "Apartment complex" },
  { code: "commercial_building", en: "Commercial building" },
  { code: "single_family", en: "Single-family" },
  { code: "mixed_use", en: "Mixed-use" },
  { code: "mobile_home_park", en: "Mobile-home park" },
  { code: "government_building", en: "Government building" },
] as const;

/** The same key `PremisesListPage` pages on, so the two screens cannot
 *  disagree about what kinds of property this utility has. */
export const newConnectPremisesTypesQueryKey = ["premises", "types"] as const;

/** `BR-RAT-030` — the picker asks for PUBLISHED plans and nothing else. */
export const newConnectPlansQueryKey = ["new-connect", "plans"] as const;

/** The read routes this utility has, for the drawn `Choose a route` list.
 *  ⚠ **THE VALUE IS THE ROUTE'S CODE AND NOT ITS ID** — `_resolve_create_route`
 *  accepts either, and B14 rule 31 keeps a uuid off the screen AND out of a
 *  control's value where a human-readable key exists. */
export const newConnectRoutesQueryKey = ["new-connect", "routes"] as const;

/** Two characters before the register is asked, because the server IGNORES a
 *  shorter `q` rather than refusing it (`BR-SHL-011`). */
const SEARCH_MIN = 2;

/**
 * **WHAT A PICK WRITES ONTO THE DRAFT — `DEF-CUS-6057`.**
 *
 * ⚠ **IT IS A FUNCTION RATHER THAN FOUR LINES INSIDE `pick` BECAUSE THAT IS
 * THE ONLY WAY THE SEAM CAN BE ASSERTED.** `address_picker.row()` served six
 * honest fields and `pick()` wrote four honest ones, and every test on both
 * sides passed — **nothing compared what the picker RETURNS against what the
 * next step NEEDS**, because that question belonged to no file.
 *
 * ⚠ **AND `null` IS NOT `[]` (`DEF-762`).** A premises whose column has never
 * been written holds SQL NULL — *nobody has been asked* — and writing `[]`
 * from that would silently blank a list the clerk had already ticked.
 *
 * ⚠ **THE PARCEL, THE READ ROUTE, THE POINT AND THE BUILDING'S NAME STILL DO
 * NOT TRAVEL.** They are asked under *The record*, they are genuinely the
 * clerk's to give on a NEW premises, and none of them feeds a later step.
 */
export function patchFromPickedPremises(
  draft: NewConnectDraft,
  row: PremisesPickerRow,
): Partial<NewConnectDraft> {
  const patch: Partial<NewConnectDraft> = {
    premise: {
      ...draft.premise,
      premisesId: row.id,
      address: row.address_line ?? "",
      city: row.city ?? "",
      state: row.state ?? "",
      postalCode: row.postal_code ?? "",
    },
  };
  if (Array.isArray(row.services_available)) {
    patch.premiseServices = [...row.services_available];
  }
  // ⚠ **A STRING IS AN ANSWER; `null` AND `undefined` ARE NOT** — `DEF-762`'s
  // condition again. A premises whose type was never set leaves the question
  // to the clerk rather than blanking an answer they may already have chosen.
  if (typeof row.premises_type === "string" && row.premises_type !== "") {
    patch.premise = { ...draft.premise, ...patch.premise, premiseType: row.premises_type };
  }
  return patch;
}

/**
 * **IS THIS FIELD THE REGISTER'S ANSWER RATHER THAN THE CLERK'S QUESTION?**
 *
 * `DEF-CUS-6116` — over a premises already on file, the premise type is a fact
 * the register holds, so it is SHOWN and not ASKED.
 */
export function premiseTypeIsOnFile(draft: NewConnectDraft): boolean {
  return draft.premise.premisesId !== "" && draft.premise.premiseType !== "";
}

/**
 * **THE ADDRESS IS THE REGISTER'S ONCE A ROW IS PICKED — HARD RULE 8.**
 *
 * An address lives on `premises` and nowhere else, and every meter, account,
 * route, cycle, bill and work order reaches it by walking back. So once the
 * clerk has said *this building*, the town, the state and the postcode are
 * **walked from that premises and shown read-only**: a second answer typed
 * here would be one building's history splitting in two. *Change address*
 * hands the question back, because then it really is theirs.
 */
export function premiseAddressIsOnFile(draft: NewConnectDraft): boolean {
  return draft.premise.premisesId !== "";
}

/**
 * ⊕ **`CR-164-BRC10` · PO ruling Q7 (2026-10-02) — *"City/State mismatch
 * reason"*.** The step accepted any State and any ZIP in silence and the
 * clerk learned nothing until a letter came back. Three FACTS, each said where
 * it is true, none of them blocking (an address outside the utility's own
 * state is lawful — a cross-border district exists):
 *
 *   * a State that is not a US postal code — the list is `usStates.ts`, the
 *     kit's one copy of `apps/tenancy/selectors.US_STATES`;
 *   * a State that is not the utility's own (`tenants.state`, served on
 *     `GET /shell/display` — every signed-in role may read it; it was
 *     `GET /settings/regional` until `DEF-SHL-10116`, which a Billing Clerk
 *     is refused, so the reason silently never appeared for one);
 *   * a ZIP that is neither five digits nor ZIP+4 (`US_ZIP`, the kit's own).
 *
 * The catalogue key of the first that applies to each box, or `null`.
 */
/** A state as its postal code — `tenants.state` is stored as typed at sign-up,
 *  `Texas` as often as `TX`, so both spellings resolve to one code. */
export function stateCodeOf(value: string): string {
  const typed = value.trim();
  const byName = US_STATE_ROWS.find(([, name]) => name.toLowerCase() === typed.toLowerCase());
  return byName !== undefined ? byName[0] : typed.toUpperCase();
}

export function addressReasons(
  premise: { state: string; postalCode: string },
  tenantState: string | null,
): { state: string | null; zip: string | null } {
  const typed = premise.state.trim().toUpperCase();
  let state: string | null = null;
  if (typed !== "") {
    if (!US_STATE_ROWS.some(([code]) => code === typed)) {
      state = "customers.newConnect.step2.stateNotACode";
    } else if (tenantState !== null && tenantState.trim() !== "" && stateCodeOf(tenantState) !== typed) {
      state = "customers.newConnect.step2.stateNotTheUtilitys";
    }
  }
  const zip = premise.postalCode.trim();
  return {
    state,
    zip: zip !== "" && !US_ZIP.test(zip) ? "customers.newConnect.step2.zipShape" : null,
  };
}

/** ⊕ PO ruling Q7 — *"hide Unit/apt for apartment complexes"*: the units of a
 *  complex are named on step 3, so a postal *Unit, apt.* box over the whole
 *  building would be a second, conflicting answer. */
export const UNIT_LINE_HIDDEN_FOR = new Set(["apartment_complex"]);

export function PremiseStep(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
}) {
  const { t } = props;
  const set = (patch: Partial<NewConnectDraft["premise"]>) =>
    props.onPatch({ premise: { ...props.draft.premise, ...patch } });
  // ⊕ `CR-164-BRC10` Q7 — the utility's own state, for the mismatch reason.
  // `DEF-SHL-10116` — from the read every role may make (the shell has already
  // fetched it, so this is a cache hit), never the admin-only regional read.
  const display = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(api),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const reasons = addressReasons(props.draft.premise, display.data?.regional.state ?? null);
  const unitLineHidden = UNIT_LINE_HIDDEN_FOR.has(props.draft.premise.premiseType);
  // ⊕ `DEF-CUS-9200` (item 13) — the plan's customer classes BY NAME. The
  // list `/lookups/account_types` is the one the plan wizard picks them from.
  const accountTypes = useQuery({
    queryKey: queryKeys.lookupEntries("account_types", "", 1, 100),
    queryFn: () => getLookupEntries("account_types", { page: 1, per: 100 }, api),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // `BR-MET-034` / `DEF-MET-5463` — the tenant's own list, never a hardcoded
  // set. `retry: false` and the fallback mean a utility whose catalogue cannot
  // be read still gets the six seeded codes rather than an empty select.
  const typesQuery = useQuery({
    queryKey: newConnectPremisesTypesQueryKey,
    queryFn: () => getPremisesTypes(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const typeOptions = (typesQuery.data ?? []).filter((row) => row.active).length
    ? (typesQuery.data ?? [])
        .filter((row) => row.active)
        .map((row) => ({ value: row.code, label: row.name }))
    : PREMISE_TYPES.map((row) => ({
        value: row.code,
        label: t(`customers.newConnect.premiseType.${row.code}`, { defaultValue: row.en }),
      }));

  // ── THE REGISTER'S OWN SEARCH ────────────────────────────────────────────
  // ⚠ **WHAT THE CLERK TYPES IN THE STREET BOX *IS* THE QUERY.** A separate
  // search box would be a second place to type the same address.
  const [picked, setPicked] = useState<PremisesPickerRow | null>(null);
  const query = props.draft.premise.address;
  const searching = query.trim().length >= SEARCH_MIN && props.draft.premise.premisesId === "";
  const premisesSearch = useQuery({
    queryKey: ["new-connect-premises-picker", query],
    queryFn: () => searchPremisesPicker(query, api),
    enabled: searching,
  });
  const results = premisesSearch.data?.results ?? [];
  // ── `CR-161-BRC10` W3 · `DEF-MET-9226` — New Connection · Step 2 Premise ──
  // A NEW property takes the Premises fields placed Input here; a property
  // picked off the register SHOWS its stored answers (Input implies View) and
  // writes nothing to them — this wizard never edits an address on file (hard
  // rule 8). The read is the property's own detail, asked only once picked.
  const pickedId = props.draft.premise.premisesId;
  const pickedDetail = useQuery({
    queryKey: ["premises", "detail", pickedId],
    queryFn: () => getPremisesDetail(pickedId, api),
    enabled: pickedId !== "",
    retry: false,
  });

  /** Picking writes the WHOLE address at once, because the register already
   *  holds all four parts of it and re-typing one of them is how two rows for
   *  one building start to disagree (hard rule 8). */
  const pick = (row: PremisesPickerRow) => {
    setPicked(row);
    props.onPatch(patchFromPickedPremises(props.draft, row));
  };
  /** Letting go of the register row, so the boxes become the clerk's own
   *  again. The address is LEFT as it stands. */
  const unpick = () => {
    setPicked(null);
    set({ premisesId: "" });
  };

  // The drawn `Choose a route` list. `retry: false` — a utility whose routes
  // cannot be read gets an empty list and an optional field, never a spinner
  // in front of the rest of the step.
  const routesQuery = useQuery({
    queryKey: newConnectRoutesQueryKey,
    queryFn: () => getRoutes(api),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  // ── THE PLAN, MOVED HERE FROM STEP 5 (PO 2026-09-16) ─────────────────────
  // ⚠ **`planApartments` IS THE ONE ASKED HERE AND `planCommonArea` IS NOT.**
  // The common area's plan depends on whether the unit pattern HAS one, and
  // the pattern is step 3. The PO asked for *"Plan"*, singular.
  const plansQuery = useQuery({
    queryKey: newConnectPlansQueryKey,
    queryFn: () => getUnitPlanOptions({ per: 200 }, api),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const plans: UnitPlanOption[] = plansQuery.data?.results ?? [];
  const chosenPlan: UnitPlanOption | null =
    plans.find((plan) => plan.id === props.draft.planApartments) ?? null;

  // ⚠ **THE FULL PLAN IS A SECOND READ AND IT HAS TO BE (PO 2026-09-16, and
  // again on the redesign: *"you ahve to show more details of plan"*).** The
  // PICKER serves `id · code · name · status · services · effective_from` and
  // nothing else. ⊕ `DEF-CUS-9821` (PO 2026-10-06, *"all component bind in
  // plan … needs to visible"*) — `GET /plans/{id}` is read ONCE as both of the
  // shapes it serves (the plan's row and its sections), with the OWNER'S class
  // from step 1 so the server narrows each base the way the bill picks it.
  // Fetched only once a plan is CHOSEN, so the step's first paint stays at the
  // reads it already made; a new plan or a new class is a new key and refreshes
  // the block.
  const ownerClass = props.draft.owner.category ?? "";
  const planDetail = useQuery({
    queryKey: ["new-connect", "plan-detail", props.draft.planApartments, ownerClass],
    queryFn: () =>
      getPlanWithSections(props.draft.planApartments, ownerClass === "" ? [] : [ownerClass], api),
    enabled: props.draft.planApartments !== "",
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // The class BY NAME for the block's footer (B14 rule 31: never the code).
  const ownerClassName =
    ownerClass === ""
      ? null
      : ((accountTypes.data?.results ?? []).find((row) => row.code === ownerClass)?.name ?? null);
  // `DEF-CUS-6116` — the type is the register's answer over a picked address.
  const onFile = premiseTypeIsOnFile(props.draft);
  // Hard rule 8 — so is the town, once a building has been named.
  const addressOnFile = premiseAddressIsOnFile(props.draft);

  return (
    <>
      {/* ══════════════════ ADDRESS ═══════════════════════════════════════ */}
      <Panel as="section" data-step-content="address">
        <StepIntro title={t("customers.newConnect.step3.address", { defaultValue: "Address" })} />
        {/* ⊕ `DEF-CUS-9828` (N2) — the address arrived from the request; the
            shared move-in note, four words and the request number. */}
        {props.draft.requestNo !== null && (
          <div className="mb-4" data-from-request="address">
            <RequestPrefillNote requestNo={props.draft.requestNo} t={t} />
          </div>
        )}

        <FieldGrid columns={2}>
          {/* ── `DEF-CUS-6116` · ANSWERED FROM THE RECORD, NOT ASKED AGAIN ──
              DISABLED, which is this screen's own habit (`BR-SHL-025`). The
              value is the REGISTER'S, so a clerk cannot give the product a
              second answer to what kind of building this is. */}
          <SelectField
            id="nc_premise_type"
            label={t("customers.newConnect.step3.type", { defaultValue: "Premise type" })}
            value={props.draft.premise.premiseType}
            disabled={onFile}
            onChange={(premiseType) =>
              set(UNIT_LINE_HIDDEN_FOR.has(premiseType) ? { premiseType, unit: "" } : { premiseType })
            }
            placeholder={t("customers.newConnect.step3.typePlaceholder", {
              defaultValue: "Choose a premise type",
            })}
            options={typeOptions}
          />
          {/* PO 2026-09-16: *"also take premises name here"*. The column has
              always existed and nothing asked for it, so a warehouse or a
              campus had no name anywhere in the product (`DEF-CUS-5468`). */}
          <TextField
            id="nc_premise_name"
            label={t("customers.newConnect.step3.name", { defaultValue: "Premises name" })}
            value={props.draft.premise.name}
            onChange={(name) => set({ name })}
          />
        </FieldGrid>

        <div className="mt-5">
          <FieldGrid columns={2}>
            <TextField
              id="nc_address"
              // ⚠ **AN EXISTING KEY, NOT A NEW ONE WITH THE SAME WORDS.** The
              // request wizard and the add-premises wizard ask for the same
              // facts; a second key holding the same English is how one
              // product ends up with two translations of `City`.
              label={t("customers.serviceRequest.capture.streetOrPremise")}
              required
              value={props.draft.premise.address}
              onChange={(address) => {
                // Typing after a pick means the clerk is looking again, so the
                // register row comes off rather than sitting stale beside a
                // line it no longer describes.
                if (props.draft.premise.premisesId !== "") {
                  setPicked(null);
                  set({ address, premisesId: "" });
                  return;
                }
                set({ address });
              }}
              placeholder={t("customers.serviceRequest.capture.searchTheRegister")}
            />
            {/* ⚠ **ENABLED AND OPTIONAL SINCE THE 2026-09-28 DRAWING.** It was
                `disabled` with *"Named on the next step"* under it, and the PO
                asked why. The drawing's own answer: *"Unit, apt. or suite is
                enabled and optional. It is part of the postal address; unit
                labels stay on step 3."* Two sentences of six, which is what
                B14 rule 33 allows an instruction, and the second is the one a
                clerk needs — the units are still named by the pattern on step
                3 and this box does not create one. */}
            {!unitLineHidden && (
            <TextField
              id="nc_unit"
              // ⚠ **AN EXISTING KEY, NOT A NEW ONE WITH THE SAME WORDS.** The
              // request wizard already holds `Unit, apt. or suite` in all
              // eleven catalogues; minting a second key for the same English
              // is how one product ends up with two translations of one label.
              label={t("customers.serviceRequest.capture.unit")}
              value={props.draft.premise.unit}
              onChange={(unit) => set({ unit })}
              help={t("customers.newConnect.step3.unitHelp", {
                defaultValue: "Part of the mailing address. Units are named on step 3.",
              })}
            />
            )}
          </FieldGrid>
        </div>

        {/* ── WHAT THE REGISTER ANSWERED ──────────────────────────────────
            ⚠ **THIS IS HARD RULE 8 ENFORCED AT THE ONLY PLACE IT CAN BE.**
            This screen is the one door in the product that can create a SECOND
            row for a building that already has one. */}
        {props.draft.premise.premisesId !== "" && picked !== null ? (
          <div className="mt-3 flex flex-wrap items-center gap-3" data-premises-picked="">
            <Note>
              {t("customers.newConnect.step3.picked", {
                defaultValue: "On file: {{address}}",
                // B14 rule 31 — the premise NUMBER is the tenant's own series
                // and the uuid is the VALUE, which is never rendered.
                address: `${picked.premise_no ?? ""} · ${picked.address_line ?? ""}`,
              })}
            </Note>
            <Button size="sm" variant="ghost" data-premises-unpick="" onClick={unpick}>
              {t("customers.newConnect.step3.changeAddress", {
                defaultValue: "Change address",
              })}
            </Button>
          </div>
        ) : (
          searching && (
            <div className="mt-3 flex flex-col items-start gap-1" data-premises-results="">
              {premisesSearch.isFetching ? (
                <p className="text-sm text-neutral-700">{t("states.loading")}</p>
              ) : results.length === 0 ? (
                <Note>
                  {t("customers.newConnect.step3.noMatch", {
                    defaultValue: "No match. Keep typing the new address.",
                  })}
                </Note>
              ) : (
                results.map((row) => (
                  <Button
                    key={row.id}
                    size="sm"
                    variant="ghost"
                    data-premises-option={row.premise_no ?? ""}
                    onClick={() => pick(row)}
                  >
                    {`${row.premise_no ?? ""} · ${row.address_line ?? ""}`}
                  </Button>
                ))
              )}
            </div>
          )
        )}

        {/* ⚠ **READ-ONLY OVER A BUILDING ALREADY ON FILE — HARD RULE 8.** The
            town is the premises' own, walked from it; typing a different one
            here is how two rows for one building start to disagree. They
            become the clerk's again the moment they press *Change address*. */}
        <div className="mt-5" data-address-source={addressOnFile ? "premise" : "typed"}>
          <FieldGrid columns={3}>
            <TextField
              id="nc_city"
              label={t("metering.premises.field.city")}
              required
              readOnly={addressOnFile}
              value={props.draft.premise.city}
              onChange={(city) => set({ city })}
            />
            {/* ⚠ **THE DRAWING DRAWS A DROPDOWN AND THIS IS A TEXT BOX, ON
                PURPOSE.** The authority for the state list is
                `apps/tenancy/selectors.US_STATES` and NO endpoint publishes it
                to a screen, so a dropdown here would mean typing fifty states
                into this file — a third hand-typed list of a thing the server
                owns. The sibling door that also creates a property
                (`AddPremisesWizard`) draws a text box for the same reason, and
                the two doors that write one column must agree. REPORTED rather
                than guessed. */}
            <TextField
              id="nc_state"
              label={t("metering.premises.field.state")}
              required
              readOnly={addressOnFile}
              value={props.draft.premise.state}
              onChange={(state) => set({ state })}
              help={
                reasons.state === null
                  ? undefined
                  : t(reasons.state, {
                      defaultValue:
                        reasons.state === "customers.newConnect.step2.stateNotACode"
                          ? "Use a two-letter state code."
                          : "Not this utility's state.",
                    })
              }
            />
            <TextField
              id="nc_zip"
              label={t("metering.premises.field.postalCode")}
              required
              readOnly={addressOnFile}
              value={props.draft.premise.postalCode}
              onChange={(postalCode) => set({ postalCode })}
              help={
                reasons.zip === null
                  ? undefined
                  : t(reasons.zip, { defaultValue: "Five digits, or ZIP+4." })
              }
            />
          </FieldGrid>
        </div>
      </Panel>

      {/* ══════════════════ WHAT IS BUILT ═════════════════════════════════
          ⚠ **MOVED HERE FROM STEP 1 BY THE REDESIGN.** The step-1 drawing
          lists *"Scope and its three explanation lines"* under *Removed from
          this step*, and step 2 draws it as its own panel.

          ⚠ **THE THREE EXPLANATION LINES STAY DELETED.** Each said what its
          own option already says — *"A new premise — nothing is served at this
          address yet"* under an option called *A new premise* — which is B14
          rule 32, and the remainder was rationale at rule 33's zero words. The
          three CHOICES are untouched: `CONNECT_SCOPES` still names them. */}
      <Panel as="section" data-step-content="scope">
        <StepIntro
          title={t("customers.newConnect.step1.what", { defaultValue: "What is built" })}
        />
        <FieldGrid columns={2}>
          <SelectField
            id="nc_scope"
            label={t("customers.newConnect.step2.scope", { defaultValue: "Scope" })}
            required
            value={props.draft.scope}
            onChange={(scope) => props.onPatch({ scope })}
            options={CONNECT_SCOPES.map((scope) => ({
              value: scope.code,
              label: t(`customers.newConnect.scope.${scope.code}`, { defaultValue: scope.en }),
            }))}
          />
        </FieldGrid>
      </Panel>

      {/* ══════════════════ THE RECORD ════════════════════════════════════ */}
      <Panel as="section" data-step-content="record">
        <StepIntro
          title={t("customers.newConnect.step3.record", { defaultValue: "The record" })}
        />
        <FieldGrid columns={2}>
          <TextField
            id="nc_parcel"
            label={t("customers.newConnect.step3.parcel", {
              defaultValue: "Import reference",
            })}
            value={props.draft.premise.parcelRef}
            onChange={(parcelRef) => set({ parcelRef })}
          />
          {/* ⚠ **A LIST, AS DRAWN, AND ITS VALUE IS THE ROUTE'S CODE.**
              `_resolve_create_route` accepts a code or an id and B14 rule 31
              keeps the uuid off the screen. A route the list does not hold is
              KEPT rather than silently dropped — a legacy value is a fact
              about the data. */}
          <SelectField
            id="nc_route"
            label={t("customers.newConnect.step3.route", { defaultValue: "Read route" })}
            value={props.draft.premise.readRoute}
            onChange={(readRoute) => set({ readRoute })}
            placeholder={t("customers.newConnect.step3.chooseRoute", {
              defaultValue: "Choose a route",
            })}
            options={routeOptions(routesQuery.data ?? [], props.draft.premise.readRoute)}
          />
        </FieldGrid>

        {/* ══ THE BUILDING'S POINT — PO: *"you should include lat and long and
            verified tag - all these will be options"* ════════════════════ */}
        <div className="mt-5">
          <FieldGrid columns={3}>
            <TextField
              id="nc_lat"
              label={t("customers.newConnect.step3.latitude", { defaultValue: "Latitude" })}
              value={props.draft.premise.lat}
              onChange={(lat) => set({ lat })}
              numeric
            />
            <TextField
              id="nc_lng"
              label={t("customers.newConnect.step3.longitude", { defaultValue: "Longitude" })}
              value={props.draft.premise.lng}
              onChange={(lng) => set({ lng })}
              numeric
            />
            <div className="flex items-end pb-1">
              <CheckboxField
                id="nc_location_verified"
                label={t("customers.newConnect.step3.locationVerified", {
                  defaultValue: "Location verified",
                })}
                checked={props.draft.premise.locationVerified}
                onChange={(locationVerified) => set({ locationVerified })}
              />
            </div>
          </FieldGrid>
        </div>

        {/* ⚠ **`BR-MET-1162`'s SCREEN OBLIGATION, IN FIVE WORDS.** *A unit may
            carry its own `lat`/`lng`, and where it does those are the truth
            for that unit* — so **every screen showing a point says which of
            the two it is showing**. This one only ever shows the building's.
            The drawn sentence *"The point is the building's. A unit may carry
            its own later; every screen says which one it shows."* is 20 words
            and its second half is RATIONALE, which rule 33 removes rather than
            shortens. What is left is the required FACT. */}
        <Note className="mt-3" data-point-belongs-to="premise">
          {t("customers.newConnect.step3.pointIsBuilding", {
            defaultValue: "This point is the building's.",
          })}
        </Note>

        {pickedId === "" ? (
          <CustomFieldsInput
            entity="premises"
            screen="NEW_CONNECTION_PREMISE"
            values={props.draft.premise.customData ?? {}}
            onChange={(customData) => set({ customData })}
          />
        ) : (
          <CustomFieldsView
            entity="premises"
            screen="NEW_CONNECTION_PREMISE"
            values={pickedDetail.data?.custom_data ?? {}}
            formatDate={(iso) => iso}
          />
        )}

        {/* ONE SOURCE, ECHOED, NEVER RE-ENTERED. ⚠ This read *"Owner: {{owner}}
            — taken from step 1, where it is entered once. Change it there and
            it changes here."* until 2026-09-16; every word after the name was
            RATIONALE (`DEF-CUS-5470`). */}
        <Note className="mt-2 max-w-measure">
          {t("customers.newConnect.step3.owner", {
            defaultValue: "Owner: {{owner}}",
            owner:
              props.draft.owner.name.trim() === ""
                ? t("customers.newConnect.step3.ownerMissing", {
                    defaultValue: "not entered yet",
                  })
                : props.draft.owner.name.trim(),
          })}
        </Note>
      </Panel>

      {/* ══════════════════ SERVICES AND PLAN ═════════════════════════════
          Both live in one Panel because the coverage check below is a
          statement about the PAIR of them. */}
      <Panel as="section" data-step-content="services-and-plan">
        <StepIntro
          title={t("customers.newConnect.step3.serviceAndPlan", {
            defaultValue: "Services and plan",
          })}
        />

        <FieldGrid columns={2}>
          {/* The tenant's OWN enabled services, chips + a type-to-filter add
              control (B14 rule 9). Never a list typed into this file. */}
          <ServicesAvailableField
            value={props.draft.premiseServices}
            onChange={(premiseServices) => props.onPatch({ premiseServices })}
          />
          {plansQuery.isError ? (
            <RefusalStrip data-plans="unavailable">
              {t("customers.newConnect.step3.plansFailed", {
                defaultValue: "Plans could not be loaded. The coverage check cannot run.",
              })}
            </RefusalStrip>
          ) : (
            <SelectField
              id="nc_plan"
              label={t("customers.newConnect.step3.plan", { defaultValue: "Plan" })}
              required
              value={props.draft.planApartments}
              onChange={(planApartments) => props.onPatch({ planApartments })}
              placeholder={t("customers.newConnect.step3.choosePlan", {
                defaultValue: "Choose a published plan",
              })}
              // B14 rule 31 — the plan's NAME is what is shown; its id is the
              // VALUE and is never rendered.
              options={plans.map((plan) => ({ value: plan.id, label: plan.name }))}
            />
          )}
        </FieldGrid>

        {/* ── THIS PLAN — `DEF-CUS-9821`, PO 2026-10-06, redrawn to the approved
            drawing: the summary, a warning only when true, Base charges and
            Usage rates open, the other five closed with a one-line summary.
            ⚠ **IT CARRIES NO MONTHLY TOTAL**, as before: hard rule 2 rounds
            money once, on the server, and nothing here adds a figure up. The
            old *WON'T COVER* line is the block's own *"not in this plan"*
            warning now, so it is not said twice. */}
        {chosenPlan !== null && (
          <div data-plan-summary={chosenPlan.code}>
            {planDetail.isError ? (
              <RefusalStrip className="mt-5" data-plan-detail="unavailable">
                {t("customers.newConnect.step3.planDetailFailed", {
                  defaultValue: "Plan details could not be loaded.",
                })}
              </RefusalStrip>
            ) : planDetail.data === undefined ? null : (
              <ThisPlanBlock
                planId={chosenPlan.id}
                detail={planDetail.data.detail}
                sections={planDetail.data.sections}
                services={props.draft.premiseServices}
                className={ownerClassName}
                t={t}
              />
            )}
          </div>
        )}
      </Panel>
    </>
  );
}

/**
 * The route list as options, with a stored code the list does not hold KEPT
 * rather than silently replaced — a legacy value is a fact about the data, and
 * dropping it would blank a route a clerk had already chosen.
 */
export function routeOptions(
  routes: readonly { id: string; code: string; name: string | null }[],
  current: string,
): { value: string; label: string }[] {
  const options = routes.map((row) => ({
    value: row.code,
    label: row.name === null || row.name === "" ? row.code : `${row.code} · ${row.name}`,
  }));
  const trimmed = current.trim();
  if (trimmed !== "" && !options.some((option) => option.value === trimmed)) {
    options.push({ value: trimmed, label: trimmed });
  }
  return options;
}
