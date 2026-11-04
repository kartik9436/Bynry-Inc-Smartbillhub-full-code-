// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Plan:    15-bulk-bill-run-build-plan.md T4 — component tests, the page
//          mounted under the REAL route pattern `/:tenant/billing/run`
// Stories: US-BIL-036 … US-BIL-041 (the §3 cases this file can reach on the
//          client; the server-side ones live in 06-backend/tests)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  CYCLE_ID,
  RUN_ID,
  SECOND_TEMPLATE_ID,
  TEMPLATE_ID,
  UNIT_NOBODY_ID,
  UNIT_NO_METER_ID,
} from "./__fixtures__/bulkRunFixtures";
import { TENANT, mountRun, where } from "./__fixtures__/mountRun";

afterEach(cleanup);

async function chooseCycle() {
  const select = await screen.findByLabelText(/^Cycle/);
  await waitFor(() => expect(within(select).getAllByRole("option").length).toBeGreaterThan(1));
  fireEvent.change(select, { target: { value: CYCLE_ID } });
}

function startButton() {
  return screen.getByRole("button", { name: "Start checking" });
}

const OPEN_RUN = `?run=${RUN_ID}`;

describe("T4 · Scope (US-BIL-036)", () => {
  it("the rail is four steps and the page opens at Scope with no services filter and no standing answers", async () => {
    mountRun();
    const rail = await screen.findByRole("navigation", { name: /./ });
    for (const label of ["Scope", "Check", "Sign off", "Send"]) {
      expect(within(rail).getByText(label)).toBeInTheDocument();
    }
    expect(document.querySelectorAll("[data-wizard-step]")).toHaveLength(4);
    expect(screen.queryByText(/which services/i)).toBeNull();
    expect(screen.queryByRole("checkbox", { name: /Electric/i })).toBeNull();
  });

  it("TC-2 continuous: the cycle prefills the period, the warnings show at the top, Start is enabled", async () => {
    const fake = mountRun({ scope: "continuous" });
    await chooseCycle();
    fireEvent.change(screen.getByLabelText(/^Run name/), { target: { value: "September 2026 · Riverside" } });
    expect(screen.getByLabelText(/^Period start/)).toHaveValue("2026-09-01");
    await screen.findByText("2 warnings. You can still start.");
    expect(document.querySelector('[data-continuity="continuous"]')).toHaveTextContent("Follows run BR-0231");
    await waitFor(() => expect(startButton()).toBeEnabled());
    const preview = fake.calls.filter((call) => call.path === "/billing/runs/scope-preview").pop();
    expect(preview?.query).toMatchObject({ cycle_id: CYCLE_ID, label: "September 2026 · Riverside", template_id: TEMPLATE_ID });
  });

  // BULK-CHG-35 (one red box listing every refusal, one amber box for warnings, each line on its field)
  it("TC-6 every refusal at once: five lines in the red box, each on its field, Start disabled with the count", async () => {
    mountRun({ scope: "problems" });
    await chooseCycle();
    const box = await screen.findByText("Fix 5 things to start.");
    const lines = within(box.parentElement as HTMLElement).getAllByRole("listitem");
    expect(lines).toHaveLength(5);
    expect(lines.map((li) => li.textContent)).toEqual([
      "Run name — Enter a run name.",
      "Period end — Ends before it starts.",
      "Bill date — Cycle has no bill day. Enter one.",
      "Days to pay — Enter whole days, zero or more.",
      "Bill template — Not published. Publish it first.",
    ]);
    // Each also on its field (the box line is one text run, the field its own).
    expect(screen.getByText("Ends before it starts.")).toBeInTheDocument();
    expect(screen.getByText("Enter a run name.")).toBeInTheDocument();
    // The run-number series is a WARNING (changes row 43).
    expect(screen.getByText(/No number series yet/)).toBeInTheDocument();
    expect(startButton()).toBeDisabled();
    expect(document.querySelector('[data-run-footnote="refusal"]')).toHaveTextContent("Fix 5 things first.");
  });

  it("TC-4 overlap refuses on Period start and links the run in a new tab; TC-5 gap warns with no tick box", async () => {
    mountRun({ scope: "overlap" });
    await chooseCycle();
    const link = await screen.findByRole("link", { name: "Open BR-0231" });
    expect(link).toHaveAttribute("href", `/${TENANT}/billing/run?run=run-0231`);
    expect(link).toHaveAttribute("target", "_blank");
    cleanup();
    mountRun({ scope: "gap" });
    await chooseCycle();
    await screen.findAllByText(/not billed/);
    expect(screen.queryByRole("checkbox", { name: /continue/i })).toBeNull();
    await waitFor(() => expect(startButton()).toBeEnabled());
  });

  it("DEF-BIL-8221 · TC-12 Nobody to bill lists the units, each with Add account in a new tab", async () => {
    const fake = mountRun();
    await chooseCycle();
    fireEvent.click(await screen.findByRole("button", { name: "See units" }));
    const panel = screen.getByRole("dialog", { name: "Units" });
    expect(within(panel).getByText("Nobody to bill")).toBeInTheDocument();
    const row = await within(panel).findByText("1416 Elm St · Unit B");
    const tr = row.closest("tr") as HTMLElement;
    expect(tr).toHaveTextContent("Unit B");
    expect(tr).toHaveTextContent("Water");
    expect(tr).toHaveTextContent("AC-2026-00099");
    expect(tr).toHaveTextContent("Moved out");
    const link = within(tr).getByRole("link", { name: /Add account/ });
    expect(link).toHaveAttribute("href", `/${TENANT}/premises/units/${UNIT_NOBODY_ID}?tab=account`);
    expect(link).toHaveAttribute("target", "_blank");
    expect(within(panel).queryByText("Not available yet.")).toBeNull();
    const read = fake.calls.find((call) => call.path === "/billing/runs/scope-list");
    expect(read?.query).toMatchObject({ cycle_id: CYCLE_ID, list: "nobody", page: 1 });
    fireEvent.click(within(panel).getAllByRole("button", { name: "Close" }).pop() as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("DEF-BIL-8221 · TC-12 Missing meter lists the services, each with Fit a meter in a new tab", async () => {
    mountRun();
    await chooseCycle();
    fireEvent.click(await screen.findByRole("button", { name: "See services" }));
    const panel = screen.getByRole("dialog", { name: "Services" });
    const row = await within(panel).findByText("1408 Elm St · Unit A");
    const tr = row.closest("tr") as HTMLElement;
    expect(tr).toHaveTextContent("Unit A");
    expect(tr).toHaveTextContent("Gas");
    expect(tr).toHaveTextContent("AC-2026-00101");
    const link = within(tr).getByRole("link", { name: /Fit a meter/ });
    expect(link).toHaveAttribute("href", `/${TENANT}/premises/units/${UNIT_NO_METER_ID}?tab=assets`);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("DEF-BIL-8222 the template select offers every published template, not only the fallback", async () => {
    const fake = mountRun({ twoTemplates: true });
    await chooseCycle();
    const select = screen.getByLabelText(/^Bill template/) as HTMLSelectElement;
    await waitFor(() => expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(
      expect.arrayContaining(["Standard bill · v4", "Winter insert · v1"]),
    ));
    // Two to choose from → the clerk chooses; nothing is picked for them.
    expect(select).toHaveValue("");
    fireEvent.change(select, { target: { value: SECOND_TEMPLATE_ID } });
    await waitFor(() => {
      const preview = fake.calls.filter((call) => call.path === "/billing/runs/scope-preview").pop();
      expect(preview?.query).toMatchObject({ template_id: SECOND_TEMPLATE_ID });
    });
    expect(fake.calls.some((call) => call.path === "/bill-templates")).toBe(false);
  });

  it("Start sends run name and template and no services, then moves to Check with ?run=", async () => {
    const fake = mountRun();
    await chooseCycle();
    fireEvent.change(screen.getByLabelText(/^Run name/), { target: { value: "September 2026 · Riverside" } });
    await waitFor(() => expect(startButton()).toBeEnabled());
    await act(async () => {
      fireEvent.click(startButton());
    });
    const post = await waitFor(() => {
      const found = fake.calls.find((call) => call.method === "POST" && call.path === "/billing/runs");
      expect(found).toBeDefined();
      return found;
    });
    expect(post?.body).toMatchObject({ label: "September 2026 · Riverside", template_id: TEMPLATE_ID, cycle_id: CYCLE_ID });
    expect(post?.body).not.toHaveProperty("scope_services");
    await waitFor(() => expect(where.location).toBe(`/${TENANT}/billing/run?run=${RUN_ID}`));
  });
});

describe("T4 · Check (US-BIL-037, -038) — the SERVED grouped read (DEF-BIL-8216)", () => {
  // BULK-CHG-36
  it("re-opening a draft run lands on Check: five tiles from the server, the list, Checked at and Check again", async () => {
    const fake = mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    expect(screen.getByRole("button", { name: "Check again" })).toBeInTheDocument();
    for (const tile of ["Problem types", "Blocked accounts", "Need a decision", "Warnings", "Ready accounts"]) {
      expect(screen.getByText(tile)).toBeInTheDocument();
    }
    const list = screen.getByRole("navigation", { name: "Problems" });
    expect(within(list).getByRole("button", { name: /Ready to bill/ })).toBeInTheDocument();
    // Nothing to bill is not a problem (BR-BIL-1025): labelled, never listed.
    expect(within(list).queryByRole("button", { name: /^Nothing to bill/ })).toBeNull();
    // The screen read the SERVER's grouping — never the legacy raw reads.
    expect(fake.calls.some((call) => call.path === `/billing/runs/${RUN_ID}/check/findings` && call.query === undefined)).toBe(true);
    expect(fake.calls.some((call) => call.path.endsWith("/findings") && !call.path.includes("/check/"))).toBe(false);
    expect(fake.calls.some((call) => call.path.endsWith("/exceptions"))).toBe(false);
  });

  // BULK-CHG-36 · NFR-3
  it("a tag's accounts are ONE server page (`?tag=`), never the whole run in the browser", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No reading/ }));
    const pane = await waitFor(() => {
      const found = document.querySelector('[data-tag-pane="missing_read"]') as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    await within(pane).findByRole("button", { name: "AC-2026-12881" });
    const read = fake.calls.find((call) => call.query?.tag === "missing_read");
    expect(read?.query).toMatchObject({ tag: "missing_read", page: 1, per: 50 });
  });

  // BULK-CHG-36 — TC-8 answer for all
  it("TC-8 answer for all writes ONE standing answer for the tag", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No reading/ }));
    const pane = await waitFor(() => document.querySelector('[data-tag-pane="missing_read"]') as HTMLElement);
    fireEvent.click(within(pane).getByRole("radio", { name: "Hold" }));
    await waitFor(() => {
      const post = fake.calls.find((call) => call.path.endsWith("/check/decisions") && call.method === "POST");
      expect(post?.body).toEqual({ case: "missing_read", choice: "hold", scope: "all" });
    });
  });

  // BULK-CHG-20 · U5 — DEF-BIL-8418 (BR-BIL-1040 amended)
  it("U5 DEF-BIL-8418: with nothing stored, Answer for all opens on the tag's default and Apply stores it", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No reading/ }));
    const pane = await waitFor(() => document.querySelector('[data-tag-pane="missing_read"]') as HTMLElement);
    expect(within(pane).getByRole("radio", { name: "Estimate" })).toBeChecked();
    fireEvent.click(within(pane).getByRole("button", { name: "Apply to all 3" }));
    await waitFor(() => {
      const post = fake.calls.find((call) => call.path.endsWith("/check/decisions") && call.method === "POST");
      expect(post?.body).toEqual({ case: "missing_read", choice: "estimate", scope: "all" });
    });
  });

  // BULK-CHG-36 — PO 2026-09-30 fixed-charge case 2
  it("PO 2026-09-30: Standing charges only offers Waive, which needs a reason and states what it does", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^Standing charges only/ }));
    const pane = await waitFor(() => {
      const found = document.querySelector('[data-tag-pane="base_only_billing"]') as HTMLElement;
      expect(within(found).getByText("Base not billed this month.")).toBeInTheDocument();
      return found;
    });
    const select = pane.querySelector("#decide-acc-11-all") as HTMLSelectElement;
    expect(within(select).getByRole("option", { name: "Waive" })).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "waive" } });
    const box = pane.querySelector("[data-reason-box]") as HTMLElement;
    const save = within(box).getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    expect(fake.calls.some((call) => call.path.endsWith("/check/decisions"))).toBe(false);
    fireEvent.change(within(box).getByLabelText("Reason"), { target: { value: "Vacant all month" } });
    fireEvent.click(save);
    await waitFor(() => {
      const post = fake.calls.find((call) => call.path.endsWith("/check/decisions"));
      expect(post?.body).toEqual({
        case: "base_only_billing",
        choice: "waive",
        scope: "accounts",
        account_ids: ["acc-11"],
        reason: "Vacant all month",
      });
    });
  });

  // BULK-CHG-36 — DEF-BIL-8218 inline fix
  it("DEF-BIL-8218: a row with no plan is fixed ON THE ROW — choose a plan, Save, and the owning write is asked for", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No plan/ }));
    const pane = await waitFor(() => {
      const found = document.querySelector('[data-tag-pane="unit_has_no_plan"]') as HTMLElement;
      expect(found.querySelector('[data-fix-here="set_plan"]')).not.toBeNull();
      return found;
    });
    const control = pane.querySelector('[data-fix-here="set_plan"]') as HTMLElement;
    const select = within(control).getByRole("combobox");
    await waitFor(() => expect(within(select).getByRole("option", { name: "Residential Standard" })).toBeInTheDocument());
    fireEvent.change(select, { target: { value: "plan-1" } });
    fireEvent.click(within(control).getByRole("button", { name: "Save" }));
    await waitFor(() => {
      const post = fake.calls.find((call) => call.path.endsWith("/check/fix"));
      expect(post?.body).toEqual({ account_id: "acc-1", fix: "set_plan", plan_id: "plan-1" });
    });
    // The pane reads the saved answer again — never an optimistic "fixed".
    await waitFor(() => expect(fake.calls.filter((call) => call.query?.tag === "unit_has_no_plan").length).toBeGreaterThan(1));
  });

  // BULK-CHG-51 · BULK-CHG-36 — DEF-BIL-8472 (U5)
  it("DEF-BIL-8472: an overlap row never offers Bill as it stands, and Apply to selected answers the gap row alone", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^Gap or overlap/ }));
    const pane = await waitFor(() => {
      const found = document.querySelector('[data-tag-pane="billing_continuity"]') as HTMLElement;
      expect(found.querySelector("#decide-acc-16-all")).not.toBeNull();
      return found;
    });
    const overlap = pane.querySelector("#decide-acc-16-all") as HTMLSelectElement;
    const gap = pane.querySelector("#decide-acc-15-all") as HTMLSelectElement;
    expect(within(overlap).queryByRole("option", { name: "Bill as it stands" })).toBeNull();
    expect(within(gap).getByRole("option", { name: "Bill as it stands" })).toBeInTheDocument();
    fireEvent.click(within(pane).getByRole("radio", { name: "Bill as it stands" }));
    fireEvent.click(within(pane).getByRole("checkbox", { name: "Select all on this page" }));
    expect(within(pane).getByText("1 cannot take this answer.")).toBeInTheDocument();
    const apply = within(pane).getByRole("button", { name: "Apply to 1 selected" });
    await waitFor(() => expect(apply).toBeEnabled());
    fireEvent.click(apply);
    await waitFor(() => {
      const posts = fake.calls.filter((call) => call.path.endsWith("/check/decisions"));
      expect(posts.at(-1)?.body).toEqual({ case: "billing_continuity", choice: "bill_as_is", scope: "accounts", account_ids: ["acc-15"] });
    });
  });

  // BULK-CHG-36
  it("the Blocked tile narrows the list; a search that hides the open tag opens the first one shown", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    fireEvent.click(screen.getByText("Blocked accounts").closest("button") as HTMLElement);
    const list = screen.getByRole("navigation", { name: "Problems" });
    expect(within(list).queryByRole("button", { name: /^Late fee/ })).toBeNull();
    expect(within(list).getByRole("button", { name: /^No unit/ })).toBeInTheDocument();
    fireEvent.click(screen.getByText("Problem types").closest("button") as HTMLElement);
    fireEvent.change(screen.getByPlaceholderText("Find a problem"), { target: { value: "size" } });
    expect(document.querySelector('[data-tag-pane="connection_size_unresolved_for_sized_schedule"]')).not.toBeNull();
  });

  // BULK-CHG-36
  it("an account opens Fix account listing every problem on it, from `?account=`", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No plan/ }));
    fireEvent.click(await screen.findByRole("button", { name: "AC-2026-12881" }));
    const panel = screen.getByRole("dialog", { name: "Fix account" });
    // AC-2026-12881: no reading, a swapped meter, no plan.
    await within(panel).findByText("3 problems on this account");
    expect(panel.querySelectorAll("[data-fix-card]")).toHaveLength(3);
    expect(fake.calls.some((call) => call.query?.account === "acc-1")).toBe(true);
  });

  // BULK-CHG-22 — DEF-BIL-8219
  it("DEF-BIL-8219: Re-check on Fix account re-checks THAT account only, by name", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No plan/ }));
    fireEvent.click(await screen.findByRole("button", { name: "AC-2026-12881" }));
    const panel = screen.getByRole("dialog", { name: "Fix account" });
    fireEvent.click(panel.querySelector("[data-recheck-account]") as HTMLElement);
    const post = await waitFor(() => {
      const found = fake.calls.find((call) => call.method === "POST" && call.path === `/billing/runs/${RUN_ID}/check/recheck`);
      expect(found).toBeDefined();
      return found;
    });
    expect((post?.body as { account_ids: string[] }).account_ids).toEqual(["acc-1"]);
  });

  // BULK-CHG-41 — DEF-BIL-8414
  it("DEF-BIL-8414: Ready to bill shows image 21's services, plan and readings columns", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    fireEvent.click(screen.getByText("Ready accounts").closest("button") as HTMLElement);
    const pane = await waitFor(() => {
      const found = document.querySelector('[data-tag-pane="ready"]') as HTMLElement;
      expect(within(found).getAllByRole("row")).toHaveLength(13);
      return found;
    });
    const headers = within(pane).getAllByRole("columnheader").map((th) => th.textContent);
    expect(headers).toEqual(expect.arrayContaining(["Services", "Plan", "Readings"]));
    const second = within(pane).getByText("AC-2026-30017").closest("tr") as HTMLElement;
    expect(second).toHaveTextContent("Electric");
    expect(second).toHaveTextContent("Water");
    expect(second).toHaveTextContent("Residential 2026");
    expect(second).toHaveTextContent("All read");
    const third = within(pane).getByText("AC-2026-30034").closest("tr") as HTMLElement;
    expect(third).toHaveTextContent("Some estimated");
  });

  // BULK-CHG-41 — DEF-BIL-8217
  it("DEF-BIL-8217: Ready to bill pages on the server, filters Regular/Master, and leaves one out / puts one back", async () => {
    const fake = mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    fireEvent.click(screen.getByText("Ready accounts").closest("button") as HTMLElement);
    const pane = await waitFor(() => {
      const found = document.querySelector('[data-tag-pane="ready"]') as HTMLElement;
      expect(within(found).getAllByRole("row")).toHaveLength(13);
      return found;
    });
    expect(within(pane).getByText("1 left out")).toBeInTheDocument();
    expect(within(pane).getByText("Leave one out. Bill it later.")).toBeInTheDocument();
    fireEvent.click(within(pane).getByRole("tab", { name: /^Master/ }));
    await waitFor(() => expect(within(pane).getAllByRole("row")).toHaveLength(3));
    expect(fake.calls.some((call) => call.query?.list === "ready" && call.query?.kind === "master")).toBe(true);
    fireEvent.click(within(pane).getByRole("tab", { name: "All" }));
    await waitFor(() => expect(within(pane).getAllByRole("row")).toHaveLength(13));
    fireEvent.click(within(pane).getAllByRole("button", { name: "Leave out" })[0]);
    await waitFor(() => {
      const post = fake.calls.find((call) => call.path.endsWith("/check/leave-out"));
      expect(post?.body).toEqual({ account_ids: ["ready-0"] });
    });
    fireEvent.click(within(pane).getByRole("button", { name: "Put back" }));
    await waitFor(() => {
      const post = fake.calls.find((call) => call.path.endsWith("/check/put-back"));
      expect(post?.body).toEqual({ account_ids: ["ready-3"] });
    });
  });

  // BULK-CHG-36
  it("TC-15 module down: names what failed, who fixes it, the run is saved, the server's reference, Try again", async () => {
    // DEF-BIL-8510 — the fake answers in the server's OWN stop envelope now
    // (check_api._stop_response); it used to answer in a shape the server did
    // not send, which is how the generic message on a live stack went unseen.
    mountRun({ moduleDown: true }, OPEN_RUN);
    const stop = await screen.findByRole("alert");
    expect(stop).toHaveTextContent("Meter Reads is not answering. No account was checked.");
    expect(stop).toHaveTextContent("Support can fix this.");
    expect(stop).toHaveTextContent("The run is saved.");
    expect(stop).toHaveTextContent("Ref SBH-73FBC9D7.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  // BULK-CHG-25 · F1 — DEF-BIL-8511
  it("F1 DEF-BIL-8511: a Check whose worker was lost says how far it got, and Resume hands it back", async () => {
    const fake = mountRun({ checkStopped: true }, OPEN_RUN);
    const notice = await screen.findByText("Checking stopped at 400 of 1,406.");
    fireEvent.click(within(notice.parentElement as HTMLElement).getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(fake.calls.some((call) => call.method === "POST" && call.path.endsWith("/check/resume"))).toBe(true));
  });

  // BULK-CHG-25 — DEF-BIL-8224
  it("DEF-BIL-8224: while the Check job runs, Checking shows its n of N", async () => {
    mountRun({ checking: true }, OPEN_RUN);
    await screen.findByText("Checking accounts");
    await screen.findByText("400 of 1,406");
  });

  // BULK-CHG-25 — DEF-BIL-8224
  it("DEF-BIL-8224: a run never checked is checked on opening, once, as a job — then the results show", async () => {
    const fake = mountRun({ unchecked: true }, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/, undefined, { timeout: 4000 });
    const starts = fake.calls.filter((call) => call.method === "POST" && call.path === `/billing/runs/${RUN_ID}/check`);
    expect(starts).toHaveLength(1);
  });

  // BULK-CHG-36 · U5 — DEF-BIL-8419
  it("DEF-BIL-8419: a tag whose page has not arrived never says No accounts here", async () => {
    const fake = mountRun({ holdTagRead: "missing_read" }, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No reading/ }));
    await waitFor(() => expect(fake.calls.some((call) => call.query?.tag === "missing_read")).toBe(true));
    const pane = await waitFor(() => {
      const found = document.querySelector('[data-tag-pane="missing_read"]') as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    expect(within(pane).queryByText("No accounts here.")).toBeNull();
  });

  // BULK-CHG-25 · U4 — DEF-BIL-8417
  it("DEF-BIL-8417: while a new run's first Check is still running, the step says Checking accounts and never shows 0 tiles", async () => {
    const fake = mountRun({ unchecked: true, holdCheckStart: true }, OPEN_RUN);
    await waitFor(() =>
      expect(fake.calls.some((call) => call.method === "POST" && call.path === `/billing/runs/${RUN_ID}/check`)).toBe(true),
    );
    expect(await screen.findByText("Checking accounts")).toBeInTheDocument();
    expect(document.querySelector("[data-check-results]")).toBeNull();
    expect(screen.queryByText(/Checked 0 accounts/)).toBeNull();
  });

  // BULK-CHG-25 · U4 — DEF-BIL-8417 (the summary read behind the saved Check)
  it("DEF-BIL-8417: a summary read taken before the Check saved is not drawn as 0 tiles", async () => {
    const fake = mountRun({ summaryBehind: true }, OPEN_RUN);
    // After the summary has ARRIVED (a loading page says Checking anyway).
    await waitFor(() =>
      expect(fake.calls.some((call) => call.path.endsWith("/check/findings") && call.query?.tag === undefined)).toBe(true),
    );
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 300));
    });
    expect(screen.getByText("Checking accounts")).toBeInTheDocument();
    expect(document.querySelector("[data-check-results]")).toBeNull();
  });

  // BULK-CHG-25
  it("Check again starts the Check as a job", async () => {
    const fake = mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    });
    expect(fake.calls.some((call) => call.method === "POST" && call.path === `/billing/runs/${RUN_ID}/check`)).toBe(true);
  });

  // BULK-CHG-39 (bills are calculated between step 2 and step 3, shown as Calculating n of N)
  it("US-BIL-038: Price shows Calculating with the job's n of N, then Sign off opens", async () => {
    const fake = mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^Price/ }));
    });
    await screen.findByText("Calculating bills");
    await screen.findByText("754 of 1,371");
    await screen.findByText("Run summary", undefined, { timeout: 4000 });
    expect(fake.calls.some((call) => call.path.endsWith("/calculate"))).toBe(true);
  });
});

describe("T4 · Sign off (US-BIL-039) and Not in this run (US-BIL-041) — served figures (DEF-BIL-8220)", () => {
  it("TC-8 Sign off stays disabled until all five are ticked, then records each separately", async () => {
    const fake = mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const actions = document.querySelector('[data-wizard="actions"]') as HTMLElement;
    const button = within(actions).getByRole("button", { name: "Sign off" });
    expect(button).toBeDisabled();
    const boxes = document.querySelectorAll<HTMLInputElement>("[data-confirmation]");
    expect(boxes).toHaveLength(5);
    boxes.forEach((box, index) => {
      if (index < 4) fireEvent.click(box);
    });
    expect(button).toBeDisabled();
    fireEvent.click(boxes[4]);
    expect(button).toBeEnabled();
    await act(async () => {
      fireEvent.click(button);
    });
    await waitFor(() => {
      const release = fake.calls.find((call) => call.path.endsWith("/release"));
      expect(release?.body).toMatchObject({
        confirmations: { compliance: true, email_mandate: true, sms_mandate: true, autopay_mandate: true, final: true },
      });
    });
  });

  // BULK-CHG-37
  it("changes row 37: every Sign off figure is the server's — who is billed, usage and base, payments, amount due", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const facts = await waitFor(() => {
      const found = document.querySelector('[data-run-facts="run-summary"]') as HTMLElement;
      expect(found).toHaveTextContent("$236,120.41");
      return found;
    });
    expect(facts).toHaveTextContent("1,840 payments"); // DEF-BIL-8682 — payments, not accounts (D1 25)
    expect(screen.queryByText("Not available yet.")).toBeNull();
    const who = document.querySelector('[data-run-table="who-accounts"]') as HTMLElement;
    expect(within(who).getByText("Regular").closest("tr")).toHaveTextContent("1,360");
    expect(within(who).getByText("Master").closest("tr")).toHaveTextContent("11");
    const units = document.querySelector('[data-run-table="who-units"]') as HTMLElement;
    expect(within(units).getByText("Through a master").closest("tr")).toHaveTextContent("80");
    const usage = document.querySelector('[data-run-table="usage"]') as HTMLElement;
    const water = usage.querySelector('[data-usage-service="water"]') as HTMLElement;
    expect(water).toHaveTextContent("$50,410.94");
    expect(water).toHaveTextContent("$17,000.00");
    expect(usage.querySelector('[data-usage-other="credits"]')).toHaveTextContent("−$1,850.00");
    const paid = document.querySelector('[data-run-table="how-paid"]') as HTMLElement;
    expect(paid.querySelector('[data-how-paid="autopay"]')).toHaveTextContent("$61,230.22");
    expect(document.querySelector("[data-no-reconcile]")).toBeNull();
  });

  // BULK-CHG-38 · BULK-CHG-37 — DEF-BIL-8242
  it("DEF-BIL-8242: Sign off names each bill the account's credit covers in full", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const row = await waitFor(() => {
      const found = document.querySelector('[data-credit-covers-row="AC-2026-12910"]') as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    expect(row).toHaveTextContent("$49.44");
    expect(row).toHaveTextContent("$500.00");
    expect(row).toHaveTextContent("$450.56");
    expect(document.querySelector("[data-credit-covers]")).toHaveAttribute("data-credit-covers", "14");
  });

  // BULK-CHG-40 · BULK-CHG-42
  it("TC-3 every See on Who is billed filters Not in this run — no side panel, the server filters", async () => {
    const fake = mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    await waitFor(() => expect(document.querySelector('[data-see="nobody"]')).not.toBeNull());
    fireEvent.click(document.querySelector('[data-see="nobody"]') as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
    const list = document.querySelector("[data-not-in-run]") as HTMLElement;
    await waitFor(() => expect(within(list).getByRole("tab", { name: "Nobody to bill 1" })).toHaveAttribute("aria-selected", "true"));
    await waitFor(() => expect(list.querySelectorAll("[data-not-in-run-row]")).toHaveLength(1));
    const row = list.querySelector("[data-not-in-run-row]") as HTMLElement;
    expect(row).toHaveAttribute("data-not-in-run-row", "nobody");
    expect(within(row).queryByRole("checkbox")).toBeNull();
    expect(within(row).getByRole("link", { name: "Add account ↗" })).toHaveAttribute("target", "_blank");
    expect(fake.calls.some((call) => call.path.endsWith("/not-in-run") && call.query?.group === "nobody")).toBe(true);
  });

  // BULK-CHG-37 · BULK-CHG-49 — fixed-charge case 2
  it("PO 2026-09-30: Sign off lists the waived bills with the served amount, and See goes back to that tag", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    expect(await screen.findByText("1 bill: base waived.")).toBeInTheDocument();
    expect(document.querySelector("[data-waived-total]")).toHaveTextContent("Total $26.00.");
    expect(document.querySelector('[data-waived-account="AC-2026-12890"]')).toHaveTextContent("$26.00");
    fireEvent.click(document.querySelector('[data-see="waived"]') as HTMLElement);
    await waitFor(() => expect(document.querySelector('[data-tag-pane="base_only_billing"]')).not.toBeNull());
  });

  it("TC-7 See breaks opens Failed to draft with Retry", async () => {
    const fake = mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    fireEvent.click(await screen.findByRole("button", { name: "See breaks" }));
    const panel = screen.getByRole("dialog", { name: "Bills" });
    fireEvent.click(within(panel).getAllByRole("button", { name: "Retry" })[0]);
    await within(panel).findByText("Drafted");
    expect(fake.calls.some((call) => call.path.endsWith("/retry"))).toBe(true);
  });

  // BULK-CHG-40
  it("TC-2 Fix in Check goes back to Check on that row's tag with its Fix-account panel", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    fireEvent.click((await screen.findAllByRole("button", { name: "Fix in Check" }))[0]);
    await screen.findByRole("dialog", { name: "Fix account" });
    await waitFor(() => expect(document.querySelector('[data-tag-pane="account_has_no_unit"]')).not.toBeNull());
  });
});

describe("T4 · Send (US-BIL-040)", () => {
  it("TC-1 Send is disabled until I checked the totals; TC-2 one press issues the run and shows Sent", async () => {
    const fake = mountRun({ phase: "authorised" }, OPEN_RUN);
    const send = await screen.findByRole("button", { name: "Send 1,371 bills" });
    expect(send).toBeDisabled();
    expect(send).toHaveAttribute("data-variant", "danger");
    fireEvent.click(document.querySelector("[data-acknowledge]") as HTMLElement);
    expect(send).toBeEnabled();
    await act(async () => {
      fireEvent.click(send);
    });
    // Send runs as the issue job now (DEF-BIL-8422) — Sent follows the job.
    await screen.findByText("1,369 bills sent", undefined, { timeout: 5000 });
    expect(fake.calls.filter((call) => call.path.endsWith("/issue"))).toHaveLength(1);
    // DEF-BIL-8421 — the two FAILED-TO-DRAFT breaks were never sent at all;
    // "not sent" is only a bill Send tried and could not issue.
    expect(screen.queryByText(/bills? not sent\./)).toBeNull();
  });

  // BULK-CHG-40 · F3 — DEF-BIL-8421
  it("F3 DEF-BIL-8421: sent and not sent apart, the failure with its reason, Retry failed sends only those", async () => {
    const fake = mountRun({ phase: "issued", sendFailure: true }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    const line = await screen.findByText("1 bill not sent.");
    fireEvent.click(within(line.parentElement as HTMLElement).getByRole("button", { name: "See breaks" }));
    const panel = await screen.findByRole("dialog", { name: "Sent" });
    const row = panel.querySelector('[data-row-account="AC-2026-00008"]') as HTMLElement;
    expect(row).toHaveTextContent("A service has no revenue account.");
    // Only the send break is listed — never the two bills that failed to draft.
    expect(panel.querySelectorAll("[data-row-account]")).toHaveLength(1);
    fireEvent.click(within(panel).getByRole("button", { name: "Retry failed" }));
    await waitFor(() => {
      const paths = fake.calls.filter((call) => call.method === "POST").map((call) => call.path);
      expect(paths.filter((path) => path.endsWith("/release"))).toHaveLength(1);
      expect(paths.filter((path) => path.endsWith("/issue"))).toHaveLength(1);
    });
    // Send with nothing named = the run's remaining drafts — the failed ones.
    const issue = fake.calls.find((call) => call.path.endsWith("/issue"));
    expect((issue?.body as { invoice_ids?: unknown }).invoice_ids).toBeUndefined();
    await waitFor(() => expect(screen.queryByText("1 bill not sent.")).toBeNull(), { timeout: 8000 });
  });

  // BULK-CHG-40 · F4 — DEF-BIL-8512
  it("F4 DEF-BIL-8512: a second clerk sees who else has the run open", async () => {
    const fake = mountRun({ otherClerk: "Dana Whitfield" }, OPEN_RUN);
    const note = await screen.findByText("Also on this run: Dana Whitfield.");
    expect(note.closest("[data-screen=bulk-bill-run]")).not.toBeNull();
    expect(fake.calls.some((call) => call.method === "POST" && call.path.endsWith("/presence"))).toBe(true);
  });

  // BULK-CHG-25 · U4 — DEF-BIL-8422 (DEF-BIL-8224's Sending half)
  it("DEF-BIL-8422: Sending shows the issue job's n of N, then Sent", async () => {
    const fake = mountRun({ phase: "authorised" }, OPEN_RUN);
    const send = await screen.findByRole("button", { name: "Send 1,371 bills" });
    fireEvent.click(document.querySelector("[data-acknowledge]") as HTMLElement);
    await act(async () => {
      fireEvent.click(send);
    });
    expect(await screen.findByText("612 of 1,371")).toBeInTheDocument();
    const post = fake.calls.find((call) => call.path.endsWith("/issue"));
    expect(post?.body).toMatchObject({ background: true });
    await screen.findByText("1,369 bills sent", undefined, { timeout: 5000 });
    // DEF-BIL-8710 — Send polls its OWN read, the one that hands a Send whose
    // worker died back to the billing worker; never the jobs kernel's.
    expect(fake.calls.some((call) => call.method === "GET" && call.path.endsWith("/issue/progress"))).toBe(true);
    expect(fake.calls.some((call) => call.path.startsWith("/jobs/"))).toBe(false);
  });

  // DEF-BIL-8747 — the Send's circuit breaker
  it("DEF-BIL-8747: a Send the server stopped says so, never the generic line", async () => {
    mountRun({ phase: "authorised", sendStopped: true }, OPEN_RUN);
    const send = await screen.findByRole("button", { name: "Send 1,371 bills" });
    fireEvent.click(document.querySelector("[data-acknowledge]") as HTMLElement);
    await act(async () => {
      fireEvent.click(send);
    });
    expect(
      await screen.findByText("Send stopped — a system fault. Unsent bills are untouched. Press Send once it is fixed.", undefined, {
        timeout: 5000,
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("That did not work. Try again.")).toBeNull();
    expect(screen.queryByText("1,369 bills sent")).toBeNull();
  });

  // BULK-CHG-40
  it("US-BIL-041 TC-3 after Send, a selection starts a catch-up run and the page says so", async () => {
    const fake = mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    const list = await waitFor(() => {
      const found = document.querySelector('[data-not-in-run="sent"]') as HTMLElement;
      expect(found.querySelectorAll('[data-not-in-run-row="blocked"]').length).toBe(2);
      return found;
    });
    fireEvent.click(within(list).getAllByRole("checkbox")[0]);
    fireEvent.click(within(list).getByRole("button", { name: "Start catch-up run for 1" }));
    await screen.findByText("Catch-up run started for 1 account.");
    const call = fake.calls.find((entry) => entry.path.endsWith("/catch-up"));
    expect(call?.body).toEqual({ account_ids: ["acc-5"] });
  });

  // BULK-CHG-40 — DEF-BIL-8223
  it("DEF-BIL-8223: after Send, a selection is left for the next cycle", async () => {
    const fake = mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    const list = await waitFor(() => {
      const found = document.querySelector('[data-not-in-run="sent"]') as HTMLElement;
      expect(found.querySelectorAll('[data-not-in-run-row="blocked"]').length).toBe(2);
      return found;
    });
    fireEvent.click(within(list).getAllByRole("checkbox")[1]);
    fireEvent.click(within(list).getByRole("button", { name: "Leave for next cycle" }));
    await waitFor(() => {
      const call = fake.calls.find((entry) => entry.path.endsWith("/not-in-run/leave-for-next-cycle"));
      expect((call?.body as { account_ids: string[] }).account_ids).toEqual(["acc-4"]);
      expect(typeof (call?.body as { at: string }).at).toBe("string");
    });
  });

  // BULK-CHG-54 — the Check report (PO 2026-09-30)
  it("a sent run carries a Check report tab: the Check as at Send, paged and filtered on the server", async () => {
    const fake = mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    fireEvent.click(screen.getByRole("tab", { name: "Check report" }));
    const report = await waitFor(() => {
      const found = document.querySelector("[data-check-report]") as HTMLElement;
      expect(found.querySelectorAll("[data-report-row]")).toHaveLength(3);
      return found;
    });
    expect(within(report).getByText("As at Send. Read only.")).toBeInTheDocument();
    expect(report.querySelector('[data-report-row="decision"]')).toHaveTextContent("No reading · No plan");
    fireEvent.click(within(report).getByRole("tab", { name: "Blocked" }));
    await waitFor(() => expect(report.querySelectorAll("[data-report-row]")).toHaveLength(1));
    expect(fake.calls.some((call) => call.path.endsWith("/check/report") && call.query?.status === "blocked")).toBe(true);
    // Read only: nothing on the report acts.
    expect(within(report).queryByRole("button", { name: /Re-check|Save|Leave out/ })).toBeNull();
  });
});

describe("T4 · the J72 accuracy walk's defects (clerk checks A1, A3, A6, U5)", () => {
  // BULK-CHG-36 · U5 — DEF-BIL-8551 / DEF-BIL-8415
  it("DEF-BIL-8551: Estimate on a No-reading row opens a box started from the usual month and records the quantity with its unit", async () => {
    const fake = mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No reading/ }));
    const pane = await waitFor(() => document.querySelector('[data-tag-pane="missing_read"]') as HTMLElement);
    await within(pane).findByRole("button", { name: "AC-2026-12881" });
    // A recorded estimate reads back as its figure.
    expect(pane).toHaveTextContent("Estimate: 7 kgal");
    const select = pane.querySelector("#decide-acc-1-water") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "estimate" } });
    const box = pane.querySelector("[data-estimate-box]") as HTMLElement;
    expect(within(box).getByLabelText("Usage")).toHaveValue("5.76");
    expect(within(box).getByLabelText("Unit")).toHaveValue("kgal");
    expect(box).toHaveTextContent("Usual month: 5.76 kgal");
    // Nothing is recorded until the clerk records it.
    expect(fake.calls.some((call) => call.path.endsWith("/check/decisions"))).toBe(false);
    fireEvent.change(within(box).getByLabelText("Usage"), { target: { value: "7" } });
    fireEvent.click(within(box).getByRole("button", { name: "Record this estimate" }));
    await waitFor(() => {
      const post = fake.calls.find((call) => call.path.endsWith("/check/decisions"));
      expect(post?.body).toEqual({
        case: "missing_read",
        choice: "estimate",
        scope: "accounts",
        account_ids: ["acc-1"],
        service_code: "water",
        amount: "7",
        unit: "kgal",
      });
    });
  });

  // BULK-CHG-36 · U5 — DEF-BIL-8551 (no history: nothing is invented)
  it("DEF-BIL-8551: with no history the box starts empty and cannot record without a quantity and a unit", async () => {
    mountRun({}, OPEN_RUN);
    fireEvent.click(await screen.findByRole("button", { name: /^No reading/ }));
    const pane = await waitFor(() => document.querySelector('[data-tag-pane="missing_read"]') as HTMLElement);
    await within(pane).findByRole("button", { name: "AC-2026-12881" });
    fireEvent.change(pane.querySelector("#decide-acc-2-water") as HTMLSelectElement, { target: { value: "estimate" } });
    const box = pane.querySelector("[data-estimate-box]") as HTMLElement;
    expect(within(box).getByLabelText("Usage")).toHaveValue("");
    expect(box.querySelector("[data-estimate-usual]")).toBeNull();
    const record = within(box).getByRole("button", { name: "Record this estimate" });
    expect(record).toBeDisabled();
    fireEvent.change(within(box).getByLabelText("Usage"), { target: { value: "6" } });
    expect(record).toBeDisabled();
    fireEvent.change(within(box).getByLabelText("Unit"), { target: { value: "kgal" } });
    expect(record).toBeEnabled();
  });

  // BULK-CHG-37 · A1 — DEF-BIL-8554
  it("DEF-BIL-8554: Price N is the accounts Calculate will price, not every Ready one", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    expect(screen.getByRole("button", { name: "Price 1,380 accounts" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Price 1,394 accounts" })).toBeNull();
  });

  // BULK-CHG-37 · A1 · A3 — DEF-BIL-8416
  it("DEF-BIL-8416: Sign off counts the waived accounts as Waived, apart from Failed to draft", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const who = await waitFor(() => {
      const found = document.querySelector('[data-run-table="who-accounts"]') as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    const row = who.querySelector('[data-who-row="waived"]') as HTMLElement;
    expect(row).toHaveTextContent("Waived");
    expect(row).toHaveTextContent("2");
    expect(who.querySelector('[data-who-row="failed"]')).toHaveTextContent("2");
  });

  // BULK-CHG-53 · A6 — DEF-BIL-8555
  it("DEF-BIL-8555: the check report lists each answer with what, who and when", async () => {
    mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    fireEvent.click(screen.getByRole("tab", { name: "Check report" }));
    const report = await waitFor(() => {
      const found = document.querySelector("[data-check-report]") as HTMLElement;
      expect(found.querySelectorAll("[data-report-row]")).toHaveLength(3);
      return found;
    });
    expect(within(report).getByRole("columnheader", { name: "Answers" })).toBeInTheDocument();
    const own = report.querySelector('[data-report-decision="account"]') as HTMLElement;
    expect(own).toHaveTextContent("Estimate 7 kgal · Priya Menon");
    const all = report.querySelector('[data-report-decision="all"]') as HTMLElement;
    expect(all).toHaveTextContent("Alex Reed");
    expect(all).toHaveTextContent(/\(all /);
  });
});

// DEF-BIL-8809 — the cold open's waterfall. The page used to ask for every
// screen read only once `GET /billing/runs/{id}` had answered (its phase picks
// the step), so a 40,000-bill run's reads queued behind it on three workers.
describe("DEF-BIL-8809 · the reads a re-opened run needs start beside the run read", () => {
  const RUN_PATH = `/billing/runs/${RUN_ID}`;
  const asked = (fake: ReturnType<typeof mountRun>, suffix: string) =>
    fake.calls.filter((call) => call.method === "GET" && call.path === `${RUN_PATH}${suffix}`).length;

  it("reads start before the run read resolves: findings, summary, breaks and Not in this run's first page", async () => {
    const fake = mountRun({ phase: "issued", holdRunRead: true }, OPEN_RUN);
    await waitFor(() => expect(asked(fake, "")).toBe(1));
    await waitFor(() => {
      expect(asked(fake, "/check/findings")).toBe(1);
      expect(asked(fake, "/totals")).toBe(1);
      expect(asked(fake, "/breaks")).toBe(1);
      expect(asked(fake, "/not-in-run")).toBe(1);
    });
    // The Sent card's meter reads row is asked only once the run says sent.
    expect(asked(fake, "/read-lock")).toBe(0);
    // Not in this run's first page is asked in the form the sent list reads,
    // so the list mounting later finds it answered rather than asking again.
    const notIn = fake.calls.find((call) => call.path === `${RUN_PATH}/not-in-run`);
    expect(notIn?.query).toMatchObject({ page: 1, per: 50 });
    expect(notIn?.query?.group).toBeUndefined();
    expect(typeof notIn?.query?.as_of).toBe("string");
    // Nothing that only one phase shows is asked before the phase is known.
    expect(asked(fake, "/sign-off-summary")).toBe(0);
    expect(asked(fake, "/check")).toBe(0);
    // The scope step's services filter is not on a re-opened run's screen.
    expect(fake.calls.some((call) => call.path === "/settings/services")).toBe(false);
    act(() => fake.releaseRunRead());
    await screen.findByText("1,369 bills sent");
    await waitFor(() =>
      expect(document.querySelectorAll('[data-not-in-run="sent"] [data-not-in-run-row]').length).toBeGreaterThan(0),
    );
    // Each read once: the list and the Sent card found theirs answered.
    expect(asked(fake, "/not-in-run")).toBe(1);
    expect(asked(fake, "/totals")).toBe(1);
    expect(asked(fake, "/breaks")).toBe(1);
  });

  // DEF-BIL-8809 (server half) — the page draws two figures of the summary
  // panel, so it asks the headline alone; and the Sent card's meter reads row
  // left the run read (every screen waits for that one) for its own read.
  it("the Sent card's total comes from /totals and its meter reads row from /read-lock; /summary is never asked", async () => {
    const fake = mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    const card = document.querySelector("[data-sent-card]") as HTMLElement;
    await waitFor(() => expect(card).toHaveTextContent("$214,386.52"));
    const reads = await waitFor(() => {
      const found = card.querySelector('[data-sent-row="meter-reads"] dd') as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    expect(reads).toHaveAttribute("data-meter-reads", "locked");
    expect(asked(fake, "/totals")).toBe(1);
    expect(asked(fake, "/read-lock")).toBe(1);
    expect(asked(fake, "/summary")).toBe(0);
  });

  it("a sent run never asks Sign off's figures or the Check job's state — Send shows neither", async () => {
    const fake = mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    await waitFor(() => expect(asked(fake, "/not-in-run")).toBeGreaterThan(0));
    expect(asked(fake, "/sign-off-summary")).toBe(0);
    expect(asked(fake, "/check")).toBe(0);
  });

  it("a calculated run asks Sign off's figures once its phase is known", async () => {
    const fake = mountRun({ phase: "calculated" }, OPEN_RUN);
    await waitFor(() => expect(asked(fake, "/sign-off-summary")).toBe(1));
  });

  it("a run at Check still asks the Check job's state, and Scope's services filter is asked only on Scope", async () => {
    const fake = mountRun({}, OPEN_RUN);
    await waitFor(() => expect(asked(fake, "/check")).toBeGreaterThan(0));
    expect(asked(fake, "/sign-off-summary")).toBe(0);
    expect(fake.calls.some((call) => call.path === "/settings/services")).toBe(false);
  });
});
