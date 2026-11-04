// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-NOT-5637, 2026-09-17 — `GET /suppressions` and
//          `POST /suppressions/{id}/release` were served and there was NO
//          screen, so the Release the Product Owner asked for by name could
//          only be performed by an engineer.
// Screens: S8 → Settings → Notifications → Blocked addresses (`SET-12B`)
// Rules:   B14 rule 31 (no database id is the visible value of a field) ·
//          rule 33 (on-screen text is capped by what it is for) · BR-SHL-025
//          (a control that cannot be used says why, on itself) · BR-TEN-043
//          (the caller states the business date) · hard-won law 2 (built is
//          not wired — and its mirror, a live screen behind a dead control) ·
//          hard-won law 7 (a check that reports zero over a scope it silently
//          excludes)
// ───────────────────────────────────────────────────────
// ⚠ **THE FIRST TWO CASES ARE THE ONES THIS FILE EXISTS FOR, AND THEY ARE
// ABOUT THE DOOR RATHER THAN ABOUT THE SCREEN.**
//
// On 2026-09-05 the customer portal shipped with two working doors out of
// eight, because every wave tested ITS OWN screen at ITS OWN address and the
// question *has the door started pointing at it* belonged to nobody. A
// blocked-addresses screen nobody can reach is the defect this one is fixing,
// in reverse. So the door is asserted BY ADDRESS — `matchRoutes` over the real
// `APP_ROUTES`, which is the router the product actually mounts — AND by the
// screen that address opens, which is `data-screen="SET-12B"`.
//
// ⚠ **AND EVERY ROUTED MOUNT BELOW IS UNDER THE REAL PATH PATTERN**
// (`/:tenant/settings/:tab/:sub`), never a bare `MemoryRouter`. A component
// mounted with no matching route has `useParams().tenant` undefined, so every
// address it builds comes out `//settings/…` — a protocol-relative URL to
// another host, which reads as a perfectly good string to `toContain`. That
// fixture is how the portal's broken links passed their own tests.
//
// ⚠ **WHAT THIS SUITE CANNOT SEE, STATED RATHER THAN IMPLIED.** jsdom performs
// no layout and no gate in this repository reads rendered output, so *does the
// Release dialog look right* is not provable here. It was clicked in a real
// browser against a real PostgreSQL row, and the walkthrough is
// `10-scripts/def_not_5637_blocked_addresses_walkthrough.mjs` (hard-won law 6).
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes, matchRoutes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient, ApiResponse } from "@/api/client";
import type {
  OutboundListResponse,
  OutboundSummary,
  SuppressionListResponse,
  SuppressionRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { BLOCKED_SCREEN_ID, BLOCKED_SUB, BlockedAddressesTab } from "./BlockedAddresses";
import { NotificationsTab, QUEUE_PAGE, TAB_SUBS } from "./SettingsNotificationsTab";

/** The address a clerk types, and the one every case below uses. */
// Moved under Configure 2026-10-22; the old address redirects here.
const BLOCKED_PATH = "/brazosbend/settings/reference-data/notifications/blocked";

/** ⚠ A REAL uuid, because the case that matters is that it never reaches the
 *  screen. A placeholder like "id-1" would pass a rule-31 assertion by being
 *  too short to notice. */
const ROW_ID = "0192f3c0-4f2a-7d11-b0a3-6c1d2e3f4a5b";
const RELEASED_ID = "0192f3c0-4f2a-7d11-b0a3-6c1d2e3f4a60";

const TYPO = "marta.whitfeild@example.com";
const SPAM = "annoyed@example.com";

function activeRow(over: Partial<SuppressionRow> = {}): SuppressionRow {
  return {
    id: ROW_ID,
    channel: "email",
    address: TYPO,
    reason: "hard_bounce",
    reason_detail: "550 5.1.1 The email account does not exist",
    suppressed_at: "2026-09-15T14:02:00Z",
    released_at: null,
    released_note: null,
    state: "active",
    ...over,
  };
}

function releasedRow(over: Partial<SuppressionRow> = {}): SuppressionRow {
  return {
    id: RELEASED_ID,
    channel: "email",
    address: "was.a.typo@example.com",
    reason: "hard_bounce",
    reason_detail: null,
    suppressed_at: "2026-03-02T09:00:00Z",
    released_at: "2026-03-04T00:00:00Z",
    released_note: "typo, corrected on the account",
    state: "released",
    ...over,
  };
}

function page(rows: SuppressionRow[]): SuppressionListResponse {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    vocabulary: {
      reasons: ["hard_bounce", "complaint", "unsubscribed", "manual"],
      channels: ["email", "sms", "pdf_print"],
      states: ["active", "released", "all"],
    },
  };
}

function ok<T>(data: T): ApiResponse<T> {
  return { status: 200, data, etag: null, notModified: false };
}

interface Recorded {
  method: "GET" | "POST";
  path: string;
  query?: Record<string, unknown>;
  body?: unknown;
}

/** The server, with the ONE behaviour that matters: a release STAMPS the row
 *  and keeps it, so the next read still returns it. A stub that dropped the
 *  row would let a screen which hides released rows pass. */
function stubClient(calls: Recorded[], rows: SuppressionRow[]): ApiClient {
  const held = [...rows];
  return {
    get: async <T,>(path: string, options?: { query?: Record<string, unknown> }) => {
      calls.push({ method: "GET", path, query: options?.query });
      if (path === "/suppressions") {
        const wanted = String(options?.query?.["f.state"] ?? "all");
        const reason = options?.query?.["f.reason"];
        // The SERVER narrows. The stub does the same so that a screen which
        // stopped sending a filter shows up as MORE rows rather than silently
        // as the same ones.
        const shown = held
          .filter((row) => (wanted === "all" ? true : row.state === wanted))
          .filter((row) => reason === undefined || row.reason === reason);
        return ok(page(shown) as T) as ApiResponse<T>;
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown) => {
      calls.push({ method: "POST", path, body });
      const match = /^\/suppressions\/([^/]+)\/release$/.exec(path);
      if (match !== null) {
        const row = held.find((one) => one.id === match[1]);
        if (row === undefined) throw new Error(`no such row ${match[1]}`);
        const sent = body as { released_on: string; note: string | null };
        row.state = "released";
        row.released_at = `${sent.released_on}T00:00:00Z`;
        row.released_note = sent.note;
        return ok({
          id: row.id,
          address: row.address,
          channel: row.channel,
          state: "released",
          released_at: row.released_at,
          released_note: row.released_note,
        } as T) as ApiResponse<T>;
      }
      throw new Error(`unstubbed POST ${path}`);
    },
    put: async () => {
      throw new Error("unstubbed PUT");
    },
  } as unknown as ApiClient;
}

/** The screen, mounted at its REAL address under its REAL route pattern. */
function mount(calls: Recorded[], rows: SuppressionRow[], readOnly = false) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <MemoryRouter initialEntries={[BLOCKED_PATH]}>
            <Routes>
              <Route
                path="/:tenant/settings/reference-data/notifications/:segment"
                element={
                  <BlockedAddressesTab
                    readOnly={readOnly}
                    client={stubClient(calls, rows)}
                    today="2026-09-17"
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * ⚠ **THE WHOLE `NotificationsTab` — ALL FIVE SUB-TABS — IS GATED BEHIND THE
 * DELIVERY QUEUE'S OWN TWO READS.** `summary.isPending || queue.isPending`
 * returns a skeleton before the sub-tab branch is reached, which is
 * pre-existing behaviour shared with the Rights and Sender tabs and is
 * deliberately NOT changed by this lane. It is why the two door cases SEED
 * those reads: a door test that watched a skeleton would prove nothing about
 * the door, and the first draft of this file did exactly that.
 */
function frameClient(queryClient: QueryClient): QueryClient {
  queryClient.setQueryData(queryKeys.outboundSummary, {
    counts: [],
    totals: {},
    held: 0,
    returned: 0,
    retry_exhausted: 0,
    queued_by_channel: {},
    unpopulated_statuses: [],
    problems: [],
  } satisfies OutboundSummary);
  queryClient.setQueryData(queryKeys.outboundQueue(QUEUE_PAGE), {
    count: 0,
    next: null,
    previous: null,
    results: [],
    vocabulary: {
      statuses: [],
      channels: [],
      source_types: [],
      unpopulated_statuses: [],
      disclosable_channels: [],
    },
  } satisfies OutboundListResponse);
  return queryClient;
}

/** The rows a clerk is actually looking at — never the filter panel, which
 *  renders its option labels in the DOM whether it is open or not. */
function tableText(): ReturnType<typeof within> {
  return within(screen.getByRole("table"));
}

/** Tick a filter option the way a clerk does: open the panel, tick the box. */
async function tickFilter(user: ReturnType<typeof userEvent.setup>, label: string) {
  // ⚠ IT IS A `<summary>` INSIDE A `<details>`, NOT A BUTTON. Its `title`
  // names the dimensions before the panel opens, and it is the one handle that
  // does not depend on how jsdom maps a summary's implicit role.
  const trigger = screen.getByTitle(/^Filter by:/);
  await user.click(trigger);
  // ⚠ AND THE TICK IS SCOPED TO THIS PANEL. The column chooser sitting beside
  // it lists every column as a checkbox too, so a bare `findByLabelText`
  // matches BOTH the *Released* filter option and the *Released* COLUMN — two
  // controls, one word, opposite meanings. Scoping is what makes the assertion
  // about the filter rather than about whichever one the DOM happened to hold
  // first.
  const panel = trigger.closest("details");
  if (panel === null) throw new Error("the filter trigger is not inside a <details>");
  await user.click(await within(panel).findByLabelText(label));
}

function listCalls(calls: Recorded[]): Recorded[] {
  return calls.filter((call) => call.method === "GET" && call.path === "/suppressions");
}

afterEach(cleanup);

// ══════════════════════════════════════════════════════════════════════════
// THE DOOR — the two cases this file exists for
// ══════════════════════════════════════════════════════════════════════════
describe("the door: a clerk can REACH this screen", () => {
  it("the address resolves through the real APP_ROUTES, and to the Settings route", () => {
    // BY ADDRESS. `APP_ROUTES` is the router the product mounts, not a copy of
    // it — an address that stops resolving fails HERE rather than in a support
    // ticket.
    const matches = matchRoutes(APP_ROUTES, BLOCKED_PATH);
    expect(matches).not.toBeNull();
    expect(matches?.[matches.length - 1]?.route.path).toBe(
      "settings/reference-data/notifications/:segment",
    );
  });

  it("that address opens SET-12B and not the empty rule page", () => {
    // BY THE SCREEN IT OPENS. `/settings/notifications/rights` once resolved
    // perfectly and rendered a page with nothing on it, because the segment was
    // missing from the guard's list — a route that reaches no content is
    // hard-won law 2 with the address present.
    expect(TAB_SUBS).toContain(BLOCKED_SUB);

    const queryClient = frameClient(
      new QueryClient({ defaultOptions: { queries: { retry: false } } }),
    );
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
            <MemoryRouter initialEntries={[BLOCKED_PATH]}>
              <Routes>
                <Route
                  path="/:tenant/settings/reference-data/notifications/:segment"
                  element={
                    <NotificationsTab
                      readOnly={false}
                      client={stubClient([], [])}
                      sub={BLOCKED_SUB}
                      onOpenRule={() => undefined}
                    />
                  }
                />
              </Routes>
            </MemoryRouter>
          </TenantRegionalProvider>
        </ToastProvider>
      </QueryClientProvider>,
    );

    expect(html).toContain(`data-screen="${BLOCKED_SCREEN_ID}"`);
    expect(html).toContain('data-testid="notifications-blocked-tab"');
  });

  it("the sub-tab strip OFFERS the door, in the clerk's own words", async () => {
    // The mirror of dead UI: a live screen behind a control that does not point
    // at it. The button is asserted BY NAME and by its label, so a later lane
    // that drops it has to drop this line too.
    const queryClient = frameClient(
      new QueryClient({ defaultOptions: { queries: { retry: false } } }),
    );
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
            <MemoryRouter initialEntries={["/brazosbend/settings/reference-data/notifications"]}>
              <Routes>
                <Route
                  path="/:tenant/settings/reference-data/notifications"
                  element={
                    <NotificationsTab
                      readOnly={false}
                      client={stubClient([], [])}
                      sub={undefined}
                      onOpenRule={() => undefined}
                    />
                  }
                />
              </Routes>
            </MemoryRouter>
          </TenantRegionalProvider>
        </ToastProvider>
      </QueryClientProvider>,
    );

    const door = await screen.findByTestId("notifications-tab-blocked");
    expect(door).toHaveTextContent("Blocked addresses");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// WHAT A CLERK SEES
// ══════════════════════════════════════════════════════════════════════════
describe("the list", () => {
  it("lists the address with WHY and WHEN, and the provider's own sentence", async () => {
    mount([], [activeRow()]);

    expect(await screen.findByText(TYPO)).toBeInTheDocument();
    // ⚠ SCOPED TO THE TABLE. `FilterBar` renders its option labels in the DOM
    // whether the panel is open or not, so a bare `getByText("Bad address")`
    // matches the CHIP as well as the CELL — and would pass over a table that
    // had stopped rendering the column at all.
    expect(tableText().getByText("Bad address")).toBeInTheDocument();
    // The tenant's date format, through the one formatting path (BR-SHL-023).
    expect(tableText().getByText("09/15/2026")).toBeInTheDocument();
    // Kept for the person who has to explain this to a customer. Dropping it
    // would hide what the server is being honest about.
    expect(
      tableText().getByText("550 5.1.1 The email account does not exist"),
    ).toBeInTheDocument();
  });

  it("NEVER puts the suppression's id on screen (B14 rule 31)", async () => {
    const { container } = mount([], [activeRow(), releasedRow()]);

    await screen.findByText(TYPO);
    // The whole rendered document, not one cell: an id can leak through a
    // title, an aria-label or a data attribute just as easily as through a
    // column, and rule 31 covers all of them.
    expect(container.innerHTML).not.toContain(ROW_ID);
    expect(container.innerHTML).not.toContain(RELEASED_ID);
  });

  it("SHOWS a released row's history rather than hiding it — which is why the row is kept", async () => {
    const user = userEvent.setup();
    mount([], [releasedRow()], false);

    // The screen lands on the WORK, so the history is asked for. That the
    // landing is *active* is the next case's assertion, not this one's.
    await tickFilter(user, "Released");

    expect(await screen.findByText("was.a.typo@example.com")).toBeInTheDocument();
    // WHEN and WHY. A column that showed only the date would answer half of
    // *why did this customer stop getting email in March*, and `audit_log` is
    // pruned, so there is no second place to ask.
    expect(tableText().getByText("03/04/2026")).toBeInTheDocument();
    expect(tableText().getByText("typo, corrected on the account")).toBeInTheDocument();
  });

  it("lands on the WORK — active rows — and says so with a chip", async () => {
    const calls: Recorded[] = [];
    mount(calls, [activeRow(), releasedRow()]);

    await screen.findByText(TYPO);
    expect(listCalls(calls)[0]?.query?.["f.state"]).toBe("active");
    // …so the released row is NOT on the first screen, and the chip is what
    // says why. A list showing 1 of 2 rows that cannot say why is DEF-442.
    expect(screen.queryByText("was.a.typo@example.com")).not.toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE FILTERS — and the fact that they narrow on the SERVER
// ══════════════════════════════════════════════════════════════════════════
describe("filtering", () => {
  it("sends f.reason to the SERVER rather than narrowing the page in the browser", async () => {
    const calls: Recorded[] = [];
    const user = userEvent.setup();
    mount(calls, [activeRow(), activeRow({ id: RELEASED_ID, address: SPAM, reason: "complaint" })]);

    await screen.findByText(TYPO);
    await tickFilter(user, "Marked as spam");

    await waitFor(() => {
      expect(listCalls(calls).some((call) => call.query?.["f.reason"] === "complaint")).toBe(true);
    });
    // ⚠ THE ASSERTION THAT MATTERS IS THE ONE ABOVE, not the row count. A
    // browser-side filter would produce exactly this screen over page one and
    // answer *no complaints* for a utility whose complaints are on page two —
    // hard-won law 7's *reporting zero over a scope it silently excludes*,
    // wearing a filter chip, and invisible to any assertion about what is on
    // screen.
    expect(await screen.findByText(SPAM)).toBeInTheDocument();
  });

  it("the All chip means ALL — it sends f.state=all and never the server's default", async () => {
    const calls: Recorded[] = [];
    const user = userEvent.setup();
    mount(calls, [activeRow(), releasedRow()]);

    await screen.findByText(TYPO);
    // ⚠ ITS ACCESSIBLE NAME IS *Clear all*, NOT *All*. `FilterBar` relabels the
    // chip the moment something is applied — sighted users read the chip's
    // state, screen readers get the ACTION — and this screen lands with the
    // state chip applied. A test looking for /^All$/ finds nothing.
    await user.click(screen.getByRole("button", { name: "Clear all" }));

    await waitFor(() => {
      expect(listCalls(calls).some((call) => call.query?.["f.state"] === "all")).toBe(true);
    });
    // Left to the server's own default, clearing the chips would have shown
    // only the ACTIVE rows under a chip saying *nothing is filtered*, with
    // nothing on screen able to say where the released ones went.
    expect(await screen.findByText("was.a.typo@example.com")).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// RELEASE — the control the Product Owner asked for by name
// ══════════════════════════════════════════════════════════════════════════
describe("Release", () => {
  it("states the consequence before it commits, and names the ADDRESS and not an id", async () => {
    const user = userEvent.setup();
    const { container } = mount([], [activeRow()]);

    await screen.findByText(TYPO);
    await user.click(screen.getByTestId(`release-${TYPO}`));

    expect(await screen.findByText("Release address")).toBeInTheDocument();
    // B14 rule 33's CONSEQUENCE kind: two sentences, six words at most each,
    // stated BEFORE the irreversible half of the act.
    expect(
      screen.getByText("Sending to this address resumes. Held messages go out."),
    ).toBeInTheDocument();
    expect(container.innerHTML).not.toContain(ROW_ID);
  });

  it("posts the business date and the note, and the row STAYS — restamped, not removed", async () => {
    const calls: Recorded[] = [];
    const user = userEvent.setup();
    mount(calls, [activeRow()]);

    await screen.findByText(TYPO);
    await user.click(screen.getByTestId(`release-${TYPO}`));
    await screen.findByText("Release address");
    await user.type(screen.getByLabelText("Note"), "typo, fixed on the account");
    await user.click(screen.getByRole("button", { name: /Release ✓/ }));

    await waitFor(() => {
      const posted = calls.find((call) => call.method === "POST");
      expect(posted?.path).toBe(`/suppressions/${ROW_ID}/release`);
      // BR-TEN-043 — the CALLER states the day. The prefill is today's, and
      // the server reads no clock.
      expect(posted?.body).toEqual({
        released_on: "2026-09-17",
        note: "typo, fixed on the account",
      });
    });

    // ⚠ THE HALF THAT IS EASY TO GET WRONG. A screen that spliced the row out
    // of the list on success would look correct and would destroy the record
    // the release exists to leave behind. The list is refetched and the row
    // comes back stamped.
    await waitFor(() => {
      expect(listCalls(calls).length).toBeGreaterThan(1);
    });
  });

  it("refuses a SECOND release on itself, with the reason on the control (BR-SHL-025)", async () => {
    const user = userEvent.setup();
    mount([], [releasedRow()]);

    await tickFilter(user, "Released");
    await screen.findByText("was.a.typo@example.com");
    const action = screen.getByTestId("release-was.a.typo@example.com");
    expect(action).toBeDisabled();
    // The clerk learns the rule instead of hunting for a control somebody
    // removed — and never meets a silent failure at the server.
    expect(action).toHaveAttribute("title", "Already released");
  });

  it("a role that may only VIEW gets the reason on the control, not a missing one", async () => {
    mount([], [activeRow()], true);

    await screen.findByText(TYPO);
    const action = screen.getByTestId(`release-${TYPO}`);
    expect(action).toBeDisabled();
    expect(action).toHaveAttribute("title", "Your role can view this, but not change it.");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// WHAT IS DELIBERATELY ABSENT — said out loud, because an absence is invisible
// to every check this repository has
// ══════════════════════════════════════════════════════════════════════════
describe("the capabilities this screen does NOT declare", () => {
  it("offers no search box and no sortable column, because the server offers neither", async () => {
    const { container } = mount([], [activeRow()]);

    await screen.findByText(TYPO);
    // A search field over an endpoint that ignores `q` is dead UI that looks
    // alive — the exact defect this screen closes in reverse (law 2).
    expect(container.querySelector("input[type=search]")).toBeNull();
    // And no header is a sort button: `GET /suppressions` orders active-first,
    // newest-first and honours no `sort`, so a clickable header would be a
    // control that changes nothing.
    expect(container.querySelectorAll("thead button").length).toBe(0);
  });

  it("does NOT claim *nothing blocked* while a chip is narrowing the list", async () => {
    // ⚠ THE SCREEN LANDS FILTERED, so a tenant with no ACTIVE rows is looking
    // at an empty FILTER RESULT and not at an empty record — and `DataTable`
    // draws the right one of the two by construction (`hasQueryState`). Saying
    // *Nothing blocked* over a view that is hiding the released rows would be
    // the false sentence, and it would hide a history that is the whole reason
    // those rows are kept.
    mount([], [releasedRow()]);

    await waitFor(() => {
      expect(screen.queryByText("Nothing blocked")).not.toBeInTheDocument();
    });
  });

  it("the empty state offers NO way to block an address by hand, because nothing writes one", async () => {
    const user = userEvent.setup();
    mount([], []);

    // Clear the landing chip: with nothing narrowing the list, an empty list
    // really does mean the record is empty.
    await user.click(await screen.findByRole("button", { name: "Clear all" }));

    expect(await screen.findByText("Nothing blocked")).toBeInTheDocument();
    expect(screen.getByText("Every address can be sent to.")).toBeInTheDocument();
    // `REASON_MANUAL` is a lawful value with no writer anywhere in the product,
    // so a `+ Block address` button here would open onto nothing.
    expect(screen.queryByRole("button", { name: /Block/i })).not.toBeInTheDocument();
  });

  it("says paper still goes out — the one fact that stops a clerk panicking", async () => {
    mount([], [activeRow()]);

    await screen.findByText(TYPO);
    // BR-NOT-024: print is the floor on every customer document, so suppressing
    // email never costs a consumer their bill.
    expect(screen.getByText("Paper bills still go out.")).toBeInTheDocument();
    expect(screen.getByText("Released addresses stay on this list.")).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-NOT-5637 (12-governance/10-defect-log.csv) · apps/notifications/api.py (`suppressions`, `suppression_release`) · apps/notifications/suppression_models.py (why the reasons are not interchangeable) · 04-docs/02-decisions/14-ui-conventions.md rules 21/31/32/33/35/36/39/41/42
// generated: 2026-09-17 by an AI lane (the blocked-addresses screen)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: every case proved RED FIRST through vitest — the harness that runs it, never a bare node run (law 7). The sabotages: removing `BLOCKED_SUB` from `TAB_SUBS` · deleting the strip button · rendering `row.id` in the address cell · hiding released rows from the list · replacing `f.reason` with a `.filter()` over `query.data.results` · letting `f.state` fall to the server default · splicing the released row out on success · dropping the `reason` from `releaseRefusal`. Each failure is quoted in the lane report.
// exceptions: (1) jsdom PERFORMS NO LAYOUT, so nothing here proves the screen LOOKS right — that was done in a real browser against a real PostgreSQL row (law 6) and the walkthrough is in `10-scripts/`. (2) THE STUB IS NOT THE SERVER: it narrows on `f.state`/`f.reason` the way the view does so that a screen which stopped sending a filter shows up as MORE rows, but the SQL half is `06-backend/tests/test_def_not_5637_blocked_addresses.py`'s to prove and is proved there.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
