// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-CUS-5994` (PO 2026-09-20) — the PINNED PANEL is removed and a
//           parked draft becomes a ROW of its own flow's list. Verbatim:
//           *"remove it - it is anyway in the list so we dont need it
//           sepretely - if it is not in list add it"*. It AMENDS the ruling
//           below, which chose the tab and left the placement open.
//           CR-035 · AMENDMENT 1 — **the "Waiting on" TAB is folded into the
//           six worklists.** PO 2026-08-26, verbatim: *"We dont need seperate
//           tab for this - this will be directly on each request Request,
//           Connect, Move IN move Out, Trasnfr, Disconnect - seperate queue not
//           reequired"*, then **"yyes"**.
// Rules:    BR-SHL-048 (a parked wizard changes nothing until it is executed —
//           and a worklist is not the unit, the premises or the account, which
//           is why this placement is lawful) · BR-SHL-046 (ONE declared step
//           list drives the STEP line and where a resume lands) · BR-SHL-025
//           (a control that cannot act is disabled with its reason) ·
//           BR-SHL-010 (a capability not declared is not rendered) ·
//           BR-SHL-011 (this panel owns NO query string) · BR-SHL-034 (one
//           date formatter) · B14 rule 6 (danger tier on a destructive
//           commit) · rule 15 (icons for row actions) · rule 21 (Tailwind
//           utilities, NO stylesheet class — registered in
//           styles/route-b-migrated.txt)
// Story:    US-CUS-031 (EP-CUS-11) — RE-POINTED 2026-08-26, see below
// Tests:    parkedDrafts.dom.test.tsx · ../../../../10-scripts/render-checks/
//           cr035-park-clickthrough.mjs · cr035-resume-clickthrough.mjs
// Impacts:  AccountsListPage.tsx (the five panel mounts come OUT) · the five
//           worklist tabs, which render the drafts as rows and import the three
//           controls here · MoveOutsTab.tsx + MoveRecordPage.tsx, which import
//           `resumePath` and MUST keep working · wizardPark.ts
//           (`parkedHomePath`) · the five wizards' `onParked` destination
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · THE PANEL IS GONE. A DRAFT IS A ROW OF ITS OWN FLOW'S LIST.
// ══════════════════════════════════════════════════════════════════════════
// **PO ruling 2026-09-20, verbatim:** *"remove it - it is anyway in the list so
// we dont need it sepretely - if it is not in list add it"*.
//
// This **AMENDS `CR-035` amendment 1** (PO 2026-08-26, *"We dont need seperate
// tab for this - this will be directly on each request Request, Connect, Move
// IN move Out, Trasnfr, Disconnect - seperate queue not reequired"*). That
// ruling put parked work ON EACH FLOW TAB and said nothing about WHERE on the
// tab; this file chose a pinned panel and today's ruling settles the placement
// it left open. **The supersession chain is `CR-035` → amendment 1 (2026-08-26)
// → this (2026-09-20, `DEF-CUS-5994`)**, and only the PLACEMENT moves: a draft
// still belongs to its own flow and there is still no ninth queue.
//
// ⚠ **THE ARGUMENT THIS FILE USED TO MAKE IS KEPT, BECAUSE IT WAS NOT SILLY
// AND BECAUSE KNOWING WHY IT FELL IS WORTH MORE THAN DELETING IT.** §1 read:
//
//   > *"(A) Merge the drafts into the tab's own `DataTable` as extra rows.
//   > Rejected, and not on taste. A `MoveInRow` and a `WizardParkRow` share not
//   > one field: the table's columns are `move_in_date`, `state`, `deposit`,
//   > `customer` — every one of which a draft has NEVER SET, so four of eight
//   > cells would render an em-dash … It would also fold drafts into
//   > `totalRows`, which is exactly the lie requirement 2 forbids."*
//
// **TWO FACTS OVERTOOK IT, AND NEITHER IS AN OPINION.**
//
//   1. **The tables already render a row with nothing in those cells, and it
//      is the DRAWING'S OWN ROW.** B18 §5.5.2 draws `SR-26-0012` with account
//      *"— draft"*, unit *"—"* and *"Step not recorded"*, and `BR-CUS-1077`
//      put it on the Move-ins list on 2026-09-16 with a NAMED ABSENCE in each
//      empty cell rather than a dash. So *"four cells would be empty"* stopped
//      being an argument against a row the day the list learned to say WHY a
//      cell is empty.
//   2. **The Move-outs list did it, on 2026-09-19, and it works.** PO ruling
//      (*"yes"*): the window widened to `∪ wizard_parks WHERE flow='move_out'`
//      and a parked move-out became a row with a real step. The panel above it
//      was pure duplication from that morning — which is the half of this
//      defect nobody filed until the PO looked at the screen.
//
// ⚠ **AND THE ONE CONSTRAINT SURVIVES INTACT — the count does not lie.** The
// old §2 was right and is honoured by the OTHER half of this change rather than
// abandoned: `total` is still the SERVER's figure over the whole window, and
// the window now genuinely contains the drafts. Nothing is spliced into a
// server-paged list in JavaScript, and no number on any tab is a sum of two
// numbers computed in two places. Each list unions in SQL (`NFR-3`, `NFR-5`).
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · WHAT THIS FILE IS NOW — the controls, not the surface
// ══════════════════════════════════════════════════════════════════════════
// `WIZARD_PARK_FLOW_SURFACE`, `resumePath`, `stepOf`, `waitingOnLabel` and
// `flowLabel` are UNCHANGED and are why this file still exists: they are the
// BR-SHL-046 contract that stops a `3 of 9` on a list disagreeing with a
// `3 of 9` in the wizard, and `resumePath` is the ONE builder for `?parked=`.
// **`MoveOutsTab` and `MoveRecordPage` both import `resumePath` today**, so
// deleting this file with its panel would have taken a live resume door with
// it (`DEF-CUS-3653`: before retiring anything, grep for its CONSUMERS,
// because an absence is invisible to every check this repo has).
//
// What is NEW is the three row controls the five worklists share —
// `ParkedBadge`, `ParkedDraftActions` and `ParkedWhyCell`. **They exist because
// removing a surface does not remove what was ON it**, and one of those things
// was a capability that lived NOWHERE else: see `ParkedDraftActions`.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · MINE / EVERYONE'S IS STILL GONE, AND THAT IS STILL THE RULING
// ══════════════════════════════════════════════════════════════════════════
// The old ninth tab opened on `?mine=1` with a toggle, because BR-SHL-048's
// phrase *"the clerk's own 'Waiting on' list"* was read as a FILTER. Amendment
// 1 settled it in the other direction — it *"dissolves the mine-versus-
// everyone's question entirely … it meant THERE AND NOWHERE ELSE"*. Every list
// therefore shows every draft for its flow, and `Parked by` on the row is what
// tells a clerk covering the desk whose it is. That line is why
// `parked_by_name` had to be ADDED to the move-out row when the panel went.
//
// ══════════════════════════════════════════════════════════════════════════
// 4 · WHAT THE PANEL SAID AND THE ROWS DELIBERATELY DO NOT
// ══════════════════════════════════════════════════════════════════════════
// The panel's one remaining sentence — *"Nothing here has changed anything
// yet."* — is NOT carried onto the rows. B14 rule 33 puts RATIONALE at ZERO
// words on screen, and it is the kind of line the PO has struck off six
// screens. The STATE cell says `Draft` or `Parked` in one word, the STEP cell
// shows how far the clerk got, and `BR-SHL-048` is where the rule lives for
// anyone who needs the reason. **A clerk needs to know which rows have not
// happened; they do not need to be told why in a sentence above the table.**
//
// ⚠ **THE AGE IS STILL THE FEATURE, AND STILL THE SERVER'S FIGURE.**
// BR-SHL-048 (c) accepts a cost in writing — *"a parked move-out is invisible,
// so the account KEEPS BILLING"* — and names the remind-on date and the visible
// age as its only mitigation. `age_days` is rendered from the response and
// never from `Date.now()`, so two clerks in two time zones read one number.
// **And no threshold is invented:** BR-SHL-047's limit is MOOT under
// BR-SHL-048 and no replacement was ruled, so a row prints the number and
// refuses nothing.
//
// ⚠ **NOTHING SENDS THE REMINDER.** There is no email or SMS adapter wired to
// it. A bell icon here would be hard-won law 1 wearing a costume — and the
// SENTENCE that used to say so was deleted on 2026-09-19 for being rationale
// AND for being measurably false about the release (the provider seam exists;
// it is this TENANT that has nothing connected).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DateCell } from "@/components/DateCell";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { TrashIcon, RollBackIcon } from "@/components/icons";
import { WIZARD_PARK_REASON_COPY } from "@/components/WizardFrame";
import type { RegionalDateFormat } from "@/components/DateCell";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  MOVE_IN_STEPS,
  MOVE_IN_WIZARD_ROUTE,
  MOVE_OUT_STEPS,
  MOVE_OUT_WIZARD_ROUTE,
  flowProgress,
  moveInStoredStep,
  moveOutStoredStep,
} from "./moveShared";
import type { FlowStepDef } from "./moveShared";
import {
  NEW_CONNECT_ROUTE,
  NEW_CONNECT_STEPS,
  newConnectStoredStep,
} from "./newConnectShared";
import {
  DISCONNECT_STEPS,
  DISCONNECT_WIZARD_ROUTE,
  TRANSFER_STEPS,
  TRANSFER_WIZARD_ROUTE,
} from "./transferDisconnectShared";
import { PARKED_PARAM } from "./wizardPark";
import { WIZARD_PARK_FLOW_COPY, discardWizardPark } from "./wizardParkEndpoints";
import type { WizardParkFlow, WizardParkRow } from "./wizardParkEndpoints";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/** ONE query key per flow, so discarding a move-in draft does not silently
 *  refetch the disconnect tab's panel — and so the prefix `["wizard-parks"]`
 *  still invalidates every one of them at once. */
export const parkedDraftsQueryKey = (flow: WizardParkFlow) => ["wizard-parks", flow] as const;

/**
 * Flow → the flow's OWN declared step list and its OWN wizard route.
 *
 * ⚠ **BR-SHL-046 IS THE REASON THIS MAP EXISTS AT ALL.** The rule's durable
 * half: *"the list's progress bar and the wizard's step bar must be driven by
 * ONE declared step list. Two literals that happen to agree today is exactly
 * the state this defect was found in, and it recurs the day a seventh step
 * appears."* The STEP line below reads these lists — the SAME arrays the five
 * wizards render their rails from — so `3 of 9` on this row and `3 of 9` in the
 * wizard cannot drift, and a conditional step (move-out's `shortfall`) counts
 * on both surfaces because it is one of the six on both.
 *
 * The route is here for the same reason: Resume must open the wizard the draft
 * belongs to, and a second place naming `/transfers/new` is a second place to
 * get it wrong.
 */
export const WIZARD_PARK_FLOW_SURFACE: Record<
  WizardParkFlow,
  {
    steps: readonly FlowStepDef[];
    route: string;
    /**
     * ⚠ **THE OLD→NEW MAP FOR A FLOW WHOSE STEP LIST HAS CHANGED SHAPE,
     * DECLARED HERE SO BOTH SURFACES READ ONE ANSWER.** A stored step is an
     * INDEX into the list as it stood when the draft was parked. Where a flow
     * has since MERGED steps, the clamp that keeps a number in range is right
     * by luck on most values and wrong on the merged ones — so the flow
     * declares the map, and the list's `stepOf` and the wizard's resume both
     * apply it before anything clamps. Absent means the list has not changed
     * shape and the stored number is already the right index.
     */
    storedStep?: (stored: number, row?: WizardParkRow) => number;
  }
> = {
  // ⚠ **SEVEN BECAME FOUR ON 2026-10-05 (`CR-171-BRC10` P2.15).** The map is
  // not idempotent, so it reads the ROW as well as the number: a draft the
  // four-step form wrote carries `values.step_shape = "four"` and is passed
  // through unchanged (`moveShared.moveInStoredStep`).
  move_in: { steps: MOVE_IN_STEPS, route: MOVE_IN_WIZARD_ROUTE, storedStep: moveInStoredStep },
  // ⚠ **SIX BECAME FOUR ON 2026-09-24 (PO: *"i okay with these steps"*), so a
  // draft parked before today carries a number off the old list.**
  // `moveOutStoredStep` is the explicit map; without it a draft parked on the
  // old step 4 — *The shortfall* — opens on *Review & close*, one step PAST
  // the money. Its own docstring carries the six-row table.
  move_out: {
    steps: MOVE_OUT_STEPS,
    route: MOVE_OUT_WIZARD_ROUTE,
    storedStep: moveOutStoredStep,
  },
  transfer: { steps: TRANSFER_STEPS, route: TRANSFER_WIZARD_ROUTE },
  disconnect: { steps: DISCONNECT_STEPS, route: DISCONNECT_WIZARD_ROUTE },
  // ⚠ **EIGHT BECAME FIVE ON 2026-09-28 (`CR-150-BRC09`, PO: *"8 steps →
  // 5"*), so every draft parked before today carries a number off the old
  // list.** `newConnectStoredStep` is the PO's own map; without it a draft
  // parked on the old step 6 — *Charges* — prints `Step 6 of 5` here and
  // opens on *Review*, one step PAST the money. Its own eight-row table is in
  // `newConnectShared.tsx`.
  new_connect: {
    steps: NEW_CONNECT_STEPS,
    route: NEW_CONNECT_ROUTE,
    storedStep: newConnectStoredStep,
  },
};

/**
 * `?parked=<id>` on the flow's own wizard. ONE builder, so the resume link and
 * anything that ever links to a draft cannot disagree about the handle.
 *
 * ⚠ **THE PARAMETER IS THE TWO FIELDS IT READS, NOT A WHOLE ROW** — widened
 * 2026-09-19 for the MOVE RECORD's resume door (PO: *"We will need this action
 * on details page - 4 · Close or complete it"*). `GET /moves/{ref}` serves a
 * move-record projection and never a `WizardParkRow`, so demanding the full row
 * would have forced that page either to fake one or to build the query string
 * itself — **a second place naming `?parked=`, which is the one thing this
 * function exists to prevent.** Every existing caller passes a whole row and
 * still satisfies this, because a wider parameter accepts everything a narrower
 * one did.
 */
export function resumePath(row: Pick<WizardParkRow, "id" | "flow">): string {
  const surface = WIZARD_PARK_FLOW_SURFACE[row.flow];
  const separator = surface.route.includes("?") ? "&" : "?";
  return `${surface.route}${separator}${PARKED_PARAM}=${encodeURIComponent(row.id)}`;
}

/** `3 of 9`, through `flowProgress` — the same function the wizards' own step
 *  line uses, reading the same list. Never a literal count.
 *
 *  ⚠ **THE STORED NUMBER IS REMAPPED FIRST WHERE THE FLOW DECLARES A MAP.**
 *  This panel and the Resume link must name the same step: a row reading
 *  *4 of 4 · Review & close* whose Resume opens *Bill & deposit* is two
 *  answers to one question, and the one a clerk acts on is whichever they
 *  happened to read. Both now apply `storedStep` before anything clamps. */
export function stepOf(row: WizardParkRow): { step: number; of: number } {
  const surface = WIZARD_PARK_FLOW_SURFACE[row.flow];
  return flowProgress(surface.steps, surface.storedStep?.(row.step, row) ?? row.step);
}

/** The nine reasons in words, from `WIZARD_PARK_REASON_COPY` — the SAME nine
 *  literal catalogue keys the park panel offers, so the words a clerk chose and
 *  the words this panel prints are one vocabulary (B18 §4.2's closed list). */
export function waitingOnLabel(code: string, t: Translator): string {
  const row = WIZARD_PARK_REASON_COPY.find((entry) => entry.code === code);
  return row === undefined ? code : t(row.key, { defaultValue: row.en });
}

export function flowLabel(flow: WizardParkFlow, t: Translator): string {
  const row = WIZARD_PARK_FLOW_COPY.find((entry) => entry.flow === flow);
  return row === undefined ? flow : t(row.key, { defaultValue: row.en });
}

// ── The row controls the five worklists share ─────────────────────────────

/**
 * The `Draft` / `Parked` badge a clerk reads FIRST on an unfinished row.
 *
 * ⚠ **IT SAYS THE ONE THING THE RECORD ROWS AROUND IT NEVER SAY ABOUT
 * THEMSELVES** — that nothing here has happened. That was the pinned panel's
 * whole job (its dashed border, its own block, its `Draft` pill), and it is the
 * job that had to survive the panel: requirement 1 of `CR-035` amendment 1 is
 * *"a clerk cannot mistake a draft for a job that happened"*, and the ruling
 * that removed the panel did not remove that requirement.
 *
 * **TWO WORDS, NEVER A SENTENCE** — B14 rule 33 caps a LABEL at three words and
 * allows it no sentence. The panel's *"Nothing here has changed anything yet."*
 * is deliberately NOT carried over: it is RATIONALE, which rule 33 puts at zero
 * words on screen, and it was the kind of line the PO has struck off six
 * screens. What a clerk needs is on the row — the state, the step, and what it
 * is waiting for.
 */
export function ParkedBadge(props: { parked: boolean; t: Translator; label?: string }) {
  return (
    // ⚠ **THE TONE IS THE REQUIREMENT; THE WORD BELONGS TO THE DRAWING.**
    // `label` is how a tab hands over the word ITS blueprint draws — p117 gives
    // the Move-outs list exactly two, `Completed` and `In progress`, and
    // `DEF-CUS-5901` moved `closed` to print `Completed` for that reason. A
    // badge that overwrote `In progress` with `Draft` would be this repo
    // inventing vocabulary over a screen the PO has already read (B14 rule 41).
    // What the panel actually contributed was the WARNING TONE, and that is
    // what carries requirement 1 — *"a clerk cannot mistake a draft for a job
    // that happened"* — on a row whose neighbours are all neutral.
    //
    // The fallback is for the three lists that never drew a word for a draft at
    // all, because they never had one to draw.
    <StatusPill tone="warning">
      {props.label ??
        (props.parked
          ? props.t("customers.parkedDrafts.badgeParked", { defaultValue: "Parked" })
          : props.t("customers.parkedDrafts.badge", { defaultValue: "Draft" }))}
    </StatusPill>
  );
}

export interface ParkedDraftActionsProps {
  flow: WizardParkFlow;
  /** The draft's own id. B14 rule 31 — nothing prints it; it addresses a door. */
  parkId: string;
  /** What the clerk saw when they put it down, for the discard confirmation. */
  subjectLabel: string;
  /** Ask the TAB to open its confirm dialog. See the component's own note for
   *  why this is a callback rather than local state. */
  onDiscard: (park: { id: string; subjectLabel: string }) => void;
  /** True while THIS row's discard is in flight. */
  working?: boolean;
  /** ⚠ **THE TAB ALREADY DRAWS ITS OWN RESUME, SO THIS ONE STANDS DOWN.** The
   *  Move-outs list has carried p117's per-row `↗ Open` since 2026-09-19 and it
   *  is the control the DRAWING puts there; a second Resume beside it would be
   *  two doors onto one wizard, which is the duplication this whole ruling is
   *  about. `resumePath` is still the ONE `?parked=` builder — that tab imports
   *  it from here. */
  resumeAlreadyDrawn?: boolean;
}

/**
 * RESUME and DISCARD, for a parked draft wherever its row now lives.
 *
 * ⚠⚠ **DISCARD IS THE REASON THIS COMPONENT EXISTS AND NOT JUST A LINK.**
 * The panel carried TWO controls and only one of them was anywhere else: the
 * Move-outs tab already had a Resume on its draft rows, and **nothing anywhere
 * had a Discard.** Removing the panel without this would have deleted a live,
 * working capability from the product — a clerk could park a draft and never
 * throw it away — and **no check in this repo would have noticed**, because an
 * absence is invisible to every one of them (`DEF-CUS-3653`). That is the
 * mirror of hard-won law 2 and it is the trap in every *"remove the surface"*
 * ruling: what was ON the surface has to be re-homed before the surface goes.
 *
 * ⚠⚠ **IT HOLDS NO STATE, AND THAT IS NOT A STYLE CHOICE — A `DataTable` CELL
 * CANNOT (`DEF-CUS-6011`).** `DataTable` rebuilds `columnDefs` on every render
 * and each `cell` is a fresh arrow function, so `flexRender` hands React a NEW
 * component type every time and React unmounts and remounts the whole cell
 * subtree. Any `useState` inside a cell is therefore destroyed by the very
 * re-render that setting it caused: the first draft of this component kept
 * `confirming` locally, the click set it, the tab re-rendered, the component
 * remounted at `false`, and **the dialog never appeared at all**.
 *
 * **It would have failed in a browser exactly as it failed under vitest**,
 * which is the only reason this is a note and not a shipped defect — the
 * proof was a click, per step 2d. So the dialog lives at the TAB level, above
 * the table, and this component asks for it.
 */
export function ParkedDraftActions(props: ParkedDraftActionsProps) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();

  return (
    // ⚠ **THE MARKER IS ON THE WRAPPER, NOT ON THE CONTROLS — ALSO A FINDING.**
    // `RowAction` and `RowActionLink` take a FIXED `RowActionShape` and spread
    // nothing, so a `data-*` passed to either is accepted by TypeScript,
    // rendered by nobody, and asserted on by a test that then cannot find it —
    // hard-won law 2 in its other direction. **A `data-*` attribute belongs on
    // an element you control.**
    <span data-parked-actions={props.parkId}>
      <RowActions>
        {/* B14 rule 15 — an ICON with an accessible name, never a text link. A
            LINK and not a button: middle-click and "open in a new tab" are a
            real loss on a worklist a clerk wants to open beside the one they
            are reading. */}
        {props.resumeAlreadyDrawn !== true && (
        <RowActionLink
          label={t("customers.waitingOn.action.resume", { defaultValue: "Resume" })}
          hint={t("customers.waitingOn.action.resumeHint", {
            defaultValue:
              "Reopen this at the step it was parked at, with everything that was typed. Every check runs again before anything is created.",
          })}
          icon={<RollBackIcon />}
          to={tenantPath(resumePath({ id: props.parkId, flow: props.flow }))}
        />
        )}
        {/* B14 rule 6 — the DANGER tier, because this throws the typing away.
            IS-6: it confirms first — at the tab, see above. */}
        <RowAction
          label={t("customers.waitingOn.action.discard", { defaultValue: "Discard" })}
          icon={<TrashIcon />}
          danger
          working={props.working === true}
          onClick={() => props.onDiscard({ id: props.parkId, subjectLabel: props.subjectLabel })}
        />
      </RowActions>
    </span>
  );
}

export interface ParkedDiscardTarget {
  id: string;
  subjectLabel: string;
}

/**
 * The discard confirmation and its mutation — mounted ONCE per tab, ABOVE the
 * table, because a `DataTable` cell cannot hold state (see
 * `ParkedDraftActions`).
 *
 * ⚠ **ONE IMPLEMENTATION, FIVE TABS.** Five copies of a confirm dialog is five
 * places for the danger tier, the consequence sentence and the invalidation key
 * to drift apart. The panel was already the single place these two controls
 * lived; this keeps that property while moving where they are drawn.
 *
 * It renders nothing when nothing is being discarded, so a tab pays no layout
 * for it.
 */
export function ParkedDiscardDialog(props: {
  flow: WizardParkFlow;
  target: ParkedDiscardTarget | null;
  onClose: () => void;
  client?: ApiClient; // test seam — screens never build their own transport
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();

  const discard = useMutation({
    mutationFn: (id: string) => discardWizardPark(id, client),
    onSuccess: () => {
      // The prefix invalidates every flow's drafts at once, and the LISTS are
      // what draw them now — so the tab a clerk is standing on has to refetch
      // too, or the row they just discarded stays on screen until they reload.
      void queryClient.invalidateQueries({ queryKey: ["wizard-parks"] });
      for (const prefix of WORKLIST_QUERY_PREFIXES) {
        void queryClient.invalidateQueries({ queryKey: [prefix] });
      }
    },
  });

  if (props.target === null) return null;
  const target = props.target;

  return (
    <>
      {/* IS-6 / B14 rule 6 — a destructive commit confirms, and the confirm
          names WHAT is lost. It is the clerk's own unfinished typing and
          nothing else: no record is deleted, because BR-SHL-048 means no record
          was ever made (which is why hard rule 4's immutability has nothing to
          say here). */}
      <ConfirmDialog
        title={t("customers.waitingOn.discard.title", { defaultValue: "Discard this draft?" })}
        consequence={t("customers.waitingOn.discard.consequence", {
          work: flowLabel(props.flow, translate),
          subject:
            target.subjectLabel === ""
              ? t("customers.waitingOn.discard.noSubject", { defaultValue: "nothing chosen yet" })
              : target.subjectLabel,
          defaultValue:
            "This throws away the parked {{work}} for {{subject}} and everything typed into it. Nothing else changes, because a parked job has not created anything yet.",
        })}
        confirmLabel={t("customers.waitingOn.discard.confirm", { defaultValue: "Discard" })}
        confirmVariant="danger"
        working={discard.isPending}
        onConfirm={() => {
          discard.mutate(target.id, { onSettled: props.onClose });
        }}
        onCancel={props.onClose}
      />
      {discard.isError && (
        <p role="alert" className="mt-2 text-sm text-danger-500">
          {apiErrorText(discard.error, translate)}
        </p>
      )}
    </>
  );
}

/**
 * ⚠ **THE FIVE WORKLIST QUERY PREFIXES, NAMED IN ONE PLACE.**
 * Discarding a draft has to refresh the LIST it was a row of, and a list is
 * keyed per tab. A prefix invalidation is used rather than five exact keys
 * because each tab's key carries its own page, sort and filter state — matching
 * the prefix catches whichever variant the clerk happens to be looking at.
 *
 * ⚠ **A WRONG PREFIX HERE FAILS SILENTLY**, which is why it is a named
 * constant with a test rather than five string literals at five call sites: the
 * discard succeeds, the toast appears, and the row simply stays on screen until
 * the clerk reloads. Nothing raises.
 */
export const WORKLIST_QUERY_PREFIXES = [
  "move-ins",
  "move-outs",
  "transfers",
  "disconnects",
  "connections",
] as const;

/**
 * The parked facts a row carries, in ONE cell — why it stopped, the clerk's own
 * note, when they asked to be reminded and whose desk it is on.
 *
 * ⚠ **EVERY LINE HERE WAS ON THE PANEL AND NONE OF THEM IS ANYWHERE ELSE.**
 * `Parked by` in particular is what `CR-035` amendment 1 put in place of the
 * mine/everyone's toggle it dissolved — *"it meant THERE AND NOWHERE ELSE"* —
 * so dropping it with the panel would quietly re-open a question that ruling
 * closed. It is drawn only where the server said something: an absent fact and
 * a blank line read the same once rendered (`DEF-127`).
 *
 * ⚠ **THE AGE IS THE SERVER'S FIGURE AND NEVER `Date.now()`**, so two clerks in
 * two time zones read one number — `BR-SHL-048` (c) accepts a real cost in
 * writing (*"a parked move-out is invisible, so the account KEEPS BILLING"*)
 * and names the visible age as its only mitigation.
 */
export function ParkedWhyCell(props: {
  row: {
    waiting_on?: string | null;
    park_note?: string | null;
    remind_on?: string | null;
    age_days?: number | null;
    parked_by_name?: string | null;
  };
  timeZone: string;
  /** ⚠ **THE TENANT'S OWN FORMAT, TYPED — not `string`.** `DateCell` takes
   *  `RegionalDateFormat`, and widening it here would put the cast at the one
   *  place a wrong format reaches a clerk. BR-SHL-034: ONE date formatter. */
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { row } = props;
  const waiting = (row.waiting_on ?? "").trim();
  return (
    <span className="flex flex-col gap-0.5 text-sm" data-parked-why="">
      {waiting !== "" && (
        <span className="font-semibold">{waitingOnLabel(waiting, translate)}</span>
      )}
      {typeof row.age_days === "number" && (
        <span className="text-neutral-700" data-waiting-age={String(row.age_days)}>
          {t("customers.waitingOn.col.age", { defaultValue: "Waiting" })}{" "}
          {t("customers.waitingOn.ageDays", {
            days: row.age_days,
            defaultValue: "{{days}} days",
          })}
        </span>
      )}
      {/* BR-SHL-034 — ONE date formatter, in the tenant's own format. */}
      {row.remind_on !== null && row.remind_on !== undefined && row.remind_on !== "" && (
        <span className="text-neutral-700">
          {t("customers.waitingOn.col.remindOn", { defaultValue: "Remind on" })}{" "}
          <DateCell value={row.remind_on} timeZone={props.timeZone} dateFormat={props.dateFormat} />
        </span>
      )}
      {row.parked_by_name !== null && row.parked_by_name !== undefined && row.parked_by_name !== "" && (
        <span className="text-neutral-700" data-parked-by="">
          {t("customers.parkedDrafts.parkedBy", {
            name: row.parked_by_name,
            defaultValue: "Parked by {{name}}",
          })}
        </span>
      )}
      {row.park_note !== null && row.park_note !== undefined && row.park_note !== "" && (
        <span className="max-w-prose text-neutral-700">{row.park_note}</span>
      )}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// screens: S17
// packet: CR-035 · AMENDMENT 1 (11-change-requests.md, PO 2026-08-26) ·
//         US-CUS-031 · BR-SHL-048 · BR-SHL-046 · BR-SHL-025 · BR-SHL-010 ·
//         BR-SHL-011 · BR-SHL-034 · B18 §4.2 · B19 §12.2 · B14 rules 6, 15, 21
// generated: 2026-08-26 by lane PARKFOLD
// checklist: A=n/a(no backend change — `?flow=` was already served) B✔ C✔ D✔
//         E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 **it is a PANEL, not rows in the tab's table** — §1 argues it
//         from the two row shapes and from requirement 2's count · E3 **three
//         new catalogue keys** (`customers.parkedDrafts.heading`, `.badge`,
//         `.notInTheListNote`, `.parkedBy`) carry a `defaultValue` and are
//         reported in `scratchpad/newkeys-PARKFOLD.json`; this lane may not
//         edit the eleven catalogues · E3 **no empty state and no loading
//         skeleton** — a panel that is absent when there is nothing parked is
//         the annotation the ruling asked for; a permanent empty block on five
//         tabs is not · E3 **no paging, no sort control, no column chooser and
//         so NO column-preference key** — which is why the shipped
//         `table.S17.waiting-on.columns` rows are left stored and unread rather
//         than renamed or deleted (see the lane report)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
