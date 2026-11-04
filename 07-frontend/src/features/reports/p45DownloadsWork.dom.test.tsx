// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  P4.5 (Finance blueprint p017) — "enable the five downloads, AND
//          DELETE the sentences P2.5 corrected, now that they are not merely
//          false but unnecessary". The phase's own DONE WHEN is *"every
//          download control in Finance either works or is disabled for a
//          reason that is true"*.
// Rules:   B14 rule 33 (RATIONALE is ZERO words on screen — a *why* sentence
//          is REMOVED, never shortened) · B14 rule 43 (a piece of UI is built
//          as a COMPONENT) · BR-SHL-025 (a control this deployment cannot
//          honour renders disabled WITH its reason — which is why deleting the
//          reason requires the control to WORK) · BR-REP-018 / IS-11 ·
//          CLAUDE.md hard-won law 2, BOTH directions
//          Screens: S59 · S60 · the customer statement
// ───────────────────────────────────────────────────────
//
// **THIS IS THE TEST HARD-WON LAW 2 ASKS FOR AND WHICH DID NOT EXIST.** The law:
//
//     WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD EXPIRES,
//     in the same commit … A hold with no such test is a promise nobody is
//     keeping.
//
// Three Finance report downloads were held behind `reports.export.reason` for
// six weeks. The sentence was corrected twice — once on 2026-09-24 morning by
// `P2.5`, because it blamed a service that was running — and each correction
// made the hold LOOK maintained while leaving it in place. Nothing anywhere
// asked *has the thing it was waiting for arrived?*
//
// `apps/ledger/finance_exports.py` registered all three that afternoon. These
// cases are what goes red if anybody puts the hold back, and they assert the
// two halves separately, because they can fail independently:
//
//   1 · **THE CONTROL IS PRESSABLE** — not merely present. A disabled button is
//       in the DOM and `getByRole` finds it happily; `DEF-CWP-3925` is a live
//       screen behind a dead control passing 391 cases.
//   2 · **THE REFUSAL SENTENCE IS GONE FROM THE SCREEN** — B14 rule 33. Asserted
//       against the CATALOGUE's own text rather than a transcription, so it
//       cannot pass by the string being reworded somewhere else.
//   3 · **AND THE KEYS ARE RETIRED FROM ALL ELEVEN CATALOGUES** — a sentence no
//       screen renders but every catalogue still holds is the next lane's
//       invitation to render it again.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import { LOCALE_REGISTRY } from "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";
import type { ByPremisesResponse, MyPermissions, SessionUser } from "@/api/endpoints";
import { ByPremisesReportPage } from "./ByPremisesReportPage";
import { BY_PREMISES_ROUTE } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

/** The three sentences `P4.5` deletes. Named by KEY, checked by VALUE. */
const RETIRED_KEYS = [
  "reports.export.reason",
  "finance.gl.exportUnavailable",
  "finance.taxes.reportUnavailable",
] as const;

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
  permissions: [
    { code: "reports", label: "Reports", access: "Full" },
    { code: "finance", label: "Finance", access: "Full" },
  ],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

const REPORT: ByPremisesResponse = {
  basis: "posting",
  currency: "USD",
  period: { start: PERIOD.start, end: PERIOD.end },
  available: true,
  rows: [
    {
      premises_id: "p1",
      premises_name: "500 Main St",
      units: null,
      services: [],
      billed: "247.8700",
      collected: "247.8700",
      owed: "0.0000",
      collection_pct: null,
    },
  ],
  kpis: { premises: 1, billed: "247.8700", collected: "247.8700", owed: "0.0000" },
  unattributed_billed: "0.0000",
  unattributed_collected: "0.0000",
  unavailable: [],
};

/** Records every POST so *"the button actually calls the export"* is evidence. */
function serverWith(posted: { path: string; body: unknown }[]): ApiClient {
  const get = async (path: string) => {
    if (path.includes("by_premises")) return { data: REPORT, status: 200 };
    return { data: {}, status: 200 };
  };
  const post = async (path: string, body: unknown) => {
    posted.push({ path, body });
    return { data: { job_id: "j1", status_url: "/jobs/j1" }, status: 202 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    request: get,
    get,
    post,
    put: write,
    patch: write,
    delete: write,
  } as unknown as ApiClient;
}

async function settle(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

/**
 * The download button, once the report behind it has loaded.
 *
 * ⚠ **A SINGLE `settle()` WAS NOT ENOUGH AND THE FAILURE WAS ORDER-DEPENDENT.**
 * Run alone the file passed; run after the ledger suites the report query had
 * not resolved by the first macrotask and the button was still legitimately
 * disabled — so the case read as *the hold is still on* over a screen that is
 * fine. That is a check whose verdict depends on its neighbours, which trains
 * a reader to dismiss it as flaky, and it is the same shape as `DEF-SHL-6555`
 * one layer over.
 *
 * `waitFor` STILL FAILS — it times out and reports the assertion — so this
 * removes the timing flake without weakening what is being asserted.
 */
async function enabledDownload(): Promise<HTMLButtonElement> {
  return await waitFor(() => {
    const button = screen.getByRole("button", {
      name: i18n.t("download.csv"),
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    return button;
  });
}

/** Mounted under the REAL `/:tenant/…` pattern — hard-won law 2's fixture clause. */
function open(route: string, element: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const router = createMemoryRouter([{ path: `/:tenant${route}`, element }], {
    initialEntries: [`/${TENANT}${route}`],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P4.5 — the held download works, and its sentence is gone", () => {
  it("the download control is PRESSABLE, not merely present", async () => {
    const posted: { path: string; body: unknown }[] = [];
    open(BY_PREMISES_ROUTE, <ByPremisesReportPage client={serverWith(posted)} />);
    await settle();

    // ⚠ PRESENCE IS NOT THE ASSERTION. A disabled button is in the DOM and
    // `getByRole` finds it; that is exactly how a live screen hid behind a dead
    // control on the portal front page while 391 cases passed.
    const button = await enabledDownload();
    expect(button.disabled).toBe(false);
  });

  it("pressing it asks the server for the registered resource", async () => {
    const posted: { path: string; body: unknown }[] = [];
    open(BY_PREMISES_ROUTE, <ByPremisesReportPage client={serverWith(posted)} />);
    await settle();

    // ⚠ `fireEvent`, not `node.click()`. React attaches its listeners at the
    // root and `HTMLElement.click()` dispatches an event `jsdom` delivers
    // before React's synthetic system is ready to see it — the handler simply
    // does not run, the recorder stays empty, and the case reads as *the
    // button does nothing* when the button is fine.
    const button = await enabledDownload();
    await act(async () => {
      fireEvent.click(button);
    });
    await settle();

    expect(posted).toHaveLength(1);
    expect(posted[0].path).toBe("/exports");
    const body = posted[0].body as { resource: string; filters: Record<string, string> };
    // The resource `apps/ledger/finance_exports.py` registers, spelled the
    // server's way. `by-premises` is the URL segment and is a different
    // vocabulary — DEF-131 is what happens when one constant serves both.
    expect(body.resource).toBe("by_premises");
    // The file's window is the SCREEN's window, so the two cannot disagree.
    expect(body.filters).toEqual({ from: PERIOD.start, to: PERIOD.end });
  });

  it("no refusal sentence renders anywhere on the screen (B14 rule 33)", async () => {
    open(BY_PREMISES_ROUTE, <ByPremisesReportPage client={serverWith([])} />);
    await settle();

    // Compared against the catalogue's OWN historical text rather than a
    // transcription, so a reworded sentence elsewhere cannot make this pass.
    const gone = "Downloads are not built yet";
    expect(document.body.textContent ?? "").not.toContain(gone);
    expect(document.body.textContent ?? "").not.toContain("no download");
  });

  it("the three retired keys are absent from ALL ELEVEN catalogues", () => {
    // A sentence no screen renders but every catalogue still holds is the next
    // lane's invitation to render it again. Rule 33 removes rationale; it does
    // not leave it lying about.
    for (const entry of LOCALE_REGISTRY) {
      const catalog = entry.catalog as Record<string, string>;
      for (const key of RETIRED_KEYS) {
        expect(catalog[key], `${key} still in ${entry.code}`).toBeUndefined();
      }
    }
  });

  it("the eleven catalogues are the eleven, so the check above has a scope", () => {
    // ⚠ A loop over an EMPTY registry passes every assertion inside it. That
    // is hard-won law 7's "reports zero over a scope it silently excludes",
    // and it is one line to rule out.
    expect(LOCALE_REGISTRY).toHaveLength(11);
  });
});
