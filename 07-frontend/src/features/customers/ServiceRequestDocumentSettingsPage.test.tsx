// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 task 4.13/4.15 — BR-CUS-095's checklist screen.
// Rules:    BR-CUS-095 (PO 2026-08-24, closing OQ-351) — *"We ship with nothing
//           ticked, and a utility that configures nothing blocks nothing."*
// ───────────────────────────────────────────────────────
//
// The assertion that matters most here is that the product ships with **NO
// OPINION**: the grid must render every cell unticked on a fresh tenant, and
// nothing may pre-tick `proof_of_identity`, however reasonable that looks.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import {
  ServiceRequestDocumentSettingsPage,
  cellIndex,
  documentRequirementsKey,
} from "./ServiceRequestDocumentSettingsPage";
import {
  DESIGNED_DOC_TYPES,
  SERVICE_REQUEST_OUTCOMES,
  getDocumentRequirements,
} from "./serviceRequestEndpoints";
import type { DocumentRequirementsGrid } from "./serviceRequestEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The whole 5 × 8 grid, as `document_requirements()` serves it on a tenant
 *  that has never opened this screen. */
function shippedGrid(): DocumentRequirementsGrid {
  return {
    requirements: SERVICE_REQUEST_OUTCOMES.flatMap((requestType) =>
      DESIGNED_DOC_TYPES.map((docType) => ({
        request_type: requestType,
        doc_type: docType,
        required: false,
        configured: false,
        updated_at: null,
      })),
    ),
    ships_unticked: true,
    br_ref: "BR-CUS-095",
  };
}

async function render(grid: DocumentRequirementsGrid): Promise<string> {
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async () =>
      new Response(JSON.stringify(grid), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await queryClient.prefetchQuery({
    queryKey: documentRequirementsKey(),
    queryFn: () => getDocumentRequirements(undefined, client),
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/settings/reference-data/service-request-documents"]}>
        <ServiceRequestDocumentSettingsPage client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** The renderer escapes `&`, `<`, `>`, `"` and `'`; a catalogue string compared
 *  against its own rendered form has to be escaped the same way or a sentence
 *  containing a quotation mark can never match (DEF-685). */
function escapeForMarkup(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

describe("BR-CUS-095 · the document checklist", () => {
  it("serves the WHOLE 5 × 8 grid — a checklist that listed only what was touched could never be ticked", () => {
    const grid = shippedGrid();
    expect(grid.requirements).toHaveLength(40);
    const index = cellIndex(grid.requirements);
    expect(index.get("move_in::proof_of_identity")?.required).toBe(false);
  });

  it("ships ENTIRELY UNTICKED — no helpful pre-tick of proof of identity", async () => {
    const html = await render(shippedGrid());
    // ⚠ THIS ASSERTION USED TO READ `not.toContain("checked")` AND IT WENT RED
    // ON ITS OWN COPY (DEF-685). The panel's explanatory sentence says a
    // document must be "…brought in and **checked** by somebody", and a
    // substring match cannot tell that word from the `checked` ATTRIBUTE on an
    // input — which is the only thing this case is about. A check whose output
    // cannot distinguish pass from fail is worse than no check, because it is
    // trusted; the same lesson CLAUDE.md law 11 records twice about `--stat`.
    // So it pins the ATTRIBUTE, in both the shapes React can emit.
    expect(html).not.toMatch(/<input[^>]*\schecked\b/);
    expect(html).not.toContain('checked=""');
    expect(html).toContain(t("customers.serviceRequest.docSettings.shipsUnticked"));
    // Every cell says *nobody has decided*, which is a different fact from
    // *we said no*.
    expect(html).toContain(t("customers.serviceRequest.docSettings.neverConfigured"));
    expect(html).not.toContain(t("customers.serviceRequest.docSettings.notRequired"));
  });

  it("tells 'nobody has looked' from 'we said no'", async () => {
    const grid = shippedGrid();
    const cell = grid.requirements.find(
      (row) => row.request_type === "move_in" && row.doc_type === "proof_of_identity",
    );
    if (cell !== undefined) {
      // Ticked once and taken back: a `false` row is a tick that was WITHDRAWN,
      // stored and never deleted.
      cell.configured = true;
    }
    const html = await render(grid);
    expect(html).toContain(t("customers.serviceRequest.docSettings.notRequired"));
    expect(html).toContain('data-requirement="move_in::proof_of_identity" data-configured="true"');
  });

  it("the TWO GATES are stated on the screen where somebody decides to tick", async () => {
    const html = await render(shippedGrid());
    expect(html).toContain(t("customers.serviceRequest.docSettings.twoGates"));
  });

  it("the ninth doc type is NOT in the grid — `other` is attachable and never tickable", async () => {
    const html = await render(shippedGrid());
    expect(html).not.toContain('data-requirement="move_in::other"');
    // ⚠ Compare against the ESCAPED render, not the raw catalogue string
    // (DEF-685). This sentence quotes a doc type in curly quotes, and
    // `renderToStaticMarkup` escapes `"` to `&quot;`, so a raw comparison fails
    // on text that is present and correct on screen. Escaping the expectation
    // the same way the renderer escapes the output is what makes the two
    // comparable.
    expect(html).toContain(escapeForMarkup(t("customers.serviceRequest.docSettings.otherIsNotTickable")));
  });

  it("all five request types are columns, `disconnect` included (BR-CUS-091)", async () => {
    const html = await render(shippedGrid());
    for (const outcome of SERVICE_REQUEST_OUTCOMES) {
      expect(html).toContain(t(`customers.serviceRequest.type.${outcome}`));
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.13 · BR-CUS-095
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: vitest✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
