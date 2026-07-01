# inspect the actual malformed JSON
```
SELECT
    JSON_OBJECT:raw_data:JSON_OBJECT::STRING
FROM BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 5;
```
- returned NULL, which means there is no key named raw_data at the top level of JSON_OBJECT.

# Show one complete JSON object

```
SELECT
    JSON_OBJECT
FROM BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 1;

```

# What are the top-level keys?

```
SELECT
    OBJECT_KEYS(JSON_OBJECT)
FROM BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 5;

```

# Check the data type

```
SELECT
    TYPEOF(JSON_OBJECT)
FROM BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 5;

```

# See the first level as formatted JSON

```
SELECT
    TO_JSON(JSON_OBJECT)
FROM BRONZE.LEAD_ACTIVITIES_RAW
LIMIT 1;

```

# flatten logic

```
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
LIMIT 20;

```
 - as per results LEAD_ACTIVITIES_RAW is okay to procced to silver table
