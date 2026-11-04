// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-NOT-10537 — both "Send test" results said *"Nothing leaves the
//          building yet — no … provider is connected"* while email sends
//          through the utility's Custom SMTP connector.
// Ruling:  PO 2026-10-22, *"Each channel tells the clerk the truth about
//          itself, in one short line."* (decision log, NOT-SENT-SWEEP entry)
// Rules:   B14 rule 33 (a fact is six words at most) · rule 31 (no database id
//          on screen — an in-app address is a user id)
// ───────────────────────────────────────────────────────
import type { ChannelLine } from "../../api/endpoints";

type Translator = (key: string, vars?: Record<string, unknown>) => string;

/** The part of either test result this sentence reads. */
export interface TestResultFacts {
  channel: string;
  recipient_address: string | null;
  will_be_delivered: boolean;
  channel_line?: ChannelLine | null;
}

/** The channel's reason, one short sentence, per state of its line. A state
 *  with no sentence here (`sending`, `waitingPrintVendor`) adds nothing — never
 *  a guess. */
const WHY_KEY: Partial<Record<ChannelLine["state"], string>> = {
  off: "notifications.test.why.off",
  noMailServer: "notifications.test.why.noMailServer",
  notWorking: "notifications.test.why.notWorking",
  noTextProvider: "notifications.test.why.noTextProvider",
  waitingTextProvider: "notifications.test.why.waitingTextProvider",
};

/**
 * What a queued test message will do, from the server's own answer.
 *
 * `will_be_delivered` is the dispatcher's verdict; `channel_line` is the
 * Channel status card's line for the same channel, so this screen and that card
 * cannot disagree. Worked: email via Custom SMTP → *"On its way to
 * ops@springfieldwater.example."*; email with no connector → *"Queued for
 * ops@springfieldwater.example. Waiting for a mail server."*
 */
export function testResultSentence(result: TestResultFacts, t: Translator): string {
  // In-app is delivered by this product itself (BR-NOT-019), and its address is
  // a user id, which is never drawn.
  if (result.channel === "in_app") return t("notifications.test.inApp");
  const address = result.recipient_address ?? "";
  if (result.will_be_delivered) return t("notifications.test.onItsWay", { address });
  const queued = t("notifications.test.queued", { address });
  const line = result.channel_line ?? null;
  const why = line !== null ? WHY_KEY[line.state] : undefined;
  if (why === undefined) return queued;
  return `${queued} ${t(why, { provider: line?.provider ?? "" })}`;
}
