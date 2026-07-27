CREATE OR REPLACE TABLE SILVER.CUSTOM_ACTIVITIES_TRANSIENT AS
SELECT
    JSON_OBJECT,
    INSERT_DATE
FROM BRONZE.CUSTOM_ACTIVITIES_RAW;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT;

SELECT *
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 5;

SELECT
    JSON_OBJECT:raw_data
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 1;

SELECT
    OBJECT_KEYS(JSON_OBJECT:raw_data)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 1;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => t.JSON_OBJECT:raw_data:data
) c;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        REPLACE(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING,
            '''',
            '"'
        )
    ):data
) ca;


SELECT
    t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
LIMIT 1;


SELECT
    TYPEOF(JSON_OBJECT:raw_data:JSON_OBJECT) AS INNER_TYPE
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 5;

SELECT
    JSON_OBJECT:raw_data
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 1;

--------------------------------------------------------

USE DATABASE SALES_ANALYTICS_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE FUNCTION SILVER.REPAIR_JSON_STRING(input_string STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
    REGEXP_REPLACE(
        REPLACE(input_string, '''', '"'),
        'None|none',
        'null'
    )
$$;


SELECT
    TRY_PARSE_JSON(
        REPAIR_JSON_STRING(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    ) AS PARSED_JSON
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
LIMIT 5;


SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        SILVER.REPAIR_JSON_STRING(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    ):data
) ca;


SELECT
    LEFT(t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING, 1000) AS RAW_SAMPLE
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
WHERE t.JSON_OBJECT:raw_data:JSON_OBJECT IS NOT NULL
LIMIT 3;

SELECT
    POSITION('data' IN t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING) AS DATA_POSITION,
    LENGTH(t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING) AS STRING_LENGTH
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
WHERE t.JSON_OBJECT:raw_data:JSON_OBJECT IS NOT NULL
LIMIT 10;


SELECT
    TRY_PARSE_JSON(
        REGEXP_REPLACE(
            SILVER.REPAIR_JSON_STRING(
                t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
            ),
            '[\\x00-\\x1F]',
            ''
        )
    ) AS PARSED_JSON
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
WHERE t.JSON_OBJECT:raw_data:JSON_OBJECT IS NOT NULL
LIMIT 5;


CREATE OR REPLACE FUNCTION SILVER.REPAIR_PYTHON_JSON(input_string STRING)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
HANDLER = 'repair'
AS
$$
import ast
import json
import re

def repair(input_string):
    if input_string is None:
        return None

    s = input_string.strip()

    try:
        # Convert JSON-style booleans/null into Python literals
        s = re.sub(r'\bfalse\b', 'False', s)
        s = re.sub(r'\btrue\b', 'True', s)
        s = re.sub(r'\bnull\b', 'None', s)
        s = re.sub(r'\bNone\b', 'None', s)

        obj = ast.literal_eval(s)
        return json.dumps(obj)

    except Exception:
        return None
$$;

SELECT
    TRY_PARSE_JSON(
        SILVER.REPAIR_PYTHON_JSON(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    ) AS PARSED_JSON
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
LIMIT 5;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        SILVER.REPAIR_PYTHON_JSON(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    ):data
) ca;

CREATE OR REPLACE FUNCTION SILVER.DEBUG_REPAIR_PYTHON_JSON(input_string STRING)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
HANDLER = 'debug_repair'
AS
$$
import ast
import json
import re

def debug_repair(input_string):
    if input_string is None:
        return 'INPUT IS NULL'

    s = input_string.strip()

    try:
        s = re.sub(r'\bfalse\b', 'False', s)
        s = re.sub(r'\btrue\b', 'True', s)
        s = re.sub(r'\bnull\b', 'None', s)

        obj = ast.literal_eval(s)
        return 'SUCCESS'

    except Exception as e:
        return str(type(e)) + ' | ' + str(e)[:500]
$$;

SELECT
    SILVER.DEBUG_REPAIR_PYTHON_JSON(
        t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
    ) AS DEBUG_RESULT
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
WHERE t.JSON_OBJECT:raw_data:JSON_OBJECT IS NOT NULL
LIMIT 10;


CREATE OR REPLACE FUNCTION SILVER.REPAIR_CUSTOM_ACTIVITY_JSON(input_string STRING)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
HANDLER = 'repair'
AS
$$
import re

def repair(input_string):
    if input_string is None:
        return None

    s = input_string

    # Remove description fields because they contain unescaped apostrophes
    s = re.sub(r",\s*'description'\s*:\s*'.*?'\s*,", ",", s)
    s = re.sub(r"'description'\s*:\s*'.*?'\s*,", "", s)
    s = re.sub(r",\s*'description'\s*:\s*null", "", s)

    # Convert remaining Python-style JSON to valid JSON
    s = s.replace("'", '"')
    s = s.replace("False", "false")
    s = s.replace("True", "true")
    s = s.replace("None", "null")

    return s
$$;

SELECT
    TRY_PARSE_JSON(
        SILVER.REPAIR_CUSTOM_ACTIVITY_JSON(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    ) AS parsed_json
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t
LIMIT 5;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        SILVER.REPAIR_CUSTOM_ACTIVITY_JSON(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    ):data
) ca;


CREATE OR REPLACE FUNCTION SILVER.EXTRACT_CUSTOM_ACTIVITY_MAPPINGS(input_string STRING)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
HANDLER = 'extract'
AS
$$
import re
import json

def extract(input_string):
    if input_string is None:
        return json.dumps([])

    s = input_string
    results = []

    blocks = re.split(r"\{\s*'api_create_only'\s*:", s)

    for block in blocks:
        if "actitype_" not in block:
            continue

        activity_id_match = re.search(r"'id'\s*:\s*'(actitype_[^']+)'", block)
        activity_name_match = re.search(r"'name'\s*:\s*'(.*?)'\s*,\s*'organization_id'", block, re.DOTALL)

        if not activity_id_match or not activity_name_match:
            continue

        activity_id = activity_id_match.group(1)
        activity_name = activity_name_match.group(1)

        field_matches = re.findall(
            r"'id'\s*:\s*'(cf_[^']+)'.*?'name'\s*:\s*'(.*?)'\s*,\s*'referenced_custom_type_id'",
            block,
            re.DOTALL
        )

        for field_id, field_name in field_matches:
            results.append({
                "CUSTOM_ACTIVITY_ID": activity_id,
                "CUSTOM_ACTIVITY_NAME": activity_name,
                "CUSTOM_ACTIVITY_OUTCOME_ID": field_id,
                "CUSTOM_ACTIVITY_OUTCOME_NAME": field_name
            })

    return json.dumps(results)
$$;

SELECT
    TRY_PARSE_JSON(
        SILVER.EXTRACT_CUSTOM_ACTIVITY_MAPPINGS(
            JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    )
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 3;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        SILVER.EXTRACT_CUSTOM_ACTIVITY_MAPPINGS(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    )
) f;

CREATE OR REPLACE FUNCTION SILVER.EXTRACT_CUSTOM_ACTIVITY_MAPPINGS_V2(input_string STRING)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
HANDLER = 'extract'
AS
$$
import re
import json

def extract(input_string):
    if input_string is None:
        return json.dumps([])

    s = input_string
    results = []

    activity_pattern = re.compile(
        r"'id'\s*:\s*'(actitype_[^']+)'\s*,\s*'is_archived'.*?'name'\s*:\s*'([^']+)'",
        re.DOTALL
    )

    field_pattern = re.compile(
        r"'id'\s*:\s*'(cf_[^']+)'\s*,\s*'is_shared'.*?'name'\s*:\s*'([^']+)'",
        re.DOTALL
    )

    activity_matches = list(activity_pattern.finditer(s))

    for i, activity_match in enumerate(activity_matches):
        activity_id = activity_match.group(1)
        activity_name = activity_match.group(2)

        start = activity_match.start()
        end = activity_matches[i + 1].start() if i + 1 < len(activity_matches) else len(s)
        block = s[start:end]

        for field_match in field_pattern.finditer(block):
            field_id = field_match.group(1)
            field_name = field_match.group(2)

            results.append({
                "CUSTOM_ACTIVITY_ID": activity_id,
                "CUSTOM_ACTIVITY_NAME": activity_name,
                "CUSTOM_ACTIVITY_OUTCOME_ID": field_id,
                "CUSTOM_ACTIVITY_OUTCOME_NAME": field_name
            })

    return json.dumps(results)
$$;

SELECT
    f.value:CUSTOM_ACTIVITY_ID::STRING AS CUSTOM_ACTIVITY_ID,
    f.value:CUSTOM_ACTIVITY_NAME::STRING AS CUSTOM_ACTIVITY_NAME,
    f.value:CUSTOM_ACTIVITY_OUTCOME_ID::STRING AS CUSTOM_ACTIVITY_OUTCOME_ID,
    f.value:CUSTOM_ACTIVITY_OUTCOME_NAME::STRING AS CUSTOM_ACTIVITY_OUTCOME_NAME
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        SILVER.EXTRACT_CUSTOM_ACTIVITY_MAPPINGS_V2(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    )
) f
LIMIT 50;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => TRY_PARSE_JSON(
        SILVER.EXTRACT_CUSTOM_ACTIVITY_MAPPINGS_V2(
            t.JSON_OBJECT:raw_data:JSON_OBJECT::STRING
        )
    )
) f;

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES_TRANSIENT;
TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES;
TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES_ALL_LEADS_DETAILS;

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES_TRANSIENT;

INSERT INTO SILVER.CUSTOM_ACTIVITIES_TRANSIENT
SELECT
    JSON_OBJECT,
    INSERT_DATE
FROM BRONZE.CUSTOM_ACTIVITIES_RAW;

SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT;

SELECT
    JSON_OBJECT:raw_data:JSON_OBJECT:data[0]:id::STRING AS SAMPLE_ID,
    JSON_OBJECT:raw_data:JSON_OBJECT:data[0]:name::STRING AS SAMPLE_NAME
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 5;

SELECT
    activity.value:id::STRING AS ACTIVITY_ID,
    activity.value:name::STRING AS ACTIVITY_NAME,
    activity.value:outcomes AS OUTCOMES
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(
    INPUT => t.JSON_OBJECT:raw_data:JSON_OBJECT:data
) activity
LIMIT 20;