// @vitest-environment jsdom
// ── THE TRANSFER WIZARD'S PAGE HEAD, AND THE GROUP HEADING THAT OUTLIVED ITS
//    GROUP ───────────────────────────────────────────────────────────────────
//
// ── Trace ────────────────────────────────────────────────────────────────────
// Defects: `DEF-CUS-6542` — one constant `<h1>` over all five steps, so step 1
//          was right and steps 2–5 told a clerk to *"Find the account, and who
//          is selling"* while the line underneath read `Step 2 of 5 · The
//          buyer`. `DEF-CUS-6543` — the shared applicant capture drew *"One
//          identifier"* and *"Give one ID or a phone."* over an EMPTY group
//          whenever no customer kind was stated.
// Drawing: `05-prototype/02 Accounts Menu Blueprint.pdf` (281-page edition),
//          read AS IMAGES at scale 2 — B14 rule 42 — PDF pages **127–131**, one
//          per step. Each draws three lines above the rail and NOTHING else:
//          the `TRANSFER` kicker, the 32px title, `Step N of 5 · <rail label>`.
// Rules:   B14 rule 32 (a row never repeats what its own control offers) · rule
//          33 (a HEADING ≤ 3 words; RATIONALE is zero words on screen) · rule 41
//          (the product matches the drawing) · rule 44 (our UI standard decides
//          construction) · `BR-SHL-046` (ONE declared step list drives the
//          count, the rail, the step line — and now the title) · `BR-CUS-1022`
//          (an unstated kind is asked for no identifier)
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **AMENDED 2026-09-24 (lane TRF-CAP) — THE FIVE HEADS ARE NO LONGER THE DRAWN
// STRINGS.** PO ruling, verbatim: ***"4 · The five transfer headings - b
// Shorten all five to the cap"***, answering the question the lane that built
// this file left open. They ran 7 · 4 · 4 · 5 · 6 words against rule 33's cap of
// three and are now 3 · 2 · 2 · 2 · 3. **`DRAWN` therefore has two string
// columns** — what the blueprint prints and what the head says — and the last
// `describe` block measures the RENDERED head against both halves of rule 33.
// ⚠ **THE MOVE-OUT's FOUR SHORTFALL PATH NAMES ARE UNAFFECTED**: the PO ruled
// *"b) Leave as drawn"* on those the same morning, and the two rulings stand
// side by side. Do not carry this one over to ACC-06.
//
// ⚠ **THE TITLE IS READ OFF THE PAGE HEAD'S OWN `<h1>`, NEVER OFF BODY TEXT.**
// Four of the five drawn titles are ALSO drawn as a SECTION heading further
// down the same step — *"Who is buying it"*, *"The date of sale"* and *"What
// the buyer takes on"* each appear twice on their own screen — so
// `getByText(title)` is satisfied on a step whose HEAD says something else
// entirely. That is this defect wearing the clothes of a pass, and it is why
// every assertion below addresses `h1` inside the screen's own container.
//
// ⚠ **BROKEN BEFORE IT WAS TRUSTED** (hard-won law 7). Pinning
// `TRANSFER_STEPS[1].titleKey` to step 1's key fails
// `step 2's head is its own title` by name, quoting both strings; deleting the
// `asked.size === 0` guard fails `no kind stated: no heading, no instruction`.
//
// ⚠ **THE BLAST RADIUS IS ASSERTED, NOT ASSUMED — AND IT IS ONE SCREEN, NOT
// THREE.** `DEF-CUS-6543`'s own row says the fault *"affects every host that
// passes headings: the transfer's step 2, the move-in request capture and new
// connect"*. Walked on 2026-09-24: **`ApplicantCaptureFields` has exactly one
// importer.** `ServiceRequestCapturePage.tsx` keeps its own `identityFieldsFor`,
// which never returns an empty list, and draws no group heading; `NewConnect`
// draws its identifier fields inline with no heading over them. The last
// `describe` block below pins all three findings so a second host cannot
// quietly re-introduce the shape.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

//: Node builtins reached the way this folder's sibling test already reaches
//: them, so the source-reading guard at the bottom works under the same config.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: "utf8"): string;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  dirname(p: string): string;
  join(...parts: string[]): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};
const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));

import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

import { TransferWizard } from "./TransferWizard";
import { TRANSFER_STEPS, TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";

//: ⚠ A lane lost an hour to cases reading the previous case's DOM.
afterEach(cleanup);

const TEST_TENANT = "brazosbend";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Mount the REAL wizard at the REAL address, on the step asked for.
 *
 *  ⚠ **THE ROUTE PATTERN IS THE REAL ONE, `/:tenant…`.** A bare `MemoryRouter`
 *  leaves `useParams().tenant` undefined and every address the page builds
 *  comes out `//…` — a protocol-relative URL that reads as a perfectly good
 *  string to `toContain` (hard-won law 2's fixture clause). */
function mountStep(step: number): void {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () => json({ count: 0, results: [] }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${TRANSFER_WIZARD_ROUTE}?step=${step}`]}>
          <Routes>
            <Route
              path={`/:tenant${TRANSFER_WIZARD_ROUTE}`}
              element={<TransferWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The page head's own `<h1>` — see the header for why this is not `getByText`. */
function headTitle(): string {
  const screenEl = document.querySelector("[data-r10='TRF-02']");
  expect(screenEl, "the TRF-02 screen container is not mounted").not.toBeNull();
  const h1 = (screenEl as Element).querySelector("h1");
  expect(h1, "the page head has no <h1>").not.toBeNull();
  return ((h1 as Element).textContent ?? "").trim();
}

/** The head of each step. `drawn` is what the blueprint prints; `title` is what
 *  the PO ruled it shortened to; `page` is the PDF page each was read off, kept
 *  here so the next lane re-opens the drawing instead of trusting this list.
 *
 *  ⚠ **`title` WAS `drawn` UNTIL 2026-09-24 — PO ruling, verbatim: *"4 · The
 *  five transfer headings - b  Shorten all five to the cap"*.** Both columns
 *  stay, because the reversal is the fact worth keeping: a lane diffing the head
 *  against the drawing finds five differences and they are RULED, not drift. */
const DRAWN = [
  {
    step: 1,
    page: 127,
    drawn: "Find the account, and who is selling",
    title: "Account & seller",
    rail: "Find the account",
  },
  { step: 2, page: 128, drawn: "Who is buying it", title: "The buyer", rail: "The buyer" },
  { step: 3, page: 129, drawn: "The date of sale", title: "The date", rail: "Date of sale" },
  {
    step: 4,
    page: 130,
    drawn: "What the buyer takes on",
    title: "The money",
    rail: "What they take on",
  },
  {
    step: 5,
    page: 131,
    drawn: "Review — one account, one new owner",
    title: "Review & confirm",
    rail: "Review & confirm",
  },
] as const;

describe("DEF-CUS-6542 · the page head is a function of the step", () => {
  for (const drawn of DRAWN) {
    it(`step ${drawn.step}'s head is its own title (p${drawn.page})`, () => {
      mountStep(drawn.step);
      expect(headTitle()).toBe(drawn.title);
    });
  }

  it("the five heads are five different strings", () => {
    const seen: string[] = [];
    for (const drawn of DRAWN) {
      mountStep(drawn.step);
      seen.push(headTitle());
      cleanup();
    }
    //: ⚠ **THE SHARPEST CHECK, because the fault is a CONSTANT.** Five correct
    //: titles are also five DIFFERENT titles, so a wizard that prints one title
    //: five times fails here by arithmetic even if a later lane mistypes what
    //: the drawing says.
    expect(new Set(seen).size).toBe(5);
  });

  it("the step line still names its own step, beneath the title", () => {
    mountStep(2);
    const line = document.querySelector("[data-flow-footer]");
    expect(line).not.toBeNull();
    const text = ((line as Element).textContent ?? "").trim();
    expect(text).toContain("Step 2 of 5");
    expect(text).toContain("The buyer");
  });

  it("the title comes off the ONE declared step list (BR-SHL-046)", () => {
    //: A sixth step must not need an edit in `TransferWizard.tsx`. Every step
    //: declares its own title beside its own rail label, and both are catalogue
    //: keys — never a hardcoded English string on the screen.
    expect(TRANSFER_STEPS).toHaveLength(5);
    for (const step of TRANSFER_STEPS) {
      expect(step.titleKey, `${step.id} declares no titleKey`).toBeDefined();
      expect(step.titleEn, `${step.id} declares no titleEn`).toBeDefined();
      expect(i18n.exists(step.titleKey as string), `${step.titleKey} is in no catalogue`).toBe(
        true,
      );
    }
  });

  it("⛔ the head carries NO rollup paragraph — p127–p131 draw none", () => {
    //: `DEF-CUS-6480` is this same sentence on the move-out, reported by the PO
    //: on 2026-09-24 (*"too much text reduce it"*) and deleted rather than
    //: shortened. The transfer carried the identical shape one wizard over.
    mountStep(2);
    expect(i18n.exists("customers.transfer.subSteps")).toBe(false);
    expect(screen.queryByText(/steps · the account changes hands/i)).toBeNull();
  });
});

// ── B14 RULE 33's HEADING CAP, ON THE STRING A CLERK ACTUALLY READS ──────────
//
// PO ruling 2026-09-24, verbatim: ***"4 · The five transfer headings - b
// Shorten all five to the cap"***. The five were built as drawn at 7 · 4 · 4 · 5
// · 6 words and are now 3 · 2 · 2 · 2 · 3.
//
// ⚠ **RULE 33's LABEL CLAUSE HAS TWO HALVES AND BOTH ARE CHECKED HERE:** a LABEL
// or heading is **≤ 3 words** AND is **not a sentence**. A cap check alone
// passes *"Sold. Now who?"* at three words, which is two sentences in a heading.
//
// ⚠ **IT READS THE RENDERED `<h1>`, NOT `titleEn`.** A constant can be shortened
// while the catalogue keeps the long value, and **a catalogue entry BEATS a code
// `defaultValue`** — so a check over the declared string would go green on a
// screen still printing seven words. The declared/rendered agreement is asserted
// separately below, which is the only way both facts get stated.
//
// ⚠ **BROKEN BEFORE TRUSTED** (hard-won law 7), in `vitest`, the harness that
// runs it: restoring step 1's drawn title through the catalogue fails
// `step 1's head is within rule 33's heading cap (p127)` by name with
// *"expected 7 to be less than or equal to 3"*, and fails
// `no head is a sentence — rule 33's other half` on the comma.
describe("B14 rule 33 · every transfer head is a heading, not a sentence", () => {
  //: Words are whitespace-separated tokens, which counts `&` as a word — the
  //: STRICTER reading, deliberately. `Account & seller` is at the cap, not
  //: under it, so nothing here is passing on a lenient count.
  const words = (s: string): number => s.trim().split(/\s+/).filter(Boolean).length;

  const HEADING_CAP = 3;

  for (const drawn of DRAWN) {
    it(`step ${drawn.step}'s head is within rule 33's heading cap (p${drawn.page})`, () => {
      mountStep(drawn.step);
      const head = headTitle();
      expect(
        words(head),
        `step ${drawn.step} head ${JSON.stringify(head)} is ${words(head)} words`,
      ).toBeLessThanOrEqual(HEADING_CAP);
    });
  }

  it("no head is a sentence — rule 33's other half", () => {
    //: A heading is a NAME. Terminal punctuation makes it a statement; a comma,
    //: semicolon, colon or em dash makes it a clause — which is exactly what
    //: the two longest drawn titles were (*"Find the account, and who is
    //: selling"*, *"Review — one account, one new owner"*).
    for (const drawn of DRAWN) {
      mountStep(drawn.step);
      const head = headTitle();
      expect(head, `step ${drawn.step} head ends a sentence`).not.toMatch(/[.!?]$/);
      expect(head, `step ${drawn.step} head carries a clause separator`).not.toMatch(/[,;:—]/);
      cleanup();
    }
  });

  it("the shortened five are still FIVE different heads", () => {
    //: The risk this shortening introduces, and the reason it is asserted again
    //: here rather than left to the block above: two steps can collapse onto one
    //: string by accident once the words are this few, and a wizard printing one
    //: title on two steps is `DEF-CUS-6542` reopened at half size.
    const seen: string[] = [];
    for (const drawn of DRAWN) {
      mountStep(drawn.step);
      seen.push(headTitle());
      cleanup();
    }
    expect(new Set(seen).size).toBe(5);
  });

  it("what is declared is what renders, and the drawing is recorded beside it", () => {
    //: `titleEn` is the pre-merge fallback and the catalogue is what ships; when
    //: they disagree the catalogue wins silently, so they are compared rather
    //: than trusted. `drawn` is asserted DIFFERENT on all five, which is what
    //: makes the ruling visible to the next lane instead of looking like drift.
    for (const [index, drawn] of DRAWN.entries()) {
      const step = TRANSFER_STEPS[index];
      expect(step.titleEn, `${step.id} declares a different title`).toBe(drawn.title);
      expect(i18n.t(step.titleKey as string), `${step.titleKey} is not the ruled title`).toBe(
        drawn.title,
      );
      expect(drawn.title, `step ${drawn.step} was not shortened`).not.toBe(drawn.drawn);
      expect(words(drawn.drawn)).toBeGreaterThan(HEADING_CAP);
    }
  });

  it("two of the five equal their rail label, and three do not", () => {
    //: ⚠ **STATED AS A FIGURE, because the honest answer to *did the titles
    //: collapse into the rail labels* is "two of them did".** `The buyer` and
    //: `Review & confirm` are the shortest true name for their step and the rail
    //: already had it; forcing a difference would invent a second name for one
    //: thing. **This case is also the guard on `titleKey` surviving:** if it ever
    //: reaches five, the field is derivable from `labelKey` and should go.
    const equal = DRAWN.filter((d) => d.title === d.rail).map((d) => d.step);
    expect(equal).toEqual([2, 5]);
  });
});

describe("DEF-CUS-6543 · a group heading belongs to its group", () => {
  /** The identifier heading, in whatever language the suite is running. */
  const identifierHeading = (): Element | null =>
    Array.from(document.querySelectorAll("p.font-heading")).find(
      (p) => (p.textContent ?? "").trim() === i18n.t("customers.capture.group.identifier"),
    ) ?? null;

  it("no kind stated: no heading, no instruction, and no boxes", async () => {
    mountStep(2);
    //: `BR-CUS-1022` — an unstated kind is asked for NO identifier, and that is
    //: the rule working. The defect was the label that stayed behind.
    expect(document.querySelector("#trf_buyer_ssn")).toBeNull();
    expect(document.querySelector("#trf_buyer_drivers_licence")).toBeNull();
    expect(document.querySelector("#trf_buyer_date_of_birth")).toBeNull();
    expect(document.querySelector("#trf_buyer_tax_id")).toBeNull();

    expect(identifierHeading(), "'One identifier' renders over an empty group").toBeNull();
    expect(
      document.querySelector("[data-identifier-instruction]"),
      "the instruction renders over an empty group",
    ).toBeNull();
  });

  // ⊕ `DEF-CUS-10255` — the buyer step is Move-in's shared form now: a
  // person's identifiers sit in their own *Identity* panel (CF-1's
  // `CustomerIdentityPanel`, with its one-ID rule line), and a company's Tax ID
  // in the Who panel. The DEF-CUS-6543 rule — no heading over an empty group —
  // is the shared panel's to keep, and these assert it on the new pieces.
  it("Person stated: the Identity panel and its one-ID line come back with the fields", async () => {
    mountStep(2);
    await userEvent.click(screen.getByText(i18n.t("customers.customer.kind.person")));
    expect(document.querySelector("#ssn")).not.toBeNull();
    expect(document.querySelector('[data-customer-panel="identity"]')).not.toBeNull();
    expect(document.querySelector("[data-identity-rule]")).not.toBeNull();
  });

  it("Company stated: the company's one box, and no person's identifiers", async () => {
    mountStep(2);
    await userEvent.click(screen.getByText(i18n.t("customers.customer.kind.company")));
    expect(document.querySelector("#tax_id")).not.toBeNull();
    //: `BR-CUS-1022` again, the other half — a company is never asked for a
    //: licence or a date of birth.
    expect(document.querySelector("#driving_licence")).toBeNull();
    expect(document.querySelector('[data-customer-panel="identity"]')).toBeNull();
  });
});

describe("DEF-CUS-6543 · the blast radius, pinned rather than assumed", () => {
  const read = (file: string): string => nodeFs.readFileSync(nodePath.join(HERE, file), "utf8");
  const HEADING_KEY = "customers.capture.group.identifier";

  // ⚠ **RESTATED 2026-10-18 (lane CF-2, G40).** The shared capture block these
  // two cases pinned (`ApplicantCaptureFields`) lost its last host when the
  // transfer buyer step moved to the shared customer form (image
  // `07-transfer.png`) and was deleted. The defect's lesson survives as two
  // facts: no screen draws its own identifier heading, and the transfer's
  // identifier group is the ONE shared Identity panel.
  it("no screen draws its own copy of the old identifier heading", () => {
    for (const file of [
      "ServiceRequestCapturePage.tsx",
      "NewConnectOwnerStep.tsx",
      "TransferWizard.tsx",
      "applicantCapture.tsx",
    ]) {
      expect(read(file).includes(HEADING_KEY), `${file} draws its own identifier heading`).toBe(
        false,
      );
    }
  });

  it("the transfer's identifiers are the shared Identity panel, not a copy", () => {
    const src = read("TransferWizard.tsx");
    expect(src).toContain("<CustomerIdentityPanel");
    expect(src).not.toContain("<ApplicantCaptureFields");
  });

  it("the move-in capture cannot reach the empty state at all", async () => {
    //: `ServiceRequestCapturePage`'s own `identityFieldsFor` returns the
    //: person's three for ANY kind that is not `business`, so its group is
    //: never empty and it draws no heading either way. Asserted so that a lane
    //: aligning it with `captureIdentityFieldsFor` — which DOES return `[]` —
    //: is told, here, that the heading question comes with it.
    const { identityFieldsFor } = await import("./ServiceRequestCapturePage");
    expect(identityFieldsFor("").length).toBeGreaterThan(0);
    expect(identityFieldsFor("business")).toEqual(["tax_id"]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-029@1b10b71 (TRF-02, the transfer wizard — tip this lane built on)
// amended: 2026-09-24 by lane TRF-CAP — the five heads shortened to B14 rule 33's
//          cap on PO ruling (*"Shorten all five to the cap"*); `DRAWN` gains a
//          `drawn` column and the rule-33 describe block below is new
// generated: 2026-09-24 by lane TRF-TITLES (maintenance, DEF-CUS-6542 + DEF-CUS-6543)
// checklist: reproduced-in-browser✔ located✔ blast-radius-both-ways✔ minimal-fix✔
//            proved-against-the-reproduction✔ regression-walk✔ version✔ reporter-told✔
// gates: tsc✔ (pinned typescript@5.5.4, proved capable of failing first) ·
//        vitest 15/15 this file✔ · customers suite 1772 passed / 27 failed, and the
//        27 are the tip's OWN — the identical command at 1b10b714 gives the same 27,
//        set difference empty both ways · run_gates 133: 54 FAIL, the SAME 54 as the
//        tip, no gate's finding COUNT raised · G15 shows 546 new-untranslated on both
//        trees, so the five keys × eleven languages added none ·
//        10-scripts/def_cus_6542_6543_transfer_head_walkthrough.mjs 18/18✔ (7 red before)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
