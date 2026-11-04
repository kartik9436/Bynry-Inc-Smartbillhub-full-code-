/* ══════════════════════════════════════════════════════════════════════════
 * THE TEST THAT FIRES WHEN A HOLD EXPIRES — CLAUDE.md hard-won law 2
 * ══════════════════════════════════════════════════════════════════════════
 *
 * Change: `DEF-CUS-4631`, 2026-09-07. PO: *"in account - view we have all those
 * icons - can you activate them now"*, then *"activate all of them"*.
 *
 * ⚠ **WHY THIS FILE EXISTS, AND IT IS NOT BECAUSE A TEST WAS MISSING — IT IS
 * BECAUSE THE TESTS THAT EXISTED WERE HOLDING THE DEFECT IN PLACE.**
 *
 * The S21 icon rail drew four disabled glyphs. Three of them refused on work
 * that had since been finished — two of them on OPEN QUESTIONS THAT HAD BEEN
 * CLOSED BY THE PRODUCT OWNER ON 2026-08-12, three weeks earlier:
 *
 *   🖨 Print bill       `OQ-103` + `OQ-169` — CLOSED. A later reprint renders
 *                       THE CORRECTED instance; reissues accumulate. And
 *                       `GET /invoices/{id}/document` was mounted the whole
 *                       time.
 *   $ Issue credit      `OQ-105` + `OQ-168` — CLOSED. *"a separate write-off
 *                       account"*; `execute_credit_only` posts DR write-off /
 *                       CR customer credit balance.
 *   ⚡ Disconnect notice `OQ-133` + `OQ-136` + `OQ-137` — all CLOSED, and both
 *                       of its structural blockers had been built:
 *                       `NoticeHistory` is the table, `medical_hold_for` is
 *                       the flag.
 *
 * **Every check in the repository passed over all three.** `tsc`, eslint, 42
 * suites, every gate. Worse: two test files asserted the false sentences WORD
 * FOR WORD, so the product and its tests agreed with each other and neither
 * agreed with the register. The PO found it by looking at the screen — the
 * fourth rotted refusal found that way in one day.
 *
 * **The mechanism is a rule with a clock in it.** A hold is written honestly
 * on the day it is true, and landing the thing it waits for and releasing the
 * control are two acts — only the first feels like the work. CLAUDE.md law 2
 * names the cure exactly: *"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES
 * WHEN THE HOLD EXPIRES, in the same commit"*. That was not done for any of
 * these four. This file is that test, written now for the ONE hold that
 * remains, so the fifth occurrence is a red suite instead of a photograph.
 *
 * ⚠ **A FAILURE HERE IS GOOD NEWS AND THE MESSAGE SAYS SO.** It does not mean
 * something broke; it means a hold came true and a control is now refusing for
 * no reason. The fix is never to loosen the assertion — it is to release the
 * glyph and delete the case.
 * ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from "vitest";

import { UNAVAILABLE_ACTIONS } from "./AccountActions";
import { ACCOUNT_RAIL_ACTION_IDS } from "./AccountIconRail";
import { disconnectWizardPathFor } from "./transferDisconnectShared";
import { billDocumentPath, fixABillPath } from "@/features/billing/billingOpsShared";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const CUSTOMERS = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.dirname(nodePath.dirname(CUSTOMERS));
const ENDPOINTS = nodePath.join(SRC, "api", "endpoints.ts");

describe("DEF-CUS-4631 — the account rail's holds, and the day each one lapses", () => {
  it("✉ SEND STATEMENT is still held, and this fails the day a statement renderer lands", () => {
    // ── WHAT MAKES THIS HOLD TRUE TODAY ───────────────────────────────────
    // A statement is a dated RANGE LEDGER over a period, carrying the
    // "nothing is due" note — BR-CUS-040 and A19 rule 1, a genuinely different
    // document from a bill. `apps/billing/documents.py` renders INVOICES and
    // nothing else, and the account-ledger derived view a statement would read
    // does not exist. So no per-account fact can derive this refusal the way
    // Print bill's and Issue credit's are derived: it is a CAPABILITY absence,
    // and the screen cannot discover it by asking about the account.
    //
    // ⚠ `GET /reports/customer-statement` IS NOT IT and must not be mistaken
    // for it. That is a cross-account BALANCE SUMMARY for one customer
    // (CR-060 C16) — no date range, no ledger lines, no disclaimer. Pointing
    // the ✉ glyph at it would ship a control that produces the WRONG document,
    // which is worse than one that refuses. The client function below is
    // deliberately excluded by name for that reason.
    const endpoints = nodeFs.readFileSync(ENDPOINTS, "utf8");
    const statementReaders = [...endpoints.matchAll(/export async function (\w*[Ss]tatement\w*)/g)]
      .map((match) => match[1])
      .filter((name) => !/bank/i.test(name)) // payments' bank-statement IMPORT — a different subject
      .filter((name) => !/customerStatement/i.test(name)); // the balance summary above

    expect(
      statementReaders,
      "A statement endpoint has appeared in endpoints.ts. THAT IS GOOD NEWS — it " +
        "means the hold on the ✉ Send statement glyph has expired. Release it in " +
        "accountRailReadiness.ts (wire `sendStatement.onClick` and drop its " +
        "reason), remove `sendStatement` from UNAVAILABLE_ACTIONS, retire " +
        "customers.account.action.sendStatementBlocked from the eleven " +
        "catalogues, and delete this case. Do NOT relax this assertion.",
    ).toEqual([]);

    // The hold is real while it holds: exactly one rail action refuses.
    expect(UNAVAILABLE_ACTIONS.map((action) => action.id)).toContain("sendStatement");
  });

  it("the three released glyphs point at REAL addresses, asserted by address", () => {
    // Law 2's own words: *"assert the destination by ADDRESS and by the screen
    // id it opens, so the day the screen lands the suite goes red and names
    // it"*. The inverse matters just as much — a control released onto an
    // address nobody serves is the same defect wearing the other face, and the
    // portal front page shipped exactly that (`//portal/…`) because its
    // fixture could not tell a working link from a broken one.
    expect(billDocumentPath("inv-1")).toBe("/billing/bills/inv-1/document");
    expect(fixABillPath("inv-1")).toBe("/billing/fix?bill=inv-1");
    expect(disconnectWizardPathFor("acc-1")).toBe("/disconnects/new?account=acc-1");
    // An id with URL-significant characters must survive the trip.
    expect(disconnectWizardPathFor("a/c 1")).toBe("/disconnects/new?account=a%2Fc%201");
    // A caller with nothing to prefill gets the plain route, never `?account=`.
    expect(disconnectWizardPathFor("  ")).toBe("/disconnects/new");
  });

  it("the rail is EIGHT and the released three are still on it", () => {
    // The failure this guards is the tempting one: "activate them" answered by
    // quietly removing the glyph that would not activate. All of them stay.
    // ⚠ EIGHT since `300a51d33` (2026-09-12, `CR-094-BRC01` wave K, `ACC-S16`):
    // *communication*, the door onto the customer, drawn FIRST. `DEF-CUS-9107`.
    expect(ACCOUNT_RAIL_ACTION_IDS).toHaveLength(8);
    for (const id of ["communication", "printBill", "issueCredit", "disconnectNotice", "sendStatement"]) {
      expect(ACCOUNT_RAIL_ACTION_IDS as readonly string[]).toContain(id);
    }
  });
});
