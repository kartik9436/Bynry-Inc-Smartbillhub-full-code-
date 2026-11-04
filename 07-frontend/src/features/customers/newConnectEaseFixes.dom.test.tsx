// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: `DEF-CUS-6099` (the New connects filter is lost on reload and cannot
//          be shared) · `DEF-CUS-6100` (the review screen printed `our_crew`) ·
//          `DEF-CUS-6101` (sixteen install dates the commit never sent) ·
//          `DEF-CUS-6112` (a charge with no payment terms committed and raised
//          nothing) · `DEF-CUS-6113` (a `.txt` accepted at step 1 and lost
//          after the commit)
// Process: 12-governance/22-product-maintenance-process.md §4 — *"write the
//          test that would have caught it"*
// Rules:   B14 rule 31 (no database value is ever visible) · rule 32 (no
//          internal code in clerk-facing copy) · rule 33 (a LABEL ≤ 3 words, a
//          FACT ≤ 6, an INSTRUCTION ≤ 6 per sentence) · `BR-SHL-011` (the
//          table's params ARE the URL) · `BR-SHL-031` (the upload allowlist) ·
//          `BR-BIL-024` (payment terms are captured and never guessed) ·
//          CLAUDE.md hard-won law 2 (built is not wired) · law 6 (no gate
//          reads rendered output) · law 7 (know what would make this pass
//          wrongly)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE THING THESE FIVE DEFECTS HAVE IN COMMON
// ══════════════════════════════════════════════════════════════════════════
// **Each takes a clerk's input, carries it through the wizard, and disappoints
// them at or after the commit.** A date typed sixteen times and sent nowhere; a
// file carried through seven steps and refused 415 once the build exists; a
// charge that raises nothing and says so on the done panel; a filter that
// narrows the list and forgets on reload; a code where a word should be, on the
// last screen before the press. Every one of them passed every check this repo
// has, because the checks ask whether the control RENDERS and these are all
// about what happens AFTERWARDS.
//
// ⚠ **SO EVERY CASE BELOW ASSERTS THE AFTERWARDS**: the payload, the address
// after a press, the word a clerk reads — never that a control exists.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { DocumentCaptureForm } from "@/components/documents";
import { refusedFileExtension } from "@/components/documents/documentCapture";
import { ToastProvider } from "@/components/Toast";

import { commitPlanOf, connectModeWord, connectScopeWord, emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import { ChargesStep } from "./NewConnectChargesStep";
import { NewConnectsTab, NEW_CONNECTS_PARAM_PREFIX } from "./NewConnectsTab";
import { ReviewStep } from "./NewConnectReviewStep";
import { NewConnectWizard } from "./NewConnectWizard";
import { draftManifest } from "./newConnectDraft";
import { NEW_CONNECT_STEPS } from "./newConnectShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string =>
  String(i18next.t(key, params as never));

afterEach(cleanup);

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-6101` — THE INSTALL DATES THE COMMIT NEVER SENT
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-CUS-6101 — a field a clerk fills in is read by something, or it is gone", () => {
  it("a date on a grid cell reaches NO payload — the guard against re-adding the column", () => {
    // ⚠ **WHAT THIS CASE CAN AND CANNOT SEE, SAID OUT LOUD (law 7, habit 2).**
    // It is **green on the pre-fix code too**, because the payload never
    // carried the date either — that WAS the defect. So it is not the
    // reproduction; it is the guard that fires the day somebody re-adds
    // `installDate` to the cell and wires it half-way. **The reproduction is
    // rendered** and lives in `NewConnectServicesStep.dom.test.tsx`
    // (*"step 4 asks for NO per-unit install date at all"*), which goes red on
    // the code that shipped the defect.
    //
    // Every existing test of step 4 asserts the cells RENDER and that *Copy
    // unit 1 to all* propagates them — both true — and none asked whether the
    // commit carried what the grid collected. It did not: `meters` carry
    // `unit_label`, `service` and `asset_no` and nothing else.
    const draft: NewConnectDraft = {
      ...emptyDraft(),
      premiseServices: ["water"],
      pattern: { ...emptyDraft().pattern, from: "1", to: "2" },
      unitServiceGrid: {
        // Written the way the picker used to write it. If the key is ever
        // re-added WITHOUT a payload that carries it, this case is the one that
        // says so — it asserts the payload, not the type.
        ["1\u001fwater"]: { taken: true, ...({ installDate: "2026-10-01" } as object) },
      },
    };
    const plan = commitPlanOf(draft, null);
    expect(JSON.stringify(plan)).not.toContain("2026-10-01");
    expect(JSON.stringify(plan)).not.toContain("install");
  });

  it("the build's OWN planned date still travels — what was lost is a per-row override", () => {
    // `OQ-MET-12571` is OPEN and nothing here answers it. The date a clerk
    // types ONCE at step 1 is stored as `connections.target_activation`, and
    // every removed cell defaulted from it.
    const draft: NewConnectDraft = { ...emptyDraft(), targetActivation: "2026-11-15" };
    expect(JSON.stringify(commitPlanOf(draft, null))).toContain("2026-11-15");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-6100` — THE WORD, NEVER THE STORED VALUE
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-CUS-6100 — the review screen reads WORDS, on every variation", () => {
  it("every mode and every scope the draft can hold renders a word", () => {
    for (const mode of ["our_crew", "external", "we_schedule"]) {
      const word = connectModeWord(mode, t);
      expect(word, `mode ${mode} renders as its own code`).not.toBe(mode);
      expect(word).not.toContain("_");
    }
    for (const scope of ["new_premise", "new_units", "new_service"]) {
      const word = connectScopeWord(scope, t);
      expect(word, `scope ${scope} renders as its own code`).not.toBe(scope);
      expect(word).not.toContain("_");
    }
  });

  it("a mode NOBODY has named states an absence and never the code, LOUDLY", () => {
    // ⚠ **THE LOUD HALF IS ASSERTED, NOT ASSUMED.** Rendering the code is how
    // a missing label stays invisible for a month: it looks deliberate and is
    // never blank. A `console.error` is what makes a walk or a browser console
    // say the name of the thing that is missing.
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    let word: string;
    try {
      word = connectModeWord("a_mode_from_the_future", t);
    } finally {
      console.error = real;
    }
    expect(word).not.toBe("a_mode_from_the_future");
    expect(word).toBe(t("customers.newConnect.mode.unnamed"));
    expect(said.join(" ")).toContain("a_mode_from_the_future");
  });

  it("the RENDERED review screen carries none of the stored spellings", () => {
    // ⚠ **THE SCREEN, NOT THE HELPER.** `DEF-CUS-6100` was not a broken
    // function — it was a second reader of one fact, inventing its own
    // fallback. Only rendering the step can see that, which is why this case
    // renders it.
    const draft: NewConnectDraft = {
      ...emptyDraft(),
      scope: "new_units",
      mode: "our_crew",
      owner: { ...emptyDraft().owner, name: "Walk Two Developments LLC" },
    };
    const html = renderToStaticMarkup(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new`]}>
          <ToastProvider>
            <ReviewStep
              draft={draft}
              manifest={draftManifest(draft, null)}
              // ⊕ 2026-09-28 — see `ReviewStep`'s own docstring: the quote's
              // stored figure and its currency, so the manifest's money row
              // renders through `MoneyCell`. This case prices nothing.
              quoteTotal={null}
              quoteCurrency={null}
              workOrderCount={0}
              onPatch={() => undefined}
              t={t}
            />
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    for (const code of ["our_crew", "new_units", "external", "we_schedule", "new_premise"]) {
      expect(html, `the review screen prints the stored value "${code}"`).not.toContain(code);
    }
    expect(html).toContain("Our crew did it");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-6113` — THE FILE IS REFUSED WHERE IT IS CHOSEN
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-CUS-6113 — a document of the wrong type never leaves step 1", () => {
  const ACCEPT = ".pdf,.png,.jpg,.jpeg,.csv";

  it("the allowlist is read from `accept`, so the screen and the door cannot drift", () => {
    expect(refusedFileExtension(new File(["x"], "deed.txt"), ACCEPT)).toBe("txt");
    expect(refusedFileExtension(new File(["x"], "scan.tif"), ACCEPT)).toBe("tif");
    expect(refusedFileExtension(new File(["x"], "deed.pdf"), ACCEPT)).toBeNull();
    // Case is the clerk's, not the rule's — a camera writes `.JPG`.
    expect(refusedFileExtension(new File(["x"], "PHOTO.JPG"), ACCEPT)).toBeNull();
    expect(refusedFileExtension(new File(["x"], "meters.CSV"), ACCEPT)).toBeNull();
  });

  it("a file with NO extension is left to the server, which reads the media type", () => {
    // ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY (law 7):** refusing
    // everything. A scanner really does produce a file with no extension and
    // the door may well take it; refusing here would refuse a file the server
    // would have accepted, which is the mirror of the defect.
    expect(refusedFileExtension(new File(["x"], "scan"), ACCEPT)).toBeNull();
    expect(refusedFileExtension(new File(["x"], "scan."), ACCEPT)).toBeNull();
    expect(refusedFileExtension(null, ACCEPT)).toBeNull();
    // A host that declares nothing has said it takes anything; this function
    // does not invent another door's allowlist.
    expect(refusedFileExtension(new File(["x"], "deed.txt"), "")).toBeNull();
  });

  it("choosing a `.txt` refuses ON THE STEP and does not hold the file", async () => {
    // ⚠ **THE REFUSAL AND THE CLEARING ARE ONE CASE, DELIBERATELY.** A refused
    // file left in the box is one the Attach button could still send — the
    // defect with an extra step in it.
    let held: File | null = new File(["x"], "placeholder.pdf");
    function Host() {
      const [value, setValue] = useState({
        docType: "contract",
        file: null as File | null,
        whatItProves: "",
    documentNumber: "",
        required: false,
      });
      held = value.file;
      return (
        <DocumentCaptureForm
          value={value}
          onChange={(next) => {
            setValue(next);
            held = next.file;
          }}
          onSubmit={() => undefined}
          docTypes={[{ value: "contract", label: "Contract" }]}
          t={t}
          accept={ACCEPT}
          idPrefix="nc-owner-doc"
        />
      );
    }
    render(<Host />);
    const input = document.querySelector("#nc-owner-doc-file") as HTMLInputElement;
    // ⚠ **`user.upload` OBEYS `accept` AND SO CANNOT REPRODUCE THIS DEFECT** —
    // it silently drops a file the attribute excludes, and a case written with
    // it passes over the thing it exists to test (law 7's *incapable of
    // failing*). A real clerk defeats `accept` without trying: every picker
    // offers *All files*, and a drag-and-drop ignores it outright. So the file
    // is put on the element and the event fired, which is what a drop does.
    // ⚠ **`user.upload` OBEYS `accept` AND DROPS THE FILE SILENTLY**, so a case
    // written with it is green over the defect (law 7's *incapable of
    // failing*). `applyAccept: false` is its FOURTH argument, and even then it
    // is the library's own model of a picker rather than a drop. The file is
    // therefore put on the element and the change fired, which is exactly what
    // a drag-and-drop does and what *All files* in any picker does.
    Object.defineProperty(input, "files", {
      configurable: true,
      value: [new File(["proof"], "proof.txt", { type: "text/plain" })],
    });
    fireEvent.change(input);

    const refusal = document.querySelector("[data-doc-type-refused]");
    expect(refusal, "a .txt was accepted at the step that asks for it").not.toBeNull();
    expect(refusal?.getAttribute("data-doc-type-refused")).toBe("txt");
    expect(refusal?.textContent).toContain("TXT");
    // The four the door takes are NAMED, so the clerk knows what to choose.
    expect(refusal?.textContent).toContain("PDF");
    expect(held, "the refused file is still held and could be sent").toBeNull();
  });

  it("choosing a `.pdf` is accepted and draws no refusal", async () => {
    const user = userEvent.setup();
    const accepted: { file: File | null } = { file: null };
    function Host() {
      const [value, setValue] = useState({
        docType: "contract",
        file: null as File | null,
        whatItProves: "",
    documentNumber: "",
        required: false,
      });
      return (
        <DocumentCaptureForm
          value={value}
          onChange={(next) => {
            setValue(next);
            accepted.file = next.file;
          }}
          onSubmit={() => undefined}
          docTypes={[{ value: "contract", label: "Contract" }]}
          t={t}
          accept={ACCEPT}
          idPrefix="nc-owner-doc"
        />
      );
    }
    render(<Host />);
    const input = document.querySelector("#nc-owner-doc-file") as HTMLInputElement;
    await user.upload(input, new File(["%PDF-1.4"], "deed.pdf", { type: "application/pdf" }));
    expect(document.querySelector("[data-doc-type-refused]")).toBeNull();
    // ⚠ **THE FILE IS HELD, WHICH IS WHAT THE REFUSED CASE ABOVE ASSERTS THE
    // ABSENCE OF.** Asserted on the value rather than on rendered text:
    // `FileField` takes a `fileName` prop and draws it nowhere, so a case
    // reading the screen for it would be green on an empty box — hard-won law
    // 2, and it is REPORTED here rather than fixed by a test.
    expect(accepted.file?.name).toBe("deed.pdf");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-6099` — THE FILTER IS IN THE ADDRESS, AND COMES BACK FROM IT
// ══════════════════════════════════════════════════════════════════════════

/** §5.4.9's own drawn row, in the shape the tab's own suite already uses —
 *  `NewConnectsTab.test.tsx`'s `row()`. A second shape of one payload is how a
 *  fixture stops being able to tell a working screen from a broken one. */
const ROW = {
  id: "con-0117",
  connection_no: "CON-26-0117",
  premises: {
    id: "prm-500",
    premise_no: "P-000500",
    name: "Main Street Block",
    address: "500 Main Street",
  },
  home: { kind: "premises", id: "prm-500" },
  units: 25,
  services: ["electric", "water"],
  orders: { done: 5, total: 7 },
  target_activation: "2026-09-30",
  waiting_on: "inspection",
  state: "partly_activated",
  request_no: "SR-26-0018",
  applicant: "Rodriguez, M.",
};

function listPayload(): unknown {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [ROW],
    kpis: {
      open: 1,
      waiting_on_inspection: 1,
      partly_activated: 1,
      units_awaiting_activation: 25,
      oldest: { days: 19, connection_no: "CON-26-0117", waiting_on: "permit" },
    },
    segment: "all",
    unavailable: [],
    filters: ["state"],
    // The ten the server really serves, including the two `DEF-CUS-6098` is
    // about — so the panel under test is the panel a clerk opens.
    states: [
      { code: "open" },
      { code: "draft" },
      { code: "requested" },
      { code: "in_progress" },
      { code: "partly_activated" },
      { code: "on_hold" },
      { code: "activated" },
      { code: "cancelled" },
      { code: "in_progress_draft", label: "Draft" },
      { code: "parked", label: "Parked" },
    ],
  };
}

/** The tab mounted under the REAL path pattern, with the address readable.
 *
 *  ⚠ **MOUNTED UNDER `/:tenant/accounts`, NOT BARE.** CLAUDE.md hard-won law 2
 *  records what a bare `MemoryRouter` costs: the portal's front page mounted
 *  with no route pattern had `useParams().tenant` undefined, every address it
 *  built came out `//portal/…`, and `toContain` read that as a perfectly good
 *  string. A fixture that cannot tell a working link from a broken one is how a
 *  defect hides.
 */
function mountTab(initial: string) {
  const urls: string[] = [];
  const client = createApiClient({
    baseUrl: "",
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      urls.push(String(input));
      return new Response(JSON.stringify(listPayload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  let search = "";
  function Address() {
    search = useLocation().search;
    return null;
  }
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route
            path="/:tenant/accounts"
            element={
              <ToastProvider>
                <Address />
                <NewConnectsTab client={client} />
              </ToastProvider>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { urls, address: () => search };
}

describe("DEF-CUS-6099 — a filtered list survives a reload and can be sent to somebody", () => {
  it("an address carrying the filter opens FILTERED — the read half", async () => {
    // ⚠ **THE READ HALF IS THE ONE THAT MAKES IT SHAREABLE**, and it is the
    // half a click-and-count walk can never see. Asserted on the REQUEST the
    // tab makes, because that is what decides which rows come back.
    const { urls } = mountTab(
      `/${TEST_TENANT}/accounts?tab=new-connects&${NEW_CONNECTS_PARAM_PREFIX}f.state=draft`,
    );
    await screen.findByText("CON-26-0117");
    expect(urls.some((url) => url.includes("f.state=draft"))).toBe(true);
  });

  it("the page's OWN params are not read as this tab's — `DEF-664` stays closed", async () => {
    // The Accounts tab writes BARE `q` and `f.status`. If this tab read them,
    // opening New connects after a search on Accounts would narrow it by a term
    // nobody typed here.
    const { urls } = mountTab(
      `/${TEST_TENANT}/accounts?tab=new-connects&q=smith&f.status=pending_activation&sort=name`,
    );
    await screen.findByText("CON-26-0117");
    expect(urls.some((url) => url.includes("smith"))).toBe(false);
    expect(urls.some((url) => url.includes("pending_activation"))).toBe(false);
  });

  it("choosing a state WRITES it to the address, and keeps `?tab=`", async () => {
    const user = userEvent.setup();
    const { address } = mountTab(`/${TEST_TENANT}/accounts?tab=new-connects`);
    await screen.findByText("CON-26-0117");

    const panel = document.querySelector("details") as HTMLDetailsElement;
    panel.open = true;
    const box = document.querySelector(
      'details fieldset input[type="checkbox"]',
    ) as HTMLInputElement;
    await user.click(box);

    expect(address()).toContain(`${NEW_CONNECTS_PARAM_PREFIX}f.state=`);
    // ⚠ **`?tab=` SURVIVES OR THE CLERK IS THROWN BACK TO ACCOUNTS** on their
    // first filter press — the reason `AccountsListPage.writeParams` exists.
    expect(address()).toContain("tab=new-connects");
  });

  it("clearing the filter REMOVES it from the address rather than blanking it", async () => {
    // A `f.state=` with nothing after it is an address that claims a filter and
    // has none — and it would be pasted to a colleague looking just as wrong.
    const user = userEvent.setup();
    const { address } = mountTab(`/${TEST_TENANT}/accounts?tab=new-connects`);
    await screen.findByText("CON-26-0117");
    const panel = document.querySelector("details") as HTMLDetailsElement;
    panel.open = true;
    const box = document.querySelector(
      'details fieldset input[type="checkbox"]',
    ) as HTMLInputElement;
    await user.click(box);
    expect(address()).toContain("f.state=");
    await user.click(
      document.querySelector('details fieldset input[type="checkbox"]') as HTMLInputElement,
    );
    expect(address()).not.toContain("f.state=");
    expect(address()).toContain("tab=new-connects");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-6115` + `DEF-CUS-6112` — STEP 6 SHOWS MONEY, AND REFUSES BEFORE
// THE PRESS RATHER THAN REPORTING AFTER IT
// ══════════════════════════════════════════════════════════════════════════

/** A seven-unit block with a connection fee per unit — the walk's own build. */
function pricedDraft(): NewConnectDraft {
  const base = emptyDraft();
  const grid: NewConnectDraft["unitServiceGrid"] = {};
  for (let unit = 1; unit <= 7; unit += 1) {
    grid[`${unit}\u001fwater`] = { taken: true };
  }
  return {
    ...base,
    premiseServices: ["water"],
    pattern: { ...base.pattern, from: "1", to: "7" },
    unitServiceGrid: grid,
    quoteLines: [{ chargeCode: "CONN", basis: "per unit" }],
  };
}

function mountCharges(preview: unknown, draft: NewConnectDraft) {
  const client = createApiClient({
    baseUrl: "",
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("quote-preview")
        ? preview
        : { results: [{ id: "c1", code: "CONN", name: "Connection fee" }], count: 1 };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new`]}>
        <ToastProvider>
          <ChargesStep
            draft={draft}
            onPatch={() => undefined}
            t={t}
            dateFormat="MM/DD/YYYY"
            client={client}
          />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const PRICED_SEVEN = {
  priced: true,
  currency: "USD",
  lines: [
    {
      charge_code: "CONN",
      description: "Connection fee",
      basis: "per unit",
      quantity: "7",
      unit: "unit",
      unit_price: { stored: "45.0000", display: "45.00" },
      amount: { stored: "315.0000", display: "315.00" },
    },
  ],
  total: { stored: "315.0000", display: "315.00" },
  unavailable: [],
};

describe("DEF-CUS-6115 — a money screen shows money, before the build exists", () => {
  it("the walk's own build reads `$45.00` each and `$315.00` quoted", async () => {
    mountCharges(PRICED_SEVEN, pricedDraft());
    // ⚠ **THE FIGURE, NOT THE ELEMENT.** Every test of this step asserted the
    // QUANTITIES, which were always right; nothing asserted that a screen whose
    // subject is money has a figure on it. Six builds were committed in the
    // acceptance walk without the clerk ever seeing one.
    expect(await screen.findByText("$45.00")).toBeInTheDocument();
    // ⚠ **TWO OF THEM, AND THAT IS RIGHT ON A ONE-LINE QUOTE:** the LINE total
    // and the QUOTE total. `findByText` throws on two matches, which is how
    // this case first went red over correct behaviour.
    expect(await screen.findAllByText("$315.00")).toHaveLength(2);
    // The total is labelled, not floating — `BR-REP-001`, no unlabelled money.
    //
    // ⊕ **AMENDED 2026-09-29 (`22cf1c575`, `CR-150-BRC09` tasks 11–14).** The
    // one `data-quote-total` line became the drawn three-line footer — Total,
    // Paid now, Remaining — so the marker is `data-charge-total` inside
    // `data-charge-totals`. **Re-pointed, not dropped, and it asks MORE than
    // it did:** the figure must sit inside the LABELLED total row, which is
    // what `BR-REP-001` is about, rather than merely somewhere on the page.
    const totals = document.querySelector("[data-charge-totals]");
    expect(totals).not.toBeNull();
    const total = document.querySelector("[data-charge-total]");
    expect(total).not.toBeNull();
    expect(total?.textContent).toContain("$315.00");
  });

  it("the server's 4dp `stored` figure never reaches the screen — hard rule 2", async () => {
    // Display is 2 decimals, from the server's ONE rounding. A screen printing
    // `315.0000` is `DEF-088` exactly, and `MoneyCell` is the boundary.
    mountCharges(PRICED_SEVEN, pricedDraft());
    await screen.findAllByText("$315.00");
    expect(document.body.textContent).not.toContain("315.0000");
    expect(document.body.textContent).not.toContain("45.0000");
  });

  it("a charge the catalogue cannot price is REFUSED on step 6, by the screen", async () => {
    // `DEF-MET-6110` — `TAP` has no amount at all. Picking it used to commit
    // eight steps of work and answer 500, losing the build.
    mountCharges(
      {
        priced: false,
        currency: null,
        lines: [],
        total: { stored: null, display: null },
        unavailable: [
          {
            field: "quote",
            code: "quote_line_cannot_be_priced",
            tracks: "BR-BIL-007",
            detail: "charge code 'TAP' is priced as None…",
          },
        ],
      },
      pricedDraft(),
    );
    const strip = await screen.findByText(/has no price/i);
    expect(strip).toBeInTheDocument();
    // ⚠ **THE ENGINEER'S SENTENCE DOES NOT REACH THE CLERK** — B14 rule 32,
    // and `DEF-742` had to remove exactly this from six surfaces once already.
    expect(document.body.textContent).not.toContain("charge code 'TAP' is priced as None");
    expect(document.body.textContent).not.toContain("quote_line_cannot_be_priced");
  });

  it("an unpriced quote shows a BLANK, never `$0.00`", async () => {
    // On a money line a zero reads as *free*; the truth is *not priced*. This
    // is `connection_record._money`'s rule on the build record's tiles, matched.
    mountCharges(
      {
        priced: false,
        currency: null,
        lines: [],
        total: { stored: null, display: null },
        unavailable: [{ field: "quote", code: "build_names_no_charge", tracks: "BR-MET-1178" }],
      },
      pricedDraft(),
    );
    await screen.findByText("Not priced");
    expect(document.body.textContent).not.toContain("$0.00");
    expect(document.body.textContent).not.toContain("0.00");
  });

  it("a build with NO charge draws no total at all — not even the absence", async () => {
    // The `No charges yet` line above it already says it in five words (B14
    // rule 32 — a stated absence is CLOSED by default). A second sentence
    // under it would be the description budget spent twice.
    mountCharges(PRICED_SEVEN, { ...emptyDraft(), quoteLines: [] });
    expect(document.querySelector("[data-quote-total]")).toBeNull();
  });
});

describe("DEF-CUS-6112 — payment terms are asked where the charge is picked", () => {
  it("the field is marked required the moment a charge line exists", async () => {
    mountCharges(PRICED_SEVEN, pricedDraft());
    await screen.findAllByText("$315.00");
    const field = document.querySelector("#nc_quote_due_days");
    expect(field?.getAttribute("aria-required")).toBe("true");
  });

  it("and is NOT required on a build that charges nothing", () => {
    // ⚠ **THE HALF THAT MAKES THIS A FIX RATHER THAN A NEW REFUSAL.** A build
    // with no charge needs no terms and the server correctly REPORTS that
    // absence rather than refusing; a screen that demanded them would stop a
    // lawful build. Nothing distinguished the two cases, which is the defect.
    mountCharges(PRICED_SEVEN, { ...emptyDraft(), quoteLines: [] });
    const field = document.querySelector("#nc_quote_due_days");
    expect(field?.getAttribute("aria-required")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 6 · THE SHORTFALL LEFT THE SCREEN AND MUST ARRIVE AT CONTINUE
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS CASE EXISTS BECAUSE THE FIRST DRAFT OF ITS OWN FIX WAS UNWIRED
// (2026-09-28, self-reported — CLAUDE.md hard-won law 2).** PO reported bug 1
// took the identity-shortfall strip off step 1, and the redesign drawing says
// where it goes instead: *"shown only as an error on Continue"*. The lane
// deleted the strip, exported `ownerShortfallSentence` for the wizard to use —
// and never changed `validate`. Every check passed: `tsc` was clean, the step
// file's own tests asserted the sentence was gone and that the function
// returns it, `vitest` was green, and the sentence reached NOBODY. A clerk
// pressing Continue on an empty step 1 got the frame's generic *check the
// fields*, which tells them to look at fields that may all be filled in.
//
// ⚠ **SO IT ASSERTS THE PRESS AND NOT THE EXPORT.** A case calling
// `ownerShortfallSentence` directly is the check that was already there and
// that passed over this; the question is whether the WIZARD hands the frame
// those words when a person presses the button.
describe("PO 2026-09-28 bug 1 · the identity shortfall moved to Continue and must ARRIVE there", () => {
  function mountWizard() {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify({ count: 0, results: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=1`]}>
            <Routes>
              <Route
                path="/:tenant/connections/new"
                element={<NewConnectWizard client={client} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("says nothing while the clerk is still typing", async () => {
    // The whole reason the strip was deleted: an untouched form refused a
    // person who had not been given the chance to answer yet.
    mountWizard();
    expect(screen.queryByText("Name the owner first.")).not.toBeInTheDocument();
    expect(screen.queryByText("Say person or company.")).not.toBeInTheDocument();
  });

  it("names the shortfall in the blocked line when Continue is pressed", async () => {
    const user = userEvent.setup();
    mountWizard();
    await user.click(screen.getByRole("button", { name: /continue/i }));
    const blocked = await screen.findByText("Name the owner first.");
    // It is the FRAME's blocked line, beside Continue — not a strip that has
    // quietly come back under the fields.
    expect(blocked.closest('[data-wizard="blocked"]')).not.toBeNull();
  });

  it("still refuses the step — the words are additional, not a replacement", async () => {
    // The deletion must not have bought a message at the cost of the gate.
    // `BR-CUS-1024` refuses the master account without an identifier, and the
    // wizard has to stop here or the clerk learns it eight steps later.
    const user = userEvent.setup();
    mountWizard();
    await user.click(screen.getByRole("button", { name: /continue/i }));
    // ⊕ **AMENDED 2026-09-29 (`ed4e7cb30` — *"New Connect is FIVE steps"*).**
    // The count in the step line moved from 8 to 5. **The question is the
    // refusal, not the number:** what this case proves is that Continue did
    // NOT advance — the clerk is still on step 1 — so the `1` is the load-
    // bearing half and the total is read from the declared list rather than
    // typed, which is what let this line rot in the first place.
    expect(
      screen.getByText(new RegExp(`Step 1 of ${NEW_CONNECT_STEPS.length}\\b`)),
    ).toBeInTheDocument();
  });
});
