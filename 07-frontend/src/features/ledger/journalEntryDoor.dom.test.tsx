// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-LED-6723 — *"we cannot click on eye."* (PO, v2.351.84)
// Task:    Finance blueprint `P3.5` — *"Doors asserted by address. For each new
//          screen, assert the inbound link resolves to the address **and** the
//          screen id it opens."*
// Rules:   CLAUDE.md hard-won law 2 **and its MIRROR** — a live screen behind a
//          dead control · hard rule 4 (no edit on a posted entry) · B14 rule 31
//          (no database id is a visible value) · B14 rule 43.
// ─────────────────────────────────────────────────────────────────────────
/**
 * ⚠ **A DOOR IS TWO CLAIMS AND THIS FILE MAKES BOTH.** The control is clicked,
 * the ADDRESS it resolved to is read, and a string only the DESTINATION renders
 * is read. Either half alone is the defect `P3.5` exists for: a hold-expiry
 * test once asserted a screen was registered at one address while the router
 * mounted it at another, and both opened onto *"not built yet"*.
 *
 * ⚠ **THE TREE IS MOUNTED UNDER THE REAL `/:tenant/…` PATTERN.** A bare
 * `MemoryRouter` leaves `useParams().tenant` undefined and every address the
 * app builds comes out `//finance/…` — a protocol-relative URL to another host
 * that reads as a perfectly good string to `toContain`. That fixture flaw hid
 * eight broken doors on the customer portal (`DEF-CWP-3925`).
 *
 * ⚠ **THE GUARD CASE COMES FIRST, AND IT IS NOT CEREMONY.** A sibling lane
 * wrote the regression pair this defect prescribed, ran it, and watched FIVE OF
 * SIX CASES PASS — all five worthless, because with reads disabled the Finance
 * page never gets past *"Set the fiscal year start"* and every *"this is
 * absent"* assertion was passing over a screen that had not rendered. So
 * `the table rendered at all` runs before anything else asserts what is on it.
 *
 * ⚠ **WHAT THIS FILE DOES NOT PROVE, STATED RATHER THAN IMPLIED.** It mounts
 * `JournalView`, not `GeneralLedgerPage`, so it does not itself demonstrate
 * that the PAGE passes `onOpen`. **The compiler does**: `onOpen` is a REQUIRED
 * prop on `JournalViewProps`, so a caller that omits it does not typecheck —
 * which is the cure for hard-won law 2's dead-UI shape (*an optional prop
 * nothing passes*) rather than a second copy of this assertion. A browser walk
 * of the real page is `10-scripts/def_led_6723_journal_detail_walkthrough.mjs`.
 */
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

// The catalogue is mocked for the reason `financeP3Doors.dom.test.tsx` records:
// pulling eleven 1.3MB locale files through vite's transform makes the file
// report `0 test` on a loaded machine, which is a file that could not be asked
// the question rather than a failing assertion.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
  Trans: ({ i18nKey }: { i18nKey: string }) => i18nKey,
  initReactI18next: { type: "3rdParty", init: () => undefined },
}));

import type { JournalEntriesResponse, JournalEntryListRow } from "@/api/endpoints";

import {
  JOURNAL_ENTRY_DETAIL_ROUTE,
  JOURNAL_ENTRY_DETAIL_SCREEN_ID,
  JournalEntryDetailBody,
  journalEntryDetailPath,
} from "./JournalEntryDetail";
import { JournalView } from "./JournalView";

const ENTRY_ID = "01a0d23c-a5e4-703d-95cb-e8aae8bf1115";

/** An OPENING BALANCE — `je_number` null, `source_label` "opening". The row the
 *  Journal shows a `—` for, and the case most likely to break. */
const OPENING: JournalEntryListRow = {
  entry_id: ENTRY_ID,
  je_number: null,
  entry_date: "2026-08-31",
  type: "standard",
  status: "posted",
  memo: "Opening balance",
  source_type: "opening_balance",
  source_label: "opening",
  source_mapped: true,
  currency: "USD",
  debit: "267.300000",
  credit: "267.300000",
  balanced: true,
  reversal_of_entry_id: null,
  reversed_by_entry_id: null,
  auto_reverse_entry_id: null,
  posted_at: "2026-08-31T00:00:00Z",
};

const RESPONSE: JournalEntriesResponse = {
  results: [OPENING],
  count: 1,
  next: null,
  previous: null,
  basis: "posting",
  currency: "USD",
  unavailable: [],
} as unknown as JournalEntriesResponse;

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname}</output>;
}

/** The destination, standing in for the real page so a case proves the ROUTE
 *  resolves and the SCREEN ID matches without dragging a read into jsdom. */
function DetailStandIn() {
  return (
    <div data-screen-id={JOURNAL_ENTRY_DETAIL_SCREEN_ID}>
      {JOURNAL_ENTRY_DETAIL_SCREEN_ID}
    </div>
  );
}

/** The journal, wired the way `GeneralLedgerPage` wires it — the same helper,
 *  the same navigate. */
function JournalUnderTest() {
  const navigate = useNavigate();
  return (
    <JournalView
      response={RESPONSE}
      loading={false}
      state={{ q: "", sort: null, dir: "desc", page: 1, per: 50, filters: {} } as never}
      onStateChange={() => undefined}
      regional={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY", today: "2026-10-12" }}
      onReverse={() => undefined}
      onDeleteDraft={() => undefined}
      onOpen={(row) => navigate(`/brazosbend${journalEntryDetailPath(row.entry_id)}`)}
    />
  );
}

function mount() {
  return render(
    <MemoryRouter initialEntries={["/brazosbend/finance"]}>
      <Where />
      <Routes>
        <Route path="/:tenant/finance" element={<JournalUnderTest />} />
        <Route
          path={`/:tenant${JOURNAL_ENTRY_DETAIL_ROUTE}`}
          element={<DetailStandIn />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("DEF-LED-6723 · the eye opens the entry", () => {
  // ══════════════════════════════════════════════════════════════════════
  // 0 · THE GUARD — the body rendered AT ALL, before anything asserts on it
  // ══════════════════════════════════════════════════════════════════════
  it("renders the journal table at all", async () => {
    mount();
    expect(await screen.findByText("Opening balance")).toBeInTheDocument();
  });

  it("resolves to /:tenant/finance/journal-entries/:id AND opens the detail", async () => {
    mount();
    // The guard again, in this case's own words: no assertion below is worth
    // anything over a tree that never drew a row.
    await screen.findByText("Opening balance");
    const eye = await screen.findByRole("button", {
      name: "finance.journal.viewAction",
    });
    // ⚠ **THE CONTROL IS ENABLED.** The whole defect was a control that was
    // visible, disabled and honest about it; a case that only checked where it
    // GOES would pass on a button nobody can press.
    expect(eye).toBeEnabled();
    await userEvent.click(eye);
    await waitFor(() => {
      // ① THE ADDRESS — with the leading `/brazosbend`, which is what proves
      //    the tenant segment survived. `//finance/…` passes a `toContain`.
      expect(screen.getByTestId("where")).toHaveTextContent(
        `/brazosbend/finance/journal-entries/${ENTRY_ID}`,
      );
    });
    // ② THE SCREEN IT OPENS, by its own id.
    expect(screen.getByText(JOURNAL_ENTRY_DETAIL_SCREEN_ID)).toBeInTheDocument();
  });

  it("builds the path from the id and encodes it", () => {
    expect(journalEntryDetailPath("a/b")).toBe("/finance/journal-entries/a%2Fb");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE DETAIL ITSELF — the `—` case, and no edit anywhere
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-LED-6723 · what the detail shows", () => {
  const LINES = [
    {
      line_id: "l1",
      account_code: "3000",
      account_name: "Opening balance clearing",
      side: "credit",
      debit: null,
      credit: "267.300000",
      service: null,
      account: { id: "acc-1", label: "A-12103" },
      premises: { id: "p-1", label: "501 Willow Bend Dr" },
      unit: { id: "u-1", label: "Unit 101" },
      tax_authority: null,
    },
    {
      line_id: "l2",
      account_code: "1200",
      account_name: "Accounts receivable",
      side: "debit",
      debit: "267.300000",
      credit: null,
      service: null,
      account: { id: "acc-1", label: "A-12103" },
      premises: { id: "p-1", label: "501 Willow Bend Dr" },
      unit: { id: "u-1", label: "Unit 101" },
      tax_authority: null,
    },
  ];

  function mountBody() {
    return render(
      <MemoryRouter initialEntries={["/brazosbend/finance"]}>
        <Routes>
          <Route
            path="/:tenant/finance"
            element={
              <JournalEntryDetailBody
                entry={OPENING}
                lines={LINES as never}
                lineCount={2}
                locale="en-US"
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("renders the lines table at all", () => {
    mountBody();
    expect(screen.getByTestId("journal-entry-lines")).toBeInTheDocument();
  });

  it("shows both sides and a footer that agrees", () => {
    mountBody();
    expect(screen.getByText("Accounts receivable")).toBeInTheDocument();
    expect(screen.getByText("Opening balance clearing")).toBeInTheDocument();
    const foot = screen.getByTestId("journal-entry-foot");
    // ⚠ THE FOOTER IS THE ENTRY'S OWN TOTALS. The two figures are equal and
    // both are $267.30 — displayed to TWO places (hard rule 2), never the six
    // the wire carries.
    expect(foot.textContent).toContain("$267.30");
    expect(foot.textContent).not.toContain("267.300000");
    expect(screen.getByText("finance.entryDetail.balanced")).toBeInTheDocument();
  });

  it("shows the ABSENCE of an entry number and never invents one", () => {
    mountBody();
    // An opening balance is not a document. Nothing on this screen may read as
    // a number for it, and the entry's own uuid must reach no cell (rule 31).
    expect(document.body.textContent).not.toContain(ENTRY_ID);
    expect(document.body.textContent).not.toContain("JE-");
  });

  it("offers nothing that could be saved (hard rule 4)", () => {
    mountBody();
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
