# Power Automate integration — Appearance Check

Every saved **Appearance Check** creates an auditable delivery and, when enabled, POSTs JSON to a Power Automate HTTP trigger.

The operational record is always saved first. A Power Automate outage does not delete or roll back the Appearance Check. Delivery status and failures are visible in Django Admin under **Power Automate deliveries**, where failed items can be retried.

## 1. Power Automate trigger

Create an automated cloud flow with the trigger **When an HTTP request is received**.

Use the following request body schema:

```json
{
  "type": "object",
  "properties": {
    "event": { "type": "string" },
    "event_version": { "type": "integer" },
    "record_id": { "type": "integer" },
    "employee_id": { "type": "string" },
    "employee_name": { "type": "string" },
    "role": { "type": "string" },
    "appearance_check": { "type": "string" },
    "appearance_check_code": { "type": "string" },
    "is_ready": { "type": "boolean" },
    "not_ready_declined": { "type": "string" },
    "fs_input": { "type": "string" },
    "comment": { "type": "string" },
    "comment_update_final_check": { "type": "string" },
    "shift": { "type": "string" },
    "recorded_date": { "type": "string" },
    "recorded_time": { "type": "string" },
    "recorded_at": { "type": "string" },
    "recorded_by": { "type": "string" }
  },
  "required": [
    "event",
    "event_version",
    "record_id",
    "employee_id",
    "employee_name",
    "appearance_check",
    "appearance_check_code",
    "is_ready",
    "not_ready_declined",
    "comment",
    "recorded_at",
    "recorded_by"
  ]
}
```

Example body sent by Django:

```json
{
  "event": "appearance_check.recorded",
  "event_version": 1,
  "record_id": 125,
  "employee_id": "49105",
  "employee_name": "Julio Cesar Tovar Rodriguez",
  "role": "Game Presenter",
  "appearance_check": "Ready",
  "appearance_check_code": "READY",
  "is_ready": true,
  "not_ready_declined": "",
  "fs_input": "",
  "comment": "Uniform and appearance confirmed.",
  "comment_update_final_check": "",
  "shift": "Afternoon",
  "recorded_date": "2026-09-09",
  "recorded_time": "14:26:00",
  "recorded_at": "2026-09-09T14:26:00-05:00",
  "recorded_by": "operator@arrise.com"
}
```

For `NOT_READY` or `DECLINED`, `not_ready_declined` contains `Not Ready` or `Declined`. For `READY`, that value is blank.

## 2. Excel mapping

The workbook range must be an actual **Excel Table** for the Excel Online (Business) connector to update rows reliably.

Add **Update a row** and use:

- Key column: `ID`
- Key value: `employee_id`
- `Appearance Check`: `appearance_check`
- `FS Imput`: `fs_input`
- `Not Ready/Declined`: `not_ready_declined`
- `Comment`: `comment`
- `Comment Update (Final Check)`: `comment_update_final_check`

`fs_input` and `comment_update_final_check` are intentionally blank in the current MVP because the Appearance application does not currently collect those values. Do not infer them from another field.

If the Excel action needs the ID as a number rather than text, use this Power Automate expression for the key value:

```text
int(triggerBody()?['employee_id'])
```

## 3. Django configuration

After saving the flow once, Power Automate generates the HTTP POST URL. Treat that URL as a secret because it contains the trigger signature.

Put it only in the VM `.env` file:

```env
POWER_AUTOMATE_ENABLED=True
POWER_AUTOMATE_FLOW_URL="https://<generated-power-automate-trigger-url>"
POWER_AUTOMATE_TIMEOUT_SECONDS=5
```

Optional custom header support is available if the flow validates an additional shared secret:

```env
POWER_AUTOMATE_API_KEY="<shared-secret>"
```

Django sends it as `X-ARRISE-API-Key`.

Restart the Django/Gunicorn process after changing environment variables.

## 4. Delivery behavior

- An Appearance Check is persisted first.
- Django creates one `PowerAutomateDelivery` per Appearance Check.
- Successful HTTP 2xx responses become `SENT`.
- HTTP/network failures become `FAILED` and preserve the payload plus safe error metadata.
- If integration is disabled, the delivery is marked `DISABLED`.
- Failed deliveries can be selected in Django Admin and retried with **Retry selected Power Automate deliveries**.

This makes Excel/Power Automate downstream of PostgreSQL rather than the operational source of truth.
