// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   `DEF-PAY-10140` — the PO opened a second counter the same day and
//           read *"Counter could not load. The counter did not answer."* over
//           a server that HAD answered, with a 422 saying why. The panel
//           hard-coded *did not answer* for every failure.
// Rules:    BR-SHL-020 r2 (the sentence is the catalogue's for the server's
//           `message_key`, never server prose) · hard-won law 7 (run RED on the
//           hard-coded panel first)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";

import { MyCounterPage } from "./MyCounterPage";

afterEach(cleanup);

const TENANT = "brazosbend";
const CODE = "CTR-261013-BS-2";

/** A client whose counter read is REFUSED with the given key, or never answered. */
function refusing(messageKey: string | null): ApiClient {
  return {
    get: async (path: string) => {
      if (path.startsWith("/counters/")) {
        if (messageKey === null) {
          throw new TypeError("Failed to fetch");
        }
        throw new ApiError(422, {
          code: "BIZ-COMPLETENESS",
          message_key: messageKey,
          params: { detail: "engineering prose that must never reach the screen" },
        });
      }
      throw new ApiError(500, { code: null, message_key: "api.error.unexpected" });
    },
  } as unknown as ApiClient;
}

function mount(client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      {/* The real path pattern, so `useParams().counterCode` is the code. */}
      <MemoryRouter initialEntries={[`/${TENANT}/payments/counter/${CODE}`]}>
        <Routes>
          <Route
            path="/:tenant/payments/counter/:counterCode"
            element={
              <MyCounterPage
                client={client}
                writeBlockedReason={null}
                dateFormat="MM/DD/YYYY"
                timeZone="America/Chicago"
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DEF-PAY-10140 — the counter failure panel says what the server said", () => {
  it("renders the server's reason, not 'did not answer', when the server refused", async () => {
    mount(refusing("payments.counter.not_found"));
    await waitFor(() =>
      expect(document.body.textContent).toContain("This counter does not exist."),
    );
    expect(document.body.textContent).toContain("Counter could not load.");
    // ⚠ The half that bites: the right sentence beside the old wrong one would
    // pass the line above and still be the defect.
    expect(document.body.textContent).not.toContain("The counter did not answer.");
    // BR-SHL-020 r2 — server prose never reaches the clerk.
    expect(document.body.textContent).not.toContain("engineering prose");
  });

  it("renders the ambiguity safety net in its own words", async () => {
    mount(refusing("payments.counter.ambiguous"));
    await waitFor(() =>
      expect(document.body.textContent).toContain("Two counters share this code."),
    );
  });

  it("keeps the generic line only when nothing answered at all", async () => {
    mount(refusing(null));
    await waitFor(() =>
      expect(document.body.textContent).toContain("The counter did not answer."),
    );
  });
});
