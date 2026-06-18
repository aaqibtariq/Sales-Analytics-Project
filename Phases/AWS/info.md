Why AWS Glue Python Shell

We selected AWS Glue Python Shell because this project needs a daily batch extraction, not real-time replication. The source updates daily by 07:30 AM EST, and the project says not to use Spark/PySpark, Databricks, or dbt.

Why not DMS: DMS is better for continuous replication, but here it would stay idle most of the day and create unnecessary cost.

Why not Lambda: Lambda timed out and is not ideal for large files/large JSON exports. Our raw data is over 14 GB after extraction.

Why not Lambda + ECS/Fargate: It can work, but it adds more setup: Docker image, ECS task, networking, task definitions, logging, and scheduling. For this project, that is over-engineering.

Why Glue Python Shell: It is serverless, simple, scheduled, supports normal Python, can connect to PostgreSQL, write JSON to S3, and fits the project restriction because it is not Spark/PySpark.
