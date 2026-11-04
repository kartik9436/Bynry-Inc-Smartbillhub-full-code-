// ── Trace ──────────────────────────────────────────────
// Change:   CR-013 P2 — the shared DEFINITION DETAIL, rows 8 · 11 · 14 of the
//           16-surface inventory (`09-screen-inventory.md` §18)
//           Screens: CHG-01 (charge) · CHG-01.discount · CHG-01.tax
// Rules:    BR-RAT-084 (ONE component, THREE routes, THREE screen ids) ·
//           BR-RAT-087 / DEF-364 (server `*_display` strings, never the stored
//           value, never scaled here) · BR-SHL-011 (the open tab is URL state) ·
//           BR-SHL-012 (the A18 states) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-025 (a forbidden control is present and disabled WITH its
//           reason) · BR-SHL-034 (one date formatter) · BR-SHL-044 (the one
//           page-header skeleton) · B14 rule 21 (new UI is Tailwind)
// ───────────────────────────────────────────────────────
//
// ONE SCREEN, THREE KINDS — the eight-part shell `09-screen-inventory.md` §2
// reads off the running canvas:
//
//   1 `← Plans & Rates` back link · 2 the uppercase `·`-separated eyebrow ·
//   3 the `<h1>` · 4 the muted sub-line · 5 status pill + Duplicate/Edit/Retire ·
//   6 EXACTLY FOUR KPI tiles · 7 the underlined tab strip · 8 the Overview body.
//
// Every part above is drawn HERE and every part's CONTENT comes from
// `definitionDetail.tsx`. That split is BR-RAT-084's *"reduction in FILES,
// never in the enumeration"* made structural: the file count falls to one and
// the three surfaces stay three, each with its own route, its own screen id,
// its own tab set and its own four tiles.
//
// ⚠ THE VERSIONS TAB IS NOT A VIEW ON `audit_log`, AND §10 IS EMPHATIC THAT THE
// WRONG IMPLEMENTATION IS THE PLAUSIBLE ONE. Both are append-only histories of
// the same object; they answer different questions and have different owners —
// a version row is *"a priced state that bills can still resolve to"*, read by
// the resolution chain on every bill run, with a `CHANGE` sentence **authored by
// the person filing it**; an audit row is an actor + action + timestamp, and the
// engine never reads one. So this tab renders the object's OWN version table,
// and until a route serves that table it says so — it does NOT fall back to a
// filtered audit query, which would look right and be a different record.
// `DefinitionDetail.test.tsx` reads this file as text and fails on any audit
// reference in it, because a rendering assertion cannot tell the two apart.
//
// ⚠ WHAT IS NOT SERVED, NAMED RATHER THAN FAKED. `apps/rating/api.py` serves 18
// handlers and NONE of them is a definition version list, a plans-carrying-it
// list, or any discount route at all (§17: *"nothing serves a plan detail, a
// rate detail, a definition detail, a version list, or an impact analysis"*).
// Each absence below renders `ArrivesWith` naming the missing read, the way
// `AssetDetailPage`'s Reads tab does for `GET /assets/{id}/reads`. An empty
// table would claim "this charge is on no plans", which is a claim this screen
// cannot make.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  activateDiscountVersion,
  approveDiscountVersion,
  getCharge,
  getChargePlans,
  getDiscount,
  getLedgerAccounts,
  getMyPermissions,
  submitDiscountVersion,
} from "@/api/endpoints";
import type { ChargeReachRow, DiscountDetail, GlAccountRef } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import { ListPager } from "@/components/ListPager";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { Kicker, Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import {
  ArrivesWith,
  RefusalNotice,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DEFINITION_ROUTES,
  DEFINITION_TABS,
  PLANS_TAB,
  isHistoryTab,
  definitionIsServed,
  definitionWizardPath,
  emptyKpis,
  presentCharge,
  presentDiscount,
} from "./definitionDetail";
import type {
  DefinitionBlock,
  DefinitionField,
  DefinitionKind,
  DefinitionPresentation,
  DefinitionRegional,
} from "./definitionDetail";
import {
  DASHBOARD_ROUTE,
  GuardedButton,
  RatingStatusPill,
  ratingAccess,
  ratingIsDenied,
  ratingIsReadOnly,
} from "./ratingShared";
import type { Translator } from "./ratingShared";
import { useRegional } from "@/features/metering/meteringShared";
import { TaxDetailPage } from "./taxDetail/TaxDetailPage";
import { DiscountDetailPage } from "./discountDetail/DiscountDetailPage";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** The URL param the open tab lives in — BR-SHL-011, so a tab is linkable. */
export const TAB_PARAM = "tab";

/** BR-SHL-011's spirit: an unknown tab segment falls back, it never errors. And
 *  the fallback is the KIND's first tab, not a shared literal, because the
 *  three tab lists are three lists.
 *
 *  ⚠ **THE TWO SPELLINGS OF THE HISTORY TAB RESOLVE TO EACH OTHER (`CR-087`,
 *  PO ruling 2026-09-10: *"Change the label, keep the address"*).** The
 *  discount and the tax moved to `audit` on 2026-09-08; the CHARGE's address is
 *  still `versions` and, under that ruling, STAYS `versions` — links already
 *  sent to people keep working and the label is the half a clerk reads.
 *
 *  **What was broken is the other direction.** The charge's tab has read
 *  `Audit` in all eleven catalogues since the rename, so every document,
 *  drawing and person naturally writes `?tab=audit` — and that landed on the
 *  OVERVIEW, silently, because the fallback below cannot tell a mistyped tab
 *  from a synonym. Nothing errored, nothing logged, and the screen a link
 *  promised simply did not open (`DEF-RAT-4832`).
 *
 *  So a history spelling the kind does not use resolves to the one it does —
 *  in BOTH directions, because the mirror is already reachable: a `?tab=versions`
 *  link to a DISCOUNT, written before that kind was renamed, lands on its
 *  Overview for the identical reason. {@link isHistoryTab} is the one predicate
 *  that knows both spellings and this is its second caller.
 *
 *  ⚠ **IT DOES NOT CHANGE WHAT THE SCREEN WRITES BACK.** `selectTab` still puts
 *  the kind's OWN id in the query string, so the address a clerk copies out of
 *  the bar is the kind's own — the ruling's *"keep the address"* half. This
 *  only widens what is ACCEPTED. */
export function definitionTabFrom(kind: DefinitionKind, raw: string | null): string {
  const tabs = DEFINITION_TABS[kind];
  const asked = raw ?? "";
  if (tabs.includes(asked)) {
    return asked;
  }
  if (isHistoryTab(asked)) {
    const history = tabs.find((tab) => isHistoryTab(tab));
    if (history !== undefined) {
      return history;
    }
  }
  return tabs[0];
}

/**
 * §2 part 5's three buttons, in r10's order.
 *
 * They were ALL disabled with their reason until 2026-08-21 — BR-SHL-025's
 * shape applied to a different cause: the control is real, the user is not
 * forbidden, and the thing it opens did not exist. Drawing them and saying so
 * is what stops the next lane re-deriving the cluster from the drawing; hiding
 * them would lose the enumeration BR-RAT-084 protects.
 *
 * **`Edit` is now live on the CHARGE kind** and opens CHG-02
 * (`ChargeCodeWizard.tsx`, §18 row 9). It stays disabled on the discount and
 * the tax, whose wizards (rows 12 · 15) are not built, and `Duplicate` and
 * `Retire` stay disabled on all three — no route serves either, for any kind.
 */
/**
 * The kinds whose `Edit` opens a real wizard — ALL THREE since 2026-09-08.
 *
 * ⚠ **IT IS A CONSTANT AND EXPORTED BECAUSE A HOLD NEEDS A TEST THAT FIRES WHEN
 * IT EXPIRES** (hard-won law 2, and `DEF-RAT-4647` is what it costs when there
 * is none). The rule is not *"remember to update this line"* — that rule
 * existed, in a comment, and was not followed for two weeks while the wizard it
 * described was live. `definition.hold.test.tsx` asserts this list against the
 * routes `App.tsx` actually registers, so a fourth kind whose wizard lands with
 * this line unmoved goes RED and names itself.
 */
export const EDITABLE_KINDS: readonly DefinitionKind[] = ["charge", "discount", "tax"];

/**
 * The two header actions that are still held, and the DESTINATIONS whose
 * absence is the reason. A test asserts no route matches either segment; the
 * day one does, the hold has expired and the suite says so by address.
 */
export const HELD_ACTION_SEGMENTS: readonly string[] = ["duplicate", "retire"];

/**
 * `BR-RAT-1016` verb 2 — may THIS version be corrected?
 *
 * Only an `active` one, and the three refusals `correct_discount_version`
 * writes are the reason: a DRAFT has priced nothing and is edited in place; a
 * `pending_approval`, `scheduled` or `rejected` filing has never been in force,
 * so there is no recorded figure to correct and it is withdrawn and re-filed;
 * a `superseded` row is the audit artefact and is frozen entirely.
 *
 * Exported and pure so the rule can be asserted without mounting a page —
 * `discountLifecycleAct`'s own posture one function up, and for the same
 * reason: a control offered in the wrong state is invisible to every check
 * this repo has until somebody presses it.
 */
export function discountCorrectable(versionStatus: string | null | undefined): boolean {
  return versionStatus === "active";
}

export const DEFINITION_ACTION_KEYS = [
  "rating.definition.action.duplicate",
  "rating.definition.action.edit",
  "rating.definition.action.retire",
] as const;

/**
 * The lifecycle acts a DISCOUNT version can take, and the one status each is
 * legal from — DEF-400.
 *
 * ⚠ **EXACTLY ONE ACT IS OFFERED AT A TIME, AND THAT IS THE DESIGN RATHER THAN
 * A SIMPLIFICATION.** BR-RAT-072 gives a version five states and CR-013 part 3
 * gives it one path through them: a draft is submitted, a submitted filing is
 * approved, an approved filing is activated. Drawing all three at once would
 * put two permanently-refusing buttons beside the working one, which is the
 * same noise the Discounts tab's row-actions column argues against.
 *
 * ⚠ **`activate` IS OFFERED FROM `draft` TOO, WARNED RATHER THAN WITHHELD
 * (BR-RAT-109, PO ruling 2026-08-21: _"We will show message and not refuse
 * it"_).** This screen withheld it for one commit, and the reasoning was
 * sound: the second-approval requirement is computed and stored at SUBMIT, so
 * a draft carries none, and the case it bypasses most cleanly is the one the
 * PO ruled ALWAYS needs two people — a discount with no budget cap.
 *
 * The PO ruled warn-and-allow instead, for the third time (backdating
 * 2026-08-11, self-approval 2026-08-19). Silver Creek has 1–2 staff, and a
 * control that requires a second person is a control that stops the business.
 *
 * **So `draft` has TWO acts and `submit` is listed first**, because it is the
 * normal path and the order is what makes it the obvious one. See
 * {@link activationSkipsApprovalCheck} for what the warning may and may not
 * say.
 */
export const DISCOUNT_LIFECYCLE: ReadonlyArray<{ from: string; act: LifecycleAct }> = [
  { from: "draft", act: "submit" },
  { from: "draft", act: "activate" },
  { from: "pending_approval", act: "approve" },
  { from: "scheduled", act: "activate" },
];

export type LifecycleAct = "submit" | "approve" | "activate";

/** The one act legal from this version status, or `null` — an ACTIVE version
 *  has arrived and a SUPERSEDED one is history; neither has a next step, and a
 *  discount with no version at all has nothing to submit. */
export function discountLifecycleAct(versionStatus: string | null | undefined): LifecycleAct | null {
  return DISCOUNT_LIFECYCLE.find((row) => row.from === versionStatus)?.act ?? null;
}

/** Every act legal from this status, in the order they should be offered. */
export function discountLifecycleActs(
  versionStatus: string | null | undefined,
): readonly LifecycleAct[] {
  return DISCOUNT_LIFECYCLE.filter((row) => row.from === versionStatus).map((row) => row.act);
}

/**
 * BR-RAT-109 — does this activation skip the second-approval check?
 *
 * ⚠ **THE WARNING MUST SAY WHAT WAS SKIPPED, NOT THAT SOMETHING WAS.** It
 * cannot say *"this needs two approvals"*, because nothing computed that —
 * skipping submit is precisely why there is no figure to quote. A warning
 * naming a number it does not have would be worse than silence, and is the
 * same failure as the hard-coded `$500` this screen's neighbour carried.
 *
 * So it states two facts it actually holds: the version was never submitted,
 * so no check ran; and where the discount states **no budget cap**, BR-RAT-077
 * would have required a second approval regardless of any threshold — that one
 * is knowable without submit, because it is a property of the discount.
 */
export function activationSkipsApprovalCheck(
  act: LifecycleAct,
  versionStatus: string | null | undefined,
): boolean {
  return act === "activate" && versionStatus === "draft";
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface DefinitionDetailPageProps {
  /** Which of the three this route is. Supplied by `App.tsx`, never guessed
   *  from the URL — the route IS the kind (BR-RAT-084). */
  kind: DefinitionKind;
  client?: ApiClient; // test seam — screens never build their own transport
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

/**
 * ⚠ **THE TAX KIND IS ITS OWN PAGE SINCE CR-165-BRC10 ROUND 3 (task 6).** The
 * Taxes & fees redesign drew a details page this shell's eight parts do not
 * have — no kicker, a facts line of pills and dates, ONE Edit plus More ▾,
 * four tiles, two fact grids and a versions table (images 18–23) — so the tax
 * route mounts `taxDetail/TaxDetailPage` and the charge and discount kinds
 * keep exactly the shell they had. BR-RAT-084's three ROUTES and three screen
 * ids are unchanged; the tax's screen is built from its own drawing (B14 rule
 * 42) out of components (rule 43) rather than as branches inside this file.
 * `kind` is fixed per route, so the split never swaps hooks on one mount.
 */
export function DefinitionDetailPage(props: DefinitionDetailPageProps) {
  if (props.kind === "tax") {
    return <TaxDetailPage client={props.client} timeZone={props.timeZone} dateFormat={props.dateFormat} />;
  }
  // CR-166-BRC10 round 3 task 6 — the discount kind is its own page too,
  // built from images 19–26 (`discountDetail/DiscountDetailPage`), for the
  // reason the tax note above gives. Only the charge kind keeps this shell.
  if (props.kind === "discount") {
    return <DiscountDetailPage client={props.client} timeZone={props.timeZone} dateFormat={props.dateFormat} />;
  }
  return <DefinitionDetailShell {...props} />;
}

function DefinitionDetailShell(props: DefinitionDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = props.client ?? api;
  const kind = props.kind;
  const route = DEFINITION_ROUTES[kind];
  const definitionId = params.definitionId ?? "";
  const active = definitionTabFrom(kind, searchParams.get(TAB_PARAM));
  // DEF-SHL-3964 — this used to spell its own copy of the seed default, one
  // layer below the resolver. Same defect, same cure: the tenant's own setting.
  // (The first wording of this comment named a prop in backtick-quoted code and
  // G13's scanner read the COMMENT as a prop reference — ten false positives.
  // A comment that contains code-shaped text is code to anything that greps.)
  const regional: DefinitionRegional = useRegional(props);

  // BR-SHL-025: the caller's own A4 row, exactly as the tab frame reads it.
  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  // DEF-206: the chart, so a GL reads as an account and never as a uuid.
  const chartQuery = useQuery({
    queryKey: queryKeys.ledgerAccounts,
    queryFn: () => getLedgerAccounts(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const accounts: readonly GlAccountRef[] = chartQuery.data ?? [];

  // ⚠ THREE READS NOW. This block said *"the two reads that exist"* and kept the
  // discount route from firing a request at a path nothing served; CR-013 part 3
  // serves `GET /discounts/{id}`, so the third is here and `definitionIsServed`
  // no longer excludes it. `enabled` still gates each on its own kind, so a
  // charge route issues exactly one request.
  const chargeQuery = useQuery({
    queryKey: queryKeys.charge(definitionId),
    queryFn: () => getCharge(definitionId, client),
    enabled: kind === "charge" && definitionId !== "",
  });
  const discountQuery = useQuery({
    queryKey: queryKeys.discount(definitionId),
    queryFn: () => getDiscount(definitionId, client),
    enabled: kind === "discount" && definitionId !== "",
  });
  const activeQuery = kind === "discount" ? discountQuery : chargeQuery;

  // ── DEF-400: the three lifecycle acts ────────────────────────────────────
  //
  // ⚠ **THIS MUTATION IS THE WHOLE OF WHAT WAS MISSING.** `submit`, `approve`
  // and `activate` were built, tested and mounted on no route for two days, so
  // a utility could write a subsidy programme, save it, read it back on this
  // very screen — and the status pill said `Draft` forever.
  //
  // ⚠ **IT DECIDES NOTHING.** The second-approval requirement is computed at
  // SUBMIT and STORED by the server with the threshold that decided it
  // (BR-RAT-077), so this refetches and RENDERS what came back rather than
  // recomputing anything: an approver must see the requirement the submitter
  // saw, and a tenant that edits the threshold in between must not move the bar
  // under a signature already given.
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const lifecycle = useMutation({
    mutationFn: (input: { act: LifecycleAct; versionId: string }) => {
      const call =
        input.act === "submit"
          ? submitDiscountVersion
          : input.act === "approve"
            ? approveDiscountVersion
            : activateDiscountVersion;
      return call(definitionId, input.versionId, client);
    },
    onSuccess: (_result, input) => {
      setRefusal(null);
      fireToast(t(`rating.definition.lifecycle.toast.${input.act}`));
      void queryClient.invalidateQueries({ queryKey: queryKeys.discount(definitionId) });
      void discountQuery.refetch();
    },
    // BR-SHL-020: the server's own sentence, never a re-worded one. Activation
    // is the act that refuses on a version that saved cleanly — a type no
    // engine can price is refused where an operator is looking at it.
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  if (permissionsQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    return (
      <PermissionDenied
        helper={t("rating.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  const readOnly = ratingIsReadOnly(access);

  // The reason a HELD header button carries. A read-only role gets the RBAC
  // sentence; everyone else gets the honest one.
  //
  // ⚠ IT USED TO SAY *"Duplicate, Edit and Retire arrive with the full-page
  // wizard for this object. This screen reads a definition; it does not change
  // one yet."* — thirty-two words, and by 2026-09-08 every clause of it was
  // false: all three wizards existed and this screen changed a definition from
  // two of them. B14 rule 33 caps a refusal at five or six words, and a refusal
  // that is merely SHORTER but still untrue would have been the worse half of
  // the fix. It now names the only condition still true: neither Duplicate nor
  // Retire has anywhere to go.
  //
  // ⚠ **TWO LANES FOUND THIS INDEPENDENTLY IN THE SAME HOUR AND WROTE TWO
  // KEYS** — `notBuilt` here and `heldNoRoute` from CR-087 E1, six words each
  // and saying the same thing. The second was RETIRED from all eleven
  // catalogues rather than left beside this one: two catalogue entries for one
  // sentence is two places for a re-word to land and one place for it to be
  // missed. The finding is the same either way, and it is worth naming — a
  // hold with a clock in it rots on the day the thing it waited for arrives,
  // and landing that thing and releasing the hold are two acts.
  const actionReason = readOnly
    ? t("rating.readOnlyReason")
    : t("rating.definition.action.notBuilt");

  const served = definitionIsServed(kind);
  if (served) {
    if (activeQuery.isPending) {
      return <LoadingSkeleton variant="card" />;
    }
    if (activeQuery.data === undefined) {
      if (isPermissionDenied(activeQuery.error)) {
        return (
          <PermissionDenied
            helper={t("rating.denied")}
            onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
          />
        );
      }
      // A direct URL to a definition that does not exist (or belongs to another
      // tenant) gets the A18 failed state — never a blank detail shell.
      return (
        <FailedWithRetry
          title={t("rating.definition.failedTitle")}
          reason={apiErrorText(activeQuery.error, translate)}
          onRetry={() => void activeQuery.refetch()}
          onDownloadReport={() => undefined}
          onCancel={() => navigate(tenantPath(route.listRoute))}
        />
      );
    }
  }

  const view: DefinitionPresentation | null =
    kind === "charge" && chargeQuery.data !== undefined
      ? presentCharge(chargeQuery.data, translate, accounts)
      : kind === "discount" && discountQuery.data !== undefined
        ? presentDiscount(discountQuery.data, translate, regional)
        : null;

  // DEF-400 — the version the acts address, and which act it is due. Read off
  // the SERVED row: `version_status` has always been here and `version_id` is
  // what the selector now publishes beside it.
  const discountRow: DiscountDetail | undefined =
    kind === "discount" ? discountQuery.data : undefined;
  const discountVersionId = discountRow?.version_id ?? null;
  // BR-RAT-109 — a draft offers TWO acts. `submit` is first because it is the
  // normal path; `activate` carries the warning below.
  const discountActs = discountLifecycleActs(discountRow?.version_status);
  // BR-RAT-109 — the message the PO ruled instead of a refusal. Visible, not a
  // tooltip: "show a message" is not satisfied by something only a mouse can
  // reveal. `null` when no offered act skips the check.
  const skipsCheckNote = discountActs.some((act) =>
    activationSkipsApprovalCheck(act, discountRow?.version_status),
  )
    ? t(
        discountRow?.budget_cap == null
          ? "rating.definition.lifecycle.skipsCheckUnbounded"
          : "rating.definition.lifecycle.skipsCheck",
      )
    : null;

  const tabs = DEFINITION_TABS[kind].map((id) => ({
    id,
    label: t(`rating.definition.tab.${id}`),
  }));

  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  }

  return (
    <div>
      <PageHeader
        // Part 1 — the back link, to the landing tab that lists this kind.
        backTo={{ to: tenantPath(route.listRoute), label: t(route.backLabelKey) }}
        // Part 2 — the eyebrow. `PageHeader` draws it through the shared Kicker,
        // which is what uppercases it; the catalog holds sentence case.
        kicker={view?.eyebrow ?? t(route.kindLabelKey)}
        // Part 3 — the h1. With no read there is no name, so the kind's own
        // title stands in rather than the raw id being shown at a person.
        title={view?.title ?? t(`rating.definition.title.${kind}`)}
        // Part 4 — the muted sub-line.
        rollup={
          view === null ? undefined : (
            <span className="text-base">
              {view.subline.map((part, index) => (
                <span key={index}>
                  {index > 0 && " · "}
                  {part}
                </span>
              ))}
            </span>
          )
        }
        // Part 5 — the status pill, then the three buttons in r10's order.
        status={
          view === null ? undefined : (
            <RatingStatusPill
              tone={view.statusTone}
              stem={view.statusStem}
              value={view.statusValue}
            />
          )
        }
        secondaryActions={[
          ...(discountVersionId === null
            ? []
            : discountActs.map((act, index) => {
                // BR-RAT-109's warning is NOT on this control. A `title`
                // tooltip is invisible on a touch device and unreliable to a
                // screen reader, so "show a message" would be satisfied only on
                // a mouse — it renders as a visible Note beside the actions.
                return (
                  <GuardedButton
                    key={`lifecycle-${act}`}
                    readOnly={readOnly}
                    readOnlyReason={t("rating.readOnlyReason")}
                    // The FIRST act is the normal path and takes the primary
                    // tier; a second act offered beside it must not compete
                    // with it for the eye (B14 rule 5's two button sizes).
                    variant={index === 0 ? "primary" : "secondary"}
                    disabled={lifecycle.isPending}
                    onClick={() => lifecycle.mutate({ act, versionId: discountVersionId })}
                  >
                    {t(`rating.definition.lifecycle.${act}`)}
                  </GuardedButton>
                );
              })),
          // ── BR-RAT-1016 verb 2 · THE CORRECTION DOOR ────────────────────
          //
          // ⚠ **OFFERED ONLY ON A VERSION THAT IS ACTUALLY IN FORCE, because
          // that is the only state with a recorded figure to correct.** A draft
          // is edited in place, a pending or scheduled filing is withdrawn and
          // re-filed, a superseded row is the audit artefact and is frozen.
          // `correct_discount_version` refuses each of those by name; drawing
          // the button anyway would be four permanently-refusing controls
          // beside one working one, which is the noise the lifecycle cluster
          // above already argues against.
          //
          // ⚠ **IT IS A SEPARATE CONTROL FROM `Edit`, NOT A MODE OF IT.** A new
          // price from a date and *that figure was always wrong* produce
          // different history, and the tax next door only avoids this choice
          // because its price CHANGE is a different object entirely. A screen
          // that guessed would be minting corrections over ordinary rises.
          ...(kind === "discount" && discountCorrectable(discountRow?.version_status)
            ? [
                <GuardedButton
                  key="discount-correct"
                  readOnly={readOnly}
                  readOnlyReason={t("rating.readOnlyReason")}
                  variant="secondary"
                  onClick={() =>
                    navigate(
                      `${tenantPath(definitionWizardPath(kind, definitionId))}?correct=1`,
                    )
                  }
                >
                  {t("rating.definition.action.correct")}
                </GuardedButton>,
              ]
            : []),
          ...DEFINITION_ACTION_KEYS.map((key) => {
          // ⚠ `Edit` IS LIVE ON THE CHARGE KIND SINCE 2026-08-21, and it had to
          // become live in the same commit that made the sentence beside it
          // false. `actionReason` says the wizard *"is not built"* — and each
          // time that stops being true for a kind, THIS LINE moves in the same
          // commit, because a disabled control carrying a reason that has
          // stopped being true is hard-won law 1 and reads as a decision.
          //
          // ⚠ **THE DISCOUNT KIND JOINED IT THE SAME DAY** — DIS-02 is
          // `DiscountWizard.tsx` (§18 row 12).
          //
          // ⚠ **AND THE TAX JOINED IT ON 2026-09-08, TWO WEEKS LATE — THAT IS
          // `DEF-RAT-4647`, AND IT IS HARD-WON LAW 2's MIRROR.** `TaxWizard.tsx`
          // shipped, `App.tsx` routed both `…/new` and `…/{id}/edit`, the SAME
          // clerk could open it from the list one click away — and this button
          // stayed greyed out on every role, over a screen that was live,
          // saying the wizard *"arrives with"* a future release. G13 asks
          // whether a prop is passed; nothing asks whether a REFUSAL is still
          // true, and the paragraph directly above this one had already stated
          // the rule that was broken (*"each time that stops being true for a
          // kind, THIS LINE moves in the same commit"*). Guidance existed;
          // nothing enforced it. `definitionEditHoldExpiry` below is the
          // enforcement — a test that goes RED the day a held destination gains
          // a route.
          //
          // Duplicate and Retire stay held on all three kinds — neither has a
          // route, on any kind, and neither is any wizard's job.
          //
          // ⚠ AND `Edit` MEANS SOMETHING DIFFERENT ON A DISCOUNT, which the
          // route rather than this button expresses: BR-RAT-078 makes
          // enrolments survive versioning, so `…/{id}/edit` drafts a NEW DATED
          // VERSION and never overwrites the live one.
          //
          // ⚠ **THAT PARAGRAPH ENDED *"There is no `PATCH /discounts/{id}` for
          // it to have called"* UNTIL 2026-09-17, AND THERE IS ONE NOW**
          // (`BR-RAT-1016` · `DEF-RAT-5709`). It writes the IDENTITY — what the
          // programme is called and who runs it — and never what it is worth,
          // so the sentence above about a new dated version is unchanged. Two
          // things did change: a DRAFT version nobody has submitted is now
          // edited in place rather than versioned, and a LIVE version can be
          // CORRECTED over the same window through the button beside this one.
          // The wizard picks the first from the version's own state; the
          // correction is a separate door because guessing between *a new price
          // from a date* and *that figure was always wrong* is what
          // `BR-RAT-104` exists to stop.
          const live =
            EDITABLE_KINDS.includes(kind) && key.endsWith("edit") && definitionId !== "";
          return (
            <GuardedButton
              key={key}
              readOnly={live ? readOnly : true}
              readOnlyReason={live ? t("rating.readOnlyReason") : actionReason}
              // B14: the destructive commit takes the danger tier.
              variant={key.endsWith("retire") ? "danger" : "secondary"}
              onClick={
                live
                  ? () => navigate(tenantPath(definitionWizardPath(kind, definitionId)))
                  : () => undefined
              }
            >
              {t(key)}
            </GuardedButton>
          );
          }),
        ]}
        // Part 7 — the tab strip, 5 · 5 · 6 per kind.
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("rating.definition.tabsLabel")}
        onTabSelect={(tab) => selectTab(tab.id)}
      />

      {/* DEF-400 — what a refused act says, in the SERVER's words (BR-SHL-020).
          Activation is the one that refuses on a version that saved cleanly. */}
      <RefusalNotice refusal={refusal} />

      {/* DEF-400 — the two facts about this filing an approver must be able to
          READ rather than work out. Both come off the row; neither is computed
          here. */}
      {discountRow === undefined ? null : (
        <DiscountApprovalNotes row={discountRow} t={translate} />
      )}

      {/* BR-RAT-109 — the message the PO ruled INSTEAD of a refusal. It sits
          beside the approval notes because that is where an operator reads what
          the filing's approval state is, and this is a statement about exactly
          that: no check ran. Rendered whenever the act is OFFERED, not after it
          is taken — a warning that appears once the discount is already live
          informs nobody in time to act on it. */}
      {skipsCheckNote === null ? null : (
        <div className="mt-3">
          <Note>{skipsCheckNote}</Note>
        </div>
      )}

      {/* Part 6 — EXACTLY FOUR tiles, on every kind. With no read the four
          LABELS still render and their figures read "—": the strip's shape is
          part of the specification, and an invented number is not. */}
      <KPIStrip kpis={view?.kpis ?? emptyKpis(kind, translate)} />

      {/* Part 8 — the tab body. */}
      <DefinitionTabBody
        kind={kind}
        tab={active}
        definitionId={definitionId}
        client={client}
        regional={regional}
        fields={view?.panels[active]}
        blocks={view?.blocks?.[active]}
        served={served}
        t={translate}
      />

    </div>
  );
}

/**
 * The two facts a discount filing carries about its own approval — DEF-400.
 *
 * ⚠ **NEITHER IS COMPUTED HERE, AND THAT IS THE RULE RATHER THAN A PREFERENCE.**
 * BR-RAT-077 puts the second-approval requirement on the version at SUBMIT,
 * with the threshold that decided it, precisely so an approver sees the
 * requirement the SUBMITTER saw. A client that re-derived it from the budget cap
 * and today's tenant setting would move the bar under a signature already given
 * — which is the failure the stored column exists to prevent.
 *
 * ⚠ **THE UNBOUNDED CASE GETS ITS OWN SENTENCE.** A discount with no budget cap
 * always requires the second approval (PO 2026-08-19), and saying *"its budget
 * cap is above $50,000"* about a discount that HAS no cap would be false. The
 * two are told apart by the served `budget_cap`, not by re-testing the rule.
 *
 * ⚠ **AND A SELF-APPROVAL IS STATED, NOT HIDDEN.** The PO allowed it — *"yes
 * allow it"*, because a 1–2 staff utility often has no second person — and the
 * server records it so an auditor reads it instead of comparing two user ids.
 * A fact recorded and never shown is a fact nobody has.
 */
export function DiscountApprovalNotes(props: { row: DiscountDetail; t: Translator }) {
  const { row, t } = props;
  const notes: string[] = [];
  if (row.second_approval_required === true) {
    notes.push(
      row.budget_cap === null || row.budget_cap === undefined
        ? t("rating.definition.lifecycle.secondApprovalUnbounded")
        : t("rating.definition.lifecycle.secondApproval", {
            threshold: row.second_approval_threshold_display ?? "",
          }),
    );
  }
  if (row.self_approved === true) {
    notes.push(t("rating.definition.lifecycle.selfApproved"));
  }
  if (notes.length === 0) {
    return null;
  }
  return (
    <div className="mt-3">
      {notes.map((note) => (
        <Note key={note}>{note}</Note>
      ))}
    </div>
  );
}

// ── The tab body ───────────────────────────────────────────────────────────

function DefinitionTabBody(props: {
  kind: DefinitionKind;
  tab: string;
  /** For the tabs that read on their own. Never a visible value (rule 31). */
  definitionId: string;
  client: ApiClient;
  /** BR-SHL-034 — the tenant's own date rendering, passed down rather than
   *  re-resolved, so the Audit tab's EFFECTIVE column and the header's
   *  sub-line cannot disagree about one date. */
  regional: DefinitionRegional;
  fields: readonly DefinitionField[] | undefined;
  blocks: readonly DefinitionBlock[] | undefined;
  served: boolean;
  t: Translator;
}) {
  const { t } = props;
  const heading = t(`rating.definition.panel.${props.tab}`);

  // ⚠ NO KIND TAKES THIS BRANCH TODAY, AND IT IS KEPT DELIBERATELY. It existed
  // for the discount, whose five tabs all named the same absent endpoint while
  // §18 row 11 was *"six tables, no route"*; `GET /discounts/{id}` is served now
  // (CR-013 part 3) and `definitionIsServed` answers true for all three. The
  // branch stays because the FOURTH kind will arrive the same way this one did —
  // declared in `DEFINITION_TABS` before its endpoint exists — and the shape
  // that kept that honest is worth more than the two lines it costs.
  if (!props.served) {
    return (
      <>
        <ArrivesWith title={heading} message={t("rating.definition.kindPending")} />
        {isHistoryTab(props.tab) && <DatedBanner t={t} />}
      </>
    );
  }

  // ⚠ **`isHistoryTab`, NOT A LITERAL — CR-087 C2.** The discount's history tab
  // is called `audit` now, the name every other module uses; the charge and the
  // tax still say `versions`. One predicate knows both, and it goes when they
  // follow. What this branch RENDERS has not changed: the object's own version
  // table, never a filtered `audit_log` query.
  if (isHistoryTab(props.tab)) {
    return (
      <>
        {/* §10: the object's OWN version table. Nothing serves it, and the
            message says which record it is — so a lane reading this does not
            reach for `audit_log`, which answers a different question. */}
        {/* ⚠ **THE TAX'S AUDIT TAB IS BUILT (CR-087, PO 2026-09-10:
            *"build"*).** It rendered one sentence saying no endpoint served its
            versions, which the blueprint quotes back as the defect;
            `GET /taxes/{id}/versions` is that endpoint. **Still the object's OWN
            version table and never a filtered `audit_log` query** — §10's
            refusal is unchanged and `DefinitionDetail.test.tsx` still reads this
            file as text and fails on an audit reference in it. The CHARGE and
            the DISCOUNT keep the stated absence: neither has a chain to read,
            and the charge has no version object at all. */}
        {/* CR-166-BRC10 round 3 task 6 — the DISCOUNT's history moved with
            the kind to `discountDetail/` (versions on Overview, every change on
            Audit, the draft's discard in More ▾), and `discountDetailTabs.tsx`
            went with it. This tab is the CHARGE's alone now, and the charge has
            no version object, so it keeps its stated absence. */}
        <ArrivesWith title={heading} message={t("rating.definition.versions.arrivesWith")} />
        <DatedBanner t={t} />
      </>
    );
  }

  if (props.tab === PLANS_TAB) {
    // ⚠ **THE TAX'S PLANS TAB IS BUILT (same ruling, same day).**
    // `GET /taxes/{id}/plans` names the plans the tile counts and says HOW each
    // one gets the tax — the two mechanisms `BR-RAT-113` gives, which behave
    // differently when the authority changes.
    // ⚠ **THE CHARGE'S PLANS TAB IS BUILT (`CR-087`, PO 2026-09-10: *"build"*).**
    // It rendered ONE SENTENCE saying it could not do its job — *"The tile above
    // counts the plans that carry this definition. Naming them one by one needs a
    // read that does not exist yet"* — which is the exact text the blueprint
    // quotes back as the defect. `GET /charges/{id}/plans` is that read, and it
    // counts BOTH routes: named on the plan, and read as the base of a rate
    // schedule the plan carries (`DEF-RAT-4832`).
    if (props.kind === "charge" && props.definitionId !== "") {
      return <ChargePlansTab chargeId={props.definitionId} client={props.client} t={t} />;
    }
    // The KPI tile says HOW MANY plans carry it (`used_by_plans`, served). WHICH
    // plans is a different read and no route answers it. Still true of the
    // DISCOUNT, which is why the sentence stays rather than being widened.
    return <ArrivesWith title={heading} message={t("rating.definition.plans.arrivesWith")} />;
  }

  // ⚠ BLOCKS WIN OVER THE FLAT LIST, AND THE FALLBACK IS NOT DEAD CODE. The
  // CHARGE kind still hands over `fields` and draws exactly what it drew before
  // CR-087; the tax's merged Overview declares blocks and so does the
  // discount's — this sentence said *"only the tax's"* for one commit and was
  // true when it was written (hard-won law 1, corrected rather than left). A
  // renderer that normalised the two would force the other kinds through a
  // grouping they do not have — BR-RAT-084's *"the shell must not force them to
  // be"* identical, one layer down.
  if (props.blocks !== undefined && props.blocks.length > 0) {
    return (
      <>
        {props.blocks.map((block) => (
          <Panel as="section" key={block.id} data-definition-block={block.id}>
            <Kicker as="div">{t(block.titleKey)}</Kicker>
            {/* B14 rule 32 — ONE sentence per section, and most have none. */}
            {block.noteKey !== undefined && <Note>{t(block.noteKey)}</Note>}
            <FieldList fields={block.fields} t={t} />
          </Panel>
        ))}
      </>
    );
  }

  if (props.fields === undefined) {
    // A tab a kind declares and no presenter fills. It cannot happen for the
    // two served kinds today, and saying so beats rendering an empty panel.
    return <ArrivesWith title={heading} message={t("rating.definition.tabPending")} />;
  }

  return (
    <Panel as="section">
      <Kicker as="div">{heading}</Kicker>
      <FieldList fields={props.fields} t={t} />
    </Panel>
  );
}

// ── CHG-01 · the Plans tab ─────────────────────────────────────────────────

const REACH_TH =
  "text-left align-bottom py-2 pr-4 border-b border-b-divider font-extrabold " +
  "text-table-header uppercase tracking-table-header " +
  "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

const REACH_TD = "align-top py-2 pr-4 border-b border-b-divider";

/**
 * **WHERE THIS CHARGE ACTUALLY REACHES CUSTOMERS — `CR-087` · `CHG-01`, PO
 * ruling 2026-09-10: *"build"*.**
 *
 * The tab said, over a screen whose whole job is to answer it, that it could not
 * name a single plan. Four columns now do: the plan, the plan's own printed
 * code, WHICH OF THE TWO ROUTES reaches it, and how many units are on it.
 *
 * ⚠ **THE ROUTE COLUMN IS THE REASON THE TAB IS WORTH BUILDING.** The
 * blueprint's own callout: *"renaming a plan's charge is local; changing a base
 * moves every size on a schedule. Naming the route is what stops a clerk
 * mistaking one for the other."*
 *
 * ⚠ **`reached_by` IS THE SERVER'S WORD, NEVER DERIVED FROM THE BLANK CODE
 * CELL.** A screen that read the route off `plan_code === null` would decide a
 * fact the server already knows, and the two would part company the first time
 * a plan carried a code with no printed reference.
 *
 * ⚠ **PAGED FROM THE SERVER (`NFR-3`), AND `total` IS THE WHOLE SET.** The tile
 * above and this table have to agree past fifty rows, and a pager fed the page's
 * own length reports *"1–50 of 50"* over a code carried by 300 plans. Nothing
 * caps the set (`NFR-5`).
 *
 * ⚠ **B14 RULE 16 WINS OVER THE DRAWING HERE, AND THE DRAWING WINS ON THE
 * SENTENCE.** The frame draws no pagination footer at all; rule 16 puts one on
 * every list table and `NFR-3` is a `CLAUDE.md` requirement rather than a
 * preference. What the drawing DOES decide is what the count means — *"how many
 * were checked out of how many CARRYING THIS CODE, never out of every plan in
 * the utility"* — and that is exactly what the served `count` is.
 */
function ChargePlansTab(props: { chargeId: string; client: ApiClient; t: Translator }) {
  const { t } = props;
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PAGE_SIZES[0]);
  const reachQuery = useQuery({
    queryKey: queryKeys.chargePlans(props.chargeId, page),
    queryFn: () => getChargePlans(props.chargeId, { page, per }, props.client),
    // The page a clerk is reading stays on screen while the next arrives.
    placeholderData: (previous) => previous,
  });
  const rows: readonly ChargeReachRow[] = reachQuery.data?.results ?? [];
  const total = reachQuery.data?.count ?? 0;

  return (
    <Panel as="section">
      <Kicker as="div">{t("rating.chargePlans.heading")}</Kicker>
      {/* B14 rule 32 — ONE sentence for the section. */}
      <Note>{t("rating.chargePlans.note")}</Note>
      {reachQuery.isError ? (
        <Note>{t("rating.chargePlans.failed")}</Note>
      ) : reachQuery.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : rows.length === 0 ? (
        /* B14 rule 17 — the empty state says what is missing. BOTH routes are
           named, so a zero here is never ambiguous: the drawing's own
           `Nothing carries it` state. */
        <Note>{t("rating.chargePlans.empty")}</Note>
      ) : (
        <>
          <div className="overflow-x-auto mt-4">
            <table className="w-full border-collapse text-table">
              <thead>
                <tr>
                  {["plan", "code", "reachedBy"].map((column) => (
                    <th key={column} scope="col" className={REACH_TH}>
                      {t(`rating.chargePlans.col.${column}`)}
                    </th>
                  ))}
                  {/* A count is a number, so it reads down its right edge. */}
                  <th scope="col" className={`${REACH_TH} text-right pr-0`}>
                    {t("rating.chargePlans.col.units")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.plan_id} data-reach={row.reached_by}>
                    <th scope="row" className={`${REACH_TD} text-left font-extrabold`}>
                      {row.plan_name}
                    </th>
                    <td className={REACH_TD}>
                      {row.plan_code === null ? (
                        /* NOT a bare dash. The plan does not NAME this code —
                           it reads the base off it — and a blank cell would
                           read as a missing value rather than as the fact the
                           next column states. */
                        <ReachAbsent reason={t("rating.chargePlans.noPlanCode")} />
                      ) : (
                        row.plan_code
                      )}
                    </td>
                    <td className={REACH_TD}>
                      {t(`rating.chargePlans.reachedBy.${row.reached_by}`)}
                    </td>
                    <td className={`${REACH_TD} text-right pr-0`}>{row.units}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ListPager
            page={page}
            per={per}
            total={total}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1); // a bigger page starting at page 9 lands past the end
            }}
          />
        </>
      )}
      {/* The frame's `TWO ROUTES` callout — the fact the whole tab turns on,
          said once under the table rather than repeated on every base row. */}
      <div className="border-l-2 border-l-accent bg-surface p-3 mt-4" role="note">
        <Kicker as="div">{t("rating.chargePlans.routesLabel")}</Kicker>
        <Note>{t("rating.chargePlans.routes")}</Note>
      </div>
    </Panel>
  );
}

/** An absent value that states WHY, so a dash is never read as a zero — the
 *  shape `PlanDetail` and `RateScheduleDetail` already draw. */
function ReachAbsent(props: { reason: string }) {
  return (
    <span className="inline-flex flex-col gap-1">
      <span
        aria-hidden="true"
        className="text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]"
      >
        —
      </span>
      <Note as="span">{props.reason}</Note>
    </span>
  );
}

/** The DATED banner that closes every Versions tab (§10), verbatim. An
 *  accent-ruled strip with the literal label — the catalog carries sentence
 *  case and `Kicker` uppercases it, so the rule survives translation. */
function DatedBanner(props: { t: Translator }) {
  return (
    <section
      className="border-l-2 border-l-accent bg-surface p-3 mb-4 max-w-measure"
      role="note"
      data-dated-banner=""
    >
      <Kicker as="div">{props.t("rating.definition.dated.label")}</Kicker>
      <Note>{props.t("rating.definition.dated.body")}</Note>
    </section>
  );
}

/**
 * One panel's labelled facts. Two columns, collapsing to one below the `sm`
 * breakpoint (720px) — the labels are the KEYS the presenter chose, resolved
 * here so no sentence is ever spelled in a component.
 *
 * ⚠ IT IS `max-sm:` AND NOT `sm:`, AND THAT IS THE RATIFIED DIRECTION RATHER
 * THAN A PREFERENCE. This app is DESKTOP-FIRST: `g36_breakpoint_direction.py`
 * measures 15 max-width rules and zero min-width ones across the stylesheets
 * and fails on the difference. Tailwind's bare `sm:` is min-width, so writing
 * the obvious thing here would have inverted the convention in the one place
 * that gate cannot see — it reads CSS files, and a utility is not in one.
 */
function FieldList(props: { fields: readonly DefinitionField[]; t: Translator }) {
  return (
    <dl className="grid grid-cols-2 max-sm:grid-cols-1 gap-3 m-0">
      {props.fields.map((field) => (
        <div key={field.labelKey}>
          <dt className="text-xs uppercase tracking-kicker font-heading font-extrabold text-neutral-700">
            {props.t(field.labelKey)}
          </dt>
          <dd className="m-0 text-base">{field.value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-013 P2 (rows 8 · 11 · 14) · BR-RAT-084 (PO ruling 2026-08-20)
// generated: 2026-08-20
// checklist: A✔ B✔ C✔ D=deferred(no API half — GET /charges/{id} and GET /taxes/{id} were already served; GET /discounts/{id} and the version list are NOT authored here) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest 34/34 (DefinitionDetail.test.tsx)✔ g31_declared_classes✔ routeBUtilities 9/9✔ g29_screen_ids✔
// exceptions: E1 — three of the twelve KPI figures have no server read and
//            render "—" with the missing route named in `definitionDetail.tsx`.
//            E2 — PARTLY CLOSED 2026-08-21: the header's `Edit` is LIVE on the
//            CHARGE kind and opens CHG-02 (`ChargeCodeWizard.tsx`, §18 row 9).
//            Duplicate and Retire stay drawn-disabled-with-their-reason on all
//            three kinds, and Edit stays so on the discount and the tax, whose
//            wizards (rows 12 · 15) are not built. The reason string had to
//            stop covering the charge code in the same commit that made it
//            false — a disabled control carrying a reason that is no longer
//            true is hard-won law 1, and reads as a decision.
//            E3 — the discount kind has no read at all (no `/discounts` route
//            in `apps/rating/api.py`), so its five tabs state what they wait
//            for rather than rendering an empty object.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
