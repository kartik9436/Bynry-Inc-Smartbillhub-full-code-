// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — P3.27 / ruling 31 (*"here crews
//           and contracteos wireframs are missing"*). Built from the IMAGE
//           `05-prototype/work-backoffice-2026-10-04/images/29-crews-add-a-crew.png`.
// Server:   `POST /work/crews {kind: crew, name, role_label, shift_start,
//           shift_end}` → `PUT /work/crews/{id}/skills` (P3.52) → `PATCH
//           /work/technicians/{slug} {crew_id}` per member (P3.44), all lane
//           SRV-3 `2.502.0`.
// Rules:    B14 rule 38/44 (our kit) · rule 9 (chips + an add control) · 33 ·
//           rule 43 (`ShiftField`, `ConsequenceBox`)
// Tests:    src/features/work/crewsLane.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THREE WRITES, AND A FAILED SECOND OR THIRD ONE NEVER MAKES A SECOND
// CREW.** The server has no single write for a crew with its skills and
// members, so the crew is created first and its id is HELD by this form: a
// press of *Add crew* after a refused skill or member write resumes from the
// step that failed instead of creating *Field crew C* twice. (Reported to the
// coordinator as a server need: one write would make the three atomic.)
//
// ⚠ **A SKILL IS SENT WITHOUT A PROFICIENCY.** Image 29 draws none for a crew,
// the server stores its default (*trained*), and the job advice reads only
// whether the skill is held (`work/advice.py`).
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import { ShiftField, shiftPayload } from "./ShiftField";
import type { ShiftValue } from "./ShiftField";
import { createCrew, listCrewsView, moveTechnician, setCrewSkills } from "./crewsEndpoints";
import type { TechnicianListRow } from "./crewsEndpoints";

const crewSchema = z.object({ name: z.string().trim().min(1).max(120) });

/** The lookup list a crew's and a contractor's skills are chosen from. */
export function useSkillCatalogue(client: ApiClient) {
  const query = useQuery({
    queryKey: ["lookups", "work_skills", "picker"],
    queryFn: () => getLookupEntries("work_skills", { per: 200 }, client),
    retry: false,
  });
  return (query.data?.results ?? [])
    .filter((row) => row.active)
    .map((row) => ({ value: row.id, label: row.name }));
}

export function AddCrewModal(props: { client: ApiClient; onClose: () => void; onAdded: () => void }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [does, setDoes] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [shift, setShift] = useState<ShiftValue>({ start: "", end: "" });
  const created = useRef<string | null>(null);
  const moved = useRef<Set<string>>(new Set());
  const skillsSet = useRef(false);

  const peopleQuery = useQuery({
    queryKey: ["work", "crews", "member-choices"],
    queryFn: () => listCrewsView<TechnicianListRow>("technicians", { per: 200 }, props.client),
    retry: false,
  });
  const people = peopleQuery.data?.results ?? [];
  const skillOptions = useSkillCatalogue(props.client);

  const movers = people.filter((row) => members.includes(row.id) && row.crew !== null);
  const shownName = name.trim() === "" ? t("work.crews.crew.thisCrew") : name.trim();

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      if (created.current === null) {
        const crew = await createCrew(
          { kind: "crew", name: name.trim(), role_label: does.trim(), ...shiftPayload(shift) },
          props.client,
        );
        created.current = crew.id;
      }
      const crewId = created.current;
      if (skills.length > 0 && !skillsSet.current) {
        await setCrewSkills(crewId, skills.map((skill_id) => ({ skill_id })), props.client);
        skillsSet.current = true;
      }
      for (const row of people.filter((one) => members.includes(one.id))) {
        if (moved.current.has(row.id)) continue;
        await moveTechnician(row.slug, crewId, props.client);
        moved.current.add(row.id);
      }
      props.onAdded();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  const leaving = movers.map((row) => t("work.crews.crew.leaves", { name: row.name, crew: row.crew?.name ?? "" }));

  return (
    <FormModal
      title={t("work.crews.crew.title")}
      schema={crewSchema}
      values={{ name }}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t("work.crews.crew.submit")}
    >
      <TextField id="name" label={t("work.crews.form.name")} value={name} onChange={setName} required />
      <TextField
        id="role_label"
        label={t("work.crews.col.does")}
        value={does}
        onChange={setDoes}
        help={t("work.crews.shownOnList")}
      />
      <ChipMultiSelect
        showLabel
        label={t("work.crews.col.members")}
        testKey="crew-members"
        options={people.map((row) => ({ value: row.id, label: row.name }))}
        selected={members}
        onChange={setMembers}
        addLabel={t("work.crews.crew.addMember")}
        emptyLabel={t("work.crews.crew.noMembers")}
        removeLabel={t("work.crews.form.remove")}
        help={t("work.crews.crew.membersHelp")}
      />
      <ChipMultiSelect
        showLabel
        label={t("work.crews.col.skills")}
        testKey="crew-skills"
        options={skillOptions}
        selected={skills}
        onChange={setSkills}
        addLabel={t("work.crews.form.addSkill")}
        emptyLabel={t("work.crews.form.noSkills")}
        removeLabel={t("work.crews.form.remove")}
        help={t("work.crews.form.skillsHelp")}
      />
      <ShiftField id="crew-shift" label={t("work.crews.col.shift")} value={shift} onChange={setShift} />
      <ConsequenceBox
        tone="publish"
        tag={t("work.crews.effect")}
        title={t("work.crews.crew.effectTitle", { name: shownName })}
        body={[t("work.crews.crew.effectBody"), ...leaving].join(" ")}
        data-consequence="add-crew"
      />
    </FormModal>
  );
}

export default AddCrewModal;
