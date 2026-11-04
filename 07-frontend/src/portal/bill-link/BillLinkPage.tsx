// ── Trace ──────────────────────────────────────────────
// Change:  DEF-BIL-10531 — `/{tenant}/portal/bill#token=…`, the page a bill
//          email's link opens (no sign-in)
// Rules:   PO 2026-10-22, *"b direct PDF link"* · decision log 2026-10-22
//          *"One-time link secrets travel in the URL FRAGMENT"* — the secret is
//          read from after `#` (`useLinkSecret`), taken off the address bar and
//          POSTed in the body · mounted BESIDE the portal app (App.tsx), like
//          the agreement page: it opens whether or not the portal is live
// Tests:   src/portal/bill-link/BillLinkPage.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useLinkSecret } from "@/routing/useLinkSecret";

import { AgreementLinkExpired } from "../agreements/AgreementAcceptance";
import { fetchBillLinkDocument, openBillLink } from "../api/billLinkClient";
import { getPortalFront } from "../api/guestClient";
import { PortalLanguage } from "../components/PortalLanguage";
import { GuestFrame } from "../shell/GuestFrame";

import { BillLinkCard } from "./BillLinkCard";

/** The route, relative to `/:tenant` — App.tsx mounts it; the backend's
 *  `bill_links.BILL_LINK_PATH` builds the same address into the email. */
export const BILL_LINK_ROUTE = "portal/bill";
/** The fragment key — `bill_links.TOKEN_PARAM`. */
export const BILL_LINK_TOKEN_PARAM = "token";
const TOKEN_KEYS = [BILL_LINK_TOKEN_PARAM] as const;

/** Hand the browser the PDF as a download named after the bill. */
function saveBlob(blob: Blob, filename: string): void {
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 0);
}

export function BillLinkPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  // The tenant from the ROUTE, never from `window.location`.
  const tenant = useParams().tenant ?? "";
  const token = useLinkSecret(TOKEN_KEYS)[BILL_LINK_TOKEN_PARAM] ?? "";
  const [gone, setGone] = useState<string | null | undefined>(undefined);

  const front = useQuery({ queryKey: queryKeys.portalFront, queryFn: () => getPortalFront(client) });
  const link = useQuery({
    queryKey: ["bill-link", token],
    queryFn: () => openBillLink(token, client),
    enabled: token !== "",
    retry: false,
    staleTime: Infinity,
  });
  const download = useMutation({
    mutationFn: () => fetchBillLinkDocument(token, tenant),
    onSuccess: (answer) => {
      if (answer.kind === "pdf") saveBlob(answer.blob, answer.filename);
      else setGone(answer.phone);
    },
  });

  if (front.isPending || (token !== "" && link.isPending)) {
    return <LoadingSkeleton variant="card" />;
  }
  if (front.data === undefined || (token !== "" && link.data === undefined)) {
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
  if (gone !== undefined) {
    body = <AgreementLinkExpired phone={gone} />;
  } else if (token === "" || link.data === undefined || link.data.state === "unavailable") {
    const phone = link.data?.state === "unavailable" ? link.data.support_phone : null;
    body = <AgreementLinkExpired phone={phone} />;
  } else {
    body = (
      <BillLinkCard
        bill={link.data}
        working={download.isPending}
        failed={download.isError}
        onDownload={() => download.mutate()}
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
