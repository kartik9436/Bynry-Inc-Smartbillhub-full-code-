// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane RULES — the Rules list (image 56), the
//           three-step builder (57, 59, 61) and one rule's page (62–64),
//           mounted on the SERVER'S RECORDED answers (CR-168 §7.3, *"Fixtures
//           come from the server"*).
// Defects:  DEF-WRK-9564 (no + New rule, no row actions, no rule page) ·
//           DEF-WRK-9573 (the search did nothing) · DEF-WRK-5066 (a
//           hand-rolled five-step rail instead of the shared WizardFrame)
// Tasks:    P3.16–P3.19 · P3.37 · P3.39 · P3.60 · P3.62–P3.64 · P3.66 · P3.67
// ───────────────────────────────────────────────────────
//
// ⚠ **WRITTEN RED FIRST.** Each case below was run on the tip before this
// lane's screens (`3cd891cfb`) and failed there; the failures are quoted in
// `CR-168-BRC10` §21. Mounted under the REAL path pattern every time — a bare
// `MemoryRouter` builds `//…` addresses that read as fine strings
// (`DEF-CWP-3925`).
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";
import type { RouteObject } from "react-router-dom";

import "@/i18n";
import i18n from "@/i18n";
import { APP_ROUTES } from "@/App";
import { resolveScreen } from "@/routing/screenIds";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { RuleBuilder } from "../RuleBuilder";
import { RulesPage } from "../RulesPage";

import RULES from "../__fixtures__/server/work.rules.json";
import RULE from "../__fixtures__/server/work.rule.json";
import RULE_JOBS from "../__fixtures__/server/work.rule.jobs.json";
import RULE_AUDIT from "../__fixtures__/server/work.rule.audit.json";
import PROCESSES from "../__fixtures__/server/work.rules.processes.json";
import TEMPLATES from "../__fixtures__/server/work.templates.json";
import RAISE_OPTIONS from "../__fixtures__/server/work.raise-options.json";
import TECHNICIANS_VIEW from "../__fixtures__/server/work.crews.technicians.json";
import CREWS_VIEW from "../__fixtures__/server/work.crews.crews.json";
import CONTRACTORS_VIEW from "../__fixtures__/server/work.crews.contractors.json";
import STAFF from "../__fixtures__/server/work.technicians.json";
import NOTIFICATION_RULES from "../__fixtures__/server/work.rules.lookup.notification-rules.json";
import SERVICES from "../__fixtures__/server/work.rules.lookup.services.json";
import ROLES from "../__fixtures__/server/work.rules.lookup.roles.json";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const RULE_ID = (RULE as { id: string }).id;
const EMPTY_PAGE = { count: 0, next: null, previous: null, results: [] };

interface Call {
  method: string;
  path: string;
  query: Record<string, unknown>;
  body: unknown;
}

/** Answers ONLY the recorded bodies, by path; an unknown path THROWS rather
 *  than answering `{}`, so *asked the wrong address* never reads as *empty*. */
function recordingClient(calls: Call[]): ApiClient {
  const reply = async (method: string, path: string, options?: { query?: Record<string, unknown> }, body?: unknown): Promise<ApiResponse<unknown>> => {
    const query = options?.query ?? {};
    calls.push({ method, path, query, body });
    const ok = (data: unknown): ApiResponse<unknown> => ({ status: 200, data, etag: null, notModified: false });
    if (method === "POST" && path === "/work/rules/preview") return ok({ subjects: 48, would_raise: 47, already_open: 0, cannot_raise: 1, cannot_raise_reasons: { "work.order.asset_type_not_on_template": 1 } });
    if (method === "POST" && path === "/work/rules") return ok(RULE);
    if (method === "POST" && /\/work\/rules\/[^/]+\/(enable|disable)$/.test(path)) return ok(RULE);
    if (path === "/work/rules/processes") return ok(PROCESSES);
    if (path.endsWith("/jobs") && path.startsWith("/work/rules/")) return ok(RULE_JOBS);
    if (path.endsWith("/audit") && path.startsWith("/work/rules/")) return ok(RULE_AUDIT);
    if (path.startsWith("/work/rules/")) return ok(RULE);
    if (path === "/work/rules") {
      // The server's own search: name, template and process words. The
      // recording is filtered by NAME here, which is enough to see whether the
      // screen sent the term at all.
      const q = String(query.q ?? "").toLowerCase();
      const rows = (RULES as { results: { name: string }[] }).results.filter(
        (row) => q === "" || row.name.toLowerCase().includes(q),
      );
      return ok({ count: rows.length, next: null, previous: null, results: rows });
    }
    if (path === "/work/templates") return ok(TEMPLATES);
    if (path === "/work/raise-options") return ok(RAISE_OPTIONS);
    if (path === "/work/crews") {
      const view = query.view;
      return ok(view === "technicians" ? TECHNICIANS_VIEW : view === "crews" ? CREWS_VIEW : CONTRACTORS_VIEW);
    }
    if (path === "/work/technicians") return ok(STAFF);
    if (path === "/roles") return ok(ROLES);
    if (path === "/settings/services") return ok(SERVICES);
    if (path === "/notification-rules") return ok(NOTIFICATION_RULES);
    if (path.startsWith("/lookups/")) return ok(EMPTY_PAGE);
    throw new Error(`no recording for ${method} ${path}`);
  };
  return {
    get: (path: string, options?: { query?: Record<string, unknown> }) => reply("GET", path, options),
    post: (path: string, body?: unknown) => reply("POST", path, undefined, body),
    patch: (path: string, body?: unknown) => reply("PATCH", path, undefined, body),
    put: (path: string, body?: unknown) => reply("PUT", path, undefined, body),
    del: (path: string) => reply("DELETE", path),
  } as unknown as ApiClient;
}

function mountAt(path: string, routes: { pattern: string; element: ReactElement }[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            {routes.map((route) => (
              <Route key={route.pattern} path={route.pattern} element={route.element} />
            ))}
            <Route path="*" element={<p data-landed="">landed</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function flatten(routes: readonly RouteObject[], parent = ""): string[] {
  const out: string[] = [];
  for (const route of routes) {
    let here = parent;
    if (typeof route.path === "string") {
      here = route.path.startsWith("/") ? route.path : `${parent === "/" ? "" : parent}/${route.path}`;
      if (!(route.children !== undefined && route.element === undefined)) out.push(here);
    }
    if (route.children) out.push(...flatten(route.children, here));
  }
  return out;
}

afterEach(cleanup);

describe("DEF-WRK-9564 · P3.16 · P3.63 — the list keeps its create, and every row opens, edits and duplicates", () => {
  it("+ New rule sits in the header WITH seven rules on screen, and goes to the builder", async () => {
    const calls: Call[] = [];
    mountAt(`/${TENANT}/work/rules`, [
      { pattern: "/:tenant/work/rules", element: <RulesPage client={recordingClient(calls)} /> },
    ]);
    expect(await screen.findByText("Backflow test due")).toBeTruthy();
    const create = screen.getByRole("link", { name: t("work.rules.new") });
    expect(create.getAttribute("href")).toBe(`/${TENANT}/work/rules/new`);
    // P3.20 — the door names the SCREEN it opens, so a re-route goes red here.
    expect(resolveScreen(`/${TENANT}/work/rules/new`).r10).toBe("WRK-13");
  });

  it("each row carries open, edit and duplicate — to the rule's page, its builder and a copy", async () => {
    const calls: Call[] = [];
    mountAt(`/${TENANT}/work/rules`, [
      { pattern: "/:tenant/work/rules", element: <RulesPage client={recordingClient(calls)} /> },
    ]);
    const row = (await screen.findByText("Backflow test due")).closest("tr") as HTMLElement;
    const id = (RULES as { results: { id: string; name: string }[] }).results.find(
      (r) => r.name === "Backflow test due",
    )!.id;
    const href = (name: string) =>
      within(row).getByRole("link", { name: t(name, { name: "Backflow test due" }) }).getAttribute("href");
    expect(href("work.rules.action.open")).toBe(`/${TENANT}/work/rules/${id}`);
    expect(href("work.rules.action.edit")).toBe(`/${TENANT}/work/rules/${id}/edit`);
    expect(href("work.rules.action.duplicate")).toBe(`/${TENANT}/work/rules/new?from=${id}`);
    // P3.20 — each released door by the screen it opens (WRK-06.rule is the
    // rule's page, WRK-13 the builder), not only by its address.
    const screenOf = (name: string) => resolveScreen((href(name) ?? "").split("?")[0]).r10;
    expect(screenOf("work.rules.action.open")).toBe("WRK-06.rule");
    expect(screenOf("work.rules.action.edit")).toBe("WRK-13");
    expect(screenOf("work.rules.action.duplicate")).toBe("WRK-13");
    // B14 rule 31 — the id is in the address and nowhere in the row's text.
    expect(row.textContent).not.toContain(id);
  });

  it("LAST FIRED reads a date with its count, or Never", async () => {
    mountAt(`/${TENANT}/work/rules`, [
      { pattern: "/:tenant/work/rules", element: <RulesPage client={recordingClient([])} /> },
    ]);
    const fired = (await screen.findByText("Asset age rule")).closest("tr") as HTMLElement;
    expect(within(fired).getByText(t("work.rules.jobsRaised", { count: 3 }))).toBeTruthy();
    const never = screen.getByText("Backflow test due").closest("tr") as HTMLElement;
    expect(within(never).getByText(t("work.rules.never"))).toBeTruthy();
  });

  it("the rule's own page and its edit address are ROUTED (they opened 'not built yet')", () => {
    const served = flatten(APP_ROUTES);
    expect(served).toContain("/:tenant/work/rules/:ruleId");
    expect(served).toContain("/:tenant/work/rules/:ruleId/edit");
    expect(served.indexOf("/:tenant/work/rules/new")).toBeLessThan(served.indexOf("/:tenant/work/rules/:ruleId"));
  });
});

describe("DEF-WRK-9573 · P3.18 — the search searches", () => {
  it("typing a term sends it to the server as q, and the rows narrow", async () => {
    const calls: Call[] = [];
    mountAt(`/${TENANT}/work/rules`, [
      { pattern: "/:tenant/work/rules", element: <RulesPage client={recordingClient(calls)} /> },
    ]);
    await screen.findByText("Backflow test due");
    const box = screen.getByPlaceholderText(t("work.rules.search"));
    fireEvent.change(box, { target: { value: "Leak" } });
    // The search marks the matched letters, so the rows are read as text.
    await waitFor(
      () => {
        const text = document.querySelector("tbody")?.textContent ?? "";
        expect(text).toContain("Leak investigation");
        expect(text).not.toContain("Backflow test due");
      },
      { timeout: 3000 },
    );
    expect(calls.some((call) => call.path === "/work/rules" && call.query.q === "Leak")).toBe(true);
  });
});

describe("DEF-WRK-5066 · P3.19 · P3.64 — three steps on the shared WizardFrame", () => {
  it("mounts WizardFrame with Trigger · Notify · Review and no hand-rolled rail", async () => {
    mountAt(`/${TENANT}/work/rules/new`, [
      { pattern: "/:tenant/work/rules/new", element: <RuleBuilder client={recordingClient([])} /> },
    ]);
    await screen.findByRole("heading", { name: t("work.rules.builder.title") });
    expect(document.querySelector("[data-wizard='frame']")).not.toBeNull();
    expect(document.querySelector("[data-rule-steps]")).toBeNull();
    const rail = Array.from(document.querySelectorAll("[data-wizard-step]")).map((el) => el.textContent?.trim() ?? "");
    expect(rail).toHaveLength(3);
    expect(rail[0]).toContain(t("work.rules.builder.step.trigger"));
    expect(rail[1]).toContain(t("work.rules.builder.step.notify"));
    expect(rail[2]).toContain(t("work.rules.builder.step.review"));
  });
});

describe("P3.65 · P3.66 · P3.67 · P3.39 — every process from the form, two triggers, a message, an escalation", () => {
  it("builds a rule with two triggers, a customer message and an escalation that ALSO tells a role, and POSTs it", async () => {
    const calls: Call[] = [];
    mountAt(`/${TENANT}/work/rules/new`, [
      { pattern: "/:tenant/work/rules/new", element: <RuleBuilder client={recordingClient(calls)} /> },
    ]);
    // Step 1 — name, template, two triggers.
    const name = await screen.findByLabelText(new RegExp(t("work.rules.builder.name")));
    fireEvent.change(name, { target: { value: "Backflow test due" } });
    const template = await screen.findByLabelText(new RegExp(t("work.rules.builder.template")));
    await waitFor(() => expect((template as HTMLSelectElement).options.length).toBeGreaterThan(1));
    fireEvent.change(template, { target: { value: (template as HTMLSelectElement).options[1].value } });

    // README ruling 10: every one of the twelve processes is offered.
    const adder = await waitFor(() => {
      const el = document.querySelector("[data-cell='add-trigger']") as HTMLSelectElement;
      expect(el.options.length).toBe(13);
      return el;
    });
    fireEvent.change(adder, { target: { value: "asset_age_rule" } });
    fireEvent.click(document.querySelector("[data-add-trigger]") as HTMLElement);
    fireEvent.change(adder, { target: { value: "dunning_auto" } });
    fireEvent.click(document.querySelector("[data-add-trigger]") as HTMLElement);
    expect(document.querySelectorAll("[data-array='rule-triggers'] tbody tr").length).toBeGreaterThanOrEqual(2);
    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));

    // Step 2 — a customer message; the message list is Notifications' own.
    const addMessage = (await waitFor(() => {
      const el = document.querySelector("[data-cell='add-message']");
      expect(el).not.toBeNull();
      return el;
    })) as HTMLSelectElement;
    fireEvent.change(addMessage, { target: { value: "raised" } });
    fireEvent.click(document.querySelector("[data-add-message]") as HTMLElement);
    fireEvent.change(document.querySelector("[data-cell='notify-1-who']") as HTMLElement, { target: { value: "customer" } });
    const message = document.querySelector("[data-cell='notify-1-message']") as HTMLSelectElement;
    expect(Array.from(message.options).map((o) => o.value)).toContain("appointment_window");
    fireEvent.change(message, { target: { value: "appointment_window" } });

    // An escalation; its message is SHOWN (the kind's own), never a picker.
    const addStall = document.querySelector("[data-cell='add-escalation']") as HTMLSelectElement;
    fireEvent.change(addStall, { target: { value: "overdue" } });
    fireEvent.click(document.querySelector("[data-add-escalation]") as HTMLElement);
    fireEvent.change(document.querySelector("[data-cell='stall-1-hours']") as HTMLElement, { target: { value: "24" } });
    fireEvent.change(document.querySelector("[data-cell='stall-1-also']") as HTMLElement, {
      target: { value: "role:system_admin" },
    });
    const stallRow = document.querySelector("[data-array='rule-stalls'] tbody tr") as HTMLElement;
    expect(within(stallRow).getByText(t("notifications.rules.event.sla_breach"))).toBeTruthy();
    expect(stallRow.querySelector("[data-cell='stall-1-message']")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));

    // Step 3 — the Review states tonight's count, from the preview.
    expect(await screen.findByText(t("work.rules.builder.tonightRaises", { count: 47 }))).toBeTruthy();
    // DEF-WRK-9661 — the one the raise would refuse is said, not counted as a job.
    expect(document.querySelector("[data-rule-cannot-raise]")?.textContent).toContain(
      t("work.rules.builder.cannotRaise", { count: 1 }),
    );
    expect(screen.getByText(t("work.rules.builder.nothingWritten"))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t("work.rules.builder.activate") }));

    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/work/rules")).toBe(true));
    const posted = calls.find((c) => c.method === "POST" && c.path === "/work/rules")!.body as {
      name: string;
      triggers: { kind: string }[];
      notifications: { event_key: string; when: string; who: string }[];
      escalations: { kind: string; after_hours: number; also_tell: { kind: string; id: string }[] }[];
    };
    expect(posted.name).toBe("Backflow test due");
    expect(posted.triggers.map((row) => row.kind)).toEqual(["asset_age_rule", "dunning_auto"]);
    expect(posted.notifications).toEqual([{ event_key: "appointment_window", when: "raised", who: "customer" }]);
    expect(posted.escalations).toEqual([
      { kind: "overdue", after_hours: 24, also_tell: [{ kind: "role", id: "system_admin" }] },
    ]);
    // `BR-NOT-017` — a message is a key; no text box sent words.
    expect(JSON.stringify(posted)).not.toContain("reminders");
  });
});

describe("P3.62 — one rule's page: Overview · Jobs · Audit", () => {
  it("the Overview says what it raises and what tonight holds, with the three panels", async () => {
    const { RuleDetailPage } = await import("../RuleDetailPage");
    mountAt(`/${TENANT}/work/rules/${RULE_ID}`, [
      { pattern: "/:tenant/work/rules/:ruleId", element: <RuleDetailPage client={recordingClient([])} /> },
    ]);
    // Values read off the RECORDING, never typed here — a re-record moves them.
    const recorded = RULE as { name: string; template: { name: string }; priority: { name: string } | null };
    expect(await screen.findByRole("heading", { level: 1, name: recorded.name })).toBeTruthy();
    const raises = document.querySelector("[data-rule-raises]") as HTMLElement;
    expect(raises.textContent).toBe(
      recorded.priority === null
        ? t("work.rules.page.raises", { template: recorded.template.name })
        : t("work.rules.page.raisesAt", { template: recorded.template.name, priority: recorded.priority.name }),
    );
    expect(document.querySelector("[data-array='rule-summary-triggers']")).not.toBeNull();
    expect(document.querySelector("[data-array='rule-summary-notify']")).not.toBeNull();
    expect(document.querySelector("[data-array='rule-summary-stalls']")).not.toBeNull();
    // README ruling 16 — Edit, Duplicate and the switch, top right.
    expect(screen.getByRole("link", { name: t("work.rules.page.edit") }).getAttribute("href")).toBe(
      `/${TENANT}/work/rules/${RULE_ID}/edit`,
    );
    expect(screen.getByRole("button", { name: t("work.rules.turnOff") })).toBeTruthy();
    expect(document.body.textContent).not.toContain(RULE_ID);
  });

  it("the Jobs tab lists every job the rule raised", async () => {
    const { RuleDetailPage } = await import("../RuleDetailPage");
    mountAt(`/${TENANT}/work/rules/${RULE_ID}?tab=jobs`, [
      { pattern: "/:tenant/work/rules/:ruleId", element: <RuleDetailPage client={recordingClient([])} /> },
    ]);
    const orders = (RULE_JOBS as { results: { order_no: string }[] }).results.map((row) => row.order_no);
    expect(orders.length).toBeGreaterThan(0);
    expect(await screen.findByText(orders[0])).toBeTruthy();
    for (const no of orders) expect(screen.getByText(no)).toBeTruthy();
  });

  it("the Audit tab says who wrote the rule, in words", async () => {
    const { RuleDetailPage } = await import("../RuleDetailPage");
    mountAt(`/${TENANT}/work/rules/${RULE_ID}?tab=audit`, [
      { pattern: "/:tenant/work/rules/:ruleId", element: <RuleDetailPage client={recordingClient([])} /> },
    ]);
    expect(await screen.findByText(t("work.rules.audit.act.created"))).toBeTruthy();
    expect(screen.getByText("Dana Whitfield")).toBeTruthy();
  });
});
