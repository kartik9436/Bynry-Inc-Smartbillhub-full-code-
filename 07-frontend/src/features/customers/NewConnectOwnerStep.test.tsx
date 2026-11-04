// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-5467 — step 1 could not search for an existing customer, so
//          every build minted a new one and the clerk retyped what was already
//          on file. With DEF-MET-5093 / DEF-MET-5438, the party kind and the
//          identifier the account door refuses to open without.
// Rules:   BR-CUS-1022 (evidence is per kind and the wrong one is refused BY
//          NAME) · BR-CUS-1023 (the minimum to MINT a number) · BR-CUS-1024
//          (match first; and a phone MINTS but may not MATCH) · BR-CUS-019 (the
//          clerk's explicit answer wins) · B14 rule 31 (no database id on
//          screen) · B14 rule 33 (on-screen text capped by what it is for)
// ⚠ WHY THIS FILE EXISTS RATHER THAN CASES IN `NewConnectWizard.test.tsx`:
//          five lanes are editing that file at once and it was left
//          type-broken twice on 2026-09-16 alone. A step with its own file
//          gets its own test file (CLAUDE.md law 11).
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { commitPlanOf, emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft, OwnerForm } from "./newConnectDraft";
import {
  OwnerScopeStep,
  customerFinderLabel,
  draftDocumentRows,
  ownerBirthDateProblem,
  ownerHasABirthDate,
  ownerIdentityShortfall,
  ownerKindOptions,
  ownerShortfallSentence,
} from "./NewConnectOwnerStep";
import { searchQueryFor } from "./moveInWizard/StepCustomer";
import { ownerToCustomer } from "./NewConnectCustomerForm";
import type { CustomerRow } from "./customerEndpoints";

/** The catalogue is not under test here, so the DEFAULT is what renders — which
 *  is also what a clerk sees before a key is faned in. */
const t = ((key: string, opts?: { defaultValue?: string }) =>
  opts?.defaultValue ?? key) as never;

/** ⚠ **A REAL CUSTOMER ROW, WITH A UUID THAT MUST NEVER REACH THE SCREEN.**
 *  `id` is deliberately a plausible uuid so the rule-31 assertion below is a
 *  real one rather than a check that an empty string is absent. */
function customerRow(over: Partial<CustomerRow> = {}): CustomerRow {
  return {
    id: "6f1d4c2a-9b37-4f58-bb21-0e7c8a5d3f10",
    customer_no: "C-00902",
    display_name: "Vasquez, M.",
    kind: "person",
    external_ref: null,
    phone: "(512) 555-0197",
    identity: {
      date_of_birth: null,
      ssn_held: true,
      ssn_last4: "6789",
      driving_licence_held: false,
      driving_licence_last4: null,
      tax_id_held: false,
      tax_id_last4: null,
    },
    account_count: 1,
    accounts: [],
    ...over,
  };
}

function ownerOf(over: Partial<OwnerForm>): OwnerForm {
  return { ...emptyDraft().owner, ...over };
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
 * `/:tenant/...` route leaves `useParams().tenant` undefined, so every address a
 * component builds comes out protocol-relative — a string `toContain` reads as
 * perfectly good, and it cost the customer portal six of its eight front-page
 * doors (CLAUDE.md hard-won law 2).
 */
function renderStep(draft: NewConnectDraft): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/connections/new?step=1"]}>
        <Routes>
          <Route
            path="/:tenant/connections/new"
            element={
              <OwnerScopeStep
                draft={draft}
                onPatch={() => undefined}
                t={t}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// `CR-164-BRC10` item 11 — THE SEARCH BOX IS GONE; STEP 1 LOOKS THE OWNER UP
// ══════════════════════════════════════════════════════════════════════════
// PO ruling Q5 (2026-10-02): an SSN or licence (a company's Tax ID) is a match,
// a name with a date of birth is a possible match, a name or a date alone is
// nothing. These cases replace the `DEF-CUS-5467` search-box cases, whose
// subject the PO removed; the RULE they guarded (BR-CUS-1024: a phone never
// matches) is asserted below on the lookup's own question.
// ⊕ **LANE CF-1 (2026-10-18) — THE AUTOMATIC LOOKUP IS REPLACED BY MOVE-IN'S
// *SEARCH CUSTOMER ID*** (drawing set `customer-forms-2026-10-18`, image 06:
// *"Search customer ID button (today an automatic card)"*, PO *"Move in UI is
// latest and correct"*). The cases that asserted the automatic card are
// superseded; the RULE they guarded — a phone never MATCHES (BR-CUS-1024) and
// an unstated kind is never judged (BR-CUS-1022) — is now the server's search
// (`owner_lookup.search_evidence`), and the question asked is Move-in's own.
describe("lane CF-1 — step 1 has Move-in's Search customer ID", () => {
  it("draws the button in the Identity panel and no automatic card", () => {
    const html = renderStep({ ...emptyDraft(), owner: ownerOf({ partyKind: "person" }) });
    expect(html).toContain("data-search-customer-id");
    expect(html).not.toContain("data-owner-match");
    expect(html).not.toContain('data-step-content="customer-match"');
  });

  it("asks Move-in's question of what the clerk typed", () => {
    expect(searchQueryFor(ownerToCustomer(ownerOf({ ssn: "123-45-6789" })))).toBeNull();
    expect(
      searchQueryFor(ownerToCustomer(ownerOf({ partyKind: "person", name: "Vasquez, M.", ssn: "123-45-6789" }))),
    ).toEqual({ kind: "person", name: "Vasquez, M.", ssn: "123-45-6789" });
    expect(
      searchQueryFor(ownerToCustomer(ownerOf({ partyKind: "company", name: "Ridge LLC", taxId: "74-1234567" }))),
    ).toEqual({ kind: "company", name: "Ridge LLC", tax_id: "74-1234567" });
    // A company's SSN box does not exist, so a leftover SSN is never sent.
    expect(
      searchQueryFor(ownerToCustomer(ownerOf({ partyKind: "company", ssn: "123-45-6789" }))),
    ).toEqual({ kind: "company" });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-9193` / `DEF-CUS-9194` — PO ruling Q4
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-9193 — a date of birth in the future or under 18 is refused", () => {
  const today = "2026-10-02";
  it("refuses a future date", () => {
    expect(ownerBirthDateProblem("2026-10-03", today)).toBe("customers.newConnect.step1.dobFuture");
  });
  it("refuses an owner who turns 18 tomorrow and accepts one who turns 18 today", () => {
    expect(ownerBirthDateProblem("2008-10-03", today)).toBe("customers.newConnect.step1.dobUnder18");
    expect(ownerBirthDateProblem("2008-10-02", today)).toBeNull();
  });
  it("leaves a blank date to the identity rule", () => {
    expect(ownerBirthDateProblem("", today)).toBeNull();
  });
  it("shows the refusal on the field", () => {
    const html = renderStep({
      ...emptyDraft(),
      owner: ownerOf({ partyKind: "person", dateOfBirth: "2099-01-01" }),
    });
    expect(html).toContain("Date of birth is in the future.");
  });
});

describe("DEF-CUS-9261 — a company has no date of birth", () => {
  // Accounts blueprint p215 (company picked) draws no Date of birth; Tax ID
  // already replaces the SSN for a company.
  it("draws no Date of birth once Company is chosen, and draws it for a person", () => {
    const company = renderStep({ ...emptyDraft(), owner: ownerOf({ partyKind: "company" }) });
    // ⊕ lane CF-1 — the shared Who panel's own ids (`dob`), image 06.
    expect(company).not.toContain('id="dob"');
    const person = renderStep({ ...emptyDraft(), owner: ownerOf({ partyKind: "person" }) });
    expect(person).toContain('id="dob"');
  });
  it("applies the under-18 and future checks to a person only", () => {
    expect(ownerHasABirthDate({ partyKind: "company" })).toBe(false);
    expect(ownerHasABirthDate({ partyKind: "person" })).toBe(true);
    expect(ownerHasABirthDate({ partyKind: "" })).toBe(true);
  });
});

describe("DEF-CUS-9194 — the SSN and the licence are masked", () => {
  it("renders both as password inputs that the browser does not offer to save", () => {
    const html = renderStep({ ...emptyDraft(), owner: ownerOf({ partyKind: "person" }) });
    // ⊕ lane CF-1 — the shared Identity panel's ids.
    for (const id of ["ssn", "driving_licence"]) {
      const at = html.indexOf(`id="${id}"`);
      expect(at).toBeGreaterThan(-1);
      const tag = html.slice(html.lastIndexOf("<", at), html.indexOf(">", at) + 1);
      expect(tag).toContain('type="password"');
      // ⊕ `DEF-CUS-10044` — `new-password`, NOT `off`: browsers ignore `off`
      // on a password input and filled the clerk's saved login into it.
      expect(tag).toContain('autoComplete="new-password"');
      expect(tag).not.toContain('autoComplete="off"');
    }
  });
});

describe("DEF-CUS-9192 — Owner type is the utility's own list", () => {
  it("offers the served rows by name and value", () => {
    const options = ownerKindOptions(
      [
        { code: "owner_occupier", name: "Owner-occupier" },
        { code: "landlord", name: "Landlord" },
        { code: "hoa", name: "HOA", active: false },
      ],
      "",
      t,
    );
    expect(options).toEqual([
      { value: "owner_occupier", label: "Owner-occupier" },
      { value: "landlord", label: "Landlord" },
    ]);
  });
  it("keeps a code stored before the change and names it", () => {
    const options = ownerKindOptions([{ code: "landlord", name: "Landlord" }], "builder_developer", t);
    expect(options.at(-1)).toEqual({ value: "builder_developer", label: "Builder or developer" });
  });
  it("no longer offers the four hand-typed codes on an empty list", () => {
    expect(ownerKindOptions([], "", t)).toEqual([]);
  });
});

describe("DEF-CUS-5467 — an attached customer is shown, and is not retyped", () => {
  const attached = () => ({
    ...emptyDraft(),
    owner: ownerOf({
      name: "Vasquez, M.",
      partyKind: "person",
      matchedCustomerId: "6f1d4c2a-9b37-4f58-bb21-0e7c8a5d3f10",
      matchedCustomerNo: "C-00902",
    }),
  });

  it("shows the customer's details, which is the point of the ruling", () => {
    // PO 2026-09-12: *"should show the details of the customer account with the
    // proper customer details"*. A bare "attached" is how the wrong customer
    // gets billed quietly.
    // ⊕ `CR-164-BRC10` — the lookup's own line now: *Using C-00902 · name*.
    // ⊕ lane CF-1 — Move-in's one-line *Linked* state (image 11).
    const html = renderStep(attached());
    expect(html).toContain('data-customer-match="linked"');
    expect(html).toContain("C-00902");
    expect(html).toContain("Vasquez, M.");
  });

  it("never prints the matched customer's database id", () => {
    const html = renderStep(attached());
    expect(html).not.toContain("6f1d4c2a-9b37-4f58-bb21-0e7c8a5d3f10");
  });

  it("asks for no identifier at all while a customer is attached", () => {
    // *"do not retype"* — and it is the server's rule too:
    // `refuse_account_without_identity` returns early on a named customer.
    // ⊕ lane CF-1 — Move-in keeps the Identity panel drawn (image 11), so the
    // rule is asserted where it lives: nothing is required of the owner.
    expect(ownerIdentityShortfall(attached().owner)).toBeNull();
  });

  it("offers a way back out of the attachment", () => {
    // ⊕ lane CF-1 — the Linked line's *Unlink* icon (Move-in's, image 11).
    const html = renderStep(attached());
    const linked = html.slice(html.indexOf('data-customer-match="linked"'));
    expect(linked).toContain("<button");
    expect(linked).toMatch(/aria-label="[^"]+"/);
  });
});

describe("DEF-MET-5438 — the party kind is asked by name and never derived", () => {
  it("is not pre-selected, because unstated is a real answer", () => {
    // BR-CUS-1022: it decides which identifier counts, and a default of
    // `person` would judge a developer by a date of birth it has not got.
    expect(emptyDraft().owner.partyKind).toBe("");
  });

  it("is not derived from the owner CLASSIFICATION", () => {
    // All four of OWNER_KINDS are refused by `_validate_customer_kind` by name,
    // and a landlord is routinely a person and routinely a company.
    const draft = { ...emptyDraft(), owner: ownerOf({ kind: "landlord" }) };
    expect(draft.owner.partyKind).toBe("");
    expect(commitPlanOf(draft, null).owner.party_kind).toBeUndefined();
  });

  it("asks a company for its Tax ID and a person for the other three", () => {
    const company = renderStep({
      ...emptyDraft(),
      owner: ownerOf({ name: "Ridge Property LLC", partyKind: "company" }),
    });
    // ⊕ **THE ASSERTION IS THE FIELD AND NOT THE WORDS, 2026-09-29.** The
    // drawing's Gov-ID panel carries the line *"A company gives Tax ID
    // instead."* on BOTH branches, so a page-wide `toContain("Tax ID")` now
    // passes for a person too — a check that can no longer fail (law 7). The
    // BOX is what the rule is about.
    // ⊕ lane CF-1 — the shared form's ids.
    expect(company).toContain('id="tax_id"');
    expect(company).not.toContain('id="ssn"');

    const person = renderStep({
      ...emptyDraft(),
      owner: ownerOf({ name: "Ibarra, M.", partyKind: "person" }),
    });
    expect(person).toContain('id="ssn"');
    expect(person).toContain('id="driving_licence"');
    expect(person).not.toContain('id="tax_id"');
  });
});

describe("BR-CUS-1023 — what earns the owner an account, stated where they type", () => {
  it("accepts a landlord who gave only a phone number", () => {
    // The decision log's own worked case (2026-09-16 §2): Marisol Ibarra,
    // landlord, phone 555-0182, no other identifier — the master account opens.
    expect(
      ownerIdentityShortfall(
        ownerOf({ name: "Ibarra, M.", partyKind: "person", phone: "555-0182" }),
      ),
    ).toBeNull();
  });

  it("refuses a company on the SAME phone and no Tax ID", () => {
    // The other half of the same worked pair: a phone does not mint a number
    // for a company.
    expect(
      ownerIdentityShortfall(
        ownerOf({
          name: "Brazos Bend Developments LLC",
          partyKind: "company",
          phone: "555-0182",
        }),
      ),
    ).toBe("customers.account.identity_required_company");
  });

  it("names the missing dropdown rather than the missing evidence", () => {
    // BR-CUS-1022: evidence against an unstated kind cannot be assessed at all,
    // so one missing thing gets one sentence.
    expect(ownerIdentityShortfall(ownerOf({ name: "Ibarra, M." }))).toBe(
      "customers.account.identity_kind_required",
    );
  });

  it("asks for nothing once a customer is attached", () => {
    expect(
      ownerIdentityShortfall(
        ownerOf({
          name: "Vasquez, M.",
          partyKind: "person",
          matchedCustomerId: "6f1d4c2a-9b37-4f58-bb21-0e7c8a5d3f10",
          matchedCustomerNo: "C-00902",
        }),
      ),
    ).toBeNull();
  });

  it("keeps the shortfall OFF the screen and hands it to Continue instead", () => {
    // ⊕ **AMENDED 2026-09-28 (PO reported bug 1).** This case asserted that
    // *"Say person or company."* was rendered beside the fields the moment the
    // step opened — so an untouched form already carried a refusal. The
    // redesign drawing lists *"Name the owner first."* under *Removed from this
    // step* with the note *"shown only as an error on Continue"*, and the
    // sibling sentences move with it.
    //
    // **The case is amended rather than deleted because the rule it guards has
    // not moved**: the words still exist, still fit B14 rule 33, and are still
    // what a clerk is shown — by `WizardStepVerdict`, at the press. So this
    // asserts BOTH halves: nothing on the screen, and the exact sentence
    // available to Continue.
    const html = renderStep({
      ...emptyDraft(),
      owner: ownerOf({ name: "Ibarra, M." }),
    });
    expect(html).not.toContain("Say person or company.");
    expect(html).not.toContain("Name the owner first.");

    const shortfall = ownerIdentityShortfall(ownerOf({ name: "Ibarra, M." }));
    expect(shortfall).not.toBeNull();
    expect(ownerShortfallSentence(shortfall ?? "", t)).toBe("Say person or company.");
    expect(
      ownerShortfallSentence(
        ownerIdentityShortfall(ownerOf({ name: "" })) ?? "",
        t,
      ),
    ).toBe("Name the owner first.");
    // B14 rule 33 — the shared catalogue sentence for the same fact runs to 21
    // words in one sentence, and is deliberately NOT reused here.
    expect(html).not.toContain("before opening the account");
  });
});

describe("DEF-MET-5093 — what the commit actually sends", () => {
  it("sends the party kind and the identity a company needs", () => {
    const draft = {
      ...emptyDraft(),
      owner: ownerOf({
        name: "Ridge Property LLC",
        partyKind: "company",
        taxId: "TX-4471-08",
      }),
    };
    const owner = commitPlanOf(draft, null).owner;
    expect(owner.party_kind).toBe("company");
    expect(owner.identity).toEqual({ tax_id: "TX-4471-08" });
  });

  it("never sends a company's evidence under a person, which the door refuses by name", () => {
    const draft = {
      ...emptyDraft(),
      owner: ownerOf({
        name: "Ibarra, M.",
        partyKind: "person",
        taxId: "TX-4471-08",
        ssn: "123-45-6789",
      }),
    };
    const identity = commitPlanOf(draft, null).owner.identity as Record<string, string>;
    expect(identity.ssn).toBe("123-45-6789");
    expect(identity.tax_id).toBeUndefined();
  });

  it("sends NO identity block at all when the kind is unstated", () => {
    // BR-CUS-1022 — sending it regardless turns one refusal that names the
    // missing dropdown into a field error about the evidence.
    const draft = {
      ...emptyDraft(),
      owner: ownerOf({ name: "Ibarra, M.", ssn: "123-45-6789" }),
    };
    const owner = commitPlanOf(draft, null).owner;
    expect(owner.party_kind).toBeUndefined();
    expect(owner.identity).toBeUndefined();
  });

  it("names the attached customer so the door opens without an identifier", () => {
    // BR-CUS-019 — the clerk's explicit answer wins over everything, and
    // `refuse_account_without_identity` returns early on a named customer.
    const draft = {
      ...emptyDraft(),
      owner: ownerOf({
        name: "Vasquez, M.",
        partyKind: "person",
        matchedCustomerId: "6f1d4c2a-9b37-4f58-bb21-0e7c8a5d3f10",
        matchedCustomerNo: "C-00902",
      }),
    };
    const owner = commitPlanOf(draft, null).owner as Record<string, unknown>;
    expect(owner.customer).toEqual({
      customer_id: "6f1d4c2a-9b37-4f58-bb21-0e7c8a5d3f10",
      display_name: "Vasquez, M.",
      kind: "person",
    });
  });

  it("sends no customer block when nobody was picked", () => {
    const owner = commitPlanOf(emptyDraft(), null).owner as Record<string, unknown>;
    expect(owner.customer).toBeUndefined();
  });
});

describe("the finder's label never renders empty", () => {
  it("prints the number and the name together", () => {
    expect(customerFinderLabel(customerRow(), t)).toBe("C-00902 — Vasquez, M.");
  });

  it("falls back to the name when a customer has no number", () => {
    expect(customerFinderLabel(customerRow({ customer_no: null }), t)).toBe("Vasquez, M.");
  });

  it("states the absence rather than rendering a blank row", () => {
    // A row a clerk can attach without knowing whose record it is, is the shape
    // of the wrong customer being billed for somebody else's building.
    expect(
      customerFinderLabel(customerRow({ customer_no: null, display_name: "" }), t),
    ).toBe("Customer with no number");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// PO 2026-09-21 · STEP 1 TAKES DOCUMENTS
// ══════════════════════════════════════════════════════════════════════════
//
// PO, verbatim: *"Step 1 — Owner & scope (p92) + you ahve to take documents -
// rest is all good"*. It is NOT on the drawing; a ruling beats a drawing.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** The shared block renders a table,
// four chips and a form, so almost any `toContain` over it succeeds. So the
// REUSE case asserts markers the shared component owns and that a hand-rolled
// copy would not have (`data-doc-empty`, `data-doc-note`, the chips' own ids),
// and the ROWS case asserts a held file by its NAME, which only the draft can
// put there.
describe("PO 2026-09-21 — step 1 takes the owner's documents", () => {
  /** A `File` the way a browser hands one over. */
  function deed(name = "title-deed.pdf"): File {
    return new File(["x"], name, { type: "application/pdf" });
  }

  // ⊕ **LANE CF-1 (2026-10-18) — MOVE-IN'S DOCUMENTS TABLE, NOT THE ACCOUNT
  // UPLOADER** (drawing set `customer-forms-2026-10-18`, image 06; PO *"Move
  // in UI is latest and correct"*). The two cases that asserted the account
  // uploader's markers and its four account types are superseded: the table
  // offers Move-in's nine types, and every file is filed in the account's KYC
  // folder after Create (move-in's own rule, `CARRIED_DOC_FOLDER`).
  it("renders Move-in's SHARED documents table", () => {
    const html = renderStep(emptyDraft());
    expect(html).toContain('data-array="move-in-documents"');
    expect(html).not.toContain('id="nc-owner-doc-type"');
  });

  it("offers Move-in's nine document types on an added row", () => {
    const html = renderStep({
      ...emptyDraft(),
      ownerDocDrafts: [{ key: "doc-a", doc_type: "", card_id: "", name: "" }],
    });
    for (const type of ["proof_of_identity", "tenancy_agreement_or_deed", "other"]) {
      expect(html).toContain(`value="${type}"`);
    }
    expect(html).not.toContain('value="system"');
  });

  it("shows a held document by NAME, and says nothing has been checked", () => {
    const held = draftDocumentRows([
      {
        id: "local-0-title-deed.pdf",
        docType: "contract",
        name: "title-deed.pdf",
        whatItProves: "The developer owns the land",
        required: true,
        file: deed(),
      },
    ]);
    expect(held).toHaveLength(1);
    // ⚠ **NOT UPLOADED YET, AND THE ROW SAYS SO.** A date here would be the
    // moment the file was CHOSEN, which is a different fact from the moment it
    // was filed and would be wrong on the record afterwards.
    expect(held[0].uploaded_at).toBeNull();
    expect(held[0].uploaded_by_name).toBeNull();
    expect(held[0].verification_state).toBe("not_checked");
    expect(held[0].file_present).toBe(true);
    expect(held[0].size_bytes).toBe(1);
  });

  it("B14 rule 31 — the local key is never the visible value of anything", () => {
    const draft: NewConnectDraft = {
      ...emptyDraft(),
      ownerDocuments: [
        {
          id: "local-0-title-deed.pdf",
          docType: "contract",
          name: "title-deed.pdf",
          whatItProves: "",
          required: false,
          file: deed(),
        },
      ],
      // ⊕ lane CF-1 — the table's row names the held file by its local key.
      ownerDocDrafts: [
        { key: "doc-a", doc_type: "tenancy_agreement_or_deed", card_id: "local-0-title-deed.pdf", name: "title-deed.pdf" },
      ],
    };
    const html = renderStep(draft);
    // The file's NAME shows; the key the draft uses to track it does not.
    expect(html).toContain("title-deed.pdf");
    expect(html).not.toContain("local-0-title-deed.pdf");
  });

  it("BR-MET-112 — no file rides the commit payload", () => {
    // *Nothing is written until step 8*, and a browser `File` is not JSON. The
    // documents are filed AFTER the commit, against the owner's account, so
    // the commit plan must carry no trace of them at all.
    const draft: NewConnectDraft = {
      ...emptyDraft(),
      ownerDocuments: [
        {
          id: "local-0-title-deed.pdf",
          docType: "contract",
          name: "title-deed.pdf",
          whatItProves: "",
          required: false,
          file: deed(),
        },
      ],
    };
    const plan = commitPlanOf(draft, null);
    expect(JSON.stringify(plan)).not.toContain("title-deed.pdf");
    expect("owner_documents" in plan).toBe(false);
    expect("documents" in plan).toBe(false);
  });
});
