// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18) — New Connection's owner birth-date rules,
//           MOVED (unchanged) out of `NewConnectOwnerStep.tsx` so the shared
//           customer form's host (`NewConnectCustomerForm.tsx`) can read them
//           without an import cycle. Re-exported from the step file, so every
//           existing import keeps working.
// Rules:    DEF-CUS-9193 (PO ruling Q4: future or under 18 refused) ·
//           DEF-CUS-9261 (a company has no date of birth) · BR-SHL-023
// ───────────────────────────────────────────────────────
import type { Translator } from "./newConnectShared";

/**
 * ── `DEF-CUS-9193` — PO RULING Q4 (2026-10-02): *"DOB in the future or under
 * 18 refused"*. The catalogue key of what is wrong, or `null`. A blank date is
 * not this rule's business: whether one is needed is the identity rule's.
 *
 * ⚠ **CALENDAR ARITHMETIC ON THE `YYYY-MM-DD` STRING, NEVER A `Date` ROUND
 * TRIP** (`BR-SHL-023`): parsing `2008-10-02` as UTC midnight and reading it in
 * Chicago makes an owner who turns 18 today one day too young.
 */
export function ownerBirthDateProblem(dob: string, today: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dob.trim());
  if (m === null) return null;
  if (dob > today) return "customers.newConnect.step1.dobFuture";
  const [ty, tm, td] = today.split("-").map(Number);
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const age = ty - y - (tm < mo || (tm === mo && td < d) ? 1 : 0);
  return age < 18 ? "customers.newConnect.step1.dobUnder18" : null;
}

const DOB_SENTENCE: Record<string, string> = {
  "customers.newConnect.step1.dobFuture": "Date of birth is in the future.",
  "customers.newConnect.step1.dobUnder18": "Owner must be 18 or over.",
};

/**
 * ⊕ **`DEF-CUS-9261` — a COMPANY has no date of birth.** The box and its
 * under-18 / future checks are a person's, as the SSN is; a company gives Tax
 * ID instead. The Accounts blueprint's company frame (p215) draws none. An
 * unpicked kind still shows it, because the clerk has not said *company*.
 */
export function ownerHasABirthDate(person: { partyKind: string }): boolean {
  return person.partyKind !== "company";
}

/** The sentence for `ownerBirthDateProblem`'s answer, or `null`. */
export function ownerBirthDateSentence(dob: string, today: string, t: Translator): string | null {
  const key = ownerBirthDateProblem(dob, today);
  return key === null ? null : t(key, { defaultValue: DOB_SENTENCE[key] });
}

/** Today in the tenant's time zone as `YYYY-MM-DD` — the day a clerk sees. */
export function todayIn(timeZone: string): string {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date());
  } catch {
    return new Date().toISOString().slice(0, 10);
  }
}
