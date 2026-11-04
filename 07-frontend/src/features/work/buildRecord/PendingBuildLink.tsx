// ── Trace ──────────────────────────────────────────────
// Change:   CR-162-BRC10 — the PO, 2026-10-02, verbatim: *"when we have new
//           connect request -we are traking the progress from detail of new
//           connect hense as shown in screenshot build ta on premises is not
//           required ;when premises is in pending status and if you have new
//           connect request asoscaiated to it then you can show link for
//           request to improve interaction"*.
// Rules:    B14 rule 31 (the build is named by its number, never an id) ·
//           rule 33 (a fact ≤ 6 words) · rule 43 (one component, two hosts) ·
//           rule 21 (Tailwind utilities; listed in route-b-migrated.txt)
// ───────────────────────────────────────────────────────
/**
 * **The link from a Pending premises or account to the New Connection that
 * will activate it.** The Build tab on the premises and the Build panel on the
 * account are gone (the request's own page tracks progress and takes every
 * action); what stays on those two pages is this one line:
 *
 *     New connection CON-26-0135 · Requested · Open request
 *
 * and, on an account opened before approval (ruled B), the fact that matters
 * for its money first: *Billing starts when the unit is activated.*
 */
import { Link } from "react-router-dom";

import { connectionStateLabel } from "@/features/customers/NewConnectsTab";
import { CONNECTIONS_ROUTE } from "@/features/customers/newConnectShared";
import type { Translator } from "@/features/customers/newConnectShared";

export interface PendingBuildRef {
  id: string;
  connection_no: string | null;
  /** The build's state word; absent when only the number is known. */
  state?: string | null;
}

/** Where the link goes — the request's own page, by ADDRESS. */
export function pendingBuildPath(buildId: string): string {
  return `${CONNECTIONS_ROUTE}/${buildId}`;
}

export function PendingBuildLink(props: {
  build: PendingBuildRef;
  t: Translator;
  path: (segment: string) => string;
  /** The account case: billing waits until the unit is activated. */
  billingWaits?: boolean;
}) {
  const { build, t } = props;
  return (
    <p
      className="m-0 flex flex-wrap items-center gap-x-2 text-sm text-neutral-700"
      data-pending-build={build.connection_no ?? ""}
    >
      {props.billingWaits === true && (
        <span className="font-semibold text-text" data-billing-waits="">
          {t("customers.build.pending.billingWaits", {
            defaultValue: "Billing starts once the unit activates.",
          })}
        </span>
      )}
      <span>
        {t("customers.build.pending.request", { defaultValue: "New connection" })}{" "}
        {build.connection_no}
        {build.state !== undefined && build.state !== null && (
          <> · {connectionStateLabel(build.state, t)}</>
        )}
      </span>
      <Link
        to={props.path(pendingBuildPath(build.id))}
        className="font-semibold text-accent underline underline-offset-2"
        data-open-request={build.connection_no ?? ""}
      >
        {t("customers.build.pending.open", { defaultValue: "Open request" })}
      </Link>
    </p>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-162-BRC10 (PO 2026-10-02, the Build tab on the premises is not required)
// generated: 2026-10-02 by lane NC-A
// gates: G31 (directory on route-b-migrated.txt) · G13 (mounted by PremisesDetailPage and AccountDetailPage)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
