/**
 * What the session layer is allowed to know about the outbox: how much is
 * waiting, per technician. And what it is allowed to do to the handset's
 * data: drop the MIRROR on a remote sign-out. Nothing else.
 *
 * ⚠ **THERE IS NO DELETE HERE, AND THAT IS THE GUARANTEE.** Security tab §1:
 * *"There is no state in which captured work is thrown away to resolve an
 * auth problem."* R60/R64: *"Nothing unsent is ever purged — at any age,
 * under any sign-in, including another technician's work. A sign-out deletes
 * nothing."* R115: *"A remote sign-out drops the mirror and keeps the
 * outbox."* So the only door from `session/` into the database is this
 * interface, and it has no method that removes an outbox row or a photo file.
 * A lane that adds one has to change this file, and
 * `tests/session/nothingUnsentDiscarded.test.ts` goes red on the first auth
 * transition that uses it.
 *
 * The sync lane (T-10) implements it over the real outbox; the session tests
 * use an in-memory one.
 */
export interface UnsentCount {
  technicianId: string;
  /** Data items waiting to send (readings, ticks, closes…). */
  items: number;
  /** Photographs waiting to upload — counted on their own line (R65). */
  photos: number;
}

export interface OutboxPort {
  /** Unsent work on this handset, one row per technician who has any. */
  unsentCounts(): Promise<UnsentCount[]>;
  /**
   * Remote sign-out (Security tab §4): drop this technician's MIRROR tables
   * (their day, their jobs as downloaded). The outbox and its photo files are
   * NOT touched — *"they send, then go"*.
   */
  dropMirror(technicianId: string): Promise<void>;
}
