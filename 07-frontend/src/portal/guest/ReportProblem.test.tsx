// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-007 (EP-CWP-03) · US-CWP-009 · Screens: CWP-006 · CWP-007
//           wireframes/CWP-006.png · wireframes/CWP-007.png
// Rules:    B14 rule 36 (compose the kit — this file asserts that the report
//           screen names NO raw `<button>` and NO danger tier) · r10 rule 6 ·
//           rule 9 (a single-choice field is a radio list) · rule 11 (a
//           consequence box before the commit) · CR-068 §2b (the photo picker
//           renders HELD and has no file input) · BR-CWP-028 · rule 31
// Cases:    US-CWP-007 TC-3 (gas routes and creates nothing) · TC-8 (the photo
//           is held, no file input) · US-CWP-009 TC-1 (the reference and the
//           four-step timeline)
// ─────────────────────────────────────────────────────────────────────────
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { ReportRoutedView, ReportSentView } from "../api/guestClient";

import { ReportProblem } from "./ReportProblem";
import { ReportRouted } from "./ReportRouted";
import { ReportSent } from "./ReportSent";

// ⚠ **THE REFERENCE READ `RP-26-0412` UNTIL 2026-09-04 (`CR-072`).** One press
// of Send wrote two rows and this screen was handed the number of the one that
// was NOT the person's request. It is the service request's own number now, and
// the `RP-` series never leaves the staff app.
const SENT: ReportSentView = {
  created: true,
  reference: "SR-26-0049",
  kind: "leak_or_burst",
  location_text: "1408 Elm St, Austin TX 78702",
  reported_at: "2026-09-02T14:52:00Z",
  status: "looking_into_it",
  already_reported_street: null,
};

const ROUTED: ReportRoutedView = {
  created: false,
  emergency_phone: "(512) 555-0100",
  tenant_name: "Pine Hill Water & Power",
};

function render(node: JSX.Element): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/pine-hill/portal/report"]}>{node}</MemoryRouter>,
  );
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;

describe("CWP-006 · report a problem (US-CWP-007)", () => {
  const html = render(
    <ReportProblem emergencyPhone="(512) 555-0100" onSent={() => undefined} />,
  );
  /**
   * ⚠ **THE SAME SCREEN AT A UTILITY THAT HAS PUBLISHED NO EMERGENCY NUMBER**,
   * which is the only state in which this screen still draws a danger band of
   * its own (`DEF-CWP-4937`). See the block of cases at the foot of this file.
   */
  const noPhone = render(<ReportProblem emergencyPhone={null} onSent={() => undefined} />);

  it("offers all six kinds as a RADIO LIST, not a wall of boxes (r10 rule 9)", () => {
    expect(html).toContain('data-radiolist=');
    for (const kind of [
      "no_water",
      "leak_or_burst",
      "low_pressure",
      "gas_smell",
      "missed_collection",
      "damaged_meter",
    ]) {
      expect(html).toContain(`data-radio="${kind}"`);
    }
    expect(html).not.toContain('type="checkbox"');
  });

  it("routes a smell of gas rather than queueing it — the hint says so on the form", () => {
    expect(html).toContain("do not use this form");
  });

  /**
   * ⚠ **THIS CASE USED TO READ *shows the emergency number in the rail* AND
   * ASSERT `(512) 555-0100` ON THE SCREEN — AND IT IS NOW THE OPPOSITE
   * ASSERTION (`DEF-CWP-4937`, `CR-085` step 2, 2026-09-11).**
   *
   * `GuestFrame` gained its own `EmergencyBand` in the same CR — above the
   * children on EVERY signed-out screen, which is what the drawing's *"Emergency
   * number on every unauthenticated screen"* asks for and what this screen
   * alone used to provide. Measured in a browser at 390 AND 1280 on a tenant
   * with a number published: **two identical red panels, stacked**, on the most
   * dangerous screen in the product.
   *
   * So the screen's own band is now the FALLBACK for the one case the frame
   * deliberately leaves empty — `BR-CWP-093`, no phone, no band — and the
   * number reaching the reader is the frame's. Asserting the number here again
   * would be asserting the duplicate.
   */
  it("draws NO danger band of its own once the utility has published a number", () => {
    expect(html).not.toContain("data-emergency-band");
    // ⚠ And the number is not hand-drawn anywhere else on the screen either —
    // a second copy of it further down would be the same defect, quieter.
    expect(html).not.toContain("(512) 555-0100");
  });

  it("and still draws one when the utility has published none (BR-CWP-093)", () => {
    expect(noPhone).toContain("data-emergency-band");
    expect(noPhone).toContain("Is anyone in danger?");
    // The fallback the frame cannot make: *ring the number on your bill*, and
    // the sentence that is only true beside a report form.
    expect(noPhone).toContain("the number on your bill");
    expect(noPhone).toContain("Do not use this form.");
  });

  it("D11 — the danger panel is Panel.Emergency, so it does not read as a note", () => {
    // ⚠ **`DEF-CWP-3986`.** The drawing has asked for `Panel.Emergency` here
    // since the wave was written — *"rail [`Panel.Emergency` *Is anyone in
    // danger?* (brand left rule, phone number bold)]"* — and the tone did not
    // exist, so this rendered as a plain grey box IDENTICAL to the *someone
    // may have reported this already* note directly beneath it. Two panels
    // saying very different things looked the same.
    //
    // ⚠ **`border-l-accent`, NOT `border-l-[var(--brand)]` as the inventory
    // spells it.** `--brand` is set nowhere in this product and every rule
    // that read it painted GREY (`DEF-CWP-3736`) — which on THIS panel would
    // be the defect being fixed, re-introduced and invisible.
    // ⚠ Read off the FALLBACK render — the only one this screen still draws
    // its own band in (`DEF-CWP-4937`). The frame's band composes the same
    // `Panel` with the same tone, so the tier this case exists to protect is
    // the same on both sides.
    expect(noPhone).toContain('data-tone="emergency"');
    expect(noPhone).toContain("border-l-4");
    expect(noPhone).toContain("border-l-accent");
    expect(noPhone).not.toContain("border-l-[var(--brand)]");
  });

  it("US-CWP-007 TC-8 — the photo picker is HELD and there is NO file input", () => {
    expect(html).toContain('data-photo-picker="held"');
    expect(html).toContain("Photos open with a later release.");
    expect(html).not.toContain('type="file"');
  });

  it("shows the consequence box before the commit (r10 rule 11)", () => {
    expect(html).toContain("WHAT THIS WILL DO");
    expect(html).toContain("Raises a job for the crew.");
    expect(html.indexOf("WHAT THIS WILL DO")).toBeLessThan(html.indexOf("Send this report"));
  });

  it("commits with `Verb ✓` and NEVER in the danger tier (r10 rules 4 and 6)", () => {
    expect(html).toContain("Send this report ✓");
    // ⚠ THE ASSERTION IS ON THE RENDERED TIER, NOT ON THE WORDS. B14 rule 36
    // breach (b) shipped a sign-in button in the danger colour and every text
    // assertion in the suite passed over it.
    expect(html).not.toContain('data-variant="danger"');
    expect(html).not.toContain("border-danger-500");
  });

  it("names no id and no rule id in anything a visitor reads (B14 rules 31, 32)", () => {
    expect(html).not.toMatch(UUID);
    expect(html).not.toMatch(/\bBR-[A-Z]{3}-\d{3,5}\b/);
  });

  // ⚠ **THE EMERGENCY BAND IS ABOVE EVERYTHING, ON EVERY WIDTH (`CR-085`,
  // 2026-09-08)** — the drawing's own words, and the reason it gives is a
  // safety one: *"A form that quietly accepts a gas-smell report is the most
  // dangerous screen in the product."*
  //
  // ⚠ **THIS ASSERTS POSITION AND THE OLDER ONE ASSERTS PRESENCE, WHICH IS WHY
  // NOTHING CAUGHT IT.** *shows the emergency number in the rail* four cases up
  // passes identically whether the band is the first thing on the page or the
  // last thing under the Send button — and in the rail it WAS the last thing,
  // because `TwoCol` stacks its rail under its main column at 390. A check that
  // cannot tell those two apart is hard-won law 7's *looking at the wrong
  // thing*; this one compares indexes, so it goes red on the arrangement the
  // screen shipped with.
  //
  // ⚠ **READ OFF THE FALLBACK RENDER SINCE `DEF-CWP-4937`.** The band the
  // frame draws is above the children by construction and is `GuestFrame`'s to
  // assert; what this case still owns is that the band THIS SCREEN draws, when
  // the frame draws none, is above the form rather than under it.
  it("puts the danger band ABOVE the form, not under it (CR-085)", () => {
    const band = noPhone.indexOf("data-emergency-band");
    expect(band).toBeGreaterThan(-1);
    // Before the page head, before the first question, before the commit.
    expect(band).toBeLessThan(noPhone.indexOf("REPORT A PROBLEM"));
    expect(band).toBeLessThan(noPhone.indexOf("WHAT IS HAPPENING?"));
    expect(band).toBeLessThan(noPhone.indexOf("Send this report"));
    // ⚠ And OUTSIDE the rail, which is the thing that actually moved: a band
    // inside `data-twocol-rail` is a band under the whole form on a phone,
    // however early it is written among the rail's own children.
    expect(band).toBeLessThan(noPhone.indexOf("data-twocol-rail"));
  });

  /**
   * ⚠ **B14 RULE 39's FIELD ANATOMY — *field → field 20px* (`DEF-CWP-4856`).**
   *
   * The five fields were direct children of `Card`, whose gap is the scale's
   * BLOCK step (16) and is correct for blocks. Measured with `getComputedStyle`
   * on the running app at 390 AND 1280 before this change: **16**, against the
   * `Where` helper's 6px — so a helper sat almost exactly between the input
   * above it and the label below, which is the failure the anatomy clause
   * describes in words.
   *
   * ⚠ **THE ASSERTION IS A CLASS AND IT KNOWS WHAT THAT IS WORTH (hard-won law
   * 7: what would make this pass wrongly?).** `gap-5` in the DOM is not proof
   * the gap RENDERS at 20 — a Tailwind utility in a file that is not on
   * `route-b-migrated.txt` is a class no stylesheet declares and renders as
   * nothing at all, and `toContain` passes on it either way (`DEF-974`). The
   * portal is covered by that ledger's `portal/` directory entry, and the 20px
   * itself was read off the running page by
   * `10-scripts/cr085_lane2_guest_walkthrough.mjs`. This case exists to notice
   * the class being taken back OUT.
   */
  it("stacks its fields on the FIELD step, not the block step (DEF-CWP-4856)", () => {
    expect(html).toContain("flex flex-col gap-5");
  });
});

describe("CWP-007 · report sent (US-CWP-009)", () => {
  const html = render(<ReportSent sent={SENT} />);

  it("shows the reference a stranger keeps, and where and what", () => {
    expect(html).toContain("SR-26-0049");
    // ⚠ `CR-072` — the utility's own operational number is not on this screen.
    expect(html).not.toContain("RP-");
    expect(html).toContain("1408 Elm St, Austin TX 78702");
    expect(html).toContain("A leak or a burst");
  });

  it("draws the four-step timeline with step two CURRENT", () => {
    // ⚠ `data-timeline-step`, NOT `data-step` — the kit's `Stepper` already
    // owns `data-step` and two components answering to one attribute is how a
    // selector starts matching the wrong thing.
    expect(html).toContain('data-timeline-step="done"');
    expect(html).toContain('data-timeline-step="current"');
    expect((html.match(/data-timeline-step="future"/g) ?? []).length).toBe(2);
    expect(html).toContain("A crew is sent if needed");
  });

  it("closes on the sentence that invites a second report", () => {
    expect(html).toContain("we would rather hear twice than not at all");
  });

  it("holds *Text me the reference* with its reason (CR-068 R3)", () => {
    expect(html).toContain("Text me the reference");
    expect(html).toContain("Texts open with a later release.");
    expect(html).toContain('data-held="true"');
  });

  // ⚠ **THE ONE BRANCH OF THIS SCREEN THAT HAD NO CASE** (added 2026-09-05).
  // `already_reported_street` is the sentence that tells a passer-by somebody
  // has already rung about this street — and `selectors.already_reported_street`
  // records that pointing it at the wrong table would have made it return null
  // for every real second report, *"a shipped sentence quietly going silent,
  // with tsc and every test green"*. That is hard-won law 2, and it is the
  // branch a test has to enter for the sentence to be proved reachable at all.
  it("names the street when somebody has already reported it — and says nothing when nobody has", () => {
    const already = render(
      <ReportSent sent={{ ...SENT, already_reported_street: "Elm St" }} />,
    );
    expect(already).toContain("Elm St");
    // The default fixture carries `null`, and the line must then be ABSENT
    // rather than rendered empty: an empty sentence reads as a bug, and a
    // present one would tell every reporter their report is a duplicate.
    expect(html).not.toContain("already told us");
  });
});

describe("CWP-006's second state · a smell of gas (US-CWP-007 TC-3)", () => {
  const html = render(<ReportRouted routed={ROUTED} />);

  it("returns a phone number and says NOTHING was created", () => {
    expect(html).toContain('data-routed="gas_smell"');
    expect(html).toContain("(512) 555-0100");
    expect(html).toContain("Nothing was sent and nothing was recorded.");
  });

  it("shows no reference, because there is nothing to reference", () => {
    expect(html).not.toContain("RP-");
    expect(html).not.toContain("Reference");
  });
});
