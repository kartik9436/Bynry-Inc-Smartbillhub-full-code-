// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 6 — the Overview tab. MOVED here from
//           `features/customers/BuildDetailTabs.tsx:160` by `DEF-CUS-7618`,
//           unchanged in what it renders.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/01-overview.png`
// Rules:    B14 rule 20 (one table type) · rule 31 (no database id is a
//           visible value) · rule 33 (RATIONALE is ZERO WORDS ON SCREEN) ·
//           rule 43 · CLAUDE.md hard rule 2 (money displays at 2 from the
//           SERVER's one rounding) · hard rule 8 (an address is WALKED to)
// Tests:    src/features/customers/BuildDetailTabs.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS NOT A COMPOSITION OF `buildViews.BuildTab`
// ══════════════════════════════════════════════════════════════════════════
// `BuildTab` is the build RECORD — blueprint p098–p107, four panels (live
// state, owner and scope, premise, provenance) under a header and the five
// record tiles — and the premises page and the account page both mount it. It
// answers *what is this build made of*. `01-overview.png` answers a different
// question in a different shape: five facts, then WHAT THIS BUILD MADE as one
// table whose every row opens the real thing, then Outstanding and What
// happens next side by side. Mounting `BuildTab` here would put the record's
// own tab inside a tab of the same page — the re-hosting wave-O judgment (2)
// names — and would not draw one row of the drawing.
//
// What IS composed: the shell's `Section` and `Facts`, `PlainTable` (B14 rule
// 20's one table type), `MoneyOrReason` and `AbsentValue` from the shared
// vocabulary, and every link through the module's own path builder.
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { DateCell } from "@/components/DateCell";
import type { KpiTile } from "@/components/KPIStrip";
import { PlainTable } from "@/components/Surfaces";
import { accountDetailPath } from "@/features/customers/customersShared";
import { AbsentValue, MoneyOrReason } from "@/features/customers/newConnectShared";
import { premisesDetailPath } from "@/features/metering/meteringShared";

import { todoSummary } from "./BuildTodoTab";
import { Facts, Section, text } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

export function BuildOverviewTab(props: BuildTabProps) {
  const { t, detail, record } = props;
  const tiles: KpiTile[] = [];
  const scope = text(record?.owner_and_scope.scope);
  const mode = text(record?.owner_and_scope.mode ?? detail.mode);
  const waiting = text(detail.waiting_on);

  if (scope !== null) {
    tiles.push({
      id: "scope",
      label: t("customers.build.fact.scope", { defaultValue: "Scope" }),
      // ⚠ **THE STORED VALUE IS A CODE** (`new_premise`) and free text on the
      // server by design, so an unrecognised value falls through to ITSELF —
      // what a clerk typed is a truer answer than a missing translation.
      value: t(`customers.newConnect.scope.${scope}`, { defaultValue: scope }),
    });
  }
  if (mode !== null) {
    tiles.push({
      id: "mode",
      label: t("customers.build.fact.mode", { defaultValue: "Mode" }),
      value: t(`customers.newConnect.mode.${mode}`, { defaultValue: mode }),
    });
  }
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
  if (waiting !== null) {
    tiles.push({
      id: "waiting",
      label: t("customers.build.fact.waitingOn", { defaultValue: "Waiting on" }),
      value: waiting,
    });
  }
  if (text(detail.started_at) !== null) {
    tiles.push({
      id: "started",
      label: t("customers.build.fact.started", { defaultValue: "Started" }),
      value: (
        <DateCell
          value={detail.started_at as string}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      ),
    });
  }

  return (
    <>
      <Facts id="overview" tiles={tiles} />
      <WhatThisBuildMade {...props} />
      <div className="grid gap-4 lg:grid-cols-2">
        <OutstandingSection {...props} />
        <WhatHappensNextSection {...props} />
      </div>
    </>
  );
}

/** WHAT · HOW MANY · NAMED · STATE, and every NAMED cell opens the real thing.
 *
 *  ⚠ **THE COUNTS ARE FACTS AND ARE NOT LINKS TO A COPY OF THE THING** — the
 *  drawing's own arrangement, and the reason the money row names the bill and
 *  not a second charges table. */
function WhatThisBuildMade(props: BuildTabProps) {
  const { t, detail, record, path } = props;
  const rows: {
    id: string;
    what: string;
    many: ReactNode;
    named: ReactNode;
    state: ReactNode;
  }[] = [];

  const ownerName = text(record?.header.owner_name);
  const accountNo = text(detail.owner_account_no ?? record?.money.billed_to);
  if (ownerName !== null || accountNo !== null) {
    rows.push({
      id: "customer",
      what: t("customers.build.made.customer", { defaultValue: "Customer" }),
      many: ownerName === null ? null : 1,
      named:
        ownerName === null ? (
          <AbsentValue reason={t("customers.build.absent.noOwner", { defaultValue: "No owner named yet." })} />
        ) : (
          ownerName
        ),
      state: null,
    });
    rows.push({
      id: "account",
      // ⊕ `CR-164-BRC10` wave 4 — a single-family owner's account says which
      // it is: it holds the home, or only pays (PO 2026-10-03). The same two
      // phrases step 5 used before Create.
      what:
        record?.owner_and_scope.owner_account_role === "lives_there"
          ? t("customers.newConnect.creates.ownerAccountLivesThere.what")
          : record?.owner_and_scope.owner_account_role === "billing_only"
            ? t("customers.newConnect.creates.ownerAccountBillingOnly.what")
            : t("customers.build.made.account", { defaultValue: "Account" }),
      many: accountNo === null ? null : 1,
      named:
        accountNo === null ? (
          <AbsentValue reason={t("customers.build.absent.noAccount", { defaultValue: "No account yet." })} />
        ) : props.accountId === null ? (
          // ⚠ **THE NUMBER WITHOUT A LINK, RATHER THAN A LINK TO NOWHERE.**
          // A link built from an id nobody served passes every assertion in
          // this repository and opens onto nothing (hard-won law 6).
          <span data-account-no={accountNo}>{accountNo}</span>
        ) : (
          <Link to={path(accountDetailPath(props.accountId))} data-account-no={accountNo}>
            {accountNo}
          </Link>
        ),
      state: null,
    });
  }

  if (detail.premises !== null) {
    rows.push({
      id: "premises",
      what: t("customers.build.made.premises", { defaultValue: "Premises" }),
      many: 1,
      named: (
        <Link
          to={path(premisesDetailPath(detail.premises.id))}
          data-premise-no={detail.premises.premise_no}
        >
          {text(detail.premises.name) ?? detail.premises.premise_no}
        </Link>
      ),
      state: null,
    });
  }

  rows.push({
    id: "units",
    what: t("customers.build.made.units", { defaultValue: "Units" }),
    many: detail.units,
    named: detail.unit_rows.map((unit) => unit.label).join(", ") || null,
    state:
      record === null ? null : (
        <span className="tabular-nums">
          {t("customers.build.counted", {
            done: record.tiles.activated.done,
            total: record.tiles.activated.total,
            defaultValue: `${record.tiles.activated.done} of ${record.tiles.activated.total}`,
          })}
        </span>
      ),
  });

  rows.push({
    id: "orders",
    what: t("customers.build.made.orders", { defaultValue: "Work orders" }),
    many: detail.orders.total,
    named: null,
    state: (
      <span className="tabular-nums">
        {t("customers.build.counted", {
          done: detail.orders.done,
          total: detail.orders.total,
          defaultValue: `${detail.orders.done} of ${detail.orders.total}`,
        })}
      </span>
    ),
  });

  const invoiceNo = text(record?.money.invoice_no);
  rows.push({
    id: "charges",
    what: t("customers.build.made.charges", { defaultValue: "One-time charges" }),
    many: (
      <MoneyOrReason
        money={record?.money.quoted ?? detail.quote_total}
        reason={t("customers.build.absent.notPriced", { defaultValue: "Nothing priced yet." })}
      />
    ),
    // ⚠ **THE BILL NUMBER, AS TEXT.** `money` carries no invoice id, so the
    // document is reached through the account rather than by a link this
    // screen would have to invent (B14 rule 31 forbids the id anyway).
    named: invoiceNo,
    state: (
      <MoneyOrReason
        money={record?.money.outstanding}
        reason={t("customers.build.absent.notPriced", { defaultValue: "Nothing priced yet." })}
      />
    ),
  });

  return (
    <Section
      id="made"
      title={t("customers.build.made.title", { defaultValue: "What this build made" })}
    >
      <PlainTable data-table="build-made">
        <thead>
          <tr>
            <th>{t("customers.build.made.col.what", { defaultValue: "What" })}</th>
            <th>{t("customers.build.made.col.howMany", { defaultValue: "How many" })}</th>
            <th>{t("customers.build.made.col.named", { defaultValue: "Named" })}</th>
            <th>{t("customers.build.made.col.state", { defaultValue: "State" })}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-made-row={row.id}>
              <td>{row.what}</td>
              <td className="tabular-nums">{row.many}</td>
              <td>{row.named}</td>
              <td>{row.state}</td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </Section>
  );
}

/** `BR-MET-114` — human-authored, never derived, and it blocks nothing. */
function OutstandingSection(props: BuildTabProps) {
  const { t, detail } = props;
  return (
    <Section
      id="outstanding"
      title={t("customers.build.outstanding.title", { defaultValue: "Outstanding" })}
    >
      {/* CR-162-BRC10 (Q3) — the Overview's one-line summary of the To-do
          tab, linking to it. Notes are not counted: they are never "open". */}
      {todoSummary(detail.outstanding.length, t) !== null && (
        <p className="m-0 mb-2 text-sm font-semibold" data-todo-summary="">
          <Link to="?tab=todo">{todoSummary(detail.outstanding.length, t)}</Link>
        </p>
      )}
      {detail.outstanding.length === 0 ? (
        <p className="text-sm text-neutral-700" data-build-empty="outstanding">
          {t("customers.build.outstanding.none", { defaultValue: "Nothing is outstanding." })}
        </p>
      ) : (
        <PlainTable data-table="build-outstanding">
          <thead>
            <tr>
              <th>{t("customers.build.outstanding.col.what", { defaultValue: "What" })}</th>
              <th>{t("customers.build.outstanding.col.detail", { defaultValue: "Detail" })}</th>
            </tr>
          </thead>
          <tbody>
            {detail.outstanding.map((todo) => (
              <tr key={todo.id} data-outstanding-row="">
                <td>{todo.title}</td>
                <td>{text(todo.detail)}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Section>
  );
}

/**
 * WHEN · WHAT · WHERE — the two dates this build actually has ahead of it.
 *
 * ⚠ **TWO ROWS AND NOT THE DRAWING'S TWO EXAMPLES.** The target activation is
 * served; a bill's due date is NOT (`money` carries no due date), so the money
 * row appears only when there is something to say and never as a dash.
 */
function WhatHappensNextSection(props: BuildTabProps) {
  const { t, detail, path } = props;
  const rows: { id: string; when: ReactNode; what: string; where: ReactNode }[] = [];
  if (text(detail.target_activation) !== null) {
    rows.push({
      id: "activation",
      when: (
        <DateCell
          value={detail.target_activation as string}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      ),
      what: t("customers.build.next.activation", { defaultValue: "Service starts" }),
      where:
        detail.premises === null ? null : (
          <Link to={path(premisesDetailPath(detail.premises.id))}>
            {t("customers.build.made.premises", { defaultValue: "Premises" })}
          </Link>
        ),
    });
  }
  return (
    <Section id="next" title={t("customers.build.next.title", { defaultValue: "What happens next" })}>
      {rows.length === 0 ? (
        <p className="text-sm text-neutral-700" data-build-empty="next">
          {t("customers.build.next.none", { defaultValue: "No date is set." })}
        </p>
      ) : (
        <PlainTable data-table="build-next">
          <thead>
            <tr>
              <th>{t("customers.build.next.col.when", { defaultValue: "When" })}</th>
              <th>{t("customers.build.next.col.what", { defaultValue: "What" })}</th>
              <th>{t("customers.build.next.col.where", { defaultValue: "Where" })}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} data-next-row={row.id}>
                <td>{row.when}</td>
                <td>{row.what}</td>
                <td>{row.where}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-150-BRC09 task 6 · `01-overview.png` (B14 rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane; MOVED into the kit the same
//   day by the DEF-CUS-7618 lane, with no change to what it renders
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
