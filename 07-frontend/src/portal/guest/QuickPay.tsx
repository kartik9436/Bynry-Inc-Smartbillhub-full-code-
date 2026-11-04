// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-003 (EP-CWP-02) — find the bill on a number and a postcode ·
//           US-CWP-002 — the throttle and the lockout in front of it.
//           Screens: CWP-002 · wireframes/CWP-002.png
// Rules:    08-screen-layouts.md CWP-002 (T2: GuestFrame → Stepper 3 → main
//           Card [kicker PAY A BILL · section title *Find your bill* · rule ·
//           FormField Bill number* · FormField Postcode of the service
//           address* · Continue →] · rail [Panel WHERE TO FIND IT ·
//           Panel.Warning five wrong tries…]) · BR-CWP-018 (a bill number
//           proves someone is HOLDING the bill, not who they are) ·
//           BR-CWP-019/020 (the amount owing and a MASKED name, nothing else) ·
//           BR-CWP-023 (five wrong tries, fifteen minutes) · BR-CWP-056 /
//           CR-068 R3 (a control that cannot be used yet is DISABLED with its
//           reason — never hidden, never live-but-inert) · B14 rule 21
//           (`src/portal/` is on route-b-migrated.txt) · rule 31 (no database
//           id is a visible value) · rule 32 (one sentence per section) ·
//           rule 33 (a refusal is five or six words) · rule 35 (the catalogue
//           writes the words) · rule 36 (compose the kit)
// Tests:    src/portal/guest/QuickPay.dom.test.tsx
// Impacts:  06-backend/apps/portal/guest_api.bill_lookup · guestClient.ts
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PortalRefusal } from "../components/a11y";

import { lookUpBill } from "../api/guestClient";
import type { BillLookupView } from "../api/guestClient";
import { usePortalDate } from "../components/regional";
import {
  Card,
  CommitButton,
  FormField,
  KVList,
  SectionTitle,
  Stepper,
  TextInput,
  TwoCol,
  usePortalPath,
} from "../components/primitives";
import { HeldCommit } from "../components/heldCommit";

/** The three steps `08-screen-layouts.md` draws across CWP-002 · 003 · 004. */
const STEP_KEYS = ["find", "check", "done"] as const;

/**
 * `CWP-002` — the two facts printed on the paper, and what happens when
 * somebody guesses at them.
 *
 * ⚠ **STEP 2 IS `CWP-003` AND IS `US-CWP-004`'s, WHICH IS BLOCKED ON RAILS —
 * SO THIS SCREEN STOPS AT THE BOUNDARY AND SAYS SO.** What a match shows here
 * is exactly what the server answered and no more: the status, the figure and
 * the masked name (`BR-CWP-019`), with the Pay control **visible, disabled and
 * carrying its reason** (`BR-CWP-056`). It deliberately does NOT draw
 * `CWP-003`'s card fields, its security code, its receipt address or its
 * consequence box — nothing in the product can charge a card, and drawing a
 * payment form in front of a gateway that does not exist is *built is not
 * wired* pointed the wrong way (hard-won law 2). Decision log 2026-09-04.
 *
 * ⚠ **THE MASKED NAME IS RENDERED AS IT ARRIVED.** Masking again here would be
 * a second implementation of `BR-CWP-020` and the two would drift; masking
 * *instead of* here would mean the browser had already been told the name.
 */
export function QuickPayFindBill(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const path = usePortalPath();
  //: The tenant's own date format, through the product's ONE formatter —
  //: `CWP-003` reads the same due date through the same hook (`DEF-CWP-3994`).
  const asDate = usePortalDate();

  const [billNumber, setBillNumber] = useState("");
  const [postcode, setPostcode] = useState("");
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [found, setFound] = useState<BillLookupView | null>(null);

  async function find() {
    setWorking(true);
    setRefused(null);
    try {
      setFound(await lookUpBill(billNumber.trim(), postcode.trim(), client));
    } catch (error) {
      // ⚠ ONE SENTENCE FOR EVERY MISS. The server already answers identically
      // for an unknown number, a wrong postcode and another utility's bill
      // (`US-CWP-003` TC-2/TC-3); this branch must not add a second one.
      setFound(null);
      setRefused(refusalText(t, error));
    } finally {
      setWorking(false);
    }
  }

  const ready = billNumber.trim().length > 0 && postcode.trim().length > 0;
  const payable = found?.status === "payable";

  return (
    <div data-screen="CWP-002">
      <Stepper steps={STEP_KEYS.map((key) => t(`portal.quickPay.step.${key}`))} current={1} />
      <TwoCol
        main={
          <Card testId="quick-pay-find">
            <PageHeader
              kicker={t("portal.quickPay.kicker")}
              title={t("portal.quickPay.title")}
              rollup={t("portal.quickPay.lead")}
            />
            <hr className="border-neutral-200" />
            <div className="mt-4 flex flex-col gap-3">
              <FormField id="quickpay-number" label={t("portal.quickPay.billNumber")} required>
                <TextInput
                  id="quickpay-number"
                  value={billNumber}
                  onChange={setBillNumber}
                  placeholder={t("portal.quickPay.billNumberExample")}
                />
              </FormField>
              <FormField
                id="quickpay-postcode"
                label={t("portal.quickPay.postcode")}
                helper={t("portal.postcodeHelper")}
                required
              >
                <TextInput id="quickpay-postcode" value={postcode} onChange={setPostcode} />
              </FormField>
              {refused !== null ? (
                <PortalRefusal data-quick-pay-refused="">{refused}</PortalRefusal>
              ) : null}
              {/* ⚠ **`HeldCommit` AND NOT `CommitButton` — `DEF-CWP-4866`.**
                  The kit puts a refusal on `title=` and NOWHERE else:
                  measured in a browser on 2026-09-11, this control carried
                  `title="Fill in both boxes first."`, `aria-label` null, `aria-describedby` null,
                  and the sentence appeared nowhere in the page text. A
                  tooltip needs a mouse and a second of hover, so on a phone
                  — where most people pay a bill — the reason a button will
                  not work did not exist. `HeldButton`, in the same kit
                  file, has rendered exactly this kind of sentence visibly
                  all along. The wrapper composes the two and is deleted the
                  day `CommitButton` says its own reason. */}
              <HeldCommit
                testKey="find"
                label={t("portal.quickPay.continue")}
                working={working}
                ready={ready}
                reason={t("portal.quickPay.needBoth")}
                onClick={() => void find()}
              />
            </div>

            {found !== null ? (
              <div className="mt-4 border-t border-neutral-200 pt-4" data-bill-found="">
                <SectionTitle>{t("portal.quickPay.foundTitle")}</SectionTitle>
                <KVList
                  rows={[
                    {
                      key: "number",
                      label: t("portal.quickPay.billNumber"),
                      value: <span data-bill-number="">{found.number}</span>,
                    },
                    {
                      key: "billed-to",
                      label: t("portal.quickPay.billedTo"),
                      // ⚠ SERVER-MASKED, RENDERED VERBATIM (`BR-CWP-020`).
                      value: <span data-masked-name="">{found.masked_name}</span>,
                    },
                    {
                      key: "status",
                      label: t("portal.quickPay.stateLabel"),
                      value: (
                        <span data-bill-status={found.status}>
                          {t(`portal.quickPay.state.${found.status}`)}
                        </span>
                      ),
                    },
                    {
                      key: "owing",
                      label: t("portal.quickPay.owing"),
                      // Hard rule 2 — the screen renders `display` and never
                      // formats money itself.
                      value: <span data-money={found.amount.amount ?? ""}>{found.amount.display}</span>,
                    },
                    // ⚠ **THE DUE DATE, WHICH THE SERVER HAS ALWAYS SENT AND
                    // THIS STEP THREW AWAY** (`CR-085`, 2026-09-08). The
                    // drawing is explicit that these two facts travel together
                    // — *"What you can see here: only the amount due and the
                    // due date"* — and draws them in the largest type on the
                    // page. `due_on` is on `BillLookupView`; `CWP-003` one step
                    // along already draws it with this exact key and this exact
                    // formatter; step 1 simply never did. Somebody holding a
                    // bill and deciding whether to pay it today is asking BY
                    // WHEN, and this is the screen they ask it on.
                    //
                    // ⚠ ABSENT rather than a dash when the server sends none.
                    // An em dash beside *Due* reads as a date that exists and
                    // is being withheld. (`CWP-003` draws a dash because its
                    // row is one of three fixed facts on a confirmation; this
                    // list is built from what came back.)
                    ...(found.due_on
                      ? [
                          {
                            key: "due",
                            label: t("portal.quickPay.due"),
                            //: The ATTRIBUTE keeps the server's own string — it
                            //: is what a test and a walkthrough read — and the
                            //: VISIBLE value is the tenant's own format.
                            value: (
                              <span data-due-on={found.due_on}>{asDate(found.due_on)}</span>
                            ),
                          },
                        ]
                      : []),
                  ]}
                />
                {found.replaced_by !== null ? (
                  <p className="mt-2 text-body text-neutral-600" data-replaced-by={found.replaced_by}>
                    {t("portal.quickPay.replacedBy", { number: found.replaced_by })}
                  </p>
                ) : null}
                <div className="mt-3">
                  {payable ? (
                    // ⚠ **RELEASED 2026-09-05, THE DAY `CWP-003` LANDED
                    // (`US-CWP-004`).** It was a `HeldButton` reading *"Card
                    // payments are not open yet"* while no gateway existed
                    // (`CR-068` R2/R3). That refusal was correct when it was
                    // written and rots the moment step 2 ships, which is
                    // hard-won law 2's amendment in one line — *landing a
                    // screen and releasing the control that pointed at it are
                    // two acts and only the first feels like the work*
                    // (`DEF-CWP-3925`, eight shut doors on one page).
                    //
                    // ⚠ **THE PAIR TRAVELS IN ROUTER STATE, NOT IN THE
                    // ADDRESS** — a bill number and somebody's postcode in a
                    // URL end up in access logs, browser history and a
                    // `Referer` header, which is the reasoning this file's own
                    // page component already records.
                    <CommitButton
                      label={t("portal.quickPay.pay", { amount: found.amount.display })}
                      working={false}
                      ready
                      reason=""
                      onClick={() =>
                        navigate(path("/pay/check"), {
                          state: { billNumber: found.number, postcode: postcode.trim() },
                        })
                      }
                    />
                  ) : (
                    <p className="text-body text-neutral-600" data-nothing-to-pay="">
                      {t("portal.quickPay.nothingToPay")}
                    </p>
                  )}
                </div>
              </div>
            ) : null}
          </Card>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.quickPay.whereToFind")}>
              <p className="text-body leading-relaxed text-neutral-600">
                {t("portal.quickPay.whereToFindBody")}
              </p>
            </Panel>
            <Panel as="aside" tone="warning" title={t("portal.quickPay.triesTitle")}>
              <p className="text-body leading-relaxed text-neutral-600" data-five-tries="">
                {t("portal.quickPay.triesBody")}
              </p>
            </Panel>
          </>
        }
      />
    </div>
  );
}
