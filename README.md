# YottaFlex.ai 72-Hour Code Challenge — Warehouse Zone Telemetry & Risk Alerting Platform

**Role:** Associate AI Forward Deployed Engineer · Round 2 Code Challenge  
**Architecture:** Spring Boot 3 (Java 25) Backend + ReactJS 18 (Vite + Tailwind CSS) Frontend + Deterministic Python Synthetic Data Generator & Validator  
**Fixed Seed:** `20261022`  

---

## 1. Executive Summary & Objective Coverage

This repository provides a complete, working end-to-end solution to **monitor temperature, humidity, occupancy, and door events by warehouse zone and alert on risk conditions**, exposing key operational decisions and exceptions, preserving append-only traceability across entities, and producing measurable evaluation and reconciliation metrics.

### Primary Actors Supported in the Platform
1. **Plant Operator** — Monitors real-time zone temperature (`°C`), relative humidity (`%RH`), occupancy (`persons`), and correlated `DoorEvent` logs (`FORKLIFT_LOADING`, `PROPPED_OPEN_FAULT`), triaging active excursions.
2. **Maintenance / Quality Engineer** — Investigates `Alarm` records, tracks sensor calibration drift and communication outages, conducts `Inspection` workflows, and executes append-only `Remediation` actions.
3. **Production Planner** — Traces `InventoryLot` storage assignments (`ZoneLotAssignment`), dwell hours, cumulative excursion exposure against `StorageRequirement` policies, and reconciled available vs. scrapped unit balances.
4. **OT / IT Administrator** — Audits sensor-to-zone topology (`SensorZoneMappingHistory`), evaluates the 4 labelled edge-case categories against `ground_truth.csv` (`100.0% Precision / Recall / F1`), runs the 23-check schema/arithmetic validation suite, and verifies two-run SHA-256 seed reproducibility.

---

## 2. Project Directory Structure

```text
yottaflex-warehouse-telemetry/
├── README.md                          # Complete setup, architecture, generator & test guide
├── GITHUB_AND_LIVE_DEPLOY_GUIDE.md    # Step-by-step commands to push to GitHub & deploy live URL
├── docker-compose.yml                 # One-command full-stack container orchestration
├── run-local.sh                       # Linux/macOS quick-start launcher script
├── run-local.bat                      # Windows laptop quick-start launcher script
├── docs/
│   └── DATA_DICTIONARY.md             # Step 1: Granular Data Dictionary & Cardinality Matrix
├── sql/
│   └── schema.sql                     # SQL DDL for all 10 Core Entities + 3 Bridge Tables
├── generator/
│   ├── generate_dataset.py            # Steps 2-7 & 9: Deterministic Generator (--seed 20261022)
│   └── validate_dataset.py            # Steps 8 & 10: PK/FK/Arithmetic Validator & 2-Run SHA-256 Verifier
├── data/
│   └── seed/
│       ├── csv/                       # 13 deterministic CSV tables (warehouses .. remediations)
│       ├── json/                      # 13 deterministic JSON tables
│       ├── ground_truth.csv           # Step 7: Separate ground-truth labels (zero input leakage)
│       ├── ground_truth.json          # Step 7: Separate ground-truth JSON
│       ├── seed_data.sql              # Step 9: SQL INSERT seed bundle
│       ├── source_manifest.json       # Step 9: Generator command, seed, provenance & SHA-256 digests
│       ├── validation_summary.json    # Step 8: 23/23 passed validation checks report
│       └── reproducibility_report.json# Step 10: Two-run SHA-256 checksum comparison report
├── data/full_scale/                   # Full CSV/JSON/SQL dataset (1M readings, 10K lots)
│   ├── csv/ and json/                 # All 13 entity/bridge tables
│   ├── seed_data.sql                  # Complete SQL seed bundle
│   ├── ground_truth.csv / .json       # Separate anomaly labels
│   ├── source_manifest.json           # Counts, provenance and SHA-256 digests
│   ├── validation_summary.json        # Full-scale domain validation
│   └── reproducibility_report.json    # Full-scale two-run reproducibility evidence
├── backend/                           # Spring Boot 3.5.16 (Java 25) REST API & Business Rule Engine
│   ├── pom.xml
│   └── src/
│       ├── main/java/ai/yottaflex/telemetry/
│       │   ├── WarehouseTelemetryApplication.java
│       │   ├── StandaloneCliVerifier.java
│       │   ├── controller/TelemetryController.java
│       │   ├── model/DomainModels.java
│       │   └── service/TelemetryDataService.java
│       └── test/java/ai/yottaflex/telemetry/
│           └── WarehouseTelemetryApplicationTests.java
└── frontend/                          # ReactJS 18 (Vite + Tailwind + Recharts + Lucide) UI
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        └── App.jsx
```

---

## 3. ID / Nomenclature Conventions (Deterministic & Zero-Padded)

| Entity / Bridge Table | Deterministic Pattern | Example ID |
| :--- | :--- | :--- |
| `Warehouse` | `WH-<NNN>` | `WH-001` .. `WH-010` |
| `Zone` | `ZONE-<warehouse-id>-<NNN>` | `ZONE-WH-001-001` .. `ZONE-WH-010-010` |
| `Sensor` | `SNS-<zone-id>-<TYPE>-<NN>` | `SNS-ZONE-WH-001-001-TEMP-01` |
| `SensorReading` | `RDG-<sensor-id>-<UTC_TIMESTAMP>` | `RDG-SNS-ZONE-WH-001-001-TEMP-01-20261001T000500Z` |
| `DoorEvent` | `DOR-<zone-id>-<UTC_TIMESTAMP>-<NNN>` | `DOR-ZONE-WH-001-001-20261001T011000Z-002` |
| `StorageRequirement` | `REQ-<NNN>` | `REQ-001` .. `REQ-006` |
| `InventoryLot` | `LOT-2026-<NNNNNN>` | `LOT-2026-000001` .. `LOT-2026-010000` |
| `ZoneLotAssignment` (Bridge) | `ZLA-2026-<NNNNNN>` | `ZLA-2026-000001` |
| `Alarm` | `ALM-2026-<NNNNNN>` | `ALM-2026-000001` |
| `AlarmAffectedLot` (Bridge) | `AAL-2026-<NNNNNN>` | `AAL-2026-000001` |
| `Inspection` | `INS-2026-<NNNNNN>` | `INS-2026-000001` |
| `Remediation` | `REM-2026-<NNNNNN>` | `REM-2026-000001` |
| `SensorZoneMappingHistory` (Bridge) | `SZM-2026-<NNNNNN>` | `SZM-2026-000001` |

---

## 4. How to Run Locally on Your Laptop

### Prerequisites
- **Java 25** and **Maven 3.9+** (for the Spring Boot backend)
- **Node.js 18+** and **npm** (for the ReactJS frontend)
- **Python 3.9+** (for the deterministic synthetic dataset generator & validator)

### Step A — Generate & Validate Synthetic Data (Starter & Full 1M-Reading Scales)
The repository comes pre-populated with the verified `starter` dataset in `data/seed/` so you can clone and launch immediately.

```bash
# 1. Regenerate starter dataset (10 Warehouses, 100 Zones, 500 Sensors, 15,000 Readings, 500 Lots)
python3 generator/generate_dataset.py --seed 20261022 --scale starter --out-dir data/seed

# 2. Run Step 8 Validation + Step 10 Two-Run SHA-256 Reproducibility Verification
python3 generator/validate_dataset.py --data-dir data/seed --seed 20261022 --scale starter

# 3. Generate the complete Full Benchmark Volume (CSV, JSON and SQL)
python3 generator/generate_dataset.py --seed 20261022 --scale full --out-dir data/full_scale
python3 generator/validate_dataset.py --data-dir data/full_scale --seed 20261022 --scale full
```

The full-scale run exports all 1,000,000 readings and 10,000 lots in CSV, JSON, and SQL. It takes more disk space than the starter data. The validator checks domain constraints, joins, timestamp ordering, temporal lot impacts, arithmetic reconciliation, ground-truth separation, and regenerates twice to verify checksums.

### Step B — Run the Spring Boot Backend & JUnit 5 Tests (`:8080`)
```bash
cd backend
# Run automated JUnit 5 tests (verifies master counts, 100% F1 edge-case detection, reconciliation & append-only state)
mvn test

# Start the Spring Boot REST API server on http://localhost:8080
mvn spring-boot:run
```

Key REST Endpoints available once running:
- `GET http://localhost:8080/api/overview` — System KPIs, financial impact, and ground-truth F1 metrics
- `GET http://localhost:8080/api/warehouses` — 10 Warehouses with reconciled pallet capacities
- `GET http://localhost:8080/api/zones?warehouseId=WH-001` — Zones by warehouse
- `GET http://localhost:8080/api/zones/ZONE-WH-001-001/telemetry` — Zone readings, sensors, door events & alarms
- `GET http://localhost:8080/api/lots/LOT-2026-000015/traceability` — End-to-end lot dwell, compatibility & remediation chain
- `GET http://localhost:8080/api/exceptions/evaluate` — Evaluates the 4 edge cases and compares against `ground_truth.csv`
- `GET http://localhost:8080/api/validation/report` — Runs programmatic PK/FK/Arithmetic validation checks
- `POST http://localhost:8080/api/alarms/ALM-2026-000001/remediate` — Appends new Inspection & Remediation records
- `GET http://localhost:8080/api/audit-events` — Lists persisted append-only workflow events

Workflow changes are appended to `data/runtime/workflow-events.jsonl` and replayed when the backend starts again. Generated seed files remain unchanged; the journal is the durable record of live inspections, remediations, and any updated lot balance.

### Step C — Run the ReactJS Frontend (`:5173`)
Open a second terminal:
```bash
cd frontend
npm ci
npm run dev
```
Open **`http://localhost:5173`** in your browser. Click **"Sync Spring Boot (:8080)"** in the top header to sync live with the Spring Boot backend, or use the deterministic starter data and generated validation/reproducibility reports directly in the browser.

---

## 5. Required Edge Cases & Acceptance Criteria Summary

| Edge Case (`issue_type`) | Description | Detection Logic | Expected System Decision |
| :--- | :--- | :--- | :--- |
| `LOT_INCOMPATIBLE_ZONE` | Lot assigned to a zone whose `zone_type` is not in `StorageRequirement.allowed_zone_types` (e.g. `LOT-2026-000015`) | Joins `InventoryLot -> StorageRequirement` and `Zone`, checking `zone_type` membership | `REJECT_ASSIGNMENT_QUARANTINE_LOT` |
| `SENSOR_MULTI_ZONE_NO_RATIONALE` | Sensor mapped concurrently to `>= 2` zones in `SensorZoneMappingHistory` with blank `mapping_rationale` | Groups active mappings by `sensor_id` and flags rows with empty `mapping_rationale` | `FLAG_INVALID_TOPOLOGY_AUDIT` |
| `READING_GAP_TREATED_AS_NORMAL` | Telemetry drop (`delta_prev_sec > 2 * sampling_interval_sec`, e.g. 2700s vs 300s) where `is_gap_after_prev = false` | Compares `SensorReading.delta_prev_sec` against `2 * Sensor.sampling_interval_sec` | `RAISE_MISSING_TELEMETRY_GAP_ALARM` |
| `ALARM_UNLINKED_TO_AFFECTED_LOTS` | Excursion/outage `Alarm` occurred in a zone while active `ZoneLotAssignment` rows overlapped `[triggered_at, resolved_at]`, yet `affected_lot_count = 0` | Temporal & spatial interval join between `Alarm` and `ZoneLotAssignment` | `BACKFILL_AFFECTED_LOT_LINKS_AND_QUARANTINE` |

---

## 6. Lawful Provenance & Public Reference Guidance
- **100% Synthetic Data (`seed=20261022`)**: All records are deterministically synthesized using Python's Mersenne Twister PRNG seeded with `20261022`. Zero personal, confidential, or proprietary data is used.
- **Schema Inspiration**: Temperature and relative humidity envelopes follow public cold-chain guidelines from the **World Health Organization (WHO Technical Supplement: Temperature Mapping of Storage Areas)**, **EU GDP Guidelines (2013/C 343/01)**, and **ISA-18.2 Industrial Alarm Management** lifecycle states.
