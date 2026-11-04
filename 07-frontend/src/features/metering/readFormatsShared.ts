// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11: one way the read-format screens
//           turn a server refusal into the sentence a clerk reads.
// Rules:    BR-SHL-037 (one envelope) · BR-SHL-025 (a refusal is said, never
//           swallowed) · B14 rule 31 (the rule id rides `data-br-ref`, never
//           the sentence)
// Tests:    src/features/metering/readFormats.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY NOT `refusalOf` ALONE.** The read-format service refuses a question
// edit with ONE envelope key — `metering.readFormats.invalid`, *"Check the
// highlighted fields."* — and puts the real reason in a FIELD error
// (`question_in_use`, `show_if_earlier`). Inside a form that highlights a
// field; on a row action (delete, move up) there is no field to highlight, so
// the generic sentence would be the whole message and the reason would be lost.
// Here the first field error's own sentence is shown instead.
//
// And a retire refused for being in use carries the three counts as params
// (`read_formats.retire`): the sentence names them, so the clerk knows which
// pointers to move — *"replace it later"* is moving a pointer first.
import { isApiError } from "@/api/client";
import { refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal, Translator } from "@/features/tenancy/settingsShared";

export const INVALID_KEY = "metering.readFormats.invalid";
export const IN_USE_KEY = "metering.readFormats.in_use";

export function readFormatRefusal(error: unknown, t: Translator): Refusal {
  if (isApiError(error)) {
    const first = error.fieldErrors[0];
    if (error.messageKey === INVALID_KEY && first !== undefined) {
      return { message: t(first.message_key, first.params ?? {}), brRef: error.brRef };
    }
    if (error.messageKey === IN_USE_KEY) {
      const params = error.params as { routes?: number; cycles?: number; services?: number };
      return {
        message: `${t(IN_USE_KEY)} ${t("settings.readFormats.usedBy", {
          routes: params.routes ?? 0,
          cycles: params.cycles ?? 0,
          services: params.services ?? 0,
        })}`,
        brRef: error.brRef,
      };
    }
  }
  return refusalOf(error, t);
}
