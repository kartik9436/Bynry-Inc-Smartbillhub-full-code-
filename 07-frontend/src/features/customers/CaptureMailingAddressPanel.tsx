// ── Trace ──────────────────────────────────────────────
// Change:  **`REQ-03` redesign, six steps into four — PO approval 2026-09-29.**
//          *Billing address* became **Mailing address**, and a ticked *Same as
//          the service address* PRINTS that address.
// Change:  ⊕ **LANE CF-1 (2026-10-18) — THE PANEL IS GONE; THIS FILE KEEPS ONE
//          FUNCTION.** The staff request's mailing block is the SHARED
//          `customerForm/MailingAddressBlock` now, on step 1 with the rest of
//          the shared customer form (drawing set `customer-forms-2026-10-18`,
//          image 03; decision log 2026-10-18 *"CUSTOMER DATA AND UI CONSISTENT
//          ACROSS THE CREATE SCREENS"*). What it prints when ticked is still
//          `serviceAddressLines` below, joined into one line.
// Rules:   hard rule 8 · `BR-CUS-070` (what the applicant SAID, never
//          overwritten) · B14 rules 21, 43
// ───────────────────────────────────────────────────────

/**
 * The service address as the clerk has it, in the two lines `02-property`
 * draws — `Mark 234, Unit 12` over `Ottumwa, Iowa 12365`.
 *
 * ⚠ **IT IS BUILT HERE AND NOT READ OFF THE SERVER, AND THAT IS `BR-CUS-070`.**
 * What is printed is what the applicant SAID, plus whatever the register
 * supplied once a premises was picked. A request that has not been saved has no
 * server-side address at all, and this has to be right from the first
 * keystroke.
 *
 * Empty parts drop out rather than leaving a stray comma, so a street line with
 * no town reads as a street line and not as `Mark 234, ,`.
 */
export function serviceAddressLines(parts: {
  street: string;
  unit: string;
  city: string;
  state: string;
  postalCode: string;
  unitWord: string;
}): readonly string[] {
  const street = parts.street.trim();
  const unit = parts.unit.trim();
  const first = [street, unit === "" ? "" : `${parts.unitWord} ${unit}`]
    .filter((part) => part !== "")
    .join(", ");
  const town = [parts.city.trim(), parts.state.trim()].filter((part) => part !== "").join(", ");
  const second = [town, parts.postalCode.trim()].filter((part) => part !== "").join(" ");
  return [first, second].filter((line) => line !== "");
}
