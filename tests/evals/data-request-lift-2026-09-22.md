# Independent lift forward test (2026-09-22)

Read-only discovery; no issue bodies (including agent-extensions #333), confirmations, mutations, DB queries, patient rows or enquiry edits. Read the new lift skill, evidence template, shared lifts contract and guardrails. Did not initialise .sqlreview because this test explicitly prohibited enquiry writes. No candidates are confirmed/filed; no delivery limitation is published.

## Sources and reproducibility

THHSAQUIRE-1836 main checkout is only the service-desk template (cb76419). Local origin/enq/1172-v2 at 368a79597646f90fd252adf3f75123a454a16ccf contains an early 125-line draft, not the implemented workaround. Read-only remote branch/tree discovery located implemented source at **5f03410b17eb72936dd225e7ddff82a9d6871160**, branch claude/gallant-curie-7rmo96. All primary pipeline line references below mean src/pipelines/falls_service_cohort.py at that revision (303 lines). Delivery to a researcher was not independently established.

Its pyproject.toml:138–139 specifies v0.1.1 for both libraries. pixi.lock:773–774,10834,10845 resolves exactly to core **a0cf6643af7983f28b65299875f2baf54c6c9fc8** and plugins **6ae27007a4edc9cfc2f5bd27923c06cf2cc56a03**, matching inspected local v0.1.1 tags. Earlier branch lock used relative local directories; therefore that earlier lock alone did not prove installed revisions.

Inspected canonical sql/v0-1-0/1172_request.sql at 368a795:48–90 (date/facility/adult/fall criteria; CLINICAL_EVENT encounter correlation, current validity and verified status), 54–69/96–99 (encounter output). The implemented Indigenous SQL is a later operator-supplied contract documented in pipeline:77–87 and tests_framework/unit/test_falls_service_cohort.py:179–208; it is absent from the original SQL. No independent dataops DDL/index or operator-original query was obtained; storage/cardinality claims remain unverified.

## Independently discovered candidates

1. **Existing-unit-gap: current-active Indigenous status plus display.** Need encounter-preserving status code/display enrichment. Workaround pipeline:58–125,223–224,237–254 uses ENCOUNTER → Raw.PERSON → Raw.PERSON_INFO → Raw.CODE_VALUE, LEFT joins throughout, ACTIVE_IND=1 and END_EFFECTIVE_DT_TM>GETUTCDATE() on the latter three, INFO_SUB_TYPE_CD=11886497, CODE_SET=100007. Pinned plugins qb_plugins/iemr/resolver.py:787–823 supplies WithIndigenousStatus but only joins PERSON_INFO by PatientId and subtype and selects ValueCd; no active-current filters, display resolution or person validity. Pinned tests/test_iemr_sql.py:621–649 tests table/subtype and join mode, not that missing behaviour. EdExtractResolver explicitly lacks this enrichment (qb_plugins/bireporting/resolver.py:34–40). Owner query-builder-plugins; bounded enhancement to the existing unit and a supported encounter-anchor composition path, retaining caller-selected temporal semantics. Tests: expired/inactive info/code/person, absent linkage preserving encounters, code-set isolation and multiple active values. Canonical minimal contract is precisely the inspected workaround JOIN/ON predicates above; independent schema evidence and duplicate policy are still required before calling it verified. Current workaround sorts by ValueCd and keeps the first (242–250): this is a request choice, not a safe library default.

2. **New-capability candidate: instance-level spec descriptions and resolver provenance.** Pipeline:159–171 duplicates specs:174–183 with hand-maintained descriptions. BasePipeline at 368a795:266–306,392–449 stores arbitrary strings and exports them; no link to resolver implementation. Inspected core clinical/specifications.py:37–85, clinical/introspection.py:33–110 and tests/clinical/test_introspection.py:1–100 at the actual core SHA. Existing get_schema_manifest enumerates supported spec classes, docstrings and field metadata, not the configured spec tree with concrete parameter values, resolved handler/source provenance and stable description output. Owner query-builder; extend introspection or add an instance-description API, not invented SQL. Proposed contract: given resolver and configured spec tree, return serialisable ordered instance parameters/operator structure plus handler/source metadata; preserve explicit researcher wording as override. Regressions: nested OR/NOT, changed date/age reflected automatically, plugin handlers, resolver-level facility configuration, deterministic output, unknown custom specs without false descriptions. Classification remains a proposal: no requirement for a specific public API name was found.

3. **New-capability candidate at this old pin: coordinated named result sets/materialise-once execution.** Pipeline:211–224 obtains cohort IDs in Python and builds a second IN query. Core analysis_pipeline/pipeline.py:223–250 has create_temp_table; tests/test_analysis_pipeline.py:581–583 checks its availability. Whole pinned-repository search found no register_result or execute_pipeline_results definitions. Do not claim all materialisation is missing: it exists. Proposed core-owned gap is named-result registration/execution on a shared connection, with cleanup and output mapping. Canonical requirement from this request is the same encounter cohort feeding an enrichment while preserving grain; the existing source has only one final merged deliverable, so a general multi-dataset API is not yet demonstrated as necessary. Keep candidate unresolved rather than filing a broad core redesign. Test proposal if requirement is confirmed: cohort built once, dependent results share temp-table lifetime, empty result schemas, failure cleanup; source-specific enrichment stays with plugins.

## Request-specific findings (no new library issue)

- OR encounter duplicates are already addressed by pinned EdExtractResolver.resolve_all(dedupe_or=True): pipeline:184–192; plugin resolver:106–155 and tests/test_bireporting_sql.py:265–295 directly cover it. Do not rediscover a missing dedupe feature from the old draft warning. A WHERE-OR performance alternative is distinct and not justified without performance evidence.
- LOS in hours (pipeline:226–235), output aliases/order (258–300), fall text/concept choices and adult/date/facility scope are local composition/output choices. No 30-day mortality appears. Latest-versus-at-time address is not an implemented choice here; source output is simply Present Suburb/Postcode and its temporal interpretation remains unverified.
- The lowest-ValueCd duplicate-active-row choice at 242–250 needs explicit researcher acceptance and is not proven uniquely deterministic if duplicate codes have different displays. Keep it separate from the reusable validity/display fix.
- Date resolver calls utc_bounds for ED ArrivalDate (plugins resolver:242–257; dates.py:11–33), whereas original SQL uses unshifted day bounds. Without dataops timezone evidence this is an unresolved correctness concern, not proof of a new capability.

## Additional branch and trial limits

A subsequent remote branch claude/magical-euler-ll6lsv at **1c34c414579b3181486e56523445026f8f894af3** adds WithClinicalEventValue composition and a finalize SQL cache. Critically, its pyproject.toml:146 pins plugins **66d5ab94971844346ee2e34be49a36b92d96ddc1**, while pixi.lock:782/10995 pins **732e613cc178da3277908ec2a8a1a297901a8839**. Core remains the inspected v0.1.1 SHA. Do not label either plugin revision its actual installed pin without resolving this mismatch; the above pinned findings apply specifically to 5f03410. This is a useful failure case for the skill's pin verification, and latest-branch close-out remains incomplete.

Inspected two additional checkout inventories: THHSAQUIRE-1893 at 5b10cccffcaf6c72500e57c6d2c6bab58cfe67fa and THHSAQUIRE-2094 at 0b394655119781fba790fdeac9efefb48bc1cbaf. Both expose scaffold base/cohort/example/raw-SQL pipelines and core v0.1.1 (pyproject:152), but no request-specific delivered SQL in their current working-tree inventories. They are not two completed backlog dogfood cases. No three-enquiry false-positive rate or completed three-enquiry trial can honestly be claimed.

## Skill result

The discovery instructions led beyond raw SQL to manual metadata and correctly distinguished a sufficient dedupe API from a missing feature. Evidence block is usable for the Indigenous enhancement with the remaining DDL/canonical provenance and modelling caveats stated. Source-path discovery and dependency-manifest/lock mismatches are practical hazards worth making explicit. No close-out, filing, recurring follow-up or release/recomposition is authorised by this read-only test. No recurrence evidence was found; default to forward-only.

## Post-discovery comparison (parent review)

Only after independent discovery, compared the findings with
[nq-rdl/query-builder-plugins #26](https://github.com/nq-rdl/query-builder-plugins/issues/26)
and [nq-rdl/query-builder #84](https://github.com/nq-rdl/query-builder/issues/84).
The first candidate reproduces #26's active-current/display shortfall; the second
reproduces #84's self-description and resolver-filter provenance need. This is an
independent discovery result, not a completed human-confirmed close-out. Canonical
provenance gaps and the three-enquiry trial remain open as described above. The
experimental hook stays disabled; no library/enquiry issues were created in this test.
