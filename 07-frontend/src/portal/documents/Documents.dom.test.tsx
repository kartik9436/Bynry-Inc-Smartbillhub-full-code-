// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-036 (EP-CWP-07) · Screen: CWP-031
// Rules:    BR-CWP-083 (post and email remain the DELIVERY RECORD) ·
//           BR-CWP-045 (documents are SERVED, never re-rendered) ·
//           BR-CWP-056 (held WITH its reason, never hidden) · B14 rule 20
//           (one table) · rule 31 (no database id on screen) · rule 32 (one
//           sentence per section) · rule 33 (a refusal is five or six words)
// Cases:    TC-1 newest first with kind and route · TC-2 a bill sent both ways
//           reads Post · Email · TC-3 a receipt by email only · TC-4 the empty
//           state · TC-7 the download control, held with its reason · and the
//           one the screen exists for — it never says a letter arrived
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalDocument, PortalDocuments, PortalListRequest } from "../api/portalClient";

// A plain function, not `vi.fn()` — a recording stand-in notices a rejected
// promise before the screen's own error handling does.
let readDocuments: () => Promise<PortalDocuments> = async () => {
  throw new Error("no behaviour set");
};
/** Every request, recorded — `DEF-CWP-5747`. Typed as the wrapper's own
 *  option bag, so an assertion about `filters.group` or `year` is checked
 *  against the shape that actually travels rather than against `{}`. */
let asked: (PortalListRequest & { year?: number; accountId?: string | null })[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getDocuments: (_accountId: string, request: Record<string, unknown> = {}) => {
      asked.push(request);
      return readDocuments();
    },
  };
});

const { DocumentsView } = await import("./Documents");

const NOT_REPORTED =
  "no provider reports delivery on any channel, so this says what was sent " +
  "and never that it arrived";

const AUGUST_BILL: PortalDocument = {
  kind: "bill",
  group: "bill",
  reference: "BL-2608-0141",
  sent_on: null,
  queued_on: "2026-08-30",
  // `DEF-CWP-3969` — the facts the row is NAMED from.
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  amount: null,
  currency: null,
  routes: [
    { channel: "pdf_print", state: "queued", reason: null, returned_on: null },
    { channel: "email", state: "queued", reason: null, returned_on: null },
  ],
  state: "queued",
  delivery_reported: false,
  delivery_not_reported_reason: NOT_REPORTED,
  stored_document: { available: true, reason: null },
};

const RECEIPT: PortalDocument = {
  ...AUGUST_BILL,
  kind: "payment_receipt",
  group: "receipt",
  reference: "PMT-2608-0042",
  queued_on: "2026-08-12",
  period_start: null,
  period_end: null,
  amount: "38.4400",
  currency: "USD",
  routes: [{ channel: "email", state: "queued", reason: null, returned_on: null }],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, WHICH IT WAS NOT UNTIL `CPB-14`**
 * (`DEF-CWP-4698`)
 * (CLAUDE.md hard-won law 2, the fixture clause). This file rendered
 * `<DocumentsView>` inside a bare `MemoryRouter` with an `initialEntries` and
 * **no matching `<Route>`**, so `useParams().tenant` was `undefined` — and
 * every address this screen builds would have come out `/api//portal/…`, a
 * protocol-relative URL to another host that reads as a perfectly good string
 * to `toContain`. Nothing in the file noticed, because until this wave the
 * screen built no address at all. It builds two now.
 */
function draw(body: Partial<PortalDocuments>) {
  readDocuments = async () => {
    const rows = body.documents === undefined ? [] : body.documents;
    return {
      documents: [],
      groups: ["bill", "receipt", "letter"],
      unavailable: null,
      // ⚠ **THE THREE WHOLE-SET FACTS THE SERVER SERVES SINCE `DEF-CWP-5747`.**
      // `count` is what the search matched; `populated` is whether this account
      // has ANY post, which `count` cannot say; `any_kept` decides whether
      // `CPB-15`'s *Download a year* is held. Each defaults from the fixture's
      // own rows so no existing case has to state them, and any case that cares
      // overrides.
      count: rows?.length ?? 0,
      page: 1,
      per: 50,
      populated: (rows?.length ?? 0) > 0,
      any_kept: (rows ?? []).some((row) => row.stored_document.available),
      ...body,
    };
  };
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/documents"]}>
      <Routes>
        <Route
          path="/:tenant/portal/documents"
          element={<DocumentsView accountId="acc-1" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * ⚠ **THE SCREEN DRAWS ITS ROWS TWICE AND jsdom APPLIES NO CSS** — the table
 * (`max-md:hidden`) and the phone card list (`md:hidden`) both render every
 * row, so an unscoped `screen.getByText("Post · Email")` finds two nodes and
 * fails on the ambiguity. This is the same helper `Bills.dom.test.tsx` already
 * carries for the same reason, and scoping is not a workaround: every
 * assertion it guards is ABOUT one half or the other, and saying which is what
 * stops the query silently starting to answer with the other.
 */
function desk(container: HTMLElement) {
  return within(container.querySelector("[data-list='CWP-031']") as HTMLElement);
}

/** The phone half, by its own mark. */
function phone(container: HTMLElement) {
  return within(container.querySelector("[data-documents-cards]") as HTMLElement);
}

/** What `usePortalDate` returns with no `TenantRegionalProvider` above it —
 *  the value unchanged (`regional === null` → `return value`). Written out so
 *  the two assertions that compare a route date with a column date compare
 *  like with like, instead of hardcoding a format this test cannot choose. */
const asPortalDate = (iso: string) => iso;

afterEach(cleanup);

describe("CWP-031 · documents and letters (US-CWP-036)", () => {
  it("names every route a document went by, as one row", async () => {
    const { container } = draw({ documents: [AUGUST_BILL] });
    await screen.findByRole("table");
    expect(desk(container).getByText(/Mail · Email/)).toBeInTheDocument();
    // ONE row, not two: the queue's grain is per channel and the customer's is
    // per document (J47 step 4).
    expect(desk(container).getAllByText(/Mail · Email/)).toHaveLength(1);
    // And the phone half says exactly the same thing — one source, two
    // renderings, so the two cannot drift.
    expect(phone(container).getAllByText(/Mail · Email/)).toHaveLength(1);
  });

  it("shows a receipt sent by email only with that one route", async () => {
    const { container } = draw({ documents: [RECEIPT] });
    await screen.findByRole("table");
    expect(desk(container).getByText("Email")).toBeInTheDocument();
    expect(desk(container).queryByText(/Mail · Email/)).not.toBeInTheDocument();
  });

  it("NEVER says a letter arrived — the caveat is on the page and no state reads delivered", async () => {
    draw({ documents: [AUGUST_BILL] });
    // The one sentence this whole screen turns on, said ONCE (B14 rule 32).
    const caveat = await screen.findByText(/cannot confirm that anything arrived/i);
    expect(caveat).toBeInTheDocument();
    // ⚠ **THE STATE CHIP MOVED INTO THE *HOW* CELL** (PO's four-column ruling,
    // 2026-09-11): the fifth column *What we know* is gone and the rollup now
    // sits beside the routes it is derived from, in BOTH renderings.
    expect(screen.getAllByText("Waiting to go")).toHaveLength(2);
    // ⚠ THE ASSERTION THAT WOULD CATCH THE DEFECT THIS SCREEN EXISTS TO AVOID.
    expect(document.body.textContent).not.toMatch(/delivered/i);
    expect(document.body.textContent).not.toMatch(/received by you/i);
  });

  it("puts NO database id on screen, and names the bill by its number", async () => {
    draw({ documents: [AUGUST_BILL] });
    expect(await screen.findByText("BL-2608-0141")).toBeInTheDocument();
    // B14 rule 31 — and DEF-3158: a truncation is the same breach, so the
    // screen must not carry anything uuid-shaped at all.
    expect(document.body.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/i);
  });

  it("says so in words when a document has no reference number", async () => {
    draw({ documents: [{ ...AUGUST_BILL, reference: null }] });
    expect(await screen.findByText("No reference number")).toBeInTheDocument();
  });

  it("names the channel that could not be sent, rather than dropping it", async () => {
    const { container } = draw({
      documents: [
        {
          ...AUGUST_BILL,
          state: "queued",
          routes: [
            { channel: "pdf_print", state: "queued", reason: null, returned_on: null },
            {
              channel: "email",
              state: "could_not_send",
              reason: "no_email_address",
              returned_on: null,
            },
          ],
        },
      ],
    });
    // BR-BIL-036 — "we hold no email address for you" is a normal fact worth
    // telling somebody, not a row to quietly omit.
    await screen.findByRole("table");
    expect(desk(container).getByText(/could not send this by Email/i)).toBeInTheDocument();
    expect(desk(container).getByText(/Mail · Email/)).toBeInTheDocument();
  });

  it("shows a returned letter as a date beside a sent route, never as a state", async () => {
    // ⚠ The chip is read through `data-chip` rather than by its text: *Sent* is
    // also the SENT column's heading, so `getByText("Sent")` matches two nodes
    // and fails on the ambiguity. A test that cannot tell a heading from a
    // value is not asserting the value.
    const { container } = draw({
      documents: [
        {
          ...AUGUST_BILL,
          state: "sent",
          routes: [
            {
              channel: "pdf_print",
              state: "sent",
              reason: null,
              returned_on: "2026-09-08",
            },
          ],
        },
      ],
    });
    // BR-NOT-005 is forward-only: a letter the post office sent back was
    // GENUINELY sent, and rewriting its state would destroy that fact.
    // ⚠ **THE DATE GOES THROUGH THE TENANT'S FORMATTER NOW — `DEF-CWP-4860`.**
    // It was interpolated RAW, so the sentence read *Came back to us on
    // 2026-09-08.* — an ISO string mid-sentence, on a screen whose `SENT`
    // column has gone through `usePortalDate` since `DEF-CWP-3994`: one file,
    // two formats for one kind of fact.
    // ⚠ **WITH NO `TenantRegionalProvider` ABOVE IT, `usePortalDate` IS THE
    // IDENTITY** — so the STRING here is unchanged and a test asserting *"not
    // an ISO string"* would be asserting the provider, not the fix. What can
    // be asserted without one is that this sentence and the `SENT` column now
    // pass through the SAME formatter: they agree, character for character, on
    // a date the two of them draw. Before the fix they could not, because only
    // one of them formatted at all.
    const back = await screen.findAllByText(/Came back to us on /);
    expect(back.length).toBeGreaterThan(0);
    const sentCell = container.querySelector("[data-cell='sent']")?.textContent ?? "";
    expect(sentCell).not.toBe("");
    expect(back[0].textContent).toContain("2026-09-08");
    // The formatter is shared, so the two dates are rendered the same way.
    expect(sentCell).toBe(asPortalDate("2026-08-30"));
    expect(back[0].textContent).toBe(`Came back to us on ${asPortalDate("2026-09-08")}.`);
    const chip = container.querySelector('[data-chip="route-state-sent"]');
    expect(chip).not.toBeNull();
    expect(chip?.textContent).toBe("Sent");
  });

  it("TC-4 · an account with nothing sent gets a sentence naming what will fill it", async () => {
    draw({ documents: [] });
    const empty = await screen.findByText(/Nothing has been sent to you yet/);
    expect(empty).toBeInTheDocument();
    // B14 rule 17 — never a table of dashes, and never an empty <tbody>, which
    // asserts "nothing was ever filed".
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("an UNREACHABLE queue is a different sentence from an empty one", async () => {
    const { container } = draw({ documents: null, unavailable: "the queue is not answering" });
    // `DEF-CWP-10118` — the SENTENCE was cut to B14 rule 33 on 2026-10-11
    // (`d8384030a`, "We cannot reach the record of what we have sent you." →
    // "We can't show what we sent."), and this matcher went red on the words
    // while the state stayed distinct. Asserted by the catalogue key's text AND
    // by the marker and the KIND, so a re-wording cannot fake a regression and
    // an empty list cannot pass for an unreachable one.
    expect(await screen.findByText(/can't show what we sent/i)).toBeInTheDocument();
    expect(container.querySelector("[data-documents-unavailable]")).not.toBeNull();
    expect(container.querySelector("[data-portal-state='failed']")).not.toBeNull();
    expect(container.querySelector("[data-portal-state='empty']")).toBeNull();
    // The whole point of the two branches: a customer of eleven months must
    // not be told nothing was ever sent to them.
    expect(screen.queryByText(/Nothing has been sent to you yet/)).not.toBeInTheDocument();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` `CPB-14` / `CPB-15` — TAKING A COPY OF WHAT WE SENT
  //
  // TC-7 used to assert that *Download a year* was HELD, and it passed for as
  // long as that was true. It is live now, so the case is rewritten rather
  // than deleted: the same control, the opposite assertion, and the held
  // branch kept because it still has a real cause.
  // ═══════════════════════════════════════════════════════════════════════

  it("TC-7 · Download a year is a LIVE address, at this tenant, on this account", async () => {
    const { container } = draw({ documents: [AUGUST_BILL] });
    await screen.findByText("BL-2608-0141");
    const link = container.querySelector("[data-download='documents-year']");
    expect(link).not.toBeNull();
    // ⚠ THE WHOLE ADDRESS, not `toContain` — the fixture note above is the
    // reason. `/api//portal/…` contains `portal/accounts` too.
    expect(link?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/accounts/acc-1/documents/year.zip",
    );
    expect(screen.queryByText("Downloads are not ready yet")).not.toBeInTheDocument();
  });

  it("TC-7b · and it is HELD again when no copy of anything was kept", async () => {
    // ⚠ **A REFUSAL THAT CANNOT ROT.** It is answered by the rows on the screen
    // every time it draws, so unlike the hold it replaces it can never
    // out-live its own reason. An archive of nothing would download an empty
    // file and look like the product working.
    const { container } = draw({
      documents: [
        { ...AUGUST_BILL, stored_document: { available: false, reason: "document_not_stored" } },
      ],
    });
    await screen.findByText("BL-2608-0141");
    expect(container.querySelector("[data-download='documents-year']")).toBeNull();
    expect(screen.getByText("Nothing kept to download yet")).toBeInTheDocument();
  });

  it("CPB-14 · a RECEIPT can be taken away, addressed by the number on it", async () => {
    // ⚠ **THIS IS THE WHOLE WAVE IN ONE ASSERTION.** Before it, the row
    // control for a receipt was disabled with the words *"We kept no copy of
    // this."* — over a receipt whose copy we had kept, which is the sentence
    // beside it on the same row saying the opposite.
    const { container } = draw({ documents: [RECEIPT] });
    await screen.findByText("PMT-2608-0042");
    // DEF-CWP-10566: the row's control is named for its own number.
    const copy = container.querySelector("[data-list='CWP-031'] a[aria-label='Download this document: PMT-2608-0042']");
    expect(copy?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/documents/PMT-2608-0042/file",
    );
    expect(screen.queryByText("We kept no copy of this.")).not.toBeInTheDocument();
  });

  it("CPB-14 · a LETTER with no number says where to get it instead", async () => {
    const { container } = draw({
      documents: [{ ...RECEIPT, group: "letter", kind: null, reference: null }],
    });
    await screen.findAllByText("A letter from us");
    // Disabled, and the reason is the true one: a document with no minted
    // number cannot be addressed one at a time, and the year's archive carries
    // it. It is NOT "we kept no copy", which would be false.
    const copy = container.querySelector(
      "[data-list='CWP-031'] button[aria-label^='Download this document']",
    );
    expect(copy).toBeDisabled();
    expect(copy?.getAttribute("title")).toBe("Use Download a year instead");
  });

  it("CPB-14 · and a document we kept NO copy of still says exactly that", async () => {
    const { container } = draw({
      documents: [
        { ...RECEIPT, stored_document: { available: false, reason: "document_not_stored" } },
      ],
    });
    await screen.findByText("PMT-2608-0042");
    const copy = container.querySelector(
      "[data-list='CWP-031'] button[aria-label^='Download this document']",
    );
    expect(copy).toBeDisabled();
    expect(copy?.getAttribute("title")).toBe("We kept no copy of this.");
  });

  it("CPB-14 · a BILL keeps its framed screen and gains the copy beside it", async () => {
    const { container } = draw({ documents: [AUGUST_BILL] });
    await screen.findByText("BL-2608-0141");
    const open = container.querySelector(
      "[data-list='CWP-031'] a[aria-label^='Open this document']",
    );
    expect(open?.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2608-0141/document");
    const copy = container.querySelector(
      "[data-list='CWP-031'] a[aria-label^='Download this document']",
    );
    expect(copy?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/documents/BL-2608-0141/file",
    );
  });

  it("CPB-14 · a receipt has NO 'open' icon, because there is no screen to open", async () => {
    // ⚠ It is ABSENT rather than permanently refused. A control that can never
    // be used on a row of this kind is not a control (`BR-CWP-045`: nothing
    // here re-renders a receipt, so there is nothing to draw).
    const { container } = draw({ documents: [RECEIPT] });
    await screen.findByText("PMT-2608-0042");
    expect(
      container.querySelector("[data-list='CWP-031'] [aria-label^='Open this document']"),
    ).toBeNull();
  });

  it("says so on the row when no copy of a document was kept", async () => {
    draw({
      documents: [
        { ...AUGUST_BILL, stored_document: { available: false, reason: "document_not_stored" } },
      ],
    });
    // BR-CWP-045 — served, never re-rendered. Where nothing was kept the row
    // states it rather than offering a control that would produce a new one.
    expect(await screen.findByText("No copy kept")).toBeInTheDocument();
  });

  it("calls a document of an unruled class a letter, never the nearest kind", async () => {
    draw({ documents: [{ ...AUGUST_BILL, kind: null, group: "letter" }] });
    // Both renderings name it, and neither guesses a nearer kind.
    expect(await screen.findAllByText("A letter from us")).toHaveLength(2);
    expect(screen.getAllByText("Letter").length).toBeGreaterThan(0);
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `DEF-CWP-3969` — the row is named after the DOCUMENT, not after its kind
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-3969 — a bill is named by the month it covers, not 'A letter from us'", async () => {
    // ⚠ **THIS IS THE CASE NO TEST COULD SEE.** The old cell rendered the kind
    // label, which resolves, is in the catalogue and type-checks — so every
    // assertion written about it passed while five of six live rows read the
    // same six words. The assertion has to be about what DISTINGUISHES the
    // row, which is why it names the period.
    const { container } = draw({ documents: [AUGUST_BILL] });
    await screen.findByText("BL-2608-0141");
    const name = container.querySelector("[data-document-name]")?.textContent ?? "";
    expect(name).toContain("Bill for");
    expect(name).toContain("2026");
    expect(name).not.toBe("A letter from us");
    // The KIND stays in the kind column, where it belongs — and stops being
    // printed twice on one row.
    expect(container.querySelector("[data-cell='kind']")?.textContent).toBe("Bill");
  });

  it("DEF-CWP-3969 — a receipt is named by what it was for", async () => {
    const { container } = draw({ documents: [RECEIPT] });
    await screen.findByText("PMT-2608-0042");
    // Money at TWO displayed places from a 4dp stored figure (hard rule 2).
    expect(container.querySelector("[data-document-name]")?.textContent).toBe(
      "Receipt for $38.44",
    );
  });

  it("DEF-CWP-3969 — six rows, six DIFFERENT names", async () => {
    // The whole complaint in one assertion: a list whose purpose is finding a
    // document must not name its rows identically.
    const { container } = draw({
      documents: [
        AUGUST_BILL,
        { ...AUGUST_BILL, reference: "BL-2607-0132", period_start: "2026-07-01", period_end: "2026-07-31" },
        RECEIPT,
        { ...RECEIPT, reference: "PMT-2607-0031", amount: "112.5000" },
        { ...AUGUST_BILL, kind: "payment_plan_agreement", group: "letter", reference: null },
        { ...AUGUST_BILL, kind: "corrected_bill_notice", group: "letter", reference: null },
      ],
    });
    await screen.findByText("BL-2608-0141");
    const names = Array.from(container.querySelectorAll("[data-document-name]")).map(
      (node) => node.textContent ?? "",
    );
    expect(names).toHaveLength(6);
    expect(new Set(names).size).toBe(6);
  });

  it("DEF-CWP-3969 — a bill with no period served falls back to its kind word", async () => {
    // A name composed around a blank would read *Bill for  – * . The honest
    // answer is the kind word, which is what this cell always had.
    const { container } = draw({
      documents: [{ ...AUGUST_BILL, period_start: null, period_end: null }],
    });
    await screen.findByText("BL-2608-0141");
    expect(container.querySelector("[data-document-name]")?.textContent).toBe("Your bill");
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2 — the ruling, the phone, and the sentence that stated a
  // fact it did not have.
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-4860 — a route with NO returned date makes no bounce claim", async () => {
    // ⚠ **THE GUARD WAS `!== null` OVER A FIELD TYPED `string | null`.** A key
    // ABSENT from the payload arrives as `undefined`, and `undefined !== null`
    // is true — so every row rendered *Came back to us on .*: a statement that
    // the post office returned the customer's bill, with the date blank. `tsc`
    // cannot see it, because the TYPE says the key is there; this is the only
    // place it can be caught.
    // ⚠ **The live server always sends the key**, so this reproduces against a
    // payload shaped like a real one rather than against the running stack —
    // hardening, and said plainly rather than dressed up as a live bug.
    const { container } = draw({
      documents: [
        {
          ...AUGUST_BILL,
          routes: [
            // `returned_on` deliberately ABSENT — the shape a serialiser that
            // drops nulls produces, and the shape the old guard let through.
            { channel: "pdf_print", state: "sent", reason: null } as never,
          ],
        },
      ],
    });
    await screen.findByRole("table");
    expect(container.querySelector("[data-route-returned]")).toBeNull();
    expect(document.body.textContent).not.toContain("Came back to us on .");
  });

  it("PO 2026-09-11 — the table is the blueprint's FOUR columns and no more", async () => {
    // ⚠ **THE RULING, PINNED BY COUNT RATHER THAN BY EYE.** The 8 September
    // blueprint draws `DOCUMENT · KIND · SENT · HOW` and ends every row `↓ PDF`;
    // the build had those four plus *What we know* plus the actions. A test
    // asserting only the four PRESENT would pass on six, so this counts the
    // header row and names the one that left.
    const { container } = draw({ documents: [AUGUST_BILL] });
    await screen.findByRole("table");
    const heads = [...container.querySelectorAll("thead th")].map((th) =>
      (th.textContent ?? "").replace(/[⇅↑↓]/g, "").trim(),
    );
    expect(heads).toHaveLength(5);
    expect(heads.slice(0, 4)).toEqual(["Document", "Kind", "Sent", "How"]);
    expect(container.querySelector("[data-cell='state']")).toBeNull();
    // The chip did not go with the column — it moved beside the routes it is
    // derived from, so *Could not send* is still reachable.
    expect(desk(container).getByText("Waiting to go")).toBeInTheDocument();
  });

  it("at 390 the list is CARDS, and no fact the table shows is lost", async () => {
    // ⚠ **A TABLE DOES NOT BECOME A SMALL TABLE.** At 390 this screen kept its
    // six-column table — 507px of content inside a 316px column — so `HOW`,
    // *What we know* and both row controls sat off the right-hand edge behind a
    // sideways scroll nobody told the customer about. Its sibling `CWP-027`
    // had already solved it with cards. jsdom applies no CSS, so what this can
    // assert is that the card half EXISTS and carries the same four facts; the
    // width itself is a browser walk, not a suite.
    const { container } = draw({ documents: [AUGUST_BILL] });
    await screen.findByRole("table");
    const card = phone(container);
    expect(card.getByText(/Bill for/)).toBeInTheDocument();
    expect(card.getByText(/BL-2608-0141/)).toBeInTheDocument();
    expect(card.getByText("2026-08-30")).toBeInTheDocument();
    expect(card.getByText(/Mail · Email/)).toBeInTheDocument();
    expect(card.getByText("Waiting to go")).toBeInTheDocument();
    // The two row doors, as WORDS — the blueprint's standard A, and 390 is the
    // width where an `aria-label` on an icon reaches nobody at all.
    expect(
      container.querySelector("[data-documents-cards] [data-card-view='BL-2608-0141']"),
    ).not.toBeNull();
    expect(
      container.querySelector("[data-documents-cards] [data-card-download='BL-2608-0141']"),
    ).not.toBeNull();
  });

  it("CPB-15 · the head says HOW MANY, and promises no retention period", async () => {
    // ⚠ **HALF OF `CPB-15`, AND THE HALF WE CAN DERIVE.** The drawing's
    // sub-line is *6 documents · kept for seven years*. The count is on the
    // screen. The retention period is a per-deployment setting nothing serves
    // to the portal, so printing *seven years* would be this screen making a
    // promise about how long a utility keeps its records — a sentence stating
    // a fact it does not have, which is the defect two tests up.
    const { container } = draw({ documents: [AUGUST_BILL, RECEIPT] });
    await screen.findByRole("table");
    expect(container.querySelector("[data-documents-count='2']")?.textContent).toBe("2 documents");
    expect(document.body.textContent).not.toMatch(/seven years|kept for/i);
  });

  it("R-10 · a failed read carries the way out beside the message", async () => {
    // PO 2026-09-11: *"when a screen tells a customer something bad, the thing
    // they can do about it must be on that same screen, next to the message."*
    // It was one grey sentence in a card with nothing to press.
    readDocuments = async () => {
      throw new Error("no");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/documents"]}>
        <Routes>
          <Route path="/:tenant/portal/documents" element={<DocumentsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText(/could not open your documents/i);
    const state = container.querySelector("[data-portal-state='failed']");
    expect(state).not.toBeNull();
    expect(state?.querySelector("[data-way-out='retry']")).not.toBeNull();
    expect(state?.querySelector("[data-way-out='help']")).not.toBeNull();
    // R-22 — the head survives the failure, so the page still says where it is.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Your documents");
  });

  it("R-22 · empty, loading and failed are three different KINDS", async () => {
    // The PO narrowed the blueprint's *"never the same picture"* to
    // *"differntiate it using text message"* — same card, three sentences. The
    // KIND is in the DOM because no check here can read whether a sentence
    // MEANS empty, and without it the rule is unobservable.
    const { container } = draw({ documents: [] });
    await screen.findByText(/Nothing has been sent to you yet/);
    expect(container.querySelector("[data-portal-state='empty']")).not.toBeNull();
    cleanup();
    const second = draw({ documents: null, unavailable: "queue_unreachable" });
    await screen.findByText(/can't show what we sent/i);
    // Nothing is listed, so it LOOKS empty — and it is marked FAILED, because
    // telling a customer of eleven months that we never wrote to them is the
    // thing this branch exists to prevent.
    expect(second.container.querySelector("[data-portal-state='failed']")).not.toBeNull();
    expect(second.container.querySelector("[data-portal-state='empty']")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-5747` — THE PAGE, THE SEARCH, THE CHIPS AND THE SORT ARE THE
// SERVER'S. These assert the REQUEST, never the rows: the rows look the same
// whether the page came from the server or from a browser holding everything
// the utility has ever sent this account.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CWP-5747 · the documents list asks the server for its page", () => {
  afterEach(() => {
    cleanup();
    asked = [];
  });

  it("asks for page 1 of fifty on the first render", async () => {
    draw({ documents: [AUGUST_BILL] });
    await screen.findByTestId("documents");
    expect(asked[0].page).toBe(1);
    expect(asked[0].per).toBe(50);
  });

  it("turns a typed GROUP WORD into the code the server stores", async () => {
    // ⚠ **B14 RULE 35.** The first column's biggest words and the chips are
    // catalogue words in the reader's own language; the server stores `bill`,
    // `receipt`, `letter`. The screen turns the word it drew back into a code.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      draw({ documents: [AUGUST_BILL] });
      await screen.findByTestId("documents");
      const box = screen.getByPlaceholderText(/search/i);
      fireEvent.change(box, { target: { value: "receipt" } });
      await vi.advanceTimersByTimeAsync(400);
      expect(asked[asked.length - 1].filters?.group).toBe("receipt");
    } finally {
      vi.useRealTimers();
    }
  });

  it("sends a chip as a filter rather than narrowing what arrived", async () => {
    draw({ documents: [AUGUST_BILL] });
    await screen.findByTestId("documents");
    fireEvent.click(document.querySelector("[data-segment='letter']") as Element);
    expect(asked[asked.length - 1].filters?.group).toBe("letter");
  });

  it("holds `Download a year` on the SERVER's whole-set answer", async () => {
    // ⚠ Counted off the page, the control would be held on page 2 for a
    // customer whose kept documents are all on page 1 — a refusal that is
    // simply untrue.
    const { container } = draw({ documents: [AUGUST_BILL], any_kept: false });
    await screen.findByTestId("documents");
    expect(
      container.querySelector("[data-documents-download] [data-held='true']"),
    ).not.toBeNull();
  });

  it("a search that matches nothing does NOT say *we have not written to you*", async () => {
    const { container } = draw({ documents: [], populated: true, count: 0 });
    await screen.findByTestId("documents");
    expect(container.querySelector("[data-documents-empty]")).toBeNull();
  });
});
