```
Sales Analytics Project – Bronze & Silver Completion Summary
Project Architecture
PostgreSQL
      │
      ▼
AWS Glue Python Shell
      │
      ▼
Amazon S3 (Raw JSON)
      │
      ▼
Snowflake Bronze
      │
      ▼
Snowflake Silver
      │
      ▼
Snowflake Gold

This architecture follows the SME requirement of a Bronze → Silver → Gold Medallion Architecture.


Phase 1 – Data Ingestion
Source

PostgreSQL

Tables

raw.leads_raw

raw.lead_activites_raw

raw.close_crm_users_raw

raw.custom_activites_raw
AWS Glue Python Shell

Implemented:

PostgreSQL connection using AWS Secrets Manager
Incremental extraction
Automatic watermark tracking
Chunk processing (1000 rows)
JSON serialization
S3 upload
Automatic watermark update
Additional Enhancement

The SME mentioned malformed JSON inside every source table.

During implementation we discovered only one table required a real repair:

raw.custom_activites_raw

The field

raw_data
    └── JSON_OBJECT

contained malformed JSON because descriptions contained apostrophes.

Example

If [Call Outcome] is "No Show's" ...

This caused

TRY_PARSE_JSON
Python json.loads
ast.literal_eval
SQL UDF

to fail.

Solution

Instead of repairing inside Snowflake, we modified Glue only for

custom_activities_raw

Glue now

repairs malformed JSON
converts JSON_OBJECT into valid JSON
writes clean JSON into S3

Only this table was modified.

The remaining three extraction flows remained unchanged.


Bronze Layer

Successfully built

LEADS_RAW

LEAD_ACTIVITIES_RAW

CLOSE_CRM_USERS_RAW

CUSTOM_ACTIVITIES_RAW

Validation

JSON loaded successfully
INSERT_DATE populated
Row counts validated
COPY INTO completed successfully
Silver Layer

Completed

CLOSE_CRM_USERS_PROCESSED

Implemented

JSON flattening
MD5 Hash
CDC
MERGE
USER_ID deduplication
LEAD_ACTIVITIES_PROCESSED_TRANSIENT

Implemented

JSON repair
Deep unwrapping
Flatten nested arrays
LEAD_ACTIVITIES_PROCESSED

Implemented

CDC
MD5 Hash
MERGE
Deduplication

Business key

LEAD_ID

ACTIVITY_ID

Latest record retained using

ACTIVITY_AT

Exactly as required by SME.

LEAD_ACTIVITIES_EMAIL

Successfully extracted

Email body
Sender
Attachments
Opens
Templates
CUSTOM_ACTIVITIES_TRANSIENT

Loaded repaired JSON from Bronze.

CUSTOM_ACTIVITIES

Flattened metadata

Columns

CUSTOM_ACTIVITY_ID

CUSTOM_ACTIVITY_NAME

CUSTOM_ACTIVITY_OUTCOME_ID

CUSTOM_ACTIVITY_OUTCOME_NAME

MD5_HASH
Discovery

Initially

450 rows

were loaded.

Investigation showed

18 snapshots

contained the same

25 activity definitions

Result

18 × 25 = 450
Resolution

Loaded only the latest snapshot.

Final

25 rows

which matches the metadata expected from the source.

CUSTOM_ACTIVITIES_ALL_LEADS_DETAILS

Created bridge table

Contains

LEAD_ID

ACTIVITY_ID

ACTIVITY_AT

WRAPPED_ACTIVITIES

MD5_HASH

Total rows

33,628
LEADS_ACTIVITIES_SUMMARY

Created final Silver business table.

Initially

1,063,730

rows

Investigation discovered duplicated ACTIVITY_ID values inside

CUSTOM_ACTIVITIES_ALL_LEADS_DETAILS

Resolution

Deduplicated using

ROW_NUMBER()

PARTITION BY ACTIVITY_ID

Final count

1,063,628

matching

LEAD_ACTIVITIES_PROCESSED
Validation Performed
1 Row Count Validation
LEAD_ACTIVITIES_PROCESSED

=

LEADS_ACTIVITIES_SUMMARY

Result

1,063,628

=

1,063,628

PASS

2 Duplicate Validation

Verified

LEAD_ID

ACTIVITY_ID

No duplicate business records after CDC.

PASS

3 MD5 Validation

Verified

Every processed table contains

MD5_HASH

PASS

4 Custom Activity Lookup Validation

Query

CUSTOM_ACTIVITY_ID IS NOT NULL

AND

CUSTOM_ACTIVITY IS NULL

Returned

0 rows

Meaning

Every custom activity successfully mapped to its lookup table.

PASS

5 User Lookup Validation

Query

USER_ID IS NOT NULL

AND

DEA_INTERNAL_EMAIL IS NULL

Returned

780,786 activity rows

Initially appeared to be an issue.

Further investigation found only

104 unique USER_IDs

were missing.

Those same users appeared repeatedly throughout activity history.

Join Validation

Verified

LEAD_ACTIVITIES_PROCESSED.USER_ID

↓

CLOSE_CRM_USERS_PROCESSED.USER_ID

The join works correctly.

Matching users populate

DEA_INTERNAL_NAME

DEA_INTERNAL_EMAIL

The missing values are caused by missing records in

close_crm_users_raw

rather than an issue in the pipeline.

```

# next

```



SME Requirement Review

Requirement specifies

Close CRM Users

↓

Map activities to CRM users

↓

Identify setters

↓

Identify closers

Only one user source is documented.

No requirement exists for

archived users
deleted users
fallback user mapping
secondary user source

Therefore the implementation follows the SME requirements exactly.

Issues Encountered
Issue 1

Malformed JSON inside

CUSTOM_ACTIVITIES_RAW

Resolution

Modified AWS Glue to repair JSON before S3.

Issue 2

Duplicate activity metadata

450 rows

Resolution

Loaded only the latest metadata snapshot.

Issue 3

Duplicate rows in Summary

Cause

Duplicate ACTIVITY_ID inside bridge table.

Resolution

Applied

ROW_NUMBER()

before joining.

Issue 4

Missing DEA user information

Cause

104 USER_ID values absent from

close_crm_users_raw

Conclusion

Source data limitation.

Pipeline implementation is correct.

Current Status
Bronze

 Complete

Silver
 Complete

JSON repair
CDC
MERGE
MD5
Deduplication
Incremental-ready
Business summary table
Validation completed

```

