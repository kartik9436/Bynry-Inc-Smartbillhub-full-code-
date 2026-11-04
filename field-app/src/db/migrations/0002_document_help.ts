/**
 * 0002 — the job's HELP rides in `document` (DEF-FLD-10581, beta MQ-011).
 *
 * The bundle (`GET work/mobile/jobs/{id}`, `mobile._help_row`) sends each help
 * entry as `{id, seq, kind, label, ref, url}`: a document (`ref` its stored
 * document's id, `url` a four-hour pre-signed link), a phone (`ref` the
 * number), a link (`ref` its https address) or a note. 0001's `document` holds
 * the title and the kind and has nowhere for a number or an address, so:
 *
 *   ref — the server's own `ref`, verbatim: what a phone dials, what a link
 *         opens, which stored file a document is (a changed `ref` is a new
 *         file, so the old copy is dropped and the new one downloaded).
 *   url — a document's pre-signed link, kept only until its bytes are down
 *         (BR-WRK-038: the phone opens its OWN copy, never the link).
 *
 * Forward only, like 0001: nothing here is ever edited — a correction is 0003.
 */
import type { Migration } from './types';

export const m0002: Migration = {
  id: 2,
  name: 'document_help',
  statements: ['ALTER TABLE document ADD COLUMN ref TEXT', 'ALTER TABLE document ADD COLUMN url TEXT'],
};
