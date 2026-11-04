// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-023 (EP-CWP-06) — the switcher re-scopes EVERY tab
// Defects:  DEF-CWP-3900 — the choice was per-page state, so it did not
//           survive the navigation it exists to survive
// Rules:    BR-CWP-010 (the scope is applied in the QUERY, never in the
//           screen) · BR-CWP-013 (the set is FLAT) · B14 rule 31 (the id is
//           never a visible value — hence no `?account=` in the address bar)
// Cases:    TC-2 the choice survives a tab change and reaches the query ·
//           TC-3 an id outside the set is not what the screen asks for ·
//           TC-4 one account · the hook without a provider
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, Link } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { PortalAccount } from "../api/portalClient";
import { getBills, getMoneyList } from "../api/portalClient";
import {
  CurrentAccountProvider,
  resolveCurrentAccount,
  useCurrentAccount,
} from "./currentAccount";

afterEach(cleanup);

function account(id: string, label: string): PortalAccount {
  return {
    id,
    account_no: `ACC-${id}`,
    label,
    permissions: ["see"],
    source: "holder",
    is_master: false,
  };
}

const ELM_A = account("a1", "1408 Elm St · A");
const ELM_B = account("a2", "1408 Elm St · B");
const COMMON = account("a3", "1408 Elm St · Common areas");
const PALM = account("a4", "22 Palm Ct");
const SET = [ELM_A, ELM_B, COMMON, PALM];

describe("which account a screen reads (US-CWP-023)", () => {
  it("reads the chosen one while it is still in the set", () => {
    expect(resolveCurrentAccount(SET, "a4")).toBe("a4");
  });

  it("falls back to the first entry when the choice has left the set", () => {
    // ⚠ NOT COSMETIC. A delegate's access ends between two page loads and the
    // held id names an account this login may no longer read; every scoped
    // call would then answer 404 and the portal would look broken. The server
    // is still the guard — this only decides what to ASK for.
    expect(resolveCurrentAccount(SET, "ACC-99999-Z")).toBe("a1");
  });

  it("is null when there is nothing to read", () => {
    expect(resolveCurrentAccount([], "a4")).toBeNull();
  });
});

/** A stand-in for one tab: it prints whatever account the portal is on. */
function ProbeMarkup(props: { name: string; current: string | null; onChoose: () => void }) {
  return (
    <div>
      <span data-testid={`on-${props.name}`}>{props.current ?? "none"}</span>
      <button type="button" onClick={props.onChoose}>
        choose 22 Palm Ct
      </button>
      <Link to="/pine-hill/portal/usage">usage</Link>
      <Link to="/pine-hill/portal/bills">bills</Link>
    </div>
  );
}

// ⚠ **TWO DISTINCT COMPONENTS, AND THE FIRST DRAFT OF THIS FILE HAD ONE — SO
// IT COULD NOT FAIL** (hard-won law 7: prove it RED first). React reconciles
// by component TYPE and POSITION, so one `Probe` rendered by both routes keeps
// its own `useState` across the navigation, and the test passed with the
// provider deliberately removed. `BillsProbe` and `UsageProbe` are different
// types, which is what the real portal has (`BillsPage` and `UsagePage`) and
// is why the shipped per-page state was thrown away by every tab change.
function BillsProbe() {
  const [current, setCurrent] = useCurrentAccount();
  return <ProbeMarkup name="bills" current={current} onChoose={() => setCurrent("a4")} />;
}
function UsageProbe() {
  const [current, setCurrent] = useCurrentAccount();
  return <ProbeMarkup name="usage" current={current} onChoose={() => setCurrent("a4")} />;
}

function portal() {
  return render(
    <CurrentAccountProvider>
      <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
        <Routes>
          <Route path="/:tenant/portal/bills" element={<BillsProbe />} />
          <Route path="/:tenant/portal/usage" element={<UsageProbe />} />
        </Routes>
      </MemoryRouter>
    </CurrentAccountProvider>,
  );
}

describe("TC-2 · the switcher re-scopes every tab", () => {
  it("carries the choice across a tab change instead of resetting to the first account", async () => {
    // ⚠ **THIS IS THE DEFECT ITSELF** (`DEF-CWP-3900`). Before this file the
    // choice lived in a `useState` inside each page, so the assertion below
    // read `a1` — the landlord chose *22 Palm Ct*, pressed Usage, and was
    // silently put back on *1408 Elm St · A* with the header agreeing.
    const user = userEvent.setup();
    portal();
    expect(screen.getByTestId("on-bills")).toHaveTextContent("none");

    await user.click(screen.getByRole("button", { name: "choose 22 Palm Ct" }));
    expect(screen.getByTestId("on-bills")).toHaveTextContent("a4");

    await user.click(screen.getByRole("link", { name: "usage" }));
    expect(screen.getByTestId("on-usage")).toHaveTextContent("a4");

    await user.click(screen.getByRole("link", { name: "bills" }));
    expect(screen.getByTestId("on-bills")).toHaveTextContent("a4");
  });

  it("still works with no provider above it, which is how every page test renders", async () => {
    // A hook that threw without a provider would turn thirty-one green screen
    // tests red for a reason that has nothing to do with what they assert.
    const user = userEvent.setup();
    render(<BillsProbe />, { wrapper: MemoryRouter });
    await user.click(screen.getByRole("button", { name: "choose 22 Palm Ct" }));
    expect(screen.getByTestId("on-bills")).toHaveTextContent("a4");
  });
});

/**
 * Records the ADDRESS each read asks for — path plus query — and answers an
 * empty list.
 *
 * ⚠ **IT COMPOSES THE QUERY RATHER THAN READING THE PATH, SINCE
 * `DEF-CWP-5747`.** These wrappers used to build their own `?account_id=…`
 * string; they hand `client.get` a `query` OBJECT now, because the page, the
 * search and the sort travel beside the account and five wrappers each
 * spelling their own query string would be five chances to send `?search=` at
 * a server that reads `?q=`. Reading only `path` here would have recorded
 * `/portal/bills` for a request that did carry the account — a test that
 * silently stopped asserting the thing it exists for (`BR-CWP-010`).
 */
function recordingClient(seen: string[]): ApiClient {
  const answer = async <T,>(
    path: string,
    options?: { query?: Record<string, unknown> },
  ): Promise<ApiResponse<T>> => {
    const query = Object.entries(options?.query ?? {})
      .map(([key, value]) => `${key}=${String(value)}`)
      .join("&");
    seen.push(query === "" ? path : `${path}?${query}`);
    return { status: 200, data: { bills: [], money: [] } as unknown as T } as ApiResponse<T>;
  };
  return {
    request: (path: string, options?: { query?: Record<string, unknown> }) =>
      answer(path, options),
    get: (path: string, options?: { query?: Record<string, unknown> }) => answer(path, options),
    post: (path: string, options?: { query?: Record<string, unknown> }) => answer(path, options),
  } as unknown as ApiClient;
}

describe("TC-2 · the scope is in the QUERY, never in the screen (BR-CWP-010)", () => {
  it("names the account on the wire for bills and for payments", async () => {
    const seen: string[] = [];
    const client = recordingClient(seen);
    await getBills({ accountId: "a4" }, client);
    await getMoneyList({ accountId: "a4" }, client);
    await getMoneyList({ accountId: "a4", year: 2026 }, client);
    expect(seen).toEqual([
      "/portal/bills?account_id=a4",
      "/portal/payments?account_id=a4",
      // ⚠ **`year` IS ITS OWN PARAMETER AND NOT AN `f.` FILTER**, because the
      // server applies it BEFORE `BR-CWP-061`'s bounce pairing — a reversal and
      // the payment it undoes have to stay adjacent.
      "/portal/payments?year=2026&account_id=a4",
    ]);
  });

  it("asks for the whole set when the switcher names nothing — the old behaviour, unchanged", async () => {
    const seen: string[] = [];
    const client = recordingClient(seen);
    await getBills({}, client);
    await getMoneyList({}, client);
    expect(seen).toEqual(["/portal/bills", "/portal/payments"]);
  });
});
