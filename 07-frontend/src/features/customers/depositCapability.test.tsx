// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave H — the ONE deposit capability.
//          PO 2026-09-12: *"(a) It is one concept — money held against an
//          account — and building it four times would give four behaviours."*
//          Screens: S18 step 4 · S19 step 5 (blueprint pages 63-64, 70-71)
// Amended: 2026-09-23 — the amount is the PLAN's figure for the category, read
//          only (DEF-CUS-6369); *Why this amount* and the credit-tier note are
//          gone; *No* only where the plan asks none (OQ-CUS-12620 (a),
//          DEF-CUS-6371); a waive carries a reason (DEF-CUS-6370)
//          2026-10-21 — no *Clearing date* and no CLEARING note (DEF-CUS-10324,
//          CR-186-BRC10): the deposit is POSTED at entry; only bank
//          reconciliation clears it
// Rules:  BR-CUS-025 (a deposit is a LIABILITY) · BR-CUS-037 (the screen is
//          an ENTRY POINT) · BR-RAT-020/023 (the plan's figure per category) ·
//          B14 rule 33 (text capped by what it is for; rationale is zero words)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PURE HALF IS TESTED AS FUNCTIONS AND NOT ONLY THROUGH THE SCREEN**,
// for `UnitPageWaveF`'s reason: the payload builder and the plan fold have more
// branches than a clerk can reach by clicking in one sitting.
//
// ⚠ **THE WORKED FIGURE IS ASSERTED, NOT ILLUSTRATED.** Rosa Pemberton is
// Residential and the unit's plan asks Residential **$150.00**. The fake server
// below answers exactly what `GET /accounts/deposit-standard` answers for her,
// and the step must show `150.00`, read-only — so a figure that ever comes from
// anywhere else (a typed box, a default, the drawing) turns this red.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/api/client";
import type { DepositStandard } from "@/api/endpoints";

import {
  DEPOSIT_DECISIONS,
  DepositStep,
  type DepositForm,
  applyPlanStandard,
  depositPayload,
  depositProblem,
  emptyDepositForm,
  planKey,
  takenToday,
} from "./depositCapability";

afterEach(cleanup);

/** The key back, so an assertion reads the key rather than a translation. */
const t = (key: string) => key;

const UNIT = "01a0cadb-c3da-7037-a3be-902379649501";
/** What the server states for the plan — four decimals, a STRING. */
const PLANS_FIGURE = "150.0000";
const COMMERCIAL_FIGURE = "400.0000";
const KEY = planKey(UNIT, "residential");

function asks(amount: string, account_type = "residential"): DepositStandard {
  return { unit_id: UNIT, account_type, asks: true, amount, currency: "USD" };
}
function none(account_type = "industrial"): DepositStandard {
  return { unit_id: UNIT, account_type, asks: false, amount: null, currency: null };
}

function taken(overrides: Partial<DepositForm> = {}): DepositForm {
  return {
    ...emptyDepositForm(),
    decision: "required",
    amount: PLANS_FIGURE,
    plan: "asks",
    plan_for: KEY,
    due_on: "2026-05-16",
    take_now: true,
    method_code: "card",
    confirmation: "AUTH 55192",
    // What the box SHOWS: an amount at 2 places (DEF-CUS-9524).
    amount_taken: "150.00",
    posted_at: "2026-05-02",
    ...overrides,
  };
}

describe("the deposit payload — what reaches the server, and what does not", () => {
  it("sends nothing at all when the plan asks no deposit", () => {
    expect(depositPayload({ ...emptyDepositForm(), plan: "none", plan_for: KEY })).toBeUndefined();
  });

  it("sends the decision and the PLAN's figure, and no payment, when it is not taken today", () => {
    const block = depositPayload(taken({ take_now: false }));
    // The figure the step SHOWED travels back, so a plan edited in between is
    // refused by name rather than silently re-priced.
    expect(block).toEqual({ decision: "required", amount: PLANS_FIGURE, due_on: "2026-05-16" });
    for (const key of ["take_now", "method_code", "posted_at", "cleared_at", "reason"]) {
      expect(block).not.toHaveProperty(key);
    }
  });

  it("a waived deposit carries its decision, the figure and its REASON — never a payment", () => {
    const block = depositPayload(taken({ decision: "waived", waive_reason: " Hardship " }));
    expect(block).toEqual({ decision: "waived", amount: PLANS_FIGURE, waive_reason: "Hardship" });
  });

  it("sends the whole tender when the money is taken today", () => {
    expect(depositPayload(taken())).toEqual({
      decision: "required",
      amount: PLANS_FIGURE,
      due_on: "2026-05-16",
      take_now: true,
      method_code: "card",
      confirmation: "AUTH 55192",
      amount_taken: "150.00",
      posted_at: "2026-05-02",
    });
  });

  it("DEF-CUS-10324: a deposit taken today carries a posting date and NEVER a clearing date", () => {
    // The form has no clearing field at all; a stale draft that still holds
    // one must not put it on the wire (the server refuses `cleared_at`).
    const stale = { ...taken(), cleared_at: "2026-05-02" } as DepositForm;
    const block = depositPayload(stale);
    expect(block).not.toHaveProperty("cleared_at");
    expect(block).toHaveProperty("posted_at", "2026-05-02");
    expect(emptyDepositForm()).not.toHaveProperty("cleared_at");
  });
});

describe("the plan decides — OQ-CUS-12620 (a)", () => {
  it("Rosa, Residential: the plan's $150.00 becomes the figure and the answer becomes Take", () => {
    const next = applyPlanStandard(emptyDepositForm(), asks(PLANS_FIGURE), KEY);
    expect(next).toMatchObject({ plan: "asks", amount: PLANS_FIGURE, decision: "required" });
    expect(next.plan_for).toBe(KEY);
  });

  it("a plan that asks nothing leaves No as the only answer and clears everything behind it", () => {
    const next = applyPlanStandard(
      taken({ decision: "waived", waive_reason: "Hardship" }),
      none(),
      planKey(UNIT, "industrial"),
    );
    expect(next).toMatchObject({
      plan: "none",
      decision: "not_required",
      amount: "",
      waive_reason: "",
      take_now: false,
      method_code: "",
    });
  });

  it("a change of category moves the figure, and an untouched Amount taken follows it", () => {
    const commercial = applyPlanStandard(
      taken(),
      asks(COMMERCIAL_FIGURE, "commercial"),
      planKey(UNIT, "commercial"),
    );
    expect(commercial.amount).toBe(COMMERCIAL_FIGURE);
    // An amount, so 2 places (DEF-CUS-9524) — the stored figure stays 4.
    expect(commercial.amount_taken).toBe("400.00");
    // …but a part-payment the clerk TYPED is theirs and is left alone.
    const part = applyPlanStandard(
      taken({ amount_taken: "25.00" }),
      asks(COMMERCIAL_FIGURE, "commercial"),
      planKey(UNIT, "commercial"),
    );
    expect(part.amount_taken).toBe("25.00");
  });

  it("a waive is kept when the figure is re-read — only No turns into Take", () => {
    const next = applyPlanStandard(taken({ decision: "waived" }), asks(PLANS_FIGURE), KEY);
    expect(next.decision).toBe("waived");
  });

  it("returns the SAME object when nothing changes, so the step's effect cannot loop", () => {
    const form = taken();
    expect(applyPlanStandard(form, asks(PLANS_FIGURE), KEY)).toBe(form);
  });
});

describe("the gate — it names the FIELD, because DEF-CUS-5082 is the other thing", () => {
  it("holds until the plan has been read", () => {
    expect(depositProblem(emptyDepositForm())).toBe("amount");
  });

  it("lets No through ONLY where the plan asks none", () => {
    expect(depositProblem({ ...emptyDepositForm(), plan: "none", plan_for: KEY })).toBeNull();
    expect(depositProblem(taken({ decision: "not_required" }))).toBe("decision");
  });

  it.each([
    [{ amount: "" }, "amount"],
    [{ method_code: "" }, "method_code"],
    [{ posted_at: "" }, "posted_at"],
    [{ decision: "waived", waive_reason: "  " }, "waive_reason"],
  ])("holds on %o and names its own field", (patch, field) => {
    expect(depositProblem(taken(patch as Partial<DepositForm>))).toBe(field);
  });

  it("a waive with its reason is ready — no tender is asked", () => {
    expect(
      depositProblem(taken({ decision: "waived", waive_reason: "Hardship", method_code: "" })),
    ).toBeNull();
  });

  it("does not ask for a tender on a deposit that is not being taken today", () => {
    expect(depositProblem(taken({ take_now: false, method_code: "", posted_at: "" }))).toBeNull();
  });
});

describe("what the customer pays today", () => {
  it("is the amount taken, to two decimals however it was stored", () => {
    // Hard rule 2 — money DISPLAYS to 2 decimals whatever it is stored to.
    expect(takenToday(taken())).toBe("150.00");
    expect(takenToday(taken({ amount_taken: "150.006" }))).toBe("150.01");
  });

  it("falls back to the deposit when the box was never touched", () => {
    expect(takenToday(taken({ amount_taken: "" }))).toBe("150.00");
  });

  it("is zero when nothing is handed over today", () => {
    expect(takenToday(taken({ take_now: false }))).toBe("0.00");
    expect(takenToday(emptyDepositForm())).toBe("0.00");
  });
});

describe("the vocabulary is DERIVED, not hand-typed twice (hard-won law 12)", () => {
  it("carries the server's three decisions, in its order", () => {
    expect([...DEPOSIT_DECISIONS]).toEqual(["required", "not_required", "waived"]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE STEP — mounted against a fake server that answers the plan's figure
// ══════════════════════════════════════════════════════════════════════════
function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

/** Answers `GET /accounts/deposit-standard` per category and RECORDS each
 *  call, so "the step asked for Rosa's category" is read off a real request. */
function planServer(byCategory: Record<string, DepositStandard>) {
  const calls: string[] = [];
  const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(typeof input === "string" ? input : String(input), "http://x");
    calls.push(`${url.pathname}?${url.searchParams.toString()}`);
    const category = url.searchParams.get("account_type") ?? "";
    return jsonResponse(byCategory[category] ?? none(category));
  });
  return { client: createApiClient({ fetchImpl, tenant: "brazosbend" } as never), calls };
}

/** A stateful wizard in miniature: the step's `onChange` really moves the
 *  form, exactly as `setDeposit` does in both wizards. */
function Harness(props: {
  initial: DepositForm;
  category: string;
  client: ReturnType<typeof planServer>["client"];
  onForm?: (form: DepositForm) => void;
  currency?: string | null;
  carryForward?: boolean;
}) {
  const [form, setForm] = useState(props.initial);
  props.onForm?.(form);
  return (
    <DepositStep
      values={form}
      onChange={setForm}
      t={t}
      dateFormat="MM/DD/YYYY"
      currency={props.currency === undefined ? "USD" : props.currency}
      carryForward={props.carryForward}
      unitId={UNIT}
      category={props.category}
      client={props.client}
    />
  );
}

function mount(
  initial: DepositForm,
  category = "residential",
  extra: { currency?: string | null; carryForward?: boolean } = {},
) {
  const server = planServer({
    residential: asks(PLANS_FIGURE),
    commercial: asks(COMMERCIAL_FIGURE, "commercial"),
  });
  let latest: DepositForm = initial;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = (cat: string) => (
    <QueryClientProvider client={qc}>
      <Harness
        initial={initial}
        category={cat}
        client={server.client}
        onForm={(f) => {
          latest = f;
        }}
        {...extra}
      />
    </QueryClientProvider>
  );
  const view = render(ui(category));
  return {
    ...view,
    server,
    form: () => latest,
    setCategory: (cat: string) => view.rerender(ui(cat)),
  };
}

describe("the step shows the plan's figure and offers only what the plan allows", () => {
  it("Rosa: reads her category's figure and shows $150.00, read-only, with Take or Waive", async () => {
    const { container, server, form } = mount(emptyDepositForm());
    await waitFor(() => expect(container.querySelector("#deposit_amount")).toBeTruthy());
    expect(server.calls).toEqual([
      `/api/brazosbend/accounts/deposit-standard?unit_id=${UNIT}&account_type=residential`,
    ]);
    const amount = container.querySelector<HTMLInputElement>("#deposit_amount");
    expect(amount?.value).toBe("150.00");
    expect(amount?.readOnly).toBe(true);
    expect(container.textContent).toContain("customers.deposit.help.planFigure");
    // *No* is not offered on a plan that asks a figure.
    const options = [...container.querySelectorAll("#deposit_decision option")].map(
      (o) => (o as HTMLOptionElement).value,
    );
    expect(options.filter((v) => v !== "")).toEqual(["required", "waived"]);
    expect(form()).toMatchObject({ plan: "asks", amount: PLANS_FIGURE, decision: "required" });
    expect(depositProblem(form())).toBeNull();
  });

  it("a plan that asks nothing says so, and offers nothing to pick or type", async () => {
    const { container, form } = mount(emptyDepositForm(), "industrial");
    await waitFor(() => expect(container.textContent).toContain("customers.deposit.noPlanDeposit"));
    expect(container.querySelector("#deposit_decision")).toBeNull();
    expect(container.querySelector("#deposit_amount")).toBeNull();
    expect(container.querySelector("input:not([type=hidden])")).toBeNull();
    expect(depositProblem(form())).toBeNull();
    expect(depositPayload(form())).toBeUndefined();
  });

  it("changing the category re-reads the plan, and the figure follows", async () => {
    const view = mount(emptyDepositForm());
    await waitFor(() => expect(view.form().amount).toBe(PLANS_FIGURE));
    act(() => view.setCategory("commercial"));
    await waitFor(() => expect(view.form().amount).toBe(COMMERCIAL_FIGURE));
    expect(view.server.calls.at(-1)).toContain("account_type=commercial");
    expect(view.container.querySelector<HTMLInputElement>("#deposit_amount")?.value).toBe("400.00");
  });

  it("holds, and says what it needs, when the category is not chosen yet", () => {
    const { container, server, form } = mount(emptyDepositForm(), "");
    expect(container.textContent).toContain("customers.deposit.planNeedsChoices");
    expect(server.calls).toEqual([]);
    expect(depositProblem(form())).toBe("amount");
  });

  it("*Why this amount* and the credit-tier note are GONE (DEF-CUS-6369)", async () => {
    const { container } = mount(taken());
    await waitFor(() => expect(container.querySelector("#deposit_amount")).toBeTruthy());
    expect(container.querySelector("#deposit_reason")).toBeNull();
    expect(container.querySelector('[data-advisory="BR-CUS-058"]')).toBeNull();
    // The Amount box's OWN help line — read by id, because the key
    // `customers.deposit.help.amount` is a prefix of `…help.amountTaken`, and a
    // substring check over the whole step passes or fails on the wrong box.
    expect(container.querySelector("#deposit_amount-help")?.textContent).toBe(
      "customers.deposit.help.planFigure",
    );
  });

  it("a waive asks for its reason, and nothing about money", async () => {
    const { container } = mount(taken({ decision: "waived", take_now: false }));
    await waitFor(() => expect(container.querySelector("#deposit_waive_reason")).toBeTruthy());
    expect(container.querySelector('label[for="deposit_waive_reason"]')).toBeTruthy();
    expect(container.querySelector("#deposit_take_now")).toBeNull();
    expect(container.querySelector("#deposit_due_on")).toBeNull();
  });

  it("draws the drawn tender controls, each with a bound label, once the money is taken", async () => {
    // ⚠ ASSERTED BY CONTROL ID, NOT BY LABEL TEXT: a required field's label
    // carries the kit's asterisk, and `field.amount` is a prefix of
    // `field.amountTaken`.
    const { container } = mount(taken());
    await waitFor(() => expect(container.querySelector("#deposit_method_code")).toBeTruthy());
    for (const id of [
      "deposit_decision",
      "deposit_amount",
      "deposit_due_on",
      "deposit_take_now",
      "deposit_method_code",
      "deposit_amount_taken",
      "deposit_confirmation",
      "deposit_posted_at",
    ]) {
      expect(container.querySelector(`#${id}`), `the drawn control ${id} is missing`).toBeTruthy();
      expect(container.querySelector(`label[for="${id}"]`), `${id} has no label`).toBeTruthy();
    }
    expect(container.querySelector("[data-deposit-totals]")).toBeTruthy();
  });

  it("DEF-CUS-10324: a $150.00 deposit taken today offers no clearing date and no 'until it clears' note", async () => {
    const { container } = mount(taken());
    await waitFor(() => expect(container.querySelector("#deposit_posted_at")).toBeTruthy());
    expect(container.querySelector("#deposit_cleared_at")).toBeNull();
    const text = container.textContent ?? "";
    for (const retired of [
      "customers.deposit.field.clearedAt",
      "customers.deposit.help.clearedAt",
      "customers.deposit.tag.clearing",
      "customers.deposit.clearingBlank",
      "customers.deposit.clearingSet",
    ]) {
      expect(text).not.toContain(retired);
    }
  });

  it("adds the carry-forward absence ONLY on the move-in (blueprint page 71)", async () => {
    const counter = mount(taken(), "residential", { carryForward: false });
    await waitFor(() => expect(counter.container.querySelector("#deposit_amount")).toBeTruthy());
    expect(counter.container.textContent).not.toContain("customers.deposit.carryAbsent");
    cleanup();
    const moveIn = mount(taken(), "residential", { carryForward: true });
    await waitFor(() =>
      expect(moveIn.container.textContent).toContain("customers.deposit.carryAbsent"),
    );
  });

  it("never renders a currency it was not given — a sentence instead of USD", async () => {
    const { container } = mount(taken(), "residential", { currency: null });
    await waitFor(() => expect(container.querySelector("[data-deposit-totals]")).toBeTruthy());
    const totals = container.querySelector("[data-deposit-totals]");
    expect(totals?.textContent).toContain("customers.deposit.totals.currencyAbsent");
    expect(totals?.textContent).not.toContain("USD");
    expect(totals?.textContent).not.toContain("$");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// OQ-RAT-12786 — a deposit priced by meter size this unit's size does not price
// ══════════════════════════════════════════════════════════════════════════
describe("a deposit priced by size that this unit's size does not price", () => {
  function refusingServer(status: number, body: unknown) {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    );
    return createApiClient({ fetchImpl, tenant: "brazosbend" } as never);
  }

  function mountWith(client: ReturnType<typeof createApiClient>) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={qc}>
        <DepositStep
          values={emptyDepositForm()}
          onChange={() => undefined}
          t={t}
          dateFormat="MM/DD/YYYY"
          currency="USD"
          unitId={UNIT}
          category="residential"
          client={client as never}
        />
      </QueryClientProvider>,
    );
  }

  it("says the size is not priced, by the server's own key — never 'asks none'", async () => {
    const { container } = mountWith(
      refusingServer(400, {
        code: "VAL-004",
        message_key: "customers.deposit.sizeNotPriced",
        params: { charge: "DEP-SIZE", size: "W-1" },
        field_errors: [],
      }),
    );
    await waitFor(() => expect(container.textContent).toContain("customers.deposit.sizeNotPriced"));
    expect(container.textContent).not.toContain("customers.deposit.noPlanDeposit");
    expect(container.querySelector("#deposit_amount")).toBeNull();
  });

  it("any other failure still reads as the plan being unreadable", async () => {
    const { container } = mountWith(
      refusingServer(500, {
        code: "SYS-001",
        message_key: "api.error.unexpected",
        params: {},
        field_errors: [],
      }),
    );
    await waitFor(() =>
      expect(container.textContent).toContain("customers.deposit.planUnreadable"),
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-9521 — no meter fitted: the clerk picks the size. PO 2026-10-04,
// verbatim: *"(c) Let the clerk pick the size on the Deposit step."* Rosa,
// 1408 Elm St · Unit A, the plan asks 5/8" $150.00 or 2" $600.00.
// ══════════════════════════════════════════════════════════════════════════
describe("no meter fitted — the clerk picks the size (DEF-CUS-9521)", () => {
  /** Served in CODE order (`W-2` before `W-58`), as the server does. */
  const PICK: DepositStandard = {
    unit_id: UNIT,
    account_type: "residential",
    asks: true,
    amount: null,
    currency: "USD",
    pick_size: true,
    sizes: [
      { size_class: "W-2", label: 'Water 2"', amount: "600.0000", currency: "USD" },
      { size_class: "W-58", label: 'Water 5/8"', amount: "150.0000", currency: "USD" },
    ],
  };

  function mountPick() {
    const server = planServer({ residential: PICK });
    let latest: DepositForm = emptyDepositForm();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={qc}>
        <Harness
          initial={emptyDepositForm()}
          category="residential"
          client={server.client}
          onForm={(f) => {
            latest = f;
          }}
        />
      </QueryClientProvider>,
    );
    return { ...view, form: () => latest };
  }

  it("offers the plan's sizes by NAME, smallest first, and holds until one is picked", async () => {
    const { container, form } = mountPick();
    await waitFor(() => expect(container.querySelector("#deposit_size_class")).toBeTruthy());
    const options = [...container.querySelectorAll("#deposit_size_class option")]
      .map((o) => o as HTMLOptionElement)
      .filter((o) => o.value !== "");
    expect(options.map((o) => o.textContent)).toEqual(['Water 5/8"', 'Water 2"']);
    expect(options.map((o) => o.value)).toEqual(["W-58", "W-2"]);
    expect(container.textContent).toContain("customers.deposit.help.sizePick");
    expect(container.textContent).not.toContain("customers.deposit.sizeNotPriced");
    expect(form()).toMatchObject({
      plan: "asks",
      decision: "required",
      amount: "",
      size_class: "",
    });
    expect(depositProblem(form())).toBe("size_class");
  });

  it('picking 2" makes the deposit $600.00 and sends the size on the commit', async () => {
    const { container, form } = mountPick();
    await waitFor(() => expect(container.querySelector("#deposit_size_class")).toBeTruthy());
    const select = container.querySelector<HTMLSelectElement>("#deposit_size_class")!;
    await act(async () => {
      select.value = "W-2";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitFor(() =>
      expect(container.querySelector<HTMLInputElement>("#deposit_amount")?.value).toBe("600.00"),
    );
    expect(form()).toMatchObject({ amount: "600.0000", size_class: "W-2", size_label: 'Water 2"' });
    expect(depositProblem(form())).toBeNull();
    expect(depositPayload(form())).toMatchObject({
      decision: "required",
      amount: "600.0000",
      size_class: "W-2",
    });
  });

  it("a fitted meter shows no picker and sends no size", () => {
    const folded = applyPlanStandard(emptyDepositForm(), asks(PLANS_FIGURE), KEY);
    expect(folded.size_pick).toBe(false);
    expect(depositPayload(folded)).not.toHaveProperty("size_class");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-9524 — *Amount taken* is an AMOUNT, and an amount DISPLAYS 2 places
// (CLAUDE.md hard rule 2). The server states the plan's figure to four
// (`600.0000`); the box defaulted to that string and showed `600.0000`. Found
// on lane DEP-PICK's walk (photo 03) and asserted here by the box's VALUE in
// the DOM, because the old proof asserted the 4-place string itself.
// ══════════════════════════════════════════════════════════════════════════
describe("Amount taken shows the deposit to 2 places (DEF-CUS-9524)", () => {
  const PICK: DepositStandard = {
    unit_id: UNIT,
    account_type: "residential",
    asks: true,
    amount: null,
    currency: "USD",
    pick_size: true,
    sizes: [
      { size_class: "W-2", label: 'Water 2"', amount: "600.0000", currency: "USD" },
      { size_class: "W-58", label: 'Water 5/8"', amount: "150.0000", currency: "USD" },
    ],
  };

  it('no meter, 2" picked, Taken today ticked: the box reads 600.00', async () => {
    const server = planServer({ residential: PICK });
    let latest: DepositForm = emptyDepositForm();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={qc}>
        <Harness
          initial={emptyDepositForm()}
          category="residential"
          client={server.client}
          onForm={(f) => {
            latest = f;
          }}
        />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(container.querySelector("#deposit_size_class")).toBeTruthy());
    const select = container.querySelector<HTMLSelectElement>("#deposit_size_class")!;
    await act(async () => {
      select.value = "W-2";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitFor(() => expect(container.querySelector("#deposit_take_now")).toBeTruthy());
    await act(async () => {
      container.querySelector<HTMLInputElement>("#deposit_take_now")!.click();
    });
    await waitFor(() =>
      expect(container.querySelector<HTMLInputElement>("#deposit_amount_taken")?.value).toBe(
        "600.00",
      ),
    );
    // The money is unchanged: $600.00 is what is taken and sent.
    expect(Number(latest.amount_taken)).toBe(600);
    expect(takenToday(latest)).toBe("600.00");
  });

  it("the plan's figure re-read: an untouched Amount taken follows it, at 2 places", () => {
    const next = applyPlanStandard(
      taken({ amount_taken: "150.00" }),
      asks(COMMERCIAL_FIGURE, "commercial"),
      planKey(UNIT, "commercial"),
    );
    expect(next.amount_taken).toBe("400.00");
  });
});
