// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-7618 (2026-09-28) — the build detail page's tab bodies
//           were EIGHT build panels declared inside
//           `features/customers/BuildDetailTabs.tsx`, which is a second home
//           for a build panel and the duplication `CR-151-BRC09` §2 rule (2)
//           forbids. They live in this kit now, beside the panels the premises
//           and the account pages already compose. This file is the piece
//           every one of them shares.
// Rules:    B14 rule 43 (a piece of UI is built as a COMPONENT) · rule 36
//           (`Panel` IS the information group on a detail screen) · rule 21
//           (Tailwind utilities; each file here is on route-b-migrated.txt) ·
//           `CR-151-BRC09` §3 — *"New tab content that has no shared panel is
//           built as components under the same kit, not inline"*
// Tests:    src/features/customers/BuildDetailTabs.dom.test.tsx (through the
//           page, at its real address) · g93_one_build_destination.py
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import type { ApiClient } from "@/api/client";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import type { Translator } from "@/features/customers/newConnectShared";
import type { ConnectionDetail } from "@/features/customers/newConnectEndpoints";

import type { BuildRecord } from "../workEndpoints";

export interface BuildTabProps {
  t: Translator;
  detail: ConnectionDetail;
  /** `GET /connections/{id}/record`, or `null` while it is in flight. */
  record: BuildRecord | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** `tenantPathFrom` bound to this tenant — every link below goes through it. */
  path: (segment: string) => string;
  /**
   * The owner account's id, DERIVED and verified, or `null`.
   *
   * ⚠ **NEITHER READ ON THIS PAGE SERVES IT.** `ConnectionDetail` carries
   * `owner_account_no` and the record carries `money.billed_to`, both of them
   * NUMBERS (B14 rule 31's own distinction). The page resolves the id through
   * `GET /premises/{id}/build` and hands it down only when that read's build
   * IS this build — see `BuildDetailPage`. `null` here means *the id could not
   * be established*, and every control that needs it is then refused BY NAME
   * rather than pointed at nothing.
   */
  accountId: string | null;
  client?: ApiClient;
  /** ⊕ `DEF-MET-9238` — why this person may not change the build (a role that
   *  only VIEWS Premises / Accounts), or null/absent. A tab's write controls
   *  are drawn disabled with it (BR-SHL-025); the server refuses regardless. */
  readOnlyReason?: string | null;
}

/** A panel with the drawn heading. Every tab body is one or more of these —
 *  B14 rule 36's *"`Panel` IS the information group on a detail screen"*. */
export function Section(props: { id: string; title: string; children: ReactNode }) {
  return (
    <Panel as="section" data-build-section={props.id}>
      <h3>{props.title}</h3>
      {props.children}
    </Panel>
  );
}

/**
 * The drawn strip above every tab body.
 *
 * ⚠ **IT IS THE KIT'S `KPIStrip` AND NOT `BuildRecordTiles`, AND THE REASON IS
 * THE VOCABULARY RATHER THAN THE SHAPE.** `BuildRecordTiles` is the record's
 * own five tiles — Units · Activated · Work orders · Quoted · Outstanding,
 * blueprint p098 — with those five labels hard-wired. The seven PNGs of
 * `05-prototype/new-connect-detail-2026-09-28/` draw a DIFFERENT strip per
 * tab (Scope · Mode · Target · Waiting on · Started on Overview; Orders · Done
 * · Open · Target on Work; Charged · Paid · Outstanding on Charges), so
 * composing that panel would mean either renaming its five or passing facts it
 * has no tile for. Both hosts use the same shared strip one level down, which
 * is where the sharing actually is.
 *
 * ⚠ **A FACT WITH NO SOURCE IS OMITTED, NEVER DASHED** — `BuildRecordTiles`'
 * own rule, and the reason is its own: a permanent dash on every build for
 * ever is the dead-control shape, and an invented figure is worse.
 */
export function Facts(props: { id: string; tiles: KpiTile[] }) {
  if (props.tiles.length === 0) {
    return null;
  }
  return (
    <div data-build-facts={props.id}>
      <KPIStrip kpis={props.tiles} />
    </div>
  );
}

export function text(value: string | null | undefined): string | null {
  return value === null || value === undefined || value === "" ? null : value;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-151-BRC09 §2 rule (2) and §3
// generated: 2026-09-28 by the DEF-CUS-7618 lane
// checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
