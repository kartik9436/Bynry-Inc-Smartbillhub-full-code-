// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-058 (EP-CWP-10) — help paying: three doors, and one of them
//           is not a door. Screen: CWP-056 (blueprint `P42`)
// Rules:    BR-CWP-089 (the portal never grants a protection; each needs a
//           person and a document) · BR-CWP-090 (three lifetimes, three
//           sentences — never imply a hold is permanent) · BR-CWP-066 (a plan
//           is granted by a clerk; a customer may only ASK) · BR-CWP-093 ·
//           B14 rule 21 · rule 31 · rule 32 · rule 33 · rule 35 · rule 36
// Open:     OQ-CWP-1601 — `P42` reads *"ask before the final notice and all
//           three stay open"*; nothing in this product closes any of them, so
//           all three stay open and the urgency is said in words instead.
// Tests:    src/portal/arrears/HelpPaying.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getHelpPaying` · `askForHelpPaying`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

// ⚠ **DATES GO THROUGH THE TENANT'S OWN FORMAT, NEVER STRAIGHT TO THE SCREEN**
// (`DEF-CWP-4138`'s fix, which wave M's five screens took and these four did
// not). `usePortalDate` returns the server's string unchanged when the tenant
// has set no drawable format — declining to state one is honest; inventing
// `MM/DD/YYYY` for a utility in Berlin is what shipped a five-hour error.
import { usePortalDate } from "../components/regional";

import {
  Card,
  CardGrid3,
  CommitButton,
  ErrandCard,
  ErrandLink,
  InfoBar,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import {
  askForHelpPaying,
  getHelpPaying,
  type PortalHelpPaying,
} from "../api/portalClient";
import { Announced } from "../components/a11y";

/**
 * `CWP-056` — *"There are three things we can do."*
 *
 * ⚠ **ONE OF THE THREE IS NOT A DOOR AT ALL.** The weather moratorium is a
 * window the regulator sets and nobody applies for, so it is drawn as an
 * `InfoBar` stating a fact **with no control** — and its dates are read from
 * the record rather than written into the copy, so a state whose window moves
 * moves this sentence with it.
 *
 * ⚠ **NOTHING ON THIS SCREEN GRANTS A PROTECTION** (`BR-CWP-089`). *Send a
 * certificate* raises a service request a person judges, and the confirmation
 * says so: no hold is placed and the document is brought to the office, because
 * this portal accepts no upload.
 *
 * ⚠ **AND NO ROUTE IS CLOSED BECAUSE A WIREFRAME IMPLIED ONE MIGHT BE.** `P42`
 * reads *"ask before the final notice and all three stay open"*. Measured,
 * nothing in this product closes any of them — so all three stay open at every
 * tier and the screen says instead that time is short. **Closing a door the
 * product would still open turns a frightened customer away from help they can
 * still get** (`OQ-CWP-1601`).
 */
export function HelpPayingView(props: { accountId: string }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const path = usePortalPath();
  const [body, setBody] = useState<PortalHelpPaying | null>(null);
  const [failed, setFailed] = useState(false);
  const [working, setWorking] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  //: R-10's *Try again* needs something to try — see `Overdue.tsx` for why the
  //: retry is the effect's own re-run key rather than a prop on the card.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getHelpPaying(props.accountId)
      .then((answer) => {
        if (live) setBody(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names, which
  // fifteen portal files already used and twenty-eight signed-in screens did
  // not. A head that lived only in the happy-path return would leave the page
  // with no `<h1>` for as long as the request takes.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.help")}
      title={t("portal.helpPaying.title")}
    />
  );

  // ⚠ **R-10 — THE SCREEN SOMEBODY OPENS BECAUSE THEY CANNOT PAY MUST NOT END
  // IN A FULL STOP** (PO 2026-09-11). A failed read here left a person looking
  // for help reading *we could not read this* with no control of any kind.
  // ⚠ **`Ask for a payment plan` IS THE DOOR THIS SCREEN ITSELF OFFERS**, so
  // the failure card hands back one of the three routes rather than inventing
  // a fourth — and it needs no figure, which is why it survives a read that
  // did not.
  const failedWaysOut: PortalWayOut[] = [
    {
      label: t("portal.payNow.tryAgain"),
      onClick: () => setAttempt((n) => n + 1),
      tone: "primary",
      testKey: "try-again",
    },
    { label: t("portal.overdue.askForAPlan"), to: path("/ask-for-a-plan"), testKey: "ask-for-a-plan" },
  ];

  if (failed) {
    return (
      <PortalScreen screen="CWP-056" head={head}>
        <PortalState
          kind="failed"
          testId="help-paying"
          sentence={t("portal.helpPaying.couldNotRead")}
          waysOut={failedWaysOut}
        />
      </PortalScreen>
    );
  }
  if (body === null) {
    return (
      <PortalScreen screen="CWP-056" head={head}>
        <PortalState kind="loading" testId="help-paying" sentence={t("portal.helpPaying.reading")} />
      </PortalScreen>
    );
  }

  const ask = (route: string) => {
    setWorking(true);
    askForHelpPaying(props.accountId, { route })
      .then((answer) => setSent(answer.reference))
      .catch(() => setFailed(true))
      .finally(() => setWorking(false));
  };

  return (
    <div data-screen="CWP-056">
      {/* ⚠ **THE SCREEN ID IS A LITERAL HERE AND MUST STAY ONE — `CR-085` lane 8.**
          `PortalScreen` renders an identical DOM from its `screen` prop, but THREE
          source scanners find a portal screen by the exact string
          `data-screen="CWP-…"` and not one of them reads a prop: this census,
          `g100_every_screen_has_a_door.py` and `g103_holds_cannot_rot.py`. Wrapping
          this branch too made the whole file invisible to all three — hard-won law
          7’s *reporting zero over a scope it silently excluded*.
          `bills/BillDetail.tsx` keeps the literal on its populated branch for
          exactly this reason. */}
      {head}
      {body.past_final_notice ? (
        // ⚠ **THE URGENCY, NOT A CLOSED DOOR** — `OQ-CWP-1601`. Every route
        // below is still open; what has changed is how little time is left.
        <div className="mb-4">
          <InfoBar
            lead={t("portal.helpPaying.pastFinalLead")}
            bold={t("portal.helpPaying.pastFinalBold")}
          />
        </div>
      ) : null}
      {sent !== null ? (
        // ⚠ **THE REFERENCE IS THE WHOLE RECORD OF THE INTERACTION**
        // (`BR-CWP-028`), and the sentence says plainly that no hold is in
        // place yet and where the document goes.
        <div className="mb-4">
          <Card testId="help-paying-sent">
            <Announced tone="status" className="text-body text-neutral-800" data-ask-sent={sent}>
              {t("portal.helpPaying.sent", { reference: sent })}
            </Announced>
            <p className="text-body text-neutral-600" data-bring-document="">
              {t("portal.helpPaying.bringTheDocument")}
            </p>
          </Card>
        </div>
      ) : null}
      <CardGrid3>
        {body.routes.map((route) => (
          <ErrandCard
            key={route.route}
            cardKey={route.route}
            title={t(`portal.helpPaying.route.${route.route}.title`)}
            description={t(`portal.helpPaying.route.${route.route}.body`)}
            action={
              route.route === "payment_plan" ? (
                // `BR-CWP-066` — *Ask for a payment plan*, five words, and a
                // CLERK grants it. The wizard is one route along.
                <ErrandLink
                  label={t("portal.helpPaying.route.payment_plan.action")}
                  to="/ask-for-a-plan"
                />
              ) : route.route === "level_pay" ? (
                // ⚠ **THESE TWO, AND THE PAIR ON `CWP-057`, WERE ALL MISSING
                // THEIR LEADING SLASH** — `usePortalPath` concatenates, so
                // `to="level-pay"` resolved to `/pine-hill/portallevel-pay` and
                // opened nothing. Four dead doors on two screens neither of
                // which anybody could reach (`DEF-CWP-3954`). `G100` fails a
                // `to=` that names no registered screen.
                <ErrandLink
                  label={t("portal.helpPaying.route.level_pay.action")}
                  to="/level-pay"
                />
              ) : (
                <CommitButton
                  label={t("portal.helpPaying.route.medical_certificate.action")}
                  working={working}
                  ready={sent === null}
                  reason={t("portal.helpPaying.alreadyAsked")}
                  onClick={() => ask(route.route)}
                />
              )
            }
          />
        ))}
      </CardGrid3>
      {body.moratorium !== null ? (
        // ⚠ **NO BUTTON, AND THE ABSENCE IS THE POINT** — `InfoBar` is rendered
        // with no `trailing`, so there is no control to press. Nobody applies
        // for a weather moratorium.
        <div className="mt-4" data-moratorium="">
          <InfoBar
            lead={t("portal.helpPaying.moratoriumLead")}
            bold={t("portal.helpPaying.moratoriumWindow", {
              from: asDate(body.moratorium.from),
              until: asDate(body.moratorium.until) ?? "",
            })}
          />
        </div>
      ) : null}
    </div>
  );
}
