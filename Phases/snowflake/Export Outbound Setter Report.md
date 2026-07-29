
# 1. Validate outbound top-of-funnel totals

```
SELECT
    COUNT(*) AS TOTAL_OUTBOUND_CALLS,
    COUNT(DISTINCT LEAD_ID) AS TOTAL_LEADS_TOUCHED,
    COUNT_IF(
        CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
    ) AS OUTBOUND_SET
FROM GOLD.OUTBOUND_PROSPECT_DIALS;

Expected:

TOTAL_OUTBOUND_CALLS = 11432
OUTBOUND_SET = 2408

```
#  Validate documented Strategy Call shows

```
SELECT
    COUNT(*) AS TOTAL_STRATEGY_CALL_ROWS,

    COUNT_IF(
        STRATEGY_CALL_OUTCOME IN (
            '1. Follow Up',
            '5. Sale',
            '6. Sale',
            '7. Lost'
        )
    ) AS TOTAL_CLOSER_SHOW,

    COUNT_IF(
        OFFER_PRESENTED = 'Yes'
    ) AS TOTAL_OFFER

FROM GOLD.ALL_STRATEGIES_DETAILS
WHERE CUSTOM_ACTIVITY = '5) Strategy Call';

```
#  Validate sales and revenue
```
SELECT
    COUNT(*) AS TOTAL_SALE,
    SUM(TRY_TO_DECIMAL(CONTRACTED_VALUE, 18, 2)) AS TOTAL_REVENUE,
    AVG(TRY_TO_DECIMAL(CONTRACTED_VALUE, 18, 2)) AS AVERAGE_ORDER_VALUE
FROM GOLD.SALES_DETAILS;

```
#  Check outbound-set leads that later reached Strategy Call
```
SELECT
    COUNT(DISTINCT osb.LEAD_ID) AS OUTBOUND_SET_LEADS,
    COUNT(DISTINCT asd.LEAD_ID) AS LEADS_WITH_LATER_STRATEGY_CALL
FROM GOLD.OUTBOUND_STRATEGIES_BOOKED osb
LEFT JOIN GOLD.ALL_STRATEGIES_DETAILS asd
    ON osb.LEAD_ID = asd.LEAD_ID
   AND asd.DATE_OF_STRATEGY_CALL >= osb.PROSPECT_CALL_DATE;
```
# Check outbound-set leads that later reached Sale
```
SELECT
    COUNT(DISTINCT osb.LEAD_ID) AS OUTBOUND_SET_LEADS,
    COUNT(DISTINCT sd.LEAD_ID) AS LEADS_WITH_LATER_SALE
FROM GOLD.OUTBOUND_STRATEGIES_BOOKED osb

```

# Create report

```

USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW
SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT AS

WITH OUTBOUND_BASE AS (

    /*
      One row per outbound prospecting activity.
    */
    SELECT
        LEAD_ID,
        ACTIVITY_ID AS OUTBOUND_ACTIVITY_ID,
        ACTIVITY_AT AS OUTBOUND_TIMESTAMP,
        ACTIVITY_AT::DATE AS OUTBOUND_DATE,

        YEAROFWEEKISO(ACTIVITY_AT::DATE)
            || '-'
            || LPAD(WEEKISO(ACTIVITY_AT::DATE), 2, '0')
            AS REPORTING_WEEK,

        COALESCE(
            DEA_INTERNAL_NAME,
            'UNMAPPED SETTER'
        ) AS SETTER,

        DEA_INTERNAL_EMAIL AS SETTER_EMAIL,

        CUSTOM_ACTIVITY,
        CUSTOM_ACTIVITY_OUTCOME,

        1 AS OUTBOUND_DIALS,

        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME IS NOT NULL
             AND CUSTOM_ACTIVITY_OUTCOME NOT IN (
                    '6. Not Interested',
                    '4. Unqualified'
                 )
            THEN 1
            ELSE 0
        END AS OUTBOUND_TAKEN,

        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME =
                 '2. Strategy Call Scheduled'
            THEN 1
            ELSE 0
        END AS STRATEGY_CALL_BOOKED

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    )
),

STRATEGY_BASE AS (

    /*
      One row per actual Strategy Call.
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

        /*
          Fixed logic:
          Count an offer only when the Strategy Call was attended.
        */
        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
            AND UPPER(TRIM(OFFER_PRESENTED)) IN (
                'YES',
                'Y',
                'TRUE',
                '1'
            )
            THEN 1
            ELSE 0
        END AS OFFER_PRESENTED_FLAG

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
),

STRATEGY_TO_OUTBOUND_CANDIDATES AS (

    /*
      Match each Strategy Call to all preceding outbound activities
      for the same lead.
    */
    SELECT
        s.LEAD_ID,
        s.STRATEGY_ACTIVITY_ID,
        s.STRATEGY_TIMESTAMP,
        s.STRATEGY_CALL_OUTCOME,
        s.STRATEGY_CALL_TAKEN,
        s.OFFER_PRESENTED_FLAG,

        o.OUTBOUND_ACTIVITY_ID,
        o.OUTBOUND_TIMESTAMP,

        ROW_NUMBER() OVER (
            PARTITION BY s.STRATEGY_ACTIVITY_ID
            ORDER BY
                o.OUTBOUND_TIMESTAMP DESC,
                o.OUTBOUND_ACTIVITY_ID DESC
        ) AS MATCH_RANK

    FROM STRATEGY_BASE s

    INNER JOIN OUTBOUND_BASE o
        ON s.LEAD_ID = o.LEAD_ID
       AND o.OUTBOUND_TIMESTAMP <= s.STRATEGY_TIMESTAMP
),

STRATEGY_ATTRIBUTED AS (

    /*
      Retain only the nearest preceding outbound activity
      for each Strategy Call.
    */
    SELECT
        OUTBOUND_ACTIVITY_ID,

        COUNT(*) AS STRATEGY_CALL_EVENTS,

        SUM(STRATEGY_CALL_TAKEN)
            AS STRATEGY_CALL_TAKEN,

        SUM(OFFER_PRESENTED_FLAG)
            AS OFFERS_PRESENTED

    FROM STRATEGY_TO_OUTBOUND_CANDIDATES

    WHERE MATCH_RANK = 1

    GROUP BY OUTBOUND_ACTIVITY_ID
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
        ) AS CONTRACT_VALUE_NUMERIC,

        TRY_TO_DECIMAL(
            NULLIF(
                REGEXP_REPLACE(
                    CASH_COLLECTED,
                    '[^0-9.-]',
                    ''
                ),
                ''
            ),
            18,
            2
        ) AS CASH_COLLECTED_NUMERIC

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    )
),

SALE_TO_OUTBOUND_CANDIDATES AS (

    /*
      Match each sale to all preceding outbound activities
      for the same lead.
    */
    SELECT
        sa.LEAD_ID,
        sa.SALE_ACTIVITY_ID,
        sa.SALE_TIMESTAMP,
        sa.CONTRACT_VALUE_NUMERIC,
        sa.CASH_COLLECTED_NUMERIC,

        o.OUTBOUND_ACTIVITY_ID,
        o.OUTBOUND_TIMESTAMP,

        ROW_NUMBER() OVER (
            PARTITION BY sa.SALE_ACTIVITY_ID
            ORDER BY
                o.OUTBOUND_TIMESTAMP DESC,
                o.OUTBOUND_ACTIVITY_ID DESC
        ) AS MATCH_RANK

    FROM SALES_BASE sa

    INNER JOIN OUTBOUND_BASE o
        ON sa.LEAD_ID = o.LEAD_ID
       AND o.OUTBOUND_TIMESTAMP <= sa.SALE_TIMESTAMP
),

SALES_ATTRIBUTED AS (

    /*
      Retain only the nearest preceding outbound activity
      for each sale.
    */
    SELECT
        OUTBOUND_ACTIVITY_ID,

        COUNT(*) AS TOTAL_SALES,

        SUM(CONTRACT_VALUE_NUMERIC)
            AS TOTAL_CONTRACT_VALUE,

        SUM(CASH_COLLECTED_NUMERIC)
            AS TOTAL_CASH_COLLECTED,

        COUNT(CONTRACT_VALUE_NUMERIC)
            AS SALES_WITH_CONTRACT_VALUE

    FROM SALE_TO_OUTBOUND_CANDIDATES

    WHERE MATCH_RANK = 1

    GROUP BY OUTBOUND_ACTIVITY_ID
),

OUTBOUND_ENRICHED AS (

    /*
      Join one-row-per-outbound aggregated datasets.
    */
    SELECT
        o.OUTBOUND_DATE,
        o.REPORTING_WEEK,
        o.SETTER,
        o.SETTER_EMAIL,
        o.OUTBOUND_ACTIVITY_ID,

        o.OUTBOUND_DIALS,
        o.OUTBOUND_TAKEN,
        o.STRATEGY_CALL_BOOKED,

        COALESCE(
            st.STRATEGY_CALL_EVENTS,
            0
        ) AS STRATEGY_CALL_EVENTS,

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
            sa.TOTAL_CASH_COLLECTED,
            0
        ) AS TOTAL_CASH_COLLECTED,

        COALESCE(
            sa.SALES_WITH_CONTRACT_VALUE,
            0
        ) AS SALES_WITH_CONTRACT_VALUE

    FROM OUTBOUND_BASE o

    LEFT JOIN STRATEGY_ATTRIBUTED st
        ON o.OUTBOUND_ACTIVITY_ID =
           st.OUTBOUND_ACTIVITY_ID

    LEFT JOIN SALES_ATTRIBUTED sa
        ON o.OUTBOUND_ACTIVITY_ID =
           sa.OUTBOUND_ACTIVITY_ID
)

SELECT
    OUTBOUND_DATE,
    REPORTING_WEEK,
    SETTER,
    SETTER_EMAIL,

    SUM(OUTBOUND_DIALS)
        AS OUTBOUND_DIALS,

    SUM(OUTBOUND_TAKEN)
        AS OUTBOUND_TAKEN,

    ROUND(
        100.0 * SUM(OUTBOUND_TAKEN)
        / NULLIF(SUM(OUTBOUND_DIALS), 0),
        2
    ) AS CONNECT_RATE,

    SUM(STRATEGY_CALL_BOOKED)
        AS STRATEGY_CALL_BOOKED,

    ROUND(
        100.0 * SUM(STRATEGY_CALL_BOOKED)
        / NULLIF(SUM(OUTBOUND_DIALS), 0),
        2
    ) AS SET_RATE,

    SUM(STRATEGY_CALL_EVENTS)
        AS STRATEGY_CALL_EVENTS,

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
    ) AS AVERAGE_ORDER_VALUE,

    ROUND(
        SUM(TOTAL_CONTRACT_VALUE),
        2
    ) AS TOTAL_CONTRACT_VALUE,

    ROUND(
        SUM(TOTAL_CASH_COLLECTED),
        2
    ) AS TOTAL_CASH_COLLECTED

FROM OUTBOUND_ENRICHED

GROUP BY
    OUTBOUND_DATE,
    REPORTING_WEEK,
    SETTER,
    SETTER_EMAIL;
```

# Inspect the report

```
SELECT *
FROM GOLD.OUTBOUND_SETTER_REPORT
ORDER BY
    DIAL_DATE,
    SETTER;

```
#  Validate the report grain
```
There should be no duplicate DIAL_DATE + SETTER combinations:

SELECT
    DIAL_DATE,
    SETTER,
    COUNT(*) AS CNT
FROM GOLD.OUTBOUND_SETTER_REPORT
GROUP BY
    DIAL_DATE,
    SETTER
HAVING COUNT(*) > 1;

Expected:

0 rows

```

#  Validate top-of-funnel totals

```
SELECT
    SUM(TOTAL_OUTBOUND_CALLS) AS REPORT_OUTBOUND_CALLS,
    SUM(OUTBOUND_SET) AS REPORT_OUTBOUND_SETS
FROM GOLD.OUTBOUND_SETTER_REPORT;

```

# Validate globally from the source
```
SELECT
    COUNT(DISTINCT LEAD_ID) AS GLOBAL_UNIQUE_LEADS_TOUCHED
FROM GOLD.OUTBOUND_PROSPECT_DIALS;

```

# Validate sequence-safe shows and offers
```
SELECT
    SUM(TOTAL_CLOSER_SHOW) AS ATTRIBUTED_CLOSER_SHOWS,
    SUM(TOTAL_OFFER) AS ATTRIBUTED_OFFERS
FROM GOLD.OUTBOUND_SETTER_REPORT;
```

# Validate attributed sales and revenue

```
SELECT
    SUM(TOTAL_SALE) AS ATTRIBUTED_OUTBOUND_SALES,
    SUM(TOTAL_REVENUE) AS ATTRIBUTED_OUTBOUND_REVENUE
FROM GOLD.OUTBOUND_SETTER_REPORT;

```


# Check for impossible funnel results
```
SELECT *
FROM GOLD.OUTBOUND_SETTER_REPORT
WHERE OUTBOUND_SET > TOTAL_OUTBOUND_CALLS
   OR TOTAL_CLOSER_SHOW > OUTBOUND_SET
   OR TOTAL_OFFER > TOTAL_CLOSER_SHOW
   OR TOTAL_SALE > TOTAL_CLOSER_SHOW;

```

# reconciliation difference
```

SELECT
    COUNT(*) AS NULL_SETTER_ROWS
FROM GOLD.OUTBOUND_PROSPECT_DIALS
WHERE SETTER_CLOSER_NAME IS NULL;

and

SELECT
    COUNT(*) AS NULL_SET_ROWS
FROM GOLD.OUTBOUND_STRATEGIES_BOOKED
WHERE SETTER_CLOSER_NAME IS NULL;

```
