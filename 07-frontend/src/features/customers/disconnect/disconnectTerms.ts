// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 — the read behind step
//           4's `Fees` table and its `The deposit` ladder (`DEF-CUS-6752`,
//           `DEF-CUS-6753`).
// Rules:    **BR-BIL-007** (NSF/reconnect fees are tenant-configured charge
//           codes, NEVER hardcoded) · **BR-CUS-104** (the fee lands AT THE CUT
//           — its TIMING clause, which `BR-CUS-1097` did NOT touch) ·
//           **B14 rule 37** (a figure drawn in a wireframe is an ILLUSTRATION,
//           never a fact to build to) · hard rule 2 · hard rule 5
// Tests:    ../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHY THIS FILE EXISTS BESIDE `transferDisconnectEndpoints.getReconnectionTerms`
// ══════════════════════════════════════════════════════════════════════════
// **THEY ARE THE SAME ROUTE AND THE SHARED TYPE IS OLDER THAN THE PAYLOAD.**
// `disconnects.reconnection_terms` grew two keys on 2026-09-20 under
// `CR-125-BRC07` — `fees` (blueprint p139's three-row table) and `to_clear`
// (its reconnection figure) — and `ReconnectionTerms` in
// `transferDisconnectEndpoints.ts` still declares neither. Step 4 needs both.
//
// ⚠ **THE HONEST TRADE, WRITTEN DOWN RATHER THAN DISCOVERED BY THE NEXT
// READER.** Two optional keys added to that shared interface would be strictly
// tidier, and `transferDisconnectEndpoints.ts` is a file lane RECONNECT is
// working in TODAY — `getReconnectionTerms` is the read the reconnect panel is
// built on. In this tree a pathspec commit takes the WHOLE file, so the second
// lane to commit silently reverts the first with a correct file count and a
// clean diff (CLAUDE.md law 11, mechanism two). **A duplicated type is a cost
// somebody can see; a reverted sibling is not.**
//
// **SO THIS IS OWED AND IS NAMED:** when the two lanes have landed, fold these
// two interfaces into `ReconnectionTerms` and delete this module's own
// declarations, keeping `getDisconnectTerms` as the one caller. It is one
// import line at this call site.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

import type { WorklistMoney } from "../worklistEndpoints";

/** The server's absence block — a CODE, a rule reference and the server's own
 *  sentence. ⚠ **`detail` NEVER REACHES A SCREEN** (B14 rules 31 and 32: no
 *  rule id, no internal code in clerk-facing copy). It is read by a person
 *  debugging and by nothing else; the screen owns the words. */
export interface TermsAbsence {
  code: string;
  br_ref?: string;
  detail?: string;
  oq?: string;
}

/**
 * One row of `_fee_table()` — blueprint p139's `CHARGE · CODE · AMOUNT · WHEN ·
 * CHARGED?`, which the rebuild draws as `CHARGE · FROM · AMOUNT · WHEN`.
 *
 * ⚠ **NOT ONE AMOUNT IS A LITERAL ANYWHERE IN THIS FLOW** (`BR-BIL-007`). The
 * drawings price the three fees `$35.00 · $75.00 · $45.00` on the regular
 * variant and `$85.00 · $150.00 · $45.00` on the master, and **every one of
 * those six is an illustration** (B14 rule 37). `amount` is `null` with a
 * reason when the tenant has no such row, which — measured on 2026-09-20 — is
 * all three on every tenant in this tree.
 *
 * ⚠ **`charged_on_this_cut` IS THE COLUMN THAT STOPS THE TABLE LYING.** The cut
 * raises the reconnection fee and nothing else; the other two codes exist as
 * names with no path to a bill. A table listing three amounts with no such flag
 * reads as three fees a customer is about to owe.
 */
export interface DisconnectFeeRow {
  /** The charge code. ⚠ **NEVER RENDERED** — B14 rule 31/32; it is the row key. */
  code: string;
  /** The tenant's OWN name for it, falling back to the design's word. */
  charge: string;
  amount: WorklistMoney | null;
  amount_absence: TermsAbsence | null;
  /** `At the cut` · `Only if a crew attends` — the server's own vocabulary. */
  when: string;
  charged_on_this_cut: boolean;
  charged_absence: TermsAbsence | null;
}

/**
 * `_to_clear()` — what a customer must clear to be reconnected.
 *
 * ⚠ **THERE IS NO DEPOSIT IN THIS SUM AND THERE MUST NOT BE ONE ON THE SCREEN
 * (`DEF-CUS-6753`).** It is `arrears + fee` and nothing else. Applying a
 * deposit against an arrear is a balance-sheet posting, and hard rule 5 leaves
 * every journal line to the ledger posting service — so the product records the
 * ELECTION and moves no money. The drawings put a `Deposit applied − $65.00`
 * row above this total; rendering it would quote a figure nothing computes, two
 * inches from the figure `mark_reconnecting` actually reads.
 *
 * ⚠ **`total` IS `null` UNLESS BOTH HALVES ARE KNOWN, AND THAT IS THE RULE.** A
 * sum over the arrears alone quotes a customer a price short by the whole fee,
 * which is `DEF-708`'s own shape.
 */
export interface DisconnectToClear {
  arrears: WorklistMoney | null;
  arrears_absence: TermsAbsence | null;
  fee: WorklistMoney | null;
  total: WorklistMoney | null;
  total_absence: TermsAbsence | null;
  /** WHICH question the total answered — whether the fee is already inside the
   *  arrears because the cut has happened. Read, never rendered. */
  basis?: TermsAbsence & { fee_in_arrears?: boolean };
}

export interface DisconnectDeposit {
  on_file: WorklistMoney;
  election: string | null;
  /** `true` when nothing is held and a new deposit is needed to reconnect;
   *  `null` when no election is recorded yet. Three-valued on purpose — a
   *  `false` and a `null` are different answers. */
  new_deposit_required: boolean | null;
  detail: string;
  posting: TermsAbsence;
}

/** The whole of `disconnects.reconnection_terms`. */
export interface DisconnectTerms {
  account_id: string;
  charge_code: string;
  fee: WorklistMoney | null;
  fee_absence: TermsAbsence | null;
  fees: DisconnectFeeRow[];
  to_clear: DisconnectToClear;
  deposit: DisconnectDeposit;
  posting: TermsAbsence;
  timing: TermsAbsence;
}

/**
 * `GET /accounts/{id}/reconnection-terms`.
 *
 * ✅ MOUNTED; measured 200 on 2026-09-12 (`DEF-CUS-5076`). ⚠ **IT IS A READ AND
 * NOT A POSTING** — nothing here writes a journal line, raises a charge or
 * touches AR (hard rule 5, `BR-CUS-037`).
 *
 * ⚠ **IT DOES NOT KNOW THE ACCOUNT'S PLAN OR ITS CATEGORY (`DEF-CUS-6752`).**
 * Every row is `_charge_code(code)` against the TENANT's one catalogue, so a
 * residential and a commercial account are quoted the same figure and the read
 * has no `FROM` to serve. Step 4 therefore names the account's own plan and
 * category **as a fact about the account**, beside the panel, and never as the
 * provenance of a figure that plan did not price. The backend half is lane
 * CUTPATH's.
 */
/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported, for the reason `transferDisconnectEndpoints.ts`
 *  and `newConnectEndpoints.ts` both give: no coupling between two files
 *  different lanes hold. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export async function getDisconnectTerms(
  accountId: string,
  client: ApiClient = api,
): Promise<DisconnectTerms> {
  return requireData(
    await client.get<DisconnectTerms>(
      `/accounts/${encodeURIComponent(accountId)}/reconnection-terms`,
    ),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 · `DEF-CUS-6752` ·
//         `DEF-CUS-6753` · BR-BIL-007 · BR-CUS-104 · B14 rules 31, 32, 37 ·
//         hard rules 2 and 5 · 06-backend/apps/customers/disconnects.py
// generated: 2026-09-25 by lane WIZARD
// gates: tsc · vitest src/features/customers/DisconnectWizard.test.tsx
// exceptions:
//   E3 `DisconnectTerms` DUPLICATES `transferDisconnectEndpoints.ReconnectionTerms`
//      over one route, deliberately and temporarily — see §1. Folding them is
//      owed once lane RECONNECT has landed.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
