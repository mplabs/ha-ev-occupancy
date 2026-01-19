# EV Occupancy (Home Assistant Custom Integration)

Home Assistant custom integration to surface EV charger occupancy and recent
charging session activity using ABRP/Iternio endpoints.

## Features
- Near-real-time occupancy counts (available, occupied, unknown, total)
- Data freshness tracking with a stale binary sensor
- Session counts for the last 7 and 30 days plus last session end time
- Optional peak-hour/weekday attributes on session sensors

## Installation
1. Copy `custom_components/ev_occupancy` into your Home Assistant config
   directory.
2. Restart Home Assistant.

### HACS
Add this repository as a custom integration and install it from HACS.

## Configuration (YAML)
See `configuration.yaml.example` for a full snippet.
```yaml
ev_occupancy:
  charger_ids:
    - DEJENE005801
    - 789012
  api_base_url: https://api.iternio.com
  headers:
    x-api-key: !secret iternio_api_key
  scan_interval_details: 120
  scan_interval_summary: 3600
  stale_threshold_minutes: 15
```

### Options
- `charger_ids` (required): List of charger IDs (numeric or alphanumeric).
- `api_base_url` (optional): Base URL for the API.
- `headers` (optional): Request headers such as `x-api-key`.
- `scan_interval_details` (optional): Seconds between detail polls.
- `scan_interval_summary` (optional): Seconds between summary polls.
- `stale_threshold_minutes` (optional): Minutes before data is treated as stale.

## Entities
Per charger ID:
- Sensors: available, occupied, unknown, total, freshness minutes
- Session sensors: sessions 7d, sessions 30d, last session end
- Binary sensor: data stale

## Notes
- Stale EVSEs are counted as unknown.
- Session counts use local time for "today."
- Headers should be stored in `secrets.yaml` and never shared.
- Poll conservatively for private use.

## Troubleshooting
- Enable debug logging for `custom_components.ev_occupancy` to inspect responses.
- If the API schema changes, sensors may show `unknown` while the integration
  logs warnings about missing fields.

## UI Configuration
Use Settings -> Devices & Services -> Add Integration and search for "EV Occupancy".
Enter charger IDs as a comma-separated list and optionally provide an API key.
