// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-6342 — the banner BR-PAY-018 names, and the clear step that
//          sends the clerk to the address the letter actually went to (PO
//          ruling 2026-09-23: "ensure you update correct address - mailing or
//          service").
// Tests:   the banner follows the ONE stored flag · a MAILING letter offers the
//          mailing correction · a SERVICE letter offers ADD mailing and links
//          the premises, never an edit of it · "address is correct" posts the
//          clear with `verified_current` and the date the clerk confirmed.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";
import type { ReturnedPostRow } from "@/api/returnedMailEndpoints";

import { ReturnedPostBanner, latestWentTo, wentToKey } from "./ReturnedPostBanner";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-1",
    account_no: "A-11340",
    bad_address: true,
    addresses: [],
    contacts: [{ id: "c-1", full_name: "Sarah Miller" }],
    service_premises_id: "prem-7",
    custom_data: {},
    ...over,
  } as unknown as AccountDetail;
}

function row(over: Partial<ReturnedPostRow> = {}): ReturnedPostRow {
  return {
    event_id: "ev-1",
    account_id: "acc-1",
    account_no: "A-11340",
    customer_name: "Sarah Miller",
    returned_on: "2026-09-08",
    source_type: "invoice",
    went_to: "service_address",
    address: "1408 Bluestem Ln · Unit A",
    ...over,
  };
}

/** A client that serves the account's open returns and records every post. */
function client(rows: ReturnedPostRow[], posted: { path: string; body: unknown }[]): ApiClient {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200, headers: new Headers() });
  return {
    get: <T,>(path: string) => {
      if (path !== "/returned-mail") throw new Error(`unplanned get(${path})`);
      return Promise.resolve(
        answer<T>({ count: rows.length, next: null, previous: null, results: rows }),
      );
    },
    post: <T,>(path: string, body: unknown) => {
      posted.push({ path, body });
      return Promise.resolve(
        answer<T>({ account_id: "acc-1", returns_resolved: rows.length, flag_cleared: true }),
      );
    },
    request: () => {
      throw new Error("unplanned request()");
    },
  } as unknown as ApiClient;
}

function mount(account: AccountDetail, api: ApiClient, done: string[] = []) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // Mounted under the REAL tenant path pattern (hard-won law 2): a bare
  // mount builds `//premises/…` and a link that reads fine to `toContain`.
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/accounts/acc-1"]}>
        <Routes>
          <Route
            path="/:tenant/accounts/:accountId"
            element={
              <ReturnedPostBanner
                detail={account}
                timeZone="America/Chicago"
                dateFormat="MM/DD/YYYY"
                client={api}
                t={t}
                onDone={(message) => done.push(message)}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ReturnedPostBanner (DEF-PAY-6342)", () => {
  it("renders nothing while the account's stored flag is down", () => {
    const { container } = mount(detail({ bad_address: false }), client([], []));
    expect(container.querySelector("[data-returned-post-banner]")).toBeNull();
  });

  it("shows the banner as a fact of six words or fewer", () => {
    mount(detail(), client([], []));
    const sentence = t("customers.account.returnedPost.banner");
    expect(screen.getByText(sentence)).toBeInTheDocument();
    expect(sentence.replace(/[.]/g, "").split(/\s+/).length).toBeLessThanOrEqual(6);
  });

  it("a MAILING letter offers the mailing correction and no premises link", async () => {
    const user = userEvent.setup();
    mount(
      detail({ addresses: [{ id: "ad-1", kind: "mailing", line1: "PO Box 77" }] as never }),
      client([row({ went_to: "mailing_address", address: "PO Box 77" })], []),
    );
    await user.click(screen.getByRole("button", { name: t("customers.account.returnedPost.resolve") }));
    expect(await screen.findByText(/PO Box 77/)).toBeInTheDocument();
    expect(
      screen.getByText(t("customers.account.returnedPost.option.correctMailing")),
    ).toBeInTheDocument();
    expect(screen.queryByText(t("customers.account.returnedPost.option.addMailing"))).toBeNull();
    expect(document.querySelector("[data-returned-post-premises]")).toBeNull();
  });

  it("a SERVICE letter offers ADD mailing and LINKS the premises, never edits it", async () => {
    const user = userEvent.setup();
    mount(detail(), client([row()], []));
    await user.click(screen.getByRole("button", { name: t("customers.account.returnedPost.resolve") }));
    expect(await screen.findByText(/1408 Bluestem Ln · Unit A/)).toBeInTheDocument();
    expect(
      screen.getByText(t("customers.account.returnedPost.option.addMailing")),
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: t("customers.account.returnedPost.openPremises") });
    expect(link.getAttribute("href")).toBe("/brazosbend/premises/prem-7");
  });

  it("'address is correct' clears with verified_current and the confirmed date", async () => {
    const user = userEvent.setup();
    const posted: { path: string; body: unknown }[] = [];
    const done: string[] = [];
    mount(detail(), client([row()], posted), done);
    await user.click(screen.getByRole("button", { name: t("customers.account.returnedPost.resolve") }));
    await screen.findByText(/1408 Bluestem Ln/);
    await user.click(screen.getByText(t("customers.account.returnedPost.option.addressCorrect")));
    await user.click(screen.getByRole("button", { name: t("customers.account.returnedPost.submit.clear") }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].path).toBe("/returned-mail/clear");
    expect(posted[0].body).toMatchObject({
      account_id: "acc-1",
      resolution: "verified_current",
    });
    expect((posted[0].body as { resolved_on: string }).resolved_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(done).toEqual([t("customers.account.returnedPost.cleared")]);
  });

  it("refuses a clear with no outcome chosen, in the clerk's language", async () => {
    const user = userEvent.setup();
    const posted: { path: string; body: unknown }[] = [];
    mount(detail(), client([row()], posted));
    await user.click(screen.getByRole("button", { name: t("customers.account.returnedPost.resolve") }));
    await screen.findByText(/1408 Bluestem Ln/);
    await user.click(screen.getByRole("button", { name: t("customers.account.returnedPost.submit.clear") }));
    expect(
      await screen.findByText(t("customers.account.returnedPost.outcomeRequired")),
    ).toBeInTheDocument();
    expect(posted).toHaveLength(0);
  });

  it("routes on the MOST RECENT letter and names an unrecorded address", () => {
    expect(latestWentTo([row({ went_to: "mailing_address" }), row({ went_to: null })])).toBeNull();
    expect(latestWentTo([])).toBeNull();
    expect(t(wentToKey(null))).toBe("Address not recorded");
  });
});
