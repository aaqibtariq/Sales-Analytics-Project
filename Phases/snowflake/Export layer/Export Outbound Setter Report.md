# create report

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


# validation 

````


SELECT
    SUM(OUTBOUND_DIALS)
        AS OUTBOUND_DIALS,

    SUM(OUTBOUND_TAKEN)
        AS OUTBOUND_TAKEN,

    SUM(STRATEGY_CALL_BOOKED)
        AS STRATEGY_CALL_BOOKED,

    ROUND(
        100.0 * SUM(OUTBOUND_TAKEN)
        / NULLIF(SUM(OUTBOUND_DIALS), 0),
        2
    ) AS OVERALL_CONNECT_RATE,

    ROUND(
        100.0 * SUM(STRATEGY_CALL_BOOKED)
        / NULLIF(SUM(OUTBOUND_DIALS), 0),
        2
    ) AS OVERALL_SET_RATE

FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT;


SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY IN (
            '1) Prospecting Activity',
            '2) Prospecting Follow Up'
        )
    ) AS SILVER_OUTBOUND_ROWS,

    (
        SELECT SUM(OUTBOUND_DIALS)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS REPORT_OUTBOUND_ROWS,

    (
        SELECT COUNT_IF(
            CUSTOM_ACTIVITY_OUTCOME =
                '2. Strategy Call Scheduled'
        )
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY IN (
            '1) Prospecting Activity',
            '2) Prospecting Follow Up'
        )
    ) AS SILVER_STRATEGY_BOOKED,

    (
        SELECT SUM(STRATEGY_CALL_BOOKED)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS REPORT_STRATEGY_BOOKED;

    SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS
    ) AS GOLD_PROSPECT_DIALS,

    (
        SELECT SUM(OUTBOUND_DIALS)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS REPORT_PROSPECT_DIALS,

    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED
    ) AS GOLD_STRATEGIES_BOOKED,

    (
        SELECT SUM(STRATEGY_CALL_BOOKED)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS REPORT_STRATEGIES_BOOKED;


    SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS
    ) AS GOLD_PROSPECT_DIALS,

    (
        SELECT SUM(OUTBOUND_DIALS)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS REPORT_PROSPECT_DIALS,

    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED
    ) AS GOLD_STRATEGIES_BOOKED,

    (
        SELECT SUM(STRATEGY_CALL_BOOKED)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS REPORT_STRATEGIES_BOOKED;


    SELECT
    COUNT_IF(
        CONNECT_RATE < 0 OR CONNECT_RATE > 100
    ) AS INVALID_CONNECT_RATE_ROWS,

    COUNT_IF(
        SET_RATE < 0 OR SET_RATE > 100
    ) AS INVALID_SET_RATE_ROWS,

    COUNT_IF(
        OFFER_RATE < 0 OR OFFER_RATE > 100
    ) AS INVALID_OFFER_RATE_ROWS,

    COUNT_IF(
        SALE_RATE < 0 OR SALE_RATE > 100
    ) AS INVALID_SALE_RATE_ROWS

FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT;


SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.GOLD.SALES_DETAILS
    ) AS TOTAL_SALES_SOURCE,

    (
        SELECT SUM(TOTAL_SALES)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS SALES_ATTRIBUTED_TO_OUTBOUND;


    SELECT
    SUM(STRATEGY_CALL_EVENTS)
        AS STRATEGY_EVENTS_ATTRIBUTED,

    SUM(STRATEGY_CALL_TAKEN)
        AS STRATEGY_CALLS_TAKEN,

    SUM(OFFERS_PRESENTED)
        AS OFFERS_PRESENTED

FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT;

SELECT *
FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
ORDER BY
    OUTBOUND_DATE DESC,
    OUTBOUND_DIALS DESC,
    SETTER;




    SELECT
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

    SUM(TOTAL_SALES)
        AS TOTAL_SALES,

    ROUND(
        SUM(TOTAL_CONTRACT_VALUE),
        2
    ) AS TOTAL_CONTRACT_VALUE

FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT

GROUP BY
    SETTER,
    SETTER_EMAIL

ORDER BY
    OUTBOUND_DIALS DESC;



SELECT
    COUNT_IF(
        CONNECT_RATE < 0 OR CONNECT_RATE > 100
    ) AS INVALID_CONNECT_RATE_ROWS,

    COUNT_IF(
        SET_RATE < 0 OR SET_RATE > 100
    ) AS INVALID_SET_RATE_ROWS,

    COUNT_IF(
        OFFER_RATE < 0 OR OFFER_RATE > 100
    ) AS INVALID_OFFER_RATE_ROWS,

    COUNT_IF(
        SALE_RATE < 0 OR SALE_RATE > 100
    ) AS INVALID_SALE_RATE_ROWS
FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT;


```

# UPDATE

```
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW
SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME AS

WITH OUTBOUND_ACTIVITIES_DEDUP AS (

    /*
        Keep one latest version of each outbound activity.

        Valid outbound activity types confirmed in Silver:
            1) Prospecting Activity
            2) Prospecting Follow Up
    */

    SELECT
        ACTIVITY_ID,
        LEAD_ID,

        ACTIVITY_AT::DATE AS DIAL_DATE,

        COALESCE(
            NULLIF(TRIM(DEA_INTERNAL_NAME), ''),
            'UNMAPPED SETTER'
        ) AS SETTER,

        NULLIF(
            TRIM(DEA_INTERNAL_EMAIL),
            ''
        ) AS SETTER_EMAIL

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    )

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ACTIVITY_ID
        ORDER BY
            DATE_UPDATED DESC NULLS LAST,
            UPDATE_DATE DESC NULLS LAST,
            INSERT_DATE DESC NULLS LAST,
            ACTIVITY_AT DESC NULLS LAST
    ) = 1
),

LEADS_TOUCHED AS (

    /*
        Count unique leads contacted by each setter on each date.

        A lead can have multiple outbound activity records on the same
        date, but it counts as only one lead touched for that setter/date.
    */

    SELECT
        DIAL_DATE,
        SETTER,
        SETTER_EMAIL,

        COUNT(DISTINCT LEAD_ID)
            AS TOTAL_LEADS_TOUCHED

    FROM OUTBOUND_ACTIVITIES_DEDUP

    GROUP BY
        DIAL_DATE,
        SETTER,
        SETTER_EMAIL
),

DETAILED_REPORT AS (

    /*
        Convert the validated detailed Outbound Setter Report metrics
        into the exact terminology required by the SME data model.
    */

    SELECT
        OUTBOUND_DATE AS DIAL_DATE,

        COALESCE(
            NULLIF(TRIM(SETTER), ''),
            'UNMAPPED SETTER'
        ) AS SETTER,

        NULLIF(
            TRIM(SETTER_EMAIL),
            ''
        ) AS SETTER_EMAIL,

        OUTBOUND_DIALS
            AS TOTAL_OUTBOUND_CALLS,

        STRATEGY_CALL_BOOKED
            AS OUTBOUND_SET,

        STRATEGY_CALL_TAKEN
            AS TOTAL_CLOSER_SHOW,

        OFFERS_PRESENTED
            AS TOTAL_OFFER,

        TOTAL_SALES
            AS TOTAL_SALE,

        /*
            Dial-to-set rate:
            Strategy Calls booked ÷ outbound calls
        */
        ROUND(
            100.0
            * STRATEGY_CALL_BOOKED
            / NULLIF(OUTBOUND_DIALS, 0),
            2
        ) AS DIAL_TO_SET_RATE,

        /*
            Set-to-show rate:
            Attended Strategy Calls ÷ Strategy Calls booked
        */
        ROUND(
            100.0
            * STRATEGY_CALL_TAKEN
            / NULLIF(STRATEGY_CALL_BOOKED, 0),
            2
        ) AS SET_TO_SHOW_RATE,

        /*
            Show-to-sale rate:
            Sales ÷ attended Strategy Calls
        */
        ROUND(
            100.0
            * TOTAL_SALES
            / NULLIF(STRATEGY_CALL_TAKEN, 0),
            2
        ) AS SHOW_TO_SALE_RATE,

        TOTAL_CONTRACT_VALUE
            AS TOTAL_REVENUE,

        AVERAGE_ORDER_VALUE

    FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
)

SELECT
    report.DIAL_DATE,
    report.SETTER,

    report.TOTAL_OUTBOUND_CALLS,

    COALESCE(
        touched.TOTAL_LEADS_TOUCHED,
        0
    ) AS TOTAL_LEADS_TOUCHED,

    report.OUTBOUND_SET,

    report.TOTAL_CLOSER_SHOW,

    report.TOTAL_OFFER,

    report.TOTAL_SALE,

    report.DIAL_TO_SET_RATE,

    report.SET_TO_SHOW_RATE,

    report.SHOW_TO_SALE_RATE,

    ROUND(
        COALESCE(report.TOTAL_REVENUE, 0),
        2
    ) AS TOTAL_REVENUE,

    ROUND(
        report.AVERAGE_ORDER_VALUE,
        2
    ) AS AVERAGE_ORDER_VALUE

FROM DETAILED_REPORT report

LEFT JOIN LEADS_TOUCHED touched
    ON report.DIAL_DATE = touched.DIAL_DATE
   AND report.SETTER = touched.SETTER
   AND EQUAL_NULL(
        report.SETTER_EMAIL,
        touched.SETTER_EMAIL
   );


```


# VALIDATION

```



   DESC VIEW SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT;


   DESC VIEW
SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME;


SELECT
    (
        SELECT SUM(OUTBOUND_DIALS)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS DETAILED_OUTBOUND_CALLS,

    (
        SELECT SUM(TOTAL_OUTBOUND_CALLS)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME
    ) AS SME_OUTBOUND_CALLS,

    (
        SELECT SUM(STRATEGY_CALL_BOOKED)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS DETAILED_OUTBOUND_SET,

    (
        SELECT SUM(OUTBOUND_SET)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME
    ) AS SME_OUTBOUND_SET,

    (
        SELECT SUM(STRATEGY_CALL_TAKEN)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS DETAILED_CLOSER_SHOW,

    (
        SELECT SUM(TOTAL_CLOSER_SHOW)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME
    ) AS SME_CLOSER_SHOW,

    (
        SELECT SUM(OFFERS_PRESENTED)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS DETAILED_TOTAL_OFFERS,

    (
        SELECT SUM(TOTAL_OFFER)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME
    ) AS SME_TOTAL_OFFERS,

    (
        SELECT SUM(TOTAL_SALES)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT
    ) AS DETAILED_TOTAL_SALES,

    (
        SELECT SUM(TOTAL_SALE)
        FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME
    ) AS SME_TOTAL_SALES;



    SELECT
    SUM(TOTAL_OUTBOUND_CALLS)
        AS TOTAL_OUTBOUND_CALLS,

    SUM(TOTAL_LEADS_TOUCHED)
        AS TOTAL_DAILY_LEADS_TOUCHED,

    COUNT_IF(
        TOTAL_LEADS_TOUCHED >
        TOTAL_OUTBOUND_CALLS
    ) AS INVALID_LEADS_TOUCHED_ROWS

FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME;




SELECT
    COUNT_IF(
        DIAL_TO_SET_RATE < 0
        OR DIAL_TO_SET_RATE > 100
    ) AS INVALID_DIAL_TO_SET_ROWS,

    COUNT_IF(
        SET_TO_SHOW_RATE < 0
        OR SET_TO_SHOW_RATE > 100
    ) AS INVALID_SET_TO_SHOW_ROWS,

    COUNT_IF(
        SHOW_TO_SALE_RATE < 0
        OR SHOW_TO_SALE_RATE > 100
    ) AS INVALID_SHOW_TO_SALE_ROWS

FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME;


SELECT
    COUNT_IF(
        DIAL_TO_SET_RATE < 0
        OR DIAL_TO_SET_RATE > 100
    ) AS INVALID_DIAL_TO_SET_ROWS,

    COUNT_IF(
        SET_TO_SHOW_RATE < 0
        OR SET_TO_SHOW_RATE > 100
    ) AS INVALID_SET_TO_SHOW_ROWS,

    COUNT_IF(
        SHOW_TO_SALE_RATE < 0
        OR SHOW_TO_SALE_RATE > 100
    ) AS INVALID_SHOW_TO_SALE_ROWS

FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME;



SELECT *
FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME

ORDER BY
    DIAL_DATE DESC,
    TOTAL_OUTBOUND_CALLS DESC,
    SETTER;


```


# new

```

USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW
SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT_SME AS

WITH OUTBOUND_BASE AS (

    /*
        One latest record per outbound activity.

        Confirmed source activity names:
            1) Prospecting Activity
            2) Prospecting Follow Up
    */

    SELECT
        ACTIVITY_ID AS OUTBOUND_ACTIVITY_ID,
        LEAD_ID,

        ACTIVITY_AT AS OUTBOUND_TIMESTAMP,
        ACTIVITY_AT::DATE AS DIAL_DATE,

        COALESCE(
            NULLIF(TRIM(DEA_INTERNAL_NAME), ''),
            'UNMAPPED SETTER'
        ) AS SETTER,

        NULLIF(
            TRIM(DEA_INTERNAL_EMAIL),
            ''
        ) AS SETTER_EMAIL,

        CUSTOM_ACTIVITY,
        CUSTOM_ACTIVITY_OUTCOME,

        /*
            Every source outbound activity is one outbound call.
        */
        1 AS TOTAL_OUTBOUND_CALLS,

        /*
            Outbound Set:
            prospecting activity scheduled a Strategy Call.
        */
        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME =
                 '2. Strategy Call Scheduled'
            THEN 1
            ELSE 0
        END AS OUTBOUND_SET

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    )

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ACTIVITY_ID
        ORDER BY
            DATE_UPDATED DESC NULLS LAST,
            UPDATE_DATE DESC NULLS LAST,
            INSERT_DATE DESC NULLS LAST,
            ACTIVITY_AT DESC NULLS LAST
    ) = 1
),

STRATEGY_BASE AS (

    /*
        One latest record per actual Strategy Call.

        Follow-up activities are not treated as a new booked meeting
        for this setter funnel. The primary 5) Strategy Call is used
        to measure whether the outbound set resulted in a show.
    */

    SELECT
        ACTIVITY_ID AS STRATEGY_ACTIVITY_ID,
        LEAD_ID,

        ACTIVITY_AT AS STRATEGY_TIMESTAMP,

        CUSTOM_ACTIVITY_OUTCOME
            AS STRATEGY_CALL_OUTCOME,

        OFFER_PRESENTED,

        /*
            Attended Strategy Call.
        */
        CASE
            WHEN CUSTOM_ACTIVITY_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
            THEN 1
            ELSE 0
        END AS STRATEGY_SHOW_FLAG,

        /*
            Offer is valid only after an attended Strategy Call.
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
        END AS OFFER_FLAG

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

STRATEGY_TO_OUTBOUND_CANDIDATES AS (

    /*
        Match each Strategy Call to the nearest preceding outbound
        activity for the same lead.

        Only outbound activities classified as OUTBOUND_SET are
        eligible to receive downstream show/offer attribution.
    */

    SELECT
        strategy.STRATEGY_ACTIVITY_ID,
        strategy.LEAD_ID,
        strategy.STRATEGY_TIMESTAMP,
        strategy.STRATEGY_SHOW_FLAG,
        strategy.OFFER_FLAG,

        outbound.OUTBOUND_ACTIVITY_ID,
        outbound.OUTBOUND_TIMESTAMP,

        ROW_NUMBER() OVER (
            PARTITION BY strategy.STRATEGY_ACTIVITY_ID
            ORDER BY
                outbound.OUTBOUND_TIMESTAMP DESC,
                outbound.OUTBOUND_ACTIVITY_ID DESC
        ) AS MATCH_RANK

    FROM STRATEGY_BASE strategy

    INNER JOIN OUTBOUND_BASE outbound
        ON strategy.LEAD_ID = outbound.LEAD_ID
       AND outbound.OUTBOUND_SET = 1
       AND outbound.OUTBOUND_TIMESTAMP
           <= strategy.STRATEGY_TIMESTAMP
),

STRATEGY_ATTRIBUTED AS (

    /*
        Collapse all attributed Strategy Calls to one funnel result
        per outbound-set activity.

        MAX is intentional:

            one outbound set
            → zero or one closer show
            → zero or one offer indicator

        Even when multiple downstream Strategy Call records exist,
        the original outbound set receives no more than one show.
    */

    SELECT
        OUTBOUND_ACTIVITY_ID,

        MAX(
            STRATEGY_SHOW_FLAG
        ) AS TOTAL_CLOSER_SHOW,

        MAX(
            OFFER_FLAG
        ) AS TOTAL_OFFER

    FROM STRATEGY_TO_OUTBOUND_CANDIDATES

    WHERE MATCH_RANK = 1

    GROUP BY
        OUTBOUND_ACTIVITY_ID
),

SALES_BASE AS (

    /*
        One latest record per sale activity.
    */

    SELECT
        ACTIVITY_ID AS SALE_ACTIVITY_ID,
        LEAD_ID,

        COALESCE(
            ACTIVITY_AT,
            DATE_OF_SALE::TIMESTAMP_NTZ
        ) AS SALE_TIMESTAMP,

        TRY_TO_DECIMAL(
            NULLIF(
                REGEXP_REPLACE(
                    CONTRACT_VALUE::STRING,
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
                    CASH_COLLECTED::STRING,
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

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ACTIVITY_ID
        ORDER BY
            DATE_UPDATED DESC NULLS LAST,
            UPDATE_DATE DESC NULLS LAST,
            INSERT_DATE DESC NULLS LAST,
            ACTIVITY_AT DESC NULLS LAST
    ) = 1
),

ATTENDED_STRATEGY_ATTRIBUTION AS (

    /*
        Retain one attributed Strategy Call record per strategy event,
        but only when that Strategy Call was attended.
    */

    SELECT
        candidate.STRATEGY_ACTIVITY_ID,
        candidate.LEAD_ID,
        candidate.STRATEGY_TIMESTAMP,
        candidate.OUTBOUND_ACTIVITY_ID

    FROM STRATEGY_TO_OUTBOUND_CANDIDATES candidate

    WHERE candidate.MATCH_RANK = 1
      AND candidate.STRATEGY_SHOW_FLAG = 1
),

SALE_TO_STRATEGY_CANDIDATES AS (

    /*
        Match each sale to the nearest preceding attended Strategy Call.

        This enforces:

            outbound set
            → attended Strategy Call
            → sale
    */

    SELECT
        sale.SALE_ACTIVITY_ID,
        sale.LEAD_ID,
        sale.SALE_TIMESTAMP,
        sale.CONTRACT_VALUE_NUMERIC,
        sale.CASH_COLLECTED_NUMERIC,

        strategy.STRATEGY_ACTIVITY_ID,
        strategy.OUTBOUND_ACTIVITY_ID,
        strategy.STRATEGY_TIMESTAMP,

        ROW_NUMBER() OVER (
            PARTITION BY sale.SALE_ACTIVITY_ID
            ORDER BY
                strategy.STRATEGY_TIMESTAMP DESC,
                strategy.STRATEGY_ACTIVITY_ID DESC
        ) AS MATCH_RANK

    FROM SALES_BASE sale

    INNER JOIN ATTENDED_STRATEGY_ATTRIBUTION strategy
        ON sale.LEAD_ID = strategy.LEAD_ID
       AND strategy.STRATEGY_TIMESTAMP
           <= sale.SALE_TIMESTAMP
),

SALES_BY_OUTBOUND_JOURNEY AS (

    /*
        Aggregate all sale events associated with each outbound journey.

        TOTAL_SALE is capped at one conversion per journey.

        Revenue is not capped because multiple valid revenue records can
        belong to the same converted journey.
    */

    SELECT
        OUTBOUND_ACTIVITY_ID,

        1 AS TOTAL_SALE,

        SUM(
            COALESCE(
                CONTRACT_VALUE_NUMERIC,
                0
            )
        ) AS TOTAL_REVENUE,

        SUM(
            COALESCE(
                CASH_COLLECTED_NUMERIC,
                0
            )
        ) AS TOTAL_CASH_COLLECTED,

        COUNT(
            CONTRACT_VALUE_NUMERIC
        ) AS SALES_WITH_CONTRACT_VALUE

    FROM SALE_TO_STRATEGY_CANDIDATES

    WHERE MATCH_RANK = 1

    GROUP BY
        OUTBOUND_ACTIVITY_ID
),

OUTBOUND_ENRICHED AS (

    /*
        One row remains per outbound activity.

        Downstream metrics are already collapsed to the funnel level,
        preventing many-to-many multiplication.
    */

    SELECT
        outbound.OUTBOUND_ACTIVITY_ID,
        outbound.LEAD_ID,
        outbound.DIAL_DATE,
        outbound.SETTER,
        outbound.SETTER_EMAIL,

        outbound.TOTAL_OUTBOUND_CALLS,
        outbound.OUTBOUND_SET,

        /*
            A show or sale is valid only for an outbound-set journey.
        */
        CASE
            WHEN outbound.OUTBOUND_SET = 1
            THEN COALESCE(
                strategy.TOTAL_CLOSER_SHOW,
                0
            )
            ELSE 0
        END AS TOTAL_CLOSER_SHOW,

        CASE
            WHEN outbound.OUTBOUND_SET = 1
            THEN COALESCE(
                strategy.TOTAL_OFFER,
                0
            )
            ELSE 0
        END AS TOTAL_OFFER,

        CASE
            WHEN outbound.OUTBOUND_SET = 1
             AND COALESCE(
                    strategy.TOTAL_CLOSER_SHOW,
                    0
                 ) = 1
            THEN COALESCE(
                sales.TOTAL_SALE,
                0
            )
            ELSE 0
        END AS TOTAL_SALE,

        CASE
            WHEN outbound.OUTBOUND_SET = 1
             AND COALESCE(
                    strategy.TOTAL_CLOSER_SHOW,
                    0
                 ) = 1
            THEN COALESCE(
                sales.TOTAL_REVENUE,
                0
            )
            ELSE 0
        END AS TOTAL_REVENUE,

        CASE
            WHEN outbound.OUTBOUND_SET = 1
             AND COALESCE(
                    strategy.TOTAL_CLOSER_SHOW,
                    0
                 ) = 1
            THEN COALESCE(
                sales.TOTAL_CASH_COLLECTED,
                0
            )
            ELSE 0
        END AS TOTAL_CASH_COLLECTED,

        CASE
            WHEN outbound.OUTBOUND_SET = 1
             AND COALESCE(
                    strategy.TOTAL_CLOSER_SHOW,
                    0
                 ) = 1
            THEN COALESCE(
                sales.SALES_WITH_CONTRACT_VALUE,
                0
            )
            ELSE 0
        END AS SALES_WITH_CONTRACT_VALUE

    FROM OUTBOUND_BASE outbound

    LEFT JOIN STRATEGY_ATTRIBUTED strategy
        ON outbound.OUTBOUND_ACTIVITY_ID =
           strategy.OUTBOUND_ACTIVITY_ID

    LEFT JOIN SALES_BY_OUTBOUND_JOURNEY sales
        ON outbound.OUTBOUND_ACTIVITY_ID =
           sales.OUTBOUND_ACTIVITY_ID
)

SELECT
    DIAL_DATE,
    SETTER,

    SUM(
        TOTAL_OUTBOUND_CALLS
    ) AS TOTAL_OUTBOUND_CALLS,

    COUNT(
        DISTINCT LEAD_ID
    ) AS TOTAL_LEADS_TOUCHED,

    SUM(
        OUTBOUND_SET
    ) AS OUTBOUND_SET,

    SUM(
        TOTAL_CLOSER_SHOW
    ) AS TOTAL_CLOSER_SHOW,

    SUM(
        TOTAL_OFFER
    ) AS TOTAL_OFFER,

    SUM(
        TOTAL_SALE
    ) AS TOTAL_SALE,

    /*
        Dial-to-set:
        outbound sets ÷ all outbound calls
    */
    ROUND(
        100.0
        * SUM(OUTBOUND_SET)
        / NULLIF(
            SUM(TOTAL_OUTBOUND_CALLS),
            0
        ),
        2
    ) AS DIAL_TO_SET_RATE,

    /*
        Set-to-show:
        successful shows ÷ outbound sets

        Because each outbound set contributes at most one show,
        this rate cannot exceed 100%.
    */
    ROUND(
        100.0
        * SUM(TOTAL_CLOSER_SHOW)
        / NULLIF(
            SUM(OUTBOUND_SET),
            0
        ),
        2
    ) AS SET_TO_SHOW_RATE,

    /*
        Show-to-sale:
        converted journeys ÷ closer shows

        Because each attended journey contributes at most one sale,
        this rate cannot exceed 100%.
    */
    ROUND(
        100.0
        * SUM(TOTAL_SALE)
        / NULLIF(
            SUM(TOTAL_CLOSER_SHOW),
            0
        ),
        2
    ) AS SHOW_TO_SALE_RATE,

    ROUND(
        SUM(TOTAL_REVENUE),
        2
    ) AS TOTAL_REVENUE,

    /*
        Average revenue per converted outbound journey.
    */
    ROUND(
        SUM(TOTAL_REVENUE)
        / NULLIF(
            SUM(TOTAL_SALE),
            0
        ),
        2
    ) AS AVERAGE_ORDER_VALUE

FROM OUTBOUND_ENRICHED

GROUP BY
    DIAL_DATE,
    SETTER;


```
