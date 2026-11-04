// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-AUD-010 — an automated action can say what it is (`CR-075` task
//          `L1`).   Screens: S61 · S21's History tab (the account history the
//          worked scenario names)
// Rules:   BR-AUD-019 (named and versioned; no user id) · BR-RBS-015 (the
//          runbook is the audit actor; it never borrows a user identity) ·
//          BR-AUD-003 (an UNNAMED null actor is still a system job) ·
//          BR-AUD-010 (a per-entity Audit tab is a WINDOW into the same store,
//          so both surfaces must read alike) · B14 rule 31 (no database id is
//          ever the visible value of a field) · B14 rule 35 (a catalogue is
//          written in its own language)
// Tests:   TC-RBS-12's screen half + US-AUD-010 TC-4
// ───────────────────────────────────────────────────────
//
// ⚠ THE ASSERTION THAT MATTERS IS THE `not.toContain` ONE, AND IT IS WHY THIS
// FILE MOUNTS A REAL TABLE INSTEAD OF CALLING `actorLabel` ALONE. The failure
// this story removes is not "the name is missing" — it is "somebody ELSE'S name
// is there". A test that only checked the happy string would pass just as
// happily over a cell that also printed Alex Reed beside it, or a raw uuid in a
// title attribute. So the automation row is rendered in a table that ALSO holds
// a person's row, and the automation cell is asserted to contain neither the
// person's name nor any id.

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { AuditRow } from "@/api/endpoints";
import { actorLabel } from "./AuditLogPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The worked scenario, exactly as `GET /audit-log` now serves it. */
const RUNBOOK_ROW: AuditRow = {
  id: "a-fee",
  created_at: "2026-08-09T03:14:00Z",
  actor: { kind: "runbook", name: "Returned payments", version: "4" },
  action: "payment.fee_applied",
  entity_type: "payment",
  entity_id: "22222222-2222-2222-2222-222222222222",
  summary: "fee: — → 25.0000",
  source: null,
};

/** A person, and an UNNAMED system job — both must read exactly as before. */
const PERSON_ROW: AuditRow = {
  ...RUNBOOK_ROW,
  id: "a-person",
  actor: { id: "01a062a7-9f7d-73e6-96e4-700cba033c73", name: "Alex Reed" },
  action: "billing_settings.updated",
};
const UNNAMED_ROW: AuditRow = { ...RUNBOOK_ROW, id: "a-job", actor: null, action: "period.closed" };

/** An automation with no version — the bare name, never an invented "version 1". */
const UNVERSIONED_ROW: AuditRow = {
  ...RUNBOOK_ROW,
  id: "a-import",
  actor: { kind: "import", name: "Nightly meter file", version: null },
};

describe("US-AUD-010 — the actor a clerk reads when a computer acted", () => {
  it("TC-RBS-12: the account history names the runbook AND its version", () => {
    expect(actorLabel(RUNBOOK_ROW, t)).toBe("Returned payments, version 4");
  });

  it("BR-RBS-015: the automation's cell carries no person and no id", () => {
    // The history a clerk actually opens holds both kinds of row at once —
    // which is the only way to assert that the automation did not take the
    // person's name with it.
    render(
      <table>
        <tbody>
          {[RUNBOOK_ROW, PERSON_ROW, UNNAMED_ROW].map((row) => (
            <tr key={row.id} data-testid={`row-${row.id}`}>
              <td>{actorLabel(row, t)}</td>
            </tr>
          ))}
        </tbody>
      </table>,
    );

    const automation = within(screen.getByTestId("row-a-fee"));
    expect(automation.getByText("Returned payments, version 4")).toBeTruthy();

    const cell = screen.getByTestId("row-a-fee").textContent ?? "";
    // The harm, named: a real person against 43 fees they never applied.
    expect(cell).not.toContain("Alex Reed");
    // B14 rule 31 — and for a named automation there is no user id on the row
    // at all, so a uuid appearing here could only have been invented.
    expect(cell).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/i);
    // And it is not the blank either: "System job" is what it used to read.
    expect(cell).not.toContain("System job");
  });

  it("US-AUD-010 TC-4: a person and an unnamed system job read exactly as before", () => {
    expect(actorLabel(PERSON_ROW, t)).toBe("Alex Reed");
    expect(actorLabel(UNNAMED_ROW, t)).toBe("System job");
  });

  it("an automation with no version draws its bare name, never an invented one", () => {
    expect(actorLabel(UNVERSIONED_ROW, t)).toBe("Nightly meter file");
    expect(actorLabel(UNVERSIONED_ROW, t)).not.toContain("version");
  });

  it("B14 rule 35: the sentence is composed here, so the catalogue can translate it", () => {
    // The proof that the version is not glued on in English: switching the
    // catalogue changes the SENTENCE while the runbook's own name — tenant
    // data, not copy — stays put. If the server had stored "Returned payments,
    // version 4" this assertion could not be written at all.
    const de = i18n.getFixedT("de");
    const label = actorLabel(RUNBOOK_ROW, (key, params) => de(key, params) as string);
    expect(label).toBe("Returned payments, Version 4");
  });
});
