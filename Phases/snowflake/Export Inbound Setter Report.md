```
The requirements define:
inbound_booked as total Triage Calls logged.
inbound_taken as Triage Calls where the lead attended.
Triage non-attended outcomes as 6. No Show, 7. Reschedule, and 8. Cancel.
triage_set_rate as the percentage of Triage Calls resulting in 1. Strategy Call Scheduled.
Strategy Calls are attended only when their outcome is not a documented cancellation/no-show outcome.

```

# Validate inbound Triage metrics
```
Run this first:
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

SELECT
    COUNT(*) AS INBOUND_BOOKED,

    COUNT_IF(
        CUSTOM_ACTIVITY_OUTCOME IS NOT NULL
        AND CUSTOM_ACTIVITY_OUTCOME NOT IN (
            '6. No Show',
            '7. Reschedule',
            '8. Cancel'
        )
    ) AS INBOUND_TAKEN,

    COUNT_IF(
        CUSTOM_ACTIVITY_OUTCOME = '1. Strategy Call Scheduled'
    ) AS TRIAGE_SETS,

    ROUND(
        100.0 * COUNT_IF(
            CUSTOM_ACTIVITY_OUTCOME IS NOT NULL
            AND CUSTOM_ACTIVITY_OUTCOME NOT IN (
                '6. No Show',
                '7. Reschedule',
                '8. Cancel'
            )
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS SHOW_RATE,

    ROUND(
        100.0 * COUNT_IF(
            CUSTOM_ACTIVITY_OUTCOME = '1. Strategy Call Scheduled'
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS TRIAGE_SET_RATE

FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

WHERE CUSTOM_ACTIVITY = '3) Triage Call';

```
# Confirm outcome classification
```
SELECT
    CUSTOM_ACTIVITY_OUTCOME,

    CASE
        WHEN CUSTOM_ACTIVITY_OUTCOME IN (
            '6. No Show',
            '7. Reschedule',
            '8. Cancel'
        )
            THEN 'NOT_TAKEN'

        WHEN CUSTOM_ACTIVITY_OUTCOME IS NULL
            THEN 'MISSING_OUTCOME'

        ELSE 'TAKEN'
    END AS TRIAGE_ATTENDANCE_CLASS,

    COUNT(*) AS TOTAL_ROWS

FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

WHERE CUSTOM_ACTIVITY = '3) Triage Call'

GROUP BY
    CUSTOM_ACTIVITY_OUTCOME,
    TRIAGE_ATTENDANCE_CLASS

ORDER BY TOTAL_ROWS DESC;
Expected classification:
NOT_TAKEN
6. No Show
7. Reschedule
8. Cancel
All other populated Triage outcomes are treated as taken because the SME only identifies those three
 as non-progression/non-attended states.

```

# Validate setter attribution
```
SELECT
    COUNT(*) AS TOTAL_TRIAGE_CALLS,

    COUNT_IF(
        DEA_INTERNAL_EMAIL IS NOT NULL
    ) AS SETTER_EMAIL_ROWS,

    COUNT_IF(
        DEA_INTERNAL_NAME IS NOT NULL
    ) AS SETTER_NAME_ROWS,

    COUNT_IF(
        CUSTOM_ACTIVITY_OUTCOME = '1. Strategy Call Scheduled'
    ) AS STRATEGY_CALL_BOOKED_ROWS

FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

WHERE CUSTOM_ACTIVITY = '3) Triage Call';
For this report, the Triage Call owner will be the setter:
setter = DEA_INTERNAL_NAME
We should preserve null setters when the source user mapping is unavailable.
```
# Validate Strategy Call attendance logic
```
SELECT
    STRATEGY_CALL_OUTCOME,

    CASE
        WHEN STRATEGY_CALL_OUTCOME IN (
            '4. No Show',
            '3. Cancel- Not Interested',
            '2. Admin Cancel',
            '8. Cancel- Nurture',
            '3. No Show',
            '7. Cancel- Nurture'
        )
            THEN 'NOT_TAKEN'

        WHEN STRATEGY_CALL_OUTCOME IN (
            '1. Follow Up',
            '5. Sale',
            '6. Sale',
            '7. Lost'
        )
            THEN 'TAKEN'

        ELSE 'UNCLASSIFIED'
    END AS STRATEGY_ATTENDANCE_CLASS,

    COUNT(*) AS TOTAL_ROWS

FROM GOLD.ALL_STRATEGIES_DETAILS

WHERE CUSTOM_ACTIVITY = '5) Strategy Call'

GROUP BY
    STRATEGY_CALL_OUTCOME,
    STRATEGY_ATTENDANCE_CLASS

ORDER BY TOTAL_ROWS DESC;

```
The requirements explicitly identify the valid attended Strategy Call outcomes and the cancellation/no-show exclusions.

# Update the classification

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

SELECT
    STRATEGY_CALL_OUTCOME,

    CASE
        WHEN STRATEGY_CALL_OUTCOME IN (
            '4. No Show',
            '5. Reschedule',
            '3. Cancel- Not Interested',
            '2. Admin Cancel',
            '8. Cancel- Nurture',
            '3. No Show',
            '7. Cancel- Nurture'
        )
            THEN 'NOT_TAKEN'

        WHEN STRATEGY_CALL_OUTCOME IN (
            '1. Follow Up',
            '5. Sale',
            '6. Sale',
            '7. Lost'
        )
            THEN 'TAKEN'

        WHEN STRATEGY_CALL_OUTCOME IS NULL
            THEN 'MISSING_OUTCOME'

        ELSE 'UNCLASSIFIED'
    END AS STRATEGY_ATTENDANCE_CLASS,

    COUNT(*) AS TOTAL_ROWS

FROM GOLD.ALL_STRATEGIES_DETAILS

WHERE CUSTOM_ACTIVITY = '5) Strategy Call'

GROUP BY
    STRATEGY_CALL_OUTCOME,
    STRATEGY_ATTENDANCE_CLASS

ORDER BY
    STRATEGY_ATTENDANCE_CLASS,
    TOTAL_ROWS DESC;

Use this full validation query with 5. Reschedule classified as NOT_TAKEN:

```

# For a total summary

```
SELECT
    CASE
        WHEN STRATEGY_CALL_OUTCOME IN (
            '4. No Show',
            '5. Reschedule',
            '3. Cancel- Not Interested',
            '2. Admin Cancel',
            '8. Cancel- Nurture',
            '3. No Show',
            '7. Cancel- Nurture'
        )
            THEN 'NOT_TAKEN'

        WHEN STRATEGY_CALL_OUTCOME IN (
            '1. Follow Up',
            '5. Sale',
            '6. Sale',
            '7. Lost'
        )
            THEN 'TAKEN'

        WHEN STRATEGY_CALL_OUTCOME IS NULL
            THEN 'MISSING_OUTCOME'

        ELSE 'UNCLASSIFIED'
    END AS STRATEGY_ATTENDANCE_CLASS,

    COUNT(*) AS TOTAL_ROWS

FROM GOLD.ALL_STRATEGIES_DETAILS

WHERE CUSTOM_ACTIVITY = '5) Strategy Call'

GROUP BY STRATEGY_ATTENDANCE_CLASS

ORDER BY STRATEGY_ATTENDANCE_CLASS;


Once that shows no UNCLASSIFIED outcomes, the Strategy Call attendance logic is ready for the Inbound Setter Report.

```

# Include rescheuke as sperate cat

```
  SELECT
    CASE
    WHEN STRATEGY_CALL_OUTCOME IN (
        '4. No Show',
        '3. Cancel- Not Interested',
        '2. Admin Cancel',
        '8. Cancel- Nurture',
        '3. No Show',
        '7. Cancel- Nurture'
    )
        THEN 'NOT_TAKEN'

    WHEN STRATEGY_CALL_OUTCOME IN (
        '1. Follow Up',
        '5. Sale',
        '6. Sale',
        '7. Lost'
    )
        THEN 'TAKEN'

    WHEN STRATEGY_CALL_OUTCOME = '5. Reschedule'
        THEN 'RESCHEDULE'

    WHEN STRATEGY_CALL_OUTCOME IS NULL
        THEN 'MISSING_OUTCOME'

    ELSE 'UNCLASSIFIED'

    END AS STRATEGY_ATTENDANCE_CLASS,

    COUNT(*) AS TOTAL_ROWS

FROM GOLD.ALL_STRATEGIES_DETAILS

WHERE CUSTOM_ACTIVITY = '5) Strategy Call'

GROUP BY STRATEGY_ATTENDANCE_CLASS

ORDER BY STRATEGY_ATTENDANCE_CLASS;

```

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

Expected:
1125

because it should reconcile to GOLD.INBOUND_STRATEGIES_BOOKED.
```
# Validate Strategy Calls booked
```
SELECT
SUM(STRATEGY_CALL_BOOKED)
FROM GOLD.INBOUND_SETTER_REPORT;

Expected:
1125
```

# Validate sales
```
SELECT
SUM(TOTAL_SALES)
FROM GOLD.INBOUND_SETTER_REPORT;
Expected:
270
which should reconcile with GOLD.SALES_DETAILS.

```
