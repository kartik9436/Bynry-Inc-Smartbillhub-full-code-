// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-003 (S18 New Account wizard — FIVE steps since 2026-09-13)
//           Screens: S18 (entered from the S17 "+ New account" primary)
//           AMENDED 2026-08-15 (tenant custom-fields lane): US-SHL-015 (EP-SHL-07 — S18 captures the tenant's own fields; the payload
//           carries `custom_data` only when something was recorded)
// Rules:    BR-CUS-012 (the confirmed account attribute set) ·
//           BR-CUS-017 (at most ONE active account per unit) ·
//           BR-CUS-018 (six-step guided page; a new account is a DRAFT that is
//           never billed, derives no occupancy and blocks no unit) ·
//           BR-CUS-019 (the step-1 duplicate check is advisory) ·
//           BR-CUS-020 (unit pickers offer only vacant units) ·
//           BR-CUS-021 (initial reads commit through the metering service) ·
//           BR-CUS-022 (the first bill starts at the service start date) ·
//           BR-CUS-023 (the deposit is a LOOKUP from the plan deposit schedule) ·
//           BR-CUS-028 (the step-4 preference set) · BR-CUS-029 (the account
//           plan snapshot has NO table) · BR-CUS-045 (contact PII — the last
//           four of a government id only) · BR-CUS-054 (the first-class
//           customer entity has no table) · BR-CUS-058 (the credit tier is
//           COMPUTED — there is no input path) · BR-CUS-059 (autopay is
//           CAPTURE-ONLY in v1) · BR-CUS-060 (bill delivery day is DROPPED) ·
//           BR-MET-040 (a plan is REQUIRED at activation; a unit without one
//           blocks with a message) · BR-SHL-018 (wizard rail semantics) ·
//           BR-SHL-019 (ONE transactional commit) · BR-SHL-025 (a forbidden
//           control is disabled WITH its reason) · BR-SHL-033 (the long-list
//           picker is searchable; dates use the date control)
// ───────────────────────────────────────────────────────
// S18 — the guided New account page. `POST /accounts` was served with no screen
// creating one; this is that screen, on the SHARED WizardFrame (B13 §1) — the
// step rail, the Back/Continue row, the ✓ confirm and its single-flight commit
// all belong to the frame. Nothing here hand-rolls a stepper.
//
// ⚠ **FIVE STEPS, AND IT WAS SIX UNTIL 2026-09-13 (`DEF-CUS-5185`).** The
// blueprint carries the PO's ruling verbatim: *"there should not be any step to
// select a plan as plan is already attached on the unit itself. So whenever the
// unit is selected, show all the details."* The Plan step collected nothing, and
// its own copy explained why it should not exist. It is deleted; what it
// CHECKED — `BR-MET-040`, an activation on a plan-less unit is refused — moved
// into the unit panel on step 2, where the clerk is choosing the unit that
// causes it, rather than one click later.
//
// Three absences, each stated where a user would look for the control:
//
//   · No duplicate check and no customer record (BR-CUS-019/054): `customers`
//     and `customer_accounts` have no tables, so step 1 writes ONE contact on
//     ONE account. `customer` and `customer_id` are refused fields.
//   · No initial meter reads (BR-CUS-021): `initial_reads` is refused — reads
//     commit through metering's own service (B1), which is the W2 reads lane.
//   · ⚠ **PAPERLESS AND SMS ARE NOW OFFERED, AND THIS LINE SAID THEY COULD NOT
//     BE UNTIL 2026-09-13 (`DEF-CUS-5184`).** Both columns were built on
//     2026-08-31 (`CR-052` task 14, migration `customers/0034`) and both are in
//     `CREATE_FIELDS`; `createAccountPayload` had been sending them to a form
//     nothing could set. What remains unbuilt is budget billing and statement
//     language (PROPOSED-SCHEMA). Autopay IS accepted and IS capture-only
//     (BR-CUS-059).
//   · No bill-delivery-day selector: DROPPED by BR-CUS-060 — cycles decide bill
//     dates. It is not "missing", it is not coming.
//
// The prototype's page head carries "Save draft & exit" beside the step-6
// "Save as draft" / "Create account ✓" pair. Both become ONE choice on the
// review step, so this flow keeps exactly one transactional commit
// (BR-SHL-019) instead of two commit buttons racing each other.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { createAccount, getUnits } from "@/api/endpoints";
import { Button } from "@/components/Button";
// Hard rule 2 — money displays to TWO decimals. `MoneyCell` with the tenant's
// code where the shell published one (`DEF-CUS-5114`); `formatMoneyInput`, the
// half of the pair that demands no currency, only where nothing was published.
import { MoneyCell, formatMoneyInput } from "@/components/MoneyCell";
import { useTenantCurrency } from "@/components/TenantRegional";
import { CustomFieldsInput, missingRequiredLabels, useCustomFieldRegistry } from "@/components/CustomFields";
import type { AccountWriteResult, UnitRow } from "@/api/endpoints";
import type { RegionalDateFormat } from "@/components/DateCell";
import {
  CheckboxField,
  DatePickerField,
  SearchSelectField,
  SegmentedField,
  TextField,
} from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { Panel } from "@/components/Panel";
// `GET /units/{id}/pricing` — the ONE place that route is spelled in this repo
// (`UnitPricingPanel`'s own note). The step-2 unit panel reads the plan through
// it rather than rendering the UUID `UnitRow` carries, which B14 rule 31 forbids.
import { getUnitPricing } from "./UnitPricingPanel";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import {
  CELL_FULL,
  Fact,
  FactList,
  ServiceTags,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ACCOUNTS_PERMISSION,
  ACCOUNTS_ROUTE,
  ACTIVE_STATUS_CODE,
  DASHBOARD_ROUTE,
  DRAFT_STATUS_CODE,
  Dash,
  NotRecorded,
  accountCategoryName,
  accountDetailPath,
  accountSubtypeName,
  useAccountCategories,
  useAccountSubtypes,
} from "./customersShared";

import {
  DepositReviewRows,
  DepositStep,
  type DepositForm,
  depositPayload,
  depositProblem,
  emptyDepositForm,
} from "./depositCapability";

import { hydrateForm } from "./wizardPark";
import { CustomerFields, customerStepProblem } from "./CustomerFields";
import { PortalLanguageField } from "./PortalLanguageField";

import "./customers.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * The FIVE drawn steps, in the blueprint's own order.
 *
 * ⚠ **THIS WAS SIX UNTIL `DEF-CUS-5185`, AND THE SIXTH WAS `plan`.** The
 * blueprint (`03-new-account-wizard.md`, pages 60–65) carries the PO's ruling
 * verbatim: *"there should not be any step to select a plan as plan is already
 * attached on the unit itself. So whenever the unit is selected, show all the
 * details."* A step of a six-step wizard that collected NOTHING, whose only
 * value was derived from the step before it, and whose own copy said so — *"the
 * plan is read from the unit and is not stored on the account"*.
 *
 * What it checked is not lost and must not be: `BR-MET-040` fails an activation
 * on a unit with no plan, and saying so AFTER five steps of typing is the thing
 * the check exists to prevent. It moved UP, into the unit panel on step 2,
 * where the clerk is choosing the unit that causes it.
 *
 * ⚠ **TWO NAMES PER STEP, AND BOTH ARE DRAWN.** `railKey` is the cell in the
 * numbered rail; `lineKey` is the name in `Step N of 5 · …` under the title.
 * They differ on step 2 — the rail draws *Service address* on all five frames,
 * the step line draws *Unit*, and the review block heading reads *SERVICE
 * ADDRESS AND UNIT · STEP 2*. Rule 37 settles two frames disagreeing about a
 * FIGURE; this is a LABEL, so both are built as drawn rather than one being
 * read as a typo for the other.
 */
export const NEW_ACCOUNT_STEPS = [
  {
    id: "customer",
    railKey: "customers.newAccount.step.customer",
    lineKey: "customers.newAccount.step.customer",
    titleKey: "customers.newAccount.title",
  },
  {
    id: "unit",
    railKey: "customers.newAccount.step.unit",
    lineKey: "customers.newAccount.step.unitLine",
    titleKey: "customers.newAccount.title.unit",
  },
  {
    id: "preferences",
    railKey: "customers.newAccount.step.preferences",
    lineKey: "customers.newAccount.step.preferences",
    titleKey: "customers.newAccount.title.preferences",
  },
  {
    id: "deposit",
    railKey: "customers.newAccount.step.deposit",
    lineKey: "customers.newAccount.step.deposit",
    titleKey: "customers.newAccount.title.deposit",
  },
  {
    id: "review",
    railKey: "customers.newAccount.step.review",
    lineKey: "customers.newAccount.step.review",
    titleKey: "customers.newAccount.title.review",
  },
] as const;

export const NEW_ACCOUNT_STEP_IDS = NEW_ACCOUNT_STEPS.map((step) => step.id);
export const STEP_PARAM = "step";
export const NEW_ACCOUNT_STEP_COUNT = NEW_ACCOUNT_STEPS.length;

/** BR-SHL-011's spirit: an out-of-range `?step=` clamps, it never errors. */
export function stepFromParam(raw: string | null): number {
  const parsed = Number(raw ?? "1");
  if (!Number.isInteger(parsed)) {
    return 1;
  }
  return Math.min(Math.max(1, parsed), NEW_ACCOUNT_STEP_COUNT);
}

/**
 * BR-CUS-018: what the ✓ writes. "Activate" hands the server an occupying
 * status, which takes the BR-CUS-017 road (locks the unit scope, refuses 409 if
 * it is taken, requires the unit's plan per BR-MET-040). "Draft" leaves the
 * seeded `pending_activation`, which blocks nothing.
 */
export const CREATE_MODES = ["activate", "draft"] as const;
export type CreateMode = (typeof CREATE_MODES)[number];

export interface CustomerForm {
  account_type: string;
  /**
   * `BR-CUS-067` — the SECOND level of the category tree, and **OPTIONAL**:
   * `accounts.account_subtype_id` is nullable by design, so `""` is a real
   * answer and never a gap to be filled.
   *
   * ⚠ **THE CODE, NOT THE ID** (B14 rule 31 — the picker shows the NAME). It
   * matches `AccountDetail.account_subtype` and the edit dialog over this same
   * column, so one account's sub-type is spelt one way on every screen that
   * writes it. `services._resolve_account_subtype` accepts either.
   */
  account_subtype: string;
  full_name: string;
  email: string;
  phone: string;
  dob: string;
  gov_id_last4: string;
  /**
   * `BR-CUS-1022` / `BR-CUS-1023` — is this a PERSON or a COMPANY? It decides
   * which identifier counts, so it is not decoration and it is not defaulted
   * here: an unstated kind is a real answer that mints no customer number and
   * says so, and a pre-selected `person` would make that answer invisible.
   */
  customer_kind: string;
  /** A person's, and only a person's (`BR-CUS-1022` — refused for a company). */
  ssn: string;
  driving_licence: string;
  /** A business's, and only a business's. */
  tax_id: string;
  /**
   * `DEF-CUS-6359` (PO 2026-09-23) — *Same as service address*, ticked by
   * default. Ticked writes NO mailing row, which is what "same as service" has
   * always meant (B2 §2, hard rule 8's `kind='mailing'` exception); unticked,
   * the five US fields below are the account's mailing address.
   */
  mailing_same: boolean;
  mailing_line1: string;
  /** Apt, suite or unit — the kit's `UsAddressFields` second line. */
  mailing_line2: string;
  mailing_city: string;
  /** The two-letter state code the kit's picker writes. */
  mailing_state: string;
  /** Five digits or ZIP+4 (`usZipIsValid`). */
  mailing_postal_code: string;
  /** `DEF-CUS-9169` — the utility's own mailing-address fields placed Input on
   *  New account (slot `S18` for `addresses`). Sent on the mailing row only,
   *  so ticking *Same as service address* sends none of them. */
  mailing_custom_data: Record<string, unknown>;
  /** `CR-161-BRC10` W4 — the utility's own CUSTOMER fields placed Input on New
   *  account (slot `S18` for `customers`). Sent inside the `customer` block,
   *  so they land on the customer (or merge onto a returning one), never on
   *  the account. Optional because the move-in and transfer forms share this
   *  shape and draw no customer fields. */
  customer_custom_data?: Record<string, unknown>;
}

/** `identity_match.KIND_*`, the server's own two words (B2 r9 #1). */
export const CUSTOMER_KIND_PERSON = "person";
export const CUSTOMER_KIND_COMPANY = "company";

/**
 * `BR-CUS-1023` — does what the clerk has typed earn a Customer number?
 *
 * ⚠ **THIS IS A HINT AND NEVER A GATE.** It changes no button and blocks no
 * step: the account opens either way, which is the ruling. It exists so the
 * refusal reaches the clerk **where they are typing** rather than after the
 * commit (the PO: *"never after the account is created"*). The SERVER's answer
 * is the one that counts and is shown on the review step beside it.
 */
export function customerNumberShortfall(values: CustomerForm): string | null {
  if (values.full_name.trim() === "") return "customers.customer.display_name_required";
  if (values.customer_kind === "") return "customers.customer.identity_kind_required";
  if (values.customer_kind === CUSTOMER_KIND_COMPANY) {
    // A phone is capturable for a business and does NOT create one: the PO's
    // list for a company names the Tax ID and nothing else.
    return values.tax_id.trim() === ""
      ? "customers.customer.identity_required_company"
      : null;
  }
  const hasOne =
    values.ssn.trim() !== "" ||
    values.driving_licence.trim() !== "" ||
    values.phone.trim() !== "";
  return hasOne ? null : "customers.customer.identity_required_person";
}

/**
 * `BR-CUS-1024` (PO 2026-09-01) — does what the clerk has typed earn an
 * **ACCOUNT**? Returns the catalogue key of the one thing missing, or `null`.
 *
 * THIS IS A GATE, AND `customerNumberShortfall` ABOVE IS NOT. That one was
 * written this morning, when a missing identifier cost only the customer number
 * and the account opened regardless. The PO reversed it the same day: *"Without
 * identifier we cannot create Customer ID or master account ot regular
 * account"*. So the step cannot be left until the shortfall clears, and the
 * sentence says the ACCOUNT is what is waiting — telling a clerk "no customer
 * number yet" and then refusing their account is worse than silence.
 *
 * THE TEST IS THE SAME TEST; ONLY THE CONSEQUENCE MOVED. It reads
 * `customerNumberShortfall` rather than restating the rule, so the two can never
 * disagree about what counts as an identifier — a person needs a Social Security
 * number, a driving licence or a phone; a business needs its Tax ID.
 */
export const ACCOUNT_SHORTFALL_KEY: Record<string, string> = {
  "customers.customer.display_name_required": "customers.account.identity_name_required",
  "customers.customer.identity_kind_required": "customers.account.identity_kind_required",
  "customers.customer.identity_required_person": "customers.account.identity_required_person",
  "customers.customer.identity_required_company": "customers.account.identity_required_company",
};

export function accountIdentityShortfall(values: CustomerForm): string | null {
  const shortfall = customerNumberShortfall(values);
  return shortfall === null ? null : (ACCOUNT_SHORTFALL_KEY[shortfall] ?? shortfall);
}

/**
 * `CR-058` tasks 7 and 8 — **which of the three things happened**, as the server
 * said it, turned into the one sentence a clerk reads.
 *
 * The server answers `linked` / `created` / `none` in `customer_outcome` and
 * this maps it to copy. It is deliberately NOT inferred from whether a customer
 * number came back: a number is present for BOTH `linked` and `created`, and
 * those are the two a clerk most needs told apart — "this looks like a customer
 * you already have" is a different fact from "a new one was made", and only the
 * server knows which happened.
 */
export function customerOutcomeKey(
  result: Pick<AccountWriteResult, "customer_outcome"> | null,
): string | null {
  const outcome = result?.customer_outcome ?? null;
  if (outcome === "linked") return "customers.account.customer.linked";
  if (outcome === "created") return "customers.account.customer.created";
  if (outcome === "none") return "customers.account.customer.none";
  return null;
}

export interface UnitForm {
  unit_id: string;
  opened_at: string;
  /** `DEF-CUS-9170` — the utility's own SERVICE-AGREEMENT fields placed Input
   *  on New account (slot `S18`), typed once on this step, which lists the
   *  unit's services. The server writes them on every agreement the account
   *  opens; a draft opens none, so a draft never sends them. */
  service_custom_data?: Record<string, unknown>;
}

/** `DEF-CUS-9170` — true when the clerk typed a service field the account will
 *  not keep: a draft opens no service agreement. The review says so. */
export function serviceFieldsLostOnDraft(unit: UnitForm, mode: CreateMode): boolean {
  return (
    mode !== "activate" &&
    Object.values(unit.service_custom_data ?? {}).some(
      (value) =>
        value !== null && value !== undefined && value !== "" &&
        !(Array.isArray(value) && value.length === 0),
    )
  );
}

export interface PreferencesForm {
  autopay: boolean;
  /**
   * ⚠ **`BR-CUS-028`'s CAPTURE SET, AND THE REFUSAL THAT KEPT IT OFF EVERY
   * SCREEN EXPIRED ON 2026-08-31** (`CR-052` task 14, migration `customers
   * 0034`). Both columns are in `services.CREATE_FIELDS` AND `PATCH_FIELDS`
   * and have been writable for twelve days; `paperless` and `sms_reminders`
   * were removed from `REFUSED_FIELDS` in the same commit, whose comment says
   * *"a refusal whose reason has expired is hard-won law 1 in its second
   * form"*. The screens never caught up, which is the other half of that law.
   *
   * Collected here since `CR-094-BRC01` wave H, on the PO's ruling: *"Make it
   * as account preferences in that user can also select paperless billing.
   * that should also be available."*
   *
   * ⚠ **NEITHER ONE SWITCHES THE PRINTED BILL OFF — `BR-BIL-036`, and print is
   * the FLOOR.** They ADD a channel. The step says so in one sentence, because
   * a clerk who believes paperless replaces post will tell the customer their
   * bill has stopped coming.
   */
  paperless: boolean;
  sms_reminders: boolean;
  preferred_language: string;
  tax_exempt: boolean;
  tax_exempt_ref: string;
  tax_exempt_expires: string;
  /**
   * EP-TEN-09 / US-SHL-015 — the tenant's OWN fields, keyed by
   * `custom_field.key`. Empty until the tenant defines one; the server refuses
   * any key it does not hold a definition for, so a stale client cannot write
   * shadow data (TC-5).
   */
  custom_data: Record<string, unknown>;
}

export function emptyCustomerForm(): CustomerForm {
  return {
    // ⚠ **A DEFAULT, NOT A VOCABULARY (DEF-684).** This read
    // `ACCOUNT_CATEGORIES[0]`, which is one of the ways a superseded list
    // reached the screen. BR-CUS-094's seven begin with `residential` and the
    // ruling keeps it selectable;
    // `06-backend/tests/test_def_684_category_vocabulary.py` pins this literal
    // against `AccountType.SEVEN_CATEGORIES`, so a ruling that ever retires it
    // goes RED here instead of shipping a default the server refuses.
    account_type: "residential",
    // ⚠ **EMPTY, AND IT STAYS EMPTY UNLESS A CLERK ANSWERS.** Unlike the
    // category above there is no defensible default: the tenant defines this
    // list, `parent_required` ties every row to one category, and a
    // pre-selected child would write a classification nobody chose onto every
    // account created in one pass. The column is nullable for exactly this.
    account_subtype: "",
    full_name: "",
    email: "",
    phone: "",
    dob: "",
    gov_id_last4: "",
    // ⚠ **EMPTY, NOT `person` (`BR-CUS-1022`).** A pre-selected kind is the
    // silent default the ruling of 2026-09-01 closed: it would judge a business
    // by a date of birth it has not got and file its Tax ID nowhere.
    customer_kind: "",
    ssn: "",
    driving_licence: "",
    tax_id: "",
    mailing_same: true,
    mailing_line1: "",
    mailing_line2: "",
    mailing_city: "",
    mailing_state: "",
    mailing_postal_code: "",
    mailing_custom_data: {},
    customer_custom_data: {},
  };
}

/**
 * The `addresses` block both wizards send, or `null` — `DEF-CUS-6359`.
 *
 * `null` when *Same as service address* is ticked, and when it is unticked with
 * no street typed: an empty block would claim a mailing address that is not
 * there. One builder for S18 and S19, so the two doors cannot disagree.
 */
export function mailingAddressFor(customer: CustomerForm): Record<string, unknown> | null {
  if (customer.mailing_same) return null;
  const line1 = customer.mailing_line1.trim();
  if (line1 === "") return null;
  const block: Record<string, unknown> = {
    kind: "mailing",
    line1,
    city: customer.mailing_city.trim(),
    state: customer.mailing_state.trim(),
    postal_code: customer.mailing_postal_code.trim(),
  };
  const line2 = customer.mailing_line2.trim();
  if (line2 !== "") block.line2 = line2;
  // `DEF-CUS-9169` — only when something was typed. The server checks the row
  // as the `S18` slot either way, so a required field placed there still
  // needs its answer; the move-in never fills this and sends exactly what it did.
  if (Object.keys(customer.mailing_custom_data ?? {}).length > 0) {
    block.custom_data = customer.mailing_custom_data;
  }
  return block;
}

/**
 * A parked draft's customer, with one migration: a draft written before
 * `mailing_same` existed and holding a street is a mailing address somebody
 * typed, so it opens UNTICKED rather than silently dropping it.
 */
export function hydrateCustomerForm(raw: unknown): CustomerForm {
  const form = hydrateForm(emptyCustomerForm(), raw);
  const source = (raw !== null && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  if (!("mailing_same" in source) && form.mailing_line1.trim() !== "") {
    return { ...form, mailing_same: false };
  }
  return form;
}

export function emptyPreferencesForm(): PreferencesForm {
  return {
    autopay: false,
    // Both default OFF: not electing is the safe answer and the one every
    // account in the product carries (`customers 0034`'s own note).
    paperless: false,
    sms_reminders: false,
    preferred_language: "",
    tax_exempt: false,
    tax_exempt_ref: "",
    tax_exempt_expires: "",
    custom_data: {},
  };
}

/** BR-CUS-020: only VACANT units may be offered, and only the server decides. */
export function vacantUnitOptions(
  rows: readonly UnitRow[] | undefined,
): { value: string; label: string }[] {
  return (rows ?? []).map((row) => ({
    value: row.id,
    label: [row.premise_address ?? row.premise_no, row.unit_no ?? row.label]
      .filter((part) => part !== null && part !== undefined && part !== "")
      .join(" · "),
  }));
}

/**
 * The `customer` block both wizards send — S18's create and S19's move-in.
 *
 * ⚠ **THIS SCREEN SENT NO `customer` BLOCK AT ALL UNTIL 2026-09-01** — the
 * server has accepted one since `CR-056` W3 and nothing posted it (hard-won law
 * 2: built is not wired; filed as `DEF-2818`). Everything the clerk typed went
 * into the CONTACT, so every account opened at the counter had a blank customer
 * column, which is the exact state `CR-056` §4 measured. **`MoveInWizard` had
 * the same gap and it is closed by importing this rather than copying it**
 * (`CR-058` task 8).
 *
 * Returns `null` when there is no name: an empty block would be a customer
 * named after nobody, and the server returns None for it anyway.
 */
export function customerBlockFor(customer: CustomerForm): Record<string, unknown> | null {
  if (customer.full_name.trim() === "") {
    return null;
  }
  const identity: Record<string, unknown> = {};
  if (customer.customer_kind === CUSTOMER_KIND_COMPANY) {
    // ⚠ **PER KIND, NEVER THE UNION (`BR-CUS-1022`).** The server refuses a
    // field belonging to the other kind BY NAME, so sending an SSN under a
    // company would refuse the whole create rather than being ignored.
    if (customer.tax_id.trim() !== "") identity.tax_id = customer.tax_id.trim();
  } else if (customer.customer_kind === CUSTOMER_KIND_PERSON) {
    if (customer.ssn.trim() !== "") identity.ssn = customer.ssn.trim();
    if (customer.driving_licence.trim() !== "")
      identity.driving_licence = customer.driving_licence.trim();
    if (customer.dob !== "") identity.date_of_birth = customer.dob;
  }
  // The phone is on BOTH capture lists and is the ONE identifier a person
  // already types on this screen, so it rides whichever kind is stated.
  if (customer.customer_kind !== "" && customer.phone.trim() !== "") {
    identity.phone = customer.phone.trim();
  }
  const block: Record<string, unknown> = { display_name: customer.full_name.trim() };
  if (customer.customer_kind !== "") block.kind = customer.customer_kind;
  if (Object.keys(identity).length > 0) block.identity = identity;
  return block;
}

/**
 * The `POST /accounts` body — EXACTLY `services.CREATE_FIELDS` and nothing else.
 * Every field the wizard collects is here, and every field the endpoint refuses
 * is absent by construction rather than filtered out downstream: a payload that
 * carried `plan` or `deposit_on_file` would be refused whole, and a wizard that
 * quietly stripped them would be the same lie one layer down.
 *
 * `contact` and `addresses` are omitted entirely when empty — an empty contact
 * object would create a nameless contact row, which is a worse answer than no
 * contact at all (the server requires `full_name` once a contact is sent).
 */
export function createAccountPayload(args: {
  customer: CustomerForm;
  unit: UnitForm;
  preferences: PreferencesForm;
  mode: CreateMode;
  /** `CR-094-BRC01` wave H — step 5. `undefined` when the account owes none;
   *  see `depositPayload`, which never sends a block saying "not required". */
  deposit?: DepositForm;
}): Record<string, unknown> {
  const { customer, unit, preferences } = args;
  const payload: Record<string, unknown> = {
    unit_id: unit.unit_id,
    account_type: customer.account_type,
    // BR-CUS-018: the draft status is the server's default; the activating
    // status is named so the create and the occupancy happen in ONE
    // transaction (BR-CUS-017 is enforced under its lock either way).
    status: args.mode === "activate" ? ACTIVE_STATUS_CODE : DRAFT_STATUS_CODE,
    // BR-CUS-022: the first bill starts here, so it is not defaulted client-side.
    autopay: preferences.autopay, // BR-CUS-059 — captured, never drafted on
    tax_exempt: preferences.tax_exempt,
    // `BR-CUS-028` + `BR-BIL-036` — the two elections that ADD a channel on top
    // of the printed bill. Writable since `customers 0034`; see the fields'
    // own note on `PreferencesForm`. Sent unconditionally because `false` is a
    // real answer here: "not paperless" is a preference, not an absent value.
    // ⚠ **AND-ED WITH THE ADDRESS THE CHANNEL NEEDS, BECAUSE STEP 1 CAN BE GONE
    // BACK TO.** Tick paperless on step 3, return to step 1 and clear the email,
    // and the tick survives in state while the control that set it is disabled —
    // an election to email a bill to nobody. The rule is the same one the
    // control's own help states, so it is enforced where the payload is built
    // rather than trusted to a screen the clerk has since left.
    paperless: preferences.paperless && customer.email.trim() !== "",
    sms_reminders: preferences.sms_reminders && customer.phone.trim() !== "",
  };
  // ⛔ **OMITTED WHEN UNANSWERED, NEVER SENT AS `""`.** `CREATE_FIELDS` carries
  // `account_subtype`, and `_resolve_account_subtype` reads `""` as None — so
  // both spellings happen to write the same row today. The key is left out
  // because the wire should say what the clerk said: *no answer* is an absent
  // key, and a present key carrying an empty string is an answer of "none",
  // which is a distinction the audit row keeps and this screen has no business
  // collapsing.
  if (customer.account_subtype !== "") {
    payload.account_subtype = customer.account_subtype;
  }
  if (unit.opened_at !== "") {
    payload.opened_at = unit.opened_at;
  }
  if (preferences.preferred_language.trim() !== "") {
    payload.preferred_language = preferences.preferred_language.trim();
  }
  if (preferences.tax_exempt_ref.trim() !== "") {
    payload.tax_exempt_ref = preferences.tax_exempt_ref.trim();
  }
  if (preferences.tax_exempt_expires !== "") {
    payload.tax_exempt_expires = preferences.tax_exempt_expires;
  }
  const depositBlock = args.deposit === undefined ? undefined : depositPayload(args.deposit);
  if (depositBlock !== undefined) {
    payload.deposit = depositBlock;
  }
  // ⚠ **SENT ALWAYS, EMPTY INCLUDED (`DEF-CUS-9191`).** This read *"sent only
  // when the tenant has recorded something … a tenant with no definitions must
  // not have their create refused by a section that renders nothing"*. Since
  // `DEF-TEN-9157` (2.456.0) a required field binds only where it is placed
  // Input, so an empty blob refuses nothing a tenant did not draw here — and
  // omitting it let a REQUIRED field drawn on this step, left blank, through,
  // because the server checks only a blob it is sent.
  payload.custom_data = preferences.custom_data;
  // `DEF-CUS-9170` — the service-agreement answers from the unit step, only
  // when the account OPENS its services. A draft opens none, so it sends none
  // (the review step says so); the server refuses a draft that tries.
  const serviceCustom = unit.service_custom_data ?? {};
  if (args.mode === "activate" && Object.keys(serviceCustom).length > 0) {
    payload.service_custom_data = serviceCustom;
  }
  if (customer.full_name.trim() !== "") {
    payload.contact = {
      full_name: customer.full_name.trim(),
      email: customer.email.trim() === "" ? null : customer.email.trim(),
      phone: customer.phone.trim() === "" ? null : customer.phone.trim(),
      dob: customer.dob === "" ? null : customer.dob,
      // BR-CUS-045: the server keeps the LAST FOUR of whatever arrives; the
      // field asks for four digits so a full id is never typed in the first
      // place.
      gov_id_last4:
        customer.gov_id_last4.trim() === "" ? null : customer.gov_id_last4.trim().slice(-4),
      is_primary: true,
    };
  }
  // ── `BR-CUS-1023` / `BR-CUS-1024` — THE `customer` BLOCK ────────────────
  // Built by `customerBlockFor` and NOT inline, because `MoveInWizard` sends
  // the identical block and a second copy is exactly what `CR-058` says must
  // not exist: *"no door may repeat this logic; a second copy is how two doors
  // start disagreeing about who a customer is."*
  const block = customerBlockFor(customer);
  if (block !== null) {
    // `CR-161-BRC10` W4 — SENT ALWAYS from this screen, empty included, for
    // `DEF-CUS-9191`'s reason: the server checks a required customer field
    // drawn here only in a blob it is sent. Added HERE and not in
    // `customerBlockFor`, which the move-in shares and which draws none.
    payload.customer = { ...block, custom_data: customer.customer_custom_data ?? {} };
  }
  const mailing = mailingAddressFor(customer);
  if (mailing !== null) {
    // No mailing row means "same as service" (B2 §2) — which is why an empty
    // block sends nothing rather than an address of empty strings.
    payload.addresses = [mailing];
  }
  return payload;
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface NewAccountWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function NewAccountWizard(props: NewAccountWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const { dateFormat, timeZone } = useRegional(props);
  /** Continue has been pressed on the Customer step — only then is its
   *  refusal drawn (`DEF-CUS-6360`). */
  const [customerTried, setCustomerTried] = useState(false);

  const step = stepFromParam(searchParams.get(STEP_PARAM));
  // The forward fence is the step itself: a user can always go BACK to a step
  // they have been on, and forward only through Continue (BR-SHL-018).
  const nav: WizardNavState = { step, reached: step };
  function setStep(next: WizardNavState): void {
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  const [customer, setCustomer] = useState<CustomerForm>(emptyCustomerForm);
  const [unit, setUnit] = useState<UnitForm>({ unit_id: "", opened_at: "" });
  const [preferences, setPreferences] = useState<PreferencesForm>(emptyPreferencesForm);

  // `DEF-CUS-9235` — the utility's OWN required fields are asked for on the
  // step that draws them, before Continue. Without this a blank required
  // account field let the clerk through to Review, the server refused the
  // create (`customFields.required`, which stays the rule underneath), and the
  // review said *"Check the highlighted fields"* about a box two steps back.
  // The same cached reads the four `CustomFieldsInput` slots below make.
  const customerFields = useCustomFieldRegistry({ entity: "customers", screen: "S18", mode: "input", client });
  const mailingFields = useCustomFieldRegistry({ entity: "addresses", screen: "S18", mode: "input", client });
  const serviceFields = useCustomFieldRegistry({ entity: "service_agreements", screen: "S18", mode: "input", client });
  const accountFields = useCustomFieldRegistry({ entity: "accounts", screen: "S18", mode: "input", client });
  /** `true`, or the sentence naming what is still blank. */
  function ownFieldsAnswered(missing: string[]): true | string {
    return missing.length === 0 ? true : t("customFields.requiredList", { fields: missing.join(", ") });
  }
  const [deposit, setDeposit] = useState<DepositForm>(emptyDepositForm);
  const [mode, setMode] = useState<CreateMode>("activate");
  const [created, setCreated] = useState<AccountWriteResult | null>(null);

  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");

  // BR-CUS-020: the picker asks the server for VACANT units only. An occupied
  // unit is not hidden by this screen — it is never returned to it, and a
  // forged submit is refused again under the BR-CUS-017 lock.
  const unitsQuery = useQuery({
    queryKey: ["units", "vacant-picker"],
    queryFn: () => getUnits({ filters: { occupancy: "vacant" }, per: 500 }, client),
    staleTime: 60 * 1000,
    retry: false,
  });
  const unitRows = unitsQuery.data?.results ?? [];
  const pickedUnit = unitRows.find((row) => row.id === unit.unit_id) ?? null;

  const create = useMutation({
    mutationFn: () =>
      createAccount(
        createAccountPayload({ customer, unit, preferences, mode, deposit }),
        client,
      ),
  });

  async function commit(): Promise<WizardCommitOutcome> {
    try {
      const result = await create.mutateAsync();
      setCreated(result);
      // ⚠ **THE SERVER'S OWN ANSWER RIDES THE TOAST, AND IT HAS TO
      // (`BR-CUS-1023` + hard-won law 2).** The review step draws it too, but
      // the flow NAVIGATES on commit, so that branch is never on screen long
      // enough to read — a statement nobody can see is dead UI, which is the
      // exact defect (`DEF-2818`) this wave was written on. The toast is where
      // the clerk is looking at the moment it matters.
      //
      // Two sentences, not one: the account DID open, and that is said first.
      // Fusing them into a single failure-shaped line would say the opposite of
      // the ruling.
      const opened = t("customers.account.toast.created", {
        account: result.account_no ?? "",
      });
      fireToast(
        result.customer_not_created
          ? `${opened} ${t(result.customer_not_created.message_key)}`
          : opened,
      );
      return { ok: true };
    } catch (error) {
      // BR-SHL-020: plain language, from the server's own message_key — this is
      // where BR-MET-040's "plan required at activation" and BR-CUS-017's "that
      // unit already has an account" reach the user, with everything they typed
      // still on screen (the frame keeps it).
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (unitsQuery.isError && isPermissionDenied(unitsQuery.error)) {
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  // The step the head is naming. Clamped by index rather than trusted: `nav.step`
  // is 1-based URL state and a stale `?step=6` from a bookmark taken before the
  // plan step went would index past the end and render an empty title.
  const currentStepDef = NEW_ACCOUNT_STEPS[Math.min(nav.step, NEW_ACCOUNT_STEP_COUNT) - 1];

  const steps: WizardStep[] = [
    {
      id: "customer",
      label: t(NEW_ACCOUNT_STEPS[0].railKey),
      content: (
        <CustomerStep
          values={customer}
          onChange={setCustomer}
          t={translate}
          showErrors={customerTried}
          dateFormat={dateFormat}
          timeZone={timeZone}
          client={props.client}
        />
      ),
      // The server requires a name once a contact is sent, and an account with
      // no contact has no name anywhere in the product (S17's cell reads "No
      // contact on file"), so the step asks for one.
      //
      // AND SINCE 2026-09-01 IT ASKS FOR AN IDENTIFIER TOO (`BR-CUS-1024`):
      // *"Without identifier we cannot create Customer ID or master account ot
      // regular account"*. The server refuses this payload, so a wizard that let
      // the clerk reach step 6 would collect five steps of typing and throw them
      // at a refusal. The step holds instead, with the reason under the field
      // that fixes it.
      validate: () => {
        setCustomerTried(true);
        if (customer.full_name.trim() === "" || customerStepProblem(customer) !== null) return false;
        return ownFieldsAnswered([
          ...missingRequiredLabels(customerFields.data ?? [], customer.customer_custom_data ?? {}),
          // the mailing block's own fields are on screen only when it is open
          ...(customer.mailing_same ? [] : missingRequiredLabels(mailingFields.data ?? [], customer.mailing_custom_data ?? {})),
        ]);
      },
    },
    {
      id: "unit",
      label: t(NEW_ACCOUNT_STEPS[1].railKey),
      content: (
        <UnitStep
          values={unit}
          options={vacantUnitOptions(unitRows)}
          picked={pickedUnit}
          loading={unitsQuery.isPending}
          dateFormat={dateFormat}
          onChange={setUnit}
          client={props.client}
          t={translate}
        />
      ),
      // BR-CUS-022: an occupying account without a start date can never be
      // billed, and the server refuses one — so Continue asks for both.
      validate: () =>
        unit.unit_id !== "" &&
        unit.opened_at !== "" &&
        ownFieldsAnswered(missingRequiredLabels(serviceFields.data ?? [], unit.service_custom_data ?? {})),
    },
    {
      id: "preferences",
      label: t(NEW_ACCOUNT_STEPS[2].railKey),
      content: (
        <PreferencesStep
          values={preferences}
          dateFormat={dateFormat}
          // Read off step 1's own state, so the two channel controls answer the
          // question the blueprint puts under them — *"Goes to the email
          // captured on step 1"* — rather than offering a channel with no
          // address behind it.
          hasEmail={customer.email.trim() !== ""}
          hasPhone={customer.phone.trim() !== ""}
          onChange={setPreferences}
          t={translate}
        />
      ),
      validate: () => ownFieldsAnswered(missingRequiredLabels(accountFields.data ?? [], preferences.custom_data ?? {})),
    },
    {
      id: "deposit",
      label: t(NEW_ACCOUNT_STEPS[3].railKey),
      // ⚠ **THE SHARED STEP — PO 2026-09-12: *"(a) It is one concept — money
      // held against an account — and building it four times would give four
      // behaviours."*** This step collected NOTHING until this wave and said
      // so; the engine behind it has existed since 2026-08-27. Mounted from
      // `depositCapability.tsx` rather than rebuilt here, which is the whole
      // of the ruling.
      //
      // ⛔ `carryForward` is ABSENT: a counter sign-up has no previous tenancy
      // to carry a deposit from, and the blueprint draws that question on the
      // MOVE-IN only (page 71: *"the one question a move-in adds"*).
      content: (
        <DepositStep
          values={deposit}
          onChange={setDeposit}
          t={translate}
          dateFormat={dateFormat}
          // `null`: there is no account yet to read `BR-TEN-042`'s currency
          // off, so the step reads the TENANT's own through
          // `useTenantCurrency()` (`DEF-CUS-5114`, fixed 2026-10-04). Only
          // when the shell published none does the footer state the absence —
          // never `USD` on its own (`UnitPricingPanel.money`'s precedent).
          currency={null}
          unitId={unit.unit_id}
          category={customer.account_type}
          client={client}
        />
      ),
      validate: () => depositProblem(deposit) === null,
    },
    {
      id: "review",
      label: t(NEW_ACCOUNT_STEPS[4].railKey),
      content: (
        <ReviewStep
          customer={customer}
          unit={unit}
          preferences={preferences}
          deposit={deposit}
          picked={pickedUnit}
          mode={mode}
          created={created}
          dateFormat={dateFormat}
          onEdit={(target) => setStep({ step: target, reached: nav.reached })}
          onMode={setMode}
          t={translate}
        />
      ),
    },
  ];

  return (
    <div className="cus-page">
      {/* US-SHL-020 / BR-SHL-044: the shared header. The kicker ("NEW ACCOUNT")
          is the same on all five screens and the TITLE IS NOT — the blueprint
          draws a different H1 on each: *Create a first-time customer account.* ·
          *Which unit?* · *Account preferences* · *Deposit* · *Review*. One title
          repeated five times was `DEF-CUS-5187`'s other half.

          ⚠ **THE `rollup` IS GONE AND IS NOT COMING BACK.** It read *"Six steps.
          Someone moving into a unit whose last tenant has already moved out has
          a guided page of its own — use Move-in on that closed account."* —
          thirty words in ONE sentence over B14 rule 33's six-per-sentence cap,
          and it stated the step count in English PROSE, so it could not follow
          its own rail and said *six* over a five-cell rail the moment the plan
          step went. The drawing puts the step line here and nothing else. */}
      <PageHeader
        backTo={{ to: tenantPath(ACCOUNTS_ROUTE), label: t("customers.accounts.title") }}
        kicker={t("customers.newAccount.kicker")}
        title={t(currentStepDef.titleKey)}
      />

      {/* ⚠ **THE STEP LINE — DRAWN UNDER THE TITLE OF ALL FIVE SCREENS AND
          ABSENT FROM EVERY ONE OF THEM UNTIL NOW (`DEF-CUS-5187`).** Both halves
          come from `NEW_ACCOUNT_STEPS`, never from a typed number: the move-in
          wizard told every clerk it had five steps while its rail drew six,
          because a step was added and the sentence quoting the count was not.
          The same shared key the move-in and move-out wizards render, so the
          four customers wizards cannot say it four ways. */}
      <Note>
        {t("customers.wizard.stepOfNamed", {
          step: nav.step,
          of: NEW_ACCOUNT_STEP_COUNT,
          name: t(currentStepDef.lineKey),
          defaultValue: "Step {{step}} of {{of}} · {{name}}",
        })}
      </Note>

      {/* BR-SHL-025: a role without write access still SEES the flow and is
          told why it cannot commit — the frame's ✓ is the server's boundary
          either way (POST /accounts is AdminOrClerk). */}
      {writeBlockedReason !== null && (
        <RefusalStrip role="alert">
          {writeBlockedReason}
        </RefusalStrip>
      )}

      {/* B13 §1 / BR-SHL-018/019: the SHARED wizard frame owns the numbered
          rail, Back/Continue, the ✓ confirm, its working state and the ONE
          transactional commit. This screen declares steps and a payload. */}
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setStep}
        commitLabel={
          mode === "activate"
            ? t("customers.newAccount.commit.activate")
            : t("customers.newAccount.commit.draft")
        }
        commitFailedTitle={t("customers.newAccount.commitFailed")}
        onCommit={
          writeBlockedReason === null
            ? commit
            : // Nothing is posted from a role the server would refuse; the
              // refusal renders in the frame's own A18 §4 card.
              () => Promise.resolve({ ok: false, reason: writeBlockedReason })
        }
        onCommitted={() =>
          navigate(
            tenantPath(created === null ? ACCOUNTS_ROUTE : accountDetailPath(created.id)),
          )
        }
      />

      <p className="settings-audit-line">{t("customers.newAccount.auditLine")}</p>
    </div>
  );
}

export default NewAccountWizard;

// ── Steps ──────────────────────────────────────────────────────────────────

function CustomerStep(props: {
  values: CustomerForm;
  onChange: (next: CustomerForm) => void;
  t: Translator;
  showErrors: boolean;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  client?: ApiClient;
}) {
  const { t } = props;
  return (
    <Panel>
      <h3>{t("customers.newAccount.customer.title")}</h3>
      {/* ⚠ **THE FIELDS ARE `CustomerFields`, SHARED WITH THE MOVE-IN'S STEP 2
          (B14 rule 43).** This step carried its own 200-line copy until
          2026-09-23; the PO's reports on the move-in (`DEF-CUS-6356`..`6360`)
          are fixed ONCE there and reach this screen with them. The hint under
          the heading and the "no duplicate check" note were rationale (rule
          33) and are deleted. */}
      <CustomerFields
        values={props.values}
        onChange={props.onChange}
        t={t}
        showErrors={props.showErrors}
        dateFormat={props.dateFormat}
        timeZone={props.timeZone}
        mailingExtra={
          // `DEF-CUS-9169` — the utility's own mailing-address fields placed
          // Input on New account. Renders nothing when they placed none.
          <CustomFieldsInput
            entity="addresses"
            screen="S18"
            values={props.values.mailing_custom_data}
            onChange={(mailing_custom_data) =>
              props.onChange({ ...props.values, mailing_custom_data })
            }
            client={props.client}
          />
        }
      />
      {/* `CR-161-BRC10` W4 — the utility's OWN customer fields placed Input on
          New account. They describe the PERSON or COMPANY, so they ride the
          `customer` block. Renders nothing when none is placed here. */}
      <CustomFieldsInput
        entity="customers"
        screen="S18"
        values={props.values.customer_custom_data ?? {}}
        onChange={(customer_custom_data) => props.onChange({ ...props.values, customer_custom_data })}
        client={props.client}
      />
    </Panel>
  );
}

function UnitStep(props: {
  values: UnitForm;
  options: { value: string; label: string }[];
  picked: UnitRow | null;
  loading: boolean;
  dateFormat: RegionalDateFormat;
  onChange: (next: UnitForm) => void;
  client?: ApiClient;
  t: Translator;
}) {
  const { t, values } = props;
  return (
    <Panel>
      {/* ⚠ NO PANEL `<h3>` HERE. The page title is *Which unit?* and a heading
          under it saying *Pick the unit they'll be billed for* is the same
          sentence twice — which is what adding a per-step title costs if the
          old heading is not removed with it. The drawing goes title → step line
          → rail → the picker, and the hint is the line it draws beside it. */}
      <p className="met-panel-hint">{t("customers.newAccount.unit.hint")}</p>

      {props.loading ? (
        <p className="met-panel-hint">{t("customers.newAccount.unit.loading")}</p>
      ) : props.options.length === 0 ? (
        // A18 §1 in miniature: nothing to pick is a statement, not a blank
        // control that looks broken.
        <RefusalStrip role="alert">
          {t("customers.newAccount.unit.noneVacant")}
        </RefusalStrip>
      ) : (
        // BR-SHL-033: the unit list is long → the searchable control.
        <SearchSelectField
          id="unit_id"
          label={t("customers.newAccount.field.unit")}
          required
          value={values.unit_id}
          options={props.options}
          placeholder={t("customers.newAccount.field.unitPlaceholder")}
          onChange={(value) => props.onChange({ ...values, unit_id: value })}
          help={t("customers.newAccount.unit.pickerHelp")}
        />
      )}

      {props.picked !== null && (
        <FactList>
          <Fact label={t("customers.accounts.col.services")}>
            <ServiceTags services={props.picked.services} t={t} />
          </Fact>
          <Fact label={t("customers.newAccount.field.metersAtUnit")}>
            {props.picked.meters.length === 0 ? (
              <Dash>{t("customers.account.metersEmpty")}</Dash>
            ) : (
              props.picked.meters
                .map((meter) => meter.asset_no)
                .filter((assetNo) => assetNo !== null)
                .join(" · ")
            )}
          </Fact>
        </FactList>
      )}

      {/* BR-CUS-022: `opened_at` is the account's start AND every service
          agreement's `started_on`. The server refuses an occupying account
          without one, so it is required here rather than defaulted. */}
      <DatePickerField
        id="opened_at"
        label={t("customers.newAccount.field.startDate")}
        required
        value={values.opened_at}
        dateFormat={props.dateFormat}
        onChange={(value) => props.onChange({ ...values, opened_at: value })}
        help={t("customers.newAccount.unit.startDateHelp")}
      />

      {/* `DEF-CUS-9170` — the utility's OWN service-agreement fields placed
          Input on New account (slot `S18`), on the step that lists the unit's
          services. Typed once; every agreement the account opens carries them.
          Renders NOTHING when the utility placed none. */}
      <CustomFieldsInput
        entity="service_agreements"
        screen="S18"
        values={values.service_custom_data ?? {}}
        onChange={(service_custom_data) => props.onChange({ ...values, service_custom_data })}
        client={props.client}
      />

      {/* BR-CUS-021: `initial_reads` is a REFUSED field — reads belong to
          metering's own append-only commit path (B1). */}
      <Note>{t("customers.newAccount.unit.noInitialReads")}</Note>

      {/* ⚠ **THE PANEL THE DELETED PLAN STEP BECAME (`DEF-CUS-5188`).** PO:
          *"whenever the unit is selected, show all the details."* It is drawn
          below the picker on page 61 as one bordered block headed with the
          unit's own name, and it closes by saying it is not an input — because
          every row in it is a fact about the unit, not a choice about the
          account. */}
      {props.picked !== null && (
        <UnitRecordPanel picked={props.picked} client={props.client} t={t} />
      )}
    </Panel>
  );
}

/**
 * *"Unit A, 1408 Elm Street — everything this unit carries"* (blueprint p61).
 *
 * ⚠ **THE PLAN ROW IS THE REASON THIS EXISTS, AND `UnitRow` CANNOT ANSWER IT.**
 * The unit payload serves `rate_plan_id` — a UUID, which B14 rule 31 forbids on
 * screen — and no name, code, version or base charge. `GET /units/{id}/pricing`
 * has served all four since 2026-08-25 and this wizard never called it, so the
 * panel reads the plan through `getUnitPricing`: the same door `UnitPricingPanel`
 * and the move-in wizard already use, rather than a second definition of it
 * (hard-won law 1).
 *
 * ⚠ **THE WHOLE `UnitPricingPanel` IS DELIBERATELY *NOT* MOUNTED HERE.** It
 * draws rate blocks, tiers, discounts, minimums and taxes; the blueprint draws
 * four plan rows. Mounting it would be adding controls the drawing does not
 * show, which is the thing this pass exists to stop.
 *
 * ⚠ **NO ADDRESS IS STORED ON A UNIT (hard rule 8 / `BR-MET-1161`).** Every
 * address row here is the PREMISES', reached by walking — `premise_address`,
 * `premise_no` — and `Map point` names which of the two points it is showing,
 * which `BR-MET-1162` makes part of the rule rather than a nicety.
 */
export function UnitRecordPanel(props: { picked: UnitRow; client?: ApiClient; t: Translator }) {
  const { t, picked } = props;
  const tenantCurrency = useTenantCurrency();
  const pricing = useQuery({
    queryKey: ["new-account-unit-pricing", picked.id],
    queryFn: () => getUnitPricing(picked.id, props.client ?? api),
    // A plan that cannot be read must not block the step: the clerk can still
    // pick the unit and the panel says the plan is not readable.
    retry: false,
  });
  const plan = pricing.data?.plan ?? null;
  const planLine =
    plan === null
      ? null
      : [plan.code, plan.name, plan.version === null ? null : `v${plan.version}`]
          .filter((part) => part !== null && part !== "")
          .join(" · ");
  const yes = t("customers.account.yes", { defaultValue: "Yes" });
  const no = t("customers.account.no", { defaultValue: "No" });
  // BR-MET-1162: a unit may hold its own point and where it does that is the
  // truth for that unit; otherwise it reads the building's. The screen says
  // WHICH, because the ruling requires it and "a point" alone is two facts.
  const pointSource =
    picked.point.source === "unit"
      ? t("customers.newAccount.unit.pointOwn", { defaultValue: "Its own" })
      : picked.point.source === "premises"
        ? t("customers.newAccount.unit.pointPremises", {
            defaultValue: "Reads the building's",
          })
        : null;

  return (
    <>
      <h4 className="cus-subhead">
        {t("customers.newAccount.unit.recordTitle", {
          unit: picked.label ?? picked.unit_no ?? "",
          premises: picked.premise_address ?? "",
          defaultValue: "{{unit}}, {{premises}} — everything this unit carries",
        })}
      </h4>
      {/* ⚠ **TWO COLUMNS, AND THE SPLIT IS THE DRAWING'S OWN.** Page 61 puts
          what the unit IS on the left — number, label, type, floor, area, its
          building, its point — and what it will COST on the right: parcel,
          plan, when the plan took effect, whether it is locked, the base charge,
          and whether the owner is billed when it is empty. Fourteen rows in one
          column is a panel a clerk scrolls past.

          `cus-two-col` / `cus-col` are `customers.css`'s own and stack to one
          column under 900px. They are used rather than a grid utility because
          this file is NOT on `route-b-migrated.txt`, so `G31` owns it and asks
          that every class be declared by a stylesheet (B14 rule 21). Migrating
          the file to make a nicer ratio available is its own work with its own
          proof, and is not done as a side effect of this one. */}
      <div className="cus-two-col">
      <div className="cus-col">
      <FactList>
        <Fact label={t("customers.newAccount.field.unitNumber")}>
          {picked.unit_no ?? <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>}
        </Fact>
        <Fact label={t("customers.newAccount.field.unitLabel")}>
          {picked.label ?? <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>}
        </Fact>
        <Fact label={t("customers.newAccount.field.unitType")}>
          {/* ⚠ **THIS RENDERED `residential_submetered` ON THE FIRST PASS** — a
              raw enum code in clerk-facing copy, which B14 rule 32 forbids by
              name. `metering.units.type.*` is the product's own display map and
              `AddPremisesWizard` already reads it the same way.

              ⚠ **THE FALLBACK IS THE CODE AND NEVER AN INVENTED LABEL.** That
              is `DEF-684`'s ruling, made on the account category in this same
              file: a made-up word is how `government` quietly starts reading as
              "Municipal". An unmapped code is a missing catalogue row and must
              look like one. */}
          {picked.unit_type === null ? (
            <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>
          ) : (
            t(`metering.units.type.${picked.unit_type}`, { defaultValue: picked.unit_type })
          )}
        </Fact>
        <Fact label={t("metering.units.field.floor")}>
          {picked.floor_label ?? <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>}
        </Fact>
        <Fact label={t("metering.units.field.floorArea")}>
          {picked.square_feet === null ? (
            <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>
          ) : (
            t("customers.newAccount.unit.squareFeet", {
              value: picked.square_feet,
              defaultValue: "{{value}} sq ft",
            })
          )}
        </Fact>
        <Fact label={t("customers.account.field.premises")}>
          {[picked.premise_address, picked.premise_no].filter(Boolean).join(" · ") || (
            <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>
          )}
        </Fact>
        <Fact label={t("metering.unit.point.label")}>
          {pointSource ?? <Dash>{t("metering.unit.point.none")}</Dash>}
        </Fact>
      </FactList>
      </div>
      <div className="cus-col">
      <FactList>
        {/* ⛔ The drawing's `Parcel` row. The unit payload carries no parcel or
            GIS reference, so the absence is STATED rather than the column
            invented — `DEF-CUS-5191`. */}
        <Fact label={t("customers.newAccount.field.parcel")}>
          <NotRecorded
            label={t("customers.newAccount.unit.parcelUnavailable")}
            why={t("customers.newAccount.unit.parcelWhy")}
            ruleRef="BR-MET-1162"
          />
        </Fact>
        <Fact label={t("customers.account.field.plan")}>
          {pricing.isPending ? (
            <Dash>{t("customers.newAccount.unit.planLoading")}</Dash>
          ) : planLine !== null && planLine !== "" ? (
            planLine
          ) : (
            // BR-MET-040: an activation on a unit with no plan is REFUSED. The
            // check the deleted step ran, said where the unit is chosen.
            <RefusalStrip as="span">{t("customers.newAccount.plan.unitHasNoPlan")}</RefusalStrip>
          )}
        </Fact>
        <Fact label={t("customers.newAccount.field.planSince")}>
          {picked.plan_effective_from ?? <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>}
        </Fact>
        <Fact label={t("customers.newAccount.field.planLocked")}>
          {picked.plan_locked ? yes : no}
        </Fact>
        <Fact label={t("customers.account.awaits.baseCharge")}>
          {/* ⚠ **HARD RULE 2: MONEY IS STORED TO FOUR DECIMALS AND DISPLAYS TO
              TWO.** `plan.base_charges` arrives as a raw decimal string and this
              row rendered `20.000000` on the first pass — six decimals of a
              figure a clerk reads as a monthly charge.

              `DEF-CUS-5114` (2026-10-04): there is no account yet, so the
              row reads the TENANT's currency (`BR-TEN-042`) and renders
              through `MoneyCell` — `$20.00`. Only where the shell published
              none does it fall back to `formatMoneyInput`, which shares
              `formatMoney`'s every decision (2 dp, the B4.4 ❄️ half-up) and
              invents NO symbol. */}
          {plan?.base_charges === null || plan?.base_charges === undefined ? (
            <Dash>{t("metering.premises.jurisdiction.notRecorded")}</Dash>
          ) : tenantCurrency !== null ? (
            <MoneyCell amount={plan.base_charges} currency={tenantCurrency} />
          ) : (
            formatMoneyInput(plan.base_charges)
          )}
        </Fact>
        <Fact label={t("customers.newAccount.field.billOwnerVacant")}>
          {picked.vacant_standby_auto ? yes : no}
        </Fact>
        {/* The step already shows a `Services` row above the picker, so the
            panel's own row takes the drawing's fuller label — two rows with one
            word between them is a clerk reading the same fact twice and
            wondering which is which. */}
        <Fact label={t("customers.newAccount.field.servicesAvailable")}>
          <ServiceTags services={picked.services} t={t} />
        </Fact>
      </FactList>
      </div>
      </div>
      <Note>{t("customers.newAccount.unit.notAnInput")}</Note>
    </>
  );
}

function PreferencesStep(props: {
  values: PreferencesForm;
  dateFormat: RegionalDateFormat;
  /** Step 1 captured an email — without one `paperless` has nowhere to send. */
  hasEmail: boolean;
  /** Step 1 captured a phone — without one `sms_reminders` has nowhere to send. */
  hasPhone: boolean;
  onChange: (next: PreferencesForm) => void;
  t: Translator;
}) {
  const { t, values } = props;
  return (
    <Panel>
      {/* ⚠ NO PANEL `<h3>` AND NO LEAD SENTENCE. The page title is *Account
          preferences*; the hint said *"Only what the account can actually hold
          is offered here"*, which stopped being true the moment paperless and
          text reminders were wired (`DEF-CUS-5184`). The drawing opens straight
          on the first section. */}

      {/* ── How the bill is delivered ──────────────────────────────────────
          ⚠ **THESE TWO CONTROLS WERE REFUSED IN WRITING OVER A WORKING DOOR
          (`DEF-CUS-5184`).** The block at the foot of this step named
          `paperless` and `sms_reminders` among four columns that "were never
          built". Both were built on 2026-08-31 (`CR-052` task 14, migration
          `customers/0034`), both are in `CREATE_FIELDS`, and `createAccountPayload`
          above has been sending both ever since — to a form nothing could set.
          Dead UI with a false sentence over it: hard-won law 2 in both of its
          directions at once, for thirteen days.

          `BR-BIL-036` — PRINT IS THE FLOOR. Neither election switches the
          printed bill off; they ADD a channel. The blueprint draws that as the
          first thing on the step and it is a FACT, so it is stated once. */}
      <h4 className="cus-subhead">{t("customers.newAccount.preferences.deliveryTitle")}</h4>
      <RefusalStrip role="note">{t("customers.moveIn.preferences.printIsTheFloor")}</RefusalStrip>
      <CheckboxField
        id="paperless"
        label={t("customers.deposit.review.paperless")}
        checked={values.paperless && props.hasEmail}
        // ⚠ **THE BLUEPRINT DRAWS THIS DISABLED WITH NO EMAIL — *"With no email
        // on file this is shown and cannot be ticked"* — AND THE KIT'S
        // `CheckboxField` TAKES NO `disabled` PROP AT ALL (`DEF-CUS-5197`).**
        // `BR-SHL-025` cannot be honoured on ANY checkbox in this product until
        // the kit gains one, and `components/FormModal.tsx` is not this lane's
        // file to change. So the election is refused where it is BUILT
        // (`createAccountPayload` ands it with the address) and the reason is
        // said under the control; the tick is not silently kept either, which
        // is why `checked` is anded here too.
        onChange={(checked) => props.onChange({ ...values, paperless: checked })}
      />
      <p className="met-panel-hint">
        {props.hasEmail
          ? t("customers.newAccount.preferences.paperlessHint")
          : t("customers.newAccount.preferences.paperlessNoEmail")}
      </p>
      <CheckboxField
        id="sms_reminders"
        label={t("customers.deposit.review.sms")}
        checked={values.sms_reminders && props.hasPhone}
        onChange={(checked) => props.onChange({ ...values, sms_reminders: checked })}
      />
      <p className="met-panel-hint">
        {props.hasPhone
          ? t("customers.newAccount.preferences.smsHint")
          : t("customers.newAccount.preferences.smsNoPhone")}
      </p>

      {/* ── Paying ────────────────────────────────────────────────────────
          BR-CUS-059: stored and displayed, and NOTHING collects on it in v1. */}
      <h4 className="cus-subhead">{t("customers.newAccount.preferences.payingTitle")}</h4>
      <CheckboxField
        id="autopay"
        label={t("customers.newAccount.field.autopay")}
        checked={values.autopay}
        onChange={(checked) => props.onChange({ ...values, autopay: checked })}
      />
      <p className="met-panel-hint">{t("customers.newAccount.preferences.autopayHint")}</p>

      {/* ── Tax ───────────────────────────────────────────────────────────
          B4.2 / BR-CUS-012: account-level tax exemption is part of the
          confirmed attribute set and the endpoint accepts all three fields. */}
      <h4 className="cus-subhead">{t("customers.newAccount.preferences.taxTitle")}</h4>
      <CheckboxField
        id="tax_exempt"
        label={t("customers.account.field.taxExempt")}
        checked={values.tax_exempt}
        onChange={(checked) => props.onChange({ ...values, tax_exempt: checked })}
      />
      {values.tax_exempt && (
        <>
          <TextField
            id="tax_exempt_ref"
            label={t("customers.newAccount.field.taxExemptRef")}
            value={values.tax_exempt_ref}
            onChange={(value) => props.onChange({ ...values, tax_exempt_ref: value })}
          />
          <DatePickerField
            id="tax_exempt_expires"
            label={t("customers.account.field.taxExemptExpires")}
            value={values.tax_exempt_expires}
            dateFormat={props.dateFormat}
            onChange={(value) => props.onChange({ ...values, tax_exempt_expires: value })}
            help={t("customers.newAccount.preferences.taxExpiresHelp")}
          />
        </>
      )}

      {/* ── Language ─────────────────────────────────────────────────────── */}
      <h4 className="cus-subhead">{t("customers.newAccount.preferences.languageTitle")}</h4>
      {/* `DEF-CUS-6364` / `OQ-CUS-12619` (a) — the same field the move-in
          mounts: the utility's languages, opening on its default. */}
      <PortalLanguageField
        value={values.preferred_language}
        onChange={(value) => props.onChange({ ...values, preferred_language: value })}
        t={t}
      />

      {/* EP-SHL-07 / US-SHL-015 — the tenant's OWN fields. S18 is an `input`
          slot for `accounts` in the US-TEN-016 allow-list, so whatever this
          utility has defined and placed there is captured here with no code
          change and no deploy. Renders NOTHING when they have defined none. */}
      <CustomFieldsInput
        entity="accounts"
        screen="S18"
        values={values.custom_data}
        onChange={(next) => props.onChange({ ...values, custom_data: next })}
      />

      {/* ⚠ **THIS NAMED FOUR COLUMNS AND TWO OF THEM WERE BUILT
          (`DEF-CUS-5184`).** `paperless` and `sms_reminders` landed on
          2026-08-31 and are the two controls at the top of this step now. What
          is left is genuinely unbuilt — `budget_billing` and
          `statement_language` are still PROPOSED-SCHEMA — plus `BR-CUS-060`'s
          bill-delivery day, which is not coming at all. A refusal whose reason
          has expired is hard-won law 1 in its second form, so the sentence is
          rewritten rather than left standing. */}
      <ArrivesWith
        title={t("customers.newAccount.preferences.arrivesTitle")}
        message={t("customers.newAccount.preferences.arrives")}
      />
    </Panel>
  );
}

// ⚠ **THIS FILE'S OWN `DepositStep` IS DELETED, NOT REWORDED (hard-won law 1).**
// It rendered two `NotRecorded` facts and an *"arrives with the deposit work"*
// panel over an engine that had been finished for sixteen days, and its
// refusal named *"the plan's deposit schedule and the deposit path that writes
// it"* — both of which exist (`rating.plan_deposit_rules`,
// `payments.record_payment(purpose="deposit")` and `BR-CUS-670`'s register
// writer). The live step is `depositCapability.DepositStep`, mounted above and
// shared with the move-in under the PO's *"It is one concept"* ruling.
//
// The CREDIT-TIER absence it also carried is not lost: it is rendered by the
// shared step as one six-word fact (`BR-CUS-058` — the tier is COMPUTED from
// payment history and has no input path, so nothing sizes a deposit).

/**
 * One review block heading: the section name, the step it came from, and the
 * way back to it. Drawn on page 64 as `CUSTOMER · STEP 1 … Edit →`.
 *
 * `step: null` is the block that is not a step — *"What will be on the account
 * the moment it is created"* — so it carries no number and no link. Two shapes
 * of heading rather than an `Edit →` that goes nowhere, which is the dead
 * control hard-won law 2 warns about in its second direction.
 *
 * ⚠ **NO TAILWIND UTILITY.** `NewAccountWizard.tsx` is NOT on
 * `07-frontend/src/styles/route-b-migrated.txt`, so `G31` owns it and demands
 * every class be declared by a stylesheet. `cus-subhead` and `cus-rollup*` are
 * `customers.css`'s own. (The ledger gates which CHECKER owns the file; it does
 * not stop the utility rendering — `DEF-GOV-5102` corrected that on 2026-09-12.)
 */
function ReviewBlock(props: {
  title: string;
  step: number | null;
  onEdit: (step: number) => void;
  t: Translator;
}) {
  const { t, step } = props;
  return (
    <h4 className="cus-subhead">
      <span className="cus-rollup">
        <span className="cus-rollup-item">{props.title}</span>
        {step !== null && (
          <span className="cus-rollup-item">
            {t("customers.newAccount.review.fromStep", {
              step,
              defaultValue: "Step {{step}}",
            })}
          </span>
        )}
      </span>
      {step !== null && (
        <Button variant="ghost" size="sm" onClick={() => props.onEdit(step)}>
          {t("customers.newAccount.review.edit", { defaultValue: "Edit →" })}
        </Button>
      )}
    </h4>
  );
}

function ReviewStep(props: {
  customer: CustomerForm;
  unit: UnitForm;
  preferences: PreferencesForm;
  /** `DEF-CUS-9505` — the SAME form the Deposit step edits, so the review and
   *  the step can never disagree (MoveInWizard's precedent). */
  deposit: DepositForm;
  picked: UnitRow | null;
  mode: CreateMode;
  created: AccountWriteResult | null;
  dateFormat: RegionalDateFormat;
  /** Jump BACK to the step that captured a block (`BR-SHL-018`). */
  onEdit: (step: number) => void;
  onMode: (mode: CreateMode) => void;
  t: Translator;
}) {
  const { t } = props;
  const categories = useAccountCategories();
  const subtypes = useAccountSubtypes();
  // `CR-058` task 7 — the server's own word, mapped to the clerk's sentence.
  const outcomeKey = customerOutcomeKey(props.created);
  return (
    <Panel>
      {/* ⚠ NO PANEL `<h3>`. The page title is *Review*; a heading under it
          reading *Review and create.* is the third place this pass had to
          remove a duplicate that appeared the moment each step got its own
          title. Named here so the next reader sees it was deliberate. */}

      {/* ⚠ **THE BLOCKS ARE THE DESIGN, NOT DECORATION (blueprint p64).** The
          review was one flat list of eight facts with nothing saying which step
          each came from and no way back to the one that is wrong. The drawing
          groups every fact under the step that captured it and puts an `Edit →`
          on each heading, which is the whole point: a clerk who spots a wrong
          postal code on the last screen of a five-screen wizard should not have
          to work out that it was step 1.

          `onEdit` jumps BACK only, which is the rail's own law (`BR-SHL-018`) —
          every step behind the review has been validated to get here. */}
      <ReviewBlock
        title={t("customers.newAccount.review.block.customer")}
        step={1}
        onEdit={props.onEdit}
        t={t}
      />
      <FactList>
        <Fact label={t("customers.account.field.fullName")}>
          {props.customer.full_name === "" ? <Dash /> : props.customer.full_name}
        </Fact>
        {/* ⚠ **THE NAME COMES FROM THE CATALOGUE, NOT FROM A KEY (DEF-684).**
            `customers.accounts.category.*` only ever held BR-CUS-094's
            superseded four, so the three codes it added — and
            `builder_developer` most visibly — fell through to their raw slug.
            The fallback is still the CODE, never an invented label: that is how
            `government` would quietly start reading as "Municipal", which the
            ruling forbids by name. */}
        <Fact label={t("customers.accounts.filter.category")}>
          {accountCategoryName(props.customer.account_type, categories.all)}
        </Fact>
        {/* ⚠ **THE NAME, FROM THE TENANT'S ROWS — never the stored code.** The
            Accounts blueprint records `account_subtype` as the ONE raw enum
            still reaching a clerk on the live product (`small_commercial`), and
            B14 rule 31 is what it breaks. The fallback is the code, never an
            invented label. */}
        <Fact label={t("customers.account.field.subtype")}>
          {props.customer.account_subtype === "" ? (
            <Dash />
          ) : (
            accountSubtypeName(props.customer.account_subtype, subtypes.rows)
          )}
        </Fact>
      </FactList>

      <ReviewBlock
        title={t("customers.newAccount.review.block.unit")}
        step={2}
        onEdit={props.onEdit}
        t={t}
      />
      <FactList>
        <Fact label={t("customers.newAccount.field.unit")}>
          {props.picked === null ? (
            <Dash />
          ) : (
            [props.picked.premise_address ?? props.picked.premise_no, props.picked.unit_no ?? props.picked.label]
              .filter((part) => part !== null && part !== undefined && part !== "")
              .join(" · ")
          )}
        </Fact>
        <Fact label={t("customers.newAccount.field.startDate")}>
          {props.unit.opened_at === "" ? <Dash /> : props.unit.opened_at}
        </Fact>
      </FactList>

      <ReviewBlock
        title={t("customers.newAccount.review.block.preferences")}
        step={3}
        onEdit={props.onEdit}
        t={t}
      />
      <FactList>
        {/* `BR-BIL-036` — the two elections, and the floor underneath them. A
            review that showed only what was ticked would let a clerk read "no
            paperless" as "no bill goes out". */}
        <Fact label={t("customers.deposit.review.paperless")}>
          {props.preferences.paperless && props.customer.email.trim() !== ""
            ? t("customers.newAccount.review.paperlessOn", {
                email: props.customer.email.trim(),
                defaultValue: "On · to {{email}}",
              })
            : t("customers.accounts.autopay.off")}
        </Fact>
        <Fact label={t("customers.deposit.review.sms")}>
          {props.preferences.sms_reminders && props.customer.phone.trim() !== ""
            ? t("customers.accounts.autopay.on")
            : t("customers.accounts.autopay.off")}
        </Fact>
        <Fact label={t("customers.newAccount.field.printedBill")}>
          {t("customers.newAccount.review.printedAlways")}
        </Fact>
        <Fact label={t("customers.newAccount.field.autopay")}>
          {props.preferences.autopay
            ? t("customers.accounts.autopay.on")
            : t("customers.accounts.autopay.off")}
        </Fact>
        <Fact label={t("customers.account.field.taxExempt")}>
          {props.preferences.tax_exempt
            ? t("customers.account.yes")
            : t("customers.account.no")}
        </Fact>
      </FactList>

      {/* `DEF-CUS-9505` — the Deposit step's answer (step 4), drawn by the
          shared capability's own review rows. Currency is `null` exactly as
          on the step, so both read the TENANT's (`DEF-CUS-5114`). */}
      <ReviewBlock
        title={t("customers.newAccount.step.deposit")}
        step={4}
        onEdit={props.onEdit}
        t={t}
      />
      <FactList>
        <DepositReviewRows
          form={props.deposit}
          currency={null}
          t={t}
          row={(label, value) => (
            <Fact key={label} label={label}>
              {value}
            </Fact>
          )}
        />
      </FactList>

      <ReviewBlock
        title={t("customers.newAccount.review.block.onCreate")}
        step={null}
        onEdit={props.onEdit}
        t={t}
      />
      <FactList>
        <Fact label={t("customers.newAccount.field.accountNumber")}>
          {/* BR-TEN-035: allocated from the tenant series AT SAVE TIME. The
              prototype prints "A-12048" here before anything is written; a
              number shown before it is allocated is a number that can be
              wrong, so this states the fact instead. */}
          {props.created === null ? (
            <Dash>{t("customers.newAccount.review.numberAtSave")}</Dash>
          ) : (
            props.created.account_no
          )}
        </Fact>
        {/* `BR-CUS-1023` — THE SERVER'S OWN ANSWER, not this screen's guess.
            `customerNumberShortfall` warns while the clerk types; THIS is what
            actually happened, and the two can differ (a returning customer is
            LINKED to an existing number on evidence that would not create one).
            ⚠ **THE VALUE IS THE CUSTOMER NUMBER AND NEVER THE DATABASE ID**
            (B14 rule 31). */}
        <Fact label={t("customers.newAccount.review.customerNumber")}>
          {props.created === null ? (
            <Dash>{t("customers.newAccount.review.numberAtSave")}</Dash>
          ) : (props.created.customer_no ?? null) !== null ? (
            props.created.customer_no
          ) : (
            <Dash>
              {props.created.customer_not_created
                ? t(props.created.customer_not_created.message_key)
                : t("customers.newAccount.review.customerNumberNone")}
            </Dash>
          )}
        </Fact>
      </FactList>

      {/* `CR-058` task 7 — **WHICH OF THE THREE THINGS HAPPENED.**

          The number above answers *what* the customer is and never answers
          *where it came from*, and those are two different facts to a clerk: a
          number that is present because somebody was RECOGNISED needs checking,
          and a number that is present because one was MINTED does not. The
          server states the outcome in a word (`customer_outcome`) and this is
          the sentence for it — on a match it says *"this looks like a customer
          you already have"* rather than linking silently, which is the whole of
          `BR-CUS-019`'s advisory posture rendered.

          One sentence, no rule id, no internal code (B14 rule 32). It appears
          only AFTER the commit, because before it there is nothing true to say.

          ⚠ **NO TAILWIND UTILITY — this file is absent from
          `route-b-migrated.txt`, so a utility here renders as NOTHING while
          every test passes (B14 rule 21 · DEF-974). `Note` brings its own
          class from a migrated component.** */}
      {outcomeKey !== null && <Note>{t(outcomeKey)}</Note>}

      {/* BR-CUS-018: the prototype's "Save draft & exit" and its "Create
          account ✓" become ONE choice, so the flow keeps exactly one
          transactional commit (BR-SHL-019). */}
      <SegmentedField
        id="create_mode"
        label={t("customers.newAccount.review.modeLabel")}
        value={props.mode}
        options={CREATE_MODES.map((value) => ({
          value,
          label: t(`customers.newAccount.mode.${value}`),
        }))}
        onChange={(value) => props.onMode(value as CreateMode)}
      />
      <p className="met-panel-hint">
        {props.mode === "activate"
          ? t("customers.newAccount.mode.activateHint")
          : t("customers.newAccount.mode.draftHint")}
      </p>
      {/* `DEF-CUS-9170` — a CONSEQUENCE, at rule 33's cap: service fields were
          typed on the unit step and a draft opens no agreement to keep them. */}
      {serviceFieldsLostOnDraft(props.unit, props.mode) && (
        <Note>{t("customers.newAccount.review.serviceFieldsOnDraft")}</Note>
      )}

      {/* Hard-won law 2: what this create will NOT write, before it is run. */}
      <ArrivesWith
        title={t("customers.newAccount.review.notWrittenTitle")}
        message={t("customers.newAccount.review.notWritten")}
      />
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-003@bbed56d (story+rules snapshot — EP-CUS-02 lead story for the write path; co-packets EP-CUS-01@a2e1d59 · customers 02-business-rules@f125a9c)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 2 — S18, the screen `POST /accounts` shipped without) · AMENDED 2026-09-01 by the CR-056 W6 lane (`BR-CUS-1023` + `DEF-2818`): the step asks person-or-company and collects that kind's identifier, `createAccountPayload` SENDS the `customer` block — which this screen had never sent, so every account opened here had a blank customer column — and the commit toast carries the server's own sentence when no number was minted, because the flow navigates and the review row is never on screen long enough to read · AMENDED 2026-08-11 by story-coder (W2 customers FRONTEND lane 3 — the sub-line said "move-in has no endpoint yet"; S19 landed, so the string was rewritten with the fact per hard-won law 1) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 670 passed / 160 todo across 49 files✔ (622 passed / 148 todo across 47 files was the pre-lane baseline — the suite grew by 48 passing + 12 todo and nothing was dropped) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included; 5 locales × 2328 keys, identical sets)
// exceptions: (W6) NO TAILWIND UTILITY IS ADDED — this file is absent from `07-frontend/src/styles/route-b-migrated.txt`, so a utility here is declared by no stylesheet and renders as nothing while every test passes (B14 rule 21 · DEF-974); every class in the new section is one `customers.css` already declares · (W6) `customerNumberShortfall` is a HINT and never a gate: it blocks no step and disables no button, because the account opens either way · E3 step 3 (Plan) collects NOTHING: `plan` / `rate_plan_id` / `plan_version` are refused server-side because BR-CUS-029's `account_plan_assignments` has no DDL. The step renders the refusal WITH the rule and checks the picked unit's own default plan instead, because BR-MET-040 fails the activation without one · E3 step 5 (Deposit) collects NOTHING for the same shape of reason: `deposit_on_file`, `deposit_received_on` and `deposit_election` are refused (BR-CUS-023 — the amount is a lookup from the unbuilt plan deposit schedule) and the credit tier is COMPUTED with no input path (BR-CUS-058). Both steps are kept rather than dropped: BR-CUS-018's six-step rail is the ruled flow, and a silently shortened wizard hides the gap instead of naming it · E3 there is NO duplicate check and no customer record (BR-CUS-019/054): `customers` and `customer_accounts` have no tables and `customer`/`customer_id` are refused fields, so step 1 writes one contact on one account and says so where the prototype promises otherwise · E3 no initial-read control (BR-CUS-021 — `initial_reads` is refused; reads commit through metering's append-only service, B1) · E3 no paperless / SMS / budget-billing / statement-language controls (BR-CUS-028 — every one is a PROPOSED-SCHEMA column that was not built) and no bill-delivery-day selector (BR-CUS-060 — DROPPED, cycles decide bill dates) · E3 the prototype's ID TYPE selector is absent: `contacts.gov_id_type` is PROPOSED-SCHEMA and unbuilt, and only the last four digits are stored (BR-CUS-045) · E3 the review step shows the account number as allocated AT SAVE (BR-TEN-035) instead of the prototype's pre-printed "A-12048" · E4 the header's "Save draft & exit" and the step-6 "Save as draft" become ONE segmented choice on the review step, so exactly one transactional commit exists (BR-SHL-019) rather than two commit buttons racing · E4 `preferred_language` is a free-text field: the accepted set is the tenant's Regional language list, which no endpoint serves, and the server itself accepts free text while that seam is unwired — the help line says the server decides · E4 tax-exempt is collected although the prototype's step 4 does not draw it: BR-CUS-012 names it in the confirmed attribute set and the endpoint accepts all three fields
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/** `DEF-CUS-9505` — the review step, exported for its test. */
export const NewAccountReviewStep = ReviewStep;
