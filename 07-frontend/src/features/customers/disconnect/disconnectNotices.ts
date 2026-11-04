// ═══════════════════════════════════════════════════════════════════════
// `DSC-02.3`'s NOTICES — the table the step reads and the proof the COMMIT writes
// ═══════════════════════════════════════════════════════════════════════
// Change:   `CR-125-BRC07` — lifted out of `NoticeAndDateStep.tsx`, because the
//           proof is no longer that step's own write. PO ruling 2026-09-21:
//           *"we need to keep only park, complete - two action only"*. Step 3
//           TYPES the proof; `DisconnectWizard`'s Complete WRITES it, so both
//           need these wrappers and neither may import the other.
// Rules:    BR-CUS-100 (the SEND and the PROOF are two different records)
// Tests:    ../DisconnectWizard.test.tsx
//
// ⚠ **`DEF-CUS-5169` — THE DOOR THAT HAD NO HANDLE.** Step 3 told a clerk
// **"No final notice is recorded as served. Record it first."** and offered
// nothing that could record one, while `POST /disconnect-notices/{id}/proof` has
// been mounted and answering since 2026-08-28. The consequence was not cosmetic:
// `assert_service_proved` refuses a cut without a proof row, so no cut could be
// scheduled from this screen on any account in this tree, and every check passed
// over it. Nothing asks whether a refusal that tells a clerk to ACT names a
// control that lets them.
import type { ApiClient } from "@/api/client";

export interface DisconnectNoticeRow {

  notice_id: string;
  account_id: string | null;
  tier: string | null;
  issued_on: string;
  recorded: boolean;
  channel: string | null;
  reference: string | null;
  served_on: string | null;
  signed_for_on: string | null;
}

/** `GET /accounts/{id}/disconnect-notices` — `DSC-02.3`'s own notice table. */
export async function getAccountNotices(
  accountId: string,
  client: ApiClient,
): Promise<DisconnectNoticeRow[]> {
  const answer = await client.get<{ notices: DisconnectNoticeRow[] }>(
    `/accounts/${accountId}/disconnect-notices`,
  );
  return answer.data?.notices ?? [];
}

/** `POST /disconnect-notices/{id}/proof` — BR-CUS-100's attestation.
 *
 *  ⚠ **CALLED BY THE WIZARD'S COMMIT, NOT BY STEP 3 — `CR-125-BRC07`.** It used
 *  to fire the moment a `Record the proof ✓` button was pressed, which was a
 *  third action on a wizard the PO ruled has two. */
export async function postProofOfService(
  noticeId: string,
  body: { channel: string; reference: string; served_on: string; signed_for_on: string | null },
  client: ApiClient,
): Promise<unknown> {
  return client.post(`/disconnect-notices/${noticeId}/proof`, body);
}

