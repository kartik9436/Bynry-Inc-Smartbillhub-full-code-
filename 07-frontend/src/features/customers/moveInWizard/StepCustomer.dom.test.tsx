// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.22–P2.27, P2.35 (lane MVI-WIZ-CUST, 2026-10-05) —
//           the move-in Customer step, from images 33–40.
// Rules:    PO ruling 2026-10-05 (1) — only what our rule calls a match is
//           drawn (found / possible per Q5, CR §9.IDN as amended 2.537.0);
//           image 35's "Only the name matches." is NOT built · §9.IDN-2 (the
//           commit's keys; the kind is the holder's) · P2.25 (`documents`) ·
//           B14 rules 31, 33 · hard rule 2 (money shown, never summed here)
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { CoOwnerCards, emptyCoOwner } from "../CoOwnerCards";
import type { CoOwnerDraft } from "../CoOwnerCards";
import type { CustomerSearchResult, CustomerSearchRow } from "../customerEndpoints";
import { CustomerMatchPanel } from "../customerMatch/CustomerMatchPanel";
import { AccountTab } from "../moveDetail/AccountTab";
import { MoveInDocumentsTable } from "../MoveInDocumentsTable";
import type { MoveInDocDraft } from "../MoveInDocumentsTable";
import { emptyCustomerForm } from "../NewAccountWizard";
import type { CustomerForm } from "../NewAccountWizard";
import {
  emptyStepCustomerOwn,
  hydrateStepCustomerOwn,
  moveInCustomerProblem,
  searchQueryFor,
  stepCustomerPayload,
} from "./StepCustomer";
import type { StepCustomerOwn } from "./StepCustomer";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function wrap(node: ReactNode) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/move-ins/new"]}>
          <Routes>
            <Route path="/:tenant/move-ins/new" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

const nilesh = (patch: Partial<CustomerForm> = {}): CustomerForm => ({
  ...emptyCustomerForm(),
  account_type: "residential",
  customer_kind: "person",
  full_name: "Nilesh G",
  email: "nilesh@bynry.io",
  phone: "(732) 630-0285",
  dob: "2001-06-18",
  ssn: "210-80-9662",
  ...patch,
});

const kestrel = (patch: Partial<CustomerForm> = {}): CustomerForm => ({
  ...emptyCustomerForm(),
  account_type: "commercial",
  customer_kind: "company",
  full_name: "Kestrel Bakery LLC",
  tax_id: "47-1234567",
  ...patch,
});

const riya = (patch: Partial<CoOwnerDraft> = {}): CoOwnerDraft => ({
  ...emptyCoOwner(),
  full_name: "Riya G",
  relationship: "spouse",
  phone: "(732) 555-0144",
  contact_by: "text",
  responsible_for_bills: true,
  title: "should never be sent on a co-owner",
  ...patch,
});

const FOUND: CustomerSearchRow = {
  id: "01a0c000-0000-7000-8000-000000000231",
  customer_no: "CU-000231",
  display_name: "Nilesh G",
  kind: "person",
  verdict: "found",
  agreed: ["name", "date_of_birth", "ssn"],
  accounts: {
    count: 2,
    rows: [
      {
        id: "acc-412",
        account_no: "AC-2025-00412",
        status_code: "closed",
        status_name: "Closed",
        closed_at: "2026-08-31",
        address: { line1: "14 Mill Rd", unit_label: "Unit 2", city: "Ottumwa", state: "IA", postal_code: "52501" },
        balance: "84.200000",
        outstanding: "84.200000",
        confident: true,
      },
      {
        id: "acc-031",
        account_no: "AC-2026-00031",
        status_code: "active",
        status_name: "Active",
        closed_at: null,
        address: { line1: "220 Ash Ave", unit_label: null, city: "Ottumwa", state: "IA", postal_code: "52501" },
        balance: "0.000000",
        outstanding: "0.000000",
        confident: true,
      },
    ],
    outstanding_total: "84.200000",
    currency: "USD",
    available: true,
  },
  company: null,
};

function panel(props: Partial<Parameters<typeof CustomerMatchPanel>[0]>) {
  return render(
    wrap(
      <CustomerMatchPanel
        result={null}
        pending={false}
        failed={false}
        linkedId={null}
        linkedRow={null}
        dismissed={[]}
        onLink={() => undefined}
        onUnlink={() => undefined}
        onNotThem={() => undefined}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        {...props}
      />,
    ),
  );
}

afterEach(cleanup);

// ═══════════════════════════════════════════════════════════════════════════
// P2.23 — the search's answer (images 34, 36, 37)
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.23 · Search customer ID draws only what our rule calls a match", () => {
  // Lane CF-1 (2026-10-18) — the stacked cards are ONE results table now
  // (customer-forms drawing set, images 01, 10, 11); the full table is
  // proved in `customerForm/customerMatchTable.dom.test.tsx`.
  it("image 34 → image 01: EXISTING CUSTOMER, what agreed, the accounts and what is owed", () => {
    const result: CustomerSearchResult = { result: "found", count: 1, customers: [FOUND] };
    panel({ result });
    const row = document.querySelector('[data-match-row="found"]') as HTMLElement;
    expect(row).not.toBeNull();
    const text = row.textContent ?? "";
    expect(text).toContain("Nilesh G");
    expect(text).toContain("CU-000231");
    expect(text).toContain("2 · 1 open");
    expect(text).toContain("$84.20");
    const said = row.querySelector("[data-match-mark]")?.getAttribute("aria-label") ?? "";
    expect(said).toContain(t("customers.moveIn.customer.match.found"));
    // `Intl.ListFormat` writes the locale's own list (en-US: the serial comma).
    expect(said).toMatch(/Name, date of birth,? and SSN match\./);
    fireEvent.click(
      screen.getByRole("button", { name: t("customers.moveIn.customer.match.showAccounts", { name: "Nilesh G · CU-000231" }) }),
    );
    const accounts = document.querySelector("[data-match-accounts]")?.textContent ?? "";
    expect(accounts).toContain("AC-2025-00412");
    expect(accounts).toContain("14 Mill Rd · Unit 2");
    expect(accounts).toContain("Closed 08/31/2026");
    expect(accounts).toContain("$84.20 due");
    expect(accounts).toContain("$0.00");
    expect(
      screen.getByRole("button", { name: t("customers.moveIn.customer.match.linkName", { name: "Nilesh G · CU-000231" }) }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: t("customers.moveIn.customer.match.notThemName", { name: "Nilesh G · CU-000231" }) }),
    ).toBeInTheDocument();
    // B14 rule 31 — the handle is never what a clerk reads.
    expect(document.body.textContent ?? "").not.toContain(FOUND.id);
  });

  it("a possible match (Q5: name AND date of birth) says so — and never 'Only the name matches.'", () => {
    const possible: CustomerSearchRow = { ...FOUND, verdict: "possible", agreed: ["name", "date_of_birth"] };
    panel({ result: { result: "possible", count: 1, customers: [possible] } });
    const said = document.querySelector("[data-match-mark]")?.getAttribute("aria-label") ?? "";
    expect(said).toContain(t("customers.moveIn.customer.match.possible"));
    expect(said).toContain("Name and date of birth match.");
    expect(document.body.textContent ?? "").not.toMatch(/only the name/i);
  });

  it("image 36: NEW CUSTOMER when nobody our rule shows — and when every one was 'Not them'", () => {
    panel({ result: { result: "new", count: 0, customers: [] } });
    expect(document.querySelector('[data-customer-match="new"]')?.textContent).toContain(
      t("customers.moveIn.customer.match.newLine"),
    );
    cleanup();
    panel({ result: { result: "found", count: 1, customers: [FOUND] }, dismissed: [FOUND.id] });
    expect(document.querySelector('[data-customer-match="new"]')).not.toBeNull();
    expect(document.querySelector('[data-match-block="found"]')).toBeNull();
  });

  it("nothing to judge (result null) is not 'new' — it asks for an ID", () => {
    panel({ result: { result: null, count: 0, customers: [] } });
    expect(document.querySelector('[data-customer-match="nothing"]')?.textContent).toBe(
      t("customers.moveIn.customer.match.needMore"),
    );
    expect(document.querySelector('[data-customer-match="new"]')).toBeNull();
  });

  it("image 37: LINKED with Unlink; a link read back from a draft draws no week-old money", () => {
    let unlinked = false;
    panel({ linkedId: FOUND.id, linkedRow: FOUND, onUnlink: () => (unlinked = true) });
    expect(document.querySelector('[data-match-block="linked"]')?.textContent).toContain(
      t("customers.moveIn.customer.match.linked"),
    );
    fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.customer.match.unlink") }));
    expect(unlinked).toBe(true);
    cleanup();
    const parked = hydrateStepCustomerOwn(JSON.parse(JSON.stringify({ linked: FOUND })));
    expect(parked.linked?.accounts).toBeNull();
    panel({ linkedId: FOUND.id, linkedRow: parked.linked });
    expect(document.body.textContent ?? "").not.toContain("$84.20");
  });

  it("the question carries the kind's own identifiers, and none without a kind", () => {
    expect(searchQueryFor(nilesh())).toEqual({
      kind: "person",
      name: "Nilesh G",
      date_of_birth: "2001-06-18",
      ssn: "210-80-9662",
      phone: "(732) 630-0285",
    });
    expect(searchQueryFor(kestrel())).toEqual({ kind: "company", name: "Kestrel Bakery LLC", tax_id: "47-1234567" });
    expect(searchQueryFor(nilesh({ customer_kind: "" }))).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// The commit body (§9.IDN-2, §9.1, P2.25)
// ═══════════════════════════════════════════════════════════════════════════
describe("what the Customer step adds to Complete", () => {
  it("a person: the link, Contact by, co-owners with co-owner fields only, staged documents", () => {
    const own: StepCustomerOwn = {
      ...emptyStepCustomerOwn(),
      contact_by: "email",
      linked: FOUND,
      co_owners_on: true,
      co_owners: [riya()],
      documents: [
        { key: "d1", doc_type: "tenancy_agreement_or_deed", card_id: "card-1", name: "deed.pdf" },
        { key: "d2", doc_type: "proof_of_identity", card_id: "", name: "" },
      ],
      // a company's facts typed and then the kind switched: never sent
      trading_as: "Nilesh Lawn Care",
      po_number: "PO-1",
    };
    const body = stepCustomerPayload(nilesh(), own);
    expect(body.customer).toMatchObject({ customer_id: FOUND.id, display_name: "Nilesh G", kind: "person" });
    expect(body.contact).toMatchObject({ full_name: "Nilesh G", contact_by: "email", is_primary: true });
    expect(body.co_owners).toEqual([
      {
        full_name: "Riya G",
        relationship: "spouse",
        phone: "(732) 555-0144",
        contact_by: "text",
        responsible_for_bills: true,
      },
    ]);
    expect(body.documents).toEqual([{ card_id: "card-1", doc_type: "tenancy_agreement_or_deed" }]);
    for (const key of ["company", "po_number", "bills_go_to"]) expect(body).not.toHaveProperty(key);
  });

  it("a company: the contact person, its own facts, PO, bills go to, officers with officer fields only", () => {
    const own: StepCustomerOwn = {
      ...emptyStepCustomerOwn(),
      trading_as: "Kestrel Bakery",
      business_type: "llc",
      registered_in: "IA",
      contact: { full_name: "Nilesh G", job_title: "Owner", email: "nilesh@bynry.io", phone: "(732) 630-0285", contact_by: "email" },
      po_number: "PO-7781",
      bills_to_contact: true,
      co_owners_on: true,
      co_owners: [
        { ...emptyCoOwner(), full_name: "Arun Mehta", title: "Managing member", ownership_pct: "50", signs_for_company: true, relationship: "spouse" },
      ],
    };
    const body = stepCustomerPayload(kestrel(), own);
    expect(body.contact).toEqual({
      full_name: "Nilesh G",
      job_title: "Owner",
      email: "nilesh@bynry.io",
      phone: "(732) 630-0285",
      contact_by: "email",
      is_primary: true,
    });
    expect(body.company).toEqual({ trading_as: "Kestrel Bakery", business_type: "llc", registered_in: "IA" });
    expect(body.po_number).toBe("PO-7781");
    expect(body.bills_go_to).toBe("contact_person");
    expect(body.co_owners).toEqual([
      { full_name: "Arun Mehta", title: "Managing member", ownership_pct: "50", signs_for_company: true },
    ]);
    expect(stepCustomerPayload(kestrel(), { ...own, bills_to_contact: false }).bills_go_to).toBe("account_holder");
    // no link → the wizard's own `customer` block stands (the step sends none)
    expect(body).not.toHaveProperty("customer");
  });

  it("an untouched step adds nothing", () => {
    expect(stepCustomerPayload(nilesh(), emptyStepCustomerOwn())).toEqual({});
  });
});

describe("what holds Continue on step 2", () => {
  it("names the first missing thing, in panel order", () => {
    const own = emptyStepCustomerOwn();
    expect(moveInCustomerProblem(nilesh({ full_name: "" }), own, false)).toBe("customers.moveIn.customer.problem.fullName");
    expect(moveInCustomerProblem(nilesh({ phone: "" }), own, false)).toBe("customers.moveIn.customer.problem.phone");
    expect(moveInCustomerProblem(nilesh(), own, false)).toBeNull();
    expect(moveInCustomerProblem(kestrel(), own, false)).toBe("customers.moveIn.customer.problem.businessType");
    expect(moveInCustomerProblem(kestrel(), { ...own, business_type: "llc" }, false)).toBe(
      "customers.moveIn.customer.problem.contact",
    );
    expect(
      moveInCustomerProblem(nilesh(), { ...own, co_owners_on: true, co_owners: [riya({ full_name: "" })] }, false),
    ).toBe("customers.moveIn.customer.problem.coOwnerName");
  });

  it("a linked customer IS the identity — no identifier is demanded", () => {
    const bare = nilesh({ ssn: "", driving_licence: "", dob: "" });
    const own = emptyStepCustomerOwn();
    expect(moveInCustomerProblem({ ...bare, phone: "" }, own, false)).toBe("customers.moveIn.customer.problem.phone");
    expect(moveInCustomerProblem(kestrel({ tax_id: "" }), { ...own, business_type: "llc" }, false)).not.toBeNull();
    expect(
      moveInCustomerProblem(kestrel({ tax_id: "" }), {
        ...own,
        business_type: "llc",
        linked: { ...FOUND, kind: "company" },
        contact: { full_name: "N", job_title: "", email: "n@x.io", phone: "(732) 555-0100", contact_by: "" },
      }, false),
    ).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P2.24 — co-owners / owners and officers (images 33, 38, 40)
// ═══════════════════════════════════════════════════════════════════════════
/** A card's open/close control — the one carrying `aria-expanded`, not its ✕. */
function toggleFor(name: RegExp): HTMLElement {
  const found = screen
    .getAllByRole("button", { name })
    .find((button) => button.hasAttribute("aria-expanded"));
  if (found === undefined) throw new Error(`no card toggle named ${String(name)}`);
  return found;
}

describe("P2.24 · one component, two kinds", () => {
  function cards(kind: "co_owner" | "officer", rows: CoOwnerDraft[], enabled = true) {
    let latest = rows;
    let on = enabled;
    render(
      wrap(
        <CoOwnerCards
          kind={kind}
          enabled={enabled}
          onEnabledChange={(next) => (on = next)}
          rows={rows}
          onChange={(next) => (latest = next)}
          t={t}
          dateFormat="MM/DD/YYYY"
          timeZone="America/Chicago"
          showErrors={false}
        />,
      ),
    );
    return { latest: () => latest, on: () => on };
  }

  it("ticking Has co-owners opens the first card", () => {
    const state = cards("co_owner", [], false);
    fireEvent.click(screen.getByLabelText(t("customers.moveIn.customer.coOwners.tick")));
    expect(state.on()).toBe(true);
    expect(state.latest()).toHaveLength(1);
  });

  it("a co-owner card: Relationship, the summary line, Photo ID held until the account exists", () => {
    cards("co_owner", [riya()]);
    const text = document.body.textContent ?? "";
    expect(text).toContain(t("customers.moveIn.customer.coOwners.added", { count: 1 }));
    expect(text).toContain("Riya G");
    expect(text).toContain("Spouse · (732) 555-0144 · Responsible for bills · No ID");
    fireEvent.click(toggleFor(/Riya G/));
    expect(document.getElementById("co_owner_0_relationship")).not.toBeNull();
    expect(document.getElementById("co_owner_0_title")).toBeNull();
    const photo = document.getElementById("co_owner_0_photo") as HTMLButtonElement;
    expect(photo.disabled).toBe(true);
    expect(photo.title).toBe(t("customers.moveIn.customer.coOwner.photoLater"));
  });

  it("an officer card: Title and Ownership %, no Relationship; image 40's summary", () => {
    cards("officer", [{ ...emptyCoOwner(), full_name: "Arun Mehta", title: "Managing member", ownership_pct: "50", signs_for_company: true }]);
    expect(document.body.textContent ?? "").toContain("Managing member · 50% · Signs · No ID");
    fireEvent.click(toggleFor(/Arun Mehta/));
    expect(document.getElementById("officer_0_title")).not.toBeNull();
    expect(document.getElementById("officer_0_ownership_pct")).not.toBeNull();
    expect(document.getElementById("officer_0_relationship")).toBeNull();
    expect(document.body.textContent ?? "").toContain(t("customers.moveIn.customer.officers.title"));
  });

  it("Remove <name>, inside the opened card (image 12), removes the card it is on", () => {
    const state = cards("co_owner", [riya(), riya({ full_name: "Dev G" })]);
    fireEvent.click(toggleFor(/Riya G/));
    fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.customer.coOwners.remove", { name: "Riya G" }) }));
    expect(state.latest().map((row) => row.full_name)).toEqual(["Dev G"]);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P2.25 — the Documents table (images 33, 39)
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.25 · the documents table locks required rows and stages uploads", () => {
  function table(rows: MoveInDocDraft[], required: string[]) {
    const asked: string[] = [];
    let latest = rows;
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL) => {
        const url = String(input);
        asked.push(url);
        if (url.includes("/move-ins/documents/required")) return json({ required });
        if (url.endsWith("/move-ins/documents")) {
          return json({ card_id: "card-9", doc_type: "tenancy_agreement_or_deed", name: "deed.pdf", size_bytes: 2064, content_type: "application/pdf" }, 201);
        }
        return json({ detail: "not found" }, 404);
      },
    } as never);
    const view = render(
      wrap(
        <MoveInDocumentsTable
          rows={rows}
          onChange={(next) => (latest = next)}
          serviceRequestId=""
          t={t}
          client={client}
        />,
      ),
    );
    return { asked, latest: () => latest, view };
  }

  it("a required type is a locked row with Upload; the fact counts what is missing", async () => {
    table([], ["proof_of_identity", "tenancy_agreement_or_deed"]);
    await waitFor(() => {
      expect(document.querySelectorAll('[data-editable-table="move-in-documents"] tbody tr').length).toBeGreaterThanOrEqual(2);
    });
    const text = document.body.textContent ?? "";
    expect(text).toContain(t("customers.serviceRequest.docType.proof_of_identity"));
    expect(text).toContain(t("customers.moveIn.customer.docs.missing", { count: 2 }));
    expect(text).toContain(t("customers.moveIn.customer.docs.stays"));
    // RATIONALE is zero words (B14 rule 33): the drawn "Required ones come
    // from Settings › Configure" is not on screen.
    expect(text).not.toMatch(/Settings/);
    const removes = [...document.querySelectorAll("[data-remove-row]")] as HTMLButtonElement[];
    expect(removes.every((button) => button.disabled)).toBe(true);
  });

  it("an upload stages the file and the row keeps its card", async () => {
    const state = table([], ["tenancy_agreement_or_deed"]);
    const input = await waitFor(() => {
      const found = document.querySelector('input[type="file"]');
      expect(found).not.toBeNull();
      return found as HTMLInputElement;
    });
    const file = new File(["%PDF-1.7"], "deed.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => {
      expect(state.latest()).toEqual([
        expect.objectContaining({ doc_type: "tenancy_agreement_or_deed", card_id: "card-9", name: "deed.pdf" }),
      ]);
    });
    expect(state.asked.some((url) => url.endsWith("/move-ins/documents"))).toBe(true);
  });

  it("an added row offers only types not already listed", async () => {
    table([{ key: "x", doc_type: "", card_id: "", name: "" }], ["proof_of_identity"]);
    const select = await waitFor(() => {
      const found = document.querySelector('[data-cell="doc-type"]');
      expect(found).not.toBeNull();
      return found as HTMLSelectElement;
    });
    await waitFor(() => {
      const values = [...select.options].map((option) => option.value);
      expect(values).not.toContain("proof_of_identity");
      expect(values).toContain("tenancy_agreement_or_deed");
    });
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P2.24's second half — the photo ID on the move-in's Account tab (image 25)
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.24 · a co-owner with No ID gets an Upload on the Account tab (law 2: it is mounted)", () => {
  function accountTab(photoId: boolean) {
    const posted: string[] = [];
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST") {
          posted.push(url);
          return json({ co_owner_id: "co-1", photo_id: true, document_id: "doc-1" }, 201);
        }
        return json({ detail: "not found" }, 404);
      },
    } as never);
    render(
      wrap(
        <AccountTab
          accountId="acc-1"
          coOwners={[
            {
              id: "co-1",
              kind: "co_owner",
              full_name: "Riya G",
              relationship: "Spouse",
              title: null,
              phone: "(732) 555-0144",
              email: null,
              contact_by: "text",
              responsible_for_bills: true,
              photo_id: photoId,
            },
          ]}
          regional={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" } as never}
          client={client}
        />,
      ),
    );
    return posted;
  }

  it("No ID → the upload is on the row, addressed by the row's handle, and posts to the door", async () => {
    const posted = accountTab(false);
    const cell = document.querySelector('[data-co-owner-photo-upload="co-1"]');
    expect(cell).not.toBeNull();
    const input = cell?.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toHaveAccessibleName(t("customers.moveIn.customer.coOwner.photoFor", { name: "Riya G" }));
    fireEvent.change(input, { target: { files: [new File(["x"], "riya-id.jpg", { type: "image/jpeg" })] } });
    await waitFor(() => {
      expect(posted.some((url) => url.endsWith("/accounts/acc-1/co-owners/co-1/photo-id"))).toBe(true);
    });
    // B14 rule 31 — the handle is the address, never the text.
    expect(document.body.textContent ?? "").not.toContain("co-1");
  });

  it("an ID on file → no upload", () => {
    accountTab(true);
    expect(document.querySelector("[data-co-owner-photo-upload]")).toBeNull();
  });
});
