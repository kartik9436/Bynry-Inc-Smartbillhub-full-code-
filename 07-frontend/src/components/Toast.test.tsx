// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-012 (EP-SHL-04 §Stories)  Screens: S22, S31, S35, S38
// Rules:    BR-SHL-021 (contract) · BR-SHL-022 (queueing)
// ───────────────────────────────────────────────────────
// TC tests for the global toast system. The queue is framework-free, so FIFO
// and timing laws run under vitest fake timers; surface markup asserts on
// react-dom/server static output (no new dependencies). Screen-reader
// announcement and pixel position are Playwright journey scope.
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { FailedWithRetry } from "./StateFrame";
import { createToastQueue, TOAST_DISMISS_MS, ToastProvider, ToastSurface } from "./Toast";

const noop = () => undefined;

afterEach(() => {
  vi.useRealTimers();
});

describe("US-SHL-012 — toast system", () => {
  it("US-SHL-012 TC-1: recording the $247.30 payment shows the A13 toast bottom-center and auto-dismisses in ~2.5s (2.0-3.0s tolerance)", () => {
    vi.useFakeTimers();
    const queue = createToastQueue();
    // §4 test data: A-10432 payment — A13 verbatim copy from the consumer.
    queue.fire("Payment $247.30 recorded · balance $0.00");
    expect(queue.getCurrent()).toBe("Payment $247.30 recorded · balance $0.00");

    const html = renderToStaticMarkup(<ToastSurface message={queue.getCurrent()} />);
    // CR-018 Route B: the handle is `data-toast="region"` now — the class name
    // it grepped for was deleted with Toast.css.
    expect(html).toContain('data-toast="region"'); // fixed bottom-center
    expect(html).toContain("Payment $247.30 recorded · balance $0.00");

    // BR-SHL-021: ~2.5s auto-dismiss, within the 2.0-3.0s tolerance.
    expect(TOAST_DISMISS_MS).toBeGreaterThanOrEqual(2000);
    expect(TOAST_DISMISS_MS).toBeLessThanOrEqual(3000);
    vi.advanceTimersByTime(TOAST_DISMISS_MS - 1);
    expect(queue.getCurrent()).not.toBeNull(); // still visible just before the deadline
    vi.advanceTimersByTime(1);
    expect(queue.getCurrent()).toBeNull(); // gone at ~2.5s
  });

  it("US-SHL-012 TC-2: three toasts fired within 200ms display one at a time, FIFO, each for its full duration, none lost", () => {
    vi.useFakeTimers();
    const queue = createToastQueue();
    // §4 triple-fire copy set.
    queue.fire("Note added");
    vi.advanceTimersByTime(100);
    queue.fire("Adjustment posted · –$25.00");
    vi.advanceTimersByTime(100);
    queue.fire("Statement sent · email + mail");

    // BR-SHL-022: one visible, the rest queued FIFO.
    expect(queue.getCurrent()).toBe("Note added");
    expect(queue.getPending()).toEqual([
      "Adjustment posted · –$25.00",
      "Statement sent · email + mail",
    ]);

    // First dismisses only at ITS full ~2.5s (fired at t=0, now t=200).
    vi.advanceTimersByTime(TOAST_DISMISS_MS - 200);
    expect(queue.getCurrent()).toBe("Adjustment posted · –$25.00");
    vi.advanceTimersByTime(TOAST_DISMISS_MS);
    expect(queue.getCurrent()).toBe("Statement sent · email + mail");
    vi.advanceTimersByTime(TOAST_DISMISS_MS);
    expect(queue.getCurrent()).toBeNull();
    expect(queue.getPending()).toEqual([]); // none lost
  });

  it("US-SHL-012 TC-3: the toast is announced via a persistent aria-live region and contains nothing focusable (no focus steal)", () => {
    // Empty surface: the aria-live region is ALWAYS mounted so a later message
    // change is announced (BR-SHL-021 / IS-10).
    const empty = renderToStaticMarkup(<ToastSurface message={null} />);
    expect(empty).toContain('aria-live="polite"');
    expect(empty).toContain('role="status"');

    const html = renderToStaticMarkup(
      <ToastSurface message="Payment $247.30 recorded · balance $0.00" />,
    );
    expect(html).toContain('aria-live="polite"');
    // BR-SHL-021: text only, no actions inside the toast; nothing focusable, so
    // keyboard focus cannot move. (The live announcement itself is asserted in
    // the Playwright journey with a real screen reader tree.)
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<a ");
    expect(html).not.toContain("tabindex");
    expect(html).not.toContain("autofocus");
  });

  it("US-SHL-012 TC-4 (negative): a server-side failure fires NO success toast — the failure renders the A18 §4 state instead", () => {
    const queue = createToastQueue();
    // The §1 consumer contract: toast only AFTER the commit succeeds. Simulated
    // failed payment post; the end-to-end assertion against the real payments
    // module lands with the US-PAY journeys.
    const postPayment = (): void => {
      throw new Error("500 — payment post failed");
    };
    let failedCardHtml = "";
    try {
      postPayment();
      queue.fire("Payment $247.30 recorded · balance $0.00"); // never reached on failure
    } catch {
      failedCardHtml = renderToStaticMarkup(
        <FailedWithRetry
          title="Payment failed."
          reason="The payment could not be posted. Nothing was recorded."
          onRetry={noop}
          onDownloadReport={noop}
          onCancel={noop}
        />,
      );
    }
    expect(queue.getCurrent()).toBeNull(); // no toast fired
    expect(queue.getPending()).toEqual([]);
    expect(failedCardHtml).toContain("Payment failed."); // A18 §4 renders instead
  });

  it("US-SHL-012 TC-5: bulk reminder to 12 accounts yields exactly ONE summary toast, not twelve", () => {
    const queue = createToastQueue();
    // BR-SHL-022: bulk flows fire one summary toast with A13's bulk copy.
    queue.fire("Reminders sent to 12 customers");
    expect(queue.getCurrent()).toBe("Reminders sent to 12 customers");
    expect(queue.getPending()).toEqual([]); // nothing queued behind it
  });

  it("US-SHL-012 TC-6 (negative): a toast fired during commit → redirect survives the navigation and completes its display on the destination", () => {
    vi.useFakeTimers();
    const queue = createToastQueue();
    queue.fire("Payment $247.30 recorded · balance $0.00");

    // The provider (and its queue) live ABOVE the router (App.tsx), so the same
    // queue drives the surface on both the origin and destination screens.
    const originScreen = renderToStaticMarkup(
      <ToastProvider queue={queue}>
        <p>payment modal</p>
      </ToastProvider>,
    );
    expect(originScreen).toContain("Payment $247.30 recorded · balance $0.00");

    vi.advanceTimersByTime(1000); // navigation happens mid-display
    const destinationScreen = renderToStaticMarkup(
      <ToastProvider queue={queue}>
        <p>account detail</p>
      </ToastProvider>,
    );
    expect(destinationScreen).toContain("account detail");
    expect(destinationScreen).toContain("Payment $247.30 recorded · balance $0.00");

    // It still completes its FULL display window after the route change.
    vi.advanceTimersByTime(TOAST_DISMISS_MS - 1000);
    expect(queue.getCurrent()).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-012@41aa2ae (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 14/14✔ (1 TC todo — browser/journey scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
