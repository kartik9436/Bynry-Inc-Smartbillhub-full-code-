// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.07 / P2.12 — the Messages tab, on a request (image
//           22) and on a move-in (image 28): Message · To · Channel · When ·
//           State, paged on the server, and *+ Send a message*.
// Rules:    B14 rule 31 (the template CODE is never a value — the catalogue
//           names it) · BR-NOT-013 (the queue's own word, never "sent" for
//           "queued") · NFR-3 (paged on the server)
// Data:     a request — `GET /service-requests/{id}/messages` (§9.REQ); a
//           move-in — the account's outbound queue (`GET /outbound?f.account_id`),
//           which is where §9.FLOW's *Send a message* door
//           (`/accounts/{id}/communication`) puts what it sends.
// ⚠ ON A REQUEST *+ Send a message* IS HELD: no request has a door for it
//   (§9.REQ — *"not a request door yet"*). It is drawn disabled with its reason
//   (BR-SHL-025) and `MoveInDetail.test.tsx` names the address that releases it.
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { ListPager } from "@/components/ListPager";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import type { PageSize } from "@/components/tableTypes";

import { getRequestMessages } from "./moveDetailEndpoints";
import { Day, DetailGroup, EmptyLine } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";
import { useAccountMessages } from "./MoveOverview";

interface MessageLine {
  id: string;
  template_code: string | null;
  to: string | null;
  channel: string;
  status: string;
  at: string | null;
}

function statusTone(status: string): StatusTone {
  if (status === "sent" || status === "delivered") return "success";
  if (status === "failed" || status === "bounced") return "danger";
  return "neutral";
}

function MessagesTable(props: {
  rows: readonly MessageLine[] | null;
  total: number;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
  failed: boolean;
  regional: Regional;
}) {
  const { t } = useTranslation();
  if (props.failed) return <EmptyLine>{t("customers.moveDetail.absent.notReadable")}</EmptyLine>;
  if (props.rows === null) return <LoadingSkeleton variant="table" />;
  if (props.rows.length === 0) return <EmptyLine>{t("customers.moveDetail.messages.none")}</EmptyLine>;
  return (
    <>
      <PlainTable data-move-messages="">
        <thead>
          <tr>
            <th>{t("customers.moveDetail.col.message")}</th>
            <th>{t("customers.moveDetail.col.to")}</th>
            <th>{t("customers.moveDetail.col.channel")}</th>
            <th>{t("customers.moveDetail.col.when")}</th>
            <th>{t("customers.moveDetail.col.state")}</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.id}>
              <td>
                {row.template_code === null
                  ? t("customers.account.communication.what.unknown")
                  : t(`customers.moveDetail.template.${row.template_code}`, {
                      defaultValue: t("customers.account.communication.what.unknown"),
                    })}
              </td>
              <td>{row.to ?? t("customers.account.communication.noAddress")}</td>
              <td>
                {t(`customers.account.communication.channel.${row.channel}`, { defaultValue: row.channel })}
              </td>
              <td>
                <Day value={row.at} regional={props.regional} withTime />
              </td>
              <td>
                <StatusPill tone={statusTone(row.status)}>
                  {t(`customers.account.communication.status.${row.status}`, { defaultValue: row.status })}
                </StatusPill>
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
      <ListPager total={props.total} page={props.page} per={props.per} onPage={props.onPage} onPer={props.onPer} />
    </>
  );
}

export function RequestMessagesTab(props: { requestId: string; regional: Regional; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const query = useQuery({
    queryKey: ["move-detail-request-messages", props.requestId, page, per],
    queryFn: () => getRequestMessages(props.requestId, page, per, client),
  });
  const rows: MessageLine[] | null = query.data
    ? query.data.results.map((row) => ({
        id: row.id,
        template_code: row.template_code,
        to: row.to_name ?? row.to_address,
        channel: row.channel,
        status: row.status,
        at: row.sent_at ?? row.queued_at,
      }))
    : null;
  return (
    <DetailGroup
      title={t("customers.moveDetail.section.messages")}
      name="messages"
      trailing={
        <Button
          variant="ghost"
          size="sm"
          disabled
          title={t("customers.moveDetail.messages.noRequestDoor")}
          data-held="request-send-message"
        >
          {t("customers.moveDetail.action.sendMessageNew")}
        </Button>
      }
    >
      <MessagesTable
        rows={rows}
        total={query.data?.count ?? 0}
        page={page}
        per={per}
        onPage={setPage}
        onPer={setPer}
        failed={query.isError}
        regional={props.regional}
      />
    </DetailGroup>
  );
}

export function MoveMessagesTab(props: {
  accountId: string | null;
  regional: Regional;
  onSend: (() => void) | null;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const query = useAccountMessages(props.accountId, page, per, props.client);
  const rows: MessageLine[] | null = query.data
    ? query.data.results.map((row) => ({
        id: row.id,
        template_code: row.template_code,
        to: row.recipient_address,
        channel: row.channel,
        status: row.status,
        at: row.queued_at,
      }))
    : null;
  return (
    <DetailGroup
      title={t("customers.moveDetail.section.messages")}
      name="messages"
      trailing={
        props.onSend === null ? undefined : (
          <Button variant="ghost" size="sm" onClick={props.onSend} data-testid="move-detail-send-message">
            {t("customers.moveDetail.action.sendMessageNew")}
          </Button>
        )
      }
    >
      {props.accountId === null ? (
        <EmptyLine>{t("customers.moveDetail.messages.noAccountYet")}</EmptyLine>
      ) : (
        <MessagesTable
          rows={rows}
          total={query.data?.count ?? 0}
          page={page}
          per={per}
          onPage={setPage}
          onPer={setPer}
          failed={query.isError}
          regional={props.regional}
        />
      )}
    </DetailGroup>
  );
}
