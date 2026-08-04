
# Sales Analytics Automation

This folder contains all automation components used in the **Sales Analytics Project** to build a fully automated data pipeline from PostgreSQL to Snowflake.

The automation process extracts new data from PostgreSQL, stores it in Amazon S3, incrementally loads Snowflake Bronze tables, refreshes the Silver and Gold layers, rebuilds reporting views, and orchestrates the complete workflow through a single master pipeline.

---

# Automation Workflow

```text
PostgreSQL
      │
      ▼
AWS Glue Python Shell
(PostgreSQL → Amazon S3)
      │
      ▼
Amazon S3 (Raw JSON)
      │
      ▼
Snowflake Bronze
(Incremental Load)
      │
      ▼
Snowflake Silver
(Data Processing & Validation)
      │
      ▼
Snowflake Gold
(Business Metrics)
      │
      ▼
Reporting Views
      │
      ▼
Daily Pipeline Orchestration
```

---

# Automation Components

| Step | Automation | Description |
|------|------------|-------------|
| 1 | PostgreSQL → Amazon S3 | Extracts incremental data from PostgreSQL and writes JSON files to Amazon S3 using AWS Glue Python Shell. |
| 2 | Bronze Load | Detects newly arrived files in Amazon S3 and loads only new records into the Bronze layer. |
| 3 | Bronze Automation | Executes Bronze validation, logging, deduplication checks, and load monitoring. |
| 4 | Silver Automation | Processes Bronze data into clean Silver tables, removes duplicates, and performs quality validation. |
| 5 | Gold Automation | Refreshes all Gold business tables used for analytics and reporting. |
| 6 | Reports Automation | Rebuilds all reporting views consumed by the Streamlit dashboard. |
| 7 | Daily Pipeline | Executes the complete workflow using a single stored procedure. |

---

# Documentation

| Automation | Documentation |
|------------|---------------|
| PostgreSQL to Amazon S3 (AWS Glue Python Shell) | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/postgres-to-s3-sales-analytics.py) |
| Load New S3 Files into Bronze | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Load%20the%20new%20S3%20files%20into%20Snowflake%20Bronze.md) |
| Bronze Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Bronze%20automation.md) |
| Silver Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Silver%20automation.md) |
| Gold Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Gold%20automation.md) |
| Reports Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Reports%20automation.md) |
| Daily Pipeline Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/daily%20pipeline%20automation.md) |

---

# Daily Execution Flow

The production pipeline is executed using a single Snowflake stored procedure.

```sql
CALL SALES_ANALYTICS_DB.AUTOMATION.RUN_DAILY_PIPELINE();
```

The pipeline automatically performs the following tasks:

1. Detect new files in Amazon S3.
2. Load incremental data into the Bronze layer.
3. Refresh all Silver tables.
4. Refresh all Gold business tables.
5. Refresh reporting views.
6. Execute data quality validations.
7. Write execution logs and processing metrics.

---

# Key Features

- Incremental PostgreSQL extraction using AWS Glue Python Shell
- Watermark-based incremental processing
- Amazon S3 raw data lake
- Automated Snowflake Bronze loading
- Automated Silver transformations
- Automated Gold refresh
- Automated report generation
- End-to-end orchestration with one stored procedure
- Built-in data quality validation
- Execution logging and monitoring
- Production-ready incremental architecture

---

# Technologies Used

- PostgreSQL
- AWS Glue Python Shell
- Amazon S3
- Snowflake
- Snowflake Stored Procedures
- Snowflake Tasks
- SQL
- Python

---

# Project Outcome

This automation framework enables a fully automated, production-style ELT pipeline that:

- Extracts incremental CRM data from PostgreSQL.
- Stores raw JSON data in Amazon S3.
- Processes data through Snowflake Bronze, Silver, and Gold layers.
- Refreshes reporting views used by the Streamlit dashboard.
- Executes the complete workflow using a single orchestration procedure.
- Supports daily scheduled execution with built-in validation and monitoring.
