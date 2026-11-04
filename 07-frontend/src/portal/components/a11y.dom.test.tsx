// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defects:  DEF-CWP-10547 (F-02) · DEF-CWP-10548 (F-03) · DEF-CWP-10551 (F-22)
//           · DEF-CWP-10552 (F-04) · DEF-CWP-10553 (F-17)
// Rulings:  decision log 2026-10-23 "Groups B and C: how they are built"
// Cases:    the focus helper; the always-present announcer (the same sentence
//           twice is heard twice); the field that wires its own box; a form
//           submitted empty (every required box marked, its message linked,
//           the summary focused, the status area filled); the focus rescue; a
//           disabled commit whose reason is TEXT; the guard that fails when a
//           portal box is drawn required but not marked in code.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import {
  Announced,
  FormScope,
  forgetLastPortalPath,
  moveFocusTo,
  PortalA11y,
  PortalAnnouncer,
  refocus,
  stableSelector,
  useAnnounce,
  usePortalForm,
} from "./a11y";
import { PortalDateBox } from "./PortalDateField";
import { CommitButton, DialInput, FormField, HeldButton, SelectInput, TextInput } from "./primitives";

afterEach(() => {
  vi.useRealTimers();
  forgetLastPortalPath();
  document.body.innerHTML = "";
});

const statusText = () => document.querySelector("[data-portal-status]")?.textContent ?? null;
const alertText = () => document.querySelector("[data-portal-alert]")?.textContent ?? null;

describe("the one focus helper", () => {
  it("focuses a heading by making it script-focusable, and says whether focus arrived", () => {
    render(
      <div>
        <h2 data-testid="h">Results</h2>
        <button type="button" disabled data-testid="b">
          Go
        </button>
      </div>,
    );
    const heading = screen.getByTestId("h");
    expect(moveFocusTo(heading)).toBe(true);
    expect(document.activeElement).toBe(heading);
    expect(heading.getAttribute("tabindex")).toBe("-1");
    // A disabled control cannot take focus, and the helper does not pretend.
    expect(moveFocusTo(screen.getByTestId("b"))).toBe(false);
    expect(moveFocusTo(null)).toBe(false);
  });

  it("finds a control again by its id or its data hooks, never by tag alone", () => {
    render(
      <div>
        <button type="button" data-action="ask-billing" data-variant="secondary">
          Ask
        </button>
        <input id="quick-name" />
        <span>bare</span>
      </div>,
    );
    expect(stableSelector(document.querySelector("button")!)).toBe('button[data-action="ask-billing"]');
    expect(stableSelector(document.querySelector("input")!)).toBe("#quick-name");
    expect(stableSelector(document.querySelector("span")!)).toBeNull();
  });
});

describe("the announcer (F-02)", () => {
  function Speaker() {
    const say = useAnnounce();
    return (
      <>
        <button type="button" onClick={() => say.polite("Saved on 2 accounts.")}>
          polite
        </button>
        <button type="button" onClick={() => say.assertive("Those details do not match.")}>
          assertive
        </button>
      </>
    );
  }

  it("is always in the page, empty, before anything is said", () => {
    render(
      <PortalAnnouncer>
        <p>page</p>
      </PortalAnnouncer>,
    );
    const status = document.querySelector("[data-portal-status]");
    const alert = document.querySelector("[data-portal-alert]");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(status?.textContent).toBe("");
  });

  it("says the same sentence twice as two announcements (a new node each time)", () => {
    render(
      <PortalAnnouncer>
        <Speaker />
      </PortalAnnouncer>,
    );
    fireEvent.click(screen.getByText("assertive"));
    const first = document.querySelector("[data-portal-alert] span");
    expect(alertText()).toBe("Those details do not match.");
    fireEvent.click(screen.getByText("assertive"));
    const second = document.querySelector("[data-portal-alert] span");
    expect(alertText()).toBe("Those details do not match.");
    expect(second).not.toBe(first);
    fireEvent.click(screen.getByText("polite"));
    expect(statusText()).toBe("Saved on 2 accounts.");
  });

  it("mounts once: a frame inside PortalApp's announcer adds no second pair", () => {
    render(
      <PortalAnnouncer>
        <PortalAnnouncer>
          <p>inner</p>
        </PortalAnnouncer>
      </PortalAnnouncer>,
    );
    expect(document.querySelectorAll("[data-portal-status]")).toHaveLength(1);
    expect(document.querySelectorAll("[data-portal-alert]")).toHaveLength(1);
  });

  it("an Announced message fills the region AND takes focus when it appears", () => {
    function Page() {
      const [shown, setShown] = useState(false);
      return (
        <PortalAnnouncer>
          <button type="button" onClick={() => setShown(true)}>
            send
          </button>
          {shown ? (
            <Announced tone="error" className="x" data-refused="">
              The amount changed. Please look again.
            </Announced>
          ) : null}
        </PortalAnnouncer>
      );
    }
    render(<Page />);
    fireEvent.click(screen.getByText("send"));
    const message = document.querySelector("[data-refused]");
    expect(alertText()).toBe("The amount changed. Please look again.");
    expect(document.activeElement).toBe(message);
    expect(message).toHaveClass("x");
  });
});

describe("the field wires its own box (F-03)", () => {
  it("marks every kit box required, described and invalid with nothing passed", () => {
    render(
      <>
        <FormField id="a" label="Name" required helper="As on the bill" error="Fill this in.">
          <TextInput id="a" value="" onChange={() => undefined} />
        </FormField>
        <FormField id="b" label="Kind" required error="Pick one.">
          <SelectInput id="b" value="" options={[{ value: "x", label: "X" }]} onChange={() => undefined} />
        </FormField>
        <FormField id="c" label="Code" required>
          <DialInput id="c" value="" onChange={() => undefined} />
        </FormField>
        <FormField id="d" label="Date" required>
          <PortalDateBox id="d" value="" onChange={() => undefined} />
        </FormField>
      </>,
    );
    const a = document.getElementById("a")!;
    expect(a).toHaveAttribute("aria-required", "true");
    expect(a).toHaveAttribute("aria-invalid", "true");
    expect(a.getAttribute("aria-describedby")?.split(" ")).toEqual(["a-helper", "a-error"]);
    expect(document.getElementById("a-error")).toHaveTextContent("Fill this in.");
    expect(document.getElementById("a-helper")).toHaveTextContent("As on the bill");
    expect(document.getElementById("b")).toHaveAttribute("aria-invalid", "true");
    expect(document.getElementById("b")).toHaveAttribute("aria-describedby", "b-error");
    expect(document.getElementById("c")).toHaveAttribute("aria-required", "true");
    expect(document.getElementById("d")).toHaveAttribute("aria-required", "true");
  });

  it("a box at rest is not invalid and points at no empty error line", () => {
    render(
      <FormField id="a" label="Name">
        <TextInput id="a" value="" onChange={() => undefined} />
      </FormField>,
    );
    const a = document.getElementById("a")!;
    expect(a).not.toHaveAttribute("aria-invalid");
    expect(a).not.toHaveAttribute("aria-describedby");
    expect(a).not.toHaveAttribute("aria-required");
  });
});

describe("a form submitted empty (F-02, F-03, F-04)", () => {
  function Form(props: { onSend: () => void }) {
    const form = usePortalForm();
    const [name, setName] = useState("");
    const [phone, setPhone] = useState("");
    return (
      <PortalAnnouncer>
        <FormScope form={form}>
          <FormField id="n" label="Your name" required>
            <TextInput id="n" value={name} onChange={setName} />
          </FormField>
          <FormField id="p" label="Phone" required>
            <TextInput id="p" value={phone} onChange={setPhone} />
          </FormField>
          <FormField id="d" label="Details">
            <TextInput id="d" value="" onChange={() => undefined} />
          </FormField>
        </FormScope>
        <button type="button" onClick={form.guard(props.onSend)}>
          Send
        </button>
      </PortalAnnouncer>
    );
  }

  it("marks each empty required box, links its message, focuses the summary and fills the alert", () => {
    const sent = vi.fn();
    render(<Form onSend={sent} />);
    const send = screen.getByText("Send");
    send.focus();
    fireEvent.click(send);
    expect(sent).not.toHaveBeenCalled();
    for (const id of ["n", "p"]) {
      const box = document.getElementById(id)!;
      expect(box).toHaveAttribute("aria-invalid", "true");
      expect(box.getAttribute("aria-describedby")).toContain(`${id}-error`);
      expect(document.getElementById(`${id}-error`)).toHaveTextContent("Fill this in.");
    }
    // The optional box is left alone.
    expect(document.getElementById("d")).not.toHaveAttribute("aria-invalid");
    const summary = document.querySelector("[data-error-summary]");
    expect(summary).not.toBeNull();
    expect(document.activeElement).toBe(summary);
    const links = [...document.querySelectorAll("[data-error-summary-link]")];
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["#n", "#p"]);
    expect(alertText()).toContain("Check these fields");
    expect(alertText()).toContain("Your name: Fill this in.");
    // A link moves focus INTO its box.
    fireEvent.click(links[1]);
    expect(document.activeElement).toBe(document.getElementById("p"));
  });

  it("sends once every required box is filled, and the error clears as they type", () => {
    const sent = vi.fn();
    render(<Form onSend={sent} />);
    fireEvent.click(screen.getByText("Send"));
    fireEvent.change(document.getElementById("n")!, { target: { value: "Ana" } });
    fireEvent.input(document.getElementById("n")!, { target: { value: "Ana" } });
    expect(document.getElementById("n")).not.toHaveAttribute("aria-invalid");
    fireEvent.change(document.getElementById("p")!, { target: { value: "2815550164" } });
    fireEvent.click(screen.getByText("Send"));
    expect(sent).toHaveBeenCalledTimes(1);
  });
});

describe("a disabled commit says why, as text (F-22)", () => {
  it("CommitButton and HeldButton draw the reason and point the button at it", () => {
    render(
      <>
        <CommitButton label="Look it up" working={false} ready={false} reason="Fill in both boxes." onClick={() => undefined} />
        <HeldButton label="Save for later" reason="Not available yet." />
      </>,
    );
    for (const [label, reason] of [
      ["Look it up", "Fill in both boxes."],
      ["Save for later", "Not available yet."],
    ]) {
      const button = screen.getByText(label).closest("button")!;
      expect(button).toBeDisabled();
      const id = button.getAttribute("aria-describedby");
      expect(id, `${label} names no reason`).toBeTruthy();
      expect(document.getElementById(id!)).toHaveTextContent(reason);
    }
  });
});

describe("focus is never left on the body (F-04)", () => {
  it("a focused control that is REMOVED hands focus to its replacement, else the page heading", async () => {
    vi.useFakeTimers();
    function Page() {
      const [open, setOpen] = useState(false);
      return (
        <PortalA11y>
          <main>
            <h1>Ask us</h1>
            {open ? (
              <div>
                <h1>Report a leak</h1>
                <button type="button" data-action="cancel-ask" onClick={() => setOpen(false)}>
                  Back
                </button>
              </div>
            ) : (
              <button type="button" data-action="ask-leak" onClick={() => setOpen(true)}>
                Ask
              </button>
            )}
          </main>
        </PortalA11y>
      );
    }
    render(
      <MemoryRouter>
        <Page />
      </MemoryRouter>,
    );
    const ask = document.querySelector<HTMLButtonElement>('[data-action="ask-leak"]')!;
    ask.focus();
    fireEvent.click(ask);
    // Neither jsdom nor Chromium fires a focusout when the focused node is
    // REMOVED; the rescue hears the page change (a MutationObserver, which
    // reports in a microtask) and then retries on timers.
    expect(document.activeElement).toBe(document.body);
    await act(async () => {
      await Promise.resolve();
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement?.tagName).toBe("H1");
  });

  it("refocus puts focus back on the opener once it is drawn again", () => {
    vi.useFakeTimers();
    render(<div id="later" />);
    refocus('button[data-action="ask-leak"]');
    act(() => {
      vi.advanceTimersByTime(100);
    });
    const button = document.createElement("button");
    button.setAttribute("data-action", "ask-leak");
    document.getElementById("later")!.appendChild(button);
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(document.activeElement).toBe(button);
  });

  it("a page change moves focus to the new heading and announces it once", () => {
    vi.useFakeTimers();
    function Nav() {
      const go = useNavigate();
      return (
        <button type="button" onClick={() => go("/bills")}>
          Bills tab
        </button>
      );
    }
    render(
      <MemoryRouter initialEntries={["/home"]}>
        <PortalA11y>
          <main>
            <Routes>
              <Route path="/home" element={<><h1>Home</h1><Nav /></>} />
              <Route path="/bills" element={<h1>Bills</h1>} />
            </Routes>
          </main>
        </PortalA11y>
      </MemoryRouter>,
    );
    // First load: nothing moves.
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(statusText()).toBe("");
    fireEvent.click(screen.getByText("Bills tab"));
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(document.activeElement?.textContent).toBe("Bills");
    expect(statusText()).toBe("Bills");
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
 * THE GUARD: a portal box drawn required but not marked in code fails here.
 * ═══════════════════════════════════════════════════════════════════════════ */

describe("guard: required is never an asterisk only (F-03) — rendered", () => {
  it("every FormField drawn `required` marks its box aria-required (rendered, all four kit boxes)", () => {
    // Covered box by box above; this is the census: each kit box, inside a
    // required field, with NOTHING passed, reads as required.
    render(
      <>
        {(["t", "s", "c", "d"] as const).map((id) => (
          <FormField key={id} id={id} label={id} required>
            {id === "t" ? (
              <TextInput id={id} value="" onChange={() => undefined} />
            ) : id === "s" ? (
              <SelectInput id={id} value="" options={[]} onChange={() => undefined} />
            ) : id === "c" ? (
              <DialInput id={id} value="" onChange={() => undefined} />
            ) : (
              <PortalDateBox id={id} value="" onChange={() => undefined} />
            )}
          </FormField>
        ))}
      </>,
    );
    for (const id of ["t", "s", "c", "d"]) {
      expect(document.getElementById(id), id).toHaveAttribute("aria-required", "true");
    }
  });
});
