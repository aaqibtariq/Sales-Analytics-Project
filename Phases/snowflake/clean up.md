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
# Important requirments

```
Important Data Property Each daily data refresh contains:
● All lead activities for a lead is updated daily with new activities appended to the json. Example: Flatten the lead activity data to see the change per activity_at for a single activity id as seen above.
● Meaning: same activity will appear on multiple days.
● This introduces duplicates in the lead activities → pipeline must deduplicate per lead. Every source table contains:
● Stringified data within JSON_OBJECT contains: Single quotes (') enclosing properties and values instead of standard double quotes (").
● Data Processing Requirements 4.1 Deduplication & Cleansing Logic Each daily batch contains historical activities, leading to potential duplicates.
● The data also contains malformed JSON strings that must be repaired before parsing. Required approach:
● Data Repair: Implement a custom UDF to repair malformed strings, neutralize messy text fields (like descriptions or notes), and escape apostrophes prior to JSON parsing.
● Deep Unwrapping: Dynamically unwrap nested arrays (raw_data, data) to access the base activity objects.
● Change Data Capture (CDC): Identify duplicates and track historical changes using an MD5_HASH generated from concatenating key row attributes (e.g., lead_id, activity_at, status_change, etc.).
● Upserts: Use MERGE INTO statements to insert new records and update existing ones only when the MD5_HASHchanges, utilizing INSERT_DATE and UPDATE_DATE for auditability.
● Identify duplicates using: lead_id + activity_id
● Keep the latest activity record using: activity_at (activity timestamp)
● Use upserts (insert new, update existing) into warehouse tables.

```

