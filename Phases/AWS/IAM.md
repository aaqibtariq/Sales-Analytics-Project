# Roles for AWS GLue

- Created
  - sales-analytics-glue-role
- Attached Policies:
  - AmazonS3FullAccess
  - AWSGlueServiceRole
  - SecretsManagerReadWrite

 # Trusted entities

 ```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "glue.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

````

# Purpose

- Read PostgreSQL credentials
- Write JSON files to S3
- Write CloudWatch logs

# Role for Snowflake

- AWS IAM → Roles → Create role
- name → snowflake-sales-analytics-s3-role
- Attach inlcine permission policy
```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSnowflakeReadSalesAnalyticsS3",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::sales-analytics-raw-aqib-test",
        "arn:aws:s3:::sales-analytics-raw-aqib-test/*"
      ]
    }
  ]
}

```

- After role is created, copy its ARN, like: arn:aws:iam::<your-account-id>:role/snowflake-sales-analytics-s3-role
- paste this value in snowflake to setup Storage Integration
- Once you get new value from snowflake add those into trust Relationship
