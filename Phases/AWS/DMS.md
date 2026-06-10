# DMS Replication Instance

- AWS Console
  - → DMS
    - → Replication Instances
      - → Create Replication Instance

**Configuration**
- Name
  - dms-sales-analytics-replication
- Description
  - Replication instance for Sales Analytics PostgreSQL to S3 migration

- Instance Class
  - dms.t3.micro
- Engine Version
  - Latest available
- Allocated Storage
  - 50 GB
- High Availability
  - Dev or test workload (Single-AZ)
- Publicly Accessible
  - Yes
- Network
  - VPC
    - Choose the same VPC where your PostgreSQL database lives.

- If using DEA RDS:

- Default VPC

- Subnet Group
  - default
- Availability Zone
  - No Preference
- Advanced Settings
  - Maintenance Window
    - Leave default.
- Encryption
  - Enable
- Use:
  - aws/dms
  - managed key.
- Create
- Click:
  - Create Replication Instance
- Wait:
  - 5-15 minutes
- Status should become:
  - Available
