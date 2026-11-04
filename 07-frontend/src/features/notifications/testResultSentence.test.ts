// DEF-NOT-10537 — a "Send test" result says what the channel is doing, from
// the server's own answer, and never that nothing leaves the building.
import { describe, expect, it } from "vitest";

import en from "../../i18n/locales/en.json";
import { testResultSentence } from "./testResultSentence";

const catalogue = en as Record<string, string>;
const t = (key: string, vars?: Record<string, unknown>): string => {
  const text = catalogue[key];
  if (text === undefined) throw new Error(`missing key ${key}`);
  return text.replace(/\{\{(\w+)\}\}/g, (_, name: string) => String(vars?.[name] ?? ""));
};

const ADDRESS = "ops@springfieldwater.example";

describe("testResultSentence (DEF-NOT-10537)", () => {
  it("email through a working connector is on its way", () => {
    const sentence = testResultSentence(
      {
        channel: "email",
        recipient_address: ADDRESS,
        will_be_delivered: true,
        channel_line: { channel: "email", state: "sending", provider: "Custom SMTP", host: "smtp.office365.com" },
      },
      t,
    );
    expect(sentence).toBe(`On its way to ${ADDRESS}.`);
  });

  it("email with no connector is queued and waits for a mail server", () => {
    const sentence = testResultSentence(
      {
        channel: "email",
        recipient_address: ADDRESS,
        will_be_delivered: false,
        channel_line: { channel: "email", state: "noMailServer", provider: null, host: null },
      },
      t,
    );
    expect(sentence).toBe(`Queued for ${ADDRESS}. Waiting for a mail server.`);
  });

  it("a switched-off channel and a failing connector say so", () => {
    const base = { channel: "email", recipient_address: ADDRESS, will_be_delivered: false };
    expect(
      testResultSentence({ ...base, channel_line: { channel: "email", state: "off", provider: null, host: null } }, t),
    ).toBe(`Queued for ${ADDRESS}. This channel is not switched on.`);
    expect(
      testResultSentence(
        { ...base, channel_line: { channel: "email", state: "notWorking", provider: "Custom SMTP", host: "smtp.office365.com" } },
        t,
      ),
    ).toBe(`Queued for ${ADDRESS}. Custom SMTP is not working.`);
  });

  it("in-app never prints its address, which is a user id", () => {
    const sentence = testResultSentence(
      { channel: "in_app", recipient_address: "01a165c9-ea6d-73c6", will_be_delivered: true, channel_line: null },
      t,
    );
    expect(sentence).toBe("On its way to your messages.");
  });

  it("no line from the server adds no reason rather than a guess", () => {
    const sentence = testResultSentence(
      { channel: "email", recipient_address: ADDRESS, will_be_delivered: false },
      t,
    );
    expect(sentence).toBe(`Queued for ${ADDRESS}.`);
    expect(sentence).not.toMatch(/leaves the building|provider is connected/);
  });

  it("the retired sentences are gone from the catalogue", () => {
    expect(catalogue["notifications.rules.testQueued"]).toBeUndefined();
    expect(catalogue["templates.detail.testQueued"]).toBeUndefined();
    for (const [key, text] of Object.entries(catalogue)) {
      if (!key.startsWith("notifications.") && !key.startsWith("templates.")) continue;
      expect(`${key}: ${text}`).not.toMatch(/leaves? the building/i);
    }
  });
});
