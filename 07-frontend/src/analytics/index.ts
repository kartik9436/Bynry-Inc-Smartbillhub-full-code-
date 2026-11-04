// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 — the ONE door screens use to analytics. A screen
//          imports from `@/analytics` and calls `track(event, props)`.
// ───────────────────────────────────────────────────────
export { currentScreenId, identifyStaff, resetAnalytics, setPageContext, startAnalytics, track } from "./client";
export type { AnalyticsApp } from "./client";
export type { EventName, EventProperties } from "./events";
export { AnalyticsPageViews } from "./AnalyticsPageViews";
export { useStaffAnalytics } from "./useStaffAnalytics";
export { useListAnalytics } from "./useListAnalytics";
export { useWorkOrderStatusAnalytics } from "./useStatusChangeAnalytics";
