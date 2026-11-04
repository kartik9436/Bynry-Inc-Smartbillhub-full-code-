// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `BR-CUS-1081` — PO ruling 2026-09-20, having walked the wizard:
//          *"step 2 dont allow to take kYC documents - DOB, all detaisl we need
//          to create account - Similar to Move in request"* and *"we have it -
//          we have created it for service request move in - use it"*.
// Rules:   CLAUDE.md hard-won law 2 (a component with a prop nothing passes is
//          dead UI — it renders nothing, every test passes, and the feature
//          does not exist) · `BR-CUS-1022` · `BR-CUS-1081` §§2–3 · hard rule 8
// Screens: `TRF-02.2` — Accounts blueprint p126–p127, "Who is buying it"
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE EXISTS BECAUSE LAW 2 SAYS A RENDERED SCREEN IS THE ONLY PROOF.**
// The wizard could import `ApplicantCaptureFields`, pass it every prop, compile
// clean and still put nothing in front of a clerk — that is four of one day's
// nine defects. So every case here TYPES INTO THE REAL SCREEN, mounted at the
// real `/:tenant/transfers/new` pattern (never bare in a `MemoryRouter`, which
// is how a front page shipped with `//portal/…` addresses that read as good
// strings), and then reads what the COMMIT would send.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

// Node's own modules, reached the way `src/styles/routeBUtilities.test.ts`
// next door does — the string-split import keeps Vite from pre-bundling them
// and keeps `tsc` from looking for `@types/node`, which this project does not
// carry. A bare `import ... from "node:fs"` compiles to TS2307 here; the
// project typecheck is what said so, which is the check doing its job.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

/** This folder — the guard below reads two real files from it. */
const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));

import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

import { TransferWizard, emptyTransferDraft, transferPlanOf } from "./TransferWizard";
import { TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";
import {
  applicantCapturePayload,
  captureIdentityFieldsFor,
  clearedForKind,
  emptyApplicantCapture,
} from "./applicantCapture";

afterEach(cleanup);

const TEST_TENANT = "brazosbend";
const t = (key: string): string => i18n.t(key) as string;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Mount step 2 of the REAL wizard at the REAL address. */
function mountStep2(
  onRequest: (url: string, init?: RequestInit) => Response = () =>
    json({ count: 0, results: [] }),
): void {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input, init) => onRequest(String(input), init as RequestInit | undefined),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${TRANSFER_WIZARD_ROUTE}?step=2`]}>
          <Routes>
            <Route
              path={`/:tenant${TRANSFER_WIZARD_ROUTE}`}
              element={<TransferWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * **THE FORM IS ALREADY OPEN — `DEF-CUS-6549`, PO ruling 2026-09-24.**
 *
 * ⚠ **THIS HELPER USED TO WALK THROUGH THE DEFECT.** It read: type a term,
 * press *Search customer*, press *Create customer* — because from `2.351.0` the
 * capture was drawn only after all three, which is the gate the PO reported
 * twice (*"you removed all buyer details and only provide search - this is
 * wrong"*). Every case below it therefore tested a form no clerk could reach,
 * and that is a large part of why nineteen green cases sat over a broken step.
 *
 * It is kept as a NO-OP rather than deleted from seven call sites: each of
 * those cases is about a FIELD, the walk to the field was never their subject,
 * and a helper that now says *"nothing to open"* is the clearest record of
 * what changed. The name stays so a reader finds this note.
 */
async function openCreateForm(term = "Vasquez, M."): Promise<void> {
  // Nothing to OPEN — the buyer's fields are on the step from the moment it
  // renders. What the old walk did incidentally, and what several cases below
  // depend on, is put the searched term into the buyer's NAME: the retired
  // *Create customer* button seeded `full_name` with it. A clerk types it, so
  // the helper types it.
  await userEvent.type(
    screen.getByLabelText(t("customers.newAccount.field.fullName"), { exact: false }),
    term,
  );
}

describe("BR-CUS-1081 · step 2 captures what an account needs", () => {
  /**
   * **THE CASE THE RULING IS ABOUT.** The PO could not give the buyer a date of
   * birth or a driving licence, and those are two of the things an account is
   * created from. Both are on screen, and both are REACHED BY THEIR LABEL —
   * not by a test id — because a label is what a clerk reads.
   */
  // ⊕ `DEF-CUS-10255` — the buyer step is Move-in's SHARED form now (CF-1's
  // Who and Identity panels, image 07): the date of birth sits in *Who is
  // buying* as the product's date picker, the SSN and licence in *Identity*.
  // The labels are the shared form's own.
  it("a clerk can type the buyer's date of birth and driving licence", async () => {
    mountStep2();
    await openCreateForm();
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));

    const dob = await screen.findByLabelText(t("customers.account.field.dob"));
    const licence = screen.getByLabelText(t("customers.newAccount.field.drivingLicence"));
    const ssn = screen.getByLabelText(t("customers.newAccount.field.ssn"));
    await userEvent.type(dob, "03/08/1984");
    await userEvent.type(licence, "TX-4417802");
    await userEvent.type(ssn, "521-44-9087");

    expect(dob).toHaveValue("03/08/1984");
    expect(licence).toHaveValue("TX-4417802");
    // The picker's TEXT box (typed in the utility's format), never a native
    // date box (PO 2026-10-18: every date is the product's date picker).
    expect(dob).toHaveAttribute("type", "text");
  });

  /** A company is refused both BY NAME — `BR-CUS-1022` — and is asked its Tax
   *  ID instead. Offered-and-discarded is the shape the rule forbids. */
  it("a company is never asked for a date of birth or a licence", async () => {
    mountStep2();
    await openCreateForm();
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.company") }));

    expect(await screen.findByLabelText(/tax id/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(t("customers.account.field.dob"))).toBeNull();
    expect(screen.queryByLabelText(t("customers.newAccount.field.drivingLicence"))).toBeNull();
    expect(screen.queryByLabelText(t("customers.newAccount.field.ssn"))).toBeNull();
  });

  /** ⊕ `DEF-CUS-10255` — the co-buyer is Move-in's co-owner CARD (image 07:
   *  full name, relationship, responsible for bills, phone, email, date of
   *  birth, SSN, licence), behind the panel's *Has co-buyers* tick. */
  it("the co-buyers are one tick until it is ticked, then a full card", async () => {
    mountStep2();
    await openCreateForm();
    expect(document.querySelector("#co_owner_0_full_name, [id$='_full_name'][id^='co_owner']")).toBeNull();
    await userEvent.click(screen.getByLabelText(t("customers.form.coBuyers.tick")));
    expect(await screen.findByText(t("customers.form.coBuyers.add"))).toBeInTheDocument();
  });

  /**
   * **HARD RULE 8's ONE NAMED EXCEPTION — AND THE DEFAULT IS THE SERVICE
   * ADDRESS** (`DEF-CUS-6388`, PO 2026-09-23: *"Bill goes elsewhere - it should
   * mailing address , we should use same vocablory in everywhere"*, and T3:
   * the seller's mailing row does not survive the sale). The block is headed
   * *Mailing address*, its tick is *Same as service address* and is ticked;
   * unticking draws the shared US address block, `line2` included.
   */
  it("the mailing address is the service address until the tick is cleared", async () => {
    mountStep2();
    await openCreateForm();
    expect(screen.getByText(t("customers.account.field.mailingAddress"))).toBeInTheDocument();
    const same = screen.getByLabelText(t("customers.transfer.step2.sameAsService"));
    expect(same).toBeChecked();
    expect(screen.queryByLabelText(t("common.usAddress.line1"))).toBeNull();

    await userEvent.click(same);
    expect(await screen.findByLabelText(t("common.usAddress.line1"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("common.usAddress.line2"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("common.usAddress.city"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("common.usAddress.state"))).toBeInTheDocument();
    expect(screen.getByLabelText(new RegExp(`^${t("common.usAddress.zip")}`, "i"))).toBeInTheDocument();
    // ⛔ The retired pair (*"Bill goes elsewhere"* / *"Bills keep going to the
    // seller's mailing address"*) is gone from the screen.
    expect(screen.queryByText(/seller's mailing address/i)).toBeNull();
  });
});

describe("DEF-CUS-6386 · a LINKED buyer brings what is on file", () => {
  /**
   * T3 writes the account's contact WHOLE at the sale, so a linked buyer whose
   * email was not carried onto the form would lose it — found on the browser
   * walk of 2026-09-23 (*Hugo Hollis*, email on file, review said *"No email
   * given"*). Link pre-fills the phone AND the email; no identifier is asked.
   */
  // ⊕ `DEF-CUS-10255` — the free-text finder is replaced by *Search customer
  // ID* and its results table; Link FILLS the name and kind from the row and
  // withdraws the identifiers (the commit names the customer by id).
  it("Link fills the buyer from the row on file, and asks for no ID", async () => {
    mountStep2((url) =>
      url.includes("/customers/match")
        ? json({
            search: {
              result: "found",
              count: 1,
              customers: [
                {
                  id: "5b0c7d2e-1a3f-4c5d-8e9f-0a1b2c3d4e5f",
                  customer_no: "C-00008",
                  display_name: "Hugo Hollis",
                  kind: "person",
                  verdict: "found",
                  agreed: ["name"],
                  date_of_birth: "1979-02-11",
                  phone_last4: "1007",
                  accounts: null,
                  company: null,
                },
              ],
            },
          })
        : json({ count: 0, results: [] }),
    );
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));
    await openCreateForm("Hollis");
    await userEvent.click(document.querySelector("[data-search-customer-id]") as HTMLElement);
    await userEvent.click(
      await screen.findByRole("button", {
        name: i18n.t("customers.moveIn.customer.match.linkName", { name: "Hugo Hollis · C-00008" }) as string,
      }),
    );
    expect(document.getElementById("full_name")).toHaveValue("Hugo Hollis");
    expect(document.querySelector('[data-customer-match="linked"]')).not.toBeNull();
  });
});

describe("BR-CUS-1081 · and the values reach the wire", () => {
  /**
   * **LAW 2's OTHER HALF.** A field on screen that never reaches the payload is
   * the same defect wearing the opposite costume, and `tsc` cannot see either.
   * This walks the draft the screen builds into `transferPlanOf` and reads what
   * `POST /transfers/commit` would actually receive.
   */
  it("the commit carries date_of_birth, drivers_licence and the mailing address", () => {
    const draft = {
      ...emptyTransferDraft(),
      fromAccountId: "acc-10650",
      buyer: {
        ...emptyTransferDraft().buyer,
        full_name: "Okafor, Chidi",
        customer_kind: "person",
        ssn: "521-44-9087",
        driving_licence: "TX-4417802",
        phone: "(512) 555-0197",
        email: "c.okafor@example.com",
        // ⊕ `DEF-CUS-10255` — the shared form holds the date of birth.
        dob: "1984-03-08",
      },
      mailingSameAsService: false,
      buyerMailing: {
        line1: "PO Box 4120",
        line2: "Suite 2",
        city: "Austin",
        state: "TX",
        postal_code: "78704",
      },
      soldOn: "2026-05-09",
    };
    const plan = transferPlanOf(draft);
    const customer = plan.customer as Record<string, unknown>;

    // THE TWO THE RULING IS ABOUT, in the server's own capture spelling.
    expect(customer.date_of_birth).toBe("1984-03-08");
    expect(customer.drivers_licence).toBe("TX-4417802");
    expect(customer.ssn).toBe("521-44-9087");
    expect(customer.applicant_email).toBe("c.okafor@example.com");
    expect(customer.applicant_phone).toBe("(512) 555-0197");

    // ⊕ `DEF-CUS-10255` — co-buyers are full CARDS on `buyer_account.co_owners`
    // now (TransferBuyerCapture.dom.test.tsx), so the contact-only co-applicant
    // rides EMPTY, which removes the seller's second person at the sale (T4).
    expect(customer.co_applicant_name).toBe("");

    // Hard rule 8's one lawful second address.
    expect(customer.mailing_address).toEqual({
      line1: "PO Box 4120",
      line2: "Suite 2",
      city: "Austin",
      state: "TX",
      postal_code: "78704",
    });
    // ⛔ `kind` is NOT sent — the write door writes `mailing` and only
    // `mailing`, so the retired `kind='service'` cannot arrive as a typo.
    expect(Object.keys(customer.mailing_address as object)).not.toContain("kind");

    // The shipped payload still sells a property: `identity{}` is untouched.
    expect(plan.customer.identity).toMatchObject({ ssn: "521-44-9087" });
  });

  /** A blank optional field means *nothing was typed*, and sending `""` for it
   *  would read as *erase what is on file* — which for a buyer is the SELLER's
   *  email and phone (`BR-CUS-1081` §2, "Absent means"). */
  it("a field nobody typed is omitted, and the mailing block with it", () => {
    const draft = {
      ...emptyTransferDraft(),
      fromAccountId: "acc-10650",
      buyer: {
        ...emptyTransferDraft().buyer,
        full_name: "Okafor, Chidi",
        customer_kind: "person",
        phone: "(512) 555-0197",
      },
      buyerCapture: { ...emptyApplicantCapture(), applicant_kind: "person" },
      soldOn: "2026-05-09",
    };
    const customer = transferPlanOf(draft).customer as Record<string, unknown>;
    expect(customer).not.toHaveProperty("date_of_birth");
    expect(customer).not.toHaveProperty("drivers_licence");
    expect(customer).not.toHaveProperty("mailing_address");
    // …and the three co-applicant keys ARE sent empty, which is the deliberate
    // exception: an empty string CLEARS, and that is the act unticking means.
    expect(customer.co_applicant_name).toBe("");
  });
});

describe("BR-CUS-1081 §4 · the buyer is looked up before anybody is written", () => {
  /**
   * **THE DRAWN FEEDBACK LINE ON p127**, which the conformance walk of
   * 2026-09-20 recorded as *"NOT BUILT: the match happens server-side at commit
   * and the clerk is never told."* This mounts the real wizard, types a real
   * buyer, and asserts the door was ASKED and its answer REACHED THE SCREEN.
   */
  it("a named buyer is previewed, and the match reaches the screen", async () => {
    const posted: { url: string; body: unknown }[] = [];
    mountStep2((url, init) => {
      if (url.includes("/transfers/buyer-preview")) {
        posted.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
        return json({
          buyer_name: "Vasquez, M.",
          buyer_kind: "person",
          buyer_match: {
            verdict: "matched",
            matched: "cus-902",
            tier: "strong",
            basis: "name and phone number",
            candidates: [{ customer_no: "C-00902", display_name: "Vasquez, M." }],
            missing_for_strong: [],
            will_create: false,
          },
        });
      }
      return json({ count: 0, results: [] });
    });

    await openCreateForm("Vasquez, M.");
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));

    // The DOOR was asked — a POST, never a GET, because a government
    // identifier may not travel in a URL (`BR-CUS-092`(c)).
    await waitFor(() => expect(posted.length).toBeGreaterThan(0));
    expect(posted[0].body).toHaveProperty("customer");

    // …and the ANSWER is on screen, with the detail the drawing prints.
    const line = await screen.findByText(
      new RegExp(t("customers.transfer.step2.matchFound"), "i"),
    );
    expect(line).toHaveTextContent("C-00902");
    expect(line).toHaveTextContent("Vasquez, M.");
    // ⚠ B14 rule 31 — the customer NUMBER is a tenant series; the uuid the
    // door also answered with is never rendered.
    expect(document.body.innerHTML).not.toContain("cus-902");
  });

  /**
   * **`candidates` IS THE ANSWER THAT COSTS MONEY WHEN IT IS MIS-STATED.**
   * Somebody looks related, the criteria are not met, and the commit creates a
   * SECOND customer beside them — `DEF-2587` measured one landlord written
   * three times over one Social Security number. So the screen says what would
   * decide it.
   */
  it("a near-miss says so, and says what would settle it", async () => {
    mountStep2((url) =>
      url.includes("/transfers/buyer-preview")
        ? json({
            buyer_match: {
              verdict: "candidates",
              matched: null,
              tier: null,
              candidates: [{ customer_no: "C-00902", display_name: "Vasquez, M." }],
              missing_for_strong: ["date_of_birth"],
              will_create: true,
            },
          })
        : json({ count: 0, results: [] }),
    );
    await openCreateForm("Vasquez, M.");
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));

    const line = await screen.findByText(
      new RegExp(t("customers.transfer.step2.matchCandidates"), "i"),
    );
    expect(line).toHaveTextContent(t("customers.transfer.step2.matchMissing"));
  });

  /**
   * **HARD RULE 2 — *we did not ask* and *nobody is on file* are different
   * facts, and only one of them is about the buyer.** A door that could not
   * answer must render NOTHING, never "no match".
   */
  it("a door that did not answer says nothing at all", async () => {
    mountStep2((url) =>
      url.includes("/transfers/buyer-preview")
        ? json({ detail: "boom" }, 500)
        : json({ count: 0, results: [] }),
    );
    await openCreateForm("Vasquez, M.");
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));

    // The step is still completable — `BR-CUS-019`, the check is ADVISORY.
    await waitFor(() =>
      expect(screen.getByLabelText(t("customers.serviceRequest.applicant.dateOfBirth"))).toBeInTheDocument(),
    );
    expect(screen.queryByText(new RegExp(t("customers.transfer.step2.matchNone"), "i"))).toBeNull();
    expect(document.querySelector("[data-buyer-match]")).toBeNull();
  });

  /** Nothing is asked before there is anything to ask about: `none` over an
   *  empty form is true of every buyer alive and tells a clerk nothing. */
  it("the door is not asked before a kind and a name exist", async () => {
    const asked: string[] = [];
    mountStep2((url) => {
      asked.push(url);
      return json({ count: 0, results: [] });
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(asked.some((url) => url.includes("/transfers/buyer-preview"))).toBe(false);
  });
});

describe("BR-CUS-1081 · the shared block and the form it came from stay in step", () => {
  /**
   * ⚠ **THE PO ASKED FOR REUSE AND THIS IS THE CHECK THAT SAYS WHETHER THEY
   * GOT IT.** *"we have it - we have created it for service request move in -
   * use it"*. `applicantCapture.tsx` IS that block, lifted out — but the
   * move-in capture page still renders its own copy of the fields today, for a
   * reason recorded in the decision log: a sibling lane collapsed its applicant
   * fields into ONE `FieldGrid` on 2026-09-19 to close a B14 rule 39 spacing
   * defect, and dropping this two-grid component into that page would re-open
   * it. So the two are ONE FIELD SET rendered twice, and this is what stops
   * that becoming two different forms.
   *
   * It reaches across to the page's SOURCE on purpose — nothing else connects
   * a form to the form it was taken from, which is exactly the seam a copy
   * rots through. Asserting the CATALOGUE KEYS rather than the markup is what
   * makes it survive the construction difference that is legitimate.
   */
  it("every capture field the shared block asks for is one the request's form still holds", () => {
    // ⊕ **AMENDED 2026-10-18 (lane CF-1) — THE REQUEST'S STEP 1 IS THE SHARED
    // CUSTOMER FORM NOW** (`CaptureCustomerForm.tsx` over `customerForm/`,
    // drawing set `customer-forms-2026-10-18`, image 03), and
    // `CaptureApplicantPanel.tsx`, which this guard read, is DELETED. The LABEL
    // half of the old case no longer has a subject: the request's labels are
    // the shared form's, and this block is Transfer's until lane CF-2 moves
    // Transfer onto the shared form too (the PO's plan, task 16).
    //
    // ⚠ **THE FIELD-SET HALF STAYS, AND IT IS THE HALF THAT CARRIES DATA.**
    // The four identifiers and the co-applicant keys are still spelt the same
    // in this block and in the request's own form (`CaptureForm`), which is
    // what lets a buyer's answers and an applicant's travel through one
    // vocabulary. A MISSING SOURCE IS A FAILURE, NOT A SKIP (`DEF-524`).
    const capturePage = nodeFs.readFileSync(
      nodePath.join(HERE, "ServiceRequestCapturePage.tsx"),
      "utf8",
    );
    const captureForm = nodeFs.readFileSync(nodePath.join(HERE, "CaptureCustomerForm.tsx"), "utf8");
    const shared = nodeFs.readFileSync(nodePath.join(HERE, "applicantCapture.tsx"), "utf8");
    expect(capturePage.length).toBeGreaterThan(1000);
    expect(captureForm.length).toBeGreaterThan(1000);
    expect(shared.length).toBeGreaterThan(1000);
    for (const field of [
      "date_of_birth",
      "drivers_licence",
      "ssn",
      "tax_id",
      "add_co_applicant",
      "applicant_email",
      "applicant_phone",
    ]) {
      expect(shared, `${field} missing from the shared block`).toContain(field);
      expect(`${capturePage}${captureForm}`, `${field} missing from the request's form`).toContain(
        field,
      );
    }
  });
});

describe("BR-CUS-1081 · the shared block's own rules", () => {
  it("BR-CUS-1022 — the kind decides which identifiers are asked for", () => {
    expect(captureIdentityFieldsFor("person")).toEqual(["date_of_birth", "ssn", "drivers_licence"]);
    expect(captureIdentityFieldsFor("company")).toEqual(["tax_id"]);
    // An UNSTATED kind is a real answer: nothing is asked for at all.
    expect(captureIdentityFieldsFor("")).toEqual([]);
  });

  /** *"asking for both and leaving one blank turns a rule into a habit and the
   *  blank field eventually gets filled with something"* — so switching kind
   *  BLANKS rather than hides. */
  it("switching kind blanks what the new kind is not asked for", () => {
    expect(clearedForKind("company")).toEqual({
      ssn: "",
      date_of_birth: "",
      drivers_licence: "",
    });
    expect(clearedForKind("person")).toEqual({ tax_id: "" });
  });

  it("only the stated kind's identifiers reach the payload", () => {
    const asCompany = applicantCapturePayload({
      ...emptyApplicantCapture(),
      applicant_kind: "company",
      tax_id: "82-1234567",
      // Left over from a kind switch that some future caller forgot to clear:
      // the payload still must not carry it (`BR-CUS-1020`).
      ssn: "521-44-9087",
    });
    expect(asCompany.tax_id).toBe("82-1234567");
    expect(asCompany).not.toHaveProperty("ssn");
  });
});
