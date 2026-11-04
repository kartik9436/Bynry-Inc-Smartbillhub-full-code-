// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 — `ACC-T11`, the Notes tab against its drawing
//           (B14 rule 41, PO 2026-09-13: the product matches the blueprint).
// Story:    US-CUS-011 · screen S21, tab `ACC-T11`.
// Rules:    BR-CUS-035 (customers OWNS `account_notes`; `customer_visible` is
//           captured and inert) · BR-AUD-003 (a pin is a server write and an
//           audit row) · BR-SHL-025 (a forbidden control keeps its reason) ·
//           BR-SHL-034 (one date formatter) · B14 rule 15 (row actions are
//           icons) · rule 16 (every list table carries the pagination footer) ·
//           rule 19 (the search prompt names what it matches) · rule 20 (one
//           table type) · rule 21 (Tailwind utilities; this file adds NO class
//           to a stylesheet and is listed in `styles/route-b-migrated.txt`) ·
//           rule 31 (no database id on screen) · rule 33 (on-screen text is
//           capped by what it is for) · rule 36 (compose the kit) · rule 39
//           (the spacing scale).
// ───────────────────────────────────────────────────────
// ⚠ **THE DRAWING, QUOTED RATHER THAN LINKED** — `ACC-T11`, from
// `04-docs/05-modules/03-customers/blueprint/02-account-detail.md` and
// transcribed in `conformance/CR-094-lane2-account-detail-step1.md` §1.5:
//
//   toolbar  `All` `Pinned` `Collections` `Customer-visible` `Search` · `Add note`
//   body     a pinned card, then `WHEN ▼` · `WHO` · `KIND` · `NOTE` · row
//            actions (pin, `…`)
//
// **IT IS BUILT AS DRAWN**, and the three differences are stated here rather
// than made quietly:
//
//  1 · ⚠ **THE CHIPS ARE THE KIT'S `[All] [chip ×] [+ Filter ▾]`, NOT FOUR
//      SEGMENTED BUTTONS.** The drawing carries r10's older segmented row;
//      `DEF-442` and `DEF-1700` both ruled on that control — a screen that
//      wants a dimension DECLARES it in `TableConfig.filters` and the shared
//      bar draws it. B14 rule 38 settles which side wins when a drawing and
//      the UI rules disagree about how a control is BUILT: the UI rules. What
//      the drawing decides is WHICH dimensions exist, and both that it can
//      offer are here.
//
//  2 · ⛔ **`Collections` IS NOT OFFERED, AND THAT IS AN ABSENCE RATHER THAN AN
//      OVERSIGHT.** `Collections`, `Field visit` and `Agreement` are a note
//      KIND, and `account_notes` has no kind column — checked on the wire
//      (`apps/customers/models.py::AccountNote`), not inferred from the
//      TypeScript. A chip that can only ever empty the list is a dead control
//      (hard-won law 2). Filed as a defect; the `KIND` column IS drawn, saying
//      what is true of every row today.
//
//  3 · ⛔ **NO `Filter ▾` MENU BEYOND THOSE TWO AND NO `Export`.** `GET
//      /accounts/{id}/notes` serves one unfiltered, unpaginated set, so the
//      sort, the search and the page are worked out here over what it sent —
//      the same shape metering's `AuditTab` uses for the same reason. `POST
//      /exports` resolves only the resources a module REGISTERS and nothing
//      registers account notes, so a download button here would be wired to a
//      404 (`BR-SHL-010`).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountNotes, updateAccountNote } from "@/api/endpoints";
import type { AccountNote } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { PinIcon, PinOffIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { RefusalStrip } from "@/components/Surfaces";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { tabMatches, tabRowsForPage } from "@/features/metering/PremisesDetailPage";
import { apiErrorText } from "@/features/tenancy/settingsShared";

// ⚠ **THE QUERY KEY IS IMPORTED, NEVER RESTATED.** A first draft of this file
// declared its own `["account-notes", id]` — and `AccountDetailPage` invalidates
// `accountNotesKey(detail.id)` after the Add-note modal saves, which is
// `["accounts", "notes", id]`. Two keys for one list means the tab does not
// refresh when a note is added: every test passes, the note is in the database,
// and the clerk sees the list they were already looking at. Hard-won law 2's
// shape, and the reason B14 rule 36 says compose rather than copy.
import { accountNotesKey } from "./AccountActions";
import { AccountNoteCards } from "./accountDetailTabs";
import { NotRecorded } from "./customersShared";

/** The screen id `TableConfig` keys its column preference on — S21's tab, so a
 *  clerk's chosen columns survive leaving the account and coming back. */
const NOTES_TABLE_SCREEN = "S21.notes";

/** The one muted tone this screen already uses, written the way every other
 *  feature file writes it. */
const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** The two dimensions the served row can actually answer. `Collections` is the
 *  third the drawing asks for and it has no column — see the header. */
const VIEW_PINNED = "pinned";
const VIEW_CUSTOMER_VISIBLE = "customer_visible";

export function notesTableConfig(
  t: Translate,
  cells: {
    when: (row: AccountNote) => JSX.Element;
    actions: (row: AccountNote) => JSX.Element;
  },
): TableConfig<AccountNote> {
  return {
    screenId: NOTES_TABLE_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["title", "body", "author_name"],
    // B14 rule 19 — the prompt names WHAT the box matches, and this one is
    // true: the match runs over the note's words and its author and nothing
    // else.
    searchPlaceholder: "customers.account.note.search",
    filters: [
      {
        name: "view",
        label: t("customers.account.note.col.kind"),
        options: [
          { value: VIEW_PINNED, label: t("customers.account.note.pinnedPill") },
          {
            value: VIEW_CUSTOMER_VISIBLE,
            label: t("customers.account.note.customerVisiblePill"),
          },
        ],
      },
    ],
    // The drawing sorts `WHEN ▼` — newest first, which is also the order the
    // server sends (pinned first, then newest) and the order a clerk reads a
    // history in.
    defaultSort: { sort: "when", dir: "desc" },
    columns: [
      {
        key: "when",
        identity: true,
        sortable: true,
        label: t("customers.account.note.col.when"),
        cell: cells.when,
      },
      {
        key: "who",
        label: t("customers.account.note.col.who"),
        // BR-CUS-035: a note with no author is a SYSTEM note — named, never
        // blanked, the same sentence the card above the table uses.
        cell: (row) => <span>{row.author_name ?? t("customers.account.note.systemAuthor")}</span>,
      },
      {
        key: "kind",
        label: t("customers.account.note.col.kind"),
        // ⚠ **DRAWN, AND HONEST ABOUT BEING EMPTY.** `account_notes` has no
        // kind column, so every row says so rather than being blank (a blank
        // reads as *nobody knows*) or inventing `Collections` for a note
        // nobody classified. The tooltip is six words, B14 rule 33's cap for a
        // fact.
        cell: () => (
          <NotRecorded
            label={t("customers.account.note.kindAbsent")}
            why={t("customers.account.note.kindAbsentWhy")}
          />
        ),
      },
      {
        key: "note",
        label: t("customers.account.note.col.note"),
        cell: (row) => (
          <span className="block">
            {row.title !== null && row.title !== "" && (
              <span className="block font-semibold">{row.title}</span>
            )}
            {row.body !== null && row.body !== "" && <span className="block">{row.body}</span>}
          </span>
        ),
      },
      {
        key: "actions",
        label: t("customers.account.note.col.actions"),
        cell: cells.actions,
      },
    ],
  };
}

/**
 * `ACC-T11` — the Notes tab.
 *
 * ⚠ **PINNED NOTES ARE CARDS ABOVE THE TABLE AND THE TABLE HOLDS THE REST**,
 * which is what the drawing shows: one `📌 Pinned` panel, then `WHEN ▼ · WHO ·
 * KIND · NOTE`. The drawn footer reads `1–4 of 4` over three rows; B14 rule 37
 * makes a drawn FIGURE an illustration, so the pager counts what is in the
 * table and the cards are counted where they are.
 */
export function AccountNotesTab(props: {
  accountId: string;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** `null` = this role may write. Anything else disables the controls and
   *  becomes their tooltip (`BR-SHL-025`). */
  addReason: string | null;
  onAdd: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();

  const notesQuery = useQuery({
    queryKey: accountNotesKey(props.accountId),
    queryFn: () => getAccountNotes(props.accountId, client),
    retry: false,
  });

  // US-CUS-015's lifecycle half. The write goes through the SERVER's own state,
  // never a local toggle: the list is invalidated and re-read, so a note that
  // failed to pin cannot appear pinned.
  const setPinned = useMutation({
    mutationFn: (vars: { noteId: string; pinned: boolean }) =>
      updateAccountNote(props.accountId, vars.noteId, { pinned: vars.pinned }, client),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: accountNotesKey(props.accountId) });
    },
  });

  const config = useMemo(
    () =>
      notesTableConfig(translate, {
        when: (row) =>
          row.created_at === null ? (
            <span />
          ) : (
            <DateCell
              value={row.created_at}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              withTime
            />
          ),
        actions: (row) => (
          <RowActions>
            <RowAction
              icon={row.pinned ? <PinOffIcon /> : <PinIcon />}
              label={
                row.pinned ? t("customers.account.note.unpin") : t("customers.account.note.pin")
              }
              reason={props.addReason}
              working={setPinned.isPending && setPinned.variables?.noteId === row.id}
              onClick={() => setPinned.mutate({ noteId: row.id, pinned: !row.pinned })}
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, props.timeZone, props.dateFormat, props.addReason, setPinned.isPending, setPinned.variables?.noteId],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const all: readonly AccountNote[] = notesQuery.data ?? [];
  const pinnedCards = all.filter((note) => note.pinned);

  // The served set is unfiltered and unpaginated (see the header), so the
  // dimension, the search, the sort and the page are all worked out here over
  // what arrived — `AuditTab`'s shape, for the same reason.
  const wanted = state.filters.view ?? "";
  const filtered = all.filter((note) => {
    if (wanted === VIEW_PINNED) {
      if (!note.pinned) return false;
    } else if (wanted === VIEW_CUSTOMER_VISIBLE) {
      if (!note.customer_visible) return false;
    } else if (note.pinned) {
      // No dimension chosen: the pinned notes are the CARDS above, so the
      // table holds the rest. Choosing `Pinned` brings them into the table,
      // which is how a clerk sees them in the same columns as everything else.
      return false;
    }
    return tabMatches([note.title, note.body, note.author_name], state.q);
  });
  const sorted = [...filtered].sort((a, b) => {
    const dir = state.dir === "desc" ? -1 : 1;
    return (a.created_at ?? "").localeCompare(b.created_at ?? "") * dir;
  });
  const rows = tabRowsForPage(sorted, state);

  return (
    /* `data-account-overview` and the per-group `data-overview-group` hook are
       what the BROWSER census selects on (`10-scripts/render-checks/
       acc02-tab-conformance.mjs`): jsdom computes no layout, so no vitest case
       in this repo can say the screen LOOKS like the drawing. One column on
       this tab, because the drawing gives it one. */
    <div data-account-overview="">
      <div className="flex min-w-0 flex-col">
        <Panel
          as="section"
          tone="group"
          data-overview-group="notes"
          data-screen={NOTES_TABLE_SCREEN}
          title={t("customers.account.tab.notes")}
          /* The drawing makes `Add note` the tab's own control. It is a
             SECONDARY here: the page header already carries this screen's one
             primary (`Record payment`, BR-SHL-044 / B14 rule 4), the same
             choice the Documents and Adjustments tabs beside it make. */
          trailing={
            <Button
              variant="secondary"
              onClick={props.onAdd}
              disabled={props.addReason !== null}
              title={props.addReason ?? undefined}
            >
              {t("customers.account.action.addNote")}
            </Button>
          }
        >
          {notesQuery.isError ? (
            <RefusalStrip role="alert">
              {apiErrorText(notesQuery.error, (key, params) => t(key, params))}
            </RefusalStrip>
          ) : (
            <>
              {pinnedCards.length > 0 && (
                <div className="mb-4">
                  <AccountNoteCards
                    notes={pinnedCards}
                    t={translate}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                    renderAction={(note) => (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setPinned.mutate({ noteId: note.id, pinned: false })}
                        disabled={props.addReason !== null}
                        title={props.addReason ?? undefined}
                      >
                        {t("customers.account.note.unpin")}
                      </Button>
                    )}
                  />
                </div>
              )}
              <DataTable<AccountNote>
                config={config}
                filterBarSlot={
                  <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
                }
                state={state}
                onStateChange={setState}
                rows={rows}
                totalRows={sorted.length}
                loading={notesQuery.isPending}
                error={null}
                empty={{
                  title: t("customers.account.note.empty"),
                  helper: t("customers.account.note.emptyHelper"),
                  ctaLabel: t("customers.account.action.addNote"),
                  ctaReason: props.addReason,
                  ctaVariant: "secondary",
                  onCta: props.onAdd,
                }}
              />
              {/* ⚠ **THE FACT, WITHOUT THE REASON FOR IT** (B14 rule 33, PO
                  sweep 2026-09-13). This line used to carry 35 words ending
                  *"…there is no rule yet on whether the original wording stays
                  visible to the next person who reads it"* — that is RATIONALE
                  and is zero words on screen. Why the control is absent is
                  `OQ-225`, and it lives in the register and in this comment. */}
              <p className={`m-0 mt-3 text-sm ${MUTED}`}>
                {t("customers.account.note.editTextNotOffered")}
              </p>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}

export default AccountNotesTab;

// ── Lifecycle ─────────────────────────────────────────────
// generated: 2026-09-13 by the ACC-02 conformance lane (tabs Documents · Notes
//            · Audit, plus the rule 33 sweep)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
