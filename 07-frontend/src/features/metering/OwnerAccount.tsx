// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-650 (critical) — *"Owner is free text on the premise record, not
//          an account. That limits where a shortfall can be sent."*
// Defect:  DEF-MET-6155 — and the account this block showed came from an OWNER
//          RECORD, so it showed **Needs an owner** on every property whose owner
//          nobody had imported, and the `Find` beneath it searched that same
//          empty table. Measured in a browser 2026-09-22: `Find an owner` + `AC`
//          issued `GET /premises-owners?q=AC` and returned nothing, on a tenant
//          holding master account `AC-2026-00051`.
// Ruling:  PO 2026-08-27, verbatim: *"so premises owner is master accountin
//          system. you ahve to showall details form account - Bascially Premises
//          -> owner = Master account - it can be existing master account also"*
//          — UNCHANGED, and finally true of the chain the screen walks.
//          PO 2026-09-22, verbatim: *"why you are point is at owner id - why not
//          directly at master accoutn Id - it will solev the problem … owner IDs
//          are not required hence no screens or fucntionality for it"*.
// Rules:   BR-MET-400 (the owner IS the master account) · BR-MET-401 (the check
//          at premises creation) · B14 rule 43 (a piece of UI is a COMPONENT —
//          the account search is `MasterAccountSearch`, not a copy) · B14 rule
//          31 (the ACCOUNT NUMBER is the visible value; the id is in the href) ·
//          B14 rule 21 (this file is listed in `src/styles/route-b-migrated.txt`,
//          so its utilities compile)
// Screens: PRM-02 premises detail — the property's own Owner fact row
// ───────────────────────────────────────────────────────
// ONE BLOCK AND THE CONTROL THAT REPAIRS IT: the block shows *"here is that
// account"* and `Find` answers *"there isn't one — attach it"*. They are one
// file because they are two halves of one sentence.
//
// ⚠ **THIS FILE USED TO HOLD FOUR MORE CONTROLS AND THE RULING RETIRED THEM,
// NOT A CLEAN-UP.** `useOwnerNameCheck` and `OwnerNameCheck` resolved a typed
// free-text name against OWNER RECORDS and offered to pick one; `OwnerAccountLink`
// attached an account to an owner RECORD; `OwnerOwnsLine` counted an owner
// record's properties. **No screen may create, pick or search an owner record**
// (PO 2026-09-22), so all four went. Their behaviour is not lost: the account
// search they surrounded is `MasterAccountSearch`, which three screens now share.
//
// ⚠ **`OQ-790` IS NOT AN OPEN QUESTION AND THIS HEADER SAID IT WAS FOR NEARLY A
// MONTH.** It read *"Question: OQ-790 — when the owner's account comes into
// existence, and of which kind. NOT answered here"*. **It has read CLOSED since
// 2026-08-27** — option (c), MASTER IMMEDIATELY — and `CR-056` says the same
// independently. That is `DEF-WRK-4030`'s shape in a docstring rather than in a
// register row: the status moved and the prose that a reader actually reads did
// not. Corrected, and quoted rather than deleted (hard-won law 1).
import { useState } from "react";
import { useParams } from "react-router-dom";

import { Button } from "@/components/Button";
import { formatMoney, isAmountAbsent } from "@/components/MoneyCell";
import type { ApiClient } from "@/api/client";
import { updatePremises } from "@/api/endpoints";
import {
  MasterAccountSearch,
  OwnerAccountNumber,
} from "@/features/metering/MasterAccountSearch";
import type { OwnerAccount } from "@/features/metering/premisesOwnerContract";
import { ownerAccountPayload } from "@/features/metering/premisesOwnerContract";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/**
 * **PO 2026-08-27, verbatim: *"you ahve to showall details form account"*.**
 *
 * Every figure here is the ACCOUNT's own, served at the moment of asking.
 * Nothing is copied onto the premises row, so there is no second writable copy
 * to drift — which is the complaint `OQ-501` files against the free-text owner
 * name carrying the same fact twice.
 *
 * ⛔ **CR-130-BRC07 — IT READS THE PREMISES' OWN MASTER ACCOUNT NOW, NOT AN
 * OWNER RECORD'S.** PO 2026-09-22: *"why you are point is at owner id - why not
 * directly at master accoutn Id … owner IDs are not required hence no screens
 * or fucntionality for it"*. The chain `premises → owner record → account` had
 * a middle link nothing in the product could create, so this block rendered
 * **Needs an owner** on every property whose owner had never been imported —
 * and the `Find` beneath it searched that same empty table.
 *
 * ⚠ **`balance` IS NULLABLE AND THE NULL HAS A REASON (DEF-127/DEF-176).** A
 * screen that renders `0.00` for *"the books could not be asked"* prints
 * something indistinguishable from a settled account. `isAmountAbsent` is the
 * one predicate that asks *did a figure arrive?* — never `=== null`, which is a
 * different question and once took a whole route down.
 *
 * ⚠ **`Kind` IS GONE FROM THE FACT LIST AND THE RULING IS WHY.** It rendered
 * `account.kind` on every row, and under `OQ-790` option (c) — MASTER
 * IMMEDIATELY — plus `CR-056`'s *every address gets its owner a Master Account*,
 * that word is now `master` on every account this block can ever show. A fact
 * row whose value cannot vary is furniture, and B14 rule 32 gives a screen a
 * description budget. Removed, not hidden.
 */
export function OwnerAccountBlock(props: {
  /** The account this PREMISES names, resolved through
   *  `premisesOwnerContract.premisesOwnerAccount`. `null` is *nobody named*. */
  account: OwnerAccount | null;
  /** `false` only where the server said it did not expand the account — the
   *  LIST. A read-only context that never asked must not draw *Needs an owner*. */
  asked?: boolean;
  ownerManager: string | null;
  t: Translator;
  /** Present on PRM-02, absent in a read-only context. When it is present the
   *  clerk can make the link the ruling asks for; when it is absent the block
   *  states the absence and offers nothing, which is the honest read-only shape
   *  rather than a dead button. */
  onLinked?: () => void;
  client?: ApiClient;
}) {
  const { account, t } = props;
  if (props.asked === false) {
    // NOT ASKED is not NO ACCOUNT (`DEF-324`'s measured N+1 is why the list does
    // not expand). Drawing the absent state here would state something the
    // server never said.
    return null;
  }
  if (account === null) {
    // ── **Needs an owner**, and a way to fix it here ──────────────────────
    //
    // ⚠ **THE HEADLINE IS THE SAME PHRASE AS THE LIST CHIP THAT FOUND IT**,
    // deliberately: one phrase for one condition, so the filter and the page
    // cannot describe it differently. It survives the vocabulary sweep because
    // it is the SURVIVING noun plus an absence — *Owner* / *Needs an owner* —
    // rather than a fifth name for the same fact, and because the blueprint
    // names that list twice (`CR-089-p036`, *"Clearing it is allowed and puts
    // the property on the Needs an owner list"*).
    return (
      <div className="text-sm" data-tracks="owner-untyped">
        <p className="font-bold" data-tracks="owner-needs">
          {t("metering.premises.owner.needs_owner")}
        </p>
        {props.ownerManager === null || props.ownerManager === "" ? null : (
          // The string somebody typed is a real fact and is NOT dropped: it is
          // what `BR-MET-151` matches on, and losing it here would discard the
          // only clue to who this is.
          <p data-tracks="owner-freetext">{props.ownerManager}</p>
        )}
        <p className={MUTED}>{t("metering.premises.owner.needsOwnerWhy")}</p>
        <PremisesOwnerFind t={t} client={props.client} onAttached={props.onLinked} />
      </div>
    );
  }
  return (
    <div className="text-sm" data-tracks="owner-typed">
      <p className="font-bold">{account.name ?? t("metering.premises.owner.unnamed")}</p>
      <dl className="mt-1 flex flex-col gap-1">
        {/* ── THE ACCOUNT IS A LINK ──────────────────────────────────────
            *"the header shows … master account A-10442 **as a link**"*. It was
            a `<span>` until `CR-089` wave B: the number was right there, a clerk
            read it, and then had to go to Accounts and search for the thing they
            were already looking at — hard-won law 2's mirror, a live destination
            behind a control that is not one.
            ⚠ B14 rule 31: the visible value is the ACCOUNT NUMBER and never the
            row id; the id travels in the href only. */}
        <OwnerAccountFact
          label={t("metering.premises.owner.fact.accountNo", { defaultValue: "Account" })}
        >
          <OwnerAccountNumber id={account.id} accountNo={account.account_no} t={t} />
        </OwnerAccountFact>
        <OwnerAccountFact
          label={t("metering.premises.owner.fact.name", { defaultValue: "Billed to" })}
        >
          {account.name ?? "—"}
        </OwnerAccountFact>
        {/* ── HOW MANY OTHER PROPERTIES THIS ACCOUNT OWNS ─────────────────
            ⚠ **C1 SERVES `owns_premises_count` FOR THIS ROW AND NOTHING WAS
            READING IT — hard-won law 2, caught in a browser rather than by a
            gate.** This lane's contract adapter named the gap (*"the blueprint
            draws this line and the server does not serve it yet"*), C1 served
            it inside `master_account` on the premises row, and the block went
            on rendering three facts. A field nothing renders is a field that
            does not exist.
            ⚠ **IT REPLACES A COUNT THAT NOW MEANS SOMETHING ELSE.** The screens
            used to read `owner.premises_count` — how many addresses point at the
            OWNER RECORD — and under the ruling the owner is the ACCOUNT, so that
            number answers a question nobody is asking any more.
            ⚠ **`null` IS *NOT ASKED* AND DRAWS NO ROW AT ALL**, and zero is its
            own sentence, because *"already owns 0"* says the opposite of what it
            means. */}
        {account.owns_count === null || account.owns_count === undefined ? null : (
          <OwnerAccountFact
            label={t("metering.premises.owner.fact.alsoOwns", { defaultValue: "Also owns" })}
          >
            <span data-tracks="owner-account-owns">
              {account.owns_count <= 0
                ? t("metering.premises.owner.ownsNothingElse")
                : account.owns_count === 1
                  ? t("metering.premises.owner.alreadyOwnsOne")
                  : t("metering.premises.owner.alreadyOwns", { count: account.owns_count })}
            </span>
          </OwnerAccountFact>
        )}
        <OwnerAccountFact
          label={t("metering.premises.owner.fact.balance", { defaultValue: "Outstanding" })}
        >
          {isAmountAbsent(account.balance ?? null) ? (
            <span className={MUTED}>
              {t("metering.premises.owner.balanceUnavailable", { defaultValue: "not available" })}
            </span>
          ) : (
            formatMoney(account.balance ?? "", account.currency ?? "USD")
          )}
        </OwnerAccountFact>
      </dl>
      {/* ⚠ **WHICH DECLARATION THIS CAME FROM IS NOT DRAWN, AND THAT IS TWO
          RULES AGREEING.** C1 serves `master_account_source` and the contract
          module carries it, because code and tests need it — but putting it on
          screen would break both halves of B14 rule 33: *why the product works
          this way* is RATIONALE and is **zero words on screen**, and the only
          honest way to say it uses the phrase *owner record*, which the PO's
          *"one volcabory"* ruling makes an internal word a clerk never reads.
          A supervisor who needs to know reads the audit log. */}
    </div>
  );
}

/**
 * ***Needs an owner* offers **Find**, and Find searches ACCOUNTS.**
 *
 * ⛔ **THIS IS THE CONTROL THE PO PRESSED, AND IT SEARCHED THE WRONG TABLE.**
 * Their report, verbatim: *"we are unabel to find and map master account to
 * premises later"*. It called `listPremisesOwners({ q })` — owner records, never
 * accounts — so *"an existing master account could never appear, however it is
 * spelled"* (`CR-130-BRC07` §9.2). Measured in a browser on 2026-09-22: pressing
 * `Find an owner` and typing `AC` issued
 * `GET /premises-owners?q=AC&active=true&per=10` and returned nothing, on a
 * tenant holding a master account whose number begins `AC-`.
 *
 * It now searches accounts, through the shared control, and PATCHes
 * `master_account_id` — C1's door, which refuses anything that is not an
 * existing `kind='master'` account in this tenant BY NAME rather than ignoring
 * it. PO 2026-09-08's *"Owner = search ( it should be optional)"* is unchanged;
 * what changed is what it searches.
 *
 * ⚠ **IT TAKES ITS PREMISES FROM THE ROUTE AND NOT FROM A PROP, AND THAT IS
 * DELIBERATE (hard-won law 2).** The alternative was an optional `premisesId`
 * prop that `PremisesDetailPage` — another wave's file — would have to start
 * passing. An optional prop nothing passes is dead UI: it renders, every test
 * goes green, and the feature does not exist. Reading `:premisesId` off the
 * route means this control is live the moment it is drawn on the page that has
 * one, and draws NOTHING anywhere else — the honest behaviour for a block that
 * is also rendered in read-only contexts.
 *
 * ⚠ **AND IT MUST NOT BECOME A SECOND PLACE THAT REQUIRES AN OWNER.** It
 * attaches one when a clerk asks; it never refuses, never blocks a save, and
 * nothing on this page depends on it having been used.
 */
function PremisesOwnerFind(props: {
  t: Translator;
  client?: ApiClient;
  onAttached?: () => void;
}) {
  const { t } = props;
  const params = useParams();
  const premisesId = params.premisesId;
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  // No premises in the URL means this block is not on a property's own page —
  // the move-out summary and the read-only contexts both render it. A Find
  // button there would post to nothing.
  if (premisesId === undefined) {
    return null;
  }

  async function attach(account: OwnerAccount | null) {
    if (account === null) return;
    setBusy(true);
    setFailed(null);
    try {
      // ⚠ **THE PAYLOAD IS BUILT BY THE CONTRACT MODULE, NOT SPELLED HERE.**
      // `master_account_id` is named in exactly one place in this lane, so C1
      // spelling it differently is one edit rather than a hunt.
      await updatePremises(premisesId as string, ownerAccountPayload(account.id), props.client);
      props.onAttached?.();
      setOpen(false);
    } catch (error) {
      setFailed(apiErrorText(error, t));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <p className="mt-2">
        <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(true)}>
          {t("metering.premises.owner.findParty")}
        </Button>
      </p>
    );
  }
  return (
    <div className="mt-2" data-tracks="owner-find" aria-busy={busy}>
      {/* ⚠ **THE SAME CONTROL THE TWO FORMS RENDER — B14 rule 43.** The account
          search already existed one branch down this very file, inside
          `OwnerAccountLink`, reachable only after an owner record had been
          attached. Writing a second one here is what rule 43 was ratified
          against; this is that one, lifted. */}
      <MasterAccountSearch
        id="owner_find_account"
        value={null}
        onChange={(account) => void attach(account)}
        t={t}
        client={props.client}
      />
      {failed === null ? null : (
        <p className="mt-1 text-danger-700" data-tracks="owner-find-failed">
          {failed}
        </p>
      )}
    </div>
  );
}

function OwnerAccountFact(props: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className={MUTED}>{props.label}</dt>
      <dd>{props.children}</dd>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-650 + DEF-1088 — 12-governance/10-defect-log.csv
// generated: 2026-08-27 by the premises-owner lane
// amended:   2026-09-22 by the CR-130-BRC07 lane C2 — the block reads the
//            PREMISES' own master account and `Find` searches ACCOUNTS
//            (DEF-MET-6155, PO ruling of that date).
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// exceptions:
//   E3 the blueprint draws this row (`CR-089-p019` row 11) as two lines —
//      `Creekside Holdings LP · Landlord` and `Master account A-10442 · Open it
//      →`. This block keeps the FACT GRID it has rendered since DEF-650, which
//      is PO 2026-08-27's *"you ahve to showall details form account"* and is a
//      later ruling than the drawing on that point. Re-cutting it to the drawn
//      two lines is `CR-089-p019`'s own conformance work and is NOT done here:
//      this lane changed WHAT the block reads and WHAT `Find` searches, and
//      re-laying it out in the same commit would bury that in a diff nobody
//      could review. Reported, not absorbed.
//   E3 `· Landlord` on the drawn line 1 is the OWNER RECORD's category. There is
//      no owner record under the 2026-09-22 ruling and so no category; line 1 is
//      the account's name alone.
//   E3 CLOSED 2026-09-22 — *"the `near` list has no default selection and no
//      auto-apply"* described `OwnerNameCheck`, which this lane retired: it
//      resolved a typed name against owner records, and no screen may search
//      those. The posture it protected — SEARCH AND NEVER GUESS, no
//      auto-selection however unambiguous a single result looks — is carried
//      into `MasterAccountSearch` and stated there.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
