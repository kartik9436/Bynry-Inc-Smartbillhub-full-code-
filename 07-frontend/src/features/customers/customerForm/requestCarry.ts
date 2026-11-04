// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 11 — **an approved request's answers,
//           as the shared customer form's values**, so the move-in (and the
//           new connect) it leads to opens with every field filled in and the
//           service request's own capture page reopens on what it saved.
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"* — PO: *"ALSO DATA COLECTED IS NOT LOST"*;
//           drawing set `customer-forms-2026-10-18` image 01's side note
//           *"From an approved request: every field arrives filled in"*.
// Rules:    BR-CUS-092(c) — a card's SSN and licence are served as their LAST
//           FOUR and are therefore NEVER put in a box (the server carries the
//           stored numbers — `services._carry_request_co_applicants`).
// Tests:    moveInFromRequestPrefill.dom.test.tsx · serviceRequestEdit.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { CustomFieldValues } from "@/components/CustomFields";

import { emptyCoOwner, hydrateCoOwners, idOnFileMask } from "../CoOwnerCards";
import type { CoOwnerDraft } from "../CoOwnerCards";
import type { ServiceRequestDetail } from "../serviceRequestEndpoints";

/** The request's co-applicant cards as the shared card's drafts. A request
 *  from before the cards (three `co_applicant_*` columns) reads as one card. */
export function coApplicantDrafts(applicant: ServiceRequestDetail["applicant"]): CoOwnerDraft[] {
  const cards = applicant.co_applicants ?? [];
  if (cards.length === 0) {
    // A detail cached before the field (or a partial fixture) may carry none.
    const legacy: { name: string | null; email: string | null; phone: string | null } =
      applicant.co_applicant ?? { name: null, email: null, phone: null };
    if ((legacy.name ?? "").trim() === "") return [];
    return [
      {
        ...emptyCoOwner(),
        full_name: legacy.name ?? "",
        email: legacy.email ?? "",
        phone: legacy.phone ?? "",
      },
    ];
  }
  return hydrateCoOwners(
    cards.map((card) => ({
      full_name: card.full_name,
      relationship: card.relationship ?? "",
      phone: card.phone ?? "",
      email: card.email ?? "",
      contact_by: card.contact_by ?? "",
      date_of_birth: card.date_of_birth ?? "",
      responsible_for_bills: card.responsible_for_bills === true,
    })),
  ).map((row, index) => ({
    ...row,
    // ⊕ `DEF-CUS-10232` — the summary says an ID is on file (its mask).
    id_on_file: idOnFileMask(cards[index]?.ssn_last4, cards[index]?.driving_licence_last4),
  }));
}

/** The utility's own CUSTOMER fields the request holds a copy of. */
export function requestCustomerCustom(detail: ServiceRequestDetail): CustomFieldValues {
  return { ...(detail.custom_data?.customers ?? {}) };
}

/** Where the bill goes, from the request — `null` when it goes to the
 *  service address (or the request holds no parts). Reads the one name
 *  (`mailing_address`), falling back to the older parts a cached detail has. */
export function requestMailing(detail: ServiceRequestDetail): {
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
} | null {
  const mailing = detail.applicant.mailing_address;
  if (mailing === undefined) return null;
  const line1 = (mailing.line1 ?? "").trim();
  if (mailing.same || line1 === "") return null;
  return {
    line1,
    line2: (mailing.line2 ?? "").trim(),
    city: (mailing.city ?? "").trim(),
    state: (mailing.state ?? "").trim(),
    postal_code: (mailing.postal_code ?? "").trim(),
  };
}
