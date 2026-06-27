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

https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/AWS/Ref%20Files/S3

https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/AWS/Ref%20Files/AWS%20glue
