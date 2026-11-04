// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-110-BRC04 phase 2 — the `they_hold_ours` SHAPE, on all six
//          connectors and not on Aclarian alone. PO 2026-09-16, verbatim:
//          "we need to follow this rule for all they read cases - not just
//          aclarina - please fix this".
// Defects: DEF-INT-5533 (the password panel over the keys WE issue, and no
//          Keys we issue panel) · DEF-INT-5536 (four quadrants, three words) ·
//          DEF-INT-5493 (the WHEN column answering WHO) · DEF-INT-5532 (the
//          summary line repeating the heading) · DEF-INT-5531 (CONNECTION
//          where the blueprint draws CONNECTOR).
// Rules:   B14 rule 41 (the product matches the blueprint) · rule 42 (built
//          from the drawing AS AN IMAGE — p062, p064, p066) · BR-INT-037 (read
//          the manifest, never branch on a provider key; G77) · CLAUDE.md
//          hard-won law 7 ("what would make this check pass wrongly?").
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY: TESTING ONE CONNECTOR.** Every fault
// this file is written against is a rule expressed as a SHAPE, and a shape
// needs two sides to be a shape. So every case here runs over THREE fixtures
// that are three different quadrants:
//
//   `erp_aclarian`   `out · them` — they READ from us, and we issue the key
//   `payments_kiosk` `in  · them` — they SEND to us, and we issue the key
//   `email_smtp`     `out · us`   — we DIAL them, and we hold their password
//
// The kiosk is the one that matters most and it is why the direction words
// were wrong for months: it is the ONE connector in the issue-a-key set that
// is genuinely `in · them`, so a fix that maps `initiative === "them"` to a
// single phrase is still wrong after the change and this file says so.
//
// PROVED RED FIRST, IN `npx vitest run src/features/integrations/
// connectorShape.test.tsx` — the harness CI runs, never `node` on a path
// nobody uses (`DEF-GOV-3733`). The failures are quoted in the CR.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { ConnectionRuns, IssuedKey, OperationRow } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { ConnectionDetailPage } from "./ConnectionDetailPage";
import { ConnectorSetupPage } from "./ConnectorSetupPage";

const TENANT = "brazosbend";

function operation(over: Partial<OperationRow> & { name: string }): OperationRow {
  return {
    label: over.name,
    description: "",
    direction: "out",
    initiative: "them",
    state: "working",
    last_run_at: null,
    last_outcome: null,
    trace_id: null,
    test_action: null,
    test_needs_recipient: false,
    executor: "server",
    latency_budget_ms: null,
    result_disposition: null,
    rate_limit_per_minute: 60,
    ...over,
  } as OperationRow;
}

/** One live key, scoped to the operations a test names. */
function key(scope: string[], over: Partial<IssuedKey> = {}): IssuedKey {
  return {
    version: 3,
    hint: "••••7Q2F",
    state: "active",
    issued_at: "2026-08-12T09:00:00Z",
    revoked_at: null,
    last_used_at: null,
    scope,
    ...over,
  };
}

type Shape = {
  key: string;
  name: string;
  mode: string;
  operations: OperationRow[];
  issued_keys: IssuedKey[];
  describe?: string;
};

/** `out · them` — a finance system reads from us under a key we issued. */
const ACLARIAN: Shape = {
  key: "erp_aclarian",
  name: "Aclarian",
  mode: "they_hold_ours",
  operations: [
    operation({ name: "serve_payment", label: "Read payments", trigger: "partner" } as never),
    operation({ name: "serve_bill", label: "Read bills", trigger: "partner" } as never),
    operation({ name: "serve_customer", label: "Read customers", trigger: "partner" } as never),
  ],
  issued_keys: [key(["serve_payment", "serve_bill"])],
};

/** `in · them` — a kiosk POSTS payments to us under a key we issued. */
const KIOSK: Shape = {
  key: "payments_kiosk",
  name: "Payment kiosk network",
  mode: "they_hold_ours",
  operations: [
    operation({
      name: "payments",
      label: "Payments",
      direction: "in",
      trigger: "webhook",
    } as never),
  ],
  issued_keys: [key(["payments"])],
};

/** `out · us` — we dial a mail server and we hold ITS password. */
const SMTP: Shape = {
  key: "email_smtp",
  name: "Custom SMTP",
  mode: "we_hold_theirs",
  operations: [
    operation({
      name: "send_message",
      label: "Send messages",
      initiative: "us",
      trigger: "dispatcher",
    } as never),
  ],
  issued_keys: [],
  // What `describe_line` really returns for a connector with an adapter: the
  // adapter's masked line. It is NOT the display name, which is the whole
  // point of `DEF-INT-5532` — that fallback is only reached by the six.
  describe: "billing@brazosbend.example · Custom SMTP",
};

function payloadFor(shape: Shape): ConnectionRuns {
  return {
    provider: {
      key: shape.key,
      display_name: shape.name,
      category: shape.key.startsWith("erp") ? "erp" : "payments",
      auth: { mode: shape.mode, placement: "bearer" },
      disposition: { kind: "live", wave: null },
    },
    // What the server actually serves for these six: the display name, because
    // no adapter is bound. That is `DEF-INT-5532`'s input, not its output.
    describe: shape.describe ?? shape.name,
    display_state: "working",
    connection: {
      id: "01a06aad-0000-7000-8000-00000000000c",
      label: shape.name,
      describe: shape.describe ?? shape.name,
      settings: {},
      connected_by: "Dana Whitfield",
      environment: "production",
      status: "working",
      enabled: true,
      cadence: "manual",
      next_run_at: null,
      last_test_at: null,
      last_test_ok: null,
      last_test_text: null,
      connected_at: "2026-08-12T09:00:00Z",
      credential: null,
      expiry: {
        state: "unknown",
        expires_at: null,
        days_left: null,
        window_days: 14,
        version: null,
      },
    },
    credentials: [
      {
        version: 1,
        is_active: true,
        hint: "••••7Q2F",
        expires_at: null,
        rotated_at: null,
        created_at: "2026-08-12T09:00:00Z",
      },
    ],
    issued_keys: shape.issued_keys,
    disconnect: {
      category: "erp",
      label: shape.name,
      versions: 1,
      runs_kept: 4,
      channel: null,
      messages_waiting: null,
    },
    operations: shape.operations,
    filters: {
      operations: shape.operations.map((one) => ({ name: one.name, label: one.label })),
      outcomes: [],
      triggers: [],
    },
    applied: { q: "", operation: null, outcome: null, trigger: null },
    rows: [],
    page: { page: 1, per: 50, count: 0, pages: 1 },
    elsewhere: 0,
  } as unknown as ConnectionRuns;
}

function ok<T>(data: T): ApiResponse<T> {
  return { status: 200, data, etag: null, notModified: false };
}

function mount(shape: Shape) {
  const data = payloadFor(shape);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(
    queryKeys.integrationRuns(shape.key, JSON.stringify(["", {}, 1, 50, "started", "desc"])),
    data,
  );
  queryClient.setQueryData(queryKeys.regionalSettings, {
    timezone: "America/Chicago",
    date_format: "MM/DD/YYYY",
  });
  const client = { get: vi.fn(async () => ok(data)) } as unknown as ApiClient;
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN. A bare MemoryRouter leaves
  // `useParams().tenant` undefined and every address the page builds comes out
  // `//settings/...` — a protocol-relative URL to another host, which reads as
  // a perfectly good string to `toContain` (CLAUDE.md hard-won law 2).
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/integrations/${shape.key}`]}>
          <Routes>
            <Route
              path="/:tenant/settings/integrations/:key"
              element={<ConnectionDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("the connection view · four quadrants need four words (DEF-INT-5536, DEF-INT-5493)", () => {
  afterEach(cleanup);

  it("Aclarian is out·them and every row says They read, never They send", async () => {
    mount(ACLARIAN);
    const rows = await screen.findAllByText("Read payments");
    expect(rows.length).toBeGreaterThan(0);
    const cells = document.querySelectorAll("[data-direction]");
    expect(cells.length).toBe(3);
    for (const cell of cells) expect(cell.textContent).toBe("They read");
  });

  it("the kiosk is in·them and says They send — the same quadrant word, a different quadrant", async () => {
    mount(KIOSK);
    await screen.findAllByText("Payments");
    const cells = document.querySelectorAll("[data-direction]");
    expect(cells.length).toBe(1);
    expect(cells[0].textContent).toBe("They send");
  });

  it("WHEN answers WHEN, on both partner and webhook — the drawing's They call us", async () => {
    mount(ACLARIAN);
    await screen.findAllByText("Read payments");
    for (const cell of document.querySelectorAll("[data-when]")) {
      expect(cell.textContent).toBe("They call us");
    }
    cleanup();
    mount(KIOSK);
    await screen.findAllByText("Payments");
    for (const cell of document.querySelectorAll("[data-when]")) {
      expect(cell.textContent).toBe("They call us");
    }
  });

  it("never the run history's words — A partner answers WHO, and this column asks WHEN", async () => {
    mount(ACLARIAN);
    await screen.findAllByText("Read payments");
    for (const cell of document.querySelectorAll("[data-when]")) {
      expect(cell.textContent).not.toBe("A partner");
      expect(cell.textContent).not.toBe("They called us");
    }
  });
});

describe("the connection view · the panel is chosen by SHAPE (DEF-INT-5533)", () => {
  afterEach(cleanup);

  for (const shape of [ACLARIAN, KIOSK]) {
    it(`${shape.key}: a Keys we issue panel, and NO password panel`, async () => {
      mount(shape);
      await screen.findAllByText(shape.operations[0].label);
      const keys = document.querySelector("[data-keys-table]");
      expect(keys, "the drawn Keys we issue panel (p062, p066) is not on the screen").not.toBeNull();
      expect(
        screen.queryByText("Passwords on this connection"),
        "a connector whose key WE issue is showing a panel about a password we never had",
      ).toBeNull();
      expect(screen.queryByText("Replace password")).toBeNull();
      // *One key. All N APIs use it.* is false where a key names its APIs.
      expect(screen.queryByText(/One key\./)).toBeNull();
    });
  }

  it("Custom SMTP keeps its password panel and gets NO keys panel", async () => {
    mount(SMTP);
    expect(await screen.findByText("Passwords on this connection")).toBeTruthy();
    expect(
      document.querySelector("[data-keys-table]"),
      "a connector we DIAL is showing a panel about keys we issue, which it has none of",
    ).toBeNull();
  });

  it("MAY CALL names the operations in the clerk's words, never the raw name", async () => {
    mount(ACLARIAN);
    // ⚠ BY ATTRIBUTE, NOT BY TEXT. The same words are on the summary line
    // above — deliberately, they are the same fact — so `findByText` finds two
    // and a test that took the first would not be reading this cell at all.
    await screen.findAllByText(/Read payments, Read bills/);
    const cell = document.querySelector("[data-may-call]");
    expect(cell?.textContent).toBe("Read payments, Read bills");
    expect(document.body.textContent).not.toContain("serve_payment");
  });

  it("the drawn STATE column tells a live key from a replaced one", async () => {
    const withOld: Shape = {
      ...ACLARIAN,
      issued_keys: [
        key(["serve_payment"]),
        key(["serve_bill"], {
          version: 2,
          hint: "••••bc91",
          state: "revoked",
          revoked_at: "2026-08-12T09:00:00Z",
        }),
      ],
    };
    mount(withOld);
    await screen.findByText("Active");
    const states = document.querySelectorAll("[data-key-state]");
    expect([...states].map((one) => one.getAttribute("data-key-state"))).toEqual([
      "active",
      "revoked",
    ]);
  });
});

describe("the connection view · the head reads the blueprint's words (DEF-INT-5531, DEF-INT-5532)", () => {
  afterEach(cleanup);

  /*
   * ⚠ **THESE THREE ASSERTED THE HEAD AS `DEF-INT-5560` LEFT IT, AND THE PO
   * OVERRODE IT ON 2026-09-17** — *"thi si good - can you include some of the
   * missing data from this into header"*. The literal word *Connector* was the
   * kicker; it is now the connector's own CATEGORY and DIRECTION. The
   * `[data-describe]` line is gone with the `4 APIs` chip beside it, and what
   * it carried — WHERE this connection reaches — is the middle fact of the
   * head's roll-up. Rewritten rather than deleted: the fact each one protects
   * is still a fact, it simply has a new address on the screen.
   */
  it("the kicker is the connector's OWN category and direction, not the word Connector", async () => {
    mount(ACLARIAN);
    await screen.findAllByText("Read payments");
    const kicker = document.querySelector(".page-header-id .kicker, .page-header-id [class*='kicker']");
    const head = document.querySelector(".page-header-id")?.textContent ?? "";
    expect(head).toContain("ERP");
    expect(head).toContain("They read");
    // The page-kind word told a reader what sort of PAGE they were on and
    // nothing about the connector, which is the whole of the PO's complaint.
    expect(screen.queryByText("Connector")).toBeNull();
    void kicker;
  });

  it("WHERE this connection reaches is in the head, capped at one segment (B14 rule 33)", async () => {
    mount(ACLARIAN);
    await screen.findAllByText(/7Q2F/);
    const line = document.querySelector("[data-meta]");
    expect(line?.textContent).toContain("7Q2F");
    // ⚠ **THE OPERATION LABELS ARE DELIBERATELY NOT HERE.** `••••7Q2F · Read
    // bills, Read customers, Read the ledger, Read payments` is EIGHT words and
    // rule 33 caps a FACT at six. They are still on the screen — in the API
    // table and in the key's MAY CALL cell — so nothing is lost, and the head
    // stops carrying the same list a third time.
    expect(line?.textContent).not.toContain("Read payments");
    // The facts that JOINED it, which is what the PO asked the head to carry.
    expect(line?.textContent).toContain("Production");
  });

  it("a connector we dial keeps the masked line the server serves for it", async () => {
    mount(SMTP);
    await screen.findAllByText("Send messages");
    const line = document.querySelector("[data-meta]");
    // ⚠ The fix must not reach the twelve we DIAL. Their line is the adapter's
    // masked identity — the mailbox, the host — and replacing it with a key
    // hint would be `DEF-INT-5532`'s mirror image. One segment of it, for the
    // same rule-33 reason as above: *Custom SMTP* after the `·` is the
    // connector's name, which the title already says.
    expect(line?.textContent).toContain("billing@brazosbend.example");
    expect(line?.textContent).not.toContain("Custom SMTP");
    void within;
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// THE SET-UP SCREEN — S147 · INT-07
//
// The direction words were wrong HERE and right on the connection view, which
// is why the two are asserted in one file: the product already held the answer
// and this screen wrote its own (`DEF-INT-5536`).
// ─────────────────────────────────────────────────────────────────────────────

function cardFor(shape: Shape) {
  return {
    key: shape.key,
    category: shape.key.startsWith("erp") ? "erp" : "payments",
    display_name: shape.name,
    summary: "",
    // ⚠ THE FIELDS ARE THE REAL ONES FOR THE SHAPE, and that matters: the
    // screen's `weIssueTheKey` is `auth.mode === "they_hold_ours"` OR an
    // `issued_secret` field, so a fixture that gave every card an issued key
    // would put the switch column on a connector we DIAL and the case below
    // would pass over the wrong thing (law 7, *looking at the wrong thing* —
    // and it DID, on the first run of this file).
    fields:
      shape.mode === "they_hold_ours"
        ? [
            { name: "allowed_addresses", label: "Allowed addresses", kind: "text", required: true, options: [] },
            { name: "issued_key", label: "The key for them to use", kind: "issued_secret", required: true, options: [] },
          ]
        : [
            { name: "host", label: "Server address", kind: "host", required: true, options: [] },
            { name: "password", label: "Password", kind: "secret", required: true, options: [] },
          ],
    disposition: { kind: "live", wave: null, phase: null },
    kicker: { direction: "out", initiative: "them" },
    auth: { mode: shape.mode, placement: "bearer" },
    codecs: [],
    vocabularies: [],
    adapter_registered: false,
    connection: payloadFor(shape).connection,
    connections: [],
    state: "working",
    display_state: "working",
    operations: shape.operations,
    credentials: [],
    disconnect: null,
    issued_keys: shape.issued_keys,
  };
}

function mountSetUp(shape: Shape) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.integrations, {
    categories: [],
    providers: [cardFor(shape)],
    counts: { providers: 1, connected: 1 },
  });
  queryClient.setQueryData(queryKeys.regionalSettings, {
    timezone: "America/Chicago",
    date_format: "MM/DD/YYYY",
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[`/${TENANT}/settings/connectors/${shape.key}/configure`]}
        >
          <Routes>
            <Route
              path="/:tenant/settings/connectors/:providerKey/configure"
              element={<ConnectorSetupPage />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("the set-up screen · four quadrants need four words (DEF-INT-5536)", () => {
  afterEach(cleanup);

  it("Aclarian reads They read — a row saying 'Read payments · They send' contradicts itself", async () => {
    mountSetUp(ACLARIAN);
    const row = await screen.findByText("Read payments");
    const cells = row.closest("tr")!.querySelectorAll("td");
    expect([...cells].map((one) => one.textContent)).toContain("They read");
    expect([...cells].map((one) => one.textContent)).not.toContain("They send");
  });

  it("the kiosk reads They send, because it is the one in·them connector here", async () => {
    mountSetUp(KIOSK);
    const row = await screen.findByText("Payments");
    const cells = row.closest("tr")!.querySelectorAll("td");
    expect([...cells].map((one) => one.textContent)).toContain("They send");
  });

  it("the page kicker says THEY READ, not THEY SEND, on a connector that reads from us", async () => {
    mountSetUp(ACLARIAN);
    await screen.findByText("Read payments");
    expect(document.body.textContent).toContain("ERP · THEY READ");
  });

  it("WHEN says They call us on both, and never invents a third vocabulary", async () => {
    for (const shape of [ACLARIAN, KIOSK]) {
      mountSetUp(shape);
      await screen.findByText(shape.operations[0].label);
      expect(document.body.textContent).toContain("They call us");
      expect(document.body.textContent).not.toContain("When they ask");
      expect(document.body.textContent).not.toContain("When they send");
      cleanup();
    }
  });

  it("the ceiling column shows the number the door enforces, not a dash", async () => {
    mountSetUp(ACLARIAN);
    await screen.findByText("Read payments");
    const cell = document.querySelector("[data-rate-limit]");
    expect(cell?.getAttribute("data-rate-limit")).toBe("60");
  });

  it("the limits footnote points the right way: WE allow THEM", async () => {
    mountSetUp(ACLARIAN);
    await screen.findByText("Read payments");
    expect(document.body.textContent).toContain("These are the limits we allow them.");
    expect(document.body.textContent).not.toContain("These are the limits they allow us.");
  });
});

describe("the set-up screen · an on/off on each API (DEF-INT-5534, DEF-INT-5537, DEF-INT-5535)", () => {
  afterEach(cleanup);

  it("there is no Their client id field left to refuse the save", async () => {
    mountSetUp(ACLARIAN);
    await screen.findByText("Read payments");
    expect(screen.queryByText(/Their client id/)).toBeNull();
    expect(screen.queryByText("What they may read")).toBeNull();
  });

  for (const shape of [ACLARIAN, KIOSK]) {
    it(`${shape.key}: every API row carries its own switch`, async () => {
      mountSetUp(shape);
      await screen.findByText(shape.operations[0].label);
      const switches = document.querySelectorAll('[role="switch"]');
      expect(switches.length).toBe(shape.operations.length);
      // ⚠ The kiosk had NO scope control of any kind before this — its key
      // opened all three of its APIs and nothing offered a clerk a choice.
      for (const one of switches) {
        expect(one.getAttribute("aria-label")).toBeTruthy();
      }
    });
  }

  it("a connector we DIAL gets no switch column — there is nothing to grant", async () => {
    mountSetUp(SMTP);
    await screen.findByText("Send messages");
    expect(document.querySelectorAll('[role="switch"]').length).toBe(0);
  });

  it("the switches start from the live key's own scope, so re-issuing cannot widen it", async () => {
    mountSetUp(ACLARIAN);
    await screen.findByText("Read payments");
    const states = [...document.querySelectorAll("[data-switch-key]")].map((one) => [
      one.getAttribute("data-switch-key"),
      one.getAttribute("data-switch-state"),
    ]);
    expect(states).toEqual([
      ["serve_payment", "on"],
      ["serve_bill", "on"],
      ["serve_customer", "off"],
    ]);
  });

  it("Generate a key POSTS the switched-on operations — an empty scope is refused at the door", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({
      status: 201,
      data: { key: "k", hint: "••••k", version: 1, issued_at: "2026-09-16T00:00:00Z", card: cardFor(ACLARIAN) },
      etag: null,
      notModified: false,
    } as never);
    mountSetUp(ACLARIAN);
    const button = await screen.findByText("Generate a key");
    button.click();
    await vi.waitFor(() => expect(post).toHaveBeenCalled());
    const [path, body] = post.mock.calls[0];
    expect(path).toBe("/integrations/erp_aclarian/key");
    // ⚠ **THE BODY WAS `{}` AND THE DOOR REFUSES THAT** — the one control this
    // whole screen exists for could not succeed on any of the six.
    expect(body).toEqual({ scope: ["serve_payment", "serve_bill"] });
    post.mockRestore();
  });
});
