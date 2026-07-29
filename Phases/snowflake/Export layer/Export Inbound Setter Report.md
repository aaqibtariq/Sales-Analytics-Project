# create report

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW
SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT AS

WITH TRIAGE_BASE AS (

    /*
      One row per Triage Call.
      This is the base population for the report.
    */
    SELECT
        LEAD_ID,
        ACTIVITY_ID AS TRIAGE_ACTIVITY_ID,
        ACTIVITY_AT AS TRIAGE_TIMESTAMP,
        ACTIVITY_AT::DATE AS TRIAGE_DATE,

        COALESCE(
            DEA_INTERNAL_NAME,
            'UNMAPPED SETTER'
        ) AS SETTER,

        DEA_INTERNAL_EMAIL AS SETTER_EMAIL,
        CUSTOM_ACTIVITY_OUTCOME AS TRIAGE_CALL_OUTCOME,

        1 AS INBOUND_BOOKED,

        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME IS NOT NULL
             AND CUSTOM_ACTIVITY_OUTCOME NOT IN (
                    '6. No Show',
                    '7. Reschedule',
                    '8. Cancel'
                 )
            THEN 1
            ELSE 0
        END AS INBOUND_TAKEN,

        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME =
                 '1. Strategy Call Scheduled'
            THEN 1
            ELSE 0
        END AS STRATEGY_CALL_BOOKED

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '3) Triage Call'
),

STRATEGY_BASE AS (

    /*
      One row per Strategy Call.
    */
    SELECT
        LEAD_ID,
        ACTIVITY_ID AS STRATEGY_ACTIVITY_ID,
        ACTIVITY_AT AS STRATEGY_TIMESTAMP,

        CUSTOM_ACTIVITY_OUTCOME AS STRATEGY_CALL_OUTCOME,
        OFFER_PRESENTED,

        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
            THEN 1
            ELSE 0
        END AS STRATEGY_CALL_TAKEN,

        CASE
            WHEN UPPER(TRIM(OFFER_PRESENTED)) = 'YES'
            THEN 1
            ELSE 0
        END AS OFFER_PRESENTED_FLAG

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
),

STRATEGY_TO_TRIAGE_CANDIDATES AS (

    /*
      Match each Strategy Call to prior Triage Calls for the same lead.
      The nearest preceding Triage Call is retained.
    */
    SELECT
        s.STRATEGY_ACTIVITY_ID,
        s.STRATEGY_TIMESTAMP,
        s.STRATEGY_CALL_OUTCOME,
        s.STRATEGY_CALL_TAKEN,
        s.OFFER_PRESENTED_FLAG,

        t.TRIAGE_ACTIVITY_ID,
        t.TRIAGE_TIMESTAMP,

        ROW_NUMBER() OVER (
            PARTITION BY s.STRATEGY_ACTIVITY_ID
            ORDER BY
                t.TRIAGE_TIMESTAMP DESC,
                t.TRIAGE_ACTIVITY_ID DESC
        ) AS MATCH_RANK

    FROM STRATEGY_BASE s

    INNER JOIN TRIAGE_BASE t
        ON s.LEAD_ID = t.LEAD_ID
       AND t.TRIAGE_TIMESTAMP <= s.STRATEGY_TIMESTAMP
),

STRATEGY_ATTRIBUTED AS (

    /*
      Each Strategy Call is attributed to no more than one Triage Call.
    */
    SELECT
        TRIAGE_ACTIVITY_ID,

        COUNT(*) AS STRATEGY_CALL_EVENTS,

        SUM(STRATEGY_CALL_TAKEN)
            AS STRATEGY_CALL_TAKEN,

        SUM(OFFER_PRESENTED_FLAG)
            AS OFFERS_PRESENTED

    FROM STRATEGY_TO_TRIAGE_CANDIDATES

    WHERE MATCH_RANK = 1

    GROUP BY TRIAGE_ACTIVITY_ID
),

SALES_BASE AS (

    /*
      One row per sale activity.
    */
    SELECT
        LEAD_ID,
        ACTIVITY_ID AS SALE_ACTIVITY_ID,

        COALESCE(
            ACTIVITY_AT,
            DATE_OF_SALE::TIMESTAMP_NTZ
        ) AS SALE_TIMESTAMP,

        TRY_TO_DECIMAL(
            NULLIF(
                REGEXP_REPLACE(
                    CONTRACT_VALUE,
                    '[^0-9.-]',
                    ''
                ),
                ''
            ),
            18,
            2
        ) AS CONTRACTED_VALUE_NUMERIC

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    )
),

SALE_TO_TRIAGE_CANDIDATES AS (

    /*
      Match each sale to prior Triage Calls for the same lead.
      The nearest preceding Triage Call is retained.
    */
    SELECT
        sa.SALE_ACTIVITY_ID,
        sa.CONTRACTED_VALUE_NUMERIC,

        t.TRIAGE_ACTIVITY_ID,
        t.TRIAGE_TIMESTAMP,

        ROW_NUMBER() OVER (
            PARTITION BY sa.SALE_ACTIVITY_ID
            ORDER BY
                t.TRIAGE_TIMESTAMP DESC,
                t.TRIAGE_ACTIVITY_ID DESC
        ) AS MATCH_RANK

    FROM SALES_BASE sa

    INNER JOIN TRIAGE_BASE t
        ON sa.LEAD_ID = t.LEAD_ID
       AND t.TRIAGE_TIMESTAMP <= sa.SALE_TIMESTAMP
),

SALES_ATTRIBUTED AS (

    /*
      Each sale is attributed to no more than one Triage Call.
    */
    SELECT
        TRIAGE_ACTIVITY_ID,

        COUNT(*) AS TOTAL_SALES,

        SUM(CONTRACTED_VALUE_NUMERIC)
            AS TOTAL_CONTRACT_VALUE,

        COUNT(CONTRACTED_VALUE_NUMERIC)
            AS SALES_WITH_CONTRACT_VALUE

    FROM SALE_TO_TRIAGE_CANDIDATES

    WHERE MATCH_RANK = 1

    GROUP BY TRIAGE_ACTIVITY_ID
),

TRIAGE_ENRICHED AS (

    /*
      Join only one-row-per-Triage aggregated datasets.
      This avoids many-to-many multiplication.
    */
    SELECT
        t.TRIAGE_DATE,
        t.SETTER,
        t.SETTER_EMAIL,
        t.TRIAGE_ACTIVITY_ID,

        t.INBOUND_BOOKED,
        t.INBOUND_TAKEN,
        t.STRATEGY_CALL_BOOKED,

        COALESCE(
            st.STRATEGY_CALL_TAKEN,
            0
        ) AS STRATEGY_CALL_TAKEN,

        COALESCE(
            st.OFFERS_PRESENTED,
            0
        ) AS OFFERS_PRESENTED,

        COALESCE(
            sa.TOTAL_SALES,
            0
        ) AS TOTAL_SALES,

        COALESCE(
            sa.TOTAL_CONTRACT_VALUE,
            0
        ) AS TOTAL_CONTRACT_VALUE,

        COALESCE(
            sa.SALES_WITH_CONTRACT_VALUE,
            0
        ) AS SALES_WITH_CONTRACT_VALUE

    FROM TRIAGE_BASE t

    LEFT JOIN STRATEGY_ATTRIBUTED st
        ON t.TRIAGE_ACTIVITY_ID =
           st.TRIAGE_ACTIVITY_ID

    LEFT JOIN SALES_ATTRIBUTED sa
        ON t.TRIAGE_ACTIVITY_ID =
           sa.TRIAGE_ACTIVITY_ID
)

SELECT
    TRIAGE_DATE,
    SETTER,
    SETTER_EMAIL,

    SUM(INBOUND_BOOKED)
        AS INBOUND_BOOKED,

    SUM(INBOUND_TAKEN)
        AS INBOUND_TAKEN,

    ROUND(
        100.0 * SUM(INBOUND_TAKEN)
        / NULLIF(SUM(INBOUND_BOOKED), 0),
        2
    ) AS SHOW_RATE,

    ROUND(
        100.0 * SUM(STRATEGY_CALL_BOOKED)
        / NULLIF(SUM(INBOUND_BOOKED), 0),
        2
    ) AS TRIAGE_SET_RATE,

    SUM(STRATEGY_CALL_BOOKED)
        AS STRATEGY_CALL_BOOKED,

    SUM(STRATEGY_CALL_TAKEN)
        AS STRATEGY_CALL_TAKEN,

    SUM(OFFERS_PRESENTED)
        AS OFFERS_PRESENTED,

    ROUND(
        100.0 * SUM(OFFERS_PRESENTED)
        / NULLIF(SUM(STRATEGY_CALL_TAKEN), 0),
        2
    ) AS OFFER_RATE,

    SUM(TOTAL_SALES)
        AS TOTAL_SALES,

    ROUND(
        100.0 * SUM(TOTAL_SALES)
        / NULLIF(SUM(STRATEGY_CALL_TAKEN), 0),
        2
    ) AS SALE_RATE,

    ROUND(
        SUM(TOTAL_CONTRACT_VALUE)
        / NULLIF(SUM(SALES_WITH_CONTRACT_VALUE), 0),
        2
    ) AS AVERAGE_ORDER_VALUE

FROM TRIAGE_ENRICHED

GROUP BY
    TRIAGE_DATE,
    SETTER,
    SETTER_EMAIL;
```

# Validate the report

```
Total report rows
SELECT COUNT(*)
FROM GOLD.INBOUND_SETTER_REPORT;

```

# View the report
```
SELECT *
FROM GOLD.INBOUND_SETTER_REPORT
ORDER BY TRIAGE_DATE, SETTER;

````

# Validate booked totals
```
SELECT
SUM(INBOUND_BOOKED)
FROM GOLD.INBOUND_SETTER_REPORT;

.
```
# Validate Strategy Calls booked
```
SELECT
SUM(STRATEGY_CALL_BOOKED)
FROM GOLD.INBOUND_SETTER_REPORT;


```

# Validate sales
```
SELECT
SUM(TOTAL_SALES)
FROM GOLD.INBOUND_SETTER_REPORT;
```

# more test

```



  SELECT
    SUM(INBOUND_BOOKED) AS INBOUND_BOOKED,
    SUM(INBOUND_TAKEN) AS INBOUND_TAKEN,
    SUM(STRATEGY_CALL_BOOKED) AS STRATEGY_CALL_BOOKED,

    ROUND(
        100.0 * SUM(INBOUND_TAKEN)
        / NULLIF(SUM(INBOUND_BOOKED), 0),
        2
    ) AS OVERALL_SHOW_RATE,

    ROUND(
        100.0 * SUM(STRATEGY_CALL_BOOKED)
        / NULLIF(SUM(INBOUND_BOOKED), 0),
        2
    ) AS OVERALL_TRIAGE_SET_RATE

FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT;


SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY = '3) Triage Call'
    ) AS SILVER_TRIAGE_ROWS,

    (
        SELECT SUM(INBOUND_BOOKED)
        FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT
    ) AS REPORT_TRIAGE_ROWS,

    (
        SELECT COUNT_IF(
            CUSTOM_ACTIVITY_OUTCOME =
                '1. Strategy Call Scheduled'
        )
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY = '3) Triage Call'
    ) AS SILVER_TRIAGE_SETS,

    (
        SELECT SUM(STRATEGY_CALL_BOOKED)
        FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT
    ) AS REPORT_TRIAGE_SETS;

    SELECT
    COUNT_IF(
        SHOW_RATE < 0 OR SHOW_RATE > 100
    ) AS INVALID_SHOW_RATE_ROWS,

    COUNT_IF(
        TRIAGE_SET_RATE < 0 OR TRIAGE_SET_RATE > 100
    ) AS INVALID_TRIAGE_SET_RATE_ROWS,

    COUNT_IF(
        OFFER_RATE < 0 OR OFFER_RATE > 100
    ) AS INVALID_OFFER_RATE_ROWS,

    COUNT_IF(
        SALE_RATE < 0 OR SALE_RATE > 100
    ) AS INVALID_SALE_RATE_ROWS

FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT;

SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.GOLD.SALES_DETAILS
    ) AS TOTAL_SALES_SOURCE,

    (
        SELECT SUM(TOTAL_SALES)
        FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT
    ) AS SALES_ATTRIBUTED_TO_INBOUND_TRIAGE;


SELECT *
FROM GOLD.INBOUND_SETTER_REPORT limit 100;

SELECT *
FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT
WHERE SALE_RATE > 100
   OR SALE_RATE < 0
   OR SALE_RATE IS NULL;


```
