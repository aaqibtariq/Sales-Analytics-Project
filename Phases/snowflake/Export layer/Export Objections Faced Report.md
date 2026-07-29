# Create report

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW
SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT AS

WITH STRATEGY_CALLS_DEDUP AS (

    /*
        Keep one row per Strategy Call activity ID.

        Current validated source:
            5,044 Strategy Call rows
            5,036 distinct Strategy Call activity IDs

        The duplicate activity IDs contain the same objection values,
        but deduplication prevents those repeated source records from
        inflating call counts and objection percentages.
    */

    SELECT
        ACTIVITY_ID,
        LEAD_ID,

        COALESCE(
            NULLIF(TRIM(CLOSER_NAME), ''),
            'UNMAPPED CLOSER'
        ) AS CLOSER_NAME,

        NULLIF(
            TRIM(CLOSER_EMAIL),
            ''
        ) AS CLOSER_EMAIL,

        ACTIVITY_AT,
        ACTIVITY_AT::DATE AS ACTIVITY_DATE,

        OBJECTIONS_FACED

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ACTIVITY_ID
        ORDER BY
            DATE_UPDATED DESC NULLS LAST,
            UPDATE_DATE DESC NULLS LAST,
            INSERT_DATE DESC NULLS LAST,
            ACTIVITY_AT DESC NULLS LAST
    ) = 1
),

CALL_TOTALS AS (

    /*
        Count all deduplicated Strategy Calls by closer and activity date.

        Calls remain in TOTAL_CALLS even when:
            - OBJECTIONS_FACED is NULL
            - OBJECTIONS_FACED is blank
            - no objection was selected

        This follows the SME logic because objection percentages use
        total Strategy Calls as the denominator.
    */

    SELECT
        CLOSER_NAME,
        CLOSER_EMAIL,
        ACTIVITY_DATE,

        COUNT(*) AS TOTAL_CALLS

    FROM STRATEGY_CALLS_DEDUP

    GROUP BY
        CLOSER_NAME,
        CLOSER_EMAIL,
        ACTIVITY_DATE
),

OBJECTION_VALUES AS (

    /*
        OBJECTIONS_FACED is a VARCHAR containing a JSON array.

        Examples:

            ["Money"]

            ["Money","Partner"]

            ["Logistical","Partner","Trust"]

        TRY_PARSE_JSON converts the VARCHAR into JSON.

        LATERAL FLATTEN creates one row per objection selected
        for the Strategy Call.
    */

    SELECT
        sc.ACTIVITY_ID,
        sc.CLOSER_NAME,
        sc.CLOSER_EMAIL,
        sc.ACTIVITY_DATE,

        TRIM(
            objection.value::STRING
        ) AS OBJECTION_CATEGORY

    FROM STRATEGY_CALLS_DEDUP sc,

    LATERAL FLATTEN(
        INPUT => TRY_PARSE_JSON(sc.OBJECTIONS_FACED)
    ) objection

    WHERE sc.OBJECTIONS_FACED IS NOT NULL
      AND TRIM(sc.OBJECTIONS_FACED) <> ''
      AND TYPEOF(
            TRY_PARSE_JSON(sc.OBJECTIONS_FACED)
          ) = 'ARRAY'
      AND objection.value IS NOT NULL
      AND TRIM(objection.value::STRING) <> ''
),

OBJECTION_METRICS AS (

    /*
        Count the number of distinct Strategy Calls containing
        each SME-approved objection.

        COUNT(DISTINCT ACTIVITY_ID) ensures an objection is counted
        no more than once per Strategy Call.
    */

    SELECT
        CLOSER_NAME,
        CLOSER_EMAIL,
        ACTIVITY_DATE,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Money'
                THEN ACTIVITY_ID
            END
        ) AS MONEY_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Fear'
                THEN ACTIVITY_ID
            END
        ) AS FEAR_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Hung Up'
                THEN ACTIVITY_ID
            END
        ) AS HUNG_UP_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Logistical'
                THEN ACTIVITY_ID
            END
        ) AS LOGISTICAL_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'No Objections'
                THEN ACTIVITY_ID
            END
        ) AS NO_OBJ_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Talking to Other Coaches'
                THEN ACTIVITY_ID
            END
        ) AS OTHER_COACHES_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Partner'
                THEN ACTIVITY_ID
            END
        ) AS PARTNER_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Think About It'
                THEN ACTIVITY_ID
            END
        ) AS THINK_ABT_IT_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Time'
                THEN ACTIVITY_ID
            END
        ) AS TIME_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Trust'
                THEN ACTIVITY_ID
            END
        ) AS TRUST_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY = 'Value'
                THEN ACTIVITY_ID
            END
        ) AS VALUE_COUNT,

        COUNT(
            DISTINCT CASE
                WHEN OBJECTION_CATEGORY =
                     'Wasn''t Looking For What We Offered'
                THEN ACTIVITY_ID
            END
        ) AS NOT_LOOKING_COUNT

    FROM OBJECTION_VALUES

    GROUP BY
        CLOSER_NAME,
        CLOSER_EMAIL,
        ACTIVITY_DATE
)

SELECT
    ct.CLOSER_NAME,
    ct.CLOSER_EMAIL,
    ct.ACTIVITY_DATE,
    ct.TOTAL_CALLS,

    /*
        Objection counts
    */

    COALESCE(
        om.MONEY_COUNT,
        0
    ) AS MONEY_COUNT,

    COALESCE(
        om.FEAR_COUNT,
        0
    ) AS FEAR_COUNT,

    COALESCE(
        om.HUNG_UP_COUNT,
        0
    ) AS HUNG_UP_COUNT,

    COALESCE(
        om.LOGISTICAL_COUNT,
        0
    ) AS LOGISTICAL_COUNT,

    COALESCE(
        om.NO_OBJ_COUNT,
        0
    ) AS NO_OBJ_COUNT,

    COALESCE(
        om.OTHER_COACHES_COUNT,
        0
    ) AS OTHER_COACHES_COUNT,

    COALESCE(
        om.PARTNER_COUNT,
        0
    ) AS PARTNER_COUNT,

    COALESCE(
        om.THINK_ABT_IT_COUNT,
        0
    ) AS THINK_ABT_IT_COUNT,

    COALESCE(
        om.TIME_COUNT,
        0
    ) AS TIME_COUNT,

    COALESCE(
        om.TRUST_COUNT,
        0
    ) AS TRUST_COUNT,

    COALESCE(
        om.VALUE_COUNT,
        0
    ) AS VALUE_COUNT,

    COALESCE(
        om.NOT_LOOKING_COUNT,
        0
    ) AS NOT_LOOKING_COUNT,

    /*
        Objection percentages

        Each percentage is:

            Calls containing objection
            ---------------------------
                 Total calls
                    × 100

        One Strategy Call can contain multiple objections.
        Therefore, objection percentages do not need to total 100%.
    */

    ROUND(
        100.0
        * COALESCE(om.MONEY_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Money%",

    ROUND(
        100.0
        * COALESCE(om.FEAR_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Fear%",

    ROUND(
        100.0
        * COALESCE(om.HUNG_UP_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Hung Up%",

    ROUND(
        100.0
        * COALESCE(om.LOGISTICAL_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Logistical%",

    ROUND(
        100.0
        * COALESCE(om.NO_OBJ_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "No Obj%",

    ROUND(
        100.0
        * COALESCE(om.OTHER_COACHES_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Other Coaches%",

    ROUND(
        100.0
        * COALESCE(om.PARTNER_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Partner%",

    ROUND(
        100.0
        * COALESCE(om.THINK_ABT_IT_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Think Abt It%",

    ROUND(
        100.0
        * COALESCE(om.TIME_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Time%",

    ROUND(
        100.0
        * COALESCE(om.TRUST_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Trust%",

    ROUND(
        100.0
        * COALESCE(om.VALUE_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Value%",

    ROUND(
        100.0
        * COALESCE(om.NOT_LOOKING_COUNT, 0)
        / NULLIF(ct.TOTAL_CALLS, 0),
        2
    ) AS "Wsn't Lkng Fr Wht We Offrd%"

FROM CALL_TOTALS ct

LEFT JOIN OBJECTION_METRICS om
    ON ct.ACTIVITY_DATE = om.ACTIVITY_DATE
   AND ct.CLOSER_NAME = om.CLOSER_NAME
   AND EQUAL_NULL(
        ct.CLOSER_EMAIL,
        om.CLOSER_EMAIL
   );

```

# validation 

```



SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
    ) AS SILVER_STRATEGY_ROWS,

    (
        SELECT COUNT(DISTINCT ACTIVITY_ID)
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
    ) AS SILVER_UNIQUE_STRATEGY_CALLS,

    (
        SELECT SUM(TOTAL_CALLS)
        FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT
    ) AS REPORT_TOTAL_CALLS;


    SELECT
    SUM(TOTAL_CALLS) AS TOTAL_CALLS,

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

FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT;




SELECT
    COUNT_IF(
        "Money%" < 0
        OR "Money%" > 100
    ) AS INVALID_MONEY_ROWS,

    COUNT_IF(
        "Fear%" < 0
        OR "Fear%" > 100
    ) AS INVALID_FEAR_ROWS,

    COUNT_IF(
        "Hung Up%" < 0
        OR "Hung Up%" > 100
    ) AS INVALID_HUNG_UP_ROWS,

    COUNT_IF(
        "Logistical%" < 0
        OR "Logistical%" > 100
    ) AS INVALID_LOGISTICAL_ROWS,

    COUNT_IF(
        "No Obj%" < 0
        OR "No Obj%" > 100
    ) AS INVALID_NO_OBJ_ROWS,

    COUNT_IF(
        "Other Coaches%" < 0
        OR "Other Coaches%" > 100
    ) AS INVALID_OTHER_COACHES_ROWS,

    COUNT_IF(
        "Partner%" < 0
        OR "Partner%" > 100
    ) AS INVALID_PARTNER_ROWS,

    COUNT_IF(
        "Think Abt It%" < 0
        OR "Think Abt It%" > 100
    ) AS INVALID_THINK_ABOUT_IT_ROWS,

    COUNT_IF(
        "Time%" < 0
        OR "Time%" > 100
    ) AS INVALID_TIME_ROWS,

    COUNT_IF(
        "Trust%" < 0
        OR "Trust%" > 100
    ) AS INVALID_TRUST_ROWS,

    COUNT_IF(
        "Value%" < 0
        OR "Value%" > 100
    ) AS INVALID_VALUE_ROWS,

    COUNT_IF(
        "Wsn't Lkng Fr Wht We Offrd%" < 0
        OR "Wsn't Lkng Fr Wht We Offrd%" > 100
    ) AS INVALID_NOT_LOOKING_ROWS

FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT;










SELECT
    COUNT_IF(MONEY_COUNT > TOTAL_CALLS)
        AS INVALID_MONEY_COUNT_ROWS,

    COUNT_IF(FEAR_COUNT > TOTAL_CALLS)
        AS INVALID_FEAR_COUNT_ROWS,

    COUNT_IF(HUNG_UP_COUNT > TOTAL_CALLS)
        AS INVALID_HUNG_UP_COUNT_ROWS,

    COUNT_IF(LOGISTICAL_COUNT > TOTAL_CALLS)
        AS INVALID_LOGISTICAL_COUNT_ROWS,

    COUNT_IF(NO_OBJ_COUNT > TOTAL_CALLS)
        AS INVALID_NO_OBJ_COUNT_ROWS,

    COUNT_IF(OTHER_COACHES_COUNT > TOTAL_CALLS)
        AS INVALID_OTHER_COACHES_COUNT_ROWS,

    COUNT_IF(PARTNER_COUNT > TOTAL_CALLS)
        AS INVALID_PARTNER_COUNT_ROWS,

    COUNT_IF(THINK_ABT_IT_COUNT > TOTAL_CALLS)
        AS INVALID_THINK_ABOUT_IT_COUNT_ROWS,

    COUNT_IF(TIME_COUNT > TOTAL_CALLS)
        AS INVALID_TIME_COUNT_ROWS,

    COUNT_IF(TRUST_COUNT > TOTAL_CALLS)
        AS INVALID_TRUST_COUNT_ROWS,

    COUNT_IF(VALUE_COUNT > TOTAL_CALLS)
        AS INVALID_VALUE_COUNT_ROWS,

    COUNT_IF(NOT_LOOKING_COUNT > TOTAL_CALLS)
        AS INVALID_NOT_LOOKING_COUNT_ROWS

FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT;






SELECT
    CLOSER_NAME,
    CLOSER_EMAIL,

    SUM(TOTAL_CALLS) AS TOTAL_CALLS,

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

FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT

GROUP BY
    CLOSER_NAME,
    CLOSER_EMAIL

ORDER BY
    TOTAL_CALLS DESC,
    CLOSER_NAME;










    SELECT *
FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT

ORDER BY
    ACTIVITY_DATE DESC,
    TOTAL_CALLS DESC,
    CLOSER_NAME;

```
