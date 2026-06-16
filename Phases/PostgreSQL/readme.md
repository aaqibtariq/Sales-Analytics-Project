# Download PostgreSQL

https://www.postgresql.org/download/

# Explore Data

- After connecting with postgresql by given credentials we can explore data first
- Our goal to exlpore these 4 tables
  - raw.leads_raw
  - raw.lead_activities_raw
  - raw.close_crm_users_raw
  - raw.custom_activities_raw

## Check all 4 tables data 

```sql

SELECT *
FROM raw.leads_raw
LIMIT 10;
SELECT *
FROM raw.lead_activities_raw
LIMIT 10;
SELECT *
FROM raw.close_crm_users_raw
LIMIT 10;
SELECT *
FROM raw.custom_activities_raw
LIMIT 10;

```

## Identify Table Structures

```
SELECT
table_schema,
table_name,
column_name,
data_type
FROM information_schema.columns
WHERE table_schema='raw'
ORDER BY table_name,column_name;

```

# Validate Data Volume

```
SELECT COUNT(*)
FROM raw.leads_raw;
SELECT COUNT(*)
FROM raw.lead_activities_raw;
SELECT COUNT(*)
FROM raw.close_crm_users_raw;
SELECT COUNT(*)
FROM raw.custom_activities_raw;
```

# Understand JSON Structure


```
Run:

SELECT data
FROM raw.lead_activities_raw
LIMIT 1;

and

SELECT data
FROM raw.custom_activities_raw
LIMIT 1;

and

SELECT data
FROM raw.leads_raw
LIMIT 1;

```

# Check Json

Run this for all 4 tables
```

SELECT
jsonb_typeof(raw_data)
FROM raw.close_crm_users_raw
LIMIT 5;

```

# Count all rows

```

Get row counts
SELECT 'leads_raw' AS table_name, COUNT(*) FROM raw.leads_raw
UNION ALL
SELECT 'lead_activites_raw', COUNT(*) FROM raw.lead_activites_raw
UNION ALL
SELECT 'custom_activites_raw', COUNT(*) FROM raw.custom_activites_raw
UNION ALL
SELECT 'close_crm_users_raw', COUNT(*) FROM raw.close_crm_users_raw;

```

# Check Date range

```
SELECT 
  'leads_raw' AS table_name,
  MIN(insert_date) AS min_insert_date,
  MAX(insert_date) AS max_insert_date
FROM raw.leads_raw
UNION ALL
SELECT 
  'lead_activites_raw',
  MIN(insert_date),
  MAX(insert_date)
FROM raw.lead_activites_raw
UNION ALL
SELECT 
  'custom_activites_raw',
  MIN(insert_date),
  MAX(insert_date)
FROM raw.custom_activites_raw
UNION ALL
SELECT 
  'close_crm_users_raw',
  MIN(insert_date),
  MAX(insert_date)
FROM raw.close_crm_users_raw;

```

## Result

- After above cmds Was able to discorver below data till 6/11

```
Source System: PostgreSQL 

Source Tables:
- raw.leads_raw
- raw.lead_activites_raw
- raw.custom_activites_raw
- raw.close_crm_users_raw

Storage Format:
- JSONB (raw_data)
- insert_date timestamp

Volume:
- 311K+ Leads
- 292K+ Activities
- 14K+ Users

Refresh Pattern:
Daily ingestion



```
