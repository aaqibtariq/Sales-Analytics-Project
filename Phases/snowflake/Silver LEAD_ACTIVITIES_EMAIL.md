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
CREATE OR REPLACE TABLE SILVER.LEAD_ACTIVITIES_EMAIL
(
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
    INSERT_DATE TIMESTAMP_NTZ
);

```

# add record

```
INSERT INTO SILVER.LEAD_ACTIVITIES_EMAIL
SELECT
    JSON_OBJECT:lead_id::STRING,
    JSON_OBJECT:activity_at::TIMESTAMP_NTZ,
    JSON_OBJECT:attachments,
    JSON_OBJECT:body_text::STRING,
    JSON_OBJECT:date_created::TIMESTAMP_NTZ,
    JSON_OBJECT:date_updated::TIMESTAMP_NTZ,
    JSON_OBJECT:direction::STRING,
    JSON_OBJECT:envelope,
    JSON_OBJECT:envelope:sender,
    JSON_OBJECT:id::STRING,
    JSON_OBJECT:opens,
    JSON_OBJECT:sender::STRING,
    JSON_OBJECT:status::STRING,
    JSON_OBJECT:subject::STRING,
    JSON_OBJECT,
    JSON_OBJECT:user_id::STRING,
    JSON_OBJECT:user_name::STRING,
    JSON_OBJECT:template_id::STRING,
    JSON_OBJECT:template_name::STRING,
    JSON_OBJECT:date_sent::TIMESTAMP_NTZ,
    JSON_OBJECT:has_reply::BOOLEAN,
    INSERT_DATE
FROM SILVER.LEAD_ACTIVITIES_PROCESSED_TRANSIENT
WHERE JSON_OBJECT:_type::STRING = 'Email';

```

# validate 

```
Validate
SELECT COUNT(*)
FROM SILVER.LEAD_ACTIVITIES_EMAIL;

You should get approximately:

179,238

Then:

SELECT *
FROM SILVER.LEAD_ACTIVITIES_EMAIL
LIMIT 20;

```

