// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-MET-002 (S15 unit detail — the Audit log tab) · CR-089 `F5`
//          Screens: S15 (PRM-03, Audit log) · S14 (PRM-02, Audit log)
// Spec:    04-docs/05-modules/04-metering/conformance/CR-089-p085-unit-audit-log.md
//          — rows 13 (the dead empty-state CTA) and 14 (one screen id on two
//          mounts)
// Defects: DEF-MET-4764 (an empty audit tab drew the same words twice, once
//          dead) · DEF-MET-4765 (both mounts declared `PRM-02.audit`, so one
//          saved column set covered a building AND every flat in it)
// Rules:   BR-SHL-013 (`table.<screen>.columns` is keyed by `screenId`) ·
//          BR-AUD-010 (a per-entity tab RENDERS and LINKS) · B14 rule 4 (one
//          primary per screen) · CLAUDE.md hard-won law 2's MIRROR
// ───────────────────────────────────────────────────────
// **WHAT THIS FILE IS FOR, AND IT IS THE HALF NO GATE CAN SEE.**
//
// `G13` asks whether a prop is PASSED. Both defects here passed every prop:
// `onCta` had a caller, `screenId` had a value, `tsc` was green and 42 test
// files went by. What was wrong was what the values MEANT — a handler that
// does nothing, and a key that is the wrong screen's.
//
// ⚠ **NO DRAWN NUMBER IS ASSERTED ANYWHERE IN THIS FILE** (PO ruling
// 2026-09-10: *"Treat every number drawn in a wireframe as an illustration,
// never a fact to build to."*). The fixtures below carry values of this
// harness's own; what is pinned is SHAPE — how many controls carry the words,
// which element type they are, and that two mounts do not share one key.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { AuditTab, auditScreenId, entityAuditQueryKey } from "./PremisesDetailPage";

const TEST_TENANT = "brazosbend";

/** An audit read that came back with nothing — the state row 13 is about. */
function renderEmptyAuditTab(entityType: string, entityId: string): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(entityAuditQueryKey(entityType, entityId), {
    page: { count: 0, next: null, previous: null, results: [] },
    window: { window: "hot", from: null },
  });
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2's fixture clause).
  // A bare `MemoryRouter` leaves `useParams().tenant` undefined and every
  // address the tab builds comes out `//audit-log?…` — a protocol-relative URL
  // to another host, which reads as a perfectly good string to `toContain`.
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/${entityId}?tab=audit`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <AuditTab
                  entityType={entityType}
                  entityId={entityId}
                  t={(key, params) => i18n.t(key, params) as string}
                  regional={{}}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** How many times a string occurs — the count IS the assertion here. */
function occurrences(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

describe("U9 row 13 · an empty audit tab offers ONE door, and it opens", () => {
  it("draws the full-log words exactly once", () => {
    const html = renderEmptyAuditTab("unit", "u-101a");
    const label = i18n.t("metering.audit.openViewer") as string;
    expect(
      occurrences(html, label),
      "the empty audit tab drew the full-log words more than once — the empty " +
        "state's CTA is back, and `EmptyList` wires it to a live <Button> that " +
        "does nothing (DEF-MET-4764)",
    ).toBe(1);
  });

  it("the one that remains is the LINK, never a button", () => {
    const html = renderEmptyAuditTab("unit", "u-101a");
    const label = i18n.t("metering.audit.openViewer") as string;
    // The surviving control is `fullLog`, a `ButtonLink` — an <a> carrying the
    // pre-filtered S61 address. A <button> carrying these words is the dead
    // one coming back, whatever handler it was given.
    const anchor = new RegExp(`<a[^>]*href="[^"]*audit-log[^"]*"[^>]*>[^<]*${label}`);
    expect(html).toMatch(anchor);
    const button = new RegExp(`<button[^>]*>[^<]*${label}`);
    expect(
      button.test(html),
      "a <button> carries the full-log words — that is the dead control " +
        "(DEF-MET-4764); the working way out is the ButtonLink below the table",
    ).toBe(false);
  });

  it("still says WHICH window was searched, which PO ruling 2026-09-10 kept", () => {
    // *"keep it as it is"* — removing the dead button must not take the
    // sentence beside it, or a short history reads as *nothing ever happened*.
    const html = renderEmptyAuditTab("unit", "u-101a");
    expect(html).toContain(i18n.t("audit.window.hot") as string);
  });
});

describe("U9 row 14 · the two mounts do not share one saved column set", () => {
  it("gives the unit's history its own screen id", () => {
    expect(auditScreenId("unit")).not.toBe(auditScreenId("premises"));
  });

  it("leaves the PROPERTY's stored key exactly where it was", () => {
    // ⚠ **PINNED AS A STRING ON PURPOSE.** `screenId` keys
    // `table.<screen>.columns`; renaming it silently resets every clerk's saved
    // layout on that screen. This is the one value here that may not drift.
    expect(auditScreenId("premises")).toBe("PRM-02.audit");
  });

  it("gives an entity type nobody has wired the property's key, not a shared new one", () => {
    // A third mount must land on a REVIEWED row rather than inventing a key.
    expect(auditScreenId("asset")).toBe("PRM-02.audit");
  });
});
