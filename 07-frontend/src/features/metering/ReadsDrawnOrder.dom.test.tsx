// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Drawn:    Meter Reads blueprint **entry 17 (Route sheet, p056-57)** and
//           **entry 18 (Estimate a missing read, p058-60)**, read as images
//           (B14 rule 42), not from the text layer.
// Rules:    B14 rule 41 (the product UI matches the blueprint EXACTLY) ·
//           rule 38 (where a drawing and our UI rules disagree about how a FORM
//           IS BUILT, the UI rules win; what it CONTAINS is the drawing's) ·
//           rule 33 (on-screen text is capped by what it is for) ·
//           rule 31 (nothing internal is ever visible to a utility user) ·
//           BR-MET-170 (3) (the register is named in the words the screens use)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS: RULE 41 IS RATIFIED AND HAS NO MECHANICAL EXPRESSION
// ══════════════════════════════════════════════════════════════════════════
// B14 rule 41's own enforcement cell says so, and says it honestly: *"UNENFORCED,
// AND HONESTLY SO — NOTHING IN THIS REPOSITORY READS A RENDERED SCREEN."* What
// it names as the plan is a **screen census** — drive each route, dump every
// heading, label and control label IN ORDER, and diff that against the drawing
// written as text. The census covers twelve tabs of ONE screen today.
//
// This is that census for two dialogs, at the cheapest level that still answers
// the question: the ORDER of the drawn elements, read off the rendered DOM.
//
// ⚠ **WHAT IT CAN AND CANNOT SEE, STATED SO NOBODY ASSUMES MORE.** It reads
// presence and ORDER — §4's first three comparisons (presence, order, labels).
// It reads nothing about alignment, spacing, weight or colour, because jsdom
// computes no layout; those remain a person with a browser (hard-won law 6).
// A file that implied otherwise would be worse than none.
//
// ⚠ **IT ASSERTS NO DRAWN FIGURE.** B14 rule 37: every number inked into a
// wireframe is an ILLUSTRATION. `MTR-0463`, `412 kWh`, `RT-04 · North Elm` and
// `08/31/2026` are examples of a SHAPE and say nothing about any real row, so
// the only route value below is one this test supplies itself.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { ToastProvider } from "@/components/Toast";

import { EstimateReadModal } from "./EstimateReadModal";
import { RouteSheetModal } from "./ReadsListPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/**
 * Every label, option and button the dialog puts on screen, in DOM order.
 *
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/reads` PATTERN.** A bare `MemoryRouter`
 * leaves `useParams().tenant` undefined and every URL these dialogs build comes
 * out `//reads/…`, which reads as a perfectly good string to `toContain`.
 */
function visibleOrder(node: React.ReactElement): string[] {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { container } = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads`]}>
          <Routes>
            <Route path="/:tenant/reads" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  const out: string[] = [];
  container.querySelectorAll("label, option, button, p").forEach((el) => {
    const text = (el.textContent ?? "").trim().replace(/\s+/g, " ").replace(/\*$/, "");
    // `✕` is the shared frame's close control, not a field of either drawing.
    if (text !== "" && text !== "✕" && !out.includes(text)) out.push(text);
  });
  return out;
}

/** Where `needle` sits in the rendered order, or -1. Order is the assertion. */
function at(order: string[], needle: string): number {
  return order.indexOf(needle);
}

describe("entry 18 — Estimate a missing read, in the drawn order", () => {
  it("Meter number → Register → Read date, each above the next", () => {
    // Page 58 draws three stacked full-width fields in this sequence. The
    // sequence is CONTENT, which rule 38 leaves to the drawing; what the fields
    // are built FROM (the shared kit's TextField, SelectField and
    // DatePickerField) is construction, which it gives to our UI rules.
    const order = visibleOrder(<EstimateReadModal onClose={() => undefined} />);
    expect(at(order, t("metering.estimate.meterNo"))).toBeGreaterThanOrEqual(0);
    expect(at(order, t("metering.estimate.meterNo"))).toBeLessThan(
      at(order, t("metering.estimate.channelLabel")),
    );
    expect(at(order, t("metering.estimate.channelLabel"))).toBeLessThan(
      at(order, t("metering.estimate.readAt")),
    );
  });

  it("the period helper sits UNDER the read date, not after the form", () => {
    // B14 rule 39: a field is label → input → helper, and the helper must read
    // as attached to the input ABOVE it. It used to be a `Note` after every
    // field, where it read as a footnote to the whole dialog.
    const order = visibleOrder(<EstimateReadModal onClose={() => undefined} />);
    expect(at(order, t("metering.estimate.readAt"))).toBeLessThan(
      at(order, t("metering.estimate.readAtHelp")),
    );
  });

  it("no rationale is on screen before the answer (B14 rule 33, MR-14)", () => {
    // Rule 33: RATIONALE is ZERO words on screen. The 25-word lede explaining
    // what estimation IS was the breach, and it is removed rather than
    // shortened — six words of rationale is still rationale.
    const order = visibleOrder(<EstimateReadModal onClose={() => undefined} />);
    const sentences = order.filter((line) => line.split(/\s+/).length > 6);
    expect(sentences).toEqual([]);
  });

  it("the footer is the kit's, and the commit carries rule 4's ✓", () => {
    // ⚠ **THE DRAWING SAYS `Close`, AND THE KIT SAYS `Cancel`.** Rule 38 names
    // a footer's buttons as CONSTRUCTION and gives construction to our UI
    // rules, because the alternative is changing every dialog in the product on
    // one screen's authority. The WORD on the commit is the drawing's
    // ("Estimate"); the ✓ is B14 rule 4's grammar for a control that writes.
    const order = visibleOrder(<EstimateReadModal onClose={() => undefined} />);
    expect(order).toContain(t("forms.cancel"));
    expect(order).toContain(t("metering.estimate.submit"));
    expect(t("metering.estimate.submit")).toContain("✓");
    expect(at(order, t("forms.cancel"))).toBeLessThan(at(order, t("metering.estimate.submit")));
  });
});

describe("entry 17 — Route sheet, in the drawn order", () => {
  const routes = [{ id: "rt-1", code: "RT-04", name: "North Elm" }] as never;
  const cycles = [{ id: "c-1", code: "CY-002" }] as never;

  function sheet() {
    return visibleOrder(
      <RouteSheetModal
        routes={routes}
        cycles={cycles}
        buildHref={(scope, id) => `/api/${TEST_TENANT}/${scope}/${id}/route-sheet`}
        onClose={() => undefined}
      />,
    );
  }

  it("scope question → its two answers → the picker it changes", () => {
    // Page 56: "Print the sheet for" over a segmented [A route | A cycle], and
    // the picker BELOW changes with the answer. It is one question with two
    // answers, which is why it is a segment and not two buttons.
    const order = sheet();
    expect(at(order, t("metering.reads.routeSheet.scopeLabel"))).toBeGreaterThanOrEqual(0);
    expect(at(order, t("metering.reads.routeSheet.scopeLabel"))).toBeLessThan(
      at(order, t("metering.reads.routeSheet.scopeRoute")),
    );
    expect(at(order, t("metering.reads.routeSheet.scopeRoute"))).toBeLessThan(
      at(order, t("metering.reads.routeSheet.route")),
    );
  });

  it("the help line sits under the picker and says what happens BEFORE the tab opens", () => {
    const order = sheet();
    expect(at(order, t("metering.reads.routeSheet.route"))).toBeLessThan(
      at(order, t("metering.reads.routeSheet.help")),
    );
    // Rule 33: two sentences of at most six words each, which is the drawing's
    // own line. Neither is cut below what a clerk acts on.
    for (const sentence of t("metering.reads.routeSheet.help").split(". ")) {
      expect(sentence.replace(/\.$/, "").split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

  it("the route option shows the route's own code and name, never its id", () => {
    // B14 rule 31. The id is the option's VALUE and never its text; a uuid in a
    // picker is the defect that rule exists for.
    const order = sheet();
    expect(order).toContain("RT-04 · North Elm");
    expect(order.join(" ")).not.toContain("rt-1");
  });
});
