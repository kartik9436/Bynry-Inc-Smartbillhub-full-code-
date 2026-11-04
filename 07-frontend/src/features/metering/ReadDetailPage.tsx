// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-013 (S29 read detail — override & dispute) · US-MET-016
//           (the J6 correction linkage this page now RENDERS) · US-AST-012
//           (TC-1: each typed record and its PAIR — ./NetMeterPair, mounted
//           here) · US-MET-012 (S25 — the list whose rows open this page)
//           Change: CR-038 W5 — S29 becomes a FULL PAGE (PO 2026-08-26,
//           verbatim: "i want page to be open for consitency - we dont open
//           side panel", confirmed the same day as a metering rule, verbatim:
//           "no read drawer required" — READS only; other modules' drawers
//           stand until a separate B14 sitting. r10 RDS-04's overlay
//           presentation is OVERRIDDEN, its content is not.)
//           Screens: S29
// Rules:    BR-MET-131 (no read drawer — S29 is a full PAGE; the row now
//           exists in 02-business-rules.md, so this is a normal citation and
//           the lane's deliberate prose-only workaround is retired) ·
//           BR-MET-017 (the permanent compliance stamp) · BR-MET-022 (stored
//           self-describing outcomes) · BR-MET-024 (Override APPENDS; the
//           original stays immutable; the compliance block is display-only) ·
//           BR-MET-028/029 (an estimate: no register value; a lawful flagged
//           bill input) · BR-MET-053 (BILLED locked; the fix routes through
//           J6) · BR-MET-056 (full chain, math shown, flag reason WITH the
//           thresholds used, channel) · BR-SHL-025 (disabled WITH the reason) ·
//           BR-SHL-034 (one date formatter) · B14 rule 21 (a NEW page is
//           Tailwind utilities — the drawer's 29 rd-* content rules are
//           ported to utilities here and DELETED from reads.css; only the
//           genuinely shared commons are still referenced) · DEF-532's law
//           (every navigation target is tenantPath(...))
// ───────────────────────────────────────────────────────
// S29 — one reading, and everything the utility can be asked to prove about it.
//
// This is the retired ReadDetailDrawer's content, re-homed on a route. What
// changed is the FRAME (PageHeader + sections instead of scrim + panel; the
// browser's Back instead of Esc/✕/backdrop) and three sections that stop
// stating absences because the payload caught up with them:
//
//   · TAGS are real — `read_dict` serves service/cycle/route since DEF-045's
//     fix, so the RDS-04 tag row (SERVICE · CYCLE · ROUTE · SOURCE) renders
//     from data;
//   · the PREMISE/UNIT linkage is real, and links to the premises detail;
//     the ACCOUNT is still not served and still says so;
//   · READ HISTORY is real — `GET /assets/{id}/reads` exists (DEF-475 closed,
//     CR-028 AST-W2), so the RDS-04 history table renders instead of the
//     ArrivesWith note that tracked that defect;
//   · CORRECTIONS render — `GET /reads/{id}` has served the J6 linkage rows
//     since US-MET-016 landed and no screen ever drew them.
//
// BR-MET-056 is still the whole design: every number on this page is a STORED
// one. The math line is assembled around the server's own usage_display, the
// flag reason walks the stored outcome bag, the chain is the server's walk of
// `superseded_by_id`, and the history is the reads seam's rows. Nothing here
// computes.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  DISPUTE_BILLED_STANDS,
  READ_STATUS_ESTIMATED,
  clearReadDispute,
  correctBilledRead,
  disputeRead,
  getAssetReads,
  getInvoices,
  getRead,
  getReadBatch,
  supersedeRead,
} from "@/api/endpoints";
import type {
  AssetReadRow,
  InvoiceRow,
  ReadChainEntry,
  ReadCorrectionRow,
  ReadDetail,
  ReadImportBatchDetail,
  ReadRuleOutcome,
} from "@/api/endpoints";
import { Chip } from "@/components/Chip";
import { CustomFieldsView } from "@/components/CustomFields";
import { DateCell, formatDate } from "@/components/DateCell";
import { formatQuantity } from "@/components/UnitCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FormModal, SearchSelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { ListPager } from "@/components/ListPager";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { InlineLinkTo, RefusalStrip } from "@/components/Surfaces";
import { Kicker, Note } from "@/components/TextBits";
import { assetDetailPath } from "@/features/assets/assetsShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { assetReadsQueryKey } from "@/features/assets/AssetDetailPage";
import { ServiceTags } from "@/features/rating/ratingShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DemandResetChip, PeakQuantity, isPeakChannel } from "./demandShared";
import { NetMeterPair } from "./NetMeterPair";
import { FieldPositionPanel } from "./FieldPositionPanel";
import { ReadFormatAnswersPanel } from "./ReadFormatAnswersPanel";
import { toEnvelope } from "./PremisesListPage";
import {
  CELL_FULL,
  Dash,
  GuardedButton,
  PREMISES_PERMISSION,
  ROLE_SYSTEM_ADMIN,
  premisesDetailPath,
  useRegional,
  useAccessCell,
  useTenantRole,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";
import {
  ActorName,
  READS_ROUTE,
  ReadStatusCell,
  flaggedOutcomes,
  outcomeSentence,
  outcomeTally,
  readDetailPath,
  unevaluatedOutcomes,
} from "./readsShared";

import "./reads.css";

// ── CR-018 Route B — the retired drawer's reads.css rules, ported VALUE FOR
// VALUE as utilities (PO 2026-08-26, verbatim: "ensure you are developing Ui
// screens for all using Tailwind , no custom CSS in new UI"). The 29 rd-*
// classes only this screen used are DELETED from reads.css in the same
// commit; what stays referenced here is only the genuinely SHARED commons
// (`met-facts` · `met-panel-hint` · `met-qualifier` · `table`), the same
// posture every migrated file takes ("the shared classes a migrated file
// still keeps"). The three muted inks are color-mix written long-hand in
// srgb — the CR-018 Phase 1 §4 rule; the oklab opacity modifier is not ours.

const MUTED55 = "text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";
const MUTED60 = "text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]";
const MUTED65 = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
/** `.rd-block`'s frame (kept declared for NetMeterPair, written here as utilities). */
const SECTION = "flex flex-col gap-1.5 border-t border-divider pt-3.5";
/** `.met-tag`, ported — this page was its last renderer, so the class retires. */
/* `tracking-label` IS the named 0.04em of this uppercase register (W14). */
const TAG = "border border-divider px-1 text-xs uppercase tracking-label";
/** r10 UI-RULES 18 as amended (PO 80%) — the description measure. */
const MEASURE = "max-w-[var(--desc-measure)]";

// ── Pure pieces (provable without a browser or a network) ─────────────────

export const readDetailQueryKey = (readId: string) => ["reads", "detail", readId] as const;
export const readBatchQueryKey = (batchId: string) => ["read-batches", batchId] as const;

export const LIFECYCLE_BILLED = "billed";

/** BR-MET-049's stored outcome — `validation.RULE_PLAN_REGISTERS`, verbatim.
 *  Named once so the screen and the engine cannot drift over a spelling
 *  (`DEF-2441` was exactly that: a table grouped on the FUNCTION name and drew
 *  nothing over a payload holding every figure). */
export const RULE_PLAN_REGISTERS = "plan_registers";

/** One stored detail value read as a list of channel codes, or nothing.
 *  A rule outcome's `detail` is `Record<string, unknown>` on purpose — it is
 *  self-describing storage (BR-MET-022) — so a reader narrows it rather than
 *  casting, and a bag that does not hold what this screen expects renders
 *  NOTHING instead of `[object Object]`. */
export function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

/**
 * `(current − prior) × multiplier = usage`, assembled from the four STORED
 * values and NEVER evaluated — BR-MET-056's "math shown". The `=` side is the
 * server's own `usage_display`, so the number in the sentence is the number
 * that bills.
 *
 * Null when the read carries no register pair: an estimate has a consumption
 * and no `current_value` (BR-MET-028), and `(— − —) × 1` is a sentence about
 * nothing. The caller renders the estimate line instead.
 *
 * ⚠ **THE OPERANDS ARE SPELLED FOR A READER, AND THE PREFIX IS GONE — `Q9`,
 * PO ruling 2026-09-14 (the blueprint's `B35`).** This line read
 * `Register: (46754.000000 − 44000.000000) × 10.000000 = 27540 kWh` on the
 * running product: a word the drawing does not have, in front of BR-MET-019's
 * `NUMERIC(18,6)` storage column arriving on the wire. The ruling is *a reading
 * displays as drawn — `45910`, not `45910.000000`*.
 *
 * ⚠ **DISPLAY ONLY, AND THAT IS THE WHOLE OF IT.** Nothing stored moves,
 * nothing is re-derived, the arithmetic is untouched and the `=` side is still
 * COPIED from the server — so no ❄️ FROZEN B4/B5 figure is within a mile of it.
 * It goes through `formatQuantity`, the ONE client composer for BR-MET-144 (*at
 * most two decimals, trailing zeros trimmed*, PO 2026-08-27), which is the same
 * function the history table in this file already used — so one screen stops
 * spelling the same quantity two ways (`D6`).
 *
 * ⚠ **IT LIVES HERE AND NOT IN `readsShared.mathLine`, AND THAT IS A SHARED-TREE
 * DECISION RATHER THAN A DESIGN ONE.** `mathLine` is that file's and that file
 * is being rewritten by another lane right now; editing it would have meant
 * pushing their half-finished work with mine (law 11, mechanism five). This
 * screen is `mathLine`'s only renderer, so the two do not disagree on any
 * screen today — and retiring the unrendered twin is a follow-up, REPORTED
 * rather than done from here.
 */
export function calculationLine(read: ReadDetail, t: Translator): string | null {
  if (read.current_value === null || read.prior_value === null || read.usage_display === null) {
    return null;
  }
  return t("metering.read.mathLine", {
    current: formatQuantity(read.current_value),
    prior: formatQuantity(read.prior_value),
    multiplier: formatQuantity(read.multiplier ?? "1"),
    usage: read.usage_display,
  });
}

/**
 * BR-MET-024's "Version: v1 · immutable" line. The version number is the
 * SERVER's — `read_chain` stamps it walking `superseded_by_id` — so a chain
 * this client has never seen renders correctly.
 */
export function versionLine(read: ReadDetail, t: Translator): string {
  const entry = read.chain.find((row) => row.id === read.id);
  const version = entry?.version ?? 1;
  if (read.superseded_by_id !== null) {
    return t("metering.read.versionSuperseded", { version });
  }
  return read.chain.length > 1
    ? t("metering.read.versionHead", { version })
    : t("metering.read.versionImmutable", { version });
}

/**
 * BR-MET-053 + BR-MET-024, as one answer: null means Override is offered.
 *
 * Three states refuse it, and the SERVER refuses each of them too — this only
 * decides which reason to show before the round trip:
 *   · a BILLED read is locked, and its correction must travel with the money
 *     fix through J6 (US-MET-016);
 *   · a read that is no longer the lineage head is not correctable — its
 *     successor is;
 *   · a role without write access is refused by the endpoint.
 */
export function overrideBlockedReason(
  read: ReadDetail,
  writeBlockedReason: string | null,
  t: Translator,
): string | null {
  if (writeBlockedReason !== null) {
    return writeBlockedReason;
  }
  if (read.superseded_by_id !== null) {
    return t("metering.read.action.notHead");
  }
  return null;
}

/**
 * ⚠ **A BILLED READ IS NO LONGER REFUSED ABOVE, AND THAT IS THE WHOLE OF
 * `MR-15` (the blueprint's `D2`).** `overrideBlockedReason` used to answer
 * `metering.read.action.billedLocked` — *"…and that path is not built"* — for
 * every billed read, while the header above it renamed the primary to *Correct
 * billed read*. **The path IS built:** `POST /reads/{id}/billed-correction` is
 * mounted (`api.py:1479`, routed `:3067`), the bill detail screen is live at
 * `/billing/bills/:invoiceId`, and the server's own
 * `metering.read.cascade_billed_recommendation` sends clerks to exactly this
 * door. The product was telling a clerk to use a door and then denying it
 * existed — hard-won law 2's mirror, a live screen behind a dead control.
 *
 * The two states that still refuse are above, and the SERVER refuses each of
 * them too. The billed door carries its own role gate on top
 * (`@require_role(SYSTEM_ADMIN, BILLING_CLERK)`), deliberately not mirrored
 * here: BR-SHL-025 makes the server the boundary, and a second copy of a role
 * list is a second place for it to drift.
 *
 * This only decides WHICH DOOR the one control opens.
 */
export function correctionIsBilled(read: ReadDetail): boolean {
  return read.lifecycle === LIFECYCLE_BILLED;
}

/**
 * BR-MET-024 / the OQ-043 closure, as one answer: null means Dispute is offered.
 *
 * ⚠ **A BILLED READ IS DISPUTABLE AND THAT IS THE POINT.** The billed lock
 * (BR-MET-053) governs CORRECTIONS — changing the number — and a dispute is a
 * claim ABOUT the number, which BR-MET-053 itself calls an *"orthogonal
 * marker"* ("disputed→cleared"). Refusing here would refuse the ordinary case:
 * a customer disputes a reading BECAUSE they got the bill. What the dispute
 * does to that bill is BR-MET-133, and the page says it: the bill stands, the
 * disputed amount does not age, and the fix is a billed correction.
 */
export function disputeBlockedReason(
  read: ReadDetail,
  writeBlockedReason: string | null,
  t: Translator,
): string | null {
  if (writeBlockedReason !== null) {
    return writeBlockedReason;
  }
  if (read.superseded_by_id !== null) {
    return t("metering.read.action.notHead");
  }
  if (read.disputed) {
    return t("metering.read.action.alreadyDisputed");
  }
  return null;
}

/**
 * Clearing is System Admin's alone (OQ-043 closure) and is what releases the
 * account back into the bill run. Null means the control is live.
 */
export function clearDisputeBlockedReason(
  read: ReadDetail,
  role: string | null,
  t: Translator,
): string | null {
  if (!read.disputed) {
    return null; // not rendered at all — see the header actions
  }
  // A null role means `/me/permissions` has not answered; the control is
  // offered and the server's own gate refuses if it must (BR-SHL-025).
  if (role !== null && role !== ROLE_SYSTEM_ADMIN) {
    return t("metering.read.action.clearNeedsAdmin");
  }
  return null;
}

/** BR-MET-024: a dispute is refused without a reason. Same shape as override. */
export function disputeSchema(t: Translator) {
  return z.object({
    reason: z.string().trim().min(1, t("metering.read.dispute_reason_required")),
  });
}

/**
 * Clearing takes an OPTIONAL note, so this schema accepts everything.
 * `meter_reads` has no cleared-reason column (B2 r8) and the note rides into
 * the audit row; requiring it here would be the screen inventing a rule for a
 * field that has nowhere on the read to live.
 */
export function clearDisputeSchema() {
  return z.object({ resolution: z.string() });
}

/** BR-MET-024: a supersede is refused without a reason and without a value ≥ 0. */
export function overrideSchema(t: Translator) {
  return z.object({
    value: z
      .string()
      .trim()
      .min(1, t("metering.read.value_required"))
      .refine((raw) => Number(raw) >= 0, t("metering.read.value_negative")),
    reason: z.string().trim().min(1, t("metering.read.reason_required")),
  });
}

/**
 * BR-MET-053: the billed door takes everything the plain one does AND the
 * INVOICE. That third field is the whole difference between the two doors —
 * *"read fix and money fix travel together"* — and the server refuses without
 * it by name (`metering.read.invoice_required`), so the form asks for it rather
 * than letting a clerk discover the rule from a refusal.
 */
export function billedCorrectionSchema(t: Translator) {
  return overrideSchema(t).extend({
    invoice_id: z.string().trim().min(1, t("metering.read.invoice_required")),
  });
}

// ── The page ───────────────────────────────────────────────────────────────

export interface ReadDetailPageProps extends RegionalProps {
  client?: ApiClient;
}

export function ReadDetailPage(props: ReadDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const readId = params.readId ?? "";
  const { timeZone, dateFormat } = useRegional(props);
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const [overriding, setOverriding] = useState(false);
  const [disputing, setDisputing] = useState(false);
  const [clearing, setClearing] = useState(false);
  // B14 rule 16 / `MR-48` — the HISTORY table's own window. The envelope has
  // carried `total` since `AST-B-19` and this screen threw it away, so a meter
  // past one page drew a truncated table with nothing saying so.
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPer, setHistoryPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  // BR-SHL-025: the server is authoritative and refuses anyway; this only
  // decides whether the control is offered or shown disabled with the reason.
  const cell = useAccessCell(PREMISES_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("metering.read.action.readOnly");
  // OQ-043's closure names a ROLE for one action; A4 grades surfaces, not
  // actions, so the role code answers it (see `useTenantRole`).
  const role = useTenantRole(client);

  const readQuery = useQuery({
    queryKey: readDetailQueryKey(readId),
    queryFn: () => getRead(readId, client),
    enabled: readId !== "",
  });
  const read = readQuery.data;

  const batchId = read?.import_batch_id ?? null;
  const batchQuery = useQuery({
    queryKey: readBatchQueryKey(batchId ?? ""),
    queryFn: () => getReadBatch(batchId as string, client),
    enabled: batchId !== null,
    retry: false,
  });

  // RDS-04's "Read history (this meter)" — REAL rows now: the assets seam
  // serves one meter's reads (DEF-475 closed), and the query key is the asset
  // detail's own, so the two screens share one cache entry.
  // ⚠ **THE PAGE IS PART OF THE KEY, AND THE ASSET DETAIL ALREADY SAID SO.**
  // `assetReadsQueryKey(id, page, per)` has taken a window since `AST-B-19`;
  // this screen called it with the id alone and asked the server for page one,
  // so a meter with years of reads drew fifty rows and nothing else. Passing
  // the window keeps the two screens on ONE cache entry per page rather than
  // fighting over a key that means different things to each of them.
  const historyQuery = useQuery({
    queryKey: assetReadsQueryKey(read?.asset_id ?? "", historyPage, historyPer),
    queryFn: () =>
      getAssetReads(read?.asset_id as string, client, { page: historyPage, per: historyPer }),
    enabled: read !== undefined,
    retry: false,
  });

  const supersede = useMutation({
    mutationFn: (values: { value: string; reason: string }) =>
      supersedeRead(readId, values, client),
    onSuccess: (created) => {
      setOverriding(false);
      void queryClient.invalidateQueries({ queryKey: ["reads"] });
      fireToast(t("metering.read.toast.superseded", { meter: created.meter ?? "" }));
      // BR-MET-024: the answer is a NEW row, so the page moves to it.
      navigate(tenantPath(readDetailPath(created.id)));
    },
    // A refusal (BILLED lock, not-the-head, a required reason) surfaces INSIDE
    // the form through the B12 §3 envelope — one place, where the fix is.
  });

  /**
   * BR-MET-053's OTHER door — the one this screen has been refusing over a live
   * endpoint (`MR-15` · the blueprint's `D2`). The read fix and the money fix
   * travel together, so this lands a NEW head AND a `read_corrections` row
   * naming the invoice. The page follows the new head exactly as the plain
   * override does; the invoice itself is untouched (hard rule 4).
   */
  const correctBilled = useMutation({
    mutationFn: (values: { value: string; reason: string; invoice_id: string }) =>
      correctBilledRead(readId, values, client),
    onSuccess: (created) => {
      setOverriding(false);
      void queryClient.invalidateQueries({ queryKey: ["reads"] });
      fireToast(
        t("metering.read.toast.billedCorrected", {
          meter: created.meter ?? "",
          invoice: created.correction.invoice_no ?? "",
        }),
      );
      navigate(tenantPath(readDetailPath(created.id)));
    },
  });

  /**
   * BR-MET-024's write half. Two invalidations, not one: the READ (so the page
   * repaints from the server rather than from an optimistic guess) and the
   * whole `reads` key — the S25 Disputed chip is a separate query and a chip
   * that stayed at 0 after a dispute was raised would be DEF-046 again.
   */
  const dispute = useMutation({
    mutationFn: (values: { reason: string }) => disputeRead(readId, values, client),
    onSuccess: (updated) => {
      setDisputing(false);
      void queryClient.invalidateQueries({ queryKey: ["reads"] });
      fireToast(
        t(
          updated.dispute.billed_bill_effect === DISPUTE_BILLED_STANDS
            ? "metering.read.toast.disputedBilled"
            : "metering.read.toast.disputed",
          { meter: updated.meter ?? "" },
        ),
      );
    },
  });

  const clearDispute = useMutation({
    mutationFn: (values: { resolution?: string }) =>
      clearReadDispute(readId, values, client),
    onSuccess: (updated) => {
      setClearing(false);
      void queryClient.invalidateQueries({ queryKey: ["reads"] });
      fireToast(t("metering.read.toast.disputeCleared", { meter: updated.meter ?? "" }));
    },
  });

  if (readQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  if (read === undefined) {
    // A cross-tenant or unknown id is an indistinguishable 404 server-side —
    // A18 §4 with the server's own reason, never a blank detail shell.
    return (
      <FailedWithRetry
        title={t("metering.read.failedTitle")}
        reason={apiErrorText(readQuery.error, translate)}
        onRetry={() => void readQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(READS_ROUTE))}
      />
    );
  }

  return (
    <div className="met-page rd-page">
      {/* US-SHL-020's ruled order: back → kicker → H1 + state → actions.
          ⚠ **THE ESTIMATE BUTTON IS GONE — PO ruling 2026-09-12, approved as
          the blueprint's change 2.3, and it is `Q6`'s shape rather than a
          tidy-up.** A control is removed only when its refusal is PERMANENT; a
          refusal that is a STATE is disabled with its reason. Estimation fills
          a MISSING (meter, channel, date) record — this reading EXISTS, so no
          state of this screen could ever enable it, and a control that can
          never become live is not a disabled control but a word in the wrong
          place. Estimating stays reachable from the Reads header and from a
          cycle's shortfall, so nothing is lost with it. And no sentence
          replaces it: B14 rule 33 puts rationale at zero words on screen. */}
      <PageHeader
        backTo={{ to: tenantPath(READS_ROUTE), label: t("metering.reads.title") }}
        // ⚠ **⑪'s OTHER HALF — THE METER NUMBER IS THE LINK BACK TO THE METER
        //     (PO 2026-09-14, the same sentence as the account above).** The
        //     kicker already reads `READING · M-7210 · TOTAL REGISTER` and the
        //     meter number was flat text, so the one identifier a clerk reads
        //     first was the one thing on the header they could not follow.
        //     ⚠ **THE SHAPE AND THE WORDS ARE UNTOUCHED** — `B19`'s three
        //     segments, the same separators, in the same order. `kicker` takes
        //     a `ReactNode` for this (the kit change is `PageHeader`'s, B14
        //     rule 36 — *"where the kit lacks a piece, ADD IT TO THE KIT"*).
        //     ⚠ **AND `see the meter →` IN ⑬ STAYS.** It is drawn, it is
        //     conditional on the plan stating an expected register set, and it
        //     answers a different question — *which sibling register never
        //     arrived* — so it is not this link twice.
        kicker={
          <MeterKicker
            meter={read.meter}
            channel={t(`metering.reads.channel.${read.channel}`, {
              defaultValue: read.channel,
            })}
            href={tenantPath(assetDetailPath(read.asset_id))}
            t={translate}
          />
        }
        title={t("metering.read.title")}
        status={<ReadIdentityChips read={read} t={translate} />}
        secondaryActions={
          <>
            {/* BR-MET-024 / the OQ-043 closure. A BILLED read is disputable on
                purpose — that is the ordinary case — and what it does to the
                issued bill is BR-MET-133, said on screen. */}
            {read.disputed ? (
              <GuardedButton
                label={t("metering.read.action.clearDispute")}
                reason={clearDisputeBlockedReason(read, role, translate)}
                working={clearDispute.isPending}
                onClick={() => setClearing(true)}
              />
            ) : (
              <GuardedButton
                label={t("metering.read.action.dispute")}
                reason={disputeBlockedReason(read, writeBlockedReason, translate)}
                working={dispute.isPending}
                onClick={() => setDisputing(true)}
              />
            )}
          </>
        }
        primaryAction={
          <GuardedButton
            label={
              correctionIsBilled(read)
                ? t("metering.read.action.correctBilled")
                : t("metering.read.action.override")
            }
            reason={overrideBlockedReason(read, writeBlockedReason, translate)}
            variant="primary"
            working={supersede.isPending || correctBilled.isPending}
            onClick={() => setOverriding(true)}
          />
        }
      />

      {/* ⚠ **THE BODY IS NO LONGER ONE 720px COLUMN (`B23`).** The drawing
          splits it: what a clerk reads to JUDGE the number on the left, what
          they read to PROVE where it came from on the right, and at narrow
          widths the right column drops beneath the left with nothing reflowing
          inside a section. Three columns with the left taking two is that
          split without an arbitrary width — the ruled scale governs the gap
          (B14 rule 39) and the grid governs the rest. */}
      <div className="grid grid-cols-1 gap-x-4 lg:grid-cols-3">
        <ReadBody
          read={read}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          batch={batchQuery.data}
          batchError={batchQuery.isError ? apiErrorText(batchQuery.error, translate) : null}
          history={historyQuery.data?.rows}
          historyTotal={historyQuery.data?.total ?? 0}
          historyPage={historyPage}
          historyPer={historyPer}
          onHistoryPage={setHistoryPage}
          onHistoryPer={(per) => {
            setHistoryPer(per);
            setHistoryPage(1); // a new window starts at its own first page
          }}
          historyFailed={historyQuery.isError}
          premisesHref={
            read.premises_id === null ? null : tenantPath(premisesDetailPath(read.premises_id))
          }
          meterHref={tenantPath(assetDetailPath(read.asset_id))}
          accountHref={
            read.account === null ? null : tenantPath(accountDetailPath(read.account.id))
          }
        />
      </div>
      {/* CR-161-BRC10 W4 — the utility's OWN reading fields, read-only (S29).
          Nothing at all when none is placed here. */}
      <CustomFieldsView
        entity="meter_reads"
        screen="S29"
        values={read.custom_data ?? {}}
        formatDate={(iso) => formatDate(iso, timeZone, dateFormat)}
        client={client}
      />

      {/* BR-MET-053's two doors, and the URL a reviewer reads says which one a
          reading takes. Neither is reachable by accident: the plain path
          refuses a billed read server-side and the billed path refuses an
          unbilled one. */}
      {overriding &&
        (correctionIsBilled(read) ? (
          <BilledCorrectionModal
            read={read}
            client={client}
            onSubmit={(values) => correctBilled.mutateAsync(values)}
            onClose={() => setOverriding(false)}
          />
        ) : (
          <OverrideModal
            read={read}
            working={supersede.isPending}
            onSubmit={(values) => supersede.mutateAsync(values)}
            onClose={() => setOverriding(false)}
          />
        ))}

      {disputing && (
        <DisputeModal
          read={read}
          onSubmit={(values) => dispute.mutateAsync(values)}
          onClose={() => setDisputing(false)}
        />
      )}

      {clearing && (
        <ClearDisputeModal
          read={read}
          onSubmit={(values) => clearDispute.mutateAsync(values)}
          onClose={() => setClearing(false)}
        />
      )}
    </div>
  );
}

// ── The body — the drawing's SIX sections, in two columns ──────────────────
//
// TEN SECTIONS BECAME SIX AND NOTHING WAS DROPPED. The merge, exactly:
//   Tags + Premise/unit/account                              → LOCATION
//   Supersession history + Billed corrections + Read history → HISTORY
//   How this usage was worked out                            → CALCULATION
//   Why this reading is flagged                              → FLAGS
//   Compliance metadata                                      → EVIDENCE
// plus the four figures, which stay a BAND rather than four cards.
//
// ⚠ **EACH OF THE FIVE IS A `<Panel>` NOW — the PO's ruling of 2026-09-12,
// verbatim: *"use Panel — a box, 1px border on all four sides, surface fill,
// 16px padding, heading inside … in detail section use Panel to information
// groups"* (`MR-32`).** The local `SECTION` constant drew a rule across the
// top and 14px of air under it — no border at the sides or bottom, no fill —
// which is a shape the drawings render nowhere. `Panel` is the box the ruling
// names, it is already used across 127 files, and B14 rule 36 says the shared
// kit is how you comply rather than a sixth hand-rolled container.
//
// ⚠ **`SECTION` SURVIVES FOR THE DISPUTE BANNER, AND THAT IS THE DRAWING'S OWN
// SPLIT.** The five groups above are things a clerk READS; the banner and the
// net-meter pair are NOTICES that only appear when they apply, and the drawing
// keeps both unchanged. "Every information group becomes a Panel" is not
// "every block becomes a Panel".
//
// The heading is the kit's own `<h3>` carrying a `Kicker` — the red small-caps
// label every panel in the drawings shows, with the heading element the
// document outline needs kept underneath it.

/** One panel heading, so the five cannot drift into five shapes. */
function GroupPanel(props: { title: string; children: ReactNode }) {
  return (
    <Panel as="section" title={<Kicker>{props.title}</Kicker>}>
      {props.children}
    </Panel>
  );
}

function ReadBody(props: {
  read: ReadDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  batch: ReadImportBatchDetail | undefined;
  batchError: string | null;
  history: AssetReadRow[] | undefined;
  historyTotal: number;
  historyPage: number;
  historyPer: PageSize;
  onHistoryPage: (page: number) => void;
  onHistoryPer: (per: PageSize) => void;
  historyFailed: boolean;
  premisesHref: string | null;
  meterHref: string;
  /** ⑪ — null when the reading carries no account, so the panel states the
   *  absence instead of drawing a link that goes nowhere (hard-won law 2). */
  accountHref: string | null;
}) {
  const { read, t } = props;
  const math = calculationLine(read, t);
  // ⚠ **`plan_registers` IS DROPPED FROM THIS LIST, AND A TEST WRITTEN FOR THIS
  // REDRAW IS WHAT CAUGHT WHY (the blueprint's `D4`, B14 rule 31).**
  // `OutcomeCard` renders a stored detail bag VERBATIM with the raw key as its
  // label, and this bag carries `plan_id` — a uuid — and `basis`, a sentence
  // ending in a rule number. The outcome is `ok` on a complete meter, so nobody
  // had ever seen it: the day a register is short it becomes a WARNING,
  // `flaggedOutcomes` picks it up, and the panel prints a primary key and
  // `BR-MET-049` at a clerk.
  //
  // It is not dropped to HIDE it — ⑬ gives it its own presentation in
  // CALCULATION, reading four named keys and nothing else, so the shortfall is
  // MORE visible than it was and states no internal reference. Rendering it in
  // both places would also be one fact on one screen twice (B14 rule 32).
  const flags = flaggedOutcomes(read).filter((outcome) => outcome.rule !== RULE_PLAN_REGISTERS);
  const unevaluated = unevaluatedOutcomes(read);
  const tally = outcomeTally(read);

  // ⚠ **THE FOUR FIGURES ARE A BAND, NOT FOUR CARDS (`B22`).** They were a
  // 2 × 2 grid of hand-rolled `Figure` blocks; the drawing runs them four
  // across with a 2px rule above and below, which is exactly what `KPIStrip`
  // draws. Using the kit rather than re-cutting the band here is B14 rule 36,
  // and it is also what makes this row match the same row on every other
  // screen in the product.
  const band: KpiTile[] = [
    {
      id: "previous",
      label: t("metering.read.previous"),
      // ⚠ **THE SERVER'S COMPOSED STRING, NOT THE STORED NUMBER (DEF-1086,
      // BR-SHL-250).** `read.prior_value` is BR-MET-019's `NUMERIC(18,6)` as
      // its own string and printed `1008.000000` here once already.
      value: read.prior_value_display ?? <Dash />,
      detail:
        read.period_start === null ? (
          <Dash />
        ) : (
          <DateCell
            value={read.period_start}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        ),
    },
    {
      id: "current",
      label: t("metering.read.current"),
      value: read.current_value_display ?? <Dash />,
      detail:
        read.read_at === null ? (
          <Dash />
        ) : (
          <DateCell
            value={read.read_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        ),
    },
    // CLAUDE.md rule 3: the server's composed "<consumption> <unit>".
    // ✅ AND THAT IS TRUE ON A DEMAND REGISTER TOO — BR-MET-143, 2026-08-27
    // (DEF-797). The write path commits BR-MET-051's own figure — the register
    // VALUE at the cycle read — in the register's own unit (`kW`), so
    // `consumption` IS the peak. It keeps its own label and badge, because a
    // MAXIMUM is still not a total.
    read.is_peak
      ? {
          id: "peak",
          label: t("metering.read.peak"),
          value: <PeakQuantity quantity={read.consumption} unit={read.unit} t={t} />,
          detail: read.demand_reset_noted ? (
            <DemandResetChip t={t} />
          ) : (
            t("metering.read.demandResetNone")
          ),
        }
      : {
          id: "usage",
          label: t("metering.read.usage"),
          value: read.usage_display ?? <Dash />,
          detail:
            read.days_since_prior === null ? (
              <Dash />
            ) : (
              t("metering.read.days", { days: read.days_since_prior })
            ),
        },
    {
      id: "status",
      label: t("metering.read.statusLabel"),
      value: <ReadStatusCell status={read.status} t={t} />,
      detail: t("metering.read.outcomeSummary", {
        passed: tally.passed,
        total: tally.evaluated,
      }),
    },
  ];

  return (
    <>
      {/* The band and the two notices run the full width above the split. */}
      <div className="lg:col-span-3">
        <KPIStrip kpis={band} />

        {/* BR-MET-024 — the dispute, when there is one. ABOVE the split,
            because it changes what every number below MEANS: the customer has
            said this reading is wrong and the account has left the bill run. */}
        {read.disputed && (
          <DisputeBanner
            read={read}
            t={t}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        )}

        {/* US-AST-011/012 — a solar cycle's import AND export, side by side. It
            renders for a net meter and for nothing else (BR-AST-010), and it
            never nets the two: that subtraction is rating's credit math, gated
            by OQ-001. See NetMeterPair.tsx. */}
        <NetMeterPair pair={read.net_pair} />
      </div>

      {/* ── LEFT: is this number right? ─────────────────────────────────── */}
      <div className="lg:col-span-2">
        {/* BR-MET-056 "math shown". Assembled from stored operands; the result
            is the server's own figure, so what is read here is what bills. */}
        <GroupPanel title={t("metering.read.panel.calculation")}>
          {math !== null ? (
            <p className="m-0 text-base tabular-nums">{math}</p>
          ) : read.status === READ_STATUS_ESTIMATED ? (
            // BR-MET-028: an estimate has a consumption and NO register value,
            // so there is no delta to show. BR-MET-029 makes it a lawful bill
            // input that travels flagged — which is why it says so here in full.
            <p className="m-0 text-base tabular-nums">
              {t("metering.read.estimateLine", {
                method: read.estimation_method ?? "—",
                number: read.consecutive_estimate_no ?? "—",
                usage: read.usage_display ?? "—",
              })}
            </p>
          ) : (
            <p className="met-panel-hint">{t("metering.read.mathUnavailable")}</p>
          )}
          <PlanRegisters read={read} t={t} meterHref={props.meterHref} />
        </GroupPanel>

        {/* BR-MET-056: the flag reason WITH the threshold values used. Every
            number below is a stored one; nothing is compared again here. */}
        <GroupPanel title={t("metering.read.panel.flags")}>
          {flags.length === 0 ? (
            <p className="met-panel-hint">{t("metering.read.flagsNone")}</p>
          ) : (
            flags.map((outcome) => <OutcomeCard key={outcome.rule} outcome={outcome} t={t} />)
          )}
          {unevaluated.length > 0 && (
            // CLAUDE.md law 1: "passed every rule" is only true of the rules
            // that ran. The ones that could not are named, with their reason.
            // ⚠ ONE INLINE LINE, not a bold heading over a `<ul>` — the
            // drawing puts it inside the card beside the flags it qualifies,
            // and a second heading inside a panel reads as a second section.
            // ⚠ **AND THE REASON IS GONE — B14 RULE 33, PO 2026-09-14
            // (`DEF-MET-5204` · `D5`).** *Why* a rule could not run is
            // RATIONALE, and rule 33 puts rationale at ZERO words on screen:
            // it is removed, never shortened. It was also the widest leak on
            // this panel — `reasonText` falls back to the stored CODE, and of
            // the twenty-nine reasons the engine can store only eight have a
            // catalogue entry, so a clerk read
            // `maximum_register_not_priced_by_schedule_uom` and
            // `no_version_in_force` verbatim (walked, both). The reason is
            // still stored, still exported and still in the register; it is
            // not on this screen. The FACT — these rules did not run — is.
            <p className="met-panel-hint">
              {t("metering.read.couldNotRun")}
              {unevaluated.map((outcome) => (
                <span key={outcome.rule}>
                  {" · "}
                  {t(`metering.reads.status.${outcome.rule}`, { defaultValue: outcome.rule })}
                </span>
              ))}
            </p>
          )}
          {/* ⚠ **A DEMAND REGISTER IS A MAXIMUM, AND THE PAGE NEVER SAID SO
              (`B32` · `MR-46`, BR-MET-051).** DEF-797 is what this line is
              for: 412 kW read as 14 kWh, $154.00 against $4,532.00. It states
              what the billable figure IS on this kind of register — nothing
              here chooses a rounding, a unit or an estimate, and the
              arithmetic above is untouched (B4/B5 are ❄️ frozen).
              It renders on a demand register and nowhere else: on any other
              reading it would be rationale about a case that does not apply,
              which B14 rule 33 puts at zero words on screen. */}
          {read.is_peak && (
            <p className="met-panel-hint">
              {t("metering.read.peakIsMaximum")}
              {" · "}
              {t("metering.read.peakIsMaximumBasis")}
            </p>
          )}
        </GroupPanel>

        {/* ⚠ **THREE SECTIONS BECAME ONE (`B27`).** Supersession history,
            billed corrections and this meter's past reads answered the same
            question — *what else has happened to this reading and this
            meter?* — from three headings a scroll apart. */}
        <GroupPanel title={t("metering.read.panel.history")}>
          {/* BR-MET-024's version line, the server's own: `read_chain` stamps
              it walking `superseded_by_id`. */}
          <p className="met-panel-hint">{versionLine(read, t)}</p>

          {/* BR-MET-056: the FULL chain, oldest first. A corrected read appears
              once in the list (BR-MET-016) and every version of it is here. */}
          {read.chain.length > 1 && (
            <ol className="m-0 pl-[18px] text-sm">
              {read.chain.map((entry) => (
                <ChainRow
                  key={entry.id}
                  entry={entry}
                  current={entry.id === read.id}
                  t={t}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              ))}
            </ol>
          )}

          {/* US-MET-016 — the J6 correction linkage(s) naming this read.
              Rendered ONLY when one exists, and NO money figure appears: the
              linkage carries references and a reason; the credit note is
              billing's. */}
          {read.corrections.length > 0 && (
            <ul className="m-0 pl-[18px] text-sm">
              {read.corrections.map((row) => (
                <CorrectionLine
                  key={row.id}
                  row={row}
                  t={t}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              ))}
            </ul>
          )}

          {/* RDS-04's read history — REAL (DEF-475 closed): the assets seam
              serves ONE meter's committed heads. */}
          {props.historyFailed ? (
            <p className="met-panel-hint">{t("metering.read.history.failed")}</p>
          ) : props.history === undefined ? (
            <LoadingSkeleton variant="table" />
          ) : props.history.length === 0 ? (
            <p className="met-panel-hint">{t("metering.read.history.empty")}</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{t("metering.reads.col.readAt")}</th>
                      <th>{t("metering.reads.col.current")}</th>
                      <th>{t("metering.reads.col.usage")}</th>
                      <th>{t("metering.reads.col.source")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {props.history.map((row) => (
                      <tr key={row.read_id ?? row.date ?? ""}>
                        <td>
                          {row.date === null ? (
                            <Dash />
                          ) : (
                            <DateCell
                              value={row.date}
                              timeZone={props.timeZone}
                              dateFormat={props.dateFormat}
                            />
                          )}
                        </td>
                        {/* ⚠ **THE REGISTER READING, THROUGH THE ONE COMPOSER
                            (DEF-1086 / DEF-1120).** The assets seam serves
                            `reading` as `str(current_value)` — BR-MET-019's
                            `NUMERIC(18,6)` — so this column printed
                            `42180.000000` beside a usage column that read
                            `612 kWh`. The unit is the row's own (BR-MET-143),
                            and a reading whose unit never arrived stays a DASH
                            rather than a bare number (hard rule 3). */}
                        <td>
                          {row.reading === null || row.unit === null ? (
                            <Dash />
                          ) : (
                            <span className="tabular-nums">{`${formatQuantity(row.reading)} ${row.unit}`}</span>
                          )}
                        </td>
                        <td>
                          {/* rule 3: quantity WITH unit, or a dash — never a
                              bare number a reader must guess the unit of.
                              ⚠ This table is EVERY channel this meter
                              recorded, so a demand row and an energy row sit
                              in it together, and the peak is MARKED so nobody
                              adds them. */}
                          {isPeakChannel(row.channel) ? (
                            <PeakQuantity quantity={row.consumption} unit={row.unit} t={t} />
                          ) : row.consumption !== null && row.unit !== null ? (
                            // ⚠ DEF-1120 — the ONE client composer, not an
                            // f-string: this printed `612.000000 kWh`.
                            <span className="tabular-nums">{`${formatQuantity(row.consumption)} ${row.unit}`}</span>
                          ) : (
                            <Dash />
                          )}
                        </td>
                        <td>
                          {row.source === null ? (
                            <Dash />
                          ) : (
                            t(`metering.reads.source.${row.source}`, { defaultValue: row.source })
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* ⚠ **B14 RULE 16, AND IT WAS THE SECOND HALF OF ONE FIX
                  (`MR-48`).** `getAssetReads` has taken a window and answered
                  `total` since `AST-B-19`; this screen asked for page one and
                  drew the rows with no footer, so a meter with years of
                  history showed a truncated table **with nothing saying so**.
                  The count is the envelope's own — nothing is counted here. */}
              <ListPager
                total={props.historyTotal}
                page={props.historyPage}
                per={props.historyPer}
                onPage={props.onHistoryPage}
                onPer={props.onHistoryPer}
              />
            </>
          )}
        </GroupPanel>
      </div>

      {/* ── RIGHT: where did it come from? ──────────────────────────────── */}
      <div>
        {/* ⚠ **TAGS + PREMISE/UNIT/ACCOUNT BECAME ONE GROUP (`B28`).** The six
            tags ARE the location — which cycle, which route, which register,
            how it arrived — and the premise walk finishes the same sentence.
            ⚠ **THE SERVICE TAG IS NOT HERE ANY MORE (`N4` · `B19`).** It moved
            to the header with the register (PO 2026-09-12), and a fact drawn
            twice on one screen is a fact that can disagree with itself. */}
        <GroupPanel title={t("metering.read.panel.location")}>
          <div className="inline-flex flex-wrap gap-1">
            {read.cycle !== null && (
              <span className={TAG}>{t("metering.read.tag.cycle", { cycle: read.cycle })}</span>
            )}
            {read.route !== null && (
              <span className={TAG}>{t("metering.read.tag.route", { route: read.route })}</span>
            )}
            <span className={TAG}>
              {t(`metering.reads.channel.${read.channel}`, { defaultValue: read.channel })}
            </span>
            <span className={TAG}>
              {t(`metering.reads.source.${read.source}`, { defaultValue: read.source })}
            </span>
            {/* HOW IT WAS COLLECTED (BR-MET-123 · CR-038 W3). The tag above is
                the TRANSPORT the reading arrived by; this is the METHOD.
                `read_method_origin` decides which of three things is drawn,
                and nothing here ever renders a DERIVED value as though a clerk
                had recorded it (hard-won law 1). */}
            {read.read_method === null ? (
              <span className={`${TAG} ${MUTED60}`}>
                {t("metering.reads.readMethod.notStated")}
              </span>
            ) : (
              <span className={TAG}>
                {t(`metering.reads.readMethod.${read.read_method}`, {
                  defaultValue: read.read_method,
                })}
                {read.read_method_origin === "derived" && (
                  <span className={`ml-1 normal-case ${MUTED60}`}>
                    {t("metering.reads.readMethod.derivedSuffix")}
                  </span>
                )}
              </span>
            )}
            {read.source_detail !== null && (
              <span className={TAG}>
                {t(`metering.reads.sourceDetail.${read.source_detail}`, {
                  defaultValue: read.source_detail,
                })}
              </span>
            )}
            {/* BR-MET-128 — *"an event read renders ITS EVENT … on the
                detail"*. Served since CR-038 W9 and drawn by nothing until
                `DEF-WRK-10184` (2026-10-17), the day field-job readings began
                posting under the job's own event (a move-out visit reads
                *Move-out*, not *New connection*). Absent for an ordinary read. */}
            {(read.event_context ?? null) !== null && (
              <span className={TAG} data-read-event={read.event_context ?? ""}>
                {t(`metering.reads.event.${read.event_context ?? ""}`, {
                  defaultValue: read.event_context ?? "",
                })}
              </span>
            )}
            {read.lifecycle === LIFECYCLE_BILLED && (
              <span className="border border-accent px-1 text-xs uppercase tracking-label">
                {t("metering.read.billedTag")}
              </span>
            )}
          </div>

          {read.premise === null && read.unit_label === null ? (
            <p className="met-panel-hint">{t("metering.read.linkageUnavailable")}</p>
          ) : (
            <p className="m-0 mt-3 text-base">
              {props.premisesHref === null ? (
                <span>{read.premise ?? "—"}</span>
              ) : (
                <InlineLinkTo to={props.premisesHref}>{read.premise ?? "—"}</InlineLinkTo>
              )}
              {read.premise_no !== null && (
                <span className="met-qualifier"> · {read.premise_no}</span>
              )}
              {/* ⚠ **`Unit Unit 1` — BR-MET-161 (DEF-899's second half).** The
                  tenant's own unit labels already begin with the word *Unit*,
                  and a label is TENANT DATA, so no template can know whether
                  the noun is already inside it. The meaning comes from the
                  group and from the `·`, never from a word concatenated in
                  front of the value. */}
              {read.unit_label !== null && <span> · {read.unit_label}</span>}
            </p>
          )}
          {/* ⚠ **⑪ — THE ACCOUNT IS DRAWN AS A LINK, AND IT IS NOW SERVED
              (`B30` · `MR-39`, PO 2026-09-14: *"if you ahve account or meter in
              read details screen - please ensure you ahve link it back to
              account and mter to imporve interaction design"*).** This line
              used to print *"The account is not served on a reading; open it
              through the unit"* — thirteen words of RATIONALE over the top of
              `meter_reads.account_id`, a reviewed cross-module FK that has been
              stamped at collection since `DEF-658`. The blueprint's own verdict:
              *"a stored column and a printed absence for the same fact is the
              two-homes problem waiting to happen."*

              **Nothing is joined in the browser and no address is composed
              here** (CLAUDE.md hard rule 8): the server walks its own seam and
              serves `{account_no, id}`, the NUMBER is what renders (B14 rule
              31) and the uuid rides on `title` as evidence.

              The two absences are different facts and say so separately — a
              reading with no account at all (a vacancy read, a unit nobody has
              taken service at) against an account customers could not answer. */}
          {read.account !== null && props.accountHref !== null ? (
            <p className="m-0 mt-1 text-base">
              <InlineLinkTo to={props.accountHref} title={read.account.id}>
                {read.account.account_no}
              </InlineLinkTo>
              {read.account.customer_name !== null && (
                <span className="met-qualifier"> · {read.account.customer_name}</span>
              )}
            </p>
          ) : (
            <p className="met-panel-hint">
              {read.account_absent_reason === "unresolved"
                ? t("metering.read.linkage.accountUnavailable")
                : t("metering.read.linkage.accountUnserved")}
            </p>
          )}
        </GroupPanel>

        {/* MQ-033 (`CR-192-BRC10` task 13) — what the reader answered on the
            utility's own read format, with any flag and any job it raised.
            Nothing renders for a reading that carried no format. */}
        <ReadFormatAnswersPanel answers={read.read_format_answers} />

        {/* DEF-MET-10633 (FB-003, PO 2026-10-27) — where the reader stood: the
            position taken at save, or the late one *added at* its own time,
            and each photograph's. Nothing renders for a read that did not
            come from a route reading. */}
        <FieldPositionPanel
          capture={read.field_capture}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />

        {/* BR-MET-017's permanent stamp, rendered VERBATIM and display-only.
            ⚠ **EIGHT ROWS, NOT TEN (`B29` · `N3`).** `Rule outcomes` is the
            band's STATUS tile and `Version` is the head of HISTORY, two
            sections up — a fact stated twice on one screen is a fact that can
            disagree with itself, and neither was ever the evidence. */}
        <GroupPanel title={t("metering.read.panel.evidence")}>
          {read.import_batch_id === null ? (
            <p className="met-panel-hint">{t("metering.read.complianceNoBatch")}</p>
          ) : props.batchError !== null ? (
            <p className="met-panel-hint">{props.batchError}</p>
          ) : props.batch === undefined ? (
            <LoadingSkeleton variant="table" />
          ) : (
            <dl className="met-facts text-sm leading-note">
              <dt>{t("metering.read.compliance.batch")}</dt>
              <dd>{props.batch.batch_no ?? props.t("metering.reads.batchUnnumbered") /* DEF-SHL-6348 */}</dd>
              <dt>{t("metering.read.compliance.file")}</dt>
              <dd>
                {props.batch.compliance.file_name ??
                  t(`metering.reads.sourceKind.${props.batch.source_kind}`, {
                    defaultValue: props.batch.source_kind,
                  })}
              </dd>
              <dt>{t("metering.read.compliance.hash")}</dt>
              <dd className="break-all tabular-nums">{props.batch.compliance.file_hash ?? "—"}</dd>
              <dt>{t("metering.read.compliance.uploadedBy")}</dt>
              {/* ⚠ **THIS PRINTED A PRIMARY KEY TO A CLERK FOR SIXTEEN DAYS
                  (DEF-899, BR-MET-163).** `uploaded_by_name` is served now
                  (audit's own `actor_names` seam); the id stays on `title` as
                  the evidence it is. */}
              <dd>
                <ActorName
                  id={props.batch.compliance.uploaded_by}
                  name={props.batch.compliance.uploaded_by_name ?? null}
                  t={t}
                />
              </dd>
              <dt>{t("metering.read.compliance.uploadedAt")}</dt>
              <dd>
                {props.batch.compliance.uploaded_at === null ? (
                  <Dash />
                ) : (
                  <DateCell
                    value={props.batch.compliance.uploaded_at}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                    withTime
                  />
                )}
              </dd>
              <dt>{t("metering.read.compliance.session")}</dt>
              <dd>
                {props.batch.compliance.session_ref ?? "—"}
                {props.batch.compliance.ip !== null && ` · ${props.batch.compliance.ip}`}
              </dd>
              <dt>{t("metering.read.compliance.certified")}</dt>
              <dd>{props.batch.compliance.certified ? t("metering.yes") : t("metering.no")}</dd>
              {/* The prototype's "Approvals: None required" line. BR-MET-017's
                  stamp records a CO-SIGNER (the OQ-042 tenant toggle), which is
                  the served fact behind that sentence. */}
              <dt>{t("metering.read.compliance.approvals")}</dt>
              {/* ⚠ DEF-951 — THE SAME DEFECT ONE ROW DOWN, and nobody had
                  reported it because nothing has ever written a co-signature.
                  BR-MET-163 covers both; *None required* is still what an
                  unsigned batch says. */}
              <dd>
                {props.batch.compliance.cosigned_by === null ? (
                  t("metering.read.compliance.noCosigner")
                ) : (
                  <ActorName
                    id={props.batch.compliance.cosigned_by}
                    name={props.batch.compliance.cosigned_by_name ?? null}
                    t={t}
                  />
                )}
              </dd>
            </dl>
          )}
        </GroupPanel>
      </div>
    </>
  );
}

/**
 * ⑮ / `R5` — SERVICE AND REGISTER SIT WITH THE READING'S IDENTITY.
 *
 * PO ruling 2026-09-12, verbatim: *"on this screen can you show utility
 * services chip in header"*, and the blueprint's own reasoning for putting the
 * register beside it: *"They belong with the identity because they decide how
 * the number is read"* — the unit, the plan's expected set and the rate all
 * follow from the two, and a clerk scanning a flagged reading should not have
 * to scroll to learn it is the demand register on an electric meter.
 *
 * ⚠ **THE REGISTER IS THE `Q7` HALF AND IT IS WHY THIS IS FIRST.** A reading
 * recorded against the wrong register is PERMANENT — `supersede_read` takes a
 * value and a reason and nothing else, and migration `0007`'s trigger freezes
 * the channel — and on a demand plan the units differ, which is DEF-797:
 * 412 kW billed as 14 kWh, $154.00 against $4,532.00. Nothing here chooses a
 * rounding, a unit or an estimate; it makes the register impossible to miss on
 * the way out.
 *
 * Both were SERVED on the row already and both were buried: the service sat in
 * the Location group four sections down, and the register only inside the
 * kicker's run-on line.
 */
function ReadIdentityChips(props: { read: ReadDetail; t: Translator }) {
  const { read, t } = props;
  return (
    <>
      <ReadStatusCell status={read.status} t={t} />
      {read.service !== null && (
        <Chip>
          {/* The letter squares have ONE owner in this product (CR-023 §9.7 /
              DEF-439) — a second badge here would be a second vocabulary. */}
          <ServiceTags services={[read.service]} />
          {/* `rating.service.*` is the ONE service-name catalogue family. */}
          {t(`rating.service.${read.service}`, { defaultValue: read.service })}
        </Chip>
      )}
      <Chip>{t(`metering.reads.channel.${read.channel}`, { defaultValue: read.channel })}</Chip>
    </>
  );
}

/**
 * ⑬ / `B31` · `MR-45` — THE WHOLE REGISTER SET THE PLAN EXPECTS, TICKED OFF.
 *
 * The data has been stored on every read since CR-038 W1: the `plan_registers`
 * outcome carries `expected`, `received`, `missing` and the plan's pricing
 * MODEL (BR-MET-049). Its severity is `ok` on a complete meter, and
 * `flaggedOutcomes` drops `ok` — so **a clerk looking at one time-of-use
 * window could not see that a sibling register never arrived**, which is the
 * shortfall the whole rule exists to surface.
 *
 * ⚠ **IT IS RENDERED FROM THE NAMED KEYS AND NEVER FROM THE BAG (`D4`).** The
 * same detail bag carries `plan_id` — a raw uuid — and `basis`, a sentence
 * ending in a rule number. `OutcomeCard` prints a detail bag verbatim with the
 * raw key as its label, so routing this outcome through it would put a primary
 * key and a rule id on a clerk's screen the day the rule fires (B14 rule 31).
 * Four keys are read here, by name, and nothing else is touched.
 */
function PlanRegisters(props: { read: ReadDetail; t: Translator; meterHref: string }) {
  const { read, t } = props;
  const outcome = read.rule_outcomes.find((row) => row.rule === RULE_PLAN_REGISTERS);
  const expected = stringList(outcome?.detail.expected);
  if (outcome === undefined || expected.length === 0) {
    // An unresolvable expected set is `not_evaluated` with its own reason
    // (a unit with no plan, rating unwired, a window naming no channel). That
    // is a stated absence the FLAGS group already carries; repeating it here
    // would be the same sentence twice.
    return null;
  }
  const received = new Set(stringList(outcome.detail.received));
  const model = typeof outcome.detail.plan_model === "string" ? outcome.detail.plan_model : null;
  const present = expected.filter((channel) => received.has(channel));
  return (
    <div className="mt-3 border-t border-divider pt-3 text-sm">
      <span className={MUTED60}>{t("metering.read.planRegisters.title")}</span>
      {model !== null && (
        <span> · {t(`rating.model.${model}`, { defaultValue: model })}</span>
      )}
      {expected.map((channel) => (
        <span key={channel}>
          {" · "}
          {t(`metering.reads.channel.${channel}`, { defaultValue: channel })}{" "}
          {received.has(channel) ? (
            <span aria-label={t("metering.read.planRegisters.arrived")}>✓</span>
          ) : (
            <span className="text-accent">{t("metering.read.planRegisters.missing")}</span>
          )}
        </span>
      ))}
      <span className="tabular-nums">
        {" · "}
        {t("metering.read.planRegisters.count", {
          present: present.length,
          expected: expected.length,
        })}
      </span>
      <span>
        {" · "}
        <InlineLinkTo to={props.meterHref}>
          {t("metering.read.planRegisters.seeMeter")}
        </InlineLinkTo>
      </span>
    </div>
  );
}

/**
 * ⑦ / `B33` — ONE STORED VERDICT: THE RULE'S NAME IN BOLD, AND ONE PROSE LINE.
 *
 * The drawing puts exactly that under `FLAGS` — *"High usage / 154% of a 5.2
 * kWh average · threshold 150% · 3 readings in the average"* — with **no
 * severity badge**, which is `B33`'s whole gap.
 *
 * ⚠ **WHAT IT REPLACES IS A LIVE BREACH, NOT A LAYOUT PREFERENCE
 * (`DEF-MET-5204` · `D3` · `D4`).** This card used to print
 * `Object.entries(outcome.detail)` as a `<dl>` with `detailLabel`'s RAW-KEY
 * fallback, so a clerk read `basis  no active account on the unit
 * (BR-MET-036)` on 2 of 2 readings opened in a browser, and `occupied  No`
 * beside it. Behind a severity branch the same code was one flag away from
 * printing `plan_id  01a09bc5-…` (walked) and a second rule number. B14 rule
 * 31 puts no id, rule number or internal path on screen; rule 32 keeps them
 * out of clerk-facing copy.
 *
 * `outcomeSentence` reads every key BY NAME, so nothing iterates the bag and
 * the guarantee survives the engine growing a key tomorrow.
 *
 * ⚠ **THE SEVERITY IS STILL SAID — IN THE RAIL, NOT IN WORDS.** An error keeps
 * the accent rail it always had; the badge went because the drawing has none
 * and because `Hard error` beside `Negative usage` is the row repeating what
 * its own name offers (B14 rule 32 clause 3).
 */
function OutcomeCard(props: { outcome: ReadRuleOutcome; t: Translator }) {
  const { outcome, t } = props;
  const sentence = outcomeSentence(outcome, t);
  // The severity is STATIC conditional utilities, never an interpolated class
  // name — the Tailwind scanner cannot see `rd-outcome-${severity}` and would
  // compile nothing for it (routeBUtilities.test.ts's own warning).
  const frame =
    outcome.severity === "error"
      ? "border-l-[3px] border-l-accent py-1.5 pl-2.5"
      : "border-l-[3px] border-l-divider py-1.5 pl-2.5";
  return (
    <div className={frame}>
      <p className="m-0 font-heading text-base font-bold">
        {t(`metering.reads.status.${outcome.rule}`, { defaultValue: outcome.rule })}
      </p>
      {sentence !== null && <p className="met-panel-hint">{sentence}</p>}
    </div>
  );
}

function ChainRow(props: {
  entry: ReadChainEntry;
  current: boolean;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { entry, t } = props;
  const row = "grid grid-cols-[5ch_1fr_1fr] gap-x-2.5 gap-y-1 py-1";
  return (
    <li className={props.current ? `${row} font-bold` : row}>
      <span className={`font-heading text-xs tabular-nums ${MUTED55}`}>
        {t("metering.read.chainVersion", { version: entry.version })}
      </span>
      {/* DEF-1086 — `ReadChainEntry extends ReadRow`, so the composed sibling
          is already on every chain row; this printed `42864.000000`. */}
      <span className="tabular-nums">{entry.current_value_display ?? "—"}</span>
      {/* rule 3 again: the chain's usage carries its unit, like every other. */}
      <span className="tabular-nums">{entry.usage_display ?? "—"}</span>
      <span className={`col-span-full ${MUTED60}`}>
        {entry.superseded_at === null ? (
          t("metering.read.chainHead")
        ) : (
          <DateCell
            value={entry.superseded_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        )}
      </span>
      <span className={`col-span-full ${MUTED60}`}>{entry.supersede_reason ?? ""}</span>
    </li>
  );
}

/** One J6 linkage: which invoice, why, and where the pair stands. */
function CorrectionLine(props: {
  row: ReadCorrectionRow;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { row, t } = props;
  return (
    <li>
      {t("metering.read.corrections.line", {
        invoice: row.invoice_no ?? row.invoice_id,
        status: row.status,
      })}
      {row.reason !== null && ` — ${row.reason}`}
      {row.opened_at !== null && (
        <span className="met-qualifier">
          {" · "}
          <DateCell
            value={row.opened_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        </span>
      )}
    </li>
  );
}

// ── The dispute (BR-MET-024 · the OQ-043 closure) ─────────────────────────

/**
 * What a disputed reading looks like to the clerk who opens it.
 *
 * Three sentences, and each is a fact the server sent rather than a hope:
 *   1. WHO said what, and when — the marker, the reason and the actor;
 *   2. **the account is out of the bill run** until a System Admin clears it,
 *      which is the whole of OQ-043's v1 consequence and the one thing a clerk
 *      chasing a missing bill next month needs to be able to find;
 *   3. **BR-MET-133** — where the reading is already BILLED, what happens to
 *      the bill their customer is holding. Saying nothing here would let a
 *      clerk tell a customer their bill had been put on hold.
 *
 * ⚠ Sentence 3 used to say *"nothing signs what it should do"* and cited
 * OQ-245. The PO ruled it on 2026-08-26: the bill STANDS, the fix is a billed
 * correction, and **while the dispute is open the disputed amount does not age
 * into late fees while the undisputed remainder ages normally**. That last
 * clause is the one a clerk repeats to a customer on the phone, so it is on the
 * screen and not only in a rule file.
 */
/**
 * ⑪ · **THE KICKER'S METER NUMBER IS THE DOOR BACK TO THE METER** — PO
 * 2026-09-14, verbatim: *"if you ahve account or meter in read details screen -
 * please ensure you ahve link it back to account and mter to imporve
 * interaction design"*.
 *
 * ⚠ **THE TRANSLATION DECIDES WHERE THE LINK SITS, NOT THIS FILE.** The kicker
 * is one catalogue sentence — `Reading · {{meter}} · {{channel}}` — and eleven
 * catalogues are free to put the three segments in another order. So the line
 * is RENDERED FIRST, with a sentinel standing in for the meter, and then split
 * on it: whatever each language wrote before and after the placeholder is kept
 * verbatim and only the meter becomes an `<a>`. Hard-coding *"Reading · "* here
 * would have quietly re-Englished the kicker in ten languages.
 *
 * A reading with no meter number falls back to the plain sentence — there is
 * nothing to link to and a bare `—` inside a link is a control that goes
 * nowhere (hard-won law 2's mirror).
 */
const KICKER_METER_SLOT = "\u0000meter\u0000";

function MeterKicker(props: {
  meter: string | null;
  channel: string;
  href: string;
  t: Translator;
}) {
  const { t } = props;
  if (props.meter === null || props.meter === "") {
    return <>{t("metering.read.kicker", { meter: "—", channel: props.channel })}</>;
  }
  const line = t("metering.read.kicker", {
    meter: KICKER_METER_SLOT,
    channel: props.channel,
  });
  const at = line.indexOf(KICKER_METER_SLOT);
  if (at === -1) {
    // A catalogue that dropped the placeholder: say the words it does have
    // rather than rendering a sentinel at a clerk.
    return <>{t("metering.read.kicker", { meter: props.meter, channel: props.channel })}</>;
  }
  return (
    <>
      {line.slice(0, at)}
      <InlineLinkTo to={props.href} title={t("metering.read.meterLink")}>
        {props.meter}
      </InlineLinkTo>
      {line.slice(at + KICKER_METER_SLOT.length)}
    </>
  );
}

function DisputeBanner(props: {
  read: ReadDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { read, t } = props;
  return (
    <section className={`${SECTION} border-l-[3px] border-l-warning-700 pl-3`} role="status">
      <Kicker>{t("metering.read.dispute.title")}</Kicker>
      <p className={`m-0 mb-1 font-semibold leading-normal ${MEASURE}`}>
        {read.dispute_reason ?? t("metering.read.dispute.noReason")}
      </p>
      <p className="met-panel-hint">
        {read.disputed_at === null ? (
          <Dash />
        ) : (
          <DateCell
            value={read.disputed_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        )}
        {read.disputed_by !== null &&
          ` · ${t("metering.read.dispute.by", { actor: read.disputed_by })}`}
      </p>
      {/* OQ-043's closure, in the clerk's words. */}
      <p className={`mb-0 mt-2 text-sm leading-body text-warning-700 ${MEASURE}`}>{t("metering.read.dispute.holdsRun")}</p>
      {/* BR-MET-133, stated where it applies and nowhere else. */}
      {read.lifecycle === LIFECYCLE_BILLED && (
        <p className={`mb-0 mt-2 text-sm leading-body ${MUTED65} ${MEASURE}`}>{t("metering.read.dispute.billedBillStands")}</p>
      )}
    </section>
  );
}

// ── The three dialogs that act on ONE reading ──────────────────────────────
//
// Blueprint entries 04 (Correct), 05 (Dispute) and 06 (Clear), built from the
// drawn pages as images (B14 rule 42, PO 2026-09-13). Each is a FormModal with
// its fields in the drawn order and its CONSEQUENCE last, immediately above the
// footer — B14 rule 11, stated before the commit rather than after it.
//
// ⚠ **THE REGISTER IS NAMED ON ALL THREE, AND THAT IS WHY (step-1 Q7, PO
// 2026-09-14: *"Put this first. DEF-797 already cost 412 kW billed as 14 kWh —
// $154 against $4,532. Money path, so I'm not classifying it"*).** A reading
// filed against the wrong register is PERMANENT: `supersede_read` takes a value
// and a reason and nothing else, and metering migration `0007`'s trigger
// freezes the channel. These dialogs COVER the page that names the register, so
// a clerk typing a corrected value could not see which register it belongs to —
// DEF-797's exact shape, where the units differ (kW against kWh) and the wrong
// column is not merely the wrong label.
//
// ⚠ **THE KICKER IS B14 RULE 38, NOT A LIBERTY TAKEN WITH THE DRAWING.** Rule 38
// names *"what the kicker says"* as FORM CONSTRUCTION, where our UI rules win
// over a drawing — so the drawn `READING · MTR-0452` yields to the kit's own
// reading kicker, which is the one the page behind already renders. Recorded as
// a divergence in `04-docs/05-modules/04-metering/conformance/
// MR-p016-correct-dispute-clear.md`, as that rule requires — which also carries
// the two things this lane raises for the PO.
//
// ⚠ **AND THAT IS ALL IT DOES — IT MAKES THE REGISTER VISIBLE, NOT CHANGEABLE.**
// Four shapes are on the table for the wrong-register case (a correction that
// carries a channel · a re-register supersede · saying it on screen · refusing
// at the import door) and the PO declined to classify any of them. Nothing here
// chooses one, and nothing here chooses a rounding, a unit or an estimate:
// B4/B5 are ❄️ FROZEN and move only by a finance re-sign (HUMAN-GUIDE §6).
function readModalKicker(read: ReadDetail, t: Translator): string {
  return t("metering.read.kicker", {
    meter: read.meter ?? "",
    channel: t(`metering.reads.channel.${read.channel}`, { defaultValue: read.channel }),
  });
}

/**
 * The blueprint's "warning rail" on entry 05 — the disputed-reading section's
 * own left rule (`ReadDisputeSection` above draws the same one), so the figure
 * under dispute reads as the same object in both places instead of as a second
 * grey caption. Utilities only, and every token is one this file already emits.
 */
const DIALOG_RAIL = "border-l-[3px] border-l-warning-700 pl-3";

/**
 * Hard rule 3 on the one screen where getting it wrong cannot be undone: a
 * register value never travels without its unit, and where the server has no
 * unit on file **the dash is the honest answer**. It read `In .` before — an
 * empty gap where the unit should be, on the dialog that rewrites the number a
 * bill is computed from. This invents no unit; it states that there is none.
 */
export function unitOrDash(unit: string | null | undefined): string {
  return unit === null || unit === undefined || unit.trim() === "" ? "—" : unit;
}

export function DisputeModal(props: {
  read: ReadDetail;
  onSubmit: (values: { reason: string }) => Promise<unknown>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [values, setValues] = useState({ reason: "" });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await props.onSubmit(values);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      title={t("metering.read.dispute.modalTitle", { meter: props.read.meter ?? "" })}
      kicker={readModalKicker(props.read, translate)}
      schema={disputeSchema(translate)}
      values={values}
      submitLabel={t("metering.read.dispute.submit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* Entry 05, top: the figure under dispute on the drawn warning rail, and
          CLAUDE.md rule 3 is why it is first — a clerk is about to hold an
          account out of a bill run over THIS quantity, so the quantity and its
          unit are the first thing on the form. `usage_display` is the server's
          own composed "<consumption> <unit>"; a dash where it has none. */}
      <p className={DIALOG_RAIL} data-dialog-rail="under-dispute">
        {t("metering.read.dispute.figure", { usage: props.read.usage_display ?? "—" })}
      </p>
      <TextField
        id="reason"
        label={t("metering.read.dispute.reason")}
        required
        multiline
        value={values.reason}
        onChange={(reason) => setValues({ reason })}
        help={t("metering.read.dispute.reasonHelp")}
      />
      {/* B14 rule 11 — the consequence BEFORE the commit, and drawn last. A
          clerk raising a dispute is taking an account out of the next bill run
          and the only way back is a System Admin, so it sits against the
          button that does it rather than above a form nobody has filled in. */}
      <Note>{t("metering.read.dispute.note")}</Note>
      {/* BR-MET-133, and only where it applies: what a dispute does to a bill
          that already went out. Beside the consequence it qualifies. */}
      {props.read.lifecycle === LIFECYCLE_BILLED && (
        <RefusalStrip role="alert">
          {t("metering.read.dispute.billedBillStands")}
        </RefusalStrip>
      )}
    </FormModal>
  );
}

export function ClearDisputeModal(props: {
  read: ReadDetail;
  onSubmit: (values: { resolution?: string }) => Promise<unknown>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState({ resolution: "" });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await props.onSubmit({ resolution: values.resolution.trim() || undefined });
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      title={t("metering.read.dispute.clearTitle", { meter: props.read.meter ?? "" })}
      kicker={readModalKicker(props.read, (key, params) => t(key, params))}
      // The note is OPTIONAL — see `clearDisputeSchema`.
      schema={clearDisputeSchema()}
      values={values}
      submitLabel={t("metering.read.dispute.clearSubmit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* Entry 06 is drawn as ONE field and ONE consequence line, in that
          order: the note first, what clearing does to the bill last. */}
      <TextField
        id="resolution"
        label={t("metering.read.dispute.resolution")}
        multiline
        value={values.resolution}
        onChange={(resolution) => setValues({ resolution })}
        help={t("metering.read.dispute.resolutionHelp")}
      />
      {/* ⚠ BR-MET-133 clause 3 (PO 2026-08-26) settles what this button means,
          and this note used to say the opposite. It read as OQ-245(c) "stated
          rather than resolved: cleared records no verdict". Clearing IS one of
          the two outcomes — *"she is wrong → clear the marker, the bill was
          always correct"* — and the OTHER outcome takes the billed-correction
          door. The screen still offers no upheld/rejected control, because
          there is exactly one verb here and the other one is a different
          button; what changed is that it now says which.
          ⚠ THE DRAWING DOES NOT CARRY THIS SENTENCE and it is kept anyway: the
          blueprint's own copy pass measured seventeen helper lines and never
          listed it, and its field table counts this dialog as two items, so its
          absence there is an omission rather than a cut. Deleting a screen
          sentence that states a SIGNED rule is a copy decision for the PO, not
          for a build lane — reported with this lane, unresolved. */}
      <p className="met-panel-hint">{t("metering.read.dispute.clearOutcome")}</p>
      {/* B14 rule 11 — the consequence immediately above the commit. */}
      <Note>{t("metering.read.dispute.clearNote")}</Note>
    </FormModal>
  );
}

// ── Override = SUPERSEDE (BR-MET-024/053) ─────────────────────────────────

export function OverrideModal(props: {
  read: ReadDetail;
  working: boolean;
  onSubmit: (values: { value: string; reason: string }) => Promise<unknown>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [values, setValues] = useState({
    // Pre-filled with the CURRENT register so a clerk corrects a digit rather
    // than retyping five. The value is a raw string end-to-end — the server
    // parses it (CLAUDE.md rule 2).
    value: props.read.current_value ?? "",
    reason: "",
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await props.onSubmit(values);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      title={t("metering.read.override.title", { meter: props.read.meter ?? "" })}
      kicker={readModalKicker(props.read, translate)}
      schema={overrideSchema(translate)}
      values={values}
      submitLabel={t("metering.read.override.submit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <TextField
        id="value"
        label={t("metering.read.override.value")}
        numeric
        required
        value={values.value}
        onChange={(value) => setValues({ ...values, value })}
        // Hard rule 3 — and `unitOrDash`, not `?? ""`: an absent unit used to
        // render "In ." on the dialog that rewrites a billed quantity.
        help={t("metering.read.override.valueHelp", { unit: unitOrDash(props.read.unit) })}
      />
      <TextField
        id="reason"
        label={t("metering.read.override.reason")}
        required
        multiline
        value={values.reason}
        onChange={(reason) => setValues({ ...values, reason })}
        help={t("metering.read.override.reasonHelp")}
      />
      {/* B14 rule 11 and entry 04's drawing agree: the consequence is the last
          thing before the button. BR-MET-024 in the clerk's words — the
          correction APPENDS, so nothing on screen is edited and the reading
          being replaced stays in the history. */}
      <Note>{t("metering.read.override.note")}</Note>
    </FormModal>
  );
}

// ── Correct a BILLED read = the J6 door (BR-MET-053 · US-MET-016) ──────────

/** The bills this reading could have been priced on — the picker's list.
 *
 *  ⚠ **IT IS SEARCHED SERVER-SIDE BY THE PREMISE, NOT LOADED WHOLE.** `GET
 *  /invoices` searches bill number, account number, customer name **and
 *  address** (`_apply_search`, `PUJ-53`), and a reading knows its premise by
 *  walking to it — so ONE paged request returns the bills at the building the
 *  meter is on. Asking for every bill in the utility and filtering in the
 *  browser would break at the top of the ICP (`NFR-3`), which is the shape
 *  `MR-11` is still open about elsewhere in this module.
 *
 *  A reading with no premise walk gets NO list, and the field says so rather
 *  than offering a whole utility's bills to be guessed among. */
export const billPickerQueryKey = (premise: string) =>
  ["invoices", "read-correction", premise] as const;

function BilledCorrectionModal(props: {
  read: ReadDetail;
  client: ApiClient;
  onSubmit: (values: { value: string; reason: string; invoice_id: string }) => Promise<unknown>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const premise = props.read.premise;
  const [values, setValues] = useState({
    // Pre-filled with the CURRENT register so a clerk corrects a digit rather
    // than retyping five. The value is a raw string end to end — the server
    // parses it (CLAUDE.md rule 2).
    value: props.read.current_value ?? "",
    reason: "",
    invoice_id: "",
  });

  const bills = useQuery({
    queryKey: billPickerQueryKey(premise ?? ""),
    queryFn: () =>
      getInvoices({ q: premise as string, sort: "issue_date", dir: "desc" }, props.client),
    enabled: premise !== null,
    retry: false,
  });

  const options = (bills.data?.results ?? []).map((row: InvoiceRow) => ({
    value: row.id,
    // B14 rule 31 — a bill is named by its NUMBER, never by its primary key. A
    // row carrying no number (a legacy one; BR-BIL-063 allocates at draft
    // creation) says so in words rather than falling back to the uuid.
    label: [row.invoice_no ?? t("metering.read.correctBilled.billUnnumbered"), row.cycle_label]
      .filter((part): part is string => typeof part === "string" && part !== "")
      .join(" · "),
  }));

  // BR-SHL-025 / BR-AST-534: a field that will not take typing owes the reader
  // its reason. Three states, and only the middle one is an error.
  const pickerReason =
    premise === null
      ? t("metering.read.correctBilled.invoiceNoPremise")
      : bills.isError
        ? apiErrorText(bills.error, translate)
        : null;

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await props.onSubmit(values);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      title={t("metering.read.correctBilled.title", { meter: props.read.meter ?? "" })}
      kicker={t("metering.reads.kicker")}
      schema={billedCorrectionSchema(translate)}
      values={values}
      submitLabel={t("metering.read.correctBilled.submit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <TextField
        id="value"
        label={t("metering.read.override.value")}
        numeric
        required
        value={values.value}
        onChange={(value) => setValues({ ...values, value })}
        help={t("metering.read.override.valueHelp", { unit: props.read.unit ?? "" })}
      />
      {/* ⚠ **THE FIELD THAT MAKES THIS A DIFFERENT DOOR.** BR-MET-053: the read
          fix and the money fix travel together, so the correction NAMES the
          invoice it opens — and the server verifies it through the billing seam
          before it writes anything, which is why a wrong bill is a refusal
          rather than a fabricated money event. B14 rule 8: past ten options a
          picker is type-to-filter, so this is the shared `SearchSelectField`
          and not a select. */}
      <SearchSelectField
        id="invoice_id"
        label={t("metering.read.correctBilled.invoice")}
        required
        value={values.invoice_id}
        onChange={(invoice_id) => setValues({ ...values, invoice_id })}
        options={options}
        disabled={pickerReason !== null}
        help={pickerReason ?? t("metering.read.correctBilled.invoiceHelp")}
      />
      <TextField
        id="reason"
        label={t("metering.read.override.reason")}
        required
        multiline
        value={values.reason}
        onChange={(reason) => setValues({ ...values, reason })}
        help={t("metering.read.override.reasonHelp")}
      />
      {/* B14 rule 11: the consequence is the last thing before the button, and
          it is the one a clerk must not learn afterwards — this opens a money
          correction against a bill the customer is already holding. Hard rule 4
          keeps the invoice itself exactly where it is. */}
      <Note>{t("metering.read.correctBilled.note")}</Note>
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-013 + US-MET-016 §3 cases · CR-038 W5 (S29 page ruling, PO 2026-08-26)
// generated: 2026-08-26 by the CR-038 W5 lane (re-homing the 2026-08-11 drawer; its Trace lineage is preserved above) · AMENDED 2026-08-27 (DEF-899 — the compliance stamp renders PEOPLE, through the shared `ActorName`; the co-signer too, DEF-951; and `Unit Unit 1` becomes `Unit 1`, BR-MET-161)
// checklist: A✔ B✔(this IS the 2b half — the S29 page) C✔(ReadDetailPage.test.tsx — the drawer suite ported and extended; RED first on the route: NotBuiltYetPage rendered where the page should) D✔(the API half shipped with the W2 lane; corrections typed this lane) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// exceptions: E3 the ACCOUNT half of the linkage block still renders its stated absence — `read_dict` serves no account and joining customers from the browser is the boundary the drawer refused too · E3 Estimate stays DISABLED with its reason (unchanged from the drawer: `POST /reads/estimate` fills a MISSING record and has no guard against a second head) · E4 the header carries the retired drawer FOOTER's three actions (US-SHL-020's slots: Override is the ONE primary) — RDS-04 draws them as a drawer footer, and the PO's page ruling overrides the drawer frame, not the actions · E4 `metering.read.kicker` keeps the drawer's meter+channel form rather than RDS-04's "Read · M-4021 · Cycle 08-A": the channel disambiguates TOU rows, which the id alone cannot — reported divergence, unchanged from the drawer
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
