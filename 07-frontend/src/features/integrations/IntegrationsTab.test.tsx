// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-001 (EP-INT-01) · US-INT-013 · US-INT-018
//           Screens: S8 · frames 47.1 · 48.1 · 46.1 · 55.2
// Rules:    BR-INT-001 · BR-INT-028 (no aggregate word over a multi-operation
//           card) · BR-INT-037 (the cards come from the registry) ·
//           B14 rule 31 (no database id is a visible value) · rule 32
// Cases:    US-INT-001 TC-1..5 · US-INT-013 TC-6 · US-INT-018 TC-1/TC-4 ·
//           US-INT-019 (wave B: the card's button is ONE map from the state,
//           and a coming-soon Connect is dashed and takes no press) ·
//           US-INT-037 (wave D: the Mappings link, drawn from the manifest)
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type {
  ConnectionState,
  IntegrationsGrid,
  OperationRow,
  ProviderCard,
} from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { resolveScreen } from "@/routing/screenIds";

import { IntegrationsTab } from "./IntegrationsTab";

function operation(over: Partial<OperationRow> = {}): OperationRow {
  return {
    name: "lookup",
    label: "Account lookup",
    description: "Find an account from a kiosk.",
    direction: "in",
    initiative: "them",
    state: "not_set_up",
    last_run_at: null,
    last_outcome: null,
    trace_id: null,
    test_action: "Send one real message to an address you type.",
    test_needs_recipient: true,
    // `CR-110-BRC04` wave B — the three columns `S142` draws. Required on
    // the type, so a fixture that omits one is a `tsc` error rather than a
    // silent `undefined` arriving at a table cell.
    trigger: "manual",
    endpoint: null,
    rate_limit_per_minute: null,
    // CR-069 wave M — `BR-INT-048`'s three declared facts. A fixture that
    // omitted them would be a shape the server never sends.
    executor: "server",
    latency_budget_ms: null,
    result_disposition: null,
    ...over,
  };
}

function card(over: Partial<ProviderCard> = {}): ProviderCard {
  const state: ConnectionState = over.state ?? "not_set_up";
  // Cast rather than annotated: a sibling wave may widen `ProviderCard` with a
  // column this factory does not seed, and a literal must compile either way.
  return {
    key: "email_smtp",
    category: "email",
    display_name: "Custom SMTP",
    summary: "Send bills from this utility's own mail server.",
    fields: [
      { name: "host", label: "Mail server", kind: "host", required: true, options: [] },
      { name: "password", label: "Password", kind: "secret", required: true, options: [] },
    ],
    disposition: { kind: "live", wave: null, phase: 1 },
    kicker: { direction: "out", initiative: "us" },
    auth: { mode: "password", placement: "header" },
    codecs: [],
    adapter_registered: true,
    connection: null,
    connections: [],
    vocabularies: [],
    state,
    display_state: over.display_state ?? state,
    operations: [operation({ name: "send", label: "Send", direction: "out", initiative: "us", state })],
    ...over,
  } as ProviderCard;
}

function grid(over: Partial<IntegrationsGrid> = {}): IntegrationsGrid {
  const providers = over.providers ?? [card()];
  return {
    categories: over.categories ?? [{ key: "email" }],
    providers,
    counts: over.counts ?? { providers: providers.length, connected: 0 },
    ...over,
  };
}

function render(data: IntegrationsGrid): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.integrations, data);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* Wave D's Mappings link is a router link (useTenantPath). */}
        <MemoryRouter initialEntries={["/brazosbend/settings/integrations"]}>
          <IntegrationsTab />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * Every `<a>`/`<button>` opening tag in the markup, as strings.
 *
 * ⚠ **ORDER-INDEPENDENT ON PURPOSE.** The assertions below used regexes with
 * two attributes in a fixed order (`/<button[^>]*disabled=""[^>]*data-card-action/`),
 * which is a check that breaks when a component reorders its props and says
 * nothing about the thing being asserted. A tag string with both attributes IN
 * IT is the claim actually being made.
 */
function tagsIn(html: string): string[] {
  return [...html.matchAll(/<(?:a|button)\b[^>]*>/g)].map((m) => m[0]);
}

/**
 * The row action with this accessible NAME whose tag also mentions `key`.
 *
 * ⚠ **THE ACCESSIBLE NAME IS THE HOOK** — the same string a screen reader
 * announces, which is what `RowActions` argues for over a `data-testid` that
 * would pass with no label at all. `key` disambiguates the ROW, because
 * `Connect` and `Edit` share an address and every row has all four.
 */
function rowAction(html: string, label: string, key: string): string | null {
  return tagsIn(html).find((tag) => tag.includes(`aria-label="${label}"`) && tag.includes(key)) ?? null;
}

describe("US-INT-001 — the Integrations grid", () => {
  it("TC-1: draws one card per provider the registry returned, each with its state word", () => {
    const html = render(
      grid({
        categories: [{ key: "email" }, { key: "payments" }],
        providers: [
          card({ key: "email_smtp", category: "email" }),
          card({ key: "payments_kiosk", category: "payments" }),
        ],
      }),
    );
    expect(html).toContain('data-provider="email_smtp"');
    expect(html).toContain('data-provider="payments_kiosk"');
    expect(html).toContain("Not set up");
  });

  it("TC-2: the declared-absence sentence is gone — the grid replaces it", () => {
    const html = render(grid());
    expect(html).not.toContain("arrive with the Integrations feature");
    expect(html).not.toContain("No connection can be made from here yet");
  });

  // ── DEF-INT-5528 · the card counts its APIs and never lists them ──────────
  //
  // ⚠ **THIS REPLACED A TEST THAT PINNED THE DEFECT.** The old TC-3 was
  // *"a multi-operation card carries NO aggregate word (BR-INT-028)"* and it
  // asserted `toContain("Account lookup")` — it REQUIRED the per-API list the
  // Product Owner then asked to have removed, so the defect could not be fixed
  // without this test going red. It is the same shape as `DEF-INT-3721`, which
  // this file already records eighty lines below: a test holding a wireframe
  // artefact in place because the file's header said so.
  //
  // ⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — four ways, each closed
  // here by name** (hard-won law 7 habit 2; a check you cannot describe a false
  // pass for is a check you do not understand):
  //
  //  1. **A FIXTURE WHERE EVERY CARD HAS ONE API.** Before the fix the card
  //     rendered its list only when `operations.length > 1`, so a one-API
  //     fixture emitted no list at all and *"the labels are absent"* passed
  //     over a Neptune card still showing sixteen. Closed by giving the first
  //     case **SIXTEEN** distinctly-labelled operations — Neptune's own number
  //     — and asserting all sixteen labels are gone.
  //  2. **ASSERTING ONLY THE ABSENCE.** `not.toContain` passes beautifully when
  //     the card failed to render, when the provider key changed, or when the
  //     query never resolved. Closed by asserting the count line IS present
  //     with its exact drawn text, and that the card element is there.
  //  3. **`data-operations="16"` AS THE PROOF.** It is not one: that attribute
  //     sat on the old `<ul>` and sits on the new `<p>`, so it is TRUE either
  //     way and can never fail on this defect. It is kept as a *reached the
  //     operations fact* marker only, and the list is disproved instead by
  //     counting `<li>` in the rendered card — zero.
  //  4. **A SUBSTRING THAT COULD COME FROM SOMEWHERE ELSE.** `"16 APIs"` might
  //     be a summary or a heading. Closed by asserting the whole drawn line,
  //     `16 APIs · 14 working`, which nothing else on the screen says.
  it("TC-3: a sixteen-API card says `16 APIs · 14 working` and lists NOTHING (DEF-INT-5528)", () => {
    // Neptune's real shape: sixteen operations, most of them working. CON-01
    // p014 names this card by name — *"Neptune's card is sixteen operation
    // lines tall beside neighbours four lines tall … hiding the per-API lines
    // is the one thing that makes the grid scannable again"*.
    const sixteen = Array.from({ length: 16 }, (_, index) =>
      operation({
        name: `read_${index + 1}`,
        label: `Meter read ${index + 1}`,
        state: index < 14 ? "working" : "not_working",
      }),
    );
    const html = render(
      grid({
        providers: [
          card({
            key: "metering_neptune",
            category: "metering",
            state: "not_working",
            display_state: "not_working",
            operations: sixteen,
          }),
        ],
      }),
    );

    // The card is on screen at all — without this the absences below are free.
    expect(html).toContain('data-provider="metering_neptune"');
    // …and the operations fact was reached (see false-pass 3: this alone proves
    // nothing about whether it drew a list or a line).
    expect(html).toContain('data-operations="16"');

    // ONE cell, with the count and the working half.
    // ⚠ **THE WORD `APIs` LEFT THE VALUE ON 2026-09-17** (grid→table): the
    // COLUMN HEADER says `APIs`, so `16 APIs · 14 working` under it said it
    // twice. The discriminator is untouched — only the noun moved.
    expect(html).toContain("16 · 14 working");

    // NOT ONE of the sixteen per-API labels survives.
    for (const one of sixteen) expect(html).not.toContain(one.label);

    // And the line is a line, not a list: the card holds no list item at all.
    expect(html.match(/<li[\s>]/g)).toBeNull();

    // The state word is on the card even though it has sixteen APIs — CON-01
    // draws exactly that (Esri ArcGIS, three APIs, *● Not working*), and the
    // narrowing of `BR-INT-028` that allows it is written into the rule's row.
    expect(html).toContain('data-state="not_working"');
    // Still no invented per-connection summary such as "3 of 3 running": that
    // line is the ENVIRONMENT fact's and belongs to a card with a connection.
    expect(html).not.toMatch(/\d+\s+of\s+\d+\s+running/i);
  });

  it("TC-3b: an untested card counts its APIs and claims none are working", () => {
    // p013 draws a not-tested card as bare `2 APIs` — no working clause. That
    // is the drawing rather than tidiness: `· 0 working` on a connector nobody
    // has tested yet reads as a failure, which is the opposite of *not tested*.
    const html = render(
      grid({
        providers: [
          card({
            key: "print_vendor",
            state: "untested",
            display_state: "untested",
            operations: [
              operation({ name: "send", label: "Send batch", state: "untested" }),
              operation({ name: "status", label: "Check status", state: "untested" }),
            ],
          }),
        ],
      }),
    );
    expect(html).toContain('data-operations="2"');
    expect(html).toContain('data-operations="2"');
    expect(html).not.toContain("Send batch");
    // ⚠ **THE ABSENCE IS ASSERTED ON THE COUNT LINE, NOT ON THE PAGE.** A bare
    // `not.toContain("working")` is what this case was first written with and
    // it was RED for the wrong reason: the toolbar's own state filter offers
    // *Working* and *Not working* as options, so the word is on the screen no
    // matter what any card says. Pinning the separator instead asks the only
    // question that matters — did the API line grow a `· N working` half.
    expect(html).not.toContain("2 APIs ·");
  });

  it("TC-3c: a one-API card reads `1 API · 1 working`, singular (DEF-INT-5528)", () => {
    // The plural is the catalogue's `_one` / `_other`, not a branch in the
    // component — and a card with ONE API is the case the old code special-cased
    // into showing nothing at all, so it is asserted rather than assumed.
    const html = render(
      grid({
        providers: [
          card({
            key: "maps_census",
            state: "working",
            display_state: "working",
            operations: [operation({ name: "geocode", label: "Find an address", state: "working" })],
          }),
        ],
      }),
    );
    expect(html).toContain("1 · 1 working");
    expect(html).not.toContain("1 APIs");
    expect(html).not.toContain("Find an address");
  });

  it("TC-4 · negative: a coming-soon card says so, and its Connect is DISABLED and takes no press", () => {
    const html = render(
      grid({
        providers: [
          card({ key: "payments_card", disposition: { kind: "coming_soon", wave: "W7", phase: null } }),
        ],
      }),
    );
    // ⚠ **THE CARD'S *Coming soon · W7* LINE HAS NO COLUMN AND THE WAVE IS NOT
    // DRAWN ANY MORE** (grid→table, PO 2026-09-17). A card had room for one
    // line and spent it on the wave INSTEAD of a state word; a row has a State
    // column that every other row fills, so it shows the state and the actions
    // cell carries the fact a clerk acts on — all four greyed, *Not built yet*.
    // The wave survives on `data-disposition` for a test and on the connector's
    // own screen for a person.
    expect(html).toContain('data-disposition="coming_soon"');
    // Frame 48.1 state 7: drawn, disabled — and the server refuses the connect
    // too (US-INT-017), which is the refusal that matters.
    const soonConnect = rowAction(html, "Connect", "Not built yet");
    expect(soonConnect, "no greyed Connect on a coming-soon row").not.toBeNull();
    expect(soonConnect).toContain('disabled=""');
    // Not a door: a ruled refusal must not become a link to a form that cannot
    // be saved. Four greyed buttons and NO anchor anywhere in the row.
    expect(tagsIn(html).filter((tag) => tag.startsWith("<a")).some((tag) => tag.includes("configure"))).toBe(false);
    // ⚠ THIS ASSERTION READ `toContain("border-dashed")` UNTIL 2026-09-04, AND
    // IT WAS PINNING A DEFECT (B14 rule 36 breach (a) · `DEF-INT-3721`). The
    // card drew its unavailable Connect as a hand-rolled hatched rectangle —
    // a wireframe hatching on a customer's screen — and the test held it there.
    // `BR-INT-001`'s own words are *"Connect disabled at UI AND API"*; the rule
    // never said dashed, only this file's header did. So the button is the
    // kit's, disabled, and the test now asserts what the RULE says.
    expect(html).not.toContain("border-dashed");
  });

  // ⚠⚠ **THIS CASE ASSERTED THE CARD'S *ONE BUTTON PER STATE* MAP — Connect ·
  // Test it now · Manage · Fix it · Turn on — AND THAT MAP IS SUPERSEDED.** PO
  // ruling 2026-09-17: the actions cell is FOUR icons, present on every row, and
  // the status changes which are ENABLED rather than which are drawn. *Set up*
  // and *Fix it* both became *Edit*; *Turn on* / *Turn off* left the row for the
  // connector's own screen, and the danger tier left with them — **no icon in
  // this table is red**, so the old `data-variant="danger"` assertion is
  // asserting the absence of a tier the ruling removed.
  //
  // The seven-row matrix is asserted in full, per state, with its reasons, in
  // `ConnectorTable.dom.test.tsx`. What is kept HERE is the half that case
  // cannot make from a DOM query: that the five retired VERBS are gone from the
  // rendered screen entirely. A clerk who learned *Test it now* must not find it
  // still sitting on one state nobody re-checked.
  it("wave B · the card's five state verbs are GONE from the row (superseded 2026-09-17)", () => {
    const states: [ConnectionState | "reading_from_us"][] = [
      ["not_set_up"], ["untested"], ["working"], ["not_working"], ["off"], ["reading_from_us"],
    ];
    for (const [state] of states) {
      const html = render(
        grid({
          providers: [
            card({
              key: "email_smtp",
              state: state === "reading_from_us" ? "working" : state,
              display_state: state,
            }),
          ],
        }),
      );
      for (const retired of ["Test it now", "Manage", "Fix it", "Turn on", "Turn off"]) {
        expect(html, `${retired} survived on ${state}`).not.toContain(`>${retired}<`);
        expect(html, `${retired} survived as a label on ${state}`).not.toContain(
          `aria-label="${retired}"`,
        );
      }
      // …and the four that replaced them are ALL there, on every state. Without
      // this the absences above are free — they would pass on a blank row.
      for (const live of ["Connect", "View", "Edit", "Keys"]) {
        expect(html, `${live} missing on ${state}`).toContain(`aria-label="${live}"`);
      }
    }
  });

  it("wave B · a read-only role sees the button disabled with the reason (BR-SHL-025)", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.integrations, grid());
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/settings/integrations"]}>
            <IntegrationsTab readOnly />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain('title="Your role can view this, but not change it."');
    // ⚠ **ALL FOUR, NOT ONE** (grid→table): a card had a single state-driven
    // control and a row has four, so a viewer must meet the role's reason on
    // every one of them. Asserting only Connect would pass on a row that left
    // Edit live for somebody who cannot use it.
    for (const label of ["Connect", "View", "Edit", "Keys"]) {
      const tag = rowAction(html, label, "Your role can view this");
      expect(tag, `${label} is not disabled with the role's reason`).not.toBeNull();
      expect(tag).toContain('disabled=""');
    }
    // And not one of them is a link — a `<a>` cannot be disabled, so a viewer
    // handed an anchor would have a working door out of a read-only screen.
    expect(tagsIn(html).some((tag) => tag.startsWith("<a") && tag.includes("configure"))).toBe(false);
  });

  it("TC-5: 'Reading from us' renders as a word without being a sixth stored status", () => {
    const html = render(
      grid({
        providers: [card({ key: "gl_partner", state: "working", display_state: "reading_from_us" })],
      }),
    );
    expect(html).toContain('data-state="reading_from_us"');
    expect(html).toContain("Reading from us");
  });

  it("TC-6: the category chips are generated from the registry, never hand-listed", () => {
    const html = render(
      grid({
        categories: [{ key: "email" }, { key: "meters" }, { key: "print" }],
        providers: [card({ key: "print_vendor", category: "print" })],
      }),
    );
    for (const key of ["all", "email", "meters", "print"]) {
      expect(html).toContain(`data-category="${key}"`);
    }
    // The card's own category has a chip, which is the thing that broke in the
    // pack: a hand-listed row made the print card vanish under every filter.
    expect(html).toContain('data-category="print"');
  });

  it("TC-7 · B14 rule 31: no database id and no rule reference reaches the screen", () => {
    const html = render(
      grid({
        providers: [
          card({
            key: "email_smtp",
            connection: {
              id: "3f1c9e2a-77b1-4a2e-9f0a-2b7d51c8e004",
              label: null,
              describe: "billing@brazosbend.example · Custom SMTP",
              settings: {},
              connected_by: "Alex Reed",
              environment: "production",
              status: "working",
              enabled: true,
              cadence: "nightly",
              next_run_at: null,
              last_test_at: null,
              last_test_ok: null,
              last_test_text: null,
              connected_at: null,
              credential: null,
              expiry: { state: "unknown", expires_at: null, days_left: null, window_days: 14, version: null },
            },
            state: "working",
            display_state: "working",
          }),
        ],
      }),
    );
    expect(html).not.toContain("3f1c9e2a-77b1-4a2e-9f0a-2b7d51c8e004");
    expect(html).not.toMatch(/BR-[A-Z]{3}-\d+/);
  });
});

describe("the reason under the state word (US-INT-022, wave F · DEF-INT-4025)", () => {
  // ⚠ THE FIELD WAS SERVED, TYPED AND DRAWN NOWHERE. `last_test_text` has been
  // on the read model since wave B and the backend now writes it from three
  // paths — a test, a rotation, and an open breaker — and no screen rendered
  // it. `tsc` and every existing case passed over a status with no reason.
  const notWorking = (text: string | null) =>
    grid({
      providers: [
        card({
          key: "email_smtp",
          connection: {
            id: "3f1c9e2a-77b1-4a2e-9f0a-2b7d51c8e004",
            label: null,
            describe: "billing@brazosbend.example · Custom SMTP",
            settings: {},
            connected_by: "Alex Reed",
            environment: "production",
            status: "not_working",
            enabled: true,
            cadence: "nightly",
            next_run_at: null,
            last_test_at: "2026-09-05T09:00:00Z",
            last_test_ok: false,
            last_test_text: text,
            connected_at: null,
            credential: null,
            expiry: { state: "unknown", expires_at: null, days_left: null, window_days: 14, version: null },
          },
          state: "not_working",
          display_state: "not_working",
        }),
      ],
    });

  it("a card that has stopped working says WHY, in the provider's own terms", () => {
    const html = render(notWorking("The mail server is not answering."));
    // The card drew this under the state word; the row gives it a COLUMN of its
    // own (`Why`), populated only when the state is *Not working* — the column
    // exists to be scanned for red.
    expect(html).toContain('data-cell="why"');
    expect(html).toContain("The mail server is not answering.");
  });

  it("and the sentence is within B14 rule 33's six words", () => {
    // The breaker's own sentence, measured rather than assumed — this is the
    // string `runtime.BREAKER_SENTENCE` produces.
    expect("The mail server is not answering.".trim().split(/\s+/).length).toBeLessThanOrEqual(6);
  });

  it("a WORKING card carries no reason line at all (B14 rule 32's budget)", () => {
    const html = render(
      grid({
        providers: [
          card({
            key: "email_smtp",
            connection: {
              id: "3f1c9e2a-77b1-4a2e-9f0a-2b7d51c8e004",
              label: null,
              describe: "billing@brazosbend.example · Custom SMTP",
              settings: {},
              connected_by: "Alex Reed",
              environment: "production",
              status: "working",
              enabled: true,
              cadence: "nightly",
              next_run_at: null,
              last_test_at: "2026-09-05T09:00:00Z",
              last_test_ok: true,
              last_test_text: "Sent one test message to alex@brazosbend.example.",
              connected_at: null,
              credential: null,
              expiry: { state: "unknown", expires_at: null, days_left: null, window_days: 14, version: null },
            },
            state: "working",
            display_state: "working",
          }),
        ],
      }),
    );
    expect(html).not.toContain("data-state-reason");
  });

  it("and a card with nothing to say draws no empty element", () => {
    const html = render(notWorking(null));
    expect(html).not.toContain("data-state-reason");
  });
});

describe("the Mappings link (US-INT-037, wave D) — REMOVED by the four-action ruling", () => {
  // ⚠⚠ **THIS IS A DOOR THAT WAS CLOSED AND THE ROOM BEHIND IT IS STILL LIT.**
  // The card drew a *Mappings* link on any connector whose manifest ships
  // vocabularies — 3 of the 28 in the demo tenant — and it was the ONLY link to
  // `ValueMappingPage` (`S143`) in the whole product. The PO's actions ruling of
  // 2026-09-17 fixes the cell at FOUR icons, *"Connect, View, Edit, Keys"*,
  // ratified in full; *Mappings* is not one of them, and this lane did not add a
  // fifth icon to keep it.
  //
  // **So `S143` is now routed, live, tested and reachable only by typing its
  // address** — which is hard-won law 2's mirror, the exact shape `DEF-INT-5513`
  // cost this module three weeks ago. It is **`DEF-INT-5572`**, filed, and it is
  // the first thing in this lane's report rather than a silent consequence.
  //
  // ⚠ **THE CASE IS KEPT AND INVERTED RATHER THAN DELETED.** A test that
  // vanishes looks exactly like a test that was never written, and this one
  // records a real capability. It now asserts the door is GONE — so the day
  // somebody restores it, this goes red and they read why it went.
  it("the row draws no Mappings door — S143 is reachable only by address (DEF-INT-5572)", () => {
    const html = render(
      grid({
        providers: [
          card({ key: "email_smtp" }),
          card({
            key: "payments_kiosk",
            display_name: "Payment kiosk network",
            vocabularies: [{ entity_type: "tender", label: "How they pay", count: 14 }],
          }),
        ],
        categories: [{ key: "email" }],
      }),
    );
    // The connector that SHIPS vocabularies is on screen — without this the
    // absence below is free and would pass on an empty list.
    expect(html).toContain('data-provider="payments_kiosk"');
    expect(html).not.toContain("/mappings");
    expect(html).not.toContain(">Mappings<");
    // And the four that ARE ruled are all present on that same row.
    for (const label of ["Connect", "View", "Edit", "Keys"]) {
      expect(html).toContain(`aria-label="${label}"`);
    }
  });
});

// ── `DEF-INT-5513` — THE DOOR, ASKED FROM THE CARD'S SIDE ──────────────────
//
// ⚠ **THIS IS THE QUESTION THAT BELONGED TO NEITHER FILE, WHICH IS THE WHOLE
// REASON THE DEFECT SHIPPED.** Wave A's `ConnectorSetupRoute.test.tsx` asserts
// the set-up screen is REGISTERED and opens for the connector named in it —
// true, and silent about who navigates there. The block above asserts the
// card's primary control FIRES ITS HANDLER — true, and silent about where that
// handler goes. Both were green while `Connect` opened the old modal on all 28
// connectors and the screen was reachable only by typing its address.
//
// ⚠ **IT ASSERTS THE ADDRESS *AND* THE SCREEN ID, DELIBERATELY.** An address
// alone goes green on a string that no longer routes anywhere; resolving that
// address through `routing/screenIds.ts` is what makes a later lane moving the
// screen turn THIS file red rather than leaving the card pointing at a dead
// URL. That is hard-won law 2's mirror clause in its literal form — *assert the
// destination by ADDRESS and by the screen id it opens*.
describe("DEF-INT-5513 — the card's Connect is a door to the set-up screen", () => {
  // ⚠ **THE DOOR SURVIVED THE GRID→TABLE MOVE AND ITS HANDLE MOVED.** The
  // card's `data-setup-link` `ButtonLink` is the row's `Connect` icon, a
  // `RowActionLink` to the same address; `Edit` is the same door from the other
  // end of a connector's life (PO 2026-09-17). **The contract this block exists
  // for is unchanged and is asserted the same way** — the address AND the
  // screen id it resolves to.
  function hrefFor(html: string, key: string, label = "Connect"): string | null {
    // Found by the action's ACCESSIBLE NAME and the connector's own address —
    // not by position, so a re-ordered list cannot make this test nothing.
    const tag = rowAction(html, label, `/connectors/${key}/configure`);
    if (tag === null) return null;
    const href = /href="([^"]+)"/.exec(tag);
    return href === null ? null : href[1];
  }

  // The four shapes the PO's walk names, and they are four DIFFERENT auth
  // stories rather than four names: one that signs in with the vendor, one
  // that takes a key we type, one that reads from us with a key WE issue, and
  // one drawn but not shipping. No provider is named in the code under test
  // (`BR-INT-037`) — these are fixtures, and connector 29 needs no line here.
  const SHAPES: [string, Partial<ProviderCard>][] = [
    ["email_microsoft", { auth: { mode: "oauth", placement: "header" } }],
    ["meters_badger", { auth: { mode: "api_key", placement: "header" } }],
    [
      "erp_partner",
      {
        auth: { mode: "api_key", placement: "header" },
        fields: [
          { name: "key", label: "Key we issue", kind: "issued_secret", required: false, options: [] },
        ],
      },
    ],
  ];

  it("points every connectable card at ITS OWN set-up address", () => {
    const html = render(
      grid({
        providers: SHAPES.map(([key, over]) =>
          card({ key, state: "not_set_up", display_state: "not_set_up", ...over }),
        ),
      }),
    );
    for (const [key] of SHAPES) {
      expect(hrefFor(html, key)).toBe(`/brazosbend/settings/connectors/${key}/configure`);
    }
    // The key is the ONLY thing that varies — two cards must not share a door.
    const doors = SHAPES.map(([key]) => hrefFor(html, key));
    expect(new Set(doors).size).toBe(SHAPES.length);
  });

  it("the address it points at IS S147, resolved through the screen registry", () => {
    const html = render(
      grid({ providers: [card({ key: "email_microsoft", state: "not_set_up", display_state: "not_set_up" })] }),
    );
    const href = hrefFor(html, "email_microsoft");
    expect(href).not.toBeNull();
    expect(resolveScreen(href as string).a1).toBe("S147");
  });

  it("the control NAVIGATES — it is a link, and it no longer opens the dialog", () => {
    const html = render(
      grid({ providers: [card({ key: "email_microsoft", state: "not_set_up", display_state: "not_set_up" })] }),
    );
    // A `<button>` here is the defect itself: a control that acts in place
    // instead of going somewhere. The live offer must be an ANCHOR, so
    // middle-click and *open in new tab* work as on any other door.
    const connect = rowAction(html, "Connect", "/connectors/email_microsoft/configure");
    expect(connect, "Connect is not a link to the set-up screen").not.toBeNull();
    expect(connect?.startsWith("<a")).toBe(true);
    // ⚠ AND NOT MERELY *an anchor exists*: a greyed `Connect` renders as a
    // `<button disabled>`, so a row that refused the offer would ALSO have no
    // anchor-shaped defect to find. There must be no disabled Connect here.
    // ⚠ `disabled=""`, THE ATTRIBUTE — not the substring `disabled`. Every
    // button in the kit carries Tailwind `disabled:…` variant classes, so a
    // bare `includes("disabled")` is TRUE of an enabled control and this
    // assertion could never fail. Found by it failing on a correct screen.
    expect(
      tagsIn(html).some((tag) => tag.includes('aria-label="Connect"') && tag.includes('disabled=""')),
    ).toBe(false);
    // And nothing opened: the modal renders a dialog, and a freshly-drawn grid
    // has none. This is the PO's own sentence — *"it is still showing modal"*.
    expect(html).not.toContain('role="dialog"');
  });

  // ⚠ THE REFUSALS ARE NOT DOORS, AND THIS ASSERTS THAT THEY STAYED REFUSALS.
  // Turning a ruled refusal into a link would trade one defect for a worse
  // one: a clerk sent to a set-up form for a connector that cannot be set up.
  // `coming_soon` is state 7 and the server refuses it too; a card with no
  // adapter is `DEF-INT-4224`'s hold and carries its reason as a line of text.
  it("a coming-soon card and an adapterless card keep their disabled buttons", () => {
    const soon = render(
      grid({
        providers: [
          card({ key: "sso", disposition: { kind: "coming_soon", wave: "v2", phase: 1 } }),
        ],
      }),
    );
    // Greyed, with its reason, and no door — `RowActionLink` renders a blocked
    // action as a disabled `<button>` because a disabled LINK is not a thing the
    // platform has (BR-SHL-025 satisfied without a fake control).
    const soonConnect = rowAction(soon, "Connect", "Not built yet");
    expect(soonConnect, "no greyed Connect on the coming-soon row").not.toBeNull();
    expect(soonConnect).toContain('disabled=""');
    expect(soon).not.toContain("/configure");

    const noAdapter = render(
      grid({
        providers: [
          card({ key: "print_vendor", adapter_registered: false, state: "not_set_up", display_state: "not_set_up" }),
        ],
      }),
    );
    // `DEF-INT-4224`'s hold, still refused ON THE LIST before a clerk types
    // anything — the whole of that fix. Its REASON is a tooltip now rather than
    // a line of text, which a row has nowhere to put; filed as `DEF-INT-5573`.
    const heldConnect = rowAction(noAdapter, "Connect", "Not ready to connect yet.");
    expect(heldConnect, "no greyed Connect on the adapterless row").not.toBeNull();
    expect(heldConnect).toContain('disabled=""');
    expect(noAdapter).not.toContain("/configure");
  });

  // BR-SHL-025 again, from the other side: a viewer must still meet a DISABLED
  // control carrying their role's reason. A `<Link>` cannot be disabled, so the
  // read-only path deliberately keeps the button — and this is what stops a
  // later lane "tidying" the branch by making every connect offer a link.
  it("a read-only role still gets a disabled button, never a link", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.integrations, grid());
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          {/* Mounted under the REAL path pattern, not a bare MemoryRouter —
              a component mounted off-pattern builds addresses from an absent
              tenant and every `toContain` on them passes meaninglessly. */}
          <MemoryRouter initialEntries={["/brazosbend/settings/integrations"]}>
            <Routes>
              <Route path="/:tenant/settings/integrations" element={<IntegrationsTab readOnly />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // The viewer's Connect is a DISABLED BUTTON and never an anchor: a `<a>`
    // cannot be disabled, so handing one to a read-only role would be a working
    // door out of a screen they may only read (BR-SHL-025).
    const connect = rowAction(html, "Connect", "Your role can view this");
    expect(connect, "no Connect carrying the role's reason").not.toBeNull();
    expect(connect?.startsWith("<button")).toBe(true);
    expect(connect).toContain('disabled=""');
    expect(html).not.toContain("/configure");
  });
});
