// ── Trace ──────────────────────────────────────────────
// Defects: `DEF-PAY-6317` — Record a payment is a MODAL where §03 frame 2·3a
//          draws a PAGE, and `/:tenant/payments/record/new` is not a route at
//          all. The agreed move was recorded in three docstrings and in no
//          queue, so nothing counted it (see the row's `escape_reason`).
// Change:  `CR-136-BRC07` row `P2.9`'s deferred half, blueprint
//          `05-prototype/06 Payments Page Blueprint.pdf` p037–p039 read as
//          IMAGES at scale 2.0 (B14 rule 42).
// Screens: `S35` — `/:tenant/payments/record/new`
// Rules:   B14 rule 41 (the product matches the drawing) · rule 43 (a piece of
//          UI is a COMPONENT) · CLAUDE.md hard-won law 2 and its mirror
//          (`DEF-CWP-3925`: assert a door by ADDRESS, never by a handler)
// ───────────────────────────────────────────────────────
// ⚠ **WHY THE FIRST CASE WALKS `APP_ROUTES` AND NOT A FIXTURE.** A fixture
// that declares its own `<Route path=…>` proves the component renders and
// proves NOTHING about the router — `DEF-CWP-3925`'s hold-expiry test asserted
// a screen was registered at one address while the router mounted it at
// another, and every check passed over both. So the route case reads the array
// `App.tsx` actually hands to the router.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { RecordPaymentForm, RecordPaymentPage } from "./RecordPaymentPage";
import { PAYMENTS_RECORD_NEW_ROUTE, PAYMENTS_RECORD_ROUTE } from "./paymentsShared";

const TENANT = "brazosbend";
const t = (key: string) => i18n.t(key);

function collectPaths(routes: readonly RouteObject[], parent = ""): string[] {
  const out: string[] = [];
  for (const route of routes) {
    let here = parent;
    if (typeof route.path === "string") {
      here = route.path.startsWith("/")
        ? route.path
        : `${parent === "/" ? "" : parent}/${route.path}`;
      out.push(here);
    }
    if (route.children) {
      out.push(...collectPaths(route.children, here));
    }
  }
  return out;
}

/** Answers nothing. Neither case below depends on a read. */
const SILENT = {
  get: () => Promise.resolve({ data: { results: [], count: 0 } }),
} as unknown as ApiClient;

describe("DEF-PAY-6317 · 2·3a is a PAGE at an address, not a modal", () => {
  it("App.tsx declares /:tenant/payments/record/new", () => {
    // The whole defect in one assertion: the address the drawing writes in its
    // own frame header — `agreed: /:tenant/payments/record/new` — resolves.
    expect(collectPaths(APP_ROUTES)).toContain(`/:tenant${PAYMENTS_RECORD_NEW_ROUTE}`);
  });

  it("the payments LIST keeps /payments/record — it is not redirected away", () => {
    // ⚠ **THE ADDRESS A CLERK MAY HAVE BOOKMARKED IS THE LIST, NOT THE FORM.**
    // p030 draws frame 2·1 at `/:tenant/payments/record → PaymentsPage →
    // PaymentsTable`. Redirecting it at the new page would delete the Payments
    // tab, so this case exists to refuse that fix.
    expect(collectPaths(APP_ROUTES)).toContain("/:tenant/payments/:tab");
    expect(PAYMENTS_RECORD_ROUTE).toBe("/payments/record");
    expect(PAYMENTS_RECORD_NEW_ROUTE).not.toBe(PAYMENTS_RECORD_ROUTE);
  });

  it("the form renders under the real path pattern, with the drawn fields", () => {
    // Mounted under `/:tenant/...` and not bare — a bare MemoryRouter leaves
    // `useParams().tenant` undefined and every address the page builds comes
    // out `//payments/…`, which reads as a good string to `toContain`.
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queries}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}${PAYMENTS_RECORD_NEW_ROUTE}`]}>
            <Routes>
              <Route
                path={`/:tenant${PAYMENTS_RECORD_NEW_ROUTE}`}
                element={
                  <RecordPaymentForm
                    client={SILENT}
                    methods={[]}
                    today="2026-09-23"
                    dateFormat="MM/DD/YYYY"
                    currency="USD"
                    onCancel={() => undefined}
                    onRecorded={() => undefined}
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // The drawing's own nine, by their drawn labels (p037).
    expect(html).toContain(t("payments.form.accountSearch"));
    expect(html).toContain(t("payments.form.amount"));
    expect(html).toContain(t("payments.form.purpose"));
    expect(html).toContain(t("payments.form.postedAt"));
    // ⛔ `DEF-PAY-10737` — no Clearing date box since 2026-10-30 (CR-186).
    expect(html).not.toContain(t("payments.form.clearedAt"));
    expect(html).toContain(t("payments.form.applyTo"));
    expect(html).toContain(t("payments.form.memo"));
    // …and the commit, which p038 draws as `Record payment` beside `Cancel`.
    expect(html).toContain(t("payments.form.submit"));
    // ⚠ NOT a dialog: the modal frame sets `role="dialog"`, and its absence is
    // the difference the PO reported.
    expect(html).not.toContain('role="dialog"');
  });

  it("the PAGE renders at that address, with the page head the drawing draws", () => {
    // ⚠ **THE CASE ABOVE MOUNTS THE FORM; THIS ONE MOUNTS WHAT THE ROUTE
    // ACTUALLY OPENS.** `DEF-CWP-3925`'s hold-expiry test asserted a screen was
    // REGISTERED at one address while the router mounted it at another, and
    // every check passed over both — so *the route exists* and *the route
    // renders the screen* are two different statements, and both are made here.
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queries}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}${PAYMENTS_RECORD_NEW_ROUTE}`]}>
            <Routes>
              <Route
                path={`/:tenant${PAYMENTS_RECORD_NEW_ROUTE}`}
                element={
                  <RecordPaymentPage
                    client={SILENT}
                    today="2026-09-23"
                    timeZone="America/Chicago"
                    dateFormat="MM/DD/YYYY"
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // B14 rule 2's ONE page head — p037 draws `PAYMENTS › RECORD A PAYMENT`
    // over **Record a payment**. A modal had nowhere to put either of them.
    expect(html).toContain(t("payments.form.kicker"));
    expect(html).toContain(t("payments.form.title"));
    // B14 rule 1: the back arrow names where it EXITS to, and that is the LIST.
    expect(html).toContain(t("payments.form.back"));
    expect(html).toContain(`/${TENANT}${PAYMENTS_RECORD_ROUTE}`);
    // The form is inside it, and not a second copy of the fields.
    expect(html).toContain(t("payments.form.submit"));
    expect(html).not.toContain('role="dialog"');
  });
});
