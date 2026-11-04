// ── Trace ──────────────────────────────────────────────
// Story:    US-NOT-014 (bounces + returned mail)   Screens: S8 (Settings →
//           Notifications → Blocked addresses)
// Rules:    B14 rule 21 (Tailwind utilities, no stylesheet class — this file is
//           on `route-b-migrated.txt`) · rule 31 (no database id is the visible
//           value of a field) · rule 32 (description budget) · rule 33 (on-screen
//           text is capped by what it is FOR; RATIONALE is zero words on screen)
//           · rule 35 (eleven catalogues, each in its own idiom) · rule 36 (the
//           shared kit is how you comply with r10's visual style) · rule 39 (a
//           field is label → input → helper) · BR-SHL-010 (only declared
//           capabilities render) · BR-SHL-011 (list grammar) · BR-SHL-020
//           (plain-language failure) · BR-SHL-025 (a control this deployment
//           cannot honour renders DISABLED WITH ITS REASON) · BR-TEN-043 (a
//           business date is a PARAMETER — the browser is the caller and states
//           the day) · `NFR-3` (universal server pagination)
// Change:   DEF-NOT-5637, 2026-09-17 — the API was served and there was no
//           screen, so the Release the Product Owner asked for by name could
//           only be performed by an engineer.
// Tests:    07-frontend/src/features/notifications/BlockedAddresses.test.tsx ·
//           06-backend/tests/test_def_not_5637_blocked_addresses.py
// Impacts:  SettingsNotificationsTab.tsx (the fifth sub-tab — the DOOR)
// ───────────────────────────────────────────────────────
// SETTINGS → NOTIFICATIONS → BLOCKED ADDRESSES: WHO WE MUST NOT SEND TO, AND
// THE ONE WAY BACK.
//
// ── THERE IS NO BLUEPRINT FOR THIS SCREEN, AND THAT WAS CHECKED ───────────
// B14 rules 41/42 say a screen is built from its drawing AS AN IMAGE where one
// exists, and `DEF-GOV-5248` is ten days of a lane building to the wrong
// reference because nobody looked. Every ref in this repository was searched at
// `668a8507` and carries EIGHT blueprint PDFs — Assets, Accounts, Meter Reads,
// Billing, Integration, Premises & Units, Customer Portal, Plans & Rates. **None
// of them is Notifications**, and the two that mention the word *suppress* mean
// *suppresses its page header*. So rule 36's other half governs: the shared
// component kit and `r10`'s `UI-RULES.md` are the whole of the visual authority
// here, and this screen is the settings sub-tab pattern its four siblings
// already use rather than a shape invented for it.
//
// ⚠ **THE SEARCH COMMAND `CLAUDE.md` PRESCRIBES CANNOT SEE ALL EIGHT** —
// `git ls-tree -r --name-only <ref> | grep -i 'pdf$'` misses the Meter Reads
// blueprint, because git QUOTES a path holding a non-ASCII character (its name
// has an em dash) and the line then ends with `"` rather than `pdf`. Filed as
// `DEF-GOV-5656` rather than left in this docstring; `-c core.quotePath=false`
// is the fix, and it is the difference between finding seven drawings and
// finding eight.
//
// ── WHAT THIS SCREEN REFUSES TO DO ────────────────────────────────────────
//  1. **It never renders a suppression's id** (B14 rule 31). The id travels on
//     every row because Release is keyed on it; the clerk sees the ADDRESS,
//     which is the thing they recognise and the thing the table is keyed by.
//  2. **It never filters rows in the browser.** The list is paginated in the
//     database and grows for ever — a released row is KEPT as history — so a
//     reason chip that narrowed the PAGE would answer *no complaints* for a
//     utility whose complaints are all on page two. That is hard-won law 7's
//     *reporting zero over a scope it silently excludes*, wearing a filter chip,
//     and it is why `f.reason` was added to the server in the same commit.
//  3. **It never hides a released row.** The row is the durable answer to *why
//     did this customer stop getting email in March* and outlives `audit_log`'s
//     retention pruning. Hiding it would leave the record with no reader.
//  4. **It offers NO search box and NO sortable column**, because the server
//     offers neither `q` nor an honoured `sort`. A search field over an endpoint
//     that ignores it is dead UI that looks alive (hard-won law 2), which is the
//     exact defect this screen exists to close in reverse.
//  5. **It offers no way to ADD an address by hand.** `REASON_MANUAL` is a
//     lawful value with no writer anywhere in the product, so an empty state
//     with a `+ Block address` button would open onto nothing. The empty block
//     therefore draws no CTA at all (`DEF-MET-4764`'s shape).
//
// ── WHY THE REASONS ARE NOT ONE WORD ──────────────────────────────────────
// `suppression_models.py` argues it and the screen obeys it: a hard bounce is a
// mistyped or dead address a clerk can FIX, a complaint is a person who does not
// want the mail, and an unsubscribe is a person who pressed a button we gave
// them. Folding them into one *blocked* would make the one screen built to
// explain this unable to. The chips are built from the SERVER's vocabulary, so a
// reason that gains a writer appears here without a screen edit.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { getSuppressions, releaseSuppression } from "@/api/endpoints";
import type { SuppressionRow } from "@/api/endpoints";
import { refusalText } from "@/api/refusalText";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { RollBackIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { Note } from "@/components/TextBits";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { todayIso } from "@/features/billing/billingOpsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";

import { MUTED, REASON_CLAMP, TABLE_SCROLL } from "./notificationsKit";

/** The `:sub` segment that opens this tab. Same reserved-value mechanism as
 *  `MESSAGES_SUB` / `RIGHTS_SUB` / `SENDER_SUB` and safe on the same proof —
 *  every other value of `:sub` is a `rule_catalog` event key, and none of the
 *  thirty this product ships is called `blocked`. `TAB_SUBS` is the ONE list
 *  both the guard and the strip read; a segment missing from it falls through
 *  to the rule page and renders an empty screen. */
export const BLOCKED_SUB = "blocked";

/** The screen id, for the column preference and for the door assertion.
 *
 *  ⚠ **`SET-12<letter>` IS THIS MODULE'S EXISTING FAMILY, NOT A NEW SCHEME.**
 *  `SET-12` is r10's badge for Settings → Notifications and `SET-12D` has named
 *  the rule-detail sub-surface in 46 places since `CR-009`. Neither is a row in
 *  `screenIds.ts` — the visible bottom-right badge comes from the ROUTE table,
 *  and these four sub-tabs share one route — so this is a marker a test and a
 *  walkthrough can hold on to, exactly as `SET-12D` is, and G29 does not read
 *  it. Said out loud so the next reader does not take it for an allocated
 *  badge (hard-won law 1: a marker claiming an allocation it does not have). */
export const BLOCKED_SCREEN_ID = "SET-12B";

/**
 * ONE page of the list, keyed by the request that produced it.
 *
 * The state and the reason are IN the key, deliberately: *active hard bounces*
 * and *every complaint we have ever had* are different questions and must never
 * answer each other out of cache.
 */
export const blockedAddressesKey = (state: string, reason: string, page: number, per: number) =>
  ["notifications", "suppressions", state, reason, page, per] as const;

/**
 * The `f.state` this screen sends when no state chip is applied.
 *
 * ⚠ **IT IS `all` AND NOT THE SERVER'S DEFAULT, AND THAT IS THE WHOLE POINT.**
 * `GET /suppressions` defaults to ACTIVE when `f.state` is absent, and the
 * toolbar's *All* chip means *nothing is filtered*. Left alone the two would
 * disagree: a clerk clicking **All** would read a chip saying *no filter* over a
 * list quietly still showing only the active rows, with no chip anywhere able to
 * say why the released ones were missing. Sending `all` explicitly makes the
 * chip's word and the list's contents the same fact.
 */
const NO_STATE_CHIP = "all";

/** What the screen lands on: the work, not the archive. */
const LANDS_ON = "active";

/** A reason code → the clerk's word for it, in their language.
 *
 *  ⚠ THE FALL-BACK IS NOT DECORATION (B14 rule 31). The options come from the
 *  SERVER's vocabulary, so a reason that gains a writer tomorrow arrives here
 *  with no screen edit — and with no catalogue key. Rendering the raw code
 *  would put an internal value on screen, which rule 31 forbids by name, so an
 *  unknown reason reads as *Other reason* until its key lands. */
export function reasonLabel(t: Translator, code: string): string {
  return t(`notifications.blocked.reason.${code}`, {
    defaultValue: t("notifications.blocked.reason.other"),
  }) as string;
}

/** Same shape, same reason, for the channel half of the key. The keys are the
 *  delivery queue's own (`notifications.queue.channel.*`) rather than a second
 *  copy of them — one vocabulary, one home. */
export function channelLabel(t: Translator, code: string): string {
  return t(`notifications.queue.channel.${code}`, {
    defaultValue: t("notifications.blocked.channel.other"),
  }) as string;
}

/**
 * Can THIS row be released, and if not, why not — in a sentence a clerk reads.
 *
 * Pure, exported and tested directly: it is the whole of the enable/disable
 * decision, and `BR-SHL-025` requires the reason to travel with the refusal
 * rather than leaving an unexplained grey button. The server refuses a second
 * release for its own reasons; this is the half that tells the clerk BEFORE they
 * press, which is the difference between a control that is off and a control
 * that is broken.
 */
export function releaseRefusal(row: SuppressionRow, t: Translator): string | null {
  if (row.state === "released") {
    return t("notifications.blocked.alreadyReleased");
  }
  return null;
}

/** The date is REQUIRED and is never defaulted silently (BR-TEN-043). */
export function releaseSchema(t: Translator) {
  return z.object({
    released_on: z.string().min(1, t("notifications.blocked.release.dateRequired")),
  });
}

// ══ The Release door ═══════════════════════════════════════════════════════

/**
 * Let this address through again — the control the Product Owner asked for by
 * name, and the reason this screen exists.
 *
 * ⚠ **EASY TO FIND, HARD TO DO BY ACCIDENT, AND THOSE PULL IN OPPOSITE
 * DIRECTIONS.** A hard bounce is most often a TYPO, so Release is the repair
 * path and burying it would leave a real customer with no email for ever. It is
 * therefore a row action on every active row, one click from the list — and the
 * click opens THIS, which names the address, states what resumes, and takes a
 * date and a note before it commits. Nothing is released by a single press.
 *
 * ⚠ **NO DANGER TIER, AND THAT IS A DECISION RATHER THAN AN OMISSION.** B14
 * rule 6's tier is for a DESTRUCTIVE commit — disconnect, retire, reverse,
 * write-off. A release destroys nothing: the row is kept and stamped, and what
 * it changes is that a customer starts receiving their bill again. Painting the
 * repair path in the colour the product uses for *this cannot be undone* would
 * teach a clerk to hesitate over the one action they are meant to take.
 */
export function ReleaseAddressModal(props: {
  row: SuppressionRow;
  /** The clerk's business day, proposed into the field and always overridable. */
  proposedDate: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  client?: ApiClient;
  onClose: () => void;
  onReleased: (address: string) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [releasedOn, setReleasedOn] = useState("");
  const [note, setNote] = useState("");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await releaseSuppression(
        props.row.id,
        releasedOn,
        // An empty box is NO note, not an empty one: `released_note` is nullable
        // precisely so *nobody said anything* stays distinguishable from *they
        // said nothing*, which is the `unavailable_reason` discipline one table
        // over.
        note.trim() === "" ? null : note.trim(),
        props.client ?? api,
      );
      props.onReleased(props.row.address);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("notifications.blocked.release.title")}
      /* The ADDRESS is the kicker and never the id (B14 rule 31): it is what the
         clerk recognises, and a dialog that named a uuid would be asking them to
         confirm something they cannot read. */
      kicker={props.row.address}
      schema={releaseSchema(translate)}
      values={{ released_on: releasedOn }}
      submitLabel={t("notifications.blocked.release.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* B14 rule 33's CONSEQUENCE kind: two sentences, six words each at most,
          stated BEFORE the act. Both are facts about what changes — what resumes
          and what goes out — and neither explains why the product works this
          way, because RATIONALE is zero words on screen. */}
      <p className="m-0 mb-3 text-md leading-body">
        {t("notifications.blocked.release.consequence")}
      </p>
      <DatePickerField
        id="released_on"
        label={t("notifications.blocked.release.dateLabel")}
        value={releasedOn}
        onChange={setReleasedOn}
        prefill={props.proposedDate}
        dateFormat={props.dateFormat}
        required
        help={t("notifications.blocked.release.dateHelp")}
      />
      <TextField
        id="released_note"
        label={t("notifications.blocked.release.noteLabel")}
        value={note}
        onChange={setNote}
        help={t("notifications.blocked.release.noteHelp")}
      />
    </FormModal>
  );
}

// ══ The list ═══════════════════════════════════════════════════════════════

export interface BlockedAddressesProps extends RegionalProps {
  readOnly: boolean;
  client?: ApiClient;
  /** Today, for the release date's prefill. Overridable so a test can pin it. */
  today?: string;
}

export function BlockedAddressesTab(props: BlockedAddressesProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const toast = useToast();
  const { timeZone, dateFormat } = useRegional(props);
  const [releasing, setReleasing] = useState<SuppressionRow | null>(null);
  const [tableState, setTableState] = useState<TableRequestState>({
    q: "",
    sort: "suppressed_at",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    // The screen lands on the WORK. A released address is history and a clerk
    // opening this tab came to act on something.
    filters: { state: LANDS_ON },
  });

  const stateFilter = tableState.filters.state ?? NO_STATE_CHIP;
  const reasonFilter = tableState.filters.reason ?? "";
  const query = useQuery({
    queryKey: blockedAddressesKey(stateFilter, reasonFilter, tableState.page, tableState.per),
    queryFn: () =>
      getSuppressions(
        {
          page: tableState.page,
          per: tableState.per,
          // Both narrow in SQL. See this file's header for what a browser-side
          // version of this line would cost.
          filters: { state: stateFilter, ...(reasonFilter === "" ? {} : { reason: reasonFilter }) },
        },
        client,
      ),
    retry: false,
  });

  const vocabulary = query.data?.vocabulary;
  const config: TableConfig<SuppressionRow> = {
    screenId: BLOCKED_SCREEN_ID,
    getRowId: (row) => row.id,
    // No `searchFields` and no `sortable` column anywhere: the server offers
    // neither, and a control over a capability the endpoint does not have is
    // dead UI that looks alive. `defaultSort` names the order the SERVER
    // actually applies, so the state this screen holds is a true statement.
    defaultSort: { sort: "suppressed_at", dir: "desc" },
    filters: [
      {
        name: "state",
        label: t("notifications.blocked.col.state"),
        // TWO options and not three: *all* is the toolbar's own All chip, and
        // offering it twice would give a clerk two controls that mean one thing
        // and can disagree about which is applied.
        options: [
          { value: "active", label: t("notifications.blocked.state.active") },
          { value: "released", label: t("notifications.blocked.state.released") },
        ],
      },
      {
        name: "reason",
        label: t("notifications.blocked.col.reason"),
        // FROM THE SERVER, never a copy of the tuple. The view serves
        // `vocabulary.reasons` with the list for exactly this, so a reason that
        // gains a writer appears as a chip with no screen edit.
        options: (vocabulary?.reasons ?? []).map((code) => ({
          value: code,
          label: reasonLabel(translate, code),
        })),
      },
    ],
    columns: [
      {
        key: "address",
        label: t("notifications.blocked.col.address"),
        // The identity column — what a clerk recognises, and never the id.
        identity: true,
        // ⚠ **WRAPPED, NEVER TRUNCATED, AND SIZED SO IT USUALLY DOES NOT HAVE
        // TO WRAP.** The whole point of this column is that a clerk reads the
        // address closely enough to spot the typo — `whitfeild` against
        // `whitfield` — and an ellipsis hides exactly the character that is
        // wrong. 17rem holds a typical consumer address on one line at
        // `--table-font-size`; a longer one wraps rather than being cut.
        cell: (row) => <span className="block min-w-[17rem] break-all">{row.address}</span>,
      },
      {
        key: "channel",
        label: t("notifications.queue.col.channel"),
        // ⚠ NOT DECORATION. The row is unique on (channel, address), so two
        // rows for one address on two channels are two different facts; without
        // this column they would read as a duplicate.
        cell: (row) => channelLabel(translate, row.channel),
      },
      {
        key: "reason",
        label: t("notifications.blocked.col.reason"),
        cell: (row) => (
          <span className="flex min-w-0 flex-col gap-0.5">
            <span>{reasonLabel(translate, row.reason)}</span>
            {/* The PROVIDER's own sentence, kept for the person who has to
                explain this to a customer. Their words, not ours — rule 33 caps
                the copy this product writes, and dropping this would hide what
                the server is being honest about. */}
            {row.reason_detail !== null && row.reason_detail !== "" && (
              <span className={`${MUTED} ${REASON_CLAMP} block text-sm`}>{row.reason_detail}</span>
            )}
          </span>
        ),
      },
      {
        key: "suppressed_at",
        label: t("notifications.blocked.col.blockedOn"),
        cell: (row) => (
          <DateCell value={row.suppressed_at} timeZone={timeZone} dateFormat={dateFormat} />
        ),
      },
      {
        key: "state",
        label: t("notifications.blocked.col.state"),
        cell: (row) => (
          <StatusPill tone={row.state === "released" ? "neutral" : "warning"}>
            {row.state === "released"
              ? t("notifications.blocked.state.released")
              : t("notifications.blocked.state.active")}
          </StatusPill>
        ),
      },
      {
        key: "released_at",
        label: t("notifications.blocked.col.released"),
        // ⚠ THE HISTORY HALF, AND IT IS WHY THE ROW IS KEPT. A release stamps
        // the row rather than deleting it, so that *why did this customer stop
        // getting email in March* survives `audit_log`'s retention pruning. A
        // column that showed only the date would answer WHEN and lose WHY.
        cell: (row) =>
          row.released_at === null ? (
            <span className={MUTED}>—</span>
          ) : (
            <span className="flex min-w-0 flex-col gap-0.5">
              {/* ⚠ **THE CALENDAR DATE, NOT THE INSTANT — AND THE TWO DIFFER BY
                  A DAY FOR EVERY NORTH AMERICAN TENANT.** A release is dated by
                  the CLERK (`BR-TEN-043`) and the server anchors that day to
                  midnight UTC purely to store it, exactly as the returned-mail
                  path does. Handing the whole timestamp to `DateCell` would
                  render midnight UTC in the tenant's own zone — 03/04 typed in
                  Chicago comes back 03/03 — which `formatDate`'s own comment
                  names as the mistake it exists to prevent (`BR-SHL-023`: a
                  calendar date is the same calendar date in every tenant).
                  Slicing to `YYYY-MM-DD` takes the timezone-free path.
                  `suppressed_at` above is NOT sliced, deliberately: that one is
                  a real instant — the moment a provider told us — and an
                  instant always displays in tenant time. */}
              <DateCell
                value={row.released_at.slice(0, 10)}
                timeZone={timeZone}
                dateFormat={dateFormat}
              />
              {row.released_note !== null && row.released_note !== "" && (
                <span className={`${MUTED} ${REASON_CLAMP} block text-sm`}>
                  {row.released_note}
                </span>
              )}
            </span>
          ),
      },
      {
        key: "actions",
        label: t("notifications.queue.col.action"),
        cell: (row) => {
          const refused = releaseRefusal(row, translate);
          return (
            <RowActions>
              <RowAction
                icon={<RollBackIcon />}
                label={t("notifications.blocked.release.action")}
                testId={`release-${row.address}`}
                // BR-SHL-025 — a control this clerk cannot use says why, on
                // itself, rather than greying out and leaving them guessing.
                reason={
                  props.readOnly ? t("settings.readOnlyReason") : (refused ?? undefined)
                }
                onClick={() => setReleasing(row)}
              />
            </RowActions>
          );
        },
      },
    ],
  };

  return (
    <div data-screen={BLOCKED_SCREEN_ID} data-testid="blocked-addresses" className="flex flex-col gap-4">
      {/* ⚠ NO TITLE AND NO DESCRIPTION PARAGRAPH HERE. The sub-tab strip already
          names this screen and B14 rule 32 gives a screen ONE sentence per
          section; the two notes at the foot are the section's whole budget and
          each is a FACT rather than an explanation. */}
      <div className={TABLE_SCROLL}>
        <DataTable<SuppressionRow>
          config={config}
          state={tableState}
          onStateChange={setTableState}
          rows={query.data?.results ?? []}
          totalRows={query.data === undefined ? null : query.data.count}
          loading={query.isPending}
          error={
            query.isError
              ? { reason: refusalText(translate, query.error), onRetry: () => void query.refetch() }
              : null
          }
          empty={{
            title: t("notifications.blocked.emptyTitle"),
            helper: t("notifications.blocked.emptyHelper"),
            // ⚠ NO CTA, DELIBERATELY. Nothing in this product writes a
            // suppression by hand, so a button here would open onto nothing —
            // the live half of hard-won law 2.
          }}
          filterBarSlot={
            <FilterBar
              filters={config.filters ?? []}
              state={tableState}
              onStateChange={setTableState}
            />
          }
        />
      </div>
      {/* Two FACTS, each ≤ 6 words (B14 rule 33). Not why the product works this
          way — that is in this file and in the register. */}
      <Note>{t("notifications.blocked.paperStillGoes")}</Note>
      <Note>{t("notifications.blocked.releasedRowsKept")}</Note>
      {releasing !== null && (
        <ReleaseAddressModal
          row={releasing}
          proposedDate={props.today ?? todayIso()}
          dateFormat={dateFormat}
          client={client}
          onClose={() => setReleasing(null)}
          onReleased={(address) => {
            setReleasing(null);
            toast(t("notifications.blocked.release.done", { address }));
            // The released row STAYS in the list, restamped — so the list is
            // refetched rather than having the row spliced out of it. A screen
            // that removed the row on success would hide the record the release
            // exists to leave behind.
            void queryClient.invalidateQueries({ queryKey: ["notifications", "suppressions"] });
          }}
        />
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-NOT-5637 (12-governance/10-defect-log.csv) · apps/notifications/suppression_models.py + suppression.py + api.py (`suppressions`, `suppression_release`) · 04-docs/02-decisions/14-ui-conventions.md rules 21/31/32/33/35/36/39/41/42 · 05-prototype/r10-2026-08-16/UI-RULES.md
// generated: 2026-09-17 by an AI lane (the blocked-addresses screen)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (BlockedAddresses.test.tsx — every case proved RED FIRST against a named sabotage, quoted in the lane report) · G31 SKIPS this file because it is on `route-b-migrated.txt`, and `routeBUtilities.test.ts` owns it instead and asks the stricter question
// exceptions: (1) NO BLUEPRINT EXISTS FOR THIS SCREEN — every ref was searched and the eight PDFs on the branch are Assets, Accounts, Meter Reads, Billing, Integration, Premises & Units, Customer Portal and Plans & Rates. Stated out loud because B14 rule 41's default is that the drawing is the scope, and a lane that finds no drawing must say so rather than leave the next reader wondering whether it looked. (2) NO SEARCH BOX AND NO SORTABLE COLUMN — `GET /suppressions` offers neither `q` nor an honoured `sort`, and a control over a capability the endpoint does not have is dead UI (law 2). (3) NO WAY TO BLOCK AN ADDRESS BY HAND — `REASON_MANUAL` is a lawful value with no writer anywhere in the product, so the empty state draws no CTA. (4) NOTHING WRITES A SUPPRESSION AUTOMATICALLY ON THIS DEPLOYMENT: `BR-NOT-013` holds and no provider adapter with a feedback door exists, so on a live tenant this list is empty until one lands. The READ and RELEASE halves are wired from this commit.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
