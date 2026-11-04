// @vitest-environment jsdom
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-037 (EP-INT-10) — S143, their words for our things.
//           Frames 45.1 · 81.2.
// Rules:    BR-INT-032 (two of theirs may share one of ours) · BR-INT-031
//           (unmapped is RED; R02 waits) · B14 rule 15 (an icon with a
//           tooltip, addressed by its accessible name) · rule 31 (no id is a
//           visible value) · rule 33 (a fact in six words or fewer)
// Cases:    US-INT-037 TC-1 (fourteen red rows, unmapped first; ACHCHECK and
//           ACHSAVINGS both → Bank transfer, both green) · the alert sentence
//           · R02 disabled with its reason · the unmapped-only filter and the
//           search · the refusal a save can meet
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { MappingRow, MappingsPayload } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";

import { ValueMappingPage } from "./ValueMappingPage";
import { TenantRegionalProvider } from "@/components/TenantRegional";

const KIOSK = "payments_kiosk";
const FOURTEEN = [
  "CASH",
  "CHECK",
  "CREDIT",
  "DEBIT",
  "ACHCHECK",
  "ACHSAVINGS",
  "MONEYORDER",
  "CASHIERCHECK",
  "PAYPAL",
  "VENMO",
  "ZELLE",
  "GIFTCARD",
  "CRYPTO",
  "OTHER",
];
const FIVE = [
  { value: "bank_transfer", label: "Bank transfer" },
  { value: "card", label: "Card" },
  { value: "cash", label: "Cash" },
  { value: "cheque", label: "Cheque" },
  { value: "money_order", label: "Money order" },
];

function row(word: string, over: Partial<MappingRow> = {}): MappingRow {
  return {
    entity_type: "tender",
    external_value: word,
    local_value: null,
    local_label: null,
    state: "unmapped",
    shipped: true,
    last_seen_at: null,
    stays_other: false,
    ...over,
  };
}

/** The server's own ordering: unmapped first, then their word. */
function ordered(rows: MappingRow[]): MappingRow[] {
  return [...rows].sort((a, b) =>
    a.state === b.state
      ? a.external_value.localeCompare(b.external_value)
      : a.state === "unmapped"
        ? -1
        : 1,
  );
}

function payload(rows: MappingRow[]): MappingsPayload {
  const unmapped = rows.filter((one) => one.state === "unmapped").length;
  return {
    provider: { key: KIOSK, display_name: "Payment kiosk network" },
    target_key: KIOSK,
    types: [
      {
        entity_type: "tender",
        label: "How they pay",
        summary: "",
        open: false,
        choices: FIVE,
        counts: { rows: rows.length, unmapped },
        beside_the_chart: false,
      },
    ],
    rows: ordered(rows),
    counts: { rows: rows.length, unmapped },
  };
}

const fresh = () => payload(FOURTEEN.map((word) => row(word)));

function mapped(word: string) {
  return row(word, { local_value: "bank_transfer", local_label: "Bank transfer", state: "mapped" });
}

function ok<T>(data: T): ApiResponse<T> {
  return { status: 200, data, etag: null, notModified: false };
}

function mount(data: MappingsPayload, put?: ApiClient["put"]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.integrationMappings(KIOSK), data);
  const client = {
    get: vi.fn(async () => ok(data)),
    put: put ?? vi.fn(async () => ok(data)),
  } as unknown as ApiClient;
  const view = render(
    <QueryClientProvider client={queryClient}>
      {/* DEF-SHL-3964 — this screen used to run its OWN copy of the shell's
          regional query and spell its own `?? "UTC"` beside it. It reads the
          published settings now, so the test publishes them the way the shell
          does — which is also what makes "in the tenant's zone" below a real
          claim rather than a restatement of a default. */}
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
      <MemoryRouter initialEntries={[`/brazosbend/settings/integrations/${KIOSK}/mappings`]}>
        <Routes>
          <Route
            path="/:tenant/settings/integrations/:key/mappings"
            element={<ValueMappingPage client={client} />}
          />
        </Routes>
      </MemoryRouter>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

describe("S143 · their words for our things (US-INT-037)", () => {
  // vitest runs without globals, so Testing Library's auto-cleanup never registers.
  afterEach(cleanup);

  it("TC-1: fourteen rows, every one red and unmapped, unmapped first", () => {
    const { container } = mount(fresh());
    const rows = container.querySelectorAll("[data-mapping-row]");
    expect(rows).toHaveLength(14);
    for (const one of rows) {
      expect(one.getAttribute("data-state")).toBe("unmapped");
      expect(one.className).toContain("border-danger-500");
      expect(within(one as HTMLElement).getByText("Not set · records as Other")).toBeTruthy();
    }
    expect(screen.getByRole("status").textContent).toContain("14 of 14 not mapped.");
    expect(screen.getByRole("status").textContent).toContain("Each records as Other until mapped.");
    // rule 15: the action is an icon whose accessible name is the verb
    expect(screen.getAllByRole("button", { name: "Map it" })).toHaveLength(14);
  });

  it("TC-1: ACHCHECK and ACHSAVINGS both mean Bank transfer — both green, listed after the red twelve", () => {
    const data = payload(
      FOURTEEN.map((word) =>
        word === "ACHCHECK" || word === "ACHSAVINGS" ? mapped(word) : row(word),
      ),
    );
    const { container } = mount(data);
    const rows = [...container.querySelectorAll("[data-mapping-row]")];
    expect(rows.map((one) => one.getAttribute("data-state"))).toEqual([
      ...Array(12).fill("unmapped"),
      "mapped",
      "mapped",
    ]);
    expect(rows.slice(12).map((one) => one.getAttribute("data-mapping-row"))).toEqual([
      "ACHCHECK",
      "ACHSAVINGS",
    ]);
    for (const one of rows.slice(12)) {
      expect(one.className).not.toContain("border-danger-500");
      expect(within(one as HTMLElement).getByText("Bank transfer")).toBeTruthy();
    }
    expect(screen.getByRole("status").textContent).toContain("12 of 14 not mapped.");
    expect(screen.getAllByRole("button", { name: "Change" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Map it" })).toHaveLength(12);
    // rule 31: their word and our word, and no id anywhere in the markup
    expect(container.innerHTML).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/);
    expect(container.innerHTML).not.toMatch(/\b(BR|OQ|DEF|US)-[A-Z]{3}-\d+/);
  });

  it("Map it opens one select of OUR words, and Save sends their word → our code", async () => {
    const user = userEvent.setup();
    const before = fresh();
    const after = payload(
      FOURTEEN.map((word) => (word === "ACHCHECK" ? mapped(word) : row(word))),
    );
    const put = vi.fn(async () => ok(after));
    const { container, client } = mount(before, put as unknown as ApiClient["put"]);
    const achcheck = container.querySelector('[data-mapping-row="ACHCHECK"]') as HTMLElement;
    await user.click(within(achcheck).getByRole("button", { name: "Map it" }));
    const select = within(achcheck).getByRole("combobox");
    expect([...select.querySelectorAll("option")].map((one) => one.textContent)).toEqual([
      "Leave unmapped",
      "Bank transfer",
      "Card",
      "Cash",
      "Cheque",
      "Money order",
    ]);
    await user.selectOptions(select, "bank_transfer");
    await user.click(within(achcheck).getByRole("button", { name: "Save" }));
    expect(client.put).toHaveBeenCalledWith(`/integrations/${KIOSK}/mappings`, {
      rows: [{ entity_type: "tender", external_value: "ACHCHECK", local_value: "bank_transfer" }],
    });
    // the page re-draws from the server's answer, not from a guess
    const redrawn = await screen.findByText("13 of 14 not mapped.");
    expect(redrawn).toBeTruthy();
    expect(
      container.querySelector('[data-mapping-row="ACHCHECK"]')?.getAttribute("data-state"),
    ).toBe("mapped");
  });

  it("a refused save shows the refusal on the row and keeps the editor open", async () => {
    const user = userEvent.setup();
    const put = vi.fn(async () => {
      // The envelope exactly as the server answers a value that is not ours.
      throw new ApiError(422, {
        code: "VAL-005",
        message_key: "integrations.refusal.mapping_not_ours",
        params: { value: "Bitcoin" },
        field_errors: [],
        br_ref: null,
        trace_id: null,
      });
    });
    const { container } = mount(fresh(), put as unknown as ApiClient["put"]);
    const crypto = container.querySelector('[data-mapping-row="CRYPTO"]') as HTMLElement;
    await user.click(within(crypto).getByRole("button", { name: "Map it" }));
    await user.selectOptions(within(crypto).getByRole("combobox"), "cash");
    await user.click(within(crypto).getByRole("button", { name: "Save" }));
    const strip = await within(crypto).findByText(/Bitcoin is not one of ours/);
    expect(strip).toBeTruthy();
    expect(within(crypto).getByRole("combobox")).toBeTruthy();
  });

  it("R02's action is disabled and the reason is the RULING, not a pending decision", () => {
    const data: MappingsPayload = {
      ...payload([]),
      provider: { key: "bank_lockbox_file", display_name: "Bank & lockbox file" },
      types: [
        {
          entity_type: "reversal_reason",
          label: "Bounced payments",
          summary: "",
          open: false,
          choices: [{ value: "nsf", label: "Not enough money" }],
          counts: { rows: 2, unmapped: 1 },
          beside_the_chart: false,
        },
      ],
      rows: [
        row("R02", { entity_type: "reversal_reason", stays_other: true }),
        row("R01", {
          entity_type: "reversal_reason",
          local_value: "nsf",
          local_label: "Not enough money",
          state: "mapped",
        }),
      ],
      counts: { rows: 2, unmapped: 1 },
    };
    mount(data);
    // `OQ-INT-1487` closed 2026-09-04 to option (b): R02 records as Other with
    // the raw code kept. The control stays disabled and the SENTENCE CHANGES —
    // a screen that still said "Waiting for a decision" would be claiming a
    // decision is pending on one that was made (hard-won law 1).
    const staysOther = screen.getByRole("button", { name: "Map it" });
    expect(staysOther.hasAttribute("disabled")).toBe(true);
    expect(staysOther.getAttribute("title")).toBe("Always records as Other");
    expect(screen.getByRole("button", { name: "Change" }).hasAttribute("disabled")).toBe(false);
    expect(screen.getByText("Not enough money")).toBeTruthy();
  });

  it("unmapped only hides the mapped rows, and the search narrows by their word or ours", async () => {
    const user = userEvent.setup();
    const { container } = mount(
      payload(FOURTEEN.map((word) => (word === "ACHCHECK" ? mapped(word) : row(word)))),
    );
    await user.click(screen.getByRole("checkbox", { name: "Unmapped only" }));
    expect(container.querySelectorAll("[data-mapping-row]")).toHaveLength(13);
    await user.click(screen.getByRole("checkbox", { name: "Unmapped only" }));
    await user.type(screen.getByRole("searchbox"), "bank");
    expect(
      [...container.querySelectorAll("[data-mapping-row]")].map((one) =>
        one.getAttribute("data-mapping-row"),
      ),
    ).toEqual(["ACHCHECK"]);
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "ach");
    expect(container.querySelectorAll("[data-mapping-row]")).toHaveLength(2);
  });

  it("an arrived word shows when it was last seen, in the tenant's zone", () => {
    const { container } = mount(
      payload([
        ...FOURTEEN.map((word) => row(word)),
        row("CASHAPP", { shipped: false, last_seen_at: "2026-09-03T11:15:00+00:00" }),
      ]),
    );
    const cashapp = container.querySelector('[data-mapping-row="CASHAPP"]') as HTMLElement;
    expect(within(cashapp).getByText(/Last seen/).textContent).toContain("09/03/2026");
    expect(within(cashapp).getByText(/Last seen/).textContent).toContain("06:15");
  });
});
