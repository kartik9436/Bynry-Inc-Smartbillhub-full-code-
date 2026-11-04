// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 — the New connects LIST, revamped to
//           `05-prototype/new-connect-detail-2026-09-28/00-list.png`, which is
//           the drawing of record (B14 rule 42: built from the IMAGE, never
//           from the extracted text).
// Rules:    B14 rule 43 (a piece of UI is built as a COMPONENT — standalone
//           code inside a page is not reuse, which is why these five live here
//           and not inline in a 1,200-line tab) · rule 12 (the toolbar's
//           grammar) · rule 15 (row actions are icons, and an opened menu is
//           words) · rule 21 (Tailwind utilities; this file adds NO class to a
//           stylesheet and is on `route-b-migrated.txt`) · rule 31 (no
//           database id is a visible value) · rule 33 (label ≤ 3 words, fact ≤
//           6, rationale ZERO) · BR-SHL-025 (a control that cannot be used
//           renders DISABLED WITH ITS REASON)
// Design:   05-prototype/new-connect-detail-2026-09-28/00-list.png ·
//           README.md in the same folder
// Tests:    07-frontend/src/features/customers/NewConnectsTab.test.tsx
// Impacts:  NewConnectsTab.tsx (the only consumer today)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS AT ALL — B14 RULE 43, RATIFIED 2026-09-20
// ══════════════════════════════════════════════════════════════════════════
// *"A piece of UI is built as a COMPONENT; standalone code inside a page is
// not reuse."* Ruled after *"use it"* turned out to mean 120 lines inline in a
// 4,186-line page, importable by nothing. `NewConnectsTab.tsx` is already
// 1,200 lines; the tiles, the row menu, the bulk bar and the act dialog are
// four pieces of UI and each is a component here.
//
// ⚠ **NONE OF THEM IS A SECOND COPY OF A KIT COMPONENT.** The tiles reuse
// `KPIStrip.css`'s own `.kpi-grid` / `.kpi` / `.k` / `.v` / `.d` so a pressable
// tile is pixel-identical to every other KPI tile in the product; the menu is
// `RowActionsMore` + `RowMenuAction`; the bar is `SelectionToolbar`; the
// dialog is `ConfirmDialog`. What is new here is the WIRING, which is the part
// that belongs to this screen.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { FormModal, TextField } from "@/components/FormModal";
import { RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { SelectionToolbar } from "@/components/SelectionToolbar";
import { LoadingSkeleton } from "@/components/StateFrame";
import { BellIcon, PauseIcon, RetireIcon } from "@/components/icons";
import type { KpiTile } from "@/components/KPIStrip";
import type { TableRequestState } from "@/components/tableTypes";
import type { Translator } from "@/features/tenancy/settingsShared";
import { actBlockedReason } from "@/features/work/buildViews";
import type { BuildAct } from "@/features/work/buildViews";
import type { BuildFacts } from "@/features/work/workEndpoints";

import { WORKLIST_QUERY_PREFIXES } from "./parkedDrafts";
import { cancelConnection, holdConnection, setWaitingOn } from "./newConnectEndpoints";
import type { ConnectionRow } from "./worklistEndpoints";

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE TILES, WHICH ARE THE FILTER — AND NOT A CONTROL BESIDE IT
// ══════════════════════════════════════════════════════════════════════════
//
// The drawing draws five tiles with the first one ringed, and the README says
// what that ring means: *"The tiles filter. Clicking one narrows the table,
// which is what four counts sitting above a table should do."*
//
// ⚠ **A TILE SETS `state.filters`; IT DOES NOT FILTER AROUND IT.** The
// difference is the whole of this component. A tile holding its own "selected"
// state and narrowing the rows itself would leave the `+ Filter ▾` bar saying
// *no filters* over a narrowed table — two controls disagreeing about what the
// table is showing, which is the shape `DEF-1702` was filed for one register
// along. So the tile writes through the SAME `onStateChange` the `FilterBar`
// writes through, and reads its own pressed-ness back out of
// `state.filters.state`. There is one source of truth and it is the request.
//
// ⚠ **A SECOND PRESS CLEARS IT.** A tile that can only ever turn a filter ON
// is a control a clerk cannot undo without finding the chip's ✕ somewhere else.
//
// ⚠ **AND THREE OF THE FIVE TILES ARE NOT CONTROLS, WHICH IS A SERVER FACT
// RATHER THAN A CHOICE (BR-SHL-010).** `GET /connections` declares exactly one
// filter dimension — `state` — and `connection_reads.STATE_FILTER_VALUES` is
// its whole vocabulary. Two of the drawn tiles name a value in it:
//
//   · **Open** → `f.state=open`, the server's own `SCOPE_OPEN` superset;
//   · **Partly activated** → `f.state=partly_activated`.
//
// The other three name no value the request can carry, and each for a
// different reason, none of which this screen may paper over:
//
//   · **Waiting on someone** — *waiting* is derived from the `waiting_on`
//     COLUMN and is not a state. That is `OQ-371`'s own point, restated by
//     `connection_reads`: *"not one drawn row carries `Waiting` in its STATE
//     column, and `waiting_on` is a separate column beside STATE"*. A tile
//     wired to `f.state=on_hold` would be a plausible-looking lie: hold and
//     waiting are two independent axes and the code says so.
//   · **Units awaiting** — it counts UNITS, and every other control on this
//     screen selects BUILDS. Its set is the Open tile's set, so wiring it
//     would put two tiles on one filter and neither would mean what it says.
//   · **Owed on open builds** — no money is served on this list at all. The
//     whole list of what the drawing asks for and the endpoint cannot fill is
//     in `NewConnectsTab.tsx` §4, with the field each one needs.
//
// A fact is rendered as a fact. `pressable: false` draws the tile as the
// static `<div>` `KPIStrip` already draws, so nothing looks like a control a
// clerk can press and then finds cannot be pressed — law 2's mirror, which is
// the expensive half.

/** The one filter dimension `GET /connections` declares. */
export const BUILD_STATE_FILTER = "state";

/** One tile of the strip: the kit's own tile, plus what pressing it asks for. */
export interface BuildTile {
  tile: KpiTile;
  /**
   * The `f.state` value this tile asks for, or `null` when the tile is a FACT
   * with no filter behind it. Never a guess — see the block above.
   */
  filter: string | null;
}

/** Whether `state` currently carries this tile's filter. */
export function tileIsApplied(state: TableRequestState, filter: string | null): boolean {
  return filter !== null && state.filters[BUILD_STATE_FILTER] === filter;
}

/**
 * Press a tile: SET the filter, or clear it when it is already the applied one.
 *
 * Exported so the rule can be asserted without a DOM — the round trip a test
 * has to be able to make is *press → the request state carries it → the
 * FilterBar reads it back*.
 *
 * ⚠ **THE PAGE GOES BACK TO 1.** Narrowing nine pages to one while the clerk
 * is standing on page 4 answers with an empty table over a total that says
 * there are rows. Every filter control in this product resets the page and
 * this one is not the exception.
 */
export function pressTile(state: TableRequestState, filter: string): TableRequestState {
  const filters = { ...state.filters };
  if (filters[BUILD_STATE_FILTER] === filter) {
    delete filters[BUILD_STATE_FILTER];
  } else {
    filters[BUILD_STATE_FILTER] = filter;
  }
  return { ...state, filters, page: 1 };
}

/**
 * The drawn strip. `KPIStrip`'s own classes, so a pressable tile and a plain
 * one are the same tile.
 *
 * ⚠ **IT WAS CALLED `BuildTiles` UNTIL 2026-09-28, AND THE NAME WAS WRONG IN
 * A WAY THAT COST SOMETHING (`DEF-CUS-7622`).** This is the New connects
 * LIST's strip — counts across many builds, two of them pressable filters —
 * and `features/work/buildRecord/BuildRecordTiles.tsx` is ONE build's five
 * tiles. Two different panels, and the old name said they were the same kind
 * of thing. **They also collided on a hook a browser walkthrough reads**:
 * both wrote `data-build-tiles`, one as a COUNT and one as an empty string,
 * and `10-scripts/cr126_build_record_walk.mjs:144` locates that attribute and
 * parses it as a number. So the strip's own hook is `data-newconnect-tiles`
 * now. `G93` check 1 read the old name as a build panel declared outside its
 * home — truthfully by its own rule, and note that this component's three
 * siblings in this file (`BuildActDialog`, `BuildBulkBar`, `BuildRowMenu`) do
 * the same job for the same screen and sail past it, because `Dialog`, `Bar`
 * and `Menu` are not in the gate's suffix list. One of four caught is what a
 * name rule does; the name was still wrong.
 *
 * ⚠ **IT DOES NOT COMPOSE `KPIStrip` AND THAT IS NOT AN OVERSIGHT.**
 * `components/KPIStrip.tsx` renders every tile as a `<div>` and has no
 * `selected` / `onSelect` pair; a clickable `<div>` is on the never-do list
 * and wrapping the whole strip in one control would make all five tiles one
 * button. **The right home for this is those two props on `KPIStrip` itself**,
 * which is the components lane's file — `DEF-CUS-7623`, and this component
 * folds into it the day they land.
 */
export function NewConnectTiles(props: {
  tiles: readonly BuildTile[];
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  t: Translator;
  loading?: boolean;
}) {
  if (props.loading === true) {
    // ⚠ **THE SHARED SKELETON, NOT A SECOND ONE (`BR-SHL-012`).** `KPIStrip`
    // draws exactly this while a strip is in flight, and replacing the strip
    // without carrying its loading state would have dropped the skeleton on
    // this one screen — five tiles reading `0` and `None open` on first paint,
    // which is a FIGURE where there is no answer yet rather than a wait.
    return <LoadingSkeleton variant="kpi" />;
  }
  return (
    <div className="kpi-grid" data-newconnect-tiles="">
      {props.tiles.map(({ tile, filter }) => {
        const body = (
          <>
            <span className="k">{tile.label}</span>
            <span className="v">{"value" in tile ? tile.value : null}</span>
            {tile.detail !== undefined && <span className="d">{tile.detail}</span>}
          </>
        );
        if (filter === null) {
          // A FACT. The same tile the kit draws, and nothing to press.
          return (
            <div className="kpi" key={tile.id} data-tile={tile.id}>
              {body}
            </div>
          );
        }
        const applied = tileIsApplied(props.state, filter);
        return (
          <button
            type="button"
            key={tile.id}
            data-tile={tile.id}
            data-tile-filter={filter}
            aria-pressed={applied}
            onClick={() => props.onStateChange(pressTile(props.state, filter))}
            // The ring is the drawing's — the `Open` tile is drawn ringed in
            // the accent. `text-left` because a `<button>` centres its content
            // and a tile is a column of left-aligned facts.
            className={
              "kpi cursor-pointer text-left" +
              (applied ? " outline outline-2 -outline-offset-2 outline-accent" : "")
            }
          >
            {body}
          </button>
        );
      })}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE ROW MENU AND THE BULK BAR — ONE SET OF ACTS, ONE REFUSAL FUNCTION
// ══════════════════════════════════════════════════════════════════════════
//
// The README: *"The row menu holds Hold, Waiting on and Cancel build; the tick
// boxes do the same in bulk."* Three acts, and they are THE SAME three in both
// places — `BUILD_ROW_ACTS` is the one list, so a menu and a bar cannot offer
// different sets of the same feature.
//
// ⚠ **THE REFUSAL IS `actBlockedReason`, WHICH IS WORK'S, AND IT IS NOT
// RESTATED HERE.** A hardcoded `disabled={row.state === "cancelled"}` would be
// a second copy of a rule the build detail already implements and the server
// already enforces — and the copy is the one that goes stale. Its own
// docstring says the rules are *"the SERVER's own restated"*.

/** The three acts the drawing puts on a row of this list, in the drawn order. */
export const BUILD_ROW_ACTS = ["hold", "waitingOn", "cancel"] as const;
export type BuildRowAct = (typeof BUILD_ROW_ACTS)[number];

/**
 * A list ROW, in the shape `actBlockedReason` reads.
 *
 * ⚠ **`actBlockedReason` TAKES `BuildFacts` AND A LIST ROW IS NOT ONE**, so
 * this maps the fields it actually reads and states the rest. It reads exactly
 * two: `state`, on every act, and `outstanding`, on `closeOutstanding` alone.
 *
 * ⚠ **`outstanding` IS EMPTY HERE AND THAT IS WHY `closeOutstanding` IS NOT IN
 * `BUILD_ROW_ACTS`.** `GET /connections` serves no to-do list per row, so an
 * empty array would make *Close outstanding* refuse on every row forever — a
 * refusal that is not a real check, which is the one thing this whole wiring
 * exists to avoid. `buildRowActsReadOnlyState` asserts the menu never offers
 * an act that reads a field this row cannot fill; add a fourth act and it goes
 * RED until the row carries what the act needs.
 */
export function rowBuildFacts(row: ConnectionRow): BuildFacts {
  return {
    id: row.id,
    connection_no: row.connection_no,
    state: row.state,
    // Not served on a list row (`NewConnectsTab.tsx` §4). Nothing in
    // `actBlockedReason` reads either of them.
    mode: null,
    target_activation: row.target_activation,
    quote_total: { stored: null, display: null },
    waiting_on: row.waiting_on,
    units: row.units,
    orders: row.orders,
    outstanding: [],
    home: row.home,
    premises_id: row.premises === null ? null : row.premises.id,
  };
}

/**
 * The acts `rowBuildFacts` can answer for truthfully — the ones whose refusal
 * reads only `state`.
 *
 * Exported so the test can assert `BUILD_ROW_ACTS ⊆ this`, which is the check
 * that fires when somebody adds a fourth act to the menu.
 */
export const ACTS_DECIDED_BY_STATE_ALONE: readonly BuildAct[] = [
  "hold",
  "release",
  "cancel",
  "waitingOn",
  "addService",
  "raiseOrder",
  "markOutstanding",
];

/** Label and glyph per act. The keys are the ones `buildViews` already uses, so
 *  the menu and the build page say the same word in all eleven languages. */
const ACT_WORDS: Record<BuildRowAct, { key: string; en: string; danger?: boolean }> = {
  hold: { key: "customers.connection.act.hold", en: "Hold…" },
  waitingOn: { key: "customers.connection.act.waitingOn", en: "Waiting on…" },
  cancel: { key: "customers.connection.act.cancel", en: "Cancel…", danger: true },
};

function actIcon(act: BuildRowAct) {
  if (act === "hold") return <PauseIcon />;
  if (act === "waitingOn") return <BellIcon />;
  return <RetireIcon />;
}

/** What a clerk is about to do, to which rows. `ids` is one row from the menu
 *  and many from the bar — the dialog and the mutation do not know which. */
export interface BuildActTarget {
  act: BuildRowAct;
  ids: readonly string[];
  /** What the clerk can SEE they picked — the build number, or the count. */
  subject: string;
}

/**
 * `⋮` on a row. `RowActionsMore` is the kit's overflow menu and it renders
 * open-able markup under `renderToStaticMarkup`, so a static case can read
 * what is inside it.
 */
export function BuildRowMenu(props: {
  row: ConnectionRow;
  t: Translator;
  onAct: (target: BuildActTarget) => void;
}) {
  const facts = rowBuildFacts(props.row);
  return (
    <RowActionsMore label={props.t("table.rowActions.more")}>
      {BUILD_ROW_ACTS.map((act) => {
        const word = ACT_WORDS[act];
        return (
          <RowMenuAction
            key={act}
            label={props.t(word.key, { defaultValue: word.en })}
            icon={actIcon(act)}
            danger={word.danger}
            // BR-SHL-025 — the reason travels with the disabled control, and
            // it is Work's check rather than a copy of it.
            reason={actBlockedReason(act, facts, props.t)}
            onClick={() =>
              props.onAct({ act, ids: [props.row.id], subject: props.row.connection_no })
            }
          />
        );
      })}
    </RowActionsMore>
  );
}

/**
 * What the bar can actually do, said before it is pressed.
 *
 * ⚠ **`SelectionToolbar.eligibility` EXISTS FOR EXACTLY THIS AND ITS OWN
 * DOCSTRING SAYS WHY:** *"a bar that goes live when the action will mostly
 * fail is worse than one that is greyed out"*. So the bulk act runs over the
 * rows that CAN take it and the bar says how many that is.
 */
export function eligibleForAct(
  rows: readonly ConnectionRow[],
  act: BuildRowAct,
  t: Translator,
): ConnectionRow[] {
  return rows.filter((row) => actBlockedReason(act, rowBuildFacts(row), t) === null);
}

/** The bulk bar — the same three acts, over the ticked rows. */
export function BuildBulkBar(props: {
  rows: readonly ConnectionRow[];
  t: Translator;
  onAct: (target: BuildActTarget) => void;
  onClear: () => void;
}) {
  const count = props.rows.length;
  // ⚠ **AN EMPTY SELECTION DRAWS NO BAR, AND THAT IS A GUARD RATHER THAN
  // TIDINESS.** The caller filters the page's rows by the ticked ids, and a
  // ticked id survives a page, a sort and a filter change — so *ticked
  // something* and *that row is on the page in front of you* are two different
  // questions and the second can be `no`. `props.rows[0]` below would throw on
  // that, which is a white screen rather than a missing bar.
  if (count === 0) {
    return null;
  }
  return (
    <SelectionToolbar
      label={props.t("customers.newConnects.bulk.label", { defaultValue: "Selected builds" })}
      count={props.t("customers.newConnects.bulk.selected", {
        defaultValue: "{{count}} selected",
        count,
      })}
      // ⚠ **WHAT CAN ACTUALLY HAPPEN, SAID BEFORE THE PRESS.** The slot's own
      // docstring: *"a bar that goes live when the action will mostly fail is
      // worse than one that is greyed out"*. Tick five builds where two are
      // cancelled and the bar says so, rather than reporting *5 selected* over
      // an act that will run on three. It counts HOLD, which is the strictest
      // of the three and the one a cancelled row refuses.
      eligibility={props.t("customers.newConnects.bulk.eligible", {
        defaultValue: "{{count}} can be held",
        count: eligibleForAct(props.rows, "hold", props.t).length,
      })}
      data-testid="new-connects-bulk"
    >
      {BUILD_ROW_ACTS.map((act) => {
        const word = ACT_WORDS[act];
        const can = eligibleForAct(props.rows, act, props.t);
        // The reason is the FIRST row's own refusal when none can act, so the
        // clerk reads a real rule rather than "nothing can be done".
        const reason =
          can.length > 0
            ? null
            : (actBlockedReason(act, rowBuildFacts(props.rows[0]), props.t) ?? null);
        return (
          <Button
            key={act}
            size="sm"
            variant={word.danger === true ? "danger" : "secondary"}
            data-act={act}
            disabled={reason !== null}
            title={reason ?? undefined}
            data-blocked-reason={reason ?? undefined}
            onClick={() =>
              props.onAct({
                act,
                ids: can.map((row) => row.id),
                subject: props.t("customers.newConnects.bulk.selected", {
                  defaultValue: "{{count}} selected",
                  count: can.length,
                }),
              })
            }
          >
            {props.t(word.key, { defaultValue: word.en })}
          </Button>
        );
      })}
      <Button size="sm" variant="secondary" onClick={props.onClear}>
        {props.t("customers.newConnects.bulk.clear", { defaultValue: "Clear" })}
      </Button>
    </SelectionToolbar>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE ACT DIALOG — MOUNTED ONCE, ABOVE THE TABLE
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **ONCE, AND NOT PER ROW — `DEF-CUS-6011`.** `DataTable` rebuilds its
// column defs on every render, so `flexRender` hands React a new component
// type each time and a cell's whole subtree is unmounted and remounted: **a
// `useState` inside a cell is destroyed by the very re-render that setting it
// caused.** `ParkedDiscardDialog` is here for the same reason and this follows
// it rather than inventing a second answer.
//
// ⚠ **ALL THREE ACTS NEED A SENTENCE TYPED, AND THE SERVER REQUIRES IT.**
// `holdConnection` and `cancelConnection` take a `reason` — *"an unattributed
// hold is half a hold, and the reason is what the WAITING ON column then
// carries"* — and `setWaitingOn` takes the text that becomes the column. So
// the field is not a courtesy and the commit stays disabled until it is filled.

/** One act's own words. `defaultValue` everywhere, per this feature's standing
 *  rule: the catalogues own the words the moment the locale lane adds the keys,
 *  and a raw key on screen is worse than English. */
export function actCopy(
  target: BuildActTarget,
  t: Translator,
): { title: string; field: string; submit: string; danger: boolean } {
  if (target.act === "hold") {
    return {
      title: t("customers.newConnects.act.holdTitle", {
        defaultValue: "Hold {{subject}}",
        subject: target.subject,
      }),
      field: t("customers.newConnects.act.holdReason", { defaultValue: "Why" }),
      submit: t("customers.connection.act.confirm", { defaultValue: "Confirm" }),
      danger: false,
    };
  }
  if (target.act === "waitingOn") {
    return {
      title: t("customers.newConnects.act.waitingTitle", {
        defaultValue: "Waiting on {{subject}}",
        subject: target.subject,
      }),
      field: t("customers.newConnects.act.waitingWho", { defaultValue: "Who" }),
      submit: t("customers.connection.act.confirm", { defaultValue: "Confirm" }),
      danger: false,
    };
  }
  return {
    title: t("customers.newConnects.act.cancelTitle", {
      defaultValue: "Cancel {{subject}}",
      subject: target.subject,
    }),
    field: t("customers.newConnects.act.cancelReason", { defaultValue: "Why" }),
    submit: t("customers.connection.act.cancel", { defaultValue: "Cancel…" }),
    danger: true,
  };
}

function runAct(act: BuildRowAct, id: string, text: string, client: ApiClient): Promise<unknown> {
  if (act === "hold") return holdConnection(id, text, client);
  if (act === "waitingOn") return setWaitingOn(id, text, client);
  return cancelConnection(id, text, client);
}

/**
 * The one dialog behind the row menu and the bulk bar.
 *
 * ⚠ **IT IS `FormModal`, THE KIT'S OWN FORM DIALOG, AND NOT `ConfirmDialog`.**
 * All three acts REQUIRE a sentence the server stores — `holdConnection` and
 * `cancelConnection` take a `reason` (*"an unattributed hold is half a hold,
 * and the reason is what the WAITING ON column then carries"*) and
 * `setWaitingOn` takes the text that becomes the column — so this is a form
 * with one field, not a yes/no. `ConfirmDialog` has no field slot, and adding
 * a bare `<input>` beside one would be a second dialog grammar.
 *
 * ⚠ **ONE REQUEST PER BUILD, IN SEQUENCE.** There is no bulk endpoint for
 * these three acts — `POST /connections/{id}/hold` and its two siblings act on
 * one build each — so twelve ticked rows are twelve requests. Stated rather
 * than hidden behind a spinner that looks atomic; `paymentsBulk` takes the
 * same posture on the same shape.
 */
export function BuildActDialog(props: {
  target: BuildActTarget | null;
  onClose: () => void;
  onDone?: () => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [text, setText] = useState("");

  if (props.target === null) return null;
  const target = props.target;
  const copy = actCopy(target, translate);
  // The sentence is REQUIRED because the server requires it; the schema says
  // so rather than the button quietly doing nothing when it is empty.
  const schema = z.object({ text: z.string().trim().min(1, copy.field) });

  return (
    <div data-build-act={target.act}>
      <FormModal
        title={copy.title}
        schema={schema}
        values={{ text }}
        submitLabel={copy.submit}
        submitVariant={copy.danger ? "danger" : undefined}
        onClose={() => {
          setText("");
          props.onClose();
        }}
        onSubmit={async () => {
          for (const id of target.ids) {
            await runAct(target.act, id, text, client);
          }
          for (const prefix of WORKLIST_QUERY_PREFIXES) {
            void queryClient.invalidateQueries({ queryKey: [prefix] });
          }
          setText("");
          props.onDone?.();
          return { ok: true };
        }}
      >
        <TextField id="text" label={copy.field} value={text} onChange={setText} required />
      </FormModal>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-150-BRC09 · 05-prototype/new-connect-detail-2026-09-28/00-list.png
//         (the drawing of record) and its README · B14 rules 12, 15, 21, 31,
//         33, 42, 43, 44 · BR-SHL-025
// generated: 2026-09-28 by lane LIST
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions: E3 **THREE OF THE FIVE DRAWN TILES ARE FACTS AND NOT CONTROLS** —
//         `GET /connections` declares one filter dimension (`state`) and the
//         other three tiles name no value in its vocabulary. Each reason is
//         written out in §1; none is a judgment that could go either way ·
//         E3 **THE TILE'S SELECTED/PRESSABLE PAIR BELONGS ON `KPIStrip`** and
//         that file is the components lane's. This composes the kit's own
//         classes so nothing looks different, and folds into `KPIStrip` the day
//         the pair lands — REPORTED · E3 **`closeOutstanding` AND `release` ARE
//         NOT IN THE ROW MENU.** The drawing names three acts and these are not
//         among them; `closeOutstanding` additionally reads a field the list
//         row does not carry, which `buildRowActsReadOnlyState` asserts ·
//         E3 **THE BULK ACTS ARE ONE REQUEST PER BUILD** — no bulk endpoint
//         exists for the three, and the bar says how many rows can take the act
//         before it runs · E3 **EIGHT CATALOGUE KEYS ARE NEW AND RENDER THEIR
//         ENGLISH `defaultValue`** (`customers.newConnects.act.*`,
//         `customers.newConnects.bulk.*`). This lane may not edit
//         `src/i18n/locales/`; they are handed to the text lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
