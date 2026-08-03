# inbound procedure

```
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA AUTOMATION;


CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_INBOUND_REPORT()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    V_ROW_COUNT NUMBER DEFAULT 0;

    V_INBOUND_BOOKED NUMBER DEFAULT 0;
    V_INBOUND_TAKEN NUMBER DEFAULT 0;

    V_STRATEGY_BOOKED NUMBER DEFAULT 0;
    V_STRATEGY_TAKEN NUMBER DEFAULT 0;

    V_TOTAL_OFFERS NUMBER DEFAULT 0;
    V_TOTAL_SALES NUMBER DEFAULT 0;

    V_INBOUND_SHOW_RATE NUMBER(18,2) DEFAULT 0;
    V_TRIAGE_SET_RATE NUMBER(18,2) DEFAULT 0;
    V_STRATEGY_SHOW_RATE NUMBER(18,2) DEFAULT 0;
    V_OFFER_RATE NUMBER(18,2) DEFAULT 0;
    V_SALE_RATE NUMBER(18,2) DEFAULT 0;

    V_ERROR_MESSAGE STRING DEFAULT NULL;

    E_INBOUND_VALIDATION_FAILED EXCEPTION
        (-20101, 'Inbound report validation failed.');

BEGIN

    /*==============================================================
      1. CAPTURE AGGREGATE REPORT TOTALS
    ==============================================================*/

    SELECT
        COUNT(*),

        COALESCE(
            SUM(INBOUND_BOOKED),
            0
        ),

        COALESCE(
            SUM(INBOUND_TAKEN),
            0
        ),

        COALESCE(
            SUM(STRATEGY_CALL_BOOKED),
            0
        ),

        COALESCE(
            SUM(STRATEGY_CALL_TAKEN),
            0
        ),

        COALESCE(
            SUM(OFFERS_PRESENTED),
            0
        ),

        COALESCE(
            SUM(TOTAL_SALES),
            0
        )

    INTO
        :V_ROW_COUNT,
        :V_INBOUND_BOOKED,
        :V_INBOUND_TAKEN,
        :V_STRATEGY_BOOKED,
        :V_STRATEGY_TAKEN,
        :V_TOTAL_OFFERS,
        :V_TOTAL_SALES

    FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT;


    /*==============================================================
      2. CALCULATE AGGREGATE RATES

      Aggregate validation avoids false failures caused by individual
      date/setter rows with zero denominators.
    ==============================================================*/

    V_INBOUND_SHOW_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_INBOUND_TAKEN
                / NULLIF(
                    V_INBOUND_BOOKED,
                    0
                ),
                2
            ),
            0
        );


    V_TRIAGE_SET_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_STRATEGY_BOOKED
                / NULLIF(
                    V_INBOUND_TAKEN,
                    0
                ),
                2
            ),
            0
        );


    V_STRATEGY_SHOW_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_STRATEGY_TAKEN
                / NULLIF(
                    V_STRATEGY_BOOKED,
                    0
                ),
                2
            ),
            0
        );


    V_OFFER_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_TOTAL_OFFERS
                / NULLIF(
                    V_STRATEGY_TAKEN,
                    0
                ),
                2
            ),
            0
        );


    V_SALE_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_TOTAL_SALES
                / NULLIF(
                    V_STRATEGY_TAKEN,
                    0
                ),
                2
            ),
            0
        );


    /*==============================================================
      3. AGGREGATE FUNNEL VALIDATION
    ==============================================================*/

    IF
    (
        V_ROW_COUNT = 0

        OR V_INBOUND_TAKEN
           > V_INBOUND_BOOKED

        OR V_STRATEGY_BOOKED
           > V_INBOUND_TAKEN

        OR V_STRATEGY_TAKEN
           > V_STRATEGY_BOOKED

        OR V_TOTAL_OFFERS
           > V_STRATEGY_TAKEN

        OR V_TOTAL_SALES
           > V_STRATEGY_TAKEN

        OR V_INBOUND_SHOW_RATE
           NOT BETWEEN 0 AND 100

        OR V_TRIAGE_SET_RATE
           NOT BETWEEN 0 AND 100

        OR V_STRATEGY_SHOW_RATE
           NOT BETWEEN 0 AND 100

        OR V_OFFER_RATE
           NOT BETWEEN 0 AND 100

        OR V_SALE_RATE
           NOT BETWEEN 0 AND 100
    )
    THEN

        V_ERROR_MESSAGE :=
              'Inbound validation failed. rows='
            || V_ROW_COUNT
            || ', inbound booked='
            || V_INBOUND_BOOKED
            || ', inbound taken='
            || V_INBOUND_TAKEN
            || ', strategy booked='
            || V_STRATEGY_BOOKED
            || ', strategy taken='
            || V_STRATEGY_TAKEN
            || ', offers='
            || V_TOTAL_OFFERS
            || ', sales='
            || V_TOTAL_SALES
            || ', inbound show rate='
            || V_INBOUND_SHOW_RATE
            || ', triage set rate='
            || V_TRIAGE_SET_RATE
            || ', strategy show rate='
            || V_STRATEGY_SHOW_RATE
            || ', offer rate='
            || V_OFFER_RATE
            || ', sale rate='
            || V_SALE_RATE;

        RAISE E_INBOUND_VALIDATION_FAILED;

    END IF;


    /*==============================================================
      4. RETURN SUCCESS
    ==============================================================*/

    RETURN OBJECT_CONSTRUCT(
        'status',
            'SUCCESS',

        'report',
            'INBOUND_SETTER_REPORT',

        'row_count',
            V_ROW_COUNT,

        'inbound_booked',
            V_INBOUND_BOOKED,

        'inbound_taken',
            V_INBOUND_TAKEN,

        'strategy_call_booked',
            V_STRATEGY_BOOKED,

        'strategy_call_taken',
            V_STRATEGY_TAKEN,

        'offers_presented',
            V_TOTAL_OFFERS,

        'total_sales',
            V_TOTAL_SALES,

        'inbound_show_rate',
            V_INBOUND_SHOW_RATE,

        'triage_set_rate',
            V_TRIAGE_SET_RATE,

        'strategy_show_rate',
            V_STRATEGY_SHOW_RATE,

        'offer_rate',
            V_OFFER_RATE,

        'sale_rate',
            V_SALE_RATE
    );

END;
$$;


```



# Outbound report validation procedure

```


USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA AUTOMATION;


CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_INBOUND_REPORT()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    V_ROW_COUNT NUMBER DEFAULT 0;
    V_INBOUND_BOOKED NUMBER DEFAULT 0;
    V_INBOUND_TAKEN NUMBER DEFAULT 0;
    V_STRATEGY_BOOKED NUMBER DEFAULT 0;
    V_STRATEGY_TAKEN NUMBER DEFAULT 0;
    V_TOTAL_SALES NUMBER DEFAULT 0;
    V_INVALID_RATES NUMBER DEFAULT 0;
    V_ERROR_MESSAGE STRING DEFAULT NULL;

    E_INBOUND_VALIDATION_FAILED EXCEPTION
        (-20101, 'Inbound report validation failed.');
BEGIN

    SELECT
        COUNT(*),
        COALESCE(SUM(INBOUND_BOOKED), 0),
        COALESCE(SUM(INBOUND_TAKEN), 0),
        COALESCE(SUM(STRATEGY_CALL_BOOKED), 0),
        COALESCE(SUM(STRATEGY_CALL_TAKEN), 0),
        COALESCE(SUM(TOTAL_SALES), 0)
    INTO
        :V_ROW_COUNT,
        :V_INBOUND_BOOKED,
        :V_INBOUND_TAKEN,
        :V_STRATEGY_BOOKED,
        :V_STRATEGY_TAKEN,
        :V_TOTAL_SALES
    FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT;


    SELECT COUNT(*)
    INTO :V_INVALID_RATES
    FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT
    WHERE
           COALESCE(SHOW_RATE, 0) NOT BETWEEN 0 AND 100
        OR COALESCE(TRIAGE_SET_RATE, 0) NOT BETWEEN 0 AND 100
        OR COALESCE(OFFER_RATE, 0) NOT BETWEEN 0 AND 100
        OR COALESCE(SALE_RATE, 0) NOT BETWEEN 0 AND 100;


    IF
    (
        V_ROW_COUNT = 0
        OR V_INBOUND_TAKEN > V_INBOUND_BOOKED
        OR V_STRATEGY_TAKEN > V_STRATEGY_BOOKED
        OR V_TOTAL_SALES > V_STRATEGY_TAKEN
        OR V_INVALID_RATES > 0
    )
    THEN
        V_ERROR_MESSAGE :=
              'Inbound validation failed. rows='
            || V_ROW_COUNT
            || ', inbound booked='
            || V_INBOUND_BOOKED
            || ', inbound taken='
            || V_INBOUND_TAKEN
            || ', strategy booked='
            || V_STRATEGY_BOOKED
            || ', strategy taken='
            || V_STRATEGY_TAKEN
            || ', sales='
            || V_TOTAL_SALES
            || ', invalid rates='
            || V_INVALID_RATES;

        RAISE E_INBOUND_VALIDATION_FAILED;
    END IF;


    RETURN OBJECT_CONSTRUCT(
        'status', 'SUCCESS',
        'report', 'INBOUND_SETTER_REPORT',
        'row_count', V_ROW_COUNT,
        'inbound_booked', V_INBOUND_BOOKED,
        'inbound_taken', V_INBOUND_TAKEN,
        'strategy_call_booked', V_STRATEGY_BOOKED,
        'strategy_call_taken', V_STRATEGY_TAKEN,
        'total_sales', V_TOTAL_SALES,
        'invalid_rates', V_INVALID_RATES
    );

END;
$$;

```


# closer procedure

```
CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_CLOSER_REPORT()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    V_ROW_COUNT NUMBER DEFAULT 0;

    V_STRATEGY_CALLS NUMBER DEFAULT 0;
    V_STRATEGY_CALL_TAKEN NUMBER DEFAULT 0;
    V_OFFERS_PRESENTED NUMBER DEFAULT 0;
    V_TOTAL_SALES NUMBER DEFAULT 0;

    V_TOTAL_CONTRACT_VALUE NUMBER(38,2) DEFAULT 0;
    V_TOTAL_CASH_COLLECTED NUMBER(38,2) DEFAULT 0;

    V_SHOW_RATE NUMBER(18,2) DEFAULT 0;
    V_OFFER_RATE NUMBER(18,2) DEFAULT 0;
    V_SALE_RATE NUMBER(18,2) DEFAULT 0;
    V_OFFER_TO_SALE_RATE NUMBER(18,2) DEFAULT 0;

    V_INVALID_NEGATIVE_ROWS NUMBER DEFAULT 0;

    V_ERROR_MESSAGE STRING DEFAULT NULL;

    E_CLOSER_VALIDATION_FAILED EXCEPTION
        (-20103, 'Closer report validation failed.');

BEGIN

    /*==============================================================
      1. CAPTURE AGGREGATE CLOSER TOTALS
    ==============================================================*/

    SELECT
        COUNT(*),

        COALESCE(
            SUM(STRATEGY_CALLS),
            0
        ),

        COALESCE(
            SUM(STRATEGY_CALL_TAKEN),
            0
        ),

        COALESCE(
            SUM(OFFERS_PRESENTED),
            0
        ),

        COALESCE(
            SUM(TOTAL_SALES),
            0
        ),

        COALESCE(
            SUM(TOTAL_CONTRACT_VALUE),
            0
        ),

        COALESCE(
            SUM(TOTAL_CASH_COLLECTED),
            0
        )

    INTO
        :V_ROW_COUNT,
        :V_STRATEGY_CALLS,
        :V_STRATEGY_CALL_TAKEN,
        :V_OFFERS_PRESENTED,
        :V_TOTAL_SALES,
        :V_TOTAL_CONTRACT_VALUE,
        :V_TOTAL_CASH_COLLECTED

    FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT;


    /*==============================================================
      2. CALCULATE AGGREGATE RATES
    ==============================================================*/

    V_SHOW_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_STRATEGY_CALL_TAKEN
                / NULLIF(
                    V_STRATEGY_CALLS,
                    0
                ),
                2
            ),
            0
        );


    V_OFFER_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_OFFERS_PRESENTED
                / NULLIF(
                    V_STRATEGY_CALL_TAKEN,
                    0
                ),
                2
            ),
            0
        );


    V_SALE_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_TOTAL_SALES
                / NULLIF(
                    V_STRATEGY_CALL_TAKEN,
                    0
                ),
                2
            ),
            0
        );


    V_OFFER_TO_SALE_RATE :=
        COALESCE(
            ROUND(
                100.0
                * V_TOTAL_SALES
                / NULLIF(
                    V_OFFERS_PRESENTED,
                    0
                ),
                2
            ),
            0
        );


    /*==============================================================
      3. INVALID NEGATIVE VALUE CHECK
    ==============================================================*/

    SELECT COUNT(*)
    INTO :V_INVALID_NEGATIVE_ROWS

    FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT

    WHERE
           COALESCE(
               STRATEGY_CALLS,
               0
           ) < 0

        OR COALESCE(
               STRATEGY_CALL_TAKEN,
               0
           ) < 0

        OR COALESCE(
               OFFERS_PRESENTED,
               0
           ) < 0

        OR COALESCE(
               TOTAL_SALES,
               0
           ) < 0

        OR COALESCE(
               TOTAL_CONTRACT_VALUE,
               0
           ) < 0

        OR COALESCE(
               TOTAL_CASH_COLLECTED,
               0
           ) < 0;


    /*==============================================================
      4. AGGREGATE CLOSER FUNNEL VALIDATION
    ==============================================================*/

    IF
    (
        V_ROW_COUNT = 0

        OR V_STRATEGY_CALL_TAKEN
           > V_STRATEGY_CALLS

        OR V_OFFERS_PRESENTED
           > V_STRATEGY_CALL_TAKEN

        OR V_TOTAL_SALES
           > V_STRATEGY_CALL_TAKEN

        OR V_SHOW_RATE
           NOT BETWEEN 0 AND 100

        OR V_OFFER_RATE
           NOT BETWEEN 0 AND 100

        OR V_SALE_RATE
           NOT BETWEEN 0 AND 100

        OR V_OFFER_TO_SALE_RATE
           NOT BETWEEN 0 AND 100

        OR V_INVALID_NEGATIVE_ROWS > 0
    )
    THEN

        V_ERROR_MESSAGE :=
              'Closer validation failed. rows='
            || V_ROW_COUNT
            || ', strategy calls='
            || V_STRATEGY_CALLS
            || ', strategy calls taken='
            || V_STRATEGY_CALL_TAKEN
            || ', offers='
            || V_OFFERS_PRESENTED
            || ', sales='
            || V_TOTAL_SALES
            || ', contract value='
            || V_TOTAL_CONTRACT_VALUE
            || ', cash collected='
            || V_TOTAL_CASH_COLLECTED
            || ', show rate='
            || V_SHOW_RATE
            || ', offer rate='
            || V_OFFER_RATE
            || ', sale rate='
            || V_SALE_RATE
            || ', offer-to-sale rate='
            || V_OFFER_TO_SALE_RATE
            || ', invalid negative rows='
            || V_INVALID_NEGATIVE_ROWS;

        RAISE E_CLOSER_VALIDATION_FAILED;

    END IF;


    /*==============================================================
      5. RETURN SUCCESS
    ==============================================================*/

    RETURN OBJECT_CONSTRUCT(
        'status',
            'SUCCESS',

        'report',
            'CLOSER_REPORT',

        'row_count',
            V_ROW_COUNT,

        'strategy_calls',
            V_STRATEGY_CALLS,

        'strategy_call_taken',
            V_STRATEGY_CALL_TAKEN,

        'offers_presented',
            V_OFFERS_PRESENTED,

        'total_sales',
            V_TOTAL_SALES,

        'total_contract_value',
            V_TOTAL_CONTRACT_VALUE,

        'total_cash_collected',
            V_TOTAL_CASH_COLLECTED,

        'show_rate',
            V_SHOW_RATE,

        'offer_rate',
            V_OFFER_RATE,

        'sale_rate',
            V_SALE_RATE,

        'offer_to_sale_rate',
            V_OFFER_TO_SALE_RATE,

        'invalid_negative_rows',
            V_INVALID_NEGATIVE_ROWS
    );

END;
$$;



```

# Objections report validation procedure

```

CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_OBJECTIONS_REPORT()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    V_ROW_COUNT NUMBER DEFAULT 0;
    V_TOTAL_CALLS NUMBER DEFAULT 0;

    V_MONEY_COUNT NUMBER DEFAULT 0;
    V_FEAR_COUNT NUMBER DEFAULT 0;
    V_HUNG_UP_COUNT NUMBER DEFAULT 0;
    V_LOGISTICAL_COUNT NUMBER DEFAULT 0;
    V_NO_OBJECTION_COUNT NUMBER DEFAULT 0;
    V_OTHER_COACHES_COUNT NUMBER DEFAULT 0;
    V_PARTNER_COUNT NUMBER DEFAULT 0;
    V_THINK_ABOUT_IT_COUNT NUMBER DEFAULT 0;
    V_TIME_COUNT NUMBER DEFAULT 0;
    V_TRUST_COUNT NUMBER DEFAULT 0;
    V_VALUE_COUNT NUMBER DEFAULT 0;
    V_NOT_LOOKING_COUNT NUMBER DEFAULT 0;

    V_INVALID_COUNTS NUMBER DEFAULT 0;
    V_ERROR_MESSAGE STRING DEFAULT NULL;

    E_OBJECTIONS_VALIDATION_FAILED EXCEPTION
        (-20104, 'Objections report validation failed.');
BEGIN

    SELECT
        COUNT(*),
        COALESCE(SUM(TOTAL_CALLS), 0),
        COALESCE(SUM(MONEY_COUNT), 0),
        COALESCE(SUM(FEAR_COUNT), 0),
        COALESCE(SUM(HUNG_UP_COUNT), 0),
        COALESCE(SUM(LOGISTICAL_COUNT), 0),
        COALESCE(SUM(NO_OBJ_COUNT), 0),
        COALESCE(SUM(OTHER_COACHES_COUNT), 0),
        COALESCE(SUM(PARTNER_COUNT), 0),
        COALESCE(SUM(THINK_ABT_IT_COUNT), 0),
        COALESCE(SUM(TIME_COUNT), 0),
        COALESCE(SUM(TRUST_COUNT), 0),
        COALESCE(SUM(VALUE_COUNT), 0),
        COALESCE(SUM(NOT_LOOKING_COUNT), 0)
    INTO
        :V_ROW_COUNT,
        :V_TOTAL_CALLS,
        :V_MONEY_COUNT,
        :V_FEAR_COUNT,
        :V_HUNG_UP_COUNT,
        :V_LOGISTICAL_COUNT,
        :V_NO_OBJECTION_COUNT,
        :V_OTHER_COACHES_COUNT,
        :V_PARTNER_COUNT,
        :V_THINK_ABOUT_IT_COUNT,
        :V_TIME_COUNT,
        :V_TRUST_COUNT,
        :V_VALUE_COUNT,
        :V_NOT_LOOKING_COUNT
    FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT;


    SELECT COUNT(*)
    INTO :V_INVALID_COUNTS
    FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT
    WHERE
           COALESCE(TOTAL_CALLS, 0) < 0
        OR COALESCE(MONEY_COUNT, 0) < 0
        OR COALESCE(FEAR_COUNT, 0) < 0
        OR COALESCE(HUNG_UP_COUNT, 0) < 0
        OR COALESCE(LOGISTICAL_COUNT, 0) < 0
        OR COALESCE(NO_OBJ_COUNT, 0) < 0
        OR COALESCE(OTHER_COACHES_COUNT, 0) < 0
        OR COALESCE(PARTNER_COUNT, 0) < 0
        OR COALESCE(THINK_ABT_IT_COUNT, 0) < 0
        OR COALESCE(TIME_COUNT, 0) < 0
        OR COALESCE(TRUST_COUNT, 0) < 0
        OR COALESCE(VALUE_COUNT, 0) < 0
        OR COALESCE(NOT_LOOKING_COUNT, 0) < 0;


    IF
    (
        V_ROW_COUNT = 0
        OR V_TOTAL_CALLS = 0
        OR V_INVALID_COUNTS > 0
    )
    THEN
        V_ERROR_MESSAGE :=
              'Objections validation failed. rows='
            || V_ROW_COUNT
            || ', total calls='
            || V_TOTAL_CALLS
            || ', invalid count rows='
            || V_INVALID_COUNTS;

        RAISE E_OBJECTIONS_VALIDATION_FAILED;
    END IF;


    RETURN OBJECT_CONSTRUCT(
        'status', 'SUCCESS',
        'report', 'OBJECTIONS_FACED_REPORT',
        'row_count', V_ROW_COUNT,
        'total_calls', V_TOTAL_CALLS,
        'money_count', V_MONEY_COUNT,
        'fear_count', V_FEAR_COUNT,
        'hung_up_count', V_HUNG_UP_COUNT,
        'logistical_count', V_LOGISTICAL_COUNT,
        'no_objection_count', V_NO_OBJECTION_COUNT,
        'other_coaches_count', V_OTHER_COACHES_COUNT,
        'partner_count', V_PARTNER_COUNT,
        'think_about_it_count', V_THINK_ABOUT_IT_COUNT,
        'time_count', V_TIME_COUNT,
        'trust_count', V_TRUST_COUNT,
        'value_count', V_VALUE_COUNT,
        'not_looking_count', V_NOT_LOOKING_COUNT,
        'invalid_count_rows', V_INVALID_COUNTS
    );

END;
$$;

```

# Master repot

```
CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_REPORTS()
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

    V_INBOUND_ROWS NUMBER DEFAULT 0;
    V_OUTBOUND_ROWS NUMBER DEFAULT 0;
    V_CLOSER_ROWS NUMBER DEFAULT 0;
    V_OBJECTION_ROWS NUMBER DEFAULT 0;

    V_INBOUND_RESULT VARIANT;
    V_OUTBOUND_RESULT VARIANT;
    V_CLOSER_RESULT VARIANT;
    V_OBJECTION_RESULT VARIANT;
BEGIN

    CALL SALES_ANALYTICS_DB.AUTOMATION
        .REFRESH_INBOUND_REPORT()
        INTO :V_INBOUND_RESULT;

    CALL SALES_ANALYTICS_DB.AUTOMATION
        .REFRESH_OUTBOUND_REPORT()
        INTO :V_OUTBOUND_RESULT;

    CALL SALES_ANALYTICS_DB.AUTOMATION
        .REFRESH_CLOSER_REPORT()
        INTO :V_CLOSER_RESULT;

    CALL SALES_ANALYTICS_DB.AUTOMATION
        .REFRESH_OBJECTIONS_REPORT()
        INTO :V_OBJECTION_RESULT;


    SELECT COUNT(*)
    INTO :V_INBOUND_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.INBOUND_SETTER_REPORT;

    SELECT COUNT(*)
    INTO :V_OUTBOUND_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.OUTBOUND_SETTER_REPORT;

    SELECT COUNT(*)
    INTO :V_CLOSER_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.CLOSER_REPORT;

    SELECT COUNT(*)
    INTO :V_OBJECTION_ROWS
    FROM SALES_ANALYTICS_DB.GOLD.OBJECTIONS_FACED_REPORT;


    V_COMPLETED_AT :=
        CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;

    V_DURATION_SECONDS :=
        ABS(
            DATEDIFF(
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
        'REPORT_REFRESH',
        'SUCCESS',
        :V_STARTED_AT,
        :V_COMPLETED_AT,
        :V_DURATION_SECONDS,

        :V_INBOUND_ROWS,
        :V_OUTBOUND_ROWS,
        :V_CLOSER_ROWS,
        :V_OBJECTION_ROWS,

        NULL,
        :V_EXECUTED_BY,
        :V_WAREHOUSE_NAME
    );


    RETURN OBJECT_CONSTRUCT(
        'run_id', V_RUN_ID,
        'status', 'SUCCESS',
        'step', 'REPORT_REFRESH',
        'duration_seconds', V_DURATION_SECONDS,
        'inbound_report', V_INBOUND_RESULT,
        'outbound_report', V_OUTBOUND_RESULT,
        'closer_report', V_CLOSER_RESULT,
        'objections_report', V_OBJECTION_RESULT
    );


EXCEPTION
    WHEN OTHER THEN

        V_ERROR_MESSAGE := SQLERRM;

        V_COMPLETED_AT :=
            CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;

        V_DURATION_SECONDS :=
            ABS(
                DATEDIFF(
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
            'REPORT_REFRESH',
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

```

# ChecK ownership

```
GRANT OWNERSHIP
ON PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_INBOUND_REPORT()
TO ROLE ACCOUNTADMIN
COPY CURRENT GRANTS;

GRANT OWNERSHIP
ON PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_OUTBOUND_REPORT()
TO ROLE ACCOUNTADMIN
COPY CURRENT GRANTS;

GRANT OWNERSHIP
ON PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_CLOSER_REPORT()
TO ROLE ACCOUNTADMIN
COPY CURRENT GRANTS;

GRANT OWNERSHIP
ON PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_OBJECTIONS_REPORT()
TO ROLE ACCOUNTADMIN
COPY CURRENT GRANTS;

GRANT OWNERSHIP
ON PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.REFRESH_REPORTS()
TO ROLE ACCOUNTADMIN
COPY CURRENT GRANTS;

```

# Test the report automation

```
CALL SALES_ANALYTICS_DB.AUTOMATION
    .REFRESH_INBOUND_REPORT();

CALL SALES_ANALYTICS_DB.AUTOMATION
    .REFRESH_OUTBOUND_REPORT();

CALL SALES_ANALYTICS_DB.AUTOMATION
    .REFRESH_CLOSER_REPORT();

CALL SALES_ANALYTICS_DB.AUTOMATION
    .REFRESH_OBJECTIONS_REPORT();

CALL SALES_ANALYTICS_DB.AUTOMATION.REFRESH_REPORTS();
