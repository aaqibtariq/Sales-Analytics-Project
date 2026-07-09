# validation 

```

Discover the actual activity names 
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS TOTAL_RECORDS
FROM LEADS_ACTIVITIES_SUMMARY
GROUP BY CUSTOM_ACTIVITY
ORDER BY TOTAL_RECORDS DESC;

Discover the actual status values


SELECT
    STATUS_CHANGE,
    COUNT(*) AS TOTAL_RECORDS
FROM LEADS_ACTIVITIES_SUMMARY
GROUP BY STATUS_CHANGE
ORDER BY TOTAL_RECORDS DESC;

If there are many custom activities, let's specifically inspect those that mention strategy, triage, consultation, booking, inbound, or call.

SELECT DISTINCT
    CUSTOM_ACTIVITY
FROM LEADS_ACTIVITIES_SUMMARY
ORDER BY CUSTOM_ACTIVITY;

```

# validate triage call only

```


SELECT *
FROM LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '3) Triage Call'
LIMIT 20;

SELECT
    LEAD_ID,
    ACTIVITY_ID,
    CUSTOM_ACTIVITY,
    STATUS_CHANGE,
    TEXT,
    MEETING_STATUS,
    MEETING_STARTS_AT,
    MEETING_END_AT,
    CREATED_BY_NAME,
    ACTIVITY_AT
FROM LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '3) Triage Call'
LIMIT 50;

```

# validate outcomes

```

SELECT
    LEAD_ID,
    CUSTOM_ACTIVITY,
    ACTIVITY_AT
FROM LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '3) Triage Call',
    '5) Strategy Call',
    '7) New Sale'
)
ORDER BY
    LEAD_ID,
    ACTIVITY_AT;

    SELECT
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    COUNT(*) AS TOTAL
FROM LEADS_ACTIVITIES_SUMMARY
GROUP BY
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME
ORDER BY
    CUSTOM_ACTIVITY,
    TOTAL DESC;

    SELECT
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    COUNT(*) AS TOTAL
FROM LEADS_ACTIVITIES_SUMMARY
GROUP BY
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME
ORDER BY
    CUSTOM_ACTIVITY,
    TOTAL DESC;


    SELECT
    CUSTOM_ACTIVITY,
    STATUS_CHANGE,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    COUNT(*) AS TOTAL
FROM LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN ('3) Triage Call', '5) Strategy Call')
GROUP BY 1,2,3,4
ORDER BY CUSTOM_ACTIVITY, TOTAL DESC;


SELECT
    LEAD_ID,
    ACTIVITY_ID,
    CUSTOM_ACTIVITY,
    WRAPPED_ACTIVITIES
FROM LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '3) Triage Call'
LIMIT 5;


```

# validate bronze

```
SELECT
    JSON_OBJECT,
    INSERT_DATE
FROM LEAD_ACTIVITIES_RAW
LIMIT 5;

SELECT
    JSON_OBJECT
FROM LEAD_ACTIVITIES_RAW
WHERE JSON_OBJECT::STRING ILIKE '%custom.%'
LIMIT 10;

SELECT
    JSON_OBJECT
FROM LEAD_ACTIVITIES_RAW
WHERE JSON_OBJECT::STRING ILIKE '%Triage Call Outcome%'
   OR JSON_OBJECT::STRING ILIKE '%Strategy Call Outcome%'
   OR JSON_OBJECT::STRING ILIKE '%Offer Presented%'
   OR JSON_OBJECT::STRING ILIKE '%Contract Value%'
   OR JSON_OBJECT::STRING ILIKE '%Cash Collected%'
   OR JSON_OBJECT::STRING ILIKE '%Objections Faced%'
LIMIT 10;

```

# finding root cause of missing outocme

```
SELECT
    JSON_OBJECT::STRING AS RAW_JSON
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
WHERE JSON_OBJECT::STRING ILIKE '%custom.%'
LIMIT 5;

SELECT
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
WHERE JSON_OBJECT::STRING ILIKE '%cf_3JFRKeLpnUvmsOsVG478u5iAQZ5i5dPmvKbIkYLUaaH%'
LIMIT 1;

SELECT
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
WHERE JSON_OBJECT::STRING ILIKE '%cf_7EQ4NbImGdxDOQNwHVneg8JIjZj7wxprE3tMGhtwDOD%'
LIMIT 1;


SELECT
    JSON_OBJECT::STRING
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
WHERE JSON_OBJECT::STRING ILIKE '%cf_h3tYb9J6yPK7J4PMExDGsEqPCf8kBGBrRNIur2Dm5aN%'
   OR JSON_OBJECT::STRING ILIKE '%cf_dhJR4N7Rm6czuJthYGJP6KqUcuOzi7fqApGI7puWnMo%'
   OR JSON_OBJECT::STRING ILIKE '%cf_LGyzSTMPy37y87rDOUmFXlZA42HPSIpbipeT2OsQNHW%'
   OR JSON_OBJECT::STRING ILIKE '%cf_vIanPjPEit6ssajmWkcprF2V1nO1itfes8hOSnjmhfT%'
   OR JSON_OBJECT::STRING ILIKE '%cf_eyLbGJm9DYY7cuJk2otnCxhUEzK9ayEARiE81xPG5uY%'
LIMIT 10;


SELECT
    ACTIVITY.VALUE:id::STRING AS ACTIVITY_ID,
    ACTIVITY.VALUE:lead_id::STRING AS LEAD_ID,
    ACTIVITY.VALUE:custom_activity_id::STRING AS CUSTOM_ACTIVITY_ID,

    ACTIVITY.VALUE:"custom.cf_h3tYb9J6yPK7J4PMExDGsEqPCf8kBGBrRNIur2Dm5aN"::STRING AS TRIAGE_CALL_OUTCOME,
    ACTIVITY.VALUE:"custom.cf_dhJR4N7Rm6czuJthYGJP6KqUcuOzi7fqApGI7puWnMo"::STRING AS STRATEGY_CALL_OUTCOME,
    ACTIVITY.VALUE:"custom.cf_LGyzSTMPy37y87rDOUmFXlZA42HPSIpbipeT2OsQNHW"::STRING AS OFFER_PRESENTED,
    ACTIVITY.VALUE:"custom.cf_vIanPjPEit6ssajmWkcprF2V1nO1itfes8hOSnjmhfT"::STRING AS CONTRACT_VALUE,
    ACTIVITY.VALUE:"custom.cf_eyLbGJm9DYY7cuJk2otnCxhUEzK9ayEARiE81xPG5uY"::STRING AS CASH_COLLECTED,
    ACTIVITY.VALUE:"custom.cf_v385AJ8HSgepKQ3rvqo4yOA3nn49eGqz39DOqojJG5M"::STRING AS SETTER_USER_ID,
    ACTIVITY.VALUE:"custom.cf_Lv5lSqLOZwLrNhe5M7kWx2mF8Ge2Z23aw5NUNhbXvVS"::STRING AS CLOSER_USER_ID,
    ACTIVITY.VALUE:"custom.cf_mXqKxcmjnlEW223wM4lgb04XyYwDm0GJ9v99xWHPWO2"::STRING AS PROGRAM,
    ACTIVITY.VALUE:"custom.cf_aIN5Gtqq33tUCCBxFTW63FY6d3mofnKIfFqfWPkvNla"::STRING AS OBJECTIONS_FACED

FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
LATERAL FLATTEN(INPUT => R.JSON_OBJECT:raw_data:JSON_OBJECT:data) LEAD_OBJ,
LATERAL FLATTEN(INPUT => LEAD_OBJ.VALUE:activities) ACTIVITY

WHERE ACTIVITY.VALUE:type::STRING = 'CustomActivity'
LIMIT 100;

WITH CUSTOM_FIELD_TEST AS (
    SELECT
        ACTIVITY.VALUE:"custom.cf_h3tYb9J6yPK7J4PMExDGsEqPCf8kBGBrRNIur2Dm5aN"::STRING AS TRIAGE_CALL_OUTCOME,
        ACTIVITY.VALUE:"custom.cf_dhJR4N7Rm6czuJthYGJP6KqUcuOzi7fqApGI7puWnMo"::STRING AS STRATEGY_CALL_OUTCOME,
        ACTIVITY.VALUE:"custom.cf_LGyzSTMPy37y87rDOUmFXlZA42HPSIpbipeT2OsQNHW"::STRING AS OFFER_PRESENTED,
        ACTIVITY.VALUE:"custom.cf_vIanPjPEit6ssajmWkcprF2V1nO1itfes8hOSnjmhfT"::STRING AS CONTRACT_VALUE,
        ACTIVITY.VALUE:"custom.cf_eyLbGJm9DYY7cuJk2otnCxhUEzK9ayEARiE81xPG5uY"::STRING AS CASH_COLLECTED
    FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
    LATERAL FLATTEN(INPUT => R.JSON_OBJECT:raw_data:JSON_OBJECT:data) LEAD_OBJ,
    LATERAL FLATTEN(INPUT => LEAD_OBJ.VALUE:activities) ACTIVITY
    WHERE ACTIVITY.VALUE:type::STRING = 'CustomActivity'
)

SELECT
    COUNT_IF(TRIAGE_CALL_OUTCOME IS NOT NULL) AS TRIAGE_OUTCOME_ROWS,
    COUNT_IF(STRATEGY_CALL_OUTCOME IS NOT NULL) AS STRATEGY_OUTCOME_ROWS,
    COUNT_IF(OFFER_PRESENTED IS NOT NULL) AS OFFER_PRESENTED_ROWS,
    COUNT_IF(CONTRACT_VALUE IS NOT NULL) AS CONTRACT_VALUE_ROWS,
    COUNT_IF(CASH_COLLECTED IS NOT NULL) AS CASH_COLLECTED_ROWS
FROM CUSTOM_FIELD_TEST;

SELECT
    ACTIVITY.VALUE
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
LATERAL FLATTEN(INPUT => R.JSON_OBJECT:raw_data:JSON_OBJECT:data) LEAD_OBJ,
LATERAL FLATTEN(INPUT => LEAD_OBJ.VALUE:activities) ACTIVITY
WHERE ACTIVITY.VALUE:type::STRING = 'CustomActivity'
LIMIT 1;


SELECT
    OBJECT_KEYS(ACTIVITY.VALUE) AS TOP_LEVEL_KEYS
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
LATERAL FLATTEN(INPUT => R.JSON_OBJECT:raw_data:JSON_OBJECT:data) LEAD_OBJ,
LATERAL FLATTEN(INPUT => LEAD_OBJ.VALUE:activities) ACTIVITY
WHERE ACTIVITY.VALUE:type::STRING = 'CustomActivity'
LIMIT 5;

SELECT
    OBJECT_KEYS(JSON_OBJECT) AS ROOT_KEYS,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 1;

SELECT
    JSON_OBJECT:raw_data AS RAW_DATA,
    TYPEOF(JSON_OBJECT:raw_data) AS RAW_DATA_TYPE,
    JSON_OBJECT:data AS DATA_FIELD,
    TYPEOF(JSON_OBJECT:data) AS DATA_FIELD_TYPE
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 5;

SELECT
    TYPEOF(JSON_OBJECT:raw_data) AS RAW_TYPE,
    TYPEOF(PARSE_JSON(JSON_OBJECT:raw_data)) AS PARSED_TYPE,
    TYPEOF(PARSE_JSON(JSON_OBJECT:raw_data):data) AS DATA_TYPE
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 5;


SELECT
    VALUE
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
LATERAL FLATTEN(
    INPUT => R.JSON_OBJECT:raw_data:data
)
LIMIT 1;

SELECT
    OBJECT_KEYS(VALUE)
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
LATERAL FLATTEN(
    INPUT => R.JSON_OBJECT:raw_data:data
)
LIMIT 5;

SELECT
    ACTIVITY.VALUE:id::STRING AS ACTIVITY_ID,
    ACTIVITY.VALUE:lead_id::STRING AS LEAD_ID,
    ACTIVITY.VALUE:_type::STRING AS ACTIVITY_TYPE,
    ACTIVITY.VALUE:custom_activity_type_id::STRING AS CUSTOM_ACTIVITY_ID,
    ACTIVITY.VALUE
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
LATERAL FLATTEN(INPUT => R.JSON_OBJECT:raw_data:data) ACTIVITY
WHERE ACTIVITY.VALUE:_type::STRING = 'CustomActivity'
LIMIT 10;

SELECT
    ACTIVITY.VALUE:id::STRING AS ACTIVITY_ID,
    ACTIVITY.VALUE:lead_id::STRING AS LEAD_ID,
    ACTIVITY.VALUE:custom_activity_type_id::STRING AS CUSTOM_ACTIVITY_ID,

    ACTIVITY.VALUE:"custom.cf_h3tYb9J6yPK7J4PMExDGsEqPCf8kBGBrRNIur2Dm5aN"::STRING AS TRIAGE_CALL_OUTCOME,
    ACTIVITY.VALUE:"custom.cf_dhJR4N7Rm6czuJthYGJP6KqUcuOzi7fqApGI7puWnMo"::STRING AS STRATEGY_CALL_OUTCOME,
    ACTIVITY.VALUE:"custom.cf_LGyzSTMPy37y87rDOUmFXlZA42HPSIpbipeT2OsQNHW"::STRING AS OFFER_PRESENTED,
    ACTIVITY.VALUE:"custom.cf_vIanPjPEit6ssajmWkcprF2V1nO1itfes8hOSnjmhfT"::STRING AS CONTRACT_VALUE,
    ACTIVITY.VALUE:"custom.cf_eyLbGJm9DYY7cuJk2otnCxhUEzK9ayEARiE81xPG5uY"::STRING AS CASH_COLLECTED,
    ACTIVITY.VALUE:"custom.cf_v385AJ8HSgepKQ3rvqo4yOA3nn49eGqz39DOqojJG5M"::STRING AS SETTER_USER_ID,
    ACTIVITY.VALUE:"custom.cf_Lv5lSqLOZwLrNhe5M7kWx2mF8Ge2Z23aw5NUNhbXvVS"::STRING AS CLOSER_USER_ID,
    ACTIVITY.VALUE:"custom.cf_mXqKxcmjnlEW223wM4lgb04XyYwDm0GJ9v99xWHPWO2"::STRING AS PROGRAM,
    ACTIVITY.VALUE:"custom.cf_aIN5Gtqq33tUCCBxFTW63FY6d3mofnKIfFqfWPkvNla"::STRING AS OBJECTIONS_FACED

FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW R,
LATERAL FLATTEN(INPUT => R.JSON_OBJECT:raw_data:data) ACTIVITY
WHERE ACTIVITY.VALUE:_type::STRING = 'CustomActivity'
LIMIT 100;

```

```
Goal

We had finished the Bronze and Silver layers and were about to start the Gold layer.

The first Gold view according to the SME is:

INBOUND_STRATEGIES_BOOKED

Before building it, we wanted to validate that the required business fields actually existed.

This follows a good data engineering practice:

Always validate your source data before implementing business logic.

Step 1 — Validate the existing Silver data

We started by understanding what was already available in LEADS_ACTIVITIES_SUMMARY.

1. Validate activity names

We ran:

SELECT CUSTOM_ACTIVITY, COUNT(*)

Purpose:

Identify the actual CRM activity names.
Compare them with the SME document.

We found:

3) Triage Call
5) Strategy Call
7) New Sale
...

This matched the business hierarchy.

2. Validate status values

We checked:

STATUS_CHANGE

We expected values like:

1. Strategy Call Scheduled

Instead we found:

published
draft
Conclusion

STATUS_CHANGE is not the business outcome.

It is simply the CRM record status.

3. Validate Triage Call records

We inspected only:

CUSTOM_ACTIVITY='3) Triage Call'

We found:

STATUS_CHANGE = published

TEXT = NULL

MEETING_STATUS = NULL

There was no business information telling us whether:

Strategy Call Scheduled
No Show
Cancel

etc.

First suspicion

At this point we asked:

Are we missing business data?

Step 2 — Validate the funnel

Next we checked the lead journey.

We queried:

Triage

↓

Strategy

↓

Sale

ordered by

LEAD_ID

ACTIVITY_AT

Purpose:

Verify that the business hierarchy matches the SME document.

It did.

Then we checked:
CUSTOM_ACTIVITY_OUTCOME_NAME

Result:

Everything was

NULL

Same for

CUSTOM_ACTIVITY_OUTCOME
First Root Cause

We concluded:

The summary table has outcome columns,

but

they are never populated.

Step 3 — Validate Bronze

Instead of immediately modifying Silver, we wanted to prove where the missing data originated.

We inspected

LEAD_ACTIVITIES_RAW
Search for
custom.

Result

We discovered many fields like

custom.cf_xxxxxxxxx

This was our first breakthrough.

The raw data contained dynamic custom fields.

Exactly what the SME document described.

Step 4 — Validate metadata

Next we inspected

CUSTOM_ACTIVITIES_RAW

Purpose:

Find out what

cf_xxxxx

actually means.

We discovered:

Each activity definition contains

fields

For example

Strategy Call Outcome

Offer Presented

Contract Value

Cash Collected

Setter

Closer

Objections Faced

This confirmed that the metadata exists.

Second Root Cause

We concluded:

The metadata exists.

The activity values exist.

Our Silver pipeline never joins them together.

Step 5 — Find the correct JSON path

At this point we made a mistake.

Initially we assumed:

raw_data

↓

data

↓

activities

We wrote

FLATTEN(...activities)

Everything returned

0 rows

Instead of forcing it, we debugged.

We inspected
OBJECT_KEYS()

We checked

TYPEOF()

We validated

raw_data

data

We discovered

raw_data

↓

data

already contains

one activity

per row.

There is

NO

activities

array.

Third Root Cause

The flatten path was wrong.

Correct path:

raw_data

↓

data

↓

activity

There is only

one

FLATTEN required.

Step 6 — Find the correct activity type

We also discovered

we were filtering using

type

The actual field is

_type

Another reason our queries returned

0 rows
Step 7 — Extract dynamic custom fields

Once the path was corrected we extracted

custom.cf_xxxxx

directly from Bronze.

We successfully extracted:

Triage Call Outcome

Strategy Call Outcome

Offer Presented

Contract Value

Cash Collected

Setter

Closer

Program

Objections Faced

This proved

The business data has existed since Bronze all along.

Step 8 — Decide where to fix it

Initially I suggested

adding

CUSTOM_ACTIVITY_FIELDS

Then we reviewed the SME architecture again.

You correctly said:

I don't want to change the SME model.

We agreed.

Instead of changing the model,

we enhanced

LEADS_ACTIVITIES_SUMMARY

which already contains

CUSTOM_ACTIVITY_OUTCOME_NAME

CUSTOM_ACTIVITY_OUTCOME

Exactly as the SME intended.

Step 9 — Rebuild Summary

Instead of

CUSTOM_ACTIVITY_OUTCOME

↓

Outcome ID

we now populate it from the

dynamic custom fields.

Final validation

After rebuilding

we finally obtained:

Triage
1. Strategy Call Scheduled

6. No Show

7. Reschedule

...

Strategy
1. Follow Up

6. Sale

7. Lost

4. No Show

...


Exactly matching the SME business rules.

Final Root Cause

The problem was not:

Bronze
AWS Glue
PostgreSQL
JSON repair
CDC
MERGE
Deduplication

The real issue was:

The Silver transformation was extracting only the standard activity fields and not the dynamic custom.cf_* business fields that contain the CRM outcomes.

Once those fields were extracted and mapped into LEADS_ACTIVITIES_SUMMARY, the business outcomes became available and the Silver layer aligned with the SME requirements.

What we learned

This debugging session followed a structured data engineering approach:

Validate the business layer (Gold) before implementing KPIs.
Verify the Silver layer to ensure required business attributes exist.
Trace missing attributes back to Bronze instead of making assumptions.
Inspect the raw JSON structure to find the correct hierarchy and flatten path.
Identify dynamic custom fields (custom.cf_*) as the source of business outcomes.
Enhance the existing Silver transformation rather than changing the SME architecture.
Revalidate until the extracted outcomes matched the documented business process.

```
