// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-009 (S55 reassign + final read) · US-AST-007 (S53 log
//           repair / inspection / test) — both converted to FULL-PAGE screens
//           Screens: S55 / AST-06 (`/assets/:assetId/reassign`) ·
//           S53 / AST-07 (`/assets/:assetId/maintenance/new`)
// Change:   CR-028 AST-W4 T2 (B16 §5.2 AS AMENDED — PO 2026-08-22: "as per
//           r10 - it is not modal"). The S53/S55 modals retire; every entry
//           point (registry row actions, detail header, panels) NAVIGATES
//           here. AST-06 additionally closes the B16-noted design gap: r10
//           draws only a "Record the final read" checkbox, and a checkbox
//           cannot CAPTURE a read — the form adds the value + date inputs,
//           wired to the reassign service's existing contract
//           (final_read_value + the W4 final_read_date).
// Rules:    BR-AST-017/022 (append-only assignments; the final read and the
//           move are ONE transaction — the server REFUSES the whole move when
//           it cannot capture) · BR-AST-018 (maintenance append-only) ·
//           BR-AST-020/031 (legal transitions only, from the behavior class) ·
//           BR-AST-037/038 (parent/child moves; Billing Clerk may log
//           repairs) · §10-D3 (estimated cost is CAPTURED, never posted — the
//           r10 "Post the cost to O&M 5300" checkbox is OMITTED) · §10-D7
//           (work-order controls render DISABLED with the two-word reason
//           "Work R5" — never hidden, never built) · BR-SHL-025 (disabled
//           with its reason) · BR-SHL-033/034 (pickers + the one formatter)
// ───────────────────────────────────────────────────────
// AST-06 · AST-07 — the two single-form lifecycle flows, as r10 draws them:
// full pages under the one PageHeader, never dialogs. The pure law (legal
// transitions, warning keys, schemas) stays in AssetLifecycleModals.tsx —
// the modals left that file, the law did not.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getAsset,
  getAssetAssignments,
  getLookupEntries,
  getUnits,
  logAssetMaintenance,
  reassignAsset,
} from "@/api/endpoints";
import type { AssetDetail, MaintenanceKind, ServerWarning } from "@/api/endpoints";
import {
  CheckboxField,
  DatePickerField,
  SearchSelectField,
  SegmentedField,
  SelectField,
  TextField,
  collectFormErrors,
  envelopeErrors,
} from "@/components/FormModal";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
// `DateCell` itself left with the context line — `assetsShared` renders the
// installed date now, and this file's remaining date work is arithmetic.
import { formatDate, todayInZone } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied, WorkingButton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { toEnvelope } from "@/features/metering/PremisesListPage";
import {
  CELL_FULL,
  DASHBOARD_ROUTE,
  PREMISES_PERMISSION,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  MAINTENANCE_KIND_VALUES,
  assetStagesQueryKey,
  assetTechPickerKey,
  assetUnitPickerKey,
  legalTargets,
  maintenanceSchema,
  reassignSchema,
  reassignWarningKey,
  stageOptionsFrom,
  unitPickerOptions,
} from "./AssetLifecycleModals";
import { listCrewDirectory } from "@/features/work/workEndpoints";

import { raiseWorkOrderPath } from "./RaiseWorkOrderPage";
// MOUNTED, NEVER COPIED (hard-won law 2). The strip is screen 08's and stays
// screen 08's; this file asks for it by name.
import { AttentionStrip, raiseWorkRefusal } from "./AssetDetailPage";
import {
  ASSETS_ROUTE,
  AssetContextLine,
  AssetStatusCell,
  assetDetailPath,
  isMeasuringCategory,
  repairActionKey,
  useTranslator,
} from "./assetsShared";

// ── The work-order pre-tick — LIVE since CR-070 wave M (US-WRK-038) ─────────

/**
 * The "raise a work order" pre-tick on the four asset flows.
 *
 * ⚠ **IT WAS DISABLED WITH THE TWO WORDS *Work R5* UNTIL 2026-09-05**, because
 * the Work module did not exist and `OQ-249`'s Work half was open. Both are now
 * closed: `BR-WRK-056` gives the door an address and wave M builds it. The
 * control is live, the reason string is gone, and `assets.flow.workR5` is
 * DELETED from all eleven catalogues — a refusal that outlives its reason is
 * hard-won law 2's mirror clause, which cost the customer portal five of eight
 * working doors on the very morning this shipped (`DEF-CWP-3925`).
 *
 * ⚠ **TICKING IT DOES NOT RAISE ANYTHING BY ITSELF, AND THAT IS DELIBERATE.**
 * The host flow saves FIRST and only then opens `Work-028` with the asset
 * already chosen. A checkbox that raised a job as a side effect of a move would
 * raise one even when the move was refused — and `BR-AST-022` refuses a move
 * whose final read cannot be captured, which is not a rare path.
 */
export function RaiseWorkOrderCheckbox(props: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-md" data-raise-work="">
      <input
        type="checkbox"
        checked={props.checked}
        onChange={(event) => props.onChange(event.target.checked)}
      />
      <span>{props.label}</span>
    </label>
  );
}

// ── The shared full-page shell (load → header → form) ──────────────────────

/**
 * The flow kicker — `METER · AMI · REASSIGN`, exactly as every redrawn figure
 * of blueprint section 05 draws it.
 *
 * Screen 08's kicker is `type · asset-no · meter-type`; on a flow the ASSET
 * NUMBER is the title, so it leaves the kicker and the FLOW takes its place.
 * Derived from the payload, never typed out (the skill's §12), so an asset kind
 * that has no meter type simply contributes no leg.
 */
export function assetFlowKicker(asset: AssetDetail, flow: string): string {
  return [asset.type_name, asset.meter_type_name, flow]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
}

// ── The context line — *"118 Bayou Bend Dr · Unit 1 · ACC-20194 Ruth Alvarez
// · Water · Installed Jan 2026"* (figure 31, p88) ──────────────────────────
//
// ⚠ **IT LIVED HERE AND IN `AssetDetailPage` AT ONCE UNTIL 2026-09-13, AND
// THE TWO HAD ALREADY DRIFTED.** The version of this comment that stood here
// said so and named the fix — *"the follow-up is to move ONE of them into
// `assetsShared.tsx` and have both screens mount it … until that happens, a
// change to either must be made to both, and this comment is the only thing
// saying so."* That is hard-won law 1: a comment asking to be obeyed is not a
// guarantee that it will be. Four differences had accumulated, one of which
// blanked the detail screen on a payload with no `billing_chain` while the
// flow screens rendered it fine.
//
// The one implementation is `AssetContextLine` in `assetsShared.tsx`; its
// docstring carries the reasoning, the drawn order and the inventory rule.
// **Both figure 10 and figure 31 draw the same line**, which is what makes a
// single implementation correct rather than merely economical.

export function AssetFlowShell(props: {
  client: ApiClient;
  /**
   * A plain string, or — since `AST-B-12` — a function of the loaded asset,
   * exactly as `title` already was. AST-09's drawn kicker is the section AND
   * the kind ("ASSETS · METER"), which cannot be built before the asset has
   * arrived; the two older callers pass a string and are unchanged.
   */
  kicker: string | ((asset: AssetDetail) => string);
  /** Defaults to the ASSET NUMBER, which is what all six redrawn figures draw
   *  in the title slot (the flow's own name lives in the kicker). */
  title?: (asset: AssetDetail) => string;
  /** The tenant's zone and date format, for the attention strip's date. */
  regional?: RegionalProps;
  /**
   * `false` suppresses the attention strip ONLY. Reassign's confirm panel is
   * the one figure that draws the header WITHOUT it (fig 32), and its caption
   * says why: at that point the person has decided, and the one thing on screen
   * should be what they are about to commit.
   */
  attention?: boolean;
  children: (asset: AssetDetail) => ReactNode;
}) {
  const t = useTranslator();
  const { t: translateRaw } = useTranslation();
  const translate: Translator = (key, params) => translateRaw(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const assetId = params.assetId ?? "";
  const regional = useRegional(props.regional ?? {});

  const cell = useAccessCell(PREMISES_PERMISSION, props.client);
  const assetQuery = useQuery({
    queryKey: ["assets", "detail", assetId],
    queryFn: () => getAsset(assetId, props.client),
    enabled: assetId !== "",
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("assets.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (assetQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (assetQuery.data === undefined) {
    if (isPermissionDenied(assetQuery.error)) {
      return (
        <PermissionDenied
          helper={t("assets.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    return (
      <FailedWithRetry
        title={t("assets.detail.failedTitle")}
        reason={apiErrorText(assetQuery.error, t)}
        onRetry={() => void assetQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(ASSETS_ROUTE))}
      />
    );
  }

  const asset = assetQuery.data;
  // Read exactly as `AssetDetailPage` reads it, so the strip's own door cannot
  // refuse for one reason on the detail page and another here.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("assets.rbac.readOnly");
  return (
    <div className="px-4 pt-6 pb-8">
      <div className="mb-4 [&_h1]:m-0 [&_h1]:text-h2">
        <PageHeader
          backTo={{
            to: tenantPath(assetDetailPath(asset.id)),
            label: t("assets.flow.backToAsset"),
          }}
          kicker={typeof props.kicker === "string" ? props.kicker : props.kicker(asset)}
          title={props.title === undefined ? asset.asset_no : props.title(asset)}
          // ── The five-slot header, screens 22–26 ────────────────────────────
          // Section 05's single largest gap and it was SIX gaps that were one:
          // `PageHeader` already had both slots, `AssetStatusCell` was already
          // exported and the strip was already right — only the mounting was
          // missing. Nothing here is a new design.
          status={<AssetStatusCell row={asset} t={translate} />}
          rollup={
            <span className="block text-base">
              {props.attention !== false && (
                <AttentionStrip
                  asset={asset}
                  regional={props.regional ?? {}}
                  t={translate}
                  raiseReason={raiseWorkRefusal(asset, writeBlockedReason, translate)}
                />
              )}
              <AssetContextLine asset={asset} t={translate} regional={regional} />
            </span>
          }
        />
      </div>
      <div className="flex max-w-3xl flex-col gap-5">{props.children(asset)}</div>
    </div>
  );
}

// ── AST-06 — Reassign (full page) ──────────────────────────────────────────

export interface AssetFlowPageProps extends RegionalProps {
  client?: ApiClient;
  today?: string;
}

export function AssetReassignPage(props: AssetFlowPageProps) {
  const client = props.client ?? api;
  const t = useTranslator();
  /**
   * **THE CONFIRM STEP — figure 32, and the whole of screen 22's first gap.**
   *
   * The step lives HERE rather than inside the form because the header changes
   * with it: the kicker gains `· CONFIRM` and the attention strip goes away,
   * which is the one figure in the section that draws the five-slot header
   * without it.
   *
   * ⚠ **IT IS NOT URL STATE, AND THAT IS DELIBERATE.** A retire is a wizard and
   * its step is linkable because a half-filled retire is worth coming back to;
   * a reassign confirm is a re-read of what is already typed into a form this
   * page does not persist, so an address for it would restore an EMPTY summary
   * on a refresh — a screen stating facts about a move nobody entered.
   */
  const [confirming, setConfirming] = useState(false);
  return (
    <AssetFlowShell
      client={client}
      regional={props}
      // Figure 31: kicker `METER · AMI · REASSIGN`, title `W-5001`. The flow's
      // own name moves into the kicker and the ASSET NUMBER becomes the title,
      // which is what screen 08 does and what all six redrawn figures draw.
      kicker={(asset) =>
        assetFlowKicker(
          asset,
          confirming
            ? `${t("assets.reassign.kicker")} · ${t("assets.reassign.confirmStep")}`
            : t("assets.reassign.kicker"),
        )
      }
      attention={!confirming}
    >
      {(asset) => (
        <ReassignForm
          asset={asset}
          client={client}
          pageProps={props}
          confirming={confirming}
          onConfirming={setConfirming}
        />
      )}
    </AssetFlowShell>
  );
}

function ReassignForm(props: {
  asset: AssetDetail;
  client: ApiClient;
  pageProps: AssetFlowPageProps;
  confirming: boolean;
  onConfirming: (confirming: boolean) => void;
}) {
  const { asset, client } = props;
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const { dateFormat, timeZone } = useRegional(props.pageProps);
  /**
   * ⚠ **`props.today` IS PASSED BY TESTS AND BY NOTHING ELSE** — `App.tsx`
   * mounts this screen with no props at all, so before 2026-09-12 `today` was
   * `""`, `prefill` was `undefined`, and the field rendered EMPTY in the
   * shipped product against `BR-PAY-033`'s *"the UI ALWAYS proposes a
   * pre-filled default date"* (`DEF-MET-4991`, measured in Chromium at 1440 and
   * 1280). It also silently voided this lane's `max` bound, which is the sharp
   * end of it: a green unit test and a browser that disagreed, because the test
   * supplied the prop the router does not. The tenant's own zone, never UTC —
   * a `max` of *not in the future* must not refuse a clerk their own today.
   */
  const today = props.pageProps.today ?? todayInZone(timeZone);
  const measuring = isMeasuringCategory(asset.tab);
  const hasChildren = asset.sub_assets.length > 0;

  // DEF-593 (CR-028 debt sweep): the unit detail's "+ Assign from inventory"
  // picker lands here with `?unit=<id>` so THAT unit arrives preselected —
  // a prefill of the same picker below, never a hidden value: the operator
  // still sees and can change the destination before saving.
  const [searchParams] = useSearchParams();
  const presetUnitId = searchParams.get("unit") ?? "";

  const [values, setValues] = useState({
    destination: "unit" as "unit" | "inventory",
    unit_id: presetUnitId,
    effective_date: "",
    record_final_read: true, // BR-AST-022: default ON
    final_read_value: "",
    final_read_date: "",
    move_children: true, // BR-AST-037: default YES
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  /* The work-order pre-tick. FALSE by default: raising a job is a choice a
     clerk makes, and a default-on checkbox would put a van on the road for
     every routine move. */
  const [raiseWork, setRaiseWork] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const unitsQuery = useQuery({
    queryKey: assetUnitPickerKey,
    queryFn: () => getUnits({ per: 500 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  /**
   * **THE EARLIEST DATE THIS MOVE MAY TAKE, READ FROM THE ASSIGNMENT IT
   * CLOSES** (`DEF-MET-4974`, B14 rule 7).
   *
   * ⚠ **THE BOUND IS THE SERVER'S OWN AND IS NOT INVENTED HERE.**
   * `_reassign_inner` refuses `effective < current.from_date` with
   * `assets.effective_before_from_date` (`BR-AST-017` — an earlier effective
   * date would overlap the history). The asset DETAIL payload does not carry
   * that date, so it is read through the endpoint that already serves it;
   * `AnyTenantRole`, so a Billing Clerk reads it too.
   *
   * ⚠ **AND `install_date` WOULD HAVE BEEN THE WRONG BOUND**, which is worth
   * writing down because it is on the detail payload and therefore the easy
   * one to reach for. It is neither the same date nor a safe approximation of
   * it: an assignment can start well after installation, so an `install_date`
   * bound would accept dates the server refuses. **A wrong bound is worse than
   * no bound** — it promises the server will accept what it will not.
   *
   * Undefined on failure, on an asset with no current assignment, and while
   * loading — all three leave the field exactly as unbounded as it was.
   */
  const assignmentsQuery = useQuery({
    queryKey: ["assets", asset.id, "assignments"],
    queryFn: () => getAssetAssignments(asset.id, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // `AST-B-19` — `.rows` off the page. The CURRENT assignment is the newest and
  // the server serves this history newest-first, so it is on page one; a
  // reassignment floor read off a later page would be a different bug, and this
  // is stated because the `.find` cannot say which page it searched.
  const effectiveFloor =
    (assignmentsQuery.data?.rows ?? []).find((row) => row.current)?.from_date ?? undefined;

  const move = useMutation({
    mutationFn: () =>
      reassignAsset(
        asset.id,
        {
          ...(values.destination === "inventory"
            ? { to_inventory: true }
            : { unit_id: values.unit_id }),
          effective_date: values.effective_date === "" ? undefined : values.effective_date,
          record_final_read: measuring ? values.record_final_read : false,
          final_read_value: values.final_read_value === "" ? undefined : values.final_read_value,
          final_read_date: values.final_read_date === "" ? undefined : values.final_read_date,
          move_children: hasChildren ? values.move_children : undefined,
        },
        client,
      ),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      fireToast(t("assets.toast.reassigned", { asset: asset.asset_no }));
      showWarnings(result.warnings, fireToast, translate);
      // THE MOVE SAVED FIRST. Only now does the pre-tick open the door — a
      // checkbox that raised a job as a side effect would raise one even when
      // `BR-AST-022` refused the move for a missing final read.
      navigate(
        tenantPath(raiseWork ? raiseWorkOrderPath(asset.id) : assetDetailPath(asset.id)),
      );
    },
    onError: (error: unknown) => {
      // BR-AST-022: when the final read cannot be captured the SERVER refuses
      // the whole move (422 BIZ-COMPLETENESS). The envelope renders under the
      // form; the asset did not move, and this screen does not pretend
      // otherwise.
      const mapped = envelopeErrors(toEnvelope(error), translate);
      setFieldErrors(mapped.fields);
      setRefusal(mapped.message);
    },
  });

  /** Panel 1's `Continue` — it VALIDATES and then shows the summary. A confirm
   *  step that could be reached over an invalid form would state consequences
   *  for a move the server was always going to refuse. */
  function toConfirm(): void {
    const validation = collectFormErrors(reassignSchema(translate), values);
    setFieldErrors(validation.errors);
    setRefusal(null);
    if (validation.count > 0) {
      return;
    }
    props.onConfirming(true);
  }

  function submit(): void {
    const validation = collectFormErrors(reassignSchema(translate), values);
    setFieldErrors(validation.errors);
    setRefusal(null);
    if (validation.count > 0) {
      // Back to the form: an error the confirm panel cannot show is an error
      // nobody can fix from where they are standing.
      props.onConfirming(false);
      return;
    }
    move.mutate();
  }

  if (props.confirming) {
    const destination =
      values.destination === "inventory"
        ? null
        : unitPickerOptions(unitsQuery.data?.results).find(
            (option) => option.value === values.unit_id,
          )?.label ?? null;
    return (
      <>
        {/* Figure 32's one sentence: WHAT is about to happen, in a line. */}
        <p className="m-0 text-base" data-reassign-confirm="">
          {t(
            values.destination === "inventory"
              ? "assets.reassign.confirmLedeInventory"
              : "assets.reassign.confirmLedeUnit",
            {
              asset: asset.asset_no,
              from: asset.assigned_to ?? t("assets.inventoryUnassigned"),
              // BR-SHL-034 — ONE formatter, even inside a sentence. A raw ISO
              // date interpolated here is exactly the drift `DateCell` exists
              // to prevent; the tenant asked for MM/DD/YYYY and gets it.
              date: formatDate(values.effective_date, timeZone, dateFormat),
              to: destination ?? "",
            },
          )}
        </p>
        {/* B14 rule 11 — the consequence preview, in the KIT's box rather than
            in two 11px grey captions beside a form nobody has filled in yet.
            Both sentences already existed in the catalogue; what was missing
            was showing them AFTER the person had decided. */}
        <ConsequenceBox
          tone="check"
          title={t("assets.reassign.confirmTitle")}
          body={
            <>
              {t("assets.reassign.oneTransaction")}{" "}
              <strong>{t("assets.reassign.confirmRefusal")}</strong>
            </>
          }
          data-consequence="assets-reassign-confirm"
        />
        <dl className="m-0 border-t border-divider text-base" data-reassign-facts="">
          <ConfirmFact label={t("assets.reassign.whatMoves")}>
            {hasChildren && values.move_children
              ? t("assets.reassign.movesWithSubs", {
                  asset: asset.asset_no,
                  // `subs` and NOT `count`: i18next reads `count` as a plural
                  // selector and would go looking for `…_one` / `…_other` keys
                  // this flat catalogue does not carry.
                  subs: asset.sub_assets.length,
                })
              : asset.asset_no}
          </ConfirmFact>
          <ConfirmFact label={t("assets.reassign.whatStays")}>
            {t("assets.reassign.readsStay")}
          </ConfirmFact>
          <ConfirmFact label={t("assets.reassign.alsoRaised")}>
            {raiseWork
              ? t("assets.reassign.raisedWorkOrder")
              : t("assets.reassign.raisedNothing")}
          </ConfirmFact>
        </dl>
        {refusal !== null && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
        <div className="mt-2 flex gap-2 border-t-2 border-divider pt-4">
          <Button variant="ghost" onClick={() => props.onConfirming(false)}>
            {t("wizard.back")}
          </Button>
          <WorkingButton working={move.isPending} onClick={submit}>
            {t("assets.reassign.save")}
          </WorkingButton>
        </div>
      </>
    );
  }

  return (
    <>
      {/* r10 AST-06's context strip: where it stands NOW. */}
      <Note>
        {t("assets.reassign.currently", {
          location: asset.assigned_to ?? t("assets.inventoryUnassigned"),
        })}
      </Note>
      <SegmentedField
        id="destination"
        label={t("assets.reassign.moveTo")}
        value={values.destination}
        options={[
          { value: "unit", label: t("assets.reassign.toUnit") },
          { value: "inventory", label: t("assets.reassign.toInventory") },
        ]}
        onChange={(value) =>
          setValues({ ...values, destination: value === "inventory" ? "inventory" : "unit" })
        }
      />
      {values.destination === "unit" && (
        <SearchSelectField
          id="unit_id"
          label={t("assets.reassign.unit")}
          required
          value={values.unit_id}
          options={unitPickerOptions(unitsQuery.data?.results)}
          placeholder={t("assets.reassign.unitPlaceholder")}
          onChange={(value) => setValues({ ...values, unit_id: value })}
          help={unitsQuery.isError ? t("assets.reassign.unitListUnavailable") : undefined}
          error={fieldErrors.unit_id}
        />
      )}
      <DatePickerField
        id="effective_date"
        label={t("assets.reassign.effectiveDate")}
        value={values.effective_date}
        prefill={today === "" ? undefined : today}
        dateFormat={dateFormat}
        // B14 rule 7 / `DEF-MET-4974` — see `effectiveFloor` above for why this
        // date and not the install date. NO `max`: a move may be dated forward
        // (a planned swap), and the server accepts one.
        min={effectiveFloor}
        onChange={(value) => setValues({ ...values, effective_date: value })}
        // ⚠ **THE SENTENCE TRAVELS WITH THE BOUND.** A calendar that greys out
        // dates with no words is `DEF-MET-4973`'s greyed-out submit in another
        // control: a refusal a person can see and cannot account for. The
        // second sentence renders only where the floor exists, so it can never
        // state a bound that is not enforced.
        help={
          effectiveFloor === undefined
            ? t("assets.reassign.effectiveDateHelp")
            : `${t("assets.reassign.effectiveDateHelp")} ${t("assets.reassign.effectiveFloorHelp")}`
        }
        error={fieldErrors.effective_date}
      />
      {/* BR-AST-022: ON by default for a measuring asset. The B16-noted gap
          closed: the checkbox alone cannot CAPTURE a read, so checking it
          reveals the value + date the capture needs. */}
      {measuring ? (
        <>
          <CheckboxField
            id="record_final_read"
            label={t("assets.reassign.recordFinalRead")}
            checked={values.record_final_read}
            onChange={(checked) => setValues({ ...values, record_final_read: checked })}
          />
          {values.record_final_read && (
            <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
              <TextField
                id="final_read_value"
                label={t("assets.reassign.finalReadValue", {
                  unit: asset.unit ?? t("assets.unitUnknown"),
                })}
                numeric
                value={values.final_read_value}
                onChange={(value) => setValues({ ...values, final_read_value: value })}
                // CLAUDE.md #3: the quantity never travels without its unit —
                // the asset's own stored UoM labels the field.
                help={t("assets.reassign.finalReadHelp")}
                error={fieldErrors.final_read_value}
              />
              {/* ⚠ **DELIBERATELY UNBOUNDED, AND THAT IS A DECISION RATHER
                  THAN AN OMISSION** (`DEF-MET-4974`). No rule, no help
                  sentence and no server refusal states a bound for a final
                  read date: `_reassign_inner` takes it as
                  `_as_date(...) or effective` and metering's
                  `capture_final_read` refuses only a date it cannot parse.
                  **`max={today}` is the tempting one and it is wrong**: left
                  BLANK this field already resolves to the EFFECTIVE date,
                  which may lawfully be in the future for a planned move — so
                  capping it at today would make the field stricter than the
                  path its own blank value takes. Inventing a bound here would
                  be inventing a rule (prime directive), so the absence is
                  stated instead. */}
              <DatePickerField
                id="final_read_date"
                label={t("assets.reassign.finalReadDate")}
                value={values.final_read_date}
                dateFormat={dateFormat}
                onChange={(value) => setValues({ ...values, final_read_date: value })}
                help={t("assets.reassign.finalReadDateHelp")}
                error={fieldErrors.final_read_date}
              />
            </div>
          )}
        </>
      ) : (
        <Note>{t("assets.reassign.nonMeasuring")}</Note>
      )}
      {/* BR-AST-037: moving a parent prompts for its children, default YES. */}
      {hasChildren && (
        <CheckboxField
          id="move_children"
          label={t("assets.reassign.moveChildren")}
          checked={values.move_children}
          onChange={(checked) => setValues({ ...values, move_children: checked })}
        />
      )}
      {asset.parent_asset_no !== null && (
        <Note>
          {t("assets.reassign.independentSubMeterNotice", { parent: asset.parent_asset_no })}
        </Note>
      )}
      {/* r10's "Raise a field work order for the physical move" — LIVE since
          wave M. Ticked, the move saves first and then opens Work-028. */}
      <RaiseWorkOrderCheckbox
        label={t("assets.reassign.workOrder")}
        checked={raiseWork}
        onChange={setRaiseWork}
      />
      {/* ⚠ **THE TWO CONSEQUENCE SENTENCES ARE NOT HERE ANY MORE — THEY ARE ON
          THE CONFIRM PANEL.** They rendered as two 11px grey `<Note>` captions
          beside the form, where a person reads them BEFORE they have decided
          anything; figure 32's caption is the whole finding in one line:
          *"THIS SHOWS IT AFTER THEY HAVE, AND BEFORE IT COMMITS."* Nothing was
          deleted — `assets.reassign.readsStay` and `.oneTransaction` both still
          render, one step later and in the kit's consequence box. */}
      {refusal !== null && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      <div className="mt-2 flex gap-2 border-t-2 border-divider pt-4">
        <Button variant="ghost" onClick={() => navigate(tenantPath(assetDetailPath(asset.id)))}>
          {t("assets.flow.cancel")}
        </Button>
        {/* Figure 31 marks this NEW: the form no longer commits.
            B14 rule 38 — footer CONSTRUCTION is the kit's, and the kit's
            `Continue` is the PRIMARY tier (`WizardFrame` renders it through
            `WorkingButton`). `Button`'s own default is `secondary`, so leaving
            the variant off drew a step-advance that looked like a `Cancel`
            beside it — measured in Chromium at 1280 before this line. */}
        <WorkingButton working={false} onClick={toConfirm}>
          {t("wizard.continue")}
        </WorkingButton>
      </div>
    </>
  );
}

/** One `What moves` / `What stays` / `Also raised` row of figure 32's fact
 *  list. A `<dl>` rather than a table: three labelled facts are a description
 *  list, and the semantic structure comes before the styling (the skill's §3). */
function ConfirmFact(props: { label: string; children: ReactNode }) {
  return (
    // A `<div>` wrapping one `dt`/`dd` pair is valid inside a `<dl>` and is
    // what keeps the row together without an arbitrary grid template.
    <div className="flex gap-4 border-b border-divider py-2">
      <dt className="w-36 shrink-0 font-semibold">{props.label}</dt>
      <dd className="m-0">{props.children}</dd>
    </div>
  );
}

export function showWarnings(
  warnings: readonly ServerWarning[],
  fireToast: (message: string) => void,
  t: Translator,
): void {
  if (warnings.length > 0) {
    fireToast(warnings.map((warning) => t(reassignWarningKey(warning), warning)).join(" "));
  }
}

// ── AST-07 — Log repair / test (full page) ─────────────────────────────────

export function AssetLogMaintenancePage(props: AssetFlowPageProps) {
  const client = props.client ?? api;
  const t = useTranslator();
  return (
    <AssetFlowShell
      client={client}
      regional={props}
      // Figure 34: kicker `METER · AMI · LOG REPAIR / MAINTENANCE`, title
      // `W-5001`. B16 §5.1b (A) / W2's `repairActionKey`: a device with a test
      // cadence says "Log test", exactly as its action is labelled — the
      // relabel moves with the flow name into the kicker.
      kicker={(asset) =>
        assetFlowKicker(
          asset,
          t(
            repairActionKey(asset) === "assets.action.logTest"
              ? "assets.maintenance.kickerTest"
              : "assets.maintenance.kicker",
          ),
        )
      }
    >
      {(asset) => <MaintenanceForm asset={asset} client={client} pageProps={props} />}
    </AssetFlowShell>
  );
}

function MaintenanceForm(props: {
  asset: AssetDetail;
  client: ApiClient;
  pageProps: AssetFlowPageProps;
}) {
  const { asset, client } = props;
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const { dateFormat, timeZone } = useRegional(props.pageProps);
  /**
   * ⚠ **`props.today` IS PASSED BY TESTS AND BY NOTHING ELSE** — `App.tsx`
   * mounts this screen with no props at all, so before 2026-09-12 `today` was
   * `""`, `prefill` was `undefined`, and the field rendered EMPTY in the
   * shipped product against `BR-PAY-033`'s *"the UI ALWAYS proposes a
   * pre-filled default date"* (`DEF-MET-4991`, measured in Chromium at 1440 and
   * 1280). It also silently voided this lane's `max` bound, which is the sharp
   * end of it: a green unit test and a browser that disagreed, because the test
   * supplied the prop the router does not. The tenant's own zone, never UTC —
   * a `max` of *not in the future* must not refuse a clerk their own today.
   */
  const today = props.pageProps.today ?? todayInZone(timeZone);
  const testingDevice = repairActionKey(asset) === "assets.action.logTest";

  const [values, setValues] = useState({
    kind: (testingDevice ? "test" : "repair") as MaintenanceKind,
    date: "",
    detail: "",
    status: asset.status, // "no change" is the default choice
    tech_user_id: "",
    cost: "",
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  /* The work-order pre-tick. FALSE by default: raising a job is a choice a
     clerk makes, and a default-on checkbox would put a van on the road for
     every routine move. */
  const [raiseWork, setRaiseWork] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const stagesQuery = useQuery({
    queryKey: assetStagesQueryKey,
    queryFn: () => getLookupEntries("asset_statuses", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  /**
   * **THE CREW LIST — `BR-AST-533`, PO 2026-09-12: *"a) Let a clerk read the
   * crew list (name + email only)"*.**
   *
   * ⚠ **THIS READ USED TO BE `GET /users`, WHICH IS `SystemAdminOnly` — SO THE
   * ONE ROLE THIS SCREEN EXISTS FOR WAS THE ONE ROLE IT COULD NOT SERVE**
   * (`DEF-MET-4977`). `BR-AST-038` is CONFIRMED and lets a Billing Clerk log a
   * repair; the service agrees (`@require_role(SYSTEM_ADMIN, BILLING_CLERK)`).
   * What the screen offered that role instead was a bare text box whose VALUE
   * is a uuid — B14 rule 31 (*"no Databse ID on screen - that is a rule"*) —
   * and an impossible task besides, because no screen in this product shows a
   * clerk a technician's uuid to copy.
   *
   * ⚠ **`GET /users` IS NOT WIDENED AND MUST NOT BE.** Measured with a real
   * Billing Clerk session on `pine-hill`, 2026-09-12: `GET /users` → **403
   * `BR-IDN-009`**, `GET /work/crew-directory` → **200 · 7 rows**. A backend
   * test holds both halves, because the half that goes green by doing nothing
   * is the half that quietly stops being true.
   *
   * `retry: false` is kept: one attempt, and the failure state below says what
   * actually happened rather than guessing at a cause.
   */
  const techQuery = useQuery({
    queryKey: assetTechPickerKey,
    queryFn: () => listCrewDirectory(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const stages = stageOptionsFrom(stagesQuery.data?.results);
  const targets = legalTargets(stages, asset.status);

  const log = useMutation({
    mutationFn: () =>
      logAssetMaintenance(
        asset.id,
        {
          kind: values.kind,
          detail: values.detail,
          date: values.date === "" ? undefined : values.date,
          // Sending the CURRENT stage is the explicit "no change" the server
          // accepts; it is not a transition and writes no status_changed row.
          status: values.status,
          tech_user_id: values.tech_user_id === "" ? null : values.tech_user_id,
          // §10-D3: CAPTURED (stored 4 dp, displayed 2), posted NOWHERE — the
          // r10 "Post the cost to O&M 5300" checkbox is deliberately absent.
          cost: values.cost === "" ? undefined : values.cost,
        },
        client,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      fireToast(t("assets.toast.maintenanceLogged", { asset: asset.asset_no }));
      navigate(
        tenantPath(raiseWork ? raiseWorkOrderPath(asset.id) : assetDetailPath(asset.id)),
      );
    },
    onError: (error: unknown) => {
      const mapped = envelopeErrors(toEnvelope(error), translate);
      setFieldErrors(mapped.fields);
      setRefusal(mapped.message);
    },
  });

  function submit(): void {
    const validation = collectFormErrors(maintenanceSchema(translate), values);
    setFieldErrors(validation.errors);
    setRefusal(null);
    if (validation.count > 0) {
      return;
    }
    log.mutate();
  }

  return (
    <>
      {/* BR-AST-018: kind repair | inspection | test — a `test` entry moves
          last_test_date, clears the BR-AST-007 chip and (W4 T5) rolls an
          explicit certification due by the asset's cadence. */}
      <SegmentedField
        id="kind"
        label={t("assets.maintenance.kind")}
        value={values.kind}
        options={MAINTENANCE_KIND_VALUES.map((kind) => ({
          value: kind,
          label: t(`assets.maintenance.kind.${kind}`),
        }))}
        onChange={(value) => setValues({ ...values, kind: value as MaintenanceKind })}
      />
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        <DatePickerField
          id="date"
          label={t("assets.maintenance.date")}
          value={values.date}
          prefill={today === "" ? undefined : today}
          dateFormat={dateFormat}
          // B14 rule 7 / `DEF-MET-4974`. ⚠ **THE HELP HAS SAID *"Cannot be in
          // the future."* SINCE THE SCREEN SHIPPED AND THE CONTROL DID NOT
          // ENFORCE IT** — measured `min: null, max: null` at 1280 and 1440. A
          // sentence promising what the control does not do reads as good copy
          // to every check this repository owns and as a lie to the clerk who
          // types tomorrow and is refused by the server instead.
          // The bound MIRRORS an existing server refusal rather than inventing
          // one: `services.py:1376` refuses `entry_date > tenant_today()` with
          // `assets.maintenance_date_future`. An empty tenant today leaves it
          // unbounded, which is exactly what it was before.
          max={today === "" ? undefined : today}
          onChange={(value) => setValues({ ...values, date: value })}
          help={t("assets.maintenance.dateHelp")}
          error={fieldErrors.date}
        />
        {/* BR-AST-020: only the LEGAL targets are offered; the server
            re-checks and its 409 is what governs. Figure 34 pairs this with
            the DATE, not with the cost. */}
        <SelectField
          id="status"
          label={t("assets.maintenance.setStatus")}
          value={values.status}
          options={targets.map((stage) => ({
            value: stage.code,
            label:
              stage.code === asset.status
                ? t("assets.maintenance.noChange", { status: stage.name })
                : stage.name,
          }))}
          onChange={(value) => setValues({ ...values, status: value })}
          help={
            stagesQuery.isError
              ? t("assets.maintenance.stagesUnavailable")
              : t("assets.maintenance.setStatusHelp")
          }
          error={fieldErrors.status}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
        {/* ⚠ **ONE CONTROL, ALWAYS — IT NEVER BECOMES A TEXT BOX**
            (`DEF-MET-4977`). Until 2026-09-12 a failed read swapped the picker
            for a `TextField` holding a uuid, which is B14 rule 31 broken and a
            task nobody could perform. A control that changes TYPE under failure
            teaches a person the product is two different products.

            ⚠ **AND THE OLD SENTENCE WAS FALSE ON EVERY FAILURE THAT WAS NOT A
            403.** The branch is `isSuccess` with `retry: false`, so a 500, a
            timeout or an offline browser degraded it exactly as a refusal did —
            and a System Admin, who has every right to the list, was told *"Your
            role can't list users"*, a statement about their own permissions
            that was simply untrue. The replacement sentence names what happened
            (the list did not load) rather than guessing why.

            `BR-SHL-025`, and `BR-AST-534` extending it from role to state:
            disabled WITH its reason, never hidden. The field is OPTIONAL, so a
            clerk can still record the repair — which is the whole reason
            disabling it is honest rather than obstructive. */}
        <SearchSelectField
          id="tech_user_id"
          label={t("assets.maintenance.tech")}
          value={values.tech_user_id}
          options={(techQuery.data?.results ?? []).map((member) => ({
            value: member.id,
            // The NAME is the label and the id is the VALUE — `BR-AST-533`:
            // "the id still travels on the wire as the chosen value; what the
            // rule forbids is a person reading or typing it."
            label: `${member.name} · ${member.email}`,
          }))}
          placeholder={t("assets.maintenance.techUnassigned")}
          disabled={!techQuery.isSuccess}
          // Figure 34 marks this helper NEW and caption 2 states it in full:
          // *"TECHNICIAN IS A PICKER ON EVERY ROLE"*. The failure sentence
          // still wins the slot when the crew list did not load, because a
          // reason beats a description of the happy path.
          help={
            techQuery.isSuccess
              ? t("assets.maintenance.techHelp")
              : t("assets.maintenance.techNoList")
          }
          onChange={(value) => setValues({ ...values, tech_user_id: value })}
        />
        {/* r10 AST-07's cost — feeds the W2-built `cost` column: captured at
            4 dp, displayed 2, and NO "post to O&M" checkbox exists here
            (§10-D3 — the PO omitted the posting sentence). Figure 34 pairs it
            with the TECHNICIAN and shortens the label to `Cost`. */}
        <TextField
          id="cost"
          label={t("assets.maintenance.cost")}
          numeric
          value={values.cost}
          onChange={(value) => setValues({ ...values, cost: value })}
          help={t("assets.maintenance.costHelp")}
          error={fieldErrors.cost}
        />
      </div>
      {/* Figure 34 moves this BELOW both paired rows. */}
      <TextField
        id="detail"
        label={t("assets.maintenance.detail")}
        required
        multiline
        value={values.detail}
        onChange={(value) => setValues({ ...values, detail: value })}
        error={fieldErrors.detail}
      />
      {/* BR-AST-018: this log is append-only, and the cost reaches no ledger
          account. Both figures draw ONE accent-ruled box carrying BOTH
          sentences; the product had one of them as an 11px grey caption and
          the other only as a field helper. B14 rule 11 + 36 — the kit's box. */}
      <ConsequenceBox
        tone="check"
        title={t("assets.maintenance.recordedNotPosted")}
        body={`${t("assets.maintenance.appendOnly")} ${t("assets.maintenance.costNotPosted")}`}
        data-consequence="assets-maintenance-recorded"
      />
      {/* §10-D7: r10's "Raise a work order from the repair template". */}
      <RaiseWorkOrderCheckbox
        label={t("assets.maintenance.workOrderRaise")}
        checked={raiseWork}
        onChange={setRaiseWork}
      />
      {refusal !== null && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      <div className="mt-2 flex gap-2 border-t-2 border-divider pt-4">
        <Button variant="ghost" onClick={() => navigate(tenantPath(assetDetailPath(asset.id)))}>
          {t("assets.flow.cancel")}
        </Button>
        <WorkingButton working={log.isPending} onClick={submit}>
          {t("assets.maintenance.save")}
        </WorkingButton>
      </div>
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-009@e1a4db0 + US-AST-007@e1a4db0 (EP-AST-03 lifecycle) · CR-028@B16 (04-docs/02-decisions/16-cr028-assets-design.md §5.2 AS AMENDED 2026-08-22 — no flow is a modal; §10 rulings D3/D7)
// generated: 2026-08-22 by the CR-028 AST-W4 lane (T2: AST-06 + AST-07 as full-page screens; the S53/S55 modals retired from AssetLifecycleModals.tsx the same commit) · AMENDED 2026-08-22 by the CR-028 debt-sweep lane (D2/DEF-593: AST-06 reads `?unit=<id>` and prefills the destination unit picker — the unit detail's "+ Assign from inventory" lands here)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AssetFlowPages.test.tsx — full-page-not-modal, "Work R5" verbatim, final-read value+date, D3 absence) · trace_lint✔
// exceptions: E3 RESOLVED 2026-08-22 (CR-028 debt sweep D5): the final-read capture SUCCEEDS — metering's capture_final_read is wired and the read commits with the move; the server still refuses honestly when the capture cannot happen (no value entered → VAL-REQUIRED `assets.final_read_value_required`; a standing head on the date, a validation error, or a metering-less deployment → the rendered refusal, asset unmoved — BR-AST-022 working) · E4 reassign warnings surface as a toast after navigation (the modal rendered them in-page; a full page navigates away on success, so the warning travels in the toast) · E4 r10's AST-06 draws ONE "Move to" select mixing Inventory among units; this page keeps the ratified segmented control + searchable unit picker (BR-SHL-033) — same choices, kit-conformant controls
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
