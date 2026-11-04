// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 P3.51 — no library English reaches a clerk.
// Rules:    BR-SHL-017 (the field kit's inline validation) · B14 rule 33 (a
//           refusal is a short sentence a clerk can act on) · rule 35 (each
//           catalogue in its own words — the two keys used here already exist
//           in all eleven).
// Tests:    this file
// ───────────────────────────────────────────────────────
/**
 * A schema rule written WITHOUT a message of its own must still put a
 * catalogue sentence under its field, never zod's English.
 *
 * Measured by the blueprint (P3.51): 14 front-end files hold at least one rule
 * with no message, and `collectFormErrors` copied `issue.message` straight onto
 * the screen — *String must contain at least 1 character(s)*, *Required*,
 * *Invalid*, *Expected number, received nan*. The fix is ONE fallback in the
 * kit; a rule that names its own message keeps it.
 */
import { afterEach, describe, expect, it } from "vitest";
import { z } from "zod";

import i18n from "@/i18n";

import { collectFormErrors } from "./FormModal";

const LIBRARY_WORDS = /String must|Required$|^Invalid|Expected |received|Number must|character\(s\)/;

afterEach(async () => {
  await i18n.changeLanguage("en");
});

describe("P3.51 — a rule with no message of its own speaks the catalogue", () => {
  const schema = z.object({
    name: z.string().min(1),
    unit: z.enum(["each", "foot"]),
    cost: z.number(),
    count: z.number().int().min(1).max(99),
    code: z.string().regex(/^[A-Z]+$/),
    labelled: z.string().min(1, "Name the part."),
  });
  const values = { name: "", cost: Number.NaN, count: 500, code: "abc", labelled: "" };

  it("an empty required field reads the catalogue's required sentence, a value out of range its range sentence", () => {
    const { errors } = collectFormErrors(schema, values);
    expect(errors.name).toBe(i18n.t("errors.val-001"));
    expect(errors.unit).toBe(i18n.t("errors.val-001"));
    expect(errors.count).toBe(i18n.t("errors.val-003"));
    expect(errors.cost).toBe(i18n.t("errors.val-002"));
    expect(errors.code).toBe(i18n.t("errors.val-002"));
  });

  it("no message under any field is the library's own English", () => {
    const { errors } = collectFormErrors(schema, values);
    for (const [field, message] of Object.entries(errors)) {
      expect(message, field).not.toMatch(LIBRARY_WORDS);
    }
  });

  it("a rule that names its own message keeps it", () => {
    const { errors } = collectFormErrors(schema, values);
    expect(errors.labelled).toBe("Name the part.");
  });

  it("in another language the fallback is that catalogue's own sentence", async () => {
    await i18n.changeLanguage("de");
    const { errors } = collectFormErrors(schema, values);
    expect(errors.name).toBe("Dieses Feld ist erforderlich.");
  });
});
