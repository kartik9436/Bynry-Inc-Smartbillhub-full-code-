# The QA tester's 23 portal pages (WCAG 2.1 AA assessment, received 2026-10-23)

This is the tester's own list, as given. It reconciles our scans (53 routed pages) with the assessment's "22 of 23 pages". "Not fully specified" is the tester's wording.

| # | Page | Path | Sign-in | Tester's automated scan (Chrome) |
|---|---|---|---|---|
| 1 | Home | `/` | No | Low contrast (6) |
| 2 | Pay a bill | `/pay` | No | Low contrast (7) |
| 3 | Report a problem | `/report` | No | Low contrast (5) |
| 4 | Ask us for something | `/ask` | No | Low contrast (5) |
| 5 | Track | `/track` | No | Low contrast (2) |
| 6 | Start service | `/start-service` | No | Low contrast (5) |
| 7 | Sign in | `/sign-in` | No | No problems found |
| 8 | Set up login | `/enrol` | No | Low contrast (5) |
| 9 | Forgot password | `/forgot-password` | No | Low contrast (1) |
| 10 | Home | `/home` | Yes | Low contrast (12); unnamed dropdown (1) |
| 11 | Help | `/help` | Yes | Low contrast (2) |
| 12 | Bills | `/bills` | Yes | Low contrast (9); incorrect ARIA attribute (3) |
| 13 | Usage | `/usage` | Yes | Low contrast (27) |
| 14 | Payments | `/payments` | Yes | Low contrast (15) |
| 15 | Requests | `/requests` | Yes | Low contrast (1) |
| 16 | My details | `/my-details` | Yes | Not fully specified |
| 17 | Account | `/account` | Yes | Not fully specified |
| 18 | Accounts | `/accounts` | Yes | Low contrast (3) |
| 19 | Pay now | `/pay-now` | Yes | Not fully specified |
| 20 | A bill | `/bills/BL-2609-000651` | Yes | Not fully specified |
| 21 | Bill document | `/bills/BL-2609-000651/document` | Yes | Not fully specified |
| 22 | Payment plan | `/ask-for-a-plan` | Yes | Not fully specified |
| 23 | Past due | `/overdue` | Yes | Not fully specified |

**Note.** Bills' "incorrect ARIA attribute (3)" is F-13 (`aria-sort` on a button). That is Group I, deferred by the PO on 2026-10-23, so it stays until Group I is built.
