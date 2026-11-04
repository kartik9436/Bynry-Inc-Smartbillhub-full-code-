// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.10` — "**Credit joins it**", from §03 frame 6·1
//           of `05-prototype/06 Payments Page Blueprint.pdf` read as images at
//           2.0. The drawing's Primary-action row: *"**Raise refund**, with
//           **Issue credit** beside it — so the cheaper option is visible at the
//           moment the choice is made."*
// Ruling:   PO 2026-09-22, verbatim: *"we can not have two path for 1
//           capabilities wew will confuse user."*
// Screens:  6·1 Refunds (S58 · PAY-P)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE STRUCTURAL ASSERTION: THIS IS A DOOR, AND IT MUST STAY ONE
// ══════════════════════════════════════════════════════════════════════════
// `P4.12` built `GET /accounts/{id}/credit-path` as a SIGNPOST and its backend
// carries a structural test asserting payments' route table mints no write verb
// for it. This is that guarantee's front half: the button hands over to
// billing's own address and posts nothing itself.
//
// **A "convenience" `POST /corrections` from a payments screen would be the
// second implementation the PO's ruling forbids** — and it would arrive one
// field at a time, which is how it would get past review.
import "@testing-library/jest-dom/vitest";

import { describe, expect, it } from "vitest";

import "@/i18n";

import { issueCreditPath } from "./IssueCreditDoor";
// ⚠ **READ THROUGH VITE'S OWN `?raw`, NOT `node:fs`** — the idiom
// `ShellWithSession`, `DataTable` and `ConfirmDialogTier` already use. This
// app's `src` tsconfig carries no node types, so `node:fs` is a red typecheck
// and `?raw` is the one that compiles; it is also the only form that survives
// the browser-shaped test environment.
import DOOR_SOURCE from "./IssueCreditDoor.tsx?raw";

describe("P4.10 — Issue credit is a DOOR to the one credit path", () => {
  it("hands over to billing's own address, carrying the bill", () => {
    // `FixABillTab` reads `?bill=`; `App.tsx`'s own comment says this route
    // *"hands it the same query the billing address does"*.
    expect(issueCreditPath("acct-1", "inv-9")).toBe(
      "/accounts/acct-1/issue-credit?bill=inv-9",
    );
  });

  it("escapes both segments, so an id can never break the address", () => {
    expect(issueCreditPath("a/b", "c?d=e")).toBe(
      "/accounts/a%2Fb/issue-credit?bill=c%3Fd%3De",
    );
  });

  it("the component posts NOTHING \u2014 no write verb is minted in payments", () => {
    // \u26a0 **A SOURCE-LEVEL ASSERTION, AND IT HAS TO BE.** This is a claim about
    // what the file does NOT do, and no rendered output can show an absence \u2014
    // the `G32` shape: a check that reports zero over a scope it cannot see.
    // Reading the file is the only thing that can actually fail here.
    //
    // **If this goes red, read the PO's ruling in the header before "fixing"
    // it.** One credit path, reachable from two places; a `POST` from this file
    // would be the second implementation, and it would arrive one field at a
    // time.
    // ⚠ **COMMENTS ARE STRIPPED FIRST, AND THAT IS NOT A WEAKENING.** The
    // component's own prose NAMES `POST /corrections` — that is the sentence
    // explaining where the write lives and why it is not here. Asserting over
    // the comments would fail on the documentation that justifies the rule,
    // which teaches the next lane to delete the explanation. The claim is about
    // CODE, so the check reads code.
    const source = DOOR_SOURCE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    // Proved capable of failing: adding `client.post("/corrections", …)` to the
    // component reddens all three of these.
    expect(source).not.toMatch(/\.post\s*[(<]/);
    expect(source).not.toMatch(/\.patch\s*[(<]/);
    expect(source).not.toContain("/corrections");
  });
});
