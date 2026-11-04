// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-7618 (2026-09-28) — this tab WAS a hand-rolled
//           `PlainTable` in `features/customers/BuildDetailTabs.tsx:660`, with
//           its own `<thead>`, its own empty state and two permanently absent
//           holder cells. It now COMPOSES `buildViews.WorkOrdersTab`, the
//           shared `DataTable` the premises detail and the account detail
//           already mount, on a third host.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/03-work.png`
// Rules:    `CR-151-BRC09` §2 rule (2) — *"NO PANEL IS COPIED. The page
//           composes `features/work/buildViews.tsx` and its `buildRecord/`
//           kit"* · B14 rule 43 · rule 20 (one table type) · CLAUDE.md
//           hard-won law 2's mirror (a control that refuses when it need not)
// Tests:    src/features/customers/BuildDetailTabs.dom.test.tsx ·
//           src/features/work/buildViews.test.tsx (the two hosts that must
//           not move) · g93_one_build_destination.py
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT COMPOSING IT BOUGHT, BESIDES CLOSING THE DEFECT
// ══════════════════════════════════════════════════════════════════════════
// The hand-rolled table had seven columns, no search, no filter, no column
// chooser, no pagination and no way to open an order without leaving the page.
// `WorkOrdersTab` has all five, and it reads the SCOPED row, which carries
// three facts the connection read does not:
//
//   * **the HOLDER.** `ConnectionWorkOrder` serves none at all, so both drawn
//     cells were `AbsentValue` on every row for ever — a permanent dash, which
//     is the dead-control shape. `_scoped_row` serves `technician`, one holder
//     with `kind: "person"` for a technician and the CREW's own kind
//     otherwise, so the two drawn columns each say what is actually known.
//   * **TARGET.** `window_start` / `due_at` / `completed_at`, drawn by
//     `03-work.png` and absent from the hand-rolled table entirely.
//   * **the drawer.** `WorkOrderPanel`, which the eye in the row action opens.
//
// ⚠ **THE ONE THING THE WIRE STILL CANNOT SAY** is a crew holding an order
// that ALSO names a technician: the server folds the two into one holder
// (`dispatch._holder`). `03-work.png` draws no such row, and the two cells
// state an absence rather than guessing — they do not claim the other is empty.
//
// ⚠ **AND THE BLOCKING BANNER IS NOT COMPOSED HERE, DELIBERATELY.**
// `buildRecord/BuildBlockingBanner.tsx` is the drawn red strip at the foot of
// `03-work.png`, and its whole action is a `ButtonLink` to *where the Work
// orders tab lives*. On the Work orders tab that is a door to where the reader
// is already standing, which is the duplicate door the Product Owner took off
// this page's header on 2026-09-28. Reported rather than built: it belongs on
// Overview pointing at `?tab=work`, which is a drawing question and not this
// defect's.
import { useState } from "react";

import type { KpiTile } from "@/components/KPIStrip";
import { DateCell } from "@/components/DateCell";

import { WorkOrdersTab } from "../buildViews";
import { Facts, Section, text } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

export function BuildWorkTab(props: BuildTabProps) {
  const { t, detail } = props;
  // The drawer's open row. It is LOCAL because the drawer is a reading aid and
  // not an address: `03-work.png` gives it no deep link and the page's `?tab=`
  // is the only thing in the query string the build screen owns.
  const [openOrderId, setOpenOrderId] = useState<string | null>(null);

  const tiles: KpiTile[] = [
    {
      id: "orders",
      label: t("customers.build.fact.orders", { defaultValue: "Orders" }),
      value: <span className="tabular-nums">{detail.orders.total}</span>,
    },
    {
      id: "done",
      label: t("customers.build.fact.done", { defaultValue: "Done" }),
      value: <span className="tabular-nums">{detail.orders.done}</span>,
    },
    {
      id: "open",
      label: t("customers.build.fact.open", { defaultValue: "Open" }),
      value: <span className="tabular-nums">{detail.orders.total - detail.orders.done}</span>,
    },
  ];
  // ⚠ **THE FOURTH DRAWN TILE, WHICH THE HAND-ROLLED VERSION DID NOT HAVE.**
  // `03-work.png` draws Orders · Done · Open · Target. It is omitted rather
  // than dashed when the build has no target date (the strip's own rule).
  if (text(detail.target_activation) !== null) {
    tiles.push({
      id: "target",
      label: t("customers.build.fact.target", { defaultValue: "Target" }),
      value: (
        <DateCell
          value={detail.target_activation as string}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      ),
    });
  }

  const premisesId = detail.premises?.id ?? null;
  const orderIds = detail.work_orders.map((order) => order.id);

  return (
    <>
      <Facts id="work" tiles={tiles} />
      {premisesId === null ? (
        // ⚠ **REFUSED BY NAME AND NOT DRAWN EMPTY** (`BR-SHL-025`). The shared
        // list is `GET /premises/{id}/work-orders`; a build whose address has
        // not resolved yet (`DEF-CUS-6109`) has no premises to read it from,
        // and an empty table would say *no work here* about a build that may
        // have plenty.
        <Section id="work" title={t("customers.build.work.title", { defaultValue: "Work orders" })}>
          <p className="text-sm text-neutral-700" data-build-empty="work">
            {t("customers.build.work.noPremises", { defaultValue: "No address yet." })}
          </p>
        </Section>
      ) : (
        <WorkOrdersTab
          host="build"
          // The PREMISES id — the shared route's own key. See `WorkOrdersTab`'s
          // docstring: there is no `GET /connections/{id}/work-orders`, and
          // `onlyOrderIds` is what narrows the address's list to this build.
          hostId={premisesId}
          onlyOrderIds={orderIds}
          t={t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          openOrderId={openOrderId}
          onOpenOrder={setOpenOrderId}
          client={props.client}
        />
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-151-BRC09 §2 rule (2) · `03-work.png` (B14 rule 42)
// generated: 2026-09-28 by the DEF-CUS-7618 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// gates: G93 proved RED through run_gates.py (never __main__ — DEF-GOV-3733)
//   on TEN findings, not the six CR-151-BRC09 §6c wrote down: nine panels
//   declared outside their home by the detail-page lane, and `BuildTiles` in
//   the New connects LIST, which is a sibling's and is DEF-CUS-7622. Green
//   once all nine lived in this kit and this tab composed the shared table.
//   G13 — every prop this passes is read.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
