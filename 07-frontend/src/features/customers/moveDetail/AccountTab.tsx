// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.10 — the Account tab (image 25): *Account holder*,
//           *Co-owners* and *Documents* with *+ Add document*.
// Rules:    B14 rule 43 (the account's own Documents tab is REUSED, not
//           re-drawn — it already uploads, opens and removes) · rule 31 ·
//           BR-CUS-092 (no identifier is shown whole; co-owners carry none here)
// Data:     `GET /accounts/{id}` (holder, contact, mailing) · the move's
//           `co_owners` (§9.LIST, added by this lane) · the account documents
//           tab's own read.
// ───────────────────────────────────────────────────────
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountDetail } from "@/api/endpoints";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

import { AccountDocumentsTab } from "../AccountDocumentsTab";
import { CoOwnerPhotoIdUpload } from "../CoOwnerCards";
import { Day, DetailGroup, EmptyLine, FactGrid, Stated } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

export interface MoveCoOwner {
  /** CR-171 P2.24 — the row's handle for the *Photo ID* upload; never shown
   *  (B14 rule 31). Absent on a read from before 2.541.0. */
  id?: string;
  kind: "co_owner" | "officer" | string;
  full_name: string;
  relationship: string | null;
  title: string | null;
  phone: string | null;
  email: string | null;
  contact_by: string | null;
  responsible_for_bills: boolean;
  photo_id: boolean;
}

export function AccountTab(props: {
  accountId: string | null;
  coOwners: readonly MoveCoOwner[];
  regional: Regional;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const account = useQuery({
    queryKey: ["move-detail-account", props.accountId ?? ""],
    enabled: props.accountId !== null,
    queryFn: () => getAccountDetail(props.accountId ?? "", client),
  });
  if (props.accountId === null) {
    return (
      <DetailGroup title={t("customers.moveDetail.section.accountHolder")} name="holder">
        <EmptyLine>{t("customers.moveDetail.absent.noAccountYet")}</EmptyLine>
      </DetailGroup>
    );
  }
  const a = account.data;
  const contact = a?.contacts?.find((row) => row.is_primary) ?? a?.contacts?.[0] ?? null;
  const mailing = a?.addresses?.find((row) => row.kind === "mailing") ?? null;
  const notRecorded = <Stated label={t("customers.moveDetail.absent.notRecorded")} />;
  const officers = props.coOwners.some((row) => row.kind === "officer");

  return (
    <div className="flex flex-col gap-6" data-move-tab="account">
      <DetailGroup title={t("customers.moveDetail.section.accountHolder")} name="holder">
        {account.isPending ? (
          <LoadingSkeleton variant="card" />
        ) : !a ? (
          <EmptyLine>{t("customers.moveDetail.absent.notReadable")}</EmptyLine>
        ) : (
          <FactGrid
            name="move-holder"
            facts={[
              {
                id: "customer",
                label: t("customers.moveDetail.fact.customer"),
                value: [a.customer_no, a.name].filter(Boolean).join(" · ") || notRecorded,
              },
              {
                id: "customerType",
                label: t("customers.moveDetail.fact.customerType"),
                value:
                  [
                    t(`customers.accounts.category.${a.account_type}`, { defaultValue: a.account_type ?? "" }),
                    a.account_subtype_name,
                  ]
                    .filter(Boolean)
                    .join(" · ") || notRecorded,
              },
              { id: "email", label: t("customers.moveDetail.fact.email"), value: contact?.email ?? notRecorded },
              { id: "phone", label: t("customers.moveDetail.fact.phone"), value: contact?.phone ?? notRecorded },
              {
                id: "dob",
                label: t("customers.moveDetail.fact.dob"),
                value: contact?.dob ? <Day value={contact.dob} regional={props.regional} /> : notRecorded,
              },
              // DEF-CUS-9788 — the PO this account's bills quote, when one was recorded.
              ...(a.po_number
                ? [{ id: "po", label: t("customers.moveIn.review.po"), value: a.po_number }]
                : []),
              {
                id: "mailing",
                label: t("customers.moveDetail.fact.mailing"),
                value: mailing
                  ? [mailing.line1, mailing.city, mailing.state, mailing.postal_code].filter(Boolean).join(", ")
                  : t("customers.moveDetail.mailing.same"),
              },
            ]}
          />
        )}
      </DetailGroup>
      <DetailGroup
        title={t(officers ? "customers.moveDetail.section.officers" : "customers.moveDetail.section.coOwners")}
        name="co-owners"
      >
        {props.coOwners.length === 0 ? (
          <EmptyLine>{t("customers.moveDetail.coOwners.none")}</EmptyLine>
        ) : (
          <PlainTable data-move-co-owners="">
            <thead>
              <tr>
                <th>{t("customers.moveDetail.fact.name")}</th>
                <th>{t(officers ? "customers.moveDetail.col.title" : "customers.moveDetail.col.relationship")}</th>
                <th>{t("customers.moveDetail.fact.phone")}</th>
                <th>{t("customers.moveDetail.col.contactBy")}</th>
                <th>{t("customers.moveDetail.col.bills")}</th>
                <th>{t("customers.moveDetail.col.photoId")}</th>
              </tr>
            </thead>
            <tbody>
              {props.coOwners.map((row, index) => (
                <tr key={`${row.full_name}-${index}`}>
                  <td>{row.full_name}</td>
                  <td>{(officers ? row.title : row.relationship) ?? ""}</td>
                  <td>{row.phone ?? ""}</td>
                  <td>
                    {row.contact_by
                      ? t(`customers.moveDetail.contactBy.${row.contact_by}`, { defaultValue: row.contact_by })
                      : ""}
                  </td>
                  <td>
                    {row.responsible_for_bills
                      ? t("customers.moveDetail.coOwners.responsible")
                      : t("customers.moveDetail.coOwners.notResponsible")}
                  </td>
                  <td>
                    {row.photo_id ? (
                      <StatusPill tone="success">{t("customers.moveDetail.reads.recorded")}</StatusPill>
                    ) : (
                      <span className="inline-flex flex-wrap items-center gap-2">
                        <StatusPill tone="warning">{t("customers.moveDetail.coOwners.missing")}</StatusPill>
                        {/* CR-171 P2.24 (lane MVI-WIZ-CUST) — the photo ID the
                            wizard could not take: the account exists now. */}
                        {props.accountId !== null && row.id !== undefined ? (
                          <CoOwnerPhotoIdUpload
                            accountId={props.accountId}
                            coOwnerId={row.id}
                            name={row.full_name}
                            t={(key, params) => t(key, params)}
                            client={client}
                            onDone={() => void queryClient.invalidateQueries({ queryKey: ["move-record"] })}
                          />
                        ) : null}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        )}
      </DetailGroup>
      <AccountDocumentsTab
        accountId={props.accountId}
        client={client}
        timeZone={props.regional.timeZone}
        dateFormat={props.regional.dateFormat}
      />
    </div>
  );
}
