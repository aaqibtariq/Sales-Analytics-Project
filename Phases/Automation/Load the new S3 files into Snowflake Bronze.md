```sql

/*==============================================================
  SALES ANALYTICS PROJECT
  INCREMENTAL S3 -> SNOWFLAKE BRONZE LOAD

  Correct objects:
    Stage:
      SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE

    File format:
      SALES_ANALYTICS_DB.BRONZE.JSON_FF

  Important:
    FORCE = FALSE prevents previously loaded files from reloading.
==============================================================*/


/*==============================================================
  1. SET CONTEXT
==============================================================*/

USE ROLE ACCOUNTADMIN;

USE WAREHOUSE COMPUTE_WH;

USE DATABASE SALES_ANALYTICS_DB;

USE SCHEMA BRONZE;


/*==============================================================
  2. VERIFY STAGE
==============================================================*/

SHOW STAGES LIKE 'SALES_ANALYTICS_RAW_STAGE'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


/*==============================================================
  3. VERIFY FILE FORMAT
==============================================================*/

SHOW FILE FORMATS LIKE 'JSON_FF'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


/*==============================================================
  4. VERIFY BRONZE TABLES
==============================================================*/

SHOW TABLES LIKE 'LEADS_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;

SHOW TABLES LIKE 'LEAD_ACTIVITIES_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;

SHOW TABLES LIKE 'CLOSE_CRM_USERS_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;

SHOW TABLES LIKE 'CUSTOM_ACTIVITIES_RAW'
IN SCHEMA SALES_ANALYTICS_DB.BRONZE;


/*==============================================================
  5. CAPTURE COUNTS BEFORE LOAD
==============================================================*/

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


SELECT *
FROM BRONZE_COUNTS_BEFORE
ORDER BY TABLE_NAME;


/*==============================================================
  6. VERIFY JULY 30 FILES ARE VISIBLE
==============================================================*/

LIST @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/leads_raw
PATTERN = '.*20260730.*[.]json';

LIST @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/lead_activities_raw
PATTERN = '.*20260730.*[.]json';

LIST @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/close_crm_users_raw
PATTERN = '.*20260730.*[.]json';

LIST @SALES_ANALYTICS_DB.BRONZE.SALES_ANALYTICS_RAW_STAGE/custom_activities_raw
PATTERN = '.*20260730.*[.]json';


/*==============================================================
  7. LOAD LEADS_RAW
==============================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.LEADS_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:json_object,
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


/*==============================================================
  8. LOAD LEAD_ACTIVITIES_RAW
==============================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:json_object,
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


/*==============================================================
  9. LOAD CLOSE_CRM_USERS_RAW
==============================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:json_object,
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


/*==============================================================
  10. LOAD CUSTOM_ACTIVITIES_RAW
==============================================================*/

COPY INTO SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
(
    JSON_OBJECT,
    INSERT_DATE
)
FROM
(
    SELECT
        $1:json_object,
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


/*==============================================================
  11. CAPTURE COUNTS AFTER LOAD
==============================================================*/

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


/*==============================================================
  12. COMPARE BEFORE AND AFTER COUNTS
==============================================================*/

SELECT
    B.TABLE_NAME,
    B.ROW_COUNT AS BEFORE_COUNT,
    A.ROW_COUNT AS AFTER_COUNT,
    A.ROW_COUNT - B.ROW_COUNT AS ROWS_ADDED
FROM BRONZE_COUNTS_BEFORE B
JOIN BRONZE_COUNTS_AFTER A
    ON B.TABLE_NAME = A.TABLE_NAME
ORDER BY B.TABLE_NAME;


/*==============================================================
  13. VERIFY TOTAL BRONZE COUNTS
==============================================================*/

SELECT
    'LEADS_RAW' AS TABLE_NAME,
    COUNT(*) AS TOTAL_ROWS
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
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW

ORDER BY TABLE_NAME;


/*==============================================================
  14. VALIDATE NULL INSERT_DATE VALUES
==============================================================*/

SELECT
    'LEADS_RAW' AS TABLE_NAME,
    COUNT_IF(
        INSERT_DATE IS NULL
    ) AS NULL_INSERT_DATE_ROWS
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    COUNT_IF(
        INSERT_DATE IS NULL
    )
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    COUNT_IF(
        INSERT_DATE IS NULL
    )
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    COUNT_IF(
        INSERT_DATE IS NULL
    )
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW

ORDER BY TABLE_NAME;


/*==============================================================
  15. VERIFY MAXIMUM INSERT_DATE
==============================================================*/

SELECT
    'LEADS_RAW' AS TABLE_NAME,
    MAX(INSERT_DATE) AS MAX_INSERT_DATE
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    MAX(INSERT_DATE)
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    MAX(INSERT_DATE)
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    MAX(INSERT_DATE)
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW

ORDER BY TABLE_NAME;


/*==============================================================
  16. VALIDATE JSON OBJECT TYPES
==============================================================*/

SELECT
    'LEADS_RAW' AS TABLE_NAME,
    COUNT(*) AS TOTAL_ROWS,
    COUNT_IF(
        JSON_OBJECT IS NULL
    ) AS NULL_JSON_ROWS,
    COUNT_IF(
        TYPEOF(JSON_OBJECT) = 'OBJECT'
    ) AS OBJECT_ROWS,
    COUNT_IF(
        TYPEOF(JSON_OBJECT) <> 'OBJECT'
        AND JSON_OBJECT IS NOT NULL
    ) AS NON_OBJECT_ROWS
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW

UNION ALL

SELECT
    'LEAD_ACTIVITIES_RAW',
    COUNT(*),
    COUNT_IF(
        JSON_OBJECT IS NULL
    ),
    COUNT_IF(
        TYPEOF(JSON_OBJECT) = 'OBJECT'
    ),
    COUNT_IF(
        TYPEOF(JSON_OBJECT) <> 'OBJECT'
        AND JSON_OBJECT IS NOT NULL
    )
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW

UNION ALL

SELECT
    'CLOSE_CRM_USERS_RAW',
    COUNT(*),
    COUNT_IF(
        JSON_OBJECT IS NULL
    ),
    COUNT_IF(
        TYPEOF(JSON_OBJECT) = 'OBJECT'
    ),
    COUNT_IF(
        TYPEOF(JSON_OBJECT) <> 'OBJECT'
        AND JSON_OBJECT IS NOT NULL
    )
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW

UNION ALL

SELECT
    'CUSTOM_ACTIVITIES_RAW',
    COUNT(*),
    COUNT_IF(
        JSON_OBJECT IS NULL
    ),
    COUNT_IF(
        TYPEOF(JSON_OBJECT) = 'OBJECT'
    ),
    COUNT_IF(
        TYPEOF(JSON_OBJECT) <> 'OBJECT'
        AND JSON_OBJECT IS NOT NULL
    )
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW

ORDER BY TABLE_NAME;


/*==============================================================
  17. VALIDATE CUSTOM ACTIVITIES
==============================================================*/

SELECT
    COUNT(*) AS TOTAL_CUSTOM_ACTIVITY_ROWS,

    COUNT_IF(
        JSON_OBJECT IS NULL
    ) AS NULL_JSON_OBJECTS,

    COUNT_IF(
        TYPEOF(JSON_OBJECT) = 'OBJECT'
    ) AS VALID_JSON_OBJECTS,

    COUNT_IF(
        TYPEOF(JSON_OBJECT) <> 'OBJECT'
        AND JSON_OBJECT IS NOT NULL
    ) AS NON_OBJECT_VALUES,

    MIN(INSERT_DATE) AS MIN_INSERT_DATE,

    MAX(INSERT_DATE) AS MAX_INSERT_DATE

FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW;


/*==============================================================
  18. VIEW LATEST CUSTOM ACTIVITY RECORDS
==============================================================*/

SELECT
    INSERT_DATE,
    TYPEOF(JSON_OBJECT) AS JSON_TYPE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.CUSTOM_ACTIVITIES_RAW
ORDER BY INSERT_DATE DESC
LIMIT 20;


/*==============================================================
  19. VIEW LATEST LEADS
==============================================================*/

SELECT
    INSERT_DATE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.LEADS_RAW
ORDER BY INSERT_DATE DESC
LIMIT 10;


/*==============================================================
  20. VIEW LATEST LEAD ACTIVITIES
==============================================================*/

SELECT
    INSERT_DATE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.LEAD_ACTIVITIES_RAW
ORDER BY INSERT_DATE DESC
LIMIT 10;


/*==============================================================
  21. VIEW LATEST CRM USERS
==============================================================*/

SELECT
    INSERT_DATE,
    JSON_OBJECT
FROM SALES_ANALYTICS_DB.BRONZE.CLOSE_CRM_USERS_RAW
ORDER BY INSERT_DATE DESC
LIMIT 10;


/*==============================================================
  22. COPY HISTORY — LEADS
==============================================================*/

SELECT
    TABLE_NAME,
    FILE_NAME,
    STATUS,
    ROW_COUNT,
    ROW_PARSED,
    FIRST_ERROR_MESSAGE,
    LAST_LOAD_TIME
FROM TABLE(
    INFORMATION_SCHEMA.COPY_HISTORY(
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
ORDER BY LAST_LOAD_TIME DESC;


/*==============================================================
  23. COPY HISTORY — ALL FOUR TABLES
==============================================================*/

SELECT
    'LEADS_RAW' AS TARGET_TABLE,
    COUNT(*) AS FILES_PROCESSED,
    COALESCE(
        SUM(ROW_COUNT),
        0
    ) AS ROWS_LOADED,
    COUNT_IF(
        STATUS = 'Loaded'
    ) AS FILES_LOADED,
    COUNT_IF(
        STATUS <> 'Loaded'
    ) AS FILES_WITH_OTHER_STATUS
FROM TABLE(
    INFORMATION_SCHEMA.COPY_HISTORY(
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
    COALESCE(
        SUM(ROW_COUNT),
        0
    ),
    COUNT_IF(
        STATUS = 'Loaded'
    ),
    COUNT_IF(
        STATUS <> 'Loaded'
    )
FROM TABLE(
    INFORMATION_SCHEMA.COPY_HISTORY(
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
    COALESCE(
        SUM(ROW_COUNT),
        0
    ),
    COUNT_IF(
        STATUS = 'Loaded'
    ),
    COUNT_IF(
        STATUS <> 'Loaded'
    )
FROM TABLE(
    INFORMATION_SCHEMA.COPY_HISTORY(
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
    COALESCE(
        SUM(ROW_COUNT),
        0
    ),
    COUNT_IF(
        STATUS = 'Loaded'
    ),
    COUNT_IF(
        STATUS <> 'Loaded'
    )
FROM TABLE(
    INFORMATION_SCHEMA.COPY_HISTORY(
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

```
