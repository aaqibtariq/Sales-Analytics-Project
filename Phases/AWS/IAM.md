# role for DMS with S3 access

- Role name:
  - dms-sales-analytics-s3-role

- Policy permission:

```

{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::sales-analytics-datalake-aqib",
        "arn:aws:s3:::sales-analytics-datalake-aqib/*"
      ]
    }
  ]
}

````
