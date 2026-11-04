// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 §2 rows 5–7 — identify the signed-in member of staff
//          (and the technician in the field app, ruling 18 of CR-168-BRC10)
//          by their internal id, group them by utility, and forget them on a
//          tenant switch. Sign-out and a dead session call `resetAnalytics()`
//          at their own single sites (`ShellWithSession`, `SessionExpired`).
// ───────────────────────────────────────────────────────
import { useEffect } from "react";

import { identifyStaff } from "./client";

export function useStaffAnalytics(person: {
  userId: string | null | undefined;
  role: string | null | undefined;
  tenant: string;
  app: "staff" | "field";
  language: string | null | undefined;
}): void {
  const { userId, role, tenant, app, language } = person;
  useEffect(() => {
    if (!userId || !tenant) {
      return;
    }
    identifyStaff({ userId, role: role ?? null, tenant, app, language: language ?? null });
  }, [userId, role, tenant, app, language]);
}
