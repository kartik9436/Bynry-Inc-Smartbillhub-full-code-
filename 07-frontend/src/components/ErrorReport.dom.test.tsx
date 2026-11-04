// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-SHL-6377` — the Product Owner, 2026-09-23, on a failed
//          property sale (*"The sale was not recorded. Nothing changed
//          hands."*): *"Unable to download error report"*.
// Rules:   CLAUDE.md hard-won law 2 (built is not wired — and its fixture
//          lesson: mount a routed component under the REAL path pattern) ·
//          law 7 (proved RED on the unchanged tip before it was trusted
//          green) · B14 rule 31 (no database id as a visible value) · A18 §4
// Screens: `TRF-02` (the transfer wizard's failure panel) · `ACC-01` (a list
//          whose failure panel is one of the 99 `() => undefined` call sites)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **WHY THIS FILE PRESSES THE BUTTON.** `StateFrame.test.tsx` has asserted
// since 2026-08-09 that the failure panel DRAWS *Download error report*, and it
// is `renderToStaticMarkup` — a string cannot be pressed. The button was live,
// labelled and pressable on 101 call sites and did nothing on every one of
// them. So every case here presses it and reads the FILE that comes out.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, asked before they were trusted
// (law 7, habit 2):**
//   * *"a download happened"* alone passes on an empty file, so the file is
//     READ and its lines are matched one by one.
//   * *"the screen id is in the file"* passes on a panel mounted bare, where
//     the router cannot say which screen this is — so the panel is mounted at
//     the real `/:tenant/transfers/new` pattern and the id must come out as
//     `TRF-02`, which only the real address yields.
//   * *"no form value leaks"* passes on a form nobody typed into, so the
//     sensitive values are TYPED, SENT in the request body, and put in the
//     query string and a cookie — every place a careless report could copy
//     them from — and then asserted absent.
//
// ⚠ **PROVED RED ON THE UNCHANGED TIP, IN THE HARNESS THAT RUNS IT.** Against
// `18818920f` (StateFrame's button calling the caller's `() => undefined` and
// the wizard frame's `noop`), `npx vitest run src/components/ErrorReport.dom.test.tsx`
// failed every download case on *"expected createObjectURL to be called"* —
// nothing was downloaded, which is exactly what the PO saw.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { version as APP_VERSION } from "../../package.json";

import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { TextField } from "@/components/FormModal";
import { FailedWithRetry } from "@/components/StateFrame";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome } from "@/components/WizardFrame";
import {
  commitTransfer,
  type TransferCommitPlan,
} from "@/features/customers/transferDisconnectEndpoints";

const TENANT = "brazosbend";
const t = (key: string, options?: Record<string, unknown>): string =>
  i18n.t(key, options) as string;

/** 19:05:30 UTC is 14:05:30 in Chicago on 2026-09-23 (CDT, UTC−5). */
const NOW = new Date("2026-09-23T19:05:30Z");
const CHICAGO = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" as const };

// What a careless report would copy. Each is put somewhere a report COULD
// read it from, and each must be absent from the file.
const BUYER_NAME = "Nadia Okonjo";
const BUYER_TAX_ID = "987-65-4321";
const SEARCHED_FOR = "Hollis";
const SESSION_COOKIE = "sessionid=S3SSION-T0KEN-DO-NOT-LEAK";

// ── The download, caught ───────────────────────────────────────────────────
// jsdom implements neither `URL.createObjectURL` nor a download, so both are
// stood in for: the Blob handed to `createObjectURL` is the file, and the
// anchor's `download` attribute at the moment it is clicked is its name.
let blobs: Blob[] = [];
let clicked: { download: string; href: string }[] = [];

function readBlob(blob: Blob): Promise<string> {
  // jsdom's Blob has no `.text()`; FileReader is the API a browser hands a page.
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  blobs = [];
  clicked = [];
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn((blob: Blob) => {
      blobs.push(blob);
      return `blob:report-${blobs.length}`;
    }),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicked.push({ download: this.download, href: this.href });
  });
  document.cookie = SESSION_COOKIE;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The server's real refusal for a seller that occupies nothing
 *  (`apps/customers/transfers.py:1280`, `BR-CUS-030`), envelope and all.
 *
 * ⚠ **THIS FIXTURE CARRIED A REFUSAL THAT NO LONGER EXISTS UNTIL 2026-09-24,
 * AND THE CASE HAD BEEN RED SINCE `2d23f5a5c` (2.351.0) THAT MORNING.**
 * `from_account_has_no_customer` was RETIRED by `BR-CUS-1081` T1
 * (`DEF-CUS-6387`) — an account with nobody linked is sold, and the seller is
 * the name on the account — and its catalogue entry went with it, correctly.
 * The panel then rendered the raw key where the sentence should be and
 * `getByText` found nothing. **The retirement was right; this fixture was the
 * stale half**, and the case it broke is the ONLY running proof of the
 * behaviour the Product Owner reported (`DEF-SHL-6377`).
 *
 * It is pointed at a refusal the server still raises rather than deleted: what
 * this file proves is that the report carries WHAT FAILED and nothing about
 * WHO, which any real refusal exercises. */
const NO_CUSTOMER_REFUSAL = {
  code: "BIZ_STATE",
  message_key: "customers.transfer.not_an_occupant",
  params: {
    account_no: "AC-2026-00012",
    status: "closed",
    reason: "from_account_is_not_an_occupant",
  },
  field_errors: [],
  br_ref: "BR-CUS-030",
  trace_id: "5f2b9c1d3e4a4b5c8d9e0f1a2b3c4d5e",
};

/**
 * The sale's last step, at the REAL address, failing the way the PO's did.
 *
 * ⚠ The commit goes through the REAL endpoint wrapper and the REAL client, so
 * the request the report describes is the one the product actually sends —
 * `POST /transfers/commit` — and its BODY carries the typed values, which is
 * the place a report that copied "the failed request" would find them.
 */
function SaleFailing() {
  const [buyer, setBuyer] = useState("");
  const [taxId, setTaxId] = useState("");
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async () => json(NO_CUSTOMER_REFUSAL, 409),
  });
  async function commit(): Promise<WizardCommitOutcome> {
    try {
      await commitTransfer(
        { buyer: { full_name: buyer, tax_id: taxId } } as unknown as TransferCommitPlan,
        client,
      );
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: refusalText(t, error) };
    }
  }
  return (
    <WizardFrame
      steps={[
        {
          id: "buyer",
          label: "The buyer",
          content: (
            <>
              <TextField id="buyer-name" label="Buyer's name" value={buyer} onChange={setBuyer} />
              <TextField id="buyer-tax" label="Tax ID" value={taxId} onChange={setTaxId} />
            </>
          ),
        },
      ]}
      commitLabel="Complete the sale ✓"
      commitFailedTitle={t("customers.transfer.commitFailed", {
        defaultValue: "The sale was not recorded. Nothing changed hands.",
      })}
      onCommit={commit}
      onCommitted={() => undefined}
    />
  );
}

function mountSale(): void {
  render(
    <TenantRegionalProvider value={CHICAGO}>
      <MemoryRouter initialEntries={[`/${TENANT}/transfers/new?step=1&q=${SEARCHED_FOR}`]}>
        <Routes>
          <Route path="/:tenant/transfers/new" element={<SaleFailing />} />
        </Routes>
      </MemoryRouter>
    </TenantRegionalProvider>,
  );
}

/** One line of the report, by its label. */
function line(report: string, label: string): string | null {
  const match = new RegExp(`^\\s*${label}:\\s*(.*)$`, "m").exec(report);
  return match === null ? null : match[1].trim();
}

describe("DEF-SHL-6377 · Download error report downloads a report", () => {
  it("TRF-02: on the PO's failed sale it downloads a named report with what failed and nothing about who", async () => {
    const user = userEvent.setup();
    mountSale();

    await user.type(screen.getByLabelText("Buyer's name"), BUYER_NAME);
    await user.type(screen.getByLabelText("Tax ID"), BUYER_TAX_ID);
    await user.click(screen.getByRole("button", { name: "Complete the sale ✓" }));

    // The PO's panel, exactly as they read it.
    expect(
      await screen.findByText("The sale was not recorded. Nothing changed hands."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("AC-2026-00012 is closed and holds no unit, so it cannot transfer."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Download error report" }));

    // 1 · a file was handed to the browser, once, under the ruled name
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(clicked).toHaveLength(1);
    expect(clicked[0].download).toBe("TRF-02-error-20260923-1405.txt");
    expect(blobs[0].type).toMatch(/^text\/plain/);

    const report = await readBlob(blobs[0]);

    // 2 · what it says — each line by its label, so an empty or shuffled file fails
    expect(line(report, "Screen")).toBe("TRF-02");
    expect(line(report, "Page")).toBe(`/${TENANT}/transfers/new?step=1&q=(withheld)`);
    expect(line(report, "Time")).toBe("2026-09-23 14:05:30 America/Chicago");
    expect(line(report, "Version")).toBe(APP_VERSION);
    expect(line(report, "What failed")).toBe("The sale was not recorded. Nothing changed hands.");
    expect(line(report, "Reason")).toBe(
      "AC-2026-00012 is closed and holds no unit, so it cannot transfer.",
    );
    expect(line(report, "Method")).toBe("POST");
    expect(line(report, "Path")).toBe("/transfers/commit");
    expect(line(report, "Status")).toBe("409");
    expect(line(report, "Code")).toBe("BIZ_STATE");
    expect(line(report, "Message key")).toBe("customers.transfer.not_an_occupant");
    expect(line(report, "Reference")).toBe("5F2B-9C1D");

    // 3 · the header says what it leaves out, in the file itself
    expect(report).toMatch(/leaves out/i);

    // 4 · and it leaves them out — typed, sent, searched for, or in a cookie
    for (const secret of [
      BUYER_NAME,
      "Okonjo",
      BUYER_TAX_ID,
      SEARCHED_FOR,
      "S3SSION-T0KEN",
      "sessionid",
      "full_name",
      "tax_id",
      "from_account_is_not_an_occupant",
      "BR-CUS-030",
    ]) {
      expect(report).not.toContain(secret);
    }
  });

  it("ACC-01: one of the 99 `() => undefined` call sites downloads the same report", async () => {
    const user = userEvent.setup();
    // A list whose load was refused, as DataTable and 98 others draw it.
    const client = createApiClient({
      tenant: TENANT,
      fetchImpl: async () =>
        json({ code: null, message_key: "api.error.unexpected", trace_id: null }, 502),
      maxAttempts: 1,
    });
    await client.get("/accounts", { query: { q: SEARCHED_FOR } }).catch(() => undefined);

    render(
      <TenantRegionalProvider value={CHICAGO}>
        <MemoryRouter initialEntries={[`/${TENANT}/accounts`]}>
          <Routes>
            <Route
              path="/:tenant/accounts"
              element={
                <FailedWithRetry
                  title="The accounts did not load."
                  reason="Nothing was changed."
                  diagnostic="HTTP 502"
                  onRetry={() => undefined}
                  onDownloadReport={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </TenantRegionalProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Download error report" }));

    expect(clicked).toHaveLength(1);
    expect(clicked[0].download).toBe("ACC-01-error-20260923-1405.txt");
    const report = await readBlob(blobs[0]);
    expect(line(report, "Screen")).toBe("ACC-01");
    expect(line(report, "Diagnostic")).toBe("HTTP 502");
    expect(line(report, "Method")).toBe("GET");
    // the path, never the query string — a search term is what a clerk typed
    expect(line(report, "Path")).toBe("/accounts");
    expect(line(report, "Status")).toBe("502");
    expect(report).not.toContain(SEARCHED_FOR);
  });

  it("a caller's own handler still runs — after the report is downloaded", async () => {
    const user = userEvent.setup();
    // The report must already be on its way when the caller's handler runs,
    // because a handler that navigates takes the page with it — so the
    // handler records how many downloads it saw, rather than asserting inside
    // a click handler where a throw would be swallowed by React.
    const seenAtCall: number[] = [];
    const own = vi.fn(() => {
      seenAtCall.push(clicked.length);
    });
    render(
      <MemoryRouter initialEntries={[`/${TENANT}/accounts`]}>
        <Routes>
          <Route
            path="/:tenant/accounts"
            element={
              <FailedWithRetry
                title="t"
                reason="r"
                onRetry={() => undefined}
                onDownloadReport={own}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Download error report" }));

    expect(own).toHaveBeenCalledTimes(1);
    expect(seenAtCall).toEqual([1]);
    expect(clicked).toHaveLength(1);
  });

  it("a refusal from before the panel appeared is not blamed on it, and the report says so", async () => {
    const user = userEvent.setup();
    const client = createApiClient({
      tenant: TENANT,
      fetchImpl: async () => json(NO_CUSTOMER_REFUSAL, 409),
    });
    await client.post("/some/earlier/thing", {}).catch(() => undefined);

    // Ten minutes later a different panel appears, with no request behind it.
    vi.setSystemTime(new Date(NOW.getTime() + 10 * 60 * 1000));
    render(
      <TenantRegionalProvider value={CHICAGO}>
        <MemoryRouter initialEntries={[`/${TENANT}/accounts`]}>
          <Routes>
            <Route
              path="/:tenant/accounts"
              element={
                <FailedWithRetry
                  title="t"
                  reason="r"
                  onRetry={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </TenantRegionalProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Download error report" }));

    const report = await readBlob(blobs[0]);
    expect(report).not.toContain("/some/earlier/thing");
    expect(line(report, "Method")).toBeNull();
    expect(line(report, "Refused request")).toBe(
      "none recorded in the minute before this panel appeared.",
    );
    expect(clicked[0].download).toBe("ACC-01-error-20260923-1415.txt");
  });

  it("with no utility time zone published, the time is written in UTC and says so", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/${TENANT}/accounts`]}>
        <Routes>
          <Route
            path="/:tenant/accounts"
            element={
              <FailedWithRetry
                title="t"
                reason="r"
                onRetry={() => undefined}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Download error report" }));

    const report = await readBlob(blobs[0]);
    expect(line(report, "Time")).toBe(
      "2026-09-23 19:05:30 UTC (the utility's time zone was not known on this page)",
    );
    expect(clicked[0].download).toBe("ACC-01-error-20260923-1905.txt");
  });
});
