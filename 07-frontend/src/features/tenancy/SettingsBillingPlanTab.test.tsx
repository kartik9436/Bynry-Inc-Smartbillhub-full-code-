// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-022 (EP-TEN-05) — S107 Settings → Billing plan · Plan tab
// Defect:   DEF-1092 (the commercial model had no screen) · DEF-1220 (r10
//           prices per connection; the product prices in bands) · DEF-1222
//           (A1 prices packages in weeks; the column is months)
// Rules:    BR-TEN-002 · BR-TEN-014 · BR-TEN-240 · BR-SHL-023 (money renders
//           with its currency, at two places) · BR-SHL-025 · B14 rules 18, 21
// ───────────────────────────────────────────────────────
// FOUR THINGS THIS SUITE EXISTS TO HOLD STILL, and three of them are about what
// must NOT appear.
//
// 1. **IMPL-26-0001 reaches a human.** That single sentence is the whole of
//    DEF-1092: the number was written into every tenant on 2026-08-27 and
//    nothing in the product could show it.
// 2. **The price is the CATALOGUE's and nothing multiplies.** r10 draws
//    `$0.85 × 1,247 = $1,059.95`, a rate that exists in no column. The failure
//    mode is not a blank card — it is a future lane restoring that panel
//    because the prototype draws it, so the assertion is that `$1,059.95`,
//    `0.85` and the word `connection` as a COUNT never appear.
// 3. **A $1.00 placeholder never renders as a price.** The PO gave the default
//    and not a figure (*"we will add price latet currently you default it to
//    $1"*), and a dollar that means nothing looks exactly like a considered
//    price once it is formatted.
// 4. **Every absence stays a STATED absence** with the id that closes it on
//    `data-tracks` and out of the sentence (DEF-332 / DEF-445), and never a
//    zero, an empty table or a dash on its own.
//
// ⚠ **WHY MOST OF THE EXPECTED STRINGS BELOW CHANGED ON 2026-09-01, AND WHY
// NOT ONE ASSERTION WAS DELETED TO MAKE THEM PASS.** The PO photographed this
// screen on the running product and asked for *"correct layout of this page"*
// and *"also content on the screen"*. B14 rule 32 (the DESCRIPTION BUDGET,
// ratified 2026-08-31: one sentence per section, a stated absence is a
// `<details>` CLOSED by default) and rule 33 (a LABEL ≤3 words, a FACT ≤6, an
// INSTRUCTION ≤6 per sentence, and RATIONALE = ZERO words on screen) rewrote
// the copy. **The FACT each assertion holds is unchanged; only the words it
// looks for moved**, and each one below says which rule moved it. Where a
// sentence was cut, the reason it carried went into the code comment beside
// the string in `SettingsBillingPlanTab.tsx` — that is where rule 33 sends
// rationale — never into nothing.
//
// 5. **The copy stays inside rule 33's caps FOR EVER**, which is the last
//    `describe` in this file. Rule 33's own status column says it is NOT
//    ENFORCED for on-screen text — no gate in this repo reads a label — so
//    this screen carries its own ratchet rather than trusting a rule nobody
//    checks. It measures the catalogue, so it goes red on the next lane's
//    twelve-word sentence and not only on a re-render of today's.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import en from "@/i18n/locales/en.json";

import type { SubscriptionOverview } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { BillingPlanTab } from "./SettingsBillingPlanTab";

/** The demo tenant exactly as `GET /subscription` serves it after a signup. */
const SELF_SERVE: SubscriptionOverview = {
  subscription: { status: "trial", trial_ends_at: "2026-09-10T00:00:00Z", started_at: null },
  plan: {
    code: "growth",
    name: "Growth",
    price_month: "5000.000000",
    currency: "USD",
    min_accounts: 300,
    max_accounts: 1000,
  },
  implementation_order: {
    order_no: "IMPL-26-0001",
    duration_months: 0,
    price: "0.0000",
    currency: "USD",
    instalments: 1,
    status: "delivered",
    started_on: null,
    delivered_on: null,
    is_self_serve: true,
  },
  addons: [],
  addon_catalogue_size: 0,
  connections: null,
  connections_unavailable: "OQ-660",
  invoices: null,
  invoices_unavailable: "S108",
  payment_method: null,
  payment_method_unavailable: "S109",
};

function render(data: SubscriptionOverview | null, readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (data !== null) {
    queryClient.setQueryData(queryKeys.subscription, data);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/settings/billing-plan"]}>
          <BillingPlanTab readOnly={readOnly} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("S107 — the commercial model finally has a screen (DEF-1092)", () => {
  it("renders the implementation order's reference, which nothing could show before", () => {
    expect(render(SELF_SERVE)).toContain("IMPL-26-0001");
  });

  it("renders the plan's CATALOGUE price at two decimals with its currency", () => {
    const html = render(SELF_SERVE);
    // BR-SHL-023 + CLAUDE.md hard rule 2: stored 4dp, DISPLAYED 2.
    expect(html).toContain("$5,000.00");
    expect(html).not.toContain("5000.000000");
  });

  it("DEF-1220: no per-connection rate and no computed invoice anywhere", () => {
    const html = render(SELF_SERVE);
    // r10 7945–7949's three figures. None has a column behind it.
    expect(html).not.toContain("0.85");
    expect(html).not.toContain("1,059.95");
    expect(html).not.toContain("1,247");
  });

  it("BR-TEN-002: the band renders as a SIZING, never as a limit", () => {
    const html = render(SELF_SERVE);
    expect(html).toContain("300 to 1,000 accounts");
    // The rule in the copy: nothing stops working past the band.
    // ⚠ THE WORDS MOVED, THE RULE DID NOT (B14 rule 33, 2026-09-01). This read
    // *"This range is what the plan was priced for. Nothing stops working if
    // you go past it."* — eighteen words of pure RATIONALE, which rule 33 puts
    // at ZERO words on screen. "Not a limit." is the whole of what BR-TEN-002
    // needs a reader to take away, and the reason it is true now lives in the
    // comment on the `note=` prop in the component.
    expect(html).toContain("Not a limit");
    // And the thing BR-TEN-002 forbids is still forbidden: the band must never
    // read as a ceiling. This is the assertion that would catch a future lane
    // "tidying" the three words away into a bare "Up to 1,000 accounts".
    expect(html).not.toContain("Up to");
  });

  it("OQ-660: the connection count is a stated absence, never a number", () => {
    const html = render(SELF_SERVE);
    expect(html).toContain('data-tracks="OQ-660"');
    // ⚠ SHORTENED, NOT DELETED (B14 rule 33). The eleven-word first half —
    // *"Your live account total is not counted against this range here"* — is
    // said by the summary naming the figure and by the disclosure being shut.
    expect(html).toContain("Bynry works this out with you");
    // The id is for us, the sentence is for them (DEF-332).
    expect(html).not.toContain(">OQ-660<");
  });

  it("B14 rule 32: the connection absence is a <details> CLOSED by default", () => {
    const html = render(SELF_SERVE);
    // Rule 32, ratified by the PO on 2026-08-31 after saying *"too much
    // content - desctiption is too much for clark to read"* four times: a
    // stated absence is a `<details>` closed by default. This one sits BESIDE
    // three facts in the Scale card, so it closes.
    expect(html).toContain('<details data-tracks="OQ-660"');
    // ⚠ THE ASSERTION THAT MAKES THIS A CHECK RATHER THAN A DECORATION. An
    // `<details open>` renders the same summary and the same body and passes
    // every `toContain` above — CLOSED is the entire rule, so it is the thing
    // measured. `renderToStaticMarkup` emits `open=""` for an open details.
    expect(html).not.toContain('<details data-tracks="OQ-660" open');
    // The summary is a LABEL and obeys rule 33's three-word cap.
    expect(html).toContain("Your account total");
  });

  it("DEF-1222: the duration is the PO's MONTHS, and zero reads as self-serve", () => {
    const html = render(SELF_SERVE);
    expect(html).toContain("Self-serve");
    // A1 still prices four packages in WEEKS. The screen renders the column.
    expect(html).not.toContain("weeks");
    // And a zero-month order shows $0.00 rather than hiding the fee line.
    expect(html).toContain("$0.00");
  });

  it("a real implementation project renders its months and its fee", () => {
    const html = render({
      ...SELF_SERVE,
      implementation_order: {
        order_no: "IMPL-26-0007",
        duration_months: 9,
        price: "9000.0000",
        currency: "USD",
        instalments: 2,
        status: "in_progress",
        started_on: "2026-08-01",
        delivered_on: null,
        is_self_serve: false,
      },
    });
    expect(html).toContain("9 months");
    expect(html).toContain("$9,000.00");
    expect(html).toContain("Paid in two installments");
    expect(html).toContain("Under way");
    expect(html).not.toContain("Self-serve");
  });

  it("BR-TEN-014: a trial says when it ends, as a labelled fact", () => {
    const html = render(SELF_SERVE);
    // ⚠ A `Fact` ROW NOW, NOT A SENTENCE (B14 rules 32 + 33, 2026-09-01). It
    // was `"Your free trial ends "` + <DateCell> + `". No card is needed until
    // then."` — a sentence spliced round a component. The date is a FACT and
    // now reads down the same column as Price and Sized for.
    expect(html).toContain("Trial ends");
    expect(html).not.toContain("Your free trial ends");
    // The DATE is what BR-TEN-014 is about and it still renders, through
    // DateCell, in the tenant's format (BR-SHL-034 / IS-8).
    expect(html).toContain("09/10/2026");
  });

  it("the card fact is stated ONCE, in the card that owns it", () => {
    const html = render(SELF_SERVE);
    // B14 rule 32's third clause pointed at a screen rather than a control:
    // *". No card is needed until then."* hung off the trial line in Scale and
    // said the same thing as `paymentMethod.absent` two cards down. One of the
    // two had to go, and it is the one furthest from where a reader looks for
    // it. OQ-015 (v1 takes no card at all) is still stated, in Invoices and
    // payment, and is still true.
    expect(html).toContain("None is needed for your trial");
    expect(html).not.toContain("No card is needed until then");
  });

  it("S108 and S109 are ONE stated absence, not two empty panels", () => {
    const html = render(SELF_SERVE);
    expect(html).toContain('data-tracks="S108"');
    expect(html).toContain('data-tracks="S109"');
    expect(html).toContain("Bynry invoices you directly");
    // An empty invoice table would read as "you have no invoices" — false.
    expect(html).not.toContain("Invoice #");
  });

  it("B14 rule 32: the SECOND absence in a card closes, the first stays open", () => {
    const html = render(SELF_SERVE);
    // ⚠ THE HALF OF RULE 32 A LANE READING ONLY ITS FIRST CLAUSE WOULD GET
    // WRONG. "A stated absence is a `<details>` closed by default" is not a
    // licence to make a card silent: collapse BOTH of these and Invoices and
    // payment is a heading and two twisties. So the test applied is whether an
    // absence sits BESIDE the work or IS the work. The invoice sentence is the
    // whole answer to the question that brings anyone to this card and stays
    // visible; the payment method sits beside it and closes.
    expect(html).not.toContain('<details data-tracks="S108"');
    expect(html).toContain('<details data-tracks="S109"');
    expect(html).not.toContain('<details data-tracks="S109" open');
    expect(html).toContain("Payment details");
  });

  it("B14 rule 32: an absence that IS the card's only content is never collapsed", () => {
    // Add-ons in an empty catalogue, and both `absent` branches, are the whole
    // of their card. Rule 32's "never silent" half: a closed twisty is what a
    // clerk sees INSTEAD of the sentence, so these four stay plain notes.
    // ⚠ SCOPED TO THE SENTENCE, NOT TO THE PAGE. A bare
    // `expect(html).not.toContain("<details")` fails on this screen's TWO
    // legitimate closed disclosures — a check that cannot tell the rule from
    // its exception is the DEF-182 shape, and it is how this test failed the
    // first time it ran. Each sentence is asserted to be the direct child of a
    // plain `<p role="note">` that CARRIES `data-tracks` — which is exactly
    // what tells the two components apart, and is the second thing this test
    // got wrong: `AbsenceDetails` renders its BODY as a `<p role="note">` too,
    // so a regex without `data-tracks` matches a closed absence as though it
    // were an open one. `StatedAbsence` puts the id on the `<p>`; a closed
    // absence puts it on the `<details>` and its body carries none.
    const visible = (sentence: string) =>
      new RegExp(`<p role="note" data-tracks="[^"]*"[^>]*>${sentence}`);

    expect(render({ ...SELF_SERVE, addon_catalogue_size: 0 })).toMatch(
      visible("No add-ons yet"),
    );
    expect(render({ ...SELF_SERVE, plan: null, subscription: null })).toMatch(
      visible("No subscription recorded"),
    );
    expect(render({ ...SELF_SERVE, implementation_order: null })).toMatch(
      visible("No setup order recorded"),
    );
    expect(render(SELF_SERVE)).toMatch(visible("Not shown here yet"));

    // And the two that DO close are not also drawn as a plain note somewhere.
    expect(render(SELF_SERVE)).not.toMatch(visible("Bynry works this out"));
    expect(render(SELF_SERVE)).not.toMatch(visible("No card or bank details"));
  });

  it("an empty CATALOGUE and an empty basket are different sentences", () => {
    // ⚠ SHORTENED, NOT MERGED (B14 rule 33). `you have taken none` and `there
    // is nothing to take` are still two different facts; sixteen words became
    // seven and the distinction is the whole point of this test.
    const empty = render(SELF_SERVE);
    expect(empty).toContain("No add-ons yet");

    const stocked = render({ ...SELF_SERVE, addon_catalogue_size: 3 });
    expect(stocked).toContain("You have not taken any add-ons");
  });

  it("an UNPRICED add-on renders its reason, never the PO's $1.00 placeholder", () => {
    const html = render({
      ...SELF_SERVE,
      addon_catalogue_size: 1,
      addons: [
        {
          code: "sms",
          name: "SMS notices",
          price_month: "1.0000",
          currency: "USD",
          price_source: "catalogue",
          priced: false,
          started_on: "2026-08-20",
          ended_on: null,
        },
      ],
    });
    expect(html).toContain("SMS notices");
    expect(html).toContain("Price not set yet");
    expect(html).not.toContain("$1.00");
  });

  it("a negotiated add-on price renders at two decimals and says it was agreed", () => {
    const html = render({
      ...SELF_SERVE,
      addon_catalogue_size: 1,
      addons: [
        {
          code: "portal",
          name: "Customer portal",
          price_month: "99.5000",
          currency: "USD",
          price_source: "negotiated",
          priced: true,
          started_on: "2026-08-20",
          ended_on: null,
        },
      ],
    });
    expect(html).toContain("$99.50");
    expect(html).toContain("agreed for you");
  });

  it("no control on this screen writes: no form, no input, no primary button", () => {
    const html = render(SELF_SERVE);
    expect(html).not.toContain("<input");
    expect(html).not.toContain("<form");
    expect(html).not.toContain('data-variant="primary"');
    // r10's two buttons and A1's three actions have no endpoint between them.
    expect(html).not.toContain("Compare plans");
    expect(html).not.toContain("Change plan");
    expect(html).not.toContain("Cancel subscription");
  });

  it("BR-SHL-025's spirit: `readOnly` changes the sentence, so the prop is USED", () => {
    // G13 / hard-won law 2 — a prop nothing reads is dead UI. This screen has
    // no control to disable, so the prop selects the reason instead.
    // ⚠ BOTH SENTENCES SHORTENED (B14 rule 33) — the prop still selects
    // between them, which is the only thing this test was ever about.
    expect(render(SELF_SERVE, false)).toContain("Not from this screen");
    expect(render(SELF_SERVE, true)).toContain("Your role can only read this");
  });

  it("BR-SHL-044: the TAB BODY mints no second <h1>", () => {
    expect(render(SELF_SERVE)).not.toContain("<h1");
  });

  it("A18 §3: an unseeded read renders the skeleton, never an empty screen", () => {
    const html = render(null);
    expect(html).not.toContain("IMPL-");
    expect(html.length).toBeGreaterThan(0);
  });

  it("a subscription that is not recorded says so and renders no price", () => {
    const html = render({ ...SELF_SERVE, plan: null, subscription: null });
    // ⚠ SHORTENED (B14 rule 33): sixteen words to eight, both sentences kept.
    // The second is the INSTRUCTION and rule 33 is explicit that cutting it to
    // reach one short line is the failure the cap exists to prevent.
    expect(html).toContain("No subscription recorded");
    expect(html).toContain("Ask Bynry to check");
    expect(html).not.toContain("$5,000.00");
  });
});

describe("S107 layout — four cards, one grid, two columns, rows that stretch", () => {
  it("is ONE grid with the column count PINNED at two, not two auto-fit grids", () => {
    const html = render(SELF_SERVE);
    // The PO's *"correct layout of this page"*. The four cards were two grids
    // stacked with `mt-4`, each on `repeat(auto-fit,minmax(320px,1fr))` — two
    // columns only BY ACCIDENT, because each grid held exactly two children so
    // `auto-fit` had nothing to open a third track with. Merge them under
    // `auto-fit` and a wide viewport puts all four in one row, which then
    // stretches every card to the tallest. The count is now STATED.
    expect(html).toContain("grid-cols-1 md:grid-cols-2");
    expect(html).not.toContain("auto-fit");
    // ONE grid, so one set of column tracks and one gutter. Two grids meant
    // the gutter between the rows (`mt-4`) was maintained by hand next to the
    // gutter inside them (`gap-4`): the same 1rem today, and a change to one
    // silently not a change to the other.
    expect(html.match(/grid gap-4/g) ?? []).toHaveLength(1);
  });

  it("rows STRETCH — `items-start` is what made four cards read as four blocks", () => {
    // Grid rows are independent, so row 1 equalises to max(Scale, Setting you
    // up) and row 2 to max(Add-ons, Invoices): the cards share two bottom
    // edges instead of four. This is the assertion that goes red if a lane
    // puts `items-start` back to "stop the short card stretching".
    expect(render(SELF_SERVE)).not.toContain("items-start");
  });

  it("Scale and Setting you up are the SAME SHAPE — three labelled facts each", () => {
    const html = render(SELF_SERVE);
    // ⚠ THIS IS THE REAL LAYOUT FIX AND IT IS A CONTENT FIX. The ragged
    // heights were not a grid bug: Scale drew a price, a band and then THREE
    // stacked paragraphs while Setting you up drew labelled facts. Equal
    // heights alone would have stretched the short card to match the tall one
    // — a taller ragged screen. Rules 32 and 33 turned Scale's paragraphs into
    // a third Fact row and a closed disclosure, so the two cards now agree in
    // height because they agree in STRUCTURE.
    for (const label of ["Price", "Sized for", "Trial ends"]) {
      expect(html).toContain(label);
    }
    for (const label of ["Reference", "Setup time", "One-off setup fee"]) {
      expect(html).toContain(label);
    }
    // `Fact` is the only thing that renders this kicker class, so counting it
    // counts label/value rows. Six: three in each of the top two cards.
    expect(html.match(/tracking-table-header/g) ?? []).toHaveLength(6);
  });
});

describe("S107 copy — B14 rules 31 and 33, held as a ratchet", () => {
  const KEYS = Object.entries(en as Record<string, string>).filter(([k]) =>
    k.startsWith("settings.billingPlan."),
  );

  it("has strings to measure at all (a guard against an empty-set green)", () => {
    // A filter that matches nothing passes every `for` loop under it. This is
    // the check that says the ratchet below is measuring something — the
    // DEF-182 lesson: a check whose output cannot distinguish pass from fail
    // is worse than none, because it is trusted.
    expect(KEYS.length).toBeGreaterThan(40);
  });

  it("B14 rule 33: no sentence over 6 words, no message over 2 sentences", () => {
    // ⚠ WHY THIS LIVES HERE AND NOT IN A GATE. Rule 33's own status column in
    // B14 reads *"NOT ENFORCED for these five kinds"* — G33 measures only the
    // REFUSAL family and not one string on this screen is a refusal, so on
    // 2026-09-01 nothing in this repo could have caught the 32-word lede, the
    // 18-word band note or the 19-word self-serve sentence. It is measured on
    // the CATALOGUE rather than the rendered output on purpose: that way it
    // goes red on the next lane's long sentence, not only on a re-render of
    // today's. The counter is deliberately the same crude, generous one G33
    // uses, so the two cannot disagree about what a long sentence is.
    const over: string[] = [];
    for (const [key, value] of KEYS) {
      const sentences = value
        .trim()
        .split(/(?<=[.!?])\s+/)
        .filter((s) => s.length > 0);
      const longest = Math.max(...sentences.map((s) => s.split(/\s+/).length));
      if (sentences.length > 2 || longest > 6) {
        over.push(`${key} (${longest}w, ${sentences.length}s): ${value}`);
      }
    }
    // ⚠ SHORTEN BY DELETING THE RATIONALE, NEVER THE INSTRUCTION — rule 33's
    // own words, and the failure this cap cannot see. The reason a thing is so
    // belongs in the code comment beside the string; every cut on this screen
    // has one there.
    expect(over).toEqual([]);
  });

  it("B14 rule 31: no internal id reaches the reader — but IMPL-26-0001 does", () => {
    // ⚠ READ IT AS TEXT, NEVER AS MARKUP. Rule 31's own sentence puts the
    // internal value on an attribute as evidence (`data-tracks="OQ-660"`), so
    // a check over the DOM string goes RED on a correct fix and GREEN on the
    // breach. Tags are stripped first, which is what a clerk actually sees.
    const text = render(SELF_SERVE).replace(/<[^>]*>/g, " ");
    for (const pattern of [/\bDEF-\d/, /\bOQ-\d/, /\bBR-[A-Z]{3}-\d/, /\bUS-[A-Z]{3}-\d/, /\bS10\d\b/]) {
      expect(text).not.toMatch(pattern);
    }
    // ⚠ AND THE ONE REFERENCE THAT STAYS. Rule 31 is not "no codes on screen";
    // it is "nothing INTERNAL", and it names the exception itself: *"Where the
    // reference is genuinely what a user needs — a batch number, a premise
    // number — it has a HUMAN-FACING number and that is what is shown."*
    // `IMPL-26-0001` is the implementation order's `order_no`, not its primary
    // key: it is written for a person, it is the number a utility quotes back
    // to Bynry, and showing it is the whole of DEF-1092's headline. It stays.
    expect(text).toContain("IMPL-26-0001");
  });

  it("B14 rule 31: the order NUMBER is shown and the row's id never is", () => {
    // The half of rule 31 G28 cannot see, because G28 inspects strings and not
    // rendered output: a uuid-shaped VALUE in a field. An order with no
    // human-facing number says so IN WORDS and renders nothing else.
    const html = render({
      ...SELF_SERVE,
      implementation_order: { ...SELF_SERVE.implementation_order!, order_no: null },
    });
    expect(html).toContain("Not numbered yet");
    expect(html).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-022@EP-TEN-05 (authored 2026-08-27 for DEF-1092)
// screens: S107
// generated: 2026-08-27 by the CR-039 wave F screen lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no write path on this resource)
// exceptions: E4 the browser half — clicking Settings → Billing plan and
//   reading IMPL-26-0001 off a live stack — is proved by hand in this lane's
//   report and is Playwright scope here (this project has no jsdom env, so a
//   click cannot be driven from vitest)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
