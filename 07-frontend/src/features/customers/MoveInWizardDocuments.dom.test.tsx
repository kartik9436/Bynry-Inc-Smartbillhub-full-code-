// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   PO ratification 2026-09-20, *"this is correct + Document links or
//           details"* — **CAPTURED DETAIL REACHES THE MOVE-IN BY REFERENCE,
//           DOCUMENTS INCLUDED** (decision log, `SEVEN PO RATIFICATIONS FROM
//           ONE SITTING`, §4). That entry states in its own words what it did
//           NOT verify: *"whether the document LINKS AND DETAIL — the files
//           themselves — are VISIBLE on a move-in surface. `MoveInWizard.tsx`
//           and `moveInRequestBlocks.tsx` both mention documents; mentioning
//           is not rendering. The check was assigned and died with its lane."*
// Defects:  DEF-CUS-6002 — what that check found, and this file is the half of
//           it that WORKS, locked so it cannot go quietly.
// Rules:    B14 rule 31 (no database id on screen) · rule 32 (a stated absence
//           is CLOSED by default) · CLAUDE.md hard-won law 2 (built is not
//           wired — and its mirror)
// ───────────────────────────────────────────────────────
//
// WHAT THIS ASSERTS, AND WHY IT MOUNTS THE WHOLE WIZARD TO ASSERT IT
// ------------------------------------------------------------------
// `moveInRequestBlocks.dom.test.tsx` already renders `RequestDocuments` on its
// own and proves it draws rows. That is the component working; it is not the
// SCREEN working. Between the two sit three things that can each fail
// silently and that no existing case asks about:
//
//   * `MoveInWizard` has to reach its `customer` step at all — on the
//     account-scoped road it renders a PENDING SHELL until the outgoing
//     account resolves, and the shell's step 2 is a sentence saying *"Choose
//     the unit above first"* with no customer form in it and therefore no
//     documents block. Measured: a mount whose account 404s reaches exactly
//     that shell, and every component-level assertion still passes.
//   * `serviceRequestId` has to survive the URL → state → step → prop chain
//     (`?request=` → `MoveInWizard:536` → `CustomerStep` → `:1569`). A prop
//     nothing passes is dead UI — hard-won law 2, four defects in one day.
//   * the block has to ASK for the right request, which is read here off a
//     recorded fetch rather than off a prop.
//
// ⚠ **THIS FILE DELIBERATELY DOES NOT ASSERT THAT THE FILES CANNOT BE OPENED.**
// They cannot — the rendered block carries ZERO anchors and ZERO buttons over
// two rows whose `file_present` is `true`, while the server has had
// `GET /service-requests/{id}/documents/{docId}/download` all along. That is
// `DEF-CUS-6002` and it is FILED, not frozen: writing `expect(anchors).toBe(0)`
// here would make the defect a rule and go red on the lane that fixes it.
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { MoveInWizard } from "./MoveInWizard";

const REQUEST_ID = "01a09540-7900-7dfa-abf4-b30b3c0fb6b8";
const ACCOUNT_ID = "01a0a444-5ad2-7e88-be8a-bdb8aa86c05e";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The account the new occupant is taking over from: CLOSED, which is what
 *  `unitFree` asks and what lets the wizard past its pending shell. */
const OUTGOING = {
  id: ACCOUNT_ID,
  account_no: "ACC-26-0044",
  status: "closed",
  status_behavior_class: "terminal",
  customer_name: "Prior, Pat",
  unit_id: "01a0b111-1111-7000-8000-000000000001",
  unit_label: "Unit 3",
  premise_id: "01a0b222-2222-7000-8000-000000000002",
  service_address: "88 Pine Vista",
  currency: "USD",
  contacts: [{ id: "c1", is_primary: true, full_name: "Prior, Pat", email: null, phone: null }],
  services: [],
  balance: { amount: "0.0000", display: "0.00", currency: "USD" },
};

/** ⚠ **BOTH ROWS CARRY `file_present: true`.** The beta's seeded rows do not
 *  (`DEF-CUS-5872`), and a fixture that copied the beta would prove only that
 *  a row with nothing behind it offers nothing — which is trivially true and
 *  is the wrong question. These are the rows a clerk would want to OPEN. */
const DOCUMENTS = {
  documents: [
    {
      id: "doc-1",
      doc_type: "government_id",
      what_it_proves: "Who they are",
      name: "Driving licence.pdf",
      uploaded_at: "2026-09-18T10:00:00Z",
      uploaded_by: "user-9",
      uploaded_by_name: "A. Clerk",
      size_bytes: 91234,
      original_size_bytes: null,
      attached: true,
      file_present: true,
      verification_state: "verified",
    },
    {
      id: "doc-2",
      doc_type: "proof_of_address",
      what_it_proves: "Where they live",
      name: "Lease.pdf",
      uploaded_at: "2026-09-18T10:05:00Z",
      uploaded_by: "user-9",
      uploaded_by_name: "A. Clerk",
      size_bytes: 55000,
      original_size_bytes: null,
      attached: true,
      file_present: true,
      verification_state: "unverified",
    },
  ],
  verified: 1,
  attached: 2,
  blocks_creation: false,
  blocks_approval: false,
  outstanding: false,
  checklist_request_type: null,
  checklist_required: [],
  checklist_unmet: [],
};

/** Mounts the REAL wizard at the REAL address, and records every URL it asks
 *  for — so *"the block queried the request the clerk arrived with"* is read
 *  off a request that was really made. */
function openMoveInAtCustomerStep(
  request: string,
  requestDetail?: Record<string, unknown>,
): { asked: string[] } {
  const asked: string[] = [];
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      asked.push(url);
      // `CR-171-BRC10` P2.25 — the move-in checklist the table locks rows for.
      if (url.includes("/move-ins/documents/required")) return json({ required: [] });
      if (url.includes("/documents")) return json(DOCUMENTS);
      if (requestDetail !== undefined && /\/service-requests\/[^/?]+(\?|$)/.test(url)) {
        return json(requestDetail);
      }
      if (/\/accounts\/[^/?]+(\?|$)/.test(url)) return json(OUTGOING);
      return json({ detail: "not found" }, 404);
    },
  } as never);
  const query = request === "" ? "" : `request=${request}&`;
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        {/* ⚠ **THE REAL `/:tenant/…` PATTERN.** `MoveInWizard` reads
            `params.accountId`, and a bare `MemoryRouter` with no such route
            leaves it empty — which silently switches the wizard onto its
            STANDALONE road, where the unit is picked rather than derived and
            step 2 never renders. That is `DEF-CWP-3925`'s shape exactly. */}
        <MemoryRouter
          // ⚠ The CUSTOMER step is 2 since `CR-171-BRC10` (2026-10-05, four
          // steps); it was 3 under the seven-step list (`DEF-CUS-9107`).
          initialEntries={[`/brazosbend/accounts/${ACCOUNT_ID}/move-in?${query}step=2`]}
        >
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId/move-in"
              element={<MoveInWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { asked };
}

// ⚠ RE-POINTED 2026-10-05 (`CR-171-BRC10` P2.25, lane MVI-WIZ-CUST). The
// request's documents are rows of the Customer step's ONE *Documents* table
// (images 33, 39) — `MoveInDocumentsTable`, not the old `RequestDocuments`
// block — and each file is now a control that OPENS it through the request's
// own content route, the half of `DEF-CUS-6002` this lane closes. The drawn
// columns are Document · Needed · File, so *what it proves* and the verdict
// are not on this step (the request page keeps both).
const docsTable = () => document.querySelector('[data-array="move-in-documents"]');

describe("PO 2026-09-20 §4 · an approved request's documents are VISIBLE on the move-in", () => {
  afterEach(cleanup);

  it("the clerk sees each document by NAME, and each one OPENS", async () => {
    openMoveInAtCustomerStep(REQUEST_ID);
    const files = await waitFor(() => {
      const found = [...document.querySelectorAll('[data-doc-file="request"]')];
      expect(found).toHaveLength(2);
      return found as HTMLButtonElement[];
    });
    expect(files.map((button) => button.textContent)).toEqual(["Driving licence.pdf", "Lease.pdf"]);
    // A real control, not text — `DEF-CUS-6002`'s "ZERO buttons" is over.
    for (const button of files) expect(button.tagName).toBe("BUTTON");
    expect(docsTable()?.textContent ?? "").toContain(i18n.t("customers.moveIn.customer.docs.title"));
  });

  it("it reads them THROUGH THE REQUEST, which is the whole of §4's claim", async () => {
    // `move_in_jobs` copies no field and names the request; this is that link
    // working on a screen. Read off a real fetch, not off a prop.
    const { asked } = openMoveInAtCustomerStep(REQUEST_ID);
    await waitFor(() => {
      expect(document.querySelectorAll('[data-doc-file="request"]')).toHaveLength(2);
    });
    expect(asked.some((url) => url.endsWith(`/service-requests/${REQUEST_ID}/documents`))).toBe(
      true,
    );
  });

  it("no request, no request rows — and the clerk can still add a document (P2.25)", async () => {
    // A move-in started from an ACCOUNT has no request behind it. Since
    // P2.25 a file uploaded here waits for Complete, so the table is there
    // with its *+ Add document* and none of a request's rows.
    openMoveInAtCustomerStep("");
    await waitFor(() => {
      expect(document.body.textContent ?? "").toContain(i18n.t("customers.moveIn.customer.whoTitle"));
      expect(document.getElementById("full_name")).not.toBeNull();
    });
    expect(document.querySelectorAll('[data-doc-file="request"]')).toHaveLength(0);
    expect(docsTable()?.querySelector('[data-array-action="add-document"]')).not.toBeNull();
  });

  it("the id it navigates by is NEVER the value a clerk reads (B14 rule 31)", async () => {
    openMoveInAtCustomerStep(REQUEST_ID);
    await waitFor(() => {
      expect(document.querySelectorAll('[data-doc-file="request"]')).toHaveLength(2);
    });
    const text = docsTable()?.textContent ?? "";
    expect(text).not.toContain(REQUEST_ID);
    expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/i);
  });
});

/** `DEF-CUS-6359` — an approved request's billing address becomes the
 *  move-in's mailing address, through REQ-FIX's `requestBillingAddress`. */
function requestWithBilling(same: boolean): Record<string, unknown> {
  return {
    header: { id: REQUEST_ID, request_no: "SR-26-0006" },
    // ⚠ `DEF-CUS-9107` — the applicant block AS THE SERVER SERVES IT
    // (`service_request_reads.py`). Since `6903ea191` (2026-10-02,
    // `DEF-CUS-9052`) the customer step reads `customer_match` and
    // `identifier` off it, and a fixture that left them out crashed the step
    // on `customer_match.customer_id`.
    applicant: {
      name: "Rivera, Ana",
      email: null,
      phone: "5125550100",
      date_of_birth: null,
      language: null,
      person_or_company: null,
      co_applicant: { name: null, email: null, phone: null },
      identifier: {
        ssn_present: false,
        ssn_last4: null,
        stored_encrypted: false,
        drivers_licence_last4: null,
        drivers_licence_present: false,
        drivers_licence_stored_encrypted: false,
      },
      acting_for_absence: { tracks: "DEF-638" },
      customer_match: {
        customer_id: null,
        tier: null,
        basis: null,
        confirmed_at: null,
        may_move_money: false,
      },
    },
    location_and_services: {
      billing_address_same: same,
      billing_line1_as_given: "PO Box 4471",
      billing_line2_as_given: "Suite 200",
      billing_city_as_given: "Round Rock",
      billing_state_as_given: "TX",
      billing_postal_code_as_given: "78664-1234",
    },
  };
}

describe("DEF-CUS-6359 · the request's billing address prefills the mailing address", () => {
  afterEach(cleanup);

  it("a request with its own billing address unchecks Same as service address and fills the US fields", async () => {
    openMoveInAtCustomerStep(REQUEST_ID, requestWithBilling(false));
    await waitFor(() => {
      expect((document.getElementById("full_name") as HTMLInputElement | null)?.value).toBe("Rivera, Ana");
    });
    expect((document.getElementById("mailing_same") as HTMLInputElement).checked).toBe(false);
    expect((document.getElementById("mailing_line1") as HTMLInputElement).value).toBe("PO Box 4471");
    expect((document.getElementById("mailing_line2") as HTMLInputElement).value).toBe("Suite 200");
    expect((document.getElementById("mailing_city") as HTMLInputElement).value).toBe("Round Rock");
    expect((document.getElementById("mailing_postal_code") as HTMLInputElement).value).toBe("78664-1234");
  });

  it("a request that said same as service leaves the box checked and draws no address", async () => {
    openMoveInAtCustomerStep(REQUEST_ID, requestWithBilling(true));
    await waitFor(() => {
      expect((document.getElementById("full_name") as HTMLInputElement | null)?.value).toBe("Rivera, Ana");
    });
    expect((document.getElementById("mailing_same") as HTMLInputElement).checked).toBe(true);
    expect(document.getElementById("mailing_line1")).toBeNull();
  });
});
