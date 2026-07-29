# create report

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW GOLD.INBOUND_SETTER_REPORT AS

WITH TRIAGE AS (

    SELECT
        LEAD_ID,
        TRIAGE_CALL_DATE AS TRIAGE_DATE,
        SETTER_CLOSER_NAME AS SETTER,

        TRIAGE_CALL_OUTCOME,

        CASE
            WHEN TRIAGE_CALL_OUTCOME NOT IN (
                '6. No Show',
                '7. Reschedule',
                '8. Cancel'
            )
            THEN 1
            ELSE 0
        END AS INBOUND_TAKEN,

        STRATEGY_CALL_BOOKED

    FROM GOLD.INBOUND_STRATEGIES_BOOKED
),

STRATEGY AS (

    SELECT
        LEAD_ID,

        CASE
            WHEN STRATEGY_CALL_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
            THEN 1
            ELSE 0
        END AS STRATEGY_CALL_TAKEN,

        CASE
            WHEN OFFER_PRESENTED = 'Yes'
            THEN 1
            ELSE 0
        END AS OFFER_PRESENTED

    FROM GOLD.ALL_STRATEGIES_DETAILS
),

SALES AS (

    SELECT
        LEAD_ID,

        1 AS TOTAL_SALE,

        CONTRACTED_VALUE

    FROM GOLD.SALES_DETAILS
)

SELECT

    t.TRIAGE_DATE,

    t.SETTER,

    COUNT(*) AS INBOUND_BOOKED,

    SUM(t.INBOUND_TAKEN) AS INBOUND_TAKEN,

    ROUND(
        100 * SUM(t.INBOUND_TAKEN) / NULLIF(COUNT(*),0),
        2
    ) AS SHOW_RATE,

    ROUND(
        100 * SUM(t.STRATEGY_CALL_BOOKED) / NULLIF(COUNT(*),0),
        2
    ) AS TRIAGE_SET_RATE,

    SUM(t.STRATEGY_CALL_BOOKED) AS STRATEGY_CALL_BOOKED,

    SUM(COALESCE(s.STRATEGY_CALL_TAKEN,0)) AS STRATEGY_CALL_TAKEN,

    ROUND(
        100 *
        SUM(COALESCE(s.OFFER_PRESENTED,0))
        /
        NULLIF(SUM(COALESCE(s.STRATEGY_CALL_TAKEN,0)),0),
        2
    ) AS OFFER_RATE,

    SUM(COALESCE(sa.TOTAL_SALE,0)) AS TOTAL_SALES,

    ROUND(
        100 *
        SUM(COALESCE(sa.TOTAL_SALE,0))
        /
        NULLIF(SUM(COALESCE(s.STRATEGY_CALL_TAKEN,0)),0),
        2
    ) AS SALE_RATE,

    ROUND(
        AVG(sa.CONTRACTED_VALUE),
        2
    ) AS AVERAGE_ORDER_VALUE

FROM TRIAGE t

LEFT JOIN STRATEGY s
ON t.LEAD_ID = s.LEAD_ID

LEFT JOIN SALES sa
ON t.LEAD_ID = sa.LEAD_ID

GROUP BY

    t.TRIAGE_DATE,
    t.SETTER;
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
