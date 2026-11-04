/* CR-075 wave C · C1a — the Sentence block.
 *
 * `RBS-006-R4`'s green READ THIS ALOUD card is the fixture: the sentence a
 * clerk says down the phone. `RBS-006-R6`'s stop card is the second. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

const READ_ALOUD =
  '"Your September bill is $82.20 higher. You used 38% more water over 4 more days, ' +
  'which also took you into the higher price tier. A $12.00 late fee was added for August. ' +
  'Your rate did not change."';

describe("OutcomeCard — RBS-006-R4 region 6, read this aloud", () => {
  it("draws the label above the copy, both as the sheet writes them", () => {
    const html = renderToStaticMarkup(
      <OutcomeCard tone="success" label="Read this aloud">
        {READ_ALOUD}
      </OutcomeCard>,
    );
    expect(html).toContain("Read this aloud");
    expect(html).toContain("Your September bill is $82.20 higher.");
    expect(html).toContain("Your rate did not change.");
  });

  it("the label is optional — a notice with none renders no empty label slot", () => {
    const html = renderToStaticMarkup(<OutcomeCard tone="muted">Nothing to do today.</OutcomeCard>);
    expect(html).not.toContain("data-outcome-label");
    expect(html).toContain("Nothing to do today.");
  });

  it("three tones, three rails, and every colour is one this theme declares", () => {
    expect(renderToStaticMarkup(<OutcomeCard tone="success">x</OutcomeCard>)).toContain(
      "border-l-success-500",
    );
    expect(renderToStaticMarkup(<OutcomeCard tone="danger">x</OutcomeCard>)).toContain(
      "border-l-danger-500",
    );
    expect(renderToStaticMarkup(<OutcomeCard tone="muted">x</OutcomeCard>)).toContain(
      "border-l-neutral-400",
    );
  });

  it("the muted tone carries NO tint — the rail alone says it", () => {
    const html = renderToStaticMarkup(<OutcomeCard tone="muted">x</OutcomeCard>);
    expect(html).toContain("bg-transparent");
    expect(html).not.toContain("bg-neutral-100");
  });

  it("a stop card offers a way past it — a dead end trains people to ignore boxes", () => {
    const html = renderToStaticMarkup(
      <OutcomeCard tone="danger" label="Stop" action={<button type="button">Set a tax region →</button>}>
        <strong>3 things stop billing.</strong> Nothing was sent.
      </OutcomeCard>,
    );
    expect(html).toContain("Set a tax region →");
    expect(html).toContain("3 things stop billing.");
  });

  it("IT COUNTS NO WORDS AND TRUNCATES NOTHING — the rule 33 divergence stays visible", () => {
    // Part 4 §1 measured 28 Outcome boxes at 14-88 words, median 25.5, ALL over
    // rule 33's six-word cap, and left the decision open. A component that
    // silently trimmed would make the divergence invisible instead of
    // settleable, and the measurement is what makes it settleable.
    const long = "A ".repeat(88).trim();
    expect(renderToStaticMarkup(<OutcomeCard tone="success">{long}</OutcomeCard>)).toContain(long);
  });

  it("a finished run is a note, never an alert — on every tone, danger included", () => {
    for (const tone of ["success", "danger", "muted"] as const) {
      const html = renderToStaticMarkup(<OutcomeCard tone={tone}>x</OutcomeCard>);
      expect(html).toContain('role="note"');
      expect(html).not.toContain('role="alert"');
    }
  });
});
