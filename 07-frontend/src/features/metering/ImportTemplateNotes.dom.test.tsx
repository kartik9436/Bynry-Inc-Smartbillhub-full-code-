// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-1077 — the meters template gave an operator no way to know what
//          to put in the Unit column. PO verbatim 2026-08-27: "when we add
//          assets we have to tie them to units; and in CSV file that we
//          download there is not unit ID or unit name that we can provide -
//          what about this". The header was our field name (`unit_ref`), the
//          three accepted shapes lived in two Python docstrings, and on a
//          tenant with no units the worked cell shipped blank — which was the
//          product saying "you have no units" in the one way nobody can read.
//          DEF-965 — the sibling half: a refusal with nothing to quote.
// Screens: WFL-01 stage 1 (the download), and the refusal strip above it
// Rules:   BR-AST-045 (a blank unit is lawful and loads to inventory — so the
//          blank column is NOT a bug to fix by inventing a number) ·
//          BR-CUS-047 (build order: a row naming a missing unit is an error,
//          never an auto-create) · DEF-332 (no internal rule id on a user's
//          screen) · B14 rule 21 (Tailwind utilities only; this file adds none)
// ───────────────────────────────────────────────────────
/**
 * **EVERY ASSERTION HERE READS RENDERED OUTPUT**, because that is the only
 * kind that could catch what this fixes. The server has declared `help` on the
 * unit column since 2026-08-27 and `blank_means` on it since CR-028; both were
 * typed, both were served, and `blank_means` has never been drawn anywhere at
 * all. A test that checked a prop would pass on a build where no operator ever
 * sees the sentence — hard-won law 2, and the reason `ImportPlanColumn.dom`
 * next door is written the same way.
 *
 * ⚠ **AND THE STAGE MATTERS AS MUCH AS THE SENTENCE.** These same words were
 * already drawn — at stage 2, on the mapping screen. By then the operator has
 * invented a format and filled in every row. Stage 1 is the screen that hands
 * over the file, so it is the only stage where the words change what somebody
 * types. `toStageOne` never advances the wizard, deliberately.
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

/** The server's own sentence for the unit column (`_asset_column`'s `help_text`
 *  on `assets_meters`) — copied, never paraphrased, because the screen renders
 *  the server's words and a paraphrase here would test the paraphrase. */
const UNIT_HELP =
  "The unit's NUMBER (U-00101), or the premises and the unit together " +
  "(P-00101 · A), or just the unit label when only one unit in this utility " +
  "carries it. Leave it blank and the meter loads into inventory — on file, " +
  "but unable to take a reading or be billed until someone assigns it.";

/** `_with_unit_readiness`' sentence, stamped only when the tenant has none. */
const NO_UNITS =
  "There are no units in this utility yet, so this column has nothing to " +
  "name. Import Premises first, then Units, then run this import again — a " +
  "unit named here has to exist already.";

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function notesClient(blankReason: string): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === "/imports/sample?target=assets_meters") {
        return ok({
          target: "assets_meters",
          filename: "assets_meters_sample.csv",
          columns: [
            {
              target: "unit_ref",
              label: "Unit",
              required: false,
              help: UNIT_HELP,
              blank_reason: blankReason,
            },
          ],
        } as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(): Promise<ApiResponse<T>> => {
      throw new Error("stage 1 must not post");
    },
  } as unknown as ApiClient;
}

function mount(client: ApiClient) {
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
              element={<ImportWorkflowPage target="assets_meters" client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

it("def1077__stage_1_says_what_the_Unit_column_takes_BEFORE_the_file_is_filled_in", async () => {
  const { container } = mount(notesClient(""));

  const note = await waitFor(() => {
    const found = container.querySelector<HTMLElement>('[data-template-note="unit_ref"]');
    expect(found).not.toBeNull();
    return found as HTMLElement;
  });
  const text = note.textContent ?? "";
  // The header an operator matches against their own spreadsheet…
  expect(text).toContain("Unit");
  // …and the three shapes `resolve_unit_ref` actually accepts.
  expect(text).toContain("NUMBER");
  expect(text).toContain("premises and the unit together");
  expect(text).toContain("just the unit label");
  // DEF-332 — no internal rule id reaches a utility's screen.
  expect(text).not.toContain("BR-");
  expect(text).not.toContain("DEF-");
  // A tenant that HAS units is told nothing about build order.
  expect(container.querySelector('[data-template-blank-reason="unit_ref"]')).toBeNull();
});

it("def1077__a_utility_with_no_units_is_told_so_and_told_what_to_do_first", async () => {
  const { container } = mount(notesClient(NO_UNITS));

  const reason = await waitFor(() => {
    const found = container.querySelector<HTMLElement>(
      '[data-template-blank-reason="unit_ref"]',
    );
    expect(found).not.toBeNull();
    return found as HTMLElement;
  });
  const text = reason.textContent ?? "";
  expect(text).toContain("no units in this utility yet");
  // The build order, in the order it has to be run.
  expect(text.indexOf("Premises")).toBeLessThan(text.indexOf("Units"));
  expect(text).toContain("Premises");
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-965 · a refusal the server never answered still carries a reference
// ══════════════════════════════════════════════════════════════════════════
//
// `DEF-965` and `DEF-1080` are one production failure reported twice, and
// neither could be diagnosed: the mechanism was a gunicorn worker killed at
// sixty seconds (`DEF-1075`), so Django formed no response, the envelope had no
// `trace_id`, and the refusal strip said "Something went wrong. Nothing was
// saved — try again." with nothing to quote. `diagnosticOf` prints the server's
// short reference when there is one; this is the case where there is not.

it("def965__a_gateway_failure_with_no_envelope_still_gives_the_operator_a_reference", async () => {
  const user = userEvent.setup();
  const sent = "5F2B-9C1D";
  const client = {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === "/imports/sample?target=assets_meters") {
        return ok({
          target: "assets_meters",
          filename: "assets_meters_sample.csv",
          columns: [],
        } as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    // The shape a killed worker produces: a gateway page, not the envelope.
    post: async <T,>(): Promise<ApiResponse<T>> => {
      throw new ApiError(502, { code: null, message_key: UNEXPECTED_ERROR_KEY }, null, sent);
    },
  } as unknown as ApiClient;

  const { container } = mount(client);
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(
    input,
    new File(["METER_NO,SERVICE\nM-9001,water\n"], "meters.csv", { type: "text/csv" }),
  );
  const advance = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(advance).toBeEnabled());
  await user.click(advance);

  await screen.findByText(/Something went wrong\. Nothing was saved/i);
  const diagnostic = await waitFor(() => {
    const found = container.querySelector<HTMLElement>('[data-diagnostic="import"]');
    expect(found).not.toBeNull();
    return found as HTMLElement;
  });
  const text = diagnostic.textContent ?? "";
  expect(text).toContain("HTTP 502");
  // THE POINT: something short enough to read down a telephone.
  expect(text).toContain(`ref ${sent}`);
  expect(text).not.toContain("BR-");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-1077 · DEF-965 (PO reports 2026-08-27, verbatim in Trace) ·
//         BR-AST-045 · BR-CUS-047 · DEF-332 · DEF-771's posture
// generated: 2026-08-28 by the meters-template lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · B14 rule 21 — this file adds no class at all
// exceptions: E1 the DEF-965 case drives ONE failure shape (a 502 whose body
//         is not the envelope). A thrown TypeError from fetch reaches the same
//         render path through the same `sentRef` and is not separately driven.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
