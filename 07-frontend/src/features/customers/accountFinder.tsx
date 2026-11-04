// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-732 — *"the transfer wizard asks a clerk to type a UUID"*. The
//           PO typed `AC-2026-00025` into `TRF-02.1` and was told **"That
//           account could not be read"**. Nothing was broken at any line:
//           `GET /accounts/{id}` correctly failed to find a uuid that was never
//           a uuid, and the field's own help text admitted what it wanted.
// Screens:  S89 `TRF-02.1` (transfer) · `DSC-02.1` (disconnect)
// Rules:    BR-CUS-053 (ONE box finds an account by account #, customer #,
//           customer name, service address or meter #) · IS-3 (the search is
//           SERVER-side and `q` under two characters is not sent) ·
//           BR-SHL-011 (a list URL never 4xx's over its params) ·
//           B14 rule 21 (Tailwind utilities; this file adds no stylesheet class)
// ───────────────────────────────────────────────────────
/**
 * THE ACCOUNT FINDER — one box a clerk can actually fill.
 *
 * **The identifier a product asks for must be one the product SHOWS.** Every
 * list, KPI tile and detail header in SMARTBillHub prints the account NUMBER;
 * nothing anywhere prints a uuid. A required field whose only valid value is an
 * internal id is unusable by definition, and both wizards that take an account
 * by hand had exactly that field.
 *
 * ⚠ **NO NEW ENDPOINT, AND THAT IS THE FINDING RATHER THAN A SHORTCUT.** The
 * search the old help text called missing has been published since W2:
 * `GET /accounts?q=` matches account #, customer #, customer name, service
 * address and meter # in ONE tenant-scoped OR-group (`selectors.account_list`,
 * BR-CUS-053), and `PaymentsPage` and the one-time bill page
 * (`features/billing/oneTimeBill`, its account step) already pick an account
 * through it. So this is that same published pair — a search box and the
 * matches it returns — extracted ONCE instead of restated a third time.
 *
 * ⚠ **THE UUID WAS NOT TRADED AWAY.** A value that IS an account id is taken as
 * one and resolved directly, because ids still reach a clerk from a URL, a
 * report or a support thread. One exclusive identifier replaced by another
 * exclusive identifier is the same defect facing the other way.
 *
 * ⚠ **"NOTHING MATCHED" AND "COULD NOT BE READ" ARE DIFFERENT FACTS.** DEF-732
 * is what happens when a product states the second over the first: the clerk
 * reads a system fault, rings support, and never checks their own typing. This
 * component states each one separately, and neither of them fabricates an
 * account (CLAUDE.md hard rule 2).
 *
 * ⚠ **THE SEARCH IS THE SERVER'S — never a client-side filter over a page of
 * rows.** `account_list` runs inside the tenant's RLS scope, so a number that
 * exists in three tenants resolves in exactly one (CLAUDE.md hard rule 1,
 * proved in `06-backend/tests/test_def_732_account_lookup.py`).
 */
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getAccounts } from "@/api/endpoints";
import type { AccountRow } from "@/api/endpoints";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import { Note } from "@/components/TextBits";

import type { Translator } from "./newConnectShared";

/** IS-3, the same minimum every other search in this app uses: an empty box
 *  must not pull the tenant's whole register into a select. */
export const MIN_SEARCH_CHARS = 2;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A term that IS an account id. `GET /accounts/{id}` takes one and the search
 *  cannot find one (`account_no ILIKE '%<uuid>%'` matches nothing), so the two
 *  inputs are told apart HERE rather than by trying both and hoping. */
export function isAccountId(term: string): boolean {
  return UUID.test(term.trim());
}

/**
 * One account, as the picker names it.
 *
 * Both halves are nullable — an account number can be absent, and BR-CUS-054's
 * `customers` entity is unbuilt so `name` is the primary CONTACT's — so the
 * label falls back account # → name → a stated placeholder and NEVER renders
 * empty. An option a clerk can select without knowing whose service they are
 * about to move or cut is the shape of the wrong customer being disconnected.
 * (The same rule as `PaymentsPage.accountPickerLabel` and the one-time bill
 * page's `features/billing/oneTimeBill/AccountStep.accountOption`, which never
 * renders an empty name or number either — it states a placeholder for each;
 * those two live in other families' diffs, so this is the third statement of it
 * and the first SHARED one — folding the two into this is owed and is REPORTED,
 * not taken here. Pointer corrected 2026-09-30, DEF-BIL-8152.)
 */
export function accountFinderLabel(account: AccountRow, t: Translator): string {
  const address = account.unit_label ?? null;
  const head =
    account.account_no !== null && account.name !== null
      ? `${account.account_no} — ${account.name}`
      : (account.account_no ??
        account.name ??
        t("customers.accountFinder.unnamed", { defaultValue: "Account with no number or name" }));
  return address === null ? head : `${head} · ${address}`;
}

/**
 * What the search ANSWERED for the term currently in the box.
 *
 * ⚠ **THE QUERY LIVES IN THE WIZARD AND THE PRESENTATION LIVES HERE, on
 * purpose.** Both wizards render their step-1 component directly in static
 * markup tests that mount no `QueryClientProvider`; a `useQuery` inside the step
 * would throw in every one of them. It is the same split `account` and `failed`
 * already use — the wizard reads, the step draws.
 */
export interface AccountSearchState {
  matches: readonly AccountRow[];
  /** The search RAN for this term (so an empty `matches` means "no such
   *  account", not "not asked yet" — the distinction DEF-732 was filed over). */
  searched: boolean;
  /** The search itself could not be run. A PLATFORM fact, never a term fact. */
  failed: boolean;
}

/** Nothing has been asked. Also what the hook returns below the minimum length,
 *  so "not asked" is ONE value and not three booleans a caller assembles. */
export const ACCOUNT_SEARCH_IDLE: AccountSearchState = {
  matches: [],
  searched: false,
  failed: false,
};

/**
 * The published account search, as a hook (IS-3: server-side, `q` under two
 * characters is not sent — an empty box must not pull the tenant's whole
 * register into a select).
 *
 * A term that IS an id is not searched for at all: `GET /accounts/{id}` takes
 * one and `account_no ILIKE '%<uuid>%'` matches nothing.
 */
export function useAccountSearch(term: string, client: ApiClient): AccountSearchState {
  const trimmed = term.trim();
  const enabled = !isAccountId(trimmed) && trimmed.length >= MIN_SEARCH_CHARS;
  const query = useQuery({
    queryKey: ["account-finder", trimmed],
    queryFn: () => getAccounts({ q: trimmed, per: 50 }, client),
    enabled,
    retry: false,
  });
  if (!enabled) {
    return ACCOUNT_SEARCH_IDLE;
  }
  return {
    matches: query.data?.results ?? [],
    searched: query.isSuccess,
    failed: query.isError,
  };
}

export interface AccountFinderProps {
  /** Field-id prefix, one per screen (`trf`, `dsc`) — G17 forbids two elements
   *  sharing a DOM id, and both wizards can be open in one app. */
  idPrefix: string;
  /** The wizard's own label for the thing it is asking for. */
  label: string;
  /** The hint under the box. Absent, the shared 27-word sentence stands, which
   *  is what five other hosts render today; a host that has been ruled on
   *  passes its own. */
  help?: string;
  /** What the clerk typed. Held by the WIZARD, not by this component: a step's
   *  content unmounts when the clerk walks to step 2, and a search term that
   *  vanished on the way back would look like the wizard forgot the account. */
  term: string;
  onTermChange: (term: string) => void;
  search: AccountSearchState;
  /** The resolved account id — `""` until one is chosen. This is what the
   *  commit posts, and it is only ever a real id. */
  value: string;
  onChange: (accountId: string) => void;
  t: Translator;
  required?: boolean;
}

/**
 * ⊕ **ONE CONTROL, NOT TWO — `DEF-CUS-6475`.** Product Owner, 2026-09-24, on
 * the move-out wizard's step 1: *"Account and matching account  it can be
 * seracable dropdown search it"*.
 *
 * **This is the same fix `DEF-PAY-6319` made for Payments on 2026-09-23 and
 * `DEF-CUS-6382` made for the transfer wizard, arriving at the third and last
 * family that still hand-rolled the pair.** `components/RemoteSearchSelectField`
 * was added to the kit for exactly this and names THIS FILE in its own Impacts
 * header as one of the hand-rolls that belongs there — so the component was
 * waiting, and B14 rule 43's *before building, LOOK for the component* is the
 * whole of the work here. Nothing new is invented and no new sentence is minted.
 *
 * ⚠ **THE EXPORTED NAME AND THE PROPS ARE UNCHANGED, DELIBERATELY** — the same
 * choice `AccountPickerFields` made for the same reason. Three hosts compose
 * this (`moveShared.MoveOutAccountPick`, `disconnect/steps/AccountAndReasonStep`
 * and `JobIntakeWizard`) and **not one of them needed an edit**, so the blast
 * radius of a shared-component change is bounded by construction rather than by
 * a sweep that might miss a caller.
 *
 * ⚠ **THE FIVE STATES STAY FIVE, WHICH IS THE PART A NAIVE DROPDOWN LOSES.**
 * `DEF-3506` was filed because a clerk could not tell them apart, and the 2026-
 * 09-03 repair made them distinguishable by ADDING the second control. The
 * states were what mattered; the second control was only how they were reached.
 * The kit draws all five inside ONE panel, and keeps *the search could not run*
 * (a PLATFORM fact, `BR-SHL-020`, a red `RefusalStrip` with `role="alert"`)
 * apart from *no account matches that* (a fact about the TERM, a `Note`) —
 * which is the pair DEF-732 exists over and the one an ordinary combobox
 * collapses into a single empty list.
 *
 * ⚠ **TYPING CLEARS THE CHOSEN ID, AND THAT IS A MONEY RULE.** The kit fires
 * `onChange("")` on every keystroke, which is what this file's own
 * `handleTerm` did and for the identical reason: a stale id behind a changed
 * box is how a clerk cuts the service they were reading about a moment ago.
 * The pasted-id path below is the deliberate exception and the only one.
 */
export function AccountFinder(props: AccountFinderProps) {
  const term = props.term.trim();
  const pasted = isAccountId(term);
  const idle = !pasted && term.length < MIN_SEARCH_CHARS;
  const matches = props.search.matches;

  /** Typing INVALIDATES the previous choice. Leaving a stale id behind a
   *  changed box is how a clerk cuts the service they were reading about a
   *  moment ago. A pasted id resolves itself, with no second click — which is
   *  why this wraps the kit's own `onChange` rather than passing it straight
   *  through: the kit clears on every keystroke, correctly, and a UUID is the
   *  one term that IS its own answer (DEF-732's second rule). */
  function handleTerm(next: string): void {
    props.onTermChange(next);
    props.onChange(isAccountId(next) ? next.trim() : "");
  }

  /**
   * ⚠ **THE KIT'S CLEAR IS SWALLOWED, AND THIS IS THE SUBTLE PART OF THE WHOLE
   * CONVERSION.** `RemoteSearchSelectField`'s input fires
   * `onTermChange(value)` and then `onChange("")` on every keystroke — the
   * right thing for its own hosts, where the only way to hold a value is to
   * pick an option. Here it runs AFTER `handleTerm`, so the LAST write wins and
   * a pasted uuid was being set and then wiped in the same event.
   *
   * **Measured, not reasoned about:** `accountLookup.dom.test.tsx`'s *"an
   * account id pasted into the box still resolves — the uuid was not traded
   * away"* went RED on both wizards, `GET /accounts/{id}` was never requested,
   * and that is DEF-732's second rule failing — one exclusive identifier traded
   * for another, which is the defect facing the other way.
   *
   * So `handleTerm` owns EVERY value change that comes from typing, and this
   * wrapper lets only a real PICK through. **The money rule is untouched and is
   * still enforced one line up**: typing a non-id clears the chosen account, so
   * a stale id can never sit behind a changed box.
   */
  function handlePick(next: string): void {
    if (next !== "") {
      props.onChange(next);
    }
  }

  /**
   * The matches, as options — plus the CHOSEN account pinned in front of them.
   *
   * ⚠ **WITHOUT THE PIN THE BOX GOES BLANK THE MOMENT A SEARCH MOVES ON.** The
   * kit shows the chosen option's LABEL at rest and falls back to the host's
   * term when the value matches no option (B14 rule 31 — it never prints the
   * id). A chosen account that has dropped out of the current result set would
   * therefore have no label to show, so it is kept addressable here. The same
   * thing `TransferWizard` does, for the same reason.
   */
  const options = matches.map((account) => ({
    value: account.id,
    label: accountFinderLabel(account, props.t),
  }));
  if (props.value !== "" && !options.some((option) => option.value === props.value)) {
    options.unshift({
      value: props.value,
      label: pasted ? term : props.value,
    });
  }

  return (
    <div className="flex flex-col gap-2" data-account-finder="">
      <RemoteSearchSelectField
        /* ⚠ **THE ID IS THE OLD *SELECT*'s, NOT THE OLD TEXT BOX's.**
           `${idPrefix}_account` is what every zod schema, every server field
           refusal and every existing test addresses, because it is the control
           that HOLDS THE VALUE. `${idPrefix}_account_q` was a second id for one
           question and goes with the second control — the same retirement
           `account_query` had in Payments. */
        id={`${props.idPrefix}_account`}
        label={props.label}
        required={props.required}
        term={props.term}
        onTermChange={handleTerm}
        status={{
          idle,
          // Something searchable is typed and no answer has come back yet.
          searching: !idle && !pasted && !props.search.searched && !props.search.failed,
          searched: props.search.searched,
          failed: props.search.failed,
        }}
        options={options}
        value={props.value}
        onChange={handlePick}
        /* ⚠ **THE PLACEHOLDER CARRIES THE INVITATION NOW.** With one control
           there is one label, so the field's NAME is the label and what to type
           is the placeholder — the judgment `DEF-PAY-6319` recorded, applied
           here rather than re-made. Six words, B14 rule 33's cap for an
           instruction; the 27-word help line it replaces is `DEF-CUS-6474`. */
        placeholder={props.t("customers.accountFinder.findHint", {
          defaultValue: "Number, name or address.",
        })}
        /* ⛔ **NO HELP LINE UNLESS THE HOST PASSES ONE.** The default used to be
           27 words quoting `AC-2026-00025` as *"the account number as your
           lists show it"* — and the account series is PER TENANT
           (`AC-{YYYY}-{00000}` is only the seeded default), so on the Product
           Owner's own screen the lists read `A-10650` and the example named a
           format they do not use (`DEF-CUS-6474`). An example that cannot be
           right for every tenant does not belong in shared copy, and the
           placeholder above already says what to type. */
        help={props.help}
        /* The four sentences the kit needs, in all eleven catalogues already —
           the same control as Payments and the transfer wizard, so the same
           words, and NOT ONE CATALOGUE KEY MOVES for this change (B14 rule 35:
           a catalogue is written in its own language, and these already are). */
        words={{
          tooShort: props.t("payments.form.accountTooShort"),
          searching: props.t("payments.form.accountSearching"),
          failed: props.t("payments.form.accountSearchFailed"),
          noMatch: props.t("payments.form.accountNoMatch"),
        }}
      />

      {pasted && (
        // The sixth state, and it is this file's own rather than the kit's: a
        // term that IS an account id is taken as one and never searched for
        // (DEF-732). Six words — a FACT, B14 rule 33.
        <Note data-account-state="id">
          {props.t("customers.accountFinder.pastedId", {
            defaultValue: "Read as an account id.",
          })}
        </Note>
      )}
    </div>
  );
}
