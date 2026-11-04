// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F2 — Channel / Language / Customers (`02`, `05`, `16`)
// Rules:    PO rulings A3 A (a variant is channel × language × customer
//           category) · A4 B (only the utility's switched-on languages) · B
//           (a message goes in the customer's preferred language, falling back
//           to the utility's) · B14 rules 8 · 31 · 33 · 43 · 44
// ───────────────────────────────────────────────────────
// THE THREE PICKERS UNDER THE TITLE, AND THE LANGUAGE RULE LINE UNDER THEM.
//
// A variant is three choices, and these are those three choices — never a
// list of variant NAMES. They replace the variant TAB strip (`CR-199-BRC10`
// §6 W2) and the sibling-surface switcher (W3):
//
//   · **Channel** opens the same notice's other channel (the email and the
//     text of *Bill ready* are two templates with two bodies, so this picker
//     NAVIGATES — it is the old surface switcher, drawn as the drawing draws
//     it);
//   · **Language** and **Customers** pick a variant of THIS template.
//
// ⚠ **NO OPTION IS EVER A DATABASE ID (B14 rule 31).** The values are a
// template code (navigation only, never shown), a language code and a customer
// category; the LABELS are words.
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { SelectField } from "@/components/FormModal";
import { StatusPill } from "@/components/StatusPill";

export interface PickerOption {
  value: string;
  label: string;
}

export function TemplateVariantPickers(props: {
  channels: readonly PickerOption[];
  channel: string;
  onChannel: (value: string) => void;
  languages: readonly PickerOption[];
  language: string;
  onLanguage: (value: string) => void;
  customers: readonly PickerOption[];
  customer: string;
  onCustomer: (value: string) => void;
  /** The language this variant is read in, and how many customers read it —
   *  the server's figure (TPL-SRV-LANG); absent draws no chip. */
  readers: { label: string; count: number } | null;
  /** The utility's own language — where a customer whose language is not
   *  written yet is sent. Absent leaves that half of the line unsaid. */
  fallbackLanguage: string | null;
}) {
  const { t } = useTranslation();
  const base = useId();
  return (
    <div className="flex flex-col gap-3" data-testid="workspace-pickers">
      <div className="flex flex-wrap items-start gap-4">
        <div className="w-48 max-sm:w-full" data-testid="picker-channel">
          <SelectField
            id={`${base}-channel`}
            label={t("templates.workspace.channel")}
            value={props.channel}
            onChange={props.onChannel}
            options={[...props.channels]}
            disabled={props.channels.length < 2}
            /* DEF-NOT-10673 — no help line. The 2026-09-08 sentence ("Each is
               edited and published separately…") explained WHY the channels
               are separate, which is rationale and B14 rule 33 puts at zero
               words on screen; the redesign the PO approved (images 02, 05)
               draws the Channel picker with nothing under it. The fact the
               sentence carried is the picker itself: one channel at a time. */
          />
        </div>
        <div className="w-48 max-sm:w-full" data-testid="picker-language">
          <SelectField
            id={`${base}-language`}
            label={t("templates.workspace.language")}
            value={props.language}
            onChange={props.onLanguage}
            options={[...props.languages]}
          />
        </div>
        <div className="w-48 max-sm:w-full" data-testid="picker-customers">
          <SelectField
            id={`${base}-customers`}
            label={t("templates.workspace.customers")}
            value={props.customer}
            onChange={props.onCustomer}
            options={[...props.customers]}
          />
        </div>
      </div>
      {/* PO ruling B (2026-10-29): the rule a customer's message follows, in
          two short facts, and the count of who reads this language. */}
      <p
        className="m-0 flex max-w-measure flex-wrap items-center gap-2 text-sm"
        data-desc
        data-testid="language-rule"
      >
        <span>{t("templates.workspace.languageRule")}</span>
        {props.fallbackLanguage !== null && (
          <span>
            {t("templates.workspace.languageFallback", { language: props.fallbackLanguage })}
          </span>
        )}
        {props.readers !== null && (
          <span data-testid="language-readers">
            <StatusPill tone="info">
              {t("templates.workspace.languageReaders", {
                language: props.readers.label,
                count: props.readers.count,
                formatted: props.readers.count.toLocaleString(),
              })}
            </StatusPill>
          </span>
        )}
      </p>
    </div>
  );
}
