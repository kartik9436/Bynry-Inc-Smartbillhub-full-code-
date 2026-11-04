// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 4 — the build's state, as a pill. MOVED here
//           from `features/customers/BuildDetailTabs.tsx:1235` by
//           `DEF-CUS-7618`, unchanged.
// Rules:    B14 rule 43 · rule 31 (the state's WORD, never its token) ·
//           `CR-151-BRC09` §2 rule (2)
// Tests:    src/features/customers/BuildDetailPage.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The state pill every host's build header shares — the SHARED tone function,
 * never a second reading of the same token.
 *
 * ⚠ **THE TONE IS `buildViews.buildStateTone` AND THE WORD IS THE CATALOGUE'S.**
 * `BuildRecordHeader` takes a `stateTone` prop and draws its own pill, so it
 * cannot be composed by a PAGE HEADER that is not the record's; this is the
 * same two facts wearing `PageHeader`'s `status` slot instead. One tone
 * function means a *Partly activated* build cannot be amber in one place and
 * green in another.
 */
import { StatusPill } from "@/components/StatusPill";
import { connectionStateLabel } from "@/features/customers/NewConnectsTab";
import type { Translator } from "@/features/customers/newConnectShared";

import { buildStateTone } from "../buildViews";

export function BuildStatePill(props: { state: string; t: Translator }) {
  return (
    <span data-build-state={props.state}>
      <StatusPill tone={buildStateTone(props.state)}>
        {/* ⚠ **`DEF-MET-7805` — THIS LINE PRINTED `requested` TO A CLERK, IN A
            FILE WHOSE OWN TRACE HEADER PROMISES *the state's WORD, never its
            token* (hard-won law 1, in one sentence).** It read
            `t(\`customers.newConnect.state.${props.state}\`, { defaultValue:
            props.state })` and that key family resolves in none of the eleven
            catalogues, so the `defaultValue` WAS the copy. `connectionStateLabel`
            is the list's own reader and is asserted complete against the
            SERVER's `CONNECTION_STATES` by `newConnectStateLabels.test.ts` —
            reusing it is the point: two vocabularies for one idea is how two
            screens start disagreeing. */}
        {connectionStateLabel(props.state, props.t)}
      </StatusPill>
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-151-BRC09 §2 rule (2)
// generated: 2026-09-28 by the DETAIL PAGE lane; MOVED into the kit the same
//   day by the DEF-CUS-7618 lane, unchanged
// checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
