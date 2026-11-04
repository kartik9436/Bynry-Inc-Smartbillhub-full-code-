// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave N — `ACC-S1` (a clerk can correct an
//           account's details without a wizard) and `ACC-S15` (every group on
//           the Overview carries an edit control, disabled with its reason).
//           `BR-CUS-1053`, PO 2026-09-13: *"Build the account edit screen"* and
//           *"Correcting an account's details from the account … Every group on
//           the Overview carrying its own edit control"*.
//           Drawing: `05-prototype/02 Accounts Menu Blueprint.pdf` R5, pages
//           175–183 (`ACC-E01` the pattern, `ACC-E02` this dialog), pinned at
//           commit `033981d4f`, blob `3f4d75fb74c8a0dc483692c8c21e341215c562d7`.
// Rules:    BR-SHL-025 (a control that cannot act is disabled WITH its reason,
//           never hidden) · BR-CUS-017 (`unit_id` create-only) · BR-CUS-030
//           (closing is the move-out flow) · BR-CUS-067 (`account_subtypes` is
//           TENANT-defined, so no front-end catalogue holds the names) ·
//           BR-CUS-064 (`preferred_language` against tenancy's BR-TEN-042 set) ·
//           B14 rule 15 (row actions are ICONS with tooltips) · rule 31 (no
//           database id is ever a visible value) · rule 32 (description budget) ·
//           rule 33 (on-screen text is capped by what it is FOR) · rule 36
//           (compose the kit) · rule 38 (the UI rules decide how a form is
//           BUILT; the drawing decides what it CONTAINS) · rule 39 (field
//           anatomy — the kit already renders label → input → helper) ·
//           CLAUDE.md hard rule 7 (every money action writes `audit_log`).
// Tests:    AccountPanelEdits.dom.test.tsx (the PATCH body, key for key) ·
//           06-backend/tests/test_cr094_n_account_edit_scope.py (the scope)
// ───────────────────────────────────────────────────────
//
// ONE LIVE DIALOG, SEVEN REFUSALS, AND THE SERVER NEEDED NOTHING.
//
// `PATCH /accounts/{id}` has been mounted, handled, audited and tested since
// August and **had no caller in the entire front end** — `updateAccountNote`
// was the only account write any screen made. So a clerk could not correct a
// misspelt name or a wrong telephone number from anywhere in the product. The
// whole of `ACC-S1` is a wrapper and a form.
//
// ⚠ **A PENCIL PER GROUP, NOT ONE FORM OVER TWENTY-THREE FIELDS.** That is the
// asset module's answer to the same problem (`AST-B-25`, six panel pencils) and
// `07-frontend/src/features/assets/AssetPanelEdits.tsx` is the built precedent
// this file follows rather than re-invents: the same `RowActions`/`RowAction`
// pencil carrying its own reason, the same one-dispatcher-many-dialogs shape,
// the same `FormModal` from the kit.
//
// ⚠ **THE DRAWING DRAWS TWELVE GROUPS AND THE OVERVIEW RENDERS SEVEN, SO THIS
// PUTS A CONTROL ON THE SEVEN THAT EXIST — PLUS the mailing-address sub-head,
// which the drawing draws as a group of its own. Eight controls.** The five
// `R5` draws that the built Overview has no group for at all — `Money`,
// `Service`, `Plan`, `Unit` and a free-standing `Mailing address` panel — are
// KPI tiles, another tab, or nothing. **Creating five new panels is
// restructuring the Overview, which is not what `ACC-S15` asks for**, and
// putting a pencil on a heading that does not exist is not possible. Recorded
// in the decision log of 2026-09-13 with the count, rather than quietly built
// or quietly dropped.
//
// ⚠ **EXACTLY ONE OF THE EIGHT IS LIVE, AND THAT IS THE HONEST STATE OF THE
// SERVER RATHER THAN A PHASING CHOICE.** `Account` is the only group whose
// endpoint exists. `R5`'s own table says the same thing in its own words: of
// its twelve controls, *"Two of the twelve need no new server work at all"* —
// `Account`, and `Plan`, which opens a wizard that already runs.
//
// ⚠ **`Customer` IS HELD, AND THE HOLD CARRIES THE TEST THAT FIRES WHEN IT
// EXPIRES** — the brief's own instruction, and hard-won law 2's mirror, which
// cost the customer portal **two working doors out of eight** on 2026-09-05.
//
// **AND THE HOLD WAS RE-CHECKED RATHER THAN ASSUMED, WHICH CHANGED WHAT IT
// SAYS.** A sibling lane landed `BR-CUS-1054` while this wave was being built:
// `customerEndpoints.updateCustomer` and `CustomerEditDialog` both exist now.
// **They are not this panel.** `updateCustomer` writes the `customers` row —
// display name, external ref, date of birth, phone, email — and is mounted on
// the customer's OWN screen. This panel renders the ACCOUNT'S CONTACT
// (`account_contacts`), a different table, and **no route in the product writes
// a contact.** `R5` says the same in its own words: *"An endpoint. GET
// /customers/{id} is read-only and there is no contacts route at all."*
//
// So the refusal stands, and the expiry test asserts the thing that is actually
// missing — that `endpoints.ts` wraps no contact write. The day one lands, it
// goes red and names this file.
//
// ⚠ **AND A SEPARATE GAP WAS FOUND IN THE RE-CHECK, RECORDED AND NOT BUILT:**
// the account carries `detail.customer` and **there is no link from the account
// to its customer record anywhere on this screen**, so a clerk who needs to fix
// a name has to leave and search for the customer by hand. Decision log,
// 2026-09-13.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { UNEXPECTED_ERROR_KEY, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  ACCOUNT_UNIT_CORRECTION_REASONS,
  correctAccountUnit,
  getLookupEntries,
  getUnits,
  updateAccount,
  updateAccountContact,
  updateAccountMailingAddress,
} from "@/api/endpoints";
import type { AccountDetail, LookupEntry } from "@/api/endpoints";
import type { RegionalDateFormat } from "@/components/DateCell";
import {
  CheckboxField,
  DatePickerField,
  FormModal,
  SearchSelectField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import {
  CustomFieldsInput,
  customDataChanges,
  displayValue,
  useCustomFieldRegistry,
} from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import type { FormSubmitOutcome, ServerErrorEnvelope, Translator } from "@/components/FormModal";
import { PencilIcon } from "@/components/icons";
import { RecapBox } from "@/components/RecapBox";
import { RowAction, RowActions } from "@/components/RowActions";
import { ROLE_EXECUTIVE, ROLE_SYSTEM_ADMIN } from "@/features/metering/meteringShared";

import { accountCategoryName, primaryContact, useAccountCategories } from "./customersShared";
import { updateAccountCoApplicant } from "./customerEndpoints";
import { CONTACT_BY } from "./CoOwnerCards";
import { emailFormatProblem, phoneFormatProblem } from "./customerForm/CustomerWhoPanel";
import { FieldGrid } from "./serviceRequestShared";
import { UsAddressFields, usZipIsValid } from "@/components/UsAddressFields";
import { vacantUnitOptions } from "./NewAccountWizard";

/**
 * The eight Overview groups that carry a control.
 *
 * ⚠ **DERIVED NOWHERE AND TYPED HERE ON PURPOSE — these are the SCREEN's own
 * groups, not a server list.** Law 12 forbids hand-typing a list that another
 * surface owns (services, statuses, sub-types); a panel layout is owned by the
 * screen and by nothing else, which is why `AssetOverviewPanel` is a hand-typed
 * union in the asset precedent too.
 */
export type AccountOverviewGroup =
  | "account"
  /** ⚠ **THE FIVE ADDED 2026-09-13 ON THE PO's OWN SCOPE INSTRUCTION** —
   *  verbatim: *"also when I say Actions 13 plus all pencils on Overview
   *  screen"*. `R5`'s rule is *"Every group heading carries the control"* and
   *  `BR-SHL-025` is what that means where nothing can be written: DISABLED
   *  WITH ITS REASON, never hidden. Measured at 1440 before this change:
   *  thirteen groups render and five of them — money, service, meters, plan
   *  and customer record — carried no control at all, so a clerk could not tell
   *  a group that cannot be edited from one nobody had got to yet.
   *
   *  ⚠ **`plan` IS THE ONE THAT IS LIVE, AND IT ROUTES RATHER THAN DUPLICATES**
   *  — `R5`'s own words, *"an edit control that routes to a wizard rather than
   *  duplicating it"*, and its table gives Plan *"The Change plan wizard"* with
   *  *"Nothing"* waiting on it. It is handled by the PAGE, not by the dialog
   *  dispatcher below, so no second plan form can ever grow here. */
  | "money"
  | "service"
  | "meters"
  | "plan"
  | "customerRecord"
  /** ⚠ ADDED 2026-09-13 — see `accountGroupBlockedReason`. The Product Owner
   *  drove the live screen and reported *"I cannot edit … Billing
   *  preferences"*. Its four rows are `accounts` columns that `PATCH
   *  /accounts/{id}` has written since August; the group simply had no
   *  control. Built-not-wired (hard-won law 2), on a served endpoint. */
  | "billingPrefs"
  /** ⚠ ADDED 2026-09-13 WITH THE GROUP ITSELF — `ACC-02` R5 draws
   *  `UNIT — WHAT THIS ACCOUNT IS ATTACHED TO ✎Change unit` and the screen
   *  rendered no unit group at all. `R5`'s own rule is *"Every group heading
   *  carries the control"*, so the group arrives with one. See
   *  `accountGroupBlockedReason` for why it is refused rather than live. */
  | "unit"
  | "bills"
  | "usage"
  | "customer"
  /** ⊕ T4 (`DEF-CUS-6391`, PO 2026-09-23) — the account's SECOND person,
   *  *"shown on the account page"*, and editable there. */
  | "coApplicant"
  | "mailing"
  | "deposit"
  | "portal";

/**
 * **WHY EACH GROUP CANNOT BE EDITED — the sentence a clerk reads on the
 * disabled pencil.** `null` means the group is live.
 *
 * ⚠ **THE REASONS ARE FACTS ABOUT THE WORK, NOT RATIONALE ABOUT THE PRODUCT.**
 * B14 rule 33 is explicit that *why the product works this way, why a control
 * is absent, is ZERO WORDS ON SCREEN* — so `bills` says what a clerk should do
 * instead ("a bill is credited, never edited") and does not explain hard rule 4.
 * Each is at most six words, which is rule 33's cap for a refusal.
 *
 * ⚠ **`payment method` IS NOT IN THIS MAP AND THAT IS DELIBERATE.** That panel
 * has shipped its own disabled `→ Update method` control since `CR-030` W3 —
 * it is the one place the product already agreed with `R5` — and a second
 * control beside it would be two refusals for one fact. `R5` says as much:
 * *"Already shipped this way — the one panel that proves the pattern."*
 */
export function accountGroupBlockedReason(
  group: AccountOverviewGroup,
  t: Translator,
): string | null {
  switch (group) {
    case "account":
      // `PATCH /accounts/{id}` — served, audited, tested, and now called.
      return null;
    case "billingPrefs":
      // ⚠ **LIVE FROM 2026-09-13, AND IT NEEDED NO SERVER WORK AT ALL.** All
      // four drawn rows a clerk can change — `autopay`, `paperless`,
      // `sms_reminders`, `preferred_language` — are in `services.PATCH_FIELDS`
      // and have been since August. The group rendered with NO control, so the
      // Product Owner could not reach a door that was already open. The fifth
      // row, `Notification template`, is a stated absence and is deliberately
      // not on the form: the server works it out at bill time and does not put
      // it on this payload.
      return null;
    case "bills":
      // Hard rule 4: an issued invoice takes no UPDATE; it is credited.
      return t("customers.account.edit.blocked.bills");
    case "usage":
      // The figure is MEASURED. The read is what gets corrected, in metering.
      return t("customers.account.edit.blocked.usage");
    case "coApplicant":
      return null;
    case "customer":
      // ⚠ **LIVE FROM 2026-09-13, AND THE HOLD IT REPLACES WAS RIGHT ABOUT THE
      // WRONG TABLE.** The note here said `BR-CUS-1054` would land it; that
      // shipped `PATCH /customers/{id}`, which writes the `customers` row on
      // the CUSTOMER's own screen. This group renders `contacts` — keyed to the
      // ACCOUNT — and nothing wrote those at all. `PATCH /accounts/{id}/contact`
      // is the door that was missing, built with this fix.
      return null;
    case "mailing":
      // ⚠ **LIVE FROM 2026-09-13.** The sentence above was TRUE when it was
      // written — hard rule 8's named exception had a create path and no
      // correction path — and `PATCH /accounts/{id}/mailing-address` is that
      // path. A customer who moves their post is followed without a new
      // account now.
      return null;
    case "deposit":
      // BR-CUS-023/050: written by the deposit path when a payment clears.
      return t("customers.account.edit.blocked.deposit");
    case "portal":
      // CR-068's portal: a customer enrols themselves; no staff door creates
      // a sign-in, and `paperless` is edited on the Account form instead.
      return t("customers.account.edit.blocked.portal");
    case "money":
      // `R5`: *"Nothing. It is worked out from the ledger; the way to change it
      // is an adjustment."* Every row in this group is DERIVED — the basis, the
      // source, the ageing band, the days past due, the deposit — so there is
      // no column to write. The refusal names the act a clerk should reach for
      // instead, which is rule 33's *keep the instruction, cut the rationale*.
      return t("customers.account.edit.blocked.money");
    case "service":
      // ⚠ **CHECKED ON THE WIRE AND NOT IN THE TYPE (the brief's own rule).**
      // `06-backend/apps/customers/api.py` mounts NO route that starts, ends or
      // amends a service agreement, and `service_agreement` appears in no
      // module's api.py at all. `R5` says the same in its own words: *"An
      // endpoint. No route starts, ends or amends an account's service
      // agreements."* So this is not a control held back by phasing; there is
      // nothing for it to call. Moving IN and OUT is how a service starts and
      // stops today, and that is what the refusal points at.
      return t("customers.account.edit.blocked.service");
    case "meters":
      // ⚠ **A MODULE BOUNDARY, NOT A GAP.** A meter is an ASSET and `B2` r4
      // gives assets to metering; this group READS them. `R5` does not draw a
      // Meters group at all, and CLAUDE.md's cross-module rule is absolute — a
      // customers screen never writes another module's table. The refusal names
      // where the change is made instead of explaining the architecture.
      return t("customers.account.edit.blocked.meters");
    case "plan":
      // ⚠ **LIVE, AND HANDLED BY THE PAGE.** `POST /accounts/{id}/plan-changes`
      // is served and wired and the three-step wizard already runs; `R5` gives
      // this control *"The Change plan wizard"* and *"Nothing"* waiting on it.
      // Returning null here makes the pencil pressable; `AccountDetailPage`
      // sends it to the wizard rather than to the dispatcher below.
      return null;
    case "unit":
      // ⚠ **LIVE FROM 2026-09-13, AND THE HOLD IT REPLACES WAS TRUE FOR ONE DAY
      // (`DEF-CUS-5163`).** `R5`'s own table gave this control *"A PO ruling,
      // not an endpoint"* — the server refused `unit` by name, create-only.
      // **That ruling landed**: `BR-CUS-1047`, PO 2026-09-12, and
      // `POST /accounts/{id}/correct-unit` built 2026-09-13. Nothing in the
      // front end called it, which is hard-won law 2's mirror — a working door
      // behind a dead control — so the pencil is live and this returns null.
      //
      // ⚠ **THE REFUSAL THAT REMAINS IS A ROLE AND IT IS NOT DECIDED HERE.**
      // `@require_role(SYSTEM_ADMIN, EXECUTIVE)` gates the write and a Billing
      // Clerk gets `AUTH-002`; that is per-USER and this map is per-GROUP, so
      // it is applied in `AccountGroupPencil` where the caller's own role is
      // known. `BR-SHL-025`: the control is drawn disabled with its reason,
      // never hidden, and the server's guard is the boundary either way.
      return null;
    case "customerRecord":
      // Both rows are DERIVED from the account's link to a customer:
      // `customer_no` is the customer's own number and the count is of their
      // accounts. `customer_id` is in neither `PATCH_FIELDS` nor
      // `REFUSED_FIELDS` on `PATCH /accounts/{id}`, so no door relinks an
      // account from here, and the customer's own screen is where their details
      // are corrected (`BR-CUS-1054`).
      return t("customers.account.edit.blocked.customerRecord");
  }
}

/**
 * **ONE GROUP NEEDS THE CALLER'S ROLE AND NOT JUST THE SURFACE CELL.**
 *
 * A4 grades Accounts `Full` for a Billing Clerk, so the page's own
 * `canWriteReason` is null for them — and `POST /accounts/{id}/correct-unit`
 * still answers 403 `AUTH-002`, because `BR-CUS-1047` requires a supervisor's
 * approval and `OQ-042`'s closure names the two roles that count (*"supervisor
 * = SysAdmin/Executive"*). Without this a clerk meets the refusal only after
 * filling the whole form.
 *
 * ⚠ **A NULL ROLE OFFERS THE CONTROL, DELIBERATELY.** `/me/permissions` may not
 * have answered yet, and `BR-SHL-025`'s own caveat applies: this decides only
 * whether the control is offered or drawn disabled with its reason, and the
 * server's `@require_role` is the boundary either way. Locking a supervisor out
 * of their own act because a read was slow is the worse failure.
 *
 * ⚠ **PURE, AND IT IS NOT A HOOK INSIDE `AccountGroupPencil` (2026-09-13).**
 * The first draft called `useTenantRole()` in that component, which made every
 * bare render of a pencil require a `QueryClientProvider` — two existing cases
 * went red with *"No QueryClient set"* over a control that had never needed
 * one. The hook belongs where one already exists: the page reads the role once
 * and passes the sentence down.
 */
export function accountGroupRoleReason(
  group: AccountOverviewGroup,
  role: string | null,
  t: Translator,
): string | null {
  if (group !== "unit" || role === null) return null;
  return role === ROLE_SYSTEM_ADMIN || role === ROLE_EXECUTIVE
    ? null
    : t("customers.account.edit.blocked.unitRole");
}

/**
 * The pencil, once — `B14` rule 15 (row actions are ICONS with a tooltip, never
 * text links) through the kit's `RowAction`, which is where `BR-SHL-025` is
 * already implemented: `reason` and `disabled` are ONE prop, so a caller
 * *cannot* disable this control without saying why.
 *
 * `roleReason` is the caller's write-permission refusal and WINS over the
 * group's own, because a clerk who may not write anything needs to be told that
 * first — the same precedence `RowAction` applies everywhere else.
 */
export function AccountGroupPencil(props: {
  group: AccountOverviewGroup;
  t: Translator;
  /** A role/state refusal from the page. `null` = this clerk may write. */
  roleReason?: string | null;
  onEdit: (group: AccountOverviewGroup) => void;
}) {
  const blocked = props.roleReason ?? accountGroupBlockedReason(props.group, props.t);
  return (
    <RowActions>
      <RowAction
        label={props.t(`customers.account.edit.group.${props.group}`)}
        icon={<PencilIcon />}
        reason={blocked}
        onClick={() => props.onEdit(props.group)}
      />
    </RowActions>
  );
}

const EMPTY_SCHEMA = z.object({});

/**
 * ⊕ **`DEF-CUS-10253` — MOVE-IN'S RULES ON THE ACCOUNT PAGE'S PERSON DIALOGS**
 * (PO 2026-10-18, image `08-edit.png`: *"Same required rules and format
 * checks"*). A name always; a phone where the dialog is about the account
 * holder; both contact boxes in a valid shape, through the SAME format checks
 * Move-in's Who panel uses (`CustomerWhoPanel`). Messages are translated here
 * because a custom zod issue's message is printed as given.
 */
function personSchema(t: Translator, phoneRequired: boolean, idPrefix: string) {
  // The issue's PATH is the box's id (`contact_phone`), which is how the kit
  // ties a refusal to the box it is about.
  const at = (key: string) => [`${idPrefix}${key}`];
  return z
    .object({ full_name: z.string(), email: z.string(), phone: z.string() })
    .passthrough()
    .superRefine((values, ctx) => {
      if (values.full_name.trim() === "") {
        ctx.addIssue({ code: "custom", path: at("full_name"), message: t("customers.contact.name_required") });
      }
      if (phoneRequired && values.phone.trim() === "") {
        ctx.addIssue({ code: "custom", path: at("phone"), message: t("customers.customer.edit.phoneRequired") });
      }
      const phone = phoneFormatProblem(values.phone);
      if (phone !== null) ctx.addIssue({ code: "custom", path: at("phone"), message: t(phone) });
      const email = emailFormatProblem(values.email);
      if (email !== null) ctx.addIssue({ code: "custom", path: at("email"), message: t(email) });
    });
}

/** ⊕ `DEF-CUS-10253` — Street, City, State and a US ZIP, unless the street is
 *  being CLEARED (which removes the row: the bill goes to the service address). */
function mailingSchema(t: Translator) {
  return z
    .object({ line1: z.string(), line2: z.string(), city: z.string(), state: z.string(), postal_code: z.string() })
    .superRefine((values, ctx) => {
      if (values.line1.trim() === "") return;
      for (const key of ["city", "state", "postal_code"] as const) {
        if (values[key].trim() === "") {
          ctx.addIssue({ code: "custom", path: [`mailing_${key}`], message: t("errors.val-002") });
        }
      }
      if (values.postal_code.trim() !== "" && !usZipIsValid(values.postal_code)) {
        ctx.addIssue({ code: "custom", path: ["mailing_postal_code"], message: t("common.usAddress.zipFormat") });
      }
    });
}

/** `DEF-CUS-5176` — an `ApiError` rendered as the envelope the form reads.
 *  Anything that is not an `ApiError` (a thrown string, a network object) falls
 *  back to the catalogue's own unexpected-error key, so the clerk always reads
 *  a sentence rather than a blank alert. */
function toEnvelope(error: unknown): ServerErrorEnvelope {
  if (isApiError(error)) return formErrorEnvelope(error);
  return { code: "", message_key: UNEXPECTED_ERROR_KEY };
}

/** A `PATCH` that renders its refusal under the field it names (B12 §3).
 *  The server answers `customers.account.field_not_writable` with the owning
 *  rule id in `params`, so a refused column explains itself without this file
 *  holding a second copy of `REFUSED_FIELDS`. */
async function patch(
  accountId: string,
  body: Record<string, unknown>,
  client: ApiClient | undefined,
): Promise<FormSubmitOutcome> {
  try {
    await (client === undefined
      ? updateAccount(accountId, body)
      : updateAccount(accountId, body, client));
    return { ok: true };
  } catch (error) {
    // ⚠ **`DEF-CUS-5176` — A CAST IS NOT A CONVERSION, AND THE REFUSAL WAS
    // RENDERING AS NOTHING.** This read `error as ServerErrorEnvelope`. What is
    // thrown is an `ApiError`, whose fields are `messageKey`/`fieldErrors`;
    // `envelopeErrors` reads `message_key`/`field_errors`, so it translated
    // `undefined` and the `role="alert"` paragraph came out EMPTY. `tsc` is
    // happy — the cast asserts the shape — and a refusal that renders as
    // nothing is indistinguishable from a form that simply did nothing (B14
    // rule 33's own warning about silence, and hard-won law 2's shape).
    // `formErrorEnvelope` is the conversion `api/client.ts` already exports for
    // exactly this, and it maps the FIELD errors too, so a refused field is
    // marked instead of the whole form shrugging.
    return { ok: false, error: toEnvelope(error) };
  }
}

/**
 * The dispatcher. One dialog today; the `switch` is what a sibling lane adds a
 * case to when `Customer` or `Unit` lands, rather than growing a second pencil
 * mechanism beside this one.
 */
export function AccountPanelEditDialog(props: {
  detail: AccountDetail;
  group: AccountOverviewGroup;
  client?: ApiClient;
  t: Translator;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSaved: () => void;
}) {
  if (props.group === "billingPrefs") return <EditBillingPreferencesDialog {...props} />;
  if (props.group === "customer") return <EditContactDialog {...props} />;
  if (props.group === "coApplicant") return <EditCoApplicantDialog {...props} />;
  if (props.group === "mailing") return <EditMailingAddressDialog {...props} />;
  if (props.group === "unit") return <CorrectUnitDialog {...props} />;
  // ⚠ **`plan` NEVER REACHES HERE AND MUST NOT.** It routes to the Change plan
  // wizard from the page, which is `R5`'s *"routes to a wizard rather than
  // duplicating it"*. A case added here would be a second plan form beside a
  // three-step one that already runs — the duplicate code the PO's standing
  // instruction forbids.
  if (props.group !== "account") {
    // Every other group is refused on its pencil, so this is unreachable —
    // a bug rather than a state, exactly as the asset precedent records.
    return null;
  }
  return <EditAccountDialog {...props} />;
}

/**
 * `ACC-E02` — *Edit the account*, page 177. The one form of the five that needs
 * no new server work.
 *
 * **THE EIGHT FIELDS, IN THE DRAWING'S OWN ORDER AND GROUPING.** `R5` draws
 * three sections — *What kind of account this is* → *Tax* → *Delivery and
 * contact preferences* — and what a form CONTAINS is the drawing's to decide
 * (B14 rule 38's last clause). What it looks like is B14's, and three
 * divergences are recorded rather than followed:
 *
 *   1. **The section headings are SHORTENED.** The drawing writes *"WHAT KIND
 *      OF ACCOUNT THIS IS"* and *"DELIVERY AND CONTACT PREFERENCES"*; rule 33
 *      caps a heading at THREE WORDS and forbids it being a sentence.
 *   2. **`Preferred language` is a TEXT FIELD, not the drawn select.** No
 *      endpoint lists the tenant's `BR-TEN-042` language set, so a select could
 *      only be hand-typed — which law 12 forbids by name — or empty. The text
 *      field is also what `NewAccountWizard` and `MoveInWizard` already render
 *      for this same column, and a second construction for one field is the
 *      drift rule 36 exists to stop.
 *   3. **The *not editable here* list carries LABELS, not the drawing's
 *      reasons.** *"Unit — an account never moves between units; a new occupant
 *      is a move-in"* is RATIONALE, which rule 33 puts at zero words on screen.
 *      The reasons live here, in the code. Same resolution the asset precedent
 *      reached for its own `NotOnThisForm`.
 *
 * ⚠ **`status` AND `opened_at` ARE WRITABLE AND ARE NOT OFFERED.** Both are in
 * `PATCH_FIELDS`; neither is drawn. `R5` refuses `status` on the form in its own
 * words — *"closing an account is the move-out flow, not an edit"* — and
 * `opened_at` moves what a bill run picks up, which is not a typo fix. Recorded
 * in the decision log rather than dropped in silence, and pinned by
 * `test_cr094_n_account_edit_scope.py::…tc4`.
 */
function EditAccountDialog(props: {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { detail, t } = props;
  const [values, setValues] = useState({
    account_subtype: detail.account_subtype ?? "",
    tax_exempt: detail.tax_exempt,
    tax_exempt_ref: detail.tax_exempt_ref ?? "",
    tax_exempt_expires: detail.tax_exempt_expires ?? "",
    preferred_language: detail.preferred_language ?? "",
    paperless: detail.paperless ?? false,
    sms_reminders: detail.sms_reminders ?? false,
    autopay: detail.autopay,
  });
  // `DEF-CUS-9158` — the utility's OWN account fields placed Input on Account
  // detail (slot S21) are edited HERE, in the Account setup dialog whose panel
  // already shows them read-only. Seeded from the row's stored answers; only
  // the keys that CHANGED travel, and the server merges them into the stored
  // blob (`custom_fields.validate_custom_data(existing=…)`), so an answer typed
  // on another screen is never wiped by an edit here.
  const [customData, setCustomData] = useState<CustomFieldValues>(() => ({
    ...(detail.custom_data ?? {}),
  }));
  const customFields = useCustomFieldRegistry({
    entity: "accounts",
    screen: "S21",
    mode: "input",
    client: props.client,
  });

  // BR-CUS-067 — the sub-type list is the TENANT'S, read through the shared
  // lookup door. Never a front-end catalogue: that is `DEF-684`'s mistake for
  // categories, where three of seven codes fell through to their raw slug.
  const subtypes = useQuery({
    queryKey: ["lookups", "account_subtypes"],
    queryFn: () =>
      props.client === undefined
        ? getLookupEntries("account_subtypes", { per: 200 })
        : getLookupEntries("account_subtypes", { per: 200 }, props.client),
  });
  const subtypeOptions = (subtypes.data?.results ?? []).map((row: LookupEntry) => ({
    value: row.code,
    label: row.name,
  }));

  // ⚠ **THE COMMENT BELOW CLAIMED THE CATALOGUE NAME AND THE CODE PRINTED THE
  // RAW ENUM (`DEF-CUS-5154`).** The dialog read `Category: residential` while
  // the Overview group two inches behind it read `Residential`, resolved
  // through this very hook — hard-won law 1 exactly: a comment claiming a
  // guarantee is not the guarantee, and B14 rule 31 forbids a database value
  // being what a clerk reads. The FALLBACK is still the code and never an
  // invented label — `DEF-684`'s ruling — so an unknown category degrades to
  // its slug rather than to a guess.
  const categories = useAccountCategories(props.client);

  // ⚠ **THE BODY IS BUILT FROM WHAT CHANGED, NOT FROM THE WHOLE FORM.**
  // `update_account` compares before saving and writes NO audit row when
  // nothing moved, so sending every field would be harmless — but a body that
  // names only the edits is what the recap below is computed from, and one
  // source for both is what stops the recap and the request disagreeing.
  const changed: Record<string, unknown> = {};
  if (values.account_subtype !== (detail.account_subtype ?? "")) {
    changed.account_subtype = values.account_subtype === "" ? null : values.account_subtype;
  }
  if (values.tax_exempt !== detail.tax_exempt) changed.tax_exempt = values.tax_exempt;
  if (values.tax_exempt_ref !== (detail.tax_exempt_ref ?? "")) {
    changed.tax_exempt_ref = values.tax_exempt_ref;
  }
  if (values.tax_exempt_expires !== (detail.tax_exempt_expires ?? "")) {
    changed.tax_exempt_expires =
      values.tax_exempt_expires === "" ? null : values.tax_exempt_expires;
  }
  if (values.preferred_language !== (detail.preferred_language ?? "")) {
    changed.preferred_language = values.preferred_language;
  }
  if (values.paperless !== (detail.paperless ?? false)) changed.paperless = values.paperless;
  if (values.sms_reminders !== (detail.sms_reminders ?? false)) {
    changed.sms_reminders = values.sms_reminders;
  }
  if (values.autopay !== detail.autopay) changed.autopay = values.autopay;
  const customChanged = customDataChanges(detail.custom_data ?? {}, customData);
  if (Object.keys(customChanged).length > 0) changed.custom_data = customChanged;

  const yes = t("customers.account.yes");
  const no = t("customers.account.no");
  const recapRows: { label: string; value: string }[] = [];
  if ("account_subtype" in changed) {
    recapRows.push({
      label: t("customers.account.field.subtype"),
      value:
        subtypeOptions.find((option) => option.value === values.account_subtype)?.label ??
        values.account_subtype,
    });
  }
  if ("tax_exempt" in changed) {
    recapRows.push({
      label: t("customers.account.field.taxExempt"),
      value: values.tax_exempt ? yes : no,
    });
  }
  if ("tax_exempt_ref" in changed) {
    recapRows.push({
      label: t("customers.newAccount.field.taxExemptRef"),
      value: values.tax_exempt_ref,
    });
  }
  if ("tax_exempt_expires" in changed) {
    recapRows.push({
      label: t("customers.account.field.taxExemptExpires"),
      value: values.tax_exempt_expires,
    });
  }
  if ("preferred_language" in changed) {
    recapRows.push({
      label: t("customers.account.field.preferredLanguage"),
      value: values.preferred_language,
    });
  }
  if ("paperless" in changed) {
    recapRows.push({
      label: t("customers.account.portal.paperless"),
      value: values.paperless ? yes : no,
    });
  }
  if ("sms_reminders" in changed) {
    recapRows.push({
      label: t("customers.account.portal.sms"),
      value: values.sms_reminders ? yes : no,
    });
  }
  if ("autopay" in changed) {
    recapRows.push({
      label: t("customers.accounts.filter.autopay"),
      value: values.autopay ? yes : no,
    });
  }
  // Each changed custom field by its OWN label, read from the same registry
  // the controls render from — never its key (B14 rule 31).
  for (const field of customFields.data ?? []) {
    if (!(field.key in customChanged)) continue;
    recapRows.push({
      label: field.label,
      value: displayValue(field, customData, (iso) => iso, t),
    });
  }

  return (
    <FormModal
      // B14 rule 31 — the kicker is the ACCOUNT NUMBER and the customer's name,
      // never the uuid this dialog is keyed by.
      kicker={[detail.account_no, detail.contacts[0]?.full_name]
        .filter((part) => part !== null && part !== undefined && part !== "")
        .join(" · ")}
      title={t("customers.account.edit.dialogTitle")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={t("customers.account.edit.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patch(detail.id, changed, props.client);
        if (outcome.ok) props.onSaved();
        return outcome;
      }}
    >
      <h4 className="cus-subhead">{t("customers.account.edit.section.kind")}</h4>
      {/* The CATEGORY is shown and not offered — `account_type` is create-only
          and moving an account between categories reprices it. A fact, at rule
          33's six-word cap, with the name the platform catalogue holds and
          never the raw code (`DEF-CUS-5000`, and `DEF-CUS-5154` for the day
          this line said so and did the opposite). */}
      <p className="field-help">
        {t("customers.account.edit.category")}:{" "}
        {accountCategoryName(detail.account_type, categories.all)}
      </p>
      <SelectField
        id="account_subtype"
        label={t("customers.account.field.subtype")}
        help={t("customers.account.edit.subtypeHelp")}
        value={values.account_subtype}
        options={subtypeOptions}
        onChange={(value) => setValues({ ...values, account_subtype: value })}
      />

      <h4 className="cus-subhead">{t("customers.account.edit.section.tax")}</h4>
      <CheckboxField
        id="tax_exempt"
        label={t("customers.account.field.taxExempt")}
        checked={values.tax_exempt}
        onChange={(checked) => setValues({ ...values, tax_exempt: checked })}
      />
      {/* The certificate and its expiry belong to the exemption and are asked
          for only when there is one — exactly as `NewAccountWizard` already
          renders the same three fields. */}
      {values.tax_exempt && (
        <>
          <TextField
            id="tax_exempt_ref"
            label={t("customers.newAccount.field.taxExemptRef")}
            help={t("customers.account.edit.taxExemptRefHelp")}
            value={values.tax_exempt_ref}
            onChange={(value) => setValues({ ...values, tax_exempt_ref: value })}
          />
          <DatePickerField
            id="tax_exempt_expires"
            label={t("customers.account.field.taxExemptExpires")}
            help={t("customers.account.edit.taxExemptExpiresHelp")}
            dateFormat={props.dateFormat}
            value={values.tax_exempt_expires}
            onChange={(value) => setValues({ ...values, tax_exempt_expires: value })}
          />
        </>
      )}
      <TextField
        id="preferred_language"
        label={t("customers.account.field.preferredLanguage")}
        help={t("customers.newAccount.preferences.languageHelp")}
        value={values.preferred_language}
        onChange={(value) => setValues({ ...values, preferred_language: value })}
      />

      <h4 className="cus-subhead">{t("customers.account.edit.section.delivery")}</h4>
      <CheckboxField
        id="paperless"
        label={t("customers.account.portal.paperless")}
        checked={values.paperless}
        onChange={(checked) => setValues({ ...values, paperless: checked })}
      />
      <p className="field-help">{t("customers.account.edit.paperlessHelp")}</p>
      <CheckboxField
        id="sms_reminders"
        label={t("customers.account.portal.sms")}
        checked={values.sms_reminders}
        onChange={(checked) => setValues({ ...values, sms_reminders: checked })}
      />
      <CheckboxField
        id="autopay"
        label={t("customers.accounts.filter.autopay")}
        checked={values.autopay}
        onChange={(checked) => setValues({ ...values, autopay: checked })}
      />
      <p className="field-help">{t("customers.account.edit.autopayHelp")}</p>

      {/* Renders NOTHING when the utility placed no account field Input on
          Account detail, so this dialog is unchanged for them (US-SHL-015 TC-4). */}
      <CustomFieldsInput
        entity="accounts"
        screen="S21"
        values={customData}
        onChange={setCustomData}
        client={props.client}
      />

      <NotEditableHere t={t} />

      {/* B14 rule 11 — a form that moves tax and delivery on a billable record
          shows what it will do before it commits. `R5` draws it as *REVIEW ·
          What pressing the button will change*; the heading is shortened to
          rule 33's three-word cap and the rows are computed from the SAME
          object the request is built from, so the two cannot disagree. */}
      <div className="mt-5">
        <RecapBox
          title={t("customers.account.edit.recap")}
          data-recap="account-edit"
          rows={
            recapRows.length === 0
              ? [
                  {
                    label: t("customers.account.edit.recap"),
                    value: t("customers.account.edit.recapNothing"),
                  },
                ]
              : recapRows
          }
          outcome={{
            label: t("customers.account.edit.recapAudit"),
            value: t("customers.account.edit.recapAuditValue"),
            testId: "audit",
          }}
        />
      </div>
    </FormModal>
  );
}

/**
 * **BILLING PREFERENCES — the group the Product Owner could not edit, and the
 * endpoint was already there.**
 *
 * PO, driving the live screen on 2026-09-13: *"I cannot edit Customer details,
 * Mailing address, Billing preferences, Portal access"*. Three of those four are
 * genuine gaps in the SERVER. This one was not: `autopay`, `paperless`,
 * `sms_reminders` and `preferred_language` are all in `services.PATCH_FIELDS`
 * and `EditAccountDialog` above has been writing them since wave N — through
 * the ACCOUNT SETUP pencil, which is the wrong heading for them and is where a
 * clerk would never look. **The group itself carried no control at all.**
 *
 * ⚠ **A FORM PER GROUP, NOT ONE FORM REACHED FROM TWO PENCILS.** `R5`'s rule is
 * *"every group heading carries the control"*, and the point of that is that
 * the control edits WHAT IS UNDER IT. Opening the whole account form from
 * BILLING PREFERENCES would put tax-exemption fields under a heading about
 * paperless bills, which is the information-architecture mistake the PO's
 * 2026-09-10 grouping ruling exists to delete.
 *
 * ⚠ **THE FIFTH DRAWN ROW, `Notification template`, IS NOT ON THIS FORM.** It
 * is a stated absence on the screen: the server works the template out when a
 * bill is raised (`bill_template_election_for_account`) and does not put it on
 * this payload, so there is no value to edit and no column on `accounts` to
 * write. Drawing a control for it would be a form field that posts nowhere.
 *
 * ⚠ **AUTOPAY CARRIES ITS WARNING ON THE FORM, NOT ONLY ON THE PILL** (`DEF-644`).
 * Autopay in this version is *"a promise recorded, never a charge"*
 * (`apps/payments/models.py:623`), so the moment a clerk switches it ON is the
 * moment the mistake is made. The helper under the checkbox is the one the
 * account form already uses — one sentence, one wording.
 */
function EditBillingPreferencesDialog(props: {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { detail, t } = props;
  const [values, setValues] = useState({
    autopay: detail.autopay,
    paperless: detail.paperless ?? false,
    sms_reminders: detail.sms_reminders ?? false,
    preferred_language: detail.preferred_language ?? "",
    // `DEF-CUS-9820` — PO ruling 2026-10-06 D4 (a): *"add an editable "PO on
    // bills" field to the account's Billing preferences"*. Bills drafted after
    // the change print the new PO; issued bills keep theirs (the server stamps
    // the PO at assembly and never rewrites an issued bill).
    po_number: detail.po_number ?? "",
  });

  // Built from what CHANGED, for `EditAccountDialog`'s reason: one object
  // behind both the request and the recap, so the two cannot disagree.
  const changed: Record<string, unknown> = {};
  // Trimmed, as the server trims it; blank CLEARS the PO (sent as "", stored
  // as no PO). Longer than 60 is refused by the server under this field.
  const po = values.po_number.trim();
  if (po !== (detail.po_number ?? "")) changed.po_number = po;
  if (values.autopay !== detail.autopay) changed.autopay = values.autopay;
  if (values.paperless !== (detail.paperless ?? false)) changed.paperless = values.paperless;
  if (values.sms_reminders !== (detail.sms_reminders ?? false)) {
    changed.sms_reminders = values.sms_reminders;
  }
  if (values.preferred_language !== (detail.preferred_language ?? "")) {
    changed.preferred_language = values.preferred_language;
  }

  const yes = t("customers.account.yes");
  const no = t("customers.account.no");
  const recapRows: { label: string; value: string }[] = [];
  if ("autopay" in changed) {
    recapRows.push({
      label: t("customers.accounts.filter.autopay"),
      value: values.autopay ? yes : no,
    });
  }
  if ("paperless" in changed) {
    recapRows.push({
      label: t("customers.account.portal.paperless"),
      value: values.paperless ? yes : no,
    });
  }
  if ("sms_reminders" in changed) {
    recapRows.push({
      label: t("customers.account.portal.sms"),
      value: values.sms_reminders ? yes : no,
    });
  }
  if ("preferred_language" in changed) {
    recapRows.push({
      label: t("customers.account.field.preferredLanguage"),
      value: values.preferred_language,
    });
  }
  if ("po_number" in changed) {
    recapRows.push({
      label: t("customers.moveIn.review.po"),
      value: po === "" ? t("customers.moveIn.review.none") : po,
    });
  }

  return (
    <FormModal
      // B14 rule 31 — the account NUMBER and the customer's name, never the uuid.
      kicker={[detail.account_no, detail.contacts[0]?.full_name]
        .filter((part) => part !== null && part !== undefined && part !== "")
        .join(" · ")}
      title={t("customers.account.panel.billingPrefs")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={t("customers.account.edit.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patch(detail.id, changed, props.client);
        if (outcome.ok) props.onSaved();
        return outcome;
      }}
    >
      <CheckboxField
        id="prefs_autopay"
        label={t("customers.accounts.filter.autopay")}
        checked={values.autopay}
        onChange={(checked) => setValues({ ...values, autopay: checked })}
      />
      <p className="field-help">{t("customers.account.edit.autopayHelp")}</p>
      <CheckboxField
        id="prefs_paperless"
        label={t("customers.account.portal.paperless")}
        checked={values.paperless}
        onChange={(checked) => setValues({ ...values, paperless: checked })}
      />
      <p className="field-help">{t("customers.account.edit.paperlessHelp")}</p>
      <CheckboxField
        id="prefs_sms"
        label={t("customers.account.portal.sms")}
        checked={values.sms_reminders}
        onChange={(checked) => setValues({ ...values, sms_reminders: checked })}
      />
      {/* A TEXT field and not the drawn select, for `EditAccountDialog`'s own
          reason: no endpoint lists the tenant's `BR-TEN-042` language set, so a
          select could only be hand-typed — which law 12 forbids by name — or
          empty. It is also what both wizards already render for this column. */}
      <TextField
        id="prefs_preferred_language"
        label={t("customers.account.field.preferredLanguage")}
        help={t("customers.newAccount.preferences.languageHelp")}
        value={values.preferred_language}
        onChange={(value) => setValues({ ...values, preferred_language: value })}
      />
      {/* `DEF-CUS-9820` — LAST, as the panel draws it. The id is the server's
          field name so a refusal (over 60 characters) renders under it. */}
      <TextField
        id="po_number"
        label={t("customers.moveIn.review.po")}
        value={values.po_number}
        autoComplete="off"
        onChange={(value) => setValues({ ...values, po_number: value })}
      />

      <div className="mt-5">
        <RecapBox
          title={t("customers.account.edit.recap")}
          data-recap="billing-prefs-edit"
          rows={
            recapRows.length === 0
              ? [
                  {
                    label: t("customers.account.edit.recap"),
                    value: t("customers.account.edit.recapNothing"),
                  },
                ]
              : recapRows
          }
          outcome={{
            label: t("customers.account.edit.recapAudit"),
            value: t("customers.account.edit.recapAuditValue"),
            testId: "audit",
          }}
        />
      </div>
    </FormModal>
  );
}

/** A `PATCH` through one of the two account-scoped write doors built on
 *  2026-09-13, shaped exactly like `patch` above so a refusal still renders
 *  under the field the server names. */
async function patchThrough(
  call: (id: string, body: Record<string, unknown>, client?: ApiClient) => Promise<unknown>,
  accountId: string,
  body: Record<string, unknown>,
  client: ApiClient | undefined,
): Promise<FormSubmitOutcome> {
  try {
    await (client === undefined ? call(accountId, body) : call(accountId, body, client));
    return { ok: true };
  } catch (error) {
    // ⚠ **`DEF-CUS-5176` — A CAST IS NOT A CONVERSION, AND THE REFUSAL WAS
    // RENDERING AS NOTHING.** This read `error as ServerErrorEnvelope`. What is
    // thrown is an `ApiError`, whose fields are `messageKey`/`fieldErrors`;
    // `envelopeErrors` reads `message_key`/`field_errors`, so it translated
    // `undefined` and the `role="alert"` paragraph came out EMPTY. `tsc` is
    // happy — the cast asserts the shape — and a refusal that renders as
    // nothing is indistinguishable from a form that simply did nothing (B14
    // rule 33's own warning about silence, and hard-won law 2's shape).
    // `formErrorEnvelope` is the conversion `api/client.ts` already exports for
    // exactly this, and it maps the FIELD errors too, so a refused field is
    // marked instead of the whole form shrugging.
    return { ok: false, error: toEnvelope(error) };
  }
}

/**
 * **CUSTOMER — the account's primary contact, and the group the Product Owner
 * could not edit.**
 *
 * PO 2026-09-13, driving the live screen: *"I cannot edit Customer details"*.
 * The refusal it replaces said the endpoint was on its way under `BR-CUS-1054`;
 * that CR landed `PATCH /customers/{id}`, which writes a DIFFERENT TABLE — the
 * `customers` row, on the customer's own screen. This group renders
 * `account_contacts`, and no route in the product wrote one.
 * `PATCH /accounts/{id}/contact` is the door that was missing.
 *
 * ⚠ **FOUR FIELDS AND NOT FIVE — `Government ID` IS SHOWN AND NOT OFFERED.**
 * The server stores the LAST FOUR only (`BR-CUS-045`), so there is no fuller
 * value for a form to round-trip: a field pre-filled with `1234` that saves
 * `1234` teaches a clerk the product holds the whole number. A fact at rule
 * 33's cap says where it can be changed instead.
 */
/**
 * **CO-APPLICANT — the account's second person (T4, `DEF-CUS-6391`).**
 *
 * PO, verbatim: *"a) Store a second person on the account (name, email,
 * phone), shown on the account page"*. Three fields, one outcome, back to the
 * page it was opened from — the estimate precedent for a dialog. An empty name
 * removes the person.
 */
function EditCoApplicantDialog(props: {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { detail, t } = props;
  const current = (detail.contacts ?? []).find((row) => !row.is_primary) ?? null;
  const [values, setValues] = useState({
    full_name: current?.full_name ?? "",
    email: current?.email ?? "",
    phone: current?.phone ?? "",
    dob: current?.dob ?? "",
  });
  const changed: Record<string, unknown> = {};
  if (values.full_name !== (current?.full_name ?? "")) changed.full_name = values.full_name;
  if (values.email !== (current?.email ?? "")) changed.email = values.email;
  if (values.phone !== (current?.phone ?? "")) changed.phone = values.phone;
  // ⊕ `DEF-CUS-10253` — the shared card's date of birth.
  if (values.dob !== (current?.dob ?? "")) changed.dob = values.dob === "" ? null : values.dob;
  // Clearing the name REMOVES the person, so the name is only required while
  // somebody is being kept.
  const removing = values.full_name.trim() === "" && current !== null;
  return (
    <FormModal
      kicker={detail.account_no ?? ""}
      title={t("customers.account.panel.coApplicant")}
      schema={removing ? EMPTY_SCHEMA : personSchema(t, false, "co_applicant_")}
      values={values}
      submitLabel={t("customers.account.edit.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patchThrough(
          updateAccountCoApplicant,
          detail.id,
          changed,
          props.client,
        );
        if (outcome.ok) props.onSaved();
        return outcome;
      }}
    >
      <TextField
        id="co_applicant_full_name"
        label={t("customers.account.field.fullName")}
        value={values.full_name}
        onChange={(value) => setValues({ ...values, full_name: value })}
        help={t("customers.account.coApplicant.clearHint")}
      />
      <FieldGrid columns={3}>
        <TextField
          id="co_applicant_phone"
          label={t("customers.account.field.phone")}
          value={values.phone}
          onChange={(value) => setValues({ ...values, phone: value })}
        />
        <TextField
          id="co_applicant_email"
          label={t("customers.account.field.email")}
          value={values.email}
          onChange={(value) => setValues({ ...values, email: value })}
        />
        <DatePickerField
          id="co_applicant_dob"
          label={t("customers.account.field.dob")}
          dateFormat={props.dateFormat}
          regional
          value={values.dob}
          onChange={(value) => setValues({ ...values, dob: value })}
        />
      </FieldGrid>
    </FormModal>
  );
}

function EditContactDialog(props: {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { detail, t } = props;
  // ⊕ T4 — an account can now hold a SECOND contact (the co-applicant), so
  // "the first row" is no longer "the primary one". The server writes the
  // primary (`update_account_contact` orders by `-is_primary`); the form reads
  // the same row.
  const contact = primaryContact(detail.contacts) ?? undefined;
  const [values, setValues] = useState({
    full_name: contact?.full_name ?? "",
    email: contact?.email ?? "",
    phone: contact?.phone ?? "",
    dob: contact?.dob ?? "",
    contact_by: contact?.contact_by ?? "",
  });

  const changed: Record<string, unknown> = {};
  // ⊕ `DEF-CUS-10253` — *Contact by*, the shared field (image 08).
  if (values.contact_by !== (contact?.contact_by ?? "")) {
    changed.contact_by = values.contact_by === "" ? null : values.contact_by;
  }
  if (values.full_name !== (contact?.full_name ?? "")) changed.full_name = values.full_name;
  if (values.email !== (contact?.email ?? "")) changed.email = values.email;
  if (values.phone !== (contact?.phone ?? "")) changed.phone = values.phone;
  // ⊕ PO 2026-10-22 (`OQ-CUS-12350` closed, `DEF-CWP-10400`) — *"Also use this
  // as the portal sign-in email"*, unticked on every open. Offered only when
  // exactly ONE login holds this account: with two, nothing says whose login
  // the primary contact is (the server refuses it by name the same way).
  const offersSignIn = detail.portal_access?.logins === 1;
  const [moveSignIn, setMoveSignIn] = useState(false);
  if (offersSignIn && moveSignIn) {
    changed.portal_sign_in = true;
    changed.email = values.email;
  }
  if (values.dob !== (contact?.dob ?? "")) changed.dob = values.dob === "" ? null : values.dob;
  // `DEF-CUS-9168` — the utility's OWN contact fields placed Input on Account
  // detail (slot `S21` for `contacts`), edited here beside the four the
  // drawing gives. Only the keys that changed travel; the server merges them
  // into the contact's stored answers. Same shape as the Account setup dialog.
  const [customData, setCustomData] = useState<CustomFieldValues>(() => ({
    ...(contact?.custom_data ?? {}),
  }));
  const customFields = useCustomFieldRegistry({
    entity: "contacts",
    screen: "S21",
    mode: "input",
    client: props.client,
  });
  const customChanged = customDataChanges(contact?.custom_data ?? {}, customData);
  if (Object.keys(customChanged).length > 0) changed.custom_data = customChanged;

  const recapRows = [
    ["full_name", t("customers.account.field.fullName"), values.full_name],
    ["email", t("customers.account.field.email"), values.email],
    ["phone", t("customers.account.field.phone"), values.phone],
    ["dob", t("customers.account.field.dob"), values.dob],
    ["portal_sign_in", t("customers.account.edit.recapSignIn"), values.email],
  ]
    .filter(([key]) => (key as string) in changed)
    .map(([, label, value]) => ({ label: label as string, value: value as string }));
  // Each changed field by its OWN label, never its key (B14 rule 31).
  for (const field of customFields.data ?? []) {
    if (!(field.key in customChanged)) continue;
    recapRows.push({
      label: field.label,
      value: displayValue(field, customData, (iso) => iso, t),
    });
  }

  return (
    <FormModal
      kicker={[detail.account_no, contact?.full_name]
        .filter((part) => part !== null && part !== undefined && part !== "")
        .join(" · ")}
      title={t("customers.account.panel.customer")}
      schema={personSchema(t, true, "contact_")}
      values={values}
      submitLabel={t("customers.account.edit.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patchThrough(
          updateAccountContact,
          detail.id,
          changed,
          props.client,
        );
        if (outcome.ok) props.onSaved();
        return outcome;
      }}
    >
      {/* ⊕ `DEF-CUS-10253` — the shared customer fields in Move-in's order
          and rules (image 08): Full name · Phone · Email · Contact by · Date
          of birth, the date the product's picker. */}
      <FieldGrid columns={2}>
        <TextField
          id="contact_full_name"
          label={t("customers.account.field.fullName")}
          value={values.full_name}
          required
          onChange={(value) => setValues({ ...values, full_name: value })}
        />
        <TextField
          id="contact_phone"
          label={t("customers.account.field.phone")}
          value={values.phone}
          required
          onChange={(value) => setValues({ ...values, phone: value })}
        />
      </FieldGrid>
      <FieldGrid columns={3}>
        <TextField
          id="contact_email"
          label={t("customers.account.field.email")}
          value={values.email}
          onChange={(value) => setValues({ ...values, email: value })}
        />
        <SelectField
          id="contact_contact_by"
          label={t("customers.moveDetail.col.contactBy")}
          value={values.contact_by}
          placeholder={t("customers.serviceRequest.categoryToSet.choose")}
          options={CONTACT_BY.map((code) => ({
            value: code,
            label: t(`customers.moveDetail.contactBy.${code}`),
          }))}
          onChange={(value) => setValues({ ...values, contact_by: value })}
        />
        <DatePickerField
          id="contact_dob"
          label={t("customers.account.field.dob")}
          dateFormat={props.dateFormat}
          regional
          value={values.dob}
          onChange={(value) => setValues({ ...values, dob: value })}
        />
      </FieldGrid>
      {offersSignIn ? (
        <div data-portal-sign-in="">
          <CheckboxField
            id="contact_portal_sign_in"
            label={t("customers.customer.edit.alsoSignIn")}
            checked={moveSignIn}
            onChange={setMoveSignIn}
          />
        </div>
      ) : null}
      {/* A FACT at rule 33's six-word cap, not an explanation of the storage. */}
      <p className="field-help">{t("customers.account.edit.govIdNotHere")}</p>

      {/* `DEF-CUS-9168` — renders NOTHING when the utility placed no contact
          field Input on Account detail, so this dialog is unchanged for them. */}
      <CustomFieldsInput
        entity="contacts"
        screen="S21"
        values={customData}
        onChange={setCustomData}
        client={props.client}
      />

      <div className="mt-5">
        <RecapBox
          title={t("customers.account.edit.recap")}
          data-recap="contact-edit"
          rows={
            recapRows.length === 0
              ? [
                  {
                    label: t("customers.account.edit.recap"),
                    value: t("customers.account.edit.recapNothing"),
                  },
                ]
              : recapRows
          }
          outcome={{
            label: t("customers.account.edit.recapAudit"),
            value: t("customers.account.edit.recapAuditValue"),
            testId: "audit",
          }}
        />
      </div>
    </FormModal>
  );
}

/**
 * **MAILING ADDRESS — where the BILL goes.**
 *
 * Hard rule 8's first named exception: an address lives on `premises` and every
 * other entity walks to it, EXCEPT this one, because for a landlord the bill
 * goes to another building entirely. It had a create path and no correction
 * path, so a customer who moved their post could not be followed.
 *
 * ⚠ **CLEARING `Street` REMOVES THE ROW, AND THE FORM SAYS SO BEFORE IT
 * COMMITS.** No mailing row means *the bill goes to the service address* —
 * which is what the group already draws in those words — so a second
 * `Remove` control would be two ways to state one fact. The consequence is at
 * rule 33's cap for an irreversible act.
 *
 * ⚠ **NO `kind` FIELD.** `kind='service'` is RETIRED (`BR-MET-1161`) and the
 * route writes `mailing` and only `mailing`, so the value cannot arrive here
 * even by accident.
 */
/**
 * ══════════════════════════════════════════════════════════════════════════
 * CHANGE UNIT — `ACC-E07` / `BR-CUS-1047`, the form behind the Overview's
 * `✎Change unit`
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ **A CORRECTION, NOT A MOVE, AND THAT SENTENCE IS ZERO WORDS ON SCREEN.**
 * `BR-CUS-017` makes an account's unit create-only because **a move-in takes
 * the outgoing account's unit**: the bills, the meters and the reads belong to
 * the unit and must not follow a person. A customer who has actually moved
 * still leaves by move-out and arrives by move-in. This door serves a RECORD
 * that named the wrong unit — and the three reasons it offers are the only
 * three ways that happens, so the FORM says which act this is by what it asks,
 * rather than by a paragraph explaining the data model. B14 rule 33: rationale
 * is zero words on screen, and it lives here.
 *
 * **THE FORM IS TWO FIELDS BECAUSE THE DOOR TAKES TWO.** `CORRECTION_FIELDS` is
 * `{unit_id, reason_code}` and everything else is refused BY NAME —
 * `effective_on` (the server owns the date; a date a clerk may type is a date a
 * clerk may backdate), `reason` as free text, and `approved_by` (the approver
 * is the signed-in supervisor, never a name in the body). So no date control
 * and no approver control is drawn: a field whose value the server refuses is a
 * field that teaches a clerk a lie.
 *
 * ⚠ **WHAT `ACC-E07` DRAWS AND THIS DOES NOT, STATED RATHER THAN QUIETLY
 * DROPPED (`DEF-CUS-5163`).** The blueprint's frame has six sections: the two
 * units side by side with thirteen facts each, a `What changes` table costing
 * the plan move, the issued-bill consequence, `Note to the file`, a
 * `Tell the customer` tick, and a review step. **Two of those have no column at
 * all** — the endpoint stores no note and queues no message — so drawing them
 * would promise storage that does not exist (hard-won law 1). The rest is
 * layout over facts this dialog does not hold, and it is a wave with its own
 * drawing rather than a guess made here. What IS carried across is the part
 * that changes a decision: the consequence, and the recap of what will move.
 *
 * ⚠ **THE UNIT LIST IS THE ONE THE PRODUCT ALREADY USES** — `getUnits` filtered
 * to `occupancy: vacant`, which is `BR-CUS-020` (*"unit pickers offer only
 * vacant or reserved units"*) and is exactly what `NewAccountWizard` asks for.
 * It is MOUNTED, not re-derived. A picker that hides a row is a convenience and
 * never the enforcement: `services._eligible_unit` refuses a forged submit, and
 * the server refuses the unit this account is already on and one another
 * account occupies.
 */
function CorrectUnitDialog(props: {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { detail, t } = props;
  const [values, setValues] = useState({ unit_id: "", reason_code: "" });
  const unitsQuery = useQuery({
    queryKey: ["units", "unit-correction-picker"],
    queryFn: () =>
      props.client === undefined
        ? getUnits({ filters: { occupancy: "vacant" }, per: 500 })
        : getUnits({ filters: { occupancy: "vacant" }, per: 500 }, props.client),
    retry: false,
  });
  // ⚠ **THE UNIT THIS ACCOUNT IS ON CANNOT BE THE ANSWER** — the server answers
  // 409 for it, and offering it is offering a refusal. It is filtered here as
  // well as there because a picker should not present a choice that cannot be
  // made (`BR-SHL-025`'s spirit), never INSTEAD of there.
  // ⚠ **THE LABELS COME FROM `vacantUnitOptions`, THE HELPER `NewAccountWizard`
  // ALREADY OWNS** — MOUNTED, never re-derived (law 12: a list typed out twice
  // is two lists). It composes `<address> · <unit no>` and carries **no database
  // id in the label** (B14 rule 31): the id is what travels, the address and the
  // unit number are what a clerk was told on the phone.
  const options = vacantUnitOptions(
    (unitsQuery.data?.results ?? []).filter((row) => row.id !== detail.unit_id),
  );
  const chosen = options.find((option) => option.value === values.unit_id) ?? null;

  return (
    <FormModal
      kicker={[detail.account_no, detail.contacts[0]?.full_name]
        .filter((part) => part !== null && part !== undefined && part !== "")
        .join(" · ")}
      title={t("customers.account.edit.group.unit")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={t("customers.account.edit.unit.commit")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patchThrough(
          (accountId, changes, client) =>
            correctAccountUnit(
              accountId,
              changes as { unit_id: string; reason_code: string },
              client,
            ),
          detail.id,
          { ...values },
          props.client,
        );
        if (outcome.ok) props.onSaved();
        return outcome;
      }}
    >
      {/* ⚠ **B14 rule 11 — A CONSEQUENCE BEFORE AN IRREVERSIBLE COMMIT.** Two
          facts, and each is one a clerk would act on: the date is the server's
          and cannot be moved, and the bills already sent do not change. Rule 33
          caps a consequence at six words a sentence and two sentences, and
          never below clarity. */}
      <ConsequenceBox
        tone="move"
        tag={t("customers.account.edit.unit.consequenceTag")}
        title={t("customers.account.edit.unit.consequenceTitle")}
        body={t("customers.account.edit.unit.consequenceBody")}
        data-consequence="unit-correction"
      />
      {/* `BR-SHL-033` — a long list is SEARCHABLE, never a bare scroll list.
          `disabled` with its reason while the list has not answered, so a
          picker whose read failed stays a picker (`DEF-MET-4977`) instead of
          turning into a box that takes a uuid. */}
      <SearchSelectField
        id="unit_correction_unit"
        label={t("customers.account.field.unit")}
        required
        value={values.unit_id}
        options={options}
        disabled={unitsQuery.isError}
        help={unitsQuery.isError ? t("customers.account.edit.unit.noUnits") : undefined}
        placeholder={t("customers.account.edit.unit.unitPlaceholder")}
        onChange={(value) => setValues({ ...values, unit_id: value })}
      />
      {/* THE FIXED LIST, and it is fixed in the database with a CHECK
          constraint. The three are the three doors that write
          `accounts.unit_id` — created, imported, moved in — which is why they
          are the three ways a record comes to name the wrong unit. */}
      <SelectField
        id="unit_correction_reason"
        label={t("customers.account.edit.unit.reason")}
        required
        value={values.reason_code}
        options={[
          { value: "", label: t("customers.account.edit.unit.reasonPlaceholder") },
          ...ACCOUNT_UNIT_CORRECTION_REASONS.map((code) => ({
            value: code,
            label: t(`customers.account.edit.unit.reason.${code}`),
          })),
        ]}
        onChange={(value) => setValues({ ...values, reason_code: value })}
      />

      <div className="mt-5">
        <RecapBox
          title={t("customers.account.edit.recap")}
          data-recap="unit-correction"
          rows={[
            {
              label: t("customers.account.edit.unit.from"),
              value: detail.unit_label ?? "—",
            },
            {
              label: t("customers.account.edit.unit.to"),
              value: chosen === null ? t("customers.account.edit.recapNothing") : chosen.label,
            },
            {
              // The plan follows the UNIT (`BR-MET-044` / PO 2026-08-11), so a
              // correction re-prices the account. It is stated rather than
              // computed: this dialog holds no rate card and a figure it cannot
              // stand behind is worse than the fact.
              label: t("customers.account.field.unitPlan"),
              value: t("customers.account.edit.unit.planFollows"),
            },
          ]}
          outcome={{
            label: t("customers.account.edit.recapAudit"),
            value: t("customers.account.edit.unit.recapAuditValue"),
            testId: "audit",
          }}
        />
      </div>
    </FormModal>
  );
}

function EditMailingAddressDialog(props: {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { detail, t } = props;
  const row = detail.addresses.find((address) => address.kind === "mailing");
  // ⊕ `DEF-CUS-10253` — Apt / Unit joins, and the state is chosen from a
  // list (image 08): the kit's `UsAddressFields`, the one US address block.
  const [values, setValues] = useState({
    line1: row?.line1 ?? "",
    line2: row?.line2 ?? "",
    city: row?.city ?? "",
    state: row?.state ?? "",
    postal_code: row?.postal_code ?? "",
  });
  const clearing = values.line1.trim() === "";
  // `DEF-CUS-9169` — the utility's OWN mailing-address fields placed Input on
  // Account detail (slot `S21` for `addresses`). Changed keys only; the server
  // merges them into the row's stored answers. Not drawn while the street is
  // being cleared: the row is about to go, and its answers with it.
  const [customData, setCustomData] = useState<CustomFieldValues>(() => ({
    ...(row?.custom_data ?? {}),
  }));
  const customChanged = customDataChanges(row?.custom_data ?? {}, customData);

  return (
    <FormModal
      kicker={[detail.account_no, detail.contacts[0]?.full_name]
        .filter((part) => part !== null && part !== undefined && part !== "")
        .join(" · ")}
      title={t("customers.account.field.mailingAddress")}
      schema={mailingSchema(t)}
      values={values}
      submitLabel={t("customers.account.edit.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patchThrough(
          updateAccountMailingAddress,
          detail.id,
          clearing || Object.keys(customChanged).length === 0
            ? { ...values }
            : { ...values, custom_data: customChanged },
          props.client,
        );
        if (outcome.ok) props.onSaved();
        return outcome;
      }}
    >
      <UsAddressFields
        idPrefix="mailing"
        value={values}
        onChange={(next) => setValues({ ...values, ...next })}
        required
      />
      {clearing ? null : (
        <CustomFieldsInput
          entity="addresses"
          screen="S21"
          values={customData}
          onChange={setCustomData}
          client={props.client}
        />
      )}
      {clearing && row !== undefined && (
        <p className="field-help" data-mailing-clearing="">
          {t("customers.account.edit.mailingCleared")}
        </p>
      )}

      <div className="mt-5">
        <RecapBox
          title={t("customers.account.edit.recap")}
          data-recap="mailing-edit"
          rows={[
            {
              label: t("customers.account.field.mailingAddress"),
              value: clearing
                ? t("customers.account.mailingSameAsService")
                : [values.line1, values.line2, values.city, values.state, values.postal_code]
                    .filter((part) => part !== "")
                    .join(", "),
            },
          ]}
          outcome={{
            label: t("customers.account.edit.recapAudit"),
            value: t("customers.account.edit.recapAuditValue"),
            testId: "audit",
          }}
        />
      </div>
    </FormModal>
  );
}

/**
 * `R5`'s *NOT EDITABLE HERE* block — as LABELS.
 *
 * The drawing gives each entry a reason: *"Unit — an account never moves
 * between units; a new occupant is a move-in"*, *"Category — create-only on the
 * server"*, *"Status — closing an account is the move-out flow, not an edit"*,
 * *"Returned payments and bad address — written by the returned-mail workflow,
 * which is not built"*. **Every one of those is rationale, and B14 rule 33 puts
 * rationale at ZERO WORDS ON SCREEN.** What survives is the absence itself,
 * which is content the drawing decides — so the five names stay, each within
 * the three-word label cap, and the reasons are here where the rule says to put
 * them. `unit` is `BR-CUS-017` narrowed by `BR-CUS-1047`; `category` is
 * create-only; `status` is `BR-CUS-030`; the last two are `BR-PAY-013/018`.
 */
function NotEditableHere(props: { t: Translator }) {
  const keys = ["unit", "category", "status", "returned", "badAddress"] as const;
  return (
    <div className="mt-5 border-t border-t-divider pt-3">
      <p className="m-0 mb-2 text-sm font-semibold">{props.t("customers.account.edit.notHere")}</p>
      <ul className="m-0 list-disc pl-5 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        {keys.map((key) => (
          <li key={key}>{props.t(`customers.account.edit.notHere.${key}`)}</li>
        ))}
      </ul>
    </div>
  );
}
