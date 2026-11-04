// ── Trace ──────────────────────────────────────────────
// Defects: DEF-PAY-6328 (a raw dotted key rendered at a clerk)
//          DEF-PAY-6327 (the deleted rationale must not come back as a key)
// Rules:   B14 rule 33 (rationale is ZERO words on screen) · B14 rule 43 (one component)
// ───────────────────────────────────────────────────────
//
// **THIS IS THE HALF A CATALOGUE CHECK CANNOT MAKE, AND IT IS THE HALF THAT
// CAUGHT THE REAL HARM.** `problemWords.rule33.test.ts` counts words in the
// eleven catalogues; every assertion it makes is about a string that EXISTS.
// The fault in `DEF-PAY-6328` is a string that does not: `i18n` is configured
// `keySeparator: false`, so `t()` on a missing key returns the KEY, and a clerk
// recording a payment read the literal text `payments.problem.receipt_queued`.
// There is nothing there to count.
//
// So these assertions read what `ProblemList` RENDERS, against codes chosen to
// be exactly the three cases that exist:
//
//   * a code with words          → the words, and never the key
//   * a code deleted on purpose  → nothing at all (rule 33's zero)
//   * a code with no key at all  → nothing at all, never a dotted key
//
// ⚠ **PROVED RED FIRST**, in the harness that runs it. Against `ProblemList` as
// it stood before this commit, the third case rendered
// `<li>payments.problem.receipt_queued</li>` and the second rendered the
// rationale sentence the Product Owner asked us to delete.
import { cleanup } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { PROBLEM_CODES_DELETED_ON_PURPOSE, ProblemList, problemWords } from "./paymentsShared";

afterEach(cleanup);

/** The shape the server sends. `br_ref` rides along and is never rendered. */
const problem = (code: string) => ({ code, br_ref: "BR-PAY-000", detail: "server English" });

describe("DEF-PAY-6328 — ProblemList renders words or nothing, never a key", () => {
  it("renders the words for a code the catalogue knows", () => {
    const html = renderToStaticMarkup(
      <ProblemList problems={[problem("nsf_fee_not_added")]} title="What is missing" />,
    );
    expect(html).toContain("Billing adds that charge.");
    expect(html).not.toContain("payments.problem.");
  });

  it("renders NOTHING for a code with no catalogue key — DEF-PAY-6328's own case", () => {
    // `receipt_queued` rides `problems` on every recorded payment behind an
    // election that is DEFAULT ON, and no catalogue has ever had a key for it.
    const html = renderToStaticMarkup(
      <ProblemList problems={[problem("receipt_queued")]} title="What is missing" />,
    );
    expect(html).toBe("");
  });

  it("renders NOTHING for a code whose sentence was deleted on purpose", () => {
    for (const code of PROBLEM_CODES_DELETED_ON_PURPOSE) {
      const html = renderToStaticMarkup(
        <ProblemList problems={[problem(code)]} title="What is missing" />,
      );
      expect(html, `${code} still renders something`).toBe("");
    }
  });

  it("drops only the wordless codes and keeps the panel for the rest", () => {
    const html = renderToStaticMarkup(
      <ProblemList
        problems={[
          problem("dso_not_computed_here"),
          problem("receipt_queued"),
          problem("nsf_count_not_incremented"),
        ]}
        title="What is missing"
      />,
    );
    expect(html).toContain("The bounce count did not move.");
    expect(html).not.toContain("payments.problem.");
    expect(html).not.toContain("Finance owns this formula");
    // One bullet survived of three.
    expect(html.match(/<li/gu)?.length).toBe(1);
  });

  it("no rendered bullet ever carries a dotted key, across the whole live family", () => {
    // The sweep, rather than three chosen codes: every key the catalogue holds,
    // plus every code this lane deleted, plus the unkeyed one. A dotted key in
    // ANY of them is the defect.
    const codes = Object.keys(i18n.getResourceBundle("en", "translation") as Record<string, string>)
      .filter((key) => key.startsWith("payments.problem."))
      .map((key) => key.slice("payments.problem.".length))
      .concat(PROBLEM_CODES_DELETED_ON_PURPOSE, ["receipt_queued", "receipt_election_off"]);
    expect(codes.length).toBeGreaterThan(30);
    const html = renderToStaticMarkup(
      <ProblemList problems={codes.map(problem)} title="What is missing" />,
    );
    expect(html).not.toContain("payments.problem.");
    expect(html).not.toContain("BR-PAY-000");
    expect(html).not.toContain("server English");
  });
});

describe("DEF-PAY-6328 — `problemWords` is the one answer, and it says no out loud", () => {
  it("returns null rather than a key when i18next hands back the key", () => {
    // A `t` that behaves the way this product's i18next actually behaves on a
    // missing key: it returns the key unless a defaultValue is supplied. A fake
    // that returned "" instead would make this test pass for the wrong reason —
    // the false pass this check exists to refuse.
    const t = (key: string, params?: Record<string, unknown>) =>
      (params?.defaultValue as string | undefined) ?? key;
    expect(problemWords(t, "a_code_nobody_worded")).toBeNull();
    expect(problemWords(t, "dso_not_computed_here")).toBeNull();
  });
});
