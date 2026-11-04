// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.34 (lane MVI-WIZ-REV) — **Edit opens the Add form,
//           and saves back to the SAME request or move-in** (image 47).
// Defect:   DEF-CUS-9731 — `?request=<id>&edit=1` was ignored: the form opened
//           prefilled from the request, autosaved a NEW `MVI-` draft on open,
//           and nothing the clerk changed ever reached the request.
// Rules:    PO ruling 2026-10-05, *"on edit of Move in request use same form
//           Add form to edit"* (J3) · CR-171 §9.REQ *Edit uses the Add form* ·
//           §9.DETAIL (`edit=1` is the one parameter the details view sends) ·
//           BR-SHL-048 (one park per move-in; *"we cannot create two build"*)
// Tests:    moveInWizard/useMoveInEdit.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// TWO KINDS OF EDIT, DECIDED BY THE SERVER'S `editable`
// ══════════════════════════════════════════════════════════════════════════
// `GET /service-requests/{id}/move-in-form` answers the request's own facts
// laid over whatever was parked for it, in the wizard's own value keys, and
// says whether the REQUEST may still be edited (Draft / Submitted / Under
// review / More info — *To approve* and *Waiting on customer*).
//
//   * **`request`** — an undecided request. Nothing may be parked under a new
//     number, so the wizard's autosave stays OFF; *Save draft & exit* and the
//     last step's commit both `PUT …/move-in-form`, which writes the request's
//     own fields back through the request's writers and parks the rest in the
//     ONE draft keyed to the request (its reference is the `SR-` number). The
//     request is never approved here, and the clerk lands back on its details.
//   * **`move_in`** — the request is approved and its move-in is Not started.
//     The request's fields are decided and the PUT refuses, so the form is the
//     move-in itself: it resumes the request's park when there is one (so the
//     autosave keeps writing THAT row, never a second), and Complete commits
//     it exactly as *Start* does. The title names the move-in's `MVI-` number.
//
// ⚠ **`DEF-CUS-9735` — START RESUMES TOO, AND EVERY DRAFT NAMES ITS REQUEST.**
// *Start* on a Not started move-in (`?request=` with no `edit=1`) reads the same
// form and resumes the same park — §9.REQ asked for exactly that — and stays
// titled *New move-in*. A draft the autosave writes for an approved request
// carries `service_request_id` and the job's `move_in_no` in `subject_ref`
// (`subjectRef` below): without them the server could never find it again, and
// every open of the form minted another `MVI-` draft (walked: MVI-26-0009 and
// MVI-26-0011 for one job, MVI-26-0001).
//
// A refused read (404, a request that is not a move-in) leaves the wizard as
// a plain `?request=` open — the prefill the wizard already does — and says
// nothing extra: the details view only offers Edit where the server does.

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import type { ApiClient, ApiResponse } from "@/api/client";

import { MOVE_IN_EDIT_PARAM } from "../moveDetail/MoveInDetail";
import { readMoveRecord } from "../MoveRecordPage";

/** `?parked=` — `wizardPark`'s own handle for the draft being resumed. */
const PARKED_PARAM = "parked";

/** §9.REQ — the answer of `GET|PUT /service-requests/{id}/move-in-form`. */
export interface MoveInFormAnswer {
  request: {
    id: string;
    request_no: string | null;
    state: string;
    status: string;
    editable: boolean;
  };
  park_id: string | null;
  step: number;
  values: Record<string, unknown>;
}

/** The house's restated guard (every endpoints file carries its own). */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export function moveInFormPath(requestId: string): string {
  return `/service-requests/${encodeURIComponent(requestId)}/move-in-form`;
}

export async function getMoveInForm(requestId: string, client: ApiClient): Promise<MoveInFormAnswer> {
  return requireData(await client.get<MoveInFormAnswer>(moveInFormPath(requestId)));
}

export async function putMoveInForm(
  requestId: string,
  body: { step: number; values: Record<string, unknown> },
  client: ApiClient,
): Promise<MoveInFormAnswer> {
  return requireData(await client.put<MoveInFormAnswer>(moveInFormPath(requestId), body));
}

export type MoveInEditMode = "none" | "pending" | "request" | "move_in";

export interface MoveInEdit {
  /** `none` — not an edit · `pending` — the form is being read, decide
   *  nothing (in particular, write no draft) · `request` / `move_in` above. */
  mode: MoveInEditMode;
  /** What the title names — `SR-…` for a request, `MVI-…` for a move-in;
   *  `null` while unknown. */
  reference: string | null;
  /** The request's number, for the details view the clerk returns to. */
  requestNo: string | null;
  /** True once the edit's values have been put in the form — a later resume
   *  of the request's own park must not put the stripped copy over them. */
  applied: boolean;
  /** `PUT …/move-in-form` — `request` mode only. */
  save: (step: number, values: Record<string, unknown>) => Promise<MoveInFormAnswer>;
  /** True only for the details view's Edit (`edit=1`) — what the TITLE reads.
   *  *Start* on an approved request resumes the same way and stays *New*. */
  isEdit: boolean;
  /**
   * `DEF-CUS-9735` — what a draft written for this move-in carries in its
   * `subject_ref`, so the server's park lookup (`move_in_request._edit_park`)
   * finds it next time and `wizard_parks` carries the job's `MVI-` number as
   * the draft's reference instead of minting another (`CARRIED_REFERENCE_KEYS`).
   * `{}` when the form is not about a request.
   */
  subjectRef: Record<string, string>;
}

export function useMoveInEdit(args: {
  client: ApiClient;
  requestId: string;
  /** Put the form's values into the wizard, ONCE. */
  apply: (values: Record<string, unknown>) => void;
}): MoveInEdit {
  const [searchParams, setSearchParams] = useSearchParams();
  const isEdit = searchParams.get(MOVE_IN_EDIT_PARAM) === "1";
  // ⚠ `DEF-CUS-9735` — *Start* (`?request=` with no `edit=1`) reads the form
  // too: an approved request's parked rest must be resumed, never re-made
  // under a second number (§9.REQ, *"For WIZ / DETAIL (P2.34, Start)"*).
  const wanted = args.requestId !== "";
  const [answer, setAnswer] = useState<MoveInFormAnswer | null>(null);
  const [failed, setFailed] = useState(false);
  const [reference, setReference] = useState<string | null>(null);
  const applied = useRef<string | null>(null);

  useEffect(() => {
    if (!wanted || applied.current === args.requestId) return;
    let live = true;
    getMoveInForm(args.requestId, args.client)
      .then(async (form) => {
        if (!live) return;
        // An undecided request opened WITHOUT Edit is the old road (the
        // prefill); only Edit writes back to it.
        if (form.request.editable && !isEdit) {
          setFailed(true);
          return;
        }
        // An approved request answers its job or its move-in (§9.LIST
        // `GET /moves/{ref}`), whose `reference` is the `MVI-` number — read
        // BEFORE the mode settles, so the first draft already carries it.
        let moveNo: string | null = null;
        if (!form.request.editable && form.request.request_no) {
          moveNo = await readMoveRecord(form.request.request_no, args.client)
            .then((record) => (record as { reference?: string | null }).reference ?? null)
            .catch(() => null);
          if (!live) return;
        }
        applied.current = args.requestId;
        // ⚠ **THE HANDLE GOES IN THE URL BEFORE THE MODE FLIPS**, so on the
        // render where the autosave first switches on it already names the
        // request's park and patches it — never creates a second one.
        if (!form.request.editable && form.park_id !== null) {
          const parkId = form.park_id;
          setSearchParams(
            (current) => {
              const next = new URLSearchParams(current);
              next.set(PARKED_PARAM, parkId);
              return next;
            },
            { replace: true },
          );
        }
        // A request that names NO service has not chosen "none" — it has not
        // chosen. `[]` would untick every service on the unit; absent leaves
        // the wizard's own pre-tick (`BR-CUS-1101`, `null` = not touched).
        const values = { ...form.values };
        if (Array.isArray(values.services) && values.services.length === 0) delete values.services;
        args.apply(values);
        setReference(form.request.editable ? form.request.request_no : moveNo);
        setAnswer(form);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
    // The read is keyed by the request; `apply` is the wizard's fresh closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wanted, args.requestId]);

  const mode: MoveInEditMode = !wanted || failed
    ? "none"
    : answer === null
      ? "pending"
      : answer.request.editable
        ? "request"
        : "move_in";
  return {
    mode,
    reference,
    requestNo: answer?.request.request_no ?? null,
    applied: answer !== null,
    save: (step, values) => putMoveInForm(args.requestId, { step, values }, args.client),
    isEdit,
    subjectRef:
      answer === null
        ? {}
        : {
            service_request_id: answer.request.id,
            ...(answer.request.request_no ? { request_no: answer.request.request_no } : {}),
            ...(!answer.request.editable && reference ? { move_in_no: reference } : {}),
          },
  };
}
