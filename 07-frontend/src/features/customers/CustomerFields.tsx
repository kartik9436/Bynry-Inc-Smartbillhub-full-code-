// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-6356 (Category is a dropdown) · DEF-CUS-6357 (Sub-category,
//           and a category with none says so instead of drawing an empty
//           control) · DEF-CUS-6358 (Date of birth is the kit's date picker in
//           the utility's format) · DEF-CUS-6359 (Same as service address, and
//           US address fields) · DEF-CUS-6360 (rule-33 cuts; the refusal shows
//           only after Continue) — PO reports of 2026-09-23 on the move-in's
//           Customer step, which New account shares.
// Rules:    BR-CUS-067 (the sub-category is filtered by its category, and moves
//           with it) · BR-CUS-1022/1023/1024 (the kind decides which identifier
//           counts; no identifier, no account) · BR-CUS-045 (last four of a
//           government id) · hard rule 8 (`kind='mailing'` is the one address an
//           account may hold) · B14 rules 21 (Tailwind; this file is on
//           route-b-migrated.txt), 33 (no rationale on screen), 38, 43
// Tests:    NewAccountWizard.test.tsx · MoveInWizard.test.tsx ·
//           AccountSubtypePicker.test.tsx · CustomerFields.dom.test.tsx
// Hosts:    NewAccountWizard.tsx (step 1) · MoveInWizard.tsx (step 2)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIELD SET, NOT THE STEP (B14 rule 43, and its own last sentence).**
// The two wizards each carried an inline copy of these fields, 200 lines apiece,
// importable by nothing — so a fix to one never reached the other. This is the
// ONE field set both mount. Each host keeps what is genuinely its own: its
// heading, the move-in's *from the request* note and its documents.
//
// ⚠ **NOTHING HERE EXPLAINS ITSELF ON SCREEN (rule 33).** The hints that said
// why a name is required, why only four digits are kept, what a customer number
// needs and why an empty mailing block means "same as service" are deleted, not
// shortened. The reasons are in the code beside each field.
import type { ReactNode } from "react";

import type { ApiClient } from "@/api/client";

import {
  CheckboxField,
  DatePickerField,
  SegmentedField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { nowInZone } from "@/components/DateCell";
import { RefusalStrip } from "@/components/Surfaces";
import { UsAddressFields, usZipIsValid } from "@/components/UsAddressFields";
import { Fact, FactList } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  accountSubtypeAfterCategoryChange,
  accountSubtypesUnder,
  useAccountCategories,
  useAccountSubtypes,
} from "./customersShared";
import {
  CUSTOMER_KIND_COMPANY,
  CUSTOMER_KIND_PERSON,
  accountIdentityShortfall,
} from "./NewAccountWizard";
import type { CustomerForm } from "./NewAccountWizard";

/**
 * What holds the Customer step, as the catalogue key of its refusal, or null.
 *
 * The identity shortfall first (`BR-CUS-1024`: no identifier, no account),
 * then a ZIP that is not five digits or ZIP+4 on a mailing address the clerk
 * chose to enter. Both hosts' Continue call this, so the two steps cannot hold
 * on different things.
 */
export function customerStepProblem(
  values: CustomerForm,
  /** `DEF-CUS-9052` — the APPROVED REQUEST already identifies this customer
   *  (a customer the clerk linked on it, or a business's Tax ID typed on its
   *  portal application). The server carries it (`_carry_request_decisions`),
   *  so the step does not hold for an identifier the clerk would only retype.
   *  The name, the kind and the ZIP still hold. */
  identityFromRequest = false,
): string | null {
  const shortfall = accountIdentityShortfall(values);
  const carried =
    identityFromRequest &&
    (shortfall === "customers.account.identity_required_company" ||
      shortfall === "customers.account.identity_required_person");
  if (shortfall !== null && !carried) return shortfall;
  if (!values.mailing_same && !usZipIsValid(values.mailing_postal_code)) {
    return "customers.account.mailingZipInvalid";
  }
  return null;
}

/**
 * **CUSTOMER TYPE AND SUB-TYPE — the pair both wizards draw.** Lifted out of
 * `CustomerFields` unchanged (`CR-171-BRC10` P2.22, B14 rule 43) so the
 * move-in's Customer step can set them SIDE BY SIDE as image 33 draws, with
 * `typeHelp` under the type (*Decides the plan, deposit and taxes.*), while New
 * account keeps rendering them stacked exactly as before — the two children
 * are siblings, so the host's grid decides the arrangement.
 */
export function CustomerTypeFields(props: {
  values: CustomerForm;
  onChange: (next: CustomerForm) => void;
  t: Translator;
  // ⚠ Lane CF-1 (2026-10-18): `typeHelp`, `typeLabel` and `subtypeLabel` are
  // GONE — the move-in was their only caller, and the shared customer form
  // draws *Category* / *Sub-category* as the 2026-10-18 drawing set does
  // (images 01, 03, 06), New account's own words. A prop nothing passes is
  // G13's dead UI.
  /** A fact under the sub-type — the shared customer form's *Optional*
   *  (drawing set 2026-10-18, image 01). Absent renders as before. */
  subtypeHelp?: string;
  /** Lane CF-1 — the category's empty first option, for a form that opens
   *  with none (the service request). Absent renders as before. */
  typePlaceholder?: string;
  /** Lane CF-1 — the host's transport for the two reference reads (a test
   *  seam, as every screen's `client`). Absent, the shared one. */
  client?: ApiClient;
}) {
  const { t, values } = props;
  const set = (patch: Partial<CustomerForm>) => props.onChange({ ...values, ...patch });
  const categories = useAccountCategories(props.client);
  const subtypes = useAccountSubtypes(props.client);
  const under = accountSubtypesUnder(subtypes.rows, values.account_type);
  return (
    <>
      {/* DEF-684 — the categories are FETCHED; a legacy code is never offered. */}
      {categories.isLoading ? (
        <p className="met-panel-hint">{t("states.loading")}</p>
      ) : categories.selectable.length === 0 ? (
        <p role="alert" className="met-panel-hint">
          {t("customers.serviceRequest.categoryNotSeeded")}
        </p>
      ) : (
        // `DEF-CUS-6356` — a dropdown (the blueprint's own control, Accounts
        // p073). Seven buttons across was a segmented control past its size.
        <SelectField
          id="account_type"
          label={t("customers.accounts.filter.category")}
          required
          placeholder={props.typePlaceholder}
          value={values.account_type}
          options={categories.selectable.map((category) => ({
            value: category.code,
            label: category.name,
          }))}
          /* The child moves with the parent (`accountSubtypeAfterCategoryChange`
             fails closed): a sub-category that does not hang under the new
             category is cleared rather than committed with it. */
          onChange={(value) =>
            set({
              account_type: value,
              account_subtype: accountSubtypeAfterCategoryChange(
                subtypes.rows,
                values.account_subtype,
                value,
              ),
            })
          }
        />
      )}

      {/* `DEF-CUS-6357` — Sub-category, from the utility's own reference data
          (`OQ-CUS-12618`). OPTIONAL: the column is nullable by design. A
          category with none is a FACT, not an empty control that looks broken;
          a failed read is said as such, and is a different fact. */}
      {subtypes.isLoading ? null : subtypes.failed ? (
        <p role="alert" className="met-panel-hint">
          {t("customers.account.field.subtypeUnavailable")}
        </p>
      ) : under.length === 0 ? (
        <FactList>
          <Fact label={t("customers.account.field.subtype")}>
            <span data-subtype-absent="">{t("customers.account.field.subtypeNoneForCategory")}</span>
          </Fact>
        </FactList>
      ) : (
        <SelectField
          id="account_subtype"
          label={t("customers.account.field.subtype")}
          placeholder={t("customers.account.field.subtypeNone")}
          help={props.subtypeHelp}
          value={values.account_subtype}
          options={under.map((row) => ({ value: row.code, label: row.name }))}
          onChange={(value) => set({ account_subtype: value })}
        />
      )}

    </>
  );
}

export function CustomerFields(props: {
  values: CustomerForm;
  onChange: (next: CustomerForm) => void;
  t: Translator;
  /** True once Continue has been pressed on this step — only then is a
   *  refusal drawn (PO 2026-09-23: nothing red before the clerk has acted). */
  showErrors: boolean;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** A host's own block, drawn between the identity and the mailing address. */
  children?: ReactNode;
  /** `DEF-CUS-9169` — a host's own block drawn UNDER the mailing address and
   *  only while one is being typed: the New Account wizard's address custom
   *  fields (slot `S18`). The move-in has none and passes nothing. */
  mailingExtra?: ReactNode;
  // ⛔ `identityFromRequest` (`DEF-CUS-9052`) is DELETED from this component
  // (`DEF-GOV-10106`): its one host, the move-in, stopped mounting
  // `CustomerFields` when its Customer step was rebuilt (`0e9b22d99`), and
  // `moveInWizard/StepCustomer.tsx` draws the request's identity line itself.
  // The New Account wizard never had a request to read it from.
}) {
  const { t, values } = props;
  const set = (patch: Partial<CustomerForm>) => props.onChange({ ...values, ...patch });
  const problem = props.showErrors ? customerStepProblem(values) : null;
  const today = nowInZone(props.timeZone).slice(0, 10);

  return (
    <>
      <CustomerTypeFields values={values} onChange={props.onChange} t={t} />

      {/* Required: the server needs a name once a contact is sent, and an
          account without one lists as "No contact on file" everywhere. */}
      <TextField
        id="full_name"
        label={t("customers.account.field.fullName")}
        required
        value={values.full_name}
        onChange={(value) => set({ full_name: value })}
      />
      <TextField
        id="email"
        label={t("customers.account.field.email")}
        value={values.email}
        onChange={(value) => set({ email: value })}
      />
      <TextField
        id="phone"
        label={t("customers.account.field.phone")}
        value={values.phone}
        onChange={(value) => set({ phone: value })}
      />
      {/* `DEF-CUS-6358` — the kit's picker, shown in the utility's own format.
          `max` is today in the utility's zone: nobody is born tomorrow, and it
          is what resolves a two-digit year (`87` → 1987). */}
      <DatePickerField
        id="dob"
        label={t("customers.account.field.dob")}
        regional
        value={values.dob}
        max={today}
        dateFormat={props.dateFormat}
        onChange={(value) => set({ dob: value })}
      />
      {/* BR-CUS-045 — the server keeps the last four digits and nothing more,
          so four digits is what is asked for. */}
      <TextField
        id="gov_id_last4"
        label={t("customers.account.field.govId")}
        numeric
        value={values.gov_id_last4}
        onChange={(value) => set({ gov_id_last4: value })}
      />

      {/* `BR-CUS-1022/1023/1024` — the kind decides which identifier counts,
          and it is NOT pre-selected: a default `person` would judge a business
          by a date of birth it has not got. A person needs an SSN, a driving
          license or the phone above; a business needs its Tax ID. */}
      <h4 className="cus-subhead">{t("customers.newAccount.customer.identityTitle")}</h4>
      <SegmentedField
        id="customer_kind"
        label={t("customers.newAccount.field.customerKind")}
        value={values.customer_kind}
        options={[
          { value: CUSTOMER_KIND_PERSON, label: t("customers.customer.kind.person") },
          { value: CUSTOMER_KIND_COMPANY, label: t("customers.customer.kind.company") },
        ]}
        onChange={(value) => set({ customer_kind: value })}
      />
      {values.customer_kind === CUSTOMER_KIND_COMPANY ? (
        <TextField
          id="tax_id"
          label={t("customers.newAccount.field.taxId")}
          value={values.tax_id}
          onChange={(value) => set({ tax_id: value })}
          help={t("customers.newAccount.customer.identityStored")}
        />
      ) : values.customer_kind === CUSTOMER_KIND_PERSON ? (
        <>
          <TextField
            id="ssn"
            label={t("customers.newAccount.field.ssn")}
            value={values.ssn}
            onChange={(value) => set({ ssn: value })}
            help={t("customers.newAccount.customer.identityStored")}
          />
          <TextField
            id="driving_licence"
            label={t("customers.newAccount.field.drivingLicence")}
            value={values.driving_licence}
            onChange={(value) => set({ driving_licence: value })}
          />
        </>
      ) : null}

      {props.children}

      {/* `DEF-CUS-6359` — ticked (the default) writes NO mailing row, which is
          what "same as service" has always meant (B2 §2); unticked, the kit's
          one US address block. `mailingAddressFor` builds the row. */}
      <h4 className="cus-subhead">{t("customers.account.field.mailingAddress")}</h4>
      <CheckboxField
        id="mailing_same"
        label={t("customers.account.field.mailingSame")}
        checked={values.mailing_same}
        onChange={(checked) => set({ mailing_same: checked })}
      />
      {values.mailing_same ? null : (
        <UsAddressFields
          idPrefix="mailing"
          value={{
            line1: values.mailing_line1,
            line2: values.mailing_line2,
            city: values.mailing_city,
            state: values.mailing_state,
            postal_code: values.mailing_postal_code,
          }}
          onChange={(next) =>
            set({
              mailing_line1: next.line1,
              mailing_line2: next.line2,
              mailing_city: next.city,
              mailing_state: next.state,
              mailing_postal_code: next.postal_code,
            })
          }
        />
      )}
      {values.mailing_same ? null : props.mailingExtra}

      {/* The refusal, only once Continue has been pressed. */}
      {problem !== null ? (
        <RefusalStrip role="alert" data-customer-problem="">
          {t(problem)}
        </RefusalStrip>
      ) : null}
    </>
  );
}
