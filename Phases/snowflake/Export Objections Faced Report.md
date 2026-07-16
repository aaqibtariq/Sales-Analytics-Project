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
