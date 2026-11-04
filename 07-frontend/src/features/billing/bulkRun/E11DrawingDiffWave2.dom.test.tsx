// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bulk bill run, every step
// Journey:  J72 § E11 — the screens put beside the D1 drawings, 2026-10-01 (wave 2)
// Defects:  DEF-BIL-8675 … 8691, as each `describe` names
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/ (the image each case names)
// Ruling:   coordinator 2026-10-01 under B14 rule 41 — for the bulk run the
//           blueprint owns layout, copy, flows and states; our kit owns how it
//           is built. Money is shown, never recomputed.
// ───────────────────────────────────────────────────────
/**
 * THE SECOND WAVE OF E11: EVERY DIFFERENCE THE SIDE-BY-SIDE FOUND THAT THE
 * FIRST WAVE LEFT OPEN. Each case was written to fail on the build that had the
 * difference (2.417.1) and names the drawing it is held to.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CYCLE_ID, RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";

afterEach(cleanup);

const OPEN_RUN = `?run=${RUN_ID}`;

function actionRow(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-wizard="actions"]');
}

describe("DEF-BIL-8678 · no footer under a progress panel or a stop (D1 09, 10, 24, 34)", () => {
  it("while the Check runs there is no 'Price 0 accounts'", async () => {
    mountRun({ checking: true }, OPEN_RUN);
    await screen.findByText("Checking accounts");
    expect(actionRow()).toBeNull();
    expect(screen.queryByRole("button", { name: /^Price/ })).toBeNull();
  });

  it("under 'Meter Reads is not answering' there is no Price button at all", async () => {
    mountRun({ moduleDown: true }, OPEN_RUN);
    await screen.findByRole("alert");
    expect(actionRow()).toBeNull();
    expect(screen.queryByRole("button", { name: /^Price/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("the results bring the footer back, with its Price", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    expect(actionRow()).not.toBeNull();
    expect(screen.getByRole("button", { name: /^Price/ })).toBeInTheDocument();
  });

  it("while Calculating there is no footer", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^Price/ }));
    });
    await screen.findByText("754 of 1,371");
    expect(actionRow()).toBeNull();
  });

  it("while Sending there is no footer", async () => {
    mountRun({ phase: "authorised" }, OPEN_RUN);
    const send = await screen.findByRole("button", { name: "Send 1,371 bills" });
    fireEvent.click(document.querySelector("[data-acknowledge]") as HTMLElement);
    await act(async () => {
      fireEvent.click(send);
    });
    await screen.findByText("612 of 1,371");
    expect(actionRow()).toBeNull();
    await waitFor(() => expect(screen.queryByText("612 of 1,371")).toBeNull(), { timeout: 5000 });
  });
});

describe("DEF-BIL-8680 · the run's name on every step after Scope (D1 25–36)", () => {
  it("a run opened from its address shows the name the clerk typed, never '—'", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const row = document.querySelector('[data-aside-row="label"]') as HTMLElement;
    expect(row).toHaveTextContent("September 2026 · Riverside");
  });
});

describe("DEF-BIL-8685 · Send says who signed off and when (D1 32)", () => {
  it("'Signed off by Dana Whitfield · <date> <time>' on a re-opened, signed-off run", async () => {
    mountRun({ phase: "authorised" }, OPEN_RUN);
    await screen.findByRole("button", { name: "Send 1,371 bills" });
    const card = document.querySelector("[data-send-card]") as HTMLElement;
    expect(card).toHaveTextContent(/Signed off by Dana Whitfield · 10\/01\/2026,? \d{1,2}:\d{2}/);
  });
});

describe("DEF-BIL-8683 · a customer type is a word, never its code (D1 25)", () => {
  it("By customer type reads 'Institutional', not 'institutional'", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const table = await waitFor(() => {
      const found = document.querySelector('[data-run-table="by-type"]') as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    expect(table).toHaveTextContent("Institutional");
    expect(table).toHaveTextContent("Residential");
    expect(table.textContent).not.toMatch(/\binstitutional\b|\bresidential\b/);
  });
});

async function openTagPane(name: string, code: string): Promise<HTMLElement> {
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(`^${name}`) }));
  return waitFor(() => {
    const found = document.querySelector<HTMLElement>(`[data-tag-pane="${code}"]`);
    expect(found).not.toBeNull();
    return found as HTMLElement;
  });
}

describe("DEF-BIL-8675 · Check names each problem in the drawing's words (D1 11–23)", () => {
  it("the list, the pane and the chips say 'No reading', 'Disputed reading', 'No plan', 'Standing charges only'", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const list = document.querySelector("[data-problem-list]") as HTMLElement;
    for (const name of ["No reading", "No plan", "Standing charges only", "Meter swapped", "No unit", "No size"]) {
      expect(list, name).toHaveTextContent(name);
    }
    expect(list.textContent).not.toMatch(/No reading for one service|The unit has no plan|standing-charges-only accounts\?/);
    const pane = await openTagPane("No reading", "missing_read");
    expect(pane.querySelector("h3")).toHaveTextContent(/^No reading/);
  });
});

describe("DEF-BIL-8676 · the decision pane as drawn (D1 11, 12, 16)", () => {
  it("the head line carries the meaning; the bar offers short answers and says they are pre-selected; no Re-check", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const pane = await openTagPane("No reading", "missing_read");
    expect(pane).toHaveTextContent("3 accounts · No reading this period. Fixed in Meter Reads.");
    const bar = pane.querySelector('[data-tag-actions="decision"]') as HTMLElement;
    expect(bar).toHaveTextContent("Pre-selected from Billing settings.");
    const answers = Array.from(bar.querySelectorAll('[role="radio"], [aria-pressed]')).map((el) => el.textContent?.trim());
    expect(answers).toEqual(expect.arrayContaining(["Estimate", "Hold"]));
    expect(bar.querySelector("[data-recheck]")).toBeNull();
  });
});

describe("DEF-BIL-8677 · a row fixed inline stays, green, 'Fixed · re-checked' (D1 13, 23)", () => {
  it("after Save the row is still on the page and says it was fixed and re-checked", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const pane = await openTagPane("No plan", "unit_has_no_plan");
    const control = await waitFor(() => {
      const found = pane.querySelector<HTMLElement>('[data-fix-here="set_plan"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    const select = control.querySelector("select") as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBeGreaterThan(1));
    const row = control.closest("[data-row-account]") as HTMLElement;
    const accountNo = row.dataset.rowAccount as string;
    fireEvent.change(select, { target: { value: "plan-1" } });
    await act(async () => {
      fireEvent.click(control.querySelector("[data-fix-save]") as HTMLElement);
    });
    await waitFor(() => {
      const fixed = document.querySelector<HTMLElement>(`[data-tag-pane="unit_has_no_plan"] [data-row-account="${accountNo}"]`);
      expect(fixed).not.toBeNull();
      expect(fixed).toHaveAttribute("data-row-fixed");
      expect(fixed).toHaveTextContent("Fixed · re-checked");
    });
  });
});

describe("DEF-BIL-8679 · Back on the left, the reason beside the primary (D1 05, 11, 31)", () => {
  it("Back opens the footer row on the left; the primary closes it on the right", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const row = actionRow() as HTMLElement;
    const buttons = Array.from(row.querySelectorAll("button"));
    expect(buttons[0]).toHaveTextContent("Back");
    expect(buttons[0].className).toContain("mr-auto");
    expect(buttons.at(-1)).toHaveTextContent(/^Price/);
  });

  it("'Fix 5 things first.' sits in the footer row, just before the disabled primary", async () => {
    mountRun({ scope: "problems" });
    const cycle = await screen.findByLabelText(/^Cycle/);
    await waitFor(() => expect(within(cycle).getAllByRole("option").length).toBeGreaterThan(1));
    fireEvent.change(cycle, { target: { value: CYCLE_ID } });
    const start = await screen.findByRole("button", { name: "Start checking" });
    const note = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-run-footnote]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(note.closest('[data-wizard="actions"]')).not.toBeNull();
    expect(note.nextElementSibling).toBe(start);
  });
});

describe("DEF-BIL-8688 · a done step carries a tick (D1 09–36)", () => {
  it("on Check, Scope is ticked and Check carries its number", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const rail = document.querySelector('[data-wizard="rail"]') as HTMLElement;
    expect(rail.querySelector('[data-wizard-step="1"]')).toHaveTextContent(/^✓\s*Scope/);
    expect(rail.querySelector('[data-wizard-step="2"]')).toHaveTextContent(/^2\s*Check/);
  });

  it("once sent, all four steps are ticked", async () => {
    mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    const rail = document.querySelector('[data-wizard="rail"]') as HTMLElement;
    for (const step of ["1", "2", "3", "4"]) {
      expect(rail.querySelector(`[data-wizard-step="${step}"]`)).toHaveTextContent(/^✓/);
    }
  });
});

describe("DEF-BIL-8682 · Sign off's money is written as money, its tables as drawn (D1 25, 28)", () => {
  it("Payments applied is a money figure with its accounts beneath; the two tables carry the drawn heads and order", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const card = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-run-facts="run-summary"] [data-run-fact="payments"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(card).toHaveTextContent(/Payments applied\s*\$[\d,]+\.\d{2}/);
    expect(card).toHaveTextContent(/[\d,]+ payments?/);
    const balances = document.querySelector('[data-run-table="balances"]') as HTMLElement;
    expect(balances.querySelector("thead")).toHaveTextContent(/Balance\s*Amount/);
    const howPaid = document.querySelector('[data-run-table="how-paid"]') as HTMLElement;
    expect(howPaid.querySelector("thead")).toHaveTextContent(/How it will be paid\s*Accounts\s*Amount/);
    expect(Array.from(howPaid.querySelectorAll("[data-how-paid]")).map((row) => (row as HTMLElement).dataset.howPaid)).toEqual([
      "autopay",
      "plan_instalment",
      "level_pay",
      "credit_covers",
      "by_due_date",
    ]);
  });
});

describe("DEF-BIL-8686 · Fix account says where the account is and what each problem means (D1 22)", () => {
  it("the head reads name · address · unit; each card carries its meaning", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const pane = await openTagPane("No reading", "missing_read");
    const link = await waitFor(() => {
      const found = pane.querySelector<HTMLElement>("[data-open-account]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    fireEvent.click(link);
    const panel = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-run-panel="fix-account"]');
      expect(found).not.toBeNull();
      expect(found?.querySelector("[data-fix-card]")).not.toBeNull();
      return found as HTMLElement;
    });
    expect(panel).toHaveTextContent(/ · \d+ Elm St · Unit \d+/);
    const card = panel.querySelector('[data-fix-card="missing_read"]') as HTMLElement;
    expect(card).toHaveTextContent("No reading this period.");
  });
});

describe("DEF-BIL-8687 · Ready to bill as drawn (D1 20, 21)", () => {
  it("a count line, counted segments, and no Status column", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    fireEvent.click(document.querySelector('[data-tag="ready"]') as HTMLElement);
    const pane = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-tag-pane="ready"]');
      expect(found?.querySelector('[data-run-table="ready"]')).not.toBeNull();
      return found as HTMLElement;
    });
    expect(pane).toHaveTextContent("12 accounts · Nothing to fix. Priced in the next step.");
    await waitFor(() => expect(pane.querySelector("[data-ready-filter]")).toHaveTextContent(/Regular 10.*Master 2/));
    expect(pane.querySelector('[data-run-table="ready"] thead')).not.toHaveTextContent("Status");
  });
});

async function chooseCycleNow() {
  const cycle = await screen.findByLabelText(/^Cycle/);
  await waitFor(() => expect(within(cycle).getAllByRole("option").length).toBeGreaterThan(1));
  fireEvent.change(cycle, { target: { value: CYCLE_ID } });
}

describe("DEF-BIL-8691 · Scope's copy and facts as drawn (D1 01–05)", () => {
  it("the aside has a Last run total; the bill day is written 1st", async () => {
    mountRun({ scope: "continuous" });
    await chooseCycleNow();
    const aside = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-run-summary]");
      expect(found).toHaveTextContent("Last run total");
      return found as HTMLElement;
    });
    expect(aside).toHaveTextContent(/Last run total\s*\$209,944\.18/);
    await waitFor(() => expect(document.body).toHaveTextContent("Cycle bill day: 1st."));
    expect(document.body.textContent).not.toMatch(/Bill day\s*Day 1/);
  });

  it("a gap says the days were not billed by any run", async () => {
    mountRun({ scope: "gap" });
    await chooseCycleNow();
    await waitFor(() =>
      expect(document.querySelector('[data-run-problems="warning"]')).toHaveTextContent("not billed by any run."),
    );
  });

  it("an overlap still shows the period the clerk typed in the aside", async () => {
    mountRun({ scope: "overlap" });
    await chooseCycleNow();
    await waitFor(() => expect(document.querySelector('[data-run-problems="refusal"]')).not.toBeNull());
    expect(document.querySelector('[data-aside-row="period"]')).not.toHaveTextContent(/^Period\s*—$/);
  });

  it("two warnings on one field are one line, as drawn", async () => {
    mountRun({ scope: "serverOrder" });
    await chooseCycleNow();
    await waitFor(() => expect(document.querySelectorAll('[data-run-problems="warning"] [data-problem-line]').length).toBe(5));
    const period = Array.from(document.querySelectorAll<HTMLElement>('[data-run-problems="warning"] [data-problem-line]')).find(
      (line) => (line.dataset.problemLine ?? "").startsWith("period_length"),
    ) as HTMLElement;
    expect(period).toHaveTextContent("45 days. Cycle is monthly. Ends after today.");
  });
});

describe("DEF-BIL-8684 · a Check warning reaches Sign off and Send (D1 25, 31, 32)", () => {
  it("Sign off's warnings note lists each warning tag with its accounts and a See that opens it in Check", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const line = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-warning-line="tag-autopay_card_expiring"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(line).toHaveTextContent("3 accounts: Autopay card expiring.");
    fireEvent.click(line.querySelector("[data-see]") as HTMLElement);
    await waitFor(() => expect(document.querySelector('[data-tag-pane="autopay_card_expiring"]')).not.toBeNull());
  });

  it("the Send card counts the warning lines Sign off shows, never 0 while one stands", async () => {
    mountRun({ phase: "authorised" }, OPEN_RUN);
    await screen.findByRole("button", { name: "Send 1,371 bills" });
    // The fake's run has a waived base, two bills that failed to draft and an
    // Autopay card expiring warning tag: three lines on Sign off, so 3 here —
    // the card used to count the failed bills alone (2).
    await waitFor(() => expect(document.querySelector('[data-send-row="warnings"]')).toHaveTextContent(/^Warnings\s*3$/));
  });
});

describe("DEF-BIL-8699 · Scope's panels head the last column Action and write the place on one line (D1 07, 08)", () => {
  async function openPanel(link: string, dialog: string, address: string) {
    mountRun();
    const select = await screen.findByLabelText(/^Cycle/);
    await waitFor(() => expect(within(select).getAllByRole("option").length).toBeGreaterThan(1));
    fireEvent.change(select, { target: { value: CYCLE_ID } });
    fireEvent.click(await screen.findByRole("button", { name: link }));
    const panel = screen.getByRole("dialog", { name: dialog });
    const cell = (await within(panel).findByText(address, { exact: false })).closest("td") as HTMLElement;
    return { panel, cell };
  }

  it("Nobody to bill: 'Action', and '1416 Elm St · Unit B' in one cell line", async () => {
    const { panel, cell } = await openPanel("See units", "Units", "1416 Elm St");
    expect(within(panel).getAllByRole("columnheader").map((th) => th.textContent)).toContain("Action");
    expect(within(panel).queryByRole("columnheader", { name: "Fix" })).toBeNull();
    expect(cell.textContent).toBe("1416 Elm St · Unit B");
  });

  it("DEF-BIL-8700 · a Check row writes its place once, on one line: '101 Elm St · Unit 1' (D1 14, 20)", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const pane = await openTagPane("No reading", "missing_read");
    const row = await waitFor(() => {
      const found = pane.querySelector<HTMLElement>('[data-row-account="AC-2026-12881"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    const cells = Array.from(row.querySelectorAll("td")).map((td) => td.textContent);
    expect(cells).toContain("101 Elm St · Unit 1");
  });

  it("Missing meter: 'Action', and '1408 Elm St · Unit A' in one cell line", async () => {
    const { panel, cell } = await openPanel("See services", "Services", "1408 Elm St");
    expect(within(panel).getAllByRole("columnheader").map((th) => th.textContent)).toContain("Action");
    expect(cell.textContent).toBe("1408 Elm St · Unit A");
  });
});
