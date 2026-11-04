// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard, step 2 · Customer) · CR-171-BRC10
//           P2.22–P2.27 (lane MVI-WIZ-CUST), images 33–40
// Rules:    BR-CUS-045 · BR-CUS-054 · BR-CUS-1022/1024 (the kind decides the
//           identifier) · BR-CUS-019 (a match is advisory) · BR-CUS-073/080 ·
//           BR-CUS-092 · hard rule 8 (the service address is the unit's,
//           walked; only a MAILING address is typed) · B14 rules 21, 31, 33,
//           36–44 · PO ruling 2026-10-05 (1): *"if match based on our logic
//           then we say match if it is not then we dont say it"*
// Server:   CR §9.IDN (as amended 2.537.0) · §9.IDN-2 · §9.1 · P2.25's
//           `documents` key — every key below is one the move-in door admits
// Tests:    moveInWizard/StepCustomer.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE FILE PER STEP — `CR-171-BRC10` P2.15.** This step reads the wizard
// through `MoveInWizardContext` and keeps what it adds in `useStepCustomerOwn`
// (`ctx.own.customer`, `DEF-CUS-9729`), so `MoveInWizard.tsx` is not touched.
//
// THE PANELS, IN IMAGE ORDER
//   Person (images 33–39): Who is moving in · Identity (+ Search customer ID
//   and its answer) · Co-owners · Documents · Mailing address.
//   Company (image 40): Who is moving in (legal name … registered in, + Search
//   customer ID and its answer) · Contact person · Owners and officers · Bills
//   go to · Documents · Mailing address.
//
// ⚠ **THE MATCH IS THE SERVER'S, AND ONLY WHAT OUR RULE CALLS A MATCH IS
// DRAWN.** `found` and `possible` are New Connection's Q5 (lane RULINGS,
// 2.537.0); image 35's *"Only the name matches."* is not built.
// ⊕ **CR-181-BRC10 (lane REOPEN, 2026-10-13)** — two weaker levels below them,
// *same name and phone* and *lived here last* (PO *"Q1 C both"*); the search
// now sends the UNIT, and a linked returning customer whose closed account is
// on this unit is offered *Reopen AC-… / New account* with the balance choice
// (`ReopenChoice`).
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/Button";
import type { CustomFieldValues } from "@/components/CustomFields";
import { CheckboxField, SelectField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { RefusalStrip } from "@/components/Surfaces";
import type { WizardStepVerdict } from "@/components/WizardFrame";
import { Fact, FactList } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  CONTACT_BY,
  CoOwnerCards,
  coOwnerFormatProblem,
  coOwnerProblem,
  coOwnersPayload,
  hydrateCoOwners,
} from "../CoOwnerCards";
import type { CoOwnerDraft } from "../CoOwnerCards";
import { customerStepProblem } from "../CustomerFields";
import { CustomerCustomFieldsPanel, customerCustomPayload } from "../customerForm/CustomerCustomFieldsPanel";
import {
  BUSINESS_TYPES,
  CustomerIdentityPanel,
  CustomerWhoPanel,
  customerFormatProblem,
  emailFormatProblem,
  phoneFormatProblem,
} from "../customerForm/CustomerWhoPanel";
import { MailingAddressBlock } from "../customerForm/MailingAddressBlock";
import { searchCustomerId } from "../customerEndpoints";
import type {
  CustomerSearchQuery,
  CustomerSearchResult,
  CustomerSearchRow,
} from "../customerEndpoints";
import { CustomerMatchPanel } from "../customerMatch/CustomerMatchPanel";
import { MoveInDocumentsTable, documentsPayload, hydrateDocDrafts } from "../MoveInDocumentsTable";
import type { CustomerReopenOffer, ReopenBalanceChoice } from "../customerEndpoints";
import { ReopenChoice, reopenOwes } from "./ReopenChoice";
import type { ReopenMode } from "./ReopenChoice";
import type { MoveInDocDraft } from "../MoveInDocumentsTable";
import { RequestPrefillNote } from "../moveInRequestBlocks";
import { CUSTOMER_KIND_COMPANY, CUSTOMER_KIND_PERSON, customerBlockFor } from "../NewAccountWizard";
import type { CustomerForm } from "../NewAccountWizard";
import type { ServiceRequestDetail } from "../serviceRequestEndpoints";
import type { MoveInWizardContext, StepOwn } from "./moveInWizardContext";

/** Image 40's *Business type* — moved with the Who panel to the shared
 *  customer form (lane CF-1, 2026-10-18) and re-exported for its readers. */
export { BUSINESS_TYPES };

/** The company's contact person (image 40) — a `contacts` row (E59). */
export interface ContactPersonDraft {
  full_name: string;
  job_title: string;
  email: string;
  phone: string;
  contact_by: string;
}

/** This step's own state (`ctx.own.customer`), held across the rail. */
export interface StepCustomerOwn {
  /** The holder's *Contact by* (image 33) — a PERSON's; a company's is the
   *  contact person's. */
  contact_by: string;
  /** The customer the clerk linked — `customer_id` on the commit. Parked with
   *  `accounts: null`: balances are re-read, never carried in a draft. */
  linked: CustomerSearchRow | null;
  /** Customers the clerk said *Not them* to, by handle. */
  dismissed: string[];
  co_owners_on: boolean;
  co_owners: CoOwnerDraft[];
  trading_as: string;
  business_type: string;
  registered_in: string;
  contact: ContactPersonDraft;
  /** *Same as the contact person* (image 40), ticked as drawn. */
  bills_to_contact: boolean;
  po_number: string;
  documents: MoveInDocDraft[];
  /** `CR-181-BRC10` Q2 — reopen the linked customer's closed account on this
   *  unit (`linked.reopen`) or open a new one. Sent only when it is offered. */
  reopen_mode: ReopenMode;
  /** `CR-181-BRC10` Q3 — what happens to what that account still owes. */
  reopen_balance: ReopenBalanceChoice | "";
  /** Lane CF-1 (2026-10-18), `DEF-CUS-10224` — the utility's own customer
   *  fields (*More about the customer*), sent as the customer block's
   *  `custom_data`. It was always `{}` before. */
  custom: CustomFieldValues;
}

export function emptyStepCustomerOwn(): StepCustomerOwn {
  return {
    contact_by: "",
    linked: null,
    dismissed: [],
    co_owners_on: false,
    co_owners: [],
    trading_as: "",
    business_type: "",
    registered_in: "",
    contact: { full_name: "", job_title: "", email: "", phone: "", contact_by: "" },
    bills_to_contact: true,
    po_number: "",
    documents: [],
    reopen_mode: "reopen",
    reopen_balance: "",
    custom: {},
  };
}

/** The reopen the commit will ask for, or null — offered, eligible, chosen. */
export function reopenAsked(own: StepCustomerOwn): CustomerReopenOffer | null {
  const offer = own.linked?.reopen ?? null;
  if (offer === null || !offer.eligible || own.reopen_mode !== "reopen") return null;
  return offer;
}

const trimmed = (value: string): string | undefined =>
  value.trim() === "" ? undefined : value.trim();

function compact(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(obj).filter(([, value]) => value !== undefined));
}

/**
 * What this step adds to the Complete body — merged LAST over the wizard's own
 * (`moveInPayload`), so `contact` and `customer` here REPLACE the wizard's.
 *
 * ⚠ **EVERY KEY IS ONE THE DOOR ADMITS** (`services.MOVE_IN_FIELDS`), and a
 * key belonging to the other kind is never sent: `company`, `po_number` and
 * `bills_go_to` on a person, or an officer-only field on a co-owner, would
 * refuse the whole move-in by name (§9.IDN-2).
 */
export function stepCustomerPayload(
  customer: CustomerForm,
  own: StepCustomerOwn,
): Record<string, unknown> {
  const company = customer.customer_kind === CUSTOMER_KIND_COMPANY;
  const out: Record<string, unknown> = {};

  // The customer block, with the LINK when the clerk made one, and the
  // utility's own customer fields (`DEF-CUS-10224`) whenever any was typed —
  // `services.link_customer` writes them on a new customer and merges them
  // into one already on file. Built by the wizard's own `customerBlockFor`,
  // so replacing the wizard's `customer` key here loses nothing.
  const custom = customerCustomPayload(own.custom);
  if (own.linked !== null) {
    out.customer = {
      ...(customerBlockFor(customer) ?? {}),
      customer_id: own.linked.id,
      ...(custom === undefined ? {} : { custom_data: custom }),
    };
  } else if (custom !== undefined) {
    const block = customerBlockFor(customer);
    if (block !== null) out.customer = { ...block, custom_data: custom };
  }

  if (company) {
    const contact = own.contact;
    if (contact.full_name.trim() !== "") {
      out.contact = compact({
        full_name: contact.full_name.trim(),
        job_title: trimmed(contact.job_title),
        email: trimmed(contact.email),
        phone: trimmed(contact.phone),
        contact_by: trimmed(contact.contact_by),
        is_primary: true,
      });
    }
    const facts = compact({
      trading_as: trimmed(own.trading_as),
      business_type: trimmed(own.business_type),
      registered_in: trimmed(own.registered_in),
    });
    if (Object.keys(facts).length > 0) out.company = facts;
    const po = trimmed(own.po_number);
    if (po !== undefined) out.po_number = po;
    // The choice is sent only when there is a contact to send it to.
    if (out.contact !== undefined) {
      out.bills_go_to = own.bills_to_contact ? "contact_person" : "account_holder";
    }
  } else if (customer.full_name.trim() !== "" && own.contact_by !== "") {
    // The wizard's own contact, plus *Contact by* — rebuilt whole because a
    // step's key replaces the wizard's (`moveInPayload`'s own builder).
    out.contact = {
      full_name: customer.full_name.trim(),
      email: trimmed(customer.email) ?? null,
      phone: trimmed(customer.phone) ?? null,
      dob: customer.dob === "" ? null : customer.dob,
      gov_id_last4:
        customer.gov_id_last4.trim() === "" ? null : customer.gov_id_last4.trim().slice(-4),
      contact_by: own.contact_by,
      is_primary: true,
    };
  }

  if (own.co_owners_on && own.co_owners.length > 0) {
    out.co_owners = coOwnersPayload(company ? "officer" : "co_owner", own.co_owners);
  }
  // CR-181-BRC10 — the SAME account, reopened, and the clerk's balance choice.
  const reopen = reopenAsked(own);
  if (reopen !== null) {
    out.reopen_account_id = reopen.account_id;
    if (own.reopen_balance !== "") out.reopen_balance = own.reopen_balance;
  }
  const documents = documentsPayload(own.documents);
  if (documents.length > 0) out.documents = documents;
  return out;
}

/** The parked shape — the linked customer WITHOUT its money (the reopen
 *  offer keeps its account and loses its figure). */
function parkOf(own: StepCustomerOwn): Record<string, unknown> {
  return {
    ...own,
    linked:
      own.linked === null
        ? null
        : {
            ...own.linked,
            accounts: null,
            reopen:
              own.linked.reopen === null || own.linked.reopen === undefined
                ? null
                : { ...own.linked.reopen, outstanding: null },
          },
  };
}

function hydrateReopenOffer(raw: unknown): CustomerReopenOffer | null {
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.account_id !== "string" || typeof r.account_no !== "string") return null;
  return {
    account_id: r.account_id,
    account_no: r.account_no,
    closed_at: typeof r.closed_at === "string" ? r.closed_at : null,
    eligible: r.eligible === true,
    reason: null,
    // Money is never parked: a resumed draft is asked about the balance anew.
    outstanding: null,
    currency: typeof r.currency === "string" ? r.currency : null,
    within_years: typeof r.within_years === "number" ? r.within_years : 0,
  };
}

function str(raw: Record<string, unknown>, key: string): string {
  return typeof raw[key] === "string" ? (raw[key] as string) : "";
}

/** A parked slice, distrusted field by field (`StepOwn.hydrate`). */
export function hydrateStepCustomerOwn(parked: unknown): StepCustomerOwn {
  const base = emptyStepCustomerOwn();
  if (typeof parked !== "object" || parked === null) return base;
  const raw = parked as Record<string, unknown>;
  const contact =
    typeof raw.contact === "object" && raw.contact !== null
      ? (raw.contact as Record<string, unknown>)
      : {};
  const linkedRaw =
    typeof raw.linked === "object" && raw.linked !== null
      ? (raw.linked as Record<string, unknown>)
      : null;
  const linked =
    linkedRaw !== null && typeof linkedRaw.id === "string"
      ? ({
          id: linkedRaw.id,
          customer_no: typeof linkedRaw.customer_no === "string" ? linkedRaw.customer_no : null,
          display_name: str(linkedRaw, "display_name"),
          kind: str(linkedRaw, "kind"),
          verdict:
            linkedRaw.verdict === "possible" ||
            linkedRaw.verdict === "name_phone" ||
            linkedRaw.verdict === "last_occupant"
              ? linkedRaw.verdict
              : "found",
          agreed: Array.isArray(linkedRaw.agreed)
            ? linkedRaw.agreed.filter((code): code is string => typeof code === "string")
            : [],
          last_occupant: linkedRaw.last_occupant === true,
          reopen: hydrateReopenOffer(linkedRaw.reopen),
          accounts: null,
          company: null,
        } satisfies CustomerSearchRow)
      : null;
  const contactBy = str(raw, "contact_by");
  return {
    contact_by: (CONTACT_BY as readonly string[]).includes(contactBy) ? contactBy : "",
    linked,
    dismissed: Array.isArray(raw.dismissed)
      ? raw.dismissed.filter((id): id is string => typeof id === "string")
      : [],
    co_owners_on: raw.co_owners_on === true,
    co_owners: hydrateCoOwners(raw.co_owners),
    trading_as: str(raw, "trading_as"),
    business_type: str(raw, "business_type"),
    registered_in: str(raw, "registered_in"),
    contact: {
      full_name: str(contact, "full_name"),
      job_title: str(contact, "job_title"),
      email: str(contact, "email"),
      phone: str(contact, "phone"),
      contact_by: str(contact, "contact_by"),
    },
    bills_to_contact: raw.bills_to_contact !== false,
    po_number: str(raw, "po_number"),
    documents: hydrateDocDrafts(raw.documents),
    reopen_mode: raw.reopen_mode === "new" ? "new" : "reopen",
    reopen_balance:
      raw.reopen_balance === "pay_first" || raw.reopen_balance === "carry"
        ? raw.reopen_balance
        : "",
    custom:
      typeof raw.custom === "object" && raw.custom !== null && !Array.isArray(raw.custom)
        ? { ...(raw.custom as CustomFieldValues) }
        : {},
  };
}

// `DEF-CUS-9729` — takes the wizard's customer form, the state this step's own
// payload is derived from.
export function useStepCustomerOwn(customer: CustomerForm): StepOwn<StepCustomerOwn> {
  const [value, set] = useState<StepCustomerOwn>(emptyStepCustomerOwn);
  return {
    value,
    set,
    payload: stepCustomerPayload(customer, value),
    park: parkOf(value),
    hydrate: (parked) => set(hydrateStepCustomerOwn(parked)),
  };
}

/**
 * What holds the Customer step, as a catalogue key, or null — the first
 * problem only, in the order the panels are drawn.
 */
export function moveInCustomerProblem(
  customer: CustomerForm,
  own: StepCustomerOwn,
  identityFromRequest: boolean,
): string | null {
  const company = customer.customer_kind === CUSTOMER_KIND_COMPANY;
  if (customer.full_name.trim() === "") {
    return company
      ? "customers.moveIn.customer.problem.legalName"
      : "customers.moveIn.customer.problem.fullName";
  }
  if (company) {
    if (own.business_type === "") return "customers.moveIn.customer.problem.businessType";
  } else if (customer.phone.trim() === "") {
    return "customers.moveIn.customer.problem.phone";
  }
  // Lane CF-1 (task 10) — the phone and email are format-checked on every
  // create screen (decision log 2026-10-18).
  if (!company) {
    const format = customerFormatProblem(customer);
    if (format !== null) return format;
  }
  // A linked customer IS the identity (`customer_id`), so the identifier
  // boxes are not demanded — the same posture as a request that carries one.
  const shortfall = customerStepProblem(customer, identityFromRequest || own.linked !== null);
  if (shortfall !== null) return shortfall;
  if (company) {
    const contact = own.contact;
    if (
      contact.full_name.trim() === "" ||
      contact.email.trim() === "" ||
      contact.phone.trim() === ""
    ) {
      return "customers.moveIn.customer.problem.contact";
    }
    const format = emailFormatProblem(contact.email) ?? phoneFormatProblem(contact.phone);
    if (format !== null) return format;
  }
  if (own.co_owners_on) {
    const problem = coOwnerProblem(own.co_owners) ?? coOwnerFormatProblem(own.co_owners);
    if (problem !== null) return problem;
  }
  // CR-181-BRC10 Q3 — reopening an account that owes: the clerk chooses.
  const reopen = reopenAsked(own);
  if (reopen !== null && reopenOwes(reopen) && own.reopen_balance === "") {
    return "customers.moveIn.reopen.choiceRequired";
  }
  return null;
}

/** Continue on step 2 (`WizardFrame`'s `validate`). */
export function stepCustomerVerdict(ctx: MoveInWizardContext): WizardStepVerdict {
  ctx.markTried("customer");
  return (
    moveInCustomerProblem(ctx.customer, ctx.own.customer.value, ctx.identityFromRequest !== null) ===
    null
  );
}

/** The search's question, from what the clerk has typed (`/customers/match`).
 *  `unitId` (CR-181-BRC10) lets the server find the unit's last occupant and
 *  offer a reopen; the email is not sent — no customer row holds one. */
export function searchQueryFor(customer: CustomerForm, unitId = ""): CustomerSearchQuery | null {
  const kind = customer.customer_kind;
  if (kind !== CUSTOMER_KIND_PERSON && kind !== CUSTOMER_KIND_COMPANY) return null;
  const query: CustomerSearchQuery = { kind };
  if (unitId !== "") query.unit_id = unitId;
  const put = (key: Exclude<keyof CustomerSearchQuery, "kind">, value: string) => {
    if (value.trim() !== "") query[key] = value.trim();
  };
  put("name", customer.full_name);
  if (kind === CUSTOMER_KIND_COMPANY) {
    put("tax_id", customer.tax_id);
  } else {
    put("date_of_birth", customer.dob);
    put("ssn", customer.ssn);
    put("driving_licence", customer.driving_licence);
    put("phone", customer.phone);
  }
  return query;
}

/** Step 2 as the rail draws it. */
export function StepCustomer(props: { ctx: MoveInWizardContext }) {
  const { ctx } = props;
  const { t, customer } = ctx;
  const own = ctx.own.customer.value;
  const setOwn = (patch: Partial<StepCustomerOwn>) => ctx.own.customer.set({ ...own, ...patch });
  const set = (patch: Partial<CustomerForm>) => ctx.setCustomer({ ...customer, ...patch });
  const company = customer.customer_kind === CUSTOMER_KIND_COMPANY;
  const problem = ctx.tried.customer
    ? moveInCustomerProblem(customer, own, ctx.identityFromRequest !== null)
    : null;

  const [answer, setAnswer] = useState<CustomerSearchResult | null>(null);
  const search = useMutation({
    mutationFn: (query: CustomerSearchQuery) => searchCustomerId(query, ctx.client),
    onSuccess: (result) => setAnswer(result),
    onError: () => setAnswer(null),
  });
  const query = searchQueryFor(customer, ctx.outgoingUnitId);
  // CR-181-BRC10 — after Payments recorded the old balance, ask again so the
  // figure is the ledger's; the linked row is replaced by its fresh self.
  const refresh = useMutation({
    mutationFn: (q: CustomerSearchQuery) => searchCustomerId(q, ctx.client),
    onSuccess: (result) => {
      setAnswer(result);
      const fresh = result.customers.find((row) => row.id === own.linked?.id);
      if (fresh !== undefined) setOwn({ linked: fresh });
    },
  });

  const link = (row: CustomerSearchRow) => {
    // A linked company brings its own facts where the clerk typed nothing.
    const facts = row.company;
    const person = facts?.contact_person ?? null;
    setOwn({
      linked: row,
      reopen_mode: "reopen",
      reopen_balance: "",
      trading_as: own.trading_as === "" ? (facts?.trading_as ?? "") : own.trading_as,
      business_type: own.business_type === "" ? (facts?.business_type ?? "") : own.business_type,
      registered_in: own.registered_in === "" ? (facts?.registered_in ?? "") : own.registered_in,
      po_number: own.po_number === "" ? (facts?.po_number ?? "") : own.po_number,
      contact:
        own.contact.full_name === "" && person !== null
          ? {
              full_name: person.full_name ?? "",
              job_title: person.job_title ?? "",
              email: person.email ?? "",
              phone: person.phone ?? "",
              contact_by: person.contact_by ?? "",
            }
          : own.contact,
    });
  };

  const searchButton = (
    <Button
      data-search-customer-id=""
      disabled={query === null || search.isPending}
      title={query === null ? t("customers.moveIn.customer.match.needKind") : undefined}
      onClick={() => {
        if (query !== null) search.mutate(query);
      }}
    >
      {t("customers.moveIn.customer.search")}
    </Button>
  );
  const matchPanel = (
    <CustomerMatchPanel
      result={answer}
      pending={search.isPending}
      failed={search.isError}
      linkedId={own.linked?.id ?? null}
      linkedRow={own.linked}
      dismissed={own.dismissed}
      onLink={link}
      onUnlink={() => setOwn({ linked: null })}
      onNotThem={(row) => setOwn({ dismissed: [...own.dismissed, row.id] })}
      timeZone={ctx.timeZone}
      dateFormat={ctx.dateFormat}
    />
  );
  const contactBy = (id: string, value: string, onChange: (value: string) => void) => (
    <SelectField
      id={id}
      label={t("customers.moveDetail.col.contactBy")}
      placeholder={t("customers.moveIn.customer.choose")}
      value={value}
      options={CONTACT_BY.map((code) => ({
        value: code,
        label: t(`customers.moveDetail.contactBy.${code}`),
      }))}
      onChange={onChange}
    />
  );
  const fromRequest =
    ctx.identityFromRequest === null ? null : (
      <FactList>
        <Fact label={ctx.identityFromRequest.label}>
          <span data-identity-from-request="">{ctx.identityFromRequest.value}</span>
        </Fact>
      </FactList>
    );
  const contact = own.contact;
  const setContact = (patch: Partial<ContactPersonDraft>) =>
    setOwn({ contact: { ...contact, ...patch } });
  const show = ctx.tried.customer;

  // Lane CF-1 (2026-10-18) — the SHARED customer form (`customerForm/`):
  // Who, Identity (+ the search results table), More about the customer,
  // Co-owners, Documents, Mailing address — images 01, 10–16, in their order.
  return (
    <div className="flex flex-col gap-6" data-move-in-customer="">
      <CustomerWhoPanel
        title={t("customers.moveIn.customer.whoTitle")}
        customer={customer}
        onCustomer={ctx.setCustomer}
        extras={own}
        onExtras={(patch) => setOwn(patch)}
        note={<RequestPrefillNote requestNo={ctx.serviceRequestNo} t={t} />}
        companyTrailing={
          <>
            {fromRequest}
            <div className="flex justify-end">{searchButton}</div>
            {matchPanel}
          </>
        }
        showErrors={show}
        t={t}
        dateFormat={ctx.dateFormat}
        timeZone={ctx.timeZone}
        client={ctx.client}
      />

      {company ? (
        <Panel
          as="section"
          title={t("customers.moveIn.customer.contactPerson")}
          data-customer-panel="contact"
        >
          <div className="grid grid-cols-2 gap-x-6 gap-y-5">
            <TextField
              id="contact_full_name"
              label={t("customers.account.field.fullName")}
              required
              value={contact.full_name}
              onChange={(value) => setContact({ full_name: value })}
            />
            <TextField
              id="contact_job_title"
              label={t("customers.moveIn.customer.jobTitle")}
              value={contact.job_title}
              onChange={(value) => setContact({ job_title: value })}
            />
            <TextField
              id="contact_email"
              label={t("customers.account.field.email")}
              required
              value={contact.email}
              error={
                show && emailFormatProblem(contact.email) !== null
                  ? t(emailFormatProblem(contact.email) ?? "")
                  : undefined
              }
              onChange={(value) => setContact({ email: value })}
            />
            <TextField
              id="contact_phone"
              label={t("customers.account.field.phone")}
              required
              help={t("customers.moveIn.customer.phoneHelp")}
              value={contact.phone}
              error={
                show && phoneFormatProblem(contact.phone) !== null
                  ? t(phoneFormatProblem(contact.phone) ?? "")
                  : undefined
              }
              onChange={(value) => setContact({ phone: value })}
            />
            {contactBy("contact_contact_by", contact.contact_by, (value) =>
              setContact({ contact_by: value }),
            )}
          </div>
        </Panel>
      ) : (
        <CustomerIdentityPanel
          customer={customer}
          onCustomer={ctx.setCustomer}
          trailing={searchButton}
          ssnPlaceholder={ctx.requestIdentifierMasks?.ssn}
          licencePlaceholder={ctx.requestIdentifierMasks?.licence}
          t={t}
        >
          {fromRequest}
          {matchPanel}
        </CustomerIdentityPanel>
      )}

      {own.linked?.reopen ? (
        <ReopenChoice
          offer={own.linked.reopen}
          mode={own.reopen_mode}
          balance={own.reopen_balance}
          onMode={(mode) => {
            ctx.clearReopenRefusal?.();
            setOwn({ reopen_mode: mode });
          }}
          onBalance={(choice) => {
            ctx.clearReopenRefusal?.();
            setOwn({ reopen_balance: choice });
          }}
          onPaid={() => {
            ctx.clearReopenRefusal?.();
            if (query !== null) refresh.mutate(query);
          }}
          refusal={ctx.reopenRefusal ?? null}
          t={t}
          timeZone={ctx.timeZone}
          dateFormat={ctx.dateFormat}
          client={ctx.client}
          showErrors={ctx.tried.customer}
        />
      ) : null}

      <CustomerCustomFieldsPanel
        screen="S18"
        values={own.custom}
        onChange={(values) => setOwn({ custom: values })}
        t={t}
        client={ctx.client}
      />

      <CoOwnerCards
        kind={company ? "officer" : "co_owner"}
        enabled={own.co_owners_on}
        onEnabledChange={(next) => setOwn({ co_owners_on: next })}
        rows={own.co_owners}
        onChange={(rows) => ctx.own.customer.set({ ...own, co_owners_on: true, co_owners: rows })}
        t={t}
        dateFormat={ctx.dateFormat}
        timeZone={ctx.timeZone}
        showErrors={ctx.tried.customer}
      />

      {company ? (
        <Panel as="section" title={t("customers.moveIn.customer.billsGoTo")} data-customer-panel="bills">
          <div className="flex flex-col gap-5">
            <CheckboxField
              id="bills_to_contact"
              label={t("customers.moveIn.customer.sameAsContact")}
              checked={own.bills_to_contact}
              onChange={(checked) => setOwn({ bills_to_contact: checked })}
            />
            <div className="grid grid-cols-2 gap-x-6">
              <TextField
                id="po_number"
                label={t("customers.moveIn.customer.poNumber")}
                value={own.po_number}
                onChange={(value) => setOwn({ po_number: value })}
              />
            </div>
          </div>
        </Panel>
      ) : null}

      <MoveInDocumentsTable
        rows={own.documents}
        onChange={(rows) => setOwn({ documents: rows })}
        serviceRequestId={ctx.serviceRequestId}
        t={t}
        client={ctx.client}
      />

      <MailingAddressBlock
        value={customer}
        onChange={(patch) => set(patch)}
        serviceAddress={ctx.unitLabel}
        t={t}
      />

      {problem !== null ? (
        <RefusalStrip role="alert" data-customer-problem="">
          {t(problem)}
        </RefusalStrip>
      ) : null}
    </div>
  );
}

/** `DEF-CUS-9052` — the one line the customer step draws for what the request
 *  already identifies, or `null`. The NUMBER and the name, never the id (B14
 *  rule 31); a Tax ID as its last four, exactly as the request page shows it. */
export function requestIdentityLine(
  request: ServiceRequestDetail | undefined,
  kind: string,
  t: Translator,
): { label: string; value: string } | null {
  if (request === undefined) return null;
  const match = request.applicant.customer_match;
  if (match.customer_id) {
    return {
      label: t("customers.finder.linked"),
      value: [match.customer_no, match.display_name].filter((part) => part).join(" · "),
    };
  }
  const identifier = request.applicant.identifier;
  if (kind === CUSTOMER_KIND_COMPANY && identifier.tax_id_present === true) {
    return {
      label: t("customers.newAccount.field.taxId"),
      value: `•••• ${identifier.tax_id_last4 ?? ""}`,
    };
  }
  return null;
}
