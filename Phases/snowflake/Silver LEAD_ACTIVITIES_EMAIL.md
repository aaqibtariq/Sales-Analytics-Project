# Explore and find more data about email
# inspect the activity types
```

SELECT
    TYPE,
    COUNT(*) AS TOTAL
FROM SILVER.LEAD_ACTIVITIES_PROCESSED
GROUP BY TYPE
ORDER BY TOTAL DESC;

```

```

Activity Type	Count
Call	508,734
SMS	301,449
Email	179,238
CustomActivity	33,628
Meeting	15,468
Created	12,701
Note	12,275
LeadMerge	135

This confirms that LEAD_ACTIVITIES_EMAIL should contain only the 179,238 Email activities.

```

# Inspect Email JSON

```

SELECT
    *
FROM SILVER.LEAD_ACTIVITIES_PROCESSED_TRANSIENT
WHERE JSON_OBJECT:_type::STRING = 'Email'
LIMIT 5;

```

```

This will show the original JSON for an Email activity.

We're specifically looking for fields like:

attachments
body_text
subject
sender
sender_json
envelope
opens
template
date_sent
has_reply
Why inspect first?

Requements

LEAD_ACTIVITIES_EMAIL

LEAD_ID
ACTIVITY_AT
ATTACHMENTS_JSON
BODY_TEXT
DATE_CREATED
DATE_UPDATED
DIRECTION
ENVELOPE_JSON
SENDER_JSON
ACTIVITY_ID
OPENS_JSON
SENDER
STATUS
SUBJECT
JSON_PAYLOAD
USER_ID
USER_NAME
TEMPLATE_ID
TEMPLATE_NAME
DATE_SENT
HAS_REPLY
INSERT_DATE

Some of these fields may be:

directly under the activity object,
nested inside another object,
or missing for certain email records.

Rather than guessing the JSON paths, we'll inspect a few Email records and map each column to its source field. That will let us build LEAD_ACTIVITIES_EMAIL correctly on the first attempt.

```

# Results

```
The JSON maps almost perfectly to the SME schema.
SME Column	JSON Path
ACTIVITY_ID	id
LEAD_ID	lead_id
USER_ID	user_id
USER_NAME	user_name
ACTIVITY_AT	activity_at
BODY_TEXT	body_text
DATE_CREATED	date_created
DATE_UPDATED	date_updated
DIRECTION	direction
ATTACHMENTS_JSON	attachments
ENVELOPE_JSON	envelope
SENDER_JSON	envelope.sender (or entire envelope if you want to preserve all metadata)
OPENS_JSON	opens
SENDER	sender
STATUS	status
SUBJECT	subject
TEMPLATE_ID	template_id
TEMPLATE_NAME	template_name
DATE_SENT	date_sent
HAS_REPLY	has_reply
INSERT_DATE	Bronze INSERT_DATE
JSON_PAYLOAD	Entire JSON_OBJECT

```

# create table 

```
CREATE OR REPLACE TABLE SILVER.LEAD_ACTIVITIES_EMAIL (
    LEAD_ID STRING,
    ACTIVITY_AT TIMESTAMP_NTZ,
    ATTACHMENTS_JSON VARIANT,
    BODY_TEXT STRING,
    DATE_CREATED TIMESTAMP_NTZ,
    DATE_UPDATED TIMESTAMP_NTZ,
    DIRECTION STRING,
    ENVELOPE_JSON VARIANT,
    SENDER_JSON VARIANT,
    ACTIVITY_ID STRING,
    OPENS_JSON VARIANT,
    SENDER STRING,
    STATUS STRING,
    SUBJECT STRING,
    JSON_PAYLOAD VARIANT,
    USER_ID STRING,
    USER_NAME STRING,
    TEMPLATE_ID STRING,
    TEMPLATE_NAME STRING,
    DATE_SENT TIMESTAMP_NTZ,
    HAS_REPLY BOOLEAN,
    INSERT_DATE TIMESTAMP_NTZ,
    UPDATE_DATE TIMESTAMP_NTZ,
    MD5_HASH STRING
);

```

# add record by merge

```
MERGE INTO SILVER.LEAD_ACTIVITIES_EMAIL tgt
USING (
    WITH email_flat AS (
        SELECT
            JSON_OBJECT:lead_id::STRING AS LEAD_ID,
            JSON_OBJECT:activity_at::TIMESTAMP_NTZ AS ACTIVITY_AT,
            JSON_OBJECT:attachments AS ATTACHMENTS_JSON,
            JSON_OBJECT:body_text::STRING AS BODY_TEXT,
            JSON_OBJECT:date_created::TIMESTAMP_NTZ AS DATE_CREATED,
            JSON_OBJECT:date_updated::TIMESTAMP_NTZ AS DATE_UPDATED,
            JSON_OBJECT:direction::STRING AS DIRECTION,
            JSON_OBJECT:envelope AS ENVELOPE_JSON,
            JSON_OBJECT:envelope:sender AS SENDER_JSON,
            JSON_OBJECT:id::STRING AS ACTIVITY_ID,
            JSON_OBJECT:opens AS OPENS_JSON,
            JSON_OBJECT:sender::STRING AS SENDER,
            JSON_OBJECT:status::STRING AS STATUS,
            JSON_OBJECT:subject::STRING AS SUBJECT,
            JSON_OBJECT AS JSON_PAYLOAD,
            JSON_OBJECT:user_id::STRING AS USER_ID,
            JSON_OBJECT:user_name::STRING AS USER_NAME,
            JSON_OBJECT:template_id::STRING AS TEMPLATE_ID,
            JSON_OBJECT:template_name::STRING AS TEMPLATE_NAME,
            JSON_OBJECT:date_sent::TIMESTAMP_NTZ AS DATE_SENT,
            JSON_OBJECT:has_reply::BOOLEAN AS HAS_REPLY,
            INSERT_DATE
        FROM SILVER.LEAD_ACTIVITIES_PROCESSED_TRANSIENT
        WHERE JSON_OBJECT:_type::STRING = 'Email'
    ),

    with_hash AS (
        SELECT
            *,
            MD5(
                COALESCE(LEAD_ID, '') || '|' ||
                COALESCE(ACTIVITY_ID, '') || '|' ||
                COALESCE(ACTIVITY_AT::STRING, '') || '|' ||
                COALESCE(DATE_UPDATED::STRING, '') || '|' ||
                COALESCE(STATUS, '') || '|' ||
                COALESCE(SUBJECT, '') || '|' ||
                COALESCE(BODY_TEXT, '') || '|' ||
                COALESCE(USER_ID, '')
            ) AS MD5_HASH
        FROM email_flat
    ),

    deduped AS (
        SELECT *
        FROM with_hash
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY LEAD_ID, ACTIVITY_ID
            ORDER BY ACTIVITY_AT DESC, DATE_UPDATED DESC, INSERT_DATE DESC
        ) = 1
    )

    SELECT * FROM deduped
) src
ON tgt.LEAD_ID = src.LEAD_ID
AND tgt.ACTIVITY_ID = src.ACTIVITY_ID

WHEN MATCHED AND tgt.MD5_HASH <> src.MD5_HASH THEN UPDATE SET
    tgt.ACTIVITY_AT = src.ACTIVITY_AT,
    tgt.ATTACHMENTS_JSON = src.ATTACHMENTS_JSON,
    tgt.BODY_TEXT = src.BODY_TEXT,
    tgt.DATE_CREATED = src.DATE_CREATED,
    tgt.DATE_UPDATED = src.DATE_UPDATED,
    tgt.DIRECTION = src.DIRECTION,
    tgt.ENVELOPE_JSON = src.ENVELOPE_JSON,
    tgt.SENDER_JSON = src.SENDER_JSON,
    tgt.OPENS_JSON = src.OPENS_JSON,
    tgt.SENDER = src.SENDER,
    tgt.STATUS = src.STATUS,
    tgt.SUBJECT = src.SUBJECT,
    tgt.JSON_PAYLOAD = src.JSON_PAYLOAD,
    tgt.USER_ID = src.USER_ID,
    tgt.USER_NAME = src.USER_NAME,
    tgt.TEMPLATE_ID = src.TEMPLATE_ID,
    tgt.TEMPLATE_NAME = src.TEMPLATE_NAME,
    tgt.DATE_SENT = src.DATE_SENT,
    tgt.HAS_REPLY = src.HAS_REPLY,
    tgt.UPDATE_DATE = CURRENT_TIMESTAMP(),
    tgt.MD5_HASH = src.MD5_HASH

WHEN NOT MATCHED THEN INSERT (
    LEAD_ID, ACTIVITY_AT, ATTACHMENTS_JSON, BODY_TEXT,
    DATE_CREATED, DATE_UPDATED, DIRECTION, ENVELOPE_JSON,
    SENDER_JSON, ACTIVITY_ID, OPENS_JSON, SENDER, STATUS,
    SUBJECT, JSON_PAYLOAD, USER_ID, USER_NAME, TEMPLATE_ID,
    TEMPLATE_NAME, DATE_SENT, HAS_REPLY, INSERT_DATE, UPDATE_DATE, MD5_HASH
)
VALUES (
    src.LEAD_ID, src.ACTIVITY_AT, src.ATTACHMENTS_JSON, src.BODY_TEXT,
    src.DATE_CREATED, src.DATE_UPDATED, src.DIRECTION, src.ENVELOPE_JSON,
    src.SENDER_JSON, src.ACTIVITY_ID, src.OPENS_JSON, src.SENDER, src.STATUS,
    src.SUBJECT, src.JSON_PAYLOAD, src.USER_ID, src.USER_NAME, src.TEMPLATE_ID,
    src.TEMPLATE_NAME, src.DATE_SENT, src.HAS_REPLY, src.INSERT_DATE, CURRENT_TIMESTAMP(), src.MD5_HASH
);

```

# validate 

```

SELECT LEAD_ID, ACTIVITY_ID, COUNT(*) AS CNT
FROM SILVER.LEAD_ACTIVITIES_EMAIL
GROUP BY LEAD_ID, ACTIVITY_ID
HAVING COUNT(*) > 1;

SELECT COUNT(*)
FROM SILVER.LEAD_ACTIVITIES_EMAIL;

You should get approximately:

179,238

Then:

SELECT *
FROM SILVER.LEAD_ACTIVITIES_EMAIL
LIMIT 20;

```

