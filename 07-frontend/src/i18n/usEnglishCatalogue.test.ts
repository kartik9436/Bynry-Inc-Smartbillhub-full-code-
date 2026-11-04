// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-SHL-6351 (the English catalogue was British English)
// Rules:    B14 rule 35 (a catalogue is written in the language its users speak) ·
//           BR-SHL-030 (adding a language is DATA, never code)
// ───────────────────────────────────────────────────────
// `en.json` IS AMERICAN ENGLISH, BECAUSE THE PEOPLE READING IT ARE AMERICAN.
//
// The product sells to North American utilities, and the first one live is in
// Iowa. The PO, looking at a fee-method dropdown that read *Card · Cash ·
// Cheque · Waive the fee*, 2026-09-23: *"cheque should american english
// check"*. The catalogue had been written in British spelling from its first
// lane, and no check read a VALUE for spelling: G15 compares key sets and G33
// counts words. This suite is that check.
//
// ⚠ IT READS VALUES, NEVER KEYS. A key such as `settings.centres.title` or
// `customers.account.field.behaviourClass` is an identifier that callers name;
// renaming it breaks every caller, so it keeps its spelling on purpose. The
// same goes for a stored code (`cheque` is still the fee-method code) and for
// every `{{placeholder}}`, which are stripped before a value is read.
//
// ⚠ IT READS en.json ONLY. The other ten catalogues are each written in their
// own language (rule 35): French says *chèque* and Spanish *cheque*, correctly.
//
// ⚠ CANADA. If a Canadian utility onboards, *cheque*, *centre* and *cancelled*
// are correct there. That is an `en-CA` catalogue beside this one — data, per
// BR-SHL-030 — and never a reason to loosen this list.
import { describe, expect, it } from "vitest";

import en from "./locales/en.json";

/**
 * British forms that have exactly one US spelling, whatever the sentence.
 * Whole words, case-insensitive. Each family is named so a failure says which
 * habit came back.
 */
const BRITISH_SPELLINGS: ReadonlyArray<readonly [family: string, pattern: RegExp]> = [
  ["cheque → check", /\b(cheque|cheques)\b/i],
  ["cancelled → canceled", /\b(cancelled|cancelling)\b/i],
  ["centre → center", /\b(centre|centres|centred)\b/i],
  ["catalogue → catalog", /\b(catalogue|catalogues)\b/i],
  ["licence → license", /\b(licence|licences)\b/i],
  ["-our → -or", /\b(colour|colours|coloured|behaviour|behaviours|labour|favour|favourite|honour|neighbour|flavour|harbour|humour|rumour)\b/i],
  ["-ise → -ize", /\b(organis(e|ed|es|ing|ation|ations)|recognis(e|ed|es|ing)|unrecognised|authoris(e|ed|es|ing|ation)|re-authoris(e|ed|ing)|categoris(e|ed)|uncategorised|annualis(e|ed)|capitalis(e|ed|ation)|finalis(e|ed|es|ing)|prioritis(e|ed|es|ing)|summaris(e|ed|es|ing)|customis(e|ed|es|ing|ation)|normalis(e|ed|ation)|amortis(e|ed|ation)|minimis(e|ed)|maximis(e|ed))\b/i],
  ["-yse → -yze", /\b(analys(e|ed|es|ing)|paralys(e|ed))\b/i],
  ["-re → -er", /\b(metre|metres|litre|litres|fibre|kilometre|kilometres)\b/i],
  ["ageing → aging", /\bageing\b/i],
  ["programme → program", /\b(programme|programmes)\b/i],
  ["-ement → -ment", /\b(acknowledgement|acknowledgements|judgement|judgements)\b/i],
  ["enrol → enroll", /\b(enrol|enrols|enrolment|enrolments)\b/i],
  ["instalment → installment", /\b(instalment|instalments)\b/i],
  ["fulfil → fulfill", /\b(fulfil|fulfils|fulfilment)\b/i],
  ["-ll- → -l-", /\b(labelled|labelling|levelled|levelling|totalled|totalling|travelled|travelling|modelled|modelling|signalled)\b/i],
  ["grey → gray", /\b(grey|greyed)\b/i],
  ["artefact → artifact", /\b(artefact|artefacts)\b/i],
  ["enquiry → inquiry", /\b(enquiry|enquiries|enquire)\b/i],
  ["e-mail → email", /\be-mail\b/i],
  ["fortnightly → biweekly", /\b(fortnight|fortnightly)\b/i],
  ["postcode → ZIP code", /\b(postcode|postcodes)\b/i],
  ["for ever → forever", /\bfor ever\b/i],
  ["driving licence → driver's license", /\bdriving licen[cs]e\b/i],
  ["tick → check or select", /\b(tick|ticks|ticked|ticking|untick|unticked|tick box|tick boxes)\b/i],
];

/**
 * British PHRASES, where the single word is fine in US English and only the
 * phrase is not. "Post" is the hard one: a ledger POSTING is correct US
 * accounting English and appears on every money screen, so only the MAIL
 * sense is listed here — never the bare word.
 */
const BRITISH_PHRASES: ReadonlyArray<readonly [family: string, pattern: RegExp]> = [
  ["post (mail) → mail", /\b(by post|in the post|returned post|post came back|post coming back|post has come back|we post everything|we will post it|printed and posted|posted mail|when post goes)\b/i],
  ["ring (phone) → call", /\b(ring us|ring the|or ring|ring back|we ring|please ring|before they ring|if you ring)\b/i],
  ["full stop → period", /\bfull stop\b/i],
  ["car park → parking lot", /\bcar park\b/i],
  ["straight away → right away", /\bstraight away\b/i],
  ["has got → has gotten", /\bhas got\b/i],
  ["trading name → doing business as", /\btrading name\b/i],
  ["postal address → mailing address", /\bpostal address\b/i],
  // "flat" is a dwelling in British English and a PRICE SHAPE in both. Only
  // the dwelling sense is listed: "a flat amount every month", "Flat or
  // tiered" and "a flat sum off" are correct US English and must not go red.
  ["flat (dwelling) → apt.", /\b(flat or suite|flats)\b/i],
  // A day before its month is British date order. US order is "August 21, 2026".
  ["date order → Month day, year", /\b\d{1,2} (January|February|March|April|June|July|August|September|October|November|December) \d{4}\b/],
];

/** `{{count}}`, `{{ticked}}` — a placeholder is a variable name, not English. */
const PLACEHOLDER = /\{\{[^{}]*\}\}/g;

function britishIn(patterns: typeof BRITISH_SPELLINGS): string[] {
  const found: string[] = [];
  for (const [key, raw] of Object.entries(en as Record<string, string>)) {
    const value = raw.replace(PLACEHOLDER, " ");
    for (const [family, pattern] of patterns) {
      const match = pattern.exec(value);
      if (match) found.push(`${family}: ${key} = ${JSON.stringify(match[0])}`);
    }
  }
  return found;
}

describe("DEF-SHL-6351 — en.json is written in American English", () => {
  it("no value carries a British spelling", () => {
    expect(britishIn(BRITISH_SPELLINGS)).toEqual([]);
  });

  it("no value carries a British phrase (post as mail, ring as call, a flat as a home)", () => {
    expect(britishIn(BRITISH_PHRASES)).toEqual([]);
  });

  it("the fee-method dropdown the PO photographed says Check, and its code stays cheque", () => {
    const catalogue = en as Record<string, string>;
    expect(catalogue["customers.serviceRequest.feeMethod.cheque"]).toBe("Check");
  });

  it("the price-shape sense of flat is untouched — the carve-out above is real", () => {
    const catalogue = en as Record<string, string>;
    expect(catalogue["billing.budgetAsks.caption"]).toBe("Customers asking for a flat amount");
    expect(catalogue["rating.model.flat"]).toBe("Flat");
  });

  it("a ledger posting is still a posting — only the mail sense of post moved", () => {
    const catalogue = en as Record<string, string>;
    expect(catalogue["payments.status.posted"]).toBe("Posted");
    expect(catalogue["finance.je.post"]).toBe("Post entry ✓");
  });
});
