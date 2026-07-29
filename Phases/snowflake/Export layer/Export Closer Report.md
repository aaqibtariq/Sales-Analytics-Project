# create report

````
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA GOLD;

CREATE OR REPLACE VIEW
SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT AS

WITH STRATEGY_BASE AS (

    /*
      One row per actual Strategy Call.

      The closer assigned to the Strategy Call receives credit
      for the call, offer and any attributed sale.
    */
    SELECT
        LEAD_ID,
        ACTIVITY_ID AS STRATEGY_ACTIVITY_ID,
        ACTIVITY_AT AS STRATEGY_TIMESTAMP,
        ACTIVITY_AT::DATE AS STRATEGY_DATE,

        YEAROFWEEKISO(ACTIVITY_AT::DATE)
            || '-'
            || LPAD(WEEKISO(ACTIVITY_AT::DATE), 2, '0')
            AS REPORTING_WEEK,

        COALESCE(
            CLOSER_NAME,
            'UNMAPPED CLOSER'
        ) AS CLOSER,

        CLOSER_EMAIL,

        CUSTOM_ACTIVITY_OUTCOME
            AS STRATEGY_CALL_OUTCOME,

        OFFER_PRESENTED,

        /*
          Every Strategy Call activity counts as one call.
        */
        1 AS STRATEGY_CALLS,

        /*
          Attended Strategy Calls.

          These outcome values were validated earlier as taken.
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
        END AS STRATEGY_CALL_TAKEN,

        /*
          Count an offer only when:
          1. The Strategy Call was attended.
          2. The offer field indicates yes.
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

SALES_BASE AS (

    /*
      One row per sale activity.

      Silver is used instead of joining Gold views because it retains
      ACTIVITY_ID and the exact activity timestamp required for
      deterministic event attribution.
    */
    SELECT
        LEAD_ID,
        ACTIVITY_ID AS SALE_ACTIVITY_ID,

        COALESCE(
            ACTIVITY_AT,
            DATE_OF_SALE::TIMESTAMP_NTZ
        ) AS SALE_TIMESTAMP,

        DATE_OF_SALE,

        PROGRAM,

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
),

SALE_TO_STRATEGY_CANDIDATES AS (

    /*
      Find every Strategy Call occurring before each sale
      for the same lead.

      A lead can have multiple Strategy Calls, so this produces
      candidate matches. The nearest prior Strategy Call will be
      retained in the next step.
    */
    SELECT
        sa.LEAD_ID,
        sa.SALE_ACTIVITY_ID,
        sa.SALE_TIMESTAMP,
        sa.DATE_OF_SALE,
        sa.PROGRAM,
        sa.CONTRACT_VALUE_NUMERIC,
        sa.CASH_COLLECTED_NUMERIC,

        st.STRATEGY_ACTIVITY_ID,
        st.STRATEGY_TIMESTAMP,

        ROW_NUMBER() OVER (
            PARTITION BY sa.SALE_ACTIVITY_ID
            ORDER BY
                st.STRATEGY_TIMESTAMP DESC,
                st.STRATEGY_ACTIVITY_ID DESC
        ) AS MATCH_RANK

    FROM SALES_BASE sa

    INNER JOIN STRATEGY_BASE st
        ON sa.LEAD_ID = st.LEAD_ID
       AND st.STRATEGY_TIMESTAMP <= sa.SALE_TIMESTAMP
),

SALES_ATTRIBUTED AS (

    /*
      Each sale is retained against no more than one Strategy Call.
    */
    SELECT
        STRATEGY_ACTIVITY_ID,

        COUNT(*) AS TOTAL_SALES,

        SUM(CONTRACT_VALUE_NUMERIC)
            AS TOTAL_CONTRACT_VALUE,

        SUM(CASH_COLLECTED_NUMERIC)
            AS TOTAL_CASH_COLLECTED,

        COUNT(CONTRACT_VALUE_NUMERIC)
            AS SALES_WITH_CONTRACT_VALUE,

        COUNT(CASH_COLLECTED_NUMERIC)
            AS SALES_WITH_CASH_COLLECTED

    FROM SALE_TO_STRATEGY_CANDIDATES

    WHERE MATCH_RANK = 1

    GROUP BY STRATEGY_ACTIVITY_ID
),

STRATEGY_ENRICHED AS (

    /*
      Join one Strategy Call to its already aggregated sale metrics.

      This prevents:
      Strategy Calls × Sales
      row multiplication.
    */
    SELECT
        st.STRATEGY_DATE,
        st.REPORTING_WEEK,
        st.CLOSER,
        st.CLOSER_EMAIL,
        st.STRATEGY_ACTIVITY_ID,

        st.STRATEGY_CALLS,
        st.STRATEGY_CALL_TAKEN,
        st.OFFER_PRESENTED_FLAG,

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
        ) AS SALES_WITH_CONTRACT_VALUE,

        COALESCE(
            sa.SALES_WITH_CASH_COLLECTED,
            0
        ) AS SALES_WITH_CASH_COLLECTED

    FROM STRATEGY_BASE st

    LEFT JOIN SALES_ATTRIBUTED sa
        ON st.STRATEGY_ACTIVITY_ID =
           sa.STRATEGY_ACTIVITY_ID
)

SELECT
    STRATEGY_DATE,
    REPORTING_WEEK,
    CLOSER,
    CLOSER_EMAIL,

    SUM(STRATEGY_CALLS)
        AS STRATEGY_CALLS,

    SUM(STRATEGY_CALL_TAKEN)
        AS STRATEGY_CALL_TAKEN,

    ROUND(
        100.0 * SUM(STRATEGY_CALL_TAKEN)
        / NULLIF(SUM(STRATEGY_CALLS), 0),
        2
    ) AS SHOW_RATE,

    SUM(OFFER_PRESENTED_FLAG)
        AS OFFERS_PRESENTED,

    ROUND(
        100.0 * SUM(OFFER_PRESENTED_FLAG)
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
        100.0 * SUM(TOTAL_SALES)
        / NULLIF(SUM(OFFER_PRESENTED_FLAG), 0),
        2
    ) AS OFFER_TO_SALE_RATE,

    ROUND(
        SUM(TOTAL_CONTRACT_VALUE),
        2
    ) AS TOTAL_CONTRACT_VALUE,

    ROUND(
        SUM(TOTAL_CASH_COLLECTED),
        2
    ) AS TOTAL_CASH_COLLECTED,

    ROUND(
        SUM(TOTAL_CONTRACT_VALUE)
        / NULLIF(SUM(SALES_WITH_CONTRACT_VALUE), 0),
        2
    ) AS AVERAGE_CONTRACT_VALUE,

    ROUND(
        SUM(TOTAL_CASH_COLLECTED)
        / NULLIF(SUM(SALES_WITH_CASH_COLLECTED), 0),
        2
    ) AS AVERAGE_CASH_COLLECTED

FROM STRATEGY_ENRICHED

GROUP BY
    STRATEGY_DATE,
    REPORTING_WEEK,
    CLOSER,
    CLOSER_EMAIL;


```

# validations

```




SELECT
    SUM(STRATEGY_CALLS)
        AS STRATEGY_CALLS,

    SUM(STRATEGY_CALL_TAKEN)
        AS STRATEGY_CALL_TAKEN,

    SUM(OFFERS_PRESENTED)
        AS OFFERS_PRESENTED,

    SUM(TOTAL_SALES)
        AS TOTAL_SALES,

    ROUND(
        100.0 * SUM(STRATEGY_CALL_TAKEN)
        / NULLIF(SUM(STRATEGY_CALLS), 0),
        2
    ) AS OVERALL_SHOW_RATE,

    ROUND(
        100.0 * SUM(OFFERS_PRESENTED)
        / NULLIF(SUM(STRATEGY_CALL_TAKEN), 0),
        2
    ) AS OVERALL_OFFER_RATE,

    ROUND(
        100.0 * SUM(TOTAL_SALES)
        / NULLIF(SUM(STRATEGY_CALL_TAKEN), 0),
        2
    ) AS OVERALL_SALE_RATE

FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT;







    SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
    ) AS SILVER_STRATEGY_CALLS,

    (
        SELECT SUM(STRATEGY_CALLS)
        FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT
    ) AS REPORT_STRATEGY_CALLS,

    (
        SELECT COUNT_IF(
            CUSTOM_ACTIVITY_OUTCOME IN (
                '1. Follow Up',
                '5. Sale',
                '6. Sale',
                '7. Lost'
            )
        )
        FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
        WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
    ) AS SILVER_STRATEGY_TAKEN,

    (
        SELECT SUM(STRATEGY_CALL_TAKEN)
        FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT
    ) AS REPORT_STRATEGY_TAKEN;




    SELECT
    (
        SELECT COUNT(*)
        FROM SALES_ANALYTICS_DB.GOLD.SALES_DETAILS
    ) AS TOTAL_SALES_SOURCE,

    (
        SELECT SUM(TOTAL_SALES)
        FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT
    ) AS SALES_ATTRIBUTED_TO_STRATEGY_CALLS;









WITH STRATEGY_BASE AS (

    SELECT
        LEAD_ID,
        ACTIVITY_ID AS STRATEGY_ACTIVITY_ID,
        ACTIVITY_AT AS STRATEGY_TIMESTAMP

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
),

SALES_BASE AS (

    SELECT
        LEAD_ID,
        ACTIVITY_ID AS SALE_ACTIVITY_ID,

        COALESCE(
            ACTIVITY_AT,
            DATE_OF_SALE::TIMESTAMP_NTZ
        ) AS SALE_TIMESTAMP

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    )
)

SELECT
    COUNT(*) AS TOTAL_SALES,

    COUNT_IF(
        NOT EXISTS (
            SELECT 1
            FROM STRATEGY_BASE st
            WHERE st.LEAD_ID = sa.LEAD_ID
              AND st.STRATEGY_TIMESTAMP <= sa.SALE_TIMESTAMP
        )
    ) AS UNATTRIBUTED_SALES

FROM SALES_BASE sa;

    WITH STRATEGY_BASE AS (

    SELECT
        LEAD_ID,
        ACTIVITY_ID AS STRATEGY_ACTIVITY_ID,
        ACTIVITY_AT AS STRATEGY_TIMESTAMP

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '5) Strategy Call'
),

SALES_BASE AS (

    SELECT
        LEAD_ID,
        ACTIVITY_ID AS SALE_ACTIVITY_ID,

        COALESCE(
            ACTIVITY_AT,
            DATE_OF_SALE::TIMESTAMP_NTZ
        ) AS SALE_TIMESTAMP

    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    )
)

SELECT
    COUNT(*) AS TOTAL_SALES,

    COUNT_IF(
        NOT EXISTS (
            SELECT 1
            FROM STRATEGY_BASE st
            WHERE st.LEAD_ID = sa.LEAD_ID
              AND st.STRATEGY_TIMESTAMP <= sa.SALE_TIMESTAMP
        )
    ) AS UNATTRIBUTED_SALES

FROM SALES_BASE sa;








SELECT
    COUNT_IF(
        SHOW_RATE < 0
        OR SHOW_RATE > 100
    ) AS INVALID_SHOW_RATE_ROWS,

    COUNT_IF(
        OFFER_RATE < 0
        OR OFFER_RATE > 100
    ) AS INVALID_OFFER_RATE_ROWS,

    COUNT_IF(
        SALE_RATE < 0
        OR SALE_RATE > 100
    ) AS INVALID_SALE_RATE_ROWS,

    COUNT_IF(
        OFFER_TO_SALE_RATE < 0
        OR OFFER_TO_SALE_RATE > 100
    ) AS INVALID_OFFER_TO_SALE_RATE_ROWS

FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT;







SELECT
    ROUND(
        SUM(TOTAL_CONTRACT_VALUE),
        2
    ) AS TOTAL_CONTRACT_VALUE,

    ROUND(
        SUM(TOTAL_CASH_COLLECTED),
        2
    ) AS TOTAL_CASH_COLLECTED,

    ROUND(
        SUM(TOTAL_CONTRACT_VALUE)
        / NULLIF(SUM(TOTAL_SALES), 0),
        2
    ) AS CONTRACT_VALUE_PER_ATTRIBUTED_SALE,

    ROUND(
        SUM(TOTAL_CASH_COLLECTED)
        / NULLIF(SUM(TOTAL_SALES), 0),
        2
    ) AS CASH_COLLECTED_PER_ATTRIBUTED_SALE

FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT;










SELECT
    CLOSER,
    CLOSER_EMAIL,

    SUM(STRATEGY_CALLS)
        AS STRATEGY_CALLS,

    SUM(STRATEGY_CALL_TAKEN)
        AS STRATEGY_CALL_TAKEN,

    ROUND(
        100.0 * SUM(STRATEGY_CALL_TAKEN)
        / NULLIF(SUM(STRATEGY_CALLS), 0),
        2
    ) AS SHOW_RATE,

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
        SUM(TOTAL_CONTRACT_VALUE),
        2
    ) AS TOTAL_CONTRACT_VALUE,

    ROUND(
        SUM(TOTAL_CASH_COLLECTED),
        2
    ) AS TOTAL_CASH_COLLECTED

FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT

GROUP BY
    CLOSER,
    CLOSER_EMAIL

ORDER BY
    TOTAL_CONTRACT_VALUE DESC,
    TOTAL_SALES DESC;





    SELECT *
FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT
ORDER BY
    STRATEGY_DATE DESC,
    STRATEGY_CALLS DESC,
    CLOSER;


```
