// ── Trace ──────────────────────────────────────────────
// Story:    CR-007 (SET-09 the template catalog · SET-10 the template detail,
//           preview, variant management, editing and versioning — DRAWN)
//           Screens: SET-09 · SET-10
// Rules:    BR-NOT-001 (variants + a mandatory default fallback) · BR-NOT-006
//           (type × category × language) · BR-NOT-014 (three disconnect slots,
//           one per stage) · BR-NOT-015 (the rights footer's sentences are not
//           ours to invent — OQ-250) · BR-BIL-026 (an edit is a NEW version) ·
//           BR-BIL-027 (System Admin publishes) · BR-SHL-011 (list grammar) ·
//           BR-SHL-013 (column visibility) · BR-SHL-020 (plain-language
//           failure) · BR-SHL-025 (a forbidden control renders DISABLED WITH
//           ITS REASON, never hidden) · BR-TEN-033 (templates are
//           notifications', not tenancy's) · B14 rules 5 · 12 · 13 · 14 · 15 ·
//           16 · 17 · 18 · 19 · 20
// ───────────────────────────────────────────────────────
// SETTINGS → CONFIGURE → TEMPLATES: EVERYTHING THIS UTILITY SENDS OR PRINTS.
//
// CR-007's own statement of purpose is drawn at the top of the screen because
// it is the distinction people get wrong: **Notifications decide WHEN,
// Templates define WHAT.** Nothing on this screen schedules, triggers or sends.
//
// ── WHAT THIS REPLACED, AND WHAT IT DID NOT ───────────────────────────────
// This sub-tab used to render `BillLayoutTab` alone — billing's five ready-made
// bill layouts and a chooser (PO 2026-08-16, the designer cut).
//
// ⚠ **THE SENTENCE THAT USED TO END THIS PARAGRAPH IS SUPERSEDED, 2026-08-30
// (CR-048 task E9, `BR-NOT-026`).** It read: *"this catalog deliberately does
// not list them, so the bill layout keeps its own panel below the catalog
// rather than being folded into a table that cannot serve it. One document, one
// home."* **The PO ruled otherwise**, verbatim: *"Yes, Go with option B; I
// agree"* — a person opens Templates ONCE and sees both kinds in one list. So
// this catalog DOES list them now, and the chooser is the EDITOR a bill row
// opens rather than a second panel underneath.
//
// **"One document, one home" survives and is better served**: it was the reason
// for the DEF-212 (4) guard in `SettingsPage`, which switched the sibling panel
// off while a template detail was open. One component renders now, so only one
// editor can be open at a time and the guard is gone with the condition that
// needed it. What did NOT change is the DATABASE: bills still pin billing's own
// registry (B2 r10 #4) and no row moved — see `unified_templates.py`.
//
// ── THE THREE CONTROLS THAT RENDER DISABLED, AND WHY EACH IS DIFFERENT ─────
// BR-SHL-025 forbids hiding a control somebody cannot use, and each of these
// carries the SERVER's own sentence rather than one composed here — a screen
// that worded the reason itself would drift from the ruling the moment either
// changed:
//   · **Send test to me** — there is no dispatcher on any channel in R2 and the
//     PO declined the resend-invite action the same day with *"no email yet"*.
//   · **Download sample PDF** — the platform's page writer is billing's and it
//     writes bills; a printable NOTICE renders TEXT (OQ-149).
//   · **Set default** — the default variant is the row's KEY, not a flag on it,
//     so setting another would re-key it and move every pin (OQ-252).
//
// ── WHAT THIS SCREEN REFUSES TO SAY ───────────────────────────────────────
//  1. **It never shows one blank cell for two different absences.** "Nobody has
//     written this letter" (`body_unavailable` — only a ruling fixes it) and
//     "nobody has defined this class's merge fields" (`catalog_unavailable`)
//     are different problems with different fixes, and DEF-163's whole finding
//     was that one blank for both sends a person to the wrong place.
//  2. **It never invents wording.** Where a template has no body the row says
//     so in the server's words with its OQ id, and the editor refuses the save.
//
// ══ DEF-211 · 2026-08-18 · THE TABLE IS THE SHARED ONE NOW ════════════════
// The browser walkthrough measured this screen against B14 rule by rule and
// found EIGHT of the twenty broken, with ONE root cause: the list was a
// `.settings-table` — B14's own words for that class are *"plain config
// tables (B9 rows declaring no table capabilities)"* — hand-rolled beside a
// hand-rolled sort, a hand-rolled column chooser and a hand-rolled pager. So
// rules 13 (sort cycle + indicator), 14 (column reset + reorder) and 16 (the
// pagination footer) were absent *at once*, which is exactly what B14's own
// priority order predicts. It rides `DataTable` (FE-02) now, and the three
// rules arrive with it instead of being written a second time here.
//
// ⚠ **THE PAGER STILL CANNOT DO ANYTHING, AND THE SCREEN SAYS SO.** Template
// CLASSES are platform vocabulary — 36 of them, and OQ-253 keeps a tenant from
// minting a thirty-seventh — while the standard page sizes start at 50. So
// there is exactly one page, forever, and both page buttons are permanently
// disabled. That is a true statement about this list rather than a bug in it,
// and printing it under the table is better than a footer a person keeps
// trying to use. Dropping the footer instead would break rule 16 to hide a
// consequence of rule 16.
//
// ══ CR-048 WAVE E · 2026-08-30 · E7 + E8 ══════════════════════════════════
//
// ⚠ **THE SEARCH BOX IS NO LONGER THIS SCREEN'S OWN, AND THE NOTE THAT SAID SO
// HAS EXPIRED.** It read: *"`DataTable`'s built-in search renders the shared
// placeholder 'Search this list' and B14 rule 19 asks for 'Search {entities}…'
// per module, so `searchFields` is deliberately NOT declared and the module's
// own labelled input rides in the filter slot instead. When `DataTable` grows a
// placeholder prop this collapses into it."* **It grew one** — `searchPlaceholder`,
// DEF-510 — so the reason for the local box is gone, and a comment claiming a
// reason is not the reason (hard-won law 1). The capability is declared, the
// local `input[type=search]` is deleted, and the toolbar has ONE box carrying
// the module's own prompt.
//
// ⚠ **AND THE SIX CATEGORY PILLS ARE GONE WITH IT (E8).** They were this
// screen's own `chip-<key>` buttons in the filter slot, drawing a dimension the
// config ALREADY declared as `f.category` — the exact duplication DEF-1700
// ruled away on Premises, Units and Reads (*"as per our stadard first raw of
// tookkit is more than suficient"*). The shared `FilterBar` draws it now: the
// `All` chip, a REMOVABLE chip per applied filter, and one `+ Filter ▾` panel
// (DEF-442). ⚠ Its `options` had to be FILLED to make that work — the config
// declared `options: []`, and `offerableFilters` DROPS a group with no options
// (DEF-782), so the dimension existed in configuration and rendered nothing.
//
// ⚠ **THE LIST IS GROUPED BY EVENT (E7).** *"'Bill ready · e-bill email' and
// 'Bill ready · SMS' sit apart as though unrelated. They are not."* The event
// is DERIVED from the seeded name — see `templateEvents.ts`, which records what
// the payload does not carry and why nothing here invents it — and the default
// sort moves from `category` to `name`, because `name` is the one server sort
// under which a run of surfaces is CONTIGUOUS.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { getTemplateCatalog } from "@/api/endpoints";
import type { TemplateCatalogRow } from "@/api/endpoints";
import { getTemplateLibrary, templateLibraryKey } from "@/api/templateLibraryEndpoints";
import type { TemplateLibraryRow } from "@/api/templateLibraryEndpoints";
import { BillLayoutTab } from "@/features/billing/BillLayoutTab";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { DataTable } from "@/components/DataTable";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { RefusalStrip } from "@/components/Surfaces";
import {
  Panel,
  PanelGrid,
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
} from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";

import { CopyIcon, EyeIcon, PencilIcon } from "@/components/icons";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { FilterBar } from "@/components/FilterBar";
import { languageName } from "@/portal/components/languageName";
import { DESC, NAME_CELL, PAGE_STACK } from "./notificationsKit";
import { eventRuns, siblingSurfaces, templateEvent, templateSurface } from "./templateEvents";
import { plainUsedBy } from "./TemplateDetail";
import { TemplateWorkspace } from "./TemplateWorkspace";
import { DisconnectRightsFooterCard } from "./DisconnectRightsFooterCard";
import { ChannelTag, TemplateChannelChips } from "./TemplateChannelChips";
import { WORKSPACE_DIALOG_PARAM, WORKSPACE_EDIT, WORKSPACE_MODE_PARAM } from "./templateWorkspaceParams";
import { Button } from "@/components/Button";

/** BR-SHL-011's URL grammar for SET-09, plus the two params SET-10 needs.
 *
 *  ⚠ **`?template=` IS THE ONE THAT PAYS FOR ITSELF** (DEF-212 (2)). Opening a
 *  template used to be component state, so a reload landed back on the catalog,
 *  the selected VARIANT was lost with it, and no walkthrough, ticket or
 *  hand-off could ever link to one template. The reference-data lists next door
 *  solved the same thing in CR-004 with `?list=<code>`. */
const TEMPLATE_PARAM = "template";
const VARIANT_PARAM = "variant";

/* ══ CR-048 E9 · 2026-08-30 · ONE TEMPLATES SCREEN, TWO STORES ═════════════
 *
 * PO ruling 2026-08-30, verbatim: *"Yes, Go with option B; I agree"*
 * (`BR-NOT-026`). A person opens Templates ONCE and sees the letters this
 * utility sends AND the layout its bills print on, in one list, filterable by
 * which kind they are.
 *
 * ⚠ **THIS TAB USED TO DRAW TWO LISTS.** The catalogue above, and billing's
 * bill-layout chooser in a panel underneath it — so *"the template we print
 * bills on"* was in the second list and you had to know that. The chooser is
 * not deleted and its rows did not move: it is now the EDITOR a bill row opens,
 * exactly as `TemplateDetailPanel` is the editor a notification row opens.
 *
 * ⛔ **AND THE TWO EDITORS ARE DELIBERATELY DIFFERENT.** The ruling asked for
 * one list and one lifecycle. It did not ask for one editor, because the two
 * kinds are not edited alike: a notification template is WORDS a person types
 * and checks against a merge-field palette; a bill template is a CHOICE among
 * five pre-built platform layouts with no body text at all. One editor for both
 * would be a text box over a layout key.
 *
 * ⛔ **AND THE TWO STORES ARE STILL TWO STORES.** `notification_templates` and
 * `bill_templates` both survive and no row moved — that is the ruling, not an
 * unfinished merge. See `apps/notifications/unified_templates.py`, whose
 * docstring carries it, and `test_cr048_e9_two_stores_one_screen.py`, which
 * goes red if a later lane "finishes" it.
 */

/** The URL prefix that says a row belongs to the OTHER store.
 *
 *  `?template=bill:<id>` rather than a second parameter, so BR-SHL-011's one
 *  grammar keeps working: a person can paste the link to a bill layout exactly
 *  as they paste the link to a disconnection notice, and `closeTemplate` needs
 *  to know about neither. */
const BILL_KEY_PREFIX = "bill:";

/** The dimension the list filters by. Named `template_kind` and NOT `kind`
 *  because this screen already has a `kind` COLUMN — the channel a message goes
 *  out on (Email · SMS · Print). Two different questions; one word between them
 *  would be a filter a person sets expecting the other answer. */
const KIND_FILTER = "template_kind";

/**
 * ONE ROW OF THE ONE LIST, whichever store it came from.
 *
 * ⚠ **A UNION AND NOT A WIDENED `TemplateCatalogRow`, ON PURPOSE.** Squeezing a
 * bill template into the catalogue's row shape would mean inventing a consumer
 * category, a variant count and a `used_by` sentence for a row that has none of
 * them — three fabricated cells that every test would pass over. Exactly one of
 * `note` and `bill` is ever set, so a cell that wants a field it cannot have
 * cannot compile.
 */
interface LibraryRow {
  templateKind: "notification" | "bill";
  /** `getRowId`, and the `?template=` value. */
  rowKey: string;
  name: string;
  /** Set iff `templateKind === "notification"`. On a COLLAPSED row this is the
   *  LEAD surface — the one the row's name opens. */
  note: TemplateCatalogRow | null;
  /** Set iff `templateKind === "bill"`. */
  bill: TemplateLibraryRow | null;
  /**
   * CR-048 wave I — THE SURFACES THIS ROW STANDS FOR.
   *
   * One entry for an ordinary notification row (itself), several for a
   * collapsed event, none for a bill row. Every aggregate cell below reads
   * this rather than guessing from the lead, so "3 variants" and "In use" are
   * statements about the whole event and not about whichever surface happened
   * to sort first.
   */
  members: readonly TemplateCatalogRow[];
}

function noteRow(row: TemplateCatalogRow): LibraryRow {
  return {
    templateKind: "notification",
    rowKey: row.code,
    name: row.name,
    note: row,
    bill: null,
    members: [row],
  };
}

function billRow(row: TemplateLibraryRow): LibraryRow {
  return {
    templateKind: "bill",
    rowKey: `${BILL_KEY_PREFIX}${row.key}`,
    name: row.name,
    note: null,
    bill: row,
    members: [],
  };
}

/**
 * CR-048 wave I — ONE ROW PER TEMPLATE, WITH A CONTROL PER SURFACE ON IT.
 *
 * The Product Owner's own design instruction, 2026-08-30, verbatim: *"past due
 * reminder - you created email SMS print, you can also do that by havng action
 * button for each type that way screen and table remain clean"*.
 *
 * *"Past-due reminder"* occupied THREE rows — Print, email, SMS — and *"Payment
 * receipt"* another three, *"Disconnect notice"* four, *"Payment plan"* three,
 * *"Bill ready"* two. Seventeen rows for five documents. They fold into five,
 * and the surface moves from being a ROW to being a CONTROL in the Kind column,
 * one click away exactly as it was.
 *
 * ⚠ **THIS ALSO ENDS THE DOUBLE NAME (the PO's first complaint), BY REMOVING
 * THE CASE THAT CAUSED IT.** Wave E's grouping drew the event as a heading line
 * and the row's own name under it; for a template that is its OWN event those
 * two lines are the same words, so the cell printed *"Account closed
 * confirmation"* twice, the second in accent colour. There is no heading line
 * any more — a collapsed row's NAME is the event, and an uncollapsed row's name
 * is its own full name. Nothing can be printed twice because nothing is printed
 * from two places.
 *
 * ⚠ **CONTIGUOUS RUNS ONLY, AND ONLY UNDER `name` ASCENDING** — the same guard
 * wave E's grouping carried and for the same reason: a run of surfaces is
 * adjacent only because the seeded names are `<event> · <surface>`, which makes
 * the event the sort prefix. Under any other sort this returns the flat list,
 * which is the screen as it was. The fallback of a derivation that cannot apply
 * is the OLD screen, never a wrong grouping.
 *
 * ⚠ **AND IT IS SAFE ONLY BECAUSE THIS LIST IS ONE PAGE.** Template classes are
 * platform vocabulary — 37 of them, and no tenant can mint a thirty-eighth —
 * while the smallest page size is 50. So every surface of every event is on the
 * page being folded. On a list that genuinely paged, a run split across a page
 * boundary would fold into two half-rows, and this function would be wrong; the
 * screen prints that one-page fact under the table already.
 */
export function collapseSurfaces(rows: readonly TemplateCatalogRow[]): LibraryRow[] {
  const runs = eventRuns(rows);
  const out: LibraryRow[] = [];
  for (let i = 0; i < rows.length; i += 1) {
    if (!runs[i].leads) {
      continue;
    }
    const members = rows.slice(i, i + runs[i].count);
    const lead = members[0];
    out.push({
      templateKind: "notification",
      rowKey: lead.code,
      // The EVENT when there is a run to name, the row's own name otherwise —
      // never `templateEvent()` of a single row, which for the 32 classes that
      // are their own event is the same string and would only look like a
      // derivation where there is none.
      name: members.length > 1 ? templateEvent(lead.name) : lead.name,
      note: lead,
      bill: null,
      members,
    });
  }
  return out;
}

/* ══════════════════════════════════════════════════════════════════════════
 * CR-199-BRC10 F1 · THE CHANNELS COLUMN (`01-list.png`)
 * ══════════════════════════════════════════════════════════════════════════
 *
 * One small tag per channel the row goes out on — *Email*, *Text*, *Letter*,
 * *In-app* — from each member's own `channel`, never parsed out of the `kind`
 * sentence. It replaces CR-048 wave I's icon column and keeps the one thing
 * that column did that a caption would not: **on a folded row every channel is
 * still one click away** (`CR-199-BRC10` §6 L9), so each tag of a two-channel
 * row is a button that opens that channel's template.
 *
 * `kind` is not lost: the server still sorts the column on it and the
 * workspace head still prints it.
 */
export function kindAtoms(kind: string): string[] {
  return kind
    .split(" + ")
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

/** A catalogue row's channel; a class with none stated is a printed one. */
function channelOf(member: TemplateCatalogRow): string {
  return member.channel ?? "pdf_print";
}

function ChannelsCell(props: { row: LibraryRow; onOpen: (code: string) => void }) {
  const { row } = props;
  const members = row.note === null ? [] : row.members;
  return (
    <span className="flex flex-col items-start gap-1" data-testid={`template-channel-${row.rowKey}`}>
      {members.length === 0 ? (
        <ChannelTag channel="pdf_print" />
      ) : members.length === 1 ? (
        <ChannelTag channel={channelOf(members[0])} />
      ) : (
        members.map((member) => (
          <ChannelTag
            key={member.code}
            channel={channelOf(member)}
            onOpen={() => props.onOpen(member.code)}
            testId={`template-surface-${member.code}`}
          />
        ))
      )}
    </span>
  );
}

/* ══ CR-199-BRC10 F1 · THE LANGUAGES COLUMN ═══════════════════════════════
 * Each of the utility's languages, written (accent) or *not written* (grey),
 * from the row's served `languages`. ⚠ **A ROW THE SERVER SERVES NO LANGUAGES
 * FOR SAYS NOTHING RATHER THAN GUESSING** — a list made up here would claim
 * wording exists that nobody wrote. On a folded row the languages are the
 * union over its channels: written if ANY channel has it written.
 *
 * ⚠ THE NAME IS `languageName(code)`, NOT A SERVER LABEL (DEF-NOT-10672). The
 * server serves the BCP-47 tag only: a language's own name is not a catalogue
 * line (B14 rule 35) and the server keeps no table of them, so a `label` it
 * served could only be the tag again. The workspace names languages the same
 * way. */
function LanguagesCell(props: { row: LibraryRow }) {
  const { t } = useTranslation();
  const merged = new Map<string, { label: string; written: boolean }>();
  for (const member of props.row.note === null ? [] : props.row.members) {
    for (const language of member.languages ?? []) {
      const seen = merged.get(language.code);
      merged.set(language.code, {
        label: languageName(language.code),
        written: (seen?.written ?? false) || language.written,
      });
    }
  }
  if (merged.size === 0) {
    return null;
  }
  return (
    <span
      className="flex flex-wrap items-start gap-1"
      data-testid={`template-languages-${props.row.rowKey}`}
    >
      {[...merged.entries()].map(([code, language]) => (
        <StatusPill key={code} tone={language.written ? "info" : "neutral"}>
          {language.written
            ? language.label
            : t("templates.list.notWritten", { language: language.label })}
        </StatusPill>
      ))}
    </span>
  );
}
/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 wave I · THE USED-BY COLUMN, AS A STATUS
 * ══════════════════════════════════════════════════════════════════════════
 *
 * *"used by - why so much text - just show some status"* — the PO, 2026-08-30.
 *
 * The column rendered the server's sentences verbatim: *"Not in use yet —
 * closing an account does not send this."* Ninety-five characters in a 260px
 * column is four lines, on thirty rows, and the list stopped being scannable.
 *
 * ⚠ **THE STATUS IS DERIVED FROM WHAT THE ROW ALREADY PROVES, AND THE SENTENCE
 * IS NOT DELETED.** `body_unavailable` is the SERVER's structural answer to
 * "has this platform written this letter at all", so three of the four states
 * are read from it rather than from copy. Only "is anything sending it" comes
 * from the prose, and it comes from a prefix the seeder writes on every such
 * row. The whole sentence stays on `title`, and it is on the template's own
 * page in full (`where-used`), which the name opens in one click.
 *
 * ⚠ **THE DURABLE FIX IS A SERVER FIELD — AND IT EXISTS NOW (`DEF-NOT-4531`,
 * 2026-09-07).** This comment used to end *"this lane does not mint it, because
 * `apps/notifications/` belongs to another lane this hour"*, and the cost of
 * waiting was exactly what it predicted: the server's sentences drifted, and
 * because the pill was derived FROM them the pill drifted too. 23 of 38 rows
 * said *"Not in use yet — no wording has been written for it."* over wording
 * that exists, one of them on the row the Product Owner opened.
 *
 * `row.used_by_state` is now derived on the server from the seeded wording and
 * the event catalogue — facts, never prose — and a test refuses a sentence that
 * contradicts either. The regular expressions below are KEPT as the fallback
 * for a server that has not been redeployed yet, and only for that: they run
 * when the field is missing, never beside it.
 */
export type UsedByState = "in-use" | "not-in-use" | "no-wording" | "placeholder";

const USED_BY_TONE: Record<UsedByState, StatusTone> = {
  "in-use": "success",
  // ⚠ `muted`, not `neutral`: A12 reads muted as *finished, nothing is owed*
  // and neutral as *nothing has happened yet*, and "nothing sends this" is the
  // second of those. StatusPill's own docstring makes that distinction the
  // rule, so it is followed rather than picked by colour.
  "not-in-use": "neutral",
  "no-wording": "warning",
  // The one document in the product whose wording carries real liability if it
  // is wrong (the NACHA authorization). It is not a danger BUTTON, but it is
  // the row a System Admin must not mistake for ready.
  placeholder: "warning",
};

const USED_BY_KEY: Record<UsedByState, string> = {
  "in-use": "templates.usedBy.inUse",
  "not-in-use": "templates.usedBy.notInUse",
  "no-wording": "templates.usedBy.noWording",
  placeholder: "templates.usedBy.placeholder",
};

export function usedByState(row: TemplateCatalogRow): UsedByState {
  // The SERVER's answer wins whenever it is there (`DEF-NOT-4531`). Checked
  // against the four names rather than cast, so an unknown value from a newer
  // server falls back to the derivation instead of painting an unstyled pill.
  const served = row.used_by_state;
  if (served !== undefined && served !== null && served in USED_BY_TONE) {
    return served as UsedByState;
  }
  const absent = row.body_unavailable;
  if (absent !== null) {
    // The seeder's own marker for the one class that ships a refusal rather
    // than a default. It is the FIRST word of that reason, so this cannot
    // match a sentence that merely mentions the word.
    return absent.trimStart().toUpperCase().startsWith("PLACEHOLDER")
      ? "placeholder"
      : "no-wording";
  }
  return /^not in use yet\b/i.test(row.used_by.trimStart()) ||
    /not switched on yet/i.test(row.used_by)
    ? "not-in-use"
    : "in-use";
}

function UsedByCell(props: {
  row: LibraryRow;
  t: (key: string, vars?: Record<string, unknown>) => string;
}) {
  const { row, t } = props;
  if (row.note === null) {
    // Every bill this utility issues prints on a bill layout, so a bill row is
    // in use by definition — the sentence it used to print said exactly that.
    return (
      <StatusPill tone="success" title={t("templates.library.usedByBills")}>
        {t("templates.usedBy.inUse")}
      </StatusPill>
    );
  }
  const states = row.members.map(usedByState);
  const distinct = [...new Set(states)];
  /* The whole of every sentence this cell stands for, on hover. On a folded
     row it is one line per surface, so a "Mixed" chip can be read without
     opening anything.

     ⚠ **`body_unavailable` IS CARRIED HERE AND THAT IS NOT OPTIONAL.** It is
     the only place in the product that says WHY a letter has no wording — the
     detail page does not print it — so dropping it with the paragraph would be
     the quietly-deleted absence DEF-445 records, not a declutter. The PO asked
     for it OFF THE ROW, and off the row is where it now is: in the tooltip of
     the chip that was derived from it, in full, still selectable by a screen
     reader, and setting the height of nothing. */
  const detail = row.members
    .map((member, index) => {
      const state = t(USED_BY_KEY[states[index]]);
      const why = member.body_unavailable ?? plainUsedBy(member.used_by);
      return row.members.length > 1
        ? `${templateSurface(member.name) ?? member.kind}: ${state} — ${why}`
        : why;
    })
    .join("\n");
  // ⚠ ONE WRAPPER FOR BOTH OUTCOMES, so a test can ask a folded row what it
  // decided. A `mixed` chip whose element differed from a settled one would be
  // a hook that is silently absent on exactly the rows worth checking.
  const mixed = distinct.length > 1;
  const state = distinct[0] ?? "in-use";
  return (
    <span
      data-testid={`template-usedby-${row.rowKey}`}
      data-usedby-state={mixed ? "mixed" : state}
    >
      <StatusPill tone={mixed ? "warning" : USED_BY_TONE[state]} title={detail}>
        {t(mixed ? "templates.usedBy.mixed" : USED_BY_KEY[state])}
      </StatusPill>
    </span>
  );
}

/**
 * CR-048 wave I — ONE NAME, ONCE.
 *
 * *"why we are showing two names under template name"* — the Product Owner,
 * 2026-08-30, reading the deployed screen.
 *
 * Wave E drew the event as a heading line above the row's own name, so a
 * template that is its OWN event printed the same words twice — *"Account
 * closed confirmation"* on top of *"Account closed confirmation"*, the second
 * in accent colour. The code's own comment predicted the case and drew it
 * anyway: *"A row that is its own event still gets one — every row belongs to
 * SOME event"*.
 *
 * ⚠ **IT IS FIXED BY REMOVING THE SECOND SOURCE, NOT BY ADDING A CONDITION.**
 * A row's name now comes from exactly one place: `LibraryRow.name`, which
 * `collapseSurfaces` sets to the EVENT when several surfaces fold into the row
 * and to the template's own full name when they do not. There is no heading
 * line left to disagree with it, so no condition can be got wrong later.
 *
 * ⚠ **AND THE SURFACE IS NOT LOST WITH THE SECOND LINE.** It moved to the KIND
 * column, where it is a control rather than a caption — the PO's own
 * instruction, *"action button for each type"*. A four-surface notice is one
 * row with four reachable surfaces instead of four rows.
 *
 * The click target is unchanged: `template-name-<code>` on the button, and the
 * accessible name is still the FULL seeded name, so a screen reader hearing
 * this row is told at least as much as it was before.
 */
function TemplateName(props: { row: LibraryRow; onOpen: (code: string) => void }) {
  const { t } = useTranslation();
  const { row } = props;
  const full = row.note?.name ?? row.name;
  /* CR-199-BRC10 F1 — the drawing's second line: what the template is FOR, in
     the server's own words (`used_by`, the sentence the in-use pill carries on
     hover). Clamped to two lines so a long one cannot set a row's height. A
     bill layout has no such sentence and draws none. */
  const purpose = row.note === null ? null : plainUsedBy(row.note.used_by);
  return (
    <span className={NAME_CELL}>
      <Button
        variant="ghost"
        onClick={() => props.onOpen(row.rowKey)}
        data-testid={`template-name-${row.rowKey}`}
        title={full}
        aria-label={full}
      >
        {row.name}
      </Button>
      {purpose !== null ? (
        <span className={`${DESC} line-clamp-2`} data-testid={`template-purpose-${row.rowKey}`}>
          {purpose}
        </span>
      ) : (
        /* A bill layout's second line says WHICH KIND it is (CR-048 E9 —
           *"say on every row which kind"*): the Kind column left with the
           redesign, and a bill layout is the one row whose kind is not
           obvious from its channel. */
        <span className={DESC} data-testid={`template-kind-${row.rowKey}`}>
          {t(`templates.library.kind.${row.templateKind}`)}
        </span>
      )}
    </span>
  );
}

/* ══ CR-199-BRC10 F1 · THE STATUS COLUMN ══════════════════════════════════
 * What a customer gets now — *Published*, *Draft waiting*, *Not published* —
 * plus *Needs approval* on a legal notice (PO ruling A1 C), each the SERVER's
 * fact. And the in-use pill CR-048 wave I made of the old Used-by column, with
 * its whole sentence on hover (`CR-199-BRC10` §6 L13): it answers a different
 * question (*does anything send this?*) and dropping it would lose the only
 * place the list says why a letter has no wording. */
function StatusCell(props: {
  row: LibraryRow;
  t: (key: string, vars?: Record<string, unknown>) => string;
}) {
  const { row, t } = props;
  const members = row.note === null ? [] : row.members;
  const published = row.note === null || members.some((member) => member.has_published);
  const draft = members.some((member) => member.has_draft === true);
  const approval = members.some((member) => member.needs_approval === true);
  return (
    <span className="flex flex-col items-start gap-1" data-testid={`template-status-${row.rowKey}`}>
      {draft ? (
        <StatusPill tone="warning">{t("templates.list.draftWaiting")}</StatusPill>
      ) : published ? (
        <StatusPill tone="success">{t("templates.status.published")}</StatusPill>
      ) : (
        <StatusPill tone="neutral">{t("templates.list.notPublished")}</StatusPill>
      )}
      {approval && <StatusPill tone="danger">{t("templates.list.needsApproval")}</StatusPill>}
      <UsedByCell row={row} t={t} />
    </span>
  );
}
/** What a list row can ask the screen to do. One object rather than four
 *  positional callbacks, because the row's actions grew from two to three
 *  (`CR-199-BRC10` F1) and a fourth positional argument is a swap waiting to
 *  happen. */
interface RowHandlers {
  open: (code: string) => void;
  edit: (code: string) => void;
  duplicate: (code: string) => void;
}

/** CR-199-BRC10 F1 — the filter the CHIP ROW above the table writes. Declared
 *  in the config so `parseTableParams` restores it from a pasted URL
 *  (BR-SHL-011), and kept OUT of the `+ Filter` panel because the drawing puts
 *  it in the chips, and two controls writing one param is the duplication
 *  CR-048 E8 removed. */
const CHANNEL_FILTER = "channel";

function catalogConfig(
  t: (key: string, vars?: Record<string, unknown>) => string,
  on: RowHandlers,
  // Read at CELL-RENDER time, not at config time: whether a person may edit is
  // the catalog payload's answer and the payload is still in flight when this
  // is built.
  isReadOnly: () => boolean,
  readOnlyReason: () => string | null,
): TableConfig<LibraryRow> {
  /* CR-048 E9 — the honest cell for a column that does not apply to this KIND.
     NOT a blank: DEF-163's whole finding was that one blank standing for two
     different absences sends a person to the wrong place, and "a bill template
     has no consumer-category variants" is a fact about the row, not a gap in
     the data. */
  const inapplicable = (
    <span className={DESC} data-desc>
      {t("templates.library.notApplicable")}
    </span>
  );
  return {
    screenId: "SET-09",
    getRowId: (row) => row.rowKey,
    defaultSort: { sort: "name", dir: "asc" },
    searchFields: ["name", "code", "category", "used_by"],
    searchPlaceholder: "templates.catalog.searchPlaceholder",
    /* CR-199-BRC10 F1 — the drawing's Category · Language · Status, drawn as
       the shared toolbar's `+ Filter` panel (B14 rules 12 and 44). Every group
       is FILLED from the server's own facets below; a group the server serves
       no values for renders nothing (DEF-782) rather than a filter that
       returns nothing forever. `template_kind` (letters vs bill layouts,
       CR-048 E9) stays — `CR-199-BRC10` §6 L3. */
    filters: [
      { name: "category", label: t("templates.catalog.category"), options: [] },
      { name: "language", label: t("templates.list.language"), options: [] },
      { name: "status", label: t("templates.list.status"), options: [] },
      { name: KIND_FILTER, label: t("templates.library.kindLabel"), options: [] },
      { name: CHANNEL_FILTER, label: t("templates.list.channels"), options: [] },
    ],
    columns: [
      {
        key: "name",
        label: t("templates.list.template"),
        sortable: true,
        identity: true,
        cell: (row) => <TemplateName row={row} onOpen={on.open} />,
      },
      {
        /* The server sorts this column on `kind`, the delivery-format string. */
        key: "kind",
        label: t("templates.list.channels"),
        sortable: true,
        cell: (row) => <ChannelsCell row={row} onOpen={on.open} />,
      },
      {
        key: "category",
        label: t("templates.column.category"),
        sortable: true,
        cell: (row) =>
          row.note !== null ? t(`templates.category.${row.note.category}`) : inapplicable,
      },
      {
        key: "languages",
        label: t("templates.list.languages"),
        cell: (row) => (row.note === null ? inapplicable : <LanguagesCell row={row} />),
      },
      {
        key: "variants",
        label: t("templates.column.variants"),
        sortable: true,
        numeric: true,
        cell: (row) =>
          row.note === null ? (
            inapplicable
          ) : (
            <span
              title={
                row.members.length > 1
                  ? row.members
                      .map((m) => `${templateSurface(m.name) ?? m.kind}: ${m.variants}`)
                      .join("\n")
                  : undefined
              }
            >
              {row.members.reduce((total, m) => total + m.variants, 0)}
            </span>
          ),
      },
      {
        key: "status",
        label: t("templates.list.status"),
        cell: (row) => <StatusCell row={row} t={t} />,
      },
      {
        key: "edited",
        label: t("templates.column.edited"),
        sortable: true,
        cell: (row) =>
          (row.note !== null
            ? row.members
                .map((m) => m.edited)
                .filter((edited): edited is string => edited !== null)
                .sort()
                .at(-1)
            : row.bill?.edited) ?? t("templates.catalog.neverEdited"),
      },
      {
        key: "actions",
        label: t("templates.column.actions"),
        cell: (row) => (
          /* B14 rule 15 — ICONS with tooltips, two visible and the rest behind
             `…`. The drawing puts three on the row (D2: *View · Edit wording ·
             Duplicate as variant*); the third is the menu's, decision log
             2026-10-29 *"screens lane"* (1).

             A Billing Clerk may read every template and change none, so ✎ and
             the duplicate render DISABLED WITH THE SERVER'S REASON
             (BR-SHL-025). A bill row has no variants to duplicate and says so. */
          <RowActions>
            <RowAction
              label={t("templates.catalog.view", { name: row.name })}
              icon={<EyeIcon />}
              onClick={() => on.open(row.rowKey)}
              testId={`template-open-${row.rowKey}`}
            />
            <RowAction
              label={t("templates.list.editWording", { name: row.name })}
              icon={<PencilIcon />}
              reason={isReadOnly() ? (readOnlyReason() ?? "") : null}
              onClick={() => (row.note === null ? on.open(row.rowKey) : on.edit(row.rowKey))}
              testId={`template-edit-${row.rowKey}`}
            />
            <RowActionsMore label={t("templates.list.moreActions", { name: row.name })}>
              <RowMenuAction
                label={t("templates.workspace.duplicate")}
                icon={<CopyIcon />}
                reason={
                  row.note === null
                    ? t("templates.list.noVariantsForBills")
                    : isReadOnly()
                      ? (readOnlyReason() ?? "")
                      : null
                }
                onClick={() => on.duplicate(row.rowKey)}
                testId={`template-duplicate-${row.rowKey}`}
              />
            </RowActionsMore>
          </RowActions>
        ),
      },
    ],
  };
}

/** The disconnection notices the five rights clauses print on (BR-NOT-014's
 *  three tiers and the single class they grew from — `rights_footer.TIER_CLASSES`
 *  plus `disconnect_notice`). */
export const DISCONNECTION_LETTER_PREFIX = "disconnect_notice";

export function isDisconnectionLetter(code: string): boolean {
  return code === DISCONNECTION_LETTER_PREFIX || code.startsWith(`${DISCONNECTION_LETTER_PREFIX}_`);
}

export function TemplateCatalogTab(props: { readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const [search, setSearch] = useSearchParams();
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const openCode = search.get(TEMPLATE_PARAM);
  const variantId = search.get(VARIANT_PARAM);

  // ⚠ NOT memoised, on purpose. The config carries closures over the CURRENT
  // request state (opening a row re-serialises the filters into the URL), so a
  // `useMemo` here would hand the table last render's filters — the stale-
  // closure shape. Building it is a handful of object literals per render;
  // `flexRender` already rebuilds the column defs every render anyway.
  //
  // The cells close over `data` and `readOnly`, which are declared BELOW: a
  // cell only runs while DataTable renders, which is after this function body
  // has finished, so there is no temporal-dead-zone read.
  const config = catalogConfig(
    t,
    {
      open: (code) => openTemplate(code),
      edit: (code) => openTemplate(code, { [WORKSPACE_MODE_PARAM]: WORKSPACE_EDIT }),
      duplicate: (code) => openTemplate(code, { [WORKSPACE_DIALOG_PARAM]: "duplicate" }),
    },
    () => readOnly,
    () => cannotEditReason,
  );
  const state = parseTableParams(search, config);
  const category = state.filters.category ?? "";
  const channel = state.filters[CHANNEL_FILTER] ?? "";

  /**
   * CR-048 wave I — the notification rows, with each event's surfaces FOLDED
   * into one row.
   *
   * ⚠ **ONLY UNDER `name` ASCENDING, AND THAT IS THE HONESTY OF THE WHOLE
   * FEATURE.** A run of surfaces is contiguous only because the seeded names
   * are `<event> · <surface>`, which makes the event the sort prefix — so
   * `name` is the one order in which "the rows next to each other share an
   * event" is a true statement about the page. Under `category`, `kind`,
   * `variants` or `edited` the same two rows can be far apart, and the flat
   * list is what the screen falls back to.
   *
   * ⚠ It also gives up on a DESCENDING name sort. Z→A still puts a run
   * together, but it puts the SURFACES in reverse and the lead row is then the
   * last surface rather than the document itself — folding *"· SMS"* over the
   * printable original reads as though the SMS were the original. Falling back
   * is cheaper than teaching the run which end it starts at.
   *
   * Built per render rather than memoised, for the same reason `config` is:
   * the closure has to see THIS render's rows, and a `useMemo` would hand the
   * table the previous page's folding while the new rows drew under it.
   */
  function notificationRows(): LibraryRow[] {
    const page = data?.results ?? [];
    if (state.sort !== "name" || state.dir !== "asc") {
      return page.map(noteRow);
    }
    return collapseSurfaces(page);
  }

  function pushSearch(next: URLSearchParams): void {
    // Carry the SET-10 params through a table-state change: a person who filters
    // while a template is open has not asked to close it.
    if (openCode !== null) {
      next.set(TEMPLATE_PARAM, openCode);
    }
    if (variantId !== null) {
      next.set(VARIANT_PARAM, variantId);
    }
    setSearch(next, { replace: true });
  }

  function pushState(next: TableRequestState): void {
    pushSearch(serializeTableParams(next, config));
  }

  /** `extra` carries what the row asked for beyond opening — CR-199-BRC10 F1's
   *  ✎ opens the workspace already editing (`?mode=edit`) and `…` → Duplicate
   *  opens it with the duplicate form up (`?dialog=duplicate`). URL state, so
   *  the row's action survives the navigation it causes. */
  function openTemplate(code: string, extra: Record<string, string> = {}): void {
    const next = serializeTableParams(state, config);
    next.set(TEMPLATE_PARAM, code);
    next.delete(VARIANT_PARAM); // a different template's variant id means nothing
    for (const [key, value] of Object.entries(extra)) {
      next.set(key, value);
    }
    setSearch(next, { replace: false });
  }

  function closeTemplate(): void {
    const next = serializeTableParams(state, config);
    setSearch(next, { replace: false });
  }

  function selectVariant(id: string): void {
    const next = serializeTableParams(state, config);
    if (openCode !== null) {
      next.set(TEMPLATE_PARAM, openCode);
    }
    next.set(VARIANT_PARAM, id);
    setSearch(next, { replace: true });
  }

  const catalog = useQuery({
    // `dir` is appended to the shared key factory rather than added to it:
    // `queryKeys.templateCatalog` predates this screen carrying a direction at
    // all, and its signature is queryClient.ts's to change. Without it, sorting
    // Z→A would read the A→Z page out of cache.
    queryKey: [
      ...queryKeys.templateCatalog(state.q, category, state.sort, state.page, state.per),
      state.dir,
      /* CR-199-BRC10 F1 — the three new server filters join the key ONLY when
         one is set, so the unfiltered list keeps the key every reader of this
         cache already uses. */
      ...(channel !== "" || state.filters.language || state.filters.status
        ? [{ channel, language: state.filters.language ?? "", status: state.filters.status ?? "" }]
        : []),
    ],
    queryFn: () =>
      getTemplateCatalog(
        {
          q: state.q,
          category,
          channel,
          language: state.filters.language ?? "",
          status: state.filters.status ?? "",
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
        },
        props.client,
      ),
    staleTime: REFERENCE_STALE_MS,
  });

  /**
   * CR-048 E9 — THE OTHER STORE, fetched beside the catalogue and never merged
   * into it on the server.
   *
   * ⚠ **A SECOND REQUEST AND NOT A SECOND SOURCE OF TRUTH.** `BR-NOT-026` keeps
   * the two stores apart, so the unified list is assembled where the list is
   * drawn. The catalogue's own request is untouched — its search, its category
   * chips, its sort and its pagination are still the server's — and this one
   * carries the handful of bill templates a tenant has.
   *
   * ⚠ **AND IT IS ALLOWED TO FAIL WITHOUT TAKING THE SCREEN DOWN.** A person
   * who came here to edit a disconnection letter must not lose the whole list
   * because the bill-template read was refused; `bills` is simply empty and the
   * kind filter offers what the server offered.
   */
  const library = useQuery({
    queryKey: [...templateLibraryKey, "bill"],
    queryFn: () => getTemplateLibrary({ kind: "bill" }, props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const data = catalog.data;
  // ⚠ `data === undefined` is NOT read-only. It is UNKNOWN, and the detail
  // screen asks the same question of its own payload — so treating a pending
  // catalog as a refusal would flash "System Admin only" at a System Admin who
  // followed a `?template=` link.
  const readOnly = props.readOnly || (data !== undefined && !data.can_edit);
  const cannotEditReason = data?.cannot_edit_reason ?? null;

  /**
   * CR-048 E8 — the SECOND stage of the config: the `category` dimension's
   * options, which are the SERVER's own five headings.
   *
   * The labels are this module's copy (IS-8 — the framework never hardcodes a
   * screen's names); the KEYS are never invented, because a chip for a
   * category the server does not offer is a filter that returns nothing
   * forever. Everything else is `config` untouched, so `parseTableParams` and
   * `serializeTableParams` keep reading the SAME declaration this renders.
   */
  /* ⚠ THE OPTIONS ARE FILLED BY MAPPING OVER `config.filters`, NOT BY WRITING
     A SECOND ARRAY (2026-08-30). This block used to restate both groups — name,
     label and all — which meant every filter's NAME and LABEL was written in
     two places and free to drift: rename a group in the declaration above and
     the fill below silently stops matching it, leaving a filter that restores
     from a URL and offers no chips. Mapping makes that unrepresentable; the
     declaration above is the single list, and this only supplies values.

     It also stopped G45 failing. That gate counts `filters: [` array literals
     against `filterBarSlot` passes, because two TABLES in one file each need a
     control (`SettingsRoutesCyclesTab`, `PaymentsPage`) — and it cannot tell a
     second table from an override of the first. **The duplication was real, so
     it is the duplication that was removed, not the gate that was loosened.**

     Keys are never invented here: a chip for a category or a kind the server
     does not offer is a filter that returns nothing forever (DEF-782). An
     unfilled group renders no panel at all, which is why the fill matters. */
  const filterOptions: Record<string, { value: string; label: string }[]> = {
    category: (data?.categories ?? []).map((chip) => ({
      value: chip.key,
      label: t(`templates.category.${chip.key}`),
    })),
    [KIND_FILTER]: (library.data?.kinds ?? []).map((kind) => ({
      value: kind,
      label: t(`templates.library.kind.${kind}`),
    })),
    /* CR-199-BRC10 F1 — the utility's own languages and the statuses, both the
       server's facets. Absent → empty → the group is not offered (DEF-782). */
    language: (data?.languages ?? []).map((language) => ({
      value: language.key,
      label: languageName(language.key),
    })),
    status: (data?.statuses ?? []).map((status) => ({
      value: status.key,
      label: t(`templates.list.statusOption.${status.key}`, { defaultValue: status.key }),
    })),
  };
  const viewConfig: TableConfig<LibraryRow> = {
    ...config,
    filters: (config.filters ?? []).map((group) => ({
      ...group,
      options: filterOptions[group.name] ?? group.options,
    })),
  };

  /* CR-048 E9 — THE ONE LIST, assembled here.
     Notification rows keep the SERVER's order (that is what makes E7's event
     grouping contiguous), and the bill rows follow them. The kind filter is
     applied here for the same reason the merge is: the catalogue endpoint
     answers about one store and knows nothing about the other. */
  const kindFilter = state.filters[KIND_FILTER] ?? "";
  /* CR-199-BRC10 F1 — a bill layout is a printed letter in no language a
     variant carries and is always live, so it answers the channel chips as
     Letter, the status filter as Published, and no language filter at all. */
  const billsAnswer =
    kindFilter !== "notification" &&
    (channel === "" || channel === "pdf_print") &&
    (state.filters.status ?? "") in { "": 1, published: 1 } &&
    (state.filters.language ?? "") === "" &&
    /* DEF-NOT-10675 — the server searches and category-filters only its own
       store, so the bill rows must ask the same two questions here: a bill
       layout has no category, and it answers a search by its name. */
    category === "";
  const needle = state.q.trim().toLocaleLowerCase();
  /* ⚠ DEF-NOT-10674 — THE TABLE IS TOLD THE SERVER'S COUNT, NOT THE ROWS ON
     SCREEN. The catalogue is paged by the server (`per`, 50 by default) and a
     sample utility already holds 87 classes, so `rows.length` (one page,
     folded) made the footer read "1–38 of 38" and left page 2 — every
     template after "Service disconnected" — unreachable. The bill layouts
     ride on the LAST notification page only, so paging forward never draws
     them twice. */
  const bills = billsAnswer
    ? (library.data?.results ?? [])
        .filter((row) => needle === "" || row.name.toLocaleLowerCase().includes(needle))
        .map(billRow)
    : [];
  const noteCount = kindFilter === "bill" ? 0 : (data?.count ?? 0);
  const onLastNotePage = state.page * state.per >= noteCount;
  const rows: LibraryRow[] = [
    ...(kindFilter === "bill" ? [] : notificationRows()),
    ...(onLastNotePage ? bills : []),
  ];
  const totalRows = data === undefined && kindFilter !== "bill" ? null : noteCount + bills.length;

  if (isPermissionDenied(catalog.error)) {
    return <SettingsDenied helper={t("templates.catalog.denied")} />;
  }

  /* CR-048 E9 — A BILL ROW OPENS THE LAYOUT CHOOSER, which is the editor that
     suits it. The chooser is `BillLayoutTab`, unchanged and still billing's;
     what changed is that it is reached FROM the one list instead of sitting
     underneath it as a second list nobody knew to look in. */
  if (openCode !== null && openCode.startsWith(BILL_KEY_PREFIX)) {
    return (
      /* ⚠ **NOT `PanelGrid`, AND `DEF-BIL-4459` IS WHY.** `PanelGrid` is
         `.settings-grid` — `repeat(auto-fit, minmax(320px, 1fr))` — and it lays
         each CHILD into a cell. Two children were handed to it: a back button
         and a whole screen. So at 1440 the button claimed a 544px column of its
         own, the five layout cards were crammed into the other one, and half
         the panel was white space. Every DOM assertion passed — both children
         render, the button works, all five cards are present — and no check in
         this repo reads rendered output.
         A grid whose children are heterogeneous (one control and one screen) is
         not a grid. The back control is page furniture and is drawn as such,
         which is also what SET-10's own detail does four lines below. */
      <div className={PAGE_STACK}>
        <div className="flex w-fit flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={closeTemplate} data-testid="bill-layout-back">
            {t("templates.library.backToTemplates")}
          </Button>
        </div>
        <BillLayoutTab readOnly={readOnly} client={props.client} />
      </div>
    );
  }

  if (openCode !== null) {
    return (
      <div className={PAGE_STACK}>
        <TemplateWorkspace
          code={openCode}
          client={props.client}
          readOnly={readOnly}
          readOnlyReason={cannotEditReason}
          variantId={variantId}
          onSelectVariant={selectVariant}
          onBack={closeTemplate}
          /* CR-048 E5 — *"one notice, four surfaces"*, and the sibling list has
             to come from HERE. `GET /template-catalog/{code}` answers about ONE
             class and names no other, so SET-10 cannot build the switcher from
             what it fetches; the CATALOG PAGE is what holds the relationship.
             Passing the rows down is the whole wiring.

             ⚠ It is the loaded page and not "all templates", which is honest
             rather than convenient: on a `?template=` link opened cold the page
             may not hold the row at all, and `siblingSurfaces` answers with an
             empty list, so no switcher is drawn (BR-SHL-010) instead of one built
             from whichever rows happened to be cached. */
          surfaces={siblingSurfaces(data?.results ?? [], openCode)}
          onOpenSurface={openTemplate}
        />
        {/* ══ THE CUSTOMER RIGHTS WORDING, UNDER THE LETTER IT PRINTS ON ════════
            PO 2026-10-22, verbatim: *"A. Move it to Configure → Templates, next
            to the disconnection letter it prints on."* It left Notifications'
            strip; the old `/settings/notifications/rights` redirects here (the
            10-day notice). One card, the same component and the same server
            write — editing stays System Admin only, which is the SERVER's gate,
            unchanged. The red *platform wording* warning lives INSIDE the card,
            so it moved with it by construction. */}
        {isDisconnectionLetter(openCode) && (
          <div data-testid="templates-rights">
            <RefusalNotice refusal={refusal} />
            <DisconnectRightsFooterCard
              client={props.client}
              readOnly={props.readOnly}
              t={t}
              onRefusal={setRefusal}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <PanelGrid>
      <RefusalNotice refusal={refusal} />
      <Panel
        /* ⛔ **`+ New variant` LEFT THE TITLE ROW (CR-199-BRC10 F1).** The
           drawing (`01-list.png`) draws no page action on the list: a variant
           is made from the template it varies, so the button is in the
           workspace's action bar (`06`) and every row's `…` holds *Duplicate as
           variant* (`10`) — `CR-199-BRC10` §6 L10. The inline creator form and
           its "pick a template first" select went with it; nothing it did is
           lost, because both doors post to the same `…/variants` route. */
        title={<span data-testid="templates-title-row">{t("templates.catalog.title")}</span>}
        hint={t("templates.catalog.separation")}
      >
        {/* BR-SHL-025 — a role that may read and not write is told so once, in
            the server's words (`CR-199-BRC10` §6 L12). It used to ride beside
            the create button; the button moved, the sentence did not. */}
        {readOnly && data?.cannot_edit_reason != null && (
          <RefusalStrip role="note" data-testid="template-readonly">
            {data.cannot_edit_reason}
          </RefusalStrip>
        )}
        {/* CR-199-BRC10 F1 — the drawing's channel chips, above the table. */}
        <TemplateChannelChips
          channels={data?.channels}
          allCount={data?.channels_total ?? data?.count ?? 0}
          active={channel}
          onSelect={(next) =>
            pushState({
              ...state,
              page: 1,
              filters: { ...state.filters, [CHANNEL_FILTER]: next },
            })
          }
        />
        {/* ⛔ **NO `downloadSlot`, AND THIS IS THE STATED ABSENCE CR-041 TASK 4
          ASKS FOR — NOT A FORGOTTEN PROP (DEF-1005).**

          `POST /exports` resolves only the resources a module REGISTERS, and an
          unregistered one is a plain 404, never a guessed queryset. Nothing
          registers `templates`, so BR-SHL-010 keeps the capability unrendered:
          an undeclared capability is not drawn. Not drawn DISABLED either —
          BR-SHL-025 is for a control this ROLE cannot use, not one the PRODUCT
          does not have.

          ⚠ Of the eight, this is the one least likely to be RULED IN: a template
          catalogue is configuration a tenant edits in place, not a register
          anybody reconciles on paper. Stated anyway — the point of task 4 is that
          the reader can tell a decision from an oversight, and 'probably never'
          is a decision.

          ⚠ A DOWNLOAD BUTTON HERE WOULD BE A CONTROL WIRED TO A 404 — hard-won
          law 2, which this repo has four instances of from a single day. The
          capability is OWED and unruled, and **DEF-1005 carries it** so this
          sentence expires when the row does rather than outliving its reason
          (DEF-445). */}
        <DataTable<LibraryRow>
          config={viewConfig}
          state={state}
          onStateChange={pushState}
          rows={rows}
          totalRows={totalRows}
          loading={catalog.isPending}
          error={
            catalog.error !== null
              ? { reason: apiErrorText(catalog.error, t), onRetry: () => void catalog.refetch() }
              : null
          }
          // B14 rule 17 — what is missing AND the action that fills it. This
          // list can only be empty if the platform catalog failed to load, so
          // the action is the honest one: read it again. A "+ New template"
          // here would be a button onto OQ-253.
          empty={{
            title: t("templates.catalog.emptyTitle"),
            helper: t("templates.catalog.emptyHelper"),
            ctaLabel: t("templates.catalog.emptyCta"),
            ctaReason: null,
            onCta: () => void catalog.refetch(),
          }}
          /* CR-048 E8 — THE SHARED FILTER BAR, in the shape B14 rule 12 and
             DEF-442 draw: the `All` chip, a REMOVABLE chip per applied filter,
             and one `+ Filter ▾` panel. This screen drew six category pills of
             its own here, which is the duplicated dimension DEF-1700 ruled away
             on three other screens — the config ALREADY declared `f.category`,
             so the pills and the panel were two controls writing one param.

             ⚠ **`config.filters` NOT `[]`, AND THAT IS THE HALF THAT WAS
             MISSING.** `offerableFilters` drops a group with no options
             (DEF-782), and the declaration carried `options: []` for as long as
             it has existed — so mounting `FilterBar` alone would have rendered
             NOTHING and looked like a working change. The options come from the
             server's own `categories`, through `catalogConfig`. */
          filterBarSlot={
            <FilterBar
              filters={(viewConfig.filters ?? []).filter((group) => group.name !== CHANNEL_FILTER)}
              state={state}
              onStateChange={pushState}
            />
          }
        />
        {/* DEF-NOT-10673 — no sentence under the table. "All N templates fit
            on one page: the smallest page size is…" explained why the page
            controls have nothing to do, which is rationale (B14 rule 33: zero
            words on screen), and image 01 draws the table's own footer
            ("6 of 6 templates · Rows per page") and nothing beneath it. */}
      </Panel>
    </PanelGrid>
  );
}

/* ⛔ **THE LOCAL `Filters` COMPONENT IS DELETED, NOT LEFT BESIDE THE FIX
   (CR-048 E8, hard-won law 1).** It drew this screen's own labelled
   `input[type=search]` and its own six `chip-<key>` category pills into
   `DataTable`'s filter slot. Both are now the shared toolbar's:

     · the SEARCH is `config.searchFields` + `config.searchPlaceholder`,
       which is DataTable's own box carrying B14 rule 19's module prompt —
       the thing the old header note was waiting for (DEF-510);
     · the CATEGORY is `FilterBar` over the `f.category` the config already
       declared, so the `All` chip, the removable chip and the `+ Filter ▾`
       panel all arrive at once (DEF-442) instead of being drawn a second
       time here.

   Leaving the component in place unreferenced would be a second, divergent
   way to draw this toolbar for the next lane to find and wire back up. */
/* ⛔ **`Creator` AND `CreatorForm` ARE DELETED, NOT LEFT BESIDE THE MOVE
   (CR-199-BRC10 F1, hard-won law 1).** The list's `+ New variant` button and
   the inline form it unfolded — pick a template, name, audience, language —
   are the workspace's `+ New variant` and the row `…` → *Duplicate as variant*
   now (`TemplateVariantDialog`), both posting to the same
   `POST /template-catalog/{code}/variants`. A form here with nothing opening
   it would be a second way to make a variant for the next lane to wire back. */
