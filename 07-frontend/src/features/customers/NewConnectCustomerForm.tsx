// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 13 — New Connection's owner step IS
//           the shared customer form (customer-forms drawing set, image 06 —
//           read as an IMAGE, B14 rule 42): Who will own the account ·
//           Identity with *Search customer ID* and the search results table ·
//           More about the customer (`NEW_CONNECTION_OWNER`) · Co-owners ·
//           Documents · Mailing address. The Preferences move to the charges
//           step, as image 02 draws them.
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"* — PO verbatim: *"Move in UI is latest and
//           correct"*, *"ALSO DATA COLECTED IS NOT LOST"*. `DEF-CUS-10222` (the
//           mailing address typed here never reached the account) ·
//           `DEF-CUS-10225` (four customer forms).
// Rules:    BR-CUS-1022/1023/1024 (the kind decides the identifier; the door
//           refuses an account without one) · BR-CUS-019 (the clerk links) ·
//           BR-CUS-092 (identifiers last-four on every read) · BR-MET-112
//           (nothing is written before Create — files are held and filed
//           after) · hard rule 8 (mailing is where the bill goes) · B14 rules
//           21, 31, 33, 41–44
// Tests:    newConnectCustomerForm.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE DRAFT KEEPS ITS OWN SHAPE (`OwnerForm`) AND MAPS AT THIS EDGE**, as
// the service request's `CaptureCustomerForm` does: the owner block, parked
// drafts and the commit plan speak `name` / `partyKind` / `drivingLicence`,
// and the shared panels speak `CustomerForm`. Each way is translated once,
// here, so neither learns the other's words.
//
// ⚠ **OWNER TYPE STAYS, UNDER THE WHO PANEL'S FIELDS.** Image 06 does not
// draw it; it is the utility's own owner list (`BR-TEN-150`) and decides
// whether the owner holds a single-family home (`owner_lives_there`, PO
// 2026-10-03). A control that carries a ruling is not removed by a drawing's
// omission — recorded as a difference left in the walk.
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";

import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { Translator } from "@/features/tenancy/settingsShared";

import { CoOwnerCards } from "./CoOwnerCards";
import type { CoOwnerDraft } from "./CoOwnerCards";
import { searchCustomerId } from "./customerEndpoints";
import type { CustomerSearchQuery, CustomerSearchResult, CustomerSearchRow } from "./customerEndpoints";
import { CustomerCustomFieldsPanel } from "./customerForm/CustomerCustomFieldsPanel";
import { CustomerIdentityPanel, CustomerWhoPanel } from "./customerForm/CustomerWhoPanel";
import type { CustomerWhoExtras } from "./customerForm/CustomerWhoPanel";
import { MailingAddressBlock } from "./customerForm/MailingAddressBlock";
import type { MailingAddressValue } from "./customerForm/MailingAddressBlock";
import { CustomerMatchPanel } from "./customerMatch/CustomerMatchPanel";
import { MoveInDocumentsTable } from "./MoveInDocumentsTable";
import { searchQueryFor } from "./moveInWizard/StepCustomer";
import { CUSTOMER_KIND_COMPANY, emptyCustomerForm } from "./NewAccountWizard";
import type { CustomerForm } from "./NewAccountWizard";
import { draftCoOwners } from "./newConnectDraft";
import { ownerBirthDateSentence, ownerHasABirthDate, todayIn } from "./newConnectOwnerRules";
import type { DraftDocument, NewConnectDraft, OwnerForm } from "./newConnectDraft";
import { RequestPrefillNote } from "./moveInRequestBlocks";

/** Every request document lands in the account's KYC folder — move-in's own
 *  rule (`move_in_people.CARRIED_DOC_FOLDER`, BR-CUS-036): proof of identity,
 *  of address, a deed, an authority to act are all what the utility was shown
 *  about who this customer is. */
export const OWNER_DOCUMENT_FOLDER = "kyc";

/** The owner as the shared form's `CustomerForm`. */
export function ownerToCustomer(owner: OwnerForm): CustomerForm {
  return {
    ...emptyCustomerForm(),
    customer_kind: owner.partyKind,
    account_type: owner.category,
    account_subtype: owner.subCategory,
    full_name: owner.name,
    email: owner.email,
    phone: owner.phone,
    dob: owner.dateOfBirth,
    ssn: owner.ssn,
    driving_licence: owner.drivingLicence,
    tax_id: owner.taxId,
    gov_id_last4: owner.govIdLast4 ?? "",
  };
}

/** What changed in the shared form, as a patch of the owner. A kind change
 *  blanks the other kind's identifier, as every create screen does. */
export function customerToOwnerPatch(next: CustomerForm, owner: OwnerForm): Partial<OwnerForm> {
  const patch: Partial<OwnerForm> = {
    partyKind: next.customer_kind,
    category: next.account_type,
    subCategory: next.account_subtype,
    name: next.full_name,
    email: next.email,
    phone: next.phone,
    dateOfBirth: next.dob,
    ssn: next.ssn,
    drivingLicence: next.driving_licence,
    taxId: next.tax_id,
    govIdLast4: next.gov_id_last4,
  };
  if (next.customer_kind !== owner.partyKind) {
    if (next.customer_kind === CUSTOMER_KIND_COMPANY) {
      Object.assign(patch, { ssn: "", drivingLicence: "", dateOfBirth: "", govIdLast4: "" });
    } else {
      patch.taxId = "";
    }
  }
  return patch;
}

function mailingOf(draft: NewConnectDraft): MailingAddressValue {
  const mailing = draft.mailing;
  return {
    mailing_same: mailing.sameAsService,
    mailing_line1: mailing.address,
    mailing_line2: mailing.unit,
    mailing_city: mailing.city,
    mailing_state: mailing.state,
    mailing_postal_code: mailing.postalCode,
  };
}

/** The service address in words, walked from step 2's premise (hard rule 8). */
function serviceAddressOf(draft: NewConnectDraft): string {
  const p = draft.premise;
  return [p.address, p.unit, p.city, [p.state, p.postalCode].filter(Boolean).join(" ")]
    .map((part) => part.trim())
    .filter((part) => part !== "")
    .join(", ");
}

/** A link read back from a parked draft holds no row: draw it from what the
 *  draft does hold (no money — balances are never parked). */
function linkedRowOf(owner: OwnerForm): CustomerSearchRow | null {
  if (owner.matchedCustomerId === null) return null;
  return (
    owner.matchedRow ?? {
      id: owner.matchedCustomerId,
      customer_no: owner.matchedCustomerNo,
      display_name: owner.name,
      kind: owner.partyKind,
      verdict: "found",
      agreed: [],
      accounts: null,
      company: null,
    }
  );
}

export function NewConnectCustomerForm(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  /** Show the refusals (format, required) — after Continue was pressed. */
  showErrors: boolean;
  t: Translator;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** The host's *Owner type* control, drawn under the Who panel's fields. */
  ownerTypeField: ReactNode;
  /** Opens a file held on the draft (it exists only in this browser). */
  onOpenHeldFile: (localId: string) => void;
  client?: ApiClient;
}) {
  const { draft, t } = props;
  const owner = draft.owner;
  const setOwner = (patch: Partial<OwnerForm>) => props.onPatch({ owner: { ...owner, ...patch } });
  const customer = ownerToCustomer(owner);
  const company = owner.partyKind === CUSTOMER_KIND_COMPANY;
  const attached = owner.matchedCustomerId !== null;

  // ── Search customer ID — Move-in's own button, question and table ────────
  const [answer, setAnswer] = useState<CustomerSearchResult | null>(null);
  const search = useMutation({
    mutationFn: (query: CustomerSearchQuery) => searchCustomerId(query, props.client),
    onSuccess: (result) => setAnswer(result),
    onError: () => setAnswer(null),
  });
  const query = searchQueryFor(customer);
  /** LINK — *"if found, attach and do not retype"*: the commit names the
   *  customer, so the identifiers are not re-presented (BR-CUS-092(c)). */
  const link = (row: CustomerSearchRow) =>
    setOwner({
      matchedCustomerId: row.id,
      matchedCustomerNo: row.customer_no,
      matchedRow: row,
      name: owner.name.trim() === "" ? row.display_name : owner.name,
      partyKind: row.kind,
      ssn: "",
      drivingLicence: "",
      taxId: "",
    });
  /** Unlinking is also *Not them* for that customer, so a re-run search does
   *  not offer the same row again. */
  const unlink = () =>
    setOwner({
      matchedCustomerId: null,
      matchedCustomerNo: null,
      matchedRow: null,
      dismissedMatchIds:
        owner.matchedCustomerId === null
          ? owner.dismissedMatchIds
          : [...(owner.dismissedMatchIds ?? []), owner.matchedCustomerId],
    });
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
      linkedId={owner.matchedCustomerId}
      linkedRow={linkedRowOf(owner)}
      dismissed={owner.dismissedMatchIds ?? []}
      onLink={link}
      onUnlink={unlink}
      onNotThem={(row) => setOwner({ dismissedMatchIds: [...(owner.dismissedMatchIds ?? []), row.id] })}
      timeZone={props.timeZone}
      dateFormat={props.dateFormat}
    />
  );

  const extras: CustomerWhoExtras = {
    contact_by: owner.contactBy ?? "",
    trading_as: "",
    business_type: "",
    registered_in: "",
  };
  const cards = draftCoOwners(draft);

  /** A file is held on the draft until Create (BR-MET-112) and filed on the
   *  owner's account afterwards; the row names it by a LOCAL key. */
  const holdDocument = async (args: { file: File; docType: string }) => {
    const id = `local-${draft.ownerDocuments.length}-${Date.now().toString(36)}-${args.file.name}`;
    const held: DraftDocument = {
      id,
      docType: OWNER_DOCUMENT_FOLDER,
      name: args.file.name,
      whatItProves: args.docType,
      required: false,
      file: args.file,
      attachedAt: new Date().toISOString(),
    };
    props.onPatch({ ownerDocuments: [...draft.ownerDocuments, held] });
    return { card_id: id, name: args.file.name };
  };

  return (
    <div className="flex flex-col gap-6" data-new-connect-customer-form="">
      <CustomerWhoPanel
        title={t("customers.form.whoOwns")}
        customer={customer}
        onCustomer={(next) => setOwner(customerToOwnerPatch(next, owner))}
        extras={extras}
        onExtras={(patch) => {
          if (patch.contact_by !== undefined) setOwner({ contactBy: patch.contact_by });
        }}
        showCompanyFacts={false}
        showCompanyContact
        categoryPlaceholder={t("customers.serviceRequest.capture.pickACategory")}
        companyTrailing={
          <div className="flex flex-col gap-3">
            <div>{searchButton}</div>
            {matchPanel}
          </div>
        }
        note={
          <>
            {/* BR-MET-111 — the owner BECOMES a customer, which is what makes
                them billable at the charges step (DEF-650). A statement of
                consequence, kept from the step's own design. */}
            <p
              className="mb-3 inline-block bg-success-100 px-2 py-1 text-xs text-success-700"
              data-badge="becomes-a-customer"
            >
              {t("customers.newConnect.step1.badge", { defaultValue: "Becomes a customer" })}
            </p>
            {draft.requestNo !== null ? (
              <div className="mb-3" data-from-request="owner">
                <RequestPrefillNote requestNo={draft.requestNo} t={t} />
              </div>
            ) : null}
          </>
        }
        footer={<div className="grid grid-cols-2 gap-x-6 gap-y-5">{props.ownerTypeField}</div>}
        showErrors={props.showErrors}
        dobError={
          ownerHasABirthDate(owner)
            ? (ownerBirthDateSentence(owner.dateOfBirth, todayIn(props.timeZone), t) ?? undefined)
            : undefined
        }
        t={t}
        dateFormat={props.dateFormat}
        timeZone={props.timeZone}
        client={props.client}
      />

      {company ? null : (
        <CustomerIdentityPanel
          customer={customer}
          onCustomer={(next) => setOwner(customerToOwnerPatch(next, owner))}
          trailing={searchButton}
          licenceMasked
          ssnPlaceholder={
            (owner.applicationSsnLast4 ?? "") !== "" ? `•••-••-${owner.applicationSsnLast4}` : undefined
          }
          licencePlaceholder={
            (owner.applicationLicenceLast4 ?? "") !== "" ? `•••• ${owner.applicationLicenceLast4}` : undefined
          }
          t={t}
        >
          {matchPanel}
        </CustomerIdentityPanel>
      )}

      {/* The owner's own customer fields are written on a customer this build
          CREATES; over a customer the clerk linked nothing is rewritten. */}
      {attached ? null : (
        <CustomerCustomFieldsPanel
          screen="NEW_CONNECTION_OWNER"
          values={draft.ownerCustomData ?? {}}
          onChange={(ownerCustomData) => props.onPatch({ ownerCustomData })}
          t={t}
          client={props.client}
        />
      )}

      <CoOwnerCards
        kind={company ? "officer" : "co_owner"}
        licenceMasked
        enabled={cards.on}
        onEnabledChange={(next) => props.onPatch({ coOwnersOn: next, coOwners: cards.rows })}
        rows={cards.rows}
        onChange={(rows: CoOwnerDraft[]) => props.onPatch({ coOwnersOn: true, coOwners: rows })}
        t={t}
        dateFormat={props.dateFormat}
        timeZone={props.timeZone}
        showErrors={props.showErrors}
      />

      <MoveInDocumentsTable
        rows={draft.ownerDocDrafts ?? []}
        onChange={(ownerDocDrafts) => props.onPatch({ ownerDocDrafts })}
        serviceRequestId={draft.requestId ?? ""}
        stage={holdDocument}
        openFile={props.onOpenHeldFile}
        t={t}
        client={props.client}
      />

      <MailingAddressBlock
        value={mailingOf(draft)}
        onChange={(patch) => {
          const next = { ...mailingOf(draft), ...patch };
          props.onPatch({
            mailing: {
              sameAsService: next.mailing_same,
              address: next.mailing_line1,
              unit: next.mailing_line2,
              city: next.mailing_city,
              state: next.mailing_state,
              postalCode: next.mailing_postal_code,
            },
          });
        }}
        serviceAddress={serviceAddressOf(draft)}
        t={t}
      />
    </div>
  );
}
