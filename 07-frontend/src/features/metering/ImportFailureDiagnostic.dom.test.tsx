// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-964 — the import wizard's refusal strip printed one sentence and
//          nothing a person could quote, on the ONE screen in this workflow
//          that writes. The PO's stage-4 commit failed behind a clean rehearsal
//          and the whole of what the product said was: "Something went wrong.
//          Nothing was saved — try again."
//          DEF-965 — that commit failure, which consequently could not be
//          diagnosed from the repo at all.
// Screens: WFL-01 (every stage; the strip is drawn once, above the stage body)
// Rules:   BR-SHL-020 (a refusal is rendered whole, never swallowed) · the PO
//          ruling of 2026-08-10 that `diagnosticOf` was built for — "unable to
//          see what is the error on screen - hence as user I'm unable to see
//          what is happening" · DEF-332 (our internal rule ids are NOT put on a
//          utility's screen; the SHORT trace reference is what support reads)
// ───────────────────────────────────────────────────────
/**
 * **THIS IS A WIRING TEST, WHICH IS THE ONLY KIND THAT COULD HAVE CAUGHT IT
 * (hard-won law 2: built is not wired).**
 *
 * `diagnosticOf` has existed since 2026-08-10, is unit-tested, and was wired to
 * `StateFrame` and the public pricing page. Every one of its own tests passed
 * for seventeen days while the import wizard — the only screen in this workflow
 * that writes to the database — called `refusalOf` and nothing else. Nothing
 * anywhere asked whether the sentence an operator actually SAW identified the
 * failure.
 *
 * **RED-FIRST (r11 2d), verbatim.** Copied into a clean `git worktree` of the
 * branch tip — the tree WITHOUT the wiring — and run there:
 *
 *     × def964__a_refusal_the_envelope_cannot_name_still_tells_the_operator…
 *       → expected null not to be null
 *     AssertionError: expected null not to be null
 *      ❯ src/features/metering/ImportFailureDiagnostic.dom.test.tsx:120:26
 *         120|   expect(diagnostic).not.toBeNull();
 *
 * ⚠ **AND THE FIRST EXPECTATION PASSED THERE.** `findByText(/Something went
 * wrong\. Nothing was saved/)` resolved: the generic sentence WAS on screen,
 * exactly as in the PO's screenshot, and it was all there was. That is the
 * defect in one run — the product had a sentence and no facts.
 *
 * The failure driven here is the one that produces that sentence in
 * production: a 502 whose body is not the ratified envelope. `asEnvelope`
 * substitutes `api.error.unexpected` for it, which is byte-for-byte the string
 * the PO photographed.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { ApiError, UNEXPECTED_ERROR_KEY } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";

afterEach(cleanup);

const TENANT = "ottumwa-water-works";
const CSV = "METER_NO,SERVICE\nM-9001,water\n";

/** A gateway answering with an HTML error page — the shape `asEnvelope` cannot
 *  read, and therefore the shape that becomes the generic sentence. */
function gatewayFailureClient(): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(): Promise<ApiResponse<T>> => {
      throw new ApiError(502, { code: null, message_key: UNEXPECTED_ERROR_KEY });
    },
  } as unknown as ApiClient;
}

function mount() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/assets/import`]}>
          <Routes>
            <Route
              path="/:tenant/assets/import"
              element={
                <ImportWorkflowPage target="assets_meters" client={gatewayFailureClient()} />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

it("def964__a_refusal_the_envelope_cannot_name_still_tells_the_operator_WHAT_happened", async () => {
  const user = userEvent.setup();
  const { container } = mount();

  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(input, new File([CSV], "meters.csv", { type: "text/csv" }));
  // The exact accessible name, not a regex: the STAGE BAR also carries the
  // word "Transform" and a loose match found both (the runner's own suite
  // names it the same way, for the same reason).
  const advance = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(advance).toBeEnabled());
  await user.click(advance);

  // 1 · the sentence the PO photographed is still shown — it is a legitimate
  //     catalogue entry and this fix does not remove it.
  await screen.findByText(/Something went wrong\. Nothing was saved/i);

  // 2 · AND the operator now has something to quote. Codes and identifiers
  //     only — never server prose, so TD-16/G14 are untouched — and no
  //     `br_ref`, per the PO's 2026-08-19 ruling (DEF-332).
  const diagnostic = await waitFor(() =>
    container.querySelector('[data-diagnostic="import"]'),
  );
  expect(diagnostic).not.toBeNull();
  expect(diagnostic?.textContent ?? "").toContain("HTTP 502");
  expect(diagnostic?.textContent ?? "").not.toContain("BR-");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-964 (PO report 2026-08-27) · BR-SHL-020 · the 2026-08-10 support
//         -diagnostic ruling · DEF-332 (no rule ids on a user's screen)
// generated: 2026-08-27 by lane ASSETIMPORT
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · B14 rule 21 — the paragraph is Tailwind utilities and
//        `WF.CELL_MUTED`, in a file already on the Route B ledger
// exceptions: E1 this proves the wiring on ONE failure shape (a 502 with a
//         non-envelope body). The other two routes to the same sentence — a
//         thrown TypeError from fetch, and `requireData`'s bare Error on a null
//         body — reach the same render path and are NOT separately driven here.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
