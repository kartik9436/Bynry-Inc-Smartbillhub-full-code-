// @vitest-environment jsdom
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-040 (EP-INT-11) — S144, the keys we issue. Frames 50.1
//           (the key in mono + Copy + *the only time it is shown*) and 46.1
//           (the card afterwards, masked).
// Rules:    BR-INT-053 (shown once; revocation refuses the very next call) ·
//           BR-INT-003 (never rendered back — the hint only) · B14 rule 6
//           (danger tier on Revoke) · rule 31 (no id is a visible value)
// Cases:    TC-1 (shown once, then the hint only) · TC-3's screen half (the
//           revoke confirm says what happens next) · TC-4 (both keys listed,
//           the old one revoked) · *never used* is a fact and not a dash ·
//           the screen is tagged S144 and not S142
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ THE MOUNT IS UNDER THE REAL PATH PATTERN, and that is not a style
// preference. A component mounted bare inside a `MemoryRouter` with no
// `/:tenant/settings/integrations/:key/access` route gets `undefined` from
// `useParams()`, every address it builds comes out `//settings/…` — a
// protocol-relative URL to another host — and `toContain` reads it as a
// perfectly good string. That is how the customer portal's front page shipped
// with two working doors out of eight (hard-won law 2).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { IntegrationsGrid, IssuedKey, ProviderCard } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";
import { resolveScreen } from "@/routing/screenIds";

import { MachineKeysPage } from "./MachineKeysPage";

const PARTNER = "gl_partner";
const ROUTE = `/brazosbend/settings/integrations/${PARTNER}/access`;
const PATTERN = "/:tenant/settings/integrations/:key/access";

/** The key the walkthrough's fixture mints. Its SHAPE is the assertion. */
const MINTED = "sbh_live_9f2c4a71b8e35d0c67429f2c4a71b8e3";

function issued(over: Partial<IssuedKey> = {}): IssuedKey {
  return {
    version: 1,
    hint: "••••b8e3",
    state: "active",
    issued_at: "2026-09-03T14:02:00Z",
    revoked_at: null,
    last_used_at: null,
    ...over,
  };
}

function card(keys: IssuedKey[]): ProviderCard {
  // Cast rather than annotated: a sibling wave may widen `ProviderCard`, and a
  // literal must still compile (the shape IntegrationsTab.test.tsx takes).
  return {
    key: PARTNER,
    category: "accounting",
    display_name: "Third-party GL",
    summary: "Your finance system collects payments and bills from here.",
    fields: [
      { name: "client_id", label: "Their client id", kind: "text", required: true, options: [] },
      {
        name: "issued_key",
        label: "The key for them to use",
        kind: "issued_secret",
        required: true,
        options: [],
      },
    ],
    disposition: { kind: "live", wave: null, phase: null },
    kicker: { direction: "out", initiative: "them" },
    auth: { mode: "they_hold_ours", placement: "bearer" },
    codecs: [],
    adapter_registered: false,
    connection: {
      environment: "production",
      status: "untested",
      credential: keys.length === 0 ? null : { version: keys[0].version, hint: keys[0].hint },
    },
    connections: [],
    vocabularies: [],
    state: "untested",
    display_state: "reading_from_us",
    operations: [],
    credentials: [],
    disconnect: null,
    issued_keys: keys,
  } as unknown as ProviderCard;
}

function grid(keys: IssuedKey[]): IntegrationsGrid {
  return { categories: [{ key: "accounting" }], providers: [card(keys)] } as IntegrationsGrid;
}

function ok<T>(data: T): ApiResponse<T> {
  return { status: 200, data, etag: null, notModified: false };
}

function mount(keys: IssuedKey[], overrides: Partial<ApiClient> = {}) {
  const payload = grid(keys);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.integrations, payload);
  const client = {
    get: vi.fn(async () => ok(payload)),
    post: vi.fn(async () => ok({ key: MINTED, hint: "••••b8e3", version: 1, issued_at: "", card: card(keys) })),
    del: vi.fn(async () => ok(card([]))),
    ...overrides,
  } as unknown as ApiClient;
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <MemoryRouter initialEntries={[ROUTE]}>
            <Routes>
              <Route path={PATTERN} element={<MachineKeysPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

afterEach(cleanup);

describe("S144 · the keys we issue (US-INT-040)", () => {
  it("TC-1 · the key is shown once, with Copy, and the table shows only the hint", async () => {
    const { container, client } = mount([]);
    await screen.findByText("No key issued yet");

    // Nothing on the screen carries a key before one is minted.
    expect(container.querySelector("[data-issued-key-panel]")).toBeNull();

    await userEvent.click(screen.getAllByRole("button", { name: "Issue key" })[0]);

    const panel = await waitFor(() => {
      const found = container.querySelector("[data-issued-key-value]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(panel.textContent).toBe(MINTED);
    expect(screen.getByText("Copy it now. This is the only time it is shown.")).toBeTruthy();
    expect((client.post as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      `/integrations/${PARTNER}/key`,
    );

    // …and Done drops it. A second render of the same screen has nothing to
    // show, because nothing anywhere is holding the key (US-INT-040 TC-1).
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(container.querySelector("[data-issued-key-value]")).toBeNull();
  });

  it("shows the hint and NEVER USED for a key nobody has presented yet", async () => {
    const { container } = mount([issued()]);
    await screen.findByText("••••b8e3");
    expect(container.querySelector("[data-never-used]")).not.toBeNull();
    // B14 rule 31 — the version rides as a suffix; no row id is anywhere.
    expect(screen.getByText("v1")).toBeTruthy();
    // …and the key itself is not on the screen at any point.
    expect(container.textContent).not.toContain("sbh_live_");
  });

  it("TC-4 · a replaced key is listed beside the new one, marked revoked", async () => {
    const { container } = mount([
      issued({ version: 2, hint: "••••7Q2F", last_used_at: "2026-09-04T06:14:00Z" }),
      issued({ version: 1, state: "revoked", revoked_at: "2026-09-04T09:00:00Z" }),
    ]);
    await screen.findByText("••••7Q2F");

    // ⚠ SCOPED TO THE ROWS, NOT THE WHOLE SCREEN. `getByText("Active")` matches
    // twice — the row AND the state filter's own chip — and a test that reads
    // the filter bar while claiming to read the table is a test named after an
    // assertion it does not make (law 7's fourth shape).
    const states = Array.from(container.querySelectorAll("[data-key-state]")).map(
      (one) => one.getAttribute("data-key-state"),
    );
    expect(states).toEqual(["active", "revoked"]);
    // …and the newest is first, which is what `issued desc` means (B9).
    const hints = Array.from(container.querySelectorAll("[data-key-row]")).map((one) =>
      one.getAttribute("data-key-row"),
    );
    expect(hints).toEqual(["••••7Q2F", "••••b8e3"]);
  });

  it("TC-3's screen half · the revoke confirm says what happens next, in the danger tier", async () => {
    const { container } = mount([issued()]);
    await screen.findByText("••••b8e3");
    await userEvent.click(screen.getByRole("button", { name: "Revoke" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog.textContent).toContain("Revoke this key?");
    expect(dialog.textContent).toContain("Their very next call is refused.");
    // B14 rule 6 — the commit that breaks something is not styled like Save.
    const confirm = Array.from(dialog.querySelectorAll("button")).find(
      (one) => one.textContent === "Revoke",
    );
    expect(confirm?.className).toContain("danger");
    expect(container.textContent).not.toContain("sbh_live_");
  });

  it("is tagged S144, not S142 — the register is matched in order", () => {
    expect(resolveScreen(ROUTE).a1).toBe("S144");
    expect(resolveScreen(`/brazosbend/settings/integrations/${PARTNER}`).a1).toBe("S142");
  });
});
