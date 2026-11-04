// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-018 (EP-TEN-03 — S1 itself)  Screens: S1
// Change:   DEF-TEN-4222 REOPENED 2026-10-02 — decision log 2026-10-02, "THE
//           PUBLIC PRICING PAGE STOPS SHOWING PRICES" and "THE PUBLIC HOME /
//           PRICING PAGE IS REBUILT FROM THE APPROVED DRAFT, AS IMAGES". PO,
//           verbatim: *"use images and not content/text and revamp this page
//           and add the links that we discussed"*.
// Rules:    BR-TEN-002 (sizes are advisory, never a cap) · BR-TEN-014 (14-day
//           trial, no card) · BR-SHL-023 (ONE money-formatting path) · B14
//           rules 21, 42, 43, 44
// ───────────────────────────────────────────────────────
//
// S1 — the public home page at `/`. A MAINTENANCE redraw of a live screen
// (22-product-maintenance-process.md): built from the three approved screenshots
// (1440 / 1280 / 400) of the PO's draft, read as IMAGES (rule 42), with OUR
// tokens, type scale and kit winning over any pixel in them (rule 44).
//
// ⚠ NO PRICE IS SHOWN, AND THIS PAGE NO LONGER FETCHES THE PLAN CATALOGUE.
// Until 2026-10-02 it read `GET /public/pricing-plans` and drew three priced
// tier cards ($1,000 / $5,000 / $8,000 a month). The PO took them down pending
// a new pricing model. The dollar figures that DO appear are an EXAMPLE
// CUSTOMER STATEMENT and two proof lines — what a utility bills, never what we
// charge — and they go through the one money path like every other figure.
//
// THE FIVE KINDS OF LINK, and why each goes where it goes (PO, same hour):
//   · the customer service number is a `tel:` link wherever it is printed
//     (hero note, its tile, the No-account-cap box, the footer — draft v6);
//   · the five section words are in-page anchors — this page has no tenant and
//     nothing to route to;
//   · Sign in → `/signin-help`, the existing tenant-less screen (sign-in is
//     per tenant, PO 2026-08-10);
//   · every Start free → `/signup`, the existing wizard (*"we already ahve
//     screesn for these two - just direct it to those screens"*);
//   · both Book a walkthrough → Bynry's own demo page, in a new tab
//     (*"book walkthorugh - direct it to this link"*). It is a CODE constant,
//     not catalogue copy: G19 refuses a host in a catalogue value, and a URL is
//     an address rather than a sentence a translator should touch.
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ButtonAnchor, ButtonLink } from "@/components/Button";
import { DEFAULT_MONEY_LOCALE, formatMoney } from "@/components/MoneyCell";
import { ProductName } from "@/components/ProductName";
import { Kicker } from "@/components/TextBits";
import { SIGNUP_SERVICES } from "@/features/tenancy/SignupWizard";
import { SIGNIN_HELP_ROUTE, SIGNUP_ROUTE } from "@/routing/tenantPath";

import { SIZE_BANDS, sizeBandBodyKey, sizeBandRange } from "./sizeBands";

export { SIGNIN_HELP_ROUTE, SIGNUP_ROUTE };

/** Bynry's demo-booking page — the PO's address, verbatim. */
export const WALKTHROUGH_URL = "https://www.bynry.com/book-a-demo";

/** The customer service line (decision log 2026-10-02, "DRAFT VERSION 6
 *  APPROVED FOR BUILD": *"number is +1 732-630-0285"*). A code constant for the
 *  same reason as the walkthrough address: it is a fact, not a translation. */
export const SUPPORT_PHONE = "+1 732-630-0285";
export const SUPPORT_PHONE_HREF = "tel:+17326300285";

/** The four trust items, ON ONE LINE under the hero buttons (PO: *"all 4
 *  should be in one line"*). Printed exactly as ruled: "SOC 2" with no type and
 *  "NIST" with no framework named — the narrowest true wording. */
/** "SOC 2" and "NIST" are proper names, printed the same in every language,
 *  so they are constants rather than catalogue entries (a catalogue value equal
 *  to English in all ten translations is what G15 exists to refuse). */
const SOC2 = "SOC 2";
const NIST = "NIST";
const TRUST_STRIP = [
  { id: "soc2", key: null, text: SOC2 },
  { id: "nist", key: null, text: NIST },
  { id: "integrations", key: "public.home.trust.integrations", text: null },
  { id: "golive", key: "public.home.trust.golive", text: null },
] as const;

/** The example statement's currency. It is an illustration of a US utility's
 *  bill, so the code rides with every figure like any served amount would. */
const EXAMPLE_CURRENCY = "USD";

/** The example statement: five of the eleven services on one bill, each line
 *  the engine's own arithmetic for that service (Fire is trash's — the size
 *  picks the price and the count multiplies it: $60.00 + 2 × $12.00). */
const STATEMENT_LINES = [
  // The electric line's detail is a quantity and its unit — sample data, not
  // copy — so it is the one line with no catalogue key.
  { service: "electric", amount: "68.40", detail: "612 kWh" },
  { service: "water", amount: "31.18" },
  { service: "sewer", amount: "28.06" },
  { service: "trash", amount: "18.00" },
  { service: "fire", amount: "84.00" },
] as const;
const STATEMENT_TOTAL = "229.64";

/** One bulk run, as measured: the proof line under "Bill 40,000 accounts". */
const RUN_ACCOUNTS = 40009;
const RUN_TOTAL = "1270167.00";

const BENEFITS = ["oneBill", "oneRun", "field", "portal", "live", "noCaps"] as const;
const STEPS = ["read", "rate", "bill", "collect", "field", "post"] as const;
const INCLUDED = ["meterToCash", "data", "field", "audit"] as const;

/** The page column: one 1200px measure, the same gutter on every band. */
const WRAP = "mx-auto w-full max-w-[1200px] px-12 max-sm:px-4";
const MUTED = "text-neutral-700";
const TILE = "grid content-start gap-2 border-t-4 border-t-text pt-4";
const SECTION = "border-t-2 border-t-divider py-16 max-sm:py-12";

/** Stands in for the number inside a translated sentence until it is drawn. */
const PHONE_MARK = "\u2063PHONE\u2063";

const PHONE = "whitespace-nowrap font-semibold text-text tabular-nums no-underline";

/** The phone number as a link a phone can dial. */
function PhoneLink(props: { className?: string }) {
  return (
    <a
      href={SUPPORT_PHONE_HREF}
      className={props.className === undefined ? PHONE : `${PHONE} ${props.className}`}
      data-public-link="phone"
    >
      {SUPPORT_PHONE}
    </a>
  );
}

/** A sentence carrying the phone number as `{{phone}}`, with the number drawn
 *  as a link wherever the language put it — word order differs by catalogue. */
function WithPhone(props: { text: string }) {
  const parts = props.text.split(PHONE_MARK);
  return (
    <>
      {parts.map((part, index) => (
        <span key={index}>
          {part}
          {index < parts.length - 1 && <PhoneLink />}
        </span>
      ))}
    </>
  );
}

function money(amount: string): string {
  return formatMoney(amount, EXAMPLE_CURRENCY, DEFAULT_MONEY_LOCALE);
}

function SectionHead(props: { kicker: string; title: string; lede?: string }) {
  return (
    <div className="mb-8 grid max-w-[60ch] gap-3">
      <Kicker>{props.kicker}</Kicker>
      <h2 className="m-0 text-h1 max-sm:text-h2">{props.title}</h2>
      {props.lede !== undefined && <p className={`m-0 text-lead ${MUTED}`}>{props.lede}</p>}
    </div>
  );
}

function WalkthroughLink(props: { variant: "primary" | "secondary"; label: string }) {
  return (
    <ButtonAnchor
      variant={props.variant}
      href={WALKTHROUGH_URL}
      target="_blank"
      rel="noopener noreferrer"
      data-public-link="walkthrough"
    >
      {props.label}
    </ButtonAnchor>
  );
}

export function PricingPage() {
  const { t, i18n } = useTranslation();
  const walkthrough = t("public.pricing.bookWalkthrough");

  return (
    <div className="min-h-screen bg-bg text-text" data-public-page="pricing">
      <nav className="border-b-2 border-b-divider" aria-label={t("public.nav.label")}>
        <div className={`${WRAP} flex flex-wrap items-center gap-6 py-4`}>
          <a className="mr-auto flex items-center gap-2 no-underline" href="#top" data-public-brand>
            <span aria-hidden="true" className="size-3 bg-accent" />
            <ProductName size="public" />
          </a>
          <div className="flex gap-6 font-semibold max-sm:hidden" data-public-sections>
            <a className="text-md text-text no-underline" href="#why">{t("public.nav.why")}</a>
            <a className="text-md text-text no-underline" href="#how">{t("public.nav.how")}</a>
            <a className="text-md text-text no-underline" href="#included">{t("public.nav.included")}</a>
            <a className="text-md text-text no-underline" href="#trust">{t("public.nav.security")}</a>
            <a className="text-md text-text no-underline" href="#sizes">{t("public.nav.sizes")}</a>
          </div>
          {/* Sign-in is PER TENANT (`/{tenant}/signin`, PO 2026-08-10) and this
              page has no tenant, so it goes to the tenant-less help screen. */}
          <Link className="text-md font-semibold text-text no-underline" to={SIGNIN_HELP_ROUTE}>
            {t("public.nav.signIn")}
          </Link>
          <ButtonLink variant="primary" to={SIGNUP_ROUTE}>
            {t("public.nav.startFree")}
          </ButtonLink>
        </div>
      </nav>

      <main id="top">
        <div
          className={`${WRAP} grid grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)] items-center gap-12 pt-16 pb-20 max-xl:grid-cols-1 max-xl:py-12`}
          data-public-section="hero"
        >
          <div>
            <Kicker>{t("public.home.eyebrow")}</Kicker>
            <h1 className="mt-4 mb-6 text-display max-md:text-h1">{t("public.home.title")}</h1>
            <p className={`m-0 mb-8 max-w-[56ch] text-h4 leading-body font-normal tracking-normal ${MUTED}`}>
              {t("public.home.lead")}
            </p>
            <div className="flex flex-wrap gap-4">
              <ButtonLink variant="primary" to={SIGNUP_ROUTE}>
                {/* BR-TEN-014: 14 days, no card. */}
                {t("public.pricing.startFree")}
              </ButtonLink>
              <WalkthroughLink variant="secondary" label={walkthrough} />
            </div>
            <ul
              className="m-0 mt-6 flex list-none flex-nowrap gap-2 p-0 text-base font-semibold whitespace-nowrap max-sm:flex-wrap max-sm:whitespace-normal"
              aria-label={t("public.home.trust.label")}
              data-public-trust
            >
              {TRUST_STRIP.map((item, index) => (
                <li
                  key={item.id}
                  className={
                    index === 0
                      ? "flex items-center gap-2"
                      : "flex items-center gap-2 before:mr-1 before:size-1 before:bg-neutral-700 before:content-['']"
                  }
                >
                  {item.key === null ? item.text : t(item.key)}
                </li>
              ))}
            </ul>
            <p className={`m-0 mt-4 text-md ${MUTED}`}>
              <WithPhone text={t("public.home.pricingNote", { phone: PHONE_MARK })} />
            </p>
          </div>

          <aside
            className="border-t-4 border-t-accent bg-surface p-6 text-md"
            aria-label={t("public.home.statement.label")}
            data-public-statement
          >
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-4">
              <h3 className="m-0 text-h4">{t("public.home.statement.title")}</h3>
              <span className={`border border-dashed border-divider px-2 py-0.5 text-sm font-semibold ${MUTED}`}>
                {t("public.home.statement.label")}
              </span>
            </div>
            <dl className="m-0 tabular-nums">
              {STATEMENT_LINES.map((line) => (
                <div
                  key={line.service}
                  className="flex justify-between gap-4 border-b border-b-divider py-2"
                  data-statement-line={line.service}
                >
                  <dt>
                    {t(`tenancy.signup.service.${line.service}`)}
                    <span className={`block text-sm ${MUTED}`}>
                      {"detail" in line ? line.detail : t(`public.home.statement.${line.service}`)}
                    </span>
                  </dt>
                  <dd className="m-0 whitespace-nowrap">{money(line.amount)}</dd>
                </div>
              ))}
              <div className="flex justify-between gap-4 pt-3 text-h5">
                <dt>{t("public.home.statement.due")}</dt>
                <dd className="m-0 whitespace-nowrap">{money(STATEMENT_TOTAL)}</dd>
              </div>
            </dl>
          </aside>
        </div>

        <section id="why" className={SECTION}>
          <div className={WRAP}>
            <SectionHead
              kicker={t("public.home.why.eyebrow", { product: t("app.name") })}
              title={t("public.home.why.title")}
            />
            <div className="grid grid-cols-3 gap-x-6 gap-y-8 max-md:grid-cols-2 max-sm:grid-cols-1">
              {BENEFITS.map((benefit) => (
                <div
                  key={benefit}
                  className="grid content-start gap-2 border-t-2 border-t-text pt-4"
                  data-public-benefit={benefit}
                >
                  <h3 className="m-0 text-h4">{t(`public.home.why.${benefit}.title`)}</h3>
                  <p className={`m-0 ${MUTED}`}>{t(`public.home.why.${benefit}.body`)}</p>
                  <span className="text-md font-semibold tabular-nums before:mr-2 before:inline-block before:size-2 before:bg-accent before:content-['']">
                    {t(`public.home.why.${benefit}.proof`, {
                      amount: benefit === "oneRun" ? money(RUN_TOTAL) : money(STATEMENT_TOTAL),
                      accounts: new Intl.NumberFormat(i18n.language).format(RUN_ACCOUNTS),
                    })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className={SECTION}>
          <div className={WRAP}>
            <SectionHead
              kicker={t("public.nav.how")}
              title={t("public.home.how.title")}
              lede={t("public.home.how.lede")}
            />
            <ol className="m-0 grid list-none grid-cols-6 gap-4 p-0 max-lg:grid-cols-3 max-sm:grid-cols-1">
              {STEPS.map((step, index) => (
                <li key={step} className="border-t-4 border-t-text pt-4" data-public-step={step}>
                  <span className="text-md font-extrabold text-accent-700">{index + 1}</span>
                  <h3 className="mt-1 mb-2 text-h4">{t(`public.home.how.${step}.title`)}</h3>
                  <p className={`m-0 ${MUTED}`}>{t(`public.home.how.${step}.body`)}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="included" className={SECTION}>
          <div className={WRAP}>
            <SectionHead kicker={t("public.nav.included")} title={t("public.home.included.title")} />
            <div className="grid grid-cols-2 gap-6 max-sm:grid-cols-1">
              <div className="col-span-full border-t-4 border-t-accent bg-surface p-6" data-public-card="services">
                <h3 className="m-0 mb-2 text-h4">{t("public.home.included.services.title")}</h3>
                <p className={`m-0 ${MUTED}`}>{t("public.home.included.services.body")}</p>
                {/* The SAME eleven the sign-up wizard offers — one list, so a
                    twelfth service cannot reach one screen and miss the other. */}
                <ul className="m-0 mt-4 flex list-none flex-wrap gap-2 p-0" data-public-services>
                  {SIGNUP_SERVICES.map((service) => (
                    <li
                      key={service.code}
                      className="border border-divider bg-bg px-3 py-1 text-base font-semibold"
                      data-service-chip={service.code}
                    >
                      {t(service.labelKey)}
                    </li>
                  ))}
                </ul>
              </div>
              {INCLUDED.map((card) => (
                <div key={card} className="border-t-4 border-t-accent bg-surface p-6" data-public-card={card}>
                  <h3 className="m-0 mb-2 text-h4">
                    {/* "Field work" is the step's own name, said once. */}
                    {t(card === "field" ? "public.home.how.field.title" : `public.home.included.${card}.title`)}
                  </h3>
                  <p className={`m-0 ${MUTED}`}>{t(`public.home.included.${card}.body`)}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="trust" className={SECTION}>
          <div className={WRAP}>
            <SectionHead kicker={t("public.home.trust.eyebrow")} title={t("public.home.trust.title")} />
            <div className="grid grid-cols-4 gap-6 max-lg:grid-cols-2 max-sm:grid-cols-1">
              <div className={TILE} data-public-tile="security">
                <Kicker>{t("public.nav.security")}</Kicker>
                <h3 className="m-0 text-h3">
                  {SOC2} · {NIST}
                </h3>
                <p className={`m-0 ${MUTED}`}>{t("public.home.trust.security.body")}</p>
              </div>
              <div className={TILE} data-public-tile="integrations">
                <Kicker>{t("public.home.trust.integrations.kicker")}</Kicker>
                <h3 className="m-0 text-h3">{t("public.home.trust.integrations")}</h3>
                <p className={`m-0 ${MUTED}`}>{t("public.home.trust.integrations.body")}</p>
              </div>
              <div className={TILE} data-public-tile="golive">
                <Kicker>{t("public.home.trust.golive")}</Kicker>
                <h3 className="m-0 text-h3">{t("public.home.trust.golive.title")}</h3>
                <p className={`m-0 ${MUTED}`}>{t("public.home.trust.golive.body")}</p>
              </div>
              <div className={TILE} data-public-tile="call">
                <Kicker>{t("public.home.trust.call.kicker")}</Kicker>
                <h3 className="m-0 text-h3">{t("public.home.trust.call.title")}</h3>
                <PhoneLink className="text-h4" />
                <p className={`m-0 ${MUTED}`}>{t("public.home.trust.call.body")}</p>
              </div>
            </div>
          </div>
        </section>

        <section id="sizes" className={SECTION}>
          <div className={WRAP}>
            <SectionHead kicker={t("public.nav.sizes")} title={t("public.home.sizes.title")} />
            {/* BR-TEN-002 · NFR-5: three sizes, NO PRICES, and no cap. */}
            <div className="grid grid-cols-3 border-t-2 border-t-text max-sm:grid-cols-1">
              {SIZE_BANDS.map((band, index) => (
                <div
                  key={band.key}
                  className={
                    index === 0
                      ? "py-6 pr-6"
                      : "border-l border-l-divider py-6 pr-6 pl-6 max-sm:border-t max-sm:border-l-0 max-sm:border-t-divider max-sm:pl-0"
                  }
                  data-public-size={band.key}
                >
                  <div className="text-h2 tabular-nums">{sizeBandRange(t, band, i18n.language)}</div>
                  <div className={`text-md ${MUTED}`}>{t("public.home.sizes.unit")}</div>
                  <p className={`m-0 mt-3 ${MUTED}`}>{t(sizeBandBodyKey(band))}</p>
                </div>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap items-center justify-between gap-6 bg-surface p-6">
              <p className="m-0 max-w-[60ch] text-lead">
                <strong className="font-extrabold">{t("public.home.sizes.noCap")}</strong>{" "}
                <WithPhone text={t("public.home.sizes.noCapBody", { phone: PHONE_MARK })} />
              </p>
              <WalkthroughLink variant="primary" label={walkthrough} />
            </div>
          </div>
        </section>
      </main>

      <footer className={`border-t-2 border-t-divider py-8 text-md ${MUTED}`}>
        <div className={`${WRAP} flex flex-wrap justify-between gap-4`}>
          <span>
            {t("app.name")} · {SOC2} · {NIST}
          </span>
          <span>
            {t("public.home.trust.call.title")} <PhoneLink />
          </span>
        </div>
      </footer>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-018@011ac24 · DEF-TEN-4222 (reopened 2026-10-02)
// generated: 2026-08-09 by story-coder v1 · REDRAWN 2026-10-02 (maintenance lane — the approved draft, read as images; prices removed; links to /signin-help, /signup and Bynry's demo page)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: the draft's footer note "Draft for review · not live" is the mock's own marker and is not built
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
