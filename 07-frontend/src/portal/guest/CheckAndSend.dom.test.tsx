// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-014 (EP-CWP-04) — check and send, and where paperless
//           consent is taken. Screen: CWP-009 · wireframes/CWP-009.png
// Rules:    BR-CWP-087 (paperless is a RECORDED CONSENT — a timestamp, the
//           wording version and a way to withdraw) · CR-068 R4 (print stays
//           the floor: the copy must say *"we print them as well"* and may
//           never claim paperless stops paper bills) · BR-CWP-026 (the form
//           grants nothing by itself) · 08-screen-layouts.md CWP-009 (KVList ·
//           WE WILL NEED THESE FROM YOU · two AFTER YOU APPLY rows · boxed
//           consent + helper · ConsequenceBox ×4 · Send my application ✓ ·
//           Back) · B14 rule 31 (no database id on screen) · rule 36
// Cases:    TC-1 (ticked → a reference, and the consent is recorded) · TC-2
//           (unticked → the application succeeds and NO consent is recorded,
//           and the screen says which) · TC-3 (the copy states that we print
//           them as well) · TC-5 (a double click is ONE submit) · TC-7 (the
//           consequence box, and the figures are `CWP-008`'s)
//
//           ⚠ **`US-CWP-014` HAD SEVEN BACKEND CASES AND NO SCREEN TEST AT
//           ALL** (`StartService.test.tsx` covers `CWP-008` and `CWP-010`
//           only). The consent is a legal record and the screen is where it is
//           taken; a wave that tested only the write would not have noticed
//           the tick disappearing.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";

import type {
  ApplicationDraft,
  Availability,
  SubmittedApplication,
} from "../api/guestClient";

let submits: boolean[] = [];
/** CR-191-BRC10 — the card payment each submit carried (null: none). */
let payments: (Record<string, unknown> | null)[] = [];
let answer: SubmittedApplication = {
  reference: "SR-26-0051",
  request_id: "request",
  consent_recorded: true,
  idempotent_replay: false,
};
let draft: ApplicationDraft;
/** True when the server holds NO draft for this token yet — the first visit.
 *  `getDraft` 404s there, which is not an error: nothing has been typed. */
let draftMissing = false;
/**
 * ⚠ **TRUE WHILE THE SEEDING SAVE IS STILL IN FLIGHT — WHICH IS WHAT A FIRST
 * VISIT ACTUALLY LOOKS LIKE, AND WHAT NO FIXTURE HERE COULD DRAW UNTIL NOW.**
 * `saveDraft` answering instantly meant `props.draft` was populated before the
 * first paint anybody could assert on, so the three heading cases below were
 * really testing the SEEDED state and passed over a head that names no address
 * (`DEF-CWP-4876`, residual, found in a browser at 390 and 1280 on
 * 2026-09-11 — the suite was green at the time). A real server takes a round
 * trip, and on the way out the head has only the query string to read.
 */
let saveHangs = false;
/** `DEF-CWP-4930` — apply each save's patch to `draft`. */
let applyPatches = false;
/** `DEF-CWP-9051` — a save held on the wire until the case releases it. */
let saveGate: Promise<void> | null = null;
/** What the SERVER refuses the submit with, when it refuses — `DEF-CWP-4877`. */
let submitRefusal: ApiError | null = null;
/** What `getAvailability` answers. Overridden by the em-dash case. */
let availability: Availability;
/** `CR-158-BRC10` — the files the mocked server holds on the draft, and the
 *  refusal it answers an upload with when one is set. */
let held: NonNullable<ApplicationDraft["documents"]> = [];
let uploadRefusal: ApiError | null = null;
let uploadedNames: string[] = [];
/** `DEF-CWP-9167` — the attach row each upload was chosen on. */
let uploadedRequirements: (string | null)[] = [];

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    getDraft: async () => {
      if (draftMissing) throw new Error("no such draft");
      return draft;
    },
    saveDraft: async (_token: string, patch: Record<string, unknown>) => {
      if (saveHangs) await new Promise(() => {});
      if (saveGate !== null) await saveGate;
      // `DEF-CWP-4930` — the ticks must reach the draft for the gate to read
      // them, so this one fixture applies what it is sent; every other case
      // keeps the frozen row it always had.
      if (applyPatches) draft = { ...draft, ...(patch as Partial<ApplicationDraft>) };
      return draft;
    },
    getAvailability: async (): Promise<Availability> => availability,
    uploadApplicationDocument: async (
      _token: string,
      file: File,
      _client?: unknown,
      requirement?: string,
    ) => {
      if (uploadRefusal !== null) throw uploadRefusal;
      uploadedNames.push(file.name);
      uploadedRequirements.push(requirement ?? null);
      held = [
        ...held,
        {
          id: `doc-${held.length + 1}`,
          requirement: requirement ?? null,
          name: file.name,
          content_type: file.type === "image/png" ? "image/png" : "application/pdf",
          size_bytes: file.size,
          uploaded_at: "2026-10-01T12:00:00Z",
        },
      ];
      return { ...draft, documents: held };
    },
    removeApplicationDocument: async (_token: string, documentId: string) => {
      held = held.filter((one) => one.id !== documentId);
      return { ...draft, documents: held };
    },
    submitApplication: async (
      _token: string,
      paperless: boolean,
      _client?: unknown,
      payment?: Record<string, unknown> | null,
    ) => {
      if (submitRefusal !== null) throw submitRefusal;
      submits.push(paperless);
      payments.push(payment ?? null);
      return { ...answer, consent_recorded: paperless };
    },
  };
});

const { ApplyForServiceBody } = await import("./ApplyForService");

/** `US-CWP-014` §4, verbatim: `$185.00` before we start, `$150.00` deposit. */
const AVAILABILITY: Availability = {
  matched: true,
  address: "31 Palm Ct",
  job: "new_connection",
  rows: [
    {
      service_code: "water",
      service_name: "Water",
      available: true,
      to_connect: { kind: "amount", amount: "185.0000", display: "$185.00", currency: "USD" },
      deposit: { kind: "amount", amount: "150.0000", display: "$150.00", currency: "USD" },
    },
  ],
  if_you_apply: {
    before_we_start: { kind: "amount", amount: "185.0000", display: "$185.00", currency: "USD" },
    on_first_bill: { kind: "amount", amount: "150.0000", display: "$150.00", currency: "USD" },
    working_days: 2,
  },
};

const DRAFT: ApplicationDraft = {
  token: "draft-token",
  address_as_given: "31 Palm Ct",
  address_unit_as_given: null,
  service_codes: ["water", "sewer", "trash"],
  applicant_kind: "person",
  first_name: "Daniel",
  last_name: "Okafor",
  company_name: null,
  email: "d.okafor@example.com",
  phone: "(512) 555-7730",
  date_of_birth: "1988-04-02",
  tax_id: null,
  requested_start: "2026-09-21",
  submitted: false,
  reference: null,
  // `DEF-CWP-9167` — the server's list of what it asks for.
  document_requirements: ["photo_id", "proof_of_address"],
  // `DEF-CWP-9818` — the applicant's category (REQUIRED) and the offered list.
  account_type_code: "residential",
  account_subtype_code: null,
  categories: [
    { code: "residential", name: "Residential", subcategories: [{ code: "single_family", name: "Single-family" }] },
    { code: "commercial", name: "Commercial", subcategories: [{ code: "healthcare", name: "Healthcare" }] },
    { code: "industrial", name: "Industrial", subcategories: [] },
  ],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE** — hard-won law 2's last
 * clause. A component mounted outside `/:tenant/portal/…` builds every address
 * from an undefined `tenant`, and `//portal/…` reads as a perfectly good string
 * to `toContain`.
 *
 * `regional` publishes the tenant's own date format, which is the only way a
 * test can tell `10/14/2026` from the wire's `2026-10-14`.
 */
function draw(
  regional?: { timeZone: string; dateFormat: "MM/DD/YYYY" | "DD/MM/YYYY" },
  /** The query string `CWP-008` puts on the link — set only by the FIRST-VISIT
   *  helper below, because a resumed link carries none. */
  search = "",
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const tree = (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/pine-hill/portal/start-service/draft-token${search}`]}>
        <Routes>
          <Route path="/:tenant/portal/start-service/:draft" element={<ApplyForServiceBody />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return render(
    regional ? <TenantRegionalProvider value={regional}>{tree}</TenantRegionalProvider> : tree,
  );
}

/**
 * `CWP-009` is step 4, and a FINISHED draft opens straight on it.
 *
 * ⚠ **THE JOURNEY GAINED ITS MISSING STEP (`CR-085` task (c)).** It ran
 * *address → about you → check* under a four-label step bar, so step 3 was
 * ticked ✓ on this very screen having never been shown to anybody. PO ruling:
 * *"please show all 4 screens - address, when , about you, check"*. Step 2 is
 * **When** and step 3 is **About you**.
 *
 * ⚠ **AND `DRAFT` IS A COMPLETE ONE, SO THIS HELPER CLICKS NOTHING** —
 * wireframe s19: somebody who comes back to a link is put on the step they did
 * not finish, and this fixture has no unfinished step. The walk through all
 * three lives in *the four steps* below, on a draft that is empty.
 */
async function reachCheckAndSend(container: HTMLElement) {
  await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
  expect(
    container.querySelector('[data-stepper] [data-state="current"]')?.getAttribute("data-step"),
  ).toBe("4");
  // ⚠ **AND WAIT FOR THE AVAILABILITY READ, WHICH IS A SECOND ROUND TRIP.**
  // A finished draft now opens straight on step 4, so the screen exists before
  // the two figures it restates have arrived; asserting on them in that gap
  // reads as *the figures are missing* when the truth is *not yet*. The em
  // dash is what the screen draws while it waits, and it is a real state.
  await waitFor(() =>
    expect(container.querySelector('[data-kv="before_we_start"] dd')?.textContent).not.toBe("—"),
  );
}

/**
 * A FIRST VISIT — the server holds no draft yet and the address rides in on
 * the link from `CWP-008`, exactly as `StartService.tsx` builds it.
 *
 * ⚠ **IT IS A DIFFERENT SCREEN FROM `draw()` AND THAT IS THE POINT.** `draw()`
 * hands `getDraft` a row, so the screen is `resumed` and wireframe s19's head
 * is the right one. The three step titles belong to the applicant who has NOT
 * been here before, which is everyone, once.
 */
function drawFirstVisit() {
  draftMissing = true;
  return draw(undefined, "?address=31%20Palm%20Ct");
}

beforeEach(() => {
  submits = [];
  payments = [];
  draftMissing = false;
  saveHangs = false;
  applyPatches = false;
  saveGate = null;
  submitRefusal = null;
  availability = AVAILABILITY;
  held = [];
  uploadRefusal = null;
  uploadedNames = [];
  uploadedRequirements = [];
  draft = { ...DRAFT };
  answer = {
    reference: "SR-26-0051",
    request_id: "request",
    consent_recorded: true,
    idempotent_replay: false,
  };
});
afterEach(cleanup);

describe("CWP-009 · check and send (US-CWP-014)", () => {
  it("summarises what is being sent, and with nothing attached each document says Bring later", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(screen.getByText("31 Palm Ct")).toBeInTheDocument();
    expect(screen.getByText(/Daniel Okafor/)).toBeInTheDocument();
    // ⚠ **THIS ASSERTED THERE WAS NO UPLOAD CONTROL UNTIL 2026-10-01.** `DF-4`
    // is superseded for this request (`CR-158-BRC10`, PO: *"we need to now
    // accept the document from portal"*), so the hold expired and this is the
    // test that fires on it — law 2's hold-expiry, kept rather than deleted.
    // The half of US-CWP-014 §1 that survives is asserted too: attaching is
    // OPTIONAL, so Send is live with no file at all.
    // ⚠ **IT ASSERTED `NOW OR LATER` ×2 UNTIL 2026-10-02 (`DEF-CWP-9167`)** —
    // the chip said the same over two attached files. With NOTHING attached
    // each row now says *Bring later*; the attached case is below.
    expect(screen.getAllByText("Bring later").length).toBe(2);
    expect(container.querySelectorAll('[data-document-state="later"]')).toHaveLength(2);
    expect(container.querySelector('[data-action="send"]')).not.toBeDisabled();
    // The drop zone is on step 3, where the wireframe draws it; this step
    // restates what will be sent and offers no second upload.
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("DEF-CWP-9167 — per document asked for, Attached ✓ with its file, or Bring later; an untyped file is Other", async () => {
    draft = {
      ...DRAFT,
      documents: [
        {
          id: "doc-1",
          requirement: "photo_id",
          name: "licence.png",
          content_type: "image/png",
          size_bytes: 3072,
          uploaded_at: "2026-10-01T12:00:00Z",
        },
        {
          id: "doc-2",
          requirement: null,
          name: "tenancy-agreement.pdf",
          content_type: "application/pdf",
          size_bytes: 3072,
          uploaded_at: "2026-10-01T12:00:00Z",
        },
      ],
    };
    const { container } = draw();
    await reachCheckAndSend(container);
    const id = container.querySelector('[data-document="photo_id"]') as HTMLElement;
    expect(id.getAttribute("data-document-state")).toBe("attached");
    expect(id.textContent).toContain("Attached ✓");
    expect(id.textContent).toContain("licence.png");
    const address = container.querySelector('[data-document="proof_of_address"]') as HTMLElement;
    expect(address.getAttribute("data-document-state")).toBe("later");
    expect(address.textContent).toContain("Bring later");
    // A file from before the rows existed still travels, listed as Other.
    expect(container.querySelector("[data-other-documents]")?.textContent).toContain(
      "tenancy-agreement.pdf",
    );
    expect(screen.queryByText("NOW OR LATER")).toBeNull();
    // Read-only: nothing on this step uploads or removes.
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(container.querySelector('[data-action="remove-file"]')).toBeNull();
  });

  it("DEF-CWP-9166 — on Check and send the file NAME opens the applicant's own file", async () => {
    const opened: string[] = [];
    const spy = vi.spyOn(window, "open").mockImplementation((url) => {
      opened.push(String(url));
      return null;
    });
    window.history.pushState({}, "", "/pine-hill/portal/start-service/draft-token");
    draft = {
      ...DRAFT,
      documents: [
        {
          id: "doc-7",
          requirement: "proof_of_address",
          name: "power-bill.pdf",
          content_type: "application/pdf",
          size_bytes: 3072,
          uploaded_at: "2026-10-01T12:00:00Z",
        },
      ],
    };
    const { container } = draw();
    await reachCheckAndSend(container);
    fireEvent.click(screen.getByRole("button", { name: "View power-bill.pdf" }));
    expect(opened).toEqual([
      "/api/pine-hill/portal/public/applications/draft-token/documents/doc-7/content?as=view",
    ]);
    spy.mockRestore();
    window.history.pushState({}, "", "/");
  });

  it("CR-158 — the limits are stated, and two chosen files go to the server and are listed", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    fireEvent.click(container.querySelector('[data-change="about"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    expect(screen.getByText("PDF, JPG or PNG. Up to 10 MB each. 5 files at most.")).toBeInTheDocument();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const pdf = new File(["%PDF-1.7 lease"], "tenancy-agreement.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [pdf] } });
    await waitFor(() =>
      expect(container.querySelector('[data-attached-file="tenancy-agreement.pdf"]')).not.toBeNull(),
    );
    const png = new File(["png"], "photo-id.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [png] } });
    await waitFor(() =>
      expect(container.querySelector('[data-attached-file="photo-id.png"]')).not.toBeNull(),
    );
    expect(uploadedNames).toEqual(["tenancy-agreement.pdf", "photo-id.png"]);
    // Name · TYPE · size — and no database id anywhere on the row (rule 31).
    const row = container.querySelector('[data-attached-file="photo-id.png"]') as HTMLElement;
    expect(row.textContent).toContain("PNG");
    expect(row.textContent).not.toContain("doc-2");
  });

  it("DEF-CWP-9051 — a save that answers AFTER an upload does not take the file off the screen", async () => {
    // Found in a browser: the applicant tabs out of the phone box (a save
    // leaves) and chooses a file at once (the upload leaves second and
    // answers first). The save's answer is the draft as it stood BEFORE the
    // file, and it replaced the screen's copy — so the file vanished from the
    // list although the server held it.
    const { container } = draw();
    await reachCheckAndSend(container);
    fireEvent.click(container.querySelector('[data-change="about"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    let release: () => void = () => {};
    saveGate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const phone = container.querySelector("#phone") as HTMLInputElement;
    fireEvent.change(phone, { target: { value: "(512) 555-7731" } });
    fireEvent.blur(phone);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["%PDF-1.7"], "lease.pdf", { type: "application/pdf" })] },
    });
    await waitFor(() =>
      expect(container.querySelector('[data-attached-file="lease.pdf"]')).not.toBeNull(),
    );
    release();
    saveGate = null;
    // Let the held save answer, then look again.
    await new Promise((resolve) => setTimeout(resolve, 50));
    await waitFor(() =>
      expect(container.querySelector('[data-attached-file="lease.pdf"]')).not.toBeNull(),
    );
  });

  it("CR-158 — a refused file is named in the sentence, and a file can be taken back", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    fireEvent.click(container.querySelector('[data-change="about"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["a"], "keep.pdf", { type: "application/pdf" })] },
    });
    await waitFor(() =>
      expect(container.querySelector('[data-attached-file="keep.pdf"]')).not.toBeNull(),
    );
    uploadRefusal = new ApiError(415, {
      code: null,
      message_key: "portal.application.documentTypeNotAllowed",
      params: { name: "notes.docx", allowed: "PDF, JPG, PNG" },
    });
    fireEvent.change(input, {
      target: { files: [new File(["x"], "notes.docx", { type: "application/msword" })] },
    });
    await waitFor(() => expect(screen.getByText("notes.docx: use PDF, JPG, PNG.")).toBeInTheDocument());
    // The file already attached is untouched by the refusal.
    expect(container.querySelector('[data-attached-file="keep.pdf"]')).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Remove keep.pdf" }));
    await waitFor(() =>
      expect(container.querySelector('[data-attached-file="keep.pdf"]')).toBeNull(),
    );
  });

  it("TC-7 — the figures are CWP-008's, restated and never recomputed", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    // `US-CWP-014` §7: *"a figure that disagrees with the availability screen
    // is the defect this test exists to catch."*
    expect(screen.getAllByText("$185.00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$150.00").length).toBeGreaterThan(0);
    expect(container.innerHTML).toMatch(/nothing is charged|charged today/i);
  });

  it("DEF-CUS-9819 — the application fee is shown before Send, $0.00 as Nothing to pay, absent when none is marked", async () => {
    availability = {
      ...AVAILABILITY,
      application_fee: { kind: "amount", amount: "10.0000", display: "$10.00", currency: "USD" },
    };
    const first = draw();
    await reachCheckAndSend(first.container);
    await waitFor(() =>
      expect(first.container.querySelector('[data-kv="application_fee"] dd')?.textContent).toBe("$10.00"),
    );
    expect(first.container.querySelector('[data-kv="application_fee"] dt')?.textContent).toContain(
      i18n.t("portal.apply.applicationFee"),
    );
    first.unmount();

    availability = {
      ...AVAILABILITY,
      application_fee: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
    };
    const zero = draw();
    await reachCheckAndSend(zero.container);
    await waitFor(() =>
      expect(zero.container.querySelector('[data-kv="application_fee"] dd')?.textContent).toBe(
        i18n.t("portal.apply.payNothing"),
      ),
    );
    zero.unmount();

    availability = { ...AVAILABILITY, application_fee: { kind: "none", amount: null, display: null, currency: null } };
    const none = draw();
    await reachCheckAndSend(none.container);
    expect(none.container.querySelector('[data-kv="application_fee"]')).toBeNull();
  });

  it("TC-3 — the consent copy says we print them as well, and never that paper stops", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    const box = container.querySelector("[data-consent-box]");
    expect(box).not.toBeNull();
    // CR-068 R4 — print stays the floor whatever they pick.
    expect(box?.textContent).toMatch(/print/i);
    expect(box?.textContent).not.toMatch(/instead of paper|stop(s)? your paper|no more paper/i);
  });

  it("DEF-CWP-9079 — the paperless box arrives UNTICKED: consent is the applicant's act, never the screen's", async () => {
    // Decision log 2026-08-31: every delivery election is NOT NULL DEFAULT
    // FALSE (opt-in, hard-won law 3). BR-CWP-087: paperless is a RECORDED
    // consent. A box that arrives ticked records one nobody gave.
    const { container } = draw();
    await reachCheckAndSend(container);
    const tick = container.querySelector("#paperless") as HTMLInputElement;
    expect(tick.checked).toBe(false);
  });

  it("TC-1 — sending it TICKED submits with the consent and shows the reference", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    const tick = container.querySelector("#paperless") as HTMLInputElement;
    const user = userEvent.setup();
    await user.click(tick);
    expect(tick.checked).toBe(true);
    await user.click(screen.getByRole("button", { name: /send my application/i }));
    await waitFor(() => expect(submits).toEqual([true]));
    await waitFor(() => expect(screen.getByText("SR-26-0051")).toBeInTheDocument());
  });

  it("TC-2 — sending it UNTICKED still succeeds, and the screen says no consent was taken", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    const user = userEvent.setup();
    // Arrives unticked (DEF-CWP-9079) — sent as it stands.
    await user.click(screen.getByRole("button", { name: /send my application/i }));
    await waitFor(() => expect(submits).toEqual([false]));
    await waitFor(() => expect(screen.getByText("SR-26-0051")).toBeInTheDocument());
    // ⚠ **AN ABSENT CONSENT IS NOT A WITHDRAWN ONE** and the screen must not
    // read as though one was recorded.
    expect(container.querySelector('[data-screen="CWP-009"]')?.textContent).not.toMatch(
      /you agreed|recorded your agreement/i,
    );
  });

  it("TC-5 — a double click is ONE submit", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    const send = screen.getByRole("button", { name: /send my application/i });
    const user = userEvent.setup();
    await user.click(send);
    await user.click(send);
    await waitFor(() => expect(screen.getByText("SR-26-0051")).toBeInTheDocument());
    expect(submits).toHaveLength(1);
  });

  it("B14 rule 31 — the reference is a human number and no id reaches the screen", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    await userEvent.setup().click(screen.getByRole("button", { name: /send my application/i }));
    await waitFor(() => expect(screen.getByText("SR-26-0051")).toBeInTheDocument());
    // The draft token is a CAPABILITY and the request id is a database id —
    // neither is a thing a person reads.
    expect(container.innerHTML).not.toMatch(/draft-token/);
    expect(container.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    );
  });
});

/**
 * ⚠ **THE JOURNEY THE PRODUCT DID NOT HAVE — `CR-085` task (c).**
 *
 * `/start-service` asked the address and `/start-service/:draft` asked
 * everything else on ONE screen, under a step bar with four labels. So step 3
 * was drawn ✓ **done** on the check screen having never been shown to anybody,
 * and step 1 was announced for the first time on step 2. PO ruling, verbatim:
 * *"please show all 4 screens - address, when , about you, check; and show
 * seperate screens for stop - when you develope you can use same code
 * internally."*
 *
 * Every case below was watched fail against the two-step journey before it was
 * written green (hard-won law 7).
 */
describe("CWP-047 · the four steps, in the order the wireframe draws them", () => {
  /** An application nobody has typed into yet — the first-visit case. */
  const EMPTY: ApplicationDraft = {
    ...DRAFT,
    applicant_kind: null,
    first_name: null,
    last_name: null,
    email: null,
    phone: null,
    date_of_birth: null,
    requested_start: null,
  };

  it("opens on WHEN, which is step 2 and asks the start date", async () => {
    draft = { ...EMPTY };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    expect(
      container.querySelector('[data-stepper] [data-state="current"]')?.getAttribute("data-step"),
    ).toBe("2");
    // The start date, and NOT the name. ⊕ `DEF-CUS-10250` — *person or
    // business* moved to the top of About you (image 04, *"I'm applying as"*).
    expect(container.querySelector('[data-field="requested_start"]')).not.toBeNull();
    expect(container.querySelector('[data-field="applicant_kind"]')).toBeNull();
    expect(container.querySelector('[data-field="first_name"]')).toBeNull();
  });

  /** Type the one thing step 2 asks for. `fireEvent` rather than `userEvent`
   *  because a `<input type="date">` takes a value, not keystrokes. */
  async function answerWhen(container: HTMLElement) {
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    fireEvent.change(container.querySelector("#requested_start") as HTMLInputElement, {
      target: { value: "2026-09-21" },
    });
  }

  it("Continue reaches ABOUT YOU, which is step 3 and asks the name", async () => {
    draft = { ...EMPTY };
    const { container } = draw();
    await answerWhen(container);
    await userEvent.setup().click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    expect(
      container.querySelector('[data-stepper] [data-state="current"]')?.getAttribute("data-step"),
    ).toBe("3");
    expect(container.querySelector('[data-field="first_name"]')).not.toBeNull();
    expect(container.querySelector('[data-field="requested_start"]')).toBeNull();
  });

  it("step 3 draws ONE attach row per document asked for — the DF-4 hold has expired", async () => {
    draft = { ...EMPTY };
    const { container } = draw();
    await answerWhen(container);
    await userEvent.setup().click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    // ⚠ **THIS ASSERTED THE BOX WAS HELD UNTIL 2026-10-01** — the hold-expiry
    // test law 2 asks for, and it fired the day `CR-158-BRC10` landed. The PO
    // superseded `DF-4` for this request: the drawn drop zone is now the
    // product's own `FileDropField`, with a real file input that posts to the
    // draft. The held shape must be GONE, or the screen says two things.
    expect(container.querySelector('[data-photo-picker="held"]')).toBeNull();
    expect(container.querySelector('[data-application-documents] input[type="file"]')).not.toBeNull();
    expect(screen.getByText("PDF, JPG or PNG. Up to 10 MB each. 5 files at most.")).toBeInTheDocument();
    // ⊕ `DEF-CWP-9167` (PO ruling 2026-10-02, option A): one row each, in the
    // server's order, each with its own Attach — one drop box until then.
    expect(
      Array.from(container.querySelectorAll("[data-requirement]"))
        .filter((one) => one.tagName === "DIV")
        .map((one) => one.getAttribute("data-requirement")),
    ).toEqual(["photo_id", "proof_of_address"]);
    expect(screen.getByRole("button", { name: "Attach Photo ID" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Attach Proof of address" })).toBeInTheDocument();
  });

  it("a part-finished draft opens on the step that is NOT finished, and says so", async () => {
    // Everything but the name — wireframe s19, *"picked up where you left
    // off"*: the unfinished step IS the page, not a checklist about it.
    draft = { ...DRAFT, first_name: null, last_name: null };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    expect(
      container.querySelector('[data-stepper] [data-state="current"]')?.getAttribute("data-step"),
    ).toBe("3");
    expect(screen.getByText(/picked up where you left off/i)).toBeInTheDocument();
    // And what is already answered is beside it, with the way back to it.
    expect(container.querySelector('[data-change="start"]')).not.toBeNull();
  });

  it("a first visit is NOT told it was picked up where it left off", async () => {
    // The draft does not exist yet: `getDraft` refuses, the screen seeds one.
    draftMissing = true;
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    expect(screen.queryByText(/picked up where you left off/i)).toBeNull();
  });

  it("each Change link on the check screen returns to the step it came from", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    const user = userEvent.setup();
    await user.click(container.querySelector('[data-change="about"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
    await user.click(container.querySelector('[data-change="when"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
  });

  it("the start date reaches the applicant in the TENANT's format, not the wire's", async () => {
    // ⚠ `DEF-CWP-4193` / `DEF-CWP-4204`'s family. It printed `2026-09-21` — the
    // wire's own string — on the last screen before a request that starts a
    // legal supply. Waves M and L took this fix; start-service was never moved.
    const { container } = draw({ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" });
    await reachCheckAndSend(container);
    expect(container.querySelector('[data-kv="start"] dd')?.textContent).toBe("09/21/2026");
  });
});

/**
 * ⚠ **THE SIX ASTERISKS THAT GATED NOTHING — `DEF-CWP-4877`, high.**
 *
 * Walked in a browser on 2026-09-11: `Continue →` was live on step 2 with no
 * date and on step 3 with all five boxes empty, so an applicant reached the
 * commit, read back `Applicant —`, `Email —`, `Mobile —`, pressed **Send my
 * application ✓** and was answered *"Finish an earlier step first."* — five
 * words naming no step and no field. The server had sent the step all along
 * (`params={"step":"name"}`) under a comment reading *"The refusal names the
 * step"*; the catalogue sentence had no placeholder, so i18next dropped it.
 *
 * Every case below was watched FAIL against the build of 2026-09-11 before it
 * was written green (hard-won law 7). The first two were failing already: the
 * two pre-existing cases above clicked `Continue` on an empty draft and
 * reached step 3, which is the defect, and they now answer the step first.
 */
describe("CWP-047 · a step that is not finished HOLDS its way forward (DEF-CWP-4877)", () => {
  const EMPTY: ApplicationDraft = {
    ...DRAFT,
    applicant_kind: null,
    first_name: null,
    last_name: null,
    email: null,
    phone: null,
    date_of_birth: null,
    requested_start: null,
  };

  const continueButton = (container: HTMLElement) =>
    container.querySelector('[data-action="continue"]') as HTMLButtonElement;

  it("step 2 · no start date means Continue is held, and the reason is ON SCREEN", async () => {
    draft = { ...EMPTY };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    expect(continueButton(container).disabled).toBe(true);
    // ⚠ **VISIBLE TEXT, NOT ONLY `title` — the portal's design target is a
    // 390px phone and nobody can hover a tooltip on one.** `BR-CWP-056` asks
    // for *disabled WITH the reason*; a `title` alone is half of that.
    const reason = container.querySelector('[data-step-held="start_date"]');
    expect(reason).not.toBeNull();
    expect(reason?.textContent).toBe("Choose a start date first.");
    expect(continueButton(container).getAttribute("title")).toBe("Choose a start date first.");
  });

  it("step 2 · typing the date releases it", async () => {
    draft = { ...EMPTY };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    fireEvent.change(container.querySelector("#requested_start") as HTMLInputElement, {
      target: { value: "2026-09-21" },
    });
    await waitFor(() => expect(continueButton(container).disabled).toBe(false));
    expect(container.querySelector("[data-step-held]")).toBeNull();
  });

  it("step 3 · an empty form holds Continue, and the reason names what is missing", async () => {
    draft = { ...EMPTY, requested_start: "2026-09-21" };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    expect(continueButton(container).disabled).toBe(true);
    expect(container.querySelector('[data-step-held="name"]')?.textContent).toBe(
      "Add your name first.",
    );
  });

  it("step 3 · the name alone is not enough — it then asks for the contact", async () => {
    draft = { ...EMPTY, requested_start: "2026-09-21" };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    const user = userEvent.setup();
    await user.type(container.querySelector("#first_name") as HTMLElement, "Daniel");
    await user.type(container.querySelector("#last_name") as HTMLElement, "Okafor");
    // ⊕ `DEF-CUS-10250` — EMAIL IS OPTIONAL (PO 2026-10-18, Move-in's rule);
    // the mobile number is what the step holds on.
    await waitFor(() =>
      expect(container.querySelector('[data-step-held="contact"]')?.textContent).toBe(
        "Add a valid cell number.",
      ),
    );
    expect(continueButton(container).disabled).toBe(true);
    await user.type(container.querySelector("#phone") as HTMLElement, "5125557730");
    await waitFor(() => expect(continueButton(container).disabled).toBe(false));
  });

  it("the date of birth is NOT required — the server accepts an application without one", async () => {
    // ⚠ The asterisk used to be on it and `missing_before_submit` never asked
    // for it, so the screen was refusing applications the product accepts.
    draft = { ...EMPTY, requested_start: "2026-09-21" };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    const user = userEvent.setup();
    await user.type(container.querySelector("#first_name") as HTMLElement, "Daniel");
    await user.type(container.querySelector("#last_name") as HTMLElement, "Okafor");
    await user.type(container.querySelector("#email") as HTMLElement, "d.okafor@example.com");
    await user.type(container.querySelector("#phone") as HTMLElement, "5125557730");
    await waitFor(() => expect(continueButton(container).disabled).toBe(false));
    expect((container.querySelector("#date_of_birth") as HTMLInputElement).value).toBe("");
    expect(
      container.querySelector('[data-field="date_of_birth"] label')?.textContent,
    ).not.toContain("*");
  });

  it("the commit is HELD rather than pressed-and-refused", async () => {
    // The applicant cannot get here from inside the product any more, but a
    // reopened link on a half-finished draft can land on step 4 — and a commit
    // that could only ever be refused is not a commit.
    draft = { ...DRAFT, email: null, phone: null };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    // Jump to the review step the way the rail's Change link does.
    await userEvent.setup().click(container.querySelector('[data-change="start"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
  });

  it("a refusal from the server NAMES the step and offers the way back to it", async () => {
    submitRefusal = new ApiError(422, {
      code: "VAL-001",
      message_key: "portal.application.stepIncomplete",
      params: { step: "name" },
      field_errors: [],
      br_ref: null,
      trace_id: "2a87780a7f5a41f08de98bd3642e1c49",
    });
    const { container } = draw();
    await reachCheckAndSend(container);
    await userEvent.setup().click(screen.getByRole("button", { name: /send my application/i }));
    await waitFor(() => expect(container.querySelector("[data-send-error]")).not.toBeNull());
    const panel = container.querySelector("[data-send-error]") as HTMLElement;
    // ⚠ The STEP NUMBER, never `params.step` — `name`, `start_date` and
    // `company_name` are internal names and B14 rule 31 keeps those off a
    // customer's screen.
    expect(panel.textContent).toContain("Finish step 3 first.");
    expect(panel.textContent).not.toContain("name.");
    // R-10 — the way out is INSIDE the panel, next to the message.
    const back = panel.querySelector('[data-action="fix-step"]') as HTMLButtonElement;
    expect(back).not.toBeNull();
    expect(back.textContent).toBe("Go to About you →");
    await userEvent.setup().click(back);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
  });

  it("any OTHER refusal still renders its own sentence, unchanged", async () => {
    submitRefusal = new ApiError(422, {
      code: "VAL-002",
      message_key: "portal.application.startTooSoon",
      params: { days: 3 },
      field_errors: [],
      br_ref: null,
      trace_id: null,
    });
    const { container } = draw();
    await reachCheckAndSend(container);
    await userEvent.setup().click(screen.getByRole("button", { name: /send my application/i }));
    await waitFor(() => expect(container.querySelector("[data-send-error]")).not.toBeNull());
    const panel = container.querySelector("[data-send-error]") as HTMLElement;
    expect(panel.textContent).toContain("Choose a later start date.");
    expect(panel.querySelector('[data-action="fix-step"]')).toBeNull();
  });
});

/**
 * ⚠ **`DEF-CWP-4876` — STEPS 2, 3 AND 4 DREW NO HEADING AT ALL.** Measured in
 * a browser at 1280 and at 390: `h1` count **0**, `.page-header` nodes **0**.
 * After step 1 nothing on screen said which address was being applied for.
 */
describe("CWP-047 · every step carries its drawn title and the address (DEF-CWP-4876)", () => {
  const EMPTY: ApplicationDraft = {
    ...DRAFT,
    applicant_kind: null,
    first_name: null,
    last_name: null,
    email: null,
    phone: null,
    date_of_birth: null,
    requested_start: null,
  };

  /** The whole first-visit walk, one step at a time — which is also the only
   *  way to reach steps 3 and 4 now that the gates are real. */
  async function walkTo(container: HTMLElement, step: "when" | "about" | "review") {
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    if (step === "when") return;
    const user = userEvent.setup();
    fireEvent.change(container.querySelector("#requested_start") as HTMLInputElement, {
      target: { value: "2026-09-21" },
    });
    await waitFor(() =>
      expect(
        (container.querySelector('[data-action="continue"]') as HTMLButtonElement).disabled,
      ).toBe(false),
    );
    await user.click(container.querySelector('[data-action="continue"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    if (step === "about") return;
    await user.type(container.querySelector("#first_name") as HTMLElement, "Daniel");
    await user.type(container.querySelector("#last_name") as HTMLElement, "Okafor");
    await user.type(container.querySelector("#email") as HTMLElement, "d.okafor@example.com");
    await user.type(container.querySelector("#phone") as HTMLElement, "5125557730");
    // ⊕ `DEF-CUS-10250` — NO category on the portal any more (PO 2026-10-18,
    // *"this is correct"*: staff set it before approving), so nothing holds.
    expect(container.querySelector("#account_type_code")).toBeNull();
    await waitFor(() =>
      expect(
        (container.querySelector('[data-action="continue"]') as HTMLButtonElement).disabled,
      ).toBe(false),
    );
    await user.click(container.querySelector('[data-action="continue"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
  }

  it("step 2 · the title is the drawn one and the sub-line carries the address", async () => {
    draft = { ...EMPTY };
    const { container } = drawFirstVisit();
    await walkTo(container, "when");
    const screenEl = container.querySelector('[data-screen="CWP-047"]') as HTMLElement;
    // ⚠ **INSIDE the `data-screen` mark**, which is where `PortalScreen` puts
    // a head and where a rendered check can see it (`DEF-CWP-4926`).
    expect(screenEl.querySelector("h1")?.textContent).toBe("When would you like it on?");
    expect(screenEl.textContent).toContain("31 Palm Ct · step 2 of 4");
  });

  it("step 2 BEFORE the draft exists — the head still names the address (DEF-CWP-4876, residual)", async () => {
    // ⚠ **THE ONE CASE THE BROWSER FAILED WHILE THE SUITE WAS GREEN.** A first
    // visit lands on step 2 with NO draft: step 1 passes the address in the
    // address bar and the draft is not written until the seeding save comes
    // back. Reading the address off the draft alone left the head saying
    // *"Step 2 of 4"* and naming no address — on the exact screen this defect
    // is about, whose complaint was that after step 1 nothing says which
    // address is being applied for. Every other case here let `saveDraft`
    // answer instantly, so all three passed over the seeded state.
    draft = { ...EMPTY };
    saveHangs = true;
    const { container } = drawFirstVisit();
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-047"]')).not.toBeNull(),
    );
    const screenEl = container.querySelector('[data-screen="CWP-047"]') as HTMLElement;
    expect(screenEl.querySelector("h1")?.textContent).toBe("When would you like it on?");
    expect(screenEl.textContent).toContain("31 Palm Ct · step 2 of 4");
  });

  it("step 3 · the same, and it says step 3", async () => {
    draft = { ...EMPTY };
    const { container } = drawFirstVisit();
    await walkTo(container, "about");
    const screenEl = container.querySelector('[data-screen="CWP-047"]') as HTMLElement;
    expect(screenEl.querySelector("h1")?.textContent).toBe("About you");
    expect(screenEl.textContent).toContain("31 Palm Ct · step 3 of 4");
  });

  it("step 4 · the same, and it says step 4", async () => {
    draft = { ...EMPTY };
    const { container } = drawFirstVisit();
    await walkTo(container, "review");
    const screenEl = container.querySelector('[data-screen="CWP-009"]') as HTMLElement;
    expect(screenEl.querySelector("h1")?.textContent).toBe("Check this, then send it");
    expect(screenEl.textContent).toContain("31 Palm Ct · step 4 of 4");
  });

  it("exactly ONE heading per step — the section title is not a second copy of it", async () => {
    draft = { ...EMPTY };
    const { container } = drawFirstVisit();
    await walkTo(container, "when");
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    // The small-caps `WHEN WOULD YOU LIKE IT ON?` that used to open the card
    // is gone: wireframe s16 draws the sentence once, at the top.
    expect(container.textContent?.match(/When would you like it on\?/g)).toHaveLength(1);
  });

  it("a RESUMED applicant keeps s19's own head, which also carries the address", async () => {
    draft = { ...DRAFT, first_name: null, last_name: null };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    const screenEl = container.querySelector('[data-screen="CWP-047"]') as HTMLElement;
    expect(screenEl.querySelector("h1")?.textContent).toBe("Picked up where you left off");
    expect(screenEl.textContent).toContain("You started this for 31 Palm Ct.");
    // ⚠ And THEN the step is named in the body, which is what s19 draws:
    // *"ABOUT YOU — THE PART YOU DID NOT FINISH"*.
    expect(screenEl.textContent).toContain("About you");
  });
});

/**
 * ⚠ **`DEF-CWP-4875` — `— deposit on your first bill.`** A `kind: "none"`
 * money cell carries `display: null` on purpose, and the screen interpolated
 * `?? "—"` into a SENTENCE. A table cell may be a dash; a sentence may not.
 */
describe("CWP-047 · nothing to quote is a line that is ABSENT (DEF-CWP-4875)", () => {
  it("the deposit sentence is gone, not drawn with an em dash", async () => {
    availability = {
      ...AVAILABILITY,
      if_you_apply: {
        before_we_start: { kind: "amount", amount: "90.0000", display: "$90.00", currency: "USD" },
        on_first_bill: { kind: "none", amount: null, display: null, currency: null },
        working_days: 3,
      },
    };
    draft = { ...DRAFT, requested_start: null };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    await waitFor(() =>
      expect(container.querySelector("[data-consequence]")?.textContent).toContain("$90.00"),
    );
    const bullets = [...container.querySelectorAll("[data-consequence] li")].map(
      (li) => li.textContent ?? "",
    );
    // The two that are TRUE survive; the one with nothing to quote is absent.
    expect(bullets).toEqual(["$90.00 before we start.", "About 3 working days."]);
    // ⚠ The assertion that would have caught it on the day: no sentence on
    // this screen begins with an em dash.
    expect(bullets.some((one) => one.trimStart().startsWith("—"))).toBe(false);
  });

  it("and the deposit IS drawn when there is one to quote", async () => {
    draft = { ...DRAFT, requested_start: null };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    await waitFor(() =>
      expect(container.querySelector("[data-consequence]")?.textContent).toContain("$150.00"),
    );
    const bullets = [...container.querySelectorAll("[data-consequence] li")].map(
      (li) => li.textContent ?? "",
    );
    expect(bullets).toContain("$150.00 deposit on your first bill.");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CWP-4930 — an address we do not hold can be APPLIED FOR, to the end
// ══════════════════════════════════════════════════════════════════════════
// It could not be sent: there were no rows, so the draft carried no services
// and the submit was refused on a step the applicant was never shown. The
// promise *"You can still apply"* was true of the first press and false of the
// last, and the walkthrough stopped short of the last (the defect's own
// escape reason). So this case presses SEND.
describe("CWP-047 · an address we do not hold — the applicant ticks the services (DEF-CWP-4930)", () => {
  const UNMATCHED: Availability = {
    matched: false,
    address: "77 Nowhere Ln",
    job: null,
    rows: [],
    if_you_apply: null,
    offered: [
      { service_code: "water", service_name: "Water" },
      { service_code: "sewer", service_name: "Sewer" },
      { service_code: "trash", service_name: "Trash" },
    ],
  };

  it("step 2 offers the utility's services to tick, holds Continue until one is ticked, and the ticks are what is sent", async () => {
    availability = UNMATCHED;
    applyPatches = true;
    draft = {
      ...DRAFT,
      address_as_given: "77 Nowhere Ln",
      service_codes: [],
      requested_start: "2026-09-21",
    };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    await waitFor(() =>
      expect(container.querySelectorAll("[data-service-pick] input[type=checkbox]")).toHaveLength(3),
    );
    // "there is nothing to choose" is false where the applicant IS choosing.
    expect(container.querySelector("[data-services-note]")).toBeNull();
    const go = () => container.querySelector('[data-action="continue"]') as HTMLButtonElement;
    expect(go().disabled).toBe(true);
    expect(container.querySelector('[data-step-held="services"]')?.textContent).toBe(
      // `DEF-CWP-9123` — American English (DEF-SHL-6351): a box is selected.
      "Select a service first.",
    );
    fireEvent.click(container.querySelector('[data-service-pick="water"] input') as HTMLInputElement);
    await waitFor(() => expect(draft.service_codes).toEqual(["water"]));
    fireEvent.click(container.querySelector('[data-service-pick="trash"] input') as HTMLInputElement);
    await waitFor(() => expect(draft.service_codes).toEqual(["water", "trash"]));
    await waitFor(() => expect(go().disabled).toBe(false));
    // Un-ticking takes it back off.
    fireEvent.click(container.querySelector('[data-service-pick="trash"] input') as HTMLInputElement);
    await waitFor(() => expect(draft.service_codes).toEqual(["water"]));
    fireEvent.click(go());
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    fireEvent.click(container.querySelector('[data-action="continue"]') as HTMLButtonElement);
    await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
    // The check screen restates what was TICKED, by name.
    expect(container.querySelector('[data-kv="services"] dd')?.textContent).toBe("Water");
    fireEvent.click(container.querySelector('[data-action="send"]') as HTMLButtonElement);
    await waitFor(() => expect(submits).toHaveLength(1));
  });

  it("a HELD address still offers nothing to tick — the address decides", async () => {
    availability = { ...AVAILABILITY, offered: [] };
    draft = { ...DRAFT, requested_start: null };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    expect(container.querySelector("[data-service-pick]")).toBeNull();
  });
});

/**
 * ⚠ **THE FIVE DEFECTS THE PO REPORTED WITH SCREENSHOTS ON 2026-10-02** —
 * decision log *"PORTAL START-SERVICE FORM — FIVE DEFECTS"*. Each case was
 * watched FAIL against the build before the fix (`2.455.0`, tip `61808f615`)
 * and then written green (hard-won law 7).
 */
describe("CWP-047 · the PO's start-service defects of 2026-10-02", () => {
  /** Open step 3 from a finished draft, by its Change link. */
  async function openStep3(container: HTMLElement) {
    await reachCheckAndSend(container);
    fireEvent.click(container.querySelector('[data-change="about"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
  }

  it("DEF-CWP-9167 — a file chosen on a row is sent AS that requirement and listed under it", async () => {
    const { container } = draw();
    await openStep3(container);
    const idInput = container.querySelector('[data-attach-input="photo_id"]') as HTMLInputElement;
    fireEvent.change(idInput, {
      target: { files: [new File(["png"], "licence.png", { type: "image/png" })] },
    });
    await waitFor(() =>
      expect(
        container.querySelector('div[data-requirement="photo_id"] [data-attached-file="licence.png"]'),
      ).not.toBeNull(),
    );
    const addressInput = container.querySelector(
      '[data-attach-input="proof_of_address"]',
    ) as HTMLInputElement;
    fireEvent.change(addressInput, {
      target: { files: [new File(["%PDF"], "power-bill.pdf", { type: "application/pdf" })] },
    });
    await waitFor(() =>
      expect(
        container.querySelector(
          'div[data-requirement="proof_of_address"] [data-attached-file="power-bill.pdf"]',
        ),
      ).not.toBeNull(),
    );
    expect(uploadedRequirements).toEqual(["photo_id", "proof_of_address"]);
  });

  it("DEF-CWP-9166 — step 3 has View beside Remove, and View opens the applicant's own file", async () => {
    const opened: string[] = [];
    const spy = vi.spyOn(window, "open").mockImplementation((url) => {
      opened.push(String(url));
      return null;
    });
    window.history.pushState({}, "", "/pine-hill/portal/start-service/draft-token");
    const { container } = draw();
    await openStep3(container);
    fireEvent.change(container.querySelector('[data-attach-input="photo_id"]') as HTMLInputElement, {
      target: { files: [new File(["png"], "licence.png", { type: "image/png" })] },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "View licence.png" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Remove licence.png" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "View licence.png" }));
    expect(opened).toEqual([
      "/api/pine-hill/portal/public/applications/draft-token/documents/doc-1/content?as=view",
    ]);
    spy.mockRestore();
    window.history.pushState({}, "", "/");
  });

  it("DEF-CWP-9163 — Same as the service address is ticked; unticking asks for the address and HOLDS Continue until it is whole", async () => {
    applyPatches = true;
    const { container } = draw();
    await openStep3(container);
    const same = container.querySelector("#mailing_same") as HTMLInputElement;
    // ⊕ `DEF-CUS-10250` — Move-in's block in the portal look (image 04): a
    // section titled *Mailing address* with *Same as service address* ticked.
    expect(screen.getAllByText("Mailing address").length).toBeGreaterThan(0);
    expect(same.checked).toBe(true);
    expect(container.querySelector("[data-mailing-fields]")).toBeNull();
    fireEvent.click(same);
    await waitFor(() => expect(container.querySelector("[data-mailing-fields]")).not.toBeNull());
    const go = () => container.querySelector('[data-action="continue"]') as HTMLButtonElement;
    expect(go().disabled).toBe(true);
    expect(container.querySelector('[data-step-held="mailing"]')?.textContent).toBe(
      "Add your mailing address.",
    );
    const type = (id: string, value: string) => {
      const box = container.querySelector(`#${id}`) as HTMLInputElement;
      fireEvent.change(box, { target: { value } });
      fireEvent.blur(box);
    };
    type("mailing_line1", "PO Box 4417");
    type("mailing_city", "Ottumwa");
    fireEvent.change(container.querySelector("#mailing_state") as HTMLSelectElement, {
      target: { value: "IA" },
    });
    type("mailing_postal_code", "5250");
    // A slip in the ZIP is caught on the field and still holds the step.
    expect(screen.getByText("Use 12345 or 12345-6789.")).toBeInTheDocument();
    expect(go().disabled).toBe(true);
    type("mailing_postal_code", "52501");
    await waitFor(() => expect(go().disabled).toBe(false));
    // What was sent is the draft's own field names, and the box is unticked.
    await waitFor(() => expect(draft.mailing_postal_code).toBe("52501"));
    expect(draft.mailing_same_as_service).toBe(false);
    expect(draft.mailing_line1).toBe("PO Box 4417");
    expect(draft.mailing_state).toBe("IA");
    fireEvent.click(go());
    await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
    expect(container.querySelector('[data-kv="mailing"] dd')?.textContent).toBe(
      "PO Box 4417, Ottumwa, IA 52501",
    );
  });

  it("DEF-CWP-9163 — with the box ticked Check and send says the bill goes to the service address", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(container.querySelector('[data-kv="mailing"] dd')?.textContent).toBe(
      "Same as the service address",
    );
  });

  it("DEF-CWP-9164 — Back is on the LEFT and the commit on the RIGHT, on steps 3 and 4", async () => {
    const { container } = draw();
    await reachCheckAndSend(container);
    const side = (action: string) =>
      container
        .querySelector(`[data-action="${action}"]`)
        ?.closest("[data-footer-side]")
        ?.getAttribute("data-footer-side");
    expect(side("back")).toBe("back");
    expect(side("send")).toBe("forward");
    const footer = container.querySelector("[data-wizard-footer]") as HTMLElement;
    const order = Array.from(footer.querySelectorAll("[data-action]")).map((one) =>
      one.getAttribute("data-action"),
    );
    expect(order).toEqual(["back", "send"]);
    fireEvent.click(container.querySelector('[data-change="about"]') as HTMLElement);
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    expect(side("back")).toBe("back");
    expect(side("continue")).toBe("forward");
  });

  it("DEF-CWP-9165 — an address we do not hold says 'We will tell you', never a bare dash", async () => {
    availability = {
      matched: false,
      address: "77 Nowhere Ln",
      job: null,
      rows: [],
      if_you_apply: null,
      offered: [{ service_code: "water", service_name: "Water" }],
    };
    draft = { ...DRAFT, address_as_given: "77 Nowhere Ln", service_codes: ["water"] };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
    await waitFor(() =>
      expect(container.querySelector('[data-kv="before_we_start"] dd')?.textContent).toBe(
        "We will tell you",
      ),
    );
    expect(container.querySelector('[data-kv="on_first_bill"] dd')?.textContent).toBe(
      "We will tell you",
    );
  });

  it("DEF-CWP-9165 — a held address whose plan charges no deposit says 'No deposit'", async () => {
    availability = {
      ...AVAILABILITY,
      if_you_apply: {
        before_we_start: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
        on_first_bill: { kind: "none", amount: null, display: null, currency: null },
        working_days: 2,
      },
    };
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(container.querySelector('[data-kv="before_we_start"] dd')?.textContent).toBe("$0.00");
    expect(container.querySelector('[data-kv="on_first_bill"] dd')?.textContent).toBe("No deposit");
  });
});

describe("CWP-047 · the address in US form and the applicant's category (DEF-CWP-9817, DEF-CWP-9818)", () => {
  /** The server's composed line — the matched premises' address, the unit the
   *  applicant's label. The screen prints it and never re-composes it. */
  const LINE = "1841 Quarry Hill Ct, Apt 12, Silver Creek, TX 78611";

  it("the rail and Check and send show the US-format line, not what was typed", async () => {
    // The PO's screenshot: the rail read exactly what was typed in one box.
    draft = {
      ...DRAFT,
      address_as_given: "Haustin Towers 2",
      address_unit_as_given: "Apt 12",
      service_address: LINE,
    };
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(container.querySelector('[data-kv="address"] dd')?.textContent).toBe(LINE);
    // The unit is INSIDE the line, so no second Unit row repeats it.
    expect(container.querySelector('[data-kv="unit"]')).toBeNull();
    expect(container.textContent).not.toContain("Haustin Towers 2");
  });

  it("step 3's rail carries the same line", async () => {
    draft = { ...DRAFT, first_name: null, service_address: LINE, address_unit_as_given: "Apt 12" };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    const rail = container.querySelector("[data-twocol-rail]") as HTMLElement;
    expect(rail.querySelector('[data-kv="address"] dd')?.textContent).toBe(LINE);
  });

  // ⊕ **`DEF-CUS-10250` — SUPERSEDED, AND REPLACED RATHER THAN DELETED.**
  // Two cases stood here asserting that step 3 offered Category and
  // Sub-category and that Check and send restated the pick (`DEF-CWP-9818`, PO
  // ruling 2026-10-06 (b)). The PO ruled the opposite on 2026-10-18 (*"this is
  // correct"* to *"the portal version … does NOT ask the customer for internal
  // classifications … staff set the category when they review the request"*),
  // so the cases now assert the absence on both screens.
  it("step 3 asks NO category and no sub-category", async () => {
    draft = { ...DRAFT, first_name: null, account_type_code: null };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="about"]')).not.toBeNull());
    expect(container.querySelector("#account_type_code")).toBeNull();
    expect(container.querySelector("#account_subtype_code")).toBeNull();
  });

  it("Check and send restates no category", async () => {
    draft = { ...DRAFT, account_type_code: "commercial", account_subtype_code: "healthcare" };
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(container.querySelector('[data-kv="category"]')).toBeNull();
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// CR-191-BRC10 (PO 2026-10-23) — a fee above $0.00 is paid by card on the last
// step, before the application is sent; $0.00 means no payment step.
// ═══════════════════════════════════════════════════════════════════════════
describe("CWP-009 · the application fee is paid online (CR-191-BRC10)", () => {
  const TEN = { kind: "amount" as const, amount: "10.0000", display: "$10.00", currency: "USD" };

  it("a $10.00 fee draws the card, Pay $10.00 and submit, and the not-refunded consequence", async () => {
    availability = { ...AVAILABILITY, application_fee: TEN, card_payment_available: true };
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(container.querySelector("[data-fee-card]")).not.toBeNull();
    expect(screen.getByLabelText(/card number/i)).toBeInTheDocument();
    const pay = screen.getByRole("button", { name: "Pay $10.00 and submit ✓" });
    // Held until the three boxes are filled, and the reason is ON SCREEN.
    expect(pay).toBeDisabled();
    expect(container.querySelector("[data-card-held]")?.textContent).toBe(
      "Fill in the card boxes first.",
    );
    const box = container.querySelector('[data-screen="CWP-009"]')?.textContent ?? "";
    expect(box).toContain("Your card is charged $10.00 now.");
    expect(box).toContain("The fee is not refunded.");
    expect(box).not.toContain("Nothing is charged today.");
  });

  it("paying sends a token, never the card number, with the fee seen and one attempt token", async () => {
    availability = { ...AVAILABILITY, application_fee: TEN, card_payment_available: true };
    answer = { ...answer, fee_paid: TEN };
    const { container } = draw();
    await reachCheckAndSend(container);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/card number/i), "4242 4242 4242 4242");
    await user.type(screen.getByLabelText(/expires/i), "11/27");
    await user.type(screen.getByLabelText(/security code/i), "123");
    const pay = screen.getByRole("button", { name: "Pay $10.00 and submit ✓" });
    expect(pay).not.toBeDisabled();
    await user.click(pay);
    await waitFor(() => expect(payments).toHaveLength(1));
    const sent = payments[0] as { instrument: Record<string, string>; fee_amount: string; attempt_token: string };
    expect(sent.fee_amount).toBe("10.0000");
    expect(sent.instrument.last_four).toBe("4242");
    expect(JSON.stringify(sent)).not.toContain("4242 4242");
    expect(JSON.stringify(sent)).not.toContain("123");
    expect(sent.attempt_token).toMatch(/.{8,}/);
    // The Sent panel states the fee received.
    await waitFor(() =>
      expect(screen.getByText("We received your $10.00 application fee.")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Nothing is charged today.")).toBeNull();
  });

  it("a utility that cannot take a card says so and holds the button", async () => {
    availability = { ...AVAILABILITY, application_fee: TEN, card_payment_available: false };
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(container.querySelector("[data-card-unavailable]")?.textContent).toBe(
      "Card payment is not available.",
    );
    expect(screen.queryByLabelText(/card number/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Pay $10.00 and submit ✓" })).toBeDisabled();
  });

  it("a $0.00 fee shows no payment step and keeps Nothing is charged today", async () => {
    availability = {
      ...AVAILABILITY,
      application_fee: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
      card_payment_available: false,
    };
    const { container } = draw();
    await reachCheckAndSend(container);
    expect(container.querySelector("[data-fee-card]")).toBeNull();
    expect(container.textContent).toContain("Nothing is charged today.");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /send my application/i }));
    await waitFor(() => expect(payments).toEqual([null]));
  });

  it("a declined card shows the customer's sentence and stays on the step", async () => {
    availability = { ...AVAILABILITY, application_fee: TEN, card_payment_available: true };
    submitRefusal = new ApiError(409, {
      code: "BIZ-001",
      message: "",
      message_key: "portal.quickPay.declined",
      params: {},
      br_ref: "BR-INT-018",
      trace_id: "t",
    } as never);
    const { container } = draw();
    await reachCheckAndSend(container);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/card number/i), "4000 0000 0000 0002");
    await user.type(screen.getByLabelText(/expires/i), "11/27");
    await user.type(screen.getByLabelText(/security code/i), "123");
    await user.click(screen.getByRole("button", { name: "Pay $10.00 and submit ✓" }));
    await waitFor(() => expect(screen.getByText("The card was declined.")).toBeInTheDocument());
    expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull();
  });
});
