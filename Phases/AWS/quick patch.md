# New glue to just get data for CUSTOM_ACTIVITIES_RAW

```
import json
import re
import boto3
import psycopg2
from datetime import datetime, timezone, date
from decimal import Decimal
from psycopg2.extras import RealDictCursor


SECRET_NAME = "sales-analytics-postgres-secret"
REGION = "us-east-1"
BUCKET = "sales-analytics-raw-aqib-test"

CHUNK_SIZE = 1000

TABLES = {
    "leads_raw": "raw.leads_raw",
    "lead_activities_raw": "raw.lead_activites_raw",
    "close_crm_users_raw": "raw.close_crm_users_raw",
    "custom_activities_raw": "raw.custom_activites_raw"
}

WATERMARK_KEY = "_watermarks/glue_watermarks.json"

# one-time reload
FORCE_FULL_LOAD_TABLES = ["custom_activities_raw"]
CUSTOM_ACTIVITIES_RELOAD_END_DATE = "2026-06-25"

s3 = boto3.client("s3")
secrets_client = boto3.client("secretsmanager", region_name=REGION)


def json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def get_secret():
    response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(response["SecretString"])


def read_watermarks():
    try:
        response = s3.get_object(Bucket=BUCKET, Key=WATERMARK_KEY)
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception:
        return {}


def write_watermarks(watermarks):
    s3.put_object(
        Bucket=BUCKET,
        Key=WATERMARK_KEY,
        Body=json.dumps(watermarks, indent=2, default=json_serializer).encode("utf-8")
    )


def get_watermark_column(cursor, source_table):
    possible_columns = [
        "insert_date",
        "date_updated",
        "updated_at",
        "activity_at",
        "date_created",
        "created_at"
    ]

    schema_name, table_name = source_table.split(".")

    for col in possible_columns:
        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND lower(column_name) = lower(%s)
        """, (schema_name, table_name, col))

        if cursor.fetchone()["count"] > 0:
            return col

    return None


def repair_single_quote_json(text):
    if text is None:
        return None

    if isinstance(text, (dict, list)):
        return text

    text = str(text).strip()

    text = re.sub(r"\bNone\b", "null", text)
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)

    output = []
    in_string = False
    i = 0

    while i < len(text):
        ch = text[i]

        if ch == "'":
            if not in_string:
                output.append('"')
                in_string = True
            else:
                j = i + 1
                while j < len(text) and text[j].isspace():
                    j += 1

                if j >= len(text) or text[j] in [",", "}", "]", ":"]:
                    output.append('"')
                    in_string = False
                else:
                    output.append("'")
            i += 1
            continue

        if ch == '"':
            output.append('\\"')
        elif ch == "\n":
            output.append("\\n")
        elif ch == "\r":
            output.append("\\r")
        elif ch == "\t":
            output.append("\\t")
        else:
            output.append(ch)

        i += 1

    repaired_text = "".join(output)

    try:
        return json.loads(repaired_text)
    except Exception as e:
        return {
            "parse_failed": True,
            "parse_error": str(e),
            "raw_json_object_text": text,
            "cleaned_at": datetime.now(timezone.utc).isoformat()
        }


def clean_custom_activities_row(row):
    cleaned_row = dict(row)

    # Main fix: JSON_OBJECT is inside raw_data
    raw_data = cleaned_row.get("raw_data")

    if isinstance(raw_data, dict):
        for key in list(raw_data.keys()):
            if key.lower() == "json_object":
                raw_data[key] = repair_single_quote_json(raw_data[key])

        cleaned_row["raw_data"] = raw_data

    cleaned_row["glue_cleaned_flag"] = True
    cleaned_row["glue_cleaned_at"] = datetime.now(timezone.utc).isoformat()

    return cleaned_row


def upload_rows_to_s3(folder_name, load_type, rows, part_number):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    s3_key = (
        f"{folder_name}/"
        f"load_type={load_type}/"
        f"{folder_name}_{timestamp}_part_{part_number:05d}.json"
    )

    ndjson_data = ""

    for row in rows:
        row_dict = dict(row)

        if folder_name == "custom_activities_raw":
            row_dict = clean_custom_activities_row(row_dict)

        ndjson_data += json.dumps(row_dict, default=json_serializer) + "\n"

    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=ndjson_data.encode("utf-8")
    )

    print(f"Uploaded {len(rows)} rows to s3://{BUCKET}/{s3_key}")


def export_table(cursor, folder_name, source_table, watermarks):
    watermark_column = get_watermark_column(cursor, source_table)
    last_watermark = watermarks.get(folder_name)

    force_full = folder_name in FORCE_FULL_LOAD_TABLES

    if force_full:
        load_type = "full"

        if folder_name == "custom_activities_raw" and CUSTOM_ACTIVITIES_RELOAD_END_DATE:
            query = f"""
                SELECT *
                FROM {source_table}
                WHERE insert_date::date <= %s
                ORDER BY insert_date
            """
            cursor.execute(query, (CUSTOM_ACTIVITIES_RELOAD_END_DATE,))
            print(f"Forced full reload for {source_table} through {CUSTOM_ACTIVITIES_RELOAD_END_DATE}")

        else:
            query = f"SELECT * FROM {source_table}"
            cursor.execute(query)
            print(f"Forced full reload for {source_table}")

    elif last_watermark and watermark_column:
        load_type = "incremental"

        query = f"""
            SELECT *
            FROM {source_table}
            WHERE {watermark_column} > %s
            ORDER BY {watermark_column}
        """
        cursor.execute(query, (last_watermark,))
        print(f"Incremental load for {source_table} using {watermark_column} > {last_watermark}")

    else:
        load_type = "full"
        query = f"SELECT * FROM {source_table}"
        cursor.execute(query)
        print(f"Full load for {source_table}")

    part_number = 1
    total_rows = 0
    max_watermark_value = last_watermark

    while True:
        rows = cursor.fetchmany(CHUNK_SIZE)

        if not rows:
            break

        upload_rows_to_s3(folder_name, load_type, rows, part_number)

        total_rows += len(rows)

        if watermark_column:
            for row in rows:
                value = row.get(watermark_column)
                if value:
                    if max_watermark_value is None or str(value) > str(max_watermark_value):
                        max_watermark_value = str(value)

        part_number += 1

    if not force_full and total_rows > 0 and watermark_column and max_watermark_value:
        watermarks[folder_name] = max_watermark_value
        print(f"Updated watermark for {folder_name}: {max_watermark_value}")

    if force_full:
        print(f"Watermark not updated for forced reload table: {folder_name}")

    print(f"Completed {source_table}. Total rows exported: {total_rows}")


def main():
    secret = get_secret()
    watermarks = read_watermarks()

    conn = psycopg2.connect(
        host=secret["host"],
        port=secret["port"],
        database=secret["dbname"],
        user=secret["username"],
        password=secret["password"]
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    for folder_name, source_table in TABLES.items():
        export_table(cursor, folder_name, source_table, watermarks)

    cursor.close()
    conn.close()

    write_watermarks(watermarks)

    print("All table exports completed successfully.")


main()

```

# Clear bronze and silver data for this

```

TRUNCATE TABLE BRONZE.CUSTOM_ACTIVITIES_RAW;

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES_TRANSIENT;
TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES;
TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES_ALL_LEADS_DETAILS;

```

# Load new data

```

COPY INTO CUSTOM_ACTIVITIES_RAW (JSON_OBJECT, INSERT_DATE)
FROM (
    SELECT
        $1,
        CURRENT_TIMESTAMP()
    FROM @SALES_ANALYTICS_RAW_STAGE/custom_activities_raw/load_type=full/
)
FILE_FORMAT = JSON_FF
ON_ERROR = CONTINUE;

```

# validate

```



SELECT COUNT(*)
FROM CUSTOM_ACTIVITIES_RAW;


SELECT
    JSON_OBJECT:raw_data:JSON_OBJECT:data[0]:id::STRING AS ACTIVITY_TYPE_ID,
    JSON_OBJECT:raw_data:JSON_OBJECT:data[0]:name::STRING AS ACTIVITY_NAME,
    JSON_OBJECT:glue_cleaned_flag::BOOLEAN AS GLUE_CLEANED_FLAG
FROM CUSTOM_ACTIVITIES_RAW
LIMIT 5;

```

# result

```

Bronze row count:

18 rows

And your validation query returned:

ACTIVITY_TYPE_ID	ACTIVITY_NAME	GLUE_CLEANED_FLAG
actitype_0swZKvY0rLQngJj3Nxgo39	0) Pipeline Update	TRUE

This confirms:

Glue successfully repaired raw_data.JSON_OBJECT.
Snowflake can now navigate the JSON.
JSON_OBJECT is no longer just a malformed string.
The Glue cleanup is working as intended.

```

## reload silver

```

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES_TRANSIENT;

INSERT INTO SILVER.CUSTOM_ACTIVITIES_TRANSIENT
SELECT
    JSON_OBJECT,
    INSERT_DATE
FROM BRONZE.CUSTOM_ACTIVITIES_RAW;

```

# validate 
```
SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT;
SELECT
    JSON_OBJECT:raw_data:JSON_OBJECT:data[0]:id::STRING AS SAMPLE_ID,
    JSON_OBJECT:raw_data:JSON_OBJECT:data[0]:name::STRING AS SAMPLE_NAME
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
LIMIT 5;

```

# result

```


SAMPLE_ID	SAMPLE_NAME
actitype_0swZKvY0rLQngJj3Nxgo39	0) Pipeline Update

That means:

Bronze is correct.
 CUSTOM_ACTIVITIES_TRANSIENT is correct.
 raw_data.JSON_OBJECT.data[] is being parsed successfully.
 We can now build the final Silver table exactly as your SME designed it.

```

# Create table

```

CREATE OR REPLACE TABLE SILVER.CUSTOM_ACTIVITIES (
    CUSTOM_ACTIVITY_ID STRING,
    CUSTOM_ACTIVITY_NAME STRING,
    CUSTOM_ACTIVITY_OUTCOME_ID STRING,
    CUSTOM_ACTIVITY_OUTCOME_NAME STRING,
    MD5_HASH STRING,
    INSERT_DATE TIMESTAMP_NTZ,
    UPDATE_DATE TIMESTAMP_NTZ
);

```

# load data

```

INSERT INTO SILVER.CUSTOM_ACTIVITIES
(
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME,
    CUSTOM_ACTIVITY_OUTCOME_ID,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5_HASH,
    INSERT_DATE,
    UPDATE_DATE
)
SELECT
    activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
    activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
    outcome.value:id::STRING AS CUSTOM_ACTIVITY_OUTCOME_ID,
    outcome.value:name::STRING AS CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5(
        COALESCE(activity.value:id::STRING, '') || '|' ||
        COALESCE(activity.value:name::STRING, '') || '|' ||
        COALESCE(outcome.value:id::STRING, '') || '|' ||
        COALESCE(outcome.value:name::STRING, '')
    ) AS MD5_HASH,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(INPUT => t.JSON_OBJECT:raw_data:JSON_OBJECT:data) activity,
LATERAL FLATTEN(INPUT => activity.value:outcomes, OUTER => TRUE) outcome;

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES;

INSERT INTO SILVER.CUSTOM_ACTIVITIES
(
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME,
    CUSTOM_ACTIVITY_OUTCOME_ID,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5_HASH,
    INSERT_DATE,
    UPDATE_DATE
)
SELECT
    activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
    activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
    outcome.value:id::STRING AS CUSTOM_ACTIVITY_OUTCOME_ID,
    outcome.value:name::STRING AS CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5(
        COALESCE(activity.value:id::STRING, '') || '|' ||
        COALESCE(activity.value:name::STRING, '') || '|' ||
        COALESCE(outcome.value:id::STRING, '') || '|' ||
        COALESCE(outcome.value:name::STRING, '')
    ) AS MD5_HASH,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT t,
LATERAL FLATTEN(INPUT => t.JSON_OBJECT:raw_data:JSON_OBJECT:data) activity,
LATERAL FLATTEN(INPUT => activity.value:outcomes, OUTER => TRUE) outcome;

```

# Validate 

```
SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES;

SELECT *
FROM SILVER.CUSTOM_ACTIVITIES
LIMIT 20;

```


```

Current status
Bronze
18 rows loaded
JSON_OBJECT repaired by Glue
 JSON can be traversed in Snowflake
Silver Transient
 Loaded successfully
Silver CUSTOM_ACTIVITIES
Loaded successfully
 450 rows inserted

The CSV you uploaded has exactly the columns required by your SME:

Column	Status
CUSTOM_ACTIVITY_ID	
CUSTOM_ACTIVITY_NAME	
CUSTOM_ACTIVITY_OUTCOME_ID	
CUSTOM_ACTIVITY_OUTCOME_NAME	
MD5_HASH	
INSERT_DATE	
UPDATE_DATE

The count of 450 rows 

we have
18 activity types in Bronze.
450 rows in CUSTOM_ACTIVITIES.

That averages to 25 outcomes per activity type, which seems unusually high.

Before we continue, let's verify that we're not accidentally flattening the wrong array.



```

# testing again

```
SELECT
    COUNT(*) AS TOTAL_ACTIVITY_TYPES
FROM TABLE(
    FLATTEN(
        INPUT => (
            SELECT JSON_OBJECT:raw_data:JSON_OBJECT:data
            FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
            LIMIT 1
        )
    )
);

and

SELECT
    CUSTOM_ACTIVITY_NAME,
    COUNT(*) AS OUTCOME_COUNT
FROM SILVER.CUSTOM_ACTIVITIES
GROUP BY CUSTOM_ACTIVITY_NAME
ORDER BY OUTCOME_COUNT DESC;

```


# new load 

```

TRUNCATE TABLE SILVER.CUSTOM_ACTIVITIES;

INSERT INTO SILVER.CUSTOM_ACTIVITIES
(
    CUSTOM_ACTIVITY_ID,
    CUSTOM_ACTIVITY_NAME,
    CUSTOM_ACTIVITY_OUTCOME_ID,
    CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5_HASH,
    INSERT_DATE,
    UPDATE_DATE
)
WITH LATEST_SNAPSHOT AS (
    SELECT JSON_OBJECT, INSERT_DATE
    FROM SILVER.CUSTOM_ACTIVITIES_TRANSIENT
    QUALIFY ROW_NUMBER() OVER (
        ORDER BY JSON_OBJECT:raw_data:INSERT_DATE::TIMESTAMP_NTZ DESC
    ) = 1
)
SELECT
    activity.value:id::STRING AS CUSTOM_ACTIVITY_ID,
    activity.value:name::STRING AS CUSTOM_ACTIVITY_NAME,
    outcome.value:id::STRING AS CUSTOM_ACTIVITY_OUTCOME_ID,
    outcome.value:name::STRING AS CUSTOM_ACTIVITY_OUTCOME_NAME,
    MD5(
        COALESCE(activity.value:id::STRING, '') || '|' ||
        COALESCE(activity.value:name::STRING, '') || '|' ||
        COALESCE(outcome.value:id::STRING, '') || '|' ||
        COALESCE(outcome.value:name::STRING, '')
    ) AS MD5_HASH,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
FROM LATEST_SNAPSHOT t,
LATERAL FLATTEN(INPUT => t.JSON_OBJECT:raw_data:JSON_OBJECT:data) activity,
LATERAL FLATTEN(INPUT => activity.value:outcomes, OUTER => TRUE) outcome;

```

# validate 

```
SELECT COUNT(*)
FROM SILVER.CUSTOM_ACTIVITIES;


Final SILVER.CUSTOM_ACTIVITIES
25 rows
 7 columns
 One row per custom activity
 No duplicate snapshots
Matches the SME data model

Columns:

CUSTOM_ACTIVITY_ID
CUSTOM_ACTIVITY_NAME
CUSTOM_ACTIVITY_OUTCOME_ID
CUSTOM_ACTIVITY_OUTCOME_NAME
MD5_HASH
INSERT_DATE
UPDATE_DATE



```
