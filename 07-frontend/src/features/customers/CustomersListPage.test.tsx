// ── Trace ──────────────────────────────────────────────
// Change:   CR-056 W5 task 25 — the customers list, its search and one person's
//           accounts. CR-056 §4 measured the absence: *"you reach a person only
//           through the accounts linked to them"*.
// Rules:    BR-CUS-054 (one customer, many accounts) · BR-CUS-089 (the tier is
//           STORED with its confirmer) · BR-CUS-092(c) (LAST FOUR ONLY — the
//           full identifier never reaches a list response) · B14 rule 19 (the
//           search prompt names what it matches) · rule 31 (no database id is
//           the visible value of a field) · rule 32 (one sentence per section)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE MOST IMPORTANT CASE IN THIS FILE IS AN ABSENCE**, and it is written
// first: no spelling of a Social Security number may appear in the rendered
// markup. A number that reaches the browser is in devtools, in a proxy log and
// in the HAR file attached to a ticket, whatever the screen chooses to draw —
// so this is asserted against the HTML rather than against the component's
// props, which is the only form of the assertion that can fail for the right
// reason.
//
// ⚠ **AND A RENDER TEST CANNOT SEE A TAILWIND UTILITY THAT DID NOT COMPILE.**
// jsdom performs no layout, so `toContain("tabular-nums")` passes whether the
// class draws or not (B14 rule 21's per-file migration clause, DEF-974). That
// half is answered by `10-scripts/render-checks/cr056-customers-list.mjs` in a
// real browser and by `src/styles/routeBUtilities.test.ts`, which puts every
// class token in this file through the actual compiler.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { defaultRequestState } from "@/components/tableTypes";

import {
  AccountsCell,
  CustomersListPage,
  IdentityCell,
  customersQueryKey,
  customersTableConfig,
  renderCustomerAccounts,
} from "./CustomersListPage";
import { listCustomers } from "./customerEndpoints";
import type { CustomerList, CustomerRow } from "./customerEndpoints";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The worked case the backend suite follows end to end: Rosa Alvarez, holding
 *  a Social Security number ending `6789` and a licence ending `4417`. */
const SSN_DIGITS = "123456789";
const FORBIDDEN = [SSN_DIGITS, "123-45-6789", "123-45", "45-6789", "12345", "456789"];

function row(over: Partial<CustomerRow> = {}): CustomerRow {
  return {
    id: "01a05a61-bedb-7607-90a5-53ace7bb0e8f",
    customer_no: "C-00417",
    display_name: "Alvarez, Rosa",
    kind: "person",
    external_ref: null,
    phone: "512-555-0142",
    identity: {
      date_of_birth: "1974-03-02",
      ssn_held: true,
      ssn_last4: "6789",
      driving_licence_held: true,
      driving_licence_last4: "4417",
      // CR-056 W2b — a PERSON holds no Tax ID. The shape carries both halves so
      // a screen needs no branch to read it; `kind` says which half to expect.
      tax_id_held: false,
      tax_id_last4: null,
    },
    account_count: 2,
    accounts: [
      {
        id: "acct-1",
        account_no: "A-10432",
        kind: "regular",
        status_code: "active",
        status_name: "Active",
        match_tier: "strong",
        match_basis: "matched on name, date of birth and Social Security number",
      },
      {
        id: "acct-2",
        account_no: "A-10433",
        kind: "master",
        status_code: "active",
        status_name: "Active",
        // Every link an import wrote carries no tier — a legacy reference is a
        // reconciliation key, not identity. A blank must read as a real state.
        match_tier: null,
        match_basis: null,
      },
    ],
    ...over,
  };
}

function payload(over: Partial<CustomerList> = {}): CustomerList {
  return { count: 1, results: [row()], ...over };
}

async function renderList(body: CustomerList | "unreadable"): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      body === "unreadable"
        ? new Response(JSON.stringify({ detail: "boom" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
  });
  // ⚠ `retryOnMount: false` is load-bearing and not tidiness: a query the
  // prefetch left in ERROR is stale, so on mount react-query refetches it and
  // the first paint is a SKELETON with `isError` false. The error branch
  // would then be unreachable in a static render — a case that can only pass.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryOnMount: false } },
  });
  const state = defaultRequestState(
    customersTableConfig(t, {
      identity: () => <span />,
      accounts: () => <span />,
      actions: () => <span />,
    }),
  );
  try {
    await queryClient.prefetchQuery({
      queryKey: customersQueryKey(state),
      queryFn: () =>
        listCustomers(
          { q: "", page: state.page, per: state.per, sort: state.sort, dir: state.dir },
          client,
        ),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/customers`]}>
        <CustomersListPage client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CR-056 task 25 · the customers list", () => {
  it("BR-CUS-092(c) · no spelling of the identifier reaches the markup", async () => {
    const html = await renderList(payload());
    for (const spelling of FORBIDDEN) {
      expect(html).not.toContain(spelling);
    }
    // The last four IS allowed, and is drawn — otherwise the case above would
    // pass on a screen that shows nothing at all.
    expect(html).toContain("6789");
    expect(html).toContain("4417");
  });

  it("B14 rule 31 · the NUMBER is the visible value and the row id is not", async () => {
    const html = await renderList(payload());
    expect(html).toContain("C-00417");
    // The uuid may ride as a machine handle (a key, an href); it may never be
    // the value of a field. Asserted as "not in a table cell", which is the
    // only form of the claim that is about what a person reads.
    expect(html).not.toContain(">01a05a61-bedb-7607-90a5-53ace7bb0e8f<");
  });

  it("BR-CUS-054 · one person, and every account they hold", async () => {
    const html = await renderList(payload());
    expect(html).toContain("Alvarez, Rosa");
    expect(html).toContain('data-account-count="2"');
    // ⚠ **THE ACCOUNT NUMBERS LIVE IN THE EXPANDED ROW, WHICH A COLLAPSED
    // FIRST PAINT DOES NOT RENDER**, so asserting them against the page markup
    // would be a case that passes on a screen where the disclosure is broken
    // and fails on one where it works. The disclosure content is rendered
    // directly instead — same function the table calls when a clerk opens a
    // row, and it can only pass if that function draws the accounts.
    const expanded = renderToStaticMarkup(
      <MemoryRouter>{renderCustomerAccounts(row(), t, (segment) => `/acme${segment}`)}</MemoryRouter>,
    );
    expect(expanded).toContain("A-10432");
    // Record links (PO 2026-10-19): each number opens its account.
    expect(expanded).toContain(`href="/acme/accounts/acct-1"`);
    expect(expanded).toContain("A-10433");
    // BR-CUS-089 — the strong link says what it matched on; the import link
    // says it was not matched, rather than drawing an empty cell.
    expect(expanded).toContain("date of birth");
    expect(expanded).toContain(t("customers.customer.list.notMatched"));
  });

  it("a company draws its Tax ID, which before CR-056 W2b read as nothing on file", () => {
    // BR-CUS-1022 (PO 2026-09-01) — a business is identified by its Tax ID and
    // by nothing else, so a company row used to say *Nothing on file* however
    // completely it had been identified. Last four only, like its siblings.
    const html = renderToStaticMarkup(
      <IdentityCell
        row={row({
          display_name: "Silver Creek Duplex Holdings LLC",
          kind: "company",
          identity: {
            date_of_birth: null,
            ssn_held: false,
            ssn_last4: null,
            driving_licence_held: false,
            driving_licence_last4: null,
            tax_id_held: true,
            tax_id_last4: "6789",
          },
        })}
        t={t}
      />,
    );
    expect(html).toContain('data-identity="held"');
    expect(html).toContain("6789");
    // BR-CUS-092(c) — the digits before the last four never reach a browser.
    for (const spelling of FORBIDDEN) {
      expect(html).not.toContain(spelling);
    }
  });

  it("a person with no identifier on file says so rather than drawing a blank", () => {
    const html = renderToStaticMarkup(
      <IdentityCell
        row={row({
          identity: {
            date_of_birth: null,
            ssn_held: false,
            ssn_last4: null,
            driving_licence_held: false,
            driving_licence_last4: null,
            tax_id_held: false,
            tax_id_last4: null,
          },
        })}
        t={t}
      />,
    );
    expect(html).toContain('data-identity="none"');
    expect(html).toContain(t("customers.customer.list.identityNone"));
  });

  it("a customer with no number reads as a stated blank, never as the row id", () => {
    const config = customersTableConfig(t, {
      identity: () => <span />,
      accounts: () => <span />,
      actions: () => <span />,
    });
    const numberColumn = config.columns.find((column) => column.key === "customer_no");
    expect(numberColumn?.identity).toBe(true);
    const html = renderToStaticMarkup(
      <>{numberColumn?.cell?.(row({ customer_no: null })) ?? null}</>,
    );
    expect(html).toContain(t("customers.customer.list.noNumber"));
    expect(html).not.toContain("01a05a61");
  });

  it("B14 rule 19 · the search prompt names what the server really matches", () => {
    const config = customersTableConfig(t, {
      identity: () => <span />,
      accounts: () => <span />,
      actions: () => <span />,
    });
    expect(config.searchPlaceholder).toBe("customers.customer.list.searchPlaceholder");
    // The prompt is a KEY and it resolves — a screen that shipped an unresolved
    // key would print the key itself to the clerk (the G15 defect).
    expect(t(config.searchPlaceholder as string)).not.toBe(config.searchPlaceholder);
    expect(config.searchFields).toEqual(["customer_no", "display_name", "external_ref", "phone"]);
  });

  it("the accounts count is a number and never a sentence (B14 rule 32)", () => {
    const html = renderToStaticMarkup(<AccountsCell row={row()} t={t} />);
    expect(html).toContain(">2<");
    // A cell holds a VALUE. Ten of these became a wall of prose on 2026-08-30.
    expect(html.replace(/<[^>]*>/g, "").trim().split(/\s+/).length).toBe(1);
  });

  it("an unreadable list says so and offers a retry, and invents no rows", async () => {
    const html = await renderList("unreadable");
    expect(html).toContain(t("customers.customer.list.loadFailed"));
    expect(html).not.toContain("Alvarez, Rosa");
  });

  it("BR-CUS-1054 · the edit pencil is on the row and it is LIVE", async () => {
    // ⚠ **HARD-WON LAW 2's MIRROR: a live screen behind a DEAD control.** G13
    // asks whether a prop is passed; nothing asks whether a refusal is still
    // true. `PATCH /customers/{id}` exists as of 2026-09-13, so this pencil must
    // be enabled — and must be asserted so, not merely present.
    const html = await renderList(payload());
    expect(html).toContain(t("customers.customer.action.edit"));
    const pencil = html.slice(html.indexOf('data-testid="customer-edit-'));
    expect(pencil.slice(0, 200)).not.toContain("disabled");
  });

  it("the query key changes when the kind filter changes, so the page refetches", () => {
    const config = customersTableConfig(t, {
      identity: () => <span />,
      accounts: () => <span />,
      actions: () => <span />,
    });
    const base = defaultRequestState(config);
    const filtered = { ...base, filters: { kind: "company" } };
    expect(customersQueryKey(base)).not.toEqual(customersQueryKey(filtered));
  });
});
// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-056 W5 task 25 (12-governance/11-change-requests.md §CR-056)
//         + BR-CUS-054 + BR-CUS-089 + BR-CUS-092(c) + B14 rules 19, 31, 32
//         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-056` allocates no story ids, and minting one to satisfy `G01`'s regex would put a citation in the tree that resolves to nothing. Same posture as `apps/customers/close_out.py`, which writes its DEF id instead
// generated: 2026-08-31 by the CR-056 W2/W3/W5 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest 9/9 in this file · tsc --noEmit clean · eslint --max-warnings 0 clean · vitest CustomersListPage.test.tsx 9/9 · src/features/customers 627 passed · routeBUtilities.test.ts 10/10 · G31 PASS (0 undeclared classes) · G13 PASS
// exceptions: `retryOnMount: false` on the test QueryClient is LOAD-BEARING, not tidiness — a query the prefetch left in ERROR is stale, so react-query refetches it on mount and the first paint is a SKELETON with `isError` false, which would make the error branch a case that can only pass · the account numbers are asserted against `renderCustomerAccounts` rather than against the page markup: a collapsed first paint renders none of the expanded row, so a page-level assertion would pass on a screen whose disclosure is broken · NO case can see whether a Tailwind utility COMPILED — jsdom performs no layout, so `toContain("tabular-nums")` passes whether the class draws or not (B14 rule 21's per-file clause, DEF-974); that half is `10-scripts/render-checks/cr056-customers-list.mjs` and `src/styles/routeBUtilities.test.ts`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
