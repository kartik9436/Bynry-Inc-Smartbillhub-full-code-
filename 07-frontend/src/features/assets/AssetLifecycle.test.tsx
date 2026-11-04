// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-007 (S53 log repair / inspection / test) · US-AST-008 (S54
//           retire — terminal) · US-AST-009 (S55 reassign + final read)
//           Screens: S53/AST-07 · S54/AST-08 · S55/AST-06 — FULL PAGES since
//           CR-028 AST-W4 (PO 2026-08-22: "as per r10 - it is not modal")
// Rules:    BR-AST-018 (append-only maintenance) · BR-AST-020/031 (legal
//           transitions from the behavior class) · BR-AST-021 (retire needs
//           reason + date) · BR-AST-022 (the final read and the move are ONE
//           transaction — the server REFUSES when it cannot capture) ·
//           BR-AST-030 (retire is TERMINAL — no un-retire exists) ·
//           BR-AST-036/037/038 (bulk assign; sub-meter move warnings) ·
//           BR-AST-047/§10-D4 (book value recorded, posted NOWHERE) ·
//           §10-D3 (cost captured — NO "post to O&M" control) ·
//           §10-D7 (work-order controls disabled with EXACTLY "Work R5")
// ───────────────────────────────────────────────────────
// The load-bearing tests here are the refusals and absences the pages must
// SHOW rather than route around: the BR-AST-022 final-read refusal, the
// absence of any un-retire path (BR-AST-030), the absence of every GL
// sentence (D3/D4), and D7's two-word disabled reason, verbatim.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import * as endpoints from "@/api/endpoints";
import { ApiError, createApiClient, formErrorEnvelope, isApiError } from "@/api/client";
import { logAssetMaintenance, reassignAsset, retireAsset } from "@/api/endpoints";
import type { AssetDetail, LookupEntry, Paginated, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { buttonClasses } from "@/components/buttonKit";
import { apiErrorText } from "@/features/tenancy/settingsShared";

import {
  MAINTENANCE_KIND_VALUES,
  RETIRE_REASON_VALUES,
  assetStagesQueryKey,
  assetTechPickerKey,
  assetUnitPickerKey,
  bulkAssignFailureKey,
  legalTargets,
  reassignWarningKey,
  stageOptionsFrom,
  transitionAllowed,
  unitPickerOptions,
} from "./AssetLifecycleModals";
import { AssetLogMaintenancePage, AssetReassignPage } from "./AssetFlowPages";
import { asset, detail } from "./assetTestFixtures";
import {
  AssetRetireWizard,
  hasBookValue,
  replacementOptions,
  retirePayload,
  retireStepValid,
  initialRetireValues,
} from "./AssetRetireWizard";
import {
  addPayload,
  initialAddValues,
  mastersFor,
  numberAvailabilityKey,
  isUntouched,
  requiresService,
  stepValid,
} from "./AssetAddWizard";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…` and
// every tenant-scoped call goes to `/api/{tenant}/…`.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function lookup(code: string, name: string, behavior: string): LookupEntry {
  return {
    id: `l-${code}`,
    code,
    name,
    // CR-089 wave A · BR-MET-1162 — a unit's own point. `null` is the state
    // all 1,109 units are in today, and `point.source: "premises"` is the
    // ruled fallback: this unit reads its building's.
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    is_system: true,
    used_by: 0,
    behavior_class: behavior,
  };
}

const STAGES: LookupEntry[] = [
  lookup("inventory", "Inventory/Spare", "available"),
  lookup("active", "Installed/Active", "in_service"),
  lookup("needs_repair", "Needs repair", "out_of_service"),
  lookup("in_repair", "In repair", "out_of_service"),
  lookup("retired", "Retired", "terminal"),
];
const OPTIONS = stageOptionsFrom(STAGES);



const UNITS: UnitRow[] = [
  {
    id: "u-224",
    unit_no: "U-224",
    premises_id: "p-riverside",
    premise_no: "P-00318",
    premise_address: "2200 Riverside",
    label: "224",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    // CR-089 wave A · BR-MET-1162 — a unit's own point. `null` is the state
    // all 1,109 units are in today, and `point.source: "premises"` is the
    // ruled fallback: this unit reads its building's.
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["water"],
    meters: [],
    occupancy: "vacant",
    occupant: null,
    account_no: null,
    status: "vacant",
    // DEF-755 — *what is METERED here*, now under its own name. `services`
    // above is what the unit's PREMISES offers; the two answer different
    // questions and no longer share a word.
    metered_services: [],
    sub_metered: false,
  },
];

function paged<T>(rows: T[]): Paginated<T> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

const NOOP_CLIENT = createApiClient({
  tenant: TEST_TENANT,
  fetchImpl: async () => new Response("{}", { status: 200 }),
});

/**
 * The four flows are ROUTED PAGES now: the render goes through the router so
 * `useParams().assetId` and `useTenantPath()` read the real URL — exactly what
 * a modal never had.
 */
/**
 * The same page with the CREW LIST missing — `DEF-MET-4977`'s degrade.
 *
 * An unseeded query is `isPending`, so `isSuccess` is false and the component
 * takes exactly the branch a 403, a 500, a timeout or an offline browser takes.
 * That is the whole point of the finding: the old branch was `isSuccess` with
 * `retry: false`, so it could not tell those four apart and named a cause for
 * all of them.
 */
function renderFlowWithoutCrew(path: string, page: ReactNode, seeded: AssetDetail): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["assets", "detail", seeded.id], seeded);
  queryClient.setQueryData(assetStagesQueryKey, paged(STAGES));
  queryClient.setQueryData(assetUnitPickerKey, paged(UNITS));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/:tenant/assets/:assetId/maintenance/new" element={page} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderFlow(path: string, page: ReactNode, seeded: AssetDetail): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["assets", "detail", seeded.id], seeded);
  queryClient.setQueryData(assetStagesQueryKey, paged(STAGES));
  queryClient.setQueryData(assetUnitPickerKey, paged(UNITS));
  // `BR-AST-533` — the CREW DIRECTORY's shape, which is `id`, `name`, `email`
  // and nothing else. It used to be seeded with `GET /users`' row (role,
  // role_name, status, last_active_at), and since 2026-09-12 that read is not
  // the one this screen makes: `GET /users` is still `SystemAdminOnly` and the
  // picker now asks `GET /work/crew-directory`. Seeding the old shape would
  // have kept this file green over a screen calling a different endpoint —
  // which is a fixture that cannot tell a working read from a broken one.
  queryClient.setQueryData(assetTechPickerKey, {
    results: [{ id: "u-ray", name: "Ray Delgado", email: "ray@brazosbend.example" }],
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/:tenant/assets/:assetId/reassign" element={page} />
            <Route path="/:tenant/assets/:assetId/maintenance/new" element={page} />
            <Route path="/:tenant/assets/:assetId/retire" element={page} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// The not-modal law (CR-028 AST-W4 — PO: "as per r10 - it is not modal")
// ══════════════════════════════════════════════════════════════════════════
/**
 * ONE button's own opening tag — see the B14 rule 6 case in the retire suite.
 * A class token asserted against a whole rendered page answers "does ANY button
 * carry this", which is not the question rule 6 asks (DEF-712's helper).
 */
function buttonTagLabelled(html: string, label: string): string {
  for (const match of html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)) {
    if (match[1].includes(label)) {
      return match[0].slice(0, match[0].indexOf(">") + 1);
    }
  }
  throw new Error(`no <button> labelled ${label} in the rendered output`);
}

describe("CR-028 AST-W4 — no lifecycle flow is a modal", () => {
  it("AST-06/07/08 render as FULL PAGES: a page header, and no dialog anywhere", () => {
    const pages: [string, ReactNode][] = [
      [
        `/${TEST_TENANT}/assets/a-4022/reassign`,
        <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" key="r" />,
      ],
      [
        `/${TEST_TENANT}/assets/a-4022/maintenance/new`,
        <AssetLogMaintenancePage client={NOOP_CLIENT} today="2026-08-16" key="m" />,
      ],
      [
        `/${TEST_TENANT}/assets/a-4022/retire`,
        <AssetRetireWizard client={NOOP_CLIENT} today="2026-08-16" key="t" />,
      ],
    ];
    for (const [path, page] of pages) {
      const html = renderFlow(path, page, detail());
      expect(html, path).toContain("page-header");
      expect(html, path).not.toContain('role="dialog"');
      expect(html, path).not.toContain("aria-modal");
    }
  });

  it("every work-order control on these flows is LIVE, and \"Work R5\" is gone", () => {
    // ⚠ **INVERTED BY CR-070 WAVE M, AND THE INVERSION IS THE POINT.** This
    // case read *every work-order control is DISABLED with EXACTLY "Work R5" —
    // never hidden, never built*, and it was correct while `OQ-249`'s Work half
    // was open. `BR-WRK-056` closed it: the Assets door has an address and the
    // four pre-ticks open it. A refusal that outlives its reason is invisible to
    // every gate in this repo (hard-won law 2's mirror clause, `DEF-CWP-3925`),
    // so the case that asserted the refusal is the case that must fire.
    //
    // The key is DELETED from all eleven catalogues, so `t()` can only echo it
    // back; a catalogue that still answered "Work R5" would mean the deletion
    // was reverted.
    expect(t("assets.flow.workR5")).not.toBe("Work R5");
    const cases: [string, ReactNode][] = [
      [
        `/${TEST_TENANT}/assets/a-4022/reassign`,
        <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" key="r" />,
      ],
      [
        `/${TEST_TENANT}/assets/a-4022/maintenance/new`,
        <AssetLogMaintenancePage client={NOOP_CLIENT} today="2026-08-16" key="m" />,
      ],
    ];
    for (const [path, element] of cases) {
      const html = renderFlow(path, element, detail());
      expect(html, path).not.toContain("data-work-r5");
      expect(html, path).not.toContain('title="Work R5"');
      // And the LIVE control is really there — an absence alone would pass
      // over a screen that simply stopped drawing the checkbox.
      expect(html, path).toContain("data-raise-work");
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// US-AST-007 — S53 / AST-07 log repair / inspection / test (full page)
// ══════════════════════════════════════════════════════════════════════════
describe("US-AST-007 — AST-07 log repair / inspection / test", () => {
  it("BR-AST-020: only the transitions LEGAL FROM the current stage are offered", () => {
    const from = (code: string) => legalTargets(OPTIONS, code).map((s) => s.code);
    expect(from("active")).toEqual(["active", "needs_repair"]);
    expect(from("needs_repair")).toEqual(["needs_repair", "in_repair"]);
    expect(from("in_repair")).toEqual(["active", "in_repair"]);
    expect(from("inventory")).toEqual(["inventory"]);
    // BR-AST-030: retired is terminal — nothing leaves it, ever.
    expect(from("retired")).toEqual(["retired"]);
    const active = OPTIONS.find((s) => s.code === "active")!;
    const inRepair = OPTIONS.find((s) => s.code === "in_repair")!;
    expect(transitionAllowed(active, inRepair)).toBe(false);
  });

  it("BR-AST-031: a TENANT-ADDED stage falls back to its behavior class, not its label", () => {
    const custom = { code: "awaiting_parts", name: "Awaiting parts", behaviorClass: "out_of_service" };
    const active = OPTIONS.find((s) => s.code === "active")!;
    const terminal = OPTIONS.find((s) => s.code === "retired")!;
    expect(transitionAllowed(active, custom)).toBe(true);
    expect(transitionAllowed(custom, active)).toBe(true);
    expect(transitionAllowed(custom, terminal)).toBe(false);
  });

  // ══════════════════════════════════════════════════════════════════════
  // BR-AST-533 / DEF-MET-4977 — a clerk names the technician, never types one
  // ══════════════════════════════════════════════════════════════════════

  const MAINTENANCE_PATH = `/${TEST_TENANT}/assets/a-4022/maintenance/new`;
  const maintenancePage = () => (
    <AssetLogMaintenancePage client={NOOP_CLIENT} today="2026-08-16" />
  );

  /** What `renderToStaticMarkup` does to a catalogue string on its way into
   *  the DOM. Only the three characters that appear in these sentences. */
  function escapeForMarkup(value: string): string {
    return value.replace(/&/g, "&amp;").replace(/'/g, "&#x27;").replace(/"/g, "&quot;");
  }

  /** One element's own opening tag — a class or attribute asserted against a
   *  whole page answers *"does ANYTHING here carry this"*, which is not the
   *  question these ask (the DEF-712 helper's reasoning). */
  function tagFor(html: string, id: string): string {
    const at = html.indexOf(`id="${id}"`);
    expect(at, `no element has id ${id}`).toBeGreaterThan(-1);
    return html.slice(html.lastIndexOf("<", at), html.indexOf(">", at) + 1);
  }

  it("BR-AST-533: the technician is a PICKER showing a name and an email, and no uuid", () => {
    const html = renderFlow(MAINTENANCE_PATH, maintenancePage(), detail());
    const field = tagFor(html, "tech_user_id");
    // A combobox, not a text box. Before 2026-09-12 a Billing Clerk — the one
    // role BR-AST-038 wrote this screen FOR — got `<input type="text">` and was
    // asked for a uuid, which B14 rule 31 forbids outright and which no screen
    // in the product would have let them look up.
    expect(field).toContain('role="combobox"');
    expect(html).toContain("Ray Delgado · ray@brazosbend.example");
    // The id is the OPTION's value and never a visible one.
    expect(html.replace(/<[^>]*>/g, " ")).not.toContain("u-ray");
  });

  it("BR-AST-533: the label is the detail page's own word for it", () => {
    // One thing, one name. The detail page's maintenance table heads this
    // column "Technician"; the form said "Assign tech" (a verb phrase for a
    // noun), so a clerk met two names for one field one click apart.
    const html = renderFlow(MAINTENANCE_PATH, maintenancePage(), detail());
    expect(html).toContain(t("assets.maintenance.tech"));
    expect(t("assets.maintenance.tech")).toBe(t("assets.maintenance.technician"));
  });

  it("DEF-MET-4977: when the crew list cannot load the control STAYS a picker, disabled with its reason", () => {
    const html = renderFlowWithoutCrew(MAINTENANCE_PATH, maintenancePage(), detail());
    const field = tagFor(html, "tech_user_id");
    expect(field).toContain('role="combobox"'); // never a text box again
    expect(field).toContain("disabled"); // BR-SHL-025 / BR-AST-534
    // ⚠ ASSERTED THROUGH THE SAME ESCAPING THE RENDERER APPLIES. The sentence
    // carries an apostrophe, which `renderToStaticMarkup` writes as `&#x27;` —
    // so a raw `toContain` of the catalogue value fails over a screen that is
    // rendering it perfectly. A check that fails for a reason that is not a
    // defect gets "fixed" by being weakened, which is worse than no check.
    expect(html).toContain(escapeForMarkup(t("assets.maintenance.techNoList")));
  });

  it("DEF-MET-4977: the failure sentence never claims a cause it cannot know", () => {
    // ⚠ THE SECOND FAULT, AND THE ONE NO RULING CURED. The branch is
    // `isSuccess` with `retry: false`, so a 500, a timeout and an offline
    // browser all take it — and the old sentence told a SYSTEM ADMIN "Your role
    // can't list users", a statement about their own permissions that was
    // simply false. The replacement says what happened, not why.
    const sentence = t("assets.maintenance.techNoList");
    expect(sentence.toLowerCase()).not.toContain("role");
    // And it no longer asks for an identifier, because the control it belongs
    // to is no longer one you can type into (asserted above, by element).
    expect(sentence).not.toMatch(/\bID\b/);
  });

  it("DEF-MET-4991: the date bound and the prefill survive the way the ROUTER mounts this page", () => {
    // ⚠ **THE ASSERTION IS THE ABSENT PROP, AND IT IS THE WHOLE POINT.**
    // `App.tsx` mounts `<AssetLogMaintenancePage />` with NO PROPS. Every other
    // case in this file passes `today="2026-08-16"`, so all of them were green
    // while the shipped screen rendered `value=""` and `max=null` — measured in
    // Chromium at 1440 and 1280. That is hard-won law 2 wearing a test's
    // clothes: the fixture supplied what the router does not, so the fixture
    // could not tell a wired screen from an unwired one.
    const html = renderFlow(
      MAINTENANCE_PATH,
      <AssetLogMaintenancePage client={NOOP_CLIENT} />,
      detail(),
    );
    const input = tagFor(html, "date");
    expect(input).toMatch(/max="\d{4}-\d{2}-\d{2}"/); // BOUNDED without the prop
    expect(input).toMatch(/value="\d{4}-\d{2}-\d{2}"/); // BR-PAY-033's proposal
  });

  it("DEF-MET-4974 / B14 rule 7: the date field enforces the bound its own help states", () => {
    // "Cannot be in the future." was rendered under a control with `max: null`
    // at 1280 and 1440, while the server refused a future date all along
    // (services.py:1376). A sentence promising what the control does not do
    // reads as good copy to every check here and as a lie to the clerk.
    const html = renderFlow(MAINTENANCE_PATH, maintenancePage(), detail());
    const input = tagFor(html, "date");
    expect(input).toContain('max="2026-08-16"');
    expect(html).toContain(t("assets.maintenance.dateHelp"));
  });

  it("US-AST-007 TC-1/TC-4 / BR-AST-018 / §10-D3: three kinds, append-only, a COST field, and NO posting checkbox", () => {
    expect([...MAINTENANCE_KIND_VALUES]).toEqual(["repair", "inspection", "test"]);
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/maintenance/new`,
      <AssetLogMaintenancePage client={NOOP_CLIENT} today="2026-08-16" />,
      detail({ status: "needs_repair", behavior_class: "out_of_service" }),
    );
    expect(html).toContain("Repair");
    expect(html).toContain("Inspection");
    expect(html).toContain("Test");
    expect(html).toContain("never edited or deleted");
    // Only the legal target plus "no change" is in the Set-status select.
    expect(html).toContain("In repair");
    expect(html).toContain("(no change)");
    expect(html).not.toContain(">Retired<");
    // r10 AST-07's cost — captured, and D3: the "Post the cost to O&M 5300"
    // checkbox does NOT exist. No GL account renders anywhere.
    //
    // ⚠ **THE LABEL IS `Cost`, NOT `Estimated cost`.** Read off figure 34 as an
    // image (p93, the REDRAWN screen): the field is headed `Cost` with the
    // helper "Recorded on the asset. Posted nowhere." The as-built figure above
    // it (p92) still reads `Estimated cost`, which is what this line asserted —
    // so the assertion was correct about the old screen and the drawing
    // supersedes it. `assets.maintenance.costEntry` is now a DEAD KEY.
    expect(html).toContain("Cost");
    expect(html).not.toContain("Estimated cost");
    // ⚠ **ASSERTED THROUGH THE TRANSLATOR, NOT BY VALUE (DEF-2367's lesson,
    //    applied the same day it was learned).** This read `toContain("posts
    //    nowhere")` and went red when CR-060 T12 swept that phrasing out under
    //    B14 rule 34 — the product now says **Recorded** / **In the books**
    //    everywhere, in one pair of words. The CLAIM here is unchanged and is
    //    what matters: the cost field says the money does not reach the books.
    //    Reading the key means a rewording cannot break it, and the assertion
    //    still fails if the sentence stops being rendered at all.
    expect(html).toContain(t("assets.maintenance.costHelp"));
    expect(html).not.toContain("O&amp;M");
    expect(html).not.toContain("5300");
    // BR-SHL-033: the date is a picker, prefilled with today; the tech list
    // is the searchable control.
    expect(html).toContain('type="date"');
    expect(html).toContain('value="2026-08-16"');
    expect(html).toContain('role="combobox"');
  });

  it("B16 §5.1b (A): a testing device's page is TITLED Log test and defaults the kind to test", () => {
    const backflow = detail({
      id: "a-3301",
      asset_no: "BF-3301",
      type: "backflow",
      type_name: "Backflow preventer",
      tab: "behind_the_meter",
      meter_type: null,
      meter_type_name: null,
      unit: null,
      has_test_cadence: true,
    });
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-3301/maintenance/new`,
      <AssetLogMaintenancePage client={NOOP_CLIENT} today="2026-08-16" />,
      backflow,
    );
    // ⚠ **HEADER RULE 1 SPLIT THIS TITLE IN TWO.** Page 36 states it verbatim —
    // "kicker without the number · the number once, in the title" — and figure
    // 34's own header (p92) draws it: kicker `METER · AMI · LOG REPAIR /
    // MAINTENANCE`, then the asset number alone as the h1. So there is no longer
    // one sentence reading "Log test · BF-3301" anywhere on the page.
    //
    // Asserted INSIDE the kicker rather than page-wide: `BF-3301` is
    // legitimately in the h1 immediately below, so `html.toContain("BF-3301")`
    // could never fail and would be a check that does not check.
    const testKicker = html.slice(html.indexOf("kicker"), html.indexOf("<h1"));
    expect(testKicker).toContain("Log test");
    expect(testKicker).not.toContain("BF-3301");
    expect(html.slice(html.indexOf("<h1"))).toContain("BF-3301");
  });

  it("US-AST-007 TC-5: an illegal transition is refused by the SERVER, in plain language", async () => {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            code: "BIZ-STATE",
            message_key: "assets.illegal_transition",
            params: { from: "active", to: "in_repair" },
            br_ref: "BR-AST-020",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
    });
    let refusal: ApiError | null = null;
    try {
      await logAssetMaintenance(
        "a-4022",
        { kind: "repair", detail: "x", status: "in_repair" },
        client,
      );
    } catch (error) {
      refusal = isApiError(error) ? error : null;
    }
    expect(refusal?.brRef).toBe("BR-AST-020");
    expect(apiErrorText(refusal, t)).toBe("An asset can't go from active straight to in_repair.");
  });

  it("§10-D3: the maintenance payload carries the captured cost", async () => {
    let sent: Record<string, unknown> = {};
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return new Response(
          JSON.stringify({ id: "m-1", asset: asset(), kind: "repair", date: "2026-08-16", resulting_status: "active" }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    await logAssetMaintenance(
      "a-4022",
      { kind: "repair", detail: "Seal replaced", cost: "31.00" },
      client,
    );
    expect(sent.cost).toBe("31.00");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// US-AST-008 — S54 / AST-08 retire (3-step wizard, TERMINAL)
// ══════════════════════════════════════════════════════════════════════════
describe("US-AST-008 — AST-08 retire wizard", () => {
  it("BR-SHL-032 / BR-AST-030: step 1 NAMES the action and says it cannot be undone", () => {
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/retire`,
      <AssetRetireWizard client={NOOP_CLIENT} today="2026-08-16" />,
      detail({ asset_no: "M-4204" }),
    );
    // Header rule 1 again: the action names the screen in the kicker, the number
    // is the title. "Retire M-4204" as one string is the pre-blueprint header.
    const retireKicker = html.slice(html.indexOf("kicker"), html.indexOf("<h1"));
    expect(retireKicker).toContain("Retire");
    expect(retireKicker).not.toContain("M-4204");
    expect(html.slice(html.indexOf("<h1"))).toContain("M-4204");
    expect(html).toContain("This cannot be undone");
    expect(html).toContain("Retiring, not deleting");
    expect(html).toContain("there is no un-retire");
    // The three-step rail is on screen — r10 AST-08's shape.
    expect(html).toContain("Reason &amp; final read");
    expect(html).toContain("Replacement");
    expect(html).toContain("Book value");
    // The final read for a MEASURING asset carries its unit (CLAUDE.md #3)…
    expect(html).toContain("Final read (kgal)");
    // …and the r10 lines this build OMITS by ruling stay omitted: no billing
    // hook and no rating math on an assets flow (B16 §7 / D2's omissions).
    expect(html).not.toContain("Bill the final read");
    expect(html).not.toContain("$12.24");
    const lower = html.toLowerCase();
    for (const forbidden of [">un-retire<", ">reactivate<", ">restore<", ">undo<"]) {
      expect(lower).not.toContain(forbidden);
    }
  });

  it("BR-AST-021: the four ratified reasons — the CATALOG's, not r10's stale list", () => {
    expect([...RETIRE_REASON_VALUES]).toEqual(["end_of_life", "failed", "replaced", "removed"]);
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/retire`,
      <AssetRetireWizard client={NOOP_CLIENT} today="2026-08-16" />,
      detail(),
    );
    for (const label of ["End of life", "Failed / unrepairable", "Replaced", "Removed from service"]) {
      expect(html).toContain(label);
    }
    // r10's own step-1 options are NOT ratified reasons and must not render.
    expect(html).not.toContain("Upgraded to AMI");
    expect(html).not.toContain("Premises demolished");
  });

  it("D4 / BR-AST-047: step 3 draws the SERVER's book value and the treatment radio — and NO GL account", () => {
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/retire?step=3`,
      <AssetRetireWizard client={NOOP_CLIENT} today="2026-08-16" />,
      detail(),
    );
    expect(html).toContain("data-book-value");
    // The r10 worked case at the formula's own figures (displayed 2 dp).
    expect(html).toContain("$164.00");
    expect(html).toContain("$19.82");
    expect(html).toContain("$144.18");
    expect(html).toContain("2 yrs 5 mo of 20");
    // The three ruled treatments…
    expect(html).toContain("Write off the remaining book value");
    expect(html).toContain("Claim under warranty first");
    expect(html).toContain("Hold pending supplier credit");
    // …and hard rule 5 / D3-D4: no GL account, no posting sentence, anywhere.
    expect(html).not.toContain("5400");
    expect(html).not.toContain("Depreciation Aug");
    expect(html).toContain("Nothing is posted to the ledger");
  });

  /**
   * ── B14 RULE 6, ASKED OF RENDERED OUTPUT — DEF-718 ────────────────────────
   *
   * Rule 6 names *retire* as its second example, and this screen's commit reads
   * "Retire M-4204 ✓". It rendered in the PRIMARY tier — the same button as
   * Save — from the day it shipped: `WizardFrame` offered no danger tier at all
   * until DEF-712, and this build's own E4 exception said so and pointed at the
   * sweep. PO ruling 2026-08-26 approved it; the wizard now declares
   * `commitVariant="danger"`.
   *
   * ⚠ **THE ASSERTION IS THE COMMIT BUTTON'S OWN RENDERED `class` ATTRIBUTE**,
   * pinned at both quotes, and the button is found by the copy it carries — the
   * step rail and Back are buttons too, and a token asserted against the whole
   * document would let any of them answer for the commit.
   */
  it("B14 rule 6 (DEF-718) — the RETIRE commit wears the DANGER tier, not the primary", () => {
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/retire?step=3`,
      <AssetRetireWizard client={NOOP_CLIENT} today="2026-08-16" />,
      detail({ asset_no: "M-4204" }),
    );
    const commit = buttonTagLabelled(html, "Retire M-4204");
    expect(commit).toContain('data-variant="danger"');
    expect(commit).toContain(`class="${buttonClasses("danger")}"`);
    // Outlined at rest, FILLED on hover — rule 6's own words, both halves.
    expect(commit).toContain("bg-transparent");
    expect(commit).toContain("border-danger-500");
    expect(commit).toContain("hover:not-disabled:bg-danger-700");
    // …and never the standard primary.
    expect(commit).not.toContain('data-variant="primary"');
    expect(commit).not.toContain("bg-accent");
    // The tier is a COLOUR: Back is untouched, so the sweep has not repainted
    // the frame's other controls on the way past.
    expect(buttonTagLabelled(html, "Back")).not.toContain("border-danger-500");
  });

  it("D4: step 3's HONEST empty state when no purchase cost is recorded", () => {
    const noCost = detail({
      valuation: {
        ...detail().valuation,
        purchase_cost: null,
        present_value: null,
        accumulated_depreciation: null,
        age_months: null,
        life_months: null,
      },
    });
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/retire?step=3`,
      <AssetRetireWizard client={NOOP_CLIENT} today="2026-08-16" />,
      noCost,
    );
    expect(html).toContain("data-book-value-absent");
    expect(html).toContain("No purchase cost recorded");
    // No treatment radio to skip and none demanded — nothing invented.
    expect(html).not.toContain("Write off the remaining book value");
    expect(hasBookValue(noCost)).toBe(false);
    expect(retireStepValid(3, initialRetireValues(), false)).toBe(true);
  });

  it("D4: with a book value the step-3 radio is NOT skippable, and the payload carries the choice", () => {
    const values = initialRetireValues();
    expect(retireStepValid(3, values, true)).toBe(false);
    const chosen = { ...values, reason: "end_of_life", book_value_treatment: "write_off" as const };
    expect(retireStepValid(3, chosen, true)).toBe(true);
    expect(retirePayload(chosen)).toEqual({
      reason: "end_of_life",
      book_value_treatment: "write_off",
    });
    // The final read travels only when a VALUE was entered; its date rides
    // with it, never alone.
    expect(
      retirePayload({
        ...chosen,
        final_read_value: "42912",
        final_read_date: "2026-08-16",
      }),
    ).toEqual({
      reason: "end_of_life",
      book_value_treatment: "write_off",
      final_read_value: "42912",
      final_read_date: "2026-08-16",
    });
  });

  it("B16 Item 3d: a NON-measuring device's step 1 has no final-read fields", () => {
    const device = detail({
      id: "a-3301",
      asset_no: "BF-3301",
      type: "backflow",
      type_name: "Backflow preventer",
      tab: "behind_the_meter",
      unit: null,
      meter_type: null,
      meter_type_name: null,
    });
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-3301/retire`,
      <AssetRetireWizard client={NOOP_CLIENT} today="2026-08-16" />,
      device,
    );
    expect(html).not.toContain("Final read");
    expect(html).toContain("Retiring, not deleting"); // the info box stays
  });

  it("the replacement picker offers IN-INVENTORY stock only, never the retiring asset", () => {
    const rows = [
      asset({ id: "a-5099", asset_no: "M-5099", behavior_class: "available" }),
      asset({ id: "a-4022", asset_no: "M-4022", behavior_class: "available" }),
      asset({ id: "a-4100", asset_no: "M-4100", behavior_class: "in_service" }),
    ];
    expect(replacementOptions(rows, { id: "a-4022" })).toEqual([
      { value: "M-5099", label: "M-5099 · Meter" },
    ]);
  });

  it("US-AST-008 TC-1: retire posts reason, date, replacement — and the W4 fields when given", async () => {
    let sent: Record<string, unknown> = {};
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return new Response(
          JSON.stringify(asset({ status: "retired", behavior_class: "terminal" })),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    const retired = await retireAsset(
      "a-4204",
      {
        reason: "failed",
        retire_date: "2026-08-08",
        replaced_by: "M-5100",
        book_value_treatment: "write_off",
      },
      client,
    );
    expect(sent).toEqual({
      reason: "failed",
      retire_date: "2026-08-08",
      replaced_by: "M-5100",
      book_value_treatment: "write_off",
    });
    expect(retired.status).toBe("retired");
  });

  it("BR-AST-030: this app exposes NO un-retire wrapper of any kind", () => {
    const names = Object.keys(endpoints).map((name) => name.toLowerCase());
    for (const forbidden of ["unretire", "reactivateasset", "restoreasset", "unarchiveasset"]) {
      expect(names).not.toContain(forbidden);
    }
    expect(names).toContain("retireasset");
    expect(names).toContain("reassignasset");
    expect(names).toContain("logassetmaintenance");
  });

  it("US-AST-008 TC-4/TC-9: the terminal and role refusals render in plain language", () => {
    const terminal = new ApiError(409, {
      code: "BIZ-IMMUTABLE",
      message_key: "assets.retired_is_terminal",
      params: { asset_no: "M-4204" },
      br_ref: "BR-AST-030",
    });
    expect(apiErrorText(terminal, t)).toContain("M-4204 is retired");
    const denied = new ApiError(403, {
      code: "AUTH-002",
      message_key: "errors.auth-002",
      br_ref: "BR-AST-032",
    });
    expect(denied.status).toBe(403);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// US-AST-009 — S55 / AST-06 reassign (full page) with final-read capture
// ══════════════════════════════════════════════════════════════════════════
describe("US-AST-009 — AST-06 reassign", () => {
  it("US-AST-009 TC-1 / BR-AST-022: the final read defaults ON, with VALUE **and DATE** inputs", () => {
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/reassign`,
      <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" />,
      detail(),
    );
    expect(html).toContain("Currently: Unit A");
    // ⚠ **THE LABEL LOST ITS LAST TWO WORDS.** Figure 32 (p88, REDRAWN) draws
    // the checkbox as `Record the final read`. The reading field beside it still
    // carries the asset's own unit, and the box still defaults ON — only the
    // words moved, and rule 33 caps a label at three words plus what it needs.
    expect(html).toContain("Record the final read");
    expect(html).toContain('checked=""');
    // CLAUDE.md #3: the reading field carries the asset's own unit of measure.
    expect(html).toContain("Final register reading (kgal)");
    // The B16-noted design gap, CLOSED: r10 draws only the checkbox — a
    // checkbox cannot CAPTURE a read, so value + date render with it.
    expect(html).toContain('id="final_read_value"');
    expect(html).toContain('id="final_read_date"');
    expect(html).toContain("The read and the move commit together");
    // ⚠ **r10's NOTE CALLOUT MOVED, AND THIS ASSERTION NOW PINS THE MOVE.** It
    // read `toContain("Reads stay with the meter")` — beside the form, which is
    // exactly what page 88 says to stop doing: the two consequence sentences
    // "already exist, unrendered at this moment … The fix is to show them
    // **before** the commit rather than beside the form." Figure 32's redrawn
    // flow puts them on a confirm panel reached by Continue.
    //
    // So the direction is asserted, not the absence: they must NOT be beside the
    // form. **THE CONFIRM PANEL ITSELF IS NOT COVERED HERE AND THIS FILE CANNOT
    // COVER IT** — it renders statically and cannot press Continue. That gap is
    // filed rather than papered over; saying so is the point, because an
    // assertion deleted in silence is how a screen loses a sentence for good.
    expect(html).not.toContain("Reads stay with the meter");
    // BR-SHL-033: the unit picker is searchable, the date is a picker.
    expect(html).toContain('role="combobox"');
    expect(html).toContain('type="date"');
    expect(unitPickerOptions(UNITS)).toEqual([{ value: "u-224", label: "2200 Riverside · 224" }]);
  });

  it("DEF-593 (CR-028 debt sweep): `?unit=` PRESELECTS the destination unit — the unit tab's door lands here filled in", () => {
    // The PRM-03 Assets tab's "+ Assign from inventory" picker navigates to
    // this page with `?unit=<id>`. The preselect is a PREFILL of the same
    // visible picker — the operator still sees and can change it.
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/reassign?unit=u-224`,
      <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" />,
      detail(),
    );
    expect(html).toContain('value="2200 Riverside · 224"');
    // Without the query param nothing is preselected — the prefill never guesses.
    const bare = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/reassign`,
      <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" />,
      detail(),
    );
    expect(bare).not.toContain('value="2200 Riverside · 224"');
  });

  it("US-AST-009 TC-4: a NON-measuring device has no read to take, and the page says so", () => {
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4420/reassign`,
      <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" />,
      detail({
        id: "a-4420",
        asset_no: "COM-4420",
        type: "comms",
        type_name: "Comms endpoint",
        tab: "behind_the_meter",
        unit: null,
        meter_type: null,
        meter_type_name: null,
      }),
    );
    expect(html).toContain("This device does not measure");
    expect(html).not.toContain("Record the final read before moving");
  });

  it("BR-AST-022: when the final read CANNOT be captured the server refuses the whole move — rendered honestly", async () => {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            code: "BIZ-COMPLETENESS",
            message_key: "assets.final_read_capture_unavailable",
            params: { asset_no: "M-4022", owner: "metering reads lane (W2)" },
            br_ref: "BR-AST-022",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
    });
    let refusal: ApiError | null = null;
    try {
      await reassignAsset("a-4022", { unit_id: "u-224", record_final_read: true }, client);
    } catch (error) {
      refusal = isApiError(error) ? error : null;
    }
    expect(refusal).not.toBeNull();
    expect(refusal?.status).toBe(422);
    expect(refusal?.brRef).toBe("BR-AST-022");
    const message = apiErrorText(refusal, t);
    expect(message).toContain("M-4022");
    expect(message).toContain("Nothing was moved");
    // DEF-322: the internal `owner` never reaches the sentence on screen.
    expect(message).not.toContain("W2");
    expect(message).not.toContain("lane");
    expect(formErrorEnvelope(refusal as ApiError).field_errors).toEqual([]);
  });

  it("US-AST-009 TC-8 / BR-AST-037: an independent sub-meter move is ALLOWED, with a warning", async () => {
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-8801/reassign`,
      <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" />,
      detail({
        id: "a-8801",
        asset_no: "SM-8801",
        type: "sub_meter",
        type_name: "Sub-meter",
        tab: "sub_meters",
        parent_asset_no: "M-MASTER-12",
      }),
    );
    expect(html).toContain("moving independently of its parent M-MASTER-12");
    expect(
      reassignWarningKey({ code: "independent_sub_meter_move", parent: "M-MASTER-12" }),
    ).toBe("assets.reassign.warning.independentSubMeter");
    expect(
      t("assets.reassign.warning.independentSubMeter", { parent: "M-MASTER-12" }),
    ).toContain("M-MASTER-12");

    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            ...asset(),
            warnings: [{ code: "independent_sub_meter_move", parent: "M-MASTER-12" }],
            final_read: null,
            children_moved: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    });
    const moved = await reassignAsset(
      "a-8801",
      { unit_id: "u-224", record_final_read: false },
      client,
    );
    expect(moved.warnings[0].code).toBe("independent_sub_meter_move");
  });

  it("US-AST-009 TC-9 / BR-AST-037: a parent move offers the children prompt, defaulting to YES", () => {
    const html = renderFlow(
      `/${TEST_TENANT}/assets/a-4022/reassign`,
      <AssetReassignPage client={NOOP_CLIENT} today="2026-08-16" />,
      detail({
        asset_no: "M-MASTER-12",
        sub_assets: [{ id: "a-8801", asset_no: "SM-8801", type: "sub_meter" }],
      }),
    );
    expect(html).toContain("Move its sub-meters too");
    expect(reassignWarningKey({ code: "children_not_moved", children: ["SM-8801"] })).toBe(
      "assets.reassign.warning.childrenNotMoved",
    );
    expect(reassignWarningKey({ code: "something_new" })).toBe(
      "assets.reassign.warning.generic",
    );
  });

  it("US-AST-009 TC-3 / BR-AST-022: moving to Inventory is the other destination, and it unassigns", async () => {
    let sent: Record<string, unknown> = {};
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        sent = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return new Response(
          JSON.stringify({
            ...asset({ status: "inventory", behavior_class: "available", assigned: false }),
            warnings: [],
            final_read: null,
            children_moved: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      },
    });
    const moved = await reassignAsset(
      "a-4022",
      { to_inventory: true, effective_date: "2026-08-08", record_final_read: false },
      client,
    );
    expect(sent.to_inventory).toBe(true);
    expect(moved.status).toBe("inventory");
  });

  it("BR-AST-036/038: the bulk failure codes render as language, and name the alternative", () => {
    expect(bulkAssignFailureKey("not_inventory")).toBe("assets.bulk.error.notInventory");
    expect(bulkAssignFailureKey("unknown_asset")).toBe("assets.bulk.error.unknownAsset");
    expect(bulkAssignFailureKey("something_else")).toBe("assets.bulk.error.generic");
    expect(t("assets.bulk.error.notInventory", { asset: "M-4021" })).toContain(
      "move it on its own or by file import",
    );
  });

  it.todo(
    "US-AST-009 TC-5/TC-6: an overlapping effective date and an over-register final read are SERVER verdicts — asserted in the backend suite",
  );
  it.todo(
    "US-AST-009 TC-7 (isolation): the unit picker and the API expose only this tenant's units — server/RLS scope (G5)",
  );
  it.todo(
    "browser scope → Playwright: switching Move-to, entering the final read and submitting the full pages",
  );
});

// ══════════════════════════════════════════════════════════════════════════
// US-AST-002 amended — AST-05 add wizard (the pure halves)
// ══════════════════════════════════════════════════════════════════════════
describe("CR-028 AST-W4 — AST-05 add wizard laws", () => {
  it("§10-D8: step validity — type, sub-meter parent, UoM+multiplier, assign-needs-unit+date", () => {
    const base = initialAddValues("meters");
    expect(stepValid(1, base)).toBe(false); // no type yet
    // ⚠ **AND NO SERVICE EITHER, SINCE `DEF-MET-4981`.** This line read
    // `expect(stepValid(1, { ...base, type: "meter" })).toBe(true)` and the
    // server refused exactly that payload with 422 `assets.service_required`
    // three steps later. BR-AST-009 is mirrored on the step now.
    expect(stepValid(1, { ...base, type: "meter" })).toBe(false);
    expect(stepValid(1, { ...base, type: "meter", service: "water" })).toBe(true);
    // Whitespace is not an answer — the server trims and so does the step.
    expect(stepValid(1, { ...base, type: "meter", service: "   " })).toBe(false);
    // BR-AST-003: a sub-meter without its master cannot leave step 1.
    const sub = { ...initialAddValues("sub_meters"), type: "sub_meter", service: "water" };
    expect(stepValid(1, sub)).toBe(false);
    expect(stepValid(1, { ...sub, parent_asset_no: "M-MASTER-12" })).toBe(true);
    // ⚠ A NON-MEASURING DEVICE STILL NEEDS NONE — BR-AST-009 refuses a service
    // requirement on equipment that belongs to a customer rather than to a
    // connection, and `_check_measuring_requirements` returns early for it.
    const device = { ...initialAddValues("behind_the_meter"), type: "backflow" };
    expect(requiresService("behind_the_meter")).toBe(false);
    expect(stepValid(1, device)).toBe(true);
    // BR-AST-009 / CLAUDE.md #3: a measuring kind needs an explicit UoM.
    expect(stepValid(2, { ...base, type: "meter", unit: "" })).toBe(false);
    expect(stepValid(2, { ...base, type: "meter", unit: "kWh" })).toBe(true);
    // `DEF-MET-4983` — "untouched" is what decides whether a `?step=` past the
    // first is honoured, and it is measured against the baseline rather than
    // tracked in a flag a reload would destroy.
    expect(isUntouched(base, "meters")).toBe(true);
    expect(isUntouched({ ...base, service: "water" }, "meters")).toBe(false);
    expect(isUntouched({ ...base, raise_work_order: true }, "meters")).toBe(false);
    // The class comes from the address, so it is never an answer.
    expect(isUntouched(initialAddValues("sub_meters"), "sub_meters")).toBe(true);
    // BR-AST-011: assign-on-create needs the seat AND its install date.
    const assigning = { ...base, type: "meter", destination: "unit" as const };
    expect(stepValid(3, assigning)).toBe(false);
    expect(stepValid(3, { ...assigning, unit_id: "u-224", install_date: "2026-08-16" })).toBe(true);
  });

  it("the create payload carries what was entered and nothing empty — valuation fields included", () => {
    const values = {
      ...initialAddValues("meters"),
      type: "meter",
      asset_no: "M-5101",
      unit: "kWh",
      multiplier: "1",
      supplier: "Itron Inc",
      purchase_cost: "164.00",
      expected_life_years: "20",
    };
    const payload = addPayload(values);
    expect(payload).toMatchObject({
      type: "meter",
      asset_no: "M-5101",
      unit: "kWh",
      multiplier: "1",
      supplier: "Itron Inc",
      purchase_cost: "164.00",
      expected_life_years: "20",
    });
    // Nothing empty travels; no uuid is ever sent (BR-AST-026).
    expect(payload).not.toHaveProperty("id");
    expect(payload).not.toHaveProperty("serial_no");
    expect(payload).not.toHaveProperty("warranty_end");
  });

  it("BR-AST-003 / §5.1b (B): masters are ACTIVE meters; inverter links narrow to NET meters", () => {
    const rows = [
      asset({ id: "m1", asset_no: "M-4310", type: "net_meter", net_metering: true }),
      asset({ id: "m2", asset_no: "M-4022", type: "meter", net_metering: false }),
      asset({ id: "m3", asset_no: "M-5099", type: "meter", behavior_class: "available" }),
      asset({ id: "s1", asset_no: "SM-8801", type: "sub_meter" }),
    ];
    expect(mastersFor(rows, "parent").map((o) => o.value)).toEqual(["M-4310", "M-4022"]);
    expect(mastersFor(rows, "net").map((o) => o.value)).toEqual(["M-4310"]);
  });

  it("BR-AST-026/033: the availability callout has three honest states", () => {
    expect(numberAvailabilityKey("", { available: null })).toBe(null);
    expect(numberAvailabilityKey("M-5101", null)).toBe(null);
    expect(numberAvailabilityKey("M-5101", { available: true })).toBe("available");
    expect(numberAvailabilityKey("M-5101", { available: false })).toBe("taken");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-008@e1a4db0 (story+rules snapshot hash — EP-AST-03; co-stories US-AST-007@e1a4db0 · US-AST-009@e1a4db0) · CR-028@B16 (§5.2 as amended + §10 D3/D4/D7/D8)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane) · REWRITTEN 2026-08-22 by the CR-028 AST-W4 lane (the three modals became the AST-06/07/08 full pages; every render goes through the ROUTER now, the pure-law tests are unchanged, and the W4 laws — not-modal, "Work R5" verbatim, D3's absent posting control, D4's step 3 both states — are pinned here)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (this file) · trace_lint✔
// exceptions: E4 the BR-AST-022 refusal is the LIVE behaviour on this deployment (metering's capture seam is unwired), so the test asserts the refusal renders and the asset stays put — the rule working · E4 the isolation halves are the G5 suite's, on live Postgres · E4 submitting/stepping the pages is browser scope (no DOM environment in vitest) — the step-3 render is reached through the wizard's URL step state instead
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
