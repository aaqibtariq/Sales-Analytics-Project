
# Validate Strategy outcomes

```

SELECT
    STRATEGY_CALL_OUTCOME,
    COUNT(*) AS TOTAL
FROM GOLD.ALL_STRATEGIES_DETAILS
GROUP BY STRATEGY_CALL_OUTCOME
ORDER BY TOTAL DESC;
```
# Validate Sales
```
SELECT
    COUNT(*) AS SALES,
    SUM(TRY_TO_DECIMAL(CONTRACTED_VALUE,18,2)) AS TOTAL_VALUE,
    AVG(TRY_TO_DECIMAL(CONTRACTED_VALUE,18,2)) AS AVG_VALUE,
    SUM(TRY_TO_DECIMAL(CASH_COLLECTED,18,2)) AS CASH_COLLECTED
FROM GOLD.SALES_DETAILS;
```
# Validate Closer mapping
```
SELECT
    DEA_INTERNAL_NAME,
    COUNT(*) AS STRATEGY_CALLS
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY='5) Strategy Call'
GROUP BY DEA_INTERNAL_NAME
ORDER BY STRATEGY_CALLS DESC;

```

# create report

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW GOLD.CLOSER_REPORT AS

WITH STRATEGY_CALLS AS (
    /*
        One row per deduplicated main Strategy Call.

        We use the Silver business-ready summary because it contains
        ACTIVITY_ID, which is required for safe event attribution.
    */
    SELECT
        ACTIVITY_ID AS STRATEGY_ACTIVITY_ID,
        LEAD_ID,
        ACTIVITY_AT AS STRATEGY_AT,
        DATE_TRUNC('MONTH', ACTIVITY_AT)::DATE AS CALL_YEAR_MONTH,

        CLOSER_NAME,

        CUSTOM_ACTIVITY_OUTCOME AS STRATEGY_CALL_OUTCOME,

        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
            THEN 1
            ELSE 0
        END AS SHOW_FLAG

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
),

SALE_EVENTS AS (
    /*
        Finalized downstream sale records.
    */
    SELECT
        ACTIVITY_ID AS SALE_ACTIVITY_ID,
        LEAD_ID,

        COALESCE(
            DATE_OF_SALE::TIMESTAMP_NTZ,
            ACTIVITY_AT
        ) AS SALE_AT,

        TRY_TO_DECIMAL(CONTRACT_VALUE, 18, 2) AS CONTRACTED_VALUE,
        TRY_TO_DECIMAL(CASH_COLLECTED, 18, 2) AS CASH_COLLECTED

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    )
),

SALE_ATTRIBUTION AS (
    /*
        Assign each sale to the most recent attended Strategy Call
        for the same lead occurring before the sale.

        This prevents one sale from being counted against multiple
        Strategy Calls or multiple closers.
    */
    SELECT
        sc.STRATEGY_ACTIVITY_ID,
        sc.LEAD_ID,
        sc.CALL_YEAR_MONTH,
        sc.CLOSER_NAME,

        se.SALE_ACTIVITY_ID,
        se.SALE_AT,
        se.CONTRACTED_VALUE,
        se.CASH_COLLECTED

    FROM SALE_EVENTS se

    INNER JOIN STRATEGY_CALLS sc
        ON se.LEAD_ID = sc.LEAD_ID
       AND sc.SHOW_FLAG = 1
       AND se.SALE_AT >= sc.STRATEGY_AT

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY se.SALE_ACTIVITY_ID
        ORDER BY
            sc.STRATEGY_AT DESC,
            sc.STRATEGY_ACTIVITY_ID DESC
    ) = 1
),

STRATEGY_METRICS AS (
    SELECT
        CLOSER_NAME,
        CALL_YEAR_MONTH,

        COUNT(DISTINCT STRATEGY_ACTIVITY_ID) AS CALL_BOOKED,

        COUNT(DISTINCT CASE
            WHEN STRATEGY_CALL_OUTCOME = '2. Admin Cancel'
            THEN STRATEGY_ACTIVITY_ID
        END) AS ADMIN_CANCEL,

        COUNT(DISTINCT CASE
            WHEN STRATEGY_CALL_OUTCOME IN (
                '7. Cancel- Nurture',
                '8. Cancel- Nurture'
            )
            THEN STRATEGY_ACTIVITY_ID
        END) AS CANCEL_NURTURE,

        COUNT(DISTINCT CASE
            WHEN STRATEGY_CALL_OUTCOME = '3. Cancel- Not Interested'
            THEN STRATEGY_ACTIVITY_ID
        END) AS CANCEL_NOT_INTEREST,

        COUNT(DISTINCT CASE
            WHEN STRATEGY_CALL_OUTCOME IN (
                '2. Admin Cancel',
                '3. Cancel- Not Interested',
                '7. Cancel- Nurture',
                '8. Cancel- Nurture'
            )
            THEN STRATEGY_ACTIVITY_ID
        END) AS TOTAL_CANCEL,

        COUNT(DISTINCT CASE
            WHEN STRATEGY_CALL_OUTCOME IN (
                '3. No Show',
                '4. No Show'
            )
            THEN STRATEGY_ACTIVITY_ID
        END) AS NO_SHOW,

        COUNT(DISTINCT CASE
            WHEN SHOW_FLAG = 1
            THEN STRATEGY_ACTIVITY_ID
        END) AS STRTGY_CALL_SHW,

        COUNT(DISTINCT CASE
            WHEN STRATEGY_CALL_OUTCOME = '7. Lost'
            THEN STRATEGY_ACTIVITY_ID
        END) AS LOST

    FROM STRATEGY_CALLS

    GROUP BY
        CLOSER_NAME,
        CALL_YEAR_MONTH
),

SALE_METRICS AS (
    SELECT
        CLOSER_NAME,
        CALL_YEAR_MONTH,

        COUNT(DISTINCT SALE_ACTIVITY_ID) AS SALE,

        AVG(CONTRACTED_VALUE) AS AVG_VAUE,

        SUM(CASH_COLLECTED) AS CASH_COLLECTED

    FROM SALE_ATTRIBUTION

    GROUP BY
        CLOSER_NAME,
        CALL_YEAR_MONTH
)

SELECT
    sm.CLOSER_NAME,
    sm.CALL_YEAR_MONTH,

    sm.CALL_BOOKED,
    sm.ADMIN_CANCEL,
    sm.CANCEL_NURTURE,
    sm.CANCEL_NOT_INTEREST,
    sm.TOTAL_CANCEL,
    sm.NO_SHOW,
    sm.STRTGY_CALL_SHW,
    sm.LOST,

    COALESCE(slm.SALE, 0) AS SALE,

    ROUND(
        slm.AVG_VAUE,
        2
    ) AS AVG_VAUE,

    ROUND(
        COALESCE(slm.CASH_COLLECTED, 0),
        2
    ) AS CASH_COLLECTED

FROM STRATEGY_METRICS sm

LEFT JOIN SALE_METRICS slm
    ON sm.CALL_YEAR_MONTH = slm.CALL_YEAR_MONTH
   AND EQUAL_NULL(sm.CLOSER_NAME, slm.CLOSER_NAME);

```

# Inspect the report
```
SELECT *
FROM GOLD.CLOSER_REPORT
ORDER BY
    CALL_YEAR_MONTH,
    CLOSER_NAME;

```

# Validate the report grain

```
SELECT
    CLOSER_NAME,
    CALL_YEAR_MONTH,
    COUNT(*) AS CNT
FROM GOLD.CLOSER_REPORT
GROUP BY
    CLOSER_NAME,
    CALL_YEAR_MONTH
HAVING COUNT(*) > 1;
```

# Validate total Strategy Calls
```
SELECT
    SUM(CALL_BOOKED) AS REPORT_CALL_BOOKED
FROM GOLD.CLOSER_REPORT;

```

# Reconcile against the source

```
SELECT COUNT(*) AS SOURCE_CALL_BOOKED
FROM SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '5) Strategy Call';
```


# Validate outcome totals
```
SELECT
    SUM(ADMIN_CANCEL) AS ADMIN_CANCEL,
    SUM(CANCEL_NURTURE) AS CANCEL_NURTURE,
    SUM(CANCEL_NOT_INTEREST) AS CANCEL_NOT_INTEREST,
    SUM(TOTAL_CANCEL) AS TOTAL_CANCEL,
    SUM(NO_SHOW) AS NO_SHOW,
    SUM(STRTGY_CALL_SHW) AS STRATEGY_CALL_SHOW,
    SUM(LOST) AS LOST
FROM GOLD.CLOSER_REPORT;

```


# Validate TOTAL_CANCEL
```
SELECT
    SUM(TOTAL_CANCEL) AS TOTAL_CANCEL,
    SUM(ADMIN_CANCEL)
        + SUM(CANCEL_NURTURE)
        + SUM(CANCEL_NOT_INTEREST) AS COMPONENT_TOTAL
FROM GOLD.CLOSER_REPORT;
```


#  Validate sales and financials
```
SELECT
    SUM(SALE) AS ATTRIBUTED_SALES,
    SUM(CASH_COLLECTED) AS ATTRIBUTED_CASH_COLLECTED
FROM GOLD.CLOSER_REPORT;
```


# Validate no impossible results
```
SELECT *
FROM GOLD.CLOSER_REPORT
WHERE TOTAL_CANCEL > CALL_BOOKED
   OR NO_SHOW > CALL_BOOKED
   OR STRTGY_CALL_SHW > CALL_BOOKED
   OR LOST > STRTGY_CALL_SHW
   OR SALE > STRTGY_CALL_SHW;
```

# final Reconcile against the source


```

SELECT
    COUNT(*) AS MISSING_REPORT_ROWS
FROM GOLD.ALL_STRATEGIES_DETAILS
WHERE (
        CLOSER_NAME IS NULL
        OR DATE_OF_STRATEGY_CALL IS NULL
      );

      SELECT
    COUNT(*) AS SOURCE_ROWS,
    COUNT(DISTINCT ACTIVITY_ID) AS DISTINCT_ACTIVITY_IDS
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '5) Strategy Call';

SELECT
    ACTIVITY_ID,
    COUNT(*) AS CNT
FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
GROUP BY ACTIVITY_ID
HAVING COUNT(*) > 1
ORDER BY CNT DESC;


There are 6 duplicated Strategy Call ACTIVITY_IDs:

ACTIVITY_ID	Count
acti_AKWW76rAJxJzuWmRh9hgzNpLUFyatRZwXSRBaq2nP5a	3
acti_9e60lro7vzFrSEQjrrJMKgPHEEtvWo8sOBxNXzSKt3k	2
acti_6utUlPV90GcMQZlAsZvh4wStI2LVyUZdwy3r9iSDDBT	2
acti_vcOcnIgFA337eRidbQfiltpIhlWiChOh2HN567jQKz2	2
acti_v0km5ahAYWfEmDL8BXQ4S9hQlLRIDjt7mK2krZdKBFw	2
(one additional duplicated ID)	2

This produces:

One activity duplicated 3 times → contributes 2 extra rows
Five activities duplicated 2 times → contribute 5 extra rows

Total extra rows:

2 + 5 = 7

Exactly matching:

4,128 raw rows
-
4,121 distinct ACTIVITY_ID
=
7 duplicate rows

This completely explains the reconciliation.

The report uses:

COUNT(DISTINCT STRATEGY_ACTIVITY_ID)

which counts business events.

The raw validation query used:

COUNT(*)

which counts physical rows.

Because the source contains duplicated Strategy Call events, the report is correct to report:

CALL_BOOKED = 4,121

rather than:

4,128

Otherwise, KPIs like Show Rate, Lost Rate, and Sale Rate would all be inflated.
```


