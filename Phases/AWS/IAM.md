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
