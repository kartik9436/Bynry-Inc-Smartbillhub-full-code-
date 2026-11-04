// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-037 · US-WRK-038 (EP-WRK-07) — the rules screen, the
//           rule builder (three steps since CR-168 round 5), and the four controls that now open the
//           Assets door. Screens: Work-026, Work-028.
// Rules:    BR-WRK-033 · BR-WRK-056 · B14 rules 21 · 31 · 32 · hard-won law 2
//           and its mirror clause
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE DESTINATIONS ARE ASSERTED AGAINST THE ROUTER, NOT AGAINST THE SCREEN
 * REGISTRY, AND THE DIFFERENCE IS NOT PEDANTRY.** `SCREEN_ROUTES` is a TABLE
 * somebody maintains; `APP_ROUTES` is what react-router actually serves. They
 * are kept identical by one assertion in `screenIds.test.tsx` — and that
 * assertion was RED on this branch when wave M started, because wave N had
 * mounted two routes and added no rows (`DEF-WRK-4076`). A control checked
 * against the registry in that state is checked against a list that does not
 * describe the running app.
 *
 * So every case below flattens `APP_ROUTES` the way `matchPath` reads it and
 * asks the router.
 */
import { describe, expect, it } from "vitest";
import type { RouteObject } from "react-router-dom";

import { APP_ROUTES } from "@/App";
import { WORK_RULE_EDIT_ROUTE } from "./RuleBuilder";
import { WORK_RULE_DETAIL_ROUTE } from "./RuleDetailPage";
import { RULE_COLUMNS, WORK_RULE_BUILDER_ROUTE } from "./RulesPage";
import { RULE_BUILDER_STEPS, moduleWord, processWord } from "./rules/ruleModel";
import type { RuleProcesses } from "./rules/ruleEndpoints";
import RECORDED_PROCESSES from "./__fixtures__/server/work.rules.processes.json";
import { WORK_RULES_ROUTE, WORK_TABS } from "./WorkShell";
import { RAISE_WORK_ORDER_ROUTE, raiseWorkOrderPath } from "@/features/assets/RaiseWorkOrderPage";
import i18n from "@/i18n";

/** `matchPath`'s own reading of the route tree — see the file header. */
function flatten(routes: readonly RouteObject[], parent = ""): string[] {
  const out: string[] = [];
  for (const route of routes) {
    let here = parent;
    const structural = route.children !== undefined && route.element === undefined;
    if (route.index === true) {
      out.push(parent === "" ? "/" : parent);
    } else if (typeof route.path === "string") {
      here = route.path.startsWith("/")
        ? route.path
        : `${parent === "/" ? "" : parent}/${route.path}`;
      if (!structural) out.push(here);
    }
    if (route.children) out.push(...flatten(route.children, here));
  }
  return out;
}

const SERVED = new Set(flatten(APP_ROUTES));
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

describe("CR-070 wave M — the four doors reach the address the ROUTER serves", () => {
  it("the Assets door is a route react-router actually serves", () => {
    expect(SERVED.has(`/:tenant${RAISE_WORK_ORDER_ROUTE}`)).toBe(true);
  });

  it("it is a SIBLING of the maintenance form, which is BR-WRK-056's own word", () => {
    expect(SERVED.has("/:tenant/assets/:assetId/maintenance/new")).toBe(true);
    expect(RAISE_WORK_ORDER_ROUTE).toBe("/assets/:assetId/work-orders/new");
  });

  it("the path builder produces an address that MATCHES the served pattern", () => {
    // ⚠ A control can hold a perfectly good-looking string that no route
    // serves. `raiseWorkOrderPath` fills the parameter in; this rebuilds the
    // pattern from it and asks the router about THAT.
    const built = raiseWorkOrderPath("a-4022");
    expect(built).toBe("/assets/a-4022/work-orders/new");
    const pattern = built.replace("a-4022", ":assetId");
    expect(SERVED.has(`/:tenant${pattern}`)).toBe(true);
  });

  it("the rules list and its builder are both served, builder FIRST", () => {
    const served = flatten(APP_ROUTES);
    expect(served).toContain(`/:tenant${WORK_RULES_ROUTE}`);
    expect(served).toContain(`/:tenant${WORK_RULE_BUILDER_ROUTE}`);
    // The static `new` is declared before the list, so no looser pattern added
    // later can swallow it.
    expect(served.indexOf(`/:tenant${WORK_RULE_BUILDER_ROUTE}`)).toBeLessThan(
      served.indexOf(`/:tenant${WORK_RULES_ROUTE}`),
    );
  });

  it("NO ROUTE CONSTANT IN THIS MODULE CARRIES A TENANT SEGMENT (DEF-WRK-4051)", () => {
    // A constant that carried `:tenant` would come out `:tenant/:tenant/...`,
    // match nothing, and fall through to "This screen is not built yet" with
    // tsc, every test and G13 green over it.
    for (const route of [WORK_RULES_ROUTE, WORK_RULE_BUILDER_ROUTE, RAISE_WORK_ORDER_ROUTE]) {
      expect(route.startsWith("/")).toBe(true);
      expect(route).not.toContain(":tenant");
    }
  });
});

describe("CR-070 wave M — Work-026 draws what BR-WRK-033 asks for (image 56 since CR-168 round 5)", () => {
  it("nine columns, in image 56's order", () => {
    expect([...RULE_COLUMNS]).toEqual([
      "name",
      "source_module",
      "trigger_kind",
      "template",
      "priority",
      "this_month",
      "last_fired",
      "enabled",
      "actions",
    ]);
  });

  it("the Rules tab sits BETWEEN Templates and Performance", () => {
    const ids = WORK_TABS.map((tab) => tab.id);
    expect(ids).toContain("rules");
    expect(ids.indexOf("rules")).toBe(ids.indexOf("templates") + 1);
    expect(ids.indexOf("rules")).toBe(ids.indexOf("performance") - 1);
  });

  it("the Rules tab points at the address the router serves", () => {
    const tab = WORK_TABS.find((entry) => entry.id === "rules");
    expect(tab).toBeDefined();
    expect(SERVED.has(`/:tenant${tab!.path}`)).toBe(true);
  });

  it("the rule's own page and its edit address are served, AFTER the static `new`", () => {
    const served = flatten(APP_ROUTES);
    const at = (route: string) => served.indexOf(`/:tenant${route}`);
    expect(at(WORK_RULE_EDIT_ROUTE)).toBeGreaterThan(at(WORK_RULE_BUILDER_ROUTE));
    expect(at(WORK_RULE_DETAIL_ROUTE)).toBeGreaterThan(at(WORK_RULE_BUILDER_ROUTE));
  });

  it("NO CODE IS A VISIBLE VALUE — every recorded process and module has a word (B14 rule 31)", () => {
    const processes = RECORDED_PROCESSES as unknown as RuleProcesses;
    expect(processes.results).toHaveLength(12);
    for (const process of processes.results) {
      const label = processWord(process.key, processes, t);
      expect(label).not.toBe(process.key);
      expect(label).not.toContain("_");
      expect(moduleWord(process.module, t)).not.toContain("work.rules");
    }
  });
});

describe("CR-168 round 5 — the THREE-step builder (the 26 Sep ruling)", () => {
  it("has THREE steps, in image 57/59/61's order", () => {
    expect(RULE_BUILDER_STEPS.map((step) => step.id)).toEqual(["trigger", "notify", "review"]);
  });

  it("every step, process, module and vocabulary has copy in all ELEVEN catalogues", () => {
    const processes = RECORDED_PROCESSES as unknown as RuleProcesses;
    const locales = [
      "en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR",
    ];
    const keys = [
      "work.tabs.rules",
      "work.rules.title",
      // CR-168 round 3: the Assets door's one-page form (and its title and
      // consequence copy) is retired by ruling 35; the raise's own keys are
      // asserted by `raise/cr168Raise.dom.test.tsx`.
      "work.raise.fromAsset",
      ...RULE_BUILDER_STEPS.map((step) => step.labelKey),
      ...processes.results.map((process) => process.label_key),
      ...processes.results.map((process) => process.module_label_key),
      ...processes.results.flatMap((process) => process.params.map((param) => param.label_key)),
      ...processes.assign_kinds.map((kind) => `work.rules.assign.${kind}`),
      ...processes.escalation_kinds.map((kind) => `work.rules.escalation.${kind}`),
      ...processes.notify_when.map((when) => `work.rules.notify.when.${when}`),
      ...processes.notify_who.map((who) => `work.rules.notify.who.${who}`),
      ...Object.values(processes.escalation_events).map((event) => `notifications.rules.event.${event}`),
    ];
    for (const locale of locales) {
      for (const key of keys) {
        expect(i18n.exists(key, { lng: locale }), `${locale} is missing ${key}`).toBe(true);
      }
    }
  });

  it("THE RETIRED REFUSAL IS GONE FROM ALL ELEVEN CATALOGUES", () => {
    // `assets.flow.workR5` said "Work R5" over seven controls. The Work module
    // exists now and the door has an address, so the key goes with the refusal
    // it carried — hard-won law 2's mirror clause.
    for (const locale of [
      "en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR",
    ]) {
      expect(
        i18n.exists("assets.flow.workR5", { lng: locale }),
        `${locale} still carries the retired refusal`,
      ).toBe(false);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-WRK-4098 · THE SCREEN RENDERED ZERO RULES FOR EVERY TENANT
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY CASE ABOVE PASSED WHILE `Work-026` COULD NOT DRAW A SINGLE ROW.**
// They assert routes, column ids, tab order and label maps — none of them
// MOUNTS the page, so none of them ever asked what happens when the server
// answers. The server answers `{count, next, previous, results}` (the DRF
// envelope `apps/work/api._envelope` puts on every Work list); the page read
// `data.rows` and `data.total`, which are `undefined` in that payload, so it
// handed `DataTable` an empty array, `totalRows` fell to `null` → `0`, and the
// screen drew its zero-results state — *"No results for ''."* — over seven
// perfectly good rules. It was found by opening the page in a browser and by
// nothing else (CLAUDE.md hard-won law 6).
//
// ⚠ **`tsc` CANNOT SEE IT AND NEVER COULD.** `client.get<WorkRulesPage>()` is a
// type ASSERTION: the generic tells TypeScript what to pretend the JSON is, and
// nothing at runtime compares the two. A wrong interface is invisible to the
// compiler precisely because the compiler believes it.
//
// So this case mounts the page with **the envelope the server really sends**
// and asserts rows reach the table. A future edit back to `rows`/`total` fails
// here instead of on a demo.
describe("DEF-WRK-4098 · the payload shape the server actually sends", () => {
  const ENVELOPE = {
    count: 7,
    next: null,
    previous: null,
    results: [
      {
        id: "01a0-rule-1",
        name: "Asset age rule",
        source_module: "assets",
        trigger_kind: "asset_past_certification_life",
        params: {},
        template: { id: "t-1", name: "Meter exchange — residential" },
        priority: { id: "p-1", name: "Normal" },
        assignment: {},
        assign_to: { kind: "nobody", id: null },
        triggers: [{ seq: 1, kind: "asset_age_rule", params: {}, module: "assets", moment: "overnight" }],
        notifications: [],
        escalation: {},
        escalations: [],
        enabled: true,
        incomplete: [],
        this_month: 3,
        jobs_raised: 3,
        last_fired_at: null,
      },
    ],
  };

  it("carries `results` and `count`, never `rows`/`total` — the keys the page reads", () => {
    // The shape assertion on its own, so the failure NAMES the cause rather
    // than showing an empty table and leaving the reader to guess.
    expect(Object.keys(ENVELOPE).sort()).toEqual(["count", "next", "previous", "results"]);
    expect(ENVELOPE).not.toHaveProperty("rows");
    expect(ENVELOPE).not.toHaveProperty("total");
  });

  it("renders a row from that envelope, and counts the enabled ones", async () => {
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { renderToStaticMarkup } = await import("react-dom/server");
    const { MemoryRouter, Route, Routes } = await import("react-router-dom");
    const { ToastProvider } = await import("@/components/Toast");
    const { DEFAULT_PAGE_SIZE } = await import("@/components/tableTypes");
    const RulesPage = (await import("./RulesPage")).default;

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, enabled: false } },
    });
    // ⚠ **PRIME THE CACHE WITH WHAT THE QUERY FUNCTION RETURNS, NOT WITH WHAT
    // THE WIRE CARRIES — AND THE DIFFERENCE IS THE POINT OF `DEF-WRK-4119`.**
    // This line used to store `ENVELOPE` itself, which only worked while
    // `listWorkRules` was an identity function over the response body. It no
    // longer is: `readListPage` unwraps the envelope (and asserts it) so the
    // screen is handed `{rows, total}` and no screen in this product describes
    // a paged reply any more. `unwrapPage` is used here rather than a
    // hand-written `{rows: ENVELOPE.results, total: ENVELOPE.count}` so this
    // fixture goes through the SAME reader the page does — a second
    // transcription here would be the original defect, in a test file.
    const { unwrapPage } = await import("@/api/paginated");
    queryClient.setQueryData(
      ["work", "rules", "", 1, DEFAULT_PAGE_SIZE],
      unwrapPage("/work/rules", ENVELOPE),
    );

    // Mounted under the REAL path pattern — hard-won law 2's fixture clause:
    // bare in a MemoryRouter, `useParams().tenant` is undefined and every
    // address the page builds comes out `//…`, which reads as a fine string.
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/work/rules"]}>
            <Routes>
              <Route path="/:tenant/work/rules" element={<RulesPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    expect(html).toContain("Asset age rule");
    // The zero-results state is what shipped; it must not be what renders.
    expect(html).not.toContain("No results for");
    // `onCount` reads the same rows — the consequence box said "0 rules" while
    // seven were on file, which is the same bug wearing a different sentence.
    expect(html).not.toContain(">0 rules");
  });
});
