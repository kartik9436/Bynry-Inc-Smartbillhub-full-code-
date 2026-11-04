// ── Trace ──────────────────────────────────────────────
// Change:  CR-190-BRC10 lane AGREEMENT — PO 2026-10-22, answer 1: *"7 Days"*,
//          a utility SETTING (*"don't do any hardcoding"*). Settings →
//          Customer portal → Overview.
// Rules:   B14 rule 43 (its own component) · rule 33 (a label, no rationale) ·
//          BR-SHL-025 (read-only roles see it and are told why)
// Tests:   src/features/tenancy/SettingsAgreementLinkDays.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { TextField } from "@/components/FormModal";

/** How many days an emailed link stays valid — one whole number. The
 *  agreement link's by default; DEF-BIL-10531 reuses it for the bill email's
 *  link by naming its own setting, id and label. */
export function AgreementLinkDaysField(props: {
  days: number;
  readOnly: boolean;
  readOnlyReason: string;
  saving: boolean;
  onSave: (days: number) => void;
  setting?: string;
  fieldId?: string;
  labelKey?: string;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState(String(props.days));
  useEffect(() => setValue(String(props.days)), [props.days]);
  const parsed = /^\d+$/.test(value.trim()) ? Number(value.trim()) : null;
  const changed = parsed !== null && parsed !== props.days;
  return (
    <div
      className="flex flex-wrap items-end gap-3"
      data-setting={props.setting ?? "agreement_link_valid_days"}
    >
      <div className="w-40">
        <TextField
          id={props.fieldId ?? "agreement-link-days"}
          label={t(props.labelKey ?? "settings.portal.agreementLinkDays")}
          value={value}
          onChange={setValue}
          numeric
          readOnly={props.readOnly}
          help={props.readOnly ? props.readOnlyReason : undefined}
        />
      </div>
      {props.readOnly ? null : (
        <Button
          variant="secondary"
          disabled={!changed || props.saving}
          onClick={() => {
            if (parsed !== null) props.onSave(parsed);
          }}
        >
          {t("settings.portal.save")}
        </Button>
      )}
    </div>
  );
}
