// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-041 (EP-INT-11) — S142 *Who has been reading*, and the
//           subprocessor register's row pointing inward (TC-8).
//           **`ACC-01` (Integration Blueprint p99–p101, DRAWN TO THE RULES)**
//           is what this is built to since 2026-09-16 — heading, grey subtitle
//           under it, THREE separate read states, the table, and the WATCH
//           quote. It supersedes frame 46.2's amber box and single sentence.
// Rules:    BR-INT-035 (who, when, how many, under which key — and the key is
//           a HINT) · B14 rule 15 (row actions are icons; there are none here)
//           · rule 20 (one table type) · rule 21 (Tailwind only; this file is
//           on route-b-migrated.txt) · rule 31 (no database id is a visible
//           value) · rule 32 (one sentence per section; a stated absence is
//           CLOSED by default) · rule 33 (five or six words) · rule 36 (the
//           captured pack gives layout, r10 gives the visual style, and the
//           SHARED KIT is how you comply)
// Tests:    src/features/integrations/AccessLogPanel.test.tsx ·
//           10-scripts/render-checks/cr069-s-partner-morning.mjs
// Impacts:  src/features/integrations/ConnectionDetailPage.tsx (mounts it) ·
//           src/api/integrationsEndpoints.ts (two reads) · the eleven locale
//           catalogues (`integrations.access.*`)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS PANEL WAS REDRAWN TO `ACC-01` ON 2026-09-16 (`CR-110-BRC04`,
// `DEF-INT-5484`).** The Integration Blueprint p99–p101 draws it as
// *ACC-01 · Who has been reading — a panel inside the connection view*,
// stamped DRAWN TO THE RULES, and B14 rule 41 says the product matches the
// blueprint. Four of its elements moved:
//
//   ① **LOADING** — `LoadingSkeleton`, the kit's own state, while the read is
//      in flight. The legend's DATA column names the component and the field
//      by hand: *"logQuery.isLoading — already available, unread"*.
//   ② **EMPTY** — *"Nobody has read anything"* over *"This partner has a key
//      and has not used it."*, drawn ONLY when the read succeeded.
//   ③ **FAILED** — *"The access log did not load"* over *"We cannot say
//      whether anybody has read anything."*, with **Retry**.
//   ⑥ the subtitle *An access log, not a run history* is PLAIN GREY TEXT
//      UNDER the heading. It shipped as a bordered warning-tone tag floated
//      right of the title, which reads as a badge on a security panel.
//   ⑨ the **WATCH** block is a QUOTE WITH A LEFT RULE, not a filled tan box.
//
// ⚠ **①②③ ARE ONE DEFECT AND IT IS THE REASON THE SCREEN EXISTS.** Until this
// commit ONE sentence — *"Nobody has collected anything yet."* — covered all
// three states, and it is the reassuring one. Confirmed in a browser on
// 2026-09-16 against `erp_aclarian` on `brazosbend`: the panel's text was
// byte-identical while the read was in flight, after a 500, and on a
// connector with no reads at all. The blueprint's own words, p101: *"A
// security screen that says 'all clear' when its request failed is worse than
// one that shows nothing — a reader who sees a blank table goes looking; a
// reader who sees 'Nobody has collected anything yet.' stops."* Nothing could
// see it: the sentence IS in the DOM, so every `toContain` passed; `G122`
// asks this exact question and its declared subject is `<FactList` screens,
// which this is not.
//
// ⚠ **THE FAILED BLOCK IS COMPOSED HERE AND IS NOT `FailedWithRetry`, AND
// THAT IS A DECISION RATHER THAN AN OVERSIGHT.** The kit's component requires
// `onDownloadReport` and `onCancel`, and 98 of its 102 call sites pass
// `() => undefined` to the first — a live button that downloads nothing. On a
// panel INSIDE a page "Cancel" cancels nothing either, and ACC-01 draws
// exactly ONE button. Drawing three where the blueprint draws one, two of
// them inert, is hard-won law 2's mirror on the one screen whose job is to
// raise an alarm. So the BLOCK is the drawing's and the BUTTON is the kit's
// (`Button`, `states.failed.retry` — the product's one word for it), which is
// what B14 rule 36 asks for. The kit gap is filed, not worked around:
// `DEF-INT-5562`.
//
// ⚠ **THE WATCH BLOCK IS RATIONALE AND B14 RULE 33 SAYS RATIONALE IS ZERO
// WORDS ON SCREEN. IT IS DRAWN ANYWAY, DELIBERATELY, AND THE CONFLICT IS
// FILED AS `OQ-INT-12394`.** Rule 41 names precisely this case — *"the only
// thing that reaches the PO is a drawing that contradicts a signed rule"* —
// and p100 is stamped DRAWN TO THE RULES, so its author has already weighed
// them. Removing a block the blueprint draws, on this lane's own reading of
// rule 33, would be resolving that silently in the other direction. It ships
// as drawn and the question is open.
//
// ⚠ **THE TWO FOOT BUTTONS (④) ARE STILL NOT DRAWN, AND NOW FOR A MEASURED
// REASON RATHER THAN A WAVE BOUNDARY.** *Revoke the key* already has a door
// on this very page: `ConnectionDetailPage`'s `ManagePanel` draws the keys
// table and a `Keys` link a few hundred pixels above this panel, and revoke
// lives there behind a `ConfirmDialog` that spells out the consequence and
// lets a clerk choose WHICH key. A second danger-tier control here would be
// two destructive doors onto one act on one screen (B14 rule 4). *Allowed
// addresses* has no endpoint and no screen — the blueprint's own legend says
// so, *"the revoke endpoint exists; the allowlist one does not"* — so the
// button would open onto nothing. Both absences are STATED (B14 rule 32); the
// allowlist half is filed as `DEF-INT-5564` and the revoke half is a judgment
// recorded in `12-governance/02-decision-log.md`, not left to be rediscovered.
//
// ⚠ **THE PANEL DECIDES WHETHER TO DRAW ITSELF FROM `operations`, NEVER FROM A
// PROVIDER KEY.** `direction === "out" && initiative === "them"` is the SERVE
// quadrant, the same pair `runners.runner_for()` reads on the server. A
// `provider === "gl_partner"` test would be the branch `G77` fails a gate on,
// and it would go quietly wrong the day a second partner manifest is registered.
//
// ⚠ `integrations.access.kicker` KEEPS ITS NAME though it is now a subtitle.
// Renaming it is eleven catalogue edits and a retire, for no reader; the words
// did not move, the element did.

import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccessLog, getSubprocessors } from "@/api/integrationsEndpoints";
import type { AccessLogRow, OperationRow, SubprocessorRow } from "@/api/integrationsEndpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { EmptyList, LoadingSkeleton } from "@/components/StateFrame";
import type { RegionalDateFormat } from "@/components/DateCell";

/** How many rows the section draws before it says how many more there are.
 *  Frame 46.2 draws four; twenty keeps a morning's collections visible without
 *  the section running off the screen. */
const SHOWN = 20;

/** The newest `SHOWN` rows UNION every unusual one, in time order.
 *
 *  ⚠ **A PLAIN `slice(0, SHOWN)` WOULD RE-INTRODUCE THE BUG THE SERVER WAS
 *  JUST FIXED FOR.** The 48,000-row collection is OLDER than a hundred small
 *  reads, so cutting by time alone drops the one row this screen exists for —
 *  which is exactly how a partner would hide it. Unusual rows are kept
 *  whatever their age. */
export function visibleRows(rows: AccessLogRow[]): AccessLogRow[] {
  const keep = new Set<AccessLogRow>(rows.slice(0, SHOWN));
  for (const row of rows) if (row.unusual) keep.add(row);
  return rows.filter((one) => keep.has(one));
}

export interface AccessLogPanelProps {
  providerKey: string;
  operations: OperationRow[];
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The one seam a test replaces (G13: the only optional prop is the client). */
  client?: ApiClient;
}

/** Does anything on this connection point INWARD? The SERVE quadrant, read off
 *  the operations the server already sends — never off the provider's name. */
export function readsFromUs(operations: OperationRow[]): boolean {
  return operations.some((one) => one.direction === "out" && one.initiative === "them");
}

/** One row of frame 46.2. The unusual one is emphasised and nothing else about
 *  it changes — it is not a warning, it is a row worth looking at twice. */
function AccessRow(props: { row: AccessLogRow; timeZone: string; dateFormat: RegionalDateFormat }) {
  const { row } = props;
  const emphasis = row.unusual ? "font-semibold text-neutral-900" : "text-neutral-800";
  return (
    <tr
      className="border-b border-neutral-200 last:border-b-0"
      data-access-row={row.what}
      data-unusual={row.unusual ? "true" : "false"}
    >
      <td className="py-2 pr-4 align-top text-table text-neutral-600">
        <DateCell value={row.when} timeZone={props.timeZone} dateFormat={props.dateFormat} withTime />
      </td>
      <td className={`py-2 pr-4 align-top text-table ${emphasis}`}>
        {row.what}
        {/* ⚠ *WHO*, AND IT WAS MISSING. `BR-INT-035` records a read "under
            which key", and the first draft of this row drew only when · what ·
            how many — so the screen called *Who has been reading* did not say
            who. Frame 46.2 has three columns, so the hint goes under the
            window text rather than becoming a fourth (B14 rule 36: the
            captured pack gives the layout). Found by clicking, not by a test. */}
        {row.hint !== null && (
          <span className="block font-mono text-xs text-neutral-600" data-access-hint={row.hint}>
            {row.hint}
          </span>
        )}
      </td>
      <td className={`py-2 text-right align-top text-table tabular-nums ${emphasis}`}>
        {row.rows.toLocaleString()}
      </td>
    </tr>
  );
}

/** The register's rows, as SENTENCES. A person reads this to answer *who else
 *  touches our customers' data*, so the sentence is the content and the fields
 *  beside it are only what a table sorts on. */
function RegisterRows(props: { rows: SubprocessorRow[] }) {
  const { t } = useTranslation();
  if (props.rows.length === 0) return null;
  return (
    <div className="flex flex-col gap-2" data-register="">
      <h3 className="font-heading text-table-header uppercase tracking-table-header text-neutral-600">
        {t("integrations.access.register.title")}
      </h3>
      <ul className="flex flex-col gap-1">
        {props.rows.map((row) => (
          <li
            key={`${row.party}-${row.direction}`}
            className="text-table text-neutral-800"
            data-register-row={row.direction}
          >
            {row.sentence}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AccessLogPanel(props: AccessLogPanelProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const enabled = readsFromUs(props.operations);

  const logQuery = useQuery({
    queryKey: ["integrations", "access-log", props.providerKey],
    queryFn: () => getAccessLog(client, props.providerKey),
    enabled,
  });
  const registerQuery = useQuery({
    queryKey: ["integrations", "subprocessors"],
    queryFn: () => getSubprocessors(client),
    enabled,
  });

  // Nothing reads from this connection, so there is nothing to show and no
  // empty box drawn where a box would never fill (hard-won law 2 wearing a
  // layout — the same reasoning ConnectionDetailPage's foot note gives).
  if (!enabled) return null;

  const all = logQuery.data?.items ?? [];
  const rows = visibleRows(all);
  const hidden = all.length - rows.length;
  const inward = (registerQuery.data ?? []).filter((one) => one.direction === "inward");

  return (
    <section className="flex flex-col gap-3" data-access-log={props.providerKey}>
      {/* ACC-01's head — the title, and the subtitle UNDER it in plain grey.
          It shipped as a bordered warning-tone tag floated right, which on a
          security panel reads as a badge rather than as the sentence it is. */}
      <div className="flex flex-col gap-1" data-access-head="">
        <h2 className="font-heading text-lead font-semibold text-neutral-900">
          {t("integrations.access.title")}
        </h2>
        <p className="text-sm text-neutral-600" data-access-subtitle="">
          {t("integrations.access.kicker")}
        </p>
      </div>

      {/* ⚠ **THREE STATES, IN THIS ORDER, AND THE ORDER IS THE FIX.** Pending
          is asked FIRST because `logQuery.data` is `undefined` while a read is
          in flight and an `items.length === 0` test cannot tell that from an
          answer of nothing. Error is asked SECOND for the same reason. Only
          when the read has come back, and come back successfully, may the
          panel say anything about what the partner has done — which is the
          whole of `DEF-INT-5484`. Tests: the three-state case asserts these
          produce three DIFFERENT strings. */}
      {logQuery.isPending ? (
        // ① The kit's own loading state (the blueprint's legend names it).
        <LoadingSkeleton variant="table" rows={6} />
      ) : logQuery.isError ? (
        // ③ What we cannot say, and the one act that can change it.
        <div
          role="alert"
          data-access-failed=""
          className="flex flex-col items-start gap-2 border-l-2 border-danger-500 pl-3"
        >
          <p className="text-table font-semibold text-neutral-900">
            {t("integrations.access.failed.title")}
          </p>
          <p className="text-table text-neutral-600">
            {t("integrations.access.failed.reason")}
          </p>
          {/* The kit's Button and the product's one word for this act. ONE
              button, because ACC-01 draws one — see the header note. */}
          <Button variant="secondary" size="sm" onClick={() => void logQuery.refetch()}>
            {t("states.failed.retry")}
          </Button>
        </div>
      ) : rows.length === 0 ? (
        // ② A read that SUCCEEDED and returned nothing. The second line is a
        // claim about the PARTNER, which only a successful read supports — and
        // it is what makes this state impossible to confuse with the other two.
        // No `ctaLabel`: a clerk cannot make a partner read, so the block
        // offers nothing rather than a control that cannot act.
        <EmptyList
          title={t("integrations.access.empty.title")}
          helper={t("integrations.access.empty.helper")}
        />
      ) : (
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-neutral-300">
              <th className="py-2 pr-4 font-heading text-table-header uppercase tracking-table-header text-neutral-600">
                {t("integrations.access.column.when")}
              </th>
              <th className="py-2 pr-4 font-heading text-table-header uppercase tracking-table-header text-neutral-600">
                {t("integrations.access.column.what")}
              </th>
              <th className="py-2 text-right font-heading text-table-header uppercase tracking-table-header text-neutral-600">
                {t("integrations.access.column.rows")}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <AccessRow
                key={`${row.when}-${index}`}
                row={row}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            ))}
          </tbody>
        </table>
      )}

      {hidden > 0 && (
        <p className="text-xs text-neutral-600" data-access-more={hidden}>
          {t("integrations.access.more", { count: hidden })}
        </p>
      )}

      {/* ⑨ ACC-01 draws this as a QUOTE WITH A LEFT RULE, not the filled tan
          `ConsequenceBox` that shipped. A consequence box is what the product
          puts in front of an irreversible act; this is a standing note about
          why the panel is here, and the drawing gives it the quieter shape.
          ⚠ It is RATIONALE, which B14 rule 33 puts at zero words on screen —
          the conflict is real, it is `OQ-INT-12394`, and the header says which
          way this lane went and why. */}
      <blockquote className="border-l-2 border-neutral-300 pl-3" data-access-watch="">
        {/* ⚠ THE `uppercase` IS ON THE TAG ALONE. Put it on the line and the
            title comes out "WHY THIS SCREEN EXISTS", which ACC-01 draws in
            sentence case — caught in a browser, not by a test (law 6). */}
        <p className="text-sm text-neutral-600">
          <span className="text-xs font-bold uppercase tracking-tag text-neutral-800">
            {t("integrations.access.note.tag")}
          </span>
          {" · "}
          {t("integrations.access.note.title")}
        </p>
        <p className="text-table text-neutral-800">{t("integrations.access.note.body")}</p>
      </blockquote>

      <RegisterRows rows={inward} />
    </section>
  );
}

// ── Lifecycle ────────────────────────────────────────────────────────────
// packet: US-INT-041@wave-S (EP-INT-11) · frame 46.2 · 10-execution-plan.md wave S task S2
// generated: 2026-09-06 by the CR-069 wave S build lane (integrations half) · REDRAWN 2026-09-16 to `ACC-01` (Integration Blueprint p99–p101) by the CR-110-BRC04 access-log lane — three read states where one sentence covered all three (`DEF-INT-5484`), the subtitle under the heading, the WATCH block as a quote
// checklist: A✔ B✔ C✔ D✔(GET /integrations/{key}/access-log · /integrations/subprocessors) E✔(mounted from ConnectionDetailPage) F✔ G✔ H=n/a
// gates: tsc · vitest · G13 (the one optional prop is the client seam) · G31 (Tailwind only; on route-b-migrated.txt — `routeBUtilities.test.ts` compiles every class) · G77 (no provider_key branch — the quadrant is read off `operations`) · G15/G18 (the four new keys are in all eleven catalogues through `i18n_fanin.py`; `integrations.access.empty` retired, it had no call site left)
// exceptions: ACC-01's two foot buttons are NOT drawn — `Revoke the key` already has a door on this same page (`ManagePanel`'s keys table and Keys link, where revoke carries its ConfirmDialog and lets a clerk pick WHICH key) and `Allowed addresses` has no endpoint, which the blueprint's own legend states; both absences are STATED — the allowlist half filed as `DEF-INT-5564`, the revoke half a judgment in the decision log · the failed block is composed here rather than `FailedWithRetry`, whose two further required handlers are dead controls on an inline panel and which ACC-01 does not draw (`DEF-INT-5562`) · the WATCH block is rationale, which B14 rule 33 forbids on screen and ACC-01 draws anyway — shipped as drawn, conflict open as `OQ-INT-12394`
// status: VERIFIED-UNRATIFIED
// ─────────────────────────────────────────────────────────────────────────
