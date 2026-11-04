// ── Trace ──────────────────────────────────────────────
// Change:  CR-130-BRC07 part three, lane C2 — the one place the wire is named.
// Defect:  DEF-MET-6155 — the server said what it did with the owner's account
//          on every create, and nothing rendered it.
// Rules:   CLAUDE.md hard-won law 7 habit 2 — ask what would make this check
//          pass WRONGLY · B14 rule 31 (no database id is a visible value)
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import type { PremisesRow } from "@/api/endpoints";
import {
  OWNER_ACCOUNT_CREATED,
  OWNER_ACCOUNT_NOT_CREATED,
  OWNER_ACCOUNT_REASONS,
  ownerAccountAsked,
  ownerAccountOpened,
  ownerAccountPayload,
  ownerAccountVerdicts,
  ownerNotNamed,
  premisesOwnerAccount,
  verdictSentences,
} from "@/features/metering/premisesOwnerContract";

const ACCOUNT = {
  id: "01a0c23c-bd23-7f85-a7d5-b55bace9a4f3",
  account_no: "AC-2026-00051",
  name: "Ridge Property LLC",
};
const OTHER = { id: "other-id", account_no: "AC-2026-00099", name: "Whitfield Rentals LLC" };

/** A premises row is 30-odd fields; these tests only ever touch the owner ones. */
const row = (extra: Record<string, unknown>) => extra as unknown as PremisesRow;

describe("premisesOwnerAccount — the ruling's declared precedence", () => {
  it("reads `premises.master_account` — the declaration, which wins", () => {
    const account = premisesOwnerAccount(
      row({ master_account: ACCOUNT, owner: { master_account: OTHER } }),
    );
    expect(account?.account_no).toBe("AC-2026-00051");
  });

  it("falls back to the owner record's account for rows that predate the ruling", () => {
    const account = premisesOwnerAccount(row({ owner: { master_account: OTHER } }));
    expect(account?.account_no).toBe("AC-2026-00099");
    expect(account?.source).toBe("owner_record");
  });

  it("takes the SERVER's word for the source, not the branch it happened to take", () => {
    // Two columns can answer and the ruling puts them in order; deriving the
    // source from which key held the account would be a second answer to a
    // question the wire already answers, and on a row carrying both they could
    // disagree.
    const account = premisesOwnerAccount(
      row({ master_account: ACCOUNT, master_account_source: "owner_record" }),
    );
    expect(account?.source).toBe("owner_record");
  });

  it("NEVER promotes `accounts.premises_id` to answer this question", () => {
    // `BR-MET-400` retired the hallway inference. *Which premises an account
    // covers* is a different question from *who owns this premises*, and a
    // screen that answered the second with the first would disagree with the
    // money path.
    expect(premisesOwnerAccount(row({ premises_id: "p1", accounts: [ACCOUNT] }))).toBeNull();
  });

  it("returns null for an owner record with no account — an absence, not a guess", () => {
    expect(premisesOwnerAccount(row({ owner: { id: "o1", master_account: null } }))).toBeNull();
  });

  it("reads the flat `master_account_no` the LIST gets, with no id and no link", () => {
    // C1's batched seam resolves the whole page in one query and leaves the
    // expansion off. A number with no id is a real state, and the number is
    // still what a clerk reads (B14 rule 31).
    const account = premisesOwnerAccount(
      row({ master_account_no: "AC-2026-00051", master_account_expanded: false }),
    );
    expect(account?.account_no).toBe("AC-2026-00051");
    expect(account?.id).toBe("");
  });

  // ── `DEF-MET-6304` — THE FLAT ROW CAN NAME ITS OWNER ────────────────────
  //
  // ⛔ **RED BEFORE THE FIX**, because case 3 hardcoded `name: null`:
  //     AssertionError: expected null to be 'Ridge Property LLC'
  //
  // The Owner cell read *"No name recorded · AC-2026-00051"* beside a real,
  // named company — a sentence stating something about the ACCOUNT that was
  // false. The name IS recorded; the list never asked for it. The batched
  // seam now carries it for the whole page beside the number it already
  // carried, so case 3 reads it instead of declaring it absent.
  it("reads the flat `master_account_name` the LIST now gets (DEF-MET-6304)", () => {
    const account = premisesOwnerAccount(
      row({
        master_account_no: "AC-2026-00051",
        master_account_name: "Ridge Property LLC",
        master_account_expanded: false,
      }),
    );
    expect(account?.name).toBe("Ridge Property LLC");
    expect(account?.account_no).toBe("AC-2026-00051");
    // ⚠ Still no id, so still not a link — the list does not expand the
    // account, and `/accounts/undefined` is the control this file already
    // learned to refuse.
    expect(account?.id).toBe("");
  });

  it("keeps an honest absence honest — no name served is still `null`", () => {
    // ⚠ **THE MIRROR CASE, AND IT MUST NOT BE 'FIXED'.** An account with
    // nobody named answers `null`, the cell says *"No name recorded"*, and
    // that sentence is now TRUE because the list asked. Substituting the
    // premises' free-text `owner_manager` would be a name this product
    // invented about a real party — `BR-MET-151` clause 3 forbids exactly
    // that, and a seeder has already been failed for one.
    const account = premisesOwnerAccount(
      row({
        master_account_no: "AC-2026-00051",
        master_account_name: null,
        owner_manager: "Whitfield Rentals LLC",
        master_account_expanded: false,
      }),
    );
    expect(account?.name).toBeNull();
    expect(account?.account_no).toBe("AC-2026-00051");
  });

  it("answers `null`, never `undefined`, on a row carrying no name key at all", () => {
    // A row from a server that predates the wire carries no key. `null` keeps
    // the old sentence — the same behaviour as before this change — where
    // `undefined` would reach `??` identically today and a `||` tomorrow
    // differently. The type says `string | null`, so the value must be one.
    const account = premisesOwnerAccount(
      row({ master_account_no: "AC-2026-00051", master_account_expanded: false }),
    );
    expect(account?.name).toBeNull();
  });

  it("refuses an account-shaped value with no id, rather than linking to nothing", () => {
    // A summary shape carrying only a number would become
    // `<Link to="/accounts/undefined">` — a control that looks live, is routed,
    // and lands on nothing.
    expect(premisesOwnerAccount(row({ master_account: { account_no: "AC-1" } }))).toBeNull();
  });
});

describe("ownerAccountAsked — NOT ASKED is not NO ACCOUNT", () => {
  it("is false where the server said it did not expand", () => {
    expect(ownerAccountAsked(row({ master_account_expanded: false }))).toBe(false);
  });
  it("is true where it did", () => {
    expect(ownerAccountAsked(row({ master_account_expanded: true }))).toBe(true);
  });
  it("is true on a row that predates the flag — those rows DO carry the account", () => {
    expect(ownerAccountAsked(row({}))).toBe(true);
  });
});

describe("ownerAccountPayload — one spelling, both doors", () => {
  it("names `master_account_id` and nothing else", () => {
    expect(ownerAccountPayload(ACCOUNT.id)).toEqual({ master_account_id: ACCOUNT.id });
  });
  it("carries null to clear it — a clerk may un-name an owner", () => {
    expect(ownerAccountPayload(null)).toEqual({ master_account_id: null });
  });
});

describe("ownerAccountVerdicts — the answer the wizard threw away", () => {
  it("reads the array off a 201 response", () => {
    // ⛔ THE REAL BODY, captured from a browser on 2026-09-22 against real
    // PostgreSQL. **HTTP 201.** Nothing failed; the half of the act that did
    // not happen was simply never mentioned.
    const verdicts = ownerAccountVerdicts({
      id: "p1",
      premise_no: "P-00081",
      warnings: [{ code: "owner_account_not_created", reason: "no_typed_owner" }],
    });
    expect(verdicts).toHaveLength(1);
    expect(verdicts[0].code).toBe(OWNER_ACCOUNT_NOT_CREATED);
    expect(verdicts[0].reason).toBe("no_typed_owner");
  });

  it("⛔ does NOT read `not_created` as `created` — the false pass this already cost", () => {
    // CLAUDE.md hard-won law 7, habit 2. The first draft of this lane's
    // walkthrough asked `/created/.test(...)` and reported the BROKEN screen as
    // FIXED, because `owner_account_not_created` matches it. Every comparison
    // is against a WHOLE constant.
    const verdicts = ownerAccountVerdicts({
      warnings: [{ code: "owner_account_not_created", reason: "owner_not_named" }],
    });
    expect(ownerAccountOpened(verdicts)).toBe(false);
  });

  it("reports an account that DID open", () => {
    const verdicts = ownerAccountVerdicts({
      warnings: [
        { code: OWNER_ACCOUNT_CREATED, message_key: "m.opened", account_no: "AC-2026-00058" },
      ],
    });
    expect(ownerAccountOpened(verdicts)).toBe(true);
  });

  it("understands BOTH spellings of *nobody was named*", () => {
    // C1 renamed `no_typed_owner` to `owner_not_named`. A screen that stopped
    // recognising the old one would go silent on exactly the verdict the PO
    // reported, on every in-flight response and every replayed fixture.
    for (const reason of [OWNER_ACCOUNT_REASONS.notNamed, OWNER_ACCOUNT_REASONS.notNamedLegacy]) {
      const verdicts = ownerAccountVerdicts({
        warnings: [{ code: OWNER_ACCOUNT_NOT_CREATED, reason }],
      });
      expect(ownerNotNamed(verdicts)).toBe(true);
    }
  });

  it("⛔ renders `owner_account_attached` — the code an enumerated list DROPPED", () => {
    // This reader accepted two codes by name and silently dropped the third,
    // which is the verdict a clerk gets every time they pick an account that
    // already exists — the commonest case of all. Measured in a browser against
    // C1's landed backend: the account WAS linked and the screen said nothing.
    // The original defect, reappearing one layer up.
    const verdicts = ownerAccountVerdicts({
      warnings: [
        {
          code: "owner_account_attached",
          message_key: "metering.premises.ownerAccount.attached",
          account_id: "01a0c23c-fc54-7111-9eba-f971601c582d",
          account_no: "AC-2026-00051",
        },
      ],
    });
    expect(verdicts).toHaveLength(1);
    expect(verdictSentences(verdicts, (k) => k)).toEqual([
      "metering.premises.ownerAccount.attached",
    ]);
  });

  it("⛔ STRIPS `account_id` out of the params — rule 31 at the boundary", () => {
    // C1's warning really does carry `account_id` beside `account_no`,
    // correctly; a SCREEN does not. A toast has no href, so an id has no
    // business in one even transiently.
    const verdicts = ownerAccountVerdicts({
      warnings: [
        {
          code: "owner_account_attached",
          message_key: "m.attached",
          account_id: "01a0c23c-fc54-7111-9eba-f971601c582d",
          account_no: "AC-2026-00051",
        },
      ],
    });
    expect(verdicts[0].params).toEqual({ account_no: "AC-2026-00051" });
    expect(JSON.stringify(verdicts[0].params)).not.toContain("01a0c23c");
  });

  it("ignores warnings that are not about the owner's account", () => {
    const verdicts = ownerAccountVerdicts({
      warnings: [{ code: "gis_unchecked", reason: "city_unreachable" }],
    });
    expect(verdicts).toHaveLength(0);
  });

  it("survives a response with no warnings key at all", () => {
    expect(ownerAccountVerdicts({ id: "p1" })).toEqual([]);
    expect(ownerAccountVerdicts(null)).toEqual([]);
  });
});

describe("verdictSentences — the SERVER's wording, never this lane's", () => {
  it("renders the entry's own message_key with the entry's own params", () => {
    const seen: Array<[string, Record<string, unknown> | undefined]> = [];
    const t = (key: string, params?: Record<string, unknown>) => {
      seen.push([key, params]);
      return `<${key}>`;
    };
    const verdicts = ownerAccountVerdicts({
      warnings: [
        {
          code: OWNER_ACCOUNT_CREATED,
          reason: null,
          message_key: "metering.premises.owner.verdict.opened",
          account_no: "AC-2026-00058",
        },
      ],
    });
    expect(verdictSentences(verdicts, t)).toEqual(["<metering.premises.owner.verdict.opened>"]);
    // The account NUMBER reaches the sentence without this lane naming it —
    // every field on the entry becomes interpolation.
    expect(seen[0][1]).toMatchObject({ account_no: "AC-2026-00058" });
  });

  it("⛔ never carries an id into a sentence, even when the server sends one", () => {
    // B14 rule 31 is signed: no database id is ever the visible value of a
    // field. `account_no` is what a person reads; an id travels in an href.
    const verdicts = ownerAccountVerdicts({
      warnings: [
        {
          code: OWNER_ACCOUNT_CREATED,
          message_key: "m.opened",
          account_no: "AC-2026-00058",
        },
      ],
    });
    expect(Object.keys(verdicts[0].params)).not.toContain("id");
    expect(Object.keys(verdicts[0].params)).not.toContain("account_id");
  });

  it("skips an entry with no message_key rather than inventing a sentence", () => {
    // C1's contract puts one on every entry. If one ever arrives without, the
    // honest outcome is that the OTHER facts still reach the clerk — the
    // premise number always does — rather than a made-up line that disagrees
    // with the eight wordings. The browser walk asserts against the LIVE server
    // that every verdict carries one, so a slipped contract goes red there.
    const verdicts = ownerAccountVerdicts({
      warnings: [{ code: OWNER_ACCOUNT_NOT_CREATED, reason: "refused" }],
    });
    expect(verdictSentences(verdicts, (k) => k)).toEqual([]);
  });
});
