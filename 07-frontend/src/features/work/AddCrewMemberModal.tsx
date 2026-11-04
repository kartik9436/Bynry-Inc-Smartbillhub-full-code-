// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — P3.43 / ruling 26: *"show the
//           wireframes of how crew members are added. also give an navigation
//           from this page to add crew member."* Built from the IMAGE
//           `05-prototype/work-backoffice-2026-10-04/images/26-crews-add-crew-member.png`.
// Server:   `POST /work/crews/{id}/members {user_id, role_label, shift_start,
//           shift_end, van}` (lane SRV-3, `2.502.0`) when a crew is chosen;
//           `POST /work/technicians` when none is — a crew member on no crew
//           yet is still a technician who can be sent jobs.
// Rules:    `BR-WRK-028` first sentence (a profile beside an EXISTING login —
//           the picker offers only logins, and *Not listed?* sends the person
//           to Users & roles) · B14 rule 38/44 (our form kit builds it) · 33 ·
//           rule 31 (the person is chosen by name; the id is the value only) ·
//           rule 43 (`ShiftField`, `ConsequenceBox` — components, not inline)
// Tests:    src/features/work/crewsLane.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **A CONTRACTOR IS NOT OFFERED AS A CREW HERE.** The server refuses a
// member on a contractor (`work.crew.members_crew_only`) because ruling 36's
// phone-only logins wait for the technician field-app document, so the *Crew*
// list reads the Crews list only and nothing on this form pretends otherwise.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormModal, SearchSelectField, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { InlineLinkTo } from "@/components/Surfaces";
import { useTenantPath } from "@/routing/tenantPath";

import { ShiftField, shiftPayload } from "./ShiftField";
import type { ShiftValue } from "./ShiftField";
import { addCrewMember, createTechnician, listCrewsView, listStaffChoices } from "./crewsEndpoints";
import type { CrewListRow, StaffChoice } from "./crewsEndpoints";

const memberSchema = z.object({ person: z.string().min(1) });

/** The muted fact beside a name (image 26): *Field technician · on Field crew
 *  A* for a login already on a crew — the move the add would make — and
 *  *Field technician · Invited* for one on none (lane SRV-4 serves `crew`). */
export function personDetail(
  row: StaffChoice,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const second =
    row.crew !== null
      ? t("work.crews.member.onCrew", { crew: row.crew.name })
      : t(`work.crews.member.status.${row.status}`);
  return [t(`work.crews.member.role.${row.role_code}`), second].filter((part) => part !== "").join(" · ");
}

export function AddCrewMemberModal(props: {
  client: ApiClient;
  onClose: () => void;
  onAdded: () => void;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const [person, setPerson] = useState("");
  const [crewId, setCrewId] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [shift, setShift] = useState<ShiftValue>({ start: "", end: "" });
  const [van, setVan] = useState("");

  const staffQuery = useQuery({
    queryKey: ["work", "crews", "staff-choices"],
    queryFn: () => listStaffChoices(props.client),
    retry: false,
  });
  // A picker of crews, not a list a person pages through: the first 200 by
  // name, which is every crew a utility of this product's size runs.
  const crewsQuery = useQuery({
    queryKey: ["work", "crews", "crew-choices"],
    queryFn: () => listCrewsView<CrewListRow>("crews", { per: 200 }, props.client),
    retry: false,
  });

  const people = (staffQuery.data?.results ?? []).filter((row) => row.status !== "deactivated");
  const chosen = people.find((row) => row.user_id === person);
  const chosenName = chosen === undefined ? "" : (chosen.full_name ?? chosen.email);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    const body = {
      user_id: person,
      role_label: jobTitle.trim(),
      ...shiftPayload(shift),
      van: van.trim(),
    };
    try {
      if (crewId === "") await createTechnician(body, props.client);
      else await addCrewMember(crewId, body, props.client);
      props.onAdded();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("work.crews.member.title")}
      schema={memberSchema}
      values={{ person }}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t("work.crews.member.submit")}
    >
      <SearchSelectField
        id="person"
        label={t("work.crews.member.person")}
        value={person}
        onChange={setPerson}
        required
        dropdown
        options={people.map((row) => ({
          value: row.user_id,
          label: row.full_name ?? row.email,
          search: row.email,
          detail: personDetail(row, (key, options) => t(key, { defaultValue: "", ...options })),
        }))}
      />
      <p className="field-help -mt-2 mb-0" data-not-listed="">
        {t("work.crews.member.notListed")}{" "}
        <InlineLinkTo to={tenantPath("/settings/users")}>{t("work.crews.member.usersRoles")}</InlineLinkTo>.
      </p>
      <SelectField
        id="crew"
        label={t("work.crews.member.crew")}
        value={crewId}
        onChange={setCrewId}
        placeholder={t("work.crews.member.noCrew")}
        options={(crewsQuery.data?.results ?? []).map((row) => ({ value: row.id, label: row.name }))}
      />
      <TextField
        id="role_label"
        label={t("work.crews.member.jobTitle")}
        value={jobTitle}
        onChange={setJobTitle}
        help={t("work.crews.shownOnList")}
      />
      <ShiftField id="member-shift" label={t("work.crews.col.shift")} value={shift} onChange={setShift} />
      <TextField id="van" label={t("work.crews.member.van")} value={van} onChange={setVan} />
      {chosen !== undefined && (
        <ConsequenceBox
          tone="publish"
          tag={t("work.crews.effect")}
          title={t("work.crews.member.effectTitle", { name: chosenName })}
          body={t("work.crews.member.effectBody", { name: chosenName })}
          data-consequence="add-crew-member"
        />
      )}
    </FormModal>
  );
}

export default AddCrewMemberModal;
