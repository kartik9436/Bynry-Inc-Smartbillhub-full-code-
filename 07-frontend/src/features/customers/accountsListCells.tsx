// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W2 (B18 §5.1.2) tasks 2.3, 2.6 and 2.9(b) — the `AGEING`
//           column the design splits off `STATUS`, the `+N` service-chip
//           overflow, and the `CUSTOMER #` cell the PO asked for on 2026-08-24.
//           Screens: S17 (the Accounts tab of the Accounts page).
// Story:    US-CUS-001 (the S17 list contract).
// Rules:    BR-CUS-053 (AMENDED 2026-08-24, PO ruling — `CUSTOMER #` is a
//           COLUMN as well as a search term) · BR-CUS-054 (the first-class
//           customer entity the number belongs to; the link is N:M) ·
//           BR-CUS-016 (ageing is DERIVED from a receivable position and is
//           NEVER stored — so a row with no derivable position renders `—`,
//           never `Current`) · BR-CUS-048 (the four ageing bands: current ·
//           31–60 · 61–90 · 90+) · BR-CUS-015 (one chip per ACTIVE service
//           agreement) · BR-SHL-023 (one formatting path) · B14 rule 20 (one
//           table type) · B14 rule 21 (Tailwind utilities — this file adds NO
//           class to any stylesheet and is registered in
//           `styles/route-b-migrated.txt` so the real compiler owns its
//           utilities).
// ───────────────────────────────────────────────────────
// WHY THIS IS ITS OWN FILE AND NOT MORE OF `AccountsListPage.tsx`.
// `AccountsListPage.tsx` is a pre-Route-B screen: it styles itself from
// `customers.css` and G31 therefore holds it to "every class this file names is
// declared by a stylesheet". B14 rule 21 says new UI is Tailwind and adds no
// stylesheet class, and the CSS ceiling in `g31_declared_classes.py` may only
// FALL. Those two facts cannot both be honoured inside one unmigrated file, so
// the new markup lives here, where the ledger hands it to
// `routeBUtilities.test.ts` and the actual Tailwind compiler.
//
// ⚠ THE AGEING FIELDS ARE TYPED HERE AND NOT IN `api/endpoints.ts`, AND THAT IS
// A REPORTED GAP, NOT A DESIGN. `apps/customers/selectors.ageing_cells` serves
// four keys on every S17 row as of 2026-08-24 and `AccountRow` does not declare
// one of them. `src/api/endpoints.ts` belongs to another lane this session, so
// this file declares the shape it reads as an INTERSECTION with the wrapper's
// own row type — `AccountRow & Partial<AccountAgeingCells>` — which is
// assignable from `AccountRow` and therefore needs no cast anywhere. The four
// keys belong in `AccountRow` the moment that file is writable; until then this
// is the one place they are named.
//
// ⚠ AMENDED 2026-08-24 (CR-030 W2 close-out, T2.9). `src/api/endpoints.ts` WAS
// writable this session — it was clean in the shared tree — so `customer_no`
// went into `AccountRow` where it belongs and is NOT typed here. The four
// `ageing_*` keys above were deliberately left where they are: adding them
// would have been a second, unrelated change to a file six lanes share, on a
// day one of them was already editing three of the fixtures that type depends
// on. The gap the paragraph above describes is therefore still open and still
// owed — it is now the only thing in it that is true.
import { ACCOUNT_KIND_MASTER } from "@/api/endpoints";
import type { AccountRow } from "@/api/endpoints";
import { AgeCell } from "@/components/AgeCell";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { serviceBadge } from "@/features/rating/ratingShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { Dash, DRAFT_STATUS_CODE } from "./customersShared";

// ── The AGEING vocabulary (BR-CUS-048), as the server spells it ────────────

/**
 * `apps/customers/models.AccountOpeningBucket.BUCKETS` verbatim, in ageing
 * order. The server's `AGEING_SEGMENTS` is that same tuple, so a fifth band
 * cannot reach the wire without reaching the schema first.
 *
 * ⚠ **THIS IS NOT `AccountRow.aging`.** That field is BILLING's invoice-derived
 * display state ("Current / 30d past / 60+ past"), it is still served null, and
 * it is a DIFFERENT VOCABULARY. The two sit side by side deliberately and the
 * backend lane reported it on 2026-08-24: when billing publishes
 * `account_aging_state`, one vocabulary has to win, and that is a ruling rather
 * than a lane's merge. Nothing in this file reads `aging`.
 */
export const AGEING_SEGMENTS = ["current", "d31_60", "d61_90", "d90_plus"] as const;
export type AgeingSegment = (typeof AGEING_SEGMENTS)[number];

/** `selectors.ageing_cells` — the four keys it puts on every S17 row. */
export interface AccountAgeingCells {
  /** One of `AGEING_SEGMENTS`, or **null** — and null is `—`, never `Current`. */
  ageing_segment: AgeingSegment | null;
  /** Calendar days past due behind the band. Null whenever the segment is. */
  ageing_days_past_due: number | null;
  /** WHERE the claim comes from, as data: `"opening_buckets"` today. */
  ageing_source: string | null;
  /** Absence WITH its reason (hard-won law 1), or null when a band was found. */
  ageing_unavailable: readonly { code: string; br_ref: string; detail: string }[] | null;
}

/**
 * The S17 row as this screen reads it: the wrapper's own type plus the four
 * ageing keys the endpoint serves and the wrapper does not yet declare. Every
 * key is optional, so an `AccountRow` is assignable to it unchanged and no cast
 * is needed at any call site — an `undefined` segment reads exactly like the
 * `null` the server sends, which is the same cell either way.
 */
export type AccountRowWithAgeing = AccountRow & Partial<AccountAgeingCells>;

/** The segment on a row, narrowed to the served vocabulary or null. */
export function ageingSegmentOf(row: AccountRowWithAgeing): AgeingSegment | null {
  const raw = row.ageing_segment;
  return raw !== undefined && raw !== null && (AGEING_SEGMENTS as readonly string[]).includes(raw)
    ? raw
    : null;
}

/**
 * The pill tone per band. `current` is NOT success-green: it means "this
 * account's oldest receivable position is inside its terms", which is the
 * ordinary state and not an achievement — and colouring it green beside a
 * `Marked disconnect` status pill in the next column reads as two conflicting
 * claims. 61–90 and 90+ are both the danger tier, because r10 draws the accent
 * on the BALANCE from 60+ up (`[shot]`: `$542.10` in the accent at `60+ past`).
 */
export function ageingTone(segment: AgeingSegment): StatusTone {
  if (segment === "current") {
    return "neutral";
  }
  if (segment === "d31_60") {
    return "warning";
  }
  return "danger";
}

/**
 * The `AGEING` cell (B18 §5.1.2's new column), derived and never stored.
 *
 * ⚠ **NULL RENDERS `—` AND CARRIES ITS REASON ON HOVER.** It is not "Current":
 * an account with no derivable receivable position is UNKNOWN, and "Current" is
 * a claim about a customer's money that nobody computed. That substitution is
 * DEF-127's mistake in a different cell, and the server sends
 * `ageing_unavailable` precisely so this cell can say which half is missing
 * rather than shrug.
 */
export function AgeingCell(props: { row: AccountRowWithAgeing; t: Translator }) {
  const segment = ageingSegmentOf(props.row);
  if (segment === null) {
    // ⚠ **SINCE `DEF-CUS-10181` A NULL IS AN ANSWER — NOTHING OWED AGES.**
    // The band reads the oldest unpaid bill as well as the migrated buckets,
    // so `—` means a zero or credit balance and carries no reason (B14 rule
    // 33: rationale is zero words). Only a deployment where the bill half
    // could not be asked serves `ageing_unavailable`, and then its sentence
    // rides on hover. The old catalogue fallback said the figure could not be
    // worked out, which stopped being true.
    const served = props.row.ageing_unavailable?.[0]?.detail;
    return (
      <span title={served !== undefined && served !== "" ? served : undefined} data-ageing="none">
        <Dash />
      </span>
    );
  }
  // The band is the label; the exact age rides on the tooltip, because a column
  // of "184 days" is a different column from the one B18 §5.1.2 draws.
  const days = props.row.ageing_days_past_due;
  const title =
    days !== undefined && days !== null
      ? props.t("customers.accounts.ageing.daysPastDue", { days })
      : undefined;
  return (
    <span title={title}>
      <StatusPill tone={ageingTone(segment)}>
        {props.t(`customers.accounts.ageing.${segment}`)}
      </StatusPill>
    </span>
  );
}

// ── The `ACCOUNT AGE` cell (DEF-CUS-10180, PO 2026-10-17) ──────────────────

/**
 * PO ruling 2026-10-17 — *"Column Account age with the Opened (or closed date)
 * beneath"*. The age itself is the SHARED `AgeCell` (PO: *"use same code
 * components"*, B14 rule 43) — the same arithmetic and words as premises,
 * units and assets; this function only chooses what goes into it:
 *
 *   * start = `opened_at` (move-in, or activation; the CR-181 reopen rewrites
 *     it, so a reopened account restarts — rule 6);
 *   * end = `closed_at` — a closed account stops ageing (rule 2), and its
 *     second line says `closed 06/30/2026`;
 *   * no Opened date = pending activation → **Not opened** (rule 5), which is
 *     a state and not a dash.
 */
export function AccountAgeCell(props: {
  row: AccountRowWithAgeing;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const opened = props.row.opened_at;
  // Rule 5 keys off the STATE: a pending account may already carry the
  // move-in date it will open on, and it is still not open.
  if (
    props.row.status === DRAFT_STATUS_CODE ||
    opened === null ||
    opened === undefined ||
    opened === ""
  ) {
    return (
      <span className="text-neutral-600 whitespace-nowrap" data-account-age="not-opened">
        {props.t("customers.accounts.age.notOpened")}
      </span>
    );
  }
  const closed = props.row.closed_at ?? null;
  const note =
    closed !== null && closed !== ""
      ? props.t("customers.accounts.age.closedOn", {
          date: formatDate(closed, props.timeZone, props.dateFormat),
        })
      : formatDate(opened, props.timeZone, props.dateFormat);
  return (
    <span data-account-age={closed !== null && closed !== "" ? "closed" : "open"}>
      <AgeCell start={opened} end={closed} note={note} timeZone={props.timeZone} />
    </span>
  );
}

// ── The `CUSTOMER #` cell (CR-030 W2 T2.9(b)) ──────────────────────────────

/**
 * B18/BR-CUS-053's `CUSTOMER #` column, AMENDED 2026-08-24 by PO ruling.
 *
 * The PO asked for this as a question about work they expected to be done —
 * *"we were suppose to add customer # comlume what happened to that"* — and the
 * rule's own words for this half are *"the list renders `CUSTOMER #` as a
 * column, available through the shared column selector"*.
 *
 * ⚠ **THE EMPTY CELL IS A DASH WITH A REASON, AND THE REASON IS NOT "AWAITING
 * SOMETHING".** Compare `AgeingCell` two functions up, which renders an
 * absence because a figure could not be DERIVED. Nothing failed here: an
 * account with no `customer_accounts` link simply has no customer entity behind
 * it, which is an ordinary and permanent state for every account created before
 * BR-CUS-054's table existed and for every import row that carried neither a
 * reference nor a name. So it reads *"No customer number"* rather than
 * *"Awaits …"* — the second would promise that one is coming.
 *
 * ⚠ **NOT MONOSPACED AND NOT A LINK.** It is not a link because the customer
 * sub-link was **CUT by PO ruling on 2026-08-24** (*"okay dont link it"*, W2
 * task 2.5), so there is nothing at the other end of one — and `ACCOUNT_FILTERS`
 * declares no `customer_id` for it to filter by either. It is a plain cell so
 * that the `cus-id` treatment stays what it has always been: the identity
 * column that opens S21.
 */
export function CustomerNoCell(props: { row: AccountRowWithAgeing; t: Translator }) {
  const value = props.row.customer_no;
  // `undefined` and `null` are ONE cell: the wrapper's type carries the field
  // as optional only because three fixtures in other lanes' files have not been
  // updated (see `AccountRow.customer_no`), and a row served by the real
  // endpoint always carries the key.
  if (value === undefined || value === null || value === "") {
    return <Dash>{props.t("customers.accounts.customerNo.none")}</Dash>;
  }
  return <span>{value}</span>;
}

// ── The service chips, with B18 §5.1.2's `+N` overflow ─────────────────────

/**
 * How many chips draw before the overflow chip takes over. B18 §5.1.2: *"Square
 * service chips `E W S G B`, `+3` overflow chip"* — five letters, then one more
 * square. TC-ACC-4 says "never six chips wrapping", which is the property that
 * matters: this product sells TEN services (BR-RAT-024), so a wrapping chip cell
 * makes every row on the page taller for the one account that takes them all.
 */
export const SERVICE_CHIP_LIMIT = 5;

/**
 * BR-CUS-015's service cell, capped.
 *
 * ⚠ **THE SQUARES ARE `ratingShared.serviceBadge`'s, NOT A SECOND MAP.** The
 * letter for each of the ten services is ruled in exactly one place, and six of
 * the ten cannot be derived from the name (Sewer/Solar/Storm water all give
 * `S`). A second table here would be DEF-348's icon split with letters instead
 * of pencils. This file owns only the CAP, which is the one thing r10's own
 * three-service rows never had to express.
 *
 * ⚠ **AND IT DOES NOT REUSE `metering.ServiceTags`**, which is what this cell
 * used before: that component wraps, has no cap, and `features/metering/**`
 * belongs to another lane today. The two draw the same square from the same
 * badge map, so nothing about a service's colour or letter can disagree.
 *
 * ⚠ **AN EMPTY CELL ON A MASTER ACCOUNT NAMES THE ADDRESS — `DEF-CUS-6295`.**
 * `kind` is REQUIRED rather than optional on purpose: an optional prop nothing
 * passes is dead UI (hard-won law 2, `G13`), and this one has exactly one call
 * site to keep honest.
 *
 * A master account hangs off the ADDRESS (`BR-CUS-1010`) and takes its services
 * from it (`BR-CUS-1093`), so an empty cell on that row means *the building has
 * none recorded* and not *this account was set up wrong*. The Product Owner
 * read the first as the second and reported it as a defect, which cost an
 * investigation to answer. **A FACT, NOT AN EXPLANATION:** B14 rule 33 caps a
 * fact at six words and puts rationale at ZERO words on screen, so the cell
 * says where to look and never why the product works this way.
 */
export function AccountServiceChips(props: {
  services: readonly string[];
  /** `regular` | `master` — the server's own column (`BR-CUS-068`). */
  kind: string | null | undefined;
  /**
   * `DEF-CUS-6917` — open agreements the server could not resolve to a code,
   * and therefore left out of `services`. Defaults to none, because every
   * caller that has not been told the number has no business claiming zero.
   */
  unresolved?: number | null;
  t: Translator;
}) {
  const unresolved = Math.max(0, Math.trunc(props.unresolved ?? 0));
  if (props.services.length === 0 && unresolved === 0) {
    return (
      <Dash>
        {props.kind === ACCOUNT_KIND_MASTER
          ? props.t("customers.accounts.services.noneAtAddress")
          : props.t("customers.accounts.services.none")}
      </Dash>
    );
  }
  const shown = props.services.slice(0, SERVICE_CHIP_LIMIT);
  const hidden = props.services.slice(SERVICE_CHIP_LIMIT);
  const hiddenNames = hidden
    .map((code) => props.t(`rating.service.${code}`, { defaultValue: code }))
    .join(", ");
  return (
    // r10's own geometry: a 20px square per service (`w-5 h-5`) with a 2px gap
    // (`gap-0.5`). `flex-nowrap` is the cap's other half — with a limit of five
    // and no wrapping, this cell can never change a row's height.
    <span className="inline-flex flex-nowrap items-center gap-0.5">
      {shown.map((code) => {
        const badge = serviceBadge(code);
        const name = props.t(`rating.service.${code}`, { defaultValue: code });
        return (
          <span
            key={code}
            // The letter alone is not something a screen reader can announce, so
            // the full service name is the accessible name and the tooltip.
            title={name}
            aria-label={name}
            role="img"
            className="inline-flex h-5 w-5 items-center justify-center font-heading text-xs font-extrabold leading-none text-bg"
            style={{ background: `var(${badge.token})` }}
          >
            {badge.letter}
          </span>
        );
      })}
      {hidden.length > 0 && (
        <span
          // The overflow chip is NOT a service and must not look like one: no
          // service colour, the neutral pill tokens instead. Its accessible name
          // NAMES the hidden services, so nothing is lost to a reader who cannot
          // hover — the cap is a layout decision, never a data one.
          title={hiddenNames}
          aria-label={props.t("customers.accounts.services.more", {
            n: hidden.length,
            services: hiddenNames,
          })}
          role="img"
          className="inline-flex h-5 w-5 items-center justify-center bg-neutral-200 font-heading text-xs font-extrabold leading-none text-neutral-700"
        >
          {/* ⚠ NO CATALOGUE KEY FOR THE GLYPH, AND THAT IS DELIBERATE. `+3` is a
              plus sign and a numeral: it carries no word of any language, and a
              key holding `+{{n}}` is byte-identical in all eleven catalogues —
              which G15 reads, correctly, as eleven values left in English. The
              MEANING is in the accessible name above, which IS translated and
              names the hidden services. Same posture the shared table takes for
              its `↑` `↓` `✕` controls: the glyph is literal, the label is a key. */}
          {`+${hidden.length}`}
        </span>
      )}
      {unresolved > 0 && <UnresolvedServiceChip n={unresolved} t={props.t} />}
    </span>
  );
}

/**
 * `DEF-CUS-6917` — THE NUMBER BESIDE THE BLIND SPOT.
 *
 * The server drops an open service agreement it cannot resolve to a service
 * code, and until 2026-09-27 it dropped it in silence: the row rendered as a
 * correct row with fewer chips and nothing on any surface said a chip was
 * missing. CLAUDE.md hard-won law 7's fifth shape is exactly that — *a
 * declared blind spot with no number beside it is indistinguishable from an
 * empty one*. This chip is the number.
 *
 * **WHAT IT SAYS AND WHAT IT MUST NOT SAY (B14 rule 33).** The glyph is `?N`:
 * a question mark and a numeral, carrying no word of any language, for the
 * same reason the `+N` overflow chip above carries none — a key holding
 * `?{{n}}` would be byte-identical in eleven catalogues and G15 reads that,
 * correctly, as eleven values left in English. The accessible name is a FACT
 * of four words and is translated. **WHY it happened is ZERO WORDS on screen**
 * — that is rationale, it belongs in this docstring and in the WARNING line
 * `selectors._report_service_chip_drops` writes, and a cell that explained the
 * cause would break rule 33 while trying to obey law 7.
 *
 * **IT IS NOT A SERVICE AND MUST NOT LOOK LIKE ONE**, so it takes no service
 * colour — the warning tokens instead, which is also what separates it at a
 * glance from the neutral `+N` chip standing beside it.
 */
function UnresolvedServiceChip(props: { n: number; t: Translator }) {
  const label = props.t("customers.accounts.services.unresolved", { n: props.n });
  return (
    <span
      title={label}
      aria-label={label}
      role="img"
      data-testid="account-services-unresolved"
      className="inline-flex h-5 w-5 items-center justify-center bg-warning-100 font-heading text-xs font-extrabold leading-none text-warning-700"
    >
      {`?${props.n}`}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030/B18@2026-08-23 §5.1.2 (S17) · US-CUS-001 · BR-CUS-015/016/048 · W2 tasks 2.3 + 2.6
// generated: 2026-08-24 by the CR-030 W2 frontend lane
// checklist: A✔ B✔ C✔ D=deferred(no API call — display components) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (AccountsPage.test.tsx TC-ACC-2/TC-ACC-4 + the TC-UI cases) · g31 (registered in styles/route-b-migrated.txt, so routeBUtilities.test.ts and the real Tailwind compiler own every utility here) · g38 (no stated absence in this file) · g40 (mounted by AccountsListPage.tsx)
// exceptions: E3 the four `ageing_*` keys are typed HERE rather than on `AccountRow` in `src/api/endpoints.ts` — that file belongs to another lane this session. The intersection type is assignable from `AccountRow`, so nothing casts; REPORTED as owed to endpoints.ts · E3 **r10 draws THREE ageing labels (`Current` · `30d past` · `60+ past`) and the server serves FOUR bands** (BR-CUS-048: current · 31–60 · 61–90 · 90+). The four are rendered, because collapsing 61–90 and 90+ into one label would make the cell disagree with the `?ageing=` filter, which has four values and no collapsed one — a chip that cannot express what the column shows. REPORTED as a divergence from `[shot]` · E3 `current` renders in the NEUTRAL tone rather than success-green: it is the ordinary state, and green beside a `Marked disconnect` status pill in the next column reads as two conflicting claims · E4 the exact `ageing_days_past_due` rides on the tooltip rather than in the cell — B18 §5.1.2 draws a band, not a number of days · E4 `SERVICE_CHIP_LIMIT` is 5 per B18 §5.1.2's `E W S G B` + `+3`; TC-ACC-4's own arithmetic says "6 services → five chips and a `+3` overflow", which does not add up (6 − 5 = 1). The remainder is what renders, so eight services give `+3` — which is where the shot's `+3` comes from. REPORTED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
