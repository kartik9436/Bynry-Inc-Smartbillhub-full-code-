// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · the New Connect BUILD DETAIL page — tasks 4 and 5,
//           the shell's vocabulary and the More menu.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/01-overview.png` (the
//           header) and `02-units.png` (the More menu, drawn OPEN over the
//           Units tab). Read AS IMAGES with the Read tool, B14 rule 42; the
//           per-screen notes in `00-all-screens.html` were read for their
//           NOTES and never for layout.
// Rules:    B14 rule 2 (one page header) · rule 6 (the danger tier is the
//           destructive commit alone — Cancel build, and nothing else) ·
//           rule 21 (Tailwind utilities; every file of this set is on
//           `styles/route-b-migrated.txt`) · rule 31 (no database id is ever a
//           visible value) · rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 ·
//           RATIONALE is ZERO WORDS ON SCREEN) · rule 37 (every figure drawn
//           is an ILLUSTRATION) · rule 43 (a piece of UI is a COMPONENT) ·
//           rule 44 (the drawing says WHAT is on the screen; our UI standard
//           says HOW it is built, and the standard wins) · BR-SHL-025 (a
//           control that cannot act is DISABLED WITH ITS REASON, never
//           hidden) · BR-SHL-046 (ONE declared step list) · CLAUDE.md
//           hard-won law 2 and its mirror (a refusal that is no longer true is
//           a dead control over a live screen).
// Tests:    src/features/customers/BuildDetailPage.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS PAGE EXISTS AGAIN, AND WHAT IT IS NOT ALLOWED TO BECOME
// ══════════════════════════════════════════════════════════════════════════
// On 2026-09-04 `CR-070` wave O DELETED `features/customers/ConnectionDetail
// Page.tsx` — 1,464 lines — on the PO's ruling that a build has ONE
// destination. **PO ruling 2026-09-28 supersedes that**: a full detail page
// per build. The two reasons the old page was killed still hold and are the
// shape of this one:
//
//   * **MONEY FACTS LINK TO THE ACCOUNT; NOTHING RE-IMPLEMENTS THE LEDGER.**
//     The Charges tab states figures the server states and opens the account
//     for everything else.
//   * **NO PANEL IS COPIED.** The acts, their refusals and the build's
//     vocabulary live in `features/work/buildViews.tsx`, which the premises
//     detail and the account detail already compose. This page composes the
//     same ones. `actBlockedReason` below is imported, never restated.
import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import type { PageHeaderTab } from "@/components/PageHeader";
import type { AddServiceChoiceValue } from "@/features/work/buildRecord/AddServiceChoice";
import { actBlockedReason, buildRecordQueryKey } from "@/features/work/buildViews";
import type { BuildAct } from "@/features/work/buildViews";
import type { BuildFacts } from "@/features/work/workEndpoints";

import {
  addConnectionService,
  cancelConnection,
  closeOutstandingWork,
  connectionDetailQueryKey,
  holdConnection,
  markOutstandingWork,
  releaseConnection,
  setWaitingOn,
} from "./newConnectEndpoints";
import type { ConnectionDetail } from "./newConnectEndpoints";
import type { Translator } from "./newConnectShared";

/**
 * **The screen id this page carries, on its own root element.**
 *
 * `NCT-02` is B18 §5.4.9's own id for the build detail. It was RETIRED on
 * 2026-09-04 with the page and is un-retired by the same ruling that brings
 * the page back; the router's half of that — `routing/screenIds.ts` and the
 * `App.tsx` route — is the reversal lane's, in its own commit.
 *
 * ⚠ **IT IS AN ATTRIBUTE AND NOT COPY.** B14 rule 31 keeps an internal code
 * off a clerk's screen; `data-screen` is the machine handle the walkthroughs
 * and the tests address a screen by, exactly as `SettingsPortalHelp` and five
 * siblings carry theirs.
 */
export const BUILD_DETAIL_SCREEN = "NCT-02";

// ══════════════════════════════════════════════════════════════════════════
// THE SEVEN TABS — and their ADDRESSES, which is what a test asserts
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **`?tab=` AND NOT A PATH SEGMENT, BECAUSE THAT IS THIS PRODUCT'S GRAMMAR**
// (`BR-SHL-011`, and `meteringShared.detailTabFrom`'s own docstring: *"rendered
// as URL state (`?tab=`) so every tab of every detail view is linkable"*). The
// account detail, the premises detail and the asset detail all spell it this
// way; a second grammar on one screen is how two detail pages stop looking
// like one product.

export const BUILD_TAB_IDS = [
  "overview",
  "units",
  "work",
  // CR-162-BRC10 (Q3) — the To-do tab, holding to-dos AND notes.
  "todo",
  "charges",
  "documents",
  "messages",
  "audit",
] as const;

export type BuildTabId = (typeof BUILD_TAB_IDS)[number];

/** The drawn words, in the drawn order. `en` is the fallback until the eleven
 *  catalogues carry the key — the same shape `buildViews.tsx` uses for its own
 *  vocabulary, and the reason a missing key reads as English rather than as
 *  silence. */
const TAB_COPY: { id: BuildTabId; key: string; en: string }[] = [
  { id: "overview", key: "customers.build.tab.overview", en: "Overview" },
  { id: "units", key: "customers.build.tab.units", en: "Units" },
  { id: "work", key: "customers.build.tab.work", en: "Work" },
  { id: "todo", key: "customers.build.tab.todo", en: "To-do" },
  { id: "charges", key: "customers.build.tab.charges", en: "Charges" },
  { id: "documents", key: "customers.build.tab.documents", en: "Documents" },
  { id: "messages", key: "customers.build.tab.messages", en: "Messages" },
  { id: "audit", key: "customers.build.tab.audit", en: "Audit" },
];

/**
 * ⚠ **A TAB WITH NOTHING BEHIND IT IS SHOWN AND NOT SELECTABLE — the DRAFT
 * case, `10-draft.png`.** The drawing greys Units, Work, Charges and Messages
 * on a parked draft and leaves Overview, Documents and Audit live, because
 * nothing has been created yet and the other four would open onto air.
 *
 * ⚠ **IT IS A `<button>` WITHOUT A `to`, NOT A HIDDEN TAB.** `PageHeaderTab`
 * draws a real `<Link>` when `to` is given and a `<button>` otherwise; a
 * draft's dead tabs are drawn with neither a destination nor a select handler,
 * so the strip keeps its shape and the page never rearranges itself under a
 * clerk. Hiding them would do exactly what the drawing's note forbids.
 */
export const DRAFT_LIVE_TABS: readonly BuildTabId[] = ["overview", "documents", "audit"];

/**
 * The tab strip, as `PageHeader` reads it.
 *
 * `here` is the page's own pathname — never a literal `/connections/<id>`,
 * which `G93` refuses from anywhere in `07-frontend/src` and which would be a
 * second place naming this address.
 */
export function buildDetailTabs(args: {
  t: Translator;
  here: string;
  /** A draft: four of the seven have nothing behind them yet. */
  draft: boolean;
}): PageHeaderTab[] {
  return TAB_COPY.map((tab) => {
    const live = !args.draft || DRAFT_LIVE_TABS.includes(tab.id);
    return {
      id: tab.id,
      label: args.t(tab.key, { defaultValue: tab.en }),
      to: live ? `${args.here}?tab=${tab.id}` : undefined,
    };
  });
}

/** An unknown `?tab=` falls back to the first, never errors (`BR-SHL-011`). */
export function buildTabFrom(raw: string | null, draft: boolean): BuildTabId {
  const wanted = (BUILD_TAB_IDS as readonly string[]).includes(raw ?? "")
    ? (raw as BuildTabId)
    : "overview";
  return draft && !DRAFT_LIVE_TABS.includes(wanted) ? "overview" : wanted;
}

// ══════════════════════════════════════════════════════════════════════════
// THE BUILD'S FACTS, IN THE SHAPE THE SHARED REFUSALS ALREADY READ
// ══════════════════════════════════════════════════════════════════════════

/**
 * `ConnectionDetail` → `BuildFacts`, so `actBlockedReason` can be IMPORTED
 * rather than re-derived.
 *
 * ⚠ **THIS IS AN ADAPTER AND NOT A SECOND SOURCE.** The two shapes are the
 * same build read two ways — `GET /connections/{id}` and
 * `GET /premises/{id}/build` both call `connection_state()` — so every field
 * below is a rename and none is a computation. Writing a second refusal set
 * for this page is precisely what the ruling that killed the old page
 * forbids: one rule, one place, and the server refuses regardless.
 *
 * ⚠ **`home` AND `premises_id` ARE NOT ON THE CONNECTION READ.** They are
 * `null` here and the page derives the account elsewhere and says so; a
 * fabricated id would be a link to nowhere, which passes every test in this
 * repository (hard-won law 6).
 */
export function buildFactsOf(detail: ConnectionDetail): BuildFacts {
  return {
    id: detail.id,
    connection_no: detail.connection_no,
    state: detail.state,
    mode: detail.mode,
    target_activation: detail.target_activation,
    quote_total: detail.quote_total,
    waiting_on: detail.waiting_on,
    units: detail.units,
    orders: detail.orders,
    outstanding: detail.outstanding.map((todo) => ({ id: todo.id, title: todo.title })),
    home: null,
    premises_id: detail.premises?.id ?? null,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// THE ACTS — one mutation for eight doors, exactly as the shared panel does
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE ENDPOINTS ARE COMPOSED; THE MUTATION IS THIS PAGE'S BECAUSE IT
// INVALIDATES DIFFERENT KEYS.** `buildViews.BuildTab` holds a mutation of the
// same eight doors and does not export it, and it re-reads
// `buildQueryKey(host, hostId)` — a key this page has no host for. What is
// shared is what MUST be shared: the eight door functions and the ONE refusal
// set. Re-implementing `actBlockedReason` here would be the fork.

export interface BuildActRequest {
  act: BuildAct;
  text: string;
  choice?: AddServiceChoiceValue;
  /** Which to-do *Close outstanding* closes. */
  todoId?: string;
}

export function useBuildActs(args: {
  connectionId: string;
  client?: ApiClient;
  onDone?: () => void;
}) {
  const client = args.client ?? api;
  const queryClient = useQueryClient();
  // ⚠ THE ANSWER IS `unknown` ON PURPOSE: eight doors answer eight shapes and
  // this screen reads none of them — it re-reads instead, so every derived
  // figure comes back from the server rather than being patched here.
  return useMutation<unknown, unknown, BuildActRequest>({
    mutationFn: ({ act, text, choice, todoId }) => {
      switch (act) {
        case "hold":
          return holdConnection(args.connectionId, text, client);
        case "release":
          // `null` CLEARS *Waiting on*. A build can come off hold and still be
          // waiting for materials, so the caller says rather than the door
          // assuming; this is the usual case and it is still stated.
          return releaseConnection(args.connectionId, null, client);
        case "cancel":
          return cancelConnection(args.connectionId, text, client);
        case "waitingOn":
          return setWaitingOn(args.connectionId, text, client);
        case "addService":
          return addConnectionService(
            args.connectionId,
            { service: choice?.service ?? "", unit_id: choice?.unitId ?? null },
            client,
          );
        case "markOutstanding":
          return markOutstandingWork(args.connectionId, { title: text }, client);
        case "closeOutstanding":
          return closeOutstandingWork(args.connectionId, todoId ?? "", client);
        default:
          // ⚠ **`raiseOrder` IS NOT A ONE-PRESS ACT ANY MORE (`DEF-CUS-9177`).**
          // It POSTed `type: "Meter set"` with no form and no feedback; the
          // page now opens `BuildRaiseOrderDialog`, which asks job type,
          // service, unit and date and names the order it made. Reaching here
          // is a caller bug, refused rather than raising a guessed order.
          return Promise.reject(new Error(`build act "${act}" has its own form`));
      }
    },
    onSettled: () => {
      // RE-READ BOTH, ALWAYS — including after a refusal, because a refusal can
      // still have moved something a sibling lane wrote in the meantime. A
      // screen where one read refreshes and the other does not is worse than
      // one that never refreshes: the two halves then disagree in front of the
      // clerk who just pressed the button.
      void queryClient.invalidateQueries({
        queryKey: connectionDetailQueryKey(args.connectionId),
      });
      void queryClient.invalidateQueries({
        queryKey: buildRecordQueryKey(args.connectionId),
      });
      args.onDone?.();
    },
  });
}

// ══════════════════════════════════════════════════════════════════════════
// THE MORE MENU — seven acts, in the four drawn groups
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **SEVEN IN THE MENU AND ONE IN THE HEADER, WHICH IS EIGHT.** `BuildAct`
// has eight members and this page invents none: *Raise order* is the PRIMARY,
// because it CREATES something rather than reporting it, and the other seven
// are the menu. The drawing's own note says the same in its own words —
// *"Eight buttons in a row is not the product's header. One primary act plus a
// menu is."*
//
// ⚠ **EVERY LABEL IS ONE OR TWO WORDS — PO ruling 2026-09-28, verbatim: *"you
// need to use 1 or 2 action words - dont use 3 words"*.** So these are NEW
// keys rather than `customers.connection.act.*`, whose words are the button
// row's — *Hold…*, *Mark outstanding work* — and would break the ruling here
// while staying correct there.
//
// ⚠ **THE REFUSALS ARE THE OLD KEYS, UNCHANGED**, because they come out of
// `actBlockedReason` and they are already right and already translated in
// eleven catalogues.
//
// ⚠ **IT IS `<details>` AND NOT A `useState` POPOVER, AND THAT IS THE DESIGN
// RATHER THAN THE SHORTCUT** — the reasoning `components/RowActions.tsx`
// records for `RowActionsMore`: the platform's disclosure opens on Enter and
// on Space, is in the tab order once, closes on Escape, and **renders its
// contents under `renderToStaticMarkup`**. A `useState` menu renders as
// nothing at all there, so seven assertions about seven acts would pass over
// an empty element.

interface MenuAct {
  id: BuildAct;
  key: string;
  en: string;
  /** B14 rule 6 — the danger tier is the destructive commit and nothing else. */
  danger?: boolean;
}

/** The four drawn groups, in the drawn order, each with its drawn heading. */
export const BUILD_MENU_GROUPS: {
  id: string;
  key: string;
  en: string;
  acts: MenuAct[];
}[] = [
  {
    id: "move",
    key: "customers.build.group.move",
    en: "Move it along",
    acts: [
      { id: "hold", key: "customers.build.act.hold", en: "Hold" },
      // CR-162-BRC10 (Q3): *"Release → Resume"* — the word changes, the act
      // (`release_connection`) does not.
      { id: "release", key: "customers.build.act.resume", en: "Resume" },
      { id: "waitingOn", key: "customers.build.act.waitingOn", en: "Waiting on" },
    ],
  },
  {
    id: "change",
    key: "customers.build.group.change",
    en: "Change what is built",
    acts: [
      // CR-162-BRC10 item 7 — *Add unit*, with its services.
      { id: "addUnit", key: "customers.build.act.addUnit", en: "Add unit" },
      { id: "addService", key: "customers.build.act.addService", en: "Add service" },
    ],
  },
  {
    id: "blocking",
    key: "customers.build.group.blocking",
    en: "Say what is blocking",
    acts: [
      {
        id: "markOutstanding",
        key: "customers.build.act.markOutstanding",
        en: "Mark outstanding",
      },
      {
        id: "closeOutstanding",
        key: "customers.build.act.closeOutstanding",
        en: "Close outstanding",
      },
    ],
  },
  {
    id: "end",
    key: "customers.build.group.end",
    en: "End it",
    acts: [{ id: "cancel", key: "customers.build.act.cancel", en: "Cancel build", danger: true }],
  },
];

/** One line of the menu. Disabled carries its reason in `title` AND in
 *  `data-blocked-reason`, so a rendered-output check can read the sentence a
 *  clerk gets rather than only the `disabled` attribute (`BR-SHL-025`). */
function MenuItem(props: {
  act: MenuAct;
  reason: string | null;
  label: string;
  onPress: () => void;
}) {
  const blocked = props.reason !== null;
  return (
    <button
      type="button"
      data-act={props.act.id}
      disabled={blocked}
      title={props.reason ?? undefined}
      data-blocked-reason={props.reason ?? undefined}
      onClick={blocked ? undefined : props.onPress}
      className={
        "w-full cursor-pointer border-none bg-transparent px-3 py-2 text-left text-md " +
        "hover:bg-neutral-100 disabled:cursor-not-allowed disabled:bg-transparent " +
        (props.act.danger === true ? "text-danger-700" : "text-text") +
        " disabled:text-neutral-500"
      }
    >
      <span className="block font-semibold">{props.label}</span>
      {blocked && (
        <span className="block text-sm font-normal text-neutral-700">{props.reason}</span>
      )}
    </button>
  );
}

export function BuildMoreMenu(props: {
  t: Translator;
  build: BuildFacts;
  /** Pressed with the act a clerk chose. The page decides what asks first. */
  onPress: (act: BuildAct) => void;
  /** Which acts this menu offers. A DRAFT offers two of them (`10-draft.png`). */
  only?: readonly BuildAct[];
  /** A draft's `Re-park`, which is not a `BuildAct` and is drawn beside them. */
  extra?: { id: string; label: string; onPress: () => void }[];
  /** ⊕ `DEF-MET-9238` — why THIS person may not act at all (a read-only role),
   *  or null. It refuses every item with that reason, ahead of the build's own. */
  blockedReason?: string | null;
}) {
  const groups = BUILD_MENU_GROUPS.map((group) => ({
    ...group,
    acts: group.acts.filter((act) => props.only === undefined || props.only.includes(act.id)),
  })).filter((group) => group.acts.length > 0);

  return (
    <details className="relative inline-flex" data-build-more="">
      <summary
        className={
          "inline-flex cursor-pointer list-none items-center gap-1 border border-text " +
          "bg-surface px-3 py-1.5 font-heading text-md font-semibold text-text " +
          "[&::-webkit-details-marker]:hidden"
        }
      >
        {props.t("customers.build.more", { defaultValue: "More" })}
        <span aria-hidden="true">▾</span>
      </summary>
      <div
        className={
          "absolute right-0 top-[calc(100%+var(--space-1))] z-40 flex min-w-64 flex-col " +
          "border border-divider bg-surface py-1 shadow-md"
        }
        data-build-more-panel=""
      >
        {props.extra?.map((item) => (
          <button
            key={item.id}
            type="button"
            data-act={item.id}
            disabled={Boolean(props.blockedReason)}
            title={props.blockedReason ?? undefined}
            data-blocked-reason={props.blockedReason ?? undefined}
            onClick={props.blockedReason ? undefined : item.onPress}
            className={
              "w-full cursor-pointer border-none bg-transparent px-3 py-2 text-left " +
              "text-md font-semibold text-text hover:bg-neutral-100"
            }
          >
            {item.label}
          </button>
        ))}
        {groups.map((group) => (
          <div key={group.id} data-build-menu-group={group.id}>
            {/* A GROUP HEADING, ≤ 3 words — B14 rule 33's LABEL cap. */}
            <p
              className={
                "m-0 bg-neutral-100 px-3 py-1.5 font-heading text-xs font-semibold " +
                "uppercase tracking-label text-neutral-700"
              }
            >
              {props.t(group.key, { defaultValue: group.en })}
            </p>
            {group.acts.map((act) => (
              <MenuItem
                key={act.id}
                act={act}
                // ⚠ **THE REAL CHECK, NEVER A HARDCODED `false`.** The shared
                // predicate is the SERVER's own rules restated; a literal here
                // is the dead control CLAUDE.md hard-won law 2's mirror is
                // about, and it is what shipped as bug 11.
                reason={props.blockedReason || actBlockedReason(act.id, props.build, props.t)}
                label={props.t(act.key, { defaultValue: act.en })}
                onPress={() => props.onPress(act.id)}
              />
            ))}
          </div>
        ))}
      </div>
    </details>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// WHAT AN ACT ASKS FOR BEFORE IT RUNS
// ══════════════════════════════════════════════════════════════════════════

/** The four acts that need a sentence from the clerk before they can run. */
export const ACTS_THAT_ASK: readonly BuildAct[] = [
  "hold",
  "cancel",
  "waitingOn",
  "markOutstanding",
];

const ASK_SCHEMA = z.object({ text: z.string().trim().min(1) });

/** The words each ask uses — the EXISTING keys, which eleven catalogues
 *  already answer. Only the menu's labels needed new ones. */
const ASK_COPY: Record<string, { label: string; title: string; submit: string }> = {
  hold: {
    label: "customers.connection.act.ask.hold",
    title: "customers.build.act.hold",
    submit: "customers.build.act.hold",
  },
  cancel: {
    label: "customers.connection.act.ask.cancel",
    title: "customers.build.act.cancel",
    submit: "customers.build.act.cancel",
  },
  waitingOn: {
    label: "customers.connection.act.ask.waitingOn",
    title: "customers.build.act.waitingOn",
    submit: "customers.build.act.waitingOn",
  },
  markOutstanding: {
    label: "customers.connection.act.ask.markOutstanding",
    title: "customers.build.act.markOutstanding",
    submit: "customers.build.act.markOutstanding",
  },
};

const ASK_EN: Record<string, string> = {
  hold: "Hold",
  cancel: "Cancel build",
  waitingOn: "Waiting on",
  markOutstanding: "Mark outstanding",
};

/**
 * The one field the four text acts take.
 *
 * ⚠ **A DIALOG AND NOT AN INLINE ROW, WHICH IS THE `§5` PRECEDENT AND NOT A
 * PREFERENCE.** One field, one outcome, returns to the screen it was launched
 * from, and nobody needs to link to it — the estimate-reads shape the PO ruled
 * on when B14 rule 30 was declined. Cancel build commits it in the DANGER
 * tier (rule 6).
 */
export function BuildActPrompt(props: {
  act: BuildAct;
  t: Translator;
  onClose: () => void;
  onConfirm: (text: string) => Promise<FormSubmitOutcome>;
  /** `CR-162-BRC10` — what the clerk must read before pressing: on *Cancel
   *  build*, the accounts left open on the build's units (ruled B: listed,
   *  never closed by this press). */
  note?: ReactNode;
}) {
  const [text, setText] = useState("");
  const copy = ASK_COPY[props.act];
  const word = props.t(copy.title, { defaultValue: ASK_EN[props.act] });
  return (
    <FormModal
      title={word}
      schema={ASK_SCHEMA}
      values={{ text }}
      submitLabel={word}
      submitVariant={props.act === "cancel" ? "danger" : "primary"}
      onClose={props.onClose}
      onSubmit={() => props.onConfirm(text.trim())}
    >
      {props.note}
      <TextField
        id="build-act-text"
        label={props.t(copy.label)}
        required
        value={text}
        onChange={setText}
      />
    </FormModal>
  );
}

// ⚠ **`BuildAddServicePrompt` LEFT ON 2026-10-02 (`CR-162-BRC10` item 8).**
// *Add service* is a proper form now — `BuildAddServiceForm` in
// `BuildLifecycleForms.tsx` — so the inline chooser that sat under the menu
// has no caller and is deleted rather than left as dead UI (hard-won law 2).

// ⚠ **`BuildPrimaryAction` LEFT THIS FILE ON 2026-09-28 (`DEF-CUS-7618`).** It
// is a build panel — the header's one act — and a build panel has one home:
// `features/work/buildRecord/BuildPrimaryAction.tsx`, beside the panels the
// premises and account pages already compose (`CR-151-BRC09` §2 rule (2), B14
// rule 43, `G93` check 1). Nothing about it changed; only where it lives.

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-150-BRC09 tasks 4–5 · the ten PNGs of
//   `05-prototype/new-connect-detail-2026-09-28/`, read as IMAGES (B14 rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// exceptions:
//   (1) **EIGHT NEW CATALOGUE KEYS ARE DECLARED HERE WITH ENGLISH FALLBACKS
//       AND ARE NOT IN `src/i18n/locales/`** — the seven menu labels, the four
//       group headings, the seven tab words and `customers.build.more`. That
//       directory is the TEXT lane's this session, so the keys travel through
//       `defaultValue` exactly as `buildViews.tsx`'s own vocabulary does, and
//       the list is handed over in the lane report for `i18n_fanin.py`.
//   (2) **CLOSED 2026-10-02 (`DEF-CUS-9177`, `CR-163-BRC10` item 1).** This
//       read *"`Raise order` POSTS `type: "Meter set"` WITH NO SERVICE …
//       REPORTED"* — reported as an exception here and never filed, which is
//       how it reached the PO. `Raise order` now opens
//       `features/work/buildRecord/BuildRaiseOrderDialog.tsx`.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
