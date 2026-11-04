// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-047 (out of range flags) · US-WRK-049 (the rule and the
//           file) · US-WRK-048 (the photograph) · US-WRK-036 (the signature)
// Rules:    BR-WRK-039 · BR-WRK-040 · BR-WRK-046 · BR-WRK-047 · BR-WRK-047a
// Tests:    src/features/work/mobile/ReadingsPane.dom.test.tsx
// Impacts:  06-backend/apps/work/api.py (#74, #76, #77, #78, #79)
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * One row of the Readings pane.
 *
 * ⚠ **`photo_required` AND `photo_attachment_id` ARE TWO FIELDS AND THE SCREEN
 * NEEDS BOTH** (`US-WRK-049`). The rule is *did the template ask*; the file is
 * *did anybody take one*. A single nullable field could not tell *asked for and
 * not taken* — which stops the close — from *never asked*, which does not.
 *
 * ⚠ **`in_range` IS THREE-VALUED AND `null` IS NOT `false`.** A reading whose
 * template set no bounds has not been checked, and rendering a red *out of
 * range* beside a number nothing ever questioned would teach a technician to
 * ignore the flag.
 */
export type ReadingRow = {
  id: string;
  seq: number;
  prompt: string;
  /**
   * ⚠ **`unit_of_measure`, BECAUSE THAT IS WHAT THE SERVER SENDS** — the job
   * bundle is `apps/work/checklist.checklist()` verbatim (`mobile.bundle`) and
   * every reading row in it carries `unit_of_measure`.
   *
   * This field was called `unit` until `DEF-WRK-4111`, and the cost of the
   * shorter name was the whole screen: `row.unit` was `undefined` on a real
   * handset, so the unit column rendered EMPTY (hard rule 3, on screen) and
   * every save posted a body with no unit — which `PUT …/readings/{rid}`
   * refuses, correctly, as `work.reading.unit_required`. **A technician could
   * not record a single reading**, and 245 front-end tests were green over it
   * because `ReadingsPane.dom.test.tsx` mocked `loadJob` with a fixture shaped
   * like this TYPE rather than like the server.
   *
   * So: a type is a claim about somebody else's payload, and a mock built from
   * the type can only ever confirm the claim to itself.
   */
  unit_of_measure: string;
  value: string | null;
  /** `CR-168-BRC10` P1.33 — `number` or `text`; a text reading's words are
   *  `value_text` and it is sent as words, never as a figure (`DEF-WRK-10602`). */
  kind?: "number" | "text";
  value_text?: string | null;
  in_range: boolean | null;
  required: boolean;
  photo_required: boolean;
  photo_attachment_id: string | null;
  captured_at: string | null;
  posts_as_meter_read: boolean;
};

/**
 * Whether the job may close, and what merely flags.
 *
 * ⚠ **TWO LISTS, AND THE SERVER SENDS THEM APART ON PURPOSE** (`BR-WRK-040`).
 * A screen that concatenated them would have undone the rule. `blocking` stops
 * the close; `flagged` never does.
 */
export type CloseReadiness = {
  can_close: boolean;
  blocking: { kind: string; scope: string; id: string; prompt: string }[];
  /** `BR-WRK-040` as superseded 2026-10-21 (PO: *"warn"*): required
   *  photographs not taken — a WARNING, never a stop. Absent on an older
   *  server, which sent them in `blocking`. */
  missing_photos?: { kind: string; scope: string; id: string; prompt: string }[];
  flagged: { kind: string; scope: string; id: string; prompt: string; value: string | null; unit: string }[];
  readings_captured: number;
  readings_total: number;
  required_photos_taken: number;
  required_photos_total: number;
};

export type AttachmentRow = {
  id: string;
  kind: string;
  taken_at: string;
  device: string;
  reading_id: string | null;
  task_id: string | null;
  duplicate?: boolean;
};

export type SignatureRow = {
  id: string;
  refused: boolean;
  printed_name: string | null;
  decline_reason: string | null;
  door_hanger_attachment_id: string | null;
  /** A phone's door-hanger photo was named and its bytes have not landed yet
   *  (DEF-WRK-10625); the attachment id fills in once they do. */
  door_hanger_uploading?: boolean;
  signed_at: string;
} | null;

/**
 * `PUT /work-orders/{id}/readings/{rid}` — the value AND its unit.
 *
 * ⚠ **THE UNIT IS ALWAYS SENT, EVEN THOUGH THE SERVER KNOWS IT** (hard rule 3:
 * *consumption always with an explicit unit; never assume*). It is not
 * redundant — the server compares what the phone thinks it measured against
 * what the job was raised carrying, and a disagreement is refused. Wave L posts
 * this number into a meter's history, where a wrong unit is a wrong bill.
 */
export async function putReading(
  orderId: string,
  readingId: string,
  body: { value: string; unit: string; captured_at?: string },
  client: ApiClient = api,
): Promise<ReadingRow> {
  return requireData(
    await client.put<ReadingRow>(`/work-orders/${orderId}/readings/${readingId}`, body),
  );
}

/** `GET /work-orders/{id}/close-readiness` — the two lists, kept apart. */
export async function loadCloseReadiness(
  orderId: string,
  client: ApiClient = api,
): Promise<CloseReadiness> {
  return requireData(
    await client.get<CloseReadiness>(`/work-orders/${orderId}/close-readiness`),
  );
}

/** `GET /work-orders/{id}/attachments` — this job's photographs. */
export async function loadAttachments(
  orderId: string,
  client: ApiClient = api,
): Promise<AttachmentRow[]> {
  return requireData(await client.get<AttachmentRow[]>(`/work-orders/${orderId}/attachments`));
}

/**
 * `POST /work-orders/{id}/attachments` — the bytes and the row, in one call.
 *
 * ⚠ **`idempotencyKey` IS MINTED ON THE HANDSET AT CAPTURE AND NEVER HERE.**
 * The whole point is that a retry of yesterday's photograph carries the SAME
 * key, so the server can tell it from a genuinely new picture of the same dial.
 * A key minted at send time would be new on every retry and write duplicates —
 * which is precisely the bug the key exists to prevent.
 */
export async function postAttachment(
  orderId: string,
  body: {
    file: Blob;
    idempotencyKey: string;
    device?: string;
    takenAt?: string;
    readingId?: string;
    taskId?: string;
    kind?: string;
  },
  client: ApiClient = api,
): Promise<AttachmentRow> {
  const form = new FormData();
  form.append("file", body.file, `${body.idempotencyKey}.jpg`);
  form.append("idempotency_key", body.idempotencyKey);
  form.append("content_type", body.file.type || "image/jpeg");
  if (body.device) form.append("device", body.device);
  if (body.takenAt) form.append("taken_at", body.takenAt);
  if (body.readingId) form.append("reading_id", body.readingId);
  if (body.taskId) form.append("task_id", body.taskId);
  if (body.kind) form.append("kind", body.kind);
  return requireData(await client.post<AttachmentRow>(`/work-orders/${orderId}/attachments`, form));
}

/** `GET /work-orders/{id}/signature` — `null` until the crew asks. */
export async function loadSignature(
  orderId: string,
  client: ApiClient = api,
): Promise<SignatureRow> {
  return requireData(await client.get<SignatureRow>(`/work-orders/${orderId}/signature`));
}

/**
 * `POST /work-orders/{id}/signature` — signed, or refused.
 *
 * ⚠ **NEVER BOTH** (`BR-WRK-046`). The two shapes are exclusive at the
 * database, at the service and here; this function takes a discriminated union
 * so a caller cannot even assemble the impossible one.
 */
export async function postSignature(
  orderId: string,
  body: (
    | { refused: false; printedName: string; image: Blob; signedAt?: string }
    | { refused: true; declineReason: string; doorHangerAttachmentId: string; signedAt?: string }
  ) & { captureToken?: string | null },
  client: ApiClient = api,
): Promise<SignatureRow> {
  const form = new FormData();
  form.append("signed_at", body.signedAt ?? new Date().toISOString());
  // CR-168-BRC10 §F, `BR-WRK-059` — whose signature capture this is, from the
  // technician signed in when it was taken (technician-api.md #10).
  if (body.captureToken) form.append("capture_token", body.captureToken);
  if (body.refused) {
    form.append("refused", "true");
    form.append("decline_reason", body.declineReason);
    form.append("door_hanger_attachment_id", body.doorHangerAttachmentId);
  } else {
    form.append("printed_name", body.printedName);
    form.append("content_type", body.image.type || "image/png");
    form.append("file", body.image, "signature.png");
  }
  return requireData(await client.post<SignatureRow>(`/work-orders/${orderId}/signature`, form));
}
