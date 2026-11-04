// ── Trace ──────────────────────────────────────────────
// Rule:     BR-CUS-1093 (PO 2026-09-23 — a MASTER account takes its utility
//           services from its PREMISES) · BR-CUS-1010 (a master hangs off the
//           ADDRESS and names no unit)
// Defect:   DEF-CUS-6295 — a correct absence that never says why. The Product
//           Owner read an empty Services cell on a master account as a broken
//           screen and reported it as a bug; the product was behaving exactly
//           as three signed rules required and said nothing on screen about it.
// Rules:    B14 rule 32 (a stated absence) · rule 33 (a FACT is ≤ 6 words and
//           RATIONALE is ZERO words on screen) · hard-won law 2 (built is not
//           wired — `kind` is a REQUIRED prop, never an optional one nothing
//           passes)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS FILE CAN AND CANNOT SEE
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS HARNESS DOES NO LAYOUT**, so it cannot see a cell that wraps, a row
// that grew taller or a sentence clipped by its column. It asserts the WORDS
// and which row gets them, which is the whole of `DEF-CUS-6295`: the cell was
// not mis-laid-out, it was silent. The rendered proof is a browser —
// `10-scripts/def_cus_6295_master_services_walkthrough.mjs` opens the Accounts
// register on a real tenant and reads the master account's row.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A component that printed the new
// sentence on EVERY empty cell would satisfy the master case and be wrong for
// every ordinary account, so tc2 asserts the ordinary row still reads the short
// form. And a component that printed it whenever `services` was empty
// regardless of `kind` would pass both if the fixtures happened to line up, so
// tc3 renders a master WITH services and asserts neither sentence appears.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ACCOUNT_KIND_MASTER } from "@/api/endpoints";

import { AccountServiceChips } from "./accountsListCells";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function markup(services: readonly string[], kind: string | null): string {
  return renderToStaticMarkup(
    <AccountServiceChips services={services} kind={kind} t={t} />,
  );
}

describe("DEF-CUS-6295 — an empty Services cell names the address on a master", () => {
  it("tc1: a MASTER account with no services says where to look", () => {
    const html = markup([], ACCOUNT_KIND_MASTER);

    // The FACT, five words. `BR-CUS-1093` makes the row's list a read of
    // `premises.services_available`, so an empty cell is a statement about the
    // BUILDING — which is the one thing a clerk can act on.
    expect(html).toContain("No services at this address");
    // …and NOT the bare form, which is what the PO reported as a defect.
    expect(html).not.toContain(">No services<");
  });

  it("tc2: an ORDINARY account with no services keeps the short form", () => {
    const html = markup([], "regular");

    expect(html).toContain("No services");
    // B14 rule 33 — an ordinary account's services come from its UNIT
    // (`BR-CUS-672`), so naming the address would send a clerk to the wrong
    // screen. The sentence is scoped to the rule that produced the emptiness.
    expect(html).not.toContain("at this address");
  });

  it("tc3: a MASTER account WITH services draws chips and no sentence at all", () => {
    const html = markup(["water"], ACCOUNT_KIND_MASTER);

    expect(html).not.toContain("No services");
    expect(html).not.toContain("at this address");
    // The chip is there, named for a screen reader — `rating.service.water`.
    expect(html).toContain(i18n.t("rating.service.water"));
  });

  it("tc4: the sentence is a FACT at B14 rule 33's cap — six words or fewer", () => {
    // Counted here rather than trusted, because the cap is the only thing
    // stopping this cell from growing into the explanation rule 33 forbids.
    const sentence = i18n.t("customers.accounts.services.noneAtAddress");
    expect(sentence.split(/\s+/).filter(Boolean).length).toBeLessThanOrEqual(6);
    // RATIONALE IS ZERO WORDS ON SCREEN: no rule id, no internal code, and no
    // sentence explaining why a master account works this way (rule 31 / 33).
    expect(sentence).not.toMatch(/BR-|OQ-|DEF-|premises\.|master account/i);
  });
});
