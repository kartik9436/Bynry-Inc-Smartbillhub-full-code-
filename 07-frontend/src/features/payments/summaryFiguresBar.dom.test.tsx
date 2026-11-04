// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   `DEF-PAY-6335` — PO, walking S32 on 2026-09-23: *"these detailsa re
//           not aligned on ui - Figures for*"*.
// Rules:    B14 rule 33 (on-screen text is capped by what it is FOR) · B14 rule
//           43 (a piece of UI is a COMPONENT) · BR-TEN-043 (`as_of` is typed,
//           never taken from a clock) · BR-PAY-015 (the autopay count carries
//           NO action) · US-PAY-016 (the returned-post count carries one) ·
//           IS-8 / CR-043 finding 15 (the tenant's date format under the input)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS FILE CANNOT SEE, STATED FIRST SO NOBODY MISTAKES IT FOR THE
// PROOF.** The defect is GEOMETRIC — the counters sat 46px below the input.
// jsdom computes no layout, so every assertion here would have passed at the
// broken commit, exactly as `SummaryTab.test.tsx` did for three weeks. The
// instrument that measures the band is
// `10-scripts/render-checks/def-pay-6335-summary-band.mjs`, and it carries a
// `--before` mode that MUST fail.
//
// What a source check CAN decide is here and nowhere else: the date is not
// rendered twice, the counters carry their figures, only one of them carries an
// action, and every string measures inside B14 rule 33's cap. Those are real
// and they are not the alignment.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { SummaryFiguresBar } from "./summaryFiguresBar";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);
const AS_OF = "2026-09-23";

function bar(over: Partial<Parameters<typeof SummaryFiguresBar>[0]> = {}) {
  return render(
    <SummaryFiguresBar
      asOf={AS_OF}
      onAsOfChange={() => undefined}
      // The tenant the PO was looking at. `DD-MMM-YY` is what makes the IS-8
      // echo render at all: `regionalDateEcho` returns null when the tenant's
      // format and the browser's own rendering would read the same.
      dateFormat="DD-MMM-YY"
      chips={{ autopay_scheduled: 3, returned_mail: 5 }}
      onMarkReturnedPost={() => undefined}
      {...over}
    />,
  );
}

describe("DEF-PAY-6335 — S32's `Figures for` band", () => {
  it("BR-TEN-043: the business day is a date input holding the day the page asked for", () => {
    bar();
    const input = document.querySelector<HTMLInputElement>("#summary_as_of");
    expect(input).not.toBeNull();
    expect(input?.type).toBe("date");
    expect(input?.value).toBe(AS_OF);
    // ⚠ `aria-required` AND NOT THE `required` ATTRIBUTE, WHICH IS THE KIT'S
    // CHOICE AND NOT AN OVERSIGHT. `DatePickerField` marks the field visibly
    // with BR-SHL-017's accent asterisk and carries the fact to AT through
    // `aria-required`; a native `required` would additionally recruit the
    // browser's own validation bubble, which this product does not use. A first
    // draft of this case asserted `input.required` and went red against correct
    // code — a test asserting something the component never claimed.
    expect(input?.getAttribute("aria-required")).toBe("true");
    expect(document.querySelector(".field-required")).toHaveTextContent("*");
  });

  it("the date is on screen ONCE as a value and once as the TENANT's format — not twice", () => {
    // ⚠ THE PO READ `09/23/2026` AND `23-Sep-26` AS ONE FACT SAID TWICE. They
    // are not: the native control renders in the BROWSER's locale and the echo
    // is the only place the tenant's own format ever reaches this screen
    // (CR-043 finding 15). What must hold is that the echo is a DIFFERENT
    // rendering and that there is exactly one of it.
    const { container } = bar();
    const echoes = container.querySelectorAll(".field-date-display");
    expect(echoes).toHaveLength(1);
    expect(echoes[0]).toHaveTextContent("23-Sep-26");
    // The control's own value is the ISO calendar date, never a second copy of
    // the echo's characters.
    expect(container.textContent).not.toContain("09/23/2026");
  });

  it("the echo is the FIELD's, so it lives inside the field rather than loose in the band", () => {
    // What made it read as a stray date was where it sat, not that it existed.
    // jsdom cannot measure that; it can prove the parentage, which is the half
    // that keeps a later lane from lifting it out again.
    const { container } = bar();
    const field = container.querySelector(".field");
    expect(field?.querySelector(".field-date-display")).not.toBeNull();
    expect(field?.querySelector("#summary_as_of")).not.toBeNull();
  });

  it("a tenant whose format the browser already renders gets NO echo (regionalDateEcho)", () => {
    // The other half of the same rule, and the one that stops this line being
    // a duplicate for most tenants. `MM/DD/YYYY` is what the test browser
    // renders anyway, so there is nothing for the echo to add.
    const { container } = bar({ dateFormat: "MM/DD/YYYY" });
    expect(container.querySelectorAll(".field-date-display")).toHaveLength(0);
  });

  it("both counters reach the screen carrying their figures", () => {
    const { container } = bar();
    const autopay = container.querySelector<HTMLElement>('[data-counter="autopay"]');
    const returned = container.querySelector<HTMLElement>('[data-counter="returned-mail"]');
    expect(autopay).not.toBeNull();
    expect(returned).not.toBeNull();
    expect(autopay?.querySelector("[data-counter-value]")).toHaveTextContent("3");
    expect(returned?.querySelector("[data-counter-value]")).toHaveTextContent("5");
    expect(autopay).toHaveTextContent(t("payments.summary.chip.autopay"));
    expect(returned).toHaveTextContent(t("payments.summary.chip.returnedMail"));
  });

  it("US-PAY-016: the returned-post count carries the action that clears it — and autopay does not", () => {
    // Hard-won law 2 in both directions. The returned-post queue counted a
    // chore nobody could do for five days; the autopay count must NOT acquire
    // an action, because BR-PAY-015 says v1 has no charging path and a button
    // there would be one wearing a retry's clothes.
    const { container } = bar();
    const returned = within(container.querySelector<HTMLElement>('[data-counter="returned-mail"]')!);
    expect(returned.getByRole("button", { name: t("payments.returnedMail.bulk.open") })).toBeVisible();
    const autopay = within(container.querySelector<HTMLElement>('[data-counter="autopay"]')!);
    expect(autopay.queryByRole("button")).toBeNull();
  });

  it("no counts yet: the field still draws and the counters do not", () => {
    // `chips: null` is the read not having answered. A counter rendering `0`
    // there would be the screen stating a figure the server has not — the same
    // rule that keeps `today.average` null rather than $0.00.
    const { container } = bar({ chips: null });
    expect(container.querySelector("#summary_as_of")).not.toBeNull();
    expect(container.querySelectorAll("[data-counter]")).toHaveLength(0);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("B14 rule 33: every string in the band is inside the cap for what it IS", () => {
    // ⚠ MEASURED, NOT ASSUMED — which is the point of the rule and the reason
    // this case counts words rather than eyeballing them. A LABEL is <= 3 words
    // and carries no sentence; a FACT is <= 6 words.
    const words = (text: string) => text.replace(/[.*]/g, "").trim().split(/\s+/).length;
    for (const key of [
      "payments.summary.asOf",
      "payments.summary.chip.autopay",
      "payments.summary.chip.returnedMail",
      "payments.returnedMail.bulk.open",
    ]) {
      expect({ key, words: words(t(key)) }).toEqual({ key, words: expect.any(Number) });
      expect(words(t(key)), `${key}: "${t(key)}"`).toBeLessThanOrEqual(3);
    }
    const help = t("payments.summary.asOfHelp");
    expect(words(help), `asOfHelp: "${help}"`).toBeLessThanOrEqual(6);
    // ...and it is ONE sentence. Rule 33 caps an instruction PER SENTENCE, so a
    // help line that grew a second clause would pass a word count and still be
    // the thing the rule forbids.
    expect(help.replace(/\.$/, "")).not.toContain(".");
  });

  it("B14 rule 33: the band states no RATIONALE — zero words about why", () => {
    // The old `CorrectionRetentionNote` is the cautionary case: a caveat
    // rendered on screen in eleven catalogues because a change-request row told
    // a lane to build it. Rationale is removed, never shortened.
    const { container } = bar();
    const text = (container.textContent ?? "").toLowerCase();
    for (const tell of ["because", "so that", "this is why", "in order to"]) {
      expect(text, `the band explains itself on screen: "${tell}"`).not.toContain(tell);
    }
  });
});
