// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-003 · US-CUS-012 · US-CUS-013 · US-CUS-014 · US-CUS-015
// Change:   CR-094-BRC01 step 2 wave J — `ACC-S14`, the thirteen quick actions.
//           CR-094-BRC01 step 2 wave L — `BR-CUS-1051`, the eight that used to
//           navigate away now open OVER the account.
// Rules:    BR-SHL-025 · BR-SHL-045 · BR-CUS-1051 · B14 rule 37 (a figure drawn
//           in a wireframe is an ILLUSTRATION, never a fact to build to)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE CENSUS IS THE POINT OF THIS FILE.** The blueprint contradicts itself
// about how many controls this screen has — `R5`'s prose says *"Twelve groups,
// twelve controls"* while its own caption says *"eleven groups, eleven
// controls"* — so the step-1 lane's instruction to step 2 was to COUNT THE
// DRAWING. These cases hold that count where a future lane will trip over it if
// an action is quietly dropped, and they are the only thing standing between
// *"twelve are declared"* and *"thirteen were drawn"*.
import { describe, expect, it } from "vitest";

import { ACCOUNT_ACTION_OVERLAYS } from "./accountActionOverlays";
import {
  ACCOUNT_QUICK_ACTIONS,
  ACCOUNT_QUICK_ACTION_IDS,
  opensOverTheAccount,
  quickActionFor,
  quickFormFor,
} from "./accountQuickActions";

describe("the thirteen quick actions, counted off the drawing", () => {
  it("declares thirteen, and thirteen is what R4's own captions number", () => {
    // `Quick action 1 of 13` … `Quick action 13 of 13`, pages 155–174.
    expect(ACCOUNT_QUICK_ACTION_IDS).toHaveLength(13);
    expect(ACCOUNT_QUICK_ACTIONS).toHaveLength(13);
  });

  it("every declared id has exactly one configuration", () => {
    for (const id of ACCOUNT_QUICK_ACTION_IDS) {
      const matches = ACCOUNT_QUICK_ACTIONS.filter((action) => action.id === id);
      expect(matches, `one configuration for ${id}`).toHaveLength(1);
    }
  });

  it("carries ACC-Q01..ACC-Q13, each figure once", () => {
    const figures = ACCOUNT_QUICK_ACTIONS.map((action) => action.figure);
    expect(new Set(figures).size).toBe(13);
    expect(figures).toEqual([
      "ACC-Q01", "ACC-Q02", "ACC-Q03", "ACC-Q04", "ACC-Q05", "ACC-Q06", "ACC-Q07",
      "ACC-Q08", "ACC-Q09", "ACC-Q10", "ACC-Q11", "ACC-Q12", "ACC-Q13",
    ]);
  });

  it("the six header actions come first, in the drawn order", () => {
    // `Adjust · Move-out · Activate account · Move-in · Close out · Record
    // payment` — read off the header of all fifteen action drawings.
    expect(ACCOUNT_QUICK_ACTION_IDS.slice(0, 6)).toEqual([
      "adjust", "moveOut", "activate", "moveIn", "closeOut", "recordPayment",
    ]);
  });

  it("the rail's seven follow, in BR-SHL-045's order", () => {
    expect(ACCOUNT_QUICK_ACTION_IDS.slice(6)).toEqual([
      "sendStatement", "printBill", "issueCredit", "changePlan",
      "disconnectNotice", "paymentPlan", "addNote",
    ]);
  });

  it("every action says where it goes, and a held one says why", () => {
    for (const action of ACCOUNT_QUICK_ACTIONS) {
      const { destination } = action;
      if (destination.kind !== "form") {
        // BR-SHL-025's principle: a control that cannot act carries its reason,
        // and a reason nobody wrote is the defect that rule exists to prevent.
        expect(destination.why.length, `${action.id} states a reason`).toBeGreaterThan(0);
      } else {
        expect(destination.form.titleKey).toContain("customers.account.quick.");
      }
    }
  });
});

describe("the activate form — the one this wave opens over the account", () => {
  it("is one of the TWO actions declaring a form, and says so plainly", () => {
    // ⚠ **THIS READ `["activate"]` UNTIL WAVE M**, when `sendStatement`
    // stopped refusing and declared `STATEMENT_FORM`. The list is asserted in
    // FULL rather than by length, so a third form cannot arrive unnamed.
    const withForms = ACCOUNT_QUICK_ACTIONS.filter((a) => a.destination.kind === "form");
    expect(withForms.map((a) => a.id)).toEqual(["activate", "sendStatement"]);
  });

  it("asks ONLY for fields POST /accounts/{id}/activate accepts", () => {
    // ⚠ THIS IS THE CASE THAT MATTERS MOST IN THIS FILE.
    // `apps/customers/services.activate_account` opens with
    //     _reject_unknown(data, frozenset({"opened_at", "status"}))
    // and `_reject_unknown` RAISES a field error on a stranger rather than
    // ignoring it. R4 draws TEN fields on `ACC-Q03`; nine of them cannot be
    // sent. A form that collected them would 400 on a field it drew itself,
    // and every other check in this repo would pass over it.
    const form = quickFormFor("activate");
    expect(form).not.toBeNull();
    const collected = form!.sections
      .flatMap((section) => section.fields)
      .filter((field) => field.kind !== "readonly")
      .map((field) => field.id);
    expect(collected).toEqual(["opened_at"]);
  });

  it("names the server's own field, so the wire key cannot drift from the form key", () => {
    const form = quickFormFor("activate")!;
    const ids = form.sections.flatMap((s) => s.fields).map((f) => f.id);
    expect(ids).toContain("opened_at");
  });

  it("every recap row reading a field names a field the form declares", () => {
    // A `fromField` pointing at nothing renders the absence sentence forever
    // and looks exactly like a fact the account does not hold — the silent
    // half of hard-won law 2.
    const form = quickFormFor("activate")!;
    const declared = new Set(form.sections.flatMap((s) => s.fields).map((f) => f.id));
    const rows = [...form.recapRows, ...(form.recapOutcome === undefined ? [] : [form.recapOutcome])];
    for (const row of rows) {
      if (row.fromField !== undefined) {
        expect(declared, `${row.labelKey} reads a declared field`).toContain(row.fromField);
      }
    }
  });

  it("reads back the date the clerk typed, not only the account as it stands", () => {
    // `ACC-S14`: *"reads back a recap"*. A recap built only from server facts
    // would not move when the date moves, and a recap that cannot move is
    // decoration.
    const form = quickFormFor("activate")!;
    const live = form.recapRows.filter((row) => row.fromField !== undefined);
    expect(live.map((row) => row.fromField)).toEqual(["opened_at"]);
  });

  it("states the three things the server will not do", () => {
    // R4's own box — *"Two things the server will not manage, and says so now
    // rather than after"* — plus the opening read, which the drawing draws as a
    // live picker and the endpoint cannot accept.
    const form = quickFormFor("activate")!;
    expect(form.caveatBulletKeys).toHaveLength(3);
    expect(form.caveatHeadingKey).toBeDefined();
  });

  it("commits through the label the header button already carried", () => {
    // Two strings for one act is how a product grows two names for one thing.
    expect(quickFormFor("activate")!.commitLabelKey).toBe("customers.account.action.activate");
  });

  it("is not blocked — its endpoint is served", () => {
    expect(quickFormFor("activate")!.commitBlockedKey).toBeUndefined();
  });
});

describe("BR-CUS-1051 — every quick action opens OVER the account", () => {
  // PO 2026-09-13, verbatim: *"Yes move the eight quick actions over the
  // account"*. Finding `F12` measured the state this reverses: NINE of the
  // thirteen took a clerk off the account they were reading.
  it("leaves exactly two that do not, and both are HELD with a reason", () => {
    const elsewhere = ACCOUNT_QUICK_ACTION_IDS.filter((id) => !opensOverTheAccount(id));
    // ⚠ **ONE, NOT TWO, SINCE WAVE M.** `sendStatement` left this list when
    // `POST /accounts/{id}/statement` landed: the measurement that wave opened
    // with found that all three parts of a statement already existed and
    // nothing joined them, so the sentence holding it shut — *"nothing renders
    // a statement"* — was never true of the ledger half and had been false
    // since 2026-08-11. `adjust` stays: billing still publishes no adjustment
    // writer, which is a capability absence and not a stale sentence.
    expect(elsewhere).toEqual(["adjust"]);
    for (const id of elsewhere) {
      // A dialog over a control that cannot act would open onto nothing —
      // hard-won law 2.
      expect(quickActionFor(id)!.destination.kind).toBe("held");
    }
  });

  it("opens twelve of the thirteen over the account", () => {
    expect(ACCOUNT_QUICK_ACTION_IDS.filter(opensOverTheAccount)).toHaveLength(12);
  });

  it("mounts exactly the eight the ruling names, and no form is re-typed", () => {
    const mounted = ACCOUNT_QUICK_ACTIONS.filter((a) => a.destination.kind === "mounted");
    expect(mounted.map((a) => a.id)).toEqual([
      "moveOut", "moveIn", "closeOut", "printBill",
      "issueCredit", "changePlan", "disconnectNotice", "paymentPlan",
    ]);
  });

  it("every mounted action names an overlay the container actually declares", () => {
    // ⚠ BY NAME, NOT BY COUNT. A `mounted` entry pointing at an overlay nobody
    // declares is a control that opens a blank dialog, and every other check
    // here would pass over it.
    const declared = new Set(ACCOUNT_ACTION_OVERLAYS.map((overlay) => overlay.id));
    for (const action of ACCOUNT_QUICK_ACTIONS) {
      if (action.destination.kind === "mounted") {
        expect(declared.has(action.destination.overlay), `${action.id} names a declared overlay`).toBe(
          true,
        );
      }
    }
    // …and the other way: an overlay nobody reaches is dead UI.
    const reached = new Set(
      ACCOUNT_QUICK_ACTIONS.flatMap((a) =>
        a.destination.kind === "mounted" ? [a.destination.overlay] : [],
      ),
    );
    expect([...declared].filter((id) => !reached.has(id))).toEqual([]);
  });

  it("no destination is a bare route any more", () => {
    // The variant is gone from the type; this asserts the DATA, because a union
    // member can be deleted and a stray object literal still carry the string.
    const kinds = new Set(ACCOUNT_QUICK_ACTIONS.map((a) => a.destination.kind));
    expect([...kinds].sort()).toEqual(["form", "held", "modal", "mounted"]);
  });
});

describe("the actions that open no form", () => {
  it("adjust is HELD, because billing publishes no adjustment writer", () => {
    const action = quickActionFor("adjust")!;
    expect(action.destination.kind).toBe("held");
    expect(quickFormFor("adjust")).toBeNull();
  });

  it("sendStatement opens a FORM now — it asks for a period and nothing else", () => {
    // ⚠ **THIS CASE USED TO READ *"sendStatement is HELD, because nothing
    // renders a statement"* AND IT WAS A TEST OF A SENTENCE RATHER THAN OF A
    // FACT.** A statement needs three things — wording, a period's activity,
    // and a queue — and every one of them was already in the repo; only the
    // joining was missing (hard-won law 2). The server half is
    // `apps/billing/statement.py`.
    const action = quickActionFor("sendStatement")!;
    expect(action.destination.kind).toBe("form");

    const form = quickFormFor("sendStatement")!;
    // The PERIOD is the only thing it collects, because it is the only thing a
    // statement needs that the books do not already know (`BR-TEN-043` — the
    // server keeps no default and reads no clock).
    const fields = form.sections.flatMap((section) => section.fields);
    expect(fields.map((f) => f.id)).toEqual(["from", "to"]);
    expect(fields.every((f) => f.kind === "date" && f.required === true)).toBe(true);

    // It can commit: the endpoint is served (`BR-SHL-025`).
    expect(form.commitBlockedKey).toBeUndefined();

    // ⚠ **THE CAVEATS ARE PART OF THE CONTRACT, NOT DECORATION.** The printed
    // copy has no wording on any deployment (`DEF-BIL-5133`), and a statement
    // is NOT a bill — A19 rule 1: *"both the printed statement and the
    // statement email must say nothing is due, or customers pay twice."*
    // `DEF-NOT-10537` (2026-10-22): the third, *"Nothing is sent this
    // release."*, is retired — the statement's email row sends now.
    expect(form.caveatBulletKeys).toHaveLength(2);
    expect(form.caveatBulletKeys).toContain("customers.account.quick.statement.notABill");
    expect(form.caveatBulletKeys).not.toContain("customers.account.quick.statement.noSending");
  });

  it("the statement recap reads back the clerk's own two dates", () => {
    // Both rows name a `fromField` and NEITHER names a `source`: there is no
    // server-side fact behind a period a clerk is still typing. Before wave M
    // a row like this had to name a source anyway, which meant writing a label
    // that was simply untrue in the file a reader consults to find out where a
    // value comes from.
    const form = quickFormFor("sendStatement")!;
    expect(form.recapRows.map((row) => row.fromField)).toEqual(["from", "to"]);
    expect(form.recapRows.every((row) => row.source === undefined)).toBe(true);
  });

  it("the other eleven keep a destination rather than being dropped", () => {
    const undeclared = ACCOUNT_QUICK_ACTION_IDS.filter((id) => quickActionFor(id) === undefined);
    expect(undeclared).toEqual([]);
  });
});
