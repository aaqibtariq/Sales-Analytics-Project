# Final Daily Pipeline Automation

## Purpose

This deployment creates the master Snowflake orchestration procedure for the Sales Analytics pipeline.

The master procedure runs the tested automation steps in dependency order:

```text
LOAD_BRONZE_INCREMENTAL()
    ↓
REFRESH_SILVER()
    ↓
REFRESH_GOLD()
    ↓
REFRESH_REPORTS()
    ↓
Write overall DAILY_PIPELINE status
```

Each child procedure already performs its own validation and logging. The master procedure stops immediately when any child step fails and writes one overall failure record.

---

# 1. One-time privilege setup

```sql
USE ROLE ACCOUNTADMIN;

GRANT USAGE
ON DATABASE SALES_ANALYTICS_DB
TO ROLE ACCOUNTADMIN;

GRANT USAGE
ON SCHEMA SALES_ANALYTICS_DB.AUTOMATION
TO ROLE ACCOUNTADMIN;

GRANT USAGE
ON WAREHOUSE COMPUTE_WH
TO ROLE ACCOUNTADMIN;

GRANT SELECT, INSERT
ON ALL TABLES IN SCHEMA SALES_ANALYTICS_DB.AUTOMATION
TO ROLE ACCOUNTADMIN;

GRANT SELECT, INSERT
ON FUTURE TABLES IN SCHEMA SALES_ANALYTICS_DB.AUTOMATION
TO ROLE ACCOUNTADMIN;
```

---

# 2. Confirm required procedures exist

```sql
SHOW PROCEDURES IN SCHEMA SALES_ANALYTICS_DB.AUTOMATION;
```

Confirm these procedures are listed:

```text
LOAD_BRONZE_INCREMENTAL
REFRESH_SILVER
REFRESH_GOLD
REFRESH_INBOUND_REPORT
REFRESH_OUTBOUND_REPORT
REFRESH_CLOSER_REPORT
REFRESH_OBJECTIONS_REPORT
REFRESH_REPORTS
```

---

# 3. Create `RUN_DAILY_PIPELINE()`

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA AUTOMATION;


CREATE OR REPLACE PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.RUN_DAILY_PIPELINE()
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

    V_CURRENT_STEP STRING DEFAULT 'INITIALIZATION';
    V_ERROR_MESSAGE STRING DEFAULT NULL;
    V_PIPELINE_ERROR STRING DEFAULT NULL;

    V_BRONZE_RESULT VARIANT;
    V_SILVER_RESULT VARIANT;
    V_GOLD_RESULT VARIANT;
    V_REPORT_RESULT VARIANT;

BEGIN

    /*==============================================================
      1. BRONZE INCREMENTAL LOAD
    ==============================================================*/

    V_CURRENT_STEP := 'BRONZE_INCREMENTAL_LOAD';

    CALL SALES_ANALYTICS_DB.AUTOMATION.LOAD_BRONZE_INCREMENTAL()
        INTO :V_BRONZE_RESULT;


    /*==============================================================
      2. SILVER REFRESH

      This runs only after Bronze returns successfully.
    ==============================================================*/

    V_CURRENT_STEP := 'SILVER_REFRESH';

    CALL SALES_ANALYTICS_DB.AUTOMATION.REFRESH_SILVER()
        INTO :V_SILVER_RESULT;


    /*==============================================================
      3. GOLD REFRESH

      This runs only after Silver returns successfully.
    ==============================================================*/

    V_CURRENT_STEP := 'GOLD_REFRESH';

    CALL SALES_ANALYTICS_DB.AUTOMATION.REFRESH_GOLD()
        INTO :V_GOLD_RESULT;


    /*==============================================================
      4. REPORT REFRESH AND VALIDATION

      This runs only after Gold returns successfully.
    ==============================================================*/

    V_CURRENT_STEP := 'REPORT_REFRESH';

    CALL SALES_ANALYTICS_DB.AUTOMATION.REFRESH_REPORTS()
        INTO :V_REPORT_RESULT;


    /*==============================================================
      5. LOG OVERALL SUCCESS
    ==============================================================*/

    V_CURRENT_STEP := 'DAILY_PIPELINE_COMPLETE';

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
        'DAILY_PIPELINE',
        'SUCCESS',
        :V_STARTED_AT,
        :V_COMPLETED_AT,
        :V_DURATION_SECONDS,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        :V_EXECUTED_BY,
        :V_WAREHOUSE_NAME
    );


    /*==============================================================
      6. RETURN COMPLETE PIPELINE RESULT
    ==============================================================*/

    RETURN OBJECT_CONSTRUCT(
        'run_id',
            V_RUN_ID,

        'pipeline_name',
            'SALES_ANALYTICS_DAILY_PIPELINE',

        'status',
            'SUCCESS',

        'step',
            'DAILY_PIPELINE',

        'started_at',
            V_STARTED_AT,

        'completed_at',
            V_COMPLETED_AT,

        'duration_seconds',
            V_DURATION_SECONDS,

        'bronze_result',
            V_BRONZE_RESULT,

        'silver_result',
            V_SILVER_RESULT,

        'gold_result',
            V_GOLD_RESULT,

        'report_result',
            V_REPORT_RESULT
    );


EXCEPTION
    WHEN OTHER THEN

        /*----------------------------------------------------------
          Preserve the child-procedure or SQL error.
        ----------------------------------------------------------*/

        V_ERROR_MESSAGE :=
            COALESCE(
                V_ERROR_MESSAGE,
                SQLERRM
            );

        V_PIPELINE_ERROR :=
              'Failed during '
            || V_CURRENT_STEP
            || '. '
            || V_ERROR_MESSAGE;

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


        /*==========================================================
          7. LOG OVERALL FAILURE

          V_CURRENT_STEP records the pipeline stage that was active
          when the error occurred.
        ==========================================================*/

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
            'DAILY_PIPELINE',
            'FAILED',
            :V_STARTED_AT,
            :V_COMPLETED_AT,
            :V_DURATION_SECONDS,
            NULL,
            NULL,
            NULL,
            NULL,
            :V_PIPELINE_ERROR,
            :V_EXECUTED_BY,
            :V_WAREHOUSE_NAME
        );

        RAISE;

END;
$$;
```

---

# 4. Confirm procedure ownership

```sql
GRANT OWNERSHIP
ON PROCEDURE
SALES_ANALYTICS_DB.AUTOMATION.RUN_DAILY_PIPELINE()
TO ROLE ACCOUNTADMIN
COPY CURRENT GRANTS;
```

Confirm the procedure:

```sql
SHOW PROCEDURES LIKE 'RUN_DAILY_PIPELINE'
IN SCHEMA SALES_ANALYTICS_DB.AUTOMATION;
```

---

# 5. Run the first end-to-end test manually

Run this before creating or resuming a scheduled task:

```sql
CALL SALES_ANALYTICS_DB.AUTOMATION.RUN_DAILY_PIPELINE();
```

Because the current S3 files were already loaded, Bronze can legitimately report zero new rows. Silver, Gold, and reports should still refresh and validate successfully.

---

# 6. Verify the overall pipeline log

```sql
SELECT
    RUN_ID,
    PIPELINE_NAME,
    STEP_NAME,
    STATUS,
    STARTED_AT,
    COMPLETED_AT,
    DURATION_SECONDS,
    ERROR_MESSAGE,
    EXECUTED_BY,
    WAREHOUSE_NAME

FROM SALES_ANALYTICS_DB.AUTOMATION.PIPELINE_RUN_LOG

WHERE STEP_NAME = 'DAILY_PIPELINE'

ORDER BY STARTED_AT DESC;
```

Expected:

```text
STEP_NAME = DAILY_PIPELINE
STATUS = SUCCESS
ERROR_MESSAGE = NULL
```

---

# 7. Verify all steps for the latest run period

```sql
SELECT
    RUN_ID,
    STEP_NAME,
    STATUS,
    STARTED_AT,
    COMPLETED_AT,
    DURATION_SECONDS,
    LEADS_ROWS_ADDED,
    ACTIVITIES_ROWS_ADDED,
    USERS_ROWS_ADDED,
    CUSTOM_ROWS_ADDED,
    ERROR_MESSAGE

FROM SALES_ANALYTICS_DB.AUTOMATION.PIPELINE_RUN_LOG

WHERE STARTED_AT >= DATEADD(
    'HOUR',
    -6,
    CURRENT_TIMESTAMP()
)

ORDER BY STARTED_AT;
```

A successful execution should include entries for:

```text
BRONZE_INCREMENTAL_LOAD
SILVER_REFRESH
GOLD_REFRESH
REPORT_REFRESH
DAILY_PIPELINE
```

---

# 8. Optional daily Snowflake task

Create the task only after the manual master-procedure test returns `SUCCESS`.

The schedule below runs at **8:30 AM America/New_York** every day. This assumes the AWS Glue extraction has completed before 8:30 AM. Adjust the schedule if the Glue job normally finishes later.

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA AUTOMATION;


CREATE OR REPLACE TASK
SALES_ANALYTICS_DB.AUTOMATION.DAILY_SALES_ANALYTICS_TASK
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = 'USING CRON 30 8 * * * America/New_York'
AS
    CALL SALES_ANALYTICS_DB.AUTOMATION.RUN_DAILY_PIPELINE();
```

Tasks are created in a suspended state. Resume the task only after confirming its definition:

```sql
SHOW TASKS LIKE 'DAILY_SALES_ANALYTICS_TASK'
IN SCHEMA SALES_ANALYTICS_DB.AUTOMATION;
```

Resume:

```sql
ALTER TASK
SALES_ANALYTICS_DB.AUTOMATION.DAILY_SALES_ANALYTICS_TASK
RESUME;
```

---

# 9. Verify task status and history

Check task status:

```sql
SHOW TASKS LIKE 'DAILY_SALES_ANALYTICS_TASK'
IN SCHEMA SALES_ANALYTICS_DB.AUTOMATION;
```

Check recent and upcoming executions:

```sql
SELECT
    NAME,
    STATE,
    SCHEDULED_TIME,
    QUERY_START_TIME,
    COMPLETED_TIME,
    RETURN_VALUE,
    ERROR_CODE,
    ERROR_MESSAGE

FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.TASK_HISTORY(
        TASK_NAME =>
            'SALES_ANALYTICS_DB.AUTOMATION.DAILY_SALES_ANALYTICS_TASK',

        SCHEDULED_TIME_RANGE_START =>
            DATEADD(
                'DAY',
                -7,
                CURRENT_TIMESTAMP()
            ),

        RESULT_LIMIT => 100
    )
)

ORDER BY SCHEDULED_TIME DESC;
```

---

# 10. Test the task immediately

To test the task without waiting for the scheduled time:

```sql
EXECUTE TASK
SALES_ANALYTICS_DB.AUTOMATION.DAILY_SALES_ANALYTICS_TASK;
```

Then check task history and `PIPELINE_RUN_LOG`.

---

# 11. Pause or change the schedule

Suspend the task:

```sql
ALTER TASK
SALES_ANALYTICS_DB.AUTOMATION.DAILY_SALES_ANALYTICS_TASK
SUSPEND;
```

Change the schedule:

```sql
ALTER TASK
SALES_ANALYTICS_DB.AUTOMATION.DAILY_SALES_ANALYTICS_TASK
SET SCHEDULE = 'USING CRON 0 9 * * * America/New_York';
```

Resume after changing it:

```sql
ALTER TASK
SALES_ANALYTICS_DB.AUTOMATION.DAILY_SALES_ANALYTICS_TASK
RESUME;
```

---

# 12. Failure behavior

```text
Bronze failure
    ↓
Silver does not run
    ↓
Gold does not run
    ↓
Reports do not run
    ↓
DAILY_PIPELINE = FAILED
```

The same stop behavior applies when Silver, Gold, or report validation fails.

Each completed child step writes its own log entry. The master procedure writes one overall `DAILY_PIPELINE` entry.

---

# 13. Retry behavior

- Bronze retries are safe because `FORCE = FALSE` skips files already recorded in Snowflake load history.
- Silver uses idempotent `MERGE` and controlled rebuild logic.
- Gold safely redeploys views.
- Report procedures validate current report views.
- Rerun `RUN_DAILY_PIPELINE()` after correcting the failure.
- Do not use `FORCE = TRUE` during a normal retry.

---

# 14. Final production flow

```text
PostgreSQL source
    ↓
AWS Glue Python Shell incremental extraction
    ↓
Amazon S3 raw JSON
    ↓
Snowflake task
    ↓
RUN_DAILY_PIPELINE()
    ├── LOAD_BRONZE_INCREMENTAL()
    ├── REFRESH_SILVER()
    ├── REFRESH_GOLD()
    └── REFRESH_REPORTS()
    ↓
Streamlit reads refreshed report views
```
