// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 12 — the staff service request's step
//           1 IS the shared customer form (customer-forms drawing set, image
//           03 — read as an IMAGE, B14 rule 42): Who is applying · Identity
//           (NO *Search customer ID*) · About the customer · Co-applicants ·
//           Documents · Mailing address · Preferences (no Autopay).
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"* and its *Same day* paragraphs — PO verbatim:
//           *"in new request we dont need Search customer ID - we will anyway do
//           that in move or new conenct - hence it is duplcate of work"*;
//           *"not required in service request"* (no tax, discounts, fees or
//           payment); Preferences on every screen, Autopay only where a payment
//           method can be saved. `DEF-CUS-10223` (the business Tax ID drawn and
//           never sent) and `DEF-CUS-10225` (four customer forms).
// Rules:    BR-CUS-1022 (the kind decides the identifier) · BR-CUS-091 (a
//           staff-raised request may carry no applicant name) · BR-CUS-092
//           (identifiers last-four on every read) · BR-CUS-095 (the document
//           checklist) · hard rule 8 (mailing is where the bill goes) · B14
//           rules 21, 31, 33, 41–44
// Tests:    ServiceRequestCaptureCustomerForm.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE REQUEST KEEPS ITS OWN FORM SHAPE (`CaptureForm`) AND MAPS AT THIS
// EDGE.** It says `applicant_kind: business`, `drivers_licence` and a
// sub-category ID where the move-in says `customer_kind: company`,
// `driving_licence` and a sub-category CODE — four years of drafts, tests and
// a server door speak the request's words. So this component translates each
// way, once, and the shared panels never learn a second vocabulary.
//
// ⚠ **THE CHANNEL STAYS, UNDER THE WHO PANEL'S FIELDS.** Image 03 does not
// draw it; it is kept because BR-CUS-091 makes `staff_collections` the thing
// that lets a staff-raised request carry no applicant name, and a control that
// carries a signed rule is not removed by a drawing's omission. Recorded as a
// difference left in the walk.
import type { ApiClient } from "@/api/client";
import type { CustomFieldValues } from "@/components/CustomFields";
import type { RegionalDateFormat } from "@/components/DateCell";
import { SelectField } from "@/components/FormModal";
import type { Translator } from "@/features/tenancy/settingsShared";

import { CoOwnerCards } from "./CoOwnerCards";
import type { CoOwnerDraft } from "./CoOwnerCards";
import { CustomerCustomFieldsPanel } from "./customerForm/CustomerCustomFieldsPanel";
import { CustomerIdentityPanel, CustomerWhoPanel } from "./customerForm/CustomerWhoPanel";
import type { CustomerWhoExtras } from "./customerForm/CustomerWhoPanel";
import { MailingAddressBlock } from "./customerForm/MailingAddressBlock";
import type { MailingAddressValue } from "./customerForm/MailingAddressBlock";
import { PreferencesPanel } from "./customerForm/PreferencesPanel";
import type { PreferencesValue } from "./customerForm/PreferencesPanel";
import type { AccountSubtypeRow } from "./customersShared";
import { MoveInDocumentsTable } from "./MoveInDocumentsTable";
import type { MoveInDocDraft } from "./MoveInDocumentsTable";
import { CUSTOMER_KIND_COMPANY, CUSTOMER_KIND_PERSON, emptyCustomerForm } from "./NewAccountWizard";
import type { CustomerForm } from "./NewAccountWizard";
import { CAPTURE_CHANNELS } from "./serviceRequestEndpoints";
import type { CaptureForm } from "./ServiceRequestCapturePage";

/** The request's applicant as the shared form's `CustomerForm`. */
export function captureToCustomer(
  form: CaptureForm,
  subtypeRows: readonly AccountSubtypeRow[],
): CustomerForm {
  return {
    ...emptyCustomerForm(),
    customer_kind: form.applicant_kind === "business" ? CUSTOMER_KIND_COMPANY : CUSTOMER_KIND_PERSON,
    account_type: form.account_type_code,
    // B14 rule 31 — the picker works in CODES; the request's door takes the
    // ID (`set_customer_category`), so the two are translated here.
    account_subtype: subtypeRows.find((row) => row.id === form.account_subtype_id)?.code ?? "",
    full_name: form.applicant_name,
    email: form.applicant_email,
    phone: form.applicant_phone,
    dob: form.date_of_birth,
    ssn: form.ssn,
    driving_licence: form.drivers_licence,
    tax_id: form.tax_id,
    gov_id_last4: form.gov_id_last4,
    mailing_same: form.billing_address_same,
    mailing_line1: form.billing_address.line1,
    mailing_line2: form.billing_address.line2,
    mailing_city: form.billing_address.city,
    mailing_state: form.billing_address.state,
    mailing_postal_code: form.billing_address.postal_code,
  };
}

/** What changed in the shared form, as a patch of the request's own form. */
export function customerToCapturePatch(
  next: CustomerForm,
  form: CaptureForm,
  subtypeRows: readonly AccountSubtypeRow[],
): Partial<CaptureForm> {
  return {
    account_type_code: next.account_type,
    account_subtype_id:
      next.account_subtype === ""
        ? ""
        : (subtypeRows.find((row) => row.code === next.account_subtype)?.id ?? form.account_subtype_id),
    applicant_name: next.full_name,
    applicant_email: next.email,
    applicant_phone: next.phone,
    date_of_birth: next.dob,
    ssn: next.ssn,
    drivers_licence: next.driving_licence,
    tax_id: next.tax_id,
    gov_id_last4: next.gov_id_last4,
  };
}

function mailingOf(form: CaptureForm): MailingAddressValue {
  return {
    mailing_same: form.billing_address_same,
    mailing_line1: form.billing_address.line1,
    mailing_line2: form.billing_address.line2,
    mailing_city: form.billing_address.city,
    mailing_state: form.billing_address.state,
    mailing_postal_code: form.billing_address.postal_code,
  };
}

export function CaptureCustomerForm(props: {
  form: CaptureForm;
  update: (patch: Partial<CaptureForm>) => void;
  /** The page's `clearOtherKind` — a kind change blanks the other kind's
   *  identifiers, and only the page knows which those are. */
  onApplicantKindChange: (kind: string) => void;
  subtypeRows: readonly AccountSubtypeRow[];
  /** The customer's own fields placed on Staff New Request (`REQUEST_NEW`). */
  customCustomers: CustomFieldValues;
  onCustomCustomers: (values: CustomFieldValues) => void;
  /** The documents table's rows the clerk added this session. */
  documents: readonly MoveInDocDraft[];
  onDocuments: (rows: MoveInDocDraft[]) => void;
  /** The request's id once saved as a draft (`""` before). */
  requestId: string;
  /** BR-CUS-095 — what the utility ticked for this request type. */
  requiredDocTypes: readonly string[];
  /** Puts a file on the REQUEST (the page creates the draft first if needed). */
  stageDocument: (args: { file: File; docType: string }) => Promise<{ card_id: string; name: string }>;
  /** The service address in words, for *Same as service address*. */
  serviceAddress: string;
  /** The masks of an SSN / licence already on file, as PLACEHOLDERS — the
   *  page's `ssnOnFileMask` / `licenceOnFileMask` (`DEF-CUS-6427`). */
  ssnPlaceholder?: string;
  licencePlaceholder?: string;
  showErrors: boolean;
  t: Translator;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  client?: ApiClient;
}) {
  const { form, update, t } = props;
  const customer = captureToCustomer(form, props.subtypeRows);
  const extras: CustomerWhoExtras = {
    contact_by: form.contact_by,
    trading_as: "",
    business_type: "",
    registered_in: "",
  };
  const onCustomer = (next: CustomerForm) => {
    if (next.customer_kind !== customer.customer_kind) {
      props.onApplicantKindChange(next.customer_kind === CUSTOMER_KIND_COMPANY ? "business" : "person");
      return;
    }
    update(customerToCapturePatch(next, form, props.subtypeRows));
  };
  const prefs: PreferencesValue = {
    paperless: form.paperless,
    sms_reminders: form.sms_reminders,
    autopay: false,
    preferred_language: form.preferred_language,
  };
  const company = customer.customer_kind === CUSTOMER_KIND_COMPANY;

  return (
    <div className="flex flex-col gap-6" data-request-customer-form="">
      <CustomerWhoPanel
        title={t("customers.form.whoApplying")}
        customer={customer}
        onCustomer={onCustomer}
        extras={extras}
        onExtras={(patch) => {
          if (patch.contact_by !== undefined) update({ contact_by: patch.contact_by });
        }}
        showCompanyFacts={false}
        showCompanyContact
        categoryPlaceholder={t("customers.serviceRequest.capture.pickACategory")}
        client={props.client}
        footer={
          <div className="grid grid-cols-2 gap-x-6 gap-y-5">
            <SelectField
              id="channel"
              label={t("customers.serviceRequest.capture.channel")}
              value={form.channel}
              onChange={(value) => update({ channel: value })}
              options={[
                ...CAPTURE_CHANNELS.map((channel) => ({
                  value: channel,
                  label: t(`customers.serviceRequest.channel.${channel}`),
                })),
                // ✅ BR-CUS-091 — a request may originate from staff.
                {
                  value: "staff_collections",
                  label: t("customers.serviceRequest.channel.staff_collections"),
                },
              ]}
            />
          </div>
        }
        showErrors={props.showErrors}
        t={t}
        dateFormat={props.dateFormat}
        timeZone={props.timeZone}
      />

      {company ? null : (
        <CustomerIdentityPanel
          customer={customer}
          onCustomer={onCustomer}
          ssnPlaceholder={props.ssnPlaceholder}
          licencePlaceholder={props.licencePlaceholder}
          t={t}
        />
      )}

      <CustomerCustomFieldsPanel
        screen="REQUEST_NEW"
        values={props.customCustomers}
        onChange={props.onCustomCustomers}
        t={t}
        client={props.client}
      />

      <CoOwnerCards
        kind="co_owner"
        label="co_applicant"
        showPhotoId={false}
        enabled={form.add_co_applicant}
        onEnabledChange={(next) => update({ add_co_applicant: next })}
        rows={form.co_applicants}
        onChange={(rows: CoOwnerDraft[]) => update({ add_co_applicant: true, co_applicants: rows })}
        t={t}
        dateFormat={props.dateFormat}
        timeZone={props.timeZone}
        showErrors={props.showErrors}
      />

      <MoveInDocumentsTable
        rows={props.documents}
        onChange={props.onDocuments}
        serviceRequestId={props.requestId}
        requiredTypes={props.requiredDocTypes}
        stage={props.stageDocument}
        fileHref={(cardId) => `/service-requests/${props.requestId}/documents/${cardId}/content`}
        t={t}
        client={props.client}
      />

      <MailingAddressBlock
        value={mailingOf(form)}
        onChange={(patch) => {
          const next = { ...mailingOf(form), ...patch };
          update({
            billing_address_same: next.mailing_same,
            billing_address: {
              line1: next.mailing_line1,
              line2: next.mailing_line2,
              city: next.mailing_city,
              state: next.mailing_state,
              postal_code: next.mailing_postal_code,
            },
          });
        }}
        serviceAddress={props.serviceAddress}
        t={t}
      />

      <PreferencesPanel
        on={form.prefs_on}
        onTick={(on) =>
          update(on ? { prefs_on: true } : { prefs_on: false, paperless: false, sms_reminders: false })
        }
        value={prefs}
        onChange={(patch) => {
          const out: Partial<CaptureForm> = {};
          if (patch.paperless !== undefined) out.paperless = patch.paperless;
          if (patch.sms_reminders !== undefined) out.sms_reminders = patch.sms_reminders;
          if (patch.preferred_language !== undefined) out.preferred_language = patch.preferred_language;
          update(out);
        }}
        showAutopay={false}
        tickId="request_prefs_on"
        t={t}
        client={props.client}
      />
    </div>
  );
}
