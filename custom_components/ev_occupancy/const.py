"""Constants for the EV Occupancy integration."""

DOMAIN = "ev_occupancy"

CONF_CHARGER_IDS = "charger_ids"
CONF_API_BASE_URL = "api_base_url"
CONF_HEADERS = "headers"
CONF_API_KEY = "api_key"
CONF_HEADERS_JSON = "headers_json"
CONF_SCAN_INTERVAL_DETAILS = "scan_interval_details"
CONF_SCAN_INTERVAL_SUMMARY = "scan_interval_summary"
CONF_STALE_THRESHOLD_MINUTES = "stale_threshold_minutes"

DEFAULT_API_BASE_URL = "https://api.iternio.com"
DEFAULT_SCAN_INTERVAL_DETAILS = 120
DEFAULT_SCAN_INTERVAL_SUMMARY = 3600
DEFAULT_STALE_THRESHOLD_MINUTES = 15
