// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-CUS-6427` — lane REQ-EDIT. PO ruling 2026-09-23, verbatim:
//           *"if user makes mistake while filling t new request form then
//           system should allow to correct it using edit , there is no edit
//           available on list view as wellas detail view"*.
// Rules:    decision log 2026-09-23, *"THE PO ASKS FOR *EDIT* ON A SERVICE
//           REQUEST, AND WHY IT CANNOT BE THE NEXT THING WIRED"* — which states
//           are editable was the coordinator's call under law 13, recorded
//           there rather than asked · BR-CUS-070 · hard rule 7
// Server:   `apps/customers/service_request.py::EDITABLE_STATES` — the SAME
//           four, and `update_request` refuses every other state by name.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// **WHICH REQUESTS A CLERK MAY STILL CORRECT — ONE PLACE, READ BY EVERY DOOR.**
// ══════════════════════════════════════════════════════════════════════════
//
// *Draft*, *Submitted*, *Under review*, *More info needed*: the request is still
// being worked. **Not** once *Approved* or *Refused* — those are decisions, and
// an approved request has already become an account and a job, so correcting it
// is a correction to THOSE records and not to the request.
//
// ⚠ **THE SERVER HOLDS THE SAME LIST AND IS THE AUTHORITY.** This copy decides
// only whether a door is DRAWN; `update_request` refuses a PATCH in any other
// state in words (`approvedNoEdit` / `terminalNoEdit`), so a door drawn wrongly
// here opens onto a refusal rather than onto a write. The pair is pinned equal
// by `test_def_cus_6427_request_edit.py` reading this file's list.
//
// ⚠ **A DECIDED REQUEST SHOWS NO DOOR AT ALL, RATHER THAN A GREYED ONE.** It is
// the reasoning `PremisesDetailPage` records for its status control: a control
// a person may NEVER press again is not a control. An approval cannot be
// undone, so there is no state in which the pencil would come back.
import { ButtonLink } from "@/components/Button";
import { RowActionLink } from "@/components/RowActions";
import { PencilIcon } from "@/components/icons";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { serviceRequestCapturePath } from "./serviceRequestShared";

export const EDITABLE_REQUEST_STATES = ["draft", "submitted", "under_review", "more_info"] as const;

/** True while a clerk may still correct what the request says. */
export function requestIsEditable(state: string | null | undefined): boolean {
  return (EDITABLE_REQUEST_STATES as readonly string[]).includes(state ?? "");
}

/** The four states `ServiceRequest.TERMINAL_STATES` names — the request is
 *  CLOSED, so the server answers `terminalNoEdit`. Every other state outside
 *  the editable four is past an approval and answers `approvedNoEdit`. */
const CLOSED_REQUEST_STATES: readonly string[] = ["completed", "refused", "withdrawn", "closed"];

/** The catalogue key of the SERVER's own refusal for `state`, so the wizard
 *  opened on a decided request by a typed address says what a PATCH would
 *  have said, in the same words, before anything is sent. */
export function editRefusalKey(state: string): string {
  return CLOSED_REQUEST_STATES.includes(state)
    ? "customers.serviceRequest.terminalNoEdit"
    : "customers.serviceRequest.approvedNoEdit";
}

// ══════════════════════════════════════════════════════════════════════════
// **THE TWO DOORS — `DEF-CUS-6427` (+ `DEF-CUS-5881`, the reopen path nothing
// linked to). Wired in the SAME commit that deleted
// `serviceRequestResumeHold.test.ts`, as that file's header instructed.**
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **ONE ADDRESS FOR BOTH WORDS.** `Resume` on a draft and `Edit` on a request
// still being worked open the SAME wizard at `serviceRequestCapturePath` —
// the builder that has existed since REQ-03 and had no caller. What differs
// is what the wizard's buttons do once it is open (Submit vs Save changes),
// and it reads that from the LOADED state, so a link cannot disagree with the
// record it opens.

/** `Resume` for a draft — the capture is unfinished; `Edit` otherwise. */
function editDoorLabelKey(state: string): string {
  return state === "draft"
    ? "customers.serviceRequest.action.resumeDraft"
    : "customers.serviceRequest.action.edit";
}

/**
 * **The row's pencil** — B14 rule 15: a row action is an icon with a tooltip,
 * and ✎ is the rule's own glyph for *edit*. With the eye it makes two, which
 * is rule 15's maximum before an overflow. Draws NOTHING on a decided request.
 */
export function RequestEditRowAction(props: { requestId: string; state: string; t: Translator }) {
  const tenantPath = useTenantPath();
  if (!requestIsEditable(props.state)) {
    return null;
  }
  return (
    <RowActionLink
      label={props.t(editDoorLabelKey(props.state))}
      icon={<PencilIcon />}
      to={tenantPath(serviceRequestCapturePath(props.requestId))}
    />
  );
}

/**
 * **The request page's `Edit` / `Resume`** — a WORD, not the pencil: an
 * ordinary button says a word and the glyph vocabulary is for table rows only
 * (PO 2026-08-20, *"this only for table actions ; not for buttons"*, recorded
 * on `PremisesDetailPage`'s head). Secondary, because the head's one primary
 * is the state's decision (B14 rule 4). Draws NOTHING on a decided request.
 */
export function RequestEditButton(props: { requestId: string; state: string; t: Translator }) {
  const tenantPath = useTenantPath();
  if (!requestIsEditable(props.state)) {
    return null;
  }
  return (
    <ButtonLink
      variant="secondary"
      data-testid="edit-request"
      to={tenantPath(serviceRequestCapturePath(props.requestId))}
    >
      {props.t(editDoorLabelKey(props.state))}
    </ButtonLink>
  );
}
