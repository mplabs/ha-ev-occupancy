# EV Occupancy - Functional Specification Document (FSD)

## Project: Home Assistant Integration – EV Charger Occupancy & Activity (ABRP/Iternio)

1. Purpose

Provide a Home Assistant custom integration that:
	1.	Displays near-real-time charger occupancy (available/occupied/unknown) for one or more chargers, and
	2.	Displays basic historical activity statistics derived from recent charging session end events.

The integration is intended for private use and focuses on quick implementation, correctness, and low operational overhead.

⸻

2. Scope

In scope
	•	Custom integration under custom_components/<domain>/
	•	Polling two HTTP endpoints:
	•	Charger details (status/occupancy)
	•	Charging sessions summary (recent session end events)
	•	Creation of HA entities (sensors and optional binary sensors)
	•	Simple derived metrics (counts, staleness, rolling windows)
	•	Lovelace-ready state + attributes suitable for graphs
	•	Support multiple charger IDs

Out of scope (for initial release)
	•	Config Flow UI setup (optional future enhancement)
	•	Push updates / webhooks
	•	Advanced forecasting (utilization estimation beyond counts)
	•	Third-party database dependencies (InfluxDB optional but not required)
	•	Automated discovery of charger IDs

⸻

3. Users and Use Cases

Primary user
Home Assistant user running a private HA instance who wants a dashboard of:
	•	“Is my nearby charger currently free?”
	•	“How often has it been used recently?”

Key use cases
	1.	Live status glance: See available vs occupied connectors (EVSEs).
	2.	Staleness awareness: Know when the status is likely stale.
	3.	Trend observation: Track daily/weekly session frequency via HA history graphs.

⸻

4. External Interfaces

4.1 HTTP APIs
The integration interacts with the following endpoints:
	1.	Charger details (occupancy)

	•	Method: POST
	•	Endpoint: https://api.iternio.com/2/charger/_get/details
	•	Body: {"chargerIds":[<id1>,<id2>,...]}

	2.	Charging session summary (history signal)

	•	Method: GET
	•	Endpoint: https://api.iternio.com/2/charger/<chargerId>/charging-sessions/summary

Authentication/headers:
	•	Support configurable headers (e.g., x-api-key) via HA configuration.
	•	Session header is not required by user’s observation; integration must not depend on it.

Rate limiting and load:
	•	Details polling: 60–180 seconds per configured set of chargers.
	•	Summary polling: 30–60 minutes per charger.
	•	Add jitter (random offset) to reduce synchronized spikes.

⸻

5. Functional Requirements

FR-1: Configuration
The integration shall allow configuration of:
	•	charger_ids (list of integers)
	•	api_base_url (default: https://api.iternio.com)
	•	headers (dictionary; typically includes x-api-key if needed)
	•	Polling intervals:
	•	scan_interval_details (default: 120s)
	•	scan_interval_summary (default: 3600s)
	•	stale_threshold_minutes (Optional; default: 15)

Initial configuration method:
	•	YAML (fastest)
Future optional:
	•	Config Flow UI

FR-2: Data Fetch – Details
The integration shall fetch charger details for all configured charger IDs in a single POST where possible.

For each charger, it shall parse:
	•	Charger name, address, coordinates (as attributes)
	•	hasDynamicStatus
	•	evses[] with:
	•	id
	•	status
	•	statusLastUpdated

FR-3: Occupancy Computation
For each charger, the integration shall compute:
	•	total_evses: count of evses
	•	available_evses: count where status == AVAILABLE and not stale
	•	occupied_evses: count where status in OCCUPIED, CHARGING and not stale (enumeration may vary; treat unknown statuses conservatively)
	•	unknown_evses: remainder + all stale EVSEs

Staleness rules:
	•	An EVSE is stale if now - statusLastUpdated > stale_threshold_minutes.
	•	Stale EVSEs are counted as unknown_evses.
	•	A binary stale indicator is set when all EVSEs are stale or when the newest update is stale (see Entities).

FR-4: Data Fetch – Session Summary
For each charger, the integration shall fetch session summary and parse:
	•	chargerTelemetry.successful[].endTime (list of timestamps)

FR-5: Historical Metrics Computation
From endTime events, the integration shall compute:
	•	sessions_today (count where endTime date == local today)
	•	sessions_7d (count within last 7 * 24h)
	•	sessions_30d (count within last 30 * 24h)
	•	last_session_end (max endTime) or unknown if none

Optional (nice-to-have but small effort):
	•	peak_hour_7d (hour 0–23 with max events in last 7 days)
	•	peak_weekday_30d (0–6 or Mon–Sun with max events in last 30 days)

FR-6: Entity Creation
The integration shall create HA entities per charger ID.

Minimum required entities (per charger):
Sensors (state)
	1.	sensor.<domain>_<chargerid>_available (int)
	2.	sensor.<domain>_<chargerid>_occupied (int)
	3.	sensor.<domain>_<chargerid>_unknown (int)
	4.	sensor.<domain>_<chargerid>_total (int)
	5.	sensor.<domain>_<chargerid>_freshness_minutes (int)
	6.	sensor.<domain>_<chargerid>_sessions_7d (int)
	7.	sensor.<domain>_<chargerid>_sessions_30d (int)
	8.	sensor.<domain>_<chargerid>_last_session_end (timestamp)

Binary sensor
9. binary_sensor.<domain>_<chargerid>_data_stale (boolean)

Entity naming:
	•	Use charger name in friendly_name attribute when available (e.g., “Dreßlerstr.”).

Common attributes (attach to at least one “main” sensor, e.g., available):
	•	charger_id
	•	name
	•	address
	•	network_name
	•	lat, lon
	•	has_dynamic_status
	•	last_status_update (timestamp)
	•	source (if provided)
	•	Optional: small list of per-EVSE statuses (bounded length)

FR-7: Update Scheduling
The integration shall run:
	•	Details coordinator at scan_interval_details
	•	Summary coordinator at scan_interval_summary

The integration shall:
	•	Avoid overlapping updates.
	•	Handle transient failures with exponential backoff (bounded).
	•	Continue operating with last-known data if an update fails.

FR-8: Error Handling and Resilience
The integration shall:
	•	Mark entities as unavailable if no successful fetch has occurred since startup.
	•	Log errors with domain-prefixed messages.
	•	On schema changes, fail gracefully:
	•	If evses missing: set occupancy to unknown and log warning.
	•	If chargerTelemetry missing: set session metrics to unknown and log warning.

FR-9: Performance Constraints
	•	Must complete each polling cycle within 10 seconds under normal conditions (few chargers).
	•	Use a shared aiohttp session from HA (async_get_clientsession).
	•	Batch details requests for multiple charger IDs.

FR-10: Privacy/Security
	•	Configuration must support storing headers in secrets.yaml (YAML) and never log secrets.
	•	Any debug logging must redact headers.
	•	Provide a prominent note in README: “Private use; do not share keys; poll conservatively.”

⸻

6. Non-Functional Requirements

NFR-1: Compatibility
	•	HA Core compatible with recent releases (target: last 6–12 months).
	•	Python 3.12+ (align with HA baseline at time of implementation).

NFR-2: Maintainability
	•	Use HA best practices:
	•	DataUpdateCoordinator
	•	async_setup_entry / YAML setup as chosen for MVP
	•	Separate modules:
	•	api.py (HTTP client)
	•	coordinator.py
	•	sensor.py, binary_sensor.py
	•	manifest.json, const.py

NFR-3: Observability
	•	Provide debug logs behind HA logger configuration.
	•	Provide a diagnostics stub (optional future) excluding secrets.

⸻

7. User Experience Requirements

UX-1: Clear occupancy signal
	•	Dashboard should show:
	•	Available / Occupied / Unknown counts
	•	Freshness indicator and stale binary sensor

UX-2: Historical visibility
	•	Session counts should be graphable in Lovelace.
	•	last_session_end should provide an at-a-glance “recently used” hint.

⸻

8. Assumptions and Constraints
	•	API schemas may change; integration must be tolerant.
	•	Charger status enumerations may vary; unknown values are treated as unknown.
	•	Session summary provides end times only; true utilization (time occupied) cannot be derived.

⸻

9. Acceptance Criteria

The project is accepted when:
	1.	User can configure at least one charger ID and (optionally) headers.
	2.	HA shows occupancy sensors updating on the configured interval.
	3.	HA shows session metrics updating on the configured interval.
	4.	Staleness logic works (manually test by forcing old timestamps).
	5.	Integration survives API failures and resumes without manual intervention.
	6.	No secrets appear in logs.

⸻

10. MVP Implementation Plan (High-Level)
	1.	Scaffold custom component and manifest.
	2.	Implement API client with two methods:
	•	fetch_details(charger_ids)
	•	fetch_session_summary(charger_id)
	3.	Implement two coordinators:
	•	DetailsCoordinator (batched)
	•	SummaryCoordinator (per charger or batched if possible)
	4.	Implement sensors/binary sensor.
	5.	Add README with configuration examples and Lovelace suggestions.
	6.	Local testing with one charger; validate staleness and stats.

⸻

11. Future Enhancements (Optional)
	•	Config Flow UI setup
	•	Device registry grouping (one device per charger)
	•	Attribute time-series for “sessions per day last 14 days”
	•	Optional InfluxDB export guidance
	•	Charger list discovery/search within HA UI
