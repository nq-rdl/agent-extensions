Title: Resolver cannot return the address in force at an encounter date

## Library baseline
Owning library: query-builder. Pinned release: v0.7.0.

## Need and classification
Proposed (engineer, unconfirmed): existing-unit-gap. A cohort output needs the address that was
current at each encounter's start, one row per encounter.

## Pinned capability inspected
`resolvers/iemr/resolver.py` and its tests at v0.7.0: only the latest address is exposed.

## Shortfall
No spec returns a historical address. The workaround joins the address table by hand.

## Delivered workaround
A hand-written join from encounter to address on person with a date-range condition.

## Canonical SQL / expected contract
Synthetic reproduction:

    encounter(enc_id, person_id, start_dt): (1, 10, 2024-03-01)
    address(person_id, suburb, valid_from, valid_to): (10, 'A', 2023-01-01, 2024-01-01),
                                                      (10, 'B', 2024-01-01, NULL)
    expected: (enc 1, suburb 'B')   actual: no column available

## Proposed fix and tests
Add an at-time address spec. Regression: the synthetic rows above return suburb 'B'.

## Rollout
Delivered under the old pin; forward release only, no backport.
