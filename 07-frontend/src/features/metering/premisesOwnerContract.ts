// ── Trace ──────────────────────────────────────────────
// Change:  CR-130-BRC07 part three, lane C2 — the three premises owner screens.
// Defect:  DEF-MET-6155 — all three read `premises_owners`, a table no screen
//          can fill, so none of them creates or finds anything.
// Ruling:  PO 2026-09-22, verbatim: *"why you are point is at owner id - why not
//          directly at master accoutn Id - it will solev the problem … owner IDs
//          are not required hence no screens or fucntionality for it"*, and, on
//          the three consequences put back to them: *"yes - im okay with this"*.
//          Decision log 2026-09-22, "A PREMISES NAMES ITS MASTER ACCOUNT
//          DIRECTLY". It is `OQ-790`'s own ruling — closed 2026-08-27 on option
//          (c), MASTER IMMEDIATELY — finally built.
// Rules:   BR-MET-112 (nothing is written until the last button) · BR-CUS-068
//          (`kind` is a REFUSED input on every account door but one, which is
//          why no screen asks master-or-regular) · B14 rule 31 (no database id
//          is ever a visible value)
// ───────────────────────────────────────────────────────
/**
 * **THE ONE PLACE THE WIRE IS NAMED, AND THAT IS THE WHOLE POINT OF THE FILE.**
 *
 * Lane C1 owns the column, the seam functions and the five verdicts; this lane
 * owns the three screens. The two were built in parallel, so every read of the
 * server's shape goes through the functions below and **a name C1 spells
 * differently is one edit here rather than nine across three screens.**
 *
 * ⚠ **THIS IS NOT A SECOND CONTRACT AND MUST NOT BECOME ONE.** Nothing here
 * invents a field: each reader takes the server's row as `unknown`, looks for
 * the key it expects, and **returns `null` when it is absent** rather than
 * defaulting to something that reads like an answer. An absence is drawn as an
 * absence on every screen below it (`CR-089-p036`'s own rule, and hard-won law
 * 2's mirror — a screen that renders a default over a missing fact states
 * something the server never said).
 */
import type { AccountRow, PremisesRow } from "@/api/endpoints";

/**
 * The owner, as a clerk sees it: a name and an account number.
 *
 * ⚠ **`id` IS HERE AND IS NEVER RENDERED (B14 rule 31).** It travels in an
 * `href` and in a write payload, and the visible value is `account_no`. The
 * account-header line that returned null for ever (`DEF-CUS-3653`) is what a
 * rule like this costs when it is applied to the wrong field, so the split is
 * made explicit in the type rather than left to each caller's discipline.
 */
export interface OwnerAccount {
  id: string;
  /** What a clerk reads and quotes down the phone. May be absent on a row the
   *  numbering series has not reached; drawn as an absence, never as "—" with
   *  an id behind it. */
  account_no: string | null;
  name: string | null;
  /** How many OTHER properties this account owns. The blueprint draws this line
   *  (`Already owns 3 properties · …`) and the server does not serve it yet —
   *  C1's `premises_ids_owned_by_account` is where it will come from. `null`
   *  means NOT ASKED and the line is not drawn at all; it is never rendered as
   *  zero, because *"already owns 0"* says the opposite of what it means. */
  owns_count: number | null;
  /**
   * What the books say, when the row that carried this account carried it.
   *
   * ⚠ **`null` HERE MEANS *THE BOOKS COULD NOT BE ASKED*, WHICH IS NOT
   * `0.00`** — a screen rendering zero for it prints something
   * indistinguishable from a settled account (`DEF-127`/`DEF-176`). Callers use
   * `isAmountAbsent`, never `=== null`, which is a different question and once
   * took a whole route down. Absent on a search result, because
   * `GET /accounts` serves it and the SEARCH does not need it.
   */
  balance?: string | null;
  currency?: string | null;
  /**
   * **WHICH DECLARATION THIS ACCOUNT CAME FROM** — `premises.master_account_id`
   * or the pre-ruling `premises_owners.master_account_id`. Served by C1 as
   * `master_account_source`.
   *
   * ⚠ **TWO COLUMNS CAN ANSWER ONE QUESTION AND THE RULING PUTS THEM IN ORDER,
   * SO A SCREEN SHOWING AN ACCOUNT MUST BE ABLE TO SAY WHICH ONE IT READ** —
   * the same reason `BR-MET-1162` makes every screen showing a map point say
   * whether it is the unit's own or the building's. `null` is *not stated*, and
   * a screen may not guess `premises` from silence.
   */
  source?: OwnerAccountSource | null;
}

/** Where a premises' master account was declared. C1's `master_account_source`. */
export type OwnerAccountSource = "premises" | "owner_record";

/** An account row from `GET /accounts`, as the owner of a property. */
export function ownerAccountFromRow(row: AccountRow): OwnerAccount {
  return {
    id: row.id,
    account_no: row.account_no,
    name: row.name,
    owns_count: readOwnsCount(row),
    balance: row.balance,
    currency: row.currency,
  };
}

/**
 * The master account a premises NAMES, read off the premises row.
 *
 * ⚠ **THREE SPELLINGS ARE ACCEPTED AND THAT IS DELIBERATE, NOT SLOPPY.** This
 * lane and C1 were building at the same time; the expanded account may arrive
 * as `master_account`, or as `owner_account`, and the pre-ruling rows still
 * carry it under `owner.master_account` (decision log 2026-09-22 declares that
 * precedence: `premises.master_account_id` wins, then
 * `premises_owners.master_account_id`, and `accounts.premises_id` is NEVER
 * promoted to answer this question because it answers a different one).
 *
 * **The precedence here is that ruling's, in its order**, so a row that answers
 * twice cannot make a screen disagree with the money path.
 */
export function premisesOwnerAccount(premises: PremisesRow | null): OwnerAccount | null {
  if (premises === null || premises === undefined) return null;
  const row = premises as unknown as Record<string, unknown>;
  // ⚠ **THE SERVER'S OWN WORD WINS OVER THE BRANCH THIS FUNCTION TOOK.** C1
  // serves `master_account_source`; deriving it from which key held the account
  // would be a second answer to a question the wire already answers, and the
  // two could disagree on a row that carries both.
  const stated = row.master_account_source;
  const said: OwnerAccountSource | undefined =
    stated === "premises" || stated === "owner_record" ? stated : undefined;
  // 1 · the declaration — `premises.master_account_id`, expanded.
  const declared =
    asAccountish(row.master_account, said ?? "premises") ??
    asAccountish(row.owner_account, said ?? "premises");
  if (declared !== null) return declared;
  // 2 · the pre-ruling declaration, for rows that predate this.
  const owner = row.owner as Record<string, unknown> | null | undefined;
  const inherited = owner ? asAccountish(owner.master_account, said ?? "owner_record") : null;
  if (inherited !== null) return inherited;
  // 3 · **THE NUMBER AND THE NAME, WHICH IS WHAT THE LIST GETS.** C1 serves
  //     `master_account_no` flat on every row through a batched seam that
  //     resolves the whole page in ONE query — the opposite of `DEF-324`, where
  //     the cost was 304 calls answering one question — while the full
  //     expansion stays off the list and `master_account_expanded: false` says
  //     so. ⚠ **IT CARRIES NO `id`, SO IT IS NOT A LINK**, and this is the one
  //     place an `OwnerAccount` legitimately has none: `OwnerAccountNumber`
  //     degrades to the plain number rather than to `/accounts/undefined`.
  //
  //     ⚠ **`name` WAS HARDCODED `null` HERE UNTIL 2026-09-23, AND THAT WAS
  //     `DEF-MET-6304`.** The Owner cell falls back to *"No name recorded"*
  //     when this is null, so every row with a real, named owner read **"No
  //     name recorded · AC-2026-00051"** — a sentence that states something
  //     about the ACCOUNT which is false. The name was recorded; the LIST had
  //     never asked for it, and the detail screen beside it showed it
  //     correctly the whole time. It was not this file's error alone: the
  //     server served no name to read, so `null` was the honest answer to a
  //     question nobody had put. **Both halves moved in one commit** —
  //     `customers.selectors.master_account_numbers` now carries the name for
  //     the whole page beside the number, status and kind it already carried,
  //     and `metering.selectors._premises_master_account_cells` serves it flat
  //     as `master_account_name`.
  //
  //     ⛔ **`null` IS STILL A REAL ANSWER, WHICH IS WHY THIS READS THE
  //     SERVER'S KEY AND FALLS BACK TO NOTHING.** An account with nobody named
  //     answers null and the cell still says *"No name recorded"* — now TRUE,
  //     because the list asked. The premises' free-text `owner_manager` sits
  //     on this very row and must NOT be borrowed for it: `BR-MET-151` clause
  //     3 forbids deriving a fact about a real party from a typed string, and
  //     that string is the OWNER's, which is not always the ACCOUNT's.
  const flatNo = row.master_account_no;
  const flatId = row.master_account_id;
  const flatName = row.master_account_name;
  if (typeof flatNo === "string" && flatNo !== "") {
    return {
      id: typeof flatId === "string" ? flatId : "",
      account_no: flatNo,
      // `null`, never `undefined`: the type says `string | null`, a row from a
      // server that predates the wire carries no key at all, and an empty
      // string is an absence wearing the costume of a name.
      name: typeof flatName === "string" && flatName !== "" ? flatName : null,
      owns_count: null,
      source: said ?? null,
    };
  }
  // 4 · there is no fourth. `accounts.premises_id` says WHICH PREMISES AN
  //     ACCOUNT COVERS, never WHO OWNS THIS PREMISES, and `BR-MET-400` retired
  //     the hallway inference exactly so it could not come back by a side door.
  return null;
}

/**
 * **WAS THE ACCOUNT ASKED FOR AT ALL?** C1 serves `master_account_expanded` and
 * it is `false` on the LIST, where the full expansion is deliberately off.
 *
 * ⚠ **NOT ASKED IS NOT NO ACCOUNT, AND A BLANK CELL MUST READ AS THE FIRST.**
 * `DEF-324` measured the alternative — 304 calls answering one question — so
 * the list serves the NUMBER through a batched seam and nothing else. A screen
 * that drew *no owner* off an unexpanded row would state something the server
 * never said, which is the same fault as rendering `0.00` for a balance that
 * could not be read.
 */
export function ownerAccountAsked(premises: PremisesRow | null): boolean {
  if (premises === null || premises === undefined) return false;
  const value = (premises as unknown as Record<string, unknown>).master_account_expanded;
  // Absent means the row predates the flag, and those rows DO carry the account.
  return value === undefined ? true : value !== false;
}

/** What the write doors are sent to attach an account. One shape, both doors. */
export function ownerAccountPayload(accountId: string | null): Record<string, unknown> {
  return { master_account_id: accountId };
}

/**
 * ⚠ **A VERDICT CODE CONTAINS THE WORD FOR ITS OWN OPPOSITE, AND THAT ALREADY
 * COST A FALSE PASS.** The first draft of this lane's walkthrough asked
 * `/created/.test(...)` of the verdict and reported the BROKEN screen as FIXED,
 * because `owner_account_not_created` matches it. CLAUDE.md hard-won law 7,
 * habit 2 — ask what would make a check pass WRONGLY. **Every comparison in
 * this file is against a WHOLE constant**, never a substring, and the constants
 * are declared here so no screen spells one by hand.
 */
export const OWNER_ACCOUNT_CREATED = "owner_account_created";
export const OWNER_ACCOUNT_NOT_CREATED = "owner_account_not_created";
/** The clerk PICKED an account that already existed, so it was linked rather
 *  than opened. C1's ninth code, and the common case on a landlord's second
 *  address. */
export const OWNER_ACCOUNT_ATTACHED = "owner_account_attached";

/**
 * ⚠ **THE FAMILY IS MATCHED BY ITS PREFIX, AND THE ASYMMETRY IS DELIBERATE.**
 * This reader first accepted two codes by name and **silently dropped
 * `owner_account_attached`** — the verdict a clerk gets every time they pick an
 * account that already exists, which is the commonest case of all. Measured in a
 * browser on 2026-09-22 against C1's landed backend: the account WAS linked, the
 * server said so, and the screen said nothing. **That is the original defect
 * reappearing one layer up**, and an enumerated list is what caused it.
 *
 * So the rule is: **anything the server namespaces into this family gets
 * rendered.** Dropping a verdict is SILENT and is the bug; rendering a sibling
 * this lane has not met is safe, because the SENTENCE comes from the server's
 * own `message_key` and this lane writes none of them.
 *
 * ⚠ **THIS IS A PREFIX ON A NAMESPACE, NOT A SUBSTRING ON A WORD.** The false
 * pass this lane already paid for was `/created/` matching
 * `owner_account_not_created` — a word appearing INSIDE another word. A
 * `startsWith` on `owner_account_` cannot do that, and the two codes whose
 * meanings are opposite are still compared WHOLE everywhere it matters.
 */
const OWNER_ACCOUNT_FAMILY = "owner_account_";

/**
 * The reasons, in the server's own words (`apps/metering/services.py`).
 *
 * ⚠ **`no_typed_owner` IS RENAMED `owner_not_named` BY THE 2026-09-22 RULING
 * (lane C1), BECAUSE THERE IS NO TYPED OWNER IN THE CHAIN ANY MORE.** The old
 * spelling is kept beside it and still matched: a tenant's in-flight response,
 * a replayed fixture and every row the browser walk captured before the rename
 * carry it, and a screen that stopped recognising it would go silent on exactly
 * the verdict the PO reported. One fact, two spellings, both understood; only
 * the new one is produced.
 */
export const OWNER_ACCOUNT_REASONS = {
  /** The premises named nobody, so there was nobody to open an account for. */
  notNamed: "owner_not_named",
  /** @deprecated the pre-2026-09-22 spelling of `notNamed`. Still matched. */
  notNamedLegacy: "no_typed_owner",
  /** No account type, which is the consumer category the bill is priced by. */
  noAccountType: "no_account_type",
  /** The account door was walked through and it refused, in its own words. */
  refused: "refused",
  /** The owner already held an account, so nothing was created. */
  alreadyLinked: "owner_account_already_linked",
} as const;

export interface OwnerAccountVerdict {
  code: string;
  reason: string | null;
  /**
   * **THE SENTENCE A CLERK READS, AND THIS LANE DOES NOT WRITE IT.**
   *
   * ⛔ C1 serves a `message_key` on every entry — eight outcomes, one wording
   * each — and **the eleven catalogue rows land in C1's commit, not this one.**
   * A second wording here would be two sentences for one fact, which is the
   * whole complaint this CR is answering. `G32` is a ratchet at zero and goes
   * red the moment a raised key resolves to nothing, so the sentences travel
   * with the server change or the gate says so.
   */
  message_key: string | null;
  /** Interpolation for that sentence — the account NUMBER among them. */
  params: Record<string, unknown>;
}

/**
 * The verdicts a create or an update carried back.
 *
 * ⛔ **THIS IS THE DEFECT'S OTHER HALF AND IT IS THE HALF THE PO ACTUALLY
 * FELT.** Measured in a browser on 2026-09-22, real PostgreSQL: `POST /premises`
 * returns **HTTP 201** carrying
 * `[{"code":"owner_account_not_created","reason":"no_typed_owner"}]`, and the
 * wizard fired one toast — *"Premise created"* — and dropped the array.
 * **So it is not an error nobody surfaced; it is a SUCCESS NOBODY QUALIFIED**,
 * which is exactly why the report reads *"it does not create the master account
 * and also not linking that account to premsies - why"*. The server has always
 * said why. Nothing rendered it: a whole front-end grep for these strings found
 * zero occurrences outside the import receipt.
 */
export function ownerAccountVerdicts(created: unknown): OwnerAccountVerdict[] {
  const row = created as Record<string, unknown> | null | undefined;
  if (!row) return [];
  const raw = row.warnings ?? row.owner_account_warnings;
  if (!Array.isArray(raw)) return [];
  const out: OwnerAccountVerdict[] = [];
  for (const entry of raw) {
    if (entry === null || typeof entry !== "object") continue;
    const w = entry as Record<string, unknown>;
    const code = typeof w.code === "string" ? w.code : null;
    // Only the owner-account family. A create may carry other warnings — a GIS
    // flag, a city refusal — and this reader must not claim them.
    if (code === null || !code.startsWith(OWNER_ACCOUNT_FAMILY)) continue;
    const params: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(w)) {
      // `code` and `message_key` are the envelope; everything else the server
      // put on the entry is interpolation for its own sentence — which is how
      // `account_no` reaches the screen without this lane naming it.
      if (key === "code" || key === "message_key") continue;
      // ⛔ **NO DATABASE ID REACHES A SENTENCE, AND THIS IS WHERE THAT IS
      // ENFORCED (B14 rule 31).** C1's `owner_account_attached` really does
      // carry `account_id` beside `account_no`, correctly — the backend needs
      // it. **A screen does not.** Rule 31 says the NUMBER is the visible value
      // and the id travels in an href; a toast has no href, so the id has no
      // business in one *"even transiently"*. Stripped at the boundary rather
      // than trusted to every caller, because a caller that forgets renders a
      // UUID at a clerk and nothing goes red.
      if (key === "id" || key.endsWith("_id")) continue;
      if (value !== null && value !== undefined) params[key] = value;
    }
    out.push({
      code,
      reason: typeof w.reason === "string" ? w.reason : null,
      message_key: typeof w.message_key === "string" && w.message_key !== "" ? w.message_key : null,
      params,
    });
  }
  return out;
}

/** Did an account actually open? A whole-constant comparison, never a substring. */
export function ownerAccountOpened(verdicts: OwnerAccountVerdict[]): boolean {
  return verdicts.some((v) => v.code === OWNER_ACCOUNT_CREATED);
}

/** Did the server say the premises named nobody? Both spellings of the reason. */
export function ownerNotNamed(verdicts: OwnerAccountVerdict[]): boolean {
  return verdicts.some(
    (v) =>
      v.reason === OWNER_ACCOUNT_REASONS.notNamed ||
      v.reason === OWNER_ACCOUNT_REASONS.notNamedLegacy,
  );
}

/**
 * The verdict sentences, ready to render — the server's own `message_key` and
 * its own params, in order.
 *
 * ⚠ **AN ENTRY WITH NO `message_key` IS SKIPPED RATHER THAN GIVEN A SENTENCE
 * THIS LANE INVENTED.** C1's contract puts one on every entry; if one ever
 * arrives without, the honest outcome is that the OTHER facts still reach the
 * clerk — the premise number always does — rather than a made-up line that
 * disagrees with the eight wordings. `cr130_c2_premises_owner_walkthrough.mjs`
 * asserts against the LIVE server that every verdict it sees carries one, so a
 * contract that slips goes red in a walk instead of going silent on a screen.
 */
export function verdictSentences(
  verdicts: OwnerAccountVerdict[],
  t: (key: string, params?: Record<string, unknown>) => string,
): string[] {
  const out: string[] = [];
  for (const verdict of verdicts) {
    if (verdict.message_key === null) continue;
    out.push(t(verdict.message_key, verdict.params));
  }
  return out;
}

// ── the two private readers ────────────────────────────────────────────────

/** A count that is a real number, or `null` for NOT ASKED. Never zero-by-default. */
function readOwnsCount(row: unknown): number | null {
  const r = row as Record<string, unknown> | null | undefined;
  if (!r) return null;
  for (const key of ["owns_premises_count", "premises_count", "owned_premises"]) {
    const value = r[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

/**
 * An account-shaped value, or `null`.
 *
 * ⚠ **AN OBJECT WITHOUT AN `id` IS NOT AN ACCOUNT.** A summary shape carrying
 * only a number would otherwise become `<Link to="/accounts/undefined">` — a
 * control that looks live, is routed, and lands on nothing (`OwnerAccount.tsx`
 * already learned this once). Here it is refused at the door instead.
 */
function asAccountish(value: unknown, source?: OwnerAccountSource): OwnerAccount | null {
  if (value === null || value === undefined || typeof value !== "object") return null;
  const v = value as Record<string, unknown>;
  if (typeof v.id !== "string" || v.id === "") return null;
  return {
    id: v.id,
    account_no: typeof v.account_no === "string" ? v.account_no : null,
    name: typeof v.name === "string" ? v.name : null,
    owns_count: readOwnsCount(v),
    balance: typeof v.balance === "string" ? v.balance : null,
    currency: typeof v.currency === "string" ? v.currency : null,
    source: source ?? null,
  };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-130-BRC07 §9 part three — 12-governance/change-requests/
//         CR-130-BRC07-percent-basis-unit-scope-and-the-owners-master-account.md
// generated: 2026-09-22 by the CR-130-BRC07 lane C2
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// exceptions:
//   E3 this file declares no class and renders nothing, so B14 rule 21 does not
//      reach it and it is not on the Route B ledger.
//   E3 `premisesOwnerAccount` accepts three spellings of one fact. That is a
//      PARALLEL-LANE accommodation with a stated end: once C1's wire is on the
//      branch, the spellings this lane guessed are deleted and the one the
//      server sends is kept. Recorded so the next lane removes them rather than
//      inheriting them as a contract.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
