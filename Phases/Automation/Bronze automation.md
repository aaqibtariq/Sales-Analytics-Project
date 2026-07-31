

# update privileges

```

USE ROLE ACCOUNTADMIN;

GRANT USAGE
ON DATABASE SALES_ANALYTICS_DB
TO ROLE ACCOUNTADMIN;

GRANT USAGE
ON SCHEMA SALES_ANALYTICS_DB.BRONZE
TO ROLE ACCOUNTADMIN;

GRANT SELECT, INSERT
ON ALL TABLES IN SCHEMA SALES_ANALYTICS_DB.BRONZE
TO ROLE ACCOUNTADMIN;

GRANT SELECT, INSERT
ON FUTURE TABLES IN SCHEMA SALES_ANALYTICS_DB.BRONZE
TO ROLE ACCOUNTADMIN;

GRANT USAGE
ON STAGE SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE
TO ROLE ACCOUNTADMIN;

GRANT USAGE
ON FILE FORMAT SALES_ANALYTICS_DB.BRONZE.JSON_FF
TO ROLE ACCOUNTADMIN;

GRANT USAGE
ON WAREHOUSE COMPUTE_WH
TO ROLE ACCOUNTADMIN;


```
# Create the automation framework

```sql

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SALES_ANALYTICS_DB;

CREATE SCHEMA IF NOT EXISTS AUTOMATION;


CREATE TABLE IF NOT EXISTS
SALES_ANALYTICS_DB.AUTOMATION.PIPELINE_RUN_LOG
(
    RUN_ID                  STRING,
    PIPELINE_NAME           STRING,
    STEP_NAME               STRING,
    STATUS                  STRING,
    STARTED_AT              TIMESTAMP_LTZ,
    COMPLETED_AT            TIMESTAMP_LTZ,
    DURATION_SECONDS        NUMBER(18,3),

    LEADS_ROWS_ADDED        NUMBER,
    ACTIVITIES_ROWS_ADDED   NUMBER,
    USERS_ROWS_ADDED        NUMBER,
    CUSTOM_ROWS_ADDED       NUMBER,

    ERROR_MESSAGE           STRING,
    EXECUTED_BY             STRING,
    WAREHOUSE_NAME          STRING
);




```
# Create the production Bronze procedure

```


/*====================================================================
  SALES ANALYTICS
  CORRECTED BRONZE INCREMENTAL AUTOMATION PROCEDURE
====================================================================*/

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA AUTOMATION;


CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.LOAD_BRONZE_INCREMENTAL()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
    V_RUN_ID STRING DEFAULT UUID_STRING();
    V_STARTED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP();
    V_COMPLETED_AT TIMESTAMP_LTZ;

    V_EXECUTED_BY STRING;
    V_WAREHOUSE_NAME STRING;
    V_DURATION_SECONDS NUMBER(18,3);

    V_LEADS_BEFORE NUMBER DEFAULT 0;
    V_ACTIVITIES_BEFORE NUMBER DEFAULT 0;
    V_USERS_BEFORE NUMBER DEFAULT 0;
    V_CUSTOM_BEFORE NUMBER DEFAULT 0;

    V_LEADS_AFTER NUMBER DEFAULT 0;
    V_ACTIVITIES_AFTER NUMBER DEFAULT 0;
    V_USERS_AFTER NUMBER DEFAULT 0;
    V_CUSTOM_AFTER NUMBER DEFAULT 0;

    V_LEADS_ADDED NUMBER DEFAULT 0;
    V_ACTIVITIES_ADDED NUMBER DEFAULT 0;
    V_USERS_ADDED NUMBER DEFAULT 0;
    V_CUSTOM_ADDED NUMBER DEFAULT 0;

    V_NULL_JSON_ROWS NUMBER DEFAULT 0;
    V_NON_OBJECT_ROWS NUMBER DEFAULT 0;
    V_NULL_INSERT_DATE_ROWS NUMBER DEFAULT 0;

    V_ERROR_MESSAGE STRING DEFAULT NULL;

    E_BRONZE_VALIDATION_FAILED EXCEPTION
        (-20001, 'Bronze data-quality validation failed.');

BEGIN

    /*==============================================================
      1. CAPTURE SESSION INFORMATION
    ==============================================================*/

    V_EXECUTED_BY := CURRENT_USER();
    V_WAREHOUSE_NAME := CURRENT_WAREHOUSE();


    /*==============================================================
      2. CAPTURE COUNTS BEFORE LOAD
    ==============================================================*/

    SELECT COUNT(*)
      INTO :V_LEADS_BEFORE
    FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW;

    SELECT COUNT(*)
      INTO :V_ACTIVITIES_BEFORE
    FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW;

    SELECT COUNT(*)
      INTO :V_USERS_BEFORE
    FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW;

    SELECT COUNT(*)
      INTO :V_CUSTOM_BEFORE
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW;


    /*==============================================================
      3. LOAD NEW LEADS FILES
    ==============================================================*/

    COPY INTO SALES_ANALYTICS_DB.BRONZE.LEADS_RAW
    (
        JSON_OBJECT,
        INSERT_DATE
    )
    FROM
    (
        SELECT
            $1:raw_data,
            TRY_TO_TIMESTAMP_NTZ($1:insert_date::STRING)
        FROM
            @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/leads_raw
            (
                FILE_FORMAT =>
                    SALES_ANALYTICS_DB.BRONZE.JSON_FF
            )
    )
    PATTERN = '.*[.]json'
    ON_ERROR = 'ABORT_STATEMENT'
    FORCE = FALSE;


    /*==============================================================
      4. LOAD NEW LEAD-ACTIVITY FILES
    ==============================================================*/

    COPY INTO SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
    (
        JSON_OBJECT,
        INSERT_DATE
    )
    FROM
    (
        SELECT
            $1:raw_data,
            TRY_TO_TIMESTAMP_NTZ($1:insert_date::STRING)
        FROM
            @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/lead_activities_raw
            (
                FILE_FORMAT =>
                    SALES_ANALYTICS_DB.BRONZE.JSON_FF
            )
    )
    PATTERN = '.*[.]json'
    ON_ERROR = 'ABORT_STATEMENT'
    FORCE = FALSE;


    /*==============================================================
      5. LOAD NEW CRM-USER FILES
    ==============================================================*/

    COPY INTO SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW
    (
        JSON_OBJECT,
        INSERT_DATE
    )
    FROM
    (
        SELECT
            $1:raw_data,
            TRY_TO_TIMESTAMP_NTZ($1:insert_date::STRING)
        FROM
            @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/close_crm_users_raw
            (
                FILE_FORMAT =>
                    SALES_ANALYTICS_DB.BRONZE.JSON_FF
            )
    )
    PATTERN = '.*[.]json'
    ON_ERROR = 'ABORT_STATEMENT'
    FORCE = FALSE;


    /*==============================================================
      6. LOAD NEW CUSTOM-ACTIVITY FILES
    ==============================================================*/

    COPY INTO SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
    (
        JSON_OBJECT,
        INSERT_DATE
    )
    FROM
    (
        SELECT
            $1:raw_data,
            TRY_TO_TIMESTAMP_NTZ($1:insert_date::STRING)
        FROM
            @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/custom_activities_raw
            (
                FILE_FORMAT =>
                    SALES_ANALYTICS_DB.BRONZE.JSON_FF
            )
    )
    PATTERN = '.*[.]json'
    ON_ERROR = 'ABORT_STATEMENT'
    FORCE = FALSE;


    /*==============================================================
      7. CAPTURE COUNTS AFTER LOAD
    ==============================================================*/

    SELECT COUNT(*)
      INTO :V_LEADS_AFTER
    FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW;

    SELECT COUNT(*)
      INTO :V_ACTIVITIES_AFTER
    FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW;

    SELECT COUNT(*)
      INTO :V_USERS_AFTER
    FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW;

    SELECT COUNT(*)
      INTO :V_CUSTOM_AFTER
    FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW;


    V_LEADS_ADDED :=
        V_LEADS_AFTER - V_LEADS_BEFORE;

    V_ACTIVITIES_ADDED :=
        V_ACTIVITIES_AFTER - V_ACTIVITIES_BEFORE;

    V_USERS_ADDED :=
        V_USERS_AFTER - V_USERS_BEFORE;

    V_CUSTOM_ADDED :=
        V_CUSTOM_AFTER - V_CUSTOM_BEFORE;


    /*==============================================================
      8. AUTOMATED BRONZE QUALITY GATES
    ==============================================================*/

    SELECT
        COALESCE(SUM(NULL_JSON_ROWS), 0),
        COALESCE(SUM(NON_OBJECT_ROWS), 0),
        COALESCE(SUM(NULL_INSERT_DATE_ROWS), 0)
    INTO
        :V_NULL_JSON_ROWS,
        :V_NON_OBJECT_ROWS,
        :V_NULL_INSERT_DATE_ROWS
    FROM
    (
        SELECT
            COUNT_IF(JSON_OBJECT IS NULL) AS NULL_JSON_ROWS,
            COUNT_IF(
                JSON_OBJECT IS NOT NULL
                AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
            ) AS NON_OBJECT_ROWS,
            COUNT_IF(INSERT_DATE IS NULL) AS NULL_INSERT_DATE_ROWS
        FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW

        UNION ALL

        SELECT
            COUNT_IF(JSON_OBJECT IS NULL),
            COUNT_IF(
                JSON_OBJECT IS NOT NULL
                AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
            ),
            COUNT_IF(INSERT_DATE IS NULL)
        FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW

        UNION ALL

        SELECT
            COUNT_IF(JSON_OBJECT IS NULL),
            COUNT_IF(
                JSON_OBJECT IS NOT NULL
                AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
            ),
            COUNT_IF(INSERT_DATE IS NULL)
        FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW

        UNION ALL

        SELECT
            COUNT_IF(JSON_OBJECT IS NULL),
            COUNT_IF(
                JSON_OBJECT IS NOT NULL
                AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
            ),
            COUNT_IF(INSERT_DATE IS NULL)
        FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
    );


    /*==============================================================
      9. FAIL WHEN BRONZE QUALITY CHECKS DO NOT PASS
    ==============================================================*/

    IF (
        V_NULL_JSON_ROWS > 0
        OR V_NON_OBJECT_ROWS > 0
        OR V_NULL_INSERT_DATE_ROWS > 0
    ) THEN

        V_ERROR_MESSAGE :=
              'Bronze validation failed. NULL JSON rows='
            || V_NULL_JSON_ROWS
            || ', non-object JSON rows='
            || V_NON_OBJECT_ROWS
            || ', NULL INSERT_DATE rows='
            || V_NULL_INSERT_DATE_ROWS;

        RAISE E_BRONZE_VALIDATION_FAILED;

    END IF;


    /*==============================================================
      10. PREPARE SUCCESS LOG VALUES

      Compute expressions before the INSERT.
    ==============================================================*/

    V_COMPLETED_AT := CURRENT_TIMESTAMP();

    V_DURATION_SECONDS :=
        DATEDIFF(
            'MILLISECOND',
            V_STARTED_AT,
            V_COMPLETED_AT
        ) / 1000.0;


    /*==============================================================
      11. LOG SUCCESS
    ==============================================================*/

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
        'BRONZE_INCREMENTAL_LOAD',
        'SUCCESS',
        :V_STARTED_AT,
        :V_COMPLETED_AT,
        :V_DURATION_SECONDS,
        :V_LEADS_ADDED,
        :V_ACTIVITIES_ADDED,
        :V_USERS_ADDED,
        :V_CUSTOM_ADDED,
        NULL,
        :V_EXECUTED_BY,
        :V_WAREHOUSE_NAME
    );


    RETURN OBJECT_CONSTRUCT(
        'run_id', V_RUN_ID,
        'status', 'SUCCESS',
        'step', 'BRONZE_INCREMENTAL_LOAD',
        'leads_rows_added', V_LEADS_ADDED,
        'lead_activities_rows_added', V_ACTIVITIES_ADDED,
        'crm_users_rows_added', V_USERS_ADDED,
        'custom_activities_rows_added', V_CUSTOM_ADDED,
        'null_json_rows', V_NULL_JSON_ROWS,
        'non_object_json_rows', V_NON_OBJECT_ROWS,
        'null_insert_date_rows', V_NULL_INSERT_DATE_ROWS,
        'duration_seconds', V_DURATION_SECONDS,
        'started_at', V_STARTED_AT,
        'completed_at', V_COMPLETED_AT
    );


EXCEPTION
    WHEN OTHER THEN

        /* Preserve the original error before executing another SQL statement. */
        V_ERROR_MESSAGE :=
            COALESCE(
                V_ERROR_MESSAGE,
                SQLERRM
            );

        V_COMPLETED_AT := CURRENT_TIMESTAMP();

        V_DURATION_SECONDS :=
            DATEDIFF(
                'MILLISECOND',
                V_STARTED_AT,
                V_COMPLETED_AT
            ) / 1000.0;

        V_EXECUTED_BY :=
            COALESCE(
                V_EXECUTED_BY,
                CURRENT_USER()
            );

        V_WAREHOUSE_NAME :=
            COALESCE(
                V_WAREHOUSE_NAME,
                CURRENT_WAREHOUSE()
            );


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
            'BRONZE_INCREMENTAL_LOAD',
            'FAILED',
            :V_STARTED_AT,
            :V_COMPLETED_AT,
            :V_DURATION_SECONDS,
            :V_LEADS_ADDED,
            :V_ACTIVITIES_ADDED,
            :V_USERS_ADDED,
            :V_CUSTOM_ADDED,
            :V_ERROR_MESSAGE,
            :V_EXECUTED_BY,
            :V_WAREHOUSE_NAME
        );

        RAISE;

END;
$$;




```

# Test the automated Bronze procedure

```
CALL SALES_ANALYTICS_DB.AUTOMATION.LOAD_BRONZE_INCREMENTAL();

```


# Result 

```
Expected result:

{
  "status": "SUCCESS",
  "step": "BRONZE_INCREMENTAL_LOAD",
  "leads_rows_added": 0,
  "lead_activities_rows_added": 0,
  "crm_users_rows_added": 0,
  "custom_activities_rows_added": 0
}

```

# Check the automated log

```

SELECT *
FROM SALES_ANALYTICS_DB.AUTOMATION.PIPELINE_RUN_LOG
ORDER BY STARTED_AT DESC;

```

