// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-007 (S53 log repair / inspection / test + the status transition) ·
//           US-AST-008 (S54 retire — terminal) · US-AST-009 (S55 reassign + final read)
//           Screens: S53, S54, S55 (entered from S49 row actions and the S50 header)
// Rules:    BR-AST-018 (maintenance is APPEND-ONLY — corrections are new entries) ·
//           BR-AST-020 (transitions are exactly A5 v4; illegal targets refused server-side) ·
//           BR-AST-021 (retire needs reason + date; optional same-tenant replacement) ·
//           BR-AST-022 (reassign captures a final read — the server REFUSES the whole move
//           when it cannot take one) · BR-AST-030 (retire is TERMINAL — no un-retire path
//           exists anywhere; the correction is a NEW asset with a linked audit note) ·
//           BR-AST-031 (stages are Reference data with a behavior class) ·
//           BR-AST-032 (retire = System Admin only; the server enforces) ·
//           BR-AST-036/037 (bulk assign is inventory→unit only; a parent move carries its
//           children by default and an independent sub-meter move warns) ·
//           BR-AST-038 (the Billing Clerk may perform repair transitions) ·
//           BR-SHL-032 (a confirm NAMES the action) · BR-SHL-033 (date pickers; searchable
//           long lists) · BR-SHL-034 (dates through the shared formatter)
// ───────────────────────────────────────────────────────
// ⚠ **THE MODALS ARE GONE FROM THIS FILE — the LAW stayed (CR-028 AST-W4,
// PO 2026-08-22: "as per r10 - it is not modal").** S53/S54/S55 are full-page
// screens now: AssetFlowPages.tsx (AST-06 reassign · AST-07 log repair/test)
// and AssetRetireWizard.tsx (AST-08). What remains here is the PURE, provable
// half every one of those pages consumes:
//
//   · **BR-AST-020/031's transition law** — SEEDED_TRANSITIONS +
//     transitionAllowed + legalTargets, mirrored from the server so a select
//     never offers a choice the server will refuse; the server re-checks and
//     its 409 is what governs.
//   · **The catalog constants** (kinds · retire reasons) and warning-key /
//     failure-key mappers — an unknown code still renders, as its code.
//   · **The schemas** (client validation is UX only — the SERVER is
//     authoritative) and `useReassignMutation`, the registry's one-click
//     inventory assign.
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { reassignAsset } from "@/api/endpoints";
import type {
  LookupEntry,
  MaintenanceKind,
  RetireReason,
  ServerWarning,
  UnitRow,
} from "@/api/endpoints";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const MAINTENANCE_KIND_VALUES: readonly MaintenanceKind[] = [
  "repair",
  "inspection",
  "test",
];

/** BR-AST-021: the four ratified reasons — the server's own set, in its order. */
export const RETIRE_REASON_VALUES: readonly RetireReason[] = [
  "end_of_life",
  "failed",
  "replaced",
  "removed",
];

export const STAGE_AVAILABLE = "available";
export const STAGE_IN_SERVICE = "in_service";
export const STAGE_OUT_OF_SERVICE = "out_of_service";
export const STAGE_TERMINAL = "terminal";

/** One lifecycle stage as `GET /lookups/asset_statuses` serves it. */
export interface StageOption {
  code: string;
  name: string;
  behaviorClass: string;
}

export function stageOptionsFrom(entries: readonly LookupEntry[] | undefined): StageOption[] {
  return (entries ?? [])
    .filter((entry) => entry.active)
    .map((entry) => ({
      code: entry.code,
      name: entry.name,
      behaviorClass: String(entry.behavior_class ?? ""),
    }));
}

// BR-AST-020 / A5 v4: the exact edges for the SEEDED stage codes. A tenant-added
// stage is not in this map and falls through to the behavior-class rule below —
// the same two-tier law the server applies, mirrored so the SELECT does not
// offer a choice the server will refuse.
export const SEEDED_TRANSITIONS: Record<string, readonly string[]> = {
  inventory: [],
  active: ["needs_repair"],
  needs_repair: ["in_repair"],
  in_repair: ["active"],
  retired: [], // terminal — no transition leaves it (BR-AST-030)
};

export function transitionAllowed(current: StageOption, target: StageOption): boolean {
  if (current.code === target.code) {
    return true; // "no change" is always a legal Set-status choice
  }
  if (current.behaviorClass === STAGE_TERMINAL) {
    return false; // BR-AST-020/030: retired is terminal, forever
  }
  if (current.code in SEEDED_TRANSITIONS && target.code in SEEDED_TRANSITIONS) {
    return SEEDED_TRANSITIONS[current.code].includes(target.code);
  }
  if (target.behaviorClass === STAGE_TERMINAL) {
    return false; // only the retire service reaches a terminal stage
  }
  return (
    [STAGE_IN_SERVICE, STAGE_OUT_OF_SERVICE].includes(current.behaviorClass) &&
    [STAGE_IN_SERVICE, STAGE_OUT_OF_SERVICE].includes(target.behaviorClass)
  );
}

export function legalTargets(stages: readonly StageOption[], currentCode: string): StageOption[] {
  const current = stages.find((stage) => stage.code === currentCode);
  if (current === undefined) {
    return [];
  }
  return stages.filter((stage) => transitionAllowed(current, stage));
}

/**
 * BR-AST-037: the warnings a reassign can come back carrying, rendered from
 * their CODES. An unknown code still renders — as its code — because a warning
 * the client does not recognise is still the server telling the user something.
 */
export function reassignWarningKey(warning: ServerWarning): string {
  if (warning.code === "independent_sub_meter_move") {
    return "assets.reassign.warning.independentSubMeter";
  }
  if (warning.code === "children_not_moved") {
    return "assets.reassign.warning.childrenNotMoved";
  }
  return "assets.reassign.warning.generic";
}

export const assetStagesQueryKey = ["lookups", "asset_statuses"] as const;
export const assetUnitPickerKey = ["units", "asset-picker"] as const;
export const assetTechPickerKey = ["users", "asset-tech-picker"] as const;

export function unitPickerOptions(
  rows: readonly UnitRow[] | undefined,
): { value: string; label: string }[] {
  return (rows ?? []).map((row) => ({
    value: row.id,
    label: [row.premise_address ?? row.premise_no, row.label ?? row.unit_no]
      .filter((part) => part !== null && part !== undefined && part !== "")
      .join(" · "),
  }));
}

// ── Bulk assign (BR-AST-036/038) ───────────────────────────────────────────

/**
 * BR-AST-036: inventory→unit ONLY. The batch reports per-asset failures with
 * `reason: "not_inventory"` and the alternative the rule names — no bulk
 * unit→unit path exists anywhere, in this modal or out of it (BR-AST-038).
 */
export function bulkAssignFailureKey(reason: string): string {
  if (reason === "not_inventory") {
    return "assets.bulk.error.notInventory";
  }
  if (reason === "unknown_asset") {
    return "assets.bulk.error.unknownAsset";
  }
  return "assets.bulk.error.generic";
}

// ── Schemas (client validation is UX only — the SERVER is authoritative) ───

export function maintenanceSchema(t: Translator) {
  return z.object({
    kind: z.string(),
    date: z.string(),
    detail: z.string().trim().min(1, t("assets.maintenance.detailRequired")),
    status: z.string(),
    tech_user_id: z.string(),
  });
}

export function retireSchema(t: Translator) {
  return z.object({
    reason: z.string().trim().min(1, t("assets.retire.reasonRequired")),
    retire_date: z.string(),
    replaced_by: z.string(),
  });
}

export function reassignSchema(t: Translator) {
  return z
    .object({
      destination: z.string(),
      unit_id: z.string(),
      effective_date: z.string(),
      record_final_read: z.boolean(),
      final_read_value: z.string(),
      move_children: z.boolean(),
    })
    .superRefine((values, ctx) => {
      if (values.destination === "unit" && values.unit_id.trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["unit_id"],
          message: t("assets.reassign.unitRequired"),
        });
      }
    });
}

/** The mutation helper the registry uses for a one-click inventory assign. */
export function useReassignMutation(
  client: ApiClient,
  onDone: (warnings: ServerWarning[]) => void,
  onFail: (message: string) => void,
  t: Translator,
) {
  return useMutation({
    mutationFn: (input: { assetId: string; unitId: string; effectiveDate?: string }) =>
      reassignAsset(
        input.assetId,
        {
          unit_id: input.unitId,
          effective_date: input.effectiveDate,
          record_final_read: false, // an inventory row has no read to take
        },
        client,
      ),
    onSuccess: (result) => onDone(result.warnings),
    onError: (error: unknown) => onFail(apiErrorText(error, t)),
  });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-008@e1a4db0 (story+rules snapshot hash — EP-AST-03 lifecycle; co-stories US-AST-007@e1a4db0 · US-AST-009@e1a4db0)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (the THREE MODAL COMPONENTS are DELETED — B16 §5.2 as amended, no flow is a modal; the full pages live in AssetFlowPages.tsx + AssetRetireWizard.tsx and consume the pure law kept here: transitions, catalogs, schemas, warning keys, useReassignMutation)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test
// exceptions: E3 the final-read capture cannot succeed on this deployment: `meter_reads` is the W2 reads lane's table and the seam returns None, so BR-AST-022 makes the server refuse the WHOLE move (422 BIZ-COMPLETENESS `assets.final_read_capture_unavailable`) — the modal renders that refusal and the asset stays put, which is the rule working, not a defect to route around · E3 `GET /users` is System-Admin-only, so for a Billing Clerk (who MAY log a repair per BR-AST-038) the tech picker degrades from the searchable select to an id field with the reason on it · E4 the transition table is MIRRORED from the server's `MAINTENANCE_TRANSITIONS` + behavior-class fallback so the Set-status select never offers a choice the server will refuse; the server re-checks and its 409 remains the law
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
