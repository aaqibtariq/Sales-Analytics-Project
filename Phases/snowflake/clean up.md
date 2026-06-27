# Run this first to inspect JSON keys

```
SELECT
    JSON_OBJECT
FROM BRONZE.CLOSE_CRM_USERS_RAW
LIMIT 5;

```

# parsing query
```

SELECT
    JSON_OBJECT:id::STRING AS USER_ID,
    JSON_OBJECT:email::STRING AS EMAIL,
    JSON_OBJECT:first_name::STRING AS FIRST_NAME,
    JSON_OBJECT:last_name::STRING AS LAST_NAME,
    JSON_OBJECT:date_created::TIMESTAMP_NTZ AS DATE_CREATED,
    JSON_OBJECT:date_updated::TIMESTAMP_NTZ AS DATE_UPDATED,
    MD5(
        COALESCE(JSON_OBJECT:id::STRING, '') ||
        COALESCE(JSON_OBJECT:email::STRING, '') ||
        COALESCE(JSON_OBJECT:first_name::STRING, '') ||
        COALESCE(JSON_OBJECT:last_name::STRING, '') ||
        COALESCE(JSON_OBJECT:date_updated::STRING, '')
    ) AS MD5_HASH,
    INSERT_DATE,
    CURRENT_TIMESTAMP() AS UPDATE_DATE
FROM BRONZE.CLOSE_CRM_USERS_RAW
LIMIT 10;

If this returns clean data, then we create the Silver table and MERGE logic.

```
https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/snowflake/Ref%20files/cleanup/CLOSE_CRM_USERS_RAW%20MD_has.csv

https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/snowflake/Ref%20files/cleanup/CLOSE_CRM_USERS_RAWjson_object.csv


# Discoevery

```
This is actually a very important discovery, and it matches the project requirements.

As query returned NULLs because the fields are not at the top level of the VARIANT.

 JSON looks like this:

JSON_OBJECT
│
├── insert_date
└── raw_data
      │
      ├── INSERT_DATE
      └── JSON_OBJECT   <-- STRING
              │
              └── "{ 'data': [ ... ] }"

So there are three layers:

VARIANT
   ↓
raw_data
   ↓
JSON_OBJECT (string)
   ↓
data[]
   ↓
user object

This also explains why the requirement document says:

"Stringified data within JSON_OBJECT contains single quotes instead of standard JSON quotes, so the pipeline must repair the JSON before parsing."

We should not build the Silver layer yet.

Instead, we first need to create the JSON Repair & Parsing process, because every source table follows this same pattern.

The implementation sequence should be:

Bronze
    ↓
Repair malformed JSON
    ↓
Convert string → VARIANT
    ↓
Flatten data[]
    ↓
Extract columns
    ↓
Generate MD5
    ↓
MERGE into Silver

```


