## EV Occupancy - Implementation Plan

### Context
- Source: `ev-occupancy-FSD.md`
- Goal: Home Assistant custom integration for EV charger occupancy + session stats.

### Plan
1. Repo scaffolding
   - Create `custom_components/ev_occupancy/` with `manifest.json`, `const.py`, `__init__.py`.
   - Add `README.md` with YAML configuration and usage notes.
2. Core configuration (YAML)
   - Define `charger_ids`, `api_base_url`, `headers`, polling intervals, staleness threshold.
   - Validate types and defaults.
3. API client
   - Shared aiohttp session; POST details (batched) + GET session summary.
   - Handle errors, redact secrets in logs.
4. Coordinators
   - Details coordinator (batched by all IDs).
   - Summary coordinator (per charger or batch if feasible).
   - Jittered scheduling, backoff, and stale handling.
5. Entities
   - Sensors for available/occupied/unknown/total/freshness/sessions/last_session_end.
   - Binary sensor for data staleness.
   - Attach common attributes to main sensor.
6. Data logic
   - Occupancy counts + stale logic.
   - Session metrics (today/7d/30d, last end, optional peaks).
7. QA + docs
   - Manual validation checklist aligned with acceptance criteria.
   - Troubleshooting and privacy notes in README.

### Progress Log
- 2025-09-06: Initialized repo; captured implementation plan.
- 2025-09-06: Added custom component scaffold (manifest, constants, init).
- 2025-09-06: Implemented YAML setup, API client, coordinators, and entities.
- 2025-09-06: Added README with configuration and usage notes.
- 2025-09-06: Added sample configuration snippet and updated manifest docs URL.
- 2025-09-06: Added HACS metadata and updated documentation/issue tracker URLs.
