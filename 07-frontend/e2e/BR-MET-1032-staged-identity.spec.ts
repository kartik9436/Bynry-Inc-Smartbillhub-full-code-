// ── Trace ──────────────────────────────────────────────
// Change:  BR-MET-1032 — an uploaded spreadsheet stops keeping Social Security
//          numbers in plain text while it waits to be committed, and the
//          checking screen stops showing them back.
// Screens: WFL-01.premises stages 1–3 · /{tenant}/premises/import
// Rules:   BR-MET-1032 · BR-CUS-092(c) · BR-MET-1030 · PO ruling 2026-09-01
//          (*"in spreadsheet we will porvide entire SSN number if required"*)
// ───────────────────────────────────────────────────────
//
// **WHY A BROWSER AND NOT ONLY THE VITEST SUITE.** Hard-won law 6: no gate in
// this repo looks at rendered output. The vitest half of this change
// (`RejectListFix.dom.test.tsx`) drives the same clicks against a MOCKED
// client — it proves the component draws what a stubbed server sends. It cannot
// prove the real server sends it, and this whole change is about what the real
// server puts on a real screen.
//
// ⚠ **AND THE FAILURE MODE HERE IS A CHANGE THAT LOOKS LIKE IT WORKED.** The
// one assertion that cannot be satisfied by accident is the negative one: the
// nine digits are nowhere in the rendered page. It is written against
// `page.content()` rather than against a locator for exactly that reason — a
// locator can only look where somebody remembered to point it.
// **PROVED RED FIRST (hard-won law 7), AND NOT BY DELETING AN ASSERTION.** The
// server's `import_identity.display_form` was made to return the operator's own
// value instead of the mask, the Django process was restarted against the same
// live database, and this spec was run again:
//
//     ✘  BR-MET-1032 — the checking screen serves the last four …
//        Error: expect(locator).toHaveAttribute(expected) failed
//        24 × locator resolved to
//             <input value="" type="text" class="input" placeholder="123-45-6789"/>
//           - unexpected value "123-45-6789"
//     1 failed
//
// The sabotage was reverted in the next command and the spec re-run green. The
// mutation was in the SERVER, deliberately: this file's job is to prove that
// the running product does not put the number on the page, so a mutation in
// the component would have proved something weaker.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const IMPORT_PATH = `/${tenant()}/premises/import`;

/** The whole number, and what a clerk must see instead of it. */
const SSN = "123-45-6789";
const MASK = "••••6789";

/**
 * One premises row that WILL be rejected, so the checking step has something
 * to draw. `PREMISE_ID` names a number this utility never issued, which is a
 * tier-2 error under the 2026-08-27 numbering ruling — chosen because it has
 * nothing to do with owners, so a failure here is never ambiguous.
 */
const FILE = [
  "PREMISE_ID,ADDR1,CITY,STATE,ZIP,OWNER,OWNER_KIND,SSN,OWNER ACCOUNT TYPE",
  `P-99999,1 Bluestem Ln,Katy,TX,77494,Rosa Alvarez,person,${SSN},residential`,
  "",
].join("\n");

test.describe("BR-MET-1032 — the checking screen serves the last four", () => {
  // `@app-server` — the census counts these as BROWSER assertions and fails a
  // run that executed none. Untagged, this file would pass while proving
  // nothing about the running product (DEF-057).
  test("a staged Social Security number is drawn as ••••6789 and the whole number is nowhere on the page @app-server", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(IMPORT_PATH);

    await page.locator('input[type="file"]').setInputFiles({
      name: "brazosbend_premises_2026.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(FILE),
    });
    await page.getByRole("button", { name: "Transform →" }).click();
    await expect(page.locator('[data-workflow="runner"]')).toHaveAttribute("data-stage", "2");

    // Stage 1's auto-detect recognises `SSN` as the owner's Social Security
    // number, so the operator confirms the mapping and moves on.
    await page.getByRole("button", { name: "Validate →" }).click();
    await expect(page.locator('[data-workflow="runner"]')).toHaveAttribute("data-stage", "3");

    // The rejected row, with its own cells behind "Fix here…".
    const rejects = page.locator('[data-workflow="rejects"]');
    await expect(rejects).toBeVisible();
    await rejects.getByRole("button", { name: "Fix here…" }).first().click();

    const ssn = page.getByLabel("SSN");
    await expect(ssn).toBeVisible();
    // ⛔ **THE MASK IS THE PLACEHOLDER AND THE BOX IS EMPTY.** A box pre-filled
    // with `••••6789` that somebody appends a digit to sends a number nobody
    // typed, and the server strips the bullets — so `67891` would be filed as
    // a real identifier against a real person.
    await expect(ssn).toHaveValue("");
    await expect(ssn).toHaveAttribute("placeholder", MASK);

    // …and the mask is what a person READS, on the page, not only in an
    // attribute a test had to know to look at.
    expect(await page.content()).toContain(MASK);

    // ⛔ **THE ASSERTION THIS FILE EXISTS FOR.** Nowhere in the rendered page —
    // no cell, no attribute, no inline payload, no React prop serialised into
    // the DOM.
    expect(
      await page.content(),
      "BR-MET-1032: the whole Social Security number is somewhere on the checking screen",
    ).not.toContain(SSN);
    // The undelimited spelling too: `normalise_identifier` treats the two as
    // one identifier, and a screen that printed `123456789` would have leaked
    // exactly the same fact.
    expect(await page.content()).not.toContain("123456789");
  });
});
