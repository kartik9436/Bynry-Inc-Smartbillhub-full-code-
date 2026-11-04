// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-028 (EP-CWP-06) — my details. Screen: CWP-024 (blueprint `P10`)
// Rules:    BR-CWP-001 kind ⑤ `contact_detail` (PO ruling 2026-09-04,
//           `OQ-CWP-1562`) · BR-CWP-103 (the security is at the door) ·
//           BR-CWP-026 (the legal name and the account holder are refused,
//           with a route into a request) · BR-CWP-086 (returned post shows
//           ABOVE the address field) · B14 rule 17 (an empty state says what
//           fills it) · rule 21 (Tailwind utilities; `portal/` is on
//           route-b-migrated.txt) · rule 31 (no database id on screen) ·
//           rule 32 (one sentence per section) · rule 33 (a refusal is five or
//           six words) · rule 35 (the catalogue writes the words) · rule 36
//           (compose the kit)
// Defects:  DEF-CWP-4016 (the drawing names `TwoEqual` in the kit's own words
//           and this composed `TwoCol`; the right column's two cards needed
//           `TwoEqual` to gain the spacing `DEF-CWP-3984` gave `TwoCol`)
// Tests:    src/portal/details/MyDetails.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getMyDetails` · `saveMyDetails`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { US_ZIP } from "@/components/UsAddressFields";
import { phoneFormatProblem } from "@/features/customers/customerForm/CustomerWhoPanel";
import { Announced, FormScope, usePortalForm } from "../components/a11y";
import { onDate } from "../components/content";
import { PortalScreen, PortalState } from "../components/states";

import {
  Card,
  CommitButton,
  FormField,
  InfoBar,
  KVList,
  SectionTitle,
  TextInput,
  TwoEqual,
  TwoUp,
  WhereNext,
} from "../components/primitives";
import {
  getMyDetails,
  saveMyDetails,
  type PortalMyDetails,
  type PortalPostal,
} from "../api/portalClient";
import { EmailCodeStep, startEmailCode, type PendingEmail } from "./EmailCodeStep";

type SaveAnswer = Awaited<ReturnType<typeof saveMyDetails>>;

const BLANK_POSTAL: PortalPostal = {
  line1: null,
  line2: null,
  city: null,
  state: null,
  postal_code: null,
  country: null,
};

/**
 * `CWP-024` — the three things a customer may fix, and the two they may not.
 *
 * ⚠ **THE REFUSED FIELDS ARE ON THE SCREEN, READ-ONLY, WITH THEIR ROUTE**
 * (`BR-CWP-026`). Hiding the legal name would read as an oversight and send
 * somebody hunting for it; showing it beside *Ask us to change this* reads as
 * a rule, which is what it is. Those two fields are what a deposit
 * carry-forward and a duplicate check are decided on, so a portal that
 * rewrote them would put a money decision behind an unverified form.
 *
 * ⚠ **AND THE SCREEN SAYS HOW FAR THE SAVE REACHES, BEFORE IT HAPPENS.** One
 * save writes every account this login holds — Maria's four — because
 * `contacts` hangs off the ACCOUNT and three bills still going to an old
 * address is not a state a customer could see or fix. The line is above the
 * button, not in a toast afterwards.
 *
 * ⚠ **THERE IS NO SECOND PASSWORD PROMPT AND THAT IS `BR-CWP-103`.** The
 * Product Owner's ruling of 2026-09-04 puts the whole defence at the door —
 * the one-time code, three tries, the lockout, the session's lifetime — and a
 * customer who is in is not asked to prove themselves again to edit their own
 * record. The account-set filter is still in every query on the server.
 */
export function MyDetailsView() {
  const { t } = useTranslation();
  const [held, setHeld] = useState<PortalMyDetails | null>(null);
  const [failed, setFailed] = useState(false);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [postal, setPostal] = useState<PortalPostal>(BLANK_POSTAL);
  const [working, setWorking] = useState(false);
  const [saved, setSaved] = useState<SaveAnswer | null>(null);
  // F-11 (`DEF-CWP-10549`): the two boxes the ruling names, refused on the
  // field — on the screen first, and by the server too (same checks).
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [zipError, setZipError] = useState<string | null>(null);
  const form = usePortalForm();
  const [refused, setRefused] = useState<string | null>(null);
  // ⊕ PO 2026-10-22 — the code step for a NEW email, and whether it moved.
  const [pending, setPending] = useState<PendingEmail | null>(null);
  const [emailMoved, setEmailMoved] = useState(false);

  useEffect(() => {
    let live = true;
    getMyDetails()
      .then((answer) => {
        if (!live) return;
        setHeld(answer);
        setEmail(answer.email ?? "");
        setPhone(answer.phone ?? "");
        setPostal(answer.postal ?? BLANK_POSTAL);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, []);

  // ⚠ **THE HEAD IS BUILT ONCE, ABOVE THE BRANCHES, AND RENDERS ON EVERY ONE
  // OF THEM — `DEF-CWP-4926` (`CR-085` step 2).** It was declared INSIDE the
  // success branch, below `if (failed) return …`, so a failed or a slow read
  // threw away the page title, the `data-screen` mark every rendered check in
  // this repo selects on, and the drawing's whole top row of controls — the
  // one row that could have got the customer anywhere else. Ten signed-in
  // screens shared that single misplaced `return`; `arrears/Overdue.tsx` is
  // the model that already did it this way. R-10 (PO 2026-09-11: *"when a
  // screen tells a customer something bad, the thing they can do about it must
  // be on that same screen"*) cannot be met by a branch that renders no
  // controls at all.
  const head = (
    <PageHeader kicker={t("portal.kicker.myDetails")} title={t("portal.myDetails.title")} />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-024" head={head}>
        <PortalState kind="failed" testId="my-details" sentence={t("portal.myDetails.couldNotRead")} />
      </PortalScreen>
    );
  }
  if (held === null) {
    return (
      <PortalScreen screen="CWP-024" head={head}>
        <PortalState kind="loading" testId="my-details" sentence={t("portal.myDetails.reading")} />
      </PortalScreen>
    );
  }

  const changed =
    email !== (held.email ?? "") ||
    phone !== (held.phone ?? "") ||
    JSON.stringify(postal) !== JSON.stringify(held.postal ?? BLANK_POSTAL);

  // ⊕ PO 2026-10-22 (Q2, option A; `DEF-CWP-10401`): a NEW email is not saved
  // here. A code goes to it, and only the code moves the contact email AND the
  // sign-in email together. Phone and mailing address save as before.
  const emailChanged = email.trim() !== (held.email ?? "");
  const restChanged =
    phone !== (held.phone ?? "") ||
    JSON.stringify(postal) !== JSON.stringify(held.postal ?? BLANK_POSTAL);

  function commit() {
    const badPhone = phone.trim() !== "" && phoneFormatProblem(phone) !== null;
    const zip = (postal.postal_code ?? "").trim();
    const badZip = zip !== "" && !US_ZIP.test(zip);
    setPhoneError(badPhone ? t("portal.myDetails.phoneFormat") : null);
    setZipError(badZip ? t("portal.myDetails.zipFormat") : null);
    if (badPhone || badZip) {
      setSaved(null);
      setRefused(null);
      form.failed();
      return;
    }
    setWorking(true);
    setRefused(null);
    setSaved(null);
    const saving: Promise<"saved" | "refused"> = restChanged
      ? saveMyDetails({ phone, postal })
          .then((answer) => {
            setSaved(answer);
            return "saved" as const;
          })
          .catch((error: unknown) => {
            // The server's own refusal of the same two boxes, on the boxes.
            const fields = error instanceof ApiError ? error.fieldErrors : [];
            const phoneRefusal = fields.find((one) => one.field === "phone");
            const zipRefusal = fields.find((one) => one.field === "postal_code");
            if (phoneRefusal === undefined && zipRefusal === undefined) throw error;
            setPhoneError(phoneRefusal ? t(phoneRefusal.message_key) : null);
            setZipError(zipRefusal ? t(zipRefusal.message_key) : null);
            form.failed();
            return "refused" as const;
          })
      : Promise.resolve("saved" as const);
    saving
      .then(async (outcome) => {
        if (outcome === "refused") {
          setWorking(false);
          return undefined;
        }
        const started = emailChanged ? await startEmailCode(email.trim()) : null;
        setWorking(false);
        if (started === null) return getMyDetails().then((fresh) => setHeld(fresh));
        if (started.pending !== null) {
          setPending(started.pending);
          return undefined;
        }
        setRefused(t(started.refusal ?? "portal.myDetails.couldNotSave"));
        return undefined;
      })
      .catch(() => {
        setWorking(false);
        setRefused(t("portal.myDetails.couldNotSave"));
      });
  }

  function emailConfirmed() {
    setPending(null);
    setEmailMoved(true);
    void getMyDetails().then((fresh) => setHeld(fresh));
  }

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names and the
  // one fifteen portal files already use — never a second one.
  //
  // ⚠ **NO ACTION IN THE HEAD.** The drawing gives this screen none: its only
  // commit is *Save changes*, which belongs to the form it saves and is
  // already there. An empty action row is what `PageHeader` renders without
  // the title shifting (TC-3).
  return (
    <div data-screen="CWP-024">
      {head}
      <TwoEqual
        left={
          <Card testId="my-details">
            {/* B14 rule 32 — ONE sentence, and it is the one a customer needs
                before they type: how far this goes. */}
            <p className="mt-1 text-body text-neutral-600" data-my-details-reach="">
              {held.account_count > 1
                ? t("portal.myDetails.reachMany", { count: held.account_count })
                : t("portal.myDetails.reachOne")}
            </p>

            {/* ⚠ `BR-CWP-086` — ABOVE the address field, because that is where
                somebody about to correct it is already looking. */}
            {held.returned_post_accounts > 0 ? (
              <div className="mt-3" data-returned-post="">
                <InfoBar
                  lead={t("portal.myDetails.returnedPostLead")}
                  bold={t("portal.myDetails.returnedPostCount", {
                    count: held.returned_post_accounts,
                  })}
                />
              </div>
            ) : null}

            <FormScope form={form}>
            <div className="mt-4 flex flex-col gap-4">
              <TwoUp>
                <FormField
                  id="my-email"
                  label={t("portal.myDetails.email")}
                  helper={held.email_varies ? t("portal.myDetails.varies") : undefined}
                >
                  <TextInput id="my-email" type="email" value={email} onChange={setEmail} />
                </FormField>
                <FormField
                  id="my-phone"
                  label={t("portal.myDetails.mobile")}
                  helper={held.phone_varies ? t("portal.myDetails.varies") : undefined}
                  error={phoneError}
                >
                  <TextInput
                    id="my-phone"
                    value={phone}
                    onChange={(value) => {
                      setPhone(value);
                      setPhoneError(null);
                    }}
                  />
                </FormField>
              </TwoUp>

              {/* ⚠ **THE HONEST REFUSAL, BESIDE THE FIELD RATHER THAN
                  INSTEAD OF IT** — the drawing names this as the one thing
                  `CWP-024` must get right: *"the service address cannot be
                  changed here, and the screen says so beside it rather than
                  offering a field that fails. Where the bill goes is genuinely
                  separate and genuinely editable."* This screen offered ONE
                  unlabelled address and said neither half, so a customer who
                  had moved could reasonably type their new house into it and
                  believe they had told us where they now take water.
                  ⚠ **AND THE SERVICE ADDRESS IS NOT REPEATED HERE.** It is on
                  the account bar at the top of every signed-in screen, drawn
                  from `premises` (hard rule 8), and a second copy on this page
                  is a second place it could go stale — the account bar names
                  the account it belongs to and this page is not per account. */}
              <p className="text-base text-neutral-600" data-postal-note="">
                {t("portal.myDetails.postalIsWhereTheBillGoes")}
              </p>
              <FormField
                id="my-postal-line1"
                label={t("portal.myDetails.postal")}
                helper={held.postal_varies ? t("portal.myDetails.varies") : undefined}
              >
                <TextInput
                  id="my-postal-line1"
                  value={postal.line1 ?? ""}
                  onChange={(value) => setPostal({ ...postal, line1: value })}
                />
              </FormField>
              <TwoUp>
                <FormField id="my-postal-city" label={t("portal.myDetails.city")}>
                  <TextInput
                    id="my-postal-city"
                    value={postal.city ?? ""}
                    onChange={(value) => setPostal({ ...postal, city: value })}
                  />
                </FormField>
                <FormField id="my-postal-code" label={t("portal.myDetails.postcode")} error={zipError}>
                  <TextInput
                    id="my-postal-code"
                    value={postal.postal_code ?? ""}
                    inputMode="numeric"
                    onChange={(value) => {
                      setPostal({ ...postal, postal_code: value });
                      setZipError(null);
                    }}
                  />
                </FormField>
              </TwoUp>
            </div>
            </FormScope>

            {refused !== null ? (
              <Announced tone="error" className="mt-3 text-body font-semibold text-danger-700" data-my-details-refused="">
                {refused}
              </Announced>
            ) : null}
            {saved !== null ? (
              // F-02 / F-11: heard and focused. *"Saved on 0 accounts."* is
              // never shown — a save that changed nothing says so instead.
              <Announced tone="status" as="div" className="mt-3 flex flex-col gap-1" data-my-details-saved="">
                <p className="text-body text-neutral-700">
                  {saved.accounts_updated > 0
                    ? t("portal.myDetails.saved", { count: saved.accounts_updated })
                    : t("portal.myDetails.savedNone")}
                </p>
                {saved.phone_removed ? (
                  <p className="text-body text-neutral-700" data-my-details-phone-removed="">
                    {t("portal.myDetails.phoneRemoved")}
                  </p>
                ) : null}
                {saved.phone_removed && saved.text_reminders_on ? (
                  <p className="text-body text-neutral-700" data-my-details-reminders-stop="">
                    {t("portal.myDetails.textRemindersStop")}
                  </p>
                ) : null}
              </Announced>
            ) : null}
            {/* ⊕ PO 2026-10-22 (Q2, option A) — the code went to the NEW
                address; nothing has moved until it comes back here. */}
            {pending !== null ? (
              <div className="mt-4">
                <EmailCodeStep
                  pending={pending}
                  onResent={setPending}
                  onDone={emailConfirmed}
                  onCancel={() => {
                    setPending(null);
                    setEmail(held.email ?? "");
                  }}
                />
              </div>
            ) : null}
            {emailMoved && pending === null ? (
              <p className="mt-3 text-body text-neutral-700" data-my-details-email-moved="">
                {t("portal.myDetails.emailCode.done")}
              </p>
            ) : null}

            <div className="mt-4 flex items-center gap-2">
              <CommitButton
                label={t("portal.myDetails.save")}
                working={working}
                ready={changed}
                // B14 rule 33 — five words, on the control, not in a footnote.
                reason={t("portal.myDetails.nothingChanged")}
                onClick={commit}
              />
            </div>

            {/* ⚠ **THE DOOR TO `CWP-025`, AND WITHOUT IT THAT SCREEN DOES NOT
                EXIST** (hard-won law 2: *built is not wired* — a route nothing
                links to renders nothing, every test passes, and the feature is
                not there). `08-screen-layouts.md` numbers *How we contact you*
                as its own screen with its own template, and the shell's six
                tabs are fixed by `CR-068` §9, so this is where a customer
                reaches it: beside the details it is about. */}
            {/* ⚠ **AND THE SAME GAP AGAIN, THREE SCREENS WIDE**
                (`DEF-CWP-3954`). `CWP-023` *All my accounts*, `CWP-065` *Your
                account* and `CWP-020` *Add another account* were all shipped,
                routed and tested, and nothing in the product pointed at any of
                them — a landlord with three properties could not open the list
                of them. `08-screen-layouts.md` draws `CWP-065` inside this tab
                (*`PortalShell` (My details active)*) and heads `CWP-023` with
                **YOUR ACCOUNTS**, which is what this page is about, so this is
                where the doors go. *Add another account* is not here: it is an
                action ON the account list, which is where that layout puts it
                and where somebody looking at three accounts asks for a fourth. */}
            <WhereNext
              mark="my-details"
              doors={[
                {
                  key: "preferences",
                  label: t("portal.myDetails.howWeContactYou"),
                  to: "/my-details/preferences",
                },
                { key: "accounts", label: t("portal.accounts.title"), to: "/accounts" },
                { key: "account", label: t("portal.yourAccount.title"), to: "/account" },
                /* ⚠ The SECOND door to `/stop-or-restart` (`DEF-CWP-4654`).
                   `YourAccount` carries the first, and it is the better one —
                   stopping is done to one property. This one exists because
                   *my details* is where a person goes looking for anything
                   about their own arrangements, and the defect that made this
                   necessary was found by exactly that expectation being wrong. */
                {
                  key: "stop-or-restart",
                  label: t("portal.stopRestart.title"),
                  to: "/stop-or-restart",
                },
              ]}
            />
          </Card>
        }
        right={
          <>
            <RefusedPanel name={held.legal_name} />
            <SecurityPanel details={held} />
          </>
        }
      />
    </div>
  );
}

/** `BR-CWP-026` — shown, refused, and pointed somewhere. */
function RefusedPanel(props: { name: string | null }) {
  const { t } = useTranslation();
  return (
    <Card testId="my-details-refused">
      <SectionTitle>{t("portal.myDetails.notHereTitle")}</SectionTitle>
      <div className="mt-2">
        <KVList
          rows={[
            {
              key: "legal_name",
              label: t("portal.myDetails.legalName"),
              // ⚠ The VALUE, not a dash. A customer checking whether we hold
              // the right name has to be able to read it.
              value: <span data-legal-name="">{props.name ?? t("portal.myDetails.notOnFile")}</span>,
            },
            {
              key: "account_holder",
              label: t("portal.myDetails.accountHolder"),
              value: <span className="text-neutral-600">{t("portal.myDetails.askUs")}</span>,
            },
          ]}
        />
      </div>
      <p className="mt-2 text-base text-neutral-600">{t("portal.myDetails.notHereWhy")}</p>
    </Card>
  );
}

/** The facts a worried customer checks. ⚠ **FACTS, NOT CONTROLS** — *sign out
 *  everywhere* is its own action on `CWP-019` and is not implied by anything
 *  being listed here. */
function SecurityPanel(props: { details: PortalMyDetails }) {
  const { t, i18n } = useTranslation();
  const { details } = props;
  return (
    <Card testId="my-details-security">
      <SectionTitle>{t("portal.myDetails.securityTitle")}</SectionTitle>
      <div className="mt-2">
        <KVList
          rows={[
            {
              key: "password_changed_on",
              label: t("portal.myDetails.passwordChanged"),
              value: details.security.password_changed_on
                ? onDate(details.security.password_changed_on, i18n.language)
                : t("portal.myDetails.never"),
            },
            {
              key: "code_channel",
              label: t("portal.myDetails.codesGoTo"),
              value:
                details.security.code_channel === null
                  ? t("portal.myDetails.notOnFile")
                  : t(`portal.myDetails.channel.${details.security.code_channel}`),
            },
            {
              key: "devices_signed_in",
              label: t("portal.myDetails.devices"),
              value: String(details.security.devices_signed_in),
            },
          ]}
        />
      </div>
    </Card>
  );
}
