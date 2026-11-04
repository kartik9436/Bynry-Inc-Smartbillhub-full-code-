// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-001 (S14 premises detail — PRM-02's Common areas tab)
//           Screens: S14 · links out to S17/S21 (the master account itself)
// Rules:    BR-MET-101 (a common area IS a unit with a flag; a master account
//           IS an account whose payer is the owner — neither gets a new table.
//           PO 2026-08-21) · BR-CUS-068 (the master account's home:
//           `accounts.kind='master'`, payer = the owner/manager, attached to
//           the common-area units through the SAME linkage every account uses.
//           PO 2026-08-22, closing OQ-314's second half) · BR-CUS-017 (an
//           account belongs to exactly one unit — which is WHY coverage rides
//           service agreements and `unit_id` is only the anchor) ·
//           BR-MET-040 (a unit without a plan blocks activation) ·
//           BR-CUS-022 (the start date is required before anything attaches) ·
//           BR-SHL-020 (the six A18 states, composed) · BR-SHL-020 r2 (the
//           customer sentence comes from the catalogue) · BR-SHL-025 (a
//           forbidden control renders disabled WITH its reason) · BR-SHL-032
//           (a confirm NAMES what it is about to do) · B14 rule 12 (filters
//           are chips) · B14 rule 15 (an ordinary button says a WORD)
// Defects:  DEF-559 (the two BR-CUS-068 refusals carry no `message_key`, so
//           this screen maps the SERVER's own `reason` onto a sentence) ·
//           DEF-560 (which common areas a master COVERS is not served — only
//           the anchor is queryable, so no per-row "billed to" cell is drawn) ·
//           DEF-564 (`.met-row-actions` was deleted on 2026-08-20 and this file
//           still asked for it — a class no stylesheet declares renders as
//           nothing; G31) · DEF-565 (the guard that fires FIRST on the
//           commonest refusal is BR-CUS-017's, not BR-CUS-068's, so the mapping
//           below keys off the MESSAGE and the endpoint, not the rule id)
// Tests:    src/features/metering/PremisesPage.test.tsx (the `P6` cases read
//           the header ROW and the first row's CELLS — a substring search over
//           the render cannot tell a drawn column from one the column chooser
//           merely lists) · src/features/metering/def4742EnglishOnlyKeys.test.ts
// ───────────────────────────────────────────────────────
// PRM-02 · **COMMON AREAS**, and this file is the half OQ-314 called "the
// screen half" until 2026-08-22.
//
// ── WHAT r10 DRAWS AND WHAT THIS SERVES ───────────────────────────────────
// r10's tab is a four-tile KPI row (`MASTER ACCOUNT MA-1408 · COMMON AREAS 2 ·
// JULY COMMON BILL $69.60 · UNALLOCATED USAGE 3.1%`), a two-row table
// (`Hallway & exterior lighting · M-4109 · Small Commercial · $41.20 · Active`
// and the shared irrigation at `$28.40`), a MASTER callout and two buttons.
// Three of those four figures have a source today and one does not:
//
//   · **MASTER ACCOUNT** — real. `GET /accounts?f.kind=master&f.unit_id=` is
//     the SERVER's answer, and the number it shows is the account's own from
//     the BR-TEN-035 tenant series. It is NOT `MA-1408`: r10's prefix is
//     layout/copy, B2 governs data, and minting a second numbering series is a
//     rule nobody signed (decision log 2026-08-22, judgment 4).
//   · **COMMON AREAS** — real, from `is_common_area` (BR-MET-101).
//   · **JULY COMMON BILL $69.60** — NOT drawn. `apps/billing/gather.py` prices
//     `account.unit_id` only, so today a master bill would carry the ANCHOR's
//     services alone; pricing $41.20 + $28.40 onto ONE document is the
//     bill-assembly half the same decision log names as still owed. A figure
//     here would be read as money by the person who pays it.
//   · **UNALLOCATED USAGE 3.1%** — NOT drawn, and OQ-327 is why: three
//     readings of "master vs unit meters" give three different numbers on the
//     same building, and the sign matters (sub-meters routinely exceed the
//     master). Nothing computes it anywhere in this product.
//
// ── THE "BILLED TO" COLUMN, AND WHY IT EXISTS NOW (DEF-560, DEF-4740) ─────
// ⚠ **THIS BLOCK USED TO BE HEADED *WHY THERE IS NO "BILLED TO" COLUMN* AND
// ITS REASONING EXPIRED ON 2026-09-01.** It read: a master row ANCHORS on the
// premises' first common area and covers the rest through open
// `service_agreements`; `GET /accounts` filters on `accounts.unit_id`, which is
// the anchor; so the endpoint can answer *is there a master for this premises*
// and cannot answer *does it cover THIS area*. All of that was true, and
// `CR-056` W1 / `BR-CUS-1010` then moved the master account onto the ADDRESS —
// it carries `premises_id` and names no unit at all — so the question the old
// note could not ask is the question the endpoint now answers. The column was
// never re-drawn, which is `DEF-4740`: *"the blueprint calls `Billed to` the
// only question that tab exists to answer."*
// **What survives of DEF-560, and it is stated on screen rather than guessed:**
// `POST /accounts/master` still accepts `unit_ids` to narrow coverage, so a
// premises carrying MORE THAN ONE master cannot say which of them pays for a
// given area. That case renders three words and a tooltip and never names one
// of them; the ordinary case — one master at an address — names it on every
// row, which is what the blueprint draws.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  ACCOUNT_KIND_MASTER,
  createMasterAccount,
  createUnit,
  getAccounts,
} from "@/api/endpoints";
import type { AccountRow, PremisesDetail, ServerWarning, UnitRow } from "@/api/endpoints";
import {
  CheckboxField,
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome, ServerErrorEnvelope } from "@/components/FormModal";
import { DataTable } from "@/components/DataTable";
import { Disclosure } from "@/components/Disclosure";
import { EyeIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import { accountDetailPath, useAccountCategories } from "@/features/customers/customersShared";
import { ArrivesWithField } from "@/features/rating/ratingShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { toEnvelope } from "./PremisesListPage";
import {
  Dash,
  GuardedButton,
  MetersCell,
  premisesDetailPath,
  unitDetailPath,
  unitStatusTone,
  useRegional,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * BR-MET-101: a common area IS a unit with a flag. The FLAG is the queryable
 * fact — never `unit_type === "common_area"`, which is the legacy typing
 * migration 0016 backfilled from.
 */
/** `BR-CUS-1114` — the fewest live units a premises needs for a master account.
 *  The server's `customers.services.MASTER_ACCOUNT_MIN_UNITS`. */
export const MASTER_ACCOUNT_MIN_UNITS = 2;

/**
 * `BR-CUS-1114` (PO 2026-10-02: *"single family hime, single unit, we should
 * not do master account"*) — the reason the master form is closed on this
 * address, or `null` where it may open. Live DWELLINGS only, as on the server
 * (`customers.services.dwelling_units_at_premises`): an `inactive` row is a
 * removed unit, and a common area (`BR-MET-101`) is not a home.
 */
export function singleUnitMasterReason(
  units: readonly UnitRow[],
  t: Translator,
  /** `CR-162-BRC10` (Q1) — the premises type's *Account type*: `master`
   *  opens the form whatever the count, `regular` closes it; `null` or absent
   *  (a type nobody has answered) falls back to counting homes. */
  accountKind?: string | null,
): string | null {
  if (accountKind === "master") {
    return null;
  }
  if (accountKind === "regular") {
    return t("customers.account.master_not_for_single_family", {
      defaultValue: "Single-family homes have no master account. Open a regular account at Move-in.",
    });
  }
  const live = units.filter((unit) => unit.status !== "inactive" && !unit.is_common_area).length;
  return live >= MASTER_ACCOUNT_MIN_UNITS
    ? null
    : t("customers.account.master_needs_two_units", {
        defaultValue: "Single unit. Open a regular account.",
      });
}

export function commonAreaUnits(units: readonly UnitRow[]): UnitRow[] {
  return units.filter((unit) => unit.is_common_area);
}

export const premisesMasterQueryKey = (premisesId: string) =>
  ["accounts", "master-for-premises", premisesId] as const;

/** Distinct rows, first occurrence wins — the same master answers for each of
 *  its covered areas' queries only when it ANCHORS on them, but a premises may
 *  legitimately carry more than one master (each covering its own subset). */
export function distinctAccounts(rows: readonly AccountRow[]): AccountRow[] {
  const seen = new Set<string>();
  const out: AccountRow[] = [];
  for (const row of rows) {
    if (!seen.has(row.id)) {
      seen.add(row.id);
      out.push(row);
    }
  }
  return out;
}

/**
 * The master account(s) for this premises — **asked BY ADDRESS since
 * 2026-09-01 (`CR-056` W1 / `BR-CUS-1010`).**
 *
 * ⚠ **THIS USED TO FAN OUT ONE QUERY PER COMMON AREA, ON `f.unit_id=`, AND
 * THAT QUESTION NO LONGER FINDS THE ACCOUNT.** A master account is the owner's
 * account at an ADDRESS: it carries `premises_id` and names no unit at all, so
 * a unit-shaped filter answers nothing and the tab would report *"no master
 * account yet"* beside a Create button that then refuses `BR-CUS-1011`. The
 * server publishes `f.premises_id=` for exactly this, and it is still the
 * SERVER's own answer rather than a client-side match over a paginated
 * tenant-wide list, which is what the previous note was protecting.
 *
 * Three things get better with it and one gets no worse: ONE request instead
 * of one per common area; a premises with **no** common area is now asked
 * about instead of being skipped (`enabled` used to require at least one, and
 * such a premises can now hold a master); a master created before this change
 * is found too, because migration 0037 backfilled `premises_id` onto every
 * existing row; and the truncation the old note worried about is still
 * impossible, because the filter is the server's.
 */
export function useMasterAccounts(premises: PremisesDetail | undefined, client: ApiClient) {
  // ⚠ `undefined` IS A SUPPORTED ARGUMENT, and it is why the KPI tile can share
  // this query. S14 returns early while its detail is still loading, so a hook
  // that demanded a loaded `PremisesDetail` could only ever be called from
  // inside the tab — and the tile above the tabs would need a SECOND request
  // for the same rows. Disabled-until-known keeps one request for both.
  const premisesId = premises?.id ?? "";
  return useQuery({
    queryKey: premisesMasterQueryKey(premisesId),
    queryFn: async () => {
      const page = await getAccounts(
        { filters: { kind: ACCOUNT_KIND_MASTER, premises_id: premisesId }, per: 25 },
        client,
      );
      return distinctAccounts(page.results);
    },
    enabled: premisesId !== "",
    retry: false,
  });
}

/**
 * DEF-559 — THE REFUSAL SENTENCE, CHOSEN FROM THE SERVER'S OWN `reason`.
 *
 * `services._master_attachment_units` raises two BR-CUS-068 refusals with NO
 * `message_key`, so both resolve to the generic `errors.biz-state` — *"That
 * isn't possible in the current state."* — which names neither the property
 * nor the unit. The backend lane said so in its own comment and left the
 * sentence to this lane (BR-SHL-020 wants plain language naming the premises
 * and the unit).
 *
 * ⚠ **THIS IS NOT A CLIENT-SIDE GUESS ABOUT WHY.** Every input is the
 * server's: `br_ref` says which rule refused, `params.reason` is the server's
 * own discriminator, and `params.label` / `params.account_no` are the server's
 * own names. What this function does is pick the catalogue key the server did
 * not send — it never invents a cause and never renders server prose (the
 * DEF-322 rule: `refusalParams` still drops `detail`).
 *
 * The right fix is a `message_key` on those two raises, at which point this
 * mapping deletes itself; DEF-559 carries that.
 */
export const MASTER_REFUSAL_KEYS: Record<string, string> = {
  no_common_area_units: "metering.premises.master.refusal.noCommonAreas",
  not_a_common_area_of_this_premises: "metering.premises.master.refusal.notACommonArea",
};

export function masterRefusalEnvelope(envelope: ServerErrorEnvelope): ServerErrorEnvelope {
  const params = envelope.params ?? {};
  const label = typeof params.label === "string" && params.label !== "" ? params.label : null;
  // ── DEF-565 · THE GUARD THAT ACTUALLY FIRES, NOT THE ONE THIS FILE EXPECTED
  //
  // `create_master_account` checks each covered unit IN ORDER:
  // `_refuse_if_unit_occupied` (**BR-CUS-017**) runs BEFORE
  // `_refuse_if_master_covered` (**BR-CUS-068**) — and the first master account
  // OCCUPIES its anchor common area. So the commonest refusal on this screen,
  // "this premises already has a master", arrives carrying **BR-CUS-017**, and
  // the branch below was originally gated on BR-CUS-068 and never ran. A clerk
  // read *"Another account already occupies this unit. Move that one out
  // first."* — advice nobody can follow, because nobody moves out of a hallway.
  // Found by clicking the second Create in a browser; no gate saw it, because
  // the key resolves perfectly and the sentence is merely WRONG.
  //
  // ⚠ **THE DISCRIMINATOR HERE IS THE ENDPOINT, AND THE SCREEN LEGITIMATELY
  // KNOWS IT.** This function is applied to the response of
  // `POST /accounts/master` and to nothing else, so every unit it can be told
  // about is a COMMON AREA. That is not a guess about the cause — it is a fact
  // about which call was made — and BR-CUS-017's own sentence stays exactly
  // right on the S18/S19 paths, which never come through here.
  if (envelope.message_key === "customers.account.unit_already_occupied") {
    if (envelope.br_ref === "BR-CUS-068") {
      // The DOUBLE-COVERAGE guard, which reaches a common area the existing
      // master covers WITHOUT anchoring on it (narrow the new master to only
      // the shared irrigation and this is the one that fires). Its params name
      // the unit AND say the holder is a master, so the sentence may say both.
      return {
        ...envelope,
        message_key:
          label === null
            ? "metering.premises.master.refusal.alreadyCoveredUnnamed"
            : "metering.premises.master.refusal.alreadyCovered",
      };
    }
    // BR-CUS-017's occupancy guard. Its params carry `account_no` and NO
    // `label`, and they do NOT say the occupant is a master — so the sentence
    // names the account and claims nothing else. Calling it "the master
    // account" here would assert something the payload never states.
    return { ...envelope, message_key: "metering.premises.master.refusal.areaTaken" };
  }
  if (envelope.br_ref !== "BR-CUS-068") {
    return envelope;
  }
  const reason = typeof params.reason === "string" ? params.reason : "";
  const key = MASTER_REFUSAL_KEYS[reason];
  if (key === undefined) {
    return envelope;
  }
  if (key === MASTER_REFUSAL_KEYS.not_a_common_area_of_this_premises && label === null) {
    // The server could not name the unit (it resolved no label), so neither
    // does the sentence — `{{label}}` rendering as "null" is DEF-332's shape.
    return { ...envelope, message_key: "metering.premises.master.refusal.notACommonAreaUnnamed" };
  }
  return { ...envelope, message_key: key };
}

/** Client validation is UX only — the SERVER is authoritative (B8 forms). */
export function masterAccountSchema(t: Translator) {
  return z.object({
    accountType: z.string().trim().min(1, t("metering.premises.master.typeRequired")),
    openedAt: z.string().trim().min(1, t("metering.premises.master.openedAtRequired")),
    coveredIds: z.array(z.string()).min(1, t("metering.premises.master.coverageRequired")),
  });
}

/** The payload `services.MASTER_CREATE_FIELDS` accepts, and nothing else. */
export function masterAccountPayload(input: {
  premisesId: string;
  accountType: string;
  openedAt: string;
  payer: string;
  coveredIds: readonly string[];
  allCommonIds: readonly string[];
  /** `DEF-CUS-9036` — sent only when there is one. */
  serviceRequestId?: string;
}): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    premises_id: input.premisesId,
    account_type: input.accountType,
    opened_at: input.openedAt,
  };
  // `unit_ids` is omitted when every common area is covered: the server's own
  // default IS "every active common area of the premises", and sending the
  // list we happen to have on screen would freeze a stale set instead.
  if (input.coveredIds.length !== input.allCommonIds.length) {
    payload.unit_ids = [...input.coveredIds];
  }
  // The payer defaults to `premises.owner_manager` SERVER-side; a name typed
  // here overrides it, and a blank one is not sent at all.
  if (input.payer.trim() !== "") {
    payload.contact = { full_name: input.payer.trim(), is_primary: true };
  }
  // `DEF-CUS-9036` — the approved request this account fulfils. The server
  // carries the customer the clerk linked on it (or the applicant, where none
  // was linked) and closes its pending move-in job.
  if ((input.serviceRequestId ?? "") !== "") {
    payload.service_request_id = input.serviceRequestId;
  }
  return payload;
}

// ── THE PRM-02 MASTER-ACCOUNT KPI TILE IS GONE (CR-089 `P4`, 2026-09-09) ───
//
// `MasterAccountKpiValue` stood here and rendered the property's fourth tile.
// `CR-089`'s agreed drawing replaces the four tiles with
// `Units · Assets · Owed here · Open work orders`, so it lost its only caller —
// and an exported component nothing renders is dead UI whichever direction it
// faces (hard-won law 2), so it is DELETED rather than left for the next reader
// to wire back in.
//
// ⚠ **NEITHER MASTER-ACCOUNT FACT WAS LOST, AND THEY ARE TWO DIFFERENT FACTS.**
//   · the PROPERTY's own master accounts — the ones that bill an owner for
//     shared space (`BR-CUS-068`) — are on the **Common areas** tab below,
//     linked, where the payer is stated beside them;
//   · the OWNER's master account (`BR-MET-400`) is on the Overview's **Owner**
//     fact, as `OwnerAccountBlock`'s own linked row.
// The tile could only ever show the first while the walkthrough's `PUJ-11`
// complaint was about the second: a tile reading *None yet* in italic that
// could not be pressed, beside an Owner row with a working **Find an owner**
// control saying the same thing. `useMasterAccounts` stays; the tab uses it.

// ── `Billed to`, as pure data (CR-089 p025 §6 · DEF-4740) ──────────────────

/**
 * Who pays for shared space at this address — the three answers, and no fourth.
 *
 * ⚠ **`several` IS NOT A FAILURE AND IT IS NOT A GUESS EITHER.** A premises may
 * carry more than one master account, each narrowed to its own subset of areas
 * by `POST /accounts/master`'s `unit_ids`, and nothing published says which
 * subset. Naming the first would assert coverage the payload never states —
 * which is the whole of `DEF-560` — so this returns the fact that there are
 * several and the cell says so in three words.
 */
export type BilledTo =
  | { kind: "none" }
  | { kind: "one"; account: AccountRow; payer: string | null }
  | { kind: "several" };

export function billedTo(
  masters: readonly AccountRow[],
  ownerManager: string | null,
): BilledTo {
  if (masters.length === 0) {
    return { kind: "none" };
  }
  if (masters.length > 1) {
    return { kind: "several" };
  }
  // The payer of RECORD: the account's own primary contact, falling back to the
  // premises' owner/manager, which is what `POST /accounts/master` fills the
  // contact FROM when the payload names nobody (BR-MET-151). Never `""`.
  const contact = masters[0].name;
  const payer = contact !== null && contact !== "" ? contact : (ownerManager ?? null);
  return { kind: "one", account: masters[0], payer: payer === "" ? null : payer };
}

/** What the SEARCH box matches on for the `Billed to` column — the payer's name
 *  and the account number, never the id. Empty for the two absent answers, so a
 *  search can never "find" a row by a word the row does not show. */
export function billedToText(billed: BilledTo): string {
  if (billed.kind !== "one") {
    return "";
  }
  return [billed.payer, billed.account.account_no].filter((part) => part).join(" ");
}

/** IS-3, client-side: this list's rows arrive inside `GET /premises/{id}`, so
 *  there is no server to ask. It matches what the row DISPLAYS — the area's
 *  name, its number, and the payer — and nothing it does not. */
export function commonAreaMatches(unit: UnitRow, q: string, payer: string): boolean {
  const needle = q.trim().toLowerCase();
  if (needle === "") {
    return true;
  }
  return [unit.label, unit.unit_no, payer]
    .filter((part): part is string => typeof part === "string" && part !== "")
    .some((part) => part.toLowerCase().includes(needle));
}

/**
 * IS-2, client-side, over the two sortable columns this tab declares.
 *
 * ⚠ **A ROW WITH NO FIGURE SORTS LAST IN BOTH DIRECTIONS, DELIBERATELY.** An
 * absent balance is *not measured*, not zero (`UnitRow.owed`), so folding it in
 * as a zero would put every vacant common area at the top of an ascending sort
 * and read as *these owe nothing*.
 */
export function compareCommonAreas(
  a: UnitRow,
  b: UnitRow,
  sort: string,
  dir: "asc" | "desc",
): number {
  const way = dir === "desc" ? -1 : 1;
  if (sort === "owed") {
    const left = owedAmount(a);
    const right = owedAmount(b);
    if (left === null && right === null) {
      return 0;
    }
    if (left === null) {
      return 1;
    }
    if (right === null) {
      return -1;
    }
    return (left - right) * way;
  }
  const left = a.label ?? a.unit_no ?? "";
  const right = b.label ?? b.unit_no ?? "";
  return left.localeCompare(right) * way;
}

/** The comparable number, or `null` when there is no figure to compare. Used
 *  for ORDERING only — the figure a person reads is `MoneyCell`'s, from the
 *  decimal string, because that is the one display path for money in this
 *  product (BR-SHL-023) and the only thing allowed to round it. */
function owedAmount(unit: UnitRow): number | null {
  const owed = unit.owed ?? null;
  if (owed === null || owed.balance === null || owed.balance_unavailable.length > 0) {
    return null;
  }
  return Number(owed.balance);
}

/** The `Billed to` cell. */
export function BilledToCell(props: { billed: BilledTo; premisesId: string; t: Translator }) {
  const { billed, t } = props;
  const tenantPath = useTenantPath();
  if (billed.kind === "none") {
    // The blueprint's own STATE for this: *"`Billed to` reads `Needs an owner`
    // and links to it, because a common area with nobody to bill is a real
    // problem, not a blank cell."* It links to the property's Overview, which
    // is where the Owner fact and its **Find an owner** control live.
    return (
      <InlineLinkTo
        to={tenantPath(`${premisesDetailPath(props.premisesId)}?tab=overview`)}
        title={t("metering.premises.common.needsOwnerWhy")}
      >
        {t("metering.premises.common.needsOwner")}
      </InlineLinkTo>
    );
  }
  if (billed.kind === "several") {
    // Three words in the cell, the whole sentence on the tooltip — a paragraph
    // here sets the height of every row (`tableTypes.TableColumnConfig.cell`).
    return (
      <Note as="span" title={t("metering.premises.common.billedToSeveralWhy")}>
        {t("metering.premises.common.billedToSeveral")}
      </Note>
    );
  }
  return (
    <span>
      {billed.payer ?? <Dash />}
      {billed.account.account_no !== null && (
        // The account NUMBER, quiet, exactly as drawn — never the uuid
        // (B14 rule 31).
        <>
          {" "}
          <InlineLinkTo to={tenantPath(accountDetailPath(billed.account.id))}>
            <span className="met-qualifier">{billed.account.account_no}</span>
          </InlineLinkTo>
        </>
      )}
    </span>
  );
}

/**
 * The `Owed` cell — the property Units tab's own three absences, from the
 * property Units tab's own keys.
 *
 * B14 rule 34 asks for one pair of words per fact across the product, so this
 * says what `UnitsListPage` says about exactly these three states rather than
 * minting a second wording that would drift on the first re-word.
 */
export function CommonAreaOwedCell(props: { unit: UnitRow; t: Translator }) {
  const { t } = props;
  // `undefined` and `null` are one answer here — see `UnitRow.owed`.
  const owed = props.unit.owed ?? null;
  if (owed === null) {
    return (
      <span title={t("metering.units.owed.vacantOwnerBilled")}>
        <Dash />
      </span>
    );
  }
  if (owed.balance === null || owed.balance_unavailable.length > 0) {
    return (
      <Note as="span" title={t("metering.units.owed.unreadableWhy")}>
        {t("metering.units.owed.unreadable")}
      </Note>
    );
  }
  if (owed.balance_not_yet_billable) {
    return (
      <Note as="span" title={t("customers.accounts.balance.awaitingWhy")}>
        {t("customers.accounts.balance.awaiting")}
      </Note>
    );
  }
  return <MoneyCell amount={owed.balance} currency={owed.balance_currency ?? ""} />;
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface CommonAreasTabProps extends RegionalProps {
  premises: PremisesDetail;
  client?: ApiClient;
  t: Translator;
  /** BR-SHL-025 — null when this role may write. */
  writeBlockedReason: string | null;
  /** `DEF-CUS-9036` — the approved request the master account fulfils, or
   *  `""`. Read from `?request=` by the page; it rides the create so the
   *  request's linked customer and class are carried and its pending move-in
   *  job closes. */
  serviceRequestId?: string;
}

export function CommonAreasTab(props: CommonAreasTabProps) {
  const { t } = props;
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const [creating, setCreating] = useState(false);
  // CR-089 wave C `C2` — the tab's own "+ Add a common area".
  const [adding, setAdding] = useState(false);
  const queryClient = useQueryClient();
  const [warnings, setWarnings] = useState<readonly ServerWarning[]>([]);
  // ── DEF-4739 · THE SHARED TABLE, NOT THE IN-PANEL ONE ────────────────────
  // The request state is CLIENT-side here and that is not a shortcut: the rows
  // arrive inside `GET /premises/{id}` as `unit_rows`, so there is no second
  // request to page, and a building holds a handful of shared spaces. The state
  // object is still the framework's (`BR-SHL-011`), so the search box, the
  // column chooser and the pagination footer are the same controls, in the same
  // places, as every other list in the product.
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "area",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  const areas = commonAreaUnits(props.premises.unit_rows);
  const mastersQuery = useMasterAccounts(props.premises, client);
  const masters = mastersQuery.data ?? [];
  // DEF-SHL-3964 — HOISTED above the early return below. `useRegional` reads a
  // context, and this was spread inside `{creating && (…)}`: a hook whose
  // presence depended on whether the modal was open.
  const regional = useRegional(props);

  // ⚠ **THE PAYER OF RECORD, RESOLVED ONCE.** The account's own primary contact,
  // which the master path fills from `premises.owner_manager` when the payload
  // names nobody — so this is the payer of RECORD rather than the premises
  // column re-drawn, and the fallback is only reached when the account carries
  // no contact at all.
  const billed = billedTo(masters, props.premises.owner_manager);

  const addControl = (
    // ── CR-089 wave C task `C2` (`PUJ-13`) ─────────────────────────────────
    // ⚠ **EVERY NEW BUILDING READ *None on this premise*, AND THERE WAS NO WAY
    // OFF THAT SENTENCE FROM THIS TAB.** The create flow never offered to add a
    // common area (that is wave B's `B5`), and the tab's own empty state told a
    // clerk to go and *"flag one on the Units tab"* — a route they have to
    // already know, on a screen whose flag is a checkbox inside a unit's edit
    // form. So the tab that is ABOUT common areas was the one place a common
    // area could not be made.
    //
    // BR-SHL-025's posture, like every other write on this screen: a role that
    // may not write gets the control DISABLED with its reason, never hidden.
    <GuardedButton
      label={t("metering.premises.common.addAction")}
      reason={props.writeBlockedReason}
      variant="primary"
      onClick={() => setAdding(true)}
    />
  );
  const addModal = adding && (
    <AddCommonAreaModal
      premises={props.premises}
      client={client}
      onClose={() => setAdding(false)}
      onCreated={() => {
        setAdding(false);
        void queryClient.invalidateQueries({ queryKey: ["premises"] });
      }}
    />
  );

  const config: TableConfig<UnitRow> = {
    // Its OWN suffix, so this tab's column set is not the property Units tab's
    // (`tableTypes.screenId`'s own `SET-05` / `SET-05.cycles` precedent).
    screenId: "PRM-02.common",
    getRowId: (row) => row.id,
    searchFields: ["area", "billedTo"],
    searchPlaceholder: "metering.premises.common.searchPlaceholder",
    defaultSort: { sort: "area", dir: "asc" },
    // ⚠ **NO FILTERS, AND THAT IS THE DRAWING RATHER THAN AN OMISSION.**
    // `CR-089-p025` §5: *"No `ALL` chip and no `+ Filter` on this tab — that is
    // the Units tab's toolbar, not this one."* `BR-SHL-010` says an undeclared
    // capability never renders, so declaring none IS how that gets drawn, and
    // `FilterBar` is not composed here for the same reason.
    columns: [
      {
        key: "area",
        label: t("metering.premises.common.col.area"),
        identity: true,
        sortable: true,
        cell: (unit) => (
          // ⚠ **NO `Common` PILL IN THE NAME CELL** (`CR-089-p025` §12, drawn as
          // an absence): the tab is already about common areas, so a pill on
          // every row of it says nothing. It stays on the Units tab, where a
          // common area sits beside flats and the word is the whole point.
          <InlineLinkTo to={tenantPath(unitDetailPath(unit.id))}>
            {unit.label ?? unit.unit_no ?? t("metering.units.noNumber")}
          </InlineLinkTo>
        ),
      },
      {
        // ⚠ **WORDS, NEVER A TYPE CODE** — the blueprint's own instruction for
        // this column (*"What it is, in words — shared room, shared lighting,
        // car park — rather than a type code"*). The words come from the unit's
        // TYPE through the catalogue every other screen reads it through, so a
        // tenant that renames a type renames it here too. A common area created
        // from this tab's own modal carries no type yet and draws a dash —
        // reported as `DEF-MET-4750`, not filled with a guess.
        key: "whatItIs",
        label: t("metering.premises.common.col.whatItIs"),
        cell: (unit) =>
          unit.unit_type === null ? (
            <Dash />
          ) : (
            <span>{t(`metering.units.type.${unit.unit_type}`)}</span>
          ),
      },
      {
        key: "meters",
        label: t("metering.units.col.meters"),
        cell: (unit) => <MetersCell meters={unit.meters} t={t} />,
      },
      {
        // ⚠ **THE COLUMN THE TAB EXISTS FOR** (`CR-089-p025` §6): *"A `Billed
        // to` column naming the owner's account, because who pays for the
        // corridor light is the only question this tab exists to answer."*
        //
        // ⚠ **IT IS ANSWERABLE NOW AND WAS NOT WHEN `DEF-560` WAS FILED.** That
        // defect's reasoning was that a master ANCHORS on one common area and
        // `GET /accounts` filtered on `accounts.unit_id`, so the endpoint could
        // not say which areas a master covered. `CR-056` W1 / `BR-CUS-1010`
        // moved the master onto the ADDRESS — it carries `premises_id` and
        // names no unit at all — and `useMasterAccounts` asks by address. One
        // master at an address is therefore the payer for every common area on
        // it, which is exactly the two rows the blueprint draws.
        //
        // The remainder of `DEF-560` is REAL and is stated rather than guessed:
        // `POST /accounts/master` accepts `unit_ids` to narrow coverage, so a
        // premises carrying MORE THAN ONE master cannot say which one pays for
        // a given area. That case says so in three words with the sentence on
        // the tooltip, and never names one of them.
        key: "billedTo",
        label: t("metering.premises.common.col.billedTo"),
        cell: () => <BilledToCell billed={billed} premisesId={props.premises.id} t={t} />,
      },
      {
        // `numeric` is what right-aligns it and gives it tabular numerals, so a
        // column of figures reads as a column. The three absences are the
        // property Units tab's own, from its own keys — one fact, one pair of
        // words across the product (B14 rule 34).
        key: "owed",
        label: t("metering.units.col.owed"),
        numeric: true,
        sortable: true,
        cell: (unit) => <CommonAreaOwedCell unit={unit} t={t} />,
      },
      {
        key: "status",
        label: t("metering.units.col.status"),
        cell: (unit) => (
          <StatusPill tone={unitStatusTone(unit.status)}>
            {t(`metering.units.status.${unit.status}`, { defaultValue: unit.status })}
          </StatusPill>
        ),
      },
      {
        // Drawn with no header and three glyphs. The kit gives every table's
        // action column a header (`metering.col.actions`) and only ONE of the
        // three glyphs has somewhere to go today, so this draws the one that
        // does rather than two that refuse — hard-won law 2. `DEF-MET-4751`
        // carries the edit and the overflow.
        key: "actions",
        label: t("metering.col.actions"),
        cell: (unit) => (
          <RowActions>
            <RowActionLink
              icon={<EyeIcon />}
              label={t("metering.premises.common.action.open")}
              to={tenantPath(unitDetailPath(unit.id))}
            />
          </RowActions>
        ),
      },
    ],
  };

  const matched = areas.filter((unit) => commonAreaMatches(unit, state.q, billedToText(billed)));
  const sorted = [...matched].sort((a, b) => compareCommonAreas(a, b, state.sort, state.dir));
  const from = (state.page - 1) * state.per;
  const rows = sorted.slice(from, from + state.per);

  return (
    <Panel as="section">
      {/* ⚠ **NO `<h3>` AND NO EXPLAINER PARAGRAPH** — the tab strip above
          already says *Common areas*, and the blueprint's own COGNITIVE LOAD
          row for this screen is *"Seven columns, no prose beyond the empty
          state."* B14 rule 32's description budget is the same instruction one
          level up. What the paragraphs said is not deleted: it is in the
          closed disclosure at the foot, which is what that rule asks for. */}
      <div className="flex flex-wrap items-center justify-end gap-2 mb-3">
        {/* B14 rule 15: an ordinary button says a WORD (PO 2026-08-20). This one
            is SECONDARY because the tab's drawn PRIMARY ACTION is the add.
            ⚠ **AND IT IS ABSENT WHILE THERE IS NOTHING TO COVER**, which is not
            the BR-SHL-025 posture and is deliberate: `create_master_account`
            refuses `no_common_area_units` outright, so a control here could
            only ever be pressed and refused. The drawing agrees — the tab's one
            action is the add — and the empty state offers exactly that. */}
        {areas.length > 0 && (
          <GuardedButton
            label={
              masters.length === 0
                ? t("metering.premises.master.create")
                : t("metering.premises.master.createAnother")
            }
            // `BR-CUS-1114` (PO 2026-10-02) — a master account only on a
            // building of two or more units; disabled WITH its reason below
            // that (BR-SHL-025). The server refuses the same way.
            reason={
              props.writeBlockedReason ??
              singleUnitMasterReason(props.premises.unit_rows, t, props.premises.premises_account_kind)
            }
            variant="secondary"
            onClick={() => setCreating(true)}
          />
        )}
        {addControl}
      </div>

      <DataTable<UnitRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={matched.length}
        // ⚠ **THE MASTER READ IS PART OF *LOADING*, NOT A LATER FILL.** `Billed
        // to` is the question this tab exists to answer, so rows drawn before
        // that query lands would show the answer as absent for a moment — and
        // *nobody pays for this* is the one wrong thing this column can say.
        //
        // ⚠ **AND ONLY WHILE THERE IS A ROW TO ANSWER FOR.** An address with no
        // shared space needs no payer, so waiting on that query there would put
        // a skeleton over the empty state — which is the one thing a clerk
        // arriving at a new building actually needs to see, and the state the
        // whole of `C2` exists to fix.
        loading={areas.length > 0 && mastersQuery.isPending}
        empty={{
          // A18 §4, and the blueprint's STATES row: *"Says what a common area
          // is — a shared space with its own meter, billed to the owner — and
          // offers to add one."* It used to point at the Units tab instead.
          title: t("metering.premises.common.emptyTitle"),
          helper: t("metering.premises.common.emptyHelper"),
          ctaLabel: t("metering.premises.common.addAction"),
          ctaReason: props.writeBlockedReason,
          onCta: () => setAdding(true),
        }}
      />

      {warnings.length > 0 && (
        <ul className="met-panel-hint" role="status">
          {warnings.map((warning) => (
            <li key={`${warning.code}:${String(warning.unit_id)}`}>
              {t("metering.premises.master.warning.noServicePoints", {
                label: String(warning.label ?? ""),
              })}
            </li>
          ))}
        </ul>
      )}

      {/* B14 rule 32 — a stated absence is CLOSED by default. Nothing here was
          deleted when the prose came off the tab: BR-MET-101's own sentence and
          the three figures r10 draws that nothing can source are all still
          stated, still cited, and now cost a clerk nothing to skip. */}
      <Disclosure title={t("metering.premises.common.notes")}>
        <Note>{t("metering.premises.common.masterCallout")}</Note>
        <ArrivesWithField
          label={t("metering.premises.common.commonBill")}
          message={t("metering.premises.common.commonBillArrivesWith")}
          tracks="OQ-314"
        />
        <ArrivesWithField
          label={t("metering.premises.common.unallocated")}
          message={t("metering.premises.common.unallocatedArrivesWith")}
          tracks="OQ-327"
        />
        <ArrivesWithField
          label={t("metering.premises.common.coverage")}
          message={t("metering.premises.common.coverageArrivesWith")}
          tracks="DEF-560"
        />
      </Disclosure>

      {addModal}

      {creating && (
        <CreateMasterAccountModal
          premises={props.premises}
          areas={areas}
          serviceRequestId={props.serviceRequestId ?? ""}
          client={client}
          {...regional}
          onClose={() => setCreating(false)}
          onCreated={(created) => {
            setCreating(false);
            setWarnings(created.warnings);
          }}
        />
      )}
    </Panel>
  );
}

// ── The create ─────────────────────────────────────────────────────────────

/**
 * `CR-089` wave C task `C2` (`PUJ-13`) — **adding a common area, from the tab
 * that is about them.**
 *
 * ⚠ **A COMMON AREA IS A UNIT WITH A FLAG, AND THIS MODAL IS THAT SENTENCE.**
 * `BR-MET-101` (PO 2026-08-21, option A of three): *"a common area IS a Unit"*
 * — meters attach to units, services attach to units, and reads, plans, routes,
 * cycles and bill assembly all key off a unit, so a second table would teach
 * every read path a second shape for no capability we would not already have.
 * This posts `POST /units` with `is_common_area: true`. There is no second
 * endpoint and no second concept.
 *
 * ⚠ **IT IS NOT THE ADD-UNITS WIZARD, AND IT IS NOT ALLOWED TO BECOME ONE.**
 * That wizard (`S16`) does bulk creation with a numbering pattern, a services
 * grid, a meter grid and a plan panel; a hallway needs a name. Three fields is
 * the whole point — a clerk who wanted the wizard already has the *New unit*
 * button in this page's header.
 *
 * ⚠ **`is_common_area` IS FIXED TRUE AND IS SHOWN RATHER THAN HIDDEN.** It is
 * the field that decides whether this row bills a tenant or the owner
 * (`BR-MET-094` — the flag is *"what separates a common area from a vacant unit
 * billed to the owner"*), so a person committing this is told what they are
 * committing. `BR-SHL-032`: a commit names what it is about to do.
 *
 * ⚠ **NO NUMBER FIELD.** `unit_no` comes from the tenant's own `BR-TEN-035`
 * series, allocated server-side; a box here would either invite a clash or be a
 * database id on screen, and B14 rule 31 forbids the second.
 */
export interface AddCommonAreaModalProps {
  premises: PremisesDetail;
  client?: ApiClient;
  onClose: () => void;
  onCreated: () => void;
}

export function commonAreaSchema(t: Translator) {
  return z.object({
    label: z.string().trim().min(1, t("metering.premises.common.addLabelRequired")),
  });
}

export function AddCommonAreaModal(props: AddCommonAreaModalProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const [label, setLabel] = useState("");

  const create = useMutation({
    mutationFn: () =>
      createUnit(
        {
          premises_id: props.premises.id,
          label: label.trim(),
          // BR-MET-101 — the flag IS the common area. Sent explicitly rather
          // than relying on a server default, because there is no such default
          // and a unit created without it is an ordinary flat.
          is_common_area: true,
        },
        client,
      ),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await create.mutateAsync();
      props.onCreated();
      return { ok: true };
    } catch (error) {
      // The server's own refusal, unchanged — a duplicate label on this
      // premises is `_check_unit_label_unique`'s and it names the field.
      return { ok: false, error: toEnvelope(error) as ServerErrorEnvelope };
    }
  }

  return (
    <FormModal
      title={t("metering.premises.common.addTitle")}
      kicker={t("metering.kicker")}
      schema={commonAreaSchema(translate)}
      values={{ label }}
      submitLabel={t("metering.premises.common.addSubmit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* BR-SHL-032 — the commit names what it is about to do, and the thing it
          is about to do is the part a clerk cannot see: this row will bill the
          owner rather than a tenant. */}
      <Note>{t("metering.premises.common.addExplainer")}</Note>

      <TextField
        id="common-area-premises"
        label={t("metering.premises.master.property")}
        value={
          [props.premises.premise_no, props.premises.address_line]
            .filter((part) => part)
            .join(" · ")
        }
        readOnly
        onChange={() => undefined}
      />

      <TextField
        id="common-area-label"
        label={t("metering.premises.common.addLabel")}
        value={label}
        required
        onChange={setLabel}
        help={t("metering.premises.common.addLabelHelp")}
      />
    </FormModal>
  );
}

export interface CreateMasterAccountModalProps extends RegionalProps {
  premises: PremisesDetail;
  areas: readonly UnitRow[];
  /** `DEF-CUS-9036` — see `CommonAreasTabProps.serviceRequestId`. */
  serviceRequestId?: string;
  client?: ApiClient;
  onClose: () => void;
  onCreated: (created: { account_no: string | null; warnings: ServerWarning[] }) => void;
}

/**
 * BR-CUS-068's create, and every field on it is one the server accepts.
 *
 * ⚠ **THERE IS NO STATUS FIELD AND NO DRAFT STEP, DELIBERATELY.** The master
 * account is created ACTIVE and ATTACHED in one call — an unattached master is
 * exactly the half-built state the ruling closed. BR-CUS-018's pending-first
 * default is the S18 wizard's rule, not this path's.
 *
 * ⚠ **THERE IS NO UNIT PICKER EITHER, only a coverage checklist.** The anchor
 * is DERIVED server-side (the premises' first common area, deterministic), so
 * an anchor field here would be a second, disagreeing source of truth for a
 * fact `accounts.unit_id` already holds.
 */
export function CreateMasterAccountModal(props: CreateMasterAccountModalProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const { dateFormat } = useRegional(props);

  const [accountType, setAccountType] = useState("");
  const categories = useAccountCategories(client);
  // BR-TEN-043 / BR-CUS-022: the date the OPERATOR states. Nothing pre-fills
  // "today" — this date opens every service agreement the account attaches.
  const [openedAt, setOpenedAt] = useState("");
  const [payer, setPayer] = useState("");
  const [coveredIds, setCoveredIds] = useState<string[]>(props.areas.map((unit) => unit.id));

  const create = useMutation({
    mutationFn: () =>
      createMasterAccount(
        masterAccountPayload({
          premisesId: props.premises.id,
          accountType,
          openedAt,
          payer,
          coveredIds,
          allCommonIds: props.areas.map((unit) => unit.id),
          serviceRequestId: props.serviceRequestId ?? "",
        }),
        client,
      ),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const created = await create.mutateAsync();
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["premises"] });
      props.onCreated({ account_no: created.account_no, warnings: created.warnings });
      return { ok: true };
    } catch (error) {
      // DEF-559 — the envelope, with the catalogue key the server did not
      // send. FormModal renders `message_key` + params exactly as it always
      // has; nothing about the rendering path changes.
      return { ok: false, error: masterRefusalEnvelope(toEnvelope(error)) };
    }
  }

  const owner = (props.premises.owner_manager ?? "").trim();

  return (
    <FormModal
      title={t("metering.premises.master.title")}
      kicker={t("metering.kicker")}
      schema={masterAccountSchema(translate)}
      values={{ accountType, openedAt, coveredIds }}
      submitLabel={t("metering.premises.master.submit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* BR-SHL-032: the commit NAMES what it is about to do. */}
      <Note>{t("metering.premises.master.explainer")}</Note>

      <TextField
        id="master-premises"
        label={t("metering.premises.master.property")}
        value={
          [props.premises.premise_no, props.premises.address_line].filter((part) => part).join(" · ")
        }
        readOnly
        onChange={() => undefined}
      />

      {/* The coverage checklist. Every common area is checked, because the
          server's own default covers them all; unchecking one narrows the
          `unit_ids` list, which is how a second master takes the areas the
          first one does not.

          ⚠ **THE BOXES NEEDED A GROUP LABEL AND DID NOT HAVE ONE**, which was
          visible the moment this modal was opened in a browser and invisible to
          every test: two bare captions floated between "Property" and "Account
          type" with nothing saying what ticking one MEANT. `CheckboxField` is
          the shared kit's own control and draws its own caption; what the kit
          has no shape for is a GROUP of them, so the group is a `.field` like
          every other row of this form. */}
      <div className="field">
        <span className="field-label">{t("metering.premises.master.coverage")}</span>
        <p className="field-help">{t("metering.premises.master.coverageHelp")}</p>
        <div className="flex flex-col gap-1 items-start">
          {props.areas.map((unit) => (
            <CheckboxField
              key={unit.id}
              id={`master-covers-${unit.id}`}
              label={unit.label ?? unit.unit_no ?? t("metering.units.noNumber")}
              checked={coveredIds.includes(unit.id)}
              onChange={(checked) =>
                setCoveredIds((current) =>
                  checked
                    ? [...current, unit.id]
                    : current.filter((id) => id !== unit.id),
                )
              }
            />
          ))}
        </div>
      </div>

      {/* ⛔ **FETCHED — DEF-684, 2026-08-26.** These options were
          `ACCOUNT_CATEGORIES`, the four codes BR-CUS-094 (PO 2026-08-24)
          superseded. `government` is LEGACY and no NEW record may carry it —
          and a master account is a new record every time this modal is used. */}
      <SelectField
        id="master-account-type"
        label={t("metering.premises.master.accountType")}
        value={accountType}
        required
        placeholder={t("metering.premises.master.accountTypePlaceholder")}
        options={categories.selectable.map((category) => ({
          value: category.code,
          label: category.name,
        }))}
        // BR-CUS-068 judgment 1 (decision log 2026-08-22): `master` is NOT a
        // fifth category. A master account still has a consumer category — a
        // residential building's shared hallway is residential.
        help={t("metering.premises.master.accountTypeHelp")}
        onChange={setAccountType}
      />

      <DatePickerField
        id="master-opened-at"
        label={t("metering.premises.master.openedAt")}
        value={openedAt}
        onChange={setOpenedAt}
        required
        dateFormat={dateFormat}
        help={t("metering.premises.master.openedAtHelp")}
      />

      <TextField
        id="master-payer"
        label={t("metering.premises.master.payer")}
        value={payer}
        onChange={setPayer}
        help={
          owner === ""
            ? t("metering.premises.master.payerRequiredHelp")
            : t("metering.premises.master.payerHelp", { owner })
        }
      />
    </FormModal>
  );
}

export default CommonAreasTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-001 + BR-CUS-068 (PO ruling 2026-08-22, OQ-314 second half) · BR-MET-101 (PO 2026-08-21)
// generated: 2026-08-22 by the master-accounts SCREEN lane (the half the backend lane recorded as owed: PRM-02's master-account cell and the refusal sentences)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest✔ (see the lane report) · g40 unmounted-components at baseline✔ · g32 refusal keys at baseline✔ · clicked through in Chromium against a live Django + Postgres
// exceptions: E3 r10's `JULY COMMON BILL $69.60` and `UNALLOCATED USAGE 3.1%` tiles are NOT drawn — the first needs the bill-assembly half (billing/gather.py prices the anchor unit only), the second has no computation anywhere (OQ-327). Both render as stated absences citing what they wait for · E3 no per-row "billed to master" cell: coverage is not served (DEF-560), only the anchor is queryable · E3 the account number is the BR-TEN-035 tenant series, not r10's `MA-` prefix (decision log 2026-08-22, judgment 4) · E4 DEF-559 — the two BR-CUS-068 refusals carry no `message_key`, so this file maps the SERVER's own `reason`/`br_ref` onto a catalogue key before FormModal renders it; no server prose reaches the screen and `refusalParams` still drops `detail`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
