// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-180-BRC10 — Fix a bill, revamped: F1–F10, test task T3
// Drawing:  05-prototype/fix-a-bill-2026-10-12/01–24 (read as images)
// Rulings:  decision log 2026-10-12 *FIX A BILL REVAMP* items 1–12
// Rules:    BR-BIL-014 (nothing is written before Send) · BR-BIL-042 (the
//           strongest class wins) · BR-BIL-044 (finance open for the approver)
//           · B14 rule 31 (no database id on screen) · hard rule 2
// ───────────────────────────────────────────────────────
// ⚠ WHAT THESE CASES CAN AND CANNOT SEE (hard-won law 7): jsdom does no layout,
// so nothing here proves the screen LOOKS like the images. They prove the
// pieces each image draws are present, in order, wired to the contract's
// routes, and that no uuid reaches the screen.
//
// RED FIRST: run against the pre-CR-180 `FixABillTab.tsx` (six scope kinds,
// eighteen ticked reasons, a case opened at step 1's Continue), every case
// below fails — there are no option cards, no `What was wrong` table and no
// `/corrections/preview` call.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { CorrectionCaseV2, CorrectionPreview } from "@/api/billingOpsEndpoints";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { FixABillTab } from "../FixABillTab";
import { ForFinance } from "./CheckStep";
import {
  ACCOUNT_BILLS,
  ACCOUNT_FACTS,
  ACCOUNT_ROW,
  BILL_AUG,
  BILL_OCT,
  BILL_SEP,
  CASE_DONE,
  CASE_DONE_BULK,
  CASE_ID,
  CASE_PENDING_APPROVER,
  CASE_PENDING_CLERK,
  CATALOG,
  OPTIONS,
  PLAN_V5,
  PREVIEW_BULK,
  PREVIEW_CREDIT,
  PREVIEW_ONE,
  PREVIEW_REPRINT,
  PREVIEW_SEVERAL,
  RUNS,
  RUN_BILLS,
  pickedTotals,
} from "./__fixtures__/fixABillFixtures";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const TENANT = "brazosbend";

interface Call {
  method: string;
  path: string;
  body: unknown;
}
interface Script {
  preview?: (body: Record<string, unknown>) => CorrectionPreview;
  sent?: CorrectionCaseV2;
  openCase?: CorrectionCaseV2;
  issued?: CorrectionCaseV2;
  cases?: unknown[];
  /** DEF-BIL-10091 — answer these acts with 202 + this job id. */
  accept?: { preview?: string; send?: string; approve?: string };
  /** …and the job's state, as `GET /corrections/jobs/{id}` serves it. */
  jobs?: Record<string, (params: URLSearchParams) => unknown>;
  /** …and `/jobs/{id}`'s poll answers, in order (the last one repeats). */
  polls?: Record<string, unknown[]>;
}

function ok(data: unknown) {
  return { status: 200, data, etag: null, notModified: false } as never;
}

function accepted(jobId: string, act: string) {
  return {
    status: 202,
    data: { job_id: jobId, status_url: `/api/jobs/${jobId}`, act },
    etag: null,
    notModified: false,
  } as never;
}

function fakeClient(script: Script = {}) {
  const calls: Call[] = [];
  function answer(method: string, path: string, body: unknown) {
    calls.push({ method, path, body });
    const [pathname, search = ""] = path.split("?");
    const params = new URLSearchParams(search);
    if (pathname === "/me/permissions") {
      return ok({ permissions: [{ code: "reads_billing_runs", access: "Full" }] });
    }
    if (pathname === "/corrections/reasons") return ok(CATALOG);
    if (pathname.startsWith("/jobs/")) {
      const id = pathname.slice("/jobs/".length);
      const queue = script.polls?.[id] ?? [{ status: "succeeded" }];
      const next = queue.length > 1 ? queue.shift() : queue[0];
      return ok({ id, kind: "billing.correction", progress: null, result_link: null, error: null, ...(next as object) });
    }
    if (pathname.startsWith("/corrections/jobs/")) {
      const id = pathname.slice("/corrections/jobs/".length);
      return ok(script.jobs?.[id]?.(params) ?? null);
    }
    if (pathname === "/corrections/preview" && script.accept?.preview)
      return accepted(script.accept.preview, "preview");
    if (pathname === "/corrections" && method === "POST" && script.accept?.send)
      return accepted(script.accept.send, "send");
    if (pathname === `/corrections/${CASE_ID}/approve-and-issue` && script.accept?.approve)
      return accepted(script.accept.approve, "approve_issue");
    if (pathname === "/corrections" && method === "GET")
      return ok({ results: script.cases ?? [], unavailable: [] });
    if (pathname === "/corrections" && method === "POST")
      return ok(script.sent ?? CASE_PENDING_CLERK);
    if (pathname === "/corrections/preview") {
      return ok(script.preview?.(body as Record<string, unknown>) ?? PREVIEW_ONE);
    }
    if (pathname === "/corrections/options") return ok(OPTIONS);
    if (pathname === "/corrections/resolve") {
      const kind = params.get("scope_kind");
      const ids = params.getAll("invoice_ids");
      if (kind === "account") return ok(ids.length > 0 ? pickedTotals(ids) : ACCOUNT_BILLS);
      return ok(RUN_BILLS);
    }
    if (pathname === `/corrections/${CASE_ID}`) return ok(script.openCase ?? CASE_PENDING_CLERK);
    if (pathname === `/corrections/${CASE_ID}/approve-and-issue`)
      return ok(script.issued ?? CASE_DONE);
    if (pathname === `/corrections/${CASE_ID}/abandon`)
      return ok({ ...CASE_PENDING_CLERK, status: "abandoned" });
    if (pathname === "/accounts") return ok({ count: 1, results: [ACCOUNT_ROW], rollup: {} });
    if (pathname.startsWith("/billing/one-time/accounts/")) return ok(ACCOUNT_FACTS);
    if (pathname === "/billing/runs") {
      // DEF-BIL-10090 — the server filters by bill type; an empty run is still
      // in its answer and must not be offered.
      const empty = { ...RUNS[0], id: "run-empty", cycle_name: null, bills_issued: 0 };
      const rows = params.get("f.bill_type") === "cycle" ? [...RUNS, empty] : RUNS;
      return ok({ count: rows.length, results: rows, tiles: {} });
    }
    if (pathname === "/settings/services")
      return ok([{ service: "water", name: "Water", enabled: true }]);
    return ok({ count: 0, results: [] });
  }
  const client = {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(options?.query ?? {})) {
        if (value !== undefined && value !== null) query.set(key, String(value));
      }
      const search = query.toString();
      const full = search === "" ? path : `${path}${path.includes("?") ? "&" : "?"}${search}`;
      return answer("GET", full, undefined);
    },
    post: async (path: string, body?: unknown) => answer("POST", path, body),
    request: async (path: string, options?: { method?: string; body?: unknown }) =>
      answer(options?.method ?? "GET", path, options?.body),
  } as unknown as ApiClient;
  return { client, calls };
}

function mount(client: ApiClient, search = "") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <MemoryRouter initialEntries={[`/${TENANT}/billing/fix${search}`]}>
            <Routes>
              <Route path="/:tenant/billing/fix" element={<FixABillTab client={client} />} />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const posts = (calls: Call[], path: string) =>
  calls.filter((c) => c.method === "POST" && c.path === path);

function noUuidOnScreen() {
  expect(document.body.textContent ?? "").not.toMatch(UUID);
  for (const input of Array.from(
    document.querySelectorAll("input:not([type=radio]):not([type=checkbox])"),
  )) {
    expect((input as HTMLInputElement).value).not.toMatch(UUID);
  }
}

async function chooseBen() {
  const box = await screen.findByRole("combobox", { name: /Find account/ });
  fireEvent.change(box, { target: { value: "benn" } });
  const list = document.getElementById("fix-account-listbox") as HTMLElement;
  const [option] = await within(list).findAllByRole("option");
  fireEvent.click(option);
  await screen.findByText("Residential Standard");
}

/** Waits for a hook to be on screen — and FAILS while it is not (a waitFor
 *  whose callback returns null would pass at once). */
async function hook(selector: string, timeout?: number): Promise<HTMLElement> {
  return waitFor(
    () => {
      const found = document.querySelector(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    timeout === undefined ? undefined : { timeout },
  );
}

function continueButton() {
  return screen.getByRole("button", { name: t("wizard.continue") });
}

async function pickOneBill(id = BILL_OCT) {
  await chooseBen();
  const table = await hook("[data-fix-bills]");
  await within(table).findByText("BL-2610-000053");
  fireEvent.click(table.querySelector(`input[value="${id}"]`) as HTMLElement);
}

async function toFix(client: ApiClient) {
  mount(client);
  await pickOneBill();
  fireEvent.click(continueButton());
  return waitFor(() => {
    const table = document.querySelector("[data-fix-rows]");
    expect(table).not.toBeNull();
    return table as HTMLElement;
  });
}

const reasonLabel = (n: number) => new RegExp(`^${t("billing.fixBill.col.reason")} ${n}$`);

function addRow(reason: string) {
  fireEvent.click(screen.getByRole("button", { name: t("billing.fixBill.fix.add") }));
  const selects = screen.getAllByLabelText(new RegExp(`^${t("billing.fixBill.col.reason")} \\d+$`));
  fireEvent.change(selects[selects.length - 1], { target: { value: reason } });
  return document.querySelectorAll("[data-fix-row]")[selects.length - 1] as HTMLElement;
}

function typeShouldBe(row: HTMLElement, value: string) {
  fireEvent.change(within(row).getByLabelText(new RegExp(t("billing.fixBill.col.shouldBe"))), {
    target: { value },
  });
}

afterEach(cleanup);

describe("Bills · images 01–05", () => {
  it("draws the four one-word steps, the two option cards inside step 1, and no summary aside", async () => {
    mount(fakeClient().client);
    await screen.findByRole("button", { name: new RegExp(t("billing.fixBill.option.one")) });
    const rail = Array.from(document.querySelectorAll("[data-wizard-step]")).map(
      (cell) => cell.querySelector("[data-step-label]")?.textContent,
    );
    expect(rail).toEqual(["Bills", "Fix", "Check", "Send"]);
    const cards = Array.from(document.querySelectorAll("[data-fix-option]"));
    expect(cards.map((c) => c.getAttribute("data-fix-option"))).toEqual(["one", "bulk"]);
    expect(cards[0].getAttribute("aria-pressed")).toBe("true");
    // The cards sit INSIDE the wizard content (item 2), not above the rail.
    expect(document.querySelector("[data-wizard=content] [data-fix-option]")).not.toBeNull();
    // Item 9 — no summary panel beside the steps.
    expect(document.querySelector("[data-fix-summary]")).toBeNull();
    expect(document.querySelector("aside")).toBeNull();
  });

  it("the sub-option dropdown depends on the option", async () => {
    mount(fakeClient().client);
    const sub = (await screen.findByLabelText(
      new RegExp(t("billing.fixBill.sub.labelOne")),
    )) as HTMLSelectElement;
    expect(Array.from(sub.options).map((o) => o.value)).toEqual(["one_bill", "several"]);
    fireEvent.click(document.querySelector("[data-fix-option=bulk]") as HTMLElement);
    const bulk = screen.getByLabelText(
      new RegExp(t("billing.fixBill.sub.labelBulk")),
    ) as HTMLSelectElement;
    expect(Array.from(bulk.options).map((o) => o.value)).toEqual(["run", "price_mistake"]);
  });

  it("one bill: the account card, a RADIO per bill, the picked total from the server, the draft named", async () => {
    const { client, calls } = fakeClient();
    mount(client);
    await pickOneBill();
    const table = document.querySelector("[data-fix-bills]") as HTMLElement;
    expect(table.querySelectorAll("input[type=radio]")).toHaveLength(4);
    await waitFor(() =>
      expect(document.querySelector("[data-fix-picked-total]")?.textContent).toContain("$232.70"),
    );
    // The total was ASKED of the server for the picked bill, never summed here.
    expect(calls.some((c) => c.path.includes(`invoice_ids=${BILL_OCT}`))).toBe(true);
    expect(document.querySelector("[data-fix-excluded]")?.textContent).toContain("Nov 2026");
    noUuidOnScreen();
  });

  it("several months: TICK boxes, and the total of three", async () => {
    mount(fakeClient().client);
    await chooseBen();
    fireEvent.change(screen.getByLabelText(new RegExp(t("billing.fixBill.sub.labelOne"))), {
      target: { value: "several" },
    });
    const table = await hook("[data-fix-bills]");
    expect(table.querySelectorAll("input[type=checkbox]")).toHaveLength(4);
    for (const id of [BILL_AUG, BILL_SEP, BILL_OCT]) {
      fireEvent.click(
        await waitFor(() => table.querySelector(`input[value="${id}"]`) as HTMLElement),
      );
    }
    await waitFor(() =>
      expect(document.querySelector("[data-fix-picked-total]")?.textContent).toContain("$734.09"),
    );
  });

  it("DEF-BIL-10090 — the run picker asks for cycle runs and offers none with no issued bill", async () => {
    const { client, calls } = fakeClient();
    mount(client);
    fireEvent.click(
      await screen.findByRole("button", { name: new RegExp(t("billing.fixBill.option.bulk")) }),
    );
    const run = (await screen.findByLabelText(
      new RegExp(`^${t("billing.fixBill.run.run")}`),
    )) as HTMLSelectElement;
    await waitFor(() => expect(run.options.length).toBeGreaterThan(1));
    expect(calls.some((c) => c.path.startsWith("/billing/runs") && c.path.includes("f.bill_type=cycle"))).toBe(true);
    const offered = Array.from(run.options).filter((o) => o.value !== "");
    expect(offered).toHaveLength(1);
  });

  it("bulk · a billing run: the run picker, Only part of it, the bills it covers and what was left out", async () => {
    mount(fakeClient().client);
    fireEvent.click(
      await screen.findByRole("button", { name: new RegExp(t("billing.fixBill.option.bulk")) }),
    );
    const run = (await screen.findByLabelText(
      new RegExp(`^${t("billing.fixBill.run.run")}`),
    )) as HTMLSelectElement;
    await waitFor(() => expect(run.options.length).toBeGreaterThan(1));
    fireEvent.change(run, { target: { value: run.options[1].value } });
    expect(screen.getByLabelText(t("billing.fixBill.run.part"))).toBeTruthy();
    const covered = await hook("[data-fix-covered]");
    await within(covered).findByText("Ana Alvarez");
    expect(covered.textContent).toContain("$9,312.60");
    expect(document.querySelector("[data-fix-left-out]")?.textContent).toContain("2");
    noUuidOnScreen();
  });

  it("bulk · a price mistake: From, To and what was wrong", async () => {
    mount(fakeClient().client);
    fireEvent.click(
      await screen.findByRole("button", { name: new RegExp(t("billing.fixBill.option.bulk")) }),
    );
    fireEvent.change(screen.getByLabelText(new RegExp(t("billing.fixBill.sub.labelBulk"))), {
      target: { value: "price_mistake" },
    });
    expect(
      await screen.findByLabelText(new RegExp(`^${t("billing.fixBill.price.from")}`)),
    ).toBeTruthy();
    expect(screen.getByLabelText(new RegExp(`^${t("billing.fixBill.price.to")}`))).toBeTruthy();
    const target = screen.getByLabelText(
      new RegExp(`^${t("billing.fixBill.price.wrong")}`),
    ) as HTMLSelectElement;
    await waitFor(() => expect(target.textContent).toContain("Water tier 2"));
  });
});

describe("Fix · images 06–15", () => {
  it("one table: the columns, every reason as a row type grouped re-price · credit only · reprint only", async () => {
    const table = await toFix(fakeClient().client);
    const heads = Array.from(table.querySelectorAll("thead th")).map((th) => th.textContent);
    expect(heads).toEqual([
      "#",
      t("billing.fixBill.col.reason"),
      t("billing.fixBill.col.item"),
      t("billing.fixBill.col.billed"),
      t("billing.fixBill.col.shouldBe"),
      t("billing.fixBill.col.applyTo"),
      t("billing.fixBill.fix.remove"),
    ]);
    const row = addRow("wrong_read");
    const select = within(row).getByLabelText(reasonLabel(1)) as HTMLSelectElement;
    const groups = Array.from(select.querySelectorAll("optgroup")).map((g) =>
      g.getAttribute("label"),
    );
    expect(groups).toEqual([
      t("billing.fixBill.class.restatement"),
      t("billing.fixBill.class.credit_only"),
      t("billing.fixBill.class.document"),
    ]);
    expect(select.querySelectorAll('option:not([value=""])')).toHaveLength(16);
    // The billed value is the served one, never a uuid: "Billed 1,159.9".
    await waitFor(() => expect(row.textContent).toContain("1,159.9"));
    noUuidOnScreen();
  });

  it("What happens is DERIVED across the rows — strongest wins", async () => {
    const table = await toFix(fakeClient().client);
    const band = () => document.querySelector("[data-fix-what-happens]")?.textContent ?? "";
    addRow("customer_name");
    expect(band()).toContain(t("billing.fixBill.class.document"));
    addRow("goodwill");
    expect(band()).toContain(t("billing.fixBill.class.credit_only"));
    addRow("wrong_read");
    expect(band()).toContain(t("billing.fixBill.class.restatement"));
    expect(table.querySelectorAll("[data-fix-row]")).toHaveLength(3);
  });

  it("the bin icon removes its row", async () => {
    const table = await toFix(fakeClient().client);
    addRow("wrong_read");
    addRow("goodwill");
    const bins = screen.getAllByRole("button", { name: t("billing.fixBill.fix.remove") });
    fireEvent.click(bins[0]);
    const left = table.querySelectorAll("[data-fix-row]");
    expect(left).toHaveLength(1);
    expect(
      (within(left[0] as HTMLElement).getByLabelText(reasonLabel(1)) as HTMLSelectElement).value,
    ).toBe("goodwill");
  });

  it("each row type draws its own inputs", async () => {
    await toFix(fakeClient().client);
    const plan = addRow("wrong_plan");
    expect(plan.textContent).toContain(t("billing.fixBill.billed.useVersion"));
    await waitFor(() => expect(within(plan).getAllByRole("combobox").length).toBe(3));
    const charge = addRow("missed_charge");
    expect(charge.textContent).toContain(t("billing.fixBill.billed.add"));
    const deposit = addRow("wrong_deposit");
    expect(deposit.textContent).toContain("$0.00");
    const name = addRow("customer_name");
    expect(name.textContent).toContain("Ben Benett");
    const credit = addRow("goodwill");
    expect(credit.querySelector("[data-fix-row-class]")?.textContent).toBe(
      t("billing.fixBill.class.credit_only"),
    );
    noUuidOnScreen();
  });

  it("DEF-BIL-10078 — opening Fix asks for no preview until a correction is finished, and never with no scope", async () => {
    const { client, calls } = fakeClient();
    await toFix(client);
    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(posts(calls, "/corrections/preview")).toHaveLength(0);
    typeShouldBe(addRow("wrong_read"), "1162.4");
    await hook("[data-fix-preview=settled] [data-fix-compare]");
    const bodies = posts(calls, "/corrections/preview").map(
      (call) => call.body as { scope: unknown; items: unknown[] },
    );
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.scope).not.toBeNull();
      expect(body.items.length).toBeGreaterThan(0);
    }
  });

  it("DEF-BIL-10088 — a reprint row sends the FIELD it changes, never the reason; a reason with two fields offers both", async () => {
    const { client, calls } = fakeClient({ preview: () => PREVIEW_REPRINT });
    await toFix(client);
    const row = addRow("service_or_mailing_address");
    const item = within(row).getByLabelText(
      new RegExp(`^${t("billing.fixBill.col.item")} 1$`),
    ) as HTMLSelectElement;
    expect(Array.from(item.options).map((o) => o.value)).toEqual(
      expect.arrayContaining(["mailing_address", "service_address"]),
    );
    typeShouldBe(row, "PO Box 4410, Silver Creek, TX 78611");
    await waitFor(() => expect(posts(calls, "/corrections/preview").length).toBeGreaterThan(0));
    const body = posts(calls, "/corrections/preview").at(-1)?.body as {
      items: { reason: string; item: string; value: string }[];
    };
    expect(body.items[0]).toMatchObject({
      reason: "service_or_mailing_address",
      item: "mailing_address",
      value: "PO Box 4410, Silver Creek, TX 78611",
    });
  });

  it("Not done here: four bullets, each a situation and a link", async () => {
    await toFix(fakeClient().client);
    const list = document.querySelector("[data-fix-not-here]") as HTMLElement;
    expect(list.querySelectorAll("li")).toHaveLength(4);
    expect(list.querySelectorAll("li a")).toHaveLength(4);
  });

  it("the old and new bill side by side, by service and rate type, rows aligned, '—' where a line is missing", async () => {
    const { client, calls } = fakeClient();
    await toFix(client);
    const row = addRow("wrong_read");
    typeShouldBe(row, "1162.4");
    const compare = await waitFor(() => {
      const found = document.querySelector("[data-fix-compare]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    const was = compare.querySelector("[data-fix-side=was]") as HTMLElement;
    const becomes = compare.querySelector("[data-fix-side=becomes]") as HTMLElement;
    const keys = (side: HTMLElement) =>
      Array.from(side.querySelectorAll("[data-fix-line]")).map((el) =>
        el.getAttribute("data-fix-line"),
      );
    expect(keys(was)).toEqual(keys(becomes));
    expect(was.querySelector("[data-fix-line='water.tier3']")?.textContent).toContain("—");
    expect(becomes.querySelector("[data-fix-line='water.tier3']")?.textContent).toContain(
      "1.6 kgal × $5.75",
    );
    expect(was.textContent).toContain(t("billing.fixBill.rateType.tiered"));
    expect(was.textContent).toContain("1% on $227.01");
    expect(document.querySelector("[data-fix-change]")?.textContent).toContain("$18.74");
    // The preview WROTE nothing: no POST /corrections yet (BR-BIL-014).
    expect(posts(calls, "/corrections/preview").length).toBeGreaterThan(0);
    expect(posts(calls, "/corrections")).toHaveLength(0);
  });

  it("several months: Apply to is month chips; month tabs over the comparison; What changes on the page", async () => {
    const { client } = fakeClient({ preview: () => PREVIEW_SEVERAL });
    mount(client);
    await chooseBen();
    fireEvent.change(screen.getByLabelText(new RegExp(t("billing.fixBill.sub.labelOne"))), {
      target: { value: "several" },
    });
    const table = await hook("[data-fix-bills]");
    for (const id of [BILL_AUG, BILL_SEP, BILL_OCT]) {
      fireEvent.click(
        await waitFor(() => table.querySelector(`input[value="${id}"]`) as HTMLElement),
      );
    }
    fireEvent.click(continueButton());
    await waitFor(() => expect(document.querySelector("[data-fix-rows]")).not.toBeNull());
    const reading = addRow("wrong_read");
    const chips = within(reading.querySelector("[data-fix-apply]") as HTMLElement).getAllByRole(
      "checkbox",
    );
    expect(chips).toHaveLength(3);
    expect(chips.every((c) => (c as HTMLInputElement).checked)).toBe(true);
    const goodwill = addRow("goodwill");
    const gw = within(goodwill.querySelector("[data-fix-apply]") as HTMLElement).getAllByRole(
      "checkbox",
    );
    expect(gw.map((c) => (c as HTMLInputElement).checked)).toEqual([false, false, true]);
    fireEvent.click(gw[0]);
    expect((gw[0] as HTMLInputElement).checked).toBe(true);
    typeShouldBe(reading, "1162.4");
    const tabs = await screen.findAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    expect(document.querySelector("[data-fix-page-changes]")?.textContent).toContain("Ben Bennett");
  });

  it("a preview problem renders the CATALOGUE's sentence, never the server's prose (CS-36's rule, carried over)", async () => {
    const problem = {
      code: "bill_already_paid_in_full",
      br_ref: "BR-BIL-014",
      message_key: "billing.fixBill.refuse.problems",
      detail: "server prose naming BR-TEN-038",
    };
    const { client } = fakeClient({ preview: () => ({ ...PREVIEW_ONE, problems: [problem] }) });
    await toFix(client);
    typeShouldBe(addRow("wrong_read"), "1162.4");
    await waitFor(() => expect(document.body.textContent).toContain(t("billing.fixBill.refuse.problems")));
    expect(document.body.textContent).not.toContain("BR-TEN-038");
  });

  it("credit only: the old bill beside the credit note", async () => {
    const { client } = fakeClient({ preview: () => PREVIEW_CREDIT });
    await toFix(client);
    typeShouldBe(addRow("goodwill"), "25.00");
    const credit = await hook("[data-fix-credit-note]");
    expect(credit.textContent).toContain("−$25.00");
    expect(credit.textContent).toContain("$207.70");
  });

  it("reprint only: amounts stay; What changes on the page lists field · was · becomes", async () => {
    const { client } = fakeClient({ preview: () => PREVIEW_REPRINT });
    await toFix(client);
    typeShouldBe(addRow("service_or_mailing_address"), "418 Pecan St, Brazos Bend, TX 77461");
    const changes = await hook("[data-fix-page-changes]");
    expect(changes.textContent).toContain("418 Pecon St");
    expect(changes.textContent).toContain("418 Pecan St, Brazos Bend, TX 77461");
  });

  it("bulk: Every bill, and going up and going down shown apart", async () => {
    const { client } = fakeClient({ preview: () => PREVIEW_BULK });
    mount(client);
    fireEvent.click(
      await screen.findByRole("button", { name: new RegExp(t("billing.fixBill.option.bulk")) }),
    );
    const run = (await screen.findByLabelText(
      new RegExp(`^${t("billing.fixBill.run.run")}`),
    )) as HTMLSelectElement;
    await waitFor(() => expect(run.options.length).toBeGreaterThan(1));
    fireEvent.change(run, { target: { value: run.options[1].value } });
    fireEvent.click(continueButton());
    await waitFor(() => expect(document.querySelector("[data-fix-rows]")).not.toBeNull());
    const row = addRow("wrong_plan");
    const select = within(row).getByLabelText(reasonLabel(1)) as HTMLSelectElement;
    expect(select.querySelectorAll('option:not([value=""])')).toHaveLength(7);
    expect(row.textContent).toContain(t("billing.fixBill.apply.every"));
    // Item 6 — the plan AND its version: the billed plan is preloaded, the version is chosen.
    const version = await waitFor(() =>
      within(row).getByLabelText(new RegExp(`^${t("billing.fixBill.col.shouldBe")} 1$`)),
    );
    fireEvent.change(version, { target: { value: PLAN_V5 } });
    const up = await hook("[data-fix-tile=up]");
    expect(up.textContent).toContain("44");
    expect(up.textContent).toContain("$412.36");
    expect(document.querySelector("[data-fix-tile=down]")?.textContent).toContain("0");
    expect(document.querySelector("[data-fix-tile=flat]")?.textContent).toContain("4");
    expect(document.querySelector("[data-fix-bulk-bills]")?.textContent).toContain("Ana Alvarez");
    noUuidOnScreen();
  });
});

describe("DEF-BIL-10096 — a bill left out of a bulk case", () => {
  it("is listed by number, and Continue still goes on to Check", async () => {
    const leftOut = {
      ...PREVIEW_BULK,
      problems: [
        { code: "cannot_price", message_key: "billing.fixBill.leftOut.cannotPrice", detail: "BL-2609-000012" },
      ],
    } as CorrectionPreview;
    const { client } = fakeClient({ preview: () => leftOut });
    mount(client);
    fireEvent.click(
      await screen.findByRole("button", { name: new RegExp(t("billing.fixBill.option.bulk")) }),
    );
    const run = (await screen.findByLabelText(
      new RegExp(`^${t("billing.fixBill.run.run")}`),
    )) as HTMLSelectElement;
    await waitFor(() => expect(run.options.length).toBeGreaterThan(1));
    fireEvent.change(run, { target: { value: run.options[1].value } });
    fireEvent.click(continueButton());
    await waitFor(() => expect(document.querySelector("[data-fix-rows]")).not.toBeNull());
    const row = addRow("wrong_plan");
    const version = await waitFor(() =>
      within(row).getByLabelText(new RegExp(`^${t("billing.fixBill.col.shouldBe")} 1$`)),
    );
    fireEvent.change(version, { target: { value: PLAN_V5 } });
    const list = await hook("[data-fix-left-out-bills]");
    expect(list.textContent).toContain("BL-2609-000012");
    await hook("[data-fix-preview=settled]");
    fireEvent.click(continueButton());
    await hook("[data-fix-check]");
  });
});

async function toCheck(client: ApiClient) {
  await toFix(client);
  typeShouldBe(addRow("wrong_read"), "1162.4");
  await hook("[data-fix-preview=settled] [data-fix-compare]");
  fireEvent.click(continueButton());
  return hook("[data-fix-check=customer]");
}

describe("Check · images 16–18", () => {
  it("for the customer, existing bills, and For finance CLOSED for the clerk", async () => {
    const customer = await toCheck(fakeClient().client);
    expect(customer.textContent).toContain("$465.77");
    expect(customer.textContent).toContain("$484.51");
    expect(document.querySelector("[data-fix-check=existing]")?.textContent).toContain(
      "BL-2610-000053",
    );
    const finance = document.querySelector("[data-otb-panel=finance]") as HTMLElement;
    expect(finance.getAttribute("data-open")).toBe("false");
    noUuidOnScreen();
  });

  it("For finance OPEN for the approver: entries, net per account, posting month", async () => {
    const { client } = fakeClient({ openCase: CASE_PENDING_APPROVER });
    mount(client, `?case=${CASE_ID}`);
    await screen.findByRole("button", { name: t("billing.fixBill.send.approve") });
    fireEvent.click(screen.getByRole("button", { name: t("wizard.back") }));
    const finance = await hook("[data-otb-panel=finance]");
    expect(finance.getAttribute("data-open")).toBe("true");
    expect(finance.textContent).toContain("Water revenue");
    expect(finance.textContent).toContain("Oct 2026");
    noUuidOnScreen();
  });
});

describe("Send · images 19–23", () => {
  it("Send for approval waits for the tick, and is where the case is CREATED", async () => {
    const { client, calls } = fakeClient();
    await toCheck(client);
    fireEvent.click(continueButton());
    const send = await screen.findByRole("button", { name: t("billing.fixBill.send.send") });
    expect((send as HTMLButtonElement).disabled).toBe(true);
    expect(posts(calls, "/corrections")).toHaveLength(0);
    fireEvent.click(screen.getByLabelText(t("billing.fixBill.send.checked")));
    fireEvent.click(send);
    await waitFor(() => expect(posts(calls, "/corrections")).toHaveLength(1));
    const body = posts(calls, "/corrections")[0].body as Record<string, unknown>;
    expect(body.preview_hash).toBe("sha256:one");
    expect(body.items).toEqual([
      { reason: "wrong_read", item: OPTIONS.meters?.[0].asset_id, value: "1162.4", bill_ids: null },
    ]);
    const waiting = await hook("[data-fix-send=waiting]");
    expect(waiting.textContent).toContain("R. Chen");
    expect(screen.queryByRole("button", { name: t("billing.fixBill.send.approve") })).toBeNull();
    noUuidOnScreen();
  });

  it("the approver sees Approve and issue; the result shows the numbers", async () => {
    const { client, calls } = fakeClient({ openCase: CASE_PENDING_APPROVER });
    mount(client, `?case=${CASE_ID}`);
    const approve = await screen.findByRole("button", { name: t("billing.fixBill.send.approve") });
    expect(document.querySelector("[data-fix-send=approver]")?.textContent).toContain(
      "Dana Whitfield",
    );
    fireEvent.click(approve);
    await waitFor(() =>
      expect(posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)).toHaveLength(1),
    );
    const done = await hook("[data-fix-send=done]");
    expect(done.textContent).toContain("CN-2610-0041");
    expect(done.textContent).toContain("BL-2610-00118");
    expect(done.textContent).toContain("CC-2026-012");
    noUuidOnScreen();
  });

  // DEF-BIL-10535 (PO 2026-10-22, Q1) — the approver picks Email · Paper ·
  // Both, starting on the ORIGINAL bill's channels; Email is greyed with no
  // email on file. Daniel Thomas: original by post, email on file.
  it("DEF-BIL-10535 — the approver picks Email, Paper or Both, starting on the original's channels", async () => {
    const { client, calls } = fakeClient({
      openCase: {
        ...CASE_PENDING_APPROVER,
        delivery: {
          choices: ["email", "paper", "email_and_paper"],
          preselected: "paper",
          email_on_file: true,
        },
      },
    });
    mount(client, `?case=${CASE_ID}`);
    const approve = await screen.findByRole("button", { name: t("billing.fixBill.send.approve") });
    const group = await screen.findByRole("radiogroup", { name: t("billing.fixBill.send.sendBy") });
    const paper = within(group).getByRole("radio", { name: t("billing.fixBill.send.delivery.paper") });
    expect(paper.getAttribute("aria-checked")).toBe("true");
    const both = within(group).getByRole("radio", {
      name: t("billing.fixBill.send.delivery.email_and_paper"),
    });
    expect((both as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(both);
    expect(both.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(approve);
    await waitFor(() =>
      expect(posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)).toHaveLength(1),
    );
    const body = posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)[0].body as Record<
      string,
      unknown
    >;
    expect(body.delivery).toBe("email_and_paper");
  });

  it("DEF-BIL-10535 — with no email on file, Email and Both are greyed and say why", async () => {
    const { client, calls } = fakeClient({
      openCase: {
        ...CASE_PENDING_APPROVER,
        delivery: {
          choices: ["email", "paper", "email_and_paper"],
          preselected: "paper",
          email_on_file: false,
        },
      },
    });
    mount(client, `?case=${CASE_ID}`);
    const approve = await screen.findByRole("button", { name: t("billing.fixBill.send.approve") });
    const group = await screen.findByRole("radiogroup", { name: t("billing.fixBill.send.sendBy") });
    for (const key of ["email", "email_and_paper"]) {
      const option = within(group).getByRole("radio", {
        name: t(`billing.fixBill.send.delivery.${key}`),
      });
      expect((option as HTMLButtonElement).disabled).toBe(true);
      fireEvent.click(option);
    }
    expect(document.body.textContent).toContain(t("billing.fixBill.send.noEmail"));
    fireEvent.click(approve);
    await waitFor(() =>
      expect(posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)).toHaveLength(1),
    );
    const body = posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)[0].body as Record<
      string,
      unknown
    >;
    expect(body.delivery).toBe("paper");
  });

  it("DEF-BIL-10535 — a case that offers no choice sends none", async () => {
    const { client, calls } = fakeClient({ openCase: { ...CASE_PENDING_APPROVER, delivery: null } });
    mount(client, `?case=${CASE_ID}`);
    const approve = await screen.findByRole("button", { name: t("billing.fixBill.send.approve") });
    expect(screen.queryByRole("radiogroup", { name: t("billing.fixBill.send.sendBy") })).toBeNull();
    fireEvent.click(approve);
    await waitFor(() =>
      expect(posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)).toHaveLength(1),
    );
    const body = posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)[0].body as Record<
      string,
      unknown
    >;
    expect("delivery" in body).toBe(false);
  });

  it("DEF-BIL-10082 — a run that left a bill failed says so, names the reason, and Try again resumes through /execute", async () => {
    const failedCase: CorrectionCaseV2 = {
      ...CASE_DONE,
      status: "open",
      viewer_can_approve: false,
      bills_detail: CASE_DONE.bills_detail.map((bill) => ({
        ...bill,
        status: "failed",
        failure_reason:
          "a fee line carries a quantity with no unit on version 01a132c6-931d-755c-b465-e07721384385",
        credit_note_no: null,
        rebill_invoice_no: null,
      })),
    };
    const { client, calls } = fakeClient({ openCase: failedCase });
    mount(client, `?case=${CASE_ID}`);
    const panel = await hook("[data-fix-send=unfinished]");
    expect(panel.textContent).toContain(t("billing.fixBill.done.unfinished"));
    expect(panel.textContent).toContain(t("billing.fixBill.done.failed"));
    expect(panel.textContent).toContain("a fee line carries a quantity with no unit");
    expect(panel.textContent).not.toContain(t("billing.fixBill.send.waiting"));
    fireEvent.click(screen.getByRole("button", { name: t("billing.fixBill.done.retry") }));
    await waitFor(() => expect(posts(calls, `/corrections/${CASE_ID}/execute`)).toHaveLength(1));
    noUuidOnScreen();
  });

  it("DEF-BIL-10085 — goodwill: For finance shows the write-off entry, and Done shows the net that was checked", async () => {
    const goodwill: CorrectionPreview = {
      ...PREVIEW_CREDIT,
      finance: {
        ...PREVIEW_CREDIT.finance,
        entries: [
          { entry: "credit_notes", amount: "0.0000" },
          { entry: "new_bills", amount: "0.0000" },
          { entry: "goodwill", amount: "40.0000" },
        ],
      },
    };
    const tr = ((key: string, opts?: Record<string, unknown>) => t(key, opts)) as never;
    const fmt = { t: tr, currency: "USD", language: "en" };
    const { unmount } = render(<ForFinance preview={goodwill} approver t={tr} fmt={fmt} />);
    const text = document.body.textContent ?? "";
    expect(text).toContain(t("billing.fixBill.finance.goodwill"));
    expect(text).toContain(t("billing.fixBill.finance.writeOff"));
    expect(text).toContain(t("billing.fixBill.finance.customerCredit"));
    expect(text).toContain("$40.00");
    unmount();
    const { client } = fakeClient({
      openCase: {
        ...CASE_DONE,
        net_delta: "0.0000",
        preview: { ...PREVIEW_CREDIT, totals: { ...PREVIEW_CREDIT.totals, net: "-40.0000" } },
      },
    });
    mount(client, `?case=${CASE_ID}`);
    const done = await hook("[data-fix-send=done]");
    expect(done.textContent).toContain("−$40.00");
  });

  it("DEF-BIL-10097 — after a resume with no result, Done counts the bills that are done", async () => {
    const { client } = fakeClient({ openCase: { ...CASE_DONE, result: undefined } });
    mount(client, `?case=${CASE_ID}`);
    const done = await hook("[data-fix-send=done]");
    expect(done.textContent).toContain(t("billing.fixBill.done.title", { count: 1 }));
  });

  it("DEF-BIL-10100 — a case closed without correcting reads Closed, with no net change", async () => {
    const closedRow = {
      ...CASE_PENDING_CLERK,
      status: "done",
      net_delta: "-9.4700",
      currency: "USD",
      bills: 1,
      closed_reason: "Sent back by the approver.",
      closed_without_correcting: true,
    };
    mount(fakeClient({ cases: [closedRow] }).client);
    const row = (await screen.findByText(t("billing.fix.status.closed"))).closest("tr") as HTMLElement;
    expect(row.textContent).not.toContain(t("billing.fix.status.done"));
    expect(row.textContent).not.toContain("9.47");
  });

  it("bulk done: done, failed and already done kept apart", async () => {
    const { client } = fakeClient({ openCase: CASE_DONE_BULK });
    mount(client, `?case=${CASE_ID}`);
    const done = await hook("[data-fix-send=done]");
    const figure = (name: string) => done.querySelector(`[data-fix-result=${name}]`)?.textContent;
    expect(figure("succeeded")).toBe("42");
    expect(figure("failed")).toBe("1");
    expect(figure("skipped")).toBe("1");
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// DEF-BIL-10091 — bulk runs in the BACKGROUND, with progress on screen
// ═══════════════════════════════════════════════════════════════════════════
const PREVIEW_JOB = "job-preview-1";
const SEND_JOB = "job-send-1";
const ISSUE_JOB = "job-issue-1";

function jobState(over: Record<string, unknown>) {
  return {
    job_id: PREVIEW_JOB,
    act: "preview",
    status: "succeeded",
    progress: { done: 48, total: 48, stage: "pricing" },
    error: null,
    refusal: null,
    preview: null,
    case: null,
    ...over,
  };
}

async function toBulkFix(client: ApiClient) {
  mount(client);
  fireEvent.click(
    await screen.findByRole("button", { name: new RegExp(t("billing.fixBill.option.bulk")) }),
  );
  const run = (await screen.findByLabelText(
    new RegExp(`^${t("billing.fixBill.run.run")}`),
  )) as HTMLSelectElement;
  await waitFor(() => expect(run.options.length).toBeGreaterThan(1));
  fireEvent.change(run, { target: { value: run.options[1].value } });
  fireEvent.click(continueButton());
  await waitFor(() => expect(document.querySelector("[data-fix-rows]")).not.toBeNull());
  const row = addRow("wrong_plan");
  const version = await waitFor(() =>
    within(row).getByLabelText(new RegExp(`^${t("billing.fixBill.col.shouldBe")} 1$`)),
  );
  fireEvent.change(version, { target: { value: PLAN_V5 } });
  return row;
}

describe("DEF-BIL-10091 — a bulk Fix a bill runs in the background", () => {
  it("the preview is a job: 'Working out 48 bills · 12 done', then the answer, a page at a time", async () => {
    const pages: string[] = [];
    const { client, calls } = fakeClient({
      accept: { preview: PREVIEW_JOB },
      polls: {
        [PREVIEW_JOB]: [
          { status: "running", progress: { done: 12, total: 48, stage: "pricing" } },
          { status: "succeeded", progress: { done: 48, total: 48, stage: "pricing" } },
        ],
      },
      jobs: {
        [PREVIEW_JOB]: (params) => {
          pages.push(params.get("page") ?? "");
          return jobState({ preview: { ...PREVIEW_BULK, page: 1, per: 25 } });
        },
      },
    });
    await toBulkFix(client);
    const progress = await hook("[data-fix-job=pricing]");
    expect(progress.textContent).toBe(
      t("billing.fixBill.job.pricing", { total: 48, done: 12 }),
    );
    expect(progress.textContent).toContain("48");
    const up = await hook("[data-fix-tile=up]", 4000);
    expect(up.textContent).toContain("$412.36");
    expect(document.querySelector("[data-fix-job]")).toBeNull();
    expect(posts(calls, "/corrections/preview")).toHaveLength(1);
    const body = posts(calls, "/corrections/preview")[0].body as Record<string, unknown>;
    expect(body.page).toBeUndefined();
    expect(pages.length).toBeGreaterThan(0);
    noUuidOnScreen();
  });

  it("Q3 — a Wrong plan that bills water at $0.00 is a WARNING beside the row, and Continue still goes on", async () => {
    const warned = {
      ...PREVIEW_BULK,
      plan_warnings: [{ position: 1, service_code: "water", amount: "0.00", bills: 48 }],
    } as CorrectionPreview;
    const { client } = fakeClient({ preview: () => warned });
    const row = await toBulkFix(client);
    const note = await waitFor(() => {
      const found = row.querySelector("[data-fix-plan-zero=water]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(note.textContent).toBe(
      t("billing.fixBill.planZero", { service: t("rating.service.water"), amount: "$0.00" }),
    );
    await hook("[data-fix-preview=settled]");
    fireEvent.click(continueButton());
    await hook("[data-fix-check]");
  });

  it("Send names the preview job and follows its own job to the case", async () => {
    const { client, calls } = fakeClient({
      accept: { preview: PREVIEW_JOB, send: SEND_JOB },
      jobs: {
        [PREVIEW_JOB]: () => jobState({ preview: { ...PREVIEW_BULK, page: 1, per: 25 } }),
        [SEND_JOB]: () => jobState({ job_id: SEND_JOB, act: "send", case: CASE_PENDING_CLERK }),
      },
    });
    await toBulkFix(client);
    await hook("[data-fix-preview=settled] [data-fix-tile=up]");
    fireEvent.click(continueButton());
    await hook("[data-fix-check]");
    fireEvent.click(continueButton());
    fireEvent.click(await screen.findByLabelText(t("billing.fixBill.send.checked")));
    fireEvent.click(screen.getByRole("button", { name: t("billing.fixBill.send.send") }));
    await waitFor(() => expect(posts(calls, "/corrections")).toHaveLength(1));
    const body = posts(calls, "/corrections")[0].body as Record<string, unknown>;
    expect(body.preview_job_id).toBe(PREVIEW_JOB);
    await hook("[data-fix-send=waiting]");
  });

  it("Q5 — an approval whose figures moved is refused: 'Figures changed. Check again.'", async () => {
    const bulkCase = {
      ...CASE_PENDING_APPROVER,
      scope_kind: "run",
      preview: { ...PREVIEW_BULK },
    } as CorrectionCaseV2;
    const { client, calls } = fakeClient({
      openCase: bulkCase,
      accept: { approve: ISSUE_JOB },
      polls: {
        [ISSUE_JOB]: [
          { status: "running", progress: { done: 3, total: 48, stage: "checking" } },
          { status: "succeeded" },
        ],
      },
      jobs: {
        [ISSUE_JOB]: () =>
          jobState({
            job_id: ISSUE_JOB,
            act: "approve_issue",
            refusal: { message_key: "billing.correction.figuresMoved", params: {} },
            case: bulkCase,
          }),
      },
    });
    mount(client, `?case=${CASE_ID}`);
    fireEvent.click(await screen.findByRole("button", { name: t("billing.fixBill.send.approve") }));
    const progress = await hook("[data-fix-job=checking]");
    expect(progress.textContent).toBe(t("billing.fixBill.job.checking", { total: 48, done: 3 }));
    await waitFor(
      () => expect(document.body.textContent).toContain(t("billing.correction.figuresMoved")),
      { timeout: 4000 },
    );
    expect(posts(calls, `/corrections/${CASE_ID}/approve-and-issue`)).toHaveLength(1);
    expect(document.querySelector("[data-fix-send=done]")).toBeNull();
  });

  it("PO 2026-10-13 — a service whose usage was shared by days says so on the new bill", async () => {
    const shared = {
      ...PREVIEW_ONE,
      bills: PREVIEW_ONE.bills.map((bill) => ({ ...bill, usage_shared_by_days: ["water"] })),
    } as CorrectionPreview;
    const { client } = fakeClient({ preview: () => shared });
    await toFix(client);
    typeShouldBe(addRow("wrong_read"), "1162.4");
    const note = await hook("[data-fix-side=becomes] [data-fix-shared-by-days=water]");
    expect(note.textContent).toBe(t("billing.fixBill.usageSharedByDays"));
    expect(document.querySelector("[data-fix-side=was] [data-fix-shared-by-days]")).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-BIL-10147 — a case is numbered at Send (G3, PO 2026-10-14): the number
// is on Corrections so far and on the result; the words are kept for the one
// case a deleted series leaves unnumbered.
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-BIL-10147 — the case number at Send", () => {
  it("Corrections so far shows CC-2026-001, and words only for a case with none", async () => {
    const numbered = { ...CASE_PENDING_CLERK, case_no: "CC-2026-001" };
    const unnumbered = {
      ...CASE_PENDING_CLERK,
      id: "ca5e0000-0000-4000-8000-000000000013",
      case_no: null,
    };
    mount(fakeClient({ cases: [numbered, unnumbered] }).client);
    const link = await screen.findByText("CC-2026-001");
    expect(link.closest("tr")).not.toBeNull();
    expect(screen.getAllByText(t("billing.fix.noCaseNo"))).toHaveLength(1);
    noUuidOnScreen();
  });

  it("the result after Send reads Case CC-2026-001, never Not numbered yet", async () => {
    const { client } = fakeClient({ openCase: { ...CASE_DONE, case_no: "CC-2026-001" } });
    mount(client, `?case=${CASE_ID}`);
    const done = await hook("[data-fix-send=done]");
    expect(done.textContent).toContain(t("billing.fixBill.done.case"));
    expect(done.textContent).toContain("CC-2026-001");
    expect(done.textContent).not.toContain(t("billing.fixBill.done.noCaseNo"));
  });
});
