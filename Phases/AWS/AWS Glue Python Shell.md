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
