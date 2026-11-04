// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — ruling 31's *Add a contractor*.
//           Built from the IMAGE
//           `05-prototype/work-backoffice-2026-10-04/images/30-crews-add-a-contractor.png`.
// Server:   `POST /work/crews {kind: contractor, name, phone, email,
//           shift_start, shift_end}` (P3.53) → `PUT /work/crews/{id}/skills`
//           (P3.52), lane SRV-3 `2.502.0`. A malformed email is refused by the
//           server (`work.crew.email_format`) and lands on the Email field.
// Rules:    B14 rule 38/44 (our kit — the drawn radio pair is the kit's
//           one-of-few control) · 33 · rule 43
// Tests:    src/features/work/crewsLane.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **NO PEOPLE, NO LOGINS.** Ruling 36 gives a contractor's people phone-only
// logins, and that is written up in the technician field-app document, which
// is not in hand. Image 30 draws no people field and this form adds none.
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormModal, SegmentedField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import { useSkillCatalogue } from "./AddCrewModal";
import { ShiftField, shiftPayload } from "./ShiftField";
import type { ShiftValue } from "./ShiftField";
import { createCrew, setCrewSkills } from "./crewsEndpoints";

const contractorSchema = z.object({ name: z.string().trim().min(1).max(120) });

export function AddContractorModal(props: { client: ApiClient; onClose: () => void; onAdded: () => void }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [hours, setHours] = useState<"arrangement" | "set">("arrangement");
  const [shift, setShift] = useState<ShiftValue>({ start: "", end: "" });
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const created = useRef<string | null>(null);
  const skillOptions = useSkillCatalogue(props.client);
  const shownName = name.trim() === "" ? t("work.crews.contractor.thisOne") : name.trim();

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      if (created.current === null) {
        const row = await createCrew(
          {
            kind: "contractor",
            name: name.trim(),
            phone: phone.trim(),
            email: email.trim(),
            ...(hours === "set" ? shiftPayload(shift) : { shift_start: null, shift_end: null }),
          },
          props.client,
        );
        created.current = row.id;
      }
      if (skills.length > 0) {
        await setCrewSkills(created.current, skills.map((skill_id) => ({ skill_id })), props.client);
      }
      props.onAdded();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("work.crews.contractor.title")}
      schema={contractorSchema}
      values={{ name }}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t("work.crews.contractor.submit")}
    >
      <TextField id="name" label={t("work.crews.form.name")} value={name} onChange={setName} required />
      <ChipMultiSelect
        showLabel
        label={t("work.crews.col.skills")}
        testKey="contractor-skills"
        options={skillOptions}
        selected={skills}
        onChange={setSkills}
        addLabel={t("work.crews.form.addSkill")}
        emptyLabel={t("work.crews.form.noSkills")}
        removeLabel={t("work.crews.form.remove")}
        help={t("work.crews.form.skillsHelp")}
      />
      <SegmentedField
        id="hours"
        label={t("work.crews.col.hours")}
        value={hours}
        onChange={(next) => setHours(next === "set" ? "set" : "arrangement")}
        options={[
          { value: "arrangement", label: t("work.crews.hours.byArrangement") },
          { value: "set", label: t("work.crews.hours.set") },
        ]}
      />
      {hours === "set" && (
        <ShiftField id="contractor-hours" label={t("work.crews.hours.set")} value={shift} onChange={setShift} />
      )}
      <TextField id="phone" label={t("work.crews.contractor.phone")} value={phone} onChange={setPhone} />
      <TextField id="email" label={t("work.crews.contractor.email")} value={email} onChange={setEmail} />
      <ConsequenceBox
        tone="publish"
        tag={t("work.crews.effect")}
        title={t("work.crews.contractor.effectTitle", { name: shownName })}
        body={t("work.crews.contractor.effectBody")}
        data-consequence="add-contractor"
      />
    </FormModal>
  );
}

export default AddContractorModal;
