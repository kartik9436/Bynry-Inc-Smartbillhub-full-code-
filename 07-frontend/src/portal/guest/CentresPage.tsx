// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-074 (EP-CWP-12) — where you can walk in, and what each
//           place can actually do. Screens: CWP-013 (the list) · CWP-014 (one
//           centre)
// Rules:    08-screen-layouts.md CWP-013 (T3 under GuestFrame: PageHead VISIT
//           US → CentreCards → rail RATHER NOT TRAVEL? + Panel.Info holidays)
//           and CWP-014 (T6 + TwoCol: WHAT YOU CAN DO HERE rows *action · ✓ or
//           —* · TAKES PAYMENT BY · rail OPENING HOURS 7 rows, today's bold,
//           footer *Closed 26 November — <the holiday>* · Panel.Info *holidays
//           not typed*) — ⚠ *Call* is a PLAIN outline, not brand-outlined:
//           B14 rule 6 reserves the brand outline for destructive commits, and
//           the drawing is overruled (08-screen-layouts.md §*where the drawings
//           and B14 disagree*) · BR-CWP-093 · BR-CWP-096 · CR-068 R8 (a portal
//           that is OFF shows the holding page and nothing else, on EVERY
//           route) · R-10 (PO 2026-09-11 — the way out beside the bad news) ·
//           R-22 (PO 2026-09-11 — three states, three SENTENCES) · B14 rule 21
//           · 31 · 32 · 35
// Defects:  DEF-CWP-4851 (both screens served in full at a utility that had
//           not switched its portal on) · DEF-CWP-4853 (a member of the public
//           with no counter near them was shown the STAFF failure panel — a
//           red *Failed* chip and a **Download error report** button — outside
//           the frame, so with no phone number and no way back)
// Tests:    src/portal/guest/CentresPage.test.tsx ·
//           src/portal/guest/HelpAndCentres.test.tsx
// Impacts:  src/portal/api/guestClient.ts · routing/portalRoutes.tsx
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";

import { getPortalCentre, getPortalCentres, getPortalFront } from "../api/guestClient";
import {
  CentreCard,
  centreStatusLine,
  clockText,
  dayMonthText,
  weekdayText,
} from "../components/content";
import { StatusChip, TwoCol, usePortalPath } from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";

import { GuestPage } from "./GuestPage";

function useFront(client: ApiClient) {
  return useQuery({ queryKey: ["portal", "front"], queryFn: () => getPortalFront(client) });
}

/**
 * ⚠ **A 404 FROM THIS ENDPOINT IS AN *EMPTY*, NOT A *FAILURE* — `DEF-CWP-4853`,
 * AND IT IS THE WHOLE OF R-22 ON ONE SCREEN.**
 *
 * `GET portal/public/service-centres` answers **404 on purpose** when the
 * utility shows no counter (`BR-CWP-093`, `US-CWP-074` TC-5): the server
 * refuses the page rather than serving a heading with nothing under it. That
 * is right on the wire and it was read WRONGLY on the screen — the page handed
 * every error to `FailedWithRetry`, the STAFF panel, so a member of the public
 * whose utility has no walk-in counter was shown a red *Failed* chip, *"the
 * address may be wrong"* (blaming a visitor who typed nothing) and a
 * **Download error report** button they have nowhere to send.
 *
 * So this splits the two by STATUS: a 404 is the utility having nothing to
 * show, and anything else is a read that did not work. Two states, two
 * sentences, one card — R-22 as the PO ruled it.
 */
function isNotFound(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/** The phone a stranger rings when the page has nothing for them — R-10's
 *  *"the thing they can do about it must be on that same screen, next to the
 *  message"*, and the drawing's own `NONE CONFIGURED` state in one sentence:
 *  *"Falls back to the phone number rather than an empty page."*
 *
 *  ⚠ **IT IS A `tel:` ANCHOR AND THEREFORE NOT A `waysOut` ENTRY.**
 *  `PortalWayOut.to` renders the kit's `ButtonLink`, which is a router `Link`
 *  and would try to navigate `/{tenant}/portal/tel:…` inside the app. The kit
 *  already owns this exact control — `CWP-014`'s head action — so the same
 *  markup and the same `portal.centre.call` key are reused rather than a
 *  second spelling of *ring us* being invented (B14 rule 36, rule 35). */
function RingUs(props: { phone: string }) {
  const { t } = useTranslation();
  return (
    <a
      href={`tel:${props.phone.replace(/[^0-9+]/g, "")}`}
      data-action="call"
      className="inline-block border border-neutral-300 px-3 py-1 text-base font-semibold text-neutral-700"
    >
      {t("portal.centre.call", { phone: props.phone })}
    </a>
  );
}

// ══ CWP-013 · where you can walk in ════════════════════════════════════════

export function CentresPage(props: { client?: ApiClient }) {
  const { t, i18n } = useTranslation();
  // ⚠ **THE DOOR TO ONE CENTRE WAS BUILT AND POINTED AT NOTHING**
  // (`DEF-CWP-4655`, `CR-085`, 2026-09-08). `CentreCard` has always taken an
  // `href` and always drawn a *see this* link; this page handed it
  // `visit/${slug}` — RELATIVE, with no leading slash and no tenant. From
  // `/{tenant}/portal/visit` that resolves to
  // `/{tenant}/portal/visit/visit/{slug}`, which is not a route. So the list
  // showed three addresses and opened none of them, and the detail screen —
  // routed, rendered, tested — could only be reached by typing its address.
  //
  // ⚠ **THAT IS WORSE THAN NO LINK AT ALL AND IT IS WHY THIS COMMENT IS LONG.**
  // A missing door is visibly missing. A door that renders, reads correctly in
  // the source and goes to a 404 looks finished in every review, passes `tsc`,
  // and passes the page's own test, which asserts the link is PRESENT and never
  // asks where it goes. Use `usePortalPath` here as everywhere else — the one
  // helper that knows a portal address needs its tenant.
  const path = usePortalPath();
  const client = props.client ?? api;
  const language = i18n.language || "en";
  const front = useFront(client);
  // ⚠ **`enabled` — A SWITCHED-OFF PORTAL DOES NOT ASK THE SERVER FOR CONTENT**
  // (`DEF-CWP-4851`). `GuestPage` decides what a visitor SEES; this decides
  // what the browser FETCHES, and the two are not the same thing. Without it
  // this page would draw the holding notice and still pull the utility's list
  // of counters over the wire on a portal its owner has not opened.
  const live = front.data?.is_live === true;
  const centres = useQuery({
    queryKey: ["portal", "centres"],
    queryFn: () => getPortalCentres(client),
    enabled: live,
  });

  // ⚠ **THE HEAD IS BUILT ONCE, ABOVE THE BRANCHES** — `PortalScreen`'s own
  // rule, and `DEF-CWP-4926`'s cure. This screen used to `return` its failure
  // before the `PageHeader` line was ever reached, so the moment the read went
  // wrong the customer lost the page title, the product lost the
  // `data-screen` mark every rendered check selects on, and the screen lost
  // the row that could have got anybody anywhere else.
  //
  // ⚠ **AND A HEADING OVER A STATED ABSENCE IS NOT THE THING `BR-CWP-093`
  // FORBIDS.** That rule makes the *Visit us* NAV WORD and the front-page CARD
  // disappear when nothing is published, so nobody is ever SENT here. What is
  // left is a typed address or a stale bookmark, and the person holding one
  // needs the frame, the utility's name and its phone number — not a heading
  // with nothing under it, and not a staff error panel either.
  const head = (
    <PageHeader
      kicker={t("portal.visit.kicker")}
      title={t("portal.visit.title")}
      rollup={t("portal.visit.subtitle")}
    />
  );
  const phone = front.data?.emergency_phone ?? null;
  const waysHome = [
    { label: t("portal.front.title"), to: path("/"), testKey: "front_page" },
  ];

  const body = () => {
    if (front.isPending || centres.isPending) {
      return <PortalState kind="loading" sentence={t("portal.visit.state.loading")} />;
    }
    if (centres.data === undefined) {
      // ⚠ **ONLY A 404 IS AN EMPTY.** Reading every refusal as *there is
      // nothing here* would be the same collapse in the other direction —
      // telling a customer the utility has no counters when the truth is that
      // the page did not load (hard-won law 7: what would make this check pass
      // wrongly?). The front payload is not consulted here at all: `GuestPage`
      // owns that read and never renders these children without it.
      const empty = isNotFound(centres.error);
      return (
        <PortalState
          kind={empty ? "empty" : "failed"}
          sentence={empty ? t("portal.visit.state.none") : t("portal.visit.state.failed")}
          waysOut={
            empty
              ? waysHome
              : [
                  {
                    label: t("portal.payNow.tryAgain"),
                    onClick: () => void centres.refetch(),
                    tone: "primary" as const,
                    testKey: "retry",
                  },
                  ...waysHome,
                ]
          }
        >
          {phone ? <RingUs phone={phone} /> : null}
        </PortalState>
      );
    }
    const nextHoliday =
      centres.data.map((one) => one.today.next_holiday).find((one) => one) ?? null;
    return (
      <TwoCol
        main={
          <>
            {centres.data.map((centre) => (
              <CentreCard
                key={centre.slug}
                centre={centre}
                t={t}
                language={language}
                href={path(`/visit/${centre.slug}`)}
              />
            ))}
          </>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.visit.ratherNotTravel")}>
              <p className="m-0">{t("portal.visit.ratherNotTravelSentence")}</p>
              {phone ? <p className="mt-2 text-neutral-600">{phone}</p> : null}
            </Panel>
            {/* ⚠ READ FROM THE HOLIDAY CALENDAR THE UTILITY ALREADY KEEPS —
                nobody typed this into a centre (BR-CWP-096). */}
            {nextHoliday ? (
              <Panel as="aside" title={t("portal.visit.holidays")} tone="info">
                <p data-next-holiday={nextHoliday.date}>
                  {t("portal.centre.closedOn", {
                    date: dayMonthText(nextHoliday.date, language),
                    label: nextHoliday.label,
                  })}
                </p>
                <p className="mt-2 text-base text-neutral-600">{t("portal.visit.holidaysNote")}</p>
              </Panel>
            ) : null}
          </>
        }
      />
    );
  };

  return (
    <GuestPage client={client}>
      {/* ⚠ **THE EMPTY `<header className="hidden">` THAT USED TO SIT HERE IS
          GONE** (`CR-085` lane 2). It held nothing, rendered nothing and was
          left behind when this screen's second head was folded into the kit's
          (`DEF-CWP-4000`). An element that exists and does nothing is the
          cheapest possible version of hard-won law 2 and it costs a reader a
          minute every time. */}
      <PortalScreen screen="CWP-013" head={head}>
        {body()}
      </PortalScreen>
    </GuestPage>
  );
}

// ══ CWP-014 · one centre ═══════════════════════════════════════════════════

export function CentrePage(props: { client?: ApiClient }) {
  const { t, i18n } = useTranslation();
  const client = props.client ?? api;
  const path = usePortalPath();
  const params = useParams();
  const slug = params.slug ?? "";
  const language = i18n.language || "en";
  const front = useFront(client);
  // ⚠ `enabled` — see `CentresPage` above: a switched-off portal draws the
  // holding notice and asks the server for nothing (`DEF-CWP-4851`).
  const live = front.data?.is_live === true;
  const centre = useQuery({
    queryKey: ["portal", "centres", slug],
    queryFn: () => getPortalCentre(slug, client),
    enabled: live,
  });

  const data = centre.data;
  const today = new Date();
  const todayIndex = (today.getDay() + 6) % 7; // JS Sunday=0 → Monday=0
  const phone = front.data?.emergency_phone ?? null;

  // ⚠ **THE HEAD ON EVERY BRANCH, AND THE BACK LINK WITH IT.** The kicker and
  // the title are the centre's own name and address when there is one and the
  // screen's own words when there is not, but `← Where you can walk in` is
  // there either way — which is the only door off this address and is exactly
  // what a person who followed a stale link needs (R-10).
  //
  // ⚠ AN ABSOLUTE PORTAL PATH, NOT `../visit` — a relative link works until a
  // screen renders from a route that is not `/:tenant/portal`, and then it
  // silently points somewhere else (`BR-CWP-007`).
  const head = (
    <span data-back="visit">
      <PageHeader
        backTo={{ to: path("/visit"), label: t("portal.visit.title") }}
        kicker={data ? data.name : t("portal.visit.kicker")}
        title={data ? data.address : t("portal.visit.title")}
        rollup={
          data ? (
            <span data-centre-status={data.slug}>{centreStatusLine(data.today, t, language)}</span>
          ) : undefined
        }
        // ⚠ **IN THE HEAD'S ACTION ROW, WHERE THE DRAWING PUTS IT**
        // (`DEF-CWP-4000`, audit row D1). This screen drew it in a
        // `<header className="mb-4">` of its own DIRECTLY BELOW the page head
        // — a second action row one element away from the one the kit already
        // renders.
        secondaryActions={
          data?.phone ? (
            // ⚠ PLAIN outline. The drawing gives *Call* the brand outline;
            // B14 rule 6 reserves that for destructive commits and wins.
            <a
              href={`tel:${data.phone.replace(/[^0-9+]/g, "")}`}
              data-action="call"
              className="border border-neutral-300 px-3 py-1 text-base font-semibold text-neutral-700"
            >
              {t("portal.centre.call", { phone: data.phone })}
            </a>
          ) : null
        }
      />
    </span>
  );

  const body = () => {
    if (front.isPending || centre.isPending) {
      return <PortalState kind="loading" sentence={t("portal.centre.state.loading")} />;
    }
    if (data === undefined) {
      const empty = isNotFound(centre.error);
      return (
        <PortalState
          kind={empty ? "empty" : "failed"}
          sentence={empty ? t("portal.centre.state.notFound") : t("portal.centre.state.failed")}
          waysOut={[
            ...(empty
              ? []
              : [
                  {
                    label: t("portal.payNow.tryAgain"),
                    onClick: () => void centre.refetch(),
                    tone: "primary" as const,
                    testKey: "retry",
                  },
                ]),
            { label: t("portal.visit.title"), to: path("/visit"), testKey: "all_centres" },
          ]}
        >
          {phone ? <RingUs phone={phone} /> : null}
        </PortalState>
      );
    }
    const allActions = data.all_actions ?? [...data.allowed_actions, ...data.cannot_do];
    return (
      <>
        {/* ⚠ **THE ONE FACT SOMEBODY NEEDS BEFORE THEY SET OFF, AND NOTHING
            DREW IT** (`CR-085`, 2026-09-08). `directions_note` has been on this
            payload, on `PortalCentre`, and in this screen's own test fixture
            since wave D — *"Parking behind the building, off the alley."* — and
            no component in the portal rendered it, on either centre screen.
            The drawing is explicit about why it matters: *"Parking and
            step-free access are facts somebody needs before setting out, not
            afterwards."*

            It sits directly under the address the head already shows, which is
            where a reader asking *where is this, and can I park* looks next.
            Absent when the utility has written none — never an empty line, and
            no heading over one sentence (B14 rule 32). */}
        {data.directions_note ? (
          <p className="mb-4 text-body text-neutral-600" data-directions-note={data.slug}>
            {data.directions_note}
          </p>
        ) : null}
        <TwoCol
          main={
            <>
              <Panel as="aside" title={t("portal.centre.whatYouCanDo")}>
                <ul className="divide-y divide-neutral-200" data-action-rows="">
                  {allActions.map((action) => {
                    const can = data.allowed_actions.includes(action);
                    return (
                      <li
                        key={action}
                        className="flex items-center justify-between gap-3 py-2"
                        data-action-row={action}
                        data-can={can ? "yes" : "no"}
                      >
                        <span className="text-neutral-900">{t(`portal.centre.action.${action}`)}</span>
                        <span className="font-bold" aria-label={can ? t("portal.centre.yes") : t("portal.centre.no")}>
                          {can ? "✓" : "—"}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                <p className="mt-3 text-base text-neutral-600">{t("portal.centre.cannotNote")}</p>
              </Panel>
              <Panel as="aside" title={t("portal.centre.takesPaymentBy")}>
                {data.payment_methods_accepted.length > 0 ? (
                  <ul className="flex flex-wrap gap-2">
                    {data.payment_methods_accepted.map((method) => (
                      <li
                        key={method}
                        data-method={method}
                        className="border border-neutral-300 px-2 py-1 text-base font-semibold text-neutral-700"
                      >
                        {t(`portal.centre.method.${method}`)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p data-method="none">{t("portal.centre.takesNothing")}</p>
                )}
                <p className="mt-3 text-base text-neutral-600">{t("portal.centre.methodNote")}</p>
              </Panel>
            </>
          }
          rail={
            <>
              <Panel as="aside" title={t("portal.centre.openingHours")}>
                <ul>
                  {data.hours.map((row) => (
                    <li
                      key={row.day_of_week}
                      className={`flex items-center justify-between gap-3 py-1 ${
                        row.day_of_week === todayIndex ? "font-bold text-neutral-900" : "text-neutral-700"
                      }`}
                      data-hours-day={row.day_of_week}
                    >
                      <span>{weekdayText(row.day_of_week, language)}</span>
                      <span className="flex items-center gap-2">
                        {row.day_of_week === todayIndex ? (
                          <StatusChip tone="neutral" testKey="today">
                            {t("portal.centre.today")}
                          </StatusChip>
                        ) : null}
                        <span>
                          {row.is_closed
                            ? t("portal.centre.closedAllDay")
                            : `${clockText(row.opens_at, language)}–${clockText(row.closes_at, language)}`}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
                {/* ⚠ THE FOOTER NOBODY TYPED. It is the tenant's holiday
                    calendar, read (BR-CWP-096). */}
                {data.today.next_holiday ? (
                  <p
                    className="mt-3 border-t border-neutral-200 pt-3 text-base text-neutral-600"
                    data-next-holiday={data.today.next_holiday.date}
                  >
                    {t("portal.centre.closedOn", {
                      date: dayMonthText(data.today.next_holiday.date, language),
                      label: data.today.next_holiday.label,
                    })}
                  </p>
                ) : null}
              </Panel>
              <Panel as="aside" title={t("portal.visit.holidays")} tone="info">
                <p className="m-0">{t("portal.visit.holidaysNote")}</p>
              </Panel>
            </>
          }
        />
      </>
    );
  };

  return (
    <GuestPage client={client}>
      <PortalScreen screen="CWP-014" head={head}>
        {body()}
      </PortalScreen>
    </GuestPage>
  );
}
