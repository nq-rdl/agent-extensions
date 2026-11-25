Title: THHSRDLENQ-90210: latest address at encounter missing from the resolver

## Enquiry and pin
Enquiry THHSRDLENQ-90210 (approval THHSAQUIRE-8675309), ledger LIFT-1.
Pipeline: https://github.com/nq-rdl/request-example/blob/0123abc/sql/v1/90210_request.sql lines 40-72.
Pinned framework_ref v0.7.0. Confirmed by jane.smith on the hand-off comment
https://github.com/rdl-service-desk/service-desk/issues/90210#issuecomment-1.

## Shortfall
The request's own `sql/v1/90210_request.sql` joins ADDRESS by hand to get the address at encounter.
Cohort criteria for the sample study are copied below: ...
