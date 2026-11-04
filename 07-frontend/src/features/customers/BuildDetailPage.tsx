// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · **the New Connect BUILD DETAIL page** — task 4, the
//           shell, and the wiring of tasks 5 to 14.
// Screens:  `NCT-02` (B18 §5.4.9), un-retired by the PO ruling of 2026-09-28.
// Drawing:  all ten PNGs of `05-prototype/new-connect-detail-2026-09-28/`,
//           each opened with the Read tool and LOOKED AT before a line of this
//           file was written (B14 rule 42, PO: *"ensure you use images to
//           build screens and not text/content"*).
// Rules:    B14 rule 1 (the `←` names where the page EXITS to) · rule 2 (ONE
//           page header, the shared component) · rule 40 (its title is 32px,
//           which that component sets) · rule 31 (no database id is a visible
//           value) · rule 33 (the copy caps) · rule 37 (every drawn figure is
//           an ILLUSTRATION — nothing below is hard-coded from a PNG) ·
//           rule 44 (the drawing says WHAT and HOW ARRANGED; our UI standard
//           says HOW IT IS BUILT, and it wins — so the header is the kit's
//           `PageHeader` with the kit's own slot order) · BR-SHL-011 (`?tab=`,
//           and an unknown value falls back rather than erroring) ·
//           BR-SHL-025 (a control that cannot act is disabled WITH its reason).
// Tests:    src/features/customers/BuildDetailPage.dom.test.tsx ·
//           src/features/customers/BuildDetailTabs.dom.test.tsx ·
//           src/features/customers/BuildDetailDialogs.dom.test.tsx
// Impacts:  the route and `routing/screenIds.ts` are the REVERSAL lane's, in
//           its own commit; this file mounts nothing by itself.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE HEADER HOLDS, AND THE TWO BUTTONS THAT ARE DELIBERATELY ABSENT
// ══════════════════════════════════════════════════════════════════════════
// Back link → the list it came from · kicker `B-… · SR-…`, the two numbers a
// clerk reads out · title, the premise name, because that is what people call
// the build · roll-up: address · unit count · raised by and when · the service
// chips · the state · a `More` menu of seven acts and ONE primary act.
//
// ⚠ **NO `Open premises` AND NO `Open account`.** The PO removed both on
// 2026-09-28: the Overview table links each of them, and a link in two places
// is one that goes stale in one of them.
//
// ══════════════════════════════════════════════════════════════════════════
// THE OWNER ACCOUNT'S ID IS DERIVED, AND THE DERIVATION IS VERIFIED
// ══════════════════════════════════════════════════════════════════════════
// Four things on this page need it — the Overview's account link, the Charges
// tab's *Billed to*, the Documents tab and Take payment — and **neither read
// serves it**: `GET /connections/{id}` carries `owner_account_no` and the
// record carries `money.billed_to`, both NUMBERS.
//
// `GET /premises/{id}/build` DOES carry `home: {kind, id}`, and it is the read
// the premises detail already uses. But it answers *the NEWEST build at this
// address*, and a property can be built on twice — so the answer is used ONLY
// when the build it names IS this build. A mismatch yields `null`, every
// dependent control is refused BY NAME, and nothing is pointed at an id this
// page guessed. A link built from a guessed id passes every assertion in this
// repository and opens onto nothing (hard-won law 6).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getTenantServices } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { Button, ButtonLink } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { enabledServiceRows } from "@/features/metering/ServicesAvailableField";
import {
  CELL_FULL,
  PREMISES_PERMISSION,
  ServiceTags,
  useAccessCell,
  useRegional,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { buildRecordQueryKey, scopedOrdersQueryKey } from "@/features/work/buildViews";
import type { BuildAct } from "@/features/work/buildViews";
import { getBuildRecord, getPremisesBuild } from "@/features/work/workEndpoints";
import type { AddServiceOption, AddServiceUnit } from "@/features/work/buildRecord/AddServiceChoice";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ACTS_THAT_ASK,
  BUILD_DETAIL_SCREEN,
  BuildActPrompt,
  BuildMoreMenu,
  buildDetailTabs,
  buildFactsOf,
  buildTabFrom,
  useBuildActs,
} from "./BuildDetailShared";
import { BuildDraftBody, BuildRepakDialog, carryOnPath, useDraftPark } from "./BuildDetailDraft";
import { ParkedBadge } from "./parkedDrafts";
import { BuildTakePaymentDialog } from "./BuildDetailDialogs";
// ⚠ **THE SEVEN TAB BODIES, THE STATE PILL AND THE PRIMARY ACT ARE COMPOSED
// FROM `features/work/buildRecord/` AND ARE NOT WRITTEN HERE (`DEF-CUS-7618`,
// 2026-09-28).** They were eight build panels declared in
// `features/customers/BuildDetailTabs.tsx`, which is a second home for a build
// panel — `CR-151-BRC09` §2 rule (2), *"NO PANEL IS COPIED. The page composes
// `features/work/buildViews.tsx` and its `buildRecord/` kit"* — and `G93`
// check 1 went red on every one of them within a minute of the page landing.
// This page is now what the ruling says it is: a header, a tab strip, four
// dialogs and a composition.
import { BuildAuditTab } from "@/features/work/buildRecord/BuildAuditTab";
import { BuildChargesTab } from "@/features/work/buildRecord/BuildChargesTab";
import { BuildDocumentsTab } from "@/features/work/buildRecord/BuildDocumentsTab";
import { BuildMessagesTab } from "@/features/work/buildRecord/BuildMessagesTab";
import { BuildOverviewTab } from "@/features/work/buildRecord/BuildOverviewTab";
import { BuildPrimaryAction } from "@/features/work/buildRecord/BuildPrimaryAction";
import { BuildRaiseOrderDialog } from "@/features/work/buildRecord/BuildRaiseOrderDialog";
import { BuildStatePill } from "@/features/work/buildRecord/BuildStatePill";
import { BuildUnitsTab } from "@/features/work/buildRecord/BuildUnitsTab";
import { BuildWorkTab } from "@/features/work/buildRecord/BuildWorkTab";
import type { BuildTabProps } from "@/features/work/buildRecord/buildTabShell";
import { addConnectionService, getConnection, connectionDetailQueryKey } from "./newConnectEndpoints";
import {
  activateServices,
  activationQueryKey,
  addBuildUnit,
  getActivation,
  todosQueryKey,
} from "./buildLifecycleEndpoints";
import { BuildAddServiceForm, BuildAddUnitForm, servicesOfThisBuild } from "./BuildLifecycleForms";
import { ActivateBuildDialog } from "@/features/work/buildRecord/ActivateBuildDialog";
import { BuildTodoTab } from "@/features/work/buildRecord/BuildTodoTab";
import { WarningBox } from "@/components/WarningBox";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { isDraftBuild } from "./newConnectShared";
import type { Translator } from "./newConnectShared";

/** Where the `←` exits to — the list this page came from (B14 rule 1). */
export const NEW_CONNECTS_LIST_PATH = "/accounts?tab=new-connects";

export interface BuildDetailPageProps extends RegionalProps {
  client?: ApiClient;
}

export function BuildDetailPage(props: BuildDetailPageProps) {
  const { t: translate } = useTranslation();
  const t: Translator = (key, params) => translate(key, params);
  const client = props.client ?? api;
  const params = useParams();
  const location = useLocation();
  const tenantPath = useTenantPath();
  const [search, setSearch] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);

  const connectionId = params.connectionId ?? "";
  const [asking, setAsking] = useState<BuildAct | null>(null);
  const [dialog, setDialog] = useState<"takePayment" | "repark" | "raiseOrder" | null>(null);
  const toast = useToast();
  const queryClient = useQueryClient();

  // ⊕ `DEF-MET-9238` — WHO may act on a build. Every write here is the
  // server's `AdminOrClerk`, which is the A4 *Premises / Accounts* cell at
  // `Full`; a role that only VIEWS it (Executive) is shown every control
  // DISABLED WITH ITS REASON (BR-SHL-025 — never hidden), and the server
  // refuses regardless. A null cell (not answered yet) offers the control, the
  // asset page's own reading.
  const accessCell = useAccessCell(PREMISES_PERMISSION, client);
  const readOnlyReason =
    accessCell === null || accessCell === CELL_FULL
      ? null
      : t("metering.rbac.readOnly", { defaultValue: "Your role can view this but not change it." });

  const detailQuery = useQuery({
    queryKey: connectionDetailQueryKey(connectionId),
    queryFn: () => getConnection(connectionId, client),
    enabled: connectionId !== "",
    retry: false,
  });
  const detail = detailQuery.data ?? null;

  const recordQuery = useQuery({
    queryKey: buildRecordQueryKey(connectionId),
    queryFn: () => getBuildRecord(connectionId, {}, client),
    enabled: connectionId !== "",
    retry: false,
  });
  const record = recordQuery.data ?? null;

  // The account id, derived and VERIFIED — see this file's header.
  const premisesId = detail?.premises?.id ?? null;
  const hostQuery = useQuery({
    queryKey: ["work", "build", "premises", premisesId ?? ""],
    queryFn: () => getPremisesBuild(premisesId as string, client),
    enabled: premisesId !== null,
    retry: false,
  });
  const accountId =
    hostQuery.data !== undefined &&
    hostQuery.data !== null &&
    hostQuery.data.id === connectionId &&
    hostQuery.data.home?.kind === "account"
      ? hostQuery.data.home.id
      : null;

  const draft = detail !== null && isDraftBuild(detail.state);
  const parkQuery = useDraftPark(connectionId, client, draft);
  const park = draft ? (parkQuery.data ?? null) : null;

  // The tenant's OWN enabled list, under the SHARED key — never a hand-typed
  // one. `SignupWizard.tsx` and `ratingShared.tsx` are why (CLAUDE.md: an
  // eleventh service does not reach a screen on its own and it fails silently).
  const tenantServices = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    retry: false,
  });
  const services: AddServiceOption[] = useMemo(
    () =>
      enabledServiceRows(tenantServices.data).map((row: { service: string; name: string }) => ({
        code: row.service,
        name: row.name,
      })),
    [tenantServices.data],
  );
  const units: AddServiceUnit[] = useMemo(
    () => (detail?.unit_rows ?? []).map((row) => ({ id: row.id, label: row.label })),
    [detail],
  );

  const acts = useBuildActs({ connectionId, client, onDone: () => setAsking(null) });

  // ── CR-162-BRC10 · APPROVE / ACTIVATE ─────────────────────────────────────
  // ONE read and ONE dialog for the header's *Approve* and the Units tab's
  // buttons, so the table and the dialog cannot disagree about what is ready.
  const activationQuery = useQuery({
    queryKey: activationQueryKey(connectionId),
    queryFn: () => getActivation(connectionId, client),
    enabled: connectionId !== "",
    retry: false,
  });
  const [activating, setActivating] = useState<string[] | null>(null);
  const [activationRefusal, setActivationRefusal] = useState<string | null>(null);
  const activate = useMutation<unknown, unknown, { ids: string[]; acknowledge: boolean }>({
    mutationFn: ({ ids, acknowledge }) =>
      activateServices(connectionId, { service_ids: ids, acknowledge_open_orders: acknowledge }, client),
    onSuccess: () => {
      setActivating(null);
      setActivationRefusal(null);
    },
    onError: (error) => setActivationRefusal(apiErrorText(error, translate)),
    onSettled: () => {
      for (const key of [
        activationQueryKey(connectionId),
        connectionDetailQueryKey(connectionId),
        buildRecordQueryKey(connectionId),
        todosQueryKey(connectionId),
      ]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    },
  });
  function openActivate(ids: string[]): void {
    setActivationRefusal(null);
    setActivating(ids);
  }
  const notActivated = (activationQuery.data?.rows ?? [])
    .filter((row) => row.state !== "activated")
    .map((row) => row.id);

  if (detailQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (detail === null) {
    return (
      <FailedWithRetry
        title={t("customers.build.failedTitle", { defaultValue: "The build did not load." })}
        reason={t("customers.build.failed", { defaultValue: "Try again in a moment." })}
        onRetry={() => void detailQuery.refetch()}
      />
    );
  }

  const facts = buildFactsOf(detail);
  const active = buildTabFrom(search.get("tab"), draft);
  const here = location.pathname;
  const tabs = buildDetailTabs({ t, here, draft });
  const serviceCodes = record?.header.services ?? detail.services.map((block) => block.service);

  function press(act: BuildAct): void {
    // `DEF-CUS-9177` — a form, not a one-press POST of a guessed order.
    if (act === "raiseOrder") {
      setDialog("raiseOrder");
      return;
    }
    if (ACTS_THAT_ASK.includes(act) || act === "addService" || act === "addUnit") {
      setAsking(act);
      return;
    }
    if (act === "closeOutstanding") {
      acts.mutate({ act, text: "", todoId: detail?.outstanding[0]?.id });
      return;
    }
    acts.mutate({ act, text: "" });
  }

  const tabProps: BuildTabProps = {
    t,
    detail,
    record,
    timeZone,
    dateFormat,
    path: tenantPath,
    accountId,
    client,
    readOnlyReason,
  };

  // ⚠ **THE PRIMARY ACT IS PER TAB, WHICH IS WHAT `PageHeaderTab.primaryAction`
  // IS FOR** (BR-SHL-044 (a)). Charges commits money, so its primary is *Take
  // payment*; everywhere else the act that CREATES something is *Raise order*.
  // Documents and Messages carry NONE, and that is deliberate — see this
  // file's lifecycle note.
  const withActions = tabs.map((tab) => {
    if (draft) {
      return tab.id === "overview"
        ? {
            ...tab,
            primaryAction: (
              // A LINK and not a button: it navigates into the wizard, so
              // ⌘-click and the browser's own *open in new tab* keep working
              // — `ButtonLink`'s own reason for existing.
              <ButtonLink
                variant="primary"
                data-act="carryOn"
                to={tenantPath(carryOnPath(connectionId, park))}
              >
                {t("customers.build.draft.carryOn", { defaultValue: "Carry on" })}
              </ButtonLink>
            ),
          }
        : tab;
    }
    if (tab.id === "charges") {
      // ⚠ **NOTHING OWED, NOTHING TO TAKE (`DEF-CUS-9185`).** A live primary
      // over `0.00` outstanding invites a payment that can only become credit.
      // Disabled WITH its reason (BR-SHL-025), never hidden. Read off the
      // server's STORED string — zero or below — so no figure is re-parsed
      // into a float to decide it.
      const owedStored = record?.money.outstanding.stored ?? null;
      const nothingOwed = owedStored !== null && (/^-/.test(owedStored) || /^0+(\.0+)?$/.test(owedStored));
      const nothingOwedReason =
        readOnlyReason ??
        (nothingOwed
          ? t("customers.build.takePayment.nothingOwed", { defaultValue: "Nothing owed" })
          : null);
      return {
        ...tab,
        primaryAction: (
          <Button
            variant="primary"
            data-act="takePayment"
            disabled={nothingOwedReason !== null}
            title={nothingOwedReason ?? undefined}
            data-blocked-reason={nothingOwedReason ?? undefined}
            onClick={nothingOwedReason !== null ? undefined : () => setDialog("takePayment")}
          >
            {t("customers.build.takePayment.title", { defaultValue: "Take payment" })}
          </Button>
        ),
      };
    }
    if (tab.id === "documents" || tab.id === "messages") {
      return tab;
    }
    return {
      ...tab,
      primaryAction: (
        <BuildPrimaryAction
          t={t}
          build={facts}
          working={acts.isPending}
          onPress={() => press("raiseOrder")}
          blockedReason={readOnlyReason}
        />
      ),
    };
  });

  return (
    <div data-screen={BUILD_DETAIL_SCREEN} data-build-detail={detail.connection_no ?? undefined}>
      <PageHeader
        backTo={{
          to: tenantPath(NEW_CONNECTS_LIST_PATH),
          label: t("customers.build.back", { defaultValue: "New connects" }),
        }}
        // ⚠ **THE TWO BUSINESS NUMBERS, NEVER THE UUID** (B14 rule 31). A draft
        // has no request behind it when it was raised directly, so the second
        // half simply is not there rather than being a dash.
        kicker={[
          detail.connection_no,
          // ⚠ **TWO DIFFERENT FACTS, NOT ONE SAID TWICE.** On a committed
          // build the second segment is the REQUEST it came from; on a draft
          // it is that the build itself is unfinished, while the pill beside
          // it says whether anybody PARKED it. `10-draft.png` draws both.
          draft ? t("customers.build.draftWord", { defaultValue: "Draft" }) : detail.request_no,
        ]
          .filter((one) => one !== null && one !== "")
          .join(" · ")}
        title={
          // The premise NAME, because that is what people call the build. A
          // build whose address has not resolved yet (`DEF-CUS-6109`) has no
          // premises block at all, so the number is what a clerk has.
          detail.premises?.name ?? detail.premises?.premise_no ?? (detail.connection_no ?? "")
        }
        status={
          park === null ? (
            <BuildStatePill state={detail.state} t={t} />
          ) : (
            // A parked draft's pill says PARKED, which is a fact about the
            // wizard row and not about the build — see the kicker note.
            <ParkedBadge parked t={t} />
          )
        }
        rollup={
          <span className="flex flex-wrap items-center gap-2">
            {detail.premises?.address !== null && detail.premises !== null && (
              <span>{detail.premises.address}</span>
            )}
            <span>
              {/* `DEF-MET-9649` — a plural key with its one-unit case; it read
                  `1 units` off a default baked into the page. */}
              {t("customers.build.rollup.units", { count: detail.units })}
            </span>
            {detail.started_at !== null && (
              <span>
                {t("customers.build.rollup.raised")}{" "}
                <DateCell
                  value={detail.started_at}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                />
                {detail.applicant !== null && <span> · {detail.applicant}</span>}
              </span>
            )}
            <ServiceTags services={serviceCodes} t={t} />
          </span>
        }
        secondaryActions={
          <>
          {/* CR-162-BRC10 — *Approve*: the same dialog the Units tab opens,
              with every row not yet activated chosen, so it lists what is
              ready, what a gate holds and what is still open. */}
          {!draft && (
            <Button
              variant="primary"
              data-act="approve"
              disabled={
                readOnlyReason !== null ||
                activationQuery.data?.can_activate !== true ||
                notActivated.length === 0
              }
              title={
                readOnlyReason ??
                (activationQuery.data?.refusal
                  ? t(activationQuery.data.refusal, { defaultValue: activationQuery.data.refusal })
                  : undefined)
              }
              data-blocked-reason={readOnlyReason ?? undefined}
              onClick={readOnlyReason !== null ? undefined : () => openActivate(notActivated)}
            >
              {t("customers.build.act.approve", { defaultValue: "Approve" })}
            </Button>
          )}
          <BuildMoreMenu
            t={t}
            build={facts}
            onPress={press}
            blockedReason={readOnlyReason}
            // A DRAFT offers two acts — `10-draft.png`. Nothing else on a build
            // that has created nothing can be held, released or added to.
            // CR-162-BRC10 (Q3): *Mark / Close outstanding* leave this menu —
            // the To-do tab adds, completes and reopens them.
            only={draft ? ["cancel"] : ["hold", "release", "waitingOn", "addUnit", "addService", "cancel"]}
            extra={
              draft
                ? [
                    {
                      id: "repark",
                      label: t("customers.build.draft.repark", { defaultValue: "Re-park" }),
                      onPress: () => setDialog("repark"),
                    },
                  ]
                : undefined
            }
          />
          </>
        }
        tabs={withActions}
        activeTabId={active}
        tabsLabel={t("customers.build.tabsLabel", { defaultValue: "Build" })}
        onTabSelect={(tab) => {
          const next = new URLSearchParams(search);
          next.set("tab", tab.id);
          setSearch(next, { replace: true });
        }}
      />

      {asking !== null && asking !== "addService" && asking !== "addUnit" && (
        <BuildActPrompt
          act={asking}
          t={t}
          onClose={() => setAsking(null)}
          onConfirm={async (text) => {
            await acts.mutateAsync({ act: asking, text });
            return { ok: true };
          }}
          note={
            asking === "cancel" && (activationQuery.data?.accounts_on_units.length ?? 0) > 0 ? (
              <WarningBox
                tone="now"
                data-warning="cancel-open-accounts"
                sentence={t("customers.build.cancel.accountsOpen", {
                  defaultValue: "These accounts stay open. Close them yourself.",
                })}
                note={(activationQuery.data?.accounts_on_units ?? [])
                  .map((row) => `${row.account_no ?? ""} · ${row.unit_label ?? ""}`)
                  .join(", ")}
              />
            ) : undefined
          }
        />
      )}
      {/* CR-162-BRC10 item 8 — *Add service* as a proper form. */}
      {asking === "addService" && (
        <BuildAddServiceForm
          t={t}
          services={services}
          units={units}
          onClose={() => setAsking(null)}
          onSave={async (body) => {
            await addConnectionService(connectionId, body, client);
            setAsking(null);
            void queryClient.invalidateQueries({ queryKey: connectionDetailQueryKey(connectionId) });
            void queryClient.invalidateQueries({ queryKey: activationQueryKey(connectionId) });
          }}
        />
      )}
      {/* CR-162-BRC10 item 7 — *Add unit*, with its services. */}
      {asking === "addUnit" && (
        <BuildAddUnitForm
          t={t}
          // ⊕ `DEF-MET-9262` — the build's own services only.
          services={servicesOfThisBuild(services, serviceCodes)}
          client={client}
          onClose={() => setAsking(null)}
          onSave={async (body) => {
            await addBuildUnit(connectionId, body, client);
            setAsking(null);
            void queryClient.invalidateQueries({ queryKey: connectionDetailQueryKey(connectionId) });
            void queryClient.invalidateQueries({ queryKey: activationQueryKey(connectionId) });
            void queryClient.invalidateQueries({ queryKey: buildRecordQueryKey(connectionId) });
          }}
        />
      )}
      {activating !== null && activationQuery.data !== undefined && (
        <ActivateBuildDialog
          t={t}
          read={activationQuery.data}
          chosen={activating}
          working={activate.isPending}
          refusal={activationRefusal}
          onActivate={(ids, acknowledge) => activate.mutate({ ids, acknowledge })}
          onClose={() => setActivating(null)}
        />
      )}

      {draft ? (
        active === "documents" ? (
          <BuildDocumentsTab {...tabProps} />
        ) : active === "audit" ? (
          <BuildAuditTab {...tabProps} />
        ) : (
          <BuildDraftBody
            t={t}
            detail={detail}
            park={park}
            timeZone={timeZone}
            dateFormat={dateFormat}
            path={tenantPath}
          />
        )
      ) : (
        <BuildTabBody
          {...tabProps}
          active={active}
          onActivate={openActivate}
        />
      )}

      {dialog === "takePayment" && (
        <BuildTakePaymentDialog
          t={t}
          accountId={accountId}
          accountNo={detail.owner_account_no ?? record?.money.billed_to ?? null}
          ownerName={record?.header.owner_name ?? null}
          invoiceNo={record?.money.invoice_no ?? null}
          outstanding={record?.money.outstanding ?? null}
          timeZone={timeZone}
          dateFormat={dateFormat}
          client={client}
          connectionId={connectionId}
          onClose={() => setDialog(null)}
          onDone={() => void recordQuery.refetch()}
        />
      )}
      {dialog === "raiseOrder" && (
        <BuildRaiseOrderDialog
          t={t}
          connectionId={connectionId}
          services={serviceCodes}
          units={units}
          dateFormat={dateFormat}
          client={client}
          onClose={() => setDialog(null)}
          onRaised={(orderNo) => {
            setDialog(null);
            toast(
              orderNo === null
                ? t("customers.build.raise.doneNoNumber", { defaultValue: "Work order raised." })
                : t("customers.build.raise.done", {
                    order: orderNo,
                    defaultValue: `Work order ${orderNo} raised.`,
                  }),
            );
            void detailQuery.refetch();
            void recordQuery.refetch();
            // The Work tab's table is the SHARED premises read; re-read it too,
            // or the tiles count the new order and the table does not show it
            // (seen in the browser walk, 2026-10-02).
            if (premisesId !== null) {
              void queryClient.invalidateQueries({
                queryKey: scopedOrdersQueryKey("premises", premisesId),
              });
            }
          }}
        />
      )}
      {dialog === "repark" && (
        <BuildRepakDialog
          t={t}
          park={park}
          client={client}
          onClose={() => setDialog(null)}
          onDone={() => void parkQuery.refetch()}
        />
      )}
    </div>
  );
}

/** Which tab body is on screen. Split out so the page's own body stays
 *  readable and so a test can address ONE tab without the header (rule 43). */
export function BuildTabBody(
  props: BuildTabProps & {
    active: string;
    /** CR-162-BRC10 — the Units tab's buttons open the page's ONE Approve dialog. */
    onActivate?: (ids: string[]) => void;
  },
) {
  const { active, onActivate, ...rest } = props;
  return (
    <div data-build-tab={active}>
      {active === "overview" && <BuildOverviewTab {...rest} />}
      {active === "units" && <BuildUnitsTab {...rest} onActivate={onActivate} />}
      {active === "work" && <BuildWorkTab {...rest} />}
      {active === "todo" && <BuildTodoTab {...rest} />}
      {active === "charges" && <BuildChargesTab {...rest} />}
      {active === "documents" && <BuildDocumentsTab {...rest} />}
      {active === "messages" && <BuildMessagesTab {...rest} />}
      {active === "audit" && <BuildAuditTab {...rest} />}
    </div>
  );
}

export default BuildDetailPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-150-BRC09 tasks 4–14 · the ten PNGs of
//   `05-prototype/new-connect-detail-2026-09-28/`, read as IMAGES (B14 rule 42)
//   · `00-all-screens.html` read for its NOTES only, never for layout
// generated: 2026-09-28 by the DETAIL PAGE lane
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//   H=deferred(PO)
// exceptions:
//   (1) **THE DOCUMENTS AND MESSAGES TABS CARRY NO HEADER PRIMARY.**
//       `05-documents.png` draws `Add document` in the header AND in the
//       panel, which is two controls for one act; the shared
//       `DocumentCapture` owns its own submit, so the header slot is left
//       empty (`PageHeaderTab`'s own note allows a tab with no action).
//       `06-messages.png` draws `Resend` in the header, and its own note says
//       *"Opened from the Resend link on a row, not from the header: it acts
//       on one message"* — a header control with no row selected would have
//       nothing to act on. Both REPORTED.
//   (2) **THE ROUTE AND THE SCREEN-ID ROW ARE NOT IN THIS COMMIT.** They are
//       the reversal lane's, together with `G93`'s amendment. This file
//       therefore mounts nowhere yet, and its tests mount it under the real
//       path pattern `/:tenant/connections/:connectionId` themselves.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
