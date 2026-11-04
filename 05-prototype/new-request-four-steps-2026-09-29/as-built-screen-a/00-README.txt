REQ-03 · New Request in four steps — lane SCREEN-A, steps 1 and 2.
Put these beside 05-prototype/new-request-four-steps-2026-09-29/*.png.
Divergences are stamped in that folder's DIVERGENCES-steps-1-and-2.md.

signed in as dana@brazosbendutilities.com
PASS  step 1's page title is the drawn question — Who is this request for?
PASS  the sub-line reads `Step 1 of 4` — 1 found
PASS  the eleven fields are in the drawn order — ["Applying as","Channel","Full name","Email","Phone","Date of birth","Tax ID","Driver's license","Social Security Number","Customer category","Sub-category"]
PASS  `Tax ID` is drawn and refused for a person
PASS  the co-applicant fields are ABSENT before the tick
PASS  ONE document button — `Add another document` is gone
PASS  `Documents` carries the drawn sub-line
  shot 01-applicant-1440.png (1440x1702)
  shot 01-applicant-1280.png (1280x1702)
  shot 01-applicant-420.png (420x2782)
PASS  the three co-applicant fields expand on tick, and are LIVE
  shot 01b-applicant-coapplicant-open-1440.png (1440x1782)
  shot 01b-applicant-coapplicant-open-1280.png (1280x1782)
  shot 01b-applicant-coapplicant-open-420.png (420x3077)
PASS  step 2's page title is the drawn question — Where is the service going?
PASS  `Found in Premises` is drawn, with its own sentence, before anything is typed
  shot 02z-property-untouched-1440.png (1440x1200)
PASS  `+ Premises` is absent while NOTHING matched
PASS  the typed address is kept word for word (BR-CUS-070)
PASS  `address_city_as_given` is read-only
PASS  `address_state_as_given` is read-only
PASS  `address_postal_code_as_given` is read-only
PASS  `Mailing address` replaces `Billing address`
PASS  ticked, the mailing block PRINTS the service address
PASS  ticked, the five mailing boxes are not drawn at all
  shot 02-property-1440.png (1440x1348)
  shot 02-property-1280.png (1280x1348)
  shot 02-property-420.png (420x2219)
PASS  cleared, the five fields expand and are LIVE
  shot 02b-property-mailing-expanded-1440.png (1440x1493)
  shot 02b-property-mailing-expanded-1280.png (1280x1493)
  shot 02b-property-mailing-expanded-420.png (420x2504)
NOTE  the FOUND state was not reachable on this seed — no premises matched 'Balcones'. NOT a pass: the absence of `+ Premises` in the found state is proved by the DOM test instead, which fakes a matching row.

ALL CHECKS PASSED