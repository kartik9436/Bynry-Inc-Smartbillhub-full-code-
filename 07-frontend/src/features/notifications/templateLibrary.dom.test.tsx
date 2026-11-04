// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave E task E9 — ONE Templates screen over BOTH template
//          stores.  Screens: SET-09 (the list) · S8 → Configure → Templates
// Rules:   BR-NOT-026 (PO 2026-08-30, *"Yes, Go with option B; I agree"* — one
//          screen and one service, TWO stores, no row moves) · BR-NOT-025 ·
//          BR-SHL-011 (`f.<name>` URL grammar) · BR-SHL-010 (an undeclared
//          capability is not rendered) · B14 rule 12 · rule 15 · rule 21
// ───────────────────────────────────────────────────────
// WHAT A PERSON COULD NOT DO BEFORE, IN ONE SENTENCE: open Templates and see
// the letters this utility sends AND the layout its bills print on in the same
// list.
//
// The tab drew TWO lists — the catalogue, and billing's bill-layout chooser in
// a panel underneath it — so *"the template we print bills on"* lived in the
// second one and you had to know that. The chooser is not deleted: it is now
// the EDITOR a bill row opens, the way the template detail is the editor a
// notification row opens.
//
// ⛔ **WHAT THIS DOES NOT DO, AND MUST NOT BE "FINISHED" INTO.** The two
// database stores stay two stores — that is the ruling. The one list is
// assembled where it is drawn, from two requests. See
// `apps/notifications/unified_templates.py` and its guard,
// `06-backend/tests/test_cr048_e9_two_stores_one_screen.py`.
//
// ── PROVED RED FIRST (hard-won law 7) ─────────────────────────────────────
// Run against the pre-change screen, every case failed on its own locator —
// the bill row simply was not in the table:
//   · the bill template is in the list  → Unable to find an element by:
//       [data-testid="template-name-bill:BT-1"]
//   · every row says which kind it is   → Unable to find an element by:
//       [data-testid="template-kind-dunning"]
//   · a bill row opens the chooser      → Unable to find an element by:
//       [data-testid="bill-layout-back"]
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { TemplateCatalogPage, TemplateCatalogRow } from "@/api/endpoints";
import type { TemplateLibraryPage } from "@/api/templateLibraryEndpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateCatalogTab } from "./TemplateCatalog";

afterEach(cleanup);

function aRow(overrides: Partial<TemplateCatalogRow> = {}): TemplateCatalogRow {
  return {
    code: "dunning",
    name: "Past-due reminder",
    category: "collections",
    category_source: "cr_007",
    kind: "Print",
    variants: 1,
    used_by: "Nothing yet",
    edited: null,
    edited_at: null,
    group: "printable",
    channel: "pdf_print",
    catalog_unavailable: null,
    body_unavailable: null,
    has_published: true,
    ...overrides,
  };
}

const NOTE_ROWS: TemplateCatalogRow[] = [
  aRow(),
  aRow({ code: "writeoff_notice", name: "Write-off notice" }),
];

/** The OTHER store. One template, which is what a seeded tenant actually has —
 *  billing seeds exactly one fallback bill template (DEF-123). */
const LIBRARY: TemplateLibraryPage = {
  results: [
    {
      kind: "bill",
      key: "BT-1",
      name: "Standard bill",
      content_model: "layout_choice",
      editor: "layout-chooser",
      live_version: 1,
      version_count: 1,
      edited: "2026-08-30",
    },
  ],
  count: 1,
  kinds: ["notification", "bill"],
};

function aPage(overrides: Partial<TemplateCatalogPage> = {}): TemplateCatalogPage {
  return {
    count: NOTE_ROWS.length,
    results: NOTE_ROWS,
    page: 1,
    per: 50,
    categories: [{ key: "collections", count: 2 }],
    columns: [
      { key: "name", always: true },
      { key: "category", always: false },
      { key: "kind", always: false },
      { key: "variants", always: false },
      { key: "used_by", always: false },
      { key: "edited", always: false },
    ],
    page_sizes: [50, 100, 200, 500, 1000],
    can_edit: true,
    cannot_edit_reason: null,
    create_action: "variant",
    create_action_reason: "A template CLASS is platform vocabulary. OQ-253.",
    ...overrides,
  };
}

function renderCatalog({
  entry = "/",
  library = LIBRARY,
}: { entry?: string; library?: TemplateLibraryPage } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["template-catalog", "", "", "name", 1, 50, "asc"], aPage());
  client.setQueryData(["template-library", "bill"], library);
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <TemplateCatalogTab readOnly={false} client={{} as never} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-048 E9 — ONE Templates screen over two stores (BR-NOT-026)", () => {
  it("lists the bill template beside the letters, in the same table", () => {
    renderCatalog();
    // Both stores, one list. The letters the utility sends…
    expect(screen.getByTestId("template-name-dunning")).toBeInTheDocument();
    // …and the layout its bills print on, which used to be a second panel.
    expect(screen.getByTestId("template-name-bill:BT-1")).toBeInTheDocument();
  });

  it("says on every row which KIND of template it is", () => {
    /* ⚠ AMENDED BY CR-199-BRC10 F1. The Kind column left with the redesign
       (`01-list.png` draws Template · Channels · Category · Languages · …).
       A letter says what it is by its purpose line and its channel; the bill
       layout — the one row whose kind is not obvious — says *Bill* under its
       name and *Letter* as its channel, and its letter-only columns say *Not
       applicable* rather than a blank (DEF-163). */
    renderCatalog();
    expect(screen.getByTestId("template-purpose-dunning")).toBeInTheDocument();
    expect(screen.queryByTestId("template-kind-dunning")).not.toBeInTheDocument();
    expect(screen.getByTestId("template-kind-bill:BT-1")).toHaveTextContent("Bill");
    expect(screen.getByTestId("template-channel-bill:BT-1")).toHaveTextContent("Letter");
  });

  it("lists BOTH stores, and draws no one-page sentence under them", () => {
    renderCatalog();
    // Two letters plus one bill template, all on the one table.
    expect(screen.getAllByTestId(/^template-name-/)).toHaveLength(3);
    // DEF-NOT-10673: "All N templates fit on one page…" was rationale
    // (B14 rule 33) and image 01 draws nothing under the table.
    expect(screen.queryByTestId("template-onepage")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("fit on one page");
  });

  it("pages by the SERVER's count, so a second page of templates is reachable (DEF-NOT-10674)", () => {
    // 87 classes at 50 a page: the footer must say so, and the bill layout
    // rides on the LAST page only. It read "1–3 of 3" and stopped at page 1.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    client.setQueryData(["template-catalog", "", "", "name", 1, 50, "asc"], aPage({ count: 87 }));
    client.setQueryData(
      ["template-catalog", "", "", "name", 2, 50, "asc"],
      aPage({ count: 87, page: 2, results: [aRow({ code: "zz_last", name: "Write-off notice" })] }),
    );
    client.setQueryData(["template-library", "bill"], LIBRARY);
    const view = (entry: string) =>
      render(
        <QueryClientProvider client={client}>
          <ToastProvider>
            <MemoryRouter initialEntries={[entry]}>
              <TemplateCatalogTab readOnly={false} client={{} as never} />
            </MemoryRouter>
          </ToastProvider>
        </QueryClientProvider>,
      );
    view("/");
    expect(document.querySelector(".table-pager-range")).toHaveTextContent("1–50 of 88");
    expect(screen.queryByTestId("template-name-bill:BT-1")).not.toBeInTheDocument();
    cleanup();
    view("/?page=2");
    expect(document.querySelector(".table-pager-range")).toHaveTextContent("51–88 of 88");
    expect(screen.getByTestId("template-name-zz_last")).toBeInTheDocument();
    expect(screen.getByTestId("template-name-bill:BT-1")).toBeInTheDocument();
  });

  it("a bill layout answers a search by its name and no category at all (DEF-NOT-10675)", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    const one = aPage({ count: 1, results: [aRow({ code: "service_restored", name: "Service restored" })] });
    client.setQueryData(["template-catalog", "restored", "", "name", 1, 50, "asc"], one);
    client.setQueryData(["template-catalog", "standard", "", "name", 1, 50, "asc"], aPage({ count: 0, results: [] }));
    client.setQueryData(["template-catalog", "", "collections", "name", 1, 50, "asc"], one);
    client.setQueryData(["template-library", "bill"], LIBRARY);
    const view = (entry: string) =>
      render(
        <QueryClientProvider client={client}>
          <ToastProvider>
            <MemoryRouter initialEntries={[entry]}>
              <TemplateCatalogTab readOnly={false} client={{} as never} />
            </MemoryRouter>
          </ToastProvider>
        </QueryClientProvider>,
      );
    view("/?q=restored");
    expect(screen.getByTestId("template-name-service_restored")).toBeInTheDocument();
    expect(screen.queryByTestId("template-name-bill:BT-1")).not.toBeInTheDocument();
    cleanup();
    view("/?q=standard");
    expect(screen.getByTestId("template-name-bill:BT-1")).toBeInTheDocument();
    cleanup();
    view("/?f.category=collections");
    expect(screen.getByTestId("template-name-service_restored")).toBeInTheDocument();
    expect(screen.queryByTestId("template-name-bill:BT-1")).not.toBeInTheDocument();
  });

  it("filters to ONE kind from the URL, per BR-SHL-011's `f.<name>` grammar", () => {
    renderCatalog({ entry: "/?f.template_kind=bill" });
    expect(screen.getByTestId("template-name-bill:BT-1")).toBeInTheDocument();
    expect(screen.queryByTestId("template-name-dunning")).not.toBeInTheDocument();
  });

  it("filters the other way too, so the bill rows can be set aside", () => {
    renderCatalog({ entry: "/?f.template_kind=notification" });
    expect(screen.getByTestId("template-name-dunning")).toBeInTheDocument();
    expect(screen.queryByTestId("template-name-bill:BT-1")).not.toBeInTheDocument();
  });

  it("opens the LAYOUT CHOOSER for a bill row — the editor that suits it", () => {
    renderCatalog({ entry: "/?template=bill:BT-1" });
    // The chooser is `BillLayoutTab`, reached from the one list instead of
    // sitting underneath it. Its own payload is not seeded here, so it draws
    // its loading state; what this pins is that the BILL editor opened and the
    // notification detail did not.
    expect(screen.getByTestId("bill-layout-back")).toBeInTheDocument();
    expect(screen.queryByTestId("templates-title-row")).not.toBeInTheDocument();
  });

  it("keeps drawing the whole list when the other store cannot be read", () => {
    // A person who came here to edit a disconnection letter must not lose the
    // list because the bill-template read was refused (BR-SHL-010's posture:
    // what cannot be answered is not drawn, and nothing else is taken down).
    renderCatalog({ library: { results: [], count: 0, kinds: [] } });
    expect(screen.getByTestId("template-name-dunning")).toBeInTheDocument();
    expect(screen.queryByTestId("template-name-bill:BT-1")).not.toBeInTheDocument();
  });
});
