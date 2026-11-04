// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-6898 — 27 of the 46 reports drew the finance ERROR panel
//          over a refusal the product had already written down.
// Covers:  ReportViewerPage (the refusal branch) · reportsShared
//          (unavailableSentence · isNotProducible) · ReportLibraryPage
//          (reasonSentence, now delegating to the same function)
// Rules:   B14 rule 33 (a FACT ≤ 6 words · RATIONALE is ZERO words on screen) ·
//          B14 rule 32 (no internal code in clerk-facing copy) ·
//          BR-REP-024 · hard-won law 6 · hard-won law 7 clause (2)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE CARD AND THE VIEWER SAY THE SAME THING, AND NEITHER SAYS MORE       ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Photographed on the running product at v2.373.0: the catalogue card for
// **Read Completeness** read *"This report cannot be produced yet."* and the
// viewer for the same report, two clicks later, read *"The finance figures
// could not be loaded / Something went wrong on our side. Nothing was saved."*
// — the word *finance* on a meter-reads report, and a fault report over
// something that had not failed.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2):
//   · **Asserting only that the error panel is GONE.** A blank screen, a
//     spinner that never ends and a crashed render all pass that. Every case
//     asserts the SENTENCE that is present, by its exact words.
//   · **Asserting the sentence with the error panel still beside it.** So the
//     refusal cases also assert the finance error heading is ABSENT.
//   · **Turning every failure into a refusal.** A real 500 must still say the
//     product broke, or the next outage reads as an unbuilt report. The last
//     case is that one, and it is the mirror the fix could most easily break.
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportViewerPage } from "./ReportViewerPage";
import { reasonSentence } from "./ReportLibraryPage";
import { REPORTS_ROUTE, unavailableSentence } from "./reportsShared";

afterEach(cleanup);

const t = i18n.getFixedT("en");
const TENANT = "brazosbend";

/** What a clerk reads. Six words — B14 rule 33's cap for a FACT. */
const SENTENCE = "This report cannot be produced yet.";
/** Three words — rule 33's cap for a heading. */
const HEADING = "Report not available";
/** What they must NOT read any more. */
const FAULT_HEADING = "The finance figures could not be loaded";

const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

/** The envelope `apps/reports/api._cannot_be_produced` sends, byte for byte —
 *  including `params.detail`, the engineering prose that must never appear. */
const DETAIL =
  "Read Completeness is one row per ROUTE with a denominator of reads that did " +
  "not happen. The meter_reads dataset produces one row per READ.";

function refusalError(): ApiError {
  return new ApiError(422, {
    code: "BIZ-COMPLETENESS",
    message_key: "reports.library.unavailableGeneric",
    params: {
      key: "read_completeness",
      reason_code: "report_grain_is_not_this_dataset_grain",
      detail: DETAIL,
    },
    field_errors: [],
    br_ref: "BR-REP-024",
    trace_id: "0".repeat(32),
  });
}

function serverFault(): ApiError {
  return new ApiError(500, {
    code: "SYS-INTERNAL",
    message_key: "errors.sys-internal",
    params: {},
    field_errors: [],
    trace_id: "f".repeat(32),
  });
}

function clientThatFails(failure: ApiError): ApiClient {
  const get = async (path: string) => {
    if (path.startsWith("/reports/")) {
      throw failure;
    }
    if (path === "/reports") {
      return {
        data: {
          // The row the clerk just clicked, carrying the name they read on it.
          cards: [
            {
              key: "read_completeness",
              name: "Read Completeness",
              available: false,
              kind: "absent",
              reason_code: "report_grain_is_not_this_dataset_grain",
              reason_detail: DETAIL,
            },
          ],
          groups: [],
          vocabularies: { services: [], bill_types: [], purposes: [] },
        },
        status: 200,
      };
    }
    if (path.startsWith("/lookups/")) {
      return { data: { results: [], count: 0 }, status: 200 };
    }
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    request: get,
    get,
    post: write,
    put: write,
    patch: write,
    delete: write,
  } as unknown as ApiClient;
}

function mountViewer(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  // The REAL path pattern — a bare MemoryRouter leaves `useParams().tenant`
  // undefined and this is not then the screen under test.
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: (
          <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-09-26" />
        ),
      },
    ],
    {
      initialEntries: [
        `/${TENANT}${REPORTS_ROUTE}/read-completeness?f.from=2026-09-01&f.to=2026-09-30`,
      ],
    },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-REP-6898 · a report that cannot be produced says so", () => {
  it("draws the SENTENCE the catalogue card already draws", async () => {
    mountViewer(clientThatFails(refusalError()));
    expect(await screen.findByText(SENTENCE)).toBeTruthy();
    expect(screen.getByText(HEADING)).toBeTruthy();
  });

  it("does NOT tell the clerk the product broke", async () => {
    mountViewer(clientThatFails(refusalError()));
    await screen.findByText(SENTENCE);
    expect(screen.queryByText(FAULT_HEADING)).toBeNull();
    expect(screen.queryByText(/Something went wrong on our side/)).toBeNull();
  });

  it("prints NO rationale and NO internal code — rule 33 and rule 32", async () => {
    mountViewer(clientThatFails(refusalError()));
    await screen.findByText(SENTENCE);
    const page = document.body.textContent ?? "";
    // The server's own prose travels for the log, never to the screen.
    expect(page).not.toContain("meter_reads");
    expect(page).not.toContain("denominator");
    // B14 rule 32: no rule id, no machine code in clerk-facing copy.
    expect(page).not.toContain("BR-REP-024");
    expect(page).not.toContain("BIZ-COMPLETENESS");
    expect(page).not.toContain("report_grain_is_not_this_dataset_grain");
  });

  it("is titled with the report's NAME and never with its slug", async () => {
    // ⚠ B14 rule 31 — no database id is ever the visible value of a field.
    // A refused report has no payload, and only nine of the forty-six keys
    // have an authored `reports.card.<key>.name`, so the page head used to
    // draw **read_completeness** on thirty-odd screens.
    mountViewer(clientThatFails(refusalError()));
    await screen.findByText(SENTENCE);
    const h1 = document.querySelector("h1");
    expect(h1?.textContent?.trim()).toBe("Read Completeness");
    expect(document.body.textContent).not.toContain("read_completeness");
  });

  it("A REAL FAULT STILL READS AS A FAULT — the mirror", async () => {
    mountViewer(clientThatFails(serverFault()));
    expect(await screen.findByText(FAULT_HEADING)).toBeTruthy();
    expect(screen.queryByText(SENTENCE)).toBeNull();
  });
});

describe("DEF-REP-6898 · the card and the viewer resolve ONE sentence", () => {
  it("the card's function and the viewer's are the same function", () => {
    const fromTheCard = reasonSentence(
      {
        key: "read_completeness",
        reason_code: "report_grain_is_not_this_dataset_grain",
      } as never,
      t,
    );
    const fromTheViewer = unavailableSentence("report_grain_is_not_this_dataset_grain", t);
    expect(fromTheViewer).toBe(fromTheCard);
    expect(fromTheViewer).toBe(SENTENCE);
  });

  it("an UNKNOWN reason code falls back to the six words, never to prose", () => {
    expect(unavailableSentence("a_code_nobody_has_authored", t)).toBe(SENTENCE);
    expect(unavailableSentence(null, t)).toBe(SENTENCE);
  });
});
