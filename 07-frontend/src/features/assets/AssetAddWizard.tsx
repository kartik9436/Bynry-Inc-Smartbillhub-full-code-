// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-002 (add asset — SHAPE AMENDED at build per §10-D8: the
//           ratified single modal becomes r10's 4-step wizard) · US-AST-004
//           (extended spec capture)   Screens: S51 / AST-05.1–4 (`/assets/new`)
// Change:   CR-028 AST-W4 T1 (B16 §5.2 + Item 1d's flows table + §10-D8 —
//           "restructure to the wizard now" — and the not-modal amendment:
//           "as per r10 - it is not modal"). Steps per the AST-05 extraction:
//           1 Identity · 2 Specification · 3 Assignment · 4 Lifecycle.
//           ⚠ **FIVE STEPS SINCE 2026-09-13** — `5 Review` is screen 32 of
//           `05-prototype/01 Assets Menu Blueprint.pdf` (pages 120–121, figure
//           49), which every figure in section 06 has always drawn on the rail
//           and which the code did not have. See `ADD_STEP_COUNT`.
// Drawing:  blueprint section 06, pages 108–124 — screens 28 Identity ·
//           29 Specification · 30 Assignment · 31 Lifecycle · 32 Review & add.
//           Rendered as IMAGES at scale 2 (page 109 at scale 4) with
//           `10-scripts/pdf/pdf_render.py` and read with eyes, per B14 rule 42
//           (PO 2026-09-13: *"dont create screens using only Text"*). The
//           measured gap list is `04-docs/05-modules/05-assets/blueprint/
//           05-add-wizard.md`; screen 33 (Drafts) is NOT built here and needs a
//           `WIZARD_PARK_FLOWS` migration before it can be.
// Rules:    BR-AST-026/033 (numbering: series suggestion via the W4 number-
//           preview PEEK + the UNIQUE availability callout; duplicate # is a
//           hard block, duplicate serial warns) · BR-AST-003 (a sub-meter
//           REQUIRES an existing ACTIVE master) · BR-AST-009/010 (service +
//           explicit UoM for measuring kinds; net metering locked for net
//           meters, refused on devices) · BR-AST-011 (assign-on-create vs
//           leave-in-inventory) · BR-AST-044 (meter_type on measuring kinds
//           only) · BR-AST-047 (step 4's valuation capture — all optional) ·
//           BR-AST-027 (blank cadence → the type's seeded default) ·
//           §10-D3 (NO GL sentence anywhere — r10's "Posts to 5300 O&M on
//           install" summary line is OMITTED) · §10-D7 ("Work R5") ·
//           BR-SHL-018/019 (wizard nav + ONE transactional commit)
// ───────────────────────────────────────────────────────
// AST-05 — Add an asset, the full-page 4-step wizard.
//
// Honest absences, each stated rather than smoothed over (the final report
// carries them; the summary of divergences from r10's own markup):
//   · **Demand flag** — r10 draws "Demand register — records peak as well as
//     consumption"; NO column exists for it, so NOTHING renders (the lane
//     instruction's own rule: no column → render nothing and report).
//   · **Opening read** — capturing one at create would write a meter_reads
//     row, and no published seam lets assets do that at create time. The
//     field renders DISABLED with the reason, per the lane instruction.
//   · **Read route / sequence** — no columns exist; omitted and reported.
//   · **Warranty term select** — no term column exists; the stored fact is
//     `warranty_end`, so a DATE field renders instead (reported).
//   · **Service checkboxes** — r10 draws multi-select services; the schema
//     stores ONE service per asset (its service point), so one entry renders
//     (the shipped modal's own posture, reported with it).
//   · **Summary "Cost · Posts to 5300 O&M on install"** — OMITTED: only the
//     ledger posting service may name a GL account (hard rule 5 / §10-D3).
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createAsset,
  getAssetNumberPreview,
  getAssets,
  getLookupEntries,
  getPremises,
  getTenantServices,
  getUnits,
} from "@/api/endpoints";
import type { AssetRow, AssetTab, LookupEntry, UnitRow } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { enabledServiceRows } from "@/features/metering/ServicesAvailableField";
import {
  CheckboxField,
  DatePickerField,
  FieldErrorsScope,
  SearchSelectField,
  SegmentedField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { CustomFieldsAnswers, CustomFieldsInput, customFieldErrors } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { Chip } from "@/components/Chip";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { formatDate } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardExit, WizardNavState } from "@/components/WizardFrame";
import { useToast } from "@/components/Toast";
import { Note } from "@/components/TextBits";
import { premisesPickerOptions } from "@/features/metering/UnitsListPage";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { RaiseWorkOrderCheckbox } from "./AssetFlowPages";
import { raiseWorkOrderPath } from "./RaiseWorkOrderPage";
import { unitPickerOptions } from "./AssetLifecycleModals";
/**
 * `AST-B-27`'s four allocation methods — **IMPORTED, NOT RE-DECLARED.**
 *
 * The drawing puts allocation on this wizard AND on `Edit · Measurement`
 * (screen 17), so there were two writers from the first day and two lanes
 * building them in the same hour. **Both wrote the list.** Wave C lane 1's
 * landed first (`AssetPanelEdits.tsx`, `2.237.8`), so this file consumes it and
 * the second copy is deleted rather than kept in step.
 *
 * ⚠ **A SECOND HAND-TYPED COPY IS THE FAILURE CLAUDE.md's HARD-WON LAW 2 NAMES
 * BY EXAMPLE**: the utility-service list is typed out in two places, and that is
 * exactly why `fire` — the eleventh service — *"does not appear on screen on its
 * own and it fails SILENTLY"*. Four codes that agree today is not the same thing
 * as one list, and the day a fifth method is ratified only one of the two copies
 * gets it.
 */
import { ALLOCATION_RULES } from "./AssetPanelEdits";
import { typesForTab } from "./AssetRegistryPage";
import {
  ASSETS_ROUTE,
  ASSET_TAB_IDS,
  assetDetailPath,
  isMeasuringCategory,
  offersConnectionSize as sizeIsOfferedFor,
  sizeOptionsForService,
} from "./assetsShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

export const CLASS_PARAM = "class";
export const STEP_PARAM = "step";
/**
 * ⚠ **FIVE, NOT FOUR — SCREEN 32 (`Add an asset · 5 Review & add`), BLUEPRINT
 * PAGES 120–121, FIGURE 49.**
 *
 * Section 06's own head reads *"the four steps and the commit"* and **every
 * figure in the section draws a FIVE-box rail** — `1 Identity › 2 Specification
 * › 3 Assignment › 4 Lifecycle › 5 Review`. This constant said `4`, so
 * `WizardFrame` treated **Lifecycle** as the final step and drew `Add asset ✓`
 * on a form. A clerk committed the one write in the whole flow while looking at
 * eight input boxes and a four-line summary, where the drawing gives them four
 * read-only panels of about fourteen facts, grouped the way the asset's own
 * Overview groups them — *"so a person reviews in the shape they will later
 * read"* (p121).
 *
 * **Nothing else moved to build it.** `POST /assets` is unchanged, `WizardFrame`
 * already takes any step count and already renders the final ✓, and every fact
 * the review shows was already in `AddWizardValues`. The document's own
 * *Walked* row says as much: *"this screen is not drawn anywhere in this
 * document today, and that is the finding … The four steps were drawn and the
 * commit was not."*
 */
export const ADD_STEP_COUNT = 5;

/** BR-SHL-011's spirit: an unknown `?class=` falls back, it never errors. */
export function classFromParam(raw: string | null): AssetTab {
  return (ASSET_TAB_IDS as readonly string[]).includes(raw ?? "") ? (raw as AssetTab) : "meters";
}

export function stepFromParam(raw: string | null): number {
  const parsed = Number(raw ?? "1");
  if (!Number.isInteger(parsed)) {
    return 1;
  }
  return Math.min(Math.max(1, parsed), ADD_STEP_COUNT);
}

export interface AddWizardValues {
  /** `CR-161-BRC10` W3 · `DEF-AST-9171` — the tenant's own asset fields placed
   *  Input on Add asset. Optional so every existing fixture stays whole. */
  custom_data?: CustomFieldValues;
  /** The work-order pre-tick. FALSE by default — raising a job is a choice a
   *  clerk makes, and a default-on checkbox would put a van on the road for
   *  every meter a utility ever adds. Not sent to the server: it decides where
   *  the wizard GOES after the asset is created, and nothing else. */
  raise_work_order: boolean;
  klass: AssetTab;
  asset_no: string;
  type: string;
  read_method: string;
  service: string;
  /**
   * **`AST-B-27`'s third column with a reader and no writer — the utility's own
   * legacy or third-party number** (`BR-AST-049`). Drawn on step 1 of screen 28
   * (figure 43) and again in the review's Identity panel (figure 49), accepted
   * by `POST /assets` since the column landed, and until now typed NOWHERE in
   * the wizard: the only way to record one was to create the asset and come
   * back to its Device edit dialog. The blueprint's own argument is that it is
   * a fact a person HOLDS while booking the thing in, with the paperwork in
   * their hand.
   *
   * ⚠ **NOT OFFERED ON A SUB-METER, AND THAT IS THE DRAWING RATHER THAN A
   * RULE.** Figure 43 (meter) draws it; figure 44 (sub-meter) does not, and
   * the two figures are the class VARIANTS of one screen — which is how this
   * document draws a per-class difference (Parent master appears only on 44).
   * B14 rule 37 says build the shape the frames agree on, so it is built where
   * a frame shows it and withheld where one deliberately does not. **Whether a
   * sub-meter should be offered one is a question, not a decision** — see the
   * lane report; nothing here answers it.
   */
  external_ref: string;
  parent_asset_no: string; // sub-meters: REQUIRED (BR-AST-003); devices: link
  // step 2 — measuring
  manufacturer: string;
  model: string;
  /**
   * `form_class` and `seal_no` — two more of the same family, drawn on BOTH
   * spec variants (figures 45 and 46) and marked **NEW** on each. The drawing
   * makes its own case for the seal in four words: *"a seal is fitted at
   * installation"*, which is this screen and not a later one.
   */
  form_class: string;
  seal_no: string;
  multiplier: string;
  register_digits: string;
  unit: string; // explicit UoM (CLAUDE.md #3)
  serial_no: string;
  firmware_version: string;
  meter_type: string;
  /**
   * BR-AST-500 / BR-AST-530 — the SERVICE CONNECTION's size class. `""` means
   * "not recorded", which is LAWFUL and is what a first migration mostly holds
   * (PO ruling 2026-08-28, judgment 2).
   *
   * ⚠ **THIS SAID "METERS ONLY" UNTIL 2026-09-01 (DEF-2414).** Judgment 4's
   * boundary is now `offersConnectionSize` — an asset that stands ON a service
   * connection, which is a meter OR a non-measuring asset that declares a
   * service, and never a sub-meter. A trash cart is the case that moved it:
   * it is the equipment a trash connection IS, and no surface could record its
   * size.
   */
  size_class: string;
  /**
   * `AST-B-14` (PO 2026-09-12) — the reading on the dial the day the meter goes
   * in, and its date. **NEITHER IS A COLUMN ON `assets`**: both are handed to
   * metering, which writes one `meter_reads` row inside the create's own
   * transaction, and the asset is not created if that write is refused.
   *
   * ⚠ **THEY LIVE ON STEP 2 AND NOT STEP 3**, which is the whole of the
   * ruling: *"Build it as drawn - move it to step 2, beside the multiplier,
   * register digits and the warning"*. A reading means nothing without the
   * multiplier and the register digits that are asked for two fields up, and
   * the ×10 warning on this step is the sentence that says why.
   *
   * ⚠ **`opening_read_date` IS LEFT BLANK ON PURPOSE AND DEFAULTED SERVER
   * SIDE.** The drawing's own helper is *"Defaults to the install date"* — and
   * the install date is chosen on the NEXT step, so a client-side default
   * would have to guess forward or re-write itself when step 3 is answered.
   * `_capture_opening_read` applies the default instead, so the wizard and a
   * direct API call cannot disagree about what a dateless reading means.
   */
  opening_read: string;
  opening_read_date: string;
  /**
   * `AST-B-27` (PO 2026-09-12, *"this is correct - build it"*) — **SUB-METERS
   * ONLY.** A sub-meter created today is *metered, not allocated*, permanently:
   * the two columns exist, `POST /assets` accepts both, and no screen in the
   * product could ever put a value in either. That is hard-won law 2's third
   * form — a column with a reader and no writer.
   *
   * `allocation_share_pct` is a percentage of the master (0-100, refused above
   * 100 by name server-side). Blank is lawful and means *metered, not
   * allocated*, which is why neither field is required.
   */
  allocation_share_pct: string;
  allocation_rule: string;
  net_metering: boolean; // r10's "Bidirectional" flag
  // step 2 — devices
  export_capacity_kw: string;
  test_interval_months: string;
  // step 3
  destination: "inventory" | "unit";
  premises_id: string;
  unit_id: string;
  install_date: string;
  /**
   * **Where a technician will actually find it** — figure 47, full width,
   * marked NEW. It is a LOCATION NOTE and never an address: hard rule 8 puts
   * the address on `premises` and every other entity walks to it, and p118's
   * *Words* row says so in the drawing's own voice.
   */
  location_note: string;
  // step 4 (BR-AST-047 — all optional)
  supplier: string;
  purchase_cost: string;
  purchase_date: string;
  warranty_end: string;
  expected_life_years: string;
  certification_due: string;
}

export function initialAddValues(klass: AssetTab): AddWizardValues {
  return {
    // FALSE by default — see the field's own comment on `AddWizardValues`.
    raise_work_order: false,
    klass,
    asset_no: "",
    type: "",
    read_method: "",
    service: "",
    external_ref: "",
    parent_asset_no: "",
    manufacturer: "",
    model: "",
    form_class: "",
    seal_no: "",
    multiplier: "1",
    register_digits: "",
    unit: "",
    serial_no: "",
    firmware_version: "",
    meter_type: "",
    size_class: "",
    opening_read: "",
    opening_read_date: "",
    allocation_share_pct: "",
    allocation_rule: "",
    net_metering: false,
    export_capacity_kw: "",
    test_interval_months: "",
    destination: "inventory",
    premises_id: "",
    unit_id: "",
    install_date: "",
    location_note: "",
    supplier: "",
    purchase_cost: "",
    purchase_date: "",
    warranty_end: "",
    expected_life_years: "",
    certification_due: "",
  };
}

/**
 * Has anybody answered anything yet? `DEF-MET-4983`'s *"when the form is
 * untouched"*, written as a comparison against the baseline rather than as a
 * flag — a flag is state, and state is exactly what a reload destroys, so it
 * would answer `false` on the one run this question exists for.
 *
 * `klass` comes from the address and is therefore never an answer; everything
 * else is compared field by field against what the form starts with.
 */
export function isUntouched(values: AddWizardValues, klass: AssetTab): boolean {
  const base = initialAddValues(klass);
  return (Object.keys(base) as (keyof AddWizardValues)[]).every(
    (key) => key === "klass" || values[key] === base[key],
  );
}

/**
 * Per-step validity — the WizardFrame blocks Continue on false and answers at
 * the button (DEF-178). The SERVER re-checks every one of these; a passing
 * step is convenience, never the law.
 */
/**
 * Does the SERVER refuse this asset without a service? **BR-AST-009**, mirrored
 * from `_check_measuring_requirements` (`apps/assets/services.py:961-978`),
 * which refuses every MEASURING type by name and lets a non-measuring device
 * through with none.
 *
 * ⚠ **THE STEP DID NOT ASK AND THE SERVER DID (`DEF-MET-4981`).** Driven: a
 * meter with Service empty walked all four steps — Continue was never
 * `disabled` and never `aria-disabled` — and `POST /assets` answered **422
 * `assets.service_required`** on step 4, three steps from the empty field. The
 * refusal named the field and not the step, and its verb was *Choose*, for a
 * control that offered nothing to choose from.
 *
 * The predicate is the CATEGORY, never a list of type codes, for the reason
 * `offersConnectionSize` gives one function up: a fourth copy of "which kinds
 * measure" is a fourth place to be wrong about the next one.
 */
export function requiresService(klass: AssetTab): boolean {
  return isMeasuringCategory(klass);
}

export function stepValid(step: number, values: AddWizardValues): boolean {
  const measuring = isMeasuringCategory(values.klass);
  if (step === 1) {
    if (values.type.trim() === "") {
      return false;
    }
    // BR-AST-009 — see `requiresService`. The server refuses this and used to
    // refuse it on step 4.
    if (requiresService(values.klass) && values.service.trim() === "") {
      return false;
    }
    // BR-AST-003: a sub-meter without its master is refused server-side; the
    // step refuses first, naming the field.
    if (values.klass === "sub_meters" && values.parent_asset_no.trim() === "") {
      return false;
    }
    return true;
  }
  if (step === 2 && measuring) {
    // BR-AST-009 / CLAUDE.md #3: explicit UoM + positive multiplier.
    return values.unit.trim() !== "" && values.multiplier.trim() !== "";
  }
  if (step === 3) {
    // `AST-B-14` — A READING WITH NO DATE ANYWHERE IS REFUSED HERE, NOT ON
    // STEP 4. `_capture_opening_read` defaults the read date to the INSTALL
    // date and refuses when there is neither, and the destination chosen on
    // this step is what decides whether an install date exists at all: an
    // asset left in inventory needs none.
    //
    // ⚠ **THIS IS `DEF-MET-4981`'s SHAPE AND IT WAS FOUND IN A BROWSER, NOT IN
    // A TEST.** Without this clause a clerk types a dial reading on step 2,
    // leaves the meter in inventory, walks two more steps and meets the
    // server's refusal on the COMMIT — the exact defect this wizard was fixed
    // for a day earlier, one field along. The step that can repair it is this
    // one, because the install date is on it.
    if (openingReadNeedsADate(values)) {
      return false;
    }
  }
  if (step === 3 && values.destination === "unit") {
    // BR-AST-011: assign-on-create needs the seat and its install date.
    return values.unit_id !== "" && values.install_date !== "";
  }
  return true;
}

/**
 * `AST-B-14` — is there a reading with no date to place it on?
 *
 * The server's own rule, mirrored so the person is told BEFORE a round trip
 * rather than after one; `_capture_opening_read` stays authoritative either way.
 * **Guessing today is what this refuses to do** — it would date a meter's first
 * reading to whenever somebody happened to type it, and a first reading is the
 * baseline every later bill measures from.
 */
export function openingReadNeedsADate(values: AddWizardValues): boolean {
  return (
    values.opening_read.trim() !== "" &&
    values.opening_read_date === "" &&
    values.install_date === ""
  );
}

/**
 * Does this asset stand ON a service connection, so that a connection size is
 * a fact about it? **BR-AST-530 as AMENDED 2026-09-01 (DEF-2414).**
 *
 * BR-AST-530's judgment 4 was METERS ONLY, and its stated reason is about
 * POSITION rather than about measurement: *"a sub-meter sits BEHIND a service
 * connection rather than on one"*. A container cart sits ON one — it is the
 * equipment the trash connection IS — so the original reason includes it and
 * the original wording excluded it, which is what the PO ruled on:
 * *"we will ahve to set in seeder as well as in setting the sizes also on
 * Units"*, confirmed the same day as *"this is correct - The size stays on the
 * equipment record, not on the unit itself."*
 *
 * **The predicate is DECLARING A SERVICE, not being a container.** A cart
 * declares `service: trash`; a backflow preventer, an EV charger and a comms
 * endpoint declare none (BR-AST-009 — a non-measuring device belongs to a
 * customer, not to a connection) and are offered nothing. Naming the type
 * instead would put `container_cart` in a fourth place and would answer wrongly
 * for the next non-measuring thing that stands on a connection — storm water's
 * and broadband's equipment, both `capacity` services under the PO ruling of
 * 2026-09-01 (DEF-2409).
 *
 * ⚠ **SUB-METERS ARE STILL EXCLUDED and nothing about judgment 4's reason
 * moves**: they are a measuring class, so they never reach this predicate at
 * all — the meters branch keeps its own `klass === "meters"` test.
 */
export function offersConnectionSize(values: AddWizardValues): boolean {
  return sizeIsOfferedFor(values.klass, values.service);
}

/** The create payload — nothing collected is dropped, nothing empty is sent. */
export function addPayload(values: AddWizardValues): Record<string, unknown> {
  const measuring = isMeasuringCategory(values.klass);
  const payload: Record<string, unknown> = { type: values.type };
  const text = (key: keyof AddWizardValues) => {
    const value = (values[key] as string).trim();
    if (value !== "") {
      payload[key] = value;
    }
  };
  text("asset_no");
  text("serial_no");
  text("manufacturer");
  text("model");
  text("firmware_version");
  // ⚠ **FOUR COLUMNS THAT COULD BE READ AND NOT WRITTEN, NOW WRITTEN AT ADD.**
  // Every one was already on the `known` list of `_validate_asset`
  // (`apps/assets/services.py:646, 670, 673, 677`) — `external_ref`,
  // `form_class`, `seal_no`, `location_note` — so **no plumbing moved for any
  // of them**; the fields simply did not exist on this form. `text()` sends
  // nothing at all for a blank, which is what a create wants: there is no
  // stored value to clear.
  text("external_ref");
  text("form_class");
  text("seal_no");
  text("location_note");
  if (values.read_method !== "") {
    payload.read_method = values.read_method;
  }
  if (values.service.trim() !== "") {
    payload.service = values.service.trim();
  }
  if (values.parent_asset_no !== "") {
    payload.parent_asset_no = values.parent_asset_no;
  }
  if (measuring) {
    payload.unit = values.unit;
    payload.multiplier = values.multiplier;
    if (values.register_digits.trim() !== "") {
      payload.register_digits = values.register_digits.trim();
    }
    if (values.meter_type !== "") {
      payload.meter_type = values.meter_type;
    }
    // BR-AST-530 (PO 2026-08-28, *"Please do both"*) — the size travels only
    // for a METER. A sub-meter sits behind a service connection rather than on
    // one, and widening that is DEF-1901's call; the control below is not even
    // rendered on the sub-meters tab, so the only way to reach this line with a
    // value is a stale form.
    //
    // ⚠ An EMPTY size sends NOTHING rather than `null`. Blank means "we have
    // not recorded one" (BR-AST-500) and that is the state a new meter starts
    // in — there is nothing to clear on a create.
    if (values.klass === "meters" && values.size_class !== "") {
      payload.size_class = values.size_class;
    }
    if (values.net_metering || values.type === "net_meter") {
      payload.net_metering = true;
    }
    // `AST-B-14` — the opening read travels as TWO non-column keys. Empty
    // sends NOTHING at all rather than `""`: a blank reading is a first-class
    // answer (*"Blank starts billing from zero"*) and not a value to clear, and
    // the server's own guard is `raw is None or str(raw).strip() == ""`.
    //
    // ⚠ **THE DATE RIDES ONLY WITH A VALUE.** A date on its own describes a
    // reading nobody took, and `_capture_opening_read` returns before it ever
    // looks at the date — so sending one alone would be a field the server
    // silently ignores, which is how a person comes to believe they set
    // something.
    if (values.opening_read.trim() !== "") {
      payload.opening_read = values.opening_read.trim();
      if (values.opening_read_date !== "") {
        payload.opening_read_date = values.opening_read_date;
      }
    }
    // `AST-B-27` — allocation is a fact about a SUB-METER and about nothing
    // else. The boundary is the same predicate the control renders on, which is
    // what BR-AST-530's judgment 4 asked of the size class one field up: two
    // halves that cannot drift, because they are one test.
    if (values.klass === "sub_meters") {
      if (values.allocation_share_pct.trim() !== "") {
        payload.allocation_share_pct = values.allocation_share_pct.trim();
      }
      if (values.allocation_rule !== "") {
        payload.allocation_rule = values.allocation_rule;
      }
    }
  } else {
    if (values.export_capacity_kw.trim() !== "") {
      payload.export_capacity_kw = values.export_capacity_kw.trim();
    }
    // BR-AST-530 as AMENDED 2026-09-01 (DEF-2414) — see `offersConnectionSize`.
    // The boundary is the SAME predicate the control renders on, so the two
    // halves cannot drift, which is the property judgment 4 asked for.
    if (offersConnectionSize(values) && values.size_class !== "") {
      payload.size_class = values.size_class;
    }
    // Plan U10 — a device's own unit; blank lets the server stamp the default.
    if (offersConnectionSize(values) && values.unit.trim() !== "") {
      payload.unit = values.unit.trim();
    }
  }
  if (values.test_interval_months !== "") {
    payload.test_interval_months = values.test_interval_months;
  }
  if (values.destination === "unit" && values.unit_id !== "") {
    payload.unit_id = values.unit_id; // BR-AST-011: assign-on-create
    payload.install_date = values.install_date;
  } else if (values.install_date !== "") {
    payload.install_date = values.install_date;
  }
  // step 4 — BR-AST-047's valuation capture, all optional.
  text("supplier");
  text("purchase_cost");
  text("purchase_date");
  text("warranty_end");
  text("expected_life_years");
  text("certification_due");
  // `CR-161-BRC10` W3 — sent only when something was typed.
  if (Object.keys(values.custom_data ?? {}).length > 0) {
    payload.custom_data = values.custom_data;
  }
  return payload;
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface AssetAddWizardProps extends RegionalProps {
  client?: ApiClient;
  today?: string;
}

export function AssetAddWizard(props: AssetAddWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  // `timeZone` joins `dateFormat` for the review step, which READS dates back
  // rather than collecting them — `formatDate` needs both (IS-8 / BR-SHL-023).
  const { dateFormat, timeZone } = useRegional(props);
  const today = props.today ?? "";

  const klass = classFromParam(searchParams.get(CLASS_PARAM));
  const step = stepFromParam(searchParams.get(STEP_PARAM));
  const nav: WizardNavState = { step, reached: step };
  // `CR-161-BRC10` W3 — a refused custom field's sentence, on its control.
  const [customErrors, setCustomErrors] = useState<Record<string, string>>({});
  const [values, setValues] = useState<AddWizardValues>(() => initialAddValues(klass));
  const [createdWarningsShown, setCreatedWarningsShown] = useState(false);

  // ── `DEF-MET-4983` — THE STEP SURVIVES A RELOAD AND THE ANSWERS DO NOT ────
  //
  // The step is URL state and the values are `useState`, so the two survive a
  // reload differently. Driven: typed an asset #, a type and a service, pressed
  // Continue, reloaded — the URL came back `&step=2`, the page drew step 2, and
  // step 1 held `asset_no ""`, `type ""`, `service ""`. **Every answer gone, no
  // banner, nothing on screen saying so.** The same split renders `?step=5` and
  // `?step=9` as step 4 while the address goes on claiming 5 and 9, because
  // `stepFromParam` clamps the value it USES and never rewrites the address.
  //
  // So: a step past the first, over a form nobody has touched, is not honoured.
  // The person lands on step 1 and the frame says why. That is the second of
  // the two remedies `DEF-MET-4983` names; the first is to persist the answers,
  // which is `AST-B-28` (Save as draft) and is not in this wave — and when it
  // lands, a resume carries values with its `?step=`, so this effect will not
  // see an untouched form and will not fire.
  //
  // ⚠ **`untouched` IS COMPARED AGAINST THE BASELINE, NOT AGAINST A FLAG.** A
  // "has the user typed" boolean is another piece of state a reload destroys —
  // it would answer `false` on exactly the run this exists for.
  const [restarted, setRestarted] = useState(false);
  const initialStepParam = useRef(searchParams.get(STEP_PARAM));
  useEffect(() => {
    const raw = initialStepParam.current;
    initialStepParam.current = "1"; // once, on the first mount only
    if (raw === null || raw === "1") {
      return;
    }
    if (!isUntouched(values, klass)) {
      return;
    }
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, "1");
    setSearchParams(params, { replace: true });
    setRestarted(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount only, by design
  }, []);

  function setStep(next: WizardNavState): void {
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  function switchClass(next: AssetTab): void {
    const params = new URLSearchParams(searchParams);
    params.set(CLASS_PARAM, next);
    params.set(STEP_PARAM, "1"); // a different class restarts the flow
    setSearchParams(params, { replace: true });
    // A different class is a different field set — type/spec entries are
    // about a kind no longer chosen and must not linger.
    setValues({ ...initialAddValues(next), asset_no: values.asset_no });
  }

  const typesQuery = useQuery({
    queryKey: ["lookups", "asset_types"],
    queryFn: () => getLookupEntries("asset_types", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const readMethodsQuery = useQuery({
    queryKey: ["lookups", "read_methods"],
    queryFn: () => getLookupEntries("read_methods", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const meterTypesQuery = useQuery({
    queryKey: ["lookups", "meter_types"],
    queryFn: () => getLookupEntries("meter_types", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // BR-AST-530 — the tenant's own ratified connection sizes (BR-TEN-170/171).
  // `per: 200` and not 100: BR-TEN-171 ratified FORTY rows on 2026-08-27 and a
  // tenant provisioned before that carries an orphan `E-3P` on top (BR-TEN-071
  // deletes from nobody), so the page size has to clear the ratified count with
  // room — the same reason `RateScheduleWizard` reads this list at 200.
  //
  // ⚠ **THIS COMMENT SAID THE LIST IS UNSCOPED *ON PURPOSE* AND THAT IS NO
  // LONGER TRUE (CR-065, 2026-09-02).** It read: *"BR-TEN-078 ruled this list is
  // NOT service-scoped … filtering here would quietly re-scope a list the PO
  // twice said to leave alone"*, and it was correct until the PO reversed that
  // ruling for this one list — *"in Setting a capacity needs to tags to utility
  // services ."*, sent with a screenshot of the FIRE rate schedule offering
  // *Electric CT-metered*. Every size class now names its service.
  //
  // ⚠ **AND THIS PICKER IS STILL UNFILTERED, WHICH IS A KNOWN GAP AND NOT A
  // DECISION: `DEF-3300`.** CR-065 filtered the two RATE screens the PO
  // photographed. Doing the same here needs an answer this lane does not have —
  // an asset being EDITED may already hold a size from another service, and
  // dropping it from the picker would silently change what the form saves. The
  // rate screens solve that by keeping whatever the schedule already prices
  // (`sizeClassesForService`); the equivalent here is one stored value rather
  // than a list, and it is filed rather than guessed at.
  const sizeClassesQuery = useQuery({
    queryKey: ["lookups", "service_size_classes"],
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // ⛔ `AST-B-03` / `DEF-MET-4980` — THE TENANT'S ENABLED SERVICES, and this
  // query is the whole fix.
  //
  // The field below was an `<input type="text">` with no placeholder and no
  // datalist, so a clerk typed a code from memory against a list the screen
  // never showed; a walk of all four steps issued twelve API calls and none of
  // them asked what the list was. `brazosbend` enables two of the eleven
  // platform services, so the picker offers TWO — and `watr` reaches the server
  // and comes back 422 three steps later.
  //
  // ⚠ **AN ARRAY HERE WOULD HAVE BEEN THE THIRD HAND-TYPED SERVICE LIST.**
  // `SignupWizard.tsx` and `ratingShared.tsx` each carry one, which is why
  // `fire` — the eleventh service — *"does not appear on screen on its own and
  // it fails SILENTLY"* (CLAUDE.md, hard-won law 2). This file had ZERO
  // hardcoded service codes and it keeps zero.
  //
  // ⚠ **AND `GET /settings/services` IS NOT System-Admin-only**, which two
  // comments in this feature said for three weeks (`DEF-MET-4982`). It is
  // `AnyTenantRole` — `apps/tenancy/api.py:419`, commented *"clerks read-only;
  // writes below"*. `retry: false` and the shared reference staleness are the
  // registry's own posture one click away (`AssetRegistryPage.tsx:504-510`): a
  // role that cannot read it gets no options, never a spinner.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const premisesQuery = useQuery({
    queryKey: ["premises", "asset-add-picker"],
    queryFn: () => getPremises({ per: 500 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const unitsQuery = useQuery({
    queryKey: ["units", "asset-add-picker"],
    queryFn: () => getUnits({ per: 500 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // Parent masters (BR-AST-003) and device links — the meters-tab rows.
  const metersQuery = useQuery({
    queryKey: ["assets", "add-parent-picker"],
    queryFn: () => getAssets({ per: 500, filters: { tab: "meters" } }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
    enabled: klass !== "meters",
  });
  // BR-AST-026/033: the series suggestion + availability — a PEEK, debkeyed
  // on what was typed so the answer is about THIS number.
  const numberQuery = useQuery({
    queryKey: ["assets", "number-preview", values.type || klass, values.asset_no],
    queryFn: () =>
      getAssetNumberPreview(
        { type: values.type || undefined, asset_no: values.asset_no || undefined },
        client,
      ),
    staleTime: 30 * 1000,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () => createAsset(addPayload(values), client),
    onSuccess: () => setCreatedWarningsShown(false),
  });

  async function commit(): Promise<WizardCommitOutcome> {
    try {
      const created = await create.mutateAsync();
      fireToast(t("assets.toast.created"));
      // BR-AST-033: a duplicate SERIAL is warn-but-allow — the warning travels
      // with the toast since this page navigates away on success.
      if (!createdWarningsShown && (created.warnings ?? []).length > 0) {
        setCreatedWarningsShown(true);
        fireToast(
          t("assets.add.duplicateSerial", {
            asset: String(created.warnings[0]?.existing_asset_no ?? ""),
          }),
        );
      }
      // THE ASSET EXISTS FIRST. Only now does the pre-tick open the door — a
      // job anchored to a meter the server refused would be a job on nothing.
      navigate(
        tenantPath(
          values.raise_work_order
            ? raiseWorkOrderPath(created.id)
            : assetDetailPath(created.id),
        ),
      );
      return { ok: true };
    } catch (error) {
      // `CR-161-BRC10` W3 — a refused custom field is marked on its control on
      // step 4, and the clerk is taken there with every answer kept.
      const custom = isApiError(error) ? customFieldErrors(error.fieldErrors, translate) : {};
      setCustomErrors(custom);
      if (Object.keys(custom).length > 0) {
        setStep({ step: 4, reached: 4 });
      }
      // BR-SHL-020: plain language, from the server's own message_key. A
      // duplicate NUMBER (BR-AST-033 hard block) lands here with its name.
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  const measuring = isMeasuringCategory(klass);
  const tabTypes = typesForTab(typesQuery.data?.results, klass);
  const availability = numberAvailabilityKey(values.asset_no, numberQuery.data ?? null);
  // The tenant's enabled services, as the picker's options and as the ONE place
  // a code is turned into a word. B14 rule 31 — a code is an internal
  // reference and never the visible value of a field, so `water` is offered and
  // displayed as *Water*, and the summary on step 4 reads the same way.
  const serviceOptions = enabledServiceRows(servicesQuery.data).map((row) => ({
    value: row.service,
    label: row.name,
  }));
  const serviceName =
    serviceOptions.find((option) => option.value === values.service)?.label ?? values.service;
  // The same rule for the asset TYPE — `DEF-MET-4990`. The summary read the
  // lookup CODE, so a clerk checking their answers saw `meter` and `net_meter`.
  const typeName = tabTypes.find((entry) => entry.code === values.type)?.name ?? values.type;
  // ⚠ **THE SAME RULE, THREE MORE TIMES, FOR SCREEN 32.** The review reads a
  // read method, a premises and a unit BACK to a clerk, and every one of them
  // is stored as an id or a code. Resolved once, here, off the list the picker
  // itself offered — so the review cannot disagree with the control a person
  // just used, which is the failure `DEF-MET-4990` was.
  const premisesOptions = premisesPickerOptions(premisesQuery.data?.results);
  const unitOptions = unitsFor(unitsQuery.data?.results, values.premises_id);
  const readMethodName =
    (readMethodsQuery.data?.results ?? []).find((entry) => entry.code === values.read_method)
      ?.name ?? values.read_method;
  const premisesName =
    premisesOptions.find((option) => option.value === values.premises_id)?.label ?? "";
  const unitName = unitOptions.find((option) => option.value === values.unit_id)?.label ?? "";
  // The class as its own word — figure 49's `Class  Meter`. `ASSET_TAB_IDS`
  // and this catalogue family are the same pair the step-1 chooser reads.
  const classLabel = t(`assets.add.class.${klass}`);
  /**
   * ⚠ **THE PAGE HEAD'S KICKER AND TITLE ARE THE DRAWING'S, AND THE PATTERN IS
   * THE MODULE'S OWN.** Every figure in section 06 heads the page `METER · ADD
   * AN ASSET` over the asset NUMBER — and figure 46 heads it `BACKFLOW
   * PREVENTER · ADD AN ASSET`, which is the TYPE rather than the class. That is
   * `assetFlowKicker`'s shape one file across (`type_name · flow`), so the four
   * action screens and this one read the same way. Before a type is chosen
   * there is no type name, and the CLASS is the truest thing we have.
   *
   * ⚠ **THE TITLE IS A HUMAN-FACING NUMBER AND NOT A DATABASE ID** — B14 rule
   * 31 names the asset number as exactly the case it permits, and nothing here
   * ever renders `values`' ids. Before a number exists the title is the flow's
   * own name, because a title that reads `—` names nothing.
   */
  const headKicker = [typeName === "" ? classLabel : typeName, t("assets.add.title")]
    .filter((part) => part !== "")
    .join(" · ");
  const reservedNumber = values.asset_no.trim() || numberQuery.data?.suggested || "";

  const steps = [
    {
      id: "identity",
      label: t("assets.add.step.identity"),
      validate: () => stepValid(1, values),
      content: (
        <IdentityStep
          t={translate}
          klass={klass}
          values={values}
          onClass={switchClass}
          onChange={setValues}
          types={tabTypes}
          masters={mastersFor(metersQuery.data?.results, "parent")}
          suggested={numberQuery.data?.suggested ?? null}
          availability={availability}
          services={serviceOptions}
          restarted={restarted}
        />
      ),
    },
    {
      id: "specification",
      label: t("assets.add.step.specification"),
      validate: () => stepValid(2, values),
      content: measuring ? (
        <MeasuringSpecStep
          t={translate}
          values={values}
          onChange={setValues}
          meterTypes={meterTypesQuery.data?.results ?? []}
          readMethods={readMethodsQuery.data?.results ?? []}
          sizeClasses={sizeClassesQuery.data?.results ?? []}
          dateFormat={dateFormat}
        />
      ) : (
        <DeviceSpecStep
          t={translate}
          values={values}
          onChange={setValues}
          meters={mastersFor(metersQuery.data?.results, linkKindOf(values.type))}
          readMethods={readMethodsQuery.data?.results ?? []}
          sizeClasses={sizeClassesQuery.data?.results ?? []}
          dateFormat={dateFormat}
        />
      ),
    },
    {
      id: "assignment",
      label: t("assets.add.step.assignment"),
      // DEF-178 / DEF-936 — a step may answer AT THE BUTTON with its own
      // sentence. A missing read date is named, because the frame's generic
      // line would send a clerk looking for a required field on this step and
      // the thing to fix is a date they left blank on the last one.
      validate: () =>
        openingReadNeedsADate(values)
          ? t("assets.add.openingReadNeedsDate")
          : stepValid(3, values),
      content: (
        <AssignmentStep
          t={translate}
          values={values}
          onChange={setValues}
          premises={premisesOptions}
          units={unitOptions}
          dateFormat={dateFormat}
          serviceName={serviceName}
        />
      ),
    },
    {
      id: "lifecycle",
      label: t("assets.add.step.lifecycle"),
      validate: () => stepValid(4, values),
      content: (
        <>
          <LifecycleStep
            t={translate}
            values={values}
            onChange={setValues}
            measuring={measuring}
            dateFormat={dateFormat}
            today={today}
          />
          {/* `CR-161-BRC10` W3 · `DEF-AST-9171` — Add asset's slot, on the last
              step that collects anything; nothing for a tenant with none. */}
          <FieldErrorsScope errors={customErrors}>
            <CustomFieldsInput
              entity="assets"
              screen="S51"
              values={values.custom_data ?? {}}
              onChange={(custom_data) => {
                setCustomErrors({});
                setValues({ ...values, custom_data });
              }}
              client={client}
            />
          </FieldErrorsScope>
        </>
      ),
    },
    {
      // ⛔ **SCREEN 32 — the fifth box the rail has always been drawn with.**
      // `WizardFrame` reads `steps.length`, so adding this entry is what turns
      // `Continue` on step 4 into `Add asset ✓` HERE, one screen later. There
      // is no `validate`: nothing on a read-only review can be unanswered, and
      // a step that cannot refuse must not pretend it might.
      id: "review",
      label: t("assets.add.step.review"),
      content: (
        <ReviewStep
          t={translate}
          values={values}
          onChange={setValues}
          measuring={measuring}
          typeName={typeName}
          readMethodName={readMethodName}
          serviceName={serviceName}
          premisesName={premisesName}
          unitName={unitName}
          classLabel={classLabel}
          suggested={numberQuery.data?.suggested ?? null}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      ),
    },
  ];
  // `CR-161-BRC10` W3 — the review lists what step 4 collected.
  const reviewStep = steps[steps.length - 1];
  steps[steps.length - 1] = {
    ...reviewStep,
    content: (
      <>
        {reviewStep.content}
        <CustomFieldsAnswers
          entity="assets"
          screen="S51"
          values={values.custom_data ?? {}}
          client={client}
        />
      </>
    ),
  };

  // ── `AST-B-28` — THE ESCAPE HATCH, AND WHY ONLY HALF OF IT IS BUILT ──────
  //
  // PO 2026-09-12 approved *Save as draft* (*"Can you fix this"*). Step 1 found
  // the spec's premise wrong: there was no button to fix. **This wizard passed
  // no `exit` prop at all**, so it drew neither of B19 §12.2's two controls on
  // any of its four steps — a clerk three fields into the wrong meter had
  // `← Back` and nothing that said *leave this*, while a clerk half way through
  // a move-in had both.
  //
  // ✅ **`Save & exit` IS WIRED AND IS THE WHOLE OF WHAT B19 §12.2 PROMISES** —
  // *"leaves quietly and writes nothing of its own"*. Nothing is created, so
  // there is nothing to undo; the clerk lands back on the registry.
  //
  // ⛔ **`Park` IS REFUSED, WITH ITS REASON, AND IS NOT BUILT HERE.** It needs
  // two things this lane cannot reach:
  //   · a `flow` value the store would accept. `wizard_parks.flow` is a
  //     DATABASE CHECK CONSTRAINT over five values (`move_in`, `move_out`,
  //     `transfer`, `disconnect`, `new_connect`), so `add_asset` is a migration
  //     rather than a client change — the decision log of 2026-09-12 says so in
  //     those words;
  //   · **somewhere a parked draft would appear.** CR-035 AMENDMENT 1 put
  //     parked drafts *"directly on each request"* tab, and there is no Drafts
  //     home on the Assets registry — screen 33 is drawn and unbuilt. A draft
  //     nothing lists is a write nobody can read, which is worse than no
  //     button: the `Save as draft` the spec describes is exactly *"a promise
  //     the product does not keep"*.
  // This is `BillRunWizard`'s own posture and its reasoning (DEF-1043), and the
  // sentence is a catalogue string rather than a `defaultValue` because it is
  // ALWAYS on screen — a `defaultValue` ships English to every tenant.
  //
  // ⚠ **THE REFUSAL CANNOT ROT SILENTLY.** `AssetWizardExit.dom.test.tsx`
  // asserts that `add_asset` is absent from `WIZARD_PARK_FLOWS` and fails the
  // day it is added, naming this comment — hard-won law 2's mirror, *"when you
  // write a hold, write the test that fires when the hold expires."*
  const exit: WizardExit = {
    onSaveAndExit: () => navigate(tenantPath(ASSETS_ROUTE)),
    parkBlockedReason: t("assets.wizard.parkBlocked"),
    parkOpen: false,
    onParkOpenChange: () => undefined,
    onPark: () =>
      Promise.resolve<WizardCommitOutcome>({
        ok: false,
        reason: t("assets.wizard.parkBlocked"),
      }),
    dateFormat,
    parkedAt: null,
  };

  return (
    <div className="px-4 pt-6 pb-8">
      {/* ⚠ **THE PAGE HEAD IS THE DRAWING'S, AND FOUR OF ITS FIVE ELEMENTS WERE
          MISSING.** Every figure in section 06 draws the same head: `← Assets`
          over the kicker `METER · ADD AN ASSET`, the RESERVED NUMBER as the
          title, a `New` chip beneath it, the line *"Not created yet · the
          number is reserved when you finish"*, and a `…` overflow at the far
          right. What stood here was the kicker `Assets` over the title `Add an
          asset` and nothing else — so the one thing the whole flow is about,
          the number, appeared nowhere until step 4's summary box.

          ⚠ **THE `…` OVERFLOW IS NOT BUILT, AND THAT IS DELIBERATE.** No page
          of section 06 draws what is inside it — not one item, on any of the
          five figures. A `…` that opens an empty menu is a dead control, which
          is hard-won law 2's mirror and the thing `DEF-CWP-3925` cost eight
          doors to learn. Reported rather than guessed at.

          ⚠ **THE SUB-LINE IS TWO FACTS AND THE SECOND IS FIVE WORDS.** The
          drawing's is three words then seven; B14 rule 33 caps a FACT at six,
          and rule 41 sends a drawing that contradicts a signed rule to the
          report. Both facts survive: it does not exist yet, and the number is
          taken at the end. */}
      <div className="mb-4 [&_h1]:m-0 [&_h1]:text-h2">
        <PageHeader
          backTo={{ to: tenantPath(ASSETS_ROUTE), label: t("shell.nav.assets") }}
          kicker={headKicker}
          title={reservedNumber === "" ? t("assets.add.title") : reservedNumber}
          status={<Chip>{t("assets.add.newChip")}</Chip>}
          rollup={t("assets.add.notCreated")}
        />
      </div>
      <div className="max-w-4xl">
        <WizardFrame
          steps={steps}
          nav={nav}
          onNavChange={setStep}
          exit={exit}
          commitLabel={t("assets.add.commit")}
          commitFailedTitle={t("assets.add.commitFailed")}
          onCommit={commit}
          onCommitted={() => undefined /* commit() already navigated with the id */}
        />
      </div>
    </div>
  );
}

// ── Option builders (pure) ─────────────────────────────────────────────────

/** BR-AST-003: masters offered are ACTIVE meters/net-meters; for a device
 *  link, `net` narrows to net meters (an inverter links to the meter that
 *  measures its export — B16 §5.1b (B)). */
export function mastersFor(
  rows: readonly AssetRow[] | undefined,
  kind: "parent" | "net" | "any",
): { value: string; label: string }[] {
  return (rows ?? [])
    .filter((row) => row.type === "meter" || row.type === "net_meter")
    .filter((row) => row.behavior_class === "in_service")
    .filter((row) => (kind === "net" ? row.net_metering : true))
    .map((row) => ({
      value: row.asset_no,
      label: [row.asset_no, row.assigned_address].filter((part) => part).join(" · "),
    }));
}

/** An exporting kind links to a NET meter; anything else may link to any. */
export function linkKindOf(typeCode: string): "net" | "any" {
  return typeCode === "pv" || typeCode === "battery" ? "net" : "any";
}

// ⚠ **`DEF-MET-4985` WAS FIXED BY WIDENING TWO SENTENCES, NOT BY BRANCHING
// THEM, AND A `deviceExports(typeCode)` PREDICATE WAS WRITTEN HERE AND THEN
// DELETED.** The defect row offers both remedies — *"either branch the two
// helpers on the chosen type, or widen the sentences so they are true of every
// device the step offers"* — and the blueprint's own drawing (PDF page 115,
// the backflow-preventer variant) had already chosen the second: *"The meter
// that measures it."* and *"A capacity, never money."* One string that is true
// everywhere beats two that each have to be kept true, and the FIELDS are
// untouched either way: which device types may record an export capacity is
// ruled nowhere — the column says *"BTM inverters only"*, `_validate_asset`
// accepts it on every type, and `assetsShared.btmKpis` derives *exporting*
// from *"has a capacity recorded"* rather than from a type list. Dropping the
// control for a generator would have invented that rule.

export function unitsFor(
  rows: readonly UnitRow[] | undefined,
  premisesId: string,
): { value: string; label: string }[] {
  const scoped =
    premisesId === "" ? (rows ?? []) : (rows ?? []).filter((row) => row.premises_id === premisesId);
  return unitPickerOptions(scoped);
}

/** The UNIQUE callout's state: ok · taken · null (nothing typed / no answer). */
export function numberAvailabilityKey(
  typed: string,
  preview: { available: boolean | null } | null,
): "available" | "taken" | null {
  if (typed.trim() === "" || preview === null || preview.available === null) {
    return null;
  }
  return preview.available ? "available" : "taken";
}

// ── Steps ──────────────────────────────────────────────────────────────────

function IdentityStep(props: {
  t: Translator;
  klass: AssetTab;
  values: AddWizardValues;
  onClass: (next: AssetTab) => void;
  onChange: (values: AddWizardValues) => void;
  types: readonly LookupEntry[];
  /** ⚠ **NO `readMethods` HERE ANY MORE.** The read method is a step-2 field on
   *  both spec variants now (figures 45 and 46), so the list goes there and
   *  this step cannot render a stale copy of it. */
  masters: { value: string; label: string }[];
  suggested: string | null;
  availability: "available" | "taken" | null;
  /** The TENANT's enabled services — `AST-B-03`. Never a list in this file. */
  services: { value: string; label: string }[];
  /** `DEF-MET-4983` — this mount refused a `?step=` past the first. */
  restarted: boolean;
}) {
  const { t, values } = props;
  return (
    <div className="flex flex-col gap-5">
      {/* `DEF-MET-4983` — a reload that lost the answers says so. `status` and
          not `alert`: nothing is wrong, the person simply starts again. */}
      {props.restarted && <Note role="status">{t("assets.add.restarted")}</Note>}
      <p className="m-0 text-base">{t("assets.add.identityLede")}</p>
      <SegmentedField
        id="klass"
        label={t("assets.add.class")}
        value={props.klass}
        options={ASSET_TAB_IDS.map((id) => ({ value: id, label: t(`assets.add.class.${id}`) }))}
        onChange={(value) => props.onClass(value as AssetTab)}
      />
      {/* ⚠ **ROW 1 IS `Asset number | Asset type` ON A METER AND
          `Asset number | Parent master` ON A SUB-METER** — figures 43 and 44.
          The number ran full width on its own row and the type sat beside a
          READ METHOD the drawing puts on step 2; both are corrected here.

          The label is the drawing's `Asset number`, and it is a wizard-scoped
          key rather than a re-wording of `assets.form.assetNo`: that key also
          labels the field on `AssetEditPage` (screen 14), which was built to
          its OWN remedy drawing at `2.239.9`, and moving a shared string is a
          change to a screen this lane did not measure.

          ⚠ **NO ASTERISK, DELIBERATELY, AND THE DRAWING'S IS THE THING TO
          QUESTION.** Figure 43 marks it `*`; `stepValid(1)` permits a blank
          and the server then takes the next number in the tenant's series
          (`BR-AST-026`) — which is the behaviour the helper describes and the
          availability note below confirms. Marking it required would delete a
          working path to satisfy an ink mark. Reported, not built. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="asset_no"
          label={t("assets.add.assetNumber")}
          value={values.asset_no}
          onChange={(value) => props.onChange({ ...values, asset_no: value })}
          placeholder={props.suggested ?? undefined}
          // B14 rule 33 — the old fallback was a SIXTEEN-word first sentence
          // (`assets.form.assetNoHelp`, still correct on the edit screen's own
          // wording). The drawing's replacement is six and says the same thing.
          help={
            props.suggested !== null
              ? t("assets.add.numberSuggested", { number: props.suggested })
              : t("assets.add.assetNumberHelp")
          }
        />
        {props.klass === "sub_meters" ? (
          // BR-AST-003: REQUIRED — the master must exist and be active; only
          // active masters are offered, and the server re-checks. Figure 44
          // puts it HERE, beside the number, and not last.
          <SearchSelectField
            id="parent_asset_no"
            label={t("assets.add.parent")}
            required
            value={values.parent_asset_no}
            options={props.masters}
            placeholder={t("assets.add.parentPlaceholder")}
            onChange={(value) => props.onChange({ ...values, parent_asset_no: value })}
            help={t("assets.add.parentHelp")}
          />
        ) : (
          <AssetTypeField {...props} />
        )}
      </div>
      {/* r10's UNIQUE callout — the availability answer, from the server's
          own case-insensitive probe (BR-AST-033's hard block, asked early). */}
      {props.availability !== null && (
        <Note>
          {props.availability === "available"
            ? t("assets.add.numberAvailable", { number: values.asset_no })
            : t("assets.add.numberTaken", { number: values.asset_no })}
        </Note>
      )}
      {/* ⚠ **ROW 2 IS `Utility service | Device ID / serial` ON A METER AND
          `Asset type | Utility service` ON A SUB-METER** — figures 43 and 44.

          ⚠ **THE SERIAL MOVED HERE FROM STEP 2, WHICH IS WHERE THE DRAWING
          PUTS IT.** It is one of three identifiers with three different
          owners, and p113's *Words* row is why they belong together: *"Asset
          number is ours, Device ID / serial is the manufacturer's, External
          reference is somebody else's"*. It stood on the SPECIFICATION step,
          which is about how the thing measures. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        {props.klass === "sub_meters" ? <AssetTypeField {...props} /> : <ServiceField {...props} />}
        {props.klass === "sub_meters" ? (
          <ServiceField {...props} />
        ) : (
          <SerialField values={values} t={t} onChange={props.onChange} />
        )}
      </div>
      {/* ROW 3 — half width, alone. On a meter it is the EXTERNAL REFERENCE;
          on a sub-meter it is the serial, because figure 44 draws the serial
          last and draws no external reference at all. See
          `AddWizardValues.external_ref` for why that difference is built
          rather than smoothed over. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        {props.klass === "sub_meters" ? (
          <SerialField values={values} t={t} onChange={props.onChange} />
        ) : (
          <TextField
            id="external_ref"
            label={t("assets.spec.externalRef")}
            value={values.external_ref}
            onChange={(value) => props.onChange({ ...values, external_ref: value })}
            // The drawing's own sentence, and the asset's Device edit dialog
            // already says it in these exact words — one string, two screens.
            help={t("assets.panel.help.externalRef")}
          />
        )}
      </div>
    </div>
  );
}

/**
 * The asset type — row 1's right half on a meter, row 2's left on a sub-meter.
 *
 * Extracted because the two class variants put the SAME control in different
 * cells (figures 43 and 44), and a second copy of a `SelectField` is how two
 * cells stop agreeing about what they offer.
 */
function AssetTypeField(props: { t: Translator; values: AddWizardValues; types: readonly LookupEntry[]; onChange: (values: AddWizardValues) => void }) {
  const { t, values } = props;
  return (
    <SelectField
      id="type"
      label={t("assets.col.assetType")}
      required
      value={values.type}
      placeholder={t("assets.add.typePlaceholder")}
      options={props.types.map((entry) => ({ value: entry.code, label: entry.name }))}
      onChange={(value) => props.onChange({ ...values, type: value })}
      // Drawn on both variants and carried by neither control before this.
      help={t("assets.add.typeHelp")}
    />
  );
}

/** The manufacturer's number — drawn on step 1 on every class. */
function SerialField(props: {
  t: Translator;
  values: AddWizardValues;
  onChange: (values: AddWizardValues) => void;
}) {
  const { t, values } = props;
  return (
    <TextField
      id="serial_no"
      label={t("assets.form.serial")}
      value={values.serial_no}
      onChange={(value) => props.onChange({ ...values, serial_no: value })}
      // B14 rule 33 — `assets.form.serialHelp` is 8 words then 12. The drawing
      // says it in five, and the Device edit dialog already carries that five.
      help={t("assets.panel.help.serial")}
    />
  );
}

function ServiceField(props: {
  t: Translator;
  values: AddWizardValues;
  services: { value: string; label: string }[];
  onChange: (values: AddWizardValues) => void;
}) {
  const { t, values } = props;
  return (
    <>
      {/* ⛔ `AST-B-03` / `DEF-MET-4980` · `DEF-MET-4981` — THE UTILITY SERVICE,
          CHOSEN FROM THE TENANT'S OWN LIST AND MARKED AS REQUIRED AS THE SERVER
          REQUIRES IT.

          It was a free-text box whose help named a list it never showed, so the
          only way to learn which codes were enabled was to type one and be
          refused on step 4. The options come from `GET /settings/services`
          (see the query on the component) and carry the service's NAME, never
          its code — B14 rule 31.

          ⚠ **REQUIRED FOR A MEASURING CLASS AND FOR NOTHING ELSE.** A backflow
          preventer belongs to a customer rather than to a connection and
          declares no service (BR-AST-009); `requiresService` is the one
          predicate and `stepValid(1)` reads the same one. */}
      <SelectField
        id="service"
        label={t("assets.form.utilityService")}
        required={requiresService(values.klass)}
        value={values.service}
        placeholder={t("assets.form.servicePlaceholder")}
        options={props.services}
        onChange={(value) => props.onChange({ ...values, service: value })}
        help={t("assets.form.serviceHelp")}
      />
    </>
  );
}

function MeasuringSpecStep(props: {
  t: Translator;
  values: AddWizardValues;
  onChange: (values: AddWizardValues) => void;
  meterTypes: readonly LookupEntry[];
  readMethods: readonly LookupEntry[];
  sizeClasses: readonly LookupEntry[];
  dateFormat: import("@/components/DateCell").RegionalDateFormat;
}) {
  const { t, values } = props;
  const netLocked = values.type === "net_meter"; // BR-AST-010: locked ON
  // `AST-B-27` — a sub-meter is the only asset an allocation share is a fact
  // about. A master meter measures the whole building; the share is what its
  // children take OUT of that.
  const subMeter = values.klass === "sub_meters";
  return (
    <div className="flex flex-col gap-5">
      <p className="m-0 text-base">{t("assets.add.specLede")}</p>
      {/* ⚠ **TWO TO A ROW THROUGHOUT, AND ROW 1 IS `Read method | Connection
          size`** — figure 45. The step opened on `Manufacturer | Model` and
          then a THREE-column `Multiplier | Register digits | Unit of measure`,
          which is the one row the drawing insists on pairing: the multiplier
          and the unit are what a reading MEANS, and they are drawn side by
          side for that reason.

          ⚠ **READ METHOD MOVED HERE FROM STEP 1.** *"How a reading reaches
          us"* is a fact about how the thing measures, which is this step; step
          1 asks what it IS and what we call it. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <SelectField
          id="read_method"
          label={t("assets.col.readMethod")}
          value={values.read_method}
          placeholder={t("assets.form.readMethodPlaceholder")}
          options={props.readMethods
            .filter((entry) => entry.active)
            .map((entry) => ({ value: entry.code, label: entry.name }))}
          onChange={(value) => props.onChange({ ...values, read_method: value })}
          help={t("assets.panel.help.readMethod")}
        />
        {/* ⛔ BR-AST-530 — THE CONNECTION SIZE, and it is the first of the two
            doors the PO ordered on 2026-08-28 (*"Please do both"*). BR-AST-500
            gave this column a home on 2026-08-27 and gave a human no way to
            fill it: the only writer was the API validator, so a utility could
            type a per-size rate ladder and never tell the product which rung a
            meter sits on. On r10's own water figures that is the difference
            between 3.20 / 4.80 / 7.20 and 3.45 / 5.10 / 7.70.

            ⚠ CHOSEN, NEVER TYPED (ruling judgment 1): a `SelectField` over the
            tenant's ratified list, because free text would put a forty-first
            code into the pricing ladder by typo.

            ⚠ METERS ONLY (judgment 4): a sub-meter sits BEHIND a connection
            rather than on one. Widening that is DEF-1901's call, and the
            payload builder holds the same boundary so the two halves cannot
            drift.

            ⚠ NOT REQUIRED (judgment 2): blank is lawful and means "no size
            recorded". The placeholder says so rather than reading as an error.

            ⚠ **IT MOVED UP FROM THE BOTTOM OF THE STEP** — figure 45 draws it
            in row 1 beside the read method — **and its helper lost 29 words.**
            `assets.form.sizeClassHelp` is a 35-word paragraph; B14 rule 33
            caps a helper at six words a sentence, and the drawing's six-word
            replacement is the sentence the asset's own Measurement dialog
            already shows. */}
        {values.klass === "meters" && (
          <SelectField
            id="size_class"
            label={t("assets.col.sizeClass")}
            value={values.size_class}
            placeholder={t("assets.form.sizeClassPlaceholder")}
            // Plan U10 — THIS service's sizes only (`AST.SIZE_FOR_SERVICE`).
            options={sizeOptionsForService(props.sizeClasses, values.service)}
            onChange={(value) => props.onChange({ ...values, size_class: value })}
            help={t("assets.panel.help.sizeClass")}
          />
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="multiplier"
          label={t("assets.form.multiplier")}
          numeric
          required
          value={values.multiplier}
          onChange={(value) => props.onChange({ ...values, multiplier: value })}
          // Drawn with a helper on a field that carried none — and it is the
          // single most consequential box on the screen.
          help={t("assets.panel.help.multiplier")}
        />
        <TextField
          id="unit"
          label={t("assets.form.uom")}
          required
          value={values.unit}
          onChange={(value) => props.onChange({ ...values, unit: value })}
          // B14 rule 33 — `assets.form.uomHelp` is fourteen words in one
          // sentence. The drawing says it in five.
          help={t("assets.panel.help.uom")}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="register_digits"
          label={t("assets.spec.registerDigits")}
          numeric
          value={values.register_digits}
          onChange={(value) => props.onChange({ ...values, register_digits: value })}
          help={t("assets.panel.help.registerDigits")}
        />
        <TextField
          id="manufacturer"
          label={t("assets.add.manufacturer")}
          value={values.manufacturer}
          onChange={(value) => props.onChange({ ...values, manufacturer: value })}
          help={t("assets.add.manufacturerHelp")}
        />
      </div>
      {/* ⛔ **FORM / CLASS AND SEAL #, BOTH MARKED NEW ON BOTH SPEC VARIANTS.**
          Two more columns `POST /assets` has always accepted
          (`services.py:670, 673`) and no screen could write until the asset
          existed. The drawing makes the seal's case itself: *"The seal fitted
          at installation."* — which is the moment this form is open. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="model"
          label={t("assets.add.model")}
          value={values.model}
          onChange={(value) => props.onChange({ ...values, model: value })}
          help={t("assets.add.modelHelp")}
        />
        <TextField
          id="form_class"
          label={t("assets.spec.formClass")}
          value={values.form_class}
          onChange={(value) => props.onChange({ ...values, form_class: value })}
          help={t("assets.add.formClassHelp")}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="firmware_version"
          label={t("assets.spec.firmware")}
          value={values.firmware_version}
          onChange={(value) => props.onChange({ ...values, firmware_version: value })}
          help={t("assets.add.firmwareHelp")}
        />
        <TextField
          id="seal_no"
          label={t("assets.spec.seal")}
          value={values.seal_no}
          onChange={(value) => props.onChange({ ...values, seal_no: value })}
          help={t("assets.add.sealHelp")}
        />
      </div>
      {/* ⛔ `AST-B-27` — THE SUB-METER'S ALLOCATION SHARE. PO ruling
          2026-09-12, verbatim: *"this is correct - build it"*, and the four
          method words were RATIFIED in the same breath — the first
          customer-facing words these values have ever had.

          **What was wrong:** `allocation_share_pct` and `allocation_rule` are
          columns, `POST /assets` and `PATCH /assets/{id}` both accept them, the
          reconciliation engine reads them — and **no screen in the product
          could put a value in either**. Every sub-meter this wizard has ever
          created came out *metered, not allocated*, permanently. That is
          hard-won law 2 in its third form: a column with a reader and no
          writer, which no gate looks for.

          ⚠ **THE METHOD IS CHOSEN, NEVER TYPED, AND THE FOUR OPTIONS ARE
          DERIVED FROM ONE LIST** (`ALLOCATION_RULES`). `allocation_rule` is a
          bare `TextField` on the model with the four codes written in a code
          comment and nowhere else — no `choices`, no lookup table, no check
          constraint — so free text here would put a fifth value into the
          reconciliation engine by typo, and nothing downstream would refuse it.

          ⚠ **B14 rule 31 — THE CODE IS NEVER THE VISIBLE VALUE.** `rubs` is
          offered and displayed as *Share of the building's total*; the stored
          value is the code and the clerk never meets it.

          ⚠ **NEITHER IS REQUIRED.** Blank means *metered, not allocated*, which
          is a lawful and common state — a sub-meter can be read for information
          long before anybody decides how its usage is shared. The placeholder
          says *Not set* rather than reading as an error. */}
      {subMeter && (
        <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
          <TextField
            id="allocation_share_pct"
            label={t("assets.spec.allocationShare")}
            numeric
            value={values.allocation_share_pct}
            onChange={(value) => props.onChange({ ...values, allocation_share_pct: value })}
            help={t("assets.add.allocationShareHelp")}
          />
          <SelectField
            id="allocation_rule"
            label={t("assets.spec.allocationRule")}
            value={values.allocation_rule}
            placeholder={t("assets.add.allocationRulePlaceholder")}
            options={ALLOCATION_RULES.map((code) => ({
              value: code,
              label: t(`assets.allocationRule.${code}`),
            }))}
            onChange={(value) => props.onChange({ ...values, allocation_rule: value })}
            help={t("assets.add.allocationRuleHelp")}
          />
        </div>
      )}
      {/* ⛔ `AST-B-14` — THE OPENING READ, AND IT IS A MOVE RATHER THAN AN
          ADDITION. PO ruling 2026-09-12, verbatim: *"Build it as drawn - move
          it to step 2, beside the multiplier, register digits and the
          warning"*.

          It stood on step 3 (`AssignmentStep`) as a DISABLED box carrying a
          refusal — *"recorded through Meter Reads once the meter is installed
          - it cannot be captured here"* — and that sentence stopped being true
          the moment the ruling landed. **The control was DELETED from step 3
          rather than un-disabled there**, which is wave B lane 5's own written
          instruction and hard-won law 2's mirror: when a hold expires, the
          thing that was holding goes with it.

          ⚠ **WHY HERE AND NOT ANYWHERE ELSE.** A register reading is
          meaningless without the multiplier it is multiplied by and the digit
          count it rolls over at, and both are asked for immediately above. The
          ×10 warning below is the product's own sentence about exactly this
          field's arithmetic; on step 3 the reading sat a whole step away from
          the only text that explains it.

          ⚠ **THE DATE IS BLANK AND DEFAULTS SERVER-SIDE** — see
          `AddWizardValues.opening_read_date`. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="opening_read"
          label={t("assets.add.openingRead")}
          numeric
          value={values.opening_read}
          onChange={(value) => props.onChange({ ...values, opening_read: value })}
          help={t("assets.add.openingReadHelp")}
        />
        <DatePickerField
          id="opening_read_date"
          label={t("assets.add.openingReadDate")}
          value={values.opening_read_date}
          dateFormat={props.dateFormat}
          onChange={(value) => props.onChange({ ...values, opening_read_date: value })}
          help={t("assets.add.openingReadDateHelp")}
        />
      </div>
      {/* B14 rule 11 — a form that writes outside its own table says what it
          will do BEFORE the commit. This one writes a `meter_reads` row, and
          the sentence a clerk needs is the failure rule rather than the happy
          path: the asset does not survive a refused reading.

          Drawn only when there IS a reading to write. An empty box writes
          nothing, so a consequence box over it would be describing something
          that is not going to happen — B14 rule 32's budget spent on nothing. */}
      {values.opening_read.trim() !== "" && (
        <ConsequenceBox
          tone="check"
          data-consequence="opening-read"
          title={t("assets.add.openingReadConsequenceTitle")}
          body={t("assets.add.openingReadConsequenceBody")}
        />
      )}
      {/* **THE MULTIPLIER CALLOUT, AS A TITLED BOX** — figure 45 draws it
          bordered with a rule down its left edge and the heading `CHECK IT
          AGAINST THE METER FACE` above the sentence, and it stood here as a
          plain `Note` with no heading at all. It is the kit's `emergency`
          panel, which is exactly that shape: the plain border plus an accent
          rule, no second hue (r10 draws no blue anywhere and reaches for an
          accent rule instead). One divergence is recorded rather than built —
          the kit renders the title as an `h3` where the drawing draws it small,
          uppercase and in the accent, and moving that is a change to the shared
          component and to every panel that uses it.

          The body keeps the product's own second sentence, *"Confirm against
          the meter face before saving."*, which the drawing has folded into the
          heading. p116 calls this *"the best warning in the module"*. */}
      <Panel as="section" tone="emergency" title={t("assets.add.meterFaceTitle")}>
        <p className="m-0 text-base">{t("assets.add.multiplierWarning")}</p>
      </Panel>
      {/* METER TYPE — **not drawn on this step, and kept on purpose.** It is
          one of the five things the code holds that the drawing does not
          (`BR-AST-044`, the SECOND classification, independent of `type`), and
          the gap list names all five precisely so that nobody deletes one to
          match a picture. Its helper drops from eleven words to seven across
          two sentences (B14 rule 33), using the sentence the asset's own
          Measurement dialog already carries. */}
      <SelectField
        id="meter_type"
        label={t("assets.col.meterType")}
        value={values.meter_type}
        placeholder={t("assets.form.meterTypePlaceholder")}
        options={props.meterTypes
          .filter((entry) => entry.active)
          .map((entry) => ({ value: entry.code, label: entry.name }))}
        onChange={(value) => props.onChange({ ...values, meter_type: value })}
        help={t("assets.panel.help.meterType")}
      />
      {/* r10's "Bidirectional" flag → net_metering (BR-AST-010: locked ON for
          a net meter). **Also not drawn on this step and also kept** — same
          reason as the meter type above. The "Demand register" flag r10 draws
          beside it has NO column and renders NOTHING — reported, not
          invented. */}
      <CheckboxField
        id="net_metering"
        label={netLocked ? t("assets.form.netMeteringLocked") : t("assets.add.bidirectional")}
        checked={netLocked || values.net_metering}
        onChange={(checked) =>
          props.onChange({ ...values, net_metering: netLocked ? true : checked })
        }
      />
    </div>
  );
}

function DeviceSpecStep(props: {
  t: Translator;
  values: AddWizardValues;
  onChange: (values: AddWizardValues) => void;
  meters: { value: string; label: string }[];
  readMethods: readonly LookupEntry[];
  sizeClasses: readonly LookupEntry[];
  dateFormat: import("@/components/DateCell").RegionalDateFormat;
}) {
  const { t, values } = props;
  return (
    <div className="flex flex-col gap-5">
      <p className="m-0 text-base">{t("assets.add.deviceSpecLede")}</p>
      {/* ⚠ **ROW 1 IS `Linked meter | Export capacity (kW)`, TWO TO A ROW** —
          figure 46. The linked meter ran full width on its own row.

          B16 Item 3d: device type (chosen at step 1) · linked meter (net
          meters offered for inverters) · export capacity · test interval. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <SearchSelectField
          id="parent_asset_no"
          label={t("assets.add.linkedMeter")}
          value={values.parent_asset_no}
          options={props.meters}
          placeholder={t("assets.add.linkedMeterPlaceholder")}
          onChange={(value) => props.onChange({ ...values, parent_asset_no: value })}
          // `DEF-MET-4985` — the blueprint's own sentence (PDF page 115), which is
          // true of a backflow preventer and of an inverter alike. It read *"An
          // exporting inverter links to the net meter that measures its export."*
          // on a control offered to all ten device types. The OPTIONS still
          // narrow to net meters for an exporting kind — that is `linkKindOf`,
          // one function up, and it is behaviour rather than a sentence.
          help={t("assets.add.linkedMeterHelp")}
        />
        <TextField
          id="export_capacity_kw"
          label={t("assets.add.exportCapacity")}
          numeric
          value={values.export_capacity_kw}
          onChange={(value) => props.onChange({ ...values, export_capacity_kw: value })}
          // `DEF-MET-4985` — PDF page 115 again. It read *"A capacity, in kW —
          // inverters and batteries only."* on a form that was offering it to a
          // backflow preventer, which is a sentence refusing the field it sits
          // under. The drawing widens it instead of branching it, and a widened
          // sentence is one string rather than two to keep true.
          help={t("assets.add.exportCapacityHelp")}
        />
      </div>
      {/* ⛔ **THE DEVICE STEP CAPTURED NO MODEL AT ALL, AND p115 SAYS SO IN ITS
          OWN BOX:** *"A backflow preventer is a Watts Water 909; the detail
          view has a Manufacturer / model row and will happily display it. So on
          a device the model is one more COLUMN WITH A READER AND NO WRITER."*
          `manufacturer` and `model` are two columns, so they are two fields on
          every class — which is the rule that same box states. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="manufacturer"
          label={t("assets.add.manufacturer")}
          value={values.manufacturer}
          onChange={(value) => props.onChange({ ...values, manufacturer: value })}
          help={t("assets.add.manufacturerHelp")}
        />
        <TextField
          id="model"
          label={t("assets.add.model")}
          value={values.model}
          onChange={(value) => props.onChange({ ...values, model: value })}
          help={t("assets.add.modelHelp")}
        />
      </div>
      {/* ⚠ **THE TEST INTERVAL IS A NUMBER OF MONTHS, NOT A THREE-OPTION
          CHOOSER, AND THAT IS A WIRING FIX RATHER THAN A PREFERENCE.** It was a
          `SelectField` over 12 / 24 / 60 whose own helper named **96** as the
          seeded default for a meter — a value the control could not produce, so
          a clerk reading the sentence could not act on it. Figure 46 draws a
          free number reading `12` and figure 48 draws one reading `96`, both
          with the helper *"In months."*

          ⚠ **THE DRAWN NUMBERS ARE ILLUSTRATIONS** (B14 rule 37): neither 12
          nor 96 is asserted anywhere here, and blank still means *"the type's
          own seeded default"* (`BR-AST-027`) — which is what the placeholder
          says. `assets.add.cadence.12/24/60` are left in the catalogues rather
          than deleted from eleven shared files by a screen lane; they are
          reported instead.

          ⚠ **CERTIFICATION DUE IS ON THIS STEP FOR A DEVICE.** Figure 46 pairs
          it with the test interval here; figure 48 draws it on step 4 for a
          meter. It is one field on one step per class, never both. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="test_interval_months"
          label={t("assets.spec.testInterval")}
          numeric
          value={values.test_interval_months}
          placeholder={t("assets.add.testCadenceDefault")}
          onChange={(value) => props.onChange({ ...values, test_interval_months: value })}
          // BR-AST-027: blank → the TYPE's seeded default (backflow 12 mo).
          help={t("assets.panel.help.testInterval")}
        />
        <DatePickerField
          id="certification_due"
          label={t("assets.add.certificationDue")}
          value={values.certification_due}
          dateFormat={props.dateFormat}
          onChange={(value) => props.onChange({ ...values, certification_due: value })}
          help={t("assets.panel.help.certificationDue")}
        />
      </div>
      {/* FORM / CLASS and SEAL # — figure 46's last row, marked NEW on it. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="form_class"
          label={t("assets.spec.formClass")}
          value={values.form_class}
          onChange={(value) => props.onChange({ ...values, form_class: value })}
          help={t("assets.add.formClassHelp")}
        />
        <TextField
          id="seal_no"
          label={t("assets.spec.seal")}
          value={values.seal_no}
          onChange={(value) => props.onChange({ ...values, seal_no: value })}
          help={t("assets.add.sealHelp")}
        />
      </div>
      {/* ⚠ **READ METHOD IS KEPT ON A DEVICE AND THE DRAWING DRAWS NONE — a
          question, not a decision.** Figure 46 is an exhaustive field list for
          this step (it even states which fields are absent and why), and it
          shows no read method; figures 43 and 44 draw step 1 for a meter and a
          sub-meter only, so no drawing in section 06 covers a device's step 1
          either. The control is LIVE today on step 1 for every class, so
          dropping it would delete a working capture site on the authority of a
          picture that does not mention it. It moves with its class-mates and
          the question is reported. */}
      <SelectField
        id="read_method"
        label={t("assets.col.readMethod")}
        value={values.read_method}
        placeholder={t("assets.form.readMethodPlaceholder")}
        options={props.readMethods
          .filter((entry) => entry.active)
          .map((entry) => ({ value: entry.code, label: entry.name }))}
        onChange={(value) => props.onChange({ ...values, read_method: value })}
        help={t("assets.panel.help.readMethod")}
      />
      {/* BR-AST-500 / BR-AST-530 as AMENDED 2026-09-01 (DEF-2414) — the size of
          the thing standing on a service connection. It renders once a SERVICE
          is named on step 1, because that is what makes this device part of a
          connection rather than a customer's own equipment; `offersConnectionSize`
          is the one predicate and the payload builder reads the same one.

          The case that moved the boundary: a trash connection's equipment is a
          CART, so "which size is this connection" and "which cart is on it" are
          one question — and until today no screen could answer it. */}
      {offersConnectionSize(values) && (
        <SelectField
          id="size_class"
          label={t("assets.col.sizeClass")}
          value={values.size_class}
          placeholder={t("assets.form.sizeClassPlaceholder")}
          // Plan U10 — THIS service's sizes only (`AST.SIZE_FOR_SERVICE`).
          options={sizeOptionsForService(props.sizeClasses, values.service)}
          onChange={(value) => props.onChange({ ...values, size_class: value })}
          help={t("assets.form.sizeClassDeviceHelp")}
        />
      )}
      {/* ⛔ Plan U10 (PO 2026-09-30) — the device's UNIT OF MEASURE / CAPACITY
          UNIT, the column the upload's devices sheet now carries (a cart, kW,
          Mbps, ton). Offered once a service is named, the same predicate as
          the size above; blank sends nothing and the server stamps the
          service's own unit (`SERVICE_DEFAULT_UOMS`). */}
      {offersConnectionSize(values) && (
        <TextField
          id="unit"
          label={t("assets.form.uom")}
          value={values.unit}
          onChange={(value) => props.onChange({ ...values, unit: value })}
          help={t("assets.add.capacityUnitHelp")}
        />
      )}
      {/* The serial left this step for step 1, where both step-1 figures draw
          it — see `SerialField`. */}
    </div>
  );
}

/**
 * ⚠ **NO LONGER READ BY EITHER SPEC STEP.** The test interval is a number of
 * months on both, exactly as figures 46 and 48 draw it, so the three-option
 * chooser these words labelled is gone. The constant and its three catalogue
 * keys are left in place rather than swept: `assets.add.cadence.12/24/60` live
 * in eleven shared catalogue files that three other lanes are writing to
 * today, and deleting from those is not a screen lane's move. Reported.
 */
export const CADENCE_MONTHS = [12, 24, 60] as const;

function AssignmentStep(props: {
  t: Translator;
  values: AddWizardValues;
  onChange: (values: AddWizardValues) => void;
  premises: { value: string; label: string }[];
  units: { value: string; label: string }[];
  dateFormat: import("@/components/DateCell").RegionalDateFormat;
  /** The chosen service as a WORD — `DEF-MET-4986`'s sentence names it. */
  serviceName: string;
}) {
  const { t, values } = props;
  return (
    <div className="flex flex-col gap-5">
      <p className="m-0 text-base">{t("assets.add.assignmentLede")}</p>
      {/* ⚠ **THE CHOOSER ASKS `Where does it go?` AND OFFERS `To a unit` FIRST**
          — figure 47, annotated `FIX · 2`. It read *"Assign now?"* over
          *"Into inventory · Assign to a unit"*, which is a different question
          (a yes/no) in a different order. p118's *Cognitive load* row is the
          reason the words matter: *"Leaving it unassigned is a FIRST-CLASS
          ANSWER, not a skipped field"* — and *"Assign now?"* frames one of the
          two answers as a refusal to answer.

          ⚠ **THE DEFAULT IS STILL `inventory` AND THE ORDER IS THE DRAWING'S.**
          Figure 47 lands on `To a unit`, which is the SELECTED state of an
          illustration (B14 rule 37) rather than a ruling about what a new form
          starts on; changing what an untouched wizard would create is a
          behaviour change nobody asked for, and `isUntouched` reads that
          baseline. Reported. */}
      <SegmentedField
        id="destination"
        label={t("assets.add.assignNow")}
        value={values.destination}
        options={[
          { value: "unit", label: t("assets.add.assignToUnit") },
          { value: "inventory", label: t("assets.add.intoInventory") },
        ]}
        onChange={(value) =>
          props.onChange({ ...values, destination: value === "unit" ? "unit" : "inventory" })
        }
      />
      {/* ⛔ `DEF-MET-4986` — THE SERVICE NAMED ON STEP 1 IS NOT KEPT ON THIS
          PATH, AND UNTIL TODAY NOTHING SAID SO.

          `assets` has no `service` column: the service is DERIVED from the
          asset's service point (`apps/assets/selectors._service_of`), and
          `_create_asset_inner` only reaches for one — `ensure_service_point(
          unit_id, service_code)` — when a unit is chosen. So a meter created on
          this step's DEFAULT destination is validated against the tenant's
          enabled list, refused outright without one, and then stored with
          `service` null. Proved by creating two real meters through this wizard
          with the same typed `water`: the assigned one came back `service
          "water"`, the inventory one `service null`.

          The backend states it in its own docstring — *"The unassigned service
          declaration has no column to live in; that gap is reported, not
          invented around"* — and the screen said nothing at all, which is the
          half this sentence closes. WHERE that declaration should live is a
          ruling nobody has made; it is `OQ-MET-1768` and this lane does not
          choose it (prime directive).

          Shown only once a service has actually been named, so an asset with
          none carries no sentence about losing one. */}
      {values.destination === "inventory" && values.service.trim() !== "" && (
        <ConsequenceBox
          tone="check"
          title={t("assets.add.serviceDroppedTitle", { service: props.serviceName })}
          body={t("assets.add.serviceDroppedBody")}
          data-consequence="assets-add-service-dropped"
        />
      )}
      {/* ⚠ **PREMISES RUNS FULL WIDTH ON ITS OWN ROW, THEN `Unit | Install
          date`** — figure 47. The two pickers shared a row and the install
          date sat in a grid whose second cell was an empty comment block.

          ⚠ **NO ASTERISK ON PREMISES, AND IT IS THE SAME CALL AS THE ASSET
          NUMBER'S ON STEP 1.** Figure 47 marks it `*`; `stepValid(3)` asks only
          for the unit and its install date, and a clerk who knows the unit can
          pick it without naming the building first. Making it required is a
          behaviour change — and `AssetLifecycle.test.tsx` asserts today's rule
          — so it is reported rather than built. */}
      {values.destination === "unit" && (
        <>
          <SearchSelectField
            id="premises_id"
            label={t("assets.add.premises")}
            value={values.premises_id}
            options={props.premises}
            placeholder={t("assets.add.premisesPlaceholder")}
            onChange={(value) => props.onChange({ ...values, premises_id: value, unit_id: "" })}
          />
        </>
      )}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        {values.destination === "unit" && (
          <SearchSelectField
            id="unit_id"
            label={t("assets.reassign.unit")}
            required
            value={values.unit_id}
            options={props.units}
            placeholder={t("assets.reassign.unitPlaceholder")}
            onChange={(value) => props.onChange({ ...values, unit_id: value })}
          />
        )}
        <DatePickerField
          id="install_date"
          label={t("assets.form.installDate")}
          value={values.install_date}
          dateFormat={props.dateFormat}
          onChange={(value) => props.onChange({ ...values, install_date: value })}
          // ⚠ **THE DRAWING'S HELPER IS *"Not in the future."* AND IT IS NOT
          // BUILT.** That sentence states a constraint the product does not
          // have: `_validate_asset` accepts any `install_date`, and the only
          // future-date refusal in this module is the maintenance date
          // (`services.py:1468`). Writing it here would put a guarantee on
          // screen that nothing enforces — hard-won law 1 — and enforcing it
          // client-side would invent a rule nobody ruled. The sentence that
          // stands is the one that is true. Reported, not built.
          help={t("assets.add.installDateHelp")}
        />
        {/* ⚠ **THE OPENING READ IS NOT HERE ANY MORE, AND THAT IS THE
            RULING.** It stood on this step as a DISABLED box whose helper said
            a reading *"cannot be captured here"*. PO, 2026-09-12: *"Build it as
            drawn - move it to step 2, beside the multiplier, register digits
            and the warning"* — so it is an enabled field on `MeasuringSpecStep`
            and the refusal it carried is gone with it.

            **DELETED rather than hidden or left disabled**, which is wave B
            lane 5's own written instruction and hard-won law 2's mirror: a
            control left behind with its `disabled` dropped is dead UI, and one
            left behind still refusing is a live refusal over a capability that
            shipped. A device has no register and no multiplier, so
            `DeviceSpecStep` gained nothing — the field went to exactly one
            step, not to both. */}
      </div>
      {/* Read route / sequence: r10 draws both; NO columns exist — omitted
          and reported rather than captured into nowhere. */}
      {/* ⛔ **WHERE A TECHNICIAN WILL FIND IT — full width, because it is a
          sentence** (figure 47, marked NEW, and p118's *Spacing* row says so in
          those words). `location_note` is a column `POST /assets` has always
          accepted and no add screen could write; the only writer was the
          asset's own Lifecycle edit dialog, which a person reaches AFTER the
          asset exists — by which time the installer standing in the plant room
          has gone.

          ⚠ **IT IS A LOCATION NOTE AND NEVER AN ADDRESS.** Hard rule 8 puts the
          address on `premises` and makes every other entity walk to it; p118's
          *Words* row states the same constraint from the drawing's side. */}
      <TextField
        id="location_note"
        label={t("assets.spec.locationNote")}
        value={values.location_note}
        onChange={(value) => props.onChange({ ...values, location_note: value })}
        help={t("assets.panel.help.locationNote")}
      />
      {/* **`OR LEAVE IT UNASSIGNED` — a TITLED box, not a bare sentence.**
          Figure 47 draws it with a rule down its left edge and that heading
          above the line; it rendered as a plain `Note` carrying only the body,
          so the one thing the drawing uses to make *leaving it unassigned* read
          as a first-class answer was missing. Same kit panel as the meter-face
          callout on step 2, and the same recorded divergence about the title's
          type. */}
      <Panel as="section" tone="emergency" title={t("assets.add.inventoryNoteTitle")}>
        <p className="m-0 text-base">{t("assets.add.inventoryNote")}</p>
      </Panel>
      {/* ⚠ **THE WORK-ORDER CHECKBOX LEFT THIS STEP FOR THE REVIEW.** Figure 47
          does not draw it and figure 49 does, immediately above the commit —
          which is where it belongs: it decides where the clerk GOES after the
          asset is created, so it is a fact about the commit and not about the
          assignment. See `ReviewStep`. */}
    </div>
  );
}

function LifecycleStep(props: {
  t: Translator;
  values: AddWizardValues;
  onChange: (values: AddWizardValues) => void;
  measuring: boolean;
  dateFormat: import("@/components/DateCell").RegionalDateFormat;
  today: string;
}) {
  const { t, values } = props;
  return (
    <div className="flex flex-col gap-5">
      <p className="m-0 text-base">{t("assets.add.lifecycleLede")}</p>
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        {/* D5: supplier is FREE TEXT — no reference list exists yet. Figure 48
            draws it with no helper either, which is the one field on this step
            the code and the drawing already agreed about. */}
        <TextField
          id="supplier"
          label={t("assets.supplier")}
          value={values.supplier}
          onChange={(value) => props.onChange({ ...values, supplier: value })}
        />
        <TextField
          id="purchase_cost"
          label={t("assets.valuation.purchaseCost")}
          numeric
          value={values.purchase_cost}
          onChange={(value) => props.onChange({ ...values, purchase_cost: value })}
          // Hard rule 2: stored to 4 decimals, displayed 2 — entered as typed.
          // The drawing spells the figures out and the asset's Cost & value
          // dialog already carries that spelling; one string, two screens.
          help={t("assets.panel.help.purchaseCost")}
        />
      </div>
      {/* ⛔ **THE RIGHT-HAND CELL OF THIS ROW IS THE DEPRECIATION METHOD AND IT
          IS NOT BUILT.** Figure 48 draws a dropdown reading *Straight line*,
          annotated in the drawing's own hand `NONE · NO LIST EXISTS` — and that
          annotation is the work. The column is real, `POST /assets` accepts it
          and the present value is computed from it, but **there is no ratified
          vocabulary anywhere in this repo** to put in a picker: no `choices`,
          no lookup list, no business rule naming the methods. Inventing four
          words here would put an unratified accounting term into a book-value
          calculation, which is not a screen lane's call. Reported. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <DatePickerField
          id="purchase_date"
          label={t("assets.add.purchaseDate")}
          value={values.purchase_date}
          prefill={props.today === "" ? undefined : props.today}
          dateFormat={props.dateFormat}
          // Drawn with a helper; the field carried none.
          help={t("assets.panel.help.purchaseDate")}
          onChange={(value) => props.onChange({ ...values, purchase_date: value })}
        />
      </div>
      {/* ⚠ **THE PAIRING IS THE DRAWING'S: `Expected life | Warranty end`, THEN
          `Test interval | Certification due`.** The step paired expected life
          with the certification date and the warranty with the purchase date,
          which reads as four unrelated boxes; figure 48 pairs the two facts
          about HOW LONG IT LASTS and then the two about WHEN IT IS LOOKED AT.

          ⚠ **`Expected life`, not `Expected life (years)` — the unit is in the
          helper.** B14 rule 33 caps a label at three words and puts the unit
          where the drawing puts it, and the asset's own Lifecycle dialog
          already says *"In years."* in exactly those words. */}
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <TextField
          id="expected_life_years"
          label={t("assets.add.expectedLife")}
          numeric
          value={values.expected_life_years}
          onChange={(value) => props.onChange({ ...values, expected_life_years: value })}
          help={t("assets.panel.help.expectedLife")}
        />
        {/* r10 draws a "Warranty term" SELECT; no term column exists — the
            stored fact is the end DATE, so that is what is asked for. The
            LABEL is figure 48's `Warranty end`; `assets.valuation.coverEnds`
            ("Cover ends") stays where it is, on the asset's own Overview. */}
        <DatePickerField
          id="warranty_end"
          label={t("assets.add.warrantyEnd")}
          value={values.warranty_end}
          dateFormat={props.dateFormat}
          help={t("assets.add.warrantyEndHelp")}
          onChange={(value) => props.onChange({ ...values, warranty_end: value })}
        />
      </div>
      {/* ⚠ **MEASURING ONLY, BOTH FIELDS.** Figure 46 puts a device's test
          interval and certification due on its SPECIFICATION step, and figure
          48 is the meter variant of this one. One field, one step, per class —
          never the same box on two steps. */}
      {props.measuring && (
        <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
          {/* See `DeviceSpecStep` for why this is a number and not a chooser:
              the select offered 12 / 24 / 60 while its own helper named 96. */}
          <TextField
            id="test_interval_months"
            label={t("assets.spec.testInterval")}
            numeric
            value={values.test_interval_months}
            placeholder={t("assets.add.testCadenceDefault")}
            onChange={(value) => props.onChange({ ...values, test_interval_months: value })}
            help={t("assets.panel.help.testInterval")}
          />
          <DatePickerField
            id="certification_due"
            label={t("assets.add.certificationDue")}
            value={values.certification_due}
            dateFormat={props.dateFormat}
            // B14 rule 33 — `assets.add.certificationDueHelp` is eleven words
            // in one sentence. Five, and the asset's own dialog already has it.
            help={t("assets.panel.help.certificationDue")}
            onChange={(value) => props.onChange({ ...values, certification_due: value })}
          />
        </div>
      )}
      {/* ⚠ **THE SUMMARY BOX IS GONE, AND THAT IS THE RECONCILIATION RATHER
          THAN A DELETION.** Figure 48 draws no summary on this step: the four
          facts it carried — the asset line, the multiplier, the opening read
          and the destination as a word — were a STAND-IN for the review step
          the wizard did not have. Screen 32 is that step, it shows those four
          facts among about fourteen, and it groups them the way the asset's own
          Overview groups them. Leaving both would say the same thing twice, one
          press apart, and neither copy would be the authoritative one.

          `DEF-MET-4990`'s rule travels WITH the facts: the review reads the
          asset type's and the service's NAMES and never their lookup codes
          (B14 rule 31), and `data-add-summary` moves to the review's own panel
          grid so the check that watches for a code has something to read. */}
    </div>
  );
}

// ── Screen 32 · Add an asset · 5 Review & add ──────────────────────────────

/**
 * The `<dl>` that draws one panel's facts — label left, value right of it, on
 * one column edge.
 *
 * ⚠ **IT IS THE ASSET OVERVIEW'S OWN STRING, CHARACTER FOR CHARACTER**
 * (`AssetDetailPage.tsx`'s `FACTS`). p121 says why in one line: the review is
 * *"grouped the way the **Overview** groups it — Identity · Assignment ·
 * Measurement · Cost & value — so a person reviews in the shape they will later
 * read."* A second, nearly-identical grid would make that sentence false the
 * first time either one was tuned.
 *
 * ⚠ **IT IS NOT LIFTED INTO THE SHARED KIT, DELIBERATELY.** The honest move is
 * one exported constant read by both screens — and `FACTS` is private to a file
 * another lane is editing this hour, so exporting it is a change to a file this
 * lane does not own. Reported with the one-line fix rather than done.
 */
const REVIEW_FACTS =
  "m-0 grid grid-cols-[minmax(150px,auto)_1fr] gap-x-3 gap-y-2 text-base " +
  "[&_dt]:font-heading [&_dt]:font-semibold " +
  "[&_dt]:text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] [&_dd]:m-0";

/** An answer that was left blank. The drawing writes a dash, not a word. */
const BLANK = "—";

function ReviewFact(props: { label: string; value: string }) {
  return (
    <>
      <dt>{props.label}</dt>
      <dd>{props.value === "" ? BLANK : props.value}</dd>
    </>
  );
}

/**
 * **Screen 32 — the step a clerk commits from.** Blueprint pages 120–121,
 * figure 49.
 *
 * Four read-only panels in two columns, the multiplier warning once more, the
 * work-order choice, and then the frame's `Add asset ✓`. p121's *Primary
 * action* row: *"the only control in the whole flow that writes anything."*
 *
 * ⚠ **NOTHING HERE IS EDITABLE AND THAT IS THE POINT.** Every value is read
 * back from `AddWizardValues`, so a wrong one is corrected by walking back to
 * the step that owns it — which is what the numbered rail is for. A second
 * editable copy of a field is two places for one fact.
 *
 * ⚠ **EVERY VALUE IS A WORD, NEVER A CODE OR AN ID (B14 rule 31).** The asset
 * type, the read method, the service, the premises and the unit all arrive here
 * as the NAME their own picker displayed, resolved once on the component;
 * `DEF-MET-4990` is what happens when a summary reads the form's raw value
 * instead — a clerk checking their answers saw `meter` and `water`.
 */
function ReviewStep(props: {
  t: Translator;
  values: AddWizardValues;
  onChange: (values: AddWizardValues) => void;
  measuring: boolean;
  /** Resolved names, never codes — see the header. */
  typeName: string;
  readMethodName: string;
  serviceName: string;
  premisesName: string;
  unitName: string;
  classLabel: string;
  suggested: string | null;
  timeZone: string;
  dateFormat: import("@/components/DateCell").RegionalDateFormat;
}) {
  const { t, values } = props;
  const showDate = (value: string): string =>
    value === "" ? "" : formatDate(value, props.timeZone, props.dateFormat);
  // The drawing's `Asset type  Meter · AMI` — the catalogue entry and how it is
  // read, folded into one row, each leg absent rather than dashed when unset.
  const typeLine = [props.typeName, props.readMethodName].filter((part) => part !== "").join(" · ");
  return (
    <div className="flex flex-col gap-5">
      {/* ⚠ **THE RESERVATION SENTENCE, IN TWO SENTENCES OF FIVE WORDS.** The
          drawing writes *"Nothing is created until you press Add asset. The
          number below is reserved at that moment, not before."* — eight words
          then twelve. B14 rule 33 caps a CONSEQUENCE stated before an
          irreversible act at six words a sentence, at most two, *"never cut
          below clarity"*, and B14 rule 41 says a drawing that contradicts a
          signed rule is REPORTED rather than built. Both facts survive the cut:
          pressing the button is what creates it, and the number is taken then.
          The divergence is in the lane report. */}
      <p className="m-0 text-base">{t("assets.add.reviewLine")}</p>
      {/* Two columns of panels — Identity and Assignment left, Measurement and
          Cost & value right (p121: *"two columns of panels at 16"*). At one
          column they stack in that same reading order.

          `data-add-summary` is the hook `DEF-MET-4990`'s check reads. It moved
          here with the facts it was watching; see `LifecycleStep`. */}
      <div
        className="grid grid-cols-2 gap-4 max-md:grid-cols-1"
        data-add-summary=""
        data-add-review=""
      >
        <div className="flex flex-col">
          <Panel as="section" title={t("assets.add.step.identity")}>
            <dl className={REVIEW_FACTS}>
              <ReviewFact
                label={t("assets.add.assetNumber")}
                // A blank number is not missing — the series will supply one,
                // which is what this sentence has always said on step 4.
                value={values.asset_no.trim() || props.suggested || t("assets.add.summaryPending")}
              />
              <ReviewFact label={t("assets.add.reviewClass")} value={props.classLabel} />
              <ReviewFact label={t("assets.col.assetType")} value={typeLine} />
              {/* ⚠ **THE UTILITY SERVICE IS NOT ON FIGURE 49 AND IT IS KEPT
                  HERE DELIBERATELY — the one addition this step makes to the
                  drawn panel, and it is stated rather than slipped in.**

                  The drawn Identity panel is five rows: number, class, type,
                  serial, external reference. The service is on none of them —
                  and the service is the fact the drawing itself marks
                  `affects billing` on step 1, one of the five billing-affecting
                  fields (`multiplier · unit · net_metering · service ·
                  size_class`), and the ONE thing the step-4 summary this screen
                  replaces has always read back as a word. Dropping it would
                  make the last screen before the only write in the flow silent
                  about which service the meter bills under, on the authority of
                  a panel that does not say why it is absent.

                  So it stays, next to the type, and the difference goes to the
                  report for the PO rather than being smoothed over either way.
                  `DEF-MET-4990`'s rule rides with it: the NAME, never the code. */}
              <ReviewFact label={t("assets.form.utilityService")} value={props.serviceName} />
              <ReviewFact label={t("assets.form.serial")} value={values.serial_no.trim()} />
              {/* Drawn on figure 49 reading `—`, which is the shape of an
                  answer nobody gave. It is absent on a sub-meter for the same
                  reason it is absent from step 1 there. */}
              {values.klass !== "sub_meters" && (
                <ReviewFact
                  label={t("assets.spec.externalRef")}
                  value={values.external_ref.trim()}
                />
              )}
            </dl>
          </Panel>
          <Panel as="section" title={t("assets.add.step.assignment")}>
            <dl className={REVIEW_FACTS}>
              {values.destination === "unit" ? (
                <>
                  <ReviewFact label={t("assets.add.premises")} value={props.premisesName} />
                  <ReviewFact label={t("assets.reassign.unit")} value={props.unitName} />
                </>
              ) : (
                // The drawing draws the assigned case only. An asset left in
                // inventory has no premises and no unit to show, and two
                // dashes would read as two things somebody forgot; the one
                // row says what was actually chosen.
                <ReviewFact
                  label={t("assets.add.summaryDestination")}
                  value={t("assets.add.intoInventory")}
                />
              )}
              <ReviewFact
                label={t("assets.form.installDate")}
                value={showDate(values.install_date)}
              />
            </dl>
          </Panel>
        </div>
        <div className="flex flex-col">
          {/* ⚠ **NO MEASUREMENT PANEL ON A DEVICE.** Figure 46 states the rule
              for its own step and it governs here too: *"No multiplier, no unit
              of measure, no register digits and no opening read — a device
              stores no reading, so the fields are ABSENT rather than dashed."*
              The asset's Overview does the same thing with the same predicate
              (`assetOverviewPanelsFor`), which is what p121 asks for. */}
          {props.measuring && (
            <Panel as="section" title={t("assets.add.reviewMeasurement")}>
              <dl className={REVIEW_FACTS}>
                <ReviewFact
                  label={t("assets.form.multiplier")}
                  value={t("assets.multiplierShort", { multiplier: values.multiplier || "1" })}
                />
                <ReviewFact label={t("assets.form.uom")} value={values.unit.trim()} />
                <ReviewFact
                  label={t("assets.spec.registerDigits")}
                  value={values.register_digits.trim()}
                />
                {/* `AST-B-14` — the one value on this form written OUTSIDE the
                    asset. It is on the last screen before the commit because
                    the commit is where it is written: a refused reading takes
                    the asset with it. */}
                <ReviewFact
                  label={t("assets.add.openingRead")}
                  value={values.opening_read.trim()}
                />
              </dl>
            </Panel>
          )}
          <Panel as="section" title={t("assets.add.reviewCost")}>
            <dl className={REVIEW_FACTS}>
              {/* ⚠ **SHOWN EXACTLY AS TYPED, AND THE DRAWING'S `$182.00` IS
                  NOT.** Hard rule 2 displays money to two decimals in the
                  tenant's currency — and this step has no currency to use:
                  `MoneyCell` requires an ISO code served WITH an amount, the
                  asset does not exist yet, and `useRegional` carries a time
                  zone and a date format and no currency at all. Inventing a
                  symbol would be picking a currency for a utility. The figure
                  the clerk typed a moment ago is read back to them unchanged,
                  and the gap is reported. */}
              <ReviewFact
                label={t("assets.valuation.purchaseCost")}
                value={values.purchase_cost.trim()}
              />
              <ReviewFact
                label={t("assets.add.expectedLife")}
                value={
                  values.expected_life_years.trim() === ""
                    ? ""
                    : t("assets.add.reviewYears", { years: values.expected_life_years.trim() })
                }
              />
            </dl>
          </Panel>
        </div>
      </div>
      {/* **THE MULTIPLIER WARNING, ONCE MORE, AND p121 SAYS WHY:** *"it repeats
          the multiplier warning, because this is the last moment it can
          matter."* Measuring kinds only — a device has no multiplier for the
          sentence to be about. */}
      {props.measuring && (
        <Panel as="section" tone="emergency" title={t("assets.add.meterFaceTitle")}>
          <p className="m-0 text-base">{t("assets.add.multiplierWarning")}</p>
        </Panel>
      )}
      {/* r10's "Raise an installation work order" — LIVE since wave M, and it
          sits HERE now rather than on step 3, which is where figure 49 draws
          it: it decides where the clerk goes AFTER the commit. The asset is
          CREATED first and the door opens on its id, because a job cannot be
          anchored to a meter that does not exist yet.

          ⚠ **THE DRAWING'S WORDS ARE `Raise a field work order to install it`
          AND THE SHORTER LABEL STANDS.** B14 rule 33 caps a label at three
          words; neither wording reaches that, and the eight-word one is further
          from it than the five-word one already in the catalogues. Rule 41
          sends a drawing that contradicts a signed rule to the report rather
          than to the screen. */}
      <RaiseWorkOrderCheckbox
        label={t("assets.add.workOrder")}
        checked={values.raise_work_order}
        onChange={(checked) => props.onChange({ ...values, raise_work_order: checked })}
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-002@9d8d058 (EP-AST-01 add-asset story — SHAPE amended per §10-D8) · CR-028@B16 (04-docs/02-decisions/16-cr028-assets-design.md §5.2 as amended + Item 1d/3d + §10 D3/D7/D8)
// generated: 2026-08-22 by the CR-028 AST-W4 lane (T1: the AST-05 4-step full-page wizard; the S51 create-mode modal retires from AssetRegistryPage the same commit)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AssetFlowPages.test.tsx — step validation, payload shape, availability states) · trace_lint✔
// exceptions: E3 the DEMAND flag r10 draws has no column — NOTHING renders (reported) · E3 CLOSED 2026-09-12 (CR-092 wave C lane 2, AST-B-14): this line read "the OPENING READ renders DISABLED with its reason: no published seam lets assets write a meter_reads row at create". The PO overruled the seam argument — "Build it as drawn - move it to step 2, beside the multiplier, register digits and the warning" — and the seam was never the blocker, only unwritten: metering now publishes capture_opening_read beside capture_final_read, assets/seams.py resolves it, and _create_asset_inner writes the read inside the create's own transaction so a refused reading takes the asset with it. The control was DELETED from AssignmentStep rather than un-disabled there · E3 READ ROUTE/SEQUENCE have no columns — omitted, reported · E4 r10's "Warranty term" select has no term column; the stored `warranty_end` DATE is captured instead · E4 r10 draws multi-select service checkboxes; the schema stores ONE service per asset (service point), so one entry renders — the shipped modal's own posture · E4 the summary box OMITS r10's "Cost · Posts to 5300 O&M on install" line (hard rule 5 / §10-D3) and its "Appears in Inventory · forecast · calendar" line (those tabs are AST-W5's) · E3 CLOSED 2026-09-12 (CR-092 lane 5, DEF-MET-4980/4981/4982): the service entry was FREE TEXT and this line said "GET /settings/services is System-Admin-only", which is FALSE and was false when it was written — apps/tenancy/api.py:419 decorates it @permission_classes([AnyTenantRole]), commented "clerks read-only; writes below", and 25 non-test front-end files already call it, AssetRegistryPage.tsx:507 among them. The field is now a SelectField over the tenant's enabled services and is marked required for a measuring class, as _check_measuring_requirements requires it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
