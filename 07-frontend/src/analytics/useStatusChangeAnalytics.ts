// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 §2 — `work_order_status_changed` (`from`, `to`), the
//          two status WORDS only. It watches the record a screen already
//          holds, so every act that moves the status — hold, resume, cancel,
//          accept — is counted by one line rather than by one call per button.
// Tests:   src/analytics/useStatusChangeAnalytics.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useEffect, useRef } from "react";

import { track } from "./client";

export function useWorkOrderStatusAnalytics(orderId: string | null | undefined, status: string | null | undefined): void {
  const seen = useRef<{ id: string; status: string } | null>(null);
  useEffect(() => {
    if (!orderId || !status) {
      return;
    }
    const before = seen.current;
    seen.current = { id: orderId, status };
    // A different order, or the first read of this one, is not a change.
    if (before === null || before.id !== orderId || before.status === status) {
      return;
    }
    track("work_order_status_changed", { from: before.status, to: status });
  }, [orderId, status]);
}
