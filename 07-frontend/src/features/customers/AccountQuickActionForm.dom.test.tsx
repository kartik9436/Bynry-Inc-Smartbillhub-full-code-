// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-003 (POST /accounts/{id}/activate — BR-CUS-018's resume half)
// Change:   CR-094-BRC01 step 2 wave J — `ACC-S14`: *"A clerk on the phone
//           presses any of the thirteen, fills the form without losing sight of
//           the balance behind it, reads back a recap, and commits — or reads
//           why it cannot be committed, on the button itself."*
// Rules:    BR-SHL-025 · B14 rule 11 · rule 33 · rule 38 · rule 39
// ───────────────────────────────────────────────────────
//
// ⚠ **jsdom COMPUTES NO LAYOUT, SO THIS FILE ASSERTS NO PIXEL.** B14 rule 39's
// 5 / 6 / 20 figures have no gate anywhere in this repo and this one does not
// pretend otherwise — what is asserted here is ORDER, PRESENCE and BEHAVIOUR.
// A test named after an assertion it does not make is hard-won law 7's *looking
// at the wrong thing*, and saying so is cheaper than being caught by it.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountQuickActionForm } from "./AccountQuickActionForm";
import { quickFormFor } from "./accountQuickActions";

afterEach(cleanup);

const FORM = quickFormFor("activate")!;

function renderForm(over: Partial<Parameters<typeof AccountQuickActionForm>[0]> = {}) {
  // Typed with its real signature so `mock.calls[0][0]` is the values object
  // rather than a tuple TypeScript believes is empty.
  const onSubmit = vi.fn<(values: Record<string, string>) => Promise<{ readonly ok: true }>>(
    async () => ({ ok: true }) as const,
  );
  const { container } = render(
    <AccountQuickActionForm
      form={FORM}
      kicker="Kwan, Michael · A-12048"
      facts={{
        statusName: "Pending activation",
        openedAt: null,
        unitPlan: "Sample — Residential · v1",
        outcomeSentence: "The account becomes active.",
      }}
      dateFormat="MM/DD/YYYY"
      today="2026-09-11"
      absentText="Not recorded"
      onSubmit={onSubmit}
      onClose={() => undefined}
      {...over}
    />,
  );
  return { onSubmit, container };
}

describe("the quick-action form, over the account", () => {
  it("names the action and the account it is open over", () => {
    renderForm();
    expect(screen.getByText("Activate this account")).toBeInTheDocument();
    // The kicker is what stops a clerk committing on the row they did not mean.
    expect(screen.getByText("Kwan, Michael · A-12048")).toBeInTheDocument();
  });

  it("says the commit is irreversible BEFORE the click", () => {
    // R4's caption for `ACC-Q03`: *"the confirmation the product is missing, and
    // it names the partial failure before the click"*.
    renderForm();
    expect(screen.getByText("This starts billing. It cannot be undone.")).toBeInTheDocument();
  });

  it("asks for the activation date, prefilled with today", () => {
    renderForm();
    const input = screen.getByLabelText(/Activation date/);
    expect(input).toHaveValue("2026-09-11");
  });

  it("shows the plan as a FACT, with no control to change it", () => {
    // BR-CUS-029 — a plan belongs to the unit and the account inherits it, so
    // there is nothing to pick and no picker is drawn.
    const { container } = renderForm();
    // It appears TWICE on purpose — once as the fact, once in the recap — so
    // each place is asserted by its own hook rather than by a loose text match
    // that cannot tell the two apart.
    expect(container.querySelector('[data-quick-readonly="unit_plan"]')).toHaveTextContent(
      "Sample — Residential · v1",
    );
    expect(container.querySelector('[data-recap-row="unitPlan"] dd')).toHaveTextContent(
      "Sample — Residential · v1",
    );
    expect(screen.getByText("A plan belongs to the unit.")).toBeInTheDocument();
    // No CONTROL for it: a plan belongs to the unit, so there is nothing to pick.
    expect(screen.queryByLabelText(/Unit plan/)).not.toBeInTheDocument();
  });

  it("reads back a recap, and the recap MOVES when the date does", () => {
    // ⚠ THE CASE THAT MATTERS. A recap built only from server facts cannot move,
    // and a recap that cannot move is decoration rather than a read-back.
    const { container } = renderForm();
    const row = () => container.querySelector('[data-recap-row="openedAt"] dd');
    expect(row()).toHaveTextContent("09/11/2026");

    // ⚠ `fireEvent.change` AND NOT `userEvent.type`. A `<input type="date">`
    // takes a whole `YYYY-MM-DD`; typing it character by character leaves the
    // control holding "" for every intermediate keystroke and the assertion
    // then fails over a TEST artefact rather than a product one. Proved by
    // probe before this line was written.
    fireEvent.change(screen.getByLabelText(/Activation date/), {
      target: { value: "2026-10-01" },
    });

    expect(row()).toHaveTextContent("10/01/2026");
    expect(row()).not.toHaveTextContent("09/11/2026");
  });

  it("reads back the status it is leaving and what it becomes", () => {
    renderForm();
    expect(screen.getByText("Pending activation")).toBeInTheDocument();
    expect(screen.getByText("The account becomes active.")).toBeInTheDocument();
  });

  it("names the three things the server will NOT do", () => {
    // R4's own box, plus the opening read the endpoint cannot accept. This is
    // the honest half of a form whose endpoint does less than the drawing
    // implies: it says so BEFORE the click rather than after.
    renderForm();
    expect(screen.getByText("No opening read is taken.")).toBeInTheDocument();
    expect(screen.getByText("No deposit is charged.")).toBeInTheDocument();
    expect(screen.getByText("No plan snapshot is recorded.")).toBeInTheDocument();
  });

  it("prints the absence sentence rather than a blank when a fact is missing", () => {
    // A blank where a plan should be reads as *"no plan"*, which on this form is
    // the difference between an account that inherits a tariff and one that will
    // not bill at all.
    const { container } = renderForm({
      facts: {
        statusName: "Pending activation",
        openedAt: null,
        unitPlan: null,
        outcomeSentence: "The account becomes active.",
      },
    });
    // Both the fact and its recap row say it, which is the point: neither place
    // is allowed to go blank.
    expect(container.querySelector('[data-quick-readonly="unit_plan"]')).toHaveTextContent(
      "Not recorded",
    );
    expect(container.querySelector('[data-recap-row="unitPlan"] dd')).toHaveTextContent(
      "Not recorded",
    );
  });

  it("sends the values under the server's own field names", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();
    await user.click(screen.getByRole("button", { name: "Activate account" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    // `opened_at` is what `services.activate_account` accepts; a form key that
    // differed from the wire key would be a mapping table nobody maintains.
    expect(onSubmit.mock.calls[0][0]).toEqual({ opened_at: "2026-09-11" });
  });

  it("lays its fields in ONE column, which is B14 rule 38 against the drawing", () => {
    // R4 draws every section as a two-column grid. Rule 38 names side-by-side
    // fields VERBATIM as form CONSTRUCTION, where the UI rules win and *"nothing
    // is built for it"* — so the kit's `FieldStack` is what renders here.
    const { container } = render(
      <AccountQuickActionForm
        form={FORM}
        kicker="k"
        facts={{ statusName: "s", openedAt: null, unitPlan: "p", outcomeSentence: "o" }}
        dateFormat="MM/DD/YYYY"
        today="2026-09-11"
        absentText="Not recorded"
        onSubmit={async () => ({ ok: true }) as const}
        onClose={() => undefined}
      />,
    );
    expect(container.querySelectorAll("[data-field-stack]").length).toBeGreaterThan(0);
    expect(container.querySelector(".grid-cols-2")).toBeNull();
  });
});

describe("a form whose endpoint does not exist (BR-SHL-025)", () => {
  // ⚠ **THIS SAMPLE WAS `adjustBlocked` UNTIL 2026-09-13 AND THAT KEY NO LONGER
  // EXISTS (`DEF-CUS-5126`).** `Adjust` is live — `POST /accounts/{id}/payments`
  // with `type: "adjustment"` has existed since `CR-059` CS-35 — so its refusal
  // is deleted from all eleven catalogues. This suite tests the MECHANISM and
  // only needs A blocked key, so it now borrows the one refusal on the account
  // that was always true: nothing in this product renders a statement.
  const BLOCKED = {
    ...FORM,
    commitBlockedKey: "customers.account.action.sendStatementBlocked",
  };

  it("keeps its whole form and refuses only the COMMIT", () => {
    // R4: *"A control the deployment cannot honour keeps its form and disables
    // its commit with the reason on it"* — the form is the specification of the
    // endpoint that does not exist yet, and a clerk reading it learns what will
    // be asked.
    renderForm({ form: BLOCKED });
    expect(screen.getByLabelText(/Activation date/)).toBeEnabled();
    expect(screen.getByRole("button", { name: "Activate account" })).toBeDisabled();
  });

  it("puts the reason on screen as TEXT, never in a title tooltip", () => {
    // A `title` is unreachable by keyboard, invisible on touch and unread by the
    // clerk who is on the phone — the exact reader B14 rule 33 writes its caps
    // for. `ACC-S14`: *"reads why it cannot be committed, on the button itself."*
    const { container } = render(
      <AccountQuickActionForm
        form={BLOCKED}
        kicker="k"
        facts={{ statusName: "s", openedAt: null, unitPlan: "p", outcomeSentence: "o" }}
        dateFormat="MM/DD/YYYY"
        today="2026-09-11"
        absentText="Not recorded"
        onSubmit={async () => ({ ok: true }) as const}
        onClose={() => undefined}
      />,
    );
    const refusal = container.querySelector("[data-commit-blocked]");
    expect(refusal).not.toBeNull();
    expect(refusal?.textContent?.length ?? 0).toBeGreaterThan(0);
    expect(refusal).toHaveAttribute("role", "alert");
  });

  it("cannot be submitted", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm({ form: BLOCKED });
    await user.click(screen.getByRole("button", { name: "Activate account" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
