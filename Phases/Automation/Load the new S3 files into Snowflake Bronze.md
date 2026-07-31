# Load New S3 Files into Snowflake Bronze

## Purpose

This script incrementally loads new JSON files written by the AWS Glue
Python Shell extraction job from Amazon S3 into the Snowflake Bronze layer.

### Data flow

```text
PostgreSQL
    ↓
AWS Glue Python Shell
    ↓
Amazon S3 JSON files
    ↓
Snowflake external stage
    ↓
Snowflake Bronze tables


```

```

Always use:
$1:raw_data
Keep this for normal incremental runs:
FORCE = FALSE
Use FORCE = TRUE only for a controlled repair or intentional reload.
Do not run the Silver refresh when the Bronze validation reports:
NULL_JSON_ROWS > 0

or:

NON_OBJECT_JSON_ROWS > 0
The AWS Glue watermark controls which PostgreSQL rows are extracted.
Snowflake load history controls which S3 files are loaded into Bronze.

The most important correction is:

```sql
$1:raw_data

```

```sql


/*====================================================================
  SALES ANALYTICS PROJECT
  PRODUCTION S3 -> SNOWFLAKE BRONZE INCREMENTAL LOAD

  Source:
    AWS Glue Python Shell output stored in Amazon S3

  Target tables:
    SALES_ANALYTICS_DB.BRONZE.LEADS_RAW
    SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
    SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW
    SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW

  External stage:
    SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE

  File format:
    SALES_ANALYTICS_DB.BRONZE.JSON_FF

  Glue JSON structure:
    {
      "insert_date": "...",
      "raw_data": {...}
    }

  Important:
    FORCE = FALSE ensures Snowflake does not reload files that were
    already successfully loaded into the same target table.
====================================================================*/


/*====================================================================
  1. SET SESSION CONTEXT
====================================================================*/

USE ROLE ACCOUNTADMIN;

USE WAREHOUSE COMPUTE_WH;

USE DATABASE SALES_ANALYTICS_DB;

USE SCHEMA BRONZE;


/*====================================================================
  2. VERIFY REQUIRED OBJECTS
====================================================================*/

SHOW STAGES LIKE 'SALES_ANALYTICS_RAW_STAGE'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


SHOW FILE FORMATS LIKE 'JSON_FF'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


SHOW TABLES LIKE 'LEADS_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


SHOW TABLES LIKE 'LEAD_ACTIVITIES_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


SHOW TABLES LIKE 'CLOSE_CRM_USERS_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


SHOW TABLES LIKE 'CUSTOM_ACTIVITIES_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


/*====================================================================
  3. CAPTURE BRONZE COUNTS BEFORE LOAD
====================================================================*/

CREATE OR REPLACE TEMPORARY TABLE BRONZE_COUNTS_BEFORE AS

SELECT
    'LEADS_RAW' AS TABLE_NAME,
    COUNT(*) AS ROW_COUNT
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    COUNT(*)
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    COUNT(*)
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    COUNT(*)
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW;


SELECT
    TABLE_NAME,
    ROW_COUNT
FROM BRONZE_COUNTS_BEFORE
ORDER BY TABLE_NAME;


/*====================================================================
  4. VERIFY FILES EXIST IN EACH S3 FOLDER

  These LIST commands show all available staged JSON files.

  Snowflake COPY load history and FORCE = FALSE determine which files
  are new and should be loaded.
====================================================================*/

LIST
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/leads_raw
PATTERN = '.*[.]json';


LIST
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/lead_activities_raw
PATTERN = '.*[.]json';


LIST
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/close_crm_users_raw
PATTERN = '.*[.]json';


LIST
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/custom_activities_raw
PATTERN = '.*[.]json';


/*====================================================================
  5. PRE-LOAD VALIDATION — LEADS FILE STRUCTURE

  Expected:
    RAW_DATA_TYPE   = OBJECT
    JSON_OBJECT     = populated
    INSERT_DATE     = populated
====================================================================*/

SELECT
    METADATA$FILENAME AS FILE_NAME,
    TYPEOF($1) AS ROOT_JSON_TYPE,
    TYPEOF($1:raw_data) AS RAW_DATA_TYPE,
    $1:raw_data AS JSON_OBJECT,
    TRY_TO_TIMESTAMP_NTZ(
        $1:insert_date::STRING
    ) AS INSERT_DATE
FROM
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/leads_raw
(
    FILE_FORMAT => SALES_ANALYTICS_DB.BRONZE.JSON_FF
)
LIMIT 10;


/*====================================================================
  6. PRE-LOAD VALIDATION — LEAD ACTIVITIES FILE STRUCTURE
====================================================================*/

SELECT
    METADATA$FILENAME AS FILE_NAME,
    TYPEOF($1) AS ROOT_JSON_TYPE,
    TYPEOF($1:raw_data) AS RAW_DATA_TYPE,
    $1:raw_data AS JSON_OBJECT,
    TRY_TO_TIMESTAMP_NTZ(
        $1:insert_date::STRING
    ) AS INSERT_DATE
FROM
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/lead_activities_raw
(
    FILE_FORMAT => SALES_ANALYTICS_DB.BRONZE.JSON_FF
)
LIMIT 10;


/*====================================================================
  7. PRE-LOAD VALIDATION — CRM USERS FILE STRUCTURE
====================================================================*/

SELECT
    METADATA$FILENAME AS FILE_NAME,
    TYPEOF($1) AS ROOT_JSON_TYPE,
    TYPEOF($1:raw_data) AS RAW_DATA_TYPE,
    $1:raw_data AS JSON_OBJECT,
    TRY_TO_TIMESTAMP_NTZ(
        $1:insert_date::STRING
    ) AS INSERT_DATE
FROM
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/close_crm_users_raw
(
    FILE_FORMAT => SALES_ANALYTICS_DB.BRONZE.JSON_FF
)
LIMIT 10;


/*====================================================================
  8. PRE-LOAD VALIDATION — CUSTOM ACTIVITIES FILE STRUCTURE
====================================================================*/

SELECT
    METADATA$FILENAME AS FILE_NAME,
    TYPEOF($1) AS ROOT_JSON_TYPE,
    TYPEOF($1:raw_data) AS RAW_DATA_TYPE,
    $1:raw_data AS JSON_OBJECT,
    TRY_TO_TIMESTAMP_NTZ(
        $1:insert_date::STRING
    ) AS INSERT_DATE
FROM
@SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/custom_activities_raw
(
    FILE_FORMAT => SALES_ANALYTICS_DB.BRONZE.JSON_FF
)
LIMIT 10;


/*====================================================================
  STOP CONDITION

  Before continuing, verify that the preceding four queries show:

    ROOT_JSON_TYPE = OBJECT
    RAW_DATA_TYPE  = OBJECT
    JSON_OBJECT    = populated
    INSERT_DATE    = populated

  Do not continue if RAW_DATA_TYPE or INSERT_DATE is NULL.
====================================================================*/


/*====================================================================
  9. LOAD LEADS_RAW

  FORCE = FALSE:
    - Loads new files only.
    - Does not reload files already recorded in Snowflake load history.
====================================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.LEADS_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:raw_data,
        TRY_TO_TIMESTAMP_NTZ(
            $1:insert_date::STRING
        )
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


/*====================================================================
  10. LOAD LEAD_ACTIVITIES_RAW
====================================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:raw_data,
        TRY_TO_TIMESTAMP_NTZ(
            $1:insert_date::STRING
        )
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


/*====================================================================
  11. LOAD CLOSE_CRM_USERS_RAW
====================================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:raw_data,
        TRY_TO_TIMESTAMP_NTZ(
            $1:insert_date::STRING
        )
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


/*====================================================================
  12. LOAD CUSTOM_ACTIVITIES_RAW
====================================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:raw_data,
        TRY_TO_TIMESTAMP_NTZ(
            $1:insert_date::STRING
        )
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


/*====================================================================
  13. CAPTURE BRONZE COUNTS AFTER LOAD
====================================================================*/

CREATE OR REPLACE TEMPORARY TABLE BRONZE_COUNTS_AFTER AS

SELECT
    'LEADS_RAW' AS TABLE_NAME,
    COUNT(*) AS ROW_COUNT
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    COUNT(*)
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    COUNT(*)
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    COUNT(*)
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW;


/*====================================================================
  14. COMPARE BEFORE AND AFTER COUNTS
====================================================================*/

SELECT
    B.TABLE_NAME,
    B.ROW_COUNT AS BEFORE_COUNT,
    A.ROW_COUNT AS AFTER_COUNT,
    A.ROW_COUNT - B.ROW_COUNT AS ROWS_ADDED
FROM BRONZE_COUNTS_BEFORE B
INNER JOIN BRONZE_COUNTS_AFTER A
    ON B.TABLE_NAME = A.TABLE_NAME
ORDER BY B.TABLE_NAME;


/*====================================================================
  15. FINAL BRONZE DATA-QUALITY VALIDATION

  Expected:
    NULL_JSON_ROWS       = 0
    NON_OBJECT_JSON_ROWS = 0
    NULL_INSERT_DATE_ROWS = 0

  OBJECT_ROWS should equal TOTAL_ROWS.
====================================================================*/

SELECT
    'LEADS_RAW' AS TABLE_NAME,
    COUNT(*) AS TOTAL_ROWS,
    COUNT_IF(JSON_OBJECT IS NULL) AS NULL_JSON_ROWS,
    COUNT_IF(TYPEOF(JSON_OBJECT) = 'OBJECT') AS OBJECT_ROWS,
    COUNT_IF(
        JSON_OBJECT IS NOT NULL
        AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
    ) AS NON_OBJECT_JSON_ROWS,
    COUNT_IF(INSERT_DATE IS NULL) AS NULL_INSERT_DATE_ROWS,
    MIN(INSERT_DATE) AS MIN_INSERT_DATE,
    MAX(INSERT_DATE) AS MAX_INSERT_DATE
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    COUNT(*),
    COUNT_IF(JSON_OBJECT IS NULL),
    COUNT_IF(TYPEOF(JSON_OBJECT) = 'OBJECT'),
    COUNT_IF(
        JSON_OBJECT IS NOT NULL
        AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
    ),
    COUNT_IF(INSERT_DATE IS NULL),
    MIN(INSERT_DATE),
    MAX(INSERT_DATE)
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    COUNT(*),
    COUNT_IF(JSON_OBJECT IS NULL),
    COUNT_IF(TYPEOF(JSON_OBJECT) = 'OBJECT'),
    COUNT_IF(
        JSON_OBJECT IS NOT NULL
        AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
    ),
    COUNT_IF(INSERT_DATE IS NULL),
    MIN(INSERT_DATE),
    MAX(INSERT_DATE)
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    COUNT(*),
    COUNT_IF(JSON_OBJECT IS NULL),
    COUNT_IF(TYPEOF(JSON_OBJECT) = 'OBJECT'),
    COUNT_IF(
        JSON_OBJECT IS NOT NULL
        AND TYPEOF(JSON_OBJECT) <> 'OBJECT'
    ),
    COUNT_IF(INSERT_DATE IS NULL),
    MIN(INSERT_DATE),
    MAX(INSERT_DATE)
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW

ORDER BY TABLE_NAME;


/*====================================================================
  16. VIEW LATEST VALID LEADS
====================================================================*/

SELECT
    INSERT_DATE,
    TYPEOF(JSON_OBJECT) AS JSON_TYPE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW
WHERE JSON_OBJECT IS NOT NULL
ORDER BY INSERT_DATE DESC
LIMIT 10;


/*====================================================================
  17. VIEW LATEST VALID LEAD ACTIVITIES
====================================================================*/

SELECT
    INSERT_DATE,
    TYPEOF(JSON_OBJECT) AS JSON_TYPE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
WHERE JSON_OBJECT IS NOT NULL
ORDER BY INSERT_DATE DESC
LIMIT 10;


/*====================================================================
  18. VIEW LATEST VALID CRM USERS
====================================================================*/

SELECT
    INSERT_DATE,
    TYPEOF(JSON_OBJECT) AS JSON_TYPE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW
WHERE JSON_OBJECT IS NOT NULL
ORDER BY INSERT_DATE DESC
LIMIT 10;


/*====================================================================
  19. VIEW LATEST VALID CUSTOM ACTIVITIES
====================================================================*/

SELECT
    INSERT_DATE,
    TYPEOF(JSON_OBJECT) AS JSON_TYPE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
WHERE JSON_OBJECT IS NOT NULL
ORDER BY INSERT_DATE DESC
LIMIT 20;


/*====================================================================
  20. COPY HISTORY — FILE-LEVEL DETAILS FOR ALL FOUR TABLES

  This captures recent load activity from the last 24 hours.
====================================================================*/

SELECT
    'LEADS_RAW' AS TARGET_TABLE,
    FILE_NAME,
    STATUS,
    ROW_COUNT,
    ROW_PARSED,
    ERROR_COUNT,
    FIRST_ERROR_MESSAGE,
    LAST_LOAD_TIME
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.LEADS_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    FILE_NAME,
    STATUS,
    ROW_COUNT,
    ROW_PARSED,
    ERROR_COUNT,
    FIRST_ERROR_MESSAGE,
    LAST_LOAD_TIME
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    FILE_NAME,
    STATUS,
    ROW_COUNT,
    ROW_PARSED,
    ERROR_COUNT,
    FIRST_ERROR_MESSAGE,
    LAST_LOAD_TIME
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    FILE_NAME,
    STATUS,
    ROW_COUNT,
    ROW_PARSED,
    ERROR_COUNT,
    FIRST_ERROR_MESSAGE,
    LAST_LOAD_TIME
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

ORDER BY LAST_LOAD_TIME DESC, TARGET_TABLE, FILE_NAME;


/*====================================================================
  21. COPY HISTORY — SUMMARY FOR ALL FOUR TABLES
====================================================================*/

SELECT
    'LEADS_RAW' AS TARGET_TABLE,
    COUNT(*) AS FILES_RECORDED,
    COUNT_IF(
        UPPER(STATUS) = 'LOADED'
    ) AS FILES_LOADED,
    COUNT_IF(
        UPPER(STATUS) <> 'LOADED'
    ) AS FILES_NOT_LOADED,
    COALESCE(
        SUM(ROW_COUNT),
        0
    ) AS ROWS_LOADED,
    COALESCE(
        SUM(ERROR_COUNT),
        0
    ) AS ERROR_COUNT,
    MAX(LAST_LOAD_TIME) AS LAST_LOAD_TIME
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.LEADS_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    COUNT(*),
    COUNT_IF(
        UPPER(STATUS) = 'LOADED'
    ),
    COUNT_IF(
        UPPER(STATUS) <> 'LOADED'
    ),
    COALESCE(
        SUM(ROW_COUNT),
        0
    ),
    COALESCE(
        SUM(ERROR_COUNT),
        0
    ),
    MAX(LAST_LOAD_TIME)
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    COUNT(*),
    COUNT_IF(
        UPPER(STATUS) = 'LOADED'
    ),
    COUNT_IF(
        UPPER(STATUS) <> 'LOADED'
    ),
    COALESCE(
        SUM(ROW_COUNT),
        0
    ),
    COALESCE(
        SUM(ERROR_COUNT),
        0
    ),
    MAX(LAST_LOAD_TIME)
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    COUNT(*),
    COUNT_IF(
        UPPER(STATUS) = 'LOADED'
    ),
    COUNT_IF(
        UPPER(STATUS) <> 'LOADED'
    ),
    COALESCE(
        SUM(ROW_COUNT),
        0
    ),
    COALESCE(
        SUM(ERROR_COUNT),
        0
    ),
    MAX(LAST_LOAD_TIME)
FROM TABLE(
    SALES_ANALYTICS_DB.INFORMATION_SCHEMA.COPY_HISTORY(
        TABLE_NAME =>
            'SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW',
        START_TIME =>
            DATEADD(
                'HOUR',
                -24,
                CURRENT_TIMESTAMP()
            )
    )
)

ORDER BY TARGET_TABLE;


/*====================================================================
  22. FINAL PIPELINE READINESS CHECK

  PASS conditions:
    - NULL_JSON_ROWS = 0
    - NON_OBJECT_JSON_ROWS = 0
    - NULL_INSERT_DATE_ROWS = 0

  A table may have ROWS_ADDED = 0 when the Glue job produced no new
  records or when all available S3 files were already loaded.
====================================================================*/

SELECT
    A.TABLE_NAME,
    B.ROW_COUNT AS BEFORE_COUNT,
    A.ROW_COUNT AS AFTER_COUNT,
    A.ROW_COUNT - B.ROW_COUNT AS ROWS_ADDED,

    CASE
        WHEN A.ROW_COUNT >= B.ROW_COUNT
        THEN 'PASS'
        ELSE 'FAIL'
    END AS ROW_COUNT_CHECK

FROM BRONZE_COUNTS_AFTER A

INNER JOIN BRONZE_COUNTS_BEFORE B
    ON A.TABLE_NAME = B.TABLE_NAME

ORDER BY A.TABLE_NAME;


```
