// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-028 (the three-step New order wizard) TC-1..TC-6.
//           Screens: sub-screen of Work-007 (`WM-20`, r10's WRK-12)
// Rules:    BR-WRK-024 (source stamped Dispatcher) · BR-WRK-006 (an anchor is
//           required) · BR-WRK-008 (the template picker offers PUBLISHED only)
//           · B14 rules 3 (stepper, not a page head) · 11 · 31 · 32 · 33
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

// The screen fires a toast on a refusal, and `useToast` THROWS outside its
// provider — so a harness without one fails every case with one message and
// says nothing about the screen.
import { ToastProvider } from "@/components/Toast";

import { NEW_ORDER_WIZARD_SCREEN, NewOrderWizard, newOrderWizardPath } from "./NewOrderWizard";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function markup(search = "") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
      {/* Mounted under the REAL path pattern — a bare mount leaves
          `useParams().tenant` undefined and every address comes out `//…`. */}
      <MemoryRouter initialEntries={[`${newOrderWizardPath(TENANT)}${search}`]}>
        <Routes>
          <Route path="/:tenant/work/orders/new" element={<NewOrderWizard />} />
        </Routes>
      </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-WRK-028 — the three-step New order wizard (WM-20)", () => {
  it("B14 rule 3 — a three-step flow gets the STEP BAR and no page head", () => {
    const html = markup();
    // ⚠ ESCAPED, because the rail's own label carries an ampersand and this
    // is server-rendered markup, not text. Asserting the raw string here
    // failed over a perfectly correct screen.
    expect(html).toContain("Job &amp; location");
    expect(html).toContain("Schedule &amp; crew");
    expect(html).toContain(t("work.newOrder.step3"));
    expect(html).toContain('data-wizard="rail"');
    // Rule 3's other half: no `PageHeader` tab strip on a wizard.
    expect(html).not.toContain("data-page-header-tabs");
  });

  it("BR-SHL-018 — a pasted ?step=3 CLAMPS to step 1 rather than skipping ahead", () => {
    // The frame only ever renders the ACTIVE step's content, and forward
    // movement comes from Continue after a step validates — never from an
    // address somebody was sent. So a deep link into Confirm lands on step 1
    // with the fields empty, which is the safe answer and not a bug.
    const html = markup("?step=3");
    expect(html).toContain('data-wizard-step="1" data-state="active"');
    expect(html).toContain(t("work.raise.premises"));
  });

  it("declares its badge, and the badge is r10's own rather than a minted one", () => {
    expect(markup()).toContain(`data-screen="${NEW_ORDER_WIZARD_SCREEN}"`);
    expect(NEW_ORDER_WIZARD_SCREEN).toBe("WRK-12");
  });

  // ⚠ CR-168-BRC10 round 3 (lane RAISE): TC-5 (published templates only), the
  // template's NAME never its uuid, the Confirm copy and the anchor refusal
  // moved to `raise/cr168Raise.dom.test.tsx` with the screen they describe —
  // the template list now arrives only once a job type is chosen (DEF-WRK-9582),
  // so a server render of step 1 can no longer hold it, and the one-sentence
  // EFFECT box and the anchor sentence were replaced by image 17's and by one
  // refusal per field (DEF-WRK-9572).
  it("one function says where the wizard opens, so nothing can disagree", () => {
    expect(newOrderWizardPath(TENANT)).toBe(`/${TENANT}/work/orders/new`);
  });
});
