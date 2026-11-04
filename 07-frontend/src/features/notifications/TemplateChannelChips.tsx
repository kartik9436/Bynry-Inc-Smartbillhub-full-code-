// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F1 — the list's channel chips (`01-list.png`)
// Rules:    B14 rules 9 · 43 · 44 · BR-SHL-011 (the choice is URL state)
// ───────────────────────────────────────────────────────
// THE ROW OF CHANNEL CHIPS ABOVE THE TEMPLATE LIST: `All · 6`, `Email · 5`,
// `Text · 3`, `In-app · 1`, `Letter · 1` as the drawing places them.
//
// ⚠ **THE COUNTS ARE THE SERVER'S.** The list is paged on the server (NFR-3),
// so a count worked out from the rows on screen would describe one page and
// not the catalogue. `channels` is a facet the catalogue read serves; when it
// is absent the row renders nothing at all (BR-SHL-010) rather than chips that
// count a page.
import { useTranslation } from "react-i18next";

import { ChipRow, ChipToggle } from "@/components/Chip";

/* The channel KEYS are the server's own (`email` · `sms` · `pdf_print` ·
   `in_app`, `notifications/models.py`), never a list typed out here: a chip
   is drawn for each channel the facet serves, and a key this screen has no
   word for prints its own value (`defaultValue`) rather than nothing. */

export function TemplateChannelChips(props: {
  /** The server's facet: one entry per channel with how many templates use it. */
  channels: readonly { key: string; count: number }[] | undefined;
  /** How many templates the whole catalogue holds under the other filters. */
  allCount: number;
  /** The chosen channel, or `""` for All. */
  active: string;
  onSelect: (channel: string) => void;
}) {
  const { t } = useTranslation();
  if (props.channels === undefined || props.channels.length === 0) {
    return null;
  }
  return (
    <ChipRow
      role="group"
      aria-label={t("templates.list.channels")}
      data-testid="template-channel-chips"
    >
      <ChipToggle
        selected={props.active === ""}
        onClick={() => props.onSelect("")}
        data-testid="template-channel-all"
      >
        {t("templates.list.all")} · {props.allCount}
      </ChipToggle>
      {props.channels.map((channel) => (
        <ChipToggle
          key={channel.key}
          selected={props.active === channel.key}
          onClick={() => props.onSelect(channel.key)}
          data-testid={`template-channel-chip-${channel.key}`}
        >
          {t(`templates.channel.${channel.key}`, { defaultValue: channel.key })} · {channel.count}
        </ChipToggle>
      ))}
    </ChipRow>
  );
}

/** One channel, as the small tag the Channels column and the status line draw. */
export function ChannelTag(props: { channel: string; onOpen?: () => void; testId?: string }) {
  const { t } = useTranslation();
  const label = t(`templates.channel.${props.channel}`, { defaultValue: props.channel });
  const look =
    "inline-flex w-fit items-center bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)] " +
    "px-2 py-px text-xs font-semibold text-text";
  if (props.onOpen === undefined) {
    return (
      <span className={look} data-testid={props.testId}>
        {label}
      </span>
    );
  }
  return (
    <button
      type="button"
      className={`${look} cursor-pointer border-none hover:underline focus-visible:outline-2 focus-visible:outline-accent`}
      onClick={props.onOpen}
      aria-label={t("templates.list.openChannel", { channel: label })}
      title={t("templates.list.openChannel", { channel: label })}
      data-testid={props.testId}
    >
      {label}
    </button>
  );
}
