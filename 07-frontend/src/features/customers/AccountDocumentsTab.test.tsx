// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave I — `ACC-S8`'s FRONTEND cases.
// Rules:    BR-CUS-036 (the five CONFIRMED types) · BR-SHL-031 (the allowlist
//           in the file input's `accept`) · BR-SHL-010 (no Export — nothing
//           registers this resource) · BR-CUS-1046 (newest first) ·
//           B14 rule 16 (the pagination footer) · rule 31 (no database id on
//           screen) · hard-won law 2 (built is not wired).
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIRST CASE IS LAW 2 AND IT IS THE ONE THAT MATTERS.** A tab whose
// component renders and whose endpoint is merely MOUNTED is dead UI: it draws
// nothing, every other assertion still passes, and the feature does not exist.
// So the first thing asserted is that the tab CALLS `GET /accounts/{id}/documents`
// with the tenant in the path.
//
// ⚠ **AND THE `Evidence` CASE ASSERTS AN ABSENCE FROM THE WHOLE RENDER, which
// is the only honest form it can take.** The drawing `ACC-T10` offers a chip
// this product must not have — `Evidence` is not one of `BR-CUS-036`'s five
// CONFIRMED types — and a case that checked the chip list would pass on a
// screen that grew the word somewhere else.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import {
  ACCOUNT_DOCUMENT_ACCEPT,
  ACCOUNT_DOCUMENT_TYPES,
  AUDIT_LOCKED_ACCOUNT_DOCUMENT_TYPES,
  REMOVABLE_ACCOUNT_DOCUMENT_TYPES,
  UPLOADABLE_ACCOUNT_DOCUMENT_TYPES,
  listAccountDocuments,
} from "@/api/endpoints";
import type { AccountDocument } from "@/api/endpoints";
import { defaultRequestState } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import {
  AccountDocumentsTab,
  documentsQueryKey,
  documentsTableConfig,
  formatBytes,
  lockedReason,
} from "./AccountDocumentsTab";

const TEST_TENANT = "brazosbend";
const ACCOUNT = "3f1a9c2e-0000-7000-8000-000000000001";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CONFIG = documentsTableConfig(t, {
  date: () => <span />,
  size: () => <span />,
  actions: () => <span />,
});

function row(overrides: Partial<AccountDocument> = {}): AccountDocument {
  return {
    id: "0198f3c2-0000-7000-8000-00000000000a",
    name: "account-documents/2026/09/AC-2026-00042-signed-lease.pdf",
    doc_type: "contract",
    uploaded_at: "2026-09-11T14:02:00Z",
    uploaded_by_name: "Dana Ruiz",
    uploaded_by_process: null,
    size_bytes: 61440,
    content_type: "application/pdf",
    ...overrides,
  };
}

async function renderTab(
  body: { count: number; results: AccountDocument[] } | "unreadable",
): Promise<{ html: string; urls: string[] }> {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return body === "unreadable"
        ? new Response(JSON.stringify({ detail: "boom" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
    },
  });
  // ⚠ `retryOnMount: false` IS LOAD-BEARING FOR THE ERROR CASE, and finding out
  // why cost twenty minutes worth writing down. An errored query with no data
  // REFETCHES on mount by default, and the optimistic result during that fetch
  // reports `status: "pending"` — so `DataTable` drew its loading skeleton and
  // the error sentence was never rendered. The screen is right; the harness was
  // measuring a query it had just restarted.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryOnMount: false } },
  });
  const state = defaultRequestState(CONFIG);
  try {
    // ⚠ **THE SAME KEY AND THE SAME FUNCTION THE COMPONENT USES.** A harness
    // that prefetches under a key the screen does not read leaves the screen
    // PENDING, so an error case renders a skeleton and the assertion fails for
    // a reason that has nothing to do with the screen — which is what the first
    // draft of this file did.
    await queryClient.fetchQuery({
      queryKey: documentsQueryKey(ACCOUNT, state),
      queryFn: () =>
        listAccountDocuments(
          ACCOUNT,
          {
            q: state.q,
            page: state.page,
            per: state.per,
            sort: state.sort,
            dir: state.dir,
            type: state.filters.type,
          },
          client,
        ),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  const html = renderToStaticMarkup(
    // ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
    // `/:tenant/...` route leaves `useParams().tenant` undefined, so every URL
    // the page builds comes out `//…` — a protocol-relative address to another
    // host, which reads as a perfectly good string to `toContain`.
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/${ACCOUNT}?tab=documents`]}>
          <AccountDocumentsTab accountId={ACCOUNT} client={client} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { html, urls };
}

describe("ACC-S8 · the Documents tab", () => {
  it("law 2 — the tab CALLS `GET /accounts/{id}/documents`; the endpoint is not merely mounted", async () => {
    const { urls } = await renderTab({ count: 1, results: [row()] });
    expect(urls.length).toBeGreaterThanOrEqual(1);
    expect(urls[0]).toContain(`/accounts/${ACCOUNT}/documents`);
    expect(urls[0]).toContain(TEST_TENANT);
  });

  it("draws `ACC-T10`'s five column heads in the drawn order, then the actions cell", () => {
    // ⚠ **THE SIXTH COLUMN IS NOT THE DRAWING BEING OVERRULED — IT IS NEWER
    // THAN THE DRAWING.** `ACC-T10` draws five columns and no row action
    // because when it was drawn nothing could remove a document.
    // `BR-CUS-1052` (PO 2026-09-13) changed that, and B14 rule 15 then decides
    // the shape: one trailing column of icons.
    expect(CONFIG.columns.map((column) => column.key)).toEqual([
      "name",
      "type",
      "uploaded",
      "uploaded_by",
      "size",
      "actions",
    ]);
    expect(CONFIG.columns.map((column) => column.label)).toEqual([
      "Document",
      "Type",
      "Date",
      "Uploaded by",
      "Size",
      "Actions",
    ]);
  });

  it("`BR-CUS-1046` — the list opens NEWEST FIRST, not on the oldest scan", () => {
    expect(CONFIG.defaultSort).toEqual({ sort: "uploaded", dir: "desc" });
  });

  it("the type filter offers `BR-CUS-036`'s five CONFIRMED values and nothing else", () => {
    const filter = (CONFIG.filters ?? []).find((f) => f.name === "type");
    expect(filter).toBeDefined();
    expect(filter?.options.map((option) => option.value)).toEqual([...ACCOUNT_DOCUMENT_TYPES]);
    expect(ACCOUNT_DOCUMENT_TYPES).toHaveLength(5);
  });

  it("the drawing's `Evidence` chip appears NOWHERE — a wireframe cannot amend signed law", async () => {
    const { html } = await renderTab({ count: 1, results: [row()] });
    expect(html).not.toContain("Evidence");
  });

  it("a clerk may file four of the five types — `system` attaches automatically", () => {
    expect([...UPLOADABLE_ACCOUNT_DOCUMENT_TYPES]).toEqual([
      "contract",
      "kyc",
      "payment",
      "correspondence",
    ]);
    expect(UPLOADABLE_ACCOUNT_DOCUMENT_TYPES).not.toContain("system");
  });

  it("`BR-SHL-031`'s allowlist reaches the file picker", () => {
    expect(ACCOUNT_DOCUMENT_ACCEPT).toBe(".pdf,.png,.jpg,.jpeg,.csv");
  });

  it("B14 rule 31 — the row shows the document's NAME and never its id", async () => {
    const { html } = await renderTab({ count: 1, results: [row()] });
    expect(html).toContain("AC-2026-00042-signed-lease.pdf");
    expect(html).not.toContain("0198f3c2-0000-7000-8000-00000000000a");
  });

  it("a document the PRODUCT filed says so, rather than leaving the person cell blank", async () => {
    const { html } = await renderTab({
      count: 1,
      results: [
        row({ uploaded_by_name: null, uploaded_by_process: "customers.move_in", doc_type: "system" }),
      ],
    });
    expect(html).toContain("The system");
    // ⚠ And NEVER the dotted process path — B14 rule 32: no internal code in
    // clerk-facing copy.
    expect(html).not.toContain("customers.move_in");
  });

  it("`BR-SHL-010` — there is no Export, because nothing registers this resource", async () => {
    const { html } = await renderTab({ count: 1, results: [row()] });
    expect(html).not.toContain("Export");
  });

  it("the empty state states the absence and still offers the one way in", async () => {
    const { html } = await renderTab({ count: 0, results: [] });
    expect(html).toContain("No documents filed yet.");
    expect(html).toContain("Upload document");
  });

  it("a failed read says so in plain language and offers a retry", async () => {
    const { html } = await renderTab("unreadable");
    expect(html).toContain("The documents could not be loaded.");
  });

  it("the size is rendered in the unit a person would say it in", () => {
    expect(formatBytes(512, "en")).toBe("512 B");
    expect(formatBytes(61440, "en")).toBe("60 KB");
    expect(formatBytes(10 * 1024 * 1024, "en")).toBe("10 MB");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `BR-CUS-1052` — a clerk can take back a document they filed (wave M)
//
// ⚠ **WHAT THESE CASES CANNOT SEE, SAID OUT LOUD.** `renderToStaticMarkup`
// paints first paint and stops, so the confirm dialog — which only exists after
// the bin is pressed — is NOT reachable from here. The dialog's danger tier is
// audited by `components/ConfirmDialogTier.dom.test.tsx`'s call-site census,
// which reads this feature's SOURCE, and the census went red on this very
// dialog before it shipped. Saying which check owns which half is the point:
// hard-won law 7's *reporting zero over a scope it silently excludes*.
// ══════════════════════════════════════════════════════════════════════════

describe("BR-CUS-1052 · taking a filing back", () => {
  it("law 2 — a Remove control REACHES THE SCREEN, on a row that may be removed", async () => {
    const { html } = await renderTab({
      count: 1,
      results: [row({ doc_type: "kyc", name: "drivers-licence.pdf" })],
    });
    // Addressed by its ACCESSIBLE NAME, which is the same string a screen
    // reader announces — a `data-testid` would pass with no label at all,
    // which is the exact failure B14 rule 15 exists to prevent.
    expect(html).toContain('aria-label="Remove"');
    // ⚠ **AND IT IS ENABLED, ASSERTED BY A DISCRIMINATOR RATHER THAN BY HOPE.**
    // A bin drawn and then disabled would satisfy the line above while the
    // feature did not exist. `RowAction` writes `title={reason ?? hint ??
    // label}`, so `title="Remove"` is reachable ONLY when no reason blocked
    // it — one attribute that cannot be true of a disabled control.
    expect(html).toContain('title="Remove"');
    expect(html).not.toContain("cannot be removed");
  });

  it("`BR-CUS-036` — a CONTRACT's Remove is disabled and carries its reason", async () => {
    const { html } = await renderTab({
      count: 1,
      results: [row({ doc_type: "contract" })],
    });
    // `BR-SHL-025`: a control that cannot act is DISABLED WITH ITS REASON,
    // never hidden. Both halves are asserted, because either alone is a
    // different screen: hidden teaches nothing, and enabled reaches a 409.
    expect(html).toContain("Contract files cannot be removed.");
    expect(html).toContain("disabled");
  });

  it("a SYSTEM document says the system's reason, not the contract's", async () => {
    const { html } = await renderTab({
      count: 1,
      results: [row({ doc_type: "system", uploaded_by_name: null, uploaded_by_process: "billing.issue" })],
    });
    expect(html).toContain("System files cannot be removed.");
    expect(html).not.toContain("Contract files cannot be removed.");
  });

  it("uploadable and removable are DIFFERENT subsets — a contract goes in and never comes out", () => {
    // ⚠ **THE ASYMMETRY IS THE RULE, NOT AN OVERSIGHT.** `BR-CUS-036`
    // audit-locks system AND contract; `contract` is uploadable because a
    // countersigned lease arrives on paper. A lane deriving one list from the
    // other would make every lease removable, and no test but this one would
    // notice.
    expect([...REMOVABLE_ACCOUNT_DOCUMENT_TYPES]).toEqual(["kyc", "payment", "correspondence"]);
    expect([...AUDIT_LOCKED_ACCOUNT_DOCUMENT_TYPES]).toEqual(["system", "contract"]);
    expect(UPLOADABLE_ACCOUNT_DOCUMENT_TYPES).toContain("contract");
    expect(REMOVABLE_ACCOUNT_DOCUMENT_TYPES).not.toContain("contract");
  });

  it("the two lists PARTITION the five types — a sixth lands in exactly one", () => {
    const covered = [...REMOVABLE_ACCOUNT_DOCUMENT_TYPES, ...AUDIT_LOCKED_ACCOUNT_DOCUMENT_TYPES];
    expect([...covered].sort()).toEqual([...ACCOUNT_DOCUMENT_TYPES].sort());
    expect(new Set(covered).size).toBe(ACCOUNT_DOCUMENT_TYPES.length);
  });

  it("`lockedReason` answers null exactly where the server allows a withdrawal", () => {
    for (const value of ACCOUNT_DOCUMENT_TYPES) {
      const reason = lockedReason(t, value);
      expect(reason === null).toBe(
        (REMOVABLE_ACCOUNT_DOCUMENT_TYPES as readonly string[]).includes(value),
      );
    }
  });

  it("B14 rule 33 — the consequence is two sentences, neither over six words", () => {
    // ⚠ **THE CAP IS CHECKED HERE BECAUSE NO GATE READS THIS KIND OF STRING.**
    // G33 enforces the REFUSAL half of rule 33; a CONSEQUENCE before an
    // irreversible act has its own cap — six words per sentence, at most two —
    // and nothing in this repo measures it. So the one string that has to obey
    // it is measured where it is written.
    const text = t("customers.account.documents.removeWarning");
    const sentences = text.split(".").map((part) => part.trim()).filter(Boolean);
    expect(sentences).toHaveLength(2);
    for (const sentence of sentences) {
      expect(sentence.split(/\s+/).length).toBeLessThanOrEqual(6);
    }
    // ⚠ And it says BOTH facts: the filing goes for good, and the file stays.
    // A consequence that omitted the second would tell a clerk they had
    // destroyed a customer's identity scan when they had not.
    expect(text).toContain("permanently");
    expect(text).toContain("kept");
  });

  it("the confirm TITLE is a heading, capped at three words", () => {
    expect(t("customers.account.documents.removeTitle").replace("?", "").split(/\s+/).length)
      .toBeLessThanOrEqual(3);
  });
});
