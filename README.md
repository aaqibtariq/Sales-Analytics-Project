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

```
| Source Table                  | Description                                                                                | Purpose                                                      |
| ----------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| **raw.leads_raw**             | Lead, contact, opportunity, and pipeline information                                       | Tracks lead lifecycle and ownership                          |
| **raw.lead_activities_raw**   | Customer interactions including calls, meetings, notes, emails, SMS, and custom activities | Captures every sales activity performed on a lead            |
| **raw.custom_activities_raw** | Metadata describing CRM custom activities and outcome mappings                             | Converts internal activity IDs into business-friendly values |
| **raw.close_crm_users_raw**   | CRM user profiles including setters, closers, and sales representatives                    | Enables user attribution and performance reporting           |


```

The source data is refreshed daily and contains nested JSON structures that require parsing, cleansing, and 
normalization before analytical processing. Because every daily extract includes historical activities, the 
pipeline performs deduplication and incremental processing to ensure only the latest activity version is retained for reporting.


