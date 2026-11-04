// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-10251 — a portal request arrives with no category (PO
//           2026-10-18: *"they may not able to provide cargory etc upfront"*)
//           and staff set it before approving (*"this is correct"*). Image
//           05-approve.png draws the marker, the *Set before approving* panel
//           and the *From the customer* summary.
// Rules:    B14 rule 43 (a component — the Approve window mounts it) · rule 44
//           (the drawing says what and where; the kit's `SelectField`,
//           `Panel` and `KeyValueList`-style rows say how) · rule 31 (names,
//           never ids — the sub-category id is sent, never shown) · rule 33 ·
//           rule 21 (Tailwind utilities only)
// Tests:    src/features/customers/RequestCategoryToSet.dom.test.tsx ·
//           ApproveChecksModal.dom.test.tsx
// ───────────────────────────────────────────────────────
import { SelectField } from "@/components/FormModal";

import { RELATIONSHIPS } from "./CoOwnerCards";
import type { AccountCategoryOption, AccountSubtypeRow } from "./customersShared";
import { accountSubtypesUnder } from "./customersShared";
import type { ServiceRequestDetail } from "./serviceRequestEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const NS = "customers.serviceRequest.categoryToSet";

/**
 * **Category to be set** — the marker, and the two pickers that answer it.
 *
 * ⚠ **THE PICK IS SAVED THE MOMENT IT IS MADE** (`onSet` posts to the
 * request's own category door, `set_customer_category`), so the server — which
 * refuses Approve without a category — and this window read one fact. The
 * panel stays drawn for the life of the window once it has been needed
 * (`needed`), so the sub-category can follow the category.
 */
export function RequestCategoryToSet(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  /** True when the window opened on a request still needing its category. */
  needed: boolean;
  categories: readonly AccountCategoryOption[];
  subtypeRows: readonly AccountSubtypeRow[];
  working?: boolean;
  onSet: (accountTypeCode: string, accountSubtypeId: string) => void;
}) {
  const { detail, t } = props;
  if (!props.needed) return null;
  const picked = detail.applicant.customer_category?.account_type?.code ?? "";
  const pickedSub = detail.applicant.customer_category?.account_subtype?.id ?? "";
  const children = accountSubtypesUnder(props.subtypeRows, picked);
  const stillToSet = detail.applicant.category_to_be_set === true;
  return (
    <div className="flex flex-col gap-3" data-category-to-set="">
      {stillToSet ? (
        <p
          className="m-0 border border-dashed border-accent px-3 py-2 text-md text-neutral-900"
          data-category-marker=""
        >
          <strong>{t(`${NS}.marker`)}</strong> {t(`${NS}.cameFromPortal`)}
        </p>
      ) : null}
      <section
        className="flex flex-col gap-2 border border-neutral-200 bg-surface p-4"
        aria-labelledby="category-to-set-title"
      >
        <h4 id="category-to-set-title" className="m-0 text-md font-semibold text-neutral-900">
          {t(`${NS}.title`)}
        </h4>
        <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1">
          <SelectField
            id="approve-category"
            label={t(`${NS}.category`)}
            required
            value={picked}
            placeholder={t(`${NS}.choose`)}
            options={props.categories.map((row) => ({ value: row.code, label: row.name }))}
            disabled={props.working === true}
            onChange={(code) => {
              if (code !== "" && code !== picked) props.onSet(code, "");
            }}
          />
          <SelectField
            id="approve-subcategory"
            label={t(`${NS}.subcategory`)}
            value={pickedSub}
            placeholder={t(`${NS}.choose`)}
            options={children.map((row) => ({ value: row.id, label: row.name }))}
            disabled={props.working === true || picked === "" || children.length === 0}
            onChange={(id) => {
              if (picked !== "") props.onSet(picked, id);
            }}
          />
        </div>
      </section>
    </div>
  );
}

/**
 * **From the customer** — what the applicant gave online, read-only (image 05:
 * Name · Phone · SSN · Co-applicant · Documents). Values come off the request
 * detail; the SSN is the server's last-four projection and nothing more.
 */
/** `Apt 2B · U-00004` — the label as said, then the linked unit's number. */
export function apartmentOf(detail: ServiceRequestDetail): string {
  const place = detail.location_and_services;
  const said = (place?.address_unit_as_given ?? "").trim();
  const linked = place?.resolved_unit_id ? (place.resolved_unit_no ?? "").trim() : "";
  const parts = [said, linked].filter((part) => part !== "");
  return parts.length > 0 ? parts.join(" · ") : "—";
}

export function FromTheCustomer(props: { detail: ServiceRequestDetail; t: Translate }) {
  const { detail, t } = props;
  const applicant = detail.applicant;
  // The first co-applicant card (lane CF-1's `co_applicants`), falling back to
  // the three legacy columns a request from before the cards carries.
  const card = applicant.co_applicants?.[0];
  // DEF-CUS-10257 — a relationship is Move-in's CODE and is named in Move-in's
  // words; an older free-text value is shown as it was typed.
  const relationship =
    card?.relationship && (RELATIONSHIPS as readonly string[]).includes(card.relationship)
      ? t(`customers.moveIn.customer.relationship.${card.relationship}`)
      : (card?.relationship ?? null);
  const co = card
    ? { name: card.full_name, relationship }
    : { name: applicant.co_applicant?.name ?? null, relationship: null };
  const documents = (detail.documents?.documents ?? [])
    .map((row) => row.name ?? "")
    .filter((name) => name !== "");
  const rows: { key: string; label: string; value: string }[] = [
    { key: "name", label: t(`${NS}.from.name`), value: applicant.name ?? "—" },
    { key: "phone", label: t(`${NS}.from.phone`), value: applicant.phone ?? "—" },
    // ⊕ `CR-200-BRC10` F5 (PO 2A) — the apartment the applicant picked or
    // typed, and the unit NUMBER it was linked to (B14 rule 31: never the id).
    { key: "apartment", label: t(`${NS}.from.apartment`), value: apartmentOf(detail) },
    {
      key: "ssn",
      label: t(`${NS}.from.ssn`),
      value: applicant.identifier.ssn_last4
        ? t(`${NS}.from.ssnLast4`, { last4: applicant.identifier.ssn_last4 })
        : "—",
    },
    {
      key: "co_applicant",
      label: t(`${NS}.from.coApplicant`),
      value: co.name
        ? co.relationship
          ? // Two translated facts joined by punctuation, not a sentence: a
            // template of only `{{name}} ({{relationship}})` is the same in
            // every language and was retired (G15).
            `${co.name} (${co.relationship})`
          : co.name
        : "—",
    },
    {
      key: "documents",
      label: t(`${NS}.from.documents`),
      value: documents.length > 0 ? documents.join(", ") : "—",
    },
  ];
  return (
    <section
      className="flex flex-col gap-2 border border-neutral-200 bg-surface p-4"
      aria-labelledby="from-the-customer-title"
      data-from-the-customer=""
    >
      <h4 id="from-the-customer-title" className="m-0 text-md font-semibold text-neutral-900">
        {t(`${NS}.from.title`)}
      </h4>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        {rows.map((row) => (
          <div key={row.key} className="contents" data-from-row={row.key}>
            <dt className="text-md text-neutral-600">{row.label}</dt>
            <dd className="m-0 text-md font-semibold text-neutral-900">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
