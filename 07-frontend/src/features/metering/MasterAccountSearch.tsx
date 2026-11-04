// ── Trace ──────────────────────────────────────────────
// Change:  CR-130-BRC07 part three, lane C2.
// Defect:  DEF-MET-6155 — all three owner surfaces searched `premises_owners`,
//          a table no screen in the product can write to. Measured in a browser
//          on 2026-09-22: the Add wizard's picker offered **0 options**, the
//          Edit modal's offered **0**, and `Find an owner` queried
//          `/premises-owners?q=AC` and found nothing.
// Ruling:  PO 2026-09-22 — a premises names its MASTER ACCOUNT directly;
//          *"owner IDs are not required hence no screens or fucntionality for
//          it"*. Decision log of that date.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT — standalone code inside a
//          page is not reuse) · B14 rule 31 (no database id is a visible value;
//          the ACCOUNT NUMBER is what a clerk reads) · B14 rule 33 (a label ≤ 3
//          words, a fact ≤ 6, RATIONALE is zero words on screen) · B14 rule 21
//          (Tailwind utilities, no new stylesheet class — this file is on
//          `src/styles/route-b-migrated.txt`) · BR-SHL-033 (a searchable
//          control past the long-list threshold) · IS-3 (search debounced
//          300 ms, minimum 2 characters)
// Drawing: *Premises & Units Blueprint 2* — `WHO LOOKS AFTER IT?` on the add
//          form (p009-p011) and the edit form (p036-p041), and the property
//          page's `Owner` fact row (p019). All three draw ONE control: a search
//          box, and beneath it a confirmation card with a `Change` control.
//          Conformance: CR-089-p008 / p036 / p019.
// Screens: S16 the guided add · PRM-01 the edit modal · PRM-02 the property page
// ───────────────────────────────────────────────────────
// ONE CONTROL, THREE SCREENS — and it is a component for the reason B14 rule 43
// was ratified: *"use it"* once meant 120 lines inline in a page, importable by
// nothing.
//
// ⚠ **THE SEARCH HALF IS NOT NEW AND WAS NOT REWRITTEN.** `OwnerAccount.tsx`'s
// `OwnerAccountLink` has called `getAccounts({ q })` since `DEF-650`, correctly,
// and it was reachable only AFTER an owner record had been attached — which is
// the cupboard nobody could fill. So the account search a clerk needed already
// existed, one branch down a road they could not walk. This is that control,
// lifted to where the ruling puts it, rather than a second one written beside it.
//
// ⚠ **IT SEARCHES AND IT NEVER GUESSES.** No single result is auto-picked,
// however unambiguous it looks — the same posture the near-match offer takes one
// file over, and for the same reason: two landlords with similar names are two
// parties, and picking the wrong one bills the wrong one.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/Button";
import { createSearchDebouncer } from "@/components/searchDebounce";
import type { ApiClient } from "@/api/client";
import { getAccounts } from "@/api/endpoints";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import type { OwnerAccount } from "@/features/metering/premisesOwnerContract";
import { ownerAccountFromRow } from "@/features/metering/premisesOwnerContract";
import { useTenantPath } from "@/routing/tenantPath";

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/**
 * ⚠ **THE SERVER CLAMPS `per` UP, NOT DOWN, AND THAT IS WHY THIS EXISTS.**
 * `core/pagination.clamp_page_size` returns the smallest allowed page — **50** —
 * for anything below it, so `per: 10` is `per: 50` on the wire. Verified live
 * on 2026-09-22: `GET /accounts?per=3` returned 50 rows. A control that asked
 * for ten and rendered whatever came back would therefore drop a 50-row list
 * under a form field. The REQUEST is honest about the page it gets; the RENDER
 * is capped here, and the cap says so on screen when it bites rather than
 * silently hiding rows.
 */
const SHOWN = 8;

type SearchState =
  | { kind: "idle" }
  | { kind: "searching" }
  | { kind: "results"; rows: OwnerAccount[]; total: number }
  | { kind: "failed"; reason: string };

/**
 * **THE OWNER CONTROL — a search over MASTER ACCOUNTS, and its confirmation card.**
 *
 * `value` is the account this property names, or `null`. `onChange` hands back
 * the whole account rather than an id, so a caller can draw the card without a
 * second fetch — which is what the old picker needed (`getPremisesOwner` on
 * every change) and what made a chosen row flicker.
 *
 * ⚠ **IT WRITES NOTHING. `BR-MET-112`: nothing is written until the last
 * button.** Picking here changes the FORM's value; the one press that follows
 * is what reaches the server. That is also why this control is identical on the
 * create form and the edit form — the drawing says *"Two screens that ask for
 * the same things should look the same, or a clerk relearns the form every time
 * they correct one."*
 */
export function MasterAccountSearch(props: {
  value: OwnerAccount | null;
  onChange: (account: OwnerAccount | null) => void;
  t: Translator;
  client?: ApiClient;
  /** `leaveForLater` on the create form, `clear` on the edit form — the two
   *  placeholders the blueprint draws, which differ because the acts differ. */
  placeholderKey?: string;
  /** One sentence, B14 rule 32. The edit form draws one; the create form does not. */
  helpKey?: string;
  /** The input's `id`, so a `<label>` can bind to it and a test can find it. */
  id?: string;
}) {
  const { t } = props;
  const id = props.id ?? "owner_master_account";
  const [term, setTerm] = useState("");
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  // ⚠ The latest request wins. Without this a slow first query can land AFTER a
  // fast second one and repaint the list with the previous term's rows — a
  // control that looks like it ignored what you typed.
  const seq = useRef(0);

  const search = useMemo(
    () =>
      createSearchDebouncer((q: string) => {
        if (q === "") {
          setState({ kind: "idle" });
          return;
        }
        const mine = ++seq.current;
        setState({ kind: "searching" });
        void getAccounts({ q, filters: { kind: "master" }, per: SHOWN }, props.client)
          .then((page) => {
            if (mine !== seq.current) return;
            const rows = (page.results ?? []).map(ownerAccountFromRow);
            setState({ kind: "results", rows, total: page.count ?? rows.length });
          })
          .catch((error) => {
            if (mine !== seq.current) return;
            // A search that cannot reach the server costs the CONVENIENCE and
            // never the address: the form still saves, exactly as the picker
            // this replaces was careful to (hard-won law 3, the other way
            // round). The reason is said out loud rather than rendered as an
            // empty list, which is indistinguishable from *no matches*.
            setState({ kind: "failed", reason: apiErrorText(error, t) });
          });
      }),
    // `props.client` and `t` are captured once on purpose: a debouncer rebuilt
    // on every render never fires, because each keystroke gets a fresh timer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  useEffect(() => () => search.clear(), [search]);

  // ── THE CONFIRMATION CARD ────────────────────────────────────────────────
  // Drawn beneath the box on both forms: the name, the account number, and a
  // `Change` control on the right.
  if (props.value !== null) {
    return (
      <div data-tracks="owner-account-field">
        <OwnerFieldLabel id={id} t={t} />
        <OwnerAccountCard
          account={props.value}
          t={t}
          onChange={() => {
            props.onChange(null);
            setTerm("");
            setState({ kind: "idle" });
          }}
        />
        {props.helpKey === undefined ? null : (
          <p className={`mt-1 text-sm ${MUTED}`}>{t(props.helpKey)}</p>
        )}
      </div>
    );
  }

  return (
    <div data-tracks="owner-account-field">
      <OwnerFieldLabel id={id} t={t} />
      <input
        id={id}
        type="search"
        className="input"
        autoComplete="off"
        value={term}
        placeholder={t(props.placeholderKey ?? "metering.premises.owner.searchLater")}
        onChange={(event) => {
          setTerm(event.target.value);
          search.type(event.target.value.trim());
        }}
      />
      {props.helpKey === undefined ? null : (
        <p className={`mt-1 text-sm ${MUTED}`}>{t(props.helpKey)}</p>
      )}
      <MasterAccountResults state={state} t={t} onPick={props.onChange} />
    </div>
  );
}

/**
 * The ONE word, and it is the deliverable.
 *
 * ⚠ **FIVE WORDINGS FOR ONE FACT WERE LIVE ON SCREEN AND THE PO COUNTED THEM**
 * — *Owner*, *Owner (record)*, *Owner / manager*, *master account {{n}}*,
 * *Needs an owner*. Verbatim: *"owner and master account is confusing we ahve
 * to use one volcabory"*. The survivor is **Owner**, which is also what the
 * blueprint labels this row on all three screens; *owner record* and *master
 * account* become internal words a clerk never reads.
 */
function OwnerFieldLabel(props: { id: string; t: Translator }) {
  return (
    <label htmlFor={props.id} id={`${props.id}-label`} className="block font-bold">
      {props.t("metering.premises.col.owner")}
    </label>
  );
}

/** Idle · searching · results · nothing · failed. All five, because a control
 *  with only its happy state is a third of a control. */
function MasterAccountResults(props: {
  state: SearchState;
  t: Translator;
  onPick: (account: OwnerAccount) => void;
}) {
  const { state, t } = props;
  if (state.kind === "idle") return null;
  if (state.kind === "searching") {
    return (
      <p className={`mt-1 text-sm ${MUTED}`} data-tracks="owner-account-searching">
        {t("metering.premises.owner.searching")}
      </p>
    );
  }
  if (state.kind === "failed") {
    return (
      <p className="mt-1 text-sm text-danger-700" data-tracks="owner-account-failed">
        {state.reason}
      </p>
    );
  }
  if (state.rows.length === 0) {
    return (
      <p className={`mt-1 text-sm ${MUTED}`} data-tracks="owner-account-empty">
        {t("metering.premises.owner.noMatch")}
      </p>
    );
  }
  const shown = state.rows.slice(0, SHOWN);
  return (
    <>
      <ul className="mt-1 flex flex-col gap-1" data-tracks="owner-account-results">
        {shown.map((row) => (
          <li key={row.id} className="flex items-center justify-between gap-2 text-sm">
            <span>
              {row.name ?? t("metering.premises.owner.unnamed")}
              {row.account_no === null ? "" : ` · ${row.account_no}`}
            </span>
            <Button type="button" variant="secondary" size="sm" onClick={() => props.onPick(row)}>
              {t("metering.premises.owner.choose")}
            </Button>
          </li>
        ))}
      </ul>
      {/* A cap that hides rows silently is a list that lies about its size. */}
      {state.total > shown.length ? (
        <p className={`mt-1 text-sm ${MUTED}`} data-tracks="owner-account-more">
          {t("metering.premises.owner.keepTyping")}
        </p>
      ) : null}
    </>
  );
}

/**
 * **THE CONFIRMATION CARD, as the blueprint draws it.**
 *
 * Line 1 the name · line 2 the account number · a `Change` control on the right.
 *
 * ⚠ **THE DRAWING'S SECOND LINE READS `Owns 3 properties · master account
 * A-10442` AND TWO OF THOSE WORDS ARE RETIRED BY A LATER RULING.** The
 * blueprint owns layout, copy and detail for this module (B14 rule 36/41), and
 * the PO's ruling of 2026-09-22 is later than the drawing and reverses exactly
 * two words in it: *"we ahve to use one volcabory"*, and the decision log's
 * *"One word reaches a clerk — **Owner** — with the account number beside it;
 * owner record and master account become internal words nobody reads."* So the
 * SHAPE is the drawing's and the WORDS are the ruling's, and the divergence is
 * stated here rather than absorbed.
 *
 * ⚠ **`Owns N properties` IS DRAWN AND IS NOT YET SERVED, SO IT IS NOT DRAWN
 * HERE EITHER.** B14 rule 37 — a figure in a wireframe is an ILLUSTRATION — so
 * the PRESENCE of the line is specification and the number is not; but a count
 * nobody sends cannot be rendered, and rendering zero would say the opposite of
 * what it means. `owns_count === null` is NOT ASKED and draws nothing. The day
 * C1's `premises_ids_owned_by_account` reaches the wire the line appears with no
 * further change, and `MasterAccountSearch.dom.test.tsx` asserts that branch so
 * it is a live path rather than a hopeful one.
 */
export function OwnerAccountCard(props: {
  account: OwnerAccount;
  t: Translator;
  /** Absent in a read-only context, and then no control is drawn at all —
   *  the honest read-only shape rather than a button that refuses. */
  onChange?: () => void;
}) {
  const { account, t } = props;
  return (
    <div
      className="mt-1 flex items-start justify-between gap-4 rounded-md border border-divider p-3"
      data-tracks="owner-account-card"
    >
      <div className="text-sm">
        <p className="font-bold" data-tracks="owner-account-name">
          {account.name ?? t("metering.premises.owner.unnamed")}
        </p>
        <p className={MUTED}>
          {account.owns_count === null || account.owns_count <= 0 ? null : (
            <span data-tracks="owner-account-owns">
              {account.owns_count === 1
                ? t("metering.premises.owner.alreadyOwnsOne")
                : t("metering.premises.owner.alreadyOwns", { count: account.owns_count })}{" "}
              ·{" "}
            </span>
          )}
          {/* B14 rule 31: the ACCOUNT NUMBER is the visible value. The row id
              travels in the href and nowhere else. */}
          <OwnerAccountNumber id={account.id} accountNo={account.account_no} t={t} />
        </p>
      </div>
      {props.onChange === undefined ? null : (
        <Button type="button" variant="secondary" size="sm" onClick={props.onChange}>
          {t("metering.premises.owner.change")}
        </Button>
      )}
    </div>
  );
}

/**
 * The account number, as a way to get to the account.
 *
 * ⚠ **IT DEGRADES TO THE PLAIN NUMBER RATHER THAN TO A DEAD LINK**, and to a
 * named absence rather than to a dash with an id behind it — the two failures
 * `OwnerAccount.tsx` already recorded, kept here because this control replaced
 * the one that learned them.
 */
export function OwnerAccountNumber(props: {
  id?: string | null;
  accountNo: string | null;
  t: Translator;
}) {
  const tenantPath = useTenantPath();
  if (props.accountNo === null || props.accountNo === "") {
    return (
      <span data-tracks="owner-account-unnumbered">
        {props.t("metering.premises.owner.unnumbered")}
      </span>
    );
  }
  if (!props.id) {
    // ⚠ **THE LIST GETS A NUMBER AND NO ID, ON PURPOSE.** C1's batched seam
    // serves `master_account_no` flat on every row and leaves the expansion
    // off, so there is nothing to link TO and the honest control is not a link
    // — the same refusal `OwnerAccount.tsx` learned when a summary shape would
    // otherwise have rendered `<Link to="/accounts/undefined">`.
    return <span data-tracks="owner-account-no">{props.accountNo}</span>;
  }
  return (
    <Link to={tenantPath(`/accounts/${props.id}`)} data-tracks="owner-account-link">
      {props.accountNo}
    </Link>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-130-BRC07 §9 part three — 12-governance/change-requests/
//         CR-130-BRC07-percent-basis-unit-scope-and-the-owners-master-account.md
// generated: 2026-09-22 by the CR-130-BRC07 lane C2
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// exceptions:
//   E3 the blueprint's confirmation card draws `Creekside Holdings LP · Landlord`
//      on line 1 — a name and the OWNER RECORD's category. There is no owner
//      record under the 2026-09-22 ruling and therefore no category, so line 1
//      is the account's name alone. The drawing could not anticipate the ruling;
//      the divergence is stated, not absorbed.
//   E3 the drawn words `master account` on line 2 are retired by that same
//      ruling. The account NUMBER stays, which is what the ruling asks for.
//   E3 `Owns N properties` is drawn and is not served by the wire yet. It is
//      rendered from `owns_count` when a count arrives and draws nothing when it
//      does not; zero is never rendered as a count.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
