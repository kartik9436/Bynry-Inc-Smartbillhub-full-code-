// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vite.config.ts` keeps
// the default environment at `node` (`DEF-523`); an interactive suite opts in.
/* ══════════════════════════════════════════════════════════════════════════
 * WHAT **+ Add** AND **Clone** ACTUALLY DO — THE TWO WIRINGS `DEF-RBS-4311`
 * OWED, AND THE TEST THAT FIRES IF EITHER IS EVER RE-HELD.
 *
 * Story: US-RBS-018 · US-RBS-003 — CR-075.
 * Rules: `07-endpoints.md` rows 5 and 6 (`POST /runbooks`,
 *        `POST /runbooks/{key}/clone`) · `BR-RBS-043` (a template already added
 *        is refused BY NAME) · B14 rule 15 (row actions are icons, max 2 + …).
 *
 * ⚠ **WHY THESE TWO CASES EXIST, AND WHY BEHAVIOUR IS THE ONLY HONEST FORM.**
 * `POST /runbooks` landed in wave `E1` and **+ Add** went on saying *"Adding is
 * not connected yet."* — hard-won law 2's mirror, a live route behind a dead
 * control. `G13` asks whether a prop is PASSED, and `onAdd` was passed,
 * required, compiled and rendered a toast; **nothing anywhere asks whether a
 * REFUSAL IS STILL TRUE.** That is how the customer portal shipped a front page
 * with two working doors out of eight under `tsc`, 42 test files and 391 green
 * cases (`DEF-CWP-3925`).
 *
 * So each case below asserts the REQUEST the button sends — its METHOD, its
 * ADDRESS and its BODY. A test that asserted a toast, or that a handler was
 * called, would pass over a control re-held tomorrow. **This one goes red the
 * moment either button stops writing**, which is the clock law 2 asks for.
 *
 * ⚠ **AND `Clone` WAS NOT A HOLD AT ALL — IT WAS ABSENT**, which is law 2's
 * FRONT half: `POST /runbooks/{key}/clone` was live and no control in the
 * product pointed at it. A missing control has no refusal to go stale, so
 * nothing would ever have said.
 * ══════════════════════════════════════════════════════════════════════════ */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { EIGHT_CHIPS, KIND_CHIPS, THREE_RUNBOOKS, TWELVE_TEMPLATES } from "./libraryFixture";
import { MyRunbooksPage } from "./MyRunbooksPage";
import { RunbookTemplateLibraryPage } from "./TemplateLibraryPage";

const TENANT = "brazosbend";

// No auto-cleanup in this repo (`vite.config.ts` sets no `setupFiles`) — every
// render would otherwise be ADDED to the same document and every count wrong.
afterEach(cleanup);

interface Write {
  method: string;
  path: string;
  body: unknown;
}

/** A transport that RECORDS every write rather than performing one, and
 *  refuses an unrecorded READ by name so a screen cannot draw a blank and be
 *  reported as a pass. */
function recordingClient(writes: Write[], rows: unknown[]): ApiClient {
  const answer = <T,>(body: unknown): Promise<ApiResponse<T>> =>
    Promise.resolve({ status: 200, data: body as T, headers: new Headers() } as ApiResponse<T>);

  const get = <T,>(path: string) => {
    if (path === "/runbooks/templates") {
      return answer<T>({
        count: rows.length,
        next: null,
        previous: null,
        results: rows,
        category_chips: EIGHT_CHIPS,
        kind_chips: KIND_CHIPS,
      });
    }
    if (path === "/runbooks") {
      return answer<T>({ count: rows.length, next: null, previous: null, results: rows });
    }
    throw new Error(`the screen asked for ${path}, which this fixture does not record`);
  };

  const write =
    (method: string) =>
    <T,>(path: string, body?: unknown) => {
      writes.push({ method, path, body });
      // What both routes answer with: the new runbook's own detail body, of
      // which the screens read only the key they navigate to.
      return answer<T>({ key: "the-new-copy", name: "The new copy" });
    };

  return {
    request: get,
    get,
    post: write("POST"),
    put: write("PUT"),
    patch: write("PATCH"),
    del: write("DELETE"),
  } as unknown as ApiClient;
}

/** Mounted at the REAL path pattern. `DEF-CWP-3925`: bare inside a
 *  `MemoryRouter` with no `/:tenant/…` route, `useParams()` is `undefined` and
 *  every address the page builds comes out `//host/…`, which reads as a
 *  perfectly good string to `toContain`. */
function mountAt(path: string, element: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}${path}`]}>
            <Routes>
              <Route path={`/:tenant${path}`} element={element} />
              {/* The destination both writes navigate to. Present so the
                  navigation RESOLVES rather than silently landing nowhere —
                  which is the difference between a working door and a string. */}
              <Route
                path="/:tenant/runbooks/:key"
                element={<p data-landed-on="RBS-004">setup</p>}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("RBS-002 · + Add writes, and the hold that said otherwise is gone", () => {
  it("posts the template key to /runbooks and lands on the new runbook's setup screen", async () => {
    const writes: Write[] = [];
    // A template the tenant has NOT added, so the card draws **+ Add** rather
    // than **Open →**.
    const notAdded = TWELVE_TEMPLATES.filter((row) => row.state === "not_added");
    expect(notAdded.length).toBeGreaterThan(0);
    mountAt(
      "/runbooks/templates",
      <RunbookTemplateLibraryPage client={recordingClient(writes, notAdded)} />,
    );

    // The card's Add button is addressed by the data attribute
    // `TemplateLibrary` stamps on it — the same handle the browser walkthrough
    // holds on to, so the two checks cannot drift about which control they mean.
    const button = await waitFor(() => {
      const found = document.querySelector<HTMLButtonElement>(
        `[data-card-add="${notAdded[0].template_key}"]`,
      );
      expect(found, "the gallery drew no Add button for a not-added template").not.toBeNull();
      return found!;
    });

    fireEvent.click(button);

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].method).toBe("POST");
    // BY ADDRESS. Law 2, and `DEF-CWP-3925`'s `//host/…` lesson.
    expect(writes[0].path).toBe("/runbooks");
    expect(writes[0].body).toEqual({ template_key: notAdded[0].template_key });
    // And the door actually opens onto a screen that exists.
    await waitFor(() =>
      expect(document.querySelector('[data-landed-on="RBS-004"]')).not.toBeNull(),
    );
  });
});

describe("RBS-003 · Clone writes, and it never existed before this commit", () => {
  it("posts the typed name to /runbooks/{key}/clone and opens the copy", async () => {
    const writes: Write[] = [];
    const source = THREE_RUNBOOKS[0];
    mountAt("/runbooks/mine", <MyRunbooksPage client={recordingClient(writes, THREE_RUNBOOKS)} />);

    // B14 rule 15: a row action is an ICON with a tooltip, so it is addressed
    // by its accessible NAME — the same string a screen reader announces.
    const clone = await screen.findAllByRole("button", { name: "Clone" });
    expect(clone.length).toBe(THREE_RUNBOOKS.length);
    fireEvent.click(clone[0]);

    // The one thing only a person can supply. `services.clone_runbook` derives
    // the copy's KEY from this, and no route renames a runbook afterwards.
    // ⚠ `/^Name/` AND NOT `"Name"`: `FieldLabel` appends an accent `*` to a
    // required field, so the label's text is `Name*` and an exact match finds
    // nothing — a failure that reads like a missing control and is a wrong
    // selector (`rbs-c-can-we-bill.mjs` records the same trap for `#signin-email`).
    fireEvent.change(await screen.findByLabelText(/^Name the copy/), {
      target: { value: "Commercial accounts" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create the copy" }));

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].method).toBe("POST");
    expect(writes[0].path).toBe(`/runbooks/${source.key}/clone`);
    expect(writes[0].body).toEqual({ name: "Commercial accounts" });
    await waitFor(() =>
      expect(document.querySelector('[data-landed-on="RBS-004"]')).not.toBeNull(),
    );
  });

  it("refuses an empty name rather than posting one — the key would be derived from it", async () => {
    const writes: Write[] = [];
    mountAt("/runbooks/mine", <MyRunbooksPage client={recordingClient(writes, THREE_RUNBOOKS)} />);

    fireEvent.click((await screen.findAllByRole("button", { name: "Clone" }))[0]);
    // ⚠ **THE FIELD ARRIVES PRE-FILLED** with *"<name> copy"*, so emptying it is
    // what this case is about: a person who clears the box and presses on.
    fireEvent.change(await screen.findByLabelText(/^Name the copy/), { target: { value: "  " } });
    fireEvent.click(await screen.findByRole("button", { name: "Create the copy" }));

    // ⚠ **THE ASSERTION IS THAT NOTHING WAS POSTED, NOT THAT A MESSAGE
    // APPEARED.** `services.clone_runbook` mints the copy's KEY from this name,
    // so a blank one would create a runbook at an address nobody chose — and no
    // route in the product renames one afterwards. The modal stays open, which
    // is `FormModal`'s own contract (`US-SHL-009 TC-1`: errors keep it open and
    // nothing is posted).
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Create the copy" })).toBeDefined(),
    );
    expect(writes).toHaveLength(0);
  });
});
