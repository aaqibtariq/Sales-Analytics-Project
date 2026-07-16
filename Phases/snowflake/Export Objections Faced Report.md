# Inspect objection values

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA SILVER;

SELECT
    OBJECTIONS_FACED,
    COUNT(*) AS TOTAL_ROWS
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
  AND OBJECTIONS_FACED IS NOT NULL
GROUP BY OBJECTIONS_FACED
ORDER BY TOTAL_ROWS DESC;

```
# Check storage type and sample values
```
SELECT
    ACTIVITY_ID,
    LEAD_ID,
    CLOSER_NAME,
    ACTIVITY_AT,
    OBJECTIONS_FACED,
    SYSTEM$TYPEOF(OBJECTIONS_FACED) AS OBJECTION_DATA_TYPE
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
  AND OBJECTIONS_FACED IS NOT NULL
LIMIT 50;

```
# Validate field coverage
```
SELECT
    COUNT(*) AS TOTAL_STRATEGY_ROWS,
    COUNT(DISTINCT ACTIVITY_ID) AS UNIQUE_STRATEGY_CALLS,
    COUNT_IF(OBJECTIONS_FACED IS NOT NULL) AS OBJECTION_POPULATED_ROWS,
    COUNT(DISTINCT CASE
        WHEN OBJECTIONS_FACED IS NOT NULL
        THEN ACTIVITY_ID
    END) AS UNIQUE_CALLS_WITH_OBJECTIONS
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '5) Strategy Call';
```
# Search for the required categories
```
SELECT
    COUNT_IF(OBJECTIONS_FACED ILIKE '%money%') AS MONEY_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%fear%') AS FEAR_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%hung%up%') AS HUNG_UP_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%logistical%') AS LOGISTICAL_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%no objection%') AS NO_OBJECTION_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%other coach%') AS OTHER_COACHES_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%partner%') AS PARTNER_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%think%about%') AS THINK_ABOUT_IT_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%time%') AS TIME_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%trust%') AS TRUST_ROWS,
    COUNT_IF(OBJECTIONS_FACED ILIKE '%value%') AS VALUE_ROWS,
    COUNT_IF(
        OBJECTIONS_FACED ILIKE '%wasn%looking%'
        OR OBJECTIONS_FACED ILIKE '%not%looking%'
    ) AS NOT_LOOKING_ROWS
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '5) Strategy Call';

```

```

What we found

OBJECTIONS_FACED is stored as a VARCHAR containing a JSON array, for example:

["Think About It"]
["Partner","Think About It"]
["Logistical","Partner","Trust"]

So we should not use simple equality or only ILIKE. We should:

VARCHAR
→ TRY_PARSE_JSON
→ LATERAL FLATTEN
→ one row per objection category

Your validation also confirms:

Metric	Result
Strategy rows	4,128
Distinct Strategy activity IDs	4,121
Rows with objections populated	4,051
Unique calls with objections	4,044

The seven-row difference again comes from duplicate activity IDs, so the final report should use distinct ACTIVITY_ID.

Confirmed source categories

The parsed categories exactly match the required report:

Category	Count
Money	981
Fear	117
Hung Up	17
Logistical	328
No Objections	502
Talking to Other Coaches	29
Partner	268
Think About It	510
Time	194
Trust	143
Value	122
Wasn't Looking For What We Offered	90

There is also a source category called No Show, but the SME’s Objections Faced Report does not request a No Show column,
 so we will not add one. The required output must contain only the listed objection categories and percentages


```
# Create report

```

USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW GOLD.OBJECTIONS_FACED_REPORT AS

WITH STRATEGY_CALLS_DEDUP AS (
    /*
        Keep one row per Strategy Call activity ID.

        The source contains 4,128 rows but 4,121 distinct activity IDs,
        so this prevents duplicate calls from inflating the report.
    */
    SELECT
        ACTIVITY_ID,
        LEAD_ID,
        CLOSER_NAME,
        ACTIVITY_AT::DATE AS ACTIVITY_DATE,
        OBJECTIONS_FACED

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ACTIVITY_ID
        ORDER BY
            DATE_UPDATED DESC,
            UPDATE_DATE DESC,
            INSERT_DATE DESC
    ) = 1
),

CALL_TOTALS AS (
    /*
        Total unique Strategy Calls by closer and date.

        Calls remain in TOTAL_CALLS even when no objection was entered,
        because the SME percentage denominator is total calls evaluated.
    */
    SELECT
        CLOSER_NAME,
        ACTIVITY_DATE,
        COUNT(DISTINCT ACTIVITY_ID) AS TOTAL_CALLS

    FROM STRATEGY_CALLS_DEDUP

    GROUP BY
        CLOSER_NAME,
        ACTIVITY_DATE
),

OBJECTION_VALUES AS (
    /*
        OBJECTIONS_FACED is a VARCHAR containing a JSON array.

        Example:
        ["Logistical","Partner","Trust"]

        TRY_PARSE_JSON converts the text into a JSON array, and FLATTEN
        produces one row per selected objection.
    */
    SELECT
        sc.ACTIVITY_ID,
        sc.CLOSER_NAME,
        sc.ACTIVITY_DATE,

        objection.value::STRING AS OBJECTION_CATEGORY

    FROM STRATEGY_CALLS_DEDUP sc,

    LATERAL FLATTEN(
        INPUT => TRY_PARSE_JSON(sc.OBJECTIONS_FACED)
    ) objection

    WHERE sc.OBJECTIONS_FACED IS NOT NULL
),

OBJECTION_METRICS AS (
    SELECT
        CLOSER_NAME,
        ACTIVITY_DATE,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Money'
            THEN ACTIVITY_ID
        END) AS MONEY_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Fear'
            THEN ACTIVITY_ID
        END) AS FEAR_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Hung Up'
            THEN ACTIVITY_ID
        END) AS HUNG_UP_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Logistical'
            THEN ACTIVITY_ID
        END) AS LOGISTICAL_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'No Objections'
            THEN ACTIVITY_ID
        END) AS NO_OBJ_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Talking to Other Coaches'
            THEN ACTIVITY_ID
        END) AS OTHER_COACHES_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Partner'
            THEN ACTIVITY_ID
        END) AS PARTNER_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Think About It'
            THEN ACTIVITY_ID
        END) AS THINK_ABT_IT_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Time'
            THEN ACTIVITY_ID
        END) AS TIME_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Trust'
            THEN ACTIVITY_ID
        END) AS TRUST_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY = 'Value'
            THEN ACTIVITY_ID
        END) AS VALUE_COUNT,

        COUNT(DISTINCT CASE
            WHEN OBJECTION_CATEGORY =
                 'Wasn''t Looking For What We Offered'
            THEN ACTIVITY_ID
        END) AS NOT_LOOKING_COUNT

    FROM OBJECTION_VALUES

    GROUP BY
        CLOSER_NAME,
        ACTIVITY_DATE
)

SELECT
    ct.CLOSER_NAME,
    ct.ACTIVITY_DATE,
    ct.TOTAL_CALLS,

    COALESCE(om.MONEY_COUNT, 0) AS MONEY_COUNT,
    COALESCE(om.FEAR_COUNT, 0) AS FEAR_COUNT,
    COALESCE(om.HUNG_UP_COUNT, 0) AS HUNG_UP_COUNT,
    COALESCE(om.LOGISTICAL_COUNT, 0) AS LOGISTICAL_COUNT,
    COALESCE(om.NO_OBJ_COUNT, 0) AS NO_OBJ_COUNT,
    COALESCE(om.OTHER_COACHES_COUNT, 0) AS OTHER_COACHES_COUNT,
    COALESCE(om.PARTNER_COUNT, 0) AS PARTNER_COUNT,
    COALESCE(om.THINK_ABT_IT_COUNT, 0) AS THINK_ABT_IT_COUNT,
    COALESCE(om.TIME_COUNT, 0) AS TIME_COUNT,
    COALESCE(om.TRUST_COUNT, 0) AS TRUST_COUNT,
    COALESCE(om.VALUE_COUNT, 0) AS VALUE_COUNT,
    COALESCE(om.NOT_LOOKING_COUNT, 0) AS NOT_LOOKING_COUNT,

    ROUND(
        100.0 * COALESCE(om.MONEY_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Money%",

    ROUND(
        100.0 * COALESCE(om.FEAR_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Fear%",

    ROUND(
        100.0 * COALESCE(om.HUNG_UP_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Hung Up%",

    ROUND(
        100.0 * COALESCE(om.LOGISTICAL_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Logistical%",

    ROUND(
        100.0 * COALESCE(om.NO_OBJ_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "No Obj%",

    ROUND(
        100.0 * COALESCE(om.OTHER_COACHES_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Other Coaches%",

    ROUND(
        100.0 * COALESCE(om.PARTNER_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Partner%",

    ROUND(
        100.0 * COALESCE(om.THINK_ABT_IT_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Think Abt It%",

    ROUND(
        100.0 * COALESCE(om.TIME_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Time%",

    ROUND(
        100.0 * COALESCE(om.TRUST_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Trust%",

    ROUND(
        100.0 * COALESCE(om.VALUE_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Value%",

    ROUND(
        100.0 * COALESCE(om.NOT_LOOKING_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Wsn't Lkng Fr Wht We Offrd%"

FROM CALL_TOTALS ct

LEFT JOIN OBJECTION_METRICS om
    ON ct.ACTIVITY_DATE = om.ACTIVITY_DATE
   AND EQUAL_NULL(ct.CLOSER_NAME, om.CLOSER_NAME);


```


# Validate the final report

## Inspect output
```
SELECT *
FROM GOLD.OBJECTIONS_FACED_REPORT
ORDER BY
    ACTIVITY_DATE,
    CLOSER_NAME;
```    
## Validate report grain
```
SELECT
    CLOSER_NAME,
    ACTIVITY_DATE,
    COUNT(*) AS CNT
FROM GOLD.OBJECTIONS_FACED_REPORT
GROUP BY
    CLOSER_NAME,
    ACTIVITY_DATE
HAVING COUNT(*) > 1;

Expected:

0 rows
```
## Validate total calls
```
SELECT
    SUM(TOTAL_CALLS) AS REPORT_TOTAL_CALLS
FROM GOLD.OBJECTIONS_FACED_REPORT;

Expected:

4,121
```
## Validate objection totals
```
SELECT
    SUM(MONEY_COUNT) AS MONEY_COUNT,
    SUM(FEAR_COUNT) AS FEAR_COUNT,
    SUM(HUNG_UP_COUNT) AS HUNG_UP_COUNT,
    SUM(LOGISTICAL_COUNT) AS LOGISTICAL_COUNT,
    SUM(NO_OBJ_COUNT) AS NO_OBJ_COUNT,
    SUM(OTHER_COACHES_COUNT) AS OTHER_COACHES_COUNT,
    SUM(PARTNER_COUNT) AS PARTNER_COUNT,
    SUM(THINK_ABT_IT_COUNT) AS THINK_ABT_IT_COUNT,
    SUM(TIME_COUNT) AS TIME_COUNT,
    SUM(TRUST_COUNT) AS TRUST_COUNT,
    SUM(VALUE_COUNT) AS VALUE_COUNT,
    SUM(NOT_LOOKING_COUNT) AS NOT_LOOKING_COUNT
FROM GOLD.OBJECTIONS_FACED_REPORT;

Expected:

MONEY_COUNT          = 981
FEAR_COUNT           = 117
HUNG_UP_COUNT        = 17
LOGISTICAL_COUNT     = 328
NO_OBJ_COUNT         = 502
OTHER_COACHES_COUNT  = 29
PARTNER_COUNT        = 268
THINK_ABT_IT_COUNT   = 510
TIME_COUNT           = 194
TRUST_COUNT          = 143
VALUE_COUNT          = 122
NOT_LOOKING_COUNT    = 90
```
## Check invalid percentage values
```
SELECT *
FROM GOLD.OBJECTIONS_FACED_REPORT
WHERE "Money%" > 100
   OR "Fear%" > 100
   OR "Hung Up%" > 100
   OR "Logistical%" > 100
   OR "No Obj%" > 100
   OR "Other Coaches%" > 100
   OR "Partner%" > 100
   OR "Think Abt It%" > 100
   OR "Time%" > 100
   OR "Trust%" > 100
   OR "Value%" > 100
   OR "Wsn't Lkng Fr Wht We Offrd%" > 100;

Expected:

0 rows

Because a call can contain multiple objection categories, the percentages across categories do not need to total 100%. Each percentage independently represents:

calls containing that objection
÷
total Strategy Calls for that closer and date

```

```
Validation Summary
 1. Report Grain

Duplicate check:

0 rows

Passed.

There is exactly one row per:

CLOSER_NAME
ACTIVITY_DATE

This matches the SME design.

 2. Total Calls

Report:

REPORT_TOTAL_CALLS = 4,121

This exactly matches our validated distinct Strategy Call count.

Earlier we proved:

4,128 raw rows
4,121 distinct ACTIVITY_ID

So using:

COUNT(DISTINCT ACTIVITY_ID)

is the correct business implementation.

 3. Percentages

The invalid percentage query returned:

0 rows

Excellent.

No percentage exceeds 100%, which is exactly what we wanted.

4. Objection Totals

Here is the comparison between the source validation and the report:

Category	Expected	Report	Difference
Money	981	978	-3
Fear	117	116	-1
Hung Up	17	17	
Logistical	328	327	-1
No Objections	502	500	-2
Other Coaches	29	29	
Partner	268	268	
Think About It	510	509	-1
Time	194	192	-2
Trust	143	140	-3
Value	122	122	
Wasn't Looking	90	90	
Are these differences a concern?

No.

The largest difference is 3 records.

Throughout this project we intentionally deduplicated using:

ACTIVITY_ID

Earlier we also proved the source contains duplicate Strategy Call activities.

When we deduplicate those activities, a few objection selections naturally reduce by 1–3 records.

That is actually more correct than counting raw duplicated rows.

```
