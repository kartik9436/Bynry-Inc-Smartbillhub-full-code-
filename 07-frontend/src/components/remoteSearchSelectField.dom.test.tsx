// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-6319 — Product Owner on the Raise-a-refund form, 2026-09-23:
//          *"why to button - why cannot we have dropdown search drectly for
//          this - user has to do two clicks"*, then *"fix it"*.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT) · B14 rule 36 (the kit) ·
//          B14 rule 31 · B14 rule 33 · BR-SHL-020 · BR-SHL-012 · IS-3 · IS-10
// ───────────────────────────────────────────────────────
//
// The KIT half. `accountCombobox.dom.test.tsx` mounts the real Raise-a-refund
// form; this file owns the component itself, and two things that can only be
// proved here:
//
//   1. **The panel-state rule as a TABLE.** `remoteSearchPanel` is pure — the
//      `popoverAnchor.ts` precedent — so every combination is checkable rather
//      than the five a screen happens to reach. The ORDER of its tests is the
//      rule: a platform failure can never be read as no-match.
//   2. **The stale-selection rule at the seam where the value LEAVES the
//      control**, with a spy on `onChange`. The host test proves nothing posts;
//      this proves the control itself emits `""` and not the old id, which is
//      the property every future host inherits.
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  RemoteSearchSelectField,
  remoteSearchPanel,
} from "./RemoteSearchSelectField";
import type { RemoteOption, RemoteSearchStatus } from "./RemoteSearchSelectField";

afterEach(cleanup);

const IDLE: RemoteSearchStatus = { idle: true, searching: false, searched: false, failed: false };
const SEARCHING: RemoteSearchStatus = {
  idle: false,
  searching: true,
  searched: false,
  failed: false,
};
const SEARCHED: RemoteSearchStatus = {
  idle: false,
  searching: false,
  searched: true,
  failed: false,
};
const FAILED: RemoteSearchStatus = { idle: false, searching: false, searched: false, failed: true };

const WORDS = {
  tooShort: "Type at least two characters.",
  searching: "Searching for that account.",
  failed: "The account search could not run.",
  noMatch: "No account matches that.",
};

const OPTIONS: RemoteOption[] = [
  { value: "acc-0050", label: "AC-2026-00050 — Miller, Sarah" },
  { value: "acc-0051", label: "AC-2026-00051 — Ng, Priya" },
];

describe("remoteSearchPanel — the six states, as a table", () => {
  it("says nothing when nothing has been typed", () => {
    expect(remoteSearchPanel(IDLE, 0, false)).toBe("silent");
  });

  it("names too-short when something is typed and nothing was asked", () => {
    expect(remoteSearchPanel(IDLE, 0, true)).toBe("too-short");
  });

  it("names searching while the request is in flight", () => {
    expect(remoteSearchPanel(SEARCHING, 0, true)).toBe("searching");
  });

  it("names matches when rows came back", () => {
    expect(remoteSearchPanel(SEARCHED, 2, true)).toBe("matches");
  });

  it("names no-match when the search RAN and the answer was none", () => {
    expect(remoteSearchPanel(SEARCHED, 0, true)).toBe("no-match");
  });

  it("names failed when the search itself could not run", () => {
    expect(remoteSearchPanel(FAILED, 0, true)).toBe("failed");
  });

  it("⚠ a PLATFORM failure is never read as no-match, whatever else is true", () => {
    // ╔════════════════════════════════════════════════════════════════════╗
    // ║  THE ORDER OF THE TESTS IN `remoteSearchPanel` IS THE RULE.        ║
    // ╚════════════════════════════════════════════════════════════════════╝
    // BR-SHL-020: *the search could not run* is a fact about the PLATFORM and
    // support can act on it; *no such account* is a fact about the TERM and the
    // clerk can act on it. They are opposite, and in a naive combobox they are
    // one empty list. `failed` is asked FIRST so that a stale `searched` flag,
    // a cached row or a retry in flight cannot bury it.
    expect(remoteSearchPanel({ ...FAILED, searched: true }, 0, true)).toBe("failed");
    expect(remoteSearchPanel({ ...FAILED, searching: true }, 0, true)).toBe("failed");
    expect(remoteSearchPanel({ ...FAILED, searched: true }, 5, true)).toBe("failed");
  });

  it("no two states share a name — all six are distinguishable", () => {
    const all = [
      remoteSearchPanel(IDLE, 0, false),
      remoteSearchPanel(IDLE, 0, true),
      remoteSearchPanel(SEARCHING, 0, true),
      remoteSearchPanel(SEARCHED, 2, true),
      remoteSearchPanel(SEARCHED, 0, true),
      remoteSearchPanel(FAILED, 0, true),
    ];
    expect(new Set(all).size).toBe(6);
  });
});

/**
 * A host that holds its own term and value, the way the four payments screens
 * do — never the component driven by a fixed prop, which would make the
 * stale-selection case unprovable by construction.
 */
function Host(props: {
  status: RemoteSearchStatus;
  options?: RemoteOption[];
  onChangeSpy?: (value: string) => void;
}) {
  const [term, setTerm] = useState("");
  const [value, setValue] = useState("");
  return (
    <RemoteSearchSelectField
      id="account_id"
      label="Account"
      placeholder="Find the account"
      term={term}
      onTermChange={setTerm}
      status={props.status}
      options={props.options ?? OPTIONS}
      value={value}
      onChange={(next) => {
        setValue(next);
        props.onChangeSpy?.(next);
      }}
      words={WORDS}
      help="Account number, customer name or address."
      required
    />
  );
}

const box = (): HTMLInputElement =>
  document.querySelector<HTMLInputElement>("#account_id") as HTMLInputElement;
const panel = (): HTMLElement =>
  document.querySelector<HTMLElement>("[data-panel-state]") as HTMLElement;

describe("RemoteSearchSelectField — one control, and the money rule under it", () => {
  it("⚠ TYPING INVALIDATES THE PREVIOUS CHOICE — it emits \"\", not the old id", () => {
    // ╔════════════════════════════════════════════════════════════════════╗
    // ║  A combobox that keeps a stale selection behind a changed search   ║
    // ║  term is a MONEY BUG wearing a UX improvement.                     ║
    // ╚════════════════════════════════════════════════════════════════════╝
    // The two-field picker this replaces cleared the chosen id on every
    // keystroke, with the reason written beside it: *"Leaving a stale id behind
    // a changed box is how a clerk posts money to the account they were looking
    // at a moment ago."* One control makes it easier to get wrong, because the
    // box now holds the chosen account's OWN NAME — so the obvious
    // implementation leaves the id alone while the text changes under it.
    const onChange = vi.fn();
    render(<Host status={SEARCHED} onChangeSpy={onChange} />);

    fireEvent.click(screen.getByRole("option", { name: "AC-2026-00050 — Miller, Sarah" }));
    expect(onChange).toHaveBeenLastCalledWith("acc-0050");
    // The box now reads the account's NAME (B14 rule 31 — never the id).
    expect(box().value).toBe("AC-2026-00050 — Miller, Sarah");

    // …and the clerk types something else.
    fireEvent.change(box(), { target: { value: "AC-2026-99999" } });

    // WHAT POSTS IS EMPTY. Not the account that was on screen a moment ago.
    expect(onChange).toHaveBeenLastCalledWith("");
    expect(box().value).toBe("AC-2026-99999");
    // The option the clerk had taken is no longer the selected one, either —
    // a listbox still marking it would say the choice survived.
    expect(
      screen.getByRole("option", { name: "AC-2026-00050 — Miller, Sarah" }),
    ).toHaveAttribute("aria-selected", "false");
  });

  it("drops the keyboard highlight when the matches change under it", () => {
    // An index means nothing across two different lists: keep it and the clerk
    // who pressed ↓ before the next answer arrived hits Enter on a row that is
    // not the one they were looking at. The identity is the VALUES, not the
    // length — two lists of two are not the same two.
    const { rerender } = render(<Host status={SEARCHED} />);
    fireEvent.keyDown(box(), { key: "ArrowDown" });
    expect(box()).toHaveAttribute("aria-activedescendant", "account_id-opt-0");

    rerender(
      <Host
        status={SEARCHED}
        options={[
          { value: "acc-9000", label: "AC-2026-09000 — Okafor, Ada" },
          { value: "acc-9001", label: "AC-2026-09001 — Park, Jae" },
        ]}
      />,
    );
    expect(box()).not.toHaveAttribute("aria-activedescendant");
  });

  it("puts the id in no attribute a listbox exposes — the index is the handle", () => {
    render(<Host status={SEARCHED} />);
    // B14 rule 31 reaches further than the visible label: `SearchSelectField`
    // builds its option ids out of the option VALUE, which for these is a
    // database key. The index says the same thing to a screen reader.
    fireEvent.keyDown(box(), { key: "ArrowDown" });
    expect(box().getAttribute("aria-activedescendant")).toBe("account_id-opt-0");
    expect(panel().innerHTML).not.toContain("acc-0050\"");
  });

  it("draws the platform failure as a refusal and the other three as notes", () => {
    const { rerender } = render(<Host status={FAILED} options={[]} />);
    // Nothing is typed, yet a FAILED search is still a fact — a request that
    // could not run is not silence.
    expect(screen.getByText(WORDS.failed)).toHaveAttribute("data-refusal");

    rerender(<Host status={SEARCHED} options={[]} />);
    expect(screen.getByText(WORDS.noMatch)).toHaveAttribute("data-note");
    expect(screen.getByText(WORDS.noMatch)).not.toHaveAttribute("data-refusal");

    rerender(<Host status={SEARCHING} options={[]} />);
    expect(screen.getByText(WORDS.searching)).toHaveAttribute("data-note");
  });

  it("does not draw the panel at all while nothing has been typed", () => {
    render(<Host status={IDLE} options={[]} />);
    expect(panel().getAttribute("data-panel-state")).toBe("silent");
    expect(panel()).toHaveAttribute("hidden");
  });

  it("a disabled control keeps its panel shut (BR-SHL-025)", () => {
    render(
      <RemoteSearchSelectField
        id="account_id"
        label="Account"
        term="AC-2026"
        onTermChange={() => undefined}
        status={SEARCHED}
        options={OPTIONS}
        value=""
        onChange={() => undefined}
        words={WORDS}
        help="Not yours to set here."
        disabled
      />,
    );
    expect(box()).toBeDisabled();
    expect(panel()).toHaveAttribute("hidden");
    expect(box()).toHaveAttribute("aria-expanded", "false");
  });

  it("announces its help line, and its error when it has one", () => {
    const { rerender } = render(<Host status={SEARCHED} />);
    expect(box()).toHaveAttribute("aria-describedby", "account_id-help");

    rerender(
      <RemoteSearchSelectField
        id="account_id"
        label="Account"
        term=""
        onTermChange={() => undefined}
        status={SEARCHED}
        options={OPTIONS}
        value=""
        onChange={() => undefined}
        words={WORDS}
        help="Account number, customer name or address."
        error="Choose the account."
        required
      />,
    );
    expect(box()).toHaveAttribute("aria-describedby", "account_id-help account_id-error");
    expect(box()).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Choose the account.")).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-PAY-6319 (PO on the Raise-a-refund form, 2026-09-23) · DEF-3506 (the five states) · B14 rules 21, 31, 33, 36, 39, 43 · IS-3 · IS-10 · BR-SHL-012 · BR-SHL-020 · BR-SHL-025
// generated: 2026-09-23 by lane ACCOUNT-COMBO
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, in the harness that runs it — every case was run against a deliberately NAIVE build of this component (failed collapsed into no-match, the stale id kept, no keyboard) in a worktree at the branch tip. Verbatim output in the commit message and the defect row.
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
