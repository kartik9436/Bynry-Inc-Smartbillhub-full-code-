// DEF-CUS-9256 — the owner's date of birth typed on New Connection step 1 reaches
// the customer record. Found by the end-to-end walk: S4's Maya Whitlock was
// committed with no birth date, so S5 typing her name and date of birth was told
// "Customer not found" instead of being offered her as a possible match.
import { describe, expect, it } from "vitest";

import { emptyDraft, ownerIdentityPayload } from "./newConnectDraft";

const maya = () => ({
  ...emptyDraft().owner,
  name: "Maya Whitlock",
  partyKind: "person",
  dateOfBirth: "1979-06-14",
  ssn: "523-41-7788",
});

describe("ownerIdentityPayload", () => {
  it("sends a person's date of birth with the rest of their evidence", () => {
    expect(ownerIdentityPayload(maya())).toEqual({
      party_kind: "person",
      identity: { date_of_birth: "1979-06-14", ssn: "523-41-7788" },
    });
  });

  it("never sends a date of birth for a company (the server refuses it by name)", () => {
    const company = { ...maya(), partyKind: "company", taxId: "74-3318620" };
    expect(ownerIdentityPayload(company)).toEqual({
      party_kind: "company",
      identity: { tax_id: "74-3318620" },
    });
  });

  it("sends nothing it was not given", () => {
    expect(ownerIdentityPayload({ ...maya(), dateOfBirth: "", ssn: "" })).toEqual({
      party_kind: "person",
    });
  });
});
