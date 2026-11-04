// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-SHL-3938 — `scrollToFirstError` called `scrollIntoView`
//           plainly. jsdom does not implement it, so the call THREW inside an
//           async submit whose promise is discarded by `void handleSubmit(e)`,
//           and it threw BEFORE `input.focus()`. The focus is the requirement;
//           the scroll is the nicety.
// Rules:    A18 §5 (submit re-validates and the viewport lands on the first
//           error) · BR-SHL-017 (submit stays enabled and re-validates)
// Why here: `FormModal.test.tsx` renders with `renderToStaticMarkup`, so it can
//           assert the first error is IDENTIFIED (`result.first` is "code") and
//           can never assert that anything ACTS on it. That gap is hard-won law
//           2 exactly — a target computed and nothing wired to it — and it is
//           why the throw above went unnoticed while every test passed.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { useState } from "react";

import { FormModal, ModalShell, TextField } from "./FormModal";
import type { FormSubmitOutcome, ServerErrorEnvelope } from "./FormModal";

afterEach(cleanup);

const SCHEMA = z.object({ code: z.string().min(1, "Required") });

function Harness(props: { onSubmit: () => Promise<{ ok: true }> }) {
  return (
    <FormModal
      title="A code is needed"
      schema={SCHEMA}
      values={{ code: "" }}
      onSubmit={props.onSubmit}
      onClose={() => undefined}
      submitLabel="Save"
    >
      {/* A bare input rather than a kit field: `scrollToFirstError` finds its
          target with `document.getElementById`, so the id is the whole
          contract and the kit's own markup is a different test's subject. */}
      <input id="code" defaultValue="" />
    </FormModal>
  );
}

describe("A18 §5 — an invalid submit lands the reader on the first error", () => {
  it("moves focus to the first invalid field, and posts nothing (DEF-SHL-3938)", async () => {
    const onSubmit = vi.fn(() => Promise.resolve({ ok: true as const }));
    render(<Harness onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    // ⚠ THE ASSERTION THAT WOULD HAVE CAUGHT THE DEFECT. With the plain
    // `scrollIntoView(...)` the throw landed before `focus()`, so the button
    // kept focus and this read `BUTTON` — while every existing assertion about
    // the rendered errors still passed, because the markup was correct.
    expect(document.activeElement).toBe(document.getElementById("code"));

    // A18 §5's other half, asserted here so the two cannot drift apart: the
    // modal stays open and nothing is posted (US-SHL-009 TC-1).
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("A code is needed")).toBeInTheDocument();
  });

  it("survives an environment with no scrollIntoView at all, which is this one", () => {
    // Stated rather than assumed, because the fix reads as defensive tidying
    // and the next lane will otherwise simplify the optional call away: jsdom
    // genuinely does not implement it, so the guard is load-bearing HERE and
    // this line is what fails if someone stubs it globally and hides the case.
    const input = document.createElement("input");
    expect(typeof (input as Partial<HTMLElement>).scrollIntoView).toBe("undefined");
  });
});

// ── DEF-SHL-9615 · a server refusal leaves its field when the field changes ──
//
// Add a part kept *"MTR-W34 is already in the register."* under Part number
// after the clerk had retyped it VLV-GT1, until the next press. A refusal is
// about the value the server was SENT; once that value is gone the sentence is
// about nothing on the screen. Only the field whose value changed loses its
// refusal — a neighbour that still holds the refused value keeps its own.
function RetypeHarness(props: { onSubmit: () => Promise<FormSubmitOutcome> }) {
  const [code, setCode] = useState("MTR-W34");
  const [name, setName] = useState("Meter");
  return (
    <FormModal
      title="Add a part"
      schema={z.object({ code: z.string(), name: z.string() })}
      values={{ code, name }}
      onSubmit={props.onSubmit}
      onClose={() => undefined}
      submitLabel="Save"
    >
      <TextField id="code" label="Part number" value={code} onChange={setCode} />
      <TextField id="name" label="Name" value={name} onChange={setName} />
    </FormModal>
  );
}

describe("DEF-SHL-9615 — a server refusal does not outlive the value it refused", () => {
  it("clears the field's refusal when its value changes, and only that field's", async () => {
    const onSubmit = vi.fn(() =>
      Promise.resolve({
        ok: false as const,
        error: {
          code: "VAL_FORMAT",
          message_key: "work.parts.duplicate_no",
          params: { existing: "MTR-W34" },
          field_errors: [
            { field: "code", code: "VAL_FORMAT", message_key: "work.parts.duplicate_no", params: { existing: "MTR-W34" } },
            { field: "name", code: "VAL_FORMAT", message_key: "work.parts.duplicate_no", params: { existing: "Meter" } },
          ],
        } as unknown as ServerErrorEnvelope,
      }),
    );
    render(<RetypeHarness onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("MTR-W34 is already in the register.")).toBeInTheDocument();
    expect(screen.getByText("Meter is already in the register.")).toBeInTheDocument();

    const input = screen.getByLabelText("Part number");
    await userEvent.clear(input);
    await userEvent.type(input, "VLV-GT1");

    expect(screen.queryByText("MTR-W34 is already in the register.")).toBeNull();
    // The untouched neighbour still holds the refused value, so it keeps its own.
    expect(screen.getByText("Meter is already in the register.")).toBeInTheDocument();

    // Typing the refused value back brings the refusal back: it is about that value.
    await userEvent.clear(input);
    await userEvent.type(input, "MTR-W34");
    expect(screen.getByText("MTR-W34 is already in the register.")).toBeInTheDocument();
  });
});

describe("DEF-SHL-6148 — Escape still closes a dialog after its submit was refused", () => {
  // `WorkingButton` disables the submit while the commit is in flight, and a
  // focused control that becomes disabled loses focus to <body> in every
  // browser — OUTSIDE the overlay whose onKeyDown closes on Escape. jsdom does
  // no focus fix-up, so the test performs the browser's half: it blurs the
  // disabled button exactly as Chromium does, then lets the refusal land.
  it("returns focus into the card when the commit ends, so Escape reaches the handler", async () => {
    let refuse: (outcome: FormSubmitOutcome) => void = () => undefined;
    const onSubmit = vi.fn(() => new Promise<FormSubmitOutcome>((resolve) => { refuse = resolve; }));
    const onClose = vi.fn();
    render(
      <FormModal
        title="A code is needed"
        schema={SCHEMA}
        values={{ code: "MTR-W34" }}
        onSubmit={onSubmit}
        onClose={onClose}
        submitLabel="Save"
      >
        <input id="code" defaultValue="MTR-W34" />
      </FormModal>,
    );
    const save = screen.getByRole("button", { name: "Save" });
    await userEvent.click(save);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    // The browser's focus fix-up. jsdom refuses `blur()` on a DISABLED control,
    // so focus is parked on a throwaway element outside the dialog and the
    // element removed — which is the fix-up jsdom does perform.
    const parked = document.createElement("button");
    document.body.appendChild(parked);
    parked.focus();
    parked.remove();
    expect(document.activeElement).toBe(document.body);

    refuse({
      ok: false,
      error: { code: "VAL_FORMAT", message_key: "work.parts.duplicate_no", params: { existing: "MTR-W34" }, field_errors: [] } as unknown as ServerErrorEnvelope,
    });
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    expect(document.activeElement).not.toBe(document.body);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("DEF-SHL-10686 — closing a dialog gives focus back to what opened it", () => {
  function Opener() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Open it
        </button>
        {open && (
          <ModalShell title="A dialog" onClose={() => setOpen(false)}>
            <div className="modal-body">Body</div>
          </ModalShell>
        )}
      </>
    );
  }

  it("Escape closes it and the opener has focus again", async () => {
    const user = userEvent.setup();
    render(<Opener />);
    const opener = screen.getByRole("button", { name: "Open it" });
    await user.click(opener);
    expect(screen.getByRole("dialog")).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  // DEF-SHL-10775 — opened from a row's "More actions" menu, the opener sits in
  // a <details> that closed when the action was chosen. A browser cannot focus
  // it, so focus fell to the page; it goes to the menu's own summary instead.
  function MenuOpener() {
    const [open, setOpen] = useState(false);
    const [menuOpen, setMenuOpen] = useState(true);
    return (
      <>
        <details open={menuOpen}>
          <summary aria-label="More actions">…</summary>
          <button
            type="button"
            onClick={() => {
              setMenuOpen(false);
              setOpen(true);
            }}
          >
            Reverse
          </button>
        </details>
        {open && (
          <ModalShell title="A dialog" onClose={() => setOpen(false)}>
            <div className="modal-body">Body</div>
          </ModalShell>
        )}
      </>
    );
  }

  it("opened from a closed menu, Escape gives focus to the menu's summary", async () => {
    const user = userEvent.setup();
    render(<MenuOpener />);
    await user.click(screen.getByRole("button", { name: "Reverse" }));
    expect(screen.getByRole("dialog")).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("…")).toHaveFocus();
  });

  // …and the Payments list's case: the table re-renders the row's menu while
  // the dialog is open, so the node that opened it has left the page.
  function RemountingRow() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <table>
          <tbody>
            <tr>
              <td>
                <details key={open ? "after" : "before"} open>
                  <summary aria-label="More actions">⋯</summary>
                  <button type="button" onClick={() => setOpen(true)}>
                    Reverse
                  </button>
                </details>
              </td>
            </tr>
          </tbody>
        </table>
        {open && (
          <ModalShell title="A dialog" onClose={() => setOpen(false)}>
            <div className="modal-body">Body</div>
          </ModalShell>
        )}
      </>
    );
  }

  it("the menu re-rendered while open: focus goes to the same row's menu", async () => {
    const user = userEvent.setup();
    render(<RemountingRow />);
    await user.click(screen.getByRole("button", { name: "Reverse" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("⋯")).toHaveFocus();
  });
});
