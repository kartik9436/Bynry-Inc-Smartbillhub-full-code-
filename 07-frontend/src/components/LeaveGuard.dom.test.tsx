// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-10001 — leaving a wizard half-done lost the work silently.
// Ruling:  PO 2026-10-07 (decision log "LEAVING A WIZARD HALF-DONE ASKS
//          FIRST"): a popup on every multi-step screen; "Save as draft" only
//          where a draft can be kept; everywhere else the clerk is told the
//          work will not be saved.
// Tests:   the guard fires on a side-nav click when dirty · not when clean ·
//          not on the wizard's own step change · not on Complete · not on
//          Save & exit · not on Park · Save as draft saves then navigates ·
//          a failed save stays · the no-draft text · Back in the browser.
// ───────────────────────────────────────────────────────
//
// ⚠ **MOUNTED UNDER A DATA ROUTER, AND THAT IS THE WHOLE POINT.** The guard
// is `useBlocker`, which exists only under `createBrowserRouter` /
// `createMemoryRouter` — the product's `App.tsx` uses the first. The frame's
// older tests mount under a plain `MemoryRouter`, where no guard can mount at
// all; a test written that way would pass with the guard deleted. The side
// nav here is a real `<Link>` OUTSIDE the frame, exactly as the app shell's.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { Link, Outlet, RouterProvider, createMemoryRouter, useNavigate, useSearchParams } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";

import { ToastProvider, createToastQueue } from "./Toast";
import type { ToastQueue } from "./Toast";
import { WizardFrame } from "./WizardFrame";
import type { WizardExit, WizardNavState, WizardStep } from "./WizardFrame";
import type { LeaveDraft } from "./LeaveGuard";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

interface Harness {
  draft?: LeaveDraft | null;
  withExit?: boolean;
  onParked?: () => void;
}

function Wizard(props: Harness) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const step = Number(params.get("step") ?? "1");
  const [reached, setReached] = useState(step);
  const nav: WizardNavState = { step, reached };
  const [parkOpen, setParkOpen] = useState(false);
  const steps: WizardStep[] = [1, 2, 3].map((n) => ({
    id: `s${n}`,
    label: `Step ${n}`,
    content: (
      <label>
        Field {n}
        <input aria-label={`field-${n}`} defaultValue="" />
      </label>
    ),
  }));
  const exit: WizardExit = {
    onSaveAndExit: () => navigate("/t/list"),
    parkBlockedReason: null,
    parkOpen,
    onParkOpenChange: setParkOpen,
    onPark: async () => {
      // A park's own navigation runs AFTER it resolves, as `useWizardPark`'s
      // `onParked` effect does in the product.
      setTimeout(() => navigate("/t/list"), 0);
      return { ok: true };
    },
    dateFormat: "MM/DD/YYYY",
    parkedAt: null,
  };
  return (
    <WizardFrame
      steps={steps}
      nav={nav}
      onNavChange={(next) => {
        setReached(next.reached);
        const p = new URLSearchParams(params);
        p.set("step", String(next.step));
        setParams(p);
      }}
      commitLabel="Finish ✓"
      commitFailedTitle="Could not finish"
      onCommit={() => Promise.resolve({ ok: true })}
      onCommitted={() => navigate("/t/done")}
      exit={props.withExit === true ? exit : undefined}
      saveDraft={props.draft}
    />
  );
}

function Shell() {
  return (
    <div>
      <nav aria-label="side">
        <Link to="/t/accounts">Accounts</Link>
      </nav>
      <Outlet />
    </div>
  );
}

function mount(harness: Harness = {}, queue?: ToastQueue) {
  const router = createMemoryRouter(
    [
      {
        path: "/t",
        element: <Shell />,
        children: [
          { path: "wiz", element: <Wizard {...harness} /> },
          { path: "accounts", element: <p>Accounts page</p> },
          { path: "list", element: <p>List page</p> },
          { path: "done", element: <p>Done page</p> },
        ],
      },
    ],
    { initialEntries: ["/t/accounts", "/t/wiz"], initialIndex: 1 },
  );
  render(
    <ToastProvider queue={queue}>
      <RouterProvider router={router} />
    </ToastProvider>,
  );
  return router;
}

const sideNav = () => fireEvent.click(screen.getByRole("link", { name: "Accounts" }));
const typeInto = (n: number) =>
  fireEvent.change(screen.getByLabelText(`field-${n}`), { target: { value: "typed" } });
const dialog = () => screen.queryByRole("alertdialog");

describe("the leave-page guard — DEF-SHL-10001", () => {
  it("does NOT ask when the wizard was only opened", async () => {
    const router = mount();
    sideNav();
    await waitFor(() => expect(router.state.location.pathname).toBe("/t/accounts"));
    expect(dialog()).toBeNull();
  });

  it("ASKS on a side-nav click once the clerk has typed, and Stay keeps the work", async () => {
    const router = mount();
    typeInto(1);
    sideNav();
    await waitFor(() => expect(dialog()).not.toBeNull());
    expect(router.state.location.pathname).toBe("/t/wiz");
    fireEvent.click(screen.getByRole("button", { name: t("leaveGuard.stay") }));
    await waitFor(() => expect(dialog()).toBeNull());
    expect(router.state.location.pathname).toBe("/t/wiz");
    expect(screen.getByLabelText("field-1")).toHaveValue("typed");
  });

  it("the 39 with no draft: says the work will not be saved, and Leave without saving leaves", async () => {
    const router = mount({ draft: null });
    typeInto(1);
    sideNav();
    await waitFor(() => expect(dialog()).not.toBeNull());
    expect(screen.getByText(t("leaveGuard.discard.title"))).toBeInTheDocument();
    expect(screen.getByText(t("leaveGuard.discard.body"))).toBeInTheDocument();
    expect(t("leaveGuard.discard.title")).toBe("Leave without saving?");
    expect(t("leaveGuard.discard.body")).toBe("Your work will not be saved.");
    expect(screen.queryByText(t("leaveGuard.saveDraft"))).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: t("leaveGuard.leave") }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/t/accounts"));
  });

  it("does NOT ask on the wizard's own step change (?step=), and asks after it", async () => {
    const router = mount();
    typeInto(1); // dirty BEFORE the step change, so a guard that asked on it would show
    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(router.state.location.search).toBe("?step=2"));
    expect(dialog()).toBeNull();
    // The RAIL is not the footer, so nothing marks this one deliberate: only
    // the guard's own rule — same path, only `?step=` moved — lets it pass.
    fireEvent.click(screen.getByRole("button", { name: /Step 1/ }));
    await waitFor(() => expect(router.state.location.search).toBe("?step=1"));
    expect(dialog()).toBeNull();
    sideNav();
    await waitFor(() => expect(dialog()).not.toBeNull());
  });

  it("asks on browser Back too", async () => {
    const router = mount();
    typeInto(1);
    await act(async () => {
      await router.navigate(-1);
    });
    await waitFor(() => expect(dialog()).not.toBeNull());
    expect(router.state.location.pathname).toBe("/t/wiz");
  });

  it("does NOT ask on Complete", async () => {
    const router = mount();
    for (const n of [1, 2]) {
      typeInto(n);
      fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
      await waitFor(() => expect(router.state.location.search).toBe(`?step=${n + 1}`));
    }
    fireEvent.click(screen.getByRole("button", { name: "Finish ✓" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/t/done"));
    expect(dialog()).toBeNull();
  });

  it("does NOT ask on Save & exit", async () => {
    const router = mount({ withExit: true });
    typeInto(1);
    fireEvent.click(screen.getByRole("button", { name: t("wizard.exit.saveAndExit") }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/t/list"));
    expect(dialog()).toBeNull();
  });

  it("does NOT ask on Park", async () => {
    const router = mount({ withExit: true });
    typeInto(1);
    fireEvent.click(screen.getByRole("button", { name: t("wizard.exit.park") }));
    fireEvent.change(document.getElementById("wizard_park_reason") as HTMLSelectElement, {
      target: { value: "customer" },
    });
    fireEvent.click(screen.getByRole("button", { name: t("wizard.park.submit") }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/t/list"));
    expect(dialog()).toBeNull();
  });

  it("the 6 with a draft: Save as draft writes it, says where it is, then goes", async () => {
    const queue = createToastQueue();
    const fired = vi.spyOn(queue, "fire");
    const onSave = vi.fn(() => Promise.resolve({ ok: true as const }));
    const router = mount({ draft: { onSave, savedMessage: "Saved as draft. Find it on Move-ins." } }, queue);
    typeInto(1);
    sideNav();
    await waitFor(() => expect(dialog()).not.toBeNull());
    expect(screen.getByText(t("leaveGuard.draft.title"))).toBeInTheDocument();
    expect(t("leaveGuard.draft.title")).toBe("Save your work as a draft?");
    fireEvent.click(screen.getByRole("button", { name: t("leaveGuard.saveDraft") }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/t/accounts"));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(fired).toHaveBeenCalledWith("Saved as draft. Find it on Move-ins.");
  });

  it("a failed Save as draft STAYS on the page and says so", async () => {
    const onSave = vi.fn(() => Promise.resolve({ ok: false as const }));
    const router = mount({ draft: { onSave, savedMessage: "x" } });
    typeInto(1);
    sideNav();
    await waitFor(() => expect(dialog()).not.toBeNull());
    fireEvent.click(screen.getByRole("button", { name: t("leaveGuard.saveDraft") }));
    await waitFor(() => expect(screen.getByText(t("leaveGuard.saveFailed"))).toBeInTheDocument());
    expect(router.state.location.pathname).toBe("/t/wiz");
    expect(screen.getByLabelText("field-1")).toHaveValue("typed");
  });
});
