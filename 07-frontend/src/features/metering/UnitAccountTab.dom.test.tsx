// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-MET-002 (S15 unit detail — the Account tab) · CR-089 wave I,
//          tasks I1–I5 · `PUJ-36` to `PUJ-40`
// Rules:   BR-CUS-039 (a protection forbids disconnection) · BR-PAY-013 (the
//          cash-only sanction at the tenant's Nth bounce) · BR-CUS-059
//          (autopay is the customer's election) · BR-BIL-036 (print is the
//          FLOOR; paperless and SMS only ADD) · BR-CUS-035 (notes) ·
//          BR-CUS-094 (the seven customer classes) · BR-MET-094 (a vacant
//          unit is billed — the base charges go to the owner) ·
//          CLAUDE.md hard rule 2 (money displayed to 2 decimals)
// Defects: DEF-CUS-4691 (a protection on no screen a clerk reaches from a
//          unit) · DEF-CUS-4692 (nine columns on zero rows) · DEF-595 (six
//          decimals on a customer-facing screen)
// ───────────────────────────────────────────────────────
// ⚠ **EVERY ASSERTION HERE IS ABOUT RENDERED OUTPUT, AND THAT IS THE POINT.**
// What can go wrong on this tab is a WORD: *autopay on* over an account that
// will never be drafted, a stated *none* silently omitted, a protection that
// does not reach the top of the page. A test that asserted the props would go
// green on a screen that told a supervisor the opposite of the truth.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { describe, expect, it } from "vitest";

import type { UnitAccountResponse } from "@/api/endpoints";

import { quietAnswer, renderAccountTab, TEST_TENANT } from "./unitAccountFixture";

/** A medical certificate in force — `DEF-CUS-4691`'s own case. */
function withMedicalProtection(): UnitAccountResponse {
  const answer = quietAnswer();
  answer.facts!.protections = {
    in_force: [
      {
        id: "prot-1",
        kind: "medical_certificate",
        in_force: true,
        effective_from: "2026-08-07",
        expires_on: "2026-11-05",
        lifted_on: null,
        set_by: "tenant",
      },
    ],
    lapsed: [],
    disconnection_held: true,
    kinds_in_force: ["medical_certificate"],
  };
  return answer;
}

describe("CR-089 I1 · a protection is a banner above everything", () => {
  it("DEF-CUS-4691: a medical certificate reaches the top of the tab, dated, with who set it", () => {
    const html = renderAccountTab(withMedicalProtection());
    expect(html).toContain("Do not disconnect.");
    // ⚠ **`Medical protection`, REWORDED 2026-09-10 TO THE DRAWN WORD.** The
    // U7 frame heads this banner *Medical protection*; the catalogue said
    // *Medical certificate*, which names the PAPER rather than the state it
    // puts the account in. What the banner is FOR — a hold on disconnection —
    // is what a supervisor about to send someone out needs to read.
    expect(html).toContain("Medical protection");
    // The tenant's own date format — the ONE formatter (`BR-SHL-023`).
    expect(html).toContain("11/05/2026");
    // ⚠ **A ROLE, NEVER A NAME.** `account_protections.set_by` holds `tenant`
    // or `regulator` and no column anywhere holds the person who typed it;
    // `CR-089`'s worked example reads *"set by D. Whitfield"* and that name is
    // not in this product. Rendering one would be a fabricated attribution on
    // the record that stops a disconnection.
    expect(html).toContain("set by this utility");
    expect(html).not.toContain("Whitfield");
    // The reassurance a supervisor acts on.
    expect(html).toContain("Disconnection is held while this stands.");
  });

  it("the banner is ABOVE the account's own facts, not beside them", () => {
    // ⚠ Position is the requirement, not presence. `DEF-CUS-4691` is about a
    // supervisor arranging a shut-off: a protection three sections down is a
    // protection they scroll past. Measured by INDEX in the markup so a lane
    // moving the block fails here rather than in a support call.
    const html = renderAccountTab(withMedicalProtection());
    const banner = html.indexOf("Do not disconnect.");
    // ⚠ **THE ANCHOR MOVED WITH THE SCREEN, 2026-09-10.** It used to be
    // `Start date`, the first fact row — and the U7 frame draws no start row at
    // all: the open date is the `Status` row's qualifier. The anchor is now the
    // heading of the first GROUP, which is a stronger thing to measure against
    // anyway: it is where the account's own facts BEGIN, whatever rows they
    // happen to contain. The presence guard below is what caught the change.
    const facts = html.indexOf("The account");
    // ⚠ **BOTH INDEXES ARE ASSERTED PRESENT FIRST, AND THAT IS NOT PEDANTRY —
    // THIS CHECK FALSE-PASSED WHEN IT WAS WRITTEN.** `indexOf` answers `-1` for
    // a string that is absent, and `-1 < 480` is true, so the ordering
    // assertion alone went GREEN on a tab with NO BANNER AT ALL — which is the
    // exact state `DEF-CUS-4691` describes. Found by breaking the component
    // deliberately (2d) rather than by reading the test. CLAUDE.md law 7: ask
    // what would make this check pass wrongly.
    expect(banner).toBeGreaterThanOrEqual(0);
    expect(facts).toBeGreaterThanOrEqual(0);
    expect(banner).toBeLessThan(facts);
  });

  it("the danger tier is used — colour is never the only signal", () => {
    const html = renderAccountTab(withMedicalProtection());
    // `WarningBox` is the shared kit (B14 rule 36). `now` is its danger tier,
    // reserved for a state a person must ACT on. The WORDS carry the message
    // either way — *Do not disconnect.* is legible with no colour at all.
    expect(html).toContain('data-warning-tone="now"');
    expect(html).toContain('data-warning="protection-medical_certificate"');
  });

  it("a weather moratorium says the REGULATOR set it, which is a different fact", () => {
    const answer = withMedicalProtection();
    answer.facts!.protections.in_force[0] = {
      ...answer.facts!.protections.in_force[0]!,
      kind: "weather_moratorium",
      set_by: "regulator",
      expires_on: "2026-10-21",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("Weather moratorium");
    expect(html).toContain("set by the regulator");
    expect(html).not.toContain("set by this utility");
  });

  it("a payment-plan hold has NO end date and does not invent one", () => {
    // `ck_protection_lifetime`: a plan hold lasts while the plan is current and
    // lapses the day an instalment is missed. A date here would be a promise.
    const answer = withMedicalProtection();
    answer.facts!.protections.in_force[0] = {
      ...answer.facts!.protections.in_force[0]!,
      kind: "payment_plan",
      expires_on: null,
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("Payment-plan hold");
    expect(html).toContain("while the plan is being kept to");
  });

  it("no protection means no banner — an empty warning box trains people to skip them", () => {
    const html = renderAccountTab(quietAnswer());
    expect(html).not.toContain("Do not disconnect.");
    expect(html).not.toContain("data-warning-tone");
  });
});

describe("CR-089 I2 · the customer class says what it decides", () => {
  it("names the class and the figure it selects", () => {
    // Since `CR-087` a charge code can price per class — residential and
    // commercial can be $8.00 and $34.00 for the same meter size — so the
    // class selects a figure on the bill and the row has to say so.
    const html = renderAccountTab(quietAnswer());
    expect(html).toContain("Residential");
    expect(html).toContain("this decides which base charge the plan applies");
  });

  it("the tenant's own sub-type rides with it where there is one", () => {
    const answer = quietAnswer();
    answer.facts!.customer_class = {
      code: "commercial",
      name: "Commercial",
      legacy: false,
      subtype_code: "restaurant",
      subtype_name: "Restaurant",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("Commercial");
    expect(html).toContain("Restaurant");
  });
});

describe("CR-089 I3 · autopay is read together with cash-only", () => {
  it("DEF-CUS-4692: enrolled and NOT cash-only says the money will be taken", () => {
    const answer = quietAnswer();
    answer.facts!.autopay = {
      elected: true,
      cash_only: false,
      nsf_count: 0,
      nsf_threshold: 2,
      will_be_taken: true,
      reading: "taken",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("On — it will be taken.");
    expect(html).toContain('data-autopay="taken"');
  });

  it("⚠ enrolled AND cash-only says the OPPOSITE, with the reason", () => {
    // ⚠ **THIS IS THE CASE THE CUSTOMER PORTAL GOT WRONG AND IT COST A WAVE.**
    // The account is enrolled — the customer asked for it and nothing un-asks
    // it (`BR-CUS-059`) — and `BR-PAY-013`'s sanction means nothing is drafted.
    // *Autopay: on* alone is not a shortened truth, it is the wrong answer.
    const answer = quietAnswer();
    answer.facts!.autopay = {
      elected: true,
      cash_only: true,
      nsf_count: 2,
      nsf_threshold: 2,
      will_be_taken: false,
      reading: "held_cash_only",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("2 payments bounced.");
    expect(html).toContain("On — but held.");
    expect(html).not.toContain("so it will be taken");
    expect(html).toContain('data-autopay="held_cash_only"');
  });

  it("not enrolled and cash-only states BOTH facts", () => {
    const answer = quietAnswer();
    answer.facts!.autopay = {
      elected: false,
      cash_only: true,
      nsf_count: 3,
      nsf_threshold: 2,
      will_be_taken: false,
      reading: "not_elected_and_cash_only",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("3 payments bounced.");
  });

  it("unreadable is NOT off — *we could not tell* and *not enrolled* differ", () => {
    const answer = quietAnswer();
    answer.facts!.autopay = {
      elected: true,
      cash_only: false,
      nsf_count: 0,
      nsf_threshold: null,
      will_be_taken: null,
      reading: "unreadable",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("Could not be read");
    expect(html).not.toContain("nothing is drafted");
  });
});

describe("CR-089 I4 · five money states are STATED, not omitted", () => {
  it("every one is drawn on a quiet account, because a stated none is the answer", () => {
    // ⚠ **AN ABSENT ROW READS AS *NOT LOOKED UP*.** These six are exactly what
    // a clerk checks before promising anything, so the screen answers all six
    // every time — including when the answer is nothing.
    const html = renderAccountTab(quietAnswer());
    expect(html).toContain("None running"); // payment plan
    expect(html).toContain("Not enrolled"); // budget billing
    expect(html).toContain("Not in collections");
    expect(html).toContain("Payments that bounced");
    expect(html).toContain("None claimed"); // tax exemption
    expect(html).toContain("None held"); // deposit
  });

  it("a deposit renders through the ONE money formatter, with the date it was taken", () => {
    // Hard rule 2: stored to 4 decimals, DISPLAYED to 2. `DEF-595` is what a
    // raw decimal string on this very tab looked like.
    const answer = quietAnswer();
    answer.facts!.deposit = {
      held: "150.000000",
      currency: "USD",
      received_on: "2026-06-01",
      any: true,
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("$150.00");
    expect(html).not.toContain("150.000000");
    expect(html).toContain("taken 06/01/2026");
  });

  it("could-not-be-read is a THIRD state and never collapses into none", () => {
    // `DEF-127` word for word: a screen that renders *no payment plan* over a
    // plan it simply could not fetch tells a clerk the customer never agreed
    // one. Three of these rows cross a module boundary and can all say this.
    const answer = quietAnswer();
    answer.facts!.payment_plan = { state: "unreadable", count: null, running: null };
    answer.facts!.budget_billing = { state: "unreadable", level: null, currency: null };
    answer.facts!.collections = { state: "unreadable", tier: null, paused_reason: null };
    const html = renderAccountTab(answer);
    expect(html).not.toContain("None running");
    expect(html).not.toContain("Not enrolled");
    expect(html).not.toContain("Not in collections");
    expect(html.match(/Could not be read/g)?.length).toBe(3);
  });

  it("a live payment plan and a budget level are drawn with their figures", () => {
    const answer = quietAnswer();
    answer.facts!.payment_plan = { state: "some", count: 2, running: 1 };
    answer.facts!.budget_billing = { state: "some", level: "242.000000", currency: "USD" };
    answer.facts!.collections = { state: "some", tier: "tier_2", paused_reason: null };
    const html = renderAccountTab(answer);
    expect(html).toContain("1 running");
    expect(html).toContain("$242.00");
    expect(html).toContain("In collections");
  });

  it("a tax exemption states the date it runs out", () => {
    const answer = quietAnswer();
    answer.facts!.tax_exemption = {
      claimed: true,
      reference: "TX-EX-4471",
      expires_on: "2027-06-30",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("Claimed");
    expect(html).toContain("until 06/30/2027");
  });
});

describe("CR-089 I5 · account notes are on the tab", () => {
  it("a pinned note leads, and a customer-visible one says so", () => {
    const answer = quietAnswer();
    answer.facts!.notes = [
      {
        id: "n1",
        title: "Medical protection",
        body: null,
        author_id: "u-1",
        author_name: null,
        pinned: true,
        customer_visible: false,
        created_at: "2026-06-12",
      },
      {
        id: "n2",
        title: "Meter access",
        body: "Dog in the side yard — ring first.",
        author_id: "u-2",
        author_name: "A. Reyes",
        pinned: false,
        customer_visible: true,
        created_at: "2026-06-12",
      },
    ];
    const html = renderAccountTab(answer);
    expect(html).toContain("📌");
    expect(html).toContain("Medical protection");
    expect(html).toContain("Meter access");
    expect(html).toContain("Dog in the side yard");
    expect(html).toContain("A. Reyes");
    expect(html).toContain("06/12/2026");
    expect(html).toContain("Marked customer-visible");
  });

  it("⚠ an author we hold and cannot NAME is not the same as no author at all", () => {
    // `DEF-CUS-4704`: `apps.identity.selectors` publishes no `user_display_name`,
    // so `author_name` is null on EVERY note in the product while `author_id` is
    // set. Printing *System* there would attribute a clerk's note to a machine —
    // which is exactly the sentence `note_dict` reserves for a background job.
    const answer = quietAnswer();
    answer.facts!.notes = [
      {
        id: "n1",
        title: "Meter box obstructed",
        body: null,
        author_id: "u-1",
        author_name: null,
        pinned: false,
        customer_visible: false,
        created_at: "2026-06-12",
      },
    ];
    expect(renderAccountTab(answer)).not.toContain("System");

    // No id at all IS the background job, and that one may say System.
    answer.facts!.notes[0] = { ...answer.facts!.notes[0]!, author_id: null };
    expect(renderAccountTab(answer)).toContain("System");
  });

  it("no notes is a sentence, not an empty block", () => {
    expect(renderAccountTab(quietAnswer())).toContain("No notes on this account.");
  });
});

describe("CR-089 I6 · the nine columns, once something writes them", () => {
  it("bad address, the delivery election and the old system's number all render", () => {
    const answer = quietAnswer();
    answer.facts!.reach = {
      bad_address: true,
      paperless: true,
      sms_reminders: true,
      preferred_language: "es-MX",
    };
    answer.facts!.external_ref = "LEG-88214";
    const html = renderAccountTab(answer);
    // ⚠ **THE BAD-ADDRESS FLAG MOVED ONTO THE `Post` ROW, 2026-09-10.** The U7
    // frame draws ONE `Reach them by` row where this tab drew a whole third
    // group, and it draws no bad-address row at all. The FLAG was kept — it is
    // a live thing a clerk acts on before posting a bill, and deleting a
    // working signal because a drawing omits it is a loss the drawing did not
    // ask for — so it rides the address it is a fact about. The sentence is
    // shorter because it now sits beside the address rather than standing as
    // the answer to a `Post came back` label.
    expect(html).toContain("Mail came back — check the address");
    // And it is still emphasised, not folded into the quiet qualifier.
    expect(html).toContain('data-bad-address=""');
    // ⚠ **PRINT IS THE FLOOR** (`BR-BIL-036`): paperless and SMS only ADD a
    // channel, so the sentence always starts with post. Copy that said *by
    // email only* would be wrong about what the customer actually receives.
    expect(html).toContain("By mail, by email and by text");
    expect(html).toContain("es-MX");
    expect(html).toContain("LEG-88214");
  });

  it("paperless alone still says the bill goes by post as well", () => {
    const answer = quietAnswer();
    answer.facts!.reach = {
      bad_address: false,
      paperless: true,
      sms_reminders: false,
      preferred_language: null,
    };
    expect(renderAccountTab(answer)).toContain("By mail and by email");
  });

  it("⚠ credit_tier is served and NEVER drawn — nothing in this product computes it", () => {
    // `BR-CUS-058`: a COMPUTED cache whose rules (`credit_tier_rules`) are
    // unbuilt. A letter on screen would read as a grade this utility awarded.
    const answer = quietAnswer();
    answer.facts!.credit_tier = { value: "B", computed: false, why: "credit_tier_rules_unbuilt" };
    const html = renderAccountTab(answer);
    expect(html).not.toContain("credit_tier");
    expect(html).not.toContain("Credit tier");
  });

  it("no internal code reaches the clerk — B14 rule 32", () => {
    const answer = quietAnswer();
    answer.facts!.autopay.reading = "held_cash_only";
    answer.facts!.autopay.cash_only = true;
    const html = renderAccountTab(answer);
    // The state codes ride in a data attribute for tests and walkthroughs; the
    // clerk-facing copy carries none of them, and neither does a rule id.
    expect(html).not.toContain(">held_cash_only<");
    expect(html).not.toContain("BR-PAY-013");
    expect(html).not.toContain("credit_tier_rules_unbuilt");
  });
});

describe("CR-089 · a vacant unit and a common area are two different sentences", () => {
  it("a vacant unit names the OWNER's account and links to it", () => {
    const answer = quietAnswer();
    answer.account = null;
    answer.facts = null;
    answer.no_account_reason = "vacant";
    answer.owner_account = {
      id: "acc-master",
      account_no: "A-10442",
      name: "Creekside Holdings LP",
      kind: "master",
      status_name: "Active",
    };
    const html = renderAccountTab(answer);
    expect(html).toContain("Nobody occupies this unit");
    expect(html).toContain("Base charges bill to the owner.");
    expect(html).toContain("A-10442");
    expect(html).toContain("Creekside Holdings LP");
    // ⚠ Under the REAL route pattern, so the tenant segment is real. A bare
    // mount would build `//accounts/…` here and `toContain` would pass on it.
    expect(html).toContain(`href="/${TEST_TENANT}/accounts/acc-master"`);
  });

  it("a common area is not called vacant, and is always the owner's", () => {
    const answer = quietAnswer();
    answer.account = null;
    answer.facts = null;
    answer.unit.is_common_area = true;
    answer.no_account_reason = "common_area";
    answer.owner_account = null;
    const html = renderAccountTab(answer);
    expect(html).toContain("This is a common area");
    // `renderToStaticMarkup` escapes the apostrophe, so the assertion stops at
    // the word before it — a literal `'` here would fail on correct output.
    expect(html).toContain("Always billed to the owner");
    expect(html).not.toContain("Nobody occupies this unit");
    // No owner on file is stated rather than left blank — a blank would imply
    // there is nobody to bill, which is a different and worse claim.
    expect(html).toContain("No owner account for this building.");
  });

  it("an unwired customers module says so — it does NOT draw an empty tab", () => {
    // An empty tab would state that this account has no protections, no notes
    // and no plan: three claims nobody made.
    const answer = quietAnswer();
    answer.facts_unavailable = "customers_cannot_answer";
    const html = renderAccountTab(answer);
    expect(html).toContain("The account details did not load.");
    expect(html).not.toContain("Not in collections");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-089 wave I (I1–I6) · DEF-CUS-4691 · DEF-CUS-4692 · PUJ-36..PUJ-41
// generated: 2026-09-08 by the CR-089 wave I build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/metering/UnitAccountTab.dom.test.tsx · every case proved RED against the pre-wave tab before this file was trusted green
// exceptions: E3 the protection banner asserts POSITION by markup index, because *above everything* is the requirement and presence alone would pass on a banner at the bottom
// ──────────────────────────────────────────────────────────
