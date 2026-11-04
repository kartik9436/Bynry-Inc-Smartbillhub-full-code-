// ── Trace ──────────────────────────────────────────────
// Change:  CR-190-BRC10 lane AGREEMENT — *"Staff see Sent / Accepted / Expired
//          on the account. A Resend agreement action issues a new link and
//          voids the old one."* (decision log 2026-10-22, the design confirmed)
// Rules:   B14 rule 43 (a component, mounted by the Documents tab and the
//          header chip) · rule 15 (row actions are icons with names) · rule 31
//          (no id on screen) · rule 33 (labels only — no rationale) ·
//          BR-SHL-025 (a blocked control stays visible and says why)
// Tests:   src/features/customers/AccountAgreementsPanel.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { openDocumentContent } from "@/components/documents";
import { EnvelopeIcon, EyeIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";

import { accountDocumentContentPath } from "./AccountDocumentsTab";
import { latestPerAgreement, listAccountAgreements, resendAccountAgreement } from "./agreementsApi";
import type { AccountAgreement, AgreementStatus } from "./agreementsApi";

const TONE: Record<AgreementStatus, StatusTone> = {
  pending: "info",
  accepted: "success",
  expired: "warning",
  voided: "muted",
};

export function agreementsQueryKey(accountId: string): readonly unknown[] {
  return ["account-agreements", accountId];
}

/** The one read both the panel and the chip share, so they cannot disagree. */
export function useAccountAgreements(accountId: string, client: ApiClient = api) {
  return useQuery({
    queryKey: agreementsQueryKey(accountId),
    queryFn: () => listAccountAgreements(accountId, client),
  });
}

/** The status word, shared by the panel and the chip. */
export function AgreementStatusPill(props: { status: AgreementStatus }) {
  const { t } = useTranslation();
  return <StatusPill tone={TONE[props.status]}>{t(`customers.account.agreements.status.${props.status}`)}</StatusPill>;
}

/**
 * The account header's chip: the newest request of each agreement, by status.
 * Draws nothing for an account that was never sent one.
 */
export function AgreementStatusChip(props: { accountId: string; client?: ApiClient }) {
  const { t } = useTranslation();
  const query = useAccountAgreements(props.accountId, props.client);
  const latest = latestPerAgreement(query.data ?? []);
  if (latest.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-1" data-agreement-chip="">
      {latest.map((row) => (
        <span key={row.id} className="inline-flex items-center gap-1" title={row.agreement_name}>
          <span className="sr-only">{row.agreement_name}</span>
          <AgreementStatusPill status={row.status} />
        </span>
      ))}
      <span className="sr-only">{t("customers.account.agreements.title")}</span>
    </span>
  );
}

/** The Documents tab's Agreements panel. */
export function AccountAgreementsPanel(props: {
  accountId: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  writeBlockedReason: string | null;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useAccountAgreements(props.accountId, client);
  const resend = useMutation({
    mutationFn: (row: AccountAgreement) => resendAccountAgreement(props.accountId, row.id, client),
    onSuccess: () => {
      toast(t("customers.account.agreements.resent"));
      void queryClient.invalidateQueries({ queryKey: agreementsQueryKey(props.accountId) });
    },
    onError: () => toast(t("customers.account.agreements.resendFailed")),
  });

  const rows = query.data ?? [];
  // Resend belongs to the NEWEST request of each agreement only: an older one
  // has already been replaced, and a second link for it would be a third.
  const newest = new Set(latestPerAgreement(rows).map((row) => row.id));
  if (!query.isError && rows.length === 0) return null;
  const date = (value: string | null) =>
    value === null ? null : (
      <DateCell value={value} timeZone={props.timeZone} dateFormat={props.dateFormat} />
    );

  return (
    <Panel as="section" tone="group" data-overview-group="agreements" title={t("customers.account.agreements.title")}>
      {query.isError ? (
        <p className="text-base text-neutral-600">{t("customers.account.agreements.loadFailed")}</p>
      ) : (
        <ul className="m-0 flex list-none flex-col divide-y divide-neutral-200 p-0">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center gap-3 py-2" data-agreement-row={row.status}>
              <span className="min-w-0 flex-1 font-semibold text-neutral-900">{row.agreement_name}</span>
              <AgreementStatusPill status={row.status} />
              <span className="text-base text-neutral-600">
                {row.status === "pending" ? (
                  <>
                    {t("customers.account.agreements.expires")} {date(row.expires_at)}
                  </>
                ) : row.status === "accepted" ? (
                  <>
                    {date(row.accepted_date)} · {row.accepted_name}
                  </>
                ) : (
                  <>
                    {t("customers.account.agreements.sentOn")} {date(row.issued_at)}
                  </>
                )}
              </span>
              <RowActions>
                {row.accepted_document_id !== null ? (
                  <RowAction
                    icon={<EyeIcon />}
                    label={t("customers.account.agreements.openCopy")}
                    onClick={() => {
                      openDocumentContent(
                        accountDocumentContentPath(props.accountId, row.accepted_document_id ?? ""),
                        "view",
                      );
                    }}
                  />
                ) : null}
                {newest.has(row.id) && (row.status === "pending" || row.status === "expired") ? (
                  <RowAction
                    icon={<EnvelopeIcon />}
                    label={t("customers.account.agreements.resend")}
                    reason={props.writeBlockedReason}
                    working={resend.isPending && resend.variables?.id === row.id}
                    onClick={() => resend.mutate(row)}
                  />
                ) : null}
              </RowActions>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
