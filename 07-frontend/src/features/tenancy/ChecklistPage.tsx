// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-003 (EP-TEN-03 §Stories)  Screens: S62
// Rules:    BR-TEN-015 (state COMPUTED from live data; manual mark-done for advisory items only) ·
//           BR-TEN-016 (mark-done/dismiss audited server-side) · BR-SHL-020 (six shared states, plain language)
// ───────────────────────────────────────────────────────
// S62 post-signup checklist. Entry is automatic after S114; re-entry from the
// dashboard until every item is complete.
//
// BR-TEN-015 is the whole design: this page NEVER computes completion. It
// renders `GET /tenants/checklist`, which derives each item from live tenant
// data at read time. Filling the Company profile in Settings completes that
// item with no click here (US-TEN-003 TC-2) — so there is no client-side
// predicate to drift out of step with the server's.
// Manual mark-done exists ONLY for advisory items; a computed item's control
// is not rendered at all (the server refuses it with 409 BIZ-STATE anyway —
// UI gating is convenience, the server is the boundary).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { dismissChecklistItem, getChecklist } from "@/api/endpoints";
import type { Checklist, ChecklistItem } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button, ButtonLink } from "@/components/Button";
import { StatusPill } from "@/components/StatusPill";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { Kicker } from "@/components/TextBits";
import { useTenantPath } from "@/routing/tenantPath";


// ── Pure pieces ────────────────────────────────────────────────────────────

export const DASHBOARD_ROUTE = "/dashboard";

/**
 * The server sends a path FRAGMENT ("settings/company"); this makes it a
 * tenant-RELATIVE route. The tenant segment is added by `tenantPath()` at the
 * link, so the server never has to know which tenant it is talking to twice.
 */
export function checklistTargetPath(target: string): string {
  return target.startsWith("/") ? target : `/${target}`;
}

/** "Continue setup →" lands on the first thing still missing. */
export function firstIncomplete(items: readonly ChecklistItem[]): ChecklistItem | null {
  return items.find((item) => !item.done) ?? null;
}

/** Item copy is keyed by the server's stable item code — never by its position. */
export function itemTitleKey(item: string): string {
  return `tenancy.checklist.item.${item}.title`;
}

export function itemDescKey(item: string): string {
  return `tenancy.checklist.item.${item}.desc`;
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface ChecklistPageProps {
  client?: ApiClient; // test seam
}

export function ChecklistPage(props: ChecklistPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const queryClient = useQueryClient();

  const checklistQuery = useQuery({
    queryKey: queryKeys.checklist,
    queryFn: () => getChecklist(client),
  });

  const markDone = useMutation({
    mutationFn: (item: string) => dismissChecklistItem(item, client),
    // No optimistic write (FI-02): the answer IS the recomputed checklist, so
    // the cache takes the server's truth, never a guess made here.
    onSuccess: (next: Checklist) => queryClient.setQueryData(queryKeys.checklist, next),
  });

  if (checklistQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }

  if (checklistQuery.data === undefined) {
    const error = checklistQuery.error;
    return (
      // A18 §4 with a retry that re-issues the identical request.
      <FailedWithRetry
        title={t("tenancy.checklist.failedTitle")}
        reason={refusalText(t, error)}
        onRetry={() => void checklistQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  const checklist = checklistQuery.data;
  const next = firstIncomplete(checklist.items);

  // CR-018 Route B: ChecklistPage.css (deleted) ported value for value — the
  // 720px column, the h3-sized title on the real h1 (same heading tokens
  // global.css already gives it; only the size differs), the 70%/65% inks
  // written long-hand in srgb, and the done/open item state as two full
  // utility strings. `data-page="checklist"` carries the machine handle.
  return (
    <div className="max-w-[720px]" data-page="checklist">
      <Kicker>{t("tenancy.checklist.kicker")}</Kicker>
      <h1 className="my-2 text-h3">{t("tenancy.checklist.title")}</h1>
      <p className="m-0 mb-4 max-w-measure text-body text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">{t("tenancy.checklist.lede")}</p>

      <p className="m-0 mb-4 font-heading text-sm font-extrabold text-accent">
        {t("tenancy.checklist.progress", {
          done: checklist.progress.done,
          total: checklist.progress.total,
        })}
      </p>

      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {checklist.items.map((item) => (
          <li
            key={item.item}
            data-checklist-item={item.done ? "done" : "open"}
            className={
              item.done
                ? "flex items-start gap-3 border-l-3 border-l-success-500 bg-surface p-4"
                : "flex items-start gap-3 border-l-3 border-l-divider bg-surface p-4"
            }
          >
            {/* The 22px tick box; done swaps its chrome for success-500. */}
            <span
              className={
                item.done
                  ? "flex h-[22px] w-[22px] flex-none items-center justify-center border-2 border-success-500 bg-success-500 font-heading text-sm font-extrabold text-bg"
                  : "flex h-[22px] w-[22px] flex-none items-center justify-center border-2 border-divider bg-bg font-heading text-sm font-extrabold"
              }
              aria-hidden="true"
            >
              {item.done ? "✓" : ""}
            </span>
            <div className="flex-1">
              {/* Each item deep-links to the Settings tab that fills it. */}
              <Link className="font-heading text-md font-extrabold text-text" to={tenantPath(checklistTargetPath(item.target))}>
                {t(itemTitleKey(item.item))}
              </Link>
              <p className="m-0 mt-1 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t(itemDescKey(item.item))}</p>
            </div>
            <span className="flex-none">
              {item.done ? (
                // BR-TEN-015: complete BECAUSE the data is there, or because an
                // advisory item was marked — the server says which.
                // CR-018 Route B: was a raw `pill ok` span — the exact DEF-244
                // shape the DashboardPage warning describes, live-but-fragile
                // because StatusPill.css was imported by StatusPill.tsx only.
                // The component renders the identical chip and owns its styling.
                <StatusPill tone="success">
                  {item.source === "manual"
                    ? t("tenancy.checklist.markedDone")
                    : t("tenancy.checklist.complete")}
                </StatusPill>
              ) : (
                item.kind === "advisory" && (
                  <Button
                    variant="ghost"
                    disabled={markDone.isPending}
                    onClick={() => markDone.mutate(item.item)}
                  >
                    {t("tenancy.checklist.markDone")}
                  </Button>
                )
              )}
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-8 flex justify-end gap-2">
        {/* US-TEN-003 TC-3: "Finish later" opens the app; the entry point stays
            reachable and the state is server-side, so it survives the session. */}
        <Button variant="ghost"  onClick={() => navigate(tenantPath(DASHBOARD_ROUTE))}>
          {t("tenancy.checklist.finishLater")}
        </Button>
        {next !== null && (
          <ButtonLink variant="primary"  to={tenantPath(checklistTargetPath(next.target))}>
            {t("tenancy.checklist.continue")}
          </ButtonLink>
        )}
      </div>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-003@d5f8c32 (story+rules snapshot hash — EP-TEN-03)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 144/144✔ (13 todo this packet — browser/journey/v2-deferred scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 the prototype's per-item "N min" estimates have no field in GET /tenants/checklist — not rendered rather than invented (reported) · E4 deep-link targets "plans-rates" and "settings/users" have no route yet (their screens are later packets)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
