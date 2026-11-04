// ── Trace ──────────────────────────────────────────────
// Change:  CR-190-BRC10 lane AGREEMENT — `/{tenant}/portal/agreements/:token`,
//          the page an agreement email's button opens (no sign-in)
// Rules:   PO 2026-10-22 answer 4 — *"No"* to accepting inside the signed-in
//          portal: this route is mounted BESIDE the portal app (App.tsx), not
//          in `PORTAL_ROUTES`, and wears the guest frame for the utility's
//          brand only — it opens whether or not the portal is switched live,
//          because an agreement sent by email must be acceptable either way.
// Tests:   src/portal/agreements/AgreementPage.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";

import { acceptAgreement, agreementDocumentHref, getAgreement } from "../api/agreementClient";
import type { AgreementAccepted as Accepted } from "../api/agreementClient";
import { getPortalFront } from "../api/guestClient";
import { PortalLanguage } from "../components/PortalLanguage";
import { GuestFrame } from "../shell/GuestFrame";

import type { AgreementFieldErrors } from "./AgreementAcceptance";
import { AgreementAccepted, AgreementAcceptance, AgreementLinkExpired } from "./AgreementAcceptance";

/** The route, relative to `/:tenant` — App.tsx mounts it; the backend's
 *  `agreements.AGREEMENT_PATH` builds the same address into the email. */
export const AGREEMENT_ROUTE = "portal/agreements/:token";

export function AgreementPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const params = useParams();
  const token = params.token ?? "";
  // The tenant from the ROUTE, never from `window.location` — the address the
  // PDF link is built on must be the one this page was opened under.
  const tenant = params.tenant ?? "";
  const [accepted, setAccepted] = useState<Accepted | null>(null);
  const [gone, setGone] = useState<string | null | undefined>(undefined);
  const [errors, setErrors] = useState<AgreementFieldErrors>({});

  const front = useQuery({ queryKey: queryKeys.portalFront, queryFn: () => getPortalFront(client) });
  const link = useQuery({
    queryKey: ["agreement-link", token],
    queryFn: () => getAgreement(token, client),
    retry: false,
  });
  const accept = useMutation({
    mutationFn: (body: Parameters<typeof acceptAgreement>[1]) => acceptAgreement(token, body, client),
    onSuccess: (answer) => {
      setErrors({});
      if (answer.state === "accepted") setAccepted(answer);
      else setGone(answer.support_phone);
    },
    onError: (error) => {
      const next: AgreementFieldErrors = {};
      if (isApiError(error)) {
        for (const item of error.fieldErrors) {
          if (item.field === "agreed" || item.field === "date" || item.field === "name") {
            next[item.field] = t(item.message_key);
          }
        }
      }
      setErrors(next);
    },
  });

  if (front.isPending || link.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (front.data === undefined || link.data === undefined) {
    return (
      <FailedWithRetry
        title={t("portal.failedTitle")}
        reason={refusalText(t, front.error ?? link.error)}
        onRetry={() => {
          void front.refetch();
          void link.refetch();
        }}
        onDownloadReport={() => undefined}
      />
    );
  }

  let body;
  if (accepted !== null) {
    body = (
      <AgreementAccepted
        agreementName={accepted.agreement_name}
        date={accepted.accepted_date}
        name={accepted.accepted_name}
      />
    );
  } else if (gone !== undefined) {
    body = <AgreementLinkExpired phone={gone} />;
  } else if (link.data.state === "unavailable") {
    body = <AgreementLinkExpired phone={link.data.support_phone} />;
  } else {
    body = (
      <AgreementAcceptance
        agreement={link.data}
        documentHref={agreementDocumentHref(token, tenant)}
        working={accept.isPending}
        errors={errors}
        onAccept={(answer) => accept.mutate(answer)}
      />
    );
  }
  return (
    <div data-portal="">
      <PortalLanguage />
      <GuestFrame front={front.data}>{body}</GuestFrame>
    </div>
  );
}
