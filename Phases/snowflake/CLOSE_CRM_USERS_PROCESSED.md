# Create Table

```
CREATE OR REPLACE TABLE SILVER.CLOSE_CRM_USERS_PROCESSED (
    USER_ID STRING,
    EMAIL STRING,
    FIRST_NAME STRING,
    LAST_NAME STRING,
    MD5_HASH STRING,
    DATE_CREATED TIMESTAMP_NTZ,
    DATE_UPDATED TIMESTAMP_NTZ,
    INSERT_DATE TIMESTAMP_NTZ,
    UPDATE_DATE TIMESTAMP_NTZ
);

```

# Explore Objects before Merge

```
SELECT
    JSON_OBJECT,
    OBJECT_KEYS(JSON_OBJECT),
    JSON_OBJECT:raw_data,
    OBJECT_KEYS(JSON_OBJECT:raw_data)
FROM BRONZE.CLOSE_CRM_USERS_RAW
LIMIT 5;

Then run:

SELECT COUNT(*)
FROM BRONZE.CLOSE_CRM_USERS_RAW r,
LATERAL FLATTEN(INPUT => r.JSON_OBJECT:raw_data:data) user_obj;

If count is 0, try:

SELECT COUNT(*)
FROM BRONZE.CLOSE_CRM_USERS_RAW r,
LATERAL FLATTEN(INPUT => r.JSON_OBJECT:data) user_obj;

```


```

For CLOSE_CRM_USERS_RAW, the real path is different:

JSON_OBJECT
  ↓
raw_data
  ↓
JSON_OBJECT  ← stringified JSON
  ↓
data[]

So this table does need parsing.

```


# Checking SOurce Pattern

```

Use this source pattern:

TRY_PARSE_JSON(JSON_OBJECT:raw_data:JSON_OBJECT::STRING):data

But because the inner value may contain single quotes, use this safer test first:

SELECT
    TRY_PARSE_JSON(
        REPLACE(JSON_OBJECT:raw_data:JSON_OBJECT::STRING, '''', '"')
    ) AS parsed_json
FROM BRONZE.CLOSE_CRM_USERS_RAW
LIMIT 5;

Then count:

SELECT COUNT(*)
FROM BRONZE.CLOSE_CRM_USERS_RAW r,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        REPLACE(r.JSON_OBJECT:raw_data:JSON_OBJECT::STRING, '''', '"')
    ):data
) user_obj;

now after finding now do merge

```

# Merge

```
MERGE INTO SILVER.CLOSE_CRM_USERS_PROCESSED tgt
USING (
    WITH flattened AS (
        SELECT
            user_obj.value:id::STRING AS USER_ID,
            user_obj.value:email::STRING AS EMAIL,
            user_obj.value:first_name::STRING AS FIRST_NAME,
            user_obj.value:last_name::STRING AS LAST_NAME,
            user_obj.value:date_created::TIMESTAMP_NTZ AS DATE_CREATED,
            user_obj.value:date_updated::TIMESTAMP_NTZ AS DATE_UPDATED,
            r.JSON_OBJECT:insert_date::TIMESTAMP_NTZ AS INSERT_DATE
        FROM BRONZE.CLOSE_CRM_USERS_RAW r,
        LATERAL FLATTEN(
            INPUT => TRY_PARSE_JSON(
                REPLACE(r.JSON_OBJECT:raw_data:JSON_OBJECT::STRING, '''', '"')
            ):data
        ) user_obj
    ),
    with_hash AS (
        SELECT *,
            MD5(
                COALESCE(USER_ID, '') || '|' ||
                COALESCE(EMAIL, '') || '|' ||
                COALESCE(FIRST_NAME, '') || '|' ||
                COALESCE(LAST_NAME, '') || '|' ||
                COALESCE(DATE_UPDATED::STRING, '')
            ) AS MD5_HASH
        FROM flattened
    ),
    deduped AS (
        SELECT *
        FROM with_hash
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY USER_ID
            ORDER BY DATE_UPDATED DESC, INSERT_DATE DESC
        ) = 1
    )
    SELECT * FROM deduped
) src
ON tgt.USER_ID = src.USER_ID
WHEN MATCHED AND tgt.MD5_HASH <> src.MD5_HASH THEN UPDATE SET
    tgt.EMAIL = src.EMAIL,
    tgt.FIRST_NAME = src.FIRST_NAME,
    tgt.LAST_NAME = src.LAST_NAME,
    tgt.DATE_CREATED = src.DATE_CREATED,
    tgt.DATE_UPDATED = src.DATE_UPDATED,
    tgt.UPDATE_DATE = CURRENT_TIMESTAMP(),
    tgt.MD5_HASH = src.MD5_HASH
WHEN NOT MATCHED THEN INSERT (
    USER_ID, EMAIL, FIRST_NAME, LAST_NAME, MD5_HASH,
    DATE_CREATED, DATE_UPDATED, INSERT_DATE, UPDATE_DATE
)
VALUES (
    src.USER_ID, src.EMAIL, src.FIRST_NAME, src.LAST_NAME, src.MD5_HASH,
    src.DATE_CREATED, src.DATE_UPDATED, src.INSERT_DATE, CURRENT_TIMESTAMP()
);

```


# validate

```
SELECT COUNT(*) FROM SILVER.CLOSE_CRM_USERS_PROCESSED;

SELECT USER_ID, COUNT(*) AS CNT
FROM SILVER.CLOSE_CRM_USERS_PROCESSED
GROUP BY USER_ID
HAVING COUNT(*) > 1;

SELECT *
FROM SILVER.CLOSE_CRM_USERS_PROCESSED
LIMIT 20;

```

# Results

```

Validation:

CLOSE_CRM_USERS_PROCESSED count: 100
Duplicate USER_ID check: 0 rows

This means:

8,600 raw flattened user records
        ↓
deduplicated by USER_ID
        ↓
100 clean CRM users

Now completed Silver tables:

LEAD_ACTIVITIES_PROCESSED_TRANSIENT
LEAD_ACTIVITIES_PROCESSED
LEADS_ACTIVITIES_SUMMARY_TRANSIENT
 LEAD_ACTIVITIES_EMAIL
CLOSE_CRM_USERS_PROCESSED

```
