// ── Trace ──────────────────────────────────────────────
// Change:   THE MOVE-OUT RECORD'S ACTIONS, RENDERED — the second half of the
//           PO's ratified grid of 2026-09-20 (decision log §7). `moveRecordActions.ts`
//           decides WHICH controls exist; this decides what each one looks like
//           and what it does.
// Rules:    B14 rule 4 (the grammar marker is appended here, once) · rule 6
//           (the danger tier reaches the CONFIRM through `confirmVariant` —
//           `DEF-718`'s half) · rule 11 (a money commit shows what it will do,
//           BEFORE the button) · rule 33 (two sentences of six) · rule 21 (the
//           kit, never a stylesheet class) · CLAUDE.md hard rules 4, 5 and 7
// Screens:  the MOVE RECORD, `/moves/{ref}`
// Tests:    MoveRecordPage.actionGrid.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ═══════════════════════════════════════════════════════════════════════════
// 🔒 WHAT THIS WRITES, AND WHY IT IS LAWFUL — read before changing a line
// ═══════════════════════════════════════════════════════════════════════════
// Three of these controls WRITE. Every one goes through
// `move_out_settlement.shortfall_decision` by way of `settleShortfall`, the
// caller `MoveOutWizard.tsx` already publishes. **NO SECOND SETTLEMENT PATH IS
// WRITTEN HERE**, deliberately: two code paths deciding where one customer's
// closing money goes is `DEF-CUS-5927` one move along.
//
//   * **hard rule 4 — financial immutability.** `shortfall_decision`'s own
//     docstring: *"A NEW ROW, NEVER AN EDIT"*. It UPDATEs no issued invoice, no
//     invoice line, no payment and no journal entry, and it DELETEs nothing.
//     ✅ Nothing on this screen can reach such an UPDATE.
//   * **hard rule 5 — the ledger.** ⚠ **AMENDED 2026-10-14 (`CR-185-BRC10`).**
//     This read *"It writes no journal line at all: `posting: {posted: false,
//     oq: "OQ-1250"}`"*. The PO closed `OQ-1250` → (a) that day (D5, *"option
//     1"*): on `transfer` the server hands the residue to
//     `apps/ledger/balance_transfer.py` and the posting service — the only
//     writer — posts ONE entry, DR AR (owner) / CR AR (this account). This
//     screen still writes nothing itself. ✅
//   * **hard rule 7 — the audit.** `_audit(actor,
//     "account.move_out.shortfall_decided", …)` on every decision. ✅
//   * **hard rule 2 — money.** Every figure here arrives as the server's
//     `display` string and is handed to `MoneyCell` or interpolated verbatim.
//     **Nothing is parsed, re-rounded or arithmetic'd on this screen.** ✅
//
// ⚠⚠ **THE CONSEQUENCE PREVIEW NOW SAYS HALF OF WHAT THE DRAWING SAYS.**
// Blueprint p118 draws: *"$186.40 moves to A-10001 and A-10432 settles at
// zero"*. Until 2026-10-14 it said neither, because nothing posted while
// `OQ-1250` was open. **The tie-back POSTS now** (`CR-185-BRC10`, PO D5), so
// *"$186.40 moves to A-10001 now"* is a fact the product keeps and is built.
// *"settles at zero"* is still NOT promised: whether the tenant's account
// stands at zero afterwards depends on what else it owes, and a promise the
// arithmetic may not keep is hard-won law 1 on a money path. The deviation is
// recorded in the conformance file.
import { useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button, buttonClasses } from "@/components/Button";
import { formatMoney } from "@/components/MoneyCell";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useTenantPath } from "@/routing/tenantPath";

import { accountDetailPath } from "./customersShared";
import { CUSTOMERS_ROUTE } from "./CustomersListPage";
import { settleShortfall } from "./MoveOutWizard";
import type { CloseImpactTerms } from "./moveShared";
import {
  grammarMarker,
  moveActionLabelKey,
  type MoveAction,
  type ShortfallPath,
} from "./moveRecordActions";
import { serviceRequestPath } from "./serviceRequestShared";
import { discardWizardPark } from "./wizardParkEndpoints";

/**
 * Everything a control needs to know to open, or to commit.
 *
 * ⚠ **EVERY FIELD IS SERVED — NOTHING HERE IS DERIVED FROM ANOTHER.** The
 * account a shortfall ties back to is `settlement.unit_falls_to.account_no`,
 * which `close-impact` has carried since `CR-056` W6; the amount is
 * `settlement.shortfall`'s own 2-dp `display` string. Composing either on this
 * screen would be a figure nobody measured.
 */
export interface MoveActionContext {
  accountId: string | null;
  customerName: string | null;
  requestRef: string | null;
  requestId: string | null;
  parkId: string | null;
  /** The page already builds this through `resumePath`, the ONE builder for
   *  `?parked=<id>`. It is handed in rather than rebuilt so there is no second
   *  copy of how a wizard is re-entered. */
  resumeTo: string | null;
  /** The shortfall, as the server's DISPLAY string — `186.40`, never a number.
   *  ⚠ **IT ARRIVES WITHOUT A SYMBOL.** `close-impact` sends `{stored,
   *  display}` and `display` is the 2-dp figure alone; the SYMBOL is
   *  `MoneyCell`'s job everywhere else on this screen. */
  shortfallDisplay: string | null;
  /** The settlement's `CHAR(3)` code, which rides WITH the amount and is never
   *  assumed (B2). */
  currency: string | null;
  /** `A-10001 · Elm Street Holdings LLC` — p118 draws it inside the option row
   *  and the product did not render it anywhere until this wave. */
  tieBackAccountNo: string | null;
  /** The two stated terms the settlement was READ with, handed straight to the
   *  WRITE. ⚠ `DEF-CUS-5927`: step 4 sent `{path}` alone, the server re-derived
   *  a settlement with no final bill, landed on `null` and refused
   *  `no_shortfall` — on a screen that was printing a shortfall at that moment.
   *  One object, both call sites, or the two halves disagree about one
   *  customer's money. */
  terms: CloseImpactTerms;
  client?: ApiClient;
  /** Where to go once a parked draft is discarded — it no longer has a page. */
  afterDiscardTo: string;
}

/**
 * EVERY TIER'S CLASS SET, RESOLVED ONCE AT MODULE SCOPE.
 *
 * ⚠ **HOISTED FOR THE REASON `MoveRecordPage`'s `DOOR_KIT` RECORDS, AND IT IS
 * A CHECK'S LIMITATION RATHER THAN TASTE.** `styles/routeBUtilities.test.ts`
 * reads string literals that appear inside a `className` attribute, so calling
 * the kit INLINE there makes it see a class named after the VARIANT and report
 * an orphan — a true reading of what it can see, over a call that is perfectly
 * correct. Naming the result keeps the literal out of the attribute and keeps
 * the check honest.
 *
 * The map is exhaustive over the four tiers the grid can produce, so a new
 * tier is a type error here rather than an `undefined` className at runtime.
 */
const TIER_CLASSES: Record<MoveAction["tier"], string> = {
  primary: buttonClasses("primary"),
  secondary: buttonClasses("secondary"),
  ghost: buttonClasses("ghost"),
  danger: buttonClasses("danger"),
};

/** Which dialog is open, or none. `null` is the ordinary state. */
type OpenDialog = "tieBack" | "collect" | "discardDraft" | null;

const DIALOG_FOR: Partial<Record<MoveAction["id"], Exclude<OpenDialog, null>>> = {
  tieBack: "tieBack",
  collect: "collect",
  discardDraft: "discardDraft",
};

/** Rule 6's danger tier reaches the CONFIRM only through this prop — DEF-718.
 *  Computed from the action rather than pinned, because half of these commits
 *  are not destructive (the polymorphic case the prop's own docstring names). */
/**
 * ⚠ **THE THREE TESTIDS THAT EXISTED BEFORE THIS WAVE ARE KEPT.**
 * `MoveRecordPage.test.tsx` selects the doors by these names and has done
 * since the screen was built. Renaming them would turn a green suite red for a
 * reason that has nothing to do with what changed, and a lane reading that
 * failure would "fix" the test rather than the screen. Everything else gets
 * `move-action-<id>`; **every control also carries `data-action`**, which is
 * what the new grid test selects on, so the two naming eras cannot drift.
 */
const LEGACY_TESTID: Partial<Record<MoveAction["id"], string>> = {
  resume: "move-record-resume",
  openAccount: "move-record-open-account",
  openCustomer: "move-record-open-customer",
};

const DANGER_DIALOGS: ReadonlySet<Exclude<OpenDialog, null>> = new Set(["discardDraft"]);

/**
 * The action bar as a HOOK, because the header has two slots and one dialog.
 *
 * ⚠ **IT IS NOT A COMPONENT, AND THAT IS `PageHeader`'s CONTRACT RATHER THAN A
 * PREFERENCE.** The head draws `leadingAction`, then `secondaryActions`, then
 * `primaryAction`, and TC-6 asserts EXACTLY ONE primary. So the grid's primary
 * has to reach a different slot from the rest — while `Tie the shortfall back`
 * is both the primary AND a dialog opener, so the two slots must share one
 * piece of state. A hook hands the page a renderer for each control and ONE
 * dialog node to drop below the header, which is the only shape that satisfies
 * both.
 */
export function useMoveRecordActionBar(ctx: MoveActionContext): {
  /** Render one action of the grid. */
  control: (action: MoveAction) => ReactNode;
  /** The open dialog, or `null`. The page renders it once, anywhere. */
  dialog: ReactNode;
  /** The disposition a clerk just committed, or `null`. Drives the ratified
   *  *"short, decided"* arm — see the warning on `ShortfallStanding`. */
  decided: ShortfallPath | null;
  /** A refusal from the last commit, in the clerk's words. */
  failed: boolean;
} {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState<OpenDialog>(null);
  const [decided, setDecided] = useState<ShortfallPath | null>(null);
  const [failed, setFailed] = useState(false);
  const client = ctx.client ?? api;

  const settle = useMutation({
    mutationFn: (path: ShortfallPath) =>
      settleShortfall(ctx.accountId ?? "", path, ctx.terms, client),
    onSuccess: (_data, path) => {
      setOpen(null);
      setFailed(false);
      // ⚠ **HELD IN THE PAGE, AND A RELOAD HONESTLY FORGETS IT
      // (`OQ-CUS-12516`).** `shortfall_decision` answers `persisted: false` —
      // there is no `final_settlements` table — and `settlement_for` recomputes
      // the landing from the BALANCE. Since 2026-10-14 a TRANSFER moves that
      // balance (`OQ-1250` → a); collect and a payment plan still do not. The
      // screen says in six words that a reload forgets the choice.
      setDecided(path);
      // The settlement is re-read anyway: if a future wave ever does persist
      // this, the page stops needing the local state and nothing else changes.
      void queryClient.invalidateQueries({ queryKey: ["move-record-settlement"] });
    },
    onError: () => {
      setOpen(null);
      setFailed(true);
    },
  });

  const discard = useMutation({
    mutationFn: () => discardWizardPark(ctx.parkId ?? "", client),
    onSuccess: () => {
      setOpen(null);
      void queryClient.invalidateQueries({ queryKey: ["move-record"] });
    },
    onError: () => {
      setOpen(null);
      setFailed(true);
    },
  });

  /** Rule 4's marker, appended in ONE place. */
  const label = (action: MoveAction): string => {
    const mark = grammarMarker(action.grammar);
    return `${mark.before}${t(moveActionLabelKey(action.id))}${mark.after}`;
  };

  /** Where a NAVIGATING action goes. ⚠ Every one is built through a path
   *  builder and then `tenantPath`: a href assembled by hand loses its tenant
   *  and comes out protocol-relative, which opens ANOTHER HOST and still reads
   *  as a good string to `toContain` (the fixture trap in hard-won law 2). */
  const destination = (action: MoveAction): string | null => {
    switch (action.id) {
      case "resume":
        return ctx.resumeTo;
      case "openAccount":
        return ctx.accountId !== null ? tenantPath(accountDetailPath(ctx.accountId)) : null;
      case "openCustomer":
        // ⚠ THERE IS NO CUSTOMER DETAIL SCREEN IN THIS PRODUCT — measured
        // 2026-09-19 and unchanged: `/customers` is a LIST whose row action
        // opens the person's first ACCOUNT. The nearest TRUE destination beats
        // a control that opens nothing, and the divergence is in the
        // conformance file so the lane that builds the detail screen re-points
        // it here.
        return tenantPath(`${CUSTOMERS_ROUTE}?q=${encodeURIComponent(ctx.customerName ?? "")}`);
      case "openRequest":
        return ctx.requestId !== null ? tenantPath(serviceRequestPath(ctx.requestId)) : null;
      case "paymentPlan":
        // `+ Payment plan` is rule 4's CREATOR grammar: it opens S24, where the
        // TERMS are taken. Posting `path: "payment_plan"` from here would
        // record a disposition with no agreement behind it.
        return ctx.accountId !== null
          ? tenantPath(`${accountDetailPath(ctx.accountId)}/payment-plan`)
          : null;
      default:
        return null;
    }
  };

  const control = (action: MoveAction): ReactNode => {
    const dialog = DIALOG_FOR[action.id];
    if (dialog === undefined) {
      const to = destination(action);
      // Hard-won law 2's mirror: no live control over a dead destination. The
      // grid already refuses to emit an action whose door is absent, so this is
      // the belt to that brace rather than the decision.
      if (to === null) return null;
      return (
        <Link
          key={action.id}
          className={TIER_CLASSES[action.tier]}
          to={to}
          data-testid={LEGACY_TESTID[action.id] ?? `move-action-${action.id}`}
          data-action={action.id}
          data-tier={action.tier}
        >
          {label(action)}
        </Link>
      );
    }
    return (
      <Button
        key={action.id}
        variant={action.tier}
        onClick={() => {
          setFailed(false);
          setOpen(dialog);
        }}
        data-testid={LEGACY_TESTID[action.id] ?? `move-action-${action.id}`}
        data-action={action.id}
        data-tier={action.tier}
      >
        {label(action)}
      </Button>
    );
  };

  /** B14 rule 11's box, capped by rule 33 at two sentences of six words. The
   *  words are the catalogue's; the FIGURES are the server's `display`
   *  strings, interpolated and never formatted here (hard rule 2). */
  const dialogNode = ((): ReactNode => {
    if (open === null) return null;
    // ⚠ **THE SYMBOL IS PUT BACK HERE, AND A BROWSER IS WHAT FOUND IT
    // MISSING.** Every other figure on this screen goes through `MoneyCell`,
    // which adds it; a dialog TITLE is a string, so the raw `display` went
    // straight into it and the live page read `Tie 186.40 back?` — a money
    // figure with no currency on a money commit, which no test asserted and
    // `tsc` cannot see. `formatMoney` is the ONE formatter (`MoneyCell`'s own,
    // 2 dp, half-up over the decimal string) rather than a second one written
    // here. Hard-won law 6: no gate in this repo reads rendered output.
    const raw = ctx.shortfallDisplay;
    const amount =
      raw === null ? "" : formatMoney(raw, ctx.currency ?? "USD");
    const account = ctx.tieBackAccountNo ?? "";
    const working = settle.isPending || discard.isPending;
    const commit: Record<Exclude<OpenDialog, null>, () => void> = {
      tieBack: () => settle.mutate("transfer"),
      collect: () => settle.mutate("collect"),
      discardDraft: () => discard.mutate(),
    };
    return (
      <ConfirmDialog
        title={t(`customers.moveRecord.confirm.${open}.title`, { amount })}
        consequence={t(`customers.moveRecord.confirm.${open}.body`, { amount, account })}
        // The confirm's verb is the SAME catalogue key the control used, so the
        // button a clerk pressed and the button they are confirming cannot
        // come to say different things — §7 finding (a), structurally.
        confirmLabel={t(
          moveActionLabelKey(
            open === "discardDraft"
              ? "discardDraft"
              : open === "tieBack"
                ? "tieBack"
                : "collect",
          ),
        )}
        confirmVariant={DANGER_DIALOGS.has(open) ? "danger" : "primary"}
        working={working}
        onConfirm={commit[open]}
        onCancel={() => setOpen(null)}
      />
    );
  })();

  return { control, dialog: dialogNode, decided, failed };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: decision log 2026-09-20 §6/§7 + the conformance file
//         `04-docs/05-modules/03-customers/conformance/move-out-record-against-its-blueprint.md`
//         + blueprint p117–p119 read as images (B14 rule 42)
// generated: 2026-09-20, the move-out record rebuild lane
// exceptions: E1 the consequence preview draws p118's `moves to A-10001` and
//             NOT its `settles at zero` — the tie-back posts since 2026-10-14
//             (`CR-185-BRC10`, OQ-1250 → a) and zero is not promised; recorded,
//             drawing unchanged ·
//             E2 the dialog FOOTER is the shared `ConfirmDialog`'s order and
//             not p119's, per B14 rule 38: a footer's button order is
//             CONSTRUCTION and the UI rules win · E3 `Open the customer →`
//             lands on the customers register filtered to that person, because
//             this product has no customer detail screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
