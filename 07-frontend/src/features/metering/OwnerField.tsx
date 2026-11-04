// ── Trace ──────────────────────────────────────────────
// Change:  CR-130-BRC07 part three, lane C2 — the owner control now searches
//          MASTER ACCOUNTS. It searched owner records, and nothing in the
//          product could create one.
// Defect:  DEF-MET-6155 — measured in a browser on 2026-09-22 against a real
//          PostgreSQL clone: this control drew **0 options** on the add wizard
//          AND on the edit modal, under the help text *"If they are not listed
//          yet, type the name in Owner / manager below"* — an instruction that
//          creates nothing.
// Ruling:  PO 2026-09-22, verbatim: *"why you are point is at owner id - why not
//          directly at master accoutn Id - it will solev the problem … owner IDs
//          are not required hence no screens or fucntionality for it"*.
//          Decision log 2026-09-22, "A PREMISES NAMES ITS MASTER ACCOUNT
//          DIRECTLY" — which is `OQ-790`'s own ruling (closed 2026-08-27 on
//          option (c), MASTER IMMEDIATELY) finally built.
// Rules:   BR-MET-400 (the owner IS the master account) · BR-MET-112 (nothing is
//          written until the last button) · BR-MET-151 (the free-text box stays;
//          it is what the import matches on) · B14 rule 43 (a piece of UI is a
//          COMPONENT) · B14 rule 21 (this file declares NO class and renders the
//          shared control, so it needs no Route B ledger line)
// Drawing: *Premises & Units Blueprint 2*, `WHO LOOKS AFTER IT?` — the add form
//          (p009-p011) and the edit form (p036-p041) draw the SAME row: a field
//          labelled `Owner`, a search box, and a confirmation card with a
//          `Change` control. Conformance CR-089-p008 and CR-089-p036.
// Screens: S16 the guided add (single-premise step) · PRM-01 the edit modal
// ───────────────────────────────────────────────────────
// ONE control, two screens — the same reason `JurisdictionField`, `AreaFields`
// and `ServicesAvailableField` exist: a second copy is a second place to add a
// rule to, and one of them gets forgotten. **That property is now load-bearing
// rather than tidy:** the PO's report named the add form and the edit form as
// two separate faults, and they are one file.
//
// ⚠ **THE HEADER OF THIS FILE USED TO ARGUE THAT NOT CREATING A PARTY WAS THE
// DESIGNED FLOW, AND IT WAS RIGHT UNTIL 2026-09-22.** It read: *"THIS CONTROL
// PICKS AN EXISTING PARTY AND DOES NOT CREATE ONE, AND THAT IS THE DESIGNED FLOW
// RATHER THAN A GAP … a clerk with an owner nobody has typed yet writes the NAME
// in the free-text box beside this control, and the address appears on the
// review list. That is the product working, not the product missing a feature."*
// **The reasoning was sound and the premise was false.** It rested on the
// matching review list being a surface that fills the cupboard, and
// `createPremisesOwner` — defined in `endpoints.ts` and in `metering/api.py` —
// **is called by no screen in the product**, so the cupboard could never be
// filled by anybody. The argument is quoted rather than deleted (hard-won law 1)
// because the SHAPE of it is the thing to watch for: a docstring can explain why
// an empty list is correct, convincingly, for a month.
//
// ⚠ **`createPremisesOwner` STAYING UNCALLED IS NOW A DELIBERATE ABSENCE THE PO
// HAS AGREED TO, NOT A DEAD DOOR TO WIRE.** Recorded in the decision log of
// 2026-09-22 so the next lane does not "fix" hard-won law 2 by building a screen
// the PO has said they do not want.
import { useEffect, useState } from "react";

import type { ApiClient } from "@/api/client";
import type { PremisesOwnerRow } from "@/api/endpoints";
import { getAccountDetail } from "@/api/endpoints";
import { MasterAccountSearch } from "@/features/metering/MasterAccountSearch";
import type { OwnerAccount } from "@/features/metering/premisesOwnerContract";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The value meaning *no owner named* — never `"null"`. */
export const OWNER_NONE = "";

/**
 * ⚠ **KEPT AS A NO-OP SO A CALLER CANNOT SILENTLY GO ON FETCHING A LIST NOBODY
 * FILLS.** Both consumers called this and passed the result into `owners`;
 * under the ruling there is no owner list to load, and a hook that quietly went
 * on calling `GET /premises-owners?per=200` would be one request per form for a
 * list that is always empty. It returns the empty array and fires nothing.
 *
 * It is **deprecated rather than deleted**, because deleting an export is how a
 * consumer outside this lane's blast radius goes red at merge for a reason that
 * reads like an unrelated breakage. Both consumers in this repo have stopped
 * calling it.
 *
 * @deprecated CR-130-BRC07 — a premises names its master account directly.
 */
export function usePremisesOwners(): PremisesOwnerRow[] {
  return [];
}

/**
 * **THE OWNER — a search over the tenant's MASTER ACCOUNTS.**
 *
 * `value` is the account id this form holds, or `null`. The id is what the form
 * posts; the NAME and the NUMBER are what a clerk sees (B14 rule 31).
 *
 * ⚠ **THE CONTROL TAKES AN ID AND KEEPS THE WHOLE ACCOUNT, WHICH IS WHY IT
 * FETCHES ONCE.** Both forms hold an id in their own state — the create form
 * because that is what `singlePayload` posts, the edit form because that is what
 * the row arrives with — and the card needs a name and a number. So an id
 * arriving from OUTSIDE (a loaded premises row) is resolved once, here; an
 * account the clerk PICKS arrives whole from the search and is never re-fetched.
 *
 * ⚠ **A FAILED RESOLVE COSTS THE CARD AND NEVER THE VALUE.** The form still
 * holds the id and still posts it, so a courtesy read that cannot reach the
 * server may not quietly un-attach an owner. That is this control's oldest rule
 * and the one thing about it that has not changed: *a picker may never be the
 * reason an address cannot be saved.*
 */
export function OwnerField(props: {
  value: string | null | undefined;
  /** ⚠ **THE WHOLE ACCOUNT RIDES WITH THE ID, AND IT IS NOT REDUNDANT.** A
   *  caller that keeps only an id has to look the NAME up again to render it,
   *  which is what made the add wizard load every owner in the tenant just to
   *  print one — and, before that, print the id itself (B14 rule 31). The
   *  control has the account in its hand at the moment of choosing. The id
   *  stays first so the edit form, which only posts, reads naturally. */
  onChange: (accountId: string | null, account: OwnerAccount | null) => void;
  /** @deprecated CR-130-BRC07 — there is no owner list. Accepted and ignored so
   *  a caller left mid-migration does not go red on an unrelated line. */
  owners?: PremisesOwnerRow[];
  t: Translator;
  client?: ApiClient;
  /** `true` on the EDIT form, which says what clearing does; the create form
   *  draws no help under this row (`CR-089-p008` vs `CR-089-p036`). */
  editing?: boolean;
  /** An account the caller has already resolved, so no fetch is needed at all. */
  account?: OwnerAccount | null;
}) {
  const chosenId = props.value === OWNER_NONE ? null : (props.value ?? null);
  const [resolved, setResolved] = useState<OwnerAccount | null>(props.account ?? null);

  useEffect(() => {
    if (props.account !== undefined && props.account !== null) {
      setResolved(props.account);
      return;
    }
    if (chosenId === null) {
      setResolved(null);
      return;
    }
    let cancelled = false;
    void getAccountDetail(chosenId, props.client)
      .then((account) => {
        if (cancelled) return;
        setResolved({
          id: account.id,
          account_no: account.account_no,
          name: account.name,
          owns_count: null,
        });
      })
      .catch(() => {
        // See the header: the card is a courtesy and the VALUE is the record.
        // Losing the read must not look like the clerk un-picking the owner, so
        // a minimal card is drawn from what the form already knows.
        if (!cancelled) {
          setResolved({ id: chosenId, account_no: null, name: null, owns_count: null });
        }
      });
    return () => {
      cancelled = true;
    };
    // `resolved` is deliberately NOT a dependency: including it re-runs this
    // effect with the value it just set and fetches for ever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chosenId, props.account, props.client]);

  return (
    <MasterAccountSearch
      id="owner_master_account"
      value={chosenId === null ? null : resolved}
      onChange={(account) => {
        setResolved(account);
        props.onChange(account === null ? null : account.id, account);
      }}
      t={props.t}
      client={props.client}
      placeholderKey={
        props.editing === true
          ? "metering.premises.owner.searchClear"
          : "metering.premises.owner.searchLater"
      }
      // ⚠ **ONE SENTENCE, AND ONLY ON THE FORM THAT DRAWS ONE.** B14 rule 32
      // gives a screen a description budget of one sentence per section, and the
      // blueprint draws this helper under the EDIT form's card and none on the
      // create form.
      helpKey={props.editing === true ? "metering.premises.owner.clearingPutsOnList" : undefined}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-130-BRC07 §9 part three — 12-governance/change-requests/
//         CR-130-BRC07-percent-basis-unit-scope-and-the-owners-master-account.md
// generated: 2026-08-27 by the CR-039 wave C tasks 12-14 lane
// amended:   2026-09-22 by the CR-130-BRC07 lane C2 — the control searches
//            MASTER ACCOUNTS rather than owner records (PO ruling of that date),
//            and its label is the one surviving word, `Owner`.
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// exceptions:
//   E3 this file declares no class of its own and renders the shared control, so
//      B14 rule 21 is satisfied without a Route B ledger line.
//   E3 CLOSED 2026-09-22 — the previous exception read *"the control does NOT
//      create a party. See the header: creating one means choosing a category,
//      and BR-MET-151 puts that on the matching surface."* There is no party to
//      create: a premises names an ACCOUNT, and the account door is the one that
//      opens one. `OQ-500` — whether the typed owner becomes the default payer —
//      is no longer this control's question either, because there is no typed
//      owner; what `owner_manager` is FOR is now said on its own label.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
