// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-027 (EP-CWP-06) — add another account. Screen: CWP-020
// Rules:    BR-CWP-001 kind ⑥ `account_link` (`DEF-CWP-3768`) · BR-CWP-033
//           (the code goes to a contact already held ON THAT ACCOUNT) ·
//           BR-CWP-039 (a consequence panel before the commit) · BR-CWP-015
//           (nothing is combined — bills stay separate) · BR-CWP-034 (no
//           contact dead-ends) · B14 rule 21 · rule 31 · rule 32 · rule 33 ·
//           rule 35 · rule 36
// Tests:    src/portal/details/AddAccount.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `findAccountToAdd` ·
//           `verifyAccountToAdd`
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  CommitButton,
  ConsequenceBox,
  ErrandLink,
  FormField,
  KVList,
  SectionTitle,
  TextInput,
  TwoCol,
  TwoUp,
  usePortalPath,
} from "../components/primitives";
import { formatMoney } from "../signin/Enrol";
import { Panel } from "@/components/Panel";
import {
  findAccountToAdd,
  verifyAccountToAdd,
  type AddAccountFound,
  type PortalAccount,
} from "../api/portalClient";
import { Announced } from "../components/a11y";

/**
 * `CWP-020` — two steps, and the second one is the whole guard.
 *
 * ⚠ **THE CODE GOES TO THE ACCOUNT BEING ADDED, NOT TO THE PERSON ADDING IT**
 * (`BR-CWP-033`). The screen says so before the button, because a customer who
 * does not expect that will type their own phone number into the field above
 * and then wonder why nothing arrived. An account number and a postcode are
 * both printed on a bill anybody could pick up, so matching proves nothing —
 * reading a message sent to the account's own contact is what proves it.
 *
 * ⚠ **AND THE CONSEQUENCE PANEL SAYS WHAT IS *NOT* HAPPENING** (`BR-CWP-039`,
 * `BR-CWP-015`). *Nothing is combined — bills stay separate* is the sentence a
 * landlord needs before pressing the button, because the obvious reading of
 * *add this account to my login* is that the two bills become one.
 */
export function AddAccountView(props: {
  accounts: PortalAccount[];
  /** What each account owes, by account id. ⚠ **THE RAIL DREW THE ACCOUNT
   *  NUMBER HERE** (`DEF-CWP-4138`) — the number the customer is about to
   *  type into the box on the left, so the rail answered the question the
   *  form was already asking. The drawing puts the BALANCE beside every
   *  address, which is the fact a landlord opens this screen holding in
   *  mind. Optional, because a set with no balance read yet must render the
   *  addresses rather than nothing (`BR-CWP-093`). */
  owing?: Record<string, { owing: string | null; currency: string | null }>;
}) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const [number, setNumber] = useState("");
  const [postcode, setPostcode] = useState("");
  const [code, setCode] = useState("");
  const [found, setFound] = useState<AddAccountFound | null>(null);
  const [linked, setLinked] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  function look() {
    setWorking(true);
    setRefusal(null);
    findAccountToAdd({ account_number: number, postcode })
      .then((answer) => {
        setWorking(false);
        if (answer.matched && answer.account_ref) {
          setFound(answer);
          return;
        }
        // B14 rule 35 — the server sends a REASON and the catalogue writes the
        // sentence, in the reader's own language.
        setRefusal(t(`portal.addAccount.reason.${answer.reason ?? "not_matched"}`));
      })
      .catch(() => {
        setWorking(false);
        setRefusal(t("portal.addAccount.reason.not_matched"));
      });
  }

  function prove() {
    if (found?.account_ref == null) return;
    setWorking(true);
    setRefusal(null);
    verifyAccountToAdd({ account_ref: found.account_ref, code })
      .then((answer) => {
        setWorking(false);
        if (answer.linked) {
          setLinked(true);
          return;
        }
        setRefusal(t(`portal.addAccount.reason.${answer.reason ?? "wrong"}`));
      })
      .catch(() => {
        setWorking(false);
        setRefusal(t("portal.addAccount.reason.wrong"));
      });
  }

  /**
   * ⚠ **THE RAIL THIS SCREEN NEVER HAD** — `DEF-CWP-3984`, audit row D9. The
   * drawing gives `CWP-020` a right-hand `Panel` **ALREADY ON THIS LOGIN**
   * with a brand count in its header, and the screen composed no `Panel` at
   * all, so it was a form on an empty page.
   *
   * ⚠ **IT IS THE ONE FACT THIS FORM NEEDS AND COULD NOT SHOW.** A landlord
   * typing an account number has no way to tell whether it is already on the
   * login; the refusal for a duplicate arrives only after a round trip, and
   * the code that proves it goes to the ACCOUNT's own contact rather than to
   * them (`BR-CWP-033`). Seeing the set is what stops the wasted attempt.
   *
   * ⚠ **THE MONEY COLUMN THE DRAWING SHOWS IS NOT SERVED AND IS NOT INVENTED.**
   * `PortalAccount` carries the label, the number and the permissions and no
   * balance; the session read is the account SET, not four account summaries.
   * The number on the paper takes that column instead — it is the thing being
   * typed into the field on the left, so it is the more useful half anyway,
   * and it is a printed number rather than a database id (B14 rule 31).
   *
   * ⚠ **REQUIRED PROP, NOT OPTIONAL** (hard-won law 2, `G13`): an optional one
   * that the page forgets to pass renders nothing while every test passes.
   */
  /**
   * ⚠ **THE DISTINCTION THAT MAKES THIS SCREEN SAFE, AND IT WAS NOT ON IT.**
   * The captured wireframe gives `CWP-020` a second panel — *Taking over an
   * account?* — and its own caption says why: *"Adding an account to a view is
   * not taking one over. The screen says so and routes a transfer to the
   * phone, because a change of responsible party has legal and deposit
   * consequences a form cannot settle."* The form said what adding DOES
   * (*nothing is combined*); it never said what it does NOT do. Somebody who
   * has bought a house, or whose tenant has left, would type the number in,
   * fail the code that goes to the OLD holder's contact, and have no idea what
   * to do next.
   *
   * ⚠ **THE DRAWING WRITES A TELEPHONE NUMBER AND THIS DOES NOT, DELIBERATELY.**
   * No payload this screen reads carries a general enquiries number: the front
   * payload has `emergency_phone`, which is the line for a gas smell and a
   * burst main, and sending a change-of-name query to it would be worse than
   * saying nothing. `CWP-062` — *Visit us* — lists every office with its own
   * number and the actions it handles, `open_or_close_an_account` among them,
   * so the door goes there and the number stays the one the utility published
   * rather than one this file invented.
   */
  const takingOver = (
    <Panel
      as="aside"
      title={t("portal.addAccount.takingOverTitle", { defaultValue: "Taking over an account?" })}
      data-testid="add-account-taking-over"
    >
      {/* B14 rule 32 — ONE sentence, and it is the one that stops the wrong
          journey rather than a description of this one. */}
      <p className="m-0 text-body text-neutral-700" data-add-account-taking-over="">
        {t("portal.addAccount.takingOver", {
          defaultValue:
            "If the account is in somebody else's name, we have to change that for you — this form does not.",
        })}
      </p>
      <div className="mt-3">
        <ErrandLink label={t("portal.nav.visit")} to="/visit" />
      </div>
    </Panel>
  );

  const rail =
    props.accounts.length > 0 ? (
      <Panel
        as="aside"
        title={t("portal.addAccount.alreadyTitle")}
        data-testid="add-account-already"
        trailing={
          <span className="text-lead font-bold text-accent-text" data-already-count="">
            {props.accounts.length}
          </span>
        }
      >
        <KVList
          rows={props.accounts.map((account) => {
            const balance = props.owing?.[account.id];
            return {
              key: account.id,
              label: account.label,
              value:
                balance && balance.owing !== null
                  ? formatMoney(balance.owing, balance.currency)
                  : account.account_no,
            };
          })}
        />
      </Panel>
    ) : null;

  /** ⚠ **THE TWO PANELS TOGETHER, SO NEITHER CAN GO MISSING ON ITS OWN.** The
   *  rail is passed to `TwoCol` from three places in this file (the form, the
   *  code step and the confirmation); a lane adding a fourth would have had to
   *  remember both, which is the shape hard-won law 2 keeps costing us. */
  const rails = (
    <>
      {rail}
      {takingOver}
    </>
  );

  if (linked) {
    return (
      <div data-screen="CWP-020">
        <TwoCol
          main={
            <Card testId="add-account">
              <SectionTitle>{t("portal.addAccount.doneTitle")}</SectionTitle>
              <p className="mt-1 text-body text-neutral-700" data-add-account-done="">
                {t("portal.addAccount.done")}
              </p>
            </Card>
          }
          rail={rails}
        />
      </div>
    );
  }

  return (
    <div data-screen="CWP-020">
      {/* ⚠ `DEF-CWP-4000` — the shared `components/PageHeader.tsx`, never a
          second one. It sits ABOVE the two columns, which is where
          `08-screen-layouts.md` puts a head on every T3 screen: the rail a
          sibling lane added here is the drawing's ALREADY ON THIS LOGIN panel,
          and a head inside one column would be a title for half a page. */}
      <PageHeader
        kicker={t("portal.kicker.accounts")}
        title={t("portal.addAccount.title")}
        backTo={{ to: path("/accounts"), label: t("portal.accounts.title") }}
      />
      <TwoCol
        main={
      <Card testId="add-account">
        {/* B14 rule 32 — one sentence, and it is the two facts to go and find. */}
        <p className="mt-1 text-body text-neutral-600">{t("portal.addAccount.lead")}</p>

        {found === null ? (
          <>
            <div className="mt-4">
              <TwoUp>
                <FormField id="add-number" label={t("portal.addAccount.number")} required>
                  <TextInput id="add-number" value={number} onChange={setNumber} />
                </FormField>
                <FormField id="add-postcode" label={t("portal.addAccount.postcode")} required>
                  <TextInput id="add-postcode" value={postcode} onChange={setPostcode} />
                </FormField>
              </TwoUp>
            </div>
            {/* `BR-CWP-039` — before the commit, never after it. */}
            <div className="mt-4" data-add-account-consequences="">
              <ConsequenceBox
                heading={t("portal.addAccount.consequenceHeading")}
                bullets={[
                  t("portal.addAccount.consequenceAdds"),
                  t("portal.addAccount.consequenceCode"),
                  // ⚠ The one a landlord actually needs.
                  t("portal.addAccount.consequenceSeparate"),
                ]}
              />
            </div>
          </>
        ) : (
          <div className="mt-4 flex flex-col gap-3" data-add-account-code="">
            <p className="text-body text-neutral-700">
              {t("portal.addAccount.sentTo", { masked: found.sent_to ?? "" })}
            </p>
            <FormField
              id="add-code"
              label={t("portal.addAccount.code")}
              required
              helper={t("portal.addAccount.codeHelper", {
                minutes: found.expires_in_minutes ?? 0,
              })}
            >
              <TextInput id="add-code" value={code} onChange={setCode} />
            </FormField>
          </div>
        )}

        {refusal !== null ? (
          <Announced tone="error" className="mt-3 text-body font-semibold text-danger-700" data-add-account-refusal="">
            {refusal}
          </Announced>
        ) : null}

        <div className="mt-4 flex items-center gap-2">
          {found === null ? (
            <CommitButton
              label={t("portal.addAccount.find")}
              working={working}
              ready={number.trim() !== "" && postcode.trim() !== ""}
              // B14 rule 33 — five words.
              reason={t("portal.addAccount.needBoth")}
              onClick={look}
            />
          ) : (
            <CommitButton
              label={t("portal.addAccount.add")}
              working={working}
              ready={code.trim() !== ""}
              reason={t("portal.addAccount.needCode")}
              onClick={prove}
            />
          )}
        </div>
      </Card>
        }
        rail={rails}
      />
    </div>
  );
}
