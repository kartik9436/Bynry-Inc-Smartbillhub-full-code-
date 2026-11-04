// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-6913 — *"On the premises detail page the header should show
//          the utility service chips; this premises has 4 utility services but
//          they are not visible in the header."* (Product Owner, 2026-09-27,
//          live beta v2.352.0, Ottumwa Water Works, premises `P-00079`)
// Screens: PRM-02 / S15 — the premises detail header.
// Rules:   B14 rule 44 (our UI standard wins over the drawing, including the
//          frame) · rule 43 (a piece of UI is a COMPONENT) · rule 33 (a chip is
//          a LABEL) · rule 31 (no database id on screen) · BR-RAT-024 (eleven
//          services) · BR-MET-003 (`services_available` ⊆ the tenant's enabled
//          set).
// ───────────────────────────────────────────────────────
// ⚠ **THIS FILE EXISTS BECAUSE HARD-WON LAW 2 IS *BUILT IS NOT WIRED*.**
// `ServiceChips.dom.test.tsx` proves the component draws chips. It would go on
// passing for ever with the premises header never mounting it — which is
// exactly the state the PO reported, one indirection along: the DATA was
// served, the fact row drew it, and the header never asked. So every assertion
// here renders THE PAGE and reads the HEADER, not the component.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** The words `Water` and `Sewer`
// already appear in the Overview fact row far below the header, so an assertion
// on the page's TEXT would pass on the unfixed screen. Every case below reads
// inside the header element (`.page-header-rollup`) and nowhere else, and tc0
// pins that by asserting the unfixed shape is detectable — the fact row still
// carries the same words while the header does not.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { PremisesDetail } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  PremisesDetailPage,
  premisesDetailQueryKey,
  premisesAssetsQueryKey,
} from "./PremisesDetailPage";

const TEST_TENANT = "brazosbend";

function premise(over: Partial<PremisesDetail> = {}): PremisesDetail {
  return {
    id: "p-79",
    premise_no: "P-00079",
    name: null,
    address_line: "78 New market",
    city: "ottumwa",
    state: "Iowa",
    postal_code: "12365",
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    premises_type: "single_family",
    premises_type_name: "Single-family",
    services_available: null,
    owner_manager: null,
    owner: null,
    owner_unmatched: false,
    external_ref: null,
    gis_unchecked: false,
    lat: null,
    lng: null,
    gis_checked_at: null,
    gis_checked_by: null,
    status: "active",
    units: 1,
    unit_rows: [],
    units_common: 0,
    ...over,
  } as PremisesDetail;
}

function renderDetail(detail: PremisesDetail): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(premisesDetailQueryKey(detail.id), detail);
  queryClient.setQueryData(premisesAssetsQueryKey(detail.id), {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/${detail.id}`]}>
          <Routes>
            <Route path="/:tenant/premises/:premisesId" element={<PremisesDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The markup of the header's roll-up block ONLY. `.page-header-rollup` is
 * `PageHeader`'s own class for the lines under the title, and reading inside it
 * is what makes these cases about the HEADER rather than about the page — the
 * same service words appear again in the Overview fact list below.
 */
function rollup(html: string): string {
  const at = html.indexOf('class="page-header-rollup"');
  if (at === -1) return "";
  // The block ends where the tab strip begins; `page-header-tabs` is the next
  // element `PageHeader` emits after the identity column.
  const end = html.indexOf("page-header-tabs", at);
  return html.slice(at, end === -1 ? html.length : end);
}

const FOUR = ["water", "sewer", "trash", "fire"];

describe("DEF-MET-6913 — the premises header shows the utility service chips", () => {
  it("tc0 — the header block is findable, and the fact row is NOT inside it", () => {
    // If this ever fails, `rollup()` above has stopped looking at the header and
    // every case below is reading the whole page — which is precisely the false
    // pass this file is built to avoid.
    const html = renderDetail(premise({ services_available: FOUR }));
    expect(rollup(html)).not.toBe("");
    expect(rollup(html)).not.toContain(i18n.t("metering.premises.col.services"));
    expect(html).toContain(i18n.t("metering.premises.col.services"));
  });

  it("tc1 — the PO's premises: four services, four chips in the header", () => {
    const head = rollup(renderDetail(premise({ services_available: FOUR })));
    expect(head.match(/data-service="/g)).toHaveLength(4);
    for (const code of FOUR) {
      expect(head).toContain(`data-service="${code}"`);
      expect(head).toContain(i18n.t(`rating.service.${code}`));
    }
  });

  it("tc2 — FIRE reaches the header (CR-063's eleventh service)", () => {
    // ⚠ The going-live customer this was reported from has Fire. The front end
    // types the service list out by hand in two places and an eleventh service
    // fails SILENTLY, so this asserts the one that is newest by name.
    const head = rollup(renderDetail(premise({ services_available: ["fire"] })));
    expect(head).toContain('data-service="fire"');
    expect(head).toContain(i18n.t("rating.service.fire"));
  });

  it("tc3 — one service draws exactly one chip", () => {
    const head = rollup(renderDetail(premise({ services_available: ["water"] })));
    expect(head.match(/data-service="/g)).toHaveLength(1);
  });

  it("tc4 — no services draws NO chip row, and no stray separator", () => {
    const head = rollup(renderDetail(premise({ services_available: [] })));
    expect(head).not.toContain("data-service=");
    expect(head).not.toContain('data-testid="service-chips"');
  });

  it("tc5 — and an address nobody was asked about draws none either", () => {
    // `null` and `[]` are different facts and the Overview fact row still tells
    // them apart in words (DEF-762). A header states what a record IS; saying
    // why a chip is absent would be RATIONALE, which B14 rule 33 puts at zero
    // words on screen.
    const html = renderDetail(premise({ services_available: null }));
    expect(rollup(html)).not.toContain("data-service=");
    expect(html).toContain(i18n.t("metering.services.notRecorded"));
  });

  it("tc6 — the premise NUMBER is untouched, and no database id is on screen", () => {
    // B14 rule 31. `P-00079` is the utility's own human-facing number and stays
    // exactly where the header already put it; the row id `p-79` must not
    // appear as the visible value of anything.
    const head = rollup(renderDetail(premise({ services_available: FOUR })));
    expect(head).toContain("P-00079");
    expect(head).not.toContain(">p-79<");
  });
});
