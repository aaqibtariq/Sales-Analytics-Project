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

# Notes

```
What happened?

Initially, we assumed that all Bronze tables had the same JSON structure because LEAD_ACTIVITIES_RAW worked with this path:

r.JSON_OBJECT:raw_data:data

So we reused the same logic for CLOSE_CRM_USERS_RAW.

Our original query was essentially:

FROM BRONZE.CLOSE_CRM_USERS_RAW r,
LATERAL FLATTEN(
    INPUT => r.JSON_OBJECT:raw_data:data
) user_obj

Result:

0 rows

The MERGE therefore showed:

Rows inserted: 0
Rows updated: 0
Why?

Because the JSON structure was different.

LEAD_ACTIVITIES_RAW

JSON_OBJECT
    │
    └── raw_data
            │
            └── data[]

But CLOSE_CRM_USERS_RAW was:

JSON_OBJECT
    │
    └── raw_data
            │
            └── JSON_OBJECT   ← String
                    │
                    └── data[]

Notice the extra layer:

JSON_OBJECT

inside raw_data.

So this path:

raw_data:data

didn't exist.

How did we debug it?

Instead of guessing, we inspected the data.

Step 1

We looked at the raw object.

SELECT JSON_OBJECT
FROM BRONZE.CLOSE_CRM_USERS_RAW;
Step 2

We checked the keys.

OBJECT_KEYS(JSON_OBJECT)
Step 3

We checked the nested object.

That's when we noticed something like:

raw_data
    │
    ├── INSERT_DATE
    └── JSON_OBJECT

That was the clue.

Step 4

We realized

JSON_OBJECT

was not a JSON object.

It was actually

STRING

containing JSON.

Example

"{ 'data':[ ... ] }"
Step 5

Snowflake cannot flatten a string.

We first had to convert it into JSON.

We used

TRY_PARSE_JSON(...)
Step 6

Because the string contained

'

instead of

"

we repaired it first.

REPLACE(..., '''', '"')

Then

TRY_PARSE_JSON(...)
Final path

Instead of

r.JSON_OBJECT:raw_data:data

we used

TRY_PARSE_JSON(
    REPLACE(
        r.JSON_OBJECT:raw_data:JSON_OBJECT::STRING,
        '''',
        '"'
    )
):data

Now Snowflake saw a real JSON array.

Why did TRY_PARSE_JSON return NULL but COUNT(*) returned 8,600?

This confused us at first.

When we ran:

SELECT
TRY_PARSE_JSON(...)
LIMIT 5;

we saw

NULL
NULL
NULL
NULL
NULL

We thought parsing wasn't working.

But then

SELECT COUNT(*)
...

returned

8600
Why?

Because

LIMIT 5

only showed the first five Bronze records.

Those happened to contain empty or malformed values.

The rest of the table contained valid JSON.

So

First 5

NULL

does NOT mean

Entire table = NULL

This is a common mistake people make when debugging.

Why did the final table only have 100 rows?

Because

8600

was

historical snapshots

The requirement says:

Daily refresh contains historical records.

The same user appears over multiple days.

Example

User A
Day 1

User A
Day 2

User A
Day 3

After

ROW_NUMBER()

PARTITION BY USER_ID

we keep

Latest version

Result

100 unique CRM users
This is exactly CDC
8600 raw records

↓

MD5_HASH

↓

ROW_NUMBER()

↓

MERGE

↓

100 current users
```
