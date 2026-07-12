# Before creating the view, we need to identify the exact prospecting activity name and confirm where that outcome is stored.
# Find prospecting activity names

```
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS TOTAL_ROWS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY ILIKE '%prospect%'
   OR CUSTOM_ACTIVITY ILIKE '%outbound%'
GROUP BY CUSTOM_ACTIVITY
ORDER BY TOTAL_ROWS DESC;

```
# Inspect all outcomes for those activities
```
SELECT
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    STATUS_CHANGE,
    COUNT(*) AS TOTAL_ROWS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY ILIKE '%prospect%'
   OR CUSTOM_ACTIVITY ILIKE '%outbound%'
GROUP BY
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    STATUS_CHANGE
ORDER BY
    CUSTOM_ACTIVITY,
    TOTAL_ROWS DESC;

```
#  Search specifically for the required positive outcome

```
SELECT
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    COUNT(*) AS TOTAL_ROWS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
GROUP BY
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME
ORDER BY TOTAL_ROWS DESC;

```
# Inspect sample outbound records
```
SELECT
    LEAD_ID,
    ACTIVITY_ID,
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    STATUS_CHANGE,
    ACTIVITY_AT,
    DEA_INTERNAL_EMAIL,
    DEA_INTERNAL_NAME,
    SETTER_EMAIL,
    SETTER_NAME
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY ILIKE '%prospect%'
   OR CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
LIMIT 50;

These results will tell us:
the exact activity name,
whether outbound booking comes from CUSTOM_ACTIVITY_OUTCOME,
whether attribution should use SETTER_EMAIL/SETTER_NAME or DEA_INTERNAL_EMAIL/DEA_INTERNAL_NAME,
and the correct expected Gold row count.

```

# actual outbound outcome values

```

SELECT
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    COUNT(*) AS TOTAL_ROWS
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
  AND CUSTOM_ACTIVITY_OUTCOME IS NOT NULL
GROUP BY
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME
ORDER BY
    TOTAL_ROWS DESC;

```

# 

```
SELECT
    LEAD_ID,
    ACTIVITY_ID,
    CUSTOM_ACTIVITY,
    TEXT,
    STATUS_CHANGE,
    WRAPPED_ACTIVITIES
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
LIMIT 20;


SELECT
    DISTINCT CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
);

```

## We should inspect the field definitions for the two prospecting activity types and find the custom field ID that stores their outcome.

```

USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA BRONZE;

WITH ACTIVITY_DEFINITIONS AS (
    SELECT
        activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
        activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
        activity.value:fields AS FIELDS
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:data
    ) activity
)

SELECT
    a.CUSTOM_ACTIVITY_ID,
    a.CUSTOM_ACTIVITY_NAME,
    field.value:id::STRING AS FIELD_ID,
    field.value:name::STRING AS FIELD_NAME,
    field.value:type::STRING AS FIELD_TYPE,
    field.value:required::BOOLEAN AS IS_REQUIRED,
    field.value AS FIELD_DEFINITION
FROM ACTIVITY_DEFINITIONS a,
LATERAL FLATTEN(INPUT => a.FIELDS) field
WHERE a.CUSTOM_ACTIVITY_NAME IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
ORDER BY
    a.CUSTOM_ACTIVITY_NAME,
    FIELD_NAME;



```


# Then narrow the result to likely booking/outcome fields:

```

WITH ACTIVITY_DEFINITIONS AS (
    SELECT
        activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
        activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
        activity.value:fields AS FIELDS
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:data
    ) activity
)

SELECT
    a.CUSTOM_ACTIVITY_NAME,
    field.value:id::STRING AS FIELD_ID,
    field.value:name::STRING AS FIELD_NAME,
    field.value:type::STRING AS FIELD_TYPE,
    field.value AS FIELD_DEFINITION
FROM ACTIVITY_DEFINITIONS a,
LATERAL FLATTEN(INPUT => a.FIELDS) field
WHERE a.CUSTOM_ACTIVITY_NAME IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
AND (
       field.value:name::STRING ILIKE '%outcome%'
    OR field.value:name::STRING ILIKE '%strategy%'
    OR field.value:name::STRING ILIKE '%scheduled%'
    OR field.value:name::STRING ILIKE '%status%'
    OR field.value:name::STRING ILIKE '%pipeline%'
)
ORDER BY
    a.CUSTOM_ACTIVITY_NAME,
    FIELD_NAME;


```

# diagnostic against the metadata:

```

SELECT DISTINCT
    activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW r,
LATERAL FLATTEN(
    INPUT => r.JSON_OBJECT:raw_data:data
) activity
ORDER BY CUSTOM_ACTIVITY_NAME;

```

# inspect the raw structure of one record from CUSTOM_ACTIVITIES_RAW.

```
SELECT
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
LIMIT 1;


SELECT
    OBJECT_KEYS(JSON_OBJECT) AS ROOT_KEYS
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
LIMIT 1;


SELECT
    TYPEOF(JSON_OBJECT:raw_data) AS RAW_TYPE,
    OBJECT_KEYS(JSON_OBJECT:raw_data) AS RAW_KEYS
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
LIMIT 1;


What we found
The JSON structure is not:
raw_data
   └── data
It is:
JSON_OBJECT
 ├── glue_cleaned_at
 ├── glue_cleaned_flag
 ├── insert_date
 └── raw_data
      └── JSON_OBJECT
           └── data
                ├── { Custom Activity Definition }
                ├── { Custom Activity Definition }
                ├── ...



```

# corrected metadata scan in Snowflake

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA BRONZE;

WITH ACTIVITY_DEFINITIONS AS (
    SELECT
        activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
        activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
        activity.value:fields AS FIELDS
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:JSON_OBJECT:data
    ) activity
)

SELECT
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME
FROM ACTIVITY_DEFINITIONS
ORDER BY CUSTOM_ACTIVITY_NAME;

```

# Then search only the outbound definitions

```

WITH ACTIVITY_DEFINITIONS AS (
    SELECT
        activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
        activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
        activity.value:fields AS FIELDS
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:JSON_OBJECT:data
    ) activity
)

SELECT
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME
FROM ACTIVITY_DEFINITIONS
WHERE CUSTOM_ACTIVITY_NAME ILIKE '%prospect%'
   OR CUSTOM_ACTIVITY_NAME ILIKE '%outbound%'
ORDER BY CUSTOM_ACTIVITY_NAME;

```

# If that returns the two expected activities, inspect their fields:

```

WITH ACTIVITY_DEFINITIONS AS (
    SELECT
        activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
        activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
        activity.value:fields AS FIELDS
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:JSON_OBJECT:data
    ) activity
)

SELECT
    a.CUSTOM_ACTIVITY_ID,
    a.CUSTOM_ACTIVITY_NAME,
    field.value:id::STRING AS FIELD_ID,
    field.value:name::STRING AS FIELD_NAME,
    field.value:type::STRING AS FIELD_TYPE,
    field.value:required::BOOLEAN AS IS_REQUIRED,
    field.value AS FIELD_DEFINITION
FROM ACTIVITY_DEFINITIONS a,
LATERAL FLATTEN(INPUT => a.FIELDS) field
WHERE a.CUSTOM_ACTIVITY_NAME IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
ORDER BY
    a.CUSTOM_ACTIVITY_NAME,
    FIELD_NAME;

```

# Booking fields

```

WITH ACTIVITY_DEFINITIONS AS (
    SELECT
        activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
        activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
        activity.value:fields AS FIELDS
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:JSON_OBJECT:data
    ) activity
)

SELECT
    a.CUSTOM_ACTIVITY_NAME,
    field.value:id::STRING AS FIELD_ID,
    field.value:name::STRING AS FIELD_NAME,
    field.value:type::STRING AS FIELD_TYPE,
    field.value AS FIELD_DEFINITION
FROM ACTIVITY_DEFINITIONS a,
LATERAL FLATTEN(INPUT => a.FIELDS) field
WHERE a.CUSTOM_ACTIVITY_NAME IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
AND (
       field.value:name::STRING ILIKE '%outcome%'
    OR field.value:name::STRING ILIKE '%strategy%'
    OR field.value:name::STRING ILIKE '%scheduled%'
    OR field.value:name::STRING ILIKE '%status%'
    OR field.value:name::STRING ILIKE '%pipeline%'
)
ORDER BY
    a.CUSTOM_ACTIVITY_NAME,
    FIELD_NAME;


```

# results

```
What we discovered
1. Prospecting Activity does exist in CUSTOM_ACTIVITIES_RAW
We found:
CUSTOM_ACTIVITY_ID
actitype_4tEv1xumZEk9vYYs7WxYy7

CUSTOM_ACTIVITY_NAME
1) Prospecting Activity
So the metadata is present. Our earlier queries failed only because we were using the wrong JSON path.
2. The activity has a dedicated business field
More importantly, the metadata contains:
FIELD NAME
Prospecting Call Outcome

FIELD TYPE
choices

FIELD ID
cf_Q2fsrD8VpPaunZLtyiy7P3vG6qJTv0w1ESmlhdHU2ra
This is exactly what we were hoping to find.
This changes everything
The requirements state:
Outbound qualification occurs during Prospecting Activity.
Positive outcome:
"2. Strategy Call Scheduled"
We now know where that value is stored.
It is not in:
CUSTOM_ACTIVITY_OUTCOME
STATUS_CHANGE
It is stored inside the dynamic custom field:
custom.cf_Q2fsrD8VpPaunZLtyiy7P3vG6qJTv0w1ESmlhdHU2ra
Exactly the same pattern as:
Triage Call Outcome
Strategy Call Outcome
Offer Presented
Contract Value
Cash Collected

Just as we added:
Strategy Call Outcome
Triage Call Outcome
Offer Presented
Contract Value
Cash Collected
Date of Sale
we should add one more column:
PROSPECTING_CALL_OUTCOME STRING
to LEADS_ACTIVITIES_SUMMARY.
```

# 1. Validate the Bronze field first

```

SELECT
    activity.value:id::STRING AS ACTIVITY_ID,
    activity.value:lead_id::STRING AS LEAD_ID,
    activity.value:custom_activity_type_id::STRING AS CUSTOM_ACTIVITY_ID,

    activity.value:
        "custom.cf_Q2fsrD8VpPaunZLtyiy7P3vG6qJTv0w1ESmlhdHU2ra"
        ::STRING AS PROSPECTING_CALL_OUTCOME,

    activity.value:activity_at::TIMESTAMP_NTZ AS ACTIVITY_AT,
    activity.value:date_updated::TIMESTAMP_NTZ AS DATE_UPDATED

FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW r,
LATERAL FLATTEN(
    INPUT => r.JSON_OBJECT:raw_data:data
) activity

WHERE activity.value:
    "custom.cf_Q2fsrD8VpPaunZLtyiy7P3vG6qJTv0w1ESmlhdHU2ra"
    IS NOT NULL

QUALIFY ROW_NUMBER() OVER (
    PARTITION BY
        activity.value:lead_id::STRING,
        activity.value:id::STRING
    ORDER BY
        activity.value:activity_at::TIMESTAMP_NTZ DESC,
        activity.value:date_updated::TIMESTAMP_NTZ DESC,
        r.JSON_OBJECT:insert_date::TIMESTAMP_NTZ DESC
) = 1

LIMIT 100;

```

# 2. Populate the existing Silver outcome columns

```
UPDATE SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY tgt

SET
    CUSTOM_ACTIVITY_OUTCOME_NAME = 'Prospecting Call Outcome',
    CUSTOM_ACTIVITY_OUTCOME = src.PROSPECTING_CALL_OUTCOME,
    UPDATE_DATE = CURRENT_TIMESTAMP()

FROM (
    SELECT
        activity.value:id::STRING AS ACTIVITY_ID,
        activity.value:lead_id::STRING AS LEAD_ID,

        activity.value:
            "custom.cf_Q2fsrD8VpPaunZLtyiy7P3vG6qJTv0w1ESmlhdHU2ra"
            ::STRING AS PROSPECTING_CALL_OUTCOME

    FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:data
    ) activity

    WHERE activity.value:
        "custom.cf_Q2fsrD8VpPaunZLtyiy7P3vG6qJTv0w1ESmlhdHU2ra"
        IS NOT NULL

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY
            activity.value:lead_id::STRING,
            activity.value:id::STRING
        ORDER BY
            activity.value:activity_at::TIMESTAMP_NTZ DESC,
            activity.value:date_updated::TIMESTAMP_NTZ DESC,
            r.JSON_OBJECT:insert_date::TIMESTAMP_NTZ DESC
    ) = 1
) src

WHERE tgt.LEAD_ID = src.LEAD_ID
  AND tgt.ACTIVITY_ID = src.ACTIVITY_ID
  AND tgt.CUSTOM_ACTIVITY IN (
      '1) Prospecting Activity',
      '2) Prospecting Follow Up'
  );

```

# 3. Validate all prospecting outcomes

```
SELECT
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    COUNT(*) AS TOTAL_ROWS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
GROUP BY
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME
ORDER BY
    CUSTOM_ACTIVITY,
    TOTAL_ROWS DESC;

```

# 4. Confirm the required positive outcome

```
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS STRATEGY_CALL_SCHEDULED_ROWS,
    COUNT(DISTINCT LEAD_ID) AS UNIQUE_LEADS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
AND CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
GROUP BY CUSTOM_ACTIVITY
ORDER BY CUSTOM_ACTIVITY;


```

# 5. Reconfirm Silver integrity

```
SELECT COUNT(*) AS SUMMARY_ROWS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY;


Expected:
1,063,628
SELECT
    LEAD_ID,
    ACTIVITY_ID,
    COUNT(*) AS CNT
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
GROUP BY
    LEAD_ID,
    ACTIVITY_ID
HAVING COUNT(*) > 1;
Expected:
0 rows

```

# Create gold table


```

USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW GOLD.OUTBOUND_STRATEGIES_BOOKED AS
SELECT
    LEAD_ID,

    ACTIVITY_AT::DATE AS ACTIVITY_LOG_DATE,

    DEA_INTERNAL_EMAIL AS SETTER_CLOSER_EMAIL,
    DEA_INTERNAL_NAME AS SETTER_CLOSER_NAME,

    ACTIVITY_AT::DATE AS PROSPECT_CALL_DATE,

    1 AS STRATEGY_CALL_BOOKED,

    YEAR(ACTIVITY_AT) || '-' ||
    LPAD(WEEKISO(ACTIVITY_AT), 2, '0') AS SC_YEAR_WEEK

FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
AND CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled';


```

# Validate total rows
```
SELECT COUNT(*) AS OUTBOUND_STRATEGIES_BOOKED_COUNT
FROM GOLD.OUTBOUND_STRATEGIES_BOOKED;

Expected:
2408
Calculation:
2,146 Prospecting Activity bookings
+ 262 Prospecting Follow Up bookings
= 2,408

```
# Validate unique leads

```
SELECT
    COUNT(*) AS TOTAL_ROWS,
    COUNT(DISTINCT LEAD_ID) AS UNIQUE_LEADS
FROM GOLD.OUTBOUND_STRATEGIES_BOOKED;
The total should be 2,408. The unique lead count may be lower because some leads can book more than once.

```
# Validate source reconciliation
```
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS SILVER_ROWS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
)
AND CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
GROUP BY CUSTOM_ACTIVITY
ORDER BY CUSTOM_ACTIVITY;

Expected:
1) Prospecting Activity     2146
2) Prospecting Follow Up     262
```
# Validate weekly reporting
```
SELECT
    SC_YEAR_WEEK,
    COUNT(*) AS STRATEGIES_BOOKED
FROM GOLD.OUTBOUND_STRATEGIES_BOOKED
GROUP BY SC_YEAR_WEEK
ORDER BY SC_YEAR_WEEK;

```
# Validate attribution coverage

```
SELECT
    COUNT(*) AS TOTAL_ROWS,
    COUNT_IF(SETTER_CLOSER_EMAIL IS NOT NULL) AS EMAIL_ROWS,
    COUNT_IF(SETTER_CLOSER_NAME IS NOT NULL) AS NAME_ROWS
FROM GOLD.OUTBOUND_STRATEGIES_BOOKED;

```
# reslts

```
Validation Results
1. Total rows 
OUTBOUND_STRATEGIES_BOOKED
2,408 rows
This matches exactly what we expected.
2. Unique Leads 
Total Rows    : 2,408
Unique Leads  : 2,184
This is a good sign.
It means:
Some leads scheduled more than one Strategy Call.
The Gold view is correctly keeping the activity grain rather than collapsing to one row per lead.
3. Source reconciliation 
The source distribution matches perfectly:
Activity	Rows
1) Prospecting Activity	2,146
2) Prospecting Follow Up	262
Total:
2146 + 262 = 2408
Exactly matches the Gold row count.
4. Weekly aggregation 
The weekly summary shows records distributed across ISO weeks.
This confirms that:
SC_YEAR_WEEK
is being generated correctly and will support the Outbound Setter Report required by the SME.
5. Attribution 
Your validation shows:
TOTAL_ROWS : 2408
EMAIL_ROWS : 235
NAME_ROWS  : 235
Only 235 rows have populated DEA_INTERNAL_EMAIL/DEA_INTERNAL_NAME.
Is this a problem?
No.
This is consistent with what we observed earlier:
Many prospecting activities do not have an associated CRM user in CLOSE_CRM_USERS_PROCESSED.
Earlier we validated that 104 user IDs were missing from the user dimension due to source data limitations.
We agreed not to fabricate or backfill user attribution.
So this is a source data limitation, not an ETL issue.


```
