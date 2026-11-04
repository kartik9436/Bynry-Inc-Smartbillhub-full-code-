// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-059 (EP-CWP-10) — what is protecting your supply: three
//           lifetimes, three sentences. Screen: CWP-064 (blueprint `P50`)
// Rules:    BR-CWP-090 (three lifetimes, three sentences; never imply a hold is
//           permanent) · BR-CWP-091 (a hold stops a disconnection, NOT the
//           debt) · BR-CWP-089 (the portal shows protections; it never grants
//           one) · BR-CWP-093 (nothing empty ever appears) · B14 rule 21 ·
//           rule 31 · rule 32 · rule 35 · rule 36
// Tests:    src/portal/arrears/Protections.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getProtections`
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

import { ErrandLink, ProtectionCard, TwoCol, usePortalPath } from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { Panel } from "@/components/Panel";
import { getProtections, type PortalProtection, type PortalProtections } from "../api/portalClient";

/**
 * `CWP-064` — three cards, and **each one has a different shape because each
 * one has a different lifetime** (`BR-CWP-090`).
 *
 * ⚠ **THE MIDDLE CARD IS THE ONE THAT SAVES MONEY.** A payment-plan hold has NO
 * end date and the screen must not invent one: it lifts the day an instalment is
 * missed, and a customer who believes it is permanent stops paying and is cut
 * the week it lapses. The product enforces that difference at the database
 * (`ck_protection_lifetime`), and this screen says it in words instead of
 * drawing a blank date cell.
 *
 * ⚠ **A CERTIFICATE NAMES ITS END DATE AND SAYS IN WORDS THAT IT IS NOT
 * PERMANENT.** §14 states as a rule that the customer must be told the expiry in
 * words, and until this screen there was nowhere for those words to go.
 *
 * ⚠ **THE MORATORIUM HAS NO CONTROL.** The regulator sets the window and nobody
 * applies for it, so `ProtectionCard` is rendered with no `action`.
 *
 * ⚠ **AND ONE LINE RUNS ACROSS ALL THREE** (`BR-CWP-091`): *a hold stops a
 * disconnection. It does not stop the debt.* On the screen, not only in help.
 *
 * ⚠ **A LIFTED PROTECTION IS STILL HERE, MARKED LIFTED** — a hold that vanished
 * the day it lapsed is the customer who did not know it had.
 */
export function ProtectionsView(props: { accountId: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const [body, setBody] = useState<PortalProtections | null>(null);
  const [failed, setFailed] = useState(false);
  //: R-10's *Try again* needs something to try — see `Overdue.tsx`.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getProtections(props.accountId)
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
      title={t("portal.protections.title")}
    />
  );

  // ⚠ **R-10 — A CUSTOMER WHO CANNOT READ THIS SCREEN IS A CUSTOMER WHO DOES
  // NOT KNOW WHETHER THEY ARE PROTECTED** (PO 2026-09-11). The failure card
  // carries the same door the *not protected* branch below already carries,
  // because the question behind both is identical: *what can I still do?*
  const failedWaysOut: PortalWayOut[] = [
    {
      label: t("portal.payNow.tryAgain"),
      onClick: () => setAttempt((n) => n + 1),
      tone: "primary",
      testKey: "try-again",
    },
    { label: t("portal.overdue.helpPaying"), to: path("/help-paying"), testKey: "help-paying" },
  ];

  if (failed) {
    return (
      <PortalScreen screen="CWP-064" head={head}>
        <PortalState
          kind="failed"
          testId="protections"
          sentence={t("portal.protections.couldNotRead")}
          waysOut={failedWaysOut}
        />
      </PortalScreen>
    );
  }
  if (body === null) {
    return (
      <PortalScreen screen="CWP-064" head={head}>
        <PortalState kind="loading" testId="protections" sentence={t("portal.protections.reading")} />
      </PortalScreen>
    );
  }
  if (!body.any) {
    // ⚠ `BR-CWP-093` — one sentence, **not three empty cards**.
    return (
      <PortalScreen screen="CWP-064" head={head}>
        {/* ⚠ **THE DOOR MOVED INTO THE CARD AND IS STILL THE SAME DOOR.** It
            was an `ErrandLink` under the sentence; `PortalState`'s `waysOut`
            renders it in the same place with the kit's own button, which is
            R-10's *"next to the message"* made structural rather than
            remembered. */}
        <PortalState
          kind="empty"
          testId="protections"
          sentence={t("portal.protections.none")}
          waysOut={[
            { label: t("portal.overdue.helpPaying"), to: path("/help-paying"), testKey: "help-paying" },
          ]}
        >
          {/* ⚠ **THE DRAWING'S *not protected* STATE IS *"neutral, not
              alarming: says which could apply and links each application"***
              (wireframe screen 46), and this branch said only that nothing was
              holding anything and stopped. A frightened customer reads that as
              a verdict.
              ⚠ **AND IT DOES NOT LIST THE PROTECTIONS HERE.** Which ones exist
              is tenant-configured — this screen's own rule is that every row is
              configured, never hard-coded — so naming winter, medical or
              military in this file would be four utilities' rules written into
              one. `CWP-056` is the configured list, served per tenant, and it
              is one hop away. */}
          <p className="m-0 text-body text-neutral-700" data-protections-what-next="">
            {t("portal.protections.whatCouldHelp")}
          </p>
        </PortalState>
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-064">
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
      <TwoCol
        main={
          <div className="flex flex-col gap-4">
            {body.protections.map((row) => (
              <OneProtection key={`${row.kind}-${row.since ?? ""}`} row={row} />
            ))}
          </div>
        }
        rail={
          // ⚠ `BR-CWP-091` — on the screen, not only in help, and worded so it
          // cannot be read as reassurance.
          <Panel as="aside" tone="warning" title={t("portal.protections.warningHeading")}>
            <p className="m-0 text-body text-neutral-800" data-hold-warning="">
              {t("portal.protections.holdDoesNotStopTheDebt")}
            </p>
          </Panel>
        }
      />
    </div>
  );
}

/**
 * What a customer can DO about this protection — `DEF-CWP-4145`, and it is
 * hard-won law 2 in its purest form.
 *
 * ⚠ **`ProtectionCard` HAS ACCEPTED AN `action` SINCE THE DAY IT WAS WRITTEN
 * AND NOTHING HAS EVER PASSED ONE.** An optional prop nothing passes is dead
 * UI: the component renders, `tsc` is happy, every DOM assertion passes, and
 * the feature does not exist. The drawing marks all three cards — *→ Apply*,
 * *→ Ask for one*, *Send a new certificate*.
 *
 * ⚠ **AND ONE OF THE THREE STILL GETS NOTHING, DELIBERATELY.** The weather
 * moratorium is a window the regulator sets; nobody applies for it and nobody
 * can be given it. This file's own docstring has said so since it was written,
 * and a control there would invite somebody to ask for a thing they already
 * have and could not be refused. `undefined` draws no row at all.
 *
 * ⚠ **NEITHER DOOR IS NEW AND NEITHER LABEL IS NEW.** The plan card opens the
 * plan screen the hold is derived FROM, which is where *when does this lift*
 * is actually answered; the certificate card opens the route that takes one,
 * carrying `CWP-056`'s own five-word label. Inventing a fourth destination for
 * an assistance programme would be building to `R-18`, which is a PROPOSAL and
 * not law — nothing in this product stores an assistance programme.
 */
function protectionAction(
  kind: string,
  t: (key: string) => string,
): { label: string; to: string } | null {
  if (kind === "payment_plan") return { label: t("portal.yourPlan.title"), to: "/plan" };
  if (kind === "medical_certificate") {
    return { label: t("portal.helpPaying.route.medical_certificate.action"), to: "/help-paying" };
  }
  return null;
}

/** One protection, and **the lifetime picks which sentence it gets.** */
function OneProtection(props: { row: PortalProtection }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const { row } = props;
  const lifted = row.lifted_on !== null;
  //: ⚠ **A LIFTED PROTECTION KEEPS ITS DOOR.** Somebody reading *lifted on
  //: 08/12/2026* is exactly the person who wants to send a new certificate or
  //: look at their plan; taking the control away at the moment it becomes
  //: useful is the shape `DEF-CWP-3925` describes one layer up.
  const action = protectionAction(row.kind, t);
  return (
    <ProtectionCard
      cardKey={row.kind}
      // ⚠ **A HEADING, NOT THE IN-SENTENCE NOUN.** `portal.protections.kind.*`
      // is written to be inserted into *"A {{kind}} is holding your supply"* on
      // `CWP-057`, so it is lower-case by design — and reusing it as a card
      // title printed *doctor's certificate* as a heading on three cards. The
      // two uses want two spellings, which is a key each, in eleven languages.
      title={t(`portal.protections.heading.${row.kind}`)}
      chip={{
        tone: lifted ? "neutral" : row.in_force ? "success" : "info",
        label: lifted
          ? t("portal.protections.chip.lifted")
          : row.in_force
            ? t("portal.protections.chip.holdingNow")
            : t("portal.protections.chip.notYet"),
      }}
      since={
        row.since !== null ? t("portal.protections.since", { date: asDate(row.since) }) : undefined
      }
      endsLabel={t("portal.protections.endsOn")}
      ends={
        lifted ? (
          <span data-ends={row.kind}>{t("portal.protections.liftedOn", { date: asDate(row.lifted_on) })}</span>
        ) : row.lifetime === "derived_from_the_plan" ? (
          // ⚠ **NO DATE, AND NONE INVENTED.** A plan hold is not a period; the
          // sentence is what ends it. An em-dash here is the customer who
          // believes the hold is permanent.
          <span className="font-normal text-neutral-600" data-ends="no-date">
            {t("portal.protections.noEndDate")}
          </span>
        ) : (
          <span data-ends={row.kind}>{asDate(row.ends_on)}</span>
        )
      }
      body={t(`portal.protections.body.${row.lifetime}`, {
        date: asDate(row.ends_on),
        from: asDate(row.since),
      })}
      action={
        action === null ? undefined : <ErrandLink label={action.label} to={action.to} />
      }
    />
  );
}
