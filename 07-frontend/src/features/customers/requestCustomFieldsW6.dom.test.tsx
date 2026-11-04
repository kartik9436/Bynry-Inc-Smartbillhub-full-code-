// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W6 — the utility's own fields on the staff New
//          Request, the request's Applicant tab and the Approve window.
// Rules:   PO 2026-10-02 Part 2 row 15 · gap 2 (*"Request detail always shows
//          the request's copy of every intake field"*) · gap 3, RULED C
//          (*"Existing: Metal · Requested: Tile side by side; the EXISTING
//          value is pre-selected; the clerk picks"*) · BR-TEN-052 (an edit
//          sends only what changed)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import i18n from "@/i18n";

import { ApproveChecksModal } from "./ApproveChecksModal";
import { RequestCustomFieldCopy } from "./RequestCustomFieldCopy";
import {
  capturePayload,
  changedCapturePayload,
  emptyCaptureForm,
} from "./ServiceRequestCapturePage";
import {
  RequestCustomFieldsDetail,
  emptyRequestCustom,
  hydrateRequestCustom,
} from "./requestCustomFields";
import type { RequestCustomFieldCopyBlock, ServiceRequestDetail } from "./serviceRequestEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const NS = "customers.serviceRequest.customFields";

afterEach(cleanup);

function roof(over: Partial<CustomFieldRegistryEntry> = {}): CustomFieldRegistryEntry {
  return {
    id: "cf-roof",
    key: "roof_material",
    label: "Roof Material",
    help_text: "",
    data_type: "select",
    options: ["Metal", "Tile", "Shingle"],
    is_required: false,
    display_order: 1,
    placement: { REQUEST_NEW: "input" },
    ...over,
  };
}

/** A registry that answers per (entity, screen, mode) — the shape the kit asks. */
function registryClient(answer: (q: Record<string, unknown>) => CustomFieldRegistryEntry[]): ApiClient {
  return {
    get: vi.fn((path: string, options?: { query?: Record<string, unknown> }) => {
      if (path === "/custom-fields") {
        const q = options?.query ?? {};
        return Promise.resolve({ data: { entity: q.entity, fields: answer(q) } });
      }
      return Promise.resolve({ data: {} });
    }),
  } as unknown as ApiClient;
}

function wrap(node: React.ReactNode) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {node}
    </QueryClientProvider>
  );
}

describe("CR-161 W6 · what Staff New Request sends", () => {
  it("a create carries only the answered fields, and no key at all when nothing was typed", () => {
    expect(capturePayload(emptyCaptureForm())).not.toHaveProperty("custom_data");
    const form = {
      ...emptyCaptureForm(),
      custom: { ...emptyRequestCustom(), premises: { roof_material: "Tile", gate: "" } },
    };
    expect(capturePayload(form).custom_data).toEqual({ premises: { roof_material: "Tile" } });
  });

  it("an edit sends only the changed key — a stored answer to a field switched off is never re-sent", () => {
    const saved = {
      ...emptyCaptureForm(),
      custom: hydrateRequestCustom({ premises: { roof_material: "Tile", retired_field: "x" } }),
    };
    const next = {
      ...saved,
      custom: { ...saved.custom, premises: { ...saved.custom.premises, roof_material: "Metal" } },
    };
    expect(changedCapturePayload(saved, next)).toEqual({
      custom_data: { premises: { roof_material: "Metal" } },
    });
    // Nothing changed → nothing about custom fields at all.
    expect(changedCapturePayload(saved, saved)).toEqual({});
    // A cleared answer is sent as null, which the server clears.
    const cleared = { ...saved, custom: { ...saved.custom, premises: { ...saved.custom.premises, roof_material: "" } } };
    expect(changedCapturePayload(saved, cleared)).toEqual({
      custom_data: { premises: { roof_material: null } },
    });
  });
});

describe("CR-161 W6 · Request detail shows the request's copy (gap 2)", () => {
  it("a field typed on Staff New Request is shown even when nothing is placed View on Request detail", async () => {
    const client = registryClient((q) =>
      q.entity === "premises" && q.screen === "REQUEST_NEW" && q.mode === "input" ? [roof()] : [],
    );
    render(
      wrap(
        <RequestCustomFieldsDetail
          data={{ premises: { roof_material: "Tile" } }}
          formatDate={(iso) => iso}
          client={client}
        />,
      ),
    );
    await waitFor(() => expect(document.body.textContent).toContain("Roof Material"));
    expect(document.body.textContent).toContain("Tile");
    expect(document.body.textContent).toContain(t(`${NS}.heading.premises`));
    // Each field once, even when it is also placed View there.
  });

  it("CR-161 W7 (DEF-CUS-9214): a field asked ONLY on the portal is shown too", async () => {
    // Placed nowhere but *Ask the customer*: no Request detail View, no Staff
    // New Request Input. The customer's answer is on the request's copy and
    // must be on its page.
    const client = registryClient((q) =>
      q.entity === "premises" && q.screen === "PORTAL_NEW_SERVICE" && q.mode === "input"
        ? [roof({ placement: { PORTAL_NEW_SERVICE: "input" } })]
        : [],
    );
    render(
      wrap(
        <RequestCustomFieldsDetail
          data={{ premises: { roof_material: "Tile" } }}
          formatDate={(iso) => iso}
          client={client}
        />,
      ),
    );
    await waitFor(() => expect(document.body.textContent).toContain("Roof Material"));
    expect(document.body.textContent).toContain("Tile");
  });

  it("a field placed both ways is listed once", async () => {
    const client = registryClient((q) => (q.entity === "premises" ? [roof()] : []));
    render(
      wrap(
        <RequestCustomFieldsDetail
          data={{ premises: { roof_material: "Tile" } }}
          formatDate={(iso) => iso}
          client={client}
        />,
      ),
    );
    await waitFor(() => expect(document.body.textContent).toContain("Roof Material"));
    expect(document.querySelectorAll("dt").length).toBe(1);
  });

  it("a utility with no fields sees nothing at all", async () => {
    const client = registryClient(() => []);
    const { container } = render(
      wrap(<RequestCustomFieldsDetail data={{}} formatDate={(iso) => iso} client={client} />),
    );
    await waitFor(() => expect(client.get).toHaveBeenCalled());
    expect(container.querySelector("section")).toBeNull();
  });
});

const BLOCKS: RequestCustomFieldCopyBlock[] = [
  {
    entity: "accounts",
    target: null,
    rows: [
      {
        key: "visit_window",
        label: "Visit window",
        data_type: "text",
        requested: "Mornings",
        existing: null,
        state: "no_target",
        default_pick: null,
      },
    ],
  },
  {
    entity: "premises",
    target: { label: "P-00012" },
    rows: [
      {
        key: "roof_material",
        label: "Roof Material",
        data_type: "select",
        requested: "Tile",
        existing: "Metal",
        state: "conflict",
        default_pick: "existing",
      },
      {
        key: "gate_code",
        label: "Gate code",
        data_type: "text",
        requested: "4471",
        existing: null,
        state: "copy",
        default_pick: null,
      },
    ],
  },
];

describe("CR-161 W6 · the Approve window's side-by-side pick (R5, RULED C)", () => {
  it("draws Existing: Metal · Requested: Tile with Existing pre-selected, and reports the clerk's pick", () => {
    const onPick = vi.fn();
    render(<RequestCustomFieldCopy blocks={BLOCKS} picks={{}} onPick={onPick} />);
    const conflict = document.querySelector('[data-copy-row="roof_material"]') as HTMLElement;
    expect(conflict).toHaveAttribute("data-copy-state", "conflict");
    const existing = conflict.querySelector('[data-segment="existing"]') as HTMLElement;
    const requested = conflict.querySelector('[data-segment="requested"]') as HTMLElement;
    expect(existing).toHaveTextContent("Metal");
    expect(requested).toHaveTextContent("Tile");
    expect(existing).toHaveAttribute("aria-checked", "true");
    expect(requested).toHaveAttribute("aria-checked", "false");
    fireEvent.click(requested);
    expect(onPick).toHaveBeenCalledWith("premises", "roof_material", "requested");
    // A key with no existing value is copied, and says so.
    expect(document.querySelector('[data-copy-row="gate_code"]')).toHaveTextContent(
      t(`${NS}.state.copy`, { value: "4471" }),
    );
    // A record that does not exist yet is named, and its answer stays put.
    expect(document.querySelector('[data-copy-entity="accounts"]')).toHaveTextContent(
      t(`${NS}.targetNone.accounts`),
    );
    expect(document.querySelector('[data-copy-entity="premises"]')).toHaveTextContent("P-00012");
  });

  it("the pick travels with the approval", async () => {
    const onSubmit = vi.fn(() => Promise.resolve({ ok: true } as const));
    const detail = {
      header: { request_no: "SR-26-0050", applicant: "Rivera, Elena" },
      actions: {},
      fees: {
        quoted: { amount: "0.0000", display: "0.00", currency: "USD" },
        collected: { amount: "0.0000", display: "0.00", currency: "USD" },
        outstanding: { amount: "0.0000", display: "0.00", currency: "USD" },
      },
      decision: {
        options: [],
        commit: { outcome: "move_in" },
        what_approving_will_do: {
          move_in: {
            window: { submit: "customers.serviceRequest.approveChecks.submit.move_in", lines: [] },
            conditions: { clear: 0, total: 0, blocking: [], outstanding: [], conditions: [] },
          },
        },
      },
      custom_field_copy: BLOCKS,
    } as unknown as ServiceRequestDetail;
    render(<ApproveChecksModal detail={detail} t={t} onClose={() => undefined} onSubmit={onSubmit} />);
    fireEvent.click(
      document.querySelector('[data-copy-row="roof_material"] [data-segment="requested"]') as Element,
    );
    fireEvent.click(document.querySelector('[role="dialog"] button[type="submit"]') as Element);
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit).toHaveBeenCalledWith("move_in", {
      addressIsNew: false,
      customFieldPicks: { premises: { roof_material: "requested" } },
    });
  });

  it("nothing is drawn when the request carries no answers", () => {
    const { container } = render(<RequestCustomFieldCopy blocks={[]} picks={{}} onPick={() => undefined} />);
    expect(container.innerHTML).toBe("");
  });
});
