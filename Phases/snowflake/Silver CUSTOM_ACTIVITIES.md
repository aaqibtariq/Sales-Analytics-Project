# Create table

```

CREATE OR REPLACE TABLE SILVER.CUSTOM_ACTIVITIES (
    CUSTOM_ACTIVITY_ID STRING,
    CUSTOM_ACTIVITY_NAME STRING,
    CUSTOM_ACTIVITY_OUTCOME_ID STRING,
    CUSTOM_ACTIVITY_OUTCOME_NAME STRING,
    MD5_HASH STRING,
    INSERT_DATE TIMESTAMP_NTZ,
    UPDATE_DATE TIMESTAMP_NTZ
);

```

# load data

```

INSERT INTO SILVER.CUSTOM_ACTIVITIES
(
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME,
    CUSTOM_ACTIVITY_OUTCOME_ID,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5_HASH,
    INSERT_DATE,
    UPDATE_DATE
)
SELECT
    activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
    activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
    outcome.value:id::STRING AS CUSTOM_ACTIVITY_OUTCOME_ID,
    outcome.value:name::STRING AS CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5(
        COALESCE(activity.value:id::STRING, '') || '|' ||
        COALESCE(activity.value:name::STRING, '') || '|' ||
        COALESCE(outcome.value:id::STRING, '') || '|' ||
        COALESCE(outcome.value:name::STRING, '')
    ) AS MD5_HASH,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(INPUT => t.JSON_OBJECT:raw_data:JSON_OBJECT:data) activity,
LATERAL FLATTEN(INPUT => activity.value:outcomes, OUTER => TRUE) outcome;

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES;

INSERT INTO SILVER.CUSTOM_ACTIVITIES
(
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME,
    CUSTOM_ACTIVITY_OUTCOME_ID,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5_HASH,
    INSERT_DATE,
    UPDATE_DATE
)
SELECT
    activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
    activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
    outcome.value:id::STRING AS CUSTOM_ACTIVITY_OUTCOME_ID,
    outcome.value:name::STRING AS CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5(
        COALESCE(activity.value:id::STRING, '') || '|' ||
        COALESCE(activity.value:name::STRING, '') || '|' ||
        COALESCE(outcome.value:id::STRING, '') || '|' ||
        COALESCE(outcome.value:name::STRING, '')
    ) AS MD5_HASH,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(INPUT => t.JSON_OBJECT:raw_data:JSON_OBJECT:data) activity,
LATERAL FLATTEN(INPUT => activity.value:outcomes, OUTER => TRUE) outcome;

```

# Validate 

```
SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES;

SELECT *
FROM SILVER.CUSTOM_ACTIVITIES
LIMIT 20;

```


```

Current status
Bronze
18 rows loaded
JSON_OBJECT repaired by Glue
 JSON can be traversed in Snowflake
Silver Transient
 Loaded successfully
Silver CUSTOM_ACTIVITIES
Loaded successfully
 450 rows inserted

The CSV you uploaded has exactly the columns required by your SME:

Column	Status
CUSTOM_ACTIVITY_ID	
CUSTOM_ACTIVITY_NAME	
CUSTOM_ACTIVITY_OUTCOME_ID	
CUSTOM_ACTIVITY_OUTCOME_NAME	
MD5_HASH	
INSERT_DATE	
UPDATE_DATE

The count of 450 rows 

we have
18 activity types in Bronze.
450 rows in CUSTOM_ACTIVITIES.

That averages to 25 outcomes per activity type, which seems unusually high.

Before we continue, let's verify that we're not accidentally flattening the wrong array.



```

# testing again

```
SELECT
    COUNT(*) AS TOTAL_ACTIVITY_TYPES
FROM TABLE(
    FLATTEN(
        INPUT => (
            SELECT JSON_OBJECT:raw_data:JSON_OBJECT:data
            FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
            LIMIT 1
        )
    )
);

and

SELECT
    CUSTOM_ACTIVITY_NAME,
    COUNT(*) AS OUTCOME_COUNT
FROM SILVER.CUSTOM_ACTIVITIES
GROUP BY CUSTOM_ACTIVITY_NAME
ORDER BY OUTCOME_COUNT DESC;

```


# new load 

```

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES;

INSERT INTO SILVER.CUSTOM_ACTIVITIES
(
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME,
    CUSTOM_ACTIVITY_OUTCOME_ID,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5_HASH,
    INSERT_DATE,
    UPDATE_DATE
)
WITH LATEST_SNAPSHOT AS (
    SELECT JSON_OBJECT, INSERT_DATE
    FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
    QUALIFY ROW_NUMBER() OVER (
        ORDER BY JSON_OBJECT:raw_data:INSERT_DATE::TIMESTAMP_NTZ DESC
    ) = 1
)
SELECT
    activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
    activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
    outcome.value:id::STRING AS CUSTOM_ACTIVITY_OUTCOME_ID,
    outcome.value:name::STRING AS CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5(
        COALESCE(activity.value:id::STRING, '') || '|' ||
        COALESCE(activity.value:name::STRING, '') || '|' ||
        COALESCE(outcome.value:id::STRING, '') || '|' ||
        COALESCE(outcome.value:name::STRING, '')
    ) AS MD5_HASH,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
FROM LATEST_SNAPSHOT t,
LATERAL FLATTEN(INPUT => t.JSON_OBJECT:raw_data:JSON_OBJECT:data) activity,
LATERAL FLATTEN(INPUT => activity.value:outcomes, OUTER => TRUE) outcome;

```

# validate 

```
SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES;


Final SILVER.CUSTOM_ACTIVITIES
25 rows
 7 columns
 One row per custom activity
 No duplicate snapshots
Matches the SME data model

Columns:

CUSTOM_ACTIVITY_ID
CUSTOM_ACTIVITY_NAME
CUSTOM_ACTIVITY_OUTCOME_ID
CUSTOM_ACTIVITY_OUTCOME_NAME
MD5_HASH
INSERT_DATE
UPDATE_DATE



```
