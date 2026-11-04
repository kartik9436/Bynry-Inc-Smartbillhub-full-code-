// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-10001 — leaving a multi-step screen half-done lost the work
//          with no warning (no screen blocked navigation at all).
// Ruling:  PO 2026-10-07, decision log "LEAVING A WIZARD HALF-DONE ASKS FIRST",
//          verbatim: *"lets start with this and also tell user if they leave
//          work will not be saved - (a) Popup on all 45. "Save as draft" only
//          on the 6 that can keep a draft. The other 39 say "Leave without
//          saving? · Stay""*.
// Rules:   B14 rules 6 (danger tier on the act that destroys), 33 (caps — the
//          popup carries a title and at most one six-word sentence; WHY the
//          work is lost is rationale and is zero words), 35 (eleven
//          catalogues, each in its own words), 43 (a component, not inline
//          code), 44 (our kit builds it: `ModalShell` + `Button`).
// Impacts: components/WizardFrame.tsx and components/workflow/WorkflowRunner.tsx
//          mount it; between them they are every multi-step staff screen
//          (`leaveGuardInventory.test.ts` counts them and goes red on one
//          that draws a step rail without it — hard-won law 2).
// ───────────────────────────────────────────────────────
import { useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { UNSAFE_DataRouterContext, useBlocker } from "react-router-dom";
import type { Location } from "react-router-dom";

import { ModalShell } from "./FormModal";
import { WorkingButton } from "./StateFrame";
import { useToastIfMounted } from "./Toast";

import { Button } from "@/components/Button";

/**
 * The navigation `state` a screen passes when it leaves ON PURPOSE from a
 * control the frame cannot see — a page-head *Save draft & exit*, say:
 * `navigate(to, { state: LEAVE_DELIBERATELY })`. The guard lets it through.
 * The frame's own exits (Complete, Park, Save & exit, Cancel, the footer) are
 * recognised without it.
 */
export const LEAVE_DELIBERATELY = { leaveGuard: "deliberate" } as const;

/** What a flow that CAN keep a draft hands the guard (six flows — the ruling). */
export interface LeaveDraft {
  /** Writes the SAME draft the flow's own Park / autosave writes — never a
   *  second store. Resolves `{ ok: false }` (never throws) when it could not. */
  onSave: () => Promise<{ ok: true } | { ok: false; reason?: string }>;
  /** The toast after a good save — where the draft now is, e.g. *"Saved as
   *  draft. Find it on Move-ins."* Already translated. */
  savedMessage: string;
}

export interface LeaveGuardOptions {
  /** A dirty signal the owner knows and the guard cannot see — a wizard that
   *  has been stepped forward, say. OR'd with the guard's own: any `change` or
   *  `input` event inside the element `touch` is spread on. */
  dirty: boolean;
  /** `null` = this screen keeps no draft, so the popup says the work will not
   *  be saved and offers no save. */
  draft: LeaveDraft | null;
}

export interface LeaveGuard {
  /** Spread on the screen's root element — a person typing, ticking or picking
   *  inside it is what arms the guard. A value put there by code (a resumed
   *  draft, a pre-fill) fires no such event and arms nothing. */
  touch: { onChangeCapture: () => void; onInputCapture: () => void };
  /** The screen's work is safely somewhere (committed, parked) — never ask
   *  again for this mount. */
  release: () => void;
  /** Run one of the screen's OWN acts; any navigation it causes while it runs,
   *  and in the same task after it settles, is deliberate and passes. */
  deliberately: <T>(act: () => T) => T;
  /** Render this once — the blocker, the popup and the tab-close prompt. */
  element: ReactNode;
}

/**
 * **ONE LEAVE-PAGE GUARD FOR EVERY MULTI-STEP SCREEN** (`DEF-SHL-10001`).
 *
 * It asks only when something would be LOST: never on an untouched screen,
 * never on the screen's own step changes (`?step=` keeps the path), and never
 * on its own exits. It catches every way out the app frame offers — side nav,
 * top menu, sub-menus, any link, browser Back — because they are all router
 * navigations, and the tab closing or reloading through `beforeunload` (the
 * browser draws that prompt and allows no words of ours).
 *
 * ⚠ **THE BLOCKER NEEDS A DATA ROUTER, AND A UNIT TEST USUALLY HAS NONE.**
 * `useBlocker` throws outside `createBrowserRouter`/`createMemoryRouter`, and
 * dozens of wizard tests mount under a plain `MemoryRouter`. So the blocker is
 * a child mounted only when the data-router context exists: the product
 * (`App.tsx` uses `createBrowserRouter`) always has it, and a bare test simply
 * renders no guard rather than crashing.
 */
export function useLeaveGuard(options: LeaveGuardOptions): LeaveGuard {
  // ⚠ **REFS, NOT STATE — A RE-RENDER ON THE FIRST KEYSTROKE LOST A PICK.**
  // `touch` fires on `input` AND on `change`, and a browser sends a `<select>`
  // pick as `input` THEN `change`, two events. With `touched` held in state,
  // the `input` re-rendered the screen between them, React put every
  // controlled `<select>` back to its old value, and the `change` then read
  // that old value: the Park panel's *Waiting on* pick came out empty
  // (`wizardPark.dom.test.tsx`, red on the first draft of this guard). Nothing
  // on screen depends on these, so nothing needs to re-render.
  const touchedRef = useRef(false);
  const dirtyRef = useRef(options.dirty);
  dirtyRef.current = options.dirty;
  const releasedRef = useRef(false);
  const deliberate = useRef(0);
  const isActive = useCallback(
    () => (touchedRef.current || dirtyRef.current) && !releasedRef.current,
    [],
  );

  const markTouched = useCallback(() => {
    touchedRef.current = true;
  }, []);
  const release = useCallback(() => {
    releasedRef.current = true;
  }, []);
  const deliberately = useCallback(<T,>(act: () => T): T => {
    deliberate.current += 1;
    // Settles after the act AND after the task it ran in, so a `navigate` the
    // act schedules on resolve (`onCommitted`, a park's `onParked`) still
    // counts as the act's own.
    const done = () => {
      window.setTimeout(() => {
        deliberate.current = Math.max(0, deliberate.current - 1);
      }, 0);
    };
    let result: T;
    try {
      result = act();
    } catch (error) {
      done();
      throw error;
    }
    if (result instanceof Promise) {
      void result.then(done, done);
    } else {
      done();
    }
    return result;
  }, []);

  // Tab close / reload — the browser's own words; `returnValue` is required by
  // some browsers to show the prompt at all.
  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!isActive() || deliberate.current > 0) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isActive]);

  const dataRouter = useContext(UNSAFE_DataRouterContext);
  const element =
    dataRouter === null ? null : (
      <LeaveBlocker
        isActive={isActive}
        isDeliberate={() => deliberate.current > 0}
        draft={options.draft}
        onLeaving={release}
      />
    );

  return {
    touch: { onChangeCapture: markTouched, onInputCapture: markTouched },
    release,
    deliberately,
    element,
  };
}

/** The `?tab=` a page's own tab strip writes — a tab change on the same path
 *  unmounts a wizard living in a tab as surely as a different path does. */
function tabOf(location: Location): string | null {
  return new URLSearchParams(location.search).get("tab");
}

function LeaveBlocker(props: {
  isActive: () => boolean;
  isDeliberate: () => boolean;
  draft: LeaveDraft | null;
  onLeaving: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToastIfMounted();
  const activeRef = useRef(props.isActive);
  activeRef.current = props.isActive;
  const deliberateRef = useRef(props.isDeliberate);
  deliberateRef.current = props.isDeliberate;

  const blocker = useBlocker(
    useCallback(
      ({ currentLocation, nextLocation }: { currentLocation: Location; nextLocation: Location }) => {
        if (!activeRef.current() || deliberateRef.current()) return false;
        const state = nextLocation.state as { leaveGuard?: string } | null;
        if (state?.leaveGuard === LEAVE_DELIBERATELY.leaveGuard) return false;
        // The wizard's own step changes and resume handles (`?step=`,
        // `?parked=`) keep the path; only leaving the screen is asked about.
        return (
          currentLocation.pathname !== nextLocation.pathname ||
          tabOf(currentLocation) !== tabOf(nextLocation)
        );
      },
      [],
    ),
  );

  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  if (blocker.state !== "blocked") return null;

  const stay = () => {
    setFailed(false);
    blocker.reset();
  };
  const leave = () => {
    props.onLeaving();
    blocker.proceed();
  };
  const saveAndLeave = async () => {
    if (props.draft === null) return;
    setSaving(true);
    setFailed(false);
    let ok = false;
    try {
      ok = (await props.draft.onSave()).ok;
    } catch {
      ok = false;
    }
    setSaving(false);
    if (!ok) {
      // Never leave on a failed save — the work is still only on this screen.
      setFailed(true);
      return;
    }
    toast(props.draft.savedMessage);
    props.onLeaving();
    blocker.proceed();
  };

  const withDraft = props.draft !== null;
  return (
    <ModalShell
      title={withDraft ? t("leaveGuard.draft.title") : t("leaveGuard.discard.title")}
      onClose={stay}
      role="alertdialog"
    >
      <div className="modal-body" data-leave-guard={withDraft ? "draft" : "discard"}>
        <p className="m-0 text-md leading-body">
          {withDraft ? t("leaveGuard.draft.body") : t("leaveGuard.discard.body")}
        </p>
        {failed && (
          <p className="m-0 mt-3 text-md leading-body text-danger-700" role="alert" data-leave-guard-failed="">
            {t("leaveGuard.saveFailed")}
          </p>
        )}
      </div>
      <div className="modal-foot">
        <Button variant="ghost" disabled={saving} onClick={stay} data-leave-guard-action="stay">
          {t("leaveGuard.stay")}
        </Button>
        <Button
          variant={withDraft ? "secondary" : "danger"}
          disabled={saving}
          onClick={leave}
          data-leave-guard-action="leave"
        >
          {t("leaveGuard.leave")}
        </Button>
        {withDraft && (
          <WorkingButton working={saving} onClick={() => void saveAndLeave()}>
            <span data-leave-guard-action="save">{t("leaveGuard.saveDraft")}</span>
          </WorkingButton>
        )}
      </div>
    </ModalShell>
  );
}
