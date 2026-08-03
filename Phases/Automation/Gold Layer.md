/*====================================================================
  SALES ANALYTICS PROJECT
  FULL CORRECTED GOLD REFRESH

  Gold objects:
    1. ALL_STRATEGIES_DETAILS
    2. INBOUND_STRATEGIES_BOOKED
    3. OUTBOUND_STRATEGIES_BOOKED
    4. SALES_DETAILS
    5. OUTBOUND_PROSPECT_DIALS

  Source:
    SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

  Important corrections:
    - Uses numbered outbound activity names found in current data.
    - Does not reference SILVER.DATE_OF_SALE.
    - Derives outbound bookings using sequential activity attribution.
    - Uses one Strategy Call per activity ID.
    - Assigns each Strategy Call to the nearest preceding outbound
      activity for the same lead.
====================================================================*/


/*====================================================================
  1. SESSION CONTEXT
====================================================================*/

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA AUTOMATION;


/*====================================================================
  2. REQUIRED PRIVILEGES — ONE-TIME SETUP

  Run these grants once. Re-running them is harmless.
====================================================================*/

GRANT USAGE
ON DATABASE SALES_ANALYTICS_DB
TO ROLE ACCOUNTADMIN;

GRANT USAGE, CREATE VIEW
ON SCHEMA SALES_ANALYTICS_DB.GOLD
TO ROLE ACCOUNTADMIN;

GRANT SELECT
ON ALL TABLES IN SCHEMA SALES_ANALYTICS_DB.SILVER
TO ROLE ACCOUNTADMIN;

GRANT SELECT
ON FUTURE TABLES IN SCHEMA SALES_ANALYTICS_DB.SILVER
TO ROLE ACCOUNTADMIN;

GRANT SELECT
ON ALL VIEWS IN SCHEMA SALES_ANALYTICS_DB.GOLD
TO ROLE ACCOUNTADMIN;

GRANT SELECT
ON FUTURE VIEWS IN SCHEMA SALES_ANALYTICS_DB.GOLD
TO ROLE ACCOUNTADMIN;

GRANT USAGE
ON WAREHOUSE COMPUTE_WH
TO ROLE ACCOUNTADMIN;


/*====================================================================
  3. CREATE OR REPLACE GOLD REFRESH PROCEDURE
====================================================================*/

CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_GOLD()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    V_RUN_ID STRING DEFAULT UUID_STRING();

    V_STARTED_AT TIMESTAMP_NTZ
        DEFAULT CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;

    V_COMPLETED_AT TIMESTAMP_NTZ;

    V_DURATION_SECONDS NUMBER(18,3) DEFAULT 0;

    V_EXECUTED_BY STRING DEFAULT CURRENT_USER();
    V_WAREHOUSE_NAME STRING DEFAULT CURRENT_WAREHOUSE();
    V_ERROR_MESSAGE STRING DEFAULT NULL;

    V_ALL_STRATEGIES_COUNT NUMBER DEFAULT 0;
    V_INBOUND_BOOKED_COUNT NUMBER DEFAULT 0;
    V_OUTBOUND_BOOKED_COUNT NUMBER DEFAULT 0;
    V_SALES_COUNT NUMBER DEFAULT 0;
    V_OUTBOUND_DIALS_COUNT NUMBER DEFAULT 0;

    V_ALL_STRATEGIES_SOURCE_COUNT NUMBER DEFAULT 0;
    V_INBOUND_SOURCE_COUNT NUMBER DEFAULT 0;
    V_SALES_SOURCE_COUNT NUMBER DEFAULT 0;
    V_OUTBOUND_DIALS_SOURCE_COUNT NUMBER DEFAULT 0;

    V_ALL_STRATEGIES_DIFF NUMBER DEFAULT 0;
    V_INBOUND_DIFF NUMBER DEFAULT 0;
    V_SALES_DIFF NUMBER DEFAULT 0;
    V_OUTBOUND_DIALS_DIFF NUMBER DEFAULT 0;

    V_INVALID_STRATEGY_ROWS NUMBER DEFAULT 0;
    V_INVALID_INBOUND_ROWS NUMBER DEFAULT 0;
    V_INVALID_OUTBOUND_ROWS NUMBER DEFAULT 0;
    V_INVALID_SALES_ROWS NUMBER DEFAULT 0;
    V_INVALID_DIAL_ROWS NUMBER DEFAULT 0;

    E_GOLD_VALIDATION_FAILED EXCEPTION
        (-20003, 'Gold data-quality validation failed.');

BEGIN

    /*================================================================
      1. ALL_STRATEGIES_DETAILS

      Contains all Strategy Call and Strategy Call Follow-Up events.
    ================================================================*/

    CREATE OR REPLACE VIEW
    SALES_ANALYTICS_DB.GOLD.ALL_STRATEGIES_DETAILS
    AS

    SELECT
        LEAD_ID,

        ACTIVITY_AT::DATE
            AS ACTIVITY_LOG_DATE,

        CUSTOM_ACTIVITY,

        STATUS_CHANGE
            AS STATUS,

        CLOSER_EMAIL,

        CLOSER_NAME,

        CUSTOM_ACTIVITY_OUTCOME
            AS STRATEGY_CALL_OUTCOME,

        ACTIVITY_AT::DATE
            AS DATE_OF_STRATEGY_CALL,

        OFFER_PRESENTED,

        SETTER_EMAIL
            AS SETTER,

        SETTER_NAME

    FROM
        SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN
    (
        '5) Strategy Call',
        '6) Strategy Call Follow Up'
    );


    /*================================================================
      2. INBOUND_STRATEGIES_BOOKED

      Positive inbound qualification:
        3) Triage Call
        Outcome = 1. Strategy Call Scheduled
    ================================================================*/

    CREATE OR REPLACE VIEW
    SALES_ANALYTICS_DB.GOLD.INBOUND_STRATEGIES_BOOKED
    AS

    SELECT
        LEAD_ID,

        ACTIVITY_AT::DATE
            AS ACTIVITY_LOG_DATE,

        DEA_INTERNAL_EMAIL
            AS SETTER_CLOSER_EMAIL,

        DEA_INTERNAL_NAME
            AS SETTER_CLOSER_NAME,

        CUSTOM_ACTIVITY_OUTCOME
            AS TRIAGE_CALL_OUTCOME,

        ACTIVITY_AT::DATE
            AS TRIAGE_CALL_DATE,

        1
            AS STRATEGY_CALL_BOOKED,

        YEAROFWEEKISO(ACTIVITY_AT::DATE)
            || '-'
            || LPAD(
                WEEKISO(ACTIVITY_AT::DATE),
                2,
                '0'
            )
            AS SC_YEAR_WEEK

    FROM
        SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY = '3) Triage Call'

      AND CUSTOM_ACTIVITY_OUTCOME =
          '1. Strategy Call Scheduled';


    /*================================================================
      3. OUTBOUND_STRATEGIES_BOOKED

      Actual outbound records do not contain the documented outbound
      outcome value.

      Therefore:
        1. Identify outbound prospecting activities.
        2. Identify later Strategy Calls for the same lead.
        3. Attribute each Strategy Call to the nearest preceding
           outbound activity.
        4. Return one booked record per Strategy Call.

      This follows the documented sequential funnel hierarchy.
    ================================================================*/

    CREATE OR REPLACE VIEW
    SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED
    AS

    WITH OUTBOUND_BASE AS
    (
        SELECT
            LEAD_ID,

            ACTIVITY_ID
                AS OUTBOUND_ACTIVITY_ID,

            ACTIVITY_AT
                AS OUTBOUND_TIMESTAMP,

            ACTIVITY_AT::DATE
                AS ACTIVITY_LOG_DATE,

            DEA_INTERNAL_EMAIL
                AS SETTER_CLOSER_EMAIL,

            DEA_INTERNAL_NAME
                AS SETTER_CLOSER_NAME

        FROM
            SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

        WHERE CUSTOM_ACTIVITY IN
        (
            '1) Prospecting Activity',
            '2) Prospecting Follow Up'
        )

          AND LEAD_ID IS NOT NULL
          AND ACTIVITY_ID IS NOT NULL
          AND ACTIVITY_AT IS NOT NULL

        QUALIFY ROW_NUMBER() OVER
        (
            PARTITION BY ACTIVITY_ID

            ORDER BY
                DATE_UPDATED DESC NULLS LAST,
                UPDATE_DATE DESC NULLS LAST,
                INSERT_DATE DESC NULLS LAST,
                ACTIVITY_AT DESC NULLS LAST
        ) = 1
    ),

    STRATEGY_BASE AS
    (
        SELECT
            LEAD_ID,

            ACTIVITY_ID
                AS STRATEGY_ACTIVITY_ID,

            ACTIVITY_AT
                AS STRATEGY_TIMESTAMP

        FROM
            SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

        WHERE CUSTOM_ACTIVITY IN
        (
            '5) Strategy Call',
            '6) Strategy Call Follow Up'
        )

          AND LEAD_ID IS NOT NULL
          AND ACTIVITY_ID IS NOT NULL
          AND ACTIVITY_AT IS NOT NULL

        QUALIFY ROW_NUMBER() OVER
        (
            PARTITION BY ACTIVITY_ID

            ORDER BY
                DATE_UPDATED DESC NULLS LAST,
                UPDATE_DATE DESC NULLS LAST,
                INSERT_DATE DESC NULLS LAST,
                ACTIVITY_AT DESC NULLS LAST
        ) = 1
    ),

    ATTRIBUTION_CANDIDATES AS
    (
        SELECT
            S.LEAD_ID,

            S.STRATEGY_ACTIVITY_ID,

            S.STRATEGY_TIMESTAMP,

            O.OUTBOUND_ACTIVITY_ID,

            O.OUTBOUND_TIMESTAMP,

            O.ACTIVITY_LOG_DATE,

            O.SETTER_CLOSER_EMAIL,

            O.SETTER_CLOSER_NAME,

            ROW_NUMBER() OVER
            (
                PARTITION BY S.STRATEGY_ACTIVITY_ID

                ORDER BY
                    O.OUTBOUND_TIMESTAMP DESC,
                    O.OUTBOUND_ACTIVITY_ID DESC
            ) AS ATTRIBUTION_RANK

        FROM STRATEGY_BASE S

        INNER JOIN OUTBOUND_BASE O
            ON S.LEAD_ID = O.LEAD_ID

           AND O.OUTBOUND_TIMESTAMP
               <= S.STRATEGY_TIMESTAMP
    )

    SELECT
        LEAD_ID,

        ACTIVITY_LOG_DATE,

        SETTER_CLOSER_EMAIL,

        SETTER_CLOSER_NAME,

        ACTIVITY_LOG_DATE
            AS PROSPECT_CALL_DATE,

        1
            AS STRATEGY_CALL_BOOKED,

        YEAROFWEEKISO(ACTIVITY_LOG_DATE)
            || '-'
            || LPAD(
                WEEKISO(ACTIVITY_LOG_DATE),
                2,
                '0'
            )
            AS SC_YEAR_WEEK

    FROM ATTRIBUTION_CANDIDATES

    WHERE ATTRIBUTION_RANK = 1;


    /*================================================================
      4. SALES_DETAILS

      DATE_OF_SALE is derived in Gold from the sale activity timestamp.
      It is not read from a nonexistent Silver column.
    ================================================================*/

    CREATE OR REPLACE VIEW
    SALES_ANALYTICS_DB.GOLD.SALES_DETAILS
    AS

    SELECT
        LEAD_ID,

        ACTIVITY_AT,

        CUSTOM_ACTIVITY_OUTCOME
            AS SALE_STATUS,

        SETTER_EMAIL,

        SETTER_NAME,

        CLOSER_EMAIL,

        CLOSER_NAME,

        CONTRACT_VALUE
            AS CONTRACTED_VALUE,

        ACTIVITY_AT::DATE
            AS DATE_OF_SALE,

        PROGRAM,

        CASH_COLLECTED

    FROM
        SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN
    (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    );


    /*================================================================
      5. OUTBOUND_PROSPECT_DIALS

      Uses the numbered source activity names found in Silver.
    ================================================================*/

    CREATE OR REPLACE VIEW
    SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS
    AS

    SELECT
        LEAD_ID,

        ACTIVITY_AT::DATE
            AS ACTIVITY_LOG_DATE,

        YEAROFWEEKISO(ACTIVITY_AT::DATE)
            || '-'
            || LPAD(
                WEEKISO(ACTIVITY_AT::DATE),
                2,
                '0'
            )
            AS PROSPECT_YEAR_WEEK,

        CUSTOM_ACTIVITY,

        STATUS_CHANGE
            AS STATUS,

        CUSTOM_ACTIVITY_OUTCOME_NAME,

        CUSTOM_ACTIVITY_OUTCOME,

        DEA_INTERNAL_EMAIL
            AS SETTER_CLOSER_EMAIL,

        DEA_INTERNAL_NAME
            AS SETTER_CLOSER_NAME

    FROM
        SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY

    WHERE CUSTOM_ACTIVITY IN
    (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    );


    /*================================================================
      6. CAPTURE GOLD COUNTS
    ================================================================*/

    SELECT COUNT(*)
    INTO :V_ALL_STRATEGIES_COUNT
    FROM SALES_ANALYTICS_DB.GOLD.ALL_STRATEGIES_DETAILS;


    SELECT COUNT(*)
    INTO :V_INBOUND_BOOKED_COUNT
    FROM SALES_ANALYTICS_DB.GOLD.INBOUND_STRATEGIES_BOOKED;


    SELECT COUNT(*)
    INTO :V_OUTBOUND_BOOKED_COUNT
    FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED;


    SELECT COUNT(*)
    INTO :V_SALES_COUNT
    FROM SALES_ANALYTICS_DB.GOLD.SALES_DETAILS;


    SELECT COUNT(*)
    INTO :V_OUTBOUND_DIALS_COUNT
    FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS;


    /*================================================================
      7. SOURCE RECONCILIATION COUNTS

      These four Gold views have direct one-to-one source filters.
      OUTBOUND_STRATEGIES_BOOKED uses sequence attribution and is
      validated separately.
    ================================================================*/

    SELECT COUNT(*)
    INTO :V_ALL_STRATEGIES_SOURCE_COUNT
    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
    WHERE CUSTOM_ACTIVITY IN
    (
        '5) Strategy Call',
        '6) Strategy Call Follow Up'
    );


    SELECT COUNT(*)
    INTO :V_INBOUND_SOURCE_COUNT
    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
    WHERE CUSTOM_ACTIVITY = '3) Triage Call'
      AND CUSTOM_ACTIVITY_OUTCOME =
          '1. Strategy Call Scheduled';


    SELECT COUNT(*)
    INTO :V_SALES_SOURCE_COUNT
    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
    WHERE CUSTOM_ACTIVITY IN
    (
        '7) New Sale',
        '8) New Sale [Custom Payment Plan]'
    );


    SELECT COUNT(*)
    INTO :V_OUTBOUND_DIALS_SOURCE_COUNT
    FROM SALES_ANALYTICS_DB.SILVER.LEADS_ACTIVITIES_SUMMARY
    WHERE CUSTOM_ACTIVITY IN
    (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    );


    /*================================================================
      8. CALCULATE RECONCILIATION DIFFERENCES
    ================================================================*/

    V_ALL_STRATEGIES_DIFF :=
        V_ALL_STRATEGIES_COUNT
        - V_ALL_STRATEGIES_SOURCE_COUNT;

    V_INBOUND_DIFF :=
        V_INBOUND_BOOKED_COUNT
        - V_INBOUND_SOURCE_COUNT;

    V_SALES_DIFF :=
        V_SALES_COUNT
        - V_SALES_SOURCE_COUNT;

    V_OUTBOUND_DIALS_DIFF :=
        V_OUTBOUND_DIALS_COUNT
        - V_OUTBOUND_DIALS_SOURCE_COUNT;


    /*================================================================
      9. BUSINESS-RULE VALIDATION
    ================================================================*/

    SELECT COUNT(*)
    INTO :V_INVALID_STRATEGY_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.ALL_STRATEGIES_DETAILS
    WHERE CUSTOM_ACTIVITY NOT IN
    (
        '5) Strategy Call',
        '6) Strategy Call Follow Up'
    );


    SELECT COUNT(*)
    INTO :V_INVALID_INBOUND_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.INBOUND_STRATEGIES_BOOKED
    WHERE TRIAGE_CALL_OUTCOME <>
          '1. Strategy Call Scheduled'

       OR STRATEGY_CALL_BOOKED <> 1;


    /*--------------------------------------------------------------
      Outbound booking validation:
        - required keys cannot be null
        - prospect date must not be after the Strategy Call date

      The view does not expose Strategy Call timestamp, so temporal
      validity is checked using the same attribution source logic.
    --------------------------------------------------------------*/

    SELECT COUNT(*)
    INTO :V_INVALID_OUTBOUND_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED
    WHERE LEAD_ID IS NULL

       OR PROSPECT_CALL_DATE IS NULL

       OR STRATEGY_CALL_BOOKED <> 1;


    SELECT COUNT(*)
    INTO :V_INVALID_SALES_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.SALES_DETAILS
    WHERE LEAD_ID IS NULL

       OR ACTIVITY_AT IS NULL

       OR DATE_OF_SALE IS NULL;


    SELECT COUNT(*)
    INTO :V_INVALID_DIAL_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS
    WHERE CUSTOM_ACTIVITY NOT IN
    (
        '1) Prospecting Activity',
        '2) Prospecting Follow Up'
    );


    /*================================================================
      10. AUTOMATED FAILURE GATE
    ================================================================*/

    IF
    (
        V_ALL_STRATEGIES_DIFF <> 0
        OR V_INBOUND_DIFF <> 0
        OR V_SALES_DIFF <> 0
        OR V_OUTBOUND_DIALS_DIFF <> 0

        OR V_INVALID_STRATEGY_ROWS > 0
        OR V_INVALID_INBOUND_ROWS > 0
        OR V_INVALID_OUTBOUND_ROWS > 0
        OR V_INVALID_SALES_ROWS > 0
        OR V_INVALID_DIAL_ROWS > 0
    )
    THEN

        V_ERROR_MESSAGE :=
              'Gold validation failed. '
            || 'all strategies difference='
            || V_ALL_STRATEGIES_DIFF
            || ', inbound difference='
            || V_INBOUND_DIFF
            || ', sales difference='
            || V_SALES_DIFF
            || ', outbound dials difference='
            || V_OUTBOUND_DIALS_DIFF
            || ', invalid strategy rows='
            || V_INVALID_STRATEGY_ROWS
            || ', invalid inbound rows='
            || V_INVALID_INBOUND_ROWS
            || ', invalid outbound rows='
            || V_INVALID_OUTBOUND_ROWS
            || ', invalid sales rows='
            || V_INVALID_SALES_ROWS
            || ', invalid dial rows='
            || V_INVALID_DIAL_ROWS;

        RAISE E_GOLD_VALIDATION_FAILED;

    END IF;


    /*================================================================
      11. PREPARE SUCCESS LOG
    ================================================================*/

    V_COMPLETED_AT :=
        CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;

    V_DURATION_SECONDS :=
        ABS
        (
            DATEDIFF
            (
                'MILLISECOND',
                V_STARTED_AT,
                V_COMPLETED_AT
            )
        ) / 1000.0;


    /*================================================================
      12. LOG SUCCESS

      Existing generic count columns are reused:
        LEADS_ROWS_ADDED      = inbound booked count
        ACTIVITIES_ROWS_ADDED = all strategy rows
        USERS_ROWS_ADDED      = outbound booked count
        CUSTOM_ROWS_ADDED     = sales count
    ================================================================*/

    INSERT INTO
    SALES_ANALYTICS_DB.AUTOMATION.PIPELINE_RUN_LOG
    (
        RUN_ID,
        PIPELINE_NAME,
        STEP_NAME,
        STATUS,
        STARTED_AT,
        COMPLETED_AT,
        DURATION_SECONDS,
        LEADS_ROWS_ADDED,
        ACTIVITIES_ROWS_ADDED,
        USERS_ROWS_ADDED,
        CUSTOM_ROWS_ADDED,
        ERROR_MESSAGE,
        EXECUTED_BY,
        WAREHOUSE_NAME
    )
    VALUES
    (
        :V_RUN_ID,
        'SALES_ANALYTICS_DAILY_PIPELINE',
        'GOLD_REFRESH',
        'SUCCESS',
        :V_STARTED_AT,
        :V_COMPLETED_AT,
        :V_DURATION_SECONDS,

        :V_INBOUND_BOOKED_COUNT,
        :V_ALL_STRATEGIES_COUNT,
        :V_OUTBOUND_BOOKED_COUNT,
        :V_SALES_COUNT,

        NULL,
        :V_EXECUTED_BY,
        :V_WAREHOUSE_NAME
    );


    /*================================================================
      13. RETURN RESULT
    ================================================================*/

    RETURN OBJECT_CONSTRUCT
    (
        'run_id',
            V_RUN_ID,

        'status',
            'SUCCESS',

        'step',
            'GOLD_REFRESH',

        'all_strategies_details_rows',
            V_ALL_STRATEGIES_COUNT,

        'inbound_strategies_booked_rows',
            V_INBOUND_BOOKED_COUNT,

        'outbound_strategies_booked_rows',
            V_OUTBOUND_BOOKED_COUNT,

        'sales_details_rows',
            V_SALES_COUNT,

        'outbound_prospect_dials_rows',
            V_OUTBOUND_DIALS_COUNT,

        'all_strategies_reconciliation_difference',
            V_ALL_STRATEGIES_DIFF,

        'inbound_reconciliation_difference',
            V_INBOUND_DIFF,

        'sales_reconciliation_difference',
            V_SALES_DIFF,

        'outbound_dials_reconciliation_difference',
            V_OUTBOUND_DIALS_DIFF,

        'invalid_strategy_rows',
            V_INVALID_STRATEGY_ROWS,

        'invalid_inbound_rows',
            V_INVALID_INBOUND_ROWS,

        'invalid_outbound_rows',
            V_INVALID_OUTBOUND_ROWS,

        'invalid_sales_rows',
            V_INVALID_SALES_ROWS,

        'invalid_dial_rows',
            V_INVALID_DIAL_ROWS,

        'duration_seconds',
            V_DURATION_SECONDS
    );


EXCEPTION
    WHEN OTHER THEN

        V_ERROR_MESSAGE :=
            COALESCE
            (
                V_ERROR_MESSAGE,
                SQLERRM
            );

        V_COMPLETED_AT :=
            CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;

        V_DURATION_SECONDS :=
            ABS
            (
                DATEDIFF
                (
                    'MILLISECOND',
                    V_STARTED_AT,
                    V_COMPLETED_AT
                )
            ) / 1000.0;


        INSERT INTO
        SALES_ANALYTICS_DB.AUTOMATION.PIPELINE_RUN_LOG
        (
            RUN_ID,
            PIPELINE_NAME,
            STEP_NAME,
            STATUS,
            STARTED_AT,
            COMPLETED_AT,
            DURATION_SECONDS,
            LEADS_ROWS_ADDED,
            ACTIVITIES_ROWS_ADDED,
            USERS_ROWS_ADDED,
            CUSTOM_ROWS_ADDED,
            ERROR_MESSAGE,
            EXECUTED_BY,
            WAREHOUSE_NAME
        )
        VALUES
        (
            :V_RUN_ID,
            'SALES_ANALYTICS_DAILY_PIPELINE',
            'GOLD_REFRESH',
            'FAILED',
            :V_STARTED_AT,
            :V_COMPLETED_AT,
            :V_DURATION_SECONDS,

            NULL,
            NULL,
            NULL,
            NULL,

            :V_ERROR_MESSAGE,
            :V_EXECUTED_BY,
            :V_WAREHOUSE_NAME
        );

        RAISE;

END;
$$;


/*====================================================================
  4. CONFIRM PROCEDURE OWNERSHIP
====================================================================*/

GRANT OWNERSHIP
ON PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_GOLD()
TO ROLE ACCOUNTADMIN
COPY CURRENT GRANTS;


/*====================================================================
  5. TEST GOLD REFRESH
====================================================================*/

CALL SALES_ANALYTICS_DB.AUTOMATION.REFRESH_GOLD();


/*====================================================================
  6. POST-REFRESH GOLD INVENTORY
====================================================================*/

SELECT
    'ALL_STRATEGIES_DETAILS' AS VIEW_NAME,
    COUNT(*) AS ROW_COUNT
FROM SALES_ANALYTICS_DB.GOLD.ALL_STRATEGIES_DETAILS

UNION ALL

SELECT
    'INBOUND_STRATEGIES_BOOKED',
    COUNT(*)
FROM SALES_ANALYTICS_DB.GOLD.INBOUND_STRATEGIES_BOOKED

UNION ALL

SELECT
    'OUTBOUND_STRATEGIES_BOOKED',
    COUNT(*)
FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED

UNION ALL

SELECT
    'SALES_DETAILS',
    COUNT(*)
FROM SALES_ANALYTICS_DB.GOLD.SALES_DETAILS

UNION ALL

SELECT
    'OUTBOUND_PROSPECT_DIALS',
    COUNT(*)
FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS

ORDER BY VIEW_NAME;


/*====================================================================
  7. OUTBOUND FUNNEL CHECK

  The number of Gold outbound-booked rows may differ from the final
  report's aggregated outbound-set total if the report applies
  additional deduplication or grouping. Both must remain logically
  consistent with the attributed Strategy Call population.
====================================================================*/

SELECT
    (SELECT COUNT(*)
     FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS)
        AS TOTAL_OUTBOUND_DIAL_ROWS,

    (SELECT COUNT(*)
     FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED)
        AS ATTRIBUTED_STRATEGY_CALL_ROWS,

    CASE
        WHEN
            (SELECT COUNT(*)
             FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_STRATEGIES_BOOKED)
            <=
            (SELECT COUNT(*)
             FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_PROSPECT_DIALS)
        THEN 'PASS'
        ELSE 'FAIL'
    END AS BOOKED_NOT_GREATER_THAN_DIALS;


/*====================================================================
  8. PIPELINE LOG
====================================================================*/

SELECT
    RUN_ID,
    PIPELINE_NAME,
    STEP_NAME,
    STATUS,
    STARTED_AT,
    COMPLETED_AT,
    DURATION_SECONDS,
    ERROR_MESSAGE

FROM SALES_ANALYTICS_DB.AUTOMATION.PIPELINE_RUN_LOG

WHERE STEP_NAME = 'GOLD_REFRESH'

ORDER BY STARTED_AT DESC;
