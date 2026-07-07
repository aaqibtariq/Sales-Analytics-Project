# Explore the table in order to understand data 

```
SELECT
    JSON_OBJECT
FROM BRONZE.CUSTOM_ACTIVITIES_RAW
LIMIT 5;

SELECT
    OBJECT_KEYS(JSON_OBJECT)
FROM BRONZE.CUSTOM_ACTIVITIES_RAW
LIMIT 5;


-- Path 1
SELECT COUNT(*)
FROM BRONZE.CUSTOM_ACTIVITIES_RAW r,
LATERAL FLATTEN(INPUT => r.JSON_OBJECT:raw_data:data) custom_obj;


-- Path 2
SELECT COUNT(*)
FROM BRONZE.CUSTOM_ACTIVITIES_RAW r,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        REPLACE(r.JSON_OBJECT:raw_data:JSON_OBJECT::STRING, '''', '"')
    ):data
) custom_obj;


SELECT
    JSON_OBJECT,
    INSERT_DATE
FROM BRONZE.CUSTOM_ACTIVITIES_RAW
LIMIT 5;

SELECT
    TYPEOF(JSON_OBJECT) AS JSON_TYPE,
    OBJECT_KEYS(JSON_OBJECT) AS TOP_LEVEL_KEYS
FROM BRONZE.CUSTOM_ACTIVITIES_RAW
LIMIT 5;



```


```

how this table is structured.

CUSTOM_ACTIVITIES_RAW Structure

From your inspection:

JSON_OBJECT
├── insert_date
└── raw_data

So the top-level structure is the same as the other Bronze tables. The difference is what's inside raw_data.

The JSON_OBJECT column already contains:

{
  "insert_date": "...",
  "raw_data": ...
}

and your Bronze table also has a separate INSERT_DATE column.


we also discovered something important during implementation:

CUSTOM_ACTIVITIES_RAW contains metadata definitions (custom activity types, outcomes, fields, etc.), not lead activity instances.
The source has only 43 records, so this is a small metadata dataset, unlike the millions of lead activity records.

One observation

Earlier we discovered that:

LEAD_ACTIVITIES_RAW required flattening.
CLOSE_CRM_USERS_RAW required parsing a stringified inner JSON.
CUSTOM_ACTIVITIES_RAW appears to have yet another structure.

This reinforces an important lesson from the project:

Never assume every source table has the same JSON structure, even if they come from the same application. Inspect each source and build the transformation based on its actual schema.

```

# Create table

```

CREATE OR REPLACE TABLE SILVER.CUSTOM_ACTIVITIES_TRANSIENT AS
SELECT
    JSON_OBJECT,
    INSERT_DATE
FROM BRONZE.CUSTOM_ACTIVITIES_RAW;

```

# validate

```
SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT;

SELECT *
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 5;

```


