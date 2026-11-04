// ── Trace ──────────────────────────────────────────────
// Tests:   `moveRecordActions.ts` — the PO's ratified action grid of
//          2026-09-20 (decision log §7), one CASE PER ROW OF THE GRID.
// Rules:   hard-won law 7 (prove a guard RED before trusting it green, IN THE
//          HARNESS THAT WILL RUN IT — these were each shown red under
//          `vitest run`, never under `node <file>`)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY** — law 7 habit (2), asked
// before it was trusted:
//
//   * **A grid that returns everything, always.** `toContain`-style assertions
//     would pass on a function that emits all nine controls in every state, so
//     every case asserts the **WHOLE LIST, IN ORDER**, with `toEqual`. An extra
//     control fails; a missing one fails; a reordered one fails.
//   * **A grid that returns nothing.** An empty array satisfies every
//     *"X is absent"* assertion ever written, which is why there is no such
//     assertion here — absence is proved by the exact list not containing it.
//   * **Tiers nobody checks.** The tier is the half rule 6 is about, so it is
//     in the compared object rather than asserted separately where it could be
//     forgotten.
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

import {
  grammarMarker,
  moveActionLabelKey,
  moveRecordActions,
  type MoveAction,
  type MoveRecordActionInput,
} from "./moveRecordActions";

/** A completed move-out with all three doors resolvable — the fullest case, so
 *  a control missing from a row is missing because the GRID dropped it and
 *  never because the fixture starved it. */
const FULL: MoveRecordActionInput = {
  state: "completed",
  shortfall: "none",
  hasAccount: true,
  hasCustomer: true,
  requestRef: "SR-26-0012",
  parkId: null,
};

const a = (
  id: MoveAction["id"],
  tier: MoveAction["tier"],
  grammar: MoveAction["grammar"],
  path: MoveAction["path"] = null,
): MoveAction => ({ id, tier, grammar, path });

// ════════════════════════════════════════════════════════════════════════════
// THE GRID, ROW BY RATIFIED ROW
// ════════════════════════════════════════════════════════════════════════════
describe("the ratified action grid (decision log 2026-09-20 §7)", () => {
  const ROWS: {
    row: string;
    input: MoveRecordActionInput;
    expected: MoveAction[];
  }[] = [
    {
      row: "In flight (parked draft) | n/a, nothing settled | Resume → primary · Discard draft danger",
      input: {
        state: "in_flight",
        shortfall: "none",
        hasAccount: false,
        hasCustomer: false,
        requestRef: null,
        parkId: "park-1",
      },
      expected: [a("resume", "primary", "navigate"), a("discardDraft", "danger", "commit")],
    },
    {
      row: "Completed | settled or refunded | Open the account → secondary · Open the customer → ghost · Open the request → ghost",
      input: { ...FULL, shortfall: "none" },
      expected: [
        a("openAccount", "secondary", "navigate"),
        a("openCustomer", "ghost", "navigate"),
        a("openRequest", "ghost", "navigate"),
      ],
    },
    {
      // PO 2026-10-12 (*"MOVE-OUT DOES NOT WRITE OFF"*) took `Write it off ✓`
      // out of this ratified row; the other three options are unchanged.
      row: "Completed | short, UNDECIDED | the three doors PLUS the three options",
      input: { ...FULL, shortfall: "undecided" },
      expected: [
        a("openAccount", "secondary", "navigate"),
        a("openCustomer", "ghost", "navigate"),
        a("openRequest", "ghost", "navigate"),
        a("tieBack", "primary", "commit", "transfer"),
        a("collect", "secondary", "commit", "collect"),
        a("paymentPlan", "secondary", "create", "payment_plan"),
      ],
    },
    {
      row: "Completed | short, DECIDED | the three doors, and the outcome stated as a FACT",
      input: { ...FULL, shortfall: "decided" },
      expected: [
        a("openAccount", "secondary", "navigate"),
        a("openCustomer", "ghost", "navigate"),
        a("openRequest", "ghost", "navigate"),
      ],
    },
  ];

  it.each(ROWS)("$row", ({ input, expected }) => {
    expect(moveRecordActions(input)).toEqual(expected);
  });
});

// ════════════════════════════════════════════════════════════════════════════
// THE RATIFIED CLAUSES THE TABLE ALONE DOES NOT STATE
// ════════════════════════════════════════════════════════════════════════════
describe("Open the request → is ABSENT rather than greyed", () => {
  // PO 2026-09-20 §7, and it is deliberately NOT `BR-SHL-025`'s
  // disabled-with-reason: a counter-raised move-out has no request to open and
  // never will, so there is nothing to wait for and nothing to grey.
  it("is simply not in the list when the move-out came from no request", () => {
    const ids = moveRecordActions({ ...FULL, requestRef: null }).map((x) => x.id);
    expect(ids).toEqual(["openAccount", "openCustomer"]);
  });

  it("appears, as a ghost, the moment a request reference arrives", () => {
    // ⚠ Today `requestRef` is null on EVERY record — the wizard never writes
    // `move_records.request_id` (`DEF-CUS-6001`, scenario `E3`). This case is
    // what fires the day that defect closes, so the door is proved by
    // behaviour rather than by a fixture nobody will revisit.
    const found = moveRecordActions({ ...FULL, requestRef: "SR-26-0012" }).find(
      (x) => x.id === "openRequest",
    );
    expect(found).toEqual(a("openRequest", "ghost", "navigate"));
  });
});

describe("the danger tier, B14 rule 6", () => {
  it("names NO control on a completed record — the write-off left move-out on 2026-10-12", () => {
    const danger = moveRecordActions({ ...FULL, shortfall: "undecided" }).filter(
      (x) => x.tier === "danger",
    );
    expect(danger).toEqual([]);
  });

  it("names EXACTLY ONE control on an in-flight record, and it is the discard", () => {
    const danger = moveRecordActions({
      state: "in_flight",
      shortfall: "none",
      hasAccount: false,
      hasCustomer: false,
      requestRef: null,
      parkId: "park-1",
    }).filter((x) => x.tier === "danger");
    expect(danger).toEqual([a("discardDraft", "danger", "commit")]);
  });

  it("does NOT make `Tie the shortfall back` destructive — it moves money and destroys none", () => {
    const tie = moveRecordActions({ ...FULL, shortfall: "undecided" }).find(
      (x) => x.id === "tieBack",
    );
    expect(tie?.tier).toBe("primary");
  });

  it("never renders the two danger controls together — they belong to opposite states", () => {
    for (const shortfall of ["none", "undecided", "decided"] as const) {
      const ids = moveRecordActions({ ...FULL, shortfall }).map((x) => x.id);
      expect(ids).not.toContain("discardDraft");
    }
  });
});

describe("the doors are emitted only where they really open onto something", () => {
  // Hard-won law 2's mirror: a live control over a dead destination.
  it("drops `Open the account →` when no account is served", () => {
    const ids = moveRecordActions({ ...FULL, hasAccount: false }).map((x) => x.id);
    expect(ids).toEqual(["openCustomer", "openRequest"]);
  });

  it("drops `Open the customer →` when no customer is linked", () => {
    const ids = moveRecordActions({ ...FULL, hasCustomer: false }).map((x) => x.id);
    expect(ids).toEqual(["openAccount", "openRequest"]);
  });

  it("gives an in-flight move NO account door, because completing one is what makes an account", () => {
    // `move_record_reads._in_flight` serves the account door as
    // `NO_ACCOUNT_UNTIL_IT_COMPLETES` on every unfinished move, so this is the
    // real shape and not a defensive branch.
    const ids = moveRecordActions({
      state: "in_flight",
      shortfall: "none",
      hasAccount: false,
      hasCustomer: false,
      requestRef: null,
      parkId: "park-2",
    }).map((x) => x.id);
    expect(ids).toEqual(["resume", "discardDraft"]);
  });

  it("drops `Discard draft` when there is no parked draft to discard", () => {
    const ids = moveRecordActions({
      state: "in_flight",
      shortfall: "none",
      hasAccount: false,
      hasCustomer: false,
      requestRef: null,
      parkId: null,
    }).map((x) => x.id);
    expect(ids).toEqual(["resume"]);
  });
});

describe("B14 rule 4's grammar markers", () => {
  it("navigates with an arrow, commits with a tick, creates with a plus", () => {
    expect(grammarMarker("navigate")).toEqual({ before: "", after: " →" });
    expect(grammarMarker("commit")).toEqual({ before: "", after: " ✓" });
    expect(grammarMarker("create")).toEqual({ before: "+ ", after: "" });
  });

  it("gives every option in the undecided row the grammar the PO ratified", () => {
    const byId = Object.fromEntries(
      moveRecordActions({ ...FULL, shortfall: "undecided" }).map((x) => [x.id, x.grammar]),
    );
    // `Tie the shortfall back ✓` · `Follow the customer ✓` · `+ Payment plan`
    // — the ticks and the plus are the PO's own spelling.
    expect(byId).toEqual({
      openAccount: "navigate",
      openCustomer: "navigate",
      openRequest: "navigate",
      tieBack: "commit",
      collect: "commit",
      paymentPlan: "create",
    });
  });
});

describe("ONE ACT, ONE NAME — PO 2026-09-20 §7 finding (a)", () => {
  it("gives the header control and the options row the IDENTICAL catalogue key", () => {
    // The whole finding was four spellings of one act. Pointing both surfaces
    // at one key is what makes them unable to disagree — a sweep that matched
    // four strings would leave four strings free to drift again.
    expect(moveActionLabelKey("tieBack")).toBe("customers.moveRecord.path.transfer");
  });

  it("reuses the catalogue's existing key for every money option", () => {
    expect(moveActionLabelKey("collect")).toBe("customers.moveRecord.path.collect");
    expect(moveActionLabelKey("paymentPlan")).toBe("customers.moveRecord.path.payment_plan");
  });

  it("resolves every action's key in the catalogue — no label falls back to its key", () => {
    // ⚠ This is the eleventh-service lesson in miniature: a key that resolves
    // to nothing renders as the key itself, `tsc` passes and every other test
    // passes. The catalogue is the only place that can answer it.
    const catalogue = en as Record<string, string>;
    const ids: MoveAction["id"][] = [
      "resume",
      "discardDraft",
      "openAccount",
      "openCustomer",
      "openRequest",
      "tieBack",
      "collect",
      "paymentPlan",
    ];
    const missing = ids.filter((id) => typeof catalogue[moveActionLabelKey(id)] !== "string");
    expect(missing).toEqual([]);
  });

  it("keeps every action label inside B14 rule 33's three-word cap for a LABEL", () => {
    const catalogue = en as Record<string, string>;
    const ids: MoveAction["id"][] = [
      "resume",
      "discardDraft",
      "openAccount",
      "openCustomer",
      "openRequest",
      "tieBack",
      "collect",
      "paymentPlan",
    ];
    const overBudget = ids
      .map((id) => [id, catalogue[moveActionLabelKey(id)]] as const)
      .filter(([, text]) => text.split(/\s+/).length > 3);
    expect(overBudget).toEqual([]);
  });
});

describe("the consequence preview obeys B14 rule 33 and tells the truth", () => {
  const catalogue = en as Record<string, string>;
  const BODIES = ["tieBack", "collect", "discardDraft"] as const;

  it.each(BODIES)("%s: at most two sentences, at most six words each", (which) => {
    const body = catalogue[`customers.moveRecord.confirm.${which}.body`];
    expect(typeof body).toBe("string");
    const sentences = body.split("\n").filter((s) => s.trim() !== "");
    expect(sentences.length).toBeLessThanOrEqual(2);
    for (const s of sentences) {
      // The interpolation placeholder counts as the one word it renders as.
      expect(s.replace(/\{\{\w+\}\}/g, "X").split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

  it("says the amount MOVES — OQ-1250 closed 2026-10-14 and the tie-back posts", () => {
    // p118 draws `Now: $186.40 moves to A-10001 and A-10432 settles at zero`.
    // Until 2026-10-14 `shortfall_decision` wrote NO journal line and this
    // case asserted *"The books do not move yet"*. PO D5 (*"option 1"*) made
    // the tie-back ONE AR→AR entry, so the first half of the drawn sentence is
    // now true and is built. The second half is NOT copy: whether the
    // tenant's account then stands at zero depends on what else it owes, and
    // a promise of zero would be law 1 on a money path.
    const body = catalogue["customers.moveRecord.confirm.tieBack.body"];
    expect(body).toContain("{{amount}} moves to {{account}} now.");
    expect(body).not.toMatch(/do not move/i);
    expect(body).not.toMatch(/settles at zero/i);
  });
});

describe("the three dispositions are the SERVER's, never a list typed out here", () => {
  it("names each shortfall path exactly once across the undecided row", () => {
    const paths = moveRecordActions({ ...FULL, shortfall: "undecided" })
      .map((x) => x.path)
      .filter((p): p is NonNullable<typeof p> => p !== null);
    // PO 2026-10-12 — no `write_off`: the balance stays outstanding and is chased.
    expect([...paths].sort()).toEqual(["collect", "payment_plan", "transfer"]);
  });

  it("gives a door no disposition at all — a door writes nothing", () => {
    const doors = moveRecordActions({ ...FULL, shortfall: "undecided" }).filter((x) =>
      ["openAccount", "openCustomer", "openRequest"].includes(x.id),
    );
    expect(doors.every((d) => d.path === null)).toBe(true);
  });
});
