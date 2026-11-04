// @vitest-environment jsdom
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-041 (EP-INT-11) — S142 *Who has been reading*, frame 46.2.
// Rules:    BR-INT-035 (who, when, how many, and the key as a HINT) ·
//           B14 rule 31 (no database id is a visible value) · rule 32 (a
//           stated absence is CLOSED by default) · rule 21 (Tailwind only —
//           the file is on route-b-migrated.txt)
// Cases:    the three rows and the unusual fourth · the WATCH quote · the
//           register's inward sentence · the panel draws NOTHING for a
//           connection nothing reads from · the key never reaches the DOM ·
//           ⚠ **ACC-01's THREE STATES, WHICH ARE THE POINT** — loading,
//           empty and failed must be three DIFFERENT things on screen
//           (`DEF-INT-5484`); the subtitle under the heading; the WATCH
//           block as a quote rather than a filled box
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { AccessLog, OperationRow, SubprocessorRow } from "@/api/integrationsEndpoints";

import { AccessLogPanel, readsFromUs, visibleRows } from "./AccessLogPanel";

const PARTNER = "gl_partner";
const HINT = "••••7Q2F";
const KEY = "sbh_live_7Q2F_this_must_never_render";

function operation(over: Partial<OperationRow> = {}): OperationRow {
  return {
    name: "read_payments",
    label: "Payments",
    description: "They collect the payments we took.",
    direction: "out",
    initiative: "them",
    state: "working",
    last_run_at: null,
    last_outcome: null,
    trace_id: null,
    test_action: null,
    test_needs_recipient: false,
    // `CR-110-BRC04` wave B — the three columns `S142` draws. A fixture
    // that omits one is a `tsc` error rather than a silent `undefined`,
    // which is why they are REQUIRED on the type and not optional.
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

/** Frame 46.2's four rows, the last one the unusual read. */
const LOG: AccessLog = {
  items: [
    {
      when: "2026-09-06T06:14:00Z",
      what: "Payments, 1–30 Sep",
      rows: 1842,
      detail: `Payments, 1–30 Sep · 1842 records · page 1 of 1 · ${HINT}`,
      hint: HINT,
      unusual: false,
      outcome: "succeeded",
    },
    {
      when: "2026-09-05T06:14:00Z",
      what: "Payments, 1–29 Sep",
      rows: 1790,
      detail: `Payments, 1–29 Sep · 1790 records · page 1 of 1 · ${HINT}`,
      hint: HINT,
      unusual: false,
      outcome: "succeeded",
    },
    {
      when: "2026-09-05T06:14:00Z",
      what: "Bills, September",
      rows: 612,
      detail: `Bills, September · 612 records · page 1 of 1 · ${HINT}`,
      hint: HINT,
      unusual: false,
      outcome: "succeeded",
    },
    {
      when: "2026-09-03T02:41:00Z",
      what: "Payments, 2 years",
      rows: 48000,
      detail: `Payments, 2 years · 48000 records · page 1 of 96 · ${HINT}`,
      hint: HINT,
      unusual: true,
      outcome: "succeeded",
    },
  ],
  total_records: 52244,
  unusual_rows_at: 10000,
};

const REGISTER: SubprocessorRow[] = [
  {
    party: "Aclarian",
    direction: "inward",
    what: "payments, bills and customers",
    authorised_by: "Alex Reed",
    authorised_on: "2026-09-03T09:00:00Z",
    environment: "production",
    sentence: "Aclarian — reads payments, bills and customers — authorised by Alex Reed on 2026-09-03",
  },
  {
    party: "Twilio",
    direction: "outward",
    what: "text messages",
    authorised_by: "Alex Reed",
    authorised_on: "2026-08-12T09:00:00Z",
    environment: "production",
    sentence: "Twilio — receives text messages — authorised by Alex Reed on 2026-08-12",
  },
];

function ok<T>(data: T): ApiResponse<T> {
  return { status: 200, data, etag: null, notModified: false };
}

function mount(operations: OperationRow[] = [operation()]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const client = {
    get: vi.fn(async (path: string) =>
      path.includes("subprocessors") ? ok({ items: REGISTER }) : ok(LOG),
    ),
  } as unknown as ApiClient;
  queryClient.setQueryData(["integrations", "access-log", PARTNER], LOG);
  queryClient.setQueryData(["integrations", "subprocessors"], REGISTER);
  const view = render(
    <QueryClientProvider client={queryClient}>
      <AccessLogPanel
        providerKey={PARTNER}
        operations={operations}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        client={client}
      />
    </QueryClientProvider>,
  );
  return { ...view, client };
}

/** A mount whose read NEVER RESOLVES.
 *
 *  ⚠ **THIS IS THE FIXTURE THE WHOLE FILE TURNED ON, AND THE EASY VERSION OF
 *  IT PASSES WRONGLY.** A client that resolves immediately — or a
 *  `setQueryData` seed, which is what every other case here uses — leaves
 *  `isPending` false on the first render, so a loading assertion would be
 *  testing the LOADED path and going green on a component with no loading
 *  branch at all. The promise below is never settled, deliberately. */
function mountPending(operations: OperationRow[] = [operation()]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const client = {
    get: vi.fn(() => new Promise<never>(() => {})),
  } as unknown as ApiClient;
  return render(
    <QueryClientProvider client={queryClient}>
      <AccessLogPanel
        providerKey={PARTNER}
        operations={operations}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        client={client}
      />
    </QueryClientProvider>,
  );
}

/** A mount whose read FAILS. `retry: false` so `isError` arrives at once. */
function mountFailed(operations: OperationRow[] = [operation()]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const client = {
    get: vi.fn(async () => {
      throw new Error("the access log did not load");
    }),
  } as unknown as ApiClient;
  return render(
    <QueryClientProvider client={queryClient}>
      <AccessLogPanel
        providerKey={PARTNER}
        operations={operations}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        client={client}
      />
    </QueryClientProvider>,
  );
}

/** A mount whose read SUCCEEDS and returns nothing — `erp_workday` live. */
const NOTHING: AccessLog = { items: [], total_records: 0, unusual_rows_at: 10000 };
function mountEmpty(operations: OperationRow[] = [operation()]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const client = {
    get: vi.fn(async (path: string) =>
      path.includes("subprocessors") ? ok({ items: [] }) : ok(NOTHING),
    ),
  } as unknown as ApiClient;
  queryClient.setQueryData(["integrations", "access-log", PARTNER], NOTHING);
  queryClient.setQueryData(["integrations", "subprocessors"], []);
  return render(
    <QueryClientProvider client={queryClient}>
      <AccessLogPanel
        providerKey={PARTNER}
        operations={operations}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        client={client}
      />
    </QueryClientProvider>,
  );
}

/** What the panel says, as one string, with the furniture that is on screen in
 *  EVERY state stripped out. Two states that produce the same sentence here are
 *  `DEF-INT-5484`, and that is the comparison case 4 below makes. */
function said(container: HTMLElement): string {
  const clone = container.cloneNode(true) as HTMLElement;
  clone.querySelectorAll("[data-access-watch], [data-register]").forEach((one) => one.remove());
  return (clone.textContent ?? "").replace(/\s+/g, " ").trim();
}

describe("S142 · who has been reading (US-INT-041)", () => {
  afterEach(cleanup);

  it("draws frame 46.2's four rows, with the unusual one emphasised", () => {
    const { container } = mount();
    const rows = container.querySelectorAll("[data-access-row]");
    expect(rows).toHaveLength(4);
    expect([...rows].map((one) => one.getAttribute("data-unusual"))).toEqual([
      "false",
      "false",
      "false",
      "true",
    ]);
    // The emphasis is the whole difference — nothing is refused because of it.
    const unusual = container.querySelector('[data-unusual="true"]');
    expect(unusual?.innerHTML).toContain("font-semibold");
    expect(screen.getByText("48,000")).toBeTruthy();
  });

  // ⚠ SUPERSEDED 2026-09-16 — this case asserted the filled amber
  // `ConsequenceBox`, which `ACC-01` finding ⑨ replaces with a left-ruled
  // quote. The assertion it made now lives in the ⑨ case at the foot of this
  // file, which checks the same sentence in the shape the blueprint draws.

  it("the register's INWARD row is a sentence, and the outward one is not shown here", () => {
    const { container } = mount();
    const rows = container.querySelectorAll("[data-register-row]");
    expect(rows).toHaveLength(1);
    expect(rows[0].getAttribute("data-register-row")).toBe("inward");
    expect(rows[0].textContent).toContain("Aclarian — reads payments, bills and customers");
    expect(rows[0].textContent).toContain("authorised by Alex Reed");
  });

  it("the row says WHO — the key's hint is on the screen", () => {
    // ⚠ THIS ASSERTION WAS ADDED AFTER THE BROWSER FOUND IT MISSING.
    // `BR-INT-035` records a read "under which key" and the first draft
    // rendered when · what · how many, so the screen called *Who has been
    // reading* did not say who. Every unit test passed over it, because none
    // of them asked.
    const { container } = mount();
    const hints = container.querySelectorAll("[data-access-hint]");
    expect(hints).toHaveLength(4);
    expect(hints[0].textContent).toBe(HINT);
  });

  it("⚠ the key never reaches the DOM — only its hint does", () => {
    const { container } = mount();
    expect(container.innerHTML).not.toContain(KEY);
    expect(container.innerHTML).not.toContain("sbh_live");
  });

  it("no database id is a visible value (B14 rule 31)", () => {
    const { container } = mount();
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("⚠ a busy partner cannot push the unusual read off the SCREEN either", () => {
    // The server keeps the unusual row in the payload; this is the same
    // property one layer up. A plain `slice(0, 20)` would drop the 48,000-row
    // collection, because it is OLDER than a hundred small reads — which is
    // exactly how a partner would hide it. Found by looking at a 5,800-pixel
    // section after this wave's own walkthrough made a hundred requests.
    const noise = Array.from({ length: 60 }, (_, index) => ({
      when: `2026-09-06T07:${String(index % 60).padStart(2, "0")}:00Z`,
      what: "Payments, 2 Sep",
      rows: 1,
      detail: `Payments, 2 Sep · 1 records · page 1 of 1 · ${HINT}`,
      hint: HINT,
      unusual: false,
      outcome: "succeeded",
    }));
    const unusual = LOG.items[3];
    const shown = visibleRows([...noise, unusual]);
    expect(shown).toHaveLength(21);
    expect(shown).toContain(unusual);
  });

  it("draws NOTHING for a connection nothing reads from — no empty box", () => {
    const { container } = mount([operation({ direction: "in", initiative: "us" })]);
    expect(container.querySelector("[data-access-log]")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("the quadrant decides, never the provider's name (G77's rule on this side)", () => {
    expect(readsFromUs([operation()])).toBe(true);
    expect(readsFromUs([operation({ initiative: "us" })])).toBe(false);
    expect(readsFromUs([operation({ direction: "in" })])).toBe(false);
    expect(readsFromUs([])).toBe(false);
  });

  // ── ACC-01's three states · DEF-INT-5484 ───────────────────────────────
  //
  // ⚠ **EVERY ASSERTION BELOW NAMES WHAT IS ON SCREEN, NOT ONLY WHAT IS
  // ABSENT.** "The empty sentence is gone" passes on a component that renders
  // nothing at all, which is the false pass this file is most exposed to: the
  // panel's very first branch is `if (!enabled) return null`, so a fixture
  // mistake empties it completely and a not-toContain check calls that a fix.

  it("① while the read is in flight the panel says it is LOADING", async () => {
    const { container } = mountPending();
    // What IS shown: the kit's own loading state, which carries aria-busy.
    const busy = container.querySelector('[aria-busy="true"]');
    expect(busy).toBeTruthy();
    expect(busy?.getAttribute("aria-label")).toBe("Loading…");
    // The panel is still here — this is not the `return null` path.
    expect(container.querySelector("[data-access-log]")).toBeTruthy();
    expect(screen.getByText("Who has been reading")).toBeTruthy();
    // And it does NOT claim the partner has read nothing.
    expect(said(container)).not.toContain("Nobody has read anything");
    expect(said(container)).not.toContain("Nobody has collected anything yet");
    await Promise.resolve();
  });

  it("③ a read that FAILED says so, and offers Retry", async () => {
    const { container } = mountFailed();
    // What IS shown — the drawing's two sentences, byte for byte.
    expect(await screen.findByText("The access log did not load")).toBeTruthy();
    expect(
      screen.getByText("We cannot say whether anybody has read anything."),
    ).toBeTruthy();
    // ONE button, and it is the one the drawing names.
    const block = container.querySelector("[data-access-failed]");
    expect(block).toBeTruthy();
    expect(block?.getAttribute("role")).toBe("alert");
    const buttons = [...(block?.querySelectorAll("button") ?? [])].map((one) => one.textContent);
    expect(buttons).toEqual(["Retry"]);
    // And it does NOT say all clear.
    expect(said(container)).not.toContain("Nobody has read anything");
    expect(said(container)).not.toContain("Nobody has collected anything yet");
  });

  it("② a read that SUCCEEDED and returned nothing says both of the drawing's lines", () => {
    const { container } = mountEmpty();
    expect(screen.getByText("Nobody has read anything")).toBeTruthy();
    // ⚠ THE SECOND LINE IS THE HALF THAT WAS MISSING. One sentence cannot
    // distinguish an absence from a failure; two can, because the second one
    // is a claim about the PARTNER that only a successful read supports.
    expect(screen.getByText("This partner has a key and has not used it.")).toBeTruthy();
    expect(container.querySelector("[data-access-row]")).toBeNull();
    expect(container.querySelector('[aria-busy="true"]')).toBeNull();
    expect(container.querySelector("[data-access-failed]")).toBeNull();
  });

  it("⚠ the three states are three DIFFERENT things on screen (DEF-INT-5484)", async () => {
    const pending = mountPending();
    const whileLoading = said(pending.container);
    cleanup();

    const failed = mountFailed();
    await screen.findByText("The access log did not load");
    const whenFailed = said(failed.container);
    cleanup();

    const nothing = mountEmpty();
    const whenEmpty = said(nothing.container);

    // Three sentences, three meanings. On the shipped panel all three of these
    // read "Who has been reading An access log, not a run history Nobody has
    // collected anything yet." — confirmed in a browser on 2026-09-16.
    expect(new Set([whileLoading, whenFailed, whenEmpty]).size).toBe(3);
    // And each says its own thing, so the set above cannot be satisfied by
    // three different kinds of nothing.
    expect(whenFailed).toContain("The access log did not load");
    expect(whenEmpty).toContain("Nobody has read anything");
    expect(whileLoading).toContain("Who has been reading");
  });

  it("⑥ the subtitle is plain text UNDER the heading, never a tag beside it", () => {
    const { container } = mountEmpty();
    const subtitle = container.querySelector("[data-access-subtitle]");
    expect(subtitle).toBeTruthy();
    expect(subtitle?.textContent).toBe("An access log, not a run history");
    // ACC-01 draws it grey and plain. The shipped panel drew it as a bordered
    // warning-tone tag floated right of the title.
    expect(subtitle?.className).not.toContain("border");
    expect(subtitle?.className).not.toContain("warning-700");
    // Under the heading: the h2 comes first in document order and they share a
    // column rather than a `justify-between` row.
    const head = container.querySelector("[data-access-head]");
    expect(head?.className).toContain("flex-col");
    expect(head?.firstElementChild?.tagName).toBe("H2");
    expect(head?.lastElementChild).toBe(subtitle);
  });

  it("⑨ WATCH is a quote with a left rule, not a filled box", () => {
    const { container } = mountEmpty();
    const watch = container.querySelector("[data-access-watch]");
    expect(watch).toBeTruthy();
    expect(watch?.tagName).toBe("BLOCKQUOTE");
    expect(watch?.className).toContain("border-l-2");
    expect(watch?.textContent).toContain("WATCH");
    expect(watch?.textContent).toContain("Why this screen exists");
    expect(watch?.textContent).toContain("two in the morning");
    // The filled amber ConsequenceBox is gone.
    expect(container.querySelector('[data-consequence="access-log"]')).toBeNull();
  });
});

// ── Lifecycle ────────────────────────────────────────────────────────────
// packet: US-INT-041@wave-S (EP-INT-11) · frame 46.2
// generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: vitest · tsc
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ─────────────────────────────────────────────────────────────────────────
