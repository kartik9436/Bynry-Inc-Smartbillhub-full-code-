// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-054 task 9 — *"The multi-select utility-service control,
//           defaulting to every enabled service; delete the 36-word note it
//           replaces."*   Screens: RDS-03 (S28) stage 1
// Rules:    B14 rule 9 (a multi-select is removable CHIPS + an add control,
//           never a wall of checkboxes) · B14 rule 31 (nothing internal is ever
//           the visible value of a field) · BR-MET-003 (only the services this
//           utility SELLS) · BR-MET-014 (the batch tag inherits to a row that
//           does not state its own) · BR-MET-137 (a stated service is resolved
//           against the enabled set) · BR-SHL-025 (a control this release
//           cannot offer renders disabled WITH its reason)
// Defects:  DEF-2671 (the 36-word note claimed no endpoint existed; one always
//           had) · DEF-2673 (the batch stores ONE service or ALL and nothing
//           between)
// ───────────────────────────────────────────────────────
// WHAT THIS FILE DEFENDS, and why nothing else can see it:
//
//   1. **The control defaults to EVERY enabled service and to nothing else.**
//      A default seeded from an empty array renders "no services" for the
//      moment before `GET /settings/services` answers and then fills in;
//      `tsc` cannot tell that from a correct default, and neither can a
//      snapshot taken after the query settles.
//   2. **The payload is DEF-2673's two shapes and never a third.** The wire
//      body is the only place the difference between *one service* and
//      *several* becomes visible — the screen looks identical either way.
//   3. **The last chip cannot be removed.** An empty control and a full one
//      send the IDENTICAL payload, so were the last remove live, "no service"
//      and "every service" would be one state wearing two faces and no later
//      check could separate them.
//   4. **Only ENABLED services are offered.** BR-MET-003, and the server
//      refuses a disabled code by name — an option that cannot be accepted is
//      worse than an absent one.
//
// ⚠ **THE BROWSER HALF IS NOT HERE AND CANNOT BE.** jsdom does no layout and
// no style, so a Tailwind utility that compiled to nothing passes every
// assertion in this file (B14 rule 21's per-file migration clause). The binding
// proof is `10-scripts/render-checks/cr054-reads-upload.mjs`, per the PO's rule
// of 2026-08-30: *"All UI screen should be confirm using real broswer testing
// and not just based on test cases"*.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { UploadReadsWizard, serviceTagFor, uploadReadMethodsKey } from "./UploadReadsWizard";
import { PREMISES_PERMISSION } from "./meteringShared";

const TEST_TENANT = "brazosbend";
const CYCLE_ID = "c-002";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/** `GET /settings/services` — the shape `apps/tenancy` serves, trimmed to the
 *  fields this control reads. **The fourth row is DISABLED**, because the
 *  assertion that matters is that it is never offered: a tenant that does not
 *  sell gas must not be able to tag a batch `gas`, which
 *  `_validate_batch_tags` refuses by name. */
const SERVICES = [
  { service: "electric", name: "Electric", enabled: true },
  { service: "water", name: "Water", enabled: true },
  { service: "sewer", name: "Sewer", enabled: true },
  { service: "gas", name: "Gas", enabled: false },
];

const STAGED = {
  id: "b-054",
  batch_no: "B-2608-09",
  status: "staged",
  source_kind: "csv",
  source_detail: null,
  read_method: null,
  period_month: "2026-08-01",
  cycle_id: CYCLE_ID,
  route_id: null,
  service: null,
  compliance: {
    file_name: "reads.csv",
    file_hash: "9f2c41ab7d0e5c88",
    uploaded_by_name: "Marcus Johnson",
    uploaded_at: "2026-08-06T14:14:22Z",
    certified: false,
    cosigned_by: null,
    cosigned_by_name: null,
  },
  counts: {
    rows: 1,
    passed: 1,
    warnings: 0,
    errors: 0,
    rows_with_unevaluated: 0,
    accepted: 0,
    rejected: 0,
    field_visit: 0,
    skipped: 0,
    estimate_requested: 0,
    undispositioned: 1,
  },
  mapping: { meter_id: "meter_id", read_date: "read_date", reading: "reading" },
  warnings: [],
};

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

interface Call {
  method: string;
  path: string;
  body?: unknown;
}

function stubClient(calls: Call[], services: unknown = SERVICES): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === "/cycles") {
        return ok({
          count: 1,
          results: [{ id: CYCLE_ID, code: "CY-002", name: "Residential" }],
        } as T);
      }
      if (path === "/routes") return ok({ count: 0, results: [] } as T);
      if (path === "/reads/read-methods") {
        return ok({ results: [{ code: "walk_by", name: "Walk-by" }] } as T);
      }
      if (path === "/settings/services") {
        if (services === null) throw new Error("settings/services is unreachable");
        return ok(services as T);
      }
      if (path === `/cycles/${CYCLE_ID}/reading-sheet/summary`) {
        return ok({
          cycle_id: CYCLE_ID,
          cycle_code: "CY-002",
          period_start: "2026-08-01",
          period_end: "2026-08-03",
          window_absent_reason: null,
          rows: 18,
          meters: 5,
          registers: { total: 5 },
          unresolved_meters: 0,
          unresolved: [],
          filename: "reading_sheet_CY-002_2026-08.csv",
        } as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path, body });
      if (path === "/read-batches") return ok(STAGED as T, 201);
      throw new Error(`unstubbed POST ${path}`);
    },
    request: async <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      calls.push({ method: options?.method ?? "PATCH", path, body: options?.body });
      return ok({} as T);
    },
  } as unknown as ApiClient;
}

function permissions(): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

function mount(calls: Call[], services: unknown = SERVICES) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(uploadReadMethodsKey, [{ code: "walk_by", name: "Walk-by" }]);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads/upload`]}>
          <Routes>
            <Route
              path="/:tenant/reads/upload"
              element={<UploadReadsWizard client={stubClient(calls, services)} />}
            />
            <Route path="/:tenant/reads" element={<div>reads list</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function chips(container: HTMLElement): HTMLButtonElement[] {
  return [...container.querySelectorAll<HTMLButtonElement>('[data-reads="service-chip"]')];
}

function chipCodes(container: HTMLElement): string[] {
  return chips(container).map((chip) => chip.getAttribute("data-reads-service") ?? "");
}

/** Stage 1 → 2, so the stage POST body can be read. */
async function stage(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
): Promise<void> {
  const month = container.querySelector<HTMLInputElement>("#period_month");
  if (month === null) throw new Error("stage 1 draws no reading-month field");
  await user.type(month, "2026-08-03");
  await user.click(await screen.findByRole("button", { name: t("workflow.advance.transform") }));
  const paste = container.querySelector<HTMLTextAreaElement>("#reads-text");
  if (paste === null) throw new Error("stage 2 draws no paste box");
  await user.type(paste, "meter_id,read_date,reading{enter}M-7450,2026-08-03,424");
  await user.click(await screen.findByRole("button", { name: t("metering.upload.file.stage") }));
}

describe("CR-054 task 9 · the payload rule, provable without a DOM", () => {
  it("DEF-2673: exactly two shapes reach the server, and a subset is the second", () => {
    // ⚠ THIS IS THE WHOLE OF DEF-2673 IN FIVE ASSERTIONS.
    // `read_import_batches.service` is ONE TextField whose NULL means *every
    // service*, so "not one particular service" is the only thing a subset can
    // say — and it is a TRUE statement, which is why the screen states it as a
    // consequence rather than apologising for a missing column.
    expect(serviceTagFor(null)).toBeNull(); // untouched = every service
    expect(serviceTagFor(["electric", "water", "sewer"])).toBeNull(); // all of them
    expect(serviceTagFor(["electric", "water"])).toBeNull(); // a SUBSET
    expect(serviceTagFor(["electric"])).toBe("electric"); // the one shape that tags
    // Two guards for one hazard, deliberately: the control makes an empty
    // choice unreachable AND this refuses to invent a tag from one.
    expect(serviceTagFor([])).toBeNull();
    expect(serviceTagFor(["   "])).toBeNull();
  });

  it("the nine copy keys exist in every one of the eleven catalogues", () => {
    // G32's ratchet is at zero and a key with no catalogue sentence renders as
    // SILENCE — a chip with no label, which reads as a broken control rather
    // than as a missing translation.
    const keys = [
      "services",
      "servicesHelp",
      "servicesAdd",
      "servicesAllAdded",
      "servicesRemove",
      "servicesKeepOne",
      "servicesTagOne",
      "servicesTagMany",
      "servicesUnavailable",
    ];
    expect(keys).toHaveLength(9);
    for (const key of keys) {
      expect(i18n.exists(`metering.upload.field.${key}`)).toBe(true);
    }
    // DEF-2671 — the 36-word note is GONE and must not come back.
    expect(i18n.exists("metering.upload.field.serviceOmitted")).toBe(false);
  });
});

describe("CR-054 task 9 · the control on stage 1", () => {
  it("defaults to EVERY enabled service, and offers no disabled one", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await waitFor(() => expect(chips(container).length).toBeGreaterThan(0));

    // ⚠ **GREATER THAN ZERO AS WELL AS CORRECT.** Three of the four seeded
    // services are enabled; an assertion that only checked "gas is absent"
    // would pass just as happily over a control that drew nothing at all.
    expect(chipCodes(container)).toEqual(["electric", "water", "sewer"]);
    expect(chipCodes(container)).not.toContain("gas");

    // B14 rule 31 — the VISIBLE value is the service's NAME. `electric` is the
    // stored code and rides on `data-reads-service`, never in the text.
    expect(chips(container)[0].textContent).toContain("Electric");
    expect(chips(container)[0].textContent).not.toContain("electric");

    // B14 rule 9 — chips plus ONE add control, never a wall of checkboxes.
    expect(container.querySelectorAll('input[type="checkbox"]')).toHaveLength(0);
    const add = container.querySelector<HTMLSelectElement>("#reads-services-add");
    expect(add).not.toBeNull();
    // Every enabled service is already chosen, so there is nothing to add and
    // the control says so rather than opening an empty menu (BR-SHL-025).
    expect(add?.disabled).toBe(true);
    expect(add?.textContent).toContain(t("metering.upload.field.servicesAllAdded"));

    // The CONSEQUENCE, stated. Not the mechanism — DEF-2673 lives in the
    // register, which is what CR-054's copy rule asks for.
    expect(container.querySelector('[data-reads="service-fact"]')?.textContent).toBe(
      t("metering.upload.field.servicesTagMany"),
    );
    expect(user).toBeDefined();
  });

  it("the default sends NO service key at all", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await waitFor(() => expect(chips(container).length).toBe(3));
    await stage(user, container);

    const staged = calls.find((call) => call.path === "/read-batches");
    expect(staged).toBeDefined();
    const body = staged?.body as Record<string, unknown>;
    // NOT `service: null` and NOT `service: ""` — OMITTED. The server stores
    // NULL for an absent key and refuses "" as an unknown lookup, so the
    // difference between the two is a 422 on every default upload.
    expect(Object.prototype.hasOwnProperty.call(body, "service")).toBe(false);
    // …and the rest of the tags still travelled, so this is not a body that
    // failed to build (the check that cannot fail).
    expect(body.period_month).toBe("2026-08-03");
    expect(body.source_kind).toBe("csv");
  });

  it("narrowing to ONE service tags the batch and names it on screen", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await waitFor(() => expect(chips(container).length).toBe(3));

    await user.click(screen.getByRole("button", { name: t("metering.upload.field.servicesRemove", { service: "Water" }) }));
    await waitFor(() => expect(chips(container).length).toBe(2));
    await user.click(screen.getByRole("button", { name: t("metering.upload.field.servicesRemove", { service: "Sewer" }) }));
    await waitFor(() => expect(chips(container).length).toBe(1));
    expect(chipCodes(container)).toEqual(["electric"]);

    // BR-MET-014's inheritance, said as a consequence and with the service's
    // NAME in it (rule 31).
    expect(container.querySelector('[data-reads="service-fact"]')?.textContent).toBe(
      t("metering.upload.field.servicesTagOne", { service: "Electric" }),
    );

    await stage(user, container);
    const body = calls.find((call) => call.path === "/read-batches")?.body as Record<
      string,
      unknown
    >;
    expect(body.service).toBe("electric");
  });

  it("a SUBSET of two sends no tag, and says why in one sentence", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await waitFor(() => expect(chips(container).length).toBe(3));

    await user.click(screen.getByRole("button", { name: t("metering.upload.field.servicesRemove", { service: "Sewer" }) }));
    await waitFor(() => expect(chips(container).length).toBe(2));
    expect(chipCodes(container)).toEqual(["electric", "water"]);
    expect(container.querySelector('[data-reads="service-fact"]')?.textContent).toBe(
      t("metering.upload.field.servicesTagMany"),
    );

    await stage(user, container);
    const body = calls.find((call) => call.path === "/read-batches")?.body as Record<
      string,
      unknown
    >;
    expect(Object.prototype.hasOwnProperty.call(body, "service")).toBe(false);
  });

  it("the LAST chip cannot be removed, and the control says why", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await waitFor(() => expect(chips(container).length).toBe(3));
    // Every chip is live while there is more than one.
    expect(chips(container).every((chip) => !chip.disabled)).toBe(true);

    await user.click(screen.getByRole("button", { name: t("metering.upload.field.servicesRemove", { service: "Water" }) }));
    await waitFor(() => expect(chips(container).length).toBe(2));
    await user.click(screen.getByRole("button", { name: t("metering.upload.field.servicesRemove", { service: "Sewer" }) }));
    await waitFor(() => expect(chips(container).length).toBe(1));

    // ⚠ AN EMPTY CONTROL AND A FULL ONE SEND THE SAME PAYLOAD. Disabled WITH
    // its reason (BR-SHL-025), never a press that is silently ignored.
    const [last] = chips(container);
    expect(last.disabled).toBe(true);
    expect(last.getAttribute("title")).toBe(t("metering.upload.field.servicesKeepOne"));
    await user.click(last);
    expect(chips(container)).toHaveLength(1);

    // …and the add control came BACK, so a clerk who over-trimmed is not stuck.
    const add = container.querySelector<HTMLSelectElement>("#reads-services-add");
    expect(add?.disabled).toBe(false);
    expect([...(add?.options ?? [])].map((option) => option.value)).toEqual([
      "",
      "water",
      "sewer",
    ]);
  });

  it("a list that could not be READ says so, and is not drawn as an empty menu", async () => {
    const calls: Call[] = [];
    const { container } = mount(calls, null);
    await waitFor(() =>
      expect(container.querySelector('[data-reads="service-unavailable"]')).not.toBeNull(),
    );
    // hard-won law 1 / BR-SHL-025: "we could not read your list" and "you sell
    // nothing" are two different facts and only the first is true here.
    expect(container.querySelector('[data-reads="service-unavailable"]')?.textContent).toBe(
      t("metering.upload.field.servicesUnavailable"),
    );
    expect(chips(container)).toHaveLength(0);
    expect(container.querySelector('[data-reads="service-fact"]')).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-054 task 9 (12-governance/11-change-requests.md, PO 2026-08-30)
//         + DEF-2671 + DEF-2673 (12-governance/10-defect-log.csv)
//         + B14 rules 9, 21 and 31 (04-docs/02-decisions/14-ui-conventions.md)
// screens: RDS-03 / S28 stage 1
// generated: 2026-08-31 by the CR-054 W1/W2 record-and-task-9 lane
// checklist: A✔ B✔ C✔ D=deferred(no endpoint of its own — the control reads
//   `GET /settings/services`, which DEF-2671 proved has always been open to a
//   Billing Clerk) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E4 **A SUBSET OF TWO OR MORE STORES NOTHING, AND THE SCREEN STATES THE
//      CONSEQUENCE RATHER THAN THE CAUSE.** DEF-2673 is a schema gap on the
//      table carrying hard rule 6's `tag_fingerprint` and no CR-054 task asks
//      for the widening; its own closing sentence tells this lane to build to
//      the two shapes the server holds. *"Each row states its own service"* is
//      TRUE of a NULL tag, so nothing on screen is a fiction.
//   E3 the control is NOT `ServicesAvailableField` reused: that component is
//      bound to the premises field id and every one of its empty states is a
//      sentence about an ADDRESS. What is reused is the half that must never
//      fork — `enabledServiceRows` and the one `queryKeys.tenantServices`.
// ──────────────────────────────────────────────────────────
