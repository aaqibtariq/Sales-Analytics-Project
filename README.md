# Sales-Analytics-Project


# Objective

Develop a scalable end-to-end Sales Analytics platform that transforms raw CRM activity data into trusted business intelligence for sales leadership. 
The solution standardizes lead lifecycle tracking, measures sales performance, and automates KPI reporting using a modern Medallion Architecture (Bronze, Silver, Gold).
The platform processes daily CRM data, applies business rules and data quality validations, and delivers analytics-ready datasets and interactive dashboards that enable 
data-driven decision-making across the sales organization.

# Business Problem

The sales organization relied on raw CRM data that was difficult to analyze and unsuitable for reporting. Business users faced several challenges:

- CRM data was stored as nested JSON, making it difficult to query directly.
- Lead activities contained duplicate historical records because each daily extract included previously captured activities.
- Activity outcomes were stored as internal IDs rather than meaningful business descriptions.
- Setter and closer attribution was inconsistent across different datasets.
- Pipeline stages were not standardized, resulting in inconsistent reporting across teams.
- Sales managers lacked visibility into how leads progressed from initial contact through strategy calls to closed sales.
- Manual reporting required significant effort and often produced inconsistent KPI calculations.
- There was no centralized reporting layer capable of supporting dashboards or future BI integrations.

# Business Value

This project provides a centralized sales analytics solution that enables leadership to measure and improve the effectiveness of the sales organization.

## Key business outcomes

- Automated daily sales reporting with minimal manual effort.
- Complete visibility into the customer journey from lead creation to revenue generation.
- Standardized KPI calculations across inbound and outbound sales teams.
- Accurate attribution of activities to setters and closers.
- Improved sales forecasting through consistent funnel metrics.
- Better understanding of conversion bottlenecks and customer drop-off reasons.
- Revenue tracking through contracted value and cash collected.
- A scalable data platform capable of supporting additional dashboards, machine learning models, and business intelligence tools in the future.

## System Architecture

<p align="center">
  <img src="https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Sales%20pipeline%20SD.png" width="100%">
</p>

# Core Flow

The Sales Analytics platform follows a Medallion Architecture that progressively transforms raw CRM data into business-ready analytics.

```

PostgreSQL CRM
        │
        ▼
AWS Glue Python Shell
(Daily Incremental Extraction)
        │
        ▼
Amazon S3
(Raw JSON Files)
        │
        ▼
Snowflake Bronze
(Raw JSON Storage)
        │
        ▼
Snowflake Silver
Data Cleansing
JSON Parsing
Deduplication
Business Mapping
Activity Normalization
        │
        ▼
Snowflake Gold
Business Views
Sales Funnel Logic
Revenue Attribution
Performance Metrics
        │
        ▼
Report Layer
• Inbound Setter Report
• Outbound Setter Report
• Closer Report
• Objections Report
        │
        ▼
Snowflake Streamlit Dashboard
Interactive Business Analytics


```
The pipeline executes daily by extracting new CRM data, loading it into Amazon S3, processing it through the Bronze, Silver, and Gold layers in Snowflake, and 
publishing curated datasets for reporting and interactive dashboards. The architecture ensures scalable processing, standardized business logic, and consistent KPI calculations.


# Source Systems

The pipeline integrates multiple CRM datasets stored in a PostgreSQL database. Each dataset contributes a different aspect of the sales process.


| Source Table                  | Description                                                                                | Purpose                                                      |
| ----------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| **raw.leads_raw**             | Lead, contact, opportunity, and pipeline information                                       | Tracks lead lifecycle and ownership                          |
| **raw.lead_activities_raw**   | Customer interactions including calls, meetings, notes, emails, SMS, and custom activities | Captures every sales activity performed on a lead            |
| **raw.custom_activities_raw** | Metadata describing CRM custom activities and outcome mappings                             | Converts internal activity IDs into business-friendly values |
| **raw.close_crm_users_raw**   | CRM user profiles including setters, closers, and sales representatives                    | Enables user attribution and performance reporting           |



The source data is refreshed daily and contains nested JSON structures that require parsing, cleansing, and 
normalization before analytical processing. Because every daily extract includes historical activities, the 
pipeline performs deduplication and incremental processing to ensure only the latest activity version is retained for reporting.


# Architecture Components

The Sales Analytics platform uses AWS and Snowflake services to create a scalable daily data pipeline from PostgreSQL CRM data to business-ready dashboards.

| Component                         | Technology                                                  | Role in the Architecture                                                                                                                             |
| --------------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Source Database**               | PostgreSQL on Amazon RDS                                    | Stores raw CRM data, including leads, lead activities, custom activity definitions, and CRM users.                                                   |
| **Data Extraction**               | AWS Glue Python Shell                                       | Connects to PostgreSQL, extracts new and updated records, and processes the source data in manageable batches.                                       |
| **Incremental Load Control**      | Watermark file in Amazon S3                                 | Stores the latest successful extraction timestamp so each run retrieves only newly inserted or updated data.                                         |
| **Raw Data Storage**              | Amazon S3                                                   | Stores extracted CRM records as raw JSON files and provides a durable landing zone between PostgreSQL and Snowflake.                                 |
| **AWS Security**                  | AWS IAM                                                     | Controls access between AWS Glue, Amazon S3, and other AWS resources using roles and permission policies.                                            |
| **Credential Management**         | AWS Secrets Manager                                         | Securely stores PostgreSQL credentials used by the Glue extraction job.                                                                              |
| **Snowflake Storage Integration** | Snowflake Storage Integration                               | Establishes secure access between Snowflake and the S3 bucket without embedding permanent AWS credentials in SQL scripts.                            |
| **External Stage**                | Snowflake External Stage                                    | References the S3 raw-data location and allows files to be loaded into Snowflake.                                                                    |
| **Bronze Layer**                  | Snowflake Tables                                            | Preserves raw JSON records with ingestion timestamps for traceability, replay, and recovery.                                                         |
| **Silver Layer**                  | Snowflake Tables and Transient Tables                       | Repairs malformed JSON, flattens nested structures, standardizes fields, maps activity IDs, removes duplicates, and applies incremental MERGE logic. |
| **Gold Layer**                    | Snowflake Views                                             | Applies business hierarchy and funnel rules for inbound calls, outbound prospecting, strategy calls, offers, sales, and revenue attribution.         |
| **Reporting Layer**               | Snowflake Report Views                                      | Produces the Inbound Setter, Outbound Setter, Closer, and Objections Faced reports.                                                                  |
| **Dashboard Layer**               | Streamlit in Snowflake                                      | Presents interactive KPI dashboards, performance summaries, filters, and detailed report tables.                                                     |
| **Orchestration**                 | Scheduled AWS Glue and Snowflake jobs                       | Coordinates the daily extraction, ingestion, transformation, validation, and reporting workflow.                                                     |
| **Monitoring and Validation**     | Glue logs, Snowflake query history, and data-quality checks | Tracks execution status, row counts, duplicates, nulls, funnel consistency, and pipeline failures.                                                   |


## **1. PostgreSQL Source Database**

The source system is a PostgreSQL CRM database containing four main datasets:

- raw.leads_raw
- raw.lead_activities_raw
- raw.custom_activities_raw
- raw.close_crm_users_raw

These datasets contain the lead lifecycle, sales activities, custom CRM outcome mappings, and user information required for setter and closer reporting. The source refresh is available daily by approximately 7:30 AM EST.

- [PostgreSQL](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/PostgreSQL)

## **2. AWS Glue Python Shell**

AWS Glue Python Shell is used as the extraction engine. It connects to PostgreSQL using Python and psycopg2, reads 
source records in batches, serializes the results as JSON, and writes the files to Amazon S3.

The extraction process supports both initial full loads and recurring incremental loads.
A Python Shell job was selected because the pipeline does not require Spark and the project specifically excludes Spark, PySpark, Databricks, and dbt.

- [Project Information](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/AWS/info.md)
- [AWS Glue Python Shell](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/AWS/AWS%20Glue%20Python%20Shell.md)
  
## **3. Watermark-Based Incremental Processing**

A watermark file stored in Amazon S3 records the latest successfully processed source timestamp for each table.

During each daily execution, the Glue job:

- Reads the previous watermark.
- Queries records newer than that watermark.
- Writes the extracted data to S3.
- Updates the watermark only after a successful load.

This prevents repeated full-table extraction and allows the process to recover safely after failures.


## **4. Amazon S3 Raw Landing Zone**

Amazon S3 serves as the raw-data landing zone between PostgreSQL and Snowflake.

The files are organized by source and extraction date, for example:

```

s3://sales-analytics-raw-bucket/
├── leads_raw/
│   └── load_date=YYYY-MM-DD/
├── lead_activities_raw/
│   └── load_date=YYYY-MM-DD/
├── custom_activities_raw/
│   └── load_date=YYYY-MM-DD/
└── close_crm_users_raw/
    └── load_date=YYYY-MM-DD/

```

This folder structure supports traceability, incremental processing, file-level auditing, and historical reprocessing.

- [S3](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/AWS/S3.md)

## **5. AWS IAM**

AWS IAM roles and policies secure access across the AWS portion of the pipeline.

IAM permissions allow the Glue job to:

- Read PostgreSQL credentials from AWS Secrets Manager.
- Write raw files and watermarks to Amazon S3.
- Publish execution logs.
- Access only the buckets and objects required for the pipeline.

Snowflake also assumes a dedicated AWS IAM role through the Snowflake storage integration.

- [IAM](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/AWS/IAM.md)
    
## **6. AWS Secrets Manager**

AWS Secrets Manager stores sensitive PostgreSQL connection information, including:

- Host
- Port
- Database
- Username
- Password

The Glue script retrieves the credentials at runtime, avoiding hard-coded credentials in the extraction code.

- [AWS Secrets Manager Secret](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/AWS/AWS%20Secrets%20Manager%20Secret.md)

## **7. Snowflake Storage Integration and External Stage**


A Snowflake storage integration creates a secure trust relationship between Snowflake and AWS.

The external stage points to the S3 raw-data location and is used by COPY INTO commands to load incoming files into the Bronze layer.

This design separates cloud authentication from SQL code and avoids storing AWS access keys inside Snowflake scripts.

- [Test Connection](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Ref%20files/test%20connection)

## **8. Bronze Layer**

The Bronze layer stores source records in their original JSON form.

The core Bronze tables are:

- CUSTOM_ACTIVITIES_RAW
- LEAD_ACTIVITIES_RAW
- CLOSE_CRM_USERS_RAW

Each table contains:

- JSON_OBJECT
- INSERT_DATE

The Bronze layer provides:

- Raw-data preservation
- Auditability
- eprocessing support
- Failure recovery
- Separation between ingestion and transformation

The data model identifies these as raw JSON ingestion tables.

- [Bronze Layer](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/snowflake/bronze.md)
  - [Bronze Ref files](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Layers%20Ref/Bronze%20setup)

## **9. Silver Layer**

The Silver layer converts raw CRM JSON into structured and validated relational data.

Its responsibilities include:

- Repairing malformed JSON.
- Flattening nested arrays and objects.
- Extracting CRM attributes.
- Converting internal IDs into readable activity outcomes.
- Mapping user IDs to setter and closer information.
- Deduplicating records by LEAD_ID and ACTIVITY_ID.
- Retaining the latest activity version.
- Generating MD5 hashes for change detection.
- Applying MERGE statements for inserts and updates.
- Maintaining INSERT_DATE and UPDATE_DATE audit columns.

Key Silver objects include:

- CLOSE_CRM_USERS_PROCESSED
- CUSTOM_ACTIVITIES
- LEAD_ACTIVITIES_PROCESSED
- LEAD_ACTIVITIES_EMAIL
- CUSTOM_ACTIVITIES_ALL_LEADS_DETAILS
- LEADS_ACTIVITIES_SUMMARY

The source contains repeated activities across daily extracts and malformed stringified JSON, so cleansing and deduplication are essential parts of this layer.

- [Silver Layer](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Silver%20Layer)
    - [Silver Ref files](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Layers%20Ref/Silver%20setup)

## **10. Gold Layer**

The Gold layer applies sales business logic and creates reusable analytical views.

Core Gold views include:

- INBOUND_STRATEGIES_BOOKED
- OUTBOUND_STRATEGIES_BOOKED
- ALL_STRATEGIES_DETAILS
- SALES_DETAILS
- OUTBOUND_PROSPECT_DIALS

These views model the required activity sequence:

```
Initial Contact
      ↓
Strategy Call Booked
      ↓
Strategy Call Attended
      ↓
Offer Presented
      ↓
Sale
      ↓
Revenue

```

The views distinguish inbound and outbound acquisition paths and ensure that downstream KPIs are counted only when the required preceding stages exist.

- [Gold Layer](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Gold%20Layer)
    - [Gold Layer Setup](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Layers%20Ref/Gold%20Layer)
  
## **11. Reporting Layer**

The reporting layer provides four final business outputs:

- Inbound Setter Report
- Outbound Setter Report
- Closer Report
- Objections Faced Report

These reports measure booking volume, show rates, strategy-call progression, sales conversion, revenue, closer performance, and objection categories.

- [Export Layer](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Export%20layer)
    - [Export Layer Setup](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/snowflake/Layers%20Ref/Export%20setup)

## **12. Streamlit Dashboard**

The Snowflake Streamlit application is the presentation layer of the platform.

It allows users to:

- Review overall sales KPIs.
- Filter results by date and employee.
- Compare inbound and outbound performance.
- Analyze setter and closer results.
- Review objections faced during strategy calls.
- View detailed report records.
- Monitor data-quality results.

Because Streamlit runs inside Snowflake, the dashboard can query reporting views directly without creating a separate application database.

- [Streamlit Dashboard](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/Streamlit)
  
## **13. Scheduling and Orchestration**

The production workflow is designed to run daily after the PostgreSQL source refresh.

The scheduled execution order is:

1. Extract incremental PostgreSQL data
2. Write JSON files to Amazon S3
3. Load new files into Snowflake Bronze
4. Run Silver transformations and MERGE operations
5. Refresh Gold business views
6. Refresh reporting views
7. Execute validation queries
8. Make updated data available to Streamlit

The project requirement specifies scheduled daily execution and a seven-day production simulation.

| Automation | Documentation |
|------------|---------------|
| Load New S3 Files into Bronze | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Load%20the%20new%20S3%20files%20into%20Snowflake%20Bronze.md) |
| Bronze Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Bronze%20automation.md) |
| Silver Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Silver%20automation.md) |
| Gold Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Gold%20automation.md) |
| Reports Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/Reports%20automation.md) |
| Daily Pipeline Automation | [Open](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Automation/daily%20pipeline%20automation.md) |


## **14. Results**

The Sales Analytics platform successfully transformed raw CRM data into a centralized, automated reporting solution capable of supporting daily operational and executive decision-making.

### Key Achievements

- Successfully built an end-to-end sales analytics pipeline using AWS, Snowflake, and Streamlit.
- Automated the daily ingestion and processing of CRM data from PostgreSQL into Snowflake using an incremental loading strategy.
- Standardized complex nested CRM JSON into analytics-ready relational datasets using a Medallion Architecture (Bronze, Silver, Gold).
- Implemented data quality checks, JSON repair, deduplication, and business-rule validation to ensure accurate reporting.
- Built reusable Gold-layer business views that model the complete sales funnel from initial contact through revenue generation.
- Delivered four production-ready KPI reports:
        - Inbound Setter Performance
        - Outbound Setter Performance
        - Closer Performance
        - Objections Faced Analysis
- Developed an interactive Snowflake Streamlit Dashboard for real-time exploration of sales performance and funnel metrics.
- Eliminated manual reporting by automating daily data processing and KPI generation.
- Created a scalable architecture that can support additional dashboards, reporting requirements, and future analytics use cases with minimal changes.

- [Results Documentation](https://github.com/aaqibtariq/Sales-Analytics-Project/blob/main/Phases/Results/readme.md)
  - [Results](https://github.com/aaqibtariq/Sales-Analytics-Project/tree/main/Phases/Results)
