# Taxes & fees — the full web walk (task 9), as agreed with the PO 2026-10-03

PO, verbatim: *"I want to create Tax code for all juridictions , all Utility Services { single or all or multple} I want to create tax for Customer class - take menaingful pratcice scenarios ; then save these codes. then view these code see all ifnrmation saved correctly and displayed correctely then edit those tax codes and see updates are correctly saved - inlcuding version hisorty and it return only 1 record when billing ask it ; the changes reflects in plans audit"*.

Desktop only (PO: *"phone edit will not required; this si desktop version"*). Real app, real PostgreSQL 16, two utilities, clicking in a browser like a clerk. Every step gets a screenshot, opened and checked not blank. Every figure below is the walk's own test data, not a signed rule. Every bug found is filed first, fixed, and walked again; anything touching ❄️ money math, a signed rule or RLS goes to the PO instead.

**Utility A** (Ottumwa Water Works) runs water, sewer, trash and storm water. **Utility B** is a second utility with no taxes.
Example bill used throughout: usage $40.00 + base $20.00 = **$60.00**, 1 meter, 12 kgal used.

⚠ **Amended 2026-10-03 by PO ruling** (*"Only what works today. An outside-city charge stays on the plan"*): taxes 1.4 and 1.7 are not created with an "Outside city limits" boundary — the outside-city surcharge is set on the plan and checked there — and 1.5 uses *Everywhere* instead of a named place. Step 2.6 is dropped.

## Phase 0 — setup
| # | What | Must be true |
|---|---|---|
| 0.1 | Utility A: 4 services on, 8 customer classes, authority accounts in Settings › Accounting (TX Comptroller, Wapello County, City of Ottumwa) | They show in the Filing step's *Account with the authority* dropdown |
| 0.2 | Plans: Residential Standard, Commercial, Agricultural, each with accounts | The Plans tab can show real account counts |
| 0.3 | Utility B exists, no taxes | Used in phase 7 |

## Phase 1 — create one tax per practical case (every authority, every service shape, every class shape, every way of charging, every boundary)
| # | Tax | Authority | Services | Customer classes | Charged as | Rate | Boundary | On the $60.00 bill |
|---|---|---|---|---|---|---|---|---|
| 1.1 | State sales tax | State | **All** | Commercial, Industrial (several) | % of bill | 6.25% | Everywhere | $3.75 |
| 1.2 | County utility tax | County | Water, Sewer (several) | Every class | % of bill | 2% | Everywhere | $1.20 |
| 1.3 | City franchise fee | City | **All** | Every class | % of bill | **150% typed by mistake** (warning shown, saved anyway) | Inside city limits | $90.00 (fixed in 4.3) |
| 1.4 | Outside-city surcharge | The utility itself | Water (**one**) | Every class | Fixed per bill | $5.00 | Outside city limits | $5.00 |
| 1.5 | Riverside storm fee | Special district | Storm water (one) | Residential (**one**) | Per meter | $1.25 | Named place: Riverside district | $1.25 |
| 1.6 | Water conservation fee | State | Water (one) | Residential, Commercial | Per unit used | $0.05 per kgal | Everywhere | 12 kgal × $0.05 = $0.60 |
| 1.7 | Rural trash fee | County | Trash (one) | Agricultural (one) | Fixed per bill | $2.00 | Outside city limits | $2.00 |
| 1.8 | A draft | City | — | — | — | — | — | *Save draft & exit* half way, reopen, finish, save |

For each: list row appears with Version v1, From, To, GL code, premises reached; **exactly one row in the database**; no tax is offered a service Utility A does not run.

## Phase 2 — the form refuses and warns correctly
| # | What I do | Must be true |
|---|---|---|
| 2.1 | New tax, everything empty, Continue | Each missing box says what is wrong; nothing typed is lost |
| 2.2 | Services dropdown | Only water, sewer, trash, storm water, with "All services" first |
| 2.3 | Classes dropdown | "Every customer class" first, then the 8 classes |
| 2.4 | Rate 62.5 | Shows 62.5% and "check the rate" on step 2 and on Review |
| 2.5 | Filing: no liability account, bad email | Both refused by name |
| 2.6 | Boundary = named place, no place name | Refused |

## Phase 3 — view every tax
| # | What I do | Must be true |
|---|---|---|
| 3.1 | Open each of the 7 taxes | Header (code, version, Over 20% where it applies, Filing due), tiles, *Rate and scope* and *On the bill and filing* show **every value entered in phase 1, exactly** |
| 3.2 | List | "Over 20%" banner counts 1.3; its pill shows; dates are MM/DD/YYYY |

## Phase 4 — edit, three ways
| # | What I do | Must be true |
|---|---|---|
| 4.1 | 1.2 → Edit → *Name and filing*: rename, change due date and reminder email | Rate and reach locked; **same row** updated; still v1; one Audit line per change, before → after |
| 4.2 | 1.1 → Edit → *New rate from a date*: 6.25% → 6.5% from 11/01/2026 | v1 ends 10/31/2026, v2 starts 11/01/2026; **two rows, nothing deleted**; header shows *Next: 6.5% from 11/01/2026* until then |
| 4.3 | 1.3 → Edit → *Fix a mistake*: 150% → 3%, reason "Typed as 150%" | Reason required; v1 marked superseded and kept; v2 has the same dates; Over 20% banner and pill gone |
| 4.4 | Try a new rate starting before the version's start | Refused by name |
| 4.5 | Overview versions table and Audit for 4.1–4.3 | Both show every version and every change with who, when and why |

## Phase 5 — billing gets exactly ONE record
| # | What I do | Must be true |
|---|---|---|
| 5.1 | Ask the billing lookup for 1.1 on 10/31/2026 and on 11/01/2026 | **One** row each: 6.25% then 6.5%, never both, never none |
| 5.2 | Ask for 1.3 on any date in its window, after the fix | **One** row, the 3% correction; the superseded 150% row is never returned |
| 5.3 | Ask for 1.2 after the name/filing edit | **One** row, the same row as before |
| 5.4 | Bill run on 10/15/2026 | One line per tax on each bill; 1.1 = $3.75 |
| 5.5 | Bill run on 11/15/2026 | 1.1 = $3.90 (6.5% of $60.00); the October bill still shows $3.75 |
| 5.6 | A bill issued at 150% before the fix | Keeps $90.00; correcting it is separate (OQ-310) |

## Phase 6 — plans and audit
| # | What I do | Must be true |
|---|---|---|
| 6.1 | Plans tab on each tax | Real plans with real account counts |
| 6.2 | Add 1.4 to a plan, remove it again | Both appear in Audit |
| 6.3 | Audit tab after phase 4 | Who, when, what, before → after, reason |

## Phase 7 — isolation and languages
| # | What I do | Must be true |
|---|---|---|
| 7.1 | Sign in to Utility B | None of A's taxes on any screen; the server returns none of them; opening one of A's addresses gives nothing |
| 7.2 | Switch through the other 10 languages | No English left on these screens |

## Evidence
Screenshots `taxwalk_<phase>_<step>.png`, a pass/fail table in `08-qa/`, and every bug: where found, what the user saw, which build fixed it or why not.
