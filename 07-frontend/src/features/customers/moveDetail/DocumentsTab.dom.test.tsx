// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 · lane MVI-POLISH
// Defect:   DEF-CUS-9764 — a move-in request's Documents tab drew Document ·
//           Required · File · Uploaded by · State · Actions and read a required
//           document as "No", where image 21 draws Document · Needed · File ·
//           Added with a REQUIRED chip.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a chip on every row would pass a
// "Required is shown" check, so an OPTIONAL row is asserted to carry no chip;
// and a Needed cell read off the uploader's own tick would pass on a fixture
// where that tick is true, so the required row here has `required: false` and
// is required ONLY by the tenant's checklist — the case the photograph showed.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";

import { RequestDocumentsTab } from "./DocumentsTab";

afterEach(cleanup);

const doc = (over: Record<string, unknown>) => ({
  id: "d-1",
  doc_type: "proof_of_identity",
  what_it_proves: null,
  document_number: null,
  name: "photo-id.jpg",
  uploaded_at: "2026-10-03T15:00:00Z",
  uploaded_by_name: "Asha Verma",
  required: false,
  size_bytes: 20480,
  original_size_bytes: null,
  file_present: true,
  content_type: "image/jpeg",
  verification_state: "unverified",
  ...over,
});

function client(): ApiClient {
  return {
    get: async () => ({
      status: 200,
      headers: {},
      data: {
        documents: [
          doc({}),
          doc({ id: "d-2", doc_type: "other", name: "note.pdf", uploaded_by_name: "Dana Whitfield" }),
        ],
        verified: 0,
        attached: 2,
        blocks_creation: false,
        blocks_approval: false,
        outstanding: null,
        checklist_required: ["proof_of_identity"],
      },
    }),
  } as unknown as ApiClient;
}

describe("DEF-CUS-9764 · a request's Documents tab is image 21", () => {
  it("draws Document · Needed · File · Added, a REQUIRED chip from the checklist, and no State or Actions", async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <RequestDocumentsTab requestId="req-14" regional={{ timeZone: "UTC", dateFormat: "MM/DD/YYYY" } as never} client={client()} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(document.querySelectorAll("tbody tr")).toHaveLength(2));
    const heads = Array.from(document.querySelectorAll("thead th")).map((th) => th.textContent?.trim());
    expect(heads).toEqual(["Document", "Needed", "File", "Added"]);
    const [identity, other] = Array.from(document.querySelectorAll("tbody tr")) as HTMLElement[];
    const needed = identity.querySelector("[data-doc-required]") as HTMLElement;
    expect(needed).toHaveTextContent("Required");
    expect(needed).not.toHaveTextContent("No");
    expect(other.querySelector("[data-doc-required]")).toHaveTextContent("—");
    // The file NAME is the link that opens it.
    expect(within(identity).getByRole("button", { name: "photo-id.jpg" })).toBeInTheDocument();
    expect(identity.querySelector("[data-doc-by]")).toHaveTextContent("10/03/2026 · Asha Verma");
  });
});
