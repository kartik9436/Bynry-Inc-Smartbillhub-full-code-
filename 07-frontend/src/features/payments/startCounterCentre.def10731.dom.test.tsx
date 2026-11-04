// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-PAY-10731` (tester payments audit L1-11, 2026-10-30, img 21) —
//          *"The tester chose service centre 'Main office' and a float of
//          $100.00. SMART360 answered 'This is required.'"*
// Rules:   B14 rule 10 (required field) · hard-won law 7 (red first)
// ───────────────────────────────────────────────────────
// The select started at `""` with no empty option, so the browser drew the
// first centre while the form held nothing. These cases SUBMIT WITHOUT
// TOUCHING THE SELECT — the clerk's real move, and the one every earlier test
// skipped by firing `change` on it.
//
// RED FIRST: against the tip before the fix, the one-centre case posted
// nothing (the form refused `service_centre`) and the two-centre case found no
// `Choose…` option.
import "@/i18n";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { StartCounterModal } from "./StartCounterModal";

function centre(slug: string, name: string) {
  return {
    slug,
    name,
    address: "101 Main St",
    phone: null,
    directions_note: null,
    allowed_actions: [],
    payment_methods_accepted: [],
    is_shown_to_customers: true,
    position: 1,
    hours: [],
    today: { open: true, opens_at: null, closes_at: null, note: null },
    last_changed_on: null,
  };
}

function client(centres: ReturnType<typeof centre>[]) {
  const posts: Record<string, unknown>[] = [];
  const api = {
    get: async () => ({
      data: { centres, all_actions: [], all_payment_methods: [] },
      status: 200,
      headers: new Headers(),
    }),
    post: async (_path: string, body?: unknown) => {
      posts.push((body ?? {}) as Record<string, unknown>);
      return { data: { code: "CTR-261030-DW" }, status: 200, headers: new Headers() };
    },
  } as unknown as ApiClient;
  return { api, posts };
}

function mount(api: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <StartCounterModal
            onClose={() => {}}
            onStarted={() => {}}
            writeBlockedReason={null}
            timeZone="America/Chicago"
            dateFormat="MM/DD/YYYY"
            client={api}
          />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function fill(container: HTMLElement, id: string, value: string) {
  const field = container.querySelector<HTMLInputElement>(`#${id}`);
  if (field === null) throw new Error(`no #${id}`);
  fireEvent.change(field, { target: { value } });
}

afterEach(cleanup);

describe("DEF-PAY-10731 — Start counter takes the centre the clerk sees", () => {
  it("one centre: it is chosen, and Start posts it without the select being touched", async () => {
    const { api, posts } = client([centre("main-office", "Main office")]);
    const { container } = mount(api);
    const select = await waitFor(() => {
      const found = container.querySelector<HTMLSelectElement>("#service_centre");
      expect(found?.querySelector('option[value="main-office"]')).not.toBeNull();
      return found as HTMLSelectElement;
    });
    await waitFor(() => expect(select.value).toBe("main-office"));
    fill(container, "opening_float", "100.00");
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].service_centre_id).toBe("main-office");
  });

  it("two centres: the select shows Choose… and holds nothing, so what it shows is what it holds", async () => {
    const { api, posts } = client([
      centre("main-office", "Main office"),
      centre("depot", "North depot"),
    ]);
    const { container } = mount(api);
    const select = await waitFor(() => {
      const found = container.querySelector<HTMLSelectElement>("#service_centre");
      expect(found?.querySelector('option[value="depot"]')).not.toBeNull();
      return found as HTMLSelectElement;
    });
    expect(select.value).toBe("");
    const shown = select.options[select.selectedIndex];
    expect(shown.textContent).toBe(i18n.t("payments.counter.start.centreChoose"));
    expect(shown.textContent).not.toBe("Main office");
    fill(container, "service_centre", "depot");
    fill(container, "opening_float", "100.00");
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].service_centre_id).toBe("depot");
  });
});
