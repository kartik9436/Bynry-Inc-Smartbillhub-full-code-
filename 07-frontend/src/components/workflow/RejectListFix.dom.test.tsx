// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-028 debt sweep D8 (2026-08-22) — stage 3's inline "fix here"
//           editor. The backend PATCH /imports/{id}/rows/{row_no} landed with
//           AST-W3; the rejects table offered re-run-rejects and nothing else,
//           so r10's own caption — *"Fix the rejects here — no need to
//           re-upload"* — was a sentence over a read-only table.
// Rules:    CR-016 (the sentences are plain English; the editor labels are the
//           operator's OWN file headers) · fix_row's law (the run drops to
//           stage 1 and stages 2–3 re-run — said on screen before the click)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RejectList } from "./RejectList";
import type { RejectedRow } from "./contract";

const ROW: RejectedRow = {
  row_number: 88,
  key: "P-11902",
  problem: "Parent premise P-11902 was not loaded.",
  suggested_fix: "Load the premise first",
  raw: { METER_NO: "M-88", UNIT_REF: "P-11902", COST: "164.00" },
};

afterEach(cleanup);

/** `BR-MET-1032` — the same row, with the identity cell the server holds
 *  encrypted. The server sends the MASK and names it in `masked`; the whole
 *  number is not in this payload and cannot be. */
const MASKED_ROW: RejectedRow = {
  row_number: 91,
  key: "P-11903",
  problem: "P-11903 is not a premise ID this utility has issued.",
  suggested_fix: "Clear this cell",
  raw: { OWNER: "Rosa Alvarez", SSN: "\u2022\u2022\u2022\u20226789" },
  masked: ["SSN"],
};

describe("BR-MET-1032 — a masked identity cell in the inline editor", () => {
  it("shows the last four on the row and opens the input EMPTY, not pre-filled", async () => {
    const user = userEvent.setup();
    render(
      <RejectList
        caption="Fix the rejects here — no need to re-upload"
        rejects={[MASKED_ROW]}
        emptyMessage="Nothing was rejected."
        onFix={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fix here…" }));
    const ssn = screen.getByLabelText("SSN");
    // ⚠ **EMPTY, WITH THE MASK AS A PLACEHOLDER.** An input holding
    // `••••6789` that somebody appends a digit to sends `••••67891`, and the
    // server strips the bullets — so `67891` would be filed as a real Social
    // Security number, matched against nobody, and a second customer minted.
    expect(ssn).toHaveValue("");
    expect(ssn).toHaveAttribute("placeholder", "\u2022\u2022\u2022\u20226789");
    // The unmasked cell beside it is untouched: this changes one kind of cell.
    expect(screen.getByLabelText("OWNER")).toHaveValue("Rosa Alvarez");
  });

  it("leaving it empty sends NOTHING — an untouched mask is not a clear", async () => {
    const user = userEvent.setup();
    const onFix = vi.fn();
    render(
      <RejectList
        caption="Fix the rejects here — no need to re-upload"
        rejects={[MASKED_ROW]}
        emptyMessage="Nothing was rejected."
        onFix={onFix}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fix here…" }));
    await user.type(screen.getByLabelText("OWNER"), "!");
    await user.click(screen.getByRole("button", { name: "Save & re-check" }));
    // The SSN is absent from the patch entirely. Reading its empty box as a
    // clear would wipe the identifier off every row an operator merely opened
    // — and that value is what the matcher joins on.
    expect(onFix).toHaveBeenCalledWith(91, { OWNER: "Rosa Alvarez!" });
  });

  it("typing a whole number sends that number and nothing masked", async () => {
    const user = userEvent.setup();
    const onFix = vi.fn();
    render(
      <RejectList
        caption="Fix the rejects here — no need to re-upload"
        rejects={[MASKED_ROW]}
        emptyMessage="Nothing was rejected."
        onFix={onFix}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fix here…" }));
    await user.type(screen.getByLabelText("SSN"), "987-65-4321");
    await user.click(screen.getByRole("button", { name: "Save & re-check" }));
    expect(onFix).toHaveBeenCalledWith(91, { SSN: "987-65-4321" });
  });
});

describe("D8 — the stage-3 inline fix editor", () => {
  it("opens the row's OWN cells and saves ONLY the changed ones", async () => {
    const user = userEvent.setup();
    const onFix = vi.fn();
    render(
      <RejectList
        caption="Fix the rejects here — no need to re-upload"
        rejects={[ROW]}
        emptyMessage="Nothing was rejected."
        onFix={onFix}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fix here…" }));
    // The operator's own file headers label the inputs.
    const unitRef = screen.getByLabelText("UNIT_REF");
    expect(unitRef).toHaveValue("P-11902");
    // The law is said BEFORE the click: saving re-runs stages 2–3.
    expect(screen.getByText(/re-runs the mapping and the checks/)).toBeInTheDocument();
    // "Load into inventory instead" is one cleared cell (BR-AST-045).
    await user.clear(unitRef);
    const save = screen.getByRole("button", { name: "Save & re-check" });
    expect(save).toBeEnabled();
    await user.click(save);
    // ONLY the changed cell travels — a full-row echo would stamp every
    // column as "fixed" in the audit trail.
    expect(onFix).toHaveBeenCalledWith(88, { UNIT_REF: null });
  });

  it("save holds until something actually changed", async () => {
    const user = userEvent.setup();
    render(
      <RejectList
        caption="Rejects"
        rejects={[ROW]}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fix here…" }));
    expect(screen.getByRole("button", { name: "Save & re-check" })).toBeDisabled();
  });

  it("without onFix (or without served raw cells) the table is its pre-D8 read-only self", () => {
    render(
      <RejectList caption="Rejects" rejects={[ROW]} emptyMessage="Nothing was rejected." />,
    );
    expect(screen.queryByRole("button", { name: "Fix here…" })).not.toBeInTheDocument();
    cleanup();
    // An older server sends no raw block — the control degrades away.
    render(
      <RejectList
        caption="Rejects"
        rejects={[{ ...ROW, raw: undefined }]}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    expect(screen.queryByRole("button", { name: "Fix here…" })).not.toBeInTheDocument();
  });
});

// ── CR-036 amendment 1 (b) ────────────────────────────────────────────────
// The PO, on a live deployment, on a units file that rejected 9,881 of 9,881
// rows: *"am not able to press the fix button"*. The handler was never wrong.
// The LIST was 9,881 rows and 9,881 buttons in one auto-layout table, and one
// `setEditing` re-rendered all of it.
function manyRejects(count: number): RejectedRow[] {
  return Array.from({ length: count }, (_unused, index) => ({
    row_number: index + 1,
    key: `P-${11_000 + index}`,
    problem: "1/1/2026 is not a date this import can read.",
    suggested_fix: "Use YYYY-MM-DD — 2026-04-01.",
    raw: { PREMISE_NO: `P-${11_000 + index}`, MOVE_IN: "1/1/2026" },
  }));
}

describe("CR-036 (b) — a four-figure reject list is a PAGE, not a page-load", () => {
  it("9,881 rejects draw ONE page of rows, and the footer says which", () => {
    const { container } = render(
      <RejectList
        caption="Fix the rejects here — no need to re-upload"
        rejects={manyRejects(9_881)}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    // ⚠ THE NUMBER IS THE POINT. Before this, every one of the 9,881 was in
    // the DOM with its own button — 69,241 nodes, measured — and opening the
    // editor re-rendered all of them: 1,114 ms in jsdom, which does no layout,
    // no style recalc and no paint. See RejectList's docstring for the run.
    expect(container.querySelectorAll("[data-workflow-reject]")).toHaveLength(50);
    expect(container.querySelectorAll("[data-workflow-reject] button")).toHaveLength(50);
    // B14 rule 16's footer, in the shared words — the operator can still see
    // that nine thousand rows were rejected, which is the fact that matters.
    expect(screen.getByText("1–50 of 9881")).toBeInTheDocument();
  });

  it("and the fix editor opens on that page — the control the PO could not press", async () => {
    const user = userEvent.setup();
    const onFix = vi.fn();
    const { container } = render(
      <RejectList
        caption="Rejects"
        rejects={manyRejects(9_881)}
        emptyMessage="Nothing was rejected."
        onFix={onFix}
      />,
    );
    const first = container.querySelectorAll<HTMLButtonElement>(
      "[data-workflow-reject] button",
    )[0];
    await user.click(first);
    // RENDERED OUTPUT: the row's own cells, under the operator's file headers.
    expect(container.querySelector("[data-workflow-fix-editor]")).not.toBeNull();
    expect(screen.getByLabelText("MOVE_IN")).toHaveValue("1/1/2026");
  });

  it("the pager reaches the rejects that are NOT on page one", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <RejectList
        caption="Rejects"
        rejects={manyRejects(9_881)}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("51–100 of 9881")).toBeInTheDocument();
    const rows = container.querySelectorAll("[data-workflow-reject]");
    expect(rows[0].getAttribute("data-workflow-reject")).toBe("51");
  });

  it("an empty list draws its sentence and NO footer arguing with it", () => {
    const { container } = render(
      <RejectList caption="Rejects" rejects={[]} emptyMessage="Nothing was rejected." />,
    );
    expect(screen.getByText("Nothing was rejected.")).toBeInTheDocument();
    expect(container.querySelector(".table-pager")).toBeNull();
  });

  it("A SECOND CLICK ON THE SAME CONTROL KEEPS THE EDITOR OPEN", async () => {
    // ⚠ THE MEASURED SYMPTOM, and the half pagination does not cure. At 9,881
    // rows the click that opens the editor took 1,114 ms to re-render in jsdom
    // — no layout, no paint — so the operator clicked again, and the old
    // toggle read that second click as "close". The editor opened and shut,
    // which is what *"am not able to press the fix button"* looks like from
    // the operator's chair. Slowness is a property of the FILE and can come
    // back; a control that closes what it opened must not.
    const user = userEvent.setup();
    render(
      <RejectList
        caption="Rejects"
        rejects={[ROW]}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    const open = screen.getByRole("button", { name: "Fix here…" });
    expect(open).toHaveAttribute("aria-expanded", "false");
    await user.click(open);
    expect(screen.getByLabelText("UNIT_REF")).toBeInTheDocument();
    expect(open).toHaveAttribute("aria-expanded", "true");
    // ⚠ THE SECOND CLICK — the one the old toggle read as "close". Asserted
    // after EACH further click, because an even number of toggles lands back
    // on "open" and would let this test pass over the defect.
    await user.click(open);
    expect(screen.getByLabelText("UNIT_REF")).toBeInTheDocument();
    await user.click(open);
    // RENDERED OUTPUT: the editor's own input, still on screen after three
    // clicks of the control that opened it.
    expect(screen.getByLabelText("UNIT_REF")).toBeInTheDocument();
    expect(open).toHaveAttribute("aria-expanded", "true");
  });

  it("and CANCEL is what closes it — the control that says so", async () => {
    const user = userEvent.setup();
    render(
      <RejectList
        caption="Rejects"
        rejects={[ROW]}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fix here…" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("UNIT_REF")).not.toBeInTheDocument();
  });

  it("another row's control MOVES the editor rather than opening a second", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <RejectList
        caption="Rejects"
        rejects={manyRejects(4)}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    const buttons = container.querySelectorAll<HTMLButtonElement>(
      "[data-workflow-reject] button",
    );
    await user.click(buttons[0]);
    expect(container.querySelector("[data-workflow-fix-editor]")?.getAttribute(
      "data-workflow-fix-editor",
    )).toBe("1");
    await user.click(buttons[2]);
    expect(container.querySelectorAll("[data-workflow-fix-editor]")).toHaveLength(1);
    expect(container.querySelector("[data-workflow-fix-editor]")?.getAttribute(
      "data-workflow-fix-editor",
    )).toBe("3");
  });

  it("A REFRESH UNDERNEATH THE OPERATOR DOES NOT CLOSE THE EDITOR", async () => {
    // A background run's rejects arrive from a 2-second poll, so the array can
    // be replaced while the operator is typing in it. `editing` is keyed by the
    // operator's ROW NUMBER, which survives that; array identity does not.
    const user = userEvent.setup();
    const first = manyRejects(120);
    const { container, rerender } = render(
      <RejectList
        caption="Rejects"
        rejects={first}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    await user.click(
      container.querySelectorAll<HTMLButtonElement>("[data-workflow-reject] button")[0],
    );
    const input = screen.getByLabelText("MOVE_IN");
    fireEvent.change(input, { target: { value: "2026-01-01" } });
    // The poll answers again: a brand-new array, same rows, new objects.
    rerender(
      <RejectList
        caption="Rejects"
        rejects={manyRejects(120)}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
      />,
    );
    expect(container.querySelector("[data-workflow-fix-editor]")).not.toBeNull();
    // …and what the operator had typed is still there.
    expect(screen.getByLabelText("MOVE_IN")).toHaveValue("2026-01-01");
  });
});

describe("DEF-766 — the page is the SERVER's, and the total is still the truth", () => {
  // ⚠ **WHY THIS BLOCK EXISTS AND THE ONE ABOVE IS NOT ENOUGH.** The tests
  // above hand this table 9,881 rows and check it draws 50 — which is exactly
  // the state the defect lived in: the server BUILT all 9,881, serialised them
  // with their `raw` cells and sent them every two seconds, and the table threw
  // 9,831 of them away. A component test that receives the whole list cannot
  // see that, so `serverPage` is the prop that makes the window visible here.
  const PAGE_ONE = manyRejects(50);

  it("fifty rows and a footer that counts NINE THOUSAND", () => {
    const { container } = render(
      <RejectList
        caption="Fix the rejects here — no need to re-upload"
        rejects={PAGE_ONE}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
        serverPage={{
          total: 9_881,
          page: 1,
          per: 50,
          onPage: () => undefined,
          onPer: () => undefined,
        }}
      />,
    );
    expect(container.querySelectorAll("[data-workflow-reject]")).toHaveLength(50);
    // The figure the bound must not cost the operator. Counting the ARRAY here
    // would print "1–50 of 50" over a run that rejected 9,881 rows.
    expect(screen.getByText("1–50 of 9881")).toBeInTheDocument();
  });

  it("turning a page ASKS THE SERVER instead of slicing an array it does not have", async () => {
    const user = userEvent.setup();
    const onPage = vi.fn();
    render(
      <RejectList
        caption="Rejects"
        rejects={PAGE_ONE}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
        serverPage={{
          total: 9_881,
          page: 1,
          per: 50,
          onPage,
          onPer: () => undefined,
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPage).toHaveBeenCalledWith(2);
  });

  it("draws the page it was GIVEN — row 9,851 on the last page, not row 1", () => {
    const lastPage = manyRejects(9_881).slice(9_850);
    const { container } = render(
      <RejectList
        caption="Rejects"
        rejects={lastPage}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
        serverPage={{
          total: 9_881,
          page: 198,
          per: 50,
          onPage: () => undefined,
          onPer: () => undefined,
        }}
      />,
    );
    // Windowed, the server sliced: the component must NOT slice again, or page
    // 198 would draw page 198 OF page 198 — which is nothing at all.
    expect(container.querySelectorAll("[data-workflow-reject]")).toHaveLength(31);
    expect(container.querySelectorAll("[data-workflow-reject]")[0].getAttribute(
      "data-workflow-reject",
    )).toBe("9851");
    expect(screen.getByText("9851–9881 of 9881")).toBeInTheDocument();
  });

  it("the Fix here editor still opens on a SERVED row (the path the window must not break)", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <RejectList
        caption="Rejects"
        rejects={PAGE_ONE}
        emptyMessage="Nothing was rejected."
        onFix={() => undefined}
        serverPage={{
          total: 9_881,
          page: 1,
          per: 50,
          onPage: () => undefined,
          onPer: () => undefined,
        }}
      />,
    );
    await user.click(
      container.querySelectorAll<HTMLButtonElement>("[data-workflow-reject] button")[0],
    );
    // The window carries `raw`, so the editor has cells to edit. A window that
    // stripped them would leave the control opening on nothing.
    expect(screen.getByLabelText("MOVE_IN")).toHaveValue("1/1/2026");
  });

  it("a windowed run that rejected NOTHING says so and draws no footer", () => {
    const { container } = render(
      <RejectList
        caption="Rejects"
        rejects={[]}
        emptyMessage="Nothing was rejected."
        serverPage={{
          total: 0,
          page: 1,
          per: 50,
          onPage: () => undefined,
          onPer: () => undefined,
        }}
      />,
    );
    expect(screen.getByText("Nothing was rejected.")).toBeInTheDocument();
    expect(container.querySelector(".table-pager")).toBeNull();
  });
});
