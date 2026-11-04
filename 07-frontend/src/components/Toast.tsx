// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-012 (EP-SHL-04 §Stories)  Screens: S22, S31, S35, S38 (global surface, all screens)
// Rules:    BR-SHL-021 (contract) · BR-SHL-022 (queueing)
// ───────────────────────────────────────────────────────
// FE-08 Toast (B13 §1): the ONE global toast system. Consuming modules fire
// toasts with their A13 verbatim copy after a COMMITTED action; this file owns
// queueing, timing, position, and accessibility. A toast is feedback only —
// the durable record of any money action is its audit_log row (CLAUDE.md #7),
// never the toast.
import { createContext, useContext, useRef, useSyncExternalStore } from "react";
import type { ReactNode } from "react";


// BR-SHL-021: auto-dismiss after ~2.5s (README §Interactions, A13).
export const TOAST_DISMISS_MS = 2500;

export interface ToastQueue {
  fire: (message: string) => void;
  dismissCurrent: () => void;
  getCurrent: () => string | null;
  getPending: () => readonly string[];
  subscribe: (listener: () => void) => () => void;
}

// The queue is plain state + setTimeout, framework-free, so its FIFO and
// timing laws are testable without a browser (B8 LAW 0: boring and explicit).
export function createToastQueue(): ToastQueue {
  let current: string | null = null;
  const pending: string[] = [];
  let timer: ReturnType<typeof setTimeout> | undefined;
  const listeners = new Set<() => void>();

  function notify(): void {
    for (const listener of listeners) {
      listener();
    }
  }

  function show(message: string): void {
    current = message;
    // BR-SHL-021: every toast auto-dismisses after ~2.5s — no user action needed.
    timer = setTimeout(dismissCurrent, TOAST_DISMISS_MS);
    notify();
  }

  function dismissCurrent(): void {
    clearTimeout(timer);
    current = null;
    const next = pending.shift();
    if (next === undefined) {
      notify();
    } else {
      // BR-SHL-022: queued toasts display sequentially, each with its FULL ~2.5s.
      show(next);
    }
  }

  function fire(message: string): void {
    if (current === null) {
      show(message);
    } else {
      // BR-SHL-022: one toast visible at a time; later fires queue FIFO, none lost.
      pending.push(message);
    }
  }

  return {
    fire,
    dismissCurrent,
    getCurrent: () => current,
    getPending: () => [...pending],
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

// The rendered surface: a persistent bottom-center aria-live region.
export function ToastSurface(props: { message: string | null }) {
  return (
    // BR-SHL-021: the aria-live region stays mounted so assistive tech
    // announces message changes; rendering a toast never moves keyboard focus
    // (nothing here is focusable) and the content is text only — no actions.
    // CR-018 Route B: Toast.css (deleted) ported value for value. The region:
    // fixed bottom-center (bottom-6 = --space-6 24px, left-1/2 + translate),
    // z-60, pointer-events-none — text-only feedback, never a click target.
    // The toast: r10's ink chip — bg-text text-bg, py-3 (12px) px-5 (20px),
    // heading font at 600/--text-base, shadow-lg, gap-2.5 (10px); rounded-md
    // is the ported --radius-md, which the Modernist theme pins to 0. The dot:
    // 8px accent square (w-2 h-2). `data-toast="region"` carries the machine
    // handle the class name used to double as.
    <div
      className="pointer-events-none fixed bottom-6 left-1/2 z-60 -translate-x-1/2"
      data-toast="region"
      aria-live="polite"
      role="status"
    >
      {props.message !== null && (
        <div className="flex items-center gap-2.5 rounded-md bg-text px-5 py-3 font-heading text-base font-semibold text-bg shadow-lg">
          <span className="inline-block h-2 w-2 bg-accent" aria-hidden="true" />
          {props.message}
        </div>
      )}
    </div>
  );
}

const ToastContext = createContext<ToastQueue | null>(null);

// Mounted ONCE, above the router (App.tsx), so an in-flight toast survives a
// commit → redirect navigation and completes its display on the destination
// screen. The optional `queue` prop lets tests drive a queue they also inspect.
export function ToastProvider(props: { children: ReactNode; queue?: ToastQueue }) {
  const ownQueue = useRef<ToastQueue | null>(null);
  if (ownQueue.current === null) {
    ownQueue.current = createToastQueue();
  }
  const queue = props.queue ?? ownQueue.current;
  const current = useSyncExternalStore(queue.subscribe, queue.getCurrent, queue.getCurrent);
  return (
    <ToastContext.Provider value={queue}>
      {props.children}
      <ToastSurface message={current} />
    </ToastContext.Provider>
  );
}

// The toast API consuming modules call after a committed action, with A13
// verbatim copy (externalized per IS-8 in the CONSUMER's catalog keys).
// Failures never fire a toast — they render A18 §4/§5 states (US-SHL-012 TC-4).
export function useToast(): (message: string) => void {
  const queue = useContext(ToastContext);
  if (queue === null) {
    throw new Error("useToast must be used inside <ToastProvider>");
  }
  return queue.fire;
}

/** `useToast` for a SHARED component that may be mounted without a provider —
 *  the leave-page guard inside `WizardFrame`, whose unit tests mount it bare.
 *  Fires nothing when there is no provider; never throws. `DEF-SHL-10001`. */
export function useToastIfMounted(): (message: string) => void {
  const queue = useContext(ToastContext);
  return queue === null ? () => undefined : queue.fire;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-012@41aa2ae (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 14/14✔ (1 TC todo — browser/journey scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
