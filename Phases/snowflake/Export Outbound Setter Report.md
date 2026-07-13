
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

CREATE OR REPLACE VIEW GOLD.OUTBOUND_SETTER_REPORT AS

WITH OUTBOUND_DIALS AS (
    /*
        Complete outbound top-of-funnel activity.
        One row per deduplicated prospecting activity.
    */
    SELECT
        ACTIVITY_ID,
        LEAD_ID,
        ACTIVITY_AT,
        ACTIVITY_AT::DATE AS DIAL_DATE,
        DEA_INTERNAL_NAME AS SETTER,
        DEA_INTERNAL_EMAIL AS SETTER_EMAIL,
        CUSTOM_ACTIVITY,
        CUSTOM_ACTIVITY_OUTCOME
    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
    WHERE CUSTOM_ACTIVITY IN (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    )
),

OUTBOUND_SETS AS (
    /*
        Successful outbound qualification events.
        Each row represents an outbound activity that scheduled
        a Strategy Call.
    */
    SELECT
        ACTIVITY_ID AS SET_ACTIVITY_ID,
        LEAD_ID,
        ACTIVITY_AT AS SET_AT,
        ACTIVITY_AT::DATE AS DIAL_DATE,
        DEA_INTERNAL_NAME AS SETTER,
        DEA_INTERNAL_EMAIL AS SETTER_EMAIL
    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
    WHERE CUSTOM_ACTIVITY IN (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    )
      AND CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
),

STRATEGY_EVENTS AS (
    /*
        Strategy Call activity events.

        Follow-up activities are not included because the validated
        Strategy Call Outcome is stored on '5) Strategy Call'.
    */
    SELECT
        ACTIVITY_ID AS STRATEGY_ACTIVITY_ID,
        LEAD_ID,
        ACTIVITY_AT AS STRATEGY_AT,
        CUSTOM_ACTIVITY_OUTCOME AS STRATEGY_CALL_OUTCOME,
        OFFER_PRESENTED
    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
),

STRATEGY_ATTRIBUTION AS (
    /*
        Assign each Strategy Call to the most recent outbound set
        for the same lead occurring before that Strategy Call.

        This prevents one Strategy Call from being attributed to
        multiple outbound bookings.
    */
    SELECT
        os.SET_ACTIVITY_ID,
        os.LEAD_ID,
        os.DIAL_DATE,
        os.SETTER,
        os.SETTER_EMAIL,

        se.STRATEGY_ACTIVITY_ID,
        se.STRATEGY_AT,
        se.STRATEGY_CALL_OUTCOME,
        se.OFFER_PRESENTED,

        CASE
            WHEN se.STRATEGY_CALL_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
            THEN 1
            ELSE 0
        END AS CLOSER_SHOW,

        CASE
            WHEN se.STRATEGY_CALL_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
            AND (
                   UPPER(TRIM(se.OFFER_PRESENTED)) = 'YES'
                OR se.STRATEGY_CALL_OUTCOME ILIKE '%offer%'
            )
            THEN 1
            ELSE 0
        END AS OFFER_FLAG

    FROM STRATEGY_EVENTS se

    INNER JOIN OUTBOUND_SETS os
        ON se.LEAD_ID = os.LEAD_ID
       AND se.STRATEGY_AT >= os.SET_AT

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY se.STRATEGY_ACTIVITY_ID
        ORDER BY
            os.SET_AT DESC,
            os.SET_ACTIVITY_ID DESC
    ) = 1
),

SALE_EVENTS AS (
    /*
        Finalized sales activity events.
    */
    SELECT
        ACTIVITY_ID AS SALE_ACTIVITY_ID,
        LEAD_ID,

        COALESCE(
            DATE_OF_SALE::TIMESTAMP_NTZ,
            ACTIVITY_AT
        ) AS SALE_AT,

        TRY_TO_DECIMAL(CONTRACT_VALUE, 18, 2) AS CONTRACTED_VALUE

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    )
),

SALE_ATTRIBUTION AS (
    /*
        A sale is valid only when a documented attended Strategy Call
        occurred before the sale.

        Each sale is assigned to the most recent attended Strategy Call.
        That Strategy Call already carries its outbound set attribution.
    */
    SELECT
        sa.SET_ACTIVITY_ID,
        sa.LEAD_ID,
        sa.DIAL_DATE,
        sa.SETTER,
        sa.SETTER_EMAIL,
        sa.STRATEGY_ACTIVITY_ID,

        sale.SALE_ACTIVITY_ID,
        sale.SALE_AT,
        sale.CONTRACTED_VALUE

    FROM SALE_EVENTS sale

    INNER JOIN STRATEGY_ATTRIBUTION sa
        ON sale.LEAD_ID = sa.LEAD_ID
       AND sa.CLOSER_SHOW = 1
       AND sale.SALE_AT >= sa.STRATEGY_AT

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY sale.SALE_ACTIVITY_ID
        ORDER BY
            sa.STRATEGY_AT DESC,
            sa.STRATEGY_ACTIVITY_ID DESC
    ) = 1
),

DIAL_METRICS AS (
    /*
        Daily activity grain required by the export model:
        DIAL_DATE + SETTER.
    */
    SELECT
        DIAL_DATE,
        SETTER,

        COUNT(DISTINCT ACTIVITY_ID) AS TOTAL_OUTBOUND_CALLS,
        COUNT(DISTINCT LEAD_ID) AS TOTAL_LEADS_TOUCHED

    FROM OUTBOUND_DIALS

    GROUP BY
        DIAL_DATE,
        SETTER
),

SET_METRICS AS (
    SELECT
        DIAL_DATE,
        SETTER,

        COUNT(DISTINCT SET_ACTIVITY_ID) AS OUTBOUND_SET

    FROM OUTBOUND_SETS

    GROUP BY
        DIAL_DATE,
        SETTER
),

STRATEGY_METRICS AS (
    SELECT
        DIAL_DATE,
        SETTER,

        COUNT(DISTINCT CASE
            WHEN CLOSER_SHOW = 1
            THEN STRATEGY_ACTIVITY_ID
        END) AS TOTAL_CLOSER_SHOW,

        COUNT(DISTINCT CASE
            WHEN OFFER_FLAG = 1
            THEN STRATEGY_ACTIVITY_ID
        END) AS TOTAL_OFFER

    FROM STRATEGY_ATTRIBUTION

    GROUP BY
        DIAL_DATE,
        SETTER
),

SALE_METRICS AS (
    SELECT
        DIAL_DATE,
        SETTER,

        COUNT(DISTINCT SALE_ACTIVITY_ID) AS TOTAL_SALE,

        SUM(CONTRACTED_VALUE) AS TOTAL_REVENUE

    FROM SALE_ATTRIBUTION

    GROUP BY
        DIAL_DATE,
        SETTER
)

SELECT
    d.DIAL_DATE,

    d.SETTER,

    d.TOTAL_OUTBOUND_CALLS,

    d.TOTAL_LEADS_TOUCHED,

    COALESCE(sm.OUTBOUND_SET, 0) AS OUTBOUND_SET,

    COALESCE(stm.TOTAL_CLOSER_SHOW, 0) AS TOTAL_CLOSER_SHOW,

    COALESCE(stm.TOTAL_OFFER, 0) AS TOTAL_OFFER,

    COALESCE(slm.TOTAL_SALE, 0) AS TOTAL_SALE,

    ROUND(
        100.0 * COALESCE(sm.OUTBOUND_SET, 0)
        / NULLIF(d.TOTAL_OUTBOUND_CALLS, 0),
        2
    ) AS DIAL_TO_SET_RATE,

    ROUND(
        100.0 * COALESCE(stm.TOTAL_CLOSER_SHOW, 0)
        / NULLIF(COALESCE(sm.OUTBOUND_SET, 0), 0),
        2
    ) AS SET_TO_SHOW_RATE,

    ROUND(
        100.0 * COALESCE(slm.TOTAL_SALE, 0)
        / NULLIF(COALESCE(stm.TOTAL_CLOSER_SHOW, 0), 0),
        2
    ) AS SHOW_TO_SALE_RATE,

    ROUND(
        COALESCE(slm.TOTAL_REVENUE, 0),
        2
    ) AS TOTAL_REVENUE,

    ROUND(
        COALESCE(slm.TOTAL_REVENUE, 0)
        / NULLIF(COALESCE(slm.TOTAL_SALE, 0), 0),
        2
    ) AS AVERAGE_ORDER_VALUE

FROM DIAL_METRICS d

LEFT JOIN SET_METRICS sm
    ON d.DIAL_DATE = sm.DIAL_DATE
   AND EQUAL_NULL(d.SETTER, sm.SETTER)

LEFT JOIN STRATEGY_METRICS stm
    ON d.DIAL_DATE = stm.DIAL_DATE
   AND EQUAL_NULL(d.SETTER, stm.SETTER)

LEFT JOIN SALE_METRICS slm
    ON d.DIAL_DATE = slm.DIAL_DATE
   AND EQUAL_NULL(d.SETTER, slm.SETTER);

LEFT JOIN GOLD.SALES_DETAILS sd
    ON osb.LEAD_ID = sd.LEAD_ID
   AND sd.DATE_OF_SALE >= osb.PROSPECT_CALL_DATE;

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
