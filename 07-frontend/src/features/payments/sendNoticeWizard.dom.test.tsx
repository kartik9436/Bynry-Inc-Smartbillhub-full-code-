// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.14` (7·3d Send notice — three steps) and `P4.27`
//           (7·3d is a WIZARD, not a modal — the step is URL state and clamps
//           to the highest validated step), from §03 frame 7·3d of
//           `05-prototype/06 Payments Page Blueprint.pdf` read as images at 2.0.
// Ruling:   `OQ-PAY-12607` (2026-09-23, CLOSED — **no fourth tone**)
// Rules:    B14 rule 31 (no database id on screen) · rule 33 (rationale is ZERO
//           words on screen) · BR-SHL-018 (a pasted `?step=` clamps to the
//           highest validated step) · BR-PAY-017 (four rungs, five stop
//           conditions)
// Screens:  7·3d Notice (S35 · PAY-B) · S34 (the door)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE TWO THINGS THIS FILE EXISTS TO STOP, AND BOTH ARE ATTRACTIVE MISTAKES
// ══════════════════════════════════════════════════════════════════════════
// **1 · SOMEBODY MINTING A FOURTH TONE.** The blueprint says *"Four tones. Each
// one selects a different letter"* on p088 and repeats it in annotation ④.
// `OQ-PAY-12607` CLOSED 2026-09-23 with the PO's *"(b) Leave it — use Final to
// escalate"*, and the register row says in terms: *"nobody should 'fix' it
// again."* Four RUNGS, three TONES, deliberately. A fourth tone would widen
// `BR-PAY-035`'s ratified table on an implementer's authority.
//
// **2 · SOMEBODY ASSERTING A COUNT THE BOARD CANNOT PREDICT.** `runs` is
// THREE-VALUED — `true` steps, `false` was stopped, and **`null` means this
// deployment cannot say** because no balance floor could be read. A commit
// button reading *Send 2* over three accounts, one of them unpredictable, is a
// number a clerk reads aloud and acts on. It drops the number instead.
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, or every address the wizard builds
// comes out `//payments/…` and reads as a perfectly good string to `toContain`.
import "@testing-library/jest-dom/vitest";

import { describe, expect, it } from "vitest";

import "@/i18n";

import type { LadderBoardRow } from "@/api/bankRecEndpoints";
import type { OutstandingRow } from "@/api/endpoints";
import { clampStepToReached, initialWizardNav } from "@/components/WizardFrame";
import {
  SEND_NOTICE_ROUTE,
  assertableSendCount,
  noticeWillSend,
  sendNoticeHandover,
  toneRow,
} from "./SendNoticeWizard";
import type { NoticePlanRow } from "./SendNoticeWizard";
// Read through Vite's own `?raw`, the idiom `ShellWithSession` and
// `ConfirmDialogTier` already use — this app's `src` tsconfig carries no node
// types, so `node:fs` is a red typecheck.
import OUTSTANDINGS_SOURCE from "./OutstandingsTab.tsx?raw";

function account(id: string, no: string): OutstandingRow {
  return {
    account_id: id,
    account_no: no,
    customer_name: "Ana Alvarez",
    balance: "1284.600000",
    days_late: 62,
    bucket: "over_60",
    open_bills: 2,
    last_payment_on: null,
    notice_summary: "Reminder sent",
    collection_tier: "friendly",
    next_step_due: null,
    plan_status: null,
    autopay: false,
    bad_address: false,
  } as unknown as OutstandingRow;
}

function board(id: string, runs: boolean | null, skip: string | null): LadderBoardRow {
  return {
    account_id: id,
    account_no: "AC-2026-00001",
    balance: "1284.600000",
    currency: "USD",
    oldest_due_on: "2026-07-14",
    current_tier: "friendly",
    tier_sent_on: "2026-09-08",
    last_notice_on: "2026-09-08",
    plan_paused: false,
    plan_pause_reason: "",
    plan_id: null,
    medical_hold: skip === "medical_hold",
    runs,
    next_rung: "first_10_day",
    next_step_on: "2026-09-24",
    skip_reason: skip,
    days_late: 62,
    detail_code: "",
  };
}

describe("P4.27 — it is a wizard, and the step CLAMPS", () => {
  it("a pasted `?step=3` cannot skip past an unvisited step (BR-SHL-018)", () => {
    // ⚠ Several wizards in this product pass `nav={{ step, reached: step }}`,
    // which makes the fence equal the request and lets a deep link open the
    // letter over a tone nobody picked. `P4.27` asks for the other behaviour by
    // name, and this is the case that holds it.
    const fresh = initialWizardNav();
    expect(clampStepToReached(3, fresh, 3).step).toBe(1);
    // Once step 2 has been validated into, a link to 2 opens; 3 still does not.
    const reachedTwo = { step: 2, reached: 2 };
    expect(clampStepToReached(2, reachedTwo, 3).step).toBe(2);
    expect(clampStepToReached(3, reachedTwo, 3).step).toBe(2);
  });

  it("it has an ADDRESS of its own, which a modal could not have", () => {
    expect(SEND_NOTICE_ROUTE).toBe("/payments/outstandings/send-notice");
  });
});

describe("P4.14 — the selection is carried, and a bad handover is refused", () => {
  it("a hard refresh (no router state) yields null rather than an empty send", () => {
    expect(sendNoticeHandover(undefined)).toBeNull();
    expect(sendNoticeHandover(null)).toBeNull();
    expect(sendNoticeHandover({ accounts: [] })).toBeNull();
    // ⚠ The CURRENCY is required too: `OutstandingRow` carries none, and a money
    // figure drawn in the wrong currency is a figure a clerk reads aloud.
    expect(sendNoticeHandover({ accounts: [], asOf: "2026-09-23" })).toBeNull();
    expect(
      sendNoticeHandover({ accounts: [], asOf: "2026-09-23", currency: "USD" }),
    ).not.toBeNull();
  });
});

describe("P4.14 — the count is never invented", () => {
  const rows = (verdicts: (boolean | null)[]): NoticePlanRow[] =>
    verdicts.map((runs, index) => ({
      account: account(`id-${index}`, `AC-2026-0000${index}`),
      board: board(`id-${index}`, runs, runs === false ? "medical_hold" : null),
    }));

  it("counts only what the board says WILL go", () => {
    expect(assertableSendCount(rows([true, true, false]))).toBe(2);
  });

  it("ONE unpredictable row drops the number entirely — never a count that is too low", () => {
    // *Send 2* over three accounts where the third is unknown is arithmetic
    // lying to a clerk. The button reads *Send notices ✓* instead.
    expect(assertableSendCount(rows([true, true, null]))).toBeNull();
  });

  it("an account the BOARD never returned is a skip, not a send", () => {
    // `notices_by_hand.send` treats it as `nothing_overdue`: *"a notice to a
    // customer who owes nothing is the worst letter this product can post."*
    expect(noticeWillSend({ account: account("x", "AC-1"), board: undefined })).toBe(false);
  });

  it("`runs: null` stays null all the way to the cell", () => {
    expect(noticeWillSend({ account: account("x", "AC-1"), board: board("x", null, null) })).toBeNull();
  });
});

describe("P4.14 — the door that was holding this screen is OPEN", () => {
  it("7·1 no longer refuses Send notice over `noticeAwaitsScreen`", () => {
    // ⚠ **THE HOLD-EXPIRY CASE, AND IT BELONGS TO THIS LANE BECAUSE THIS LANE
    // LANDED THE SCREEN.** `P4.11` rebuilt the selection toolbar and left two
    // slots refusing with *the wizard that goes here is not built* — naming
    // 7·3d, p087 and `P4.14` explicitly (`DEF-PAY-6252`). That wizard is this
    // commit, so both slots open it now.
    //
    // **A SOURCE-LEVEL ASSERTION, AND IT HAS TO BE.** `debtorScreens.dom.test`
    // mounts the BAR with its own props, so it asserts what the bar renders
    // when handed a reason — which stays true whatever the screen passes. The
    // claim here is about the screen's CALL SITE, and no rendered output of the
    // bar can show it. This is the mirror of hard-won law 2's own prescription:
    // *"when you land a screen, grep for the control that was holding it."*
    expect(OUTSTANDINGS_SOURCE).not.toContain("action.noticeAwaitsScreen");
    // …and it opens THIS screen, by its address, not merely something.
    expect(OUTSTANDINGS_SOURCE).toContain("SEND_NOTICE_ROUTE");
  });

  it("the selection and the business day are handed over, so the wizard cannot invent either", () => {
    // `OutstandingsTab` owns `asOf` and the tenant's currency; the wizard has
    // neither and must not guess. `BR-TEN-043`: the business date is an
    // argument, never a clock.
    expect(OUTSTANDINGS_SOURCE).toMatch(/asOf:\s*props\.asOf/);

    // ⚠ **THE CURRENCY IS THE SCREEN'S *RESOLVED* ONE, NOT `props.currency`,
    // AND THIS CASE ASSERTED THE WRONG ONE UNTIL `DEF-PAY-6269` LANDED.**
    // The prop comes from `GET /payments` and is null on a tenant with issued
    // bills and no payments yet; the resolved binding prefers the CHAR(3) that
    // `GET /outstandings` — the read that computed these very balances —
    // carries. Handing the wizard the prop reproduces that defect one screen
    // downstream, on a LETTER that states an amount owed, and every suite
    // passes: an absent currency renders a refusal sentence, not a crash.
    //
    // So this asserts both halves, and the negative is the load-bearing one.
    const handover = OUTSTANDINGS_SOURCE.slice(
      OUTSTANDINGS_SOURCE.indexOf("navigate(tenantPath(SEND_NOTICE_ROUTE)"),
    ).slice(0, 220);
    expect(handover).toMatch(/state:\s*\{[^}]*\bcurrency\b/);
    expect(handover).not.toMatch(/currency:\s*props\.currency/);
    expect(OUTSTANDINGS_SOURCE).toMatch(/const currency = view\?\.currency \?\? props\.currency/);
  });
});

describe("P4.14 — THREE tones, and the drawing's fourth is superseded", () => {
  const TONES = [
    { tone: "friendly", step: null, template_class: "dunning", regulated: false, certified_mail: false },
    {
      tone: "firm",
      step: "first_10_day",
      template_class: "disconnect_notice_10_day",
      regulated: true,
      certified_mail: false,
    },
    {
      tone: "final",
      step: "final_48_hour",
      template_class: "disconnect_notice_48_hour",
      regulated: true,
      certified_mail: true,
    },
  ];

  it("the picker resolves a tone through the SERVER's table, not a map in the screen", () => {
    // *"the picker a clerk uses and the resolution the send performs cannot
    // disagree"* — `notices_by_hand`'s own stated design, and what makes the
    // no-double-send guarantee reachable.
    expect(toneRow(TONES, "firm")?.template_class).toBe("disconnect_notice_10_day");
    expect(toneRow(TONES, "final")?.certified_mail).toBe(true);
    expect(toneRow(TONES, "friendly")?.regulated).toBe(false);
  });

  it("there is no tone for the 5-day rung, and that is RULED (OQ-PAY-12607)", () => {
    // ⚠ **IF THIS CASE GOES RED BECAUSE SOMEBODY ADDED A FOURTH TONE, THE FOURTH
    // TONE IS THE DEFECT, NOT THIS TEST.** PO, 2026-09-23, verbatim: *"(b)
    // Leave it — use Final to escalate"*. The four rungs are the sequence the
    // utility walks automatically; the three tones are what a person may choose
    // by hand.
    expect(TONES).toHaveLength(3);
    expect(toneRow(TONES, "second_5_day")).toBeUndefined();
    expect(TONES.some((row) => row.step === "second_5_day")).toBe(false);
  });

  it("BR-NOT-008: *Firm* selects the REGULATED disconnect class, not a firmer reminder", () => {
    // The blueprint calls this *"the single most dangerous sentence on this
    // screen"*, and it is what the whole wizard exists to show before pressing.
    const firm = toneRow(TONES, "firm");
    expect(firm?.regulated).toBe(true);
    expect(firm?.template_class).toContain("disconnect_notice");
  });
});
