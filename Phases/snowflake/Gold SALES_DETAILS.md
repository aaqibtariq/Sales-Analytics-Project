# Validate sale activity names and current fields

```
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS TOTAL_ROWS,
    COUNT_IF(SETTER_EMAIL IS NOT NULL) AS SETTER_ROWS,
    COUNT_IF(CLOSER_EMAIL IS NOT NULL) AS CLOSER_ROWS,
    COUNT_IF(CONTRACT_VALUE IS NOT NULL) AS CONTRACT_VALUE_ROWS,
    COUNT_IF(CASH_COLLECTED IS NOT NULL) AS CASH_COLLECTED_ROWS,
    COUNT_IF(PROGRAM IS NOT NULL) AS PROGRAM_ROWS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '7) New Sale',
    '8) New Sale [Custom Payment Plan]'
)
GROUP BY CUSTOM_ACTIVITY
ORDER BY CUSTOM_ACTIVITY;

```
# Inspect sample sale records
```
SELECT
    LEAD_ID,
    ACTIVITY_ID,
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME,
    ACTIVITY_AT,
    SETTER_EMAIL,
    SETTER_NAME,
    CLOSER_EMAIL,
    CLOSER_NAME,
    CONTRACT_VALUE,
    PROGRAM,
    CASH_COLLECTED
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '7) New Sale',
    '8) New Sale [Custom Payment Plan]'
)
LIMIT 50;

```

# Validate the dedicated DATE_OF_SALE custom field in Bronze

```

Run:
SELECT
    activity.value:id::STRING AS ACTIVITY_ID,
    activity.value:lead_id::STRING AS LEAD_ID,
    activity.value:custom_activity_type_id::STRING AS CUSTOM_ACTIVITY_ID,
    activity.value:activity_at::TIMESTAMP_NTZ AS ACTIVITY_AT,
    activity.value:
        "custom.cf_duzvav8KQ1PjbJLeAjqZna96ndGp3jO5U2JTfIuGFKi"
        ::DATE AS DATE_OF_SALE,
    activity.value:
        "custom.cf_vIanPjPEit6ssajmWkcprF2V1nO1itfes8hOSnjmhfT"
        ::STRING AS CONTRACT_VALUE,
    activity.value:
        "custom.cf_eyLbGJm9DYY7cuJk2otnCxhUEzK9ayEARiE81xPG5uY"
        ::STRING AS CASH_COLLECTED
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW r,
LATERAL FLATTEN(
    INPUT => r.JSON_OBJECT:raw_data:data
) activity
WHERE activity.value:_type::STRING = 'CustomActivity'
  AND (
      activity.value:
          "custom.cf_duzvav8KQ1PjbJLeAjqZna96ndGp3jO5U2JTfIuGFKi"
          IS NOT NULL
      OR activity.value:
          "custom.cf_vIanPjPEit6ssajmWkcprF2V1nO1itfes8hOSnjmhfT"
          IS NOT NULL
      OR activity.value:
          "custom.cf_eyLbGJm9DYY7cuJk2otnCxhUEzK9ayEARiE81xPG5uY"
          IS NOT NULL
  )
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY
        activity.value:lead_id::STRING,
        activity.value:id::STRING
    ORDER BY
        activity.value:activity_at::TIMESTAMP_NTZ DESC,
        activity.value:date_updated::TIMESTAMP_NTZ DESC
) = 1
LIMIT 100;
```

# update lead act summary

```
Add the column
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA SILVER;

ALTER TABLE SILVER.LEADS_ACTIVITIES_SUMMARY
ADD COLUMN IF NOT EXISTS DATE_OF_SALE DATE;


-- 2. Populate it from the deduplicated Bronze activity
UPDATE SILVER.LEADS_ACTIVITIES_SUMMARY tgt
SET DATE_OF_SALE = src.DATE_OF_SALE
FROM (
    SELECT
        activity.value:id::STRING AS ACTIVITY_ID,
        activity.value:lead_id::STRING AS LEAD_ID,

        TRY_TO_DATE(
            activity.value:
                "custom.cf_duzvav8KQ1PjbJLeAjqZna96ndGp3jO5U2JTfIuGFKi"
                ::STRING
        ) AS DATE_OF_SALE

    FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW r,
    LATERAL FLATTEN(
        INPUT => r.JSON_OBJECT:raw_data:data
    ) activity

    WHERE activity.value:
        "custom.cf_duzvav8KQ1PjbJLeAjqZna96ndGp3jO5U2JTfIuGFKi"
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
  AND tgt.ACTIVITY_ID = src.ACTIVITY_ID;

```
# Validate the field
```
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS TOTAL_ROWS,
    COUNT_IF(DATE_OF_SALE IS NOT NULL) AS DATE_OF_SALE_ROWS,
    COUNT_IF(CONTRACT_VALUE IS NOT NULL) AS CONTRACT_VALUE_ROWS,
    COUNT_IF(CASH_COLLECTED IS NOT NULL) AS CASH_COLLECTED_ROWS
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '7) New Sale',
    '8) New Sale [Custom Payment Plan]'
)
GROUP BY CUSTOM_ACTIVITY
ORDER BY CUSTOM_ACTIVITY;

```
# Inspect sample records

```
SELECT
    LEAD_ID,
    ACTIVITY_ID,
    CUSTOM_ACTIVITY,
    ACTIVITY_AT,
    DATE_OF_SALE,
    SETTER_EMAIL,
    SETTER_NAME,
    CLOSER_EMAIL,
    CLOSER_NAME,
    CONTRACT_VALUE,
    PROGRAM,
    CASH_COLLECTED
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '7) New Sale',
    '8) New Sale [Custom Payment Plan]'
)
ORDER BY ACTIVITY_AT DESC
LIMIT 50;

```
# Confirm Silver count and dedup remain unchanged

```
SELECT COUNT(*) AS SUMMARY_ROWS
FROM SILVER.LEADS_ACTIVITIES_SUMMARY;
Expected:
1,063,628
SELECT
    LEAD_ID,
    ACTIVITY_ID,
    COUNT(*) AS CNT
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
GROUP BY LEAD_ID, ACTIVITY_ID
HAVING COUNT(*) > 1;
Expected:
0 rows

```
# GOLD.SALES_DETAILS

```



USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW GOLD.SALES_DETAILS AS
SELECT
    LEAD_ID,

    ACTIVITY_AT::DATE AS ACTIVITY_LOG_DATE,

    CUSTOM_ACTIVITY_OUTCOME AS SALE_STATUS,

    SETTER_EMAIL,
    SETTER_NAME,

    CLOSER_EMAIL,
    CLOSER_NAME,

    CONTRACT_VALUE AS CONTRACTED_VALUE,

    DATE_OF_SALE,

    PROGRAM,

    CASH_COLLECTED

FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '7) New Sale',
    '8) New Sale [Custom Payment Plan]'
);

```
# Validation 1

```
SELECT COUNT(*) AS SALES_DETAILS_COUNT
FROM GOLD.SALES_DETAILS;
Expected:
270

```

# Validation 2

```
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS TOTAL
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY IN (
    '7) New Sale',
    '8) New Sale [Custom Payment Plan]'
)
GROUP BY CUSTOM_ACTIVITY;
Expected to match the Gold row count.

```
# Validation 3

```
SELECT
    COUNT_IF(CONTRACTED_VALUE IS NOT NULL) AS CONTRACT_ROWS,
    COUNT_IF(CASH_COLLECTED IS NOT NULL) AS CASH_ROWS,
    COUNT_IF(DATE_OF_SALE IS NOT NULL) AS DATE_ROWS,
    COUNT_IF(PROGRAM IS NOT NULL) AS PROGRAM_ROWS
FROM GOLD.SALES_DETAILS;
Expected (based on your Silver validation):
CONTRACT_ROWS = 230
CASH_ROWS = 230
DATE_ROWS = 230
PROGRAM_ROWS = 270

```
# Validation 4
```
SELECT *
FROM GOLD.SALES_DETAILS
LIMIT 25;

```



