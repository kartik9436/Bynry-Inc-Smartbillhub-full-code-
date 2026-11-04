// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.07 / P2.12 — the Audit tab: When · Who · What, newest
//           first, paged on the server. A request (image 23) reads its own
//           timeline; a move-in (image 29) reads the audit log of the account
//           it opened.
// Rules:    B14 rule 31 (WHO is a name, never an id; WHAT is the catalogue's
//           sentence, never a stored code) · NFR-3
// ⚠ IMAGE 29's *All · Changes · Messages* IS A SERVER FILTER (`DEF-CUS-9722`):
//   `GET /audit-log?f.entity_id=<account>&f.kind=all|changes|messages`, so
//   each chip pages and counts the whole history, never a cut of one page.
//   *Messages* are the account's queued messages (audited against the
//   message, naming the account). A request's audit (image 23) draws none.
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { AUDIT_KINDS, getAuditLog } from "@/api/endpoints";
import type { AuditKind } from "@/api/endpoints";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { ListPager } from "@/components/ListPager";
import { LoadingSkeleton } from "@/components/StateFrame";
import { PlainTable } from "@/components/Surfaces";
import type { PageSize } from "@/components/tableTypes";
import { actorLabel } from "@/features/audit/AuditLogPage";
import { AuditEventSentenceText } from "@/features/audit/auditEvents";

import { EventWhat } from "../serviceRequestShared";
import { getRequestAudit } from "./moveDetailEndpoints";
import { Day, DetailGroup, EmptyLine } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

function AuditFrame(props: {
  loading: boolean;
  failed: boolean;
  empty: boolean;
  children: React.ReactNode;
  total: number;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
  filter?: React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <DetailGroup title={t("customers.moveDetail.section.audit")} name="audit">
      {props.filter}
      {props.loading ? (
        <LoadingSkeleton variant="table" />
      ) : props.failed ? (
        <EmptyLine>{t("customers.moveDetail.absent.notReadable")}</EmptyLine>
      ) : props.empty ? (
        <EmptyLine>{t("customers.moveDetail.audit.none")}</EmptyLine>
      ) : (
        <>
          <PlainTable data-move-audit="">
            <thead>
              <tr>
                <th>{t("customers.moveDetail.col.when")}</th>
                <th>{t("customers.moveDetail.col.who")}</th>
                <th>{t("customers.moveDetail.col.what")}</th>
              </tr>
            </thead>
            <tbody>{props.children}</tbody>
          </PlainTable>
          <ListPager total={props.total} page={props.page} per={props.per} onPage={props.onPage} onPer={props.onPer} />
        </>
      )}
    </DetailGroup>
  );
}

export function RequestAuditTab(props: { requestId: string; regional: Regional; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const query = useQuery({
    queryKey: ["move-detail-request-audit", props.requestId, page, per],
    queryFn: () => getRequestAudit(props.requestId, page, per, client),
  });
  const rows = query.data?.results ?? [];
  return (
    <AuditFrame
      loading={query.isPending}
      failed={query.isError}
      empty={rows.length === 0}
      total={query.data?.count ?? 0}
      page={page}
      per={per}
      onPage={setPage}
      onPer={setPer}
    >
      {rows.map((row) => (
        <tr key={row.id}>
          <td>
            <Day value={row.at} regional={props.regional} withTime />
          </td>
          <td>{row.actor_name ?? t("audit.actor.system")}</td>
          <td>
            {row.kind === "state" && row.to_state ? (
              t("customers.moveDetail.audit.movedTo", {
                state: t(`customers.serviceRequest.state.${row.to_state}`, { defaultValue: row.to_state }),
              })
            ) : (
              <EventWhat kind={row.kind} noteType={row.note_type} t={t} />
            )}
          </td>
        </tr>
      ))}
    </AuditFrame>
  );
}

export function MoveAuditTab(props: { accountId: string | null; regional: Regional; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const [kind, setKind] = useState<AuditKind>("all");
  const query = useQuery({
    queryKey: ["move-detail-audit", props.accountId ?? "", kind, page, per],
    enabled: props.accountId !== null,
    queryFn: () =>
      getAuditLog(
        { filters: { entity_id: props.accountId ?? "" }, kind, page, per, sort: "when", dir: "desc" },
        client,
      ),
  });
  if (props.accountId === null) {
    return (
      <DetailGroup title={t("customers.moveDetail.section.audit")} name="audit">
        <EmptyLine>{t("customers.moveDetail.audit.noAccountYet")}</EmptyLine>
      </DetailGroup>
    );
  }
  const rows = query.data?.page.results ?? [];
  return (
    <AuditFrame
      loading={query.isPending}
      failed={query.isError}
      empty={rows.length === 0}
      total={query.data?.page.count ?? 0}
      page={page}
      per={per}
      onPage={setPage}
      onPer={setPer}
      filter={
        <ChipRow className="mb-4" role="group" aria-label={t("customers.moveDetail.audit.kind.label")}>
          {AUDIT_KINDS.map((value) => (
            <ChipToggle
              key={value}
              selected={kind === value}
              data-audit-kind={value}
              onClick={() => {
                setKind(value);
                setPage(1);
              }}
            >
              {t(`customers.moveDetail.audit.kind.${value}`)}
            </ChipToggle>
          ))}
        </ChipRow>
      }
    >
      {rows.map((row) => (
        <tr key={row.id}>
          <td>
            <Day value={row.created_at} regional={props.regional} withTime />
          </td>
          <td>{actorLabel(row, t)}</td>
          <td>
            <AuditEventSentenceText row={row} t={t} />
          </td>
        </tr>
      ))}
    </AuditFrame>
  );
}
