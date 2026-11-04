// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-PAY-6314` — `POST /counters` reads `service_centre_id` and
//          `StartCounterBody` declared `service_centre`; the server requires
//          `opened_at` and neither the type nor the form has ever mentioned it,
//          so a clerk could not open a till at all.
//          `DEF-PAY-6315` — the same break on `close`, `force-close` and
//          `declare`, each missing the moment its endpoint requires.
// Screens: 3·3a Start · 3·3b Close · 3·3c Force close · 3·3d Declare
// Rules:   `BR-TEN-043` (every moment is an INPUT; `apps/payments/` reads no
//          clock — gate G6) · `BR-TEN-081` / `OQ-153` (a naive moment is
//          anchored in the TENANT's zone, which is why 3·3a posts a wall clock
//          and the other three post an instant) · `IS-8` / `BR-SHL-023` (one
//          formatting path; the tenant's format and zone) · B14 rule 33
//          (RATIONALE is zero words on screen) · rule 43 (a piece of UI is a
//          COMPONENT — hence `DateTimeField` in the kit) · hard-won law 2
//          (built is not wired) · law 7 (a check whose output cannot
//          distinguish pass from fail is worse than no check)
//
// ⚠ **PO RULING 2026-09-23 SUPERSEDED THIS FILE'S FIRST SHAPE.** It was
// written asserting that 3·3a draws NO timestamp field and stamps
// `toISOString()`, on the authority of p055's *Fields* row (*"Two."*). The PO,
// verbatim: *"show date and time pciker and deult should be as per date time
// format set by utility and timezone - show the detault time"*. A drawing is
// the agreement (rule 41) and a ruling outranks it. The superseded case is
// named inside the replacing one rather than deleted silently.
// Tests:   this file · 06-backend/tests/test_cr136_p2_counters.py
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS AND WHY A MOCKED `startCounter` CANNOT REPLACE IT
// ══════════════════════════════════════════════════════════════════════════
// `StartCounterBody` was written to match its CALLER rather than its ENDPOINT.
// It declared `service_centre: string` and `opening_float: string`; the form
// passed exactly those two; `tsc` was green — because the only thing `tsc` can
// check is whether the front end agrees with ITSELF. `opened_at` was not a
// missing property: there was no property to miss.
//
// So a test that mocks the endpoint wrapper and asserts it was called cannot
// see this class of defect, ever, in either direction. Neither can one that
// hand-writes a body against the exported interface — that asserts the type
// agrees with a copy of itself. **The two ends have to be read from two
// different files**, and that is what this does:
//
//   · the SERVER end is parsed out of `counters_api.py`'s own source — every
//     `payload.get("…")` it reads and every `_required_moment(payload, "…")`
//     it demands;
//   · the CLIENT end is the body a recording stub `ApiClient` actually
//     receives when the REAL modal is mounted, filled in and submitted.
//
// Then two assertions per route, and they catch opposite faults:
//   1. every REQUIRED key the endpoint reads is in the body   → `opened_at`
//   2. every key in the body is a key the endpoint reads      → `service_centre`
//
// ⚠ **THE PARSE MUST BE PROVED TO HAVE FOUND SOMETHING** (law 7's fifth shape:
// a check reporting zero over a scope it silently excludes). If
// `counters_api.py` moves, is renamed, or stops using these two spellings, the
// key sets come back EMPTY and both assertions above pass vacuously over four
// broken routes. `the contract is read from the server's own source` asserts
// the file was found, that all four endpoints are in it, and that each one
// yields at least one required moment — so a silent zero is RED, not green.
import "@/i18n";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CounterDetail } from "@/api/counterEndpoints";
import { nowInZone, sameDayBounds } from "@/components/DateCell";
import { ToastProvider } from "@/components/Toast";

import { CloseCounterModal } from "./CloseCounterModal";
import { DeclareCountModal } from "./DeclareCountModal";
import { ForceCloseCounterModal } from "./ForceCloseCounterModal";
import { StartCounterModal } from "./StartCounterModal";

// ── the server end, read from the server ───────────────────────────────────
// `import.meta.url` is an `http:` URL under jsdom and `fileURLToPath` refuses
// it (see `SettingsOwnedField.test.tsx`), so the repository root is walked up
// from the working directory instead.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  existsSync(p: string): boolean;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...parts: string[]): string;
  dirname(p: string): string;
  resolve(p: string): string;
};

const COUNTERS_API = "06-backend/apps/payments/counters_api.py";

/** `process.cwd()` without `@types/node`, which this project does not install.
 *  The alternative — `import.meta.url` — is an `http:` URL under jsdom. */
function workingDirectory(): string {
  const host = globalThis as { process?: { cwd?: () => string } };
  return host.process?.cwd?.() ?? ".";
}

function repoFile(relative: string): string {
  let dir = nodePath.resolve(workingDirectory());
  for (let hop = 0; hop < 6; hop += 1) {
    const candidate = nodePath.join(dir, relative);
    if (nodeFs.existsSync(candidate)) {
      return candidate;
    }
    dir = nodePath.dirname(dir);
  }
  throw new Error(
    `${relative} is not anywhere above ${workingDirectory()}. This contract test reads the ` +
      `server's source for its assertions; without it it asserts NOTHING and must fail ` +
      `loudly rather than pass over four unchecked routes.`,
  );
}

const API_SOURCE = nodeFs.readFileSync(repoFile(COUNTERS_API), "utf8");

/** One endpoint function's source, from its `def` to the next one's. */
function endpointSource(fn: string): string {
  const marker = `def ${fn}(`;
  const start = API_SOURCE.indexOf(marker);
  if (start < 0) {
    throw new Error(
      `${COUNTERS_API} no longer defines ${fn}(). Either the route moved or this test is ` +
        `reading the wrong file — both are RED, because an empty key set passes every ` +
        `assertion below.`,
    );
  }
  const rest = API_SOURCE.slice(start + marker.length);
  const next = rest.indexOf("\ndef ");
  return next < 0 ? rest : rest.slice(0, next);
}

interface Contract {
  /** Every body key this endpoint reads at all. */
  read: Set<string>;
  /** The moments it REFUSES the request without (`_required_moment`). */
  required: Set<string>;
}

function contractOf(fn: string): Contract {
  const source = endpointSource(fn);
  const read = new Set<string>();
  const required = new Set<string>();
  for (const hit of source.matchAll(/payload\.get\(\s*"([a-z_]+)"/g)) {
    read.add(hit[1]);
  }
  // `\s` spans the newline: the call is written across three lines.
  for (const hit of source.matchAll(/_required_moment\(\s*payload,\s*"([a-z_]+)"/g)) {
    read.add(hit[1]);
    required.add(hit[1]);
  }
  return { read, required };
}

const ROUTES = {
  start: { fn: "_counters_open", path: "/counters" },
  close: { fn: "counter_close", path: "/counters/CTR-260921-DW/close" },
  forceClose: { fn: "counter_force_close", path: "/counters/CTR-260921-DW/force-close" },
  declare: { fn: "counter_declare", path: "/counters/CTR-260921-DW/declare" },
} as const;

// ── the client end, recorded off the real screens ──────────────────────────
interface Recorded {
  path: string;
  body: Record<string, unknown>;
}

function recordingClient(options: { get?: unknown; reply: unknown }): {
  client: ApiClient;
  posts: Recorded[];
} {
  const posts: Recorded[] = [];
  const client = {
    get: async () => ({ data: options.get ?? null, status: 200, headers: new Headers() }),
    post: async (path: string, body?: unknown) => {
      posts.push({ path, body: (body ?? {}) as Record<string, unknown> });
      return { data: options.reply, status: 200, headers: new Headers() };
    },
  } as unknown as ApiClient;
  return { client, posts };
}

/** UTC+14 — far enough from UTC that a tenant wall clock can never coincide
 *  with the browser's by accident, which is what makes the zone assertions
 *  below able to fail. */
const TENANT_ZONE = "Pacific/Kiritimati";

const CENTRES = {
  centres: [
    {
      slug: "main-counter",
      name: "Main counter",
      address: "101 Main St",
      phone: null,
      directions_note: null,
      allowed_actions: [],
      payment_methods_accepted: [],
      is_shown_to_customers: true,
      position: 1,
      hours: [],
      today: { open: true, opens_at: null, closes_at: null, note: null },
      last_changed_on: null,
    },
  ],
  all_actions: [],
  all_payment_methods: [],
};

/** `CTR-260921-DW`, with ONE countable method so a count is one field. */
function counter(over: Partial<CounterDetail> = {}): CounterDetail {
  return {
    code: "CTR-260921-DW",
    owner_name: "D. Whitfield",
    service_centre_name: "Main counter",
    opened_at: "2026-09-21T08:55:00Z",
    closed_at: null,
    close_kind: null,
    declared_at: null,
    declared_by_name: null,
    payment_count: 4,
    taken_total: "510.0000",
    counted_total: null,
    difference: null,
    currency: "USD",
    opening_float: "100.0000",
    note: null,
    closed_by_name: null,
    methods: [
      {
        method_id: "m-cash",
        method_name: "Cash",
        method_code: "cash",
        system_total: "510.0000",
        countable: true,
        payment_count: 4,
        counted_total: null,
      },
    ],
    ...over,
  };
}

function mount(node: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>{node}</ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function type(container: HTMLElement, id: string, value: string): void {
  const field = container.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`);
  if (field === null) {
    throw new Error(`the form draws no field #${id}; this case cannot fill it in`);
  }
  fireEvent.change(field, { target: { value } });
}

/** 3·3a ① is a REUSED reference list, so the option is not there on first
 *  paint. Waited for BY VALUE: a count of one is also what an empty list plus
 *  a placeholder looks like. */
async function waitForCentres(container: HTMLElement): Promise<void> {
  await waitFor(() => {
    expect(container.querySelector('#service_centre option[value="main-counter"]')).not.toBeNull();
  });
}

async function submitAndRecord(
  container: HTMLElement,
  posts: Recorded[],
): Promise<Record<string, unknown>> {
  const form = container.querySelector("form");
  if (form === null) {
    throw new Error("the modal drew no form at all");
  }
  fireEvent.submit(form);
  await waitFor(() => expect(posts.length).toBe(1));
  return posts[0].body;
}

/** The two assertions, stated once so four routes cannot drift apart. */
function assertBodyMatchesContract(
  fn: string,
  body: Record<string, unknown>,
  sent: { path: string },
  expectedPath: string,
): void {
  const { read, required } = contractOf(fn);
  expect(sent.path).toBe(expectedPath);
  // (1) A key the server REFUSES the request without.
  for (const key of required) {
    expect(
      Object.prototype.hasOwnProperty.call(body, key),
      `${fn}() refuses this request without \`${key}\`, and the body carries ` +
        `{${Object.keys(body).sort().join(", ")}}`,
    ).toBe(true);
  }
  // (2) A key the server never looks at is a key that does nothing — which is
  //     how `service_centre` sat beside a `service_centre_id` the endpoint was
  //     reading and every check in this repository stayed green.
  for (const key of Object.keys(body)) {
    expect(
      read.has(key),
      `the screen posts \`${key}\`, which ${fn}() never reads. It reads ` +
        `{${[...read].sort().join(", ")}}`,
    ).toBe(true);
  }
}

afterEach(cleanup);

describe("DEF-PAY-6314 / DEF-PAY-6315 — the counter writes speak the server's own keys", () => {
  it("the contract is read from the server's own source, and it is not empty", () => {
    // Law 7's fifth shape, closed before anything depends on it: an empty key
    // set makes every assertion in this file pass over a broken route.
    expect(API_SOURCE).toContain("def _counters_open(");
    for (const { fn } of Object.values(ROUTES)) {
      const { read, required } = contractOf(fn);
      expect(read.size, `${fn}() yielded no body keys at all — the parse is broken`).toBeGreaterThan(
        0,
      );
      expect(
        required.size,
        `${fn}() yielded no REQUIRED moment — every moment on this surface is an input ` +
          `(BR-TEN-043), so zero means the parse stopped matching`,
      ).toBeGreaterThan(0);
    }
    // The four moments by name, so a rename on the server is a red line here
    // rather than a silent 400 on a money path.
    expect([...contractOf(ROUTES.start.fn).required]).toEqual(["opened_at"]);
    expect([...contractOf(ROUTES.close.fn).required]).toEqual(["closed_at"]);
    expect([...contractOf(ROUTES.forceClose.fn).required]).toEqual(["closed_at"]);
    expect([...contractOf(ROUTES.declare.fn).required]).toEqual(["declared_at"]);
  });

  it("3·3a Start posts the centre under the key POST /counters reads, and names the moment", async () => {
    const { client, posts } = recordingClient({ get: CENTRES, reply: counter() });
    const { container } = mount(
      <StartCounterModal
        onClose={() => {}}
        onStarted={() => {}}
        writeBlockedReason={null}
        client={client}
      />,
    );
    await waitForCentres(container);
    type(container, "service_centre", "main-counter");
    type(container, "opening_float", "100.00");

    const body = await submitAndRecord(container, posts);
    assertBodyMatchesContract(ROUTES.start.fn, body, posts[0], ROUTES.start.path);
    // The VALUE is the slug and always was — `_service_centre()` resolves a
    // slug first and falls back to a uuid pk. Only the key name was wrong.
    expect(body.service_centre_id).toBe("main-counter");
    expect(body.opening_float).toBe("100.00");
  });

  it("3·3b Close names the moment the drawer was sealed", async () => {
    const till = counter();
    const { client, posts } = recordingClient({ reply: till });
    const { container } = mount(
      <CloseCounterModal
        counter={till}
        onClose={() => {}}
        onClosed={() => {}}
        writeBlockedReason={null}
        client={client}
      />,
    );
    type(container, "counter-close-m-cash", "510.00");
    type(container, "note", "Counted twice.");

    const body = await submitAndRecord(container, posts);
    assertBodyMatchesContract(ROUTES.close.fn, body, posts[0], ROUTES.close.path);
  });

  it("3·3c Force close names the moment the supervisor sealed it", async () => {
    const till = counter();
    const { client, posts } = recordingClient({ reply: till });
    const { container } = mount(
      <ForceCloseCounterModal
        counter={till}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        onClose={() => {}}
        onForceClosed={() => {}}
        writeBlockedReason={null}
        client={client}
      />,
    );
    type(container, "note", "Dana went home ill.");

    const body = await submitAndRecord(container, posts);
    assertBodyMatchesContract(ROUTES.forceClose.fn, body, posts[0], ROUTES.forceClose.path);
  });

  it("3·3d Declare names the moment the late count was made", async () => {
    const till = counter({ closed_at: "2026-09-21T17:02:00Z", close_kind: "forced" });
    const { client, posts } = recordingClient({ reply: till });
    const { container } = mount(
      <DeclareCountModal
        counter={till}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        onClose={() => {}}
        onDeclared={() => {}}
        writeBlockedReason={null}
        client={client}
      />,
    );
    type(container, "counter-declare-m-cash", "498.00");
    type(container, "note", "Counted Tuesday morning.");

    const body = await submitAndRecord(container, posts);
    assertBodyMatchesContract(ROUTES.declare.fn, body, posts[0], ROUTES.declare.path);
  });

  it("3·3a draws a DATE AND TIME picker, prefilled — PO ruling 2026-09-23", async () => {
    // Verbatim: *"show date and time pciker and deult should be as per date
    // time format set by utility and timezone - show the detault time"*.
    //
    // ⚠ **THIS CASE REPLACED ONE ASSERTING THE OPPOSITE.** Until that ruling
    // this screen was built to send `new Date().toISOString()` and draw no
    // field, on p055's *Fields* row (*"Two."*). The ruling outranks the
    // drawing, and the superseded case is recorded here rather than silently
    // deleted, so the next lane does not "restore" it.
    const { client } = recordingClient({ get: CENTRES, reply: counter() });
    const { container } = mount(
      <StartCounterModal
        onClose={() => {}}
        onStarted={() => {}}
        writeBlockedReason={null}
        timeZone={TENANT_ZONE}
        dateFormat="DD.MM.YYYY"
        client={client}
      />,
    );
    const field = container.querySelector<HTMLInputElement>("#opened_at");
    expect(field, "3·3a draws no opening-time field at all").not.toBeNull();
    // BOTH halves — a time alone would not let a clerk correct yesterday's
    // till, which is the case `counter_left_open` exists for.
    expect(field?.type).toBe("datetime-local");
    // "show the detault time" — a value sitting there, not an empty box.
    expect(field?.value).not.toBe("");
  });

  it("the default is NOW IN THE UTILITY'S ZONE, never the browser's", async () => {
    // `Pacific/Kiritimati` is UTC+14, so a tenant wall clock can never coincide
    // with a UTC one by accident. If the zone did not reach the field, the
    // hour would be UTC's and this case says so.
    const before = nowInZone(TENANT_ZONE);
    const { client } = recordingClient({ get: CENTRES, reply: counter() });
    const { container } = mount(
      <StartCounterModal
        onClose={() => {}}
        onStarted={() => {}}
        writeBlockedReason={null}
        timeZone={TENANT_ZONE}
        dateFormat="MM/DD/YYYY"
        client={client}
      />,
    );
    const after = nowInZone(TENANT_ZONE);
    const shown = container.querySelector<HTMLInputElement>("#opened_at")?.value;
    // One of the two, because a minute can turn over mid-render.
    expect([before, after]).toContain(shown);
    expect(shown).not.toBe(nowInZone("UTC"));
  });

  it("the utility's DATE FORMAT is echoed beneath the control (IS-8)", () => {
    // The native picker renders in the BROWSER's locale and ignores the tenant
    // setting entirely, so this line is the only place a utility on
    // `DD.MM.YYYY` ever sees its own format — the same reason
    // `DatePickerField` carries one (CR-043 finding 15).
    const { client } = recordingClient({ get: CENTRES, reply: counter() });
    const { container } = mount(
      <StartCounterModal
        onClose={() => {}}
        onStarted={() => {}}
        writeBlockedReason={null}
        timeZone={TENANT_ZONE}
        dateFormat="DD.MM.YYYY"
        client={client}
      />,
    );
    const echo = container.querySelector(".field-date-display")?.textContent ?? "";
    const wall = nowInZone(TENANT_ZONE); // YYYY-MM-DDTHH:mm
    const [day, month] = [wall.slice(8, 10), wall.slice(5, 7)];
    expect(echo).toContain(`${day}.${month}.${wall.slice(0, 4)}`);
  });

  it("what POSTS is the wall clock the clerk read, naive so the server anchors it", async () => {
    // ⚠ NOT offset-bearing, and that is the decision. `apps/payments/api
    // ._moment` anchors a value with no offset in the TENANT's own zone
    // (BR-TEN-081 / OQ-153). Computing an offset here would derive the
    // utility's UTC offset — DST included — a second time in the browser.
    const { client, posts } = recordingClient({ get: CENTRES, reply: counter() });
    const { container } = mount(
      <StartCounterModal
        onClose={() => {}}
        onStarted={() => {}}
        writeBlockedReason={null}
        timeZone={TENANT_ZONE}
        dateFormat="MM/DD/YYYY"
        client={client}
      />,
    );
    await waitForCentres(container);
    type(container, "service_centre", "main-counter");
    type(container, "opening_float", "100.00");
    // The clerk corrects the default, which is the whole point of the picker.
    type(container, "opened_at", "2026-09-21T08:55");

    const body = await submitAndRecord(container, posts);
    expect(body.opened_at).toBe("2026-09-21T08:55");
    expect(String(body.opened_at)).not.toMatch(/(Z|[+-]\d{2}:\d{2})$/);
  });

  it("all FOUR counter writes draw the picker, prefilled and bounded to today", async () => {
    // PO ruling 2026-09-23, verbatim: *"(a) Picker on all four, same as
    // opening"*, answering *"Dana closes the till at 17:05 but counts the cash
    // at 17:20 — which is the closing time?"*.
    //
    // ⚠ **THIS CASE REPLACED ONE ASSERTING THE OPPOSITE** — that the other
    // three stamp `toISOString()` and draw nothing — which is what
    // `DEF-PAY-6315` was fixed to before the ruling arrived. Named rather than
    // deleted, so the next lane does not restore it.
    const till = counter({ closed_at: "2026-09-21T17:02:00Z", close_kind: "forced" });
    const bounds = sameDayBounds(TENANT_ZONE);
    const screens: [string, React.ReactElement][] = [
      [
        "opened_at",
        <StartCounterModal
          onClose={() => {}}
          onStarted={() => {}}
          writeBlockedReason={null}
          timeZone={TENANT_ZONE}
          dateFormat="MM/DD/YYYY"
          client={recordingClient({ get: CENTRES, reply: till }).client}
        />,
      ],
      [
        "closed_at",
        <CloseCounterModal
          counter={till}
          onClose={() => {}}
          onClosed={() => {}}
          writeBlockedReason={null}
          timeZone={TENANT_ZONE}
          dateFormat="MM/DD/YYYY"
          client={recordingClient({ reply: till }).client}
        />,
      ],
      [
        "closed_at",
        <ForceCloseCounterModal
          counter={till}
          timeZone={TENANT_ZONE}
          dateFormat="MM/DD/YYYY"
          onClose={() => {}}
          onForceClosed={() => {}}
          writeBlockedReason={null}
          client={recordingClient({ reply: till }).client}
        />,
      ],
      [
        "declared_at",
        <DeclareCountModal
          counter={till}
          timeZone={TENANT_ZONE}
          dateFormat="MM/DD/YYYY"
          onClose={() => {}}
          onDeclared={() => {}}
          writeBlockedReason={null}
          client={recordingClient({ reply: till }).client}
        />,
      ],
    ];
    for (const [field, node] of screens) {
      const { container, unmount } = mount(node);
      const input = container.querySelector<HTMLInputElement>(`#${field}`);
      expect(input, `no #${field} picker on this screen`).not.toBeNull();
      expect(input?.type).toBe("datetime-local");
      expect(input?.value, `#${field} is not prefilled`).not.toBe("");
      // `BR-PAY-1191` — backward within today and no further.
      expect(input?.getAttribute("min")).toBe(bounds.min);
      expect(input?.getAttribute("max")).toBe(bounds.max);
      unmount();
    }
  });

  it("the three sibling writes post the wall clock too, not an instant", async () => {
    const till = counter({ closed_at: "2026-09-21T17:02:00Z", close_kind: "forced" });
    const { client, posts } = recordingClient({ reply: till });
    const { container } = mount(
      <ForceCloseCounterModal
        counter={till}
        timeZone={TENANT_ZONE}
        dateFormat="MM/DD/YYYY"
        onClose={() => {}}
        onForceClosed={() => {}}
        writeBlockedReason={null}
        client={client}
      />,
    );
    type(container, "note", "Dana went home ill.");
    type(container, "closed_at", "2026-09-21T17:05");
    const body = await submitAndRecord(container, posts);
    expect(body.closed_at).toBe("2026-09-21T17:05");
    // Naive on purpose: `_moment` anchors it in the utility's own zone, and an
    // offset computed here would be that derivation done twice (BR-TEN-081).
    expect(String(body.closed_at)).not.toMatch(/(Z|[+-]\d{2}:\d{2})$/);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-PAY-6314 · DEF-PAY-6315 · CR-136-BRC07 §3.1–§3.3 ·
//         06-backend/apps/payments/counters_api.py (the other end of the contract) ·
//         CLAUDE.md hard-won law 2 · law 7 · BR-TEN-043 · BR-TEN-081 · B14 rule 33
// generated: 2026-09-23 by LANE COUNTER-OPEN
// checklist: A✔ B=n/a(no endpoint is served here) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/counterWriteContract.def6314.dom.test.tsx · tsc --noEmit
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
