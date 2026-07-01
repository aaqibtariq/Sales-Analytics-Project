# Creation of first table LEAD_ACTIVITIES_PROCESSED

```

USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE LEAD_ACTIVITIES_PROCESSED (
    ACTIVITY_ID STRING,
    LEAD_ID STRING,
    CONTACT_ID STRING,
    USER_ID STRING,
    TYPE STRING,
    TEXT STRING,
    STATUS_CHANGE STRING,
    CREATED_BY_NAME STRING,
    UPDATED_BY_NAME STRING,
    ATTENDEES VARIANT,
    CUSTOM_ACTIVITY_ID STRING,
    MEETING_STARTS_AT TIMESTAMP_NTZ,
    MEETING_END_AT TIMESTAMP_NTZ,
    MEETING_STATUS STRING,
    ACTIVITY_AT TIMESTAMP_NTZ,
    DATE_CREATED TIMESTAMP_NTZ,
    DATE_UPDATED TIMESTAMP_NTZ,
    CREATED_BY_USER STRING,
    UPDATED_BY_USER STRING,
    INSERT_DATE TIMESTAMP_NTZ,
    UPDATE_DATE TIMESTAMP_NTZ,
    MD5_HASH STRING
);

```

## merge

```

MERGE INTO SILVER.LEAD_ACTIVITIES_PROCESSED tgt
USING (
    WITH flattened AS (
        SELECT
            activity.value:id::STRING AS ACTIVITY_ID,
            activity.value:lead_id::STRING AS LEAD_ID,
            activity.value:contact_id::STRING AS CONTACT_ID,
            activity.value:user_id::STRING AS USER_ID,
            activity.value:_type::STRING AS TYPE,
            activity.value:text::STRING AS TEXT,
            activity.value:status::STRING AS STATUS_CHANGE,
            activity.value:created_by_name::STRING AS CREATED_BY_NAME,
            activity.value:updated_by_name::STRING AS UPDATED_BY_NAME,
            activity.value:attendees AS ATTENDEES,
            activity.value:custom_activity_type_id::STRING AS CUSTOM_ACTIVITY_ID,
            activity.value:meeting_starts_at::TIMESTAMP_NTZ AS MEETING_STARTS_AT,
            activity.value:meeting_ends_at::TIMESTAMP_NTZ AS MEETING_END_AT,
            activity.value:meeting_status::STRING AS MEETING_STATUS,
            activity.value:activity_at::TIMESTAMP_NTZ AS ACTIVITY_AT,
            activity.value:date_created::TIMESTAMP_NTZ AS DATE_CREATED,
            activity.value:date_updated::TIMESTAMP_NTZ AS DATE_UPDATED,
            activity.value:created_by::STRING AS CREATED_BY_USER,
            activity.value:updated_by::STRING AS UPDATED_BY_USER,
            r.JSON_OBJECT:insert_date::TIMESTAMP_NTZ AS INSERT_DATE
        FROM BRONZE.LEAD_ACTIVITIES_RAW r,
        LATERAL FLATTEN(INPUT => r.JSON_OBJECT:raw_data:data) activity
    ),

    with_hash AS (
        SELECT
            *,
            MD5(
                COALESCE(ACTIVITY_ID, '') || '|' ||
                COALESCE(LEAD_ID, '') || '|' ||
                COALESCE(CONTACT_ID, '') || '|' ||
                COALESCE(USER_ID, '') || '|' ||
                COALESCE(TYPE, '') || '|' ||
                COALESCE(TEXT, '') || '|' ||
                COALESCE(STATUS_CHANGE, '') || '|' ||
                COALESCE(CUSTOM_ACTIVITY_ID, '') || '|' ||
                COALESCE(ACTIVITY_AT::STRING, '') || '|' ||
                COALESCE(DATE_UPDATED::STRING, '')
            ) AS MD5_HASH
        FROM flattened
    ),

    deduped AS (
        SELECT *
        FROM with_hash
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY LEAD_ID, ACTIVITY_ID
            ORDER BY ACTIVITY_AT DESC, DATE_UPDATED DESC, INSERT_DATE DESC
        ) = 1
    )

    SELECT * FROM deduped
) src
ON tgt.LEAD_ID = src.LEAD_ID
AND tgt.ACTIVITY_ID = src.ACTIVITY_ID

WHEN MATCHED AND tgt.MD5_HASH <> src.MD5_HASH THEN UPDATE SET
    tgt.CONTACT_ID = src.CONTACT_ID,
    tgt.USER_ID = src.USER_ID,
    tgt.TYPE = src.TYPE,
    tgt.TEXT = src.TEXT,
    tgt.STATUS_CHANGE = src.STATUS_CHANGE,
    tgt.CREATED_BY_NAME = src.CREATED_BY_NAME,
    tgt.UPDATED_BY_NAME = src.UPDATED_BY_NAME,
    tgt.ATTENDEES = src.ATTENDEES,
    tgt.CUSTOM_ACTIVITY_ID = src.CUSTOM_ACTIVITY_ID,
    tgt.MEETING_STARTS_AT = src.MEETING_STARTS_AT,
    tgt.MEETING_END_AT = src.MEETING_END_AT,
    tgt.MEETING_STATUS = src.MEETING_STATUS,
    tgt.ACTIVITY_AT = src.ACTIVITY_AT,
    tgt.DATE_CREATED = src.DATE_CREATED,
    tgt.DATE_UPDATED = src.DATE_UPDATED,
    tgt.CREATED_BY_USER = src.CREATED_BY_USER,
    tgt.UPDATED_BY_USER = src.UPDATED_BY_USER,
    tgt.UPDATE_DATE = CURRENT_TIMESTAMP(),
    tgt.MD5_HASH = src.MD5_HASH

WHEN NOT MATCHED THEN INSERT (
    ACTIVITY_ID, LEAD_ID, CONTACT_ID, USER_ID, TYPE, TEXT,
    STATUS_CHANGE, CREATED_BY_NAME, UPDATED_BY_NAME, ATTENDEES,
    CUSTOM_ACTIVITY_ID, MEETING_STARTS_AT, MEETING_END_AT, MEETING_STATUS,
    ACTIVITY_AT, DATE_CREATED, DATE_UPDATED, CREATED_BY_USER, UPDATED_BY_USER,
    INSERT_DATE, UPDATE_DATE, MD5_HASH
)
VALUES (
    src.ACTIVITY_ID, src.LEAD_ID, src.CONTACT_ID, src.USER_ID, src.TYPE, src.TEXT,
    src.STATUS_CHANGE, src.CREATED_BY_NAME, src.UPDATED_BY_NAME, src.ATTENDEES,
    src.CUSTOM_ACTIVITY_ID, src.MEETING_STARTS_AT, src.MEETING_END_AT, src.MEETING_STATUS,
    src.ACTIVITY_AT, src.DATE_CREATED, src.DATE_UPDATED, src.CREATED_BY_USER, src.UPDATED_BY_USER,
    src.INSERT_DATE, CURRENT_TIMESTAMP(), src.MD5_HASH
);


```

# Validate 

```
SELECT COUNT(*) FROM SILVER.LEAD_ACTIVITIES_PROCESSED;

SELECT *
FROM SILVER.LEAD_ACTIVITIES_PROCESSED
LIMIT 20;

```

# Result

```
Bronze
LEAD_ACTIVITIES_RAW
379,946 rows
Silver
LEAD_ACTIVITIES_PROCESSED
1,063,628 rows

requirement says:

Each daily data refresh contains all lead activities for a lead, with new activities appended to the JSON.

So one Bronze row becomes many Silver rows after flattening.

That's exactly what LATERAL FLATTEN is supposed to do.

requirement also says:

Deduplicate using

lead_id + activity_id

Keep latest record using activity_at

```

# validate the deduplication

```
SELECT
    LEAD_ID,
    ACTIVITY_ID,
    COUNT(*) AS CNT
FROM SILVER.LEAD_ACTIVITIES_PROCESSED
GROUP BY
    LEAD_ID,
    ACTIVITY_ID
HAVING COUNT(*) > 1
LIMIT 20;

Expected result
0 rows

```

# Raw flattened
```

SELECT COUNT(*)
FROM BRONZE.LEAD_ACTIVITIES_RAW r,
LATERAL FLATTEN(INPUT => r.JSON_OBJECT:raw_data:data);

to check How many activity records exist after flattening.

```

# Distinct activities

```

SELECT COUNT(DISTINCT CONCAT(
    activity.value:lead_id::STRING,
    '|',
    activity.value:id::STRING
))
FROM BRONZE.LEAD_ACTIVITIES_RAW r,
LATERAL FLATTEN(INPUT => r.JSON_OBJECT:raw_data:data) activity;

to check How many unique (LEAD_ID, ACTIVITY_ID) pairs exist.

```

# FInal 

```

Validation results
Duplicate check in Silver: 0 rows 
Raw flattened rows: 7,247,395
Distinct lead_id + activity_id: 1,063,628
Silver processed rows: 1,063,628 

So the pipeline did exactly what we wanted:

7,247,395 raw activity records
        ↓
deduplicated by LEAD_ID + ACTIVITY_ID
        ↓
1,063,628 clean Silver activity records

This satisfies the key requirement:

Identify duplicates using lead_id + activity_id
Keep latest activity record using activity_at
Use MD5_HASH for CDC
Use MERGE for insert/update


```
