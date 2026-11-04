# CR-085 lane 1 · The door map — every portal address, and what points at it

**Read from source at tip `b4063d1e6`, 2026-09-11.** Fifty registered portal routes, the
inbound link map built by reading every `.tsx` under `07-frontend/src/portal/` for the three
forms a door can take (a quoted `to=`, a backtick `to=`/`navigate()` with its interpolations
folded to `:param`, and a bare `navigate("/x")`), then walking the import graph so that a link
written in a component counts as a door from **every screen that renders that component** —
which is how `PortalShell`'s six tabs and `GuestFrame`'s nav become doors on every screen
inside them.

⚠ **THIS ANSWERS *IS THERE A LINK*, NOT *IS THE LINK WHERE A PERSON WOULD LOOK*.** The
second question is the one the PO actually asked on 2026-09-08 — *"when you mention that
door is from x screen, when we check x screen we dont find the door there"* — and no static
read can answer it. `everyRouteHasADoor.test.ts` says the same thing about itself in its own
header, and it is right to.

⚠ **AND IT ANSWERS *IN THE SOURCE*, NOT *ON THE SCREEN*.** Several of these links are behind
a server switch (`front.links.help`, `front.links.visit`, `front.switches.*`,
`cardIsAvailable`) or behind a data condition (Past due only appears when the account is
overdue). On the shared stack today those switches are all off — see §4.

---

## 1 · The count

| question | answer |
|---|---|
| routes registered in `portalRoutes.tsx` | **50** |
| routes with at least one inbound link in source | **49** |
| routes with **no** inbound link anywhere | **1** — `/start-service/:draft` (CWP-047) |
| routes reachable by walking links from the front page `/` alone | **49** |
| routes reachable from `/` **and** `/home` together | **49** — the same 49 |
| routes reachable from nowhere | **1**, the same one |

**The one is documented and is not a defect.** `REACHED_FROM_OUTSIDE` in
`everyRouteHasADoor.test.ts` names it: the draft token *is* the address, it arrives as an
emailed resume link, and a list of other people's unfinished applications is not a screen we
want.

⚠ **SO THE BLUEPRINT'S HEADLINE — *37 of 60 screens name no door* — IS A STATEMENT ABOUT THE
BLUEPRINT, NOT ABOUT THE PRODUCT, AND BOTH HALVES CHECK OUT.** Counted in the PDF's own text:
**37 screens carry the red callout** *"This screen does not carry a How you get here row"*
and **37 carry the line** *"No door named."* — exactly the number claimed. What those 37 are
missing is a **row in the document**. In the code, 49 of the 50 addresses have a door today.
The two flows the blueprint names as having **no door at all** — `stop-or-restart` and
`visit/:slug` — **both have doors now**: `/stop-or-restart` from `accounts/YourAccount` and
`details/MyDetails`, `/visit/:slug` from `guest/CentresPage`. The blueprint's own appendix
already says so (*"Two screens are still described as unreachable and both now have doors"*).

---

## 2 · The thinnest doors — one way in, and that is the whole of it

Seventeen screens are reachable from exactly **one** file. Each is a single point of failure:
delete one conditional and the screen is unreachable with every test still green, which is the
`DEF-CWP-4654` shape.

| screen | address | its only door |
|---|---|---|
| CWP-001 | `/` | `signin/FrontDoor` (the brand word in the guest bar reaches `/` too — see §4) |
| CWP-010 | `/ask` | `shell/GuestFrame` nav |
| CWP-003 | `/pay/check` | `guest/QuickPay` (step 2 of the wizard, by `navigate()`) |
| CWP-004 | `/pay/done` | `guest/QuickPayCheck` (step 3, by `navigate()`) |
| CWP-050 | `/fees` | `payments/Payments` |
| CWP-014 | `/visit/:slug` | `guest/CentresPage` |
| CWP-065 | `/account` | `details/MyDetails` |
| CWP-030 | `/bills/:number/comparison` | `bills/BillDetail` |
| CWP-025 | `/my-details/preferences` | `details/MyDetails` |
| CWP-020 | `/accounts/add` | `accounts/MyAccounts` |
| CWP-063 | `/plan-offer` | `payments/Payments` |
| CWP-066 | `/level-pay/standing` | `plans/LevelPay` |
| CWP-032 | `/final-bill` | `accounts/YourAccount` |
| CWP-034 | `/readings` | `usage/Usage` |
| CWP-043 | `/plan` | `payments/Payments` |
| CWP-064 | `/protections` | `arrears/Overdue` |
| CWP-045 | `/money-back` | `payments/Payments` |

⚠ **FOUR OF THE SEVENTEEN HANG OFF ONE SCREEN.** `payments/Payments` is the only door to
`/fees`, `/plan-offer`, `/plan` and `/money-back`. A customer who never opens *Payments and
receipts* cannot reach any of the four, and three of them (a plan offer, your plan, a refund)
are things the utility wants them to see.

⚠ **AND `/protections` IS REACHED ONLY FROM `/overdue`.** *What is protecting your supply* —
a medical certificate, a winter hold — is behind *What happens if this is not paid*. A
customer in good standing whose supply is protected has no way to that screen at all, and
`/overdue` itself answers `overdue: false` for them, so the door is not merely hard to find,
it is not drawn.

---

## 3 · Every address and its doors

| screen | address | inbound doors, read from source | count |
|---|---|---|---|
| CWP-001 | `/` | `signin/FrontDoor` | 1 |
| CWP-008 | `/start-service` | `payments/FeesPage` · `signin/FrontDoor` | 2 |
| CWP-047 | `/start-service/:draft` | **none** | 0 |
| CWP-010 | `/ask` | `shell/GuestFrame` | 1 |
| CWP-002 | `/pay` | `guest/QuickPayCheck` · `guest/QuickPayDone` · `shell/GuestFrame` · `signin/Enrol` | 4 |
| CWP-003 | `/pay/check` | `guest/QuickPay` | 1 |
| CWP-004 | `/pay/done` | `guest/QuickPayCheck` | 1 |
| CWP-038 | `/pay-now` | `accounts/MyAccounts` · `arrears/Overdue` · `bills/BillDetail` · `bills/Bills` · `home/Home` · `payments/Payments` | 6 |
| CWP-039 | `/payment-methods` | `methods/Autopay` · `payments/PayNow` · `payments/Payments` | 3 |
| CWP-040 | `/autopay` | `methods/Methods` · `payments/Payments` | 2 |
| CWP-050 | `/fees` | `payments/Payments` | 1 |
| CWP-011 | `/help` | `bills/PrintedBill` · `shell/GuestFrame` · `shell/PortalShell` | 3 |
| CWP-060 | `/help/:slug` | `arrears/Overdue` · `bills/BillDetail` · `requests/AskAQuestion` | 3 |
| CWP-013 | `/visit` | `details/AddAccount` · `guest/CentresPage` · `shell/GuestFrame` | 3 |
| CWP-014 | `/visit/:slug` | `guest/CentresPage` | 1 |
| CWP-015 | `/sign-in` | `guest/FrontPageView` · `shell/GuestFrame` · `signin/ForgotPassword` | 3 |
| CWP-016 | `/enrol` | `guest/FrontPageView` · `guest/QuickPayDone` · `signin/FrontDoor` | 3 |
| CWP-019 | `/forgot-password` | `guest/FrontPageView` · `signin/FrontDoor` | 2 |
| CWP-022 | `/home` | `shell/PortalShell` · `signin/Enrol` · `signin/FrontDoor` | 3 |
| CWP-023 | `/accounts` | `details/AddAccount` · `details/MyDetails` · `home/Home` | 3 |
| CWP-065 | `/account` | `details/MyDetails` | 1 |
| CWP-027 | `/bills` | `accounts/MyAccounts` · `accounts/YourAccount` · `bills/BillDetail` · `home/Home` · `shell/PortalShell` | 5 |
| CWP-029 | `/bills/:number/document` | `bills/BillDetail` · `bills/FinalBill` · `home/Home` | 3 |
| CWP-030 | `/bills/:number/comparison` | `bills/BillDetail` | 1 |
| CWP-028 | `/bills/:number` | `bills/BillComparison` · `bills/Bills` · `bills/PrintedBill` · `home/Home` · `requests/DisputeBill` · `usage/Readings` | 6 |
| CWP-024 | `/my-details` | `details/Preferences` · `shell/PortalShell` | 2 |
| CWP-025 | `/my-details/preferences` | `details/MyDetails` | 1 |
| CWP-020 | `/accounts/add` | `accounts/MyAccounts` | 1 |
| CWP-031 | `/documents` | `accounts/YourAccount` · `bills/Bills` | 2 |
| CWP-063 | `/plan-offer` | `payments/Payments` | 1 |
| CWP-066 | `/level-pay/standing` | `plans/LevelPay` | 1 |
| CWP-044 | `/level-pay` | `arrears/HelpPaying` · `payments/Payments` | 2 |
| CWP-032 | `/final-bill` | `accounts/YourAccount` | 1 |
| CWP-033 | `/usage` | `accounts/YourAccount` · `home/Home` · `shell/PortalShell` · `usage/Equipment` · `usage/Readings` | 5 |
| CWP-034 | `/readings` | `usage/Usage` | 1 |
| CWP-037 | `/equipment` | `accounts/YourAccount` · `usage/Usage` | 2 |
| CWP-041 | `/payments` | `payments/PayNow` · `shell/PortalShell` | 2 |
| CWP-042 | `/ask-for-a-plan` | `arrears/HelpPaying` · `arrears/Overdue` · `home/Home` · `plans/PlanOffer` · `plans/YourPlan` | 5 |
| CWP-043 | `/plan` | `payments/Payments` | 1 |
| CWP-046 | `/requests` | `accounts/YourAccount` · `shell/PortalShell` | 2 |
| CWP-052 | `/stop-or-restart` | `accounts/YourAccount` · `details/MyDetails` | 2 |
| CWP-057 | `/overdue` | `bills/Bills` · `home/Home` | 2 |
| CWP-056 | `/help-paying` | `arrears/Overdue` · `arrears/Protections` · `bills/Bills` · `plans/AskForPlan` | 4 |
| CWP-064 | `/protections` | `arrears/Overdue` | 1 |
| CWP-045 | `/money-back` | `payments/Payments` | 1 |
| CWP-051 | `/requests/:reference` | `requests/AskAQuestion` · `requests/DisputeBill` · `requests/Requests` | 3 |
| CWP-055 | `/bills/:number/dispute` | `bills/BillDetail` · `bills/FinalBill` | 2 |
| CWP-054 | `/ask-a-question` | `payments/Fees` · `requests/TrackRequest` | 2 |
| CWP-006 | `/report` | `shell/GuestFrame` · `usage/Equipment` | 2 |
| CWP-012 | `/track` | `guest/QuickPayDone` · `shell/GuestFrame` | 2 |


---

## 4 · The doors that exist in source and do not render on the running product

Measured in a browser on the shared stack at `http://127.0.0.1:8401`, tenant `brazosbend`,
2026-09-11.

**The tenant has 0 rows in `portal_settings`, 0 customers and 0 accounts.** `GET
/portal/public/front` answers `is_live: false`, `cards: []`, `links: {help:false,
visit:false}` and **no `switches` object at all**. So on that tenant:

* `/` and `/pay` both render **CWP-001's holding page** — *"We are not open online yet."* —
  and the front page's six errand cards do not exist, so **six doors are absent**;
* the guest bar draws **no nav at all** past the brand word, so `/ask`, `/help`, `/visit`,
  `/report` and `/track` lose their only or their main door;
* every signed-in address renders `FailedWithRetry` — *"You're signed out"* — with **no
  frame, no menu and no account line**, so the six tab doors do not exist either.

**That is a tenant-configuration state and not a build defect**, and it is recorded here
because it is also the reason no signed-in screen could be walked on the shared stack: a
lane that measures the frame there and reports *the menu is missing* would be reporting the
fixture.

**With the two frame reads stubbed live** — `portal/public/front` returning
`is_live: true`, all six cards `available`, both links true and all five switches true, and
`portal/session` returning one account — the built bundle draws the real guest bar, the real
signed-in shell and the real account line. Those measurements are in
`CR-085-lane1-spacing-anchors.md`.

---

## 5 · What no static read can tell you, stated so nobody mistakes this for the answer

1. **Whether the door is where a person would look.** Past due had a door from Bills and
   budget billing had a door from Help paying, and both were still wrong.
2. **Whether the control is live.** A door inside a `Held` wrapper renders as text with a
   reason beside it and this map counts it as a door.
3. **Whether the branch ever runs.** `/overdue`'s link to `/protections` is drawn only on an
   overdue account; `/protections` answers `any: false` when no hold exists.
4. **Whether the destination is the address the router actually mounts.** That one is
   `DEF-CWP-4707`'s shape and it needs a routed mount, not a grep.
