// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane PERFORMANCE — P5.5, bulk raise ACROSS
//           buildings: *"400 meters due for test → 400 jobs from a list. One
//           act, a per-order result."* (blueprint §02, capability B16). Many
//           jobs in ONE building is the raise form itself (ruling 19, P2.12);
//           what stays here is the list that crosses buildings. NAMED, NOT
//           DRAWN — built from the component kit under B14 rule 44 and put to
//           the PO as a photograph.
// Reads:    `GET /work/templates?f.raisable=1` (what may be raised, BR-WRK-011)
//           · `GET /assets?f.assigned=true&f.service=&f.test_due=&q=&page=&per=`
//           (the registry, paged in SQL — NFR-3).
// Writes:   `POST /work-orders/bulk-raise {asset_ids[]}` — one job per asset,
//           each walking asset → unit → premises for its OWN building (P2.20),
//           one savepoint per job (law 14), an answer per job (`BR-WRK-027`),
//           and a repeated key answers the first press (P2.12).
// Rules:    B14 rules 4, 17, 20 (every selection table is the kit
//           `TableArray`), 21, 31, 33, 43 (the raise's own pick table and
//           result are reused, never copied), 44 · NFR-3 · NFR-5.
// Tests:    src/features/work/performance/cr168Performance.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **NO `premises_id` TRAVELS, AND THAT IS WHAT MAKES IT ACROSS BUILDINGS.**
// The raise form sends the building it was opened on and the server refuses an
// asset standing anywhere else (`work.order.asset_not_on_premises`). Here each
// asset names its own building by the walk, so 400 meters on 300 streets are
// 400 jobs on 300 premises — proved on PostgreSQL in
// `06-backend/tests/test_cr168_perf_lane.py`.
//
// ⚠ **THE TICKS SURVIVE PAGING.** A page is 25 rows of a list of hundreds; the
// chosen set is kept by id with the words its result row needs, so the count
// beside the table is what will be raised, not what is on screen.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAssets } from "@/api/endpoints";
import type { AssetRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import type { PageSize } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";
import i18n from "@/i18n";

import { WORK_ORDERS_ROUTE } from "../WorkShell";
import { RaisePickTable } from "../raise/RaisePickTable";
import { RaiseResult } from "../raise/RaiseConfirm";
import type { RaiseJobLine } from "../raise/RaiseConfirm";
import { bulkRaise, listRaiseTemplates } from "../raise/raiseEndpoints";
import type { BulkRaiseOutcome } from "../raise/raiseEndpoints";
import { newIdempotencyKey, useDebouncedTerm } from "../raise/raiseModel";
import type { TemplateRow } from "../workEndpoints";

interface AcrossRow extends AssetRow {
  name: string;
}

interface Chosen {
  asset: string;
  where: string | null;
}

/** The one write's body. No `premises_id` — see the header. */
export function acrossBody(template: TemplateRow, assetIds: readonly string[], due: string, key: string) {
  return {
    template_id: template.id,
    ...(template.job_type !== null ? { type_id: template.job_type.id } : {}),
    type: template.job_type?.name ?? template.name,
    asset_ids: [...assetIds],
    priority_id: null,
    due_on: due === "" ? null : due,
    window_start: null,
    window_end: null,
    technician_notes: null,
    assignee: null,
    idempotency_key: key,
    custom_data: {},
    source: "dispatcher" as const,
  };
}

/** P5.5 — tick assets in any building, raise one job each. */
export function RaiseAcrossBoard(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional({});

  const [templateId, setTemplateId] = useState("");
  const [dueForTest, setDueForTest] = useState(true);
  const [search, setSearch] = useState("");
  const term = useDebouncedTerm(search);
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const [chosen, setChosen] = useState<ReadonlyMap<string, Chosen>>(new Map());
  const [due, setDue] = useState("");
  const [key, setKey] = useState(() => newIdempotencyKey());
  const [outcome, setOutcome] = useState<BulkRaiseOutcome | null>(null);
  const [lines, setLines] = useState<RaiseJobLine[]>([]);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const templates = useQuery({
    queryKey: ["work", "across", "templates"],
    queryFn: () => listRaiseTemplates({}, client),
  });
  const template = (templates.data?.results ?? []).find((row) => row.id === templateId) ?? null;
  const service = template?.service?.code;

  const assets = useQuery({
    queryKey: ["work", "across", "assets", service ?? "", dueForTest, term, page, per],
    queryFn: () =>
      getAssets(
        {
          q: term || undefined,
          page,
          per,
          filters: { assigned: "true", service, test_due: dueForTest ? "true" : undefined },
        },
        client,
      ),
    enabled: template !== null,
  });
  const rows: AcrossRow[] = useMemo(
    () => (assets.data?.results ?? []).map((row) => ({ ...row, name: row.asset_no })),
    [assets.data],
  );
  const chosenIds = useMemo(() => new Set(chosen.keys()), [chosen]);

  function onToggle(changed: readonly AcrossRow[], ticked: boolean) {
    setChosen((current) => {
      const next = new Map(current);
      for (const row of changed) {
        if (ticked) next.set(row.id, { asset: row.asset_no, where: row.assigned_address });
        else next.delete(row.id);
      }
      return next;
    });
  }

  function chooseTemplate(id: string) {
    setTemplateId(id);
    setChosen(new Map());
    setPage(1);
  }

  const blocked =
    template === null
      ? t("work.across.needTemplate")
      : chosen.size === 0
        ? t("work.across.needAssets")
        : undefined;

  async function raise() {
    if (template === null || chosen.size === 0 || busy) return;
    setBusy(true);
    setFailed(false);
    const ids = [...chosen.keys()];
    try {
      const result = await bulkRaise(acrossBody(template, ids, due, key), client);
      setLines(
        ids.map((id) => {
          const row = chosen.get(id);
          // The result's Unit column is the raise's own (image 18); an asset
          // row across buildings has no unit word to put there, so a dash.
          return { key: id, unit: "—", asset: row?.asset ?? null, where: row?.where ?? null, lastRead: null };
        }),
      );
      setOutcome(result);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  function raiseMore() {
    setOutcome(null);
    setLines([]);
    setChosen(new Map());
    setKey(newIdempotencyKey());
    setDue("");
  }

  if (outcome !== null) {
    return (
      <div data-raise-across="" data-raise-across-step="result">
        <RaiseResult
          outcome={outcome}
          lines={lines}
          reasonText={(reason) => (i18n.exists(reason) ? t(reason) : t("work.raise.refusedGeneric"))}
          onRaiseMore={raiseMore}
          onOpenOrders={() => navigate(tenantPath(WORK_ORDERS_ROUTE))}
          orderHref={(orderNo) => tenantPath(`${WORK_ORDERS_ROUTE}/${orderNo}`)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4" data-raise-across="" data-raise-across-step="pick">
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-base">
          <span className="font-semibold">{t("work.across.template")}</span>
          <select
            className="input w-80"
            value={templateId}
            onChange={(event) => chooseTemplate(event.target.value)}
            data-across-template=""
          >
            <option value="">{t("work.across.templatePick")}</option>
            {(templates.data?.results ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {row.service === null ? row.name : `${row.name} · ${row.service.name}`}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-base">
          <span className="font-semibold">{t("work.across.due")}</span>
          <input
            type="date"
            className="input w-48"
            value={due}
            onChange={(event) => setDue(event.target.value)}
            data-across-due=""
          />
        </label>
      </div>

      {template !== null && (
        <RaisePickTable<AcrossRow>
          title={t("work.across.assets")}
          collection="across-assets"
          rows={rows}
          total={assets.data?.count ?? 0}
          chosen={chosenIds}
          onToggle={onToggle}
          search={{
            label: t("work.raise.assetsSearchLabel"),
            placeholder: t("work.raise.assetsSearch"),
            value: search,
            onChange: (value) => {
              setSearch(value);
              setPage(1);
            },
          }}
          chips={
            <label className="inline-flex items-center gap-2 text-base">
              <input
                type="checkbox"
                checked={dueForTest}
                onChange={(event) => {
                  setDueForTest(event.target.checked);
                  setPage(1);
                }}
                data-across-test-due=""
              />
              {t("work.across.testDue")}
            </label>
          }
          chosenFact={t("work.raise.chosen", { n: chosen.size, total: assets.data?.count ?? 0 })}
          tickLabel={(row) => t("work.raise.tick", { unit: row.asset_no })}
          tickAllLabel={t("work.raise.tickAll")}
          emptyText={assets.isPending ? t("work.across.loading") : t("work.across.empty")}
          columns={[
            { key: "asset", label: t("work.across.col.asset"), cell: (row) => <span className="font-semibold">{row.asset_no}</span> },
            { key: "type", label: t("work.across.col.type"), cell: (row) => row.type_name },
            { key: "where", label: t("work.across.col.where"), cell: (row) => row.assigned_address ?? "—" },
            {
              key: "test",
              label: t("work.across.col.nextTest"),
              cell: (row) =>
                row.next_test ? <span className="tabular-nums">{formatDate(row.next_test, timeZone, dateFormat)}</span> : "—",
            },
          ]}
          page={page}
          per={per}
          onPage={setPage}
          onPer={(next) => {
            setPer(next);
            setPage(1);
          }}
        />
      )}

      <div className="flex items-center justify-end gap-3" data-across-actions="">
        {blocked !== undefined && (
          <span className="text-base font-semibold text-neutral-700" data-across-blocked="">
            {blocked}
          </span>
        )}
        {failed && (
          <span className="text-base text-danger-700" role="alert">
            {t("work.across.failed")}
          </span>
        )}
        <Button
          variant="primary"
          disabled={blocked !== undefined || busy}
          title={blocked}
          onClick={() => void raise()}
          data-across-raise=""
        >
          {t("work.raise.commit", { count: chosen.size })}
        </Button>
      </div>
    </div>
  );
}
