// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18) — task 3 of the PO's customer-form plan: the
//           shared **Who** and **Identity** panels, lifted out of Move-in's
//           Customer step (`moveInWizard/StepCustomer.tsx`) so Move-in, the
//           staff service request, New connect, Portal apply and Transfer draw
//           ONE customer form (B14 rule 43).
// Drawing:  `04-docs/05-modules/03-customers/wireframes/customer-forms-2026-10-18/`
//           images 01 (Move-in, the reference), 03 (service request — no
//           *Search customer ID*), 06 (New connect) — read as IMAGES (rule 42).
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"* and its *Same day* paragraphs: Move-in's
//           required-field rules everywhere (phone required for a person, email
//           optional, at least one ID unless an existing customer is linked);
//           every date is the kit's date picker; phone and email format checked.
// Rules:    BR-CUS-1022/1024 (the kind decides the identifier) · BR-CUS-045
//           (government id: last four) · B14 rules 21, 31, 33, 37, 41–44
// Tests:    customerForm/customerForm.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE COMPONENT, PROPS FOR WHAT DIFFERS — NEVER A COPY PER SCREEN.** The
// panel title (*Who is moving in* / *Who is applying* / *Who will own the
// account* / *Who is buying*), whether the category pair is asked
// (`showCategory` — the portal asks none, staff set it before approving), and
// whether the identity panel carries *Search customer ID* (the host passes the
// button as `trailing`, or nothing — the service request has none, PO
// 2026-10-18 *"in new request we dont need Search customer ID"*).
//
// ⚠ **THE VALUES ARE THE MOVE-IN'S `CustomerForm` PLUS `CustomerWhoExtras`.**
// A host whose own form is shaped differently (the service request's
// `applicant_kind`/`drivers_licence`) maps to and from these at its edge, so
// this file never learns a second vocabulary for one person.
import type { ReactNode } from "react";

import type { ApiClient } from "@/api/client";
import type { RegionalDateFormat } from "@/components/DateCell";
import { nowInZone } from "@/components/DateCell";
import {
  DatePickerField,
  SegmentedField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { US_STATE_OPTIONS } from "@/components/usStates";
import type { Translator } from "@/features/tenancy/settingsShared";

import { CONTACT_BY } from "../CoOwnerCards";
import { CustomerTypeFields } from "../CustomerFields";
import { CUSTOMER_KIND_COMPANY, CUSTOMER_KIND_PERSON } from "../NewAccountWizard";
import type { CustomerForm } from "../NewAccountWizard";

/**
 * Move-in's *Business type* vocabulary (decision log 2026-10-05, P2.27).
 * `customers.business_type` is free text and no rule names its values; *Sole
 * proprietor* is NOT offered — `OQ-1242` is open.
 */
export const BUSINESS_TYPES = [
  "llc",
  "corporation",
  "partnership",
  "non_profit",
  "government",
  "other",
] as const;

/** What the Who panel asks beside `CustomerForm`. */
export interface CustomerWhoExtras {
  /** A person's *Contact by* — `models.CONTACT_BY`. */
  contact_by: string;
  trading_as: string;
  business_type: string;
  registered_in: string;
}

export function emptyCustomerWhoExtras(): CustomerWhoExtras {
  return { contact_by: "", trading_as: "", business_type: "", registered_in: "" };
}

// ── The format checks (task 10) ──────────────────────────────────────────────

const EMAIL_SHAPE = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;

/** `customers.form.emailInvalid`, or null — blank is no error (email is
 *  optional everywhere, PO 2026-10-18). */
export function emailFormatProblem(value: string): string | null {
  const typed = value.trim();
  if (typed === "") return null;
  return EMAIL_SHAPE.test(typed) ? null : "customers.form.emailInvalid";
}

/**
 * `customers.form.phoneInvalid`, or null. A North American number: ten digits,
 * or eleven starting with `1`, once the punctuation a person types — spaces,
 * dots, dashes, brackets, a leading `+` — is set aside. Anything else (a
 * letter, too few digits) is refused. Blank is no error here; whether a phone
 * is REQUIRED is the host's rule (a person's, on Move-in's rules).
 */
export function phoneFormatProblem(value: string): string | null {
  const typed = value.trim();
  if (typed === "") return null;
  if (!/^[+\d\s().-]+$/.test(typed)) return "customers.form.phoneInvalid";
  const digits = typed.replace(/\D/g, "");
  const ok = digits.length === 10 || (digits.length === 11 && digits.startsWith("1"));
  return ok ? null : "customers.form.phoneInvalid";
}

/** The first format problem on the form, for a host's Continue. */
export function customerFormatProblem(customer: Pick<CustomerForm, "email" | "phone">): string | null {
  return emailFormatProblem(customer.email) ?? phoneFormatProblem(customer.phone);
}

function errorFor(problem: string | null, show: boolean, t: Translator): string | undefined {
  return show && problem !== null ? t(problem) : undefined;
}

/**
 * **WHO** — Person/Company on top, the category pair, then the person's name,
 * email, phone, date of birth and *Contact by* (image 01), or a company's
 * legal name, trading name, business type, Tax ID and state (Move-in image 40).
 */
export function CustomerWhoPanel(props: {
  /** *Who is moving in* · *Who is applying* · *Who will own the account* ·
   *  *Who is buying* — the host's own words. */
  title: string;
  customer: CustomerForm;
  onCustomer: (next: CustomerForm) => void;
  extras: CustomerWhoExtras;
  onExtras: (patch: Partial<CustomerWhoExtras>) => void;
  /** The category and sub-category pair. Default on; the portal passes false
   *  (PO 2026-10-18: staff set the category before approving). */
  showCategory?: boolean;
  /** An empty first option on *Category* — for a host whose form opens with
   *  no category (the service request), so *unanswered* never reads as the
   *  first category (`DEF-CUS-5082`). Move-in opens on Residential. */
  categoryPlaceholder?: string;
  /** A company's trading name, business type and state. Default on; a host
   *  with nowhere to keep them (the service request) passes false. */
  showCompanyFacts?: boolean;
  /** A company's email and phone in this panel. Default off — Move-in asks
   *  them of the CONTACT PERSON; the service request keeps them here. */
  showCompanyContact?: boolean;
  /** Drawn under the company's fields: Move-in's *Search customer ID* and its
   *  answer (a company has no Identity panel — its Tax ID is here). */
  companyTrailing?: ReactNode;
  /** Above the fields — Move-in's *from request SR-…* note. */
  note?: ReactNode;
  /** Below the fields — a host's own extra control (the request's channel). */
  footer?: ReactNode;
  /** Show the refusals (format, required) — after Continue was pressed. */
  showErrors?: boolean;
  /** Lane CF-1 (additive) — a host's own date-of-birth refusal, drawn on the
   *  field as typed (New connect's under-18 / future rule, `DEF-CUS-9193`). */
  dobError?: string;
  t: Translator;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** The host's transport for the category reads (a test seam). */
  client?: ApiClient;
}) {
  const { t, customer, extras } = props;
  const set = (patch: Partial<CustomerForm>) => props.onCustomer({ ...customer, ...patch });
  const company = customer.customer_kind === CUSTOMER_KIND_COMPANY;
  const today = nowInZone(props.timeZone).slice(0, 10);
  const show = props.showErrors === true;
  const emailError = errorFor(emailFormatProblem(customer.email), show, t);
  const phoneError = errorFor(phoneFormatProblem(customer.phone), show, t);

  const email = (
    <TextField
      id="email"
      label={t("customers.account.field.email")}
      autoComplete="email"
      value={customer.email}
      error={emailError}
      onChange={(value) => set({ email: value })}
    />
  );
  const phone = (required: boolean) => (
    <TextField
      id="phone"
      label={t("customers.account.field.phone")}
      required={required}
      autoComplete="tel"
      help={t("customers.moveIn.customer.phoneHelp")}
      value={customer.phone}
      error={phoneError}
      onChange={(value) => set({ phone: value })}
    />
  );

  return (
    <Panel as="section" title={props.title} data-customer-panel="who">
      {props.note}
      <div className="flex flex-col gap-5">
        <SegmentedField
          id="customer_kind"
          label={t("customers.newAccount.field.customerKind")}
          labelHidden
          value={customer.customer_kind}
          options={[
            { value: CUSTOMER_KIND_PERSON, label: t("customers.customer.kind.person") },
            { value: CUSTOMER_KIND_COMPANY, label: t("customers.customer.kind.company") },
          ]}
          onChange={(value) => set({ customer_kind: value })}
        />
        {props.showCategory === false ? null : (
          <div className="grid grid-cols-2 gap-x-6 gap-y-5" data-customer-category="">
            <CustomerTypeFields
              values={customer}
              onChange={props.onCustomer}
              t={t}
              subtypeHelp={t("customers.moveIn.optional")}
              typePlaceholder={props.categoryPlaceholder}
              client={props.client}
            />
          </div>
        )}
        {company ? (
          <>
            <div className="grid grid-cols-2 gap-x-6 gap-y-5">
              <TextField
                id="full_name"
                label={t("customers.moveIn.customer.legalName")}
                required
                value={customer.full_name}
                onChange={(value) => set({ full_name: value })}
              />
              {props.showCompanyFacts === false ? null : (
                <TextField
                  id="trading_as"
                  label={t("customers.moveIn.customer.tradingAs")}
                  value={extras.trading_as}
                  onChange={(value) => props.onExtras({ trading_as: value })}
                />
              )}
              {props.showCompanyFacts === false ? null : (
                <SelectField
                  id="business_type"
                  label={t("customers.moveIn.customer.businessType")}
                  required
                  placeholder={t("customers.moveIn.customer.choose")}
                  value={extras.business_type}
                  options={BUSINESS_TYPES.map((code) => ({
                    value: code,
                    label: t(`customers.moveIn.customer.businessTypeOption.${code}`),
                  }))}
                  onChange={(value) => props.onExtras({ business_type: value })}
                />
              )}
              <TextField
                id="tax_id"
                label={t("customers.moveIn.customer.ein")}
                required
                autoComplete="off"
                value={customer.tax_id}
                onChange={(value) => set({ tax_id: value })}
              />
              {props.showCompanyFacts === false ? null : (
                <SelectField
                  id="registered_in"
                  label={t("customers.moveIn.customer.registeredIn")}
                  placeholder={t("customers.moveIn.customer.choose")}
                  value={extras.registered_in}
                  options={US_STATE_OPTIONS}
                  onChange={(value) => props.onExtras({ registered_in: value })}
                />
              )}
              {props.showCompanyContact === true ? email : null}
              {props.showCompanyContact === true ? phone(false) : null}
            </div>
            {props.companyTrailing}
          </>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-x-6 gap-y-5">
              <TextField
                id="full_name"
                label={t("customers.account.field.fullName")}
                required
                autoComplete="name"
                value={customer.full_name}
                onChange={(value) => set({ full_name: value })}
              />
              {email}
            </div>
            <div className="grid grid-cols-3 gap-x-6 gap-y-5">
              {phone(true)}
              <DatePickerField
                id="dob"
                label={t("customers.account.field.dob")}
                regional
                value={customer.dob}
                max={today}
                dateFormat={props.dateFormat}
                error={props.dobError}
                onChange={(value) => set({ dob: value })}
              />
              <SelectField
                id="contact_by"
                label={t("customers.moveDetail.col.contactBy")}
                placeholder={t("customers.moveIn.customer.choose")}
                value={extras.contact_by}
                options={CONTACT_BY.map((code) => ({
                  value: code,
                  label: t(`customers.moveDetail.contactBy.${code}`),
                }))}
                onChange={(value) => props.onExtras({ contact_by: value })}
              />
            </div>
          </>
        )}
        {props.footer}
      </div>
    </Panel>
  );
}

/**
 * **IDENTITY** — a person's SSN, driver's licence and government ID, three
 * across (image 01), *Staff see the last four only.* under the SSN and the
 * at-least-one-ID rule under the row. A company has no Identity panel: its Tax
 * ID is asked in Who, so a host draws this for a person only.
 *
 * `trailing` is *Search customer ID* where the host has a search (Move-in, New
 * connect) and nothing where it has none (the service request); `children` is
 * what sits under the fields — the search's answer, a fact from the request.
 */
export function CustomerIdentityPanel(props: {
  customer: CustomerForm;
  onCustomer: (next: CustomerForm) => void;
  trailing?: ReactNode;
  children?: ReactNode;
  /** The mask of a number already on file (a request reopened for
   *  correction), shown as a PLACEHOLDER, never as a value (`DEF-CUS-6427`). */
  ssnPlaceholder?: string;
  licencePlaceholder?: string;
  /** Lane CF-1 (additive) — the licence masked as typed, with Show/Hide, as
   *  New connect has had it since `DEF-CUS-9194` (PO ruling Q4). */
  licenceMasked?: boolean;
  t: Translator;
}) {
  const { t, customer } = props;
  const licenceMasked = props.licenceMasked === true;
  const set = (patch: Partial<CustomerForm>) => props.onCustomer({ ...customer, ...patch });
  return (
    <Panel
      as="section"
      title={t("customers.moveIn.customer.identityTitle")}
      trailing={props.trailing}
      data-customer-panel="identity"
    >
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-x-6 gap-y-5">
          <TextField
            id="ssn"
            label={t("customers.newAccount.field.ssn")}
            autoComplete="off"
            masked
            revealable
            help={t("customers.moveIn.customer.lastFourHelp")}
            placeholder={props.ssnPlaceholder}
            value={customer.ssn}
            onChange={(value) => set({ ssn: value })}
          />
          <TextField
            id="driving_licence"
            label={t("customers.newAccount.field.drivingLicence")}
            autoComplete="off"
            masked={licenceMasked}
            revealable={licenceMasked}
            placeholder={props.licencePlaceholder}
            value={customer.driving_licence}
            onChange={(value) => set({ driving_licence: value })}
          />
          <TextField
            id="gov_id_last4"
            label={t("customers.account.field.govId")}
            numeric
            autoComplete="off"
            value={customer.gov_id_last4}
            onChange={(value) => set({ gov_id_last4: value })}
          />
        </div>
        <p className="m-0 text-sm text-neutral-700" data-identity-rule="">
          {t("customers.form.oneIdRule")}
        </p>
        {props.children}
      </div>
    </Panel>
  );
}
