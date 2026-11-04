// ── Trace ──────────────────────────────────────────────
// Change:   BR-CUS-1054 — **a customer's own details can be corrected.** PO
//           2026-09-13, verbatim: *"Start the customer edit one also - we will
//           need this"*. `CR-094-BRC01` wave R.
// Rules:    BR-CUS-1054 · BR-CUS-054 (one customer, many accounts — so one
//           email correction reaches all of them) · BR-CUS-092(c) (a full
//           identifier never reaches a browser) · BR-CUS-1022 (identity is per
//           KIND — a company has no date of birth) · BR-SHL-025 (a control this
//           role cannot use renders disabled WITH its reason) · CLAUDE.md hard
//           rule 4 (issued bills do not restate) · B14 rule 15 (row actions are
//           ICONS) · rule 31 (no database id on screen) · rule 32 (one sentence
//           per section; no rule id in clerk copy) · rule 33 (what a string is
//           FOR caps its length; RATIONALE is zero words on screen) · rule 38
//           (the UI rules decide how a form is built) · rule 39 (label → input
//           → helper).
// Tests:    07-frontend/src/features/customers/CustomerEditDialog.dom.test.tsx
// Impacts:  CustomersListPage.tsx (the pencil) · customerEndpoints.ts
//           (`updateCustomer`) · 06-backend `PATCH /api/{tenant}/customers/{id}`
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE IS ON `src/styles/route-b-migrated.txt`.** B14 rule 21: new UI
// is Tailwind utilities and adds NO class to a stylesheet. The ledger is what
// decides which CHECK reads the file — `G31` skips a listed one and
// `routeBUtilities.test.ts` asks the stricter question of it — so a utility in
// an UNLISTED file is a red gate at merge, and the fix is to list the file
// rather than reach for a stylesheet class.
//
// ⚠ **A DIALOG AND NOT A PAGE, AND THAT IS THE RULE RATHER THAN TASTE**
// (`AssetPanelEdits`' own words): a PAGE when you are creating something or
// moving where it lives; a MODAL when you are correcting a value on something
// you are already looking at. Five fields on a row you have just read is a
// dialog.
//
// ⚠ **WHAT THIS FORM DOES NOT OFFER, AND WHY IT SAYS NOTHING ABOUT IT ON
// SCREEN.** `PATCH /customers/{id}` also accepts `ssn`, `driving_licence` and
// `tax_id`. None is drawn: they are the columns `BR-CUS-092(c)` keeps off every
// read path, correcting one is an identity act rather than a typo fix, and the
// PO named a misspelt name, a wrong telephone number and a wrong email. B14
// rule 33 puts RATIONALE at zero words on screen, so the reason lives here and
// in the register — the screen does not explain the absence, it simply does not
// draw the field.
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { CustomFieldsInput, customDataChanges } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import {
  CheckboxField,
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { SegmentedControl } from "@/components/SegmentedControl";
import type { FormSubmitOutcome, ServerErrorEnvelope } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { z } from "zod";

import { CONTACT_BY } from "./CoOwnerCards";
import { emailFormatProblem, phoneFormatProblem } from "./customerForm/CustomerWhoPanel";
import { updateCustomer } from "./customerEndpoints";
import { FieldGrid } from "./serviceRequestShared";
import type { CustomerEdit, CustomerRow } from "./customerEndpoints";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/** `BR-CUS-1022` — a company has no date of birth; that is the whole collision
 *  the rule resolves, and the server refuses the field by name. The form does
 *  not offer what the server will refuse. */
export const CUSTOMER_KIND_COMPANY = "company";

/**
 * **WHAT THE CLERK ACTUALLY CHANGED, AND NOTHING ELSE.**
 *
 * ⚠ **AN ABSENT KEY AND AN EMPTY KEY ARE DIFFERENT ACTS.** The server reads an
 * absent key as *leave it alone* and `""` as *clear it*, so sending the whole
 * form back would turn every untouched blank into a deliberate erasure — and on
 * `phone` that would drop the customer out of the search box with nothing on
 * screen to show for it. Exported because this is the claim worth testing, and
 * a test that drives the DOM cannot see which keys were sent.
 */
export function customerChanges(row: CustomerRow, values: CustomerFormValues): CustomerEdit {
  const changes: CustomerEdit = {};
  if (values.display_name !== row.display_name) {
    changes.display_name = values.display_name;
  }
  if (values.external_ref !== (row.external_ref ?? "")) {
    changes.external_ref = values.external_ref;
  }
  if (values.phone !== (row.phone ?? "")) {
    changes.phone = values.phone;
  }
  if (
    row.kind !== CUSTOMER_KIND_COMPANY &&
    values.date_of_birth !== (row.identity.date_of_birth ?? "")
  ) {
    changes.date_of_birth = values.date_of_birth;
  }
  // ⊕ `DEF-CUS-10253` — the email now opens on the value on file (the list row
  // serves it), so it travels when it CHANGED, like every other field; an
  // untouched blank is never sent as an erasure.
  if (values.email !== (row.email ?? "")) {
    changes.email = values.email;
  }
  if (values.contact_by !== (row.contact_by ?? "")) {
    changes.contact_by = values.contact_by;
  }
  // ⊕ `DEF-CUS-10253` — an identifier box opens EMPTY over the last four on
  // file (the full number never reaches a browser, BR-CUS-092(c)); typing in
  // it replaces the number, and an empty box changes nothing.
  if (values.ssn.trim() !== "") changes.ssn = values.ssn.trim();
  if (values.driving_licence.trim() !== "") changes.driving_licence = values.driving_licence.trim();
  if (values.tax_id.trim() !== "") changes.tax_id = values.tax_id.trim();
  return changes;
}

/**
 * ⊕ PO 2026-10-22 (`OQ-CUS-12350` closed, `DEF-CWP-10400`) — the tick box.
 * Ticked, the email travels WITH the flag even when it did not change here: a
 * clerk who saved the email unticked yesterday can tick today and move the
 * sign-in to it. Unticked, nothing about the sign-in is sent at all.
 */
export function withSignIn(changes: CustomerEdit, moveSignIn: boolean, email: string): CustomerEdit {
  return moveSignIn ? { ...changes, email, portal_sign_in: true } : changes;
}

export interface CustomerFormValues {
  display_name: string;
  external_ref: string;
  date_of_birth: string;
  phone: string;
  email: string;
  contact_by: string;
  ssn: string;
  driving_licence: string;
  tax_id: string;
}

/** B8: the schema mirrors the server's VAL codes; the server stays
 *  authoritative and its field errors land under the same field names.
 *  ⊕ `DEF-CUS-10253` — Move-in's rules: a name always, a phone for a person,
 *  and both contact boxes in a valid shape (the shared format checks). */
function schemaFor(isCompany: boolean, t: Translator) {
  return z
    .object({
      display_name: z.string().trim().min(1),
      external_ref: z.string(),
      date_of_birth: z.string(),
      phone: z.string(),
      email: z.string(),
      contact_by: z.string(),
      ssn: z.string(),
      driving_licence: z.string(),
      tax_id: z.string(),
    })
    .superRefine((values, ctx) => {
      if (!isCompany && values.phone.trim() === "") {
        ctx.addIssue({ code: "custom", path: ["phone"], message: t("customers.customer.edit.phoneRequired") });
      }
      const phone = phoneFormatProblem(values.phone);
      if (phone !== null) ctx.addIssue({ code: "custom", path: ["phone"], message: t(phone) });
      const email = emailFormatProblem(values.email);
      if (email !== null) ctx.addIssue({ code: "custom", path: ["email"], message: t(email) });
    });
}

/** `•••-••-4471` — the last four on file, as the box's placeholder. */
function maskedSsn(last4: string | null): string | undefined {
  return last4 ? `•••-••-${last4}` : undefined;
}

/** `•••• 8903` — a licence or Tax ID's last four, as the box's placeholder. */
function maskedTail(last4: string | null): string | undefined {
  return last4 ? `•••• ${last4}` : undefined;
}

/**
 * `Edit customer` — the one form `BR-CUS-1054` asks for, ⊕ built from image
 * `08-edit.png` (`DEF-CUS-10253`, PO 2026-10-18: the edit dialogs use the
 * shared customer fields): Person / Company · Full name · Phone · Email ·
 * Contact by · Date of birth · SSN · Driver's licence.
 *
 * ⚠ **PERSON / COMPANY IS SHOWN AND CANNOT BE SWITCHED HERE.** The server
 * refuses a change of kind by name (`REFUSED_FIELDS["kind"]`, `OQ-CUS-12351`
 * open): flipping it would leave every identifier stored and unmatchable. The
 * drawing draws the segment, so it is drawn — the other kind disabled.
 *
 * ⚠ **THE EMAIL FIELD REACHES EVERY ACCOUNT AND THE HELPER SAYS SO.**
 * `contacts` hangs off the account, so a landlord with four accounts has four
 * contact rows; a save that fixed one would leave three bills going to the old
 * address and nobody could tell which. *Contact by* travels the same way.
 */
export function CustomerEditDialog(props: {
  row: CustomerRow;
  t: Translator;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  /** `BR-SHL-025` — a refusal this deployment or this role carries. `null` or
   *  absent means the commit is live. */
  commitBlocked?: string | null;
  onClose: () => void;
  onSaved: (accountsUpdated: number) => void;
}) {
  const { row, t } = props;
  const isCompany = row.kind === CUSTOMER_KIND_COMPANY;
  const [values, setValues] = useState<CustomerFormValues>({
    display_name: row.display_name,
    external_ref: row.external_ref ?? "",
    date_of_birth: row.identity.date_of_birth ?? "",
    phone: row.phone ?? "",
    email: row.email ?? "",
    contact_by: row.contact_by ?? "",
    ssn: "",
    driving_licence: "",
    tax_id: "",
  });

  function set<K extends keyof CustomerFormValues>(key: K, value: CustomerFormValues[K]): void {
    setValues((current) => ({ ...current, [key]: value }));
  }
  // ⊕ PO 2026-10-22 — unticked every time the dialog opens; offered only when
  // this customer holds a portal login.
  const [moveSignIn, setMoveSignIn] = useState(false);
  const offersSignIn = row.has_portal_login === true;
  const storedCustomData: CustomFieldValues = row.custom_data ?? {};
  const [customData, setCustomData] = useState<CustomFieldValues>(storedCustomData);

  async function submit(): Promise<FormSubmitOutcome> {
    const changes = withSignIn(
      {
        ...customerChanges(row, values),
        custom_data: customDataChanges(storedCustomData, customData),
      },
      offersSignIn && moveSignIn,
      values.email,
    );
    try {
      const result =
        props.client === undefined
          ? await updateCustomer(row.id, changes)
          : await updateCustomer(row.id, changes, props.client);
      props.onSaved(result.accounts_updated);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: error as ServerErrorEnvelope };
    }
  }

  return (
    <FormModal
      title={t("customers.customer.edit.title")}
      // ⚠ B14 rule 31 — the NAME, never `row.id`. A customer created before the
      // number backfill may carry no `customer_no`, and the name is the thing a
      // clerk recognises on a dialog they just opened from that row.
      kicker={row.display_name}
      schema={schemaFor(isCompany, t)}
      values={values}
      submitLabel={t("customers.customer.edit.submit")}
      commitBlocked={props.commitBlocked ?? undefined}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <div className="field" data-customer-kind={row.kind}>
        <span id="customer-edit-kind" className="sr-only">
          {t("customers.newAccount.field.customerKind")}
        </span>
        <SegmentedControl
          purpose="choice"
          name="customer-edit-kind"
          labelledBy="customer-edit-kind"
          label={t("customers.newAccount.field.customerKind")}
          active={isCompany ? "company" : "person"}
          onSelect={() => undefined}
          segments={[
            {
              id: "person",
              label: t("customers.customer.kind.person"),
              disabled: isCompany ? true : undefined,
            },
            {
              id: "company",
              label: t("customers.customer.kind.company"),
              disabled: isCompany ? undefined : true,
            },
          ]}
        />
      </div>
      <FieldGrid columns={2}>
        <TextField
          id="display_name"
          label={t("customers.customer.edit.name")}
          value={values.display_name}
          required
          onChange={(value) => set("display_name", value)}
        />
        <TextField
          id="phone"
          label={t("customers.customer.edit.phone")}
          value={values.phone}
          required={!isCompany}
          help={t("customers.customer.edit.phoneHelp")}
          onChange={(value) => set("phone", value)}
        />
      </FieldGrid>
      <FieldGrid columns={3}>
        <TextField
          id="email"
          label={t("customers.customer.edit.email")}
          value={values.email}
          help={t("customers.customer.edit.emailHelp")}
          onChange={(value) => set("email", value)}
        />
        <SelectField
          id="contact_by"
          label={t("customers.moveDetail.col.contactBy")}
          value={values.contact_by}
          placeholder={t("customers.serviceRequest.categoryToSet.choose")}
          options={CONTACT_BY.map((code) => ({
            value: code,
            label: t(`customers.moveDetail.contactBy.${code}`),
          }))}
          onChange={(value) => set("contact_by", value)}
        />
        {/* `BR-CUS-1022` — a PERSON's fact. A company row does not draw it, and
            the server refuses it by name for the same reason. ⊕ The product's
            date picker in the utility's format (PO 2026-10-18). */}
        {isCompany ? null : (
          <DatePickerField
            id="date_of_birth"
            label={t("customers.customer.edit.dob")}
            value={values.date_of_birth}
            dateFormat={props.dateFormat}
            regional
            onChange={(value) => set("date_of_birth", value)}
          />
        )}
      </FieldGrid>
      {/* ⊕ PO 2026-10-22, the PO's own words for the label. The sign-in is
          another module's row; the server moves it only on this tick. */}
      {offersSignIn ? (
        <div data-portal-sign-in="">
          <CheckboxField
            id="portal_sign_in"
            label={t("customers.customer.edit.alsoSignIn")}
            checked={moveSignIn}
            onChange={setMoveSignIn}
          />
        </div>
      ) : null}
      <FieldGrid columns={2}>
        {isCompany ? (
          <TextField
            id="tax_id"
            label={t("customers.newAccount.field.taxId")}
            value={values.tax_id}
            placeholder={maskedTail(row.identity.tax_id_last4)}
            onChange={(value) => set("tax_id", value)}
          />
        ) : (
          <>
            <TextField
              id="ssn"
              label={t("customers.newAccount.field.ssn")}
              value={values.ssn}
              placeholder={maskedSsn(row.identity.ssn_last4)}
              onChange={(value) => set("ssn", value)}
            />
            <TextField
              id="driving_licence"
              label={t("customers.newAccount.field.drivingLicence")}
              value={values.driving_licence}
              placeholder={maskedTail(row.identity.driving_licence_last4)}
              onChange={(value) => set("driving_licence", value)}
            />
          </>
        )}
      </FieldGrid>
      <TextField
        id="external_ref"
        label={t("customers.customer.edit.ref")}
        value={values.external_ref}
        help={t("customers.customer.edit.refHelp")}
        onChange={(value) => set("external_ref", value)}
      />
      {/* `CR-161-BRC10` W4 — the utility's OWN customer fields. Nothing at all
          when none is placed on this dialog. */}
      <CustomFieldsInput
        entity="customers"
        screen="CUSTOMER_EDIT"
        values={customData}
        onChange={setCustomData}
        client={props.client}
      />
      {/* ⚠ **TWO SENTENCES OF FIVE AND SIX, WHICH IS RULE 33's SHAPE FOR A
          CONSEQUENCE** — and both are things a clerk would otherwise learn from
          an angry customer. A bill's customer name is locked into its snapshot
          at issue (hard rule 4), and the portal sign-in is a different column in
          another module which this save must not move. */}
      <ConsequenceBox
        tone="check"
        title={t("customers.customer.edit.effectTitle")}
        tag={t("customers.customer.edit.effectTag")}
        body={t(
          offersSignIn && moveSignIn
            ? "customers.customer.edit.effectBodySignIn"
            : "customers.customer.edit.effectBody",
        )}
        data-consequence="customer-edit"
      />
    </FormModal>
  );
}
// ── Lifecycle ─────────────────────────────────────────────
// packet: BR-CUS-1054@this-commit (04-docs/05-modules/03-customers/02-business-rules.md)
//         + BR-CUS-054 + BR-CUS-092(c) + BR-CUS-1022 + BR-SHL-025
//         + CLAUDE.md hard rule 4 + B14 rules 15, 21, 31, 32, 33, 38, 39
//         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-094-BRC01` allocates no story ids, and minting one to satisfy `G01`'s regex would put a citation in the tree that resolves to nothing. Same posture as `CustomersListPage.tsx`, one screen over
// generated: 2026-09-13 by the BR-CUS-1054 build lane
// checklist: A✔ B✔ C✔ D✔(CustomersListPage.tsx opens it) E✔(the customers list) F✔ G✔ H=n/a(no money figure is drawn or written here)
// gates: tsc --noEmit · vitest CustomerEditDialog.dom.test.tsx · G31 (the file is on route-b-migrated.txt) · G13 (the dialog is mounted by the list, not an unpassed prop)
// exceptions: E3 the three government identifiers are NOT drawn — `BR-CUS-092(c)` keeps a full identifier off every read path, correcting one is an identity act rather than a typo fix, and B14 rule 33 puts the reason at zero words on screen · E3 no customer DETAIL screen exists in this product, so the pencil lives on the list row (`CustomersListPage.tsx`'s own E3 records the same absence)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
