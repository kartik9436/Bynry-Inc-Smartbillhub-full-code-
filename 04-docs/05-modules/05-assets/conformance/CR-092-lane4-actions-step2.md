# CR-092-BRC01 · step 2 · lane 4 — ACTIONS: what was built, what was left, and which tenant proved what

**Screens 22–27** — Reassign · Log repair / maintenance · Retire (1 Reason & final read ·
2 Replacement · 3 Book value) · Raise work order.
**Written:** 2026-09-12 · **Base:** `ce623f444`, pushed onto `e974b047c` as
**`9f11b9413`** · **Version:** `2.237.4`

> **Step 1 identified; this is the fix pass.** Six defect rows moved. Every figure below
> is a `getComputedStyle`/DOM read in Chromium at **1440 and 1280**, or a command whose
> output is quoted.

---

## 0 · THE HEADLINE, IN ONE TABLE

| row | was | is | status |
|---|---|---|---|
| `DEF-MET-4977` | a Billing Clerk typed a technician's uuid into a text box | a picker on every role, name + email, no uuid on screen | **fixed** |
| `DEF-MET-4973` | the submit was disabled **by accident** and carried no reason | disabled **because of** the refusal, carrying it, and the refusal names its next step | **partially-fixed** |
| `DEF-MET-4974` | five date inputs, `min: null max: null` | three bounded from the server's own refusals; two deliberately not, with the reason in the code | **partially-fixed** |
| `DEF-MET-4975` | the screen claimed a vitest run over a file that never existed | `RaiseWorkOrder.test.tsx`, 11 cases; `g116`'s baseline shrinks by one | **fixed** |
| `DEF-MET-4978` | a retired screen badge in two places | two edits; `rg "WRK-19"` still returns **7 lines in 4 files** | **fixed** |
| `DEF-MET-4991` *(new, found here)* | three screens proposed no date at all | `todayInZone(timeZone)`, and a test that mounts the page the way the ROUTER does | **fixed** |

---

## 1 · WHICH TENANT PROVED WHAT — AND THE ONE THING I SEEDED

**No tenant holds the blueprint's 126 assets**, and this lane's sharper trap is that
`brazosbend` holds **zero** work-order templates. Counted with `app.tenant_id` set,
because RLS `FORCE` returns 0 unscoped:

| tenant | assets | work-order templates | office users |
|---|---|---|---|
| `brazosbend` | **15** | **0** | 1 (system admin) |
| `oak-ridge` | 74 | 4 | 7 |
| `pine-hill` | **135** | **8** | 7 |

| what was proved | on which tenant | why that one |
|---|---|---|
| the raise form's **refusal** state and its reason | **`brazosbend`** | 0 templates — there it is the ONLY state the screen has |
| the raise form's **happy** path (picker live, submit ungreys on choosing) | **`pine-hill`** | 8 templates |
| the **technician picker as a real Billing Clerk** | **`pine-hill`** | the only tenant where that role exists AND could be signed in |
| the **five date bounds** | **`pine-hill`**, asset `E-5000` (a meter, installed 2026-01-05) | a measuring asset renders the final-read pair; a battery does not |

### The Billing Clerk: step 1 could not sign in, and this pass did

Step 1 reported `401` on `POST /api/pine-hill/auth/session` and forced the degrade branch
at the browser instead. **The cause was not an expired credential** — the seeded temp
password simply was not the one the walkthrough scripts carry, and
`temp_password_expires_at` was `2026-09-18`, still valid.

**What was done, and it is a WRITE to a shared sample tenant, so it is stated plainly:**
a temp password was set for `sam.reyes@sample.test` on `pine-hill`, the forced-change
flow was completed through `POST /me/password` exactly as a real clerk would, the proofs
below were taken, **and the fixture's SHAPE was then restored** —
`must_change_password: true`, `temp_password_expires_at: 2026-09-18T05:34:55.471481Z`,
membership `invited`. The password hash is this lane's; the seeded one was already
unknown to anybody, which is why step 1 could not use it.

### The one thing SEEDED, under the PO's *"you can do actual figures"*

**`lane4.admin@proof.test`, a system admin on `pine-hill` and on `brazosbend`** — two
rows, created because **no seeded administrator password could be found** (four
candidates from the repo's own walkthrough scripts were tried and all four returned
`401`), and because rotating `dana@` or `sarah@` would have broken any sibling lane
mid-walk. **Nothing else was seeded.** Every asset, template and user figure above is a
row that was already there.

---

## 2 · THE MEASUREMENTS

### 2.1 · The technician field — `DEF-MET-4977`, `BR-AST-533`

**As a real Billing Clerk, `pine-hill`, at 1440 and 1280, identical:**

```
tech = {"tag":"input","type":"text","role":"combobox","disabled":false,
        "label":"Technician","help":null}
uuid visible anywhere on screen: NONE
picker options (first 3): ["Avery Cole · avery.cole@sample.test",
                           "D. Ortiz · d.ortiz@sample.test",
                           "J. Okoro · j.okoro@sample.test"]
```

`role="combobox"` is the kit's `SearchSelectField`; the old degrade rendered a bare
`TextField` with no role and the uuid sentence. **`AST-B-04`'s own done-test** — *"shows
a searchable picker listing Sam Reyes · sam.reyes@sample.test, and no UUID appears
anywhere on the screen"* — **is met.**

**And the half that must stay true, same session:**

| read | status |
|---|---|
| `GET /users` | **403 `BR-IDN-009`** |
| `GET /work/crew-directory` | **200**, 7 rows of `{id, name, email}` |

### 2.2 · The five date inputs — `DEF-MET-4974`, B14 rule 7

`pine-hill` `E-5000`, both widths, identical:

| screen | input | before | after |
|---|---|---|---|
| 22 Reassign | `effective_date` | `min:null max:null value:""` | **`min:2026-01-05`** · `value:2026-09-12` |
| 22 Reassign | `final_read_date` | `min:null max:null` | unchanged — **deliberate** |
| 23 Log repair | `date` | `min:null max:null value:""` | **`max:2026-09-12`** · `value:2026-09-12` |
| 24 Retire 1 | `retire_date` | `min:null max:null value:""` | **`min:2026-01-05`** · `value:2026-09-12` |
| 24 Retire 1 | `final_read_date` | `min:null max:null` | unchanged — **deliberate** |

Each bound arrives with its sentence: *"Not before this assignment started."*, *"Cannot
be in the future."* (already there, now enforced), *"Not before the install date."*

### 2.3 · The raise form — `DEF-MET-4973`, `BR-AST-534`

**`brazosbend` (0 templates), both widths:**

```
submit  {"disabled":true,
         "title":"No template applies to this kind of asset.",
         "describedby":"raise-none"}
picker  {"disabled":true,"options":1,"describedby":"raise-none"}
refusal {"id":"raise-none",
         "text":"No template applies to this kind of asset. Ask an admin to add one."}
badge   WRK-24
```

Before: `{"disabled":true,"title":null,"describedby":null}`. **`pine-hill` (8 templates):**
the picker is live with 5 options rendered, the submit disabled until one is chosen and
carrying **no** reason — the mirror assertion, so the fix cannot become a lie.

### 2.4 · The badge — `DEF-MET-4978`

```
$ git grep -c "WRK-19" 9f11b9413 -- 07-frontend/src
routing/screenIds.ts:4 · work/AwaitingApprovalPage.tsx:1
work/TemplatesPage.tsx:1 · work/mobile/screenIds.ts:1        →  7 lines, 4 files
```

**Exactly step 1's stated done-test.** The blueprint's *"returns nothing"* would have
deleted the retirement ruling and two minting precedents. ⚠ **My own explanatory comment
originally spelled the retired id and pushed the count to 13 in 6 files** — a fifth copy
of the very string this row exists to remove. It was rewritten to cite `DEF-MET-4978`
and `routing/screenIds.ts` instead.

---

## 3 · WHERE THIS LANE DISAGREES WITH THE DRAWINGS — AND BUILT NEITHER

**Figure 35 draws a `Cancel` on retire step 1.** Measured footer, both widths:
`["Continue"]`. **Step 1's §5.3 is confirmed against the running product.** The redrawn
figure 36 replaces it with `Save as draft` marked **NEW**, which is `AST-B-28`.

**Figure 42 draws the raise footer as `Cancel · Raise work order ✓`**; the product draws
the commit first. **B14 rule 38 names this exact case** — *"that the footer puts Cancel
on the left … is not layout, it is FORM CONSTRUCTION"* — so the drawing loses, this
sentence is the record, and nothing was built.

**Figure 35 also draws the retire date's help as *"Cannot be before the install date."***
The product renders *"Any current assignment closes on this date."*, and the install-date
sentence is a SERVER refusal — step 1's §5.2, confirmed. **The BOUND is now enforced and
a second short sentence states it**; the drawing's wording was not copied.

---

## 4 · WHAT WAS LEFT, AND WHY EACH IS NOT A DEFERRAL OF CONVENIENCE

| left | why |
|---|---|
| **The Today shortcut** (rule 7's other half) | a new control on every date field in the product plus a key in eleven catalogues, and **no ruling authorises it**. Wave A left it for the same reason |
| **Both `final_read_date` bounds** | nothing states one, and `max = today` would make the field **stricter than the path its own blank value takes** — blank resolves to the effective/retire date, which may lawfully be forward-dated |
| **A navigating control on the raise refusal** | both destinations that would work are unruled: the Work templates screen is admin-only (a clerk meets a second refusal) and a template-less order has no `type` to send |
| **`BR-AST-534`'s retired-asset instance** | it is the detail page's DOOR (`AST-B-02`, `DEF-MET-4965`, lane 2), and `/assets/{id}/work-order-templates` carries no lifecycle status |
| **The raise footer's button order** | B14 rule 38: recorded, not built |
| **R12 / field order** | `DEF-SHL-4921` owns it kit-wide |

---

## 5 · THE CHECKS

| check | result |
|---|---|
| `npx tsc --noEmit` | **0 errors** — and proved able to fail first (`TS2322` on a deliberate error), because a silent pass is law 7's *incapable of failing* shape |
| `npx vitest run src/features/assets …` | **9 files · 220 passed · 12 todo · 0 failed** (177 at step 1; **+17 cases** from this lane) |
| `pytest tests/test_br_ast_533_crew_directory.py` | **6 passed** |
| `run_gates.py` | **77 PASS · 43 FAIL · 3 SKIP — MERGE BLOCKED**, the same counts step 1 measured on a clean tree |

**Every guard here was shown RED on the fault it exists for, then green** — the crew
read's key set (by adding `role_code` back), its permission class (by swapping in
`SystemAdminOnly`), the do-not-widen assertion (by widening `UsersView`), the technician
control (by restoring the uuid text box), the date bound (by deleting `max`), the
disabled submit's reason (by removing `title`/`aria-describedby`), and the unwired-prop
guard (by restoring `?? ""`).

### The one gate failure that was mine, and the one that was not

⚠ **MINE, AND CAUGHT BY THE SUITE:** `G106 cited-ids-exist` named `DEF-MET-4979` in
`DateCell.tsx` — an id I had written into a docstring before the allocator answered.
**The allocator gave `4990`, then `4990` was taken by a sibling at push time and the
verify caught it, so the row is `DEF-MET-4991`.** Every citation was corrected and G106
no longer names it.

⚠ **NOT MINE, AND DATED RATHER THAN ASSERTED:** `routeBUtilities.test.ts` fails on
`rounded (asked for by features/metering/UnitDetailPage.tsx)`.
`git log -S` dates that token to **`c724ab25a`, 2026-09-09, CR-089 wave G** — three days
before this lane started — and my copy of that file is **byte-identical to the tip**.
Calling a red *pre-existing* without dating it is what `DEF-CWP-4187` cost, so it is
dated here.

---

## 6 · TWO THINGS THIS PASS LEARNED THAT ARE NOT ABOUT ASSETS

**1 · A fixture that supplies a prop the router does not is indistinguishable from a
wired screen.** All 34 existing cases on these screens pass `today="2026-08-16"`;
`App.tsx` passes nothing. So a green suite and a browser disagreed, and `DEF-MET-4991`
had been live since `CR-028 AST-W4`. The guard now mounts the page **without** the prop.

**2 · The push guards earned their keep three times in one push.** `push_paths.sh`
refused a stale blob on 13 paths; the register rebuild found a sibling's `DEF-MET-4989`
that a plain commit would have **reverted by subtraction**; and `allocate.py --verify`
found `DEF-MET-4990` taken between allocation and push. None of those is visible to a
file count, to `git show`, or to a clean `git status`.
