# AWS GLue setup

- Create new ETL python shell
- Name
  - postgres-to-s3-sales-analytics
- IAM Role
  - sales-analytics-glue-role
- Type
  - python shell
- Version
  - Python 3.9
- Data processing units
  - 1 DPU ( Due to large full first time load)
- Number of retries
  - 0
- Job timeout (minutes)
  - 60
- Script filename
  - postgres-to-s3-sales-analytics.py
- Script path
  - s3://sales-analytics-raw-aqib-test
- Libraries
  - Additional Python modules path
    - psycopg2-binary==2.9.9

# Connect test with PostgreSQL

```python
import json
import boto3
import psycopg2

secret_name = "sales-analytics-postgres"
region = "us-east-1"

client = boto3.client("secretsmanager", region_name=region)

secret = client.get_secret_value(
    SecretId=secret_name
)

creds = json.loads(secret["SecretString"])

conn = psycopg2.connect(
    host=creds["host"],
    port=creds["port"],
    database="dea_analytics_dev",
    user=creds["username"],
    password=creds["password"]
)

cursor = conn.cursor()

cursor.execute("""
SELECT COUNT(*)
FROM raw.leads_raw
""")

count = cursor.fetchone()[0]

print(f"Total rows = {count}")

cursor.close()
conn.close()

```

# Full Load Script

```python

import json
import boto3
import psycopg2
from datetime import datetime, timezone
from decimal import Decimal
from psycopg2.extras import RealDictCursor

SECRET_NAME = "sales-analytics-postgres"
REGION = "us-east-1"
BUCKET = "sales-analytics-raw-aqib-test"

CHUNK_SIZE = 1000

TABLES = {
    "leads_raw": "raw.leads_raw",
    "lead_activities_raw": "raw.lead_activites_raw",
    "close_crm_users_raw": "raw.close_crm_users_raw",
    "custom_activities_raw": "raw.custom_activites_raw"
}

def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def get_secret():
    client = boto3.client("secretsmanager", region_name=REGION)
    secret = client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(secret["SecretString"])

def upload_chunk_to_s3(s3_client, folder_name, rows, chunk_number):
    load_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    key = (
        f"{folder_name}/load_type=full/load_date={load_date}/"
        f"{folder_name}_{run_ts}_part_{chunk_number:05d}.json"
    )

    body = "\n".join(
        json.dumps(row, default=json_serializer)
        for row in rows
    )

    s3_client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json"
    )

    print(f"Uploaded {len(rows)} rows to s3://{BUCKET}/{key}")

def main():
    creds = get_secret()
    s3_client = boto3.client("s3")

    conn = psycopg2.connect(
        host=creds["host"],
        port=creds["port"],
        database="dea_analytics_dev",
        user=creds["username"],
        password=creds["password"]
    )

    for folder_name, table_name in TABLES.items():
        print(f"Starting full load for {table_name}")

        cursor_name = f"cursor_{folder_name}"
        cursor = conn.cursor(
            name=cursor_name,
            cursor_factory=RealDictCursor
        )

        cursor.itersize = CHUNK_SIZE

        cursor.execute(f"""
            SELECT *
            FROM {table_name}
        """)

        chunk_number = 1
        total_rows = 0

        while True:
            rows = cursor.fetchmany(CHUNK_SIZE)

            if not rows:
                break

            upload_chunk_to_s3(
                s3_client=s3_client,
                folder_name=folder_name,
                rows=rows,
                chunk_number=chunk_number
            )

            total_rows += len(rows)
            print(f"{table_name}: total rows exported so far = {total_rows}")

            chunk_number += 1

        cursor.close()
        print(f"Completed full load for {table_name}. Total rows exported = {total_rows}")

    conn.close()
    print("All tables loaded successfully.")

main()

```

# Incremental Load

```

import json
import boto3
import psycopg2
from datetime import datetime, timezone
from decimal import Decimal
from psycopg2.extras import RealDictCursor

SECRET_NAME = "sales-analytics-postgres"
REGION = "us-east-1"
BUCKET = "sales-analytics-raw-aqib-test"

CHUNK_SIZE = 1000

# Last successful full load date
START_WATERMARK = "2026-06-14"

TABLES = {
    "leads_raw": "raw.leads_raw",
    "lead_activities_raw": "raw.lead_activites_raw",
    "close_crm_users_raw": "raw.close_crm_users_raw",
    "custom_activities_raw": "raw.custom_activites_raw"
}

def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def get_secret():
    client = boto3.client("secretsmanager", region_name=REGION)
    secret = client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(secret["SecretString"])

def upload_chunk_to_s3(s3_client, folder_name, rows, chunk_number):
    load_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    key = (
        f"{folder_name}/load_type=incremental/load_date={load_date}/"
        f"{folder_name}_{run_ts}_part_{chunk_number:05d}.json"
    )

    body = "\n".join(
        json.dumps(row, default=json_serializer)
        for row in rows
    )

    s3_client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json"
    )

    print(f"Uploaded {len(rows)} rows to s3://{BUCKET}/{key}")

def main():
    creds = get_secret()
    s3_client = boto3.client("s3")

    conn = psycopg2.connect(
        host=creds["host"],
        port=creds["port"],
        database="dea_analytics_dev",
        user=creds["username"],
        password=creds["password"]
    )

    for folder_name, table_name in TABLES.items():
        print(f"Starting incremental load for {table_name}")
        print(f"Pulling records where insert_date > {START_WATERMARK}")

        cursor_name = f"cursor_{folder_name}"
        cursor = conn.cursor(
            name=cursor_name,
            cursor_factory=RealDictCursor
        )

        cursor.itersize = CHUNK_SIZE

        cursor.execute(f"""
            SELECT *
            FROM {table_name}
            WHERE insert_date > %s
            ORDER BY insert_date
        """, (START_WATERMARK,))

        chunk_number = 1
        total_rows = 0

        while True:
            rows = cursor.fetchmany(CHUNK_SIZE)

            if not rows:
                break

            upload_chunk_to_s3(
                s3_client=s3_client,
                folder_name=folder_name,
                rows=rows,
                chunk_number=chunk_number
            )

            total_rows += len(rows)
            print(f"{table_name}: total incremental rows exported so far = {total_rows}")

            chunk_number += 1

        cursor.close()
        print(f"Completed incremental load for {table_name}. Total rows exported = {total_rows}")

    conn.close()
    print("Incremental load completed successfully.")

main()

```

# Incremental Load without manually update date

```

import json
import re
import boto3
import psycopg2
from datetime import datetime, timezone
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

def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def get_secret():
    client = boto3.client("secretsmanager", region_name=REGION)
    secret = client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(secret["SecretString"])

def get_watermark_key(folder_name):
    return f"_control/watermarks/{folder_name}.json"

def detect_latest_s3_load_date(s3_client, folder_name):
    latest_date = None

    for load_type in ["incremental", "full"]:
        prefix = f"{folder_name}/load_type={load_type}/"
        paginator = s3_client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                match = re.search(r"load_date=(\d{4}-\d{2}-\d{2})", obj["Key"])
                if match:
                    load_date = match.group(1)
                    if latest_date is None or load_date > latest_date:
                        latest_date = load_date

    return latest_date

def get_last_watermark(s3_client, folder_name):
    watermark_key = get_watermark_key(folder_name)

    try:
        obj = s3_client.get_object(Bucket=BUCKET, Key=watermark_key)
        watermark_data = json.loads(obj["Body"].read().decode("utf-8"))
        return watermark_data["last_successful_insert_date"]

    except s3_client.exceptions.NoSuchKey:
        latest_s3_date = detect_latest_s3_load_date(s3_client, folder_name)

        if latest_s3_date:
            print(f"No watermark found for {folder_name}. Using latest S3 load_date: {latest_s3_date}")
            return latest_s3_date

        print(f"No previous load found for {folder_name}. Using default start date.")
        return "1900-01-01"

def save_watermark(s3_client, folder_name, watermark_value, row_count):
    watermark_key = get_watermark_key(folder_name)

    payload = {
        "table": folder_name,
        "last_successful_insert_date": str(watermark_value),
        "row_count": row_count,
        "updated_at_utc": datetime.now(timezone.utc).isoformat()
    }

    s3_client.put_object(
        Bucket=BUCKET,
        Key=watermark_key,
        Body=json.dumps(payload, indent=2).encode("utf-8"),
        ContentType="application/json"
    )

    print(f"Saved watermark for {folder_name}: {watermark_value}")

def upload_chunk_to_s3(s3_client, folder_name, rows, chunk_number):
    load_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    key = (
        f"{folder_name}/load_type=incremental/load_date={load_date}/"
        f"{folder_name}_{run_ts}_part_{chunk_number:05d}.json"
    )

    body = "\n".join(
        json.dumps(row, default=json_serializer)
        for row in rows
    )

    s3_client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json"
    )

    print(f"Uploaded {len(rows)} rows to s3://{BUCKET}/{key}")

def main():
    creds = get_secret()
    s3_client = boto3.client("s3")

    conn = psycopg2.connect(
        host=creds["host"],
        port=creds["port"],
        database="dea_analytics_dev",
        user=creds["username"],
        password=creds["password"]
    )

    for folder_name, table_name in TABLES.items():
        last_watermark = get_last_watermark(s3_client, folder_name)

        print(f"Starting incremental load for {table_name}")
        print(f"Pulling records where insert_date > {last_watermark}")

        cursor = conn.cursor(
            name=f"cursor_{folder_name}",
            cursor_factory=RealDictCursor
        )

        cursor.itersize = CHUNK_SIZE

        cursor.execute(f"""
            SELECT *
            FROM {table_name}
            WHERE insert_date > %s
            ORDER BY insert_date
        """, (last_watermark,))

        chunk_number = 1
        total_rows = 0
        max_insert_date = last_watermark

        while True:
            rows = cursor.fetchmany(CHUNK_SIZE)

            if not rows:
                break

            upload_chunk_to_s3(
                s3_client=s3_client,
                folder_name=folder_name,
                rows=rows,
                chunk_number=chunk_number
            )

            for row in rows:
                if row.get("insert_date") and str(row["insert_date"]) > str(max_insert_date):
                    max_insert_date = row["insert_date"]

            total_rows += len(rows)
            print(f"{table_name}: total rows exported so far = {total_rows}")

            chunk_number += 1

        cursor.close()

        if total_rows > 0:
            save_watermark(s3_client, folder_name, max_insert_date, total_rows)
        else:
            print(f"No new rows found for {table_name}. Watermark unchanged.")

        print(f"Completed incremental load for {table_name}. Total rows exported = {total_rows}")

    conn.close()
    print("Incremental load completed successfully.")

main()

```
 # final script which include all above fix 

 ```
"""
Sales Analytics Incremental Extraction
PostgreSQL -> AWS Glue Python Shell -> Amazon S3

Purpose:
    - Extract new and recently changed PostgreSQL records.
    - Store newline-delimited JSON files in Amazon S3.
    - Repair malformed nested JSON for CUSTOM_ACTIVITIES_RAW.
    - Maintain table-level incremental watermarks.
    - Create run manifests for monitoring and auditing.

AWS Glue configuration:
    Job type: Python Shell
    Python version: Python 3.9
    DPU: 1

Required Python module:
    psycopg2-binary==2.9.9
"""

import ast
import io
import json
import logging
import re
import traceback
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
import psycopg2
from botocore.exceptions import ClientError
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


# =====================================================================
# CONFIGURATION
# =====================================================================

AWS_REGION = "us-east-1"

SECRET_NAME = "sales-analytics-postgres-secret"

S3_BUCKET = "sales-analytics-raw-aqib-test"

WATERMARK_KEY = "_watermarks/glue_watermarks.json"

MANIFEST_PREFIX = "_control/run_manifests"

CHUNK_SIZE = 1000

# Reread the previous 60 minutes to protect against late-arriving records.
# Snowflake Silver MERGE/deduplication will handle duplicate overlap rows.
LOOKBACK_MINUTES = 60

# Keep False after all four watermarks have been created.
ALLOW_BOOTSTRAP_FULL_LOAD = False

BOOTSTRAP_WATERMARK = "1900-01-01 00:00:00.000000"

# Fail CUSTOM_ACTIVITIES_RAW if malformed nested JSON cannot be repaired.
MAX_CUSTOM_ACTIVITY_PARSE_FAILURES = 0


# PostgreSQL table names intentionally preserve source-system spelling.
TABLES: Dict[str, Dict[str, str]] = {
    "leads_raw": {
        "schema": "raw",
        "table": "leads_raw",
        "watermark_column": "insert_date",
    },
    "lead_activities_raw": {
        "schema": "raw",
        "table": "lead_activites_raw",
        "watermark_column": "insert_date",
    },
    "close_crm_users_raw": {
        "schema": "raw",
        "table": "close_crm_users_raw",
        "watermark_column": "insert_date",
    },
    "custom_activities_raw": {
        "schema": "raw",
        "table": "custom_activites_raw",
        "watermark_column": "insert_date",
    },
}


# =====================================================================
# LOGGING
# =====================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =====================================================================
# AWS CLIENTS AND RUN INFORMATION
# =====================================================================

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
)

secrets_client = boto3.client(
    "secretsmanager",
    region_name=AWS_REGION,
)

RUN_ID = str(uuid.uuid4())

RUN_STARTED_AT = datetime.now(timezone.utc)


# =====================================================================
# GENERAL HELPERS
# =====================================================================

def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


def json_serializer(value: Any) -> Any:
    """
    Convert Python and PostgreSQL values into JSON-compatible values.
    """

    if isinstance(value, datetime):
        return value.isoformat(sep=" ")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return str(value)


def normalize_datetime(value: Any) -> datetime:
    """
    Convert a value into a naive Python datetime.

    The project PostgreSQL INSERT_DATE column is treated as:
        TIMESTAMP WITHOUT TIME ZONE

    Therefore, no UTC conversion or timezone shifting is applied.
    """

    if isinstance(value, datetime):
        parsed = value

    elif isinstance(value, date):
        parsed = datetime.combine(
            value,
            datetime.min.time(),
        )

    else:
        text = str(value).strip()

        if not text:
            raise ValueError("Watermark datetime value is empty.")

        # Handle timestamps that end with Z.
        if text.endswith("Z"):
            text = text[:-1]

        try:
            parsed = datetime.fromisoformat(text)

        except ValueError as error:
            raise ValueError(
                f"Unable to parse datetime value: {value}"
            ) from error

    # PostgreSQL INSERT_DATE is treated as timezone-free.
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)

    return parsed


def format_watermark(value: datetime) -> str:
    """
    Format a watermark consistently with six-digit microseconds.
    """

    return value.strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )


# =====================================================================
# AWS SECRETS MANAGER
# =====================================================================

def get_database_secret() -> Dict[str, Any]:
    """
    Retrieve PostgreSQL credentials from AWS Secrets Manager.
    """

    logger.info(
        "Retrieving PostgreSQL credentials from secret: %s",
        SECRET_NAME,
    )

    response = secrets_client.get_secret_value(
        SecretId=SECRET_NAME
    )

    secret_string = response.get("SecretString")

    if not secret_string:
        raise ValueError(
            f"AWS secret {SECRET_NAME} does not contain SecretString."
        )

    secret = json.loads(secret_string)

    required_fields = [
        "host",
        "port",
        "username",
        "password",
    ]

    missing_fields = [
        field
        for field in required_fields
        if not secret.get(field)
    ]

    if missing_fields:
        raise ValueError(
            f"Missing required secret fields: {missing_fields}"
        )

    # Supports either dbname or database.
    # Change the fallback only if your PostgreSQL database has another name.
    secret["resolved_database"] = (
        secret.get("dbname")
        or secret.get("database")
        or "dea_analytics_dev"
    )

    return secret


# =====================================================================
# POSTGRESQL CONNECTION
# =====================================================================

def connect_to_postgresql(
    secret: Dict[str, Any]
):
    """
    Create the PostgreSQL connection.
    """

    logger.info(
        "Connecting to PostgreSQL host %s, database %s",
        secret["host"],
        secret["resolved_database"],
    )

    connection = psycopg2.connect(
        host=secret["host"],
        port=int(secret["port"]),
        database=secret["resolved_database"],
        user=secret["username"],
        password=secret["password"],
        connect_timeout=30,
        application_name="sales-analytics-incremental-glue",
        sslmode=secret.get(
            "sslmode",
            "prefer",
        ),
    )

    logger.info(
        "PostgreSQL connection established successfully."
    )

    return connection


# =====================================================================
# WATERMARK MANAGEMENT
# =====================================================================

def read_watermarks() -> Dict[str, Any]:
    """
    Read the table-level watermark file from Amazon S3.

    Supported legacy format:

    {
      "leads_raw": "2026-07-07 11:01:29.570346"
    }

    Supported enhanced format:

    {
      "leads_raw": {
        "last_successful_insert_date":
            "2026-07-07 11:01:29.570346"
      }
    }
    """

    logger.info(
        "Reading watermarks from s3://%s/%s",
        S3_BUCKET,
        WATERMARK_KEY,
    )

    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET,
            Key=WATERMARK_KEY,
        )

        body = response["Body"].read().decode(
            "utf-8"
        )

        watermarks = json.loads(body)

        if not isinstance(watermarks, dict):
            raise ValueError(
                "Watermark file must contain a JSON object."
            )

        logger.info(
            "Watermark file loaded successfully."
        )

        return watermarks

    except ClientError as error:
        error_code = (
            error.response
            .get("Error", {})
            .get("Code")
        )

        if error_code in {
            "NoSuchKey",
            "404",
            "NotFound",
        }:
            if ALLOW_BOOTSTRAP_FULL_LOAD:
                logger.warning(
                    "Watermark file does not exist. "
                    "Bootstrap mode is enabled."
                )

                return {}

            raise RuntimeError(
                "Watermark file is missing. The job stopped to "
                "prevent an accidental full extraction. Expected: "
                f"s3://{S3_BUCKET}/{WATERMARK_KEY}"
            ) from error

        raise


def extract_watermark_value(
    watermarks: Dict[str, Any],
    folder_name: str,
) -> Optional[str]:
    """
    Retrieve one table's watermark from either the legacy
    or enhanced watermark format.
    """

    table_watermark = watermarks.get(
        folder_name
    )

    if isinstance(table_watermark, str):
        return table_watermark

    if isinstance(table_watermark, dict):
        return (
            table_watermark.get(
                "last_successful_insert_date"
            )
            or table_watermark.get("watermark")
        )

    return None


def write_watermarks(
    watermarks: Dict[str, Any]
) -> None:
    """
    Write the complete watermark document back to Amazon S3.
    """

    watermark_body = json.dumps(
        watermarks,
        indent=2,
        default=json_serializer,
        sort_keys=True,
    ).encode("utf-8")

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=WATERMARK_KEY,
        Body=watermark_body,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )

    logger.info(
        "Watermarks successfully updated at s3://%s/%s",
        S3_BUCKET,
        WATERMARK_KEY,
    )


def update_table_watermark(
    watermarks: Dict[str, Any],
    folder_name: str,
    watermark_column: str,
    watermark_value: datetime,
    rows_extracted: int,
    files_written: int,
) -> None:
    """
    Update one table's watermark and audit metadata.
    """

    watermarks[folder_name] = {
        "last_successful_insert_date": format_watermark(
            watermark_value
        ),
        "watermark_column": watermark_column,
        "rows_extracted_last_run": rows_extracted,
        "files_written_last_run": files_written,
        "run_id": RUN_ID,
        "updated_at_utc": utc_now().isoformat(),
    }


# =====================================================================
# CUSTOM ACTIVITIES JSON REPAIR
# =====================================================================

def fallback_single_quote_json_repair(
    text: str
) -> Any:
    """
    Repair JSON-like strings that contain structural single quotes.

    Examples of problems addressed:
        {'key': 'value'}
        {'name': 'John's Call'}
        Python None/True/False values

    Parsing with json.loads and ast.literal_eval is attempted before
    this fallback function.
    """

    cleaned_text = text.strip()

    cleaned_text = re.sub(
        r"\bNone\b",
        "null",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\bTrue\b",
        "true",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\bFalse\b",
        "false",
        cleaned_text,
    )

    output: List[str] = []

    inside_single_quoted_string = False

    index = 0

    while index < len(cleaned_text):
        character = cleaned_text[index]

        if character == "'":
            if not inside_single_quoted_string:
                output.append('"')
                inside_single_quoted_string = True

            else:
                next_index = index + 1

                while (
                    next_index < len(cleaned_text)
                    and cleaned_text[next_index].isspace()
                ):
                    next_index += 1

                next_character = (
                    cleaned_text[next_index]
                    if next_index < len(cleaned_text)
                    else None
                )

                # Treat the quote as structural only when it ends
                # a key or value.
                if (
                    next_character is None
                    or next_character
                    in {
                        ",",
                        "}",
                        "]",
                        ":",
                    }
                ):
                    output.append('"')
                    inside_single_quoted_string = False

                else:
                    # Preserve an apostrophe inside a word/value.
                    output.append("'")

            index += 1
            continue

        if character == '"':
            if inside_single_quoted_string:
                output.append('\\"')
            else:
                output.append(character)

        elif character == "\n":
            output.append("\\n")

        elif character == "\r":
            output.append("\\r")

        elif character == "\t":
            output.append("\\t")

        else:
            output.append(character)

        index += 1

    repaired_text = "".join(output)

    return json.loads(repaired_text)


def parse_json_like_value(
    value: Any
) -> Tuple[Any, Optional[str]]:
    """
    Convert malformed JSON-like content into a Python dict or list.

    Parsing order:
        1. Already parsed dict/list
        2. Standard JSON
        3. Python literal syntax
        4. Custom apostrophe/single-quote repair
    """

    if value is None:
        return None, None

    if isinstance(
        value,
        (
            dict,
            list,
        ),
    ):
        return value, None

    text = str(value).strip()

    if not text:
        return value, None

    try:
        parsed = json.loads(text)

        return parsed, None

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        pass

    try:
        parsed = ast.literal_eval(text)

        if isinstance(
            parsed,
            (
                dict,
                list,
            ),
        ):
            return parsed, None

    except (
        ValueError,
        SyntaxError,
    ):
        pass

    try:
        parsed = fallback_single_quote_json_repair(
            text
        )

        return parsed, None

    except Exception as error:
        return value, str(error)


def repair_nested_json_object(
    value: Any
) -> Tuple[Any, List[str]]:
    """
    Recursively locate any field named JSON_OBJECT and repair
    malformed string content.

    The earlier custom-activities issue occurred inside:
        raw_data.JSON_OBJECT

    Recursive handling protects against changes in nesting structure.
    """

    errors: List[str] = []

    if isinstance(value, dict):
        repaired_dictionary: Dict[str, Any] = {}

        for key, child_value in value.items():
            if str(key).lower() == "json_object":
                parsed_value, parse_error = (
                    parse_json_like_value(
                        child_value
                    )
                )

                repaired_dictionary[key] = (
                    parsed_value
                )

                if parse_error:
                    errors.append(
                        f"{key}: {parse_error}"
                    )

            else:
                (
                    repaired_child,
                    child_errors,
                ) = repair_nested_json_object(
                    child_value
                )

                repaired_dictionary[key] = (
                    repaired_child
                )

                errors.extend(child_errors)

        return repaired_dictionary, errors

    if isinstance(value, list):
        repaired_list: List[Any] = []

        for item in value:
            (
                repaired_item,
                item_errors,
            ) = repair_nested_json_object(
                item
            )

            repaired_list.append(
                repaired_item
            )

            errors.extend(
                item_errors
            )

        return repaired_list, errors

    return value, errors


def clean_custom_activities_row(
    source_row: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """
    Repair one CUSTOM_ACTIVITIES_RAW source row.

    The row remains structurally equivalent to the PostgreSQL source.
    No temporary patch dates or forced-load fields are added.
    """

    repaired_row, errors = (
        repair_nested_json_object(
            dict(source_row)
        )
    )

    return repaired_row, len(errors)


# =====================================================================
# SOURCE VALIDATION
# =====================================================================

def validate_source_table(
    connection,
    schema_name: str,
    table_name: str,
    watermark_column: str,
) -> None:
    """
    Confirm that the source table and watermark column exist.
    """

    validation_query = """
        SELECT
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND LOWER(column_name) = LOWER(%s)
    """

    with connection.cursor(
        cursor_factory=RealDictCursor
    ) as cursor:
        cursor.execute(
            validation_query,
            (
                schema_name,
                table_name,
                watermark_column,
            ),
        )

        result = cursor.fetchone()

    if not result:
        raise ValueError(
            f"Watermark column '{watermark_column}' was not "
            f"found in {schema_name}.{table_name}."
        )

    logger.info(
        "Validated source %s.%s using watermark column %s (%s)",
        schema_name,
        table_name,
        result["column_name"],
        result["data_type"],
    )


# =====================================================================
# S3 FILE CREATION
# =====================================================================

def build_s3_key(
    folder_name: str,
    run_timestamp: str,
    part_number: int,
) -> str:
    """
    Preserve the project's existing S3 folder structure.

    Example:
        leads_raw/
          leads_raw_20260730_183000_part_00001.json
    """

    return (
        f"{folder_name}/"
        f"{folder_name}_{run_timestamp}"
        f"_part_{part_number:05d}.json"
    )


def upload_chunk_to_s3(
    folder_name: str,
    rows: List[Dict[str, Any]],
    part_number: int,
    run_timestamp: str,
) -> Tuple[str, int]:
    """
    Convert one chunk into newline-delimited JSON and upload it to S3.

    Returns:
        - Uploaded S3 key
        - Number of custom-activity parse failures
    """

    s3_key = build_s3_key(
        folder_name=folder_name,
        run_timestamp=run_timestamp,
        part_number=part_number,
    )

    output_buffer = io.StringIO()

    parse_failure_count = 0

    for source_row in rows:
        output_row = dict(source_row)

        if folder_name == "custom_activities_raw":
            (
                output_row,
                row_failure_count,
            ) = clean_custom_activities_row(
                output_row
            )

            parse_failure_count += (
                row_failure_count
            )

        output_buffer.write(
            json.dumps(
                output_row,
                default=json_serializer,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

        output_buffer.write("\n")

    if (
        parse_failure_count
        > MAX_CUSTOM_ACTIVITY_PARSE_FAILURES
    ):
        raise ValueError(
            f"{folder_name} produced "
            f"{parse_failure_count} unrepairable nested JSON "
            "values. The chunk was not uploaded and the "
            "watermark will not advance."
        )

    encoded_body = (
        output_buffer
        .getvalue()
        .encode("utf-8")
    )

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=encoded_body,
        ContentType="application/x-ndjson",
        ServerSideEncryption="AES256",
        Metadata={
            "run-id": RUN_ID,
            "source-folder": folder_name,
            "row-count": str(len(rows)),
        },
    )

    logger.info(
        "Uploaded %s rows to s3://%s/%s",
        len(rows),
        S3_BUCKET,
        s3_key,
    )

    return s3_key, parse_failure_count


# =====================================================================
# INCREMENTAL EXTRACTION
# =====================================================================

def export_incremental_table(
    connection,
    folder_name: str,
    table_config: Dict[str, str],
    watermarks: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract one PostgreSQL table incrementally and upload the results.
    """

    schema_name = table_config["schema"]
    table_name = table_config["table"]
    watermark_column = table_config[
        "watermark_column"
    ]

    validate_source_table(
        connection=connection,
        schema_name=schema_name,
        table_name=table_name,
        watermark_column=watermark_column,
    )

    stored_watermark_value = (
        extract_watermark_value(
            watermarks=watermarks,
            folder_name=folder_name,
        )
    )

    if stored_watermark_value:
        previous_watermark = (
            normalize_datetime(
                stored_watermark_value
            )
        )

    elif ALLOW_BOOTSTRAP_FULL_LOAD:
        previous_watermark = (
            normalize_datetime(
                BOOTSTRAP_WATERMARK
            )
        )

        logger.warning(
            "%s has no stored watermark. "
            "Bootstrap watermark will be used: %s",
            folder_name,
            format_watermark(
                previous_watermark
            ),
        )

    else:
        raise RuntimeError(
            f"No watermark exists for '{folder_name}'. "
            "The table was not extracted because "
            "ALLOW_BOOTSTRAP_FULL_LOAD is False."
        )

    query_start_watermark = (
        previous_watermark
        - timedelta(
            minutes=LOOKBACK_MINUTES
        )
    )

    logger.info("=" * 80)

    logger.info(
        "Starting source table: %s.%s",
        schema_name,
        table_name,
    )

    logger.info(
        "Stored watermark: %s",
        format_watermark(
            previous_watermark
        ),
    )

    logger.info(
        "Query begins after lookback at: %s",
        format_watermark(
            query_start_watermark
        ),
    )

    incremental_query = sql.SQL(
        """
        SELECT *
        FROM {}.{}
        WHERE {} >= %s
        ORDER BY {} ASC
        """
    ).format(
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
        sql.Identifier(watermark_column),
        sql.Identifier(watermark_column),
    )

    cursor_name = (
        f"incremental_{folder_name}_"
        f"{RUN_ID.replace('-', '')[:8]}"
    )

    cursor = connection.cursor(
        name=cursor_name,
        cursor_factory=RealDictCursor,
    )

    cursor.itersize = CHUNK_SIZE

    cursor.execute(
        incremental_query,
        (
            query_start_watermark,
        ),
    )

    run_timestamp = utc_now().strftime(
        "%Y%m%d_%H%M%S"
    )

    part_number = 1

    total_rows = 0

    files_written = 0

    parse_failures = 0

    uploaded_keys: List[str] = []

    # The watermark does not move backward because of the lookback.
    maximum_watermark = previous_watermark

    try:
        while True:
            fetched_rows = cursor.fetchmany(
                CHUNK_SIZE
            )

            if not fetched_rows:
                break

            rows = [
                dict(row)
                for row in fetched_rows
            ]

            for row in rows:
                row_watermark_value = row.get(
                    watermark_column
                )

                if row_watermark_value is None:
                    logger.warning(
                        "%s row contains a null %s value.",
                        folder_name,
                        watermark_column,
                    )

                    continue

                normalized_row_watermark = (
                    normalize_datetime(
                        row_watermark_value
                    )
                )

                if (
                    normalized_row_watermark
                    > maximum_watermark
                ):
                    maximum_watermark = (
                        normalized_row_watermark
                    )

            (
                uploaded_key,
                chunk_parse_failures,
            ) = upload_chunk_to_s3(
                folder_name=folder_name,
                rows=rows,
                part_number=part_number,
                run_timestamp=run_timestamp,
            )

            uploaded_keys.append(
                uploaded_key
            )

            parse_failures += (
                chunk_parse_failures
            )

            total_rows += len(rows)

            files_written += 1

            part_number += 1

            logger.info(
                "%s progress: %s rows, %s files",
                folder_name,
                total_rows,
                files_written,
            )

    finally:
        cursor.close()

    if total_rows > 0:
        update_table_watermark(
            watermarks=watermarks,
            folder_name=folder_name,
            watermark_column=watermark_column,
            watermark_value=maximum_watermark,
            rows_extracted=total_rows,
            files_written=files_written,
        )

        # Save the watermark after each successfully completed table.
        write_watermarks(
            watermarks
        )

    else:
        logger.info(
            "%s returned no rows. "
            "The watermark remains unchanged at %s.",
            folder_name,
            format_watermark(
                previous_watermark
            ),
        )

    result = {
        "folder_name": folder_name,
        "source_table": (
            f"{schema_name}.{table_name}"
        ),
        "status": "SUCCESS",
        "watermark_before_run": (
            format_watermark(
                previous_watermark
            )
        ),
        "query_start_after_lookback": (
            format_watermark(
                query_start_watermark
            )
        ),
        "watermark_after_run": (
            format_watermark(
                maximum_watermark
            )
        ),
        "rows_extracted": total_rows,
        "files_written": files_written,
        "custom_activity_parse_failures": (
            parse_failures
        ),
        "s3_keys": uploaded_keys,
    }

    logger.info(
        "Completed %s: rows=%s, files=%s, watermark=%s",
        folder_name,
        total_rows,
        files_written,
        format_watermark(
            maximum_watermark
        ),
    )

    return result


# =====================================================================
# RUN MANIFEST
# =====================================================================

def write_run_manifest(
    status: str,
    table_results: List[Dict[str, Any]],
    error_message: Optional[str] = None,
) -> str:
    """
    Write a run-level audit manifest to Amazon S3.
    """

    completed_at = utc_now()

    run_date = RUN_STARTED_AT.strftime(
        "%Y-%m-%d"
    )

    manifest_key = (
        f"{MANIFEST_PREFIX}/"
        f"run_date={run_date}/"
        f"sales_analytics_run_{RUN_ID}.json"
    )

    manifest = {
        "run_id": RUN_ID,
        "status": status,
        "started_at_utc": (
            RUN_STARTED_AT.isoformat()
        ),
        "completed_at_utc": (
            completed_at.isoformat()
        ),
        "duration_seconds": (
            completed_at
            - RUN_STARTED_AT
        ).total_seconds(),
        "source": "PostgreSQL",
        "destination_bucket": S3_BUCKET,
        "watermark_key": WATERMARK_KEY,
        "lookback_minutes": LOOKBACK_MINUTES,
        "chunk_size": CHUNK_SIZE,
        "table_results": table_results,
        "error": error_message,
    }

    manifest_body = json.dumps(
        manifest,
        indent=2,
        default=json_serializer,
    ).encode("utf-8")

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=manifest_key,
        Body=manifest_body,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )

    logger.info(
        "Run manifest written to s3://%s/%s",
        S3_BUCKET,
        manifest_key,
    )

    return manifest_key


# =====================================================================
# MAIN JOB
# =====================================================================

def main() -> None:
    """
    Main AWS Glue job execution.
    """

    logger.info("=" * 80)

    logger.info(
        "Sales Analytics incremental extraction started."
    )

    logger.info(
        "Run ID: %s",
        RUN_ID,
    )

    logger.info("=" * 80)

    connection = None

    table_results: List[
        Dict[str, Any]
    ] = []

    try:
        secret = get_database_secret()

        watermarks = read_watermarks()

        connection = connect_to_postgresql(
            secret
        )

        for (
            folder_name,
            table_config,
        ) in TABLES.items():
            table_result = (
                export_incremental_table(
                    connection=connection,
                    folder_name=folder_name,
                    table_config=table_config,
                    watermarks=watermarks,
                )
            )

            table_results.append(
                table_result
            )

        write_run_manifest(
            status="SUCCESS",
            table_results=table_results,
        )

        logger.info("=" * 80)

        logger.info(
            "All incremental table extractions "
            "completed successfully."
        )

        logger.info("=" * 80)

    except Exception as error:
        error_details = (
            f"{type(error).__name__}: {error}\n"
            f"{traceback.format_exc()}"
        )

        logger.error(
            "Incremental extraction failed:\n%s",
            error_details,
        )

        try:
            write_run_manifest(
                status="FAILED",
                table_results=table_results,
                error_message=error_details,
            )

        except Exception:
            logger.exception(
                "Failure manifest could not be written."
            )

        raise

    finally:
        if connection is not None:
            connection.close()

            logger.info(
                "PostgreSQL connection closed."
            )


if __name__ == "__main__":
    main()


```
