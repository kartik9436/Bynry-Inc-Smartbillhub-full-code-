// ── Trace ──────────────────────────────────────────────
// Change:   CR-085 step 2 lane 6 — the four screens that take money say why a
//           commit is refused, OUT LOUD. Screens: CWP-038 · CWP-076 · CWP-002 ·
//           CWP-003.
// Rules:    BR-CWP-056 / CR-068 R3 (a control that may not be used is VISIBLE,
//           DISABLED and carries its REASON) · R-10 (PO 2026-09-11: the thing a
//           customer can do about bad news is on the same screen, next to the
//           message) · B14 rule 33 (a refusal is five or six words) · rule 36
//           (compose the kit)
// Defects:  DEF-CWP-4866 · and it is the standing cause of DEF-CWP-4152
// Tests:    src/portal/payments/PayNow.dom.test.tsx ·
//           src/portal/payments/PayNowCheck.dom.test.tsx ·
//           src/portal/guest/QuickPay.dom.test.tsx
// ───────────────────────────────────────────────────────
import { CommitButton } from "./primitives";

/**
 * The kit's `CommitButton` **with its reason rendered as text** — `DEF-CWP-4866`.
 *
 * ⚠ **`CommitButton` PUTS A REFUSAL ON `title=` AND NOWHERE ELSE.** Measured in
 * a browser on 2026-09-11: the disabled control carries `title="Fill in both
 * boxes first."`, `aria-label` null, `aria-describedby` null, and the sentence
 * appears **nowhere in the page text**. A `title` tooltip needs a mouse and a
 * second of hover — on a phone it does not exist at all, and a phone is where
 * most people pay. `HeldButton`, in the same kit file, renders the identical
 * kind of sentence as a visible `<span>`, so one screen says *We cannot draft
 * payments yet* out loud while the screen that takes the money says nothing.
 *
 * ⚠ **THE FIX BELONGS IN THE KIT AND THIS IS NOT IT.** `primitives.tsx` is one
 * file and four lanes are editing the portal at once (hard-won law 11: the
 * second to commit silently reverts the first), so `CR-085` step 2 gave the kit
 * to one lane and this one owns only its own screens. What this component does
 * is compose the two pieces the kit already owns — the disabled `CommitButton`
 * and `HeldButton`'s own `text-base text-neutral-500` sentence — in the
 * arrangement `HeldButton` established. When `CommitButton` learns to say its
 * own reason, THIS WRAPPER IS DELETED and every call site keeps working.
 *
 * ⚠ **THE SENTENCE IS `role="status"` AND NOT AN ALERT.** It is standing copy
 * about a control, re-read on every keystroke while an amount is typed; an
 * alert role would make a screen reader interrupt itself on each one.
 */
export function HeldCommit(props: {
  label: string;
  working: boolean;
  ready: boolean;
  reason: string;
  onClick: () => void;
  testKey?: string;
}) {
  // ⚠ **`CommitButton` NOW SAYS ITS OWN REASON (F-22, `DEF-CWP-10551`)** —
  // drawn under the button, in these same classes, with the button pointing
  // at it — so the sentence this wrapper used to add would now appear twice.
  // It keeps only its `data-pay-control` hook, which the payment tests read.
  return (
    <div className="flex flex-col items-start gap-1" data-pay-control={props.testKey ?? ""}>
      <CommitButton
        label={props.label}
        working={props.working}
        ready={props.ready}
        reason={props.reason}
        onClick={props.onClick}
      />
    </div>
  );
}
