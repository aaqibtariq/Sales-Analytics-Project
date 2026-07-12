# Create table

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW GOLD.OUTBOUND_PROSPECT_DIALS AS
SELECT
    LEAD_ID,

    ACTIVITY_AT::DATE AS ACTIVITY_LOG_DATE,

    YEAR(ACTIVITY_AT) || '-' ||
    LPAD(WEEKISO(ACTIVITY_AT), 2, '0') AS PROSPECT_YEAR_WEEK,

    CUSTOM_ACTIVITY,

    -- CRM record lifecycle status, such as published or draft
    STATUS_CHANGE AS STATUS,

    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,

    DEA_INTERNAL_EMAIL AS SETTER_CLOSER_EMAIL,
    DEA_INTERNAL_NAME AS SETTER_CLOSER_NAME

FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

WHERE CUSTOM_ACTIVITY IN (
    '1) Prospecting Activity',
    '2) Prospecting Follow Up'
);

```

#  Validate total rows
```
SELECT COUNT(*) AS OUTBOUND_PROSPECT_DIALS_COUNT
FROM GOLD.OUTBOUND_PROSPECT_DIALS;
Expected:
11,432
Calculation:
10,046 Prospecting Activity
+ 1,386 Prospecting Follow Up
= 11,432

```

# Validate source reconciliation
```
SELECT
    CUSTOM_ACTIVITY,
    COUNT(*) AS TOTAL_ROWS
FROM GOLD.OUTBOUND_PROSPECT_DIALS
GROUP BY CUSTOM_ACTIVITY
ORDER BY CUSTOM_ACTIVITY;
Expected:
1) Prospecting Activity     10,046
2) Prospecting Follow Up     1,386

```
# Validate outcome distribution
```
SELECT
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME,
    COUNT(*) AS TOTAL_ROWS
FROM GOLD.OUTBOUND_PROSPECT_DIALS
GROUP BY
    CUSTOM_ACTIVITY,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    CUSTOM_ACTIVITY_OUTCOME
ORDER BY
    CUSTOM_ACTIVITY,
    TOTAL_ROWS DESC;
You should see outbound outcomes such as:
1. Triage Booked
2. Strategy Call Scheduled
3. Follow Up
4. Unqualified
6. Not Interested
Null outcomes should remain visible because they represent attempted or incomplete prospecting activity.

```
# Validate outbound sets
```
SELECT
    COUNT(*) AS OUTBOUND_SET_ROWS,
    COUNT(DISTINCT LEAD_ID) AS OUTBOUND_SET_LEADS
FROM GOLD.OUTBOUND_PROSPECT_DIALS
WHERE CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled';
Expected:
OUTBOUND_SET_ROWS = 2,408
The unique lead count should reconcile closely with OUTBOUND_STRATEGIES_BOOKED.
```
# Reconcile with the booked view
```
SELECT
    (
        SELECT COUNT(*)
        FROM GOLD.OUTBOUND_PROSPECT_DIALS
        WHERE CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
    ) AS DIAL_VIEW_BOOKED_ROWS,

    (
        SELECT COUNT(*)
        FROM GOLD.OUTBOUND_STRATEGIES_BOOKED
    ) AS BOOKED_VIEW_ROWS;
Expected:
2,408
2,408

```
# Validate unique leads touched
```
SELECT
    COUNT(*) AS TOTAL_OUTBOUND_ACTIVITIES,
    COUNT(DISTINCT LEAD_ID) AS UNIQUE_LEADS_TOUCHED
FROM GOLD.OUTBOUND_PROSPECT_DIALS;
This becomes the base for:
Total Outbound Calls
Total Leads Touched

```
# Validate weekly reporting
```
SELECT
    PROSPECT_YEAR_WEEK,
    COUNT(*) AS TOTAL_OUTBOUND_ACTIVITIES,
    COUNT(DISTINCT LEAD_ID) AS UNIQUE_LEADS_TOUCHED,
    COUNT_IF(
        CUSTOM_ACTIVITY_OUTCOME = '2. Strategy Call Scheduled'
    ) AS OUTBOUND_SETS
FROM GOLD.OUTBOUND_PROSPECT_DIALS
GROUP BY PROSPECT_YEAR_WEEK
ORDER BY PROSPECT_YEAR_WEEK;

```


