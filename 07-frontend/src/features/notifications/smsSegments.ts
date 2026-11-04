// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave E · E2 — *"a phone-sized bubble with a live character
//          count and segment counter. ⚠ Passing 160 characters splits the
//          message into two segments and doubles the per-message cost — on a
//          2,000-account run that is real money, so the counter and the '4
//          characters left' warning belong BESIDE THE WORDS BEING TYPED, not in
//          a validation message after saving."*
// Screens: SET-10, the SMS designers (S103–S106)
// Rules:   BR-SHL-025 (a control renders disabled WITH its reason) · the prime
//          directive (never resolve an open question by choosing a value)
// ───────────────────────────────────────────────────────
// WHAT ONE SMS COSTS, COUNTED FROM THE ONE NUMBER THE SERVER SENDS.
//
// ── THE SEGMENT SIZE IS SERVED; THE CONCATENATION SIZE IS NOT ─────────────
// `templates_api.py` serves `sms_character_counter: 160` and its comment says
// exactly what that number is for:
//
//     "Served rather than hardcoded in the client so the counter and ANY
//      FUTURE SEGMENT RULE have one source. It is a COUNTER, not a limit:
//      nothing here truncates or refuses a longer body, because no signed rule
//      says a 161-character SMS is invalid — A19 r8 records the four SMS
//      bodies' lengths (99–138 chars) and states no cap."
//
// **"any future segment rule" is the server saying it does not have one yet**,
// and it is right: `160` is the only figure on the wire.
//
// ⚠ **SO THIS FILE DOES NOT WRITE 153, AND THE OMISSION IS DELIBERATE.** In
// GSM-7, a message split across several parts spends six bytes per part on a
// concatenation header, so each part carries **153** characters and not 160 —
// which means the real boundaries are 160, 306, 459, and a body of 320
// characters is THREE parts, not two. That is a true fact about the GSM
// standard and it is **not a signed rule of this product**: no B-document, no
// business rule and no PO ruling states it, nothing on the wire carries it, and
// there is no SMS provider adapter in this release for it to be true of yet
// (CR-048 step 3 puts every provider adapter out of scope in as many words).
// Writing 153 here would be resolving an open question by choosing a value.
//
// **What IS ruled is the one thing the counter has to get right**, and CR-048
// E2 states it: *"passing 160 characters splits the message into two segments
// and doubles the per-message cost."* So the count is `ceil(length / 160)` —
// one segment to 160, two above it — which is the requirement's own arithmetic
// and needs no second figure.
//
// **The consequence, stated so nobody has to rediscover it:** on a body longer
// than about 306 characters this counter is OPTIMISTIC by one part or more. It
// is honest at the boundary that matters — CR-048 names 160 and the four seeded
// SMS bodies are 99–138 characters — and it will need the concatenation figure
// before anything actually bills per part. The lane that owns
// `12-governance/01-open-questions.md` should carry that as a question; it is
// not numbered here, because an id written in code that no register row answers
// to is the dangling citation DEF-524 records.

/** What the composer prints beside the words being typed. */
export interface SmsCost {
  /** Characters in the body as typed. */
  length: number;
  /** How many messages this will be sent as — and therefore what it costs. */
  segments: number;
  /** How many more characters fit before the NEXT segment starts. Never
   *  negative, and `0` means the very next keystroke adds one. */
  remaining: number;
  /** True once the body costs more than one message to send. The composer
   *  paints this tier; it never refuses the body, because no signed rule says
   *  a 161-character SMS is invalid. */
  overSegment: boolean;
}

/**
 * @param length      characters in the body — the RENDERED length where a
 *                    preview is available, because merge tokens change it and
 *                    `{balance}` is four characters on screen and eight in the
 *                    message that goes out.
 * @param segmentSize the server's `sms_character_counter`. Passed in rather
 *                    than read from a constant so there is one source, which
 *                    is why the server sends it.
 */
export function smsCost(length: number, segmentSize: number): SmsCost {
  // A segment size of zero or less would divide by nothing. It cannot arrive
  // from this server, and answering "one segment, nothing left" is the only
  // statement that is not a lie if it ever does.
  if (segmentSize <= 0) {
    return { length, segments: 1, remaining: 0, overSegment: false };
  }
  // An EMPTY body is one segment and not zero: nothing has been written yet,
  // and "0 messages" would read as "this costs nothing to send" rather than as
  // "there is nothing here".
  const segments = length === 0 ? 1 : Math.ceil(length / segmentSize);
  return {
    length,
    segments,
    remaining: segments * segmentSize - length,
    overSegment: segments > 1,
  };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-048 wave E task E2 (12-governance/11-change-requests.md CR-048
//         step 5, WAVE E) · 06-backend/apps/notifications/templates_api.py
//         (`sms_character_counter`) · A19 r8 SMS table (the four seeded bodies,
//         99–138 chars, no cap stated)
// generated: 2026-08-30 by the CR-048 wave E designer lane
// gates: tsc✔ · vitest smsSegments.test.ts, RED-proved against the screen's
//        previous counter (a character count with no segment and no remainder)
// exceptions: (1) GSM-7's 153-CHARACTER CONCATENATED PART IS NOT WRITTEN HERE.
//         It is a fact about the standard and not a signed rule of this
//         product, nothing serves it, and there is no provider adapter in this
//         release. The counter is therefore optimistic beyond ~306 characters
//         and says so in the module note.
//         (2) NOTHING TRUNCATES AND NOTHING REFUSES — the tier is a warning
//         about COST, because no signed rule makes a long SMS invalid.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
